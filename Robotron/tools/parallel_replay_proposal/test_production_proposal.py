"""Exercise the unapplied production patch in a temporary copied module tree."""

import ast
from contextlib import ExitStack
import hashlib
import importlib.util
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = ""
for _key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"

import numpy as np

from .build_proposal import ROOT, patched_sources


def files_digest(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


class PatchedReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="robotron-parallel-proposal-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.originals, cls.candidates = patched_sources()
        cls.live_hashes = files_digest([ROOT / path for path in cls.originals])
        copied = cls.root / "Robotron/Scripts/dqn"
        shutil.copytree(ROOT / "Robotron/Scripts/dqn", copied, ignore=shutil.ignore_patterns("__pycache__"))
        # Apply the actual review artifact, not a second handwritten integration.
        proposal = Path(__file__).resolve().parent / "production.patch"
        subprocess.run(["git", "apply", "--check", str(proposal)], cwd=cls.root, check=True, capture_output=True)
        subprocess.run(["git", "apply", str(proposal)], cwd=cls.root, check=True, capture_output=True)
        for path, candidate in cls.candidates.items():
            if (cls.root / path).read_text() != candidate:
                raise AssertionError("Review patch differs from the tested generated source")
        cls.package = "parallel_replay_candidate_dqn"
        spec = importlib.util.spec_from_file_location(cls.package, copied / "__init__.py",
                                                    submodule_search_locations=[str(copied)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[cls.package] = module
        spec.loader.exec_module(module)
        cls.rb = __import__(cls.package + ".replay_buffer", fromlist=["replay_buffer"])
        # Compile the exact stop method from copied agent.py without importing
        # the model/CUDA-heavy agent module or constructing an agent.
        tree = ast.parse((copied / "agent.py").read_text())
        agent_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and
                           any(isinstance(child, ast.FunctionDef) and child.name == "stop" for child in node.body))
        stop = next(node for node in agent_class.body if isinstance(node, ast.FunctionDef) and node.name == "stop")
        stop_code = ast.Module(body=[stop], type_ignores=[])
        namespace = dict(queue=queue)
        exec(compile(ast.fix_missing_locations(stop_code), str(copied / "agent.py"), "exec"), namespace)
        cls.stop = staticmethod(namespace["stop"])

    @classmethod
    def tearDownClass(cls):
        if files_digest([ROOT / path for path in cls.originals]) != cls.live_hashes:
            raise AssertionError("Live production source changed during isolated proposal tests")
        for key in list(sys.modules):
            if key == cls.package or key.startswith(cls.package + "."):
                del sys.modules[key]

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"DQN_PARALLEL_STATE_FILL": "1"}))
        for name, value in dict(hof_enabled=True, ephof_enabled=True, hof_max_episodes=2,
                                ephof_max_episodes=2, hof_episode_stride=64, ephof_episode_stride=64,
                                hof_min_transitions=2, ephof_min_transitions=2,
                                hof_replay_fraction=.1, ephof_replay_fraction=.15,
                                interesting_replay_bank_size=64).items():
            self.stack.enter_context(patch.object(self.rb.RL_CONFIG, name, value))
        self.memory = self.make_memory()
        self.outputs = [np.empty((20, 7), np.float32) for _ in range(2)]
        # Restore test-process RNG state after exact private comparisons.
        state = np.random.get_state()
        self.addCleanup(np.random.set_state, state)

    def make_memory(self):
        memory = self.rb.PrioritizedReplayBuffer(64, 7)
        self.addCleanup(memory.close_state_fill)
        for index in range(64):
            state = np.full(7, index / 10, np.float32)
            memory.add(state, index % 81, index / 100, -state, index % 9 == 0,
                       horizon=1 + index % 16, expert=index % 3 == 0,
                       actor_kind=index % 3, interest=1. if index % 4 == 0 else 0.)
        for bank in ("hof", "ephof"):
            setattr(memory, f"{bank}_total", 4)
            setattr(memory, f"_{bank}_flat", np.arange(4, dtype=np.int64))
            for field in ("states", "next_states"):
                getattr(memory, f"{bank}_{field}")[:4] = np.float32(1.000123 if field == "states" else -2.000321)
        return memory

    def compare(self):
        before = np.random.get_state()
        storage = [value for value in vars(self.memory).values() if isinstance(value, np.ndarray)]
        sources = [hashlib.sha256(value.tobytes()).hexdigest() for value in storage]
        expected = self.memory.sample(20, beta=.7)
        after = np.random.get_state()
        np.random.set_state(before)
        actual = self.memory.sample_into(20, *self.outputs, beta=.7)
        for expected_array, actual_array in zip(expected, actual):
            self.assertEqual(expected_array.dtype, actual_array.dtype)
            np.testing.assert_array_equal(actual_array, expected_array)
        for wanted, observed in zip(after, np.random.get_state()):
            np.testing.assert_array_equal(observed, wanted)
        self.assertEqual(sources, [hashlib.sha256(value.tobytes()).hexdigest() for value in storage])
        self.assertIs(actual[0], self.outputs[0]); self.assertIs(actual[3], self.outputs[1])
        return actual

    def assert_replay_locked(self):
        acquired = self.memory.lock.acquire(blocking=False)
        if acquired:
            self.memory.lock.release()
        self.assertFalse(acquired)

    def test_all_fields_sampling_rng_banks_and_persistent_executor_exact(self):
        self.compare()
        executor = self.memory._state_fill_executor
        self.assertIsNotNone(executor)
        self.compare()
        self.assertIs(executor, self.memory._state_fill_executor)
        self.assertEqual(executor._max_workers, 2)
        self.assertEqual(self.memory.state_fill_status()["completed_batches"], 2)

    def test_no_bank_and_zero_quota_path_is_exact(self):
        self.memory._hof_enabled = self.memory._ephof_enabled = False
        with patch.object(self.rb.RL_CONFIG, "interesting_replay_fraction", 0), \
                patch.object(self.rb.RL_CONFIG, "recent_replay_fraction", 0):
            self.compare()
        self.assertEqual(self.memory.state_fill_status()["completed_batches"], 1)

    def test_default_off_and_native_unavailable_preserve_sequential_path(self):
        for requested, available in ((False, True), (True, False)):
            with self.subTest(requested=requested, available=available), \
                    patch.object(self.memory, "_parallel_state_fill_requested", requested), \
                    patch.object(self.rb, "_native_gather_available", available):
                self.compare()
                self.assertIsNone(self.memory._state_fill_executor)
        with patch.dict(os.environ, {}, clear=True):
            new_memory = self.rb.PrioritizedReplayBuffer(1, 1)
        self.addCleanup(new_memory.close_state_fill)
        self.assertFalse(new_memory.state_fill_status()["requested"])

    def test_allocating_sampling_never_starts_parallel_workers(self):
        self.assertIsNotNone(self.memory.sample(20))
        self.assertIsNone(self.memory._state_fill_executor)

    def test_invalid_alias_rejected_before_sampling_rng_or_executor(self):
        before = np.random.get_state()
        with self.assertRaisesRegex(ValueError, "alias each other"):
            self.memory.sample_into(20, self.outputs[0], self.outputs[0])
        for wanted, observed in zip(before, np.random.get_state()):
            np.testing.assert_array_equal(observed, wanted)
        self.assertIsNone(self.memory._state_fill_executor)

    def test_replay_lock_blocks_insert_and_storage_reset_until_writers_drain(self):
        for operation in ("add", "flush"):
            with self.subTest(operation=operation):
                self.locked_write(operation)

    def locked_write(self, operation):
        entered, release, mutation_done = (threading.Event() for _ in range(3))
        entry_lock = threading.Lock()
        count, errors = [0], []
        actual_fill = self.rb._fill_state_rows
        def filling(*args):
            with entry_lock:
                count[0] += 1
                if count[0] == 2:
                    entered.set()
            if not release.wait(3):
                raise TimeoutError("Test failed to release actual replay workers")
            return actual_fill(*args)
        def sample():
            try:
                self.memory.sample_into(20, *self.outputs)
            except BaseException as error:
                errors.append(error)
        def mutate():
            if operation == "add":
                self.memory.add(np.ones(7, np.float32), 0, 0., -np.ones(7, np.float32), False)
            else:
                self.memory.flush()
            mutation_done.set()
        with patch.object(self.rb, "_fill_state_rows", filling):
            caller = threading.Thread(target=sample); caller.start()
            writer = threading.Thread(target=mutate)
            try:
                self.assertTrue(entered.wait(3))
                writer.start()
                self.assertFalse(mutation_done.wait(.03))
                self.assert_replay_locked()
            finally:
                release.set(); caller.join(3)
                if writer.ident is not None:
                    writer.join(3)
            self.assertFalse(caller.is_alive()); self.assertFalse(writer.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(mutation_done.is_set())

    def test_worker_error_does_not_unlock_replay_or_return_while_sibling_writes(self):
        entered, release, failed, returned = (threading.Event() for _ in range(4))
        errors = []
        actual_fill = self.rb._fill_state_rows
        def fill(output, *args):
            if output is self.outputs[0]:
                if not entered.wait(3):
                    raise TimeoutError("Sibling did not enter")
                failed.set()
                raise LookupError("Injected actual replay field error")
            entered.set()
            if not release.wait(3):
                raise TimeoutError("Sibling not released")
            return actual_fill(output, *args)
        def sample():
            try:
                self.memory.sample_into(20, *self.outputs)
            except BaseException as error:
                errors.append(error)
            finally:
                returned.set()
        with patch.object(self.rb, "_fill_state_rows", fill):
            caller = threading.Thread(target=sample); caller.start()
            try:
                self.assertTrue(failed.wait(3))
                self.assertFalse(returned.wait(.03))
                self.assert_replay_locked()
            finally:
                release.set(); caller.join(3)
            self.assertFalse(caller.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], LookupError)
        self.assertEqual(self.memory.state_fill_status()["completed_batches"], 0)
        self.assertTrue(self.memory.state_fill_status()["closed"])
        self.assertIsNotNone(self.memory.sample(20))

    def test_partial_submission_error_drains_first_actual_replay_writer(self):
        # Prime the replay-owned executor so its submit method can be faulted.
        self.memory.sample_into(20, *self.outputs)
        executor = self.memory._state_fill_executor
        entered, release, returned = (threading.Event() for _ in range(3))
        actual_fill, actual_submit = self.rb._fill_state_rows, executor._publish
        errors, submissions = [], [0]
        def fill(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError("Test did not release submitted replay writer")
            return actual_fill(*args)
        def submit(*args):
            submissions[0] += 1
            if submissions[0] == 2:
                if not entered.wait(3):
                    raise TimeoutError("First published writer did not start")
                raise RuntimeError("Injected actual replay submission failure")
            return actual_submit(*args)
        def sample():
            try:
                self.memory.sample_into(20, *self.outputs)
            except BaseException as error:
                errors.append(error)
            finally:
                returned.set()
        with patch.object(self.rb, "_fill_state_rows", fill), patch.object(executor, "_publish", submit):
            caller = threading.Thread(target=sample); caller.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertFalse(returned.wait(.03))
                self.assert_replay_locked()
            finally:
                release.set(); caller.join(3)
        self.assertEqual(len(errors), 1)
        self.assertEqual(str(errors[0]), "Injected actual replay submission failure")
        self.assertEqual(self.memory.state_fill_status()["completed_batches"], 1)

    def test_publication_raises_after_put_keeps_both_running_destinations_owned(self):
        self.memory.sample_into(20, *self.outputs)
        owner = self.memory._state_fill_executor
        first_entered, second_entered, first_release, second_release, failed, returned = (
            threading.Event() for _ in range(6))
        actual_fill, actual_publish = self.rb._fill_state_rows, owner._publish
        errors, count = [], [0]
        def fill(output, *args):
            entered = first_entered if output is self.outputs[0] else second_entered
            release = first_release if output is self.outputs[0] else second_release
            entered.set()
            if not release.wait(3):
                raise TimeoutError("Test did not release queued destination writer")
            return actual_fill(output, *args)
        def publish(ticket):
            count[0] += 1
            actual_publish(ticket)
            if count[0] == 2:
                if not second_entered.wait(3):
                    raise TimeoutError("Second enqueued writer did not start")
                failed.set()
                raise RuntimeError("Injected failure after queue.put")
        def sample():
            try:
                self.memory.sample_into(20, *self.outputs)
            except BaseException as error:
                errors.append(error)
            finally:
                returned.set()
        with patch.object(self.rb, "_fill_state_rows", fill), patch.object(owner, "_publish", publish):
            caller = threading.Thread(target=sample); caller.start()
            try:
                self.assertTrue(first_entered.wait(3)); self.assertTrue(failed.wait(3))
                first_release.set()
                self.assertFalse(returned.wait(.03), "Sampler returned while unreturned job still wrote")
                self.assert_replay_locked()
            finally:
                first_release.set(); second_release.set(); caller.join(3)
        self.assertFalse(caller.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertEqual(str(errors[0]), "Injected failure after queue.put")
        self.assertTrue(all(not worker.is_alive() for worker in owner._threads))

    def test_queued_tickets_cancel_before_claim_and_cannot_write_on_late_entry(self):
        self.memory.sample_into(20, *self.outputs)
        owner = self.memory._state_fill_executor
        actual_publish, actual_run = owner._publish, self.rb._StateFillTicket.run
        waiting, release, returned = (threading.Event() for _ in range(3))
        errors, published, writes = [], [0], []
        for output in self.outputs:
            output.fill(-98765.)
        def run(ticket):
            waiting.set()
            if not release.wait(3):
                raise TimeoutError("Test did not release ticket claim")
            return actual_run(ticket)
        def publish(ticket):
            published[0] += 1
            actual_publish(ticket)
            if published[0] == 2:
                if not waiting.wait(3):
                    raise TimeoutError("Queued ticket did not enter delayed claim")
                raise RuntimeError("Injected queued-ticket publication error")
        def sample():
            try:
                self.memory.sample_into(20, *self.outputs)
            except BaseException as error:
                errors.append(error)
            finally:
                returned.set()
        with patch.object(self.rb._StateFillTicket, "run", run), \
                patch.object(owner, "_publish", publish), \
                patch.object(self.rb, "_fill_state_rows", lambda *args: writes.append(args)):
            caller = threading.Thread(target=sample); caller.start()
            try:
                self.assertTrue(waiting.wait(3))
                self.assertFalse(returned.wait(.03), "Shutdown did not join delayed claim worker")
            finally:
                release.set(); caller.join(3)
        self.assertFalse(caller.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertEqual(str(errors[0]), "Injected queued-ticket publication error")
        self.assertEqual(writes, [])
        self.assertTrue(all(np.all(output == -98765.) for output in self.outputs))

    def test_real_thread_start_failure_before_and_after_start_never_publishes_outputs(self):
        actual_start = threading.Thread.start
        for failing_index in (0, 1):
            for after_start in (False, True):
                with self.subTest(index=failing_index, after_start=after_start):
                    memory = self.make_memory()
                    outputs = [np.full((20, 7), -98765., np.float32) for _ in range(2)]
                    calls = []
                    def start(thread, *args, **kwargs):
                        if thread.name == f"robotron-state-fill_{failing_index}":
                            if after_start:
                                actual_start(thread, *args, **kwargs)
                            raise RuntimeError("Injected real Thread.start failure")
                        return actual_start(thread, *args, **kwargs)
                    with patch.object(threading.Thread, "start", start), \
                            patch.object(self.rb, "_fill_state_rows", lambda *args: calls.append(args)):
                        with self.assertRaisesRegex(RuntimeError, "real Thread.start failure"):
                            memory.sample_into(20, *outputs)
                    self.assertEqual(calls, [])
                    self.assertTrue(all(np.all(output == -98765.) for output in outputs))
                    owner = memory._state_fill_executor
                    self.assertIsNotNone(owner, "Startup-failure owner reference was lost")
                    self.assertTrue(memory.state_fill_status()["closed"])
                    self.assertTrue(all(not worker.is_alive() for worker in owner._threads))
                    memory.close_state_fill()
                    self.assertIs(memory._state_fill_executor, owner)

    def test_interrupt_during_wait_is_delayed_until_both_writers_finish(self):
        entered, release, interrupted, returned = (threading.Event() for _ in range(4))
        errors = []
        self.memory.sample_into(20, *self.outputs)
        owner = self.memory._state_fill_executor
        actual_wait, actual_fill = owner._wait_ticket, self.rb._fill_state_rows
        def fill(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError("Test failed to release workers")
            return actual_fill(*args)
        count = [0]
        def wait(ticket):
            count[0] += 1
            if count[0] == 1:
                interrupted.set()
                raise KeyboardInterrupt("Injected wait interruption")
            return actual_wait(ticket)
        def sample():
            try:
                self.memory.sample_into(20, *self.outputs)
            except BaseException as error:
                errors.append(error)
            finally:
                returned.set()
        with patch.object(self.rb, "_fill_state_rows", fill), patch.object(owner, "_wait_ticket", wait):
            caller = threading.Thread(target=sample); caller.start()
            try:
                self.assertTrue(entered.wait(3)); self.assertTrue(interrupted.wait(3))
                self.assertFalse(returned.wait(.03))
            finally:
                release.set(); caller.join(3)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], KeyboardInterrupt)

    def test_shutdown_waits_for_inflight_work_and_joins_every_owned_worker(self):
        entered, release, closed = (threading.Event() for _ in range(3))
        actual_fill = self.rb._fill_state_rows
        errors = []
        def fill(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError("Test failed to release actual replay workers")
            return actual_fill(*args)
        def sample():
            try:
                self.memory.sample_into(20, *self.outputs)
            except BaseException as error:
                errors.append(error)
        def close():
            self.memory.close_state_fill(); closed.set()
        with patch.object(self.rb, "_fill_state_rows", fill):
            caller = threading.Thread(target=sample); caller.start()
            closer = threading.Thread(target=close)
            try:
                self.assertTrue(entered.wait(3))
                workers = list(self.memory._state_fill_executor._threads)
                closer.start()
                self.assertFalse(closed.wait(.03))
            finally:
                release.set(); caller.join(3)
                if closer.ident is not None:
                    closer.join(3)
        self.assertEqual(errors, [])
        self.assertTrue(closed.is_set())
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertIsNone(self.memory._state_fill_executor)
        self.memory.close_state_fill()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            self.memory.sample_into(20, *self.outputs)
        self.assertIsNotNone(self.memory.sample(20))

    def test_actual_agent_stop_orders_prefetch_then_replay_owner_shutdown(self):
        calls = []
        self.memory.sample_into(20, *self.outputs)
        workers = list(self.memory._state_fill_executor._threads)
        actual_close = self.memory.close_state_fill
        def close():
            calls.append("replay.close_state_fill")
            actual_close()
        fake = types.SimpleNamespace(running=True, _train_queue=queue.Queue(), memory=self.memory,
                                     _train_thread=types.SimpleNamespace(join=lambda **_: calls.append("train.join")),
                                     _prefetcher=types.SimpleNamespace(close=lambda: calls.append("prefetch.close")))
        with patch.object(self.memory, "close_state_fill", close):
            self.stop(fake)
        self.assertEqual(calls, ["train.join", "prefetch.close", "replay.close_state_fill"])
        self.assertFalse(fake.running)
        self.assertTrue(all(not worker.is_alive() for worker in workers))

    def test_status_read_finishes_while_replay_lock_is_held(self):
        returned = threading.Event()
        snapshots = []
        def status():
            snapshots.append(self.memory.state_fill_status())
            returned.set()
        reader = threading.Thread(target=status)
        try:
            with self.memory.lock:
                reader.start()
                self.assertTrue(returned.wait(.2), "Telemetry waited for replay sampling")
        finally:
            if reader.ident is not None:
                reader.join(3)
        self.assertEqual(snapshots[0]["completed_batches"], 0)

    def test_shutdown_interruption_retains_live_executor_reference_for_retry(self):
        self.memory.sample_into(20, *self.outputs)
        executor = self.memory._state_fill_executor
        workers = list(executor._threads)
        self.assertTrue(any(worker.is_alive() for worker in workers))
        with patch.object(executor, "shutdown", side_effect=KeyboardInterrupt("Injected shutdown interruption")):
            with self.assertRaises(KeyboardInterrupt):
                self.memory.close_state_fill()
        self.assertIs(self.memory._state_fill_executor, executor)
        self.assertTrue(self.memory.state_fill_status()["closed"])
        self.assertTrue(self.memory.state_fill_status()["executor_created"])
        self.memory.close_state_fill()
        self.assertIsNone(self.memory._state_fill_executor)
        self.assertTrue(all(not worker.is_alive() for worker in workers))

    def test_real_join_interruption_drains_worker_before_propagation_and_retry(self):
        self.memory.sample_into(20, *self.outputs)
        owner = self.memory._state_fill_executor
        entered, release, join_failed, returned = (threading.Event() for _ in range(4))
        worker_ref, errors, joins = [], [], [0]
        def non_output_work():
            worker_ref.append(threading.current_thread())
            entered.set()
            if not release.wait(3):
                raise TimeoutError("Test did not release non-output shutdown work")
        ticket = self.rb._StateFillTicket(non_output_work, ())
        owner._publish(ticket)
        self.assertTrue(entered.wait(3))
        worker = worker_ref[0]
        actual_join = worker.join
        def join(*args, **kwargs):
            joins[0] += 1
            if joins[0] == 1:
                join_failed.set()
                raise KeyboardInterrupt("Injected real join interruption")
            return actual_join(*args, **kwargs)
        def close():
            try:
                self.memory.close_state_fill()
            except BaseException as error:
                errors.append(error)
            finally:
                returned.set()
        with patch.object(worker, "join", join):
            caller = threading.Thread(target=close); caller.start()
            try:
                self.assertTrue(join_failed.wait(3))
                self.assertFalse(returned.wait(.03), "Join interruption escaped while worker was active")
                self.assertIs(self.memory._state_fill_executor, owner)
            finally:
                release.set(); caller.join(3)
        self.assertFalse(caller.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], KeyboardInterrupt)
        self.assertTrue(all(not thread.is_alive() for thread in owner._threads))
        self.assertIs(self.memory._state_fill_executor, owner)
        self.memory.close_state_fill()
        self.assertIsNone(self.memory._state_fill_executor)

    def test_process_exits_after_fill_without_explicit_close_on_return_or_raise(self):
        code = '''
import sys
sys.path.insert(0, sys.argv[1])
import numpy as np
from dqn import replay_buffer as rb
owner = rb._StateFillWorkers()
owner.start()
source = np.arange(35, dtype=np.float16).reshape(5, 7)
indices = np.array([4, 0, 4], dtype=np.int64)
outputs = [np.empty((3, 7), np.float32) for _ in range(2)]
owner.fill_pair(rb._fill_state_rows, [(output, source, indices, []) for output in outputs])
for output in outputs:
    np.testing.assert_array_equal(output, source[indices].astype(np.float32))
assert all(thread.daemon for thread in owner._threads)
print("filled-with-live-owned-workers", flush=True)
if sys.argv[2] == "raise":
    raise RuntimeError("Injected outer setup failure before agent.stop")
'''
        for mode, expected_code in (("return", 0), ("raise", 1)):
            with self.subTest(mode=mode):
                result = subprocess.run([sys.executable, "-c", code,
                                         str(self.root / "Robotron/Scripts"), mode],
                                        capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
                self.assertIn("filled-with-live-owned-workers", result.stdout)
                if mode == "raise":
                    self.assertIn("Injected outer setup failure before agent.stop", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
