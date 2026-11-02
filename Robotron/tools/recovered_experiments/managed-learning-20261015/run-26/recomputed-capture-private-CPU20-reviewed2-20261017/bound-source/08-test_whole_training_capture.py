"""UNEXECUTED separate whole-implementation CPU integration proposal.

Reuses immutable08061 fixture setup, then loads the ENTIRE new training module
in its private package. Real CPU replay/prefetch/original4-output loss/Adam and
exposure run. One test uses explicit CPU CUDA-branch/scaler adapters, not CUDA.
Run separately from the tiny observer suite in a fresh CUDA-hidden interpreter.
"""
from contextlib import ExitStack
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parents[1] / "executed_trace_validation_proposal/test_whole_train_step.py"
TEMPLATE_SHA = "08061c2aed557135c824ce277440276430cabe6d6b96cbccbdd64d96af592901"


def template_module():
    if hashlib.sha256(TEMPLATE.read_bytes()).hexdigest() != TEMPLATE_SHA:
        raise RuntimeError("Whole-step private fixture source drift")
    spec = importlib.util.spec_from_file_location("private_recomputed_whole_template", TEMPLATE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


template = template_module()  # source definitions only; template imports no Torch
Base = template.WholeTrainStepTests


class WholeRecomputedCaptureTests(unittest.TestCase):
    # Reuse setup/helpers, not the old test methods or old target-capture ABI.
    setUp = Base.setUp
    metrics_for = Base.metrics_for
    assert_tree_equal = Base.assert_tree_equal
    snapshot = Base.snapshot
    assert_progress = Base.assert_progress
    cpu_amp_branch = Base.cpu_amp_branch

    @classmethod
    def setUpClass(cls):
        if os.environ.get("ROBOTRON_ALLOW_RECOMPUTED_WHOLE_CPU") != "1":
            raise RuntimeError("Explicit whole recomputed CPU test permission required")
        Base.setUpClass.__func__(cls)
        package = "kl_fixture_candidate"
        for filename in ("training.py", "recomputed_ce_capture.py"):
            (cls.package_dir / ("new_" + filename)).write_bytes((HERE / filename).read_bytes())
        cls.training = importlib.import_module(package + ".new_training")
        cls.capture_module = importlib.import_module(package + ".new_recomputed_ce_capture")
        cls.width_patch = mock.patch.object(cls.capture_module, "STATE_WIDTH", template.WIDTH)
        cls.width_patch.start()
        # Source-copy and original loss hashes are checked by the fixture and
        # live observer itself; no actual agent/model/CUDA dependency is loaded.
        if cls.torch.cuda.is_initialized() or cls.torch.cuda.device_count() != 0:
            raise RuntimeError("Unexpected CUDA visibility/context")

    @classmethod
    def tearDownClass(cls):
        cls.width_patch.stop()
        Base.tearDownClass.__func__(cls)

    def build(self, module=None, *, capture=True):
        module = module or self.training
        self.cfg.use_torch_compile = self.cfg.compile_full_loss = True
        # Original fixture build creates real CPU Adam and current exposure.
        agent, metrics = Base.build(self, module, trace=False, kernel=False)
        agent.device = self.torch.device("cpu")
        agent.target_net.eval()
        agent._recomputed_ce_capture = None
        agent.compiled_training_loss = self.base_loss.TrainingLoss(agent.online_net, agent.target_net, self.cfg, False)
        agent.compiled_training_loss_diagnostics = self.base_loss.TrainingLoss(agent.online_net, agent.target_net, self.cfg, True)
        if capture:
            self._serial += 1
            agent._recomputed_ce_capture = self.capture_module.RecomputedCECapture(
                str(self.case / ("ce-recomputed-capture-%d" % self._serial)), self.cfg,
                optimizer_exposure=agent._learning_optimizer_exposure,
                runtime=dict(scope="Whole4096x8 CPU body, original4 loss, actual Adam/exposure; no actual compile/CUDA"))
        return agent, metrics

    def producer(self, agent):
        return self.prefetch.ReplayPrefetcher(agent.memory, template.BATCH, lambda: 1., "cpu", depth=2,
            min_replay_size=template.BATCH, direct_state_fill=True, trace_observer=agent._recomputed_ce_capture)

    def payload(self, observer, ordinal=1):
        return self.torch.load(observer.directory / ("attempt-%02d.payload.pt" % ordinal),
                               weights_only=True, map_location="cpu")

    def test_entire_body_base_off_on_equal_and_real_adam_progress_matches_pre(self):
        agents, results, before_all, rngs = [], [], [], []
        for module, enabled in ((self.base_training, False), (self.training, False), (self.training, True)):
            agent, metrics = self.build(module, capture=enabled)
            before = self.snapshot(agent)
            self.np.random.seed(template.SEED)
            results.append(module.train_step(agent))
            self.assert_progress(before, agent)
            self.assertEqual(agent._learning_optimizer_exposure.snapshot()["total"]["applied"], 1)
            self.assertEqual(agent.online_net.training_calls, 1)
            agents.append(agent)
            before_all.append(before)
            rngs.append(self.np.random.get_state())
        self.assertEqual(results, [results[0]] * 3)
        for agent in agents[1:]:
            self.assert_tree_equal(self.snapshot(agents[0]), self.snapshot(agent))
            self.assert_tree_equal(agents[0].priorities, agent.priorities)
        for state in rngs[1:]:
            self.np.testing.assert_array_equal(rngs[0][1], state[1])
            self.assertEqual(rngs[0][2:], state[2:])
        observer = agents[-1]._recomputed_ce_capture
        row, payload = observer.rows[0], self.payload(observer)
        self.assertTrue(row["capture_complete"])
        self.assertTrue(row["draw_batch_join_checked"] and row["staged_draw_join_checked"])
        self.assertEqual(row["optimizer_outcome"], "applied_admission")
        self.assert_tree_equal(payload["online"], before_all[-1]["online"])
        self.assert_tree_equal(payload["target"], before_all[-1]["target"])
        self.np.testing.assert_array_equal(payload["actual"]["ce"].numpy(), agents[-1].priorities[0][1])
        self.assertEqual(float(payload["actual"]["weighted_loss"]), results[-1])
        self.assertNotIn("projected_target", payload["actual"])
        self.assertIsNone(observer.raw)

    def test_real_prefetch_lease_is_held_through_pre_copies_adam_and_drain(self):
        agent, _ = self.build()
        observer = agent._recomputed_ce_capture
        before = self.snapshot(agent)
        producer = self.producer(agent)
        batch = None
        try:
            batch = producer.get(timeout=5.)
            self.assertIsNotNone(batch)
            expected_inputs = [tensor.clone() for tensor in batch.tensors]
            original_pre = observer.pre_loss
            seen = []
            def checked_pre(*args, **kwargs):
                self.assertTrue(agent._training_lock._is_owned())
                self.assertFalse(batch._released)
                original_pre(*args, **kwargs)
                self.assert_tree_equal(observer.raw["online"], before["online"])
                seen.append("pre")
            original_release = batch.release
            def checked_release():
                self.assertIsNone(observer.raw)
                self.assertTrue((observer.directory / "attempt-01.json").is_file())
                seen.append("release")
                original_release()
            with mock.patch.object(observer, "pre_loss", side_effect=checked_pre), mock.patch.object(batch, "release", side_effect=checked_release):
                self.assertIsNotNone(self.training.train_step(agent, batch))
            self.assertEqual(seen, ["pre", "release"])
            self.assertTrue(batch._released)
            self.assert_progress(before, agent)
            payload = self.payload(observer)
            for name, expected in zip(self.capture_module.INPUT_NAMES, expected_inputs):
                self.assertTrue(self.torch.equal(payload["inputs"][name], expected))
            self.assertEqual(payload["draw"]["capture_id"], observer.capture_id)
            self.assertEqual(observer.rows[0]["prefetch_exit"]["lease_epoch"], batch._epoch)
        finally:
            self.assertTrue(producer.close(timeout=5.))
            self.assertFalse(producer._thread.is_alive())
        # No producer is active during this synthetic reuse/mutation check.
        batch._slot.host[0].fill_(999.)
        self.assertTrue(self.torch.equal(self.payload(observer)["inputs"]["states"], expected_inputs[0]))

    def test_entire_body_real_cpu_scaler_skip_errors_first_eight_no_replacement(self):
        agent, _ = self.build()
        observer = agent._recomputed_ce_capture
        producer = self.producer(agent)
        try:
            with self.cpu_amp_branch(agent):
                for ordinal in range(1, 10):
                    batch = producer.get(timeout=5.)
                    self.assertIsNotNone(batch)
                    with ExitStack() as hooks:
                        if ordinal == 2:
                            before = self.snapshot(agent)
                            scale = agent.grad_scaler.get_scale()
                            handle = next(agent.online_net.parameters()).register_hook(lambda gradient: gradient * float("inf"))
                            hooks.callback(handle.remove)
                        failure = RuntimeError("private full body failure-%d" % ordinal)
                        if ordinal == 3:
                            hooks.enter_context(mock.patch.object(agent.online_net, "training_outputs", side_effect=failure))
                        if ordinal == 4:
                            hooks.enter_context(mock.patch.object(batch, "wait_on_current_stream", side_effect=failure))
                        if ordinal in (3, 4):
                            with self.assertRaises(RuntimeError) as caught:
                                self.training.train_step(agent, batch)
                            self.assertIs(caught.exception, failure)
                        else:
                            self.assertIsNotNone(self.training.train_step(agent, batch))
                        if ordinal == 2:
                            self.assert_tree_equal(before["online"], self.snapshot(agent)["online"])
                            self.assert_tree_equal(before["adam"], self.snapshot(agent)["adam"])
                            self.assertEqual(agent.grad_scaler.get_scale(), scale / 2.)
                    self.assertTrue(batch._released)
                    self.assertIsNone(observer.raw)
                    self.assertEqual(observer.consumed, min(ordinal, 8))
            self.assertEqual([row["index"] for row in observer.rows], list(range(1, 9)))
            self.assertEqual(observer.rows[1]["optimizer_outcome"], "amp_skipped")
            self.assertEqual(observer.rows[1]["optimizer_observation"]["found_inf"], 1.)
            self.assertTrue(observer.rows[1]["capture_complete"])
            self.assertEqual([observer.rows[i]["status"] for i in (2, 3)], ["learner_exception"] * 2)
            self.assertFalse(json.loads((observer.directory / "final.json").read_text())["complete"])
            self.assertFalse((observer.directory / "attempt-09.json").exists())
            counts = agent._learning_optimizer_exposure.snapshot()["total"]
            self.assertEqual((counts["applied"], counts["amp_skipped"], counts["unavailable"]), (6, 1, 0))
        finally:
            self.assertTrue(producer.close(timeout=5.))
            self.assertFalse(producer._thread.is_alive())
        self.assertFalse(self.torch.cuda.is_initialized())

    def test_optimizer_and_late_priority_errors_keep_original_error_and_known_outcome(self):
        for where in ("optimizer", "priorities"):
            with self.subTest(where=where):
                agent, _ = self.build()
                before = self.snapshot(agent)
                error = OSError("actual private " + where)
                owner, method = (agent.optimizer, "step") if where == "optimizer" else (agent.memory, "update_priorities")
                with mock.patch.object(owner, method, side_effect=error):
                    with self.assertRaises(OSError) as caught:
                        self.training.train_step(agent)
                self.assertIs(caught.exception, error)
                observer = agent._recomputed_ce_capture
                self.assertFalse(observer.rows[0]["capture_complete"])
                self.assertIsNone(observer.raw)
                self.assertIn("actual", self.payload(observer))
                if where == "priorities":
                    self.assert_progress(before, agent)
                    self.assertEqual(observer.rows[0]["optimizer_outcome"], "applied_admission")
                else:
                    self.assert_tree_equal(before, self.snapshot(agent))
                    self.assertEqual(observer.rows[0]["actual_exposure_delta"]["unavailable"], 1)

    def test_observer_faults_leave_real_kernel_and_actual_adam_learning_enabled(self):
        for where in ("pre_loss", "loss", "_persist_raw"):
            with self.subTest(where=where):
                agent, _ = self.build()
                observer = agent._recomputed_ce_capture
                original = agent.compiled_training_loss_diagnostics
                before = self.snapshot(agent)
                with mock.patch.object(observer, where, side_effect=OSError("observer-only")):
                    self.assertIsNotNone(self.training.train_step(agent))
                self.assert_progress(before, agent)
                self.assertIs(agent.compiled_training_loss_diagnostics, original)
                self.assertTrue(observer.invalid)
                self.assertFalse(observer.rows[0]["capture_complete"])
                self.assertIsNone(observer.raw)

    def test_wrong_draw_identity_does_not_get_relabelled_as_executed_inputs(self):
        agent, _ = self.build()
        observer = agent._recomputed_ce_capture
        original_sample = observer.sample
        def wrong_draw(*args, **kwargs):
            batch = original_sample(*args, **kwargs)
            batch.draw_metadata["capture_id"] = "wrong-producer-session"
            return batch
        before = self.snapshot(agent)
        with mock.patch.object(observer, "sample", side_effect=wrong_draw):
            self.assertIsNotNone(self.training.train_step(agent))
        self.assert_progress(before, agent)
        self.assertTrue(observer.invalid)
        self.assertFalse(observer.rows[0]["capture_complete"])
        self.assertIsNone(observer.raw)


if __name__ == "__main__":
    unittest.main()
