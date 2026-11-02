#!/usr/bin/env python3
"""Compare compatible DQN checkpoints against one bounded read-only sample.

Run with the GB300 virtual environment; CUDA is hidden before Torch imports.
Example:
  .venv-gb300/bin/python Robotron/tools/probe_checkpoint_cpu.py \
      Robotron/models_dqn/robotron_dqn_best.pt --ring-size 6000000

The total sample is capped at 512 across ring/HOF/EpHOF, and CPU threads at two.
No replay file, checkpoint, configuration, or live process is modified.
"""

import argparse
import contextlib
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

# Enforce these before importing NumPy or Torch, including for imported usage.
os.environ["CUDA_VISIBLE_DEVICES"] = ""
for _thread_variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_variable] = "2"

import numpy as np
import torch


ROBOTRON_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = ROBOTRON_DIR.parent
DIAGNOSTIC_NAMES = (
    "q_min", "q_max", "q_overestimate", "q_mean", "stored_move_agreement",
    "stored_fire_agreement", "target_mass_below_support", "target_mass_above_support",
    "taken_action_edge_mass", "target_entropy", "top_two_q_gap", "categorical_kl",
)
CAVEATS = [
    "Rows are sampled uniformly within each partition, with an equal sample budget per available partition. This is not the learner's PER/recent/interest/bank mixture or its importance weights.",
    "Actor fractions describe sampled stored actions. Eval actions are encoded as DQN; epsilon actions can be uniform or heuristic-guided. Expert agreement compares recorded expert labels only, not fresh expert recommendations.",
    "The live ring is copied without acquiring the trainer lock. Concurrent overwrites can mix columns; bounded row validation detects some, not all, races. Saved bank files can lag live in-memory banks.",
    "Without --ring-size, ring sampling uses the saved metadata's conservative valid prefix; metadata can lag collection. Use a verified telemetry replay_size to include the full live ring.",
    "Checkpoints are evaluated on identical sampled rows and their own saved target network. Current code/configuration supplies architecture, discount and smoothing; old checkpoints may have used different historical settings.",
    "Agreement, Bellman diagnostics and elite-bank scores are offline diagnostics, not unbiased gameplay evaluation. HOF scores are cumulative game score at a life end; EpHOF scores are points earned in one life.",
]


def sample_budget(total, names):
    if not 1 <= total <= 512:
        raise ValueError("--samples must be between 1 and 512 in total")
    return {name: total // len(names) + (index < total % len(names)) for index, name in enumerate(names)}


def load_partition(path, name, rng, count, ring_size=None):
    """Copy sampled rows only; bank indexing excludes stride padding."""
    prefix = "" if name == "ring" else f"{name}_"
    states = np.load(path / f"{prefix}states.npy", mmap_mode="r", allow_pickle=False)
    metadata = {"path": str(path), "storage_rows": len(states), "state_size": states.shape[1]}
    if name == "ring":
        saved_meta = np.load(path / "_meta.npy", allow_pickle=False)
        # Persisted metadata is [write pointer, valid size, maximum priority].
        saved_size = int(saved_meta[1])
        valid_size = saved_size if ring_size is None else ring_size
        if not 0 < valid_size <= len(states):
            raise ValueError(f"ring size {valid_size} outside available rows 1..{len(states)}")
        indices = rng.integers(0, valid_size, count)
        metadata.update(valid_rows=valid_size, saved_size=saved_size, explicit_ring_size=ring_size)
    else:
        with np.load(path / f"{prefix}meta.npz", allow_pickle=False) as bank_meta:
            lengths = np.asarray(bank_meta["ep_len"], dtype=np.int64)
            stride = int(bank_meta["stride"])
            if np.any((lengths < 0) | (lengths > stride)):
                raise ValueError(f"{name} has invalid episode lengths")
            cumulative = np.cumsum(lengths)
            valid_size = int(cumulative[-1]) if len(cumulative) else 0
            if not valid_size:
                return None
            offsets = rng.integers(0, valid_size, count)
            episodes = np.searchsorted(cumulative, offsets, side="right")
            starts = np.concatenate(([0], cumulative[:-1]))
            indices = episodes * stride + offsets - starts[episodes]
            scores = np.asarray(bank_meta["ep_score"])
            metadata.update(
                valid_rows=valid_size, episodes=len(lengths), stride=stride,
                bank_score_semantics="cumulative game score at life end" if name == "hof" else "points earned within one life",
                bank_score_min=float(scores.min()), bank_score_max=float(scores.max()),
            )
    fields = ("states", "next_states", "actions", "rewards", "dones", "horizons", "is_expert")
    arrays = {}
    for field in fields:
        source = states if field == "states" else np.load(path / f"{prefix}{field}.npy", mmap_mode="r", allow_pickle=False)
        arrays[field] = np.asarray(source[indices]).copy()
    actor_path = path / f"{prefix}actor_kind.npy"
    arrays["actor_kind"] = (
        np.asarray(np.load(actor_path, mmap_mode="r", allow_pickle=False)[indices]).copy()
        if actor_path.exists() else np.where(arrays["is_expert"] > 0, 2, 0).astype(np.uint8)
    )
    metadata.update(sample_count=len(indices), sample_index_min=int(indices.min()), sample_index_max=int(indices.max()))
    return metadata, arrays


def validate_arrays(arrays, cfg):
    valid = np.isfinite(arrays["states"]).all(axis=1) & np.isfinite(arrays["next_states"]).all(axis=1)
    valid &= np.isfinite(arrays["rewards"])
    valid &= (arrays["actions"] >= 0) & (arrays["actions"] < cfg.num_joint_actions)
    valid &= (arrays["horizons"] >= 1) & (arrays["horizons"] <= cfg.n_step)
    valid &= np.isin(arrays["dones"], [0, 1]) & np.isin(arrays["is_expert"], [0, 1])
    valid &= np.isin(arrays["actor_kind"], [0, 1, 2])
    return {name: value[valid] for name, value in arrays.items()}, int(np.count_nonzero(~valid))


def probe_partition(online, target, arrays, cfg, TrainingLoss):
    arrays, rejected = validate_arrays(arrays, cfg)
    size = len(arrays["actions"])
    if size == 0:
        return {"sample_count": 0, "rejected_rows": rejected}
    states = torch.from_numpy(arrays["states"]).float()
    next_states = torch.from_numpy(arrays["next_states"]).float()
    actions = torch.from_numpy(arrays["actions"]).long()
    expert = torch.from_numpy(arrays["is_expert"]).bool()
    args = (
        states, actions, torch.from_numpy(arrays["rewards"]).float(), next_states,
        torch.from_numpy(arrays["dones"]).float(), torch.from_numpy(arrays["horizons"]).float(),
        expert, torch.ones(size), torch.zeros(3),
    )
    with torch.inference_mode():
        _, cross_entropy, _, diagnostics = TrainingLoss(online, target, cfg)(*args)
        log_probabilities, bc_logits, _, _ = online.training_outputs(states)
        q = (log_probabilities.exp() * online.support).sum(-1)
        predicted = q.argmax(1)
        expert_count = int(expert.sum())
        q_expert_accuracy = float((predicted[expert] == actions[expert]).float().mean()) if expert_count else None
        bc_expert_accuracy = float((bc_logits.argmax(1)[expert] == actions[expert]).float().mean()) if expert_count else None
        metrics = dict(zip(DIAGNOSTIC_NAMES, map(float, diagnostics)))
        metrics.update(
            sample_count=size, rejected_rows=rejected,
            categorical_cross_entropy=float(cross_entropy.mean()),
            expert_count=expert_count, q_expert_joint_agreement=q_expert_accuracy,
            bc_expert_joint_agreement=bc_expert_accuracy,
            bc_q_joint_agreement=float((predicted == bc_logits.argmax(1)).float().mean()),
            actor_counts={name: int(np.count_nonzero(arrays["actor_kind"] == code)) for code, name in enumerate(("dqn_including_eval", "epsilon", "expert"))},
            mean_horizon=float(arrays["horizons"].mean()),
            horizon_1_fraction=float(np.mean(arrays["horizons"] == 1)),
            full_horizon_fraction=float(np.mean(arrays["horizons"] == cfg.n_step)),
            terminal_fraction=float(np.mean(arrays["dones"])),
            mean_nstep_reward=float(arrays["rewards"].mean()),
        )
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoints", nargs="+", type=Path)
    parser.add_argument("--replay-dir", type=Path, default=Path("/dev/shm/robotron_dqn_latest_replay"))
    parser.add_argument("--bank-base", type=Path, default=ROBOTRON_DIR / "models_dqn/robotron_dqn_latest_replay")
    parser.add_argument("--ring-size", type=int, help="Verified current valid ring size; overrides possibly stale saved metadata")
    parser.add_argument("--samples", type=int, default=512, help="Total row budget across available partitions, maximum512")
    parser.add_argument("--seed", type=int, default=81955)
    args = parser.parse_args()
    if not 1 <= args.samples <= 512:
        parser.error("--samples must be between 1 and 512 in total")
    torch.set_num_threads(2)
    torch.set_num_interop_threads(2)
    sys.path.insert(0, str(REPOSITORY_DIR))
    # Current config can print learning-control status. Keep stdout valid JSON.
    with contextlib.redirect_stdout(sys.stderr):
        from Robotron.Scripts.dqn.config import RL_CONFIG
        from Robotron.Scripts.dqn.loss_kernel import TrainingLoss
        from Robotron.Scripts.dqn.model import RainbowNet
    cfg = copy.copy(RL_CONFIG)
    paths = {"ring": args.replay_dir}
    for bank in ("hof", "ephof"):
        path = Path(f"{args.bank_base}_{bank}")
        if (path / f"{bank}_meta.npz").exists():
            paths[bank] = path
    budget = sample_budget(args.samples, list(paths))
    rng = np.random.default_rng(args.seed)
    partitions = {}
    warnings = []
    for name, path in paths.items():
        if not budget[name]:
            continue
        try:
            partition = load_partition(path, name, rng, budget[name], args.ring_size)
            if partition is not None:
                partitions[name] = partition
            else:
                warnings.append(f"{name} bank has no valid rows")
        except (OSError, ValueError) as error:
            if name == "ring":
                raise
            warnings.append(f"{name} unavailable: {error}")
    results = []
    for path in args.checkpoints:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if int(checkpoint["state_size"]) != int(cfg.state_size):
            raise ValueError(f"{path}: state size differs from current architecture; use matching DQN_FRAME_STACK/code")
        online = RainbowNet(cfg.state_size).cpu().eval()
        target = RainbowNet(cfg.state_size).cpu().eval()
        online.load_state_dict(checkpoint["online_state_dict"])
        target.load_state_dict(checkpoint["target_state_dict"])
        checkpoint_info = {name: checkpoint.get(name) for name in ("frame_count", "learner_frame_count", "training_steps", "optimized_samples", "engine_version")}
        del checkpoint
        results.append({
            "path": str(path.resolve()), **checkpoint_info,
            "partitions": {name: probe_partition(online, target, arrays, cfg, TrainingLoss) for name, (_, arrays) in partitions.items()},
        })
        del online, target
    result = {
        "schema_version": 1, "utc": datetime.now(timezone.utc).isoformat(),
        "device": "cpu", "torch_threads": torch.get_num_threads(), "sample_budget": args.samples,
        "seed": args.seed, "config": {name: getattr(cfg, name) for name in ("gamma", "n_step", "v_min", "v_max", "num_atoms", "c51_target_smoothing")},
        "partitions": {name: metadata for name, (metadata, _) in partitions.items()},
        "warnings": warnings, "caveats": CAVEATS, "checkpoints": results,
    }
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
