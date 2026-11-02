"""Pure CPU protocol tests; no trainer imports or live mutations."""

from collections import deque
from types import SimpleNamespace
import unittest

from .frozen_evaluation import (
    FrozenCohort, FrozenPolicy, reset_async_episode_tracking, reset_client_replay_segment,
)


class TestFrozenEvaluation(unittest.TestCase):
    def test_controls_apply_equally_to_all_actor_roles(self):
        policy = FrozenPolicy("reference", 5)
        for _role in ("training", "eval"):
            self.assertEqual(policy.controls(), dict(
                epsilon=0.0, expert_ratio=0.0, action_source="measurement",
                count_learner=False, store_replay=False, update_schedules=False,
            ))

    def test_replay_boundaries_discard_pending_segments_only(self):
        class Pending:
            def __init__(self):
                self.rows = ["before measurement"]
            def reset(self):
                self.rows.clear()
        pending = Pending()
        client = dict(nstep=pending, frame_history=deque([1, 2]), last_state=object(),
                      last_action=(2, 4), prev_action_source="dqn", ep_frames=55,
                      ep_dqn_reward=3.0, fire_hold_dir=2, fire_hold_count=2,
                      game_uid=39, was_done=False, game_score=1000)
        reset_client_replay_segment(client, 1000)
        self.assertEqual(pending.rows, [])
        self.assertEqual(list(client["frame_history"]), [])
        self.assertIsNone(client["last_state"])
        self.assertIsNone(client["last_action"])
        self.assertEqual(client["ep_frames"], 0)
        self.assertEqual(client["ep_start_score"], 1000)
        self.assertTrue(client["replay_episode_partial"])
        self.assertEqual(client["game_uid"], 39)
        replay = object()
        buffer = SimpleNamespace(_client_indices={1: [5]}, _episode_indices={1: [5]},
                                 memory=replay, _elite_thr_hwm={90: (50000, 6)})
        reset_async_episode_tracking(buffer)
        self.assertEqual(buffer._client_indices, {})
        self.assertEqual(buffer._episode_indices, {})
        self.assertIs(buffer.memory, replay)
        self.assertEqual(buffer._elite_thr_hwm, {90: (50000, 6)})

    def test_start_side_cohort_waits_for_slow_game_and_includes_zero(self):
        cohort = FrozenCohort(FrozenPolicy("candidate", 4), frozenset([1, 2]), 1)
        self.assertFalse(cohort.start("old", 1, known_start=False, generation=4))
        self.assertFalse(cohort.start("old_policy", 1, known_start=True, generation=3))
        self.assertTrue(cohort.start("slow", 1, known_start=True, generation=4))
        self.assertTrue(cohort.start("fast", 2, known_start=True, generation=4))
        self.assertFalse(cohort.start("replacement", 2, known_start=True, generation=4))
        cohort.finish("fast", score=0, eligible=True, generation=4)
        self.assertFalse(cohort.complete)
        with self.assertRaises(RuntimeError):
            cohort.scores_by_actor()
        cohort.finish("slow", score=100000, eligible=True, generation=4)
        self.assertTrue(cohort.complete)
        self.assertEqual(cohort.scores_by_actor(), {1: [100000.0], 2: [0.0]})

    def test_invalid_game_or_timeout_makes_leg_inconclusive(self):
        for invalid_reason in ("disconnect", "policy_changed", "timeout"):
            cohort = FrozenCohort(FrozenPolicy("reference", 2), frozenset([1]), 1)
            cohort.start("game", 1, known_start=True, generation=2)
            if invalid_reason == "timeout":
                cohort.abort("timeout")
            else:
                cohort.finish("game", score=9, eligible=False, generation=2, reason=invalid_reason)
            self.assertFalse(cohort.complete)
            self.assertTrue(cohort.invalid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
