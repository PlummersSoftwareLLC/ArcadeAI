#!/usr/bin/env python3
"""Analyze final64M receipt(s) against BOTH valid32M references, never merging receipts.

This stdlib-only report cannot launch, protect checkpoints, mutate managed state,
or overwrite output. Incomplete/invalid evidence raises before publication;
valid score regressions are retained with an explicitly failed management gate.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import statistics
import sys

RUN = Path(__file__).resolve().parent
CAMPAIGN = RUN.parent
GAME = RUN.parents[2]
sys.path.insert(0, str(GAME / "tools"))
from compare_sidecar_measurements import JOB_FIELDS, compare_sidecars, validate_backend
from compare_frozen_measurements import bootstrap, validate_receipt
from sidecar_boot import load_snapshot

REFERENCE_PLAN_SHA = "a380203462ad9d6453fa5aaca2fbff196922fbe25a81035a286b66cabd4ddc08"
REFERENCE_MODEL_SHA = "50a374d33250713ba205024f85aaed3e50b62db913c29b2c2fb8c28392f051af"
EXPECTED_SHA = "fe88785bf9475c50a7a3df6cd04ab52caf46b706a7f6e22c36b99c21bcc93244"
REFERENCE_CLOCKS = dict(training_steps=368323, optimized_samples=778166272, learner_frame_count=36632770)
CANDIDATE_CLOCKS = dict(training_steps=607219, optimized_samples=1267425280, learner_frame_count=68634783)
SLOTS = list(range(4096, 4112))
SEED = 20261016
VALIDATOR_HASHES = {
    "compare_sidecar_measurements.py": "879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746",
    "compare_frozen_measurements.py": "53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def pinned_json(path, expected):
    path = Path(path)
    require(not path.is_symlink(), f"Unexpected symlink: {path}")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, f"Changed evidence: {path}")
    return json.loads(raw)


def summarize(rows, labels):
    scores = [row["score"] for row in rows]
    require(len(scores) >= 2, "Insufficient full-game rows")
    sd = statistics.stdev(scores)
    return dict(unit="descriptive original-row pool; not a measurement receipt",
        source_labels=list(labels), count=len(rows), mean=statistics.mean(scores),
        median=statistics.median(scores), sd=sd, se=sd / math.sqrt(len(scores)),
        minimum=min(scores), maximum=max(scores),
        actor_slot_counts=dict(sorted(Counter(str(row["client_slot"]) for row in rows).items())),
        game_ids=[row["journal_game_id"] for row in rows])


def analyze_rows(reference, candidate, reference_labels, candidate_labels, iterations):
    baseline = summarize(reference, reference_labels)
    current = summarize(candidate, candidate_labels)
    contrasts = {}
    for slot in SLOTS:
        scores = [[row["score"] for row in values if row["client_slot"] == slot]
                  for values in (reference, candidate)]
        require(all(scores), f"Missing paired actor slot: {slot}")
        means = [statistics.mean(values) for values in scores]
        contrasts[str(slot)] = dict(reference_count=len(scores[0]), candidate_count=len(scores[1]),
            reference_mean=means[0], candidate_mean=means[1], mean_difference=means[1] - means[0],
            mean_ratio=means[1] / means[0] if means[0] else None)
    return dict(reference=baseline, candidate=current,
        mean_difference=current["mean"] - baseline["mean"], mean_ratio=current["mean"] / baseline["mean"],
        median_difference=current["median"] - baseline["median"],
        game_bootstrap=bootstrap(reference, candidate, iterations=iterations, seed=SEED),
        paired_slot_bootstrap=bootstrap(reference, candidate, iterations=iterations, seed=SEED, cluster=True),
        actor_contrasts=contrasts,
        slots_with_positive_mean_contrast=sum(value["mean_difference"] > 0 for value in contrasts.values()))


def management_gate(reference, candidates):
    baseline = summarize(reference, [])
    result = {}
    for label, rows in candidates.items():
        current = summarize(rows, [label])
        result[label] = dict(count=current["count"], mean=current["mean"], median=current["median"],
            mean_ratio=current["mean"] / baseline["mean"],
            mean_at_least5pct=current["mean"] >= 1.05 * baseline["mean"],
            median_at_least_reference=current["median"] >= baseline["median"])
    every = bool(result) and all(row["mean_at_least5pct"] and row["median_at_least_reference"] for row in result.values())
    return dict(reference_count=baseline["count"], reference_mean=baseline["mean"], reference_median=baseline["median"],
        mean_minimum=1.05 * baseline["mean"], each_candidate=result, every_supplied_leg_passes=every,
        two_separate_candidate_legs_present=len(result) == 2,
        confirmation_gate_passed=len(result) == 2 and every,
        rule="Each separate64M leg mean>=1.05 times pooled236 reference mean and median>=pooled reference median; confirmation required.")


def validate_leg(label, *, expected_sha, clocks, receipt_sha=None):
    require(Path(label).name == label, "Receipt label must be one path component")
    path = CAMPAIGN / label / "receipt.json"
    require(not path.is_symlink(), f"Unexpected receipt symlink: {path}")
    receipt_bytes = path.read_bytes()
    receipt_digest = hashlib.sha256(receipt_bytes).hexdigest()
    if receipt_sha is not None:
        require(receipt_digest == receipt_sha, f"Changed receipt: {path}")
    receipt = json.loads(receipt_bytes)
    leg = validate_backend(receipt, verify_checkpoint=True)
    require(receipt["label"] == label and receipt["phase"] == "finished"
            and receipt["reason"] is None and receipt["receipt_validator"] == "passed", f"Not a final named validated leg: {label}")
    require(receipt["checkpoint_sha256"] == expected_sha, f"Wrong policy identity: {label}")
    expected_source = GAME / "models_dqn/managed-checkpoints" / (
        "fresh3-32M.pt" if expected_sha == REFERENCE_MODEL_SHA else "fresh3-64M.pt")
    require(Path(receipt["source_checkpoint_path"]).resolve() == expected_source.resolve()
        and Path(receipt["job"]["checkpoint"]).resolve() == expected_source.resolve(), f"Wrong explicit checkpoint source: {label}")
    require(digest(expected_source) == expected_sha, f"Changed source checkpoint: {label}")
    for key, expected in clocks.items():
        leg_key = "learner_frames" if key == "learner_frame_count" else key
        require(receipt["checkpoint_metadata"][key] == receipt["clocks"][key] == leg["clocks"][leg_key] == expected,
            f"Saved actor/checkpoint clocks differ: {label}/{key}")
    require(receipt["job"]["cohort_s"] == 600 and receipt["job"]["timeout_s"] == 1200
        and receipt["job"]["port"] == 9999 and receipt["job"]["wait_us"] == 1000
        and receipt["job"]["inference_backend"] == "inductor", f"Unexpected frozen backend: {label}")
    boundary = receipt["boundary"]
    require(boundary["clients"] == boundary["expected"] == boundary["acknowledged"] == 16
        and boundary["generation"] == boundary["requested_generation"] == receipt["generation"]
        and sorted(boundary["actor_slots"]) == leg["expected_actor_slots"] == SLOTS,
        f"Actor boundary coverage differs: {label}")
    require(sorted({row["client_slot"] for row in leg["rows"]}) == SLOTS, f"Extra/missing actor slots: {label}")
    boot = load_snapshot(Path(receipt["job"]["boot_assets"]))
    require(boot["identity"] == receipt["boot_assets"]["identity"] and boot["files"] == receipt["boot_assets"]["files"],
        f"Boot seed changed: {label}")
    require(digest(receipt["socket_wait"]["library"]) == receipt["socket_wait"]["sha256"], f"Socket shim changed: {label}")
    require(all(value["activation_count"] == 1 for value in receipt["socket_wait"]["actors"].values()), f"Shim activation count differs: {label}")
    summary = summarize(leg["rows"], [label])
    for key in ("mean", "median", "sd", "se"):
        require(math.isclose(summary[key], receipt[key], abs_tol=1e-8), f"Receipt summary differs: {label}/{key}")
    require(all(row["boundary_reason"] == "wire_lives_exhausted" and row["end_unix_s"] <= receipt["ended_unix_s"]
        for row in leg["rows"]), f"Incomplete game-tail evidence: {label}")
    return receipt, leg, dict(label=label, path=str(path), sha256=receipt_digest)


def historical_ids(path, expected_sha, seen, evidence):
    campaign = pinned_json(path, expected_sha)
    for source in campaign["sources"]:
        receipt = pinned_json(source["path"], source["sha256"])
        leg = validate_receipt(receipt)
        require(leg["label"] not in seen, "Duplicate historical receipt label")
        seen[leg["label"]] = {row["journal_game_id"] for row in leg["rows"]}
        evidence[leg["label"]] = dict(label=leg["label"], path=source["path"], sha256=source["sha256"])
    previous = campaign.get("historical_segment", {})
    if previous.get("path"):
        historical_ids(Path(previous["path"]), previous["sha256"], seen, evidence)


def recheck_receipt_evidence(sources):
    """Reject changed receipts before publishing; hashes describe parsed bytes."""
    for source in sources:
        require(not Path(source["path"]).is_symlink()
            and digest(source["path"]) == source["sha256"], f"Receipt changed before publication: {source['path']}")


def build(candidate_labels, iterations):
    require(1 <= len(candidate_labels) <= 2 and len(set(candidate_labels)) == len(candidate_labels), "Supply one screen or screen+confirmation")
    expected_labels = ["sidecar-gpu0-64M-screen-01", "sidecar-gpu0-64M-confirm-01"]
    require(candidate_labels == expected_labels[:len(candidate_labels)], "Use the prespecified screen, then exact-policy confirmation")
    for name, expected in VALIDATOR_HASHES.items():
        require(digest(GAME / "tools" / name) == expected, f"Official validator changed: {name}")
    plan_path = CAMPAIGN / "run-13/quality64M-composite-reference-plan.json"
    plan = pinned_json(plan_path, REFERENCE_PLAN_SHA)
    pinned = plan["reference"]
    model = pinned["protected_checkpoint"]
    require(digest(model["path"]) == model["sha256"] == REFERENCE_MODEL_SHA, "Protected32M checkpoint changed")
    require(digest(model["metadata_path"]) == model["metadata_sha256"], "Protected32M metadata bytes changed")
    raw, legs, sources = [], [], []
    for source in pinned["sources"]:
        row, leg, evidence = validate_leg(source["label"], expected_sha=REFERENCE_MODEL_SHA,
            clocks=REFERENCE_CLOCKS, receipt_sha=source["sha256"])
        raw.append(row); legs.append(leg); sources.append(evidence)
    for label in candidate_labels:
        row, leg, evidence = validate_leg(label, expected_sha=EXPECTED_SHA, clocks=CANDIDATE_CLOCKS)
        raw.append(row); legs.append(leg); sources.append(evidence)
    pairs = {}
    for a, b in itertools.combinations(range(len(raw)), 2):
        pairs[f"{raw[a]['label']} vs {raw[b]['label']}"] = compare_sidecars(raw[a], raw[b],
            iterations=iterations, verify_checkpoint=True)
    ids, receipt_evidence = {}, {}
    historical_ids(Path(pinned["campaign"]["path"]), pinned["campaign"]["sha256"], ids, receipt_evidence)
    for source in sources:
        previous = receipt_evidence.get(source["label"])
        require(previous is None or (previous["sha256"] == source["sha256"]
            and Path(previous["path"]).resolve() == Path(source["path"]).resolve()), "Historical/current receipt identity differs")
        receipt_evidence[source["label"]] = source
    historical_count = sum(map(len, ids.values()))
    for leg in legs[2:]:
        require(leg["label"] not in ids, "Candidate label already in published history")
        ids[leg["label"]] = {row["journal_game_id"] for row in leg["rows"]}
    overlaps = {}
    for a, b in itertools.combinations(ids, 2):
        count = len(ids[a] & ids[b])
        require(count == 0, f"Game IDs overlap: {a} vs {b}")
        overlaps[a + " vs " + b] = count
    reference = legs[0]["rows"] + legs[1]["rows"]
    baseline = summarize(reference, [leg["label"] for leg in legs[:2]])
    require(baseline["count"] == 236 and baseline["mean"] == pinned["mean"] and baseline["median"] == pinned["median"], "Composite reference differs")
    candidates = {leg["label"]: leg["rows"] for leg in legs[2:]}
    comparisons = {label: analyze_rows(reference, rows, baseline["source_labels"], [label], iterations) for label, rows in candidates.items()}
    pooled_candidate = [row for rows in candidates.values() for row in rows]
    return dict(schema="robotron-64M-composite-reference-analysis-v1", utc=datetime.now(timezone.utc).isoformat(),
        stage="screen" if len(candidates) == 1 else "screen_and_confirmation", sources=sources,
        receipt_byte_snapshots=list(receipt_evidence.values()),
        all_source_receipts_separately_validated=True, no_fabricated_measurement_receipt=True,
        analysis_code=dict(path=str(Path(__file__).resolve()), sha256=digest(__file__)),
        validator_hashes={name: digest(GAME / "tools" / name) for name in ("compare_sidecar_measurements.py", "compare_frozen_measurements.py")},
        policy_identity=dict(reference_sha256=REFERENCE_MODEL_SHA, candidate_sha256=EXPECTED_SHA,
            reference_saved_clocks=REFERENCE_CLOCKS, candidate_saved_clocks=CANDIDATE_CLOCKS),
        management_gate=management_gate(reference, candidates), separate_official_pair_comparisons=pairs,
        composite_reference=baseline, each_candidate_vs_composite_reference=comparisons,
        pooled_candidate_vs_composite_reference=analyze_rows(reference, pooled_candidate, baseline["source_labels"], list(candidates), iterations),
        unique_ids=dict(historical_receipts=len(ids) - len(candidates), historical_games=historical_count,
            total_receipts=len(ids), total_games=sum(map(len, ids.values())), pairwise_overlaps=overlaps),
        common_private_backend=dict(job={field: raw[0]["job"][field] for field in JOB_FIELDS},
            numeric_policy=raw[0]["numeric_policy"], runtime=raw[0]["runtime"], source_hashes=raw[0]["source_hashes"]),
        protection_or_state_changes=False, limitations=[
            "Pools are descriptive original rows from independently valid final receipts, never merged valid/complete receipts.",
            "Sequential repeated looks/checkpoint selection; bootstrap intervals are descriptive and do not correct selection or multiple comparisons.",
            "16actor-slot clusters pair labels, not emulator trajectories/RNG seeds; within-actor games may depend.",
            "Main host workload/actorcount changed since32M; unchanged private source/backend/boot does not guarantee identical host pacing/batch trajectories.",
            "No cross-backend/historicalGB300/eager/oldtransport score ratios. Confirmation is mandatory before root considers protection.",
            "Stdlib-only report: no Torch/CUDA context, launch/control, source/model/protection or managed-state mutation."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", required=True)
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(100 <= args.iterations <= 100000, "Bootstrap iterations must be100..100000")
    require(not args.output.exists(), "Refusing to overwrite analysis evidence")
    report = build(args.candidate, args.iterations)
    data = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    recheck_receipt_evidence(report["receipt_byte_snapshots"])
    with args.output.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(dict(output=str(args.output), stage=report["stage"], gate=report["management_gate"],
        comparison=report["pooled_candidate_vs_composite_reference"]["mean_ratio"])))


if __name__ == "__main__":
    main()
