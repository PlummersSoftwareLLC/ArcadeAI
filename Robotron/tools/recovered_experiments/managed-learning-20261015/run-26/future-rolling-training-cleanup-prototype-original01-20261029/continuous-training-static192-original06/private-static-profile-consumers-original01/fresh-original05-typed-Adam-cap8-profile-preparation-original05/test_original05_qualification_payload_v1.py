"""Two genuine-function payload/publication-boundary checks; synthetic evidence.

Root may run this stdlib-only fixture later. Author has not imported/run it.
No Torch, model/journal/capturebody reads, process, socket or active metadata
writes. Actual capture_qualification_payload and qualify_capture AST only;
full capture/CPU/observer validation is independently qualified elsewhere.
"""
import ast
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

SOURCE=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/fresh-original05-typed-Adam-cap8-profile-preparation-original05/prepare_fresh_original05_typed_capture_profiles_v1.py')
SHA='9ca5fff59644e4946c61909492222601c5d5e2f8185a9bd349dbeac5c6ec32ed'

class Original05PayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=SOURCE.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=SHA:raise AssertionError('Selected profile constructor source changed')
        tree=ast.parse(raw);wanted={'capture_qualification_payload','qualify_capture','require'}
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in wanted]
        if len(nodes)!=3:raise AssertionError('Actual payload/qualification function inventory differs')
        cls.nodes=nodes

    def harness(self,fail=False):
        calls=[]
        fixed={}
        for n in ast.walk(ast.Module(body=self.nodes,type_ignores=[])):
            if isinstance(n,ast.Subscript)and isinstance(n.value,ast.Name)and n.value.id=='FIXED':
                fixed[ast.literal_eval(n.slice)]=dict(path='/synthetic/'+ast.literal_eval(n.slice),sha256='1'*64,bytes=1)
        def capture(h):
            calls.append('capture')
            if fail:raise ValueError('synthetic capture proof failed')
            return dict(progress_proof=dict(classification='synthetic-typed-proof',dose=60380)),dict()
        def pin(path):return dict(path=str(path),sha256='2'*64,bytes=1)
        def put(path,value):
            calls.append(('put',str(path),value));return pin(path)
        h=SimpleNamespace(pin=pin,put=put)
        ns=dict(Path=Path,FIXED=fixed,CANDIDATE='4ab677004e8a178f69d4438583a07d00a76f3b90e09eb08870ad0528fc08f871',
            __file__=str(SOURCE),capture=capture,dependencies=lambda:(h,None))
        exec(compile(ast.Module(body=self.nodes,type_ignores=[]),str(SOURCE),'exec'),ns)
        return ns,h,fixed,calls

    def test_actual_payload_is_deterministic_and_consumes_capture_result(self):
        ns,h,fixed,calls=self.harness()
        first=ns['capture_qualification_payload'](h);second=ns['capture_qualification_payload'](h)
        self.assertEqual(first,second)
        self.assertEqual(calls,['capture','capture'])
        self.assertEqual(first['typed_progress_proof'],dict(classification='synthetic-typed-proof',dose=60380))
        self.assertEqual(first['typed_progress_verifier'],fixed['closed_capture_validator'])
        self.assertEqual(first['capture_plan'],fixed['capture_plan'])
        self.assertEqual(first['capture_result'],fixed['capture_result'])
        self.assertEqual(first['policy_checkpoint_sha256'],ns['CANDIDATE'])
        self.assertEqual(first['status'],'CAPTURE_CPU_VERIFIED_AND_ORIGINAL_SCOPE_CLOSED')
        self.assertFalse(first['new_exposure_credited']);self.assertFalse(first['quality_qualified'])

    def test_actual_qualification_refuses_before_output_on_capture_or_payload_failure(self):
        with tempfile.TemporaryDirectory()as directory:
            for phase in ('capture','payload'):
                ns,h,fixed,calls=self.harness(fail=phase=='capture')
                if phase=='payload':
                    def broken_payload(h):raise ValueError('synthetic payload construction failed')
                    ns['capture_qualification_payload']=broken_payload
                output=Path(directory)/phase
                with self.assertRaises(ValueError):ns['qualify_capture'](output)
                self.assertFalse(output.exists());self.assertFalse(any(isinstance(x,tuple)for x in calls))
            ns,h,fixed,calls=self.harness();output=Path(directory)/'positive'
            result=ns['qualify_capture'](output)
            self.assertTrue(output.is_dir());self.assertEqual(result['path'],str(output/'original-valid-capture-qualification.json'))
            self.assertEqual(calls[0],'capture');self.assertEqual(calls[1][0],'put')

if __name__=='__main__':unittest.main()
