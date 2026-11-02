"""CPU-only original/proposed source AST parity and deterministic host clocks."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import random
from types import SimpleNamespace
import unittest

import numpy as np


DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[3]


class Clock:
    def __init__(self):
        self.value, self.reads = 0.0, 0
    def perf_counter(self):
        self.reads += 1
        return self.value
    def advance(self, seconds):
        self.value += seconds


class Lock:
    def __init__(self, clock):
        self.clock, self.held, self.enters = clock, False, 0
    def __enter__(self):
        self.clock.advance(0.004)
        self.held = True
        self.enters += 1
    def __exit__(self, *args):
        self.held = False
        self.clock.advance(0.002)


def replay_method(category, clock):
    parsed = ast.parse((DIRECTORY / category / "replay_buffer.py").read_text())
    cls = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "PrioritizedReplayBuffer")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "update_priorities")
    namespace = {"np": np, "time": clock}
    exec(compile(ast.Module(body=[method], type_ignores=[]), category + "/replay_buffer.py", "exec"), namespace)
    return namespace["update_priorities"], method


def phase_nodes(category):
    parsed = ast.parse((DIRECTORY / category / "training.py").read_text())
    method = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == "_train_step_impl")
    marker = "priority_t0" if category == "before" else "priority_telemetry"
    first = next(i for i, n in enumerate(method.body) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == marker for t in n.targets))
    last = next(i for i in range(first, len(method.body)) if isinstance(method.body[i], ast.Try))
    return method, first, last


def phase_function(category, clock, metrics):
    method, first, last = phase_nodes(category)
    arguments = ast.parse("def phase(agent, packed, gpu_timing, B, diagnostic_due, indices): pass").body[0].args
    body = copy.deepcopy(method.body[first:last])
    body += [ast.parse("return host, loss_val, gn, bc_loss_val, priority_ms").body[0]]
    fn = ast.FunctionDef(name="phase", args=arguments, body=body, decorator_list=[], returns=None,
                         type_comment=None, type_params=[])
    namespace = {"time": clock, "metrics": metrics}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), category + "/training.py", "exec"), namespace)
    return namespace["phase"]


def recorder_class():
    spec = importlib.util.spec_from_file_location("proposed_priority_pipeline", DIRECTORY / "proposed/pipeline_telemetry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PipelineTelemetry


class Tests(unittest.TestCase):
    def make_buffer(self, category, clock, *, fail=False):
        lock, calls = Lock(clock), []
        class Tree:
            def batch_update(self, indices, priorities):
                self_outer.assertTrue(lock.held)
                calls.append((indices.copy(), priorities.copy()))
                clock.advance(0.003)
                if fail:
                    raise ValueError("deliberate priority failure")
        self_outer = self
        buffer = SimpleNamespace(capacity=17, alpha=0.6, lock=lock, tree=Tree())
        fn, _ = replay_method(category, clock)
        buffer.update_priorities = lambda *args, **kwargs: fn(buffer, *args, **kwargs)
        return buffer, calls

    def test_two_argument_update_preserves_operations_and_has_no_clock_reads(self):
        values = (np.array([1, 4, 1, 20], np.int64), np.array([-1, 2, 3, 9], np.float32))
        outputs = []
        for category in ("before", "proposed"):
            clock = Clock()
            buffer, calls = self.make_buffer(category, clock)
            self.assertIsNone(buffer.update_priorities(*values))
            self.assertEqual(clock.reads, 0)
            self.assertEqual(buffer.lock.enters, 1)
            outputs.append(calls)
        np.testing.assert_array_equal(outputs[0][0][0], outputs[1][0][0])
        self.assertEqual(outputs[0][0][1].tobytes(), outputs[1][0][1].tobytes())

    def test_optional_timings_are_exact_and_written_only_after_lock_release(self):
        clock = Clock()
        buffer, _ = self.make_buffer("proposed", clock)
        class Timing(dict):
            def update(self, *args, **kwargs):
                self_outer.assertFalse(buffer.lock.held)
                return super().update(*args, **kwargs)
        self_outer, timing = self, Timing()
        buffer.update_priorities(np.array([1, 20], np.int64), np.array([3, 9], np.float32), timing_out=timing)
        self.assertAlmostEqual(timing["replay_lock_wait_ms"], 4)
        self.assertAlmostEqual(timing["locked_priority_ms"], 3)
        self.assertAlmostEqual(timing["replay_update_host_ms"], 9)

    def test_early_return_and_error_keep_behavior_and_publish_after_unlock(self):
        for fail in (False, True):
            clock = Clock()
            buffer, calls = self.make_buffer("proposed", clock, fail=fail)
            timing = {}
            indices = np.array([1 if fail else 20], np.int64)
            if fail:
                with self.assertRaisesRegex(ValueError, "deliberate priority failure"):
                    buffer.update_priorities(indices, np.array([3]), timing_out=timing)
            else:
                self.assertIsNone(buffer.update_priorities(indices, np.array([3]), timing_out=timing))
                self.assertFalse(calls)
            self.assertFalse(buffer.lock.held)
            self.assertEqual(set(timing), {"replay_lock_wait_ms", "locked_priority_ms", "replay_update_host_ms"})

    def run_phase(self, category, *, diagnostic=True, telemetry=True):
        clock, metrics, events = Clock(), SimpleNamespace(), []
        buffer, calls = self.make_buffer(category, clock)
        agent = SimpleNamespace(memory=buffer)
        if telemetry:
            recorder = recorder_class()(clock=clock.perf_counter)
            original_record = recorder.record_learner_priority
            def record(values):
                self.assertFalse(buffer.lock.held)
                events.append("record")
                return original_record(values)
            recorder.record_learner_priority = record
            agent._pipeline_telemetry = recorder
        else:
            recorder = None
        data = np.arange(19, dtype=np.float32)
        class Packed:
            def cpu(self):
                events.append("cpu")
                clock.advance(0.005)
                return self
            def numpy(self):
                events.append("numpy")
                clock.advance(0.001)
                return data
        class Event:
            def elapsed_time(self, other):
                events.append("event_elapsed")
                clock.advance(0.001)
                return 12
        function = phase_function(category, clock, metrics)
        result = function(agent, Packed(), (Event(), object()), 4, diagnostic,
                          np.array([1, 2, 3, 20], np.int64))
        return result, metrics.__dict__, events, recorder, calls, clock

    def test_sampled_training_decomposition_and_operation_parity(self):
        old = self.run_phase("before", telemetry=False)
        new = self.run_phase("proposed")
        self.assertEqual(old[0][0].tobytes(), new[0][0].tobytes())
        self.assertEqual(old[0][1:4], new[0][1:4])
        self.assertEqual(old[1], new[1])
        self.assertEqual(old[2], new[2][:-1])
        self.assertEqual(new[2][-1], "record")
        self.assertEqual(old[4][0][1].tobytes(), new[4][0][1].tobytes())
        stats = new[3].snapshot()["learner_priority"]
        for key, expected in {"readback_host_ms": 6, "cpu_bookkeeping_ms": 1,
                              "replay_lock_wait_ms": 4, "locked_priority_ms": 3,
                              "replay_update_host_ms": 9, "total_host_ms": 16}.items():
            self.assertAlmostEqual(stats[key]["total"], expected)
            self.assertEqual(stats[key]["count"], 1)
        self.assertEqual(stats["count"], 1)
        self.assertAlmostEqual(old[0][-1], new[0][-1])

    def test_unsampled_and_no_recorder_paths_keep_original_clock_count(self):
        for diagnostic, telemetry in ((False, True), (True, False)):
            old = self.run_phase("before", diagnostic=diagnostic, telemetry=False)
            new = self.run_phase("proposed", diagnostic=diagnostic, telemetry=telemetry)
            self.assertEqual(old[2], new[2])
            # Recorder construction itself reads its clock once.
            self.assertEqual(new[5].reads - int(telemetry), old[5].reads)
            if telemetry:
                self.assertEqual(new[3].snapshot()["learner_priority"]["count"], 0)

    def test_bounded_monotone_raw_snapshot_and_no_new_CUDA_call_sites(self):
        result = self.run_phase("proposed")
        recorder = result[3]
        before = recorder.snapshot()
        recorder.record_learner_priority({"total_host_ms": 99999})
        after = recorder.snapshot()
        self.assertEqual(after["learner_priority"]["count"], 2)
        self.assertEqual(len(after["learner_priority"]["total_host_ms"]["histogram"]), 17)
        self.assertEqual(after["learner_priority"]["total_host_ms"]["histogram"][-1], 1)
        self.assertEqual(before["learner_priority"]["count"], 1)
        json.dumps(after, allow_nan=False)
        old, oi, oj = phase_nodes("before")
        new, ni, nj = phase_nodes("proposed")
        self.assertEqual(ast.dump(ast.Module(body=old.body[:oi], type_ignores=[])),
                         ast.dump(ast.Module(body=new.body[:ni], type_ignores=[])))
        self.assertEqual(ast.dump(ast.Module(body=old.body[oj:], type_ignores=[])),
                         ast.dump(ast.Module(body=new.body[nj:], type_ignores=[])))
        def cuda_calls(body):
            return [ast.dump(n) for statement in body for n in ast.walk(statement)
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in ("cpu", "numpy", "elapsed_time", "synchronize", "record", "Event")]
        self.assertEqual(cuda_calls(old.body[oi:oj]), cuda_calls(new.body[ni:nj]))

    def test_original_locked_priority_body_AST_is_unchanged(self):
        clock = Clock()
        _, old = replay_method("before", clock)
        _, new = replay_method("proposed", clock)
        original_body = next(n for n in old.body if isinstance(n, ast.With)).body
        outer_try = next(n for n in new.body if isinstance(n, ast.Try))
        new_with = outer_try.body[0]
        new_body = next(n for n in new_with.body if isinstance(n, ast.Try)).body
        self.assertEqual(ast.dump(ast.Module(body=original_body, type_ignores=[])),
                         ast.dump(ast.Module(body=new_body, type_ignores=[])))

    def test_real_tree_bytes_sentinels_and_all_CPU_rng_remain_equal(self):
        import torch
        parsed = ast.parse((DIRECTORY / "before/replay_buffer.py").read_text())
        definition = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "SumTree")
        namespace = {"np": np, "_native_propagate": None, "_native_batch_update": None}
        exec(compile(ast.Module(body=[definition], type_ignores=[]), "original/SumTree", "exec"), namespace)
        py, numpy, cpu = random.getstate(), np.random.get_state(), torch.get_rng_state().clone()
        rng = np.random.default_rng(10162026)
        for capacity in (1, 5, 17, 513):
            buffers = []
            for category in ("before", "proposed"):
                clock = Clock()
                buffer = SimpleNamespace(capacity=capacity, alpha=0.6, lock=Lock(clock), tree=namespace["SumTree"](capacity))
                fn, _ = replay_method(category, clock)
                buffers.append((buffer, fn))
            for _ in range(12):
                indices = rng.integers(0, 2 * capacity, 64, dtype=np.int64)
                errors = rng.uniform(-5, 5, 64).astype(np.float32)
                for index, (buffer, fn) in enumerate(buffers):
                    if index:
                        fn(buffer, indices, errors, timing_out={})
                    else:
                        fn(buffer, indices, errors)
                self.assertEqual(buffers[0][0].tree.tree.tobytes(), buffers[1][0].tree.tree.tobytes())
                self.assertEqual(buffers[0][0].tree.max_priority, buffers[1][0].tree.max_priority)
        self.assertEqual(py, random.getstate())
        self.assertTrue(all(np.array_equal(a, b) if isinstance(a, np.ndarray) else a == b
                            for a, b in zip(numpy, np.random.get_state())))
        self.assertTrue(torch.equal(cpu, torch.get_rng_state()))
        self.assertFalse(torch.cuda.is_initialized())

    def test_all_live_and_private_guarded_sources_remain_untouched(self):
        manifest = json.loads((DIRECTORY / "prepared.json").read_text())
        for name, record in manifest["sources"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), record["before_sha256"])
        for name, digest in manifest["guarded_source_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest)
        self.assertEqual((DIRECTORY / "before/agent.py").read_bytes(),
                         (DIRECTORY / "proposed/agent.py").read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
