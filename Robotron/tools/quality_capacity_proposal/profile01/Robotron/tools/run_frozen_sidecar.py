#!/usr/bin/env python3
"""One isolated, inference-only 16- or 32-actor frozen cohort.

The default prints a launch plan. --launch explicitly starts a new job. Coordinate
with the training owner: the legacy global MAME launcher can kill this private
fleet. Never call startmame.sh here. GPU0 needs its own reevaluated baseline;
results from other devices/slot sets are historical, not paired controls.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import threading
import time

GAME = Path(__file__).resolve().parents[1]
ACTORS = 16
SLOTS = tuple(range(4096, 4096 + ACTORS))
INFERENCE_MAX_BATCH_SIZE = 16


def slots_for_actors(actors):
    """Explicit private profiles; actor count never changes compiled batch shapes."""
    if type(actors) is not int or actors not in (16, 32):
        raise ValueError("Private actor count must be exactly 16 or 32")
    return tuple(range(4096, 4096 + actors))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def retain_invalidity_reasons(result, secondary_reasons):
    reasons = ([result["reason"]] if result.get("valid") is False and result.get("reason") else [])
    reasons.extend(secondary_reasons)
    result["invalidity_reasons"] = list(dict.fromkeys(reasons))
    if reasons:
        result.update(valid=False, reason=reasons[0])


def timeout_evidence(before_shutdown, final_events, snapshot_unix_s):
    """Separate measured timeouts from deliberate shutdown without hiding them.

    A runtime print may be flushed only when MAME exits. Its integer unix_s
    still identifies it as runtime; same-second or missing timestamps fail
    conservatively. Events already visible at the snapshot always count.
    """
    runtime, final, cleanup = {}, {}, {}
    for slot in sorted(set(before_shutdown) | set(final_events)):
        observed = int(before_shutdown.get(slot, 0))
        events = final_events.get(slot, [])
        measured = max(observed, sum(
            index < observed or event.get("unix_s") is None
            or event["unix_s"] <= int(snapshot_unix_s)
            for index, event in enumerate(events)))
        runtime[slot], final[slot] = measured, len(events)
        cleanup[slot] = max(0, len(events)-measured)
    return dict(actor_timeout_logs=runtime,
                actor_timeout_logs_before_shutdown=dict(before_shutdown),
                actor_timeout_logs_after_shutdown=final,
                actor_cleanup_timeout_logs=cleanup,
                timeout_snapshot_unix_s=snapshot_unix_s,
                timeout_accounting="Pre-shutdown counts plus late-flushed runtime events; "
                "same-second/missing timestamps are runtime. Later cleanup events are diagnostic only.")


@dataclass(frozen=True)
class Job:
    checkpoint: Path
    directory: Path
    label: str
    device: str
    gpu_uuid: str | None = None
    port: int = 9999
    cohort_s: float = 120.0
    timeout_s: float = 600.0
    wait_us: int = 1000
    mame: Path = Path("/usr/games/mame")
    rompath: Path = GAME / "roms"
    cpu_threads: int = 2
    boot_assets: Path | None = None
    inference_backend: str = "eager"
    game_boundary_diagnostics: bool = True
    completion_policy: str = "confirmed_reset_reserves_v1"
    actors: int = ACTORS

    @property
    def actor_slots(self):
        return slots_for_actors(self.actors)

    def validate(self, *, require_boot_assets=False):
        slots_for_actors(self.actors)
        if self.directory != self.directory.resolve():
            raise ValueError("Job directory must be absolute and resolved")
        if not self.checkpoint.is_file():
            raise ValueError("An existing immutable checkpoint is required")
        if self.directory.exists():
            raise ValueError("Job directory must be new; journals are never reused")
        if (self.directory == GAME or GAME.is_relative_to(self.directory)
                or self.directory.is_relative_to(GAME / "models_dqn")
                or self.directory.is_relative_to(Path("/dev/shm"))):
            raise ValueError("Job output must be separate from training model/replay paths")
        if not self.label.strip() or len(self.label) > 160:
            raise ValueError("A nonempty label of at most 160 characters is required")
        if not 1024 <= self.port <= 65535 or self.port == 9998:
            raise ValueError("Choose a nonproduction high port, normally 9999")
        if not 0 < self.cohort_s < self.timeout_s or self.timeout_s > 7200:
            raise ValueError("Require 0 < cohort_s < timeout_s <= 7200")
        if not 0 <= self.wait_us <= 10000 or not 1 <= self.cpu_threads <= 8:
            raise ValueError("Invalid bounded host wait or CPU thread limit")
        if self.device not in ("cpu", "cuda"):
            raise ValueError("device must be cpu or cuda")
        if self.inference_backend not in ("eager", "inductor"):
            raise ValueError("inference_backend must be eager or inductor")
        if self.completion_policy != "confirmed_reset_reserves_v1" or self.game_boundary_diagnostics is not True:
            raise ValueError("Confirmed full-game resets and boundary diagnostics are required")
        if type(self.game_boundary_diagnostics) is not bool:
            raise ValueError("game_boundary_diagnostics must be a bool")
        if self.inference_backend == "inductor" and self.device != "cuda":
            raise ValueError("The opt-in inductor inference backend requires CUDA")
        if self.device == "cuda" and not (self.gpu_uuid or "").startswith("GPU-"):
            raise ValueError("CUDA sidecars require an explicit physical GPU UUID")
        if not self.mame.is_file() or not os.access(self.mame, os.X_OK):
            raise ValueError("MAME executable is unavailable")
        if not self.rompath.is_dir():
            raise ValueError("ROM directory is unavailable")
        if require_boot_assets and self.boot_assets is None:
            raise ValueError("An initialized, validated private boot-assets snapshot is required")
        if self.boot_assets is not None:
            boot_module().load_snapshot(self.boot_assets)

    def plan(self):
        return dict(checkpoint=str(self.checkpoint), directory=str(self.directory),
                    label=self.label, device=self.device, gpu_uuid=self.gpu_uuid,
                    host="127.0.0.1", port=self.port, actors=self.actors,
                    actor_slots=list(self.actor_slots),
                    cohort_s=self.cohort_s, timeout_s=self.timeout_s, wait_us=self.wait_us,
                    epsilon=0, expert_ratio=0, difficulty=5, start_level=1,
                    replay_enabled=False, fp16=False, mame=str(self.mame),
                    inference_max_batch_size=INFERENCE_MAX_BATCH_SIZE,
                    rompath=str(self.rompath), cpu_threads=self.cpu_threads,
                    boot_assets=str(self.boot_assets) if self.boot_assets else None,
                    inference_backend=self.inference_backend,
                    game_boundary_diagnostics=self.game_boundary_diagnostics,
                    completion_policy=self.completion_policy,
                    comparison_caveat="Reevaluate the incumbent on this same device, high-slot set, "
                    "fresh private MAME configuration and pacing before candidate comparisons.")


def boot_module():
    try:
        from . import sidecar_boot
    except ImportError:
        import sidecar_boot
    return sidecar_boot


def build_inference_actor(factory, checkpoint, job):
    # The opt-in adapter performs strict compilation and complete warmup in
    # its constructor. No listener or MAME process exists before this returns.
    actor = factory(checkpoint, device=job.device, inference_backend=job.inference_backend)
    if (actor.inference_backend != job.inference_backend
            or actor.numeric_policy.get("compiled") != (job.inference_backend == "inductor")):
        raise RuntimeError("Requested inference backend differs from the prepared actor policy")
    return actor


def configure_environment(job):
    """Run before importing Torch, config, model, or the socket server."""
    if any(name == "torch" or name.endswith(".config") and "dqn" in name
           for name in sys.modules) or "config" in sys.modules:
        raise RuntimeError("Sidecar must start in a fresh process before training imports")
    if "robotron-socketwait" in Path("/proc/self/maps").read_text():
        raise RuntimeError("The select shim must never preload the Python evaluator")
    os.environ.pop("LD_PRELOAD", None)
    os.environ.pop("ROBOTRON_SOCKET_WAIT_ACTIVE", None)
    os.environ["CUDA_VISIBLE_DEVICES"] = job.gpu_uuid if job.device == "cuda" else ""
    os.environ["ROBOTRON_DQN_MODEL_DIR"] = str(job.directory / "isolated-models")
    os.environ["ROBOTRON_DQN_CONTROL_PATH"] = str(job.directory / "isolated-control.json")
    os.environ["ROBOTRON_RUN_DIR"] = str(job.directory / "journal")
    os.environ["ROBOTRON_GAME_COMPLETION_POLICY"] = job.completion_policy
    # Bind the plan's explicit choice; inherited environment never opts in.
    os.environ["ROBOTRON_GAME_BOUNDARY_DIAGNOSTICS"] = "1" if job.game_boundary_diagnostics else "0"
    os.environ["ROBOTRON_TRAIN_GPU"] = "0"
    os.environ["ROBOTRON_INFERENCE_GPU"] = "0"
    os.environ["OMP_NUM_THREADS"] = str(job.cpu_threads)
    os.environ["MKL_NUM_THREADS"] = str(job.cpu_threads)
    os.environ["OPENBLAS_NUM_THREADS"] = str(job.cpu_threads)
    os.environ["TORCHINDUCTOR_COMPILE_THREADS"] = "2"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["TORCHINDUCTOR_CACHE_DIR"] = str(job.directory / "torch-cache")
    os.environ["TRITON_CACHE_DIR"] = str(job.directory / "triton-cache")
    os.environ["TORCH_EXTENSIONS_DIR"] = str(job.directory / "torch-extensions")
    os.environ["TORCH_HOME"] = str(job.directory / "torch-home")
    os.environ["CUDA_CACHE_PATH"] = str(job.directory / "cuda-cache")
    sys.dont_write_bytecode = True


def copy_checkpoint(job):
    before = sha256(job.checkpoint)
    destination = job.directory / "checkpoint.pt"
    shutil.copyfile(job.checkpoint, destination)
    if sha256(destination) != before or sha256(job.checkpoint) != before:
        raise RuntimeError("Checkpoint changed while making the isolated copy")
    destination.chmod(0o444)
    return destination, before


def mame_spec(job, slot, library=None):
    """Pure command/environment construction; no process discovery or globals."""
    if type(slot) is not int or slot not in job.actor_slots:
        raise ValueError("Unexpected sidecar actor slot")
    private = job.directory / "actors" / str(slot)
    command = [str(job.mame), "robotron", "-rompath", str(job.rompath),
               "-cheat", "-nothrottle", "-sound", "none", "-video", "none",
               "-skip_gameinfo", "-autoboot_script", str(GAME / "Scripts/main.lua"),
               "-cfg_directory", str(private / "cfg"),
               "-nvram_directory", str(private / "nvram"),
               "-inipath", str(private / "ini"),
               "-state_directory", str(private / "sta"),
               "-snapshot_directory", str(private / "snap"),
               "-diff_directory", str(private / "diff"),
               "-input_directory", str(private / "inp"),
               "-share_directory", str(private / "share"),
               "-comment_directory", str(private / "comments")]
    environment = dict(os.environ)
    for name in ("LD_PRELOAD", "ROBOTRON_SOCKET_WAIT_ACTIVE"):
        environment.pop(name, None)
    environment.update(ROBOTRON_SOCKET_ADDRESS=f"127.0.0.1:{job.port}",
                       ROBOTRON_CLIENT_SLOT=str(slot), ROBOTRON_EVAL_MODE="1",
                       ROBOTRON_PREVIEW_CLIENT="0", ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES="0",
                       ROBOTRON_SOCKET_WAIT_US=str(job.wait_us),
                       ROBOTRON_SOCKET_WAIT_PORT=str(job.port))
    if job.wait_us:
        if library is None:
            raise ValueError("Enabled socket waits require the validated shim")
        environment["LD_PRELOAD"] = str(library)
    return command, environment, private


class PrivateFleet:
    """Only the Popen handles created by this object may be signaled."""
    def __init__(self, job, library=None, *, popen=subprocess.Popen, expected_boot_identity=None):
        self.job, self.library, self.popen = job, library, popen
        self.processes, self.streams = {}, []
        self.boot_identity = (expected_boot_identity or boot_module().load_snapshot(job.boot_assets)["identity"]
                              if job.boot_assets is not None else None)
        self.boot_restores = {}

    def launch(self):
        try:
            for slot in self.job.actor_slots:
                command, environment, private = mame_spec(self.job, slot, self.library)
                for name in ("cfg", "nvram", "ini", "sta", "snap", "diff", "inp", "share", "comments"):
                    (private / name).mkdir(parents=True)
                if self.job.boot_assets is None:
                    raise ValueError("Private MAME launch requires initialized boot assets")
                restored = boot_module().restore_snapshot(self.job.boot_assets, private)
                if restored["identity"] != self.boot_identity:
                    raise RuntimeError("Boot snapshot identity changed between actor restores")
                self.boot_restores[slot] = {name: restored[name] for name in
                                          ("identity", "manifest_sha256", "restored_paths", "files")}
                stream = (private / "console.log").open("w")
                self.streams.append(stream)
                self.processes[slot] = self.popen(command, env=environment, cwd=private,
                    stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                    close_fds=True, start_new_session=True)
        except BaseException:
            self.stop()
            raise

    def exited(self):
        return {slot: process.returncode for slot, process in self.processes.items()
                if process.poll() is not None}

    def stop(self):
        # No pgrep/pkill, global pidfile, launcher, or process-group wildcard.
        errors = []
        for process in self.processes.values():
            if process.poll() is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                except OSError as error:
                    errors.append(str(error))
        deadline = time.monotonic() + 5
        for process in self.processes.values():
            try:
                process.wait(timeout=max(.01, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired) as error:
                    errors.append(str(error))
            except OSError as error:
                errors.append(str(error))
        for stream in self.streams:
            stream.close()
        self.streams.clear()
        return errors

    def timeout_logs(self):
        return {slot: len(events) for slot, events in self.timeout_events().items()}

    def timeout_events(self):
        result = {}
        for slot in self.job.actor_slots:
            path = self.job.directory / "actors" / str(slot) / "console.log"
            if not path.exists():
                continue
            events = []
            for line in path.read_text(errors="replace").splitlines():
                if "[SOCKET ACTION TIMEOUT]" in line:
                    match = re.search(r"\bunix_s=(\d+)\b", line)
                    events.append(dict(unix_s=int(match[1]) if match else None))
            result[slot] = events
        return result

    def backend_evidence(self):
        evidence = {}
        pattern = r"\[robotron-socket-wait\] pid=(\d+) fd=(\d+) port=(\d+) interval_us=(\d+)"
        for slot, process in self.processes.items():
            path = self.job.directory / "actors" / str(slot) / "console.log"
            content = path.read_text(errors="replace") if path.exists() else ""
            matches = [dict(zip(("pid", "fd", "port", "interval_us"), map(int, match)))
                       for match in re.findall(pattern, content)]
            observed = any(row["pid"] == process.pid and row["port"] == self.job.port
                           and row["interval_us"] == self.job.wait_us for row in matches)
            evidence[slot] = dict(pid=process.pid, matching_activation=observed,
                                  activations=matches[:5], activation_count=len(matches))
        return evidence


def fixed_boundary(server, generation, actor_slots=SLOTS):
    required = tuple(actor_slots)
    if (any(type(slot) is not int for slot in required)
            or required != slots_for_actors(len(required))):
        raise ValueError("Exact declared private actor slots required")
    result = server.measurement_boundary_status(generation)
    exact = (result.get("clients") == len(required)
             and result.get("actor_slots") == list(required))
    result["ready"] = (result.get("ready", False) and exact
                       and not server.inference_only_error)
    result["required_actor_slots"] = list(required)
    return result


def check_protocol(config, actor, checkpoint_signature, checkpoint):
    expected = dict(start_advanced=False, start_level_min=1, epsilon_pct=0,
                    expert_pct=0, auto_curriculum=False, difficulty=5)
    if config.game_settings.snapshot() != expected or not config.metrics.measurement_active:
        raise RuntimeError("Frozen evaluation settings or measurement mode changed")
    if actor.training_enabled or getattr(actor, "memory", None) is not None:
        raise RuntimeError("Inference-only actor acquired training/replay state")
    if getattr(actor, "inference_error", None):
        raise RuntimeError(f"Actor inference failed: {actor.inference_error}")
    if checkpoint_identity(checkpoint) != checkpoint_signature:
        raise RuntimeError("Immutable checkpoint copy changed")


def checkpoint_identity(checkpoint):
    stat = checkpoint.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_mode


def source_hashes():
    paths = [Path(__file__), GAME / "tools/sidecar_boot.py",
             GAME / "tools/confirmed_terminal_evidence.py",
             GAME / "Scripts/main.lua", GAME / "Scripts/robotron_socket_wait.c"]
    paths.extend(GAME / "Scripts/dqn" / name for name in (
        "config.py", "model.py", "actor_tags.py", "socket_server.py", "game_journal.py",
        "managed_measurement.py", "inference_actor.py", "nstep_buffer.py", "rejected_gap_telemetry.py"))
    return {str(path.relative_to(GAME)): sha256(path) for path in paths}


def cleanup_job(fleet, server, worker, controller, prior_handlers):
    """Attempt every cleanup even when an earlier operation fails."""
    errors, handlers, safe_to_restore = [], [], True
    server.shutdown_event.set()  # Exclude our intentional EOFs from the fatal latch.
    batcher_thread = getattr(server.inference_batcher, "_thread", None)
    try:
        with server.client_lock:
            handlers = list(server.clients.values())
    except Exception as error:
        errors.append(f"Handler snapshot failed: {error}")
    for name, operation in (("Fleet", fleet.stop), ("Server", server.stop)):
        try:
            errors.extend(operation() or [])
        except Exception as error:
            errors.append(f"{name} cleanup failed: {error}")
    try:
        if worker.ident is not None:
            worker.join(timeout=10)
        join_deadline = time.monotonic()+5
        for handler in [*handlers, batcher_thread]:
            if isinstance(handler, threading.Thread):
                handler.join(timeout=max(.01, join_deadline-time.monotonic()))
        if worker.is_alive() or any(isinstance(handler, threading.Thread)
                                   and handler.is_alive() for handler in [*handlers, batcher_thread]):
            errors.append("Socket server/handler did not stop")
            safe_to_restore = False
    except Exception as error:
        errors.append(f"Thread cleanup failed: {error}")
        safe_to_restore = False
    try:
        if safe_to_restore:
            controller.exit()
        else:
            # This process is disposable. A hung inference worker may own the
            # actor lock; entering restoration could make cleanup unbounded.
            errors.append("Skipped policy restoration because a worker is still live")
    except Exception as error:
        errors.append(f"Controller cleanup failed: {error}")
    for signum, handler in prior_handlers.items():
        try:
            signal.signal(signum, handler)
        except Exception as error:
            errors.append(f"Signal handler restoration failed: {error}")
    return errors


def cleanup_with_timeout_evidence(fleet, server, worker, controller, prior_handlers, *, clock=time.time):
    # Take the validity snapshot before cleanup sets shutdown_event or closes
    # sockets. Later owner-induced read timeouts are retained separately.
    snapshot_error = None
    try:
        before_shutdown = fleet.timeout_logs()
    except OSError as error:
        before_shutdown, snapshot_error = {}, str(error)
    # A log scan can cross a wall-clock second. Publish intentional shutdown
    # first, then timestamp its boundary, so an event during that scan can
    # never be mistaken for cleanup merely because its output flushed late.
    server.shutdown_event.set()
    snapshot_unix_s = clock()
    errors = cleanup_job(fleet, server, worker, controller, prior_handlers)
    if snapshot_error:
        errors.append(f"Runtime timeout snapshot failed: {snapshot_error}")
    try:
        final_events = fleet.timeout_events()
    except OSError as error:
        final_events = {}
        errors.append(f"Final timeout diagnostics failed: {error}")
    return timeout_evidence(before_shutdown, final_events, snapshot_unix_s), errors


def run(job):
    job.validate(require_boot_assets=True)
    boot_identity = boot_module().load_snapshot(job.boot_assets)
    configure_environment(job)
    job.directory.mkdir(parents=True)
    checkpoint, identity = copy_checkpoint(job)
    write_json(job.directory / "plan.json", dict(job.plan(), checkpoint_sha256=identity))
    # Imports occur only after all process-global paths and device visibility are isolated.
    sys.path.insert(0, str(GAME / "Scripts"))
    import torch
    from dqn import config
    from dqn.inference_actor import InferenceActor
    from dqn.managed_measurement import ManagedMeasurement
    from dqn.socket_server import SocketServer
    try:
        from .compare_frozen_measurements import validate_receipt
        from .build_socket_wait import build
    except ImportError:
        from compare_frozen_measurements import validate_receipt
        from build_socket_wait import build
    torch.set_num_threads(job.cpu_threads)
    torch.set_num_interop_threads(1)
    config.RL_CONFIG.inference_batch_max_size = INFERENCE_MAX_BATCH_SIZE
    actor = build_inference_actor(InferenceActor, checkpoint, job)
    metadata = dict(actor.checkpoint_metadata)
    if (metadata.get("total_training_steps", actor.training_steps) != actor.training_steps
            or metadata.get("total_optimized_samples", actor.optimized_samples) != actor.optimized_samples):
        raise ValueError("Checkpoint metric/agent clocks differ; the shared receipt validator cannot compare this lineage")
    for key in ("learner_frame_count", "frame_count", "measurement_frame_count"):
        setattr(config.metrics, key, int(metadata[key]))
    config.metrics.total_training_steps = int(metadata.get("total_training_steps", actor.training_steps))
    config.metrics.total_optimized_samples = actor.optimized_samples
    config.metrics.training_enabled = False
    config.metrics.preview_capture_enabled = False
    config.metrics.hud_enabled = False
    for name, value in dict(start_advanced=False, start_level_min=1, epsilon_pct=0,
                            expert_pct=0, auto_curriculum=False, difficulty=5).items():
        setattr(config.game_settings, name, value)
    library = build(job.directory / "socket-wait-build") if job.wait_us else None
    server = SocketServer("127.0.0.1", job.port, actor, replay_enabled=False)
    if server.async_buffer is not None or actor.checkpoint_sha256 != identity:
        raise RuntimeError("Inference-only isolation/checkpoint identity check failed")
    controller = ManagedMeasurement(actor, config.metrics, server.game_journal,
        boundary_status=lambda generation: fixed_boundary(server, generation, job.actor_slots))
    fleet = PrivateFleet(job, library, expected_boot_identity=boot_identity["identity"])
    worker = threading.Thread(target=server.start, name="frozen-sidecar-server", daemon=True)
    stopped = threading.Event()
    prior_handlers = {}
    for signum in (signal.SIGTERM, signal.SIGINT):
        prior_handlers[signum] = signal.signal(signum, lambda *_: stopped.set())
    result, failure = {}, None
    checkpoint_signature = checkpoint_identity(checkpoint)
    loaded_source_hashes = source_hashes()
    started = time.time()
    try:
        controller.enter(job.label, cohort_s=job.cohort_s, timeout_s=job.timeout_s)
        worker.start()
        deadline = time.monotonic() + 15
        while not server.running:
            if not worker.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Private socket server did not bind")
            time.sleep(.02)
        fleet.launch()
        while True:
            check_protocol(config, actor, checkpoint_signature, checkpoint)
            if server.inference_only_error:
                raise RuntimeError(server.inference_only_error)
            if stopped.is_set():
                raise RuntimeError("Sidecar interrupted")
            if dead := fleet.exited():
                raise RuntimeError(f"Owned actor exited: {dead}")
            status = controller.tick()
            if status["phase"] != "warming":
                boundary = fixed_boundary(server, controller.generation, job.actor_slots)
                if not boundary["ready"]:
                    raise RuntimeError("Actor disconnected or changed after admission")
            if not worker.is_alive() or not server.running:
                raise RuntimeError("Private server stopped unexpectedly")
            display = {key: value for key, value in status.items() if key not in ("rows", "cohort")}
            display["cohort"] = {key: value for key, value in status.get("cohort", {}).items() if key != "rows"}
            display.update(job=job.plan(), checkpoint_sha256=identity,
                           elapsed_s=time.time()-started,
                           actor_pids={slot: process.pid for slot, process in fleet.processes.items()})
            write_json(job.directory / "status.json", display)
            if status["complete"]:
                result = status
                break
            time.sleep(.25)
    except BaseException as error:
        failure = f"{type(error).__name__}: {error}"
        reason = ("server_or_actor_connection_failed" if server.inference_only_error else
                  "actor_inference_failed" if actor.inference_error else
                  "sidecar_isolation_or_runtime_failure")
        result = dict(controller.status(), complete=True, valid=False,
                      reason=reason, error=failure)
    finally:
        # No nonmeasurement frame can execute after exit clears the mode.
        timeout_diagnostics, cleanup_errors = cleanup_with_timeout_evidence(
            fleet, server, worker, controller, prior_handlers)
    result.update(active=False, phase="finished", job=job.plan(), checkpoint_sha256=identity,
                  checkpoint_path=str(checkpoint), source_checkpoint_path=str(job.checkpoint),
                  checkpoint_metadata=metadata, numeric_policy=actor.numeric_policy,
                  inference_backend=job.inference_backend, compile_report=actor.compile_report,
                  boot_assets=boot_identity,
                  boot_restores=fleet.boot_restores,
                  **timeout_diagnostics, cleanup_errors=cleanup_errors,
                  ended_unix_s=time.time(),
                  elapsed_s=time.time()-started, runtime=dict(torch=torch.__version__,
                  device=job.device, cuda_visible_devices=os.environ["CUDA_VISIBLE_DEVICES"],
                  cuda=torch.version.cuda, cudnn=torch.backends.cudnn.version(),
                  gpu_name=torch.cuda.get_device_name(0) if job.device == "cuda" else None,
                  compute_capability=list(torch.cuda.get_device_capability(0))
                  if job.device == "cuda" else None),
                  engine_version=metadata["engine_version"], state_size=metadata["state_size"],
                  single_frame_state_size=metadata["single_frame_state_size"],
                  frame_stack=metadata["frame_stack"], wire_params_count=config.WIRE_PARAMS_COUNT,
                  wire_version=2, frame_protocol="robotron-v2", source_hashes=loaded_source_hashes,
                  ended_source_hashes=source_hashes(),
                  socket_wait=dict(wait_us=job.wait_us, port=job.port,
                                   library=str(library) if library else None,
                                   sha256=sha256(library) if library else None,
                                   actors=fleet.backend_evidence()),
                  server_error=server.inference_only_error, inference_error=actor.inference_error)
    invalidity_reasons = []
    if cleanup_errors:
        invalidity_reasons.append("sidecar_cleanup_failed")
    if server.inference_only_error:
        invalidity_reasons.append("server_or_actor_connection_failed")
    if actor.inference_error:
        invalidity_reasons.append("actor_inference_failed")
    if job.wait_us and (len(result["socket_wait"]["actors"]) != job.actors or
                       not all(row["matching_activation"] for row in result["socket_wait"]["actors"].values())):
        invalidity_reasons.append("socket_wait_backend_not_verified")
    if result["source_hashes"] != result["ended_source_hashes"]:
        invalidity_reasons.append("source_changed_during_evaluation")
    if sha256(checkpoint) != identity:
        invalidity_reasons.append("checkpoint_copy_hash_changed")
    if any(result["actor_timeout_logs"].values()):
        invalidity_reasons.append("actor_action_receive_timeout")
    try:
        if boot_module().load_snapshot(job.boot_assets)["identity"] != boot_identity["identity"]:
            invalidity_reasons.append("boot_snapshot_changed_during_evaluation")
    except (OSError, ValueError, RuntimeError):
        invalidity_reasons.append("boot_snapshot_invalid_after_evaluation")
    retain_invalidity_reasons(result, invalidity_reasons)
    if result.get("valid"):
        try:
            validate_receipt(result)
            try:
                from .confirmed_terminal_evidence import collect_successors, validate_receipt_terminals
            except ImportError:
                from confirmed_terminal_evidence import collect_successors, validate_receipt_terminals
            rows = result.get("rows", result.get("cohort", {}).get("rows", []))
            def read_original(name):
                raw = (job.directory / "journal" / name).read_bytes()
                if raw and not raw.endswith(b"\n"):
                    raise ValueError("Partial original terminal journal")
                return [json.loads(line) for line in raw.splitlines()]
            result["terminal_successors"] = collect_successors(rows,
                read_original("games.jsonl"), read_original("measurement_starts.jsonl"))
            result["terminal_journal_sha256"] = {name: sha256(job.directory / "journal" / name)
                for name in ("games.jsonl", "measurement_starts.jsonl")}
            validate_receipt_terminals(result, rows)
            result["receipt_validator"] = "passed"
        except (OSError, ValueError, TypeError, KeyError) as error:
            result.update(valid=False, reason="receipt_validation_failed", validation_error=str(error))
            result["invalidity_reasons"].append("receipt_validation_failed")
    write_json(job.directory / "receipt.json", result)
    print(json.dumps({key: result.get(key) for key in
                     ("valid", "reason", "label", "count", "mean", "elapsed_s")}))
    return 0 if result.get("valid") else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)
    parser.add_argument("--gpu-uuid")
    parser.add_argument("--inference-backend", choices=("eager", "inductor"), default="eager",
                        help="inductor opts into strict CUDA compile/warmup before server/fleet startup")
    parser.add_argument("--game-boundary-diagnostics", action="store_true", default=True,
                        help="opt in to primitive game-boundary inputs in private journal contexts")
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--cohort-s", type=float, default=120)
    parser.add_argument("--timeout-s", type=float, default=600)
    parser.add_argument("--wait-us", type=int, default=1000)
    parser.add_argument("--cpu-threads", type=int, default=2)
    parser.add_argument("--actors", type=int, choices=(16, 32), default=ACTORS,
                        help="private fleet size; compiled inference remains limited to batches1..16")
    parser.add_argument("--mame", type=Path, default=Path("/usr/games/mame"))
    parser.add_argument("--rompath", type=Path, default=GAME / "roms")
    parser.add_argument("--boot-assets", type=Path,
                        help="required for launch: immutable initialized MAME cfg/NVRAM/ini snapshot")
    parser.add_argument("--launch", action="store_true", help="start this isolated job; default prints a plan")
    args = parser.parse_args(argv)
    job = Job(args.checkpoint.resolve(), args.job_dir.resolve(), args.label, args.device,
              args.gpu_uuid, args.port, args.cohort_s, args.timeout_s, args.wait_us,
              args.mame.resolve(), args.rompath.resolve(), args.cpu_threads,
              args.boot_assets.resolve() if args.boot_assets else None, args.inference_backend,
              game_boundary_diagnostics=args.game_boundary_diagnostics, actors=args.actors)
    job.validate()
    if not args.launch:
        print(json.dumps(job.plan(), indent=2))
        return 0
    return run(job)


if __name__ == "__main__":
    raise SystemExit(main())
