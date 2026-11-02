"""Regression: a capped learner must not churn replay minibatches."""
from types import SimpleNamespace
import threading
import sys
import unittest
from unittest.mock import patch

from . import training
from .agent import RainbowAgent
from .prefetch import ReplayPrefetcher
from .test_performance import _Memory


class ReplayPressureTests(unittest.TestCase):
    def setUp(self):
        self.metrics = SimpleNamespace(lock=threading.Lock(), frame_count=1100,
                                       loaded_frame_count=1000,
                                       loaded_optimized_samples=10000,
                                       training_enabled=True)
        self.cfg = SimpleNamespace(max_samples_per_frame=32, baseline_batch_size=512)
        self.agent = SimpleNamespace(training_steps=30, loaded_training_steps=20,
                                     optimized_samples=13200)
        for name, value in [('metrics', self.metrics), ('RL_CONFIG', self.cfg)]:
            patcher = patch.object(training, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_resume_sample_clock_and_boundary(self):
        self.assertTrue(training.replay_pressure_reached(self.agent))
        self.metrics.frame_count += 1
        self.assertFalse(training.replay_pressure_reached(self.agent))
        self.cfg.max_samples_per_frame = 0
        self.agent.optimized_samples = 1000000
        self.assertFalse(training.replay_pressure_reached(self.agent))

    def test_measurement_frames_do_not_grant_training_credit(self):
        self.metrics.frame_count += 1000
        self.metrics.measurement_frame_count = 1000
        self.assertTrue(training.replay_pressure_reached(self.agent))
        self.metrics.frame_count += 100
        self.assertFalse(training.replay_pressure_reached(self.agent))

    def test_measurement_frames_do_not_advance_beta(self):
        self.cfg.priority_beta_frames = 1000
        self.cfg.priority_beta_start = 0.4
        self.metrics.measurement_frame_count = 0
        before = training._beta_schedule(100)
        self.metrics.measurement_frame_count = 500
        self.assertEqual(training._beta_schedule(600), before)

    def test_fresh_replay_warmup_does_not_bank_update_credit(self):
        self.cfg.min_replay_to_train = 4
        self.cfg.batch_size = 4
        self.agent.memory = []
        self.metrics.frame_count += 10000
        self.metrics.learner_frame_count = 7000
        self.assertTrue(training.replay_pressure_reached(self.agent))
        self.assertEqual(self.agent._replay_pressure_anchor, (11100, 0, 13200))
        self.agent.memory = [0] * 4
        self.assertFalse(training.replay_pressure_reached(self.agent))
        self.metrics.frame_count += 100
        self.agent.optimized_samples += 3200
        self.assertTrue(training.replay_pressure_reached(self.agent))
        self.metrics.frame_count += 1
        self.assertFalse(training.replay_pressure_reached(self.agent))
        self.assertEqual(self.metrics.loaded_frame_count, 1000)
        self.assertEqual(self.metrics.loaded_optimized_samples, 10000)
        self.assertEqual(self.metrics.learner_frame_count, 7000)

    def test_paused_fill_seals_budget_at_first_ready_observation(self):
        self.cfg.min_replay_to_train = 4
        self.agent.memory = []
        self.assertTrue(training.replay_pressure_reached(self.agent))
        # Simulate a paused consumer/producer while actors finish warmup.
        self.metrics.frame_count += 50000
        self.agent.memory = [0] * 4
        self.assertFalse(training.replay_pressure_reached(self.agent))
        self.assertEqual(self.agent._replay_pressure_anchor, (51100, 0, 13200))
        self.agent.optimized_samples += 2048
        self.assertTrue(training.replay_pressure_reached(self.agent))

    def test_blocked_producer_does_no_sampling_then_resumes(self):
        memory = _Memory()
        pipeline = ReplayPrefetcher(memory, 4, beta_fn=lambda: 0.4,
                                   enabled_fn=lambda: not training.replay_pressure_reached(self.agent),
                                   device='cpu', depth=2)
        self.addCleanup(pipeline.close)
        self.assertIsNone(pipeline.get(timeout=0.1))
        self.assertEqual(memory.calls, 0)
        self.metrics.frame_count += 100
        batch = pipeline.get(timeout=2)
        self.assertIsNotNone(batch)
        batch.release()

    def test_capped_consumer_never_requests_batch(self):
        agent = RainbowAgent.__new__(RainbowAgent)
        agent.running = True
        agent.training_enabled = True
        agent._train_queue = __import__('queue').Queue()
        module = sys.modules[RainbowAgent.__module__]
        with patch.object(module, 'replay_pressure_reached', return_value=True), \
             patch.object(module, 'metrics', self.metrics), \
             patch.object(agent, '_prefetch_batch') as fetch, \
             patch.object(module.time, 'sleep', side_effect=lambda _: setattr(agent, 'running', False)):
            agent._background_train()
        fetch.assert_not_called()
        self.assertEqual(self.metrics.replay_pressure_waits, 1)


if __name__ == '__main__':
    unittest.main()
