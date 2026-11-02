#!/usr/bin/env python3
"""Prepared root-only CPU verifier; import/help never open future160M data.

Execution requires --verify and independently supplied proposal/checkpoint/runtime SHAs.
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
PRECOMMIT_SHA = "a434cc1b816d9c1ab29173ef01e8df6d9228d02f3738445f456f4a16d0013040"
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
    require(not Path(requested).is_symlink(), "Final lineage output cannot be a symlink")
    output = Path(requested).resolve()
    require(output.parent == HERE.parent.resolve() and output.parent.is_dir()
        and output.name.startswith("fresh3-160M-checkpoint-lineage") and output.suffix == ".json"
        and not output.exists(), "Need a NEW run23/fresh3-160M-checkpoint-lineage*.json")
    return output


def check_moments(states, group_ids, online, pinned_order, is_tensor):
    # Pinned v28 geometry: state_dict has99 parameters plus persistent support.
    # Adam receives online_net.parameters() in the same recursive module order.
    names = [name for name in pinned_order if name != "support"]
    require(len(pinned_order) == 100 and "support" in pinned_order and len(names) == 99
        and all(type(owner) is int for owner in group_ids)
        and len(group_ids) == len(set(group_ids)) == 99 and set(online) == set(pinned_order),
        "Cannot bind pinned99 parameter names to Adam IDs")
    parameters = dict(zip(group_ids, names, strict=True))
    require(len(states) == 81 and all(type(owner) is int for owner in states)
        and set(states).issubset(parameters), "Unknown Adam moment owner")
    for owner, row in states.items():
        parameter = online[parameters[owner]]
        for key in ("exp_avg", "exp_avg_sq"):
            value = row[key]
            require(is_tensor(value) and value.shape == parameter.shape and value.dtype == parameter.dtype,
                    "Actual Adam moment does not match its online parameter shape/dtype")


def publish(output, report, evidence):
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=".160M-lineage-", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
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


def process_identity(pid):
    """Read-only continuity guard; an intervening restart requires new review."""
    try:
        parts = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
        require(parts[0] not in ("Z", "X"), "Pinned main process is not running")
        return dict(pid=int(pid), start_ticks=int(parts[19]))
    except (OSError, IndexError, ValueError) as error:
        raise ValueError("Pinned run23 process is gone or changed; review restart chronology") from error


def process_environment(pid):
    try:
        values = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        return dict(value.decode().split("=", 1) for value in values if b"=" in value)
    except (OSError, UnicodeError) as error:
        raise ValueError("Cannot inspect pinned main environment") from error


def verify(args):
    # Check all explicit arguments before any future proposal/checkpoint/gate read
    # or Torch import. Root supplies these values after actual capture.
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "", "Hide CUDA before execution")
    require(all(sha_string(value) for value in (args.proposal_sha256, args.checkpoint_sha256,
        args.runtime_metadata_sha256)), "Explicit actual proposal/checkpoint/runtime64-hex SHAs required")
    require(args.proposal is not None and args.checkpoint is not None and args.runtime_metadata is not None,
        "Explicit actual proposal/checkpoint/runtime paths required")
    output = output_path(args.output)
    started, begin = utc(), time.monotonic()
    manifest_path = HERE / "verification-precommit.json"
    manifest_raw = manifest_path.read_bytes()
    require(hashlib.sha256(manifest_raw).hexdigest() == PRECOMMIT_SHA, "Prepared verification contract changed")
    manifest = json.loads(manifest_raw)
    contract_record = manifest["evidence"]["analyzer"]
    require(sha(contract_record["path"]) == contract_record["sha256"], "Pinned analyzer changed")
    spec = importlib.util.spec_from_file_location("root160_lineage_contract", contract_record["path"])
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    evidence = contract.Evidence()
    evidence.file(__file__, sha(__file__))
    evidence.json(manifest_path, PRECOMMIT_SHA)
    documents = {}
    for label, record in manifest["evidence"].items():
        if Path(record["path"]).suffix == ".json":
            documents[label] = evidence.json(record["path"], record["sha256"])
        else:
            evidence.file(record["path"], record["sha256"])
    plan, reference = documents["plan"], documents["reference128M"]
    require(reference.get("proposal_only") is False and reference.get("PASS") is True
        and reference.get("checks") and all(value is True for value in reference["checks"].values())
        and reference["root_verification"]["status"] == "PASS"
        and reference["root_verification"]["CUDA_initialized"] is False, "Need final root CPU128M reference")
    protected = plan["reference"]["checkpoint"]
    previous = reference["candidate"]["saved_metadata"]
    require(previous == plan["reference"]["saved_clocks"]
        and reference["candidate"]["sha256"] == protected["sha256"]
        and documents["protected128_metadata"]["sha256"] == protected["sha256"]
        and documents["protected128_metadata"]["saved_checkpoint_metadata"] == previous,
        "Pinned protected128M metadata differs")
    require(documents["root128_promotion"]["PASS"] is True
        and documents["root128_promotion"]["new_incumbent"]["sha256"] == protected["sha256"],
        "128M promotion provenance differs")
    require(documents["root_plan_adoption"]["status"] == "ROOT_ADOPTED_PLAN_AND_ANALYZER_BEFORE_ACTUAL160M_BYTES"
        and documents["root_plan_adoption"]["files"]["analyze160M_guard.py"] == contract_record["sha256"],
        "160M plan/analyzer adoption differs")
    require(documents["root_capture_adoption"]["status"] == "ROOT_ADOPTED_PROSPECTIVE_CPU_CAPTURE_LOADER_BEFORE_ACTUAL160M"
        and documents["root_capture_adoption"]["files"]["capture160M_lineage_proposal.py"]
            == manifest["evidence"]["capture_loader"]["sha256"], "160M CPU capture adoption differs")
    runtime_record = manifest["evidence"]["runtime_metadata"]
    require(Path(args.runtime_metadata).absolute() == Path(runtime_record["path"]).absolute()
        and args.runtime_metadata_sha256 == runtime_record["sha256"],
        "Runtime/restart changed; require separately reviewed chronology")
    runtime = evidence.json(args.runtime_metadata, args.runtime_metadata_sha256)
    require(runtime == documents["runtime_metadata"], "Current runtime metadata differs")
    config, environment = runtime["config"], runtime["environment"]
    require(environment == documents["run23_environment"]
        and environment == documents["source20_private12"]["environment"], "Recorded environment changed")
    wanted = dict(DQN_BATCH_SIZE="4096", DQN_COMPILE_MODE="default", DQN_LEARNING_EXPOSURE_COUNTERS="1",
        DQN_N_STEP="3", DQN_MAX_SAMPLES_PER_FRAME="8", DQN_C51_TARGET_SMOOTHING="0", DQN_STREAM_BANK_OUTPUT="1")
    require(all(environment.get(key) == value for key, value in wanted.items()), "Current compiler/counter recipe differs")
    require(all(config.get(key) == value for key, value in dict(batch_size=4096, baseline_batch_size=512,
        n_step=3, max_samples_per_frame=8.0, c51_target_smoothing=0.0, torch_compile_mode="default").items()),
        "Recorded current learning config differs")
    baseline_process = manifest["expected_process"]
    require(documents["source20_private12"]["PASS"] is True
        and documents["source20_private12"]["pid"] == baseline_process["pid"]
        and documents["source20_private12"]["start_ticks"] == baseline_process["start_ticks"]
        and process_identity(baseline_process["pid"]) == baseline_process,
        "Main restarted; require reviewed continuous branch chronology")
    current_environment = process_environment(baseline_process["pid"])
    require(all(current_environment.get(key) == value for key, value in environment.items()),
        "Pinned main current environment differs")
    application = documents["counter_application"]
    require(application["PASS"] is True and application["reviewed_proposed_bytes_exact"] is True
        and application["guarded_source12_unchanged"] is True
        and set(application["applied_sources"]) == {"agent.py", "replay_buffer.py", "training.py", "learning_exposure.py"},
        "Reviewed four-source exposure application differs")
    source_hashes = documents["source20_private12"]["source_hashes"]
    private_hashes = documents["source20_private12"]["private12_hashes"]
    require(len(source_hashes) == 20 and len(private_hashes) == 12, "Source20/private12 inventory differs")
    for relative, expected in source_hashes.items():
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "Invalid source path")
        evidence.file(REPO / relative, expected)
    for relative, expected in private_hashes.items():
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "Invalid private source path")
        evidence.file(GAME / relative, expected)
    for name, expected in application["applied_sources"].items():
        require(source_hashes.get("Robotron/Scripts/dqn/" + name) == expected,
            "Reviewed exposure bytes differ from current source inventory")

    proposal = evidence.json(args.proposal, args.proposal_sha256)
    require(proposal.get("proposal_only") is True and proposal.get("PASS") is True
        and proposal.get("schema") == "robotron-160M-checkpoint-lineage-v1"
        and isinstance(proposal.get("root_verification"), str)
        and proposal["root_verification"].startswith("PENDING")
        and proposal.get("checks") and all(value is True for value in proposal["checks"].values()),
        "Need strict proposed160M lineage, not a marked final document")
    require(proposal.get("counter_exposure_evidence", {}).get("available") is False,
        "API counters need a separately validated explicit contract; not accepted here")
    candidate = proposal["candidate"]
    path = Path(args.checkpoint).absolute()
    require(path == Path(candidate["path"]).absolute() == Path(plan["candidate"]["checkpoint"])
        and path == GAME / manifest["checkpoint"] and candidate["sha256"] == args.checkpoint_sha256,
        "Wrong actual future checkpoint identity")
    branch = proposal["branch_provenance"]
    require(Path(branch["runtime_metadata_path"]).absolute() == Path(args.runtime_metadata).absolute()
        and branch["runtime_metadata_sha256"] == args.runtime_metadata_sha256
        and branch["recorded_runtime_recipe"] == runtime, "Proposal runtime proof differs")
    evidence._path(path)
    before = identity(path)
    require(0 < before["size"] <= 512*1024*1024 and before == candidate["stat"], "Actual checkpoint stat differs")
    require(sha(path) == args.checkpoint_sha256, "Actual checkpoint SHA differs")
    evidence.files[str(path)] = args.checkpoint_sha256
    evidence.bind_stat(path, before)
    trigger = proposal["trigger_gate"]
    require(Path(trigger["path"]).absolute() == GAME / manifest["gate"], "Wrong gate path")
    gate = evidence.json(trigger["path"], trigger["sha256"])
    require(gate == trigger["record"] and gate["tag"] == "fresh3-160M" and gate["target"] == 164629023
        and gate["experiment"] == "best10M-fresh3-eps10-cap8-nosmooth"
        and Path(gate["checkpoint"]).resolve() == path.resolve(), "Actual gate identity differs")
    require(Path(branch["control_path"]).absolute() == GAME / "models_dqn/learning_control.json",
        "Wrong learning-control path")
    controls = evidence.json(branch["control_path"])
    require(controls == branch["control_snapshot"] and controls["experiment"] == gate["experiment"]
        and controls["lr_scale"] == .5
        and controls["epsilon_ramp"]["start"] == controls["epsilon_ramp"]["end"] == .1,
        "Captured/current branch controls differ")
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    require(not torch.cuda.is_initialized(), "CUDA unexpectedly initialized")
    saved = torch.load(path, map_location="cpu", weights_only=True)
    require(isinstance(saved, dict), "Malformed actual saved checkpoint")
    metadata = {key: scalar(saved[key], torch) for key in previous}
    require(metadata == candidate["saved_metadata"], "Actual saved metadata differs from proposal")
    for key in contract.META_KEYS:
        integer(metadata[key], key)
    require(metadata["baseline_batch_size"] == 512
        and metadata["total_training_steps"] == metadata["training_steps"]
        and metadata["frame_count"] >= max(previous["frame_count"], metadata["learner_frame_count"])
        and metadata["measurement_frame_count"] >= previous["measurement_frame_count"]
        and previous["last_target_update_samples"] <= metadata["last_target_update_samples"] <= metadata["optimized_samples"]
        and metadata["learner_frame_count"] >= 164629023, "Actual saved clocks differ or regressed")
    require(metadata["epsilon"] == previous["epsilon"] == .1
        and math.isclose(metadata["expert_ratio"], .1, abs_tol=1e-12)
        and math.isclose(metadata["expert_ratio"], previous["expert_ratio"], abs_tol=1e-12)
        and metadata["lr_gear"] == previous["lr_gear"], "Actual saved behavior/LR lineage differs")
    require(type(metadata["lr_anchor_step"]) in (int, float) and math.isfinite(metadata["lr_anchor_step"])
        and metadata["lr_anchor_step"] == previous["lr_anchor_step"], "Malformed/changed saved LR anchor")
    for key in ("engine_version", "state_size", "single_frame_state_size", "frame_stack"):
        require(metadata[key] == previous[key], "Actual saved architecture metadata differs")
    for key in ("online_state_dict", "target_state_dict"):
        state = saved[key]
        require(isinstance(state, dict) and state and all(isinstance(name, str) and torch.is_tensor(value)
            for name, value in state.items()), "Malformed actual state dictionary")
        signature = {name: dict(shape=list(value.shape), dtype=str(value.dtype)) for name, value in state.items()}
        pinned = reference["candidate"]["state_dict_signatures"][key]
        require(signature == candidate["state_dict_signatures"][key] == pinned
            and list(state) == list(pinned), "Actual online/target full signature or order differs")
    tensors = list(tensor_walk(saved, torch))
    require(tensors and all(value.device.type == "cpu" and bool(torch.isfinite(value).all().item())
        for value in tensors), "Actual saved tensor non-CPU/nonfinite")
    require(candidate["checkpoint_tensor_count"] == len(tensors) and candidate["tensor_devices"] == ["cpu"]
        and candidate["all_network_optimizer_tensors_finite"] is True, "Proposed tensor inventory differs")
    optimizer = saved["optimizer_state_dict"]
    require(isinstance(optimizer, dict) and isinstance(optimizer.get("state"), dict)
        and isinstance(optimizer.get("param_groups"), list)
        and len(optimizer["state"]) == candidate["optimizer"]["state_count"] == 81, "Actual optimizer is not Adam81")
    raw_steps = [scalar(row["step"], torch) for row in optimizer["state"].values()]
    require(all(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= metadata["training_steps"]
        and float(value).is_integer() for value in raw_steps), "Malformed actual Adam parameter step")
    steps = sorted({float(value) for value in raw_steps})
    require(steps == candidate["optimizer"]["step_values"]
        and candidate["optimizer"]["minimum_parameter_step"] == min(raw_steps)
        and candidate["optimizer"]["maximum_parameter_step"] == max(raw_steps)
        and candidate["optimizer"]["all_tensors_CPU"] is True
        and candidate["optimizer"]["tensor_count"] == len(list(tensor_walk(optimizer, torch))),
        "Actual Adam parameter steps/tensor inventory differ")
    groups, ids = [], []
    for group in optimizer["param_groups"]:
        require(isinstance(group.get("params"), list) and group["params"]
            and all(type(owner) is int for owner in group["params"]), "Malformed actual optimizer parameter IDs")
        ids.extend(group["params"])
        groups.append(dict({key: scalar(value, torch) for key, value in group.items() if key != "params"},
            parameter_count=len(group["params"])))
    require(len(ids) == len(set(ids)) == 99 and set(optimizer["state"]).issubset(ids)
        and groups == candidate["optimizer"]["groups"], "Actual Adam groups/IDs differ")
    require(all(type(group["lr"]) in (int, float) and math.isfinite(group["lr"]) and group["lr"] > 0
        for group in groups), "Malformed actual optimizer learning rate")
    geometry = lambda rows: [{key: value for key, value in row.items() if key != "lr"} for row in rows]
    require(geometry(groups) == geometry(reference["candidate"]["optimizer"]["groups"]),
        "Actual Adam group geometry differs from128M")
    check_moments(optimizer["state"], ids, saved["online_state_dict"],
        list(reference["candidate"]["state_dict_signatures"]["online_state_dict"]), torch.is_tensor)
    chronology = interval(previous, metadata, reference["candidate"]["optimizer"]["step_values"], steps,
        "Protected128M -> actual160M; same run23 process", "default", True)
    expected_exposure = {key: chronology[key] for key in ("recorded_batch_size", "logical_updates_delta",
        "optimized_samples_delta", "learner_frames_delta")}
    require(proposal["actual_recorded_batch_exposure"]["since128M"] == expected_exposure,
        "Proposed128M->160M exposure differs from actual clocks")
    report = copy.deepcopy(proposal)
    report["proposal_only"] = False
    report["branch_provenance"]["compiler_and_instrumentation_chronology"] = [chronology]
    report["branch_provenance"]["prior128M_history"] = dict(
        lineage=manifest["evidence"]["reference128M"],
        compiler_and_instrumentation_chronology=reference["branch_provenance"]["compiler_and_instrumentation_chronology"],
        scope="Historical pre128M default/rejectedB/default/counter exposure is retained verbatim and never relabeled as all-default.")
    report["counter_exposure_evidence"] = dict(available=False,
        reason="No API counters collected or accepted by this verifier; they are process/epoch evidence separate from saved checkpoint/Adam clocks.")
    report["root_verification"] = dict(status="PASS", started_utc=started, finished_utc=utc(),
        elapsed_s=time.monotonic()-begin,
        method="Independent root CPU checkpoint load; actual SHA/stat, all saved finiteCPU tensors, online/target signatures/order, Adam81/groups/99parameter moment geometry/steps, pinned gate/runtime/source20/private12 and same-process4096/default/counter chronology.",
        CUDA_VISIBLE_DEVICES="", CUDA_initialized=torch.cuda.is_initialized(),
        torch_threads=torch.get_num_threads(), torch_version=str(torch.__version__),
        proposal_sha256=args.proposal_sha256, verifier_sha256=sha(__file__), precommit_sha256=PRECOMMIT_SHA,
        runtime_metadata_sha256=args.runtime_metadata_sha256, main_process_identity=baseline_process,
        saved_tensor_count=len(tensors), optimizer_parameter_steps=steps)
    report["checks"].update(root_independent_CPU_verification=True, all_saved_tensors_finite_CPU=True,
        recorded_source20_private12_and_current_environment_verified=True, unchanged_main_process_after128M=True)
    contract.lineage_identity(report, path, plan["reference"]["saved_clocks"])
    require(identity(path) == before and not torch.cuda.is_initialized()
        and process_identity(baseline_process["pid"]) == baseline_process,
        "Candidate/process identity or CUDA guard changed")
    report["root_verification_evidence"] = evidence.snapshot()
    report["limitations"].extend([
        "Only128M->160M is one same-process4096/default/counters interval. Prior128M lineage retains earlier compiler history, including rejectedB; no whole-trajectory numeric or causal equivalence is claimed.",
        "Static recorded/current environment and controls are corroboration, not proof of every historical read. Any restart/source/recipe change requires separately reviewed chronology rather than silent acceptance.",
        "No API outcome collection: logical updates, optimized samples, Adam parameter steps and process-local applied/AMP outcomes remain separate."])
    publish(output, report, evidence)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--proposal-sha256")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--runtime-metadata", type=Path)
    parser.add_argument("--runtime-metadata-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.verify:
        parser.print_help()
        return
    if args.proposal is None or args.checkpoint is None or args.runtime_metadata is None or args.output is None:
        parser.error("--verify requires explicit --proposal, --checkpoint, --runtime-metadata and --output")
    try:
        result = verify(args)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Root160M verification rejected: {error}\n")
    print(json.dumps(dict(PASS=True, path=str(args.output), sha256=sha(args.output),
        checkpoint_sha256=result["candidate"]["sha256"], root_verification=result["root_verification"])))


if __name__ == "__main__":
    main()


