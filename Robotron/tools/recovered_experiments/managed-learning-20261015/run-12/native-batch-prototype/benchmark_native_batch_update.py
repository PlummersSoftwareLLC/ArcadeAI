"""Short isolated CPU benchmark. Never imports a production replay instance."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import time

import numpy as np
import torch

from native_batch_update import batch_update, load
from test_native_batch_update import ORIGINAL, SOURCE, SumTree, clone


DIRECTORY = Path(__file__).resolve().parent


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def stats(samples):
    return {"n": len(samples), "median_ms": float(np.median(samples)),
            "mean_ms": float(np.mean(samples)), "p95_ms": float(np.percentile(samples, 95)),
            "max_ms": float(np.max(samples))}


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("Run with CUDA_VISIBLE_DEVICES='' explicitly")
    if datetime.datetime.now(datetime.timezone.utc) < datetime.datetime(2026, 10, 16, 7, 3, 15, tzinfo=datetime.timezone.utc):
        raise RuntimeError("Parent's performance-window gate has not elapsed")
    torch.set_num_threads(2)
    load()
    started_utc, started = utc(), time.monotonic()
    py_rng, np_rng, torch_rng = random.getstate(), np.random.get_state(), torch.get_rng_state().clone()
    rng = np.random.default_rng(101607)
    initial = SumTree(6_000_000)
    # Intentionally inconsistent old parents make the current method the only
    # oracle; leaf values and parents vary across many magnitudes and signs.
    initial.tree[:] = rng.uniform(-1000.0, 1000.0, initial.tree.size)
    reference, candidate = initial, clone(initial)
    validation_batches, byte_checks, cases = 0, 0, {}
    for case, ring_rows, sentinels, duplicates in (
        ("mixed2048", 1536, 512, True),
        ("ring2048", 2048, 0, False),
        ("duplicate_heavy2048", 2048, 0, True),
    ):
        reference_times, native_times = [], []
        for repeat in range(144):
            indices = rng.integers(0, reference.capacity, ring_rows, dtype=np.int64)
            if duplicates:
                n = ring_rows // 5
                indices[-n:] = indices[:n]
            # Mimic the unchanged caller's sentinel filtering and power cast.
            all_indices = np.concatenate((indices, reference.capacity + rng.integers(0, 400_000, sentinels, dtype=np.int64)))
            errors = rng.uniform(-3.0, 3.0, all_indices.size).astype(np.float32)
            selected = all_indices < reference.capacity
            indices = all_indices[selected]
            priorities = (np.abs(errors.astype(np.float64))[selected] + 1e-6) ** 0.6
            def old():
                before = time.perf_counter()
                ORIGINAL(reference, indices, priorities)
                return (time.perf_counter() - before) * 1000
            def new():
                before = time.perf_counter()
                used = batch_update(candidate, indices, priorities, ORIGINAL)
                elapsed = (time.perf_counter() - before) * 1000
                if not used:
                    raise AssertionError("Native path rejected a supported benchmark batch")
                return elapsed
            # Alternate ordering to avoid consistently favouring one cache path.
            if repeat % 2:
                native, python = new(), old()
            else:
                python, native = old(), new()
            if repeat >= 16:
                reference_times.append(python)
                native_times.append(native)
            validation_batches += 1
            if repeat % 24 == 23:
                assert reference.tree.tobytes() == candidate.tree.tobytes()
                assert np.float64(reference.max_priority).tobytes() == np.float64(candidate.max_priority).tobytes()
                byte_checks += 1
        old_stats, new_stats = stats(reference_times), stats(native_times)
        cases[case] = {"ring_rows": ring_rows, "bank_sentinels_filtered": sentinels,
                       "warmups": 16, "timed_batches": 128,
                       "python": old_stats, "native_with_validation": new_stats,
                       "median_speedup": old_stats["median_ms"] / new_stats["median_ms"],
                       "median_saved_ms": old_stats["median_ms"] - new_stats["median_ms"]}
    after = np.random.get_state()
    checks = {"full_tree_byte_identity": reference.tree.tobytes() == candidate.tree.tobytes(),
              "max_priority_identity": np.float64(reference.max_priority).tobytes() == np.float64(candidate.max_priority).tobytes(),
              "python_rng_unchanged": py_rng == random.getstate(),
              "numpy_rng_unchanged": all(np.array_equal(a, b) if isinstance(a, np.ndarray) else a == b for a, b in zip(np_rng, after)),
              "torch_cpu_rng_unchanged": torch.equal(torch_rng, torch.get_rng_state()),
              "cuda_uninitialized": not torch.cuda.is_initialized()}
    assert all(checks.values())
    ended_utc = utc()
    files = [SOURCE, DIRECTORY / "batch_update.c", DIRECTORY / "native_batch_update.py",
             DIRECTORY / "test_native_batch_update.py", Path(__file__)]
    report = {"schema": "robotron-native-batch-offline-benchmark-v1", "pid": os.getpid(),
              "start_utc": started_utc, "end_utc": ended_utc,
              "wall_s": time.monotonic() - started, "capacity": reference.capacity,
              "tree_bytes_each": reference.tree.nbytes, "simultaneous_tree_count": 2,
              "validated_sequential_batches": validation_batches,
              "full_tree_byte_checks": byte_checks + 1,
              "checks": checks, "cases": cases,
              "source_hashes": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              "scope": ["Offline CPU-only synthetic trees; no live replay/model/optimizer or production source edits.",
                        "Native timing includes ABI validation, C allocations/sort/staged propagation and Python max_priority update; original timing is the unchanged actual SumTree.batch_update method.",
                        "Sentinel filtering/TD power conversion is shared input preparation outside both timings. Both paths receive identical immutable inputs.",
                        "No GPU/readback/lock contention; this does not establish a live throughput gain or explain intermittent priority spikes."]}
    destination = DIRECTORY / "benchmark-result.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
