#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN AGENT                                                                                    ||
# ||  Joint Rainbow-lite agent: C51 + dueling + PER + n-step + target net + background training.                  ||
# ==================================================================================================================
"""RainbowAgent — owns the online/target/inference networks, the replay buffer,
the optimizer, and the background training thread.  Actions are twin-stick joint
move/fire decisions (9×9, index 8 = idle on each stick)."""

if __name__ == "__main__":
    print("This is not the main application, run 'main.py' instead")
    exit(1)

import os, sys, time, random, math, threading, queue, traceback, shutil
import select as _select
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

# Optional terminal-control modules for the interactive keyboard handler.
try:
    import termios, tty, fcntl
except Exception:                                   # pragma: no cover - non-POSIX
    termios = tty = fcntl = None
try:
    import msvcrt
except Exception:                                   # pragma: no cover - non-Windows
    msvcrt = None

try:
    from .config import (RL_CONFIG, MODEL_DIR, LATEST_MODEL_PATH,
                         metrics as config_metrics, RESET_METRICS, IS_INTERACTIVE)
    from .model import (device, _cuda_device, RainbowNet,
                        NUM_MOVE, NUM_FIRE, NUM_JOINT,
                        combine_action, split_joint_action)
    from .training import train_step, _beta_schedule
    from .replay_buffer import PrioritizedReplayBuffer
except ImportError:
    from config import (RL_CONFIG, MODEL_DIR, LATEST_MODEL_PATH,
                        metrics as config_metrics, RESET_METRICS, IS_INTERACTIVE)
    from model import (device, _cuda_device, RainbowNet,
                       NUM_MOVE, NUM_FIRE, NUM_JOINT,
                       combine_action, split_joint_action)
    from training import train_step, _beta_schedule
    from replay_buffer import PrioritizedReplayBuffer

metrics = config_metrics

ENGINE_VERSION = 15  # Flat compact-state trunk ablation


class RainbowAgent:
    """Rainbow-lite agent with joint move/fire values, C51, PER, n-step."""

    def __init__(self, state_size: int):
        self.state_size = state_size
        self.device = device
        cfg = RL_CONFIG

        # Counters and locks (must be created before _sync_inference)
        self.training_steps = 0
        self.loaded_training_steps = 0
        self.last_inference_sync = 0
        self._sync_lock = threading.Lock()
        self.training_enabled = True
        self.running = True

        # Networks
        self.online_net = RainbowNet(state_size).to(self.device)
        self.target_net = RainbowNet(state_size).to(self.device)
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()
        self.online_net.train()

        # Inference model (optionally on CPU for non-blocking frame serving)
        self.use_separate_inference = cfg.use_separate_inference_model
        if cfg.inference_on_cpu:
            infer_dev = torch.device("cpu")
        elif torch.cuda.is_available():
            infer_dev = _cuda_device(getattr(cfg, "inference_cuda_device_index", 0))
        else:
            infer_dev = self.device
        self.inference_device = infer_dev

        # ── CUDA streams for overlapping training & inference (no-op on CPU) ──
        self._inference_stream = None
        self._sync_event = None
        if (
            self.use_separate_inference
            and infer_dev.type == "cuda"
            and self.device.type == "cuda"
            and infer_dev.index == self.device.index
        ):
            self._inference_stream = torch.cuda.Stream(device=infer_dev)
            self._sync_event = torch.cuda.Event()

        if self.use_separate_inference:
            self.infer_net = RainbowNet(state_size).to(infer_dev)
            self.infer_net.eval()
            self._sync_inference(force=True)
        else:
            self.infer_net = self.online_net

        _stream_info = f", inference_stream={'yes' if self._inference_stream else 'no'}"
        print(
            f"Agent devices: train={self.device}, infer={self.inference_device}, "
            f"separate_infer={self.use_separate_inference}{_stream_info}"
        )

        # Optimizer
        self.optimizer = optim.Adam(self.online_net.parameters(), lr=cfg.lr, eps=1.5e-4)

        # Replay
        self.memory = PrioritizedReplayBuffer(
            capacity=cfg.memory_size,
            state_size=state_size,
            alpha=cfg.priority_alpha,
        )

        # AMP (CUDA only)
        self.use_amp = cfg.enable_amp and (self.device.type == "cuda")
        try:
            self.grad_scaler = torch.amp.GradScaler("cuda", enabled=self.use_amp)
        except Exception:
            self.grad_scaler = torch.cuda.amp.GradScaler(enabled=self.use_amp)

        # Background training thread
        self._train_queue = queue.Queue(maxsize=8)
        self._train_thread = threading.Thread(target=self._background_train, daemon=True, name="TrainWorker")
        self._train_thread.start()

    # ── LR schedule ─────────────────────────────────────────────────────
    def get_lr(self) -> float:
        cfg = RL_CONFIG
        step = self.training_steps
        if step < cfg.lr_warmup_steps:
            return cfg.lr * (step + 1) / max(1, cfg.lr_warmup_steps)
        decay_horizon = max(1, cfg.lr_cosine_period)
        if bool(getattr(cfg, "lr_use_restarts", False)):
            t = (step - cfg.lr_warmup_steps) % decay_horizon
        else:
            t = min(step - cfg.lr_warmup_steps, decay_horizon)
        cosine = 0.5 * (1.0 + math.cos(math.pi * t / decay_horizon))
        return cfg.lr_min + (cfg.lr - cfg.lr_min) * cosine

    def _update_lr(self):
        lr = self.get_lr()
        for pg in self.optimizer.param_groups:
            pg["lr"] = lr

    # ── Inference ───────────────────────────────────────────────────────
    def _sync_inference(self, force=False):
        if not self.use_separate_inference:
            return
        if not force and (self.training_steps - self.last_inference_sync < RL_CONFIG.inference_sync_steps):
            return
        with self._sync_lock:
            same_cuda_device = (
                self.device.type == "cuda"
                and self.inference_device.type == "cuda"
                and self.device.index == self.inference_device.index
            )
            if self.inference_device.type == "cpu":
                sd = {k: v.detach().cpu() for k, v in self.online_net.state_dict().items()}
            elif same_cuda_device:
                sd = self.online_net.state_dict()
            else:
                sd = {k: v.detach().to(self.inference_device) for k, v in self.online_net.state_dict().items()}
            self.infer_net.load_state_dict(sd, strict=False)
            self.infer_net.eval()
            self.last_inference_sync = self.training_steps
            if self._sync_event is not None:
                self._sync_event.record()

    def _infer_q_branched(self, states_t: torch.Tensor):
        """Return (move_q, fire_q) expected Q-values from the inference net."""
        net = self.infer_net if self.use_separate_inference else self.online_net
        net.eval()
        with torch.no_grad():
            if self._inference_stream is not None:
                self._inference_stream.wait_event(self._sync_event)
                with torch.cuda.stream(self._inference_stream):
                    return net.q_values_branched(states_t)
            elif self.use_separate_inference:
                with self._sync_lock:
                    return net.q_values_branched(states_t)
            return net.q_values_branched(states_t)

    def _infer_q_joint(self, states_t: torch.Tensor):
        """Return joint expected Q-values from the inference net."""
        net = self.infer_net if self.use_separate_inference else self.online_net
        net.eval()
        with torch.no_grad():
            if self._inference_stream is not None:
                self._inference_stream.wait_event(self._sync_event)
                with torch.cuda.stream(self._inference_stream):
                    return net.q_values_joint(states_t)
            elif self.use_separate_inference:
                with self._sync_lock:
                    return net.q_values_joint(states_t)
            return net.q_values_joint(states_t)

    @staticmethod
    def _sample_from_scores(scores: np.ndarray, temperature: float) -> int:
        scores = np.asarray(scores, dtype=np.float64)
        if scores.size <= 0 or not np.isfinite(scores).any():
            return 0
        temp = max(1e-3, float(temperature))
        centered = (scores - np.nanmax(scores)) / temp
        weights = np.exp(np.clip(centered, -30.0, 30.0))
        weights[~np.isfinite(weights)] = 0.0
        total = float(weights.sum())
        if total <= 0.0:
            return int(np.nanargmax(scores))
        return int(np.random.choice(np.arange(scores.size), p=weights / total))

    def _safe_epsilon_action(self, state: np.ndarray) -> Tuple[int, int, bool]:
        """Affordance-guided exploration instead of uniform random twin-stick noise."""
        cfg = RL_CONFIG
        if random.random() < float(getattr(cfg, "safe_epsilon_random_fraction", 0.10)):
            return random.randrange(NUM_MOVE), random.randrange(NUM_FIRE), True
        try:
            start = int(getattr(cfg, "global_features", 40))
            count = int(getattr(cfg, "enemy_token_count", 96))
            feats = int(getattr(cfg, "enemy_token_features", 10))
            enemies = np.asarray(state[start:start + count * feats], dtype=np.float32).reshape(count, feats)
            active = enemies[:, 0] > 0.5
            if not np.any(active):
                return random.randrange(NUM_MOVE), random.randrange(NUM_FIRE), True

            e = enemies[active]
            type_id = np.zeros(e.shape[0], dtype=np.int32)
            if feats > 9:
                type_id = np.rint(np.clip(e[:, 9], 0.0, 1.0) * 8.0).astype(np.int32)
            move_mask = type_id != 7  # ignore humans as danger.
            fire_mask = np.isin(type_id, np.asarray([0, 2, 3, 4, 5, 6, 8], dtype=np.int32))

            move_e = e[move_mask]
            if move_e.size == 0:
                move_e = e
            dx = move_e[:, 1]
            dy = move_e[:, 2]
            dist = np.clip(move_e[:, 3], 0.0, 1.0)
            threat = np.clip(move_e[:, 6], 0.0, 1.0)
            ttc = np.clip(move_e[:, 8], 0.0, 1.0) if feats > 8 else np.ones_like(dist)
            closeness = 1.0 - dist
            weight = (0.25 + 0.75 * threat) * (0.35 + 0.65 * closeness) * (0.5 + 0.5 * (1.0 - ttc))

            dirs = np.asarray([
                [0.0, -1.0], [1.0, -1.0], [1.0, 0.0], [1.0, 1.0],
                [0.0, 1.0], [-1.0, 1.0], [-1.0, 0.0], [-1.0, -1.0],
            ], dtype=np.float32)
            dirs /= np.linalg.norm(dirs, axis=1, keepdims=True).clip(min=1.0)
            vec = np.stack([dx, dy], axis=1)
            vec /= np.linalg.norm(vec, axis=1, keepdims=True).clip(min=1e-6)

            toward = dirs @ vec.T
            move_scores8 = (np.clip(-toward, 0.0, None) * weight).sum(axis=1)
            move_scores8 -= 0.75 * (np.clip(toward, 0.0, None) * weight).sum(axis=1)
            pressure = float(np.nanmax(weight)) if weight.size else 0.0
            idle_move = -0.35 if pressure > 0.15 else 0.05
            move_scores = np.concatenate([move_scores8, np.asarray([idle_move], dtype=np.float32)])

            target_e = e[fire_mask]
            if target_e.size > 0:
                target_dx = target_e[:, 1]
                target_dy = target_e[:, 2]
                target_dist = np.clip(target_e[:, 3], 0.0, 1.0)
                target_threat = np.clip(target_e[:, 6], 0.0, 1.0)
                target_close = 1.0 - target_dist
                target_vec = np.stack([target_dx, target_dy], axis=1)
                target_vec /= np.linalg.norm(target_vec, axis=1, keepdims=True).clip(min=1e-6)
                target_toward = dirs @ target_vec.T
                fire_scores8 = (
                    np.clip(target_toward, 0.0, None)
                    * (0.25 + 0.75 * target_close)
                    * (0.25 + 0.75 * target_threat)
                ).sum(axis=1)
            else:
                fire_scores8 = np.zeros(8, dtype=np.float32)
            target_pressure = float(np.nanmax(fire_scores8)) if fire_scores8.size else 0.0
            idle_fire = 0.10 if target_pressure < 0.05 else -0.35
            fire_scores = np.concatenate([fire_scores8, np.asarray([idle_fire], dtype=np.float32)])
            temp = float(getattr(cfg, "safe_epsilon_temperature", 0.25))
            return self._sample_from_scores(move_scores, temp), self._sample_from_scores(fire_scores, temp), True
        except Exception:
            return random.randrange(NUM_MOVE), random.randrange(NUM_FIRE), True

    def act(self, state: np.ndarray, epsilon: float, locked_fire: int | None = None) -> Tuple[int, int, bool]:
        """Return (move_idx, fire_idx, is_epsilon)."""
        if random.random() < epsilon:
            mv, fr, is_eps = self._safe_epsilon_action(state)
            if locked_fire is not None:
                fr = max(0, min(NUM_FIRE - 1, int(locked_fire)))
            return mv, fr, is_eps

        st = torch.from_numpy(state).float().unsqueeze(0).to(self.inference_device)
        joint_q = self._infer_q_joint(st)
        if locked_fire is not None:
            lf = max(0, min(NUM_FIRE - 1, int(locked_fire)))
            move_idx = int(joint_q.view(1, NUM_MOVE, NUM_FIRE)[0, :, lf].argmax().item())
            return move_idx, lf, False
        joint_idx = int(joint_q.argmax(dim=1).item())
        move_idx, fire_idx = split_joint_action(joint_idx)
        return int(move_idx), int(fire_idx), False

    def debug_q_spread(self, state: np.ndarray):
        """Diagnostic: return (move_q, fire_q) as python lists for one state.

        Used to inspect whether the dueling advantage stream has collapsed
        (near-identical Q across actions ⇒ argmax is effectively random).
        """
        st = torch.from_numpy(np.asarray(state, dtype=np.float32)).float().unsqueeze(0).to(self.inference_device)
        joint_q = self._infer_q_joint(st).view(1, NUM_MOVE, NUM_FIRE)
        move_q = joint_q.max(dim=2).values
        fire_q = joint_q.max(dim=1).values
        return move_q.squeeze(0).detach().cpu().tolist(), fire_q.squeeze(0).detach().cpu().tolist()

    def act_batch(self, states: list, epsilons: list, locked_fires: list | None = None) -> list:
        """Return batched (move_idx, fire_idx, is_epsilon) for aligned lists."""
        n = min(len(states), len(epsilons))
        if n <= 0:
            return []
        if locked_fires is None:
            locked_fires = [None] * n

        actions = [None] * n
        greedy_idx: list = []
        greedy_states: list = []

        for i in range(n):
            eps = float(epsilons[i])
            locked_fire = locked_fires[i] if i < len(locked_fires) else None
            if random.random() < eps:
                mv, fr, is_eps = self._safe_epsilon_action(np.asarray(states[i], dtype=np.float32))
                if locked_fire is not None:
                    fr = max(0, min(NUM_FIRE - 1, int(locked_fire)))
                actions[i] = (mv, fr, is_eps)
            else:
                greedy_idx.append(i)
                greedy_states.append(states[i])

        if greedy_idx:
            batch_np = np.asarray(greedy_states, dtype=np.float32)
            st = torch.from_numpy(batch_np).to(self.inference_device)
            joint_q = self._infer_q_joint(st)
            joint_best = joint_q.argmax(dim=1).detach().cpu().tolist()
            joint_q_np = joint_q.detach().cpu().numpy().reshape(len(greedy_idx), NUM_MOVE, NUM_FIRE)
            for row, (pos, ji) in enumerate(zip(greedy_idx, joint_best)):
                locked_fire = locked_fires[pos] if pos < len(locked_fires) else None
                if locked_fire is not None:
                    fi = max(0, min(NUM_FIRE - 1, int(locked_fire)))
                    mi = int(np.argmax(joint_q_np[row, :, fi]))
                else:
                    mi, fi = split_joint_action(int(ji))
                actions[pos] = (int(mi), int(fi), False)

        return [a if a is not None else (0, 0, False) for a in actions]

    # ── Step (add experience) ───────────────────────────────────────────
    def step(self, state, action, reward, next_state, done, actor="dqn", horizon=1, priority_reward=None, interest=0.0):
        if isinstance(action, (tuple, list)) and len(action) >= 2:
            action_idx = combine_action(action[0], action[1])
        else:
            action_idx = int(max(0, min(NUM_JOINT - 1, int(action))))
        is_expert = 1 if actor == "expert" else 0
        pri = float(priority_reward) if priority_reward is not None else 0.0
        # Ensure terminal transitions get a minimum priority floor
        if done:
            boost = float(getattr(RL_CONFIG, "death_priority_boost", 0.0))
            if boost > 0:
                pri = max(abs(pri), boost) * (-1.0 if pri < 0 else 1.0)
        self.memory.add(state, action_idx, float(reward), next_state, bool(done), int(horizon), is_expert,
                priority_hint=pri, interest=interest)
        # Return the index of the just-written transition for pre-death tracking
        try:
            return int(self.memory.tree.data_ptr - 1) % self.memory.capacity
        except AttributeError:
            return -1

    # ── Background training ─────────────────────────────────────────────
    def _background_train(self):
        pending_batch = None                  # prefetched batch for next step
        while self.running:
            try:
                try:
                    tok = self._train_queue.get_nowait()
                    if tok is None:
                        break
                except queue.Empty:
                    pass

                if not self.training_enabled or not getattr(metrics, "training_enabled", True):
                    pending_batch = None
                    time.sleep(0.01)
                    continue

                did = False
                for _ in range(RL_CONFIG.training_steps_per_cycle):
                    loss = train_step(self, prefetched_batch=pending_batch)
                    pending_batch = None      # consumed
                    if loss is None:
                        break
                    did = True
                    pending_batch = self._prefetch_batch()
                if not did:
                    pending_batch = None
                    time.sleep(0.002)
            except Exception as e:
                pending_batch = None
                print(f"Training error: {e}")
                traceback.print_exc()
                time.sleep(0.1)

    def _prefetch_batch(self):
        """Pre-sample a batch from replay so it's ready for the next step."""
        try:
            if len(self.memory) < max(RL_CONFIG.min_replay_to_train, RL_CONFIG.batch_size):
                return None
            beta = _beta_schedule(metrics.frame_count)
            t0 = time.time()
            batch = self.memory.sample(RL_CONFIG.batch_size, beta=beta)
            self._pending_batch_sample_ms = (time.time() - t0) * 1000.0
            return batch
        except Exception:
            self._pending_batch_sample_ms = 0.0
            return None

    # ── Target update ───────────────────────────────────────────────────
    def update_target(self, tau: float = None):
        if tau is None:
            tau = RL_CONFIG.target_tau
        if tau >= 1.0:
            self.target_net.load_state_dict(self.online_net.state_dict())
        else:
            for tp, op in zip(self.target_net.parameters(), self.online_net.parameters()):
                tp.data.mul_(1.0 - tau).add_(op.data, alpha=tau)
        self.target_net.eval()
        try:
            metrics.last_target_update_step = metrics.total_training_steps
            metrics.last_target_update_time = time.time()
        except Exception:
            pass

    # ── Save / Load ─────────────────────────────────────────────────────
    @staticmethod
    def _load_compatible(model, ckpt_sd):
        """Load state dict, silently skipping keys with shape mismatches."""
        model_sd = model.state_dict()
        compatible = {}
        skipped = []
        shape_mismatches = []
        for k, v in ckpt_sd.items():
            if k == "support":
                skipped.append(f"{k}: keeping configured C51 support")
                continue
            if k in model_sd:
                if model_sd[k].shape == v.shape:
                    compatible[k] = v
                else:
                    msg = f"{k}: {tuple(v.shape)} → {tuple(model_sd[k].shape)}"
                    skipped.append(msg)
                    shape_mismatches.append(msg)
        if skipped:
            print(f"  Skipped {len(skipped)} checkpoint keys:")
            for s in skipped[:5]:
                print(f"    {s}")
            if len(skipped) > 5:
                print(f"    ... and {len(skipped) - 5} more")
        return model.load_state_dict(compatible, strict=False), shape_mismatches

    @staticmethod
    def _text_progress(label: str, frac: float, width: int = 24):
        frac_clamped = max(0.0, min(1.0, float(frac)))
        filled = int(round(frac_clamped * width))
        bar = "#" * filled + "-" * (width - filled)
        sys.stdout.write(f"\r{label} [{bar}] {frac_clamped * 100.0:5.1f}%")
        sys.stdout.flush()
        if frac_clamped >= 1.0:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def save(self, filepath, is_forced_save=False, show_status=True, save_replay=None):
        try:
            with metrics.lock:
                fc = int(metrics.frame_count)
                lfc = int(getattr(metrics, "learner_frame_count", 0))
                ts = int(metrics.total_training_steps)
                er = float(metrics.expert_ratio)
                ep = float(metrics.epsilon)
        except Exception:
            fc, lfc, ts, er, ep = 0, 0, self.training_steps, RL_CONFIG.expert_ratio_start, RL_CONFIG.epsilon_start

        ckpt = {
            "online_state_dict": self.online_net.state_dict(),
            "target_state_dict": self.target_net.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "training_steps": self.training_steps,
            "frame_count": fc,
            "learner_frame_count": lfc,
            "total_training_steps": ts,
            "expert_ratio": er,
            "epsilon": ep,
            "engine_version": ENGINE_VERSION,
            "state_size": self.state_size,
            "single_frame_state_size": int(getattr(RL_CONFIG, "single_frame_state_size", self.state_size)),
            "frame_stack": int(getattr(RL_CONFIG, "frame_stack", 1)),
        }
        if hasattr(self, "grad_scaler") and self.grad_scaler is not None:
            ckpt["grad_scaler_state_dict"] = self.grad_scaler.state_dict()
        if show_status:
            self._text_progress("  Model save", 0.0)

        # Backup existing checkpoint before overwriting
        if os.path.exists(filepath):
            try:
                shutil.copy2(filepath, filepath + ".bak")
            except Exception as e:
                print(f"  [WARN] Backup copy failed: {e}")

        # Atomic save: write to .tmp then rename
        tmp_path = filepath + ".tmp"
        torch.save(ckpt, tmp_path)
        os.replace(tmp_path, filepath)

        if show_status:
            self._text_progress("  Model save", 1.0)
        if is_forced_save and show_status:
            print(f"Model saved to {filepath}")

        # Save replay buffer alongside the model (directory format).  The buffer
        # can be multi-GB, so by default only persist it on forced/manual saves
        # (and shutdown) — periodic autosaves skip it to avoid stalling training.
        if save_replay is None:
            save_replay = is_forced_save or bool(getattr(RL_CONFIG, "save_replay_on_autosave", False))
        if save_replay and bool(getattr(RL_CONFIG, "save_replay_buffer", True)):
            buf_path = filepath.rsplit(".", 1)[0] + "_replay"
            try:
                self.memory.save(buf_path, verbose=bool(show_status))
            except Exception as e:
                print(f"  Replay buffer save failed: {e}")

    def load(self, filepath, show_status=True) -> bool:
        if not os.path.exists(filepath):
            return False
        try:
            if show_status:
                self._text_progress("  Model load", 0.0)
            ckpt = torch.load(filepath, map_location=self.device, weights_only=False)
            if show_status:
                self._text_progress("  Model load", 1.0)

            if int(ckpt.get("engine_version", 0)) < ENGINE_VERSION:
                print("⚠  Incompatible checkpoint engine version — starting fresh.")
                return False

            load1, shape_skips1 = self._load_compatible(self.online_net, ckpt.get("online_state_dict", {}))
            load2, shape_skips2 = self._load_compatible(self.target_net,
                ckpt.get("target_state_dict", ckpt.get("online_state_dict", {})))
            m1, u1 = load1
            m2, u2 = load2
            saved_state_size = ckpt.get("state_size")
            arch_changed = bool(shape_skips1 or shape_skips2)
            if saved_state_size is not None:
                try:
                    arch_changed = arch_changed or int(saved_state_size) != int(self.state_size)
                except Exception:
                    arch_changed = True

            opt_sd = ckpt.get("optimizer_state_dict")
            if opt_sd and not arch_changed:
                try:
                    self.optimizer.load_state_dict(opt_sd)
                except Exception as e:
                    print(f"Optimizer state skipped: {e}")
            elif opt_sd:
                print("Optimizer state skipped: checkpoint state shape differs from current frame stack.")

            gs_sd = ckpt.get("grad_scaler_state_dict")
            if gs_sd and hasattr(self, "grad_scaler") and self.grad_scaler is not None:
                try:
                    self.grad_scaler.load_state_dict(gs_sd)
                except Exception as e:
                    print(f"GradScaler state skipped: {e}")

            self.training_steps = ckpt.get("training_steps", 0)
            self.loaded_training_steps = self.training_steps
            self._sync_inference(force=True)

            if m1 or u1 or m2 or u2:
                print(f"Partial load (missing={len(m1)}, unexpected={len(u1)})")

            try:
                with metrics.lock:
                    if not RESET_METRICS:
                        metrics.expert_ratio = ckpt.get("expert_ratio", RL_CONFIG.expert_ratio_start)
                        metrics.epsilon = ckpt.get("epsilon", RL_CONFIG.epsilon_start)
                        metrics.frame_count = int(ckpt.get("frame_count", 0))
                        metrics.learner_frame_count = int(ckpt.get("learner_frame_count", 0))
                        metrics.loaded_frame_count = metrics.frame_count
                        metrics.total_training_steps = int(ckpt.get("total_training_steps", self.training_steps))
                    else:
                        metrics.expert_ratio = RL_CONFIG.expert_ratio_start
                        metrics.epsilon = RL_CONFIG.epsilon_start
                        metrics.frame_count = 0
                        metrics.learner_frame_count = 0
                        metrics.loaded_frame_count = 0
                        metrics.total_training_steps = self.training_steps
            except Exception:
                pass

            print(f"Loaded v{ENGINE_VERSION} model from {filepath}")

            # Load replay buffer if present alongside the model
            if arch_changed:
                print("  Replay buffer skipped — checkpoint state shape differs from current frame stack.")
            else:
                buf_path = filepath.rsplit(".", 1)[0] + "_replay"
                try:
                    if not self.memory.load(buf_path, verbose=bool(show_status)):
                        print("  No replay buffer found — starting with empty buffer.")
                except Exception as e:
                    print(f"  Replay buffer load failed: {e}")

            return True
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            traceback.print_exc()
            return False

    def flush_replay_buffer(self):
        """Clear the entire replay buffer."""
        self.memory.flush()

    def get_q_value_range(self):
        """Return (min, max) expected Q across a small sampled batch, for display."""
        try:
            if len(self.memory) < 64:
                return float("nan"), float("nan")
            batch = self.memory.sample(64, beta=0.4)
            if batch is None:
                return float("nan"), float("nan")
            st = torch.from_numpy(batch[0]).to(self.inference_device).float()
            joint_q = self._infer_q_joint(st)
            return float(joint_q.min().item()), float(joint_q.max().item())
        except Exception:
            return float("nan"), float("nan")

    def reset_attention_weights(self):
        """Reinitialize enemy/action attention weights, keeping trunk and heads intact."""
        def attention_modules(net):
            mods = []
            if getattr(net, "use_object_attn", False):
                mods.append(net.object_attn)
            if getattr(net, "use_action_context", False):
                mods.append(net.move_context_attn)
                mods.append(net.fire_context_attn)
            if getattr(net, "use_attn", False):
                mods.append(net.lane_attn)
            return mods

        modules = attention_modules(self.online_net)
        if not modules:
            print("No attention layer to reset.")
            return
        for net in (self.online_net, self.target_net):
            for root in attention_modules(net):
                for m in root.modules():
                    if isinstance(m, nn.MultiheadAttention):
                        nn.init.xavier_uniform_(m.in_proj_weight, gain=1.0)
                        if m.in_proj_bias is not None:
                            nn.init.constant_(m.in_proj_bias, 0.0)
                        nn.init.xavier_uniform_(m.out_proj.weight, gain=1.0)
                        if m.out_proj.bias is not None:
                            nn.init.constant_(m.out_proj.bias, 0.0)
                    elif isinstance(m, nn.Linear):
                        nn.init.xavier_uniform_(m.weight, gain=1.0)
                        if m.bias is not None:
                            nn.init.constant_(m.bias, 0.0)
                    elif isinstance(m, nn.Embedding):
                        nn.init.normal_(m.weight, mean=0.0, std=0.02)
                    elif isinstance(m, nn.LayerNorm):
                        nn.init.constant_(m.weight, 1.0)
                        nn.init.constant_(m.bias, 0.0)
        self._sync_inference(force=True)
        attn_param_ids = {id(p) for root in modules for p in root.parameters()}
        for p in list(self.optimizer.state.keys()):
            if id(p) in attn_param_ids:
                self.optimizer.state.pop(p, None)
        print("✓ Enemy/action attention weights and optimizer state reset (trunk + heads preserved)")

    def diagnose_attention(self, num_samples: int = 256) -> str:
        """Report enemy self-attention entropy to gauge whether it's meaningful."""
        if not getattr(self.online_net, "use_object_attn", False):
            return "Object attention is disabled in this model."
        if len(self.memory) < num_samples:
            return f"Need {num_samples} samples in buffer, have {len(self.memory)}."
        batch = self.memory.sample(num_samples, beta=0.4)
        if batch is None:
            return "Could not sample from buffer."
        states = torch.from_numpy(batch[0]).to(self.device).float()
        was_training = self.online_net.training
        self.online_net.eval()
        with torch.no_grad():
            enc = self.online_net.object_attn
            tokens = self.online_net._object_tokens(states)
            present = tokens[:, :, 0] > 0.5
            active_counts = present.sum(dim=1)
            if int(active_counts.max().item()) <= 1:
                if was_training:
                    self.online_net.train()
                mean_active = float(active_counts.float().mean().item())
                return f"Enemy self-attention: only {mean_active:.1f} active rows/sample; entropy not informative yet."
            x = enc.norm(enc.embed(tokens))
            key_padding_mask = ~present
            all_empty = key_padding_mask.all(dim=1)
            if all_empty.any():
                key_padding_mask = key_padding_mask.clone()
                key_padding_mask[all_empty, 0] = False
            _, w = enc.attn(
                x, x, x,
                key_padding_mask=key_padding_mask,
                need_weights=True,
                average_attn_weights=True,
            )  # (B, rows, rows)
            ent_by_query = -(w * w.clamp_min(1e-9).log()).sum(dim=2)
            valid = present & (active_counts > 1).unsqueeze(1)
            ent = ent_by_query[valid].mean().item()
            max_ent = active_counts.float().clamp_min(1.0).log().unsqueeze(1).expand_as(ent_by_query)[valid].mean().item()
        if was_training:
            self.online_net.train()
        pct = 100.0 * ent / max_ent if max_ent > 0 else 0.0
        mean_active = float(active_counts.float().mean().item())
        return (f"Enemy self-attention: mean entropy {ent:.3f}/{max_ent:.3f} "
                f"({pct:.0f}% of uniform), {mean_active:.1f} active rows/sample")

    def stop(self):
        """Signal the background training thread to exit and wait for it."""
        self.running = False
        try:
            self._train_queue.put(None, block=False)
        except queue.Full:
            pass
        try:
            self._train_thread.join(timeout=3.0)
        except Exception:
            pass


# ── Interactive terminal keyboard handler ───────────────────────────────────
class KeyboardHandler:
    """Non-blocking single-key reader for the live training console."""

    def __init__(self):
        self.platform = sys.platform
        self.fd = None
        self.old_settings = None
        if not IS_INTERACTIVE:
            return
        if self.platform in ("linux", "darwin") and termios:
            try:
                self.fd = sys.stdin.fileno()
                self.old_settings = termios.tcgetattr(self.fd)
            except Exception:
                self.fd = None

    def setup_terminal(self):
        if self.platform in ("linux", "darwin") and self.fd is not None and tty and fcntl:
            try:
                # cbreak (not raw): disables canonical mode + echo for single-key
                # reads but KEEPS output post-processing (OPOST/ONLCR) so newlines
                # still map to \r\n — otherwise console rows stair-step diagonally.
                tty.setcbreak(self.fd)
                flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
                fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            except Exception:
                pass

    def __enter__(self):
        self.setup_terminal()
        return self

    def __exit__(self, *a):
        self.restore_terminal()

    def check_key(self):
        if not IS_INTERACTIVE:
            return None
        try:
            if self.platform == "win32" and msvcrt:
                if msvcrt.kbhit():
                    return msvcrt.getch().decode("utf-8")
            elif self.platform in ("linux", "darwin") and self.fd is not None:
                if _select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                    return sys.stdin.read(1)
        except Exception:
            pass
        return None

    def restore_terminal(self):
        if self.platform in ("linux", "darwin") and self.fd is not None and termios:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass

    def set_raw_mode(self):
        if self.platform in ("linux", "darwin") and self.fd is not None and tty:
            try:
                tty.setcbreak(self.fd)
            except Exception:
                pass


def print_with_terminal_restore(kb, *args, **kwargs):
    """Print to the live console, temporarily leaving raw mode so output is clean."""
    if IS_INTERACTIVE and kb and kb.platform in ("linux", "darwin"):
        kb.restore_terminal()
    try:
        text = " ".join(str(a) for a in args)
        for line in text.split("\n"):
            for _ in range(5):
                try:
                    print(line, **kwargs, flush=True)
                    break
                except BlockingIOError:
                    time.sleep(0.05)
    except Exception:
        pass
    if IS_INTERACTIVE and kb and kb.platform in ("linux", "darwin"):
        kb.set_raw_mode()
