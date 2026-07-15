#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN CONFIGURATION                                                                            ||
# ||  Rainbow-lite engine (C51 + dueling + PER + n-step + target net + expert BC), enemy-list attention,        ||
# ||  and a joint twin-stick action head.  Ported and refactored from the Tempest DQN.                           ||
# ==================================================================================================================
"""Central configuration: server, RL hyper-parameters, game settings, metrics.

State representation
--------------------
Each frame the Lua client sends ``WIRE_PARAMS_COUNT`` (1890) big-endian f32
values. The DQN consumes a deliberately plain single-frame slice of that wire:
the 18 core game/player scalars, the 22 raw ELIST/level-state bytes, and a
112-row distance-sorted object state bag:
64 destructible enemies/projectiles, 16 hulks, 16 obstacles, and 16 humans.
Legacy lanes/grids remain on the wire for the expert/debugging path, but are
not part of the DQN model input.

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
# Best-ever weights by rolling 1M-frame score, saved separately so a training
# collapse is a restore instead of a loss (the 120K-era weights were gone by
# the time the 2026-07-05 LR-restart collapse was diagnosed — never again).
BEST_MODEL_PATH = os.path.join(MODEL_DIR, "robotron_dqn_best.pt")
SETTINGS_PATH = os.path.join(MODEL_DIR, "game_settings.json")

# ---------------------------------------------------------------------------
#  Wire / state-slice geometry
# ---------------------------------------------------------------------------
# Number of f32 values the Lua client packs into each frame's state payload.
# Lua emits four distance-sorted 10-wide state-bag groups after lane/grid data.
WIRE_PARAMS_COUNT = 1890

# Model slice: 18 core game features + 22 ELIST/level-state features +
# 112 grouped object rows × 10 features.
CORE_FEATURES = 18                       # wire[0:18]
ELIST_FEATURES = 22                      # wire[18:40]
GLOBAL_FEATURES = CORE_FEATURES + ELIST_FEATURES
LANE_COUNT = 8                           # 8 fire/move directions
LANE_FEATURES = 30                       # features per lane
TACTICAL_LANE_OFFSET = 40                # wire index where lane blocks begin
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

# Grouped object-list section. Each group is sorted nearest-first; overflow is
# dropped by Lua and defensively re-sorted here.
DESTRUCTIBLE_TOKEN_COUNT = 64
HULK_TOKEN_COUNT = 16
OBSTACLE_TOKEN_COUNT = 16
HUMAN_TOKEN_COUNT = 16
ENEMY_TOKEN_COUNT = (
    DESTRUCTIBLE_TOKEN_COUNT
    + HULK_TOKEN_COUNT
    + OBSTACLE_TOKEN_COUNT
    + HUMAN_TOKEN_COUNT
)

# ── Object row geometry: wire row vs. model token row ──────────────────────
# The Lua wire emits a fixed 10-wide row per object slot:
#   [present, dx, dy, dist, vx, vy, threat, approach, ttc, type_norm]
# The DQN model token row is DERIVED from that wire row in ``_state_bag_row``
# and is WIDER: the ordinal ``type_norm`` scalar is expanded into a
# ``TYPE_CLASS_COUNT`` one-hot (object types are categorical, not ordinal), and
# dx/dy/vx/vy/approach are re-normalized to isotropic, high-resolution scales
# (see the physical constants below). The WIRE format is unchanged, so the
# v3/PPO path and the raw-wire expert remain unaffected.
WIRE_POOL_SLOT_FEATURES = 10             # what Lua packs per object slot (fixed)

# Unified object type ids (must match main.lua UNIFIED_TYPE_ID): grunt=0, hulk=1,
# brain=2, tank=3, spawner=4, enforcer=5, projectile=6, human=7, electrode=8.
TYPE_CLASS_COUNT = 9
TYPE_ONEHOT_OFFSET = 9                    # one-hot occupies model-row cols 9..17

# Model token row = 9 geometric/kinematic features + one-hot type.
ENEMY_TOKEN_FEATURES = TYPE_ONEHOT_OFFSET + TYPE_CLASS_COUNT                   # 18
ENEMY_FEATURES = ENEMY_TOKEN_COUNT * ENEMY_TOKEN_FEATURES
ENEMY_TOKEN_OFFSET = GLOBAL_FEATURES
ENEMY_TOKEN_END = ENEMY_TOKEN_OFFSET + ENEMY_FEATURES
SINGLE_FRAME_STATE_SIZE = ENEMY_TOKEN_END                                     # 2056
_frame_stack_env = os.getenv("DQN_FRAME_STACK", os.getenv("ROBOTRON_DQN_FRAME_STACK", "1"))
try:
    FRAME_STACK_COUNT = max(1, int(_frame_stack_env))
except Exception:
    FRAME_STACK_COUNT = 1
MODEL_STATE_SIZE = SINGLE_FRAME_STATE_SIZE * FRAME_STACK_COUNT

# ── Physical playfield + normalization constants ───────────────────────────
# These MUST match main.lua's GAME_XMIN/XMAX/YMIN/YMAX and POS_* constants.
# Positions are unsigned 8.8 fixed-point (256 raw units == 1 screen pixel).
POS_X_RANGE = (143 - 7) * 256            # 34816  (playfield width, raw units)
POS_Y_RANGE = (234 - 24) * 256           # 53760  (playfield height, raw units)
POS_MAX_DIAG = math.sqrt(POS_X_RANGE * POS_X_RANGE + POS_Y_RANGE * POS_Y_RANGE)  # ~64049
# Velocity normalization: raw units/frame that map to 1.0. 16 px/frame covers the
# full range of real enemy/projectile motion (Lua treats >32 px/frame as slot
# reuse and zeroes it). The wire divides per-frame deltas by the whole playfield
# span, crushing real speeds to ~2-6% of range; we recover and rescale here.
VELOCITY_NORM_SCALE = 16.0 * 256         # 4096
# Wire->model rescale factors. The wire normalizes X by width and Y by height
# (anisotropic); the model uses an isotropic diagonal for position so that
# direction and distance agree (sqrt(dx^2+dy^2) == dist), and a realistic
# per-frame scale for velocity so closing speed fills the usable range.
_WIRE_DX_TO_ISO = POS_X_RANGE / POS_MAX_DIAG          # ~0.5438
_WIRE_DY_TO_ISO = POS_Y_RANGE / POS_MAX_DIAG          # ~0.8397
_WIRE_VX_TO_VEL = POS_X_RANGE / VELOCITY_NORM_SCALE   # ~8.5
_WIRE_VY_TO_VEL = POS_Y_RANGE / VELOCITY_NORM_SCALE   # ~13.125

# Pool layout mirrors main.lua tactical pool emission (WIRE width, 10-wide rows).
TACTICAL_POOL_DEFS = (
    ("destructible", DESTRUCTIBLE_TOKEN_COUNT, WIRE_POOL_SLOT_FEATURES),
    ("hulk", HULK_TOKEN_COUNT, WIRE_POOL_SLOT_FEATURES),
    ("obstacle", OBSTACLE_TOKEN_COUNT, WIRE_POOL_SLOT_FEATURES),
    ("human", HUMAN_TOKEN_COUNT, WIRE_POOL_SLOT_FEATURES),
)

TOKEN_GROUP_RANGES = {
    "destructible": (0, DESTRUCTIBLE_TOKEN_COUNT),
    "hulk": (DESTRUCTIBLE_TOKEN_COUNT, DESTRUCTIBLE_TOKEN_COUNT + HULK_TOKEN_COUNT),
    "obstacle": (
        DESTRUCTIBLE_TOKEN_COUNT + HULK_TOKEN_COUNT,
        DESTRUCTIBLE_TOKEN_COUNT + HULK_TOKEN_COUNT + OBSTACLE_TOKEN_COUNT,
    ),
    "human": (
        DESTRUCTIBLE_TOKEN_COUNT + HULK_TOKEN_COUNT + OBSTACLE_TOKEN_COUNT,
        ENEMY_TOKEN_COUNT,
    ),
}

# Group ranges in pool-emission order (destructible, hulk, obstacle, human).
OBJECT_GROUP_RANGES = tuple(TOKEN_GROUP_RANGES[name] for name, _, _ in TACTICAL_POOL_DEFS)

# ── Flat-trunk exposure: nearest-K rows per group ───────────────────────────
# The raw MLP trunk should NOT see all 112 slot-sorted rows: distance sorting
# makes slot contents churn (object A overtaking B swaps their slots), so
# slot-specific first-layer weights must relearn the same feature per slot.
# Only the nearest few rows per group are slot-stable enough to deserve
# dedicated weights; the long tail reaches the trunk through the
# permutation-invariant object-attention digest instead.
FLAT_ROWS_PER_GROUP = {
    "destructible": 8,
    "hulk": 4,
    "obstacle": 4,
    "human": 4,
}


def _build_flat_trunk_indices() -> np.ndarray:
    """Model-state indices the flat trunk consumes: globals + nearest-K rows."""
    idx = list(range(GLOBAL_FEATURES))
    for name, _, _ in TACTICAL_POOL_DEFS:
        lo, hi = TOKEN_GROUP_RANGES[name]
        k = min(int(FLAT_ROWS_PER_GROUP.get(name, 0)), hi - lo)
        for row in range(lo, lo + k):
            base = ENEMY_TOKEN_OFFSET + row * ENEMY_TOKEN_FEATURES
            idx.extend(range(base, base + ENEMY_TOKEN_FEATURES))
    return np.asarray(idx, dtype=np.int64)


FLAT_TRUNK_INDICES = _build_flat_trunk_indices()
FLAT_TRUNK_FRAME_FEATURES = int(FLAT_TRUNK_INDICES.shape[0])   # 40 + 20*18 = 400


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


def _state_bag_row(slot: np.ndarray, feat_per_slot: int) -> np.ndarray | None:
    """Convert one 10-wide Lua wire row into an 18-wide model token row.

    Applies the signal-fidelity fixes (all DQN-side; the WIRE is unchanged so
    v3/PPO and the raw-wire expert are unaffected):
      * dx/dy re-normalized to the isotropic diagonal so direction and distance
        agree with ``dist`` (``sqrt(dx^2+dy^2) == dist``) — P3.
      * vx/vy recovered from the wire's playfield-span normalization and
        rescaled by a realistic per-frame velocity scale (isotropic) — P1.
      * approach recomputed as the normalized radial closing speed
        ``-(v . unit_dir_to_player)`` in consistent units — P2.
      * the ordinal ``type_norm`` scalar expanded into a categorical one-hot — P5.

    Output row layout (``ENEMY_TOKEN_FEATURES`` wide)::

        [present, dx, dy, dist, vx, vy, threat, approach, ttc, type_onehot(9)]
    """
    if not np.isfinite(slot).all() or slot[0] <= 0.5:
        return None
    dx_w = _clip11(slot[1]) if feat_per_slot > 1 else 0.0
    dy_w = _clip11(slot[2]) if feat_per_slot > 2 else 0.0
    dist = _clip01(slot[3] if feat_per_slot > 3 else 1.0)
    vx_w = _clip11(slot[4]) if feat_per_slot > 4 else 0.0
    vy_w = _clip11(slot[5]) if feat_per_slot > 5 else 0.0
    threat = _clip01(slot[6] if feat_per_slot > 6 else 0.0)
    ttc = _clip01(slot[8] if feat_per_slot > 8 else 1.0)
    type_norm = _clip01(slot[9] if feat_per_slot > 9 else 0.0)

    # P3: isotropic position (consistent with dist and the 8-way action grid).
    dx = _clip11(dx_w * _WIRE_DX_TO_ISO)
    dy = _clip11(dy_w * _WIRE_DY_TO_ISO)
    # P1: high-resolution isotropic velocity.
    vx = _clip11(vx_w * _WIRE_VX_TO_VEL)
    vy = _clip11(vy_w * _WIRE_VY_TO_VEL)
    # P2: approach = normalized radial closing speed. dir = (dx, dy)/dist is a
    # true unit vector now that dx/dy are isotropic, so -(v . dir) is the closing
    # component; positive means the object is moving toward the player.
    approach = 0.0
    if dist > 1e-6:
        approach = _clip11(-(((vx * dx) + (vy * dy)) / dist))

    # P5: categorical one-hot type (drops the false ordinal type ramp).
    type_id = int(round(type_norm * (TYPE_CLASS_COUNT - 1)))
    type_id = min(TYPE_CLASS_COUNT - 1, max(0, type_id))

    row = np.zeros(ENEMY_TOKEN_FEATURES, dtype=np.float32)
    row[0] = 1.0
    row[1] = dx
    row[2] = dy
    row[3] = dist
    row[4] = vx
    row[5] = vy
    row[6] = threat
    row[7] = approach
    row[8] = ttc
    row[TYPE_ONEHOT_OFFSET + type_id] = 1.0
    return row


def decode_token_types(rows: np.ndarray) -> np.ndarray:
    """Return integer type ids from the one-hot block of model token rows.

    ``rows`` has shape ``(..., ENEMY_TOKEN_FEATURES)``; returns ``(...)`` int32
    ids. Empty/padding rows (all-zero one-hot) decode to 0 and are expected to be
    masked out by the caller via the ``present`` flag at column 0.
    """
    oh = np.asarray(rows)[..., TYPE_ONEHOT_OFFSET:TYPE_ONEHOT_OFFSET + TYPE_CLASS_COUNT]
    return np.argmax(oh, axis=-1).astype(np.int32)


def _build_pool_row_indices() -> np.ndarray:
    """Wire indices of every pool slot row, shape (112, 10), for one-shot gather."""
    idx = np.zeros((ENEMY_TOKEN_COUNT, WIRE_POOL_SLOT_FEATURES), dtype=np.int64)
    row = 0
    off = TACTICAL_POOL_OFFSET
    for _name, max_slots, feats in TACTICAL_POOL_DEFS:
        base = off + 1
        for s in range(max_slots):
            start = base + s * feats
            idx[row] = np.arange(start, start + feats, dtype=np.int64)
            row += 1
        off += 1 + max_slots * feats
    return idx


_POOL_ROW_INDICES = _build_pool_row_indices()
_POOL_ROW_MAX_INDEX = int(_POOL_ROW_INDICES.max())
_POOL_GROUP_IDS = np.repeat(
    np.arange(len(TACTICAL_POOL_DEFS), dtype=np.int64),
    [max_slots for _n, max_slots, _f in TACTICAL_POOL_DEFS],
)


def _extract_enemy_tokens(arr: np.ndarray) -> np.ndarray:
    """Return the 112-row grouped object state bag from Lua tactical pools.

    Fully vectorized single pass: gather all 112 wire slot rows at once, apply
    the same transforms as ``_state_bag_row`` (which remains the single-row
    reference implementation used by tests), zero inactive rows, then one
    stable lexsort (group id, distance) packs each group's active rows
    nearest-first with padding rows after them.
    """
    if arr.shape[0] <= _POOL_ROW_MAX_INDEX:
        return np.zeros(ENEMY_TOKEN_COUNT * ENEMY_TOKEN_FEATURES, dtype=np.float32)

    raw = arr[_POOL_ROW_INDICES]                                   # (112, 10)
    with np.errstate(invalid="ignore"):
        active = (raw[:, 0] > 0.5) & np.isfinite(raw).all(axis=1)

        dx = np.clip(np.clip(raw[:, 1], -1.0, 1.0) * _WIRE_DX_TO_ISO, -1.0, 1.0)
        dy = np.clip(np.clip(raw[:, 2], -1.0, 1.0) * _WIRE_DY_TO_ISO, -1.0, 1.0)
        dist = np.clip(raw[:, 3], 0.0, 1.0)
        vx = np.clip(np.clip(raw[:, 4], -1.0, 1.0) * _WIRE_VX_TO_VEL, -1.0, 1.0)
        vy = np.clip(np.clip(raw[:, 5], -1.0, 1.0) * _WIRE_VY_TO_VEL, -1.0, 1.0)
        threat = np.clip(raw[:, 6], 0.0, 1.0)
        ttc = np.clip(raw[:, 8], 0.0, 1.0)
        type_norm = np.clip(raw[:, 9], 0.0, 1.0)
        approach = np.where(
            dist > 1e-6,
            np.clip(-((vx * dx) + (vy * dy)) / np.maximum(dist, 1e-9), -1.0, 1.0),
            0.0,
        )
        type_id = np.clip(
            np.rint(np.nan_to_num(type_norm) * (TYPE_CLASS_COUNT - 1)).astype(np.int64),
            0, TYPE_CLASS_COUNT - 1,
        )

    rows = np.zeros((ENEMY_TOKEN_COUNT, ENEMY_TOKEN_FEATURES), dtype=np.float32)
    rows[:, 0] = 1.0
    rows[:, 1] = dx
    rows[:, 2] = dy
    rows[:, 3] = dist
    rows[:, 4] = vx
    rows[:, 5] = vy
    rows[:, 6] = threat
    rows[:, 7] = approach
    rows[:, 8] = ttc
    rows[np.arange(ENEMY_TOKEN_COUNT), TYPE_ONEHOT_OFFSET + type_id] = 1.0
    rows[~active] = 0.0

    # Stable sort: group blocks stay in place, active rows pack nearest-first,
    # zeroed padding rows sink to the end of their group.
    sort_key = np.where(active, np.nan_to_num(dist, nan=2.0), 2.0)
    order = np.argsort(sort_key + _POOL_GROUP_IDS * 4.0, kind="stable")
    return rows[order].reshape(-1)


def slice_model_state(wire) -> np.ndarray:
    """Extract the compact model input from a full wire vector.

    ``wire`` may be any sequence of length >= TACTICAL_POOL_OFFSET.  Returns a
    contiguous float32 array of length ``SINGLE_FRAME_STATE_SIZE`` laid out as
    ``[core(18), elist(22), grouped_objects(112 x 18)]``.

    The core scalars are rescaled DQN-side to match the object-row fixes:
      * player velocity (cols 7,8) is recovered from the wire's playfield-span
        normalization and rescaled by the realistic per-frame velocity scale so
        it is subtractable from object closing velocity — P4/P6.
      * nearest enemy/spawner dx/dy (cols 11,12,15,16) are made isotropic so the
        core direction features agree with the object rows and with distance — P3.
    The WIRE itself is never mutated (a copy is taken), so the raw-wire expert
    and v3/PPO paths are unaffected.
    """
    arr = np.asarray(wire, dtype=np.float32)
    global_state = np.array(arr[0:GLOBAL_FEATURES], dtype=np.float32, copy=True)
    if global_state.shape[0] >= 18:
        # P4/P6: player velocity to realistic isotropic per-frame scale.
        global_state[7] = _clip11(global_state[7] * _WIRE_VX_TO_VEL)
        global_state[8] = _clip11(global_state[8] * _WIRE_VY_TO_VEL)
        # P3: nearest enemy dx/dy and nearest spawner dx/dy to isotropic scale.
        global_state[11] = _clip11(global_state[11] * _WIRE_DX_TO_ISO)
        global_state[12] = _clip11(global_state[12] * _WIRE_DY_TO_ISO)
        global_state[15] = _clip11(global_state[15] * _WIRE_DX_TO_ISO)
        global_state[16] = _clip11(global_state[16] * _WIRE_DY_TO_ISO)
    enemies = _extract_enemy_tokens(arr)
    return np.concatenate([global_state, enemies]).astype(np.float32, copy=False)


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
    global_features: int = GLOBAL_FEATURES
    lane_count: int = 0
    lane_features: int = 0
    extra_features: int = 0
    enemy_token_count: int = ENEMY_TOKEN_COUNT
    enemy_token_features: int = ENEMY_TOKEN_FEATURES
    object_token_count: int = ENEMY_TOKEN_COUNT      # compatibility alias
    object_token_features: int = ENEMY_TOKEN_FEATURES

    # ── network architecture ────────────────────────────────────────────
    # Flat trunk input = globals(40) + nearest-K object rows per group
    # (8 destructible + 4 hulk + 4 obstacle + 4 human = 20 rows × 18 = 360).
    # Near rows are slot-stable under distance sorting, so dedicated first-layer
    # weights are justified there; the remaining 92 rows reach the trunk only
    # through the permutation-invariant object-attention digest below.
    flat_state_to_trunk: bool = True
    flat_trunk_frame_features: int = FLAT_TRUNK_FRAME_FEATURES
    trunk_layer_sizes: tuple[int, ...] = (1024, 768, 512)
    trunk_hidden: int = 384
    trunk_layers: int = 2
    use_layer_norm: bool = True
    dropout: float = 0.0

    # Lane inputs are intentionally removed for the object-list experiment.
    use_lane_attention: bool = False
    attn_heads: int = 8
    attn_dim: int = 128

    # Self-attention over the 112 grouped object rows. This does not replace the
    # flat state input; it adds a relational digest to the first trunk layer.
    # The digest is per-group masked mean-pools (destructible/hulk/obstacle/
    # human, 4 × dim) plus a global masked max-pool (1 × dim) so rare rows
    # (last human, closing projectile) are not averaged away by 64 grunt slots.
    use_object_attention: bool = True
    object_attn_heads: int = 8
    object_attn_dim: int = 128
    object_attn_group_pooling: bool = True

    # Action-conditioned attention for the DQN advantage heads. Direction queries
    # attend over enemy rows so each move/fire/joint action is scored with
    # object evidence relevant to that candidate action.
    use_action_context_attention: bool = True
    action_context_heads: int = 8
    joint_action_embed_dim: int = 32
    action_head_hidden: int = 192
    # Parameter-free geometric prior for action-context attention. Direction
    # queries still learn freely, but the attention logits start biased toward
    # objects aligned with the candidate fire lane / movement affordance instead
    # of having to rediscover that geometry from sparse score rewards alone.
    action_context_geometry_bias: bool = True
    action_context_geometry_bias_strength: float = 1.35

    # Main policy/value head.  Branch heads remain for auxiliary BC + metrics.
    use_joint_head: bool = True
    branch_aux_bc_weight: float = 0.25

    # Distributional C51.  The support MUST bracket the discounted n-step
    # RETURNS that actually occur, not the raw game score.  With gamma=0.995 and
    # score_reward_scale=0.001 the bootstrapped Q lands in roughly [-5, +20]
    # (see the Q-Range telemetry column).  The old [-200, 500] support gave
    # delta_z=(700/50)=14.0, so only ~2 of 51 atoms covered the operational
    # range and inter-action value gaps (~0.1-2 units) were smaller than one
    # atom — the categorical projection quantised the reward away and every
    # joint action collapsed to the same Q (argmax ≈ random).  Tighten the
    # support so delta_z≈1.2: now a single grunt (0.1) is ~8% of an atom and a
    # 1-2 unit action advantage spans a full atom, so the critic can finally
    # rank actions.  `support` is rebuilt from config on checkpoint load
    # (agent._load_compatible skips the saved buffer), so this is warm-loadable
    # with no layer-shape change.  Widen again only if Q genuinely exceeds ~40.
    use_distributional: bool = True
    num_atoms: int = 51
    v_min: float = -10.0
    v_max: float = 50.0
    # C51 target smoothing: this fraction of uniform-over-atoms mass is mixed
    # into every projected Bellman target, bounding the minimum achievable
    # cross-entropy away from zero (~0.095 at 0.01).  Prevents the critic's
    # distributions collapsing to deltas and the TD gradient starving to
    # nothing (the 415K→210K sag of 2026-07-19).  0 disables.
    c51_target_smoothing: float = 0.01

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
    # Warm restarts OFF: the restart at step 1,005,000 doubled the LR on a
    # converged policy and collapsed a 120K-score run to 30K — the 10M sliding
    # replay buffer forgot the peak-era trajectories long before the new cosine
    # re-annealed, leaving nothing to recover from. Cosine-to-floor, then flat.
    lr_use_restarts: bool = False
    gamma: float = 0.995
    n_step: int = 16
    # Replay-pressure cap: steps/s <= max_samples_per_frame * FPS / batch_size.
    # This is the binding constraint on steps/s, NOT GPU speed — the v18 model
    # is ~30% cheaper per step, so convert that headroom into more gradient
    # steps per unit of experience (20 -> 32 ≈ FPS/32 steps/s).
    max_samples_per_frame: float = 32

    # Replay (PER with proportional priorities).  The grouped-object representation is
    # wider than the old compact lane slice: state/next_state alone cost about
    # 80 GB at 10M transitions with the default 1-frame stack.
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
    # scoring bursts, wave transitions, close danger, target-rich enemy rows,
    # human opportunities, and terminal/pre-death cues.
    interesting_replay_fraction: float = 0.18
    interesting_replay_min_score: float = 0.50
    max_interesting_replay_fraction: float = 0.30
    interesting_replay_over_cap_min_score: float = 0.95
    legacy_interest_positive_reward: float = 0.75
    interesting_replay_bank_size: int = 1_000_000

    # Recent replay quota: keep the learner responsive to the behavior it is
    # currently generating instead of letting a 10M buffer dilute new outcomes.
    recent_replay_fraction: float = 0.35
    recent_replay_window: int = 1_000_000

    # ── hall-of-fame replay (permanent retention) ───────────────────────
    # The structural cure for the recurring peak->collapse cycle (2026-07
    # forensics): every other preservation device lives inside the 10M ring
    # (~42-minute eviction horizon), priority boosts are erased at first
    # sample, and PER beta pins to 1.0 early — so once peak-era data ages
    # out, NOTHING can generate a gradient pointing back toward peak play.
    # The hall of fame COPIES the best episodes ever seen (absolute ratchet
    # admission, min-heap replacement, never time-evicted) into a separate
    # store and guarantees them a small slice of every batch, keeping peak
    # states' Bellman targets grounded forever.  Survives buffer clear() and
    # collapse-recovery wipes by design; persists in its own directory.
    hof_enabled: bool = True
    hof_max_episodes: int = 192
    hof_episode_stride: int = 1536         # transitions kept per episode (tail)
    hof_min_game_score: int = 50_000       # absolute admission floor
    hof_replay_fraction: float = 0.10      # guaranteed batch quota once seeded
    hof_min_transitions: int = 4_096       # quota activates only past this

    # Target network (periodic hard sync)
    target_update_period: int = 1_000

    # ── collapse watchdog ───────────────────────────────────────────────
    # Terminal-collapse signature measured 2026-07-12 after the unattended
    # week: loss pinned ~0.0015 with Q-range pegged at the C51 support
    # ceiling ([-10, 49.4] vs v_max=50) — perfect self-consistency, zero
    # grounding (healthy: loss 0.15-0.25, Q upper 10-15).  The C51 edge clamp
    # makes runaway optimism a stable ZERO-LOSS fixed point, so divergence is
    # silent; both signals together are unambiguous.  When sustained, restore
    # the best-EScr1M checkpoint and wipe the poisoned replay buffer.
    collapse_watchdog_enabled: bool = True
    collapse_loss_threshold: float = 0.02      # ~10x below healthy loss
    collapse_q_upper_frac: float = 0.90        # of v_max
    # Sag signature (added after the 415K→210K gradient-starvation decline):
    # loss below the healthy band while the eval score sits far below the
    # recorded best, with Q NOWHERE near the ceiling — the variant the
    # terminal signature deliberately does not catch.  The loss threshold
    # sits above the c51_target_smoothing floor (~0.095) so the detector
    # stays armed after smoothing raises the loss floor.
    collapse_sag_loss_threshold: float = 0.12
    collapse_sag_escr1m_frac: float = 0.75     # of best_escr1m on record
    # Signature B2 (score-only): the wave-1 fresh run regressed 305K -> 65K at
    # HEALTHY loss 0.39-0.41 — unreachable by B1's loss conjunct.  A deep,
    # sustained score collapse is actionable regardless of what loss reads:
    # best.pt is the only true external memory of peak play, and this is its
    # trigger.  Same sustain/cooldown/max-restore guards as A and B1.
    collapse_score_only_frac: float = 0.50     # of best_escr1m, no loss conjunct
    collapse_check_interval_s: float = 60.0
    collapse_sustain_checks: int = 10          # consecutive minutes required
    collapse_cooldown_s: float = 21_600.0      # 6h between restores
    collapse_max_restores: int = 2             # then halt training, serve frozen best
    target_tau: float = 1.0

    # ── policy ratchet (2026-07-15) ─────────────────────────────────────
    # Monotonic policy improvement for a learner whose gradient reliably
    # DEGRADES a good policy (measured six ways on 2026-07-14: the untouched
    # 415K checkpoint evals at 215-270K; ANY training config tried — including
    # this exact code — drives it to ~39-75K within ~13k steps).  Instead of
    # trusting the gradient, gate it: train a candidate window, FREEZE, measure
    # mean game score under an all-greedy protocol, and keep the weights only
    # if they beat the incumbent by the margin; otherwise restore the incumbent
    # (weights+target+optimizer+scaler) and try a different window (reseeded,
    # adaptively shrunk).  By construction the served policy cannot get worse;
    # "training destroys the agent" becomes a low accept rate instead of a
    # collapse.  Epoch 0 measures the loaded checkpoint itself — the same
    # protocol as the DQN_EVAL_ONLY control — so the first incumbent score is
    # trustworthy.  Enable with DQN_RATCHET=1 (or this flag).  While active,
    # the collapse watchdog and the legacy rolling-window best-save are
    # suspended: the ratchet subsumes both (its incumbent IS the best-known
    # policy, measured, not inferred from a rolling window).
    ratchet_enabled: bool = False
    ratchet_train_steps: int = 2_000        # candidate window (gradient steps)
    ratchet_min_train_steps: int = 250      # adaptive-shrink floor
    ratchet_eval_episodes: int = 40         # target cohort size (games)
    # Cohort sampling (review fix): "first K completions" censors the LONGEST
    # games — which are the highest-scoring — biasing the mean down, and MORE
    # for better candidates.  Instead the cohort is fixed at the START side:
    # every game that BEGINS within this window after the freeze is in, and
    # the measurement waits for ALL of them to finish.  No completion-time
    # selection; identical design every epoch.
    # 240 -> 600 (2026-07-15): in FINAL-GAME units a 450K-class game runs 4-8
    # minutes, so a 240s start-window yielded n=17 games and SE ~69K — the
    # accept gate degenerated to "beat the incumbent by ~100K".  600s yields
    # n≈40-50.  Heavy-tailed finals (SD ~285K) make n the whole ballgame.
    ratchet_eval_cohort_s: float = 600.0
    ratchet_eval_timeout_s: float = 2_100.0 # window + longest-game tail
    ratchet_eval_max_extends: int = 3       # then abort the epoch (fleet dead?)
    # Incumbent measurements (epoch 0 and bar re-measures) use a longer window:
    # the incumbent's SE enters EVERY future gate via sqrt(se_c^2+se_i^2), so
    # precision here is amortized across all epochs.
    ratchet_incumbent_cohort_mult: float = 2.0
    ratchet_accept_margin: float = 0.01     # candidate must beat incumbent by 1%
    # Noise-aware gate: Robotron game scores are heavy-tailed (SD ~140K on a
    # ~230K mean), so at K=30 the SE of the mean is ~26K — a bare 1% margin
    # (~2.3K) would accept measurement luck ~40% of the time and the ratchet
    # would advance on noise (winner's curse: the bar inflates, the weights
    # don't improve).  The candidate must clear the margin bar by this many
    # standard errors of ITS OWN sample mean.  1.0 ≈ 84% one-sided confidence;
    # 0 disables (bare margin).
    # 1.0 -> 0.5 (2026-07-15): with the reject-streak re-measure in place, a
    # noise-accept is SELF-CORRECTING — the inflated bar gets reset within
    # ~ratchet_remeasure_after_rejects epochs, and the falsely-accepted policy
    # is statistically ≈ the incumbent (bounded harm).  The optimal operating
    # point therefore shifts toward accepting more and letting the re-measure
    # audit: monotonicity in expectation, far higher climb rate on heavy-tailed
    # scores where a strict gate starves on sampling noise.
    ratchet_accept_z: float = 0.5
    ratchet_reseed_on_reject: bool = True   # new RNG stream per retry
    # Data floor (2026-07-15, measured): epoch-1 trained 2,000 steps x 1,024
    # batch = 2.05M gradient samples against a ring that held 33K->180K
    # transitions — every row hammered ~20x (worse early, worse under PER),
    # covering ~2 hours of wave-1..12 play vs the 401M frames the checkpoint
    # encodes.  The net re-carves itself to fit the sliver and bulldozes the
    # rest through the shared trunk: candidate measured 70K (median 29K) vs
    # incumbent 211K, Q-max crushed to ~0-4 within one window.  The original
    # 415K run NEVER trained against a thin ring (continuous training beside
    # a full 10M buffer, replay ratio ~3-6) — every demolition this week was
    # a resume-onto-thin-ring.  So: no candidate window may train until the
    # ring holds this many transitions of incumbent play.  One-time cost
    # (~5-10 min); the ring is never wiped on reject and, under the behavior
    # lock, only ever accumulates incumbent-quality data.
    ratchet_min_ring_transitions: int = 1_000_000
    # Fresh-optimizer protocol (2026-07-15, next single-variable probe).  The
    # 1M-ring run refuted data density as the primary killer: epoch-1 trained
    # at equilibrium-healthy Rpl/F 3-8 and was still demolished (205K -> 88K,
    # EpLen RISING while score fell — the passive-survival attractor forming
    # within one window).  Remaining mechanical suspect: the checkpoint's Adam
    # second moments are in equilibrium with a mature 10M ring's gradients;
    # on resume every row is fresh (PER max priority, larger TD errors) and
    # Adam divides the larger gradients by the stale too-small v-hat ->
    # oversized parameter steps until v-hat re-adapts.  beta2=0.999 puts that
    # adaptation at ~1,000-2,000 steps — exactly the window size that does the
    # damage, independent of ring size.  With this on, every candidate window
    # starts with ZEROED optimizer state and a linear LR warmup over the first
    # ratchet_window_warmup_steps, so early steps cannot be mis-scaled.  If
    # candidates are STILL demolished under this protocol, the objective's
    # local landscape is the confirmed cause (nothing mechanical remains).
    ratchet_fresh_optimizer: bool = True
    ratchet_window_warmup_steps: int = 200
    # Per-GAME measurement (2026-07-15).  frame.done fires per LIFE
    # (main.lua: previous_alive==1 and alive==0), so cohort samples were
    # running-scores-at-life-end: ~60-70% of true final-game scores, n
    # inflated ~20x with correlated samples (SE overconfident), and pre-freeze
    # stratified games leaked their post-freeze lives into every measurement.
    # The ratchet now samples FINAL GAME SCORES: a game boundary is detected
    # when game_score RESETS (it is non-decreasing within a Robotron game),
    # cohort membership is stamped per game start, and one sample = one
    # game's final total.  Guards: a client whose score hasn't advanced for
    # this long while frozen has wedged (attract mode / stuck reconnect) —
    # its cohort game is voided so the epoch can complete; greedy play scores
    # every few seconds, so 120s of silence is unambiguous.
    ratchet_stuck_void_s: float = 120.0
    # Junk-score refusal for game finals (transient-RAM BCD reads during
    # resets have produced absurd values before): finals above this are
    # discarded as garbage, the game voided.
    ratchet_max_credible_final: float = 2_000_000.0
    # Throughput + bar hygiene (2026-07-15):
    # After this many consecutive rejects, re-measure the INCUMBENT itself and
    # reset the bar to the fresh measurement.  An accept that was partly
    # sampling luck inflates the bar above the incumbent's true play (winner's
    # curse) and every honest candidate then loses to a ghost — observed as a
    # wall of rejects clustered 15-25% below a freshly-raised bar.  Weights
    # never change on a re-measure; only the number candidates must beat.
    ratchet_remeasure_after_rejects: int = 6
    # Train the NEXT candidate (from the incumbent) on the training GPU while
    # the fleet is busy measuring the CURRENT one — eval wall-time dominates
    # an epoch ~5:1 and the GPU idles through it.  On reject, the pre-trained
    # candidate enters measurement immediately; epochs collapse to eval-time.
    # The behavior lock keeps the fleet on the measured candidate throughout
    # (periodic syncs are suppressed; only transition force-syncs move nets).
    ratchet_pipeline: bool = True

    # Gradient
    grad_clip_norm: float = 5.0

    # ── exploration ─────────────────────────────────────────────────────
    epsilon_start: float = 1.0
    epsilon_end: float = 0.05
    epsilon_decay_frames: int = 2_500_000
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
    # Keep a SMALL permanent expert floor instead of decaying to zero.  Decaying
    # every imitation signal to exactly 0 is what turned a weak critic into a
    # crater: the replay (10M) is far smaller than the number of frames the
    # expert was active for (~29M), so all expert transitions get recycled out —
    # once the ratio reaches 0 there is literally no expert experience left to
    # learn from and nothing anchoring expert-level play.
    #
    # Floor lowered 5% → 1% (2026-07): three A/B trials at high skill levels
    # settled the value.  0% produced the buffer-drain sag every time it was
    # tried (EScr1M -16% at 383M frames, 415K→210K at 402M, and again on the
    # post-restore refill at 405M — decline tracks buffer expert content
    # falling below ~1%).  1% produced the 415K all-time record.  5% pays the
    # deep-wave takeover tax (~6 bot-controlled frames per episode, and the
    # scripted bot is suicidal at wave 15+) without adding measurable anchor
    # value over 1%.  A config-level floor also survives restarts, unlike the
    # keyboard override, which reset to the old 5% floor on every boot and
    # repeatedly landed the run on unvalidated settings.
    expert_ratio_end: float = 0.01
    # Decay is keyed to TRAINING STEPS, not frames.  At 20k+ fps the steady-state
    # frame:step ratio is ~200:1, so a frame-based 2M schedule completed in ~10k
    # gradient steps (2-3 wall-clock minutes) — the policy never had time to learn
    # before the expert handed off.  Steps are FPS-independent and track learning.
    # Stretched from 125k so the (now correctly-scaled) critic has time to learn
    # to reproduce the expert before the crutch eases off to the floor.
    expert_ratio_decay_start_step: int = 0
    expert_ratio_decay_steps: int = 300_000
    expert_ratio: float = 0.60

    # Expert BC — also step-based (same FPS-independence rationale as above).
    # This trains auxiliary bc_* heads and shared trunk features.  The acting
    # policy below is trained by the direct Q-policy + margin losses, then all
    # imitation anchors decay away so DQN can exceed the demonstrator.
    expert_bc_weight: float = 1.0
    expert_bc_decay_start_step: int = 0
    expert_bc_decay_steps: int = 300_000
    expert_bc_min_weight: float = 0.05
    # Directly distill demonstrations into the deployed joint Q policy. Cross
    # entropy treats Q(s, a) / temperature as action logits, giving the acting
    # head a real expert-like launch instead of leaving imitation in side heads.
    expert_q_policy_weight: float = 0.35
    expert_q_policy_temperature: float = 10.0
    expert_q_policy_decay_start_step: int = 0
    expert_q_policy_decay_steps: int = 300_000
    expert_q_policy_min_weight: float = 0.05
    # Q-margin also imitates directly into the acting joint head by constraining
    # Q(expert_action) >= Q(other) + margin on expert-visited states.  Left on
    # permanently it is a hard ceiling, so decay it on the same step schedule.
    expert_q_margin_weight: float = 0.05
    expert_q_margin: float = 0.50
    expert_q_margin_decay_start_step: int = 0
    expert_q_margin_decay_steps: int = 300_000
    expert_q_margin_min_weight: float = 0.0

    # ── reward ──────────────────────────────────────────────────────────
    # Score reward is based on actual game_score delta, not Lua objreward. A
    # 1,000-point event maps to 1.0 reward and a 5,000-point rescue maps to 5.0,
    # comfortably below score_reward_clip so it remains rank-ordered.
    score_reward_scale: float = 0.001
    point_reward_scale: float = 1.0 / score_reward_scale  # Derived: 1000.0
    score_reward_clip: float = 25.0
    # Score-only experiment: ignore all Lua subjective shaping and explicit
    # death reward.  Death is bad only because it ends future point collection.
    subj_reward_scale: float = 0.0
    subj_positive_weight: float = 0.0
    subj_positive_decay_start_step: int = 0
    subj_positive_decay_steps: int = 125_000
    subj_positive_min_weight: float = 0.0
    shaping_reward_clip: float = 4.0
    death_penalty: float = 10.0
    reward_clip: float = 30.0
    death_reward_clip: float = 40.0

    # Non-harvestable shaping. These are either event based (wave clear,
    # no-human no-score stall) or potential-based state differences
    # gamma*Phi(s') - Phi(s). They densify movement credit without paying the
    # policy just for occupying a state.
    # 1.0 -> 2.5 + positive TRAINING TERMINAL (2026-07-15, ported from expert2
    # as the first reward-surgery candidate generator under the ratchet).  The
    # value surface's only external grounding is death at v_min=-10; a wave
    # clear now closes the n-step episode for replay purposes (the live game
    # continues), so Tz = r at the clear — bootstrap-free POSITIVE ground
    # truth.  2.5 = 2,500 points-equivalent: meaningful, but smaller than one
    # max-chain rescue (5,000) so it cannot out-bid rescuing humans (a rush
    # incentive would fight the game's biggest income source).  Delivered
    # OUTSIDE the shaping clip.  The ratchet's gate metric is final GAME SCORE
    # — invariant to reward changes — so candidates trained under this reward
    # are directly comparable to the incumbent's existing bar.
    wave_clear_training_terminal: bool = True
    wave_clear_bonus: float = 2.5
    wave_progress_bonus: float = 0.15
    potential_human_scale: float = 0.45
    potential_human_sharpness: float = 2.0
    potential_danger_scale: float = 0.65
    potential_danger_sharpness: float = 2.0
    potential_corner_scale: float = 0.35
    potential_corner_band: float = 0.16
    no_human_stall_grace_frames: int = 90
    no_human_stall_penalty_per_frame: float = 0.015
    no_human_stall_max_penalty: float = 0.08

    # Legacy hard-start tuning retained for old checkpoints/config snapshots.
    hard_start_min_level: int = 5
    hard_start_wave_spread: int = 8

    # Episode-level elite replay: preserve tails from rare/high-performing
    # episodes, not only individual interesting transitions.
    elite_episode_score_threshold: int = 80_000
    elite_episode_level_threshold: int = 6
    elite_episode_tail_len: int = 256
    elite_episode_priority_boost: float = 3.0
    elite_episode_interest_score: float = 1.0
    # Separate protection for self-discovered learner episodes.  The regular elite
    # path catches very high absolute scores, but mostly-DQN episodes that are only
    # "good for now" can otherwise be washed out by the 10M buffer before their
    # Bellman targets shape the policy.
    learner_elite_score_threshold: int = 60_000
    learner_elite_level_threshold: int = 6
    learner_elite_min_learner_fraction: float = 0.90
    learner_elite_tail_len: int = 512
    learner_elite_priority_boost: float = 4.0
    learner_elite_interest_score: float = 1.0
    # Adaptive elite gate: the static thresholds above are FLOORS.  Once the
    # agent's typical play passes them (average level crossed 6 at ~200M
    # frames), a fixed threshold matches half of all episodes and the elite
    # boost stops being selective.  The effective threshold is
    # max(static, rolling percentile of recent episode scores/levels), so
    # "elite" always means "top ~10% of recent play" no matter how good the
    # agent gets.  Window is in episodes; adaptive gating engages only after
    # min_episodes have been observed.
    elite_adaptive_window: int = 200
    elite_adaptive_min_episodes: int = 20
    elite_adaptive_percentile: float = 90.0
    learner_elite_adaptive_percentile: float = 80.0
    # Ratchet the adaptive thresholds (2026-07): the rolling percentile
    # re-anchors to ~35s of current play, so during a decline it certifies
    # the top decile of MEDIOCRE play as elite.  With the ratchet, thresholds
    # never fall more than the slack below their within-run high-water mark —
    # "elite" keeps meaning "good vs the best this run has shown", not "good
    # vs the last 35 seconds".
    elite_threshold_ratchet: bool = True
    elite_ratchet_score_slack: float = 0.85   # usable floor = 0.85 * hwm score
    elite_ratchet_level_slack: float = 1.0    # usable floor = hwm level - 1

    # ── fire cadence ────────────────────────────────────────────────────
    # Hold each fire direction stable for this many frames.  Set to 1 for the
    # no-hold experiment: expert/DQN can choose a fresh fire direction every
    # frame, and replay stores that per-frame choice.
    fire_hold_frames: int = 1

    # ── death attribution ───────────────────────────────────────────────
    # NOTE: pre-death upsampling is deliberately kept BELOW the positive
    # counterweight (elite_episode_priority_boost=3.0, learner_elite=4.0) so a
    # batch is never negative-target dominated.  Over-boosting pre-death frames
    # while expert anchoring is weak drives distributional value collapse (the
    # Q-Range slides toward v_min=-10).  See repo memory on the 0%-expert run.
    death_priority_boost: float = 3.0
    pre_death_lookback: int = 150
    pre_death_priority_boost: float = 2.0
    pre_death_reward_lookback: int = 90
    # Pre-death reward repaint DISABLED (2026-07 forensics): this in-place
    # rewrite of the last ~90 stored returns before EVERY death was verified
    # to be the primary directional eraser of peak play — danger-scaled it
    # taxes deep-wave deaths ~40:1 vs shallow (~-8..-12.5 units per deep death
    # against +6..9 units of TOTAL episode score income), it double-counts the
    # -10 death penalty that n_step=16 already propagates at >=92.8% strength,
    # and it is applied AFTER episode metrics are recorded, so no dashboard
    # ever showed it.  The effective (trained-on) reward landscape had a local
    # optimum at passive survival that the visible landscape did not — the
    # recurring 300-415K -> 60-75K collapse landed there every time.  Both
    # zeros make apply_pre_death_penalty a no-op via its guard.
    pre_death_base_penalty: float = 0.0
    pre_death_danger_penalty: float = 0.0
    pre_death_max_penalty: float = 0.35
    pre_death_min_danger: float = 0.15
    pre_death_penalize_expert: bool = False

    # ── inference ───────────────────────────────────────────────────────
    use_separate_inference_model: bool = True
    # torch.compile (inductor): the forward pass is DISPATCH-bound, not
    # FLOP-bound — hundreds of small kernels per call for a 3.6M-param net.
    # Measured: inference batch~29 7.4 -> 1.4 ms (dynamic shapes); train
    # fwd+bwd batch=1024 35 -> 27 ms fp32 / 18 ms AMP.  Real speedup — but on
    # the free-threaded 3.14t build dynamo has produced four distinct failure
    # modes here (cross-thread FX race, 1024-recompile storm, SpeculationLog
    # divergence, boot-time compile storms tanking FPS to ~200), because any
    # runtime guard failure recompiles on one thread while another invokes a
    # dynamo-optimized callable.  Default OFF for unattended stability; opt
    # back in with DQN_TORCH_COMPILE=1 (revisit after a PyTorch upgrade).
    use_torch_compile: bool = os.getenv("DQN_TORCH_COMPILE", "0").strip().lower() not in ("0", "false", "no", "off")
    inference_on_cpu: bool = False         # agent falls back to CPU if no CUDA
    train_cuda_device_index: int = 0
    inference_cuda_device_index: int = 1
    # 5 -> 50 (2026-07-15): PERF FIX cherry-picked onto the 415K-era code, NOT a
    # learning change.  Every sync now forces a GPU queue drain (see the event
    # fix in agent._sync_inference); at every-5-steps that drain fires 10x more
    # often than needed.  The inference net only has to track the online net
    # closely enough to act, and 50 steps of drift is negligible against the
    # ~100ms stalls the old cadence produced.
    inference_sync_steps: int = 50
    inference_batching_enabled: bool = True
    inference_batch_max_size: int = 128
    inference_batch_wait_ms: float = 1.0
    # How long a handler waits for the batcher before solo-inferring.  Was a
    # hardcoded 50ms — short enough that one boot-time stall tipped all 32
    # handlers into permanent solo fallback (each timed-out request was ALSO
    # still batched: double inference, self-sustaining ~104ms stampede,
    # 2026-07-13).  Waiting out a transient stall in the batched path is
    # nearly always cheaper than defecting to a solo-call convoy.
    inference_request_timeout_ms: float = 250.0
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
# arbitrary wave for curriculum training.
ROBOTRON_SELECTABLE_LEVELS = list(range(1, 41))

# Stratified training starts (2026-07): with uniform wave-1 starts, deep-wave
# data exists in the buffer ONLY while the policy is good enough to reach it —
# any dip evicts the data that maintained depth within one buffer turnover,
# with a regeneration floor of zero (the curriculum lock-in that made the
# wave-1 run's peak strictly less stable than the start-11 run's).  Stratified
# per-client start waves guarantee deep-wave experience regardless of policy
# quality.  Applies to TRAINING clients only when the operator has not set
# start_advanced/auto_curriculum in game settings (operator settings win);
# eval clients remain hard-pinned to wave 1 so EScr1M stays comparable.
STRATIFIED_TRAINING_STARTS = True
STRATIFIED_START_LEVELS = (1, 5, 9, 13)

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
SCORE_1M_WINDOW_FRAMES = 1_000_000
LEVEL_1M_WINDOW_FRAMES = 1_000_000
EVAL_SCORE_1M_WINDOW_FRAMES = 1_000_000


def _new_metric_ring(size: int) -> np.ndarray:
    return np.zeros(max(1, int(size)), dtype=np.float64)


@dataclass
class MetricsData:
    frame_count: int = 0
    learner_frame_count: int = 0
    total_controls: int = 0
    total_training_steps: int = 0
    memory_buffer_size: int = 0
    client_count: int = 0
    web_client_count: int = 0

    preview_capture_enabled: bool = True
    hud_enabled: bool = False
    game_preview_seq: int = 0
    game_preview_client_id: int = -1
    game_preview_width: int = 0
    game_preview_height: int = 0
    game_preview_format: str = ""
    game_preview_data: bytes = b""
    game_preview_updated_ts: float = 0.0
    game_preview_source_format: str = ""
    game_preview_encoded_bytes: int = 0
    game_preview_raw_bytes: int = 0
    game_preview_compression_ratio: float = 1.0
    game_preview_fps: float = 0.0

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
    level_sum_interval: float = 0.0
    level_count_interval: int = 0

    total_inference_time: float = 0.0
    total_inference_requests: int = 0

    last_grad_norm: float = 0.0
    last_loss: float = 0.0
    last_q_mean: float = 0.0
    last_bc_loss: float = 0.0
    last_bc_weight: float = 0.0
    last_subj_positive_weight: float = 1.0
    last_sample_dqn_frac: float = 0.0
    last_sample_epsilon_frac: float = 0.0
    last_sample_expert_frac: float = 0.0
    last_inference_sync_age: int = 0
    last_priority_mean: float = 0.0
    last_agreement: float = 0.0
    last_train_sample_ms: float = 0.0
    last_train_transfer_ms: float = 0.0
    last_train_compute_ms: float = 0.0
    last_train_priority_ms: float = 0.0
    last_train_step_ms: float = 0.0

    average_level: float = 0.0
    average_game_score: float = 0.0
    score_1m_window: int = SCORE_1M_WINDOW_FRAMES
    score_1m_values: np.ndarray = field(default_factory=lambda: _new_metric_ring(SCORE_1M_WINDOW_FRAMES))
    score_1m_pos: int = 0
    score_1m_count: int = 0
    score_1m_sum: float = 0.0
    score_1m_average: float = 0.0
    level_1m_window: int = LEVEL_1M_WINDOW_FRAMES
    level_1m_values: np.ndarray = field(default_factory=lambda: _new_metric_ring(LEVEL_1M_WINDOW_FRAMES))
    level_1m_pos: int = 0
    level_1m_count: int = 0
    level_1m_sum: float = 0.0
    level_1m_average: float = 0.0
    eval_average_reward: float = 0.0
    eval_average_score: float = 0.0
    eval_average_level: float = 0.0
    eval_average_length: float = 0.0
    eval_episode_count: int = 0
    eval_score_1m_window: int = EVAL_SCORE_1M_WINDOW_FRAMES
    # Entries are (score, level, ep_frames); score and level share one window
    # so EScr1M and ELvl1M always describe the same set of eval episodes.
    eval_score_1m_entries: Deque[tuple[float, float, int]] = field(default_factory=deque)
    eval_score_1m_frames: int = 0
    eval_score_1m_sum: float = 0.0
    eval_score_1m_average: float = 0.0
    eval_score_1m_count: int = 0
    eval_level_1m_sum: float = 0.0
    eval_level_1m_average: float = 0.0
    peak_level: int = 0
    # Policy-ratchet measurement accumulator.  epoch == -1 means "not
    # collecting" (zero overhead outside a ratchet eval phase); when >= 0,
    # every completed game's score — eval AND training clients, since the
    # ratchet forces the whole fleet greedy during measurement — is appended,
    # PROVIDED the game STARTED after collect_t0.  A 215-270K game runs
    # 2.5-3.5 minutes, so games in flight at the freeze finish long after any
    # reasonable warmup — start-time tagging is the only exact way to exclude
    # mixed-policy games from the sample.
    ratchet_eval_epoch: int = -1
    ratchet_eval_collect_t0: float = 0.0
    ratchet_eval_cohort_close_ts: float = 0.0   # games starting after this are NOT in the cohort
    ratchet_eval_cohort_started: int = 0        # games started inside the cohort window
    ratchet_eval_scores: list = field(default_factory=list)
    # THE freeze flag (review fix): consulted directly by get_effective_epsilon,
    # _effective_expert_ratio_locked, the replay-store/boost gates, and the
    # start-wave packer.  The ratchet used to impersonate operator settings
    # (game_settings.epsilon_pct/expert_pct), which the web dashboard could
    # overwrite mid-measurement and persist to disk; a dedicated flag cannot
    # be touched by any operator surface.
    ratchet_frozen: bool = False
    peak_episode_reward: float = 0.0
    peak_game_score: int = 0
    replay_dropped_steps: int = 0
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

    def _push_score_1m_locked(self, value: float):
        window = max(1, int(self.score_1m_window))
        if self.score_1m_values.shape[0] != window:
            self.score_1m_values = _new_metric_ring(window)
            self.score_1m_pos = 0
            self.score_1m_count = 0
            self.score_1m_sum = 0.0
            self.score_1m_average = 0.0
        pos = int(self.score_1m_pos) % window
        v = float(value)
        if self.score_1m_count < window:
            self.score_1m_values[pos] = v
            self.score_1m_sum += v
            self.score_1m_count += 1
        else:
            old = float(self.score_1m_values[pos])
            self.score_1m_values[pos] = v
            self.score_1m_sum += v - old
        self.score_1m_pos = (pos + 1) % window
        self.score_1m_average = self.score_1m_sum / max(1, self.score_1m_count)

    def _push_level_1m_locked(self, value: float):
        window = max(1, int(self.level_1m_window))
        if self.level_1m_values.shape[0] != window:
            self.level_1m_values = _new_metric_ring(window)
            self.level_1m_pos = 0
            self.level_1m_count = 0
            self.level_1m_sum = 0.0
            self.level_1m_average = 0.0
        pos = int(self.level_1m_pos) % window
        v = float(value)
        if self.level_1m_count < window:
            self.level_1m_values[pos] = v
            self.level_1m_sum += v
            self.level_1m_count += 1
        else:
            old = float(self.level_1m_values[pos])
            self.level_1m_values[pos] = v
            self.level_1m_sum += v - old
        self.level_1m_pos = (pos + 1) % window
        self.level_1m_average = self.level_1m_sum / max(1, self.level_1m_count)

    def note_game_score(self, score: int, level: int | float | None = None):
        """Thread-safe peak score plus rolling 1M-frame score/level metrics."""
        with self.lock:
            if score > self.peak_game_score:
                self.peak_game_score = int(score)
            self._push_score_1m_locked(float(score))
            if level is not None and int(score) > 0:
                self._push_level_1m_locked(float(level))

    def note_game_state_averages(self, average_level: float, average_game_score: float, peak_level: int | None = None):
        """Thread-safe live game-state aggregate update."""
        with self.lock:
            self.average_level = float(average_level)
            self.average_game_score = float(average_game_score)
            if peak_level is not None and int(peak_level) > self.peak_level:
                self.peak_level = int(peak_level)

    def _push_eval_score_1m_locked(self, score: float, level: float, length: int):
        window = max(1, int(self.eval_score_1m_window))
        ep_frames = max(1, int(length))
        self.eval_score_1m_entries.append((float(score), float(level), ep_frames))
        self.eval_score_1m_frames += ep_frames
        self.eval_score_1m_sum += float(score)
        self.eval_level_1m_sum += float(level)
        while len(self.eval_score_1m_entries) > 1 and self.eval_score_1m_frames > window:
            old_score, old_level, old_frames = self.eval_score_1m_entries.popleft()
            self.eval_score_1m_frames -= int(old_frames)
            self.eval_score_1m_sum -= float(old_score)
            self.eval_level_1m_sum -= float(old_level)
        self.eval_score_1m_count = len(self.eval_score_1m_entries)
        self.eval_score_1m_average = (
            self.eval_score_1m_sum / max(1, self.eval_score_1m_count)
        )
        self.eval_level_1m_average = (
            self.eval_level_1m_sum / max(1, self.eval_score_1m_count)
        )

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
            if self.ratchet_frozen:
                return 0.0          # measurement protocol: pure greedy
            ep = game_settings.epsilon_pct
            if ep >= 0:
                return ep / 100.0
            return 0.0 if self.override_epsilon else float(self.epsilon)

    @staticmethod
    def _natural_epsilon_for_learner_frame(learner_frame_count: int) -> float:
        progress = min(1.0, learner_frame_count / max(1, RL_CONFIG.epsilon_decay_frames))
        return RL_CONFIG.epsilon_start + progress * (RL_CONFIG.epsilon_end - RL_CONFIG.epsilon_start)

    def _effective_expert_ratio_locked(self) -> float:
        if self.ratchet_frozen:
            return 0.0              # measurement protocol: no bot frames
        xp = game_settings.expert_pct
        if xp >= 0:
            return xp / 100.0
        return float(self.expert_ratio)

    def update_epsilon(self, frames_advanced: int = 1):
        with self.lock:
            if self.manual_epsilon_override:
                return self.epsilon
            base = self._natural_epsilon_for_learner_frame(int(self.learner_frame_count))
            # While the expert still drives a meaningful share of frames, hold a
            # minimum exploration floor so the learner keeps probing its own
            # action space instead of collapsing to greedy before handoff.
            floor_until = float(getattr(RL_CONFIG, "epsilon_expert_floor_until_ratio", 0.0))
            if floor_until > 0.0 and self._effective_expert_ratio_locked() > floor_until:
                base = max(base, float(getattr(RL_CONFIG, "epsilon_expert_floor", 0.0)))
            if self.manual_pulse_active:
                self.manual_pulse_frames_remaining -= max(1, int(frames_advanced))
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
            return self._effective_expert_ratio_locked()

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

    def ratchet_note_eval_start(self, ep_started_at: float):
        """A new game began; count it into the measurement cohort if the
        freeze is on and the cohort window is still open."""
        with self.lock:
            if (self.ratchet_frozen and self.ratchet_eval_cohort_close_ts > 0.0
                    and self.ratchet_eval_collect_t0 <= ep_started_at <= self.ratchet_eval_cohort_close_ts):
                self.ratchet_eval_cohort_started += 1

    def ratchet_note_eval_abandoned(self, ep_started_at: float):
        """A client died with an unfinished game.  If that game was counted
        into the measurement cohort, remove it — otherwise the decide
        condition (all cohort games finished) can never be satisfied and the
        epoch wedges until the 20-minute timeout on every client death."""
        with self.lock:
            if (self.ratchet_eval_epoch >= 0 and self.ratchet_eval_cohort_close_ts > 0.0
                    and self.ratchet_eval_collect_t0 <= ep_started_at <= self.ratchet_eval_cohort_close_ts):
                self.ratchet_eval_cohort_started = max(0, self.ratchet_eval_cohort_started - 1)

    def ratchet_note_eval_episode(self, score: float, ep_started_at: float = 0.0):
        """Record one completed game's score into the ratchet measurement.

        Cohort membership is decided by START time only: the game must have
        begun after the freeze (no mixed-policy games) and before the cohort
        window closed (no completion-time selection — waiting for the whole
        cohort keeps long high-scoring games in the sample).
        """
        with self.lock:
            if (self.ratchet_eval_epoch >= 0
                    and ep_started_at >= self.ratchet_eval_collect_t0
                    and (self.ratchet_eval_cohort_close_ts <= 0.0
                         or ep_started_at <= self.ratchet_eval_cohort_close_ts)):
                self.ratchet_eval_scores.append(float(score))

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
            self._push_eval_score_1m_locked(float(score), float(level), int(length))

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
        self.update_epsilon()


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
