"""SOURCE-ONLY / UNEXECUTED: actual private parser+whole client-handler test.

Future explicit CPU execution uses no model instances, real socket, listener,
MAME, live data or replay storage. The parser/handler/journal are never mocked.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[2]
REVISION = HERE.parent / "activation_bound_revision"
REVISION_LOCK = "3ded25b28ce5eef044c7ec3ff411f5c09e44cc4a34f3470884c0c4839d27d58e"
SLOT = 4097
MAX_SOURCE_BYTES = 4 * 1024 * 1024


def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, expected):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), "Not a regular source file: " + str(path))
    raw = path.read_bytes()
    require(len(raw) <= 512 * 1024 and digest(raw) == expected, "Source drift: " + str(path))
    return raw


def prepare_private(work):
    """Bounded source text only; called before creating a numerical child."""
    lock = json.loads((HERE / "source-lock.json").read_text())
    require(lock["new_files_sha256"][Path(__file__).name] == digest(Path(__file__).read_bytes()),
            "Validation script differs from its source lock")
    revision = json.loads(checked(REVISION / "source-lock.json", REVISION_LOCK))
    require(all(digest((REVISION / name).read_bytes()) == expected
                for name, expected in revision["new_files_sha256"].items()), "Sealed revision drift")
    files = {name: checked(GAME / "Scripts/dqn" / name, expected)
             for name, expected in lock["base_package_sha256"].items()}
    require(len(files) <= 64 and sum(map(len, files.values())) <= MAX_SOURCE_BYTES,
            "Private source-copy budget exceeded")
    for name, candidate in (("socket_server.py", "socket_server_candidate.py"),
                            ("game_journal.py", "game_journal_candidate.py")):
        files[name] = checked(REVISION / candidate, revision["new_files_sha256"][candidate])
    # Existing __new__ fixtures do not execute the new constructor latch. Give
    # those TEST OWNED objects the explicit original OFF value, without changing
    # production getattr behavior or any existing assertion/algorithm.
    name = "test_measurement_actor.py"
    old = files[name].decode()
    needle = "server = server_module.SocketServer.__new__(server_module.SocketServer)"
    require(old.count(needle) == 2, "Unexpected existing __new__ fixture layout")
    lines = []
    for line in old.splitlines(keepends=True):
        lines.append(line)
        if line.strip() == needle:
            indentation = line[:len(line)-len(line.lstrip())]
            lines.append(indentation + "server.game_boundary_diagnostics = False\n")
    files[name] = "".join(lines).encode()
    package = work / "private/Scripts/dqn"
    package.mkdir(parents=True)
    for name, raw in files.items():
        (package / name).write_bytes(raw)
    for name in ("models", "journal", "control", "cache", "tmpfs"):
        (work / name).mkdir()
    (work / "models/game_settings.json").write_text("{}\n")
    (work / "control/learning_control.json").write_text("{}\n")
    manifest = dict(schema="robotron-private-boundary-wire-input-v1",
        work=str(work), source_lock_sha256=digest((HERE / "source-lock.json").read_bytes()),
        validation_source_sha256=digest(Path(__file__).read_bytes()),
        revision_source_lock_sha256=REVISION_LOCK,
        private_package_sha256={name: digest(raw) for name, raw in files.items()},
        source_bytes=sum(map(len, files.values())),
        copied_existing_test_fixture_edits="Only explicit diagnosticsFalse on two __new__ test objects")
    (work / "private-input.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def child_environment(work):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("DQN_", "ROBOTRON_")) and key not in ("LD_PRELOAD", "PYTHONPATH")}
    environment.update(CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1",
        ROBOTRON_ALLOW_BOUNDARY_WIRE_TEST="1", ROBOTRON_GAME_BOUNDARY_DIAGNOSTICS="0",
        ROBOTRON_DQN_MODEL_DIR=str(work / "models"),
        ROBOTRON_DQN_CONTROL_PATH=str(work / "control/learning_control.json"),
        ROBOTRON_RUN_DIR=str(work / "journal"), DQN_FRAME_STACK="4",
        DQN_LEARNING_EXPOSURE_COUNTERS="0", DQN_NATIVE_BATCH_UPDATE="0",
        OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2",
        XDG_CACHE_HOME=str(work / "cache"), TORCH_HOME=str(work / "cache/torch"),
        TORCHINDUCTOR_CACHE_DIR=str(work / "cache/inductor"), TRITON_CACHE_DIR=str(work / "cache/triton"),
        TORCH_EXTENSIONS_DIR=str(work / "cache/extensions"), CUDA_CACHE_PATH=str(work / "cache/cuda"))
    return environment


def frame(score, wave, *, alive=True, done=False, start=False, lives=3):
    return dict(score=score, wave=wave, alive=alive, done=done, start=start, lives=lives)


def fixture_frames(case):
    beginning = [frame(9800, 2, start=True), frame(9900, 2)]
    if case == "valid_wave1":
        return beginning + [frame(0, 1, alive=False), frame(0, 1), frame(100, 1),
                            frame(700, 1, alive=False, done=True, lives=0)]
    scoring = [frame(index * 10000 // 17, 2) for index in range(1, 18)]
    if case == "direct_bad_wave2":
        return beginning + [frame(0, 2)] + scoring
    if case == "inactive_then_bad_wave2":
        return beginning + [frame(0, 0, alive=False), frame(0, 2)] + scoring
    raise ValueError(case)


class MemoryWire:
    """Synthetic descriptor-free connection; actual _recv_exact consumes it.

    Only readiness and socket syscalls are adapted. Length framing, incremental
    recv, v2 parser, state slice/stack, handler and all actions remain actual.
    """
    def __init__(self, server, wire):
        self.server, self.wire, self.offset, self.reads = server, wire, 0, 0
        self.actions, self.options, self.final_client = [], [], None
        self.closed = self.shutdown_called = False
    def setblocking(self, value):
        require(value is False, "Handler unexpectedly changed blocking policy")
    def setsockopt(self, *args):
        self.options.append(args)
    def recv(self, count):
        if self.offset == len(self.wire):
            client = self.server.client_states[7]
            self.final_client = {key: copy.deepcopy(client.get(key)) for key in (
                "frames", "game_uid", "game_score", "level_number", "raw_score_prev", "raw_wave_prev",
                "last_game_score", "deaths_this_game", "total_reward", "ep_dqn_reward", "ep_expert_reward")}
            # Intentional end AFTER every synthetic frame/action, not an
            # unexpected actor death or a swallowed handler failure.
            self.server.shutdown_event.set()
            return b""
        chunk = min(count, (1, 3, 17, 4096)[self.reads % 4], len(self.wire)-self.offset)
        self.reads += 1
        result = self.wire[self.offset:self.offset+chunk]
        self.offset += chunk
        return result
    def ready(self, readable, writable, exceptional, timeout):
        require(readable == [self] and not writable and not exceptional, "Unexpected readiness request")
        return [self], [], []
    def sendall(self, payload):
        require(len(payload) == 6, "Actual parser failed to select v2 action framing")
        self.actions.append(bytes(payload))
    def shutdown(self, how):
        self.shutdown_called = True
    def close(self):
        self.closed = True


def run_case(module, config, np, work, case, enabled):
    specs = fixture_frames(case)
    directory = work / "journal" / (case + ("-on" if enabled else "-off"))
    os.environ["ROBOTRON_RUN_DIR"] = str(directory)
    os.environ["ROBOTRON_GAME_BOUNDARY_DIAGNOSTICS"] = "1" if enabled else "0"
    metrics = config.MetricsData()
    config.metrics = module.metrics = metrics
    for key, value in dict(measurement_active=True, measurement_generation=1, measurement_label="wire-fixture",
        frame_count=2000, learner_frame_count=1000, measurement_frame_count=1000,
        total_training_steps=7, total_optimized_samples=3584, training_enabled=False,
        ratchet_frozen=False, preview_capture_enabled=False, hud_enabled=False).items():
        setattr(metrics, key, value)
    class DummyActor:
        optimized_samples, training_steps = 3584, 7
        def __init__(self):
            self.calls = []
            self.memory_accesses = 0
        @property
        def memory(self):
            self.memory_accesses += 1
            raise AssertionError("Inference-only handler touched replay memory")
        def act(self, state, epsilon, locked_fire=None):
            require(state.shape == (config.RL_CONFIG.state_size,) and np.isfinite(state).all(),
                    "Actual parser/state slice/stack produced invalid shape or values")
            require(epsilon == 0.0, "Frozen action stopped being greedy")
            self.calls.append(dict(epsilon=epsilon, locked_fire=locked_fire,
                                   state_sha256=digest(state.tobytes()), state_shape=list(state.shape)))
            return 8, 8, False
        def step(self, *args, **kwargs):
            raise AssertionError("Measurement attempted an actual replay step")
    actor = DummyActor()
    server = module.SocketServer("private-memory-wire", 0, actor, replay_enabled=False)
    require(server.game_boundary_diagnostics is enabled, "Constructor activation mismatch")
    require(server.server_socket is None and server.async_buffer is None and server.inference_batcher is None,
            "Unexpected listener/replay/batcher construction")
    require(server.game_journal.directory == directory, "Journal escaped its private case")
    server.running = True
    server._init_client(7)
    header = struct.pack(">H", (1 << 14) | (SLOT << 1))
    state = np.zeros(module.WIRE_PARAMS_COUNT, dtype=">f4").tobytes()
    wire = bytearray(header)
    for spec in specs:
        payload = struct.pack(module._HDR_FMT_V2, module.WIRE_PARAMS_COUNT, 0.0, 0.0,
            int(spec["done"]), spec["score"], int(spec["alive"]), 0, int(spec["start"]),
            0, 0, spec["wave"], spec["lives"]) + state
        wire.extend(struct.pack(">I", len(payload)) + payload)
    connection = MemoryWire(server, bytes(wire))
    no_timer = type("NoTimer", (), {"start": lambda self: None})()
    with patch.object(module.select, "select", side_effect=connection.ready), \
            patch.object(module.threading, "Timer", return_value=no_timer) as timer, \
            patch.object(module.socket, "socket", side_effect=AssertionError("No real socket/listener allowed")):
        server.handle_client(connection, 7)
    require(server.inference_only_error is None, "Actual client handler failed: " + str(server.inference_only_error))
    require(connection.offset == len(wire) and connection.closed and connection.shutdown_called,
            "Whole wire/handler cleanup did not complete")
    require(len(connection.actions) == len(specs), "Not exactly one action per complete wire frame")
    require(not server.client_states and server.clients.get(7) is None, "Client cleanup incomplete")
    require(actor.memory_accesses == 0, "Replay memory was accessed")
    require(len(actor.calls) == sum(row["alive"] and not row["done"] for row in specs), "Wrong actual action count")
    require(timer.call_count == 1, "Unexpected cleanup timer lifecycle")
    require(metrics.frame_count == 2000+len(specs) and metrics.measurement_frame_count == 1000+len(specs),
            "Actual accepted-frame accounting changed")
    require(metrics.learner_frame_count == 1000 and metrics.total_training_steps == 7
            and metrics.total_optimized_samples == 3584, "Frozen measurement advanced learner clocks")
    streams = {}
    for name in ("games.jsonl", "lives.jsonl", "measurement_starts.jsonl"):
        path = directory / name
        raw = path.read_bytes() if path.exists() else b""
        streams[name] = dict(sha256=digest(raw), bytes=len(raw),
                             rows=[json.loads(line) for line in raw.splitlines()])
    admission = streams["measurement_starts.jsonl"]["rows"]
    require(len(admission) == 1 and admission[0]["client_slot"] == SLOT, "Unexpected actual admission set")
    begin = admission[0]["start_unix_s"]
    cohort = server.game_journal.cohort_status("wire-fixture", begin, begin)
    require(cohort["closed"] and cohort["started"] == 1, "Original toy cohort did not close")
    actions = [list(struct.unpack(">bbBBBB", action)) for action in connection.actions]
    require(all(row[:2] == [-1, -1] and row[3:] == [0, 1, 0x85] for row in actions),
            "Actual eval action/start/difficulty protocol changed")
    result = dict(case=case, diagnostics=enabled, input_frames=specs, wire_bytes=len(wire),
        wire_sha256=digest(wire), recv_calls=connection.reads, actions=actions, actor_calls=actor.calls,
        final_client=connection.final_client, unwrap_stash={key: value for key, value in server._unwrap_stash[7].items() if key != "t"},
        metrics=dict(frame_count=metrics.frame_count, measurement_frame_count=metrics.measurement_frame_count,
                     learner_frame_count=metrics.learner_frame_count, training_steps=metrics.total_training_steps,
                     optimized_samples=metrics.total_optimized_samples, total_controls=metrics.total_controls),
        journal=streams, cohort=cohort, inference_only_error=server.inference_only_error,
        no_replay_or_listener=True, intentional_cleanup=True)
    return result


def normalized(result):
    identifiers = {row["journal_game_id"]: "game-" + str(row["game_uid"])
                   for stream in result["journal"].values() for row in stream["rows"]}
    removed = {"diagnostics", "game_boundary_diagnostics", "first_play_not_wave_1_inputs", "sha256", "bytes",
               "start_utc", "start_unix_s", "end_utc", "end_unix_s", "duration_s", "utc", "start_ts", "close_ts"}
    def walk(value):
        if isinstance(value, dict):
            return {identifiers.get(key, key): walk(item) for key, item in value.items() if key not in removed}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            return identifiers.get(value, value)
        return value
    return walk(result)


def child(work):
    require(os.environ.get("ROBOTRON_ALLOW_BOUNDARY_WIRE_TEST") == "1"
            and os.environ.get("CUDA_VISIBLE_DEVICES") == "", "Explicit isolated CPU permission required")
    require(not any(name in sys.modules for name in ("numpy", "torch", "dqn", "config")), "Child is not fresh")
    work = work.resolve(strict=True)
    manifest = json.loads((work / "private-input.json").read_text())
    require(manifest["work"] == str(work) and digest(Path(__file__).read_bytes()) == manifest["validation_source_sha256"],
            "Private manifest/script mismatch")
    package = work / "private/Scripts/dqn"
    require(all(digest((package / name).read_bytes()) == expected
                for name, expected in manifest["private_package_sha256"].items()), "Private source drift before imports")
    for key, path in (("ROBOTRON_DQN_MODEL_DIR", work / "models"),
                      ("ROBOTRON_DQN_CONTROL_PATH", work / "control/learning_control.json"),
                      ("ROBOTRON_RUN_DIR", work / "journal")):
        require(os.environ[key] == str(path), "Private environment path mismatch: " + key)
    sys.path.insert(0, str(package.parent))
    import numpy as np
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    require(torch.cuda.device_count() == 0 and not torch.cuda.is_initialized(), "CUDA exposed or initialized")
    from dqn import config
    require(Path(config.MODEL_DIR) == work / "models"
            and Path(config.SETTINGS_PATH) == work / "models/game_settings.json"
            and config.learning_control.path == work / "control/learning_control.json", "Import-time paths escaped")
    config.RL_CONFIG.replay_tmpfs_dir = str(work / "tmpfs")
    config.RL_CONFIG.inference_batching_enabled = False
    for key, value in dict(start_advanced=False, start_level_min=1, epsilon_pct=0,
                           expert_pct=0, auto_curriculum=False, difficulty=5).items():
        setattr(config.game_settings, key, value)
    from dqn import socket_server as module
    initial_threads = {thread.ident for thread in threading.enumerate()}
    results = []
    with patch.object(subprocess, "Popen", side_effect=AssertionError("Child may not launch any process")):
        for case in ("valid_wave1", "direct_bad_wave2", "inactive_then_bad_wave2"):
            off, on = [run_case(module, config, np, work, case, enabled) for enabled in (False, True)]
            require(normalized(off) == normalized(on), "OFF/ON actions, IDs, scoring, admissions or cohort differ: " + case)
            require(on["final_client"]["game_uid"] == 2, "Unexpected actual game UID transition")
            if case == "valid_wave1":
                require(on["cohort"]["complete"] and on["cohort"]["count"] == 1
                        and on["cohort"]["rows"][0]["score"] == 700, "Valid wave1 game failed unchanged rules")
            else:
                require(not on["cohort"]["valid"] and on["cohort"]["abandoned"] == 1
                        and on["cohort"]["count"] == 0
                        and set(on["cohort"]["abandonment_reasons"].values()) == {"measurement_start_not_wave_1"},
                        "Bad first-play game was repaired or silently admitted")
                require(on["final_client"]["game_score"] == 10000, "Synthetic17-frame score trace changed")
            start = on["journal"]["measurement_starts.jsonl"]["rows"][0]["context"]["game_boundary_diagnostics"]
            require(start["previous_accepted_wire"]["raw_score"] == 9900
                    and start["current_wire"]["raw_score"] == 0 and start["classifier_new_game"]
                    and start["recent_start"], "Actual reset input evidence missing")
            if case == "inactive_then_bad_wave2":
                records = on["journal"]["games.jsonl"]["rows"]
                evidence = records[-1]["start_context"]["first_play_not_wave_1_inputs"]
                require(evidence["previous_accepted_wire"]["raw_wave"] == 0
                        and not evidence["previous_accepted_wire"]["player_alive"]
                        and evidence["current_wire"]["raw_wave"] == 2
                        and evidence["current_wire"]["player_alive"] and not evidence["classifier_new_game"],
                        "Later rejecting first-play input evidence missing")
            results.extend([off, on])
        # Reuse actual copied measurement entry/exit/FIFO regressions. Only two
        # explicit OFF fixture assignments were added before importing this file.
        regression = importlib.import_module("dqn.test_measurement_actor")
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(regression.MeasurementActorTests)
        log = io.StringIO()
        status = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        require(status.wasSuccessful() and status.testsRun == 7, "Existing private measurement/FIFO regressions failed:\n" + log.getvalue())
    require({thread.ident for thread in threading.enumerate()} == initial_threads, "Python worker thread leaked")
    loaded = {}
    for name, module in list(sys.modules.items()):
        if name == "dqn" or name.startswith("dqn.") or name == "v3" or name.startswith("v3."):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(package), "Module escaped private source tree: " + name)
            loaded[name] = dict(path=str(path.relative_to(work)), sha256=digest(path.read_bytes()))
    require(not any("dqn." + name in sys.modules for name in ("agent", "training", "replay_buffer", "prefetch", "metrics_dashboard")),
            "Forbidden agent/learner/replay/dashboard module imported")
    require(torch.cuda.device_count() == 0 and not torch.cuda.is_initialized(), "CUDA initialized during CPU wire test")
    require(all(digest((package / name).read_bytes()) == expected
                for name, expected in manifest["private_package_sha256"].items()), "Private source drift after tests")
    report = dict(status="PASS", actual_full_handler=True, actual_v2_parser=True, actual_journal=True,
        actual_model_or_checkpoint_or_replay_storage=False, actual_socket_listener=False,
        real_network_inference=False, cuda_devices=0, cuda_initialized=False,
        private_source_manifest=manifest, loaded_modules=loaded, cases=results,
        existing_private_measurement_regressions=dict(count=status.testsRun, log=log.getvalue()),
        limits="Synthetic memory transport/readiness and dummy inference; no MAME, controller campaign, real socket or16actor quality qualification")
    (work / "result.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


class WholeWireIntegrationTests(unittest.TestCase):
    def test_actual_whole_handler_off_on_and_existing_private_measurement_regressions(self):
        require(os.environ.get("ROBOTRON_ALLOW_BOUNDARY_WIRE_TEST") == "1"
                and os.environ.get("CUDA_VISIBLE_DEVICES") == "", "Explicit CPU execution authorization required")
        require("torch" not in sys.modules and "numpy" not in sys.modules, "Fresh stdlib parent required")
        with tempfile.TemporaryDirectory(prefix="robotron-boundary-wire-") as temporary:
            work = Path(temporary).resolve()
            prepare_private(work)
            argv = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--child", str(work)]
            process = subprocess.Popen(argv, env=child_environment(work), stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=15)
                self.fail("Owned private child timeout; reaped exit%s\n%s\n%s" % (process.returncode, stdout, stderr))
            self.assertEqual(process.returncode, 0, "Owned child failed:\n" + stdout + "\n" + stderr)
            report = json.loads((work / "result.json").read_text())
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(len(report["cases"]), 6)
            # Preserve all original private row dictionaries, hashes, inputs,
            # actions, module provenance and child output in captured unit logs.
            print(json.dumps(dict(child_argv=argv, actual_child_exit=process.returncode,
                                  child_stdout=stdout, child_stderr=stderr, report=report), allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child is None:
        print(json.dumps(dict(status="SOURCE_ONLY_PLAN", tests_executed=0,
            requires="Explicit future bounded CUDA-hidden unittest execution", source_lock=str(HERE / "source-lock.json"))))
        return 0
    child(args.child)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
