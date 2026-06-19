#!/usr/bin/env python3
"""Robotron AI v3 — Configuration for object-ray transformer + PPO."""

from dataclasses import dataclass, field
from pathlib import Path
import os, json

_CONFIG_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _CONFIG_DIR.parent
_ROBOTRON_DIR = _SCRIPTS_DIR.parent
_REPO_ROOT = _ROBOTRON_DIR.parent

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
)
NUM_ENTITY_TYPES = len(ENTITY_TYPE_NAMES)
MODEL_ARCHITECTURE = "object_ray_v1"
ACTION_FEATURE_DIM = 12

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

    # Global context (core features + ELIST + appended surround affordances).
    global_context_dim: int = LEGACY_CORE_FEATURES + LEGACY_ELIST_FEATURES + GLOBAL_EXTRA_FEATURES  # 44

    # Per-action ray affordances for move and fire heads.
    action_feature_dim: int = ACTION_FEATURE_DIM

    # Fusion MLP after temporal entity/context encoding.
    fusion_hidden: int = 320
    fusion_layers: int = 2

    # Action space
    num_move_actions: int = 9      # 8 directions + idle
    num_fire_actions: int = 9      # 8 directions + idle

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
    entropy_coeff: float = 0.015
    value_coeff: float = 0.25
    max_grad_norm: float = 1.0

    # PPO mini-batch
    rollout_length: int = 512       # minimum queued steps before PPO update
    max_rollout_drain: int = 2048   # drain bigger batches when many clients are connected
    num_epochs: int = 3             # PPO epochs per rollout
    mini_batch_size: int = 512
    num_actors: int = 32            # parallel MAME instances

    # Policy-gradient oversampling: during the guided phase policy-sampled frames
    # are rare (most are expert/BC). Replicating them in the PPO minibatch pool so
    # the policy gradient is not drowned out by behavioral-cloning data.
    policy_oversample: int = 3

    # Optimizer
    lr: float = 3e-4
    lr_min: float = 1e-5
    lr_warmup_steps: int = 5000
    lr_decay_steps: int = 3_000_000
    weight_decay: float = 1e-5
    adam_eps: float = 1e-5

    # Expert behavioral cloning
    bc_weight_initial: float = 1.0
    # Keep BC present, but hand off much sooner so the policy learns to recover
    # from its own states instead of watching the heuristic for millions of frames.
    bc_weight_floor: float = 0.05
    bc_decay_start_frame: int = 100_000
    bc_decay_end_frame: int = 1_200_000

    # Expert action ratio (how often to use expert vs policy)
    expert_ratio_initial: float = 0.99
    expert_ratio_final: float = 0.08
    expert_ratio_decay_start_frame: int = 50_000
    expert_ratio_decay_frames: int = 1_000_000

    # Exploration (epsilon-greedy fallback for PPO)
    epsilon_initial: float = 0.1
    epsilon_final: float = 0.04
    epsilon_decay_frames: int = 5_000_000

    # If recent self-play reward collapses after the early guided phase,
    # temporarily raise the expert/BC floor so the policy can recover.
    guidance_rescue_min_frame: int = 4_000_000
    guidance_rescue_reward_threshold: float = -10.0
    guidance_rescue_expert_ratio_floor: float = 0.12
    guidance_rescue_bc_weight_floor: float = 0.08

    # Reward shaping
    survival_bonus: float = 0.01
    score_log_scale: float = 1.0
    # Lua-side subjective shaping (aim/evade/human proximity/survival) is carried
    # in subj_reward; scale it so it densifies learning without dominating the
    # log-scaled objective score signal.
    subj_reward_scale: float = 0.02
    human_rescue_bonus: float = 5.0
    death_penalty: float = 10.0
    proximity_penalty_scale: float = 0.1
    # Only penalize proximity when the nearest enemy is within this normalized
    # distance; bounded so it shapes spacing without a constant negative drift.
    proximity_penalty_dist: float = 0.12
    # Bonus on the frame a wave is cleared (rewards reaching deeper waves).
    wave_clear_bonus: float = 3.0
    reward_clip: float = 10.0

    # Curriculum: when GAME_SETTINGS.start_advanced is enabled, spread per-client
    # start levels across this many waves so some actors train on dense late-game
    # object fields instead of every instance starting on the same wave.
    curriculum_wave_spread: int = 6

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
    start_advanced: bool = False
    start_level_min: int = 1
    epsilon: float = CONFIG.train.epsilon_initial
    expert_ratio: float = CONFIG.train.expert_ratio_initial
    total_frames: int = 0

    def save(self):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, "w") as f:
            json.dump({
                "start_advanced": self.start_advanced,
                "start_level_min": self.start_level_min,
                "epsilon": self.epsilon,
                "expert_ratio": self.expert_ratio,
                "total_frames": self.total_frames,
            }, f, indent=2)

    def load(self):
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH) as f:
                d = json.load(f)
            for k, v in d.items():
                if hasattr(self, k):
                    setattr(self, k, type(getattr(self, k))(v))

GAME_SETTINGS = GameSettings()
