"""CPU-only actual proposed sources: exact output and bounded status evidence."""
import ast
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest import mock

import numpy as np


DIRECTORY = Path(__file__).resolve().parent
V1 = DIRECTORY.with_name("native-batch-prototype")
BASE = DIRECTORY.parents[4]
sys.path.insert(0, str(V1))
import test_native_batch_update as oracle


def helper(name, enabled="1"):
    with mock.patch.dict(os.environ, {}):
        if enabled is None:
            os.environ.pop("DQN_NATIVE_BATCH_UPDATE", None)
        else:
            os.environ["DQN_NATIVE_BATCH_UPDATE"] = enabled
        spec = importlib.util.spec_from_file_location(name, DIRECTORY / "proposed/native_sumtree.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


HELPER = helper("observed_native_oracle")
REPLAY_AST = ast.parse((DIRECTORY / "proposed/replay_buffer.py").read_bytes())
TREE_CLASS = next(n for n in REPLAY_AST.body if isinstance(n, ast.ClassDef) and n.name == "SumTree")
NAMESPACE = {"np": np, "_native_propagate": None, "_native_batch_update": HELPER.batch_update}
exec(compile(ast.fix_missing_locations(ast.Module(body=[TREE_CLASS], type_ignores=[])),
             "proposed/replay_buffer.py", "exec"), NAMESPACE)
METHOD = NAMESPACE["SumTree"].batch_update
AGENT_AST = ast.parse((DIRECTORY / "proposed/agent.py").read_bytes())
AGENT_CLASS = next(n for n in AGENT_AST.body if isinstance(n, ast.ClassDef) and n.name == "RainbowAgent")
SNAPSHOT_METHOD = next(n for n in AGENT_CLASS.body if isinstance(n, ast.FunctionDef) and n.name == "pipeline_telemetry_snapshot")


def integrated(owner, indices, priorities, original):
    decisions = []
    def route(*args):
        used = HELPER.batch_update(*args)
        decisions.append(used)
        return used
    NAMESPACE["_native_batch_update"] = route
    try:
        METHOD(owner, indices, priorities)
    finally:
        NAMESPACE["_native_batch_update"] = HELPER.batch_update
    return any(decisions)


class ExactOutputTests(oracle.NativeBatchTests):
    @classmethod
    def setUpClass(cls):
        assert HELPER.NATIVE_BATCH_ENABLED and HELPER.NATIVE_BATCH_AVAILABLE
        cls.saved = oracle.batch_update, oracle.try_batch_update, oracle.load
        oracle.batch_update = integrated
        oracle.try_batch_update = HELPER.batch_update
        oracle.load = lambda: HELPER._BATCH_FUNCTION

    @classmethod
    def tearDownClass(cls):
        oracle.batch_update, oracle.try_batch_update, oracle.load = cls.saved


class StatusAndScopeTests(unittest.TestCase):
    def setUp(self):
        self.helper = helper("observed_native_" + self._testMethodName)

    def update(self, *, indices=None, priorities=None):
        owner = oracle.SumTree(17)
        indices = np.array([1, 4, 1], np.int64) if indices is None else indices
        priorities = np.array([99, 5, 2], np.float64) if priorities is None else priorities
        return self.helper.batch_update(owner.tree, owner.capacity, indices, priorities)

    def test_enabled_success_fallback_and_snapshot_copy_are_cumulative(self):
        before = self.helper.batch_update_status()
        self.assertTrue(before["enabled"] and before["available"])
        self.assertEqual(before["completed_count"], 0)
        self.assertTrue(self.update())
        self.assertFalse(self.update(priorities=np.array([1, 2, 3], np.float32)))
        first = self.helper.batch_update_status()
        self.assertEqual([first[k] for k in ("completed_count", "success_count", "fallback_count", "error_count")], [2, 1, 1, 0])
        first["success_count"] = -999
        self.assertEqual(self.helper.batch_update_status()["success_count"], 1)
        self.assertTrue(self.update())
        self.assertEqual(self.helper.batch_update_status()["completed_count"], 3)

    def test_disabled_calls_skip_counter_lock_and_getter_never_resets(self):
        disabled = helper("observed_native_disabled", None)
        class ForbiddenLock:
            def __enter__(self):
                raise AssertionError("Disabled call touched stats lock")
            def __exit__(self, *args):
                pass
        with mock.patch.object(disabled, "_BATCH_STATS_LOCK", ForbiddenLock()):
            self.assertFalse(disabled.batch_update(None, None, None, None))
        first, second = disabled.batch_update_status(), disabled.batch_update_status()
        self.assertEqual(first, second)
        self.assertFalse(first["enabled"])
        self.assertEqual(first["completed_count"], 0)

    def test_unavailable_startup_and_native_rejection_count_fallback(self):
        with mock.patch("ctypes.CDLL", side_effect=OSError("deliberate unavailable library")):
            unavailable = helper("observed_native_unavailable")
        owner = oracle.SumTree(17)
        indices, priorities = np.array([1], np.int64), np.array([2], np.float64)
        old = owner.tree.tobytes()
        self.assertFalse(unavailable.batch_update(owner.tree, 17, indices, priorities))
        status = unavailable.batch_update_status()
        self.assertFalse(status["available"])
        self.assertEqual(status["fallback_count"], 1)
        self.assertEqual(old, owner.tree.tobytes())
        with mock.patch.object(self.helper, "_BATCH_FUNCTION", return_value=0):
            self.assertFalse(self.update())
        self.assertEqual(self.helper.batch_update_status()["fallback_count"], 1)

    def test_unexpected_exception_counted_and_reraised_without_fallback(self):
        with mock.patch.object(self.helper, "_BATCH_FUNCTION", side_effect=RuntimeError("deliberate native error")):
            with self.assertRaisesRegex(RuntimeError, "deliberate native error"):
                self.update()
        status = self.helper.batch_update_status()
        self.assertEqual([status[k] for k in ("completed_count", "success_count", "fallback_count", "error_count")], [1, 0, 0, 1])

    def test_concurrent_private_trees_have_exact_counts_and_atomic_snapshots(self):
        def work():
            for _ in range(50):
                self.assertTrue(self.update())
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(work) for _ in range(2)]
            previous = 0
            for _ in range(100):
                snapshot = self.helper.batch_update_status()
                self.assertGreaterEqual(snapshot["completed_count"], previous)
                self.assertEqual(snapshot["completed_count"], sum(snapshot[k] for k in ("success_count", "fallback_count", "error_count")))
                previous = snapshot["completed_count"]
            for future in futures:
                future.result(timeout=3)
        status = self.helper.batch_update_status()
        self.assertEqual(status["completed_count"], 100)
        self.assertEqual(status["success_count"], 100)

    def test_status_getter_takes_no_replay_or_model_lock(self):
        # The function is a scalar snapshot and its AST has no torch/owner call.
        module = ast.parse((DIRECTORY / "proposed/native_sumtree.py").read_bytes())
        getter = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "batch_update_status")
        names = {n.id for n in ast.walk(getter) if isinstance(n, ast.Name)}
        self.assertFalse(names & {"torch", "self", "tree", "memory"})
        self.assertEqual(self.helper.batch_update_status()["completed_count"], 0)

    def test_actual_agent_snapshot_exposes_same_helper_after_other_locks_release(self):
        active = []
        class Recorder:
            def snapshot(self, reset=False):
                self_reset.append(reset)
                active.append("recorder")
                result = {"schema": "host-test", "available": True}
                active.pop()
                return result
        class Graphs:
            def snapshot(self):
                self_outer.assertFalse(active)
                active.append("graphs")
                result = {"ready": True}
                active.pop()
                return result
        self_outer, self_reset = self, []
        namespace = {"unavailable_snapshot": lambda: {"available": False},
                     "disabled_snapshot": lambda: {"ready": False}}
        def native_snapshot():
            self.assertFalse(active)
            return self.helper.batch_update_status()
        namespace["batch_update_status"] = native_snapshot
        exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(SNAPSHOT_METHOD)], type_ignores=[])),
                     "proposed/agent.py", "exec"), namespace)
        class Agent:
            pass
        agent = Agent()
        agent._pipeline_telemetry, agent._exact_inference_graphs = Recorder(), Graphs()
        self.assertTrue(self.update())
        first = namespace["pipeline_telemetry_snapshot"](agent)
        self.assertEqual(first["native_batch_update"]["success_count"], 1)
        self.assertEqual(self_reset, [False])
        second = namespace["pipeline_telemetry_snapshot"](agent)
        self.assertEqual(first["native_batch_update"], second["native_batch_update"])
        json.dumps(first)

    def test_agent_AST_has_only_two_imports_and_one_snapshot_field_added(self):
        original = ast.parse((DIRECTORY / "before/agent.py").read_bytes())
        edited = copy.deepcopy(AGENT_AST)
        class StripStatus(ast.NodeTransformer):
            def visit_ImportFrom(self, node):
                if node.module == "native_sumtree" and [a.name for a in node.names] == ["batch_update_status"]:
                    return None
                return node
            def visit_Assign(self, node):
                if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript)
                        and isinstance(node.targets[0].value, ast.Name) and node.targets[0].value.id == "snapshot"
                        and isinstance(node.targets[0].slice, ast.Constant) and node.targets[0].slice.value == "native_batch_update"):
                    return None
                return self.generic_visit(node)
        self.assertEqual(ast.dump(original), ast.dump(StripStatus().visit(edited)))
        for source in (AGENT_AST, REPLAY_AST):
            imports = [n for n in ast.walk(source) if isinstance(n, ast.ImportFrom) and n.module == "native_sumtree"]
            self.assertEqual({n.level for n in imports}, {0, 1})

    def test_C_replay_prior_artifacts_and_live_sources_are_preserved(self):
        manifest = json.loads((DIRECTORY / "integration-prepared.json").read_text())
        v1_manifest = json.loads((V1 / "integration-prepared.json").read_text())
        self.assertEqual(manifest["prior_patch_sha256"], v1_manifest["patch_sha256"])
        for name in ("sumtree.c", "replay_buffer.py"):
            self.assertEqual((DIRECTORY / "proposed" / name).read_bytes(), (V1 / "proposed" / name).read_bytes())
        for name, record in manifest["sources"].items():
            self.assertEqual(hashlib.sha256((BASE / name).read_bytes()).hexdigest(), record["before_sha256"])
        pinned = json.loads((V1 / "prepared-validation.json").read_text())["artifact_sha256"]
        for name, expected in pinned.items():
            self.assertEqual(hashlib.sha256((V1 / name).read_bytes()).hexdigest(), expected)
        subprocess.run(["git", "apply", "--check", str(DIRECTORY / "native-batch-observed-v2.patch")],
                       cwd=BASE, check=True, capture_output=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
