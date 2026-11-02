"""New persistent-coordinator scope using real temporary flock descriptors.

Imports old fixture definitions only; no old test methods or GPU runtime run.
The canonical coordinator is never opened for writing or locked by these tests.
"""
from pathlib import Path
import copy
import importlib.util
import json
import os
import sys
import unittest

HERE=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


runtime=load('_new_compiled32_coordinator_runtime',HERE/'run_compiled_startup32_v2.py')
control=load('_new_compiled32_coordinator_control',HERE/'control_compiled_startup32_v2.py')
fixtures=load('_consumed_compiled32_fixture_definitions_only',HERE/'test_compiled_startup32_contract_v1.py')


class PersistentCoordinatorContract(unittest.TestCase):
    def fixture(self):return fixtures.CompiledStartup32Contract.fixture(self)
    def coordinator(self):
        directory=self.fixture();path=directory/'persistent.lock';path.touch(mode=0o600)
        return directory,path,runtime.helpers().pin(path)

    def test_existing_coordinator_real_exclusion_release_and_reacquire_preserve_full8(self):
        directory,path,expected=self.coordinator();first=runtime.PrivateLease(expected)
        second=runtime.PrivateLease(expected)
        try:
            first.acquire()
            with self.assertRaises(BlockingIOError):second.acquire()
            self.assertIsNone(second.fd);self.assertFalse(second.locked)
            self.assertEqual(runtime.helpers().pin(path),expected)
            first.release()
            self.assertTrue(path.exists());self.assertEqual(runtime.helpers().pin(path),expected)
            second.acquire();self.assertTrue(second.locked);second.release()
            self.assertEqual(runtime.helpers().pin(path),expected)
            with self.assertRaises(ValueError):second.release()
        finally:
            for lease in (first,second):
                if lease.fd is not None:os.close(lease.fd);lease.fd=None

    def test_stale_identity_symlink_and_replaced_original_never_touch_foreign_inode(self):
        directory,path,expected=self.coordinator()
        stale=copy.deepcopy(expected);stale['identity']['inode']+=1
        lease=runtime.PrivateLease(stale)
        with self.assertRaises(ValueError):lease.acquire()
        self.assertIsNone(lease.fd);self.assertEqual(runtime.helpers().pin(path),expected)
        lease=runtime.PrivateLease(expected);lease.acquire()
        try:
            old=directory/'held-original.lock';path.rename(old);path.touch(mode=0o600)
            foreign=runtime.helpers().pin(path)
            with self.assertRaises(ValueError):lease.release()
            self.assertEqual(runtime.helpers().pin(path),foreign)
            self.assertEqual(old.stat().st_ino,expected['identity']['inode'])
        finally:
            if lease.fd is not None:os.close(lease.fd);lease.fd=None
        path.unlink();path.symlink_to(old)
        with self.assertRaises(ValueError):runtime.PrivateLease(expected).acquire()
        self.assertTrue(path.is_symlink());self.assertEqual(old.read_bytes(),b'')

    def test_v2_job_and_exact_source_inverse_select_the_existing_coordinator_driver(self):
        directory=self.fixture();job=fixtures.CompiledStartup32Contract.job(self,directory)
        preflight=runtime.G/'logs/managed-learning-20261015/run-26/compiled-startup32-scope-ownership-contract-original01-preparation-20261022/canonical-persistent-lease-readonly-preflight.json'
        expected=json.loads(preflight.read_bytes())['lease']
        job.update(schema='robotron-compiled-startup32-original-v2',lease=expected)
        self.assertEqual(runtime.validate_job(job),directory/'uncreated-output')
        changed=copy.deepcopy(job);changed['lease']['path']=str(directory/'foreign.lock')
        with self.assertRaises(ValueError):runtime.validate_job(changed)
        changed=copy.deepcopy(job);changed['lease']['bytes']=1
        with self.assertRaises(ValueError):runtime.validate_job(changed)
        manifest=json.loads((HERE/'compiled32-persistent-coordinator-v2-source-construction.json').read_bytes())
        source=(HERE/'run_compiled_startup32_v2.py').read_text()
        for old,new in reversed(manifest['other_replacements']):source=source.replace(new,old)
        source=source.replace(manifest['added_lease_validation']+manifest['validation_anchor'],manifest['validation_anchor'])
        source=source.replace(manifest['new_class'],manifest['original_class'])
        self.assertEqual(source,(HERE/'run_compiled_startup32_v1.py').read_text())
        self.assertEqual((HERE/'control_compiled_startup32_v2.py').read_text().replace(
            'run_compiled_startup32_v2.py','run_compiled_startup32_v1.py'),
            (HERE/'control_compiled_startup32_v1.py').read_text())
        root=runtime.G/'logs/managed-learning-20261015/run-26'
        jp=root/'coordinator-v2-contract-fixture-not-launched/job.json';driver=str(HERE/'run_compiled_startup32_v2.py')
        config=dict(unit='robotron-compiled-startup32-integration-coordinator-fixture.service',
            output=str(directory/'uncreated'),argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python',
                '-Xgil=0','-I','-B',driver,'--execute','--job',str(jp),'--job-sha256','a'*64,'--source-sha256','b'*64],
            properties=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=900',
                'TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
            pins=[dict(path=str(jp),sha256='a'*64),dict(path=driver,sha256='b'*64)],observation_s=960)
        path=directory/'synthetic-config.json';path.write_text(json.dumps(config))
        self.assertEqual(control.checked_config(path),config)
        config['argv'][4]=str(HERE/'run_compiled_startup32_v1.py');path.write_text(json.dumps(config))
        with self.assertRaises(ValueError):control.checked_config(path)
        self.assertNotIn('torch',sys.modules);self.assertEqual(control._LAUNCHES,{})


if __name__=='__main__':unittest.main(verbosity=2)
