#!/usr/bin/env python3
"""Robotron AI v3 — Strategic heuristic expert system.

Ported from V2's strategic expert (aimodel.py) to work with V3's entity
feature arrays. Provides:
  1. Behavioral cloning demonstrations during early training
  2. Safety-override actions mixed with policy output
  3. Standalone expert play for baseline measurement

Movement: priority cascade (flee → rescue → orbit → align → flee fallback)
  with swept-path AABB collision avoidance.
Firing: aligned-shot priority system with spawn-class preference and
  last-enemy rescue mode.

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


# ── Main expert action ─────────────────────────────────────────────────────

def _get_strategic_expert_action(entities, px, py, wave_number=1, locked_fire=None):
    ne = _nearest_enemy(entities)
    np_ = _nearest_projectile(entities)
    nh = _nearest_human(entities)
    nph = _nearest_of_types(entities, _HUNT_PRIORITY_TYPES)
    nar = _preferred_align_robot(entities)
    nec = _nearest_endgame_cleanup(entities)
    hazards = _nearby_hazards(entities)
    aligned = _nearest_aligned_fire(entities)
    priority_spawn = _priority_spawn_fire(entities, ne, np_)
    humans_remaining, _cleanup = _count_humans_and_cleanup(entities)
    humans_rescue, destructible = _count_humans_and_destructible(entities)
    threat_pressure, proj_count = _strategic_threat_pressure(entities)

    wave = max(0, wave_number)
    rescue_wave = wave > 0 and (wave % 5) == 0
    tank_wave = wave >= 7 and ((wave - 7) % 5) == 0
    protect_humans_wave = rescue_wave or tank_wave
    last_enemy_rescue = humans_rescue > 0 and destructible <= 1
    radial_dist = math.hypot(px - 0.5, py - 0.5)

    near_human_rescue_ok = False
    if nh is not None:
        near_human_rescue_ok = (
            nh[2] <= _RESCUE_NEAR_DIST
            and proj_count <= _RESCUE_ABORT_PROJECTILES
            and threat_pressure < _RESCUE_ABORT_PRESSURE
        )

    # ── Fire direction ──────────────────────────────────────────────
    rescue_proj_fire = None
    rescue_hunt_fire = None

    if last_enemy_rescue:
        df = _defensive_fire(entities)
        fire_dir = df if df is not None else 8
    else:
        if protect_humans_wave:
            if np_ is not None and np_[2] <= _PROJECTILE_DANGER_DIST:
                rescue_proj_fire = _nearest_aligned_fire(
                    entities, frozenset({TYPE_PROJECTILE, TYPE_MISSILE, TYPE_SPARK}))
            rescue_hunt_fire = _nearest_aligned_fire(entities, _HUNT_PRIORITY_TYPES)
        if rescue_proj_fire is not None:
            fire_dir = rescue_proj_fire
        elif rescue_hunt_fire is not None:
            fire_dir = rescue_hunt_fire
        elif protect_humans_wave and nph is not None:
            fx, fy, _ = nph
            fire_dir = _closest_dir8(fx * _REL_POS_X_RANGE, fy * _REL_POS_Y_RANGE, default_dir=0)
        elif priority_spawn is not None:
            fire_dir = priority_spawn
        elif aligned is not None:
            fire_dir = aligned
        elif np_ is not None and (ne is None or np_[2] <= max(ne[2], _PROJECTILE_DANGER_DIST)):
            fire_dir = _closest_dir8(np_[0] * _REL_POS_X_RANGE, np_[1] * _REL_POS_Y_RANGE, default_dir=0)
        elif ne is not None:
            fire_dir = _closest_dir8(ne[0] * _REL_POS_X_RANGE, ne[1] * _REL_POS_Y_RANGE, default_dir=0)
        else:
            fire_dir = 8

    if locked_fire is not None and locked_fire >= 0:
        fire_dir = max(0, min(8, locked_fire))

    # ── Movement ────────────────────────────────────────────────────
    if ne is not None:
        ex, ey, enemy_dist = ne
        ex_world = ex * _REL_POS_X_RANGE
        ey_world = ey * _REL_POS_Y_RANGE

        is_close_threat = enemy_dist < _ALIGN_SAFE_DIST
        if np_ is not None and np_[2] < _PROJECTILE_DANGER_DIST:
            ex, ey, enemy_dist = np_
            ex_world = ex * _REL_POS_X_RANGE
            ey_world = ey * _REL_POS_Y_RANGE
            is_close_threat = True

        if is_close_threat:
            move_dir = _closest_dir8(-ex_world, -ey_world, default_dir=0)
        elif nh is not None and threat_pressure < (_PERIMETER_ORBIT_PRESSURE_THRESHOLD - 1.0):
            hx, hy, _ = nh
            move_dir = _closest_dir8(hx * _REL_POS_X_RANGE, hy * _REL_POS_Y_RANGE)
        elif last_enemy_rescue and nh is not None:
            hx, hy, _ = nh
            move_dir = _closest_dir8(hx * _REL_POS_X_RANGE, hy * _REL_POS_Y_RANGE)
        elif protect_humans_wave and nh is not None:
            hx, hy, _ = nh
            move_dir = _closest_dir8(hx * _REL_POS_X_RANGE, hy * _REL_POS_Y_RANGE)
        elif near_human_rescue_ok:
            hx, hy, _ = nh
            move_dir = _closest_dir8(hx * _REL_POS_X_RANGE, hy * _REL_POS_Y_RANGE)
        elif (
            not protect_humans_wave
            and not last_enemy_rescue
            and (
                (threat_pressure + proj_count * _PERIMETER_ORBIT_PROJECTILE_BONUS) >= _PERIMETER_ORBIT_PRESSURE_THRESHOLD
                or (threat_pressure >= _PERIMETER_ORBIT_PRESSURE_THRESHOLD and radial_dist < _PERIMETER_ORBIT_RING_MIN)
            )
        ):
            move_dir = _perimeter_orbit_move(px, py, fire_dir)
        elif nar is not None:
            ax, ay, _ = nar
            move_dir = _axis_align_toward(ax * _REL_POS_X_RANGE, ay * _REL_POS_Y_RANGE)
        elif humans_remaining <= 0 and nec is not None:
            ax, ay, _ = nec
            move_dir = _axis_align_toward(ax * _REL_POS_X_RANGE, ay * _REL_POS_Y_RANGE)
        else:
            move_dir = _closest_dir8(-ex_world, -ey_world, default_dir=0)
    elif nh is not None:
        hx, hy, _ = nh
        move_dir = _closest_dir8(hx * _REL_POS_X_RANGE, hy * _REL_POS_Y_RANGE)
    else:
        move_dir = 8

    # ── Collision avoidance post-check ──────────────────────────────
    intended_move = move_dir
    move_dir = _apply_hazard_avoidance(move_dir, hazards)

    # ── Lava zone prevention ────────────────────────────────────────
    if move_dir < 8:
        move_dir = _forbid_lava(move_dir, px, py)

    if (locked_fire is None or locked_fire < 0) and move_dir != intended_move:
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
