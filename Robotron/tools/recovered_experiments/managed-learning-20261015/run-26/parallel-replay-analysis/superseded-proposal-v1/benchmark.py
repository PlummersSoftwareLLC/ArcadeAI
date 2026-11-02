#!/usr/bin/env python3
"""Bounded copied-pool CPU benchmark; no trainer/control/model/CUDA writes."""

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import mmap
import os
from pathlib import Path
import resource
import statistics
import sys
import time

# There are two executor workers and no nested BLAS/OpenMP thread teams.
os.environ["CUDA_VISIBLE_DEVICES"] = ""
for _key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
with contextlib.redirect_stdout(sys.stderr):
    from Robotron.Scripts.dqn import native_sumtree
    from Robotron.tools.parallel_replay_proposal.parallel_replay import FieldFill, ParallelFill, fill_sequential

FIELDS = ("states", "next_states")


def digest_array(array):
    return hashlib.sha256(memoryview(array).cast("B")).hexdigest()


def bank_generation(path, bank):
    """Resolve CURRENT once. All files are subsequently opened from that path.

    No mixed old/current field reads or legacy fallback are permitted when a
    CURRENT pointer exists. If generation cleanup wins the race before all
    files open, fail this observation rather than silently sample another one.
    """
    pointer = path / "CURRENT.json"
    if not pointer.exists():
        return path, dict(format="legacy", path=str(path))
    raw = pointer.read_bytes()
    data = json.loads(raw)
    generation = data.get("generation", "") if isinstance(data, dict) else ""
    if (not isinstance(data, dict) or data.get("schema") != "robotron-bank-generation-v1"
            or data.get("bank") != bank or not isinstance(generation, str)
            or len(generation) != 36 or not generation.startswith("gen-")
            or any(char not in "0123456789abcdef" for char in generation[4:])):
        raise ValueError("Invalid bank generation pointer")
    resolved = path / "generations" / generation
    if not resolved.is_dir() or resolved.is_symlink():
        raise ValueError("Selected bank generation missing or not a regular directory")
    return resolved, dict(format="generation", path=str(resolved), pointer=data,
                         pointer_sha256=hashlib.sha256(raw).hexdigest())


def copy_pool(path, name, rng, count, ring_size=None):
    """Copy only selected states/next states; exclude bank stride padding."""
    prefix = "" if name == "ring" else name + "_"
    opened = {}
    try:
        # Open both read-only mappings before copying; retain mappings even if
        # the writer unlinks this now-old generation during the row copy.
        for field in FIELDS:
            opened[field] = np.load(path / f"{prefix}{field}.npy", mmap_mode="r", allow_pickle=False)
            # Linux mmap fault-around can otherwise make many unselected file
            # pages resident in this process during random row copying.
            if hasattr(mmap, "MADV_RANDOM"):
                opened[field]._mmap.madvise(mmap.MADV_RANDOM)
        first = opened["states"]
        if (first.ndim != 2 or opened["next_states"].shape != first.shape
                or any(source.dtype != np.dtype(np.float16 if name == "ring" else np.float32)
                       for source in opened.values())):
            raise ValueError("Unexpected state storage shape or dtype")
        provenance = dict(path=str(path), storage_rows=len(first), state_width=first.shape[1])
        if name == "ring":
            saved_meta = np.load(path / "_meta.npy", allow_pickle=False)
            saved_size = int(saved_meta[1])
            valid_size = saved_size if ring_size is None else ring_size
            if not 0 < valid_size <= len(first):
                raise ValueError("Ring size is outside available rows")
            indices = rng.integers(0, valid_size, count, dtype=np.int64)
            provenance.update(valid_rows=valid_size, saved_size=saved_size, explicit_ring_size=ring_size)
        else:
            with np.load(path / f"{prefix}meta.npz", allow_pickle=False) as meta:
                lengths = np.asarray(meta["ep_len"], dtype=np.int64)
                stride = int(meta["stride"])
            if (lengths.ndim != 1 or stride < 1 or np.any((lengths < 0) | (lengths > stride))
                    or len(lengths) * stride > len(first)):
                raise ValueError("Invalid bank stride/episode geometry")
            cumulative = np.cumsum(lengths)
            valid_size = int(cumulative[-1]) if len(lengths) else 0
            if not valid_size:
                raise ValueError("Representative benchmark requires a populated bank")
            offsets = rng.integers(0, valid_size, count, dtype=np.int64)
            episodes = np.searchsorted(cumulative, offsets, side="right")
            starts = np.concatenate(([0], cumulative[:-1]))
            indices = episodes * stride + offsets - starts[episodes]
            provenance.update(valid_rows=valid_size, episodes=len(lengths), stride=stride,
                              episode_lengths=lengths.tolist())
        result = {}
        for field, source in opened.items():
            result[field] = np.empty((count, source.shape[1]), source.dtype)
            for start in range(0, count, 64):
                result[field][start:start + 64] = source[indices[start:start + 64]]
                # Unmap only this process's completed file-backed pages; retain
                # the read-only descriptor to pin the chosen generation. This
                # does not evict the trainer's mappings or the shared page cache.
                if hasattr(mmap, "MADV_DONTNEED"):
                    source._mmap.madvise(mmap.MADV_DONTNEED)
        for value in result.values():
            value.flags.writeable = False
        provenance.update(copied_rows=count, copied_index_sha256=digest_array(indices),
                          copied_index_min=int(indices.min()), copied_index_max=int(indices.max()))
        return result, provenance
    finally:
        for source in opened.values():
            source._mmap.close()


def expected_row_chunks(output, field, sources, indices):
    """Check in bounded chunks without allocating a full additional field."""
    cursor = 0
    for name in ("ring", "hof", "ephof"):
        selected = indices[name]
        for start in range(0, len(selected), 128):
            rows = selected[start:start + 128]
            expected = sources[name][field][rows].astype(np.float32, copy=False)
            actual = output[cursor + start:cursor + start + len(rows)]
            if not np.array_equal(actual, expected, equal_nan=True):
                return False
            finite = np.isfinite(expected)
            if not np.array_equal(actual.view(np.uint32)[finite], expected.view(np.uint32)[finite]):
                return False
        cursor += len(selected)
    return cursor == len(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, default=Path("/dev/shm/robotron_dqn_latest_replay"))
    parser.add_argument("--bank-base", type=Path, default=ROOT / "Robotron/models_dqn/robotron_dqn_latest_replay")
    parser.add_argument("--ring-size", type=int)
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[2048, 4096])
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--seed", type=int, default=713711)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 6 <= args.rounds <= 8 or any(size not in (2048, 4096) for size in args.batch_sizes):
        parser.error("Only 6..8 rounds and batch sizes 2048/4096 are permitted")
    if len(args.batch_sizes) != len(set(args.batch_sizes)):
        parser.error("Duplicate batch sizes are not permitted")
    if not native_sumtree.NATIVE_GATHER_AVAILABLE:
        parser.error("This observation requires the production native fp16 gather")
    rng = np.random.default_rng(args.seed)
    sources, provenance = {}, {}
    rss_milestones = {}
    for name, count in (("ring", 4096), ("hof", 512), ("ephof", 512)):
        path = args.replay_dir if name == "ring" else Path(f"{args.bank_base}_{name}")
        selected = {}
        if name != "ring":
            path, selected = bank_generation(path, name)
        sources[name], provenance[name] = copy_pool(path, name, rng, count, args.ring_size)
        provenance[name].update(selected)
        rss_milestones[name + "_copy_peak"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    hashes_before = {name: {field: digest_array(array) for field, array in fields.items()}
                     for name, fields in sources.items()}
    source_bytes = sum(value.nbytes for fields in sources.values() for value in fields.values())
    maximum = max(args.batch_sizes)
    width = sources["ring"]["states"].shape[1]
    # One reused output pair, plus two bank fancy-index temporaries and bounded
    # equality chunks, leaves ample space below the 1GiB process RSS budget.
    projected_bytes = source_bytes + 2 * maximum * width * 4 + 2 * round(maximum * .15) * width * 4 + 32 * 1024**2
    if projected_bytes > 900 * 1024**2:
        raise ValueError("Projected private array memory exceeds bounded budget")
    storage = [np.empty((maximum, width), np.float32) for _ in FIELDS]
    results = []
    with ParallelFill() as parallel:
        for size in args.batch_sizes:
            counts = dict(hof=round(size * .10), ephof=round(size * .15))
            counts["ring"] = size - sum(counts.values())
            samples = [{name: rng.integers(0, len(sources[name]["states"]), count, dtype=np.int64)
                        for name, count in counts.items()} for _ in range(args.rounds + 1)]
            timings = dict(sequential=[], parallel=[])
            exact = True
            for round_index, indices in enumerate(samples):
                fields = tuple(FieldFill(storage[index][:size], sources["ring"][field], indices["ring"],
                                         tuple((sources[name][field], indices[name]) for name in ("hof", "ephof")))
                               for index, field in enumerate(FIELDS))
                order = ("sequential", "parallel") if round_index % 2 == 0 else ("parallel", "sequential")
                for method in order:
                    began = time.perf_counter()
                    (fill_sequential if method == "sequential" else parallel.fill)(fields)
                    elapsed = (time.perf_counter() - began) * 1000
                    if round_index:
                        timings[method].append(elapsed)
                    # Validate each method before the other can overwrite it.
                    for output, field in zip(storage, FIELDS):
                        exact &= expected_row_chunks(output[:size], field, sources, indices)
                    if not exact:
                        raise AssertionError("Sequential/parallel output differs from NumPy row oracle")
            medians = {name: statistics.median(values) for name, values in timings.items()}
            results.append(dict(batch_size=size, row_mix=counts, timings_ms=timings,
                                medians_ms=medians, parallel_speedup=medians["sequential"] / medians["parallel"],
                                parallel_reduction_pct=100 * (1 - medians["parallel"] / medians["sequential"]),
                                exact_equal=exact))
    hashes_after = {name: {field: digest_array(array) for field, array in fields.items()}
                    for name, fields in sources.items()}
    peak_rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    report = dict(schema="robotron-parallel-replay-offline-v1", utc=datetime.now(timezone.utc).isoformat(),
                  seed=args.seed, rounds=args.rounds, workers=2, nested_math_threads=1,
                  cuda_visible=os.environ["CUDA_VISIBLE_DEVICES"], native_status=native_sumtree.NATIVE_STATUS,
                  state_width=width, copied_source_bytes=source_bytes, output_pair_bytes=sum(x.nbytes for x in storage),
                  projected_private_array_bytes=projected_bytes, peak_rss_bytes=peak_rss_bytes,
                  rss_milestones=rss_milestones,
                  sources_unchanged=hashes_before == hashes_after, source_hashes=hashes_before,
                  provenance=provenance, results=results,
                  caveats=["Copied pools are much smaller than the live 6M-row ring: cache effects can change absolute latency and speedup.",
                           "Read-only ring rows are copied without the trainer replay lock; concurrent overwrites can mix fields. This benchmark tests copying only, not policy quality.",
                           "Saved HOF/EpHOF CURRENT generations are resolved once and all fields copied from those immutable paths; they can lag live banks.",
                           "Pageable NumPy destinations exclude pinned-memory NUMA placement, H2D, sampling/PER, actor insertion and live replay-lock contention.",
                           "Two CPU workers can compete with the live trainer and actors. Alternating order reduces but does not remove cache, scheduler and contention bias.",
                           "Host fill timing is not useful training FPS or faster learning. A separately precommitted live A/B is required before an efficiency claim."])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in ("utc", "peak_rss_bytes", "sources_unchanged", "results")}, indent=2))
    if not report["sources_unchanged"] or peak_rss_bytes > 1024**3:
        raise AssertionError("Source immutability or 1GiB RSS budget failed")


if __name__ == "__main__":
    main()
