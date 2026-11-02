"""Decision-relevant checks for journal filtering, independent blocks, and intervals."""
import json
from pathlib import Path
import tempfile
import unittest

from .analyze_learning_games import (
    bootstrap_comparison, comparison_warnings, make_report, read_games, select_block, summarize,
)


def game(identifier, score=1000, label="baseline", start=100, end=120, **changes):
    row = dict(journal_game_id=identifier, eligible=True, complete=True, known_start=True,
               eval_only=True, experiment=label, score=score, playable_frames=100,
               duration_s=end-start, start_unix_s=start, end_unix_s=end,
               client_slot=4, start_context=dict(experiment=label, learner_frames=start*10),
               end_context=dict(experiment=label, learner_frames=end*10))
    row.update(changes)
    return row


class LearningGameAnalysisTests(unittest.TestCase):
    def test_read_snapshot_excludes_partial_training_duplicate_and_incomplete_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "games.jsonl"
            rows = [game("good"), game("partial", known_start=False),
                    game("training", eval_only=False), game("good"),
                    game("excluded", eligible=False), game("zero", score=0)]
            data = "".join(json.dumps(row)+"\n" for row in rows) + '{"journal_game_id":'
            path.write_text(data)
            actual, diagnostics, warnings = read_games([path])
            self.assertEqual({row["journal_game_id"] for row in actual}, {"good", "zero"})
            self.assertEqual(diagnostics["duplicate_game_ids"], 1)
            self.assertEqual(diagnostics["incomplete_trailing_lines"], 1)
            self.assertTrue(warnings)
            self.assertEqual(path.read_text(), data)

    def test_completion_blocks_have_no_overlap_and_rate_uses_frame_weighting(self):
        rows = [game(f"candidate-{i}", score=100*i, label="candidate", end=120+i,
                     playable_frames=10*i) for i in range(1, 7)]
        first, first_selection = select_block(rows, "candidate", skip=0, limit=3)
        second, second_selection = select_block(rows, "candidate", skip=3, limit=3)
        self.assertFalse(set(first_selection["game_ids"]) & set(second_selection["game_ids"]))
        self.assertEqual(second_selection["game_ids"], ["candidate-4", "candidate-5", "candidate-6"])
        summary = summarize(first, "candidate", first_selection)
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["mean"], 200)
        self.assertEqual(summary["score_per_observed_playable_frame"], 10)

    def test_bootstrap_known_difference_ratio_and_reproducibility(self):
        baseline = [game(str(i), score=1000) for i in range(5)]
        candidate = [game(str(i), score=1200) for i in range(5)]
        result = bootstrap_comparison(baseline, candidate, iterations=100, seed=19)
        self.assertEqual(result["mean_difference"]["ci"], [200, 200])
        self.assertEqual(result["mean_ratio"]["ci"], [1.2, 1.2])
        candidate[-1]["score"] = 9000
        self.assertEqual(bootstrap_comparison(baseline, candidate, iterations=100, seed=19),
                         bootstrap_comparison(baseline, candidate, iterations=100, seed=19))

    def test_zero_baseline_uses_difference_and_leaves_ratio_undefined(self):
        result = bootstrap_comparison([game("b", score=0)], [game("c", score=100)],
                                      iterations=100)
        self.assertEqual(result["mean_difference"]["estimate"], 100)
        self.assertIsNone(result["mean_ratio"]["estimate"])
        self.assertIsNone(result["mean_ratio"]["ci"])

    def test_report_warns_about_small_samples_and_different_completion_tails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "games.jsonl"
            rows = [game("b1", start=100, end=110), game("b2", start=101, end=111),
                    game("c1", label="candidate", start=200, end=240),
                    game("c2", label="candidate", start=230, end=270)]
            path.write_text("".join(json.dumps(row)+"\n" for row in rows))
            report = make_report([path], baseline="baseline", candidate="candidate", iterations=100)
            warnings = " ".join(report["warnings"])
            self.assertIn("<30", warnings)
            self.assertIn("completion-window spans", warnings)
            self.assertIn("completion tails", warnings)
            self.assertIn("iid-game approximation", warnings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
