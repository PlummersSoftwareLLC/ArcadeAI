"""PREPARED ONLY: CPU/stdlib mocks; run after root releases frozen quality.

No actual affinity, process discovery, API, service, numerical library or GPU
is used by these tests. Temporary files belong exclusively to each test.
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import cpu_reservation_trial as trial
from Robotron.tools import inference_worker_affinity as baseline
from Robotron.tools.test_inference_worker_affinity import FakeHost


class MemoryJournal:
    def __init__(self, *args, **kwargs):
        self.rows, self.errors = [], []
        self.failed = False
        self.fail_kind = None
        self.fail_intent_number = None
        self.intents = 0

    def record(self, kind, **fields):
        if kind == 'intent':
            self.intents += 1
        if self.failed or kind == self.fail_kind or self.intents == self.fail_intent_number:
            self.failed = True
            self.errors.append('injected journal/fsync failure')
            raise OSError(self.errors[-1])
        self.rows.append(copy.deepcopy(dict(kind=kind, **fields)))

    def best(self, kind, **fields):
        try:
            self.record(kind, **fields)
            return True
        except OSError:
            return False

    def close(self):
        pass


class FakeSystem:
    """Exact logical identities and masks, never real PIDs/TIDs or syscalls."""
    def __init__(self):
        self.host = FakeHost(treatment_rate=18)
        # Reservation phase_start records the real Host's armed log offsets.
        # The shared older single-thread fixture does not use that attribute.
        self.host.log_offsets = {}
        actor = dict(pid=201, starttime_ticks=44, client_slot=0)
        self.host.binding['actors'] = [actor]
        self.owners = [dict(kind='trainer', identity=copy.deepcopy(self.host.binding['worker']['trainer'])),
                       dict(kind='mame', identity=copy.deepcopy(actor))]
        self.identities = {owner['identity']['pid']: copy.deepcopy(owner['identity']) for owner in self.owners}
        self.tasks = {
            109: {109: self.row(109, 11), 110: self.row(110, 22, comm=baseline.THREAD_NAME), 111: self.row(111, 33)},
            201: {201: self.row(201, 44), 202: self.row(202, 45)},
        }
        self.calls, self.events, self.commits = [], [], []
        self.unreadable, self.bad_enumeration = set(), set()
        self.before_set = self.after_set = self.commit_failure = None
        self.handlers_active, self.block_depth = False, 0
        self.base = SimpleNamespace(THREAD_NAME=baseline.THREAD_NAME,
            block_restore_signals=self.block, interrupt_handlers=self.handlers,
            api_issues=baseline.api_issues, summarize_phase=baseline.summarize_phase,
            judge=baseline.judge)
        self.identity = SimpleNamespace(boot_id=lambda: 'fake-boot')

    @staticmethod
    def row(tid, start, affinity=trial.ALL, comm='worker'):
        return dict(tid=tid, starttime_ticks=start, affinity=list(affinity), comm=comm)

    @contextlib.contextmanager
    def handlers(self):
        self.handlers_active = True
        try:
            yield
        finally:
            self.handlers_active = False

    @contextlib.contextmanager
    def block(self):
        self.block_depth += 1
        try:
            yield
        finally:
            self.block_depth -= 1

    def now(self):
        return self.host.clock

    def sleep(self, duration):
        self.host.sleep(duration)

    def bindings(self):
        return self.host.bindings()

    def verify_owner(self, owner):
        if self.identities.get(owner['identity']['pid']) != owner['identity']:
            raise ProcessLookupError('injected original process replacement')

    def thread_ids(self, owner):
        self.verify_owner(owner)
        pid = owner['identity']['pid']
        if pid in self.bad_enumeration:
            raise PermissionError('injected enumeration failure')
        return sorted(self.tasks[pid])

    def task(self, owner, tid):
        self.verify_owner(owner)
        pid = owner['identity']['pid']
        if (pid, tid) in self.unreadable:
            raise PermissionError('injected one-task inspection failure')
        if tid not in self.tasks[pid]:
            raise ProcessLookupError('ordinary exited fake task')
        return copy.deepcopy(self.tasks[pid][tid])

    def scan_owner(self, owner):
        return [self.task(owner, tid) for tid in self.thread_ids(owner)]

    def scan(self, owners):
        return [dict(kind=owner['kind'], identity=copy.deepcopy(owner['identity']),
                     threads=self.scan_owner(owner)) for owner in owners]

    def set_task(self, owner, row, target, expected_current):
        self.verify_owner(owner)
        actual = self.task(owner, row['tid'])
        if trial.task_key(owner, row) != trial.task_key(owner, actual) or trial.mask(actual) != tuple(expected_current):
            raise RuntimeError('injected identity/current-mask mismatch')
        if self.before_set:
            self.before_set(owner, row, target)
        key = trial.task_key(owner, row)
        self.calls.append((key, tuple(target)))
        self.events.append(('set', key, tuple(target)))
        self.tasks[owner['identity']['pid']][row['tid']]['affinity'] = list(target)
        if row['tid'] == 110:
            self.host.current_mask = list(target)
        if self.after_set:
            callback, self.after_set = self.after_set, None
            callback(owner, row, target)

    def commit(self, path, value, *, immutable=False):
        self.events.append(('commit', Path(path).name))
        self.commits.append((str(path), copy.deepcopy(value)))
        if self.commit_failure:
            self.commit_failure(Path(path), value)
        with Path(path).open('x' if immutable else 'w') as stream:
            json.dump(value, stream, allow_nan=False)
        if immutable:
            Path(path).chmod(0o444)

    def originals(self):
        return dict(schema=trial.SCHEMA, project=str(trial.GAME), uid=os.getuid(), boot_id='fake-boot',
                    worker=copy.deepcopy(self.host.binding['worker']), processes=self.scan(self.owners))

    def plan(self, path):
        with patch.object(baseline, 'online_cpus', return_value=set(trial.ALL)):
            plan = baseline.prepare(self.host, path)
        plan['schema'] = trial.SCHEMA
        return plan


def make_state():
    system, journal = FakeSystem(), MemoryJournal()
    state = trial.ThreadState(system, system.originals(), journal)
    return system, journal, state


class ReservationSafetyTests(unittest.TestCase):
    def assert_all_broad(self, system, except_tasks=()):
        for pid, tasks in system.tasks.items():
            for tid, row in tasks.items():
                if (pid, tid) not in except_tasks:
                    self.assertEqual(trial.mask(row), trial.ALL)

    def test_default_never_imports_helpers_or_queries_or_creates_output(self):
        with patch.object(trial, 'load_helpers', side_effect=AssertionError('helper import')), \
                patch.object(trial.os, 'sched_setaffinity', side_effect=AssertionError('syscall')), \
                patch.object(trial.Path, 'mkdir', side_effect=AssertionError('mkdir')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(trial.main([]), 0)
        self.assertIn('PLAN_ONLY_NO_RUNTIME_QUERIES', output.getvalue())

    def test_non_inference_tasks_change_first_and_exact_worker_last(self):
        system, journal, state = make_state()
        state.apply_b()
        self.assertEqual(system.calls[-1][0], state.worker)
        self.assertEqual(system.calls[-1][1], trial.INFERENCE)
        self.assertTrue(all(target == trial.OTHERS for _, target in system.calls[:-1]))

    def test_first_intent_failure_prevents_every_treatment_syscall(self):
        system, journal, state = make_state()
        journal.fail_kind = 'intent'
        with self.assertRaises(OSError):
            state.apply_b()
        self.assertEqual(system.calls, [])
        self.assertEqual(state.possibly_mutated, set())

    def test_later_intent_failure_cannot_block_earlier_owned_undo(self):
        system, journal, state = make_state()
        journal.fail_intent_number = 2
        with self.assertRaises(OSError):
            state.apply_b()
        self.assertEqual(len(system.calls), 1)
        restored = state.restore()
        self.assertTrue(restored['masks_restored'])
        self.assertTrue(restored['journal_failed'])
        self.assert_all_broad(system)

    def test_possibly_mutated_registration_precedes_failing_syscall_readback(self):
        system, journal, state = make_state()
        def registered(owner, row, target):
            self.assertIn(trial.task_key(owner, row), state.possibly_mutated)
            self.assertEqual(journal.rows[-1]['kind'], 'intent')
        system.before_set = registered
        system.after_set = lambda *args: (_ for _ in ()).throw(OSError('readback failed after real mock change'))
        with self.assertRaises(OSError):
            state.apply_b()
        system.before_set = None
        self.assertTrue(state.restore()['masks_restored'])
        self.assert_all_broad(system)

    def test_new_inherited_others_mask_is_recorded_without_repair(self):
        system, journal, state = make_state()
        state.apply_b(); count = len(system.calls)
        system.tasks[109][112] = system.row(112, 34, trial.OTHERS)
        state.scan_guard('B')
        self.assertEqual(len(system.calls), count)
        restored = state.restore()
        self.assertIn([109, 11, 112, 34], restored['newborn_leader_fallbacks'])
        self.assert_all_broad(system)

    def test_new_inference_inherited71_invalidates_and_only_undo_widens(self):
        system, journal, state = make_state()
        state.apply_b(); count = len(system.calls)
        system.tasks[109][112] = system.row(112, 34, trial.INFERENCE)
        with self.assertRaisesRegex(RuntimeError, 'Unexpected thread mask'):
            state.scan_guard('B')
        self.assertEqual(len(system.calls), count)
        self.assertTrue(state.restore()['masks_restored'])
        self.assert_all_broad(system)

    def test_a_newborn71_before_any_possible_write_is_preserved_as_external(self):
        system, journal, state = make_state()
        system.tasks[109][112] = system.row(112, 34, trial.INFERENCE)
        with self.assertRaisesRegex(RuntimeError, 'Unexpected thread mask'):
            state.scan_guard('A')
        restored = state.restore()
        self.assertTrue(restored['manual_recovery_required'])
        self.assertEqual(system.calls, [])
        self.assertEqual(trial.mask(system.tasks[109][112]), trial.INFERENCE)

    def test_other_owner_intents_cannot_authorize_newborn71_overwrite(self):
        system, journal, state = make_state()
        state.apply_b()
        system.tasks[201][203] = system.row(203, 46, trial.INFERENCE)
        restored = state.restore()
        self.assertTrue(restored['manual_recovery_required'])
        self.assertEqual(trial.mask(system.tasks[201][203]), trial.INFERENCE)
        self.assert_all_broad(system, except_tasks={(201, 203)})

    def test_actor_others_intent_cannot_authorize_trainer_newborn_others_overwrite(self):
        system, journal, state = make_state()
        owner = system.owners[1]
        state.treatment_write(owner, system.task(owner, 201), trial.OTHERS)
        system.tasks[109][112] = system.row(112, 34, trial.OTHERS)
        restored = state.restore()
        self.assertTrue(restored['manual_recovery_required'])
        self.assertEqual(trial.mask(system.tasks[109][112]), trial.OTHERS)
        self.assert_all_broad(system, except_tasks={(109, 112)})

    def test_new_wrong_mask_during_transition_also_invalidates_without_repair(self):
        system, journal, state = make_state()
        def born(*args):
            system.tasks[109][112] = system.row(112, 34, trial.INFERENCE)
        system.after_set = born
        with self.assertRaisesRegex(RuntimeError, 'Unexpected thread mask'):
            state.apply_b()
        self.assertNotIn(((109, 11, 112, 34), trial.OTHERS), system.calls)
        restored = state.restore()
        self.assertTrue(restored['manual_recovery_required'])
        self.assertEqual(trial.mask(system.tasks[109][112]), trial.INFERENCE)
        self.assert_all_broad(system, except_tasks={(109, 112)})

    def test_only_original_inference_key_may_receive_pin71_intent(self):
        system, journal, state = make_state()
        owner = system.owners[0]
        with self.assertRaisesRegex(RuntimeError, 'Undeclared treatment target'):
            state.treatment_write(owner, system.task(owner, 109), trial.INFERENCE)
        self.assertEqual(system.calls, [])
        self.assertEqual(journal.rows, [])

    def test_reused_non_inference_tid_gets_same_owner_fallback_not_old_identity(self):
        system, journal, state = make_state()
        state.apply_b()
        system.tasks[109][111] = system.row(111, 333, trial.OTHERS)
        state.scan_guard('B')
        restored = state.restore()
        self.assertIn([109, 11, 111, 333], restored['newborn_leader_fallbacks'])
        self.assert_all_broad(system)

    def test_external_mask_skipped_while_same_owner_and_other_owner_restore(self):
        system, journal, state = make_state()
        state.apply_b()
        system.tasks[109][111]['affinity'] = [42]
        before = len(system.calls)
        restored = state.restore()
        self.assertTrue(restored['manual_recovery_required'])
        self.assert_all_broad(system, except_tasks={(109, 111)})
        self.assertEqual(system.tasks[109][111]['affinity'], [42])
        self.assertNotIn(((109, 11, 111, 33), trial.ALL), system.calls[before:])

    def test_one_unreadable_task_never_hides_eligible_same_owner_tasks(self):
        system, journal, state = make_state()
        state.apply_b()
        system.unreadable.add((109, 111))
        with patch.object(system, 'scan_owner', side_effect=AssertionError('whole-owner rollback scan forbidden')):
            restored = state.restore()
        self.assertTrue(restored['manual_recovery_required'])
        self.assert_all_broad(system, except_tasks={(109, 111)})
        self.assertEqual(trial.mask(system.tasks[109][111]), trial.OTHERS)
        self.assertTrue(any(error['operation'] == 'task_inspection' for error in restored['errors']))

    def test_enumeration_failure_still_attempts_all_sealed_known_tasks(self):
        system, journal, state = make_state()
        state.apply_b(); system.bad_enumeration.add(109)
        restored = state.restore()
        self.assertTrue(restored['manual_recovery_required'])
        self.assert_all_broad(system)

    def test_replaced_actor_is_untouched_and_other_original_owner_restores(self):
        system, journal, state = make_state()
        state.apply_b()
        system.identities[201]['starttime_ticks'] = 999
        before = len(system.calls)
        restored = state.restore()
        self.assertTrue(restored['manual_recovery_required'])
        self.assertTrue(all(key[0] != 201 for key, _ in system.calls[before:]))
        for row in system.tasks[109].values():
            self.assertEqual(trial.mask(row), trial.ALL)

    def test_missing_inference_does_not_gate_other_task_undo(self):
        system, journal, state = make_state()
        state.apply_b(); del system.tasks[109][110]
        with patch.object(system, 'bindings', side_effect=AssertionError('global health must not gate rollback')):
            restored = state.restore()
        self.assertTrue(restored['manual_recovery_required'])
        self.assert_all_broad(system)

    def test_system_setter_rejects_expected_mask_drift_before_actual_syscall(self):
        system = FakeSystem()
        owner, row = system.owners[0], system.task(system.owners[0], 109)
        adapter = object.__new__(trial.System)
        adapter.verify_owner = system.verify_owner
        adapter.task = lambda *args: dict(row, affinity=[42])
        with patch.object(trial.os, 'sched_setaffinity', side_effect=AssertionError('unsafe syscall')):
            with self.assertRaisesRegex(RuntimeError, 'External current-mask'):
                adapter.set_task(owner, row, trial.OTHERS, trial.ALL)

    def test_full_fresh_trial_durably_precommits_all_originals_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            system, journal = FakeSystem(), MemoryJournal()
            output = Path(directory) / 'new'
            plan, original = system.plan(output), system.originals()
            def precommitted(owner, row, target):
                self.assertTrue(system.handlers_active)
                self.assertGreater(system.block_depth, 0)
                stored = json.loads((output / 'originals.json').read_text())
                self.assertEqual(stored, original)
                self.assertTrue((output / 'precommit.json').exists())
            system.before_set = precommitted
            with patch.object(trial, 'Journal', return_value=journal), patch.object(trial.signal, 'sigpending', return_value=set()):
                result = trial.run_trial(system, plan, original)
            self.assertEqual(result['state'], 'complete', result.get('error'))
            self.assertEqual([row['phase'] for row in result['results']], ['A', 'B', 'Areturn'])
            self.assertEqual([row['duration_s'] for row in result['results']], [300, 300, 300])
            starts = [row for row in journal.rows if row['kind'] == 'phase_start']
            self.assertEqual([row['phase'] for row in starts], ['A', 'B', 'Areturn'])
            self.assertTrue(all(row['log_offsets'] == {} for row in starts))
            self.assertEqual(result['decision']['outcome'], 'qualified')
            self.assertFalse(result['decision']['automatic_promotion'])
            self.assert_all_broad(system)
            self.assertFalse(system.handlers_active)

    def test_precommit_failure_never_changes_affinity(self):
        with tempfile.TemporaryDirectory() as directory:
            system = FakeSystem(); output = Path(directory) / 'new'
            def fail(path, value):
                if path.name == 'precommit.json':
                    raise OSError('injected directory/file fsync failure')
            system.commit_failure = fail
            with patch.object(trial.signal, 'sigpending', return_value=set()):
                result = trial.run_trial(system, system.plan(output), system.originals())
            self.assertEqual(result['state'], 'failed')
            self.assertEqual(system.calls, [])

    def test_api_failure_and_handled_interruption_restore_every_eligible_task(self):
        for interruption in (False, True):
            with self.subTest(interruption=interruption), tempfile.TemporaryDirectory() as directory:
                system, journal = FakeSystem(), MemoryJournal()
                if interruption:
                    system.host.signal_during_B = True
                else:
                    system.host.throw_during_B = True
                with patch.object(trial, 'Journal', return_value=journal), patch.object(trial.signal, 'sigpending', return_value=set()):
                    result = trial.run_trial(system, system.plan(Path(directory) / 'new'), system.originals())
                self.assertEqual(result['decision']['outcome'], 'invalid')
                self.assert_all_broad(system)

    def test_pending_term_during_cleanup_invalidates_even_when_masks_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            system = FakeSystem(); output = Path(directory) / 'new'
            with patch.object(trial, 'Journal', return_value=MemoryJournal()), \
                    patch.object(trial.signal, 'sigpending', return_value={signal.SIGTERM}):
                result = trial.run_trial(system, system.plan(output), system.originals())
            self.assertEqual(result['decision']['outcome'], 'invalid')
            self.assert_all_broad(system)

    def test_final_status_failure_cannot_leave_qualified_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            system = FakeSystem(); output = Path(directory) / 'new'
            complete_publications = []
            def fail(path, value):
                if path.name == 'status.json' and value.get('state') == 'complete':
                    complete_publications.append(copy.deepcopy(value))
                    raise OSError('final durable recovery publication failed')
            system.commit_failure = fail
            with patch.object(trial, 'Journal', return_value=MemoryJournal()), \
                    patch.object(trial.signal, 'sigpending', return_value=set()), contextlib.redirect_stderr(io.StringIO()):
                result = trial.run_trial(system, system.plan(output), system.originals())
            self.assertEqual(len(complete_publications), 1)
            self.assertEqual(complete_publications[0]['decision']['outcome'], 'qualified')
            self.assertEqual([row['phase'] for row in complete_publications[0]['results']], ['A', 'B', 'Areturn'])
            self.assertEqual(result['state'], 'failed')
            self.assertEqual(result['decision']['outcome'], 'invalid')
            self.assertIn('final durable recovery publication failed', result['status_publication_error'])
            self.assertTrue(result['restoration']['manual_recovery_required'])
            self.assert_all_broad(system)

    def test_restore_only_open_failure_cannot_gate_valid_prefix_owned_undo(self):
        with tempfile.TemporaryDirectory() as directory:
            system, _, state = make_state()
            original = copy.deepcopy(state.originals)
            owner, row = system.owners[0], system.task(system.owners[0], 109)
            system.set_task(owner, row, trial.OTHERS, trial.ALL)
            root = Path(directory)
            intent = dict(sequence=1, kind='intent', key=list(trial.task_key(owner, row)),
                          target=list(trial.OTHERS), restore=list(trial.ALL))
            (root / 'mutation-journal.jsonl').write_text(json.dumps(intent) + '\n')
            with patch.object(trial, 'validate_originals', return_value=(root / 'originals.json', original)), \
                    patch.object(trial, 'Journal', side_effect=OSError('log open denied')):
                restored = trial.restore_only(system, root / 'originals.json')
            self.assertTrue(restored['journal_failed'])
            self.assertTrue(restored['manual_recovery_required'])
            self.assert_all_broad(system)

    def test_torn_last_journal_record_does_not_erase_earlier_valid_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            system, _, state = make_state()
            original = copy.deepcopy(state.originals)
            owner, row = system.owners[0], system.task(system.owners[0], 109)
            system.set_task(owner, row, trial.OTHERS, trial.ALL)
            root = Path(directory)
            intent = dict(sequence=1, kind='intent', key=list(trial.task_key(owner, row)),
                          target=list(trial.OTHERS), restore=list(trial.ALL))
            (root / 'mutation-journal.jsonl').write_text(json.dumps(intent) + '\n{"sequence":2,')
            with patch.object(trial, 'validate_originals', return_value=(root / 'originals.json', original)):
                restored = trial.restore_only(system, root / 'originals.json')
            self.assertTrue(restored['journal_failed'])
            self.assert_all_broad(system)

    def test_journal_file_and_directory_fsync_precede_first_durable_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(trial.os, 'fsync', wraps=os.fsync) as sync:
                journal = trial.Journal(Path(directory) / 'journal.jsonl')
                self.assertGreaterEqual(sync.call_count, 2)
                before = sync.call_count
                journal.record('intent', key=[1, 2, 3, 4])
                self.assertGreater(sync.call_count, before)
                journal.close()

    def test_writer_record_bound_matches_recovery_parser_bound_and_latches_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = trial.Journal(Path(directory) / 'journal.jsonl')
            with patch.object(trial, 'MAX_RECORD_BYTES', 80):
                with self.assertRaises(RuntimeError):
                    journal.record('thread_scan', payload='x' * 200)
            self.assertTrue(journal.failed)
            self.assertFalse(journal.best('restored'))
            journal.close()

    def test_both_fresh_control_gates_accepted_rate_and_amp_skip_guard_stay_fixed(self):
        system = FakeSystem()
        with tempfile.TemporaryDirectory() as directory:
            plan = system.plan(Path(directory) / 'new')
        def result(phase, rate=100, accepted=10, skip=0):
            return dict(phase=phase, applied_admission_samples_per_s=rate,
                        accepted_learner_per_s=accepted, amp_skip_fraction=skip, operationally_valid=True)
        a, ar = result('A'), result('Areturn', 101)
        self.assertEqual(baseline.judge([a, result('B', 105), ar], plan)['outcome'], 'rejected')
        self.assertEqual(baseline.judge([a, result('B', 107, accepted=9), ar], plan)['outcome'], 'rejected')
        self.assertEqual(baseline.judge([a, result('B', 107, skip=.002), ar], plan)['outcome'], 'rejected')
        self.assertEqual(baseline.judge([a, result('B', 107), ar], plan)['outcome'], 'qualified')


if __name__ == '__main__':
    unittest.main()
