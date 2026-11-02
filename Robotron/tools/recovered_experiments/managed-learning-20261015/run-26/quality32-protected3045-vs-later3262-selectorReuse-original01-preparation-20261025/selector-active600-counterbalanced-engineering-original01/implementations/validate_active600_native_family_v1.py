"""Original CPU guards for the isolated reference600 quota64 native family.

Never calls an emulator, CUDA, a native controller launch or a live observer.
The guarded native run is exercised only with its required closeout absent,
which must reject before output creation or any private GPU acquisition.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-guards',action='store_true')
    parser.add_argument('--job',type=Path)
    parser.add_argument('--job-sha256')
    args=parser.parse_args()
    if not args.run_guards or args.job is None or not args.job_sha256:
        parser.error('Explicit original CPU job required')
    raw=args.job.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and 'torch'not in sys.modules
    def load(name,pin):
        path=Path(pin['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        name='_quota64_native_family_guard_'+name
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        spec.loader.exec_module(module)
        return module
    h=load('helper',job['helper'])
    for pin in job['inputs']:h.checked(pin)
    reader=load('reader',job['reader'])
    read=lambda pin:reader.read_pin(pin)
    native=read(job['native_job']);cfg=read(job['native_config'])
    family,protocol=read(native['source_family_manifest']),read(native['main_health_protocol'])
    runtime=load('runtime',native['runtime'])
    control=load('native_controller',job['native_controller'])
    worker_control=load('worker_controller',family['main_observer']['controller'])
    base_dir=Path(job['original_bridge']['path']).parent
    sys.path.insert(0,str(base_dir))
    bridge=load('bridge',native['quota64_source_pins']['bridge'])
    outdir=Path(native['output'])
    negative_cases=[]
    main_observations=[]
    def main_health(label):
        result=subprocess.run(['/usr/bin/python3.12','-I','-B',job['main_monitor']['path']],
                              capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        value=json.loads(result.stdout)
        assert value['client_count']==192 and value['held_inputs']==197 and value['autosave_age_s']<=360
        main_observations.append(h.put(Path(job['directory'])/(label+'-main-health.json'),value))
    main_health('before')

    class Guards(unittest.TestCase):
        def reject_native(self,name,mutate):
            value=copy.deepcopy(native);mutate(value)
            with self.assertRaises((ValueError,KeyError,TypeError)):
                runtime.validate_job(value)
            self.assertFalse(outdir.exists())
            negative_cases.append(name)

        def reject_config(self,module,original,name,mutate):
            value=copy.deepcopy(original);mutate(value)
            with tempfile.TemporaryDirectory(prefix='quota64-resource-guard-')as directory:
                path=Path(directory)/'config.json';path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):module.checked_config(path)
            negative_cases.append(name)

        def test_exact_reference_engineering_job_validates_without_side_effects(self):
            self.assertEqual(runtime.validate_job(copy.deepcopy(native)),outdir)
            self.assertEqual(native['checkpoint']['sha256'],runtime.REFERENCE_SHA)
            self.assertEqual(native['expected_policy_clocks'],runtime.REFERENCE_CLOCKS)
            self.assertEqual(native['diagnostic_precommit'],job['diagnostic_precommit'])
            self.assertFalse(outdir.exists())
            self.assertIsNone(protocol['prior_case'])

        def test_scientific_case_fields_and_old_candidate_are_rejected(self):
            for key in ('quality_leg','quality_pair_precommit','minimum_completed_games'):
                self.reject_native(key,lambda value,key=key:value.update({key:'forbidden'}))
            self.reject_native('old_b66_candidate',lambda value:value['checkpoint'].update(
                sha256='b66e751cc32004822272ccb0691f9e524ee94852c8e461299fac57c2985cdfc3'))
            self.reject_native('wrong_reference_clocks',lambda value:value['expected_policy_clocks'].update(training_steps=1))
            self.reject_native('wrong_engineering_precommit',lambda value:value['diagnostic_precommit'].update(sha256='0'*64))

        def test_fixed_quota_limits_are_typed_and_cannot_extend(self):
            for key,value in (('admission_s',5400),('whole_cohort_timeout_s',9000),
                              ('wall_limit_s',961),('admission_s',21540.0),('cpu_threads',True)):
                self.reject_native(key+repr(value),lambda obj,key=key,value=value:obj.update({key:value}))

        def test_all32_slots_ports_private_GPU_and_backend_are_required(self):
            self.reject_native('missing_slot',lambda value:value['actor_slots'].pop())
            self.reject_native('foreign_proxy_port',lambda value:value['proxy_ports'].update({'4096':9998}))
            self.reject_native('wrong_private_GPU',lambda value:value.update(gpu_uuid='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'))
            self.reject_native('wrong_backend',lambda value:value.update(backend='eager'))
            self.reject_native('duplicate_sessions',lambda value:value['sessions'].update({'4096':value['sessions']['4097']}))

        def test_count_selector_drain_and_bridge_sources_must_match(self):
            for key in ('view','drain','bridge'):
                self.reject_native('changed_'+key,lambda value,key=key:
                    value['quota64_source_pins'][key].update(sha256='0'*64))

        def test_native_controller_requires_exact_12CPU16G_bounds_and_runtime(self):
            self.assertEqual(control.checked_config(job['native_config']['path']),cfg)
            for old,new in (('CPUQuota=1200%','CPUQuota=200%'),('MemoryMax=16G','MemoryMax=4G'),
                            ('RuntimeMaxSec=22260','RuntimeMaxSec=9660'),('SendSIGKILL=no','SendSIGKILL=yes')):
                self.reject_config(control,cfg,old,lambda value,old=old,new=new:
                    value['properties'].__setitem__(value['properties'].index(old),new))
            self.reject_config(control,cfg,'wrong_native_runtime',lambda value:
                value['argv'].__setitem__(4,job['original_native_runtime']['path']))
            self.reject_config(control,cfg,'wrong_native_observation',lambda value:value.update(observation_s=9720))

        def test_observer_controller_requires_separate2CPU4G_and_selected_bounds(self):
            worker=dict(unit='robotron-quota64-engineering-worker-guard.service',
                output=str(Path(job['directory'])/'UNLAUNCHED-observer'),
                argv=['/usr/bin/python3.12','-I','-B','UNLAUNCHED'],pins=[],
                properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=22260',
                            'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],observation_s=22320)
            with tempfile.TemporaryDirectory(prefix='quota64-worker-guard-')as directory:
                path=Path(directory)/'valid.json';path.write_text(json.dumps(worker))
                self.assertEqual(worker_control.checked_config(path),worker)
            for old,new in (('CPUQuota=200%','CPUQuota=1200%'),('RuntimeMaxSec=22260','RuntimeMaxSec=9660'),
                            ('MemorySwapMax=0','MemorySwapMax=1G'),('SendSIGKILL=no','SendSIGKILL=yes')):
                self.reject_config(worker_control,worker,'worker_'+old,lambda value,old=old,new=new:
                    value['properties'].__setitem__(value['properties'].index(old),new))
            self.reject_config(worker_control,worker,'worker_observation',lambda value:value.update(observation_s=9720))

        def test_bridge_only_changes_the_underlying_startup_journal_binding(self):
            original=Path(job['original_bridge']['path']).read_text()
            changed=Path(native['quota64_source_pins']['bridge']['path']).read_text()
            self.assertEqual(changed.count('self.server.game_journal.journal'),1)
            restored=changed.replace('self.server.game_journal.journal','self.server.game_journal')
            self.assertEqual(ast.dump(ast.parse(original),include_attributes=False),
                             ast.dump(ast.parse(restored),include_attributes=False))
            self.assertTrue(hasattr(bridge,'StartupProxy'))

        def test_manifest_binds_the_guarded_transport_and_all_new_observer_components(self):
            self.assertEqual(family['runtime'],native['runtime'])
            self.assertEqual(protocol['health_job']['binding'],native['main_binding'])
            self.assertEqual(protocol['health_job']['sources']['transport']['sha256'],
                             '72edfb7c42106011e9551d59e1e43bba0ee8759b9e39402fd6b11dd4f5e7a0ad')
            self.assertEqual({key:value['sha256']for key,value in family['main_observer'].items()},runtime.OBSERVER_DEPENDENCIES)
            self.assertEqual({key:value['sha256']for key,value in protocol['health_job']['sources'].items()},runtime.HEALTH_DEPENDENCIES)
            self.assertEqual(family['quota64_components'],native['quota64_source_pins'])

        def test_native_rejects_missing_exact_job_guard_closeout_before_output_or_GPU(self):
            self.assertFalse(Path(native['prelaunch_family_guard_closeout']).exists())
            with self.assertRaises(FileNotFoundError):runtime.run(copy.deepcopy(native),job['native_job'],h)
            self.assertFalse(outdir.exists())
            self.assertNotIn('torch',sys.modules)

        def test_actual_engineering_preparer_fixture_protocol_is_native_contract(self):
            fixture=read(job['initializer_fixture_job'])
            self.assertEqual(runtime.validate_job(fixture),Path(fixture['output']))
            actual_protocol=read(fixture['main_health_protocol'])
            actual_family=read(fixture['source_family_manifest'])
            runtime.validate_main_health_contract(fixture,actual_protocol,actual_family)
            self.assertEqual(actual_protocol,protocol)
            self.assertFalse(Path(fixture['output']).exists())
            wrong=dict(actual_protocol,schema='robotron-native-quota64-dedicated-main-health-protocol-v1')
            with self.assertRaisesRegex(ValueError,'Exact prospective main-health'):
                runtime.validate_main_health_contract(fixture,wrong,actual_family)
            negative_cases.append('scientific-schema-cannot-replace-engineering-protocol')

        def test_default_native_and_controller_entrypoints_are_inert(self):
            for pin in (native['runtime'],job['native_controller']):
                result=subprocess.run(['/usr/bin/python3.12','-I','-B',pin['path']],
                                      capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('PLAN_ONLY',result.stdout)
            self.assertFalse(outdir.exists())
            self.assertNotIn('torch',sys.modules)

    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    main_health('after')
    for pin in job['inputs']:h.checked(pin)
    assert 'torch'not in sys.modules
    report=dict(schema='robotron-quota64-native-family-original-CPU-guards-v1',
        original_job=h.pin(args.job),native_job=job['native_job'],native_config=job['native_config'],
        native_runtime=native['runtime'],initializer_fixture_job=job['initializer_fixture_job'],successful=result.wasSuccessful(),tests_run=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),negative_cases=negative_cases,
        negative_cases_count=len(negative_cases),unittest_output=output.getvalue(),
        main_observations=main_observations,all_selected_inputs_unchanged=True,
        synthetic_resource_configs_only=True,actual_native_resources_or_load_verified=False,
        native_output_absent=not outdir.exists(),numerical_runtime_imported=False,
        private_GPU_acquired=False,production_changed=False,quality_qualified=False)
    reportpin=h.put(Path(job['report']),report)
    print(json.dumps(dict(successful=result.wasSuccessful(),tests_run=result.testsRun,
                         negative_cases=len(negative_cases),report=reportpin)),flush=True)
    return 0 if result.wasSuccessful()else 1


if __name__=='__main__':
    raise SystemExit(main())
