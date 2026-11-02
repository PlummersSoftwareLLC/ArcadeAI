"""Plan-only by default; private CPU sampler fixtures require explicit execution.

Authoring this file does not authorize its execution during a frozen campaign.
No trainer/agent/model, checkpoint, persisted replay, actor or service is used.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import unittest


HERE = Path(__file__).parent
REPO = HERE.parents[2]
PINS = {
    "__init__.py": "a2b3412fc502b7631295d639092e320d73f848895b994edc16bf9eebf8b5054c",
    "replay_buffer.py": "28556797d15e0acf9387030b87f9ccce0b18e1e3cfa629b63c2d7239a4206238",
    "config.py": "f2794754a14e9f13c82b613aa131698246a08dc9021c18f1b78fda7c4b484498",
    "learning_control.py": "29a74b25be391290b07373cdce4680ae7513db31596929f0bc9972aaf0ab220d",
    "learning_exposure.py": "30d9191e9fc845d80e52a7a891244fcf0c7041cf60529f6559b15e6d47ac5c7f",
    "actor_tags.py": "fc5b868a7fb68d4ab7ba65ba872ea0e845759af6143edfe648239d57cb7f1591",
    "bank_output.py": "85a161a445dc44e8bb0ef225a5630b485ff0c4d4874f9d04367544ab744caa9d",
    "native_sumtree.py": "de0900aecd09668dc0551d4ecec118351a1228e2a664bc183c5c06b865e52250",
    "sumtree.c": "352badec2ee64b7c42852e743bf930c565a2e4279137df12ca859d2c396d8e5e",
}
CANDIDATE_SHA256 = "b659cd7bba656adb1c313d6805f0499d23dcb2a60f1cb779da11e2696f2dd17c"
BATCH = 4096
CAPACITY = 8192
STATE_WIDTH = 8
SEED = 20261017
OBSERVATIONS = []


def checked_source(path, expected):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"Source must be a regular, non-symlink file: {path}")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"Pinned source drift: {path}")
    return data


def configure_private_environment(work):
    """Before NumPy/config import; paths are all private fixture directories."""
    if any(name == "numpy" or name == "torch" or name.startswith("dqn")
           or name.startswith("kl_fixture_") for name in sys.modules):
        raise RuntimeError("Run in a fresh interpreter before numerical/application imports")
    # A preloaded library cannot be unloaded here. The documented command
    # unsets LD_PRELOAD/PYTHONPATH before interpreter startup as well.
    for name in list(os.environ):
        if name.startswith(("DQN_", "ROBOTRON_")) or name in ("LD_PRELOAD", "PYTHONPATH"):
            os.environ.pop(name, None)
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "2"
    os.environ.update(CUDA_VISIBLE_DEVICES="", DQN_FRAME_STACK="4",
                      DQN_LEARNING_EXPOSURE_COUNTERS="0", DQN_NATIVE_BATCH_UPDATE="0")
    for name in ("models", "journal", "cache", "tmpfs"):
        (work / name).mkdir()
    control = work / "learning-control.json"
    control.write_text('{}\n')
    (work / "models/game_settings.json").write_text('{}\n')
    os.environ.update(ROBOTRON_DQN_MODEL_DIR=str(work / "models"),
                      ROBOTRON_DQN_CONTROL_PATH=str(control),
                      ROBOTRON_RUN_DIR=str(work / "journal"),
                      XDG_CACHE_HOME=str(work / "cache"))


def load_private_sources(work):
    """Copy and import the actual pinned modules, including native helpers.

    Native code may compile only into these new package sibling __pycache__
    directories. No AST extraction/reimplementation or production source writes.
    """
    originals = {name: checked_source(REPO / "Robotron/Scripts/dqn" / name, expected)
                 for name, expected in PINS.items()}
    candidate = checked_source(HERE / "replay_buffer_candidate.py", CANDIDATE_SHA256)
    configure_private_environment(work)
    packages = work / "packages"
    packages.mkdir()
    for package, replacement in (("kl_fixture_base", None), ("kl_fixture_candidate", candidate)):
        directory = packages / package
        directory.mkdir()
        for name, data in originals.items():
            (directory / name).write_bytes(replacement if name == "replay_buffer.py" and replacement else data)
    sys.path.insert(0, str(packages))
    modules = []
    for package in ("kl_fixture_base", "kl_fixture_candidate"):
        config = importlib.import_module(package + ".config")
        cfg = config.RL_CONFIG
        # Only synthetic storage dimensions and fixture source counts change.
        # Quota/normalization functions execute from the actual source module.
        cfg.hof_enabled = cfg.ephof_enabled = True
        cfg.hof_max_episodes = cfg.ephof_max_episodes = 8
        cfg.hof_episode_stride = cfg.ephof_episode_stride = 512
        cfg.hof_min_transitions = cfg.ephof_min_transitions = 4096
        cfg.hof_replay_fraction, cfg.ephof_replay_fraction = .10, .15
        cfg.interesting_replay_fraction, cfg.recent_replay_fraction = .18, .35
        cfg.interesting_replay_bank_size = CAPACITY
        cfg.recent_replay_window = 1024
        cfg.bank_starvation_adds, cfg.bank_stale_quota_floor = 1000, .25
        cfg.replay_tmpfs_dir = str(work / "tmpfs")
        module = importlib.import_module(package + ".replay_buffer")
        modules.append(module)
    for name, module in list(sys.modules.items()):
        if name.startswith(("kl_fixture_base", "kl_fixture_candidate")):
            source = Path(module.__file__).resolve()
            if not source.is_relative_to(packages.resolve()):
                raise RuntimeError(f"Escaped copied package: {name}")
    if "torch" in sys.modules or os.environ["CUDA_VISIBLE_DEVICES"] != "":
        raise RuntimeError("Sampler mechanics must not import Torch or expose CUDA")
    OBSERVATIONS.append(dict(native_helpers={
        package: dict(status=sys.modules[package + ".native_sumtree"].NATIVE_STATUS,
                      propagation=sys.modules[package + ".native_sumtree"].NATIVE_AVAILABLE,
                      gather=sys.modules[package + ".native_sumtree"].NATIVE_GATHER_AVAILABLE,
                      batch_update_enabled=sys.modules[package + ".native_sumtree"].NATIVE_BATCH_ENABLED)
        for package in ("kl_fixture_base", "kl_fixture_candidate")},
        note="Availability is recorded; Python fallback does not certify a native path."))
    return modules


def make_buffer(module, scenario="default"):
    """Build deterministic, synthetic compact-width storage; not live data.

    Bank arrays are fixture-populated valid-slot tables, not an admission or
    persistence test. Sampling, quotas, origins, duplicates and IS are real code.
    """
    import numpy as np
    cfg = sys.modules[module.__package__ + ".config"].RL_CONFIG
    cfg.recent_replay_window = 1 if scenario == "duplicates" else 1024
    buffer = module.PrioritizedReplayBuffer(CAPACITY, STATE_WIDTH, alpha=.7)
    indices = np.arange(CAPACITY)
    for column in range(STATE_WIDTH):
        buffer.states[:, column] = (indices % (column + 7)) / 16.
        buffer.next_states[:, column] = -buffer.states[:, column]
    buffer.actions[:] = indices % 81
    buffer.rewards[:] = ((indices % 23) - 11) / 11.
    buffer.dones[:] = (indices % 17) == 0
    buffer.horizons[:] = indices % 3 + 1
    buffer.is_expert[:] = (indices % 7) == 0
    buffer.actor_kind[:] = np.where(buffer.is_expert, 2, indices % 2)
    buffer.interesting[:] = 1.
    buffer._interesting_bank[:] = indices
    buffer._interesting_bank_count = CAPACITY
    buffer._n_interesting = CAPACITY
    buffer.size = buffer.tree.size = CAPACITY
    buffer.tree.data_ptr = 137
    buffer._adds_total = CAPACITY + 137
    leaves = 0.03 + (indices % 101) / 11.
    if scenario == "duplicates":
        leaves[:] = 1e-14
        leaves[136] = 1e6
        buffer._interesting_bank[:] = 136
    buffer.tree.tree[CAPACITY:] = leaves
    for parent in range(CAPACITY - 1, 0, -1):
        buffer.tree.tree[parent] = buffer.tree.tree[2 * parent] + buffer.tree.tree[2 * parent + 1]
    buffer.tree.max_priority = float(leaves.max())
    for bank in ("hof", "ephof"):
        getattr(buffer, bank + "_ep_len")[:] = 512
        getattr(buffer, bank + "_ep_score")[:] = 100_000
        setattr(buffer, bank + "_ep_count", 8)
        setattr(buffer, bank + "_total", 4096)
        setattr(buffer, "_" + bank + "_flat", np.arange(4096, dtype=np.int64))
        setattr(buffer, "_" + bank + "_last_admit_add", buffer._adds_total)
        setattr(buffer, "_" + bank + "_last_normal_admit_add", buffer._adds_total)
        buffer._bank_revision[bank] = 4
        for field in ("actions", "rewards", "dones", "horizons", "is_expert", "actor_kind"):
            getattr(buffer, bank + "_" + field)[:] = getattr(buffer, field)[:4096]
        getattr(buffer, bank + "_states")[:] = 2.1234567 if bank == "hof" else 3.2345678
        getattr(buffer, bank + "_next_states")[:] = -getattr(buffer, bank + "_states")
    if scenario == "bank_shortfall":
        buffer.hof_total = buffer.ephof_total = 4095
        buffer.hof_ep_len[-1] = buffer.ephof_ep_len[-1] = 511
        # Keep valid flat tables consistent with the under-threshold totals.
        with buffer.lock:
            buffer._hof_rebuild_flat_locked()
            buffer._ephof_rebuild_flat_locked()
    if scenario == "interesting_shortfall":
        buffer.interesting[:] = 0.
        buffer.interesting[0] = 1.
        buffer._interesting_bank[:] = -1
        buffer._n_interesting = 1
    if scenario == "stale_banks":
        for bank in ("hof", "ephof"):
            setattr(buffer, "_" + bank + "_last_admit_add", buffer._adds_total - 3000)
    return buffer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-fixture", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.execute_fixture:
        # No source/data reads, package imports, output mutation or runtime query.
        print(json.dumps(dict(status="PLAN_ONLY_UNEXECUTED", batch_rows=BATCH,
                              state_width=STATE_WIDTH, scenarios=5,
                              eight_executed_ce_attempts="NOT_IMPLEMENTED")))
        return 0
    if args.output is None:
        parser.error("Explicit new --output under run-26/kl-sampler-fixture-* is required")
    output = args.output.absolute()
    allowed = (REPO / "Robotron/logs/managed-learning-20261015/run-26").resolve()
    if output.parent.resolve() != allowed or not output.name.startswith("kl-sampler-fixture-"):
        raise RuntimeError("Fixture output must be a new, directly owned run-26/kl-sampler-fixture-* directory")
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
    output.mkdir()  # create-only; no restoration or reuse of existing artifacts
    os.environ["KL_SAMPLER_FIXTURE_OUTPUT"] = str(output)
    sys.modules.setdefault("sampler_fixture", sys.modules[__name__])
    sys.path.insert(0, str(HERE))
    specification = importlib.util.spec_from_file_location(
        "kl_sampler_fixture_tests", HERE / "test_sampler_fixture.py")
    tests = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(tests)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(tests))
    (output / "test-output.txt").write_text(stream.getvalue())
    report = dict(status="FIXTURE_PASS" if result.wasSuccessful() else "FIXTURE_FAIL",
                  tests_run=result.testsRun, errors=len(result.errors), failures=len(result.failures),
                  source_pins=PINS, candidate_sha256=CANDIDATE_SHA256,
                  batch_rows=BATCH, state_width=STATE_WIDTH, capacity=CAPACITY,
                  synthetic_only=True, numpy_imported="numpy" in sys.modules,
                  torch_imported="torch" in sys.modules, cuda_visible=os.environ.get("CUDA_VISIBLE_DEVICES"),
                  observations=OBSERVATIONS,
                  eight_executed_ce_attempts="NOT_IMPLEMENTED_NOT_VALIDATED")
    (output / "fixture-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(stream.getvalue(), end="")
    print(json.dumps({"status": report["status"], "output": str(output)}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
