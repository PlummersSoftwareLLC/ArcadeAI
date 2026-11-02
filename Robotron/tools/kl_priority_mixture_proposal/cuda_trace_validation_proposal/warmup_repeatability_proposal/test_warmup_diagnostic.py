"""SOURCE-ONLY, UNEXECUTED tests for the backward-only diagnostic.

Future authorized execution uses tiny CPU tensors and explicit device/compiler
adapters. It does not validate CUDA, compilation, Rainbow4096 or learning.
No dqn/frozen numerical helper/model/checkpoint imports or reads occur at import.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from . import cuda_trace_worker as worker
from . import cuda_trace_parent as parent


TOLERANCES = dict(gradient=dict(rtol=.002,atol=2e-6), ce=dict(rtol=.0002,atol=.00002),
                  scalars=dict(rtol=.002,atol=2e-6))
CASES = [dict(index=i+1,diagnostics=d,empty=e)
         for i,(d,e) in enumerate(((False,False),(False,True),(True,False),(True,True)))]


def digest_tree(torch, value):
    digest=hashlib.sha256()
    def walk(item):
        if isinstance(item,torch.Tensor):
            digest.update(str((str(item.dtype),list(item.shape))).encode())
            digest.update(item.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes())
        elif isinstance(item,dict):
            for key in sorted(item): digest.update(str(key).encode());walk(item[key])
        elif isinstance(item,(tuple,list)):
            for part in item:walk(part)
        else: digest.update(repr(item).encode())
    walk(value)
    return digest.hexdigest()


def finite(torch,value):
    if isinstance(value,torch.Tensor): return bool(torch.isfinite(value).all())
    if isinstance(value,dict): return all(finite(torch,item) for item in value.values())
    if isinstance(value,(tuple,list)): return all(finite(torch,item) for item in value)
    if isinstance(value,float):
        import math
        return math.isfinite(value)
    return True


def comparator_context(torch):
    return SimpleNamespace(torch=torch,lock=dict(tolerances=copy.deepcopy(TOLERANCES)),
        science=SimpleNamespace(finite=lambda ctx,value:finite(torch,value),
            tensor_bytes=lambda ctx,value:value.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()))


class CPUDeviceAdapter:
    """Only the explicitly listed CUDA/compile entry points are CPU-adapted."""
    def __init__(self,torch,ctx):
        self.real,self.ctx=torch,ctx
        self.cuda=SimpleNamespace(synchronize=lambda index:ctx.events.append(('sync',index)),
                                  max_memory_allocated=lambda index:0,max_memory_reserved=lambda index:0)
    def __getattr__(self,name): return getattr(self.real,name)
    def from_numpy(self,value):
        tensor=self.real.from_numpy(value)
        def transfer(*,device,dtype):
            if device!='cuda:0': raise AssertionError('Unexpected device boundary')
            return tensor.to(dtype=dtype)
        return SimpleNamespace(to=transfer)
    def ones(self,*args,device,dtype):
        if device!='cuda:0': raise AssertionError('Unexpected device boundary')
        return self.real.ones(*args,dtype=dtype)
    def autocast(self,device,*,dtype):
        if device!='cuda' or dtype!=self.real.float16: raise AssertionError('Unexpected AMP boundary')
        return contextlib.nullcontext() # explicit CPU-only control, no AMP claim
    def compile(self,kernel,*,dynamic,options):
        from torch._dynamo.utils import counters
        if dynamic is not False or options!={'triton.cudagraphs':False}:
            raise AssertionError('Compiler policy changed')
        counters['stats']['unique_graphs']+=1
        return kernel # no actual compiler execution in these CPU tests


def case_context(torch,np,root,variant='base_a',inject=None):
    """Tiny2x2 CPU net with real autograd/Adam; scientific source is a fake."""
    phase=root/variant; phase.mkdir()
    scripts=root/'private'; scripts.mkdir(exist_ok=True)
    for name in ('baseline_loss_kernel.py','loss_kernel.py'):
        (scripts/name).write_text('synthetic test source only\n')
    checkpoint=root/'synthetic-checkpoint'; checkpoint.write_bytes(b'opaque test identity; not a model')
    torch.manual_seed(123)
    online=torch.nn.Linear(2,2)
    a=SimpleNamespace(online_net=online,target_net=copy.deepcopy(online),infer_net=copy.deepcopy(online),
        optimizer=torch.optim.Adam(online.parameters(),lr=.001),
        _executed_ce_trace=None,training_steps=7,optimized_samples=28)
    a.grad_scaler=SimpleNamespace(step=lambda *args:None,update=lambda *args:None,
        state_dict=lambda:dict(scale=1048576.,growth_tracker=27))
    a._learning_optimizer_exposure=SimpleNamespace(snapshot=lambda:dict(process_id=77,instance_monotonic_ns=88,
        epoch=0,total=dict(attempts_started=0,outcomes_recorded=0,applied=0,amp_skipped=0,unavailable=0)))
    ctx=SimpleNamespace(variant=variant,agent=a,cfg=SimpleNamespace(),events=[],saves=[],kernel_calls=[],
        paths=dict(root=phase),layout=SimpleNamespace(output=root,scripts=scripts.parent),
        input_description_sha256='fixture-input-identity',input_files={},trained=checkpoint,
        lock=dict(warmup_cases=copy.deepcopy(CASES),tolerances=copy.deepcopy(TOLERANCES),
                  checkpoint=dict(sha256='test',bytes=checkpoint.stat().st_size)))
    ctx.torch=CPUDeviceAdapter(torch,ctx)
    def save(ctx,path,payload):
        ctx.events.append(('save',Path(path).name))
        with Path(path).open('xb') as stream:torch.save(payload,stream)
        record=dict(path=str(path),sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),bytes=Path(path).stat().st_size)
        ctx.saves.append(record)
        return record
    def rng_state(ctx): return dict(cpu=torch.get_rng_state().clone(),cuda=torch.tensor([123],dtype=torch.uint8))
    ctx.science=SimpleNamespace(
        finite=lambda ctx,value:finite(torch,value),digest_tree=lambda ctx,value:digest_tree(torch,value),
        tensor_bytes=lambda ctx,value:value.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes(),
        clocks=lambda ctx:dict(training_steps=a.training_steps,optimized_samples=a.optimized_samples),
        rng_state=rng_state,restore_rng=lambda ctx,value:torch.set_rng_state(value['cpu']),
        save_tensors=save,optimizer_observation=lambda ctx:dict(persistent=digest_tree(torch,worker.full_state(ctx)),
            exposure=a._learning_optimizer_exposure.snapshot()),modules_private=lambda ctx:None)
    ctx.rng=rng_state(ctx)
    ctx.parent=SimpleNamespace(digest=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        stable_file=lambda *args,**kwargs:'synthetic-stable-copy')
    ctx.base=SimpleNamespace(verify_source_copies=lambda *args:ctx.events.append(('source_guard',)))
    ctx.manifest=dict(sources={},trained_fixture=dict(copied='synthetic-stable-copy'))
    class Kernel(torch.nn.Module):
        def __init__(self,online,target,cfg,*,diagnostics,**kwargs):
            super().__init__();self.online=online;self.diagnostics=diagnostics
            ctx.events.append(('kernel_source',variant,diagnostics,kwargs))
        def forward(self,states,actions,rewards,next_states,dones,horizons,expert,weights,schedule):
            ctx.kernel_calls.append((self.diagnostics,bool((states==0).all())))
            if inject is not None: inject(ctx,len(ctx.kernel_calls))
            logits=self.online(states)
            ce=(logits.sum(1)-rewards).square()
            loss=(ce*weights).mean()
            return loss,ce,loss.detach()*0,logits.detach().mean(0)
    ctx.loss=SimpleNamespace(TrainingLoss=Kernel,__file__=str(scripts/('baseline_loss_kernel.py' if variant!='off' else 'loss_kernel.py')))
    states=np.array([[1.,2.],[.5,-.5]],dtype=np.float32)
    ctx.batch=(states,np.array([0,1],dtype=np.int64),np.array([.2,-.1],dtype=np.float32),states.copy(),
        np.array([0,1],dtype=np.uint8),np.array([1,3],dtype=np.uint8),np.array([1,0],dtype=np.uint8),
        np.array([0,1],dtype=np.uint8),np.array([0,1],dtype=np.int64),np.array([1.,.5],dtype=np.float32))
    return ctx


@contextlib.contextmanager
def cpu_phase(worker,ctx):
    # Effective-GIL observation is explicit injection, not a CPU/GIL claim.
    with mock.patch.object(worker,'sys',SimpleNamespace(_is_gil_enabled=lambda:False,stderr=io.StringIO())):
        yield


class ComparatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        torch.set_num_threads(2)
        cls.torch=torch

    def test_one_of128_original_tolerance_path_mask_and_coordinate_retained(self):
        t=self.torch;ctx=comparator_context(t)
        expected=t.full((128,),.004128,dtype=t.float32);actual=expected.clone();actual[37]+=3.24249e-5
        records,masks=worker.compare_payload(ctx,dict(gradient={'named.bias':actual}),dict(gradient={'named.bias':expected}),
                                             'case-01-diagnostic0-empty0')
        record=records[0];path='case-01-diagnostic0-empty0/gradient/named.bias'
        self.assertEqual(record['path'],path);self.assertFalse(record['passed']);self.assertEqual(record['violations'],1)
        self.assertEqual(record['tolerance'],TOLERANCES['gradient'])
        self.assertEqual(record['coordinate_examples'][0]['index'],[37])
        self.assertEqual(record['max_violation']['index'],[37])
        self.assertGreater(record['max_violation']['absolute_error'],record['max_violation']['allowed_bound'])
        self.assertTrue(t.equal(masks[path],~t.isclose(actual,expected,**TOLERANCES['gradient'],equal_nan=False)))
        self.assertEqual(record['actual_sha256'],hashlib.sha256(ctx.science.tensor_bytes(ctx,actual)).hexdigest())

    def test_per_field_tolerances_and_integer_exactness_are_unchanged(self):
        ctx=comparator_context(self.torch)
        self.assertEqual(worker.tolerance_for(ctx,'case/ce'),TOLERANCES['ce'])
        self.assertEqual(worker.tolerance_for(ctx,'case/loss'),TOLERANCES['scalars'])
        self.assertEqual(worker.tolerance_for(ctx,'case/bc_loss'),TOLERANCES['scalars'])
        self.assertEqual(worker.tolerance_for(ctx,'case/gradient/a'),TOLERANCES['gradient'])
        self.assertEqual(worker.tolerance_for(ctx,'case/a',False),dict(rtol=0.,atol=0.))

    def test_python_scalar_loss_keeps_original_symmetric_math_isclose_policy(self):
        ctx=comparator_context(self.torch)
        # This passes original scalar math.isclose, but exceeds a tensor's
        # expected-only additive bound. Do not silently replace that policy.
        records,masks=worker.compare_payload(ctx,{'loss':1.002003},{'loss':1.},'case')
        self.assertTrue(records[0]['passed']);self.assertEqual(masks,{})
        self.assertEqual(records[0]['tolerance'],TOLERANCES['scalars'])

    def test_native_float32_boundary_and_zero_reference_mask_agree_with_torch(self):
        t=self.torch;ctx=comparator_context(t)
        ref=t.tensor([0.,.001,.1,1.],dtype=t.float32)
        bound=TOLERANCES['gradient']['atol']+TOLERANCES['gradient']['rtol']*ref.abs()
        actual=ref+bound
        actual=t.cat((t.nextafter(actual,t.full_like(actual,float('-inf'))),actual,
                      t.nextafter(actual,t.full_like(actual,float('inf')))))
        expected=ref.repeat(3)
        records,masks=worker.compare_payload(ctx,{'gradient':actual},{'gradient':expected},'case')
        wanted=~t.isclose(actual,expected,**TOLERANCES['gradient'],equal_nan=False)
        self.assertEqual(records[0]['violations'],int(wanted.sum()))
        self.assertTrue(t.equal(masks['case/gradient'],wanted))

    def test_nonfinite_matching_patterns_are_fatal_not_supported_amp_skips(self):
        t=self.torch;ctx=comparator_context(t)
        for value in (float('nan'),float('inf'),float('-inf')):
            with self.subTest(value=value),self.assertRaisesRegex(RuntimeError,'Nonfinite'):
                worker.compare_payload(ctx,t.tensor([value]),t.tensor([value]),'case/gradient')

    def test_structure_dtype_none_and_key_mismatches_fatal(self):
        t=self.torch;ctx=comparator_context(t)
        pairs=((t.ones(2),t.ones(3)),(t.ones(2,dtype=t.float64),t.ones(2)),
               ({'a':None},{'a':t.ones(2)}),({'b':t.ones(2)},{'a':t.ones(2)}))
        for actual,expected in pairs:
            with self.subTest(actual=type(actual)),self.assertRaises(RuntimeError):
                worker.compare_payload(ctx,actual,expected,'case')

    def test_unexpected_assertclose_runtime_exception_is_not_numeric_mismatch(self):
        t=self.torch;ctx=comparator_context(t);failure=OSError('synthetic comparator failure')
        with mock.patch.object(t.testing,'assert_close',side_effect=failure):
            with self.assertRaises(OSError) as caught:worker.compare_payload(ctx,t.ones(2),t.ones(2),'case/gradient')
        self.assertIs(caught.exception,failure)

    def test_partial_comparison_records_and_masks_survive_later_fatal_structure(self):
        t=self.torch;ctx=comparator_context(t);records=[];masks={}
        with self.assertRaisesRegex(RuntimeError,'Structural'):
            worker.compare_payload(ctx,dict(first=t.tensor([1.]),second=t.ones(2)),
                dict(first=t.tensor([0.]),second=t.ones(3)),'case',records=records,masks=masks)
        self.assertEqual(len(records),1);self.assertFalse(records[0]['passed'])
        self.assertIn('case/first',masks)


class RetentionAndCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        import numpy as np
        torch.set_num_threads(2)
        cls.torch,cls.np=torch,np

    def baseline(self,root):
        ctx=case_context(self.torch,self.np,root)
        with cpu_phase(worker,ctx):result=worker.run_cases(ctx)
        worker.write_json(root/'base_a/phase-result.json',result)
        return ctx,result

    def test_baseline_all_four_cases_no_steps_and_persisted_state_rng_payloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);ctx,result=self.baseline(root)
            self.assertEqual(result['status'],'OBSERVATIONS_COMPLETE');self.assertFalse(result['qualification_pass'])
            self.assertEqual(result['comparison_scope'],'baseline_reference_only')
            self.assertEqual(ctx.kernel_calls,[(False,False),(False,True),(True,False),(True,True)])
            self.assertEqual(result['update_calls'],dict(optimizer_step=0,scaler_step=0,scaler_update=0))
            self.assertEqual(result['before'],result['after'])
            for row in result['cases']:
                payload=self.torch.load(row['actual']['path'],map_location='cpu',weights_only=True)
                self.assertIn('gradient',payload['numerical']);self.assertEqual(payload['pre_state_sha256'],payload['post_state_sha256'])
                self.assertEqual(row['pre_rng_sha256'],row['post_rng_sha256'])
            self.assertFalse(list(root.rglob('attempt-*.json')))

    def test_full_candidate_payload_exists_before_each_compare_and_four_finite_mismatches_continue(self):
        t=self.torch
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.baseline(root);ctx=case_context(t,self.np,root,'off')
            comparisons=[]
            def compare(ctx,actual,expected,label,*,records,masks):
                path=ctx.paths['root']/(label+'.actual.pt')
                self.assertTrue(path.is_file())
                stored=t.load(path,map_location='cpu',weights_only=True)
                self.assertIn('pre_rng',stored);self.assertIn('post_rng',stored)
                self.assertTrue((ctx.paths['root']/(label+'.payload-retained.json')).is_file())
                self.assertEqual(set(stored['numerical']['gradient']),set(actual['gradient']))
                comparisons.append(label)
                records.append(dict(path=label+'/gradient/synthetic',passed=False,violations=1))
                masks[label]=t.tensor([True])
                return records,masks
            with mock.patch.object(worker,'compare_payload',side_effect=compare),cpu_phase(worker,ctx):result=worker.run_cases(ctx)
            self.assertEqual(len(comparisons),4);self.assertEqual(len(result['cases']),4)
            self.assertFalse(result['comparison_pass']);self.assertTrue(result['interpretation_requires_review'])
            self.assertFalse(result['qualification_pass']);self.assertEqual(len(list((root/'off').glob('*.violations.pt'))),4)
            self.assertTrue(all(not row['comparison_pass'] for row in result['cases']))

    def test_same_source_repeat_uses_baseline_constructor_no_trace_rows_argument(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.baseline(root);ctx=case_context(self.torch,self.np,root,'base_repeat')
            with cpu_phase(worker,ctx):result=worker.run_cases(ctx)
            self.assertTrue(result['comparison_pass']);self.assertFalse(result['qualification_pass'])
            calls=[event for event in ctx.events if event[0]=='kernel_source']
            self.assertEqual(len(calls),2);self.assertTrue(all(event[3]=={} for event in calls))

    def test_cross_role_scientific_state_mismatch_is_fatal_before_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.baseline(root);ctx=case_context(self.torch,self.np,root,'off')
            with self.torch.no_grad():ctx.agent.target_net.bias.add_(.125)
            with cpu_phase(worker,ctx),self.assertRaisesRegex(RuntimeError,'Cross-role persistent'):
                worker.run_cases(ctx)
            self.assertEqual(len(ctx.kernel_calls),1)
            self.assertEqual(len(list((root/'off').glob('*.actual.pt'))),1)

    def test_rng_post_change_is_retained_for_review_without_claiming_parity(self):
        def random_forward(ctx,ordinal):self.torch.rand(1)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.baseline(root);ctx=case_context(self.torch,self.np,root,'off',random_forward)
            with cpu_phase(worker,ctx):result=worker.run_cases(ctx)
            self.assertTrue(result['comparison_pass']);self.assertTrue(result['interpretation_requires_review'])
            self.assertTrue(all(row['rng_changed_components']==['cpu'] for row in result['cases']))
            self.assertTrue(all(row['cross_role_post_rng_changed_components']==['cpu'] for row in result['cases']))
            self.assertFalse(result['qualification_pass'])

    def test_pre_rng_control_mismatch_is_fatal_before_first_forward(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=case_context(self.torch,self.np,Path(temporary))
            ctx.rng['cpu']=self.torch.Generator().manual_seed(99).get_state()
            ctx.science.restore_rng=lambda *args:None
            with cpu_phase(worker,ctx),self.assertRaisesRegex(RuntimeError,'Pre-case RNG'):
                worker.run_cases(ctx)
            self.assertEqual(ctx.kernel_calls,[])

    def test_state_hash_ignores_only_process_identity_retains_epoch_and_counters(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=case_context(self.torch,self.np,Path(temporary))
            original=ctx.agent._learning_optimizer_exposure.snapshot()
            before=digest_tree(self.torch,worker.full_state(ctx))
            changed=copy.deepcopy(original);changed['process_id']=99;changed['instance_monotonic_ns']=111
            ctx.agent._learning_optimizer_exposure.snapshot=lambda:copy.deepcopy(changed)
            self.assertEqual(before,digest_tree(self.torch,worker.full_state(ctx)))
            changed['total']['applied']=1
            self.assertNotEqual(before,digest_tree(self.torch,worker.full_state(ctx)))
            changed['total']['applied']=0;changed['epoch']=1
            self.assertNotEqual(before,digest_tree(self.torch,worker.full_state(ctx)))

    def test_structural_comparison_error_is_fatal_after_retention_no_later_case(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.baseline(root);ctx=case_context(self.torch,self.np,root,'off')
            original=RuntimeError('Structural tensor mismatch: original')
            with mock.patch.object(worker,'compare_payload',side_effect=original),cpu_phase(worker,ctx):
                with self.assertRaises(RuntimeError) as caught:worker.run_cases(ctx)
            self.assertIs(caught.exception,original);self.assertEqual(len(ctx.kernel_calls),1)
            self.assertEqual(len(list((root/'off').glob('*.actual.pt'))),1)

    def test_nonfinite_backward_payload_retained_then_fatal_without_amp_skip(self):
        def poison(ctx,ordinal):
            if ordinal==1:
                ctx.agent.online_net.weight.register_hook(lambda grad:grad*self.torch.tensor(float('nan')))
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);ctx=case_context(self.torch,self.np,root,inject=poison)
            with cpu_phase(worker,ctx),self.assertRaisesRegex(RuntimeError,'Nonfinite unscaled'):
                worker.run_cases(ctx)
            payloads=list((root/'base_a').glob('*.actual.pt'));self.assertEqual(len(payloads),1)
            payload=self.torch.load(payloads[0],map_location='cpu',weights_only=True)
            self.assertFalse(finite(self.torch,payload['numerical']['gradient']))
            self.assertEqual(len(ctx.kernel_calls),1)

    def test_kernel_failure_not_replaced_by_secondary_reporting_failure(self):
        original=RuntimeError('original kernel error')
        def explode(ctx,ordinal):raise original
        with tempfile.TemporaryDirectory() as temporary:
            ctx=case_context(self.torch,self.np,Path(temporary),inject=explode)
            original_write=worker.write_json
            def report(path,value):
                if str(path).endswith('.failure.json'):raise OSError('secondary persistence fault')
                return original_write(path,value)
            with mock.patch.object(worker,'write_json',side_effect=report),cpu_phase(worker,ctx):
                with self.assertRaises(RuntimeError) as caught:worker.run_cases(ctx)
            self.assertIs(caught.exception,original);self.assertEqual(len(ctx.kernel_calls),1)

    def test_partial_comparison_failure_keeps_original_when_both_reports_fail(self):
        original=RuntimeError('original structural comparison fault')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.baseline(root);ctx=case_context(self.torch,self.np,root,'off')
            def broken(ctx,actual,expected,label,*,records,masks):
                records.append(dict(path=label+'/gradient/first',passed=False,violations=1))
                masks[label]=self.torch.tensor([True])
                raise original
            original_write=worker.write_json
            def reports(path,value):
                if str(path).endswith(('.comparison.json','.failure.json')):raise OSError('secondary reporting failure')
                return original_write(path,value)
            with mock.patch.object(worker,'compare_payload',side_effect=broken), \
                 mock.patch.object(worker,'write_json',side_effect=reports),cpu_phase(worker,ctx):
                with self.assertRaises(RuntimeError) as caught:worker.run_cases(ctx)
            self.assertIs(caught.exception,original)
            self.assertEqual(len(list((root/'off').glob('*.actual.pt'))),1)
            self.assertEqual(len(list((root/'off').glob('*.violations.pt'))),1)
            self.assertEqual(len(ctx.kernel_calls),1)

    def test_payload_save_io_failure_fatal_and_never_compared_or_continued(self):
        with tempfile.TemporaryDirectory() as temporary:
            ctx=case_context(self.torch,self.np,Path(temporary))
            with mock.patch.object(ctx.science,'save_tensors',side_effect=OSError('disk full')), \
                 mock.patch.object(worker,'compare_payload',side_effect=AssertionError('must not compare')),cpu_phase(worker,ctx):
                with self.assertRaisesRegex(OSError,'disk full'):worker.run_cases(ctx)
            self.assertEqual(len(ctx.kernel_calls),1)

    def test_forbidden_optimizer_step_is_fatal_not_a_numeric_mismatch(self):
        def violate(ctx,ordinal):ctx.agent.optimizer.step()
        with tempfile.TemporaryDirectory() as temporary:
            ctx=case_context(self.torch,self.np,Path(temporary),inject=violate)
            with cpu_phase(worker,ctx),self.assertRaisesRegex(RuntimeError,'Forbidden update'):
                worker.run_cases(ctx)
            self.assertEqual(len(ctx.kernel_calls),1)

    def test_scaler_step_and_update_are_each_forbidden_even_without_optimizer(self):
        for method in ('step','update'):
            with self.subTest(method=method),tempfile.TemporaryDirectory() as temporary:
                def violate(ctx,ordinal):getattr(ctx.agent.grad_scaler,method)()
                ctx=case_context(self.torch,self.np,Path(temporary),inject=violate)
                with cpu_phase(worker,ctx),self.assertRaisesRegex(RuntimeError,'Forbidden update'):
                    worker.run_cases(ctx)
                self.assertEqual(len(ctx.kernel_calls),1)


class DefaultGuardTests(unittest.TestCase):
    def test_setup_role_mapping_uses_original_class_twice_and_does_not_regenerate_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);scripts=root/'Scripts'/'dqn';scripts.mkdir(parents=True)
            for name in ('baseline_loss_kernel.py','loss_kernel.py'):(scripts/name).write_text(name)
            for role,wanted_setup,wanted_inputs in (('base_a','base','base'),('base_repeat','base','off'),('off','off','off')):
                calls=[]
                ctx=SimpleNamespace(variant=role,layout=SimpleNamespace(scripts=scripts.parent),
                    parent=SimpleNamespace(digest=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()),
                    manifest=dict(sources={name:dict(sha256=hashlib.sha256((scripts/name).read_bytes()).hexdigest())
                                           for name in ('baseline_loss_kernel.py','loss_kernel.py')}))
                def setup(ctx):
                    calls.append(('setup',ctx.variant));ctx.agent=SimpleNamespace(_executed_ce_trace=None)
                    ctx.loss=SimpleNamespace(__file__=str(scripts/('baseline_loss_kernel.py' if ctx.variant=='base' else 'loss_kernel.py')))
                ctx.science=SimpleNamespace(setup=setup,inputs=lambda ctx:calls.append(('inputs',ctx.variant)))
                with mock.patch.dict(worker.os.environ,{},clear=True):worker.setup_case_source(ctx)
                self.assertEqual(ctx.variant,role)
                self.assertEqual(calls,[('setup',wanted_setup),('inputs',wanted_inputs)])

    def test_parent_default_no_helpers_reads_numerics_launch_or_output(self):
        original_import=__import__
        def guarded(name,*args,**kwargs):
            if name.startswith(('torch','numpy')):raise AssertionError('Numerical default import')
            return original_import(name,*args,**kwargs)
        with mock.patch('builtins.__import__',side_effect=guarded), \
             mock.patch.object(parent,'read_lock',side_effect=AssertionError('source read')), \
             mock.patch.object(parent,'launch',side_effect=AssertionError('launch')), \
             mock.patch.object(Path,'mkdir',side_effect=AssertionError('output')),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(parent.main([]),0)
        result=json.loads(output.getvalue())
        self.assertFalse(result['launch']);self.assertFalse(result['qualification_pass']);self.assertEqual(result['attempts'],0)

    def test_worker_without_owned_manifest_exits_before_bootstrap_or_numerics(self):
        with mock.patch.object(worker,'bootstrap',side_effect=AssertionError('bootstrap')), \
             mock.patch.object(worker,'load_science',side_effect=AssertionError('numerical helper')), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:worker.main([])
        self.assertEqual(caught.exception.code,2)


if __name__=='__main__':
    unittest.main()
