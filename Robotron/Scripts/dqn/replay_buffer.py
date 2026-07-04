#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • PRIORITIZED EXPERIENCE REPLAY                                                                ||
# ||  Sum-tree backed proportional PER with per-slot storage (ported from Tempest).                               ||
# ==================================================================================================================
"""Prioritized replay buffer using a sum-tree for O(log N) sampling."""

import os, sys, time, shutil
import numpy as np
import threading

try:
    from .config import RL_CONFIG
except ImportError:
    from config import RL_CONFIG


ACTOR_DQN = 0
ACTOR_EPSILON = 1
ACTOR_EXPERT = 2
ACTOR_KIND_COUNT = 3


class SumTree:
    """Binary sum-tree for efficient proportional sampling in O(log N)."""

    __slots__ = ("capacity", "tree", "data_ptr", "size", "max_priority", "_depth")

    def __init__(self, capacity: int):
        self.capacity = int(capacity)
        self.tree = np.zeros(2 * self.capacity, dtype=np.float64)
        self.data_ptr = 0
        self.size = 0
        self.max_priority = 1.0
        self._depth = int(np.ceil(np.log2(max(2, self.capacity))))

    def _propagate(self, idx: int):
        parent = idx >> 1
        while parent >= 1:
            self.tree[parent] = self.tree[parent * 2] + self.tree[parent * 2 + 1]
            parent >>= 1

    def total(self) -> float:
        return float(self.tree[1])

    def add(self, priority: float) -> int:
        """Add a new entry and return its data index."""
        idx = self.data_ptr
        tree_idx = idx + self.capacity
        self.tree[tree_idx] = float(priority)
        self._propagate(tree_idx)
        self.data_ptr = (self.data_ptr + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)
        if priority > self.max_priority:
            self.max_priority = float(priority)
        return idx

    def update(self, data_idx: int, priority: float):
        tree_idx = data_idx + self.capacity
        self.tree[tree_idx] = float(priority)
        self._propagate(tree_idx)
        if priority > self.max_priority:
            self.max_priority = float(priority)

    def get(self, value: float) -> int:
        """Sample a data index proportional to priority."""
        idx = 1
        while idx < self.capacity:
            left = idx * 2
            if value <= self.tree[left]:
                idx = left
            else:
                value -= self.tree[left]
                idx = left + 1
        return idx - self.capacity

    def batch_get(self, values: np.ndarray) -> np.ndarray:
        """Vectorised batch sampling — all queries traverse the tree in lockstep.

        Instead of a Python loop over batch_size items each doing O(log N)
        scalar traversals, this performs log N numpy-vectorised steps.
        """
        n = len(values)
        indices = np.ones(n, dtype=np.int64)
        remaining = values.astype(np.float64, copy=True)
        cap = self.capacity
        for _ in range(self._depth):
            # Mask: True where index is still an internal node
            mask = indices < cap
            if not mask.any():
                break
            # Safe left-child indices (use 0 for already-resolved leaves)
            left = np.where(mask, indices << 1, 0)
            left_vals = self.tree[left]
            go_right = mask & (remaining > left_vals)
            remaining -= left_vals * go_right
            indices = np.where(mask, left + go_right.astype(np.int64), indices)
        return indices - cap

    def batch_update(self, data_indices: np.ndarray, priorities: np.ndarray):
        """Vectorised batch priority update with deduped parent propagation.

        Sets all leaf priorities at once then walks up the tree one level at
        a time, merging duplicate parents with np.unique at each level.
        """
        tree_idx = data_indices.astype(np.int64) + self.capacity
        self.tree[tree_idx] = priorities.astype(np.float64)
        mx = float(priorities.max())
        if mx > self.max_priority:
            self.max_priority = mx
        # Walk parents upward, deduplicating at each level
        parents = np.unique(tree_idx >> 1)
        while len(parents) > 0 and parents[0] >= 1:
            self.tree[parents] = self.tree[parents * 2] + self.tree[parents * 2 + 1]
            parents = np.unique(parents >> 1)
            parents = parents[parents >= 1]

    def priority(self, data_idx: int) -> float:
        return float(self.tree[data_idx + self.capacity])


class PrioritizedReplayBuffer:
    """Proportional PER backed by a SumTree.

    Stores transitions as flat numpy arrays for fast vectorised sampling.
    Thread-safe via a reentrant lock.
    """

    def __init__(self, capacity: int, state_size: int, alpha: float = 0.6):
        self.capacity = int(capacity)
        self.state_size = int(state_size)
        self.alpha = float(alpha)
        self.lock = threading.Lock()

        # Storage arrays
        self.states      = np.zeros((self.capacity, self.state_size), dtype=np.float32)
        self.next_states = np.zeros((self.capacity, self.state_size), dtype=np.float32)
        self.actions     = np.zeros(self.capacity, dtype=np.int64)
        self.rewards     = np.zeros(self.capacity, dtype=np.float32)
        self.dones       = np.zeros(self.capacity, dtype=np.float32)
        self.horizons    = np.ones(self.capacity, dtype=np.int32)
        self.is_expert   = np.zeros(self.capacity, dtype=np.uint8)
        self.actor_kind  = np.zeros(self.capacity, dtype=np.uint8)
        self.interesting = np.zeros(self.capacity, dtype=np.float32)

        self.tree = SumTree(self.capacity)
        self.size = 0
        self._n_expert = 0          # O(1) expert tracking
        self._n_actor = np.zeros(ACTOR_KIND_COUNT, dtype=np.int64)
        self._n_interesting = 0
        bank_size = int(getattr(RL_CONFIG, "interesting_replay_bank_size", 1_000_000))
        self._interesting_bank = np.full(max(1, bank_size), -1, dtype=np.int64)
        self._interesting_bank_ptr = 0
        self._interesting_bank_count = 0
        self._mmap_dir = None

    @staticmethod
    def actor_kind_from_name(actor: str | None, expert: int = 0) -> int:
        if expert:
            return ACTOR_EXPERT
        a = str(actor or "dqn").lower()
        if a == "expert":
            return ACTOR_EXPERT
        if a == "epsilon":
            return ACTOR_EPSILON
        return ACTOR_DQN

    @staticmethod
    def _progress_bar(label: str, frac: float, width: int = 28):
        frac_clamped = max(0.0, min(1.0, float(frac)))
        filled = int(round(frac_clamped * width))
        bar = "#" * filled + "-" * (width - filled)
        sys.stdout.write(f"\r{label} [{bar}] {frac_clamped * 100.0:5.1f}%")
        sys.stdout.flush()
        if frac_clamped >= 1.0:
            sys.stdout.write("\n")
            sys.stdout.flush()

    @staticmethod
    def _mmap_chunk_rows(arr: np.ndarray, target_mb: int | None = None) -> int:
        """Rows per mmap write chunk, bounded by target megabytes."""
        if arr.ndim <= 0 or arr.shape[0] <= 0:
            return 1
        if target_mb is None:
            target_mb = int(os.environ.get("ROBOTRON_REPLAY_MMAP_CHUNK_MB", "256"))
        target_bytes = max(1, int(target_mb)) * 1024 * 1024
        row_items = int(np.prod(arr.shape[1:])) if arr.ndim > 1 else 1
        row_bytes = max(1, int(arr.dtype.itemsize) * max(1, row_items))
        return max(1, min(int(arr.shape[0]), target_bytes // row_bytes))

    @classmethod
    def _save_npy_memmap(cls, path: str, source, verbose: bool,
                         base_frac: float, span_frac: float):
        """Write a standard .npy file through an on-disk memmap."""
        src = np.asarray(source)
        dst = np.lib.format.open_memmap(path, mode="w+", dtype=src.dtype, shape=src.shape)
        if src.ndim == 0:
            dst[...] = src
            dst.flush()
            del dst
            return

        total = int(src.shape[0])
        if total <= 0:
            dst.flush()
            del dst
            return

        chunk_rows = cls._mmap_chunk_rows(src)
        for start in range(0, total, chunk_rows):
            end = min(total, start + chunk_rows)
            dst[start:end] = src[start:end]
            if verbose:
                frac = base_frac + span_frac * (end / max(1, total))
                cls._progress_bar("  Replay save", frac)
        dst.flush()
        del dst

    def _storage_specs(self) -> dict[str, tuple[str, np.dtype, tuple[int, ...]]]:
        cap = int(self.capacity)
        state_size = int(self.state_size)
        return {
            "states": ("states", np.dtype(np.float32), (cap, state_size)),
            "next_states": ("next_states", np.dtype(np.float32), (cap, state_size)),
            "actions": ("actions", np.dtype(np.int64), (cap,)),
            "rewards": ("rewards", np.dtype(np.float32), (cap,)),
            "dones": ("dones", np.dtype(np.float32), (cap,)),
            "horizons": ("horizons", np.dtype(np.int32), (cap,)),
            "is_expert": ("is_expert", np.dtype(np.uint8), (cap,)),
            "actor_kind": ("actor_kind", np.dtype(np.uint8), (cap,)),
            "interesting": ("interesting", np.dtype(np.float32), (cap,)),
        }

    @staticmethod
    def _is_memmap_array(arr) -> bool:
        return isinstance(arr, np.memmap)

    def _flush_live_mmaps_locked(self):
        for attr, _, _ in self._storage_specs().values():
            arr = getattr(self, attr, None)
            if self._is_memmap_array(arr):
                arr.flush()

    def add(self, state, action: int, reward: float, next_state, done: bool,
            horizon: int = 1, expert: int = 0, priority_hint: float = 0.0,
            interest: float = 0.0, actor_kind: int | None = None):
        with self.lock:
            kind = int(actor_kind) if actor_kind is not None else self.actor_kind_from_name(None, expert)
            kind = max(0, min(ACTOR_KIND_COUNT - 1, kind))
            priority = self.tree.max_priority
            cap_mult = float(getattr(RL_CONFIG, "per_new_priority_cap_multiplier", 0.0))
            mean_pri = 0.0
            if cap_mult > 0.0 and self.size > 0:
                mean_pri = self.tree.total() / max(1, self.size)
                if mean_pri > 0.0:
                    priority = min(priority, mean_pri * cap_mult)
            if priority_hint != 0.0:
                hint_pri = abs(priority_hint) ** self.alpha
                if hint_pri > priority:
                    priority = hint_pri
            if cap_mult > 0.0 and mean_pri > 0.0:
                priority = min(priority, mean_pri * cap_mult)
            priority = max(1e-6, float(priority))
            # If buffer is full, undo the expert flag of the slot being recycled
            if self.tree.size >= self.capacity:
                self._n_expert -= int(self.is_expert[self.tree.data_ptr])
                old_kind = int(self.actor_kind[self.tree.data_ptr])
                if 0 <= old_kind < ACTOR_KIND_COUNT:
                    self._n_actor[old_kind] -= 1
                self._n_interesting -= int(self.interesting[self.tree.data_ptr] > 0.0)
            idx = self.tree.add(priority)
            self.states[idx]      = np.asarray(state, dtype=np.float32)
            self.next_states[idx] = np.asarray(next_state, dtype=np.float32)
            self.actions[idx]     = int(action)
            self.rewards[idx]     = float(reward)
            self.dones[idx]       = 1.0 if done else 0.0
            self.horizons[idx]    = max(1, int(horizon))
            self.is_expert[idx]   = int(expert)
            self.actor_kind[idx]  = np.uint8(kind)
            min_interest = float(getattr(RL_CONFIG, "interesting_replay_min_score", 0.35))
            interest_val = max(0.0, min(1.0, float(interest)))
            if interest_val < min_interest:
                interest_val = 0.0
            elif self.size > 0:
                max_frac = max(0.0, min(1.0, float(getattr(RL_CONFIG, "max_interesting_replay_fraction", 1.0))))
                max_keep = max(1, int(max_frac * max(1, self.size))) if max_frac > 0.0 else 0
                # Hard cap: once the interesting pool is full, admit nothing new.
                # A once-rare "over-cap" escape hatch (admit any score >= 0.95)
                # let a mastered agent's constant deep-wave score bursts flood the
                # pool past 60%, destroying the rare-event upsampling the quota is
                # for.  New rare events still get in continuously as flagged slots
                # recycle out and the count drops back below the cap.
                if max_keep <= 0 or self._n_interesting >= max_keep:
                    interest_val = 0.0
            self.interesting[idx] = interest_val
            self._n_expert += int(expert)
            self._n_actor[kind] += 1
            if interest_val > 0.0:
                self._n_interesting += 1
                self._interesting_bank[self._interesting_bank_ptr] = idx
                self._interesting_bank_ptr = (self._interesting_bank_ptr + 1) % len(self._interesting_bank)
                self._interesting_bank_count = min(self._interesting_bank_count + 1, len(self._interesting_bank))
            self.size = self.tree.size

    def _sample_interesting_indices(self, count: int) -> np.ndarray:
        if count <= 0 or self._n_interesting <= 0 or self._interesting_bank_count <= 0:
            return np.empty(0, dtype=np.int64)
        found = []
        attempts = 0
        max_attempts = max(count * 12, 32)
        bank_n = self._interesting_bank_count
        while len(found) < count and attempts < max_attempts:
            take = min(max((count - len(found)) * 3, 8), bank_n)
            pos = np.random.randint(0, bank_n, size=take)
            idxs = self._interesting_bank[pos]
            valid = idxs[(idxs >= 0) & (idxs < self.size)]
            if valid.size:
                valid = valid[self.interesting[valid] > 0.0]
                if valid.size:
                    scores = self.interesting[valid].astype(np.float64)
                    total = float(scores.sum())
                    if total > 0.0:
                        pick_n = min(count - len(found), valid.size)
                        replace = valid.size < pick_n
                        picks = np.random.choice(valid, size=pick_n, replace=replace, p=scores / total)
                        found.extend(int(x) for x in picks)
            attempts += take
        if not found:
            return np.empty(0, dtype=np.int64)
        return np.asarray(found[:count], dtype=np.int64)

    def _sample_recent_indices(self, count: int) -> np.ndarray:
        if count <= 0 or self.size <= 0:
            return np.empty(0, dtype=np.int64)
        window = max(1, min(int(getattr(RL_CONFIG, "recent_replay_window", 500_000)), self.size))
        offsets = np.random.randint(0, window, size=int(count), dtype=np.int64)
        if self.size < self.capacity:
            newest = self.size - 1
            return newest - offsets
        newest = (self.tree.data_ptr - 1) % self.capacity
        return (newest - offsets) % self.capacity

    def sample(self, batch_size: int, beta: float = 0.4):
        """Sample a prioritised batch. Returns (states, actions, rewards,
        next_states, dones, horizons, is_expert, actor_kind, indices, weights)."""
        with self.lock:
            if self.size < batch_size:
                return None

            total = self.tree.total()
            if total <= 0:
                return None

            frac = max(0.0, min(0.75, float(getattr(RL_CONFIG, "interesting_replay_fraction", 0.0))))
            recent_frac = max(0.0, min(0.75, float(getattr(RL_CONFIG, "recent_replay_fraction", 0.0))))
            if frac + recent_frac > 0.90:
                scale = 0.90 / (frac + recent_frac)
                frac *= scale
                recent_frac *= scale
            interesting_count = min(batch_size - 1, int(round(batch_size * frac))) if frac > 0.0 else 0
            interesting_indices = self._sample_interesting_indices(interesting_count)
            recent_count = min(batch_size - int(interesting_indices.size) - 1, int(round(batch_size * recent_frac))) if recent_frac > 0.0 else 0
            recent_indices = self._sample_recent_indices(recent_count)
            per_count = batch_size - int(interesting_indices.size) - int(recent_indices.size)

            # Stratified sampling — one uniform draw per segment (vectorised)
            segment = total / max(1, per_count)
            lows = np.arange(per_count, dtype=np.float64) * segment
            highs = lows + segment
            values = np.random.uniform(lows, highs)
            per_indices = self.tree.batch_get(values) if per_count > 0 else np.empty(0, dtype=np.int64)
            if per_indices.size:
                np.clip(per_indices, 0, self.size - 1, out=per_indices)
            indices = np.concatenate([per_indices, interesting_indices, recent_indices])

            # Gather priorities in one vectorised read
            priorities = np.maximum(1e-10, self.tree.tree[indices + self.tree.capacity])

            # Importance-sampling weights
            probs = priorities / total
            weights = (self.size * probs) ** (-beta)
            weights /= weights.max()

            return (
                self.states[indices],
                self.actions[indices],
                self.rewards[indices],
                self.next_states[indices],
                self.dones[indices],
                self.horizons[indices],
                self.is_expert[indices],
                self.actor_kind[indices],
                indices,
                weights.astype(np.float32),
            )

    def update_priorities(self, indices, td_errors):
        """Update priorities based on TD errors (fully vectorised)."""
        with self.lock:
            new_p = (np.abs(td_errors.astype(np.float64)) + 1e-6) ** self.alpha
            self.tree.batch_update(np.asarray(indices, dtype=np.int64), new_p)

    def boost_priorities(self, indices, factor: float):
        """Multiply existing priorities of the given indices by *factor*.

        Used for pre-death lookback: frames leading up to a death get their
        PER priority boosted so they are sampled more often.
        """
        if factor <= 1.0 or len(indices) == 0:
            return
        with self.lock:
            idxs = np.asarray(indices, dtype=np.int64)
            idxs = idxs[(idxs >= 0) & (idxs < self.size)]
            if idxs.size <= 0:
                return
            idxs = np.unique(idxs)
            tree_idx = idxs + self.tree.capacity
            boosted = self.tree.tree[tree_idx] * float(factor)
            self.tree.batch_update(idxs, boosted)

    def apply_pre_death_penalty(self, indices):
        """Add danger-weighted negative reward to recent learner frames before death.

        Priority makes fatal lead-up frames more visible, but reward is what tells
        the Bellman target those movement choices were bad.  By default this skips
        expert transitions so demonstrations do not become internally contradictory.
        """
        if len(indices) == 0:
            return 0
        cfg = RL_CONFIG
        lookback = max(0, int(getattr(cfg, "pre_death_reward_lookback", 0)))
        base = max(0.0, float(getattr(cfg, "pre_death_base_penalty", 0.0)))
        danger_scale = max(0.0, float(getattr(cfg, "pre_death_danger_penalty", 0.0)))
        max_penalty = max(0.0, float(getattr(cfg, "pre_death_max_penalty", 0.0)))
        if lookback <= 0 or max_penalty <= 0.0 or (base <= 0.0 and danger_scale <= 0.0):
            return 0

        with self.lock:
            idxs = np.asarray(list(indices)[-lookback:], dtype=np.int64)
            idxs = idxs[(idxs >= 0) & (idxs < self.size)]
            if idxs.size <= 0:
                return 0
            if not bool(getattr(cfg, "pre_death_penalize_expert", False)):
                idxs = idxs[self.is_expert[idxs] == 0]
                if idxs.size <= 0:
                    return 0

            enemy_start = int(getattr(cfg, "global_features", 40))
            enemy_count = int(getattr(cfg, "enemy_token_count", 96))
            enemy_features = int(getattr(cfg, "enemy_token_features", 10))
            danger = np.zeros(idxs.size, dtype=np.float32)
            try:
                rows = self.states[
                    idxs,
                    enemy_start:enemy_start + enemy_count * enemy_features,
                ].reshape(idxs.size, enemy_count, enemy_features)
                present = rows[:, :, 0] > 0.5
                dist = np.clip(rows[:, :, 3], 0.0, 1.0)
                threat = np.clip(rows[:, :, 6], 0.0, 1.0)
                ttc = np.clip(rows[:, :, 8], 0.0, 1.0) if enemy_features > 8 else np.ones_like(dist)
                dangerous = np.ones_like(present, dtype=bool)
                if enemy_features > 9:
                    type_id = np.rint(np.clip(rows[:, :, 9], 0.0, 1.0) * 8.0).astype(np.int32)
                    dangerous = type_id != 7
                cue = np.maximum((1.0 - dist) * threat, (1.0 - dist) * (1.0 - ttc))
                cue = np.where(present & dangerous, cue, 0.0)
                danger = np.nanmax(cue, axis=1).astype(np.float32)
            except Exception:
                danger.fill(0.0)
            danger = np.nan_to_num(danger, nan=0.0, posinf=1.0, neginf=0.0)
            danger = np.clip(danger, 0.0, 1.0)

            min_danger = max(0.0, min(0.95, float(getattr(cfg, "pre_death_min_danger", 0.15))))
            danger = np.clip((danger - min_danger) / max(1e-6, 1.0 - min_danger), 0.0, 1.0)
            temporal = np.linspace(0.35, 1.0, idxs.size, dtype=np.float32)
            penalties = np.minimum(max_penalty, (base + danger_scale * danger) * temporal)
            self.rewards[idxs] -= penalties.astype(np.float32)
            return int(idxs.size)

    def _append_interesting_bank_locked(self, idxs: np.ndarray):
        if idxs.size <= 0:
            return
        bank_len = len(self._interesting_bank)
        if idxs.size >= bank_len:
            self._interesting_bank[:] = idxs[-bank_len:]
            self._interesting_bank_ptr = 0
            self._interesting_bank_count = bank_len
            return
        end = self._interesting_bank_ptr + idxs.size
        if end <= bank_len:
            self._interesting_bank[self._interesting_bank_ptr:end] = idxs
        else:
            first = bank_len - self._interesting_bank_ptr
            self._interesting_bank[self._interesting_bank_ptr:] = idxs[:first]
            self._interesting_bank[:end - bank_len] = idxs[first:]
        self._interesting_bank_ptr = end % bank_len
        self._interesting_bank_count = min(self._interesting_bank_count + int(idxs.size), bank_len)

    def mark_interesting(self, indices, interest: float):
        """Mark existing replay entries as interesting for quota sampling."""
        interest_val = max(0.0, min(1.0, float(interest)))
        min_interest = float(getattr(RL_CONFIG, "interesting_replay_min_score", 0.35))
        if interest_val < min_interest or len(indices) == 0:
            return
        with self.lock:
            idxs = np.asarray(indices, dtype=np.int64)
            idxs = idxs[(idxs >= 0) & (idxs < self.size)]
            if idxs.size <= 0:
                return
            idxs = np.unique(idxs)
            already = self.interesting[idxs] > 0.0
            # Upgrading the score of slots that are already interesting never
            # grows the pool, so always allow those.
            upgrade_idx = idxs[already]
            new_idx = idxs[~already]
            # New flags must respect the hard cap so elite/learner episode tails
            # (marked in bulk at score 1.0) cannot push the interesting pool past
            # max_interesting_replay_fraction — the same leak that add() guards.
            if new_idx.size > 0:
                max_frac = max(0.0, min(1.0, float(getattr(RL_CONFIG, "max_interesting_replay_fraction", 1.0))))
                max_keep = max(1, int(max_frac * max(1, self.size))) if max_frac > 0.0 else 0
                room = max(0, max_keep - self._n_interesting)
                if new_idx.size > room:
                    new_idx = new_idx[:room]
            if upgrade_idx.size > 0:
                self.interesting[upgrade_idx] = np.maximum(self.interesting[upgrade_idx], interest_val)
            if new_idx.size > 0:
                self.interesting[new_idx] = interest_val
                self._n_interesting += int(new_idx.size)
            touched = np.concatenate([upgrade_idx, new_idx]) if new_idx.size else upgrade_idx
            if touched.size > 0:
                self._append_interesting_bank_locked(touched)

    def __len__(self):
        return self.size

    def get_partition_stats(self):
        """Return buffer statistics (O(1) via tracked counter)."""
        with self.lock:
            n_exp = self._n_expert
            n_dqn = self.size - n_exp
            return {
                "total_size": self.size,
                "total_capacity": self.capacity,
                "dqn": n_dqn,
                "expert": n_exp,
                "actor_dqn": int(self._n_actor[ACTOR_DQN]),
                "actor_epsilon": int(self._n_actor[ACTOR_EPSILON]),
                "actor_expert": int(self._n_actor[ACTOR_EXPERT]),
                "frac_dqn": n_dqn / max(1, self.size),
                "frac_expert": n_exp / max(1, self.size),
                "frac_actor_dqn": int(self._n_actor[ACTOR_DQN]) / max(1, self.size),
                "frac_actor_epsilon": int(self._n_actor[ACTOR_EPSILON]) / max(1, self.size),
                "frac_actor_expert": int(self._n_actor[ACTOR_EXPERT]) / max(1, self.size),
                "interesting": self._n_interesting,
                "frac_interesting": self._n_interesting / max(1, self.size),
            }

    # ── Persistence ─────────────────────────────────────────────────────

    def save(self, filepath: str, verbose: bool = True):
        """Save the full replay buffer as individual .npy files in a directory."""
        abs_path = os.path.abspath(filepath)
        if self._mmap_dir is not None and os.path.abspath(self._mmap_dir) == abs_path:
            with self.lock:
                t0 = time.time()
                n = int(self.size)
                if verbose:
                    print(f"  Flushing mmap replay buffer ({n:,} transitions)...")
                    self._progress_bar("  Replay flush", 0.10)
                self._flush_live_mmaps_locked()
                if verbose:
                    self._progress_bar("  Replay flush", 0.55)
                priorities_path = os.path.join(abs_path, "priorities.npy")
                priorities = np.lib.format.open_memmap(
                    priorities_path,
                    mode="r+",
                    dtype=np.float64,
                    shape=(self.capacity,),
                )
                priorities[:n] = self.tree.tree[self.tree.capacity:self.tree.capacity + n]
                if n < self.capacity:
                    priorities[n:] = 0.0
                priorities.flush()
                del priorities
                if verbose:
                    self._progress_bar("  Replay flush", 0.82)
                meta = np.array([self.tree.data_ptr, n, self.tree.max_priority])
                meta_path = os.path.join(abs_path, "_meta.npy")
                tmp_meta = meta_path + ".tmp.npy"
                np.save(tmp_meta, meta)
                os.replace(tmp_meta, meta_path)
                if verbose:
                    self._progress_bar("  Replay flush", 1.0)
                    elapsed = time.time() - t0
                    print(f"  Replay mmap flushed in {elapsed:.1f}s")
            return

        t0 = time.time()
        tmp_dir = filepath + ".tmp"
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        os.makedirs(tmp_dir, exist_ok=True)

        total_bytes = 0
        with self.lock:
            if self.size == 0:
                if verbose:
                    print("  Replay buffer is empty — nothing to save.")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return

            n = self.size
            if verbose:
                print(f"  Saving replay buffer ({n:,} transitions, mmap .npy)...")
                self._progress_bar("  Replay save", 0.05)

            arrays = {
                "states":      self.states[:n],
                "next_states": self.next_states[:n],
                "actions":     self.actions[:n],
                "rewards":     self.rewards[:n],
                "dones":       self.dones[:n],
                "horizons":    self.horizons[:n],
                "is_expert":   self.is_expert[:n],
                "actor_kind":  self.actor_kind[:n],
                "interesting": self.interesting[:n],
                "priorities":  self.tree.tree[self.tree.capacity:self.tree.capacity + n],
            }
            total_bytes = sum(a.nbytes for a in arrays.values())
            names = list(arrays.keys())
            for i, name in enumerate(names):
                base = 0.05 + 0.90 * (i / len(names))
                span = 0.90 / len(names)
                self._save_npy_memmap(
                    os.path.join(tmp_dir, f"{name}.npy"),
                    arrays[name],
                    verbose,
                    base,
                    span,
                )
            meta = np.array([self.tree.data_ptr, n, self.tree.max_priority])
            np.save(os.path.join(tmp_dir, "_meta.npy"), meta)
            if verbose:
                self._progress_bar("  Replay save", 0.97)

        # Atomic rename
        if os.path.exists(filepath):
            if os.path.isdir(filepath):
                shutil.rmtree(filepath, ignore_errors=True)
            else:
                os.remove(filepath)
        os.rename(tmp_dir, filepath)
        if verbose:
            self._progress_bar("  Replay save", 1.0)

        elapsed = time.time() - t0
        mb = total_bytes / (1024 * 1024)
        if verbose:
            print(f"  Replay buffer saved: {mb:.0f} MB in {elapsed:.1f}s")

    def _load_directory(self, dirpath: str, verbose: bool = True) -> bool:
        """Load replay buffer from a directory of .npy files."""
        meta_path = os.path.join(dirpath, "_meta.npy")
        states_path = os.path.join(dirpath, "states.npy")
        if not os.path.isfile(meta_path) or not os.path.isfile(states_path):
            return False

        if verbose:
            print(f"  Loading replay buffer (directory mmap format) from {dirpath}...")
        t0 = time.time()
        if verbose:
            self._progress_bar("  Replay load", 0.05)

        try:
            meta = np.load(meta_path)
            data_ptr = int(meta[0])
            saved_n = int(meta[1])
            max_priority = float(meta[2])
        except Exception as e:
            print(f"  Failed to read replay meta: {e}")
            return False

        if self._try_adopt_mmap_directory(dirpath, data_ptr, saved_n, max_priority, t0, verbose):
            return True

        # Load arrays
        names = ["states", "next_states", "actions", "rewards", "dones", "horizons", "is_expert", "priorities"]
        arch = {}
        for i, name in enumerate(names):
            fpath = os.path.join(dirpath, f"{name}.npy")
            if not os.path.isfile(fpath):
                print(f"  Missing array file: {name}.npy")
                return False
            arch[name] = np.load(fpath, mmap_mode="r")
            if verbose:
                frac = 0.05 + 0.30 * ((i + 1) / len(names))
                self._progress_bar("  Replay load", frac)
        interesting_path = os.path.join(dirpath, "interesting.npy")
        if os.path.isfile(interesting_path):
            arch["interesting"] = np.load(interesting_path, mmap_mode="r")
        actor_kind_path = os.path.join(dirpath, "actor_kind.npy")
        if os.path.isfile(actor_kind_path):
            arch["actor_kind"] = np.load(actor_kind_path, mmap_mode="r")

        return self._restore_from_arrays(arch, data_ptr, max_priority, t0, dirpath, verbose, saved_n=saved_n)

    def _try_adopt_mmap_directory(self, dirpath: str, data_ptr: int, saved_n: int,
                                  max_priority: float, t0: float, verbose: bool) -> bool:
        """Use existing full-size .npy files as the live replay storage."""
        n = max(0, min(int(saved_n), self.capacity))
        if n <= 0:
            return False
        specs = self._storage_specs()
        mapped = {}
        try:
            for name, (_, dtype, expected_shape) in specs.items():
                path = os.path.join(dirpath, f"{name}.npy")
                if not os.path.isfile(path):
                    return False
                arr = np.load(path, mmap_mode="r+")
                if arr.dtype != dtype or arr.shape != expected_shape:
                    return False
                mapped[name] = arr
            priorities_path = os.path.join(dirpath, "priorities.npy")
            if not os.path.isfile(priorities_path):
                return False
            priorities = np.load(priorities_path, mmap_mode="r")
            if priorities.dtype != np.dtype(np.float64) or priorities.shape != (self.capacity,):
                return False
        except Exception as e:
            if verbose:
                print(f"  Replay mmap adoption skipped: {e}")
            return False

        if verbose:
            self._progress_bar("  Replay load", 0.40)

        with self.lock:
            for name, (attr, _, _) in specs.items():
                setattr(self, attr, mapped[name])

            self.tree = SumTree(self.capacity)
            self.tree.size = n
            self.tree.data_ptr = data_ptr if 0 <= int(data_ptr) < self.capacity else n % self.capacity
            self.tree.max_priority = max_priority
            self.tree.tree[self.tree.capacity:self.tree.capacity + n] = np.asarray(priorities[:n], dtype=np.float64)
            if n < self.capacity:
                self.tree.tree[self.tree.capacity + n:] = 0.0

            total_nodes = max(1, self.tree.capacity - 1)
            update_every = max(1, total_nodes // 64)
            for i in range(self.tree.capacity - 1, 0, -1):
                self.tree.tree[i] = self.tree.tree[2 * i] + self.tree.tree[2 * i + 1]
                if verbose and ((self.tree.capacity - i) % update_every == 0):
                    rebuilt = self.tree.capacity - i
                    frac = 0.40 + (0.50 * (rebuilt / total_nodes))
                    self._progress_bar("  Replay load", frac)

            self.size = n
            self._n_expert = int(self.is_expert[:n].sum())
            self._n_actor[:] = 0
            counts = np.bincount(self.actor_kind[:n].astype(np.int64), minlength=ACTOR_KIND_COUNT)
            self._n_actor[:ACTOR_KIND_COUNT] = counts[:ACTOR_KIND_COUNT]
            self._sanitize_interesting_after_load_locked(n, verbose)
            self._rebuild_interesting_bank_locked(n)
            self._mmap_dir = os.path.abspath(dirpath)

        elapsed = time.time() - t0
        if verbose:
            self._progress_bar("  Replay load", 1.0)
            print(f"  Replay buffer mmap mapped: {n:,} transitions in {elapsed:.1f}s")
        return True

    def _load_npz(self, filepath: str, verbose: bool = True) -> bool:
        """Load replay buffer from a legacy .npz file."""
        if not os.path.isfile(filepath):
            return False

        if verbose:
            print(f"  Loading replay buffer (legacy npz) from {filepath}...")
        t0 = time.time()
        if verbose:
            self._progress_bar("  Replay load", 0.05)

        try:
            arch = np.load(filepath, allow_pickle=False)
        except Exception as e:
            print(f"  Failed to read replay buffer: {e}")
            return False
        if verbose:
            self._progress_bar("  Replay load", 0.35)

        data_ptr = int(arch["data_ptr"]) if "data_ptr" in arch else 0
        max_priority = float(arch["max_priority"]) if "max_priority" in arch else 1.0
        return self._restore_from_arrays(dict(arch), data_ptr, max_priority, t0, filepath, verbose)

    def _restore_from_arrays(self, arch: dict, data_ptr: int, max_priority: float,
                              t0: float, source_path: str, verbose: bool,
                              saved_n: int | None = None) -> bool:
        """Common restore logic for both directory and npz formats."""
        stored_n = len(arch["states"])
        n = stored_n if saved_n is None else max(0, min(int(saved_n), stored_n))
        if n == 0:
            print("  Replay buffer file is empty.")
            return False

        saved_state_size = arch["states"].shape[1]
        if saved_state_size != self.state_size:
            print(f"  State size mismatch: saved={saved_state_size}, expected={self.state_size}")
            return False

        if n > self.capacity:
            print(f"  Saved buffer ({n:,}) exceeds capacity ({self.capacity:,}), truncating to most recent.")
            offset = n - self.capacity
            n = self.capacity
        else:
            offset = 0
        if verbose:
            self._progress_bar("  Replay load", 0.40)

        with self.lock:
            if verbose:
                self._progress_bar("  Replay load", 0.45)

            self.states[:n]      = arch["states"][offset:offset + n]
            self.next_states[:n] = arch["next_states"][offset:offset + n]
            self.actions[:n]     = arch["actions"][offset:offset + n]
            self.rewards[:n]     = arch["rewards"][offset:offset + n]
            self.dones[:n]       = arch["dones"][offset:offset + n]
            self.horizons[:n]    = arch["horizons"][offset:offset + n]
            self.is_expert[:n]   = arch["is_expert"][offset:offset + n]
            if "actor_kind" in arch:
                self.actor_kind[:n] = np.clip(
                    arch["actor_kind"][offset:offset + n], 0, ACTOR_KIND_COUNT - 1
                ).astype(np.uint8, copy=False)
            else:
                self.actor_kind[:n] = np.where(self.is_expert[:n] > 0, ACTOR_EXPERT, ACTOR_DQN).astype(np.uint8)
            if "interesting" in arch:
                self.interesting[:n] = arch["interesting"][offset:offset + n]
            else:
                self.interesting[:n] = 0.0
            if n < self.capacity:
                self.actor_kind[n:] = 0
                self.interesting[n:] = 0.0
            if verbose:
                self._progress_bar("  Replay load", 0.62)

            priorities = np.asarray(arch["priorities"][offset:offset + n], dtype=np.float64)
            self.tree.size = n
            self.tree.data_ptr = data_ptr if offset == 0 else n % self.capacity
            self.tree.max_priority = max_priority

            self.tree.tree[self.tree.capacity:self.tree.capacity + n] = priorities
            if n < self.capacity:
                self.tree.tree[self.tree.capacity + n:] = 0.0

            total_nodes = max(1, self.tree.capacity - 1)
            update_every = max(1, total_nodes // 64)
            for i in range(self.tree.capacity - 1, 0, -1):
                self.tree.tree[i] = self.tree.tree[2 * i] + self.tree.tree[2 * i + 1]
                if verbose and ((self.tree.capacity - i) % update_every == 0):
                    rebuilt = self.tree.capacity - i
                    frac = 0.62 + (0.33 * (rebuilt / total_nodes))
                    self._progress_bar("  Replay load", frac)

            self.size = n
            self._n_expert = int(self.is_expert[:n].sum())
            self._n_actor[:] = 0
            counts = np.bincount(self.actor_kind[:n].astype(np.int64), minlength=ACTOR_KIND_COUNT)
            self._n_actor[:ACTOR_KIND_COUNT] = counts[:ACTOR_KIND_COUNT]
            self._sanitize_interesting_after_load_locked(n, verbose)
            self._rebuild_interesting_bank_locked(n)

        elapsed = time.time() - t0
        if verbose:
            self._progress_bar("  Replay load", 1.0)
            print(f"  Replay buffer loaded: {n:,} transitions in {elapsed:.1f}s")
        return True

    def _sanitize_interesting_after_load_locked(self, n: int, verbose: bool = True):
        """Prune legacy broad-interest flags after loading old replay buffers.

        Older runs treated late-wave frames as interesting by themselves, which
        can mark almost the entire 10M buffer and make the interesting replay
        quota behave like another generic sampler.  Keep terminal, scoring, and
        high-priority surprises, then cap the partition so it remains sparse.
        """
        if n <= 0:
            return
        max_frac = max(0.0, min(1.0, float(getattr(RL_CONFIG, "max_interesting_replay_fraction", 0.30))))
        if max_frac <= 0.0:
            self.interesting[:n] = 0.0
            return
        current = int(np.count_nonzero(self.interesting[:n] > 0.0))
        max_keep = max(1, int(n * max_frac))
        if current <= max_keep:
            return

        rewards = self.rewards[:n].astype(np.float32, copy=False)
        dones = self.dones[:n] > 0.5
        priorities = self.tree.tree[self.tree.capacity:self.tree.capacity + n]
        old_interest = np.maximum(0.0, self.interesting[:n].astype(np.float32, copy=False))

        pos_keep = float(getattr(RL_CONFIG, "legacy_interest_positive_reward", 0.75))
        positive_score = np.clip(np.maximum(rewards, 0.0) / max(1e-6, pos_keep * 4.0), 0.0, 1.0)
        big_abs_reward = np.clip(np.abs(rewards) / max(1e-6, float(getattr(RL_CONFIG, "reward_clip", 30.0)) * 0.5), 0.0, 1.0)
        if priorities.size > 0 and np.isfinite(priorities).any():
            finite = priorities[np.isfinite(priorities) & (priorities > 0.0)]
            if finite.size > 0:
                scale = float(np.quantile(finite, 0.99))
            else:
                scale = 1.0
        else:
            scale = 1.0
        priority_score = np.clip(priorities / max(1e-9, scale), 0.0, 1.0).astype(np.float32, copy=False)

        rare_score = np.maximum.reduce([
            dones.astype(np.float32),
            positive_score.astype(np.float32),
            0.60 * big_abs_reward.astype(np.float32),
            0.55 * priority_score,
            0.05 * np.clip(old_interest, 0.0, 1.0),
        ])
        candidate = rare_score > 0.0
        if int(candidate.sum()) > max_keep:
            cand_idx = np.flatnonzero(candidate)
            scores = rare_score[cand_idx]
            top_rel = np.argpartition(scores, -max_keep)[-max_keep:]
            keep_idx = cand_idx[top_rel]
        else:
            keep_idx = np.flatnonzero(candidate)

        min_interest = float(getattr(RL_CONFIG, "interesting_replay_min_score", 0.55))
        self.interesting[:n] = 0.0
        if keep_idx.size > 0:
            self.interesting[keep_idx] = np.maximum(min_interest, np.minimum(1.0, rare_score[keep_idx]))
        if verbose:
            print(
                f"  Pruned legacy interesting flags: {current:,} -> "
                f"{int(np.count_nonzero(self.interesting[:n] > 0.0)):,}"
            )

    def _rebuild_interesting_bank_locked(self, n: int):
        interesting = np.nonzero(self.interesting[:n] > 0.0)[0]
        self._n_interesting = int(interesting.size)
        self._interesting_bank.fill(-1)
        if interesting.size <= 0:
            self._interesting_bank_ptr = 0
            self._interesting_bank_count = 0
            return
        bank_n = min(len(self._interesting_bank), int(interesting.size))
        self._interesting_bank[:bank_n] = interesting[-bank_n:].astype(np.int64)
        self._interesting_bank_count = bank_n
        self._interesting_bank_ptr = bank_n % len(self._interesting_bank)

    def load(self, filepath: str, verbose: bool = True) -> bool:
        """Load replay buffer: tries directory format first, then falls back to legacy .npz."""
        # Try directory format (new fast path)
        if os.path.isdir(filepath):
            return self._load_directory(filepath, verbose)
        # Try .npz at the given path
        if os.path.isfile(filepath):
            return self._load_npz(filepath, verbose)
        # Try deriving the directory path from a .npz path or vice versa
        if filepath.endswith(".npz"):
            dir_path = filepath[:-4]
            if os.path.isdir(dir_path):
                return self._load_directory(dir_path, verbose)
        else:
            npz_path = filepath + ".npz"
            if os.path.isfile(npz_path):
                return self._load_npz(npz_path, verbose)
        return False

    def flush(self):
        """Clear the entire replay buffer."""
        with self.lock:
            self.tree = SumTree(self.capacity)
            self.size = 0
            self._n_expert = 0
            self._n_actor.fill(0)
            self._n_interesting = 0
            self._interesting_bank.fill(-1)
            self._interesting_bank_ptr = 0
            self._interesting_bank_count = 0
            # Zero the storage arrays so stale data can't leak
            self.states.fill(0)
            self.next_states.fill(0)
            self.actions.fill(0)
            self.rewards.fill(0)
            self.dones.fill(0)
            self.horizons.fill(1)
            self.is_expert.fill(0)
            self.actor_kind.fill(0)
            self.interesting.fill(0)
        print("  Replay buffer flushed.")
