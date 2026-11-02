#!/usr/bin/env python3
"""Final192M math/depth review only; operational cleanup is separately audited."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

RUN = Path(__file__).resolve().parent
GAME = RUN.parents[2]
LABELS = ("sidecar-gpu0-192M-screen-01", "sidecar-gpu0-192M-confirm-01")
REFS = ("sidecar-gpu0-128M-screen-01", "sidecar-gpu0-128M-confirm-01")
ANALYSIS_SHA = "828fcf58476fd87afcb6973cfbd40353257c3add49b13f095023b73fb26204bb"
PLAN_SHA = "13fecf794902fc9d20c690be6b8bad39d4c0256bf6d3f153fc309ec8003e06aa"
HISTORY_SHA = "171d1cb6d64827c9752d2376f9ea7a5c4835ff34419fe463506a53c0c033eb0e"
RECEIPT_SHAS = ("026a5d7714cc8dc2dd46e82244046ba67694d07413a72cd56568836af0e773be",
                 "f38c5ad61b4ec27a06f1967b64a7ec414fdf1bdafe0da3c0cd58b733be2acc86")
META_KEYS = ("training_steps", "optimized_samples", "learner_frame_count", "engine_version", "state_size",
    "single_frame_state_size", "frame_stack", "frame_count", "measurement_frame_count", "total_training_steps", "last_target_update_samples")
SLOTS = list(range(4096, 4112))


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    snapshots = {}
    def raw(path, expected=None):
        path = Path(path).absolute()
        require(not path.is_symlink() and path.is_file(), "Evidence not a regular file")
        if path not in snapshots:
            snapshots[path] = path.read_bytes()
        value = snapshots[path]
        require(expected is None or sha(value) == expected, "Changed evidence: " + str(path))
        return value
    def doc(path, expected=None):
        return json.loads(raw(path, expected))
    raw(__file__)
    analysis = doc(RUN / "quality192M-two-leg-final-analysis.json", ANALYSIS_SHA)
    plan = doc(RUN / "quality192M-preparation/quality192M-assessment-plan.json", PLAN_SHA)
    history = doc(RUN / "quality192M-preparation/history-manifest.final.json", HISTORY_SHA)
    lineage = doc(analysis["lineage"]["path"], analysis["lineage"]["sha256"])
    math_path = RUN / "audit192M_screen_first.py"
    prior_proof = doc(RUN / "quality192M-screen-first-independent-math-proof.json",
        "52a041eb1979d680124d8c796198a147858bb88d69ce1bea9808e028fb0ba87e")
    math_sha = next(row["sha256"] for row in prior_proof["source_snapshots"] if row["path"] == str(math_path))
    raw(math_path, math_sha)
    spec = importlib.util.spec_from_file_location("independent192_math", math_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    for name, expected in helper.PINS.items():
        raw(GAME / "tools" / name, expected)
    sys.path.insert(0, str(GAME / "tools"))
    from compare_frozen_measurements import validate_receipt
    from compare_sidecar_measurements import validate_backend, JOB_FIELDS
    require(not any(name.startswith("torch") for name in sys.modules), "Torch unexpectedly imported")
    checks = {}
    def check(name, value):
        require(value, name)
        checks[name] = True
    receipts, legs, source_map, ids = {}, {}, {}, {}
    for source in analysis["sources"]:
        label = source["label"]
        require(label not in receipts, "Duplicate source label")
        receipt = doc(source["path"], source["sha256"])
        leg = validate_receipt(receipt)
        if "job" in receipt:
            validate_backend(receipt, verify_checkpoint=False)
        require(leg["label"] == label, "Receipt label differs")
        receipts[label], legs[label], source_map[label] = receipt, leg, source
        for row in leg["rows"]:
            require(row["journal_game_id"] not in ids, "Game ID overlap")
            ids[row["journal_game_id"]] = label
    check("all26_final_receipts_separately_valid_and2613_uniqueIDs", len(receipts) == 26 and len(ids) == 2613
        and analysis["global_ids"] == dict(receipts=26, games=2613, overlaps=0))
    check("original24_history_pins_2500rows_exact", {(s["label"], s["path"], s["sha256"]) for s in analysis["sources"] if s["label"] not in LABELS}
        == {(s["label"], s["path"], s["sha256"]) for s in history["all_original_receipt_sources"]}
        and sum(len(leg["rows"]) for label, leg in legs.items() if label not in LABELS) == 2500)
    check("both_new_receipt_SHA_pins", all(source_map[label]["sha256"] == expected for label, expected in zip(LABELS, RECEIPT_SHAS)))
    baseline = [row for label in REFS for row in legs[label]["rows"]]
    pooled = [row for label in LABELS for row in legs[label]["rows"]]
    check("original148_and52plus61_all113_no_trimming", len(baseline) == 148 and len(pooled) == 113
        and [len(legs[label]["rows"]) for label in LABELS] == [52, 61])
    candidate_identity = analysis["policy_identity"]["candidate"]
    check("root_final_CPU_lineage_PASS_bound_identity", lineage["proposal_only"] is False and lineage["PASS"] is True
        and lineage["checks"] and all(value is True for value in lineage["checks"].values())
        and lineage["root_verification"]["status"] == "PASS" and lineage["root_verification"]["CUDA_initialized"] is False
        and candidate_identity == dict(path=lineage["candidate"]["path"], sha256=lineage["candidate"]["sha256"],
            metadata=lineage["candidate"]["saved_metadata"], optimizer=lineage["candidate"]["optimizer"]))
    current = receipts[LABELS[0]]
    check("all4_same_backend_numeric_runtime_source12_boot_shim", all(
        all(receipts[label]["job"][k] == current["job"][k] for k in JOB_FIELDS)
        and all(receipts[label][k] == current[k] for k in ("numeric_policy", "runtime", "source_hashes"))
        and receipts[label]["boot_assets"]["identity"] == current["boot_assets"]["identity"]
        and receipts[label]["socket_wait"]["sha256"] == current["socket_wait"]["sha256"]
        for label in (*REFS, *LABELS)) and len(current["source_hashes"]) == 12)
    for label in (*REFS, *LABELS):
        receipt, leg = receipts[label], legs[label]
        identity = analysis["policy_identity"]["reference" if label in REFS else "candidate"]
        check(label + "_identity_full16_boundary_frozen_clocks_fulltails", receipt["checkpoint_sha256"] == identity["sha256"]
            and receipt["source_checkpoint_path"] == receipt["job"]["checkpoint"] == identity["path"]
            and receipt["checkpoint_metadata"]["defaulted_metadata_fields"] == []
            and all(receipt["checkpoint_metadata"][k] == identity["metadata"][k] for k in META_KEYS)
            and all(leg["clocks"][alias] == identity["metadata"][key] for key, alias in
                (("training_steps", "training_steps"), ("optimized_samples", "optimized_samples"), ("learner_frame_count", "learner_frames")))
            and receipt["boundary"]["clients"] == receipt["boundary"]["expected"] == receipt["boundary"]["acknowledged"] == 16
            and receipt["boundary"]["generation"] == receipt["boundary"]["requested_generation"] == receipt["generation"]
            and sorted({row["client_slot"] for row in leg["rows"]}) == SLOTS
            and all(row["boundary_reason"] == "wire_lives_exhausted" and row["end_unix_s"] <= receipt["ended_unix_s"] for row in leg["rows"]))
    check("Adam81_4096_exposure_distinct_from_logicalclocks", candidate_identity["optimizer"]["state_count"] == 81
        and candidate_identity["optimizer"]["step_values"] == [1155946.0]
        and lineage["actual_recorded_batch_exposure"]["since128M"]["optimized_samples_delta"]
            == 4096 * lineage["actual_recorded_batch_exposure"]["since128M"]["logical_updates_delta"])
    def compare(rows, labels):
        base, now = helper.score_summary(baseline, REFS), helper.score_summary(rows, labels)
        contrasts = {}
        for slot in SLOTS:
            scores = [[row["score"] for row in values if row["client_slot"] == slot] for values in (baseline, rows)]
            means = list(map(statistics.mean, scores))
            contrasts[str(slot)] = dict(reference_count=len(scores[0]), candidate_count=len(scores[1]),
                reference_mean=means[0], candidate_mean=means[1], mean_difference=means[1] - means[0], mean_ratio=means[1] / means[0])
        return dict(reference=base, candidate=now, mean_difference=now["mean"] - base["mean"],
            mean_ratio=now["mean"] / base["mean"], median_difference=now["median"] - base["median"],
            game_bootstrap=helper.resample(baseline, rows), paired_slot_bootstrap=helper.resample(baseline, rows, True),
            actor_contrasts=contrasts, slots_with_positive_mean_contrast=sum(v["mean_difference"] > 0 for v in contrasts.values()))
    comparisons = {}
    for label in LABELS:
        comparisons[label] = compare(legs[label]["rows"], [label])
        check(label + "_every_stat_and10000_game_cluster_draws_exact", comparisons[label] == analysis["each_candidate_vs_composite"][label])
    combined = compare(pooled, LABELS)
    check("pooled113_weighted_mean_median_SE_contrasts_and10000_draws_exact", combined == analysis["pooled_candidate_vs_composite"])
    base = combined["reference"]
    thresholds = dict(mean=.9 * base["mean"], median=.9 * base["median"], severe_mean=.8 * base["mean"],
        gain_mean=1.05 * base["mean"], gain_median=base["median"])
    m = analysis["management"]
    check("exact_precommitted5pct_and_median_regression_thresholds", m["thresholds"] == thresholds
        and thresholds["gain_mean"] == plan["precommitted_decisions"]["mean_at_least_each_leg"]
        and thresholds["gain_median"] == plan["precommitted_decisions"]["median_at_least_each_leg"])
    expected = []
    for label in LABELS:
        stats = comparisons[label]["candidate"]
        row = {k: stats[k] for k in ("count", "mean", "median", "sd", "se")}
        row.update(label=label, mean_alarm=stats["mean"] < thresholds["mean"], median_alarm=stats["median"] < thresholds["median"],
            low_N=stats["count"] < 64, mean_gate=stats["mean"] >= thresholds["gain_mean"], median_gate=stats["median"] >= thresholds["gain_median"])
        row.update(passes_both_promotion_gates=row["mean_gate"] and row["median_gate"],
            severe_alert=stats["mean"] < thresholds["severe_mean"] and row["median_alarm"])
        expected.append(row)
    check("both_original_leg_gates_pass_individually_no_poolrescue", m["each_leg"] == expected
        and all(row["passes_both_promotion_gates"] and not row["mean_alarm"] and not row["median_alarm"] for row in expected))
    check("eligible_review_only_no_promotion_rebase_extra_cohort_or_knob", m["status"] == "two_legs_pass_root_promotion_review"
        and m["promotion_eligible"] is m["maximum_valid_legs_reached"] is True
        and m["two_fixed_valid_legs_required"] is m["second_leg_required_regardless_first_quality"] is True
        and all(m[k] is False for k in ("confirmation_still_needed", "repeated_mean_alarm", "repeated_median_alarm",
            "repeated_same_criterion_alarm", "third_valid_cohort_authorized", "plateau_declared", "learning_knob_change_authorized",
            "promotion", "reference_rebased", "automatic_action"))
        and all(analysis[k] is False for k in ("promotion", "protection", "state_or_control_changes")))
    groups = {"original128M_reference148": baseline, "first192M_screen52": legs[LABELS[0]]["rows"],
        "second192M_confirm61": legs[LABELS[1]]["rows"], "descriptive192M_pool113": pooled}
    diagnostics = {name: helper.diagnostics(rows) for name, rows in groups.items()}
    differences = {name: {key: dict(mean_delta=stats[key]["mean"] - diagnostics["original128M_reference148"][key]["mean"],
        mean_ratio=stats[key]["mean"] / diagnostics["original128M_reference148"][key]["mean"],
        median_delta=stats[key]["median"] - diagnostics["original128M_reference148"][key]["median"])
        for key in ("max_level", "playable_frames", "duration_s", "deaths")}
        for name, stats in diagnostics.items() if name != "original128M_reference148"}
    check("all_original_depth_duration_death_fields_retained_no_new_gate", all(
        stats[key]["count"] == len(groups[name]) for name, stats in diagnostics.items()
        for key in ("max_level", "playable_frames", "duration_s", "deaths")))
    for path, value in snapshots.items():
        require(path.read_bytes() == value, "Evidence changed during independent math audit")
    finished = datetime.now(timezone.utc).isoformat()
    proof = dict(schema="robotron-192M-two-leg-independent-math-proof-v1", started_utc=started,
        finished_utc=finished, elapsed_s=time.monotonic() - t0, pid=os.getpid(), checks=checks,
        each_leg_reproduction=comparisons, pooled_reproduction=combined,
        source_snapshots=[dict(path=str(p), sha256=sha(b), bytes=len(b)) for p, b in snapshots.items()],
        scope="Final JSON receipts and small lineage/plan/source bytes only; no model payload hash/load, Torch/GPU, tests, controls or state/publication/protection action. No cleanup-log reclassification attempted.")
    proof["pass"] = True
    proof_path = RUN / "quality192M-two-leg-independent-math-proof.json"
    proof_raw = (json.dumps(proof, indent=2) + "\n").encode()
    summary = dict(schema="robotron-192M-two-leg-independent-summary-v1", utc=finished, checks=checks,
        analysis_sha256=ANALYSIS_SHA, proof=dict(path=str(proof_path), sha256=sha(proof_raw)),
        original_denominators=dict(reference=148, candidate_legs=[52, 61], candidate_pool=113), global_ids=analysis["global_ids"],
        each_leg=[dict(label=label, **{k:v for k,v in comparisons[label].items() if k not in ("reference", "actor_contrasts")}) for label in LABELS],
        descriptive_candidate_pool={k:v for k,v in combined.items() if k not in ("reference", "actor_contrasts")},
        supporting_diagnostics=diagnostics, supporting_differences=differences,
        management="Both separate fixed valid legs pass the adopted mean and median point gates. Numerical eligibility for ROOT review only. No protection, publication, promotion, reference rebase or control action.",
        operational_cleanup_status="SEPARATE_PENDING_AUTHORITATIVE_FINAL_ISOLATION_AUDIT: root reported cleanup-only batcher-stop exceptions. This math review does not classify logs or establish final operational publication readiness.",
        limitations=["All original148 reference and113 candidate rows retained, including full admitted late tails; no pooled rescue of a failed leg and no additional diagnostic gate.",
            "Both candidate counts52/61 meet the existing50-game validity floor; N<64 remains a precision caveat, not authorization for another valid cohort.",
            "The113-row pool is descriptive and not a fabricated merged measurement receipt. Both individual legs decide numerical eligibility.",
            "max_level is highest journal-observed wire level after playable start, not completed waves. playable_frames counts received alive frames, not60Hz-converted seconds.",
            "duration_s is host wall time through the recorded end boundary, including inactive/death/restart/host-wait intervals; every current diagnostic row ended wire_lives_exhausted. It is not pure emulated survival time.",
            "deaths counts observed journal done edges following playable life. Earned extra lives and longer games can increase it; it is not a fixed3-life or standalone quality metric.",
            "Game and paired-slot fixed10000-draw intervals are descriptive sensitivities without correction for repeated policy selection/shared host/trajectory history. Slot labels do not match trajectories.",
            "Checkpoint identity comes from receipt metadata and final rootCPUlineage; no repeat model payload load/hash or OS cleanup audit was performed here.",
            "Sequential learning changes and continuing training do not isolate a causal batch4096, GPU or individual optimization effect."])
    summary["pass"] = True
    for path, value in ((proof_path, proof_raw), (RUN / "quality192M-two-leg-independent-summary.json", (json.dumps(summary, indent=2) + "\n").encode())):
        with path.open("xb") as output:
            output.write(value)
        print(path.name, sha(value))
    print(json.dumps(dict(checks=len(checks), pooled_count=113, pooled_mean=combined["candidate"]["mean"],
        pooled_median=combined["candidate"]["median"], pooled_se=combined["candidate"]["se"], mean_ratio=combined["mean_ratio"],
        game_bootstrap=combined["game_bootstrap"], paired_slot_bootstrap=combined["paired_slot_bootstrap"],
        diagnostics={name:{key:{k:stats[key][k] for k in ("count", "mean", "median", "minimum", "maximum")}
            for key in ("max_level", "playable_frames", "duration_s", "deaths")} for name, stats in diagnostics.items()},
        started_utc=started, finished_utc=finished), indent=2))


if __name__ == "__main__":
    main()
