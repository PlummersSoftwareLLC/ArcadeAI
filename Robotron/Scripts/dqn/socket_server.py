#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN SOCKET BRIDGE SERVER                                                                     ||
# ||  TCP server bridging Lua (MAME) ↔ Python.  Tempest DQN data-path on Robotron's wire protocol.              ||
# ==================================================================================================================
"""Socket server — receives frames from Lua, queries the branching DQN agent,
returns 5-byte ``>bbBBB`` actions (move_dir, fire_dir, source, start_advanced,
start_level_min).

Game-flow contract (Robotron-specific):
  • Inbound framing: 4-byte big-endian length prefix, then the payload.
  • Payload header ``>HddBIBBBIBB`` (n, subj, obj, done, score, player_alive,
    save, start_pressed, replay_level, num_lasers, wave), then n f32 (big-endian).
  • The model consumes the compact slice of the wire (18 core + 22 ELIST values
    + 16 lane-density values + nearest target/type summaries + 96 role-aware
    object rows); the full wire is still used by the expert/debug paths.
  • Episodes terminate on ``frame.done``.  While ``player_alive`` is false (death
    animation / between lives) we send a neutral action and store no transitions.
    • Reward = clipped game_score delta plus tightly clipped Lua subjective shaping.
"""

if __name__ == "__main__":
    print("This is not the main application, run 'main.py' instead")
    exit(1)

import os, sys, time, socket, select, struct, threading, traceback, random, queue
import numpy as np
from collections import deque
from dataclasses import dataclass
from typing import Optional

try:
    from .config import (RL_CONFIG, SERVER_CONFIG, metrics, LATEST_MODEL_PATH,
                         game_settings, slice_model_state, WIRE_PARAMS_COUNT,
                         extract_tactical_diagnostics)
    from .nstep_buffer import NStepReplayBuffer
    from .model import combine_action, split_joint_action, action_index_to_wire_dir
    from .metrics_display import (
        add_episode_to_dqn100k_window,
        add_episode_to_dqn1m_window,
        add_episode_to_dqn5m_window,
        add_episode_to_dqn_perframe_window,
        add_episode_to_total_windows,
        add_episode_to_eplen_window,
    )
except ImportError:
    from config import (RL_CONFIG, SERVER_CONFIG, metrics, LATEST_MODEL_PATH,
                        game_settings, slice_model_state, WIRE_PARAMS_COUNT,
                        extract_tactical_diagnostics)
    from nstep_buffer import NStepReplayBuffer
    from model import combine_action, split_joint_action, action_index_to_wire_dir
    from metrics_display import (
        add_episode_to_dqn100k_window,
        add_episode_to_dqn1m_window,
        add_episode_to_dqn5m_window,
        add_episode_to_dqn_perframe_window,
        add_episode_to_total_windows,
        add_episode_to_eplen_window,
    )

# Robotron heuristic expert — reused from the v3 package (game logic, not PPO).
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../Scripts
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
try:
    # Lean DQN-only extractor: identical behavior to v3.expert.get_expert_action
    # but skips the full entity-token tensor the DQN model never uses
    # (keeps high expert ratios from stalling the per-client loop).
    from dqn.expert_fast import fast_expert_action as get_expert_action
except Exception as e:                      # pragma: no cover - expert optional
    print(f"[WARN] Robotron expert unavailable ({e}); expert guidance disabled.")
    get_expert_action = None

_MAX_FRAME_PAYLOAD_BYTES = 4 * 1024 * 1024

# Action source codes (low nibble of the source byte)
_SRC_NONE = 0
_SRC_DQN = 1
_SRC_EPSILON = 2
_SRC_EXPERT = 3
_SRC_EVAL = 4
_PREVIEW_FLAG = 0x40
_HUD_FLAG = 0x80
# Preview/HUD source bits are intentionally hard-disabled. The current
# dashboard does not consume client preview streams, and enabling these bits
# makes Lua do expensive screen/HUD preparation work.
_ENABLE_PREVIEW_BITS = False

# Live action diagnostics (set DQN_DEBUG_ACTIONS=1 to enable).  Prints a throttled
# line showing the chosen source, live entity counts, and the exact bytes sent.
_DBG_ACTIONS = os.environ.get("DQN_DEBUG_ACTIONS", "") not in ("", "0", "false", "False")
_DBG_EVERY = max(1, int(os.environ.get("DQN_DEBUG_EVERY", "60")))

# Fire-hold cadence: keep each fire direction stable for this many frames so the
# game registers reliable shots.  Applied Python-side (replaces the old Lua hold)
# so the replay buffer stores the *effective* held fire action, not the raw request.
FIRE_HOLD_FRAMES = max(1, int(getattr(RL_CONFIG, "fire_hold_frames", 4)))
CLIENT_IDLE_TIMEOUT_S = max(1.0, float(os.environ.get("DQN_CLIENT_IDLE_TIMEOUT_S", "30.0")))


def _apply_fire_hold(cs: dict, raw_fire: int) -> int:
    """Fixed-cadence fire hold.  Returns the effective fire direction to send.

    While a hold is active the previously latched direction is kept and the
    counter decremented; once it expires the freshly requested direction is
    accepted and the hold window restarts.  Fire indices are in model space
    (0-7 = direction, 8 = idle)."""
    cs["fire_pending_dir"] = int(raw_fire)
    count = cs.get("fire_hold_count", 0)
    if count > 0:
        cs["fire_hold_count"] = count - 1
        return int(cs.get("fire_hold_dir", raw_fire))
    next_fire = int(cs.get("fire_pending_dir", raw_fire))
    cs["fire_hold_dir"] = next_fire
    cs["fire_hold_count"] = FIRE_HOLD_FRAMES - 1
    return next_fire


# ── Frame data (parsed from wire) ───────────────────────────────────────────
@dataclass
class FrameData:
    state: np.ndarray
    subjreward: float
    objreward: float
    done: bool
    player_alive: bool
    save_signal: bool
    start_pressed: bool
    level_number: int
    game_score: int
    num_lasers: int
    preview_bytes: int = 0


_HDR_FMT = ">HddBIBBBIBB"
_HDR_SIZE = struct.calcsize(_HDR_FMT)


def parse_frame_data(data: bytes) -> Optional[FrameData]:
    """Parse the Robotron binary wire protocol from Lua."""
    if not data or len(data) < _HDR_SIZE:
        return None
    try:
        (n, subj, obj, done, score, alive, save,
         start, replay, lasers, wave) = struct.unpack(_HDR_FMT, data[:_HDR_SIZE])
    except struct.error:
        return None
    base_len = _HDR_SIZE + n * 4
    if len(data) < base_len:
        return None
    state = np.frombuffer(data[_HDR_SIZE:base_len], dtype=">f4", count=n).astype(np.float32)
    if state.shape[0] != n:
        return None
    preview_bytes = 0
    if len(data) >= base_len + 4:
        try:
            preview_len = int(struct.unpack(">I", data[base_len:base_len + 4])[0])
            if preview_len > 0 and len(data) >= base_len + 4 + preview_len:
                preview_bytes = preview_len
        except struct.error:
            preview_bytes = 0
    return FrameData(
        state=state, subjreward=float(subj), objreward=float(obj),
        done=bool(done), player_alive=bool(alive), save_signal=bool(save),
        start_pressed=bool(start), level_number=int(wave),
        game_score=int(score), num_lasers=int(lasers), preview_bytes=preview_bytes,
    )


def _transition_interest_score(prev_state: np.ndarray, next_state: np.ndarray,
                               frame, obj_r: float, total_r: float) -> float:
    """Sparse rare/elite-event score for replay sampling, independent of TD error."""
    try:
        cfg = RL_CONFIG
        object_start = int(getattr(cfg, "global_features", 40))
        object_count = int(getattr(cfg, "object_token_count", getattr(cfg, "enemy_token_count", 96)))
        object_features = int(getattr(cfg, "object_token_features", getattr(cfg, "enemy_token_features", 10)))

        def object_cues(state):
            rows = np.asarray(
                state[object_start:object_start + object_count * object_features],
                dtype=np.float32,
            ).reshape(object_count, object_features)
            present = rows[:, 0] > 0.5
            if not np.any(present):
                return 0.0, 0.0, 0.0, 0.0, 0.0
            active = rows[present]
            dist = np.clip(active[:, 3], 0.0, 1.0)
            threat = np.clip(active[:, 6], 0.0, 1.0)
            ttc = np.clip(active[:, 8], 0.0, 1.0) if object_features > 8 else np.ones_like(dist)
            destructible = np.clip(active[:, 12], 0.0, 1.0) if object_features > 12 else np.ones_like(dist)
            blocker = np.clip(active[:, 13], 0.0, 1.0) if object_features > 13 else np.zeros_like(dist)
            rescue = np.clip(active[:, 14], 0.0, 1.0) if object_features > 14 else np.zeros_like(dist)
            projectile = np.clip(active[:, 15], 0.0, 1.0) if object_features > 15 else np.zeros_like(dist)
            closeness = 1.0 - dist
            imminent = 1.0 - ttc
            danger_cue = np.maximum.reduce((
                closeness * threat,
                closeness * imminent * (0.4 + 0.6 * projectile),
                closeness * blocker,
            ))
            target_cue = closeness * (0.25 + 0.75 * np.maximum(destructible, projectile)) * (
                0.5 + 0.5 * np.maximum(threat, projectile)
            ) * (1.0 - 0.95 * rescue)
            danger = float(np.nanmax(danger_cue))
            blocker_cue = float(np.nanmax(closeness * blocker))
            target = float(np.nanmax(target_cue))
            rescue_cue = float(np.nanmax(closeness * rescue))
            crowd = float(min(1.0, active.shape[0] / 32.0))
            return danger, blocker_cue, crowd, target, rescue_cue

        prev_danger, prev_blocker, prev_crowd, prev_target, prev_rescue = object_cues(prev_state)
        next_danger, next_blocker, next_crowd, next_target, next_rescue = object_cues(next_state)
        danger = max(prev_danger, next_danger)
        blocker = max(prev_blocker, next_blocker)
        crowd = max(prev_crowd, next_crowd)
        target = max(prev_target, next_target)
        rescue = max(prev_rescue, next_rescue)

        prev_wave = 0.0
        if len(prev_state) > 4 and np.isfinite(prev_state[4]):
            prev_wave = float(prev_state[4]) * 40.0
        wave = max(1.0, float(frame.level_number))
        wave_advance = 1.0 if wave > prev_wave + 0.5 else 0.0
        deep_wave = max(0.0, min(1.0, (wave - 3.0) / 8.0))
        terminal = 1.0 if frame.done else 0.0

        def ramp(value: float, start: float) -> float:
            return max(0.0, min(1.0, (float(value) - float(start)) / max(1e-6, 1.0 - float(start))))

        score_burst = max(0.0, min(1.0, max(0.0, float(obj_r)) / 5.0))
        positive_surprise = max(0.0, min(1.0, max(0.0, float(total_r)) / 5.0))
        danger_event = ramp(danger, 0.55)
        blocker_event = ramp(blocker, 0.65)
        crowd_event = ramp(crowd, 0.55)
        target_event = ramp(target, 0.55)
        rescue_event = ramp(rescue, 0.55)
        deep_tactical = deep_wave * max(danger_event, blocker_event, crowd_event, target_event)

        return max(
            score_burst,
            0.95 * wave_advance,
            0.90 * terminal,
            0.75 * danger_event,
            0.60 * blocker_event,
            0.70 * target_event,
            0.65 * crowd_event,
            0.50 * rescue_event,
            0.55 * deep_tactical,
            0.35 * positive_surprise,
        )
    except Exception:
        return 0.0


def _clip_abs(value: float, limit: float) -> float:
    limit = max(0.0, float(limit))
    return max(-limit, min(limit, float(value)))


def _destructible_target_count(model_state) -> int | None:
    """Count current targetable objects in the compact model state."""
    if model_state is None:
        return None
    try:
        arr = np.asarray(model_state, dtype=np.float32)
        start = int(getattr(RL_CONFIG, "global_features", 0))
        count = int(getattr(RL_CONFIG, "object_token_count", 0))
        feats = int(getattr(RL_CONFIG, "object_token_features", 0))
        if count <= 0 or feats <= 0 or arr.size < start + count * feats:
            return None
        rows = arr[start:start + count * feats].reshape(count, feats)
        present = rows[:, 0] > 0.5
        destructible = rows[:, 12] > 0.5 if feats > 12 else present
        rescue = rows[:, 14] > 0.5 if feats > 14 else np.zeros_like(present, dtype=bool)
        return int(np.count_nonzero(present & destructible & ~rescue))
    except Exception:
        return None


def _no_human_delay_penalty(frame, score_delta: int, model_state=None) -> float:
    penalty = max(0.0, float(getattr(RL_CONFIG, "no_human_delay_penalty", 0.0)))
    if penalty <= 0.0 or bool(frame.done) or not bool(frame.player_alive) or int(score_delta) > 0:
        return 0.0

    try:
        state = frame.state
        human_frac = float(state[13]) if len(state) > 13 else 1.0
        nearest_enemy_dist = float(state[9]) if len(state) > 9 else 1.0
    except Exception:
        return 0.0
    if not np.isfinite(human_frac) or not np.isfinite(nearest_enemy_dist):
        return 0.0

    # core[13] is num_humans/255 and core[9] is nearest enemy distance.
    # Penalize only when a live enemy appears to remain, avoiding wave gaps.
    target_count = _destructible_target_count(model_state)
    max_targets = max(1, int(getattr(RL_CONFIG, "no_human_delay_max_targets", 2)))
    if target_count is not None and target_count > max_targets:
        return 0.0
    if human_frac <= 1e-6 and nearest_enemy_dist < 0.999:
        return -penalty
    return 0.0


def _shape_transition_reward(frame, last_game_score: int, model_state=None) -> tuple[float, float, float, float, int]:
    """Reward from actual score delta plus tightly clipped subjective shaping."""
    try:
        score_delta = max(0, int(frame.game_score) - int(last_game_score))
    except Exception:
        score_delta = 0
    score_r = min(
        float(score_delta) * float(RL_CONFIG.score_reward_scale),
        float(RL_CONFIG.score_reward_clip),
    )
    subj_r = _clip_abs(
        float(frame.subjreward) * float(RL_CONFIG.subj_reward_scale),
        float(RL_CONFIG.shaping_reward_clip),
    )
    subj_r += _no_human_delay_penalty(frame, score_delta, model_state=model_state)
    death_r = -float(getattr(RL_CONFIG, "death_penalty", 0.0)) if bool(frame.done) else 0.0
    total_r = score_r + subj_r + death_r
    total_r = _clip_abs(total_r, float(RL_CONFIG.death_reward_clip if frame.done else RL_CONFIG.reward_clip))
    return total_r, score_r, subj_r, death_r, score_delta


# ── Async buffer (queues step() calls to avoid blocking the frame loop) ─────
class AsyncReplayBuffer:
    def __init__(self, agent, batch_size=100, max_queue_size=20000):
        self.agent = agent
        self.batch_size = batch_size
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.running = True
        self._lookback = int(getattr(RL_CONFIG, "pre_death_lookback", 120))
        self._client_indices = {}          # client_id -> deque(maxlen=lookback)
        self._episode_indices = {}         # client_id -> replay indices for current episode
        # Drop accounting (queue overflow on non-critical frames only)
        self.dropped_steps = 0
        self._drop_lock = threading.Lock()
        self._last_drop_warn = 0.0
        self._thread = threading.Thread(target=self._consume, daemon=True)
        self._thread.start()

    def _record_drop(self, n=1):
        with self._drop_lock:
            self.dropped_steps += n
            total = self.dropped_steps
            now = time.time()
            warn = (now - self._last_drop_warn) >= 10.0
            if warn:
                self._last_drop_warn = now
        try:
            metrics.note_replay_drop(n)
        except Exception:
            pass
        if warn:
            print(f"[WARN] Replay queue saturated — dropped {total:,} non-terminal "
                  f"transitions so far (consumer can't keep up)")

    def step_async(self, *args, client_id=None, **kwargs):
        is_terminal = bool(args[4]) if len(args) > 4 else False
        item = ("step", client_id, args, kwargs)
        try:
            self.queue.put_nowait(item)
        except queue.Full:
            if is_terminal:
                try:
                    self.queue.put(item, timeout=0.25)
                    return
                except queue.Full:
                    pass
            self._record_drop()

    def boost_pre_death(self, client_id):
        try:
            self.queue.put_nowait(("boost", client_id, None, None))
        except queue.Full:
            try:
                self.queue.put(("boost", client_id, None, None), timeout=0.25)
                return
            except queue.Full:
                pass
            self._record_drop()

    def boost_elite_episode(self, client_id, score: int, level: int, total_reward: float, ep_len: int):
        try:
            self.queue.put_nowait(("elite", client_id, (int(score), int(level), float(total_reward), int(ep_len)), None))
        except queue.Full:
            try:
                self.queue.put(("elite", client_id, (int(score), int(level), float(total_reward), int(ep_len)), None), timeout=0.25)
                return
            except queue.Full:
                pass
            self._record_drop()

    def _consume(self):
        while self.running:
            try:
                item = self.queue.get(timeout=0.01)
            except queue.Empty:
                continue
            batch = [item]
            while len(batch) < self.batch_size:
                try:
                    batch.append(self.queue.get_nowait())
                except queue.Empty:
                    break
            for cmd, cid, a, kw in batch:
                try:
                    if cmd == "step":
                        idx = self.agent.step(*a, **kw)
                        if cid is not None and idx is not None and idx >= 0:
                            if cid not in self._client_indices:
                                self._client_indices[cid] = deque(maxlen=self._lookback)
                            self._client_indices[cid].append(idx)
                            if cid not in self._episode_indices:
                                self._episode_indices[cid] = []
                            self._episode_indices[cid].append(idx)
                    elif cmd == "boost":
                        self._do_boost(cid)
                    elif cmd == "elite":
                        self._do_elite_episode_boost(cid, *(a or (0, 0, 0.0, 0)))
                except Exception as e:
                    print(f"AsyncReplayBuffer error: {e}")

    def _do_boost(self, client_id):
        indices = self._client_indices.get(client_id)
        if not indices:
            return
        penalized = 0
        try:
            penalized = int(self.agent.memory.apply_pre_death_penalty(list(indices)) or 0)
        except Exception as e:
            print(f"  Pre-death reward penalty error: {e}")
        if penalized > 0:
            try:
                metrics.note_pre_death_penalty(penalized)
            except Exception:
                pass
        boost = float(getattr(RL_CONFIG, "pre_death_priority_boost", 2.0))
        if boost <= 1.0:
            indices.clear()
            return
        try:
            self.agent.memory.boost_priorities(list(indices), boost)
        except Exception as e:
            print(f"  Pre-death boost error: {e}")
        indices.clear()

    def _do_elite_episode_boost(self, client_id, score: int, level: int, total_reward: float, ep_len: int):
        indices = self._episode_indices.get(client_id)
        if not indices:
            return
        try:
            elite = (
                int(score) >= int(getattr(RL_CONFIG, "elite_episode_score_threshold", 120_000))
                or int(level) >= int(getattr(RL_CONFIG, "elite_episode_level_threshold", 8))
            )
            if elite:
                tail_len = max(1, int(getattr(RL_CONFIG, "elite_episode_tail_len", 768)))
                tail = list(indices)[-tail_len:]
                boost = float(getattr(RL_CONFIG, "elite_episode_priority_boost", 3.0))
                interest = float(getattr(RL_CONFIG, "elite_episode_interest_score", 1.0))
                self.agent.memory.boost_priorities(tail, boost)
                self.agent.memory.mark_interesting(tail, interest)
        except Exception as e:
            print(f"  Elite episode boost error: {e}")
        finally:
            indices.clear()

    def remove_client(self, client_id):
        self._client_indices.pop(client_id, None)
        self._episode_indices.pop(client_id, None)

    def stop(self):
        self.running = False
        while True:
            try:
                cmd, cid, a, kw = self.queue.get_nowait()
                if cmd == "step" and a is not None:
                    self.agent.step(*a, **kw)
                elif cmd == "boost":
                    self._do_boost(cid)
                elif cmd == "elite":
                    self._do_elite_episode_boost(cid, *(a or (0, 0, 0.0, 0)))
            except queue.Empty:
                break
            except Exception:
                pass
        self._thread.join(timeout=5.0)


class _InferenceRequest:
    __slots__ = ("state", "epsilon", "locked_fire", "event", "action")

    def __init__(self, state, epsilon: float, locked_fire=None):
        self.state = state
        self.epsilon = float(epsilon)
        self.locked_fire = locked_fire
        self.event = threading.Event()
        self.action = None


class AsyncInferenceBatcher:
    """Micro-batch inference requests across clients for better throughput."""

    def __init__(self, agent, max_batch_size=32, max_wait_ms=1.0, request_timeout_ms=50.0):
        self.agent = agent
        self.max_batch_size = max(1, int(max_batch_size))
        self.max_wait_s = max(0.0, float(max_wait_ms) / 1000.0)
        self.request_timeout_s = max(0.001, float(request_timeout_ms) / 1000.0)
        self.queue = queue.Queue(maxsize=20000)
        self.running = True
        self._thread = threading.Thread(target=self._consume, daemon=True, name="InferBatchWorker")
        self._thread.start()

    def infer(self, state, epsilon: float, locked_fire=None):
        if not self.running:
            return self.agent.act(state, epsilon, locked_fire=locked_fire)
        req = _InferenceRequest(state, epsilon, locked_fire=locked_fire)
        try:
            self.queue.put(req, timeout=self.request_timeout_s)
        except queue.Full:
            return self.agent.act(state, epsilon, locked_fire=locked_fire)
        if not req.event.wait(timeout=self.request_timeout_s):
            return self.agent.act(state, epsilon, locked_fire=locked_fire)
        return req.action if req.action is not None else (0, 0, False)

    def _consume(self):
        while self.running or not self.queue.empty():
            try:
                first = self.queue.get(timeout=0.01)
            except queue.Empty:
                continue

            batch = [first]
            deadline = time.perf_counter() + self.max_wait_s
            while len(batch) < self.max_batch_size:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    break
                try:
                    batch.append(self.queue.get(timeout=remaining))
                except queue.Empty:
                    break

            try:
                states = [r.state for r in batch]
                epsilons = [r.epsilon for r in batch]
                locked_fires = [r.locked_fire for r in batch]
                actions = self.agent.act_batch(states, epsilons, locked_fires=locked_fires)
            except Exception as e:
                print(f"AsyncInferenceBatcher error: {e}")
                actions = []

            for idx, req in enumerate(batch):
                act = actions[idx] if idx < len(actions) else None
                if act is None:
                    try:
                        act = self.agent.act(req.state, req.epsilon, locked_fire=req.locked_fire)
                    except Exception:
                        act = (0, 0, False)
                req.action = act
                req.event.set()

    def stop(self):
        self.running = False
        self._thread.join(timeout=5.0)
        while True:
            try:
                req = self.queue.get_nowait()
            except queue.Empty:
                break
            req.action = (0, 0, False)
            req.event.set()


# ── Socket Server ───────────────────────────────────────────────────────────
class SocketServer:
    def __init__(self, host, port, agent, metrics_wrapper=None):
        self.host = host
        self.port = port
        self.agent = agent
        self.async_buffer = AsyncReplayBuffer(agent) if agent else None
        self.inference_batcher = None
        if agent and bool(getattr(RL_CONFIG, "inference_batching_enabled", True)):
            self.inference_batcher = AsyncInferenceBatcher(
                agent,
                max_batch_size=int(getattr(RL_CONFIG, "inference_batch_max_size", 32)),
                max_wait_ms=float(getattr(RL_CONFIG, "inference_batch_wait_ms", 1.0)),
                request_timeout_ms=float(getattr(RL_CONFIG, "inference_request_timeout_ms", 50.0)),
            )
            print(
                "Async inference batching enabled: "
                f"max_batch={self.inference_batcher.max_batch_size}, "
                f"wait_ms={self.inference_batcher.max_wait_s * 1000.0:.2f}"
            )
        self.metrics = metrics_wrapper if metrics_wrapper is not None else metrics

        self.server_socket = None
        self.running = False
        self.shutdown_event = threading.Event()

        self.clients = {}
        self.client_states = {}
        self.client_lock = threading.Lock()
        self._last_preview_payload_warn = 0.0

    def _alloc_id(self):
        with self.client_lock:
            cid = 0
            while cid in self.client_states or self.clients.get(cid) is not None:
                cid += 1
            return cid

    def _sync_client_count_locked(self):
        count = len(self.client_states)
        metrics.client_count = count
        if self.metrics is not metrics:
            try:
                self.metrics.client_count = count
            except Exception:
                pass
        return count

    @staticmethod
    def _is_eval_client(cid: int) -> bool:
        stride = int(getattr(RL_CONFIG, "eval_client_stride", 0))
        if stride <= 0:
            return False
        offset = int(getattr(RL_CONFIG, "eval_client_offset", stride - 1)) % stride
        return (int(cid) % stride) == offset

    @staticmethod
    def _expert_guidance_mode() -> str:
        mode = str(getattr(RL_CONFIG, "expert_guidance_mode", "episode")).strip().lower()
        if mode in ("frame", "per_frame", "per-frame"):
            return "frame"
        return "episode"

    @staticmethod
    def _reset_episode_control(cs: dict) -> None:
        cs["episode_control_initialized"] = False
        cs["episode_use_expert"] = False

    def _episode_expert_enabled(self, cs: dict, eval_only: bool) -> bool:
        """Return whether the current playable episode should use expert actions."""
        expert_ratio = 0.0 if eval_only else metrics.get_expert_ratio()
        force_off = bool(eval_only or metrics.override_expert or get_expert_action is None or expert_ratio <= 0.0)
        if force_off:
            cs["episode_control_initialized"] = True
            cs["episode_use_expert"] = False
            return False

        force_on = bool(getattr(metrics, "expert_mode", False) or expert_ratio >= 0.999)
        if force_on:
            cs["episode_control_initialized"] = True
            cs["episode_use_expert"] = True
            return True

        if not bool(cs.get("episode_control_initialized", False)):
            cs["episode_use_expert"] = bool(random.random() < expert_ratio)
            cs["episode_control_initialized"] = True
        return bool(cs.get("episode_use_expert", False))

    def _init_client(self, cid):
        n = max(1, int(getattr(RL_CONFIG, "n_step", 1)))
        gamma = float(getattr(RL_CONFIG, "gamma", 0.99))
        nstep = NStepReplayBuffer(n_step=n, gamma=gamma) if n > 1 else None
        eval_only = self._is_eval_client(cid)
        with self.client_lock:
            self.client_states[cid] = {
                "frames": 0, "last_time": time.time(), "fps": 0.0,
                "level_number": 0, "game_score": 0, "last_state": None, "last_action": None,
                "last_advisor_action": None,
                "last_game_score": 0,
                "prev_action_source": None,
                "total_reward": 0.0, "ep_dqn_reward": 0.0, "ep_dqn_score_reward": 0.0, "ep_expert_reward": 0.0,
                "ep_subj_reward": 0.0, "ep_obj_reward": 0.0, "ep_frames": 0,
                "ep_death_reward": 0.0,
                "ep_dqn_frames": 0,
                "eval_only": eval_only,
                "episode_control_initialized": False, "episode_use_expert": False,
                "was_done": False, "nstep": nstep,
                "frame_history": deque(maxlen=max(1, int(getattr(RL_CONFIG, "frame_stack", 1)))),
                "fire_hold_dir": -1, "fire_hold_count": 0, "fire_pending_dir": -1,
            }
            self._sync_client_count_locked()

    @staticmethod
    def _stack_model_state(cs: dict, current_state: np.ndarray) -> np.ndarray:
        depth = max(1, int(getattr(RL_CONFIG, "frame_stack", 1)))
        cur = np.asarray(current_state, dtype=np.float32)
        if depth <= 1:
            return cur
        hist = cs.get("frame_history")
        if hist is None or getattr(hist, "maxlen", None) != depth:
            hist = deque(maxlen=depth)
            cs["frame_history"] = hist
        hist.append(cur.copy())
        frames = list(hist)
        if len(frames) < depth:
            pad = frames[0] if frames else cur
            frames = [pad] * (depth - len(frames)) + frames
        return np.concatenate(list(reversed(frames[-depth:]))).astype(np.float32, copy=False)

    @staticmethod
    def _recv_exact(sock, n, timeout_s=0.5):
        """Read exactly *n* bytes; return None on timeout, b"" on EOF/socket error."""
        buf = bytearray()
        deadline = time.time() + timeout_s
        while len(buf) < n:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            try:
                r, _, _ = select.select([sock], [], [], min(0.05, remaining))
            except (OSError, ValueError):
                return b""
            if not r:
                continue
            try:
                chunk = sock.recv(n - len(buf))
            except BlockingIOError:
                continue
            except OSError:
                return b""
            if not chunk:
                return b""
            buf += chunk
        return bytes(buf)

    def _pack_action(self, move_cmd, fire_cmd, source_code, cid: int = 0):
        _gs = game_settings.snapshot()
        start_adv = 1 if _gs["start_advanced"] or bool(_gs.get("auto_curriculum", False)) else 0
        base_level = max(1, min(255, int(_gs["start_level_min"])))
        if bool(_gs.get("auto_curriculum", False)):
            base_level = max(base_level, int(getattr(RL_CONFIG, "hard_start_min_level", 5)))
        start_level = base_level
        if bool(_gs.get("auto_curriculum", False)):
            spread = max(1, int(getattr(RL_CONFIG, "hard_start_wave_spread", 1)))
            start_level = base_level + (int(cid) % spread)
        start_level = max(1, min(255, int(start_level)))
        raw_source = int(source_code) & 0xFF
        source_u8 = raw_source & 0x0F
        return struct.pack(">bbBBB", int(move_cmd), int(fire_cmd),
                           source_u8, start_adv, start_level)

    def handle_client(self, sock, cid):
        local_accum = 0
        try:
            sock.setblocking(False)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)

            # Handshake — 2-byte value (preview capability / slot; unused here)
            ping = self._recv_exact(sock, 2, timeout_s=5.0)
            if not ping or len(ping) < 2:
                raise ConnectionError("No handshake")

            BATCH = 8
            last_payload_time = time.time()

            while self.running and not self.shutdown_event.is_set():
                # Read 4-byte length header
                hdr = self._recv_exact(sock, 4, timeout_s=0.25)
                if hdr is None:
                    if time.time() - last_payload_time >= CLIENT_IDLE_TIMEOUT_S:
                        raise ConnectionError(
                            f"idle timeout ({CLIENT_IDLE_TIMEOUT_S:.1f}s without frames)"
                        )
                    continue
                if len(hdr) < 4:
                    raise ConnectionError("EOF")
                dlen = struct.unpack(">I", hdr)[0]
                if dlen <= 0 or dlen > _MAX_FRAME_PAYLOAD_BYTES:
                    raise ConnectionError(f"Invalid payload length {dlen}")

                data = self._recv_exact(sock, dlen, timeout_s=0.5)
                if data is None or len(data) < dlen:
                    raise ConnectionError("Broken payload")
                last_payload_time = time.time()

                if len(data) >= 2:
                    n = struct.unpack(">H", data[:2])[0]
                    if n != WIRE_PARAMS_COUNT:
                        print(f"Client {cid}: param mismatch {n} != {WIRE_PARAMS_COUNT}")
                        break
                else:
                    break

                frame = parse_frame_data(data)
                if not frame:
                    sock.sendall(self._pack_action(-1, -1, _SRC_NONE, cid))
                    continue
                if int(getattr(frame, "preview_bytes", 0)) > 0:
                    try:
                        self.metrics.note_preview_payload(int(frame.preview_bytes))
                    except Exception:
                        pass
                    now_warn = time.time()
                    if now_warn - self._last_preview_payload_warn >= 10.0:
                        self._last_preview_payload_warn = now_warn
                        print(
                            f"[WARN] Client {cid} sent preview payload "
                            f"({int(frame.preview_bytes):,} bytes) while preview is disabled by default",
                            flush=True,
                        )

                # Single-frame compact input; stacked current-first with recent history.
                single_state = slice_model_state(frame.state)

                with self.client_lock:
                    if cid not in self.client_states:
                        break
                    cs = self.client_states[cid]
                    cs["frames"] += 1
                    client_frame_count = int(cs["frames"])
                    cs["level_number"] = frame.level_number
                    cs["game_score"] = frame.game_score
                    now = time.time()
                    el = now - cs["last_time"]
                    if el >= 1.0:
                        cs["fps"] = 1.0 / el
                        cs["last_time"] = now

                model_state = self._stack_model_state(cs, single_state)
                diag_every = max(1, int(getattr(RL_CONFIG, "tactical_diagnostics_sample_every", 30)))
                if client_frame_count % diag_every == 0:
                    try:
                        metrics.note_tactical_diagnostics(extract_tactical_diagnostics(frame.state, single_state))
                    except Exception:
                        pass

                # Peak game score is shared metrics state — guard with metrics.lock
                # (not client_lock) to stay consistent with dashboard reads.
                metrics.note_game_score(frame.game_score)

                local_accum += 1
                if local_accum >= BATCH:
                    metrics.update_frame_count(delta=local_accum)
                    local_accum = 0
                    metrics.update_epsilon()
                    metrics.update_expert_ratio()
                    self._calc_avg_game_state()

                # ── Process previous step ───────────────────────────────
                if cs.get("last_state") is not None and cs.get("last_action") is not None:
                    mv_i, fr_i = cs["last_action"]
                    total_r, score_r, subj_r, death_r, score_delta = _shape_transition_reward(
                        frame, cs.get("last_game_score", frame.game_score), model_state=model_state)
                    interest = _transition_interest_score(cs["last_state"], model_state, frame, score_r, total_r)

                    eval_only = bool(cs.get("eval_only", False))
                    if self.agent and not eval_only:
                        tag = cs.get("prev_action_source", "dqn")
                        nstep = cs.get("nstep")
                        if nstep is not None:
                            joint = combine_action(mv_i, fr_i)
                            advisor = cs.get("last_advisor_action")
                            advisor_joint = combine_action(advisor[0], advisor[1]) if advisor is not None else -1
                            matured = nstep.add(cs["last_state"], joint, total_r,
                                                model_state, bool(frame.done),
                                                actor=tag, priority_reward=total_r,
                                                interest=interest,
                                                advisor_action=advisor_joint)
                            for s0, a, Rn, pR, sn, dn, h, act, intr, adv in matured:
                                mv_n, fr_n = split_joint_action(a)
                                self.async_buffer.step_async(
                                    s0, (mv_n, fr_n), Rn, sn, bool(dn),
                                    client_id=cid, actor=act, horizon=int(h), priority_reward=pR,
                                    interest=intr, advisor_action=adv)
                        else:
                            self.async_buffer.step_async(
                                cs["last_state"], (mv_i, fr_i), total_r,
                                model_state, bool(frame.done), client_id=cid,
                                actor=tag, horizon=1, priority_reward=total_r,
                                interest=interest, advisor_action=cs.get("last_advisor_action"))

                    cs["total_reward"] += total_r
                    cs["ep_subj_reward"] = cs.get("ep_subj_reward", 0.0) + subj_r
                    cs["ep_obj_reward"] = cs.get("ep_obj_reward", 0.0) + score_r
                    cs["ep_death_reward"] = cs.get("ep_death_reward", 0.0) + death_r
                    cs["ep_frames"] = cs.get("ep_frames", 0) + 1
                    src = cs.get("prev_action_source")
                    if eval_only:
                        pass
                    elif src in ("dqn", "epsilon"):
                        cs["ep_dqn_reward"] += total_r
                        cs["ep_dqn_score_reward"] = cs.get("ep_dqn_score_reward", 0.0) + score_r
                        cs["ep_dqn_frames"] = cs.get("ep_dqn_frames", 0) + 1
                    elif src == "expert":
                        cs["ep_expert_reward"] += total_r

                # ── Terminal ────────────────────────────────────────────
                if frame.done:
                    eval_only = bool(cs.get("eval_only", False))
                    if self.async_buffer is not None and not eval_only:
                        self.async_buffer.boost_pre_death(cid)
                    if not cs.get("was_done", False):
                        ep_len = cs.get("ep_frames", 0)
                        if eval_only:
                            metrics.add_eval_episode_reward(
                                cs["total_reward"], frame.game_score, frame.level_number, length=ep_len)
                        else:
                            metrics.note_completed_game_score(frame.game_score)
                            metrics.add_episode_reward(
                                cs["total_reward"], cs["ep_dqn_reward"], cs["ep_expert_reward"],
                                cs.get("ep_subj_reward", 0.0), cs.get("ep_obj_reward", 0.0),
                                cs.get("ep_death_reward", 0.0),
                                length=ep_len)
                            if self.async_buffer is not None:
                                self.async_buffer.boost_elite_episode(
                                    cid, frame.game_score, frame.level_number,
                                    cs["total_reward"], ep_len)
                            try:
                                ep_dqn = cs.get("ep_dqn_score_reward", cs["ep_dqn_reward"])
                                ep_dqn_frames = cs.get("ep_dqn_frames", 0)
                                add_episode_to_dqn100k_window(ep_dqn, ep_len, ep_dqn_frames)
                                add_episode_to_dqn1m_window(ep_dqn, ep_len, ep_dqn_frames)
                                add_episode_to_dqn5m_window(ep_dqn, ep_len, ep_dqn_frames)
                                add_episode_to_dqn_perframe_window(ep_dqn, ep_dqn_frames, ep_len)
                                add_episode_to_total_windows(cs["total_reward"], ep_len)
                                add_episode_to_eplen_window(ep_len)
                            except Exception:
                                pass
                    cs["was_done"] = True
                    try:
                        sock.sendall(self._pack_action(-1, -1, _SRC_NONE, cid))
                    except Exception:
                        break
                    cs["last_state"] = cs["last_action"] = None
                    cs["last_advisor_action"] = None
                    cs["prev_action_source"] = None
                    cs["total_reward"] = cs["ep_dqn_reward"] = cs["ep_dqn_score_reward"] = cs["ep_expert_reward"] = 0.0
                    cs["ep_subj_reward"] = cs["ep_obj_reward"] = cs["ep_death_reward"] = 0.0
                    cs["ep_frames"] = 0
                    cs["ep_dqn_frames"] = 0
                    self._reset_episode_control(cs)
                    cs["fire_hold_dir"] = -1
                    cs["fire_hold_count"] = 0
                    cs["fire_pending_dir"] = -1
                    hist = cs.get("frame_history")
                    if hist is not None:
                        hist.clear()
                    continue

                if cs.get("was_done"):
                    cs["was_done"] = False
                    cs["total_reward"] = cs["ep_dqn_reward"] = cs["ep_dqn_score_reward"] = cs["ep_expert_reward"] = 0.0
                    cs["ep_subj_reward"] = cs["ep_obj_reward"] = cs["ep_death_reward"] = 0.0
                    cs["ep_frames"] = 0
                    cs["ep_dqn_frames"] = 0
                    self._reset_episode_control(cs)

                # ── Not playable (death animation / between lives) ──────
                if not frame.player_alive:
                    cs["last_state"] = cs["last_action"] = None
                    cs["last_advisor_action"] = None
                    cs["prev_action_source"] = None
                    self._reset_episode_control(cs)
                    cs["fire_hold_dir"] = -1
                    cs["fire_hold_count"] = 0
                    cs["fire_pending_dir"] = -1
                    hist = cs.get("frame_history")
                    if hist is not None:
                        hist.clear()
                    if (cs.get("nstep") is not None):
                        cs["nstep"].reset()
                    try:
                        sock.sendall(self._pack_action(-1, -1, _SRC_NONE, cid))
                    except Exception:
                        break
                    continue

                # ── Choose action ───────────────────────────────────────
                metrics.increment_total_controls()
                mv_idx, fr_idx = 8, 8           # idle defaults
                action_source = "none"
                advisor_action = None

                # Fire-hold: while a hold is active, lock the fire direction so
                # the expert/model don't fight the cadence — keeps move quality
                # and the stored action consistent with what the game does.
                fire_update_open = cs.get("fire_hold_count", 0) <= 0
                locked_fire = None
                if not fire_update_open:
                    held = cs.get("fire_hold_dir", -1)
                    locked_fire = max(0, min(8, held)) if held >= 0 else 8

                if self.agent:
                    eval_only = bool(cs.get("eval_only", False))
                    expert_ratio = 0.0 if eval_only else metrics.get_expert_ratio()
                    if (
                        bool(getattr(RL_CONFIG, "advisor_labels_enabled", True))
                        and not eval_only
                        and get_expert_action is not None
                    ):
                        try:
                            wave = max(1, int(frame.level_number))
                            adv_mv, adv_fr = get_expert_action(frame.state, wave, locked_fire=locked_fire)
                            advisor_action = (int(adv_mv), int(adv_fr))
                        except Exception:
                            advisor_action = None
                    if self._expert_guidance_mode() == "frame":
                        use_expert = (
                            (random.random() < expert_ratio)
                            and not metrics.override_expert
                            and not eval_only
                            and get_expert_action is not None
                        )
                    else:
                        use_expert = self._episode_expert_enabled(cs, eval_only)

                    if use_expert and get_expert_action is not None:
                        # Clamp wave to >=1 like v3 — the expert's rescue/tank-wave
                        # logic keys off wave_number and misbehaves at 0.
                        if advisor_action is not None:
                            mv_idx, fr_idx = advisor_action
                        else:
                            wave = max(1, int(frame.level_number))
                            mv_idx, fr_idx = get_expert_action(frame.state, wave,
                                                               locked_fire=locked_fire)
                            advisor_action = (int(mv_idx), int(fr_idx))
                        action_source = "expert"
                    else:
                        epsilon = float(getattr(RL_CONFIG, "eval_epsilon", 0.0)) if eval_only else metrics.get_effective_epsilon()
                        t0 = time.perf_counter()
                        if self.inference_batcher is not None:
                            mv_idx, fr_idx, is_eps = self.inference_batcher.infer(model_state, epsilon, locked_fire=locked_fire)
                        else:
                            mv_idx, fr_idx, is_eps = self.agent.act(model_state, epsilon, locked_fire=locked_fire)
                        metrics.add_inference_time(time.perf_counter() - t0)
                        action_source = "eval" if eval_only else ("epsilon" if is_eps else "dqn")
                    if locked_fire is not None:
                        fr_idx = locked_fire

                if action_source in ("dqn", "epsilon"):
                    metrics.update_learner_frame_count()

                # Apply fire hold → the effective fire is what we send AND store.
                effective_fire = _apply_fire_hold(cs, int(fr_idx))

                cs["last_state"] = model_state
                cs["last_action"] = (int(mv_idx), int(effective_fire))
                if advisor_action is not None:
                    adv_mv, adv_fr = advisor_action
                    cs["last_advisor_action"] = (int(adv_mv), int(adv_fr))
                else:
                    cs["last_advisor_action"] = None
                cs["last_game_score"] = int(frame.game_score)
                cs["prev_action_source"] = action_source

                move_cmd = action_index_to_wire_dir(int(mv_idx))
                fire_cmd = action_index_to_wire_dir(int(effective_fire))
                src_code = {"dqn": _SRC_DQN, "epsilon": _SRC_EPSILON,
                            "expert": _SRC_EXPERT, "eval": _SRC_EVAL}.get(action_source, _SRC_NONE)

                if _DBG_ACTIONS:
                    dn = cs.get("dbg_n", 0) + 1
                    cs["dbg_n"] = dn
                    if dn % _DBG_EVERY == 0:
                        try:
                            from v3.state_processor import _collect_entity_slots as _ces
                            slots = _ces(np.asarray(frame.state, dtype=np.float32))
                            nh = sum(1 for s in slots if s["pool"] == "human")
                            nd = sum(1 for s in slots if s["pool"] == "danger")
                        except Exception as _e:
                            slots, nh, nd = [], -1, -1
                        try:
                            mq, fq = self.agent.debug_q_spread(model_state)
                            mspread = max(mq) - min(mq)
                            fspread = max(fq) - min(fq)
                            qinfo = (f"mQ[{min(mq):+.2f},{max(mq):+.2f}]d{mspread:.3f} "
                                     f"fQ[{min(fq):+.2f},{max(fq):+.2f}]d{fspread:.3f}")
                        except Exception:
                            qinfo = "qspread=err"
                        print(
                            f"[DBG] src={action_source:<7} n={len(frame.state)} "
                            f"ents={len(slots)}(H{nh}/D{nd}) wave={int(frame.level_number)} "
                            f"mv={int(mv_idx)}->{move_cmd} fr={int(effective_fire)}->{fire_cmd} "
                            f"xr={metrics.get_expert_ratio():.2f} eps={metrics.get_effective_epsilon():.2f} "
                            f"{qinfo}", flush=True)

                try:
                    sock.sendall(self._pack_action(move_cmd, fire_cmd, src_code, cid))
                except Exception:
                    break

        except ConnectionError as e:
            print(f"Client {cid} disconnected: {e}")
        except Exception as e:
            print(f"Client {cid} error: {e}")
            traceback.print_exc()
        finally:
            # Flush frames accumulated since the last batch so decay schedules
            # (epsilon / expert ratio) don't lag when a client disconnects.
            if local_accum > 0:
                try:
                    metrics.update_frame_count(delta=local_accum)
                except Exception:
                    pass
                local_accum = 0
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
            with self.client_lock:
                self.client_states.pop(cid, None)
                self.clients[cid] = None
                self._sync_client_count_locked()
            if self.async_buffer is not None:
                self.async_buffer.remove_client(cid)
            threading.Timer(1.0, self._cleanup).start()

    def _cleanup(self):
        with self.client_lock:
            dead = [k for k, v in self.clients.items() if v is None]
            for k in dead:
                del self.clients[k]
            self._sync_client_count_locked()

    def _calc_avg_game_state(self):
        try:
            with self.client_lock:
                lvls = [s.get("level_number", 0) for s in self.client_states.values() if s.get("level_number", 0) >= 0]
                scores = [s.get("game_score", 0) for s in self.client_states.values()]
                avg_level = sum(lvls) / len(lvls) if lvls else 0.0
                avg_score = sum(scores) / len(scores) if scores else 0.0
                peak_level = max(lvls) if lvls else None
            metrics.note_game_state_averages(avg_level, avg_score, peak_level)
        except Exception:
            pass

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        for i in range(10):
            try:
                if self.shutdown_event.is_set():
                    return
                self.server_socket.bind((self.host, self.port))
                break
            except OSError as e:
                if e.errno in (98, 48):
                    print(f"Port {self.port} busy, retry {i+1}/10")
                    time.sleep(1.0)
                else:
                    raise
        else:
            raise OSError(f"Cannot bind {self.host}:{self.port}")

        self.server_socket.listen(SERVER_CONFIG.max_clients)
        self.server_socket.setblocking(False)
        self.running = True
        print(f"SocketServer listening on {self.host}:{self.port}")

        try:
            while self.running and not self.shutdown_event.is_set():
                try:
                    rd, _, _ = select.select([self.server_socket], [], [], 0.05)
                except (OSError, ValueError):
                    if self.shutdown_event.is_set():
                        break
                    raise
                if not self.server_socket:
                    break
                if self.server_socket in rd:
                    try:
                        cs, addr = self.server_socket.accept()
                    except OSError:
                        continue
                    cid = self._alloc_id()
                    self._init_client(cid)
                    t = threading.Thread(target=self.handle_client, args=(cs, cid), daemon=True)
                    with self.client_lock:
                        self.clients[cid] = t
                    t.start()
        except Exception as e:
            if not self.shutdown_event.is_set():
                print(f"Server error: {e}")
                traceback.print_exc()
        finally:
            self.stop()

    def stop(self):
        if self.shutdown_event.is_set() and not self.running:
            return
        self.running = False
        self.shutdown_event.set()
        if self.inference_batcher:
            print("Stopping async inference batcher...")
            self.inference_batcher.stop()
            self.inference_batcher = None
        if self.async_buffer:
            print("Flushing async replay buffer...")
            self.async_buffer.stop()
            self.async_buffer = None
        try:
            if self.server_socket:
                try:
                    self.server_socket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.server_socket.close()
                self.server_socket = None
        except Exception:
            pass
