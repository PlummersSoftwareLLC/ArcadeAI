"""UNEXECUTED private CPU/stdlib tests; no archive input/model/CUDA reads."""
import contextlib
import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('private_archived_payload_auditor',Path(__file__).with_name('audit_payloads.py'))
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class GuardTests(unittest.TestCase):
    def test_default_literal_plan_has_no_source_input_framework_or_output_operation(self):
        original=__import__
        def guarded(name,*args,**kwargs):
            if name.startswith(('torch','numpy')):raise AssertionError('numerical import')
            return original(name,*args,**kwargs)
        with (mock.patch('builtins.__import__',side_effect=guarded),
              mock.patch.object(audit,'read_json',side_effect=AssertionError('input')),
              mock.patch.object(audit,'sha_file',side_effect=AssertionError('source')),
              mock.patch.object(Path,'mkdir',side_effect=AssertionError('output')),
              contextlib.redirect_stdout(io.StringIO()) as output):
            self.assertEqual(audit.main([]),0)
        self.assertEqual(output.getvalue(),audit.PLAN+'\n')

    def test_fixed_load_whitelist_cannot_include_checkpoint_or_sampler(self):
        allowed=audit.expected_payloads()
        self.assertEqual(len(allowed),14)
        self.assertFalse(any(path.name in ('trained.pt','torch-rng.pt','draw.pt','batch.npz') for path in allowed))
        fake=type('FakeTorch',(),dict(load=mock.Mock(side_effect=AssertionError('load'))))()
        with self.assertRaisesRegex(ValueError,'whitelist'):
            audit.load_payload(fake,audit.RUN_ROOT/audit.JOB/'inputs/trained.pt',
                dict(path=str(audit.RUN_ROOT/audit.JOB/'inputs/trained.pt'),bytes=0,sha256='bad'),allowed)
        fake.load.assert_not_called()


class SmallTensorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(2)
        cls.torch=torch

    def test_original_predicate_exact_mask_coordinates_scalar_and_none(self):
        t=self.torch
        expected=t.full((128,),.004128,dtype=t.float32)
        actual=expected.clone();actual[37]+=3.24249e-5
        left=dict(ce=t.tensor([1.,2.]),loss=1.002003,gradient={'named.bias':actual,'unused':None})
        right=dict(ce=t.tensor([1.,2.]),loss=1.,gradient={'named.bias':expected,'unused':None})
        records,masks,none=audit.recompute(t,left,right,'case')
        gradient=next(row for row in records if row['path']=='case/gradient/named.bias')
        self.assertEqual(gradient['violations'],1)
        self.assertEqual(gradient['max_violation']['index'],[37])
        self.assertTrue(t.equal(masks['case/gradient/named.bias'],~t.isclose(actual,expected,**audit.TOLS['gradient'],equal_nan=False)))
        self.assertTrue(next(row for row in records if row['path']=='case/loss')['passed'])
        self.assertEqual(none,['case/gradient/unused'])
        audit.equal_record(gradient,copy.deepcopy(gradient))
        broken=copy.deepcopy(gradient);broken['violations']=0
        with self.assertRaisesRegex(ValueError,'Statistic mismatch'):audit.equal_record(gradient,broken)

    def test_finite_dtype_shape_and_none_controls_fail_closed(self):
        t=self.torch
        for actual,expected in ((t.tensor([float('nan')]),t.tensor([float('nan')])),
                                (t.ones(2),t.ones(3)),(t.ones(2,dtype=t.float64),t.ones(2)),
                                ({'x':None},{'x':t.ones(1)})):
            with self.subTest(actual=type(actual)),self.assertRaises(ValueError):
                audit.recompute(t,actual,expected,'case')

    def test_canonical_tensor_and_rng_tuple_hash_has_independent_byte_expectation(self):
        t=self.torch
        value=t.tensor([1.,2.],dtype=t.float32)
        expected=hashlib.sha256(str(('torch.float32',[2])).encode()+struct.pack('<ff',1.,2.)).hexdigest()
        self.assertEqual(audit.tree_digest(t,value),expected)
        digest=hashlib.sha256(b'tuple'+b'7'+str(('torch.float32',[2])).encode()+struct.pack('<ff',1.,2.)+b'None').hexdigest()
        self.assertEqual(audit.tree_digest(t,(7,value,None)),digest)

    def test_small_payload_load_uses_weights_only_cpu_and_detects_hash_tamper(self):
        t=self.torch
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'case.actual.pt';t.save({'gradient':t.tensor([1.])},path)
            record=dict(path=str(path),bytes=path.stat().st_size,sha256=audit.sha_file(path))
            original=t.load
            with mock.patch.object(t,'load',wraps=original) as call:
                loaded=audit.load_payload(t,path,record,{path})
            self.assertEqual(call.call_args.kwargs,dict(map_location='cpu',weights_only=True))
            self.assertEqual(loaded['gradient'].tolist(),[1.])
            record['sha256']='0'*64
            with mock.patch.object(t,'load',side_effect=AssertionError('must not load')):
                with self.assertRaisesRegex(ValueError,'BEFORE'):audit.load_payload(t,path,record,{path})


if __name__=='__main__':
    unittest.main()
