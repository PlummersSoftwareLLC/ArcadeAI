"""CPU-only failure-order, recovery, actual file and loopback TCP checks."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).parent


def module(name):
    spec = importlib.util.spec_from_file_location('_test_'+name,HERE/(name+'.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


C = module('handoff_controller_v1')
L = module('handoff_linux_v1')
R = module('handoff_recovery_v1')
P = module('handoff_poststop_v1')
S = module('handoff_socket_seal_v1')
V = module('handoff_live_runner_v1')
I = module('bank_shutdown_intent_v1')


STAGES = ['preflight','probe_registered_without_frames','first_supported_pause',
    'all192_acknowledged_and_advanced8_measured_frames','exact_accept_thread_held',
    'original_emulator_fleet_frozen','input_ownership_and_receive_queues_sealed',
    'first_FIFO_marker_acknowledged','original192_handlers_finished',
    'first_pause_restored_with_no_input','actual_original_budget_exhausted',
    'final_supported_pause_prefetch_quiesced','final_FIFO_marker_acknowledged',
    'owned_probe_closed_and_handler_finished','no_remaining_input_producers',
    'real_bank_shutdown_intent_sealed','original_main_graceful_stop',
    'newest_stopped_checkpoint_CPU_verified','exact_parser_and_resume_record_installed',
    'one_replacement_started','same_replacement_startup_verified','original_fleet_thawed',
    'original192_reconnected_and_learning']


class Backend:
    def __init__(self,fail=None,pending=False,updates=0):
        self.fail,self.pending = fail,pending
        self.stages,self.calls,self.recoveries = [],[],[]
        self.results = dict(seal_banks=dict(input_sources_sealed=True,all_handlers_finished=True,
            prefetch_paused=True,budget_exhausted=True,bank_shutdown_intent_verified=True),
            stop_original=dict(actual_exit=0,original_absent=True),
            verify_stopped=dict(actual_original_CPU_exit=0,strict_phase_verified=True,
                newest_stopped_source=True,replay_bank_consistency_verified=True),
            install=dict(exact_selected_parser=True,only_selected_source_changed=True,newest_checkpoint_unchanged=True),
            verify_startup=dict(same_original_replacement=True,newest_state_preserved=True,
                startup_update_count=updates,logical_sample_delta=updates*4096,learner_frame_delta=0,
                raw_frame_delta=0,replay_storage_and_bank_identity_verified=True),
            verify_progress=dict(original192_identities_preserved=True,training_progress_verified=True,pipeline_errors=0))
        self.recovery_error = False

    def before_stage(self,stage):
        self.stages.append(stage)
        if self.fail == stage:
            if self.pending:
                raise C.ObservationPending('Same handle remains live')
            raise RuntimeError('Injected original failure: '+stage)

    def after_stage(self,stage,value):
        pass

    def __getattr__(self,name):
        if name.startswith('_') or name == 'bind_observation_pending':
            raise AttributeError(name)
        def operation(*args):
            self.calls.append(name)
            return self.results.get(name,{})
        return operation

    def recover(self,controller,*,observation_pending):
        self.recoveries.append(observation_pending)
        if self.recovery_error:
            raise RuntimeError('Recovery failed independently')
        return dict(status='SAME_REPLACEMENT_HANDLE_OBSERVATION_PENDING' if observation_pending else
                    'PRESTOP_ORIGINAL_RESOURCES_RESTORED',errors=[])

    def finish(self,value):
        self.finished = value


class ControllerTests(unittest.TestCase):
    def test_closed_original_probe_API_cache_is_pending_until_explicit_zero_clients(self):
        path = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')/(
            'future-score-carry-main-handoff-original01-preparation-20261019/live-original03/API-wires/0188.raw')
        captured = json.loads(L.checked(L.full_pin(path)))
        self.assertEqual(captured['client_count'],1)
        self.assertEqual(captured['client_rows'][0]['client_slot'],8191)
        complete = dict(captured,client_count=0,client_rows=[])
        snapshots = iter([captured,complete])
        b = L.LinuxBackend.__new__(L.LinuxBackend)
        b.api = lambda:next(snapshots)
        b.probe_id = captured['client_rows'][0]['client_id']
        b.current_pause = {k:captured['managed_measurement'][k] for k in ('label','generation')}
        b.owner,b.actor_handlers,b.probe_tid = dict(pid=99999999),{},dict(tid=1)
        b.accept_held = b.fleet_frozen = True
        observed = []
        def bounded_wait(predicate,seconds,message):
            if seconds == 5:
                observed.extend([predicate(),predicate()])
            else:
                observed.append(predicate())
        b.wait = bounded_wait
        with patch.object(L,'potential_handlers',return_value={}):
            self.assertTrue(b.no_producers({}, {})['all_handlers_finished'])
        self.assertEqual(observed,[False,True,True])

    def test_owned_startup_label_wait_never_hides_pipeline_or_bank_errors(self):
        path = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')/(
            'future-score-carry-main-handoff-original01-preparation-20261019/live-original03/API-wires/0188.raw')
        captured = json.loads(L.checked(L.full_pin(path)))
        expected = captured['managed_experiment']
        for kind in ('replay','optimizer'):
            captured['host_pipeline']['learning_exposure'][kind]['process_id'] = 222
        captured['ts'],captured['pipeline_snapshot_age_s'] = time.time(),0.
        captured['managed_experiment'] = 'initializing'
        raw_path = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/raw_api_witness_v1.py')
        spec = importlib.util.spec_from_file_location('_startup_actual_raw_reader',raw_path)
        raw = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(raw)
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            (output/'API-wires').mkdir()
            b = L.LinuxBackend.__new__(L.LinuxBackend)
            b.raw,b.counter,b.owner,b.replacement,b.main = raw,0,dict(pid=826357),dict(pid=222),dict(experiment=expected)
            b.event = lambda name,value:L.publish(output/name,value)
            def response(*args,**kwargs):
                return io.BytesIO(json.dumps(captured).encode())
            with patch('urllib.request.urlopen',side_effect=response):
                self.assertIsNone(b.api(observe_startup=True))
                captured['managed_experiment'] = expected
                self.assertEqual(b.api(observe_startup=True)['managed_experiment'],expected)
                captured['managed_experiment'] = 'initializing'
                captured['bank_persistence']['write_failures'] = 1
                with self.assertRaisesRegex(RuntimeError,'pipeline/bank health'):
                    b.api(observe_startup=True)

    def test_actual_original_pause_off_training_off_cache_waits_for_complete_restore(self):
        directory = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')/(
            'future-score-carry-main-handoff-original01-preparation-20261019/live-original02/API-wires')
        active = json.loads(L.checked(L.full_pin(directory/'0170.raw')))
        partial = json.loads(L.checked(L.full_pin(directory/'0171.raw')))
        self.assertFalse(partial['measurement_active'])
        self.assertFalse(partial['training_enabled'])
        self.assertEqual(partial['managed_measurement']['phase'],'finished')
        complete = copy.deepcopy(partial)
        complete['training_enabled'] = True
        snapshots = iter([active,partial,complete])
        with tempfile.TemporaryDirectory() as root:
            control = Path(root)/'control.json'
            control.write_bytes(b'{"measurement":"owned"}\n')
            b = L.LinuxBackend.__new__(L.LinuxBackend)
            b.control_pin,b.control_bytes = L.full_pin(control),b'{"lr_scale":0.25}\n'
            b.job = dict(case='scorecarry-private-restoration')
            b.state = lambda:None
            b.api = lambda:next(snapshots)
            observed = []
            def bounded_wait(predicate,seconds,message):
                observed.extend(predicate() for _ in range(3))
                self.assertEqual(observed,[False,False,True])
            b.wait = bounded_wait
            with patch.object(L,'CONTROL',control):
                result = b.cancel_pause(dict(label=partial['managed_measurement']['label']))
            self.assertTrue(result['owned_pause_restored'])
            self.assertEqual(control.read_bytes(),b.control_bytes)

    def test_actual_original_warming_empty_boundary_waits_for_the_next_driver_tick(self):
        path = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')/(
            'future-score-carry-main-handoff-original01-preparation-20261019/live-original01/API-wires/0011.raw')
        captured = json.loads(L.checked(L.full_pin(path)))
        self.assertEqual(captured['managed_measurement']['boundary'],{})
        self.assertEqual(captured['client_count'],193)
        baseline = copy.deepcopy(captured)
        for row in baseline['client_rows']:
            if row['client_slot'] != 8191:
                row['session_seconds'] -= 16/60
        probe = next(row['client_id'] for row in captured['client_rows'] if row['client_slot'] == 8191)
        complete = copy.deepcopy(captured)
        complete['managed_measurement']['boundary'] = dict(acknowledged=192,pending_client_ids=[probe],
                                                           replay_pending_client_ids=[])
        snapshots = iter([baseline,captured,complete])
        backend = L.LinuxBackend.__new__(L.LinuxBackend)
        backend.api = lambda:next(snapshots)
        backend.probe_id = probe
        observed = []
        def bounded_wait(predicate,seconds,message):
            observed.append(predicate())
            observed.append(predicate())
            self.assertEqual(observed,[False,True])
        backend.wait = bounded_wait
        managed = captured['managed_measurement']
        result = backend.measured_progress(dict(label=managed['label'],generation=managed['generation']))
        self.assertEqual(set(result['measured_frame_deltas'].values()),{16})

    def test_two_pause_order_and_counted_actual_startup_work(self):
        for updates in (0,1):
            with self.subTest(updates=updates):
                b = Backend(updates=updates)
                result = C.Handoff(b).run()
                self.assertEqual(result['status'],'SCORE_CARRY_HANDOFF_VERIFIED_ORIGINAL192_LEARNING')
                self.assertEqual(b.stages,STAGES)
                self.assertEqual(result['startup_update_count'],updates)
                self.assertEqual(b.calls.count('stop_original'),1)
                self.assertEqual(b.calls.count('start_once'),1)
                self.assertFalse(result['objective_complete'])
                self.assertFalse(result['quality_qualified'])

    def test_each_stage_failure_stops_dependent_actions_and_never_retries(self):
        for i,stage in enumerate(STAGES):
            with self.subTest(stage=stage):
                b = Backend(fail=stage)
                h = C.Handoff(b)
                result = h.run()
                self.assertEqual(result['status'],'ORIGINAL_HANDOFF_FAILURE_PRESERVED')
                self.assertEqual(b.stages,STAGES[:i+1])
                self.assertEqual(b.recoveries,[False])
                if i <= STAGES.index('original_main_graceful_stop'):
                    self.assertNotIn('stop_original',b.calls)
                if i <= STAGES.index('one_replacement_started'):
                    self.assertNotIn('start_once',b.calls)
                with self.assertRaisesRegex(C.HandoffError,'Do not retry'):
                    h.run()

    def test_every_final_seal_flag_is_required_before_signal(self):
        for key in Backend().results['seal_banks']:
            with self.subTest(key=key):
                b = Backend()
                del b.results['seal_banks'][key]
                C.Handoff(b).run()
                self.assertNotIn('stop_original',b.calls)

    def test_strict_CPU_gate_precedes_source_install(self):
        for key in Backend().results['verify_stopped']:
            with self.subTest(key=key):
                b = Backend()
                b.results['verify_stopped'][key] = False
                C.Handoff(b).run()
                self.assertNotIn('install',b.calls)
                self.assertNotIn('start_once',b.calls)

    def test_boolean_exit_or_frame_counters_cannot_pass_as_zero(self):
        for operation,key in [('stop_original','actual_exit'),('verify_stopped','actual_original_CPU_exit'),
                ('verify_startup','startup_update_count'),('verify_startup','logical_sample_delta'),
                ('verify_startup','raw_frame_delta'),('verify_startup','learner_frame_delta'),
                ('verify_progress','pipeline_errors')]:
            with self.subTest(operation=operation,key=key):
                b = Backend()
                b.results[operation][key] = False
                self.assertEqual(C.Handoff(b).run()['status'],'ORIGINAL_HANDOFF_FAILURE_PRESERVED')

    def test_live_observation_expiry_preserves_same_handle_without_retry(self):
        b = Backend(fail='same_replacement_startup_verified',pending=True)
        result = C.Handoff(b).run()
        self.assertEqual(result['status'],'SAME_ORIGINAL_HANDLE_OBSERVATION_PENDING')
        self.assertEqual(b.recoveries,[True])
        self.assertEqual(b.calls.count('start_once'),1)
        self.assertNotIn('thaw_fleet',b.calls)
        self.assertFalse(result['restart_retry'])

    def test_recovery_failure_does_not_mask_original_or_skip_receipt(self):
        b = Backend(fail='preflight')
        b.recovery_error = True
        result = C.Handoff(b).run()
        self.assertIn('Injected original failure',result['error'])
        self.assertIn('Recovery failed independently',result['recovery_error'])
        self.assertIs(b.finished,result)


class ActualFileTests(unittest.TestCase):
    def test_actual_console_append_window_preserves_identity_and_detects_save_failures(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'console.log'
            path.write_bytes(b'prior attempts including an old save failed: record\n')
            before = path.stat()
            binding = dict(path=str(path),device=before.st_dev,inode=before.st_ino,uid=before.st_uid,
                           nlink=1,offset=before.st_size)
            raw = (b'Flushing mmap replay buffer (6,000,000 transitions)...\nReplay mmap flushed in 0.2s\n'
                   b'Final model & settings saved\nShutdown complete\n')
            with path.open('ab') as stream:
                stream.write(raw)
            self.assertEqual(P.read_console_tail(binding),raw)
            self.assertTrue(P.final_save_console(raw)['actual_replay_flush_success_logged'])
            for warning in (b'Replay buffer save failed: injected',b'[WARN] HOF save failed: injected',
                            b'[WARN] EpHOF save failed: injected'):
                with self.subTest(warning=warning),self.assertRaisesRegex(RuntimeError,'logged a failure'):
                    P.final_save_console(raw+warning)
            bad = dict(binding,inode=binding['inode']+1)
            with self.assertRaisesRegex(RuntimeError,'identity/offset changed'):
                P.read_console_tail(bad)

    def test_save_request_publication_refuses_foreign_slot_and_keeps_actual_single_link_pin(self):
        with tempfile.TemporaryDirectory() as root:
            staging,request = Path(root)/'owned-staging.json',Path(root)/'request.json'
            raw = b'{"tag":"owned"}\n'
            L.publish(staging,raw)
            request.write_bytes(b'{"tag":"foreign"}\n')
            with self.assertRaises(FileExistsError):
                P.publish_request_exclusive(L,staging,request)
            self.assertEqual(request.read_bytes(),b'{"tag":"foreign"}\n')
            self.assertEqual(staging.read_bytes(),raw)
            request.unlink()
            published = P.publish_request_exclusive(L,staging,request)
            self.assertEqual(L.checked(published),raw)
            self.assertFalse(staging.exists())
            self.assertEqual(published['identity']['nlink'],1)
            self.assertEqual(published['path'],str(request))

    def test_exact_existing_controller_pin_ABI_and_full_pin_ABI(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'immutable.json'
            path.write_bytes(b'{"actual":true}\n')
            path.chmod(0o444)
            full = L.full_pin(path)
            legacy = copy.deepcopy(full)
            legacy['identity'] = {k:v for k,v in full['identity'].items()
                                  if k in ('device','inode','mode','uid','nlink')}
            self.assertEqual(L.checked(full),L.checked(legacy))
            for key in ('inode','uid','nlink'):
                bad = copy.deepcopy(legacy)
                bad['identity'][key] += 1
                with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'changed'):
                    L.checked(bad)
            bad = copy.deepcopy(legacy)
            bad['identity']['mtime_ns'] = full['identity']['mtime_ns']
            with self.assertRaisesRegex(RuntimeError,'Unknown pin identity ABI'):
                L.checked(bad)
            path.chmod(0o664)
            writable = L.full_pin(path)
            writable['identity'] = {k:v for k,v in writable['identity'].items() if k in legacy['identity']}
            with self.assertRaisesRegex(RuntimeError,'changed'):
                L.checked(writable)

    def test_atomic_control_restore_and_foreign_preimage_refusal(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'control.json'
            path.write_bytes(b'{"lr_scale":0.25}\n')
            old = L.full_pin(path)
            new = L.atomic_owned_replace(path,old,b'{"measurement":"owned"}\n',suffix='owned')
            self.assertNotEqual(old['identity']['inode'],new['identity']['inode'])
            path.write_bytes(b'{"measurement":"foreign"}\n')
            with self.assertRaisesRegex(RuntimeError,'changed'):
                L.atomic_owned_replace(path,new,b'old',suffix='owned')
            self.assertEqual(path.read_bytes(),b'{"measurement":"foreign"}\n')

    def test_staging_creation_race_preserves_foreign_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'control.json'
            path.write_bytes(b'original')
            staging = path.with_name('control.json.owned.tmp')
            original_open = Path.open
            def racing_open(current,*args,**kwargs):
                if current == staging and args and args[0] == 'xb':
                    with original_open(staging,'wb') as stream:
                        stream.write(b'foreign staging owner')
                return original_open(current,*args,**kwargs)
            pin = L.full_pin(path)
            with patch.object(Path,'open',racing_open):
                with self.assertRaises(FileExistsError):
                    L.atomic_owned_replace(path,pin,b'new',suffix='owned')
            self.assertEqual(staging.read_bytes(),b'foreign staging owner')
            self.assertEqual(path.read_bytes(),b'original')

    def test_recovery_covers_rename_before_state_update_and_refuses_foreign_control(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'control.json'
            base = b'{"experiment":"test","lr_scale":0.25}\n'
            case = 'scorecarry-test'
            variants = R.owned_control_variants(base,case)
            for raw in variants:
                path.write_bytes(raw)
                state = dict(control_path=str(path),expected_owned_control={'stale':'before atomic rename'})
                R.restore_original_control(L,dict(case=case),state,base)
                self.assertEqual(path.read_bytes(),base)
            path.write_bytes(b'{"lr_scale":0.5}')
            with self.assertRaisesRegex(RuntimeError,'foreign control'):
                R.restore_original_control(L,dict(case=case),state,base)
            self.assertEqual(path.read_bytes(),b'{"lr_scale":0.5}')


class RecoveryTests(unittest.TestCase):
    def test_result_file_does_not_hide_failed_recovery(self):
        self.assertTrue(R.terminal_recovery_required(dict(status='ORIGINAL_HANDOFF_FAILURE_PRESERVED')))
        self.assertTrue(R.terminal_recovery_required(dict(recovery_error='failed')))
        self.assertTrue(R.terminal_recovery_required(dict(recovery=dict(status='PRESTOP_ORIGINAL_RESOURCES_RESTORED',errors=['failed']))))
        self.assertFalse(R.terminal_recovery_required(dict(recovery=dict(status='PRESTOP_ORIGINAL_RESOURCES_RESTORED',errors=[]))))

    def test_committed_live_timeout_only_resumes_exact_owned_publication_pause(self):
        owner = dict(pid=222,starttime_ticks=333,unit='owned.service',invocation_id='a'*32,cgroup='/owned')
        replacement = dict(owner,pid=444,starttime_ticks=555,invocation_id='b'*32)
        job = dict(prepared={'path':'prepared'},case='scorecarry-test')
        state = dict(case=job['case'],original_owner=owner,original_stop_sent=True,replacement=replacement,
                     poststop=dict(startup_save_paused_owner=None))
        fake = SimpleNamespace(checked=lambda pin: json.dumps({'original_main':{'path':'main'}} if pin['path']=='prepared'
            else {'owner':owner}).encode(),process_start=lambda pid: 555 if pid==444 else None,
            live_owner=lambda observed: self.assertEqual(observed,replacement))
        with patch.object(P,'load_linux',return_value=fake),patch.object(os,'kill') as kill:
            result = P.recover_committed(job,state,observation_pending=True)
            self.assertEqual(result['owner'],replacement)
            self.assertFalse(result['restart_retry'])
            kill.assert_not_called()
            state['poststop']['startup_save_paused_owner'] = replacement
            P.recover_committed(job,state,observation_pending=True)
            kill.assert_called_once_with(444,signal.SIGCONT)
            state['poststop']['startup_save_paused_owner'] = owner
            with self.assertRaisesRegex(RuntimeError,'captured save-publication owner'):
                P.recover_committed(job,state,observation_pending=True)
            kill.assert_called_once()

    def test_owner_unit_invocation_and_cgroup_drift_rejected(self):
        owner = dict(pid=222,starttime_ticks=333,unit='owned.service',invocation_id='a'*32,cgroup='/owned')
        original = dict(MainPID='222',InvocationID='a'*32,ControlGroup='/owned',NRestarts='0',SubState='running')
        for field,bad in [('MainPID','999'),('InvocationID','b'*32),('ControlGroup','/foreign'),('NRestarts','1')]:
            with self.subTest(field=field),patch.object(L,'show',return_value=dict(original,**{field:bad})),\
                    patch.object(L,'process_start',return_value=333):
                with self.assertRaisesRegex(RuntimeError,'owner changed'):
                    L.live_owner(owner)


class StartupAndBankTests(unittest.TestCase):
    def test_dirty_paused_bank_intent_is_explicitly_unpersisted_until_matching_final_generations(self):
        total = dict(attempts_started=5,outcomes_recorded=5,applied=5,amp_skipped=0,unavailable=0)
        before = dict(ts=98,pipeline_snapshot_age_s=.1,pipeline_read_error='',bank_persistence_read_error='',
            training_enabled=False,measurement_active=True,
            managed_measurement=dict(active=True,phase='warming',generation=3,label='owned'),
            frame_count=2000,learner_frame_count=1000,measurement_frames=1000,training_steps=7,optimized_samples=3584,
            host_pipeline=dict(available=True,generation=1,elapsed_s=10,learning_exposure=dict(
                optimizer=dict(enabled=True,available=True,process_id=123,epoch=1,total=total,unclassified_started_total=0),
                replay=dict(enabled=True,process_id=123,epoch=1,accepted_total=22,accepted_learner_total=14,
                            accepted_by_source_total=dict(dqn=14,expert=8)))),
            bank_persistence=dict(writer_active=False,write_failures=0,last_error=None,writes=1,
                revision=dict(hof=9,ephof=9),saved_revision=dict(hof=7,ephof=7),dirty=dict(hof=True,ephof=True),
                output=dict(active=None,totals={'write':dict(errors=0)})))
        after = copy.deepcopy(before)
        after['ts'],after['host_pipeline']['elapsed_s'] = 99,12
        bank = dict(selector=dict(mutation_generation=7),episodes=192,stride=1536,state_size=11128,captured_adds=22)
        banks = dict(hof=copy.deepcopy(bank),ephof=copy.deepcopy(bank))
        intent = I.validate(before,after,banks,expected_pid=123,now=100)
        self.assertFalse(intent['all_target_revisions_already_persisted'])
        final = copy.deepcopy(banks)
        for value in final.values():
            value['selector']['mutation_generation'] = 9
            value['pointer'] = dict(mtime_ns=101000000000)
        self.assertTrue(P.fulfill_bank_intent(intent,final,{}, {},100)['all_target_revisions_now_persisted'])
        bad = copy.deepcopy(final)
        bad['hof']['selector']['mutation_generation'] = 7
        with self.assertRaisesRegex(RuntimeError,'sealed RAM revision'):
            P.fulfill_bank_intent(intent,bad,{}, {},100)
        clean = copy.deepcopy(intent)
        clean_final = copy.deepcopy(final)
        old_semantics,new_semantics = {},{}
        for name in ('hof','ephof'):
            clean['target_revisions'][name] = 7
            clean['dirty_at_seal'][name] = False
            clean['banks'][name].update(transitions=3,arrays={'states':dict(header={'shape':[4,5]},bytes=128)})
            clean_final[name].update(selector=dict(mutation_generation=7),captured_adds=23,transitions=3,
                                     arrays=copy.deepcopy(clean['banks'][name]['arrays']))
            old_semantics[name] = {'ep_len.npy':'a','captured_adds.npy':'old','stale_age.npy':'old'}
            new_semantics[name] = dict(old_semantics[name],**{'captured_adds.npy':'new','stale_age.npy':'new'})
        self.assertTrue(P.fulfill_bank_intent(clean,clean_final,old_semantics,new_semantics,100)[
            'all_target_revisions_now_persisted'])
        new_semantics['hof']['ep_len.npy'] = 'changed'
        with self.assertRaisesRegex(RuntimeError,'clean bank episode metadata'):
            P.fulfill_bank_intent(clean,clean_final,old_semantics,new_semantics,100)
        for mutation in ('dirty_lie','writer','counter','cache','revision','error','owner'):
            changed = copy.deepcopy(after)
            if mutation == 'dirty_lie':changed['bank_persistence']['dirty']['hof'] = False
            elif mutation == 'writer':changed['bank_persistence']['writer_active'] = True
            elif mutation == 'counter':changed['measurement_frames'] += 1
            elif mutation == 'cache':changed['host_pipeline']['elapsed_s'] = 10
            elif mutation == 'revision':changed['bank_persistence']['revision']['hof'] += 1
            elif mutation == 'error':changed['bank_persistence']['output']['totals']['write']['errors'] = 1
            else:changed['host_pipeline']['learning_exposure']['optimizer']['process_id'] = 999
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                I.validate(before,changed,banks,expected_pid=123,now=100)

    def test_final_replay_save_success_and_caught_failure_or_foreign_producer(self):
        owner = dict(pid=12,invocation_id='a'*32)
        messages = ['Flushing mmap replay buffer (6,000,000 transitions)...','Replay mmap flushed in 0.2s',
                    'Final model & settings saved','Shutdown complete']
        def wire(values,pid='12',inv='a'*32):
            return b'\n'.join(json.dumps(dict(MESSAGE=message,_PID=pid,_SYSTEMD_INVOCATION_ID=inv,
                __REALTIME_TIMESTAMP='100000000')).encode() for message in values)
        self.assertTrue(P.final_save_journal(wire(messages),owner,99,101)['original_final_save_messages_verified'])
        for failure in ('  Replay buffer save failed: injected','  [WARN] HOF save failed: injected',
                        '  [WARN] EpHOF save failed: injected','[MANAGED MEASUREMENT] restore failed during shutdown: injected'):
            with self.subTest(failure=failure),self.assertRaisesRegex(RuntimeError,'logged a failure'):
                P.final_save_journal(wire(messages+[failure]),owner,99,101)
        for kwargs in (dict(pid='99'),dict(inv='b'*32)):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(RuntimeError,'another producer'):
                P.final_save_journal(wire(messages,**kwargs),owner,99,101)
        with self.assertRaisesRegex(RuntimeError,'sequence is incomplete'):
            P.final_save_journal(wire(messages[1:]),owner,99,101)

    def test_stopped_ring_position_and_storage_follow_actual_completed_insertions(self):
        array = dict(path='/dev/shm/private/array.npy',dtype='<f2',shape=[6000000,2],data_offset=128,
            data_bytes=24000000,header_sha256='a'*64,identity=dict(device=1,inode=2,size=24000128,uid=1001,nlink=1))
        boot = dict(spec=dict(capacity=6000000),ring=dict(meta=dict(ptr=5999997,size=6000000),
            arrays={str(i):copy.deepcopy(array) for i in range(10)}))
        stopped = copy.deepcopy(boot)
        stopped['ring']['meta']['ptr'] = 5
        exposure = dict(schema='robotron-replay-insert-exposure-v1',enabled=True,available=True,
            process_id=12,epoch=1,epoch_reason='directory_adopt_begin',accepted_total=8)
        self.assertEqual(P.ring_continuity(boot,stopped,exposure,12)['actual_stopped_pointer'],5)
        for change in (dict(accepted_total=7),dict(accepted_total=True),dict(epoch=2),dict(process_id=99)):
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                P.ring_continuity(boot,stopped,dict(exposure,**change),12)
        replaced = copy.deepcopy(stopped)
        replaced['ring']['arrays']['0']['identity']['inode'] += 1
        with self.assertRaisesRegex(RuntimeError,'storage was replaced'):
            P.ring_continuity(boot,replaced,exposure,12)

    def test_zero_or_one_actual_batch_and_no_boolean_clocks(self):
        before = dict(training_steps=10,optimized_samples=40960,learner_frame_count=100,frame_count=200)
        for count in (0,1):
            after = dict(before,training_steps=10+count,optimized_samples=40960+count*4096)
            self.assertEqual(P.startup_delta(after,before)['startup_update_count'],count)
        for change in [dict(training_steps=12,optimized_samples=49152),dict(frame_count=201),dict(optimized_samples=40961),
                       dict(training_steps=True)]:
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                P.startup_delta(dict(before,**change),before)

    def test_new_disk_generation_allowed_only_with_same_revision_and_metadata(self):
        bank = dict(selector=dict(generation='before',mutation_generation=9),episodes=2,transitions=3,
            stride=4,state_size=5,captured_adds=6,arrays={'states':dict(header={'descr':'<f4','shape':[8,5]},bytes=128)})
        before = dict(hof=copy.deepcopy(bank),ephof=copy.deepcopy(bank))
        after = copy.deepcopy(before)
        after['hof']['selector']['generation'] = 'after'
        semantic = dict(hof={'ep_len.npy':'a'*64},ephof={'ep_len.npy':'b'*64})
        P.verify_final_banks(before,after,semantic,semantic)
        after['hof']['selector']['mutation_generation'] += 1
        with self.assertRaisesRegex(RuntimeError,'sealed bank'):
            P.verify_final_banks(before,after,semantic,semantic)
        after = copy.deepcopy(before)
        changed = copy.deepcopy(semantic)
        changed['hof']['ep_len.npy'] = 'c'*64
        with self.assertRaisesRegex(RuntimeError,'sealed bank'):
            P.verify_final_banks(before,after,semantic,changed)


class SocketTests(unittest.TestCase):
    def test_193_actual_loopback_connections_join_and_detect_queued_input_and_foreign_peer(self):
        clients,servers = [],[]
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0))
            listener.listen(256)
            port = listener.getsockname()[1]
            try:
                for _ in range(193):
                    clients.append(socket.create_connection(listener.getsockname(),timeout=2))
                    servers.append(listener.accept()[0])
                inode = lambda sock: int(os.readlink('/proc/self/fd/'+str(sock.fileno()))[8:-1])
                owned = {i:{inode(sock):[sock.fileno()]} for i,sock in enumerate(clients)}
                server_inodes = {inode(sock):[sock.fileno()] for sock in servers}
                rows = S.tcp_rows(os.getpid(),port)
                joined = S.join_owned_connections(rows,server_inodes,owned,port=port)
                self.assertEqual(len(joined),193)
                self.assertTrue(all(v['server']['rx_bytes'] == v['client']['tx_bytes'] == 0 for v in joined))
                clients[0].sendall(b'pending input')
                deadline = time.monotonic()+2
                while time.monotonic()<deadline:
                    joined = S.join_owned_connections(S.tcp_rows(os.getpid(),port),server_inodes,owned,port=port)
                    if joined[0]['server']['rx_bytes']:
                        break
                    time.sleep(.01)
                self.assertEqual(joined[0]['server']['rx_bytes'],len(b'pending input'))
                bad = dict(owned)
                bad[0] = owned[1]
                with self.assertRaisesRegex(RuntimeError,'one-to-one'):
                    S.join_owned_connections(rows,server_inodes,bad,port=port)
                clients.append(socket.create_connection(listener.getsockname(),timeout=2))
                servers.append(listener.accept()[0])
                server_inodes[inode(servers[-1])] = [servers[-1].fileno()]
                with self.assertRaisesRegex(RuntimeError,'connection count'):
                    S.join_owned_connections(S.tcp_rows(os.getpid(),port),server_inodes,owned,port=port)
            finally:
                for sock in clients+servers:
                    sock.close()

    def test_truncated_timer_name_is_not_counted_as_a_receive_wait_or_a_birth(self):
        candidates = {i:dict(tid=i,starttime_ticks=i+100,wchan='poll_schedule_timeout.constprop.0') for i in range(193)}
        candidates[999] = dict(tid=999,starttime_ticks=1000,wchan='hrtimer_nanosleep')
        probe = candidates[192]
        original = {i:candidates[i] for i in range(192)}
        with patch.object(S,'birth',side_effect=lambda pid,tid: candidates[tid]['starttime_ticks']):
            self.assertEqual(len(S.verify_waiting_threads(1,candidates,probe,original)),193)
        with patch.object(S,'birth',return_value=99999),self.assertRaisesRegex(RuntimeError,'TID was replaced'):
            S.verify_waiting_threads(1,candidates,probe,original)


class ActualBoundedUnitTests(unittest.TestCase):
    def test_live_runner_original_birth_runtime_and_six_descriptor_release_for_both_roles(self):
        root = HERE.parent/'live-runner-unit-lifecycle'
        root.mkdir(mode=0o700)
        r = V.Runner.__new__(V.Runner)
        r.l,r.out = L,root
        def load_absolute(path,name):
            spec = importlib.util.spec_from_file_location(name,path)
            value = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(value)
            return value
        game = Path('/home/dave/source/repos/ArcadeAI/Robotron')
        r.c = load_absolute(game/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_test_runner_C218')
        r.reader = load_absolute(game/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_test_runner_reader')
        r.reviewer = load_absolute(game/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_test_runner_reviewer')
        case = 'scorecarry-runner-private-'+str(os.getpid())+'-20261019'
        r.plan = dict(controller_unit='robotron-'+case+'-controller.service',rescue_unit='robotron-'+case+'-rescue.service',
                      controller_runtime_s=1800,rescue_runtime_s=2300)
        summaries = {}
        with patch.object(V,'CASE',case):
            for role in ('controller','rescue'):
                with self.subTest(role=role):
                    owner = r.launch(role,['/usr/bin/python3.12','-I','-B','-c','import time; time.sleep(2)'])
                    self.assertEqual(owner['unit'],r.plan[role+'_unit'])
                    self.assertTrue(owner['observed_live'])
                    child = Path('/sys/fs/cgroup'+owner['cgroup'])/('listener-'+case)
                    child.mkdir()
                    (child/'cgroup.type').write_text('threaded\n')
                    (child/'cgroup.freeze').write_text('1\n')
                    r.wait(lambda:L.show(owner['unit']).get('MainPID') == '0',10,'Private owner has not retired')
                    cleanup = P.release_retired_empty_listener(L,owner,case)
                    self.assertTrue(cleanup['status'].startswith('retired_'))
                    self.assertFalse(child.exists())
                    closure = r.wait(lambda:r.close_if_terminal(role),10,'Private original unit did not close')
                    self.assertEqual(closure['original_exit'],0)
                    self.assertTrue(closure['lifecycle_complete'])
                    self.assertEqual(len(closure['full_original_archives']),6)
                    summaries[role] = L.full_pin(root/(role+'-unit/root-original-result-and-owned-release.json'))
        L.publish(root/'both-original-unit-roles-PASS.json',dict(status='PASS',closures=summaries,
            actual_live_runtime_bounds_s=dict(controller=1800,rescue=2300),production_changed=False))


if __name__ == '__main__':
    unittest.main(verbosity=2)
