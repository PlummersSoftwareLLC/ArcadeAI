#!/usr/bin/env python3
"""Robotron AI v3 - object-ray transformer policy.

The model is built around two observations that matter for Robotron:

1. The Lua side already emits HUD-consistent collision-center positions for
   active objects. Those are best represented as a set, not a flattened lane
   table.
2. The action space is small and geometric. Each move/fire direction can be
   scored with features computed along that direction's ray.

RobotronPPONet keeps the external PPO API intact, but replaces the old generic
set encoder + MLP actor with:

  entity tokens + player/global token -> small Transformer encoder
  temporal fusion over the last frames
  action-conditioned move/fire heads that consume per-direction affordances
"""

from __future__ import annotations

import math
from typing import Optional

import torch
import torch.nn as nn

from .config import GLOBAL_EXTRA_FEATURES
from .state_processor import (
    _REL_POS_X_RANGE,
    _REL_POS_Y_RANGE,
    _AIM_CROSS_WORLD,
    _MOVE_STEP_WORLD,
    _WALL_CLEARANCE_WORLD,
    _DIR8,
    NUM_ENTITY_CLASSES,
    ACTION_FEATURE_DIM,
    _DANGEROUS_TYPES,
    _PROJECTILE_TYPES,
    _STATIC_BLOCKER_TYPES,
    _DESTRUCTIBLE_TYPES,
    _PRIORITY_FIRE_TYPES,
    TYPE_GRUNT,
    TYPE_HUMAN,
    TYPE_HULK,
    TYPE_BRAIN,
    TYPE_TANK,
    TYPE_SPAWNER,
    TYPE_ENFORCER,
    TYPE_PROJECTILE,
    TYPE_ELECTRODE,
    TYPE_MISSILE,
    TYPE_SPARK,
    TYPE_PROG,
)

# ── GPU-side action-feature geometry ─────────────────────────────────────────
# The per-direction move/fire "ray" features used to be built on the CPU in a
# scalar Python double loop (9 directions × N entities) inside
# state_processor.build_action_features — ~1 ms per frame, the single biggest
# preprocessing cost. Every input it needs already lives in the entity_features
# and global_context tensors the GPU receives, so we recompute it here as a
# fully-batched tensor op that runs on whatever device the model is on (the
# otherwise-idle inference GPU). See build_action_features for the reference
# (oracle) implementation that test_smoke checks this against for parity.

_AF_LUT_CACHE: dict = {}

# Columns of the per-type role lookup table (built from the same type sets the
# numpy oracle build_action_features uses, so masks match exactly).
_ROLE_DANGEROUS = 0
_ROLE_PROJECTILE = 1
_ROLE_HUMAN = 2
_ROLE_STATIC = 3
_ROLE_DESTRUCTIBLE = 4
_ROLE_PRIORITY_FIRE = 5
_ROLE_HULK = 6
_ROLE_COLS = 7


def _action_feature_luts(device: torch.device, dtype: torch.dtype):
    """Build (and cache per device/dtype) the small constant lookup tensors."""
    key = (device, dtype)
    cached = _AF_LUT_CACHE.get(key)
    if cached is not None:
        return cached
    dirs = torch.as_tensor(_DIR8, device=device, dtype=dtype)  # (9, 2), idle last
    # 1 for the 8 real directions, 0 for the idle row — zeroes entity-derived
    # columns on the idle action to match the CPU "skip idle" semantics.
    real_dir = torch.tensor(
        [1, 1, 1, 1, 1, 1, 1, 1, 0], device=device, dtype=dtype
    )
    role = torch.zeros(NUM_ENTITY_CLASSES, _ROLE_COLS, device=device, dtype=dtype)
    for t in range(NUM_ENTITY_CLASSES):
        role[t, _ROLE_DANGEROUS] = 1.0 if t in _DANGEROUS_TYPES else 0.0
        role[t, _ROLE_PROJECTILE] = 1.0 if t in _PROJECTILE_TYPES else 0.0
        role[t, _ROLE_HUMAN] = 1.0 if t == TYPE_HUMAN else 0.0
        role[t, _ROLE_STATIC] = 1.0 if t in _STATIC_BLOCKER_TYPES else 0.0
        role[t, _ROLE_DESTRUCTIBLE] = 1.0 if t in _DESTRUCTIBLE_TYPES else 0.0
        role[t, _ROLE_PRIORITY_FIRE] = 1.0 if t in _PRIORITY_FIRE_TYPES else 0.0
        role[t, _ROLE_HULK] = 1.0 if t == TYPE_HULK else 0.0
    priority = [
        1.45 if t in _PROJECTILE_TYPES else (1.25 if t in _PRIORITY_FIRE_TYPES else 1.0)
        for t in range(NUM_ENTITY_CLASSES)
    ]
    priority_lut = torch.tensor(priority, device=device, dtype=dtype)
    out = (dirs, real_dir, role, priority_lut)
    _AF_LUT_CACHE[key] = out
    return out


def compute_action_features(
    entity_features: torch.Tensor,
    entity_mask: torch.Tensor,
    global_context: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Vectorized move/fire action geometry for one frame.

    Args:
        entity_features: (B, N, F) latest-frame entity rows
        entity_mask:     (B, N) bool, True = padding/inactive
        global_context:  (B, G) raw global context (uses px=[:,5], py=[:,6])

    Returns:
        (move_features, fire_features) each (B, 9, ACTION_FEATURE_DIM)
    """
    B, N, F = entity_features.shape
    device = entity_features.device
    dtype = entity_features.dtype
    D = 9
    AF = ACTION_FEATURE_DIM
    RX = _REL_POS_X_RANGE
    RY = _REL_POS_Y_RANGE
    STEP = _MOVE_STEP_WORLD
    AIM2 = _AIM_CROSS_WORLD * 2.0
    WALL = _WALL_CLEARANCE_WORLD
    INF = torch.finfo(dtype).max

    dirs, real_dir, role_lut, priority_lut = _action_feature_luts(device, dtype)
    dir_x = dirs[:, 0]                       # (9,)
    dir_y = dirs[:, 1]
    dirx = dir_x.view(1, D, 1)               # (1,9,1)
    diry = dir_y.view(1, D, 1)

    ef = entity_features
    active = (~entity_mask.bool()).to(dtype)                       # (B,N)

    # Per-entity scalars (B, N)
    dx_w = ef[..., 0] * RX
    dy_w = ef[..., 1] * RY
    dist_norm = ef[..., 20].clamp(0.0, 1.0)
    closeness = 1.0 - dist_norm
    threat = ef[..., 26].clamp(0.0, 1.0)
    ttc = ef[..., 24].clamp(0.0, 1.0)
    cur_dist = torch.hypot(dx_w, dy_w).clamp_min(1.0)

    # Role masks derived from the type one-hot (same source the numpy oracle
    # uses), active-gated so padded slots contribute nothing.
    type_id = ef[..., 6:6 + NUM_ENTITY_CLASSES].argmax(dim=-1)     # (B,N)
    roles = role_lut[type_id] * active.unsqueeze(-1)              # (B,N,7)
    dangerous = roles[..., _ROLE_DANGEROUS]
    projectile = roles[..., _ROLE_PROJECTILE]
    human = roles[..., _ROLE_HUMAN]
    static_blocker = roles[..., _ROLE_STATIC]
    destructible = roles[..., _ROLE_DESTRUCTIBLE]
    priority_fire = roles[..., _ROLE_PRIORITY_FIRE]
    hulk = roles[..., _ROLE_HULK]
    priority_e = priority_lut[type_id]                           # (B,N)
    type_f = type_id.to(dtype)
    type_active = active

    def type_mask(*type_ids: int) -> torch.Tensor:
        mask = torch.zeros_like(type_f)
        for tid in type_ids:
            mask = torch.maximum(mask, (type_id == tid).to(dtype))
        return mask * type_active

    # Broadcast helpers (B,1,N)
    cl = closeness.unsqueeze(1)
    th = threat.unsqueeze(1)
    tt = ttc.unsqueeze(1)
    dn = dist_norm.unsqueeze(1)
    dxw = dx_w.unsqueeze(1)
    dyw = dy_w.unsqueeze(1)
    cur = cur_dist.unsqueeze(1)

    # Direction-dependent geometry (B,9,N)
    next_dist = torch.hypot(dxw - dirx * STEP, dyw - diry * STEP)
    moving_toward = ((cur - next_dist) / STEP).clamp(0.0, 1.0)
    moving_away = ((next_dist - cur) / STEP).clamp(0.0, 1.0)
    forward = dxw * dirx + dyw * diry
    cross = (dxw * diry - dyw * dirx).abs()
    align = (forward / cur).clamp(0.0, 1.0)
    cross_gate = (1.0 - cross / AIM2).clamp(0.0, 1.0)

    dmask = dangerous.unsqueeze(1)
    pmask = projectile.unsqueeze(1)
    bmask = static_blocker.unsqueeze(1)
    humask = human.unsqueeze(1)
    hulkmask = hulk.unsqueeze(1)
    grunt_mask = type_mask(TYPE_GRUNT).unsqueeze(1)
    brain_mask = type_mask(TYPE_BRAIN).unsqueeze(1)
    spawn_mask = type_mask(TYPE_TANK, TYPE_SPAWNER, TYPE_ENFORCER).unsqueeze(1)
    electrode_mask = type_mask(TYPE_ELECTRODE).unsqueeze(1)
    missile_spark_mask = type_mask(TYPE_MISSILE, TYPE_SPARK).unsqueeze(1)
    prog_mask = type_mask(TYPE_PROG).unsqueeze(1)

    # ── Move danger / safety ──
    pressure = th * (0.25 + 0.75 * cl) * (0.2 + 0.8 * moving_toward)
    enemy_danger = (pressure * (dmask * (1.0 - pmask))).sum(-1)
    proj_danger = (pressure * pmask).sum(-1)
    safety = (th * (0.25 + 0.75 * cl) * moving_away * dmask).amax(-1)

    danger_dist = torch.where(dmask > 0, dn.expand(B, D, N), torch.full_like(pressure, INF))
    nearest_danger = danger_dist.amin(-1).clamp(max=1.0)
    proj_ttc = torch.where(pmask > 0, tt.expand(B, D, N), torch.full_like(pressure, INF))
    nearest_proj_ttc = proj_ttc.amin(-1).clamp(max=1.0)

    # ── Blockers ──
    blocker = (0.25 + 0.75 * cl) * (0.25 + 0.75 * moving_toward)
    move_blocker = (blocker * bmask).amax(-1)
    hulk_blocker = (blocker * hulkmask).amax(-1)

    # ── Human pull ──
    fwd_pos = (forward > 0).to(dtype)
    gate_h = humask * fwd_pos
    human_pull = (align * (0.35 + 0.65 * cl) * gate_h).amax(-1)
    aligned_human_penalty = (cross_gate * align * cl * gate_h).amax(-1)

    # ── Fire targeting (destructible only, forward-facing) ──
    tmask = destructible.unsqueeze(1) * fwd_pos
    pri = priority_e.unsqueeze(1)
    score = (align * cross_gate * (0.25 + 0.75 * cl) * pri).clamp(0.0, 1.0) * tmask
    best_target = score.amax(-1)
    target_density = score.sum(-1)
    priority_target = (score * priority_fire.unsqueeze(1)).amax(-1)
    intercept = score * (0.35 + 0.65 * (1.0 - tt))
    projectile_intercept = (intercept * pmask).amax(-1)
    target_dist = torch.where(tmask > 0, dn.expand(B, D, N), torch.full_like(score, INF))
    nearest_target = target_dist.amin(-1).clamp(max=1.0)

    # Per-type ray splits. These deliberately live after the original 12 columns
    # so older feature meanings remain stable while the action heads get a
    # Tempest-like view of which class is responsible for each ray affordance.
    grunt_pressure = (pressure * grunt_mask).sum(-1).clamp(max=1.0)
    hulk_pressure = (pressure * hulkmask).sum(-1).clamp(max=1.0)
    brain_pressure = (pressure * brain_mask).sum(-1).clamp(max=1.0)
    spawn_pressure = (pressure * spawn_mask).sum(-1).clamp(max=1.0)
    electrode_pressure = (pressure * electrode_mask).sum(-1).clamp(max=1.0)
    missile_spark_pressure = (pressure * missile_spark_mask).sum(-1).clamp(max=1.0)

    def nearest(mask: torch.Tensor) -> torch.Tensor:
        dist = torch.where(mask > 0, dn.expand(B, D, N), torch.full_like(dn.expand(B, D, N), INF))
        return dist.amin(-1).clamp(max=1.0)

    nearest_hulk = nearest(hulkmask)
    nearest_electrode = nearest(electrode_mask)
    nearest_brain = nearest(brain_mask)
    nearest_spawn = nearest(spawn_mask)

    grunt_target = (score * grunt_mask).amax(-1).clamp(max=1.0)
    brain_target = (score * brain_mask).amax(-1).clamp(max=1.0)
    spawn_target = (score * spawn_mask).amax(-1).clamp(max=1.0)
    enforcer_target = (score * type_mask(TYPE_ENFORCER).unsqueeze(1)).amax(-1).clamp(max=1.0)
    projectile_target = (score * type_mask(TYPE_PROJECTILE).unsqueeze(1)).amax(-1).clamp(max=1.0)
    missile_spark_target = (score * missile_spark_mask).amax(-1).clamp(max=1.0)
    prog_target = (score * prog_mask).amax(-1).clamp(max=1.0)
    nearest_brain_target = nearest(brain_mask * tmask)
    nearest_spawn_target = nearest(spawn_mask * tmask)
    destructible_active_count = destructible.sum(-1).clamp(max=32.0) / 32.0

    # ── Player-relative constants (B,9) ──
    # Mirror state_processor._safe_float(global_context[5/6], 0.5): px/py default
    # to 0.5 if the wire ever delivers a non-finite value.
    px = torch.nan_to_num(global_context[:, 5], nan=0.5, posinf=0.5, neginf=0.5)
    py = torch.nan_to_num(global_context[:, 6], nan=0.5, posinf=0.5, neginf=0.5)
    px_w = (px * RX).unsqueeze(1)            # (B,1)
    py_w = (py * RY).unsqueeze(1)
    dx9 = dir_x.view(1, D)
    dy9 = dir_y.view(1, D)
    big = torch.full((B, D), INF, device=device, dtype=dtype)
    cx_pos = torch.where(dx9 > 1e-6, (RX - px_w) / torch.where(dx9 > 1e-6, dx9, torch.ones_like(dx9)), big)
    cx_neg = torch.where(dx9 < -1e-6, px_w / torch.where(dx9 < -1e-6, -dx9, torch.ones_like(dx9)), big)
    cy_pos = torch.where(dy9 > 1e-6, (RY - py_w) / torch.where(dy9 > 1e-6, dy9, torch.ones_like(dy9)), big)
    cy_neg = torch.where(dy9 < -1e-6, py_w / torch.where(dy9 < -1e-6, -dy9, torch.ones_like(dy9)), big)
    clearance = torch.minimum(torch.minimum(cx_pos, cx_neg), torch.minimum(cy_pos, cy_neg))
    clearance = torch.where(clearance >= INF, torch.zeros_like(clearance), clearance)
    wall_clearance = (clearance / WALL).clamp(0.0, 1.0)

    cx = (0.5 - px) * RX
    cy = (0.5 - py) * RY
    mag = torch.hypot(cx, cy)
    inv = torch.where(mag > 1e-6, 1.0 / mag, torch.zeros_like(mag))
    center_pull = ((cx * inv).unsqueeze(1) * dx9 + (cy * inv).unsqueeze(1) * dy9).clamp(0.0, 1.0)

    destructible_count_norm = (destructible.sum(-1) / 32.0).clamp(max=1.0)  # (B,)

    idle_flag = (1.0 - real_dir).view(1, D).expand(B, D)
    rd = real_dir.view(1, D)                 # zero entity-derived cols on idle
    dirx_b = dir_x.view(1, D).expand(B, D)
    diry_b = dir_y.view(1, D).expand(B, D)

    move = torch.zeros(B, D, AF, device=device, dtype=dtype)
    move[..., 0] = dirx_b
    move[..., 1] = diry_b
    move[..., 2] = wall_clearance
    move[..., 3] = enemy_danger.clamp(max=1.0) * rd
    move[..., 4] = proj_danger.clamp(max=1.0) * rd
    move[..., 5] = move_blocker.clamp(max=1.0) * rd
    move[..., 6] = human_pull.clamp(max=1.0) * rd
    move[..., 7] = (safety + 0.2 * move[..., 6]).clamp(max=1.0) * rd
    move[..., 8] = nearest_danger * rd
    move[..., 9] = nearest_proj_ttc * rd
    move[..., 10] = center_pull
    move[..., 11] = idle_flag
    if AF >= 24:
        move[..., 12] = grunt_pressure * rd
        move[..., 13] = hulk_pressure * rd
        move[..., 14] = brain_pressure * rd
        move[..., 15] = spawn_pressure * rd
        move[..., 16] = electrode_pressure * rd
        move[..., 17] = missile_spark_pressure * rd
        move[..., 18] = nearest_hulk * rd
        move[..., 19] = nearest_electrode * rd
        move[..., 20] = nearest_brain * rd
        move[..., 21] = nearest_spawn * rd
        move[..., 22] = (human_pull * (1.0 - aligned_human_penalty)).clamp(max=1.0) * rd
        move[..., 23] = destructible_active_count.unsqueeze(1).expand(B, D)

    fire = torch.zeros(B, D, AF, device=device, dtype=dtype)
    fire[..., 0] = dirx_b
    fire[..., 1] = diry_b
    fire[..., 2] = best_target.clamp(max=1.0) * rd
    fire[..., 3] = priority_target.clamp(max=1.0) * rd
    fire[..., 4] = projectile_intercept.clamp(max=1.0) * rd
    fire[..., 5] = (target_density / 2.5).clamp(max=1.0) * rd
    fire[..., 6] = nearest_target * rd
    fire[..., 7] = aligned_human_penalty.clamp(max=1.0) * rd
    fire[..., 8] = destructible_count_norm.unsqueeze(1).expand(B, D)
    fire[..., 9] = hulk_blocker.clamp(max=1.0) * rd
    fire[..., 10] = 1.0
    fire[..., 11] = idle_flag
    if AF >= 24:
        fire[..., 12] = grunt_target * rd
        fire[..., 13] = brain_target * rd
        fire[..., 14] = spawn_target * rd
        fire[..., 15] = enforcer_target * rd
        fire[..., 16] = projectile_target * rd
        fire[..., 17] = missile_spark_target * rd
        fire[..., 18] = prog_target * rd
        fire[..., 19] = nearest_brain_target * rd
        fire[..., 20] = nearest_spawn_target * rd
        fire[..., 21] = (1.0 - aligned_human_penalty).clamp(min=0.0, max=1.0) * rd
        fire[..., 22] = hulk_blocker.clamp(max=1.0) * rd
        fire[..., 23] = destructible_active_count.unsqueeze(1).expand(B, D)

    return move, fire


def compute_global_affordances(move_features: torch.Tensor) -> torch.Tensor:
    """Surround/"boxed-in" scalars from the 8 real move directions. (B,9,AF)->(B,4)."""
    dirs = move_features[:, :8]
    enemy = dirs[..., 3]
    proj = dirs[..., 4]
    total = (enemy + proj).clamp(0.0, 1.0)
    clearance = dirs[..., 2]
    escape = clearance * (1.0 - total)
    safest = total.amin(dim=-1)
    mean_danger = total.mean(dim=-1)
    boxed_in = 1.0 - escape.amax(dim=-1)
    safe_dirs_frac = (total < 0.3).to(move_features.dtype).mean(dim=-1)
    return torch.stack([safest, mean_danger, boxed_in, safe_dirs_frac], dim=-1)


class ActionConditionedHead(nn.Module):
    """Score each discrete action from shared state and per-action features.

    Optionally consumes a per-action context vector (e.g. the output of
    DirectionCrossAttention) so each action's logit can depend on object-specific
    evidence gathered for that direction, not just the globally pooled scene.
    """

    def __init__(
        self,
        state_dim: int,
        action_count: int,
        action_feature_dim: int,
        action_context_dim: int = 0,
        action_embed_dim: int = 32,
        hidden_dim: int = 128,
    ):
        super().__init__()
        self.action_count = int(action_count)
        self.action_feature_dim = int(action_feature_dim)
        self.action_context_dim = int(action_context_dim)
        self.action_embedding = nn.Embedding(self.action_count, action_embed_dim)
        in_dim = state_dim + action_feature_dim + action_embed_dim + self.action_context_dim
        self.scorer = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self,
        state: torch.Tensor,
        action_features: torch.Tensor,
        action_context: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Return logits with shape (B, action_count)."""
        B = state.shape[0]
        if action_features.dim() != 3:
            raise ValueError("action_features must be (B, A, F)")
        if action_features.shape[1] != self.action_count:
            raise ValueError(
                f"expected {self.action_count} action rows, got {action_features.shape[1]}"
            )

        action_ids = torch.arange(self.action_count, device=state.device)
        action_emb = self.action_embedding(action_ids).unsqueeze(0).expand(B, -1, -1)
        state_expanded = state.unsqueeze(1).expand(-1, self.action_count, -1)
        parts = [state_expanded, action_features, action_emb]
        if self.action_context_dim > 0:
            if action_context is None:
                raise ValueError("action_context required when action_context_dim > 0")
            parts.append(action_context)
        x = torch.cat(parts, dim=-1)
        return self.scorer(x).squeeze(-1)


class DirectionCrossAttention(nn.Module):
    """Per-direction cross-attention over the encoded entity tokens.

    Mirrors the Tempest lane->enemy cross-attention breakthrough: each action
    candidate (here a move/fire direction) is a query token that attends to the
    set of encoded objects and gathers the entities relevant to it. The
    per-direction context it returns lets the action head reason about what is
    actually in/along each candidate direction from the LEARNED object
    representations, instead of depending solely on the globally pooled scene
    vector plus the hand-engineered ray affordances.

    Each direction's query is a learned embedding added to a projection of that
    direction's hand-engineered ray features, so attention starts from a
    geometry-aware prior and refines it with object evidence.
    """

    def __init__(
        self,
        num_dirs: int,
        action_feature_dim: int,
        embed_dim: int,
        num_heads: int,
        attention_kind: str = "move",
        geometry_bias: bool = True,
        geometry_bias_strength: float = 1.25,
    ):
        super().__init__()
        self.num_dirs = int(num_dirs)
        self.embed_dim = int(embed_dim)
        self.out_dim = int(embed_dim)
        self.num_heads = int(num_heads)
        self.attention_kind = str(attention_kind)
        self.geometry_bias = bool(geometry_bias)
        self.geometry_bias_strength = float(geometry_bias_strength)
        self.dir_embedding = nn.Embedding(self.num_dirs, embed_dim)
        self.feature_proj = nn.Linear(action_feature_dim, embed_dim)
        self.query_norm = nn.LayerNorm(embed_dim)
        self.attn = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True)
        self.out_norm = nn.LayerNorm(embed_dim)

    def _geometry_attention_bias(
        self,
        entity_features: Optional[torch.Tensor],
        action_features: torch.Tensor,
    ) -> Optional[torch.Tensor]:
        """Parameter-free object relevance prior, shape (B, directions, objects)."""
        if (
            entity_features is None
            or not self.geometry_bias
            or self.geometry_bias_strength <= 0.0
            or entity_features.dim() != 3
        ):
            return None
        B, D, _AF = action_features.shape
        if entity_features.shape[0] != B:
            return None

        ef = entity_features.to(dtype=action_features.dtype, device=action_features.device)
        dir_x = action_features[..., 0]
        dir_y = action_features[..., 1]
        real_dir = ((dir_x.abs() + dir_y.abs()) > 1e-6).to(action_features.dtype)

        dx_w = ef[..., 0] * _REL_POS_X_RANGE
        dy_w = ef[..., 1] * _REL_POS_Y_RANGE
        dist = torch.hypot(dx_w, dy_w).clamp_min(1.0)
        dist_norm = ef[..., 20].clamp(0.0, 1.0) if ef.shape[-1] > 20 else torch.ones_like(dist)
        closeness = 1.0 - dist_norm

        dirx = dir_x.unsqueeze(-1)
        diry = dir_y.unsqueeze(-1)
        dx = dx_w.unsqueeze(1)
        dy = dy_w.unsqueeze(1)
        inv_dist = (1.0 / dist).unsqueeze(1)
        forward = (dx * dirx + dy * diry) * inv_dist
        cross = (dx * diry - dy * dirx).abs()

        if self.attention_kind == "fire":
            destructible = ef[..., 31].clamp(0.0, 1.0) if ef.shape[-1] > 31 else torch.ones_like(dist)
            cross_gate = (1.0 - cross / (_AIM_CROSS_WORLD * 2.0)).clamp(0.0, 1.0)
            relevance = (
                forward.clamp(0.0, 1.0)
                * cross_gate
                * (0.25 + 0.75 * closeness.unsqueeze(1))
                * (0.35 + 0.65 * destructible.unsqueeze(1))
            )
        else:
            danger = ef[..., 27].clamp(0.0, 1.0) if ef.shape[-1] > 27 else torch.zeros_like(dist)
            human = ef[..., 29].clamp(0.0, 1.0) if ef.shape[-1] > 29 else torch.zeros_like(dist)
            static = ef[..., 30].clamp(0.0, 1.0) if ef.shape[-1] > 30 else torch.zeros_like(dist)
            role = (danger + human + static).clamp(0.0, 1.0)
            axis_gate = (1.0 - cross / (_AIM_CROSS_WORLD * 6.0)).clamp(0.0, 1.0)
            relevance = (
                forward.abs().clamp(0.0, 1.0)
                * (0.5 + 0.5 * axis_gate)
                * (0.25 + 0.75 * closeness.unsqueeze(1))
                * (0.35 + 0.65 * role.unsqueeze(1))
            )

        return self.geometry_bias_strength * relevance * real_dir.unsqueeze(-1)

    def forward(
        self,
        object_repr: torch.Tensor,       # (B, N, E)
        object_mask: torch.Tensor,       # (B, N) bool, True = padding/inactive
        action_features: torch.Tensor,   # (B, D, AF)
        entity_features: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Return per-direction context, shape (B, num_dirs, embed_dim)."""
        B, N, _ = object_repr.shape
        dir_ids = torch.arange(self.num_dirs, device=object_repr.device)
        q = self.dir_embedding(dir_ids).unsqueeze(0).expand(B, -1, -1)
        q = self.query_norm(q + self.feature_proj(action_features))

        # Guard rows where every key is padding (no active objects): an all-True
        # key_padding_mask makes the attention softmax operate over all -inf and
        # produce NaN. Unmask one slot for those rows, then zero their output.
        all_pad = object_mask.all(dim=1)
        key_mask = object_mask
        any_all_pad = bool(all_pad.any())
        if any_all_pad:
            key_mask = object_mask.clone()
            key_mask[all_pad, 0] = False

        attn_bias = self._geometry_attention_bias(entity_features, action_features)
        if attn_bias is None or attn_bias.shape != (B, self.num_dirs, N):
            attn_bias = torch.zeros(B, self.num_dirs, N, device=q.device, dtype=q.dtype)
        else:
            attn_bias = attn_bias.to(device=q.device, dtype=q.dtype)
        attn_mask = attn_bias.masked_fill(
            key_mask.unsqueeze(1),
            torch.finfo(q.dtype).min,
        ).repeat_interleave(self.num_heads, dim=0)

        attn_out, _ = self.attn(
            q, object_repr, object_repr,
            attn_mask=attn_mask,
            need_weights=False,
        )
        ctx = self.out_norm(q + attn_out)
        if any_all_pad:
            ctx = ctx.masked_fill(all_pad.view(B, 1, 1), 0.0)
        return ctx


class RobotronPPONet(nn.Module):
    """Compact PPO policy/value network for object-centric Robotron state."""

    def __init__(
        self,
        entity_feature_dim: int = 32,
        max_entities: int = 96,
        embed_dim: int = 160,
        transformer_layers: int = 2,
        num_heads: int = 4,
        global_context_dim: int = 40,
        action_feature_dim: int = ACTION_FEATURE_DIM,
        frame_stack: int = 2,
        fusion_hidden: int = 320,
        fusion_layers: int = 2,
        num_move_actions: int = 9,
        num_fire_actions: int = 9,
        use_auxiliary_head: bool = False,
        auxiliary_predict_steps: Optional[list[int]] = None,
        dropout: float = 0.0,
        use_direction_attention: bool = True,
        attention_geometry_bias: bool = True,
        attention_geometry_bias_strength: float = 1.25,
    ):
        super().__init__()
        del auxiliary_predict_steps

        self.max_entities = int(max_entities)
        self.entity_feature_dim = int(entity_feature_dim)
        self.embed_dim = int(embed_dim)
        self.frame_stack = int(frame_stack)
        self.global_context_dim = int(global_context_dim)
        self.action_feature_dim = int(action_feature_dim)
        self.num_move_actions = int(num_move_actions)
        self.num_fire_actions = int(num_fire_actions)
        self.use_auxiliary_head = bool(use_auxiliary_head)
        self.use_direction_attention = bool(use_direction_attention)
        self.attention_geometry_bias = bool(attention_geometry_bias)
        self.attention_geometry_bias_strength = float(attention_geometry_bias_strength)

        self.entity_proj = nn.Sequential(
            nn.Linear(self.entity_feature_dim, self.embed_dim),
            nn.LayerNorm(self.embed_dim),
            nn.GELU(),
            nn.Linear(self.embed_dim, self.embed_dim),
        )
        self.global_token = nn.Sequential(
            nn.Linear(self.global_context_dim + GLOBAL_EXTRA_FEATURES, self.embed_dim),
            nn.LayerNorm(self.embed_dim),
            nn.GELU(),
            nn.Linear(self.embed_dim, self.embed_dim),
        )

        enc_layer = nn.TransformerEncoderLayer(
            d_model=self.embed_dim,
            nhead=num_heads,
            dim_feedforward=self.embed_dim * 2,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.entity_encoder = nn.TransformerEncoder(
            enc_layer,
            num_layers=transformer_layers,
            enable_nested_tensor=False,
        )

        self.frame_fusion = nn.Sequential(
            nn.Linear(self.embed_dim * 3, self.embed_dim),
            nn.LayerNorm(self.embed_dim),
            nn.GELU(),
        )

        # Per-slot temporal fusion: combine each object's embedding across the
        # frame stack BEFORE the transformer. Because the Lua side keeps stable
        # slot assignments, slot i is the same object over time, so this MLP
        # learns per-object motion/identity instead of pooling whole frames.
        self.temporal_fusion = nn.Sequential(
            nn.Linear(self.frame_stack * self.embed_dim, self.embed_dim),
            nn.LayerNorm(self.embed_dim),
            nn.GELU(),
        )

        fusion = []
        in_dim = self.embed_dim
        for _ in range(fusion_layers):
            fusion.extend([
                nn.Linear(in_dim, fusion_hidden),
                nn.LayerNorm(fusion_hidden),
                nn.GELU(),
            ])
            in_dim = fusion_hidden
        self.fusion = nn.Sequential(*fusion)

        self.move_head = ActionConditionedHead(
            state_dim=fusion_hidden,
            action_count=self.num_move_actions,
            action_feature_dim=self.action_feature_dim,
            action_context_dim=(self.embed_dim if self.use_direction_attention else 0),
            hidden_dim=128,
        )
        self.fire_head = ActionConditionedHead(
            state_dim=fusion_hidden,
            action_count=self.num_fire_actions,
            action_feature_dim=self.action_feature_dim,
            action_context_dim=(self.embed_dim if self.use_direction_attention else 0),
            hidden_dim=128,
        )
        if self.use_direction_attention:
            self.move_dir_attn = DirectionCrossAttention(
                num_dirs=self.num_move_actions,
                action_feature_dim=self.action_feature_dim,
                embed_dim=self.embed_dim,
                num_heads=num_heads,
                attention_kind="move",
                geometry_bias=self.attention_geometry_bias,
                geometry_bias_strength=self.attention_geometry_bias_strength,
            )
            self.fire_dir_attn = DirectionCrossAttention(
                num_dirs=self.num_fire_actions,
                action_feature_dim=self.action_feature_dim,
                embed_dim=self.embed_dim,
                num_heads=num_heads,
                attention_kind="fire",
                geometry_bias=self.attention_geometry_bias,
                geometry_bias_strength=self.attention_geometry_bias_strength,
            )
        self.value_head = nn.Sequential(
            nn.Linear(fusion_hidden, 160),
            nn.LayerNorm(160),
            nn.GELU(),
            nn.Linear(160, 1),
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=math.sqrt(2))
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

        for head in (self.move_head, self.fire_head):
            final = head.scorer[-1]
            nn.init.orthogonal_(final.weight, gain=0.01)
            nn.init.zeros_(final.bias)
        nn.init.orthogonal_(self.value_head[-1].weight, gain=1.0)
        nn.init.zeros_(self.value_head[-1].bias)

    def _ensure_temporal_inputs(
        self,
        entity_features: torch.Tensor,
        entity_mask: torch.Tensor,
        global_context: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        B = entity_features.shape[0]
        T = self.frame_stack

        if entity_features.dim() == 3:
            entity_features = entity_features.unsqueeze(1).expand(B, T, -1, -1)
        if entity_mask.dim() == 2:
            entity_mask = entity_mask.unsqueeze(1).expand(B, T, -1)
        if global_context.dim() == 2:
            global_context = global_context.unsqueeze(1).expand(B, T, -1)

        if entity_features.shape[1] != T:
            raise ValueError(f"expected frame_stack={T}, got {entity_features.shape[1]}")

        return entity_features, entity_mask, global_context

    def _encode_frames(
        self,
        entity_features: torch.Tensor,
        entity_mask: torch.Tensor,
        global_latest: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Encode the frame stack into a scene vector plus per-object tokens.

        Each object's per-frame embedding is fused along the time axis first
        (per-slot temporal tracking), then the resulting current-scene tokens go
        through the transformer once. This is both cheaper (one transformer pass
        per sample instead of frame_stack passes) and richer, since per-object
        motion is preserved instead of being averaged away by per-frame pooling.

        global_latest is the already-augmented (raw + affordances) current-frame
        global context, shape (B, global_context_dim + GLOBAL_EXTRA_FEATURES).

        Returns (scene, object_repr, latest_mask):
          scene:       (B, embed_dim) pooled scene vector for the value head /
                       fusion trunk.
          object_repr: (B, N, embed_dim) per-object encoded tokens, consumed by
                       the direction cross-attention.
          latest_mask: (B, N) bool padding mask for object_repr.
        """
        B, T, N, F = entity_features.shape

        # Project every frame's entities, then zero padded slots so absent
        # objects contribute nothing to the temporal fusion.
        ent = self.entity_proj(entity_features.reshape(B * T, N, F))
        ent = ent.reshape(B, T, N, self.embed_dim)
        active_all = (~entity_mask.bool()).unsqueeze(-1).to(ent.dtype)
        ent = ent * active_all

        # Per-slot temporal fusion: (B, T, N, E) -> (B, N, T*E) -> (B, N, E)
        ent = ent.permute(0, 2, 1, 3).reshape(B, N, T * self.embed_dim)
        ent_tokens = self.temporal_fusion(ent)

        # Encode the current scene once using the latest-frame mask + globals.
        latest_mask = entity_mask[:, -1].bool()
        player_token = self.global_token(global_latest).unsqueeze(1)
        tokens = torch.cat([player_token, ent_tokens], dim=1)
        token_mask = torch.cat(
            [
                torch.zeros(B, 1, dtype=torch.bool, device=latest_mask.device),
                latest_mask,
            ],
            dim=1,
        )

        encoded = self.entity_encoder(tokens, src_key_padding_mask=token_mask)
        player_repr = encoded[:, 0]
        object_repr = encoded[:, 1:]

        active = (~latest_mask).unsqueeze(-1).to(object_repr.dtype)
        active_count = active.sum(dim=1).clamp_min(1.0)
        mean_repr = (object_repr * active).sum(dim=1) / active_count

        very_neg = torch.finfo(object_repr.dtype).min
        max_src = object_repr.masked_fill(latest_mask.unsqueeze(-1), very_neg)
        max_repr = max_src.max(dim=1).values
        no_objects = latest_mask.all(dim=1)
        if bool(no_objects.any()):
            max_repr = max_repr.clone()
            max_repr[no_objects] = 0.0

        scene = self.frame_fusion(torch.cat([player_repr, mean_repr, max_repr], dim=-1))
        return scene, object_repr, latest_mask

    def forward(
        self,
        entity_features: torch.Tensor,
        entity_mask: torch.Tensor,
        global_context: torch.Tensor,
        move_action_features: Optional[torch.Tensor] = None,
        fire_action_features: Optional[torch.Tensor] = None,
    ) -> dict[str, torch.Tensor]:
        """Produce move/fire logits and value estimate.

        move_action_features / fire_action_features are accepted for API
        compatibility but ignored: the per-direction action geometry and the
        surround affordances are now computed on-device from entity_features +
        global_context (see compute_action_features), which keeps that work on
        the otherwise-idle inference GPU instead of the CPU hot path.
        """
        del move_action_features, fire_action_features

        entity_features, entity_mask, global_context = self._ensure_temporal_inputs(
            entity_features,
            entity_mask,
            global_context,
        )

        # Latest-frame action geometry + surround affordances, on-device.
        ef_latest = entity_features[:, -1]
        mask_latest = entity_mask[:, -1]
        gc_latest = global_context[:, -1]
        move_current, fire_current = compute_action_features(ef_latest, mask_latest, gc_latest)
        affordances = compute_global_affordances(move_current)
        global_latest = torch.cat([gc_latest, affordances], dim=-1)

        scene, object_repr, object_mask = self._encode_frames(
            entity_features, entity_mask, global_latest
        )
        fused = self.fusion(scene)

        if self.use_direction_attention:
            move_ctx = self.move_dir_attn(object_repr, object_mask, move_current, ef_latest)
            fire_ctx = self.fire_dir_attn(object_repr, object_mask, fire_current, ef_latest)
        else:
            move_ctx = None
            fire_ctx = None

        return {
            "move_logits": self.move_head(fused, move_current, move_ctx),
            "fire_logits": self.fire_head(fused, fire_current, fire_ctx),
            "value": self.value_head(fused).squeeze(-1),
        }

    def get_action_and_value(
        self,
        entity_features: torch.Tensor,
        entity_mask: torch.Tensor,
        global_context: torch.Tensor,
        move_action_features: Optional[torch.Tensor] = None,
        fire_action_features: Optional[torch.Tensor] = None,
        move_action: Optional[torch.Tensor] = None,
        fire_action: Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Sample or evaluate factored move/fire actions for PPO."""
        out = self.forward(
            entity_features,
            entity_mask,
            global_context,
            move_action_features,
            fire_action_features,
        )

        move_logits = out["move_logits"].clamp(-50.0, 50.0)
        fire_logits = out["fire_logits"].clamp(-50.0, 50.0)
        if torch.isnan(move_logits).any() or torch.isinf(move_logits).any():
            move_logits = torch.zeros_like(move_logits)
        if torch.isnan(fire_logits).any() or torch.isinf(fire_logits).any():
            fire_logits = torch.zeros_like(fire_logits)

        move_dist = torch.distributions.Categorical(logits=move_logits)
        fire_dist = torch.distributions.Categorical(logits=fire_logits)

        if move_action is None:
            move_action = move_dist.sample()
        if fire_action is None:
            fire_action = fire_dist.sample()

        log_prob = move_dist.log_prob(move_action) + fire_dist.log_prob(fire_action)
        entropy = move_dist.entropy() + fire_dist.entropy()

        return move_action, fire_action, log_prob, entropy, out["value"]

    def get_value(
        self,
        entity_features: torch.Tensor,
        entity_mask: torch.Tensor,
        global_context: torch.Tensor,
        move_action_features: Optional[torch.Tensor] = None,
        fire_action_features: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Return only the value estimate for bootstrapping."""
        out = self.forward(
            entity_features,
            entity_mask,
            global_context,
            move_action_features,
            fire_action_features,
        )
        v = out["value"]
        if torch.isnan(v).any():
            v = torch.zeros_like(v)
        return v
