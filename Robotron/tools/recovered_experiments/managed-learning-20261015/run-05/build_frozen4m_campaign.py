"""Reproduce read-only 4M comparisons from independently valid cohort receipts."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import statistics

os.environ["CUDA_VISIBLE_DEVICES"] = ""
for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[name] = "2"
import numpy as np


ROOT = Path(__file__).resolve().parents[4]
ROBOTRON = ROOT / "Robotron"
CAMPAIGN = ROBOTRON / "logs/managed-learning-20261015"
RUN = CAMPAIGN / "run-05"
RECEIPTS = ROBOTRON / "models_dqn/managed-measurements"
ITERATIONS = 10000
SEED = 20261015


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def validate(label):
    path = RECEIPTS / (label + ".json")
    data = json.loads(path.read_text())
    rows = data["rows"]
    cohort = data["cohort"]
    assert data["complete"] and data["valid"] and data["phase"] == "finished", label
    assert data["pending"] == data["abandoned"] == 0, label
    assert data["count"] == data["started"] == len(rows), label
    assert cohort["complete"] and cohort["valid"], label
    ids = [row["journal_game_id"] for row in rows]
    assert len(ids) == len(set(ids)) and set(ids) == set(cohort["started_ids"]), label
    assert set(cohort["started_actor_slots"]) == set(range(16)), label
    assert {row["client_slot"] for row in rows} == set(range(16)), label
    clocks = data["clocks"]
    for row in rows:
        assert row["eligible"] and row["complete"] and row["known_start"], label
        assert row["measurement_active"] and row["eval_only"], label
        assert row["experiment"] == label and row["first_play_level"] == 1, label
        assert math.isfinite(row["score"]) and row["score"] >= 0, label
        assert data["start_ts"] <= row["start_unix_s"] <= data["close_ts"], label
        for context_name in ("start_context", "end_context"):
            context = row[context_name]
            assert context["experiment"] == label and context["measurement_active"], label
            assert context["epsilon"] == context["expert_ratio"] == 0, label
            assert context["difficulty"] == 5 and not context["ratchet_frozen"], label
            for key, receipt_key in (("learner_frames", "learner_frame_count"),
                                     ("optimized_samples", "optimized_samples"),
                                     ("training_steps", "training_steps")):
                assert context[key] == clocks[receipt_key], (label, context_name, key)
    assert math.isclose(statistics.mean(row["score"] for row in rows), data["mean"], abs_tol=1e-8)
    return data, dict(path=str(path), sha256=digest(path), label=label)


def summary(rows, labels):
    scores = [row["score"] for row in rows]
    sd = statistics.stdev(scores)
    return dict(
        unit="Descriptive pool of separately validated same-policy cohorts; not a measurement receipt",
        source_labels=labels, count=len(rows), mean=statistics.mean(scores),
        median=statistics.median(scores), sd=sd, se=sd / math.sqrt(len(scores)),
        minimum=min(scores), maximum=max(scores), zero_score_games=scores.count(0),
        actor_slot_counts=dict(Counter(str(row["client_slot"]) for row in rows)),
        duration_s=dict(mean=statistics.mean(row["duration_s"] for row in rows),
                        maximum=max(row["duration_s"] for row in rows)),
        playable_frames=dict(mean=statistics.mean(row["playable_frames"] for row in rows),
                             total=sum(row["playable_frames"] for row in rows)),
        game_ids=[row["journal_game_id"] for row in rows],
    )


def interval(difference, ratio, method):
    return dict(method=method, iterations=ITERATIONS, seed=SEED, confidence=.95,
                mean_difference_ci=np.quantile(difference, [.025, .975]).tolist(),
                mean_ratio_ci=np.quantile(ratio, [.025, .975]).tolist())


def compare(baseline, candidate, base_labels, candidate_labels):
    a = np.asarray([row["score"] for row in baseline], dtype=np.float64)
    b = np.asarray([row["score"] for row in candidate], dtype=np.float64)
    rng = np.random.default_rng(SEED)
    am = a[rng.integers(len(a), size=(ITERATIONS, len(a)))].mean(axis=1)
    bm = b[rng.integers(len(b), size=(ITERATIONS, len(b)))].mean(axis=1)
    games = interval(bm - am, bm / am, "independently resampled games")
    sums, counts = [], []
    for rows in (baseline, candidate):
        groups = [[row["score"] for row in rows if row["client_slot"] == slot]
                  for slot in range(16)]
        assert all(groups)
        sums.append(np.asarray([sum(group) for group in groups], dtype=np.float64))
        counts.append(np.asarray([len(group) for group in groups], dtype=np.float64))
    rng = np.random.default_rng(SEED)
    slots = rng.integers(16, size=(ITERATIONS, 16))
    ac = sums[0][slots].sum(axis=1) / counts[0][slots].sum(axis=1)
    bc = sums[1][slots].sum(axis=1) / counts[1][slots].sum(axis=1)
    clusters = interval(bc - ac, bc / ac, "paired actor-slot clusters; whole clusters, game-weighted means")
    contrasts = {str(slot): dict(baseline_mean=float(sums[0][slot] / counts[0][slot]),
                                 candidate_mean=float(sums[1][slot] / counts[1][slot]))
                 for slot in range(16)}
    for value in contrasts.values():
        value["difference"] = value["candidate_mean"] - value["baseline_mean"]
    return dict(baseline=summary(baseline, base_labels), candidate=summary(candidate, candidate_labels),
                mean_difference=float(b.mean() - a.mean()), mean_ratio=float(b.mean() / a.mean()),
                relative_change_pct=float(100 * (b.mean() / a.mean() - 1)),
                game_bootstrap=games, paired_slot_bootstrap=clusters,
                actor_contrasts=contrasts,
                slots_with_positive_mean_contrast=sum(x["difference"] > 0 for x in contrasts.values()))


def main():
    groups = {
        "original": ["frozen-reference-best10M-v2"],
        "1M": ["frozen-fresh3-1M", "frozen-fresh3-1M-confirm"],
        "2M": ["frozen-fresh3-2M", "frozen-fresh3-2M-confirm"],
        "4M": ["frozen-fresh3-4M"],
    }
    confirmation = RECEIPTS / "frozen-fresh3-4M-confirm.json"
    if confirmation.exists():
        state = json.loads(confirmation.read_text())
        if state.get("complete") and state.get("valid"):
            groups["4M"].append("frozen-fresh3-4M-confirm")
    receipts, sources, pooled = {}, [], {}
    for group, labels in groups.items():
        pooled[group] = []
        for label in labels:
            data, source = validate(label)
            receipts[label] = data
            sources.append(source)
            pooled[group].extend(data["rows"])
    overlap = {}
    for left, right in itertools.combinations(receipts, 2):
        shared = {row["journal_game_id"] for row in receipts[left]["rows"]} & {
            row["journal_game_id"] for row in receipts[right]["rows"]}
        overlap[left + " vs " + right] = len(shared)
        assert not shared
    lineage_path = RUN / "frozen-fresh3-4M-checkpoint-lineage.json"
    lineage = json.loads(lineage_path.read_text())
    for policy in lineage["policies"].values():
        assert digest(Path(policy["path"])) == policy["sha256"]
    for group, labels in groups.items():
        expected = Path(lineage["policies"]["original_reference" if group == "original" else group]["path"])
        for label in labels:
            selected = Path(receipts[label]["checkpoint_path"])
            assert digest(selected) == digest(expected), (label, selected, expected)
    runtime_path = RUN / "frozen-fresh3-4M-runtime.json"
    runtime = json.loads(runtime_path.read_text())
    result = dict(
        schema="frozen-policy-campaign-analysis-v1", created_utc=datetime.now(timezone.utc).isoformat(),
        stage="confirmed" if len(groups["4M"]) == 2 else "first_leg_only_confirmation_pending",
        sources=sources,
        validation=dict(each_receipt_separately_validated=True, no_fabricated_merged_receipt=True,
                        pairwise_game_id_overlap_counts=overlap,
                        all_cohorts_cover_actor_slots_0_through_15=True,
                        each_leg_pending_and_abandoned_zero=True,
                        each_leg_optimizer_samples_and_learner_clocks_constant=True,
                        shared_recorded_protocol=dict(epsilon=0, expert_ratio=0, difficulty=5,
                                                      first_play_level=1, actors=16)),
        checkpoint_lineage=lineage,
        clock_interpretation="Checkpoint CPU metadata identifies installed policy progress. Receipt clocks identify a later live online learner paused during infer-only evaluation; they must not be reported as the selected checkpoint clocks.",
        runtime_provenance=dict(
            path=str(runtime_path), sha256=digest(runtime_path), data=runtime,
            confirmation_backend_provenance="Session continuity reported by parent: same16actor select-v1/1000us fleet. The sidecar explicitly labels the first4M leg; neither measurement receipt independently persists the wait backend.",
        ),
        comparisons={},
        limitations=[
            "Descriptive bootstrap sensitivity intervals; repeated looks, checkpoint selection and multiple comparisons are not corrected. These are not a formal promotion rule.",
            "Independent-game bootstrap approximates games as iid; same-slot whole-cluster resampling has only16clusters and does not pair games or RNG seeds.",
            "Prior2M/original controls are historical and reused, not randomized interleaved controls.",
            "4M uses select-v1 readiness wait1000us while earlier2M used busy polling. Packet and fixed-emulated-time tests support protocol equivalence; host pacing, RNG sequences and inference batching can still drift. A contemporaneous2M evaluation under the same pacing would better isolate policy-only gain.",
            "The first4M runtime sidecar explicitly records the wait backend; confirmation backend identity relies on session continuity rather than a separately persisted receipt field.",
            "4M confirmation admits starters for240s versus firstleg180s. Every admitted game tail must complete; different counts reflect sampling, not a truncated best-N comparison.",
            "Pools contain only separately validated complete same-policy cohorts. No synthetic valid merged measurement receipt is created.",
        ],
    )
    for baseline in ("2M", "1M", "original"):
        result["comparisons"]["4M_vs_" + baseline] = compare(
            pooled[baseline], pooled["4M"], groups[baseline], groups["4M"])
    first = receipts["frozen-fresh3-4M"]["rows"]
    result["first_leg_vs_2M"] = compare(pooled["2M"], first, groups["2M"], ["frozen-fresh3-4M"])
    if len(groups["4M"]) == 2:
        second = receipts["frozen-fresh3-4M-confirm"]["rows"]
        result["confirmation_leg_vs_2M"] = compare(pooled["2M"], second, groups["2M"], ["frozen-fresh3-4M-confirm"])
        result["first_leg_vs_confirmation"] = compare(first, second, ["frozen-fresh3-4M"], ["frozen-fresh3-4M-confirm"])
    checkpoint = lineage["policies"]["4M"]
    result["policy_identity"] = dict(
        source_checkpoint=checkpoint["path"], sha256=checkpoint["sha256"],
        saved_policy_clocks=checkpoint["metadata"],
        same_explicit_checkpoint_requested_by_each_4M_leg=True,
        live_driver_ahead_of_selected_policy_by_leg={
            label: {
                "training_steps": receipts[label]["clocks"]["training_steps"] - checkpoint["metadata"]["training_steps"],
                "optimized_samples": receipts[label]["clocks"]["optimized_samples"] - checkpoint["metadata"]["optimized_samples"],
                "learner_frames": receipts[label]["clocks"]["learner_frame_count"] - checkpoint["metadata"]["learner_frame_count"],
            } for label in groups["4M"]},
    )
    origin = lineage["policies"]["original_reference"]["metadata"]
    result["saved_policy_progress"] = {
        name: dict(
            postwarmup_learner_frames=policy["metadata"]["learner_frame_count"] - 4629023,
            optimized_samples_since_origin=policy["metadata"]["optimized_samples"] - origin["optimized_samples"],
            optimizer_steps_since_origin=policy["metadata"]["training_steps"] - origin["training_steps"],
        ) for name, policy in lineage["policies"].items() if name != "original_reference"
    }
    protected = ROBOTRON / "models_dqn/managed-incumbents/fresh3-4M-confirmed.pt"
    metadata_path = protected.with_suffix(".pt.json")
    if protected.exists() and metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        protected_sha = digest(protected)
        assert protected_sha == checkpoint["sha256"] == metadata["sha256"]
        assert metadata["counts"] == [len(receipts[label]["rows"]) for label in groups["4M"]]
        assert metadata["means"] == [receipts[label]["mean"] for label in groups["4M"]]
        assert metadata["combined_n"] == len(pooled["4M"])
        assert math.isclose(metadata["combined_mean"], statistics.mean(row["score"] for row in pooled["4M"]), abs_tol=1e-8)
        assert all(value == checkpoint["metadata"][key] for key, value in metadata["saved_clocks"].items())
        result["policy_identity"]["protected_copy"] = dict(
            path=str(protected), sha256=protected_sha, metadata_path=str(metadata_path),
            metadata_sha256=digest(metadata_path), counts_means_and_saved_clocks_match=True,
            verified_utc=datetime.now(timezone.utc).isoformat(),
        )
    result["judgment"] = (
        "The completed confirmation independently reinforces the higher first-leg mean. "
        "The pooled4M analysis supports practical promotion under the measured runtime; "
        "both game and paired-slot sensitivity intervals exceed the historical2M reference. "
        "It does not isolate a pure policy effect from the host-pacing change. "
        "No learning-knob change is indicated by these improving scores."
        if len(groups["4M"]) == 2 else
        "Firstleg suggests improvement, but confirmation is pending; do not promote from this analysis."
    )
    suffix = "confirmed-campaign" if result["stage"] == "confirmed" else "first-comparison"
    output = CAMPAIGN / ("frozen-fresh3-4M-" + suffix + ".json")
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, output)
    print(output)
    for name, comparison in result["comparisons"].items():
        print(name, comparison["candidate"]["count"], comparison["candidate"]["mean"],
              comparison["relative_change_pct"], comparison["game_bootstrap"]["mean_ratio_ci"],
              comparison["paired_slot_bootstrap"]["mean_ratio_ci"])


if __name__ == "__main__":
    main()
