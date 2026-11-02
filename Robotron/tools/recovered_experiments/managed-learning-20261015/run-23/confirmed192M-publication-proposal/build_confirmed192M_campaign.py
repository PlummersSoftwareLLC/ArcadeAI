#!/usr/bin/env python3
"""Prospective ROOT-only confirmed192M protection/publication; default plan only.

--publish requires explicit hashes of the FINAL two-leg analysis, FINAL root
CPU lineage, actual checkpoint and both final isolation audits. No future data
is opened on import/help/default use. No state, control, source, figure, fleet,
model training or GPU actions exist here. Publication never overwrites files.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile


HERE = Path(__file__).resolve().parent
CAMPAIGN, GAME = HERE.parents[1], HERE.parents[3]
PLAN = CAMPAIGN / "run-23/quality192M-preparation/quality192M-assessment-plan.json"
PLAN_SHA = "13fecf794902fc9d20c690be6b8bad39d4c0256bf6d3f153fc309ec8003e06aa"
ANALYZER = PLAN.with_name("analyze192M_assessment.py")
ANALYZER_SHA = "6a8dda64851bafdf765bc78140663e29488b0ba4e39c2e3a889a0ce3a1d51363"
ROOT_VERIFIER_SHA = "68249876eba5e850d65e692c46fa62d80b172302f5fcfab44a072d217c15dabe"
ROOT_PRECOMMIT_SHA = "2c86925956ec2aa1616998c27e06e08ee3d5f8ddbf0f69a009da7c6a5d8e14e2"
PRIOR_PINS = HERE / "prior-byte-pins.json"
PRIOR_PINS_SHA = "57ffdae12774bf274682970a7b4cc2d31f9053c837e3823a9b60d9b14c557876"
LABELS = ("sidecar-gpu0-192M-screen-01", "sidecar-gpu0-192M-confirm-01")
REFERENCE_LABELS = ("sidecar-gpu0-128M-screen-01", "sidecar-gpu0-128M-confirm-01")
GUARD_LABELS = ("sidecar-gpu0-96M-regression-guard-01", "sidecar-gpu0-160M-regression-guard-01", "sidecar-gpu0-160M-regression-guard-02")
SOURCE = GAME / "models_dqn/managed-checkpoints/fresh3-192M.pt"
DESTINATION = GAME / "models_dqn/managed-incumbents/fresh3-192M-confirmed.pt"
PUBLICATION = CAMPAIGN / "sidecar-fresh3-192M-confirmed-campaign.json"
REFERENCE_MEAN, MEDIAN_FLOOR = 206615.54054054053, 166112.5
MEAN_FLOOR = 1.05 * REFERENCE_MEAN


def require(value, message):
    if not value:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def sha_string(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def regular(path):
    path = Path(path).absolute()
    require(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode), "Need nonsymlink regular file: " + str(path))
    return path


def pinned_json(path, expected):
    require(sha_string(expected), "Need an explicit64-hex SHA")
    path = regular(path)
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, "Changed pinned JSON: " + str(path))
    value = json.loads(raw, object_pairs_hook=unique_object,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    require(isinstance(value, dict), "Expected JSON object")
    return value


def load_analyzer():
    path = regular(ANALYZER)
    require(digest(path) == ANALYZER_SHA, "Pinned strict192M analyzer changed")
    spec = importlib.util.spec_from_file_location("confirmed192_strict_analyzer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_prior(evidence):
    """Reuse prior model attestations; statguard payloads, byte-check small files.

    This is not a new cryptographic verification of old model payloads. No old
    mode/inode/content is written; before/after checks bind this publication.
    """
    pins = evidence.json(PRIOR_PINS, PRIOR_PINS_SHA)
    require(len(pins["protected"]) == 9 and len(pins["historical_campaigns"]) == 5,
            "Require all nine previous protected pairs and five campaigns")
    inherited = evidence.json(pins["inherited_prior_manifest"]["path"], pins["inherited_prior_manifest"]["sha256"])
    root = evidence.json(pins["root128_publication_attestation"]["path"], pins["root128_publication_attestation"]["sha256"])
    require(root.get("PASS") is True and len(inherited["protected"]) == 8,
            "Missing actual prior publication attestation")
    for index, item in enumerate(pins["protected"]):
        for kind in ("checkpoint", "metadata"):
            row = item[kind]
            if index < 8:
                old = inherited["protected"][index][kind]
                require(all(row[k] == old[k] for k in ("path", "sha256", "size_bytes", "mode", "inode", "device")),
                        "Inherited old artifact attestation differs")
            else:
                key = "sha256" if kind == "checkpoint" else "metadata_sha256"
                require(row["sha256"] == root["new_incumbent"][key], "Protected128M attestation differs")
            path = regular(row["path"]) if kind == "checkpoint" else evidence.file(row["path"], row["sha256"])
            info = path.stat()
            actual = dict(size_bytes=info.st_size, mode=oct(stat.S_IMODE(info.st_mode)),
                inode=info.st_ino, device=info.st_dev, mtime_ns=info.st_mtime_ns,
                ctime_ns=info.st_ctime_ns, nlink=info.st_nlink)
            require(all(actual[k] == row[k] for k in actual), "Previous protected artifact statguard changed")
            if kind == "checkpoint":
                evidence.bind_stat(path, dict(size=info.st_size, mtime_ns=info.st_mtime_ns,
                    inode=info.st_ino, device=info.st_dev))
    for row in pins["historical_campaigns"]:
        path = evidence.file(row["path"], row["sha256"])
        info = path.stat()
        require(info.st_size == row["size_bytes"] and oct(stat.S_IMODE(info.st_mode)) == row["mode"],
                "Previous campaign mode/size changed")
    return pins


def confirmed_gate(report, checkpoint_sha, lineage_path, lineage_sha):
    require(report.get("schema") == "robotron-192M-two-leg-assessment-v1"
            and report.get("fixed_bootstrap_iterations") == 10000
            and report.get("all_source_receipts_separately_validated") is True
            and report.get("no_fabricated_measurement_receipt") is True,
            "Need strict final192M analysis")
    require(report["lineage"] == dict(path=str(Path(lineage_path).resolve()), sha256=lineage_sha),
            "Analysis uses another root lineage")
    identity = report["policy_identity"]["candidate"]
    require(Path(identity["path"]).resolve() == SOURCE.resolve() and identity["sha256"] == checkpoint_sha,
            "Wrong192M checkpoint")
    management = report["management"]
    require(management["status"] == "two_legs_pass_root_promotion_review"
            and management["promotion_eligible"] is True and management["promotion"] is False
            and management["reference_rebased"] is False
            and management["third_valid_cohort_authorized"] is False
            and management["two_fixed_valid_legs_required"] is True
            and management["second_leg_required_regardless_first_quality"] is True
            and management["maximum_valid_legs_reached"] is True
            and management["confirmation_still_needed"] is False,
            "Both separate passing192M legs are required")
    reference = management["reference"]
    require(reference["count"] == 148 and reference["mean"] == REFERENCE_MEAN
            and reference["median"] == MEDIAN_FLOOR
            and management["thresholds"] == dict(mean=.9*REFERENCE_MEAN, median=.9*MEDIAN_FLOOR, severe_mean=.8*REFERENCE_MEAN, gain_mean=MEAN_FLOOR, gain_median=MEDIAN_FLOOR),
            "Original protected128M reference/gate changed")
    legs = management["each_leg"]
    require(len(legs) == 2 and [row["label"] for row in legs] == list(LABELS), "Missing/reordered candidate legs")
    for row in legs:
        require(type(row["count"]) is int and row["count"] > 0
                and math.isfinite(row["mean"]) and math.isfinite(row["median"])
                and row["mean"] >= MEAN_FLOOR and row["median"] >= MEDIAN_FLOOR
                and row["mean_gate"] is True and row["median_gate"] is True
                and row["passes_both_promotion_gates"] is True, "A separate192M leg fails the fixed gate")
    ids = report["global_ids"]
    require(ids["receipts"] == 26 and ids["overlaps"] == 0
            and ids["games"] == 2500 + sum(row["count"] for row in legs), "Historical/global denominator changed")
    require(report["promotion"] is False and report["protection"] is False
            and report["state_or_control_changes"] is False, "Analyzer must not perform deployment")
    return management


def same_analysis(provided, fresh):
    # Only analyzer wall-clock creation time is nondeterministic. All source,
    # row, denominator, bootstrap, backend and management fields must match.
    return {k: v for k, v in provided.items() if k != "utc"} == {k: v for k, v in fresh.items() if k != "utc"}


def audit_identity(audit, source, checkpoint_sha):
    require(audit.get("pass") is True and audit.get("checks")
            and all(value is True for value in audit["checks"].values())
            and audit.get("receipt_sha256") == source["sha256"]
            and audit.get("checkpoint_sha256") == checkpoint_sha,
            "Need positive SHA-bound final isolation audit: " + source["label"])
    checks = audit["checks"]
    require(checks.get("private_owned_processes_listener_released") is True
            and checks.get("private_GPU0_context_released") is True
            and checks.get("loaded_sources_unchanged") is True,
            "Final private cleanup/source proof missing")


def new_destinations():
    for path in (DESTINATION, DESTINATION.with_suffix(".pt.json"), PUBLICATION):
        require(path.parent.is_dir() and not path.exists() and not path.is_symlink(),
                "Refuse any existing/partial confirmed192M publication: " + str(path))


def publish_file(path, writer, before_link):
    """Retained reviewed128M publication protocol: new readonly inode, fsync, exclusive link."""
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            writer(stream)
            stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        before_link()
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def publish_json(path, value, before_link):
    raw = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    publish_file(path, lambda stream: stream.write(raw), before_link)


def protect_checkpoint(source, destination, metadata, recheck):
    """Never aliases or changes source; validates copied SHA before publication."""
    original = source.stat()
    def copy_checked(stream):
        value = hashlib.sha256()
        with source.open("rb") as reader:
            for block in iter(lambda: reader.read(4 * 1024 * 1024), b""):
                stream.write(block); value.update(block)
        require(value.hexdigest() == metadata["sha256"], "Copied checkpoint SHA differs")
        latest = source.stat()
        require((original.st_dev, original.st_ino, original.st_size, original.st_mtime_ns, original.st_ctime_ns)
                == (latest.st_dev, latest.st_ino, latest.st_size, latest.st_mtime_ns, latest.st_ctime_ns),
                "Source changed during protection copy")
    publish_file(destination, copy_checked, recheck)
    require(digest(destination) == metadata["sha256"], "Published copy SHA differs")
    publish_json(destination.with_suffix(".pt.json"), metadata, recheck)
    expected_metadata = (json.dumps(metadata, indent=2, allow_nan=False) + "\n").encode()
    require(digest(destination.with_suffix(".pt.json")) == hashlib.sha256(expected_metadata).hexdigest(),
            "Published protection metadata bytes differ")
    for path in (destination, destination.with_suffix(".pt.json")):
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o222 and info.st_nlink == 1,
                "Protection must be independent readonly regular files")
    require((source.stat().st_dev, source.stat().st_ino) != (destination.stat().st_dev, destination.stat().st_ino),
            "Protected copy aliases source inode")
    return dict(path=str(destination), sha256=digest(destination), metadata_path=str(destination.with_suffix(".pt.json")),
                metadata_sha256=digest(destination.with_suffix(".pt.json")), size_bytes=destination.stat().st_size,
                nlink=1, writable=False, independent_source_inode=True)


def publish_campaign(args):
    require(args.publish is True and os.environ.get("CUDA_VISIBLE_DEVICES") == "", "Explicit publish with hidden CUDA required")
    for key in ("analysis_sha256", "lineage_sha256", "checkpoint_sha256", "screen_audit_sha256", "confirm_audit_sha256"):
        require(sha_string(getattr(args, key, None)), "Explicit actual SHA required: " + key)
    new_destinations()
    plan = pinned_json(PLAN, PLAN_SHA)
    require(plan["candidate"]["labels"] == list(LABELS) and Path(plan["candidate"]["checkpoint"]) == SOURCE,
            "Prepared labels/checkpoint changed")
    analyzer = load_analyzer()
    initial = analyzer.Evidence()
    initial.file(__file__, digest(__file__)); initial.file(ANALYZER, ANALYZER_SHA)
    initial.json(PLAN, PLAN_SHA)
    completed_history = analyzer.history_manifest(plan, initial)
    provided = initial.json(args.analysis, args.analysis_sha256)
    confirmed_gate(provided, args.checkpoint_sha256, args.lineage, args.lineage_sha256)
    lineage = initial.json(args.lineage, args.lineage_sha256)
    analyzer.lineage_identity(lineage, SOURCE, plan["reference"]["saved_clocks"])
    require(lineage["root_verification"]["verifier_sha256"] == ROOT_VERIFIER_SHA
            and lineage["root_verification"]["precommit_sha256"] == ROOT_PRECOMMIT_SHA,
            "Use the independently reviewed root CPU verifier contract")
    require(lineage["candidate"]["sha256"] == args.checkpoint_sha256, "Root lineage checkpoint SHA differs")
    prior = verify_prior(initial)
    fresh, evidence = analyzer.build(list(LABELS), args.lineage, args.lineage_sha256)
    confirmed_gate(fresh, args.checkpoint_sha256, args.lineage, args.lineage_sha256)
    require(same_analysis(provided, fresh), "Supplied final analysis differs from fresh deterministic validation")
    sources = {row["label"]: row for row in fresh["sources"]}
    require(len(sources) == len(fresh["sources"]) == 26 and all(label in sources for label in (*LABELS, *REFERENCE_LABELS, *GUARD_LABELS)),
            "Need all historical and current real receipts")
    audits = {}
    for label, path, expected in ((LABELS[0], args.screen_audit, args.screen_audit_sha256),
                                  (LABELS[1], args.confirm_audit, args.confirm_audit_sha256)):
        audit = initial.json(path, expected)
        audit_identity(audit, sources[label], args.checkpoint_sha256)
        audits[label] = dict(path=str(Path(path).resolve()), sha256=expected)
    require(not any(name == "torch" or name.startswith("torch.") for name in sys.modules),
            "Publication must remain a fresh CPU-only process without Torch imports")
    def recheck():
        initial.recheck(); evidence.recheck(); verify_prior(initial)
    # Every gate and final CPU/backend/full-tail/global-ID validation occurs
    # before any new copied model, metadata or campaign is made visible.
    recheck(); new_destinations()
    pooled = fresh["pooled_candidate_vs_composite"]
    now = utc()
    candidate_sources = [sources[label] for label in LABELS]
    reference_sources = [sources[label] for label in REFERENCE_LABELS]
    metadata = dict(schema="managed-confirmed-incumbent-v4", utc=now,
        checkpoint=str(DESTINATION.relative_to(GAME)), origin=str(SOURCE.relative_to(GAME)),
        sha256=args.checkpoint_sha256, receipts=candidate_sources, reference_receipts=reference_sources,
        saved_checkpoint_metadata=lineage["candidate"]["saved_metadata"],
        saved_policy_clocks=fresh["policy_identity"]["candidate"]["metadata"],
        optimizer_exposure=lineage["candidate"]["optimizer"],
        compiler_and_instrumentation_chronology=lineage["branch_provenance"]["compiler_and_instrumentation_chronology"],
        counter_exposure_evidence=lineage["counter_exposure_evidence"],
        branch_provenance=lineage["branch_provenance"],
        actual_recorded_batch_exposure=lineage["actual_recorded_batch_exposure"],
        full_leg_validation=fresh["full_leg_denominators"],
        combined_n=pooled["candidate"]["count"], combined_mean=pooled["candidate"]["mean"],
        combined_median=pooled["candidate"]["median"], combined_se=pooled["candidate"]["se"],
        selected_ratio=pooled["mean_ratio"], selected_ratio_reference="Original148 rows from two separately valid protected128M legs",
        gain_gate=fresh["management"], backend=fresh["matched_frozen_backend"],
        analysis=dict(path=str(Path(args.analysis).resolve()), sha256=args.analysis_sha256),
        lineage=dict(path=str(Path(args.lineage).resolve()), sha256=args.lineage_sha256),
        main_training_isolation_provenance=audits,
        retained_prior_artifact_scope=prior.get("scope", "Inherited SHA attestations plus current statguards; small files byte-checked."),
        limitations=fresh["caveats"], state_or_control_changed=False,
        scope="Root-requested readonly protection after two passing separately valid192M cohorts; no state promotion.")
    protected = protect_checkpoint(SOURCE, DESTINATION, metadata, recheck)
    # Bind the newly protected pair too, so its bytes are included in every
    # remaining prepublication/final recheck, rather than only recording hashes.
    initial.file(DESTINATION, protected["sha256"])
    initial.file(DESTINATION.with_suffix(".pt.json"), protected["metadata_sha256"])
    recheck()
    campaign = dict(schema="frozen-policy-campaign-analysis-v5", stage="confirmed", created_utc=now,
        segment="GPU0 compiledFP32 fixed-transport3s private16actor cohorts", sources=candidate_sources,
        reference_sources=reference_sources,
        historical_segment=dict(path=plan["reference"]["campaign"], sha256=plan["reference"]["campaign_sha256"],
            use="Prior confirmed128M campaign; original148 reference/history rows stay separate.96M/both160M guards are unpromoted global history only."),
        additional_history=copy.deepcopy(completed_history["additional_history"]),
        completed_history_manifest=dict(path=plan["history"]["manifest_path"], sha256=plan["history"]["manifest_sha256"]),
        analysis_code=dict(path=str(Path(__file__).resolve()), sha256=digest(__file__)),
        pinned_helpers=dict(analyzer=ANALYZER_SHA, root_verifier=ROOT_VERIFIER_SHA, prior_byte_pins=PRIOR_PINS_SHA),
        comparison_report=metadata["analysis"], lineage=metadata["lineage"],
        validation=dict(each_receipt_separately_validated=True, no_fabricated_merged_receipt=True,
            full_started_denominators_completed=True, pending_abandoned_zero=True,
            global_ids=fresh["global_ids"], official_pair_validation=fresh["official_pair_validation"]),
        gain_gate=fresh["management"], each_candidate_vs_composite=fresh["each_candidate_vs_composite"],
        confirmed192M_vs_composite128M=pooled,
        descriptive_pools=dict(composite128M=pooled["reference"], confirmed192M=pooled["candidate"]),
        common_runtime=fresh["matched_frozen_backend"], main_training_isolation_provenance=audits,
        clocks_separate=fresh["clocks_separate"],
        policy_identity=dict(source_checkpoint=str(SOURCE), sha256=args.checkpoint_sha256,
            saved_policy_clocks=metadata["saved_checkpoint_metadata"], protected_copy=protected,
            retained_previous_incumbents=prior["protected"]),
        limitations=fresh["caveats"] + ["Protection is not managed-state promotion; only root may make that separate decision."],
        managed_state_changed=False, promotion=False, cuda_initialized=False,
        prior_byte_pins=dict(path=str(PRIOR_PINS), sha256=PRIOR_PINS_SHA,
            scope=prior.get("scope", "Inherited model attestations/statguards; metadata/campaign byte checks.")))
    publish_json(PUBLICATION, campaign, recheck)
    recheck()
    return campaign


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    for name in ("analysis", "lineage", "screen-audit", "confirm-audit"):
        parser.add_argument("--" + name, type=Path)
        parser.add_argument("--" + name + "-sha256")
    parser.add_argument("--checkpoint-sha256")
    args = parser.parse_args()
    if not args.publish:
        print(json.dumps(dict(mode="plan_only_no_future_reads", labels=LABELS, source=str(SOURCE),
            protected_destination=str(DESTINATION), campaign=str(PUBLICATION),
            mean_floor_each_leg=MEAN_FLOOR, median_floor_each_leg=MEDIAN_FLOOR), indent=2))
        return
    if any(getattr(args, name) is None for name in ("analysis", "lineage", "screen_audit", "confirm_audit")):
        parser.error("--publish requires final analysis, root lineage and both final isolation audits")
    try:
        campaign = publish_campaign(args)
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.exit(2, "192M publication rejected; no managed-state action: " + str(error) + "\n")
    print(json.dumps(dict(published=str(PUBLICATION), sha256=digest(PUBLICATION),
        protected=campaign["policy_identity"]["protected_copy"], managed_state_changed=False)))


if __name__ == "__main__":
    main()
