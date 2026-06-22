#!/usr/bin/env python3
"""Robotron AI v3 — Configuration for object-ray transformer + PPO."""

from dataclasses import dataclass, field
from pathlib import Path
import os, json

_CONFIG_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _CONFIG_DIR.parent
_ROBOTRON_DIR = _SCRIPTS_DIR.parent

# ── Model directory resolution ──────────────────────────────────────────────

def _resolve_model_dir() -> Path:
    env_dir = (os.getenv("ROBOTRON_V3_MODEL_DIR") or "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return _ROBOTRON_DIR / "models_v3"

MODEL_DIR = _resolve_model_dir()
CHECKPOINT_PATH = MODEL_DIR / "robotron_v3_latest.pt"
SETTINGS_PATH = MODEL_DIR / "game_settings_v3.json"

# ── Wire protocol constants (must match Lua) ────────────────────────────────

LEGACY_CORE_FEATURES = 18
LEGACY_ELIST_FEATURES = 22
TACTICAL_LANE_COUNT = 8
TACTICAL_LANE_FEATURES = 30
TACTICAL_LOCAL_GRID_FEATURES = 9 * 9 * 6  # 486
PY_CONTROL_CONTEXT_FEATURES = 4

# Extra global-context scalars appended by the StateProcessor (surround/boxed-in
# affordances derived from the per-direction move rays). See state_processor.
GLOBAL_EXTRA_FEATURES = 4

# Entity pool definitions: (name, max_slots, features_per_slot)
# The projectile pool carries an extra subtype channel (cruise missile vs
# spark/shell) so the model can distinguish homing threats from straight shots.
ENTITY_POOL_DEFS: list[tuple[str, int, int]] = [
    ("projectile", 24, 11),
    ("danger",     32, 10),
    ("human",      12,  7),
    ("electrode",   8,  5),
]

# Total Lua wire payload size
WIRE_PARAMS_COUNT = (
    LEGACY_CORE_FEATURES
    + LEGACY_ELIST_FEATURES
    + (TACTICAL_LANE_COUNT * TACTICAL_LANE_FEATURES)
    + TACTICAL_LOCAL_GRID_FEATURES
    + sum(1 + slots * feats for _, slots, feats in ENTITY_POOL_DEFS)
)
# After Python appends fire-hold context
AUGMENTED_PARAMS_COUNT = WIRE_PARAMS_COUNT + PY_CONTROL_CONTEXT_FEATURES

# ── Entity type system ──────────────────────────────────────────────────────

ENTITY_TYPE_NAMES = (
    "grunt", "hulk", "brain", "tank", "spawner",
    "enforcer", "projectile", "human", "electrode",
    "missile", "spark", "prog",
)
MODEL_ARCHITECTURE = "object_ray_v3"
ACTION_FEATURE_DIM = 24

# ── Server ──────────────────────────────────────────────────────────────────

@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 9998
    max_clients: int = 36
    params_count: int = WIRE_PARAMS_COUNT

# ── Object-ray transformer architecture ─────────────────────────────────────

@dataclass
class ModelConfig:
    architecture: str = MODEL_ARCHITECTURE

    # Entity features keep the old first 18 columns for expert compatibility:
    # rel_xy, box_wh, velocity, and 12 type one-hot columns. The remaining
    # columns add HUD-consistent absolute position, timing, and role flags.
    entity_feature_dim: int = 32
    max_entities: int = 96

    # Entity encoder
    embed_dim: int = 160
    transformer_layers: int = 2
    num_heads: int = 4
    dropout: float = 0.0

    # Temporal context
    frame_stack: int = 2

    # Global context stored/transported raw (core features + ELIST). The 4
    # surround-affordance features (GLOBAL_EXTRA_FEATURES) are derived from the
    # per-direction move geometry and appended on-device inside the model, so
    # the buffer/wire only ever carry the 40 raw dims.
    global_context_dim: int = LEGACY_CORE_FEATURES + LEGACY_ELIST_FEATURES  # 40

    # Per-action ray affordances for move and fire heads.
    action_feature_dim: int = ACTION_FEATURE_DIM

    # Fusion MLP after temporal entity/context encoding.
    fusion_hidden: int = 320
    fusion_layers: int = 2

    # Action space
    num_move_actions: int = 9      # 8 directions + idle
    num_fire_actions: int = 9      # 8 directions + idle

    # Per-direction cross-attention (Tempest lane->enemy analog): each move/fire
    # direction token attends to the encoded entity tokens, so the action heads
    # see object-specific evidence for each candidate direction instead of only
    # a globally pooled scene vector + hand-engineered ray features. The pooled
    # scene threw away the per-object detail the transformer produces; this is
    # the main structural lever for action quality.
    use_direction_attention: bool = True
    # Cross-attention is most useful when each direction query starts with a
    # geometric prior over relevant object tokens. Keep this parameter-free so
    # old checkpoints still load, but bias move attention toward objects on the
    # movement axis and fire attention toward forward aligned targets.
    attention_geometry_bias: bool = True
    attention_geometry_bias_strength: float = 1.25

    @property
    def num_joint_actions(self) -> int:
        return self.num_move_actions * self.num_fire_actions

    # The old next-position auxiliary head was tied to stable pool slots. The
    # new model is action-conditioned and starts fresh without that loss.
    use_auxiliary_head: bool = False
    auxiliary_predict_steps: list[int] = field(default_factory=lambda: [1, 5])

# ── PPO training ────────────────────────────────────────────────────────────

@dataclass
class TrainConfig:
    # PPO core
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    clip_value: float = 0.5
    entropy_coeff: float = 0.012
    value_coeff: float = 0.25
    max_grad_norm: float = 1.0

    # PPO mini-batch
    rollout_length: int = 512       # minimum queued steps before PPO update
    max_rollout_drain: int = 2048   # drain bigger batches when many clients are connected
    num_epochs: int = 3             # PPO epochs per rollout
    mini_batch_size: int = 512
    num_actors: int = 32            # parallel MAME instances
    # Keep inference and training on one GPU/network by default. The old
    # automatic split (infer cuda:0, train cuda:1) required periodic weight
    # copies and made it harder to reason about policy freshness while debugging.
    # Set true only when explicitly re-enabling the separate inference copy.
    use_multi_gpu: bool = True
    # Multi-GPU only: copy trained weights to the inference GPU every N PPO
    # updates instead of after every one. The cross-device state_dict copy is
    # pure overhead and one-update-fresh inference is needless churn when updates
    # fire many times/sec; syncing every few steps cuts PCIe traffic and gives
    # the actors a slightly more stable target. 1 = sync every step (old
    # behavior). Checkpoint loads always force a sync regardless of this value.
    inference_sync_interval: int = 4

    # Policy-gradient oversampling: during the guided phase policy-sampled frames
    # are rare (most are expert/BC). Replicating them in the PPO minibatch pool so
    # the policy gradient is not drowned out by behavioral-cloning data.
    policy_oversample: int = 3

    # Optimizer
    lr: float = 3e-4
    lr_min: float = 1e-5
    lr_warmup_steps: int = 5000
    lr_decay_steps: int = 1_000_000
    weight_decay: float = 1e-5
    adam_eps: float = 1e-5

    # Expert behavioral cloning
    bc_weight_initial: float = 1.0
    # Keep a meaningful BC anchor even after decay: at the old 0.02 floor the
    # expert-taught behavior (human chasing / aiming) was too weakly held once
    # expert control handed off, and self-play scores slid. With PPO finding a
    # passive-survival local optimum (camping at ~10k vs the expert's ~66k), a
    # 0.1 floor was too weak to hold the line (BCLoss sat ~2.5, worse than
    # random, i.e. the policy confidently disagreed with the expert). 0.2 lets
    # imitation pull the policy back toward expert-like aggressive wave clearing.

    bc_weight_floor: float = 0.2
    bc_decay_start_frame: int = 100_000
    bc_decay_end_frame: int = 2_000_000
    # Weight the BC term by the expert-frame fraction of each minibatch instead
    # of using a flat mean cross-entropy. F.cross_entropy reduces with mean, so
    # the BC magnitude (~2.8) is independent of how many expert frames are
    # present; once expert_ratio floors at 5% the imitation term (bc_weight*~2.8
    # ~= 0.5) still dominates the total loss and drowns out the PPO gradient
    # (PiLoss ~0.01). Scaling by the expert fraction makes imitation contribute
    # in proportion to the expert data actually present, so it fades together
    # with the expert handoff and lets self-play take over.
    bc_scale_by_expert_fraction: bool = True
    # Apply that expert-fraction scaling to the MOVE BC term too? Firing has a
    # dense PPO teacher (the score reward directly rewards killing, so fire-at-
    # enemy is learned on its own), but movement has no comparable dense reward —
    # BC is its only teacher of intentful navigation. Fading the move term to ~5%
    # at the expert floor starved it: BCMv sat at ln9 (~uniform) and movement
    # degraded to a random walk while firing stayed sharp. Keep move BC at full
    # weight; only let the fire term fade with the handoff.
    bc_scale_move_by_expert_fraction: bool = False
    # Keep fire imitation active too when the fire head is still random. A run
    # with BCFr pinned at ln(9) showed that score-only PPO was not a dense enough
    # teacher once expert control had decayed to the floor.
    bc_scale_fire_by_expert_fraction: bool = False
    # Movement labels are intentionally tactical and can flip between neighboring
    # directions due to small rescue/flee/orbit/slide boundary changes. Train the
    # move head on a directional cone instead of a one-hot target so adjacent
    # moves are treated as partial credit, not as wrong as the opposite direction.
    bc_move_soft_targets: bool = True
    bc_move_soft_exact_mass: float = 0.80
    bc_move_soft_adjacent_mass: float = 0.10
    # Expert action ratio (how often to use expert vs policy)
    expert_ratio_initial: float = 0.99
    expert_ratio_final: float = 0.05
    expert_ratio_decay_start_frame: int = 50_000
    # Halved decay rate (was 1M) for a longer on-ramp: expert control now eases
    # to the 5% floor at ~2.05M frames instead of ~1.05M, giving the policy more
    # frames at each blend level so the handoff is gradual and scores don't slide.
    expert_ratio_decay_frames: int = 2_000_000

    # Drive the guidance schedules (expert ratio, BC weight, epsilon decay) off
    # total emulator frames so the expert handoff reaches the configured floor
    # at the intended wall-clock training frame. Policy-only scheduling made the
    # 99% expert phase self-pacing, but it also meant 1.4M total frames was only
    # ~70K schedule frames and the expert ratio stayed near 98%.
    schedule_on_policy_frames: bool = False

    # Exploration (epsilon-greedy fallback for PPO)
    epsilon_initial: float = 0.1
    epsilon_final: float = 0.05
    epsilon_decay_frames: int = 5_000_000
    epsilon_pulse_min_frame: int = 2_000_000
    epsilon_pulse_period_frames: int = 1_500_000
    epsilon_pulse_amplitude: float = 0.025
    # Entropy coefficient for PPO entropy loss. Higher values encourage exploration.
    # Start at 0.012 for guided phase, decay to 0.004 for exploitation phase.
    entropy_coeff_initial: float = 0.012
    entropy_coeff_final: float = 0.004
    entropy_coeff_decay_frames: int = 3_000_000

    # If self-play competence collapses during the expert handoff, temporarily
    # raise the expert/BC floors so the policy rehearses the expert behavior it
    # is losing. This must engage before the natural expert schedule reaches the
    # 5% floor; the observed failure starts around 1.2M-2.0M frames.
    guidance_rescue_min_frame: int = 750_000
    guidance_rescue_reward_threshold: float = -10.0
    guidance_rescue_expert_ratio_floor: float = 0.40
    guidance_rescue_bc_weight_floor: float = 0.25
    # Hysteresis: enter rescue on these "bad" thresholds, leave only after the
    # stronger "recovered" thresholds are all met. Prevents flicker and avoids
    # letting the handoff decay continue while score/episode length are sliding.
    guidance_rescue_score_threshold: float = 30_000.0
    guidance_rescue_score_recovered_threshold: float = 45_000.0
    guidance_rescue_ep_len_threshold: float = 350.0
    guidance_rescue_ep_len_recovered_threshold: float = 380.0
    guidance_rescue_bc_fire_loss_threshold: float = 1.80
    guidance_rescue_bc_fire_loss_recovered_threshold: float = 1.35
    guidance_rescue_bc_move_loss_threshold: float = 1.80
    guidance_rescue_bc_move_loss_recovered_threshold: float = 1.55
    guidance_rescue_curriculum_wave_spread: int = 4
    # De-bounce: the BC losses are per-minibatch and swing wildly batch-to-batch
    # (BCFr seen jumping 0.2<->2.3 between consecutive evals), which made the
    # rescue flap ON/OFF almost every log line and jerked the expert ratio
    # 5%<->40% — a non-stationary objective that hurts the noisier move head
    # most. We (a) smooth the BC inputs with an EMA before thresholding and
    # (b) require N consecutive agreeing evaluations before actually flipping the
    # committed rescue state. Score/ep_len are already rolling averages, so they
    # need no extra smoothing. Ineligibility (pre-min-frame / non-finite) still
    # forces OFF immediately, bypassing the debounce.
    guidance_rescue_bc_ema_alpha: float = 0.3   # EMA weight on the newest BC loss
    guidance_rescue_debounce_evals: int = 3     # consecutive agreeing evals to flip
    # Recovery (rescue OFF) criteria. Movement BC is inherently noisier and more
    # multimodal than fire BC (the expert's move flips between flee/rescue/orbit/
    # align modes), so smoothed BCMv may NEVER drop to the recovered threshold —
    # making it a one-way ratchet that locks rescue permanently ON and prevents
    # the handoff from ever completing (observed: Xprt pinned at 40% for an
    # entire run). We therefore base RECOVERY on the smooth competence signals
    # (score + ep_len) plus fire BC, and do NOT require move BC to recover.
    # Movement BC can still TRIGGER rescue entry (guidance_rescue_bc_move_loss_
    # threshold) — it just can't hold the clamp on by itself.
    guidance_rescue_recovery_require_move_bc: bool = False
    guidance_rescue_recovery_require_fire_bc: bool = True


    # Reward shaping
    # Survival bonus REMOVED (0.0). Time-on-task has no terminal value in
    # Robotron: you survive in order to score, and per-wave score is bounded by a
    # fixed enemy roster, so any per-frame "stay alive" drip just paid the policy
    # to dodge the last straggler forever instead of clearing the wave (the
    # wave-4 camping optimum). Score already rewards survival implicitly (you
    # can't score while dead) and death_penalty covers the cold-start, so the
    # survival drip's only unique contribution was that perverse one. Kept as a
    # config field (=0.0) so the dashboard RSurv component still resolves.
    survival_bonus: float = 0.0
    # Score is the real objective, applied LINEARLY (reward proportional to the
    # per-frame point delta). The old per-frame log1p was concave, which broke
    # the ordering two ways: (1) the same total score earned as many small kills
    # paid far more than a few big events (10x log1p(10) >> log1p(100)), and
    # (2) a single 100-pt kill already gave 2.5*log1p(100)=11.5 -> clipped to 10,
    # so EVERY scoring frame maxed the clip regardless of magnitude. Together
    # that literally paid the policy to camp and farm tiny gains on early waves
    # (the ~12k-score / wave-2 plateau). Linear makes total reward proportional
    # to total score and timing-independent, so deeper waves and rescues dominate
    # the return. Tuned so a ~12k-point episode contributes ~24 reward (on par
    # with wave clears) and a ~5k-point rescue chain saturates the per-frame clip.
    score_reward_scale: float = 0.002
    # Lua-side subjective shaping (aim/evade/human proximity/survival) carries
    # huge raw per-frame weights (AIM=15, HUMAN=12, EVADE=10, ENEMY=8). At the
    # old 0.02 scale this dense term dominated the ~400-frame episode return
    # (AvgRwd pinned ~97 while score swung 9.5k-12k), so the policy converged to
    # a score-decoupled "look busy" proxy optimum (~10k score, stuck at wave 2-3,
    # PiLoss~0 = no gradient left to climb). Cut 5x to a faint densifier so the
    # objective actually tracks scoring and wave progress.
    subj_reward_scale: float = 0.004
    # Human-rescue premium. Rescues are the dominant SCORE source (1,000-5,000
    # pts) and are MOVEMENT-driven, so the move head must feel them strongly. We
    # no longer add a FLAT bonus (which couldn't tell a 1,000 rescue from a 5,000
    # one); instead the premium is a MULTIPLE of the score reward the event
    # already earned, so it scales with the rescue's value automatically with
    # nothing to track by hand. Premium = human_rescue_bonus_scale * (score
    # component) for any single-frame score delta >= human_rescue_min_score, so a
    # 5,000 rescue earns score(0.002*5000=10) + premium(scale*10) and rank-orders
    # strictly above a 2,500 rescue. Kills (small deltas) stay below the
    # threshold and get no premium. The score component (score + premium) rides
    # the generous score_reward_clip, not the tight reward_clip.
    human_rescue_bonus_scale: float = 1.0
    human_rescue_min_score: float = 1000.0
    death_penalty: float = 5.0
    proximity_penalty_scale: float = 0.02
    # Only penalize proximity when the nearest enemy is within this normalized
    # distance; bounded so it shapes spacing without a constant negative drift.
    proximity_penalty_dist: float = 0.12
    # Bonus on the frame a wave is cleared. With the survival bonus removed,
    # advancing is already the score-maximizing policy (bounded per-wave score +
    # auto-complete on last kill means the only way to keep earning is to finish
    # and move on). The wave bonus no longer has to OVERCOME a camping incentive;
    # it only prices the residual RISK PREMIUM of the last kill (chasing a
    # straggler into the open for little marginal score). Cut 6.0 -> 2.0 to a
    # token nudge; raise only if runs show the policy still stalls on the final
    # enemy.
    wave_clear_bonus: float = 2.0
    wave_progress_bonus: float = 1.0
    # Wave-survival drip REMOVED (0.0) for the same reason as survival_bonus:
    # it paid the policy to linger on deeper waves rather than clear them.
    wave_survival_bonus_per_level: float = 0.0
    wave_survival_bonus_max: float = 0.0
    # Potential-based movement shaping (Ng, Harada & Russell 1999). Firing has a
    # dense PPO teacher (the score reward), but MOVEMENT has none -> the move head
    # collapsed to a random walk. We add a policy-INVARIANT shaping term: the
    # per-transition reward is F = γΦ(s') - Φ(s) for a state potential Φ(s) that
    # is a pure function of state and gated to 0 when the player is dead (giving
    # the required Φ(terminal)=0 for free), so it densifies the move signal
    # WITHOUT changing the optimal policy (any potential-shaped MDP shares the
    # original's optimal policies).
    #
    # Φ(s) = Φ_human(s) + Φ_danger(s), both gated to 0 on death:
    #   Φ_human  = +potential_move_scale   * closeness_h ^ potential_human_sharpness
    #              (closeness_h = 1 - nearest_human_dist; 0 when no humans remain)
    #   Φ_danger = -potential_danger_scale * closeness_e ^ potential_danger_sharpness
    #              (closeness_e ramps 0->1 as the nearest enemy enters
    #               potential_danger_dist; negative potential when in danger, so
    #               MOVING AWAY from a close enemy raises Φ -> positive reward).
    # The convex sharpness (^2) puts the steepest reward gradient on the FINAL
    # approach to a human and on escaping a CLOSE enemy, exactly the movement
    # decisions that matter. Net cumulative pull for crossing the arena to a
    # human ≈ potential_move_scale, an order of magnitude below a rescue/wave
    # event. Set a scale to 0.0 to disable that term.
    potential_move_scale: float = 0.5          # human-approach weight (peak Φ on human)
    potential_human_sharpness: float = 2.0     # convex ramp exponent for approach
    potential_danger_scale: float = 0.5        # flee-from-danger weight
    potential_danger_dist: float = 0.12        # enemy within this normalized dist = "danger"
    potential_danger_sharpness: float = 2.0    # convex ramp exponent for flee

    # Sparse-event hierarchy after rebalancing: a 5,000 rescue (score 10 +
    # scaled premium 10 = 20) > death_penalty=5 > wave_clear=2. The Huber value
    # loss handles the heavy-tailed value-target gradients without flattening
    # these distinctions.
    reward_clip: float = 10.0
    # SEPARATE, more generous clip for the SCORE component (score + human-rescue
    # premium). The plain reward_clip is a per-frame guillotine tuned to tame
    # noisy SUBJECTIVE spikes, but it also annihilated the single most valuable
    # legitimate event in the game: a big human rescue. A 5,000-pt rescue is
    # 0.002*5000 = 10 score + scaled premium 10 = 20 raw, which the ±10 clip
    # flattened to 10 -- identical to a 2,500-pt rescue, so the rescue CHAIN (3rd,
    # 4th, 5th human) produced ZERO marginal reward and the move head could not
    # learn that rescuing more humans is better. We now clip the score component
    # on its OWN budget so the entire rescue value rank-orders all the way to the
    # 5,000 maximum, while the noisy shaping terms keep the tight ±reward_clip.
    # Headroom above the 15-pt single-rescue max lets multi-event frames through.
    score_reward_clip: float = 25.0

    # Curriculum: when GAME_SETTINGS.start_advanced is enabled, spread per-client
    # start levels across this many waves so some actors train on dense late-game
    # object fields instead of every instance starting on the same wave.
    curriculum_wave_spread: int = 10

    # Checkpoint
    save_interval_frames: int = 500_000
    log_interval_frames: int = 50_000

# ── Potential field expert ──────────────────────────────────────────────────

@dataclass
class ExpertConfig:
    # Repulsive weights (negative = repel, positive = attract)
    weight_grunt: float = -10.0
    weight_hulk: float = -50.0
    weight_brain: float = -100.0
    weight_tank: float = -30.0
    weight_spawner: float = -40.0
    weight_enforcer: float = -20.0
    weight_projectile: float = -200.0
    weight_human: float = 50.0
    weight_electrode: float = -30.0
    weight_cruise_missile: float = -250.0

    # Firing priority thresholds
    missile_critical_radius: float = 0.25   # normalized [0,1]
    spawner_priority_radius: float = 0.5
    brain_human_defense_radius: float = 0.2

# ── Composite ───────────────────────────────────────────────────────────────

@dataclass
class V3Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    expert: ExpertConfig = field(default_factory=ExpertConfig)

CONFIG = V3Config()

# ── Game settings (persisted JSON, runtime-mutable) ─────────────────────────

@dataclass
class GameSettings:
    # Curriculum ON by default: spread actors across waves 1..curriculum_wave_spread
    # so the policy directly experiences (and learns to value) deeper waves it
    # would otherwise never reach by camping early waves. Runtime-toggleable from
    # the dashboard and persisted to game_settings_v3.json.
    start_advanced: bool = True
    start_level_min: int = 1
    epsilon: float = CONFIG.train.epsilon_initial
    expert_ratio: float = CONFIG.train.expert_ratio_initial
    manual_epsilon_override: bool = False
    manual_expert_override: bool = False
    total_frames: int = 0
    policy_frames: int = 0

    def save(self):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            json.dump({
                "start_advanced": self.start_advanced,
                "start_level_min": self.start_level_min,
                "epsilon": self.epsilon,
                "expert_ratio": self.expert_ratio,
                "manual_epsilon_override": self.manual_epsilon_override,
                "manual_expert_override": self.manual_expert_override,
                "total_frames": self.total_frames,
                "policy_frames": self.policy_frames,
            }, f, indent=2)

    def load(self):
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH) as f:
                d = json.load(f)
            for k, v in d.items():
                if hasattr(self, k):
                    setattr(self, k, type(getattr(self, k))(v))

GAME_SETTINGS = GameSettings()
