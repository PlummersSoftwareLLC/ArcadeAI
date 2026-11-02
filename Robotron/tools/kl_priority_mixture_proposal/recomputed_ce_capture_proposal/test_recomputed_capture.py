"""UNEXECUTED tiny CPU observer/AST contracts; no real CUDA/compiler claim.

Only a separately authorized CPU test run may import this module. Geometry is
explicitly patched for small owned fixtures; production4096 correctness remains
the separate actual one-attempt rehearsal. No production package is imported.
"""
import ast
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[2]
CORE = GAME / "Scripts/dqn"


def load_source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


capture_module = load_source(HERE / "recomputed_ce_capture.py", "private_recomputed_capture")
original_loss = load_source(CORE / "loss_kernel.py", "private_original_loss_only")


class Exposure:
    def __init__(self):
        self.total = dict(attempts_started=0, outcomes_recorded=0, applied=0, amp_skipped=0, unavailable=0)

    def snapshot(self):
        return dict(schema="robotron-optimizer-exposure-v1", enabled=True,
            available=bool(self.total["outcomes_recorded"]), process_id=1,
            instance_monotonic_ns=2, epoch=0, total=dict(self.total),
            unclassified_started_total=0, prior_epoch_outcomes_total=0)

    def finish(self, skip=False):
        self.total["attempts_started"] += 1
        self.total["outcomes_recorded"] += 1
        self.total["amp_skipped" if skip else "applied"] += 1
        return SimpleNamespace(owner=self, epoch=0, finished=True)


class Lease:
    def __init__(self, draw, release):
        self.draw_metadata = draw
        self._epoch = 3
        self._owner = SimpleNamespace(_epoch=3)
        self.is_current = True
        self.sample_ms = self.stage_host_ms = 0.0
        self.release_callback = release
        self.released = False

    def release(self):
        self.release_callback()
        self.released = True


def training_wrapper():
    tree = ast.parse((HERE / "training.py").read_text())
    wanted = {"_capture_observe", "train_step"}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = dict(nullcontext=contextlib.nullcontext)
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<owned-wrapper-only>", "exec"), namespace)
    return namespace


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for name, value in (("BATCH_ROWS", 4), ("STATE_WIDTH", 3)):
            p = patch.object(capture_module, name, value)
            p.start()
            self.addCleanup(p.stop)
        env = patch.dict(os.environ, DQN_EXECUTED_CE_TRACE_DIR="", DQN_PER_PRIORITY_METRIC="ce")
        env.start()
        self.addCleanup(env.stop)
        self.cfg = SimpleNamespace(batch_size=4, num_atoms=51, num_fire_actions=9,
            v_min=-10., v_max=10., gamma=.99, c51_target_smoothing=.01,
            use_torch_compile=True, compile_full_loss=True, replay_prefetch_slots=3)
        self.exposure = Exposure()
        self.capture = capture_module.RecomputedCECapture(
            str(Path(self.temp.name) / "ce-recomputed-capture-unit"), self.cfg,
            optimizer_exposure=self.exposure, runtime=dict(scope="tiny CPU fixture, not actual compile"))
        online, target = torch.nn.Linear(3, 2), torch.nn.Linear(3, 2)
        target.load_state_dict(online.state_dict())
        online.train()
        target.eval()
        self.agent = SimpleNamespace(device=torch.device("cpu"), online_net=online, target_net=target,
            optimizer=torch.optim.Adam(online.parameters(), lr=.001), training_steps=0,
            optimized_samples=0, _training_lock=threading.RLock(), _recomputed_ce_capture=self.capture)
        self.kernel = original_loss.TrainingLoss(online, target, self.cfg, diagnostics=False)
        self.inputs = (torch.arange(12, dtype=torch.float32).reshape(4, 3),
            torch.arange(4), torch.zeros(4), torch.ones(4, 3), torch.zeros(4),
            torch.ones(4), torch.ones(4, dtype=torch.bool), torch.tensor([1., .5, .25, .125]))
        self.schedule = torch.tensor([1., .1, .2])
        leaves = np.array([.25, .5, 1., 2.], dtype=np.float64)
        leaves.flags.writeable = False
        self.batch = capture_module.ObservedReplayBatch(tuple(range(10)),
            dict(capture_id=self.capture.capture_id, per_raw_leaves=leaves,
                 unknown=dict(priority_metric="unknown")))
        self.wrapper = training_wrapper()

    def pre(self, staged=None):
        self.capture.begin(self.agent, self.batch, staged)
        self.capture.pre_loss(self.agent, self.inputs, schedule=self.schedule,
                              kernel=self.kernel, diagnostic_due=False, use_amp=False)

    def loss(self):
        self.capture.loss(self.agent, torch.arange(1, 5, dtype=torch.float32),
            weighted_loss=torch.tensor(2.), bc_loss=torch.tensor(1.), diagnostic_values=torch.zeros(12))

    def outcome(self, skip=False):
        ticket = self.exposure.finish(skip)
        self.capture.outcome("test_explicit_exposure", 1. if skip else 0., ticket)
        self.agent.training_steps += 1
        self.agent.optimized_samples += 4

    def payload(self, index=1):
        return torch.load(self.capture.directory / ("attempt-%02d.payload.pt" % index),
                          map_location="cpu", weights_only=True)

    def test_exact_owned_pre_state_and_inputs_survive_later_writes(self):
        self.pre()
        expected_inputs = [value.clone() for value in self.inputs]
        expected_online = {name: value.clone() for name, value in self.agent.online_net.state_dict().items()}
        with torch.no_grad():
            self.agent.online_net.weight.add_(10)
            self.agent.target_net.weight.add_(20)
            self.inputs[0].fill_(99)
        self.loss()
        self.outcome()
        self.capture.end(self.agent, result=2.)
        payload = self.payload()
        for name, value in zip(capture_module.INPUT_NAMES, expected_inputs):
            self.assertTrue(torch.equal(payload["inputs"][name], value))
            self.assertEqual(payload["inputs"][name].dtype, value.dtype)
        for name, value in expected_online.items():
            self.assertTrue(torch.equal(payload["online"][name], value))
        self.assertIsNone(self.capture.raw)
        self.assertIsNone(self.capture.current)
        self.assertNotIn("draw", self.capture.rows[0])
        self.assertTrue(self.capture.rows[0]["capture_complete"])

    def test_first_eight_include_actual_skips_and_no_ninth(self):
        for index in range(9):
            self.pre()
            self.loss()
            self.outcome(skip=index % 2 == 1)
            self.capture.end(self.agent, result=2.)
        self.assertEqual(self.capture.consumed, 8)
        self.assertEqual(len(self.capture.rows), 8)
        self.assertEqual(len(list(self.capture.directory.glob("attempt-*.payload.pt"))), 8)
        self.assertEqual([r["optimizer_outcome"] for r in self.capture.rows],
                         ["applied_admission", "amp_skipped"] * 4)
        self.assertTrue(json.loads((self.capture.directory / "final.json").read_text())["complete"])
        self.assertFalse(self.capture.want_draw())

    def test_transfer_error_retains_first_ordinal_and_original_exception_before_release(self):
        error = RuntimeError("actual transfer error")
        released = []
        lease = Lease(self.batch.draw_metadata, lambda: released.append((self.capture.raw,
            (self.capture.directory / "attempt-01.json").exists())))
        def actual_impl(agent, prefetched):
            self.capture.begin(agent, self.batch, prefetched)
            raise error
        self.wrapper["_train_step_impl"] = actual_impl
        with self.assertRaises(RuntimeError) as caught:
            self.wrapper["train_step"](self.agent, lease)
        self.assertIs(caught.exception, error)
        self.assertEqual(released, [(None, True)])
        self.assertEqual(self.capture.consumed, 1)
        self.assertFalse(self.capture.rows[0]["capture_complete"])
        self.assertFalse(list(self.capture.directory.glob("attempt-01.payload.pt")))

    def test_forward_error_retains_pre_snapshot_and_preserves_exception(self):
        self.pre()
        error = ValueError("actual kernel error")
        self.capture.end(self.agent, exception=error)
        payload = self.payload()
        self.assertIn("online", payload)
        self.assertNotIn("actual", payload)
        self.assertEqual(self.capture.rows[0]["exception"], "ValueError: actual kernel error")
        self.assertFalse(self.capture.rows[0]["capture_complete"])

    def test_loss_nonfinite_values_are_retained_before_interpretation_fails(self):
        self.pre()
        self.wrapper["_capture_observe"](self.capture, "loss", self.agent,
            torch.tensor([float("nan"), 1., 2., 3.]), weighted_loss=torch.tensor(float("nan")),
            bc_loss=torch.tensor(1.), diagnostic_values=torch.zeros(12))
        self.capture.end(self.agent, result=None)
        self.assertTrue(torch.isnan(self.payload()["actual"]["ce"][0]))
        self.assertFalse(self.capture.rows[0]["capture_complete"])
        self.assertTrue(self.capture.invalid)

    def test_observer_disk_failure_does_not_replace_original_training_result(self):
        def actual_impl(agent, prefetched):
            self.pre()
            self.loss()
            self.outcome()
            return 2.
        self.wrapper["_train_step_impl"] = actual_impl
        with patch.object(self.capture, "_persist_raw", side_effect=OSError("disk unavailable")):
            self.assertEqual(self.wrapper["train_step"](self.agent), 2.)
        self.assertIsNone(self.capture.raw)
        self.assertTrue(self.capture.invalid)
        self.assertFalse(self.capture.rows[0]["capture_complete"])

    def test_budget_fails_before_over_budget_tensor_copy_and_clears_on_end(self):
        self.capture.begin(self.agent, self.batch, None)
        with patch.object(capture_module, "MAX_RAW_BYTES", 4):
            self.wrapper["_capture_observe"](self.capture, "pre_loss", self.agent,
                self.inputs, schedule=self.schedule, kernel=self.kernel, diagnostic_due=False, use_amp=False)
        self.capture.end(self.agent, exception=RuntimeError("private failure"))
        self.assertFalse(self.capture.rows[0]["capture_complete"])
        self.assertIsNone(self.capture.raw)

    def test_fp16_input_is_rejected_without_rounding_or_training_exception(self):
        self.capture.begin(self.agent, self.batch, None)
        bad = (self.inputs[0].half(), *self.inputs[1:])
        self.wrapper["_capture_observe"](self.capture, "pre_loss", self.agent, bad,
            schedule=self.schedule, kernel=self.kernel, diagnostic_due=False, use_amp=False)
        self.assertTrue(self.capture.invalid)
        self.assertIsNone(self.capture.raw)
        self.assertEqual(bad[0].dtype, torch.float16)
        self.capture.end(self.agent, result=None)

    def test_cpu_and_numpy_rng_are_not_advanced_by_capture(self):
        before_torch = torch.get_rng_state().clone()
        before_numpy = np.random.get_state()
        self.pre()
        self.loss()
        self.outcome()
        self.capture.end(self.agent, result=2.)
        self.assertTrue(torch.equal(torch.get_rng_state(), before_torch))
        after_numpy = np.random.get_state()
        self.assertEqual(before_numpy[0], after_numpy[0])
        self.assertTrue(np.array_equal(before_numpy[1], after_numpy[1]))
        self.assertEqual(before_numpy[2:], after_numpy[2:])

    def test_disposed_lease_has_only_primitive_retained_rows(self):
        release = []
        lease = Lease(self.batch.draw_metadata, lambda: release.append(self.capture.raw is None))
        def impl(agent, prefetched):
            self.pre(prefetched)
            self.loss()
            self.outcome()
            return 2.
        self.wrapper["_train_step_impl"] = impl
        self.assertEqual(self.wrapper["train_step"](self.agent, lease), 2.)
        self.assertTrue(lease.released)
        self.assertEqual(release, [True])
        json.dumps(self.capture.rows, allow_nan=False)
        self.assertEqual(self.payload()["outcome"]["prefetch"]["lease_epoch"], 3)


class SourceContracts(unittest.TestCase):
    def test_original_loss_is_not_overlaid_and_constructor_is_unchanged(self):
        self.assertFalse((HERE / "loss_kernel.py").exists())
        self.assertEqual(hashlib.sha256((CORE / "loss_kernel.py").read_bytes()).hexdigest(), capture_module.LOSS_SHA256)
        def method(path):
            tree = ast.parse(path.read_text())
            return ast.dump(next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                                 and n.name == "_setup_torch_compile"), include_attributes=False)
        self.assertEqual(method(HERE / "agent.py"), method(CORE / "agent.py"))

    def test_compile_call_unpack_and_backward_expressions_remain_original(self):
        def expressions(path):
            tree = ast.parse(path.read_text())
            return [ast.dump(node, include_attributes=False) for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and
                    (isinstance(node.func, ast.Name) and node.func.id == "kernel" or
                     isinstance(node.func, ast.Attribute) and node.func.attr in ("backward", "step", "update"))]
        self.assertEqual(expressions(HERE / "training.py"), expressions(CORE / "training.py"))


if __name__ == "__main__":
    unittest.main()
