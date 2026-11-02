#!/usr/bin/env python3
"""Audit only the completed first192M screen and its original128M reference.

No model payloads, pending/future confirmation files, Torch, GPU or controls.
The two output JSONs are new exclusive artifacts; this is not publication.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

RUN = Path(__file__).resolve().parent
CAMPAIGN = RUN.parent
GAME = CAMPAIGN.parents[1]
ANALYSIS_SHA = "ad0502de6efd6dd15f199d1fbfa48cd20fde5141d51132d9dd1734cb83c8e3f1"
PLAN_SHA = "13fecf794902fc9d20c690be6b8bad39d4c0256bf6d3f153fc309ec8003e06aa"
HISTORY_SHA = "171d1cb6d64827c9752d2376f9ea7a5c4835ff34419fe463506a53c0c033eb0e"
LABEL = "sidecar-gpu0-192M-screen-01"
REFS = ("sidecar-gpu0-128M-screen-01", "sidecar-gpu0-128M-confirm-01")
RECEIPT_SHA = "026a5d7714cc8dc2dd46e82244046ba67694d07413a72cd56568836af0e773be"
PINS = {
    "compare_frozen_measurements.py": "53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0",
    "compare_sidecar_measurements.py": "879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746",
}
SLOTS = list(range(4096, 4112))
SEED, DRAWS = 20261016, 10000


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def quantile(values, p):
    values = sorted(values)
    index = (len(values) - 1) * p
    lo, hi = math.floor(index), math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def score_summary(rows, labels):
    scores = [row["score"] for row in rows]
    sd = statistics.stdev(scores)
    return dict(unit="descriptive original-row pool; not a measurement receipt",
        source_labels=list(labels), count=len(rows), mean=statistics.mean(scores),
        median=statistics.median(scores), sd=sd, se=sd / math.sqrt(len(scores)),
        minimum=min(scores), maximum=max(scores),
        actor_slot_counts=dict(sorted(Counter(str(row["client_slot"]) for row in rows).items())),
        game_ids=[row["journal_game_id"] for row in rows])


def resample(base, candidate, cluster=False):
    """Independent implementation of the frozen fixed-seed percentile recipe."""
    rng = random.Random(SEED)
    grouped = []
    for rows in (base, candidate):
        slots = defaultdict(list)
        for row in rows:
            slots[row["client_slot"]].append(row["score"])
        grouped.append(dict(sorted(slots.items())))
    need(set(grouped[0]) == set(grouped[1]) == set(SLOTS), "Cluster coverage differs")
    differences, ratios = [], []
    for _ in range(DRAWS):
        draw = rng.choices(list(grouped[0]), k=len(grouped[0])) if cluster else None
        means = []
        for rows, slots in zip((base, candidate), grouped):
            values = ([value for slot in draw for value in slots[slot]] if cluster else
                      [row["score"] for row in rng.choices(rows, k=len(rows))])
            means.append(statistics.fmean(values))
        differences.append(means[1] - means[0])
        if means[0] > 0:
            ratios.append(means[1] / means[0])
    return dict(method="paired actor-slot clusters" if cluster else "independent games",
        iterations=DRAWS, seed=SEED, percentile=.95,
        mean_difference_ci=[quantile(differences, .025), quantile(differences, .975)],
        mean_ratio_ci=[quantile(ratios, .025), quantile(ratios, .975)],
        ratio_defined_resamples=len(ratios), actor_clusters=[16, 16])


def diagnostics(rows):
    result = {}
    for key in ("max_level", "playable_frames", "duration_s", "deaths"):
        values = [row[key] for row in rows]
        need(all(isinstance(x, (int, float)) and not isinstance(x, bool)
                 and math.isfinite(x) and x >= 0 for x in values), "Bad diagnostic " + key)
        result[key] = dict(count=len(values), mean=statistics.mean(values),
            median=statistics.median(values), sd=statistics.stdev(values),
            se=statistics.stdev(values) / math.sqrt(len(values)),
            minimum=min(values), p25=quantile(values, .25), p75=quantile(values, .75),
            maximum=max(values), total=sum(values))
        if key in ("max_level", "deaths"):
            result[key]["distribution"] = dict(sorted(Counter(map(str, sorted(values))).items(),
                                                       key=lambda pair: float(pair[0])))
    result["derived_descriptive_rates"] = dict(
        total_score_per_playable_frame=sum(row["score"] for row in rows) / sum(row["playable_frames"] for row in rows),
        recorded_deaths_per1000_playable_frames=1000 * sum(row["deaths"] for row in rows) / sum(row["playable_frames"] for row in rows))
    return result


def main():
    started, t0 = utc(), time.monotonic()
    snapshots = {}
    def raw(path, expected=None):
        path = Path(path).absolute()
        need(not path.is_symlink() and path.is_file(), "Unexpected evidence type")
        if path not in snapshots:
            snapshots[path] = path.read_bytes()
        value = snapshots[path]
        need(expected is None or digest(value) == expected, "Changed evidence: " + str(path))
        return value
    def document(path, expected=None):
        return json.loads(raw(path, expected))
    analysis = document(RUN / "quality192M-screen-first-analysis.json", ANALYSIS_SHA)
    plan = document(RUN / "quality192M-preparation/quality192M-assessment-plan.json", PLAN_SHA)
    history = document(RUN / "quality192M-preparation/history-manifest.final.json", HISTORY_SHA)
    lineage = document(analysis["lineage"]["path"], analysis["lineage"]["sha256"])
    raw(__file__)
    for name, expected in PINS.items():
        raw(GAME / "tools" / name, expected)
    sys.path.insert(0, str(GAME / "tools"))
    from compare_frozen_measurements import validate_receipt
    from compare_sidecar_measurements import validate_backend, JOB_FIELDS
    need(not any(name.startswith("torch") for name in sys.modules), "Torch imported")
    receipts, legs, seen = {}, {}, {}
    for source in analysis["sources"]:
        label = source["label"]
        need(label != "sidecar-gpu0-192M-confirm-01" and label not in receipts, "Unexpected/duplicate label")
        receipt = document(source["path"], source["sha256"])
        leg = validate_receipt(receipt)
        if "job" in receipt:
            validate_backend(receipt, verify_checkpoint=False)
        need(label == leg["label"], "Label differs")
        receipts[label], legs[label] = receipt, leg
        for row in leg["rows"]:
            identifier = row["journal_game_id"]
            need(identifier not in seen, "Global game ID overlap")
            seen[identifier] = label
    checks = {}
    def check(name, value):
        need(value, name)
        checks[name] = True
    historical = {(s["label"], s["path"], s["sha256"]) for s in history["all_original_receipt_sources"]}
    reported = {(s["label"], s["path"], s["sha256"]) for s in analysis["sources"] if s["label"] != LABEL}
    check("pinned24_history_registry_exact", reported == historical and len(historical) == 24)
    check("all25_separately_valid_full_receipts_2552_disjoint_IDs", len(legs) == 25 and len(seen) == 2552
        and analysis["global_ids"] == dict(receipts=25, games=2552, overlaps=0))
    reference = [row for label in REFS for row in legs[label]["rows"]]
    candidate = legs[LABEL]["rows"]
    check("original148_and52_denominators_no_filtering", len(reference) == 148 and len(candidate) == 52)
    current = receipts[LABEL]
    check("explicit192_receipt_SHA", digest(snapshots[Path(next(s["path"] for s in analysis["sources"] if s["label"] == LABEL))]) == RECEIPT_SHA)
    check("root_final_CPU_lineage_PASS_identity", lineage["proposal_only"] is False and lineage["PASS"] is True
        and all(v is True for v in lineage["checks"].values()) and lineage["root_verification"]["status"] == "PASS"
        and lineage["root_verification"]["CUDA_initialized"] is False
        and analysis["policy_identity"]["candidate"] == dict(path=lineage["candidate"]["path"],
            sha256=lineage["candidate"]["sha256"], metadata=lineage["candidate"]["saved_metadata"],
            optimizer=lineage["candidate"]["optimizer"]))
    check("192_clocks_Adam_exposure_separate", lineage["candidate"]["saved_metadata"]["training_steps"] == 1156456
        and lineage["candidate"]["saved_metadata"]["optimized_samples"] == 3289255936
        and lineage["candidate"]["saved_metadata"]["learner_frame_count"] == 196632084
        and lineage["candidate"]["optimizer"]["state_count"] == 81
        and lineage["candidate"]["optimizer"]["step_values"] == [1155946.0]
        and lineage["actual_recorded_batch_exposure"]["since128M"]["optimized_samples_delta"] == 4096 * lineage["actual_recorded_batch_exposure"]["since128M"]["logical_updates_delta"])
    check("all3_matching_frozen_backend_source12_boot_numeric", all(
        all(receipts[label]["job"][k] == current["job"][k] for k in JOB_FIELDS)
        and all(receipts[label][k] == current[k] for k in ("numeric_policy", "runtime", "source_hashes"))
        and receipts[label]["boot_assets"]["identity"] == current["boot_assets"]["identity"]
        and receipts[label]["socket_wait"]["sha256"] == current["socket_wait"]["sha256"]
        for label in REFS) and len(current["source_hashes"]) == 12)
    for label, identity in [(x, analysis["policy_identity"]["reference"]) for x in REFS] + [(LABEL, analysis["policy_identity"]["candidate"])]:
        receipt, leg = receipts[label], legs[label]
        check(label + "_identity_metadata_clocks_all16_tails", receipt["checkpoint_sha256"] == identity["sha256"]
            and receipt["source_checkpoint_path"] == receipt["job"]["checkpoint"] == identity["path"]
            and receipt["checkpoint_metadata"]["defaulted_metadata_fields"] == []
            and all(receipt["checkpoint_metadata"][k] == identity["metadata"][k] for k in
                ("training_steps", "optimized_samples", "learner_frame_count", "engine_version", "state_size",
                 "single_frame_state_size", "frame_stack", "frame_count", "measurement_frame_count",
                 "total_training_steps", "last_target_update_samples"))
            and all(leg["clocks"][alias] == identity["metadata"][k] for k, alias in
                    (("training_steps", "training_steps"), ("optimized_samples", "optimized_samples"), ("learner_frame_count", "learner_frames")))
            and sorted({row["client_slot"] for row in leg["rows"]}) == SLOTS
            and receipt["boundary"]["clients"] == receipt["boundary"]["expected"] == receipt["boundary"]["acknowledged"] == 16
            and receipt["boundary"]["generation"] == receipt["boundary"]["requested_generation"] == receipt["generation"]
            and all(row["boundary_reason"] == "wire_lives_exhausted" and row["end_unix_s"] <= receipt["ended_unix_s"] for row in leg["rows"]))
    base, now = score_summary(reference, REFS), score_summary(candidate, [LABEL])
    contrasts = {}
    for slot in SLOTS:
        values = [[row["score"] for row in rows if row["client_slot"] == slot] for rows in (reference, candidate)]
        means = list(map(statistics.mean, values))
        contrasts[str(slot)] = dict(reference_count=len(values[0]), candidate_count=len(values[1]),
            reference_mean=means[0], candidate_mean=means[1], mean_difference=means[1] - means[0], mean_ratio=means[1] / means[0])
    comparison = dict(reference=base, candidate=now, mean_difference=now["mean"] - base["mean"],
        mean_ratio=now["mean"] / base["mean"], median_difference=now["median"] - base["median"],
        game_bootstrap=resample(reference, candidate), paired_slot_bootstrap=resample(reference, candidate, True),
        actor_contrasts=contrasts, slots_with_positive_mean_contrast=sum(x["mean_difference"] > 0 for x in contrasts.values()))
    check("all_composite_math_10000_game_and_paired_slot_draws_exact", comparison == analysis["pooled_candidate_vs_composite"]
        and comparison == analysis["each_candidate_vs_composite"][LABEL])
    m = analysis["management"]
    check("unchanged_per_leg_promotion_and_regression_threshold_arithmetic", m["thresholds"] == dict(
        mean=.9 * base["mean"], median=.9 * base["median"], severe_mean=.8 * base["mean"],
        gain_mean=1.05 * base["mean"], gain_median=base["median"])
        and m["thresholds"]["gain_mean"] == plan["precommitted_decisions"]["mean_at_least_each_leg"])
    expected_leg = {k: now[k] for k in ("count", "mean", "median", "sd", "se")}
    expected_leg.update(label=LABEL, mean_alarm=now["mean"] < .9 * base["mean"],
        median_alarm=now["median"] < .9 * base["median"], low_N=len(candidate) < 64,
        mean_gate=now["mean"] >= 1.05 * base["mean"], median_gate=now["median"] >= base["median"],
        passes_both_promotion_gates=True, severe_alert=False)
    check("first_leg_passes_gates_lowN_precision_only", m["each_leg"] == [expected_leg]
        and m["reference"] == {k: base[k] for k in ("count", "mean", "median", "sd", "se")})
    check("mandatory_second_no_promotion_rebase_or_automatic_plateau", m["status"] == "second_fixed_leg_required_regardless_first_quality"
        and m["confirmation_still_needed"] is True and m["two_fixed_valid_legs_required"] is True
        and m["second_leg_required_regardless_first_quality"] is True
        and all(m[k] is False for k in ("promotion_eligible", "maximum_valid_legs_reached", "promotion",
                "reference_rebased", "automatic_action", "plateau_declared", "learning_knob_change_authorized", "third_valid_cohort_authorized"))
        and analysis["promotion"] is analysis["protection"] is analysis["state_or_control_changes"] is False)
    cleanup = document(RUN / "quality192M-screen01-final-isolation-audit.json")
    check("separate_positive_cleanup_attestation_matches_final_receipt_policy", cleanup["pass"] is True
        and cleanup["checks"] and all(v is True for v in cleanup["checks"].values())
        and cleanup["receipt_sha256"] == RECEIPT_SHA and cleanup["checkpoint_sha256"] == current["checkpoint_sha256"]
        and all(cleanup["checks"].get(k) is True for k in
            ("private_owned_processes_listener_released", "private_GPU0_context_released", "loaded_sources_unchanged")))
    summaries = {"original128M_reference148": diagnostics(reference), "first192M_screen52": diagnostics(candidate)}
    differences = {key: {"mean_delta": summaries["first192M_screen52"][key]["mean"] - summaries["original128M_reference148"][key]["mean"],
        "mean_ratio": summaries["first192M_screen52"][key]["mean"] / summaries["original128M_reference148"][key]["mean"],
        "median_delta": summaries["first192M_screen52"][key]["median"] - summaries["original128M_reference148"][key]["median"]}
        for key in ("max_level", "playable_frames", "duration_s", "deaths")}
    check("supporting_all_original_fields_complete_no_new_gates", all(
        x[key]["count"] == count for x, count in ((summaries["original128M_reference148"], 148),
            (summaries["first192M_screen52"], 52)) for key in ("max_level", "playable_frames", "duration_s", "deaths")))
    for path, original in snapshots.items():
        need(path.read_bytes() == original, "Evidence changed during independent audit")
    finished = utc()
    sources = [dict(path=str(path), sha256=digest(value), bytes=len(value)) for path, value in snapshots.items()]
    proof = dict(schema="robotron-192M-first-independent-math-proof-v1", started_utc=started,
        finished_utc=finished, elapsed_s=time.monotonic() - t0, pid=os.getpid(), pass_=True,
        checks=checks, exact_reproduced_comparison=comparison, source_snapshots=sources,
        scope="Only completed final JSON receipts, small JSON/source pins and stdlib math. No model payload hashes/loads, Torch/GPU/context, future confirmation reads, process/control/state/source changes or actual publication.")
    proof["pass"] = proof.pop("pass_")
    proof_path = RUN / "quality192M-screen-first-independent-math-proof.json"
    proof_bytes = (json.dumps(proof, indent=2) + "\n").encode()
    result = dict(schema="robotron-192M-first-independent-summary-v1", utc=finished, pass_=True,
        checks=checks, analysis_sha256=ANALYSIS_SHA, receipt_sha256=RECEIPT_SHA,
        proof=dict(path=str(proof_path), sha256=digest(proof_bytes)), original_denominators=dict(reference=148, candidate=52),
        scores={k: comparison[k] for k in ("reference", "candidate", "mean_difference", "mean_ratio", "median_difference", "game_bootstrap", "paired_slot_bootstrap", "slots_with_positive_mean_contrast")},
        supporting_diagnostics=summaries, supporting_differences=differences,
        management="First complete valid leg passes its mean and median gates; mandatory same-checkpoint second leg remains outstanding. No promotion, rebase, pooled rescue or automatic learning change.",
        interpretation=["Supporting depth/duration/life counters use every original row and add no selection gate or bootstrap claim.",
            "max_level is the highest journal-observed level after playable start, not levels completed; playable_frames counts received actor frames while alive, not host FPS or wall duration.",
            "duration_s is host wall time from recognized game start through final death, including inactive/death intervals; it is affected by emulator/host pacing and is not a pure game-time clock.",
            "deaths counts journal done-edge events following observed playable life. Extra lives and longer games can increase the count; it is not a fixed initial-life budget or a standalone quality metric.",
            "All52 screen games, including9 tails after admission closed, are retained. LowN52 meets the official50-game validity floor but has limited precision; two fixed legs remain required regardless first result.",
            "Intervals are fixed10000-draw descriptive sensitivities, not formal confidence or repeated-look correction. Actor slots are paired labels, not matched trajectories.",
            "Checkpoint identities use saved root-final CPU verification and immutable receipt metadata; this audit does not reload/hash model payloads or independently repeat OS cleanup checks.",
            "Learning and policy selection are sequential with shared host/policy history; no causal claim about batch4096 or any individual optimization follows."])
    result["pass"] = result.pop("pass_")
    for path, value in ((proof_path, proof_bytes), (RUN / "quality192M-screen-first-independent-summary.json", (json.dumps(result, indent=2) + "\n").encode())):
        with path.open("xb") as out:
            out.write(value)
        print(path.name, digest(value))
    print(json.dumps(dict(checks=len(checks), comparisons=1, draws_per_method=DRAWS, supporting=summaries,
        differences=differences, started_utc=started, finished_utc=finished), indent=2))


if __name__ == "__main__":
    main()
