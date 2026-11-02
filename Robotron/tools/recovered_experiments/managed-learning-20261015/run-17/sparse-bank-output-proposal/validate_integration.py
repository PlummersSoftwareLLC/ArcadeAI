"""Bounded CPU tests and source-only review receipt; no apply/launch capability."""
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


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("Require CUDA_VISIBLE_DEVICES='' for this CPU-only test")
    here = Path(__file__).resolve().parent
    game = here.parents[3]
    paths = [*sorted((here / "proposed").glob("*.py")), here / "test_integration.py",
             here / "prepare_integration.py", here / "README.txt", Path(__file__),
             here / "sparse-bank-output.patch", game / "Scripts/dqn/replay_buffer.py",
             game / "Scripts/dqn/pipeline_telemetry.py", game / "Scripts/dqn/run_telemetry.py"]
    before = {str(path): digest(path) for path in paths}
    started = datetime.now(timezone.utc).isoformat()
    sys.path.insert(0, str(here))
    spec = importlib.util.spec_from_file_location("sparse_bank_integration_tests", here / "test_integration.py")
    tests = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tests
    spec.loader.exec_module(tests)
    import torch
    if torch.cuda.is_initialized():
        raise RuntimeError("Unexpected CUDA initialization")
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t0 = time.perf_counter()
    with (here / "test-output.txt").open("x") as log:
        result = unittest.TextTestRunner(verbosity=2, stream=log).run(
            unittest.defaultTestLoader.loadTestsFromModule(tests))
    after = {str(path): digest(path) for path in paths}
    receipt = dict(schema="robotron-sparse-bank-output-integration-tests-v1",
        started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(),
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), passed=result.wasSuccessful(), test_wall_s=time.perf_counter()-t0,
        source_hashes=before, sources_unchanged=before == after,
        test_log_sha256=digest(here / "test-output.txt"),
        maxrss_before_suite_kib=rss_before,
        maxrss_after_suite_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        torch_threads=torch.get_num_threads(), cuda_initialized=torch.cuda.is_initialized(),
        proposal_only=True, production_applied=False, protocol_sources_changed=False,
        process_controls=False, GPU_context=False,
        limits=["No live throughput, large-bank stall-cause or power-loss durability claim.",
                "Field phase telemetry excludes metadata/CURRENT/directory finalization.",
                "Default memmap now adds bank-only scalar timing overhead; no replay hot-path work."])
    with (here / "validation.json").open("x") as output:
        json.dump(receipt, output, indent=2, allow_nan=False); output.write("\n")
    print(json.dumps({key: receipt[key] for key in ("tests_run", "passed", "failures", "errors",
        "test_wall_s", "sources_unchanged", "cuda_initialized")}))
    if not (result.wasSuccessful() and before == after and not torch.cuda.is_initialized()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
