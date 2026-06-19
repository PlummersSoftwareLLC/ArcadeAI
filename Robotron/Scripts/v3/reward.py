#!/usr/bin/env python3
"""Robotron AI v3 — Reward shaping module.

Transforms raw objective/subjective rewards from the Lua wire protocol
into a shaped reward signal for PPO training.

Reward components:
  - Survival: +bonus per frame alive
  - Score: log-scaled score delta for dense kill signal
  - Human rescue: large bonus per rescue (scaled by progressive multiplier)
  - Death penalty: strong negative on terminal frame
  - Proximity penalty: gentle penalty for being near enemies
"""

import math
import numpy as np
from .config import CONFIG, TrainConfig


class RewardShaper:
    """Transforms raw rewards into shaped training signal."""

    def __init__(self, cfg: TrainConfig = None):
        self.cfg = cfg or CONFIG.train

    def shape(
        self,
        obj_reward: float,
        subj_reward: float,
        done: bool,
        player_alive: bool,
        score_delta: float = 0.0,
        nearest_enemy_dist: float = 1.0,
        wave_completed: bool = False,
    ) -> float:
        """Compute shaped reward from frame data.

        Args:
            obj_reward: raw objective reward from Lua (score-based)
            subj_reward: raw subjective reward from Lua (aim/evade/human/survival)
            done: True on death/episode end
            player_alive: whether player is currently alive
            score_delta: change in game score this frame (>= 0)
            nearest_enemy_dist: distance to nearest enemy (normalized 0-1)
            wave_completed: True on the frame a wave was just cleared

        Returns:
            float: shaped reward, clipped to [-reward_clip, +reward_clip]
        """
        r = 0.0
        cfg = self.cfg

        # Survival bonus
        if player_alive and not done:
            r += cfg.survival_bonus

        # Score-based reward (log-scaled for density). Log scaling keeps large
        # point events (human rescues 1000-5000) ordered above smaller kills
        # instead of saturating a linear clip, which is what makes "is a human
        # worth saving" learnable.
        if score_delta > 0:
            r += cfg.score_log_scale * math.log1p(score_delta)

        # Lua-side subjective shaping (dense, between scoring events).
        r += cfg.subj_reward_scale * float(subj_reward)

        # Wave-clear bonus: reward reaching deeper waves.
        if wave_completed:
            r += cfg.wave_clear_bonus

        # Proximity penalty (bounded; encourages a "safety bubble").
        if player_alive and not done and nearest_enemy_dist < cfg.proximity_penalty_dist:
            closeness = (cfg.proximity_penalty_dist - nearest_enemy_dist) / max(
                cfg.proximity_penalty_dist, 1e-6
            )
            r -= cfg.proximity_penalty_scale * max(0.0, min(1.0, closeness))

        # Death penalty
        if done:
            r -= cfg.death_penalty

        # Clip
        r = max(-cfg.reward_clip, min(cfg.reward_clip, r))
        return r

    def shape_simple(
        self,
        obj_reward: float,
        subj_reward: float,
        done: bool,
    ) -> float:
        """Simplified shaping using just the raw Lua rewards.

        When full entity-level detail isn't available, fall back to
        scaling and combining the Lua-provided objective and subjective.
        """
        cfg = self.cfg

        # Objective reward dominates
        r = obj_reward * 0.03 + subj_reward * 0.001

        # Survival bonus when not dying
        if not done:
            r += cfg.survival_bonus

        # Death penalty
        if done:
            r -= cfg.death_penalty

        return max(-cfg.reward_clip, min(cfg.reward_clip, r))


# Module-level singleton
_shaper: RewardShaper = None

def shape_reward(
    obj_reward: float,
    subj_reward: float,
    done: bool,
    player_alive: bool = True,
    score_delta: float = 0.0,
    nearest_enemy_dist: float = 1.0,
    wave_completed: bool = False,
) -> float:
    global _shaper
    if _shaper is None:
        _shaper = RewardShaper()
    return _shaper.shape(
        obj_reward,
        subj_reward,
        done,
        player_alive=player_alive,
        score_delta=score_delta,
        nearest_enemy_dist=nearest_enemy_dist,
        wave_completed=wave_completed,
    )
