#!/usr/bin/env python3
"""Strict1200s192M reference only. Import/default/help are inert; ROOT executes.

No launch, state/control action, protection, model loading or future224/256 read.
Exactly two named full cohorts form the reference regardless their scores.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
CAMPAIGN = RUN.parent
GAME = CAMPAIGN.parents[1]
PLAN_SHA = "6560765fbf787f78bc033a9c0cee8ace59ea76ecb52e74e4dcc70049fabe488e"
SHARED = CAMPAIGN / "run-23/quality192M-preparation/analyze192M_assessment.py"
SHARED_SHA = "6a8dda64851bafdf765bc78140663e29488b0ba4e39c2e3a889a0ce3a1d51363"
LABELS = ("sidecar-gpu0-192M-reference1200-01", "sidecar-gpu0-192M-reference1200-02")
SLOTS = list(range(4096, 4112))


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def shared_module():
    raw = SHARED.read_bytes()
    require(sha(raw) == SHARED_SHA, "Changed reused192M validator")
    spec = importlib.util.spec_from_file_location("quality1200_shared192", SHARED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(SHARED.read_bytes() == raw, "Reused validator changed during import")
    return module


def full_stat(path):
    path = Path(path)
    require(not path.is_symlink() and stat.S_ISREG(path.stat().st_mode), "Need regular protected source")
    x = path.stat()
    return dict(size=x.st_size, mtime_ns=x.st_mtime_ns, inode=x.st_ino, device=x.st_dev,
                mode=stat.S_IMODE(x.st_mode), nlink=x.st_nlink)


def check_plan(plan, design):
    require(plan["schema"] == "robotron-quality1200-plan-v1" and design["root_adopted_design"] is True,
            "Need root-adopted1200s design")
    require(plan["fixed_labels"] == design["fixed_labels"]
        and plan["fixed_labels"]["192M_reference"] == list(LABELS)
        and plan["reference"]["required_valid_legs"] == 2, "Fixed reference labels/cardinality changed")
    job = plan["backend"]["job"]
    require(job["cohort_s"] == 1200 and job["timeout_s"] == 2400
        and job["actors"] == 16 and job["actor_slots"] == SLOTS and job["port"] == 9999
        and job["wait_us"] == 1000 and job["device"] == "cuda" and job["inference_backend"] == "inductor",
        "Changed matched1200s backend")
    require(plan["reference"]["checkpoint"]["sha256"] == design["reference_checkpoint_sha256"]
        and plan["validity"]["official_min_games"] == 50
        and plan["validity"]["precision_only_N_below"] == 64
        and plan["validity"]["operational_replacement_authorized"] is False,
        "Changed reference/validity policy")
    require(Path(plan["publication"]["reference_output"]) == RUN / "quality1200-reference-final.json",
        "Wrong fixed reference publication path")


def positive_audit(audit, receipt_sha, checkpoint_sha):
    require(audit.get("pass") is True and audit.get("checks")
        and all(value is True for value in audit["checks"].values())
        and audit.get("receipt_sha256") == receipt_sha
        and audit.get("checkpoint_sha256") == checkpoint_sha, "Need exact positive final isolation audit")
    for key in ("private_owned_processes_listener_released", "private_GPU0_context_released", "loaded_sources_unchanged"):
        require(audit["checks"].get(key) is True, "Missing positive ownedcleanup/source evidence")


def history_registry(plan, evidence, tools):
    history = evidence.json(plan["history"]["path"], plan["history"]["sha256"])
    require(history["schema"] == "robotron-quality1200-completed-history-v1" and history["complete"] is True,
        "Incomplete original history")
    final = evidence.json(history["final192_analysis"]["path"], history["final192_analysis"]["sha256"])
    require(final["global_ids"] == dict(receipts=26, games=2613, overlaps=0)
        and final["sources"] == history["sources"], "Original26/2613 registry differs")
    published = evidence.json(history["published192_campaign"]["path"], history["published192_campaign"]["sha256"])
    root = evidence.json(history["root192_promotion"]["path"], history["root192_promotion"]["sha256"])
    require(root["root_promoted"] is True and root["new_model_root_sha256"] == plan["reference"]["checkpoint"]["sha256"]
        and published["sources"] == [source for source in final["sources"] if source["label"] in
            ("sidecar-gpu0-192M-screen-01", "sidecar-gpu0-192M-confirm-01")], "192M publication lineage differs")
    seen, labels = {}, set()
    for source in history["sources"]:
        require(source["label"] not in labels, "Duplicate historical label")
        labels.add(source["label"])
        receipt = evidence.json(source["path"], source["sha256"])
        leg = tools.validate_receipt(receipt)
        require(leg["label"] == source["label"], "Historical label differs")
        for row in leg["rows"]:
            require(row["journal_game_id"] not in seen, "Historical game ID overlap")
            seen[row["journal_game_id"]] = source["label"]
    require(len(labels) == history["expected_receipts"] == plan["history"]["expected_receipts"] == 26
        and len(seen) == history["expected_unique_games"] == plan["history"]["expected_unique_games"] == 2613,
        "Wrong historical denominator")
    return history, seen


def context():
    shared = shared_module()
    evidence = shared.Evidence()
    evidence.file(SHARED, SHARED_SHA)
    evidence.file(__file__, shared.digest(__file__))
    plan = evidence.json(HERE / "quality1200-plan.json", PLAN_SHA)
    design = evidence.json(plan["root_design"]["path"], plan["root_design"]["sha256"])
    check_plan(plan, design)
    launch = evidence.json(plan["deferred_launch_contract"]["path"], plan["deferred_launch_contract"]["sha256"])
    require(launch, "Missing deferred launch contract")
    tools = shared.dependencies(evidence)
    history, seen = history_registry(plan, evidence, tools)
    source = plan["reference"]["checkpoint"]
    require(full_stat(source["path"]) == source["stat"] and source["stat"]["mode"] == 0o444
        and source["stat"]["nlink"] == 1, "Protected192M stat/protection changed")
    evidence.bind_stat(source["path"], source["stat"])
    metadata = evidence.json(source["metadata_path"], source["metadata_sha256"])
    lineage = evidence.json(plan["reference"]["lineage"]["path"], plan["reference"]["lineage"]["sha256"])
    require(lineage["proposal_only"] is False and lineage["PASS"] is True
        and lineage["checks"] and all(value is True for value in lineage["checks"].values())
        and lineage["root_verification"]["status"] == "PASS"
        and lineage["root_verification"]["CUDA_initialized"] is False
        and lineage["candidate"]["sha256"] == metadata["sha256"] == source["sha256"]
        and lineage["candidate"]["saved_metadata"] == metadata["saved_checkpoint_metadata"] == plan["reference"]["saved_metadata"]
        and lineage["candidate"]["optimizer"] == plan["reference"]["optimizer"], "Final root192M identity changed")
    for relative, expected in plan["backend"]["source_hashes"].items():
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "Invalid source path")
        evidence.file(GAME / relative, expected)
    require(len(plan["backend"]["source_hashes"]) == 12, "Need all12 private sources")
    boot = tools.load_snapshot(Path(plan["backend"]["job"]["boot_assets"]))
    require(boot["identity"] == plan["backend"]["boot_identity"] and boot["files"] == plan["backend"]["boot_files"], "Changed boot snapshot")
    evidence.boot(plan["backend"]["job"]["boot_assets"], boot, tools.load_snapshot)
    # The existing binary is bound by its actual historical receipt; no rebuild.
    original_source = next(source for source in history["sources"] if source["label"] == "sidecar-gpu0-192M-screen-01")
    original = evidence.json(original_source["path"], original_source["sha256"])
    require(original["socket_wait"]["sha256"] == plan["backend"]["socket_wait_sha256"], "Changed recorded shim")
    evidence.file(original["socket_wait"]["library"], plan["backend"]["socket_wait_sha256"])
    require(not any(name == "torch" or name.startswith("torch.") for name in sys.modules), "Torch must not be imported")
    return shared, evidence, tools, plan, history, seen


def validate_reference_leg(receipt, label, plan, evidence, tools, shared):
    require(label in LABELS and receipt["label"] == label, "Unexpected assigned reference label")
    leg = tools.validate_backend(receipt, verify_checkpoint=False)
    require(receipt["phase"] == "finished" and receipt["reason"] is None
        and receipt["receipt_validator"] == "passed", "Need explicit final validated cohort")
    source = plan["reference"]["checkpoint"]
    require(receipt["checkpoint_sha256"] == source["sha256"]
        and receipt["source_checkpoint_path"] == receipt["job"]["checkpoint"] == source["path"], "Wrong protected192M source")
    evidence.file(receipt["checkpoint_path"], source["sha256"])
    expected = plan["backend"]
    require({key: receipt["job"][key] for key in tools.JOB_FIELDS} == expected["job"], "Window/private job settings differ")
    for key in ("numeric_policy", "runtime", "source_hashes"):
        require(receipt[key] == expected[key], "Matched backend differs: " + key)
    require(receipt["boot_assets"]["identity"] == expected["boot_identity"]
        and receipt["boot_assets"]["files"] == expected["boot_files"]
        and receipt["socket_wait"]["sha256"] == expected["socket_wait_sha256"]
        and all(value["activation_count"] == 1 for value in receipt["socket_wait"]["actors"].values()), "Boot/shim provenance differs")
    saved = plan["reference"]["saved_metadata"]
    require(receipt["checkpoint_metadata"].get("defaulted_metadata_fields") == []
        and all(receipt["checkpoint_metadata"].get(key) == saved[key] for key in shared.META_KEYS), "Saved actor metadata changed")
    for key in shared.CORE_CLOCKS:
        alias = "learner_frames" if key == "learner_frame_count" else key
        require(leg["clocks"][alias] == receipt["clocks"][key] == saved[key], "Frozen actor clocks changed")
    boundary = receipt["boundary"]
    require(boundary["clients"] == boundary["expected"] == boundary["acknowledged"] == 16
        and boundary["generation"] == boundary["requested_generation"] == receipt["generation"]
        and sorted(boundary["actor_slots"]) == leg["expected_actor_slots"] == SLOTS
        and sorted({row["client_slot"] for row in leg["rows"]}) == SLOTS, "Incomplete exact16-slot boundary")
    require(math.isclose(leg["close_ts"] - leg["start_ts"], 1200, abs_tol=1e-6)
        and all(row["boundary_reason"] == "wire_lives_exhausted" and row["end_unix_s"] <= receipt["ended_unix_s"]
            for row in leg["rows"]), "Admission or full natural tails differ")
    summary = shared.summarize(leg["rows"])
    require(all(math.isclose(summary[key], receipt[key], rel_tol=1e-12, abs_tol=1e-8)
                for key in ("mean", "median", "sd", "se")), "Receipt summary differs")
    return leg


def build(labels, audit_paths, audit_shas, *, single=False):
    require((single and len(labels) == 1 and labels[0] in LABELS) or
            (not single and tuple(labels) == LABELS), "Require exact assigned cardinality/order; no selection or replacement")
    require(len(audit_paths) == len(audit_shas) == len(labels), "Need one explicit SHA-bound final audit per leg")
    shared, evidence, tools, plan, history, seen = context()
    rows, sources, audits, per_leg = [], [], [], []
    for label, audit_path, audit_sha in zip(labels, audit_paths, audit_shas):
        path = CAMPAIGN / label / "receipt.json"
        receipt = evidence.json(path)
        receipt_sha = evidence.files[str(path.absolute())]
        leg = validate_reference_leg(receipt, label, plan, evidence, tools, shared)
        audit = evidence.json(audit_path, audit_sha)
        positive_audit(audit, receipt_sha, plan["reference"]["checkpoint"]["sha256"])
        for row in leg["rows"]:
            require(row["journal_game_id"] not in seen, "New/reference/history game ID overlap")
            seen[row["journal_game_id"]] = label
        rows.extend(leg["rows"])
        sources.append(dict(label=label, path=str(path), sha256=receipt_sha))
        audits.append(dict(label=label, path=str(Path(audit_path).absolute()), sha256=audit_sha))
        per_leg.append(dict(label=label, **shared.summarize(leg["rows"]), low_N_precision_only=len(leg["rows"]) < 64,
            full_denominator=dict(started=receipt["started"], count=receipt["count"], pending=0, abandoned=0),
            late_tail_count=sum(row["end_unix_s"] > leg["close_ts"] for row in leg["rows"])))
    evidence.recheck()
    require(full_stat(plan["reference"]["checkpoint"]["path"]) == plan["reference"]["checkpoint"]["stat"], "Source protection changed")
    result = dict(schema="robotron-quality1200-192M-reference-v1", utc=datetime.now(timezone.utc).isoformat(),
        reference_final=not single, usable_as_new_reference=not single,
        sources=sources, per_leg=per_leg, original_row_pool=tools.summarize(rows, labels),
        global_ids=dict(receipts=26 + len(labels), games=len(seen), overlaps=0),
        prior_history=plan["history"], root_design=plan["root_design"], plan_sha256=PLAN_SHA,
        protected_policy=plan["reference"], backend=plan["backend"], final_isolation_audits=audits,
        original_rows=rows if not single else None, all_original_fulltails_retained=True,
        no_score_threshold_or_reference_selection=True, no_fabricated_measurement_receipt=True,
        promotion=False, protection=False, state_or_control_changes=False,
        scope="New1200s reference uses ALL fixed original rows regardless scores; original600s113/+28.88% remains immutable. No192M learning gain, old/new reference selection, model-copy promotion or control action.",
        caveats=["Single-leg validation is never a usable reference; both fixed legs remain mandatory regardless first result.",
            "N<64 precision caveat only; official50 floor/full16-slot/fulltail validity unchanged. No extension/count retry/third valid rescue.",
            "Reference pool is descriptive original-row data, not a merged valid receipt. Future224/256 windows must match1200/2400 exactly.",
            "Model source trust is existing root CPU/publication attestations plus pinned stat guards; new private checkpoint copies are SHA verified. No Torch/model loading.",
            "Separate saved checkpoint/Adam versus concurrent main/process counters; no whole-interval AMP or causal learning claim."], evidence=evidence.snapshot())
    return result, evidence


def publish(report, evidence, output):
    output = Path(output).absolute()
    require(output.parent == RUN and output.name.startswith("quality1200-") and output.suffix == ".json"
        and not output.exists() and not output.is_symlink(), "Only new quality1200 JSON in run25")
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, prefix=".quality1200-", delete=False) as file:
            temporary = Path(file.name)
            file.write(raw); file.flush(); os.fchmod(file.fileno(), 0o444); os.fsync(file.fileno())
        evidence.recheck()
        if "protected_policy" in report:
            source = report["protected_policy"]["checkpoint"]
            require(full_stat(source["path"]) == source["stat"], "Protected source changed before publication")
        os.link(temporary, output)  # atomic/exclusive: never replaces any file
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return sha(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-readiness", action="store_true")
    mode.add_argument("--validate-leg", choices=LABELS)
    mode.add_argument("--publish-reference", action="store_true")
    parser.add_argument("--audit", action="append", type=Path, default=[])
    parser.add_argument("--audit-sha256", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not (args.check_readiness or args.validate_leg or args.publish_reference):
        print(json.dumps(dict(mode="PLAN_ONLY_NO_EVIDENCE_READS", reference_labels=LABELS,
            cohort_s=1200, timeout_s=2400, launch=False, controls=False)))
        return 0
    require(args.output is not None, "Explicit new output path required")
    if args.check_readiness:
        require(not args.audit and not args.audit_sha256, "Readiness accepts no future leg/audit inputs")
        _, evidence, _, plan, _, seen = context()
        report = dict(schema="robotron-quality1200-readiness-v1", ready_for_ROOT_launch_review=True,
            private_launch_authorized=False, source_model_payload_rehashed=False, Torch_imported=False,
            original_history=dict(receipts=26, games=len(seen)), reference_labels=LABELS,
            plan_sha256=PLAN_SHA, root_design=plan["root_design"], deferred_launch_contract=plan["deferred_launch_contract"],
            backend=plan["backend"], scope="Existing source/boot/shim/metadata/stat and completed history only; ROOT separately verifies idleGPU0/port/highslots/main safety and owns explicit launch.")
    else:
        labels = [args.validate_leg] if args.validate_leg else list(LABELS)
        report, evidence = build(labels, args.audit, args.audit_sha256, single=bool(args.validate_leg))
    if args.publish_reference:
        require(args.output.absolute() == RUN / "quality1200-reference-final.json", "Wrong fixed final reference path")
    print(json.dumps(dict(path=str(args.output), sha256=publish(report, evidence, args.output),
        reference_final=report.get("reference_final", False), launch=False, promotion=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
