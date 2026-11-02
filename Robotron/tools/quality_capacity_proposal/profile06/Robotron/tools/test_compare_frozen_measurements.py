"""Frozen receipt rejection and reproducible comparison checks using small fixtures."""
import copy
import unittest

from .compare_frozen_measurements import compare_receipts, validate_receipt


def receipt(label="policy", offset=0):
    rows = []
    for index in range(50):
        context = dict(experiment=label, measurement_active=True, measurement_generation=1,
                       epsilon=0.0, expert_ratio=0.0, difficulty=5, training_steps=100,
                       optimized_samples=204800, learner_frames=100000)
        rows.append(dict(journal_game_id=f"{label}:{index}", eligible=True, complete=True,
                         known_start=True, eval_only=True, measurement_active=True,
                         measurement_generation=1, experiment=label, first_play_level=1,
                         client_slot=index % 5, score=1000+index*100+offset,
                         start_unix_s=100+index, end_unix_s=120+index, duration_s=20,
                         playable_frames=1200, start_context=context, end_context=dict(context)))
    return dict(valid=True, complete=True, active=False, label=label, generation=1,
                pending=0, abandoned=0, started=50, count=50, start_ts=100, close_ts=160,
                frame_stack=4, engine_version=28, state_size=11128, rows=rows,
                boundary=dict(ready=True, generation=1, actor_slots=list(range(5))),
                clocks=dict(training_steps=100, optimized_samples=204800, learner_frame_count=100000))


class FrozenComparisonTests(unittest.TestCase):
    def test_invalid_incomplete_pending_abandoned_and_small_legs_are_rejected(self):
        for field, value in (("valid", False), ("complete", False), ("active", True),
                             ("pending", 1), ("abandoned", 1), ("started", 51)):
            with self.subTest(field=field):
                data = receipt()
                data[field] = value
                with self.assertRaises(ValueError):
                    validate_receipt(data)
        data = receipt()
        data["rows"].pop()
        data["started"] = data["count"] = 49
        with self.assertRaisesRegex(ValueError, "At least 50"):
            validate_receipt(data)

    def test_changing_clocks_or_protocol_and_mismatched_legs_are_rejected(self):
        for key, value in (("optimized_samples", 204801), ("epsilon", .1),
                           ("difficulty", 4), ("frame_stack", 2)):
            with self.subTest(key=key):
                data = receipt()
                data["rows"][-1]["end_context"][key] = value
                with self.assertRaises(ValueError):
                    validate_receipt(data)
        candidate = receipt("candidate")
        candidate["frame_stack"] = 2
        with self.assertRaisesRegex(ValueError, "protocols differ"):
            compare_receipts(receipt(), candidate, iterations=100)

    def test_known_shift_is_preserved_by_paired_actor_resampling(self):
        report = compare_receipts(receipt("base"), receipt("candidate", offset=500),
                                  iterations=100, seed=8)
        self.assertEqual(report["score_delta"], 500)
        self.assertEqual(report["actor_cluster_bootstrap"]["mean_difference_ci"], [500, 500])

    def test_nested_rows_and_late_completion_are_valid_without_mutating_inputs(self):
        data = receipt()
        data["cohort"] = dict(rows=data.pop("rows"), pending=0, abandoned=0,
                              started=50, count=50, valid=True, complete=True, closed=True)
        original = copy.deepcopy(data)
        self.assertEqual(len(validate_receipt(data)["rows"]), 50)
        self.assertGreater(data["cohort"]["rows"][-1]["end_unix_s"], data["close_ts"])
        self.assertEqual(data, original)

    def test_identity_comparison_is_deterministic_and_paired_clusters_are_exact(self):
        data = receipt()
        report = compare_receipts(data, data, iterations=200, seed=19)
        self.assertEqual(report, compare_receipts(data, data, iterations=200, seed=19))
        self.assertEqual((report["score_delta"], report["score_ratio"]), (0, 1))
        clustered = report["actor_cluster_bootstrap"]
        self.assertEqual(clustered["method"], "paired actor-slot clusters")
        self.assertEqual(clustered["mean_difference_ci"], [0, 0])
        self.assertEqual(clustered["mean_ratio_ci"], [1, 1])

    def test_coverage_difference_uses_independent_clusters_and_zero_ratio_is_undefined(self):
        base, candidate = receipt("base"), receipt("candidate")
        candidate["boundary"]["actor_slots"] = [5, 6, 7, 8, 9]
        for row in base["rows"]:
            row["score"] = 0
        for row in candidate["rows"]:
            row["client_slot"] += 5
        report = compare_receipts(base, candidate, iterations=100)
        self.assertEqual(report["actor_cluster_bootstrap"]["method"], "independent actor-slot clusters")
        self.assertIsNone(report["score_ratio"])
        self.assertIsNone(report["game_bootstrap"]["mean_ratio_ci"])


if __name__ == "__main__":
    unittest.main()
