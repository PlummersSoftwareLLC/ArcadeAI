"""CPU bitwise tests for optional native sum-tree propagation.

Load just the actual SumTree class so these checks need no trainer configuration,
model imports, CUDA context, or allocated replay ring. Run directly with Python.
"""

import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

try:
    from . import native_sumtree
except ImportError:
    import native_sumtree


def load_sumtree(propagate):
    path = Path(__file__).with_name("replay_buffer.py")
    module = ast.parse(path.read_text())
    definition = next(node for node in module.body
                      if isinstance(node, ast.ClassDef) and node.name == "SumTree")
    code = compile(ast.Module(body=[definition], type_ignores=[]), str(path), "exec")
    namespace = {"np": np, "_native_propagate": propagate,
                 "_native_batch_update": None}
    exec(code, namespace)
    return namespace["SumTree"]


class TestNativeSumTree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.PythonTree = load_sumtree(None)
        cls.NativeTree = load_sumtree(native_sumtree.propagate)

    def require_native(self):
        if not native_sumtree.NATIVE_AVAILABLE:
            self.skipTest(native_sumtree.NATIVE_STATUS)

    def assert_tree_bits(self, python, native):
        np.testing.assert_array_equal(python.tree.view(np.uint64), native.tree.view(np.uint64))
        self.assertEqual(
            (python.data_ptr, python.size, python.max_priority),
            (native.data_ptr, native.size, native.max_priority),
        )

    def test_random_add_update_exact_bits_and_sample_indices(self):
        self.require_native()
        random = np.random.default_rng(42)
        capacities = (1, 2, 3, 5, 17, 33, 997, 1024, 65537)
        for capacity in capacities:
            with self.subTest(capacity=capacity):
                python, native = self.PythonTree(capacity), self.NativeTree(capacity)
                for step in range(1200):
                    # Broad magnitudes make reassociation/arithmetic changes
                    # visible even when a loose numeric comparison would pass.
                    priority = float(10.0 ** random.uniform(-15, 15))
                    if step < 400 or random.random() < 0.4:
                        self.assertEqual(python.add(priority), native.add(priority))
                    else:
                        index = int(random.integers(capacity))
                        python.update(index, priority)
                        native.update(index, priority)
                    if step % 40 == 0:
                        self.assert_tree_bits(python, native)
                self.assert_tree_bits(python, native)
                values = np.linspace(0, python.total(), 100)
                np.testing.assert_array_equal(python.batch_get(values), native.batch_get(values))
                self.assertEqual(
                    [python.get(float(value)) for value in values],
                    [native.get(float(value)) for value in values],
                )

    def test_array_replacement_never_uses_cached_pointer(self):
        self.require_native()
        random = np.random.default_rng(7)
        for capacity in (1, 3, 17, 997, 65537):
            with self.subTest(capacity=capacity):
                python, native = self.PythonTree(capacity), self.NativeTree(capacity)
                for _ in range(100):
                    priority = float(random.uniform(0, 100))
                    python.add(priority)
                    native.add(priority)
                for _ in range(8):
                    retained = native.tree
                    retained_bits = retained.copy()
                    native.tree = native.tree.copy()
                    python.tree = python.tree.copy()
                    self.assertNotEqual(retained.ctypes.data, native.tree.ctypes.data)
                    index = int(random.integers(capacity))
                    priority = float(random.uniform(100, 200))
                    python.update(index, priority)
                    native.update(index, priority)
                    self.assert_tree_bits(python, native)
                    np.testing.assert_array_equal(retained, retained_bits)

    def test_batch_priority_updates_remain_exact(self):
        self.require_native()
        random = np.random.default_rng(15)
        for capacity in (3, 17, 1000):
            with self.subTest(capacity=capacity):
                python, native = self.PythonTree(capacity), self.NativeTree(capacity)
                for _ in range(capacity):
                    priority = float(random.uniform(0.01, 10))
                    python.add(priority)
                    native.add(priority)
                for _ in range(20):
                    indices = random.integers(capacity, size=64)
                    priorities = random.uniform(0.001, 1000, size=64)
                    python.batch_update(indices, priorities)
                    native.batch_update(indices, priorities)
                    self.assert_tree_bits(python, native)

    def test_unavailable_helper_keeps_python_fallback(self):
        with patch.object(native_sumtree, "_FUNCTION", None):
            array = np.zeros(16, dtype=np.float64)
            self.assertFalse(native_sumtree.propagate(array, 9))
            python, native = self.PythonTree(17), self.NativeTree(17)
            for value in (0.1, 1e-15, 1e15, 17.3, 4.0) * 20:
                python.add(value)
                native.add(value)
            self.assert_tree_bits(python, native)

    def test_unsupported_layouts_decline_native(self):
        # Declining unsupported layouts leaves their original Python semantics.
        self.assertFalse(native_sumtree.propagate(np.zeros(16, dtype=np.float32), 9))
        self.assertFalse(native_sumtree.propagate(np.zeros(32, dtype=np.float64)[::2], 9))
        self.assertFalse(native_sumtree.propagate(np.zeros((4, 4), dtype=np.float64), 9))
        array = np.zeros(16, dtype=np.float64)
        array.flags.writeable = False
        self.assertFalse(native_sumtree.propagate(array, 9))
        self.assertFalse(native_sumtree.propagate(np.zeros(16, dtype=np.float64), 16))

    def require_native_gather(self):
        if not native_sumtree.NATIVE_GATHER_AVAILABLE:
            self.skipTest("Direct fp16 gathering requires ARM Neoverse-V2")

    def assert_half_conversion(self, actual, expected):
        self.assertEqual(actual.dtype, np.dtype(np.float32))
        np.testing.assert_array_equal(np.isnan(actual), np.isnan(expected))
        # IEEE signaling-NaN conversion can quiet its payload differently from
        # NumPy's software conversion. Every non-NaN bit, including signed zero,
        # infinities, and subnormals, must match the existing fp32 representation.
        finite_or_infinite = ~np.isnan(expected)
        np.testing.assert_array_equal(
            actual[finite_or_infinite].view(np.uint32),
            expected[finite_or_infinite].view(np.uint32),
        )

    def test_all_fp16_patterns_have_exact_non_nan_conversion(self):
        self.require_native_gather()
        source = np.arange(65536, dtype=np.uint16).reshape(256, 256).view(np.float16)
        indices = np.arange(256, dtype=np.int64)
        with np.errstate(invalid="ignore"):
            expected = source[indices].astype(np.float32)
            actual = native_sumtree.gather_fp16_rows(source, indices)
        self.assertIsNotNone(actual)
        self.assert_half_conversion(actual, expected)

    def test_random_fp16_rows_duplicates_empty_and_readonly_memmap(self):
        self.require_native_gather()
        random = np.random.default_rng(32)
        source = random.standard_normal((127, 73)).astype(np.float16)
        indices = random.integers(0, len(source), size=256, dtype=np.int64)
        self.assert_half_conversion(
            native_sumtree.gather_fp16_rows(source, indices), source[indices].astype(np.float32),
        )
        empty = native_sumtree.gather_fp16_rows(source, np.empty(0, dtype=np.int64))
        self.assertEqual(empty.shape, (0, 73))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "states.npy"
            np.save(path, source)
            readonly = np.load(path, mmap_mode="r")
            self.assertFalse(readonly.flags.writeable)
            self.assert_half_conversion(
                native_sumtree.gather_fp16_rows(readonly, indices), source[indices].astype(np.float32),
            )

    def test_fp16_gather_bounds_and_layout_fallback(self):
        source = np.zeros((10, 16), dtype=np.float16)
        invalid_indices = (
            np.array([-1], dtype=np.int64), np.array([10], dtype=np.int64),
            np.array([2**62], dtype=np.int64), np.array([0], dtype=np.int32),
            np.arange(4, dtype=np.int64)[::2],
        )
        for indices in invalid_indices:
            self.assertIsNone(native_sumtree.gather_fp16_rows(source, indices))
        valid_indices = np.array([0, 9], dtype=np.int64)
        for unsupported in (source.astype(np.float32), source[:, ::2], source.astype(">f2")):
            self.assertIsNone(native_sumtree.gather_fp16_rows(unsupported, valid_indices))
        with patch.object(native_sumtree, "_GATHER_FUNCTION", None):
            self.assertIsNone(native_sumtree.gather_fp16_rows(source, valid_indices))

    def test_preallocated_gather_preserves_storage_and_rejects_unsafe_outputs(self):
        self.require_native_gather()
        source = np.arange(80, dtype=np.float16).reshape(10, 8)
        source.flags.writeable = False
        indices = np.array([9, 2, 2], dtype=np.int64)
        output = np.empty((3, 8), dtype=np.float32)
        self.assertIs(native_sumtree.gather_fp16_rows(source, indices, out=output), output)
        self.assert_half_conversion(output, source[indices].astype(np.float32))
        invalid = [np.empty((3, 8), dtype=np.float16), np.empty((8, 3), dtype=np.float32),
                   np.empty((3, 16), dtype=np.float32)[:, ::2]]
        readonly = output.copy(); readonly.flags.writeable = False
        invalid.append(readonly)
        invalid.append(np.ndarray((3, 8), dtype=np.float32, buffer=bytearray(3*8*4+1), offset=1))
        for out in invalid:
            self.assertIsNone(native_sumtree.gather_fp16_rows(source, indices, out=out))
        empty = np.empty((0, 8), dtype=np.float32)
        self.assertIs(native_sumtree.gather_fp16_rows(source, indices[:0], out=empty), empty)
        aliased = np.zeros((16, 8), dtype=np.float32)
        source_alias = aliased.view(np.float16).reshape(32, 8)
        self.assertIsNone(native_sumtree.gather_fp16_rows(source_alias, indices, out=aliased[:3]))
        invalid_indices = np.array([0, 2, 100], dtype=np.int64)
        output.fill(731)
        self.assertIsNone(native_sumtree.gather_fp16_rows(source, invalid_indices, out=output))
        np.testing.assert_array_equal(output, np.full((3, 8), 731, dtype=np.float32))


if __name__ == "__main__":
    unittest.main(verbosity=2)
