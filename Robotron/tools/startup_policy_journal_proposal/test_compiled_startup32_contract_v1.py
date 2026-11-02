"""New CPU-only contract for32-slot bindings and bounded original ownership.

No Torch, GPU, MAME, systemd launch, old test method or scientific reader runs.
Real temporary lease inodes exercise exclusivity and replacement refusal.
"""
from pathlib import Path
import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module


runtime=load('_compiled32_new_contract_runtime',HERE/'run_compiled_startup32_v1.py')
control=load('_compiled32_new_contract_control',HERE/'control_compiled_startup32_v1.py')


class CompiledStartup32Contract(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory(prefix='robotron-new-compiled32-contract-')
        self.addCleanup(temp.cleanup);return Path(temp.name)

    def job(self,directory):
        return dict(schema='robotron-compiled-startup32-original-v1',actor_slots=list(runtime.SLOTS),
            frames=1200,origin_port=19998,proxy_ports={str(k):v for k,v in runtime.PORTS.items()},
            device='cuda',backend='inductor',gpu_uuid=runtime.GPU,cpu_threads=2,admission_s=90,
            wall_limit_s=840,source_package=dict(sha256='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'),
            checkpoint=dict(sha256='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'),
            validated_CPU_prefix=dict(sha256='7d0cc6f960626fef0b9c0a6c40f68f9dcb55fa98d351c6b25111792156cdb647'),
            main_sources=dict(supervision=dict(sha256='1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'),
                window=dict(sha256='f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3'),
                reader=dict(sha256='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')),
            sessions={str(slot):format(slot,'032x')for slot in runtime.SLOTS},
            connections={str(slot):format(slot+10000,'032x')for slot in runtime.SLOTS},
            output=str(directory/'uncreated-output'))

    def test_all32_exact_compiled_backend_predecessor_and_distinct_subjects_required(self):
        d=self.fixture();job=self.job(d)
        self.assertEqual(runtime.validate_job(job),d/'uncreated-output')
        for key,value in [('actor_slots',list(runtime.SLOTS[:-1])),('device','cpu'),('backend','eager'),
                         ('gpu_uuid','GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'),
                         ('frames',1201),('frames',1200.),('admission_s',91),('wall_limit_s',900)]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                runtime.validate_job(dict(job,**{key:value}))
        for key in ('sessions','connections'):
            changed=copy.deepcopy(job);changed[key]['4097']=changed[key]['4096']
            with self.subTest(key=key),self.assertRaises(ValueError):runtime.validate_job(changed)
        changed=copy.deepcopy(job);changed['connections']['4096']=changed['sessions']['4096']
        with self.assertRaises(ValueError):runtime.validate_job(changed)
        for key in ('source_package','checkpoint','validated_CPU_prefix'):
            changed=copy.deepcopy(job);changed[key]['sha256']='0'*64
            with self.subTest(key=key),self.assertRaises(ValueError):runtime.validate_job(changed)
        changed=copy.deepcopy(job);changed['proxy_ports']['4097']=20000
        with self.assertRaises(ValueError):runtime.validate_job(changed)
        self.assertNotIn('torch',sys.modules)

    def test_each_original_actor_has_own_bridge_and_MAME_only_preload(self):
        d=self.fixture();job=self.job(d);job.update(mame=dict(path='/usr/games/mame'),rompath='/bound/roms')
        base=dict(ROBOTRON_CLIENT_SLOT='0',ROBOTRON_SOCKET_ADDRESS='127.0.0.1:9998',
            ROBOTRON_ENABLE_RRCHRIS_PATCH='1',LD_PRELOAD='/inherited.so',PYTHONPATH='/unsafe',CUDA_VISIBLE_DEVICES='main')
        ports=set()
        for slot in runtime.SLOTS:
            private=d/str(slot)
            env=runtime.actor_environment(base,private,slot,job['sessions'][str(slot)],
                                           job['connections'][str(slot)],'/bound/private-wait.so')
            port=20000+slot-4096;ports.add(port)
            self.assertEqual(env['ROBOTRON_SOCKET_ADDRESS'],'127.0.0.1:'+str(port))
            self.assertEqual(env['ROBOTRON_SOCKET_WAIT_PORT'],str(port))
            self.assertEqual(env['ROBOTRON_FULL_STARTUP_SLOT'],str(slot))
            self.assertEqual(env['ROBOTRON_FULL_STARTUP_SESSION'],job['sessions'][str(slot)])
            self.assertEqual(env['ROBOTRON_FULL_STARTUP_TRACE'],str(private/'producer.jsonl'))
            self.assertEqual(env['LD_PRELOAD'],'/bound/private-wait.so')
            self.assertEqual(env['CUDA_VISIBLE_DEVICES'],'')
            self.assertEqual(env['ROBOTRON_ENABLE_RRCHRIS_PATCH'],'0')
            self.assertNotIn('PYTHONPATH',env)
            argv=runtime.actor_command(job,private)
            self.assertEqual(argv[argv.index('-autoboot_script')+1],str(private/'boot.lua'))
            self.assertEqual(argv[argv.index('-cfg_directory')+1],str(private/'cfg'))
            self.assertIn('-noreadconfig',argv)
        self.assertEqual(ports,set(range(20000,20032)))
        self.assertEqual(base['LD_PRELOAD'],'/inherited.so')
        with self.assertRaises(ValueError):runtime.actor_environment(base,d,0,'1'*32,'2'*32,'/bound.so')

    def test_real_lease_exclusivity_and_replaced_inode_refuse_foreign_unlink(self):
        d=self.fixture();path=d/'private.lock';lease=runtime.PrivateLease(path)
        original=lease.acquire()
        try:
            self.assertEqual(original['inode'],path.stat().st_ino)
            other=runtime.PrivateLease(path)
            with self.assertRaises(FileExistsError):other.acquire()
            self.assertIsNone(other.fd)
            self.assertTrue(path.exists())
            lease.release();self.assertFalse(path.exists());self.assertIsNone(lease.fd)
        finally:
            if lease.fd is not None:os.close(lease.fd)
        lease=runtime.PrivateLease(path);lease.acquire();preserved=d/'original-preserved.lock'
        try:
            path.rename(preserved);path.write_text('foreign replacement\n')
            with self.assertRaises(ValueError):lease.release()
            self.assertEqual(path.read_text(),'foreign replacement\n')
            self.assertEqual(preserved.stat().st_ino,lease.identity[1])
        finally:
            if lease.fd is not None:os.close(lease.fd);lease.fd=None

    def test_bounded_controller_gate_keeps_entire_original_lifecycle_byte_identical(self):
        d=self.fixture();manifest=json.loads((HERE/'compiled32-controller-source-construction.json').read_bytes())
        parent=Path(manifest['parent']).read_text();source=(HERE/'control_compiled_startup32_v1.py').read_text()
        self.assertEqual(source.replace(manifest['new_gate'],manifest['original_gate']),parent)
        job=runtime.G/'logs/managed-learning-20261015/run-26/compiled32-contract-fixture-not-launched/job.json'
        driver=str(HERE/'run_compiled_startup32_v1.py')
        config=dict(unit='robotron-compiled-startup32-integration-contract-fixture.service',output=str(d/'uncreated'),
            argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',driver,
                '--execute','--job',str(job),'--job-sha256','a'*64,'--source-sha256','b'*64],
            properties=['CPUQuota=1200%','MemoryMax=16G','MemorySwapMax=0','RuntimeMaxSec=900',
                'TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
            pins=[dict(path=str(job),sha256='a'*64),dict(path=driver,sha256='b'*64)],observation_s=960)
        path=d/'synthetic-config.json'
        def check(value):
            path.write_text(json.dumps(value));return control.checked_config(path)
        self.assertEqual(check(config),config)
        for changed in (dict(config,unit='robotron-main.service'),dict(config,observation_s=961),
                        dict(config,pins=[]),dict(config,properties=config['properties'][:-1]+['SendSIGKILL=yes'])):
            with self.assertRaises(ValueError):check(changed)
        changed=copy.deepcopy(config);changed['argv'][4]='/unexpected/driver.py'
        with self.assertRaises(ValueError):check(changed)
        self.assertEqual(control._LAUNCHES,{})
        self.assertFalse((d/'uncreated').exists())


if __name__=='__main__':unittest.main(verbosity=2)
