"""CPU equivalence/ownership tests for opt-in final-buffer replay filling."""

from contextlib import ExitStack
import threading
import unittest
from unittest.mock import patch

import numpy as np
import torch

from . import replay_buffer
from .prefetch import ReplayPrefetcher


class DirectReplayTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in dict(hof_max_episodes=2, ephof_max_episodes=2,
                                hof_episode_stride=64, ephof_episode_stride=64,
                                hof_min_transitions=2, ephof_min_transitions=2,
                                interesting_replay_bank_size=64).items():
            self.stack.enter_context(patch.object(replay_buffer.RL_CONFIG, name, value))
        self.memory = replay_buffer.PrioritizedReplayBuffer(64, 7)
        for i in range(64):
            state = np.full(7, i / 10, dtype=np.float32)
            self.memory.add(state, i % 81, i / 100, -state, i % 9 == 0,
                            horizon=1+i % 16, expert=i % 3 == 0, actor_kind=i % 3,
                            interest=1.0 if i % 4 == 0 else 0.0)
        for bank in ("hof", "ephof"):
            setattr(self.memory, f"{bank}_total", 4)
            setattr(self.memory, f"_{bank}_flat", np.arange(4, dtype=np.int64))
            for field in ("states", "next_states"):
                array = getattr(self.memory, f"{bank}_{field}")
                array[:4] = np.float32(1.000123 if field == "states" else -2.000321)
            getattr(self.memory, f"{bank}_actor_kind")[:4] = 2
            getattr(self.memory, f"{bank}_is_expert")[:4] = 1

    def compare(self, batch_size=20):
        np.random.seed(731)
        rng_before = np.random.get_state()
        tree_before = self.memory.tree.tree.copy()
        expected = self.memory.sample(batch_size, beta=.7)
        rng_after = np.random.get_state()
        np.random.set_state(rng_before)
        outputs = [np.empty((batch_size, 7), dtype=np.float32) for _ in range(2)]
        actual = self.memory.sample_into(batch_size, *outputs, beta=.7)
        for wanted, observed in zip(expected, actual):
            self.assertEqual(wanted.dtype, observed.dtype)
            np.testing.assert_array_equal(wanted, observed)
        for wanted, observed in zip(rng_after, np.random.get_state()):
            np.testing.assert_array_equal(wanted, observed)
        np.testing.assert_array_equal(self.memory.tree.tree, tree_before)
        self.assertIs(actual[0], outputs[0]); self.assertIs(actual[3], outputs[1])
        return actual

    def test_mixed_quotas_indices_weights_rng_and_bank_precision_are_exact(self):
        actual = self.compare()
        bank = actual[8] >= self.memory.capacity
        self.assertTrue(bank.any())
        self.assertTrue(np.any(actual[0][bank] != actual[0][bank].astype(np.float16).astype(np.float32)))

    def test_zero_bank_recent_and_interest_quotas_remain_exact(self):
        self.memory._hof_enabled = self.memory._ephof_enabled = False
        with patch.object(replay_buffer.RL_CONFIG, "recent_replay_fraction", 0), \
                patch.object(replay_buffer.RL_CONFIG, "interesting_replay_fraction", 0):
            self.compare()

    def test_bad_output_rejected_before_sampling_or_rng_changes(self):
        valid = np.empty((20, 7), dtype=np.float32)
        readonly = valid.copy(); readonly.flags.writeable = False
        invalid = [readonly, np.empty((20, 7), dtype=np.float16),
                   np.empty((20, 14), dtype=np.float32)[:, ::2],
                   np.empty((21, 7), dtype=np.float32), self.memory.hof_states[:20]]
        for output in invalid:
            state = np.random.get_state()
            with self.assertRaises(ValueError):
                self.memory.sample_into(20, output, valid)
            for wanted, observed in zip(state, np.random.get_state()):
                np.testing.assert_array_equal(wanted, observed)
        with self.assertRaises(ValueError):
            self.memory.sample_into(20, valid, valid)

    def test_non_native_fill_and_zero_bank_rows_preserve_float32(self):
        source = np.arange(70, dtype=np.float32).reshape(10, 7) + np.float32(.000123)
        indices = np.array([3, 0, 9], dtype=np.int64)
        output = np.empty((3, 7), dtype=np.float32)
        actual = replay_buffer._fill_state_rows(output, source[:, ::-1], indices,
                                                [(source, indices[:0])])
        np.testing.assert_array_equal(actual, source[:, ::-1][indices])
        with self.assertRaises(IndexError):
            replay_buffer._fill_state_rows(output, source, np.array([99, 0, 1]), [])

    def test_metadata_and_tree_output_aliases_cannot_corrupt_replay(self):
        outputs = [self.memory.rewards[:28].reshape(4, 7),
                   self.memory.hof_rewards[:28].reshape(4, 7),
                   self.memory.tree.tree.view(np.float32)[:28].reshape(4, 7)]
        rewards, tree = self.memory.rewards.copy(), self.memory.tree.tree.copy()
        valid = np.empty((4, 7), dtype=np.float32)
        for output in outputs:
            with self.assertRaisesRegex(ValueError, "alias replay storage"):
                self.memory.sample_into(4, output, valid)
            np.testing.assert_array_equal(self.memory.rewards, rewards)
            np.testing.assert_array_equal(self.memory.tree.tree, tree)


class FillMemory:
    state_size = 7
    def __init__(self):
        self.calls = 0
        self.block = False
        self.started, self.finish = threading.Event(), threading.Event()
    def __len__(self):
        return 128
    def sample(self, size, beta):
        raise AssertionError("Opt-in producer unexpectedly used allocating sample")
    def sample_into(self, size, states_out, next_states_out, beta):
        self.calls += 1
        states_out.fill(np.float32(self.calls+.000123))
        next_states_out[:] = -states_out
        if self.block and self.calls == 1:
            self.started.set()
            if not self.finish.wait(2):
                raise TimeoutError("Test failed to release direct sampling")
        return (states_out, np.arange(size, dtype=np.int64), np.ones(size, np.float32),
                next_states_out, np.zeros(size, np.float32), np.ones(size, np.int32),
                np.ones(size, np.uint8), np.full(size, 2, np.uint8),
                np.arange(size, dtype=np.int64), np.full(size, beta, np.float32))


class DirectPrefetchTests(unittest.TestCase):
    def pipeline(self, memory, **kwargs):
        pipeline = ReplayPrefetcher(memory, 4, lambda: .7, "cpu", depth=2,
                                    direct_state_fill=True, **kwargs)
        self.addCleanup(pipeline.close)
        return pipeline

    def test_direct_leases_alias_final_host_storage_without_overwrites(self):
        memory = FillMemory(); pipeline = self.pipeline(memory)
        first, second = pipeline.get(2), pipeline.get(2)
        self.assertIsNotNone(first); self.assertIsNotNone(second)
        held = first.tensors[0].clone()
        pointer = first.tensors[0].data_ptr()
        self.assertEqual(first.batch[0].ctypes.data, pointer)
        self.assertIsNone(pipeline.get(.03))
        self.assertEqual(memory.calls, 2)
        torch.testing.assert_close(first.tensors[0], held, rtol=0, atol=0)
        first.release()
        fresh = pipeline.get(2)
        self.assertIsNotNone(fresh)
        self.assertEqual(fresh.tensors[0].data_ptr(), pointer)
        self.assertGreater(float(fresh.tensors[0][0, 0]), float(held[0, 0]))
        self.assertGreaterEqual(fresh.stage_host_ms, 0)
        fresh.release(); second.release()

    def test_invalidate_waits_for_direct_fill_and_discards_old_slot(self):
        memory = FillMemory(); memory.block = True
        paused = threading.Event()
        pipeline = self.pipeline(memory, enabled_fn=lambda: not paused.is_set())
        self.addCleanup(memory.finish.set)
        self.assertTrue(memory.started.wait(2))
        paused.set()
        self.assertFalse(pipeline.invalidate(timeout=.02))
        memory.finish.set()
        self.assertTrue(pipeline.invalidate(timeout=2))
        self.assertIsNone(pipeline.get(.03))
        paused.clear()
        fresh = pipeline.get(2)
        self.assertIsNotNone(fresh); self.assertTrue(fresh.is_current)
        self.assertGreaterEqual(pipeline.direct_state_batches, 2)
        fresh.release()

    def test_optin_with_unsupported_memory_retains_allocating_fallback(self):
        class AllocatingOnly:
            def __len__(self):
                return 128
            def sample(self, size, beta):
                return FillMemory().sample_into(size, np.empty((size, 7), np.float32),
                                                np.empty((size, 7), np.float32), beta)
        pipeline = self.pipeline(AllocatingOnly())
        prepared = pipeline.get(2)
        self.assertIsNotNone(prepared)
        self.assertFalse(pipeline.direct_state_fill)
        self.assertEqual(pipeline.direct_state_batches, 0)
        prepared.release()


if __name__ == "__main__":
    torch.set_num_threads(2)
    unittest.main(verbosity=2)
