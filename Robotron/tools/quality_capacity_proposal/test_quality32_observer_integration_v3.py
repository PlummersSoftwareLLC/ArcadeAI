"""Real observer context -> real review CLI -> synthetic immutable protection.

Full original journals, acquisition, archives, source and raw API joins run.
Native processes, CPU review scheduling, external OS state and clock are mocked.
No model is loaded or actual game, GPU or policy launched/published.
"""
import copy
import io
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import Mock,patch

import quality32_runtime_guard_v3 as observer
import test_quality32_runtime_guard_v1 as gates
import test_closed_quality32_full_path_v4 as fixtures
import protect_quality32_winner_v2 as protect

gates.observer=observer
ObserverTests=gates.ObserverTests
ReviewControllerTests=gates.ReviewControllerTests


class FullObserverIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.FullPathTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.reader=self.fixture.reader;self.root=self.fixture.root
        self.actual_checked=self.reader.checked_module
        self.launches=[];self.observations=[];self.holds=Mock();self.cleanup=Mock()
        self.audit_calls=0

    def build(self,gain=True,mutation=None,CPU_exit_after_report=None):
        f=self.fixture
        original_job,entry,main=f.build(candidate_gain=gain,mutation=mutation)
        context=self.reader.read_pin(self.reader.pin(original_job['closed_context_path']))
        template=self.reader.read_pin(original_job['binding'])
        parameters=dict(directory=str(f.directory))
        bindingdir=self.root/'observer-bindings';bindingdir.mkdir()
        nativeconfig=self.reader.read_pin(context['native_controller_config'])
        job=dict(campaign_parameters=parameters,review_output=original_job['output'],
            review_execution=str(self.root/'observer-original-review-execution'),
            review_unit='robotron-quality32-observer-integration-review.service',
            reviewer_source=self.reader.pin(observer.REVIEWER),
            review_controller_source=self.reader.pin(observer.HERE/'control_quality32_review_v1.py'),
            main_guard_source=original_job['main_guard_source'],lease_path=original_job['lease_path'],
            lease_identity=original_job['lease_identity'])
        base=self.actual_checked('_integration_base_'+str(time.time_ns()),self.reader.pin(observer.BASE))
        inputs=dict(job=job,template=template,reader=self.reader,main=main,baseline={},baseline_wire=b'{}',window=Mock(),
            config_pin=context['native_controller_config'],review_job=dict(
                closed_context_path=str(bindingdir/'closed-context.json'),runtime_paths=dict(
                    pilot_closure=context['native_closure']['path'])))
        self.guard=observer.guard_class(base)(nativeconfig,inputs)
        for key,value in dict(binding_entry=original_job['binding'],owner_entry=context['native_owner'],
            main_entry=context['main_binding'],main_manifest=context['main_observations'],
            birth_entry=context['leg_evaluator_births'],actor_entry=context['leg_actor_identities'],finished=True).items():
            setattr(self.guard,key,value)
        self.job=job;self.main=main;self.CPU_exit_after_report=CPU_exit_after_report
        self.native_result=dict(lifecycle_complete=True,unit_released=True,original_exit=0)

    def fake_launch(self,path):
        self.assertFalse(self.launches,'Exactly one original review launch')
        self.launches.append(str(path))
        config=self.reader.read_pin(self.reader.pin(path))
        Path(config['output']).mkdir()

    def fake_observe(self,path):
        self.assertEqual(self.launches,[str(path)]);self.assertFalse(self.observations)
        self.observations.append(str(path));f=self.fixture
        config=self.reader.read_pin(self.reader.pin(path))
        argv=config['argv'];root_job_path=Path(argv[argv.index('--job')+1])
        reviewer=self.actual_checked('_integration_real_original_review_'+str(time.time_ns()),self.job['reviewer_source'])
        with patch.object(reviewer,'reader_module',return_value=self.reader),\
             patch.object(reviewer.time,'time',return_value=f.end_unix+5),\
             patch.object(reviewer.time,'monotonic',return_value=f.end_mono+5),\
             patch.object(reviewer.urllib.request,'urlopen',side_effect=lambda *a,**kw:
                io.BytesIO(json.dumps(f.api(f.end_unix+5,9999,self.main)).encode())):
            self.audit_calls+=1
            code=reviewer.main(argv[4:])
        root_job=self.reader.read_pin(self.reader.pin(root_job_path))
        self.report=self.reader.read_pin(self.reader.pin(Path(root_job['output'])/'review.json'))
        self.assertEqual(code,0 if self.report['valid'] else 2)
        exitcode=code if self.CPU_exit_after_report is None else self.CPU_exit_after_report
        owner=dict(f.owner,unit=config['unit'],timer=config['unit'].removesuffix('.service')+'.timer',
            pid=9_000_020,invocation_id='e'*32,timer_invocation_id='f'*32,cgroup='/synthetic-observer-review')
        closure_entry=f.closure(owner,config,'observer-original-review-closure',f.end_mono+1,f.end_mono+2)
        closure=self.reader.read_pin(closure_entry);record=closure['full_original_archives'][0]
        fields=dict(row.split('=',1) for row in self.reader.read_pin(record['stdout'],as_json=False).decode().splitlines() if '=' in row)
        fields.update(RuntimeMaxUSec='3min',MemoryMax=str(4<<30),CPUQuotaPerSecUSec='2s',
            ExecMainStatus=str(exitcode),Result='success' if exitcode==0 else 'exit-code')
        record['stdout']=f.put(record['stdout']['path'],(''.join(key+'='+value+'\n' for key,value in fields.items())).encode())
        closure['original_exit']=exitcode
        f.put(Path(config['output'])/'root-original-result-and-owned-release.json',closure)
        f.put(Path(config['output'])/'root-original-identity.json',owner)
        return closure

    def checked(self,name,entry):
        module=self.actual_checked(name,entry)
        if entry['sha256']==observer.REVIEW_CONTROL_SHA:
            module.launch=self.fake_launch;module.observe=self.fake_observe
        if entry==self.job['main_guard_source']:module.owner_and_files=self.holds
        if entry['sha256']==fixtures.review.DEPENDENCIES['runtime'][1]:module.verify_cleanup=self.cleanup
        return module

    def execute(self,**kwargs):
        self.build(**kwargs)
        Path(self.guard.config['output']).mkdir()
        with patch.object(self.reader,'checked_module',side_effect=self.checked):
            result=self.guard.close_and_review(self.native_result)
        self.assertEqual(self.audit_calls,1);self.assertEqual(len(self.launches),1);self.assertEqual(len(self.observations),1)
        self.assertNotIn('torch',sys.modules)
        self.controller_result=json.loads((Path(self.guard.config['output'])/'root-controller-result.json').read_bytes())
        return result

    def protection_job(self):
        value=self.controller_result
        destination=self.root/'protected-observer-integration';destination.mkdir(mode=0o700)
        job=dict(schema='robotron-quality32-winner-protection-job-v1',label='synthetic-observer-winner',
            destination=str(destination),reviewer_source=self.job['reviewer_source'],
            **{key:value[key] for key in ('review_job','review_report','review_owner','review_closure','review_controller_config')})
        entry=self.fixture.put(self.root/'observer-protection-job.json',job)
        return job,entry

    def test_observer_closed_context_real_CLI_and_immutable_winner_without_scientific_rerun(self):
        result=self.execute()
        self.assertTrue(result['valid'],result.get('error'));self.assertTrue(result['quality_qualified'])
        self.assertTrue(self.controller_result['valid'])
        self.assertEqual(sum(leg['cohort']['original_games']['rom_game_over_evidence']['verified_games'] for leg in result['legs']),200)
        job,entry=self.protection_job();forbidden=Mock(side_effect=AssertionError('Scientific audit must not rerun'))
        def checked(name,source):
            module=self.actual_checked(name,source)
            if source['sha256']==protect.REVIEWER_SHA:module.review=forbidden
            return module
        with patch.object(self.reader,'checked_module',side_effect=checked):
            protected=protect.publish(job,entry,self.reader)
        forbidden.assert_not_called();self.assertFalse(protected['managed_incumbent_updated'])
        self.assertEqual(protect.digest(Path(protected['protected_checkpoint'])),self.fixture.candidate['sha256'])
        self.assertEqual(self.reader.pin(self.fixture.reference['path']),self.fixture.reference)
        with self.assertRaisesRegex(ValueError,'one review attempt'):self.guard.close_and_review(self.native_result)
        self.assertEqual(len(self.launches),1)

    def test_valid_not_improved_original_review_cannot_publish_or_retry(self):
        result=self.execute(gain=False)
        self.assertTrue(result['valid']);self.assertFalse(result['quality_qualified'])
        self.assertEqual(result['decision']['outcome'],'not_improved')
        job,entry=self.protection_job()
        with self.assertRaisesRegex(ValueError,'qualified original independent review'):
            protect.publish(job,entry,self.reader)
        self.assertEqual(list(Path(job['destination']).iterdir()),[])
        self.assertEqual(self.audit_calls,1)

    def test_invalid_raw_API_original_review_exit2_preserved_without_retry(self):
        result=self.execute(mutation='raw_projection')
        self.assertFalse(result['valid']);self.assertEqual(result['original_CPU_review_exit'],2)
        self.assertEqual(self.controller_result['original_review_exit'],2)
        self.assertFalse(self.controller_result['valid']);self.assertFalse(self.controller_result['quality_qualified'])
        self.assertEqual(self.audit_calls,1)

    def test_nonzero_original_CPU_exit_after_valid_report_cannot_be_accepted(self):
        result=self.execute(CPU_exit_after_report=1)
        self.assertTrue(self.report['valid'],'Retain the actual valid report, but its owner failed')
        self.assertFalse(result['valid']);self.assertFalse(result['quality_qualified'])
        self.assertTrue(self.controller_result['original_report_valid'])
        self.assertEqual(self.controller_result['original_review_exit'],1)
        self.assertFalse(self.controller_result['valid'])
        job,entry=self.protection_job()
        with self.assertRaises(ValueError):protect.publish(job,entry,self.reader)
        self.assertEqual(list(Path(job['destination']).iterdir()),[])


if __name__=='__main__':
    unittest.main()
