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


class ActionConditionedHead(nn.Module):
    """Score each discrete action from shared state and per-action features."""

    def __init__(
        self,
        state_dim: int,
        action_count: int,
        action_feature_dim: int,
        action_embed_dim: int = 32,
        hidden_dim: int = 128,
    ):
        super().__init__()
        self.action_count = int(action_count)
        self.action_feature_dim = int(action_feature_dim)
        self.action_embedding = nn.Embedding(self.action_count, action_embed_dim)
        self.scorer = nn.Sequential(
            nn.Linear(state_dim + action_feature_dim + action_embed_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, state: torch.Tensor, action_features: torch.Tensor) -> torch.Tensor:
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
        x = torch.cat([state_expanded, action_features, action_emb], dim=-1)
        return self.scorer(x).squeeze(-1)


class RobotronPPONet(nn.Module):
    """Compact PPO policy/value network for object-centric Robotron state."""

    def __init__(
        self,
        entity_feature_dim: int = 32,
        max_entities: int = 96,
        embed_dim: int = 160,
        transformer_layers: int = 2,
        num_heads: int = 4,
        global_context_dim: int = 44,
        action_feature_dim: int = 12,
        frame_stack: int = 2,
        fusion_hidden: int = 320,
        fusion_layers: int = 2,
        num_move_actions: int = 9,
        num_fire_actions: int = 9,
        use_auxiliary_head: bool = False,
        auxiliary_predict_steps: Optional[list[int]] = None,
        dropout: float = 0.0,
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

        self.entity_proj = nn.Sequential(
            nn.Linear(self.entity_feature_dim, self.embed_dim),
            nn.LayerNorm(self.embed_dim),
            nn.GELU(),
            nn.Linear(self.embed_dim, self.embed_dim),
        )
        self.global_token = nn.Sequential(
            nn.Linear(self.global_context_dim, self.embed_dim),
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
            hidden_dim=128,
        )
        self.fire_head = ActionConditionedHead(
            state_dim=fusion_hidden,
            action_count=self.num_fire_actions,
            action_feature_dim=self.action_feature_dim,
            hidden_dim=128,
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
        move_action_features: Optional[torch.Tensor],
        fire_action_features: Optional[torch.Tensor],
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        B = entity_features.shape[0]
        T = self.frame_stack

        if entity_features.dim() == 3:
            entity_features = entity_features.unsqueeze(1).expand(B, T, -1, -1)
        if entity_mask.dim() == 2:
            entity_mask = entity_mask.unsqueeze(1).expand(B, T, -1)
        if global_context.dim() == 2:
            global_context = global_context.unsqueeze(1).expand(B, T, -1)

        if move_action_features is None:
            move_action_features = torch.zeros(
                B,
                T,
                self.num_move_actions,
                self.action_feature_dim,
                device=entity_features.device,
                dtype=entity_features.dtype,
            )
        elif move_action_features.dim() == 3:
            move_action_features = move_action_features.unsqueeze(1).expand(B, T, -1, -1)

        if fire_action_features is None:
            fire_action_features = torch.zeros(
                B,
                T,
                self.num_fire_actions,
                self.action_feature_dim,
                device=entity_features.device,
                dtype=entity_features.dtype,
            )
        elif fire_action_features.dim() == 3:
            fire_action_features = fire_action_features.unsqueeze(1).expand(B, T, -1, -1)

        if entity_features.shape[1] != T:
            raise ValueError(f"expected frame_stack={T}, got {entity_features.shape[1]}")

        return (
            entity_features,
            entity_mask,
            global_context,
            move_action_features,
            fire_action_features,
        )

    def _encode_frames(
        self,
        entity_features: torch.Tensor,
        entity_mask: torch.Tensor,
        global_context: torch.Tensor,
    ) -> torch.Tensor:
        """Encode the frame stack into a single (B, embed_dim) scene vector.

        Each object's per-frame embedding is fused along the time axis first
        (per-slot temporal tracking), then the resulting current-scene tokens go
        through the transformer once. This is both cheaper (one transformer pass
        per sample instead of frame_stack passes) and richer, since per-object
        motion is preserved instead of being averaged away by per-frame pooling.
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
        ctx = global_context[:, -1]
        player_token = self.global_token(ctx).unsqueeze(1)
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
        return scene

    def forward(
        self,
        entity_features: torch.Tensor,
        entity_mask: torch.Tensor,
        global_context: torch.Tensor,
        move_action_features: Optional[torch.Tensor] = None,
        fire_action_features: Optional[torch.Tensor] = None,
    ) -> dict[str, torch.Tensor]:
        """Produce move/fire logits and value estimate."""
        (
            entity_features,
            entity_mask,
            global_context,
            move_action_features,
            fire_action_features,
        ) = self._ensure_temporal_inputs(
            entity_features,
            entity_mask,
            global_context,
            move_action_features,
            fire_action_features,
        )

        frame_repr = self._encode_frames(entity_features, entity_mask, global_context)
        fused = self.fusion(frame_repr)

        # Current-frame action geometry is the most relevant for the next input.
        move_current = move_action_features[:, -1]
        fire_current = fire_action_features[:, -1]

        return {
            "move_logits": self.move_head(fused, move_current),
            "fire_logits": self.fire_head(fused, fire_current),
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
