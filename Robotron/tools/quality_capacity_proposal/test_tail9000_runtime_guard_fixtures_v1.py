"""Synthetic prospective observer tests; real /proc reads only for this CPU.

No real checkpoint load, game, GPU, native quality service or policy write.
Original bounded CPU controller execution is checked separately by its owner.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import quality32_runtime_guard_v5 as observer
import control_quality32_review_v1 as control
from tail9000_test_support_v1 import campaign


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name)
        self.base=load(observer.BASE,'_test_observer_base_'+str(time.time_ns()))
        self.reader=self.base.reader_module()
        self.directory=observer.GAME/'logs/managed-learning-20261015'/('synthetic-quality32-observer-'+str(time.time_ns()))
        self.addCleanup(lambda:shutil.rmtree(self.directory) if self.directory.exists() else None)
        self.reference=self.reader.pin(observer.GAME/'models_dqn/managed-incumbents/freshCE-LR25-1059M-confirmed-reset-20261018.pt')
        self.candidate=self.put(self.area/'candidate.pt',b'synthetic bytes; no model is loaded')
        self.template=dict(candidate=self.candidate,reference=self.reference,evidence={},expected_window={},main_holds={})
        self.parameters=dict(directory=str(self.directory),reference_label='future-reference',candidate_label='future-candidate',
            hypothesis='Synthetic observer lifecycle only; no quality or speed claim.',
            boot_assets=str(observer.GAME/'logs/managed-learning-20261015/sidecar-boot-assets-v1'))
        self.config=dict(unit='robotron-quality32-observer-synthetic.service',output=str(self.area/'execution'),
            argv=observer.campaign_command(dict(campaign_parameters=self.parameters),self.template),
            properties=['CPUQuota=1200%','MemoryMax=12G','MemorySwapMax=0','RuntimeMaxSec=36600',
                'TasksMax=512','TimeoutStopSec=120','KillMode=mixed','SendSIGKILL=no'],
            pins=[],observation_s=37200,guard_source={},pilot_controller_job={})
        self.bindingdir=self.area/'bindings'
        self.job=dict(campaign_parameters=self.parameters,launch_pins=[],binding_directory=str(self.bindingdir),
            review_output=str(self.area/'review'),review_execution=str(self.area/'review-execution'),
            review_unit='robotron-quality32-observer-synthetic-review.service',
            reviewer_source=self.reader.pin(observer.REVIEWER),
            review_controller_source=self.reader.pin(observer.HERE/'control_quality32_review_v1.py'),
            main_guard_source={},lease_path='/dev/shm/robotron-snapshot-smoke-gpu0.lock',lease_identity={})
        main=dict(owner=dict(pid=100),actors=[dict(pid=1000+i) for i in range(192)],
            experiment='synthetic',held_hashes={})
        cohorts=load(observer.HERE/'audit_quality32_evidence_v2.py','_observer_cohorts_'+str(time.time_ns()))
        self.inputs=dict(job=self.job,template=self.template,reader=self.reader,cohorts=cohorts,
            game=observer.HERE/'profile04/Robotron',main=main,baseline={},baseline_wire=b'{}',window=Mock(),
            config_pin=self.put(self.area/'config.json',self.config),
            review_job=dict(closed_context_path=str(self.bindingdir/'closed-context.json'),runtime_paths=dict(
                pilot_closure=str(self.area/'native-closure.json'),main_observations=str(self.bindingdir/'main-observations.json'))))
        self.guard=observer.guard_class(self.base)(self.config,self.inputs)
        self.guard.sample=Mock()
        self.guard.prepare_bindings()
        self.owner=dict(unit=self.config['unit'],timer=self.config['unit'].removesuffix('.service')+'.timer',
            pid=8_000_000,starttime_ticks=10,invocation_id='a'*32,timer_invocation_id='b'*32,
            cgroup='/synthetic/'+self.config['unit'],observed_live=True)
        self.guard.record_birth(self.owner)
        self.records=[]
        self.plan=None

    def put(self,path,value):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        raw=value if isinstance(value,bytes) else (json.dumps(value,allow_nan=False)+'\n').encode()
        if path.exists():path.chmod(0o644)
        path.write_bytes(raw);path.chmod(0o444)
        return self.reader.pin(path)

    def make_plan(self):
        job=campaign.Campaign(Path(self.reference['path']),Path(self.candidate['path']),self.directory,
            reference_label=self.parameters['reference_label'],candidate_label=self.parameters['candidate_label'],
            hypothesis=self.parameters['hypothesis'],actors=32,cohort_s=5400,timeout_s=9000,
            mame=Path('/usr/games/mame'),rompath=observer.GAME/'roms',boot_assets=Path(self.parameters['boot_assets']))
        with patch.object(campaign.sys,'executable',str(observer.GAME.parent/'.venv-gb300/bin/python')):
            self.plan=campaign.make_plan(job)
        self.put(self.directory/'plan.json',self.plan)
        return self.plan

    def active(self,index=1):
        if self.plan is None:self.make_plan()
        spec=self.plan['legs'][index-1]
        record=dict(index=index,role=spec['role'],pid=8_100_000+index,state='running',
            started_unix_s=time.time()+3600,**{key:spec[key] for key in
                ('receipt_path','console_log','evaluator_status_path')})
        if len(self.records)<index:self.records.append(record)
        else:self.records[index-1]=record
        self.write_status()
        pids={str(slot):8_200_000+index*100+offset for offset,slot in enumerate(observer.SLOTS)}
        self.put(spec['evaluator_status_path'],dict(phase='warming',actor_pids=pids,start_ts=None))
        return record,pids

    def write_status(self):
        self.put(self.directory/'status.json',dict(state='running',plan_sha256=observer.digest(self.directory/'plan.json'),
            legs=self.records))

    def fake_live(self,pid,parent,cgroup,command=None):
        return dict(pid=pid,parent_pid=parent,starttime_ticks=pid+1,cgroup=cgroup,observed_live=True,
            command=command or ['/usr/games/mame','synthetic'],affinity=[4,5],observed_unix_s=time.time())

    def capture(self):
        with patch.object(observer,'live_process',side_effect=self.fake_live):self.guard.capture_actors()

    def test_exact_command_resources_and_inherited_main_methods(self):
        self.guard.validate_config(self.config)
        for name in ('_sample','validate_exposure','sample','before_scheduling','on_tick',
                     'interrupt_original','finish_main_observation','preserve_incomplete_observation'):
            self.assertIs(getattr(type(self.guard),name),getattr(self.base.MainGuard,name))
        for flag,value in (('--actors','32'),('--cohort-s','5400'),('--timeout-s','9000'),('--port','9999')):
            self.assertEqual(self.config['argv'][self.config['argv'].index(flag)+1],value)
        self.assertNotIn('torch',sys.modules)

    def test_prospective_binding_and_all_four_live_birth_registries(self):
        self.make_plan()
        for index in range(1,5):
            record,pids=self.active(index);self.capture()
            self.assertEqual(self.guard.births[str(index)]['pid'],record['pid'])
            self.assertEqual({slot:value['pid'] for slot,value in self.guard.actor_births[str(index)].items()},pids)
            self.records[index-1].update(state='finished',returncode=0)
            self.write_status()
        self.capture()
        self.guard._finish()
        binding=self.reader.read_pin(self.guard.binding_entry)
        self.assertEqual(binding['campaign']['plan_sha256'],observer.digest(self.directory/'plan.json'))
        self.assertEqual(binding['candidate'],self.candidate)
        self.assertEqual(self.reader.read_pin(self.guard.birth_entry),self.guard.births)
        self.assertEqual(set(self.reader.read_pin(self.guard.actor_entry)),{'1','2','3','4'})
        self.assertEqual(self.reader.read_pin(self.guard.main_manifest)['status'],'PASS')

    def test_finished_display_uses_retained_socket_wait_pid_map(self):
        record,pids=self.active();self.capture()
        self.put(record['evaluator_status_path'],dict(phase='finished',socket_wait=dict(
            actors={slot:dict(pid=pid) for slot,pid in pids.items()})))
        self.records[0].update(state='finished',returncode=0);self.write_status();self.capture()
        self.assertEqual(len(self.guard.actor_births['1']),32)

    def test_duplicate_actor_pid_refused(self):
        record,pids=self.active();pids['4097']=pids['4096']
        self.put(record['evaluator_status_path'],dict(phase='warming',actor_pids=pids))
        with self.assertRaisesRegex(ValueError,'distinct'):self.capture()

    def test_changed_evaluator_pid_refused(self):
        self.active();self.capture();self.records[0]['pid']+=1;self.write_status()
        with self.assertRaisesRegex(ValueError,'evaluator PID changed'):self.capture()

    def test_changed_actor_pid_refused(self):
        record,pids=self.active();self.capture();pids['4096']+=999
        self.put(record['evaluator_status_path'],dict(phase='warming',actor_pids=pids))
        with self.assertRaisesRegex(ValueError,'actor PIDs changed'):self.capture()

    def test_finished_evaluator_cannot_be_adopted(self):
        self.active();self.records[0].update(state='finished',returncode=0);self.write_status()
        with self.assertRaisesRegex(ValueError,'birth missed'):self.capture()

    def test_completed_leg_missing_live_actors_refused(self):
        record,pids=self.active()
        self.put(record['evaluator_status_path'],dict(phase='warming',actor_pids={}))
        self.capture();self.records[0].update(state='finished',returncode=0);self.write_status()
        with self.assertRaisesRegex(ValueError,'actor births missed'):self.capture()

    def test_late_binding_rejected_and_original_binding_retained(self):
        record,pids=self.active()
        self.put(record['evaluator_status_path'],dict(phase='collecting',start_ts=time.time()-10,actor_pids=pids))
        with self.assertRaisesRegex(ValueError,'missed first admission'):self.capture()
        self.assertTrue((self.bindingdir/'campaign-binding.json').exists())
        self.assertFalse(self.guard.births)

    def test_substituted_checkpoint_or_label_or_gate_refused(self):
        self.make_plan()
        cases=[('checkpoint',lambda p:p['checkpoints']['candidate'].update(source='/tmp/substituted.pt')),
               ('label',lambda p:p['legs'][1]['job'].update(label='substituted')),
               ('gate',lambda p:p['precommit']['candidate_gate'].update(minimum_mean_ratio=1.0))]
        original=copy.deepcopy(self.plan)
        for name,mutate in cases:
            with self.subTest(name=name):
                value=copy.deepcopy(original);mutate(value);self.put(self.directory/'plan.json',value)
                with self.assertRaises(ValueError):self.guard.capture_plan()
                self.assertIsNone(self.guard.binding_entry)

    def test_wrong_parent_cgroup_command_propagates_live_birth_failure(self):
        self.active()
        with patch.object(observer,'live_process',side_effect=ValueError('foreign process')):
            with self.assertRaisesRegex(ValueError,'foreign process'):self.guard.capture_actors()
        self.assertFalse(self.guard.births)

    def test_missing_all_four_births_marks_final_witness_failed(self):
        self.guard._finish()
        manifest=self.reader.read_pin(self.guard.main_manifest)
        self.assertEqual(manifest['status'],'FAILED');self.assertIn('Missing original',manifest['error'])

    def test_failed_native_without_binding_has_no_review_attempt(self):
        self.guard._finish();Path(self.config['output']).mkdir()
        result=self.guard.close_and_review(dict(lifecycle_complete=True,unit_released=True,original_exit=1))
        self.assertFalse(result['valid'])
        saved=json.loads((Path(self.config['output'])/'root-controller-result.json').read_bytes())
        self.assertEqual(saved['original_native_exit'],1)
        self.assertEqual(saved['status'],'NO_PROSPECTIVE_BINDING_REVIEW_NOT_LAUNCHED')
        with self.assertRaisesRegex(ValueError,'one review attempt'):self.guard.close_and_review(
            dict(lifecycle_complete=True,unit_released=True,original_exit=1))

    def test_original_failed_interrupted_or_reordered_record_refused(self):
        self.active()
        for mutate in (lambda s:s['legs'][0].update(state='finished',returncode=1),
                       lambda s:s['legs'][0].update(role='candidate'),
                       lambda s:s['legs'].append(copy.deepcopy(s['legs'][0])),
                       lambda s:s.update(plan_sha256='0'*64)):
            status=json.loads((self.directory/'status.json').read_bytes());mutate(status)
            with self.assertRaises(ValueError):observer.validate_records(status,observer.digest(self.directory/'plan.json'))

    def test_resource_and_native_command_drift_refused(self):
        for change in (lambda c:c['argv'].extend(['--actors','16']),
                       lambda c:c['properties'].append('CPUQuota=1200%'),
                       lambda c:c['properties'].__setitem__(0,'CPUQuota=1600%'),
                       lambda c:c.update(observation_s=60000)):
            config=copy.deepcopy(self.config);change(config)
            guard=observer.guard_class(self.base)(config,self.inputs)
            with self.assertRaises(ValueError):guard.validate_config(config)

    def test_original_campaign_birth_cannot_replace_main(self):
        other=observer.guard_class(self.base)(self.config,self.inputs)
        owner=dict(self.owner,pid=self.inputs['main']['owner']['pid'])
        with self.assertRaises(ValueError):other.record_birth(owner)

    def test_real_own_process_identity_bracket_and_foreign_parent_command_rejection(self):
        pid=os.getpid();cgroup=Path('/proc/self/cgroup').read_text().strip().split('::',1)[1]
        command=[value.decode() for value in Path('/proc/self/cmdline').read_bytes().rstrip(b'\0').split(b'\0')]
        result=observer.live_process(pid,os.getppid(),cgroup,command)
        self.assertEqual(result['pid'],pid);self.assertTrue(result['observed_live'])
        for parent,group,argv in ((os.getppid()+1,cgroup,command),(os.getppid(),'/foreign',command),
                                  (os.getppid(),cgroup,['foreign'])):
            with self.assertRaises(ValueError):observer.live_process(pid,parent,group,argv)

    def test_missing_control_job_rejects_before_outputs_and_queries(self):
        config=dict(self.config,guard_source=self.reader.pin(Path(observer.__file__).resolve()),
            pilot_controller_job=dict(path=str(self.area/'missing-job.json')))
        entry=self.put(self.area/'missing-config.json',config)
        with patch.object(self.base,'unit_fields',side_effect=AssertionError('unit query must not occur')):
            with self.assertRaises((FileNotFoundError,KeyError)):observer.prepare(config,entry)
        self.assertFalse(Path(config['output']).exists())


class ReviewControllerTests(unittest.TestCase):
    def test_explicit_no_SIGKILL_required_and_cpu_resource_scope_preserved(self):
        with tempfile.TemporaryDirectory() as area:
            path=Path(area)/'config.json'
            config=dict(unit='robotron-quality32-review-synthetic.service',output=str(Path(area)/'output'),
                argv=['/usr/bin/python3.12','-I','-B','synthetic.py'],pins=[],observation_s=240,
                properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
                    'TasksMax=256','TimeoutStopSec=5','SendSIGKILL=no'])
            path.write_text(json.dumps(config));self.assertEqual(control.checked_config(path),config)
            for props in ([p for p in config['properties'] if not p.startswith('SendSIGKILL=')],
                          [p.replace('SendSIGKILL=no','SendSIGKILL=yes') for p in config['properties']],
                          config['properties']+['SendSIGKILL=no']):
                path.write_text(json.dumps(dict(config,properties=props)))
                with self.assertRaises(ValueError):control.checked_config(path)

    def test_original_lifecycle_functions_unchanged(self):
        original=observer.GAME/'logs/managed-learning-20261015/run-26/production-boundary-replay-integration-original01-root-preparation-20261018/control_private_replay_integration.py'
        before=ast.parse(original.read_text());after=ast.parse(Path(control.__file__).read_text())
        def functions(tree):
            return {node.name:ast.dump(node) for node in tree.body
                    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name!='checked_config'}
        self.assertEqual(functions(before),functions(after))


if __name__=='__main__':
    unittest.main()
