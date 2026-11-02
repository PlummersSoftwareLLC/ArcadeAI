#!/usr/bin/env python3
"""Prepare/validate confirmed64M publication; no action occurs on import/help.

Only root should execute after final confirmation and isolation audits exist:
  python build_confirmed64M_campaign.py --comparison FINAL_REPORT.json \
    --comparison-sha256 SHA --protect --output ../sidecar-fresh3-64M-confirmed-campaign.json

Without --protect/--output this validates and prints a summary only. There is no
managed-state, fleet, training-control, figure or source mutation capability.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys


os.environ["CUDA_VISIBLE_DEVICES"] = ""
for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[variable] = "2"
RUN = Path(__file__).resolve().parent
CAMPAIGN, GAME = RUN.parent, RUN.parents[2]
SOURCE = GAME / "models_dqn/managed-checkpoints/fresh3-64M.pt"
DESTINATION = GAME / "models_dqn/managed-incumbents/fresh3-64M-confirmed.pt"
PUBLICATION = CAMPAIGN / "sidecar-fresh3-64M-confirmed-campaign.json"
LABELS = ("sidecar-gpu0-64M-screen-01", "sidecar-gpu0-64M-confirm-01")
REFERENCE_LABELS = ("sidecar-gpu0-32M-screen-01", "sidecar-gpu0-32M-confirm-01")
EXPECTED_SHA = "fe88785bf9475c50a7a3df6cd04ab52caf46b706a7f6e22c36b99c21bcc93244"
EXPECTED_CLOCKS = dict(training_steps=607219, optimized_samples=1267425280, learner_frame_count=68634783)
PINNED_SCREEN_SHA = "a40030abe1ab8ab027f198c119ee5dbd2714fc1056fcf47aebbddce56aa55189"
COMPARISON_HELPER_SHA = "2dc2f768361944b4e087022c248a21fa24c266da536cd2d653d035aa83874746"
PUBLISH_HELPER_SHA = "0effac51a82642d08f57d9ad97c2ec977bc64492802b8e4f2ab66315e431972d"
PRIOR_PINS = RUN / "confirmed64M-prior-byte-pins.json"
PRIOR_PINS_SHA = "b023bccda91ef9c2080a731400ea355c38e3ce6c1d9e39b7e3db82e8f968f8e8"
LINEAGE = RUN / "fresh3-64M-checkpoint-lineage.json"
LINEAGE_SHA = "2c81a921172d1dcae9f6601660b4f8cc5839b9153d13cc604770dd003a11c2e4"
ISOLATION_AUDITS = {label: RUN / name for label, name in zip(LABELS, (
    "sidecar-64M-screen01-readonly-audit.json", "sidecar-64M-confirm01-readonly-audit.json"))}
ITERATIONS = 10000


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def verify_hash(path, expected):
    path = Path(path)
    require(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode)
            and digest(path) == expected, f"Identity changed: {path}")


def pinned_json(path, expected):
    path = Path(path)
    require(not path.is_symlink(), f"Unexpected symlink: {path}")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, f"Identity changed: {path}")
    return json.loads(raw)


def pinned_module(path, expected, name):
    verify_hash(path, expected)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_prior_artifacts():
    """Read only; never chmod or republish the seven older protected pairs."""
    pins = pinned_json(PRIOR_PINS, PRIOR_PINS_SHA)
    require(len(pins["protected"]) == 7, "Require all seven prior model/metadata pairs")
    for pair in pins["protected"]:
        for kind in ("checkpoint", "metadata"):
            record = pair[kind]
            verify_hash(record["path"], record["sha256"])
            info = Path(record["path"]).stat()
            require(oct(stat.S_IMODE(info.st_mode)) == record["mode"]
                    and info.st_size == record["size_bytes"], "Prior file mode/size changed")
    for record in pins["historical_campaigns"]:
        verify_hash(record["path"], record["sha256"])
    return pins


def require_confirmed_gate(report):
    """The pooled result can never rescue either separate leg."""
    require(report.get("schema") == "robotron-64M-composite-reference-analysis-v1"
            and report.get("stage") == "screen_and_confirmation", "Both final candidate legs required")
    identity = report["policy_identity"]
    require(identity["candidate_sha256"] == EXPECTED_SHA
            and identity["candidate_saved_clocks"] == EXPECTED_CLOCKS, "Wrong64M policy/clocks")
    gate = report["management_gate"]
    require(gate["reference_count"] == 236 and gate["reference_mean"] == 121245.33898305085
            and gate["reference_median"] == 124125.0, "Wrong composite32M reference")
    require(set(gate["each_candidate"]) == set(LABELS), "Wrong/missing separate64M legs")
    for label in LABELS:
        row = gate["each_candidate"][label]
        require(row["count"] >= 50 and row["mean"] >= 127307.6059322034
                and row["median"] >= 124125.0 and row["mean_at_least5pct"] is True
                and row["median_at_least_reference"] is True,
                "64M separate-leg gain gate rejected: " + label)
    require(gate["confirmation_gate_passed"] is True and gate["every_supplied_leg_passes"] is True
            and gate["two_separate_candidate_legs_present"] is True, "Confirmation gate rejected")
    return gate


def checkpoint_metadata():
    verify_hash(SOURCE, EXPECTED_SHA)
    lineage = pinned_json(LINEAGE, LINEAGE_SHA)
    import torch
    torch.set_num_threads(2)
    checkpoint = torch.load(SOURCE, map_location="cpu", weights_only=True)
    saved = {key: checkpoint.get(key) for key in lineage["candidate"]["saved_metadata"]}
    require(saved == lineage["candidate"]["saved_metadata"], "Actual saved64M metadata differs")
    require(all(saved[k] == v for k, v in EXPECTED_CLOCKS.items()), "64M checkpoint clock differs")
    for name, expected in lineage["candidate"]["state_dict_signatures"].items():
        signature = {key: dict(shape=list(value.shape), dtype=str(value.dtype))
                     for key, value in checkpoint[name].items()}
        require(signature == expected, "64M checkpoint architecture differs")
    require(len(checkpoint["optimizer_state_dict"]["state"]) == 81, "Require saved Adam81")
    require(not torch.cuda.is_initialized(), "CPU builder must not own a CUDA context")
    return saved


def isolation_evidence(sources):
    evidence = {}
    for source in sources:
        label = source["label"]
        path = ISOLATION_AUDITS[label]
        raw = path.read_bytes()
        audit = json.loads(raw)
        require(not path.is_symlink() and audit["pass"] is True and audit["checks"]
                and all(value is True for value in audit["checks"].values())
                and audit["receipt_sha256"] == source["sha256"]
                and audit["checkpoint_sha256"] == EXPECTED_SHA, "Missing positive final isolation audit: " + label)
        evidence[label] = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
            interpretation="Main trainer/prelaunch clocks are separate from the frozen saved-policy actor clocks")
    return evidence


def recheck_report_and_isolation(path, sha256, audits):
    verify_hash(path, sha256)
    for value in audits.values():
        verify_hash(value["path"], value["sha256"])


def build_campaign(comparison_path, comparison_sha256, *, protect=False):
    # Every validation/gate precedes any protection or publication write.
    previous = verify_prior_artifacts()
    composite = pinned_module(RUN / "compare64M_composite.py", COMPARISON_HELPER_SHA, "confirmed64_composite")
    publication = pinned_module(CAMPAIGN / "run-08/build_confirmed32M_campaign.py", PUBLISH_HELPER_SHA, "confirmed64_publish")
    provided = pinned_json(comparison_path, comparison_sha256)
    require_confirmed_gate(provided)
    fresh = composite.build(list(LABELS), ITERATIONS)
    require_confirmed_gate(fresh)
    require({k: v for k, v in provided.items() if k != "utc"}
            == {k: v for k, v in fresh.items() if k != "utc"}, "Final composite report differs from fresh strict validation")
    sources = {source["label"]: source for source in fresh["sources"]}
    require(set(sources) == set(REFERENCE_LABELS + LABELS), "Need all four current real receipts")
    require(sources[LABELS[0]]["sha256"] == PINNED_SCREEN_SHA, "First64M screen receipt changed")
    receipts = {}
    for label, source in sources.items():
        receipts[label] = pinned_json(source["path"], source["sha256"])
    reference = receipts[REFERENCE_LABELS[0]]
    for label, receipt in receipts.items():
        require(all(receipt[key] == reference[key] for key in (
            "engine_version", "state_size", "single_frame_state_size", "frame_stack",
            "wire_params_count", "wire_version", "frame_protocol")), "Root model/wire protocol differs: " + label)
        require(receipt["compile_report"]["graph_state"] == reference["compile_report"]["graph_state"],
                "Compilation graph state differs: " + label)
    candidate_sources = [sources[label] for label in LABELS]
    audits = isolation_evidence(candidate_sources)
    saved = checkpoint_metadata()
    pooled = fresh["pooled_candidate_vs_composite_reference"]
    now = datetime.now(timezone.utc).isoformat()
    metadata = dict(schema="managed-confirmed-incumbent-v3", utc=now,
        checkpoint=str(DESTINATION.relative_to(GAME)), sha256=EXPECTED_SHA,
        origin=str(SOURCE.relative_to(GAME)), receipts=candidate_sources,
        reference_receipts=[sources[label] for label in REFERENCE_LABELS],
        counts=[receipts[label]["count"] for label in LABELS],
        means=[receipts[label]["mean"] for label in LABELS], saved_clocks=EXPECTED_CLOCKS,
        saved_checkpoint_metadata=saved, full_leg_validation={label: {
            key: receipts[label][key] for key in ("started", "count", "pending", "abandoned",
                "start_ts", "close_ts", "ended_unix_s", "clocks")} for label in sources},
        combined_n=pooled["candidate"]["count"], combined_mean=pooled["candidate"]["mean"],
        combined_median=pooled["candidate"]["median"], combined_se=pooled["candidate"]["se"],
        selected_ratio=pooled["mean_ratio"], selected_ratio_reference="pooled236 original rows from two separately valid32M legs",
        gain_gate=fresh["management_gate"], numeric_policy=reference["numeric_policy"], runtime=reference["runtime"],
        backend_controls=fresh["common_private_backend"]["job"], source_hashes=reference["source_hashes"],
        boot_identity=reference["boot_assets"]["identity"], shim_sha256=reference["socket_wait"]["sha256"],
        composite_report=dict(path=str(Path(comparison_path).resolve()), sha256=comparison_sha256),
        main_training_isolation_provenance=audits, limitations=fresh["limitations"],
        scope="Confirmed64M versus separately valid same-backend32M composite reference; no state mutation.")
    # Final checks just before any write; protect uses a checked streaming copy,
    # independent inode, readonly publication and exclusive no-overwrite links.
    composite.recheck_receipt_evidence(fresh["receipt_byte_snapshots"])
    verify_prior_artifacts()
    recheck_report_and_isolation(comparison_path, comparison_sha256, audits)
    protected = (publication.protect_checkpoint(SOURCE, DESTINATION, metadata) if protect
                 else dict(requested=False, path=str(DESTINATION)))
    verify_prior_artifacts()
    composite.recheck_receipt_evidence(fresh["receipt_byte_snapshots"])
    recheck_report_and_isolation(comparison_path, comparison_sha256, audits)
    return dict(schema="frozen-policy-campaign-analysis-v4", stage="confirmed", created_utc=now,
        segment="GPU0 compiledFP32 fixed-transport3s private16actor cohorts",
        sources=candidate_sources, reference_sources=[sources[label] for label in REFERENCE_LABELS],
        historical_segment=dict(path=previous["historical_campaigns"][0]["path"],
            sha256=previous["historical_campaigns"][0]["sha256"],
            use="Previous separately validated campaign; reference receipts are not duplicated in current sources"),
        analysis_code=dict(path=str(Path(__file__).resolve()), sha256=digest(__file__)),
        pinned_helpers=dict(composite=COMPARISON_HELPER_SHA, publication=PUBLISH_HELPER_SHA),
        comparison_report=dict(path=str(Path(comparison_path).resolve()), sha256=comparison_sha256),
        validation=dict(each_receipt_separately_validated=True, no_fabricated_merged_receipt=True,
            official_sidecar_all_six_pairs=True, full_started_denominators_completed=True,
            pending_abandoned_zero=True, current_comparison_receipts=4, unique_ids=fresh["unique_ids"]),
        gain_gate=fresh["management_gate"], composite_reference=fresh["composite_reference"],
        each_candidate_vs_composite_reference=fresh["each_candidate_vs_composite_reference"],
        confirmed64M_vs_composite32M=pooled, separate_official_pair_comparisons=fresh["separate_official_pair_comparisons"],
        descriptive_pools=dict(composite32M=pooled["reference"], confirmed64M=pooled["candidate"]),
        common_runtime=dict(**fresh["common_private_backend"], boot_identity=metadata["boot_identity"],
            boot_files=reference["boot_assets"]["files"], shim_sha256=metadata["shim_sha256"]),
        policy_identity=dict(source_checkpoint=str(SOURCE), sha256=EXPECTED_SHA, saved_policy_clocks=saved,
            protected_copy=protected, retained_previous_incumbents=previous["protected"]),
        main_training_isolation_provenance=audits, receipt_byte_snapshots=fresh["receipt_byte_snapshots"],
        clock_interpretation="Saved frozen actor clocks are distinct from contemporaneous live main trainer clocks.",
        limitations=fresh["limitations"], managed_state_changed=False, cuda_initialized=False,
        judgment="Both separate64M legs pass prespecified mean/median gates. Descriptive pooled/bootstrap results; protection requested=" + str(protect))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--comparison-sha256", required=True)
    parser.add_argument("--protect", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        require(len(args.comparison_sha256) == 64 and all(c in "0123456789abcdef" for c in args.comparison_sha256), "Need exact final report SHA")
        require(not args.protect or args.output is not None, "Protection requires the new campaign output as well")
        if args.output:
            require(args.output.resolve() == PUBLICATION.resolve(), "Use the canonical new64M campaign path")
            require(not args.output.exists() and not args.output.is_symlink(), "Refusing to replace published campaign evidence")
        result = build_campaign(args.comparison, args.comparison_sha256, protect=args.protect)
        if args.output:
            composite = pinned_module(RUN / "compare64M_composite.py", COMPARISON_HELPER_SHA, "confirmed64_publish_recheck")
            composite.recheck_receipt_evidence(result["receipt_byte_snapshots"])
            verify_prior_artifacts()
            recheck_report_and_isolation(result["comparison_report"]["path"],
                result["comparison_report"]["sha256"], result["main_training_isolation_provenance"])
            publication = pinned_module(CAMPAIGN / "run-08/build_confirmed32M_campaign.py", PUBLISH_HELPER_SHA, "confirmed64_publish_output")
            publication.publish_json(args.output, result)
            verify_prior_artifacts()
        print(json.dumps(dict(gate_passed=True, protected=args.protect,
            count=result["confirmed64M_vs_composite32M"]["candidate"]["count"],
            mean_ratio=result["confirmed64M_vs_composite32M"]["mean_ratio"], output=str(args.output))))
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, "64M campaign rejected; no managed-state action: " + str(error) + "\n")


if __name__ == "__main__":
    main()
