#!/usr/bin/env python3
"""Bounded CPU copy-chain benchmark against copied read-only replay rows.

No live replay/RNG/model/control writes or CUDA context. Destination tensors are
pageable CPU buffers; this isolates host work and does not benchmark H2D copies.
"""

import argparse
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import sys
import time

os.environ["CUDA_VISIBLE_DEVICES"] = ""
for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[variable] = "2"

import numpy as np
import torch

from probe_checkpoint_cpu import load_partition


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--replay-dir", type=Path, default=Path("/dev/shm/robotron_dqn_latest_replay"))
    parser.add_argument("--bank-base", type=Path, default=Path(__file__).resolve().parents[1] / "models_dqn/robotron_dqn_latest_replay")
    parser.add_argument("--ring-size", type=int, default=6000000)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=2048)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 12 or not 1 <= args.batch_size <= 2048:
        parser.error("rounds must be1..12 and batch-size1..2048")
    torch.set_num_threads(2)
    torch.set_num_interop_threads(2)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    with contextlib.redirect_stdout(sys.stderr):
        from Robotron.Scripts.dqn import replay_buffer
    rng = np.random.default_rng(71713)
    sources = {}
    for name, count in (("ring", 4096), ("hof", 512), ("ephof", 512)):
        path = args.replay_dir if name == "ring" else Path(f"{args.bank_base}_{name}")
        loaded = load_partition(path, name, rng, count, args.ring_size)
        if loaded is None:
            raise RuntimeError(f"Representative benchmark needs populated{name}")
        _, arrays = loaded
        sources[name] = {key: arrays[key] for key in ("states", "next_states")}
        for value in sources[name].values():
            value.flags.writeable = False
    width = sources["ring"]["states"].shape[1]
    host = [torch.empty((args.batch_size, width), dtype=torch.float32) for _ in range(2)]
    outputs = [tensor.numpy() for tensor in host]
    hof_count, ephof_count = round(args.batch_size * .10), round(args.batch_size * .15)
    ring_count = args.batch_size-hof_count-ephof_count
    samples = [(
        rng.integers(0, 4096, ring_count, dtype=np.int64),
        rng.integers(0, 512, hof_count, dtype=np.int64),
        rng.integers(0, 512, ephof_count, dtype=np.int64),
    ) for _ in range(args.rounds+1)]

    def baseline(indices):
        t0 = time.perf_counter()
        ring = [replay_buffer._gather_states_fp32(sources["ring"][field], indices[0])
                for field in ("states", "next_states")]
        t1 = time.perf_counter()
        joined = [np.concatenate((ring[index], sources["hof"][field][indices[1]],
                                  sources["ephof"][field][indices[2]]))
                  for index, field in enumerate(("states", "next_states"))]
        t2 = time.perf_counter()
        for destination, source in zip(host, joined):
            destination.copy_(torch.from_numpy(source))
        t3 = time.perf_counter()
        return dict(gather_ms=(t1-t0)*1000, bank_concat_ms=(t2-t1)*1000,
                    host_stage_ms=(t3-t2)*1000, total_ms=(t3-t0)*1000)

    def direct(indices):
        t0 = time.perf_counter()
        for output, field in zip(outputs, ("states", "next_states")):
            replay_buffer._fill_state_rows(
                output, sources["ring"][field], indices[0],
                [(sources["hof"][field], indices[1]), (sources["ephof"][field], indices[2])],
            )
        return dict(total_ms=(time.perf_counter()-t0)*1000)

    baseline(samples[0])
    if not args.baseline_only:
        direct(samples[0])
    timings = {"baseline": []}
    if not args.baseline_only:
        timings["direct"] = []
    equivalent = True
    for index, indices in enumerate(samples[1:]):
        # Alternate order to reduce systematic cache/temperature advantage.
        names = ["baseline"] if args.baseline_only else (["baseline", "direct"] if index % 2 == 0 else ["direct", "baseline"])
        for name in names:
            timings[name].append((baseline if name == "baseline" else direct)(indices))
            if name == "direct":
                # Validate immediately, before a following baseline call can
                # overwrite the same destinations and conceal a bad fill.
                for output, field in zip(outputs, ("states", "next_states")):
                    expected = np.concatenate((sources["ring"][field][indices[0]].astype(np.float32),
                                               sources["hof"][field][indices[1]], sources["ephof"][field][indices[2]]))
                    equivalent &= bool(np.array_equal(output, expected, equal_nan=True))
    summary = {name: {key: statistics.median(row[key] for row in rows) for key in rows[0]}
               for name, rows in timings.items()}
    report = dict(
        utc=datetime.now(timezone.utc).isoformat(), batch_size=args.batch_size, state_width=width,
        rounds=args.rounds, cpu_threads=torch.get_num_threads(), cuda_visible=os.environ["CUDA_VISIBLE_DEVICES"],
        row_mix=dict(ring=ring_count, hof=hof_count, ephof=ephof_count),
        copied_source_bytes=sum(array.nbytes for fields in sources.values() for array in fields.values()),
        output_pair_bytes=sum(array.nbytes for array in outputs),
        medians=summary, timings=timings, exact_equal=equivalent,
        caveats=["Copied read-only pools exclude the live replay lock, PER selection, live RNG and writer contention.",
                 "CPU destinations are pageable, not pinned; no H2D or GPU work is timed.",
                 "This measures host state gathering/concatenation/staging only; live FPS and learning gains require a later opt-in trial."],
    )
    if "direct" in summary:
        report["host_chain_speedup"] = summary["baseline"]["total_ms"] / summary["direct"]["total_ms"]
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
