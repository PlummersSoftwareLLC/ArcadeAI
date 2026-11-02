#!/usr/bin/env python3
"""One root-bound live8 maintenance operation. Default prints a literal plan.

Source preparation only. No historical experiment driver is invoked. The live
adapter imports only the pinned ownership/measurement primitives on --launch.
The ordinary newest persisted latest is always the boot input; an insurance
checkpoint establishes a minimum clock floor, never an automatic rollback.
"""
from __future__ import annotations

import argparse
import base64
import copy
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request

SCHEMA = "robotron-live8-maintenance-job-v1"
RESULT_SCHEMA = "robotron-live8-maintenance-result-v1"
FLAG = "DQN_RECOMPUTED_CE_CAPTURE_DIR"
OLD_FLAG = "DQN_EXECUTED_CE_TRACE_DIR"
CLOCKS = ("training_steps", "optimized_samples", "learner_frame_count", "frame_count")
NAMES = ("agent.py", "training.py", "replay_buffer.py", "prefetch.py", "recomputed_ce_capture.py")
MAX_JSON = 2 << 20
MAX_SOURCE = 4 << 20
MAX_CAPTURE = 6 << 30
MAX_PAYLOAD = 640 << 20
BLOCKED = frozenset(("checkpoint_at_frame.py", "run_quality_campaign.py", "run_frozen_sidecar.py",
    "cuda_trace_parent.py", "cuda_trace_worker.py", "forensic_parent.py", "forensic_worker.py",
    "whole_agent_smoke.py", "whole_agent_worker.py", "inference_worker_affinity.py", "parallel_state_fill_trial.py",
    "inference_cpu_reservation.py", "cpu_reservation_trial.py", "run_live8_maintenance.py",
    "verify_maintenance_checkpoint.py", "verify_retained_ce.py", "verify_saved_checkpoint.py"))


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def canonical(value, exists=True):
    path = Path(value)
    require(path.is_absolute() and path == path.resolve(strict=exists), "Noncanonical path: " + str(path))
    return path


def fingerprint(path, limit=None):
    path = canonical(str(path))
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), "Expected nonsymlink regular file: " + str(path))
    require(limit is None or before.st_size <= limit, "File exceeds bounded read: " + str(path))
    digest = hashlib.sha256()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), "File changed before open")
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
        require(identity(os.fstat(stream.fileno())) == identity(before), "File changed while reading")
    require(identity(path.lstat()) == identity(before), "File path changed while reading")
    return dict(path=str(path), sha256=digest.hexdigest(), bytes=before.st_size, identity=identity(before))


def pin(value, limit=None):
    require(isinstance(value, dict) and set(value) == {"path", "sha256", "bytes", "identity"}, "Invalid file pin")
    require(re.fullmatch("[0-9a-f]{64}", value["sha256"] or ""), "Invalid pinned SHA256")
    require(fingerprint(value["path"], limit) == value, "Pinned file changed: " + value["path"])
    return Path(value["path"])


def read_json(value):
    path = pin(value, MAX_JSON)
    result = json.loads(path.read_text())
    pin(value, MAX_JSON)
    return result


def read_source(value):
    path = pin(value, MAX_SOURCE)
    data = path.read_bytes()
    pin(value, MAX_SOURCE)
    require(hashlib.sha256(data).hexdigest() == value["sha256"], "Staged source bytes differ")
    return data


def capture_row_checks(entry, index, expected, capture_id):
    require(entry["index"] == index and entry["capture_complete"] is True and not entry["observer_errors"]
        and entry["optimizer_outcome"] in ("applied_admission", "amp_skipped")
        and entry["draw_batch_join_checked"] is True and entry["staged_draw_join_checked"] is True
        and entry == expected and entry["draw_capture_id"] == capture_id, "Invalid consumed capture/draw join")
    lease = entry["prefetch"]
    held = {key:lease[key] for key in ("lease_epoch", "owner_epoch_at_consumption", "current")} if lease else None
    require(lease is not None and lease["current"] is True and lease["lease_epoch"] == lease["owner_epoch_at_consumption"]
        and all(entry["prefetch_" + name] == held for name in ("begin", "pre_loss", "exit")), "Consumed lease epoch/current proof differs")


def first_attempt_clock_proof(row, saved, capture_id):
    capture_row_checks(row, 1, row, capture_id)
    observed = dict(training_steps=row["before"]["training_steps"], optimized_samples=row["before"]["optimized_samples"],
        frame_count=row["frame_context"]["frame_count"], learner_frame_count=row["frame_context"]["learner_frame_count"])
    expected = {key:saved[key] for key in CLOCKS}
    require(observed == expected, "First consumed PRE four clocks differ from verified stopped latest")
    return dict(observed=observed, verified_saved=expected, optimizer_outcome=row["optimizer_outcome"],
        scope="Completed first consumed PRE clock equality before any owned actor resumes; no coherent replay/actor/RNG anchor")


def boot_log_proof(payload, latest):
    """Successful original load prints, not merely later advancing counters."""
    text = payload.decode(errors="replace")
    agent = re.findall(r"^Loaded v28 model from (.+)$", text, re.MULTILINE)
    main = re.findall(r"^Loaded model from: (.+)$", text, re.MULTILINE)
    require(agent == [latest] and main == [latest], "New stdout does not prove exactly one successful latest boot")
    require("[RECOMPUTED CE CAPTURE INVALID]" not in text, "Capture observation invalidated during startup")
    return dict(agent_load_paths=agent, main_load_paths=main,
        interpretation="Pinned original load source plus exact-graph postload/optimizer/scaler refusal guards; no exported loaded-clock API exists")


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(path, value):
    """Create once; even failure paths never rewrite prior evidence."""
    data = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    require(len(data) <= MAX_JSON, "Receipt exceeds2MiB")
    with Path(path).open("xb") as stream:
        stream.write(data); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    fsync_directory(Path(path).parent)
    return fingerprint(path, MAX_JSON)


def exclusive_copy(source, target):
    before = fingerprint(source)
    require(200 << 20 <= before["bytes"] <= 400 << 20, "Checkpoint exceeds inherited200..400MiB bound")
    with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), "rb") as src, Path(target).open("xb") as dst:
        require(identity(os.fstat(src.fileno())) == before["identity"], "Checkpoint copy open race")
        for chunk in iter(lambda: src.read(4 << 20), b""):
            dst.write(chunk)
        require(identity(os.fstat(src.fileno())) == before["identity"], "Checkpoint changed during copy")
        dst.flush(); os.fchmod(dst.fileno(), 0o444); os.fsync(dst.fileno())
    fsync_directory(Path(target).parent)
    require(fingerprint(source) == before, "Checkpoint path changed during copy")
    copied = fingerprint(target)
    require(copied["sha256"] == before["sha256"] and copied["bytes"] == before["bytes"]
        and copied["identity"]["inode"] != before["identity"]["inode"], "Independent checkpoint copy differs")
    return before, copied


class Sources:
    """Only known before/after bytes are eligible for a whole-set reconciliation."""
    def __init__(self, entries, directory):
        self.entries, self.directory, self.staged = entries, directory, {}

    def stage(self):
        for entry in self.entries:
            after = read_source(entry["after"])
            before = read_source(entry["before"]) if entry["before"] else None
            require(before is not None or not Path(entry["destination"]).exists(), "New observer already exists")
            self.staged[entry["destination"]] = (before, after)
            for phase, data in (("before", before), ("after", after)):
                name = Path(entry["destination"]).name + "." + phase
                if data is None:
                    publish(self.directory / (name + ".absent.json"), dict(absent=True, destination=entry["destination"]))
                else:
                    with (self.directory / name).open("xb") as stream:
                        stream.write(data); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        fsync_directory(self.directory)
        self.check("before")

    def observed(self, entry):
        path = Path(entry["destination"])
        require(not path.is_symlink(), "Source became a symlink")
        if not path.exists():
            return None
        require(stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size <= MAX_SOURCE, "Invalid source file")
        return path.read_bytes()

    def check(self, phase):
        for entry in self.entries:
            require(self.observed(entry) == self.staged[entry["destination"]][phase == "after"],
                "Source set is not wholly " + phase + ": " + entry["destination"])

    def reconcile(self, phase, absent, blocked_signals):
        absent()  # Never replace imported source under any still-live trainer.
        for entry in self.entries:
            require(self.observed(entry) in self.staged[entry["destination"]], "Unknown source bytes; manual recovery required")
        for index, entry in enumerate(self.entries):
            absent()
            data = self.staged[entry["destination"]][phase == "after"]
            path = Path(entry["destination"])
            with blocked_signals():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    fd, temporary_name = tempfile.mkstemp(prefix=".live8-maintenance-", dir=path.parent)
                    temporary = Path(temporary_name)
                    created = os.fstat(fd)
                    mode = int(entry["before"]["identity"]["mode"], 8) if entry["before"] else 0o644
                    try:
                        with os.fdopen(fd, "wb") as stream:
                            stream.write(data); stream.flush(); os.fchmod(stream.fileno(), mode); os.fsync(stream.fileno())
                        os.replace(temporary, path)
                    finally:
                        # Only the exact temp inode created by this operation
                        # may be removed. A changed path is left for root review.
                        try:
                            actual = temporary.lstat()
                        except FileNotFoundError:
                            pass
                        else:
                            require((actual.st_dev, actual.st_ino) == (created.st_dev, created.st_ino), "Owned source temp was externally replaced")
                            temporary.unlink()
                fsync_directory(path.parent)
        self.check(phase)


def resume_all(host):
    """Emergency undo has no global health, source, logging or journal gate."""
    failures, attempted, unresolved = [], [], []
    for actor in list(host.paused):
        attempted.append(actor["pid"])
        try:
            host.signal_actor(actor, signal.SIGCONT)
        except BaseException as error:
            failures.append(dict(pid=actor["pid"], error=repr(error)))
            unresolved.append(actor)
    # A failed SIGCONT may still describe a stopped owned task. Preserve it
    # across a later partial re-pause so final undo cannot lose that suffix.
    host.paused = unresolved
    return dict(attempted=attempted, failures=failures, all_matching_actors_resumed=not failures)


def binding_matches(current, initial, expected_sources, environment):
    require(current["unit_files"] == initial["unit_files"], "Unrelated unit configuration changed")
    require(current["fleet"]["MainPID"] == initial["fleet"]["MainPID"] and
        current["supervisor_start_ticks"] == initial["supervisor_start_ticks"], "Fleet supervisor changed")
    require(current["trainer_stdout"] == initial["trainer_stdout"], "Trainer stdout inode/path changed")
    for key in ("actors", "fleet_cgroup", "control_hashes", "logs"):
        require(current["bindings"][key] == initial["bindings"][key], "Ownership/control changed: " + key)
    require(current["bindings"]["source_hashes"] == expected_sources, "Unexpected source change")
    require(current["environment"] == environment, "Unexpected selected recipe/environment change")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_job(args):
    require(args.job and args.expected_job_sha256 and args.expected_controller_sha256, "Explicit root job/source hashes required")
    require(fingerprint(Path(__file__).resolve(), MAX_SOURCE)["sha256"] == args.expected_controller_sha256, "Controller source differs")
    record = fingerprint(args.job, MAX_JSON)
    require(record["sha256"] == args.expected_job_sha256, "Root job SHA differs")
    job = json.loads(Path(args.job).read_text())
    require(fingerprint(args.job, MAX_JSON) == record and job.get("schema") == SCHEMA, "Job changed/schema differs")
    game = canonical(job["game_root"])
    require(canonical(job["model_dir"]) == game / "models_dqn", "Unexpected model directory")
    output = canonical(job["output_directory"], False)
    capture = canonical(job["capture_directory"], False)
    require(not output.exists() and output.parent.is_dir() and output.is_relative_to(game / "logs"), "Output must be new under game logs")
    require(not capture.exists() and capture.parent == output and capture.name.startswith("ce-recomputed-capture-"), "Capture child must be NEW under output")
    require(len(job["sources"]) == 5 and {Path(x["destination"]).name for x in job["sources"]} == set(NAMES), "Exactly five capture overlays required")
    for entry in job["sources"]:
        require(entry["destination"] == str(game / "Scripts/dqn" / Path(entry["destination"]).name), "Unexpected overlay destination")
        require((entry["before"] is None) == (Path(entry["destination"]).name == "recomputed_ce_capture.py"), "Only observer may be new")
        if entry["before"]:
            require(entry["before"]["path"] == entry["destination"], "Before pin must bind destination")
        pin(entry["after"], MAX_SOURCE)
    require(job["readiness_timeout_s"] == 600 and job["capture_timeout_s"] == 600 and job["verifier"]["timeout_s"] == 120,
        "Fixed bounded maintenance deadlines differ")
    require(FLAG not in job["before"]["environment"] and OLD_FLAG not in job["before"]["environment"], "Existing observer session is forbidden")
    require(job["before"]["environment"].get("DQN_RATCHET") == "0"
        and job["before"]["environment"].get("ROBOTRON_DQN_MODEL_DIR") == job["model_dir"]
        and job["before"]["environment"].get("DQN_EXACT_GRAPH_CHECKPOINT") == str(Path(job["model_dir"]) / "robotron_dqn_latest.pt"),
        "Held boot must use latest path with ratchet disabled and matching exact-graph checkpoint")
    require(job["original_dropin"]["content_base64"] is None and job["original_dropin"]["mode"] is None,
        "New dedicated maintenance override must initially be absent")
    require(set(map(int, job["actor_masks"])) == {x["pid"] for x in job["before"]["bindings"]["actors"]}, "Actor mask manifest differs")
    require(all(mask == list(range(72)) for mask in job["actor_masks"].values()) and job["worker_mask"] == list(range(72)), "Held original72CPU masks required")
    require(len(job["before"]["bindings"]["actors"]) == 192, "Exact192 original actors required")
    for value in job["helper_pins"].values():
        pin(value, MAX_SOURCE)
    require(job["helper_pins"]["controller"]["path"] == str(Path(__file__).resolve()) and
        job["helper_pins"]["controller"]["sha256"] == args.expected_controller_sha256, "Controller helper pin differs")
    for value in job["static_pins"]:
        pin(value, MAX_SOURCE)
    pin(job["verifier"]["script"], MAX_SOURCE)
    require(canonical(job["verifier"]["python"]).name.startswith("python"), "Explicit verifier Python required")
    return job, record


class Runtime:
    """Thin adapter over LiveHost; no old trial verify/ready/main is used."""
    def __init__(self, job, output):
        self.job, self.output = job, output
        tools = Path(job["helper_pins"]["live_host"]["path"]).parent
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(tools))
        self.primitives = load_module(job["helper_pins"]["live_host"]["path"], "live8_owned_primitives")
        self.metrics = self.primitives.metrics
        for key, module in (("metrics", self.metrics), ("identity", self.metrics.identity), ("protection", self.primitives.protection)):
            require(Path(module.__file__).resolve() == Path(job["helper_pins"][key]["path"]), "Unexpected imported helper: " + key)
        self.banks = load_module(job["helper_pins"]["bank_state"]["path"], "live8_bank_state")
        owner = self
        class Host(self.primitives.LiveHost):
            def runtime_dropin(self):
                return Path("/run/user") / str(os.getuid()) / "systemd/user" / (self.trainer_unit + ".d") / "90-recomputed-ce-live8.conf"
            def no_sidecars(self):
                super().no_sidecars()
                owner.exclusive()
        self.host = Host(job["trainer_unit"], job["fleet_unit"])
        self.phase = "before"
        self.lineages = {}
        self.insurance = read_json(job["insurance_verification"])
        self.insured = self.insurance["root_job"]["insurance"]["trainer"]
        self.floor = {key: self.insurance["clocks"][key] for key in CLOCKS}
        require(self.insurance["status"] == "PASS" and self.insurance["mode"] == "insurance"
            and self.insurance["root_job"]["experiment"] == job["experiment"]
            and self.insurance["root_job"]["source_control_context"]["model_dir"] == job["model_dir"], "Insurance proof does not bind branch/model directory")
        saved = read_json(job["insurance_receipt"])
        require(saved["tag"] == self.insurance["root_job"]["insurance"]["tag"] and
            saved["source"]["sha256"] == self.insurance["root_job"]["source"]["sha256"], "Wrong completed insurance request consumed")
        self.current_checkpoint = None
        self.last_retired = None
        self.verification_failed = False
        self.lease_fd = None
        self.original_dropin = base64.b64decode(job["original_dropin"]["content_base64"]) if job["original_dropin"]["content_base64"] is not None else None
        self.dropin = ("[Service]\nRestart=no\nEnvironment=\"%s=%s\"\nUnsetEnvironment=%s\n" %
            (FLAG, job["capture_directory"], OLD_FLAG)).encode()
        self.recovery_dropin = ("[Service]\nRestart=no\nUnsetEnvironment=%s %s\n" % (FLAG, OLD_FLAG)).encode()
        require("\n" not in job["capture_directory"] and '"' not in job["capture_directory"] and "%" not in job["capture_directory"], "Unsafe systemd capture path")
        require(str(self.host.runtime_dropin()) == job["original_dropin"]["path"], "Wrong owned override path")
        require(self.host._dropin_bytes() == self.original_dropin, "Original maintenance override differs")
        self.host.dropin_expected = self.original_dropin

    def exclusive(self):
        for entry in Path("/proc").iterdir():
            if not entry.name.isdecimal() or int(entry.name) == os.getpid():
                continue
            try:
                raw = (entry / "cmdline").read_bytes()
            except OSError as error:
                if error.errno in (errno.ENOENT, errno.ESRCH):
                    continue  # ONLY unclassified initial cmdline churn.
                raise
            argv = raw.split(b"\0")
            matches = [os.path.basename(os.fsdecode(arg)) for arg in argv if arg and os.path.basename(os.fsdecode(arg)) in BLOCKED]
            require(not matches, "Competing helper/carrier PID %s: %s" % (entry.name, matches))
        require(not Path(self.job["model_dir"], "managed_save.request.json").exists(), "A managed save request is pending")
        require(not any(path.is_dir() for path in Path("/dev/shm").glob("robotron-snapshot-smoke-*")), "Private diagnostic tmpfs still exists")
        app = Path("/sys/fs/cgroup") / self.job["before"]["trainer"]["ControlGroup"].lstrip("/")
        for group in app.parent.glob("robotron-snapshot-smoke-*"):
            members = list(group.rglob("cgroup.procs"))
            require(len(members) <= 256 and all(not member.read_text().split() for member in members), "Private diagnostic cgroup is nonempty")

    def static(self):
        self.exclusive()
        for value in self.job["helper_pins"].values():
            pin(value, MAX_SOURCE)
        for value in self.job["static_pins"]:
            pin(value, MAX_SOURCE)
        pin(self.job["verifier"]["script"], MAX_SOURCE)
        pin(self.job["insurance_verification"], MAX_JSON)
        pin(self.job["insurance_receipt"], MAX_JSON)

    def trainer_id(self):
        known = self.host.known_trainer
        require(known is not None, "No explicitly owned trainer")
        unit = self.host.unit(self.job["trainer_unit"])
        require(unit["MainPID"] == str(known["pid"]) and unit["ControlGroup"] == known["cgroup"], "Unknown replacement trainer")
        require(self.metrics.identity.identify_process(known["pid"], "trainer") == known["identity"], "Owned PID identity changed")
        invocation = subprocess.run(["systemctl", "--user", "show", self.job["trainer_unit"], "--value", "-p", "InvocationID"],
            capture_output=True, text=True, check=True, timeout=5).stdout.strip()
        require(re.fullmatch("[0-9a-f]{32}", invocation), "Missing actual trainer invocation")
        return dict(pid=known["pid"], starttime_ticks=known["identity"]["starttime_ticks"],
            unit=self.job["trainer_unit"], invocation_id=invocation, cgroup=known["cgroup"])

    def expected_sources(self, phase):
        expected = dict(self.job["before"]["bindings"]["source_hashes"])
        if phase == "after":
            for entry in self.job["sources"]:
                expected[entry["destination"]] = entry["after"]["sha256"]
        return expected

    def inspect(self, phase):
        self.static()
        current = self.host.describe()  # describe rejects replacement before reader/ownership adoption.
        environment = dict(self.job["before"]["environment"])
        if phase == "after":
            environment.pop(OLD_FLAG, None); environment[FLAG] = self.job["capture_directory"]
        binding_matches(current, self.job["before"], self.expected_sources(phase), environment)
        require(current["trainer"]["Restart"] == ("no" if self.host.dropin_expected is not None else self.job["before"]["trainer"]["Restart"]), "Unexpected effective restart policy")
        require(self.host._dropin_bytes() == self.host.dropin_expected, "Owned override changed externally")
        for actor in current["bindings"]["actors"]:
            require(sorted(os.sched_getaffinity(actor["pid"])) == self.job["actor_masks"][str(actor["pid"])], "Actor affinity drift")
        require(self.host.metric_host.mask(current["bindings"]["worker"]) == self.job["worker_mask"], "Inference affinity drift")
        return current

    def initial(self):
        self.static()
        require(shutil.disk_usage(self.output).free >= 8 << 30, "Need8GiB free for capture6GiB plus independent checkpoint copies")
        current = self.host.describe()
        require(current == self.job["before"], "Initial current runtime differs from pinned root job")
        self.host.adopt_initial(current)
        require(self.trainer_id() == self.insured, "Insurance owner differs from current trainer")
        # Hold the existing reviewed private diagnostic lease throughout this
        # exclusive maintenance. Never create/chmod the historical lease file.
        lease = Path("/dev/shm/robotron-snapshot-smoke-gpu0.lock")
        before = lease.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid(), "Diagnostic lease identity invalid")
        self.lease_fd = os.open(lease, os.O_RDONLY | os.O_NOFOLLOW)
        require(identity(os.fstat(self.lease_fd)) == identity(before), "Diagnostic lease open race")
        fcntl.flock(self.lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.host.metric_host.configure_logs(current["bindings"]["logs"])
        snapshot = self.host.capture()
        local = dict(batch_size=4096, replay_cap=8, initial_snapshot=dict(csv=self.job["baseline_csv"]),
            exposure_identity={kind:self.metrics.exposure_key(snapshot["exposure"][kind]) for kind in ("optimizer", "replay")})
        require(all(value["process_id"] == self.insured["pid"] for value in local["exposure_identity"].values())
            and not self.metrics.api_issues(snapshot, local)
            and all(snapshot[key] >= self.floor[key] for key in CLOCKS), "Initial actualAPI/recipe/clock guards failed")
        self.initial_api = snapshot
        return self.inspect("before")

    def close(self):
        if self.lease_fd is not None:
            os.close(self.lease_fd)
            self.lease_fd = None

    def absence(self):
        self.host.assert_retired_absent()
        unit = self.host.unit(self.job["trainer_unit"])
        require(unit["MainPID"] == "0" and unit["ActiveState"] == "inactive", "Trainer unit is not fully inactive")
        group = Path("/sys/fs/cgroup") / self.host.trainer_cgroup.lstrip("/") / "cgroup.procs"
        require(not group.exists() or not group.read_text().split(), "Owned cgroup still has a process; no source write/start")
        return unit

    def stopped_checkpoint(self, retired, label):
        self.static(); self.absence()
        root = self.output / label
        root.mkdir(mode=0o700)
        latest = Path(self.job["model_dir"]) / "robotron_dqn_latest.pt"
        source, copied = exclusive_copy(latest, root / "latest-readonly-copy.pt")
        absence = publish(root / "absence.json", dict(schema="robotron-live8-owned-trainer-absence-v1", trainer=retired,
            unit_main_pid=0, unit_active_state="inactive", old_process_absent=True, owned_cgroup_empty=True, latest_path=str(latest)))
        spec = dict(old_trainer=retired, absence_receipt=absence, insurance_verification=self.job["insurance_verification"])
        if retired != self.insured:
            require(retired["pid"] in self.lineages, "Retired trainer lacks own requested-start lineage")
            spec["owned_restart_lineage"] = self.lineages[retired["pid"]]
        cpu_job = dict(schema="robotron-live8-maintenance-checkpoint-CPU-job-v1", mode="stopped_latest",
            verifier_sha256=self.job["verifier"]["script"]["sha256"], experiment=self.job["experiment"], source=source,
            verification_copy=copied, clock_floor=self.floor, source_control_context=self.job["verifier"]["context"],
            output_directory=str(root / "cpu-output"), stopped_latest=spec)
        job_pin = publish(root / "cpu-job.json", cpu_job)
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
            OPENBLAS_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2")
        for key in ("LD_PRELOAD", "PYTHONPATH"):
            env.pop(key, None)
        argv = [self.job["verifier"]["python"], "-Xgil=0", "-I", "-B", self.job["verifier"]["script"]["path"],
            "--execute", "--job", job_pin["path"], "--expected-job-sha256", job_pin["sha256"],
            "--expected-verifier-sha256", self.job["verifier"]["script"]["sha256"]]
        try:
            with (root / "cpu.stdout").open("xb") as stdout, (root / "cpu.stderr").open("xb") as stderr:
                completed = subprocess.run(argv, env=env, stdout=stdout, stderr=stderr, timeout=120, check=False)
            publish(root / "cpu-completion.json", dict(argv=argv, exit_code=completed.returncode, CUDA_VISIBLE_DEVICES=""))
            require(completed.returncode == 0, "Stopped latest CPU verification failed; no automatic rollback")
        except BaseException:
            self.verification_failed = True
            raise
        result_pin = fingerprint(root / "cpu-output/cpu-verification.json", MAX_JSON)
        result = read_json(result_pin)
        require(result["status"] == "PASS" and result["mode"] == "stopped_latest" and result["root_job"] == cpu_job
            and result["sha256"] == source["sha256"] and all(result["clocks"][key] >= self.floor[key] for key in CLOCKS), "Stopped latest proof differs")
        self.absence(); require(fingerprint(latest) == source, "Latest changed after CPU proof")
        self.current_checkpoint = dict(source=source, verification=result_pin, clocks=result["clocks"])
        self.last_retired = retired
        return self.current_checkpoint

    def start(self, phase, label):
        self.static(); self.absence()
        require(fingerprint(self.current_checkpoint["source"]["path"]) == self.current_checkpoint["source"], "Newest verified boot latest changed")
        request_id = self.job["experiment"] + "-" + label
        request = publish(self.output / (label + "-start-request.json"), dict(schema="robotron-live8-owned-trainer-start-request-v1",
            insured_trainer=self.insured, unit=self.job["trainer_unit"], cgroup=self.host.trainer_cgroup,
            experiment=self.job["experiment"], model_dir=self.job["model_dir"], source_phase=phase,
            owned_start_requested=True, request_id=request_id))
        self.host.start()
        require(self.host.known_trainer is not None, "Requested trainer failed before an owned PID existed")
        owner = self.trainer_id()
        lineage = publish(self.output / (label + "-owned-lineage.json"), dict(schema="robotron-live8-owned-restart-lineage-v1",
            insured_trainer=self.insured, retired_trainer=owner, authorized_start_adopted=True,
            unknown_replacement_adopted=False, experiment=self.job["experiment"], model_dir=self.job["model_dir"],
            source_phase=phase, request_id=request_id, start_request=request))
        self.lineages[owner["pid"]] = lineage
        self.phase = phase
        return owner

    def raw_api(self):
        with urllib.request.urlopen("http://127.0.0.1:8771/api/now", timeout=3) as response:
            data = response.read(MAX_JSON + 1)
        require(len(data) <= MAX_JSON, "API exceeds bounded observation")
        return json.loads(data)

    def ready(self, phase, banks, *, actors):
        deadline = time.monotonic() + self.job["readiness_timeout_s"]
        while time.monotonic() < deadline:
            self.static()
            owner = self.trainer_id()  # Never adopt a PID seen only by a polling observer.
            try:
                raw = self.raw_api()
            except (OSError, json.JSONDecodeError):
                time.sleep(1); continue
            exposure = raw.get("host_pipeline", {}).get("learning_exposure", {}).get("optimizer", {})
            graphs = raw.get("host_pipeline", {}).get("inference_graphs", {})
            if (exposure.get("process_id") != owner["pid"] or not graphs.get("ready")
                    or exposure.get("total", {}).get("outcomes_recorded", 0) <= 0
                    or actors and raw.get("client_count") != 192):
                time.sleep(1); continue
            current = self.inspect(phase)
            require(all(raw[key] >= self.current_checkpoint["clocks"][key] for key in CLOCKS), "Loaded clocks regressed behind actual stopped latest")
            require(raw.get("managed_experiment") == self.job["experiment"], "Loaded branch label differs")
            transition_events = []
            if actors:
                # Arm the runtime reader BEFORE the final transition scan, so
                # the boundary has overlapping coverage rather than a gap.
                self.host.metric_host.configure_logs(current["bindings"]["logs"])
                transition_events = self.fault_scan()
                row = self.host.capture()
            else:
                row = self.metrics.compact_api(raw)
                row.update(csv=self.job["baseline_csv"], observed_unix_s=time.time(), observed_monotonic_s=time.monotonic(), log_errors=[])
                row["csv_scope"] = "Held pre-stop baseline; actual new CSV is checked after192 reconnect"
            local = dict(batch_size=4096, replay_cap=8, initial_snapshot=dict(csv=self.job["baseline_csv"]),
                exposure_identity={kind:self.metrics.exposure_key(row["exposure"][kind]) for kind in ("optimizer", "replay")})
            require(all(value["process_id"] == owner["pid"] for value in local["exposure_identity"].values()), "Exposure epoch is not owned by the new trainer")
            issues = self.metrics.api_issues(row, local)
            if not actors:
                issues = [issue for issue in issues if issue != "client_count"]
                require(raw["client_count"] == 0, "Paused actors unexpectedly connected before admission")
            require(not issues, "Postload guards: " + repr(issues))
            if not actors:
                proof = self.host.bank_load_proof(current)
                stdout = proof["stdout"]
                with Path(stdout["path"]).open("rb") as stream:
                    info = os.fstat(stream.fileno())
                    require((info.st_dev,info.st_ino) == (stdout["device"],stdout["inode"]), "New stdout inode changed before boot proof")
                    stream.seek(proof["start_byte"])
                    payload = stream.read(proof["end_byte"]-proof["start_byte"])
                require(hashlib.sha256(payload).hexdigest() == proof["sha256"], "Owned boot log increment changed")
                proof["model_boot"] = boot_log_proof(payload, self.current_checkpoint["source"]["path"])
                proof["verified_saved_clocks"] = self.current_checkpoint["clocks"]
                proof["API_loaded_clock_fields"] = {key:raw.get(key) for key in
                    ("loaded_training_steps", "loaded_optimized_samples", "loaded_frame_count", "loaded_learner_frame_count")}
                require(fingerprint(self.current_checkpoint["source"]["path"]) == self.current_checkpoint["source"], "Boot latest changed from CPU-verified bytes")
                if phase == "after":
                    # The source pressure budget permits its first startup
                    # batch at zero new frames. Wait for its create-only sealed
                    # receipt; no retry or actor credit is introduced here.
                    first = Path(self.job["capture_directory"]) / "attempt-01.json"
                    context_path = Path(self.job["capture_directory"]) / "context.json"
                    if not first.exists() or stat.S_IMODE(first.lstat().st_mode) != 0o444:
                        time.sleep(1); continue
                    first_pin = fingerprint(first, MAX_JSON)
                    context = read_json(fingerprint(context_path, MAX_JSON))
                    first_row = read_json(first_pin)
                    proof["first_attempt_loaded_clocks"] = first_attempt_clock_proof(first_row,
                        self.current_checkpoint["clocks"], context["capture_id"])
                    proof["first_attempt_receipt"] = first_pin
                require(proof["counts"] == {name.upper():value["counts"] for name,value in banks["banks"].items()}, "Loaded bank counts differ from selected stopped generations")
                self.banks.assert_unchanged(banks, self.job["bank_spec"])
                maps = self.banks.verify_maps(owner["pid"], banks)
            else:
                proof, maps = None, None
            return dict(binding=current, api=row, bank_load_proof=proof, mapped_ring=maps, transition_events=transition_events)
        raise RuntimeError("Owned trainer readiness exceeded fixed600s")

    def fault_scan(self):
        events = self.host.transition_log_events()
        require(all(event.get("intentional_restart_compatible") is True for event in events), "Unexpected restart/persistence/fallback log event: " + repr(events))
        return events

    def capture_complete(self):
        root = Path(self.job["capture_directory"])
        deadline, previous = time.monotonic() + self.job["capture_timeout_s"], None
        while time.monotonic() < deadline:
            self.inspect("after")
            row = self.host.capture()
            if previous is None:
                local = dict(batch_size=4096, replay_cap=8, initial_snapshot=dict(csv=self.job["baseline_csv"]),
                    exposure_identity={kind:self.metrics.exposure_key(row["exposure"][kind]) for kind in ("optimizer", "replay")})
            require(not self.metrics.api_issues(row, local, previous), "Live capture health guard failed")
            previous = row
            names = set(path.name for path in root.iterdir()) if root.exists() else set()
            allowed = {"context.json", "final.json"} | {"status-%03d.json" % x for x in range(1,129)} | {
                "attempt-%02d%s" % (x,suffix) for x in range(1,9) for suffix in (".entered.json", ".json", ".payload.pt")}
            require(names <= allowed and len(names) <= 154, "Unexpected/ninth capture artifact")
            if root.exists():
                require(root == root.resolve(strict=True) and root.is_dir() and root.stat().st_uid == os.getuid(), "Capture directory changed ownership/path")
                require(all(stat.S_ISREG(path.lstat().st_mode) for path in root.iterdir()), "Unexpected nonregular capture artifact")
                require(sum(path.lstat().st_size for path in root.iterdir()) <= MAX_CAPTURE, "Capture6GiB budget exceeded")
                sealed_status = sorted(path for path in root.glob("status-*.json") if stat.S_IMODE(path.lstat().st_mode) == 0o444)
                if sealed_status:
                    status_row = read_json(fingerprint(sealed_status[-1], MAX_JSON))
                    require(status_row["attempts_consumed"] <= 8 and not status_row["observer_errors"]
                        and status_row["reporting_failed"] is False, "Observer invalidated; no capture retry")
            # Create-only JSON is visible while being written. Mode0444 is set
            # only after the observer has fsynced the completed file/directory.
            if "final.json" in names and stat.S_IMODE((root / "final.json").lstat().st_mode) == 0o444:
                final = read_json(fingerprint(root / "final.json", MAX_JSON))
                context = read_json(fingerprint(root / "context.json", MAX_JSON))
                require(final["status"] == "EIGHT_INPUT_CE_CAPTURES_COMPLETE" and final["complete"] is True
                    and final["attempts_consumed"] == 8 and len(final["rows"]) == 8 and not final["observer_errors"]
                    and final["actual_target_entropy_or_KL_observed"] is False, "Eight-capture result invalid/incomplete")
                require(context["attempts"] == 8 and context["loss_abi"] == 4 and context["optimizer_recipe_change"] is False,
                    "Capture context no longer declares original4/first8")
                rows, capture_id = [], context["capture_id"]
                for index in range(1,9):
                    entry = read_json(fingerprint(root / ("attempt-%02d.json" % index), MAX_JSON))
                    capture_row_checks(entry, index, final["rows"][index-1], capture_id)
                    payload = entry["payload"]
                    require(payload["path"] == str(root / ("attempt-%02d.payload.pt" % index)) and payload["bytes"] <= MAX_PAYLOAD, "Payload path/bound differs")
                    info = Path(payload["path"]).lstat()
                    require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o444 and info.st_size == payload["bytes"], "Capture payload identity/size/mode differs")
                    # The observer fsynced and hashed each payload before release.
                    # Do not reread4GiB during the live capture window.
                    require(re.fullmatch("[0-9a-f]{64}", payload["sha256"]), "Missing producer payload hash")
                    rows.append(entry)
                return dict(final=final, rows=rows, api=row, payload_byte_validation="Producer SHA retained; no parent tensor or4GiB byte reread")
            time.sleep(1)
        raise RuntimeError("Eight consumed attempts did not finish in fixed600s; no retry")


class Maintenance:
    """Control flow is injectable for CPU-only failure tests."""
    def __init__(self, runtime, sources, emit):
        self.r, self.sources, self.emit = runtime, sources, emit
        self.result = dict(schema=RESULT_SCHEMA, status="RUNNING", capture_complete=False,
            manual_recovery_required=False, recovery_errors=[], limitations=[
            "Ordinary save may omit post-save optimizer/FIFO/bank tails; no coherent replay/actor/RNG anchor.",
            "Selected bank generation proof is source-derived disk/header/count evidence, not RAM byte equality.",
            "First8 consumed attempts can precede actor resume; AMP skips retained; no ninth/replacement attempt.",
            "Actual CE only; entropy/KL/targets remain offline conditional recomputations, no learning claim."])
        self.changed = False
        self.recovery_banks = None

    def event(self, phase, **data):
        self.emit(dict(phase=phase, unix_s=time.time(), **data))

    def recover(self):
        r, errors = self.r, self.result["recovery_errors"]
        try:
            require(not r.verification_failed, "A checkpoint CPU verification failed; manual recovery, no retry/rollback")
            # Stop only a previously adopted owned trainer. Unknown replacements
            # fail trainer_id/stop and are never killed/adopted for recovery.
            unit = r.host.unit(r.job["trainer_unit"])
            if unit["MainPID"] != "0":
                retired = r.trainer_id()
                # A fault after the first resume needs a NEW owned pause before
                # stopping. Partial pauses are registered before each syscall.
                for actor in r.job["before"]["bindings"]["actors"]:
                    if actor not in r.host.paused:
                        with r.metrics.block_restore_signals():
                            r.host.paused.append(actor)
                            r.host.signal_actor(actor, signal.SIGSTOP)
                r.host.wait_paused()
                r.host.stop()
            else:
                retired = r.last_retired
                require(retired is not None, "No verified retired owner; manual recovery")
            r.absence()
            if retired != r.last_retired:
                r.stopped_checkpoint(retired, "recovery-stopped")
            else:
                require(r.current_checkpoint is not None and fingerprint(r.current_checkpoint["source"]["path"]) == r.current_checkpoint["source"],
                    "Failed unowned startup changed latest; no automatic adoption/rollback")
            self.sources.reconcile("before", r.absence, r.metrics.block_restore_signals)
            r.host.write_dropin(r.recovery_dropin, r.host.dropin_expected)
            r.phase = "before"
            banks = r.banks.stopped_state(r.job["bank_spec"])
            # Arm a fresh owned stdout boundary for EVERY replacement, including recovery.
            r.host.begin_transition_logs(r.job["before"]["bindings"]["logs"], r.job["before"]["trainer_stdout"])
            r.start("before", "recovery")
            proof = r.ready("before", banks, actors=False)
            events = r.fault_scan()
            self.result["recovery_boot"] = dict(proof=proof, events=events, input="newest CPU-verified stopped latest")
            self.recovery_banks = banks
        except BaseException as error:
            errors.append(dict(error=repr(error), traceback=traceback.format_exc()))
            self.result["manual_recovery_required"] = True

    def run(self):
        r = self.r
        primary = None
        try:
            before = r.initial()
            self.sources.stage()
            self.event("precommit_verified", trainer=r.trainer_id())
            r.host.begin_transition_logs(before["bindings"]["logs"], before["trainer_stdout"])
            # pause registers in memory before SIGSTOP; cleanup remains armed
            # through every later source, journal, signal and readiness failure.
            r.host.pause(dict(initial=r.job["before"]))
            self.changed = True
            retired = r.trainer_id()
            r.host.stop(before)
            self.event("stopped", checkpoint=r.stopped_checkpoint(retired, "initial-stopped"))
            banks = r.banks.stopped_state(r.job["bank_spec"])
            self.event("stopped_disk_state", state=banks)
            self.sources.reconcile("after", r.absence, r.metrics.block_restore_signals)
            r.host.write_dropin(r.dropin, r.host.dropin_expected)
            r.start("after", "capture")
            loaded = r.ready("after", banks, actors=False)
            events = r.fault_scan()
            self.event("loaded_before_resume", proof=loaded, events=events)
            resumed = resume_all(r.host)
            self.result["initial_resume"] = resumed
            require(not resumed["failures"], "Some paused original actors could not be resumed")
            ready = r.ready("after", banks, actors=True)
            self.event("main192_ready", proof=ready, resume=resumed)
            captured = r.capture_complete()
            self.result.update(capture_complete=True, captured=captured)
            # Future starts return to their original operational policy. The
            # current completed observer is dormant; this does not hot-unset env.
            r.host.write_dropin(r.original_dropin, r.host.dropin_expected,
                r.job["original_dropin"].get("mode") or 0o644)
            self.result.update(status="COMPLETE", installed_source_phase="after", future_override_restored=True)
        except BaseException as error:
            primary = error
            self.result.update(status="FAILED", error=repr(error), traceback=traceback.format_exc())
            # A partial pause can occur before pause() returns. Recovery never
            # relies on self.changed to decide whether actors need SIGCONT.
            if self.changed:
                self.recover()
        finally:
            # Keep installed signal handlers and block repeated handled signals
            # until every eligible exact actor has received an undo attempt.
            with r.metrics.block_restore_signals():
                resumed = resume_all(r.host)
            self.result["final_resume"] = resumed
            if resumed["failures"]:
                self.result["manual_recovery_required"] = True
            if self.recovery_banks is not None and not resumed["failures"]:
                try:
                    self.result["recovery192_ready"] = r.ready("before", self.recovery_banks, actors=True)
                    r.host.write_dropin(r.original_dropin, r.host.dropin_expected,
                        r.job["original_dropin"].get("mode") or 0o644)
                    self.result["recovery_future_override_restored"] = True
                except BaseException as error:
                    self.result["recovery_errors"].append(dict(error=repr(error), traceback=traceback.format_exc()))
                    self.result["manual_recovery_required"] = True
            try:
                self.event("terminal", result=self.result)
            except BaseException as error:
                self.result.setdefault("evidence_errors", []).append(repr(error))
                self.result["manual_recovery_required"] = True
        return self.result, primary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--job", type=Path)
    parser.add_argument("--expected-job-sha256")
    parser.add_argument("--expected-controller-sha256")
    args = parser.parse_args(argv)
    if not args.launch:
        print("PLAN_ONLY: new root-bound live8 maintenance; no files/imported helpers/runtime queries/output/actions")
        return 0
    output = None
    runtime = None
    try:
        require(not any(name == "torch" or name.startswith(("torch.", "numpy", "dqn")) for name in sys.modules), "Fresh stdlib-only parent required")
        job, job_record = read_job(args)
        output = Path(job["output_directory"])
        output.mkdir(mode=0o700)
        publish(output / "root-job.json", job)
        backups = output / "sources"
        backups.mkdir(mode=0o700)
        runtime = Runtime(job, output)
        events = [0]
        def emit(value):
            events[0] += 1
            require(events[0] <= 32, "Maintenance event budget exceeded")
            publish(output / ("event-%02d.json" % events[0]), value)
        operation = Maintenance(runtime, Sources(job["sources"], backups), emit)
        with runtime.metrics.interrupt_handlers():
            result, primary = operation.run()
        result.update(root_job=job_record, finished_unix_s=time.time())
        publish(output / "result.json", result)
        print(json.dumps(dict(status=result["status"], manual_recovery_required=result["manual_recovery_required"],
            capture_complete=result["capture_complete"], output=str(output)), indent=2))
        return 0 if result["status"] == "COMPLETE" and not result["manual_recovery_required"] else 1
    except BaseException as error:
        if output is not None:
            try:
                publish(output / "controller-error.json", dict(error=repr(error), traceback=traceback.format_exc()))
            except BaseException:
                pass
        try:
            traceback.print_exc()
        except BaseException:
            pass
        return 1
    finally:
        if runtime is not None:
            runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
