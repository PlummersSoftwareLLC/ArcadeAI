#!/usr/bin/env python3
"""Precommit one inference-worker affinity A/B/A trial; default is read-only.

Example (only after every frozen quality campaign has finished):
  python3 Robotron/tools/inference_worker_affinity.py --trainer-pid PID \
    --fleet-unit robotron-managed-RUN-HASH-fleet.service --output-dir NEW_DIR

Add --launch to run 90-second settling and 300-second primary windows. Only
the unique InferBatchWorke thread is pinned to CPU 71 for B. Its original mask
is restored for A return and on failure/signals if its process/thread identity
still matches. Nothing is killed, restarted, promoted, or checkpoint-modified.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.request

try:
    from . import cpu_affinity_pilot as identity
except ImportError:
    import cpu_affinity_pilot as identity


GAME = Path(__file__).resolve().parents[1]
SCHEMA = "robotron-inference-affinity-trial-v1"
PHASES = ("A", "B", "Areturn")
THREAD_NAME = "InferBatchWorke"
LOG_MARKERS = ("Batched inference request timed out", "Batched inference failed",
               "Training error:", "ExactInferenceGraphError", "AsyncReplayBuffer error:",
               "[SOCKET ACTION TIMEOUT]", "[SOCKET ACTION ERROR]", "Traceback",
               "Replay queue saturated", "replay prefetch failed",
               "falling back to synchronous sampling", "fused Adam unavailable",
               "torch.compile unavailable", "[WARN] HOF save failed:",
               "[WARN] EpHOF save failed:", "Replay buffer save failed:",
               "[WARN] compiled inference failed", "disabling torch.compile for training after error",
               "[WARN] replay live-mmap init failed:", "Optimizer state skipped:",
               "GradScaler state skipped:", "Optimizer state absent/stale",
               "Incompatible checkpoint engine version", "Replay buffer skipped",
               "No replay buffer found", "Replay buffer load failed:",
               "[WARN] Backup copy failed:", "[WARN] HOF load failed:", "[WARN] EpHOF load failed:",
               "[BANKS] background HOF save failed:", "[BANKS] background EPHOF save failed:",
               "HOF load skipped: stride/state_size mismatch with config",
               "EPHOF load skipped: stride/state_size mismatch with config",
               "Failed to read replay meta:", "Missing array file:",
               "[WARN] live-mmap backing unavailable", "[WARN] live-mmap promotion failed",
               "Replay mmap adoption skipped:", "Failed to read replay buffer:",
               "Replay buffer file is empty.", "Replay buffer is empty — nothing to save.",
               "State size mismatch: saved=", "truncating to most recent.",
               "Pruned legacy interesting flags:", "Replay buffer flushed.",
               "Model load failed/incompatible, starting fresh", "No model found, starting fresh",
               "[BANKS] periodic save failed:", "[WARN] Best-checkpoint save failed:",
               "[WARN] peak archive failed:", "[MANAGED CHECKPOINT] rejected request:")
# Deliberately exclude generic WARN, expected C51 support-key messages and
# "Partial load": target support alone can produce that normal startup text.
CLOCKS = ("frame_count", "learner_frame_count", "optimized_samples", "training_steps")
ENV_RECIPE = {"DQN_BATCH_SIZE": "4096", "DQN_N_STEP": "3", "DQN_MAX_SAMPLES_PER_FRAME": "8",
              "DQN_C51_TARGET_SMOOTHING": "0", "DQN_EXACT_INFERENCE_GRAPHS": "1",
              "DQN_NATIVE_BATCH_UPDATE": "1", "DQN_STREAM_BANK_OUTPUT": "1",
              "DQN_LEARNING_EXPOSURE_COUNTERS": "1", "DQN_INFERENCE_BATCH_WAIT_MS": "1"}
LIMITATIONS = [
    "Sequential evolving-policy/replay A/B/A; not a randomized causal or learning-quality test.",
    "Applied exposure counts optimizer-call admissions; it does not prove each Adam parameter advanced.",
    "Logical and exposure snapshots are cached asynchronously; one in-flight optimizer outcome is allowed.",
    "Host latency and migration counters do not measure cache misses or establish a bottleneck.",
    "All primary observations and natural bank events are retained; there is no favorable-window trimming.",
    "Affinity syscalls use numeric TIDs; identity checks minimize but cannot eliminate the kernel reuse race.",
]


class GuardFailure(ValueError):
    pass


class TrialInterrupted(BaseException):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value, *, immutable=False):
    path = Path(path)
    if immutable:
        with path.open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        path.chmod(0o444)
    else:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)


def require(condition, message):
    if not condition:
        raise GuardFailure(message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def exposure_key(value):
    return {key: value[key] for key in ("process_id", "instance_monotonic_ns", "epoch")}


def online_cpus():
    online = set()
    for part in Path("/sys/devices/system/cpu/online").read_text().strip().split(","):
        ends = [int(value) for value in part.split("-")]
        online.update(range(ends[0], ends[-1] + 1))
    return online


def discover_fleet_actors(cgroup):
    """Classify a cgroup snapshot, then strictly inspect every MAME actor.

    Supervisors also own short-lived sleep/pgrep children. Their disappearance
    before classification is harmless; exact slots and the caller's complete
    immutable binding comparison still detect missing or replaced actors.
    """
    actors, logs = [], set()
    for pid in (Path('/sys/fs/cgroup') / cgroup.lstrip('/') / 'cgroup.procs').read_text().split():
        process = Path('/proc') / pid
        try:
            argv = process.joinpath('cmdline').read_bytes().split(b'\0')
        except OSError as error:
            if error.errno in (errno.ENOENT, errno.ESRCH):
                continue
            raise GuardFailure(f'Fleet candidate PID {pid} cmdline discovery failed: {error}') from error
        if not (len(argv) > 1 and argv[1] == b'robotron' and argv[0].endswith(b'/mame')):
            continue
        operation = 'identity'
        try:
            actor = identity.identify_process(int(pid), 'mame')
            operation = 'cgroup'
            require(process.joinpath('cgroup').read_text().strip() == '0::' + cgroup,
                    'Actor left the owned fleet cgroup')
            for descriptor in ('1', '2'):
                operation = 'stdout/stderr fd ' + descriptor
                logs.add(str((process / 'fd' / descriptor).resolve(strict=True)))
            actors.append(actor)
        except (OSError, ValueError) as error:
            raise GuardFailure(f'Classified MAME PID {pid} {operation} inspection failed: {error}') from error
    actors.sort(key=lambda actor: actor['client_slot'])
    require([actor['client_slot'] for actor in actors] == list(range(192)),
            'Expected exact main actor slots 0..191')
    return actors, logs


def compact_api(raw):
    """Keep counters/flags/timings, excluding per-client lists and large recent arrays."""
    hp = raw["host_pipeline"]
    graphs, bank = hp["inference_graphs"], raw["bank_persistence"]
    out = {key: raw[key] for key in (*CLOCKS, "ts", "client_count", "epsilon", "expert_ratio", "lr",
           "training_enabled", "measurement_active", "loss", "grad_norm", "memory_buffer_size",
           "pipeline_read_error", "bank_persistence_read_error")}
    out["exposure"] = hp["learning_exposure"]
    # Optional route evidence shares this exact process/timestamp snapshot.
    out["parallel_state_fill"] = hp.get("parallel_state_fill")
    # Rare AMP Inf gradient diagnostics are evidence, not an automatic fault.
    # Retain them in valid JSON while finite loss/outcome guards remain strict.
    out["grad_norm_nonfinite"] = not finite(out["grad_norm"])
    if out["grad_norm_nonfinite"]:
        out["grad_norm"] = str(out["grad_norm"])
    out["graphs"] = {key: graphs[key] for key in ("ready", "capture_count", "validation_replay_count",
        "postload_validations", "runtime_capture_count", "fallback_count", "fatal_error", "replay_count")}
    out["native"] = hp["native_batch_update"]
    out["pipeline_errors"] = {key: hp[key]["errors"] for key in
                              ("inference", "actor_refresh", "target_refresh", "learner_priority")}
    out["inference_timing"] = {key: hp["inference"][key] for key in
                               ("count", "batch_size", "total_host_ms")}
    out["bank"] = {key: bank[key] for key in ("writes", "write_failures", "last_error", "writer_active",
        "write_duration_s", "last_write_duration_s", "snapshot_lock_max_ms", "revision", "saved_revision")}
    out["bank"].update(backend=bank["output"]["backend"],
        stream_enabled=bank["output"]["stream_output_enabled"],
        output_errors=sum(value["errors"] for value in bank["output"]["totals"].values()))
    return out


def api_issues(row, plan, previous=None):
    issues = []
    def check(condition, message):
        if not condition:
            issues.append(message)
    try:
        check(row["client_count"] == 192, "client_count")
        check(row["training_enabled"] and not row["measurement_active"], "training_mode")
        check(row["epsilon"] == .1 and abs(row["expert_ratio"]-.1) < 1e-12
              and row["lr"] == 2.5e-5 and row["memory_buffer_size"] == 6000000, "held_controls")
        check(finite(row["loss"]), "nonfinite_loss")
        check(not row["pipeline_read_error"] and not row["bank_persistence_read_error"], "metadata_read_error")
        for key in CLOCKS:
            check(type(row[key]) is int and row[key] >= 0, "bad_clock:" + key)
            if previous:
                check(row[key] >= previous[key], "clock_decreased:" + key)
        check(finite(row["ts"]) and (not previous or row["ts"] >= previous["ts"]), "API_timestamp")
        g, n, b = row["graphs"], row["native"], row["bank"]
        check(g["ready"] and g["capture_count"] == 128 and g["validation_replay_count"] == 640
              and g["postload_validations"] == 1 and not g["runtime_capture_count"]
              and not g["fallback_count"] and not g["fatal_error"], "graph_route")
        check(n["enabled"] and n["available"] and n["completed_count"] == n["success_count"]
              and not n["fallback_count"] and not n["error_count"], "native_route")
        check(b["backend"] == "stream" and b["stream_enabled"] and not b["write_failures"]
              and not b["last_error"] and not b["output_errors"], "bank_route")
        check(not any(row["pipeline_errors"].values()), "pipeline_errors")
        e = row["exposure"]
        for kind in ("optimizer", "replay"):
            value = e[kind]
            check(value["enabled"] and exposure_key(value) == plan["exposure_identity"][kind],
                  "exposure_identity:" + kind)
        o, r = e["optimizer"], e["replay"]
        totals = o["total"]
        check(all(type(v) is int and v >= 0 for v in totals.values()), "optimizer_counters")
        pending = totals["attempts_started"] - totals["outcomes_recorded"]
        row["optimizer_pending"] = pending
        check(pending in (0, 1) and o["unclassified_started_total"] == pending, "optimizer_pending")
        check(totals["outcomes_recorded"] == totals["applied"] + totals["amp_skipped"] + totals["unavailable"],
              "optimizer_partition")
        check(totals["unavailable"] == 0 and not o["prior_epoch_outcomes_total"], "unavailable_outcomes")
        check(o["available"] or pending == 1, "optimizer_unavailable_without_inflight")
        check(r["available"] and r["accepted_by_source_total"]["unattributed"] == 0, "replay_unavailable")
        check(r["accepted_total"] == sum(r["accepted_by_source_total"].values())
              and r["accepted_learner_total"] == r["accepted_by_source_total"]["dqn"]
                  + r["accepted_by_source_total"]["epsilon"], "replay_partition")
        if previous:
            for key, value in totals.items():
                check(value >= previous["exposure"]["optimizer"]["total"][key], "optimizer_decreased:" + key)
            for key, value in r["accepted_by_source_total"].items():
                check(value >= previous["exposure"]["replay"]["accepted_by_source_total"][key], "replay_decreased:" + key)
        check(not row.get("log_errors"), "new_runtime_log_error")
        check(row["csv"]["replay_dropped"] == plan["initial_snapshot"]["csv"]["replay_dropped"], "replay_drops")
        check(row["csv"]["batch_size"] == plan["batch_size"]
              and row["csv"]["replay_sample_cap"] == plan["replay_cap"], "CSV_recipe")
        if previous:
            gap = row["observed_monotonic_s"] - previous["observed_monotonic_s"]
            check(gap <= 10, "observation_gap_over_10s")
        check(-2 <= row["observed_unix_s"] - row["ts"] <= 10, "stale_API_snapshot")
    except (KeyError, TypeError, ValueError) as error:
        issues.append("malformed_API:" + str(error))
    return issues


class Host:
    def __init__(self, trainer_pid, fleet_unit):
        self.pid, self.fleet_unit = trainer_pid, fleet_unit
        self.log_offsets = {}
        self.csv_path = None
        self.worker = None

    now = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)

    def no_sidecars(self):
        for entry in Path("/proc").iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                argv = entry.joinpath("cmdline").read_bytes().split(b"\0")
                if argv and Path(os.fsdecode(argv[0])).name.startswith("python"):
                    require(not any(Path(os.fsdecode(arg)).name in ("run_frozen_sidecar.py", "run_quality_campaign.py")
                                    for arg in argv[1:] if arg), "A frozen evaluation/campaign process is active")
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
        # Bind without listening: detect a wildcard or loopback listener without
        # creating a fake client handshake on the evaluator socket.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", 9999))
            except OSError as error:
                raise GuardFailure("Evaluation port 9999 is in use") from error

    def thread_identity(self, tid=None):
        trainer = identity.identify_process(self.pid, "trainer")
        matches = []
        for entry in (Path("/proc") / str(self.pid) / "task").iterdir():
            try:
                if (entry / "comm").read_text().strip() == THREAD_NAME:
                    info = identity.read_thread(self.pid, int(entry.name))
                    matches.append({"tid": info["tid"], "starttime_ticks": info["starttime_ticks"]})
            except (FileNotFoundError, ProcessLookupError):
                continue
        require(len(matches) == 1, "Expected exactly one inference worker thread")
        require(tid is None or matches[0]["tid"] == tid, "Inference worker TID changed")
        return {"trainer": trainer, "thread": matches[0]}

    def set_mask(self, binding, mask):
        actual = self.thread_identity(binding["thread"]["tid"])
        require(actual == binding, "Trainer or inference thread identity changed before affinity syscall")
        os.sched_setaffinity(binding["thread"]["tid"], set(mask))
        require(self.thread_identity(binding["thread"]["tid"]) == binding, "Identity changed during affinity syscall")
        require(self.mask(binding) == sorted(mask), "Affinity readback differs")

    def mask(self, binding):
        require(self.thread_identity(binding["thread"]["tid"]) == binding, "Trainer/thread identity changed")
        return sorted(os.sched_getaffinity(binding["thread"]["tid"]))

    def bindings(self):
        self.no_sidecars()
        worker = self.thread_identity()
        self.worker = worker
        proc = Path("/proc") / str(self.pid)
        environment = dict(item.split("=", 1) for item in (proc / "environ").read_bytes().decode().split("\0") if "=" in item)
        selected = {key: value for key, value in environment.items()
                    if key.startswith(("DQN_", "ROBOTRON_")) or key == "CUDA_VISIBLE_DEVICES"}
        require(all(selected.get(key) == value for key, value in ENV_RECIPE.items()), "Trainer environment differs from selected recipe")
        self.csv_path = Path(selected["ROBOTRON_RUN_DIR"]) / "training.csv"
        require(re.fullmatch(r"robotron-managed-[A-Za-z0-9_.-]+-fleet\.service", self.fleet_unit), "Unexpected fleet unit name")
        cgroup = subprocess.run(["systemctl", "--user", "show", self.fleet_unit, "--value", "-p", "ControlGroup"],
                                capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        require(cgroup.startswith("/user.slice/") and cgroup.endswith("/" + self.fleet_unit), "Unexpected fleet cgroup")
        actors, logs = discover_fleet_actors(cgroup)
        logs.update(str((proc / "fd" / fd).resolve()) for fd in ("1", "2"))
        log_bindings = {}
        for name in sorted(logs):
            info = Path(name).stat()
            require(stat.S_ISREG(info.st_mode), "Runtime stdout must be a regular file")
            log_bindings[name] = {"device": info.st_dev, "inode": info.st_ino}
        model_dir = Path(selected.get("ROBOTRON_DQN_MODEL_DIR", str(GAME / "models_dqn")))
        control = Path(selected.get("ROBOTRON_DQN_CONTROL_PATH", str(model_dir / "learning_control.json")))
        sources = [GAME / "Scripts/main.lua", GAME / "Scripts/run_dqn.py", GAME / "Scripts/robotron_socket_wait.c",
                   Path(__file__).resolve(), Path(identity.__file__).resolve(),
                   Path(__file__).with_name('test_fleet_actor_discovery.py').resolve()]
        sources += sorted((GAME / "Scripts/dqn").glob("*.py")) + sorted((GAME / "Scripts/dqn").glob("*.c"))
        settings = [control, model_dir / "game_settings.json"]
        return dict(worker=worker, actors=actors, fleet_cgroup=cgroup, environment_sha256=digest(selected),
                    source_hashes={str(path): file_digest(path) for path in sources},
                    control_hashes={str(path): file_digest(path) for path in settings}, logs=log_bindings)

    def configure_logs(self, bindings):
        for name, expected in bindings.items():
            info = Path(name).stat()
            require((info.st_dev, info.st_ino) == (expected["device"], expected["inode"]), "Runtime log identity changed")
            self.log_offsets[name] = {"offset": info.st_size, "partial": "", **expected}

    def log_errors(self):
        errors = []
        for name, saved in self.log_offsets.items():
            with Path(name).open("rb") as stream:
                info = os.fstat(stream.fileno())
                require((info.st_dev, info.st_ino) == (saved["device"], saved["inode"])
                        and info.st_size >= saved["offset"], "Runtime log replaced/truncated")
                stream.seek(saved["offset"])
                payload = stream.read(4 * 1024 * 1024)
                require(stream.tell() == info.st_size, "Runtime log increment exceeds bounded read")
                saved["offset"] = stream.tell()
            text = saved["partial"] + payload.decode(errors="replace")
            errors.extend({"path": name, "marker": marker} for marker in LOG_MARKERS if marker in text)
            saved["partial"] = text[-256:] if "\n" not in text else text.rsplit("\n", 1)[-1][-256:]
        return errors

    def capture(self):
        self.no_sidecars()
        with urllib.request.urlopen("http://127.0.0.1:8771/api/now", timeout=3) as response:
            payload = response.read(2 * 1024 * 1024 + 1)
        require(len(payload) <= 2 * 1024 * 1024, "API snapshot too large")
        row = compact_api(json.loads(payload))
        # Read only the header and a bounded suffix. Ignore a partial last row.
        with self.csv_path.open("rb") as stream:
            header = stream.readline(32768).decode()
            stream.seek(0, os.SEEK_END); length = stream.tell()
            stream.seek(max(0, length - 256 * 1024))
            tail = stream.read().decode().splitlines(keepends=True)
        complete = [line for line in tail if line.endswith("\n")]
        require(bool(complete), "No complete CSV row available")
        values = list(csv.DictReader([header, complete[-1]]))[-1]
        row["csv"] = {key: int(values[key]) for key in ("replay_dropped", "batch_size")}
        row["csv"].update(replay_sample_cap=float(values["replay_sample_cap"]), utc=values["utc"])
        tid = self.worker["thread"]["tid"]
        sched = identity.read_thread(self.pid, tid)
        timing = (Path("/proc") / str(self.pid) / "task" / str(tid) / "schedstat").read_text().split()
        row["thread_sched"] = dict(migrations=sched["migrations"], runtime_ns=int(timing[0]), ready_wait_ns=int(timing[1]))
        row.update(observed_monotonic_s=self.now(), observed_unix_s=time.time(), log_errors=self.log_errors())
        return row

    def verify(self, plan, expected_mask):
        require(self.bindings() == plan["bindings"], "Ownership/source/environment/control binding changed")
        require(self.mask(plan["bindings"]["worker"]) == sorted(expected_mask), "Inference worker affinity changed externally")


def prepare(host, directory, cpu=71, settle_s=90, window_s=300, period_s=1):
    directory = Path(directory).expanduser().resolve()
    require(not directory.exists(), "Output directory must be new; trials never resume or overwrite")
    require(cpu == 71, "This precommitted trial targets fixed CPU 71")
    require(settle_s >= 90 and window_s >= 300 and .2 <= period_s <= 5, "Require >=90s settling, >=300s windows and bounded polling")
    bindings = host.bindings()
    original = host.mask(bindings["worker"])
    require(cpu in original and cpu in online_cpus() and len(original) > 1, "CPU 71 must be online and included in an unrestricted original mask")
    host.configure_logs(bindings["logs"])
    initial = host.capture()
    exposure_identity = {kind: exposure_key(initial["exposure"][kind]) for kind in ("optimizer", "replay")}
    require(all(value["process_id"] == host.pid for value in exposure_identity.values()), "Exposure belongs to another process")
    plan = dict(schema=SCHEMA, created_unix_s=time.time(), output_directory=str(directory), cpu=cpu,
        original_affinity=original, bindings=bindings, exposure_identity=exposure_identity,
        batch_size=4096, replay_cap=8, phases=list(PHASES), settle_s=settle_s, window_s=window_s,
        poll_s=period_s, binding_check_s=30,
        gates=dict(applied_rate_ratio=1.05, accepted_learner_rate_ratio=1.0,
                   amp_skip_fraction_allowance=.001, SPF_min=7.6, SPF_max=8.4),
        initial_snapshot=initial, limitations=LIMITATIONS)
    issues = api_issues(initial, plan)
    require(not issues, "Initial API guards: " + repr(issues))
    return plan


@contextmanager
def interrupt_handlers():
    def interrupted(signum, frame):
        raise TrialInterrupted(f"Received signal {signum}")
    saved = {value: signal.getsignal(value) for value in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        for value in saved:
            signal.signal(value, interrupted)
        yield
    finally:
        for value, handler in saved.items():
            signal.signal(value, handler)


@contextmanager
def block_restore_signals():
    """Defer a second handled signal until the original affinity is restored."""
    values = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, values)
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def summarize_phase(rows, plan):
    primary = [row for row in rows if row["stage"] == "primary"]
    require(len(primary) >= 2, "Not enough primary observations")
    a, z = primary[0], primary[-1]
    duration = z["observed_monotonic_s"] - a["observed_monotonic_s"]
    require(duration >= plan["window_s"], "Primary window ended before its fixed duration")
    delta = {key: z[key]-a[key] for key in CLOCKS}
    o = {key: z["exposure"]["optimizer"]["total"][key]-value
         for key, value in a["exposure"]["optimizer"]["total"].items()}
    replay = z["exposure"]["replay"]["accepted_learner_total"] - a["exposure"]["replay"]["accepted_learner_total"]
    require(delta["frame_count"] > 0 and o["outcomes_recorded"] > 0, "No primary progress")
    bins, anchor = [], a
    for row in primary[1:]:
        if row["observed_monotonic_s"] - anchor["observed_monotonic_s"] >= 30:
            frames = row["frame_count"] - anchor["frame_count"]
            bins.append(dict(start_monotonic_s=anchor["observed_monotonic_s"], end_monotonic_s=row["observed_monotonic_s"],
                             SPF=(row["optimized_samples"] - anchor["optimized_samples"])/frames if frames else None))
            anchor = row
    SPF = delta["optimized_samples"] / delta["frame_count"]
    healthy_bins = all(item["SPF"] is not None and plan["gates"]["SPF_min"] <= item["SPF"] <= plan["gates"]["SPF_max"] for item in bins)
    return dict(phase=a["phase"], duration_s=duration, observations=len(primary), start=a, end=z,
        logical_samples_per_s=delta["optimized_samples"]/duration,
        applied_admission_samples_per_s=o["applied"]*plan["batch_size"]/duration,
        accepted_learner_per_s=replay/duration, fleet_fps=delta["frame_count"]/duration,
        learner_fps=delta["learner_frame_count"]/duration, optimizer_delta=o,
        amp_skip_fraction=o["amp_skipped"]/o["outcomes_recorded"], SPF=SPF, nominal_30s_bins=bins,
        operationally_valid=healthy_bins and plan["gates"]["SPF_min"] <= SPF <= plan["gates"]["SPF_max"],
        bank_events=dict(writes=z["bank"]["writes"]-a["bank"]["writes"],
            write_duration_s=z["bank"]["write_duration_s"]-a["bank"]["write_duration_s"],
            writer_active_observations=sum(bool(row["bank"]["writer_active"]) for row in rows),
            cumulative_lock_max_ms_at_end=z["bank"]["snapshot_lock_max_ms"]),
        thread_sched_rates={key: (z["thread_sched"][key]-a["thread_sched"][key])/duration
                            for key in a["thread_sched"]})


def judge(results, plan):
    require([row["phase"] for row in results] == list(PHASES), "Incomplete A/B/A results")
    a, b, ar = results
    required_applied = plan["gates"]["applied_rate_ratio"] * max(a["applied_admission_samples_per_s"], ar["applied_admission_samples_per_s"])
    required_learner = max(a["accepted_learner_per_s"], ar["accepted_learner_per_s"])
    checks = dict(all_operationally_valid=all(row["operationally_valid"] for row in results),
        applied_rate=b["applied_admission_samples_per_s"] >= required_applied,
        accepted_learner_rate=b["accepted_learner_per_s"] >= required_learner,
        amp_skip_fraction=b["amp_skip_fraction"] <= max(a["amp_skip_fraction"], ar["amp_skip_fraction"]) + plan["gates"]["amp_skip_fraction_allowance"])
    return dict(outcome="qualified" if all(checks.values()) else "rejected", checks=checks,
                required_applied_samples_per_s=required_applied, required_accepted_learner_per_s=required_learner,
                automatic_promotion=False, final_affinity="original")


def restore_original(host, plan):
    with block_restore_signals():
        try:
            if host.thread_identity(plan["bindings"]["worker"]["thread"]["tid"]) != plan["bindings"]["worker"]:
                return dict(restored=False, reason="process_or_thread_identity_changed")
            if host.mask(plan["bindings"]["worker"]) != plan["original_affinity"]:
                host.set_mask(plan["bindings"]["worker"], plan["original_affinity"])
            return dict(restored=True)
        except (OSError, ValueError) as error:
            return dict(restored=False, reason=str(error))


def run_trial(host, plan):
    # The handlers remain installed through _run_trial's finally/restoration.
    with interrupt_handlers():
        return _run_trial(host, plan)


def _run_trial(host, plan):
    directory = Path(plan["output_directory"])
    host.verify(plan, plan["original_affinity"])
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "precommit.json", plan, immutable=True)
    frozen_digest = file_digest(directory / "precommit.json")
    status = dict(schema=SCHEMA, state="running", precommit_sha256=frozen_digest, results=[])
    current_mask, previous = plan["original_affinity"], plan["initial_snapshot"]
    restoration = None
    try:
        with (directory / "observations.jsonl").open("x") as stream:
            for phase in PHASES:
                require(file_digest(directory / "precommit.json") == frozen_digest, "Precommit changed")
                host.verify(plan, current_mask)
                target = [plan["cpu"]] if phase == "B" else plan["original_affinity"]
                if target != current_mask:
                    host.set_mask(plan["bindings"]["worker"], target)
                    current_mask = list(target)
                start = host.now(); anchor = None; checked = start; rows = []
                while True:
                    row = host.capture()
                    row["phase"] = phase
                    row["stage"] = "settle"
                    if row["observed_monotonic_s"] - start >= plan["settle_s"]:
                        anchor = row["observed_monotonic_s"] if anchor is None else anchor
                        row["stage"] = "primary"
                    row["issues"] = api_issues(row, plan, previous)
                    if host.now() - checked >= plan["binding_check_s"]:
                        try:
                            host.verify(plan, current_mask)
                        except (OSError, ValueError, subprocess.SubprocessError) as error:
                            row["issues"].append("binding_check:" + str(error))
                        checked = host.now()
                    rows.append(row); stream.write(json.dumps(row, allow_nan=False) + "\n"); stream.flush()
                    require(not row["issues"], "Observation guards: " + repr(row["issues"]))
                    previous = row
                    if anchor is not None and row["observed_monotonic_s"] - anchor >= plan["window_s"]:
                        host.verify(plan, current_mask)
                        break
                    host.sleep(plan["poll_s"])
                status["results"].append(summarize_phase(rows, plan))
                write_json(directory / "status.json", status)
            status.update(state="complete", decision=judge(status["results"], plan))
    except BaseException as error:
        status.update(state="interrupted" if isinstance(error, (TrialInterrupted, KeyboardInterrupt)) else "failed",
                      error=str(error), decision=dict(outcome="invalid", automatic_promotion=False))
        raise
    finally:
        # Restoration is deliberately independent of source/actor/control checks:
        # only the exact original process/thread identity may receive this mask.
        restoration = restore_original(host, plan)
        status["restoration"] = restoration
        if not restoration["restored"]:
            status.update(state="failed", decision=dict(outcome="invalid", automatic_promotion=False))
        write_json(directory / "status.json", status)
    require(restoration["restored"], "Original affinity could not be restored safely")
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trainer-pid", type=int, required=True)
    parser.add_argument("--fleet-unit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args(argv)
    try:
        host = Host(args.trainer_pid, args.fleet_unit)
        plan = prepare(host, args.output_dir)
        if args.launch:
            result = run_trial(host, plan)
            print(json.dumps({"state": result["state"], "decision": result["decision"], "output_directory": str(args.output_dir)}, indent=2))
        else:
            print(json.dumps(plan, indent=2, allow_nan=False))
    except (OSError, ValueError, subprocess.SubprocessError, TrialInterrupted, KeyboardInterrupt) as error:
        print(f"Inference affinity trial stopped/refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
