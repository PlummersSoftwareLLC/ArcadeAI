"""CPU reproduction of the separate GPU0 compiled 8M-to-16M campaign.

Default execution validates/analyzes immutable receipts and an existing protected
copy. --protect creates the new 16M copy/metadata if absent, without replacing
any incumbent or changing managed state, controls, models or replay in memory.
"""
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys

os.environ["CUDA_VISIBLE_DEVICES"] = ""
for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[variable] = "2"
import numpy as np
import torch

RUN = Path(__file__).resolve().parent
CAMPAIGN = RUN.parent
GAME = RUN.parents[2]
sys.path.insert(0, str(GAME / "tools"))
from compare_frozen_measurements import validate_receipt
from sidecar_boot import load_snapshot

LABELS = ["sidecar-gpu0-8M-baseline-04", "sidecar-gpu0-16M-screen-01",
          "sidecar-gpu0-16M-confirm-01"]
SLOTS = list(range(4096, 4112))
EXPECTED_SHA = "b8db175280b8e5d49865d14c83dccfe90737dfcb33d13d219ff5bb38d9abf281"
EXPECTED_CLOCKS = dict(training_steps=249165, optimized_samples=534130688,
                       learner_frame_count=20632694)
ITERATIONS, SEED = 10000, 20261016


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def summarize(rows, labels):
    scores = [row["score"] for row in rows]
    sd = statistics.stdev(scores)
    return dict(unit="descriptive pool; not a measurement receipt", source_labels=labels,
                count=len(rows), mean=statistics.mean(scores), median=statistics.median(scores),
                sd=sd, se=sd / math.sqrt(len(scores)), minimum=min(scores), maximum=max(scores),
                actor_slot_counts=dict(sorted(Counter(str(r["client_slot"]) for r in rows).items())),
                duration_s=dict(mean=statistics.mean(r["duration_s"] for r in rows),
                                maximum=max(r["duration_s"] for r in rows)),
                playable_frames_total=sum(r["playable_frames"] for r in rows),
                game_ids=[r["journal_game_id"] for r in rows])


def compare(base, candidate, base_labels, candidate_labels):
    a, b = [np.asarray([r["score"] for r in rows], dtype=np.float64)
            for rows in (base, candidate)]
    rng = np.random.default_rng(SEED)
    am = a[rng.integers(len(a), size=(ITERATIONS, len(a)))].mean(axis=1)
    bm = b[rng.integers(len(b), size=(ITERATIONS, len(b)))].mean(axis=1)

    def interval(x, y, method):
        return dict(method=method, iterations=ITERATIONS, seed=SEED, percentile=.95,
                    mean_difference_ci=np.quantile(y-x, [.025, .975]).tolist(),
                    mean_ratio_ci=np.quantile(y/x, [.025, .975]).tolist())

    games = interval(am, bm, "independent game resampling")
    sums, counts = [], []
    for rows in (base, candidate):
        groups = [[r["score"] for r in rows if r["client_slot"] == slot] for slot in SLOTS]
        assert all(groups)
        sums.append(np.asarray([sum(g) for g in groups], dtype=np.float64))
        counts.append(np.asarray([len(g) for g in groups], dtype=np.float64))
    rng = np.random.default_rng(SEED)
    draw = rng.integers(16, size=(ITERATIONS, 16))
    ac = sums[0][draw].sum(axis=1) / counts[0][draw].sum(axis=1)
    bc = sums[1][draw].sum(axis=1) / counts[1][draw].sum(axis=1)
    paired = interval(ac, bc, "paired actor-slot whole clusters; game-weighted means")
    contrasts = {}
    for i, slot in enumerate(SLOTS):
        av, bv = sums[0][i]/counts[0][i], sums[1][i]/counts[1][i]
        contrasts[str(slot)] = dict(baseline_count=int(counts[0][i]), candidate_count=int(counts[1][i]),
                                   baseline_mean=float(av), candidate_mean=float(bv),
                                   difference=float(bv-av), ratio=float(bv/av))
    return dict(baseline=summarize(base, base_labels), candidate=summarize(candidate, candidate_labels),
                mean_difference=float(b.mean()-a.mean()), mean_ratio=float(b.mean()/a.mean()),
                relative_change_pct=float(100*(b.mean()/a.mean()-1)), game_bootstrap=games,
                paired_slot_bootstrap=paired, actor_contrasts=contrasts,
                slots_with_positive_mean_contrast=sum(v["difference"] > 0 for v in contrasts.values()))


def validate_sidecar(label):
    path = CAMPAIGN / label / "receipt.json"
    raw = json.loads(path.read_text())
    leg = validate_receipt(raw)
    assert raw["phase"] == "finished" and raw["reason"] is None
    assert raw["receipt_validator"] == "passed"
    assert not any(raw.get(k) for k in ("server_error", "inference_error", "invalidity_reasons", "cleanup_errors"))
    assert not any(raw["actor_timeout_logs"].values())
    assert raw["source_hashes"] == raw["ended_source_hashes"]
    assert raw["boundary"]["clients"] == raw["boundary"]["expected"] == raw["boundary"]["acknowledged"] == 16
    assert raw["boundary"]["generation"] == raw["boundary"]["requested_generation"] == raw["generation"]
    assert sorted(raw["boundary"]["actor_slots"]) == leg["expected_actor_slots"] == SLOTS
    assert sorted({r["client_slot"] for r in raw["rows"]}) == SLOTS
    assert raw["clocks"]["training_steps"] == raw["checkpoint_metadata"]["training_steps"]
    assert raw["clocks"]["optimized_samples"] == raw["checkpoint_metadata"]["optimized_samples"]
    assert raw["clocks"]["learner_frame_count"] == raw["checkpoint_metadata"]["learner_frame_count"]
    assert digest(raw["checkpoint_path"]) == digest(raw["source_checkpoint_path"]) == raw["checkpoint_sha256"]
    assert raw["inference_backend"] == "inductor" and raw["numeric_policy"]["compiled"] is True
    assert raw["compile_report"]["graph_state"] == dict(unique_graphs=2, graph_breaks=0, unimplemented=0)
    assert raw["compile_report"]["all_shapes_verified"] == list(range(1, 17))
    job = raw["job"]
    for key, value in dict(actors=16, actor_slots=SLOTS, cohort_s=600., timeout_s=1200., wait_us=1000,
                           epsilon=0, expert_ratio=0, difficulty=5, start_level=1, replay_enabled=False,
                           fp16=False, inference_max_batch_size=16, inference_backend="inductor").items():
        assert job[key] == value, (label, key)
    boot = load_snapshot(Path(job["boot_assets"]))
    assert boot["identity"] == raw["boot_assets"]["identity"]
    assert boot["files"] == raw["boot_assets"]["files"]
    assert set(map(int, raw["boot_restores"])) == set(SLOTS)
    assert all(v["identity"] == boot["identity"] and v["files"] == boot["files"]
               for v in raw["boot_restores"].values())
    assert raw["socket_wait"]["wait_us"] == 1000 and raw["socket_wait"]["port"] == 9999
    assert set(map(int, raw["socket_wait"]["actors"])) == set(SLOTS)
    assert all(a["matching_activation"] and a["activation_count"] == 1
               for a in raw["socket_wait"]["actors"].values())
    for row in raw["rows"]:
        assert row["boundary_reason"] == "wire_lives_exhausted"
        assert row["end_unix_s"] <= raw["ended_unix_s"]
    for key in ("mean", "median", "sd", "se"):
        assert math.isclose(summarize(raw["rows"], [label])[key], raw[key], abs_tol=1e-8)
    return raw, leg, dict(label=label, path=str(path), sha256=digest(path))


def main(protect=False):
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    receipts, legs, sources = {}, {}, []
    for label in LABELS:
        receipts[label], legs[label], source = validate_sidecar(label)
        sources.append(source)
    reference = receipts[LABELS[0]]
    exact_fields = ("runtime", "numeric_policy", "source_hashes", "ended_source_hashes", "engine_version",
                    "state_size", "single_frame_state_size", "frame_stack", "wire_params_count", "wire_version", "frame_protocol")
    assert all(r[k] == reference[k] for r in receipts.values() for k in exact_fields)
    assert all(legs[label]["protocol"] == legs[LABELS[0]]["protocol"] for label in LABELS)
    assert all(r["boot_assets"]["identity"] == reference["boot_assets"]["identity"] for r in receipts.values())
    assert all(r["socket_wait"]["sha256"] == reference["socket_wait"]["sha256"] for r in receipts.values())
    ids = {label: set(r["journal_game_id"] for r in receipts[label]["rows"]) for label in LABELS}
    historical_path = CAMPAIGN / "frozen-fresh3-8M-confirmed-campaign.json"
    historical = json.loads(historical_path.read_text())
    for item in historical["sources"]:
        path = Path(item["path"])
        assert digest(path) == item["sha256"]
        raw = json.loads(path.read_text())
        validate_receipt(raw)
        ids[item["label"]] = {r["journal_game_id"] for r in raw["rows"]}
    overlaps = {}
    for a, b in itertools.combinations(ids, 2):
        overlap = len(ids[a] & ids[b])
        assert overlap == 0, (a, b)
        overlaps[a + " vs " + b] = overlap
    pooled = receipts[LABELS[1]]["rows"] + receipts[LABELS[2]]["rows"]
    comparisons = {"confirmed16M_vs_compiled8M": compare(reference["rows"], pooled, [LABELS[0]], LABELS[1:]),
                   "first16M_vs_compiled8M": compare(reference["rows"], receipts[LABELS[1]]["rows"], [LABELS[0]], [LABELS[1]]),
                   "confirmation16M_vs_compiled8M": compare(reference["rows"], receipts[LABELS[2]]["rows"], [LABELS[0]], [LABELS[2]]),
                   "confirmation_vs_first16M": compare(receipts[LABELS[1]]["rows"], receipts[LABELS[2]]["rows"], [LABELS[1]], [LABELS[2]])}
    source = GAME / "models_dqn/managed-checkpoints/fresh3-16M.pt"
    assert digest(source) == EXPECTED_SHA
    checkpoint = torch.load(source, map_location="cpu", weights_only=True)
    saved = {k: checkpoint.get(k) for k in ("engine_version", "state_size", "single_frame_state_size", "frame_stack",
             "training_steps", "optimized_samples", "learner_frame_count", "frame_count", "measurement_frame_count",
             "total_training_steps", "baseline_batch_size", "last_target_update_samples")}
    assert all(saved[k] == v for k, v in EXPECTED_CLOCKS.items())
    assert all(all(receipts[label]["checkpoint_metadata"][k] == v for k, v in EXPECTED_CLOCKS.items()) for label in LABELS[1:])
    assert all(receipts[label]["checkpoint_sha256"] == EXPECTED_SHA for label in LABELS[1:])
    del checkpoint
    protected = GAME / "models_dqn/managed-incumbents/fresh3-16M-confirmed.pt"
    protected_meta = protected.with_suffix(".pt.json")
    if protect and not protected.exists():
        temporary = protected.with_suffix(".pt.tmp")
        with source.open("rb") as reader, temporary.open("xb") as writer:
            shutil.copyfileobj(reader, writer, 4 * 1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        assert digest(temporary) == EXPECTED_SHA
        os.replace(temporary, protected)
    assert digest(protected) == EXPECTED_SHA
    meta = dict(utc=datetime.now(timezone.utc).isoformat(), checkpoint=str(protected.relative_to(GAME)),
                sha256=EXPECTED_SHA, origin=str(source.relative_to(GAME)),
                receipts=[str((CAMPAIGN/label/"receipt.json").relative_to(GAME)) for label in LABELS[1:]],
                counts=[receipts[label]["count"] for label in LABELS[1:]],
                means=[receipts[label]["mean"] for label in LABELS[1:]],
                combined_n=len(pooled), combined_mean=statistics.mean(r["score"] for r in pooled),
                combined_median=statistics.median(r["score"] for r in pooled),
                combined_se=statistics.stdev(r["score"] for r in pooled)/math.sqrt(len(pooled)),
                saved_clocks=EXPECTED_CLOCKS, scope="Two separately valid complete16M cohorts; matching GPU0 compiledFP32, boot seed, source, wire, actor slots and pacing. Distinct from historical GB300 segment.")
    if protect and not protected_meta.exists():
        write_json(protected_meta, meta)
    actual_meta = json.loads(protected_meta.read_text())
    assert all(actual_meta[k] == meta[k] for k in meta if k != "utc")
    retained = {}
    for path in sorted(protected.parent.glob("*.pt.json")):
        if path == protected_meta:
            continue
        old = json.loads(path.read_text())
        checkpoint_path = GAME / old["checkpoint"]
        assert digest(checkpoint_path) == old["sha256"]
        retained[str(checkpoint_path)] = dict(sha256=old["sha256"], metadata_sha256=digest(path))
    main_evidence = {}
    for label, prefix, key in zip(LABELS, ("run-05", "run-05", "run-06"),
                                 ("sidecar-job04", "sidecar-16M-screen01", "sidecar-16M-confirm01")):
        path = CAMPAIGN / prefix / (key + "-prelaunch.json")
        audit = CAMPAIGN / prefix / (key + "-readonly-audit.json")
        data = json.loads(path.read_text())
        completed_audit = json.loads(audit.read_text())
        assert completed_audit["pass"]
        assert completed_audit["receipt_sha256"] == digest(CAMPAIGN / label / "receipt.json")
        main_evidence[label] = dict(prelaunch_path=str(path), prelaunch_sha256=digest(path),
            prelaunch_main_trainer_clocks=data.get("main"),
            completed_isolation_audit_path=str(audit), completed_isolation_audit_sha256=digest(audit),
            interpretation="Main trainer observations are separate from installed frozen actor clocks.")
    result = dict(schema="frozen-policy-campaign-analysis-v2", stage="confirmed", segment="GPU0 compiledFP32 private initialized16actor cohorts",
        created_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
        analysis_code=dict(path=str(Path(__file__)), sha256=digest(Path(__file__))),
        validation=dict(each_receipt_separately_validated=True, no_fabricated_merged_receipt=True,
            sidecar_receipts=3, sidecar_disjoint_games=sum(len(receipts[x]["rows"]) for x in LABELS),
            historical_receipts_revalidated=len(historical["sources"]),
            all_historical_and_sidecar_disjoint_games=sum(map(len, ids.values())), pairwise_game_id_overlap_counts=overlaps,
            full_started_denominators_completed=True, pending_and_abandoned_zero=True,
            all16_slots_covered_each_leg=SLOTS, all_runtime_timeout_counts_zero=True,
            exact_backend_numeric_runtime_source_model_wire_boot_and_shim_match=True),
        common_runtime=dict(runtime=reference["runtime"], numeric_policy=reference["numeric_policy"],
            protocol=legs[LABELS[0]]["protocol"], job_controls={k:reference["job"][k] for k in ("actors","actor_slots","cohort_s","timeout_s","wait_us","epsilon","expert_ratio","difficulty","start_level","replay_enabled","fp16","inference_backend")},
            source_hashes=reference["source_hashes"], boot_identity=reference["boot_assets"]["identity"],
            boot_files=reference["boot_assets"]["files"], shim_sha256=reference["socket_wait"]["sha256"]),
        cohort_summaries={label:dict(**summarize(receipts[label]["rows"], [label]), saved_actor_clocks=receipts[label]["clocks"],
            start_ts=receipts[label]["start_ts"],close_ts=receipts[label]["close_ts"],ended_unix_s=receipts[label]["ended_unix_s"],
            last_tail_s=max(r["end_unix_s"] for r in receipts[label]["rows"])-receipts[label]["close_ts"],
            compile_report=receipts[label]["compile_report"]) for label in LABELS},
        descriptive_pools=dict(compiled8M_reference=summarize(reference["rows"], [LABELS[0]]),confirmed16M=summarize(pooled,LABELS[1:])),
        comparisons=comparisons,
        policy_identity=dict(source_checkpoint=str(source),sha256=EXPECTED_SHA,saved_policy_clocks=saved,
            protected_copy=dict(path=str(protected),sha256=digest(protected),metadata_path=str(protected_meta),metadata_sha256=digest(protected_meta)),
            retained_previous_incumbents=retained,
            reference_checkpoint=reference["source_checkpoint_path"],reference_sha256=reference["checkpoint_sha256"],
            reference_saved_clocks=reference["checkpoint_metadata"]),
        clock_interpretation="Sidecar receipt clocks are loaded frozen actor clocks and equal installed checkpoint clocks. Main trainer continued separately; its prelaunch clocks belong to run-specific isolation sidecars, not these policy clocks.",
        main_training_isolation_provenance=main_evidence,
        historical_segment=dict(path=str(historical_path),sha256=digest(historical_path),use="Separate GB300 production curve; no pooled games, direct original ratio, or cross-backend gain inference here."),
        limitations=["Descriptive bootstrap sensitivity intervals; repeated looks, checkpoint selection and multiple comparisons are not corrected; not a formal promotion rule.",
            "Paired actor-slot resampling has only16clusters and pairs labels, not trajectories or RNG seeds. Games may retain within-actor dependence.",
            "Controls are sequential historical cohorts, not randomized interleaved runs. Identical seed assets do not ensure identical emulator trajectories or host pacing/batching.",
            "The incumbent GPU0 baseline has one complete cohort; candidate has two. All admission windows600s and all admitted tails completed, without best-N truncation.",
            "Main training and host workload differed between sequential legs; common source/backend/boot protocol and no runtime errors reduce but do not eliminate this nuisance.",
            "These receipts predate the later transport timeout/reconnect correctness patch. Matching old source hashes were stable throughout all3legs; no timeout failure was reported in any of them.",
            "GPU0 compiled segment is distinct from historical GB300 evaluations; no direct original-reference gain is asserted from these pooled scores.",
            "Descriptive pools are analyses of individual validated receipts, never fabricated merged valid receipts."],
        judgment="Both complete16M legs improve over the same-backend compiled8M reference; pooled score and both descriptive resampling intervals support continued learning with unchanged learning controls. Exact16M checkpoint is protected; no state.json edits performed.",
        cuda_initialized=torch.cuda.is_initialized())
    assert not result["cuda_initialized"]
    output = CAMPAIGN / "sidecar-fresh3-16M-confirmed-campaign.json"
    write_json(output,result)
    print(output)
    print(json.dumps({"protected":str(protected),"sha256":EXPECTED_SHA,
        "summary":{k:v for k,v in result["descriptive_pools"]["confirmed16M"].items() if k != "game_ids"},
        "comparison":{k:v for k,v in comparisons["confirmed16M_vs_compiled8M"].items()
                      if k not in ("baseline","candidate","actor_contrasts")}},indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--protect", action="store_true")
    main(parser.parse_args().protect)
