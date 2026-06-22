#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN MODEL                                                                                    ||
# ||                                                                                                              ||
# ||  Rainbow-lite network refactored for Robotron's twin-stick control:                                          ||
# ||    • C51 distributional value estimation                                                                     ||
# ||    • BRANCHING factored heads — independent move (9) and fire (9) streams over a shared value stream         ||
# ||    • Self-attention over the 8 directional "lane" tokens                                                      ||
# ||    • Dueling architecture                                                                                     ||
# ==================================================================================================================
"""Model + action helpers for the Robotron DQN.

The state vector is the compact 258-float slice (18 core + 8 lanes × 30).  The
8 lane blocks are contiguous at ``state[:, 18:258]`` so they reshape directly
into ``(B, 8, 30)`` tokens — no scatter/gather needed (the Lua client already
bins enemies into directional lanes).
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

        self.core_features = cfg.core_features    # 18
        self.lane_count = cfg.lane_count          # 8
        self.lane_features = cfg.lane_features    # 30

        # ── Lane self-attention encoder ────────────────────────────────
        self.use_attn = cfg.use_lane_attention
        attn_out_dim = 0
        if self.use_attn:
            self.lane_attn = LaneSelfAttentionEncoder(
                lane_features=self.lane_features,
                embed_dim=cfg.attn_dim,
                num_heads=cfg.attn_heads,
            )
            attn_out_dim = cfg.attn_dim

        # ── Trunk ──────────────────────────────────────────────────────
        trunk_in = state_size + attn_out_dim
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
            # Move advantage stream → (num_move × num_atoms)
            self.move_adv_fc = nn.Linear(head_in, head_mid)
            self.move_adv_out = nn.Linear(head_mid, self.num_move * self.num_atoms)
            # Fire advantage stream → (num_fire × num_atoms)
            self.fire_adv_fc = nn.Linear(head_in, head_mid)
            self.fire_adv_out = nn.Linear(head_mid, self.num_fire * self.num_atoms)
        else:
            self.move_fc = nn.Linear(head_in, head_mid)
            self.move_out = nn.Linear(head_mid, self.num_move * self.num_atoms)
            self.fire_fc = nn.Linear(head_in, head_mid)
            self.fire_out = nn.Linear(head_mid, self.num_fire * self.num_atoms)

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

    def _lane_tokens(self, state: torch.Tensor) -> torch.Tensor:
        """Reshape the contiguous lane slice into (B, 8, lane_features)."""
        B = state.shape[0]
        start = self.core_features
        end = start + self.lane_count * self.lane_features
        return state[:, start:end].reshape(B, self.lane_count, self.lane_features)

    def forward(self, state: torch.Tensor, log: bool = False):
        """Return per-branch action-value distributions.

        Distributional: a tuple ``(move_dist, fire_dist)`` of shape
        ``(B, num_move, num_atoms)`` and ``(B, num_fire, num_atoms)`` —
        probabilities, or log-probabilities when ``log=True``.

        Scalar (non-distributional): a tuple ``(move_q, fire_q)`` of shape
        ``(B, num_move)`` and ``(B, num_fire)``.
        """
        B = state.shape[0]

        if self.use_attn:
            lane_tokens = self._lane_tokens(state)              # (B, 8, F)
            pooled = self.lane_attn(lane_tokens)                # (B, D)
            trunk_in = torch.cat([state, pooled], dim=1)
        else:
            trunk_in = state

        h = self.trunk(trunk_in)

        if self.use_dueling:
            val = F.relu(self.val_fc(h))
            val = self.val_out(val).view(B, 1, self.num_atoms)
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
