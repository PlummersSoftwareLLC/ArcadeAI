"""Whole-game measurement must not mistake life ends or partial games for games."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from .game_journal import GameJournal


class GameJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1000.0
        self.journal = GameJournal(self.temp.name, clock=lambda: self.now)
        self.cs = dict(client_slot=14, game_uid=1, eval_only=True,
                       journal_experiment="baseline")
        self.frames = 0

    def context(self):
        return dict(experiment=self.cs["journal_experiment"], fleet_frames=self.frames,
                    learner_frames=self.frames // 2, optimized_samples=self.frames * 32,
                    epsilon=0.01)

    def observe(self, score=0, alive=True, done=False, lives=3, start=False,
                new_game=False, level=1):
        self.now += 1
        self.frames += 8
        frame = SimpleNamespace(game_score=score, level_number=level,
                                player_alive=alive, done=done, lives=lives,
                                start_pressed=start)
        self.journal.observe(9, frame, self.cs, new_game=new_game, context=self.context)

    def rows(self, filename="games.jsonl"):
        path = Path(self.temp.name) / filename
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def start_known_game(self):
        self.observe(score=12000)
        self.cs["game_uid"] = 2
        self.observe(score=0, alive=False, new_game=True)
        self.observe(score=0)

    def test_small_final_score_is_included_once_and_startup_is_excluded(self):
        self.start_known_game()
        self.observe(score=100, done=True, alive=False, lives=2)
        self.observe(score=100, done=True, alive=False, lives=2)
        self.observe(score=100)
        self.observe(score=700, done=True, alive=False, lives=1)
        self.observe(score=700)
        self.cs["game_uid"] = 3
        self.observe(score=0, alive=False, new_game=True)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[0]["eligible"])
        self.assertEqual(rows[0]["excluded_reason"], "startup_attachment")
        game = rows[1]
        self.assertTrue(game["eligible"])
        self.assertEqual(game["score"], 700)
        self.assertEqual(game["deaths"], 2)
        self.assertEqual(game["client_slot"], 14)
        self.assertEqual(game["start_context"]["fleet_frames"], 16)
        self.assertEqual(game["end_context"]["fleet_frames"], self.frames)
        self.assertEqual(self.journal.summary()["count"], 1)
        self.assertEqual(self.journal.summary()["mean"], 700)
        self.assertEqual(len(self.rows("lives.jsonl")), 2)

    def test_repeated_zero_score_games_are_retained_without_score_drop(self):
        self.start_known_game()
        for life in range(3):
            self.observe(score=0, alive=False, done=True, lives=max(0, 2-life))
            if life < 2:
                self.observe(score=0, lives=max(0, 2-life))
        self.assertEqual(self.journal.summary()["count"], 1)
        self.assertEqual(self.journal.summary()["mean"], 0)
        # Lua's wire lives counter does not reset when score stays zero.
        self.observe(alive=False, lives=0, start=True)
        self.observe(alive=True, lives=0)
        for life in range(3):
            self.observe(alive=False, done=True, lives=0)
            if life < 2:
                self.observe(alive=True, lives=0)
        self.assertEqual(self.journal.summary()["count"], 2)
        self.assertEqual(self.rows()[-1]["start_reason"], "zero_score_restart")
        self.assertEqual(self.rows()[-1]["boundary_reason"], "zero_score_lives_exhausted")

    def test_life_end_is_not_full_game_and_score_wrap_is_not_reset(self):
        self.start_known_game()
        self.observe(score=4000, alive=False, done=True, lives=2)
        self.assertEqual(self.journal.summary()["count"], 0)
        self.observe(score=4000)
        self.observe(score=100000100, level=257)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.journal.active[9]["max_level"], 257)

    def test_wire_exhaustion_does_not_duplicate_at_following_score_reset(self):
        self.start_known_game()
        self.observe(score=1200, alive=False, done=True, lives=0)
        self.assertEqual(self.journal.summary()["count"], 1)
        self.cs["game_uid"] = 3
        self.observe(score=0, alive=False, new_game=True)
        self.assertEqual(self.journal.summary()["count"], 1)

    def test_boot_inactive_terminal_is_not_counted_as_an_observed_life(self):
        self.observe(alive=False, done=True, lives=2)
        self.observe(alive=False, done=False, lives=2)
        self.assertEqual(len(self.rows("lives.jsonl")), 0)
        self.assertEqual(self.journal.active[9]["deaths"], 0)

    def test_attract_fields_are_excluded_and_not_inherited_after_real_reset(self):
        # Observed at live startup: boot/attract RAM reports level 171 and
        # unknown lives.  Keep its raw evidence, exclude the attachment.
        self.observe(score=400, level=171, alive=False, lives=255)
        self.observe(score=400, level=0, alive=True, lives=255)
        self.observe(score=400, level=0, alive=False, done=True, lives=255)
        self.cs["game_uid"] = 2
        self.observe(score=0, level=1, alive=False, lives=3, new_game=True)
        self.observe(score=0, level=1, alive=True, lives=3)
        self.observe(score=700, level=1, alive=False, done=True, lives=0)
        partial, full = self.rows()
        self.assertEqual(partial["max_level"], 171)
        self.assertFalse(partial["eligible"])
        self.assertEqual(partial["excluded_reason"], "startup_attachment")
        self.assertTrue(full["eligible"])
        self.assertEqual(full["max_level"], 1)
        self.assertEqual(full["score"], 700)
        self.assertEqual(self.journal.summary()["count"], 1)

    def test_experiment_crossing_is_excluded_even_if_label_returns(self):
        self.start_known_game()
        self.cs["journal_experiment"] = "trial"
        self.observe(score=1000)
        self.cs["journal_experiment"] = "baseline"
        self.observe(score=2000, alive=False, done=True, lives=0)
        self.assertFalse(self.rows()[-1]["eligible"])
        self.assertEqual(self.rows()[-1]["excluded_reason"], "experiment_changed")

    def test_disconnect_retains_partial_and_summary_separates_eval_clients(self):
        self.start_known_game()
        self.observe(score=1500)
        self.journal.disconnect(9, self.context)
        self.assertFalse(self.rows()[-1]["complete"])
        self.assertEqual(self.rows()[-1]["excluded_reason"], "disconnect")
        self.cs["eval_only"] = False
        self.start_known_game()
        self.observe(score=1000, alive=False, done=True, lives=0)
        self.assertEqual(self.journal.summary()["count"], 0)
        self.assertEqual(self.journal.summary(eval_only=False)["count"], 1)

    def enable_measurement(self, generation=1):
        self.cs["eval_only"] = False  # The whole fleet becomes evaluation actors.
        self.cs["journal_experiment"] = "frozen-A"
        self.cs["journal_measurement_active"] = True
        self.cs["journal_measurement_generation"] = generation
        original = self.context
        self.context = lambda: dict(original(), measurement_active=True,
                                    measurement_generation=generation)

    def test_start_side_cohort_waits_for_late_high_score_tail(self):
        self.enable_measurement()
        self.start_known_game()
        start = 1002
        self.observe(score=100, alive=False, done=True, lives=0)  # t=1004
        self.cs["game_uid"] = 3
        self.observe(score=0, alive=False, new_game=True)        # t=1005
        self.observe(score=0)                                  # t=1006
        status = self.journal.cohort_status("frozen-A", start, 1005)
        self.assertTrue(status["closed"])
        self.assertFalse(status["complete"])
        self.assertEqual((status["started"], status["count"], status["pending"]), (2, 1, 1))
        self.assertEqual(status["started_actor_slots"], [14])
        # Shrinking the rolling display history cannot evict cohort members.
        from collections import deque
        self.journal.completed = deque(maxlen=1)
        self.now = 1200
        self.observe(score=900000, alive=False, done=True, lives=0)
        status = self.journal.cohort_status("frozen-A", start, 1005)
        self.assertTrue(status["complete"])
        self.assertTrue(status["valid"])
        self.assertEqual(status["count"], 2)
        self.assertEqual(status["mean"], 450050)
        self.assertTrue(all(row["eval_only"] and row["measurement_active"] for row in status["rows"]))
        self.assertEqual(status["pending_ids"], [])
        self.assertEqual(status["abandoned_ids"], [])

    def test_cohort_abandonment_is_explicit_and_does_not_shrink_started(self):
        self.enable_measurement()
        self.start_known_game()
        self.journal.disconnect(9, self.context)
        self.now = 2000
        status = self.journal.cohort_status("frozen-A", 1002, 1005)
        self.assertEqual(status["started"], 1)
        self.assertEqual(status["abandoned"], 1)
        self.assertEqual(status["count"], 0)
        self.assertFalse(status["valid"])
        self.assertFalse(status["complete"])
        self.assertIn("disconnect", status["abandonment_reasons"].values())

    def test_measurement_generation_change_excludes_game_in_flight(self):
        self.enable_measurement()
        self.start_known_game()
        prior_context = self.context
        next_context = lambda: dict(prior_context(), measurement_generation=2, measurement_active=False)
        self.journal.policy_boundary(9, next_context)
        self.now = 2000
        status = self.journal.cohort_status("frozen-A", 1002, 1005)
        self.assertEqual(status["abandoned"], 1)
        self.assertEqual(self.journal.summary()["count"], 0)
        self.assertEqual(self.rows()[-1]["excluded_reason"], "measurement_policy_changed")

    def test_measurement_cohort_rejects_non_wave_one_start(self):
        self.enable_measurement()
        self.observe(score=10000, level=5)
        self.cs["game_uid"] = 2
        self.observe(score=0, level=5, new_game=True)
        self.observe(score=1000, level=5, alive=False, done=True, lives=0)
        self.now = 2000
        status = self.journal.cohort_status("frozen-A", 1002, 1005)
        self.assertEqual(status["started"], 1)
        self.assertEqual(status["abandoned"], 1)
        self.assertEqual(status["count"], 0)

    def test_stale_wave_on_inactive_reset_frame_is_not_a_non_wave_one_start(self):
        self.enable_measurement()
        self.observe(score=20000, level=3)
        self.cs["game_uid"] = 2
        self.observe(score=0, level=3, alive=False, new_game=True)
        self.observe(score=0, level=1, alive=False)
        self.observe(score=0, level=1, alive=True)
        self.observe(score=1000, level=1, alive=False, done=True, lives=0)
        self.now = 2000
        status = self.journal.cohort_status("frozen-A", 1002, 1005)
        self.assertTrue(status["complete"])
        self.assertEqual((status["started"], status["count"], status["abandoned"]), (1, 1, 0))
        self.assertEqual(status["rows"][0]["first_play_level"], 1)
        self.assertEqual(status["rows"][0]["max_level"], 1)
        self.assertEqual(status["rows"][0]["start_frame"]["level"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
