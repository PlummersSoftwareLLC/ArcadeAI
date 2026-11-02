"""Actual bound64 drain/controller/certificate and pre-MAME constructor guards."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
N=Path(__file__).resolve().parent
F=N/'future-capacity64-shared-slot-domain-UNSELECTED-original01'
R=F/'runtime-family-original03'
E=N/'evaluator-count-active600-counterbalanced-engineering-original01'


def load(name,path,digest=None):
    if digest:assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m


h=load('_complete64_test_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
       '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
manifest_pin=h.pin(R/'complete-source-family-INCOMPLETE.json')
assert manifest_pin['sha256']=='b5ca3e1d050daffed5c0166eed998793c6805298d24e8b9217644c7db90ef090'
manifest=json.loads(h.checked(manifest_pin).read_bytes())
codec=load('wire_codec_v2',F/'wire_codec_v2.py')
startup=load('startup_handoff_v2',F/'startup_handoff_v2.py')
boot=load('boot_readiness_v3',F/'boot_readiness_v3.py')
ledger=load('tail_ledger_v1',F/'tail_ledger_v1.py')
bridge=load('_complete64_actual_bridge',F/'full_startup_proxy_quota64_v1.py')
journal=load('_complete64_actual_journal',G/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/game_journal.py',
             '96864c78df67f46bc58b1c4af4ce1bceb3791a8842fdcf02871385a1013d1e0f')
measurement=load('_complete64_actual_measurement',G/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/managed_measurement.py',
                 '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6')
FAMILIES=[]
for family in manifest['families']:
    modules={k:load('_complete64_'+family['role']+'_'+k,h.checked(pin),pin['sha256'])for k,pin in family['sources'].items()}
    fixture=load('_complete64_'+family['role']+'_fixture',h.checked(family['fixture']))
    modules.update(startup=startup,journal=journal,measurement=measurement)
    Fixture=fixture.fixture_type(dict(modules,audit=modules['games']))
    FAMILIES.append((family,modules,Fixture))
CONSTRUCTION=[]
COLD_IMPORTS=[]


class FakeListener:
    instances=[]
    def __init__(self,*args,**kwargs):self.address=None;self.closed=False;type(self).instances.append(self)
    def setsockopt(self,*args):pass
    def bind(self,address):self.address=address
    def listen(self,*args):pass
    def settimeout(self,*args):pass
    def close(self):self.closed=True


class CompleteFamilyGuards(unittest.TestCase):
    def fixture(self,Factory):
        f=Factory();self.addCleanup(f.close);return f

    def test_01_actual32_and64_controller_view_drain_and_registered_certificates(self):
        for family,modules,Factory in FAMILIES:
            with self.subTest(role=family['role']):
                f=self.fixture(Factory);count=family['actor_count']
                self.assertEqual(len(f.gate.subjects),count);self.assertEqual(len(f.gate.registrations),count)
                self.assertEqual(set(f.gate.registrations),set(range(4096,4096+count)))
                self.assertEqual(type(f.controller).__name__,'FixedSlotManagedMeasurement')
                self.assertEqual(type(f.journal).__name__,'FixedSlotCohortView')
                self.assertIsNone(f.gate.try_issue())

    def test_02_all64_terminal_life_ROM_and_raw_selection_joins_for_each_shape(self):
        for family,modules,Factory in FAMILIES:
            with self.subTest(role=family['role']):
                f=self.fixture(Factory);f.complete_all();permit=f.gate.try_issue();self.assertIsNotNone(permit)
                body=json.loads(permit.payload);self.assertEqual(body['count'],64)
                receipts=[f.authorize(permit,slot)for slot in modules['drain'].SLOTS]
                self.assertEqual(len(receipts),family['actor_count'])
                self.assertEqual(permit.used_slots,set(modules['drain'].SLOTS))
                reviewed=modules['games'].review(**f.closed_payloads())
                self.assertEqual(reviewed['statistics']['count'],64)
                n=family['actor_count'];self.assertEqual(reviewed['statistics']['score_sum'],n*(n-1)//2*100*family['games_per_slot'])
                self.assertEqual(reviewed['slot_admitted_counts'],{slot:family['games_per_slot']for slot in modules['drain'].SLOTS})
                self.assertEqual(len(reviewed['terminal_links']),64);self.assertEqual(len(reviewed['rom_links']),64)
                self.assertEqual(sum(r['verified_lives']for r in reviewed['life_links']),64)
                self.assertFalse(reviewed['quality_qualified'])

    def test_03_a_fast_slot_cannot_replace_missing_selected_tails(self):
        for family,modules,Factory in FAMILIES:
            f=self.fixture(Factory)
            for score in (100,99999999,99999999):f.complete_game(4096,score=score)
            f.controller.tick();self.assertIsNone(f.gate.try_issue())
            self.assertFalse(f.controller.status()['complete'])

    def test_04_missing_foreign_duplicate_and_identity_subjects_refused(self):
        for family,modules,Factory in FAMILIES:
            f=self.fixture(Factory)
            for mutation in ('missing','foreign','duplicate_slot','duplicate_session','duplicate_connection'):
                subjects=copy.deepcopy(f.subjects)
                if mutation=='missing':subjects.pop()
                elif mutation=='foreign':subjects[-1]['slot']=4096+family['actor_count']
                elif mutation=='duplicate_slot':subjects[-1]['slot']=subjects[0]['slot']
                elif mutation=='duplicate_session':subjects[-1]['session']=subjects[0]['session']
                else:subjects[-1]['connection']=subjects[0]['connection']
                with self.subTest(role=family['role'],mutation=mutation),self.assertRaises(ValueError):
                    modules['drain'].CohortDrain(f.journal,f.controller,subjects=subjects,
                        policy_reader=lambda:f.policy,admission_reader=lambda:f.window,
                        wall_ns=lambda:f.wall,monotonic_ns=lambda:f.mono)

    def test_05_missing_registration_abandonment_and_replay_refused(self):
        for family,modules,Factory in FAMILIES:
            f=self.fixture(Factory);f.complete_all();f.gate.registrations.pop(4096)
            with self.assertRaises(ValueError):f.gate.try_issue()
            f=self.fixture(Factory);f.journal.disconnect(4096-4000,lambda:f.context);f.controller.tick()
            with self.assertRaises(ValueError):f.gate.try_issue()
            f=self.fixture(Factory);f.complete_all();permit=f.gate.try_issue();f.authorize(permit,4096)
            with self.assertRaises(ValueError):f.authorize(permit,4096)

    def test_06_actual_pre_MAME_actor_loop_restores_and_constructs_every_subject(self):
        for family,modules,Factory in FAMILIES:
            runtime=modules['runtime'];n=family['actor_count']
            historical=E/('01-A1-control'if n==32 else'02-B1-capacity64')/'job.json'
            job=copy.deepcopy(json.loads(historical.read_text()))
            seed=load('_complete64_seed_'+str(n),h.checked(job['seed_runtime']),job['seed_runtime']['sha256'])
            with tempfile.TemporaryDirectory()as tmp:
                out=Path(tmp);(out/'actors').mkdir();actors={};streams=[];errors=[];FakeListener.instances=[]
                try:
                    with patch.object(runtime.socket,'socket',FakeListener), \
                         patch.object(runtime.threading.Thread,'start',side_effect=AssertionError('worker must not start'))as thread, \
                         patch.object(runtime.subprocess,'Popen',side_effect=AssertionError('MAME must not start'))as child, \
                         patch.object(runtime.PrivateLease,'acquire',side_effect=AssertionError('GPU lease forbidden'))as lease:
                        runtime.prepare_actor_resources(job=job,output=out,server=SimpleNamespace(),h=h,seed=seed,
                            bridge=bridge,BoundedWitness=ledger.BoundedWitness,bridge_stop=threading.Event(),
                            policy_reader=lambda:{},admission=lambda:None,parse_frame_data=lambda _:None,
                            drain_reader=lambda:None,actors=actors,streams=streams,errors=errors)
                        thread.assert_not_called();child.assert_not_called();lease.assert_not_called()
                    self.assertEqual(set(actors),set(range(4096,4096+n)));self.assertEqual(len(streams),n)
                    self.assertEqual(errors,[])
                    for slot,row in actors.items():
                        self.assertIsNone(row['child']);self.assertFalse(row['worker_started'])
                        restored=json.loads(h.checked(row['boot_restore']).read_bytes())
                        self.assertTrue(restored['normal_seed_and_helper_unchanged'])
                        self.assertEqual(row['proxy'].subject,dict(slot=slot,session=job['sessions'][str(slot)],connection=job['connections'][str(slot)]))
                        self.assertEqual(row['listener'].address,('127.0.0.1',20000+slot-4096))
                        self.assertTrue((row['private']/'boot.lua').is_file())
                    CONSTRUCTION.append(dict(role=family['role'],constructed=n,seed_restores=n,
                        real_proxy_and_witness_objects=True,network_listeners_stubbed=True,MAME_or_worker_or_GPU_started=False))
                finally:
                    for row in actors.values():row['listener'].close()
                    for stream in streams:stream.flush();os.fsync(stream.fileno());stream.close()
                self.assertTrue(all(sock.closed for sock in FakeListener.instances))

    def test_07_native_uses_the_exact_extracted_constructor_loop(self):
        for family,modules,Factory in FAMILIES:
            row=next(r for r in manifest['derivations']if r['role']==family['role']and r['component']=='runtime')
            tree=ast.parse(Path(family['sources']['runtime']['path']).read_text())
            fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='prepare_actor_resources')
            self.assertEqual(ast.dump(fn.body[0],include_attributes=False),row['constructor_loop_extraction']['extracted_loop_AST'])
            run=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='run')
            calls=[n for n in ast.walk(run)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='prepare_actor_resources']
            self.assertEqual(len(calls),1)
            self.assertFalse(any(isinstance(n,ast.Attribute)and n.attr in ('Popen','start')for n in ast.walk(fn)))

    def test_08_new_public_import_and_wire_auditor_bindings_are_exact(self):
        for family,modules,Factory in FAMILIES:
            runtime=modules['runtime']
            self.assertEqual(runtime.BRIDGE_COMPONENTS,F)
            self.assertEqual(runtime.COMPONENTS,Path(family['sources']['view']['path']).parent)
            self.assertEqual(runtime.DIAGNOSTIC_SHA,manifest['scope']['sha256'])
            modules['wire'].dependencies()
            self.assertEqual(Path(modules['wire'].codec.__file__),F/'wire_codec_v2.py')
            self.assertEqual(modules['wire'].games_audit.ACTOR_COUNT,family['actor_count'])
            self.assertEqual(modules['drain'].VIEW_SHA,family['sources']['view']['sha256'])
            self.assertEqual(modules['games'].COHORT_SELECTION,modules['drain'].COHORT_SELECTION)
        self.assertIs(bridge.codec,codec);self.assertIs(bridge.authority,startup);self.assertNotIn('torch',sys.modules)


    def test_09_actual_cold_native_imports_and_regression_in_free_threaded_runtime(self):
        checker=N/'check_actual_native_cold_imports_v3.py'
        for family,modules,Factory in FAMILIES:
            role=family['role'];case='01-A1-control' if role=='A32' else '02-B1-capacity64'
            job=N/'evaluator-count-active600-counterbalanced-engineering-original02'/case/'job.json'
            for old in (True,False):
                native=(F/'runtime-family-original01'/role/'run_evaluator_count_active600_v2.py') if old else Path(family['sources']['runtime']['path'])
                command=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python','-Xgil=0','-I','-B',str(checker),
                    '--native',str(native),'--job',str(job)]+(['--expect-old-missing-drain'] if old else [])
                process=subprocess.run(command,capture_output=True,text=True,timeout=35)
                self.assertEqual(process.returncode,0,(role,old,process.stdout[-1500:],process.stderr[-2000:]))
                report=json.loads(process.stdout.splitlines()[-1])
                self.assertFalse(report['cuda_initialized'])
                self.assertTrue(report['old_failure_reproduced'] if old else report['passed'])
                COLD_IMPORTS.append(report)
        self.assertNotIn('torch',sys.modules)

    def test_10_actual_native_observer_dependencies_bind_closed_coalescing_worker_component(self):
        component=json.loads(h.checked(manifest['observer_component_CPU']).read_bytes())
        self.assertEqual(component['actual_tool_terminal_exit'],0)
        self.assertTrue(component['live_control_coalesced_without_losing_raw'])
        self.assertEqual(component['original_raw_main_samples'],127)
        self.assertLessEqual(component['maximum_observation_gap_s'],.5)
        self.assertEqual(component['running_projection_publication_stats']['coalesced_busy_reader'],6)
        self.assertEqual(component['actual_protocol'],manifest['observer_sources']['protocol'])
        for family,modules,Factory in FAMILIES:
            runtime=modules['runtime']
            self.assertEqual(runtime.OBSERVER_DEPENDENCIES,{k:v['sha256']for k,v in manifest['observer_sources'].items()})
            case='01-A1-control' if family['role']=='A32' else '02-B1-capacity64'
            j=json.loads((N/'evaluator-count-active600-counterbalanced-engineering-original03'/case/'job.json').read_bytes())
            f=json.loads(h.checked(j['source_family_manifest']).read_bytes())
            protocol=json.loads(h.checked(j['main_health_protocol']).read_bytes())
            j['runtime']=family['sources']['runtime'];f['runtime']=j['runtime'];f['main_observer']=manifest['observer_sources']
            self.assertIsNone(runtime.validate_main_health_contract(j,protocol,f))
            for key in ('protocol','worker','reviewer'):
                bad=copy.deepcopy(f);bad['main_observer'][key]['sha256']='a'*64
                with self.subTest(role=family['role'],wrong_source=key),self.assertRaises(ValueError):
                    runtime.validate_main_health_contract(j,protocol,bad)


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CompleteFamilyGuards))
    report=dict(schema='robotron-shared64-complete-family-constructor-drain-CPU-results-v1',source=h.pin(__file__),
        source_family=manifest_pin,tests_run=result.testsRun,passed=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors),
        actual_pre_MAME_constructions=CONSTRUCTION,actual_free_threaded_cold_imports=COLD_IMPORTS,actual_journal_view_controller_startup_drain_and_raw_terminal_paths_used=True,
        synthetic_ROM_policy_time_and_historical_seed_templates_only=True,actual64_live_MAME_startup_verified=False,
        original_failed_case_retried=False,native_launch_ready=False,quality_qualified=False,throughput_gain_verified=False)
    print(json.dumps(dict(report=h.put(R/'CPU-complete-family-guards-original01/actual-complete-family-CPU-results.json',report),
        tests_run=result.testsRun,passed=result.wasSuccessful())),flush=True)
    time.sleep(8);return 0 if result.wasSuccessful()else 1


if __name__=='__main__':raise SystemExit(main())
