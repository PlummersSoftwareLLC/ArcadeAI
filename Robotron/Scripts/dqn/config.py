#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN CONFIGURATION                                                                            ||
# ||  Rainbow-lite engine (C51 + dueling + PER + n-step + target net + expert BC), 8-lane state, factored        ||
# ||  move/fire action heads.  Ported and refactored from the Tempest DQN.                                       ||
# ==================================================================================================================
"""Central configuration: server, RL hyper-parameters, game settings, metrics.

State representation
--------------------
Each frame the Lua client sends ``WIRE_PARAMS_COUNT`` (1478) big-endian f32 values.
The DQN consumes a *compact slice* of that wire — the 18 core features plus the
8 directional "lane" blocks (8 × 30) — for a model input of ``MODEL_STATE_SIZE``
(258) floats.  The remaining wire fields (raw entity pools, the 9×9 tactical
grid) are used by the heuristic expert but are too large to store in the replay
buffer, so only the 258-float model slice is persisted.

Action representation
---------------------
Robotron is twin-stick: an independent 8-way movement stick and 8-way fire
stick, each with an idle option (9 options per stick).  We model this with a
*branching* dueling-distributional head: a shared value stream plus separate
move (9) and fire (9) advantage streams.  The joint action index stored in the
replay buffer is ``move * NUM_FIRE_ACTIONS + fire`` (0..80).
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
WIRE_PARAMS_COUNT = 1478

# Compact model slice: 18 core features + 8 directional lanes × 30 features.
CORE_FEATURES = 18                       # wire[0:18]
LANE_COUNT = 8                           # 8 fire/move directions
LANE_FEATURES = 30                       # features per lane
TACTICAL_LANE_OFFSET = 40                # wire index where lane blocks begin
TACTICAL_LANE_END = TACTICAL_LANE_OFFSET + LANE_COUNT * LANE_FEATURES   # 280
MODEL_STATE_SIZE = CORE_FEATURES + LANE_COUNT * LANE_FEATURES           # 258


def slice_model_state(wire) -> np.ndarray:
    """Extract the compact 258-float model input from a full wire vector.

    ``wire`` may be any sequence of length >= TACTICAL_LANE_END.  Returns a
    contiguous float32 array of length ``MODEL_STATE_SIZE``.
    """
    arr = np.asarray(wire, dtype=np.float32)
    core = arr[0:CORE_FEATURES]
    lanes = arr[TACTICAL_LANE_OFFSET:TACTICAL_LANE_END]
    return np.concatenate([core, lanes]).astype(np.float32, copy=False)


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
    state_size: int = MODEL_STATE_SIZE

    # Factored twin-stick action space.  Index 0..7 = direction, 8 = idle.
    num_move_actions: int = 9
    num_fire_actions: int = 9

    @property
    def num_joint_actions(self) -> int:
        return self.num_move_actions * self.num_fire_actions   # 81

    # State-slice geometry (mirrors module constants, exposed for components)
    core_features: int = CORE_FEATURES
    lane_count: int = LANE_COUNT
    lane_features: int = LANE_FEATURES

    # ── network architecture ────────────────────────────────────────────
    trunk_hidden: int = 384
    trunk_layers: int = 2
    use_layer_norm: bool = True
    dropout: float = 0.0

    # Self-attention over the 8 directional lane tokens
    use_lane_attention: bool = True
    attn_heads: int = 8
    attn_dim: int = 128

    # Distributional C51.  Support [-100,100] keeps a ~20:1 ratio vs reward_clip
    # (=10) so the Bellman target never saturates for large kill/death rewards.
    use_distributional: bool = True
    num_atoms: int = 51
    v_min: float = -100.0
    v_max: float = 100.0

    use_dueling: bool = True

    # ── training ────────────────────────────────────────────────────────
    batch_size: int = 768
    lr: float = 1e-4
    lr_min: float = 4e-5
    lr_warmup_steps: int = 5_000
    lr_cosine_period: int = 3_000_000
    lr_use_restarts: bool = True
    gamma: float = 0.99
    n_step: int = 12
    max_samples_per_frame: float = 20

    # Replay (PER with proportional priorities).  Capacity trimmed from
    # Tempest's 25M to keep host RAM bounded: 258 floats × 2M × 2 × 4B ≈ 4.1 GB.
    memory_size: int = 2_000_000
    priority_alpha: float = 0.7
    priority_beta_start: float = 0.4
    priority_beta_frames: int = 10_000_000
    priority_eps: float = 1e-6
    per_new_priority_cap_multiplier: float = 3.0
    min_replay_to_train: int = 10_000

    # Target network (periodic hard sync)
    target_update_period: int = 2_500
    target_tau: float = 1.0

    # Gradient
    grad_clip_norm: float = 5.0

    # ── exploration ─────────────────────────────────────────────────────
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay_frames: int = 500_000
    # Manual epsilon pulse (fired with P key, runs for N frames then auto-stops).
    manual_pulse_epsilon: float = 0.25
    manual_pulse_duration_frames: int = 750_000
    epsilon: float = 1.0

    # Expert guidance
    # Match the v3 schedule: the heuristic expert drives ~99% of frames early
    # (clean human rescues / data quality), holds until decay_start_frame, then
    # eases to the floor over decay_frames.  A low start ratio interleaves too
    # many policy/epsilon frames and visibly wrecks rescue behaviour.
    expert_ratio_start: float = 0.99
    expert_ratio_end: float = 0.05
    # Decay is keyed to TRAINING STEPS, not frames.  At 20k+ fps the steady-state
    # frame:step ratio is ~200:1, so a frame-based 2M schedule completed in ~10k
    # gradient steps (2-3 wall-clock minutes) — the policy never had time to learn
    # before the expert handed off.  Steps are FPS-independent and track learning.
    expert_ratio_decay_start_step: int = 50_000
    expert_ratio_decay_steps: int = 1_000_000
    expert_ratio: float = 0.99

    # Expert BC — also step-based (same FPS-independence rationale as above).
    expert_bc_weight: float = 1.0
    expert_bc_decay_start_step: int = 250_000
    expert_bc_decay_steps: int = 1_000_000
    expert_bc_min_weight: float = 0.001

    # ── reward ──────────────────────────────────────────────────────────
    obj_reward_scale: float = 0.01
    point_reward_scale: float = 1.0 / obj_reward_scale  # Derived: 100.0
    subj_reward_scale: float = 0.005
    reward_clip: float = 10.0
    death_reward_clip: float = 10.0

    # ── fire cadence ────────────────────────────────────────────────────
    # Hold each fire direction stable for this many frames so the game
    # registers reliable shots.  Applied Python-side; the *effective* (held)
    # fire direction is what gets stored in replay and sent to Lua.
    fire_hold_frames: int = 4

    # ── death attribution ───────────────────────────────────────────────
    death_priority_boost: float = 5.0
    pre_death_lookback: int = 120
    pre_death_priority_boost: float = 2.0

    # ── inference ───────────────────────────────────────────────────────
    use_separate_inference_model: bool = True
    inference_on_cpu: bool = False         # agent falls back to CPU if no CUDA
    train_cuda_device_index: int = 0
    inference_cuda_device_index: int = 1
    inference_sync_steps: int = 25
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
@dataclass
class MetricsData:
    frame_count: int = 0
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
    losses: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    fps: float = 0.0
    frames_last_second: int = 0
    last_fps_time: float = 0.0

    # Interval accumulators (reset each display row)
    loss_sum_interval: float = 0.0
    loss_count_interval: int = 0
    agree_sum_interval: float = 0.0
    agree_count_interval: int = 0
    reward_sum_interval: float = 0.0
    reward_count_interval: int = 0
    reward_sum_interval_dqn: float = 0.0
    reward_count_interval_dqn: int = 0
    reward_sum_interval_subj: float = 0.0
    reward_count_interval_subj: int = 0
    reward_sum_interval_obj: float = 0.0
    reward_count_interval_obj: int = 0
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
    last_priority_mean: float = 0.0
    last_agreement: float = 0.0

    average_level: float = 0.0
    average_game_score: float = 0.0
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

    def note_replay_drop(self, n: int = 1):
        """Record dropped replay transitions (queue overflow) for reporting."""
        with self.lock:
            self.replay_dropped_steps += max(0, int(n))

    def note_game_score(self, score: int):
        """Thread-safe peak game-score update."""
        with self.lock:
            if score > self.peak_game_score:
                self.peak_game_score = int(score)

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
    def _natural_epsilon_for_frame(frame_count: int) -> float:
        progress = min(1.0, frame_count / max(1, RL_CONFIG.epsilon_decay_frames))
        return RL_CONFIG.epsilon_start + progress * (RL_CONFIG.epsilon_end - RL_CONFIG.epsilon_start)

    def update_epsilon(self):
        with self.lock:
            if self.manual_epsilon_override:
                return self.epsilon
            base = self._natural_epsilon_for_frame(int(self.frame_count))
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

    def add_episode_reward(self, total, dqn, expert, subj=None, obj=None, length=0):
        with self.lock:
            self.episodes_this_run += 1
            self.episode_rewards.append(float(total))
            self.dqn_rewards.append(float(dqn))
            self.expert_rewards.append(float(expert))
            if subj is not None:
                self.subj_rewards.append(float(subj))
            if obj is not None:
                self.obj_rewards.append(float(obj))
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
            if length > 0:
                self.episode_length_sum_interval += length
                self.episode_length_count_interval += 1
            if float(total) > self.peak_episode_reward:
                self.peak_episode_reward = float(total)

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
            self.epsilon = self._natural_epsilon_for_frame(int(self.frame_count))


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
