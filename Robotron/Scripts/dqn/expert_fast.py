"""Fast expert action for the DQN path.

The shared ``v3.expert.get_expert_action`` builds the full ``(128, 32)`` entity
token tensor via ``extract_entities``/``_collect_entity_slots`` — one-hot type
channels, box dims, threat/ttc/closest-pass trigonometry — and then throws all
of it away inside ``_get_active_entities``, which only keeps
``(dx, dy, vx, vy, dist_norm, type_id)`` per active entity.

That tensor exists for v3's *model* token input. The DQN model uses lane slices
instead, so for the DQN expert path the whole tensor is dead weight (~86% of the
0.72 ms/call cost). This module reads the wire role-pools directly into the six
fields the expert actually consumes, then defers to the **unchanged** shared
strategic-decision logic. Output is byte-identical (and identically ordered) to
``get_expert_action`` — verified by ``dqn.test_smoke``.

No v3 code is modified; only public/module constants are imported.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from v3.state_processor import (
    _POOLS_START,
    ENTITY_POOL_DEFS,
    NUM_ENTITY_CLASSES,
    _REL_POS_X_RANGE,
    _REL_POS_Y_RANGE,
    _POS_MAX_DIAG,
    _slot_type,
)
from v3.expert import TYPE_MISSILE, _get_strategic_expert_action

_PROJECTILE = "projectile"
_VEL_POOLS = frozenset({"projectile", "danger", "human"})
_TYPE_HI = NUM_ENTITY_CLASSES - 1


def _clamp11(v: float) -> float:
    return -1.0 if v < -1.0 else (1.0 if v > 1.0 else v)


def _active_entities_fast(wire_state: np.ndarray):
    """Direct wire-pool -> expert entity list.

    Mirrors the active-slot path of ``_collect_entity_slots`` +
    ``extract_entities`` + ``_get_active_entities`` exactly, but only for the
    fields the expert reads. Entities are emitted in ascending global-index
    order (pool order, then slot), matching the shared path.
    """
    pools_data = wire_state[_POOLS_START:]
    pools_len = pools_data.shape[0]
    pool_offset = 0
    entities = []

    for pool_name, max_slots, feat_per_slot in ENTITY_POOL_DEFS:
        slot_start = pool_offset + 1
        slot_end = slot_start + max_slots * feat_per_slot
        if slot_end > pools_len:
            pool_offset += 1 + max_slots * feat_per_slot
            continue

        raw = pools_data[slot_start:slot_end].reshape(max_slots, feat_per_slot)
        is_vel = pool_name in _VEL_POOLS and feat_per_slot > 5
        is_proj = pool_name == _PROJECTILE
        for slot_idx in range(max_slots):
            slot = raw[slot_idx]
            if slot[0] <= 0.5 or not np.isfinite(slot).all():
                continue

            type_id = _slot_type(pool_name, slot)
            dx = _clamp11(float(slot[1])) if feat_per_slot > 1 else 0.0
            dy = _clamp11(float(slot[2])) if feat_per_slot > 2 else 0.0

            vx = 0.0
            vy = 0.0
            if is_vel:
                vx = _clamp11(float(slot[4]))
                vy = _clamp11(float(slot[5]))

            if is_proj:
                subtype = float(slot[10]) if feat_per_slot > 10 else 0.0
                if subtype >= 0.5:
                    type_id = TYPE_MISSILE

            type_id = 0 if type_id < 0 else (_TYPE_HI if type_id > _TYPE_HI else int(type_id))

            world_dx = dx * _REL_POS_X_RANGE
            world_dy = dy * _REL_POS_Y_RANGE
            dist_norm = math.hypot(world_dx, world_dy) / _POS_MAX_DIAG
            entities.append((dx, dy, vx, vy, dist_norm, type_id))

        pool_offset += 1 + max_slots * feat_per_slot

    return entities


def fast_expert_action(
    wire_state: np.ndarray,
    wave_number: int = 1,
    locked_fire: Optional[int] = None,
) -> tuple[int, int]:
    """Drop-in replacement for ``v3.expert.get_expert_action`` (DQN path)."""
    entities = _active_entities_fast(wire_state)
    px = float(wire_state[5]) if wire_state.size > 6 else 0.5
    py = float(wire_state[6]) if wire_state.size > 6 else 0.5
    return _get_strategic_expert_action(
        entities, px, py, wave_number, locked_fire=locked_fire
    )
