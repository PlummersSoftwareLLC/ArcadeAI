"""Exercise proposed helper/hook copies; production source remains untouched."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import numpy as np

import test_native_batch_update as oracle_tests


DIRECTORY = Path(__file__).resolve().parent
BASE = DIRECTORY.parents[4]


def import_helper(name, enabled):
    environment = {} if enabled is None else {"DQN_NATIVE_BATCH_UPDATE": enabled}
    with mock.patch.dict(os.environ, environment):
        if enabled is None:
            os.environ.pop("DQN_NATIVE_BATCH_UPDATE", None)
        spec = importlib.util.spec_from_file_location(name, DIRECTORY / "proposed/native_sumtree.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


HELPER = import_helper("prepared_native_enabled", "1")
PROPOSED_AST = ast.parse((DIRECTORY / "proposed/replay_buffer.py").read_bytes())
PROPOSED_CLASS = next(n for n in PROPOSED_AST.body if isinstance(n, ast.ClassDef) and n.name == "SumTree")
NAMESPACE = {"np": np, "_native_propagate": None, "_native_batch_update": HELPER.batch_update}
exec(compile(ast.fix_missing_locations(ast.Module(body=[PROPOSED_CLASS], type_ignores=[])),
             "proposed/replay_buffer.py", "exec"), NAMESPACE)
PROPOSED_METHOD = NAMESPACE["SumTree"].batch_update


def integrated(owner, indices, priorities, original):
    decisions = []
    def route(*args):
        used = HELPER.batch_update(*args)
        decisions.append(used)
        return used
    NAMESPACE["_native_batch_update"] = route
    try:
        PROPOSED_METHOD(owner, indices, priorities)
    finally:
        NAMESPACE["_native_batch_update"] = HELPER.batch_update
    return any(decisions)


class ActualProposedSourceTests(oracle_tests.NativeBatchTests):
    @classmethod
    def setUpClass(cls):
        if not HELPER.NATIVE_BATCH_AVAILABLE or not HELPER.NATIVE_BATCH_ENABLED:
            raise AssertionError("The proposed opt-in helper must be available for these tests")
        cls.saved = oracle_tests.batch_update, oracle_tests.try_batch_update, oracle_tests.load
        oracle_tests.batch_update = integrated
        oracle_tests.try_batch_update = HELPER.batch_update
        oracle_tests.load = lambda: HELPER._BATCH_FUNCTION

    @classmethod
    def tearDownClass(cls):
        oracle_tests.batch_update, oracle_tests.try_batch_update, oracle_tests.load = cls.saved


class IntegrationScopeTests(unittest.TestCase):
    def test_default_off_and_unavailable_library_take_unchanged_fallback(self):
        disabled = import_helper("prepared_native_disabled", None)
        self.assertFalse(disabled.NATIVE_BATCH_ENABLED)
        for helper in (disabled, HELPER):
            with mock.patch.object(helper, "_BATCH_FUNCTION", None):
                expected, actual = oracle_tests.SumTree(5), oracle_tests.SumTree(5)
                indices = np.array([1, 1, 4], np.int64)
                priorities = np.array([99, 3, 2], np.float64)
                before = actual.tree.tobytes()
                self.assertFalse(helper.batch_update(actual.tree, 5, indices, priorities))
                self.assertEqual(before, actual.tree.tobytes())
                oracle_tests.ORIGINAL(expected, indices, priorities)
                NAMESPACE["_native_batch_update"] = helper.batch_update
                try:
                    PROPOSED_METHOD(actual, indices, priorities)
                finally:
                    NAMESPACE["_native_batch_update"] = HELPER.batch_update
                self.assertEqual(expected.tree.tobytes(), actual.tree.tobytes())
                self.assertEqual(expected.max_priority, actual.max_priority)

    def test_actual_startup_CDLL_error_is_caught_and_helper_returns_false(self):
        with mock.patch("ctypes.CDLL", side_effect=OSError("deliberate unavailable library")):
            unavailable = import_helper("prepared_native_unavailable", "1")
        self.assertFalse(unavailable.NATIVE_BATCH_AVAILABLE)
        self.assertIsNone(unavailable._BATCH_FUNCTION)
        self.assertIn("Python fallback", unavailable.NATIVE_STATUS)
        owner = oracle_tests.SumTree(5)
        before = owner.tree.tobytes()
        self.assertFalse(unavailable.batch_update(owner.tree, 5, np.array([1], np.int64), np.array([2], np.float64)))
        self.assertEqual(before, owner.tree.tobytes())

    def test_disabled_import_preserves_existing_native_status_and_functions(self):
        disabled = import_helper("prepared_native_disabled_status", "0")
        self.assertTrue(disabled.NATIVE_AVAILABLE)
        self.assertTrue(disabled.NATIVE_BATCH_AVAILABLE)
        self.assertFalse(disabled.NATIVE_BATCH_ENABLED)
        self.assertTrue(disabled.NATIVE_STATUS.startswith("exact float64 native propagation"))
        tree = np.ones(10, dtype=np.float64)
        self.assertTrue(disabled.propagate(tree, 7))
        self.assertEqual(tree[3], 2.0)

    def test_native_and_replay_fallback_ASTs_and_C_functions_unchanged(self):
        before = ast.parse((DIRECTORY / "before/native_sumtree.py").read_bytes())
        after = ast.parse((DIRECTORY / "proposed/native_sumtree.py").read_bytes())
        for name in ("_neoverse_v2", "propagate", "gather_fp16_rows"):
            old = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name)
            new = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertEqual(ast.dump(old), ast.dump(new))
        old_method = next(n for n in oracle_tests.SUMTREE.body if isinstance(n, ast.FunctionDef) and n.name == "batch_update")
        new_method = next(n for n in PROPOSED_CLASS.body if isinstance(n, ast.FunctionDef) and n.name == "batch_update")
        self.assertIsInstance(new_method.body[1], ast.If)
        restored = ast.FunctionDef(name=new_method.name, args=new_method.args,
                                  body=[new_method.body[0]] + new_method.body[2:],
                                  decorator_list=new_method.decorator_list)
        # Function type_params are empty on the free-threaded Python3.14 build.
        for name in ("returns", "type_comment", "type_params"):
            if hasattr(old_method, name):
                setattr(restored, name, getattr(old_method, name))
        self.assertEqual(ast.dump(old_method), ast.dump(restored))
        old_c = (DIRECTORY / "before/sumtree.c").read_text()
        new_c = (DIRECTORY / "proposed/sumtree.c").read_text()
        self.assertTrue(new_c.replace("#include <stddef.h>\n#include <stdlib.h>\n", "", 1).startswith(old_c.rstrip()))

    def test_unsupported_tree_dtype_stride_and_readonly_fallback(self):
        indices, priorities = np.array([1, 1, 7], np.int64), np.array([99, 3, 2], np.float64)
        for kind in ("float32", "strided", "readonly"):
            expected, actual = oracle_tests.SumTree(11), oracle_tests.SumTree(11)
            for owner in (expected, actual):
                if kind == "float32":
                    owner.tree = owner.tree.astype(np.float32)
                elif kind == "strided":
                    owner.tree = np.zeros(44, dtype=np.float64)[::2]
                else:
                    owner.tree.flags.writeable = False
            errors = []
            for fn, owner in ((oracle_tests.ORIGINAL, expected), (PROPOSED_METHOD, actual)):
                try:
                    fn(owner, indices, priorities)
                    errors.append(None)
                except Exception as error:
                    errors.append((type(error), str(error)))
            self.assertEqual(errors[0], errors[1])
            self.assertEqual(expected.tree.tobytes(), actual.tree.tobytes())
            self.assertEqual(expected.max_priority, actual.max_priority)

    def test_patch_checks_cleanly_and_production_hashes_unchanged(self):
        manifest = json.loads((DIRECTORY / "integration-prepared.json").read_text())
        for name, record in manifest["sources"].items():
            self.assertEqual(hashlib.sha256((BASE / name).read_bytes()).hexdigest(), record["before_sha256"])
        subprocess.run(["git", "apply", "--check", str(DIRECTORY / "native-batch-default-off.patch")],
                       cwd=BASE, check=True, capture_output=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
