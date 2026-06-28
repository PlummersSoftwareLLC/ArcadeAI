#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN MODEL                                                                                    ||
# ||                                                                                                              ||
# ||  Rainbow-lite network refactored for Robotron's twin-stick control:                                          ||
# ||    • C51 distributional value estimation                                                                     ||
# ||    • JOINT 81-action head for coupled move/fire values                                                        ||
# ||    • Auxiliary BRANCHING heads for move/fire imitation diagnostics                                             ||
# ||    • Self-attention over a 96-row role-aware object list                                                      ||
# ||    • Dueling architecture                                                                                     ||
# ==================================================================================================================
"""Model + action helpers for the Robotron DQN.

The state vector is the model slice (18 core game/player scalars + 22
ELIST/level-state scalars + 16 directional lane-density scalars + 3 nearest
destructible-target scalars + 16 nearest typed-object scalars + 96 role-aware
object rows × 21). When frame stacking is enabled, only the compact
global/lane/target/nearest-type slice from each frame is concatenated into the
raw trunk. The current-frame object list is encoded by attention.
"""

if __name__ == "__main__":
    print("This is not the main application, run 'main.py' instead")
    exit(1)

import math
import random
from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from .config import RL_CONFIG
except ImportError:
    from config import RL_CONFIG


# ── Device selection ────────────────────────────────────────────────────────
def _cuda_device(index_hint: int) -> torch.device:
    n = torch.cuda.device_count()
    if n <= 0:
        return torch.device("cpu")
    idx = int(index_hint)
    if idx < 0 or idx >= n:
        idx = 0
    return torch.device(f"cuda:{idx}")


if torch.cuda.is_available():
    device = _cuda_device(getattr(RL_CONFIG, "train_cuda_device_index", 0))
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    try:
        torch.set_float32_matmul_precision("high")
    except Exception:
        pass
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")


# ── Action helpers ──────────────────────────────────────────────────────────
NUM_MOVE = RL_CONFIG.num_move_actions      # 9  (0..7 = direction, 8 = idle)
NUM_FIRE = RL_CONFIG.num_fire_actions      # 9
NUM_JOINT = RL_CONFIG.num_joint_actions    # 81
IDLE_INDEX = 8                             # action index meaning "no input" on a stick


def combine_action(move: int, fire: int) -> int:
    """Combine factored (move, fire) indices into a single joint index 0..80."""
    m = max(0, min(NUM_MOVE - 1, int(move)))
    f = max(0, min(NUM_FIRE - 1, int(fire)))
    return m * NUM_FIRE + f


def split_joint_action(idx: int) -> Tuple[int, int]:
    """Split a joint index 0..80 back into (move, fire) indices."""
    idx = max(0, min(NUM_JOINT - 1, int(idx)))
    return idx // NUM_FIRE, idx % NUM_FIRE


def action_index_to_wire_dir(idx: int) -> int:
    """Map a model action index (0..8) to a wire direction byte.

    Directions 0..7 pass through; idle (index 8) maps to -1 (neutral stick).
    """
    idx = int(idx)
    return idx if 0 <= idx < IDLE_INDEX else -1


def wire_dir_to_action_index(direction: int) -> int:
    """Inverse of :func:`action_index_to_wire_dir` (neutral -1 → idle index 8)."""
    d = int(direction)
    return d if 0 <= d < IDLE_INDEX else IDLE_INDEX


# ── Lane Self-Attention Encoder ─────────────────────────────────────────────
class LaneSelfAttentionEncoder(nn.Module):
    """Multi-head self-attention over the 8 directional lane tokens.

    The Lua client already bins enemies/humans/projectiles into 8 directional
    lanes, so we use *self*-attention (lanes attend to each other) rather than
    cross-attention.  All 8 lanes are always present — empty directions simply
    carry zeroed features plus their sin/cos identity — so no masking is needed.
    """

    def __init__(self, lane_features: int, embed_dim: int, num_heads: int):
        super().__init__()
        self.embed = nn.Linear(lane_features, embed_dim)
        self.norm = nn.LayerNorm(embed_dim)
        self.attn = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True)
        self.attn_norm = nn.LayerNorm(embed_dim)
        self.out_dim = embed_dim

    def forward(self, lane_tokens: torch.Tensor) -> torch.Tensor:
        """lane_tokens: (B, 8, lane_features) → (B, embed_dim)."""
        x = self.norm(self.embed(lane_tokens))          # (B, 8, D)
        attn_out, _ = self.attn(x, x, x)                # (B, 8, D)
        enriched = self.attn_norm(x + attn_out)         # residual + norm
        return enriched.mean(dim=1)                     # (B, D)


class ObjectSelfAttentionEncoder(nn.Module):
    """Self-attention over role-aware object rows with a presence mask."""

    def __init__(self, token_features: int, embed_dim: int, num_heads: int):
        super().__init__()
        self.embed = nn.Linear(token_features, embed_dim)
        self.norm = nn.LayerNorm(embed_dim)
        self.attn = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True)
        self.attn_norm = nn.LayerNorm(embed_dim)
        self.out_dim = embed_dim

    def encode_tokens(self, tokens: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        present = tokens[..., 0] > 0.5
        key_padding_mask = ~present
        all_empty = key_padding_mask.all(dim=1)
        if all_empty.any():
            key_padding_mask = key_padding_mask.clone()
            key_padding_mask[all_empty, 0] = False
        x = self.norm(self.embed(tokens))
        attn_out, _ = self.attn(x, x, x, key_padding_mask=key_padding_mask)
        enriched = self.attn_norm(x + attn_out)
        return enriched, present

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        enriched, present = self.encode_tokens(tokens)
        weights = present.float().unsqueeze(-1)
        pooled = (enriched * weights).sum(dim=1)
        denom = weights.sum(dim=1).clamp_min(1.0)
        return pooled / denom


class DirectionalObjectAttention(nn.Module):
    """Action-direction queries attending over encoded object rows.

    The learned query is seeded with a fixed controller-direction embedding.
    A lightweight additive attention bias gives the model the same kind of
    geometry prior that helped Tempest: move actions inspect nearby hazards in
    that direction, while fire actions inspect target-like objects along the
    firing ray. The bias is only a prior; the attention/value projections remain
    fully learned.
    """

    def __init__(
        self,
        object_dim: int,
        num_actions: int,
        num_heads: int,
        mode: str,
        geometry_bias: bool = True,
        geometry_bias_strength: float = 1.75,
        fire_alignment_width: float = 0.075,
    ):
        super().__init__()
        self.num_actions = int(num_actions)
        self.object_dim = int(object_dim)
        self.num_heads = int(num_heads)
        self.mode = str(mode)
        self.geometry_bias = bool(geometry_bias)
        self.geometry_bias_strength = float(geometry_bias_strength)
        self.fire_alignment_width = float(fire_alignment_width)

        dirs = torch.tensor([
            [0.0, -1.0], [1.0, -1.0], [1.0, 0.0], [1.0, 1.0],
            [0.0, 1.0], [-1.0, 1.0], [-1.0, 0.0], [-1.0, -1.0],
            [0.0, 0.0],
        ], dtype=torch.float32)
        dirs = dirs / dirs.norm(dim=1, keepdim=True).clamp_min(1.0)
        idle = torch.zeros((dirs.shape[0], 1), dtype=torch.float32)
        idle[IDLE_INDEX, 0] = 1.0
        action_features = torch.cat([dirs, idle], dim=1)
        self.register_buffer("action_dirs", dirs[:self.num_actions], persistent=False)
        self.register_buffer("action_features", action_features[:self.num_actions], persistent=False)

        self.dir_proj = nn.Linear(3, self.object_dim)
        self.dir_embedding = nn.Embedding(self.num_actions, self.object_dim)
        self.query_norm = nn.LayerNorm(self.object_dim)
        self.attn = nn.MultiheadAttention(self.object_dim, num_heads, batch_first=True)
        self.out_norm = nn.LayerNorm(self.object_dim)

    def _geometry_attn_mask(
        self,
        object_tokens: torch.Tensor,
        object_present: torch.Tensor,
    ) -> torch.Tensor | None:
        if not self.geometry_bias or object_tokens is None:
            return None

        present = object_present.bool()
        B, rows, feats = object_tokens.shape
        if rows <= 0:
            return None

        def col(idx: int, default: float = 0.0) -> torch.Tensor:
            if feats > idx:
                return object_tokens[:, :, idx]
            return torch.full((B, rows), float(default), device=object_tokens.device, dtype=object_tokens.dtype)

        xy = object_tokens[:, :, 1:3]
        xy_norm = xy.norm(dim=-1, keepdim=True).clamp_min(1e-6)
        obj_dir = xy / xy_norm
        action_dirs = self.action_dirs.to(device=object_tokens.device, dtype=object_tokens.dtype)
        align = torch.einsum("ad,bnd->ban", action_dirs, obj_dir)
        forward = align.clamp_min(0.0)

        dist = col(3, 1.0).clamp(0.0, 1.0)
        threat = col(6, 0.0).clamp(0.0, 1.0)
        ttc = col(8, 1.0).clamp(0.0, 1.0)
        destructible = col(12, 0.0).clamp(0.0, 1.0)
        blocker = col(13, 0.0).clamp(0.0, 1.0)
        rescue = col(14, 0.0).clamp(0.0, 1.0)
        projectile = col(15, 0.0).clamp(0.0, 1.0)

        closeness = (1.0 - dist).unsqueeze(1)
        imminent = (1.0 - ttc).unsqueeze(1)
        threat_u = threat.unsqueeze(1)
        projectile_u = projectile.unsqueeze(1)
        blocker_u = blocker.unsqueeze(1)
        destructible_u = destructible.unsqueeze(1)
        rescue_u = rescue.unsqueeze(1)

        strength = torch.as_tensor(self.geometry_bias_strength, device=object_tokens.device, dtype=object_tokens.dtype)
        if self.mode == "move":
            # Humans are present in the same object list but should not become
            # movement hazards. Projectiles, electrodes, hulks/blockers, and
            # high-threat enemies get the strongest prior.
            hazard = torch.maximum(threat_u, torch.maximum(projectile_u, blocker_u))
            hazard = hazard * (1.0 - 0.85 * rescue_u)
            cue = 0.35 + 1.20 * hazard + 0.50 * imminent
            bias = strength * (0.35 * closeness + 0.65 * forward) * cue
            if self.num_actions > IDLE_INDEX:
                idle_bias = strength * closeness.squeeze(1) * (
                    hazard.squeeze(1) + 0.25 * imminent.squeeze(1)
                )
                bias[:, IDLE_INDEX, :] = idle_bias
        else:
            # Fire queries should be target-seeking. Rescue rows are visible to
            # the model, but the initial fire bias de-emphasizes them. A second
            # ray-alignment term asks whether this specific fire direction is
            # already lined up, which is more precise than "roughly in front."
            target = torch.maximum(destructible_u, projectile_u) * (1.0 - 0.95 * rescue_u)
            cue = 0.25 + 1.40 * target + 0.40 * threat_u
            projection = torch.einsum("ad,bnd->ban", action_dirs, xy)
            lateral_vec = xy.unsqueeze(1) - action_dirs.view(1, self.num_actions, 1, 2) * projection.unsqueeze(-1)
            lateral = lateral_vec.norm(dim=-1).clamp(0.0, 1.0)
            line_width = torch.as_tensor(
                self.fire_alignment_width,
                device=object_tokens.device,
                dtype=object_tokens.dtype,
            ).clamp_min(1e-4)
            line_ready = torch.exp(-torch.square(lateral / line_width))
            line_ready = line_ready * (projection > 0.0).to(dtype=object_tokens.dtype)
            directional = (0.40 * forward.pow(2)) + (0.60 * line_ready)
            bias = strength * directional * (0.35 + 0.65 * closeness) * cue
            if self.num_actions > IDLE_INDEX:
                bias[:, IDLE_INDEX, :] = 0.0

        bias = bias * present.unsqueeze(1).to(dtype=object_tokens.dtype)
        bias = bias.clamp(-6.0, 6.0)
        return bias.repeat_interleave(self.num_heads, dim=0)

    def forward(
        self,
        object_repr: torch.Tensor,
        object_present: torch.Tensor,
        object_tokens: torch.Tensor,
    ) -> torch.Tensor:
        B = object_repr.shape[0]
        action_ids = torch.arange(self.num_actions, device=object_repr.device)
        action_features = self.action_features.to(device=object_repr.device, dtype=object_repr.dtype)
        q0 = self.dir_proj(action_features) + self.dir_embedding(action_ids)
        q = q0.unsqueeze(0).expand(B, -1, -1)
        q = self.query_norm(q)

        key_padding_bool = ~object_present.bool()
        all_empty = key_padding_bool.all(dim=1)
        if all_empty.any():
            key_padding_bool = key_padding_bool.clone()
            key_padding_bool[all_empty, 0] = False
        key_padding_mask = torch.zeros_like(key_padding_bool, dtype=q.dtype)
        key_padding_mask = key_padding_mask.masked_fill(key_padding_bool, float("-inf"))

        bias_tokens = object_tokens.to(device=object_repr.device, dtype=object_repr.dtype)
        attn_mask = self._geometry_attn_mask(bias_tokens, object_present)
        attn_out, _ = self.attn(
            q,
            object_repr,
            object_repr,
            key_padding_mask=key_padding_mask,
            attn_mask=attn_mask,
            need_weights=False,
        )
        if all_empty.any():
            attn_out = attn_out.masked_fill(all_empty.view(B, 1, 1), 0.0)
        return self.out_norm(q + attn_out)


# ── Branching Distributional Dueling Network ────────────────────────────────
class RainbowNet(nn.Module):
    """C51 distributional network with branching dueling heads.

    A shared value distribution V(atoms) is combined with two independent
    advantage streams — move (9 actions) and fire (9 actions) — to produce two
    per-branch action-value distributions::

        Q_move = V + A_move - mean(A_move)
        Q_fire = V + A_fire - mean(A_fire)

    This factors the 81-way joint action into two 9-way decisions, matching
    Robotron's independent movement and fire sticks.
    """

    def __init__(self, state_size: int):
        super().__init__()
        cfg = RL_CONFIG
        self.state_size = state_size
        self.use_dist = cfg.use_distributional
        self.num_atoms = cfg.num_atoms if self.use_dist else 1
        self.v_min = cfg.v_min
        self.v_max = cfg.v_max
        self.use_dueling = cfg.use_dueling
        self.num_move = NUM_MOVE
        self.num_fire = NUM_FIRE

        self.core_features = cfg.core_features
        self.elist_features = getattr(cfg, "elist_features", 22)
        self.global_features = getattr(cfg, "global_features", self.core_features + self.elist_features)
        self.lane_count = int(getattr(cfg, "lane_count", 0))
        self.lane_features = int(getattr(cfg, "lane_features", 0))
        self.extra_features = int(getattr(cfg, "extra_features", 0))
        self.object_token_count = getattr(cfg, "object_token_count", getattr(cfg, "enemy_token_count", 96))
        self.object_token_features = getattr(cfg, "object_token_features", getattr(cfg, "enemy_token_features", 10))
        self.single_frame_state_size = int(getattr(cfg, "single_frame_state_size", state_size))
        self.frame_stack = max(1, int(getattr(cfg, "frame_stack", 1)))

        # ── Lane self-attention encoder ────────────────────────────────
        self.use_attn = bool(getattr(cfg, "use_lane_attention", False)) and self.lane_count > 0 and self.lane_features > 0
        attn_out_dim = 0
        if self.use_attn:
            self.lane_attn = LaneSelfAttentionEncoder(
                lane_features=self.lane_features,
                embed_dim=cfg.attn_dim,
                num_heads=cfg.attn_heads,
            )
            attn_out_dim = cfg.attn_dim

        # ── Object self-attention encoder ──────────────────────────────
        self.use_object_attn = cfg.use_object_attention
        object_attn_out_dim = 0
        if self.use_object_attn:
            self.object_attn = ObjectSelfAttentionEncoder(
                token_features=self.object_token_features,
                embed_dim=cfg.object_attn_dim,
                num_heads=cfg.object_attn_heads,
            )
            object_attn_out_dim = cfg.object_attn_dim

        self.use_action_context = bool(getattr(cfg, "use_action_context_attention", False)) and self.use_object_attn
        self.action_context_dim = object_attn_out_dim if self.use_action_context else 0
        self.joint_move_ids = torch.arange(NUM_JOINT, dtype=torch.long) // NUM_FIRE
        self.joint_fire_ids = torch.arange(NUM_JOINT, dtype=torch.long) % NUM_FIRE
        if self.use_action_context:
            heads = int(getattr(cfg, "action_context_heads", cfg.object_attn_heads))
            self.move_context_attn = DirectionalObjectAttention(
                object_dim=self.action_context_dim,
                num_actions=self.num_move,
                num_heads=heads,
                mode="move",
                geometry_bias=bool(getattr(cfg, "action_context_geometry_bias", True)),
                geometry_bias_strength=float(getattr(cfg, "action_context_geometry_bias_strength", 1.75)),
            )
            self.fire_context_attn = DirectionalObjectAttention(
                object_dim=self.action_context_dim,
                num_actions=self.num_fire,
                num_heads=heads,
                mode="fire",
                geometry_bias=bool(getattr(cfg, "action_context_geometry_bias", True)),
                geometry_bias_strength=float(getattr(cfg, "action_context_geometry_bias_strength", 1.75)),
                fire_alignment_width=float(getattr(cfg, "action_context_fire_alignment_width", 0.075)),
            )

        # ── Trunk ──────────────────────────────────────────────────────
        self.raw_trunk_state_size = self.global_features * self.frame_stack
        trunk_in = self.raw_trunk_state_size + attn_out_dim + object_attn_out_dim
        layers = []
        for i in range(cfg.trunk_layers):
            out_dim = cfg.trunk_hidden
            layers.append(nn.Linear(trunk_in if i == 0 else cfg.trunk_hidden, out_dim))
            if cfg.use_layer_norm:
                layers.append(nn.LayerNorm(out_dim))
            layers.append(nn.ReLU())
            if cfg.dropout > 0:
                layers.append(nn.Dropout(cfg.dropout))
        self.trunk = nn.Sequential(*layers)

        # ── Branching heads ────────────────────────────────────────────
        head_in = cfg.trunk_hidden
        head_mid = head_in // 2

        if self.use_dueling:
            # Shared value stream → (num_atoms,)
            self.val_fc = nn.Linear(head_in, head_mid)
            self.val_out = nn.Linear(head_mid, self.num_atoms)
            # Joint move×fire value stream → (81 × atoms)
            self.joint_val_fc = nn.Linear(head_in, head_mid)
            self.joint_val_out = nn.Linear(head_mid, self.num_atoms)
            if self.use_action_context:
                action_embed_dim = int(getattr(cfg, "joint_action_embed_dim", 32))
                action_hidden = int(getattr(cfg, "action_head_hidden", head_mid))
                self.move_action_embedding = nn.Embedding(self.num_move, action_embed_dim)
                self.fire_action_embedding = nn.Embedding(self.num_fire, action_embed_dim)
                self.joint_action_embedding = nn.Embedding(NUM_JOINT, action_embed_dim)
                self.move_adv_scorer = nn.Sequential(
                    nn.Linear(head_in + self.action_context_dim + action_embed_dim, action_hidden),
                    nn.LayerNorm(action_hidden),
                    nn.ReLU(),
                    nn.Linear(action_hidden, self.num_atoms),
                )
                self.fire_adv_scorer = nn.Sequential(
                    nn.Linear(head_in + self.action_context_dim + action_embed_dim, action_hidden),
                    nn.LayerNorm(action_hidden),
                    nn.ReLU(),
                    nn.Linear(action_hidden, self.num_atoms),
                )
                self.joint_adv_scorer = nn.Sequential(
                    nn.Linear(head_in + (2 * self.action_context_dim) + action_embed_dim, action_hidden),
                    nn.LayerNorm(action_hidden),
                    nn.ReLU(),
                    nn.Linear(action_hidden, self.num_atoms),
                )
            else:
                # Move advantage stream → (num_move × num_atoms)
                self.move_adv_fc = nn.Linear(head_in, head_mid)
                self.move_adv_out = nn.Linear(head_mid, self.num_move * self.num_atoms)
                # Fire advantage stream → (num_fire × num_atoms)
                self.fire_adv_fc = nn.Linear(head_in, head_mid)
                self.fire_adv_out = nn.Linear(head_mid, self.num_fire * self.num_atoms)
                self.joint_adv_fc = nn.Linear(head_in, head_mid)
                self.joint_adv_out = nn.Linear(head_mid, NUM_JOINT * self.num_atoms)
        else:
            self.move_fc = nn.Linear(head_in, head_mid)
            self.move_out = nn.Linear(head_mid, self.num_move * self.num_atoms)
            self.fire_fc = nn.Linear(head_in, head_mid)
            self.fire_out = nn.Linear(head_mid, self.num_fire * self.num_atoms)
            self.joint_fc = nn.Linear(head_in, head_mid)
            self.joint_out = nn.Linear(head_mid, NUM_JOINT * self.num_atoms)

        # BC heads are policy-classification auxiliaries. Keep imitation away
        # from Q magnitudes so Bellman values remain value estimates instead of
        # being bent into expert-action logits.
        self.bc_move_head = nn.Sequential(
            nn.Linear(head_in, head_mid),
            nn.ReLU(),
            nn.Linear(head_mid, self.num_move),
        )
        self.bc_fire_head = nn.Sequential(
            nn.Linear(head_in, head_mid),
            nn.ReLU(),
            nn.Linear(head_mid, self.num_fire),
        )
        self.bc_joint_head = nn.Sequential(
            nn.Linear(head_in, head_mid),
            nn.ReLU(),
            nn.Linear(head_mid, NUM_JOINT),
        )

        self._init_weights()

        # Register support as buffer (not a parameter)
        if self.use_dist:
            support = torch.linspace(self.v_min, self.v_max, self.num_atoms)
            self.register_buffer("support", support)
            self.delta_z = (self.v_max - self.v_min) / (self.num_atoms - 1)

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight, gain=1.0)
                nn.init.constant_(m.bias, 0.0)
            elif isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def _current_frame(self, state: torch.Tensor) -> torch.Tensor:
        if self.frame_stack <= 1:
            return state
        return state[:, :self.single_frame_state_size]

    def _stacked_frames(self, state: torch.Tensor) -> torch.Tensor:
        B = state.shape[0]
        return state.reshape(B, self.frame_stack, self.single_frame_state_size)

    def _raw_trunk_state(self, state: torch.Tensor) -> torch.Tensor:
        if self.frame_stack <= 1:
            return state[:, :self.global_features]
        return self._stacked_frames(state)[:, :, :self.global_features].reshape(
            state.shape[0], self.raw_trunk_state_size)

    def _lane_tokens(self, state: torch.Tensor) -> torch.Tensor:
        """Legacy lane helper, used only if lane attention is re-enabled."""
        state = self._current_frame(state)
        B = state.shape[0]
        start = self.global_features
        end = start + self.lane_count * self.lane_features
        return state[:, start:end].reshape(B, self.lane_count, self.lane_features)

    def _object_tokens(self, state: torch.Tensor) -> torch.Tensor:
        state = self._current_frame(state)
        B = state.shape[0]
        start = self.global_features
        end = start + self.object_token_count * self.object_token_features
        return state[:, start:end].reshape(B, self.object_token_count, self.object_token_features)

    def _trunk_features(self, state: torch.Tensor) -> torch.Tensor:
        parts = [self._raw_trunk_state(state)]
        if self.use_attn:
            parts.append(self.lane_attn(self._lane_tokens(state)))
        if self.use_object_attn:
            parts.append(self.object_attn(self._object_tokens(state)))
        trunk_in = torch.cat(parts, dim=1) if len(parts) > 1 else parts[0]
        return self.trunk(trunk_in)

    def _action_contexts(self, state: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        object_tokens = self._object_tokens(state)
        object_repr, object_present = self.object_attn.encode_tokens(object_tokens)
        move_ctx = self.move_context_attn(object_repr, object_present, object_tokens)
        fire_ctx = self.fire_context_attn(object_repr, object_present, object_tokens)
        return move_ctx, fire_ctx

    def _score_branch_advantage(
        self,
        h: torch.Tensor,
        action_ctx: torch.Tensor,
        action_embedding: nn.Embedding,
        scorer: nn.Module,
        action_count: int,
    ) -> torch.Tensor:
        B = h.shape[0]
        action_ids = torch.arange(action_count, device=h.device)
        emb = action_embedding(action_ids).unsqueeze(0).expand(B, -1, -1)
        h_exp = h.unsqueeze(1).expand(-1, action_count, -1)
        x = torch.cat([h_exp, action_ctx, emb], dim=-1)
        return scorer(x).view(B, action_count, self.num_atoms)

    def _score_joint_advantage(
        self,
        h: torch.Tensor,
        move_ctx: torch.Tensor,
        fire_ctx: torch.Tensor,
    ) -> torch.Tensor:
        B = h.shape[0]
        move_ids = self.joint_move_ids.to(device=h.device)
        fire_ids = self.joint_fire_ids.to(device=h.device)
        joint_ctx = torch.cat([move_ctx[:, move_ids], fire_ctx[:, fire_ids]], dim=-1)
        action_ids = torch.arange(NUM_JOINT, device=h.device)
        emb = self.joint_action_embedding(action_ids).unsqueeze(0).expand(B, -1, -1)
        h_exp = h.unsqueeze(1).expand(-1, NUM_JOINT, -1)
        x = torch.cat([h_exp, joint_ctx, emb], dim=-1)
        return self.joint_adv_scorer(x).view(B, NUM_JOINT, self.num_atoms)

    def bc_logits(self, state: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        h = self._trunk_features(state)
        return self.bc_joint_head(h), self.bc_move_head(h), self.bc_fire_head(h)

    def forward(self, state: torch.Tensor, log: bool = False):
        """Return per-branch action-value distributions.

        Distributional: a tuple ``(move_dist, fire_dist)`` of shape
        ``(B, num_move, num_atoms)`` and ``(B, num_fire, num_atoms)`` —
        probabilities, or log-probabilities when ``log=True``.

        Scalar (non-distributional): a tuple ``(move_q, fire_q)`` of shape
        ``(B, num_move)`` and ``(B, num_fire)``.
        """
        B = state.shape[0]

        h = self._trunk_features(state)

        if self.use_dueling:
            val = F.relu(self.val_fc(h))
            val = self.val_out(val).view(B, 1, self.num_atoms)
            if self.use_action_context:
                move_ctx, fire_ctx = self._action_contexts(state)
                madv = self._score_branch_advantage(
                    h, move_ctx, self.move_action_embedding, self.move_adv_scorer, self.num_move)
                fadv = self._score_branch_advantage(
                    h, fire_ctx, self.fire_action_embedding, self.fire_adv_scorer, self.num_fire)
            else:
                madv = F.relu(self.move_adv_fc(h))
                madv = self.move_adv_out(madv).view(B, self.num_move, self.num_atoms)
                fadv = F.relu(self.fire_adv_fc(h))
                fadv = self.fire_adv_out(fadv).view(B, self.num_fire, self.num_atoms)
            move_atoms = val + madv - madv.mean(dim=1, keepdim=True)
            fire_atoms = val + fadv - fadv.mean(dim=1, keepdim=True)
        else:
            mh = F.relu(self.move_fc(h))
            move_atoms = self.move_out(mh).view(B, self.num_move, self.num_atoms)
            fh = F.relu(self.fire_fc(h))
            fire_atoms = self.fire_out(fh).view(B, self.num_fire, self.num_atoms)

        if self.use_dist:
            if log:
                return (F.log_softmax(move_atoms, dim=2),
                        F.log_softmax(fire_atoms, dim=2))
            return (F.softmax(move_atoms, dim=2),
                    F.softmax(fire_atoms, dim=2))
        else:
            return move_atoms.squeeze(2), fire_atoms.squeeze(2)

    def joint_dist(self, state: torch.Tensor, log: bool = False) -> torch.Tensor:
        """Return joint move×fire action distributions, shape ``(B, 81, atoms)``."""
        B = state.shape[0]
        h = self._trunk_features(state)
        if self.use_dueling:
            val = F.relu(self.joint_val_fc(h))
            val = self.joint_val_out(val).view(B, 1, self.num_atoms)
            if self.use_action_context:
                move_ctx, fire_ctx = self._action_contexts(state)
                adv = self._score_joint_advantage(h, move_ctx, fire_ctx)
            else:
                adv = F.relu(self.joint_adv_fc(h))
                adv = self.joint_adv_out(adv).view(B, NUM_JOINT, self.num_atoms)
            atoms = val + adv - adv.mean(dim=1, keepdim=True)
        else:
            x = F.relu(self.joint_fc(h))
            atoms = self.joint_out(x).view(B, NUM_JOINT, self.num_atoms)
        if self.use_dist:
            return F.log_softmax(atoms, dim=2) if log else F.softmax(atoms, dim=2)
        return atoms

    def q_values_joint(self, state: torch.Tensor) -> torch.Tensor:
        """Expected joint Q-values, shape ``(B, 81)``."""
        if self.use_dist:
            probs = self.joint_dist(state, log=False)
            sup = self.support.unsqueeze(0).unsqueeze(0)
            return (probs * sup).sum(dim=2)
        return self.joint_dist(state, log=False).squeeze(2)

    def q_values_branched(self, state: torch.Tensor):
        """Expected per-branch Q-values: ``(move_q (B,9), fire_q (B,9))``."""
        if self.use_dist:
            move_probs, fire_probs = self.forward(state, log=False)
            sup = self.support.unsqueeze(0).unsqueeze(0)        # (1, 1, N)
            move_q = (move_probs * sup).sum(dim=2)
            fire_q = (fire_probs * sup).sum(dim=2)
            return move_q, fire_q
        else:
            return self.forward(state, log=False)
