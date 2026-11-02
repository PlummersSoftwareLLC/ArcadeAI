#!/usr/bin/env python3
"""Prepare a CPU-only proposal after BOTH actual96M capture files exist.

No checkpoint is opened at import or --help. This does not publish the final
root lineage report, launch an evaluation, or write a checkpoint/control/state.
Use a fresh process with CUDA_VISIBLE_DEVICES='' and --capture explicitly.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import stat
import sys
import time

RUN = Path(__file__).resolve().parent
CAMPAIGN = RUN.parent
GAME = RUN.parents[2]
GUARD_SHA = "f20c3744d7da535e7cde7875371e5c118a77df097934feecebc4500d99249688"
REFERENCE_LINEAGE_SHA = "2c81a921172d1dcae9f6601660b4f8cc5839b9153d13cc604770dd003a11c2e4"
EXPERIMENT = "best10M-fresh3-eps10-cap8-nosmooth"
TARGET = 100629023
EXPECTED_POLICY = dict(DQN_N_STEP="3", DQN_MAX_SAMPLES_PER_FRAME="8",
                       DQN_C51_TARGET_SMOOTHING="0")


def require(value, message):
    if not value:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def load_contract():
    path = RUN / "analyze96M_guard.py"
    require(sha(path) == GUARD_SHA, "Reviewed analyzer contract changed")
    spec = importlib.util.spec_from_file_location("lineage96_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signature(state, torch):
    require(isinstance(state, dict) and state, "Missing state dictionary")
    require(all(isinstance(name, str) and torch.is_tensor(value) for name, value in state.items()),
            "State dictionary contains a non-tensor")
    require(all(value.device.type == "cpu" for value in state.values()), "Non-CPU network tensor")
    return {name: dict(shape=list(value.shape), dtype=str(value.dtype)) for name, value in state.items()}


def scalar(value, torch):
    if torch.is_tensor(value):
        require(value.device.type == "cpu" and value.numel() == 1, "Invalid scalar optimizer group value")
        return scalar(value.item(), torch)
    if isinstance(value, (tuple, list)):
        return [scalar(item, torch) for item in value]
    require(value is None or isinstance(value, (bool, int, float, str)), "Unsupported scalar metadata type")
    require(not isinstance(value, float) or math.isfinite(value), "Nonfinite scalar metadata")
    return value


def tensor_walk(value, torch):
    if torch.is_tensor(value):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from tensor_walk(item, torch)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from tensor_walk(item, torch)


def optimizer_info(value, torch):
    require(isinstance(value, dict) and isinstance(value.get("state"), dict)
            and isinstance(value.get("param_groups"), list), "Missing optimizer state")
    states = value["state"]
    require(len(states) == 81 and all(isinstance(row, dict) for row in states.values()), "Expected Adam81 states")
    tensors = list(tensor_walk(value, torch))
    require(all(item.device.type == "cpu" for item in tensors), "Non-CPU optimizer tensor")
    steps = []
    for row in states.values():
        step = row["step"]
        step = step.item() if torch.is_tensor(step) and step.numel() == 1 else step
        require(isinstance(step, (int, float)) and not isinstance(step, bool)
            and math.isfinite(step) and step >= 0, "Invalid Adam parameter step")
        steps.append(float(step))
        require(torch.is_tensor(row.get("exp_avg")) and torch.is_tensor(row.get("exp_avg_sq"))
            and row["exp_avg"].shape == row["exp_avg_sq"].shape, "Missing/mismatched Adam moments")
    groups = []
    parameter_ids = []
    for group in value["param_groups"]:
        require(isinstance(group.get("params"), list) and group["params"], "Missing optimizer group parameter IDs")
        parameter_ids.extend(group["params"])
        groups.append(dict({key: scalar(item, torch) for key, item in group.items() if key != "params"},
                           parameter_count=len(group["params"])))
    require(len(parameter_ids) == len(set(parameter_ids)) and set(states).issubset(parameter_ids),
            "Duplicate/unknown optimizer parameter IDs")
    return dict(state_count=len(states), step_values=sorted(set(steps)),
        minimum_parameter_step=min(steps), maximum_parameter_step=max(steps),
        groups=groups, all_tensors_CPU=True, tensor_count=len(tensors)), tensors


def exposure(before, after, configured_batch, label):
    """Clock corroboration, not an invented per-step execution trace."""
    updates = after["training_steps"] - before["training_steps"]
    samples = after["optimized_samples"] - before["optimized_samples"]
    learner = after["learner_frame_count"] - before["learner_frame_count"]
    require(updates > 0 and samples > 0 and learner >= 0, f"Nonmonotone exposure: {label}")
    require(configured_batch in (2048, 4096) and samples == updates * configured_batch,
            f"Saved clock exposure does not match recorded batch: {label}")
    return dict(label=label, recorded_batch_size=configured_batch, logical_updates_delta=updates,
        optimized_samples_delta=samples, learner_frames_delta=learner,
        samples_per_logical_update=samples / updates,
        interpretation="Exact clock delta agrees with the recorded batch; not a per-parameter Adam-step count or per-update trace.")


def group_geometry(groups):
    # LR follows the existing sample-clock schedule; its actual value is kept
    # in the report but need not stay numerically equal to the64M LR.
    return [{key: value for key, value in group.items() if key != "lr"} for group in groups]


def proposed_report(torch, checkpoint, candidate, candidate_sha, before_stat,
                    gate, gate_path, gate_sha, reference, plan, evidence, started,
                    process_start, contract):
    metadata_keys = tuple(plan["reference"]["saved_clocks"])
    metadata = {key: scalar(checkpoint[key], torch) for key in metadata_keys}
    ref = reference["candidate"]
    signatures = {key: signature(checkpoint[key], torch) for key in ("online_state_dict", "target_state_dict")}
    optimizer, optimizer_tensors = optimizer_info(checkpoint["optimizer_state_dict"], torch)
    network_tensors = list(tensor_walk({key: checkpoint[key] for key in signatures}, torch))
    finite = all(not item.is_floating_point() or bool(torch.isfinite(item).all().item())
                 for item in (*network_tensors, *optimizer_tensors))
    require(finite, "Nonfinite saved network/optimizer tensor")
    require(all(signatures[key] == ref["state_dict_signatures"][key] for key in signatures),
            "Actual96M network/target architecture differs from64M")
    require(group_geometry(optimizer["groups"]) == group_geometry(ref["optimizer"]["groups"]),
            "Adam group geometry differs from64M")
    require(min(optimizer["step_values"]) >= max(ref["optimizer"]["step_values"]), "Adam exposure moved backwards")
    require(gate["tag"] == "fresh3-96M" and gate["target"] == TARGET
        and gate["experiment"] == EXPERIMENT and Path(gate["checkpoint"]).resolve() == candidate.resolve(),
        "Gate identity/branch differs")
    require(metadata["epsilon"] == .1 and math.isclose(metadata["expert_ratio"], .1, abs_tol=1e-12),
            "Saved behavior controls differ from recovery branch")
    require(metadata["lr_gear"] == ref["saved_metadata"]["lr_gear"]
        and metadata["lr_anchor_step"] == ref["saved_metadata"]["lr_anchor_step"], "Saved LR lineage differs")
    resumes, envs, anchors = {}, {}, {}
    for number in range(14, 21):
        folder = CAMPAIGN / f"run-{number:02d}"
        resumes[str(number)] = evidence.json(folder / "final-resume-checkpoint.json")
        envs[str(number)] = evidence.json(folder / "resume-environment.json")
        anchors[str(number)] = resumes[str(number)]["saved_metadata"]
        require(resumes[str(number)].get("cpu_only") is True
            and resumes[str(number)].get("cuda_initialized", False) is False,
            f"Unverified CPU resume anchor: {number}")
        require(all(envs[str(number)].get(key) == expected for key, expected in EXPECTED_POLICY.items()),
            f"Recorded short-return/cap/smoothing controls differ: {number}")
        require(all(anchors[str(number)][key] == metadata[key] for key in
            ("engine_version", "state_size", "single_frame_state_size", "frame_stack")),
            f"Resume architecture differs: {number}")
    current_meta = evidence.json(CAMPAIGN / "run-20/metadata.json")
    require(all(current_meta["config"].get(key) == expected for key, expected in
        dict(batch_size=4096, baseline_batch_size=512, n_step=3,
             max_samples_per_frame=8.0, c51_target_smoothing=0.0).items()),
        "Run20 recorded config differs")
    # This is a byte snapshot of the current control file, not proof of every
    # historical control read. Final root verification remains required.
    controls_path = GAME / "models_dqn/learning_control.json"
    controls = evidence.json(controls_path)
    require(controls["experiment"] == EXPERIMENT and controls["lr_scale"] == .5
        and controls["epsilon_ramp"]["start"] == controls["epsilon_ramp"]["end"] == .1,
        "Current branch controls differ")
    require(int(envs["16"]["DQN_BATCH_SIZE"]) == int(envs["18"]["DQN_BATCH_SIZE"]) == 2048
        and all(int(envs[key]["DQN_BATCH_SIZE"]) == 4096 for key in ("17", "19", "20")),
        "Recorded2048/4096 phase provenance differs")
    exposures = [
        exposure(ref["saved_metadata"], anchors["17"], 2048, "protected64M -> run17 B4096 resume"),
        exposure(anchors["17"], anchors["18"], 4096, "run17 B4096"),
        exposure(anchors["18"], anchors["19"], 2048, "run18 A-return2048"),
        exposure(anchors["19"], anchors["20"], 4096, "run19 selected4096"),
        exposure(anchors["20"], metadata, 4096, "run20 selected4096 -> saved96M")]
    exposure_totals = {str(batch): dict(logical_updates=sum(row["logical_updates_delta"] for row in exposures
        if row["recorded_batch_size"] == batch), optimized_samples=sum(row["optimized_samples_delta"] for row in exposures
        if row["recorded_batch_size"] == batch)) for batch in (2048, 4096)}
    checkpoint_tensors = list(tensor_walk(checkpoint, torch))
    all_tensor_devices = sorted({str(item.device) for item in checkpoint_tensors})
    require(all_tensor_devices == ["cpu"] and torch.cuda.is_initialized() is False, "CPU-only guard failed")
    final_stat = contract.file_stat(candidate)
    require(final_stat == before_stat and sha(candidate) == candidate_sha, "Candidate changed during CPU capture")
    evidence.bind_stat(candidate, before_stat)
    checks = dict(candidate_stable_during_read=True, protected64M_hash_matches_metadata=True,
        architecture_matches64M=True, online_target_keys_shapes_dtypes_match64M=True,
        Adam81=True, Adam_group_geometry_matches64M=True, all_network_optimizer_tensors_finite=True,
        saved_learner_gate_passed=metadata["learner_frame_count"] >= TARGET,
        saved_clocks_advance64M=all(metadata[key] > ref["saved_metadata"][key] for key in contract.CORE_CLOCKS),
        measurement_exclusion_clock_preserved=metadata["measurement_frame_count"] >= ref["saved_metadata"]["measurement_frame_count"],
        total_training_steps_equal_saved_training_steps=metadata["training_steps"] == metadata["total_training_steps"],
        recovery_branch_controls_match=True, recorded2048_4096_clock_exposure_consistent=True, CPU_only=True)
    require(all(checks.values()), "Proposed lineage checks did not pass")
    result = dict(schema="robotron-96M-checkpoint-lineage-v1", utc=utc(),
        proposal_only=True, root_verification="PENDING; this is not the final root-published lineage report",
        PASS=True, checks=checks,
        candidate=dict(path=str(candidate.resolve()), sha256=candidate_sha,
            stat=dict(before_stat, mode=oct(stat.S_IMODE(candidate.stat().st_mode)), nlink=candidate.stat().st_nlink),
            saved_metadata=metadata, optimizer=optimizer, state_dict_signatures=signatures,
            tensor_devices=all_tensor_devices, checkpoint_tensor_count=len(checkpoint_tensors),
            all_network_optimizer_tensors_finite=True),
        protected64M=dict(path=plan["reference"]["checkpoint"]["path"],
            sha256=ref["sha256"], saved_metadata=ref["saved_metadata"], optimizer=ref["optimizer"]),
        trigger_gate=dict(path=str(gate_path), sha256=gate_sha, record=gate,
            note="Trigger snapshot is retained verbatim; actual saved checkpoint clocks above are authoritative."),
        branch_provenance=dict(experiment=EXPERIMENT, control_path=str(controls_path), control_snapshot=controls,
            run20_config=current_meta["config"], recorded_environments=envs,
            resume_anchors={key: dict(sha256=value["sha256"], saved_metadata=value["saved_metadata"])
                            for key, value in resumes.items()}),
        actual_recorded_batch_exposure=dict(since64M=exposures, totals=exposure_totals,
            Adam_parameter_steps64M=ref["optimizer"]["step_values"], Adam_parameter_steps96M=optimizer["step_values"],
            note="Saved clock differences corroborate recorded batch phases; Adam parameter steps are separately measured, not equated to logical updates. Not all exposure since64M was4096."),
        capture_execution=dict(started_utc=started, finished_utc=utc(), elapsed_s=time.monotonic()-process_start,
            python=sys.version, torch=str(torch.__version__), CUDA_VISIBLE_DEVICES=os.environ.get("CUDA_VISIBLE_DEVICES"),
            torch_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads(),
            CUDA_initialized=torch.cuda.is_initialized(), max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        limitations=["Automated proposal only: root must independently verify candidate SHA/critical saved metadata and publish the final lineage.",
            "Checkpoint format does not save every historical replay/behavior control; recorded environment/config/control provenance is separate evidence, not a replay of every historical read.",
            "No policy quality inference, promotion, protection, model write, gate/state/control change or evaluation launch."],
        evidence=evidence.snapshot())
    contract.lineage_identity(result, candidate, ref["saved_metadata"])
    evidence.recheck()
    return result


def capture(output):
    require(os.environ.get("CUDA_VISIBLE_DEVICES") == "", "Run with CUDA_VISIBLE_DEVICES='' before importing Torch")
    require(Path(output).resolve().parent == RUN.resolve() and Path(output).name.startswith("proposed-")
        and Path(output).suffix == ".json", "Only a new proposed-*.json in run19 may be written")
    require(not Path(output).exists(), "Proposal output already exists")
    candidate = GAME / "models_dqn/managed-checkpoints/fresh3-96M.pt"
    gate_path = CAMPAIGN / "run-14/fresh3-96M-gate.json"
    require(candidate.is_file() and gate_path.is_file(), "Actual96M checkpoint and gate must both exist")
    started, process_start = utc(), time.monotonic()
    contract = load_contract()
    evidence = contract.Evidence()
    evidence.file(__file__, sha(__file__))
    evidence.file(RUN / "analyze96M_guard.py", GUARD_SHA)
    plan = evidence.json(RUN / "quality96M-regression-guard-plan.json", contract.PLAN_SHA)
    reference = evidence.json(CAMPAIGN / "run-14/fresh3-64M-checkpoint-lineage.json", REFERENCE_LINEAGE_SHA)
    require(reference["PASS"] is True and all(reference["checks"].values()), "64M root lineage is not PASS")
    protected = plan["reference"]["checkpoint"]
    require(reference["candidate"]["sha256"] == protected["sha256"]
        and reference["candidate"]["saved_metadata"] == plan["reference"]["saved_clocks"], "64M reference evidence differs")
    evidence.file(protected["path"], protected["sha256"])
    evidence.json(protected["metadata_path"], protected["metadata_sha256"])
    gate = evidence.json(gate_path)
    gate_sha = evidence.files[str(gate_path.absolute())]
    evidence._path(candidate)
    before_stat = contract.file_stat(candidate)
    require(0 < before_stat["size"] <= 512 * 1024 * 1024, "Candidate exceeds bounded checkpoint size")
    candidate_sha = sha(candidate)
    evidence.file(candidate, candidate_sha)
    evidence.bind_stat(candidate, before_stat)
    import torch
    require(torch.cuda.is_initialized() is False, "CUDA context already initialized")
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    checkpoint = torch.load(candidate, map_location="cpu", weights_only=True)
    require(isinstance(checkpoint, dict), "Checkpoint must be a dictionary")
    report = proposed_report(torch, checkpoint, candidate, candidate_sha, before_stat,
        gate, gate_path, gate_sha, reference, plan, evidence, started, process_start, contract)
    evidence.recheck()
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    with Path(output).open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--output", type=Path, default=RUN / "proposed-fresh3-96M-checkpoint-lineage.json")
    args = parser.parse_args()
    if not args.capture:
        parser.print_help()
        return
    try:
        result = capture(args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"96M lineage proposal rejected: {error}\n")
    print(json.dumps(dict(output=str(args.output), PASS=result["PASS"], candidate_sha256=result["candidate"]["sha256"],
        saved_metadata=result["candidate"]["saved_metadata"], capture_execution=result["capture_execution"])))


if __name__ == "__main__":
    main()
