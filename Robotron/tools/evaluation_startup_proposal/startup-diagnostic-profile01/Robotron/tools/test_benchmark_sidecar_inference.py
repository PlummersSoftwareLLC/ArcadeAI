"""Pure standard-library tests; no Torch import, GPU, MAME or compiler."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import benchmark_sidecar_inference as bench


class SidecarCompilePlanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        checkpoint = self.root / "checkpoint.pt"
        checkpoint.write_bytes(b"fixture only; plan must not load it")
        self.plan = bench.Plan(checkpoint, self.root / "output")

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_plan_is_readonly_and_imports_no_numerical_runtime(self):
        script = ("import sys,json; from Robotron.tools.benchmark_sidecar_inference import main;"
                  "main(sys.argv[1:]); assert 'torch' not in sys.modules; assert 'numpy' not in sys.modules")
        output = subprocess.check_output([sys.executable, "-c", script, "--checkpoint", str(self.plan.checkpoint),
                                          "--directory", str(self.plan.directory)], text=True)
        plan = json.loads(output)
        self.assertEqual(plan["compile_threads"], 2)
        self.assertEqual(plan["warm_shapes"], [1, 2, 4, 8, 16])
        self.assertFalse(plan["compile_options"]["triton.cudagraphs"])
        self.assertFalse(plan["autocast"])
        self.assertFalse(plan["mame"])
        self.assertFalse(self.plan.directory.exists())

    def test_bounds_and_gb300_exclusion(self):
        for changes in (dict(gpu_uuid="GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1"),
                        dict(repetitions=31), dict(repetitions=2), dict(sample_rows=513),
                        dict(sample_rows=15), dict(directory=bench.GAME / "models_dqn/unsafe-bench")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.plan, **changes).validate()
        self.plan.directory.mkdir()
        with self.assertRaises(ValueError):
            self.plan.validate()

    def test_cuda_uuid_prefix_representation_is_normalized_without_relaxing_identity(self):
        self.assertEqual(bench.canonical_uuid(bench.GPU0_UUID),
                         bench.canonical_uuid(bench.GPU0_UUID.removeprefix("GPU-").upper()))
        self.assertNotEqual(bench.canonical_uuid(bench.GPU0_UUID),
                            bench.canonical_uuid("GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1"))

    def test_active_gpu0_owner_rejected_while_gb300_owner_is_ignored(self):
        with patch.object(bench.subprocess, "check_output", return_value=f"123, {bench.GPU0_UUID}\n"):
            with self.assertRaisesRegex(RuntimeError, "active compute owner"):
                bench.require_idle_gpu(self.plan)
        with patch.object(bench.subprocess, "check_output", return_value="406146, GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1\n"):
            bench.require_idle_gpu(self.plan)

    def test_environment_is_private_and_bounded(self):
        with patch.dict(os.environ, {"LD_PRELOAD": "inherited", "ROBOTRON_SOCKET_WAIT_ACTIVE": "select-v1"}), \
             patch.dict(sys.modules):
            sys.modules.pop("numpy", None)
            sys.modules.pop("torch", None)
            bench.configure_environment(self.plan)
            self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"], bench.GPU0_UUID)
            self.assertEqual(os.environ["TORCHINDUCTOR_COMPILE_THREADS"], "2")
            self.assertNotIn("LD_PRELOAD", os.environ)
            self.assertNotIn("ROBOTRON_SOCKET_WAIT_ACTIVE", os.environ)
            self.assertEqual(os.environ["ROBOTRON_DQN_CONTROL_PATH"], str(self.plan.directory / "isolated-control.json"))
            self.assertEqual(os.environ["TRITON_CACHE_DIR"], str(self.plan.directory / "triton"))
        with patch.dict(sys.modules, {"torch": object()}), self.assertRaises(RuntimeError):
            bench.configure_environment(self.plan)

    def test_parity_reports_joint_and_all_locked_fire_changes(self):
        a = [[float(i) for i in range(81)]]
        self.assertEqual(bench.parity(a, a)["greedy_agreement"], 1)
        self.assertEqual(bench.parity(a, a)["locked_fire_agreement"], 1)
        b = [a[0].copy()]
        b[0][0] = 100
        result = bench.parity(a, b)
        self.assertEqual(result["greedy_agreement"], 0)
        self.assertAlmostEqual(result["locked_fire_agreement"], 8/9)
        self.assertFalse(result["q_allclose"])
        self.assertEqual(result["max_abs_error"], 100)

    def test_small_q_drift_and_bad_q_rows_are_distinguished(self):
        a = [[float(i) for i in range(81)]]
        b = [[v+.0001 for v in a[0]]]
        self.assertTrue(bench.parity(a, b)["q_allclose"])
        for other in ([], [[0.0]], [[float("nan")]*81]):
            with self.assertRaises(ValueError):
                bench.parity(a, other)

    def test_timing_summary_uses_wall_units_and_p95(self):
        result = bench.timing_summary([9, 1, 2, 3])
        self.assertEqual(result, dict(calls=4, median_ms=2.5, p95_ms=9, minimum_ms=1, maximum_ms=9))


if __name__ == "__main__":
    unittest.main()
