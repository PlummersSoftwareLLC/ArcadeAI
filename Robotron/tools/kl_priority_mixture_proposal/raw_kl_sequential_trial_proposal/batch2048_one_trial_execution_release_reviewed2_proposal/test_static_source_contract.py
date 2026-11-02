"""Authored/unexecuted stdlib static-source boundary guards; no numerical imports."""
import ast
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

HERE=Path(__file__).parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


adapter=load('_CE2048_corrected_adapter_contract',HERE/'run_CE_batch_transition.py')
controller=load('_CE2048_corrected_controller_contract',HERE/'run_one_trial.py')
deadline=load('_CE2048_corrected_deadline_contract',HERE/'deadline_guard.py')
readiness=load('_CE2048_corrected_readiness_contract',HERE/'execution_readiness.py')


def fingerprint(path,limit):
    path=Path(path);before=path.lstat()
    def identity(value):return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns,value.st_mode,value.st_uid,value.st_nlink)
    if not (path.is_absolute() and path==path.resolve(strict=True) and not path.is_symlink()
        and stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o444
        and before.st_uid==os.getuid() and before.st_nlink==1 and 0<before.st_size<=limit):
        raise AssertionError('Static source is not bounded owned readonly metadata: '+str(path))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        if identity(os.fstat(stream.fileno()))!=identity(before):raise AssertionError('Source open identity changed')
        data=stream.read(limit+1)
        if identity(os.fstat(stream.fileno()))!=identity(before):raise AssertionError('Source changed during read')
    if identity(path.lstat())!=identity(before):raise AssertionError('Source path identity changed')
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


class StaticSourceContracts(unittest.TestCase):
    def test_real_phase_early_boundary_authenticates_and_imports_actual_stdlib_helper(self):
        forbidden=lambda:{name for name in sys.modules if name.split('.')[0] in ('torch','numpy','dqn')}
        before=forbidden();calls=[]
        def source_load(path,name):calls.append(path);return load(name,Path(path))
        base=SimpleNamespace(MAX_SOURCE=4<<20,fingerprint=fingerprint,load_module=source_load)
        with patch('subprocess.run',side_effect=AssertionError('No subprocess')),             patch('subprocess.Popen',side_effect=AssertionError('No subprocess')),             patch('os.kill',side_effect=AssertionError('No signal')):
            helper=adapter.phase_early_module(base)
        self.assertEqual(calls,[str(adapter.PHASE_EARLY)])
        self.assertEqual(helper.EXECUTION_KIND,'phase_early_insurance2048')
        self.assertTrue(callable(helper.EarlyPhaseInsurance))
        self.assertTrue(callable(helper.phase_insurance_floor))
        self.assertEqual(forbidden(),before)

    def test_wrong_manifest_or_source_refuses_before_any_helper_import(self):
        importer=Mock(side_effect=AssertionError('Wrong source must not import'))
        base=SimpleNamespace(MAX_SOURCE=4<<20,fingerprint=fingerprint,load_module=importer)
        actual=adapter.PHASE_EARLY_MANIFEST_SHA
        with patch.object(adapter,'PHASE_EARLY_MANIFEST_SHA',actual+'6'):
            with self.assertRaisesRegex(RuntimeError,'Exact phase early-insurance manifest differs'):
                adapter.phase_early_module(base)
        with patch.object(adapter,'PHASE_EARLY_SHA','0'*64):
            with self.assertRaisesRegex(RuntimeError,'Exact phase early-insurance source differs'):
                adapter.phase_early_module(base)
        importer.assert_not_called()

    def test_all_digest_literals_and_path_bound_static_source_targets_match(self):
        def check(path,sha,expected_bytes=None):
            self.assertRegex(sha,r'^[0-9a-f]{64}$')
            observed=fingerprint(path,4<<20)
            self.assertEqual(observed['sha256'],sha,str(path))
            if expected_bytes is not None:self.assertEqual(observed['bytes'],expected_bytes)
        for module in (adapter,controller,deadline,readiness):
            for key,value in vars(module).items():
                if key.endswith(('_SHA','_SHA256')) and isinstance(value,str):
                    self.assertRegex(value,r'^[0-9a-f]{64}$',module.__name__+'.'+key)
            for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
                if isinstance(node,ast.Constant) and isinstance(node.value,str) and re.fullmatch('[0-9a-f]{60,70}',node.value):
                    self.assertEqual(len(node.value),64,(module.__name__,node.lineno))
        for path,sha in [(adapter.V4,adapter.V4_SHA),(adapter.PHASE,adapter.PHASE_SHA),
            (adapter.PHASE.parent/'strict_phase_base.py',adapter.STRICT_SHA),
            (adapter.ANCESTOR,adapter.ANCESTOR_SHA),(adapter.HORIZON,adapter.HORIZON_SHA),
            (adapter.BOUNDARY,adapter.BOUNDARY_SHA),(adapter.PHASE_EARLY,adapter.PHASE_EARLY_SHA),
            (adapter.PHASE_EARLY.parent/'preparation-manifest.json',adapter.PHASE_EARLY_MANIFEST_SHA),
            (adapter.RELEASE_VALIDATOR,adapter.RELEASE_VALIDATOR_SHA),(controller.ADAPTER,controller.ADAPTER_SHA),
            (controller.HORIZON,controller.HORIZON_SHA),(controller.EARLY_PATH,controller.EARLY_SHA),
            (controller.RELEASE_VALIDATOR,controller.RELEASE_VALIDATOR_SHA),
            (deadline.PROFILE_PATH,deadline.PROFILE_SHA),(deadline.RELEASE_VALIDATOR,deadline.RELEASE_VALIDATOR_SHA)]:check(path,sha)
        for value in adapter.CPU2048_BINDING.values():check(value['path'],value['sha256'],value['bytes'])
        source_root=HERE.parent
        for name,sha in adapter.CANDIDATE.items():check(source_root/name,sha)
        def descriptors(value):
            if isinstance(value,dict):
                if {'path','sha256','bytes'}<=set(value):check(value['path'],value['sha256'],value['bytes'])
                for item in value.values():descriptors(item)
            elif isinstance(value,(list,tuple)):
                for item in value:descriptors(item)
        descriptors(readiness.FIXED);descriptors(readiness.GUARDS)


if __name__=='__main__':unittest.main()
