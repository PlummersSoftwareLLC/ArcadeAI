#!/usr/bin/env python3
"""Prepare or launch a durable systemd user trainer and supervised MAME fleet.

Default is read-only: print the exact command/environment manifest. --launch
records that manifest in a new run directory before starting either unit.
No checkpoints, replay, controls, services or existing processes are removed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys

try:
    from . import build_socket_wait
except ImportError:  # Direct script execution.
    import build_socket_wait


ROBOTRON = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = Path(__file__).with_name("managed_training_profile.json")
SCHEMA = "robotron-managed-training-launch-v1"


def active_robotron_processes(proc: Path = Path("/proc")) -> list[dict]:
    """Read command identity only; never include arbitrary process environments."""
    found = []
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            argv = entry.joinpath("cmdline").read_bytes().decode(errors="replace").strip("\0").split("\0")
        except (OSError, ProcessLookupError):
            continue
        if not argv or not argv[0]:
            continue
        executable = Path(argv[0]).name
        mame = "mame" in executable.lower() and "robotron" in argv[1:]
        trainer = executable.startswith("python") and any(arg.endswith("Scripts/run_dqn.py") for arg in argv[1:])
        if mame or trainer:
            found.append({"pid": int(entry.name), "kind": "mame" if mame else "trainer", "executable": argv[0]})
    return sorted(found, key=lambda item: item["pid"])


def assert_idle() -> None:
    existing = active_robotron_processes()
    if existing:
        raise ValueError(f"Existing Robotron processes must be handled explicitly first: {existing}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", 9998))
        except OSError as error:
            raise ValueError("Trainer port 9998 is already in use") from error


def required_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Required nonempty file missing: {path}")


def plan(run_dir: Path, profile_path: Path = DEFAULT_PROFILE,
         robotron_dir: Path = ROBOTRON) -> dict:
    robotron_dir = robotron_dir.expanduser().resolve()
    run_dir = run_dir.expanduser().resolve()
    profile_path = profile_path.expanduser().resolve()
    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    if profile.get("schema") != "robotron-managed-training-profile-v1":
        raise ValueError("Unknown managed training profile schema")
    actors = profile["actors"]
    if type(actors) is not int or not 1 <= actors <= 1024:
        raise ValueError("Profile actor count must be in 1..1024")
    checkpoint = robotron_dir / "models_dqn/robotron_dqn_latest.pt"
    trainer = robotron_dir / "starttrainer.sh"
    fleet = robotron_dir / "startmame.sh"
    wrapper = robotron_dir / "tools/mame_with_socket_wait.sh"
    builder = robotron_dir / "tools/build_socket_wait.py"
    readiness = robotron_dir / "Scripts/wait_for_trainer.py"
    python = robotron_dir.parent / ".venv-gb300/bin/python"
    for path in (checkpoint, trainer, fleet, wrapper, builder, readiness, python):
        required_file(path)
    if run_dir.exists() and (not run_dir.is_dir() or any(run_dir.iterdir())):
        raise ValueError("Run directory must be new or empty; existing run logs are never overwritten")
    env = dict(profile["trainer_environment"])
    fleet_env = dict(profile["fleet_environment"])
    for item in (env, fleet_env):
        if any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or not isinstance(value, str)
               or "\0" in value or "\n" in value for key, value in item.items()):
            raise ValueError("Profile environment must contain single-line string values")
    env.update(ROBOTRON_RUN_DIR=str(run_dir), ROBOTRON_PYTHON=str(python),
               DQN_EXACT_GRAPH_CHECKPOINT=str(checkpoint))
    # The cache builder is content-addressed and reuses a complete existing .so.
    # Preparation computes its expected path without compiling or writing files.
    identity = robotron_dir.joinpath("Scripts/robotron_socket_wait.c").read_bytes()
    identity += repr((build_socket_wait.platform.system(), build_socket_wait.platform.machine(),
                      build_socket_wait.FLAGS, build_socket_wait.LIBRARIES)).encode()
    fingerprint = hashlib.sha256(identity).hexdigest()[:24]
    library = build_socket_wait.default_cache_dir() / f"robotron-socketwait-{fingerprint}.so"
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", run_dir.name)[:35] or "run"
    suffix = hashlib.sha256(str(run_dir).encode()).hexdigest()[:8]
    fleet_env.update(MAME_BIN=str(wrapper), ROBOTRON_SOCKET_WAIT_LIBRARY=str(library),
                     ROBOTRON_FLEET_ID=f"managed-{slug}-{suffix}")
    trainer_unit = f"robotron-managed-{slug}-{suffix}-trainer.service"
    fleet_unit = f"robotron-managed-{slug}-{suffix}-fleet.service"

    def command(unit, environment, properties, executable):
        args = ["systemd-run", "--user", f"--unit={unit}",
                f"--property=WorkingDirectory={robotron_dir}", "--property=KillSignal=SIGINT",
                "--property=Restart=on-failure", "--property=RestartSec=15"]
        args += [f"--property={value}" for value in properties]
        args += [f"--setenv={key}={value}" for key, value in sorted(environment.items())]
        return args + executable

    trainer_command = command(trainer_unit, env, ["TimeoutStopSec=240",
        f"StandardOutput=append:{run_dir / 'console.log'}", "StandardError=inherit"], [str(trainer)])
    fleet_command = command(fleet_unit, fleet_env, [f"Wants={trainer_unit}", f"After={trainer_unit}",
        "KillMode=mixed", "TimeoutStopSec=10", "TimeoutStartSec=650",
        f"ExecStartPre=/usr/bin/python3 {readiness}",
        f"StandardOutput=append:{run_dir / 'fleet.log'}", "StandardError=inherit"],
        [str(fleet), str(actors), "novideo", "nonaudio", "--supervise", "--socket-address", "dell:9998"])
    return dict(schema=SCHEMA, utc=datetime.now(timezone.utc).isoformat(), state="prepared",
                run_dir=str(run_dir), profile=str(profile_path),
                profile_sha256=hashlib.sha256(profile_bytes).hexdigest(),
                checkpoint=dict(path=str(checkpoint), bytes=checkpoint.stat().st_size),
                checkpoint_validation="Existence and size only; verify saved tensors separately before launch.",
                trainer_unit=trainer_unit, fleet_unit=fleet_unit,
                trainer_environment=env, fleet_environment=fleet_env,
                trainer_command=trainer_command, fleet_command=fleet_command,
                socket_wait_build_command=["/usr/bin/python3", str(builder)],
                stop_command=["systemctl", "--user", "stop", fleet_unit, trainer_unit])


def launch(manifest: dict) -> None:
    # Initial recovery requires an idle host to avoid overlapping an existing
    # untagged legacy fleet. Later service restarts reconcile only the exported
    # fleet ID, preserving concurrently running frozen sidecars.
    assert_idle()
    directory = Path(manifest["run_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "launch.json"
    with path.open("x") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    try:
        built = subprocess.run(manifest["socket_wait_build_command"], check=True,
                               capture_output=True, text=True, timeout=60).stdout.strip()
        if built != manifest["fleet_environment"]["ROBOTRON_SOCKET_WAIT_LIBRARY"]:
            raise ValueError("Socket wait builder output differs from recorded library")
        subprocess.run(manifest["trainer_command"], check=True, timeout=30)
        subprocess.run(manifest["fleet_command"], check=True, timeout=660)
    except BaseException as error:
        manifest.update(state="launch_failed", error=str(error))
        # Keep the already launched trainer available for explicit inspection;
        # no global process kill or checkpoint rollback occurs on partial failure.
        path.write_text(json.dumps(manifest, indent=2) + "\n")
        raise
    manifest["state"] = "launched"
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = plan(args.run_dir, args.profile)
        assert_idle()
        if args.launch:
            launch(manifest)
        print(json.dumps(manifest, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Managed training launch refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
