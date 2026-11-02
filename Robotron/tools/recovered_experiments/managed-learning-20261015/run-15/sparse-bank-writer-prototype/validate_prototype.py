"""CPU-only validation receipt, never a live benchmark or production installer."""
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("Run with CUDA_VISIBLE_DEVICES='' to forbid device admission")
    here = Path(__file__).resolve().parent
    robotron = here.parents[3]
    paths = [here / "sparse_bank_writer.py", here / "test_sparse_bank_writer.py",
             here / "README.txt", Path(__file__),
             robotron / "Scripts/dqn/replay_buffer.py",
             robotron / "Scripts/dqn/test_bank_persistence.py"]
    before = {str(path): sha(path) for path in paths}
    entry = here / "entry-source"
    entry.mkdir(exist_ok=True)
    for path in paths[-2:]:
        destination = entry / path.name
        if destination.exists() and destination.read_bytes() != path.read_bytes():
            raise ValueError("Preserved entry source changed; do not overwrite it")
        if not destination.exists():
            with destination.open("xb") as output:
                output.write(path.read_bytes())
    sys.path.insert(0, str(here))
    spec = importlib.util.spec_from_file_location("test_sparse_writer_validation",
                                                here / "test_sparse_bank_writer.py")
    tests = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tests
    spec.loader.exec_module(tests)
    import numpy as np
    import torch
    if torch.cuda.is_initialized():
        raise RuntimeError("Unexpected CUDA initialization")
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = datetime.now(timezone.utc).isoformat()
    timer = time.perf_counter()
    log = here / "test-output.txt"
    with log.open("x") as output:
        result = unittest.TextTestRunner(verbosity=2, stream=output).run(
            unittest.defaultTestLoader.loadTestsFromModule(tests))
    elapsed = time.perf_counter() - timer
    after = {str(path): sha(path) for path in paths}
    receipt = dict(schema="robotron-sparse-bank-writer-prototype-validation-v1",
        started_utc=started, ended_utc=datetime.now(timezone.utc).isoformat(),
        default_off=True, production_installed=False,
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), passed=result.wasSuccessful(), test_wall_s=elapsed,
        source_hashes=before, sources_unchanged=before == after,
        test_log=dict(path=str(log), sha256=sha(log)),
        python=sys.version, numpy=np.__version__, torch=torch.__version__,
        torch_threads=torch.get_num_threads(), cuda_initialized=torch.cuda.is_initialized(),
        max_output_write_chunk_bytes=8 * 1024 * 1024,
        largest_full_padded_file_fixture_bytes=512 * 11128 * 4 + 128,
        maxrss_before_suite_kib=rss_before,
        maxrss_after_suite_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        cpu_only=True, live_replay_reads=False, live_replay_writes=False,
        live_process_controls=False,
        limits=["This is not a live throughput or stall-cause experiment.",
                "Hard process exits test selector authority, not power-loss durability.",
                "Small fixtures do not establish 17.5GB unmap/fsync behavior.",
                "RSS includes the imported CPU Torch runtime; file/data fixture bounds are separate."])
    with (here / "validation.json").open("x") as output:
        json.dump(receipt, output, indent=2, allow_nan=False); output.write("\n")
    print(json.dumps({key: receipt[key] for key in ("tests_run", "passed", "failures", "errors",
        "test_wall_s", "sources_unchanged", "cuda_initialized", "maxrss_before_suite_kib",
        "maxrss_after_suite_kib")}))
    if not (result.wasSuccessful() and before == after and not torch.cuda.is_initialized()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
