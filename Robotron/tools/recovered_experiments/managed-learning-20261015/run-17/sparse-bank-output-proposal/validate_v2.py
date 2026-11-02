"""Validate proposed helper/replay plus durable test; never apply or launch."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import time
import unittest


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("Require CUDA_VISIBLE_DEVICES='' for this CPU-only test")
    here = Path(__file__).resolve().parent
    game = here.parents[3]
    paths = [*sorted((here / "proposed").glob("*.py")), here / "test_integration.py",
        here / "prepare_v2.py", Path(__file__), here / "sparse-bank-output-v2.patch",
        game / "Scripts/dqn/replay_buffer.py", game / "Scripts/dqn/pipeline_telemetry.py",
        game / "Scripts/dqn/run_telemetry.py"]
    before = {str(path): digest(path) for path in paths}
    started = datetime.now(timezone.utc).isoformat()
    sys.path.insert(0, str(here))
    integration = load("sparse_bank_integration_v2", here / "test_integration.py")
    durable = load("dqn.test_bank_output_prepared", here / "proposed/test_bank_output.py")
    import torch
    if torch.cuda.is_initialized():
        raise RuntimeError("Unexpected CUDA initialization")
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(integration),
                               unittest.defaultTestLoader.loadTestsFromModule(durable)])
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t0 = time.perf_counter()
    with (here / "test-output-v2.txt").open("x") as log:
        result = unittest.TextTestRunner(verbosity=2, stream=log).run(suite)
    after = {str(path): digest(path) for path in paths}
    value = dict(schema="robotron-sparse-bank-output-v2-validation-v1",
        started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(),
        tests_run=result.testsRun, integration_tests=44, durable_tests=9,
        existing_bank_tests_per_mode=16, existing_bank_modes=[0, 1],
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        passed=result.wasSuccessful(), test_wall_s=time.perf_counter()-t0,
        source_hashes=before, sources_unchanged=before == after,
        test_log_sha256=digest(here / "test-output-v2.txt"),
        maxrss_before_suite_kib=rss_before,
        maxrss_after_suite_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        torch_threads=torch.get_num_threads(), cuda_initialized=torch.cuda.is_initialized(),
        proposal_only=True, production_applied=False, process_controls=False, GPU_context=False,
        postapply_commands=[
            "CUDA_VISIBLE_DEVICES='' DQN_STREAM_BANK_OUTPUT=0 python -m unittest dqn.test_bank_persistence dqn.test_bank_output",
            "CUDA_VISIBLE_DEVICES='' DQN_STREAM_BANK_OUTPUT=1 python -m unittest dqn.test_bank_persistence dqn.test_bank_output"],
        limits=["Commands above require Robotron/Scripts on PYTHONPATH after authorized application.",
                "Preparation tests explicitly load proposed replay while reusing all existing bank tests.",
                "No live performance, bank-stall cause or power-loss durability conclusion."])
    with (here / "validation-v2.json").open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write("\n")
    print(json.dumps({name: value[name] for name in ("tests_run", "passed", "failures", "errors",
        "test_wall_s", "sources_unchanged", "cuda_initialized")}))
    if not (result.wasSuccessful() and before == after and not torch.cuda.is_initialized()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
