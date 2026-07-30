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
                         metrics as config_metrics, RESET_METRICS, IS_INTERACTIVE,
                         decode_token_types, TYPE_ONEHOT_OFFSET, TYPE_CLASS_COUNT)
    from .model import (device, _cuda_device, RainbowNet,
                        NUM_MOVE, NUM_FIRE, NUM_JOINT,
                        combine_action, split_joint_action)
    from .training import train_step, _beta_schedule
    from .replay_buffer import PrioritizedReplayBuffer
except ImportError:
    from config import (RL_CONFIG, MODEL_DIR, LATEST_MODEL_PATH,
                        metrics as config_metrics, RESET_METRICS, IS_INTERACTIVE,
                        decode_token_types, TYPE_ONEHOT_OFFSET, TYPE_CLASS_COUNT)
    from model import (device, _cuda_device, RainbowNet,
                       NUM_MOVE, NUM_FIRE, NUM_JOINT,
                       combine_action, split_joint_action)
    from training import train_step, _beta_schedule
    from replay_buffer import PrioritizedReplayBuffer

metrics = config_metrics

ENGINE_VERSION = 28  # (2026-07-30) 4-frame stacking: state 2782 -> 11128
# (2782 x 4), attacking the reflex bound (EScrF pinned 24-29 through every
# regime; all gains were survival depth).  Trunk dims unchanged from v27.
# v27 checkpoints/banks refuse to load here BY DESIGN — stored states are
# single-frame.  Cold start; v27 peak banked at
# checkpoint_archive/wider_v27_escr1m765k_20260727.pt + auto best saves.
# (was v27:) "wider" branch (2026-07-25): trunk (1600,1200,800) ×1.5
# -> (2400,1800,1200), single-knob width test from frame 0 vs the v24 curve
# (v24 plateau: EScr1M ~500K difficulty-7 era, loss pinned 1.80).  Engine 27
# because 25 is burned (staging episode) and 26 stays reserved for the queued
# rung-3 (2000,1500,1000).  v24/v23 checkpoints refuse to load here BY DESIGN
# — a raw cross-load would shape-skip the trunk into a frankenstein.
# (was v24:) Restored to the record lineage (2026-07-19): the staged
# rung-3 bump (engine 25, 11M dims) never launched and would have orphaned the
# live 1.68M lineage's checkpoints on any restart.  Rung 3, when deliberately
# staged, should use engine 26 (25 is burned by this staging episode).
# v24 = WIDTH ladder rung 2: trunk (1600,1200,800)
# from frame 0, single-knob vs the v23 curve.  v23 = (1280,960,640), the
# 796,526 record-holder — its artifacts are engine-23 and refuse to load here
# (restore recipe: dims + ENGINE_VERSION back, then the archived best).
# (was v23:) +25% width, fp16 deep ring, warm restarts — record 796K.
# (was v22:) attention ablation.  (was v21:) capacity-shrink (768,512,384),
# ~2.6M params, same 2782-wide state.  Version history: v18 = 2056 state;
# v19 = +lanes/grid (4.45M, the 204,914-record architecture); v20 = 9M
# experiment, closed (92K@792K steps — bigger-from-random learns worse).
# The bump refuses v19/v20 checkpoints: a raw cross-load would half-load
# (attention tensors match, trunk/heads shape-skip to random) into a silent
# frankenstein.  To return to the record-holder: dims back to (1024,768,512)
# + object_attn_dim 128, ENGINE_VERSION back to 19, then restore
# checkpoint_archive/best_v19_escr1m204914_migrated.pt (+ its sidecar).


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
        self.behavior_locked = False   # ratchet: pin the fleet to the incumbent
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

        # ── torch.compile placeholders (configured after AMP setup below) ──
        self.compiled_online_joint_dist = None
        self.compiled_online_q_joint = None
        self.compiled_target_joint_dist = None
        self.compiled_infer_q_joint = None

        # Optimizer
        self.optimizer = optim.Adam(self.online_net.parameters(), lr=cfg.lr, eps=1.5e-4)

        # Replay
        self.memory = PrioritizedReplayBuffer(
            capacity=cfg.memory_size,
            state_size=state_size,
            alpha=cfg.priority_alpha,
        )
        # Ring lives in tmpfs (if configured + present) so a spinning disk's
        # writeback can't throttle the transition-storing thread; the hall of
        # fame stays on the model disk (durable across reboot/revert).
        _model_replay = LATEST_MODEL_PATH.rsplit(".", 1)[0] + "_replay"
        self.memory._hof_dir = _model_replay + "_hof"
        self.memory._ephof_dir = _model_replay + "_ephof"
        _tmpfs = str(getattr(cfg, "replay_tmpfs_dir", "") or "").strip()
        if _tmpfs and os.path.isdir(_tmpfs):
            self._ring_dir = os.path.join(_tmpfs, os.path.basename(_model_replay))
        else:
            self._ring_dir = _model_replay
        # Live-mmap backing from birth (Tempest-style): if no saved ring
        # exists yet, back the storage arrays with sparse memmaps now so every
        # save is a fast flush and restarts adopt in place.  With a saved ring
        # present this is a no-op and load() adopts it as before.
        if bool(getattr(cfg, "replay_live_mmap", True)):
            try:
                self.memory.ensure_live_mmap(self._ring_dir)
            except Exception as e:
                print(f"  [WARN] replay live-mmap init failed: {e}")

        # AMP (CUDA only)
        self.use_amp = cfg.enable_amp and (self.device.type == "cuda")
        try:
            self.grad_scaler = torch.amp.GradScaler("cuda", enabled=self.use_amp)
        except Exception:
            self.grad_scaler = torch.cuda.amp.GradScaler(enabled=self.use_amp)

        # torch.compile: MUST complete before the background train thread or
        # socket server exist — all dynamo tracing has to happen serially on
        # this thread (executing a compiled fn while another thread traces
        # raises "using FX to symbolically trace a dynamo-optimized function").
        if bool(getattr(cfg, "use_torch_compile", False)):
            self._setup_torch_compile()

        # Background training thread
        self._train_queue = queue.Queue(maxsize=8)
        self._train_thread = threading.Thread(target=self._background_train, daemon=True, name="TrainWorker")
        self._train_thread.start()

    # ── LR schedule ─────────────────────────────────────────────────────
    def shift_to_hold_gear(self, reason: str = ""):
        """One-way LR downshift: the automated form of the intervention that
        turned the 1.19M collapse into the 1.68M climb.  Re-anchors so the
        hold cosine starts at its top; persists via save()."""
        if getattr(self, "lr_gear", "climb") == "hold":
            return
        self.lr_gear = "hold"
        self.lr_anchor_step = int(self.training_steps)
        print(f"[LR GEARBOX] downshift CLIMB -> HOLD at step {self.training_steps:,}"
              f"{' — ' + reason if reason else ''} (gentle pressure: "
              f"{RL_CONFIG.lr_hold:.1e} -> {RL_CONFIG.lr_hold_min:.1e})")

    def get_lr(self) -> float:
        cfg = RL_CONFIG
        # Gear-aware schedule (see the LR GEARBOX block in config.py).
        if getattr(self, "lr_gear", "climb") == "hold":
            lr_hi = float(getattr(cfg, "lr_hold", 3.5e-5))
            lr_lo = float(getattr(cfg, "lr_hold_min", 2.5e-5))
            period = int(getattr(cfg, "lr_hold_cosine_period", 3_000_000))
        else:
            lr_hi, lr_lo, period = cfg.lr, cfg.lr_min, cfg.lr_cosine_period
        # lr_anchor_step re-bases the warmup+cosine WITHOUT touching
        # training_steps (which the expert/BC schedules key on).
        step = self.training_steps - int(getattr(self, "lr_anchor_step", 0))
        # Manual override (keyboard 1/2/3): scales whatever the gearbox
        # schedule produces, so it composes with gear changes and warmup.
        scale = float(getattr(self, "lr_manual_scale", 1.0))
        if step < cfg.lr_warmup_steps:
            return lr_hi * (step + 1) / max(1, cfg.lr_warmup_steps) * scale
        decay_horizon = max(1, period)
        if bool(getattr(cfg, "lr_use_restarts", False)):
            t = (step - cfg.lr_warmup_steps) % decay_horizon
        else:
            t = min(step - cfg.lr_warmup_steps, decay_horizon)
        cosine = 0.5 * (1.0 + math.cos(math.pi * t / decay_horizon))
        return (lr_lo + (lr_hi - lr_lo) * cosine) * scale

    def _update_lr(self):
        lr = self.get_lr()
        # Ratchet fresh-optimizer protocol: linear LR warmup at the start of a
        # candidate window (Adam with zeroed state takes ~sign(g)*lr steps on
        # its first iterations — unramped, that is itself a shock).
        ws = int(getattr(self, "ratchet_warmup_start_step", -1))
        wn = int(getattr(self, "ratchet_warmup_steps", 0))
        if ws >= 0 and wn > 0:
            done = self.training_steps - ws
            if done < wn:
                lr *= max(0.05, (done + 1) / float(wn))
        for pg in self.optimizer.param_groups:
            pg["lr"] = lr

    def ratchet_begin_window(self, warmup_steps: int = 0):
        """Fresh-optimizer window start: zero Adam moments + arm LR warmup.

        The snapshot/restore round-trip is unaffected — on reject the
        incumbent's optimizer state is restored and the next window zeroes it
        again; on accept the freshly-adapted moments ride along with the new
        incumbent snapshot."""
        with self._sync_lock:
            self.optimizer.state.clear()
        self.ratchet_warmup_start_step = int(self.training_steps)
        self.ratchet_warmup_steps = int(max(0, warmup_steps))

    # ── Inference ───────────────────────────────────────────────────────
    def _setup_torch_compile(self):
        """Compile AND fully warm every hot forward/backward graph, serially.

        Two production failure modes this guards against (both observed):
          1. Cross-thread trace race: executing a dynamo-compiled callable on
             one thread while another thread is mid-trace raises "Detected
             that you are using FX to symbolically trace a dynamo-optimized
             function". So ALL tracing happens here, before the train thread
             and socket server exist.
          2. Recompile-limit fallback: the four entry points share code
             objects (attention internals), and train/eval x device x dtype x
             shape variants exceed dynamo's default cache of 8 — after which
             it silently reverts to eager. Raise the caches first.
        Any failure falls back to eager permanently.
        """
        try:
            t0 = time.time()
            try:
                import torch._dynamo as _dynamo
                for k, v in (("recompile_limit", 64),
                             ("cache_size_limit", 64),
                             ("accumulated_recompile_limit", 1024),
                             ("accumulated_cache_size_limit", 1024)):
                    if hasattr(_dynamo.config, k):
                        setattr(_dynamo.config, k, v)
            except Exception:
                pass

            print("torch.compile: compiling + warming all graphs (one-time)...")
            self.compiled_online_joint_dist = torch.compile(self.online_net.joint_dist, dynamic=False)
            self.compiled_online_q_joint = torch.compile(self.online_net.q_values_joint, dynamic=False)
            self.compiled_target_joint_dist = torch.compile(self.target_net.joint_dist, dynamic=False)
            infer_src = self.infer_net if self.use_separate_inference else self.online_net
            self.compiled_infer_q_joint = torch.compile(infer_src.q_values_joint, dynamic=True)

            bsz = int(RL_CONFIG.batch_size)
            amp_on = bool(self.use_amp) and self.device.type == "cuda"

            # Warm BOTH data-dependent branch variants (encode_tokens forks on
            # all-objects-empty), otherwise the first real batch re-traces at
            # runtime and can race a concurrent thread.
            def _variants(b, dev):
                empty = torch.zeros(b, self.state_size, device=dev)
                popd = torch.rand(b, self.state_size, device=dev)
                return (popd, empty)

            # Training graphs: warm the exact prod variants — online train-mode
            # log=True under autocast (+ backward), online/target eval-path
            # no_grad calls.
            self.online_net.train()
            self.target_net.eval()
            for train_states in _variants(bsz, self.device):
                with torch.autocast("cuda", dtype=torch.float16, enabled=amp_on):
                    logp = self.compiled_online_joint_dist(train_states, log=True)
                    warm_loss = logp.float().mean()
                warm_loss.backward()          # warm the compiled backward graph
                self.online_net.zero_grad(set_to_none=True)
                with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16, enabled=amp_on):
                    self.compiled_online_q_joint(train_states)
                    self.compiled_target_joint_dist(train_states, log=False)
            print(f"torch.compile: training graphs warm ({time.time() - t0:.0f}s)")

            # Inference graph: dynamic shapes, eval mode, no autocast.
            with torch.no_grad():
                for b in (1, 8, 32):
                    for d in _variants(b, self.inference_device):
                        self.compiled_infer_q_joint(d)
            if self.device.type == "cuda":
                torch.cuda.synchronize(self.device)
            if self.inference_device.type == "cuda":
                torch.cuda.synchronize(self.inference_device)
            print(f"torch.compile: all graphs warm in {time.time() - t0:.0f}s")
        except Exception as e:
            print(f"torch.compile unavailable ({type(e).__name__}: {e}) — running eager")
            self.compiled_online_joint_dist = None
            self.compiled_online_q_joint = None
            self.compiled_target_joint_dist = None
            self.compiled_infer_q_joint = None

    def _sync_inference(self, force=False):
        if not self.use_separate_inference:
            return
        # Behavior lock (ratchet, 2026-07-15): when set, the fleet keeps acting
        # on the weights already in the inference net (the measured INCUMBENT)
        # while the online net trains candidate windows.  Without this, every
        # train phase leaks candidate play into the replay ring; as rejected
        # candidates degrade, the DATA degrades, and the next candidate trains
        # on worse data — weights roll back, the ring never does.  Measured
        # overnight 07-15: candidate quality fell 80K -> ~12K across ~100
        # rejected epochs at IDENTICAL restored weights, purely through this
        # data spiral.  With the lock, ring data is pegged to incumbent-quality
        # play forever and every retry is a near-iid draw.  force=True (used by
        # the ratchet's own freeze/restore transitions) still syncs.
        if not force and getattr(self, "behavior_locked", False):
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
                # PERF FIX cherry-picked onto the 415K-era code (2026-07-15).
                # NOT a learning change — this only removes a stall that was
                # corrupting the measurement.
                #
                # The old bare record() ran on THIS (training) thread's current
                # device, so the event landed on GPU0's default stream BEHIND the
                # entire queued training workload.  Every inference batch then
                # waited ~100ms for training kernels before its ~3ms forward
                # (measured live: AvgInf 105ms, FPS 4500->280).  The second-order
                # damage is worse than the latency: frame collection craters while
                # the trainer keeps stepping, so Rpl/F goes 5 -> 75 and the policy
                # gets flogged ~75x per frame on a starved data stream.  The
                # max_samples_per_frame=32 guard does NOT catch this — it averages
                # cumulatively since load, so a transient stall never trips it.
                #
                # Record on the INFERENCE device's stream, after the weight copies
                # have landed.  The training thread absorbs its own queue drain
                # here — a cost it pays at its next sync point anyway.
                if self.device.type == "cuda":
                    torch.cuda.synchronize(self.device)
                if self.inference_device.type == "cuda":
                    torch.cuda.synchronize(self.inference_device)
                    with torch.cuda.device(self.inference_device):
                        self._sync_event.record()
                else:
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
        fn = self.compiled_infer_q_joint or net.q_values_joint
        with torch.no_grad():
            try:
                if self._inference_stream is not None:
                    self._inference_stream.wait_event(self._sync_event)
                    with torch.cuda.stream(self._inference_stream):
                        return fn(states_t)
                elif self.use_separate_inference:
                    with self._sync_lock:
                        return fn(states_t)
                return fn(states_t)
            except Exception as e:
                if self.compiled_infer_q_joint is not None:
                    # Transient (e.g. a rare re-trace racing another thread's
                    # trace): serve this call eagerly, keep compiled for the
                    # next one. Only disable permanently if it keeps failing.
                    self._compiled_infer_failures = getattr(self, "_compiled_infer_failures", 0) + 1
                    if self._compiled_infer_failures >= 20:
                        print(f"[WARN] compiled inference failed {self._compiled_infer_failures}x "
                              f"({type(e).__name__}: {e}) — disabling, eager from now on")
                        self.compiled_infer_q_joint = None
                    elif self._compiled_infer_failures <= 3:
                        print(f"[WARN] compiled inference transient failure "
                              f"({type(e).__name__}: {e}) — serving eagerly")
                    return net.q_values_joint(states_t)
                raise

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
            if feats >= TYPE_ONEHOT_OFFSET + TYPE_CLASS_COUNT:
                type_id = decode_token_types(e)
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
        actor_kind = self.memory.actor_kind_from_name(actor, is_expert)
        pri = float(priority_reward) if priority_reward is not None else 0.0
        # Ensure terminal transitions get a minimum priority floor
        if done:
            boost = float(getattr(RL_CONFIG, "death_priority_boost", 0.0))
            if boost > 0:
                pri = max(abs(pri), boost) * (-1.0 if pri < 0 else 1.0)
        self.memory.add(state, action_idx, float(reward), next_state, bool(done), int(horizon), is_expert,
                priority_hint=pri, interest=interest, actor_kind=actor_kind)
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
                if self.compiled_online_joint_dist is not None:
                    print("[WARN] disabling torch.compile for training after error — falling back to eager")
                    self.compiled_online_joint_dist = None
                    self.compiled_online_q_joint = None
                    self.compiled_target_joint_dist = None
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
        """Load state dict, skipping known non-loadable keys and shape mismatches."""
        model_sd = model.state_dict()
        compatible = {}
        skipped = []
        expected_skips = []
        shape_mismatches = []
        for k, v in ckpt_sd.items():
            if k == "support":
                expected_skips.append(f"{k}: keeping configured C51 support")
                continue
            if k in model_sd:
                if model_sd[k].shape == v.shape:
                    compatible[k] = v
                else:
                    msg = f"{k}: {tuple(v.shape)} → {tuple(model_sd[k].shape)}"
                    skipped.append(msg)
                    shape_mismatches.append(msg)
        if expected_skips:
            print(f"  Info: skipped {len(expected_skips)} expected checkpoint keys:")
            for s in expected_skips[:5]:
                print(f"    {s}")
            if len(expected_skips) > 5:
                print(f"    ... and {len(expected_skips) - 5} more")
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

    # ── policy-ratchet snapshot/restore (2026-07-15) ─────────────────────
    # In-RAM deep copies of EVERYTHING training mutates, so a rejected
    # candidate window can be rolled back exactly — weights, target net,
    # Adam moments, and AMP scaler.  CPU-side (~160MB) so VRAM is untouched.
    # Restore is only legal while the TrainWorker is idle
    # (training_enabled=False): the ratchet controller guarantees that by
    # construction (restores happen inside the frozen eval phase).

    @staticmethod
    def _optimizer_state_to_cpu(sd: dict) -> dict:
        out = {"state": {}, "param_groups": [dict(g) for g in sd.get("param_groups", [])]}
        for k, st in sd.get("state", {}).items():
            out["state"][k] = {
                n: (v.detach().clone().cpu() if torch.is_tensor(v) else v)
                for n, v in st.items()
            }
        return out

    def snapshot_training_state(self) -> dict:
        with self._sync_lock:
            return {
                "online": {k: v.detach().clone().cpu() for k, v in self.online_net.state_dict().items()},
                "target": {k: v.detach().clone().cpu() for k, v in self.target_net.state_dict().items()},
                "optimizer": self._optimizer_state_to_cpu(self.optimizer.state_dict()),
                "scaler": (self.grad_scaler.state_dict() if self.grad_scaler is not None else None),
                "training_steps": int(self.training_steps),
                # Schedule clocks (review fix): expert/epsilon/BC schedules key
                # off metrics counters, not agent.training_steps — a rollback
                # that skips them would retrain every retry under a slightly
                # different objective mixture.
                "metrics_clocks": self._snapshot_metrics_clocks(),
            }

    @staticmethod
    def _snapshot_metrics_clocks() -> dict:
        with metrics.lock:
            return {
                "total_training_steps": int(getattr(metrics, "total_training_steps", 0)),
                "learner_frame_count": int(getattr(metrics, "learner_frame_count", 0)),
                "expert_ratio": float(getattr(metrics, "expert_ratio", 0.0)),
                "epsilon": float(getattr(metrics, "epsilon", 0.0)),
            }

    @staticmethod
    def _restore_metrics_clocks(clocks: dict):
        with metrics.lock:
            for k, v in clocks.items():
                try:
                    setattr(metrics, k, type(getattr(metrics, k))(v))
                except Exception:
                    pass

    def restore_training_state(self, snap: dict, sync_inference: bool = True):
        with self._sync_lock:
            # load_state_dict copies into the existing device tensors, and
            # Optimizer.load_state_dict casts saved state to each param's
            # device/dtype — CPU-held snapshots restore cleanly onto CUDA.
            self.online_net.load_state_dict(snap["online"])
            self.target_net.load_state_dict(snap["target"])
            self.optimizer.load_state_dict(snap["optimizer"])
            if snap.get("scaler") is not None and self.grad_scaler is not None:
                try:
                    self.grad_scaler.load_state_dict(snap["scaler"])
                except Exception:
                    pass
            self.training_steps = int(snap["training_steps"])
        clocks = snap.get("metrics_clocks")
        if clocks:
            self._restore_metrics_clocks(clocks)
        # Push the restored weights to the inference net immediately — the
        # fleet must act on the incumbent, not the rejected candidate.
        # (sync_inference=False is the ratchet pipeline's path: it restores
        # the incumbent into the ONLINE net to train the next candidate while
        # the fleet keeps measuring the CURRENT candidate on the infer net.)
        if sync_inference:
            self._sync_inference(force=True)

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
            "lr_anchor_step": int(getattr(self, "lr_anchor_step", 0)),
            "lr_gear": str(getattr(self, "lr_gear", "climb")),
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
            # Prefer the live ring dir (tmpfs when enabled); fall back to the
            # model-adjacent path for legacy/no-mmap runs.
            buf_path = getattr(self, "_ring_dir", None) or (filepath.rsplit(".", 1)[0] + "_replay")
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
            opt_loaded = False
            if opt_sd and not arch_changed:
                try:
                    self.optimizer.load_state_dict(opt_sd)
                    opt_loaded = True
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
            self.lr_anchor_step = int(ckpt.get("lr_anchor_step", 0))
            # Gear persistence.  Checkpoints from before the gearbox existed
            # load conservatively as HOLD: any pre-gearbox checkpoint worth
            # loading is an advanced policy, and hot LR is what kills those
            # (fresh runs have no checkpoint, so they still start in CLIMB).
            self.lr_gear = str(ckpt.get("lr_gear", "hold"))
            if self.lr_gear == "hold":
                print("  LR gear: HOLD (gentle frontier pressure)")
            if not opt_loaded:
                # Cold-optimizer shock guard: reuse the ratchet's warmup ramp.
                # Fresh Adam at full mid-run LR after the v19 migration deformed
                # the 204,914 policy to ~138K within ~15K steps (2026-07-17);
                # ramping LR from 5% over 8K steps (~5 min) absorbs the cold
                # phase while the moment estimates converge.
                self.ratchet_warmup_start_step = int(self.training_steps)
                self.ratchet_warmup_steps = 8_000
                print("  Optimizer state absent/stale — armed 8,000-step LR warmup")
            self._sync_inference(force=True)

            # The C51 support tensor is intentionally rebuilt from config and is
            # expected to appear as a missing key when loading with strict=False.
            expected_missing = {"support"}
            unexpected_missing = set(m1) - expected_missing
            if unexpected_missing or u1 or m2 or u2:
                print(f"Partial load (missing={len(m1)}, unexpected={len(u1)})")
            elif m1:
                print("Checkpoint load complete (expected C51 support override)")

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
                buf_path = getattr(self, "_ring_dir", None) or (filepath.rsplit(".", 1)[0] + "_replay")
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
