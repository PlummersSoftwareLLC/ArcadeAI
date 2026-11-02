"""CPU-only checks of a SHA-pinned actual prepared cold64 job and controllers.

Explicit --execute-tests only. No GPU, MAME, lease, native output, unit or state
action. Real Lua5.4 runs the job's actual nested adapter with bounded ROM/IO mocks;
this does not certify real ROM startup. Observer scope fields are explicit mocks.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
MANIFEST=None

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m

class ActualColdJobController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads(MANIFEST.read_bytes())
        cls.chain=load('_cold_actual_chain',HERE/'startup_slot64_chain_v1.py')
        def read(pin):
            assert cls.chain.pin(pin['path'])==pin
            return json.loads(Path(pin['path']).read_bytes())
        cls.job=read(cls.manifest['native_job']);cls.cfg=read(cls.manifest['unqualified_controller_config'])
        cls.family=read(cls.manifest['source_family']);cls.protocol=read(cls.manifest['main_health_protocol'])
        cls.native=load('_cold_actual_native',Path(cls.manifest['runtime']['path']))
        cls.control=load('_cold_actual_control',Path(cls.manifest['native_controller']['path']))
        cls.worker=load('_cold_actual_worker',Path(cls.family['main_observer']['worker']['path']))
        cls.observer_control=load('_cold_actual_worker_control',Path(cls.family['main_observer']['controller']['path']))
        cls.lua_tools=load('_cold_actual_lua_tools',HERE/'test_startup_slot64_actual_lua.py')
        cls.lua=cls.lua_tools.Lua()

    def checked_config(self,module,value):
        with tempfile.TemporaryDirectory(prefix='cold64-controller-fixture-') as temp:
            path=Path(temp)/'config.json';path.write_text(json.dumps(value))
            return module.checked_config(path)

    def test_01_actual_job_native_and_full_health_join(self):
        self.assertEqual(self.native.validate_job(self.job),Path(self.job['output']))
        self.native.validate_main_health_contract(self.job,self.protocol,self.family)
        self.chain.validate_job(self.job)
        self.assertEqual(self.job['runtime'],self.manifest['runtime'])
        self.assertEqual(self.family['native_closure'],self.manifest['native_controller'])
        self.assertEqual(self.family['reviewer'],self.manifest['reviewer'])
        self.assertFalse(Path(self.job['output']).exists())
        self.assertFalse(Path(self.cfg['output']).exists())

    def test_02_wrong_role_work_bound_and_actual_source_fail(self):
        variants=[dict(schema='robotron-evaluator-count-active600-engineering-v1'),
            dict(diagnostic_role='timing_load_only'),dict(wall_limit_s=960),
            dict(engineering_implementation='B64'),dict(runtime={**self.job['runtime'],'sha256':'0'*64})]
        for change in variants:
            with self.subTest(change=change):
                value=copy.deepcopy(self.job);value.update(change)
                with self.assertRaises((AssertionError,ValueError)):self.native.validate_job(value)

    def test_03_actual_entry_nested_adapter_accepts_all64_fresh_subjects(self):
        chain=self.chain.validate_job(self.job)
        entry=Path(self.job['lua']['path']).read_text()
        needle='assert(loadfile('+json.dumps(chain['adapter']['path'])+'))().attach('
        self.assertEqual(entry.count(needle),1)
        code='return assert(loadfile('+json.dumps(chain['adapter']['path'])+'))()'
        for slot in self.job['actor_slots']:
            with self.subTest(slot=slot):
                source=self.lua_tools.fixture(code,slot=str(slot),session=self.job['sessions'][str(slot)],connection=self.job['connections'][str(slot)])
                status,error=self.lua.run(source)
                self.assertEqual(status,0,error)

    def test_04_outside_domain_and_original_failure_control(self):
        chain=self.chain.validate_job(self.job)
        for path,slot in [(chain['adapter']['path'],'4095'),(chain['adapter']['path'],'4160'),
            ('/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal/full_startup_wire_v2.lua','4159')]:
            with self.subTest(path=path,slot=slot):
                source=self.lua_tools.fixture('return assert(loadfile('+json.dumps(path)+'))()',slot=slot)
                status,error=self.lua.run(source)
                self.assertNotEqual(status,0);self.assertIn('startup integer outside contract',error)

    def test_05_exact_native_controller_positive_and_wrong_scope_rejections(self):
        self.assertEqual(self.checked_config(self.control,self.cfg),self.cfg)
        variants=[]
        v=copy.deepcopy(self.cfg);v['unit']='robotron-compiled-full-tail32-integration-foreign.service';variants.append(v)
        v=copy.deepcopy(self.cfg);v['argv'][4]='/tmp/old-native.py';variants.append(v)
        v=copy.deepcopy(self.cfg);v['observation_s']=22320;variants.append(v)
        v=copy.deepcopy(self.cfg);v['properties']=[x.replace('RuntimeMaxSec=420','RuntimeMaxSec=22260') for x in v['properties']];variants.append(v)
        v=copy.deepcopy(self.cfg);v['properties']=[x.replace('SendSIGKILL=no','SendSIGKILL=yes') for x in v['properties']];variants.append(v)
        for number,value in enumerate(variants):
            with self.subTest(number=number):
                with self.assertRaises(ValueError):self.checked_config(self.control,value)

    def test_06_observer_controller420_and_old_bound_rejection(self):
        value=dict(unit=self.cfg['unit'][:-8]+'-mainhealth.service',output='/tmp/explicit-never-launched-cold64-observer',
            argv=['/usr/bin/python3.12','-B','explicit-never-launched-fixture.py'],pins=[],
            properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=420','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],observation_s=480)
        self.assertEqual(self.checked_config(self.observer_control,value),value)
        for change in ('runtime','observation'):
            bad=copy.deepcopy(value)
            if change=='runtime':bad['properties']=[x.replace('RuntimeMaxSec=420','RuntimeMaxSec=22260') for x in bad['properties']]
            else:bad['observation_s']=22320
            with self.assertRaises(ValueError):self.checked_config(self.observer_control,bad)

    def test_07_actual_worker_scope_guard420_positive_and_strict_negative(self):
        unit=self.cfg['unit'][:-8]+'-mainhealth.service';cg='/cpu-only-mock/'+unit
        fields=dict(Id=unit,MainPID=str(os.getpid()),InvocationID='a'*32,ActiveState='active',SubState='running',NRestarts='0',
            CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no',RuntimeMaxUSec='7min',ControlGroup=cg)
        job=dict(observer_unit=unit,unit_runtime_s=420,parent=dict(cgroup='/cpu-only-different-parent'))
        with mock.patch.object(self.worker,'show',return_value=fields),mock.patch.object(self.worker,'own_cgroup',return_value=cg),mock.patch.object(self.worker,'birth',return_value=1),mock.patch.dict(os.environ,INVOCATION_ID='a'*32):
            self.assertEqual(self.worker.verify_self(job)['unit'],unit)
            with self.assertRaises(ValueError):self.worker.verify_self({**job,'unit_runtime_s':22260})
            fields['RuntimeMaxUSec']='6h 11min'
            with self.assertRaises(ValueError):self.worker.verify_self(job)

    def test_08_actual_fresh_identity_and_exact_family_dependencies(self):
        ids=[*self.job['sessions'].values(),*self.job['connections'].values()]
        self.assertEqual(len(ids),128);self.assertEqual(len(set(ids)),128)
        old=set()
        for pin in self.manifest['prior_jobs']:
            value=json.loads(Path(pin['path']).read_bytes())
            for key in ('sessions','connections'):old.update(value.get(key,{}).values())
        self.assertFalse(set(ids)&old)
        for key,pin in self.family['main_observer'].items():
            self.assertEqual(self.chain.pin(pin['path']),pin)
            self.assertEqual(self.native.OBSERVER_DEPENDENCIES[key],pin['sha256'])

    def test_09_native_lifecycle_AST_retained_exactly(self):
        parent=HERE.parents[1]/'future-capacity64-shared-slot-domain-UNSELECTED-original01/runtime-family-original03/B64/control_evaluator_count_active600_v2.py'
        before={x.name:ast.dump(x,include_attributes=False) for x in ast.parse(parent.read_text()).body if isinstance(x,ast.FunctionDef)}
        after={x.name:ast.dump(x,include_attributes=False) for x in ast.parse(Path(self.manifest['native_controller']['path']).read_text()).body if isinstance(x,ast.FunctionDef)}
        self.assertEqual(set(before),set(after))
        self.assertEqual([k for k in before if before[k]!=after[k]],['checked_config'])

def main():
    global MANIFEST
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute-tests',action='store_true');p.add_argument('--manifest',type=Path);p.add_argument('--manifest-sha256');p.add_argument('--output',type=Path);a=p.parse_args()
    if not a.execute_tests:print('PLAN_ONLY_NO_READS_OR_ACTIONS');return 0
    assert a.manifest is not None and a.output is not None and a.manifest_sha256
    assert hashlib.sha256(a.manifest.read_bytes()).hexdigest()==a.manifest_sha256
    MANIFEST=a.manifest;started=time.time()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ActualColdJobController))
    report=dict(schema='robotron-cold64-actual-job-entry-controller-CPU-tests-v1',passed=result.wasSuccessful(),tests_run=result.testsRun,
        errors=[str(x) for x in result.errors],failures=[str(x) for x in result.failures],manifest_path=str(a.manifest),manifest_sha256=a.manifest_sha256,
        started_unix_s=started,ended_unix_s=time.time(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        native_output_created=False,GPU_or_MAME_or_units_or_model_body=False,scope='Actualpreparedjob/entry/controllerjoins, actualLua5.4nestedadapterwithboundedROM/IOmocks, explicitmockworkerfields; notactualstartuporROMcertification.')
    with a.output.open('x') as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    print(json.dumps(dict(passed=report['passed'],tests_run=report['tests_run'],output=str(a.output))))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
