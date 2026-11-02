#!/usr/bin/env python3
"""Prepare a guarded parallel replay A/B/A trial; only --launch mutates runtime.

Requires an already applied/audited default-off proposal, a completed reviewed
256M quality campaign, an immutable recovery checkpoint, and a trainer service
with SendSIGKILL=no. Every phase restarts ONLY that trainer while pausing its
192 owned MAME actors. The fleet service is never restarted. Recovery restores
the original drop-in and serial behavior when ownership permits; failures keep
explicit recovery diagnostics. No winning treatment is promoted.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

try:
    from . import inference_worker_affinity as metrics
    from . import protect_quality_winner as protection
except ImportError:
    import inference_worker_affinity as metrics
    import protect_quality_winner as protection


FLAG = "DQN_PARALLEL_STATE_FILL"
SCHEMA = "robotron-parallel-state-fill-live-trial-v1"
ORDER = (("A", "0"), ("B", "1"), ("Areturn", "0"))
PROPOSAL = metrics.GAME / "tools/parallel_replay_proposal/production-manifest.json"
NUMERICAL_ENV = frozenset(("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "LD_PRELOAD", "LD_LIBRARY_PATH",
    "MALLOC_ARENA_MAX", "GOMP_CPU_AFFINITY", "KMP_AFFINITY", "OMP_PROC_BIND", "OMP_PLACES"))
require = metrics.require


def selected_environment(pid):
    entries = (Path("/proc") / str(pid) / "environ").read_bytes().decode().split("\0")
    return {key: value for item in entries if "=" in item for key, value in [item.split("=", 1)]
            if key.startswith(("DQN_", "ROBOTRON_", "CUDA_", "TORCH", "PYTORCH", "TRITON")) or key in NUMERICAL_ENV}


def environment_without_flag(environment):
    return {key: value for key, value in environment.items() if key != FLAG}


def route_issues(row, flag, previous=None):
    route = row.get("parallel_state_fill")
    if not isinstance(route, dict):
        return ["parallel_route_missing"]
    errors = []
    if (route.get("requested") is not (flag == "1") or route.get("closed") is not False
            or route.get("native_available") is not True):
        errors.append("parallel_route_flags")
    count = route.get("completed_batches")
    if type(count) is not int or count < 0:
        errors.append("parallel_route_counter")
    elif flag == "0" and (count != 0 or route.get("executor_created") is not False):
        errors.append("serial_control_used_parallel_route")
    elif flag == "1" and route.get("executor_created") is not True:
        errors.append("parallel_executor_absent")
    if previous and isinstance(count, int) and count < previous["parallel_state_fill"]["completed_batches"]:
        errors.append("parallel_route_counter_decreased")
    return errors


class LiveHost:
    now = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)

    def __init__(self, trainer_unit, fleet_unit):
        require(re.fullmatch(r"robotron-managed-[A-Za-z0-9_.-]+-trainer\.service", trainer_unit), "Unexpected trainer unit")
        require(fleet_unit == trainer_unit.removesuffix("trainer.service") + "fleet.service", "Trainer/fleet unit names do not match")
        self.trainer_unit, self.fleet_unit = trainer_unit, fleet_unit
        self.metric_host = None
        self.current = None
        self.paused = []
        self.pause_issues = []
        self.dropin_expected = None
        self.transition_logs = None
        self.transition_stdout = None
        self.known_trainer = None
        self.retired_trainers = []
        self.start_requested = False
        self.restart_in_progress = False
        self.trainer_cgroup = None
        self.owned_fleet_cgroup = None

    def no_sidecars(self):
        metrics.Host(0, self.fleet_unit).no_sidecars()

    def unit(self, name):
        keys = ("MainPID", "ActiveState", "SubState", "ControlGroup", "FragmentPath", "DropInPaths",
                "KillSignal", "TimeoutStopUSec", "SendSIGKILL", "Restart", "Requires", "Wants", "BindsTo", "PartOf")
        result = subprocess.run(["systemctl", "--user", "show", name,
                                 *["--property=" + key for key in keys]],
                                capture_output=True, text=True, timeout=5, check=True)
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def command(self, *args):
        self.no_sidecars()
        return subprocess.run(["systemctl", "--user", *args], check=True,
                              capture_output=True, text=True, timeout=10)

    def runtime_dropin(self):
        return Path("/run/user") / str(os.getuid()) / "systemd/user" / (self.trainer_unit + ".d") / "80-parallel-state-fill-trial.conf"

    def dropin_snapshot(self):
        path = self.runtime_dropin()
        require(not path.is_symlink() and path.parent.resolve() == path.parent, "Trial drop-in must not traverse a symlink")
        data = path.read_bytes() if path.exists() else None
        if data is not None:
            require(data == ("[Service]\nEnvironment=" + FLAG + "=0\n").encode(), "Existing trial drop-in is not the serial baseline")
        return dict(path=str(path), content_base64=base64.b64encode(data).decode() if data is not None else None,
                    mode=path.stat().st_mode & 0o777 if data is not None else None)

    def _dropin_bytes(self):
        path = self.runtime_dropin()
        require(not path.is_symlink(), "Trial drop-in became a symlink")
        return path.read_bytes() if path.exists() else None

    def write_dropin(self, data, expected, mode=0o644):
        self.no_sidecars()
        require(self._dropin_bytes() == expected, "Trial drop-in changed outside this runner")
        path = self.runtime_dropin()
        if data is None:
            with metrics.block_restore_signals():
                if path.exists():
                    path.unlink()
                self.dropin_expected = data
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=".parallel-trial-", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data);stream.flush();os.fchmod(stream.fileno(), mode);os.fsync(stream.fileno())
                with metrics.block_restore_signals():
                    os.replace(name, path)
                    self.dropin_expected = data
            finally:
                Path(name).unlink(missing_ok=True)
        if path.parent.exists():
            descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
        self.command("daemon-reload")

    def _inspect(self):
        self.no_sidecars()
        trainer, fleet = self.unit(self.trainer_unit), self.unit(self.fleet_unit)
        require(trainer["ActiveState"] == "active" and int(trainer["MainPID"]) > 0, "Trainer is not active")
        require(trainer["KillSignal"] == "2" and trainer["SendSIGKILL"] == "no"
                and trainer["TimeoutStopUSec"] in ("4min", "240s"), "Trainer must stop via SIGINT/240s without force kill")
        require(fleet["ActiveState"] == "active" and self.trainer_unit in fleet["Wants"].split(), "Fleet must have the soft trainer dependency")
        require(all(self.trainer_unit not in fleet[key].split() for key in ("Requires", "BindsTo", "PartOf")), "Fleet would stop/restart with trainer")
        require(trainer["ControlGroup"].endswith("/" + self.trainer_unit), "Unexpected trainer cgroup")
        mh = metrics.Host(int(trainer["MainPID"]), self.fleet_unit)
        binding = mh.bindings()
        for actor in binding["actors"]:
            if self.actor_stopped(actor):
                require(actor in self.paused,"An actor was already stopped outside this trial")
        proc = Path("/proc") / trainer["MainPID"]
        require(proc.joinpath("cgroup").read_text().strip() == "0::" + trainer["ControlGroup"], "Trainer is outside its service cgroup")
        environment = selected_environment(mh.pid)
        config = {}
        for role, unit in (("trainer", trainer), ("fleet", fleet)):
            files = [unit["FragmentPath"], *shlex.split(unit["DropInPaths"])]
            config[role] = {path: metrics.file_digest(path) for path in files if Path(path) != self.runtime_dropin()}
        supervisor_ticks=metrics.identity.stat_fields((Path("/proc")/fleet["MainPID"]/"stat").read_text())["starttime_ticks"]
        stdout=str((proc/"fd/1").resolve(strict=True))
        require(stdout in binding["logs"],"Trainer stdout is absent from owned log bindings")
        current = dict(trainer=trainer, fleet=fleet, supervisor_start_ticks=supervisor_ticks,
                       bindings=binding, environment=environment, unit_files=config,
                       trainer_stdout=dict(path=stdout,**binding["logs"][stdout]))
        return current,mh

    def describe(self):
        current,new_host = self._inspect()
        if self.known_trainer is not None:
            require(current["bindings"]["worker"]["trainer"]==self.known_trainer["identity"],
                    "Observed an unknown replacement trainer; ownership is not adopted")
            require(current["trainer"]["ControlGroup"]==self.trainer_cgroup,"Trainer service cgroup changed")
        # A guard inspection must never silently disarm the live log offsets.
        # Only a real phase restart receives a fresh metric/log reader.
        if (self.metric_host is None or self.metric_host.pid != new_host.pid
                or self.metric_host.worker != current["bindings"]["worker"]):
            self.metric_host = new_host
        self.current=current
        return copy.deepcopy(current)

    def adopt_initial(self,current):
        require(self.known_trainer is None,"Initial ownership was already established")
        process=current["bindings"]["worker"]["trainer"]
        self.known_trainer=dict(pid=process["pid"],identity=copy.deepcopy(process),cgroup=current["trainer"]["ControlGroup"])
        self.trainer_cgroup=current["trainer"]["ControlGroup"]
        self.owned_fleet_cgroup=current["bindings"]["fleet_cgroup"]

    def verify(self, plan, flag=None):
        current = self.describe()
        require(current["unit_files"] == plan["initial"]["unit_files"], "Unrelated service configuration changed")
        require(current["fleet"]["MainPID"] == plan["initial"]["fleet"]["MainPID"], "Fleet supervisor changed")
        require(current["supervisor_start_ticks"] == plan["initial"]["supervisor_start_ticks"], "Fleet supervisor PID was reused")
        require(current["trainer_stdout"]==plan["initial"]["trainer_stdout"],"Trainer stdout identity changed")
        for key in ("actors", "fleet_cgroup", "source_hashes", "control_hashes", "logs"):
            require(current["bindings"][key] == plan["initial"]["bindings"][key], "Main ownership/source/control changed: " + key)
        require(environment_without_flag(current["environment"]) == environment_without_flag(plan["initial"]["environment"]), "A recipe variable other than the treatment changed")
        if flag is not None:
            require(current["environment"].get(FLAG, "0") == flag, "Trainer flag differs from the phase")
        return current

    def signal_actor(self, actor, signum):
        # Recovery SIGCONT is permitted even if an unexpected evaluator appeared:
        # leaving owned actors stopped would violate the cleanup contract.
        if signum != signal.SIGCONT:
            self.no_sidecars()
        require(metrics.identity.identify_process(actor["pid"], "mame") == actor, "Refusing a signal to a missing/reused actor")
        require((Path("/proc") / str(actor["pid"]) / "cgroup").read_text().strip() == "0::" + self.owned_fleet_cgroup, "Actor left the owned fleet cgroup")
        os.kill(actor["pid"], signum)

    def pause(self, plan):
        for actor in plan["initial"]["bindings"]["actors"]:
            require(actor not in self.paused, "Actor is already registered paused")
            with metrics.block_restore_signals():
                # Register before syscall, including interruptions after a
                # successful kill but before its Python caller returns.
                self.paused.append(actor)
                self.signal_actor(actor, signal.SIGSTOP)
        self.wait_paused()

    def actor_stopped(self,actor):
        require(metrics.identity.identify_process(actor["pid"],"mame")==actor,"Actor identity changed while checking stopped state")
        text=(Path("/proc")/str(actor["pid"])/"stat").read_text()
        return text[text.rfind(")")+2:].split()[0] in ("T","t")

    def wait_paused(self):
        deadline=self.now()+2
        while self.now()<deadline:
            if all(self.actor_stopped(actor) for actor in self.paused):return
            self.sleep(.01)
        raise metrics.GuardFailure("Not every owned actor acknowledged SIGSTOP")

    def resume(self):
        failures = []
        for actor in self.paused:
            try:
                self.signal_actor(actor, signal.SIGCONT)
            except (OSError, ValueError) as error:
                failures.append(dict(pid=actor["pid"], reason=str(error)))
        self.paused = []
        self.pause_issues.extend(failures)
        require(not failures, "Some paused actors were missing/reused; matching actors were resumed: " + repr(failures))

    def stop(self, expected=None):
        self.no_sidecars()
        actual = self.unit(self.trainer_unit)
        require(self.known_trainer is not None or actual["MainPID"] == "0", "Refusing stop of an unknown live startup PID")
        saved = expected["bindings"]["worker"]["trainer"] if expected is not None else (
            self.known_trainer["identity"] if self.known_trainer else None)
        expected_pid = str(saved["pid"]) if saved else "0"
        require(actual["MainPID"] in ("0", expected_pid), "Trainer PID changed before stop")
        if actual["MainPID"] != "0":
            require(actual["ControlGroup"] == self.trainer_cgroup,"Trainer service cgroup changed before stop")
            require(metrics.identity.identify_process(int(actual["MainPID"]), "trainer") == saved, "Trainer identity changed before stop")
            require((Path("/proc")/actual["MainPID"]/"cgroup").read_text().strip() == "0::"+actual["ControlGroup"], "Trainer left its owned cgroup")
        self.restart_in_progress = True
        if saved and saved not in self.retired_trainers:
            self.retired_trainers.append(saved)
        self.command("stop", "--no-block", self.trainer_unit)
        deadline = self.now() + 240
        while self.now() <= deadline:
            unit = self.unit(self.trainer_unit)
            if unit["ActiveState"] == "inactive" and unit["MainPID"] == "0":
                self.assert_retired_absent()
                return
            require(unit["MainPID"] in ("0", expected_pid), "Unexpected trainer replacement during stop")
            self.sleep(.5)
        raise metrics.GuardFailure("Trainer did not finish its 240s graceful stop; no force kill was sent")

    def start(self):
        self.assert_retired_absent()
        require(self.unit(self.trainer_unit)["MainPID"] == "0", "Cannot start over a live trainer")
        with metrics.block_restore_signals():
            self.start_requested = True
            self.known_trainer = None
            self.command("start", "--no-block", self.trainer_unit)
            deadline=self.now()+10
            while self.now()<deadline:
                unit=self.unit(self.trainer_unit)
                if int(unit["MainPID"]):
                    try:process=metrics.identity.identify_process(int(unit["MainPID"]),"trainer")
                    except (OSError,ValueError):
                        self.sleep(.1);continue
                    require((Path("/proc")/unit["MainPID"]/"cgroup").read_text().strip()=="0::"+self.trainer_cgroup,"New trainer left expected cgroup")
                    self.known_trainer=dict(pid=int(unit["MainPID"]),identity=process,cgroup=self.trainer_cgroup)
                    break
                if unit["ActiveState"] in ("failed","inactive"):
                    break
                self.sleep(.1)

    def assert_retired_absent(self):
        for process in self.retired_trainers:
            try:
                actual=metrics.identity.stat_fields((Path("/proc")/str(process["pid"])/"stat").read_text())
            except FileNotFoundError:
                continue
            require(actual["starttime_ticks"] != process["starttime_ticks"],
                    "Old trainer is still alive; refusing another trainer start")
        cgroup=self.unit(self.trainer_unit)["ControlGroup"] or self.trainer_cgroup
        require(cgroup.endswith("/"+self.trainer_unit),"Trainer cgroup changed during absence check")
        members=Path("/sys/fs/cgroup")/cgroup.lstrip("/")/"cgroup.procs"
        if not members.exists():return
        for member in members.read_text().split():
            try:
                argv=(Path("/proc")/member/"cmdline").read_bytes().split(b"\0")
            except FileNotFoundError:
                continue
            require(not any(arg.endswith(b"Scripts/run_dqn.py") for arg in argv),
                    "An unretired trainer is still present in the owned service cgroup")

    def ready(self, plan, flag, *, actors=False):
        deadline = self.now() + 600
        errors = []
        while self.now() < deadline:
            self.no_sidecars()
            unit = self.unit(self.trainer_unit)
            require(unit["ActiveState"] not in ("failed", "inactive"), "Trainer startup failed")
            if int(unit["MainPID"]):
                process = metrics.identity.identify_process(int(unit["MainPID"]), "trainer")
                known = dict(pid=int(unit["MainPID"]),identity=process,cgroup=unit["ControlGroup"])
                require(self.known_trainer is not None or self.start_requested,"Readiness cannot adopt an unrequested trainer")
                require(self.known_trainer is None or known == self.known_trainer, "Trainer changed during startup")
                self.known_trainer = known
            try:
                with urllib.request.urlopen("http://127.0.0.1:8771/api/now", timeout=3) as response:
                    raw = json.load(response)
                pid = int(unit["MainPID"])
                owner = raw["host_pipeline"]["learning_exposure"]["optimizer"]["process_id"]
                if pid and owner == pid and raw["host_pipeline"]["inference_graphs"]["ready"]:
                    current = self.verify(plan, flag)
                    outcomes = raw["host_pipeline"]["learning_exposure"]["optimizer"]["total"]["outcomes_recorded"]
                    route = raw["host_pipeline"].get("parallel_state_fill", {})
                    route_ready = (flag == "0" or route.get("completed_batches",0) > 0)
                    if not actors or raw["client_count"] == 192 and outcomes > 0 and route_ready:
                        if actors:self.restart_in_progress=False
                        return current
            except (OSError, KeyError, ValueError) as error:
                if isinstance(error,metrics.GuardFailure):raise
                errors = [str(error)]
            self.sleep(1)
        raise metrics.GuardFailure("Trainer readiness deadline exceeded: " + repr(errors))

    def capture(self):
        return self.metric_host.capture()

    def serial_running(self,plan):
        unit=self.unit(self.trainer_unit)
        if unit["ActiveState"]!="active" or unit["MainPID"]=="0" or self.known_trainer is None:return False
        require(unit["MainPID"]==str(self.known_trainer["pid"]),"Trainer PID changed before recovery")
        require(metrics.identity.identify_process(int(unit["MainPID"]),"trainer")==self.known_trainer["identity"],"Trainer identity changed before recovery")
        environment=selected_environment(int(unit["MainPID"]))
        return (environment.get(FLAG,"0")=="0" and environment_without_flag(environment)==environment_without_flag(plan["initial"]["environment"]))

    def begin_transition_logs(self, bindings, trainer_stdout=None):
        self.transition_logs = metrics.Host(0,self.fleet_unit)
        self.transition_logs.configure_logs(bindings)
        self.transition_stdout=copy.deepcopy(trainer_stdout)

    def bank_load_proof(self,current):
        """Read the new trainer stdout increment without moving fault offsets."""
        self.no_sidecars()
        stdout=current["trainer_stdout"]
        require(stdout==self.transition_stdout,"Trainer stdout differs from the restart boundary")
        process=current["bindings"]["worker"]["trainer"]
        require(self.known_trainer is not None and process==self.known_trainer["identity"],"Bank proof does not belong to the owned trainer")
        require(metrics.identity.identify_process(process["pid"],"trainer")==process,"Trainer changed before bank proof")
        descriptor=Path('/proc')/str(process['pid'])/'fd/1'
        require(str(descriptor.resolve(strict=True))==stdout['path'],"Trainer stdout fd changed before bank proof")
        saved=self.transition_logs.log_offsets[stdout['path']]
        require((saved['device'],saved['inode'])==(stdout['device'],stdout['inode']),"Trainer stdout binding differs from fault reader")
        with Path(stdout['path']).open('rb') as stream:
            info=os.fstat(stream.fileno())
            require((info.st_dev,info.st_ino)==(stdout['device'],stdout['inode']) and info.st_size>=saved['offset'],"Trainer stdout was replaced/truncated before bank proof")
            length=info.st_size-saved['offset']
            require(length<=4*1024*1024,"Trainer stdout increment exceeds bounded bank-proof read")
            stream.seek(saved['offset']);payload=stream.read(length)
            require(len(payload)==length,"Trainer stdout changed during bank-proof read")
        complete=''.join(line for line in payload.decode(errors='replace').splitlines(keepends=True) if line.endswith('\n'))
        matches=re.findall(r'^\s*(HOF|EPHOF) loaded: ([0-9][0-9,]*) episodes / ([0-9][0-9,]*) transitions\s*$',complete,re.MULTILINE)
        require(len(matches)==2 and sorted(bank for bank,_,_ in matches)==['EPHOF','HOF'],"New trainer stdout lacks exactly one positive HOF/EPHOF startup pair")
        counts={bank:dict(episodes=int(episodes.replace(',','')),transitions=int(transitions.replace(',',''))) for bank,episodes,transitions in matches}
        require(all(value['episodes']>0 and value['transitions']>0 for value in counts.values()),"A startup bank was empty")
        return dict(trainer=copy.deepcopy(process),stdout=copy.deepcopy(stdout),start_byte=saved['offset'],end_byte=saved['offset']+len(payload),
                    sha256=__import__('hashlib').sha256(payload).hexdigest(),counts=counts)

    def transition_log_events(self):
        if self.transition_logs is None:
            return []
        segments={}
        for name,saved in self.transition_logs.log_offsets.items():
            with Path(name).open("rb") as stream:
                stream.seek(saved["offset"]);payload=stream.read(4*1024*1024)
            text=payload.decode(errors="replace")
            exceptions=re.findall(r"^([A-Za-z_]*(?:Error|Exception)): (.*)$",text,re.MULTILINE)
            known=bool(exceptions) and all(
                kind=="TimeoutError" and message=="Batched inference request timed out"
                or kind=="RuntimeError" and message=="Inference batcher stopped before completion"
                for kind,message in exceptions)
            segments[name]=dict(start_byte=saved["offset"],end_byte=saved["offset"]+len(payload),
                sha256=__import__("hashlib").sha256(payload).hexdigest(),known_shutdown_traceback=known)
        events=self.transition_logs.log_errors()
        for event in events:
            event["segment"]=segments[event["path"]]
            marker=event["marker"]
            event["intentional_restart_compatible"]=(marker in ("[SOCKET ACTION TIMEOUT]","Batched inference request timed out")
                or marker=="Traceback" and event["segment"]["known_shutdown_traceback"])
        return events


def prepare(host, directory, quality_directory, recovery_checkpoint, proposal_path=PROPOSAL):
    directory = Path(directory).resolve()
    require(not directory.exists(), "Trial output directory must be new")
    audited = protection.review(quality_directory)
    require(audited["assessment"]["outcome"] in ("not_improved", "qualified_improvement"), "Quality campaign is not finished/audited")
    candidate=audited["checkpoints"]["candidate"]
    expected_candidate=(metrics.GAME/"models_dqn/managed-checkpoints/fresh3-256M.pt").resolve()
    require(Path(candidate["source"]).resolve()==expected_candidate,
            "This trial requires the intended completed 256M quality campaign")
    require(metrics.file_digest(expected_candidate)==candidate["sha256"],
            "The audited 256M candidate source no longer matches its campaign snapshot")
    proposal_path = Path(proposal_path).resolve();proposal = json.loads(proposal_path.read_text())
    patch = proposal_path.with_name("production.patch")
    require(metrics.file_digest(patch) == proposal["patch_sha256"], "Audited proposal patch changed")
    for name, entry in proposal["files"].items():
        require(metrics.file_digest(metrics.GAME.parent / name) == entry["proposed_sha256"], "Audited proposal has not been applied exactly: " + name)
    initial = host.describe()
    require(initial["environment"].get(FLAG, "0") == "0", "Initial trainer must use the serial baseline")
    host.adopt_initial(initial)
    dropin = host.dropin_snapshot()
    recovery_checkpoint = Path(recovery_checkpoint).resolve(strict=True)
    require(recovery_checkpoint.stat().st_size > 0, "Recovery checkpoint is empty")
    return dict(schema=SCHEMA, output_directory=str(directory), created_unix_s=time.time(),
        initial=initial, original_dropin=dropin, quality_review=audited,
        recovery_checkpoint=dict(path=str(recovery_checkpoint), sha256=metrics.file_digest(recovery_checkpoint)),
        proposal=dict(path=str(proposal_path), sha256=metrics.file_digest(proposal_path), patch_sha256=proposal["patch_sha256"]),
        tool_hashes={str(Path(module.__file__).resolve()): metrics.file_digest(module.__file__)
                     for module in (metrics, protection, sys.modules[__name__])},
        phases=[dict(phase=phase, flag=flag) for phase, flag in ORDER], settle_s=90, window_s=300,
        poll_s=1, binding_check_s=30, batch_size=4096, replay_cap=8,
        gates=dict(applied_rate_ratio=1.05, accepted_learner_rate_ratio=1., amp_skip_fraction_allowance=.001, SPF_min=7.6, SPF_max=8.4),
        limitations=["All three phases include the same controlled restart; evolving policy/replay and restart RNG still confound causal attribution.",
            "Environment binding covers DQN/ROBOTRON/CUDA/TORCH/PYTORCH/TRITON variables and explicit numerical/thread/preload settings, not every process variable.",
            "Intentional restart log increments are retained separately before verified192-client readiness; later faults invalidate the phase.",
            "No automatic promotion; recovery restores the original drop-in and serial semantics when ownership permits. An explicit flag0 may remain in Areturn's process environment.",
            "Recovery cannot signal reused PIDs or force-kill a hung trainer; external ownership changes may require manual recovery."])


def original_bytes(plan):
    value = plan["original_dropin"]["content_base64"]
    return base64.b64decode(value) if value is not None else None


def check_static(plan):
    for path, sha in plan["tool_hashes"].items():
        require(metrics.file_digest(path) == sha, "Trial tool changed after precommit")
    recovery = plan["recovery_checkpoint"]
    require(metrics.file_digest(recovery["path"]) == recovery["sha256"], "Protected recovery checkpoint changed")
    require(metrics.file_digest(plan["proposal"]["path"]) == plan["proposal"]["sha256"], "Proposal manifest changed")
    require(protection.review(plan["quality_review"]["campaign_directory"])["evidence_sha256"]
            == plan["quality_review"]["evidence_sha256"], "Completed quality evidence changed")


def restart_phase(host, plan, phase, flag, transition):
    check_static(plan)
    before = host.verify(plan)
    transition.update(state="pausing", before=before)
    host.begin_transition_logs(before["bindings"]["logs"],before["trainer_stdout"])
    host.pause(plan)
    transition["state"] = "stopping"
    host.stop(before)
    transition["state"] = "setting_flag"
    data = ("[Service]\nEnvironment=" + FLAG + "=" + flag + "\n").encode()
    host.write_dropin(data, host.dropin_expected)
    transition["state"] = "starting"
    host.start()
    loaded=host.ready(plan, flag)
    transition['bank_load_proof']=host.bank_load_proof(loaded)
    transition["state"] = "resuming"
    host.resume()
    current = host.ready(plan, flag, actors=True)
    # Log increment counts before this readiness boundary are explicitly
    # transition diagnostics. No phase observations are trimmed afterward.
    transition.update(state="ready", after=current, ready_monotonic_s=host.now(),
                      log_events=host.transition_log_events())
    require(all(event.get("intentional_restart_compatible") is True for event in transition["log_events"]),
            "Unexpected or ambiguous fault during the controlled restart")
    host.metric_host.configure_logs(current["bindings"]["logs"])
    initial = host.capture()
    local = dict(plan, exposure_identity={kind: metrics.exposure_key(initial["exposure"][kind])
                 for kind in ("optimizer", "replay")}, initial_snapshot=initial)
    require(all(value["process_id"] == int(current["trainer"]["MainPID"]) for value in local["exposure_identity"].values()), "Phase exposure belongs to another trainer")
    initial["issues"] = metrics.api_issues(initial, local) + route_issues(initial, flag)
    require(not initial["issues"], "Post-restart phase guards: " + repr(initial["issues"]))
    return local, initial


def decision(results, plan):
    result = metrics.judge(results, plan)
    a, b, ar = results
    required = 1.05 * max(a["logical_samples_per_s"], ar["logical_samples_per_s"])
    result["checks"]["logical_rate"] = b["logical_samples_per_s"] >= required
    result["checks"]["B_parallel_route_advanced"] = b["parallel_completed_delta"] > 0
    result["outcome"] = "qualified" if all(result["checks"].values()) else "rejected"
    result.pop("final_affinity", None)
    result.update(required_logical_samples_per_s=required, final_environment="original serial semantics")
    return result


def recover(host, plan, status):
    """Restore the owned drop-in and baseline service, then resume every safe PID."""
    errors = []
    try:
        if host.serial_running(plan) and not host.restart_in_progress:
            if host.dropin_expected != original_bytes(plan):
                host.write_dropin(original_bytes(plan),host.dropin_expected,mode=plan["original_dropin"]["mode"] or 0o644)
        elif host.dropin_expected != original_bytes(plan) or host.restart_in_progress:
            if not host.paused:
                host.pause(plan)
            host.stop()
            host.write_dropin(original_bytes(plan), host.dropin_expected,
                               mode=plan["original_dropin"]["mode"] or 0o644)
            host.start()
            host.ready(plan, "0")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        errors.append(str(error))
        # Even when a treatment failed to start, restore the owned file before
        # retrying the original service, without killing an unknown process.
        try:
            host.write_dropin(original_bytes(plan), host.dropin_expected,
                               mode=plan["original_dropin"]["mode"] or 0o644)
            unit = host.unit(host.trainer_unit)
            if unit["MainPID"] == "0":
                host.stop()
                host.start();host.ready(plan, "0")
        except (OSError, ValueError, subprocess.SubprocessError) as failure:
            errors.append("baseline recovery: " + str(failure))
    finally:
        try:
            host.resume()
        except (OSError, ValueError) as error:
            errors.append("actor recovery: " + str(error))
    status["recovery"] = dict(errors=errors, paused_actor_identity_issues=host.pause_issues,
                              original_dropin_restored=host.dropin_expected == original_bytes(plan),
                              manual_recovery_required=bool(errors),
                              final_environment=("unverified; manual recovery required" if errors else
                                  "original serial semantics; an explicit treatment flag 0 may remain in the running Areturn process"))


def run(host, plan):
    directory = Path(plan["output_directory"])
    check_static(plan);host.verify(plan)
    directory.mkdir(parents=True, exist_ok=False)
    metrics.write_json(directory / "precommit.json", plan, immutable=True)
    sha = metrics.file_digest(directory / "precommit.json")
    status = dict(schema=SCHEMA, state="running", precommit_sha256=sha, results=[], transitions=[])
    host.dropin_expected = original_bytes(plan)
    with metrics.interrupt_handlers():
        try:
            with (directory / "observations.jsonl").open("x") as stream:
                for phase, flag in ORDER:
                    require(metrics.file_digest(directory / "precommit.json") == sha, "Precommit changed")
                    transition = dict(phase=phase, flag=flag, started_monotonic_s=host.now())
                    status["transitions"].append(transition)
                    local, previous = restart_phase(host, plan, phase, flag, transition)
                    start = transition["ready_monotonic_s"];anchor = None;checked = start;rows = []
                    while True:
                        row = host.capture();row.update(phase=phase, stage="settle")
                        if row["observed_monotonic_s"] - start >= plan["settle_s"]:
                            anchor = row["observed_monotonic_s"] if anchor is None else anchor
                            row["stage"] = "primary"
                        row["issues"] = metrics.api_issues(row, local, previous) + route_issues(row, flag, previous)
                        if host.now()-checked >= plan["binding_check_s"]:
                            try:
                                current = host.verify(plan, flag)
                                require(current["bindings"]["worker"] == transition["after"]["bindings"]["worker"], "Trainer/thread changed within phase")
                            except (OSError, ValueError, subprocess.SubprocessError) as error:
                                row["issues"].append("bindings:"+str(error))
                            checked = host.now()
                        rows.append(row);stream.write(json.dumps(row, allow_nan=False)+"\n");stream.flush()
                        require(not row["issues"], "Phase observation guards: " + repr(row["issues"]))
                        previous = row
                        if anchor is not None and row["observed_monotonic_s"]-anchor >= plan["window_s"]:
                            endpoint=host.verify(plan,flag)
                            require(endpoint["bindings"]["worker"]==transition["after"]["bindings"]["worker"],"Trainer/thread changed at phase endpoint")
                            break
                        host.sleep(plan["poll_s"])
                    result = metrics.summarize_phase(rows, local)
                    result["parallel_completed_delta"] = result["end"]["parallel_state_fill"]["completed_batches"]-result["start"]["parallel_state_fill"]["completed_batches"]
                    status["results"].append(result);metrics.write_json(directory / "status.json", status)
                status.update(state="complete", decision=decision(status["results"], plan))
        except BaseException as error:
            status.update(state="interrupted" if isinstance(error,(metrics.TrialInterrupted,KeyboardInterrupt)) else "failed",
                          error=str(error), decision=dict(outcome="invalid",automatic_promotion=False))
            raise
        finally:
            with metrics.block_restore_signals():
                if status["transitions"] and status["transitions"][-1].get("state") != "ready":
                    try:
                        status["transitions"][-1]["log_events"] = host.transition_log_events()
                    except (OSError,ValueError) as log_error:
                        status["transitions"][-1]["log_read_error"] = str(log_error)
                recover(host, plan, status)
                if status["recovery"]["errors"]:
                    status.update(state="failed", decision=dict(outcome="invalid",automatic_promotion=False))
                metrics.write_json(directory / "status.json", status)
    require(not status["recovery"]["errors"], "Trial needs manual recovery: " + repr(status["recovery"]))
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trainer-unit", required=True)
    parser.add_argument("--fleet-unit", required=True)
    parser.add_argument("--quality-campaign", type=Path, required=True)
    parser.add_argument("--recovery-checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args(argv)
    try:
        host = LiveHost(args.trainer_unit, args.fleet_unit)
        plan = prepare(host,args.output_dir,args.quality_campaign,args.recovery_checkpoint)
        result = run(host,plan) if args.launch else plan
        print(json.dumps(result,indent=2,allow_nan=False))
    except (OSError,ValueError,subprocess.SubprocessError,metrics.TrialInterrupted,KeyboardInterrupt) as error:
        print("Parallel replay trial stopped/refused: " + str(error),file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":raise SystemExit(main())
