"""Fixture-only checks; no real future checkpoint/receipt is opened or created."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[2]
sys.path.insert(0, str(GAME))
from tools.compare_sidecar_measurements import compare_sidecars, validate_backend, JOB_FIELDS
from tools.compare_frozen_measurements import validate_receipt
from tools.sidecar_boot import _identity, load_snapshot, REQUIRED_PATHS
from tools.test_compare_sidecar_measurements import sidecar


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = imported("guard96_under_test", HERE / "analyze96M_guard.py")
math_helper = imported("guard96_math_test", HERE.parent / "run-14/compare64M_composite.py")


def saved_meta(*, updates=607219, samples=1267425280, learner=68634783):
    return dict(engine_version=28, state_size=11128, single_frame_state_size=2782,
        frame_stack=4, baseline_batch_size=512, training_steps=updates,
        optimized_samples=samples, total_training_steps=updates,
        learner_frame_count=learner, frame_count=learner * 2,
        measurement_frame_count=100, last_target_update_samples=samples - 2048)


class Fixture:
    """Private fake bytes + real official validators and boot loader."""
    def __init__(self, directory):
        self.root = Path(directory)
        self.game = self.root / "Robotron"
        self.campaign = self.game / "logs/campaign"
        self.run = self.campaign / "run-19"
        self.run.mkdir(parents=True)
        self.reference_meta = saved_meta()
        self.candidate_meta = saved_meta(updates=800000, samples=2000000000, learner=100629100)
        self.reference_file = self.game / "models_dqn/managed-checkpoints/fresh3-64M.pt"
        self.candidate_file = self.game / "models_dqn/managed-checkpoints/fresh3-96M.pt"
        self.write(self.reference_file, b"reference checkpoint fixture")
        self.write(self.candidate_file, b"future checkpoint fixture")
        self.source_hashes = {}
        for index in range(12):
            relative = f"sources/frozen-{index}.py"
            self.source_hashes[relative] = self.write(self.game / relative, f"fixture{index}".encode())
        self.wire = self.game / "wire-fixture.so"
        self.wire_sha = self.write(self.wire, b"synthetic wire bytes")
        self.boot = self.game / "boot"
        self.make_boot()
        self.ref_labels = ["reference-screen", "reference-confirm"]
        self.labels = ["sidecar-gpu0-96M-regression-guard-01",
                       "sidecar-gpu0-96M-regression-guard-confirm-01"]
        self.ref_rows = []
        self.ref_sources = []
        for count, label in zip((108, 109), self.ref_labels):
            row = self.receipt(label, self.reference_meta, self.reference_file, count=count)
            self.ref_rows.extend(row["rows"])
            path = self.campaign / label / "receipt.json"
            self.ref_sources.append(dict(label=label, path=str(path), sha256=self.write_json(path, row)))
        # An older published leg is outside current backend but still validated
        # and included in the global game-ID denominator.
        historic = sidecar("older-history")
        old_receipt = self.campaign / "older-history/receipt.json"
        old_source = dict(label=historic["label"], path=str(old_receipt), sha256=self.write_json(old_receipt, historic))
        old_campaign = self.campaign / "old-campaign.json"
        old_sha = self.write_json(old_campaign, dict(sources=[old_source]))
        campaign = self.campaign / "confirmed64-campaign.json"
        campaign_sha = self.write_json(campaign, dict(sources=self.ref_sources,
            historical_segment=dict(path=str(old_campaign), sha256=old_sha)))
        protected = self.game / "models_dqn/managed-incumbents/fresh3-64M-confirmed.pt"
        protected_sha = self.write(protected, self.reference_file.read_bytes())
        metadata = Path(str(protected) + ".json")
        metadata_sha = self.write_json(metadata, dict(fixture=True))
        baseline = guard.summarize(self.ref_rows)
        self.plan = dict(candidate=dict(labels=self.labels), reference=dict(campaign=str(campaign),
            campaign_sha256=campaign_sha, sources=self.ref_sources, count=217,
            mean=baseline["mean"], median=baseline["median"], saved_clocks=self.reference_meta,
            checkpoint=dict(path=str(protected), sha256=protected_sha, metadata_path=str(metadata),
                            metadata_sha256=metadata_sha)),
            precommitted_decisions=dict(mean_alarm_below=.9 * baseline["mean"],
                median_alarm_below=.9 * baseline["median"], severe_mean_below=.8 * baseline["mean"]),
            reporting=["Fixture repeated-look caveat"])
        self.plan_sha = self.write_json(self.run / "quality96M-regression-guard-plan.json", self.plan)
        self.old_lineage_sha = self.write_json(self.campaign / "run-14/fresh3-64M-checkpoint-lineage.json",
            dict(candidate=dict(sha256=protected_sha, saved_metadata=self.reference_meta,
                optimizer=dict(state_count=81, all_tensors_CPU=True, step_values=[606960.0]))))
        self.resume_sha = self.write_json(self.run / "final-resume-checkpoint.json", dict(cpu_only=True,
            cuda_initialized=False, saved_metadata=saved_meta(updates=724620, samples=1520455680, learner=84949637)))
        gate_path = self.run / "future-gate.json"
        gate = dict(tag="fresh3-96M", target=100629023, checkpoint=str(self.candidate_file))
        gate_sha = self.write_json(gate_path, gate)
        self.lineage = dict(schema="robotron-96M-checkpoint-lineage-v1", PASS=True,
            checks=dict(CPU_only=True, architecture_matches64M=True, saved_learner_gate_passed=True),
            candidate=dict(path=str(self.candidate_file), sha256=guard.digest(self.candidate_file),
                saved_metadata=self.candidate_meta, stat=guard.file_stat(self.candidate_file),
                optimizer=dict(state_count=81, all_tensors_CPU=True, step_values=[799741.0])),
            trigger_gate=dict(path=str(gate_path), sha256=gate_sha, record=gate))
        self.lineage_path = self.run / "future-lineage.json"
        self.lineage_sha = self.write_json(self.lineage_path, self.lineage)
        for label in self.labels:
            self.write_json(self.campaign / label / "receipt.json",
                self.receipt(label, self.candidate_meta, self.candidate_file, count=64))
        self.analysis_iterations = []

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def write_json(self, path, value):
        return self.write(path, (json.dumps(value, sort_keys=True) + "\n").encode())

    def make_boot(self):
        values = (bytes(1024), b'<mameconfig version="10"><system name="robotron"/></mameconfig>', b"fixture=1\n")
        files = {}
        for relative, raw in zip(REQUIRED_PATHS, values):
            files[relative] = dict(bytes=len(raw), sha256=self.write(self.boot / relative, raw))
        manifest = dict(schema="robotron-sidecar-boot-v1", created_utc="fixture", files=files,
            source_files={relative: {} for relative in REQUIRED_PATHS}, writer_checks={})
        manifest["identity"] = _identity(manifest)
        self.write_json(self.boot / "manifest.json", manifest)
        for current, _, names in os.walk(self.boot, topdown=False):
            for name in names:
                (Path(current) / name).chmod(0o444)
            Path(current).chmod(0o555)
        self.boot_manifest = load_snapshot(self.boot)

    def receipt(self, label, metadata, source, *, count=64):
        value = sidecar(label)
        rows = []
        for index in range(count):
            row = copy.deepcopy(value["rows"][index % 50])
            row.update(journal_game_id=f"{label}:{index}", client_slot=guard.SLOTS[index % 16],
                start_unix_s=100 + index, end_unix_s=120 + index, duration_s=20,
                score=1000 + index * 100, boundary_reason="wire_lives_exhausted")
            for context in (row["start_context"], row["end_context"]):
                context.update(training_steps=metadata["training_steps"], optimized_samples=metadata["optimized_samples"],
                    learner_frames=metadata["learner_frame_count"])
            rows.append(row)
        # Keep one legitimate tail after admission closes, never truncate it.
        rows[-1].update(end_unix_s=725, duration_s=725 - rows[-1]["start_unix_s"])
        value.update(rows=rows, count=count, started=count, close_ts=700, phase="finished", reason=None,
            receipt_validator="passed", ended_unix_s=730, checkpoint_metadata=copy.deepcopy(metadata),
            source_checkpoint_path=str(source), checkpoint_sha256=guard.digest(source),
            source_hashes=dict(self.source_hashes), ended_source_hashes=dict(self.source_hashes))
        value["checkpoint_metadata"]["defaulted_metadata_fields"] = []
        value["job"].update(checkpoint=str(source), cohort_s=600, timeout_s=1200, boot_assets=str(self.boot))
        value["clocks"] = {key: metadata[key] for key in guard.CORE_CLOCKS}
        value["clocks"].update(total_training_steps=metadata["training_steps"], total_optimized_samples=metadata["optimized_samples"])
        value["boundary"].update(clients=16, expected=16, acknowledged=16, requested_generation=1)
        copy_path = self.campaign / label / "checkpoint.pt"
        self.write(copy_path, source.read_bytes())
        value["checkpoint_path"] = str(copy_path)
        value["boot_assets"] = copy.deepcopy(self.boot_manifest)
        value["boot_restores"] = {str(slot): copy.deepcopy(self.boot_manifest) for slot in guard.SLOTS}
        value["socket_wait"].update(library=str(self.wire), sha256=self.wire_sha)
        for actor in value["socket_wait"]["actors"].values():
            actor["activation_count"] = 1
        value.update(guard.summarize(rows))
        return value

    def analysis(self, reference, candidate, ref_labels, cand_labels, iterations):
        self.analysis_iterations.append(iterations)
        # Exercise the exact pinned math with bounded fixture draws. Production
        # always passes10000 and has no runtime option to reduce that number.
        return math_helper.analyze_rows(reference, candidate, ref_labels, cand_labels, 10)

    def context(self):
        return patch.multiple(guard, RUN=self.run, CAMPAIGN=self.campaign, GAME=self.game,
            PLAN_SHA=self.plan_sha, REFERENCE_LINEAGE_SHA=self.old_lineage_sha, RESUME_SHA=self.resume_sha,
            dependencies=lambda evidence: SimpleNamespace(validate_backend=validate_backend,
                validate_receipt=validate_receipt, compare_sidecars=compare_sidecars,
                load_snapshot=load_snapshot, analyze_rows=self.analysis, JOB_FIELDS=JOB_FIELDS))

    def cleanup_permissions(self):
        for current, _, _ in os.walk(self.boot):
            Path(current).chmod(0o700)


class Guard96Tests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        value = Fixture(temporary.name)
        self.addCleanup(temporary.cleanup)
        self.addCleanup(value.cleanup_permissions)
        return value

    def test_import_and_help_do_not_open_any_evidence_or_import_torch(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("data opened at import")):
            imported("guard96_inert_import", HERE / "analyze96M_guard.py")
        code = ("import runpy,sys;sys.argv=['guard','--help'];"
            f"runpy.run_path({str(HERE / 'analyze96M_guard.py')!r},run_name='__main__')")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=5,
            env=dict(os.environ, CUDA_VISIBLE_DEVICES=""))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--lineage-sha256", result.stdout)
        self.assertNotIn("torch", guard.__dict__)

    def test_thresholds_strict_low_N_severe_and_same_criterion_confirmation(self):
        rows = lambda score, count=64: [dict(score=score) for _ in range(count)]
        self.assertFalse(guard.decisions(rows(100), {"first": rows(90)})["confirmation_still_needed"])
        self.assertTrue(guard.decisions(rows(100), {"first": rows(100, 63)})["confirmation_still_needed"])
        alarm = guard.decisions(rows(100), {"first": rows(79), "confirm": rows(89)})
        self.assertTrue(alarm["severe_first_leg_alert"])
        self.assertTrue(alarm["repeated_same_criterion_alarm"])
        mixed = guard.decisions(rows(100), {"first": rows(89), "confirm": rows(120)})
        self.assertEqual(mixed["status"], "mixed_alarm_inconclusive")
        self.assertFalse(mixed["repeated_same_criterion_alarm"])
        self.assertFalse(mixed["promotion"])
        mean_only = rows(100, 33) + rows(0, 31)
        median_only = rows(80, 33) + rows(120, 31)
        crossed = guard.decisions(rows(100), {"first": mean_only, "confirm": median_only})
        self.assertFalse(crossed["repeated_same_criterion_alarm"])
        self.assertEqual(crossed["status"], "mixed_alarm_inconclusive")

    def test_full_two_leg_build_binds_original_tails_ids_exposure_and_fixed_draw_count(self):
        value = self.fixture()
        with value.context():
            report, evidence = guard.build(value.labels, value.lineage_path, value.lineage_sha)
        self.assertEqual(report["management"]["reference"]["count"], 217)
        self.assertEqual(report["global_ids"], dict(receipts=5, games=217 + 50 + 128, overlaps=0))
        self.assertEqual(len(report["official_pair_validation"]), 6)
        self.assertEqual(value.analysis_iterations, [10000, 10000, 10000])
        self.assertEqual(len(report["pooled_candidate_vs_composite"]["actor_contrasts"]), 16)
        self.assertTrue(report["no_fabricated_measurement_receipt"])
        self.assertTrue(all(row["completed_tails_after_admission"] == 1 for row in report["full_leg_denominators"]))
        self.assertFalse(report["protection"])
        self.assertIsNone(report["clocks_separate"][0]["main_training_driver_clocks"])
        self.assertGreater(report["optimizer_exposure"]["minimum_parameter_step_delta"], 0)
        output = value.run / "new-only-report.json"
        guard.publish(report, evidence, output)
        with self.assertRaises(FileExistsError):
            guard.publish(report, evidence, output)

    def test_bad_lineage_hash_path_gate_metadata_and_adam_are_rejected(self):
        value = self.fixture()
        with value.context(), self.assertRaisesRegex(ValueError, "pinned JSON"):
            guard.build(value.labels[:1], value.lineage_path, "0" * 64)
        cases = [lambda row: row.update(PASS=False),
                 lambda row: row["checks"].update(CPU_only=False),
                 lambda row: row["candidate"].update(path="/wrong/checkpoint.pt"),
                 lambda row: row["candidate"]["saved_metadata"].update(learner_frame_count=100629022),
                 lambda row: row["candidate"]["optimizer"].update(state_count=80),
                 lambda row: row["trigger_gate"]["record"].update(target=1)]
        for mutate in cases:
            row = copy.deepcopy(value.lineage)
            mutate(row)
            with self.subTest(change=cases.index(mutate)), self.assertRaises(ValueError):
                guard.lineage_identity(row, value.candidate_file, value.reference_meta)

    def test_pending_errors_source_numeric_and_whole_tail_fail_closed(self):
        value = self.fixture()
        path = value.campaign / value.labels[0] / "receipt.json"
        original = json.loads(path.read_bytes())
        cases = [lambda row: row.update(pending=1),
                 lambda row: row["actor_timeout_logs"].update({"4096": 1}),
                 lambda row: row["source_hashes"].update({"sources/frozen-0.py": "0" * 64}),
                 lambda row: row["numeric_policy"].update(suppress_errors=True),
                 lambda row: row["rows"][-1].update(boundary_reason="life_lost")]
        for index, mutate in enumerate(cases):
            row = copy.deepcopy(original)
            mutate(row)
            value.write_json(path, row)
            with self.subTest(case=index), value.context(), self.assertRaises(ValueError):
                guard.build(value.labels[:1], value.lineage_path, value.lineage_sha)

    def test_historical_id_overlap_is_rejected_not_dropped(self):
        value = self.fixture()
        path = value.campaign / value.labels[0] / "receipt.json"
        row = json.loads(path.read_bytes())
        row["rows"][0]["journal_game_id"] = "older-history:0"
        value.write_json(path, row)
        with value.context(), self.assertRaisesRegex(ValueError, "global game ID overlap"):
            guard.build(value.labels[:1], value.lineage_path, value.lineage_sha)

    def test_candidate_runtime_drift_rejects_even_individually_valid_leg(self):
        value = self.fixture()
        path = value.campaign / value.labels[0] / "receipt.json"
        row = json.loads(path.read_bytes())
        row["runtime"]["gpu_name"] = "different GPU"
        validate_backend(row, verify_checkpoint=True)
        value.write_json(path, row)
        with value.context(), self.assertRaisesRegex(ValueError, "backend differs: runtime"):
            guard.build(value.labels[:1], value.lineage_path, value.lineage_sha)

    def test_two_candidates_must_match_exact_saved_identity_and_clocks(self):
        value = self.fixture()
        path = value.campaign / value.labels[1] / "receipt.json"
        row = json.loads(path.read_bytes())
        row["checkpoint_metadata"]["training_steps"] += 1
        value.write_json(path, row)
        with value.context(), self.assertRaisesRegex(ValueError, "actor metadata differs"):
            guard.build(value.labels, value.lineage_path, value.lineage_sha)

    def test_changed_receipt_boot_modes_or_candidate_stat_prevents_publication(self):
        value = self.fixture()
        with value.context():
            report, evidence = guard.build(value.labels[:1], value.lineage_path, value.lineage_sha)
        path = value.campaign / value.labels[0] / "receipt.json"
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        output = value.run / "must-not-publish.json"
        with self.assertRaisesRegex(ValueError, "changed before publication"):
            guard.publish(report, evidence, output)
        self.assertFalse(output.exists())
        path.write_bytes(original)
        value.boot.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "immutable"):
            guard.publish(report, evidence, output)
        value.boot.chmod(0o555)
        os.utime(value.candidate_file, ns=(1, 2))
        with self.assertRaisesRegex(ValueError, "stat changed"):
            guard.publish(report, evidence, output)
        self.assertFalse(output.exists())

    def test_json_snapshot_rejects_duplicate_nan_and_symlink(self):
        value = self.fixture()
        path = value.run / "untrusted.json"
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                guard.Evidence().json(path)
        path.unlink()
        path.symlink_to(value.lineage_path)
        with self.assertRaises(ValueError):
            guard.Evidence().json(path)

    def test_actual_deferred_dependencies_are_pinned_stdlib_validators(self):
        evidence = guard.Evidence()
        before = set(sys.modules)
        tools = guard.dependencies(evidence)
        self.assertEqual(tools.JOB_FIELDS, JOB_FIELDS)
        self.assertEqual(len(evidence.snapshot()), 4)
        self.assertFalse(any(name == "torch" or name.startswith("torch.") for name in set(sys.modules) - before))
        evidence.recheck()


if __name__ == "__main__":
    unittest.main()
