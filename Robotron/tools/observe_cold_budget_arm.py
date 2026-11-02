"""Observe one precommitted throughput interval and publish its actual stage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request
from zoneinfo import ZoneInfo
from datetime import datetime


def read(path):
    return json.loads(Path(path).read_text())


def atomic(path, value):
    raw = (json.dumps(value, allow_nan=False) + "\n").encode()
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def immutable(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)


def birth(pid):
    return int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])


def observe(args):
    for pid, expected in ((args.trainer_pid, args.trainer_birth),
                          (args.fleet_pid, args.fleet_birth)):
        if birth(pid) != expected:
            raise RuntimeError(f"Original owner changed: {pid}")
    env = Path(f"/proc/{args.trainer_pid}/environ").read_bytes().split(b"\0")
    if f"DQN_MAX_SAMPLES_PER_FRAME={args.cap}".encode() not in env:
        raise RuntimeError("Actual startup cap differs from selected arm")
    with urllib.request.urlopen("http://127.0.0.1:8771/api/now", timeout=5) as response:
        api = json.load(response)
    fleet = read(args.fleet_status)
    exposure = api["host_pipeline"]["learning_exposure"]
    if time.time() - api["ts"] > 5 or time.time() - fleet["updated_unix_s"] > 5:
        raise RuntimeError("Live observations are stale")
    counts = fleet["counts"]
    if not api["training_enabled"] or counts["active_train"] != 155:
        raise RuntimeError("Training stopped or original TRAIN cohort is incomplete")
    if fleet.get("errors") or fleet["error_summary"]["occurrences"]:
        raise RuntimeError("Original fleet reports an error")
    hp = api["host_pipeline"]
    if api.get("pipeline_read_error") or hp["inference"]["errors"]:
        raise RuntimeError("Pipeline/inference error")
    if not hp["inference_graphs"]["ready"] or hp["inference_graphs"].get("fatal_error"):
        raise RuntimeError("Inference graph unavailable")
    opt = exposure["optimizer"]
    if opt["process_id"] != args.trainer_pid or not opt["available"]:
        raise RuntimeError("Optimizer observation unavailable or owner changed")
    if opt["since_epoch"]["unavailable"] or opt["unclassified_started_total"]:
        raise RuntimeError("Unknown optimizer outcomes")
    return dict(observed_unix_s=time.time(), observed_monotonic_s=time.monotonic(),
                api=api, fleet=fleet)


def publish(args, stage, waiting, next_stage, eta, training=True):
    control = read(args.control)
    control["mode"] = "manual"
    control["next_work"].update(dict(
        state="throughput_trial" if training else "throughput_trial_needs_review",
        current_stage=stage,
        detail=(f"Comparing update budgets 8 → 12 → 8 at batch 4096 to measure useful "
                "learning updates without sacrificing game or new-experience throughput. "
                "Saved model, optimizer and replay were restored exactly; training is continuing."),
        waiting_for=waiting, next_stage=next_stage, eta=eta,
        deadline_unix_s=None, updated_unix_s=time.time(),
        observation_unix_s=time.time(), main_training_continues=training))
    atomic(Path(args.control), control)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "control", "fleet-status", "barrier", "held-report"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--arm", required=True, choices=("A1", "B", "A2"))
    for name in ("trainer-pid", "trainer-birth", "fleet-pid", "fleet-birth", "cap"):
        parser.add_argument("--" + name, required=True, type=int)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    immutable(args.output / "owner.json", dict(pid=os.getpid(), birth=birth(os.getpid()),
              started_unix_s=time.time(), argv=vars(args) | {k:str(v) for k,v in vars(args).items() if isinstance(v,Path)}))
    samples = []
    try:
        barrier = read(args.barrier)
        held = read(args.held_report)
        if held["startup_budget"]["runtime_cap"] != args.cap:
            raise RuntimeError("Held startup witness has wrong cap")
        earliest = barrier["monotonic_ns"] / 1e9 + 300
        while time.monotonic() < earliest:
            observe(args)
            left = earliest - time.monotonic()
            publish(args, f"Warming up {args.arm}: update budget {args.cap}",
                    "The required five-minute client/GPU warmup", "Measure throughput for five minutes",
                    f"Warmup ends in about {int(left)+1} seconds; measurement then takes five minutes.")
            time.sleep(min(10, max(0.01,left)))
        start = time.monotonic()
        end = start + 300
        end_wall = time.time() + 300
        finish = datetime.fromtimestamp(end_wall, ZoneInfo("America/Chicago")).strftime("%I:%M:%S %p CDT").lstrip("0")
        for index in range(11):
            if index:
                time.sleep(max(0, start + index * 30 - time.monotonic()))
            sample = observe(args)
            immutable(args.output / f"sample-{index:02d}.json", sample)
            samples.append(sample)
            left = max(0, end - time.monotonic())
            counts = sample["fleet"]["counts"]
            publish(args, f"Measuring {args.arm}: update budget {args.cap} ({index}/10 intervals)",
                    f"Five minutes of matched throughput data; {counts['active_train']} TRAIN and {counts['active_eval']} EVAL clients active",
                    "Preserve this arm's complete state, then resume with budget 12" if args.arm == "A1" else
                    "Preserve this arm's complete state, then resume with budget 8" if args.arm == "B" else
                    "Compare all three arms and retain the practical setting",
                    f"This measurement ends around {finish} ({int(left)+1} seconds remaining). State preservation and restart follow; their duration is measured separately.")
            print(json.dumps(dict(arm=args.arm,sample=index,fps=sample["api"]["fps"],counts=counts,remaining_s=left)),flush=True)
        first, last = samples[0]["api"], samples[-1]["api"]
        seconds = last["ts"] - first["ts"]
        ex0, ex1 = (d["host_pipeline"]["learning_exposure"] for d in (first,last))
        for kind in ("optimizer", "replay"):
            for key in ("process_id", "instance_monotonic_ns", "epoch"):
                if len({s["api"]["host_pipeline"]["learning_exposure"][kind][key] for s in samples}) != 1:
                    raise RuntimeError(f"{kind} process/epoch changed")
        opt0,opt1 = (ex["optimizer"]["since_epoch"] for ex in (ex0,ex1))
        applied = opt1["applied"] - opt0["applied"]
        skips = opt1["amp_skipped"] - opt0["amp_skipped"]
        frames = (last["frame_count"]-last["measurement_frames"])-(first["frame_count"]-first["measurement_frames"])
        optimized = last["optimized_samples"]-first["optimized_samples"]
        baseline = held["startup_budget"]["loaded_baseline"]
        cumulative_frames = last["frame_count"] - last["measurement_frames"] - baseline["frame_count"] + baseline["measurement_frame_count"]
        report = dict(schema="robotron-cold-budget-arm-observation-v1",status="PASS_ENGINEERING_OBSERVATION",
            arm=args.arm,cap=args.cap,seconds=seconds,warmup_s=samples[0]["observed_monotonic_s"]-barrier["monotonic_ns"]/1e9,
            game_fps=frames/seconds,applied_updates_per_s=applied/seconds,
            new_replay_per_s=(ex1["replay"]["accepted_total"]-ex0["replay"]["accepted_total"])/seconds,
            new_learner_replay_per_s=(ex1["replay"]["accepted_learner_total"]-ex0["replay"]["accepted_learner_total"])/seconds,
            applied=applied,amp_skipped=skips,amp_skip_fraction=skips/max(1,applied+skips),
            interval_optimized_samples_per_unmeasured_frame=optimized/frames,
            cumulative_budget_samples_per_unmeasured_frame=(last["optimized_samples"]-baseline["optimized_samples"])/cumulative_frames,
            role_counts=[s["fleet"]["counts"] for s in samples],
            GPU_util_scope="Whole-device utilization includes unrelated workloads; host spans are not device utilization",
            policy_quality_qualified=False, ended_unix_s=time.time())
        if report["amp_skip_fraction"] > .005:
            report["status"] = "FAIL_AMP_SKIP_GUARD"
        immutable(args.output / "report.json",report)
        publish(args, f"{args.arm} measurement complete; preparing the next stage",
                "Review of the completed measurement before controlled state preservation",
                "Save all training state and test budget 12" if args.arm == "A1" else "Continue the precommitted 8 → 12 → 8 comparison",
                "The five-minute measurement is complete. Training continues while the next controlled transition is prepared.")
        immutable(args.output / "result.json",dict(actual_exit=0,status=report["status"],ended_unix_s=time.time()))
        print(json.dumps(report),flush=True)
    except BaseException as error:
        immutable(args.output / "failure.json",dict(error=repr(error),ended_unix_s=time.time(),completed_samples=len(samples)))
        try:
            publish(args,f"{args.arm} throughput observation needs review",str(error),
                    "Inspect the preserved failure before selecting the next action",
                    "No reliable completion estimate is available until the observation is reviewed.",False)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
