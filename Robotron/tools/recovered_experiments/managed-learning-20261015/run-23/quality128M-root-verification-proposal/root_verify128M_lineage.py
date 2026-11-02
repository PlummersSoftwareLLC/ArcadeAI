#!/usr/bin/env python3
"""Prepared root-only CPU verifier; import/help never open future128M data.

Execution requires --verify and independently supplied proposal/checkpoint SHAs.
Only a NEW final lineage JSON is published. No model, gate, state, control,
protected-copy, quality decision, process or source writes are implemented.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
GAME = CAMPAIGN.parents[1]
REPO = GAME.parent
PRECOMMIT_SHA = "f47ec6b41a015e8ea11bcaa96982be80bcb385dbffa61ae75e189c38cddfed31"
CORE = ("training_steps", "optimized_samples", "learner_frame_count")


def require(value, message):
    if not value:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def sha_string(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def identity(path):
    value = Path(path).stat()
    return dict(size=value.st_size, mtime_ns=value.st_mtime_ns, inode=value.st_ino,
                device=value.st_dev, mode=oct(stat.S_IMODE(value.st_mode)), nlink=value.st_nlink)


def integer(value, label):
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"Invalid integer: {label}")
    return value


def interval(before, after, steps_before, steps_after, label, compiler, counters):
    """Saved-clock evidence, deliberately distinct from Adam/outcome evidence."""
    for meta in (before, after):
        for key in CORE:
            integer(meta[key], key)
    updates = after["training_steps"] - before["training_steps"]
    samples = after["optimized_samples"] - before["optimized_samples"]
    learner = after["learner_frame_count"] - before["learner_frame_count"]
    require(updates > 0 and samples == 4096 * updates and learner >= 0,
            f"Recorded4096 exposure/monotonicity differs: {label}")
    for values in (steps_before, steps_after):
        require(values and all(isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) and v >= 0 and float(v).is_integer() for v in values), "Invalid Adam steps")
    require(min(steps_after) >= max(steps_before), "Adam exposure moved backwards")
    same_steps = len(steps_before) == len(steps_after) == 1
    adam_delta = steps_after[0] - steps_before[0] if same_steps else None
    return dict(label=label, compiler=compiler, exposure_counters_enabled=counters,
        recorded_batch_size=4096, logical_updates_delta=updates, optimized_samples_delta=samples,
        learner_frames_delta=learner, Adam_parameter_steps_before=steps_before,
        Adam_parameter_steps_after=steps_after, Adam_uniform_step_delta=adam_delta,
        logical_minus_uniform_Adam_delta=(updates-adam_delta if same_steps else None),
        interpretation="Saved interval clocks; no per-event overflow proof or causal compiler/numeric-equivalence claim.")


def check_exposures(exposure):
    totals = {str(batch): dict(logical_updates=0, optimized_samples=0) for batch in (2048, 4096)}
    for row in exposure["since64M"]:
        batch = row["recorded_batch_size"]
        require(type(batch) is int and batch in (2048, 4096), "Unknown historical batch")
        updates = integer(row["logical_updates_delta"], "exposure updates")
        samples = integer(row["optimized_samples_delta"], "exposure samples")
        require(updates > 0 and samples == updates * batch, "Historical sample/update arithmetic differs")
        totals[str(batch)]["logical_updates"] += updates
        totals[str(batch)]["optimized_samples"] += samples
    require(totals == exposure["totals"], "Historical exposure totals differ")


def counter_evidence(snapshot, baseline, metadata):
    """Optional timestamped API evidence; never pretend it is checkpoint state."""
    result = copy.deepcopy(snapshot["host_pipeline"]["learning_exposure"])
    opt, replay = result["optimizer"], result["replay"]
    for name, value in result.items():
        require(value["enabled"] is True and value["process_id"] == baseline[name]["process_id"]
            and value["instance_monotonic_ns"] == baseline[name]["instance_monotonic_ns"]
            and value["epoch"] == baseline[name]["epoch"] and value["schema"] == baseline[name]["schema"]
            and value["epoch_reason"] == baseline[name]["epoch_reason"], "Counter schema/process/load epoch changed")
    require(opt["supported_torch"] == baseline["optimizer"]["supported_torch"], "Counter supported Torch changed")
    total = opt["total"]
    for key in ("attempts_started", "outcomes_recorded", "applied", "amp_skipped", "unavailable"):
        integer(total[key], key)
        require(total[key] >= baseline["optimizer"]["total"][key], "Optimizer counter moved backwards")
    pending = integer(opt["unclassified_started_total"], "pending")
    require(total["outcomes_recorded"] == total["applied"] + total["amp_skipped"] + total["unavailable"]
        and total["attempts_started"] == total["outcomes_recorded"] + pending and pending <= 1,
        "Counter outcomes/pending arithmetic differs")
    require(opt['since_epoch'] == total and total["unavailable"] == opt["prior_epoch_outcomes_total"] == 0
        and opt["available"] == (pending == 0 and total["outcomes_recorded"] > 0),
        "Unknown counter outcomes or availability differs")
    sources = replay["accepted_by_source_total"]
    require(set(sources) == {"dqn", "epsilon", "expert", "eval", "unattributed"}, "Unknown replay categories")
    for key, value in sources.items():
        integer(value, key)
        require(value >= baseline["replay"]["accepted_by_source_total"][key], "Replay counter moved backwards")
    require(replay['available'] is True and replay['accepted_since_epoch'] == replay['accepted_total'] and replay['accepted_by_source_since_epoch'] == sources and replay['accepted_learner_since_epoch'] == replay['accepted_learner_total'] and replay["accepted_total"] == sum(sources.values())
        and replay["accepted_learner_total"] == sources["dqn"] + sources["epsilon"]
        and sources["unattributed"] == 0, "Replay admission attribution differs")
    clocks = {key: integer(snapshot[key], key) for key in CORE}
    require(all(clocks[key] >= metadata[key] for key in CORE), "Counter snapshot predates saved candidate clocks")
    require(isinstance(snapshot["ts"], (int, float)) and not isinstance(snapshot["ts"], bool)
        and math.isfinite(snapshot["ts"]), "Invalid API timestamp")
    return dict(status="TIMESTAMPED_API_EVIDENCE_ONLY", snapshot_ts=snapshot["ts"],
        API_clocks=clocks, clocks_after_saved_candidate={k:clocks[k]-metadata[k] for k in CORE},
        counters=result, limitation="Not persisted in checkpoint and not atomic with its saved clocks. Applied means call admitted, not every parameter moved; no exact candidate-time AMP/Adam reconciliation is inferred.")


def tensor_walk(value, torch):
    if torch.is_tensor(value):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from tensor_walk(item, torch)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from tensor_walk(item, torch)


def scalar(value, torch):
    if torch.is_tensor(value):
        require(value.device.type == "cpu" and value.numel() == 1, "Non-CPU/non-scalar metadata")
        return scalar(value.item(), torch)
    if isinstance(value, (list, tuple)):
        return [scalar(item, torch) for item in value]
    require(value is None or type(value) in (str, bool, int, float), "Unsupported scalar metadata")
    require(type(value) is not float or math.isfinite(value), "Nonfinite scalar metadata")
    return value


def output_path(requested):
    output = Path(requested).resolve()
    require(output.parent == HERE.parent.resolve() and output.parent.is_dir()
        and output.name.startswith("fresh3-128M-checkpoint-lineage") and output.suffix == ".json"
        and not output.exists(), "Need a NEW run23/fresh3-128M-checkpoint-lineage*.json")
    return output


def check_moments(states, group_ids, online, pinned_order, is_tensor):
    # Pinned v28 geometry: state_dict has99 parameters plus persistent support.
    # Adam receives online_net.parameters() in the same recursive module order.
    names = [name for name in pinned_order if name != "support"]
    require(len(pinned_order) == 100 and "support" in pinned_order and len(names) == 99
        and len(group_ids) == len(set(group_ids)) == 99 and set(online) == set(pinned_order),
        "Cannot bind pinned99 parameter names to Adam IDs")
    parameters = dict(zip(group_ids, names, strict=True))
    require(len(states) == 81 and set(states).issubset(parameters), "Unknown Adam moment owner")
    for owner, row in states.items():
        parameter = online[parameters[owner]]
        for key in ("exp_avg", "exp_avg_sq"):
            value = row[key]
            require(is_tensor(value) and value.shape == parameter.shape and value.dtype == parameter.dtype,
                    "Actual Adam moment does not match its online parameter shape/dtype")


def publish(output, report, evidence):
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=".128M-lineage-", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o444)
        evidence.recheck()
        os.link(temporary, output)  # Atomic exclusive publication; no overwrite.
        os.unlink(temporary)
        directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify(args):
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "", "Hide CUDA before execution")
    require(sha_string(args.proposal_sha256) and sha_string(args.checkpoint_sha256), "Explicit actual64-hex SHAs required")
    output = output_path(args.output)
    started, begin = utc(), time.monotonic()
    manifest_path = HERE / "verification-precommit.json"
    manifest_raw = manifest_path.read_bytes()
    require(hashlib.sha256(manifest_raw).hexdigest() == PRECOMMIT_SHA, "Prepared verification contract changed")
    manifest = json.loads(manifest_raw)
    contract_record = manifest["evidence"]["analyzer"]
    require(sha(contract_record["path"]) == contract_record["sha256"], "Pinned analyzer changed")
    spec = importlib.util.spec_from_file_location("root128_lineage_contract", contract_record["path"])
    contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(contract)
    evidence = contract.Evidence()
    evidence.file(__file__, sha(__file__)); evidence.json(manifest_path, PRECOMMIT_SHA)
    documents = {}
    for label, record in manifest["evidence"].items():
        if Path(record["path"]).suffix == ".json":
            documents[label] = evidence.json(record["path"], record["sha256"])
        else:
            evidence.file(record["path"], record["sha256"])
    plan, old64, old96 = documents["plan"], documents["reference64M"], documents["prior96M"]
    proposal = evidence.json(args.proposal, args.proposal_sha256)
    require(proposal.get("proposal_only") is True and proposal.get("PASS") is True
        and proposal.get("schema") == "robotron-128M-checkpoint-lineage-v1"
        and proposal.get("checks") and all(v is True for v in proposal["checks"].values()), "Need strict proposed128M lineage")
    candidate = proposal["candidate"]; path = Path(candidate["path"]).absolute()
    require(path == Path(plan["candidate"]["checkpoint"]) and path == GAME / manifest["checkpoint"]
        and candidate["sha256"] == args.checkpoint_sha256, "Wrong actual future candidate identity")
    evidence._path(path)
    before = identity(path)
    require(0 < before["size"] <= 512*1024*1024 and before == candidate["stat"], "Actual checkpoint stat differs")
    require(sha(path) == args.checkpoint_sha256, "Actual checkpoint SHA differs")
    evidence.files[str(path)] = args.checkpoint_sha256; evidence.bind_stat(path, before)
    trigger = proposal["trigger_gate"]
    require(Path(trigger["path"]).absolute() == GAME / manifest["gate"], "Wrong gate path")
    gate = evidence.json(trigger["path"], trigger["sha256"])
    require(gate == trigger["record"] and gate["tag"] == "fresh3-128M" and gate["target"] == 132629023
        and gate["experiment"] == "best10M-fresh3-eps10-cap8-nosmooth"
        and Path(gate["checkpoint"]).resolve() == path.resolve(), "Actual gate identity differs")
    for relative, expected in documents["source20_private12"]["source_hashes"].items():
        evidence.file(REPO / relative, expected)
    for relative, expected in documents["source20_private12"]["private12_hashes"].items():
        evidence.file(GAME / relative, expected)
    require(documents["B_guard"]["B_valid"] is False
        and documents["B_guard"]["invalid_window_not_used_for_ABA_selection"] is True, "B rejection history differs")
    environments = [documents[key] for key in ("B_environment", "default_return_environment", "counter_environment")]
    require([env["DQN_COMPILE_MODE"] for env in environments] == ["max-autotune-no-cudagraphs", "default", "default"]
        and environments[-1]["DQN_LEARNING_EXPOSURE_COUNTERS"] == "1", "Recorded compiler/counter chronology differs")
    for before_env, after_env, allowed in ((environments[0], environments[1], {"ROBOTRON_RUN_DIR", "DQN_COMPILE_MODE"}),
            (environments[1], environments[2], {"ROBOTRON_RUN_DIR", "DQN_LEARNING_EXPOSURE_COUNTERS"})):
        require({k for k in before_env.keys() | after_env.keys() if before_env.get(k) != after_env.get(k)} == allowed,
                "Unrecorded environment change in chronology")
    for env in environments:
        require(all(env.get(k) == v for k,v in dict(DQN_BATCH_SIZE="4096", DQN_N_STEP="3",
            DQN_MAX_SAMPLES_PER_FRAME="8", DQN_C51_TARGET_SMOOTHING="0").items()), "Recorded learning recipe differs")
    import torch
    torch.set_num_threads(2); torch.set_num_interop_threads(1)
    require(not torch.cuda.is_initialized(), "CUDA unexpectedly initialized")
    saved = torch.load(path, map_location="cpu", weights_only=True)
    metadata = {key:scalar(saved[key], torch) for key in plan["reference"]["saved_clocks"]}
    require(metadata == candidate["saved_metadata"], "Actual saved metadata differs from proposal")
    previous_meta = old96["candidate"]["saved_metadata"]
    require(metadata["epsilon"] == .1 and math.isclose(metadata["expert_ratio"], .1, abs_tol=1e-12)
        and metadata["lr_gear"] == previous_meta["lr_gear"]
        and metadata["lr_anchor_step"] == previous_meta["lr_anchor_step"], "Actual saved behavior/LR lineage differs")
    controls = evidence.json(proposal["branch_provenance"]["control_path"])
    require(controls == proposal["branch_provenance"]["control_snapshot"]
        and controls["experiment"] == "best10M-fresh3-eps10-cap8-nosmooth" and controls["lr_scale"] == .5
        and controls["epsilon_ramp"]["start"] == controls["epsilon_ramp"]["end"] == .1, "Captured/current branch controls differ")
    for key in ("online_state_dict", "target_state_dict"):
        state = saved[key]
        require(isinstance(state, dict) and state and all(isinstance(k, str) and torch.is_tensor(v) for k,v in state.items()), "Malformed state dictionary")
        signature = {key:dict(shape=list(value.shape), dtype=str(value.dtype)) for key,value in state.items()}
        require(signature == candidate["state_dict_signatures"][key]
            == old64["candidate"]["state_dict_signatures"][key] == old96["candidate"]["state_dict_signatures"][key], "Actual online/target geometry differs")
    tensors = list(tensor_walk(saved, torch))
    require(tensors and all(t.device.type == "cpu" and bool(torch.isfinite(t).all()) for t in tensors), "Saved tensor is non-CPU/nonfinite")
    optimizer = saved["optimizer_state_dict"]
    require(len(optimizer["state"]) == candidate["optimizer"]["state_count"] == 81, "Actual optimizer is not Adam81")
    raw_steps = [scalar(row["step"], torch) for row in optimizer["state"].values()]
    require(all(type(v) in (int,float) and math.isfinite(v) and v >= 0 and float(v).is_integer() for v in raw_steps), "Malformed actual Adam step")
    steps = sorted({float(v) for v in raw_steps})
    require(steps == candidate["optimizer"]["step_values"], "Actual Adam steps differ")
    groups, ids = [], []
    for group in optimizer["param_groups"]:
        ids.extend(group["params"])
        groups.append(dict({k:scalar(v, torch) for k,v in group.items() if k != "params"}, parameter_count=len(group["params"])))
    require(len(ids) == len(set(ids)) == 99 and set(optimizer["state"]).issubset(ids)
        and groups == candidate["optimizer"]["groups"], "Actual Adam groups/IDs differ")
    geometry = lambda rows:[{k:v for k,v in row.items() if k != "lr"} for row in rows]
    require(geometry(groups) == geometry(old64["candidate"]["optimizer"]["groups"])
        == geometry(old96["candidate"]["optimizer"]["groups"]), "Actual Adam group geometry differs")
    check_moments(optimizer["state"], ids, saved["online_state_dict"],
        list(old64["candidate"]["state_dict_signatures"]["online_state_dict"]), torch.is_tensor)
    check_exposures(proposal["actual_recorded_batch_exposure"])
    old_rows = old96["actual_recorded_batch_exposure"]["since64M"]
    rows = proposal["actual_recorded_batch_exposure"]["since64M"]
    require(len(rows) == len(old_rows)+1 and rows[:-1] == old_rows, "Prior2048/4096 exposure history changed")
    for key, value in dict(recorded_batch_size=4096,
            logical_updates_delta=metadata["training_steps"]-previous_meta["training_steps"],
            optimized_samples_delta=metadata["optimized_samples"]-previous_meta["optimized_samples"],
            learner_frames_delta=metadata["learner_frame_count"]-previous_meta["learner_frame_count"]).items():
        require(rows[-1][key] == value, "Proposed96M->128M exposure differs from actual saved clocks")
    points = [(old96["candidate"]["saved_metadata"], old96["candidate"]["optimizer"]["step_values"])]
    for key in ("B_start", "B_end_default_return_start", "default_return_end_counters_start"):
        anchor = documents[key]; points.append((anchor["saved_metadata"], anchor["optimizer_parameter_steps"]))
    points.append((metadata, steps))
    labels = ["96M -> default beforeB", "run21 B (rejected performance leg; weights retained)", "run22 default return", "run23 default + exposure counters -> actual128M"]
    modes = ["default", "max-autotune-no-cudagraphs", "default", "default"]
    chronology = [interval(points[i][0], points[i+1][0], points[i][1], points[i+1][1], labels[i], modes[i], i==3) for i in range(4)]
    require(sum(row["optimized_samples_delta"] for row in chronology) == metadata["optimized_samples"]-old96["candidate"]["saved_metadata"]["optimized_samples"], "Chronology does not span96M ->128M")
    report = copy.deepcopy(proposal)
    report["proposal_only"] = False
    report["branch_provenance"]["compiler_and_instrumentation_chronology"] = chronology
    report["counter_exposure_evidence"] = dict(status="NOT_PERSISTED_IN_CHECKPOINT; no explicit API snapshot supplied")
    if args.counter_snapshot:
        require(sha_string(args.counter_snapshot_sha256), "Counter snapshot requires explicit SHA")
        snapshot = evidence.json(args.counter_snapshot, args.counter_snapshot_sha256)
        report["counter_exposure_evidence"] = counter_evidence(snapshot, documents["counter_prefleet"]["learning_exposure"], metadata)
    else:
        require(args.counter_snapshot_sha256 is None, "Counter SHA supplied without snapshot")
    report["root_verification"] = dict(status="PASS", started_utc=started, finished_utc=utc(),
        elapsed_s=time.monotonic()-begin, method="Independent root CPU checkpoint load, actual SHA/stat, metadata, all finiteCPU tensors, geometry, Adam81/groups/steps, pinned gate,4096 exposure and compiler/source chronology.",
        CUDA_VISIBLE_DEVICES="", CUDA_initialized=torch.cuda.is_initialized(), torch_threads=torch.get_num_threads(),
        torch_version=torch.__version__,
        proposal_sha256=args.proposal_sha256, verifier_sha256=sha(__file__), precommit_sha256=PRECOMMIT_SHA,
        saved_tensor_count=len(tensors), optimizer_parameter_steps=steps)
    report["checks"].update(root_independent_CPU_verification=True, all_saved_tensors_finite_CPU=True,
        recorded_compiler_source_chronology_verified=True)
    contract.lineage_identity(report, path, plan["reference"]["saved_clocks"])
    require(identity(path) == before and not torch.cuda.is_initialized(), "Candidate identity/CUDA guard changed")
    report["root_verification_evidence"] = evidence.snapshot()
    report["limitations"].extend(["96M->128M includes rejectedB compiler exposure followed by default; no rollback, causal compiler attribution or whole-interval numeric equivalence is inferred.",
        "Exposure counters are process-local and not checkpoint state; logical/sample clocks, Adam parameter steps and separately timestamped AMP outcomes are not interchangeable."])
    publish(output, report, evidence)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--proposal-sha256")
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--counter-snapshot", type=Path)
    parser.add_argument("--counter-snapshot-sha256")
    args = parser.parse_args()
    if not args.verify:
        parser.print_help(); return
    if args.proposal is None or args.output is None:
        parser.error("--verify requires --proposal and --output")
    try:
        result = verify(args)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Root128M verification rejected: {error}\n")
    print(json.dumps(dict(PASS=True, path=str(args.output), sha256=sha(args.output),
        checkpoint_sha256=result["candidate"]["sha256"], root_verification=result["root_verification"])))


if __name__ == "__main__":
    main()
