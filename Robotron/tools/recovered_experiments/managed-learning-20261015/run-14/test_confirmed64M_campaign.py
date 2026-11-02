"""Prepare-only pure/temp tests: no pending leg, real build or protection read."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).with_name("build_confirmed64M_campaign.py")
spec = importlib.util.spec_from_file_location("prepared64_campaign", SOURCE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def report():
    gate = dict(reference_count=236, reference_mean=121245.33898305085, reference_median=124125.0,
        each_candidate={label: dict(count=100, mean=150000.0, median=150000.0,
            mean_at_least5pct=True, median_at_least_reference=True) for label in builder.LABELS},
        confirmation_gate_passed=True, every_supplied_leg_passes=True, two_separate_candidate_legs_present=True)
    sources = [dict(label=label, path="/isolated/" + label, sha256=(builder.PINNED_SCREEN_SHA
        if label == builder.LABELS[0] else hashlib.sha256(label.encode()).hexdigest()))
        for label in builder.REFERENCE_LABELS + builder.LABELS]
    pool = dict(candidate=dict(count=200, mean=150000.0, median=150000.0, se=100.0),
                reference=dict(count=236, mean=121245.33898305085, median=124125.0), mean_ratio=1.23716)
    return dict(schema="robotron-64M-composite-reference-analysis-v1", utc="fixture",
        stage="screen_and_confirmation", policy_identity=dict(candidate_sha256=builder.EXPECTED_SHA,
            candidate_saved_clocks=builder.EXPECTED_CLOCKS), management_gate=gate, sources=sources,
        pooled_candidate_vs_composite_reference=pool, each_candidate_vs_composite_reference={},
        separate_official_pair_comparisons={}, unique_ids={}, composite_reference=pool["reference"],
        common_private_backend=dict(job={}), limitations=["Fixture only"], receipt_byte_snapshots=sources)


def receipts():
    return {label: dict(engine_version=28, state_size=11128, single_frame_state_size=2782, frame_stack=4,
        wire_params_count=8, wire_version=2, frame_protocol="robotron-v2",
        compile_report=dict(graph_state=dict(unique_graphs=2)), count=100, started=100, pending=0,
        abandoned=0, start_ts=10, close_ts=610, ended_unix_s=680, clocks=builder.EXPECTED_CLOCKS,
        mean=150000.0, numeric_policy=dict(weights="float32"), runtime=dict(torch="fixture"),
        source_hashes=dict(fake="fixture"), boot_assets=dict(identity="fixture", files={}),
        socket_wait=dict(sha256="fixture")) for label in builder.REFERENCE_LABELS + builder.LABELS}


class PreparationTests(unittest.TestCase):
    def test_each_leg_gate_not_rescued_by_pool_or_single_screen(self):
        good = report()
        self.assertTrue(builder.require_confirmed_gate(good)["confirmation_gate_passed"])
        for change in ("mean", "median", "missing", "policy", "clocks"):
            bad = copy.deepcopy(good)
            if change == "mean":
                bad["management_gate"]["each_candidate"][builder.LABELS[0]]["mean"] = 127307.0
            elif change == "median":
                bad["management_gate"]["each_candidate"][builder.LABELS[0]]["median"] = 124124.0
            elif change == "missing":
                bad["stage"] = "screen"
            elif change == "policy":
                bad["policy_identity"]["candidate_sha256"] = "0" * 64
            else:
                bad["policy_identity"]["candidate_saved_clocks"] = dict(builder.EXPECTED_CLOCKS, training_steps=1)
            with self.subTest(change=change), self.assertRaises(ValueError):
                builder.require_confirmed_gate(bad)
        edge = copy.deepcopy(good)
        for leg in edge["management_gate"]["each_candidate"].values():
            leg.update(mean=127307.6059322034, median=124125.0)
        builder.require_confirmed_gate(edge)

    def fixture_build(self, *, provided=None, fresh=None, protocol_change=False, protect=False):
        provided = report() if provided is None else provided
        fresh = copy.deepcopy(provided) if fresh is None else fresh
        raw = receipts()
        if protocol_change:
            raw[builder.LABELS[1]]["wire_version"] = 3
        log = []
        comp = SimpleNamespace(build=Mock(side_effect=lambda *args: log.append("strict validation") or fresh),
            recheck_receipt_evidence=Mock(side_effect=lambda *args: log.append("receipt recheck")))
        pub = SimpleNamespace(protect_checkpoint=Mock(side_effect=lambda *args: log.append("protect") or dict(path="temp-only")))
        prior = dict(protected=[{}] * 7, historical_campaigns=[dict(path="old-campaign", sha256="a" * 64)])
        def read(path, digest):
            if str(path) == "comparison":
                return provided
            return raw[Path(path).name]
        with patch.object(builder, "verify_prior_artifacts", side_effect=lambda: log.append("prior bytes") or prior), \
             patch.object(builder, "pinned_module", side_effect=[comp, pub]), \
             patch.object(builder, "pinned_json", side_effect=read), \
             patch.object(builder, "isolation_evidence", return_value={}), \
             patch.object(builder, "checkpoint_metadata", return_value=builder.EXPECTED_CLOCKS), \
             patch.object(builder, "verify_hash"):
            try:
                value = builder.build_campaign("comparison", "0" * 64, protect=protect)
            except ValueError as error:
                value = error
        return value, comp, pub, log

    def test_fresh_report_mismatch_and_wire_mismatch_precede_any_protection(self):
        provided, fresh = report(), report()
        fresh["composite_reference"]["mean"] = 1
        for kwargs in (dict(provided=provided, fresh=fresh), dict(protocol_change=True)):
            value, _, pub, _ = self.fixture_build(protect=True, **kwargs)
            self.assertIsInstance(value, ValueError)
            pub.protect_checkpoint.assert_not_called()

    def test_missing_confirmation_stops_before_strict_build_or_copy(self):
        partial = report()
        partial["stage"] = "screen"
        value, comp, pub, _ = self.fixture_build(provided=partial, protect=True)
        self.assertIsInstance(value, ValueError)
        comp.build.assert_not_called()
        pub.protect_checkpoint.assert_not_called()

    def test_new_campaign_sources_do_not_duplicate_historical_references(self):
        result, comp, pub, log = self.fixture_build()
        self.assertIsInstance(result, dict)
        self.assertEqual([x["label"] for x in result["sources"]], list(builder.LABELS))
        self.assertEqual([x["label"] for x in result["reference_sources"]], list(builder.REFERENCE_LABELS))
        self.assertNotIn("valid", result)
        self.assertFalse(result["managed_state_changed"])
        self.assertEqual(len(result["policy_identity"]["retained_previous_incumbents"]), 7)
        comp.build.assert_called_once_with(list(builder.LABELS), builder.ITERATIONS)
        pub.protect_checkpoint.assert_not_called()
        self.assertLess(log.index("strict validation"), log.index("receipt recheck"))

    def test_explicit_protection_is_after_all_gates_and_rechecks(self):
        result, _, pub, log = self.fixture_build(protect=True)
        self.assertIsInstance(result, dict)
        pub.protect_checkpoint.assert_called_once()
        self.assertLess(log.index("strict validation"), log.index("protect"))
        self.assertLess(log.index("receipt recheck"), log.index("protect"))
        self.assertEqual(log[-2:], ["prior bytes", "receipt recheck"])

    def test_seven_prior_pairs_and_campaigns_fail_closed_on_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = []
            for n in range(7):
                pair = {}
                for kind in ("checkpoint", "metadata"):
                    path = root / (str(n) + kind)
                    path.write_bytes((str(n) + kind).encode())
                    pair[kind] = dict(path=str(path), sha256=builder.digest(path),
                        mode=oct(path.stat().st_mode & 0o777), size_bytes=path.stat().st_size)
                records.append(pair)
            history = root / "historical.json"
            history.write_text("{}")
            pins = dict(protected=records, historical_campaigns=[dict(path=str(history), sha256=builder.digest(history))])
            with patch.object(builder, "pinned_json", return_value=pins):
                builder.verify_prior_artifacts()
                Path(records[3]["metadata"]["path"]).write_text("changed")
                with self.assertRaisesRegex(ValueError, "Identity changed"):
                    builder.verify_prior_artifacts()
            self.assertEqual(history.read_text(), "{}")

    def test_pinned_publisher_makes_independent_readonly_copy_without_overwrite(self):
        publisher = builder.pinned_module(builder.CAMPAIGN / "run-08/build_confirmed32M_campaign.py",
            builder.PUBLISH_HELPER_SHA, "fixture64_publisher")
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory) / "source", Path(directory) / "new64.pt"
            source.write_bytes(b"synthetic checkpoint, never a real model")
            original = source.read_bytes(), source.stat().st_mode
            metadata = dict(sha256=builder.digest(source), utc="fixture", identity="all-gates-already-required")
            publisher.protect_checkpoint(source, destination, metadata)
            self.assertNotEqual(source.stat().st_ino, destination.stat().st_ino)
            self.assertEqual(destination.stat().st_nlink, 1)
            self.assertFalse(destination.stat().st_mode & 0o222)
            self.assertFalse(destination.with_suffix(".pt.json").stat().st_mode & 0o222)
            with self.assertRaisesRegex(ValueError, "metadata differs"):
                publisher.protect_checkpoint(source, destination, dict(metadata, identity="bad"))
            self.assertEqual((source.read_bytes(), source.stat().st_mode), original)

    def test_changed_source_cannot_publish_copy_or_metadata(self):
        publisher = builder.pinned_module(builder.CAMPAIGN / "run-08/build_confirmed32M_campaign.py",
            builder.PUBLISH_HELPER_SHA, "fixture64_publisher_fault")
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory) / "source", Path(directory) / "new64.pt"
            source.write_bytes(b"old")
            metadata = dict(sha256=builder.digest(source))
            original = publisher.publish_file
            def changed(path, writer, **kwargs):
                def mutate(stream):
                    source.write_bytes(b"new")
                    return writer(stream)
                return original(path, mutate, **kwargs)
            with patch.object(publisher, "publish_file", side_effect=changed):
                with self.assertRaisesRegex(ValueError, "Copied checkpoint identity differs"):
                    publisher.protect_checkpoint(source, destination, metadata)
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_suffix(".pt.json").exists())

    def test_help_and_invalid_output_never_read_pending_receipt_or_build(self):
        with patch.object(builder, "build_campaign", side_effect=AssertionError("No real build")):
            with self.assertRaises(SystemExit) as caught:
                builder.main(["--help"])
            self.assertEqual(caught.exception.code, 0)
            with self.assertRaises(SystemExit) as caught:
                builder.main(["--comparison", "absent", "--comparison-sha256", "0" * 64, "--protect"])
            self.assertEqual(caught.exception.code, 2)
            with self.assertRaises(SystemExit) as caught:
                builder.main(["--comparison", "absent", "--comparison-sha256", "0" * 64,
                    "--output", "/tmp/incorrect64-output"])
            self.assertEqual(caught.exception.code, 2)

    def test_report_or_isolation_mutation_rejected_before_campaign_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comparison, audit, output = (root / name for name in ("comparison", "audit", "campaign"))
            for changed in (comparison, audit):
                comparison.write_bytes(b"final report")
                audit.write_bytes(b"positive final audit")
                sha = builder.digest(comparison)
                result = dict(receipt_byte_snapshots=[],
                    comparison_report=dict(path=str(comparison), sha256=sha),
                    main_training_isolation_provenance={"confirm": dict(path=str(audit), sha256=builder.digest(audit))})
                comp = SimpleNamespace(recheck_receipt_evidence=Mock(side_effect=lambda *args: changed.write_bytes(b"changed")))
                pub = SimpleNamespace(publish_json=Mock())
                with patch.object(builder, "PUBLICATION", output), \
                     patch.object(builder, "build_campaign", return_value=result), \
                     patch.object(builder, "verify_prior_artifacts"), \
                     patch.object(builder, "pinned_module", side_effect=[comp, pub]):
                    with self.assertRaises(SystemExit) as caught:
                        builder.main(["--comparison", str(comparison), "--comparison-sha256", sha, "--output", str(output)])
                self.assertEqual(caught.exception.code, 2)
                pub.publish_json.assert_not_called()
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
