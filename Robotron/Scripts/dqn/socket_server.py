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
    + 112 grouped object rows); the full wire is still used by the expert/debug
    paths.
  • Episodes terminate on ``frame.done``.  While ``player_alive`` is false (death
    animation / between lives) we send a neutral action and store no transitions.
    • Reward = clipped game_score delta plus tightly bounded non-harvestable
      movement/progress shaping. Lua subjective shaping and explicit terminal
      death reward remain independently configurable.
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
                         TOKEN_GROUP_RANGES, decode_token_types,
                         TYPE_ONEHOT_OFFSET, TYPE_CLASS_COUNT,
                         STRATIFIED_TRAINING_STARTS, STRATIFIED_START_LEVELS)
    from .nstep_buffer import NStepReplayBuffer
    from .replay_buffer import ACTOR_DQN, ACTOR_EPSILON, ACTOR_EXPERT
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
                        TOKEN_GROUP_RANGES, decode_token_types,
                        TYPE_ONEHOT_OFFSET, TYPE_CLASS_COUNT,
                        STRATIFIED_TRAINING_STARTS, STRATIFIED_START_LEVELS)
    from nstep_buffer import NStepReplayBuffer
    from replay_buffer import ACTOR_DQN, ACTOR_EPSILON, ACTOR_EXPERT
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

# Wave-transition probe (diagnostic; off unless DQN_WAVE_PROBE=1)
_WAVE_PROBE = os.getenv("DQN_WAVE_PROBE", "").strip().lower() in ("1", "true", "yes", "on")

# Action source codes (low nibble of the source byte)
_SRC_NONE = 0
_SRC_DQN = 1
_SRC_EPSILON = 2
_SRC_EXPERT = 3
_SRC_EVAL = 4

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
    preview_width: int = 0
    preview_height: int = 0
    preview_format: int = 0
    preview_pixels: Optional[bytes] = None
    preview_encoded_format: int = 0
    preview_encoded_bytes: int = 0
    preview_raw_bytes: int = 0


_HDR_FMT = ">HddBIBBBIBB"
_HDR_SIZE = struct.calcsize(_HDR_FMT)

# Ingest sanity: reject crash/garbage frames at the wire boundary (see
# RL_CONFIG.max_plausible_game_score).  Read once at import like the other
# hot-path constants; a warn throttle keeps a crash burst from flooding stdout.
_MAX_PLAUSIBLE_GAME_SCORE = int(getattr(RL_CONFIG, "max_plausible_game_score", 2_000_000))
_MAX_PLAUSIBLE_PER_LEVEL = int(getattr(RL_CONFIG, "max_plausible_score_per_level", 25_000))
_MAX_SCORE_JUMP = int(getattr(RL_CONFIG, "max_plausible_score_jump", 250_000))
_last_implausible_warn_t = 0.0


def parse_frame_data(data: bytes, parse_preview: bool = False) -> Optional[FrameData]:
    """Parse the Robotron binary wire protocol from Lua."""
    if not data or len(data) < _HDR_SIZE:
        return None
    try:
        (n, subj, obj, done, score, alive, save,
         start, replay, lasers, wave) = struct.unpack(_HDR_FMT, data[:_HDR_SIZE])
    except struct.error:
        return None

    # Drop crash/garbage frames before any downstream consumer (metrics,
    # reward, replay buffer, HOF) can see them.  A game crash randomizes
    # memory and surfaces an absurd game_score; a legit per-game score never
    # approaches the ceiling, so this only ever fires on memory garbage.
    _limit = _MAX_PLAUSIBLE_GAME_SCORE + _MAX_PLAUSIBLE_PER_LEVEL * int(wave)
    if score > _limit:
        global _last_implausible_warn_t
        _now = time.time()
        if _now - _last_implausible_warn_t > 5.0:
            _last_implausible_warn_t = _now
            print(f"[INGEST] dropped implausible frame: score={score} wave={wave} "
                  f"(> {_limit} = base {_MAX_PLAUSIBLE_GAME_SCORE} + {_MAX_PLAUSIBLE_PER_LEVEL}/level); likely game crash")
        return None

    base_len = _HDR_SIZE + n * 4
    if len(data) < base_len:
        return None
    state = np.frombuffer(data[_HDR_SIZE:base_len], dtype=">f4", count=n).astype(np.float32)
    if state.shape[0] != n:
        return None

    preview_width = preview_height = preview_format = 0
    preview_pixels = None
    preview_encoded_format = preview_encoded_bytes = preview_raw_bytes = 0

    if len(data) > base_len:
        if len(data) < (base_len + 4):
            return None
        preview_len = struct.unpack(">I", data[base_len:base_len + 4])[0]
        tail_start = base_len + 4
        tail_end = tail_start + int(preview_len)
        if tail_end != len(data):
            return None
        if (not parse_preview) and preview_len > 0:
            preview_len = 0
        elif preview_len > 0 and preview_len < 5:
            return None
        if preview_len >= 5:
            preview_width, preview_height, preview_format = struct.unpack(
                ">HHB", data[tail_start:tail_start + 5]
            )
            pixels = data[tail_start + 5:tail_end]
            if preview_width <= 0 or preview_height <= 0 or len(pixels) <= 0:
                return None
            expected_px = preview_width * preview_height * 2
            pf = int(preview_format)
            preview_encoded_format = pf
            preview_encoded_bytes = len(pixels)
            preview_raw_bytes = expected_px
            if pf == 1:
                if len(pixels) != expected_px:
                    return None
                preview_pixels = bytes(pixels)
            elif pf == 2:
                out = bytearray(expected_px)
                oi = si = 0
                plen = len(pixels)
                ok = True
                while oi < expected_px and si < plen:
                    flags = pixels[si]
                    si += 1
                    for bit in range(8):
                        if oi >= expected_px:
                            break
                        if (flags >> bit) & 1:
                            if (si + 1) >= plen:
                                ok = False
                                break
                            b1, b2 = pixels[si], pixels[si + 1]
                            si += 2
                            mlen = ((b1 >> 4) & 0x0F) + 3
                            dist = ((b1 & 0x0F) << 8) | b2
                            if dist <= 0 or dist > oi:
                                ok = False
                                break
                            src_idx = oi - dist
                            for _ in range(mlen):
                                if oi >= expected_px:
                                    break
                                out[oi] = out[src_idx]
                                oi += 1
                                src_idx += 1
                        else:
                            if si >= plen:
                                ok = False
                                break
                            out[oi] = pixels[si]
                            oi += 1
                            si += 1
                    if not ok:
                        break
                if (not ok) or (oi != expected_px):
                    return None
                preview_pixels = bytes(out)
                preview_format = 1
            elif pf == 3:
                out = bytearray(expected_px)
                oi = si = 0
                plen = len(pixels)
                ok = True
                while si < plen and oi < expected_px:
                    ctrl = pixels[si]
                    si += 1
                    words = (ctrl & 0x7F) + 1
                    if (ctrl & 0x80) != 0:
                        if (si + 1) >= plen:
                            ok = False
                            break
                        b0, b1 = pixels[si], pixels[si + 1]
                        si += 2
                        need = words * 2
                        if (oi + need) > expected_px:
                            ok = False
                            break
                        for _ in range(words):
                            out[oi] = b0
                            out[oi + 1] = b1
                            oi += 2
                    else:
                        need = words * 2
                        if (si + need) > plen or (oi + need) > expected_px:
                            ok = False
                            break
                        out[oi:oi + need] = pixels[si:si + need]
                        oi += need
                        si += need
                if (not ok) or (oi != expected_px) or (si != plen):
                    return None
                preview_pixels = bytes(out)
                preview_format = 1
            else:
                return None

    return FrameData(
        state=state, subjreward=float(subj), objreward=float(obj),
        done=bool(done), player_alive=bool(alive), save_signal=bool(save),
        start_pressed=bool(start), level_number=int(wave),
        game_score=int(score), num_lasers=int(lasers),
        preview_width=int(preview_width), preview_height=int(preview_height),
        preview_format=int(preview_format), preview_pixels=preview_pixels,
        preview_encoded_format=int(preview_encoded_format),
        preview_encoded_bytes=int(preview_encoded_bytes),
        preview_raw_bytes=int(preview_raw_bytes),
    )


def _base_model_state(state: np.ndarray) -> np.ndarray:
    """Return the current-frame compact state from a possibly stacked state."""
    arr = np.asarray(state, dtype=np.float32)
    size = int(getattr(RL_CONFIG, "single_frame_state_size", arr.shape[0]))
    return arr[:min(arr.shape[0], size)]


def _object_rows(state: np.ndarray) -> np.ndarray:
    base = _base_model_state(state)
    cfg = RL_CONFIG
    start = int(getattr(cfg, "global_features", 40))
    count = int(getattr(cfg, "enemy_token_count", 112))
    feats = int(getattr(cfg, "enemy_token_features", 10))
    end = start + count * feats
    if base.shape[0] < end:
        rows = np.zeros((count, feats), dtype=np.float32)
        available = max(0, base.shape[0] - start)
        if available > 0:
            rows.reshape(-1)[:available] = base[start:start + available]
        return rows
    return np.asarray(base[start:end], dtype=np.float32).reshape(count, feats)


def _group_rows(state: np.ndarray, group: str) -> np.ndarray:
    rows = _object_rows(state)
    lo, hi = TOKEN_GROUP_RANGES.get(group, (0, 0))
    return rows[int(lo):int(hi)]


def _active_group_count(state: np.ndarray, group: str) -> int:
    rows = _group_rows(state, group)
    if rows.size == 0:
        return 0
    return int(np.count_nonzero(rows[:, 0] > 0.5))


def _state_wave(state: np.ndarray) -> float:
    base = _base_model_state(state)
    if base.shape[0] > 4 and np.isfinite(base[4]):
        return max(1.0, float(base[4]) * 40.0)
    return 1.0


def _wave_advanced(prev_state: np.ndarray | None, frame: FrameData, prev_level_number: int | None = None) -> bool:
    """Return True only when the wave/level actually increments.

    Prefer the prior frame's level_number from client state (uncapped, exact).
    Fall back to decoded state wave for backward compatibility.
    """
    if prev_level_number is not None:
        try:
            return int(frame.level_number) > int(prev_level_number)
        except Exception:
            pass
    if prev_state is None:
        return False
    return float(frame.level_number) > (_state_wave(prev_state) + 0.5)


def _movement_potential(state: np.ndarray | None, alive: bool = True) -> float:
    """State potential used for dense, non-harvestable movement credit.

    The potential is always <= 0 and becomes 0 on terminal/dead states. The
    reward term is gamma*Phi(s') - Phi(s), so approaching humans, escaping close
    danger, and getting out of dangerous corners get immediate credit without a
    per-frame survival drip.
    """
    if state is None or not alive:
        return 0.0

    cfg = RL_CONFIG
    phi = 0.0
    rows = _object_rows(state)
    present = rows[:, 0] > 0.5
    if not np.any(present):
        return 0.0
    active = rows[present]
    dist = np.clip(active[:, 3], 0.0, 1.0)
    threat = np.clip(active[:, 6], 0.0, 1.0)
    ttc = np.clip(active[:, 8], 0.0, 1.0) if active.shape[1] > 8 else np.ones_like(dist)
    type_id = np.zeros(active.shape[0], dtype=np.int32)
    if active.shape[1] >= TYPE_ONEHOT_OFFSET + TYPE_CLASS_COUNT:
        type_id = decode_token_types(active)

    humans = type_id == 7
    if np.any(humans):
        nearest_human = float(np.nanmin(dist[humans]))
        scale = max(0.0, float(getattr(cfg, "potential_human_scale", 0.0)))
        sharp = max(0.1, float(getattr(cfg, "potential_human_sharpness", 2.0)))
        phi -= scale * (nearest_human ** sharp)

    dangerous = ~humans
    danger_cue = 0.0
    if np.any(dangerous):
        closeness = 1.0 - dist[dangerous]
        danger_raw = np.maximum(
            closeness * (0.25 + 0.75 * threat[dangerous]),
            closeness * (1.0 - ttc[dangerous]),
        )
        danger_cue = float(np.nanmax(danger_raw)) if danger_raw.size else 0.0
        scale = max(0.0, float(getattr(cfg, "potential_danger_scale", 0.0)))
        sharp = max(0.1, float(getattr(cfg, "potential_danger_sharpness", 2.0)))
        phi -= scale * (max(0.0, min(1.0, danger_cue)) ** sharp)

    base = _base_model_state(state)
    if base.shape[0] > 6:
        px = min(1.0, max(0.0, float(base[5]) if np.isfinite(base[5]) else 0.5))
        py = min(1.0, max(0.0, float(base[6]) if np.isfinite(base[6]) else 0.5))
        wall = min(px, 1.0 - px, py, 1.0 - py)
        band = max(1e-6, float(getattr(cfg, "potential_corner_band", 0.16)))
        corner = max(0.0, min(1.0, (band - wall) / band))
        if corner > 0.0:
            crowd = min(1.0, float(np.count_nonzero(dangerous)) / 32.0)
            gate = max(danger_cue, crowd)
            phi -= max(0.0, float(getattr(cfg, "potential_corner_scale", 0.0))) * (corner ** 2) * gate

    return float(phi)


def _stall_penalty(stall_frames: int) -> float:
    grace = max(0, int(getattr(RL_CONFIG, "no_human_stall_grace_frames", 0)))
    if stall_frames <= grace:
        return 0.0
    per_frame = max(0.0, float(getattr(RL_CONFIG, "no_human_stall_penalty_per_frame", 0.0)))
    max_penalty = max(0.0, float(getattr(RL_CONFIG, "no_human_stall_max_penalty", 0.0)))
    ramp = min(1.0, (stall_frames - grace) / max(1, grace))
    return -min(max_penalty, per_frame * (1.0 + 3.0 * ramp))


def _transition_interest_score(prev_state: np.ndarray, next_state: np.ndarray,
                               frame, obj_r: float, total_r: float,
                               prev_level_number: int | None = None) -> float:
    """Sparse rare/elite-event score for replay sampling, independent of TD error."""
    try:
        def enemy_cues(state):
            rows = _object_rows(state)
            present = rows[:, 0] > 0.5
            if not np.any(present):
                return {
                    "danger": 0.0, "blocker": 0.0, "crowd": 0.0, "target": 0.0,
                    "projectile": 0.0, "humans": 0, "targets": 0, "corner": 0.0,
                }
            active = rows[present]
            dist = np.clip(active[:, 3], 0.0, 1.0)
            threat = np.clip(active[:, 6], 0.0, 1.0)
            ttc = np.clip(active[:, 8], 0.0, 1.0) if active.shape[1] > 8 else np.ones_like(dist)
            type_id = np.zeros(active.shape[0], dtype=np.int32)
            if active.shape[1] >= TYPE_ONEHOT_OFFSET + TYPE_CLASS_COUNT:
                type_id = decode_token_types(active)
            dangerous = type_id != 7
            targetable = np.isin(type_id, np.asarray([0, 2, 3, 4, 5, 6, 8], dtype=np.int32))
            projectile = np.isin(type_id, np.asarray([6], dtype=np.int32))
            closeness = 1.0 - dist
            danger_cue = np.where(dangerous, np.maximum(closeness * threat, closeness * (1.0 - ttc)), 0.0)
            target_cue = np.where(targetable, closeness * (0.25 + 0.75 * threat), 0.0)
            projectile_cue = np.where(projectile, np.maximum(closeness * threat, closeness * (1.0 - ttc)), 0.0)
            danger = float(np.nanmax(danger_cue)) if danger_cue.size else 0.0
            target = float(np.nanmax(target_cue)) if target_cue.size else 0.0
            proj = float(np.nanmax(projectile_cue)) if projectile_cue.size else 0.0
            crowd = float(min(1.0, active.shape[0] / 32.0))
            base = _base_model_state(state)
            corner = 0.0
            if base.shape[0] > 6:
                px = min(1.0, max(0.0, float(base[5]) if np.isfinite(base[5]) else 0.5))
                py = min(1.0, max(0.0, float(base[6]) if np.isfinite(base[6]) else 0.5))
                wall = min(px, 1.0 - px, py, 1.0 - py)
                corner = max(0.0, min(1.0, (0.16 - wall) / 0.16))
            return {
                "danger": danger,
                "blocker": 0.0,
                "crowd": crowd,
                "target": target,
                "projectile": proj,
                "humans": int(np.count_nonzero(type_id == 7)),
                "targets": int(np.count_nonzero(targetable)),
                "corner": corner,
            }

        prev = enemy_cues(prev_state)
        nxt = enemy_cues(next_state)
        danger = max(prev["danger"], nxt["danger"])
        blocker = max(prev["blocker"], nxt["blocker"])
        crowd = max(prev["crowd"], nxt["crowd"])
        target = max(prev["target"], nxt["target"])
        projectile = max(prev["projectile"], nxt["projectile"])

        wave = max(1.0, float(frame.level_number))
        wave_advance = 1.0 if _wave_advanced(prev_state, frame, prev_level_number=prev_level_number) else 0.0
        deep_wave = max(0.0, min(1.0, (wave - 3.0) / 8.0))
        wave9 = 1.0 if int(wave) % 10 == 9 else 0.0
        terminal = 1.0 if frame.done else 0.0
        corner_death = terminal * max(prev["corner"], nxt["corner"]) * max(danger, projectile)
        last_enemy_no_humans = 1.0 if min(prev["humans"], nxt["humans"]) == 0 and 0 < min(prev["targets"], nxt["targets"]) <= 3 else 0.0
        last_human_rescue = 1.0 if prev["humans"] > nxt["humans"] and obj_r >= 1.0 else 0.0

        def ramp(value: float, start: float) -> float:
            return max(0.0, min(1.0, (float(value) - float(start)) / max(1e-6, 1.0 - float(start))))

        score_burst = max(0.0, min(1.0, max(0.0, float(obj_r)) / 5.0))
        positive_surprise = max(0.0, min(1.0, max(0.0, float(total_r)) / 5.0))
        danger_event = ramp(danger, 0.55)
        blocker_event = ramp(blocker, 0.65)
        crowd_event = ramp(crowd, 0.55)
        target_event = ramp(target, 0.55)
        deep_tactical = deep_wave * max(danger_event, crowd_event, target_event)

        return max(
            score_burst,
            0.80 * wave_advance,
            0.75 * terminal,
            0.75 * danger_event,
            0.60 * blocker_event,
            0.70 * target_event,
            0.65 * crowd_event,
            0.55 * deep_tactical,
            0.80 * last_enemy_no_humans,
            1.00 * last_human_rescue,
            0.85 * wave9 * max(danger_event, crowd_event, target_event, projectile),
            0.75 * ramp(projectile, 0.35),
            0.95 * corner_death,
            0.35 * positive_surprise,
        )
    except Exception:
        return 0.0


def _clip_abs(value: float, limit: float) -> float:
    limit = max(0.0, float(limit))
    return max(-limit, min(limit, float(value)))


def _subj_positive_weight_schedule(training_step: int) -> float:
    """Anneal positive subjective shaping separately from BCW."""
    cfg = RL_CONFIG
    start = max(0.0, float(getattr(cfg, "subj_positive_weight", 1.0)))
    floor = max(0.0, float(getattr(cfg, "subj_positive_min_weight", start)))
    start_step = int(getattr(cfg, "subj_positive_decay_start_step", 0))
    decay_steps = max(1, int(getattr(cfg, "subj_positive_decay_steps", 1)))
    step = max(0, int(training_step))
    if step < start_step:
        return start
    progress = min(1.0, (step - start_step) / decay_steps)
    return start + progress * (floor - start)


def _shape_transition_reward(
    frame,
    last_game_score: int,
    prev_state: np.ndarray | None = None,
    next_state: np.ndarray | None = None,
    prev_level_number: int | None = None,
    stall_frames: int = 0,
) -> tuple[float, float, float, float, int]:
    """Reward from score plus bounded non-harvestable shaping.

    The second returned component is still named ``subj_r`` by the older metrics
    path, but it now means all shaping: Lua subjective reward if enabled,
    wave-clear/event bonuses, potential-difference movement shaping, and
    no-human no-score stall penalties.
    """
    try:
        score_delta = max(0, int(frame.game_score) - int(last_game_score))
    except Exception:
        score_delta = 0
    score_r = min(
        float(score_delta) * float(RL_CONFIG.score_reward_scale),
        float(RL_CONFIG.score_reward_clip),
    )
    subj_weight = _subj_positive_weight_schedule(getattr(metrics, "total_training_steps", 0))
    try:
        metrics.last_subj_positive_weight = float(subj_weight)
    except Exception:
        pass
    subj_raw = float(frame.subjreward) * float(RL_CONFIG.subj_reward_scale)
    if subj_raw > 0.0:
        subj_raw *= subj_weight
    shaping_raw = subj_raw

    # Do not pay "escape danger" potential on terminal/death frames.  Since
    # Phi(s) <= 0, treating death as Phi(s') = 0 can accidentally reward dying
    # from a dangerous state.
    if prev_state is not None and next_state is not None and bool(frame.player_alive) and not bool(frame.done):
        phi_prev = _movement_potential(prev_state, alive=True)
        phi_next = _movement_potential(next_state, alive=True)
        shaping_raw += float(RL_CONFIG.gamma) * phi_next - phi_prev

    clear_r = 0.0
    if _wave_advanced(prev_state, frame, prev_level_number=prev_level_number):
        wave = max(1, int(frame.level_number))
        # Wave-clear bonus OUTSIDE the shaping clip so +2.5 means +2.5 — this
        # is the positive grounding term (see wave_clear_training_terminal),
        # not garden-variety shaping to be blended and clamped.
        clear_r = float(getattr(RL_CONFIG, "wave_clear_bonus", 0.0))
        shaping_raw += float(getattr(RL_CONFIG, "wave_progress_bonus", 0.0)) * min(10, max(0, wave - 1))

    shaping_raw += _stall_penalty(int(stall_frames))

    subj_r = _clip_abs(shaping_raw, float(RL_CONFIG.shaping_reward_clip)) + clear_r
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
        # Rolling per-episode stats for the adaptive elite gate (consumer
        # thread only — no locking needed).
        _ew = max(10, int(getattr(RL_CONFIG, "elite_adaptive_window", 200)))
        self._recent_ep_scores = deque(maxlen=_ew)
        self._recent_ep_levels = deque(maxlen=_ew)
        # High-water marks per percentile for the elite-threshold ratchet
        # (consumer thread only).
        self._elite_thr_hwm = {}
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
            self._record_drop()

    def boost_pre_death(self, client_id):
        try:
            self.queue.put_nowait(("boost", client_id, None, None))
        except queue.Full:
            self._record_drop()

    def boost_elite_episode(self, client_id, score: int, level: int, total_reward: float, ep_len: int):
        try:
            self.queue.put_nowait(("elite", client_id, (int(score), int(level), float(total_reward), int(ep_len)), None))
        except queue.Full:
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
        try:
            self.agent.memory.apply_pre_death_penalty(list(indices))
        except Exception as e:
            print(f"  Pre-death reward penalty error: {e}")
        boost = float(getattr(RL_CONFIG, "pre_death_priority_boost", 2.0))
        if boost <= 1.0:
            indices.clear()
            return
        try:
            self.agent.memory.boost_priorities(list(indices), boost)
        except Exception as e:
            print(f"  Pre-death boost error: {e}")
        indices.clear()

    def _elite_thresholds(self, percentile: float, score_floor: int, level_floor: int) -> tuple[float, float]:
        """Effective elite thresholds: static floors raised to a rolling
        percentile of recent episodes, so 'elite' stays selective as the agent
        improves (a fixed level threshold below the average level matches half
        of all play and the boost degenerates into noise)."""
        if len(self._recent_ep_scores) < int(getattr(RL_CONFIG, "elite_adaptive_min_episodes", 20)):
            return float(score_floor), float(level_floor)
        pct = max(0.0, min(100.0, float(percentile)))
        score_thr = max(float(score_floor), float(np.percentile(np.asarray(self._recent_ep_scores, dtype=np.float64), pct)))
        level_thr = max(float(level_floor), float(np.percentile(np.asarray(self._recent_ep_levels, dtype=np.float64), pct)))
        # Ratchet (2026-07): the rolling percentile re-anchors to ~35s of
        # current play, so during a decline it would certify the top decile
        # of MEDIOCRE play as elite.  Track the within-run high-water mark
        # and never let the usable threshold fall more than the slack below
        # it — "elite" keeps meaning good vs the best this run has shown.
        if bool(getattr(RL_CONFIG, "elite_threshold_ratchet", True)):
            hwm_s, hwm_l = self._elite_thr_hwm.get(pct, (score_thr, level_thr))
            hwm_s = max(hwm_s, score_thr)
            hwm_l = max(hwm_l, level_thr)
            self._elite_thr_hwm[pct] = (hwm_s, hwm_l)
            score_thr = max(score_thr, float(getattr(RL_CONFIG, "elite_ratchet_score_slack", 0.85)) * hwm_s)
            level_thr = max(level_thr, hwm_l - float(getattr(RL_CONFIG, "elite_ratchet_level_slack", 1.0)))
        return score_thr, level_thr

    def _do_elite_episode_boost(self, client_id, score: int, level: int, total_reward: float, ep_len: int):
        indices = self._episode_indices.get(client_id)
        # Every finished episode feeds the adaptive gate, boosted or not —
        # thresholds must track typical play, not just elite play.
        self._recent_ep_scores.append(int(score))
        self._recent_ep_levels.append(int(level))
        if not indices:
            return
        # Hall-of-fame admission is INDEPENDENT of the elite gate: absolute
        # criteria only (static floor + all-time top-N inside hof_admit), so
        # a declining run can never certify its own play into permanence.
        # Copies must happen here, before the ring recycles these indices.
        if bool(getattr(RL_CONFIG, "hof_enabled", False)):
            try:
                # Silent by design: admissions surface via the HOF dashboard
                # column (bank bar) and the b-key buffer report.
                self.agent.memory.hof_admit(list(indices), int(score))
            except Exception as e:
                print(f"  HOF admission error: {e}")
        try:
            e_score_thr, e_level_thr = self._elite_thresholds(
                float(getattr(RL_CONFIG, "elite_adaptive_percentile", 90.0)),
                int(getattr(RL_CONFIG, "elite_episode_score_threshold", 120_000)),
                int(getattr(RL_CONFIG, "elite_episode_level_threshold", 8)),
            )
            elite = int(score) >= e_score_thr or int(level) >= e_level_thr
            learner_elite = False
            try:
                mem = self.agent.memory
                with mem.lock:
                    idxs = np.asarray(indices, dtype=np.int64)
                    idxs = idxs[(idxs >= 0) & (idxs < mem.size)]
                    kinds = mem.actor_kind[idxs].copy() if idxs.size > 0 else np.empty(0, dtype=np.uint8)
                if idxs.size > 0:
                    learner_frac = float(np.mean(kinds != ACTOR_EXPERT))
                    min_learner = max(0.0, min(1.0, float(getattr(RL_CONFIG, "learner_elite_min_learner_fraction", 0.90))))
                    l_score_thr, l_level_thr = self._elite_thresholds(
                        float(getattr(RL_CONFIG, "learner_elite_adaptive_percentile", 80.0)),
                        int(getattr(RL_CONFIG, "learner_elite_score_threshold", 60_000)),
                        int(getattr(RL_CONFIG, "learner_elite_level_threshold", 6)),
                    )
                    learner_elite = (
                        learner_frac >= min_learner
                        and (int(score) >= l_score_thr or int(level) >= l_level_thr)
                    )
            except Exception:
                learner_elite = False
            if elite or learner_elite:
                elite_tail = int(getattr(RL_CONFIG, "elite_episode_tail_len", 768)) if elite else 0
                learner_tail = int(getattr(RL_CONFIG, "learner_elite_tail_len", 1536)) if learner_elite else 0
                tail_len = max(1, elite_tail, learner_tail)
                tail = list(indices)[-tail_len:]
                boost = max(
                    float(getattr(RL_CONFIG, "elite_episode_priority_boost", 3.0)) if elite else 1.0,
                    float(getattr(RL_CONFIG, "learner_elite_priority_boost", 4.0)) if learner_elite else 1.0,
                )
                interest = max(
                    float(getattr(RL_CONFIG, "elite_episode_interest_score", 1.0)) if elite else 0.0,
                    float(getattr(RL_CONFIG, "learner_elite_interest_score", 1.0)) if learner_elite else 0.0,
                )
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
    __slots__ = ("state", "epsilon", "locked_fire", "event", "action", "cancelled")

    def __init__(self, state, epsilon: float, locked_fire=None):
        self.state = state
        self.epsilon = float(epsilon)
        self.locked_fire = locked_fire
        self.event = threading.Event()
        self.action = None
        self.cancelled = False


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
            # Cancel BEFORE falling back to a solo act(): an abandoned request
            # left live in the queue still gets batched and inferred — every
            # timed-out frame was costing TWO inferences.  Under load, 32
            # handlers timing out at once turned into 32 solo CUDA calls plus
            # the batcher's ghost work, which kept latency above the timeout
            # forever: a self-sustaining stampede (measured: AvgInf pinned at
            # ~104ms for an entire boot on 2026-07-13).  Cancelling the
            # request breaks the amplification; the longer timeout (config:
            # inference_request_timeout_ms) keeps handlers in the batched
            # path through transient stalls instead of defecting.
            req.cancelled = True
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

            # Drop requests whose handler already gave up and solo-inferred —
            # running them here would be pure duplicate GPU work.
            batch = [r for r in batch if not r.cancelled]
            if not batch:
                continue

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
                request_timeout_ms=float(getattr(RL_CONFIG, "inference_request_timeout_ms", 250.0)),
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
        # Per-cid eval override from the handshake (--eval / --noeval).
        # True=force eval, False=force non-eval, absent=auto (cid%stride rule).
        self._eval_override = {}
        self.client_lock = threading.Lock()
        self.preview_cid: Optional[int] = None
        self.preview_disabled = False

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

    def _auto_curriculum_level(self) -> int:
        """Frontier-biased random start level (Dave's design, 2026-07-19).

        N = max(floor, ceil(ELvl1M)) + spread; start = 1 + int(N * sqrt(u)):
        density rises linearly toward (and past) the eval frontier, thin at
        the bottom (eval clients guarantee wave-1 play).  Drawn per packet,
        but Robotron latches the start level only at game start, so each new
        game samples the distribution exactly once.
        """
        _elvl = float(getattr(metrics, "eval_level_1m_average", 0.0) or 0.0)
        _n = max(int(getattr(RL_CONFIG, "stratified_auto_floor", 5)),
                 int(_elvl + 0.999)) + int(getattr(RL_CONFIG, "stratified_auto_spread", 8))
        return max(1, min(255, 1 + int(_n * (random.random() ** 0.5))))

    def _is_eval_client(self, cid: int) -> bool:
        # Per-client override wins (set from the handshake --eval/--noeval flag);
        # otherwise the default cid%stride==offset rule.
        ov = self._eval_override.get(int(cid))
        if ov is not None:
            return bool(ov)
        stride = int(getattr(RL_CONFIG, "eval_client_stride", 0))
        if stride <= 0:
            return False
        offset = int(getattr(RL_CONFIG, "eval_client_offset", stride - 1)) % stride
        return (int(cid) % stride) == offset

    def _init_client(self, cid):
        n = max(1, int(getattr(RL_CONFIG, "n_step", 1)))
        gamma = float(getattr(RL_CONFIG, "gamma", 0.99))
        nstep = NStepReplayBuffer(n_step=n, gamma=gamma) if n > 1 else None
        eval_only = self._is_eval_client(cid)
        with self.client_lock:
            self.client_states[cid] = {
                "frames": 0, "connected_since": time.time(), "last_time": time.time(),
                "fps": 0.0, "fps_frames": 0,
                "level_number": 0, "game_score": 0, "last_state": None, "last_action": None,
                "last_game_score": 0,
                "last_level_number": 0,
                "preview_capable": False, "client_slot": int(cid),
                "prev_action_source": None,
                "total_reward": 0.0, "ep_dqn_reward": 0.0, "ep_dqn_score_reward": 0.0, "ep_expert_reward": 0.0,
                "ep_subj_reward": 0.0, "ep_obj_reward": 0.0, "ep_frames": 0,
                "ep_death_reward": 0.0,
                "ep_dqn_frames": 0,
                "no_human_no_score_frames": 0,
                "eval_only": eval_only, "ep_t0": time.time(),
                "game_t0": time.time(), "cohort_voided": False,
                "wx_ring": deque(maxlen=10), "wx_dumped": 0,
                "prev_score_seen": 0, "last_score_advance": time.time(),
                "was_done": False, "nstep": nstep,
                "frame_history": deque(maxlen=max(1, int(getattr(RL_CONFIG, "frame_stack", 1)))),
                "fire_hold_dir": -1, "fire_hold_count": 0, "fire_pending_dir": -1,
            }
            self._sync_client_count_locked()
            # A client (re)connecting mid-measurement starts a fresh game; count
            # it into the cohort so its completion doesn't arrive uncounted.
            try:
                metrics.ratchet_note_eval_start(float(self.client_states[cid]["game_t0"]))
            except Exception:
                pass

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
    def _parse_client_handshake(handshake_value: int) -> tuple[bool, int, int]:
        # 16-bit handshake:
        #   bit 0      = preview-capable
        #   bits 1-13  = launcher slot (<=8191)
        #   bits 14-15 = eval mode (0=auto, 1=force-eval, 2=force-noeval)
        # Old clients send 0 in the eval bits -> auto -> unchanged behavior.
        raw = max(0, int(handshake_value or 0))
        preview_capable = (raw & 0x01) != 0
        client_slot = max(0, (raw >> 1) & 0x1FFF)
        eval_mode = (raw >> 14) & 0x03
        return preview_capable, client_slot, eval_mode

    def _pick_default_preview_client_locked(self) -> Optional[int]:
        candidates = []
        for cid, cs in self.client_states.items():
            if not bool(cs.get("preview_capable", False)):
                continue
            slot = int(cs.get("client_slot", cid))
            candidates.append((slot, int(cid)))
        if not candidates:
            return None
        candidates.sort()
        return int(candidates[0][1])

    def _ensure_preview_client_selected_locked(self) -> tuple[Optional[int], bool]:
        if self.preview_disabled:
            changed = self.preview_cid is not None
            self.preview_cid = None
            return None, changed
        selected = self.preview_cid
        if selected is not None:
            cs = self.client_states.get(int(selected))
            if isinstance(cs, dict) and bool(cs.get("preview_capable", False)):
                return int(selected), False
        fallback = self._pick_default_preview_client_locked()
        changed = self.preview_cid != fallback
        self.preview_cid = fallback
        return fallback, changed

    def _is_preview_client(self, cid: int) -> bool:
        with self.client_lock:
            preview_cid, changed = self._ensure_preview_client_selected_locked()
        if changed:
            self._clear_preview_cache()
        return preview_cid is not None and int(cid) == int(preview_cid)

    def _preview_enabled_for_client(self, cid: int) -> bool:
        if not self._is_preview_client(cid):
            return False
        with self.client_lock:
            cs = self.client_states.get(int(cid))
            if not isinstance(cs, dict) or not bool(cs.get("preview_capable", False)):
                return False
        with self.metrics.lock:
            if not bool(getattr(self.metrics, "preview_capture_enabled", True)):
                return False
            return int(getattr(self.metrics, "web_client_count", 0) or 0) > 0

    def _hud_enabled_for_client(self, cid: int) -> bool:
        if not self._is_preview_client(cid):
            return False
        with self.metrics.lock:
            return bool(getattr(self.metrics, "hud_enabled", False))

    def _clear_preview_cache(self):
        with self.metrics.lock:
            self.metrics.game_preview_client_id = -1
            self.metrics.game_preview_seq = 0
            self.metrics.game_preview_width = 0
            self.metrics.game_preview_height = 0
            self.metrics.game_preview_format = ""
            self.metrics.game_preview_data = b""
            self.metrics.game_preview_updated_ts = 0.0
            self.metrics.game_preview_source_format = ""
            self.metrics.game_preview_encoded_bytes = 0
            self.metrics.game_preview_raw_bytes = 0
            self.metrics.game_preview_compression_ratio = 1.0
            self.metrics.game_preview_fps = 0.0

    def _cache_client_preview(self, cid: int, frame: FrameData):
        if not self._is_preview_client(cid):
            return
        pixels = frame.preview_pixels
        width = int(frame.preview_width)
        height = int(frame.preview_height)
        if not pixels or width <= 0 or height <= 0:
            return
        if int(frame.preview_format) != 1:
            return
        expected_len = width * height * 2
        if len(pixels) != expected_len:
            return
        enc_fmt = int(frame.preview_encoded_format)
        enc_bytes = int(frame.preview_encoded_bytes)
        raw_bytes = int(frame.preview_raw_bytes)
        with self.metrics.lock:
            prev_seq = int(getattr(self.metrics, "game_preview_seq", 0))
            prev_ts = float(getattr(self.metrics, "game_preview_updated_ts", 0.0))
            now_ts = time.time()
            if prev_ts > 0.0:
                dt = max(1e-6, now_ts - prev_ts)
                self.metrics.game_preview_fps = 1.0 / dt
            self.metrics.game_preview_client_id = int(cid)
            self.metrics.game_preview_seq = prev_seq + 1
            self.metrics.game_preview_width = width
            self.metrics.game_preview_height = height
            self.metrics.game_preview_format = "rgb565be"
            self.metrics.game_preview_data = bytes(pixels)
            self.metrics.game_preview_updated_ts = now_ts
            self.metrics.game_preview_source_format = {1: "raw", 2: "lzss", 3: "rle"}.get(enc_fmt, "unknown")
            self.metrics.game_preview_encoded_bytes = enc_bytes
            self.metrics.game_preview_raw_bytes = raw_bytes if raw_bytes > 0 else expected_len
            if enc_bytes > 0 and raw_bytes > 0:
                self.metrics.game_preview_compression_ratio = float(raw_bytes) / float(enc_bytes)
            else:
                self.metrics.game_preview_compression_ratio = 1.0

    def get_client_rows(self) -> list[dict]:
        with self.client_lock:
            selected, changed = self._ensure_preview_client_selected_locked()
            now = time.time()
            rows = []
            for cid, cs in self.client_states.items():
                frames = max(0, int(cs.get("frames", 0) or 0))
                connected_since = float(cs.get("connected_since", now) or now)
                rows.append({
                    "client_id": int(cid),
                    "client_slot": int(cs.get("client_slot", cid)),
                    "session_seconds": float(frames) / 60.0,
                    "connected_seconds": max(0.0, now - connected_since),
                    "fps": float(cs.get("fps", 0.0) or 0.0),
                    "level": max(0, int(cs.get("level_number", 0) or 0)),
                    "score": max(0, int(cs.get("game_score", 0) or 0)),
                    "selected_preview": (selected is not None and int(selected) == int(cid)),
                    "preview_capable": bool(cs.get("preview_capable", False)),
                    "eval": bool(cs.get("eval_only", False)),
                })
        if changed:
            self._clear_preview_cache()
        rows.sort(key=lambda r: (int(r.get("client_slot", r.get("client_id", 0))), int(r.get("client_id", 0))))
        return rows

    def get_selected_preview_client_id(self) -> Optional[int]:
        with self.client_lock:
            selected, changed = self._ensure_preview_client_selected_locked()
        if changed:
            self._clear_preview_cache()
        return None if selected is None else int(selected)

    def set_preview_client(self, cid: Optional[int]) -> tuple[bool, Optional[int]]:
        with self.client_lock:
            was_disabled = bool(self.preview_disabled)
            old_selected = self.preview_cid
            if cid is None:
                selected = None
                self.preview_disabled = True
            else:
                cs = self.client_states.get(int(cid))
                if not isinstance(cs, dict) or not bool(cs.get("preview_capable", False)):
                    return False, self.preview_cid
                selected = int(cid)
                self.preview_disabled = False
            changed = old_selected != selected or was_disabled != self.preview_disabled
            self.preview_cid = selected
        if changed:
            self._clear_preview_cache()
        return True, selected

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

    def _pack_action(
        self,
        move_cmd,
        fire_cmd,
        source_code,
        cid: int = 0,
        preview_enabled: bool = False,
        hud_enabled: bool = False,
    ):
        if self._is_eval_client(cid):
            # Eval clients always start a fresh game at wave 1: EScr1M measures
            # true full-game performance, not curriculum-boosted play.
            start_adv = 0
            start_level = 1
        elif getattr(metrics, "ratchet_frozen", False):
            # Ratchet measurement: the whole fleet plays the eval protocol —
            # wave-1 fresh games — so the number is the same yardstick as the
            # DQN_EVAL_ONLY control, not a mixture over stratified starts.
            start_adv = 0
            start_level = 1
        else:
            _gs = game_settings.snapshot()
            if bool(_gs.get("auto_curriculum", False)):
                # UI "Automatic" toggle: frontier-biased auto-curriculum draw,
                # applied LIVE (game_settings needs no restart).  Wins over the
                # manual level — "Automatic" means automatic; untick to return
                # to the dialed start_level_min.
                start_level = self._auto_curriculum_level()
                start_adv = 1 if start_level > 1 else 0
            elif _gs["start_advanced"]:
                # Operator-driven manual curriculum.
                start_adv = 1
                start_level = max(1, min(255, int(_gs["start_level_min"])))
            elif STRATIFIED_TRAINING_STARTS and bool(getattr(RL_CONFIG, "stratified_auto", False)):
                # Config-default auto-curriculum (same draw as the UI toggle).
                start_level = self._auto_curriculum_level()
                start_adv = 1 if start_level > 1 else 0
            elif STRATIFIED_TRAINING_STARTS:
                # Stratified per-client start waves (2026-07): guarantee
                # deep-wave experience in the buffer regardless of policy
                # quality, breaking the wave-1 curriculum lock-in where deep
                # data existed only while the policy could reach it.
                levels = STRATIFIED_START_LEVELS
                start_level = max(1, min(255, int(levels[cid % len(levels)])))
                start_adv = 1 if start_level > 1 else 0
            else:
                start_adv = 0
                start_level = 1
        source_u8 = int(source_code) & 0x0F
        if preview_enabled:
            source_u8 |= 0x40
        if hud_enabled:
            source_u8 |= 0x80
        return struct.pack(">bbBBB", int(move_cmd), int(fire_cmd),
                           source_u8, start_adv, start_level)

    def handle_client(self, sock, cid):
        local_accum = 0
        try:
            sock.setblocking(False)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)

            # Handshake — 2-byte value: bit 0 = preview-capable, upper bits = launch slot.
            ping = self._recv_exact(sock, 2, timeout_s=5.0)
            if not ping or len(ping) < 2:
                raise ConnectionError("No handshake")
            handshake_val = struct.unpack(">H", ping)[0]
            preview_capable, client_slot, eval_mode = self._parse_client_handshake(handshake_val)
            with self.client_lock:
                cs0 = self.client_states.get(cid)
                if isinstance(cs0, dict):
                    cs0["preview_capable"] = bool(preview_capable)
                    cs0["client_slot"] = int(client_slot)
                    # Client-requested eval override (--eval / --noeval).
                    if eval_mode == 1:
                        self._eval_override[cid] = True
                        cs0["eval_only"] = True
                    elif eval_mode == 2:
                        self._eval_override[cid] = False
                        cs0["eval_only"] = False
                _, changed = self._ensure_preview_client_selected_locked()
            if eval_mode in (1, 2):
                print(f"Client {cid} (slot {client_slot}) forced "
                      f"{'EVAL' if eval_mode == 1 else 'NON-EVAL'} by handshake")
            if changed:
                self._clear_preview_cache()

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

                preview_enabled = self._preview_enabled_for_client(cid)
                hud_enabled = self._hud_enabled_for_client(cid)
                should_parse_preview = bool(preview_enabled and self._is_preview_client(cid))

                frame = parse_frame_data(data, parse_preview=should_parse_preview)
                if not frame:
                    sock.sendall(self._pack_action(
                        -1, -1, _SRC_NONE, cid,
                        preview_enabled=preview_enabled,
                        hud_enabled=hud_enabled,
                    ))
                    continue
                if should_parse_preview and frame.preview_pixels:
                    self._cache_client_preview(cid, frame)

                # ── Marathon accounting: unwrap score + wave, reject crashes ─
                # Levels routinely pass 255 (byte counter wraps ~mod 256) and
                # the BCD score register wraps at a power of 10.  Every frame
                # is classified from per-client RAW trackers (updated only on
                # ACCEPTED frames, so a crash frame can never corrupt the
                # baseline):
                #   continue  raw score >= prev, jump within MAX_SCORE_JUMP
                #   WRAP      prev near a 10^k top, raw lands near zero,
                #             player alive, no recent start press
                #             -> score_offset += 10^k
                #   NEW GAME  small raw score (fresh game) -> offsets reset
                #   CRASH     everything else (up-jumps AND unexplained
                #             mid-air drops) -> frame dropped, no-op action
                # frame.game_score / frame.level_number are REWRITTEN to true
                # unwrapped values here, so every consumer — reward deltas
                # (continuous across wraps), wave-clear terminals (255->256
                # reads as an advance, not a regression), game boundaries,
                # HOF admission, peaks, eval scoring, the dashboard — sees
                # accurate marathon totals.
                _verdict = "accept"
                _wrap_note = None
                with self.client_lock:
                    _cs0 = self.client_states.get(cid)
                    if _cs0 is not None:
                        _raw_sc = int(frame.game_score)
                        _raw_wv = int(frame.level_number)
                        if frame.start_pressed:
                            _cs0["last_start_frame"] = int(_cs0.get("frames", 0))
                        _recent_start = (int(_cs0.get("frames", 0))
                                         - int(_cs0.get("last_start_frame", -10**9))) < 300
                        _prev_sc = _cs0.get("raw_score_prev")
                        _prev_wv = _cs0.get("raw_wave_prev")
                        _new_game_max = int(getattr(RL_CONFIG, "score_new_game_max", 100_000))
                        if _prev_sc is None:
                            pass  # first frame of the connection: accept as-is
                        elif _raw_sc > _prev_sc + _MAX_SCORE_JUMP:
                            _verdict = "crash-jump"
                        elif _raw_sc < _prev_sc:
                            _mod = 10 ** len(str(max(1, _prev_sc)))
                            if (_prev_sc >= 0.9 * _mod and _raw_sc <= 0.1 * _mod
                                    and frame.player_alive and not _recent_start):
                                _cs0["score_offset"] = int(_cs0.get("score_offset", 0)) + _mod
                                _wrap_note = (f"[UNWRAP] cid={cid} score rolled "
                                              f"{_prev_sc:,} -> {_raw_sc:,} (+{_mod:,}); "
                                              f"true {_cs0['score_offset'] + _raw_sc:,}")
                            elif _raw_sc <= _new_game_max:
                                _cs0["score_offset"] = 0
                                _cs0["wave_offset"] = 0
                            else:
                                _verdict = "crash-drop"
                        if _verdict == "accept":
                            if (_prev_wv is not None and _raw_wv < _prev_wv - 200
                                    and frame.player_alive and not _recent_start):
                                _cs0["wave_offset"] = int(_cs0.get("wave_offset", 0)) + 256
                                _wrap_note = (_wrap_note or f"[UNWRAP] cid={cid}") + (
                                    f"  [wave {_prev_wv} -> {_raw_wv}; "
                                    f"true wave {_cs0['wave_offset'] + _raw_wv}]")
                            _cs0["raw_score_prev"] = _raw_sc
                            _cs0["raw_wave_prev"] = _raw_wv
                            frame.game_score = int(_cs0.get("score_offset", 0)) + _raw_sc
                            frame.level_number = int(_cs0.get("wave_offset", 0)) + _raw_wv
                if _wrap_note:
                    print(_wrap_note)
                if _verdict != "accept":
                    global _last_implausible_warn_t
                    _nowj = time.time()
                    if _nowj - _last_implausible_warn_t > 5.0:
                        _last_implausible_warn_t = _nowj
                        print(f"[INGEST] dropped {_verdict} frame: cid={cid} "
                              f"raw_score={frame.game_score} (baseline unchanged); "
                              f"likely game crash")
                    sock.sendall(self._pack_action(
                        -1, -1, _SRC_NONE, cid,
                        preview_enabled=preview_enabled,
                        hud_enabled=hud_enabled,
                    ))
                    continue

                # Single-frame compact input; stacked current-first with recent history.
                single_state = slice_model_state(frame.state)

                with self.client_lock:
                    if cid not in self.client_states:
                        break
                    cs = self.client_states[cid]
                    cs["frames"] += 1
                    cs["level_number"] = frame.level_number
                    cs["game_score"] = frame.game_score
                    cs["player_alive"] = bool(frame.player_alive)
                    cs["num_lasers"] = int(frame.num_lasers)
                    now = time.time()
                    cs["fps_frames"] = int(cs.get("fps_frames", 0)) + 1
                    el = now - cs["last_time"]
                    if el >= 1.0:
                        cs["fps"] = float(cs.get("fps_frames", 0)) / el
                        cs["fps_frames"] = 0
                        cs["last_time"] = now

                model_state = self._stack_model_state(cs, single_state)

                # Peak score and rolling score/level telemetry are shared
                # metrics state; guard with metrics.lock for dashboard reads.
                metrics.note_game_score(frame.game_score, frame.level_number)

                local_accum += 1
                if local_accum >= BATCH:
                    frames_advanced = local_accum
                    metrics.update_frame_count(delta=local_accum)
                    local_accum = 0
                    metrics.update_epsilon(frames_advanced=frames_advanced)
                    metrics.update_expert_ratio()
                    self._calc_avg_game_state()

                # ── DIAGNOSTIC: wave-transition frame ordering (DQN_WAVE_PROBE=1) ──
                # Tests whether Robotron's wave transition asserts
                # STATUS_PLAYER_INACTIVE (main.lua read_player_alive), which
                # would make done=(prev_alive==1 and alive==0) fire on a WAVE
                # CLEAR — charging -death_penalty for clearing and hiding the
                # level increment from _wave_advanced behind the alive-gate.
                if _WAVE_PROBE:
                    try:
                        _r = cs["wx_ring"]
                        _r.append((int(frame.level_number), 1 if frame.player_alive else 0,
                                   1 if frame.done else 0, int(frame.game_score)))
                        if (len(_r) >= 2 and _r[-1][0] > _r[-2][0]
                                and cs["wx_dumped"] < 6):
                            cs["wx_dumped"] += 1
                            _fmt = " -> ".join(
                                f"w{lv}/a{al}/d{dn}" for lv, al, dn, _sc in _r)
                            print(f"[WAVEPROBE cid={cid} #{cs['wx_dumped']}] {_fmt}")
                    except Exception:
                        pass

                # ── Ratchet per-game accounting ─────────────────────────
                # A Robotron game's score is non-decreasing; a reset marks the
                # boundary.  One cohort sample = one game's FINAL score.  A
                # client whose score stops advancing while frozen has wedged
                # (attract mode / stuck reconnect): void its cohort game so
                # the measurement can complete without it.
                try:
                    _sc = int(frame.game_score)
                    _prev_sc = int(cs.get("prev_score_seen", 0))
                    _ts = time.time()
                    if _sc > _prev_sc:
                        cs["last_score_advance"] = _ts
                    if _sc < _prev_sc and _prev_sc >= 5_000 and _sc <= _prev_sc // 2:
                        # game over: _prev_sc was the final score
                        if not cs.get("cohort_voided", False):
                            _cap = float(getattr(RL_CONFIG, "ratchet_max_credible_final", 2e6))
                            if _prev_sc <= _cap:
                                metrics.ratchet_note_eval_episode(float(_prev_sc), cs.get("game_t0", 0.0))
                            else:   # transient-RAM junk read — void, don't record
                                metrics.ratchet_note_eval_abandoned(cs.get("game_t0", 0.0))
                        cs["game_t0"] = _ts
                        cs["cohort_voided"] = False
                        cs["last_score_advance"] = _ts
                        metrics.ratchet_note_eval_start(cs["game_t0"])
                    elif (metrics.ratchet_frozen and not cs.get("cohort_voided", False)
                          and _ts - cs.get("last_score_advance", _ts) >
                              float(getattr(RL_CONFIG, "ratchet_stuck_void_s", 120.0))):
                        metrics.ratchet_note_eval_abandoned(cs.get("game_t0", 0.0))
                        cs["cohort_voided"] = True
                    cs["prev_score_seen"] = _sc
                except Exception:
                    pass

                # ── Process previous step ───────────────────────────────
                if cs.get("last_state") is not None and cs.get("last_action") is not None:
                    mv_i, fr_i = cs["last_action"]
                    try:
                        score_delta_probe = max(0, int(frame.game_score) - int(cs.get("last_game_score", frame.game_score)))
                    except Exception:
                        score_delta_probe = 0
                    if (
                        frame.done
                        or not frame.player_alive
                        or score_delta_probe > 0
                        or _active_group_count(model_state, "human") > 0
                    ):
                        cs["no_human_no_score_frames"] = 0
                    else:
                        cs["no_human_no_score_frames"] = int(cs.get("no_human_no_score_frames", 0)) + 1
                    total_r, score_r, subj_r, death_r, score_delta = _shape_transition_reward(
                        frame,
                        cs.get("last_game_score", frame.game_score),
                        prev_state=cs.get("last_state"),
                        next_state=model_state,
                        prev_level_number=cs.get("last_level_number"),
                        stall_frames=int(cs.get("no_human_no_score_frames", 0)),
                    )
                    interest = _transition_interest_score(
                        cs["last_state"],
                        model_state,
                        frame,
                        score_r,
                        total_r,
                        prev_level_number=cs.get("last_level_number"),
                    )

                    # Terminal-outcome accounting (FtlPct) — deliberately
                    # OUTSIDE the store/frozen gate: it describes play, not
                    # training, and must keep updating through measurements.
                    try:
                        _clr = _wave_advanced(cs.get("last_state"), frame,
                                              prev_level_number=cs.get("last_level_number"))
                        if bool(frame.done) or (
                            _clr and bool(getattr(RL_CONFIG, "wave_clear_training_terminal", False))
                        ):
                            # death wins if both land on one frame
                            metrics.note_training_terminal(bool(frame.done))
                    except Exception:
                        pass

                    eval_only = bool(cs.get("eval_only", False))
                    # Eval frames now TRAIN (Dave, 2026-07-19).  The old
                    # blanket exclusion was a ratchet-era guard: measurement
                    # phases dominated wall-clock ~5:1 and would have flooded
                    # the ring with frozen-policy frames.  With the ratchet
                    # retired, permanent eval clients are a small minority of
                    # the fleet — and their games are the system's BEST data,
                    # twice over: banked free lives take them to wave 20-23+
                    # (deeper than any injection-carrying training client can
                    # reach), and every game is a full wave-1->N traversal
                    # that also refreshes the early-wave anchor.  Training on
                    # them cannot corrupt EScr1M: eval behavior stays pure
                    # greedy regardless of where its frames go.  Only the
                    # ratchet-frozen measurement case remains excluded.
                    if self.agent and not metrics.ratchet_frozen:
                        tag = cs.get("prev_action_source", "dqn")
                        # Positive training terminal (ported from expert2):
                        # clearing a wave closes the n-step episode for REPLAY
                        # purposes, so Tz = r there — a bootstrap-free POSITIVE
                        # boundary for a value function whose only other ground
                        # truth is death at v_min.  The live game continues;
                        # HOF/episode bookkeeping still key off frame.done.
                        training_done = bool(frame.done) or (
                            _wave_advanced(cs.get("last_state"), frame,
                                           prev_level_number=cs.get("last_level_number"))
                            and bool(getattr(RL_CONFIG, "wave_clear_training_terminal", False))
                        )
                        nstep = cs.get("nstep")
                        if nstep is not None:
                            joint = combine_action(mv_i, fr_i)
                            matured = nstep.add(cs["last_state"], joint, total_r,
                                                model_state, bool(training_done),
                                                actor=tag, priority_reward=total_r,
                                                interest=interest)
                            for s0, a, Rn, pR, sn, dn, h, act, intr in matured:
                                mv_n, fr_n = split_joint_action(a)
                                self.async_buffer.step_async(
                                    s0, (mv_n, fr_n), Rn, sn, bool(dn),
                                    client_id=cid, actor=act, horizon=int(h), priority_reward=pR,
                                    interest=intr)
                        else:
                            self.async_buffer.step_async(
                                cs["last_state"], (mv_i, fr_i), total_r,
                                model_state, bool(training_done), client_id=cid,
                                actor=tag, horizon=1, priority_reward=total_r,
                                interest=interest)

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
                    if self.async_buffer is not None and not metrics.ratchet_frozen:
                        self.async_buffer.boost_pre_death(cid)
                    if not cs.get("was_done", False):
                        ep_len = cs.get("ep_frames", 0)
                        if eval_only:
                            metrics.add_eval_episode_reward(
                                cs["total_reward"], frame.game_score, frame.level_number, length=ep_len)
                        else:
                            metrics.add_episode_reward(
                                cs["total_reward"], cs["ep_dqn_reward"], cs["ep_expert_reward"],
                                cs.get("ep_subj_reward", 0.0), cs.get("ep_obj_reward", 0.0),
                                cs.get("ep_death_reward", 0.0),
                                length=ep_len)
                            # Frozen-measurement games are excluded: they would
                            # poison the elite high-water mark (all-greedy play
                            # rates "elite" against noisy play) and admit
                            # measurement games to the HOF; their scores are
                            # already captured via ratchet_note_eval_episode.
                            if self.async_buffer is not None and not metrics.ratchet_frozen:
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
                        _pv = self._preview_enabled_for_client(cid)
                        _hd = self._hud_enabled_for_client(cid)
                        sock.sendall(self._pack_action(
                            -1, -1, _SRC_NONE, cid,
                            preview_enabled=_pv,
                            hud_enabled=_hd,
                        ))
                    except Exception:
                        break
                    cs["last_state"] = cs["last_action"] = None
                    cs["prev_action_source"] = None
                    cs["total_reward"] = cs["ep_dqn_reward"] = cs["ep_dqn_score_reward"] = cs["ep_expert_reward"] = 0.0
                    cs["ep_subj_reward"] = cs["ep_obj_reward"] = cs["ep_death_reward"] = 0.0
                    cs["ep_frames"] = 0
                    cs["ep_dqn_frames"] = 0
                    cs["no_human_no_score_frames"] = 0
                    cs["fire_hold_dir"] = -1
                    cs["fire_hold_count"] = 0
                    cs["fire_pending_dir"] = -1
                    hist = cs.get("frame_history")
                    if hist is not None:
                        hist.clear()
                    continue

                if cs.get("was_done"):
                    cs["was_done"] = False
                    # New game starts here — stamp it so ratchet measurements can
                    # exclude games already in flight when the fleet was frozen.
                    cs["ep_t0"] = time.time()
                    cs["total_reward"] = cs["ep_dqn_reward"] = cs["ep_dqn_score_reward"] = cs["ep_expert_reward"] = 0.0
                    cs["ep_subj_reward"] = cs["ep_obj_reward"] = cs["ep_death_reward"] = 0.0
                    cs["ep_frames"] = 0
                    cs["ep_dqn_frames"] = 0
                    cs["no_human_no_score_frames"] = 0

                # ── Not playable (death animation / between lives) ──────
                if not frame.player_alive:
                    cs["last_state"] = cs["last_action"] = None
                    cs["prev_action_source"] = None
                    cs["no_human_no_score_frames"] = 0
                    cs["fire_hold_dir"] = -1
                    cs["fire_hold_count"] = 0
                    cs["fire_pending_dir"] = -1
                    hist = cs.get("frame_history")
                    if hist is not None:
                        hist.clear()
                    if (cs.get("nstep") is not None):
                        cs["nstep"].reset()
                    try:
                        _pv = self._preview_enabled_for_client(cid)
                        _hd = self._hud_enabled_for_client(cid)
                        sock.sendall(self._pack_action(
                            -1, -1, _SRC_NONE, cid,
                            preview_enabled=_pv,
                            hud_enabled=_hd,
                        ))
                    except Exception:
                        break
                    continue

                # ── Choose action ───────────────────────────────────────
                metrics.increment_total_controls()
                mv_idx, fr_idx = 8, 8           # idle defaults
                action_source = "none"

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
                    use_expert = (random.random() < expert_ratio) and not metrics.override_expert and not eval_only

                    if use_expert and get_expert_action is not None:
                        # Clamp wave to >=1 like v3 — the expert's rescue/tank-wave
                        # logic keys off wave_number and misbehaves at 0.
                        wave = max(1, int(frame.level_number))
                        mv_idx, fr_idx = get_expert_action(frame.state, wave,
                                                           locked_fire=locked_fire)
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
                cs["last_game_score"] = int(frame.game_score)
                cs["last_level_number"] = int(frame.level_number)
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
                            nt = sum(1 for s in slots if s["pool"] == "destructible")
                            nb = sum(1 for s in slots if s["pool"] == "hulk")
                            no = sum(1 for s in slots if s["pool"] == "obstacle")
                        except Exception as _e:
                            slots, nh, nt, nb, no = [], -1, -1, -1, -1
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
                            f"ents={len(slots)}(T{nt}/B{nb}/O{no}/H{nh}) wave={int(frame.level_number)} "
                            f"mv={int(mv_idx)}->{move_cmd} fr={int(effective_fire)}->{fire_cmd} "
                            f"xr={metrics.get_expert_ratio():.2f} eps={metrics.get_effective_epsilon():.2f} "
                            f"{qinfo}", flush=True)

                try:
                    _pv = self._preview_enabled_for_client(cid)
                    _hd = self._hud_enabled_for_client(cid)
                    sock.sendall(self._pack_action(
                        move_cmd, fire_cmd, src_code, cid,
                        preview_enabled=_pv,
                        hud_enabled=_hd,
                    ))
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
                _dead_cs = self.client_states.pop(cid, None)
                self._eval_override.pop(cid, None)
                self.clients[cid] = None
                _, preview_changed = self._ensure_preview_client_selected_locked()
                self._sync_client_count_locked()
            if preview_changed:
                self._clear_preview_cache()
            if self.async_buffer is not None:
                self.async_buffer.remove_client(cid)
            # Ratchet cohort accounting: if this client died mid-game and that
            # game was in the measurement cohort, un-count it so the epoch
            # doesn't wait for a score that can never arrive.
            try:
                if _dead_cs is not None and not _dead_cs.get("cohort_voided", False):
                    metrics.ratchet_note_eval_abandoned(float(_dead_cs.get("game_t0", 0.0)))
            except Exception:
                pass
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
                lvls = [
                    s.get("level_number", 0)
                    for s in self.client_states.values()
                    if s.get("level_number", 0) >= 0 and s.get("game_score", 0) > 0
                ]
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
