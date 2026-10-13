#!/usr/bin/env python3
"""Robotron AI v3 — Reward shaping module.

Transforms raw objective/subjective rewards from the Lua wire protocol
into a shaped reward signal for PPO training.

Reward components:
  - Score: log-scaled score delta for dense kill signal
  - Human rescue: large bonus per rescue (scaled by progressive multiplier)
  - Death penalty: strong negative on terminal frame
  - Proximity penalty: gentle penalty for being near enemies
  - Wave clear: token bonus pricing the risk premium of the last kill
"""

import numpy as np
from .config import CONFIG, TrainConfig


class RewardShaper:
    """Transforms raw rewards into shaped training signal."""

    def __init__(self, cfg: TrainConfig = None):
        self.cfg = cfg or CONFIG.train

    def move_potential(
        self,
        nearest_human_dist: float,
        num_humans: float,
        player_alive: bool,
        nearest_enemy_dist: float = 1.0,
    ) -> float:
        """Potential Φ(s) for movement shaping (Ng et al. 1999).

        Φ(s) = Φ_human(s) + Φ_danger(s), both gated to 0 when the player is dead
        so that Φ(terminal) = 0 (the condition that makes potential-based shaping
        policy-invariant). The per-transition reward is F = γΦ(s') - Φ(s).

        IMPORTANT — anchoring: the whole potential is kept <= 0 with Φ = 0 at the
        IDEAL state (standing on a human, no enemy near). PBRS leaks (γ-1)·Φ per
        frame at a stable potential; with γ=0.99 a persistently POSITIVE Φ would
        bleed a constant negative "RMove" drag (a spurious movement penalty),
        while a <=0 Φ leaks a small POSITIVE drip for being near the goal. The
        per-step DIRECTIONAL rewards are unchanged by the anchor (approaching a
        human and fleeing a close enemy both still raise Φ).

        Φ_human  = -potential_move_scale * (1 - closeness_h ** human_sharpness)
            closeness_h = 1 - nearest_human_dist. Φ_human = 0 on the human and
            -scale when far; the convex exponent makes Φ rise STEEPEST on the
            final approach -> dense, immediate credit for movement that leads to a
            rescue, before the lump-sum score even arrives. 0 when no humans.

        Φ_danger = -potential_danger_scale * closeness_e ** danger_sharpness
            closeness_e ramps 0->1 as the nearest enemy enters
            potential_danger_dist. 0 when safe, negative when an enemy is close,
            so moving AWAY raises Φ -> a positive shaping reward for fleeing
            danger (and a penalty for charging into it).

        Args:
            nearest_human_dist: normalized 0-1 distance to nearest human (wire
                state index 10). 0 = on top of a human, 1 = far / none.
            num_humans: count (or any >0 proxy) of humans currently alive (wire
                state index 13 carries count/255, so any human -> >0).
            player_alive: whether the player is currently alive.
            nearest_enemy_dist: normalized 0-1 distance to nearest enemy (wire
                state index 9). 0 = on top of an enemy, 1 = far / none.

        Returns:
            float: the potential Φ(s) (<= 0); 0.0 when gated off.
        """
        if not player_alive:
            return 0.0

        phi = 0.0

        # Human-approach term (only while humans remain). Anchored at 0 on the
        # human, -scale when far; convex so the final approach is steepest.
        if self.cfg.potential_move_scale > 0.0 and num_humans > 0:
            d_h = max(0.0, min(1.0, float(nearest_human_dist)))
            closeness_h = 1.0 - d_h
            phi -= self.cfg.potential_move_scale * (
                1.0 - closeness_h ** self.cfg.potential_human_sharpness
            )

        # Danger-flee term (only while an enemy is within the danger band). 0
        # when safe, negative when close, so moving away raises Φ.
        danger_dist = self.cfg.potential_danger_dist
        if self.cfg.potential_danger_scale > 0.0 and danger_dist > 0.0:
            d_e = max(0.0, min(1.0, float(nearest_enemy_dist)))
            if d_e < danger_dist:
                closeness_e = (danger_dist - d_e) / danger_dist
                closeness_e = max(0.0, min(1.0, closeness_e))
                phi -= self.cfg.potential_danger_scale * (
                    closeness_e ** self.cfg.potential_danger_sharpness
                )

        return phi


    def shape(
        self,
        obj_reward: float,
        subj_reward: float,
        done: bool,
        player_alive: bool,
        score_delta: float = 0.0,
        nearest_enemy_dist: float = 1.0,
        wave_completed: bool = False,
        wave_number: int = 1,
        move_potential_prev: float = 0.0,
        move_potential_cur: float = 0.0,
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
            wave_number: current wave after the transition

        Returns:
            float: shaped reward, clipped to [-reward_clip, +reward_clip]
        """
        return self.shape_with_components(
            obj_reward,
            subj_reward,
            done,
            player_alive=player_alive,
            score_delta=score_delta,
            nearest_enemy_dist=nearest_enemy_dist,
            wave_completed=wave_completed,
            wave_number=wave_number,
            move_potential_prev=move_potential_prev,
            move_potential_cur=move_potential_cur,
        )[0]

    def shape_with_components(
        self,
        obj_reward: float,
        subj_reward: float,
        done: bool,
        player_alive: bool,
        score_delta: float = 0.0,
        nearest_enemy_dist: float = 1.0,
        wave_completed: bool = False,
        wave_number: int = 1,
        move_potential_prev: float = 0.0,
        move_potential_cur: float = 0.0,
    ) -> tuple[float, dict[str, float]]:
        """Compute shaped reward plus diagnostic component contributions."""
        components = {
            "score": 0.0,
            "subj": 0.0,
            "surv": 0.0,
            "prox": 0.0,
            "death": 0.0,
            "wave": 0.0,
            "human": 0.0,
            "move": 0.0,
            "clip": 0.0,
        }
        cfg = self.cfg
        wave = max(1, int(wave_number or 1))

        # Survival bonus removed: time-on-task has no terminal value in Robotron
        # and a per-frame "stay alive" drip just incentivized camping the last
        # enemy instead of clearing the wave. Score (you can't score while dead)
        # and death_penalty cover the legitimate "avoid death" signal. The
        # components["surv"] key is left at 0.0 so the dashboard column resolves.

        # Score-based reward (linear in the per-frame point delta). Linearity
        # keeps total reward proportional to total score regardless of how the
        # points are spread across frames, so the policy cannot inflate reward
        # by farming many tiny gains (the per-frame log1p drip that produced the
        # passive camping optimum). Big point events (human rescues 1000-5000)
        # are still ordered above small kills and only saturate the per-frame
        # clip at the very top end.
        if score_delta > 0:
            components["score"] += cfg.score_reward_scale * score_delta
            # Rescue premium: a MULTIPLE of the score this event just earned, so
            # it scales with the rescue's value (1,000-5,000) automatically. Only
            # single-frame deltas at/above the rescue threshold qualify, so small
            # kills get no premium. This makes a 5,000 rescue strictly out-reward
            # a 2,500 one and gives the movement head the full escalating signal.
            if score_delta >= cfg.human_rescue_min_score:
                components["human"] += (
                    cfg.human_rescue_bonus_scale * cfg.score_reward_scale * score_delta
                )

        # Lua-side subjective shaping (dense, between scoring events).
        components["subj"] += cfg.subj_reward_scale * float(subj_reward)

        # Wave-clear bonus: reward reaching deeper waves.
        if wave_completed:
            components["wave"] += cfg.wave_clear_bonus
            components["wave"] += cfg.wave_progress_bonus * min(10, max(0, wave - 1))

        # Proximity penalty (bounded; encourages a "safety bubble").
        if player_alive and not done and nearest_enemy_dist < cfg.proximity_penalty_dist:
            closeness = (cfg.proximity_penalty_dist - nearest_enemy_dist) / max(
                cfg.proximity_penalty_dist, 1e-6
            )
            components["prox"] -= cfg.proximity_penalty_scale * max(0.0, min(1.0, closeness))

        # Death penalty
        if done:
            components["death"] -= cfg.death_penalty

        # Potential-based movement shaping: F = γΦ(s') - Φ(s). The caller passes
        # the cached previous-frame potential and the current-frame potential
        # (both already gated via move_potential(); the current one is 0 on a
        # terminal frame because the player is no longer alive). This telescopes
        # across an episode so it adds no net return at the optimum but densely
        # rewards reducing distance to the nearest human -> the move head's only
        # teacher, since firing already learns from the score reward.
        components["move"] += cfg.gamma * float(move_potential_cur) - float(move_potential_prev)

        # Clip. The SCORE component (score + human-rescue bonus) is exempt from
        # the tight ±reward_clip and gets its own, more generous budget so the
        # full value of a big human rescue (up to 0.002*5000 + 5 = 15) and the
        # escalating rescue chain propagate to the move head instead of being
        # flattened to a constant 10. The noisy SHAPING terms (subj/prox/death/
        # wave/move/surv) keep the tight clip that protects against subjective
        # spikes. The two clipped parts are then summed.
        score_part = components["score"] + components["human"]
        shaping_part = (
            components["subj"]
            + components["surv"]
            + components["prox"]
            + components["death"]
            + components["wave"]
            + components["move"]
        )
        score_clip = getattr(cfg, "score_reward_clip", cfg.reward_clip)
        score_clipped = max(-score_clip, min(score_clip, score_part))
        shaping_clipped = max(-cfg.reward_clip, min(cfg.reward_clip, shaping_part))
        clipped = score_clipped + shaping_clipped
        raw = score_part + shaping_part
        components["clip"] = clipped - raw
        return clipped, components

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

def move_potential(
    nearest_human_dist: float,
    num_humans: float,
    player_alive: bool,
    nearest_enemy_dist: float = 1.0,
) -> float:
    global _shaper
    if _shaper is None:
        _shaper = RewardShaper()
    return _shaper.move_potential(
        nearest_human_dist, num_humans, player_alive, nearest_enemy_dist
    )


def shape_reward(
    obj_reward: float,
    subj_reward: float,
    done: bool,
    player_alive: bool = True,
    score_delta: float = 0.0,
    nearest_enemy_dist: float = 1.0,
    wave_completed: bool = False,
    wave_number: int = 1,
    move_potential_prev: float = 0.0,
    move_potential_cur: float = 0.0,
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
        wave_number=wave_number,
        move_potential_prev=move_potential_prev,
        move_potential_cur=move_potential_cur,
    )


def shape_reward_with_components(
    obj_reward: float,
    subj_reward: float,
    done: bool,
    player_alive: bool = True,
    score_delta: float = 0.0,
    nearest_enemy_dist: float = 1.0,
    wave_completed: bool = False,
    wave_number: int = 1,
    move_potential_prev: float = 0.0,
    move_potential_cur: float = 0.0,
) -> tuple[float, dict[str, float]]:
    global _shaper
    if _shaper is None:
        _shaper = RewardShaper()
    return _shaper.shape_with_components(
        obj_reward,
        subj_reward,
        done,
        player_alive=player_alive,
        score_delta=score_delta,
        nearest_enemy_dist=nearest_enemy_dist,
        wave_completed=wave_completed,
        wave_number=wave_number,
        move_potential_prev=move_potential_prev,
        move_potential_cur=move_potential_cur,
    )
