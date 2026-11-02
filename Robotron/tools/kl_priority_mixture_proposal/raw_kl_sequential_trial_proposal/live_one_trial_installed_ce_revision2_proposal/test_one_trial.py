"""Authored stdlib contracts; only root may execute this future test module."""
import contextlib
import copy
import fcntl
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

from . import deadline_guard as d
from . import run_one_trial as c


OWNER = dict(pid=101, starttime_ticks=202, unit='owned.service',
    invocation_id='a' * 32, cgroup='/owned/owned.service')


class DeadlineContracts(unittest.TestCase):
    def adopted(self):
        return dict(owner=copy.deepcopy(OWNER), start=dict(boot_id='boot', monotonic_s=0))

    def test_unbound_old_CE_is_never_a_guessed_KL_target(self):
        probe, stop = mock.Mock(), mock.Mock()
        result = d.supervise(adoption=lambda: None,
            get_clock=lambda: dict(boot_id='boot', monotonic_s=4000),
            probe=probe, stop=stop, sleep=lambda value: None, emit=lambda value: None, maximum_polls=3)
        self.assertEqual(result['status'], 'UNBOUND_OR_UNOBSERVABLE_MANUAL')
        probe.assert_not_called(); stop.assert_not_called()

    def test_exact3310_stop_and_actual_retirement_are_separate(self):
        now = [3309.0]; stopped = []
        def sleep(value): now[0] += value
        def probe(owner): return dict(state='ABSENT' if stopped else 'SAME')
        result = d.supervise(adoption=self.adopted,
            get_clock=lambda: dict(boot_id='boot', monotonic_s=now[0]), probe=probe,
            stop=lambda owner: stopped.append((owner, now[0])), sleep=sleep,
            emit=lambda value: None, maximum_polls=4)
        self.assertEqual(stopped, [(OWNER, 3310.0)])
        self.assertEqual(result['status'], 'RETIRED')
        self.assertEqual(result['absence']['elapsed_s'], 3310)

    def test_slow_absence_probe_uses_receipt_time_not_start_time(self):
        now = [3599.0]
        def probe(owner): now[0] = 3600.01; return dict(state='ABSENT')
        result = d.supervise(adoption=self.adopted,
            get_clock=lambda: dict(boot_id='boot', monotonic_s=now[0]), probe=probe,
            stop=mock.Mock(), sleep=lambda value: None, emit=lambda value: None)
        self.assertEqual(result['status'], 'CEILING_BREACH')
        self.assertEqual(result['absence']['elapsed_s'], 3600.01)

    def test_new_CE_or_unknown_replacement_is_never_stopped(self):
        command = mock.Mock(); lock = NS(hold=lambda: contextlib.nullcontext())
        replacement = lambda owner: dict(state='REPLACEMENT_OR_OTHER_MEMBERS')
        result = d.supervise(adoption=self.adopted,
            get_clock=lambda: dict(boot_id='boot', monotonic_s=3311),
            probe=replacement, stop=lambda owner: d.request_stop(owner, lock, probe=replacement, command=command),
            sleep=lambda value: None, emit=lambda value: None)
        command.assert_not_called(); self.assertEqual(result['status'], 'MANUAL_RECONCILIATION')

    def test_later_marker_failure_cannot_block_already_adopted_owner_stop(self):
        now = [3309]; adopted = mock.Mock(side_effect=[self.adopted(), RuntimeError('later marker error')])
        stopped = []
        result = d.supervise(adoption=adopted,
            get_clock=lambda: dict(boot_id='boot', monotonic_s=now[0]),
            probe=lambda owner: dict(state='ABSENT' if stopped else 'SAME'),
            stop=lambda owner: stopped.append(owner),
            sleep=lambda value: now.__setitem__(0, now[0]+value), emit=lambda value: None, maximum_polls=4)
        self.assertEqual(adopted.call_count, 1); self.assertEqual(stopped, [OWNER])
        self.assertEqual(result['status'], 'RETIRED')

    def test_pre_request_guard_error_does_not_become_absence(self):
        stop = mock.Mock(side_effect=OSError('stop request failed'))
        now = [3310]
        result = d.supervise(adoption=self.adopted,
            get_clock=lambda: dict(boot_id='boot', monotonic_s=now[0]),
            probe=lambda owner: dict(state='SAME'), stop=stop,
            sleep=lambda value: now.__setitem__(0, now[0]+value), emit=lambda value: None, maximum_polls=3)
        self.assertEqual(stop.call_count, 3)  # only pre-submission exact-owner guard retries
        self.assertNotEqual(result['status'], 'RETIRED')
        self.assertIn('stop request failed', result['stop_attempt']['error'])

    def test_replacement_between_guard_and_short_lock_prevents_command(self):
        command = mock.Mock(); lock = NS(hold=lambda: contextlib.nullcontext())
        result = d.request_stop(OWNER, lock,
            probe=lambda owner: dict(state='REPLACEMENT_OR_OTHER_MEMBERS'), command=command)
        self.assertFalse(result['requested']); command.assert_not_called()

    def test_persistent_probe_failure_cannot_skip3310_intent_or3600_result(self):
        now = [3309.0]; stop = mock.Mock(side_effect=RuntimeError('fresh stop identity refused'))
        def sleep(value): now[0] += 150
        result = d.supervise(adoption=self.adopted,
            get_clock=lambda: dict(boot_id='boot', monotonic_s=now[0]),
            probe=mock.Mock(side_effect=OSError('descriptive probe failed')), stop=stop,
            sleep=sleep, emit=lambda value: None, maximum_polls=5)
        self.assertGreaterEqual(stop.call_count, 1)
        self.assertEqual(result['status'], 'ABSENCE_UNPROVEN_AT_CEILING')
        self.assertLessEqual(now[0], 3759)

    def test_pre_request_probe_recovers_but_submitted_stop_is_not_repeated(self):
        now = [3310]; stopped = []
        def stop(owner):
            if not stopped:
                stopped.append('guard-refused'); raise OSError('pre-request unit probe')
            stopped.append('submitted'); return dict(requested=True)
        def probe(owner):
            return dict(state='ABSENT' if len(stopped) > 1 else 'SAME')
        result = d.supervise(adoption=self.adopted,
            get_clock=lambda: dict(boot_id='boot', monotonic_s=now[0]), probe=probe, stop=stop,
            sleep=lambda value: now.__setitem__(0, now[0]+value), emit=lambda value: None, maximum_polls=5)
        self.assertEqual(stopped, ['guard-refused', 'submitted'])
        self.assertEqual(result['status'], 'RETIRED')
        self.assertEqual(len(result['guard_refusals']), 1)

    def test_requested_start_without_lineage_uses_known_origin_but_never_guesses_PID(self):
        now = [3309.0]; probe, stop = mock.Mock(), mock.Mock()
        result = d.supervise(adoption=lambda: None,
            requested=lambda: dict(start=dict(boot_id='boot', monotonic_s=0)),
            get_clock=lambda: dict(boot_id='boot', monotonic_s=now[0]), probe=probe, stop=stop,
            sleep=lambda value: now.__setitem__(0, now[0]+value), emit=lambda value: None, maximum_polls=4)
        self.assertEqual(result['status'], 'UNADOPTED_START_MANUAL')
        self.assertEqual(result['observed_monotonic_s'], 3310)
        probe.assert_not_called(); stop.assert_not_called()

    def test_terminal_reporting_failure_does_not_extend_ceiling_or_reissue_stop(self):
        stop = mock.Mock(); emit = mock.Mock(side_effect=OSError('receipt filesystem'))
        with contextlib.redirect_stdout(io.StringIO()):
            result = d.supervise(adoption=self.adopted,
                get_clock=lambda: dict(boot_id='boot', monotonic_s=3600),
                probe=lambda owner: dict(state='SAME'), stop=stop,
                sleep=lambda value: self.fail('No sleep beyond ceiling'), emit=emit)
        self.assertEqual(result['status'], 'CEILING_BREACH')
        self.assertIn('publication_error', result); self.assertEqual(stop.call_count, 1)

    def test_same_old_invocation_stale_PID_or_draining_cgroup_remains_pending(self):
        for pid, occupied in ((str(OWNER['pid']), False), ('0', True)):
            unit = dict(MainPID=pid, InvocationID=OWNER['invocation_id'], ControlGroup=OWNER['cgroup'])
            with self.subTest(pid=pid), mock.patch.object(d, 'show', return_value=unit), \
                    mock.patch.object(d, 'process_start', return_value=None), \
                    mock.patch.object(Path, 'exists', return_value=occupied), \
                    mock.patch.object(Path, 'read_text', return_value='700\n'):
                self.assertEqual(d.classify(OWNER)['state'], 'RETIRING')
        foreign = dict(MainPID='999', InvocationID='b'*32, ControlGroup=OWNER['cgroup'])
        with mock.patch.object(d, 'show', return_value=foreign), \
                mock.patch.object(d, 'process_start', return_value=None), \
                mock.patch.object(Path, 'exists', return_value=False):
            self.assertEqual(d.classify(OWNER)['state'], 'REPLACEMENT_OR_OTHER_MEMBERS')

    def test_retiring_snapshot_can_finish_with_strict_absence_without_early_manual_exit(self):
        now = [3500]; observations = iter([dict(state='RETIRING'), dict(state='ABSENT')])
        result = d.supervise(adoption=self.adopted,
            get_clock=lambda: dict(boot_id='boot', monotonic_s=now[0]),
            probe=lambda owner: next(observations), stop=lambda owner: dict(requested=False),
            sleep=lambda value: now.__setitem__(0, now[0]+value), emit=lambda value: None)
        self.assertEqual(result['status'], 'RETIRED'); self.assertEqual(result['absence']['elapsed_s'], 3501)


class ReceiptContracts(unittest.TestCase):
    def test_real_metrics_three_key_identity_accepts_first_healthy_evidence(self):
        from Robotron.tools import inference_worker_affinity as metrics
        identity = dict(process_id=101, instance_monotonic_ns=10, epoch=0, epoch_reason='startup', enabled=True)
        optimizer = dict(identity, available=True, unclassified_started_total=0, prior_epoch_outcomes_total=0,
            total=dict(attempts_started=1, outcomes_recorded=1, applied=1, amp_skipped=0, unavailable=0))
        replay = dict(identity, available=True, accepted_total=0, accepted_learner_total=0,
            accepted_by_source_total=dict(dqn=0, epsilon=0, expert=0, eval=0, unattributed=0))
        exposure = dict(optimizer=optimizer, replay=replay)
        csv = dict(replay_dropped=0, batch_size=4096, replay_sample_cap=8)
        observer = dict(before_resume_api=dict(host_pipeline=dict(learning_exposure=exposure)))
        local = c.live_api_plan(NS(metrics=metrics), observer, csv)
        row = dict(client_count=192, training_enabled=True, measurement_active=False, epsilon=.1,
            expert_ratio=.1, lr=2.5e-5, memory_buffer_size=6000000, loss=1., pipeline_read_error=False,
            bank_persistence_read_error=False, ts=1., observed_unix_s=1., pipeline_errors={}, csv=csv,
            training_steps=1, optimized_samples=4096, frame_count=2, learner_frame_count=1,
            graphs=dict(ready=True, capture_count=128, validation_replay_count=640, postload_validations=1,
                runtime_capture_count=0, fallback_count=0, fatal_error=False),
            native=dict(enabled=True, available=True, completed_count=1, success_count=1, fallback_count=0, error_count=0),
            bank=dict(backend='stream', stream_enabled=True, write_failures=0, last_error=None, output_errors=0),
            exposure=exposure)
        self.assertEqual(set(local['exposure_identity']['optimizer']), {'process_id', 'instance_monotonic_ns', 'epoch'})
        self.assertEqual(metrics.api_issues(row, local), [])

    def test_DRAFT_false_authorization_and_mismatched_phase_fail_before_arm(self):
        activation = dict(phase_id='planned-kl')
        valid = dict(activation_authorized=True, status=d.FINAL_CORE_STATUS,
            mode='activate_kl', phase_id='planned-kl')
        d.validate_authorization(valid, activation)
        for changes in (dict(activation_authorized=False), dict(status='DRAFT'),
                dict(phase_id='other'), dict(mode='return_ce')):
            with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, 'authorized'):
                d.validate_authorization(dict(valid, **changes), activation)

    def test_default_PLAN_does_not_load_helpers_or_read_files(self):
        with mock.patch.object(c, 'load', side_effect=AssertionError('import')), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('read')), \
                mock.patch.object(subprocess, 'run', side_effect=AssertionError('runtime')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(c.main([]), 0)
            self.assertEqual(d.main([]), 0)

    def test_first_LATCH_fsync_straddling3240_is_retained_but_cannot_request(self):
        stored = []
        event = dict(sequence=3, state='LATCH', observed_monotonic_s=3239.9)
        def publish(path, value): stored.append((path.name, copy.deepcopy(value))); return dict(path=str(path))
        with self.assertRaisesRegex(RuntimeError, 'after3240'):
            c.durable_event(event, dict(start_request=dict(boot_id='boot', monotonic_s=0)), Path('/unused'),
                publish=publish, get_clock=lambda: dict(boot_id='boot', monotonic_s=3240.01))
        self.assertEqual(stored[0][1], event)
        self.assertEqual(stored[1][1]['elapsed_s'], 3240.01)
        self.assertEqual(event['state'], 'LATCH')

    def test_actual_completed_fsync_at3240_is_allowed_without_reanchor(self):
        result = c.durable_event(dict(sequence=0, state='LATCH', observed_monotonic_s=3290),
            dict(start_request=dict(boot_id='boot', monotonic_s=50)), Path('/unused'),
            publish=lambda path, value: dict(path=str(path)),
            get_clock=lambda: dict(boot_id='boot', monotonic_s=3290))
        self.assertTrue(result['event']['path'].endswith('observation-0000.json'))

    def test_replacement_deadline_receipt_cannot_authorize_CE_start(self):
        report = dict(status='RETIRED', adopted=dict(owner=dict(OWNER, pid=102)),
            absence=dict(elapsed_s=3500, proof=dict(state='ABSENT')))
        fake = NS(pin=lambda path: ({}, b''), read_pin=lambda pin: report)
        with self.assertRaisesRegex(RuntimeError, 'retirement proof'):
            c.require_deadline_retirement(fake, Path('/unused'), OWNER)

    def test_total_journal_reserves_metadata_and_preserves_first_write_failure(self):
        write = mock.Mock(side_effect=OSError('first disk failure'))
        journal = c.ReceiptJournal(publish=write, get_clock=lambda: dict(boot_id='boot', monotonic_s=2),
            root=Path('/unused'), observer=dict(start_request=dict(boot_id='boot', monotonic_s=0)))
        event = dict(sequence=0, state='CONTINUE', observed_monotonic_s=1)
        with self.assertRaisesRegex(OSError, 'first disk'): journal.emit(event)
        with self.assertRaisesRegex(RuntimeError, 'cannot be retried'): journal.emit(dict(event, sequence=1))
        self.assertEqual(write.call_count, 1); self.assertIn('first disk', journal.failure)
        journal = c.ReceiptJournal(publish=mock.Mock(), get_clock=mock.Mock(), root=Path('/unused'),
            observer=dict(start_request=dict(boot_id='boot', monotonic_s=0)))
        journal.used = c.JOURNAL_BYTES - 4096
        with self.assertRaisesRegex(RuntimeError, '32MiB'): journal.emit(event)
        journal.publish.assert_not_called()

    def test_raw_optional_NaN_is_retained_only_for_explicit_API_artifacts(self):
        strict = mock.Mock(return_value='strict'); raw = mock.Mock(return_value='raw')
        base = NS(publish=strict); deadline = NS(publish=raw)
        trial = dict(output_directory='/trial', return_intent=dict(output_directory='/return'))
        c.raw_api_publication(base, deadline, trial, dict(output_directory='/activation'))
        value = dict(grad_norm=float('nan'))
        self.assertEqual(base.publish(Path('/trial/early/snapshot/trigger-API.json'), value), 'raw')
        self.assertIs(raw.call_args.args[1], value)
        self.assertEqual(base.publish(Path('/trial/numeric-proof.json'), value), 'strict')
        self.assertEqual(base.publish(Path('/foreign/trigger-API.json'), value), 'strict')


class RetiredHandoffContracts(unittest.TestCase):
    def pair(self):
        from Robotron.tools.parallel_state_fill_trial import LiveHost
        known = dict(pid=OWNER['pid'], identity=dict(pid=OWNER['pid'], starttime_ticks=OWNER['starttime_ticks']),
            cgroup=OWNER['cgroup'])
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        lease_path = Path(directory.name) / 'lease'; lease_path.write_bytes(b'')
        fd = os.open(lease_path, os.O_RDONLY); self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = NS(absence=mock.Mock(), retired_owner=copy.deepcopy(OWNER), lease_path=lease_path,
            retirement_candidate=copy.deepcopy(OWNER), settings=object(), lease_fd=fd,
            host=NS(known_trainer=known, retired_trainers=[known['identity']], paused=[dict(pid=1), dict(pid=2)],
                metric_host=NS(configure_logs=mock.Mock())))
        host = LiveHost('robotron-managed-test-trainer.service', 'robotron-managed-test-fleet.service')
        self.assertIsNone(host.metric_host)  # genuine constructor; adopt_initial does NOT initialize it
        host.adopt_initial = mock.Mock(wraps=host.adopt_initial)
        host.begin_transition_logs = mock.Mock()
        following = NS(host=host, lease_fd=None, absence=mock.Mock(),
            job=dict(before=dict(bindings=dict(logs=[], worker=dict(trainer=copy.deepcopy(known['identity'])),
                fleet_cgroup='/held/fleet'), trainer=dict(ControlGroup=OWNER['cgroup']), trainer_stdout={})))
        return previous, following

    def test_same_process_handoff_transfers_original_lease_and_all_pending_actor_undo(self):
        previous, following = self.pair()
        original_fd = previous.lease_fd
        c.inherit_retirement(previous, following, OWNER, lease_path=previous.lease_path)
        self.assertEqual(following.lease_fd, original_fd); self.assertIsNone(previous.lease_fd)
        self.assertEqual(following.host.paused, [dict(pid=1), dict(pid=2)])
        self.assertEqual(previous.host.paused, [])
        self.assertIs(following.settings, previous.settings)
        self.assertIs(following.host.metric_host, previous.host.metric_host)
        following.absence.assert_called_once()

    def test_unregistered_or_mismatched_retirement_cannot_be_adopted(self):
        for kind in ('unknown', 'unregistered', 'mismatch'):
            with self.subTest(kind=kind):
                previous, following = self.pair()
                original_fd = previous.lease_fd
                if kind == 'unknown': previous.host.known_trainer = None
                elif kind == 'unregistered': previous.host.retired_trainers = []
                else: previous.retired_owner = dict(OWNER, pid=999)
                with self.assertRaisesRegex(RuntimeError, 'registered KL retirement'):
                    c.inherit_retirement(previous, following, OWNER, lease_path=previous.lease_path)
                self.assertEqual(previous.lease_fd, original_fd)
                following.host.adopt_initial.assert_not_called()

    def test_partial_new_host_failure_leaves_original_actor_undo_owned(self):
        previous, following = self.pair()
        original_fd = previous.lease_fd
        following.host.adopt_initial.side_effect = OSError('new host construction')
        with self.assertRaises(OSError): c.inherit_retirement(previous, following, OWNER, lease_path=previous.lease_path)
        self.assertEqual(previous.host.paused, [dict(pid=1), dict(pid=2)])
        self.assertEqual(previous.lease_fd, original_fd)


class ReturnOrderingContracts(unittest.TestCase):
    def runtime(self, *, fail=None):
        order = []
        def call(name, result=None):
            def invoke(*args, **kwargs):
                order.append(name)
                if name == fail: raise RuntimeError('injected ' + name)
                return result
            return invoke
        runtime = NS(absence=call('absence'), post_stop_ending=call('candidateCPU', {}),
            stopped_checkpoint=call('latestCPU', {}), expected_sources=lambda phase: {},
            banks=NS(stopped_state=call('banks', {}), assert_unchanged=call('headers')),
            job=dict(bank_spec={}), start_phase=call('CEstart', dict(pid=303)),
            ready_transport=lambda phase, banks, actors: call('healthy192' if actors else 'zeroReady', {})(),
            raw_api=lambda: dict(client_count=0), startup_snapshot=call('startupCPU', {}),
            inspect=call('inspect', {}), output=Path('/unused'), start_request=None,
            host=NS(paused=[]), cpu_attempts={})
        base = NS(publish=lambda path, value: {},
            resume_all=lambda host: call('resume', dict(failures=[]))())
        adapter = NS(RESULT_SCHEMA='result', zero_replay=lambda raw, pid: None)
        return runtime, base, adapter, order

    def test_stronger_candidate_and_latest_CPU_complete_before_explicit_CE_start(self):
        runtime, base, adapter, order = self.runtime()
        result = c.return_after_retirement(adapter, base, runtime, OWNER)
        self.assertEqual(result['status'], 'READY')
        self.assertLess(order.index('candidateCPU'), order.index('latestCPU'))
        self.assertLess(order.index('latestCPU'), order.index('CEstart'))
        self.assertLess(order.index('startupCPU'), order.index('resume'))

    def test_candidate_CPU_failure_or_stale_latest_never_starts_CE_and_still_undoes(self):
        for name in ('candidateCPU', 'latestCPU'):
            with self.subTest(name=name):
                runtime, base, adapter, order = self.runtime(fail=name)
                result = c.return_after_retirement(adapter, base, runtime, OWNER)
                self.assertEqual(result['status'], 'FAILED')
                self.assertNotIn('CEstart', order)
                self.assertEqual(order[-1], 'resume')


class RegisteredCPUContracts(unittest.TestCase):
    def fixture(self, root):
        entry = root / '777'; entry.mkdir()
        executable = root / 'python'; executable.write_bytes(b'fake executable NEVER RUN')
        game = root / 'game'; game.mkdir()
        (entry / 'cwd').symlink_to(game); (entry / 'exe').symlink_to(executable)
        command = [str(executable), '-Xgil=0', '-I', '-B', '-u', '/strict7d.py',
            '--execute', '--job', '/job.json', '--expected-job-sha256', 'f'*64]
        argv = [value.encode() for value in command] + [b'']
        (entry / 'cmdline').write_bytes(b'\0'.join(argv))
        (entry / 'cgroup').write_text('0::/cpu/early.service\n')
        (entry / 'status').write_text('Uid:\t' + '\t'.join([str(os.getuid())]*4) + '\n')
        (entry / 'stat').write_text('fake stat parsed by injected pure parser')
        registration = dict(command=command, argv=['systemd-run', 'other'], unit='early.service',
            owner=None, job=dict(path='/job.json', sha256='f'*64))
        runtime = NS(job=dict(game_root=str(game)), metrics=NS(identity=NS(
            stat_fields=lambda value: dict(starttime_ticks=123))))
        return entry, argv, registration, runtime

    def test_only_exact_registered_job_argv_and_retained_unit_may_bypass_scanner(self):
        with tempfile.TemporaryDirectory() as temp:
            entry, argv, registration, runtime = self.fixture(Path(temp)); adopt = mock.Mock()
            show = NS(stdout='MainPID=777\nNRestarts=0\nInvocationID='+'b'*32+'\nControlGroup=/cpu/early.service\n')
            with mock.patch.object(subprocess, 'run', return_value=show):
                self.assertTrue(c.owned_cpu(registration, entry, argv, runtime, adopt=adopt))
            self.assertEqual(adopt.call_args.args[0]['starttime_ticks'], 123)
            bad = list(argv); bad[-2] = b'wrong-job-sha'
            self.assertFalse(c.owned_cpu(registration, entry, bad, runtime, adopt=mock.Mock()))

    def test_matching_basename_with_foreign_unit_or_reused_PID_is_fatal(self):
        with tempfile.TemporaryDirectory() as temp:
            entry, argv, registration, runtime = self.fixture(Path(temp))
            show = NS(stdout='MainPID=999\nNRestarts=0\nInvocationID='+'b'*32+'\nControlGroup=/cpu/early.service\n')
            with mock.patch.object(subprocess, 'run', return_value=show):
                with self.assertRaisesRegex(RuntimeError, 'CPU unit/argv'):
                    c.owned_cpu(registration, entry, argv, runtime, adopt=mock.Mock())
            show.stdout = 'MainPID=777\nNRestarts=0\nInvocationID='+'b'*32+'\nControlGroup=/cpu/early.service\n'
            runtime.metrics.identity.stat_fields = mock.Mock(side_effect=[dict(starttime_ticks=123), dict(starttime_ticks=124)])
            with mock.patch.object(subprocess, 'run', return_value=show):
                with self.assertRaisesRegex(RuntimeError, 'PID changed'):
                    c.owned_cpu(registration, entry, argv, runtime, adopt=mock.Mock())

    def test_registered_CPU_exit_race_uses_original_terminal_or_sealed_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            entry, argv, registration, runtime = self.fixture(Path(temp))
            owner = dict(pid=777, starttime_ticks=123, unit='early.service',
                invocation_id='b'*32, cgroup='/cpu/early.service')
            registration['owner'] = owner; (entry/'stat').unlink()
            text = 'LoadState=loaded\nMainPID=0\nExecMainPID=777\nNRestarts=0\nInvocationID='+'b'*32+\
                '\nControlGroup=\nSubState=exited\nExecMainCode=1\nExecMainStatus=0\n'
            with mock.patch.object(subprocess, 'run', return_value=NS(stdout=text)):
                self.assertTrue(c.owned_cpu(registration, entry, argv, runtime, adopt=mock.Mock()))
            registration['terminal_archive'] = dict(path='/archive.json')
            original = dict(original_owner=owner, original_pid=777, original_invocation='b'*32,
                original_nrestarts=0, original_exec_code=1)
            with mock.patch.object(subprocess, 'run', return_value=NS(stdout='LoadState=not-found\n')):
                self.assertTrue(c.owned_cpu(registration, entry, argv, runtime, adopt=mock.Mock(),
                    read_terminal=lambda pin: original))
                registration['owner'] = None
                with self.assertRaisesRegex(RuntimeError, 'previously observed'):
                    c.owned_cpu(registration, entry, argv, runtime, adopt=mock.Mock(), read_terminal=lambda pin: original)


class BoundedCopyContracts(unittest.TestCase):
    def fixture(self, root):
        game = root / 'game'; package = game / 'Scripts/dqn'; package.mkdir(parents=True)
        model = game / 'models_dqn'; model.mkdir()
        trial_root = game / 'logs/trial'; trial_root.mkdir(parents=True)
        activation_root = game / 'logs/activation'; activation_root.mkdir()
        return_root = game / 'logs/return'; return_root.mkdir()
        def fingerprint(path, limit=None): return d.pin(path, limit or d.LIMIT)[0]
        def model_only(source, target):
            size = Path(source).stat().st_size
            c.require(200 << 20 <= size <= 400 << 20, 'inherited checkpoint minimum')
            raise AssertionError('No huge checkpoint body needed for this contract')
        def sync(path):
            fd = os.open(path, os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        base = NS(exclusive_copy=model_only, fingerprint=fingerprint, identity=d.identity,
            MAX_SOURCE=4<<20, fsync_directory=sync)
        trial = dict(output_directory=str(trial_root), return_intent=dict(output_directory=str(return_root)))
        activation = dict(output_directory=str(activation_root), game_root=str(game), model_dir=str(model))
        c.bounded_copy_dispatch(base, trial, activation)
        return base, package, model, trial_root

    def test_real_tiny_source_and_request_JSON_keep_owned_nooverwrite_independent444_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            base, package, model, output = self.fixture(Path(temp))
            for source in (package/'agent.py', model/'managed_save.request.json.completed'):
                source.write_bytes(b'{}\n'); source.chmod(0o644)
                target = output/(source.name+'.json')
                before, copied = base.exclusive_copy(source, target)
                self.assertEqual(copied['sha256'], before['sha256'])
                self.assertEqual(copied['identity']['mode'], '0o444')
                self.assertNotEqual(copied['identity']['inode'], before['identity']['inode'])
                self.assertEqual(source.stat().st_mode & 0o777, 0o644)
                with self.assertRaises(FileExistsError): base.exclusive_copy(source, target)

    def test_truncated_PT_never_enters_small_metadata_path(self):
        with tempfile.TemporaryDirectory() as temp:
            base, package, model, output = self.fixture(Path(temp))
            source = model/'truncated.pt'; source.write_bytes(b'tiny invalid model')
            with self.assertRaisesRegex(RuntimeError, 'checkpoint minimum'):
                base.exclusive_copy(source, output/'copy.pt')
            self.assertFalse((output/'copy.pt').exists())

    def test_unknown_or_symlink_archive_and_changed_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base, package, model, output = self.fixture(Path(temp))
            unknown = model/'unregistered.json'; unknown.write_bytes(b'{}')
            with self.assertRaisesRegex(RuntimeError, 'Unregistered'):
                base.exclusive_copy(unknown, output/'unknown.json')
            source = package/'agent.py'; source.write_bytes(b'held source')
            outside = Path(temp)/'outside'; outside.mkdir(); (output/'escape').symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError, 'escapes'):
                base.exclusive_copy(source, output/'escape/copy.py')
            # Genuine source mutation after copy/fsync, before final path check.
            base.fsync_directory = lambda path: source.write_bytes(b'changed source bytes')
            with self.assertRaisesRegex(RuntimeError, 'path changed'):
                base.exclusive_copy(source, output/'changed.py')


if __name__ == '__main__':
    unittest.main()
