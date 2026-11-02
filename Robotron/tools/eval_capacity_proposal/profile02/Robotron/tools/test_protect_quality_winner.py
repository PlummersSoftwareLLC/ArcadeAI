"""CPU-only provenance/publication checks; no live services, GPU, or model changes."""
import contextlib
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from . import protect_quality_winner as protect
from . import test_run_quality_campaign as fixtures


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CampaignTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.directory = self.fixture.config.directory
        self.directory.mkdir()
        protect.campaign.snapshot_checkpoints(self.fixture.plan)
        self.fixture.fill()
        self.plan = self.fixture.plan
        self.records = [dict(index=s["index"], role=s["role"], state="finished", returncode=0)
                        for s in self.plan["legs"]]
        self.destination = self.root / "protected"
        self.destination.mkdir()
        self.write_final()

    def write_final(self):
        plan_path = self.directory / "plan.json"
        plan_path.write_text(json.dumps(self.plan))
        plan_hash = protect.digest(plan_path)
        self.summary = protect.campaign.assess_campaign(self.plan, self.records)
        self.summary.update(plan_path=str(plan_path), plan_sha256=plan_hash, stop_signal=None)
        self.status = dict(state="finished", outcome=self.summary["outcome"], legs=self.records,
                           plan_path=str(plan_path), plan_sha256=plan_hash)
        self.flush()

    def flush(self):
        for name in ("status", "summary"):
            (self.directory / f"{name}.json").write_text(json.dumps(getattr(self, name)))

    def test_dry_review_is_read_only_and_keeps_every_original_tail(self):
        counts = [51, 59, 64, 56]
        for spec, count in zip(self.plan["legs"], counts):
            self.fixture.write_receipt(spec, 200 if spec["role"] == "reference" else 220, count=count)
        self.write_final()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = protect.review(self.directory)
        self.assertTrue(result["assessment"]["qualified_improvement"])
        self.assertEqual(result["assessment"]["pooled_reference"]["count"], 115)
        self.assertEqual([len(x["included_game_ids"]) for x in result["assessment"]["legs"]], counts)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(protect.main(["--campaign-dir", str(self.directory)]), 0)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_publishes_independent_readonly_copy_and_complete_lineage(self):
        result = protect.publish(self.directory, self.destination, "candidate-confirmed")
        final = Path(result["protected_checkpoint"])
        source = Path(self.plan["checkpoints"]["candidate"]["snapshot"])
        self.assertEqual(final.read_bytes(), source.read_bytes())
        self.assertNotEqual(final.stat().st_ino, source.stat().st_ino)
        metadata = final.with_suffix(".pt.json")
        self.assertEqual(json.loads(metadata.read_text()), result)
        self.assertFalse(result["managed_incumbent_updated"])
        self.assertFalse(result["live_learner_restored"])
        self.assertEqual(len(result["evidence_sha256"]), 7)
        self.assertEqual([x["role"] for x in result["assessment"]["legs"]], list(protect.campaign.ORDER))
        self.assertEqual(final.stat().st_mode & 0o222, 0)
        self.assertEqual(metadata.stat().st_mode & 0o222, 0)
        before = final.read_bytes(), metadata.read_bytes()
        with self.assertRaises(FileExistsError):
            protect.publish(self.directory, self.destination, "candidate-confirmed")
        self.assertEqual(before, (final.read_bytes(), metadata.read_bytes()))

    def test_rejects_pooled_rescue_even_with_winning_combined_candidate_mean(self):
        self.fixture.fill((100, 300, 300, 200))
        self.write_final()
        self.assertEqual(protect.review(self.directory)["assessment"]["outcome"], "not_improved")
        with self.assertRaisesRegex(ValueError, "independently"):
            protect.publish(self.directory, self.destination, "loser")
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_rejects_interruption_failed_missing_duplicate_or_still_running_records(self):
        original = copy.deepcopy(self.status)
        for mutation in (
            lambda s: s.update(state="running"),
            lambda s: s["legs"].pop(),
            lambda s: s["legs"][0].update(returncode=1),
            lambda s: s["legs"][0].update(state="running"),
            lambda s: s["legs"][1].update(index=1),
            lambda s: s["legs"][1].update(role="reference"),
        ):
            with self.subTest(mutation=mutation):
                self.status = copy.deepcopy(original)
                mutation(self.status)
                self.flush()
                with self.assertRaises(ValueError):
                    protect.review(self.directory)
        self.status = original
        self.summary["stop_signal"] = 15
        self.flush()
        with self.assertRaisesRegex(ValueError, "interruption"):
            protect.review(self.directory)

    def test_saved_summary_cannot_override_original_rows_or_hide_tail_changes(self):
        self.summary["candidate_checks"][0]["mean_ratio"] = 42
        self.flush()
        with self.assertRaisesRegex(ValueError, "independently recomputed"):
            protect.review(self.directory)
        self.write_final()
        path = Path(self.plan["legs"][1]["receipt_path"])
        data = json.loads(path.read_text())
        data["cohort"]["pending"] = 1
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            protect.review(self.directory)

    def test_rejects_changed_plan_and_weakened_gate_even_with_updated_hashes(self):
        self.status["plan_sha256"] = "0" * 64
        self.flush()
        with self.assertRaisesRegex(ValueError, "hash"):
            protect.review(self.directory)
        self.plan["precommit"]["candidate_gate"]["minimum_mean_ratio"] = 1.0
        self.write_final()
        with self.assertRaisesRegex(ValueError, "criteria"):
            protect.review(self.directory)

    def test_actual_plan_roles_cannot_silently_turn_every_leg_into_a_reference(self):
        # Declared precommit and final status still claim R/C/R/C. The original
        # assessment could otherwise vacuously qualify all([]) candidate checks.
        for spec in self.plan["legs"]:
            spec["role"] = "reference"
            spec["job"]["checkpoint"] = self.plan["checkpoints"]["reference"]["snapshot"]
            spec["job"]["label"] = "reference-extra-" + str(spec["index"])
            directory = self.directory / f"{spec['index']:02d}-reference"
            spec["job"]["directory"] = str(directory)
            spec["receipt_path"] = str(directory / "receipt.json")
            self.fixture.write_receipt(spec, 200)
        self.write_final()
        self.assertEqual(self.summary["candidate_checks"], [])
        self.assertTrue(self.summary["qualified_improvement"])
        with self.assertRaisesRegex(ValueError, "Planned legs"):
            protect.review(self.directory)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_duplicate_plan_indices_and_mismatched_checkpoint_roles_rejected(self):
        original = copy.deepcopy(self.plan)
        for mutate in (
            lambda p: p["legs"][1].update(index=1),
            lambda p: p["legs"][1]["job"].update(checkpoint=p["checkpoints"]["reference"]["snapshot"]),
            lambda p: p["checkpoints"]["candidate"].update(snapshot=p["checkpoints"]["reference"]["snapshot"]),
        ):
            with self.subTest(mutation=mutate):
                self.plan.clear();self.plan.update(copy.deepcopy(original))
                mutate(self.plan)
                self.write_final()
                with self.assertRaises(ValueError):
                    protect.review(self.directory)

    def test_defensive_rejection_of_empty_candidate_assessment(self):
        empty = dict(self.summary, candidate_checks=[], qualified_improvement=True, outcome="qualified_improvement")
        with patch.object(protect.campaign, "assess_campaign", return_value=empty):
            with self.assertRaisesRegex(ValueError, "two independent candidate"):
                protect.review(self.directory)

    def test_rejects_checkpoint_tampering_and_path_traversal_labels(self):
        for label in ("../escape", "", "/absolute", "a/b"):
            with self.assertRaisesRegex(ValueError, "filename"):
                protect.publish(self.directory, self.destination, label)
        candidate = Path(self.plan["checkpoints"]["candidate"]["snapshot"])
        candidate.chmod(0o644)
        candidate.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            protect.review(self.directory)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_changed_evidence_during_copy_blocks_publication_and_cleans_partials(self):
        original = protect.review(self.directory)
        changed = copy.deepcopy(original)
        changed["evidence_sha256"]["new"] = "changed"
        with patch.object(protect, "review", side_effect=[original, changed]):
            with self.assertRaisesRegex(ValueError, "changed while copying"):
                protect.publish(self.directory, self.destination, "candidate")
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_metadata_publication_failure_retains_unpromoted_checkpoint_without_partials(self):
        actual_link = protect.os.link
        calls = []
        def fail_second(source, destination):
            calls.append(str(destination))
            if len(calls) == 2:
                raise OSError("simulated metadata failure")
            actual_link(source, destination)
        with patch.object(protect.os, "link", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "metadata failure"):
                protect.publish(self.directory, self.destination, "candidate")
        self.assertEqual([p.name for p in self.destination.iterdir()], ["candidate.pt"])
        self.assertEqual(protect.digest(self.destination / "candidate.pt"),
                         self.plan["checkpoints"]["candidate"]["sha256"])


if __name__ == "__main__":
    unittest.main()
