#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN CONFIGURATION                                                                            ||
# ||  Rainbow-lite engine (C51 + dueling + PER + n-step + target net + expert BC), object-list attention,       ||
# ||  and a joint twin-stick action head.  Ported and refactored from the Tempest DQN.                           ||
# ==================================================================================================================
"""Central configuration: server, RL hyper-parameters, game settings, metrics.

State representation
--------------------
Each frame the Lua client sends ``WIRE_PARAMS_COUNT`` (2130) big-endian f32
values. The DQN consumes a deliberately plain single-frame slice of that wire:
the 18 core game/player scalars, the 22 raw ELIST/level-state bytes, 16
directional lane-density scalars, 3 nearest-destructible-target scalars, 16
nearest typed-object scalars, and 96 role-aware object rows distilled from the
projectile, danger, human, and electrode tactical pools. Each object row also
includes compact shot-alignment geometry for the nearest useful fire ray. The
full lane and grid blocks plus a diagnostics trailer remain on the wire for
expert/debugging paths, but are not part of the DQN model input.

Action representation
---------------------
Robotron is twin-stick: an independent 8-way movement stick and 8-way fire
stick, each with an idle option (9 options per stick).  The replay buffer stores
the joint action index ``move * NUM_FIRE_ACTIONS + fire`` (0..80).  The main
Bellman policy head is a joint 81-action C51 head; branch heads are retained for
auxiliary expert imitation and diagnostics.
"""

if __name__ == "__main__":
    print("This is not the main application, run 'main.py' instead")
    exit(1)

import os, sys, time, threading, math, json
from dataclasses import dataclass, field
from typing import Deque
from collections import deque

import numpy as np

IS_INTERACTIVE = sys.stdin.isatty()
RESET_METRICS = False
FORCE_FRESH_MODEL = False

# Resolve the model directory to an absolute path (Robotron/models_dqn) so it
# is independent of the current working directory, matching the v3 launcher.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../Scripts
_ROBOTRON_DIR = os.path.dirname(_SCRIPTS_DIR)                                # .../Robotron
_env_model_dir = (os.getenv("ROBOTRON_DQN_MODEL_DIR") or "").strip()
MODEL_DIR = os.path.abspath(os.path.expanduser(_env_model_dir)) if _env_model_dir \
    else os.path.join(_ROBOTRON_DIR, "models_dqn")
LATEST_MODEL_PATH = os.path.join(MODEL_DIR, "robotron_dqn_latest.pt")
SETTINGS_PATH = os.path.join(MODEL_DIR, "game_settings.json")

# ---------------------------------------------------------------------------
#  Wire / state-slice geometry
# ---------------------------------------------------------------------------
# Number of f32 values the Lua client packs into each frame's state payload.
# The 96-slot danger pool adds 640 floats over the prior 1478-float wire.
WIRE_PARAMS_COUNT = 2130

# Model slice: 18 core game features + 22 ELIST/level-state features +
# 16 lane-density features + nearest target dx/dy/dist + nearest typed-object
# summaries + 96 role-aware object rows × 21 features.
CORE_FEATURES = 18                       # wire[0:18]
ELIST_FEATURES = 22                      # wire[18:40]
CORE_ELIST_FEATURES = CORE_FEATURES + ELIST_FEATURES
LANE_COUNT = 8                           # 8 fire/move directions
LANE_FEATURES = 30                       # features per lane
LANE_SUMMARY_FEATURES = LANE_COUNT * 2   # enemy density + human density per action direction
LANE_SUMMARY_OFFSET = CORE_ELIST_FEATURES
LANE_SUMMARY_END = LANE_SUMMARY_OFFSET + LANE_SUMMARY_FEATURES
TARGET_SUMMARY_FEATURES = 3              # nearest destructible target dx, dy, dist
TARGET_SUMMARY_OFFSET = LANE_SUMMARY_END
TARGET_SUMMARY_END = TARGET_SUMMARY_OFFSET + TARGET_SUMMARY_FEATURES
TYPE_NEAREST_FEATURES = 16               # grunt/hulk/projectile/blocker/human nearest summaries
TYPE_NEAREST_OFFSET = TARGET_SUMMARY_END
TYPE_NEAREST_END = TYPE_NEAREST_OFFSET + TYPE_NEAREST_FEATURES
GLOBAL_FEATURES = TYPE_NEAREST_END
TACTICAL_LANE_OFFSET = CORE_ELIST_FEATURES
TACTICAL_LANE_END = TACTICAL_LANE_OFFSET + LANE_COUNT * LANE_FEATURES   # 280
# Lua emits lane rows in geometric angle order:
#   E, NE, N, NW, W, SW, S, SE
# Model actions are controller order:
#   N, NE, E, SE, S, SW, W, NW
# Reorder lanes so model lane row N lines up with move/fire action N.
ACTION_LANE_WIRE_INDICES = (2, 1, 0, 7, 6, 5, 4, 3)
TACTICAL_GRID_FEATURES = 9 * 9 * 6
TACTICAL_GRID_OFFSET = TACTICAL_LANE_END
TACTICAL_GRID_END = TACTICAL_GRID_OFFSET + TACTICAL_GRID_FEATURES        # 766
TACTICAL_POOL_OFFSET = TACTICAL_GRID_END

# Role-aware object-token section. Rows are distilled from all Lua tactical
# pools, sorted by immediate action relevance, and capped to keep the model
# compact.
OBJECT_TOKEN_COUNT = 96
OBJECT_BASE_FEATURES = 16
SHOT_ALIGNMENT_FEATURES = 5
OBJECT_TOKEN_FEATURES = OBJECT_BASE_FEATURES + SHOT_ALIGNMENT_FEATURES
OBJECT_SHOT_DIR_X = 16
OBJECT_SHOT_DIR_Y = 17
OBJECT_SHOT_ALIGN_DX = 18
OBJECT_SHOT_ALIGN_DY = 19
OBJECT_SHOT_ALIGN_DIST = 20
OBJECT_FEATURES = OBJECT_TOKEN_COUNT * OBJECT_TOKEN_FEATURES
OBJECT_TOKEN_OFFSET = GLOBAL_FEATURES
OBJECT_TOKEN_END = OBJECT_TOKEN_OFFSET + OBJECT_FEATURES
SINGLE_FRAME_STATE_SIZE = OBJECT_TOKEN_END                                    # 2091
_frame_stack_env = os.getenv("DQN_FRAME_STACK", os.getenv("ROBOTRON_DQN_FRAME_STACK", "1"))
try:
    FRAME_STACK_COUNT = max(1, int(_frame_stack_env))
except Exception:
    FRAME_STACK_COUNT = 1
MODEL_STATE_SIZE = SINGLE_FRAME_STATE_SIZE * FRAME_STACK_COUNT


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return int(default)

# Pool layout mirrors main.lua tactical pool emission.
TACTICAL_POOL_DEFS = (
    ("projectile", 24, 11),
    ("danger", 96, 10),
    ("human", 12, 7),
    ("electrode", 8, 5),
)
TACTICAL_POOL_FEATURES = sum(1 + max_slots * feat_per_slot for _, max_slots, feat_per_slot in TACTICAL_POOL_DEFS)
TACTICAL_POOL_END = TACTICAL_POOL_OFFSET + TACTICAL_POOL_FEATURES        # 2118
TACTICAL_DIAG_OFFSET = TACTICAL_POOL_END
TACTICAL_DIAG_FEATURES = 12
TACTICAL_DIAG_END = TACTICAL_DIAG_OFFSET + TACTICAL_DIAG_FEATURES        # 2130

# Compatibility aliases for callers/tests that still use the previous enemy-list
# names. The representation is now a unified object list, not danger-only.
ENEMY_TOKEN_COUNT = OBJECT_TOKEN_COUNT
ENEMY_TOKEN_FEATURES = OBJECT_TOKEN_FEATURES
ENEMY_FEATURES = OBJECT_FEATURES
ENEMY_TOKEN_OFFSET = OBJECT_TOKEN_OFFSET
ENEMY_TOKEN_END = OBJECT_TOKEN_END

_ROLE_NORM = {"projectile": 0.25, "danger": 0.50, "human": 0.75, "electrode": 1.00}
_TYPE_NORM_DEFAULT = {"projectile": 6.0 / 11.0, "danger": 0.0, "human": 7.0 / 11.0, "electrode": 8.0 / 11.0}
_LANE_ENEMY_COUNT_OFFSET = 7
_LANE_HUMAN_COUNT_OFFSET = 11
_FIRE_DIRS = np.asarray([
    [0.0, -1.0], [1.0, -1.0], [1.0, 0.0], [1.0, 1.0],
    [0.0, 1.0], [-1.0, 1.0], [-1.0, 0.0], [-1.0, -1.0],
], dtype=np.float32)
_FIRE_DIRS = _FIRE_DIRS / np.maximum(np.linalg.norm(_FIRE_DIRS, axis=1, keepdims=True), 1.0)


def _clip01(v: float) -> float:
    try:
        x = float(v)
    except Exception:
        return 0.0
    if not math.isfinite(x):
        return 0.0
    return min(1.0, max(0.0, x))


def _clip11(v: float) -> float:
    try:
        x = float(v)
    except Exception:
        return 0.0
    if not math.isfinite(x):
        return 0.0
    return min(1.0, max(-1.0, x))


def _extract_lane_density_features(arr: np.ndarray) -> np.ndarray:
    """Return 8×(enemy_density, human_density) in controller action order."""
    out = np.zeros((LANE_COUNT, 2), dtype=np.float32)
    start = TACTICAL_LANE_OFFSET
    end = TACTICAL_LANE_END
    if len(arr) < end:
        return out.reshape(-1)
    lanes = arr[start:end].reshape(LANE_COUNT, LANE_FEATURES)
    for action_idx, wire_lane_idx in enumerate(ACTION_LANE_WIRE_INDICES):
        if 0 <= wire_lane_idx < LANE_COUNT:
            lane = lanes[wire_lane_idx]
            out[action_idx, 0] = _clip01(lane[_LANE_ENEMY_COUNT_OFFSET])
            out[action_idx, 1] = _clip01(lane[_LANE_HUMAN_COUNT_OFFSET])
    return out.reshape(-1)


def _shot_alignment_features(dx: float, dy: float) -> list[float]:
    """Return best fire ray plus player movement residual to line up that shot.

    The residual is the movement delta the player would need, in normalized
    relative-position units, so the target lies exactly on the chosen 8-way fire
    ray. Example: target right and slightly up -> best ray right, residual
    y negative, meaning move up to align the shot.
    """
    x = _clip11(dx)
    y = _clip11(dy)
    mag = math.hypot(x, y)
    if mag <= 1e-6:
        return [0.0, 0.0, 0.0, 0.0, 0.0]

    unit = np.asarray([x / mag, y / mag], dtype=np.float32)
    idx = int(np.argmax(_FIRE_DIRS @ unit))
    fx = float(_FIRE_DIRS[idx, 0])
    fy = float(_FIRE_DIRS[idx, 1])
    forward = (x * fx) + (y * fy)
    align_x = _clip11(x - (fx * forward))
    align_y = _clip11(y - (fy * forward))
    align_dist = _clip01(math.hypot(align_x, align_y))
    return [fx, fy, align_x, align_y, align_dist]


def _extract_object_tokens(arr: np.ndarray) -> np.ndarray:
    """Return a role-aware top-K object list from the Lua tactical pools.

    Row layout:
    ``[present, dx, dy, dist, vx, vy, threat, approach, ttc, closest_pass,
    type_norm, role_norm, destructible, blocker, rescue, projectile,
    best_fire_dx, best_fire_dy, shot_align_dx, shot_align_dy,
    shot_align_dist]``.
    """
    tokens = []
    pools = arr[TACTICAL_POOL_OFFSET:]
    pool_offset = 0

    for pool_name, max_slots, feat_per_slot in TACTICAL_POOL_DEFS:
        slot_start = pool_offset + 1
        slot_end = slot_start + max_slots * feat_per_slot
        if slot_end > len(pools):
            pool_offset += 1 + max_slots * feat_per_slot
            continue
        raw = pools[slot_start:slot_end].reshape(max_slots, feat_per_slot)
        for slot_idx in range(max_slots):
            slot = raw[slot_idx]
            if not np.isfinite(slot).all() or slot[0] <= 0.5:
                continue

            dx = _clip11(slot[1] if feat_per_slot > 1 else 0.0)
            dy = _clip11(slot[2] if feat_per_slot > 2 else 0.0)
            dist = _clip01(slot[3] if feat_per_slot > 3 else 1.0)
            vx = _clip11(slot[4] if feat_per_slot > 4 else 0.0)
            vy = _clip11(slot[5] if feat_per_slot > 5 else 0.0)
            threat = 0.0
            approach = 0.0
            ttc = 1.0
            closest_pass = dist
            type_norm = _TYPE_NORM_DEFAULT.get(pool_name, 0.0)
            destructible = 0.0
            blocker = 0.0
            rescue = 0.0
            projectile = 0.0

            if pool_name == "projectile":
                threat = _clip01(slot[6] if feat_per_slot > 6 else 0.8)
                ttc = _clip01(slot[7] if feat_per_slot > 7 else 1.0)
                closest_pass = _clip01(slot[8] if feat_per_slot > 8 else dist)
                approach = _clip11(slot[9] if feat_per_slot > 9 else 0.0)
                if feat_per_slot > 10 and float(slot[10]) >= 0.5:
                    type_norm = 9.0 / 11.0
                destructible = 1.0
                projectile = 1.0
                priority = 5.0 * (1.0 - dist) + 3.0 * (1.0 - ttc) + 2.0 * threat + 1.0
            elif pool_name == "danger":
                threat = _clip01(slot[6] if feat_per_slot > 6 else 0.6)
                approach = _clip11(slot[7] if feat_per_slot > 7 else 0.0)
                ttc = _clip01(slot[8] if feat_per_slot > 8 else 1.0)
                if feat_per_slot > 9:
                    type_norm = _clip01(float(slot[9]) * (8.0 / 11.0))
                is_hulk = abs(type_norm - (1.0 / 11.0)) < 0.05
                destructible = 0.0 if is_hulk else 1.0
                blocker = 1.0 if is_hulk else 0.0
                priority = 4.0 * (1.0 - dist) + 2.0 * threat + 1.0 * (1.0 - ttc) + 0.5 * blocker
            elif pool_name == "human":
                threat = _clip01(slot[6] if feat_per_slot > 6 else 0.0)
                rescue = 1.0
                priority = 1.6 * (1.0 - dist) + 0.25
            else:  # electrode
                threat = _clip01(slot[4] if feat_per_slot > 4 else 0.7)
                blocker = 1.0
                priority = 3.0 * (1.0 - dist) + 2.0 * threat + 0.75

            shot = _shot_alignment_features(dx, dy)
            tokens.append((
                float(priority),
                [
                    1.0, dx, dy, dist, vx, vy, threat, approach, ttc, closest_pass,
                    type_norm, _ROLE_NORM.get(pool_name, 0.0),
                    destructible, blocker, rescue, projectile,
                    *shot,
                ],
            ))
        pool_offset += 1 + max_slots * feat_per_slot

    out = np.zeros((OBJECT_TOKEN_COUNT, OBJECT_TOKEN_FEATURES), dtype=np.float32)
    if tokens:
        tokens.sort(key=lambda item: item[0], reverse=True)
        for row, (_, vals) in enumerate(tokens[:OBJECT_TOKEN_COUNT]):
            out[row] = np.asarray(vals, dtype=np.float32)
    return out.reshape(-1)


def extract_tactical_diagnostics(wire, model_state=None) -> dict:
    """Return runtime diagnostics for Lua tactical pools and Python object rows.

    These values are observability-only; they are not appended to the DQN model
    input.  Lua emits a 12-float trailer after the tactical pools:
    raw counts, emitted slot counts, then Lua pool drops for projectile, danger,
    human, and electrode.
    """
    arr = np.asarray(wire, dtype=np.float32)
    diag: dict[str, float] = {}
    role_names = ("projectile", "danger", "human", "electrode")

    slot_active: dict[str, int] = {}
    off = TACTICAL_POOL_OFFSET
    for pool_name, max_slots, feat_per_slot in TACTICAL_POOL_DEFS:
        active_slots = 0
        slot_start = off + 1
        slot_end = slot_start + max_slots * feat_per_slot
        if slot_end <= len(arr):
            raw = arr[slot_start:slot_end].reshape(max_slots, feat_per_slot)
            active_slots = int(np.count_nonzero(np.isfinite(raw[:, 0]) & (raw[:, 0] > 0.5)))
        slot_active[pool_name] = active_slots
        off += 1 + max_slots * feat_per_slot

    if len(arr) >= TACTICAL_DIAG_END:
        vals = np.asarray(arr[TACTICAL_DIAG_OFFSET:TACTICAL_DIAG_END], dtype=np.float32)
        raw_counts = {name: max(0, int(round(float(vals[i])))) for i, name in enumerate(role_names)}
        emit_counts = {name: max(0, int(round(float(vals[i + 4])))) for i, name in enumerate(role_names)}
        drop_counts = {name: max(0, int(round(float(vals[i + 8])))) for i, name in enumerate(role_names)}
    else:
        raw_counts = dict(slot_active)
        emit_counts = dict(slot_active)
        drop_counts = {name: 0 for name in role_names}

    for name in role_names:
        diag[f"lua_pool_{name}"] = float(raw_counts.get(name, 0))
        diag[f"lua_emitted_{name}"] = float(emit_counts.get(name, slot_active.get(name, 0)))
        diag[f"lua_dropped_{name}"] = float(drop_counts.get(name, 0))
        diag[f"wire_slots_{name}"] = float(slot_active.get(name, 0))

    lua_dropped_total = sum(drop_counts.get(name, 0) for name in role_names)
    emitted_total = sum(max(slot_active.get(name, 0), emit_counts.get(name, 0)) for name in role_names)
    diag["lua_pool_dropped"] = float(lua_dropped_total)
    diag["wire_slots_active"] = float(sum(slot_active.values()))

    try:
        ms = np.asarray(model_state if model_state is not None else slice_model_state(arr), dtype=np.float32)
        rows = ms[OBJECT_TOKEN_OFFSET:OBJECT_TOKEN_END].reshape(OBJECT_TOKEN_COUNT, OBJECT_TOKEN_FEATURES)
        present = np.isfinite(rows[:, 0]) & (rows[:, 0] > 0.5)
        roles = rows[:, 11] if OBJECT_TOKEN_FEATURES > 11 else np.zeros(rows.shape[0], dtype=np.float32)
        row_counts = {
            "projectile": int(np.count_nonzero(present & (np.abs(roles - _ROLE_NORM["projectile"]) < 0.08))),
            "danger": int(np.count_nonzero(present & (np.abs(roles - _ROLE_NORM["danger"]) < 0.08))),
            "human": int(np.count_nonzero(present & (np.abs(roles - _ROLE_NORM["human"]) < 0.08))),
            "electrode": int(np.count_nonzero(present & (np.abs(roles - _ROLE_NORM["electrode"]) < 0.08))),
        }
        active_rows = int(np.count_nonzero(present))
    except Exception:
        row_counts = {name: 0 for name in role_names}
        active_rows = 0

    for name in role_names:
        diag[f"py_rows_{name}"] = float(row_counts.get(name, 0))
    py_clipped = max(0, emitted_total - active_rows)
    diag["py_rows_active"] = float(active_rows)
    diag["py_rows_clipped"] = float(py_clipped)
    diag["object_rows_dropped_total"] = float(lua_dropped_total + py_clipped)
    return diag


def _extract_nearest_destructible_target_features(objects: np.ndarray) -> np.ndarray:
    """Return ``[dx, dy, dist]`` for the nearest targetable object."""
    try:
        rows = np.asarray(objects, dtype=np.float32).reshape(OBJECT_TOKEN_COUNT, OBJECT_TOKEN_FEATURES)
    except Exception:
        return np.asarray([0.0, 0.0, 1.0], dtype=np.float32)
    present = rows[:, 0] > 0.5
    destructible = rows[:, 12] > 0.5 if OBJECT_TOKEN_FEATURES > 12 else present
    rescue = rows[:, 14] > 0.5 if OBJECT_TOKEN_FEATURES > 14 else np.zeros_like(present, dtype=bool)
    target = present & destructible & ~rescue
    if not np.any(target):
        return np.asarray([0.0, 0.0, 1.0], dtype=np.float32)
    dist = np.where(target, np.clip(rows[:, 3], 0.0, 1.0), np.inf)
    idx = int(np.argmin(dist))
    return np.asarray([
        _clip11(rows[idx, 1]),
        _clip11(rows[idx, 2]),
        _clip01(rows[idx, 3]),
    ], dtype=np.float32)


def _nearest_row_features(rows: np.ndarray, mask: np.ndarray, include_ttc: bool = False) -> np.ndarray:
    out_len = 4 if include_ttc else 3
    out = np.zeros(out_len, dtype=np.float32)
    out[2] = 1.0
    if include_ttc:
        out[3] = 1.0
    if rows.size <= 0 or not np.any(mask):
        return out

    dist = np.where(mask, np.clip(rows[:, 3], 0.0, 1.0), np.inf)
    idx = int(np.argmin(dist))
    if not np.isfinite(dist[idx]):
        return out
    out[0] = _clip11(rows[idx, 1])
    out[1] = _clip11(rows[idx, 2])
    out[2] = _clip01(rows[idx, 3])
    if include_ttc:
        out[3] = _clip01(rows[idx, 8] if rows.shape[1] > 8 else 1.0)
    return out


def _extract_type_nearest_features(objects: np.ndarray) -> np.ndarray:
    """Return nearest typed-object summaries.

    Layout:
    ``grunt dx/dy/dist, hulk dx/dy/dist, projectile dx/dy/dist/ttc,
    blocker dx/dy/dist, human dx/dy/dist``.
    """
    try:
        rows = np.asarray(objects, dtype=np.float32).reshape(OBJECT_TOKEN_COUNT, OBJECT_TOKEN_FEATURES)
    except Exception:
        return np.asarray([0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0,
                           0.0, 0.0, 1.0, 0.0, 0.0, 1.0], dtype=np.float32)

    present = rows[:, 0] > 0.5
    role = rows[:, 11] if OBJECT_TOKEN_FEATURES > 11 else np.zeros(rows.shape[0], dtype=np.float32)
    type_norm = rows[:, 10] if OBJECT_TOKEN_FEATURES > 10 else np.zeros(rows.shape[0], dtype=np.float32)
    projectile = rows[:, 15] > 0.5 if OBJECT_TOKEN_FEATURES > 15 else np.zeros(rows.shape[0], dtype=bool)
    blocker = rows[:, 13] > 0.5 if OBJECT_TOKEN_FEATURES > 13 else np.zeros(rows.shape[0], dtype=bool)
    rescue = rows[:, 14] > 0.5 if OBJECT_TOKEN_FEATURES > 14 else np.zeros(rows.shape[0], dtype=bool)
    danger_role = np.abs(role - _ROLE_NORM["danger"]) < 0.08

    grunt = present & danger_role & (type_norm < 0.04)
    hulk = present & danger_role & (np.abs(type_norm - (1.0 / 11.0)) < 0.05)
    pieces = [
        _nearest_row_features(rows, grunt),
        _nearest_row_features(rows, hulk),
        _nearest_row_features(rows, present & projectile, include_ttc=True),
        _nearest_row_features(rows, present & blocker),
        _nearest_row_features(rows, present & rescue),
    ]
    return np.concatenate(pieces).astype(np.float32, copy=False)


def slice_model_state(wire) -> np.ndarray:
    """Extract the compact model input from a full wire vector.

    ``wire`` may be any sequence of length >= TACTICAL_POOL_OFFSET.  Returns a
    contiguous float32 array of length ``SINGLE_FRAME_STATE_SIZE`` laid out as
    ``[core(18), elist(22), lane_density(8×2), target(3), type_nearest(16),
    objects(96×21)]``.
    """
    arr = np.asarray(wire, dtype=np.float32)
    core_elist = arr[0:CORE_ELIST_FEATURES]
    lane_density = _extract_lane_density_features(arr)
    objects = _extract_object_tokens(arr)
    target = _extract_nearest_destructible_target_features(objects)
    type_nearest = _extract_type_nearest_features(objects)
    return np.concatenate([core_elist, lane_density, target, type_nearest, objects]).astype(np.float32, copy=False)


# ---------------------------------------------------------------------------
@dataclass
class ServerConfigData:
    host: str = "0.0.0.0"
    port: int = 9998
    max_clients: int = 36
    wire_params_count: int = WIRE_PARAMS_COUNT

SERVER_CONFIG = ServerConfigData()

# ---------------------------------------------------------------------------
@dataclass
class RLConfigData:
    # ── state / action ──────────────────────────────────────────────────
    single_frame_state_size: int = SINGLE_FRAME_STATE_SIZE
    frame_stack: int = FRAME_STACK_COUNT
    state_size: int = MODEL_STATE_SIZE

    # Factored twin-stick action space.  Index 0..7 = direction, 8 = idle.
    num_move_actions: int = 9
    num_fire_actions: int = 9

    @property
    def num_joint_actions(self) -> int:
        return self.num_move_actions * self.num_fire_actions   # 81

    # State-slice geometry (mirrors module constants, exposed for components)
    core_features: int = CORE_FEATURES
    elist_features: int = ELIST_FEATURES
    core_elist_features: int = CORE_ELIST_FEATURES
    lane_summary_features: int = LANE_SUMMARY_FEATURES
    target_summary_features: int = TARGET_SUMMARY_FEATURES
    type_nearest_features: int = TYPE_NEAREST_FEATURES
    global_features: int = GLOBAL_FEATURES
    type_nearest_offset: int = TYPE_NEAREST_OFFSET
    lane_count: int = 0
    lane_features: int = 0
    extra_features: int = 0
    object_token_count: int = OBJECT_TOKEN_COUNT
    object_token_features: int = OBJECT_TOKEN_FEATURES
    enemy_token_count: int = OBJECT_TOKEN_COUNT      # compatibility alias
    enemy_token_features: int = OBJECT_TOKEN_FEATURES
    tactical_diagnostics_sample_every: int = max(1, _env_int("ROBOTRON_TACTICAL_DIAG_EVERY", 30))

    # ── network architecture ────────────────────────────────────────────
    trunk_hidden: int = 384
    trunk_layers: int = 2
    use_layer_norm: bool = True
    dropout: float = 0.0

    # Full 8x30 lane attention remains off; the trunk gets only the compact
    # 16-scalar enemy/human lane-density summary above.
    use_lane_attention: bool = False
    attn_heads: int = 8
    attn_dim: int = 128

    # Self-attention over the 96 role-aware object rows.
    use_object_attention: bool = True
    object_attn_heads: int = 8
    object_attn_dim: int = 128

    # Action-conditioned attention for the DQN advantage heads. Fixed direction
    # queries attend over object rows with a Tempest-style geometry bias so each
    # move/fire/joint action starts with the relevant spatial prior.
    use_action_context_attention: bool = True
    action_context_heads: int = 8
    action_context_geometry_bias: bool = True
    action_context_geometry_bias_strength: float = 1.75
    action_context_fire_alignment_width: float = 0.075
    joint_action_embed_dim: int = 32
    action_head_hidden: int = 192

    # Main policy/value head.  Branch heads remain for auxiliary BC + metrics.
    use_joint_head: bool = True
    branch_aux_bc_weight: float = 0.25

    # Distributional C51. Keep the support tight enough that ordinary score,
    # death, and cleanup tradeoffs move several atoms. The previous [-200, 500]
    # support made the post-handoff Bellman loss tiny while Q-values collapsed
    # into a low-contrast band.
    use_distributional: bool = True
    num_atoms: int = 51
    v_min: float = -80.0
    v_max: float = 220.0

    use_dueling: bool = True

    # ── training ────────────────────────────────────────────────────────
    # Net is tiny (~779k params); the GPU is far from saturated at 768, so a
    # larger batch raises samples/sec (and Rpl/F) at near-zero extra wall-time.
    # Keep sampling/transfers inline: pinned-memory or background CUDA host work
    # re-enables the GIL in the free-threaded Torch build and tanks MAME FPS.
    batch_size: int = 1024
    lr: float = 1e-4
    lr_min: float = 5e-5
    lr_warmup_steps: int = 5_000
    lr_cosine_period: int = 1_000_000
    lr_use_restarts: bool = True
    gamma: float = 0.995
    n_step: int = 12
    max_samples_per_frame: float = 20

    # Replay (PER with proportional priorities).  The 96-object representation
    # is wider than the old compact lane slice: state/next_state alone cost
    # about 127 GB at 10M transitions with the default 1-frame stack.
    memory_size: int = 10_000_000
    priority_alpha: float = 0.7
    priority_beta_start: float = 0.4
    priority_beta_frames: int = 10_000_000
    priority_eps: float = 1e-6
    per_new_priority_cap_multiplier: float = 3.0
    min_replay_to_train: int = 10_000

    # Elite/rare-event replay. PER keeps surprising transitions hot, but once a
    # valuable event becomes predictable its TD error can fall out of the sample
    # stream. Reserve a small batch quota for broad "interesting" states:
    # scoring bursts, wave transitions, close danger, target-rich object rows,
    # human opportunities, and terminal/pre-death cues.
    interesting_replay_fraction: float = 0.12
    interesting_replay_min_score: float = 0.55
    max_interesting_replay_fraction: float = 0.20
    interesting_replay_over_cap_min_score: float = 0.95
    legacy_interest_positive_reward: float = 0.75
    interesting_replay_bank_size: int = 1_000_000

    # Recent replay quota: keep the learner responsive to the behavior it is
    # currently generating instead of letting a 10M buffer dilute new outcomes.
    recent_replay_fraction: float = 0.30
    recent_replay_window: int = 1_000_000
    # Demonstration replay quota: keep competent trajectories visible to the
    # Bellman head after live expert actions and BC decay away. This is a small
    # DQfD-style anchor, not permanent expert control.
    expert_replay_fraction: float = 0.12
    expert_replay_bank_size: int = 1_000_000

    # Target network (periodic hard sync)
    target_update_period: int = 1_000
    target_tau: float = 1.0

    # Gradient
    grad_clip_norm: float = 5.0

    # ── exploration ─────────────────────────────────────────────────────
    epsilon_start: float = 1.0
    epsilon_end: float = 0.05
    epsilon_decay_frames: int = 5_000_000
    # Most epsilon steps were affordance-guided (a second mini-expert), so only
    # this fraction broke out of the heuristic manifold.  Raised so exploration
    # can actually discover better-than-expert behaviour.
    safe_epsilon_random_fraction: float = 0.25
    safe_epsilon_temperature: float = 0.25
    # While the expert is still injecting a meaningful share of actions, hold a
    # minimum exploration floor so the agent keeps probing its own (non-expert)
    # action space instead of collapsing to greedy + expert before handoff.
    epsilon_expert_floor: float = 0.12
    epsilon_expert_floor_until_ratio: float = 0.15
    # Manual epsilon pulse (fired with P key, runs for N frames then auto-stops).
    manual_pulse_epsilon: float = 0.25
    manual_pulse_duration_frames: int = 750_000
    epsilon: float = 1.0

    # Expert guidance.  Start with substantial demonstrations, but let the DQN
    # get meaningful early control so n-step returns and epsilon exploration are
    # not dominated by expert futures.
    expert_ratio_start: float = 0.60
    # End at zero: any permanent expert injection anchors the behaviour-policy
    # state distribution to expert-reachable trajectories, capping the agent at
    # demonstrator skill.  Let the policy eventually drive entirely on its own.
    expert_ratio_end: float = 0.0
    # Decay is keyed to TRAINING STEPS, not frames.  At 20k+ fps the steady-state
    # frame:step ratio is ~200:1, so a frame-based 2M schedule completed in ~10k
    # gradient steps (2-3 wall-clock minutes) — the policy never had time to learn
    # before the expert handed off.  Steps are FPS-independent and track learning.
    expert_ratio_decay_start_step: int = 0
    expert_ratio_decay_steps: int = 75_000
    expert_ratio: float = 0.60
    # Demonstrations are sampled per episode/trajectory by default, not per
    # frame. Per-frame expert mixing chops learner n-step returns whenever the
    # actor flips, which hides the delayed death credit Robotron needs.
    expert_guidance_mode: str = "episode"  # "episode" or legacy "frame"

    # Expert BC — also step-based (same FPS-independence rationale as above).
    # This trains auxiliary bc_* heads and shared trunk features.  The acting
    # policy below is trained by the direct Q-policy + margin losses. These
    # auxiliary losses age out with the expert handoff; advisor labels carry the
    # short stabilizing bridge after that.
    expert_bc_weight: float = 1.0
    expert_bc_decay_start_step: int = 0
    expert_bc_decay_steps: int = 75_000
    expert_bc_min_weight: float = 0.0
    # Directly distill demonstrations into the deployed joint Q policy. Cross
    # entropy treats Q(s, a) / temperature as action logits, giving the acting
    # head a real expert-like launch instead of leaving imitation in side heads.
    expert_q_policy_weight: float = 0.35
    expert_q_policy_temperature: float = 10.0
    expert_q_policy_decay_start_step: int = 0
    expert_q_policy_decay_steps: int = 75_000
    expert_q_policy_min_weight: float = 0.0
    # Q-margin also imitates directly into the acting joint head by constraining
    # Q(expert_action) >= Q(other) + margin on expert-visited states.  Left on
    # after handoff it is a hard ceiling, so it decays out with the expert.
    expert_q_margin_weight: float = 0.05
    expert_q_margin: float = 0.50
    expert_q_margin_decay_start_step: int = 0
    expert_q_margin_decay_steps: int = 75_000
    expert_q_margin_min_weight: float = 0.0

    # DAgger-style advisor labels.  The expert still does not act once expert
    # control decays out, but we can ask it what it would have done on learner
    # states. This plugs the BC distribution-shift hole without taking control
    # away from the DQN policy.
    advisor_labels_enabled: bool = True
    # Keep advisor imitation strong through the expert handoff, then release it
    # entirely. A permanent floor stabilized the handoff but plateaued the
    # policy near the advisor; by 300k learner steps Bellman/self-play should be
    # the only acting-head objective.
    advisor_q_policy_weight: float = 0.10
    advisor_q_policy_min_weight: float = 0.0
    advisor_q_policy_temperature: float = 10.0
    advisor_q_policy_decay_start_step: int = 0
    advisor_q_policy_decay_steps: int = 300_000
    advisor_q_margin_weight: float = 0.02
    advisor_q_margin_min_weight: float = 0.0
    advisor_q_margin_decay_start_step: int = 0
    advisor_q_margin_decay_steps: int = 300_000

    # ── reward ──────────────────────────────────────────────────────────
    # Score reward is based on actual game_score delta, not Lua objreward. A
    # 1,000-point event maps to 1.0 reward and a 5,000-point rescue maps to 5.0,
    # comfortably below score_reward_clip so it remains rank-ordered.
    score_reward_scale: float = 0.001
    point_reward_scale: float = 1.0 / score_reward_scale  # Derived: 1000.0
    score_reward_clip: float = 25.0
    subj_reward_scale: float = 0.001
    shaping_reward_clip: float = 0.25
    # Once all humans are gone, stalling the last enemies can extend episodes
    # without strategic value. Penalize no-score live frames only in cleanup
    # states; applying this to all no-human combat swamped the score objective.
    no_human_delay_penalty: float = 0.003
    no_human_delay_max_targets: int = 2
    death_penalty: float = 12.0
    reward_clip: float = 30.0
    death_reward_clip: float = 40.0

    # Deliberate hard-state starts when dashboard auto-curriculum is enabled.
    hard_start_min_level: int = 5
    hard_start_wave_spread: int = 8

    # Episode-level elite replay: preserve tails from rare/high-performing
    # episodes, not only individual interesting transitions.
    elite_episode_score_threshold: int = 90_000
    elite_episode_level_threshold: int = 7
    elite_episode_tail_len: int = 768
    elite_episode_priority_boost: float = 3.0
    elite_episode_interest_score: float = 1.0

    # ── fire cadence ────────────────────────────────────────────────────
    # Hold each fire direction stable for this many frames so the game
    # registers reliable shots.  Applied Python-side; the *effective* (held)
    # fire direction is what gets stored in replay and sent to Lua.
    fire_hold_frames: int = 3

    # ── death attribution ───────────────────────────────────────────────
    death_priority_boost: float = 5.0
    pre_death_lookback: int = 120
    pre_death_priority_boost: float = 3.0
    pre_death_reward_lookback: int = 75
    pre_death_base_penalty: float = 0.03
    pre_death_danger_penalty: float = 0.45
    pre_death_max_penalty: float = 0.65
    pre_death_min_danger: float = 0.15
    pre_death_penalize_expert: bool = False

    # ── inference ───────────────────────────────────────────────────────
    use_separate_inference_model: bool = True
    inference_on_cpu: bool = False         # agent falls back to CPU if no CUDA
    train_cuda_device_index: int = 0
    inference_cuda_device_index: int = 1
    inference_sync_steps: int = 5
    inference_batching_enabled: bool = True
    inference_batch_max_size: int = 128
    inference_batch_wait_ms: float = 1.0
    inference_request_timeout_ms: float = 50.0

    # ── background training ─────────────────────────────────────────────
    training_steps_per_cycle: int = 16
    save_interval: int = 10_000

    # ── replay persistence ──────────────────────────────────────────────
    # The replay buffer can be multi-GB; saving it beside every autosave
    # checkpoint causes heavy I/O that can stall training.  Persist it only
    # on forced/manual saves (and shutdown) unless explicitly overridden.
    save_replay_buffer: bool = True       # master switch
    save_replay_on_autosave: bool = False # if True, periodic autosaves persist replay too

    enable_amp: bool = True

    # Autonomous eval-only clients: no expert, fixed low epsilon, no replay writes.
    # With 50 clients this makes client ids 9/19/29/39/49 eval by default.
    eval_client_stride: int = 10
    eval_client_offset: int = 9
    eval_epsilon: float = 0.01


RL_CONFIG = RLConfigData()

# ---------------------------------------------------------------------------
#  Game Settings (shared between dashboard, socket server, and LUA clients)
# ---------------------------------------------------------------------------
# Robotron waves progress 1, 2, 3, …  The operator can start the agent at an
# arbitrary wave for curriculum training.  This list drives the auto-curriculum
# stepping in the socket server.
ROBOTRON_SELECTABLE_LEVELS = list(range(1, 41))

class GameSettings:
    """Thread-safe container for operator-adjustable game settings."""
    def __init__(self):
        self._lock = threading.Lock()
        self._start_advanced: bool = False
        self._start_level_min: int = 1
        self._epsilon_pct: int = -1   # -1 = auto (follow decay), 0-100 = manual override %
        self._expert_pct: int = -1    # -1 = auto (follow decay), 0-100 = manual override %
        self._auto_curriculum: bool = False

    @property
    def start_advanced(self) -> bool:
        with self._lock:
            return self._start_advanced

    @start_advanced.setter
    def start_advanced(self, value: bool):
        with self._lock:
            self._start_advanced = bool(value)

    @property
    def start_level_min(self) -> int:
        with self._lock:
            return self._start_level_min

    @start_level_min.setter
    def start_level_min(self, value: int):
        with self._lock:
            self._start_level_min = max(1, min(255, int(value)))

    @property
    def epsilon_pct(self) -> int:
        with self._lock:
            return self._epsilon_pct

    @epsilon_pct.setter
    def epsilon_pct(self, value: int):
        with self._lock:
            self._epsilon_pct = max(-1, min(100, int(value)))

    @property
    def expert_pct(self) -> int:
        with self._lock:
            return self._expert_pct

    @expert_pct.setter
    def expert_pct(self, value: int):
        with self._lock:
            self._expert_pct = max(-1, min(100, int(value)))

    @property
    def auto_curriculum(self) -> bool:
        with self._lock:
            return self._auto_curriculum

    @auto_curriculum.setter
    def auto_curriculum(self, value: bool):
        with self._lock:
            self._auto_curriculum = bool(value)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "start_advanced": self._start_advanced,
                "start_level_min": self._start_level_min,
                "epsilon_pct": self._epsilon_pct,
                "expert_pct": self._expert_pct,
                "auto_curriculum": self._auto_curriculum,
            }

    def reset(self) -> None:
        """Restore all settings to initial defaults (fresh-start)."""
        with self._lock:
            self._start_advanced = False
            self._start_level_min = 1
            self._epsilon_pct = -1
            self._expert_pct = -1
            self._auto_curriculum = False

    # ── Persistence ───────────────────────────────────────────────

    def save(self, path: str = SETTINGS_PATH) -> None:
        """Write current settings to a JSON file."""
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            data = self.snapshot()
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except Exception:
            pass  # best-effort; don't crash the server

    def load(self, path: str = SETTINGS_PATH) -> None:
        """Restore settings from a JSON file if it exists."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            with self._lock:
                if "start_advanced" in data:
                    self._start_advanced = bool(data["start_advanced"])
                if "start_level_min" in data:
                    self._start_level_min = max(1, min(255, int(data["start_level_min"])))
                if "epsilon_pct" in data:
                    self._epsilon_pct = max(-1, min(100, int(data["epsilon_pct"])))
                if "expert_pct" in data:
                    self._expert_pct = max(-1, min(100, int(data["expert_pct"])))
                if "auto_curriculum" in data:
                    self._auto_curriculum = bool(data["auto_curriculum"])
        except FileNotFoundError:
            pass  # first run — use defaults
        except Exception:
            pass  # corrupted file — use defaults

game_settings = GameSettings()
game_settings.load()

# ---------------------------------------------------------------------------
#  Metrics
# ---------------------------------------------------------------------------
@dataclass
class MetricsData:
    frame_count: int = 0
    learner_frame_count: int = 0
    total_controls: int = 0
    total_training_steps: int = 0
    memory_buffer_size: int = 0
    client_count: int = 0
    web_client_count: int = 0

    epsilon: float = RL_CONFIG.epsilon_start
    expert_ratio: float = RL_CONFIG.expert_ratio_start

    episode_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    dqn_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    expert_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    subj_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    obj_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    death_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    losses: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    fps: float = 0.0
    frames_last_second: int = 0
    last_fps_time: float = 0.0

    # Interval accumulators (reset each display row)
    loss_sum_interval: float = 0.0
    loss_count_interval: int = 0
    agree_sum_interval: float = 0.0
    agree_count_interval: int = 0
    agree_move_sum_interval: float = 0.0
    agree_fire_sum_interval: float = 0.0
    reward_sum_interval: float = 0.0
    reward_count_interval: int = 0
    reward_sum_interval_dqn: float = 0.0
    reward_count_interval_dqn: int = 0
    reward_sum_interval_subj: float = 0.0
    reward_count_interval_subj: int = 0
    reward_sum_interval_obj: float = 0.0
    reward_count_interval_obj: int = 0
    reward_sum_interval_death: float = 0.0
    reward_count_interval_death: int = 0
    eval_reward_sum_interval: float = 0.0
    eval_score_sum_interval: float = 0.0
    eval_level_sum_interval: float = 0.0
    eval_length_sum_interval: float = 0.0
    eval_count_interval: int = 0
    training_steps_interval: int = 0
    frames_count_interval: int = 0
    episode_length_sum_interval: int = 0
    episode_length_count_interval: int = 0
    completed_score_sum_interval: float = 0.0
    completed_score_count_interval: int = 0
    level_sum_interval: float = 0.0
    level_count_interval: int = 0

    total_inference_time: float = 0.0
    total_inference_requests: int = 0

    last_grad_norm: float = 0.0
    last_loss: float = 0.0
    last_q_mean: float = 0.0
    last_bellman_loss: float = 0.0
    last_imitation_loss: float = 0.0
    last_bc_loss: float = 0.0
    last_bc_weight: float = 0.0
    last_bc_loss_contrib: float = 0.0
    last_expert_q_policy_loss: float = 0.0
    last_expert_q_policy_weight: float = 0.0
    last_expert_q_policy_loss_contrib: float = 0.0
    last_expert_q_margin_loss: float = 0.0
    last_expert_q_margin_weight: float = 0.0
    last_expert_q_margin_loss_contrib: float = 0.0
    last_advisor_q_policy_loss: float = 0.0
    last_advisor_q_policy_weight: float = 0.0
    last_advisor_q_policy_loss_contrib: float = 0.0
    last_advisor_q_margin_loss: float = 0.0
    last_advisor_q_margin_weight: float = 0.0
    last_advisor_q_margin_loss_contrib: float = 0.0
    last_sample_expert_frac: float = 0.0
    last_sample_advisor_frac: float = 0.0
    last_sample_per_frac: float = 0.0
    last_sample_expert_quota_frac: float = 0.0
    last_sample_interesting_frac: float = 0.0
    last_sample_recent_frac: float = 0.0
    last_sample_horizon_mean: float = 0.0
    last_sample_terminal_frac: float = 0.0
    last_inference_sync_age: int = 0
    last_priority_mean: float = 0.0
    last_agreement: float = 0.0
    last_expert_joint_agreement: float = 0.0
    last_learner_joint_agreement: float = 0.0
    last_advisor_joint_agreement: float = 0.0
    last_expert_q_rank_mean: float = 0.0
    last_expert_q_margin_mean: float = 0.0
    last_advisor_q_rank_mean: float = 0.0
    last_advisor_q_margin_mean: float = 0.0
    last_current_q_action_mean: float = 0.0
    last_target_q_mean: float = 0.0
    last_unclamped_target_q_mean: float = 0.0
    last_next_q_max_mean: float = 0.0
    last_target_next_q_mean: float = 0.0
    last_double_q_gap_mean: float = 0.0
    last_td_q_mean: float = 0.0
    last_td_q_abs_mean: float = 0.0
    last_q_gap_mean: float = 0.0
    last_target_clip_low_frac: float = 0.0
    last_target_clip_high_frac: float = 0.0
    last_target_low_atom_mass: float = 0.0
    last_target_high_atom_mass: float = 0.0
    last_target_mass_error_mean: float = 0.0
    last_policy_idle_move_frac: float = 0.0
    last_policy_idle_fire_frac: float = 0.0
    last_policy_noop_frac: float = 0.0
    last_policy_top_action_frac: float = 0.0
    last_policy_action_entropy: float = 0.0
    last_sample_idle_move_frac: float = 0.0
    last_sample_idle_fire_frac: float = 0.0
    last_sample_noop_frac: float = 0.0
    last_sample_top_action_frac: float = 0.0
    last_sample_action_entropy: float = 0.0
    last_sample_reward_mean: float = 0.0
    last_sample_reward_abs_mean: float = 0.0
    last_sample_reward_min: float = 0.0
    last_sample_reward_max: float = 0.0
    last_train_sample_ms: float = 0.0
    last_train_transfer_ms: float = 0.0
    last_train_compute_ms: float = 0.0
    last_train_priority_ms: float = 0.0
    last_train_step_ms: float = 0.0

    average_level: float = 0.0
    average_game_score: float = 0.0
    eval_average_reward: float = 0.0
    eval_average_score: float = 0.0
    eval_average_level: float = 0.0
    eval_average_length: float = 0.0
    eval_episode_count: int = 0
    peak_level: int = 0
    peak_episode_reward: float = 0.0
    peak_game_score: int = 0
    replay_dropped_steps: int = 0
    pre_death_penalized_steps: int = 0
    pre_death_penalized_interval: int = 0
    preview_payload_frames: int = 0
    preview_payload_bytes: int = 0
    preview_payload_interval: int = 0
    tactical_diag_last: dict = field(default_factory=dict)
    tactical_diag_sum_interval: dict = field(default_factory=dict)
    tactical_diag_count_interval: int = 0
    episodes_this_run: int = 0
    last_target_update_step: int = 0
    last_target_update_time: float = 0.0
    loaded_frame_count: int = 0

    # UI toggles
    override_expert: bool = False
    expert_mode: bool = False
    manual_expert_override: bool = False
    override_epsilon: bool = False
    manual_epsilon_override: bool = False
    manual_pulse_active: bool = False
    manual_pulse_frames_remaining: int = 0
    training_enabled: bool = True
    verbose_mode: bool = False
    saved_expert_ratio: float = 0.99

    global_server: object = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    # ── helpers ─────────────────────────────────────────────────────────
    def update_frame_count(self, delta: int = 1):
        with self.lock:
            d = max(1, delta)
            self.frame_count += d
            self.frames_count_interval += d
            self.frames_last_second += d
            now = time.time()
            if self.last_fps_time == 0:
                self.last_fps_time = now
            elapsed = now - self.last_fps_time
            if elapsed >= 1.0:
                self.fps = self.frames_last_second / elapsed
                self.frames_last_second = 0
                self.last_fps_time = now

    def update_learner_frame_count(self, delta: int = 1):
        with self.lock:
            self.learner_frame_count += max(0, int(delta))

    def note_replay_drop(self, n: int = 1):
        """Record dropped replay transitions (queue overflow) for reporting."""
        with self.lock:
            self.replay_dropped_steps += max(0, int(n))

    def note_pre_death_penalty(self, n: int = 1):
        """Record replay rows that received pre-death reward penalties."""
        with self.lock:
            d = max(0, int(n))
            self.pre_death_penalized_steps += d
            self.pre_death_penalized_interval += d

    def note_preview_payload(self, byte_count: int):
        """Record unexpected preview image payloads from Lua clients."""
        try:
            n = max(0, int(byte_count))
        except Exception:
            n = 0
        if n <= 0:
            return
        with self.lock:
            self.preview_payload_frames += 1
            self.preview_payload_bytes += n
            self.preview_payload_interval += 1

    def note_tactical_diagnostics(self, diag: dict):
        """Record sampled Lua pool / Python object-row diagnostics."""
        if not diag:
            return
        clean = {}
        for key, value in dict(diag).items():
            try:
                v = float(value)
            except Exception:
                continue
            if math.isfinite(v):
                clean[str(key)] = v
        if not clean:
            return
        with self.lock:
            self.tactical_diag_last = clean
            for key, value in clean.items():
                self.tactical_diag_sum_interval[key] = self.tactical_diag_sum_interval.get(key, 0.0) + value
            self.tactical_diag_count_interval += 1

    def consume_tactical_diagnostics_interval(self) -> tuple[dict, dict]:
        """Return average sampled tactical diagnostics since the last display row."""
        with self.lock:
            last = dict(self.tactical_diag_last)
            count = int(self.tactical_diag_count_interval)
            if count > 0:
                avg = {key: value / max(1, count) for key, value in self.tactical_diag_sum_interval.items()}
            else:
                avg = {}
            self.tactical_diag_sum_interval = {}
            self.tactical_diag_count_interval = 0
        return avg, last

    def note_game_score(self, score: int):
        """Thread-safe peak game-score update."""
        with self.lock:
            if score > self.peak_game_score:
                self.peak_game_score = int(score)

    def note_completed_game_score(self, score: int | float):
        """Record a completed training episode's final game score for the next report row."""
        try:
            s = float(score)
        except Exception:
            return
        if not math.isfinite(s):
            return
        with self.lock:
            self.completed_score_sum_interval += s
            self.completed_score_count_interval += 1
            if int(s) > self.peak_game_score:
                self.peak_game_score = int(s)

    def consume_completed_game_score_interval(self) -> tuple[float, int]:
        """Return and reset the average final game score since the last report row."""
        with self.lock:
            count = int(self.completed_score_count_interval)
            avg = self.completed_score_sum_interval / max(1, count) if count > 0 else 0.0
            self.completed_score_sum_interval = 0.0
            self.completed_score_count_interval = 0
        return float(avg), count

    def note_game_state_averages(self, average_level: float, average_game_score: float, peak_level: int | None = None):
        """Thread-safe live game-state aggregate update."""
        with self.lock:
            self.average_level = float(average_level)
            self.average_game_score = float(average_game_score)
            if peak_level is not None and int(peak_level) > self.peak_level:
                self.peak_level = int(peak_level)

    def get_fps(self) -> float:
        """Return current FPS, decaying to 0 if no frames arrive for >2s."""
        with self.lock:
            if self.last_fps_time > 0:
                stale = time.time() - self.last_fps_time
                if stale >= 2.0:
                    self.fps = 0.0
            return float(self.fps)

    def get_epsilon(self):
        with self.lock:
            return float(self.epsilon)

    def get_effective_epsilon(self) -> float:
        with self.lock:
            ep = game_settings.epsilon_pct
            if ep >= 0:
                return ep / 100.0
            return 0.0 if self.override_epsilon else float(self.epsilon)

    @staticmethod
    def _natural_epsilon_for_learner_frame(learner_frame_count: int) -> float:
        progress = min(1.0, learner_frame_count / max(1, RL_CONFIG.epsilon_decay_frames))
        return RL_CONFIG.epsilon_start + progress * (RL_CONFIG.epsilon_end - RL_CONFIG.epsilon_start)

    def update_epsilon(self):
        with self.lock:
            if self.manual_epsilon_override:
                return self.epsilon
            base = self._natural_epsilon_for_learner_frame(int(self.learner_frame_count))
            # While the expert still drives a meaningful share of frames, hold a
            # minimum exploration floor so the learner keeps probing its own
            # action space instead of collapsing to greedy before handoff.
            floor_until = float(getattr(RL_CONFIG, "epsilon_expert_floor_until_ratio", 0.0))
            if floor_until > 0.0 and float(self.expert_ratio) > floor_until:
                base = max(base, float(getattr(RL_CONFIG, "epsilon_expert_floor", 0.0)))
            if self.manual_pulse_active:
                self.manual_pulse_frames_remaining -= 1
                if self.manual_pulse_frames_remaining <= 0:
                    self.manual_pulse_active = False
                    self.manual_pulse_frames_remaining = 0
                    self.epsilon = base
                else:
                    self.epsilon = max(base, float(RL_CONFIG.manual_pulse_epsilon))
            else:
                self.epsilon = base
            return self.epsilon

    def get_expert_ratio(self):
        with self.lock:
            xp = game_settings.expert_pct
            if xp >= 0:
                return xp / 100.0
            return float(self.expert_ratio)

    def update_expert_ratio(self):
        with self.lock:
            if self.expert_mode or self.override_expert or self.manual_expert_override:
                return self.expert_ratio
            start_step = int(getattr(RL_CONFIG, "expert_ratio_decay_start_step", 0))
            ts = int(self.total_training_steps)
            if ts <= start_step:
                progress = 0.0
            else:
                progress = min(1.0, (ts - start_step) / max(1, RL_CONFIG.expert_ratio_decay_steps))
            self.expert_ratio = RL_CONFIG.expert_ratio_start + progress * (RL_CONFIG.expert_ratio_end - RL_CONFIG.expert_ratio_start)
            return self.expert_ratio

    def add_episode_reward(self, total, dqn, expert, subj=None, obj=None, death=None, length=0):
        with self.lock:
            self.episodes_this_run += 1
            self.episode_rewards.append(float(total))
            self.dqn_rewards.append(float(dqn))
            self.expert_rewards.append(float(expert))
            if subj is not None:
                self.subj_rewards.append(float(subj))
            if obj is not None:
                self.obj_rewards.append(float(obj))
            if death is not None:
                self.death_rewards.append(float(death))
            self.reward_sum_interval += float(total)
            self.reward_count_interval += 1
            self.reward_sum_interval_dqn += float(dqn)
            self.reward_count_interval_dqn += 1
            if subj is not None:
                self.reward_sum_interval_subj += float(subj)
                self.reward_count_interval_subj += 1
            if obj is not None:
                self.reward_sum_interval_obj += float(obj)
                self.reward_count_interval_obj += 1
            if death is not None:
                self.reward_sum_interval_death += float(death)
                self.reward_count_interval_death += 1
            if length > 0:
                self.episode_length_sum_interval += length
                self.episode_length_count_interval += 1
            if float(total) > self.peak_episode_reward:
                self.peak_episode_reward = float(total)

    def add_eval_episode_reward(self, total, score, level, length=0):
        with self.lock:
            self.eval_episode_count += 1
            self.eval_reward_sum_interval += float(total)
            self.eval_score_sum_interval += float(score)
            self.eval_level_sum_interval += float(level)
            self.eval_length_sum_interval += float(length)
            self.eval_count_interval += 1
            n = min(50, self.eval_episode_count)
            # Lightweight EMA-like rolling display without another deque.
            if n <= 1:
                self.eval_average_reward = float(total)
                self.eval_average_score = float(score)
                self.eval_average_level = float(level)
                self.eval_average_length = float(length)
            else:
                a = 1.0 / float(n)
                self.eval_average_reward = (1.0 - a) * self.eval_average_reward + a * float(total)
                self.eval_average_score = (1.0 - a) * self.eval_average_score + a * float(score)
                self.eval_average_level = (1.0 - a) * self.eval_average_level + a * float(level)
                self.eval_average_length = (1.0 - a) * self.eval_average_length + a * float(length)

    def increment_total_controls(self):
        with self.lock:
            self.total_controls += 1

    def update_game_state(self, enemy_seg, open_level):
        pass  # compat stub

    def add_inference_time(self, t: float):
        with self.lock:
            self.total_inference_time += t
            self.total_inference_requests += 1

    # ── UI toggle methods ───────────────────────────────────────────────
    def toggle_override(self, kb=None):
        with self.lock:
            self.override_expert = not self.override_expert
            if self.override_expert:
                self.saved_expert_ratio = self.expert_ratio
                self.expert_ratio = 0.0
            else:
                self.expert_ratio = self.saved_expert_ratio

    def toggle_expert_mode(self, kb=None):
        with self.lock:
            self.expert_mode = not self.expert_mode
            if self.expert_mode:
                self.saved_expert_ratio = self.expert_ratio
                self.expert_ratio = 1.0
            else:
                self.expert_ratio = self.saved_expert_ratio

    def toggle_training_mode(self, kb=None):
        with self.lock:
            self.training_enabled = not self.training_enabled

    def toggle_epsilon_override(self, kb=None):
        with self.lock:
            self.override_epsilon = not self.override_epsilon

    def toggle_verbose_mode(self, kb=None):
        with self.lock:
            self.verbose_mode = not self.verbose_mode

    def toggle_epsilon_pulse(self, kb=None):
        """Fire or cancel the manual epsilon pulse."""
        with self.lock:
            if self.manual_pulse_active:
                # Cancel the running pulse
                self.manual_pulse_active = False
                self.manual_pulse_frames_remaining = 0
            else:
                # Start a new pulse
                self.manual_pulse_active = True
                self.manual_pulse_frames_remaining = int(RL_CONFIG.manual_pulse_duration_frames)

    def increase_expert_ratio(self, kb=None):
        with self.lock:
            p = int(self.expert_ratio * 100)
            p = min(100, p + (1 if p < 10 else 5))
            self.expert_ratio = p / 100.0
            self.manual_expert_override = True

    def decrease_expert_ratio(self, kb=None):
        with self.lock:
            p = int(self.expert_ratio * 100)
            p = max(0, p - (1 if p <= 10 else 5))
            self.expert_ratio = p / 100.0
            self.manual_expert_override = True

    def restore_natural_expert_ratio(self, kb=None):
        with self.lock:
            self.manual_expert_override = False
            start_step = int(getattr(RL_CONFIG, "expert_ratio_decay_start_step", 0))
            ts = int(self.total_training_steps)
            if ts <= start_step:
                progress = 0.0
            else:
                progress = min(1.0, (ts - start_step) / max(1, RL_CONFIG.expert_ratio_decay_steps))
            self.expert_ratio = RL_CONFIG.expert_ratio_start + progress * (RL_CONFIG.expert_ratio_end - RL_CONFIG.expert_ratio_start)

    def increase_epsilon(self, kb=None):
        with self.lock:
            p = int(self.epsilon * 100)
            p = min(100, p + (1 if p < 10 else 5))
            self.epsilon = p / 100.0
            self.manual_epsilon_override = True

    def decrease_epsilon(self, kb=None):
        with self.lock:
            p = int(self.epsilon * 100)
            p = max(0, p - (1 if p <= 10 else 5))
            self.epsilon = p / 100.0
            self.manual_epsilon_override = True

    def restore_natural_epsilon(self, kb=None):
        with self.lock:
            self.manual_epsilon_override = False
            self.epsilon = self._natural_epsilon_for_learner_frame(int(self.learner_frame_count))


metrics = MetricsData()


# ── PlateauPulser stub ──────────────────────────────────────────────────────
# Provides the interface expected by the dashboard, backed by our manual pulse.
class PlateauPulser:
    WATCHING   = "watching"
    PULSING    = "pulsing"
    RECOVERING = "recovering"

    @property
    def state(self) -> str:
        return self.PULSING if metrics.manual_pulse_active else self.WATCHING

    @property
    def total_pulses(self) -> int:
        return 0                       # manual pulse doesn't track lifetime count

    pulse_start_frame: int = 0
    pulse_end_frame: int = 0
    cooldown_multiplier: float = 1.0


plateau_pulser = PlateauPulser()
