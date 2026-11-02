"""CPU/std-lib mocks only: no real services, signals, trainers, or GPUs."""
import copy
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from . import restore_serial_after_parallel_trial as restore
from .test_inference_worker_affinity import FakeHost as MetricFixture


class CleanupHost(MetricFixture):
    trainer_unit = restore.TRAINER_UNIT
    def __init__(self, directory, changes):
        super().__init__()
        self.pid = restore.ARETURN[0]
        self.changes = changes
        self.directory = directory
        self.events = []
        self.paused = []
        self.pause_issues = []
        self.metric_host = types.SimpleNamespace(configure_logs=lambda _: None)
        self.live = True
        self.hung = self.missing_bank = self.partial_pause = self.unknown_new_pid = False
        self.interrupt_pause = False
        self.stdout = directory / 'trainer.log'
        self.stdout.write_text('Loaded model from: ' + str(restore.GAME / 'models_dqn/robotron_dqn_latest.pt') + '\n')

    def verify(self, plan, flag):
        self.events.append('verify')
        for path, digest in plan['initial']['bindings']['source_hashes'].items():
            restore.require(restore.metrics.file_digest(path) == digest, 'mock source mismatch')
        return copy.deepcopy(plan['initial'])

    def no_sidecars(self):
        pass

    def unit(self, name):
        return dict(MainPID=str(self.pid) if self.live else '0')

    def begin_transition_logs(self, *args):
        self.events.append('arm')

    def pause(self, plan):
        self.events.append('pause')
        self.paused.append(1)
        if self.interrupt_pause:
            raise restore.metrics.TrialInterrupted('mock signal during partial pause')
        if self.partial_pause:
            raise OSError('mock reused actor')
        self.paused.append(2)

    def resume(self):
        self.events.append('resume')
        self.paused = []

    def stop(self, before):
        self.events.append('stop')
        restore.require(self.live, 'mock unknown stop')
        restore.require(not self.hung, 'old trainer remains alive')
        for change in self.changes:
            restore.require(Path(change['path']).read_bytes() == bytes.fromhex(change['before']),
                            'disk changed before old imported trainer stopped')
        self.live = False

    def assert_retired_absent(self):
        restore.require(not self.live, 'mock old trainer alive')

    def start(self):
        self.events.append('start')
        self.assert_retired_absent()
        for change in self.changes:
            restore.require(Path(change['path']).read_bytes() == bytes.fromhex(change['after']), 'mixed source start')
        self.pid += 1
        self.live = True

    def ready(self, plan, flag, *, actors=False):
        self.events.append('ready_actors' if actors else 'ready_loaded')
        restore.require(not self.unknown_new_pid, 'unknown externally replaced startup PID')
        return dict(bindings=dict(worker=dict(trainer=dict(pid=self.pid, starttime_ticks=999)), logs={}))

    def bank_load_proof(self, loaded):
        self.events.append('banks')
        restore.require(self.paused and not self.missing_bank, 'missing positive bank proof')
        payload = self.stdout.read_bytes()
        return dict(stdout=dict(path=str(self.stdout)), start_byte=0, end_byte=len(payload),
                    sha256=restore.sha(payload), counts={bank: dict(episodes=192, transitions=1) for bank in ('HOF', 'EPHOF')})

    def transition_log_events(self):
        self.events.append('fault_scan')
        return []


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.changes = []
        for index in range(3):
            path = self.directory / f'source{index}.py'
            before, after = f'patched{index}'.encode(), f'base{index}'.encode()
            path.write_bytes(before);path.chmod(0o640)
            self.changes.append(dict(path=str(path), before=before.hex(), after=after.hex(),
                                     before_sha256=restore.sha(before), after_sha256=restore.sha(after), mode=0o640))
        self.host = CleanupHost(self.directory, self.changes)
        self.plan = dict(output_directory=str(self.directory / 'output'), changes=self.changes,
                         original_dropin=dict(content_base64=None),
                         initial=dict(bindings=dict(source_hashes={c['path']: c['before_sha256'] for c in self.changes}, logs={}),
                                      trainer_stdout={}),
                         insurance=dict(clocks={key: 0 for key in restore.metrics.CLOCKS}))

    def execute(self):
        with patch.object(restore, 'assert_static'):
            return restore.execute(self.host, self.plan)

    def assert_sources(self, role):
        for change in self.changes:
            self.assertEqual(Path(change['path']).read_bytes(), bytes.fromhex(change[role]))
            self.assertEqual(Path(change['path']).stat().st_mode & 0o777, change['mode'])

    def test_success_stops_old_before_source_write_and_checks_banks_before_resume(self):
        result = self.execute()
        self.assertEqual(result['state'], 'complete')
        self.assertFalse(result['manual_recovery_required'])
        self.assert_sources('after')
        self.assertEqual(self.host.events.count('stop'), 1)
        self.assertEqual(self.host.events.count('start'), 1)
        self.assertLess(self.host.events.index('stop'), self.host.events.index('start'))
        self.assertLess(self.host.events.index('banks'), self.host.events.index('resume'))
        self.assertLess(self.host.events.index('fault_scan'), self.host.events.index('resume'))
        self.assertFalse(self.host.paused)

    def test_hung_old_trainer_does_not_restore_or_start(self):
        self.host.hung = True
        result = self.execute()
        self.assertTrue(result['manual_recovery_required'])
        self.assertNotIn('start', self.host.events)
        self.assert_sources('before')
        self.assertFalse(self.host.paused)

    def test_partial_source_write_reconciles_complete_before_set_and_never_starts(self):
        atomic = restore.atomic_bytes
        failed = False
        def fail_second_source(path, payload, mode):
            nonlocal failed
            if path == Path(self.changes[1]['path']) and payload == bytes.fromhex(self.changes[1]['after']) and not failed:
                failed = True
                raise OSError('mock second source replace failure')
            return atomic(path, payload, mode)
        with patch.object(restore, 'atomic_bytes', side_effect=fail_second_source):
            result = self.execute()
        self.assertEqual(result['source_group'], 'before_reconciled')
        self.assertNotIn('start', self.host.events)
        self.assert_sources('before')
        self.assertTrue(result['manual_recovery_required'])

    def test_partial_pause_and_signal_always_resume_without_stopping(self):
        for attribute in ('partial_pause', 'interrupt_pause'):
            with self.subTest(attribute=attribute):
                self.plan['output_directory'] = str(self.directory / attribute)
                self.host = CleanupHost(self.directory, self.changes)
                setattr(self.host, attribute, True)
                result = self.execute()
                self.assertEqual(result['state'], 'failed')
                self.assertFalse(self.host.paused)
                self.assertNotIn('stop', self.host.events)
                self.assert_sources('before')

    def test_missing_banks_or_unknown_new_pid_is_manual_without_second_stop(self):
        for attribute in ('missing_bank', 'unknown_new_pid'):
            with self.subTest(attribute=attribute):
                for change in self.changes:
                    Path(change['path']).write_bytes(bytes.fromhex(change['before']))
                self.plan['output_directory'] = str(self.directory / attribute)
                self.host = CleanupHost(self.directory, self.changes)
                setattr(self.host, attribute, True)
                result = self.execute()
                self.assertEqual(result['state'], 'failed')
                self.assertTrue(result['manual_recovery_required'])
                self.assertEqual(self.host.events.count('stop'), 1)
                self.assertEqual(self.host.events.count('start'), 1)
                self.assertFalse(self.host.paused)

    def test_source_lock_refuses_changed_input_before_any_pause(self):
        Path(self.changes[1]['path']).write_bytes(b'user edit')
        with self.assertRaises(restore.metrics.GuardFailure):
            self.execute()
        self.assertNotIn('pause', self.host.events)

    def test_default_cli_does_not_execute_or_create_output(self):
        args = ['--insurance-checkpoint', 'model', '--insurance-verification', 'receipt',
                '--insurance-verification-sha256', 'abc', '--output-dir', str(self.directory / 'dryrun')]
        with patch.object(restore, 'prepare', return_value=copy.deepcopy(self.plan)), \
                patch.object(restore.trial, 'LiveHost'), patch.object(restore, 'execute') as execute, \
                patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(restore.main(args), 0)
            execute.assert_not_called()
        self.assertFalse((self.directory / 'dryrun').exists())

    def test_insurance_requires_exact_immutable_cpu_receipt_and_final_clocks(self):
        checkpoint, verification = self.directory / 'insurance.pt', self.directory / 'cpu.json'
        checkpoint.write_bytes(b'immutable CPU-verified tensor bytes');checkpoint.chmod(0o444)
        clocks = {key: 100 for key in restore.metrics.CLOCKS}
        clocks.update(engine_version=28, state_size=11128, frame_stack=4, epsilon=.1, expert_ratio=.1)
        receipt = dict(status='PASS', path=str(checkpoint), sha256=restore.metrics.file_digest(checkpoint),
                       bytes=checkpoint.stat().st_size, cuda_initialized=False, visible_cuda_devices=0,
                       finite=dict(tensors=443, tensor_elements=123), adam_state_count=81,
                       adam_step_min=10., adam_step_max=10., clocks=clocks,
                       grad_scaler=dict(scale=1024., growth_factor=2., backoff_factor=.5,
                                        growth_interval=2000, _growth_tracker=1))
        def write_receipt():
            verification.chmod(0o644) if verification.exists() else None
            verification.write_text(json.dumps(receipt));verification.chmod(0o444)
            return restore.metrics.file_digest(verification)
        digest = write_receipt()
        minimum = {key: 99 for key in restore.metrics.CLOCKS}
        self.assertEqual(restore.verified_insurance(checkpoint, verification, digest, minimum)['clocks'], clocks)
        with self.assertRaises(restore.metrics.GuardFailure):
            restore.verified_insurance(checkpoint, verification, 'wrong hash', minimum)
        with self.assertRaises(restore.metrics.GuardFailure):
            restore.verified_insurance(checkpoint, verification, digest, {key: 101 for key in minimum})
        receipt['cuda_initialized'] = True
        digest = write_receipt()
        with self.assertRaises(restore.metrics.GuardFailure):
            restore.verified_insurance(checkpoint, verification, digest, minimum)
        receipt['cuda_initialized'] = False
        digest = write_receipt();checkpoint.chmod(0o644)
        with self.assertRaises(restore.metrics.GuardFailure):
            restore.verified_insurance(checkpoint, verification, digest, minimum)

    def test_trial_must_be_complete_rejected_clean_and_controller_absent(self):
        directory = self.directory / 'trial';directory.mkdir()
        pre = dict(settle_s=90)
        prebytes = json.dumps(pre).encode();(directory / 'precommit.json').write_bytes(prebytes)
        rows, results, transitions = [], [], []
        for index, phase in enumerate(('A', 'B', 'Areturn')):
            first = dict(phase=phase, stage='primary', observed_monotonic_s=index * 1000 + 90,
                         optimized_samples=100 * 4096, client_count=192, issues=[],
                         exposure=dict(optimizer=dict(total=dict(applied=100, unavailable=0)),
                                       replay=dict(accepted_learner_total=100)))
            last = copy.deepcopy(first);last['observed_monotonic_s'] += 300
            last['optimized_samples'] += 100 * 4096
            last['exposure']['optimizer']['total']['applied'] += 100
            last['exposure']['replay']['accepted_learner_total'] += 100
            rows.extend((first, last))
            results.append(dict(phase=phase, operationally_valid=True, duration_s=300, observations=2,
                                start=first, end=last, optimizer_delta=dict(applied=100, unavailable=0),
                                logical_samples_per_s=100 * 4096 / 300,
                                applied_admission_samples_per_s=100 * 4096 / 300,
                                accepted_learner_per_s=100 / 300))
            transitions.append(dict(phase=phase, state='ready', ready_monotonic_s=index * 1000))
        (directory / 'observations.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        status = dict(precommit_sha256=restore.sha(prebytes), state='complete', results=results,
                      transitions=transitions, decision=dict(outcome='rejected', automatic_promotion=False),
                      recovery=dict(errors=[], manual_recovery_required=False, original_dropin_restored=True,
                                    paused_actor_identity_issues=[]))
        host = types.SimpleNamespace(unit=lambda _: dict(ActiveState='inactive', MainPID='0'))
        def check():
            (directory / 'status.json').write_text(json.dumps(status))
            return restore.terminal_evidence(directory, host)
        with patch.object(restore, 'TRIAL', directory), patch.object(restore, 'process_present', return_value=False):
            self.assertEqual(check()[2]['observations'], 6)
            for field, value in (('state', 'running'), ('state', 'failed')):
                status[field] = value
                with self.assertRaises(restore.metrics.GuardFailure):check()
            status['state'] = 'complete';status['recovery']['errors'] = ['bank failure']
            with self.assertRaises(restore.metrics.GuardFailure):check()
            status['recovery']['errors'] = []
            with patch.object(restore, 'process_present', return_value=True):
                with self.assertRaises(restore.metrics.GuardFailure):check()
            host.unit = lambda _: dict(ActiveState='active', MainPID='123')
            with self.assertRaises(restore.metrics.GuardFailure):check()


if __name__ == '__main__':
    unittest.main()
