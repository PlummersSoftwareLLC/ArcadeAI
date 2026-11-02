"""CPU byte-oracle and observable-outcome tests for actual native batch code.

No replay/model/optimizer construction. The NumPy reference is the pre-native
batch method, retained independently of the production fast-path implementation.
"""
import ast
from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import random
import unittest
from unittest.mock import patch

import numpy as np

try:
    from . import native_sumtree as native
except ImportError:
    import native_sumtree as native


def numpy_reference(owner, indices, priorities):
    tree_indices = indices.astype(np.int64) + owner.capacity
    owner.tree[tree_indices] = priorities.astype(np.float64)
    maximum = float(priorities.max())
    if maximum > owner.max_priority:
        owner.max_priority = maximum
    parents = np.unique(tree_indices >> 1)
    while len(parents) > 0 and parents[0] >= 1:
        owner.tree[parents] = owner.tree[parents * 2] + owner.tree[parents * 2 + 1]
        parents = np.unique(parents >> 1)
        parents = parents[parents >= 1]


def tree_class():
    source = Path(__file__).with_name("replay_buffer.py")
    parsed = ast.parse(source.read_text())
    definition = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "SumTree")
    namespace = {"np": np, "_native_propagate": None, "_native_batch_update": native.batch_update}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["SumTree"]


SumTree = tree_class()


class TestNativeBatchUpdate(unittest.TestCase):
    def setUp(self):
        if not native.NATIVE_BATCH_AVAILABLE:
            self.skipTest("Optional native batch symbol is unavailable")
        self.enabled = patch.object(native, "NATIVE_BATCH_ENABLED", True)
        self.enabled.start()
        self.addCleanup(self.enabled.stop)
        counters = patch.object(native, "_BATCH_COUNTS", {"success": 0, "fallback": 0, "error": 0})
        counters.start()
        self.addCleanup(counters.stop)

    def assert_bits(self, expected, actual):
        self.assertEqual(expected.tree.tobytes(), actual.tree.tobytes())
        self.assertEqual(np.float64(expected.max_priority).tobytes(),
                         np.float64(actual.max_priority).tobytes())

    def test_sequential_odd_capacity_and_adversarial_old_internal_nodes(self):
        rng = np.random.default_rng(101628)
        for capacity in (1, 2, 3, 5, 17, 997, 4097):
            expected, actual = SumTree(capacity), SumTree(capacity)
            expected.tree[:] = rng.uniform(-1000, 1000, len(expected.tree))
            actual.tree[:] = expected.tree
            for _ in range(24):
                indices = rng.integers(0, capacity, 128, dtype=np.int64)
                priorities = rng.uniform(-10, 10, 128)
                numpy_reference(expected, indices, priorities)
                actual.batch_update(indices, priorities)
                self.assert_bits(expected, actual)
        self.assertEqual(native.batch_update_status()["success_count"], 7 * 24)

    def test_duplicate_leaf_last_wins_and_maximum_includes_overwritten_values(self):
        owner = SumTree(5)
        owner.batch_update(np.array([2, 2, 2], np.int64), np.array([99, 12, 3], np.float64))
        self.assertEqual(owner.tree[7], 3)
        self.assertEqual(owner.max_priority, 99)

    def test_old_signed_zero_subnormal_inf_and_nan_payload_tree_bits(self):
        bits = np.array([0, 0x8000000000000000, 1, 0x8000000000000001,
                         0x7fefffffffffffff, 0xffefffffffffffff, 0x7ff0000000000000,
                         0xfff0000000000000, 0x7ff8000000000001, 0x7ff8000000000002], np.uint64)
        expected, actual = SumTree(17), SumTree(17)
        expected.tree[:] = np.resize(bits.view(np.float64), len(expected.tree))
        actual.tree[:] = expected.tree
        with np.errstate(invalid="ignore", over="ignore", under="ignore"):
            indices, priorities = np.array([0, 2, 16, 0], np.int64), np.array([-0.0, 0.0, 1e-300, -1e-300])
            numpy_reference(expected, indices, priorities)
            actual.batch_update(indices, priorities)
        self.assert_bits(expected, actual)

    def test_dtype_shape_empty_bounds_and_alias_fallback_preserve_numpy_result(self):
        cases = [(np.array([1, 2], np.int32), np.array([2, 3], np.float64)),
                 (np.array([1, 2], np.int64), np.array([2, 3], np.float32)),
                 (np.array([1, 2], np.int64), np.array([2], np.float64)),
                 (np.array([], np.int64), np.array([], np.float64)),
                 (np.array([-1, 1], np.int64), np.array([2, 3], np.float64)),
                 (np.array([1, 17], np.int64), np.array([2, 3], np.float64))]
        for indices, priorities in cases:
            expected, actual = SumTree(17), SumTree(17)
            errors = []
            for fn, owner in ((numpy_reference, expected), (lambda b, i, p: b.batch_update(i, p), actual)):
                try:
                    fn(owner, indices, priorities)
                    errors.append(None)
                except Exception as error:
                    errors.append((type(error), str(error)))
            self.assertEqual(errors[0], errors[1])
            self.assert_bits(expected, actual)
        tree = SumTree(17).tree
        before = tree.tobytes()
        self.assertFalse(native.batch_update(tree, 17, np.array([1, 2], np.int64), tree[:2]))
        self.assertEqual(before, tree.tobytes())
        self.assertEqual(native.batch_update_status()["fallback_count"], len(cases) + 1)

    def test_status_success_disabled_unavailable_and_error_semantics(self):
        tree, indices, priorities = SumTree(5).tree, np.array([1], np.int64), np.array([2], np.float64)
        self.assertTrue(native.batch_update(tree, 5, indices, priorities))
        enabled = native.batch_update_status()
        with patch.object(native, "NATIVE_BATCH_ENABLED", False):
            self.assertFalse(native.batch_update(None, None, None, None))
            disabled = native.batch_update_status()
            self.assertFalse(disabled["enabled"])
            self.assertEqual(disabled["completed_count"], enabled["completed_count"])
        with patch.object(native, "_BATCH_FUNCTION", None):
            self.assertFalse(native.batch_update(tree, 5, indices, priorities))
            self.assertFalse(native.batch_update_status()["available"])
        with patch.object(native, "_BATCH_FUNCTION", side_effect=RuntimeError("deliberate native error")):
            with self.assertRaisesRegex(RuntimeError, "deliberate native error"):
                native.batch_update(tree, 5, indices, priorities)
        status = native.batch_update_status()
        self.assertEqual([status[k] for k in ("completed_count", "success_count", "fallback_count", "error_count")], [3, 1, 1, 1])
        status["success_count"] = -999
        self.assertEqual(native.batch_update_status()["success_count"], 1)

    def test_two_callers_have_exact_completed_counts(self):
        def work():
            owner = SumTree(17)
            for _ in range(40):
                owner.batch_update(np.array([1, 2, 1], np.int64), np.array([99, 4, 2], np.float64))
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: work(), range(2)))
        snapshot = native.batch_update_status()
        self.assertEqual(snapshot["success_count"], 80)
        self.assertEqual(snapshot["completed_count"], 80)

    def test_rng_unchanged_and_actual_agent_snapshot_publishes_status(self):
        import torch
        py, numpy, cpu = random.getstate(), np.random.get_state(), torch.get_rng_state().clone()
        owner = SumTree(5)
        owner.batch_update(np.array([1, 3, 1], np.int64), np.array([2, 7, 3], np.float64))
        self.assertEqual(py, random.getstate())
        self.assertTrue(all(np.array_equal(a, b) if isinstance(a, np.ndarray) else a == b
                            for a, b in zip(numpy, np.random.get_state())))
        self.assertTrue(torch.equal(cpu, torch.get_rng_state()))
        source = Path(__file__).with_name("agent.py")
        module = ast.parse(source.read_text())
        cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "RainbowAgent")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "pipeline_telemetry_snapshot")
        namespace = {"unavailable_snapshot": lambda: {"available": False},
                     "disabled_snapshot": lambda: {"ready": False},
                     "batch_update_status": native.batch_update_status}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(method)], type_ignores=[])), str(source), "exec"), namespace)
        class Agent:
            pass
        first = namespace["pipeline_telemetry_snapshot"](Agent())
        second = namespace["pipeline_telemetry_snapshot"](Agent())
        self.assertEqual(first["native_batch_update"], native.batch_update_status())
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
