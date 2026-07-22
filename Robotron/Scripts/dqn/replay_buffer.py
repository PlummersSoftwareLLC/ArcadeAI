#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • PRIORITIZED EXPERIENCE REPLAY                                                                ||
# ||  Sum-tree backed proportional PER with per-slot storage (ported from Tempest).                               ||
# ==================================================================================================================
"""Prioritized replay buffer using a sum-tree for O(log N) sampling."""

import os, sys, time, shutil
import numpy as np
import threading
from collections import deque

try:
    from .config import RL_CONFIG, decode_token_types, TYPE_ONEHOT_OFFSET, TYPE_CLASS_COUNT
except ImportError:
    from config import RL_CONFIG, decode_token_types, TYPE_ONEHOT_OFFSET, TYPE_CLASS_COUNT


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
        # fp16 ring states (2026-07-18): halves state memory so the ring can
        # deepen to 18M within /dev/shm.  Features are normalized [-1,1] where
        # fp16 keeps ~3 decimal digits — ample.  sample() upcasts gathered
        # batches to fp32 before they reach torch; the HOF stays fp32.
        self.states      = np.zeros((self.capacity, self.state_size), dtype=np.float16)
        self.next_states = np.zeros((self.capacity, self.state_size), dtype=np.float16)
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
        # HOF persists on the model DISK even when the ring lives in tmpfs.
        # None -> derive from the ring path at save/load time (legacy behavior).
        self._hof_dir = None

        # ── hall-of-fame partition (permanent retention, 2026-07) ────────
        # COPIES of the best episodes ever seen — never evicted by time,
        # replaced only by better episodes (min-heap by game score).  This is
        # the only store that survives ring turnover, so it is the only thing
        # that can keep peak-play Bellman targets grounded after the sliding
        # window has forgotten the peak.  Deliberately NOT cleared by clear().
        self._hof_enabled = bool(getattr(RL_CONFIG, "hof_enabled", False))
        self.hof_ep_count = 0
        self.hof_total = 0
        if self._hof_enabled:
            self._hof_max_eps = max(1, int(getattr(RL_CONFIG, "hof_max_episodes", 192)))
            self._hof_stride = max(64, int(getattr(RL_CONFIG, "hof_episode_stride", 1536)))
            hof_slots = self._hof_max_eps * self._hof_stride
            self.hof_states      = np.zeros((hof_slots, self.state_size), dtype=np.float32)
            self.hof_next_states = np.zeros((hof_slots, self.state_size), dtype=np.float32)
            self.hof_actions     = np.zeros(hof_slots, dtype=np.int64)
            self.hof_rewards     = np.zeros(hof_slots, dtype=np.float32)
            self.hof_dones       = np.zeros(hof_slots, dtype=np.float32)
            self.hof_horizons    = np.ones(hof_slots, dtype=np.int32)
            self.hof_is_expert   = np.zeros(hof_slots, dtype=np.uint8)
            self.hof_actor_kind  = np.zeros(hof_slots, dtype=np.uint8)
            self.hof_ep_score    = np.full(self._hof_max_eps, -np.inf, dtype=np.float64)
            self.hof_ep_len      = np.zeros(self._hof_max_eps, dtype=np.int32)
            self.hof_ep_game     = np.full(self._hof_max_eps, -1, dtype=np.int64)
            self.hof_ep_level    = np.zeros(self._hof_max_eps, dtype=np.int32)
            self._hof_flat       = np.empty(0, dtype=np.int64)

        # ── EpHOF: episode (per-life) hall of fame (2026-07) ─────────────
        # Same permanence contract as the game HOF, but admission is keyed
        # by score earned within a single life.  Best lives cluster at the
        # deepest waves — the state distribution the ring is thinnest on.
        self._ephof_dir = None
        self._ephof_enabled = bool(getattr(RL_CONFIG, "ephof_enabled", False))
        self.ephof_ep_count = 0
        self.ephof_total = 0
        if self._ephof_enabled:
            self._ephof_max_eps = max(1, int(getattr(RL_CONFIG, "ephof_max_episodes", 192)))
            self._ephof_stride = max(64, int(getattr(RL_CONFIG, "ephof_episode_stride", 2048)))
            ephof_slots = self._ephof_max_eps * self._ephof_stride
            self.ephof_states      = np.zeros((ephof_slots, self.state_size), dtype=np.float32)
            self.ephof_next_states = np.zeros((ephof_slots, self.state_size), dtype=np.float32)
            self.ephof_actions     = np.zeros(ephof_slots, dtype=np.int64)
            self.ephof_rewards     = np.zeros(ephof_slots, dtype=np.float32)
            self.ephof_dones       = np.zeros(ephof_slots, dtype=np.float32)
            self.ephof_horizons    = np.ones(ephof_slots, dtype=np.int32)
            self.ephof_is_expert   = np.zeros(ephof_slots, dtype=np.uint8)
            self.ephof_actor_kind  = np.zeros(ephof_slots, dtype=np.uint8)
            self.ephof_ep_score    = np.full(self._ephof_max_eps, -np.inf, dtype=np.float64)
            self.ephof_ep_len      = np.zeros(self._ephof_max_eps, dtype=np.int32)
            self.ephof_ep_game     = np.full(self._ephof_max_eps, -1, dtype=np.int64)
            self.ephof_ep_level    = np.zeros(self._ephof_max_eps, dtype=np.int32)
            self._ephof_flat       = np.empty(0, dtype=np.int64)
        # ── Bank health (2026-07-22 post-mortem) ─────────────────────────
        # Two clocks per bank, deliberately distinct:
        #  * last NORMAL admission (beat-the-minimum) arms BAR RELIEF — a
        #    bank whose bar has outrun reachable play stops admitting and
        #    must decay its bar toward what current play actually produces;
        #  * last admission of ANY kind (normal or relief) drives the
        #    QUOTA STALENESS decay — a bank that is refreshing, even via
        #    relief, has earned its batch share; only a truly frozen one
        #    surrenders quota.
        # Clocks are in ring-adds (one capacity = one ring turnover).
        self._adds_total = 0
        self._hof_last_admit_add = 0
        self._hof_last_normal_admit_add = 0
        self._ephof_last_admit_add = 0
        self._ephof_last_normal_admit_add = 0
        self._hof_recent_offers = deque(maxlen=512)
        self._ephof_recent_offers = deque(maxlen=512)
        # EpHOF sentinel indices start past the game-HOF sentinel span so the
        # two banks can never alias in update_priorities' >= capacity filter.
        self._ephof_base = self.capacity + (
            self._hof_max_eps * self._hof_stride if self._hof_enabled else 0)

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
            "states": ("states", np.dtype(np.float16), (cap, state_size)),
            "next_states": ("next_states", np.dtype(np.float16), (cap, state_size)),
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
            self._adds_total += 1   # bank starvation/staleness clock
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

    def clear(self):
        """Wipe all transitions in place (collapse-watchdog recovery).

        Resets the priority tree and bookkeeping so the buffer refills from
        scratch. The storage arrays need no scrubbing: with tree.size back to
        zero every slot is overwritten by add() before sampling can reach it,
        and the recycle-decrement path is guarded by tree.size >= capacity.
        After a clear, train_step()'s min_replay_to_train gate holds training
        until enough fresh experience accumulates.

        The hall-of-fame partition is deliberately NOT cleared: it holds the
        best play ever seen and must survive collapse-recovery wipes — that
        permanence is its entire reason to exist.
        """
        with self.lock:
            self.tree.tree[:] = 0.0
            self.tree.data_ptr = 0
            self.tree.size = 0
            self.tree.max_priority = 1.0
            self.size = 0
            self._n_expert = 0
            self._n_actor[:] = 0
            self._n_interesting = 0
            self._interesting_bank[:] = -1
            self._interesting_bank_ptr = 0
            self._interesting_bank_count = 0

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

    @staticmethod
    def _bank_span(idxs: np.ndarray, stride: int) -> np.ndarray:
        """Strided span of the WHOLE episode (first frame through terminal)
        rather than the death-tail (2026-07-22 post-mortem): banks must
        enshrine reachable mid-episode competence, not only the sequences
        that end in death.  Endpoints are always kept — the terminal row
        grounds the value function."""
        n = int(idxs.size)
        if n <= stride:
            return idxs
        sel = np.unique(np.linspace(0, n - 1, stride).round().astype(np.int64))
        return idxs[sel]

    def _bank_admit(self, bank: str, indices, score: float, floor: float,
                    per_game_cap: int, stride: int, max_eps: int,
                    game_uid: int, level: int) -> bool:
        """Shared admission engine for the 'hof' and 'ephof' banks.

        Admission is ABSOLUTE (static floor + replace-the-minimum once
        full), never the rolling elite gate — a decline must not certify
        its own play.  Two escapes from the pure ratchet, both from the
        2026-07-22 collapse post-mortem:
          * per-game dedup — a game at its slot cap may only supplant its
            own weakest entry, so no single marathon can colonize the bank;
          * bar relief — when no NORMAL admission has occurred for a full
            ring turnover, the bar has outrun reachable play; candidates at
            or above the relief percentile of recent offers may replace the
            global minimum even without beating it, backfilling the bank
            with reachable lives until normal churn resumes.
        An admission counts as 'normal' only if it beat the global minimum
        (or filled an empty slot): same-game supplants below the global min
        must not re-arm the relief clock, or one churning marathon keeps
        the other 191 slots frozen forever.
        """
        with self.lock:
            offers = getattr(self, f"_{bank}_recent_offers")
            offers.append(float(score))
            if score < floor:
                return False
            idxs = np.asarray(list(indices), dtype=np.int64)
            idxs = idxs[(idxs >= 0) & (idxs < self.size)]
            if idxs.size < 32:
                return False
            idxs = self._bank_span(idxs, stride)
            ep_score = getattr(self, f"{bank}_ep_score")
            ep_len   = getattr(self, f"{bank}_ep_len")
            ep_game  = getattr(self, f"{bank}_ep_game")
            ep_level = getattr(self, f"{bank}_ep_level")
            count    = int(getattr(self, f"{bank}_ep_count"))
            gmin = float(ep_score[:count].min()) if count > 0 else float("-inf")
            relief_note = None
            same = (np.where(ep_game[:count] == game_uid)[0]
                    if game_uid > 0 else np.empty(0, dtype=np.int64))
            fresh_slot = False
            if same.size >= per_game_cap:
                ep = int(same[np.argmin(ep_score[same])])
                if score <= float(ep_score[ep]):
                    return False
                normal = score > gmin
            elif count < max_eps:
                ep = count
                fresh_slot = True
                setattr(self, f"{bank}_ep_count", count + 1)
                normal = True
            else:
                ep = int(np.argmin(ep_score[:count]))
                normal = score > gmin
                if not normal:
                    starve = self._adds_total - int(
                        getattr(self, f"_{bank}_last_normal_admit_add"))
                    limit = int(getattr(RL_CONFIG, "bank_starvation_adds", 25_000_000))
                    if starve > limit and len(offers) >= 64:
                        pct = float(np.percentile(
                            np.asarray(offers, dtype=np.float64),
                            float(getattr(RL_CONFIG, "bank_relief_percentile", 90.0))))
                        if score >= max(floor, pct):
                            relief_note = (
                                f"[{bank.upper()}] bar relief: admitting {score:,.0f} "
                                f"over frozen min {float(ep_score[ep]):,.0f} "
                                f"(no normal admission in {starve:,} ring adds)")
                        else:
                            return False
                    else:
                        return False
            base = ep * stride
            n = int(idxs.size)
            for f in ("states", "next_states", "actions", "rewards",
                      "dones", "horizons", "is_expert", "actor_kind"):
                getattr(self, f"{bank}_{f}")[base:base + n] = getattr(self, f)[idxs]
            # A fresh slot contributes no prior length — ep_len can hold a
            # stale value there after a mid-run bank reload shrank ep_count.
            setattr(self, f"{bank}_total",
                    int(getattr(self, f"{bank}_total"))
                    - (0 if fresh_slot else int(ep_len[ep])) + n)
            ep_score[ep] = float(score)
            ep_len[ep] = n
            ep_game[ep] = int(game_uid)
            ep_level[ep] = int(level)
            getattr(self, f"_{bank}_rebuild_flat_locked")()
            setattr(self, f"_{bank}_last_admit_add", self._adds_total)
            if normal:
                setattr(self, f"_{bank}_last_normal_admit_add", self._adds_total)
        if relief_note:
            print(relief_note)
        return True

    def max_game_uid(self) -> int:
        """Highest game uid persisted in either bank (0 when empty).  The
        server seeds its uid counter ABOVE this at boot: banks survive
        restarts while the counter would otherwise restart at 1, and a
        collision binds unrelated games together in per-game dedup."""
        with self.lock:
            m = 0
            if self._hof_enabled and self.hof_ep_count > 0:
                m = max(m, int(self.hof_ep_game[:self.hof_ep_count].max()))
            if self._ephof_enabled and self.ephof_ep_count > 0:
                m = max(m, int(self.ephof_ep_game[:self.ephof_ep_count].max()))
            return max(0, m)

    def hof_admit(self, indices, game_score: int, game_uid: int = -1, level: int = 0) -> bool:
        """Admit an episode to the hall of fame, keyed on CUMULATIVE game
        score at episode end.  See _bank_admit for the admission contract."""
        if not self._hof_enabled:
            return False
        return self._bank_admit(
            "hof", indices, float(game_score),
            float(getattr(RL_CONFIG, "hof_min_game_score", 50_000)),
            max(1, int(getattr(RL_CONFIG, "hof_max_per_game", 2))),
            self._hof_stride, self._hof_max_eps, int(game_uid), int(level))

    def hof_admission_bar(self):
        """Current hall-of-fame admission bar (dashboard HOF column).

        The score a new episode must beat to enter: the static floor while
        the bank is filling, then the worst enshrined score once full — the
        ratchet the operator watches climb.  Returns None when disabled.
        """
        if not self._hof_enabled:
            return None
        with self.lock:
            floor = float(getattr(RL_CONFIG, "hof_min_game_score", 0))
            if self.hof_ep_count >= self._hof_max_eps:
                return max(floor, float(self.hof_ep_score[:self.hof_ep_count].min()))
            return floor

    def hof_score_range(self):
        """(bar, best) for the dashboard HOF column.

        bar  = admission bar: the static floor while filling, else the worst
               enshrined score once full (what a new episode must beat).
        best = highest score currently in the bank.
        Returns None when disabled or empty (renders as "-").
        """
        if not self._hof_enabled:
            return None
        with self.lock:
            n = self.hof_ep_count
            if n <= 0:
                return None
            scores = self.hof_ep_score[:n]
            best = float(scores.max())
            floor = float(getattr(RL_CONFIG, "hof_min_game_score", 0))
            bar = max(floor, float(scores.min())) if n >= self._hof_max_eps else floor
            if not np.isfinite(best):
                return None
            return bar, best

    def _bank_stats_locked(self, bank: str, min_tr: int, frac: float, floor: float, max_eps: int):
        """Bank summary for the buffer stats report (call under lock)."""
        n = int(getattr(self, f"{bank}_ep_count"))
        total = int(getattr(self, f"{bank}_total"))
        quota_active = total >= min_tr
        scale = self._bank_quota_scale_for(bank)
        stats = {
            "episodes": n,
            "max_episodes": max_eps,
            "transitions": total,
            "quota_active": quota_active,
            "fraction": (frac * scale) if quota_active else 0.0,
            "quota_scale": scale,
            "admission_floor": floor,
            "starve_adds": int(self._adds_total
                               - int(getattr(self, f"_{bank}_last_normal_admit_add"))),
        }
        if n > 0:
            scores = getattr(self, f"{bank}_ep_score")[:n]
            levels = getattr(self, f"{bank}_ep_level")[:n]
            games = getattr(self, f"{bank}_ep_game")[:n]
            stats.update(best=float(scores.max()), worst=float(scores.min()),
                         median=float(np.median(scores)),
                         distinct_games=int(np.unique(games[games > 0]).size),
                         level_min=int(levels.min()), level_max=int(levels.max()),
                         level_median=int(np.median(levels)))
            # Once full, the WORST admitted score is the live admission bar.
            if n >= max_eps:
                stats["admission_floor"] = max(stats["admission_floor"], float(scores.min()))
        return stats

    def _hof_stats_locked(self):
        if not self._hof_enabled:
            return None
        return self._bank_stats_locked(
            "hof", int(getattr(RL_CONFIG, "hof_min_transitions", 4096)),
            float(getattr(RL_CONFIG, "hof_replay_fraction", 0.0)),
            float(getattr(RL_CONFIG, "hof_min_game_score", 0)), self._hof_max_eps)

    def _hof_rebuild_flat_locked(self):
        parts = [np.arange(ep * self._hof_stride, ep * self._hof_stride + int(self.hof_ep_len[ep]), dtype=np.int64)
                 for ep in range(self.hof_ep_count) if self.hof_ep_len[ep] > 0]
        self._hof_flat = np.concatenate(parts) if parts else np.empty(0, dtype=np.int64)

    def ephof_admit(self, indices, episode_score: int, game_uid: int = -1, level: int = 0) -> bool:
        """Admit a life to the per-life hall of fame, keyed on the score
        earned WITHIN that single life.  See _bank_admit for the contract."""
        if not self._ephof_enabled:
            return False
        return self._bank_admit(
            "ephof", indices, float(episode_score),
            float(getattr(RL_CONFIG, "ephof_min_episode_score", 25_000)),
            max(1, int(getattr(RL_CONFIG, "ephof_max_per_game", 3))),
            self._ephof_stride, self._ephof_max_eps, int(game_uid), int(level))

    def _bank_quota_scale_for(self, bank: str) -> float:
        """Staleness scale for a bank's replay quota.  A bank still FILLING
        is never stale — relief cannot apply to it and its quota is already
        gated by min_transitions; staleness is only meaningful once the bar
        (the full bank's minimum) exists to outrun live play."""
        if int(getattr(self, f"{bank}_ep_count")) < int(getattr(self, f"_{bank}_max_eps")):
            return 1.0
        return self._bank_quota_scale(int(getattr(self, f"_{bank}_last_admit_add")))

    def _bank_quota_scale(self, last_admit_add: int) -> float:
        """Staleness decay on a bank's replay quota: full share while the
        bank has admitted within one ring turnover, then a linear surrender
        toward the floor — even a frozen bank cannot dominate the gradient
        indefinitely (2026-07-22: 25% of every batch was a bank with zero
        admissions for ~25 ring turnovers)."""
        limit = max(1, int(getattr(RL_CONFIG, "bank_starvation_adds", 25_000_000)))
        starve = (self._adds_total - int(last_admit_add)) / limit
        if starve <= 1.0:
            return 1.0
        floor = float(getattr(RL_CONFIG, "bank_stale_quota_floor", 0.25))
        return max(floor, 1.0 - 0.375 * (starve - 1.0))

    def _ephof_rebuild_flat_locked(self):
        parts = [np.arange(ep * self._ephof_stride, ep * self._ephof_stride + int(self.ephof_ep_len[ep]), dtype=np.int64)
                 for ep in range(self.ephof_ep_count) if self.ephof_ep_len[ep] > 0]
        self._ephof_flat = np.concatenate(parts) if parts else np.empty(0, dtype=np.int64)

    def _ephof_stats_locked(self):
        if not self._ephof_enabled:
            return None
        return self._bank_stats_locked(
            "ephof", int(getattr(RL_CONFIG, "ephof_min_transitions", 4096)),
            float(getattr(RL_CONFIG, "ephof_replay_fraction", 0.0)),
            float(getattr(RL_CONFIG, "ephof_min_episode_score", 0)), self._ephof_max_eps)

    def sample(self, batch_size: int, beta: float = 0.4):
        """Sample a prioritised batch. Returns (states, actions, rewards,
        next_states, dones, horizons, is_expert, actor_kind, indices, weights)."""
        with self.lock:
            if self.size < batch_size:
                return None

            total = self.tree.total()
            if total <= 0:
                return None

            # Hall-of-fame quota first: a guaranteed slice of permanent
            # peak-play data in every batch (the anti-forgetting anchor).
            hof_count = 0
            if self._hof_enabled and self.hof_total >= int(getattr(RL_CONFIG, "hof_min_transitions", 4096)):
                hof_frac = max(0.0, min(0.25, float(getattr(RL_CONFIG, "hof_replay_fraction", 0.0))))
                hof_frac *= self._bank_quota_scale_for("hof")
                hof_count = min(batch_size // 4, int(round(batch_size * hof_frac)))
            ephof_count = 0
            if self._ephof_enabled and self.ephof_total >= int(getattr(RL_CONFIG, "ephof_min_transitions", 4096)):
                ephof_frac = max(0.0, min(0.30, float(getattr(RL_CONFIG, "ephof_replay_fraction", 0.0))))
                ephof_frac *= self._bank_quota_scale_for("ephof")
                ephof_count = min(batch_size // 4, int(round(batch_size * ephof_frac)))
            # Combined banks may never crowd the ring below half the batch.
            if hof_count + ephof_count > batch_size // 2:
                ephof_count = max(0, batch_size // 2 - hof_count)

            frac = max(0.0, min(0.75, float(getattr(RL_CONFIG, "interesting_replay_fraction", 0.0))))
            recent_frac = max(0.0, min(0.75, float(getattr(RL_CONFIG, "recent_replay_fraction", 0.0))))
            if frac + recent_frac > 0.90:
                scale = 0.90 / (frac + recent_frac)
                frac *= scale
                recent_frac *= scale
            ring_budget = batch_size - hof_count - ephof_count
            interesting_count = min(ring_budget - 1, int(round(batch_size * frac))) if frac > 0.0 else 0
            interesting_indices = self._sample_interesting_indices(interesting_count)
            recent_count = min(ring_budget - int(interesting_indices.size) - 1, int(round(batch_size * recent_frac))) if recent_frac > 0.0 else 0
            recent_indices = self._sample_recent_indices(recent_count)
            per_count = ring_budget - int(interesting_indices.size) - int(recent_indices.size)

            # Stratified sampling — one uniform draw per segment (vectorised)
            segment = total / max(1, per_count)
            lows = np.arange(per_count, dtype=np.float64) * segment
            highs = lows + segment
            values = np.random.uniform(lows, highs)
            per_indices = self.tree.batch_get(values) if per_count > 0 else np.empty(0, dtype=np.int64)
            if per_indices.size:
                np.clip(per_indices, 0, self.size - 1, out=per_indices)
            indices = np.concatenate([per_indices, interesting_indices, recent_indices])

            # Importance-sampling weights (2026-07 fix): the PER formula
            # applies ONLY to the tree-drawn slice.  The recent/interesting
            # quotas are uniform/score-drawn, not priority-drawn — assigning
            # them PER weights computed from tree priorities they were never
            # drawn by tilted over half of each batch's effective gradient
            # toward the newest minutes of the policy's own play (the
            # positive-feedback engine of every collapse).  Quota and HOF
            # samples get weight 1.0.
            weights = np.ones(int(indices.size) + hof_count + ephof_count, dtype=np.float64)
            if per_indices.size:
                pri = np.maximum(1e-10, self.tree.tree[per_indices + self.tree.capacity])
                w = (self.size * (pri / total)) ** (-beta)
                weights[:per_indices.size] = w / max(1e-12, float(w.max()))
                # Honest bank weights (2026-07-22): bank rows previously rode
                # weight 1.0 — the PER max — giving 25% of the batch a
                # privileged gradient pull over live data (mean PER weight is
                # well below 1).  Bank rows now carry exactly the mean PER
                # weight: an average vote, never a megaphone.
                if hof_count + ephof_count > 0:
                    weights[int(indices.size):] = float(
                        np.mean(weights[:per_indices.size]))

            # Bank rows (HOF / EpHOF) ride sentinel indices >= capacity;
            # update_priorities filters them out (no sum-tree leaves).  EpHOF
            # sentinels start at _ephof_base, past the game-HOF span, so the
            # two banks cannot alias.
            banks = []
            if hof_count > 0:
                banks.append(("hof", self.capacity,
                              self._hof_flat[np.random.randint(0, self._hof_flat.size, hof_count)]))
            if ephof_count > 0:
                banks.append(("ephof", self._ephof_base,
                              self._ephof_flat[np.random.randint(0, self._ephof_flat.size, ephof_count)]))
            if banks:
                all_indices = np.concatenate(
                    [indices] + [base + slots for _, base, slots in banks])

                def _cat(field, cast=None):
                    # fp16 ring + fp32 banks: concat promotes to fp32 (free);
                    # astype guards the invariant if bank dtype ever changes.
                    parts = [getattr(self, field)[indices]] + [
                        getattr(self, f"{prefix}_{field}")[slots] for prefix, _, slots in banks]
                    out = np.concatenate(parts)
                    return out.astype(cast, copy=False) if cast is not None else out

                return (
                    _cat("states", np.float32),
                    _cat("actions"),
                    _cat("rewards"),
                    _cat("next_states", np.float32),
                    _cat("dones"),
                    _cat("horizons"),
                    _cat("is_expert"),
                    _cat("actor_kind"),
                    all_indices,
                    weights.astype(np.float32),
                )

            return (
                self.states[indices].astype(np.float32),
                self.actions[indices],
                self.rewards[indices],
                self.next_states[indices].astype(np.float32),
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
            idx = np.asarray(indices, dtype=np.int64)
            td = np.abs(np.asarray(td_errors).astype(np.float64))
            # HOF rows carry sentinel indices >= capacity and have no
            # sum-tree leaves — writing them would corrupt ring priorities.
            mask = idx < self.capacity
            if not mask.all():
                idx = idx[mask]
                td = td[mask]
            if idx.size == 0:
                return
            new_p = (td + 1e-6) ** self.alpha
            self.tree.batch_update(idx, new_p)

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
                if enemy_features >= TYPE_ONEHOT_OFFSET + TYPE_CLASS_COUNT:
                    type_id = decode_token_types(rows)
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
                "hof": self._hof_stats_locked(),
                "ephof": self._ephof_stats_locked(),
            }

    # ── Persistence ─────────────────────────────────────────────────────

    def _save_hof(self, dirpath: str, verbose: bool = True):
        """Persist the hall of fame to its own directory.

        Deliberately a SIBLING of the replay directory (…_replay_hof), not
        inside it: collapse-recovery reverts delete the replay dir, and the
        hall of fame must survive reverts — that is its entire purpose.
        """
        if not self._hof_enabled or self.hof_ep_count == 0:
            return
        with self.lock:
            os.makedirs(dirpath, exist_ok=True)
            used = self.hof_ep_count * self._hof_stride
            np.save(os.path.join(dirpath, "hof_states.npy"), self.hof_states[:used])
            np.save(os.path.join(dirpath, "hof_next_states.npy"), self.hof_next_states[:used])
            np.save(os.path.join(dirpath, "hof_actions.npy"), self.hof_actions[:used])
            np.save(os.path.join(dirpath, "hof_rewards.npy"), self.hof_rewards[:used])
            np.save(os.path.join(dirpath, "hof_dones.npy"), self.hof_dones[:used])
            np.save(os.path.join(dirpath, "hof_horizons.npy"), self.hof_horizons[:used])
            np.save(os.path.join(dirpath, "hof_is_expert.npy"), self.hof_is_expert[:used])
            np.save(os.path.join(dirpath, "hof_actor_kind.npy"), self.hof_actor_kind[:used])
            np.savez(os.path.join(dirpath, "hof_meta.npz"),
                     ep_score=self.hof_ep_score[:self.hof_ep_count],
                     ep_len=self.hof_ep_len[:self.hof_ep_count],
                     ep_game=self.hof_ep_game[:self.hof_ep_count],
                     ep_level=self.hof_ep_level[:self.hof_ep_count],
                     # Staleness watermarks (ages, not raw clocks — the adds
                     # counter is process-local): a frozen bank must not
                     # reload as "fresh" and reclaim full quota.
                     stale_age=np.int64(self._adds_total - self._hof_last_admit_add),
                     stale_age_normal=np.int64(self._adds_total - self._hof_last_normal_admit_add),
                     stride=np.int64(self._hof_stride),
                     state_size=np.int64(self.state_size))
            if verbose:
                print(f"  HOF saved: {self.hof_ep_count} episodes / {self.hof_total:,} transitions")

    def _load_hof(self, dirpath: str, verbose: bool = True) -> bool:
        if not self._hof_enabled or not os.path.isdir(dirpath):
            return False
        meta_path = os.path.join(dirpath, "hof_meta.npz")
        if not os.path.isfile(meta_path):
            return False
        meta = np.load(meta_path)
        if int(meta["stride"]) != self._hof_stride or int(meta["state_size"]) != self.state_size:
            print("  HOF load skipped: stride/state_size mismatch with config")
            return False
        with self.lock:
            ep_score = np.asarray(meta["ep_score"], dtype=np.float64)
            ep_len = np.asarray(meta["ep_len"], dtype=np.int32)
            n_eps = min(int(ep_score.shape[0]), self._hof_max_eps)
            used = n_eps * self._hof_stride
            self.hof_states[:used] = np.load(os.path.join(dirpath, "hof_states.npy"))[:used]
            self.hof_next_states[:used] = np.load(os.path.join(dirpath, "hof_next_states.npy"))[:used]
            self.hof_actions[:used] = np.load(os.path.join(dirpath, "hof_actions.npy"))[:used]
            self.hof_rewards[:used] = np.load(os.path.join(dirpath, "hof_rewards.npy"))[:used]
            self.hof_dones[:used] = np.load(os.path.join(dirpath, "hof_dones.npy"))[:used]
            self.hof_horizons[:used] = np.load(os.path.join(dirpath, "hof_horizons.npy"))[:used]
            self.hof_is_expert[:used] = np.load(os.path.join(dirpath, "hof_is_expert.npy"))[:used]
            self.hof_actor_kind[:used] = np.load(os.path.join(dirpath, "hof_actor_kind.npy"))[:used]
            self.hof_ep_score[:n_eps] = ep_score[:n_eps]
            self.hof_ep_len[:n_eps] = ep_len[:n_eps]
            # Legacy saves lack game/level metadata: -1 ids are treated as
            # unique by dedup.  New-format ids stay valid because the server
            # seeds its uid counter above max_game_uid() at boot.
            if "ep_game" in meta.files:
                self.hof_ep_game[:n_eps] = np.asarray(meta["ep_game"], dtype=np.int64)[:n_eps]
                self.hof_ep_level[:n_eps] = np.asarray(meta["ep_level"], dtype=np.int32)[:n_eps]
            else:
                self.hof_ep_game[:n_eps] = -1
                self.hof_ep_level[:n_eps] = 0
            # Zero tail metadata: a mid-run reload can SHRINK ep_count below
            # slots the live bank had filled; a stale ep_len there corrupts
            # the fresh-slot accounting on the next admission.
            self.hof_ep_len[n_eps:] = 0
            self.hof_ep_score[n_eps:] = -np.inf
            self.hof_ep_game[n_eps:] = -1
            self.hof_ep_level[n_eps:] = 0
            # Restore staleness ages relative to this process's clock.
            if "stale_age" in meta.files:
                self._hof_last_admit_add = self._adds_total - int(meta["stale_age"])
                self._hof_last_normal_admit_add = self._adds_total - int(meta["stale_age_normal"])
            self.hof_ep_count = n_eps
            self.hof_total = int(self.hof_ep_len[:n_eps].sum())
            self._hof_rebuild_flat_locked()
        if verbose:
            print(f"  HOF loaded: {self.hof_ep_count} episodes / {self.hof_total:,} transitions "
                  f"(best {self.hof_ep_score[:self.hof_ep_count].max():,.0f})")
        return True

    def _save_ephof(self, dirpath: str, verbose: bool = True):
        """Persist the EpHOF to its own sibling directory (same survive-the-
        revert contract as the game HOF)."""
        if not self._ephof_enabled or self.ephof_ep_count == 0:
            return
        with self.lock:
            os.makedirs(dirpath, exist_ok=True)
            used = self.ephof_ep_count * self._ephof_stride
            np.save(os.path.join(dirpath, "ephof_states.npy"), self.ephof_states[:used])
            np.save(os.path.join(dirpath, "ephof_next_states.npy"), self.ephof_next_states[:used])
            np.save(os.path.join(dirpath, "ephof_actions.npy"), self.ephof_actions[:used])
            np.save(os.path.join(dirpath, "ephof_rewards.npy"), self.ephof_rewards[:used])
            np.save(os.path.join(dirpath, "ephof_dones.npy"), self.ephof_dones[:used])
            np.save(os.path.join(dirpath, "ephof_horizons.npy"), self.ephof_horizons[:used])
            np.save(os.path.join(dirpath, "ephof_is_expert.npy"), self.ephof_is_expert[:used])
            np.save(os.path.join(dirpath, "ephof_actor_kind.npy"), self.ephof_actor_kind[:used])
            np.savez(os.path.join(dirpath, "ephof_meta.npz"),
                     ep_score=self.ephof_ep_score[:self.ephof_ep_count],
                     ep_len=self.ephof_ep_len[:self.ephof_ep_count],
                     ep_game=self.ephof_ep_game[:self.ephof_ep_count],
                     ep_level=self.ephof_ep_level[:self.ephof_ep_count],
                     stale_age=np.int64(self._adds_total - self._ephof_last_admit_add),
                     stale_age_normal=np.int64(self._adds_total - self._ephof_last_normal_admit_add),
                     stride=np.int64(self._ephof_stride),
                     state_size=np.int64(self.state_size))
            if verbose:
                print(f"  EpHOF saved: {self.ephof_ep_count} episodes / {self.ephof_total:,} transitions")

    def _load_ephof(self, dirpath: str, verbose: bool = True) -> bool:
        if not self._ephof_enabled or not os.path.isdir(dirpath):
            return False
        meta_path = os.path.join(dirpath, "ephof_meta.npz")
        if not os.path.isfile(meta_path):
            return False
        meta = np.load(meta_path)
        if int(meta["stride"]) != self._ephof_stride or int(meta["state_size"]) != self.state_size:
            print("  EpHOF load skipped: stride/state_size mismatch with config")
            return False
        with self.lock:
            ep_score = np.asarray(meta["ep_score"], dtype=np.float64)
            ep_len = np.asarray(meta["ep_len"], dtype=np.int32)
            n_eps = min(int(ep_score.shape[0]), self._ephof_max_eps)
            used = n_eps * self._ephof_stride
            self.ephof_states[:used] = np.load(os.path.join(dirpath, "ephof_states.npy"))[:used]
            self.ephof_next_states[:used] = np.load(os.path.join(dirpath, "ephof_next_states.npy"))[:used]
            self.ephof_actions[:used] = np.load(os.path.join(dirpath, "ephof_actions.npy"))[:used]
            self.ephof_rewards[:used] = np.load(os.path.join(dirpath, "ephof_rewards.npy"))[:used]
            self.ephof_dones[:used] = np.load(os.path.join(dirpath, "ephof_dones.npy"))[:used]
            self.ephof_horizons[:used] = np.load(os.path.join(dirpath, "ephof_horizons.npy"))[:used]
            self.ephof_is_expert[:used] = np.load(os.path.join(dirpath, "ephof_is_expert.npy"))[:used]
            self.ephof_actor_kind[:used] = np.load(os.path.join(dirpath, "ephof_actor_kind.npy"))[:used]
            self.ephof_ep_score[:n_eps] = ep_score[:n_eps]
            self.ephof_ep_len[:n_eps] = ep_len[:n_eps]
            if "ep_game" in meta.files:
                self.ephof_ep_game[:n_eps] = np.asarray(meta["ep_game"], dtype=np.int64)[:n_eps]
                self.ephof_ep_level[:n_eps] = np.asarray(meta["ep_level"], dtype=np.int32)[:n_eps]
            else:
                self.ephof_ep_game[:n_eps] = -1
                self.ephof_ep_level[:n_eps] = 0
            self.ephof_ep_len[n_eps:] = 0
            self.ephof_ep_score[n_eps:] = -np.inf
            self.ephof_ep_game[n_eps:] = -1
            self.ephof_ep_level[n_eps:] = 0
            if "stale_age" in meta.files:
                self._ephof_last_admit_add = self._adds_total - int(meta["stale_age"])
                self._ephof_last_normal_admit_add = self._adds_total - int(meta["stale_age_normal"])
            self.ephof_ep_count = n_eps
            self.ephof_total = int(self.ephof_ep_len[:n_eps].sum())
            self._ephof_rebuild_flat_locked()
        if verbose:
            print(f"  EpHOF loaded: {self.ephof_ep_count} episodes / {self.ephof_total:,} transitions "
                  f"(best life {self.ephof_ep_score[:self.ephof_ep_count].max():,.0f})")
        return True

    def save(self, filepath: str, verbose: bool = True):
        """Save the full replay buffer as individual .npy files in a directory."""
        abs_path = os.path.abspath(filepath)
        try:
            self._save_hof(self._hof_dir or (abs_path + "_hof"), verbose)
        except Exception as e:
            print(f"  [WARN] HOF save failed: {e}")
        try:
            self._save_ephof(self._ephof_dir or (abs_path + "_ephof"), verbose)
        except Exception as e:
            print(f"  [WARN] EpHOF save failed: {e}")
        if self._mmap_dir is not None and os.path.abspath(self._mmap_dir) == abs_path:
            with self.lock:
                t0 = time.time()
                n = int(self.size)
                if verbose:
                    print(f"  Flushing mmap replay buffer ({n:,} transitions)...")
                    self._progress_bar("  Replay flush", 0.10)
                # msync only for power-loss durability (see replay_flush_msync).
                do_msync = bool(getattr(RL_CONFIG, "replay_flush_msync", False))
                if do_msync:
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
                if do_msync:
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

    def ensure_live_mmap(self, dirpath: str, verbose: bool = True) -> bool:
        """Give an EMPTY buffer live mmap backing from birth (Tempest-style).

        The storage arrays become full-size on-disk .npy memmaps immediately,
        so every save is a ~0.1s flush and every restart adopts in place —
        no multi-GB first save after a fresh start or a collapse-recovery
        wipe.  Creation is instant: open_memmap produces sparse files on
        ext4/xfs, and disk usage grows only as the ring actually fills.

        If the directory already holds saved transitions, this does nothing —
        the normal load() path adopts it and restores counters properly.
        """
        if self._mmap_dir is not None or self.size > 0:
            return False
        abs_path = os.path.abspath(dirpath)
        meta_path = os.path.join(abs_path, "_meta.npy")
        if os.path.isfile(meta_path):
            try:
                if int(np.load(meta_path)[1]) > 0:
                    return False  # real data present: defer to load()/adoption
            except Exception:
                return False      # unreadable meta: leave the directory alone
        try:
            os.makedirs(abs_path, exist_ok=True)
            # Stale atomic-save leftovers (<dir>.tmp) are incomplete by
            # definition and can silently eat tens of GB of tmpfs headroom —
            # a 44 GB stray .tmp caused the 2026-07-18 SIGBUS silent-exit
            # (ring page-fault with /dev/shm at 100%).  Reclaim them.
            tmp_dir = abs_path + ".tmp"
            if os.path.isdir(tmp_dir):
                import shutil as _sh
                _sh.rmtree(tmp_dir, ignore_errors=True)
                print(f"  Removed stale replay tmp dir: {tmp_dir}")
            with self.lock:
                for name, (attr, dtype, shape) in self._storage_specs().items():
                    path = os.path.join(abs_path, f"{name}.npy")
                    arr = None
                    if os.path.isfile(path):
                        candidate = np.load(path, mmap_mode="r+")
                        if candidate.dtype == dtype and candidate.shape == shape:
                            arr = candidate
                    if arr is None:
                        arr = np.lib.format.open_memmap(path, mode="w+", dtype=dtype, shape=shape)
                        # Reserve the FULL file now (tmpfs honors fallocate).
                        # Sparse files defer allocation to page-fault time, so
                        # an over-committed tmpfs kills the trainer with a
                        # silent SIGBUS hours in — at the worst possible
                        # moment, when the ring finally fills.  Reserving at
                        # boot converts that into an immediate, loud error.
                        with open(path, "r+b") as fh:
                            nbytes = int(np.prod(shape)) * dtype.itemsize + 4096
                            os.posix_fallocate(fh.fileno(), 0, nbytes)
                    setattr(self, attr, arr)
                pri_path = os.path.join(abs_path, "priorities.npy")
                if not os.path.isfile(pri_path):
                    pri = np.lib.format.open_memmap(pri_path, mode="w+", dtype=np.float64, shape=(self.capacity,))
                    del pri
                tmp_meta = meta_path + ".tmp.npy"
                np.save(tmp_meta, np.array([0, 0, 1.0]))
                os.replace(tmp_meta, meta_path)
                self._mmap_dir = abs_path
            if verbose:
                print(f"  Replay buffer live-mmap backing at {abs_path} (saves are flushes)")
            return True
        except Exception as e:
            print(f"  [WARN] live-mmap backing unavailable ({e}) — using RAM arrays")
            return False

    def _promote_to_live_mmap(self, dirpath: str, verbose: bool = True) -> bool:
        """Rewrite RAM storage as full-size on-disk mmaps after a load that
        couldn't adopt (legacy truncated dir, .npz, or copy-restore).

        Without this, a buffer migrated from the old truncated save format
        stays in RAM and every save takes the multi-GB copy path forever —
        adoption requires full-CAPACITY arrays, which the old format never
        wrote.  Promotion is a one-time ~n-row write (the rest stays sparse),
        after which saves are ~1s priority/meta flushes and RAM is freed.
        """
        if self._mmap_dir is not None:
            return True
        abs_path = os.path.abspath(dirpath)
        try:
            os.makedirs(abs_path, exist_ok=True)
            with self.lock:
                n = int(self.size)
                for name, (attr, dtype, shape) in self._storage_specs().items():
                    path = os.path.join(abs_path, f"{name}.npy")
                    mm = np.lib.format.open_memmap(path, mode="w+", dtype=dtype, shape=shape)
                    cur = getattr(self, attr)
                    if n > 0:
                        mm[:n] = cur[:n]
                    setattr(self, attr, mm)   # old RAM array drops -> frees RAM
                pri = np.lib.format.open_memmap(
                    os.path.join(abs_path, "priorities.npy"),
                    mode="w+", dtype=np.float64, shape=(self.capacity,))
                if n > 0:
                    pri[:n] = self.tree.tree[self.tree.capacity:self.tree.capacity + n]
                del pri
                meta = np.array([self.tree.data_ptr, n, self.tree.max_priority])
                tmp_meta = os.path.join(abs_path, "_meta.npy.tmp.npy")
                np.save(tmp_meta, meta)
                os.replace(tmp_meta, os.path.join(abs_path, "_meta.npy"))
                self._mmap_dir = abs_path
            if verbose:
                print(f"  Replay buffer promoted to live-mmap ({abs_path}) — future saves are flushes")
            return True
        except Exception as e:
            print(f"  [WARN] live-mmap promotion failed ({e}) — saves remain full-copy")
            return False

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
        # Hall of fame loads independently of (and before) the main ring:
        # after a collapse-recovery wipe the ring is gone but the HOF is not.
        try:
            self._load_hof(self._hof_dir or (os.path.abspath(filepath) + "_hof"), verbose)
        except Exception as e:
            print(f"  [WARN] HOF load failed: {e}")
        try:
            self._load_ephof(self._ephof_dir or (os.path.abspath(filepath) + "_ephof"), verbose)
        except Exception as e:
            print(f"  [WARN] EpHOF load failed: {e}")
        # Try directory format (new fast path)
        ok = False
        promote_dir = filepath if not filepath.endswith(".npz") else filepath[:-4]
        if os.path.isdir(filepath):
            ok = self._load_directory(filepath, verbose)
        elif os.path.isfile(filepath):
            ok = self._load_npz(filepath, verbose)
        elif filepath.endswith(".npz"):
            dir_path = filepath[:-4]
            if os.path.isdir(dir_path):
                ok = self._load_directory(dir_path, verbose)
        else:
            npz_path = filepath + ".npz"
            if os.path.isfile(npz_path):
                ok = self._load_npz(npz_path, verbose)

        # If the load succeeded but adoption didn't leave us mmap-backed
        # (legacy truncated dir / npz / copy-restore), promote so subsequent
        # saves are flushes rather than multi-GB copies.
        if ok and self._mmap_dir is None and bool(getattr(RL_CONFIG, "replay_live_mmap", True)):
            self._promote_to_live_mmap(promote_dir, verbose)
        return ok

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
