"""CPU-only failure-order, recovery, actual file and loopback TCP checks."""
import copy
import importlib.util
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


STAGES = ['preflight','probe_registered_without_frames','first_supported_pause',
    'all192_acknowledged_and_advanced8_measured_frames','exact_accept_thread_held',
    'original_emulator_fleet_frozen','input_ownership_and_receive_queues_sealed',
    'first_FIFO_marker_acknowledged','original192_handlers_finished',
    'first_pause_restored_with_no_input','actual_original_budget_exhausted',
    'final_supported_pause_prefetch_quiesced','final_FIFO_marker_acknowledged',
    'owned_probe_closed_and_handler_finished','no_remaining_input_producers',
    'real_bank_generations_sealed','original_main_graceful_stop',
    'newest_stopped_checkpoint_CPU_verified','exact_parser_and_resume_record_installed',
    'one_replacement_started','same_replacement_startup_verified','original_fleet_thawed',
    'original192_reconnected_and_learning']


class Backend:
    def __init__(self,fail=None,pending=False,updates=0):
        self.fail,self.pending = fail,pending
        self.stages,self.calls,self.recoveries = [],[],[]
        self.results = dict(seal_banks=dict(input_sources_sealed=True,all_handlers_finished=True,
            prefetch_paused=True,budget_exhausted=True,bank_pair_verified=True),
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
