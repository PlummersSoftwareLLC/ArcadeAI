"""Exact real server boundary + real frozen controller, staggered startup only.

No previous tests, models, Torch, live actors, MAME, GPU, sockets or controls.
Only the inference-policy/replay-FIFO collaborators are bounded fakes.
"""
import ast
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
OLD = RUN / 'deadline-score60min-protocol-original01-preparation-20261026'
LAZY = RUN / 'deadline-score32-lazy-carry-correction-original02-preparation-20261026'
GAME = HERE.parents[3]
SERVER = GAME / 'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/socket_server.py'
NEW_SHA = '2d9c8d8681708440f641a8f78fe0f2df5e77c7da9fe73e0ff37c78f26e20dfcb'


def load(name, path, expected):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); sys.modules[name] = value
    spec.loader.exec_module(value); return value


new = load('_fixed_fleet_SELECTED_NEW_lifecycle', HERE / 'deadline_measurement_lifecycle_v2.py', NEW_SHA)
old = load('_fixed_fleet_FAILED_lifecycle_negative_control_ONLY', OLD / 'deadline_measurement_lifecycle_v1.py',
           '54aec0ffcc223670494fa6a79d94b509c45452c722fa45cdf6f3022accc964ff')
defs = load('_fixed_fleet_actual_server_suites_definitions_ONLY', LAZY / 'test_actual_server_lazy_score_carry_v1.py',
            'ae67a2d2bdc4b7d70cbc4b88b6d1ee33200882837e74cef12fb31a16f331a46f')
journal_module = load('_fixed_fleet_REAL_journal', SERVER.parent / 'game_journal.py',
                      '96864c78df67f46bc58b1c4af4ce1bceb3791a8842fdcf02871385a1013d1e0f')


class Agent:
    def __init__(self):
        self.training_enabled = False; self.behavior_locked = False; self._prefetch_paused = False
        self._training_lock = threading.RLock(); self.training_steps = 10; self.optimized_samples = 40960
        self.memory = None; self.installs = 0
    def _pause_prefetch(self): self._prefetch_paused = True
    def _resume_prefetch(self): self._prefetch_paused = False
    def capture_inference_policy(self): return {'unchanged': True}
    def install_inference_policy(self, value):
        assert value == {'unchanged': True}; self.installs += 1


class Tests(unittest.TestCase):
    def fixture(self, *, original=False):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        clock = SimpleNamespace(wall=100.)
        metrics = SimpleNamespace(lock=threading.Lock(), training_enabled=False,
            measurement_active=False, measurement_generation=0, measurement_label='', ratchet_frozen=False,
            total_training_steps=10, total_optimized_samples=40960, learner_frame_count=1000)
        journal = journal_module.GameJournal(temp.name, clock=lambda: clock.wall,
            completion_policy='confirmed_reset_reserves_v1')
        api = defs.actual_server_suites(metrics)
        tree = ast.parse(SERVER.read_bytes())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'measurement_boundary_status')
        exact = deepcopy(method)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[exact], type_ignores=[])),
                     str(SERVER) + '::EXACT-measurement-boundary-status-CPU', 'exec'), api)
        server = SimpleNamespace(client_lock=threading.Lock(), client_states={}, game_journal=journal,
            async_buffer=None, replay_enabled=False, _is_eval_client=lambda _: True,
            _sync_client_count_locked=lambda: None, _measurement_snapshot=api['_measurement_snapshot'],
            _journal_context=lambda _: dict(experiment=metrics.measurement_label,
                measurement_active=metrics.measurement_active, measurement_generation=metrics.measurement_generation))
        calls = []
        def boundary(generation):
            value = api['measurement_boundary_status'](server, generation)
            calls.append(deepcopy(value)); return value
        cohort_calls = []; actual_cohort = journal.cohort_status
        def cohort(*args):
            cohort_calls.append(args); return actual_cohort(*args)
        journal.cohort_status = cohort
        lifecycle = (old if original else new).DeadlineMeasurementLifecycle(Agent(), metrics, journal,
            boundary_status=boundary, clock=lambda: clock.wall)
        lifecycle.enter('new-fixed32-startup')
        self.addCleanup(lambda: lifecycle.exit(all_original_threads_stopped=True))
        def connect(cid, *, acknowledge=True):
            api['_init_client'](server, cid)
            cs = server.client_states[cid]; cs['client_slot'] = 4096 + cid  # Actual forced-slot handshake.
            if acknowledge: api['_sync_measurement_boundary'](server, cid, cs, 0)
            return cs
        def acknowledge(cid):
            cs = server.client_states[cid]; return api['_sync_measurement_boundary'](server, cid, cs, 0)
        return lifecycle, metrics, server, connect, acknowledge, boundary, calls, cohort_calls

    def test_real_server_partial_ready_waits_full32_pending_ACK_then_admits_once(self):
        value, metrics, server, connect, acknowledge, boundary, calls, cohorts = self.fixture()
        self.assertEqual(boundary(1)['clients'], 0)
        self.assertIsNone(value.admit_when_ready()); self.assertIsNone(value.origin.start_ts)
        for cid in range(31):
            connect(cid)
            if cid in (0, 2, 30):
                raw = boundary(1)
                self.assertIs(raw['ready'], True); self.assertEqual(raw['expected'], cid + 1)
                self.assertIsNone(value.admit_when_ready()); self.assertIsNone(value.origin.start_ts)
                self.assertEqual(value.origin._boundary['clients'], cid + 1)
                self.assertIs(value.origin._boundary['ready'], False)
                self.assertIs(calls[-1]['ready'], True)  # Raw source result was not mutated.
        self.assertEqual(cohorts, [])
        connect(31, acknowledge=False)
        self.assertEqual(boundary(1)['pending_client_ids'], [31])
        self.assertIsNone(value.admit_when_ready()); self.assertIsNone(value.origin.start_ts)
        pending = threading.Event()
        server.async_buffer = SimpleNamespace(reset_client_async=lambda _: pending)
        acknowledge(31)
        self.assertEqual(boundary(1)['replay_pending_client_ids'], [31])
        self.assertIsNone(value.admit_when_ready()); self.assertIsNone(value.origin.start_ts)
        metrics.learner_frame_count += 7  # Frozen original warming permits the last pre-entry bookkeeping.
        pending.set()
        window = value.admit_when_ready()
        self.assertEqual(window, dict(open_unix_ns=100000000000, close_unix_ns=400000000000,
                                     generation=1, experiment='new-fixed32-startup'))
        self.assertEqual(value.origin._clocks['learner_frame_count'], 1007)
        self.assertEqual(value.phase, 'active'); self.assertEqual(len(cohorts), 1)
        for _ in range(3): self.assertEqual(value.admit_when_ready(), window)
        self.assertEqual(len(cohorts), 1)
        self.assertEqual(value.guard()['actor_slots'], list(range(4096, 4128)))

    def test_real_boundary_loss_generation_and_FIFO_fault_remain_strict_after_arm(self):
        value, metrics, server, connect, acknowledge, boundary, calls, cohorts = self.fixture()
        for cid in range(32): connect(cid)
        window = value.admit_when_ready(); self.assertIsNotNone(window)
        cs = server.client_states.pop(31)
        self.assertTrue(boundary(1)['ready']); self.assertEqual(boundary(1)['clients'], 31)
        with self.assertRaises(ValueError): value.guard()
        server.client_states[31] = cs
        cs['measurement_generation'] = 0
        with self.assertRaises(ValueError): value.guard()
        acknowledge(31)
        pending = threading.Event(); cs['measurement_reset_event'] = pending
        with self.assertRaises(ValueError): value.guard()
        pending.set(); self.assertEqual(value.admit_when_ready(), window)
        self.assertEqual(len(cohorts), 1)

    def test_frozen_original_tick_still_rejects_training_clock_movement_while_partial(self):
        value, metrics, server, connect, acknowledge, boundary, calls, cohorts = self.fixture()
        for cid in range(3): connect(cid)
        self.assertTrue(boundary(1)['ready']); self.assertIsNone(value.admit_when_ready())
        metrics.total_training_steps += 1
        with self.assertRaisesRegex(ValueError, 'Entry barrier failed'): value.admit_when_ready()
        self.assertFalse(value.origin.status()['valid'])
        self.assertEqual(value.origin.status()['reason'], 'training_or_learner_clock_moved')
        self.assertIsNone(value.origin.start_ts); self.assertEqual(cohorts, [])

    def test_failed_original_lifecycle_reproduces_real_three_client_premature_start(self):
        value, metrics, server, connect, acknowledge, boundary, calls, cohorts = self.fixture(original=True)
        for cid in range(3): connect(cid)
        raw = boundary(1); self.assertTrue(raw['ready']); self.assertEqual(raw['expected'], 3)
        with self.assertRaisesRegex(ValueError, 'All32 actual origin acknowledgements required'):
            value.admit_when_ready()
        self.assertIsNotNone(value.origin.start_ts); self.assertEqual(len(cohorts), 1)


if __name__ == '__main__': unittest.main(verbosity=2)
