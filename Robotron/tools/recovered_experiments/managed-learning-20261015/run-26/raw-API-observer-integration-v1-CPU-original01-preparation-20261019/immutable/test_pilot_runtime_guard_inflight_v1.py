"""CPU-only pilot-controller checks with fake unit/process/signal APIs."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import Mock,patch

import control_original_pilot as control
import pilot_runtime_guard_inflight_v1 as guard
import review_original_pilot_inflight_v1 as reviewer

GAME=guard.GAME
QUALITY=GAME/'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018'


class GuardFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.reader=reviewer.protector()
        self.t=1000.;self.u=1_792_400_000.
        template=json.loads((QUALITY.parent/'post-confirmed-scoring-next8M-original01-root-preparation-20261018/job.json').read_bytes())
        self.main={key:copy.deepcopy(template[key]) for key in ('owner','actors','held_hashes','experiment')}
        self.api=json.loads(Path(template['baseline_API']['path']).read_bytes());self.api['ts']=self.u
        self.api['pipeline_snapshot_age_s']=0
        self.window=SimpleNamespace(owner_and_files=Mock(),healthy=lambda *args:None)
        plan=json.loads((QUALITY/'capacity32-confirmed1059-raw-API-v1-preparation-20261019/planned-pilot.json').read_bytes())
        plan['job']['directory']=str(self.root/'pilot');plan['unit']='robotron-synthetic-pilot.service';plan['timer']='robotron-synthetic-pilot.timer'
        directory=self.root/'bindings';execution=self.root/'execution';execution.mkdir()
        paths={name:str(directory/(name+'.json')) for name in ('pilot_owner','pilot_closure','main_binding',
            'main_observations','actor_identities','preceding_quality_decision','incumbent_before_pilot')}
        self.review_job=dict(closed_context_path=str(directory/'closed-context.json'),runtime_paths=paths,
            console_path=str(execution/'stdout.txt'))
        props=[value for value in plan['service_properties'] if value.split('=',1)[0] not in ('Type','RemainAfterExit','Restart')]
        self.config=dict(unit=plan['unit'],output=str(execution),argv=plan['command'],properties=props,pins=[],
            observation_s=6500,guard_source={},pilot_controller_job={})
        self.review=Mock(return_value=dict(valid=True,status='SYNTHETIC_REVIEW_ONLY'))
        self.g=guard.MainGuard(self.config,dict(reader=self.reader,reviewer=SimpleNamespace(review=self.review),
            review_job=self.review_job,main=self.main,window=self.window,baseline=copy.deepcopy(self.api),baseline_wire=json.dumps(self.api).encode(),
            plan=plan,job=dict(launch_pins=[]),preceding=dict(preceding_native_closure={},preceding_observer_closure={}),
            decision=dict(synthetic=True),state_raw=b'{"incumbent":{}}\n',selected=dict(source={},job={})))
        self.g.clock=lambda:self.u;self.g.monotonic=lambda:self.t
        self.latest=self.root/'models_dqn/robotron_dqn_latest.pt';self.latest.parent.mkdir();self.latest.write_bytes(b'synthetic checkpoint')
        self.addCleanup(patch.stopall)
        patch.object(guard,'GAME',self.root).start()
        patch.object(guard,'read_API_bytes',side_effect=lambda:json.dumps(self.get_API()).encode()).start()
        self.g.prepare_bindings()
        self.owner=dict(unit=plan['unit'],timer=plan['timer'],pid=9_000_000,starttime_ticks=123,
            invocation_id='a'*32,timer_invocation_id='b'*32,cgroup='/synthetic/'+plan['unit'],observed_live=True)

    def get_API(self):
        value=copy.deepcopy(self.api);value['ts']=self.u
        os.utime(self.latest,ns=(int((self.u-5)*1e9),int((self.u-5)*1e9)))
        return value

    def advance(self,seconds=10):
        self.t+=seconds;self.u+=seconds
        for key in ('frame_count','learner_frame_count','optimized_samples','training_steps'):self.api[key]+=100
        for bucket in ('total','since_epoch'):
            for key in ('attempts_started','outcomes_recorded','applied'):
                self.api['host_pipeline']['learning_exposure']['optimizer'][bucket][key]+=1
        self.api['host_pipeline']['learning_exposure']['replay']['accepted_learner_total']+=100


class MainGuardTests(GuardFixture):
    def test_original_command_resources_and_observation_budget_are_exact(self):
        self.g.validate_config(self.config)
        for key,value in (('unit','foreign.service'),('argv',['/bin/true']),('properties',[]),('observation_s',6000),('pins',[{}])):
            changed=copy.deepcopy(self.config);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.g.validate_config(changed)

    def test_samples_are_immutable_and_preserve_owner_sources_and_clock(self):
        self.advance();self.g.sample();self.assertEqual(len(self.g.samples),2)
        sample=self.reader.read_pin(self.g.samples[-1]);self.assertEqual(sample['main_owner'],self.main['owner'])
        self.assertTrue(sample['original192_actors_verified']);self.assertEqual(sample['autosave']['age_s'],5)
        self.assertEqual(self.g.samples[-1]['identity']['mode'],'0o444')

    def test_too_large_observation_gap_is_a_failure_not_skipped(self):
        self.advance(31)
        with self.assertRaisesRegex(ValueError,'gap'):self.g.sample()
        self.assertEqual(len(self.g.samples),1)

    def test_source_epoch_or_work_clock_regression_is_rejected(self):
        original=copy.deepcopy(self.api)
        for change in ('source','epoch','counter','outcome'):
            self.api=copy.deepcopy(original);self.advance()
            if change=='source':self.window.owner_and_files.side_effect=ValueError('held input changed')
            elif change=='epoch':self.api['host_pipeline']['learning_exposure']['optimizer']['epoch']+=1
            elif change=='counter':self.api['training_steps']=0
            else:self.api['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable']=1
            with self.subTest(change=change),self.assertRaises(ValueError):self.g.sample()
            self.window.owner_and_files.side_effect=None

    def test_stalled_applied_optimizer_or_accepted_data_is_not_healthy_training(self):
        original=copy.deepcopy(self.api)
        for name in ('applied','accepted','learner'):
            self.api=copy.deepcopy(original);self.g.progress={};self.g.last_sample=None
            self.g.exposure_previous=None;self.g.baseline=copy.deepcopy(self.api)
            initial_optimizer=copy.deepcopy(self.api['host_pipeline']['learning_exposure']['optimizer'])
            self.g.sample()
            count=(self.api['learner_frame_count'] if name=='learner' else
                self.api['host_pipeline']['learning_exposure']['optimizer']['total']['applied'] if name=='applied' else
                self.api['host_pipeline']['learning_exposure']['replay']['accepted_learner_total'])
            for index in range(3):
                self.advance(20)
                if name=='learner':self.api['learner_frame_count']=count
                elif name=='applied':
                    for bucket in ('total','since_epoch'):
                        counters=self.api['host_pipeline']['learning_exposure']['optimizer'][bucket]
                        extra=counters['applied']-initial_optimizer[bucket]['applied']
                        counters['applied']=initial_optimizer[bucket]['applied'];counters['amp_skipped']+=extra
                else:self.api['host_pipeline']['learning_exposure']['replay']['accepted_learner_total']=count
                if index<2:self.g.sample()
                else:
                    with self.subTest(name=name),self.assertRaisesRegex(ValueError,'progress for60'):self.g.sample()

    def test_capture_all32_actors_once_while_they_are_alive(self):
        path=Path(self.g.plan['job']['directory']);path.mkdir()
        actors={str(slot):8_000_000+slot for slot in guard.SLOTS}
        (path/'status.json').write_text(json.dumps(dict(actor_pids=actors)))
        with patch.object(guard,'process_start',return_value=456):self.g.capture_actors()
        value=self.reader.read_pin(self.g.actor_entry)
        self.assertEqual(set(value),set(actors));self.assertTrue(all(v['observed_live'] for v in value.values()))
        self.g.capture_actors()
        actors['4127']+=1;(path/'status.json').write_text(json.dumps(dict(actor_pids=actors)))
        with self.assertRaisesRegex(ValueError,'PIDs changed'):self.g.capture_actors()

    def test_missing_actor_birth_is_never_claimed_as_observed(self):
        path=Path(self.g.plan['job']['directory']);path.mkdir()
        actors={str(slot):8_000_000+slot for slot in guard.SLOTS}
        (path/'status.json').write_text(json.dumps(dict(actor_pids=actors)))
        with patch.object(guard,'process_start',return_value=None):self.g.capture_actors()
        self.g.finish_main_observation();self.assertEqual(self.reader.read_pin(self.g.actor_entry),{})

    def test_main_or_training_actor_cannot_be_recorded_as_pilot_owner(self):
        for pid in (self.main['owner']['pid'],self.main['actors'][0]['pid']):
            with self.subTest(pid=pid),self.assertRaises(ValueError):self.g.record_birth(dict(self.owner,pid=pid))
        with self.assertRaises(ValueError):self.g.record_birth(dict(self.owner,unit='foreign.service'))
        self.g.record_birth(self.owner)
        with self.assertRaises(ValueError):self.g.record_birth(self.owner)

    def test_guard_failure_is_retained_and_only_one_owned_pidfd_signal_is_sent(self):
        self.g.record_birth(self.owner);self.g.failed='main source changed'
        fields=dict(MainPID=str(self.owner['pid']),InvocationID=self.owner['invocation_id'],NRestarts='0')
        def sent(descriptor,signum):
            self.assertTrue((Path(self.config['output'])/'root-owned-guard-stop-intent.json').exists())
            self.assertEqual((descriptor,signum),(99,signal.SIGINT))
        with patch.object(guard,'unit_fields',return_value=fields),patch.object(guard,'process_start',return_value=123),\
             patch.object(guard.os,'pidfd_open',return_value=99) as opened,\
             patch.object(guard.signal,'pidfd_send_signal',side_effect=sent) as send,patch.object(guard.os,'close'):
            self.g.interrupt_original();self.g.interrupt_original()
        opened.assert_called_once_with(self.owner['pid']);send.assert_called_once()
        result=json.loads((Path(self.config['output'])/'root-owned-guard-stop-result.json').read_bytes())
        self.assertTrue(result['signal_sent']);self.assertFalse(result['main_touched'])

    def test_changed_invocation_or_process_birth_never_receives_a_signal(self):
        self.g.record_birth(self.owner);self.g.failed='synthetic failure'
        fields=dict(MainPID=str(self.owner['pid']),InvocationID='c'*32,NRestarts='0')
        with patch.object(guard,'unit_fields',return_value=fields),patch.object(guard,'process_start',return_value=123),\
             patch.object(guard.os,'pidfd_open') as opened,patch.object(guard.signal,'pidfd_send_signal') as send:
            self.g.interrupt_original()
        opened.assert_not_called();send.assert_not_called()

    def test_stop_before_scheduling_and_after_birth_are_scoped(self):
        self.g.requested_stop=signal.SIGINT
        with self.assertRaises(ValueError):self.g.before_scheduling()
        self.g.record_birth(self.owner)
        with patch.object(self.g,'interrupt_original') as stop:
            self.g.on_tick(dict(MainPID=str(self.owner['pid'])),self.owner)
        stop.assert_called_once();self.assertIn('stop requested',self.g.failed)

    def test_failed_guard_cannot_finish_with_a_passing_manifest(self):
        self.g.failed='observation gap';self.g.finish_main_observation()
        value=self.reader.read_pin(self.g.main_manifest)
        self.assertEqual(value['status'],'FAILED');self.assertIsNone(value['configuration_changed'])
        self.assertFalse(value['controller_changed_learning'])

    def test_original_context_and_independent_review_are_created_once_after_closure(self):
        self.g.record_birth(self.owner);self.advance();self.g.finish_main_observation()
        Path(self.review_job['runtime_paths']['pilot_closure']).write_text('{}\n')
        Path(self.review_job['runtime_paths']['pilot_closure']).chmod(0o444)
        result=dict(lifecycle_complete=True,unit_released=True,original_exit=0)
        report=self.g.close_and_review(result);self.assertTrue(report['valid']);self.review.assert_called_once()
        self.assertTrue(Path(self.review_job['closed_context_path']).exists())
        with self.assertRaises(FileExistsError):self.g.close_and_review(result)


class ControllerPrimitiveTests(unittest.TestCase):
    def test_ownership_release_and_archive_helpers_are_AST_identical(self):
        parent=GAME/'tools/quality_audit_control_gc_repair_proposal/control_audit_reviewed3.py'
        def functions(path):return {n.name:ast.dump(n) for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef)}
        old=functions(parent);new=functions(Path(control.__file__))
        for name in ('command','fields','show','timer_state','original_terminal','release_original','publish'):
            with self.subTest(name=name):self.assertEqual(old[name],new[name])

    def test_streaming_hash_retains_original_five_field_pin_ABI(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'input';path.write_bytes(b'synthetic data');pin=control.pin(path)
            self.assertEqual(pin['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(set(pin['identity']),{'device','inode','mode','uid','nlink'})

    def test_without_authenticated_guard_no_launch_can_start(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'config.json';path.write_text('{}')
            with patch.object(control,'_GUARD',None),patch.object(control,'show') as show,self.assertRaises(ValueError):
                control.launch(path)
            show.assert_not_called()


class ActualBlockedPreflightTests(unittest.TestCase):
    def test_missing_predecessor_evidence_prevents_all_queries_and_scheduling(self):
        with tempfile.TemporaryDirectory() as temp:
            reader=guard.reader_module();guard_pin=reader.pin(Path(guard.__file__))
            job_pin={'kind':'job'};selection_pin={'kind':'selection'};review_job_pin={'kind':'review-job'};ready_pin={'kind':'ready'}
            missing=Path(temp)/'missing-native-closure.json'
            config=dict(unit='unused.service',output=str(Path(temp)/'unused'),argv=[],properties=[],pins=[],
                observation_s=6500,guard_source=guard_pin,pilot_controller_job=job_pin)
            def read(entry,as_json=True):
                if entry==guard_pin:return Path(guard.__file__).read_bytes()
                if entry==job_pin:return dict(schema='robotron-original-capacity-pilot-control-job-v1',reviewer_selection=selection_pin)
                if entry==selection_pin:return dict(source={},job=review_job_pin)
                if entry==review_job_pin:return dict(readiness_amendment=ready_pin,runtime_paths={'preceding_native_closure':str(missing)})
                if entry==ready_pin:return dict(current_native_owner={})
                raise AssertionError(entry)
            with patch.object(reader,'read_pin',side_effect=read),patch.object(reader,'checked_module',return_value=SimpleNamespace()),\
                 patch.object(guard,'idle_GPU') as gpu,patch.object(guard,'unit_fields') as query,\
                 patch.object(guard.MainGuard,'prepare_bindings') as output,self.assertRaises(FileNotFoundError) as error:
                guard.load_and_preflight(config,reader)
            self.assertEqual(error.exception.filename,str(missing))
            gpu.assert_not_called();query.assert_not_called();output.assert_not_called()


class ScriptedControllerTests(GuardFixture):
    """Run original launch/observe/GC code with zero real subprocesses/signals."""
    def execute_scripted(self,*,native_exit=0,miss_birth=False,expire=False):
        execution=Path(self.config['output']);execution.rmdir() # launch alone creates its original output
        config_path=self.root/'controller-config.json';config_path.write_text(json.dumps(self.config));config_path.chmod(0o444)
        unit=self.config['unit'];timer=self.g.plan['timer'];pid=os.getpid()
        live=True;scheduled=False;service_exists=True;calls=[]
        def state(name):
            nonlocal live,scheduled,service_exists
            if not scheduled or (name==timer and not live) or (name==unit and not service_exists):
                return dict(Id=name,LoadState='not-found',MainPID='0')
            if name==timer:return dict(Id=timer,LoadState='loaded',InvocationID='b'*32,Unit=unit)
            is_live=live and not miss_birth
            return dict(Id=unit,LoadState='loaded',InvocationID='a'*32,NRestarts='0',MainPID=str(pid) if is_live else '0',
                ExecMainPID=str(pid),ExecMainCode='0' if is_live else '1',ExecMainStatus='0' if is_live else str(native_exit),
                ActiveState='active' if is_live or native_exit==0 else 'failed',
                SubState='running' if is_live else 'exited' if native_exit==0 else 'failed',
                Result='success' if is_live or native_exit==0 else 'exit-code',ControlGroup='/synthetic/'+unit)
        def run(argv,**kwargs):
            nonlocal live,scheduled,service_exists
            calls.append(argv);code=0;stdout=b'';stderr=b''
            if argv[0]=='systemd-run':
                self.assertFalse(scheduled);scheduled=True
                self.assertEqual(argv[-len(self.config['argv']):],self.config['argv'])
            elif argv[:3]==['systemctl','--user','show']:
                stdout=''.join(f'{key}={value}\n' for key,value in state(argv[3]).items()).encode()
            elif argv[:3]==['systemctl','--user','cat']:
                if argv[3]==timer and not live:code=1;stderr=b'Original timer no longer loaded\n'
                else:stdout=('['+('Timer' if argv[3]==timer else 'Service')+']\n'+('Unit='+unit+'\n' if argv[3]==timer else '')).encode()
            elif argv[:3]==['systemctl','--user','stop']:
                self.assertEqual(argv[3],unit);self.assertFalse(live);service_exists=False
            elif argv[0]=='journalctl':stdout=b'synthetic original invocation journal\n'
            else:raise AssertionError('Unexpected subprocess: '+repr(argv))
            if kwargs.get('text'):stdout=stdout.decode();stderr=stderr.decode()
            return SimpleNamespace(returncode=code,stdout=stdout,stderr=stderr)
        def sleep(seconds):
            nonlocal live
            self.advance(7000 if expire else 10)
            if not expire:live=False
        original_api=self.get_API
        def api():self.advance(.001);return original_api()
        status=Path(self.g.plan['job']['directory']);status.mkdir()
        actors={str(slot):8_000_000+slot for slot in guard.SLOTS}
        (status/'status.json').write_text(json.dumps(dict(actor_pids=actors)))
        actual_start=guard.process_start
        def proc(pid):return 456 if pid>=8_000_000 else actual_start(pid)
        fake_subprocess=SimpleNamespace(run=run,TimeoutExpired=control.subprocess.TimeoutExpired)
        clock=SimpleNamespace(time=time.time,monotonic=lambda:self.t,sleep=sleep)
        self.advance(1)
        with patch.object(control,'_GUARD',self.g),patch.object(control,'_LAUNCHES',{}),\
             patch.object(control,'subprocess',fake_subprocess),patch.object(control,'time',clock),\
             patch.object(guard,'process_start',side_effect=proc),patch.object(guard,'read_API_bytes',side_effect=lambda:json.dumps(api()).encode()),\
             patch.object(self.g,'interrupt_original',side_effect=AssertionError('No signal in lifecycle fixture')):
            control.launch(config_path);result=control.observe(config_path)
        return result,calls

    def test_original_success_archives_all_six_descriptors_then_releases_exact_owner(self):
        result,calls=self.execute_scripted()
        self.assertEqual(result['original_exit'],0,result.get('error'));self.assertTrue(result['lifecycle_complete'])
        self.assertTrue(result['original_archived_before_release']);self.assertTrue(result['unit_released'])
        self.assertEqual(len(result['full_original_archives']),6)
        self.assertEqual(result['full_original_archives'][4]['exit'],1) # Honest timer GC retained.
        self.assertFalse(result['all_six_original_archive_commands_succeeded'])
        self.assertTrue(all(row['confirmed_absent'] for row in result['owned_release']))
        self.assertTrue(self.reader.read_pin(self.g.main_manifest)['status']=='PASS')
        self.assertEqual(len(self.reader.read_pin(self.g.actor_entry)),32)
        self.assertEqual(sum(argv[0]=='systemd-run' for argv in calls),1)
        self.assertTrue(Path(self.g.review_job['runtime_paths']['pilot_closure']).exists())
        self.assertTrue(self.g.close_and_review(result)['valid']);self.review.assert_called_once()

    def test_original_nonzero_is_preserved_with_successful_owned_cleanup(self):
        result,calls=self.execute_scripted(native_exit=1)
        self.assertEqual(result['original_exit'],1);self.assertTrue(result['lifecycle_complete'])
        self.assertTrue(result['unit_released']);self.assertFalse(result['payload_retried'])
        self.assertEqual(sum(argv[0]=='systemd-run' for argv in calls),1)

    def test_missing_live_birth_is_not_retrospectively_adopted_or_retried(self):
        result,calls=self.execute_scripted(native_exit=1,miss_birth=True)
        self.assertIsNone(result['original']);self.assertFalse(result['lifecycle_complete'])
        self.assertIn('live identity missed',result['error'])
        self.assertFalse(any(argv[:3]==['systemctl','--user','stop'] for argv in calls))
        self.assertEqual(sum(argv[0]=='systemd-run' for argv in calls),1)

    def test_observation_deadline_does_not_claim_terminal_or_restart(self):
        result,calls=self.execute_scripted(expire=True)
        self.assertIsNone(result['original_exit']);self.assertFalse(result['lifecycle_complete'])
        self.assertIn('Observational deadline',result['error'])
        self.assertFalse(any(argv[:3]==['systemctl','--user','stop'] for argv in calls))
        self.assertEqual(sum(argv[0]=='systemd-run' for argv in calls),1)


if __name__=='__main__':unittest.main()
