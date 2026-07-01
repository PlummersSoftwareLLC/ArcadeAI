#!/usr/bin/env python3
"""Robotron AI v3 — deterministic expert play controller.

Implements the document-driven Robotron expert architecture over the shared
Lua/Python state-bag pools. Provides:
  1. Behavioral cloning demonstrations during early training
  2. Safety-override actions mixed with policy output
  3. Standalone expert play for baseline measurement

Movement: artificial potential fields (threat/electrode/wall repulsion, Hulk
  vortex, weighted human center-of-mass attraction) with swept-path AABB
  collision avoidance.
Firing: decoupled 8-way raycasting hierarchy (last-grunt milking, imminent
  threat, spawners, Hulk-human blockers, density tunneling, tactical targets,
  deterministic spray).

All public functions accept V3's pre-extracted entity arrays. The learner now
uses wider object-ray features, but the first 18 columns are kept compatible:
  entity_features: (max_entities, >=18) — [x, y, w, h, vx, vy, type_one_hot(12), ...]
  entity_mask: (max_entities,) bool — True for padding
  num_entities: int — count of actual entities
"""

import math
import numpy as np
from typing import Optional
from .config import CONFIG
from .state_processor import (
    extract_entities,
    extract_global_context,
    NUM_ENTITY_CLASSES,
    _CORE_START, _ELIST_END,
)

# ── Type indices (matching state_processor one-hot order) ──────────────────

TYPE_GRUNT = 0
TYPE_HULK = 1
TYPE_BRAIN = 2
TYPE_TANK = 3
TYPE_SPAWNER = 4
TYPE_ENFORCER = 5
TYPE_PROJECTILE = 6
TYPE_HUMAN = 7
TYPE_ELECTRODE = 8
TYPE_MISSILE = 9
TYPE_SPARK = 10
TYPE_PROG = 11

# ── Coordinate system constants (from Robotron's 8.8 fixed-point) ──────────

_REL_POS_X_RANGE = 34816.0
_REL_POS_Y_RANGE = 53760.0
_POS_MAX_DIAG = 64022.0  # sqrt(34816² + 53760²)
_WORLD_UNITS_PER_PIXEL = 256.0

# ── Distance thresholds (normalised to _POS_MAX_DIAG) ─────────────────────

_SAFE_DIST = 6720.0 / _POS_MAX_DIAG        # ~0.105 (1/8 screen height)
_ALIGN_SAFE_DIST = 3072.0 / _POS_MAX_DIAG  # ~0.048 (~12px)
_PROJECTILE_DANGER_DIST = 6144.0 / _POS_MAX_DIAG  # ~24px

# ── Alignment / firing constants ───────────────────────────────────────────

_ALIGN_HALF_WINDOW_PX = 8.0
_ALIGN_HALF_WINDOW_WORLD = _ALIGN_HALF_WINDOW_PX * _WORLD_UNITS_PER_PIXEL

# ── Perimeter orbit constants ──────────────────────────────────────────────

_PERIMETER_ORBIT_RING_MIN = 0.16
_PERIMETER_ORBIT_RING_TARGET = 0.30
_PERIMETER_ORBIT_PRESSURE_THRESHOLD = 6.0
_PERIMETER_ORBIT_PROJECTILE_BONUS = 2.5
_RESCUE_NEAR_DIST = 4608.0 / _POS_MAX_DIAG  # ~18px
_RESCUE_ABORT_PROJECTILES = 2
_RESCUE_ABORT_PRESSURE = _PERIMETER_ORBIT_PRESSURE_THRESHOLD + 1.5

# ── Collision avoidance constants ──────────────────────────────────────────

_PLAYER_BOX_W_PX = 4.0
_PLAYER_BOX_H_PX = 12.0
_PLAYER_BOX_W_WORLD = _PLAYER_BOX_W_PX * _WORLD_UNITS_PER_PIXEL
_PLAYER_BOX_H_WORLD = _PLAYER_BOX_H_PX * _WORLD_UNITS_PER_PIXEL

_AVOIDANCE_BASE_PADDING_PX = 1.0
_AVOIDANCE_PADDING_BY_TYPE = {
    TYPE_GRUNT: 0.5,
    TYPE_HULK: 1.0,
    TYPE_BRAIN: 1.0,
    TYPE_TANK: 1.0,
    TYPE_SPAWNER: 1.0,
    TYPE_ENFORCER: 1.0,
    TYPE_PROJECTILE: 0.5,
    TYPE_ELECTRODE: 0.5,
    TYPE_MISSILE: 0.5,
    TYPE_SPARK: 0.5,
    TYPE_PROG: 0.5,
}

_MOVE_SAFETY_LOOKAHEAD_PX = 10.0
_MOVE_SAFETY_PATH_RADIUS_PX = 2.0
_MOVE_SAFETY_LOOKAHEAD_WORLD = _MOVE_SAFETY_LOOKAHEAD_PX * _WORLD_UNITS_PER_PIXEL
_MOVE_SAFETY_PATH_RADIUS_WORLD = _MOVE_SAFETY_PATH_RADIUS_PX * _WORLD_UNITS_PER_PIXEL

# Lava zone: outer 16px of playfield
_LAVA_X = 4096.0 / _REL_POS_X_RANGE  # ~0.118
_LAVA_Y = 4096.0 / _REL_POS_Y_RANGE  # ~0.076

# ── Bounding boxes by type (pixels) ───────────────────────────────────────

_TYPE_BOX_PX: dict[int, tuple[float, float]] = {
    TYPE_GRUNT: (5.0, 13.0),
    TYPE_HULK: (7.0, 16.0),
    TYPE_BRAIN: (7.0, 16.0),
    TYPE_TANK: (7.0, 16.0),
    TYPE_SPAWNER: (8.0, 15.0),
    TYPE_ENFORCER: (8.0, 15.0),
    TYPE_PROJECTILE: (4.0, 7.0),
    TYPE_HUMAN: (5.0, 13.0),
    TYPE_ELECTRODE: (6.0, 6.0),
    TYPE_MISSILE: (4.0, 7.0),
    TYPE_SPARK: (4.0, 7.0),
    TYPE_PROG: (5.0, 13.0),
}

# ── Category sets ──────────────────────────────────────────────────────────

_DANGEROUS_TYPES = frozenset({
    TYPE_GRUNT, TYPE_HULK, TYPE_BRAIN, TYPE_TANK,
    TYPE_SPAWNER, TYPE_ENFORCER, TYPE_PROJECTILE,
    TYPE_ELECTRODE, TYPE_MISSILE, TYPE_SPARK, TYPE_PROG,
})

_ALIGN_ROBOT_TYPES = frozenset({
    TYPE_GRUNT, TYPE_BRAIN, TYPE_TANK, TYPE_SPAWNER, TYPE_ENFORCER, TYPE_PROG,
})

_ENDGAME_CLEANUP_TYPES = frozenset({
    TYPE_GRUNT, TYPE_BRAIN, TYPE_TANK, TYPE_SPAWNER,
    TYPE_ENFORCER, TYPE_HULK, TYPE_PROG,
})

_ALIGNED_FIRE_TYPES = _ENDGAME_CLEANUP_TYPES | {TYPE_PROJECTILE, TYPE_MISSILE, TYPE_SPARK}

_SPAWN_CLASS_TYPES = frozenset({TYPE_SPAWNER, TYPE_TANK})

_HUNT_PRIORITY_TYPES = frozenset({TYPE_BRAIN, TYPE_TANK, TYPE_SPAWNER})

_DESTRUCTIBLE_TYPES = _ALIGN_ROBOT_TYPES

# Document-driven expert groups. Lua currently emits 0..8 type IDs; the
# missile/spark/prog constants are retained for compatibility with older v3
# entity tensors and tests.
_PROJECTILE_TYPES = frozenset({TYPE_PROJECTILE, TYPE_MISSILE, TYPE_SPARK})
_SPAWNER_EXPERT_TYPES = frozenset({TYPE_SPAWNER})
_TACTICAL_EXPERT_TYPES = frozenset({TYPE_BRAIN, TYPE_TANK, TYPE_ENFORCER, TYPE_PROG})
_ROBOT_WAVE_TYPES = frozenset({
    TYPE_GRUNT, TYPE_BRAIN, TYPE_TANK, TYPE_SPAWNER, TYPE_ENFORCER, TYPE_PROG,
})
_TARGETABLE_EXPERT_TYPES = _ROBOT_WAVE_TYPES | _PROJECTILE_TYPES | frozenset({TYPE_ELECTRODE})
_SURVIVAL_FIRE_TYPES = _TARGETABLE_EXPERT_TYPES | frozenset({TYPE_HULK})
_APF_DANGER_TYPES = _TARGETABLE_EXPERT_TYPES | frozenset({TYPE_HULK})

# APF tuning is intentionally in pixels; conversion happens at use sites.
_APF_REST_EPS = 0.09
_APF_WALL_MARGIN_X = 0.16
_APF_WALL_MARGIN_Y = 0.13
_APF_HUMAN_PATH_BLOCK_PX = 14.0
_APF_HUMAN_PATH_CLEAR_PX = 30.0
_APF_GRUNT_DENSITY_RADIUS_PX = 72.0
_APF_IMMINENT_TTC_FRAMES = 24.0
_APF_WAVE9_LEFT_EDGE = _LAVA_X + 0.045
_LOCAL_RESCUE_ALWAYS_DIST_PX = 18.0
_LOCAL_RESCUE_PREFER_DIST_PX = 44.0
_LOCAL_RESCUE_DANGER_MARGIN_PX = 2.0
_HUMAN_HUNT_CLEAR_DANGER_RADIUS_PX = 56.0
_CORNER_MARGIN_X = 0.24
_CORNER_MARGIN_Y = 0.19
_CORNER_HARD_RISK = 0.18
_CORNER_SWITCH_EPS = 0.015
_CORNER_APF_WEIGHT = 4.2
_WAVE9_PATH_CLEAR_FORWARD_PX = 34.0
_WAVE9_PATH_CLEAR_PERP_PX = 13.0
_WAVE9_PATH_PRESSURE_FORWARD_PX = 82.0
_WAVE9_PATH_PRESSURE_PERP_PX = 23.0
_WAVE9_PUSH_MIN_FORWARD_PX = 10.0
_WAVE9_HOLE_DIRS = (6, 7, 5, 0, 4, 2, 1, 3)
_WAVE9_WALL_DIRS = (0, 4, 1, 3)
_WAVE9_DIR_BIAS = {
    6: 0.00, 7: 0.35, 5: 0.35, 0: 1.05, 4: 1.05,
    2: 3.00, 1: 3.35, 3: 3.35,
}

# ── 8-way direction system ─────────────────────────────────────────────────

_DIR8_VECTORS: tuple[tuple[float, float], ...] = (
    (0.0, -1.0),                    # 0: N
    (0.70710678, -0.70710678),      # 1: NE
    (1.0, 0.0),                     # 2: E
    (0.70710678, 0.70710678),       # 3: SE
    (0.0, 1.0),                     # 4: S
    (-0.70710678, 0.70710678),      # 5: SW
    (-1.0, 0.0),                    # 6: W
    (-0.70710678, -0.70710678),     # 7: NW
)

_DIR8_COMPONENTS: tuple[tuple[int, int], ...] = (
    ( 0, -1),  # N
    ( 1, -1),  # NE
    ( 1,  0),  # E
    ( 1,  1),  # SE
    ( 0,  1),  # S
    (-1,  1),  # SW
    (-1,  0),  # W
    (-1, -1),  # NW
)


def _closest_dir8(vx: float, vy: float, default_dir: int = 0) -> int:
    mag2 = vx * vx + vy * vy
    if mag2 <= 1e-10:
        return default_dir
    best_idx = default_dir
    best_dot = -1e30
    for i, (dx, dy) in enumerate(_DIR8_VECTORS):
        dot = vx * dx + vy * dy
        if dot > best_dot:
            best_dot = dot
            best_idx = i
    return best_idx


def _move_dir_vector(move_dir: int) -> tuple[float, float]:
    if 0 <= move_dir < 8:
        return _DIR8_VECTORS[move_dir]
    return 0.0, 0.0


def _move_dir_endpoint_world(move_dir: int) -> tuple[float, float]:
    vx, vy = _move_dir_vector(move_dir)
    return vx * _MOVE_SAFETY_LOOKAHEAD_WORLD, vy * _MOVE_SAFETY_LOOKAHEAD_WORLD


# ── Entity data extraction helpers ─────────────────────────────────────────

def _get_active_entities(
    entity_features: np.ndarray,
    entity_mask: np.ndarray,
    num_entities: int,
) -> list[tuple[float, float, float, float, float, int]]:
    """Extract active entities into (dx, dy, vx, vy, dist_norm, type_id)."""
    if num_entities == 0:
        return []
    result = []
    for i in range(num_entities):
        if entity_mask[i]:
            continue
        ent = entity_features[i]
        dx = float(ent[0])
        dy = float(ent[1])
        vx = float(ent[4])
        vy = float(ent[5])
        type_id = int(np.argmax(ent[6:6 + NUM_ENTITY_CLASSES]))
        world_dx = dx * _REL_POS_X_RANGE
        world_dy = dy * _REL_POS_Y_RANGE
        dist_norm = math.hypot(world_dx, world_dy) / _POS_MAX_DIAG
        result.append((dx, dy, vx, vy, dist_norm, type_id))
    return result


def _nearest_of_types(
    entities: list[tuple[float, float, float, float, float, int]],
    type_set: frozenset[int],
) -> Optional[tuple[float, float, float]]:
    best = None
    for dx, dy, _vx, _vy, dist, tid in entities:
        if tid not in type_set:
            continue
        if best is None or dist < best[2]:
            best = (dx, dy, dist)
    return best


def _nearest_enemy(entities):
    return _nearest_of_types(entities, _DANGEROUS_TYPES)


def _nearest_human(entities):
    best = None
    for dx, dy, _vx, _vy, dist, tid in entities:
        if tid != TYPE_HUMAN:
            continue
        if best is None or dist < best[2]:
            best = (dx, dy, dist)
    return best


def _nearest_projectile(entities):
    return _nearest_of_types(entities, frozenset({TYPE_PROJECTILE, TYPE_MISSILE, TYPE_SPARK}))


def _preferred_align_robot(entities):
    nearest_spawner = _nearest_of_types(entities, frozenset({TYPE_SPAWNER}))
    if nearest_spawner is not None:
        return nearest_spawner
    return _nearest_of_types(entities, _ALIGN_ROBOT_TYPES)


def _nearest_endgame_cleanup(entities):
    return _nearest_of_types(entities, _ENDGAME_CLEANUP_TYPES)


def _count_humans_and_destructible(entities):
    humans = destructible = 0
    for _dx, _dy, _vx, _vy, _dist, tid in entities:
        if tid == TYPE_HUMAN:
            humans += 1
        elif tid in _DESTRUCTIBLE_TYPES:
            destructible += 1
    return humans, destructible


def _count_humans_and_cleanup(entities):
    humans = cleanup = 0
    for _dx, _dy, _vx, _vy, _dist, tid in entities:
        if tid == TYPE_HUMAN:
            humans += 1
        elif tid in _ENDGAME_CLEANUP_TYPES:
            cleanup += 1
    return humans, cleanup


# ── Threat pressure ────────────────────────────────────────────────────────

def _strategic_threat_pressure(entities):
    pressure = 0.0
    proj_count = 0
    proj_types = frozenset({TYPE_PROJECTILE, TYPE_MISSILE, TYPE_SPARK})
    ignore = frozenset({TYPE_HUMAN, TYPE_ELECTRODE})
    for _dx, _dy, _vx, _vy, dist, tid in entities:
        if tid in ignore:
            continue
        prox = max(0.0, 1.0 - min(1.0, dist / max(_SAFE_DIST, 1e-6)))
        weight = 1.0
        if tid in proj_types:
            proj_count += 1
            weight = 1.75
        elif tid in {TYPE_BRAIN, TYPE_TANK, TYPE_ENFORCER, TYPE_SPAWNER}:
            weight = 1.25
        elif tid == TYPE_HULK:
            weight = 1.5
        pressure += weight * (0.35 + prox)
    return pressure, proj_count


# ── Axis alignment ────────────────────────────────────────────────────────

def _axis_align_toward(ex_world: float, ey_world: float) -> int:
    if abs(ex_world) <= _ALIGN_HALF_WINDOW_WORLD:
        return _closest_dir8(0.0, 1.0 if ey_world >= 0.0 else -1.0, default_dir=0)
    if abs(ey_world) <= _ALIGN_HALF_WINDOW_WORLD:
        return _closest_dir8(1.0 if ex_world >= 0.0 else -1.0, 0.0, default_dir=0)
    if abs(ex_world) <= abs(ey_world):
        return _closest_dir8(1.0 if ex_world >= 0.0 else -1.0, 0.0, default_dir=0)
    else:
        return _closest_dir8(0.0, 1.0 if ey_world >= 0.0 else -1.0, default_dir=0)


# ── Perimeter orbit ────────────────────────────────────────────────────────

def _perimeter_orbit_move(px: float, py: float, fire_dir: int) -> int:
    rel_x = px - 0.5
    rel_y = py - 0.5
    radial_len = math.hypot(rel_x, rel_y)
    if radial_len <= 1e-6:
        rel_x, rel_y = 0.0, 1.0
        radial_len = 1.0
    radial_x = rel_x / radial_len
    radial_y = rel_y / radial_len

    fire_dx, fire_dy = _move_dir_vector(fire_dir % 8)
    clockwise = (radial_x * fire_dy - radial_y * fire_dx) >= 0.0
    tangent_x = radial_y if clockwise else -radial_y
    tangent_y = -radial_x if clockwise else radial_x

    ring_push = max(0.0, (_PERIMETER_ORBIT_RING_TARGET - radial_len) / max(_PERIMETER_ORBIT_RING_TARGET, 1e-6))
    outward_w = 0.35 + 0.95 * ring_push
    tangent_w = 1.05 if radial_len >= _PERIMETER_ORBIT_RING_MIN else 0.45
    move_vx = radial_x * outward_w + tangent_x * tangent_w
    move_vy = radial_y * outward_w + tangent_y * tangent_w
    return _closest_dir8(move_vx, move_vy, default_dir=0)


# ── Lava zone prevention ──────────────────────────────────────────────────

def _forbid_lava(move_dir: int, px: float, py: float) -> int:
    if move_dir < 0 or move_dir >= 8:
        return move_dir
    cx, cy = _DIR8_COMPONENTS[move_dir]
    block_x = (cx < 0 and px <= _LAVA_X) or (cx > 0 and px >= 1.0 - _LAVA_X)
    block_y = (cy < 0 and py <= _LAVA_Y) or (cy > 0 and py >= 1.0 - _LAVA_Y)
    if not block_x and not block_y:
        return move_dir
    if block_x and block_y:
        return move_dir
    nx = 0 if block_x else cx
    ny = 0 if block_y else cy
    if nx == 0 and ny == 0:
        return move_dir
    return _closest_dir8(float(nx), float(ny))


# ── Aligned fire ───────────────────────────────────────────────────────────

def _nearest_aligned_fire(entities, allowed_types=None):
    if allowed_types is None:
        allowed_types = _ALIGNED_FIRE_TYPES
    per_dir = [None] * 8
    for dx, dy, _vx, _vy, _dist, tid in entities:
        if tid not in allowed_types:
            continue
        world_dx = dx * _REL_POS_X_RANGE
        world_dy = dy * _REL_POS_Y_RANGE
        world_dist = math.hypot(world_dx, world_dy)
        if world_dist < 1e-3:
            continue
        for fire_dir, (dir_x, dir_y) in enumerate(_DIR8_VECTORS):
            forward = world_dx * dir_x + world_dy * dir_y
            if forward <= 0.0:
                continue
            perp = abs(world_dx * dir_y - world_dy * dir_x)
            if perp > _ALIGN_HALF_WINDOW_WORLD:
                continue
            cur = per_dir[fire_dir]
            if cur is None or world_dist < cur[0]:
                per_dir[fire_dir] = (world_dist, fire_dir)
    best = None
    for cand in per_dir:
        if cand is None:
            continue
        if best is None or cand[0] < best[0]:
            best = cand
    return best[1] if best is not None else None


def _priority_spawn_fire(entities, nearest_enemy_info, nearest_proj_info):
    if nearest_proj_info is not None and nearest_proj_info[2] <= _PROJECTILE_DANGER_DIST:
        proj_fire = _nearest_aligned_fire(
            entities, frozenset({TYPE_PROJECTILE, TYPE_MISSILE, TYPE_SPARK}))
        if proj_fire is not None:
            return proj_fire
    spawn_fire = _nearest_aligned_fire(entities, _SPAWN_CLASS_TYPES)
    if spawn_fire is not None:
        return spawn_fire
    nearest_spawn = _nearest_of_types(entities, _SPAWN_CLASS_TYPES)
    if nearest_spawn is None:
        return None
    close_threat = False
    if nearest_enemy_info is not None and nearest_enemy_info[2] < _ALIGN_SAFE_DIST:
        close_threat = True
    if nearest_proj_info is not None and nearest_proj_info[2] < _PROJECTILE_DANGER_DIST:
        close_threat = True
    if close_threat:
        return None
    sx, sy, _ = nearest_spawn
    return _closest_dir8(sx * _REL_POS_X_RANGE, sy * _REL_POS_Y_RANGE, default_dir=0)


def _defensive_fire(entities):
    close_proj = _nearest_projectile(entities)
    if close_proj is not None and close_proj[2] <= _PROJECTILE_DANGER_DIST:
        px, py, _ = close_proj
        return _closest_dir8(px * _REL_POS_X_RANGE, py * _REL_POS_Y_RANGE, default_dir=0)
    close_enemy = _nearest_of_types(entities, _ENDGAME_CLEANUP_TYPES)
    if close_enemy is not None and close_enemy[2] <= _ALIGN_SAFE_DIST:
        ex, ey, _ = close_enemy
        return _closest_dir8(ex * _REL_POS_X_RANGE, ey * _REL_POS_Y_RANGE, default_dir=0)
    return None


# ── Document-driven expert helpers ────────────────────────────────────────

def _entity_world(ent) -> tuple[float, float]:
    return float(ent[0]) * _REL_POS_X_RANGE, float(ent[1]) * _REL_POS_Y_RANGE


def _entity_vel_world(ent) -> tuple[float, float]:
    return float(ent[2]) * _REL_POS_X_RANGE, float(ent[3]) * _REL_POS_Y_RANGE


def _entity_type(ent) -> int:
    return int(ent[5])


def _entity_dist_world(ent) -> float:
    wx, wy = _entity_world(ent)
    return math.hypot(wx, wy)


def _entity_dist_px(ent) -> float:
    return _entity_dist_world(ent) / _WORLD_UNITS_PER_PIXEL


def _dist_px_between(a, b) -> float:
    ax, ay = _entity_world(a)
    bx, by = _entity_world(b)
    return math.hypot(ax - bx, ay - by) / _WORLD_UNITS_PER_PIXEL


def _entities_of_types(entities, type_set):
    return [ent for ent in entities if _entity_type(ent) in type_set]


def _count_types(entities, type_set) -> int:
    return sum(1 for ent in entities if _entity_type(ent) in type_set)


def _threat_profile(tid: int) -> tuple[float, float]:
    """Return (APF weight, influence radius in pixels)."""
    if tid in _PROJECTILE_TYPES:
        return 2.70, 84.0
    if tid == TYPE_PROG:
        return 2.25, 78.0
    if tid == TYPE_HULK:
        return 1.85, 74.0
    if tid == TYPE_ELECTRODE:
        return 2.10, 32.0
    if tid == TYPE_GRUNT:
        return 1.15, 58.0
    if tid == TYPE_BRAIN:
        return 1.50, 62.0
    if tid == TYPE_TANK:
        return 1.55, 60.0
    if tid == TYPE_SPAWNER:
        return 1.20, 52.0
    if tid == TYPE_ENFORCER:
        return 1.35, 58.0
    return 1.0, 48.0


def _closing_kinematics(ent) -> tuple[float, float, float]:
    """Return (time-to-closest in frames, closest-pass px, approach 0..1)."""
    wx, wy = _entity_world(ent)
    vx, vy = _entity_vel_world(ent)
    dist = math.hypot(wx, wy)
    speed2 = vx * vx + vy * vy
    if dist <= 1e-6 or speed2 <= 1e-6:
        return float("inf"), dist / _WORLD_UNITS_PER_PIXEL, 0.0

    dot = wx * vx + wy * vy
    speed = math.sqrt(speed2)
    approach = max(0.0, min(1.0, -dot / max(1.0, dist * speed)))
    t = -dot / speed2
    if t < 0.0:
        return float("inf"), dist / _WORLD_UNITS_PER_PIXEL, approach

    cx = wx + vx * t
    cy = wy + vy * t
    return t, math.hypot(cx, cy) / _WORLD_UNITS_PER_PIXEL, approach


def _point_segment_metrics(px, py, tx, ty) -> tuple[float, float]:
    """Return segment projection 0..1 and perpendicular distance in world units."""
    seg2 = tx * tx + ty * ty
    if seg2 <= 1e-6:
        return 0.0, math.hypot(px, py)
    proj = (px * tx + py * ty) / seg2
    clamped = max(0.0, min(1.0, proj))
    cx = tx * clamped
    cy = ty * clamped
    return proj, math.hypot(px - cx, py - cy)


def _ray_blocked_by_hulk(entities, tx: float, ty: float, skip_ent=None) -> bool:
    target_dist = math.hypot(tx, ty)
    if target_dist <= 1e-6:
        return False
    block_radius = 11.0 * _WORLD_UNITS_PER_PIXEL
    for ent in entities:
        if ent is skip_ent or _entity_type(ent) != TYPE_HULK:
            continue
        hx, hy = _entity_world(ent)
        proj, perp = _point_segment_metrics(hx, hy, tx, ty)
        if 0.04 < proj < 0.98 and perp <= block_radius:
            return True
    return False


def _nearest_unoccluded_entity(entities, type_set, skip_ent=None):
    candidates = sorted(
        (ent for ent in entities if ent is not skip_ent and _entity_type(ent) in type_set),
        key=_entity_dist_world,
    )
    for ent in candidates:
        wx, wy = _entity_world(ent)
        if not _ray_blocked_by_hulk(entities, wx, wy, skip_ent=ent):
            return ent
    return None


def _fire_dir_to_point(wx: float, wy: float, default_dir: int = 8) -> int:
    if wx * wx + wy * wy <= 1e-6:
        return default_dir
    return _closest_dir8(wx, wy, default_dir=0)


def _fire_dir_to_entity(ent, lead: bool = False) -> int:
    wx, wy = _entity_world(ent)
    if lead:
        t, _closest_px, approach = _closing_kinematics(ent)
        if math.isfinite(t) and approach > 0.2:
            vx, vy = _entity_vel_world(ent)
            # Do not lead all the way to the player collision point; that can
            # collapse the target vector to neutral for perfectly inbound shots.
            lead_frames = max(0.0, min(4.0, t * 0.5))
            wx += vx * lead_frames
            wy += vy * lead_frames
    return _fire_dir_to_point(wx, wy)


def _milking_last_grunt(entities) -> tuple[bool, Optional[tuple]]:
    humans = _count_types(entities, frozenset({TYPE_HUMAN}))
    if humans <= 0:
        return False, None
    wave_robots = _entities_of_types(entities, _ROBOT_WAVE_TYPES)
    if len(wave_robots) != 1:
        return False, None
    final = wave_robots[0]
    return _entity_type(final) == TYPE_GRUNT, final


def _human_path_hopelessly_occluded(entities, hx: float, hy: float) -> bool:
    human_dist_px = math.hypot(hx, hy) / _WORLD_UNITS_PER_PIXEL
    if human_dist_px <= _APF_HUMAN_PATH_CLEAR_PX:
        return False

    block_score = 0.0
    for ent in entities:
        tid = _entity_type(ent)
        if tid == TYPE_HUMAN:
            continue
        ex, ey = _entity_world(ent)
        proj, perp = _point_segment_metrics(ex, ey, hx, hy)
        if proj <= 0.03 or proj >= 0.98:
            continue
        perp_px = perp / _WORLD_UNITS_PER_PIXEL
        if perp_px > _APF_HUMAN_PATH_BLOCK_PX:
            continue
        if tid in {TYPE_HULK, TYPE_ELECTRODE}:
            block_score += 2.5
        elif tid in _PROJECTILE_TYPES:
            block_score += 1.5
        elif tid in _APF_DANGER_TYPES:
            block_score += 1.0

    return block_score >= 4.0


def _human_weight(entities, human, wave: int) -> float:
    weight = 1.0
    hx, hy = _entity_world(human)
    for other in entities:
        if other is human or _entity_type(other) != TYPE_HUMAN:
            continue
        ox, oy = _entity_world(other)
        dpx = math.hypot(hx - ox, hy - oy) / _WORLD_UNITS_PER_PIXEL
        if dpx <= 48.0:
            weight += 0.45 * (1.0 - dpx / 48.0)

    urgent = 0.0
    for ent in entities:
        tid = _entity_type(ent)
        if tid == TYPE_HUMAN:
            continue
        ex, ey = _entity_world(ent)
        dpx = math.hypot(hx - ex, hy - ey) / _WORLD_UNITS_PER_PIXEL
        if tid in {TYPE_BRAIN, TYPE_HULK} and dpx <= 82.0:
            urgent = max(urgent, 4.0 * (1.0 - dpx / 82.0))
        elif tid in {TYPE_GRUNT, TYPE_PROG} and dpx <= 42.0:
            urgent = max(urgent, 2.0 * (1.0 - dpx / 42.0))
    if wave > 0 and (wave % 5) == 0:
        urgent *= 1.35
    return weight * (1.0 + urgent)


def _human_center_of_mass(entities, wave: int, milking: bool) -> Optional[tuple[float, float, float]]:
    humans = _entities_of_types(entities, frozenset({TYPE_HUMAN}))
    if not humans:
        return None

    sx = sy = sw = 0.0
    max_urgency = 0.0
    for human in humans:
        hx, hy = _entity_world(human)
        if not milking and _human_path_hopelessly_occluded(entities, hx, hy):
            continue
        weight = _human_weight(entities, human, wave)
        sx += hx * weight
        sy += hy * weight
        sw += weight
        max_urgency = max(max_urgency, min(4.0, weight - 1.0))

    if sw <= 1e-6:
        nearest = min(humans, key=_entity_dist_world)
        hx, hy = _entity_world(nearest)
        return hx, hy, 0.0
    return sx / sw, sy / sw, max_urgency


def _nearest_danger_dist_px(entities) -> float:
    best = float("inf")
    for ent in entities:
        if _entity_type(ent) not in _APF_DANGER_TYPES:
            continue
        best = min(best, _entity_dist_px(ent))
    return best


def _move_dir_is_immediately_safe(move_dir: int, entities) -> bool:
    if move_dir < 0 or move_dir >= 8:
        return True
    hazards = _nearby_hazards(entities)
    penalty, clearance = _move_candidate_hazard_score(move_dir, hazards)
    if penalty > 1e-6 or clearance < 0.0:
        return False
    blocker = _movement_blocking_target(entities, move_dir)
    if blocker is not None and _entity_type(blocker) in _PROJECTILE_TYPES:
        return _kill_risk_score(blocker) <= 0.0
    return True


def _local_human_rescue_move(entities, wave: int) -> Optional[int]:
    if wave > 0 and (wave % 10) == 9:
        return None

    humans = sorted(_entities_of_types(entities, frozenset({TYPE_HUMAN})), key=_entity_dist_world)
    if not humans:
        return None

    nearest_danger_px = _nearest_danger_dist_px(entities)
    for human in humans:
        hdist_px = _entity_dist_px(human)
        if hdist_px > _LOCAL_RESCUE_PREFER_DIST_PX:
            break
        rescue_is_urgent = hdist_px <= _LOCAL_RESCUE_ALWAYS_DIST_PX
        human_beats_danger = hdist_px + _LOCAL_RESCUE_DANGER_MARGIN_PX < nearest_danger_px
        if not rescue_is_urgent and not human_beats_danger:
            continue

        hx, hy = _entity_world(human)
        move_dir = _closest_dir8(hx, hy, default_dir=8)
        if move_dir == 8 or _move_dir_is_immediately_safe(move_dir, entities):
            return move_dir

    return None


def _clear_board_human_hunt_move(entities, wave: int, milking: bool) -> Optional[int]:
    if wave > 0 and (wave % 10) == 9:
        return None
    if _nearest_danger_dist_px(entities) <= _HUMAN_HUNT_CLEAR_DANGER_RADIUS_PX:
        return None

    human_com = _human_center_of_mass(entities, wave, milking)
    if human_com is None:
        return None

    hx, hy, _urgency = human_com
    move_dir = _closest_dir8(hx, hy, default_dir=8)
    if move_dir == 8 or _move_dir_is_immediately_safe(move_dir, entities):
        return move_dir
    return None


def _wall_repulsion(px: float, py: float) -> tuple[float, float]:
    fx = fy = 0.0
    if px < _APF_WALL_MARGIN_X:
        fx += 1.15 * ((_APF_WALL_MARGIN_X - px) / _APF_WALL_MARGIN_X) ** 3
    elif px > 1.0 - _APF_WALL_MARGIN_X:
        fx -= 1.15 * ((px - (1.0 - _APF_WALL_MARGIN_X)) / _APF_WALL_MARGIN_X) ** 3
    if py < _APF_WALL_MARGIN_Y:
        fy += 1.05 * ((_APF_WALL_MARGIN_Y - py) / _APF_WALL_MARGIN_Y) ** 3
    elif py > 1.0 - _APF_WALL_MARGIN_Y:
        fy -= 1.05 * ((py - (1.0 - _APF_WALL_MARGIN_Y)) / _APF_WALL_MARGIN_Y) ** 3
    return fx, fy


def _edge_pressure(pos: float, margin: float) -> float:
    edge_dist = min(max(0.0, pos), max(0.0, 1.0 - pos))
    if edge_dist >= margin:
        return 0.0
    return (margin - edge_dist) / max(1e-6, margin)


def _corner_risk_at(px: float, py: float) -> float:
    return _edge_pressure(px, _CORNER_MARGIN_X) * _edge_pressure(py, _CORNER_MARGIN_Y)


def _project_move_pos(px: float, py: float, move_dir: int) -> tuple[float, float]:
    if move_dir < 0 or move_dir >= 8:
        return px, py
    dx, dy = _move_dir_vector(move_dir)
    step_x = _MOVE_SAFETY_LOOKAHEAD_WORLD / _REL_POS_X_RANGE
    step_y = _MOVE_SAFETY_LOOKAHEAD_WORLD / _REL_POS_Y_RANGE
    return (
        max(0.0, min(1.0, px + dx * step_x)),
        max(0.0, min(1.0, py + dy * step_y)),
    )


def _corner_risk_after(px: float, py: float, move_dir: int) -> float:
    nx, ny = _project_move_pos(px, py, move_dir)
    return _corner_risk_at(nx, ny)


def _centerward_alignment(px: float, py: float, move_dir: int) -> float:
    if move_dir < 0 or move_dir >= 8:
        return 0.0
    dx, dy = _move_dir_vector(move_dir)
    cx = 0.5 - px
    cy = 0.5 - py
    clen = math.hypot(cx, cy)
    if clen <= 1e-6:
        return 0.0
    return (dx * cx + dy * cy) / clen


def _corner_pressure_count(entities) -> int:
    count = 0
    for ent in entities:
        tid = _entity_type(ent)
        if tid == TYPE_ENFORCER or tid in _PROJECTILE_TYPES:
            count += 1
    return count


def _corner_apf_repulsion(px: float, py: float, entities) -> tuple[float, float]:
    risk = _corner_risk_at(px, py)
    if risk <= 1e-6:
        return 0.0, 0.0
    cx = 0.5 - px
    cy = 0.5 - py
    clen = math.hypot(cx, cy)
    if clen <= 1e-6:
        return 0.0, 0.0
    pressure_mul = 1.0 + 0.35 * min(4, _corner_pressure_count(entities))
    force = _CORNER_APF_WEIGHT * pressure_mul * (0.20 + risk) * risk
    return (cx / clen) * force, (cy / clen) * force


def _calculate_apf_move(entities, px: float, py: float, wave: int, milking: bool,
                        final_grunt=None) -> int:
    rescue_move = _local_human_rescue_move(entities, wave)
    if rescue_move is not None:
        return rescue_move
    hunt_move = _clear_board_human_hunt_move(entities, wave, milking)
    if hunt_move is not None:
        return hunt_move

    human_com = _human_center_of_mass(entities, wave, milking)
    fx = fy = 0.0

    for ent in entities:
        tid = _entity_type(ent)
        if tid not in _APF_DANGER_TYPES:
            continue
        wx, wy = _entity_world(ent)
        dist_world = max(1.0, math.hypot(wx, wy))
        dist_px = dist_world / _WORLD_UNITS_PER_PIXEL
        away_x = -wx / dist_world
        away_y = -wy / dist_world
        weight, radius_px = _threat_profile(tid)

        if milking and ent is final_grunt:
            weight *= 3.0
            radius_px = max(radius_px, 112.0)

        ttc, closest_px, approach = _closing_kinematics(ent)
        if approach > 0.15:
            if tid in _PROJECTILE_TYPES:
                radius_px += 36.0 * approach
                weight *= 1.0 + 0.65 * approach
            elif tid in {TYPE_GRUNT, TYPE_PROG}:
                radius_px += 16.0 * approach

        prox = max(0.0, 1.0 - dist_px / max(1.0, radius_px))
        if prox > 0.0:
            force = weight * (0.55 * prox + 3.20 * prox * prox)
            fx += away_x * force
            fy += away_y * force

        if (
            approach > 0.15
            and math.isfinite(ttc)
            and ttc <= _APF_IMMINENT_TTC_FRAMES
            and closest_px <= max(13.0, radius_px * 0.48)
        ):
            imminent = (
                (1.0 - ttc / _APF_IMMINENT_TTC_FRAMES)
                * (1.0 - min(1.0, closest_px / max(13.0, radius_px * 0.48)))
                * approach
            )
            vx, vy = _entity_vel_world(ent)
            future_x = wx + vx * max(0.0, min(ttc, _APF_IMMINENT_TTC_FRAMES))
            future_y = wy + vy * max(0.0, min(ttc, _APF_IMMINENT_TTC_FRAMES))
            future_len = max(1.0, math.hypot(future_x, future_y))
            fx += (-future_x / future_len) * weight * 5.0 * imminent
            fy += (-future_y / future_len) * weight * 5.0 * imminent

        if tid == TYPE_HULK and human_com is not None and dist_px <= 118.0:
            hx, hy, _urgency = human_com
            tangent_a = (-away_y, away_x)
            tangent_b = (away_y, -away_x)
            dot_a = tangent_a[0] * hx + tangent_a[1] * hy
            dot_b = tangent_b[0] * hx + tangent_b[1] * hy
            tx, ty = tangent_a if dot_a >= dot_b else tangent_b
            swirl = (1.0 - min(1.0, dist_px / 118.0)) * 1.25
            fx += tx * swirl
            fy += ty * swirl

    wx_force, wy_force = _wall_repulsion(px, py)
    fx += wx_force
    fy += wy_force
    cx_force, cy_force = _corner_apf_repulsion(px, py, entities)
    fx += cx_force
    fy += cy_force

    if human_com is not None and not (wave > 0 and (wave % 10) == 9):
        hx, hy, urgency = human_com
        hdist = max(1.0, math.hypot(hx, hy))
        rescue_mul = 1.0
        if wave > 0 and (wave % 5) == 0:
            rescue_mul = 1.45
        if milking:
            rescue_mul = 3.4
        pull = rescue_mul * (0.62 + 0.22 * min(4.0, urgency))
        fx += (hx / hdist) * pull
        fy += (hy / hdist) * pull

    if fx * fx + fy * fy <= _APF_REST_EPS * _APF_REST_EPS:
        return 8
    return _closest_dir8(fx, fy, default_dir=8)


def _imminent_collision_target(entities, skip_ent=None):
    best = None
    best_score = 0.0
    for ent in entities:
        if ent is skip_ent:
            continue
        tid = _entity_type(ent)
        if tid not in _TARGETABLE_EXPERT_TYPES:
            continue
        dist_px = _entity_dist_px(ent)
        ttc, closest_px, approach = _closing_kinematics(ent)
        score = 0.0
        if tid in _PROJECTILE_TYPES:
            if dist_px <= 42.0:
                score += 90.0 - dist_px
            if math.isfinite(ttc) and ttc <= 22.0 and closest_px <= 18.0 and approach > 0.1:
                score += 160.0 * (1.0 - ttc / 22.0) * (1.0 - closest_px / 18.0) * (0.5 + approach)
        elif tid == TYPE_PROG:
            if dist_px <= 44.0:
                score += 70.0 - dist_px
            if math.isfinite(ttc) and ttc <= 18.0 and closest_px <= 18.0:
                score += 80.0 * (1.0 - ttc / 18.0)
        elif tid == TYPE_ELECTRODE:
            if dist_px <= 18.0:
                score += 35.0 - dist_px
        elif dist_px <= 24.0:
            score += 48.0 - dist_px

        if score <= 0.0:
            continue
        wx, wy = _entity_world(ent)
        if _ray_blocked_by_hulk(entities, wx, wy, skip_ent=ent) and tid != TYPE_ELECTRODE:
            score *= 0.25
        if score > best_score:
            best = ent
            best_score = score
    return best


def _kill_risk_score(ent) -> float:
    """Immediate collision risk where preserving the wave is no longer worth it."""
    tid = _entity_type(ent)
    if tid not in _SURVIVAL_FIRE_TYPES:
        return 0.0

    dist_px = _entity_dist_px(ent)
    ttc, closest_px, approach = _closing_kinematics(ent)

    if tid in _PROJECTILE_TYPES:
        score = max(0.0, 52.0 - dist_px)
        if math.isfinite(ttc) and ttc <= 24.0 and closest_px <= 20.0 and approach > 0.1:
            score += 180.0 * (1.0 - ttc / 24.0) * (1.0 - closest_px / 20.0) * (0.5 + approach)
        return score

    if tid == TYPE_ELECTRODE:
        return max(0.0, 24.0 - dist_px) * 3.0

    if tid == TYPE_HULK:
        score = max(0.0, 24.0 - dist_px) * 2.0
        if math.isfinite(ttc) and ttc <= 18.0 and closest_px <= 18.0 and approach > 0.15:
            score += 80.0 * (1.0 - ttc / 18.0) * (1.0 - closest_px / 18.0) * approach
        return score

    score = max(0.0, 22.0 - dist_px) * 2.5
    if math.isfinite(ttc) and ttc <= 18.0 and closest_px <= 16.0 and approach > 0.15:
        score += 120.0 * (1.0 - ttc / 18.0) * (1.0 - closest_px / 16.0) * approach
    return score


def _survival_fire_target(entities):
    best = None
    best_score = 0.0
    for ent in entities:
        score = _kill_risk_score(ent)
        if score <= 0.0:
            continue
        if score > best_score:
            best = ent
            best_score = score
    return best


def _deterministic_phase(entities, px: float, py: float, wave: int, modulo: int) -> int:
    if modulo <= 1:
        return 0
    seed = int(abs(px * 997.0) + abs(py * 991.0) + max(0, wave) * 37 + len(entities) * 17)
    for idx, ent in enumerate(entities[:12]):
        seed += int((idx + 1) * (abs(ent[0]) * 113.0 + abs(ent[1]) * 127.0 + _entity_type(ent) * 19.0))
    return seed % modulo


def _blind_sweep_dir(entities, px: float, py: float, wave: int, target_ent) -> int:
    base = _fire_dir_to_entity(target_ent)
    offset = (_deterministic_phase(entities, px, py, wave, 3) - 1)
    if base >= 8:
        return _deterministic_phase(entities, px, py, wave, 8)
    return (base + offset) % 8


def _hulk_blocking_human(entities):
    humans = _entities_of_types(entities, frozenset({TYPE_HUMAN}))
    hulks = _entities_of_types(entities, frozenset({TYPE_HULK}))
    if not humans or not hulks:
        return None

    best = None
    best_score = 0.0
    for human in humans:
        hx, hy = _entity_world(human)
        human_dist = max(1.0, math.hypot(hx, hy))
        for hulk in hulks:
            ux, uy = _entity_world(hulk)
            proj, perp = _point_segment_metrics(ux, uy, hx, hy)
            perp_px = perp / _WORLD_UNITS_PER_PIXEL
            h_to_human = math.hypot(hx - ux, hy - uy) / _WORLD_UNITS_PER_PIXEL
            blocking = 0.04 < proj < 0.98 and perp_px <= 13.0
            threatening_human = h_to_human <= 38.0
            if not blocking and not threatening_human:
                continue
            score = (1.0 - min(1.0, perp / human_dist)) + max(0.0, 1.0 - h_to_human / 38.0)
            score += max(0.0, 1.0 - _entity_dist_px(hulk) / 90.0)
            if score > best_score:
                best = hulk
                best_score = score
    return best


def _movement_blocking_target(entities, move_dir: int, skip_ent=None):
    if move_dir < 0 or move_dir >= 8:
        return None
    mvx, mvy = _move_dir_vector(move_dir)
    best = None
    best_key = None
    for ent in entities:
        if ent is skip_ent:
            continue
        tid = _entity_type(ent)
        if tid not in _TARGETABLE_EXPERT_TYPES:
            continue
        wx, wy = _entity_world(ent)
        forward = wx * mvx + wy * mvy
        if forward <= 0.0:
            continue
        forward_px = forward / _WORLD_UNITS_PER_PIXEL
        if forward_px > 38.0:
            continue
        perp = abs(wx * mvy - wy * mvx) / _WORLD_UNITS_PER_PIXEL
        if perp > 11.0:
            continue
        priority = 0 if tid == TYPE_ELECTRODE else (1 if tid in _PROJECTILE_TYPES else 2)
        key = (priority, forward_px, perp)
        if best_key is None or key < best_key:
            best_key = key
            best = ent
    return best


def _grunt_density_fire_point(entities) -> Optional[tuple[float, float]]:
    grunts = _entities_of_types(entities, frozenset({TYPE_GRUNT}))
    if len(grunts) <= 5:
        return None

    radius = _APF_GRUNT_DENSITY_RADIUS_PX * _WORLD_UNITS_PER_PIXEL
    best_center = None
    best_score = -1.0
    for anchor in grunts:
        ax, ay = _entity_world(anchor)
        sx = sy = sw = 0.0
        density = 0.0
        for grunt in grunts:
            gx, gy = _entity_world(grunt)
            d = math.hypot(gx - ax, gy - ay)
            if d > radius:
                continue
            w = 1.0 - d / radius
            density += w
            sx += gx * w
            sy += gy * w
            sw += w
        if sw <= 1e-6:
            continue
        dist_penalty = 0.35 + _entity_dist_world(anchor) / max(1.0, _POS_MAX_DIAG)
        score = density / dist_penalty
        if score > best_score:
            best_score = score
            best_center = (sx / sw, sy / sw)
    return best_center


def _default_spray_dir(entities, px: float, py: float, wave: int) -> int:
    return _deterministic_phase(entities, px, py, wave, 8)


def _calculate_fire_dir(entities, px: float, py: float, wave: int, move_dir: int,
                        milking: bool, final_grunt=None) -> int:
    if milking:
        survival = _survival_fire_target(entities)
        if survival is not None:
            return _fire_dir_to_entity(survival, lead=_entity_type(survival) in _PROJECTILE_TYPES)
        imminent = _imminent_collision_target(entities, skip_ent=final_grunt)
        if imminent is not None and _entity_type(imminent) in _PROJECTILE_TYPES:
            return _fire_dir_to_entity(imminent, lead=True)
        blocker = _movement_blocking_target(entities, move_dir, skip_ent=final_grunt)
        if blocker is not None and _entity_type(blocker) == TYPE_ELECTRODE:
            return _fire_dir_to_entity(blocker)
        return 8

    imminent = _imminent_collision_target(entities)
    if imminent is not None:
        return _fire_dir_to_entity(imminent, lead=True)

    nearest_spawner = _nearest_unoccluded_entity(entities, _SPAWNER_EXPERT_TYPES)
    if nearest_spawner is not None:
        return _fire_dir_to_entity(nearest_spawner, lead=True)
    blocked_spawners = _entities_of_types(entities, _SPAWNER_EXPERT_TYPES)
    if blocked_spawners:
        nearest_blocked = min(blocked_spawners, key=_entity_dist_world)
        return _blind_sweep_dir(entities, px, py, wave, nearest_blocked)

    blocking_hulk = _hulk_blocking_human(entities)
    if blocking_hulk is not None:
        return _fire_dir_to_entity(blocking_hulk)

    blocker = _movement_blocking_target(entities, move_dir)
    if blocker is not None:
        return _fire_dir_to_entity(blocker, lead=_entity_type(blocker) in _PROJECTILE_TYPES)

    grunt_com = _grunt_density_fire_point(entities)
    if grunt_com is not None and not _ray_blocked_by_hulk(entities, grunt_com[0], grunt_com[1]):
        return _fire_dir_to_point(grunt_com[0], grunt_com[1])

    tactical = _nearest_unoccluded_entity(entities, _TACTICAL_EXPERT_TYPES)
    if tactical is not None:
        return _fire_dir_to_entity(tactical, lead=_entity_type(tactical) in _PROJECTILE_TYPES)

    target = _nearest_unoccluded_entity(entities, _TARGETABLE_EXPERT_TYPES)
    if target is not None:
        return _fire_dir_to_entity(target, lead=_entity_type(target) in _PROJECTILE_TYPES)

    return _default_spray_dir(entities, px, py, wave)


def _wave9_lane_metrics(entities, move_dir: int) -> tuple[float, float, float]:
    if move_dir < 0 or move_dir >= 8:
        return 0.0, 0.0, float("inf")
    dir_x, dir_y = _move_dir_vector(move_dir)
    block = 0.0
    pressure = 0.0
    nearest_forward = float("inf")

    for ent in entities:
        tid = _entity_type(ent)
        if tid not in _APF_DANGER_TYPES:
            continue
        wx, wy = _entity_world(ent)
        forward_px = (wx * dir_x + wy * dir_y) / _WORLD_UNITS_PER_PIXEL
        perp_px = abs(wx * dir_y - wy * dir_x) / _WORLD_UNITS_PER_PIXEL
        if forward_px > 0.0 and perp_px <= _WAVE9_PATH_PRESSURE_PERP_PX:
            nearest_forward = min(nearest_forward, forward_px)

        if (
            -4.0 <= forward_px <= _WAVE9_PATH_PRESSURE_FORWARD_PX
            and perp_px <= _WAVE9_PATH_PRESSURE_PERP_PX
        ):
            forward_term = 1.0 - max(0.0, forward_px) / _WAVE9_PATH_PRESSURE_FORWARD_PX
            align_term = 1.0 - perp_px / _WAVE9_PATH_PRESSURE_PERP_PX
            type_mul = 1.4 if tid in {TYPE_GRUNT, TYPE_PROG} else 1.0
            pressure += type_mul * (0.25 + 0.75 * forward_term) * (0.20 + 0.80 * align_term)

        if (
            -2.0 <= forward_px <= _WAVE9_PATH_CLEAR_FORWARD_PX
            and perp_px <= _WAVE9_PATH_CLEAR_PERP_PX
        ):
            forward_term = 1.0 - max(0.0, forward_px) / _WAVE9_PATH_CLEAR_FORWARD_PX
            align_term = 1.0 - perp_px / _WAVE9_PATH_CLEAR_PERP_PX
            block += 1.0 + 1.75 * forward_term + 1.25 * align_term

    return block, pressure, nearest_forward


def _wave9_lane_clear(entities, move_dir: int) -> bool:
    block, _pressure, _nearest_forward = _wave9_lane_metrics(entities, move_dir)
    return block <= 1e-6 and _move_dir_is_immediately_safe(move_dir, entities)


def _wave9_lane_pushable(entities, move_dir: int) -> bool:
    if not _move_dir_is_immediately_safe(move_dir, entities):
        return False
    _block, _pressure, nearest_forward = _wave9_lane_metrics(entities, move_dir)
    return nearest_forward >= _WAVE9_PUSH_MIN_FORWARD_PX


def _wave9_lane_status(entities, move_dir: int) -> int:
    if _wave9_lane_clear(entities, move_dir):
        return 0
    if _wave9_lane_pushable(entities, move_dir):
        return 1
    return 2


def _wave9_best_hole_dir(entities, candidate_dirs=_WAVE9_HOLE_DIRS) -> int:
    if 6 in candidate_dirs and _wave9_lane_status(entities, 6) <= 1:
        return 6

    best_dir = 6
    best_key = None
    for cand_dir in candidate_dirs:
        block, pressure, nearest_forward = _wave9_lane_metrics(entities, cand_dir)
        status = _wave9_lane_status(entities, cand_dir)
        key = (
            status,
            pressure,
            _WAVE9_DIR_BIAS.get(cand_dir, 5.0),
            block,
            nearest_forward,
        )
        if best_key is None or key < best_key:
            best_key = key
            best_dir = cand_dir
    return best_dir


def _wave9_idle_safe(entities) -> bool:
    hazards = _nearby_hazards(entities)
    penalty, clearance = _move_candidate_hazard_score(8, hazards)
    return penalty <= 1e-6 and clearance >= 0.0


def _wave9_best_move_dir(entities, preferred_dir: int, candidate_dirs=_WAVE9_HOLE_DIRS) -> int:
    if _wave9_lane_status(entities, preferred_dir) <= 1:
        return preferred_dir

    preferred_x, preferred_y = _move_dir_vector(preferred_dir)
    best_dir = None
    best_key = None
    for cand_dir in candidate_dirs:
        cand_dir = max(0, min(7, int(cand_dir)))
        status = _wave9_lane_status(entities, cand_dir)
        if status > 1:
            continue
        block, pressure, nearest_forward = _wave9_lane_metrics(entities, cand_dir)
        cand_x, cand_y = _move_dir_vector(cand_dir)
        preferred_align = preferred_x * cand_x + preferred_y * cand_y
        key = (
            status,
            pressure,
            _WAVE9_DIR_BIAS.get(cand_dir, 5.0),
            -preferred_align,
            block,
            nearest_forward,
        )
        if best_key is None or key < best_key:
            best_key = key
            best_dir = cand_dir

    if best_dir is not None:
        return best_dir
    if _wave9_idle_safe(entities):
        return 8
    return preferred_dir


def _wave9_override(entities, px: float, py: float, wave: int, locked_fire=None):
    if wave <= 0 or (wave % 10) != 9:
        return None
    if _count_types(entities, frozenset({TYPE_GRUNT})) < 8:
        return None

    if px > _APF_WAVE9_LEFT_EDGE:
        fire_dir = _wave9_best_hole_dir(entities)
        move_dir = _wave9_best_move_dir(entities, fire_dir)
    else:
        preferred_wall_dir = 0 if py > 0.58 else 4  # vertical wall oscillation
        move_dir = _wave9_best_move_dir(entities, preferred_wall_dir, _WAVE9_WALL_DIRS)
        fire_dir = 2  # E

    if locked_fire is not None and locked_fire >= 0:
        fire_dir = max(0, min(8, locked_fire))
    if move_dir < 8:
        move_dir = _forbid_lava(move_dir, px, py)
    return move_dir, fire_dir


# ── AABB collision avoidance ───────────────────────────────────────────────

def _aabb_clearance(ax, ay, aw, ah, bx, by, bw, bh):
    dx1 = bx - (ax + aw)
    dx2 = ax - (bx + bw)
    dy1 = by - (ay + ah)
    dy2 = ay - (by + bh)
    sep_x = max(dx1, dx2)
    sep_y = max(dy1, dy2)
    if sep_x > 0.0 or sep_y > 0.0:
        return math.hypot(max(sep_x, 0.0), max(sep_y, 0.0))
    overlap_x = min((ax + aw) - bx, (bx + bw) - ax)
    overlap_y = min((ay + ah) - by, (by + bh) - ay)
    return -min(overlap_x, overlap_y)


def _player_box_center():
    return 0.5 * _PLAYER_BOX_W_WORLD, 0.5 * _PLAYER_BOX_H_WORLD


def _closest_point_on_aabb(px, py, bx, by, bw, bh):
    return min(max(px, bx), bx + bw), min(max(py, by), by + bh)


def _hazard_repulsion_vector(bx, by, bw, bh, pad_world):
    hx = bx - pad_world
    hy = by - pad_world
    hw = bw + 2.0 * pad_world
    hh = bh + 2.0 * pad_world
    clearance = _aabb_clearance(0.0, 0.0, _PLAYER_BOX_W_WORLD, _PLAYER_BOX_H_WORLD, hx, hy, hw, hh)
    pcx, pcy = _player_box_center()
    nx, ny = _closest_point_on_aabb(pcx, pcy, hx, hy, hw, hh)
    rx = pcx - nx
    ry = pcy - ny
    if abs(rx) <= 1e-6 and abs(ry) <= 1e-6:
        hcx = hx + 0.5 * hw
        hcy = hy + 0.5 * hh
        rx = pcx - hcx
        ry = pcy - hcy
    return rx, ry, clearance


Hazard = tuple[float, float, float, float, float, float, float]


def _nearby_hazards(entities):
    nearby = []
    for dx, dy, _vx, _vy, _dist, tid in entities:
        if tid == TYPE_HUMAN:
            continue
        center_x = 0.5 * _PLAYER_BOX_W_WORLD + dx * _REL_POS_X_RANGE
        center_y = 0.5 * _PLAYER_BOX_H_WORLD + dy * _REL_POS_Y_RANGE
        w_px, h_px = _TYPE_BOX_PX.get(tid, (8.0, 8.0))
        box_w = w_px * _WORLD_UNITS_PER_PIXEL
        box_h = h_px * _WORLD_UNITS_PER_PIXEL
        box_x = center_x - 0.5 * box_w
        box_y = center_y - 0.5 * box_h
        pad_px = _AVOIDANCE_BASE_PADDING_PX + _AVOIDANCE_PADDING_BY_TYPE.get(tid, 0.5)
        pad_world = pad_px * _WORLD_UNITS_PER_PIXEL
        clearance = _aabb_clearance(
            0.0, 0.0, _PLAYER_BOX_W_WORLD, _PLAYER_BOX_H_WORLD,
            box_x - pad_world, box_y - pad_world,
            box_w + 2.0 * pad_world, box_h + 2.0 * pad_world,
        )
        if clearance <= _MOVE_SAFETY_LOOKAHEAD_WORLD + _MOVE_SAFETY_PATH_RADIUS_WORLD:
            nearby.append((box_x, box_y, box_w, box_h, pad_world, center_x, center_y))
    return nearby


def _move_candidate_hazard_score(move_dir, hazards):
    end_x, end_y = _move_dir_endpoint_world(move_dir)
    is_idle = move_dir == 8
    total_penalty = 0.0
    min_clearance = float("inf")
    for bx, by, bw, bh, pad_world, _cx, _cy in hazards:
        hx = bx - pad_world
        hy = by - pad_world
        hw = bw + 2.0 * pad_world
        hh = bh + 2.0 * pad_world
        samples = ((0.0, 0.0),) if is_idle else ((0.0, 0.0), (end_x * 0.5, end_y * 0.5), (end_x, end_y))
        clearances = [
            _aabb_clearance(px, py, _PLAYER_BOX_W_WORLD, _PLAYER_BOX_H_WORLD, hx, hy, hw, hh)
            for px, py in samples
        ]
        clearance = min(clearances)
        if clearance < min_clearance:
            min_clearance = clearance
        if clearance < 0.0:
            total_penalty += 1.0 + (-clearance) / max(1.0, min(hw, hh))
            if clearances[-1] < clearances[0]:
                total_penalty += (clearances[0] - clearances[-1]) / max(1.0, min(hw, hh))
    return total_penalty, min_clearance


def _hazard_escape_vector(hazards):
    escape_x = escape_y = 0.0
    nearest = None
    for bx, by, bw, bh, pad_world, cx, cy in hazards:
        rx, ry, clearance = _hazard_repulsion_vector(bx, by, bw, bh, pad_world)
        if nearest is None or clearance < nearest[2]:
            nearest = (rx, ry, clearance)
        weight = max(0.0, (_MOVE_SAFETY_LOOKAHEAD_WORLD + _MOVE_SAFETY_PATH_RADIUS_WORLD) - clearance)
        if weight <= 0.0:
            continue
        rlen = math.hypot(rx, ry)
        scale = weight / max(1.0, rlen)
        escape_x += rx * scale
        escape_y += ry * scale
    if escape_x * escape_x + escape_y * escape_y > 1e-10:
        return escape_x, escape_y
    if nearest is not None:
        return nearest[0], nearest[1]
    return 0.0, 0.0


def _primary_blocking_hazard(move_dir, hazards):
    if not hazards:
        return None
    end_x, end_y = _move_dir_endpoint_world(move_dir)
    is_idle = move_dir == 8
    best_hazard = None
    best_key = None
    for hazard in hazards:
        bx, by, bw, bh, pad_world, cx, cy = hazard
        hx = bx - pad_world
        hy = by - pad_world
        hw = bw + 2.0 * pad_world
        hh = bh + 2.0 * pad_world
        samples = ((0.0, 0.0),) if is_idle else ((0.0, 0.0), (end_x * 0.5, end_y * 0.5), (end_x, end_y))
        clearance = min(
            _aabb_clearance(px, py, _PLAYER_BOX_W_WORLD, _PLAYER_BOX_H_WORLD, hx, hy, hw, hh)
            for px, py in samples
        )
        if clearance >= 0.0:
            continue
        center_dist = math.hypot(cx, cy)
        key = (clearance, center_dist)
        if best_key is None or key < best_key:
            best_key = key
            best_hazard = hazard
    return best_hazard


def _blocking_hazard_fire_dir(move_dir, hazards):
    if not hazards:
        return None
    end_x, end_y = _move_dir_endpoint_world(move_dir)
    is_idle = move_dir == 8
    best_key = None
    best_center = None
    for bx, by, bw, bh, pad_world, cx, cy in hazards:
        hx = bx - pad_world
        hy = by - pad_world
        hw = bw + 2.0 * pad_world
        hh = bh + 2.0 * pad_world
        samples = ((0.0, 0.0),) if is_idle else ((0.0, 0.0), (end_x * 0.5, end_y * 0.5), (end_x, end_y))
        clearance = min(
            _aabb_clearance(px, py, _PLAYER_BOX_W_WORLD, _PLAYER_BOX_H_WORLD, hx, hy, hw, hh)
            for px, py in samples
        )
        if clearance >= 0.0:
            continue
        center_dist = math.hypot(cx, cy)
        key = (clearance, center_dist)
        if best_key is None or key < best_key:
            best_key = key
            best_center = (cx, cy)
    if best_center is None:
        return None
    return _closest_dir8(best_center[0], best_center[1], default_dir=0)


def _slide_candidate_dirs(move_dir, hazard):
    bx, by, bw, bh, pad_world, _cx, _cy = hazard
    hw = bw + 2.0 * pad_world
    hh = bh + 2.0 * pad_world
    dvx, dvy = _move_dir_vector(move_dir)
    if abs(dvx) <= 1e-6 and abs(dvy) <= 1e-6:
        return []
    pcx, pcy = _player_box_center()
    hcx = (bx - pad_world) + 0.5 * hw
    hcy = (by - pad_world) + 0.5 * hh
    rx = pcx - hcx
    ry = pcy - hcy
    candidates = []
    if abs(dvx) >= abs(dvy):
        go_above = ry <= 0.0
        pvy = -1.0 if go_above else 1.0
        svy = -pvy
        if hh <= hw:
            candidates.append(_closest_dir8(dvx, pvy, default_dir=move_dir))
            candidates.append(_closest_dir8(0.0, pvy))
            candidates.append(_closest_dir8(dvx, svy, default_dir=move_dir))
            candidates.append(_closest_dir8(0.0, svy))
        else:
            candidates.append(_closest_dir8(0.0, pvy))
            candidates.append(_closest_dir8(dvx, pvy, default_dir=move_dir))
            candidates.append(_closest_dir8(0.0, svy))
            candidates.append(_closest_dir8(dvx, svy, default_dir=move_dir))
    else:
        go_left = rx <= 0.0
        pvx = -1.0 if go_left else 1.0
        svx = -pvx
        if hw <= hh:
            candidates.append(_closest_dir8(pvx, dvy, default_dir=move_dir))
            candidates.append(_closest_dir8(pvx, 0.0))
            candidates.append(_closest_dir8(svx, dvy, default_dir=move_dir))
            candidates.append(_closest_dir8(svx, 0.0))
        else:
            candidates.append(_closest_dir8(pvx, 0.0))
            candidates.append(_closest_dir8(pvx, dvy, default_dir=move_dir))
            candidates.append(_closest_dir8(svx, 0.0))
            candidates.append(_closest_dir8(svx, dvy, default_dir=move_dir))
    seen = set()
    ordered = []
    for c in candidates:
        c = max(0, min(7, c))
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _apply_hazard_avoidance(move_dir, hazards):
    if not hazards:
        return move_dir
    penalty, clearance = _move_candidate_hazard_score(move_dir, hazards)
    if penalty <= 1e-6 and clearance >= 0.0:
        return move_dir
    dvx, dvy = _move_dir_vector(move_dir)
    escape_x, escape_y = _hazard_escape_vector(hazards)
    primary = _primary_blocking_hazard(move_dir, hazards)
    slide_dirs = _slide_candidate_dirs(move_dir, primary) if primary is not None else []
    for cand_dir in slide_dirs:
        cand_pen, cand_cl = _move_candidate_hazard_score(cand_dir, hazards)
        if cand_pen > 1e-6 or cand_cl < 0.0:
            continue
        return cand_dir
    best_dir = move_dir
    best_key = None
    for cand_dir in range(8):
        cand_pen, cand_cl = _move_candidate_hazard_score(cand_dir, hazards)
        cvx, cvy = _move_dir_vector(cand_dir)
        escape_align = escape_x * cvx + escape_y * cvy
        desired_align = dvx * cvx + dvy * cvy
        key = (cand_pen, -escape_align, -cand_cl, -desired_align)
        if best_key is None or key < best_key:
            best_key = key
            best_dir = cand_dir
    return best_dir


def _apply_corner_escape(move_dir: int, px: float, py: float, entities, hazards) -> int:
    current_risk = _corner_risk_at(px, py)
    chosen_risk = _corner_risk_after(px, py, move_dir)
    if current_risk <= 1e-6 and chosen_risk <= 1e-6:
        return move_dir

    chosen_center = _centerward_alignment(px, py, move_dir)
    if (
        current_risk < _CORNER_HARD_RISK
        and chosen_risk <= current_risk + _CORNER_SWITCH_EPS
        and chosen_center >= 0.0
    ):
        return move_dir

    desired_x, desired_y = _move_dir_vector(move_dir)
    best_dir = None
    best_key = None
    seen = set()
    for raw_dir in range(8):
        cand_dir = _forbid_lava(raw_dir, px, py)
        if cand_dir < 0 or cand_dir >= 8 or cand_dir in seen:
            continue
        seen.add(cand_dir)
        if not _move_dir_is_immediately_safe(cand_dir, entities):
            continue

        cand_pen, cand_cl = _move_candidate_hazard_score(cand_dir, hazards)
        if cand_pen > 1e-6 or cand_cl < 0.0:
            continue

        cand_risk = _corner_risk_after(px, py, cand_dir)
        center_align = _centerward_alignment(px, py, cand_dir)
        cand_x, cand_y = _move_dir_vector(cand_dir)
        desired_align = desired_x * cand_x + desired_y * cand_y
        key = (cand_risk, -center_align, cand_pen, -cand_cl, -desired_align)
        if best_key is None or key < best_key:
            best_key = key
            best_dir = cand_dir

    if best_dir is None:
        return move_dir

    best_risk = _corner_risk_after(px, py, best_dir)
    best_center = _centerward_alignment(px, py, best_dir)
    pressure_active = _corner_pressure_count(entities) > 0
    risk_improves = best_risk + _CORNER_SWITCH_EPS < chosen_risk
    hard_corner_escape = (
        current_risk >= _CORNER_HARD_RISK
        and best_risk <= chosen_risk + _CORNER_SWITCH_EPS
        and best_center > chosen_center + 0.10
    )
    pressure_escape = (
        pressure_active
        and best_risk <= chosen_risk + _CORNER_SWITCH_EPS
        and best_center > chosen_center + 0.25
    )
    if risk_improves or hard_corner_escape or pressure_escape:
        return best_dir
    return move_dir


# ── Main expert action ─────────────────────────────────────────────────────

def _get_strategic_expert_action(entities, px, py, wave_number=1, locked_fire=None):
    wave = max(0, int(wave_number or 0))

    override = _wave9_override(entities, float(px), float(py), wave, locked_fire=locked_fire)
    if override is not None:
        return override

    milking, final_grunt = _milking_last_grunt(entities)
    move_dir = _calculate_apf_move(
        entities,
        float(px),
        float(py),
        wave,
        milking=milking,
        final_grunt=final_grunt,
    )
    fire_dir = _calculate_fire_dir(
        entities,
        float(px),
        float(py),
        wave,
        move_dir,
        milking=milking,
        final_grunt=final_grunt,
    )

    if locked_fire is not None and locked_fire >= 0:
        fire_dir = max(0, min(8, int(locked_fire)))

    hazards = _nearby_hazards(entities)
    intended_move = move_dir
    move_dir = _apply_hazard_avoidance(move_dir, hazards)

    if move_dir < 8:
        move_dir = _forbid_lava(move_dir, float(px), float(py))

    move_dir = _apply_corner_escape(move_dir, float(px), float(py), entities, hazards)

    if (
        not milking
        and (locked_fire is None or locked_fire < 0)
        and move_dir != intended_move
    ):
        blocked_fire = _blocking_hazard_fire_dir(intended_move, hazards)
        if blocked_fire is not None:
            fire_dir = blocked_fire

    return move_dir, fire_dir


# ═══════════════════════════════════════════════════════════════════════════
# Public API — matches the interface expected by socket_server.py
# ═══════════════════════════════════════════════════════════════════════════

def get_expert_action(
    wire_state: np.ndarray,
    wave_number: int = 1,
    max_entities: int = CONFIG.model.max_entities,
    locked_fire: Optional[int] = None,
) -> tuple[int, int]:
    """Compute expert action from raw wire state."""
    entity_features, entity_mask, num_entities = extract_entities(wire_state, max_entities)
    px = float(wire_state[5]) if wire_state.size > 6 else 0.5
    py = float(wire_state[6]) if wire_state.size > 6 else 0.5
    entities = _get_active_entities(entity_features, entity_mask, num_entities)
    return _get_strategic_expert_action(entities, px, py, wave_number, locked_fire=locked_fire)


def get_expert_action_from_entities(
    entity_features: np.ndarray,
    entity_mask: np.ndarray,
    num_entities: int,
    wave_number: int = 1,
    px: float = 0.5,
    py: float = 0.5,
    locked_fire: Optional[int] = None,
) -> tuple[int, int]:
    """Compute expert action from pre-extracted V3 entity arrays."""
    entities = _get_active_entities(entity_features, entity_mask, num_entities)
    return _get_strategic_expert_action(entities, px, py, wave_number, locked_fire=locked_fire)
