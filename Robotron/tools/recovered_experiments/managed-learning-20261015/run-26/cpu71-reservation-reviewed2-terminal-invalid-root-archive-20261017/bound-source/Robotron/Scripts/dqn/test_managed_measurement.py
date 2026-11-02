"""Isolated CPU fakes verify measurement rollback, clocks and actor swapping."""

import copy
import os
from pathlib import Path
import tempfile
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = ""

import torch

from .agent import RainbowAgent, ENGINE_VERSION
from .managed_measurement import ManagedMeasurement


class FakeAgent:
    def __init__(self):
        self.training_enabled = True
        self.behavior_locked = False
        self._prefetch_paused = False
        self._training_lock = threading.RLock()
        self.training_steps, self.optimized_samples = 3, 6144
        self.online, self.infer = {"weight": 7}, {"weight": 6}
        self.optimizer = {"moments": [1, 2], "step": 3}
        self.memory = SimpleNamespace(_adds_total=10, size=10, hof_total=0, ephof_total=0,
                                      tree=SimpleNamespace(data_ptr=10))
        self.install_calls = 0
        self.fail_installs = set()

    def prepare_inference_checkpoint(self, path):
        if path == "bad":
            raise ValueError("incompatible checkpoint")
        return {"weight": 2}

    def capture_inference_policy(self):
        return copy.deepcopy(self.online)

    def install_inference_policy(self, state):
        self.install_calls += 1
        if self.install_calls in self.fail_installs:
            raise RuntimeError("copy failed")
        if self.training_enabled or not self.behavior_locked:
            raise RuntimeError("unsafe actor copy")
        self.infer = copy.deepcopy(state)

    def _pause_prefetch(self):
        self._prefetch_paused = True

    def _resume_prefetch(self):
        self._prefetch_paused = False


class TestManagedMeasurement(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.agent = FakeAgent()
        self.metrics = SimpleNamespace(
            lock=threading.RLock(), training_enabled=True, learner_frame_count=55,
            total_training_steps=3, total_optimized_samples=6144,
            measurement_active=False, measurement_generation=0, measurement_label="",
        )
        self.ready = False
        self.cohort = dict(started=2, pending=1, abandoned=0, count=1,
                           rows=[{"score": 0}], complete=False, started_actor_slots=[0, 1])
        self.journal = SimpleNamespace(cohort_status=lambda *args: copy.deepcopy(self.cohort))
        self.controller = ManagedMeasurement(
            self.agent, self.metrics, self.journal, clock=lambda: self.now,
            boundary_status=lambda generation: dict(ready=self.ready, generation=generation,
                                                    actor_slots=[0, 1]),
        )

    def begin(self):
        self.controller.enter("reference", checkpoint_path="preserved.pt", cohort_s=10, timeout_s=50)

    def test_waits_for_barrier_and_every_started_game_then_restores(self):
        original_optimizer = copy.deepcopy(self.agent.optimizer)
        self.begin()
        self.assertEqual(self.agent.infer, {"weight": 2})
        self.assertFalse(self.agent.training_enabled)
        self.assertFalse(self.metrics.training_enabled)
        self.assertTrue(self.agent._prefetch_paused)
        self.assertEqual(self.controller.tick()["phase"], "warming")
        self.now, self.ready = 103, True
        status = self.controller.tick()
        self.assertEqual(status["start_ts"], 103)
        self.now = 114
        self.assertEqual(self.controller.tick()["phase"], "draining")
        self.assertFalse(self.controller.status()["complete"])
        self.cohort.update(pending=0, count=2, complete=True, mean=50000,
                           rows=[{"score": 0}, {"score": 100000}])
        status = self.controller.tick()
        self.assertTrue(status["complete"])
        self.assertTrue(status["valid"])
        self.assertTrue(status["active"])
        status = self.controller.exit()
        self.assertFalse(status["active"])
        self.assertEqual(status["phase"], "finished")
        self.assertEqual(self.agent.infer, self.agent.online)
        self.assertEqual(self.agent.optimizer, original_optimizer)
        self.assertEqual(self.metrics.learner_frame_count, 55)
        self.assertEqual(self.agent.optimized_samples, 6144)
        self.assertTrue(self.agent.training_enabled)
        self.assertFalse(self.agent.behavior_locked)
        self.assertFalse(self.agent._prefetch_paused)
        self.assertEqual(self.metrics.measurement_generation, 2)

    def test_timeout_invalidates_whole_cohort_without_dropping_pending(self):
        self.begin()
        self.ready = True
        self.controller.tick()
        self.now = 151
        status = self.controller.tick()
        self.assertTrue(status["complete"])
        self.assertFalse(status["valid"])
        self.assertEqual(status["reason"], "whole_cohort_timeout")
        self.assertEqual(status["pending"], 1)
        self.controller.exit()

    def test_entry_actor_bookkeeping_can_drain_before_learner_clock_freezes(self):
        self.begin()
        self.metrics.learner_frame_count += 1
        self.assertFalse(self.controller.tick()["complete"])
        self.ready = True
        status = self.controller.tick()
        self.assertEqual(status["clocks"]["learner_frame_count"], 56)
        self.metrics.learner_frame_count += 1
        self.assertFalse(self.controller.tick()["valid"])
        self.controller.exit()
        self.assertEqual(self.metrics.learner_frame_count, 57)

    def test_clock_replay_and_actor_coverage_fail_closed(self):
        for failure in ("clock", "replay", "coverage", "abandoned"):
            with self.subTest(failure=failure):
                self.setUp()
                self.begin()
                self.ready = True
                self.controller.tick()
                if failure == "clock":
                    self.metrics.learner_frame_count += 1
                elif failure == "replay":
                    self.agent.memory._adds_total += 1
                elif failure == "coverage":
                    self.cohort.update(pending=0, complete=True, started_actor_slots=[0])
                else:
                    self.cohort["abandoned"] = 1
                status = self.controller.tick()
                self.assertTrue(status["complete"])
                self.assertFalse(status["valid"])
                self.controller.exit()
                # Never roll a counter backwards to hide protocol damage.
                self.assertEqual(self.metrics.learner_frame_count, 56 if failure == "clock" else 55)

    def test_incompatible_checkpoint_leaves_live_flags_unchanged(self):
        with self.assertRaises(ValueError):
            self.controller.enter("bad", checkpoint_path="bad")
        self.assertTrue(self.agent.training_enabled)
        self.assertFalse(self.metrics.measurement_active)
        self.assertFalse(self.agent._prefetch_paused)

    def test_lock_timeout_does_not_retry_the_unavailable_lock(self):
        class UnavailableLock:
            def acquire(self, timeout):
                return False
            def release(self):
                raise AssertionError("Unavailable lock was never acquired")
        self.agent._training_lock = UnavailableLock()
        with self.assertRaises(TimeoutError):
            self.begin()
        self.assertTrue(self.agent.training_enabled)
        self.assertTrue(self.metrics.training_enabled)
        self.assertFalse(self.metrics.measurement_active)
        self.assertFalse(self.agent._prefetch_paused)

    def test_entry_failure_restores_and_restore_failure_stays_paused(self):
        self.agent.fail_installs = {1}
        with self.assertRaises(RuntimeError):
            self.begin()
        self.assertTrue(self.agent.training_enabled)
        self.assertFalse(self.metrics.measurement_active)
        self.assertEqual(self.agent.infer, self.agent.online)
        self.agent.fail_installs = {4}
        self.begin()  # third install succeeds; fourth is exit restoration.
        with self.assertRaises(RuntimeError):
            self.controller.exit()
        self.assertFalse(self.agent.training_enabled)
        self.assertFalse(self.metrics.training_enabled)
        self.assertTrue(self.metrics.measurement_active)
        self.assertEqual(self.controller.status()["phase"], "restore_failed")

    def test_preserves_already_paused_flags(self):
        self.agent.training_enabled = self.metrics.training_enabled = False
        self.agent._prefetch_paused = self.agent.behavior_locked = True
        self.begin()
        self.controller.exit()
        self.assertFalse(self.agent.training_enabled)
        self.assertFalse(self.metrics.training_enabled)
        self.assertTrue(self.agent._prefetch_paused)
        self.assertTrue(self.agent.behavior_locked)


class TinyActor(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = torch.nn.Linear(2, 2, bias=False)
        self.register_buffer("support", torch.tensor([-10.0, 20.0, 50.0]))

    def forward(self, states):
        return self.linear(states)


class TestInferencePolicyInstallation(unittest.TestCase):
    def setUp(self):
        agent = RainbowAgent.__new__(RainbowAgent)
        agent.use_separate_inference, agent.state_size = True, 2
        agent.online_net, agent.infer_net = TinyActor(), TinyActor()
        agent.target_net = TinyActor()
        agent._training_lock, agent._sync_lock = threading.RLock(), threading.RLock()
        agent.training_enabled, agent.behavior_locked = False, True
        agent.inference_device, agent._inference_stream = torch.device("cpu"), None
        agent.compiled_infer_q_joint = agent.infer_net.forward
        agent.training_steps, agent.optimized_samples = 9, 18432
        self.agent = agent

    def test_existing_actor_storage_and_callable_are_preserved(self):
        agent = self.agent
        online = copy.deepcopy(agent.online_net.state_dict())
        actor, callable_before = agent.infer_net, agent.compiled_infer_q_joint
        storage = agent.infer_net.linear.weight.data_ptr()
        state = agent.capture_inference_policy()
        state["linear.weight"].fill_(9)
        agent.install_inference_policy(state)
        self.assertIs(agent.infer_net, actor)
        self.assertIs(agent.compiled_infer_q_joint, callable_before)
        self.assertEqual(agent.infer_net.linear.weight.data_ptr(), storage)
        torch.testing.assert_close(callable_before(torch.ones(1, 2)), torch.full((1, 2), 18.0))
        for key, value in agent.online_net.state_dict().items():
            torch.testing.assert_close(value, online[key])
        self.assertEqual((agent.training_steps, agent.optimized_samples), (9, 18432))

    def test_rejects_partial_nonfinite_or_different_support_without_mutation(self):
        before = copy.deepcopy(self.agent.infer_net.state_dict())
        for failure in ("missing", "shape", "dtype", "support", "nan"):
            with self.subTest(failure=failure):
                state = copy.deepcopy(before)
                if failure == "missing":
                    del state["linear.weight"]
                elif failure == "shape":
                    state["linear.weight"] = torch.ones(3, 2)
                elif failure == "dtype":
                    state["linear.weight"] = state["linear.weight"].double()
                elif failure == "support":
                    state["support"] += 1
                else:
                    state["linear.weight"][0, 0] = float("nan")
                with self.assertRaises(ValueError):
                    self.agent.install_inference_policy(state)
                for key, value in self.agent.infer_net.state_dict().items():
                    torch.testing.assert_close(value, before[key])

    def test_requires_paused_separate_actor_and_strict_checkpoint_metadata(self):
        state = self.agent.capture_inference_policy()
        self.agent.training_enabled = True
        with self.assertRaises(RuntimeError):
            self.agent.install_inference_policy(state)
        self.agent.training_enabled = False
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "actor.pt"
            checkpoint = dict(engine_version=ENGINE_VERSION, state_size=2, online_state_dict=state)
            torch.save(checkpoint, path)
            self.agent.prepare_inference_checkpoint(path)
            checkpoint["engine_version"] -= 1
            torch.save(checkpoint, path)
            with self.assertRaises(ValueError):
                self.agent.prepare_inference_checkpoint(path)
        self.agent.use_separate_inference = False
        with self.assertRaises(RuntimeError):
            self.agent.capture_inference_policy()

    def test_measurement_frame_clock_persists_and_legacy_defaults_to_zero(self):
        agent = self.agent
        agent.device = torch.device("cpu")
        agent.optimizer = torch.optim.Adam(agent.online_net.parameters(), lr=0.001)
        agent.baseline_batch_size = 512
        agent.last_target_update_samples = 0
        agent.last_inference_sync = agent.last_inference_sync_samples = 0
        agent._prefetcher, agent._prefetch_paused = None, False
        agent.memory = SimpleNamespace(load=lambda *args, **kwargs: False)
        fake_metrics = SimpleNamespace(
            lock=threading.Lock(), frame_count=1000, learner_frame_count=500,
            measurement_frame_count=200, loaded_measurement_frame_count=100,
            total_training_steps=9, total_optimized_samples=18432,
            expert_ratio=0.1, epsilon=0.5,
        )
        with patch.object(sys.modules[RainbowAgent.__module__], "metrics", fake_metrics), \
                patch.object(sys.modules[RainbowAgent.__module__], "RESET_METRICS", False), \
                tempfile.TemporaryDirectory() as temporary:
            path = str(Path(temporary) / "actor.pt")
            agent.save(path, show_status=False, save_replay=False)
            checkpoint = torch.load(path, map_location="cpu", weights_only=True)
            self.assertEqual(checkpoint["measurement_frame_count"], 200)
            fake_metrics.measurement_frame_count = 999
            self.assertTrue(agent.load(path, show_status=False))
            self.assertEqual(fake_metrics.measurement_frame_count, 200)
            self.assertEqual(fake_metrics.loaded_measurement_frame_count, 200)
            snapshot = agent._snapshot_metrics_clocks()
            fake_metrics.measurement_frame_count = 999
            fake_metrics.loaded_measurement_frame_count = 888
            agent._restore_metrics_clocks(snapshot)
            self.assertEqual(fake_metrics.measurement_frame_count, 200)
            self.assertEqual(fake_metrics.loaded_measurement_frame_count, 200)
            del checkpoint["measurement_frame_count"]
            torch.save(checkpoint, path)
            self.assertTrue(agent.load(path, show_status=False))
            self.assertEqual(fake_metrics.measurement_frame_count, 0)
            self.assertEqual(fake_metrics.loaded_measurement_frame_count, 0)
            self.assertEqual((fake_metrics.frame_count, fake_metrics.learner_frame_count), (1000, 500))

    def test_prefetch_resume_failure_keeps_pipeline_paused(self):
        self.agent._prefetch_paused = True
        self.agent._prefetcher = SimpleNamespace(invalidate=lambda **kwargs: False)
        with self.assertRaises(TimeoutError):
            self.agent._resume_prefetch()
        self.assertTrue(self.agent._prefetch_paused)


if __name__ == "__main__":
    unittest.main(verbosity=2)
