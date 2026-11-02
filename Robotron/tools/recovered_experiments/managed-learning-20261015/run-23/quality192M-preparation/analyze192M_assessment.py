#!/usr/bin/env python3
"""Assess the two prespecified FINAL192M cohorts; never launch, protect or promote.

Import and --help open no candidate/lineage/receipt files. Execution requires
the SHA of a root-verified future192M lineage report. Only an exclusive new JSON
report is written; checkpoints, receipts, gates, controls and state are read-only.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import stat
import statistics
import sys

RUN = Path(__file__).resolve().parent
CAMPAIGN = RUN.parents[1]
GAME = CAMPAIGN.parents[1]
PLAN_SHA = "13fecf794902fc9d20c690be6b8bad39d4c0256bf6d3f153fc309ec8003e06aa"
COMPOSITE_SHA = "2dc2f768361944b4e087022c248a21fa24c266da536cd2d653d035aa83874746"
VALIDATORS = {
    "compare_sidecar_measurements.py": "879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746",
    "compare_frozen_measurements.py": "53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0",
    "sidecar_boot.py": "f06492e6d96cd472d9f0073b4c643e820bcacb6a96c5f542a59d6b6874e62362",
}
REFERENCE_LINEAGE_SHA = "4535f56d71a1fe3c3b6c3f148ae7ab9cc6f9846d6eaa3b420ede0e82bc6eda18"
EXPERIMENT = "best10M-fresh3-eps10-cap8-nosmooth"
TARGET = 196629023
SLOTS = list(range(4096, 4112))
ITERATIONS = 10000
CORE_CLOCKS = ("training_steps", "optimized_samples", "learner_frame_count")
META_KEYS = (*CORE_CLOCKS, "engine_version", "state_size", "single_frame_state_size",
             "frame_stack", "frame_count", "measurement_frame_count",
             "total_training_steps", "last_target_update_samples")


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def sha_string(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def file_stat(path):
    value = Path(path).stat()
    return dict(size=value.st_size, mtime_ns=value.st_mtime_ns,
                inode=value.st_ino, device=value.st_dev)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


class Evidence:
    """One parsed+hashed byte snapshot per JSON; all evidence rechecked at publish."""
    def __init__(self):
        self.files = {}
        self.documents = {}
        self.stats = {}
        self.boots = {}

    def _path(self, path):
        path = Path(path).absolute()
        require(not path.is_symlink() and stat.S_ISREG(path.stat().st_mode),
                f"Evidence must be a regular nonsymlink file: {path}")
        return path

    def json(self, path, expected=None):
        path = self._path(path)
        if path not in self.documents:
            raw = path.read_bytes()
            value = hashlib.sha256(raw).hexdigest()
            self.files[str(path)] = value
            self.documents[path] = json.loads(raw, object_pairs_hook=unique_object,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            require(isinstance(self.documents[path], dict), f"Expected a JSON object: {path}")
        value = self.files[str(path)]
        require(expected is None or value == expected, f"Changed pinned JSON evidence: {path}")
        return self.documents[path]

    def file(self, path, expected):
        require(sha_string(expected), "Invalid expected evidence SHA")
        path = self._path(path)
        if str(path) not in self.files:
            self.files[str(path)] = digest(path)
        require(self.files[str(path)] == expected, f"Changed pinned file: {path}")
        return path

    def bind_stat(self, path, expected):
        path = self._path(path)
        value = {key: expected[key] for key in ("size", "mtime_ns", "inode", "device")}
        require(file_stat(path) == value, f"Lineage checkpoint stat changed: {path}")
        self.stats[str(path)] = value

    def boot(self, directory, manifest, loader):
        directory = Path(directory).absolute()
        self.file(directory / "manifest.json", manifest["manifest_sha256"])
        for relative, value in manifest["files"].items():
            self.file(directory / relative, value["sha256"])
        self.boots[str(directory)] = (manifest["identity"], loader)

    def recheck(self):
        for path, expected in self.files.items():
            self._path(path)
            require(digest(path) == expected,
                    f"Evidence changed before publication: {path}")
        for path, expected in self.stats.items():
            require(file_stat(path) == expected, f"Lineage checkpoint stat changed: {path}")
        for directory, (identity, loader) in self.boots.items():
            require(loader(Path(directory))["identity"] == identity, "Boot seed changed before publication")

    def snapshot(self):
        return [dict(path=path, sha256=value) for path, value in sorted(self.files.items())]


def dependencies(evidence):
    """Deferred imports: no future data access on import/help."""
    for name, expected in VALIDATORS.items():
        evidence.file(GAME / "tools" / name, expected)
    path = CAMPAIGN / "run-14/compare64M_composite.py"
    evidence.file(path, COMPOSITE_SHA)
    sys.path.insert(0, str(GAME / "tools"))
    spec = importlib.util.spec_from_file_location("guard128_composite_math", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def summarize(rows):
    require(len(rows) >= 2, "Insufficient original full-game rows")
    scores = [row["score"] for row in rows]
    return dict(count=len(scores), mean=statistics.mean(scores), median=statistics.median(scores),
                sd=statistics.stdev(scores), se=statistics.stdev(scores) / math.sqrt(len(scores)))


def decisions(reference, candidates):
    """Two fixed valid legs, unchanged per-leg gates; no automatic plateau rule."""
    base = summarize(reference)
    thresholds = dict(mean=0.9 * base["mean"], median=0.9 * base["median"],
                      severe_mean=0.8 * base["mean"], gain_mean=1.05 * base["mean"],
                      gain_median=base["median"])
    legs = []
    for label, rows in candidates.items():
        row = summarize(rows)
        row.update(label=label, mean_alarm=row["mean"] < thresholds["mean"],
                   median_alarm=row["median"] < thresholds["median"], low_N=row["count"] < 64,
                   mean_gate=row["mean"] >= thresholds["gain_mean"],
                   median_gate=row["median"] >= thresholds["gain_median"])
        row["passes_both_promotion_gates"] = row["mean_gate"] and row["median_gate"]
        row["severe_alert"] = row["mean"] < thresholds["severe_mean"] and row["median_alarm"]
        legs.append(row)
    require(1 <= len(legs) <= 2, "Require one or two fixed assessment legs")
    complete = len(legs) == 2
    eligible = complete and all(row["passes_both_promotion_gates"] for row in legs)
    mean_confirmed = complete and all(row["mean_alarm"] for row in legs)
    median_confirmed = complete and all(row["median_alarm"] for row in legs)
    if not complete:
        status = "second_fixed_leg_required_regardless_first_quality"
    elif eligible:
        status = "two_legs_pass_root_promotion_review"
    elif mean_confirmed or median_confirmed:
        status = "repeated_same_criterion_alarm_root_review"
    else:
        status = "two_fixed_legs_complete_root_assesses_evidence_no_automatic_plateau"
    return dict(status=status, reference=base, thresholds=thresholds, each_leg=legs,
        two_fixed_valid_legs_required=True, second_leg_required_regardless_first_quality=True,
        confirmation_still_needed=not complete, promotion_eligible=eligible,
        repeated_mean_alarm=mean_confirmed, repeated_median_alarm=median_confirmed,
        repeated_same_criterion_alarm=mean_confirmed or median_confirmed,
        low_N_leg_labels=[row["label"] for row in legs if row["low_N"]],
        severe_leg_labels=[row["label"] for row in legs if row["severe_alert"]],
        maximum_valid_legs_reached=complete, third_valid_cohort_authorized=False,
        plateau_declared=False, learning_knob_change_authorized=False,
        promotion=False, reference_rebased=False, automatic_action=False,
        rule="BOTH original legs independently need mean>=1.05x128M and median>=128M; no pooled rescue. SAME criterion below90% in BOTH legs is confirmed regression. Severe means<80% AND median<90%. Failed promotion alone is not plateau or futility; root records its interpretation before any one-knob proposal.")


def assigned_labels(labels, plan, authorizations, evidence, checkpoint_sha):
    """Root-only one corrected operational replacement per assigned leg.

    No outcome selection, automatic replacement or valid third leg. Originals
    remain pinned invalid evidence; authorization must predate replacement start.
    """
    require(1 <= len(labels) <= 2 and len(set(labels)) == len(labels),
            "Use first fixed leg or both fixed legs in assigned order")
    require(len(authorizations) <= 2, "At most one operational authorization per assigned leg")
    by_leg = {}
    for path, expected in authorizations:
        require(sha_string(expected), "Explicit root operational authorization SHA required")
        value = evidence.json(path, expected)
        index = value.get("assigned_leg")
        require(type(index) is int and index in (1, 2) and index not in by_leg,
                "One root authorization per assigned leg")
        require(value.get("schema") == "root-corrected-operational-replacement-v1"
            and value.get("root_authorized") is True
            and value.get("outcome_or_count_based_selection") is False
            and value.get("recorded_before_launch") is True
            and value.get("checkpoint_sha256") == checkpoint_sha,
            "Operational replacement requires exact root authorization/checkpoint")
        require(value.get("cause") in ("runtime", "backend", "boundary", "model_integrity", "main_training_safety")
            and isinstance(value.get("corrective_action"), str) and value["corrective_action"].strip()
            and isinstance(value.get("rationale"), str) and value["rationale"].strip(),
            "Root must record corrected operational cause and rationale")
        primary = plan["candidate"]["labels"][index - 1]
        replacement = plan["candidate"]["replacement_labels"][index - 1]
        require(value.get("original_label") == primary and value.get("replacement_label") == replacement,
                "Wrong assigned operational replacement labels")
        original = value["invalid_original"]
        invalid = evidence.json(original["path"], original["sha256"])
        require(invalid.get("label") == primary and invalid.get("valid") is False
            and invalid.get("phase") == "finished", "Preserve a FINAL invalid original receipt")
        stamp = value.get("recorded_unix_s")
        require(isinstance(stamp, (int, float)) and not isinstance(stamp, bool)
            and math.isfinite(stamp) and stamp > 0, "Root authorization timestamp required")
        by_leg[index] = dict(path=str(Path(path).absolute()), sha256=expected, record=value)
    selected = []
    for index, label in enumerate(labels, 1):
        if label == plan["candidate"]["labels"][index - 1]:
            require(index not in by_leg, "Unused operational authorization cannot select an original")
        else:
            require(index in by_leg and label == plan["candidate"]["replacement_labels"][index - 1],
                    "Replacement label requires its root operational authorization")
        selected.append(dict(assigned_leg=index, selected_label=label,
            operational_replacement=by_leg.get(index)))
    require(set(by_leg).issubset(range(1, len(labels) + 1)), "Authorization for an unselected leg")
    return selected


def history_manifest(plan, evidence):
    row = plan["history"]
    require(row.get("complete") is True, "Completed160 history required before any192 data access")
    value = evidence.json(row["manifest_path"], row["manifest_sha256"])
    require(value.get("schema") == "robotron-192M-completed-history-manifest-v1"
        and value.get("complete") is True and len(value.get("completed160_sources", [])) == 2,
        "Both completed160 guards/cleanup must be pinned before any192 data access")
    require(value["base_campaign"] == plan["reference"]["campaign"]
        and value["base_campaign_sha256"] == plan["reference"]["campaign_sha256"], "Wrong history reference")
    report = evidence.json(value["final160_analysis"]["path"], value["final160_analysis"]["sha256"])
    require(report.get("schema") == "robotron-160M-regression-analysis-v1"
        and report.get("promotion") is False and report["management"].get("reference_rebased") is False
        and report["management"].get("maximum_valid_legs_reached") is True
        and report["global_ids"] == dict(receipts=row["expected_receipts"], games=row["expected_unique_games"], overlaps=0)
        and report["sources"] == value["all_original_receipt_sources"], "Completed160 history registry differs")
    for source in value["completed160_sources"]:
        require(any(all(candidate.get(key) == source[key] for key in ("label", "path", "sha256"))
            for candidate in report["sources"]), "160 source absent from final registry")
        audit = evidence.json(source["isolation_audit_path"], source["isolation_audit_sha256"])
        require(audit.get("pass") is True and audit.get("checks")
            and all(flag is True for flag in audit["checks"].values())
            and audit.get("receipt_sha256") == source["sha256"], "Missing positive completed160 audit")
        for key in ("private_owned_processes_listener_released", "private_GPU0_context_released", "loaded_sources_unchanged"):
            require(audit["checks"].get(key) is True, "Missing positive160 cleanup/source proof")
        source_lineage = evidence.json(source["lineage_path"], source["lineage_sha256"])
        require(audit.get("checkpoint_sha256") == source_lineage["candidate"]["sha256"], "160 cleanup checkpoint mismatch")
    return value


def lineage_identity(report, expected_path, reference_meta):
    require(report.get("proposal_only") is False
        and isinstance(report.get("root_verification"), dict)
        and report["root_verification"].get("status") == "PASS"
        and report["root_verification"].get("CUDA_initialized") is False,
        "Need FINAL root-verified lineage, never an automated proposal")
    require(report.get("schema") == "robotron-192M-checkpoint-lineage-v1"
        and report.get("PASS") is True and report.get("checks")
        and all(value is True for value in report["checks"].values()), "Root lineage report is not a strict PASS")
    require(report["checks"].get("CPU_only") is True, "Missing CPU lineage validation")
    candidate = report["candidate"]
    require(Path(candidate["path"]).resolve() == Path(expected_path).resolve()
        and sha_string(candidate.get("sha256")), "Wrong future192M checkpoint identity")
    meta = candidate["saved_metadata"]
    for key in META_KEYS:
        require(key in meta and isinstance(meta[key], int) and not isinstance(meta[key], bool)
                and meta[key] >= 0, f"Missing/invalid lineage metadata: {key}")
    for key in ("engine_version", "state_size", "single_frame_state_size", "frame_stack"):
        require(meta[key] == reference_meta[key], f"Architecture differs: {key}")
    require(meta["learner_frame_count"] >= 196629023 and all(meta[key] > reference_meta[key]
                for key in CORE_CLOCKS), "Future192M saved gate/clocks did not advance")
    require(meta["total_training_steps"] == meta["training_steps"], "Lineage total/logical step clocks differ")
    require(meta.get("baseline_batch_size", 512) == 512, "Unexpected saved schedule baseline batch")
    require(meta["measurement_frame_count"] >= reference_meta["measurement_frame_count"]
        and meta["frame_count"] >= meta["learner_frame_count"]
        and meta["last_target_update_samples"] <= meta["optimized_samples"], "Invalid saved lineage clocks")
    optimizer = candidate["optimizer"]
    values = optimizer.get("step_values")
    require(optimizer.get("state_count") == 81 and optimizer.get("all_tensors_CPU") is True
        and values and all(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0 for value in values), "Missing CPU Adam exposure evidence")
    trigger = report["trigger_gate"]["record"]
    require(trigger["tag"] == "fresh3-192M" and trigger["target"] == 196629023
        and trigger.get("experiment") == EXPERIMENT
        and Path(trigger["checkpoint"]).resolve() == Path(expected_path).resolve(), "Wrong queued192M gate evidence")
    require(meta.get("epsilon") == reference_meta["epsilon"] == .1
        and math.isclose(meta.get("expert_ratio", -1), reference_meta["expert_ratio"], abs_tol=1e-12)
        and math.isclose(meta["expert_ratio"], .1, abs_tol=1e-12), "Saved behavior recipe changed")
    require(all(meta.get(key) == reference_meta[key] for key in ("lr_gear", "lr_anchor_step")),
            "Saved LR lineage changed")
    branch = report.get("branch_provenance", {})
    require(branch.get("experiment") == EXPERIMENT and branch.get("unchanged4096_after128M") is True
        and branch.get("compile_mode") == "default" and branch.get("exposure_counters_enabled") is True,
        "Changed branch/compiler/exposure recipe requires a separately reviewed contract")
    updates = meta["training_steps"] - reference_meta["training_steps"]
    samples = meta["optimized_samples"] - reference_meta["optimized_samples"]
    learner = meta["learner_frame_count"] - reference_meta["learner_frame_count"]
    exposure = report.get("actual_recorded_batch_exposure", {}).get("since128M", {})
    require(samples == 4096 * updates and exposure.get("recorded_batch_size") == 4096
        and exposure.get("logical_updates_delta") == updates
        and exposure.get("optimized_samples_delta") == samples
        and exposure.get("learner_frames_delta") == learner,
        "Saved4096 clock exposure differs from unchanged128M branch")
    return dict(path=str(Path(expected_path).resolve()), sha256=candidate["sha256"],
                metadata=meta, optimizer=optimizer)


def validate_leg(receipt, label, identity, evidence, tools):
    leg = tools.validate_backend(receipt, verify_checkpoint=True)
    require(receipt["label"] == label and receipt["phase"] == "finished"
        and receipt["reason"] is None and receipt["receipt_validator"] == "passed", "Need explicit final validated leg")
    require(receipt["checkpoint_sha256"] == identity["sha256"], "Wrong frozen checkpoint SHA")
    for path in (receipt["source_checkpoint_path"], receipt["job"]["checkpoint"]):
        require(Path(path).resolve() == Path(identity["path"]).resolve(), "Wrong explicit frozen checkpoint path")
    evidence.file(identity["path"], identity["sha256"])
    evidence.file(receipt["checkpoint_path"], identity["sha256"])
    for key in META_KEYS:
        require(receipt["checkpoint_metadata"].get(key) == identity["metadata"][key], f"Saved actor metadata differs: {key}")
    require(receipt["checkpoint_metadata"].get("defaulted_metadata_fields") == [],
        "Guard checkpoint metadata must not be defaulted")
    for key in CORE_CLOCKS:
        normalized = "learner_frames" if key == "learner_frame_count" else key
        require(receipt["clocks"].get(key) == leg["clocks"][normalized] == identity["metadata"][key], f"Frozen clocks differ: {key}")
    job = receipt["job"]
    require(job["cohort_s"] == 600 and job["timeout_s"] == 1200 and job["port"] == 9999
        and job["wait_us"] == 1000 and job["inference_backend"] == "inductor", "Guard protocol differs")
    boundary = receipt["boundary"]
    require(boundary["clients"] == boundary["expected"] == boundary["acknowledged"] == 16
        and boundary["generation"] == boundary["requested_generation"] == receipt["generation"]
        and sorted(boundary["actor_slots"]) == leg["expected_actor_slots"] == SLOTS
        and sorted({row["client_slot"] for row in leg["rows"]}) == SLOTS, "Guard actor boundary differs")
    require(len(receipt["source_hashes"]) == 12, "Need all12 guarded source hashes")
    for relative, expected in receipt["source_hashes"].items():
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "Invalid guarded source path")
        evidence.file(GAME / relative, expected)
    boot = tools.load_snapshot(Path(job["boot_assets"]))
    require(boot["identity"] == receipt["boot_assets"]["identity"]
        and boot["files"] == receipt["boot_assets"]["files"], "Boot snapshot differs")
    # Bind the actual immutable boot manifest/files, not only their receipt copy.
    evidence.boot(job["boot_assets"], boot, tools.load_snapshot)
    evidence.file(receipt["socket_wait"]["library"], receipt["socket_wait"]["sha256"])
    require(all(value["activation_count"] == 1 for value in receipt["socket_wait"]["actors"].values()), "Wire shim activation differs")
    summary = summarize(leg["rows"])
    for key in ("mean", "median", "sd", "se"):
        require(math.isclose(summary[key], receipt[key], abs_tol=1e-8), f"Receipt summary differs: {key}")
    require(all(row["boundary_reason"] == "wire_lives_exhausted"
        and row["end_unix_s"] <= receipt["ended_unix_s"] for row in leg["rows"]), "Whole-game tails missing")
    return leg


def build(labels, lineage_path, lineage_sha, authorizations=()):
    evidence = Evidence()
    evidence.file(__file__, digest(__file__))
    plan = evidence.json(RUN / "quality192M-assessment-plan.json", PLAN_SHA)
    completed_history = history_manifest(plan, evidence)  # before any candidate/lineage read
    require(1 <= len(labels) <= 2, "Use one or two fixed192M assigned legs")
    require(sha_string(lineage_sha), "Pass root-verified lineage SHA explicitly")
    lineage = evidence.json(lineage_path, lineage_sha)
    reference = plan["reference"]
    expected_path = GAME / "models_dqn/managed-checkpoints/fresh3-192M.pt"
    identity = lineage_identity(lineage, expected_path, reference["saved_clocks"])
    assignments = assigned_labels(labels, plan, authorizations, evidence, identity["sha256"])
    evidence.bind_stat(identity["path"], lineage["candidate"]["stat"])
    gate = evidence.json(lineage["trigger_gate"]["path"], lineage["trigger_gate"]["sha256"])
    require(gate == lineage["trigger_gate"]["record"], "Lineage trigger record differs from pinned gate")
    evidence.file(identity["path"], identity["sha256"])
    evidence.bind_stat(identity["path"], lineage["candidate"]["stat"])
    tools = dependencies(evidence)
    campaign = evidence.json(reference["campaign"], reference["campaign_sha256"])
    protected = reference["checkpoint"]
    evidence.file(protected["path"], protected["sha256"])
    evidence.json(protected["metadata_path"], protected["metadata_sha256"])
    prior_lineage = evidence.json(CAMPAIGN / "run-23/fresh3-128M-checkpoint-lineage.json", REFERENCE_LINEAGE_SHA)
    require(prior_lineage["candidate"]["sha256"] == protected["sha256"]
        and prior_lineage["candidate"]["saved_metadata"] == reference["saved_clocks"], "128M exposure lineage differs")
    reference_optimizer = prior_lineage["candidate"]["optimizer"]
    require(min(identity["optimizer"]["step_values"]) >= max(reference_optimizer["step_values"]),
        "Candidate Adam exposure moved backwards")
    geometry = lambda groups: [{key: value for key, value in group.items() if key != "lr"} for group in groups]
    require(geometry(identity["optimizer"]["groups"]) == geometry(reference_optimizer["groups"]),
        "Candidate Adam group geometry differs from protected128M")
    ids, receipt_sources, campaigns = {}, [], set()
    def history(path, expected):
        key = str(Path(path).resolve())
        require(key not in campaigns, "Historical campaign cycle")
        campaigns.add(key)
        value = evidence.json(path, expected)
        for source in value["sources"]:
            row = evidence.json(source["path"], source["sha256"])
            leg = tools.validate_receipt(row)
            require(leg["label"] not in ids, "Duplicate historical receipt")
            ids[leg["label"]] = {game["journal_game_id"] for game in leg["rows"]}
            receipt_sources.append(dict(source))
        old = value.get("historical_segment", {})
        if old.get("path"):
            history(old["path"], old["sha256"])
    history(reference["campaign"], reference["campaign_sha256"])
    require(campaign["sources"] == reference["sources"], "Confirmed128M source identities differ")
    raw, legs = [], []
    ref_identity = dict(path=str(GAME / "models_dqn/managed-checkpoints/fresh3-128M.pt"),
                        sha256=protected["sha256"], metadata=reference["saved_clocks"])
    for source in reference["sources"]:
        row = evidence.json(source["path"], source["sha256"])
        raw.append(row); legs.append(validate_leg(row, source["label"], ref_identity, evidence, tools))
    additional_history = []
    for source in completed_history["additional_history"]:
        past = evidence.json(source["lineage_path"], source["lineage_sha256"])
        require(past.get("schema") in ("robotron-96M-checkpoint-lineage-v1", "robotron-160M-checkpoint-lineage-v1")
            and past.get("proposal_only") is False and past.get("PASS") is True
            and past.get("checks") and all(value is True for value in past["checks"].values())
            and past["root_verification"]["status"] == "PASS", "Historical guard root lineage differs")
        past_actor = past["candidate"]
        past_identity = dict(path=past_actor["path"], sha256=past_actor["sha256"], metadata=past_actor["saved_metadata"])
        past_report = evidence.json(source["analysis_path"], source["analysis_sha256"])
        require(past_report["promotion"] is False and past_report["management"]["reference_rebased"] is False,
            "96M/160M guards must remain unpromoted separate history")
        require(any(all(candidate.get(key) == source[key] for key in ("label", "path", "sha256"))
            for candidate in past_report["sources"]), "Guard receipt not bound by its final analysis")
        row = evidence.json(source["path"], source["sha256"])
        past_leg = validate_leg(row, source["label"], past_identity, evidence, tools)
        tools.compare_sidecars(raw[0], row, iterations=100, verify_checkpoint=False)
        require(source["label"] not in ids, "Duplicate additional historical label")
        ids[source["label"]] = {game["journal_game_id"] for game in past_leg["rows"]}
        receipt_sources.append(dict(label=source["label"], path=source["path"], sha256=source["sha256"]))
        additional_history.append(dict(label=source["label"], count=len(past_leg["rows"]), pooled_into_reference=False))
        require(all(identity["metadata"][key] > past_identity["metadata"][key] for key in CORE_CLOCKS)
            and min(identity["optimizer"]["step_values"]) >= max(past_actor["optimizer"]["step_values"]),
            "192M clocks/Adam exposure did not advance completed guard history")
    require(len(ids) == plan["history"]["expected_receipts"]
        and sum(map(len, ids.values())) == plan["history"]["expected_unique_games"],
        "Original historical receipt/game registry differs")
    require({(source["label"], source["path"], source["sha256"]) for source in receipt_sources}
        == {(source["label"], source["path"], source["sha256"]) for source in completed_history["all_original_receipt_sources"]},
        "Completed original historical byte registry differs")
    for assigned, label in zip(assignments, labels):
        path = CAMPAIGN / label / "receipt.json"
        row = evidence.json(path)
        raw.append(row); legs.append(validate_leg(row, label, identity, evidence, tools))
        if assigned["operational_replacement"]:
            runner_start = row.get("started_unix_s")
            require(isinstance(runner_start, (int, float)) and not isinstance(runner_start, bool)
                and math.isfinite(runner_start) and 0 < runner_start <= row["start_ts"],
                "Operational replacement needs a finite actual runner-start timestamp; admission start is insufficient")
            require(assigned["operational_replacement"]["record"]["recorded_unix_s"] <= runner_start,
                    "Root operational rationale must predate actual replacement runner startup")
        require(label not in ids, "Candidate label already in published history")
        ids[label] = {game["journal_game_id"] for game in legs[-1]["rows"]}
        receipt_sources.append(dict(label=label, path=str(path), sha256=evidence.files[str(path.absolute())]))
    pairs = {}
    for a, b in itertools.combinations(raw, 2):
        checked = tools.compare_sidecars(a, b, iterations=100, verify_checkpoint=False)
        pairs[a["label"] + " vs " + b["label"]] = dict(backend_validated=checked["backend_validated"],
            checkpoint_copies_verified_separately=True, checkpoint_sha256=checked["checkpoint_sha256"])
    seen = {}
    for label, values in ids.items():
        for identifier in values:
            require(identifier not in seen, f"Historical/global game ID overlap: {label} / {seen.get(identifier)}")
            seen[identifier] = label
    baseline = legs[0]["rows"] + legs[1]["rows"]
    stats = summarize(baseline)
    require(stats["count"] == reference["count"] == 148 and stats["mean"] == reference["mean"]
        and stats["median"] == reference["median"], "Original-row128M composite differs")
    candidates = {leg["label"]: leg["rows"] for leg in legs[2:]}
    decision = decisions(baseline, candidates)
    require(decision["thresholds"]["mean"] == plan["precommitted_decisions"]["mean_alarm_below"]
        and decision["thresholds"]["median"] == plan["precommitted_decisions"]["median_alarm_below"]
        and decision["thresholds"]["severe_mean"] == plan["precommitted_decisions"]["severe_mean_below"],
        "Precommitted regression thresholds differ")
    require(decision["thresholds"]["gain_mean"] == plan["precommitted_decisions"]["mean_at_least_each_leg"]
        and decision["thresholds"]["gain_median"] == plan["precommitted_decisions"]["median_at_least_each_leg"],
        "Precommitted promotion thresholds differ")
    comparisons = {label: tools.analyze_rows(baseline, rows, [leg["label"] for leg in legs[:2]],
        [label], ITERATIONS) for label, rows in candidates.items()}
    pooled = [game for rows in candidates.values() for game in rows]
    denominators = []
    for row, leg in zip(raw, legs):
        cohort = row.get("cohort", {})
        denominators.append(dict(label=row["label"],
            **{key: row.get(key, cohort.get(key)) for key in ("started", "count", "pending", "abandoned")},
            valid=row["valid"], complete=row["complete"], start_ts=leg["start_ts"], close_ts=leg["close_ts"],
            latest_tail_end_unix_s=max(game["end_unix_s"] for game in leg["rows"]),
            completed_tails_after_admission=sum(game["end_unix_s"] > leg["close_ts"] for game in leg["rows"])))
    result = dict(schema="robotron-192M-two-leg-assessment-v1", utc=datetime.now(timezone.utc).isoformat(),
        management=decision, fixed_bootstrap_iterations=ITERATIONS, sources=receipt_sources,
        assigned_legs=assignments, history_manifest=dict(path=plan["history"]["manifest_path"], sha256=plan["history"]["manifest_sha256"]),
        root_followup_learning_trial=plan["followup_learning_trial"],
        lineage=dict(path=str(Path(lineage_path).resolve()), sha256=lineage_sha),
        policy_identity=dict(reference=ref_identity, candidate=identity),
        optimizer_exposure=dict(reference128M=reference_optimizer, candidate192M=identity["optimizer"],
            minimum_parameter_step_delta=min(identity["optimizer"]["step_values"]) - max(reference_optimizer["step_values"]),
            note="Logical updates, optimized samples and Adam parameter steps are separate. The unchanged128M-to192M branch must satisfy4096 samples per logical update; this does not identify every parameter update or candidate-time AMP outcomes."),
        exposure_deltas={"since128M": {key: identity["metadata"][key] - reference["saved_clocks"][key]
            for key in CORE_CLOCKS}},
        actual_recorded_batch_exposure=lineage["actual_recorded_batch_exposure"],
        branch_provenance=lineage["branch_provenance"],
        process_counter_evidence=lineage.get("counter_exposure_evidence"),
        clocks_separate=[dict(label=row["label"], saved_checkpoint_actor=row["checkpoint_metadata"],
            private_measurement_metrics=row["clocks"], main_training_driver_clocks=None,
            note="Private receipt metrics are initialized from its saved actor checkpoint; concurrent main-driver clocks are not recorded in this receipt.") for row in raw],
        full_leg_denominators=denominators,
        matched_frozen_backend=dict(job={key: raw[0]["job"][key] for key in tools.JOB_FIELDS},
            numeric_policy=raw[0]["numeric_policy"], runtime=raw[0]["runtime"],
            source_hashes=raw[0]["source_hashes"], boot_identity=raw[0]["boot_assets"]["identity"],
            boot_files=raw[0]["boot_assets"]["files"], socket_wait_sha256=raw[0]["socket_wait"]["sha256"]),
        official_pair_validation=pairs, all_source_receipts_separately_validated=True,
        no_fabricated_measurement_receipt=True, each_candidate_vs_composite=comparisons,
        pooled_candidate_vs_composite=(comparisons[labels[0]] if len(labels) == 1 else tools.analyze_rows(
            baseline, pooled, [leg["label"] for leg in legs[:2]], labels, ITERATIONS)),
        global_ids=dict(receipts=len(ids), games=len(seen), overlaps=0), additional_history=additional_history, evidence=evidence.snapshot(),
        promotion=False, protection=False, state_or_control_changes=False,
        caveats=plan["reporting"][-1:] + ["Actor labels are paired clusters, not identical trajectories; repeated looks remain descriptive.",
            "96M and both160M guards remain unpromoted history and never enter the protected128M148-game reference pool; eligibility is not promotion.",
            "Official pair calls validate protocols using their minimum100 draws; those sensitivities are discarded. Only the fixed10000-draw composite sensitivities are reported.",
            "Two fixed valid192M legs are required regardless first outcome. Root alone may preserve/promote after both independently pass; no pool rescues a failed leg. Failed promotion alone is not plateau/futility; no automatic LR action or third valid cohort."])
    evidence.recheck()
    return result, evidence


def output_path(output):
    value = Path(output).absolute()
    require(value.parent == RUN.parent.absolute() and value.name.startswith("quality192M-")
        and value.name.endswith("-analysis.json") and not value.is_symlink(),
        "Only a NEW run23/quality192M-*-analysis.json report may be written")
    require(not value.exists(), "Refuse to overwrite assessment evidence")
    return value


def publish(report, evidence, output):
    output = output_path(output)
    data = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    evidence.recheck()
    with Path(output).open("xb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", required=True)
    parser.add_argument("--lineage", type=Path, required=True)
    parser.add_argument("--lineage-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--operational-authorization", action="append", nargs=2, default=[],
                        metavar=("ROOT_JSON", "SHA256"))
    args = parser.parse_args()
    try:
        output_path(args.output)
        report, evidence = build(args.candidate, args.lineage, args.lineage_sha256, args.operational_authorization)
        publish(report, evidence, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"192M assessment rejected: {error}\n")
    print(json.dumps(dict(output=str(args.output), management=report["management"])))


if __name__ == "__main__":
    main()
