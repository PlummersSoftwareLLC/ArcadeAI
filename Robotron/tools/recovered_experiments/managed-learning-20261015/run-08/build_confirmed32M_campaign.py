#!/usr/bin/env python3
"""Reproduce the fixed-transport GPU0 compiled16M-to-32M campaign on CPU.

Preparation does not execute this builder. After explicit authorization, run:
  python build_confirmed32M_campaign.py --protect --output ../sidecar-fresh3-32M-confirmed-campaign.json

Without --protect/--output this only validates/analyzes and prints a summary.
Existing publications and managed state are never overwritten. Both candidate
legs must independently pass the stated gain gate before any protection write.
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
import stat
import statistics
import sys
import tempfile

os.environ["CUDA_VISIBLE_DEVICES"] = ""
for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[variable] = "2"

RUN = Path(__file__).resolve().parent
CAMPAIGN, GAME = RUN.parent, RUN.parents[2]
sys.path.insert(0, str(GAME / "tools"))
from compare_sidecar_measurements import compare_sidecars, validate_backend
from compare_frozen_measurements import bootstrap, validate_receipt
from sidecar_boot import load_snapshot

LABELS = ("sidecar-gpu0-16M-reference-fixed-01", "sidecar-gpu0-32M-screen-01",
          "sidecar-gpu0-32M-confirm-01")
EVIDENCE = ("sidecar-16M-reference-fixed01", "sidecar-32M-screen01", "sidecar-32M-confirm01")
SLOTS = list(range(4096, 4112))
EXPECTED_SHA = "50a374d33250713ba205024f85aaed3e50b62db913c29b2c2fb8c28392f051af"
EXPECTED_CLOCKS = dict(training_steps=368323, optimized_samples=778166272,
                       learner_frame_count=36632770)
REFERENCE_SHA = "b8db175280b8e5d49865d14c83dccfe90737dfcb33d13d219ff5bb38d9abf281"
REFERENCE_CLOCKS = dict(training_steps=249165, optimized_samples=534130688,
                        learner_frame_count=20632694)
PINNED_RECEIPTS = {LABELS[0]: "ce7c5d0b56da5b9bed9089920eb6cbdc7dba29e4a0e9471e3088519cc903e772",
                   LABELS[1]: "d5e7ebaa8f7924967b35865d13a214fb56d33a5edfb00958f5960ebefc2ca1ec"}
PINNED_HELPERS = {
    "compare_sidecar_measurements.py": "879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746",
    "compare_frozen_measurements.py": "53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0",
}
HISTORICAL_NAME = "sidecar-fresh3-16M-confirmed-campaign.json"
HISTORICAL_SHA = "04438887dddfca3ff027afb84db9c2c50076f04ee0744130c5e31e68dba73f2f"
# Frozen metadata bytes of all six prior protected incumbents at preparation.
PRIOR_METADATA = {
    "fresh3-250k-confirmed.pt.json": "624a672d4110515706e925fde7e1fb7406a4b4c90c2318f0d5df37cb3f374873",
    "fresh3-1M-confirmed.pt.json": "37492d3783ba3c4b37939156689b8e44679fa31a99b2e00e4fe15911e6ec92c1",
    "fresh3-2M-confirmed.pt.json": "abe5bcdb7e0c8f40ca7cd363e18e79763e072fa46503dbb1a16f12ff52efd91b",
    "fresh3-4M-confirmed.pt.json": "59444dd3174f3a7f413e685323d06d9a5c0ea63d240e6ca1ee9f59b25f20bbbe",
    "fresh3-8M-confirmed.pt.json": "29a0c7e0c43d2c8a1b68294e6c002f634ca8ac97707fd88ec6db9412416f568b",
    "fresh3-16M-confirmed.pt.json": "6c5a2328d29904617985c6068c2b3e62ebeac5cc2c0fadb7393416d345abc7fd",
}
ITERATIONS, SEED = 10000, 20261016
LIMITATIONS = [
    "Descriptive bootstrap sensitivity intervals do not correct repeated looks, checkpoint selection or multiple comparisons; the stated gain gate is a management rule, not statistical proof.",
    "Paired actor-slot resampling has16clusters and pairs labels, not trajectories or RNG seeds. Within-actor game dependence remains possible.",
    "The fixed16M reference has one complete cohort;32M has two sequential cohorts. All600s admissions retain every started tail, with no best-N truncation.",
    "Identical boot assets/backend/source do not guarantee identical emulator trajectories or host pacing/batching. Main training continued under changing host workload.",
    "This fixed-transport3s-deadline segment is separate from historical old-transport GPU0 and GB300 curves. No direct historical/original score ratio is asserted.",
    "Pools below are descriptive rows from separately validated receipts, never synthesized valid measurement receipts.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def verify_hash(path, expected):
    require(not Path(path).is_symlink() and digest(path) == expected, f"Identity changed: {path}")


def publish_file(path, writer, *, mode=0o444):
    """Publish a fully fsynced new inode exclusively, without replacing a file."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            writer(stream)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        # link is an exclusive atomic publication of the new copied inode,
        # never a hard link to the source checkpoint. Remove the temp name.
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def publish_json(path, value):
    data = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    publish_file(path, lambda stream: stream.write(data))


def summarize_rows(rows, labels):
    scores = [r["score"] for r in rows]
    require(len(scores) >= 2, "At least two rows required for descriptive statistics")
    sd = statistics.stdev(scores)
    return dict(unit="descriptive row pool; not a measurement receipt", source_labels=list(labels),
                count=len(rows), mean=statistics.mean(scores), median=statistics.median(scores),
                sd=sd, se=sd / math.sqrt(len(rows)), minimum=min(scores), maximum=max(scores),
                actor_slot_counts=dict(sorted(Counter(str(r["client_slot"]) for r in rows).items())),
                duration_s=dict(mean=statistics.mean(r["duration_s"] for r in rows),
                                maximum=max(r["duration_s"] for r in rows)),
                playable_frames_total=sum(r["playable_frames"] for r in rows),
                game_ids=[r["journal_game_id"] for r in rows])


def compare_rows(base, candidate, base_labels, candidate_labels, *, iterations=ITERATIONS):
    """Analyze already validated rows directly; do not invent a receipt."""
    a, b = summarize_rows(base, base_labels), summarize_rows(candidate, candidate_labels)
    require(a["mean"] > 0, "Positive baseline mean required")
    contrasts = {}
    for slot in SLOTS:
        av, bv = [[r["score"] for r in rows if r["client_slot"] == slot] for rows in (base, candidate)]
        require(bool(av) and bool(bv), f"Missing paired actor slot{slot}")
        am, bm = statistics.mean(av), statistics.mean(bv)
        contrasts[str(slot)] = dict(baseline_count=len(av), candidate_count=len(bv),
                                   baseline_mean=am, candidate_mean=bm, difference=bm-am,
                                   ratio=bm/am if am else None)
    return dict(baseline=a, candidate=b, mean_difference=b["mean"]-a["mean"],
                mean_ratio=b["mean"]/a["mean"], relative_change_pct=100*(b["mean"]/a["mean"]-1),
                game_bootstrap=bootstrap(base, candidate, iterations=iterations, seed=SEED),
                paired_slot_bootstrap=bootstrap(base, candidate, iterations=iterations, seed=SEED, cluster=True),
                actor_contrasts=contrasts,
                slots_with_positive_mean_contrast=sum(v["difference"] > 0 for v in contrasts.values()))


def gain_gate(reference_rows, candidate_legs):
    baseline = summarize_rows(reference_rows, [LABELS[0]])
    require(baseline["mean"] > 0, "Positive fixed16M mean required")
    details = {}
    for label, rows in candidate_legs.items():
        summary = summarize_rows(rows, [label])
        ratio = summary["mean"] / baseline["mean"]
        details[label] = dict(count=summary["count"], mean=summary["mean"], median=summary["median"],
                              mean_ratio=ratio, mean_at_least_5pct=ratio >= 1.05,
                              median_at_least_reference=summary["median"] >= baseline["median"])
    passed = len(details) == 2 and all(v["mean_at_least_5pct"] and v["median_at_least_reference"]
                                     for v in details.values())
    result = dict(passed=passed, rule="Each separate32M leg mean>=1.05x fixed16M mean and median>=fixed16M median",
                  reference=baseline, candidate_legs=details)
    if not passed:
        raise ValueError("32M gain gate rejected; no protection performed: " + json.dumps(details, sort_keys=True))
    return result


def validate_leg(label, expected_sha, expected_clocks):
    path = CAMPAIGN / label / "receipt.json"
    if label in PINNED_RECEIPTS:
        verify_hash(path, PINNED_RECEIPTS[label])
    raw = json.loads(path.read_text())
    leg = validate_backend(raw, verify_checkpoint=True)  # includes full whole-game validator
    require(raw["label"] == label and raw["phase"] == "finished" and raw["reason"] is None,
            f"Not a finished named leg: {label}")
    require(raw["receipt_validator"] == "passed", f"Missing runner validation: {label}")
    require(raw["checkpoint_sha256"] == expected_sha, f"Wrong checkpoint: {label}")
    expected_source = (GAME / "models_dqn/managed-incumbents/fresh3-16M-confirmed.pt" if label == LABELS[0]
                       else GAME / "models_dqn/managed-checkpoints/fresh3-32M.pt")
    require(Path(raw["source_checkpoint_path"]).resolve() == expected_source.resolve()
            and Path(raw["job"]["checkpoint"]).resolve() == expected_source.resolve(),
            f"Wrong explicit source checkpoint path: {label}")
    verify_hash(raw["source_checkpoint_path"], expected_sha)
    for key, value in expected_clocks.items():
        require(raw["checkpoint_metadata"][key] == raw["clocks"][key] == value,
                f"Saved/frozen actor clock differs: {label}/{key}")
    require(raw["job"]["cohort_s"] == 600 and raw["job"]["timeout_s"] == 1200
            and raw["job"]["port"] == 9999 and raw["job"]["wait_us"] == 1000
            and raw["job"]["inference_backend"] == "inductor", f"Unexpected current backend: {label}")
    boundary = raw["boundary"]
    require(boundary["clients"] == boundary["expected"] == boundary["acknowledged"] == 16
            and boundary["generation"] == boundary["requested_generation"] == raw["generation"]
            and sorted(boundary["actor_slots"]) == leg["expected_actor_slots"] == SLOTS,
            f"Actor boundary coverage differs: {label}")
    require(sorted({r["client_slot"] for r in leg["rows"]}) == SLOTS, f"Extra/missing slots: {label}")
    boot = load_snapshot(Path(raw["job"]["boot_assets"]))
    require(boot["identity"] == raw["boot_assets"]["identity"] and boot["files"] == raw["boot_assets"]["files"],
            f"Boot seed changed: {label}")
    verify_hash(raw["socket_wait"]["library"], raw["socket_wait"]["sha256"])
    require(all(v["activation_count"] == 1 for v in raw["socket_wait"]["actors"].values()),
            f"Unexpected shim activation count: {label}")
    summary = summarize_rows(leg["rows"], [label])
    for key in ("mean", "median", "sd", "se"):
        require(math.isclose(summary[key], raw[key], abs_tol=1e-8), f"Summary differs: {label}/{key}")
    require(all(r["boundary_reason"] == "wire_lives_exhausted" and r["end_unix_s"] <= raw["ended_unix_s"]
                for r in leg["rows"]), f"Missing terminal/tail evidence: {label}")
    return raw, leg, dict(label=label, path=str(path), sha256=digest(path))


def verify_history(ids):
    path = CAMPAIGN / HISTORICAL_NAME
    verify_hash(path, HISTORICAL_SHA)
    historical = json.loads(path.read_text())
    older_path = Path(historical["historical_segment"]["path"])
    verify_hash(older_path, historical["historical_segment"]["sha256"])
    older = json.loads(older_path.read_text())
    sources = historical["sources"] + older["sources"]
    for item in sources:
        receipt_path = Path(item["path"])
        verify_hash(receipt_path, item["sha256"])
        raw = json.loads(receipt_path.read_text())
        leg = validate_receipt(raw)
        require(leg["label"] not in ids, "Duplicate historical receipt label")
        ids[leg["label"]] = {row["journal_game_id"] for row in leg["rows"]}
    retained = {}
    for name, meta_hash in PRIOR_METADATA.items():
        meta_path = GAME / "models_dqn/managed-incumbents" / name
        verify_hash(meta_path, meta_hash)
        meta = json.loads(meta_path.read_text())
        checkpoint_path = GAME / meta["checkpoint"]
        verify_hash(checkpoint_path, meta["sha256"])
        retained[str(checkpoint_path)] = dict(sha256=meta["sha256"], metadata_path=str(meta_path), metadata_sha256=meta_hash)
    return dict(path=str(path), sha256=HISTORICAL_SHA, older_path=str(older_path),
                older_sha256=digest(older_path), historical_receipts=len(sources),
                use="Byte-verified provenance only; no cross-backend pooling or ratio"), retained


def verify_disjoint(ids):
    overlaps = {}
    for a, b in itertools.combinations(ids, 2):
        count = len(ids[a] & ids[b])
        require(count == 0, f"Game ID overlap: {a} vs {b} ({count})")
        overlaps[a + " vs " + b] = count
    return overlaps


def checkpoint_metadata(source):
    verify_hash(source, EXPECTED_SHA)
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    checkpoint = torch.load(source, map_location="cpu", weights_only=True)
    saved = {key: checkpoint.get(key) for key in (
        "engine_version", "state_size", "single_frame_state_size", "frame_stack", "training_steps",
        "optimized_samples", "learner_frame_count", "frame_count", "measurement_frame_count",
        "total_training_steps", "baseline_batch_size", "last_target_update_samples")}
    require(all(saved[k] == v for k, v in EXPECTED_CLOCKS.items()), "32M saved checkpoint clocks differ")
    require(saved["engine_version"] == 28 and saved["state_size"] == 11128
            and saved["single_frame_state_size"] == 2782 and saved["frame_stack"] == 4, "32M model geometry differs")
    require(not torch.cuda.is_initialized(), "CPU builder must not own a CUDA context")
    return saved


def protect_checkpoint(source, destination, metadata):
    """Create only the new checkpoint+metadata; validate/reuse exact existing pair."""
    source, destination = Path(source), Path(destination)
    meta_path = destination.with_suffix(".pt.json")
    require(destination.exists() == meta_path.exists(), "Partial existing protection pair; inspect manually")
    if destination.exists():
        actual = json.loads(meta_path.read_text())
        require({k:v for k,v in actual.items() if k != "utc"} == {k:v for k,v in metadata.items() if k != "utc"},
                "Existing32M metadata differs; no overwrite allowed")
    else:
        verify_hash(source, metadata["sha256"])
        original = source.stat()
        def copy_checked(stream):
            copied_hash = hashlib.sha256()
            with source.open("rb") as reader:
                for block in iter(lambda: reader.read(4 * 1024 * 1024), b""):
                    stream.write(block)
                    copied_hash.update(block)
            require(copied_hash.hexdigest() == metadata["sha256"], "Copied checkpoint identity differs")
            stream.flush()
            copied = source.stat()
            require((original.st_dev, original.st_ino, original.st_size, original.st_mtime_ns, original.st_ctime_ns)
                    == (copied.st_dev, copied.st_ino, copied.st_size, copied.st_mtime_ns, copied.st_ctime_ns),
                    "Source checkpoint changed during copy")
        publish_file(destination, copy_checked)
        verify_hash(destination, metadata["sha256"])
        publish_json(meta_path, metadata)
    verify_hash(destination, metadata["sha256"])
    for path in (destination, meta_path):
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o222 and info.st_nlink == 1,
                f"Protection must be independent regular read-only file: {path}")
    a, b = source.stat(), destination.stat()
    require((a.st_dev, a.st_ino) != (b.st_dev, b.st_ino), "Protected checkpoint aliases source inode")
    return dict(path=str(destination), sha256=digest(destination), metadata_path=str(meta_path),
                metadata_sha256=digest(meta_path), size_bytes=b.st_size, nlink=b.st_nlink,
                writable=False, independent_source_inode=True)


def build_campaign(*, protect=False):
    for name, expected in PINNED_HELPERS.items():
        verify_hash(GAME / "tools" / name, expected)
    receipts, legs, sources, isolation = {}, {}, [], {}
    for label, evidence in zip(LABELS, EVIDENCE):
        expected_sha = REFERENCE_SHA if label == LABELS[0] else EXPECTED_SHA
        expected_clocks = REFERENCE_CLOCKS if label == LABELS[0] else EXPECTED_CLOCKS
        receipts[label], legs[label], source = validate_leg(label, expected_sha, expected_clocks)
        sources.append(source)
        audit_path, prelaunch = RUN / (evidence + "-readonly-audit.json"), RUN / (evidence + "-prelaunch.json")
        audit = json.loads(audit_path.read_text())
        require(audit["pass"] is True and all(value is True for value in audit["checks"].values())
                and audit["receipt_sha256"] == source["sha256"], f"Missing positive completed isolation audit: {label}")
        isolation[label] = dict(path=str(audit_path), sha256=digest(audit_path), prelaunch_path=str(prelaunch),
                                prelaunch_sha256=digest(prelaunch), main_prelaunch_clocks=json.loads(prelaunch.read_text()).get("main"),
                                interpretation="Main trainer progressed separately; these are not actor policy clocks")
    reference = receipts[LABELS[0]]
    # The final reviewed tool validates each real complete leg plus exact current
    # numeric/runtime/source/job/boot/shim match and pairwise disjoint IDs.
    real_comparisons = {}
    for a, b in ((0, 1), (0, 2), (1, 2)):
        real_comparisons[f"{LABELS[b]} vs {LABELS[a]}"] = compare_sidecars(
            receipts[LABELS[a]], receipts[LABELS[b]], iterations=ITERATIONS, verify_checkpoint=True)
    for label, raw in receipts.items():
        require(all(raw[key] == reference[key] for key in (
            "engine_version", "state_size", "single_frame_state_size", "frame_stack", "wire_params_count", "wire_version", "frame_protocol")),
            f"Root frame metadata differs: {label}")
        require(raw["compile_report"]["graph_state"] == reference["compile_report"]["graph_state"],
                f"Compilation graph state differs: {label}")
    gate = gain_gate(legs[LABELS[0]]["rows"], {label: legs[label]["rows"] for label in LABELS[1:]})
    ids = {label: {r["journal_game_id"] for r in legs[label]["rows"]} for label in LABELS}
    historical, retained = verify_history(ids)
    overlaps = verify_disjoint(ids)
    pooled = legs[LABELS[1]]["rows"] + legs[LABELS[2]]["rows"]
    pooled_comparison = compare_rows(legs[LABELS[0]]["rows"], pooled, [LABELS[0]], LABELS[1:])
    source = GAME / "models_dqn/managed-checkpoints/fresh3-32M.pt"
    saved = checkpoint_metadata(source)
    protected = GAME / "models_dqn/managed-incumbents/fresh3-32M-confirmed.pt"
    metadata = dict(schema="managed-confirmed-incumbent-v2", utc=datetime.now(timezone.utc).isoformat(),
        checkpoint=str(protected.relative_to(GAME)), sha256=EXPECTED_SHA, origin=str(source.relative_to(GAME)),
        receipts=sources[1:], reference_receipt=sources[0], counts=[len(legs[label]["rows"]) for label in LABELS[1:]],
        means=[receipts[label]["mean"] for label in LABELS[1:]], saved_clocks=EXPECTED_CLOCKS,
        full_leg_validation={label: dict(started=receipts[label]["started"], count=receipts[label]["count"],
            pending=receipts[label]["pending"], abandoned=receipts[label]["abandoned"],
            start_ts=receipts[label]["start_ts"], close_ts=receipts[label]["close_ts"],
            ended_unix_s=receipts[label]["ended_unix_s"], frozen_actor_clocks=receipts[label]["clocks"])
            for label in LABELS},
        saved_checkpoint_metadata=saved, combined_n=len(pooled), combined_mean=pooled_comparison["candidate"]["mean"],
        combined_median=pooled_comparison["candidate"]["median"], combined_se=pooled_comparison["candidate"]["se"],
        selected_ratio=pooled_comparison["mean_ratio"], selected_ratio_reference="fixed-transport16M reference only",
        gain_gate=gate, numeric_policy=reference["numeric_policy"], runtime=reference["runtime"],
        backend_controls=real_comparisons[f"{LABELS[1]} vs {LABELS[0]}"]["matched_private_backend"],
        source_hashes=reference["source_hashes"], boot_identity=reference["boot_assets"]["identity"],
        shim_sha256=reference["socket_wait"]["sha256"], limitations=LIMITATIONS,
        scope="Two separately valid full-tail32M cohorts against same fixed-transport GPU0 compiledFP32 reference. No historical cross-backend ratio and no state mutation.")
    protected_evidence = protect_checkpoint(source, protected, metadata) if protect else dict(requested=False, path=str(protected))
    # Recheck previous metadata bytes after any new protection, without writing them.
    for name, expected in PRIOR_METADATA.items():
        verify_hash(protected.parent / name, expected)
    result = dict(schema="frozen-policy-campaign-analysis-v3", stage="confirmed",
        segment="GPU0 compiledFP32 fixed-transport3s private initialized16actor cohorts",
        created_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
        analysis_code=dict(path=str(Path(__file__)), sha256=digest(__file__)), validator_hashes=PINNED_HELPERS,
        validation=dict(each_receipt_separately_validated=True, official_sidecar_comparator_passed_all_three_pairs=True,
            no_fabricated_merged_receipt=True, sidecar_receipts=3, new_disjoint_games=sum(len(legs[x]["rows"]) for x in LABELS),
            historical_receipts_revalidated=historical["historical_receipts"],
            all_historical_and_new_disjoint_games=sum(map(len, ids.values())), pairwise_game_id_overlap_counts=overlaps,
            full_started_denominators_completed=True, pending_and_abandoned_zero=True,
            all16_slots_covered_each_leg=SLOTS, exact_current_backend_numeric_runtime_source_model_wire_boot_shim_match=True),
        gain_gate=gate, separately_validated_leg_comparisons=real_comparisons,
        cohort_summaries={label:dict(**summarize_rows(legs[label]["rows"], [label]), saved_actor_clocks=receipts[label]["clocks"],
            start_ts=receipts[label]["start_ts"], close_ts=receipts[label]["close_ts"], ended_unix_s=receipts[label]["ended_unix_s"],
            late_completions=sum(r["end_unix_s"] > receipts[label]["close_ts"] for r in legs[label]["rows"]),
            last_tail_s=max(r["end_unix_s"] for r in legs[label]["rows"])-receipts[label]["close_ts"],
            compile_report=receipts[label]["compile_report"]) for label in LABELS},
        descriptive_pools=dict(fixed16M_reference=pooled_comparison["baseline"], confirmed32M=pooled_comparison["candidate"]),
        confirmed32M_vs_fixed16M=pooled_comparison, common_runtime=dict(runtime=reference["runtime"],
            numeric_policy=reference["numeric_policy"], protocol=legs[LABELS[0]]["protocol"],
            backend_controls=metadata["backend_controls"], source_hashes=reference["source_hashes"],
            boot_identity=reference["boot_assets"]["identity"], boot_files=reference["boot_assets"]["files"],
            shim_sha256=reference["socket_wait"]["sha256"]),
        policy_identity=dict(source_checkpoint=str(source), sha256=EXPECTED_SHA, saved_policy_clocks=saved,
            protected_copy=protected_evidence, retained_previous_incumbents=retained,
            reference_checkpoint=reference["source_checkpoint_path"], reference_sha256=REFERENCE_SHA,
            reference_saved_clocks=reference["checkpoint_metadata"]),
        clock_interpretation="Sidecar clocks are installed frozen saved-policy clocks; later main trainer/prelaunch clocks remain separate.",
        main_training_isolation_provenance=isolation, historical_segment=historical, limitations=LIMITATIONS,
        judgment="Both separately complete32M legs pass the explicit mean/median rule against the fixed16M reference. Pool/bootstrap are descriptive. Protection requested="+str(protect)+"; no state.json changes.",
        cuda_initialized=False)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protect", action="store_true", help="Create immutable new32M checkpoint+metadata only after every validation/gate")
    parser.add_argument("--output", type=Path, help="Publish analysis to a new file; never overwrite evidence")
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError("Output already exists; refusing to overwrite published analysis")
        report = build_campaign(protect=args.protect)
        if args.output:
            publish_json(args.output, report)
        comparison = report["confirmed32M_vs_fixed16M"]
        print(json.dumps(dict(gain_gate=report["gain_gate"]["passed"],
            pooled={k:v for k,v in comparison["candidate"].items() if k != "game_ids"},
            mean_ratio=comparison["mean_ratio"], protected=report["policy_identity"]["protected_copy"], output=str(args.output)), indent=2))
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, "32M campaign rejected; no state/promotion action: " + str(error) + "\n")


if __name__ == "__main__":
    main()
