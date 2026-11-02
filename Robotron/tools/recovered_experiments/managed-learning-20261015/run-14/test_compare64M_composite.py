"""CPU-only composite math/gates, plus actual already-published reference checks."""
import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).with_name("compare64M_composite.py")
SPEC = importlib.util.spec_from_file_location("composite64", PATH)
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


def rows(scores):
    return [dict(score=score, client_slot=4096 + index % 16, journal_game_id=str(index))
            for index, score in enumerate(scores)]


class CompositeTests(unittest.TestCase):
    def test_receipt_changed_after_validation_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            before = b'{"a":1}\n'
            path.write_bytes(before)
            evidence = [dict(path=str(path), sha256=hashlib.sha256(before).hexdigest())]
            REPORT.recheck_receipt_evidence(evidence)
            path.write_bytes(b'{"a":2}\n')
            with self.assertRaisesRegex(ValueError, "changed before publication"):
                REPORT.recheck_receipt_evidence(evidence)

    def test_unequal_leg_counts_use_original_rows_not_average_of_means(self):
        result = REPORT.summarize(rows([0] * 50 + [100] * 150), ["a", "b"])
        self.assertEqual(result["count"], 200)
        self.assertEqual(result["mean"], 75)
        self.assertEqual(result["median"], 100)
        self.assertNotIn("valid", result)
        self.assertNotIn("complete", result)

    def test_pooled_gain_does_not_hide_failed_leg_or_median(self):
        reference = rows([100] * 16)
        result = REPORT.management_gate(reference, {"a": rows([104] * 16), "b": rows([200] * 16)})
        self.assertFalse(result["confirmation_gate_passed"])
        self.assertFalse(result["each_candidate"]["a"]["mean_at_least5pct"])
        result = REPORT.management_gate(reference, {"screen": rows([1, 1, 400])})
        self.assertTrue(result["each_candidate"]["screen"]["mean_at_least5pct"])
        self.assertFalse(result["each_candidate"]["screen"]["median_at_least_reference"])
        result = REPORT.management_gate(reference, {"screen": rows([150] * 16)})
        self.assertTrue(result["every_supplied_leg_passes"])
        self.assertFalse(result["confirmation_gate_passed"])

    def test_slot_pairing_and_descriptive_bootstrap_use_original_rows(self):
        baseline = rows(list(range(100, 116)))
        candidate = rows(list(range(150, 166)))
        result = REPORT.analyze_rows(baseline, candidate, ["reference"], ["screen"], 100)
        self.assertEqual(result["mean_difference"], 50)
        self.assertEqual(result["slots_with_positive_mean_contrast"], 16)
        self.assertEqual(result["paired_slot_bootstrap"]["mean_difference_ci"], [50, 50])

    def test_both_actual_reference_receipts_and_learner_clock_alias(self):
        plan = REPORT.pinned_json(REPORT.CAMPAIGN / "run-13/quality64M-composite-reference-plan.json", REPORT.REFERENCE_PLAN_SHA)
        all_rows = []
        for source in plan["reference"]["sources"]:
            _, leg, _ = REPORT.validate_leg(source["label"], expected_sha=REPORT.REFERENCE_MODEL_SHA,
                clocks=REPORT.REFERENCE_CLOCKS, receipt_sha=source["sha256"])
            self.assertEqual(leg["clocks"]["learner_frames"], 36632770)
            all_rows.extend(leg["rows"])
        result = REPORT.summarize(all_rows, [])
        self.assertEqual(result["count"], 236)
        self.assertEqual(result["mean"], 121245.33898305085)
        self.assertEqual(result["median"], 124125)


if __name__ == "__main__":
    unittest.main()
