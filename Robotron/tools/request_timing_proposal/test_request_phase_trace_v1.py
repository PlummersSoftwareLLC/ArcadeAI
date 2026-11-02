"""CPU-only execution of exact extracted classes; no live module import."""
import ast
import concurrent.futures
import hashlib
import json
from pathlib import Path
import queue
import random
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare_request_trace_sources_v1 as prepare
import request_phase_trace_v1 as trace


def extracted_classes():
    source = (prepare.G/'Scripts/dqn/socket_server.py').read_text()
    tree = ast.parse(prepare.instrument('socket_server.py', source))
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)
             and n.name in ('_InferenceRequest', 'AsyncInferenceBatcher')]
    assert len(nodes) == 2
    scope = dict(threading=threading, queue=queue, time=time, _request_trace=trace)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<extracted-batcher>', 'exec'), scope)
    return scope['AsyncInferenceBatcher']


class GoodAgent:
    def __init__(self):
        self.calls = 0
        self.inputs = []

    def act_batch(self, states, epsilons, locked_fires=None):
        self.calls += 1
        self.inputs.append((states, epsilons, locked_fires))
        return [(int(s), 8 if fire is None else fire, bool(e))
                for s, e, fire in zip(states, epsilons, locked_fires)]


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Batcher = extracted_classes()

    def test_all_operational_AST_preserved(self):
        for name in prepare.EXPECTED:
            original = (prepare.G/'Scripts/dqn'/name).read_text()
            changed = prepare.instrument(name, original)
            self.assertEqual(prepare.stripped_tree(original), prepare.stripped_tree(changed))

    def test_changed_source_refused(self):
        for name in prepare.EXPECTED:
            with self.assertRaisesRegex(ValueError, 'Pinned source'):
                prepare.instrument(name, (prepare.G/'Scripts/dqn'/name).read_text()+'\n')

    def test_module_has_no_import_launch_network_or_file_effects(self):
        allowed = {'collections', 'contextlib', 'math', 'threading', 'time'}
        imports = [n for n in ast.walk(ast.parse(Path(trace.__file__).read_text()))
                   if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual({n.module if isinstance(n, ast.ImportFrom) else n.names[0].name
                          for n in imports}, allowed)
        self.assertIsNone(trace._active)

    def test_disabled_path_returns_exact_action(self):
        batcher = self.Batcher(GoodAgent(), max_wait_ms=0, request_timeout_ms=1000)
        try:
            self.assertEqual(batcher.infer(3, .1, locked_fire=7), (3, 7, True))
            self.assertIsNone(trace.new_request())
        finally:
            batcher.stop()

    def test_concurrent_requests_and_exact_partition(self):
        recorder, agent = trace.Recorder(sample_every=1), GoodAgent()
        with trace.capture(recorder):
            batcher = self.Batcher(agent, max_batch_size=16, max_wait_ms=2, request_timeout_ms=2000)
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                    futures = [pool.submit(batcher.infer, i % 9, .1, i % 9) for i in range(64)]
                    self.assertEqual([f.result(timeout=3) for f in futures],
                                     [(i % 9, i % 9, True) for i in range(64)])
            finally:
                batcher.stop()
        result = trace.analyze(recorder.snapshot())
        self.assertEqual(result['outcomes'], {'returned': 64})
        self.assertEqual(result['partition_residual_ns'], [0]*64)
        self.assertEqual(result['capture_loss'], dict(capacity_drops=0, event_drops=0, errors=0))
        self.assertEqual(sum(len(s) for s, e, f in agent.inputs), 64)

    def test_capacity_and_sampling_bounded(self):
        recorder = trace.Recorder(max_requests=2, sample_every=3)
        with trace.capture(recorder):
            for _ in range(10):
                trace.new_request()
        snapshot = recorder.snapshot()
        self.assertEqual([r['request_id'] for r in snapshot['rows']], [0, 3])
        self.assertEqual(snapshot['seen'], 10)
        self.assertEqual(snapshot['capacity_drops'], 2)
        self.assertEqual(trace.analyze(snapshot)['outcomes'], {'incomplete': 2})

    def test_snapshot_is_detached(self):
        recorder = trace.Recorder(sample_every=1)
        with trace.capture(recorder):
            ticket = trace.new_request()
            before = recorder.snapshot()
            trace.mark(ticket, 'enqueue_attempt')
        self.assertEqual(len(before['rows'][0]['events']), 1)
        self.assertEqual(len(recorder.snapshot()['rows'][0]['events']), 2)

    def test_nested_activation_refused_and_teardown_restored(self):
        with self.assertRaisesRegex(RuntimeError, 'already active'):
            with trace.capture(trace.Recorder()):
                with trace.capture(trace.Recorder()):
                    pass
        self.assertIsNone(trace._active)

    def test_invalid_clock_is_loss_not_request_exception(self):
        recorder = trace.Recorder(sample_every=1, clock=lambda: float('nan'))
        with trace.capture(recorder):
            ticket = trace.new_request()
            trace.mark(ticket, 'enqueue_attempt')
        self.assertEqual(recorder.snapshot()['errors'], 2)
        self.assertEqual(trace.analyze(recorder.snapshot())['outcomes'], {'incomplete': 1})

    def test_model_failure_propagated_and_counted(self):
        class BadAgent:
            def act_batch(self, *a, **kw):
                raise ArithmeticError('test-only failure')
        recorder = trace.Recorder(sample_every=1)
        with trace.capture(recorder):
            batcher = self.Batcher(BadAgent(), max_wait_ms=0, request_timeout_ms=1000)
            try:
                with self.assertRaisesRegex(RuntimeError, 'ArithmeticError: test-only failure'):
                    batcher.infer(1, 0)
            finally:
                batcher.stop()
        result = trace.analyze(recorder.snapshot())
        self.assertEqual(result['outcomes'], {'returned_error': 1})
        self.assertEqual(result['intervals'], {})

    def test_malformed_action_still_refused(self):
        class BadAgent:
            def act_batch(self, *a, **kw):
                return [(99, 0, False)]
        recorder = trace.Recorder(sample_every=1)
        with trace.capture(recorder):
            batcher = self.Batcher(BadAgent(), max_wait_ms=0, request_timeout_ms=1000)
            try:
                with self.assertRaisesRegex(RuntimeError, 'malformed action batch'):
                    batcher.infer(1, 0)
            finally:
                batcher.stop()
        self.assertEqual(trace.analyze(recorder.snapshot())['outcomes'], {'returned_error': 1})

    def test_inflight_timeout_never_reissues_solo(self):
        entered, release = threading.Event(), threading.Event()
        class BlockedAgent(GoodAgent):
            def act_batch(self, *a, **kw):
                entered.set()
                if not release.wait(2):
                    raise RuntimeError('test synchronization expired')
                return super().act_batch(*a, **kw)
        recorder, agent = trace.Recorder(sample_every=1), BlockedAgent()
        with trace.capture(recorder):
            batcher = self.Batcher(agent, max_wait_ms=0, request_timeout_ms=30)
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(batcher.infer, 1, 0)
                    self.assertTrue(entered.wait(1))
                    with self.assertRaisesRegex(TimeoutError, 'Batched inference request timed out'):
                        future.result(timeout=1)
            finally:
                release.set()
                batcher.stop()
        self.assertEqual(agent.calls, 1)
        result = trace.analyze(recorder.snapshot())
        self.assertEqual(result['outcomes'], {'wait_timeout': 1})
        self.assertEqual(result['intervals'], {})

    def test_admission_timeout_counted(self):
        class FullQueue:
            def put(self, req, timeout):
                raise queue.Full
        recorder = trace.Recorder(sample_every=1)
        with trace.capture(recorder):
            batcher = self.Batcher(GoodAgent(), max_wait_ms=0)
            batcher.stop()
            batcher.running = True
            batcher.queue = FullQueue()
            with self.assertRaisesRegex(TimeoutError, 'queue admission timed out'):
                batcher.infer(1, 0)
            batcher.running = False
        self.assertEqual(trace.analyze(recorder.snapshot())['outcomes'], {'admission_timeout': 1})

    def test_stop_wakes_waiter_without_late_success(self):
        entered, release = threading.Event(), threading.Event()
        class BlockedAgent(GoodAgent):
            def act_batch(self, *a, **kw):
                entered.set()
                if not release.wait(2):
                    raise RuntimeError('test synchronization expired')
                return super().act_batch(*a, **kw)
        recorder = trace.Recorder(sample_every=1)
        with trace.capture(recorder):
            batcher = self.Batcher(BlockedAgent(), max_wait_ms=0, request_timeout_ms=2000)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                future = pool.submit(batcher.infer, 2, 0)
                try:
                    self.assertTrue(entered.wait(1))
                    stopped = pool.submit(batcher.stop)
                    with self.assertRaisesRegex(RuntimeError, 'stopped before completion'):
                        future.result(timeout=1)
                finally:
                    release.set()
                    stopped.result(timeout=3)
        self.assertEqual(trace.analyze(recorder.snapshot())['outcomes'], {'returned_error': 1})

    def test_agent_phase_markers_for_greedy_epsilon_and_locked_fire(self):
        # Execute the exact extracted method with CPU NumPy and a tensor shim;
        # torch itself and the production agent module are never imported.
        import numpy as np
        source = (prepare.G/'Scripts/dqn/agent.py').read_text()
        tree = ast.parse(prepare.instrument('agent.py', source))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'act_batch')
        scope = dict(_request_trace=trace, random=random, np=np,
            torch=types.SimpleNamespace(from_numpy=lambda x: x), NUM_FIRE=9, NUM_MOVE=9,
            NUM_JOINT=81, split_joint_action=lambda j: divmod(j, 9))
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<extracted-act-batch>', 'exec'), scope)
        class Agent:
            def _safe_epsilon_action(self, s):
                return 2, 3, True
            def _infer_q_joint(self, st, return_cpu):
                rows = np.tile(np.arange(81, dtype=np.float32), (len(st), 1))
                return types.SimpleNamespace(numpy=lambda: rows)
        for epsilon in (0., 1.):
            recorder = trace.Recorder(sample_every=1)
            with trace.capture(recorder):
                ticket = trace.new_request()
                trace.batch_begin([ticket])
                try:
                    result = scope['act_batch'](Agent(), [[1., 2.]], [epsilon], [4])
                finally:
                    trace.batch_end()
            self.assertEqual(result, [(8, 4, False)] if epsilon == 0 else [(2, 4, True)])
            phases = dict(recorder.snapshot()['rows'][0]['events'])
            self.assertTrue({'epsilon_begin', 'epsilon_end'} <= phases.keys())
            for key in ('state_pack_begin', 'state_pack_end', 'model_begin', 'model_end', 'reduce_begin', 'reduce_end'):
                self.assertEqual(key in phases, epsilon == 0)
        self.assertNotIn('torch', sys.modules)

    def test_analyzer_refuses_bad_or_incomplete_success(self):
        recorder = trace.Recorder(sample_every=1)
        with trace.capture(recorder):
            ticket = trace.new_request()
            trace.mark(ticket, 'returned')
        snapshot = recorder.snapshot()
        with self.assertRaisesRegex(ValueError, 'lacks matched partition'):
            trace.analyze(snapshot)
        snapshot['rows'][0]['events'] = [['begin', 10], ['enqueue_attempt', 9]]
        with self.assertRaisesRegex(ValueError, 'nonmonotonic'):
            trace.analyze(snapshot)
        snapshot['rows'][0]['events'] = [['begin', 10]]
        snapshot['rows'].append(snapshot['rows'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            trace.analyze(snapshot)

    def test_bounds_refused(self):
        for kwargs in ({'max_requests': 0}, {'max_requests': True}, {'sample_every': 0}, {'sample_every': float('inf')}):
            with self.assertRaises(ValueError):
                trace.Recorder(**kwargs)


if __name__ == '__main__':
    # Run explicitly as a CPU subprocess. This module has no service controls,
    # production imports, GPU dispatches or automatic file writes.
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps(dict(schema='robotron-request-phase-offline-tests-v1', tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), successful=result.wasSuccessful(),
        production_modules_imported=False, torch_imported='torch' in sys.modules)))
    sys.exit(0 if result.wasSuccessful() else 1)
