"""Deferred, unexecuted metadata contracts; root alone may run after freeze release.

The real reviewed3 helper is imported only by setUpClass during future tests.
Held n-step class definitions execute in a stdlib-only namespace: no project,
NumPy or Torch imports. These fixtures do not execute the socket handler or prove
behavior/performance noninterference. Source values and actions are synthetic.
"""
import ast
from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
from queue import Queue
import sys
import threading
import types
from typing import Any, Deque, List, Optional, Tuple
import unittest


PROPOSAL = Path(__file__).resolve().parent.parent
REPO = PROPOSAL.parents[2]
HELPER = PROPOSAL / 'rejected_gap_telemetry_reviewed3.py'
NSTEP = REPO / 'Robotron/Scripts/dqn/nstep_buffer.py'
PINS = {
    HELPER: ('d58610a139644b79f39504e48e1bc43bda9837cc51d743bec623103918c50cbd', 12216),
    NSTEP: ('e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1', 3592),
    PROPOSAL / 'socket_server-insertion.patch':
        ('b09570b80da4ec94acd7ba1221ce87010aa7a3b45141d09555fde18ae7fca448', 12729),
    PROPOSAL / 'preparation-manifest.json':
        ('225a0a0192c46478d7286239aced07c720db9174efeed84f6cacdf27031a4366', 8599),
}


def pinned_source(path):
    raw = path.read_bytes()
    expected, length = PINS[path]
    if len(raw) != length or hashlib.sha256(raw).hexdigest() != expected:
        raise AssertionError('Deferred fixture selected source changed: ' + str(path))
    return raw


def client(uid=42, slot=4096, nstep=None, source='dqn'):
    return dict(game_uid=uid, client_slot=slot, frames=10,
                last_state=object(), last_action=(1, 2), prev_action_source=source,
                frame_history=[object(), object()], nstep=nstep,
                measurement_generation=1, measurement_active=False,
                was_done=False, player_alive=True, last_game_score=100,
                last_level_number=2)


def rejected(observer, connection, state, reason='crash_drop', ok=True):
    observer.event('received', connection)
    observer.event('reject', connection, reason=reason, cs=state)
    observer.event('neutral_result', connection, ok=ok)


def accept(observer, connection, state, *, after=None, new_game=False,
           done=False, writable=True):
    observer.event('received', connection)
    ticket = observer.event('accepted', connection, cs=state,
                            score=105, wave=2, alive=not done, done=done,
                            new_game=new_game)
    observer.event('after_reset', ticket, cs=state if after is None else after,
                   writable=writable)
    return ticket


class RejectAllLocks:
    def __init__(self):
        self.entries = 0

    def __enter__(self):
        self.entries += 1
        raise AssertionError('Disabled/no-ticket event acquired diagnostic lock')

    def __exit__(self, *args):
        return False


class QueueDouble:
    """A returning call can discard its input; it is not an insertion receipt."""
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at
        self.physical_insertions = 0

    def step_async(self, experience):
        self.calls.append(experience)
        if len(self.calls) == self.fail_at:
            raise RuntimeError('synthetic queue failure')
        return None


class RejectedGapContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in PINS:
            pinned_source(path)
        spec = importlib.util.spec_from_file_location('_deferred_rejected_gap3', HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        pinned_source(HELPER)
        cls.helper = module

        # Use the actual held dataclass/add/flush bodies, excluding its unused
        # numpy import and every project import. No replica of n-step formulas.
        tree = ast.parse(pinned_source(NSTEP).decode(), filename=str(NSTEP))
        nodes = [node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name in ('_PendingStep', 'NStepReplayBuffer')]
        if [node.name for node in nodes] != ['_PendingStep', 'NStepReplayBuffer']:
            raise AssertionError('Held n-step class boundary changed')
        namespace = types.ModuleType('_deferred_held_nstep_stdlib')
        namespace.__dict__.update(deque=deque, dataclass=dataclass, Any=Any,
                                  Deque=Deque, List=List, Optional=Optional, Tuple=Tuple)
        sys.modules[namespace.__name__] = namespace
        cls.addClassCleanup(sys.modules.pop, namespace.__name__, None)
        body = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
        exec(compile(body, str(NSTEP), 'exec'), namespace.__dict__)
        cls.NStep = namespace.NStepReplayBuffer
        pinned_source(NSTEP)

    def fresh(self):
        return self.helper.RejectedGapTelemetry(enabled=True)

    def test_disabled_and_absent_tickets_do_not_lock(self):
        stages = ('received', 'reject', 'accepted', 'after_reset', 'previous_step',
                  'nstep_before', 'nstep_after', 'one_step', 'enqueue_called',
                  'enqueue_returned', 'next_action', 'finish', 'disconnect')
        for enabled in (False, True):
            observer = self.helper.RejectedGapTelemetry(enabled=enabled)
            real_lock, guard = observer._lock, RejectAllLocks()
            observer._lock = guard
            if not enabled:
                self.assertIsNone(observer.event('connect', cid=1))
                self.assertIsNone(observer.event('reject', 999, reason='crash_drop'))
            for stage in stages:
                self.assertIsNone(observer.event(stage, None))
            observer._lock = real_lock
            self.assertEqual(guard.entries, 0)
            self.assertFalse(observer.snapshot()['observer_error'])
            self.assertTrue(all(value == 0 for value in observer.snapshot()['counters'].values()))

    def test_payload_denominator_reasons_and_failed_neutral_send(self):
        observer, state = self.fresh(), client()
        connection = observer.event('connect', cid=7)
        for reason in ('parse_none', 'crash_jump', 'crash_drop'):
            rejected(observer, connection, state, reason)
        ticket = accept(observer, connection, state)
        observer.event('finish', ticket, outcome='accepted_action_write_completed')
        observer.event('disconnect', connection)
        failed = observer.event('connect', cid=8)
        rejected(observer, failed, client(43, 4097), 'parse_none', ok=False)
        observer.event('disconnect', failed)  # sendall failure exits the real path
        for exit_kind in ('param_mismatch', 'short_payload', 'receive_header_idle',
                          'receive_header_eof', 'receive_invalid_length', 'receive_broken_payload'):
            c = observer.event('connect', cid=9)
            if exit_kind in ('param_mismatch', 'short_payload'):
                observer.event('received', c)
            observer.event(exit_kind, c)
            observer.event('disconnect', c)
        snap = observer.snapshot()
        counts = snap['counters']
        self.assertEqual(counts['payloads_complete'], 7)  # 4 + failed send's 1 + 2 malformed
        self.assertEqual([counts[key] for key in ('parse_none', 'crash_jump', 'crash_drop')], [2, 1, 1])
        self.assertEqual((counts['neutral_write_ok'], counts['neutral_write_failed']), (3, 1))
        self.assertEqual((counts['gaps_opened'], counts['accepted_closures'],
                          counts['disconnect_closures']), (2, 1, 1))
        self.assertEqual(len(snap['witnesses']), 2)
        row, failed_row = snap['witnesses']
        self.assertEqual((row['first_receive_sequence'], row['last_receive_sequence'],
                          row['first_accepted_receive_sequence']), (1, 3, 4))
        self.assertEqual(row['reasons'], dict(parse_none=1, crash_jump=1, crash_drop=1))
        self.assertEqual(failed_row['outcome'], 'handler_ended_without_completed_accepted_frame')
        self.assertEqual(failed_row['neutral_write_failed'], 1)
        self.assertIsNone(failed_row['before_reset'])
        for key in ('param_mismatch', 'short_payload', 'receive_header_idle',
                    'receive_header_eof', 'receive_invalid_length', 'receive_broken_payload'):
            self.assertEqual(counts[key], 1)
        self.assertTrue(snap['available'])

    def test_first32_witnesses_survive_overflow_without_replacement(self):
        observer, state = self.fresh(), client()
        connection = observer.event('connect', cid=1)
        for _ in range(40):
            rejected(observer, connection, state)
            ticket = accept(observer, connection, state)
            observer.event('finish', ticket, outcome='accepted_action_write_completed')
        snap = observer.snapshot()
        self.assertEqual(len(snap['witnesses']), 32)
        self.assertEqual([r['first_receive_sequence'] for r in snap['witnesses']], list(range(1, 64, 2)))
        self.assertEqual((snap['counters']['gaps_opened'], snap['counters']['accepted_closures'],
                          snap['counters']['witness_overflow']), (40, 40, 8))
        self.assertTrue(snap['available'])  # overflow explicitly limits examples, not counters

    def test_client_capacity_stays_bounded_and_overflow_invalidates_availability(self):
        observer = self.fresh()
        keys = [observer.event('connect', cid=i) for i in range(256)]
        self.assertEqual(len(set(keys)), 256)
        self.assertIsNone(observer.event('connect', cid=256))
        observer.event('received', None)
        snap = observer.snapshot()
        self.assertEqual((snap['active_tracked_clients'], snap['counters']['connections'],
                          snap['counters']['tracking_overflow']), (256, 256, 1))
        self.assertFalse(snap['available'])
        observer.event('disconnect', keys[0])
        replacement = observer.event('connect', cid=257)
        self.assertNotIn(replacement, keys)
        self.assertEqual(observer.snapshot()['active_tracked_clients'], 256)
        self.assertFalse(observer.snapshot()['available'])  # lost tracking is not erased

    def test_positive_uid_continuity_and_interrupted_unknown(self):
        observer, state = self.fresh(), client(91)
        connection = observer.event('connect', cid=1)
        rejected(observer, connection, state)
        ticket = accept(observer, connection, state)
        observer.event('next_action', ticket, cs=dict(state, last_action=(3, 4), prev_action_source='epsilon'))
        observer.event('finish', ticket, outcome='accepted_action_write_completed')
        witness = observer.snapshot()['witnesses'][0]
        self.assertTrue(witness['same_classifier_game'])
        self.assertEqual([witness[key]['game_uid'] for key in ('reject_before', 'before_reset', 'after_reset')], [91, 91, 91])
        self.assertEqual(witness['next_action'], [3, 4])
        self.assertEqual(witness['next_action_source'], 'epsilon')
        rejected(observer, connection, state)
        observer.event('received', connection)
        observer.event('accepted', connection, cs=state, score=105, wave=2,
                       alive=True, done=False, new_game=False)
        observer.event('disconnect', connection)  # never reached the real reset aftermath
        interrupted = observer.snapshot()['witnesses'][1]
        self.assertIsNone(interrupted['same_classifier_game'])
        self.assertIsNone(interrupted['after_reset'])

    def test_initial_uid_new_game_and_measurement_reset_are_distinguished(self):
        cases = (
            (client(0), client(0), client(101), False, False, False),
            (client(11), client(12), client(12), True, False, False),
            (client(11), client(12), client(12), False, False, False),
            (client(11), client(11), client(12), False, False, False),
            (client(11), client(11), dict(client(11), measurement_generation=2,
                                        measurement_active=True, last_state=None,
                                        last_action=None, frame_history=[]), False, True, True),
        )
        for before, accepted, after, new_game, same, boundary in cases:
            with self.subTest(initial_uid=before['game_uid'], new_game=new_game, boundary=boundary):
                observer = self.fresh()
                c = observer.event('connect', cid=1)
                rejected(observer, c, before)
                ticket = accept(observer, c, accepted, after=after, new_game=new_game,
                                writable=not boundary)
                observer.event('finish', ticket, outcome='accepted_action_write_completed')
                row = observer.snapshot()['witnesses'][0]
                self.assertIs(row['same_classifier_game'], same)
                self.assertIs(row['measurement_boundary'], boundary)
                self.assertEqual(observer.snapshot()['counters']['new_game_classified'], int(new_game))
                if boundary:
                    self.assertFalse(row['after_reset']['last_state_present'])
                    self.assertIsNone(row['after_reset']['last_action'])
                    self.assertFalse(row['replay_writable_after_reset'])
                    self.assertFalse(row['previous_step_entered'])

    def test_held_nstep_same_group_and_terminal_emissions_include_current_input(self):
        for terminal in (False, True):
            with self.subTest(terminal=terminal):
                nstep = self.NStep(3, 0.5)
                self.assertEqual(nstep.add('s0', 0, 1, 's1', False, actor='dqn'), [])
                self.assertEqual(nstep.add('s1', 1, 2, 's2', False, actor='epsilon'), [])
                observer, state = self.fresh(), client(nstep=nstep)
                c = observer.event('connect', cid=1)
                rejected(observer, c, state)
                ticket = accept(observer, c, state, done=terminal)
                observer.event('previous_step', ticket)
                observer.event('nstep_before', ticket, nstep=nstep, actor='dqn', done=terminal)
                emitted = nstep.add('s2', 2, 4, 's3', terminal, actor='dqn')
                observer.event('nstep_after', ticket, count=len(emitted))
                self.assertEqual([x[0] for x in emitted], ['s0', 's1', 's2'] if terminal else ['s0'])
                self.assertEqual([x[2] for x in emitted], [3.0, 4.0, 4.0] if terminal else [3.0])
                self.assertTrue(all(x[4] == 's3' and x[5] == terminal for x in emitted))
                queue = QueueDouble()
                for experience in emitted:
                    observer.event('enqueue_called', ticket)
                    queue.step_async(experience)
                    observer.event('enqueue_returned', ticket)
                observer.event('finish', ticket, outcome='accepted_done_neutral_write_completed' if terminal else 'accepted_action_write_completed')
                row = observer.snapshot()['witnesses'][0]
                self.assertTrue(row['previous_step_entered'])
                self.assertEqual(row['nstep'], dict(input_actor='dqn', training_done=terminal,
                    pending_before=2, group_flush_before_input=0, matured_total=len(emitted),
                    matured_including_current_input=len(emitted)))
                self.assertEqual(row['including_current_input_enqueue_calls'], len(emitted))
                self.assertEqual(queue.physical_insertions, 0)

    def test_held_group_flush_precedes_current_terminal_and_queue_failure(self):
        nstep = self.NStep(3, 0.5)
        nstep.add('old-A', 0, 2, 'old-B', False, actor='expert')
        nstep.add('old-B', 1, 4, 'before-gap', False, actor='expert')
        observer, state = self.fresh(), client(nstep=nstep, source='dqn')
        c = observer.event('connect', cid=1)
        rejected(observer, c, state)
        ticket = accept(observer, c, state, done=True)
        observer.event('previous_step', ticket)
        observer.event('nstep_before', ticket, nstep=nstep, actor='dqn', done=True)
        emitted = nstep.add('gap-following', 2, 8, 'current-next', True, actor='dqn')
        observer.event('nstep_after', ticket, count=len(emitted))
        self.assertEqual([(x[0], x[2], x[4], x[5], x[6], x[7]) for x in emitted], [
            ('old-A', 4.0, 'before-gap', False, 2, 'expert'),
            ('old-B', 4.0, 'before-gap', False, 1, 'expert'),
            ('gap-following', 8.0, 'current-next', True, 1, 'dqn')])
        queue = QueueDouble(fail_at=3)
        with self.assertRaisesRegex(RuntimeError, 'synthetic queue failure'):
            for experience in emitted:
                observer.event('enqueue_called', ticket)
                queue.step_async(experience)
                observer.event('enqueue_returned', ticket)
        observer.event('disconnect', c)  # finally closes the interrupted accepted gap
        row = observer.snapshot()['witnesses'][0]
        self.assertEqual(row['nstep']['group_flush_before_input'], 2)
        self.assertEqual(row['nstep']['matured_including_current_input'], 1)
        self.assertEqual((row['enqueue_calls'], row['enqueue_returns'],
                          row['including_current_input_enqueue_calls']), (3, 2, 1))
        self.assertEqual(row['outcome'], 'handler_ended_without_completed_accepted_frame')
        self.assertTrue(observer.snapshot()['available'])  # queue failure != observer failure

    def test_one_step_called_returned_is_not_physical_insertion(self):
        observer, state = self.fresh(), client(nstep=None)
        c = observer.event('connect', cid=1)
        rejected(observer, c, state)
        ticket = accept(observer, c, state)
        observer.event('previous_step', ticket)
        observer.event('one_step', ticket, actor='eval', done=False)
        queue = QueueDouble()
        observer.event('enqueue_called', ticket)
        queue.step_async(('synthetic transition',))
        observer.event('enqueue_returned', ticket)
        observer.event('finish', ticket, outcome='accepted_action_write_completed')
        row = observer.snapshot()['witnesses'][0]
        self.assertEqual((row['enqueue_calls'], row['enqueue_returns'],
                          row['including_current_input_enqueue_calls']), (1, 1, 1))
        self.assertEqual(row['nstep']['input_actor'], 'eval')
        self.assertEqual(observer.snapshot()['counters']['one_step_called'], 1)
        self.assertEqual(observer.snapshot()['counters']['nstep_add_called'], 0)
        self.assertEqual(queue.physical_insertions, 0)

    def test_readonly_snapshot_does_not_drain_or_retain_caller_objects(self):
        observer, state = self.fresh(), client()
        c = observer.event('connect', cid=1)
        rejected(observer, c, state)
        ticket = accept(observer, c, state)
        observer.event('finish', ticket, outcome='accepted_action_write_completed')
        first = observer.snapshot()
        self.assertEqual(first, observer.snapshot())
        json.dumps(first, allow_nan=False)  # object() states/history must never escape
        state['last_action'] = (8, 8)
        state['game_uid'] = 999
        first['counters']['crash_drop'] = -100
        first['witnesses'][0]['reasons']['crash_drop'] = -100
        first['witnesses'][0]['after_reset']['last_action'][0] = 8
        fresh = observer.snapshot()
        self.assertEqual(fresh['counters']['crash_drop'], 1)
        self.assertEqual(fresh['witnesses'][0]['reasons']['crash_drop'], 1)
        self.assertEqual(fresh['witnesses'][0]['after_reset']['last_action'], [1, 2])
        self.assertEqual(fresh['witnesses'][0]['reject_before']['game_uid'], 42)

    def test_fault_and_saturation_make_counters_unavailable_without_raising(self):
        observer = self.fresh()
        c = observer.event('connect', cid=1)
        observer.event('received', c)
        self.assertIsNone(observer.event('reject', c, reason='foreign_reason', cs=client()))
        snap = observer.snapshot()
        self.assertTrue(snap['observer_error'])
        self.assertFalse(snap['available'])
        self.assertEqual(snap['counters']['payloads_complete'], 1)
        # Boundary fixture reaches 2^63 without billions of synthetic events.
        saturated = self.fresh()
        c = saturated.event('connect', cid=1)
        saturated._counts['payloads_complete'] = self.helper.MAX_COUNT
        saturated.event('received', c)
        snap = saturated.snapshot()
        self.assertEqual(snap['counters']['payloads_complete'], (1 << 63) - 1)
        self.assertTrue(snap['counter_saturated'])
        self.assertFalse(snap['available'])
        # Real incompatible n-step output ordering must also be visible as fault.
        bad = self.fresh()
        nstep = self.NStep(3, 0.5)
        nstep.add('old', 0, 1, 'next', False, actor='expert')
        state = client(nstep=nstep)
        c = bad.event('connect', cid=2)
        rejected(bad, c, state)
        ticket = accept(bad, c, state)
        bad.event('nstep_before', ticket, nstep=nstep, actor='dqn', done=False)
        self.assertIsNone(bad.event('nstep_after', ticket, count=0))
        self.assertTrue(bad.snapshot()['observer_error'])
        self.assertFalse(bad.snapshot()['available'])

    def test_concurrent_clients_keep_counters_and_gap_witnesses_separate(self):
        observer = self.fresh()
        opened, proceed, failures = threading.Barrier(9, timeout=5), threading.Barrier(9, timeout=5), Queue()

        def run_client(cid):
            try:
                c = observer.event('connect', cid=cid)
                state = client(1000 + cid, 4096 + cid)
                for index in range(6):
                    rejected(observer, c, state, ('parse_none', 'crash_jump', 'crash_drop')[cid % 3])
                    if index == 0:
                        opened.wait()
                        proceed.wait()
                    ticket = accept(observer, c, state)
                    observer.event('finish', ticket, outcome='accepted_action_write_completed')
                observer.event('disconnect', c)
            except BaseException as error:
                failures.put(repr(error))

        threads = [threading.Thread(target=run_client, args=(cid,), daemon=True) for cid in range(8)]
        for thread in threads:
            thread.start()
        try:
            opened.wait()
            mid = observer.snapshot()
            self.assertEqual((mid['pending_gaps'], mid['accepted_frames_in_progress']), (8, 0))
            self.assertEqual(mid['witnesses'], [])
            self.assertEqual(mid['counters']['gaps_opened'], 8)
        finally:
            try:
                proceed.wait()
            except threading.BrokenBarrierError:
                proceed.abort()
        for thread in threads:
            thread.join(timeout=8)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertTrue(failures.empty(), list(failures.queue))
        snap = observer.snapshot()
        self.assertTrue(snap['available'])
        self.assertEqual((snap['active_tracked_clients'], snap['pending_gaps'],
                          snap['accepted_frames_in_progress']), (0, 0, 0))
        self.assertEqual([snap['counters'][key] for key in (
            'connections', 'payloads_complete', 'gaps_opened', 'accepted_frames',
            'accepted_closures', 'neutral_write_ok', 'witness_overflow')], [8, 96, 48, 48, 48, 48, 16])
        self.assertEqual([snap['counters'][key] for key in ('parse_none', 'crash_jump', 'crash_drop')], [18, 18, 12])
        for row in snap['witnesses']:
            self.assertEqual(row['reject_before']['game_uid'], 1000 + row['cid'])
            self.assertEqual(row['after_reset']['slot'], 4096 + row['cid'])
            self.assertTrue(row['same_classifier_game'])
            self.assertEqual(row['first_accepted_receive_sequence'], row['last_receive_sequence'] + 1)
            reason = ('parse_none', 'crash_jump', 'crash_drop')[row['cid'] % 3]
            self.assertEqual(row['reasons'][reason], 1)
            self.assertEqual(sum(row['reasons'].values()), 1)


if __name__ == '__main__':
    unittest.main()
