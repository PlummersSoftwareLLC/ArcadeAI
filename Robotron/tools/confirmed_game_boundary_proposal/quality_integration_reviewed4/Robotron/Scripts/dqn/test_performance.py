"""Correctness checks for the GB300 execution changes.

Run on an isolated CPU process, never against the live learner::

    CUDA_VISIBLE_DEVICES='' ROBOTRON_BASELINE_MODEL=/path/to/old/model.py \
        python -m unittest dqn.test_performance -v

The model comparison loads the old source with today's same configuration.
It verifies the checkpoint contract and numerical behavior for both empty and
populated object bags. No checkpoint, replay ring, or service is opened.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import threading
import unittest

import numpy as np
import torch
import torch.nn.functional as F

try:
    from .prefetch import ReplayPrefetcher
    from . import config
    from .model import RainbowNet
    from .agent import RainbowAgent
except ImportError:
    from prefetch import ReplayPrefetcher
    import config
    from model import RainbowNet
    from agent import RainbowAgent


def setUpModule():
    global _PREVIOUS_TORCH_THREADS
    _PREVIOUS_TORCH_THREADS = torch.get_num_threads()
    torch.set_num_threads(2)


def tearDownModule():
    torch.set_num_threads(_PREVIOUS_TORCH_THREADS)


class SampleClockMigrationTests(unittest.TestCase):
    def test_legacy_checkpoint_keeps_target_update_phase(self):
        period = int(config.RL_CONFIG.target_update_period)
        agent = RainbowAgent.__new__(RainbowAgent)
        agent.baseline_batch_size = 512
        for offset in (0, 1, period - 1):
            with self.subTest(offset=offset):
                agent.training_steps = 2 * period + offset
                agent.optimized_samples = agent.training_steps * 512
                last_target_samples = agent._legacy_target_update_samples()
                remaining_samples = period * 512 - (agent.optimized_samples - last_target_samples)
                # A checkpoint between target updates keeps the remaining
                # interval; loading does not grant it an entire new interval.
                self.assertEqual(remaining_samples, (period - offset) * 512)
                self.assertEqual(last_target_samples, 2 * period * 512)


def _expert_loss(logits, targets, expert, subset):
    """Two independently reduced formulations of joint and branch BC."""
    joint, move, fire = logits
    num_fire = fire.shape[1]
    count = int(expert.sum())
    if not count:
        return sum(output.sum() * 0.0 for output in logits)
    if subset:
        joint, move, fire = (output[expert] for output in logits)
        action = targets[expert]
        return (
            F.cross_entropy(joint, action)
            + 0.125 * (
                F.cross_entropy(move, action // num_fire)
                + F.cross_entropy(fire, action % num_fire)
            )
        )
    per_row = F.cross_entropy(joint, targets, reduction="none")
    per_row = per_row + 0.125 * (
        F.cross_entropy(move, targets // num_fire, reduction="none")
        + F.cross_entropy(fire, targets % num_fire, reduction="none")
    )
    return (per_row * expert).sum() / count


class ExpertLossEquivalenceTests(unittest.TestCase):
    def test_masked_bc_matches_subset_value_and_gradients(self):
        """Dropping nonexperts must not change any expert gradient or scale."""
        generator = torch.Generator().manual_seed(731)
        source = [torch.randn(17, n, dtype=torch.float64, generator=generator)
                  for n in (81, 9, 9)]
        targets = torch.randint(81, (17,), generator=generator)
        masks = {
            "no_expert": torch.zeros(17, dtype=torch.bool),
            "one_expert": torch.arange(17) == 6,
            "sparse": torch.arange(17) % 4 == 0,
            "dense": torch.arange(17) != 6,
            "all_expert": torch.ones(17, dtype=torch.bool),
        }
        for name, expert in masks.items():
            with self.subTest(expert=name):
                expected_logits = [tensor.clone().requires_grad_() for tensor in source]
                actual_logits = [tensor.clone().requires_grad_() for tensor in source]
                expected = _expert_loss(expected_logits, targets, expert, subset=True)
                actual = _expert_loss(actual_logits, targets, expert, subset=False)
                expected.backward()
                actual.backward()
                torch.testing.assert_close(actual, expected, atol=1e-12, rtol=1e-12)
                for observed, wanted in zip(actual_logits, expected_logits):
                    torch.testing.assert_close(observed.grad, wanted.grad,
                                               atol=1e-12, rtol=1e-12)
                    self.assertEqual(int(torch.count_nonzero(observed.grad[~expert])), 0)

    def test_masked_q_policy_and_margin_preserve_batch_scaling(self):
        """Expert-only Q auxiliaries retain their original full-batch weight."""
        generator = torch.Generator().manual_seed(732)
        source = torch.randn(13, 81, dtype=torch.float64, generator=generator)
        targets = torch.randint(81, (13,), generator=generator)
        for present in (0, 1, 4, 12, 13):
            with self.subTest(expert_count=present):
                expert = torch.arange(13) < present
                expected_q = source.clone().requires_grad_()
                actual_q = source.clone().requires_grad_()
                if present:
                    subset_q, subset_actions = expected_q[expert], targets[expert]
                    margins = torch.full_like(subset_q, 0.5)
                    margins.scatter_(1, subset_actions[:, None], 0.0)
                    margin_loss = (subset_q + margins).max(1).values
                    margin_loss -= subset_q.gather(1, subset_actions[:, None]).squeeze(1)
                    expected = present / 13 * (
                        0.3 * F.cross_entropy(subset_q / 10.0, subset_actions)
                        + 0.1 * margin_loss.mean()
                    )
                else:
                    expected = expected_q.sum() * 0.0
                margins = torch.full_like(actual_q, 0.5)
                margins.scatter_(1, targets[:, None], 0.0)
                margin_loss = (actual_q + margins).max(1).values
                margin_loss -= actual_q.gather(1, targets[:, None]).squeeze(1)
                actual = (
                    0.3 * (F.cross_entropy(actual_q / 10.0, targets,
                                           reduction="none") * expert).sum() / 13
                    + 0.1 * (margin_loss * expert).sum() / 13
                )
                expected.backward()
                actual.backward()
                torch.testing.assert_close(actual, expected, atol=1e-12, rtol=1e-12)
                torch.testing.assert_close(actual_q.grad, expected_q.grad,
                                           atol=1e-12, rtol=1e-12)


def _load_baseline_model(path):
    package = RainbowNet.__module__.rpartition(".")[0]
    module_name = (package + "." if package else "") + "_performance_baseline_model"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import baseline model from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RainbowNet


class ModelCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get("ROBOTRON_BASELINE_MODEL", "").strip()
        if not path:
            raise unittest.SkipTest("Set ROBOTRON_BASELINE_MODEL to the old model.py")
        if not Path(path).is_file():
            raise RuntimeError(f"Baseline model does not exist: {path}")
        cls.baseline_type = _load_baseline_model(path)
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(2)
        torch.manual_seed(735)
        cls.original = cls.baseline_type(config.MODEL_STATE_SIZE).cpu()
        cls.modified = RainbowNet(config.MODEL_STATE_SIZE).cpu()
        cls.modified.load_state_dict(cls.original.state_dict(), strict=True)

    @classmethod
    def tearDownClass(cls):
        del cls.original, cls.modified
        torch.set_num_threads(cls.previous_threads)

    def _states(self, density):
        cfg = config.RL_CONFIG
        generator = torch.Generator().manual_seed(738)
        states = torch.randn(2, config.MODEL_STATE_SIZE, generator=generator) * 0.05
        frames = states.reshape(2, cfg.frame_stack, cfg.single_frame_state_size)
        start = cfg.global_features
        end = start + cfg.enemy_token_count * cfg.enemy_token_features
        objects = frames[..., start:end].reshape(
            2, cfg.frame_stack, cfg.enemy_token_count, cfg.enemy_token_features,
        )
        objects[..., 0] = 0.0
        objects[..., config.TYPE_ONEHOT_OFFSET:
                config.TYPE_ONEHOT_OFFSET + config.TYPE_CLASS_COUNT] = 0.0
        if density == "dense":
            objects[..., 0] = 1.0
        elif density == "sparse":
            objects[..., [0, 17, 90], 0] = 1.0
        elif density != "empty":
            raise ValueError(density)
        objects[..., config.TYPE_ONEHOT_OFFSET + 2] = objects[..., 0]
        return states

    def test_old_checkpoint_keys_are_preserved(self):
        old_keys = set(self.original.state_dict())
        new_keys = set(self.modified.state_dict())
        self.assertSetEqual(new_keys, old_keys)
        self.assertNotIn("joint_move_ids", new_keys)
        self.assertNotIn("joint_fire_ids", new_keys)
        self.assertIn("joint_move_ids", dict(self.modified.named_buffers()))
        self.assertIn("joint_fire_ids", dict(self.modified.named_buffers()))
        self.modified.load_state_dict(self.original.state_dict(), strict=True)

    def test_empty_sparse_dense_bags_preserve_eager_outputs(self):
        for training in (False, True):
            self.original.train(training)
            self.modified.train(training)
            for density in ("empty", "sparse", "dense"):
                with self.subTest(training=training, bag=density), torch.no_grad():
                    states = self._states(density)
                    expected = self.original.joint_dist(states, log=True)
                    actual = self.modified.joint_dist(states, log=True)
                    self.assertTrue(bool(torch.isfinite(actual).all()))
                    torch.testing.assert_close(actual, expected, atol=5e-5, rtol=5e-5)
                    torch.testing.assert_close(actual.exp().sum(-1),
                                               torch.ones_like(actual[..., 0]),
                                               atol=1e-6, rtol=1e-6)
                    old_bc = self.original.bc_logits(states)
                    new_bc = self.modified.bc_logits(states)
                    for wanted, observed in zip(old_bc, new_bc):
                        self.assertTrue(bool(torch.isfinite(observed).all()))
                        torch.testing.assert_close(observed, wanted, atol=5e-5, rtol=5e-5)
                    combined = self.modified.training_outputs(states)
                    for wanted, observed in zip((actual, *new_bc), combined):
                        torch.testing.assert_close(observed, wanted, atol=1e-6, rtol=1e-6)

    def test_shared_training_encoder_preserves_loss_and_parameter_gradients(self):
        self.assertEqual(float(config.RL_CONFIG.dropout), 0.0,
                         "Shared encoder equivalence requires deterministic dropout-free encoding")
        self.modified.train()
        parameters = tuple(self.modified.parameters())
        for density in ("empty", "sparse", "dense"):
            with self.subTest(bag=density):
                states = self._states(density)
                actions = torch.tensor([13, 57], dtype=torch.long)
                expert = torch.tensor([True, False])

                def loss_from_outputs(outputs):
                    joint_logp, *bc = outputs
                    # Fixed Bellman label plus an expert BC term exercise both
                    # contributions to the shared trunk's accumulated gradient.
                    critic = -joint_logp[torch.arange(2), actions, 24].mean()
                    return critic + 0.3 * _expert_loss(bc, actions, expert, subset=False)

                separate = (self.modified.joint_dist(states, log=True),
                            *self.modified.bc_logits(states))
                expected_loss = loss_from_outputs(separate)
                expected_grads = torch.autograd.grad(expected_loss, parameters,
                                                     allow_unused=True)
                shared = self.modified.training_outputs(states)
                actual_loss = loss_from_outputs(shared)
                actual_grads = torch.autograd.grad(actual_loss, parameters,
                                                   allow_unused=True)
                torch.testing.assert_close(actual_loss, expected_loss,
                                           atol=1e-6, rtol=1e-6)
                for observed, wanted in zip(actual_grads, expected_grads):
                    if wanted is None:
                        self.assertIsNone(observed)
                    else:
                        self.assertIsNotNone(observed)
                        self.assertTrue(bool(torch.isfinite(observed).all()))
                        torch.testing.assert_close(observed, wanted,
                                                   atol=5e-6, rtol=5e-5)


class _Memory:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail
        self.lock = threading.Lock()

    def __len__(self):
        return 128

    def sample(self, batch_size, beta):
        if self.fail:
            raise ValueError("intentional replay sample failure")
        with self.lock:
            self.calls += 1
            sequence = self.calls
        states = np.full((batch_size, 7), sequence + 0.1234567, dtype=np.float32)
        actions = np.arange(batch_size, dtype=np.int32)
        rewards = np.full(batch_size, sequence, dtype=np.float32)
        next_states = np.full((batch_size, 7), sequence + 1.0, dtype=np.float16)
        dones = np.zeros(batch_size, dtype=np.uint8)
        horizons = np.full(batch_size, 16, dtype=np.uint8)
        experts = np.arange(batch_size) % 2 == 0
        actor_kind = np.full(batch_size, 2, dtype=np.uint8)
        indices = np.arange(batch_size, dtype=np.int64) + 100 * sequence
        weights = np.full(batch_size, beta, dtype=np.float32)
        return (states, actions, rewards, next_states, dones, horizons,
                experts, actor_kind, indices, weights)


class ReplayPrefetchCorrectnessTests(unittest.TestCase):
    def _prefetch(self, memory=None, **kwargs):
        memory = memory or _Memory()
        pipeline = ReplayPrefetcher(memory, batch_size=4, beta_fn=lambda: 0.7,
                                    device="cpu", depth=2, **kwargs)
        self.addCleanup(pipeline.close)
        return memory, pipeline

    def _get(self, pipeline):
        result = pipeline.get(timeout=2.0)
        self.assertIsNotNone(result, "Replay producer did not deliver a minibatch")
        return result

    def test_bounded_leases_reuse_storage_without_overwriting_consumers(self):
        memory, pipeline = self._prefetch()
        first, second = self._get(pipeline), self._get(pipeline)
        first.wait_on_current_stream()
        second.wait_on_current_stream()
        held = tuple(tensor.clone() for tensor in first.tensors)
        first_pointers = tuple(tensor.data_ptr() for tensor in first.tensors)
        self.assertIsNone(pipeline.get(timeout=0.05))
        self.assertEqual(memory.calls, 2)
        for before, after in zip(held, first.tensors):
            torch.testing.assert_close(before, after, atol=0.0, rtol=0.0)
        first.release()
        first.release()  # Idempotence must not enqueue the same slot twice.
        next_batch = self._get(pipeline)
        self.assertEqual(first_pointers,
                         tuple(tensor.data_ptr() for tensor in next_batch.tensors))
        self.assertGreater(float(next_batch.tensors[0][0, 0]), float(held[0][0, 0]))
        next_batch.release()
        second.release()
        with self.assertRaisesRegex(RuntimeError, "released"):
            first.wait_on_current_stream()

    def test_transfer_fields_dtypes_and_float32_bank_precision(self):
        _, pipeline = self._prefetch()
        prepared = self._get(pipeline)
        self.addCleanup(prepared.release)
        tensors = prepared.wait_on_current_stream()
        source_fields = (0, 1, 2, 3, 4, 5, 6, 9)
        dtypes = (torch.float32, torch.long, torch.float32, torch.float32,
                  torch.float32, torch.float32, torch.bool, torch.float32)
        for tensor, field, dtype in zip(tensors, source_fields, dtypes):
            self.assertEqual(tensor.dtype, dtype)
            expected = torch.from_numpy(prepared.batch[field]).to(dtype=dtype)
            torch.testing.assert_close(tensor, expected, atol=0.0, rtol=0.0)
        # The source fp32 value has more precision than fp16; staging retains it.
        self.assertNotEqual(float(tensors[0][0, 0]),
                            float(tensors[0][0, 0].to(torch.float16)))

    def test_pause_invalidate_resume_drops_old_generations(self):
        paused = threading.Event()
        memory, pipeline = self._prefetch(enabled_fn=lambda: not paused.is_set())
        first, second = self._get(pipeline), self._get(pipeline)
        paused.set()
        self.assertTrue(pipeline.invalidate(wait=True))
        self.assertFalse(first.is_current)
        self.assertFalse(second.is_current)
        first.release()
        second.release()
        calls = memory.calls
        self.assertIsNone(pipeline.get(timeout=0.08))
        self.assertEqual(memory.calls, calls, "Paused producer sampled after a released lease")
        paused.clear()
        fresh = self._get(pipeline)
        self.assertTrue(fresh.is_current)
        self.assertGreater(int(fresh.batch[8][0] // 100), 2)
        fresh.release()

    def test_invalidate_waits_for_inflight_sampling_and_discards_its_result(self):
        class BlockingMemory(_Memory):
            def __init__(self):
                super().__init__()
                self.started = threading.Event()
                self.finish = threading.Event()

            def sample(self, batch_size, beta):
                result = super().sample(batch_size, beta)
                if self.calls == 1:
                    self.started.set()
                    if not self.finish.wait(timeout=2.0):
                        raise RuntimeError("Test failed to release in-flight sampling")
                return result

        paused = threading.Event()
        memory = BlockingMemory()
        _, pipeline = self._prefetch(memory=memory,
                                     enabled_fn=lambda: not paused.is_set())
        self.addCleanup(memory.finish.set)
        self.assertTrue(memory.started.wait(timeout=2.0))
        paused.set()
        self.assertFalse(pipeline.invalidate(wait=True, timeout=0.03))
        memory.finish.set()
        self.assertTrue(pipeline.invalidate(wait=True, timeout=2.0))
        self.assertIsNone(pipeline.get(timeout=0.05))
        self.assertEqual(memory.calls, 1)
        paused.clear()
        fresh = self._get(pipeline)
        self.assertTrue(fresh.is_current)
        self.assertGreater(int(fresh.batch[8][0] // 100), 1)
        fresh.release()

    def test_close_with_outstanding_lease_is_safe(self):
        _, pipeline = self._prefetch()
        prepared = self._get(pipeline)
        snapshot = prepared.tensors[0].clone()
        self.assertTrue(pipeline.close(timeout=2.0))
        self.assertFalse(prepared.is_current)
        torch.testing.assert_close(prepared.tensors[0], snapshot, atol=0.0, rtol=0.0)
        prepared.release()
        prepared.release()
        self.assertIsNone(pipeline.get(timeout=0.0))

    def test_producer_errors_are_reported_to_learner(self):
        _, pipeline = self._prefetch(memory=_Memory(fail=True))
        with self.assertRaisesRegex(RuntimeError, "producer failed") as raised:
            pipeline.get(timeout=2.0)
        self.assertIsInstance(raised.exception.__cause__, ValueError)
        self.assertTrue(pipeline.close(timeout=2.0))


if __name__ == "__main__":
    # Limit this correctness process; the live learner can be benchmarked
    # concurrently without a 72-thread CPU test stealing the Grace cores.
    torch.set_num_threads(2)
    unittest.main(verbosity=2)
