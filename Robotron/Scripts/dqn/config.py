#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN CONFIGURATION                                                                            ||
# ||  Rainbow-lite engine (C51 + dueling + PER + n-step + target net + expert BC), enemy-list attention,        ||
# ||  and a joint twin-stick action head.  Ported and refactored from the Tempest DQN.                           ||
# ==================================================================================================================
"""Central configuration: server, RL hyper-parameters, game settings, metrics.

State representation
--------------------
Each frame the Lua client sends ``WIRE_PARAMS_COUNT`` (1890) big-endian f32
values. The DQN consumes a deliberately plain single-frame slice of that wire:
the 18 core game/player scalars, the 22 raw ELIST/level-state bytes, and a
112-row distance-sorted object state bag:
64 destructible enemies/projectiles, 16 hulks, 16 obstacles, and 16 humans.
Legacy lanes/grids remain on the wire for the expert/debugging path, but are
not part of the DQN model input.

Action representation
---------------------
Robotron is twin-stick: an independent 8-way movement stick and 8-way fire
stick, each with an idle option (9 options per stick).  The replay buffer stores
the joint action index ``move * NUM_FIRE_ACTIONS + fire`` (0..80).  The main
Bellman policy head is a joint 81-action C51 head; branch heads are retained for
auxiliary expert imitation and diagnostics.
"""

if __name__ == "__main__":
    print("This is not the main application, run 'main.py' instead")
    exit(1)

import os, sys, time, threading, math, json
from dataclasses import dataclass, field
from typing import Deque
from collections import deque

import numpy as np

IS_INTERACTIVE = sys.stdin.isatty()
RESET_METRICS = False
FORCE_FRESH_MODEL = False

# Resolve the model directory to an absolute path (Robotron/models_dqn) so it
# is independent of the current working directory, matching the v3 launcher.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../Scripts
_ROBOTRON_DIR = os.path.dirname(_SCRIPTS_DIR)                                # .../Robotron
_env_model_dir = (os.getenv("ROBOTRON_DQN_MODEL_DIR") or "").strip()
MODEL_DIR = os.path.abspath(os.path.expanduser(_env_model_dir)) if _env_model_dir \
    else os.path.join(_ROBOTRON_DIR, "models_dqn")
LATEST_MODEL_PATH = os.path.join(MODEL_DIR, "robotron_dqn_latest.pt")
SETTINGS_PATH = os.path.join(MODEL_DIR, "game_settings.json")

# ---------------------------------------------------------------------------
#  Wire / state-slice geometry
# ---------------------------------------------------------------------------
# Number of f32 values the Lua client packs into each frame's state payload.
# Lua emits four distance-sorted 10-wide state-bag groups after lane/grid data.
WIRE_PARAMS_COUNT = 1890

# Model slice: 18 core game features + 22 ELIST/level-state features +
# 112 grouped object rows × 10 features.
CORE_FEATURES = 18                       # wire[0:18]
ELIST_FEATURES = 22                      # wire[18:40]
GLOBAL_FEATURES = CORE_FEATURES + ELIST_FEATURES
LANE_COUNT = 8                           # 8 fire/move directions
LANE_FEATURES = 30                       # features per lane
TACTICAL_LANE_OFFSET = 40                # wire index where lane blocks begin
TACTICAL_LANE_END = TACTICAL_LANE_OFFSET + LANE_COUNT * LANE_FEATURES   # 280
# Lua emits lane rows in geometric angle order:
#   E, NE, N, NW, W, SW, S, SE
# Model actions are controller order:
#   N, NE, E, SE, S, SW, W, NW
# Reorder lanes so model lane row N lines up with move/fire action N.
ACTION_LANE_WIRE_INDICES = (2, 1, 0, 7, 6, 5, 4, 3)
TACTICAL_GRID_FEATURES = 9 * 9 * 6
TACTICAL_GRID_OFFSET = TACTICAL_LANE_END
TACTICAL_GRID_END = TACTICAL_GRID_OFFSET + TACTICAL_GRID_FEATURES        # 766
TACTICAL_POOL_OFFSET = TACTICAL_GRID_END

# Grouped object-list section. Each group is sorted nearest-first; overflow is
# dropped by Lua and defensively re-sorted here.
DESTRUCTIBLE_TOKEN_COUNT = 64
HULK_TOKEN_COUNT = 16
OBSTACLE_TOKEN_COUNT = 16
HUMAN_TOKEN_COUNT = 16
ENEMY_TOKEN_COUNT = (
    DESTRUCTIBLE_TOKEN_COUNT
    + HULK_TOKEN_COUNT
    + OBSTACLE_TOKEN_COUNT
    + HUMAN_TOKEN_COUNT
)
ENEMY_TOKEN_FEATURES = 10
ENEMY_FEATURES = ENEMY_TOKEN_COUNT * ENEMY_TOKEN_FEATURES
ENEMY_TOKEN_OFFSET = GLOBAL_FEATURES
ENEMY_TOKEN_END = ENEMY_TOKEN_OFFSET + ENEMY_FEATURES
SINGLE_FRAME_STATE_SIZE = ENEMY_TOKEN_END                                     # 1160
_frame_stack_env = os.getenv("DQN_FRAME_STACK", os.getenv("ROBOTRON_DQN_FRAME_STACK", "1"))
try:
    FRAME_STACK_COUNT = max(1, int(_frame_stack_env))
except Exception:
    FRAME_STACK_COUNT = 1
MODEL_STATE_SIZE = SINGLE_FRAME_STATE_SIZE * FRAME_STACK_COUNT

# Pool layout mirrors main.lua tactical pool emission.
TACTICAL_POOL_DEFS = (
    ("destructible", DESTRUCTIBLE_TOKEN_COUNT, ENEMY_TOKEN_FEATURES),
    ("hulk", HULK_TOKEN_COUNT, ENEMY_TOKEN_FEATURES),
    ("obstacle", OBSTACLE_TOKEN_COUNT, ENEMY_TOKEN_FEATURES),
    ("human", HUMAN_TOKEN_COUNT, ENEMY_TOKEN_FEATURES),
)

TOKEN_GROUP_RANGES = {
    "destructible": (0, DESTRUCTIBLE_TOKEN_COUNT),
    "hulk": (DESTRUCTIBLE_TOKEN_COUNT, DESTRUCTIBLE_TOKEN_COUNT + HULK_TOKEN_COUNT),
    "obstacle": (
        DESTRUCTIBLE_TOKEN_COUNT + HULK_TOKEN_COUNT,
        DESTRUCTIBLE_TOKEN_COUNT + HULK_TOKEN_COUNT + OBSTACLE_TOKEN_COUNT,
    ),
    "human": (
        DESTRUCTIBLE_TOKEN_COUNT + HULK_TOKEN_COUNT + OBSTACLE_TOKEN_COUNT,
        ENEMY_TOKEN_COUNT,
    ),
}


def _clip01(v: float) -> float:
    try:
        x = float(v)
    except Exception:
        return 0.0
    if not math.isfinite(x):
        return 0.0
    return min(1.0, max(0.0, x))


def _clip11(v: float) -> float:
    try:
        x = float(v)
    except Exception:
        return 0.0
    if not math.isfinite(x):
        return 0.0
    return min(1.0, max(-1.0, x))


def _state_bag_row(slot: np.ndarray, feat_per_slot: int) -> np.ndarray | None:
    if not np.isfinite(slot).all() or slot[0] <= 0.5:
        return None
    return np.asarray([
        1.0,
        _clip11(slot[1] if feat_per_slot > 1 else 0.0),
        _clip11(slot[2] if feat_per_slot > 2 else 0.0),
        _clip01(slot[3] if feat_per_slot > 3 else 1.0),
        _clip11(slot[4] if feat_per_slot > 4 else 0.0),
        _clip11(slot[5] if feat_per_slot > 5 else 0.0),
        _clip01(slot[6] if feat_per_slot > 6 else 0.0),
        _clip11(slot[7] if feat_per_slot > 7 else 0.0),
        _clip01(slot[8] if feat_per_slot > 8 else 1.0),
        _clip01(slot[9] if feat_per_slot > 9 else 0.0),
    ], dtype=np.float32)


def _extract_enemy_tokens(arr: np.ndarray) -> np.ndarray:
    """Return the 112-row grouped object state bag from Lua tactical pools.

    Row layout:
    ``[present, dx, dy, dist, vx, vy, threat, approach, ttc, type_norm]``.
    Groups are laid out as destructible, hulk, obstacle, human. Active rows are
    distance-sorted within each group and overflow is ignored.
    """
    out = np.zeros((ENEMY_TOKEN_COUNT, ENEMY_TOKEN_FEATURES), dtype=np.float32)
    pools = arr[TACTICAL_POOL_OFFSET:]
    pool_offset = 0
    out_offset = 0

    for pool_name, max_slots, feat_per_slot in TACTICAL_POOL_DEFS:
        slot_start = pool_offset + 1
        slot_end = slot_start + max_slots * feat_per_slot
        if slot_end > len(pools):
            out_offset += max_slots
            pool_offset += 1 + max_slots * feat_per_slot
            continue

        rows = []
        raw = pools[slot_start:slot_end].reshape(max_slots, feat_per_slot)
        for slot_idx in range(max_slots):
            row = _state_bag_row(raw[slot_idx], feat_per_slot)
            if row is not None:
                rows.append(row)
        rows.sort(key=lambda row: float(row[3]))
        for i, row in enumerate(rows[:max_slots]):
            dst = out_offset + i
            if dst >= ENEMY_TOKEN_COUNT:
                break
            out[dst] = row

        out_offset += max_slots
        pool_offset += 1 + max_slots * feat_per_slot

    return out.reshape(-1)


def slice_model_state(wire) -> np.ndarray:
    """Extract the compact model input from a full wire vector.

    ``wire`` may be any sequence of length >= TACTICAL_POOL_OFFSET.  Returns a
    contiguous float32 array of length ``SINGLE_FRAME_STATE_SIZE`` laid out as
    ``[core(18), elist(22), grouped_objects(112×10)]``.
    """
    arr = np.asarray(wire, dtype=np.float32)
    global_state = arr[0:GLOBAL_FEATURES]
    enemies = _extract_enemy_tokens(arr)
    return np.concatenate([global_state, enemies]).astype(np.float32, copy=False)


# ---------------------------------------------------------------------------
@dataclass
class ServerConfigData:
    host: str = "0.0.0.0"
    port: int = 9998
    max_clients: int = 36
    wire_params_count: int = WIRE_PARAMS_COUNT

SERVER_CONFIG = ServerConfigData()

# ---------------------------------------------------------------------------
@dataclass
class RLConfigData:
    # ── state / action ──────────────────────────────────────────────────
    single_frame_state_size: int = SINGLE_FRAME_STATE_SIZE
    frame_stack: int = FRAME_STACK_COUNT
    state_size: int = MODEL_STATE_SIZE

    # Factored twin-stick action space.  Index 0..7 = direction, 8 = idle.
    num_move_actions: int = 9
    num_fire_actions: int = 9

    @property
    def num_joint_actions(self) -> int:
        return self.num_move_actions * self.num_fire_actions   # 81

    # State-slice geometry (mirrors module constants, exposed for components)
    core_features: int = CORE_FEATURES
    elist_features: int = ELIST_FEATURES
    global_features: int = GLOBAL_FEATURES
    lane_count: int = 0
    lane_features: int = 0
    extra_features: int = 0
    enemy_token_count: int = ENEMY_TOKEN_COUNT
    enemy_token_features: int = ENEMY_TOKEN_FEATURES
    object_token_count: int = ENEMY_TOKEN_COUNT      # compatibility alias
    object_token_features: int = ENEMY_TOKEN_FEATURES

    # ── network architecture ────────────────────────────────────────────
    trunk_hidden: int = 384
    trunk_layers: int = 2
    use_layer_norm: bool = True
    dropout: float = 0.0

    # Lane inputs are intentionally removed for the object-list experiment.
    use_lane_attention: bool = False
    attn_heads: int = 8
    attn_dim: int = 128

    # Self-attention over the 112 grouped object rows.
    use_object_attention: bool = True
    object_attn_heads: int = 8
    object_attn_dim: int = 128

    # Action-conditioned attention for the DQN advantage heads. Direction queries
    # attend over enemy rows so each move/fire/joint action is scored with
    # object evidence relevant to that candidate action.
    use_action_context_attention: bool = True
    action_context_heads: int = 8
    joint_action_embed_dim: int = 32
    action_head_hidden: int = 192

    # Main policy/value head.  Branch heads remain for auxiliary BC + metrics.
    use_joint_head: bool = True
    branch_aux_bc_weight: float = 0.25

    # Distributional C51. Wider support is needed after score-delta rewards: a
    # 150k game is roughly 150 score-reward units before shaping/death terms.
    use_distributional: bool = True
    num_atoms: int = 51
    v_min: float = -200.0
    v_max: float = 500.0

    use_dueling: bool = True

    # ── training ────────────────────────────────────────────────────────
    # Net is tiny (~779k params); the GPU is far from saturated at 768, so a
    # larger batch raises samples/sec (and Rpl/F) at near-zero extra wall-time.
    # Keep sampling/transfers inline: pinned-memory or background CUDA host work
    # re-enables the GIL in the free-threaded Torch build and tanks MAME FPS.
    batch_size: int = 1024
    lr: float = 1e-4
    lr_min: float = 5e-5
    lr_warmup_steps: int = 5_000
    lr_cosine_period: int = 1_000_000
    lr_use_restarts: bool = True
    gamma: float = 0.995
    n_step: int = 12
    max_samples_per_frame: float = 20

    # Replay (PER with proportional priorities).  The grouped-object representation is
    # wider than the old compact lane slice: state/next_state alone cost about
    # 80 GB at 10M transitions with the default 1-frame stack.
    memory_size: int = 10_000_000
    priority_alpha: float = 0.7
    priority_beta_start: float = 0.4
    priority_beta_frames: int = 10_000_000
    priority_eps: float = 1e-6
    per_new_priority_cap_multiplier: float = 3.0
    min_replay_to_train: int = 10_000

    # Elite/rare-event replay. PER keeps surprising transitions hot, but once a
    # valuable event becomes predictable its TD error can fall out of the sample
    # stream. Reserve a small batch quota for broad "interesting" states:
    # scoring bursts, wave transitions, close danger, target-rich enemy rows,
    # human opportunities, and terminal/pre-death cues.
    interesting_replay_fraction: float = 0.08
    interesting_replay_min_score: float = 0.55
    max_interesting_replay_fraction: float = 0.20
    interesting_replay_over_cap_min_score: float = 0.95
    legacy_interest_positive_reward: float = 0.75
    interesting_replay_bank_size: int = 1_000_000

    # Recent replay quota: keep the learner responsive to the behavior it is
    # currently generating instead of letting a 10M buffer dilute new outcomes.
    recent_replay_fraction: float = 0.35
    recent_replay_window: int = 1_000_000

    # Target network (periodic hard sync)
    target_update_period: int = 1_000
    target_tau: float = 1.0

    # Gradient
    grad_clip_norm: float = 5.0

    # ── exploration ─────────────────────────────────────────────────────
    epsilon_start: float = 1.0
    epsilon_end: float = 0.05
    epsilon_decay_frames: int = 5_000_000
    # Most epsilon steps were affordance-guided (a second mini-expert), so only
    # this fraction broke out of the heuristic manifold.  Raised so exploration
    # can actually discover better-than-expert behaviour.
    safe_epsilon_random_fraction: float = 0.25
    safe_epsilon_temperature: float = 0.25
    # While the expert is still injecting a meaningful share of actions, hold a
    # minimum exploration floor so the agent keeps probing its own (non-expert)
    # action space instead of collapsing to greedy + expert before handoff.
    epsilon_expert_floor: float = 0.12
    epsilon_expert_floor_until_ratio: float = 0.15
    # Manual epsilon pulse (fired with P key, runs for N frames then auto-stops).
    manual_pulse_epsilon: float = 0.25
    manual_pulse_duration_frames: int = 750_000
    epsilon: float = 1.0

    # Expert guidance.  Start with substantial demonstrations, but let the DQN
    # get meaningful early control so n-step returns and epsilon exploration are
    # not dominated by expert futures.
    expert_ratio_start: float = 0.60
    # End at zero: any permanent expert injection anchors the behaviour-policy
    # state distribution to expert-reachable trajectories, capping the agent at
    # demonstrator skill.  Let the policy eventually drive entirely on its own.
    expert_ratio_end: float = 0.0
    # Decay is keyed to TRAINING STEPS, not frames.  At 20k+ fps the steady-state
    # frame:step ratio is ~200:1, so a frame-based 2M schedule completed in ~10k
    # gradient steps (2-3 wall-clock minutes) — the policy never had time to learn
    # before the expert handed off.  Steps are FPS-independent and track learning.
    expert_ratio_decay_start_step: int = 0
    expert_ratio_decay_steps: int = 125_000
    expert_ratio: float = 0.60

    # Expert BC — also step-based (same FPS-independence rationale as above).
    # This trains auxiliary bc_* heads and shared trunk features.  The acting
    # policy below is trained by the direct Q-policy + margin losses, then all
    # imitation anchors decay away so DQN can exceed the demonstrator.
    expert_bc_weight: float = 1.0
    expert_bc_decay_start_step: int = 0
    expert_bc_decay_steps: int = 125_000
    expert_bc_min_weight: float = 0.0
    # Directly distill demonstrations into the deployed joint Q policy. Cross
    # entropy treats Q(s, a) / temperature as action logits, giving the acting
    # head a real expert-like launch instead of leaving imitation in side heads.
    expert_q_policy_weight: float = 0.35
    expert_q_policy_temperature: float = 10.0
    expert_q_policy_decay_start_step: int = 0
    expert_q_policy_decay_steps: int = 125_000
    expert_q_policy_min_weight: float = 0.0
    # Q-margin also imitates directly into the acting joint head by constraining
    # Q(expert_action) >= Q(other) + margin on expert-visited states.  Left on
    # permanently it is a hard ceiling, so decay it on the same step schedule.
    expert_q_margin_weight: float = 0.05
    expert_q_margin: float = 0.50
    expert_q_margin_decay_start_step: int = 0
    expert_q_margin_decay_steps: int = 125_000
    expert_q_margin_min_weight: float = 0.0

    # ── reward ──────────────────────────────────────────────────────────
    # Score reward is based on actual game_score delta, not Lua objreward. A
    # 1,000-point event maps to 1.0 reward and a 5,000-point rescue maps to 5.0,
    # comfortably below score_reward_clip so it remains rank-ordered.
    score_reward_scale: float = 0.001
    point_reward_scale: float = 1.0 / score_reward_scale  # Derived: 1000.0
    score_reward_clip: float = 25.0
    subj_reward_scale: float = 0.001
    # Positive subjective shaping is a scaffold, so fade it independently from
    # BCW.  BCW controls imitation loss; SubjW controls dense Lua bonuses.  The
    # socket reward path applies this only when the Lua subjective term is net
    # positive, leaving no-human/human-stall/wall guardrail penalties full size.
    subj_positive_weight: float = 1.0
    subj_positive_decay_start_step: int = 0
    subj_positive_decay_steps: int = 125_000
    subj_positive_min_weight: float = 0.25
    shaping_reward_clip: float = 0.25
    death_penalty: float = 12.0
    reward_clip: float = 30.0
    death_reward_clip: float = 40.0

    # Deliberate hard-state starts when dashboard auto-curriculum is enabled.
    hard_start_min_level: int = 5
    hard_start_wave_spread: int = 8

    # Episode-level elite replay: preserve tails from rare/high-performing
    # episodes, not only individual interesting transitions.
    elite_episode_score_threshold: int = 120_000
    elite_episode_level_threshold: int = 8
    elite_episode_tail_len: int = 768
    elite_episode_priority_boost: float = 3.0
    elite_episode_interest_score: float = 1.0

    # ── fire cadence ────────────────────────────────────────────────────
    # Hold each fire direction stable for this many frames so the game
    # registers reliable shots.  Applied Python-side; the *effective* (held)
    # fire direction is what gets stored in replay and sent to Lua.
    fire_hold_frames: int = 3

    # ── death attribution ───────────────────────────────────────────────
    death_priority_boost: float = 5.0
    pre_death_lookback: int = 120
    pre_death_priority_boost: float = 3.0
    pre_death_reward_lookback: int = 75
    pre_death_base_penalty: float = 0.03
    pre_death_danger_penalty: float = 0.45
    pre_death_max_penalty: float = 0.65
    pre_death_min_danger: float = 0.15
    pre_death_penalize_expert: bool = False

    # ── inference ───────────────────────────────────────────────────────
    use_separate_inference_model: bool = True
    inference_on_cpu: bool = False         # agent falls back to CPU if no CUDA
    train_cuda_device_index: int = 0
    inference_cuda_device_index: int = 1
    inference_sync_steps: int = 5
    inference_batching_enabled: bool = True
    inference_batch_max_size: int = 128
    inference_batch_wait_ms: float = 1.0
    inference_request_timeout_ms: float = 50.0

    # ── background training ─────────────────────────────────────────────
    training_steps_per_cycle: int = 16
    save_interval: int = 10_000

    # ── replay persistence ──────────────────────────────────────────────
    # The replay buffer can be multi-GB; saving it beside every autosave
    # checkpoint causes heavy I/O that can stall training.  Persist it only
    # on forced/manual saves (and shutdown) unless explicitly overridden.
    save_replay_buffer: bool = True       # master switch
    save_replay_on_autosave: bool = False # if True, periodic autosaves persist replay too

    enable_amp: bool = True

    # Autonomous eval-only clients: no expert, fixed low epsilon, no replay writes.
    # With 50 clients this makes client ids 9/19/29/39/49 eval by default.
    eval_client_stride: int = 10
    eval_client_offset: int = 9
    eval_epsilon: float = 0.01


RL_CONFIG = RLConfigData()

# ---------------------------------------------------------------------------
#  Game Settings (shared between dashboard, socket server, and LUA clients)
# ---------------------------------------------------------------------------
# Robotron waves progress 1, 2, 3, …  The operator can start the agent at an
# arbitrary wave for curriculum training.  This list drives the auto-curriculum
# stepping in the socket server.
ROBOTRON_SELECTABLE_LEVELS = list(range(1, 41))

class GameSettings:
    """Thread-safe container for operator-adjustable game settings."""
    def __init__(self):
        self._lock = threading.Lock()
        self._start_advanced: bool = False
        self._start_level_min: int = 1
        self._epsilon_pct: int = -1   # -1 = auto (follow decay), 0-100 = manual override %
        self._expert_pct: int = -1    # -1 = auto (follow decay), 0-100 = manual override %
        self._auto_curriculum: bool = False

    @property
    def start_advanced(self) -> bool:
        with self._lock:
            return self._start_advanced

    @start_advanced.setter
    def start_advanced(self, value: bool):
        with self._lock:
            self._start_advanced = bool(value)

    @property
    def start_level_min(self) -> int:
        with self._lock:
            return self._start_level_min

    @start_level_min.setter
    def start_level_min(self, value: int):
        with self._lock:
            self._start_level_min = max(1, min(255, int(value)))

    @property
    def epsilon_pct(self) -> int:
        with self._lock:
            return self._epsilon_pct

    @epsilon_pct.setter
    def epsilon_pct(self, value: int):
        with self._lock:
            self._epsilon_pct = max(-1, min(100, int(value)))

    @property
    def expert_pct(self) -> int:
        with self._lock:
            return self._expert_pct

    @expert_pct.setter
    def expert_pct(self, value: int):
        with self._lock:
            self._expert_pct = max(-1, min(100, int(value)))

    @property
    def auto_curriculum(self) -> bool:
        with self._lock:
            return self._auto_curriculum

    @auto_curriculum.setter
    def auto_curriculum(self, value: bool):
        with self._lock:
            self._auto_curriculum = bool(value)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "start_advanced": self._start_advanced,
                "start_level_min": self._start_level_min,
                "epsilon_pct": self._epsilon_pct,
                "expert_pct": self._expert_pct,
                "auto_curriculum": self._auto_curriculum,
            }

    def reset(self) -> None:
        """Restore all settings to initial defaults (fresh-start)."""
        with self._lock:
            self._start_advanced = False
            self._start_level_min = 1
            self._epsilon_pct = -1
            self._expert_pct = -1
            self._auto_curriculum = False

    # ── Persistence ───────────────────────────────────────────────

    def save(self, path: str = SETTINGS_PATH) -> None:
        """Write current settings to a JSON file."""
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            data = self.snapshot()
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except Exception:
            pass  # best-effort; don't crash the server

    def load(self, path: str = SETTINGS_PATH) -> None:
        """Restore settings from a JSON file if it exists."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            with self._lock:
                if "start_advanced" in data:
                    self._start_advanced = bool(data["start_advanced"])
                if "start_level_min" in data:
                    self._start_level_min = max(1, min(255, int(data["start_level_min"])))
                if "epsilon_pct" in data:
                    self._epsilon_pct = max(-1, min(100, int(data["epsilon_pct"])))
                if "expert_pct" in data:
                    self._expert_pct = max(-1, min(100, int(data["expert_pct"])))
                if "auto_curriculum" in data:
                    self._auto_curriculum = bool(data["auto_curriculum"])
        except FileNotFoundError:
            pass  # first run — use defaults
        except Exception:
            pass  # corrupted file — use defaults

game_settings = GameSettings()
game_settings.load()

# ---------------------------------------------------------------------------
#  Metrics
# ---------------------------------------------------------------------------
SCORE_1M_WINDOW_FRAMES = 1_000_000
LEVEL_1M_WINDOW_FRAMES = 1_000_000


def _new_metric_ring(size: int) -> np.ndarray:
    return np.zeros(max(1, int(size)), dtype=np.float64)


@dataclass
class MetricsData:
    frame_count: int = 0
    learner_frame_count: int = 0
    total_controls: int = 0
    total_training_steps: int = 0
    memory_buffer_size: int = 0
    client_count: int = 0
    web_client_count: int = 0

    epsilon: float = RL_CONFIG.epsilon_start
    expert_ratio: float = RL_CONFIG.expert_ratio_start

    episode_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    dqn_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    expert_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    subj_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    obj_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    death_rewards: Deque[float] = field(default_factory=lambda: deque(maxlen=50))
    losses: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    fps: float = 0.0
    frames_last_second: int = 0
    last_fps_time: float = 0.0

    # Interval accumulators (reset each display row)
    loss_sum_interval: float = 0.0
    loss_count_interval: int = 0
    agree_sum_interval: float = 0.0
    agree_count_interval: int = 0
    agree_move_sum_interval: float = 0.0
    agree_fire_sum_interval: float = 0.0
    reward_sum_interval: float = 0.0
    reward_count_interval: int = 0
    reward_sum_interval_dqn: float = 0.0
    reward_count_interval_dqn: int = 0
    reward_sum_interval_subj: float = 0.0
    reward_count_interval_subj: int = 0
    reward_sum_interval_obj: float = 0.0
    reward_count_interval_obj: int = 0
    reward_sum_interval_death: float = 0.0
    reward_count_interval_death: int = 0
    eval_reward_sum_interval: float = 0.0
    eval_score_sum_interval: float = 0.0
    eval_level_sum_interval: float = 0.0
    eval_length_sum_interval: float = 0.0
    eval_count_interval: int = 0
    training_steps_interval: int = 0
    frames_count_interval: int = 0
    episode_length_sum_interval: int = 0
    episode_length_count_interval: int = 0
    level_sum_interval: float = 0.0
    level_count_interval: int = 0

    total_inference_time: float = 0.0
    total_inference_requests: int = 0

    last_grad_norm: float = 0.0
    last_loss: float = 0.0
    last_q_mean: float = 0.0
    last_bc_loss: float = 0.0
    last_bc_weight: float = 0.0
    last_subj_positive_weight: float = 1.0
    last_sample_expert_frac: float = 0.0
    last_inference_sync_age: int = 0
    last_priority_mean: float = 0.0
    last_agreement: float = 0.0
    last_train_sample_ms: float = 0.0
    last_train_transfer_ms: float = 0.0
    last_train_compute_ms: float = 0.0
    last_train_priority_ms: float = 0.0
    last_train_step_ms: float = 0.0

    average_level: float = 0.0
    average_game_score: float = 0.0
    score_1m_window: int = SCORE_1M_WINDOW_FRAMES
    score_1m_values: np.ndarray = field(default_factory=lambda: _new_metric_ring(SCORE_1M_WINDOW_FRAMES))
    score_1m_pos: int = 0
    score_1m_count: int = 0
    score_1m_sum: float = 0.0
    score_1m_average: float = 0.0
    level_1m_window: int = LEVEL_1M_WINDOW_FRAMES
    level_1m_values: np.ndarray = field(default_factory=lambda: _new_metric_ring(LEVEL_1M_WINDOW_FRAMES))
    level_1m_pos: int = 0
    level_1m_count: int = 0
    level_1m_sum: float = 0.0
    level_1m_average: float = 0.0
    eval_average_reward: float = 0.0
    eval_average_score: float = 0.0
    eval_average_level: float = 0.0
    eval_average_length: float = 0.0
    eval_episode_count: int = 0
    peak_level: int = 0
    peak_episode_reward: float = 0.0
    peak_game_score: int = 0
    replay_dropped_steps: int = 0
    episodes_this_run: int = 0
    last_target_update_step: int = 0
    last_target_update_time: float = 0.0
    loaded_frame_count: int = 0

    # UI toggles
    override_expert: bool = False
    expert_mode: bool = False
    manual_expert_override: bool = False
    override_epsilon: bool = False
    manual_epsilon_override: bool = False
    manual_pulse_active: bool = False
    manual_pulse_frames_remaining: int = 0
    training_enabled: bool = True
    verbose_mode: bool = False
    saved_expert_ratio: float = 0.99

    global_server: object = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    # ── helpers ─────────────────────────────────────────────────────────
    def update_frame_count(self, delta: int = 1):
        with self.lock:
            d = max(1, delta)
            self.frame_count += d
            self.frames_count_interval += d
            self.frames_last_second += d
            now = time.time()
            if self.last_fps_time == 0:
                self.last_fps_time = now
            elapsed = now - self.last_fps_time
            if elapsed >= 1.0:
                self.fps = self.frames_last_second / elapsed
                self.frames_last_second = 0
                self.last_fps_time = now

    def update_learner_frame_count(self, delta: int = 1):
        with self.lock:
            self.learner_frame_count += max(0, int(delta))

    def note_replay_drop(self, n: int = 1):
        """Record dropped replay transitions (queue overflow) for reporting."""
        with self.lock:
            self.replay_dropped_steps += max(0, int(n))

    def _push_score_1m_locked(self, value: float):
        window = max(1, int(self.score_1m_window))
        if self.score_1m_values.shape[0] != window:
            self.score_1m_values = _new_metric_ring(window)
            self.score_1m_pos = 0
            self.score_1m_count = 0
            self.score_1m_sum = 0.0
            self.score_1m_average = 0.0
        pos = int(self.score_1m_pos) % window
        v = float(value)
        if self.score_1m_count < window:
            self.score_1m_values[pos] = v
            self.score_1m_sum += v
            self.score_1m_count += 1
        else:
            old = float(self.score_1m_values[pos])
            self.score_1m_values[pos] = v
            self.score_1m_sum += v - old
        self.score_1m_pos = (pos + 1) % window
        self.score_1m_average = self.score_1m_sum / max(1, self.score_1m_count)

    def _push_level_1m_locked(self, value: float):
        window = max(1, int(self.level_1m_window))
        if self.level_1m_values.shape[0] != window:
            self.level_1m_values = _new_metric_ring(window)
            self.level_1m_pos = 0
            self.level_1m_count = 0
            self.level_1m_sum = 0.0
            self.level_1m_average = 0.0
        pos = int(self.level_1m_pos) % window
        v = float(value)
        if self.level_1m_count < window:
            self.level_1m_values[pos] = v
            self.level_1m_sum += v
            self.level_1m_count += 1
        else:
            old = float(self.level_1m_values[pos])
            self.level_1m_values[pos] = v
            self.level_1m_sum += v - old
        self.level_1m_pos = (pos + 1) % window
        self.level_1m_average = self.level_1m_sum / max(1, self.level_1m_count)

    def note_game_score(self, score: int, level: int | float | None = None):
        """Thread-safe peak score plus rolling 1M-frame score/level metrics."""
        with self.lock:
            if score > self.peak_game_score:
                self.peak_game_score = int(score)
            self._push_score_1m_locked(float(score))
            if level is not None:
                self._push_level_1m_locked(float(level))

    def note_game_state_averages(self, average_level: float, average_game_score: float, peak_level: int | None = None):
        """Thread-safe live game-state aggregate update."""
        with self.lock:
            self.average_level = float(average_level)
            self.average_game_score = float(average_game_score)
            if peak_level is not None and int(peak_level) > self.peak_level:
                self.peak_level = int(peak_level)

    def get_fps(self) -> float:
        """Return current FPS, decaying to 0 if no frames arrive for >2s."""
        with self.lock:
            if self.last_fps_time > 0:
                stale = time.time() - self.last_fps_time
                if stale >= 2.0:
                    self.fps = 0.0
            return float(self.fps)

    def get_epsilon(self):
        with self.lock:
            return float(self.epsilon)

    def get_effective_epsilon(self) -> float:
        with self.lock:
            ep = game_settings.epsilon_pct
            if ep >= 0:
                return ep / 100.0
            return 0.0 if self.override_epsilon else float(self.epsilon)

    @staticmethod
    def _natural_epsilon_for_learner_frame(learner_frame_count: int) -> float:
        progress = min(1.0, learner_frame_count / max(1, RL_CONFIG.epsilon_decay_frames))
        return RL_CONFIG.epsilon_start + progress * (RL_CONFIG.epsilon_end - RL_CONFIG.epsilon_start)

    def update_epsilon(self):
        with self.lock:
            if self.manual_epsilon_override:
                return self.epsilon
            base = self._natural_epsilon_for_learner_frame(int(self.learner_frame_count))
            # While the expert still drives a meaningful share of frames, hold a
            # minimum exploration floor so the learner keeps probing its own
            # action space instead of collapsing to greedy before handoff.
            floor_until = float(getattr(RL_CONFIG, "epsilon_expert_floor_until_ratio", 0.0))
            if floor_until > 0.0 and float(self.expert_ratio) > floor_until:
                base = max(base, float(getattr(RL_CONFIG, "epsilon_expert_floor", 0.0)))
            if self.manual_pulse_active:
                self.manual_pulse_frames_remaining -= 1
                if self.manual_pulse_frames_remaining <= 0:
                    self.manual_pulse_active = False
                    self.manual_pulse_frames_remaining = 0
                    self.epsilon = base
                else:
                    self.epsilon = max(base, float(RL_CONFIG.manual_pulse_epsilon))
            else:
                self.epsilon = base
            return self.epsilon

    def get_expert_ratio(self):
        with self.lock:
            xp = game_settings.expert_pct
            if xp >= 0:
                return xp / 100.0
            return float(self.expert_ratio)

    def update_expert_ratio(self):
        with self.lock:
            if self.expert_mode or self.override_expert or self.manual_expert_override:
                return self.expert_ratio
            start_step = int(getattr(RL_CONFIG, "expert_ratio_decay_start_step", 0))
            ts = int(self.total_training_steps)
            if ts <= start_step:
                progress = 0.0
            else:
                progress = min(1.0, (ts - start_step) / max(1, RL_CONFIG.expert_ratio_decay_steps))
            self.expert_ratio = RL_CONFIG.expert_ratio_start + progress * (RL_CONFIG.expert_ratio_end - RL_CONFIG.expert_ratio_start)
            return self.expert_ratio

    def add_episode_reward(self, total, dqn, expert, subj=None, obj=None, death=None, length=0):
        with self.lock:
            self.episodes_this_run += 1
            self.episode_rewards.append(float(total))
            self.dqn_rewards.append(float(dqn))
            self.expert_rewards.append(float(expert))
            if subj is not None:
                self.subj_rewards.append(float(subj))
            if obj is not None:
                self.obj_rewards.append(float(obj))
            if death is not None:
                self.death_rewards.append(float(death))
            self.reward_sum_interval += float(total)
            self.reward_count_interval += 1
            self.reward_sum_interval_dqn += float(dqn)
            self.reward_count_interval_dqn += 1
            if subj is not None:
                self.reward_sum_interval_subj += float(subj)
                self.reward_count_interval_subj += 1
            if obj is not None:
                self.reward_sum_interval_obj += float(obj)
                self.reward_count_interval_obj += 1
            if death is not None:
                self.reward_sum_interval_death += float(death)
                self.reward_count_interval_death += 1
            if length > 0:
                self.episode_length_sum_interval += length
                self.episode_length_count_interval += 1
            if float(total) > self.peak_episode_reward:
                self.peak_episode_reward = float(total)

    def add_eval_episode_reward(self, total, score, level, length=0):
        with self.lock:
            self.eval_episode_count += 1
            self.eval_reward_sum_interval += float(total)
            self.eval_score_sum_interval += float(score)
            self.eval_level_sum_interval += float(level)
            self.eval_length_sum_interval += float(length)
            self.eval_count_interval += 1
            n = min(50, self.eval_episode_count)
            # Lightweight EMA-like rolling display without another deque.
            if n <= 1:
                self.eval_average_reward = float(total)
                self.eval_average_score = float(score)
                self.eval_average_level = float(level)
                self.eval_average_length = float(length)
            else:
                a = 1.0 / float(n)
                self.eval_average_reward = (1.0 - a) * self.eval_average_reward + a * float(total)
                self.eval_average_score = (1.0 - a) * self.eval_average_score + a * float(score)
                self.eval_average_level = (1.0 - a) * self.eval_average_level + a * float(level)
                self.eval_average_length = (1.0 - a) * self.eval_average_length + a * float(length)

    def increment_total_controls(self):
        with self.lock:
            self.total_controls += 1

    def update_game_state(self, enemy_seg, open_level):
        pass  # compat stub

    def add_inference_time(self, t: float):
        with self.lock:
            self.total_inference_time += t
            self.total_inference_requests += 1

    # ── UI toggle methods ───────────────────────────────────────────────
    def toggle_override(self, kb=None):
        with self.lock:
            self.override_expert = not self.override_expert
            if self.override_expert:
                self.saved_expert_ratio = self.expert_ratio
                self.expert_ratio = 0.0
            else:
                self.expert_ratio = self.saved_expert_ratio

    def toggle_expert_mode(self, kb=None):
        with self.lock:
            self.expert_mode = not self.expert_mode
            if self.expert_mode:
                self.saved_expert_ratio = self.expert_ratio
                self.expert_ratio = 1.0
            else:
                self.expert_ratio = self.saved_expert_ratio

    def toggle_training_mode(self, kb=None):
        with self.lock:
            self.training_enabled = not self.training_enabled

    def toggle_epsilon_override(self, kb=None):
        with self.lock:
            self.override_epsilon = not self.override_epsilon

    def toggle_verbose_mode(self, kb=None):
        with self.lock:
            self.verbose_mode = not self.verbose_mode

    def toggle_epsilon_pulse(self, kb=None):
        """Fire or cancel the manual epsilon pulse."""
        with self.lock:
            if self.manual_pulse_active:
                # Cancel the running pulse
                self.manual_pulse_active = False
                self.manual_pulse_frames_remaining = 0
            else:
                # Start a new pulse
                self.manual_pulse_active = True
                self.manual_pulse_frames_remaining = int(RL_CONFIG.manual_pulse_duration_frames)

    def increase_expert_ratio(self, kb=None):
        with self.lock:
            p = int(self.expert_ratio * 100)
            p = min(100, p + (1 if p < 10 else 5))
            self.expert_ratio = p / 100.0
            self.manual_expert_override = True

    def decrease_expert_ratio(self, kb=None):
        with self.lock:
            p = int(self.expert_ratio * 100)
            p = max(0, p - (1 if p <= 10 else 5))
            self.expert_ratio = p / 100.0
            self.manual_expert_override = True

    def restore_natural_expert_ratio(self, kb=None):
        with self.lock:
            self.manual_expert_override = False
            start_step = int(getattr(RL_CONFIG, "expert_ratio_decay_start_step", 0))
            ts = int(self.total_training_steps)
            if ts <= start_step:
                progress = 0.0
            else:
                progress = min(1.0, (ts - start_step) / max(1, RL_CONFIG.expert_ratio_decay_steps))
            self.expert_ratio = RL_CONFIG.expert_ratio_start + progress * (RL_CONFIG.expert_ratio_end - RL_CONFIG.expert_ratio_start)

    def increase_epsilon(self, kb=None):
        with self.lock:
            p = int(self.epsilon * 100)
            p = min(100, p + (1 if p < 10 else 5))
            self.epsilon = p / 100.0
            self.manual_epsilon_override = True

    def decrease_epsilon(self, kb=None):
        with self.lock:
            p = int(self.epsilon * 100)
            p = max(0, p - (1 if p <= 10 else 5))
            self.epsilon = p / 100.0
            self.manual_epsilon_override = True

    def restore_natural_epsilon(self, kb=None):
        with self.lock:
            self.manual_epsilon_override = False
            self.epsilon = self._natural_epsilon_for_learner_frame(int(self.learner_frame_count))


metrics = MetricsData()


# ── PlateauPulser stub ──────────────────────────────────────────────────────
# Provides the interface expected by the dashboard, backed by our manual pulse.
class PlateauPulser:
    WATCHING   = "watching"
    PULSING    = "pulsing"
    RECOVERING = "recovering"

    @property
    def state(self) -> str:
        return self.PULSING if metrics.manual_pulse_active else self.WATCHING

    @property
    def total_pulses(self) -> int:
        return 0                       # manual pulse doesn't track lifetime count

    pulse_start_frame: int = 0
    pulse_end_frame: int = 0
    cooldown_multiplier: float = 1.0


plateau_pulser = PlateauPulser()
