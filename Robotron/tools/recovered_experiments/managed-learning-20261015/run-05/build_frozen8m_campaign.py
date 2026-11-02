"""Read-only CPU reproduction of the confirmed 8M campaign analysis.

Each original receipt is validated independently. Pools are descriptive data
analyses, never fabricated successful measurement receipts. No live state,
replay, controls, or checkpoint is modified.
"""

from datetime import datetime, timezone
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import statistics

os.environ["CUDA_VISIBLE_DEVICES"] = ""
for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[variable] = "2"
import torch


RUN = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("frozen4m_analysis", RUN / "build_frozen4m_campaign.py")
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
ROBOTRON, CAMPAIGN = previous.ROBOTRON, previous.CAMPAIGN
digest, compare, summary = previous.digest, previous.compare, previous.summary
GROUPS = {
    "original": ["frozen-reference-best10M-v2"],
    "250k": ["frozen-fresh3-eps10-cap8-250k", "frozen-fresh3-eps10-cap8-250k-confirm"],
    "1M": ["frozen-fresh3-1M", "frozen-fresh3-1M-confirm"],
    "2M": ["frozen-fresh3-2M", "frozen-fresh3-2M-confirm"],
    "4M": ["frozen-fresh3-4M", "frozen-fresh3-4M-confirm"],
    "8M": ["frozen-fresh3-8M", "frozen-fresh3-8M-confirm"],
}
METADATA_FIELDS = (
    "engine_version", "state_size", "single_frame_state_size", "frame_stack",
    "training_steps", "optimized_samples", "total_training_steps", "total_optimized_samples",
    "frame_count", "learner_frame_count", "measurement_frame_count",
    "last_target_update_samples", "last_inference_sync_samples", "lr_mode", "lr_anchor_step",
)


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, path)


def validate(label):
    data, source = previous.validate(label)
    boundary, cohort = data["boundary"], data["cohort"]
    assert not data["active"] and data["reason"] is None, label
    assert boundary["ready"] and boundary["active"], label
    assert boundary["generation"] == boundary["requested_generation"] == data["generation"], label
    assert boundary["clients"] == boundary["expected"] == boundary["acknowledged"] == 16, label
    assert not boundary["pending_client_ids"] and not boundary["replay_pending_client_ids"], label
    assert set(boundary["actor_slots"]) == set(range(16)), label
    assert cohort["closed"] and not cohort["pending_ids"] and not cohort["abandoned_ids"], label
    assert not cohort["abandonment_reasons"], label
    assert data["request"]["label"] == label, label
    assert math.isclose(data["close_ts"] - data["start_ts"], data["request"]["cohort_s"], abs_tol=1e-6), label
    assert data["clocks"]["training_steps"] == data["clocks"]["total_training_steps"], label
    assert data["clocks"]["optimized_samples"] == data["clocks"]["total_optimized_samples"], label
    for row in data["rows"]:
        assert row["measurement_generation"] == data["generation"], label
        assert row["boundary_reason"] == "wire_lives_exhausted", label
        assert row["end_unix_s"] >= row["start_unix_s"], label
        assert row["end_unix_s"] <= data["ended_unix_s"], label
        for context_name in ("start_context", "end_context"):
            assert row[context_name]["measurement_generation"] == data["generation"], label
    return data, source


def load_policy(path):
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    metadata = {name: checkpoint.get(name) for name in METADATA_FIELDS}
    assert (metadata["engine_version"], metadata["state_size"], metadata["single_frame_state_size"],
            metadata["frame_stack"]) == (28, 11128, 2782, 4)
    assert all(isinstance(metadata[name], int) and metadata[name] >= 0 for name in
               ("training_steps", "optimized_samples", "learner_frame_count", "frame_count"))
    return dict(path=str(path), sha256=digest(path), bytes=path.stat().st_size, metadata=metadata)


def main():
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    receipts, sources, pooled = {}, [], {}
    for group, labels in GROUPS.items():
        pooled[group] = []
        for label in labels:
            data, source = validate(label)
            receipts[label] = data
            sources.append(source)
            pooled[group].extend(data["rows"])
    overlaps = {}
    for left, right in itertools.combinations(receipts, 2):
        shared = set(receipts[left]["cohort"]["started_ids"]) & set(receipts[right]["cohort"]["started_ids"])
        assert not shared, (left, right)
        overlaps[left + " vs " + right] = len(shared)

    old_lineage_path = RUN / "frozen-fresh3-4M-checkpoint-lineage.json"
    old_lineage = json.loads(old_lineage_path.read_text())
    policies = old_lineage["policies"]
    for policy in policies.values():
        assert digest(Path(policy["path"])) == policy["sha256"]
    # Only the new policies need another CPU metadata read. Prior policies have
    # their earlier read provenance and are byte-verified again above.
    policies["250k"] = load_policy(ROBOTRON / "models_dqn/managed-incumbents/fresh3-250k-confirmed.pt")
    policies["8M"] = load_policy(ROBOTRON / "models_dqn/managed-checkpoints/fresh3-8M.pt")
    current_policy_snapshots = {}
    for group, labels in GROUPS.items():
        policy = policies["original_reference" if group == "original" else group]
        for label in labels:
            if receipts[label]["checkpoint_path"] is None:
                # The first recovery leg measured the current online policy;
                # its quiescent default snapshot is label.pt, not an explicit
                # checkpoint request. Verify that distinction and all clocks.
                assert label == "frozen-fresh3-eps10-cap8-250k"
                assert receipts[label]["request"]["checkpoint"] is None
                selected = previous.RECEIPTS / (label + ".pt")
                assert all(receipts[label]["clocks"][key] == policy["metadata"][key]
                           for key in ("training_steps", "optimized_samples", "learner_frame_count"))
                current_policy_snapshots[label] = dict(
                    path=str(selected), sha256=digest(selected),
                    saved_policy_clocks_equal_first_receipt=True,
                    explicit_checkpoint_request=False,
                )
            else:
                selected = Path(receipts[label]["checkpoint_path"])
            assert digest(selected) == policy["sha256"], (label, selected)
            request = receipts[label]["request"].get("checkpoint")
            if request is not None:
                assert Path(request).resolve() == selected.resolve(), label
    lineage = dict(
        utc=datetime.now(timezone.utc).isoformat(), device="cpu", threads=2,
        cuda_initialized=torch.cuda.is_initialized(),
        earlier_metadata_source=dict(path=str(old_lineage_path), sha256=digest(old_lineage_path)),
        current_policy_snapshots=current_policy_snapshots,
        policies=policies,
    )
    assert not lineage["cuda_initialized"]
    lineage_path = RUN / "frozen-fresh3-8M-checkpoint-lineage.json"
    write_json(lineage_path, lineage)

    runtimes = {}
    for name in ("4M", "8M"):
        path = RUN / ("frozen-fresh3-" + name + "-runtime.json")
        data = json.loads(path.read_text())
        first = receipts[GROUPS[name][0]]
        assert data["driver_clocks"] == first["clocks"]
        assert data["boundary"] == first["boundary"]
        assert Path(data["checkpoint"]).resolve() == Path(first["checkpoint_path"]).resolve()
        assert data["actors"] == 16 and data["socket_wait_backend"] == "select-v1" and data["socket_wait_us"] == 1000
        runtimes[name] = dict(path=str(path), sha256=digest(path), data=data)
    assert runtimes["4M"]["data"]["source_hashes"] == runtimes["8M"]["data"]["source_hashes"]

    policy = policies["8M"]
    protected = ROBOTRON / "models_dqn/managed-incumbents/fresh3-8M-confirmed.pt"
    metadata_path = protected.with_suffix(".pt.json")
    metadata = json.loads(metadata_path.read_text())
    assert digest(protected) == policy["sha256"] == metadata["sha256"]
    assert (ROBOTRON / metadata["checkpoint"]).resolve() == protected.resolve()
    assert (ROBOTRON / metadata["origin"]).resolve() == Path(policy["path"]).resolve()
    assert [(ROBOTRON / path).resolve() for path in metadata["receipts"]] == [
        (previous.RECEIPTS / (label + ".json")).resolve() for label in GROUPS["8M"]]
    assert metadata["counts"] == [receipts[label]["count"] for label in GROUPS["8M"]]
    assert metadata["means"] == [receipts[label]["mean"] for label in GROUPS["8M"]]
    assert metadata["combined_n"] == len(pooled["8M"])
    assert math.isclose(metadata["combined_mean"], statistics.mean(row["score"] for row in pooled["8M"]), abs_tol=1e-8)
    assert all(policy["metadata"][key] == value for key, value in metadata["saved_clocks"].items())

    origin = policies["original_reference"]["metadata"]
    result = dict(
        schema="frozen-policy-campaign-analysis-v1", stage="confirmed",
        created_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
        analysis_code=dict(path=str(Path(__file__).resolve()), sha256=digest(Path(__file__)),
                           reused_helpers_path=str(RUN / "build_frozen4m_campaign.py"),
                           reused_helpers_sha256=digest(RUN / "build_frozen4m_campaign.py")),
        validation=dict(
            each_receipt_separately_validated=True, no_fabricated_merged_receipt=True,
            receipt_count=len(receipts), total_disjoint_games=sum(len(rows) for rows in pooled.values()),
            pairwise_game_id_overlap_counts=overlaps,
            all_cohorts_cover_actor_slots_0_through_15=True,
            each_leg_pending_and_abandoned_zero=True,
            each_leg_optimizer_samples_and_learner_clocks_constant=True,
            boundary_and_context_generations_match=True,
            whole_game_end_reason="wire_lives_exhausted",
            shared_recorded_protocol=dict(epsilon=0, expert_ratio=0, difficulty=5, first_play_level=1, actors=16),
        ),
        checkpoint_lineage=lineage,
        clock_interpretation="Saved checkpoint clocks identify the installed policy. Measurement receipt clocks identify a later online learner paused for inference-only evaluation. Different driver clocks across the two legs do not indicate different installed policies.",
        runtime_provenance=dict(
            first_leg_sidecars=runtimes, matching_wait_backend="select-v1",
            matching_wait_us=1000, matching_actor_count=16,
            lua_native_wait_and_wrapper_source_hashes_identical=True,
            device_precision_provenance="Parent session provenance: both stages used the production GB300 FP32 inference backend. First-leg sidecars record pacing, actor count and source hashes; confirmation receipts do not independently persist device/precision/backend fields.",
            confirmation_backend_provenance="Session continuity: the same 16-actor select-v1/1000us fleet remained active within each stage. Retain this qualification instead of treating unrecorded fields as independently verified.",
        ),
        cohort_summaries={label: dict(count=data["count"], mean=data["mean"], median=data["median"],
            se=data["se"], driver_clocks=data["clocks"], generation=data["generation"],
            start_ts=data["start_ts"], close_ts=data["close_ts"], ended_unix_s=data["ended_unix_s"])
            for label, data in receipts.items()},
        descriptive_pools={name: summary(rows, GROUPS[name]) for name, rows in pooled.items()},
        comparisons={"8M_vs_" + name: compare(pooled[name], pooled["8M"], GROUPS[name], GROUPS["8M"])
                     for name in ("4M", "2M", "1M", "250k", "original")},
        first_leg_vs_4M=compare(pooled["4M"], receipts[GROUPS["8M"][0]]["rows"], GROUPS["4M"], [GROUPS["8M"][0]]),
        confirmation_leg_vs_4M=compare(pooled["4M"], receipts[GROUPS["8M"][1]]["rows"], GROUPS["4M"], [GROUPS["8M"][1]]),
        first_leg_vs_confirmation=compare(receipts[GROUPS["8M"][0]]["rows"], receipts[GROUPS["8M"][1]]["rows"],
                                          [GROUPS["8M"][0]], [GROUPS["8M"][1]]),
        policy_identity=dict(
            source_checkpoint=policy["path"], sha256=policy["sha256"], saved_policy_clocks=policy["metadata"],
            same_explicit_checkpoint_requested_by_both_8M_legs=True,
            protected_copy=dict(path=str(protected), sha256=digest(protected), metadata_path=str(metadata_path),
                metadata_sha256=digest(metadata_path), counts_means_and_saved_clocks_match=True),
            live_driver_ahead_of_selected_policy_by_leg={label: {
                "training_steps": receipts[label]["clocks"]["training_steps"] - policy["metadata"]["training_steps"],
                "optimized_samples": receipts[label]["clocks"]["optimized_samples"] - policy["metadata"]["optimized_samples"],
                "learner_frames": receipts[label]["clocks"]["learner_frame_count"] - policy["metadata"]["learner_frame_count"],
            } for label in GROUPS["8M"]},
        ),
        saved_policy_progress={name: dict(
            postwarmup_learner_frames=value["metadata"]["learner_frame_count"] - 4629023,
            optimized_samples_since_origin=value["metadata"]["optimized_samples"] - origin["optimized_samples"],
            optimizer_steps_since_origin=value["metadata"]["training_steps"] - origin["training_steps"],
        ) for name, value in policies.items() if name != "original_reference"},
        limitations=[
            "Descriptive bootstrap sensitivity intervals: repeated checkpoint looks, policy selection and multiple comparisons are not corrected. These are not a formal promotion rule.",
            "Game resampling approximates games as independent. Paired actor-slot whole-cluster resampling has only 16 clusters; it pairs slot labels, not individual games, trajectories or RNG seeds.",
            "All controls are historical and reused, not randomized interleaved controls. Host pacing, emulator RNG and inference batching can drift even with matching declared backend and source hashes.",
            "4M and 8M have matching first-leg select-v1/1000us/16-actor sidecars. Confirmation device/precision/backend equality relies on session continuity rather than fields embedded in each final receipt.",
            "Original, 250k, 1M and 2M used earlier busy socket polling. Packet and fixed-emulated-time tests support protocol equivalence, but those comparisons retain a pacing change caveat.",
            "The 8M cohorts admitted starters for 180s and 240s. Every admitted tail completed; counts differ because of admission windows and game duration, not best-N truncation.",
            "These are production-backend measurements. Future eager inference on GPU0 requires a fresh same-backend baseline and candidate; its results must not silently be merged into these pools.",
            "Each descriptive pool combines separately valid complete same-policy cohorts. No synthetic successful measurement receipt is created or passed to promotion validation.",
        ],
        judgment="Both independently complete 8M legs exceed the protected 4M pooled mean. The confirmed 8M pool and game/paired-slot sensitivity intervals support practical promotion under the declared common production backend. Scores continue improving, so this analysis provides no reason to change learning knobs now.",
    )
    output = CAMPAIGN / "frozen-fresh3-8M-confirmed-campaign.json"
    write_json(output, result)
    print(output)
    for name, comparison in result["comparisons"].items():
        print(name, comparison["candidate"]["count"], comparison["candidate"]["mean"],
              comparison["relative_change_pct"], comparison["game_bootstrap"]["mean_ratio_ci"],
              comparison["paired_slot_bootstrap"]["mean_ratio_ci"],
              "positive_slots", comparison["slots_with_positive_mean_contrast"])


if __name__ == "__main__":
    main()
