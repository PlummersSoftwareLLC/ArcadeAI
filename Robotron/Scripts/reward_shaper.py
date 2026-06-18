#!/usr/bin/env python3
"""Robotron AI v2 — Modular reward shaping (backported from V3).

Transforms raw objective/subjective rewards from the Lua wire protocol
into a shaped reward signal with additional components:
  - Survival: +bonus per frame alive
  - Score: log-scaled score delta for dense kill signal
  - Human rescue: bonus per rescue (scaled by progressive multiplier)
  - Death penalty: explicit negative on terminal frame
  - Proximity penalty: gentle penalty for being near enemies
"""

import math

try:
    from config import RL_CONFIG
except ImportError:
    from Scripts.config import RL_CONFIG


class RewardShaper:
    """Transforms raw rewards into shaped training signal for V2 DQN."""

    def __init__(self):
        self._cfg = RL_CONFIG

    def shape(
        self,
        obj_reward: float,
        subj_reward: float,
        done: bool,
        player_alive: bool = True,
        score_delta: float = 0.0,
        nearest_enemy_dist: float = 1.0,
        humans_rescued_this_frame: int = 0,
        human_bonus_level: int = 1,
    ) -> float:
        """Compute shaped reward from frame data.

        The base objective/subjective scaling from V2 is preserved.
        Additional shaping components are layered on top.

        Returns:
            float: shaped reward, clipped to [-reward_clip, +reward_clip]
                   (or [-death_reward_clip, ...] on terminal frames)
        """
        cfg = self._cfg
        # Base V2 reward: scale obj + subj
        r = float(obj_reward) * cfg.obj_reward_scale + float(subj_reward) * cfg.subj_reward_scale

        # Survival bonus
        if player_alive and not done:
            r += cfg.survival_bonus

        # Log-scaled score delta (dense kill signal)
        if score_delta > 0:
            r += cfg.score_log_scale * math.log1p(score_delta)

        # Human rescue bonus (progressive multiplier 1-5)
        if humans_rescued_this_frame > 0:
            multiplier = min(5, max(1, int(human_bonus_level)))
            r += cfg.human_rescue_bonus * multiplier * humans_rescued_this_frame

        # Proximity penalty (encourages "safety bubble")
        if player_alive and not done and nearest_enemy_dist < 1.0:
            inv_dist = 1.0 / max(nearest_enemy_dist, 0.01)
            r -= cfg.proximity_penalty_scale * inv_dist

        # Explicit death penalty (on top of whatever obj_reward already has)
        death_pen = getattr(cfg, "death_penalty", 0.0)
        if done and death_pen > 0.0:
            r -= death_pen

        # Clip
        clip = cfg.death_reward_clip if done else cfg.reward_clip
        return max(-clip, min(clip, r))


# Module-level singleton for simple import
_shaper = None


def shape_reward(
    obj_reward: float,
    subj_reward: float,
    done: bool,
    player_alive: bool = True,
    score_delta: float = 0.0,
    nearest_enemy_dist: float = 1.0,
    humans_rescued_this_frame: int = 0,
    human_bonus_level: int = 1,
) -> float:
    """Convenience function using module singleton."""
    global _shaper
    if _shaper is None:
        _shaper = RewardShaper()
    return _shaper.shape(
        obj_reward, subj_reward, done, player_alive,
        score_delta, nearest_enemy_dist,
        humans_rescued_this_frame, human_bonus_level,
    )
