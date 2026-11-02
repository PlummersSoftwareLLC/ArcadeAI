"""Actual unchanged Python oracle versus offline native prototype, CPU only."""
import ast
import hashlib
from pathlib import Path
import random
import tempfile
import unittest

import numpy as np

from native_batch_update import batch_update, load, try_batch_update


BASE = Path(__file__).resolve().parents[5]
SOURCE = BASE / "Robotron/Scripts/dqn/replay_buffer.py"
MODULE = ast.parse(SOURCE.read_bytes())
SUMTREE = next(n for n in MODULE.body if isinstance(n, ast.ClassDef) and n.name == "SumTree")
NAMESPACE = {"np": np, "_native_propagate": None}
exec(compile(ast.fix_missing_locations(ast.Module(body=[SUMTREE], type_ignores=[])),
             str(SOURCE), "exec"), NAMESPACE)
SumTree = NAMESPACE["SumTree"]
ORIGINAL = SumTree.batch_update


def clone(owner):
    result = SumTree(owner.capacity)
    result.tree[:] = owner.tree
    result.max_priority = owner.max_priority
    return result


class NativeBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load()

    def assert_same(self, expected, actual):
        self.assertEqual(expected.tree.tobytes(), actual.tree.tobytes())
        self.assertEqual(np.float64(expected.max_priority).tobytes(),
                         np.float64(actual.max_priority).tobytes())

    def compare(self, owner, indices, priorities, accepted=None):
        expected, actual = clone(owner), clone(owner)
        expected_error = actual_error = None
        try:
            ORIGINAL(expected, indices, priorities)
        except Exception as error:
            expected_error = (type(error), str(error))
        try:
            used = batch_update(actual, indices, priorities, ORIGINAL)
        except Exception as error:
            actual_error = (type(error), str(error))
            used = None
        self.assertEqual(expected_error, actual_error)
        self.assert_same(expected, actual)
        if accepted is not None:
            self.assertEqual(used, accepted)
        return actual

    def test_sequential_odd_nonpower_and_capacity1_full_tree_bytes(self):
        rng = np.random.default_rng(29261016)
        for capacity in (1, 2, 3, 5, 7, 9, 15, 17, 31, 63, 127, 513, 4097):
            owner = SumTree(capacity)
            # Deliberately inconsistent internals catch same-frontier overlap.
            owner.tree[:] = rng.uniform(-10000, 10000, owner.tree.size)
            for _ in range(24):
                count = max(1, min(256, capacity * 2))
                indices = rng.integers(0, capacity, count, dtype=np.int64)
                priorities = rng.uniform(-30, 30, count).astype(np.float64)
                owner = self.compare(owner, indices, priorities, accepted=True)

    def test_adversarial_same_frontier_parent_child_is_staged(self):
        owner = SumTree(5)
        owner.tree[:] = np.array([123, 456, 1000, 2000, 3000, 1, 2, 3, 4, 5], np.float64)
        indices = np.array([0, 1, 3], np.int64)  # first parents2,3,4 overlap
        priorities = np.array([7, 11, 13], np.float64)
        result = self.compare(owner, indices, priorities, accepted=True)
        # At the first frontier, parent2 uses OLD parent4=3000, not new18.
        self.assertEqual(result.tree[2], result.tree[4] + result.tree[5])

    def test_duplicate_last_leaf_wins_max_uses_overwritten_high_value(self):
        owner = SumTree(5)
        result = self.compare(owner, np.array([2, 2, 2], np.int64),
                              np.array([99, 12, 3], np.float64), accepted=True)
        self.assertEqual(result.tree[7], 3)
        self.assertEqual(result.max_priority, 99)

    def test_signed_zero_subnormal_extreme_and_nonfinite_old_tree_bits(self):
        patterns = np.array([0, 0x8000000000000000, 1, 0x8000000000000001,
                             0x7fefffffffffffff, 0xffefffffffffffff,
                             0x7ff0000000000000, 0xfff0000000000000,
                             0x7ff8000000000001, 0x7ff8000000000002], dtype=np.uint64)
        values = patterns.view(np.float64)
        for capacity in (5, 17, 513):
            owner = SumTree(capacity)
            owner.tree[:] = np.resize(values, owner.tree.size)
            with np.errstate(invalid="ignore", over="ignore", under="ignore"):
                for indices in (np.array([0, 2, 4, 0], np.int64),
                                np.array([capacity - 1, 1, capacity - 1], np.int64)):
                    priorities = np.resize(np.array([-0.0, 0.0, 1e-300, -1e-300]), len(indices))
                    owner = self.compare(owner, indices, priorities, accepted=True)

    def test_input_dtype_shape_stride_and_error_fallback_matches_oracle(self):
        owner = SumTree(11)
        cases = [
            (np.array([1, 2], np.int32), np.array([2, 3], np.float64)),
            (np.array([1, 2], np.int64), np.array([2, 3], np.float32)),
            (np.arange(6, dtype=np.int64)[::2], np.array([2, 3, 4], np.float64)),
            (np.array([1, 2], np.int64), np.arange(4, dtype=np.float64)[::2]),
            (np.array([1, 2], np.int64), np.array([2], np.float64)),
            (np.array([[1, 2]], np.int64), np.array([[2, 3]], np.float64)),
            (np.array([], np.int64), np.array([], np.float64)),
            (np.array([-1, 1], np.int64), np.array([2, 3], np.float64)),
            (np.array([1, 11], np.int64), np.array([2, 3], np.float64)),
            (np.array([1, 2], np.int64), np.array([np.nan, 3], np.float64)),
            (np.array([1, 2], np.int64), np.array([np.inf, 3], np.float64)),
        ]
        for indices, priorities in cases:
            with self.subTest(dtype=indices.dtype, shape=indices.shape,
                              priorities=priorities):
                self.compare(owner, indices, priorities)
                before = owner.tree.tobytes()
                self.assertFalse(try_batch_update(owner.tree, owner.capacity, indices, priorities))
                self.assertEqual(owner.tree.tobytes(), before)

    def test_tree_alias_readonly_wrong_geometry_and_dtype_reject_without_write(self):
        owner = SumTree(5)
        indices, priorities = np.array([1, 2], np.int64), np.array([2, 3], np.float64)
        views = [(owner.tree, 6, indices, priorities),
                 (owner.tree.astype(np.float32), 5, indices, priorities),
                 (owner.tree[::-1], 5, indices, priorities),
                 (owner.tree, 5, indices, owner.tree[:2]),
                 (owner.tree, 5, owner.tree.view(np.int64)[:2], priorities)]
        for tree, capacity, idx, pri in views:
            before = tree.tobytes()
            self.assertFalse(try_batch_update(tree, capacity, idx, pri))
            self.assertEqual(before, tree.tobytes())
        owner.tree.flags.writeable = False
        self.assertFalse(try_batch_update(owner.tree, 5, indices, priorities))

    def test_sentinel_filtered_actual_update_priorities_preserves_full_tree(self):
        cls = next(n for n in MODULE.body if isinstance(n, ast.ClassDef) and n.name == "PrioritizedReplayBuffer")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "update_priorities")
        namespace = {"np": np}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                     str(SOURCE), "exec"), namespace)
        import threading
        class Buffer:
            pass
        rng = np.random.default_rng(35113)
        expected, actual = Buffer(), Buffer()
        for b in (expected, actual):
            b.capacity, b.alpha, b.lock, b.tree = 513, 0.6, threading.Lock(), SumTree(513)
        class NativeTree:
            def __init__(self, owner):
                self.owner = owner
            def batch_update(self, indices, priorities):
                return batch_update(self.owner, indices, priorities, ORIGINAL)
        native_owner = actual.tree
        actual.tree = NativeTree(native_owner)
        for _ in range(40):
            indices = rng.integers(0, 1026, 256, dtype=np.int64)
            errors = rng.uniform(-10, 10, 256).astype(np.float32)
            namespace["update_priorities"](expected, indices, errors)
            namespace["update_priorities"](actual, indices, errors)
            self.assert_same(expected.tree, native_owner)

    def test_writable_memmap_and_readonly_inputs(self):
        expected = SumTree(17)
        with tempfile.TemporaryDirectory() as directory:
            actual = clone(expected)
            actual.tree = np.memmap(Path(directory) / "tree.dat", mode="w+", shape=(34,), dtype=np.float64)
            actual.tree[:] = expected.tree
            indices = np.array([0, 16, 0, 7], np.int64)
            priorities = np.array([9, 7, 2, 4], np.float64)
            indices.flags.writeable = priorities.flags.writeable = False
            ORIGINAL(expected, indices, priorities)
            self.assertTrue(batch_update(actual, indices, priorities, ORIGINAL))
            self.assert_same(expected, actual)

    def test_numpy_python_and_torch_cpu_rng_unchanged(self):
        import torch
        py, numpy, cpu = random.getstate(), np.random.get_state(), torch.get_rng_state().clone()
        owner = SumTree(5)
        self.compare(owner, np.array([1, 3, 1], np.int64), np.array([2, 7, 3], np.float64), accepted=True)
        self.assertEqual(py, random.getstate())
        after = np.random.get_state()
        self.assertTrue(all(np.array_equal(a, b) if isinstance(a, np.ndarray) else a == b
                            for a, b in zip(numpy, after)))
        self.assertTrue(torch.equal(cpu, torch.get_rng_state()))
        self.assertFalse(torch.cuda.is_initialized())


if __name__ == "__main__":
    unittest.main()
