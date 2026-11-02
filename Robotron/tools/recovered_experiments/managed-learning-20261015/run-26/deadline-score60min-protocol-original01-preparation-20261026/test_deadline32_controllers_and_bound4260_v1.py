"""New CPU source/configuration qualification only; never call launch/observe.

Mocked scope observations are labelled as such. No systemd command, MAME,
Torch, model body, native run or GPU operation occurs in these tests.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
Q=Path(__file__).resolve().parent
D=Q/'observer-bound4260-family-original01'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

controller=load('_deadline32_native_controller_CPU',Q/'control_deadline32_leg_v1.py')
observer=load('_deadline32_observer_controller_CPU',D/'control_main_health_deadline4260_v1.py')
worker=load('_deadline32_observer_worker_CPU',D/'run_main_health_deadline4260_v1.py')
manifest=json.loads((D/'source-derivation-direct-historical-v2.json').read_text())

class ControllersAndBounds(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory(dir=Q,prefix='cpu-controller-config-fixture-')
        self.addCleanup(temp.cleanup);root=Path(temp.name);job=root/'job.json';job.write_text('{}\n')
        runtime=Q/'run_deadline32_leg_v1.py'
        cfg=dict(unit='robotron-deadline32-score60min-r1-original01-20261026.service',output=str(root/'UNLAUNCHED'),
            argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',str(runtime),
                '--execute','--job',str(job),'--job-sha256',controller.pin(job)['sha256'],
                '--source-sha256',controller.pin(runtime)['sha256']],
            properties=['CPUQuota=1200%','MemoryMax=24G','MemorySwapMax=0','RuntimeMaxSec=4260',
                'TasksMax=512','TimeoutStopSec=30','KillMode=mixed','SendSIGKILL=no'],
            pins=[controller.pin(job),controller.pin(runtime)],observation_s=4320)
        path=root/'config.json'
        return cfg,path
    def check(self,cfg,path,module=controller):
        path.write_text(json.dumps(cfg));return module.checked_config(path)
    def test_all_four_exact_namespace_runtime_and_resources_validate(self):
        cfg,path=self.fixture()
        for leg in ('r1','c1','r2','c2'):
            cfg['unit']='robotron-deadline32-score60min-'+leg+'-original01-20261026.service'
            self.assertEqual(self.check(cfg,path),cfg)
    def test_foreign_namespace_path_bounds_and_missing_pin_rejected(self):
        original,path=self.fixture()
        for damage in ('namespace','runtime','watchdog','observation','cpu','sendkill','jobpin'):
            cfg=copy.deepcopy(original)
            if damage=='namespace':cfg['unit']='robotron-foreign-original01.service'
            elif damage=='runtime':cfg['argv'][4]='/tmp/foreign.py'
            elif damage=='watchdog':cfg['properties'][3]='RuntimeMaxSec=420'
            elif damage=='observation':cfg['observation_s']=4321
            elif damage=='cpu':cfg['properties'][0]='CPUQuota=1300%'
            elif damage=='sendkill':cfg['properties'][-1]='SendSIGKILL=yes'
            else:cfg['pins']=cfg['pins'][1:]
            with self.subTest(damage=damage),self.assertRaises(ValueError):self.check(cfg,path)
    def test_native_actual_owned_controller_lifecycle_unchanged(self):
        parent=Q.parent/'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025/evaluator-count-active600-counterbalanced-engineering-original06/future-startup-slot64-chain-correction-original01/control_cold_slot64_prefix_v1.py'
        def methods(path):
            tree=ast.parse(path.read_text());return {n.name:ast.dump(n,include_attributes=False)for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        old,new=methods(parent),methods(Q/'control_deadline32_leg_v1.py')
        self.assertEqual(old.keys(),new.keys())
        for name in old:
            if name!='checked_config':self.assertEqual(old[name],new[name],name)
    def test_observer_controller_exact4260_and4320_bounds(self):
        cfg,path=self.fixture();cfg.update(unit=cfg['unit'][:-8]+'-mainhealth.service',
            properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=4260',
                'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'])
        self.assertEqual(self.check(cfg,path,observer),cfg)
        for key,value in (('observation_s',480),('properties',cfg['properties'][:3]+['RuntimeMaxSec=420']+cfg['properties'][4:])):
            changed=dict(cfg,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(changed,path,observer)
    def test_observer_worker_actual_verify_self_with_explicitly_mocked_scope(self):
        unit='robotron-deadline32-score60min-r1-original01-20261026-mainhealth.service'
        fields=dict(Id=unit,MainPID=str(os.getpid()),InvocationID='f'*32,ActiveState='active',SubState='running',
            NRestarts='0',CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',
            TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no',RuntimeMaxUSec='1h 11min',ControlGroup='/mock/observer')
        job=dict(unit_runtime_s=4260,observer_unit=unit,parent={'cgroup':'/mock/native'})
        with patch.object(worker,'show',return_value=fields),patch.object(worker,'own_cgroup',return_value='/mock/observer'),patch.dict(os.environ,INVOCATION_ID='f'*32):
            self.assertEqual(worker.verify_self(job)['unit'],unit)
            fields['RuntimeMaxUSec']='7min'
            with self.assertRaises(ValueError):worker.verify_self(job)
    def test_every_observer_source_exact_parent_transformation_only(self):
        parents,selected=manifest['source_parents'],manifest['selected_sources']
        for pin in [*parents.values(),*selected.values()]:
            raw=Path(pin['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),pin['sha256'])
        def raw(which,key):return Path(which[key]['path']).read_text()
        expected=raw(parents,'controller').replace("'22260'","'4260'").replace('22320','4320').replace('22380','4320')
        self.assertEqual(raw(selected,'controller'),expected)
        expected=raw(parents,'client').replace(parents['controller']['sha256'],selected['controller']['sha256']).replace('22260','4260').replace('22320','4320')
        self.assertEqual(raw(selected,'client'),expected)
        self.assertEqual(raw(selected,'worker'),raw(parents,'worker').replace('in (180,22260)','in (4260,)').replace("{180:'3min',22260:'6h 11min'}","{4260:'1h 11min'}"))
        expected=raw(parents,'reviewer').replace('22260','4260').replace('22320','4320').replace("'6h 11min'","'1h 11min'")
        self.assertEqual(raw(selected,'reviewer'),expected)
        self.assertEqual(selected['protocol'],parents['protocol'])
    def test_family_bounds_have_separate_work_watchdog_and_observation(self):
        self.assertEqual(manifest['bounds'],dict(native_work_s=4200,native_watchdog_s=4260,observer_watchdog_s=4260,
            outer_observation_s=4320,observer_cpu_cores=2,observer_memory_bytes=4<<30,observer_tasks_max=128))
        self.assertFalse(manifest['launched']);self.assertFalse(manifest['old_sources_changed'])

if __name__=='__main__':unittest.main(verbosity=2)
