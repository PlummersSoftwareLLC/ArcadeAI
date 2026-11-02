"""Bounded, CPU-only priority timing using actual source AST, never live replay."""
import ast
import datetime
import hashlib
import json
import pathlib
import threading
import time

import numpy as np


BASE = pathlib.Path(__file__).resolve().parents[4]
SOURCE = BASE / "Robotron/Scripts/dqn/replay_buffer.py"
DESTINATION = pathlib.Path(__file__).with_name("learner-priority-cpu-probe.json")


def summarize(values):
    return {"n": len(values), "median_ms": float(np.median(values)),
            "p95_ms": float(np.percentile(values, 95)),
            "max_ms": float(np.max(values)), "mean_ms": float(np.mean(values))}


def main():
    raw = SOURCE.read_bytes()
    module = ast.parse(raw)
    tree_class = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "SumTree")
    buffer_class = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "PrioritizedReplayBuffer")
    update = next(n for n in buffer_class.body if isinstance(n, ast.FunctionDef) and n.name == "update_priorities")
    namespace = {"np": np, "_native_propagate": None}
    selected = ast.Module(body=[tree_class, update], type_ignores=[])
    exec(compile(ast.fix_missing_locations(selected), str(SOURCE), "exec"), namespace)
    capacity = 6_000_000
    tree = namespace["SumTree"](capacity)
    tree.tree[capacity:] = 1.0
    # Heap depth boundaries are powers of two even for a non-power-of-two cap.
    upper = capacity
    lower = 1 << ((capacity - 1).bit_length() - 1)
    while lower:
        indices = np.arange(lower, upper, dtype=np.int64)
        tree.tree[indices] = tree.tree[indices * 2] + tree.tree[indices * 2 + 1]
        upper, lower = lower, lower >> 1
    assert tree.total() == float(capacity)

    class Buffer:
        pass

    buffer = Buffer()
    buffer.capacity, buffer.alpha, buffer.tree, buffer.lock = capacity, 0.6, tree, threading.Lock()
    random_state_before = np.random.get_state()
    rng = np.random.default_rng(61212026)
    cases = {}
    for label, ring_rows, sentinels, duplicate in (
        ("mixed_batch_2048", 1536, 512, True),
        ("all_ring_2048", 2048, 0, False),
        ("duplicate_heavy_2048", 2048, 0, True),
    ):
        elapsed, preparation, propagation = [], [], []
        for repeat in range(72):
            indices = rng.integers(0, capacity, ring_rows, dtype=np.int64)
            if duplicate:
                n = ring_rows // 5
                indices[-n:] = indices[:n]
            if sentinels:
                indices = np.concatenate([indices, capacity + rng.integers(0, 400_000, sentinels, dtype=np.int64)])
            errors = rng.uniform(0.01, 3.0, len(indices)).astype(np.float32)
            started = time.perf_counter()
            namespace["update_priorities"](buffer, indices, errors)
            update_ms = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            idx = np.asarray(indices, dtype=np.int64)
            td = np.abs(np.asarray(errors).astype(np.float64))
            mask = idx < capacity
            if not mask.all():
                idx, td = idx[mask], td[mask]
            priorities = (td + 1e-6) ** buffer.alpha
            prepare_ms = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            tree.batch_update(idx, priorities)
            propagate_ms = (time.perf_counter() - started) * 1000
            if repeat >= 8:
                elapsed.append(update_ms)
                preparation.append(prepare_ms)
                propagation.append(propagate_ms)
        cases[label] = {"ring_rows": ring_rows, "bank_sentinels": sentinels,
                        "duplicate_fraction_requested": 0.2 if duplicate else 0.0,
                        "actual_update_priorities": summarize(elapsed),
                        "isolated_numpy_mask_power": summarize(preparation),
                        "isolated_batch_update": summarize(propagation)}
    after = np.random.get_state()
    rng_unchanged = all(np.array_equal(a, b) if isinstance(a, np.ndarray) else a == b
                        for a, b in zip(random_state_before, after))
    assert rng_unchanged
    result = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "scope": "CPU-only synthetic AST-extracted actual SumTree and update_priorities; no live replay/import/locks/GPU; serial no contention",
              "source": str(SOURCE), "source_sha256": hashlib.sha256(raw).hexdigest(),
              "probe_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
              "capacity": capacity, "tree_bytes": tree.tree.nbytes,
              "initial_tree_total_exact": True, "numpy_global_rng_unchanged": rng_unchanged,
              "warmups_per_case": 8, "timed_repeats_per_case": 64, "cases": cases,
              "caveats": ["No live replay, model or optimizer construction; private default_rng only.",
                          "Uncontended synthetic timing excludes GPU readback, live scheduling and replay contention; it does not decompose the live priority timer.",
                          "Mask/power and propagation are a second call after the actual update, with warmer caches. Do not sum these as a measured live phase."]}
    DESTINATION.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"path": str(DESTINATION), "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
