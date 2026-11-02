#!/usr/bin/env python3
"""Prospective1200s224M/256M assessment. Default/import/help are inert.

Explicit ROOT analysis reads only named FINAL receipts and a SHA-pinned FINAL
two-leg reference. No launch, model load, protection, promotion, control or state.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RUN, CAMPAIGN = HERE.parent, HERE.parents[1]
PLAN_SHA = "1a37bcbe99844a56f76bd5f5d70476e22fd38368423c7d32a011f83c5420275e"
REFERENCE_SHA = "62370f2a77facc20b75777b47de3c06f3dfdfa8210133e39b8d9dcbdd5c6251b"
LABELS = {"224M": ("sidecar-gpu0-224M-regression-guard1200-01",),
          "256M": ("sidecar-gpu0-256M-screen1200-01", "sidecar-gpu0-256M-confirm1200-01")}
SLOTS = list(range(4096, 4112))
EXPERIMENT = "best10M-fresh3-eps10-cap8-nosmooth"


def require(ok, why):
    if not ok:
        raise ValueError(why)


def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def context():
    path = HERE / "quality1200_reference.py"
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == REFERENCE_SHA, "Changed frozen reference helper")
    spec = importlib.util.spec_from_file_location("assessment1200_reference", path)
    ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)
    require(path.read_bytes() == raw, "Reference helper changed during import")
    shared, evidence, tools, base, history, seen = ref.context()
    evidence.file(path, REFERENCE_SHA)
    evidence.file(__file__, shared.digest(__file__))
    plan = evidence.json(HERE / "quality1200-assessment-plan.json", PLAN_SHA)
    require(plan["schema"] == "robotron-quality1200-assessment-plan-v1"
        and plan["reference_plan"]["sha256"] == ref.PLAN_SHA
        and plan["reference_helper"]["sha256"] == REFERENCE_SHA
        and plan["reference_publication"]["exact_source_labels"] == list(ref.LABELS)
        and all(plan["roles"][role]["labels"] == list(labels) for role, labels in LABELS.items()), "Changed fixed role/reference contract")
    require(plan["root_design"] == base["root_design"] and plan["history"] == base["history"], "Changed design/history")
    for key in ("lineage_verifier", "lineage_precommit", "lineage_independent_review"):
        evidence.file(plan[key]["path"], plan[key]["sha256"])
    adopted = evidence.json(plan["lineage_root_adoption"]["path"], plan["lineage_root_adoption"]["sha256"])
    require(adopted["root_adopts"] is True
        and adopted["files"]["verify_future_checkpoint_cpu.py"] == plan["lineage_verifier"]
        and adopted["files"]["future-cpu-precommit.json"] == plan["lineage_precommit"], "CPU verifier was not ROOT-adopted")
    return ref, shared, evidence, tools, base, plan, seen


def validate_leg(receipt, label, identity, base, evidence, tools, shared, *, verify_new_copy, expected_protocol=None):
    """Same official full-row/backend contract; old reference bodies are attested."""
    leg = tools.validate_backend(receipt, verify_checkpoint=False)
    require(expected_protocol is None or leg["protocol"] == expected_protocol, "Official wire/frame/evaluation protocol differs")
    require(receipt["label"] == label and receipt["phase"] == "finished" and receipt["reason"] is None
        and receipt["receipt_validator"] == "passed", "Need named FINAL validated cohort")
    require(receipt["checkpoint_sha256"] == identity["sha256"]
        and receipt["source_checkpoint_path"] == receipt["job"]["checkpoint"] == identity["path"], "Wrong explicit policy identity")
    if verify_new_copy:
        evidence.file(receipt["checkpoint_path"], identity["sha256"])
    expected = base["backend"]
    require({key: receipt["job"][key] for key in tools.JOB_FIELDS} == expected["job"], "Changed1200/2400 private job protocol")
    require(all(receipt[key] == expected[key] for key in ("numeric_policy", "runtime", "source_hashes"))
        and receipt["boot_assets"]["identity"] == expected["boot_identity"]
        and receipt["boot_assets"]["files"] == expected["boot_files"]
        and receipt["socket_wait"]["sha256"] == expected["socket_wait_sha256"]
        and all(row["activation_count"] == 1 for row in receipt["socket_wait"]["actors"].values()), "Changed numeric/source/boot/shim backend")
    saved = identity["metadata"]
    require(receipt["checkpoint_metadata"].get("defaulted_metadata_fields") == []
        and all(receipt["checkpoint_metadata"].get(key) == saved[key] for key in shared.META_KEYS), "Saved policy metadata differs")
    for key in shared.CORE_CLOCKS:
        alias = "learner_frames" if key == "learner_frame_count" else key
        require(receipt["clocks"][key] == leg["clocks"][alias] == saved[key], "Within-leg frozen clocks differ")
    boundary = receipt["boundary"]
    require(boundary["clients"] == boundary["expected"] == boundary["acknowledged"] == 16
        and boundary["generation"] == boundary["requested_generation"] == receipt["generation"]
        and sorted(boundary["actor_slots"]) == leg["expected_actor_slots"] == SLOTS
        and sorted({r["client_slot"] for r in leg["rows"]}) == SLOTS, "Incomplete16-slot boundary")
    require(math.isclose(leg["close_ts"] - leg["start_ts"], 1200, abs_tol=1e-6)
        and all(row["boundary_reason"] == "wire_lives_exhausted" and row["end_unix_s"] <= receipt["ended_unix_s"]
            for row in leg["rows"]), "Incomplete natural late tails")
    actual = shared.summarize(leg["rows"])
    require(all(math.isclose(actual[k], receipt[k], rel_tol=1e-12, abs_tol=1e-8) for k in ("mean", "median", "sd", "se")), "Receipt arithmetic differs")
    return leg


def add_ids(rows, label, seen):
    for row in rows:
        require(row["journal_game_id"] not in seen, "Global original game ID overlap")
        seen[row["journal_game_id"]] = label


def read_reference(reference_sha, ref, shared, evidence, tools, base, plan, seen):
    path = plan["reference_publication"]["path"]
    report = evidence.json(path, reference_sha)
    require(report["schema"] == "robotron-quality1200-192M-reference-v1"
        and report["reference_final"] is report["usable_as_new_reference"] is True
        and report["plan_sha256"] == ref.PLAN_SHA
        and [s["label"] for s in report["sources"]] == list(ref.LABELS)
        and report["protected_policy"] == base["reference"] and report["backend"] == base["backend"]
        and report["no_score_threshold_or_reference_selection"] is True
        and report["all_original_fulltails_retained"] is True
        and report["no_fabricated_measurement_receipt"] is True
        and all(report[k] is False for k in ("promotion", "protection", "state_or_control_changes")), "Not the exact complete fixed two-leg reference")
    identity = dict(path=base["reference"]["checkpoint"]["path"], sha256=base["reference"]["checkpoint"]["sha256"],
        metadata=base["reference"]["saved_metadata"])
    require(len(report["final_isolation_audits"]) == 2, "Missing reference final audits")
    rows, protocol = [], None
    for source, audit in zip(report["sources"], report["final_isolation_audits"]):
        receipt = evidence.json(source["path"], source["sha256"])
        leg = validate_leg(receipt, source["label"], identity, base, evidence, tools, shared, verify_new_copy=False)
        if protocol is None:
            protocol = leg["protocol"]
        require(leg["protocol"] == protocol, "Reference legs use different official frame protocols")
        require(audit["label"] == source["label"], "Reference audit labels differ")
        ref.positive_audit(evidence.json(audit["path"], audit["sha256"]), source["sha256"], identity["sha256"])
        add_ids(leg["rows"], source["label"], seen); rows.extend(leg["rows"])
    require(report["original_rows"] == rows and report["original_row_pool"] == tools.summarize(rows, ref.LABELS)
        and report["global_ids"] == dict(receipts=28, games=len(seen), overlaps=0), "Reference omitted/reweighted/changed original rows")
    return dict(report, _validated_protocol=protocol), rows


def lineage_identity(role, report, plan, base, evidence):
    spec = plan["roles"][role]
    require(report["schema"] == spec["lineage_schema"] and report["proposal_only"] is False
        and report["PASS"] is True and report["checks"] and all(value is True for value in report["checks"].values())
        and report["root_verification"]["status"] == "PASS" and report["root_verification"]["CUDA_initialized"] is False,
        "Need FINAL root CPU-verified candidate lineage")
    proof = report["root_verification"]
    require(proof["verifier_sha256"] == plan["lineage_verifier"]["sha256"]
        and proof["precommit_sha256"] == plan["lineage_precommit"]["sha256"]
        and proof["model_body_reads"] == proof["model_CPU_loads"] == 1
        and proof["CUDA_VISIBLE_DEVICES"] == "", "Wrong adopted single-load CPU verifier")
    candidate, prior = report["candidate"], base["reference"]["saved_metadata"]
    require(candidate["path"] == spec["checkpoint"] and valid_sha(candidate["sha256"])
        and candidate["all_network_optimizer_tensors_finite"] is True, "Wrong finite CPU policy identity")
    meta = candidate["saved_metadata"]
    require(all(type(meta[k]) is int and meta[k] >= 0 for k in (*base_meta_keys(), "baseline_batch_size"))
        and meta["baseline_batch_size"] == 512 and meta["total_training_steps"] == meta["training_steps"]
        and meta["learner_frame_count"] >= spec["target"]
        and all(meta[k] > prior[k] for k in ("training_steps", "optimized_samples", "learner_frame_count"))
        and meta["frame_count"] >= meta["learner_frame_count"] and meta["measurement_frame_count"] >= prior["measurement_frame_count"]
        and meta["last_target_update_samples"] <= meta["optimized_samples"], "Malformed/rewound candidate clocks")
    require(all(meta[k] == prior[k] for k in ("engine_version", "state_size", "single_frame_state_size", "frame_stack", "lr_gear", "lr_anchor_step"))
        and meta["epsilon"] == .1 and math.isclose(meta["expert_ratio"], .1, abs_tol=1e-12), "Changed architecture or behavior/LR recipe")
    opt, old_opt = candidate["optimizer"], base["reference"]["optimizer"]
    require(opt["state_count"] == 81 and opt["all_tensors_CPU"] is True and opt["tensor_count"] == 243
        and opt["step_values"] and all(type(x) in (int, float) and math.isfinite(x) and float(x).is_integer()
            and max(old_opt["step_values"]) <= x <= meta["training_steps"] for x in opt["step_values"]), "Invalid saved Adam81 exposure")
    geometry = lambda groups: [{k:v for k,v in group.items() if k != "lr"} for group in groups]
    require(geometry(opt["groups"]) == geometry(old_opt["groups"])
        and all(type(g["lr"]) in (int,float) and math.isfinite(g["lr"]) and g["lr"] > 0 for g in opt["groups"]), "Changed Adam geometry")
    gate = report["trigger_gate"]
    require(gate["path"] == spec["gate_path"] and evidence.json(gate["path"], gate["sha256"]) == gate["record"]
        and gate["record"]["tag"] == "fresh3-" + role and gate["record"]["target"] == spec["target"]
        and gate["record"]["checkpoint"] == spec["checkpoint"] and gate["record"]["experiment"] == EXPERIMENT, "Wrong candidate gate lineage")
    branch = report["branch_provenance"]
    held = branch["held_recipe"]
    require(branch["experiment"] == EXPERIMENT and branch["compile_mode"] == "default"
        and branch["exposure_counters_enabled"] is True and held["batch_size"] == 4096 and held["n_step"] == 3
        and held["max_samples_per_frame"] == 8 and held["lr_scale"] == .5 and held["epsilon"] == .1
        and math.isclose(held["expert_ratio"], .1, abs_tol=1e-12), "Changed held learning recipe")
    core = lambda rows: [{key: row[key] for key in ("path", "sha256", "saved_metadata")} for row in rows]
    require(core(branch["collector_resume_chronology"]) == core(plan["collector_resume_chronology"]), "Collector chronology differs")
    for row in plan["collector_resume_chronology"]:
        require(evidence.json(row["path"], row["sha256"])["saved_metadata"] == row["saved_metadata"], "Changed pinned collector resume anchor")
    exposure = report["actual_recorded_batch_exposure"]["since192M"]
    require(exposure["recorded_batch_size"] == 4096
        and exposure["logical_updates_delta"] == meta["training_steps"] - prior["training_steps"]
        and exposure["optimized_samples_delta"] == meta["optimized_samples"] - prior["optimized_samples"]
        and exposure["learner_frames_delta"] == meta["learner_frame_count"] - prior["learner_frame_count"]
        and exposure["optimized_samples_delta"] == 4096 * exposure["logical_updates_delta"]
        and report["counter_exposure_evidence"]["available"] is False, "Saved4096 clocks or separate-counter scope differ")
    evidence.bind_stat(candidate["path"], candidate["stat"])
    return dict(path=candidate["path"], sha256=candidate["sha256"], metadata=meta, optimizer=opt)


def base_meta_keys():
    return ("training_steps", "optimized_samples", "learner_frame_count", "engine_version", "state_size",
        "single_frame_state_size", "frame_stack", "frame_count", "measurement_frame_count", "total_training_steps", "last_target_update_samples")


def decisions(role, reference_rows, candidates, shared):
    if role == "256M":
        result = shared.decisions(reference_rows, candidates)
        result["rule"] = "Both fixed256M legs independently mean>=1.05NEW1200s192M mean and median>=NEWreference median; same criterion below90% in both is numerical regression. No pooled rescue, third valid cohort, automatic plateau or control."
        return result
    require(len(candidates) == 1, "224M is exactly one guard, never an N-trigger confirmation")
    base = shared.summarize(reference_rows)
    label, rows = next(iter(candidates.items()))
    current = shared.summarize(rows)
    mean_alarm, median_alarm = current["mean"] < .9 * base["mean"], current["median"] < .9 * base["median"]
    severe = current["mean"] < .8 * base["mean"] and median_alarm
    return dict(status="single_guard_severe_ROOT_damage_review" if severe else "single_guard_alarm_ROOT_watch" if mean_alarm or median_alarm else "single_guard_no_alarm_continue_fixed256M",
        reference=base, thresholds=dict(mean=.9*base["mean"],median=.9*base["median"],severe_mean=.8*base["mean"]),
        each_leg=[dict(label=label,**current,mean_alarm=mean_alarm,median_alarm=median_alarm,severe_alert=severe,low_N=len(rows)<64)],
        maximum_valid_legs=1, maximum_valid_legs_reached=True, confirmation_still_needed=False,
        additional_valid_guard_authorized=False, promotion_eligible=False, promotion=False, reference_rebased=False,
        plateau_declared=False, learning_knob_change_authorized=False, automatic_action=False,
        rule="Exactly one valid224M guard; N<64 precision only. Severe <80%mean AND <90%median requests ROOT damage review, other <90%alarm requests ROOT watch; no automatic rollback/LR/promotion/rebase/plateau or extra cohort.")


def build(role, labels, reference_sha, lineage_path, lineage_sha, audit_paths, audit_shas, guard_sha=None):
    require(role in LABELS and ((role == "224M" and tuple(labels) == LABELS[role]) or
        (role == "256M" and 1 <= len(labels) <= 2 and tuple(labels) == LABELS[role][:len(labels)])), "Wrong fixed assigned labels/cardinality")
    require(valid_sha(reference_sha) and valid_sha(lineage_sha)
        and len(labels) == len(audit_paths) == len(audit_shas) and all(valid_sha(x) for x in audit_shas)
        and (role != "256M" or valid_sha(guard_sha)), "Explicit final reference/lineage/audit/guard SHA pins required")
    ref, shared, evidence, tools, base, plan, seen = context()
    reference_report, reference_rows = read_reference(reference_sha, ref, shared, evidence, tools, base, plan, seen)
    additional_guard = None
    if role == "256M":
        additional_guard = evidence.json(plan["roles"]["224M"]["output"], guard_sha)
        require(additional_guard["schema"] == "robotron-quality1200-assessment-v1" and additional_guard["role"] == "224M"
            and additional_guard["validity_passed"] is True and additional_guard["reference_publication"]["sha256"] == reference_sha
            and [s["label"] for s in additional_guard["sources"]] == list(LABELS["224M"])
            and additional_guard["management"]["promotion"] is False
            and additional_guard["management"]["reference_rebased"] is False, "Need the completed unpromoted single224M guard history")
        guard_lineage = evidence.json(additional_guard["lineage"]["path"], additional_guard["lineage"]["sha256"])
        guard_identity = lineage_identity("224M", guard_lineage, plan, base, evidence)
        require(len(additional_guard["final_isolation_audits"]) == 1, "Guard audit missing")
        for source, audit in zip(additional_guard["sources"], additional_guard["final_isolation_audits"]):
            old = evidence.json(source["path"], source["sha256"])
            old_leg = validate_leg(old, source["label"], guard_identity, base, evidence, tools, shared, verify_new_copy=False,
                expected_protocol=reference_report["_validated_protocol"])
            ref.positive_audit(evidence.json(audit["path"], audit["sha256"]), source["sha256"], guard_identity["sha256"])
            add_ids(old_leg["rows"], source["label"], seen)
    lineage = evidence.json(lineage_path, lineage_sha)
    identity = lineage_identity(role, lineage, plan, base, evidence)
    candidates, sources, audits = {}, [], []
    for label, audit_path, audit_sha in zip(labels, audit_paths, audit_shas):
        path = CAMPAIGN / label / "receipt.json"
        receipt = evidence.json(path)
        receipt_sha = evidence.files[str(path.absolute())]
        leg = validate_leg(receipt, label, identity, base, evidence, tools, shared, verify_new_copy=True,
            expected_protocol=reference_report["_validated_protocol"])
        ref.positive_audit(evidence.json(audit_path, audit_sha), receipt_sha, identity["sha256"])
        add_ids(leg["rows"], label, seen)
        candidates[label] = leg["rows"]
        sources.append(dict(label=label,path=str(path),sha256=receipt_sha))
        audits.append(dict(label=label,path=str(Path(audit_path).absolute()),sha256=audit_sha))
    comparisons = {label:tools.analyze_rows(reference_rows,rows,ref.LABELS,[label],10000) for label,rows in candidates.items()}
    pooled = [row for rows in candidates.values() for row in rows]
    report = dict(schema="robotron-quality1200-assessment-v1",utc=datetime.now(timezone.utc).isoformat(),role=role,
        validity_passed=True, plan_sha256=PLAN_SHA, reference_publication=dict(path=plan["reference_publication"]["path"],sha256=reference_sha),
        reference_original_denominator=len(reference_rows),matched_frozen_protocol=reference_report["_validated_protocol"],
        sources=sources, final_isolation_audits=audits,
        lineage=dict(path=str(Path(lineage_path).absolute()),sha256=lineage_sha), policy_identity=identity,
        management=decisions(role,reference_rows,candidates,shared), each_candidate_vs_reference=comparisons,
        descriptive_candidate_pool_vs_reference=(comparisons[labels[0]] if len(labels)==1 else tools.analyze_rows(reference_rows,pooled,ref.LABELS,labels,10000)),
        global_ids=dict(receipts=28+int(role=="256M")+len(labels),games=len(seen),overlaps=0),
        completed224_guard_history=None if additional_guard is None else dict(path=plan["roles"]["224M"]["output"],sha256=guard_sha,pooled_into_reference=False),
        branch_provenance=lineage["branch_provenance"],actual_recorded_batch_exposure=lineage["actual_recorded_batch_exposure"],
        process_counter_evidence=lineage["counter_exposure_evidence"], fixed_bootstrap_iterations=10000,
        original_full_denominators={label:len(rows) for label,rows in candidates.items()},
        all_original_fulltails_retained=True,no_fabricated_measurement_receipt=True,promotion=False,protection=False,state_or_control_changes=False,
        evidence=evidence.snapshot(),caveats=["Only new1200s two-leg192M reference rows enter comparisons; historical600s and224M guard remain separate history.",
            "Fixed10000 game/paired-slot sensitivities and SE are descriptive, not formal confidence/repeated-look correction or a causal batch/compiler estimate.",
            "N<64 precision only.224M exactly one;256M two fixed valid legs regardless first quality, no extra N-trigger cohort/count extension/pooling rescue/automatic plateau.",
            "Old reference/guard model payload identity reuses completed root validation attestations; only new candidate private copies are rehashed. Final saved CPU/Adam clocks and process counters remain separate.",
            "ROOT alone interprets results and may later protect/promote; this report performs no launch/control/model/state action."])
    evidence.recheck()
    return report, evidence


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyze",action="store_true")
    parser.add_argument("--role",choices=LABELS)
    parser.add_argument("--label",action="append",default=[])
    parser.add_argument("--reference-sha256")
    parser.add_argument("--lineage",type=Path)
    parser.add_argument("--lineage-sha256")
    parser.add_argument("--audit",action="append",type=Path,default=[])
    parser.add_argument("--audit-sha256",action="append",default=[])
    parser.add_argument("--guard-analysis-sha256")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if not args.analyze:
        print(json.dumps(dict(mode="PLAN_ONLY_NO_EVIDENCE_READS",roles=LABELS,launch=False,promotion=False)))
        return 0
    require(args.lineage is not None and args.output is not None,"Explicit final lineage/output paths required")
    report,evidence=build(args.role,args.label,args.reference_sha256,args.lineage,args.lineage_sha256,args.audit,args.audit_sha256,args.guard_analysis_sha256)
    expected=RUN/("quality1200-224M-guard-final-analysis.json" if args.role=="224M" else
        "quality1200-256M-first-analysis.json" if len(args.label)==1 else "quality1200-256M-two-leg-final-analysis.json")
    require(args.output.absolute()==expected,"Wrong fixed role/cardinality output path")
    path=HERE/"quality1200_reference.py"
    spec=importlib.util.spec_from_file_location("quality1200_final_json_publisher",path)
    ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
    print(json.dumps(dict(path=str(args.output),sha256=ref.publish(report,evidence,args.output),management=report["management"]["status"],promotion=False)))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
