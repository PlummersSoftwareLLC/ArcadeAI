#!/usr/bin/env python3
"""Robotron AI v3 - object/ray state processor.

Lua sends the shared Robotron wire packet: core scalars, ELIST bytes, legacy
lane/grid blocks, and distance-sorted state-bag pools. The v3 learner ignores
the legacy lane/grid block and uses the state-bag pools, whose positions come
from the same collision-center calculations as the debug HUD overlay.

Processed observation:
  entity_features:      (max_entities, 32)
  entity_mask:          (max_entities,) True for padding
  global_context:       (40,) core player/game + ELIST bytes (raw; the 4 surround
                        affordances are appended on-device inside the model)
  move_action_features: (9, 12) zero placeholder; computed on-device in the model
  fire_action_features: (9, 12) zero placeholder; computed on-device in the model

The first 18 entity columns intentionally remain compatible with the expert:
  [rel_x, rel_y, box_w, box_h, rel_vx, rel_vy, type_one_hot(12)]
"""

from __future__ import annotations

import math

import numpy as np
import torch

from .config import (
    LEGACY_CORE_FEATURES,
    LEGACY_ELIST_FEATURES,
    TACTICAL_LANE_COUNT,
    TACTICAL_LANE_FEATURES,
    TACTICAL_LOCAL_GRID_FEATURES,
    ENTITY_POOL_DEFS,
    CONFIG,
)

# Offsets into the Lua wire state.
_CORE_START = 0
_CORE_END = LEGACY_CORE_FEATURES
_ELIST_START = _CORE_END
_ELIST_END = _ELIST_START + LEGACY_ELIST_FEATURES
_LANES_START = _ELIST_END
_LANES_END = _LANES_START + TACTICAL_LANE_COUNT * TACTICAL_LANE_FEATURES
_GRID_START = _LANES_END
_GRID_END = _GRID_START + TACTICAL_LOCAL_GRID_FEATURES
_POOLS_START = _GRID_END

# Robotron playfield geometry. These match main.lua's 8.8 fixed-point ranges.
_REL_POS_X_RANGE = 34816.0
_REL_POS_Y_RANGE = 53760.0
_POS_MAX_DIAG = math.sqrt((_REL_POS_X_RANGE ** 2) + (_REL_POS_Y_RANGE ** 2))
_WORLD_UNITS_PER_PIXEL = 256.0
_AIM_CROSS_WORLD = 8.0 * _WORLD_UNITS_PER_PIXEL
_MOVE_STEP_WORLD = 10.0 * _WORLD_UNITS_PER_PIXEL
_WALL_CLEARANCE_WORLD = 96.0 * _WORLD_UNITS_PER_PIXEL

NUM_ENTITY_CLASSES = 12
ENTITY_FEATURE_DIM = CONFIG.model.entity_feature_dim
ACTION_FEATURE_DIM = CONFIG.model.action_feature_dim

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

_DIR8 = np.asarray(
    [
        (0.0, -1.0),
        (0.70710678, -0.70710678),
        (1.0, 0.0),
        (0.70710678, 0.70710678),
        (0.0, 1.0),
        (-0.70710678, 0.70710678),
        (-1.0, 0.0),
        (-0.70710678, -0.70710678),
        (0.0, 0.0),  # idle
    ],
    dtype=np.float32,
)

_TYPE_BOX_PX = {
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

_DANGEROUS_TYPES = frozenset({
    TYPE_GRUNT, TYPE_HULK, TYPE_BRAIN, TYPE_TANK, TYPE_SPAWNER,
    TYPE_ENFORCER, TYPE_PROJECTILE, TYPE_ELECTRODE, TYPE_MISSILE,
    TYPE_SPARK, TYPE_PROG,
})
_PROJECTILE_TYPES = frozenset({TYPE_PROJECTILE, TYPE_MISSILE, TYPE_SPARK})
_DESTRUCTIBLE_TYPES = frozenset({
    TYPE_GRUNT, TYPE_BRAIN, TYPE_TANK, TYPE_SPAWNER, TYPE_ENFORCER,
    TYPE_PROJECTILE, TYPE_ELECTRODE, TYPE_MISSILE, TYPE_SPARK, TYPE_PROG,
})
_PRIORITY_FIRE_TYPES = frozenset({
    TYPE_BRAIN, TYPE_TANK, TYPE_SPAWNER, TYPE_ENFORCER,
    TYPE_PROJECTILE, TYPE_MISSILE, TYPE_SPARK,
})
_STATIC_BLOCKER_TYPES = frozenset({TYPE_HULK, TYPE_ELECTRODE})

_POOL_TYPE_DEFAULT = {
    "destructible": TYPE_GRUNT,
    "hulk": TYPE_HULK,
    "obstacle": TYPE_ELECTRODE,
    "human": TYPE_HUMAN,
}

# Per-pool base offset into the flattened entity array. Rows are distance-sorted
# within each group, so indices encode group and distance rank rather than a
# stable object pointer identity.
_POOL_GLOBAL_BASE: dict[str, int] = {}
_ENTITY_SLOT_TOTAL = 0
for _pname, _pslots, _pfeats in ENTITY_POOL_DEFS:
    _POOL_GLOBAL_BASE[_pname] = _ENTITY_SLOT_TOTAL
    _ENTITY_SLOT_TOTAL += _pslots


def _clamp01(v):
    return np.clip(v, 0.0, 1.0)


def _clamp11(v):
    return np.clip(v, -1.0, 1.0)


def _safe_float(v: float, default: float = 0.0) -> float:
    try:
        out = float(v)
    except Exception:
        return default
    if not math.isfinite(out):
        return default
    return out


def _decode_unified_type_id(type_norm: float) -> int:
    val = max(0.0, min(1.0, _safe_float(type_norm, 0.0)))
    return int(round(val * 8.0))


def _type_box_norm(type_id: int) -> tuple[float, float]:
    w, h = _TYPE_BOX_PX.get(int(type_id), (5.0, 13.0))
    return min(1.0, w / 16.0), min(1.0, h / 16.0)


def _dist_from_rel(dx: float, dy: float) -> float:
    wx = float(dx) * _REL_POS_X_RANGE
    wy = float(dy) * _REL_POS_Y_RANGE
    return min(1.0, math.hypot(wx, wy) / _POS_MAX_DIAG)


def _slot_type(pool_name: str, slot: np.ndarray) -> int:
    if slot.shape[0] > 9:
        return max(0, min(NUM_ENTITY_CLASSES - 1, _decode_unified_type_id(slot[9])))
    return _POOL_TYPE_DEFAULT.get(pool_name, TYPE_GRUNT)


def _collect_entity_slots(wire_state: np.ndarray) -> list[dict[str, float]]:
    pools_data = wire_state[_POOLS_START:]
    pools_len = len(pools_data)
    pool_offset = 0
    out: list[dict[str, float]] = []

    for pool_name, max_slots, feat_per_slot in ENTITY_POOL_DEFS:
        slot_start = pool_offset + 1
        slot_end = slot_start + max_slots * feat_per_slot
        if slot_end > pools_len:
            pool_offset += 1 + max_slots * feat_per_slot
            continue

        raw = pools_data[slot_start:slot_end].reshape(max_slots, feat_per_slot)
        for slot_idx in range(max_slots):
            slot = raw[slot_idx]
            if not np.isfinite(slot).all() or slot[0] <= 0.5:
                continue

            type_id = _slot_type(pool_name, slot)
            dx = float(_clamp11(slot[1] if feat_per_slot > 1 else 0.0))
            dy = float(_clamp11(slot[2] if feat_per_slot > 2 else 0.0))
            dist = float(_clamp01(slot[3] if feat_per_slot > 3 else _dist_from_rel(dx, dy)))
            if dist <= 1e-6:
                dist = _dist_from_rel(dx, dy)

            vx = float(_clamp11(slot[4])) if feat_per_slot > 4 else 0.0
            vy = float(_clamp11(slot[5])) if feat_per_slot > 5 else 0.0
            threat = float(_clamp01(slot[6] if feat_per_slot > 6 else 0.0))
            approach = float(_clamp11(slot[7] if feat_per_slot > 7 else 0.0))
            ttc_norm = float(_clamp01(slot[8] if feat_per_slot > 8 else 1.0))
            closest_pass_norm = dist

            out.append({
                "pool": pool_name,
                "slot": float(slot_idx),
                "type_id": float(type_id),
                "dx": dx,
                "dy": dy,
                "dist": dist,
                "vx": vx,
                "vy": vy,
                "threat": threat,
                "approach": approach,
                "ttc_norm": ttc_norm,
                "closest_pass_norm": closest_pass_norm,
            })

        pool_offset += 1 + max_slots * feat_per_slot

    return out


def extract_entities(
    wire_state: np.ndarray,
    max_entities: int = CONFIG.model.max_entities,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Extract HUD-consistent object tokens from the Lua state-bag pools."""
    entity_dim = ENTITY_FEATURE_DIM
    features = np.zeros((max_entities, entity_dim), dtype=np.float32)
    mask = np.ones(max_entities, dtype=bool)

    px = _safe_float(wire_state[5], 0.5) if wire_state.shape[0] > 6 else 0.5
    py = _safe_float(wire_state[6], 0.5) if wire_state.shape[0] > 6 else 0.5
    slots = _collect_entity_slots(wire_state)

    # Place each entity at its group/rank index (pool base + slot). Holes stay
    # masked. num_entities is returned as an exclusive upper bound on occupied
    # indices, so consumers that iterate range(n) with a mask check still visit
    # every active row.
    max_idx = -1
    for slot in slots:
        gidx = _POOL_GLOBAL_BASE[slot["pool"]] + int(slot["slot"])
        if gidx >= max_entities:
            continue
        type_id = int(max(0, min(NUM_ENTITY_CLASSES - 1, int(slot["type_id"]))))
        dx = float(slot["dx"])
        dy = float(slot["dy"])
        vx = float(slot["vx"])
        vy = float(slot["vy"])
        dist = float(slot["dist"])
        threat = float(slot["threat"])
        approach = float(slot["approach"])
        ttc_norm = float(slot["ttc_norm"])
        closest_pass_norm = float(slot["closest_pass_norm"])
        box_w, box_h = _type_box_norm(type_id)

        out = features[gidx]
        out[0] = dx
        out[1] = dy
        out[2] = box_w
        out[3] = box_h
        out[4] = vx
        out[5] = vy
        out[6 + type_id] = 1.0
        out[18] = float(_clamp01(px + dx))
        out[19] = float(_clamp01(py + dy))
        out[20] = dist
        out[21] = 1.0 - dist

        speed_world = math.hypot(vx * _REL_POS_X_RANGE, vy * _REL_POS_Y_RANGE)
        out[22] = min(1.0, speed_world / (16.0 * _WORLD_UNITS_PER_PIXEL))
        out[23] = approach
        out[24] = ttc_norm
        out[25] = closest_pass_norm
        out[26] = threat
        out[27] = 1.0 if type_id in _DANGEROUS_TYPES else 0.0
        out[28] = 1.0 if type_id in _PROJECTILE_TYPES else 0.0
        out[29] = 1.0 if type_id == TYPE_HUMAN else 0.0
        out[30] = 1.0 if type_id in _STATIC_BLOCKER_TYPES else 0.0
        out[31] = 1.0 if type_id in _DESTRUCTIBLE_TYPES else 0.0
        mask[gidx] = False
        if gidx > max_idx:
            max_idx = gidx

    return features, mask, max_idx + 1


def extract_global_context(wire_state: np.ndarray) -> np.ndarray:
    """Extract core player/game fields plus ELIST bytes."""
    return wire_state[_CORE_START:_ELIST_END].astype(np.float32).copy()


def _active_entity_rows(entity_features: np.ndarray, entity_mask: np.ndarray) -> list[np.ndarray]:
    rows = []
    for i in range(entity_features.shape[0]):
        if entity_mask[i]:
            continue
        rows.append(entity_features[i])
    return rows


def _wall_clearance(px_norm: float, py_norm: float, dir_x: float, dir_y: float) -> float:
    if abs(dir_x) < 1e-6 and abs(dir_y) < 1e-6:
        return 0.0
    px_world = float(px_norm) * _REL_POS_X_RANGE
    py_world = float(py_norm) * _REL_POS_Y_RANGE
    clearance = _POS_MAX_DIAG
    if dir_x > 1e-6:
        clearance = min(clearance, (_REL_POS_X_RANGE - px_world) / dir_x)
    elif dir_x < -1e-6:
        clearance = min(clearance, px_world / (-dir_x))
    if dir_y > 1e-6:
        clearance = min(clearance, (_REL_POS_Y_RANGE - py_world) / dir_y)
    elif dir_y < -1e-6:
        clearance = min(clearance, py_world / (-dir_y))
    if clearance == _POS_MAX_DIAG:
        clearance = 0.0
    return max(0.0, min(1.0, clearance / _WALL_CLEARANCE_WORLD))


def _center_pull_alignment(px_norm: float, py_norm: float, dir_x: float, dir_y: float) -> float:
    cx = (0.5 - float(px_norm)) * _REL_POS_X_RANGE
    cy = (0.5 - float(py_norm)) * _REL_POS_Y_RANGE
    mag = math.hypot(cx, cy)
    if mag <= 1e-6:
        return 0.0
    return max(0.0, min(1.0, ((cx / mag) * dir_x) + ((cy / mag) * dir_y)))


def _direction_geometry(ent: np.ndarray, dir_x: float, dir_y: float) -> tuple[float, float, float, float]:
    dx_world = float(ent[0]) * _REL_POS_X_RANGE
    dy_world = float(ent[1]) * _REL_POS_Y_RANGE
    dist = max(1.0, math.hypot(dx_world, dy_world))
    forward = (dx_world * dir_x) + (dy_world * dir_y)
    cross = abs((dx_world * dir_y) - (dy_world * dir_x))
    align = max(0.0, min(1.0, forward / dist))
    cross_gate = max(0.0, min(1.0, 1.0 - (cross / (_AIM_CROSS_WORLD * 2.0))))
    return dist, forward, align, cross_gate


def build_action_features(
    entity_features: np.ndarray,
    entity_mask: np.ndarray,
    global_context: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Build action-conditioned geometry rows for move and fire heads."""
    move = np.zeros((9, ACTION_FEATURE_DIM), dtype=np.float32)
    fire = np.zeros((9, ACTION_FEATURE_DIM), dtype=np.float32)
    px = _safe_float(global_context[5], 0.5) if global_context.shape[0] > 6 else 0.5
    py = _safe_float(global_context[6], 0.5) if global_context.shape[0] > 6 else 0.5
    ents = _active_entity_rows(entity_features, entity_mask)

    destructible_count = sum(1 for e in ents if e[31] > 0.5)
    destructible_count_norm = min(1.0, destructible_count / 32.0)

    for action_idx, (dir_x, dir_y) in enumerate(_DIR8):
        idle = 1.0 if action_idx == 8 else 0.0
        move[action_idx, 0] = dir_x
        move[action_idx, 1] = dir_y
        move[action_idx, 2] = _wall_clearance(px, py, float(dir_x), float(dir_y))
        move[action_idx, 10] = _center_pull_alignment(px, py, float(dir_x), float(dir_y))
        move[action_idx, 11] = idle

        fire[action_idx, 0] = dir_x
        fire[action_idx, 1] = dir_y
        fire[action_idx, 8] = destructible_count_norm
        fire[action_idx, 10] = 1.0
        fire[action_idx, 11] = idle
        if ACTION_FEATURE_DIM >= 24:
            move[action_idx, 23] = destructible_count_norm
            fire[action_idx, 23] = destructible_count_norm

        if idle > 0.0:
            continue

        nearest_danger_dist = 1.0
        nearest_projectile_ttc = 1.0
        best_target = 0.0
        priority_target = 0.0
        projectile_intercept = 0.0
        target_density = 0.0
        nearest_target_dist = 1.0
        aligned_human_penalty = 0.0
        hulk_blocker = 0.0
        nearest_hulk_dist = 1.0
        nearest_electrode_dist = 1.0
        nearest_brain_dist = 1.0
        nearest_spawn_dist = 1.0
        nearest_brain_target_dist = 1.0
        nearest_spawn_target_dist = 1.0
        type_move_pressure = {
            TYPE_GRUNT: 0.0,
            TYPE_HULK: 0.0,
            TYPE_BRAIN: 0.0,
            TYPE_TANK: 0.0,
            TYPE_SPAWNER: 0.0,
            TYPE_ENFORCER: 0.0,
            TYPE_ELECTRODE: 0.0,
            TYPE_MISSILE: 0.0,
            TYPE_SPARK: 0.0,
        }
        type_fire_score = {
            TYPE_GRUNT: 0.0,
            TYPE_BRAIN: 0.0,
            TYPE_TANK: 0.0,
            TYPE_SPAWNER: 0.0,
            TYPE_ENFORCER: 0.0,
            TYPE_PROJECTILE: 0.0,
            TYPE_MISSILE: 0.0,
            TYPE_SPARK: 0.0,
            TYPE_PROG: 0.0,
        }

        for ent in ents:
            type_id = int(np.argmax(ent[6:6 + NUM_ENTITY_CLASSES]))
            dist_norm = float(ent[20])
            closeness = 1.0 - max(0.0, min(1.0, dist_norm))
            threat = float(max(0.0, min(1.0, ent[26])))
            ttc = float(max(0.0, min(1.0, ent[24])))

            dx_world = float(ent[0]) * _REL_POS_X_RANGE
            dy_world = float(ent[1]) * _REL_POS_Y_RANGE
            cur_dist = max(1.0, math.hypot(dx_world, dy_world))
            next_dist = math.hypot(
                dx_world - (float(dir_x) * _MOVE_STEP_WORLD),
                dy_world - (float(dir_y) * _MOVE_STEP_WORLD),
            )
            moving_toward = max(0.0, min(1.0, (cur_dist - next_dist) / _MOVE_STEP_WORLD))
            moving_away = max(0.0, min(1.0, (next_dist - cur_dist) / _MOVE_STEP_WORLD))

            if type_id in _DANGEROUS_TYPES:
                nearest_danger_dist = min(nearest_danger_dist, dist_norm)
                pressure = threat * (0.25 + 0.75 * closeness) * (0.2 + 0.8 * moving_toward)
                if type_id in type_move_pressure:
                    type_move_pressure[type_id] = min(1.0, type_move_pressure[type_id] + pressure)
                if type_id == TYPE_HULK:
                    nearest_hulk_dist = min(nearest_hulk_dist, dist_norm)
                elif type_id == TYPE_ELECTRODE:
                    nearest_electrode_dist = min(nearest_electrode_dist, dist_norm)
                elif type_id == TYPE_BRAIN:
                    nearest_brain_dist = min(nearest_brain_dist, dist_norm)
                elif type_id in {TYPE_TANK, TYPE_SPAWNER, TYPE_ENFORCER}:
                    nearest_spawn_dist = min(nearest_spawn_dist, dist_norm)
                if type_id in _PROJECTILE_TYPES:
                    move[action_idx, 4] += pressure
                    nearest_projectile_ttc = min(nearest_projectile_ttc, ttc)
                else:
                    move[action_idx, 3] += pressure
                move[action_idx, 7] = max(
                    move[action_idx, 7],
                    threat * (0.25 + 0.75 * closeness) * moving_away,
                )

            if type_id in _STATIC_BLOCKER_TYPES:
                blocker = (0.25 + 0.75 * closeness) * (0.25 + 0.75 * moving_toward)
                move[action_idx, 5] = max(move[action_idx, 5], blocker)
                hulk_blocker = max(hulk_blocker, blocker if type_id == TYPE_HULK else 0.0)

            if type_id == TYPE_HUMAN:
                _dist, forward, align, cross_gate = _direction_geometry(ent, float(dir_x), float(dir_y))
                if forward > 0.0:
                    human_pull = align * (0.35 + 0.65 * closeness)
                    move[action_idx, 6] = max(move[action_idx, 6], human_pull)
                    aligned_human_penalty = max(aligned_human_penalty, cross_gate * align * closeness)
                continue

            if type_id not in _DESTRUCTIBLE_TYPES:
                continue

            _dist, forward, align, cross_gate = _direction_geometry(ent, float(dir_x), float(dir_y))
            if forward <= 0.0:
                continue

            priority = 1.0
            if type_id in _PRIORITY_FIRE_TYPES:
                priority = 1.25
            if type_id in _PROJECTILE_TYPES:
                priority = 1.45
            score = max(0.0, min(1.0, align * cross_gate * (0.25 + 0.75 * closeness) * priority))
            best_target = max(best_target, score)
            nearest_target_dist = min(nearest_target_dist, dist_norm)
            target_density += score
            if type_id in type_fire_score:
                type_fire_score[type_id] = max(type_fire_score[type_id], score)
            if type_id == TYPE_BRAIN:
                nearest_brain_target_dist = min(nearest_brain_target_dist, dist_norm)
            elif type_id in {TYPE_TANK, TYPE_SPAWNER, TYPE_ENFORCER}:
                nearest_spawn_target_dist = min(nearest_spawn_target_dist, dist_norm)
            if type_id in _PRIORITY_FIRE_TYPES:
                priority_target = max(priority_target, score)
            if type_id in _PROJECTILE_TYPES:
                intercept = score * (0.35 + 0.65 * (1.0 - ttc))
                projectile_intercept = max(projectile_intercept, intercept)

        move[action_idx, 3] = min(1.0, move[action_idx, 3])
        move[action_idx, 4] = min(1.0, move[action_idx, 4])
        move[action_idx, 5] = min(1.0, move[action_idx, 5])
        move[action_idx, 6] = min(1.0, move[action_idx, 6])
        move[action_idx, 7] = min(1.0, move[action_idx, 7] + 0.2 * move[action_idx, 6])
        move[action_idx, 8] = nearest_danger_dist
        move[action_idx, 9] = nearest_projectile_ttc
        if ACTION_FEATURE_DIM >= 24:
            move[action_idx, 12] = min(1.0, type_move_pressure[TYPE_GRUNT])
            move[action_idx, 13] = min(1.0, type_move_pressure[TYPE_HULK])
            move[action_idx, 14] = min(1.0, type_move_pressure[TYPE_BRAIN])
            move[action_idx, 15] = min(
                1.0,
                type_move_pressure[TYPE_TANK]
                + type_move_pressure[TYPE_SPAWNER]
                + type_move_pressure[TYPE_ENFORCER],
            )
            move[action_idx, 16] = min(1.0, type_move_pressure[TYPE_ELECTRODE])
            move[action_idx, 17] = min(1.0, type_move_pressure[TYPE_MISSILE] + type_move_pressure[TYPE_SPARK])
            move[action_idx, 18] = nearest_hulk_dist
            move[action_idx, 19] = nearest_electrode_dist
            move[action_idx, 20] = nearest_brain_dist
            move[action_idx, 21] = nearest_spawn_dist
            move[action_idx, 22] = min(1.0, move[action_idx, 6] * (1.0 - aligned_human_penalty))
            move[action_idx, 23] = destructible_count_norm

        fire[action_idx, 2] = min(1.0, best_target)
        fire[action_idx, 3] = min(1.0, priority_target)
        fire[action_idx, 4] = min(1.0, projectile_intercept)
        fire[action_idx, 5] = min(1.0, target_density / 2.5)
        fire[action_idx, 6] = nearest_target_dist
        fire[action_idx, 7] = min(1.0, aligned_human_penalty)
        fire[action_idx, 9] = min(1.0, hulk_blocker)
        if ACTION_FEATURE_DIM >= 24:
            fire[action_idx, 12] = min(1.0, type_fire_score[TYPE_GRUNT])
            fire[action_idx, 13] = min(1.0, type_fire_score[TYPE_BRAIN])
            fire[action_idx, 14] = min(
                1.0,
                max(type_fire_score[TYPE_TANK], type_fire_score[TYPE_SPAWNER], type_fire_score[TYPE_ENFORCER]),
            )
            fire[action_idx, 15] = min(1.0, type_fire_score[TYPE_ENFORCER])
            fire[action_idx, 16] = min(1.0, type_fire_score[TYPE_PROJECTILE])
            fire[action_idx, 17] = min(1.0, max(type_fire_score[TYPE_MISSILE], type_fire_score[TYPE_SPARK]))
            fire[action_idx, 18] = min(1.0, type_fire_score[TYPE_PROG])
            fire[action_idx, 19] = nearest_brain_target_dist
            fire[action_idx, 20] = nearest_spawn_target_dist
            fire[action_idx, 21] = max(0.0, min(1.0, 1.0 - aligned_human_penalty))
            fire[action_idx, 22] = min(1.0, hulk_blocker)
            fire[action_idx, 23] = destructible_count_norm

    return move, fire


def _global_affordances(move_features: np.ndarray) -> np.ndarray:
    """Derive surround/"boxed-in" scalars from the per-direction move rays.

    Returns 4 features (see config.GLOBAL_EXTRA_FEATURES):
      [0] safest_danger   - lowest total danger over the 8 escape directions
      [1] mean_danger     - average total danger over the 8 directions
      [2] boxed_in        - 1 - best escape quality (high => surrounded/trapped)
      [3] safe_dirs_frac  - fraction of directions with low danger
    """
    dirs = move_features[:8]
    enemy_danger = dirs[:, 3]
    proj_danger = dirs[:, 4]
    total_danger = np.clip(enemy_danger + proj_danger, 0.0, 1.0)
    clearance = dirs[:, 2]
    escape_quality = clearance * (1.0 - total_danger)
    safest_danger = float(total_danger.min())
    mean_danger = float(total_danger.mean())
    boxed_in = 1.0 - float(escape_quality.max())
    safe_dirs_frac = float((total_danger < 0.3).sum()) / 8.0
    return np.array([safest_danger, mean_danger, boxed_in, safe_dirs_frac], dtype=np.float32)


class StateProcessor:
    """Convert raw Lua state into tensors for the object-ray policy."""

    def __init__(
        self,
        max_entities: int = None,
        frame_stack: int = None,
    ):
        cfg = CONFIG.model
        self.max_entities = max_entities or cfg.max_entities
        self.frame_stack = frame_stack or cfg.frame_stack
        self.entity_dim = cfg.entity_feature_dim
        self.global_dim = cfg.global_context_dim
        self.action_feature_dim = cfg.action_feature_dim

    def process_frame(self, wire_state: np.ndarray) -> dict[str, np.ndarray]:
        features, mask, num_ents = extract_entities(wire_state, self.max_entities)
        global_ctx = extract_global_context(wire_state)
        # The per-direction move/fire ray features and the surround affordances
        # are now computed on-device in the model (see model.compute_action_features
        # / compute_global_affordances), which moves ~1 ms/frame of scalar Python
        # off the CPU hot path onto the otherwise-idle inference GPU. We emit zero
        # placeholders here so the buffer/wire shapes stay unchanged; the model
        # ignores the stored action features and recomputes them. global_context
        # stays raw (no affordances appended).
        zero_actions = np.zeros((9, self.action_feature_dim), dtype=np.float32)
        return {
            "entity_features": features,
            "entity_mask": mask,
            "global_context": global_ctx,
            "move_action_features": zero_actions,
            "fire_action_features": zero_actions.copy(),
            "num_entities": num_ents,
        }

    def stack_frames(self, frame_list: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
        T = len(frame_list)
        assert T == self.frame_stack, f"Expected {self.frame_stack} frames, got {T}"
        return {
            "entity_features": np.stack([f["entity_features"] for f in frame_list], axis=0),
            "entity_mask": np.stack([f["entity_mask"] for f in frame_list], axis=0),
            "global_context": np.stack([f["global_context"] for f in frame_list], axis=0),
            "move_action_features": np.stack([f["move_action_features"] for f in frame_list], axis=0),
            "fire_action_features": np.stack([f["fire_action_features"] for f in frame_list], axis=0),
        }

    def to_tensors(
        self,
        stacked: dict[str, np.ndarray],
        device: torch.device = None,
    ) -> dict[str, torch.Tensor]:
        if device is None:
            device = torch.device("cpu")
        return {
            "entity_features": torch.from_numpy(stacked["entity_features"]).float().to(device),
            "entity_mask": torch.from_numpy(stacked["entity_mask"]).bool().to(device),
            "global_context": torch.from_numpy(stacked["global_context"]).float().to(device),
            "move_action_features": torch.from_numpy(stacked["move_action_features"]).float().to(device),
            "fire_action_features": torch.from_numpy(stacked["fire_action_features"]).float().to(device),
        }
