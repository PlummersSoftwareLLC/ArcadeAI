#!/usr/bin/env python3
"""Analyze explicitly named FINAL96M guard receipts, never launch or promote.

Import and --help open no candidate/lineage/receipt files. Execution requires
the SHA of a root-verified future96M lineage report. Only an exclusive new JSON
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
CAMPAIGN = RUN.parent
GAME = RUN.parents[2]
PLAN_SHA = "8584f3e90646af460dd2b330bb2cb419c7d9ea8f05014de6e9a2d059447ebac3"
COMPOSITE_SHA = "2dc2f768361944b4e087022c248a21fa24c266da536cd2d653d035aa83874746"
VALIDATORS = {
    "compare_sidecar_measurements.py": "879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746",
    "compare_frozen_measurements.py": "53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0",
    "sidecar_boot.py": "f06492e6d96cd472d9f0073b4c643e820bcacb6a96c5f542a59d6b6874e62362",
}
REFERENCE_LINEAGE_SHA = "2c81a921172d1dcae9f6601660b4f8cc5839b9153d13cc604770dd003a11c2e4"
RESUME_SHA = "d5edb8bce91a01ca9dc115c1731960fb293ed5cd6edaa8d1787378a420b18efe"
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
    spec = importlib.util.spec_from_file_location("guard96_composite_math", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def summarize(rows):
    require(len(rows) >= 2, "Insufficient original full-game rows")
    scores = [row["score"] for row in rows]
    return dict(count=len(scores), mean=statistics.mean(scores), median=statistics.median(scores),
                sd=statistics.stdev(scores), se=statistics.stdev(scores) / math.sqrt(len(scores)))


def decisions(reference, candidates):
    """Exactly the adopted point-management rule, not a statistical test."""
    base = summarize(reference)
    thresholds = dict(mean=0.9 * base["mean"], median=0.9 * base["median"],
                      severe_mean=0.8 * base["mean"])
    legs = []
    for label, rows in candidates.items():
        row = summarize(rows)
        row.update(label=label, mean_alarm=row["mean"] < thresholds["mean"],
                   median_alarm=row["median"] < thresholds["median"], low_N=row["count"] < 64)
        legs.append(row)
    require(1 <= len(legs) <= 2, "Require one or two distinct guard legs")
    first = legs[0]
    needs = first["mean_alarm"] or first["median_alarm"] or first["low_N"]
    mean_confirmed = len(legs) == 2 and all(row["mean_alarm"] for row in legs)
    median_confirmed = len(legs) == 2 and all(row["median_alarm"] for row in legs)
    severe = first["mean"] < thresholds["severe_mean"] and first["median_alarm"]
    if mean_confirmed or median_confirmed:
        status = "repeated_same_criterion_alarm_root_review"
    elif len(legs) == 1 and needs:
        status = "exact_checkpoint_confirmation_required"
    elif any(row["mean_alarm"] or row["median_alarm"] for row in legs):
        status = "mixed_alarm_inconclusive"
    elif sum(row["count"] for row in legs) < 64:
        status = "low_precision_inconclusive"
    else:
        status = "no_preset_alarm_not_proof_of_noninferiority"
    return dict(status=status, reference=base, thresholds=thresholds, each_leg=legs,
        confirmation_required_by_first_leg=bool(needs),
        confirmation_still_needed=bool(needs and len(legs) == 1),
        extra_second_leg_not_requested_by_plan=bool(len(legs) == 2 and not needs),
        repeated_mean_alarm=mean_confirmed, repeated_median_alarm=median_confirmed,
        repeated_same_criterion_alarm=mean_confirmed or median_confirmed,
        low_N_leg_labels=[row["label"] for row in legs if row["low_N"]],
        maximum_valid_legs_reached=len(legs) == 2,
        further_confirmation_authorized=False,
        severe_first_leg_alert=bool(severe), promotion=False, reference_rebased=False,
        scheduled128M_changed=False, automatic_action=False,
        rule="Strictly below10% mean OR median floor; moderate action needs SAME criterion below in BOTH real legs. Never use a pool to erase a failing leg.")


def lineage_identity(report, expected_path, reference_meta):
    require(report.get("schema") == "robotron-96M-checkpoint-lineage-v1"
        and report.get("PASS") is True and report.get("checks")
        and all(value is True for value in report["checks"].values()), "Root lineage report is not a strict PASS")
    require(report["checks"].get("CPU_only") is True, "Missing CPU lineage validation")
    candidate = report["candidate"]
    require(Path(candidate["path"]).resolve() == Path(expected_path).resolve()
        and sha_string(candidate.get("sha256")), "Wrong future96M checkpoint identity")
    meta = candidate["saved_metadata"]
    for key in META_KEYS:
        require(key in meta and isinstance(meta[key], int) and not isinstance(meta[key], bool)
                and meta[key] >= 0, f"Missing/invalid lineage metadata: {key}")
    for key in ("engine_version", "state_size", "single_frame_state_size", "frame_stack"):
        require(meta[key] == reference_meta[key], f"Architecture differs: {key}")
    require(meta["learner_frame_count"] >= 100629023 and all(meta[key] > reference_meta[key]
                for key in CORE_CLOCKS), "Future96M saved gate/clocks did not advance")
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
    require(trigger["tag"] == "fresh3-96M" and trigger["target"] == 100629023
        and Path(trigger["checkpoint"]).resolve() == Path(expected_path).resolve(), "Wrong queued96M gate evidence")
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


def build(labels, lineage_path, lineage_sha):
    evidence = Evidence()
    evidence.file(__file__, digest(__file__))
    plan = evidence.json(RUN / "quality96M-regression-guard-plan.json", PLAN_SHA)
    require(labels == plan["candidate"]["labels"][:len(labels)] and 1 <= len(labels) <= 2,
            "Use explicit prespecified first or first+confirmation96M labels")
    require(sha_string(lineage_sha), "Pass root-verified lineage SHA explicitly")
    lineage = evidence.json(lineage_path, lineage_sha)
    reference = plan["reference"]
    expected_path = GAME / "models_dqn/managed-checkpoints/fresh3-96M.pt"
    identity = lineage_identity(lineage, expected_path, reference["saved_clocks"])
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
    prior_lineage = evidence.json(CAMPAIGN / "run-14/fresh3-64M-checkpoint-lineage.json", REFERENCE_LINEAGE_SHA)
    require(prior_lineage["candidate"]["sha256"] == protected["sha256"]
        and prior_lineage["candidate"]["saved_metadata"] == reference["saved_clocks"], "64M exposure lineage differs")
    reference_optimizer = prior_lineage["candidate"]["optimizer"]
    require(min(identity["optimizer"]["step_values"]) >= max(reference_optimizer["step_values"]),
        "Candidate Adam exposure moved backwards")
    resume = evidence.json(RUN / "final-resume-checkpoint.json", RESUME_SHA)
    require(resume["cpu_only"] is True and resume["cuda_initialized"] is False
        and all(identity["metadata"][key] > resume["saved_metadata"][key] for key in CORE_CLOCKS),
        "Candidate clocks did not advance since selected4096 resume")
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
    require(campaign["sources"] == reference["sources"], "Confirmed64M source identities differ")
    raw, legs = [], []
    ref_identity = dict(path=str(GAME / "models_dqn/managed-checkpoints/fresh3-64M.pt"),
                        sha256=protected["sha256"], metadata=reference["saved_clocks"])
    for source in reference["sources"]:
        row = evidence.json(source["path"], source["sha256"])
        raw.append(row); legs.append(validate_leg(row, source["label"], ref_identity, evidence, tools))
    for label in labels:
        path = CAMPAIGN / label / "receipt.json"
        row = evidence.json(path)
        raw.append(row); legs.append(validate_leg(row, label, identity, evidence, tools))
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
    require(stats["count"] == reference["count"] == 217 and stats["mean"] == reference["mean"]
        and stats["median"] == reference["median"], "Original-row64M composite differs")
    candidates = {leg["label"]: leg["rows"] for leg in legs[2:]}
    decision = decisions(baseline, candidates)
    require(decision["thresholds"]["mean"] == plan["precommitted_decisions"]["mean_alarm_below"]
        and decision["thresholds"]["median"] == plan["precommitted_decisions"]["median_alarm_below"]
        and decision["thresholds"]["severe_mean"] == plan["precommitted_decisions"]["severe_mean_below"],
        "Adopted guard thresholds differ")
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
    result = dict(schema="robotron-96M-regression-guard-analysis-v1", utc=datetime.now(timezone.utc).isoformat(),
        management=decision, fixed_bootstrap_iterations=ITERATIONS, sources=receipt_sources,
        lineage=dict(path=str(Path(lineage_path).resolve()), sha256=lineage_sha),
        policy_identity=dict(reference=ref_identity, candidate=identity),
        optimizer_exposure=dict(reference64M=reference_optimizer, candidate96M=identity["optimizer"],
            minimum_parameter_step_delta=min(identity["optimizer"]["step_values"]) - max(reference_optimizer["step_values"]),
            run19_resume_parameter_steps=None,
            note="Run19 resume JSON did not record Adam parameter steps. Parameter steps and logical updates are distinct; exposure was not all4096."),
        exposure_deltas={name: {key: identity["metadata"][key] - base[key] for key in CORE_CLOCKS}
            for name, base in (("since64M", reference["saved_clocks"]), ("since_run19_resume", resume["saved_metadata"]))},
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
        global_ids=dict(receipts=len(ids), games=len(seen), overlaps=0), evidence=evidence.snapshot(),
        promotion=False, protection=False, state_or_control_changes=False,
        caveats=plan["reporting"][-1:] + ["Actor labels are paired clusters, not identical trajectories; repeated looks remain descriptive.",
            "This guard does not replace scheduled128M promotion assessment and never rebases protected64M.",
            "Official pair calls validate protocols using their minimum100 draws; those sensitivities are discarded. Only the fixed10000-draw composite sensitivities are reported."])
    evidence.recheck()
    return result, evidence


def publish(report, evidence, output):
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
    args = parser.parse_args()
    try:
        require(not args.output.exists(), "Refuse to overwrite guard evidence")
        report, evidence = build(args.candidate, args.lineage, args.lineage_sha256)
        publish(report, evidence, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Guard analysis rejected: {error}\n")
    print(json.dumps(dict(output=str(args.output), management=report["management"])))


if __name__ == "__main__":
    main()
