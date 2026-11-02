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
from contextlib import nullcontext
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
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
                         metrics as config_metrics, RESET_METRICS, IS_INTERACTIVE, learning_control,
                         decode_token_types, TYPE_ONEHOT_OFFSET, TYPE_CLASS_COUNT)
    from .model import (device, _cuda_device, RainbowNet,
                        NUM_MOVE, NUM_FIRE, NUM_JOINT,
                        combine_action, split_joint_action)
    from .training import train_step, _beta_schedule, replay_pressure_reached
    from .replay_buffer import PrioritizedReplayBuffer
    from .native_sumtree import batch_update_status
    from .prefetch import ReplayPrefetcher
    from .learning_exposure import OptimizerExposure, exposure_enabled, disabled_snapshot as exposure_disabled_snapshot
    from .pipeline_telemetry import PipelineTelemetry, unavailable_snapshot
    from .exact_inference_graphs import ExactInferenceGraphs, ExactInferenceGraphError, disabled_snapshot
except ImportError:
    from config import (RL_CONFIG, MODEL_DIR, LATEST_MODEL_PATH,
                        metrics as config_metrics, RESET_METRICS, IS_INTERACTIVE, learning_control,
                        decode_token_types, TYPE_ONEHOT_OFFSET, TYPE_CLASS_COUNT)
    from model import (device, _cuda_device, RainbowNet,
                       NUM_MOVE, NUM_FIRE, NUM_JOINT,
                       combine_action, split_joint_action)
    from training import train_step, _beta_schedule, replay_pressure_reached
    from replay_buffer import PrioritizedReplayBuffer
    from native_sumtree import batch_update_status
    from prefetch import ReplayPrefetcher
    from learning_exposure import OptimizerExposure, exposure_enabled, disabled_snapshot as exposure_disabled_snapshot
    from pipeline_telemetry import PipelineTelemetry, unavailable_snapshot
    from exact_inference_graphs import ExactInferenceGraphs, ExactInferenceGraphError, disabled_snapshot

metrics = config_metrics


def _with_training_lock(fn):
    """Serialize model/optimizer snapshots with the background learner."""
    def locked(self, *args, **kwargs):
        with self._training_lock:
            return fn(self, *args, **kwargs)
    return locked


def _with_training_paused(fn):
    """Invalidate replay pipeline work around a checkpoint restoration."""
    def paused(self, *args, **kwargs):
        with self._training_lock:
            try:
                self._pause_prefetch()
                return fn(self, *args, **kwargs)
            finally:
                self._resume_prefetch()
    return paused

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
        # Graph mode is an explicit resume-only startup choice. Fail before
        # allocation when main would skip load() and silently start fresh.
        self._exact_inference_graphs = None
        self._exact_graph_loaded = False
        self._exact_graph_requested = os.getenv("DQN_EXACT_INFERENCE_GRAPHS", "0").strip().lower() in ("1", "true", "yes", "on")
        self._exact_graph_checkpoint = None
        if self._exact_graph_requested:
            required = os.getenv("DQN_EXACT_GRAPH_CHECKPOINT", "").strip()
            ratchet_on = bool(getattr(cfg, "ratchet_enabled", False)) or os.getenv("DQN_RATCHET", "").strip().lower() in ("1", "true", "yes", "on")
            boot_path = LATEST_MODEL_PATH
            incumbent = os.path.join(MODEL_DIR, "robotron_dqn_ratchet_incumbent.pt")
            if ratchet_on and os.path.exists(incumbent):
                boot_path = incumbent
            if not required or not os.path.isfile(required) or os.path.realpath(required) != os.path.realpath(boot_path):
                raise ExactInferenceGraphError("Graph resume requires an existing DQN_EXACT_GRAPH_CHECKPOINT matching main's boot path")
            self._exact_graph_checkpoint = os.path.realpath(required)

        self._priority_metric = str(getattr(cfg, "per_priority_metric", "ce"))
        self._loss_priority_metric = self._priority_metric
        self._priority_phase = None
        if self._priority_metric == "kl" or os.getenv("DQN_PRIORITY_PHASE_RECORD", "").strip():
            try:
                from .priority_phase import PriorityPhase
            except ImportError:
                from priority_phase import PriorityPhase
            if (not self._exact_graph_requested or not bool(getattr(cfg, "compile_full_loss", True))
                    or not bool(getattr(cfg, "use_torch_compile", False))):
                raise RuntimeError("Priority trial requires held resume-only full-loss compile profile")
            self._priority_phase = PriorityPhase(self._priority_metric, self._exact_graph_checkpoint, MODEL_DIR)

        # Counters and locks (must be created before _sync_inference)
        self.training_steps = 0
        self.loaded_training_steps = 0
        self.baseline_batch_size = max(1, int(getattr(cfg, "baseline_batch_size", 512)))
        self.optimized_samples = 0
        self.loaded_optimized_samples = 0
        self.last_inference_sync = 0
        self.last_inference_sync_samples = 0
        self.last_target_update_samples = 0
        self._sync_lock = threading.RLock()
        self._training_lock = threading.RLock()
        self._pipeline_telemetry = PipelineTelemetry(sample_every=20)
        self._learning_optimizer_exposure = OptimizerExposure() if exposure_enabled() else None
        self._prefetch_paused = False
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
            self._inference_stream = torch.cuda.Stream(device=infer_dev, priority=-1)
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
        self.compiled_online_bc_logits = None
        self.compiled_training_outputs = None
        self.compiled_training_loss = None
        self.compiled_training_loss_diagnostics = None
        self.compiled_target_joint_dist = None
        self.compiled_infer_q_joint = None

        # Optimizer
        optimizer_kwargs = {"lr": cfg.lr, "eps": 1.5e-4}
        if self.device.type == "cuda" and bool(getattr(cfg, "optimizer_fused", True)):
            optimizer_kwargs["fused"] = True
        try:
            self.optimizer = optim.Adam(self.online_net.parameters(), **optimizer_kwargs)
        except (TypeError, RuntimeError) as e:
            if "fused" not in optimizer_kwargs:
                raise
            print(f"[WARN] fused Adam unavailable ({e}) — using standard Adam")
            optimizer_kwargs.pop("fused")
            self.optimizer = optim.Adam(self.online_net.parameters(), **optimizer_kwargs)

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
            # (2026-07-31) Fail LOUD if a big ring ends up on RAM arrays.
            # The fallback is a deferred OOM kill: the 10M-cap v28 launch
            # got ENOSPC on the second fallocate, "fell back" to RAM, and
            # the kernel killed the trainer 40 minutes later at 454GB.
            # A saved ring deferring to load() is fine (size adopts there);
            # an EMPTY buffer without mmap backing is only safe when the
            # arrays are genuinely RAM-sized.
            _ring_gb = 2 * int(cfg.memory_size) * int(state_size) * 2 / 1e9
            _saved_ring = False
            try:
                _meta = os.path.join(self._ring_dir, "_meta.npy")
                _saved_ring = os.path.isfile(_meta) and int(np.load(_meta)[1]) > 0
            except Exception:
                pass
            if (self.memory._mmap_dir is None and len(self.memory) == 0
                    and not _saved_ring and _ring_gb > 64):
                raise RuntimeError(
                    f"replay ring needs {_ring_gb:.0f}GB but live-mmap backing "
                    f"failed and no saved ring exists — refusing RAM fallback. "
                    f"Free {cfg.replay_tmpfs_dir} or lower memory_size.")

        # AMP (CUDA only)
        self.use_amp = cfg.enable_amp and (self.device.type == "cuda")
        try:
            self.grad_scaler = torch.amp.GradScaler("cuda", enabled=self.use_amp)
        except Exception:
            self.grad_scaler = torch.cuda.amp.GradScaler(enabled=self.use_amp)

        # Separate startup-only observation. Original compiled loss source,
        # construction, four-output ABI and math are unchanged in both modes.
        self._recomputed_ce_capture = None
        _capture_directory = os.getenv("DQN_RECOMPUTED_CE_CAPTURE_DIR", "").strip()
        if _capture_directory:
            if os.getenv("DQN_EXECUTED_CE_TRACE_DIR", "").strip():
                raise ValueError("Recomputed capture and executed-target trace are mutually exclusive")
            from .recomputed_ce_capture import RecomputedCECapture
            self._recomputed_ce_capture = RecomputedCECapture(_capture_directory, cfg,
                optimizer_exposure=self._learning_optimizer_exposure,
                runtime=dict(torch=str(torch.__version__), cuda=torch.version.cuda,
                    device=str(self.device), use_amp=bool(self.use_amp),
                    fused_adam=bool(self.optimizer.defaults.get("fused", False))))

        # torch.compile: MUST complete before the background train thread or
        # socket server exist — all dynamo tracing has to happen serially on
        # this thread (executing a compiled fn while another thread traces
        # raises "using FX to symbolically trace a dynamo-optimized function").
        if bool(getattr(cfg, "use_torch_compile", False)):
            self._setup_torch_compile()

        # Startup-only capture, before either replay producer or learner exists.
        # load() repeats exact parity under the existing paused/locked guard.
        if self._exact_graph_requested:
            self._setup_exact_inference_graphs()

        self._prefetcher = None
        if bool(getattr(cfg, "replay_prefetch", True)):
            self._prefetcher = ReplayPrefetcher(
                self.memory, int(cfg.batch_size),
                beta_fn=lambda: _beta_schedule(metrics.frame_count),
                device=self.device, use_amp=self.use_amp,
                depth=max(1, int(getattr(cfg, "replay_prefetch_slots", 3))),
                direct_state_fill=bool(getattr(cfg, "replay_direct_state_fill", False)),
                min_replay_size=max(int(cfg.min_replay_to_train), int(cfg.batch_size)),
                enabled_fn=lambda: self.running and self.training_enabled
                and (not self._exact_graph_requested or self._exact_graph_loaded)
                and not self._prefetch_paused and getattr(metrics, "training_enabled", True)
                and not replay_pressure_reached(self),
                trace_observer=self._recomputed_ce_capture,
            )

        # Background training thread
        self._train_queue = queue.Queue(maxsize=8)
        self._train_thread = threading.Thread(target=self._background_train, daemon=True, name="TrainWorker")
        self._train_thread.start()

    # ── LR schedule ─────────────────────────────────────────────────────
    @property
    def schedule_steps(self) -> float:
        """Learning schedule clock in original-batch equivalents."""
        return float(self.optimized_samples) / float(self.baseline_batch_size)

    def _legacy_target_update_samples(self) -> int:
        """Recover the target-update phase from an older step-only checkpoint."""
        period = max(1, int(RL_CONFIG.target_update_period))
        return (int(self.training_steps) // period) * period * self.baseline_batch_size

    def shift_to_hold_gear(self, reason: str = ""):
        """One-way LR downshift: the automated form of the intervention that
        turned the 1.19M collapse into the 1.68M climb.  Re-anchors so the
        hold cosine starts at its top; persists via save()."""
        if getattr(self, "lr_gear", "climb") == "hold":
            return
        self.lr_gear = "hold"
        self.lr_anchor_step = self.schedule_steps
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
        step = self.schedule_steps - float(getattr(self, "lr_anchor_step", 0))
        # Manual override (keyboard 1/2/3): scales whatever the gearbox
        # schedule produces, so it composes with gear changes and warmup.
        scale = float(getattr(self, "lr_manual_scale", 1.0)) * learning_control.lr_scale
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
        ws = float(getattr(self, "ratchet_warmup_start_step", -1))
        wn = int(getattr(self, "ratchet_warmup_steps", 0))
        if ws >= 0 and wn > 0:
            done = self.schedule_steps - ws
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
            exposure = getattr(self, "_learning_optimizer_exposure", None)
            if exposure is not None:
                exposure.new_epoch("ratchet_optimizer_clear_begin")
            self.optimizer.state.clear()
        self.ratchet_warmup_start_step = self.schedule_steps
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
            # Capture is deliberately disabled: training and inference share a
            # GPU and optimizer/weight-copy streams. Inductor still fuses point
            # operations and tunes tensor-core GEMMs without graph lifetime or
            # cross-stream output-buffer hazards.
            compile_options = {"triton.cudagraphs": False}
            if str(getattr(RL_CONFIG, "torch_compile_mode", "default")).startswith("max-autotune"):
                compile_options["max_autotune"] = True
            infer_src = self.infer_net if self.use_separate_inference else self.online_net
            self.compiled_infer_q_joint = torch.compile(
                infer_src.q_values_joint, dynamic=True, options={"triton.cudagraphs": False})

            bsz = int(RL_CONFIG.batch_size)
            amp_on = bool(self.use_amp) and self.device.type == "cuda"

            def _variants(b, dev, dtype=torch.float32):
                empty = torch.zeros(b, self.state_size, device=dev, dtype=dtype)
                popd = torch.rand(b, self.state_size, device=dev, dtype=dtype)
                return (popd, empty)

            self.online_net.train()
            self.target_net.eval()
            if bool(getattr(RL_CONFIG, "compile_full_loss", True)):
                try:
                    from .loss_kernel import TrainingLoss
                except ImportError:
                    from loss_kernel import TrainingLoss
                # Compile the whole tensor loss so C51 projection, expert
                # masks, diagnostics and their many small reductions do not
                # dispatch through Python/GIL while the MAME fleet serves.
                # Diagnostic mode is a static module flag, never a runtime
                # Python branch inside the optimized graph.
                if self._priority_metric == "kl":
                    self.compiled_training_loss = torch.compile(
                        TrainingLoss(self.online_net, self.target_net, RL_CONFIG, diagnostics=False, return_priorities=True),
                        dynamic=False, options=compile_options)
                    self.compiled_training_loss_diagnostics = torch.compile(
                        TrainingLoss(self.online_net, self.target_net, RL_CONFIG, diagnostics=True, return_priorities=True),
                        dynamic=False, options=compile_options)
                else:
                    self.compiled_training_loss = torch.compile(
                        TrainingLoss(self.online_net, self.target_net, RL_CONFIG, diagnostics=False),
                        dynamic=False, options=compile_options)
                    self.compiled_training_loss_diagnostics = torch.compile(
                        TrainingLoss(self.online_net, self.target_net, RL_CONFIG, diagnostics=True),
                        dynamic=False, options=compile_options)
                actions = torch.zeros(bsz, device=self.device, dtype=torch.long)
                rewards = torch.zeros(bsz, device=self.device, dtype=torch.float32)
                dones = torch.zeros_like(rewards)
                horizons = torch.ones_like(rewards)
                expert = torch.ones(bsz, device=self.device, dtype=torch.bool)
                weights = torch.ones_like(rewards)
                schedule = torch.tensor([1.0, 1.0, 1.0], device=self.device, dtype=torch.float32)
                for loss_fn in (self.compiled_training_loss, self.compiled_training_loss_diagnostics):
                    for train_states in _variants(bsz, self.device, torch.float32):
                        next_states = train_states.clone()
                        with torch.autocast("cuda", dtype=torch.float16, enabled=amp_on):
                            if self._priority_metric == "kl":
                                warm_loss, _, _, _, _ = loss_fn(
                                    train_states, actions, rewards, next_states,
                                    dones, horizons, expert, weights, schedule)
                            else:
                                warm_loss, _, _, _ = loss_fn(
                                    train_states, actions, rewards, next_states,
                                    dones, horizons, expert, weights, schedule)
                        warm_loss.backward()
                        self.online_net.zero_grad(set_to_none=True)
            else:
                # Portable opt-out keeps the independently compiled networks
                # and the original Python-side tensor loss available.
                self.compiled_online_joint_dist = torch.compile(
                    self.online_net.joint_dist, dynamic=False, options=compile_options)
                self.compiled_online_q_joint = torch.compile(
                    self.online_net.q_values_joint, dynamic=False, options=compile_options)
                self.compiled_training_outputs = torch.compile(
                    self.online_net.training_outputs, dynamic=False, options=compile_options)
                self.compiled_target_joint_dist = torch.compile(
                    self.target_net.joint_dist, dynamic=False, options=compile_options)
                for train_states in _variants(bsz, self.device, torch.float32):
                    with torch.autocast("cuda", dtype=torch.float16, enabled=amp_on):
                        joint_log_p, joint_logits, move_logits, fire_logits = self.compiled_training_outputs(train_states)
                        actions = torch.zeros(bsz, device=self.device, dtype=torch.long)
                        rows = torch.arange(bsz, device=self.device)
                        selected_log_p = joint_log_p[rows, actions]
                        dense_target = torch.full_like(selected_log_p, 1.0 / int(RL_CONFIG.num_atoms))
                        warm_loss = -(dense_target * selected_log_p).sum(dim=1).mean()
                        warm_loss = warm_loss + F.cross_entropy(joint_logits, actions, reduction="none").mean()
                        warm_loss = warm_loss + F.cross_entropy(move_logits, actions, reduction="none").mean()
                        warm_loss = warm_loss + F.cross_entropy(fire_logits, actions, reduction="none").mean()
                    warm_loss.backward()
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
            if self._priority_phase is not None:
                raise  # Explicit phase cannot silently change the compiled recipe.
            print(f"torch.compile unavailable ({type(e).__name__}: {e}) — running eager")
            self.compiled_online_joint_dist = None
            self.compiled_online_q_joint = None
            self.compiled_online_bc_logits = None
            self.compiled_training_outputs = None
            self.compiled_training_loss = None
            self.compiled_training_loss_diagnostics = None
            self.compiled_target_joint_dist = None
            self.compiled_infer_q_joint = None

    def _setup_exact_inference_graphs(self):
        """Capture all exact sizes serially; no replay/optimizer construction here."""
        if not self.use_separate_inference or self._inference_stream is None:
            raise ExactInferenceGraphError("Exact graphs require the separate same-GPU inference stream")
        try:
            budget = int(os.getenv("DQN_EXACT_GRAPH_BUDGET_BYTES", str(10 * (1 << 30))))
            self._exact_inference_graphs = ExactInferenceGraphs(
                torch, self.infer_net, self.compiled_infer_q_joint,
                stream=self._inference_stream, lock=self._sync_lock,
                state_size=self.state_size, budget_bytes=budget)
        except Exception as exc:
            if isinstance(exc, ExactInferenceGraphError):
                raise
            raise ExactInferenceGraphError("Exact graph startup failed: " + str(exc)) from exc
        return self._exact_inference_graphs

    def _validate_exact_inference_graphs(self):
        """All-shape checkpoint parity while load's learner/prefetch guard holds."""
        graphs = getattr(self, "_exact_inference_graphs", None)
        if graphs is None:
            return
        samples = None
        memory = getattr(self, "memory", None)
        if memory is not None:
            # Fixed rows, never sample replay or advance its RNG/priorities.
            with memory.lock:
                count = min(128, len(memory))
                if count:
                    fixed = np.array(memory.states[:count], dtype=np.float32, copy=True)
            if count:
                samples = torch.from_numpy(np.tile(fixed, (math.ceil(128 / count), 1))[:128].copy())
        graphs.validate(samples=samples)
        self._exact_graph_loaded = True

    def _sync_inference(self, force=False):
        if not self.use_separate_inference:
            return
        if not force and getattr(self, "behavior_locked", False):
            return
        sync_samples = int(RL_CONFIG.inference_sync_steps) * self.baseline_batch_size
        if not force and self.optimized_samples - self.last_inference_sync_samples < sync_samples:
            return
        # Protect CPU checkpoint mutations as well as GPU optimizer writes.
        # Inference requests use their own stream; the training stream waits
        # only for this occasional small weight copy, never a device drain.
        telemetry = getattr(self, "_pipeline_telemetry", None)
        timings = {} if telemetry is not None else None
        started = time.perf_counter() if telemetry is not None else 0.0
        succeeded = False
        try:
            with self._training_lock:
                if timings is not None:
                    sync_started = time.perf_counter()
                    timings["training_lock_wait_ms"] = (sync_started - started) * 1000.0
                with self._sync_lock:
                    if timings is not None:
                        service_started = time.perf_counter()
                        timings["sync_lock_wait_ms"] = (service_started - sync_started) * 1000.0
                    try:
                        if self._inference_stream is not None:
                            training_stream = torch.cuda.current_stream(self.device)
                            source_ready = torch.cuda.Event()
                            source_ready.record(training_stream)
                            with torch.cuda.stream(self._inference_stream):
                                self._inference_stream.wait_event(source_ready)
                                copy_started = time.perf_counter() if timings is not None else 0.0
                                try:
                                    self.infer_net.load_state_dict(self.online_net.state_dict(), strict=False)
                                finally:
                                    if timings is not None:
                                        timings["copy_host_ms"] = (time.perf_counter() - copy_started) * 1000.0
                                self._sync_event.record(self._inference_stream)
                            # Do not let the next optimizer mutation alter source weights
                            # while the inference stream is still copying them.
                            training_stream.wait_event(self._sync_event)
                        else:
                            copy_started = time.perf_counter() if timings is not None else 0.0
                            try:
                                if self.inference_device.type == "cpu":
                                    sd = {k: v.detach().cpu() for k, v in self.online_net.state_dict().items()}
                                elif self.inference_device == self.device:
                                    sd = self.online_net.state_dict()
                                else:
                                    sd = {k: v.detach().to(self.inference_device)
                                          for k, v in self.online_net.state_dict().items()}
                                self.infer_net.load_state_dict(sd, strict=False)
                            finally:
                                if timings is not None:
                                    timings["copy_host_ms"] = (time.perf_counter() - copy_started) * 1000.0
                        self.infer_net.eval()
                        graphs = getattr(self, "_exact_inference_graphs", None)
                        if graphs is not None:
                            graphs.check_storage()
                        self.last_inference_sync = self.training_steps
                        self.last_inference_sync_samples = self.optimized_samples
                        succeeded = True
                    finally:
                        if timings is not None:
                            timings["service_host_ms"] = (time.perf_counter() - service_started) * 1000.0
        finally:
            if timings is not None:
                timings["total_host_ms"] = (time.perf_counter() - started) * 1000.0
                telemetry.record_actor_refresh(timings, error=not succeeded, forced=force)

    def pipeline_telemetry_snapshot(self, reset=False):
        """Return bounded cumulative host timings without taking model locks.

        Inference measures the actual greedy subbatch entering _run_inference.
        Durations include host waiting/enqueue/readback, not CUDA kernel timing.
        Reporting uses reset=False; reset=True is an optional atomic drain.
        """
        telemetry = getattr(self, "_pipeline_telemetry", None)
        snapshot = telemetry.snapshot(reset=reset) if telemetry is not None else unavailable_snapshot()
        graphs = getattr(self, "_exact_inference_graphs", None)
        snapshot["inference_graphs"] = graphs.snapshot() if graphs is not None else disabled_snapshot()
        snapshot["native_batch_update"] = batch_update_status()
        exposure = getattr(self, "_learning_optimizer_exposure", None)
        optimizer_exposure = exposure.snapshot() if exposure is not None else exposure_disabled_snapshot()
        memory = getattr(self, "memory", None)
        getter = getattr(memory, "get_learning_exposure_snapshot", None)
        replay_exposure = getter() if callable(getter) else exposure_disabled_snapshot()
        snapshot["learning_exposure"] = dict(optimizer=optimizer_exposure, replay=replay_exposure)
        return snapshot

    def _validate_measurement_policy(self, state_dict):
        """Require one complete compatible actor, never a partial warm load."""
        if not self.use_separate_inference or self.infer_net is self.online_net:
            raise RuntimeError("Frozen measurement requires a separate inference model")
        expected = self.infer_net.state_dict()
        if set(state_dict) != set(expected):
            missing = sorted(set(expected) - set(state_dict))
            unexpected = sorted(set(state_dict) - set(expected))
            raise ValueError(f"Inference policy keys differ: missing={missing}, unexpected={unexpected}")
        for name, value in state_dict.items():
            if not isinstance(value, torch.Tensor) or value.shape != expected[name].shape:
                raise ValueError(f"Inference policy tensor shape differs: {name}")
            if value.dtype != expected[name].dtype:
                raise ValueError(f"Inference policy tensor dtype differs: {name}")
            if value.is_floating_point() and not bool(torch.isfinite(value).all()):
                raise ValueError(f"Inference policy contains non-finite values: {name}")
        if "support" in expected and not torch.equal(
                state_dict["support"].detach().cpu(), expected["support"].detach().cpu()):
            raise ValueError("Inference policy C51 support differs from the live actor")

    @_with_training_lock
    def capture_inference_policy(self):
        """Copy current online actor weights without optimizer/clock mutation."""
        if not self.use_separate_inference or self.infer_net is self.online_net:
            raise RuntimeError("Frozen measurement requires a separate inference model")
        state = {name: value.detach().clone().cpu()
                 for name, value in self.online_net.state_dict().items()}
        self._validate_measurement_policy(state)
        return state

    def prepare_inference_checkpoint(self, filepath):
        """Validate a preserved actor on CPU before pausing the live learner."""
        checkpoint = torch.load(filepath, map_location="cpu", weights_only=True)
        if int(checkpoint.get("engine_version", -1)) != ENGINE_VERSION:
            raise ValueError("Measurement checkpoint engine version differs")
        if int(checkpoint.get("state_size", -1)) != int(self.state_size):
            raise ValueError("Measurement checkpoint state size differs")
        state = checkpoint.get("online_state_dict")
        if not isinstance(state, dict):
            raise ValueError("Measurement checkpoint has no online actor state")
        self._validate_measurement_policy(state)
        return state

    def install_inference_policy(self, state_dict):
        """Replace only existing actor tensor values while training is paused.

        Keeping the infer_net object and its parameter storage preserves the
        compiled callable's binding. No online/target parameters, optimizer,
        schedule clocks, or inference-sync sample markers are changed.
        """
        with self._training_lock, self._sync_lock:
            if self.training_enabled:
                raise RuntimeError("Pause training before installing a measurement actor")
            if not self.behavior_locked:
                raise RuntimeError("Lock periodic actor sync before installing a measurement actor")
            self._validate_measurement_policy(state_dict)
            if self._inference_stream is not None:
                self._inference_stream.synchronize()
                with torch.cuda.stream(self._inference_stream):
                    self.infer_net.load_state_dict(state_dict, strict=True)
                    self._sync_event.record(self._inference_stream)
                self._sync_event.synchronize()
            elif self.inference_device.type == "cuda":
                # A different inference GPU has no dedicated shared-GPU stream.
                with torch.cuda.device(self.inference_device):
                    torch.cuda.synchronize(self.inference_device)
                    self.infer_net.load_state_dict(state_dict, strict=True)
                    torch.cuda.synchronize(self.inference_device)
            else:
                self.infer_net.load_state_dict(state_dict, strict=True)
            self.infer_net.eval()
            graphs = getattr(self, "_exact_inference_graphs", None)
            if graphs is not None:
                graphs.check_storage()

    def _run_inference(self, fn, states_t: torch.Tensor, return_cpu=False, *, graph_cpu=False):
        """Dispatch on the dedicated stream with explicit tensor ownership.

        CPU inputs are transferred on the inference stream so they do not
        queue behind training. Live action selection also consumes results on
        that stream, avoiding a wait inserted into the trainer's default
        stream. GPU-returning diagnostic callers receive a stream dependency.
        """
        graphs = getattr(self, "_exact_inference_graphs", None) if graph_cpu else None
        if graph_cpu and (graphs is None or not return_cpu or self._inference_stream is None):
            raise ExactInferenceGraphError("Invalid exact-graph inference route")
        telemetry = getattr(self, "_pipeline_telemetry", None)
        sampled = telemetry.begin_inference() if telemetry is not None else False
        timings = {"batch_size": int(states_t.shape[0])} if sampled else None
        started = time.perf_counter() if sampled else 0.0
        succeeded = False
        train_guard = self._training_lock if not self.use_separate_inference else nullcontext()
        try:
            with train_guard:
                if sampled:
                    sync_started = time.perf_counter()
                    if not self.use_separate_inference:
                        timings["training_lock_wait_ms"] = (sync_started - started) * 1000.0
                with self._sync_lock:
                    if sampled:
                        service_started = time.perf_counter()
                        timings["sync_lock_wait_ms"] = (service_started - sync_started) * 1000.0
                    try:
                        with torch.no_grad():
                            if self._inference_stream is None:
                                transfer_started = time.perf_counter() if sampled else 0.0
                                try:
                                    inputs = states_t.to(self.inference_device)
                                finally:
                                    if sampled:
                                        timings["input_transfer_host_ms"] = (time.perf_counter() - transfer_started) * 1000.0
                                dispatch_started = time.perf_counter() if sampled else 0.0
                                try:
                                    result = fn(inputs)
                                finally:
                                    if sampled:
                                        timings["dispatch_host_ms"] = (time.perf_counter() - dispatch_started) * 1000.0
                                if return_cpu:
                                    readback_started = time.perf_counter() if sampled else 0.0
                                    try:
                                        result = (tuple(x.detach().cpu() for x in result)
                                                  if isinstance(result, tuple) else result.detach().cpu())
                                    finally:
                                        if sampled:
                                            timings["cpu_readback_host_ms"] = (time.perf_counter() - readback_started) * 1000.0
                            else:
                                caller_stream = torch.cuda.current_stream(self.inference_device)
                                if states_t.is_cuda:
                                    self._inference_stream.wait_stream(caller_stream)
                                with torch.cuda.stream(self._inference_stream):
                                    transfer_started = time.perf_counter() if sampled else 0.0
                                    try:
                                        if graph_cpu:
                                            inputs = graphs.prepare_input(states_t)
                                        else:
                                            inputs = states_t.to(self.inference_device)
                                            if inputs.is_cuda:
                                                inputs.record_stream(self._inference_stream)
                                    finally:
                                        if sampled:
                                            timings["input_transfer_host_ms"] = (time.perf_counter() - transfer_started) * 1000.0
                                    dispatch_started = time.perf_counter() if sampled else 0.0
                                    try:
                                        result = graphs.replay_prepared(inputs) if graph_cpu else fn(inputs)
                                    finally:
                                        if sampled:
                                            timings["dispatch_host_ms"] = (time.perf_counter() - dispatch_started) * 1000.0
                                    if return_cpu:
                                        readback_started = time.perf_counter() if sampled else 0.0
                                        try:
                                            result = (tuple(x.detach().cpu() for x in result)
                                                      if isinstance(result, tuple) else result.detach().cpu())
                                            if graph_cpu:
                                                graphs.complete_cpu_return()
                                        finally:
                                            if sampled:
                                                timings["cpu_readback_host_ms"] = (time.perf_counter() - readback_started) * 1000.0
                                if not return_cpu:
                                    # Diagnostics need the existing stream dependency
                                    # and ownership before returning CUDA outputs.
                                    caller_stream.wait_stream(self._inference_stream)
                                    outputs = result if isinstance(result, tuple) else (result,)
                                    for output in outputs:
                                        output.record_stream(caller_stream)
                            succeeded = True
                            return result
                    except Exception as exc:
                        if graph_cpu:
                            raise graphs.fail(exc) from exc
                        raise
                    finally:
                        if sampled:
                            timings["service_host_ms"] = (time.perf_counter() - service_started) * 1000.0
        finally:
            # Do not nest this recorder lock inside the inference sync lock.
            if sampled:
                timings["total_host_ms"] = (time.perf_counter() - started) * 1000.0
                telemetry.record_inference(timings, error=not succeeded)

    def _infer_q_branched(self, states_t: torch.Tensor, return_cpu=False):
        net = self.infer_net if self.use_separate_inference else self.online_net
        net.eval()
        return self._run_inference(net.q_values_branched, states_t, return_cpu=return_cpu)

    def _infer_q_joint(self, states_t: torch.Tensor, return_cpu=False):
        net = self.infer_net if self.use_separate_inference else self.online_net
        net.eval()

        graphs = getattr(self, "_exact_inference_graphs", None)
        if graphs is not None and self.compiled_infer_q_joint is not graphs.compiled:
            raise graphs.fail(ExactInferenceGraphError("Captured compiled actor callable changed"))
        if graphs is not None and not getattr(self, "_exact_graph_loaded", False):
            raise graphs.fail(ExactInferenceGraphError("Graph checkpoint has not passed post-load validation"))
        if graphs is not None and return_cpu:
            return self._run_inference(self.compiled_infer_q_joint, states_t,
                                       return_cpu=True, graph_cpu=True)

        def forward(inputs):
            if graphs is not None:
                graphs.note_compiled_diagnostic()
            fn = self.compiled_infer_q_joint or net.q_values_joint
            try:
                return fn(inputs)
            except Exception as e:
                if graphs is not None:
                    raise graphs.fail(e) from e
                if self.compiled_infer_q_joint is None:
                    raise
                # Disable the failing callable immediately: repeated retracing
                # can contend with training compilation and worsen latency.
                print(f"[WARN] compiled inference failed ({type(e).__name__}: {e}) — falling back to eager")
                self.compiled_infer_q_joint = None
                return net.q_values_joint(inputs)

        return self._run_inference(forward, states_t, return_cpu=return_cpu)

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

        st = torch.from_numpy(state).float().unsqueeze(0)
        joint_q = self._infer_q_joint(st, return_cpu=True)
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
        st = torch.from_numpy(np.asarray(state, dtype=np.float32)).float().unsqueeze(0)
        joint_q = self._infer_q_joint(st, return_cpu=True).view(1, NUM_MOVE, NUM_FIRE)
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
            st = torch.from_numpy(batch_np)
            joint_q = self._infer_q_joint(st, return_cpu=True)
            joint_q_np = joint_q.numpy().reshape(len(greedy_idx), NUM_MOVE, NUM_FIRE)
            joint_best = joint_q_np.reshape(len(greedy_idx), NUM_JOINT).argmax(axis=1).tolist()
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
        if getattr(self.memory, "_insert_exposure", None) is None:
            self.memory.add(state, action_idx, float(reward), next_state, bool(done), int(horizon), is_expert,
                    priority_hint=pri, interest=interest, actor_kind=actor_kind)
        else:
            self.memory.add(state, action_idx, float(reward), next_state, bool(done), int(horizon), is_expert,
                    priority_hint=pri, interest=interest, actor_kind=actor_kind, source_actor=actor)
        # Return the index of the just-written transition for pre-death tracking
        try:
            return int(self.memory.tree.data_ptr - 1) % self.memory.capacity
        except AttributeError:
            return -1

    # ── Background training ─────────────────────────────────────────────
    def _background_train(self):
        while self.running:
            # Resume-only opt-in never optimizes random weights before load.
            if getattr(self, "_exact_graph_requested", False) and not self._exact_graph_loaded:
                time.sleep(0.01)
                continue
            pending_batch = None
            try:
                try:
                    tok = self._train_queue.get_nowait()
                    if tok is None:
                        break
                except queue.Empty:
                    pass

                if not self.training_enabled or not getattr(metrics, "training_enabled", True):
                    time.sleep(0.01)
                    continue

                did = False
                for _ in range(RL_CONFIG.training_steps_per_cycle):
                    if not self.running:
                        break
                    if replay_pressure_reached(self):
                        metrics.replay_pressure_waits = getattr(metrics, "replay_pressure_waits", 0) + 1
                        break
                    pending_batch = self._prefetch_batch()
                    if self._prefetcher is not None and pending_batch is None:
                        break
                    with self._training_lock:
                        if pending_batch is not None and not getattr(pending_batch, "is_current", True):
                            pending_batch.release()
                            pending_batch = None
                            continue
                        try:
                            loss = train_step(self, prefetched_batch=pending_batch)
                        finally:
                            if pending_batch is not None and hasattr(pending_batch, "release"):
                                pending_batch.release()
                            pending_batch = None
                    if loss is None:
                        break
                    did = True
                if not did:
                    time.sleep(0.002)
            except Exception as e:
                if pending_batch is not None and hasattr(pending_batch, "release"):
                    pending_batch.release()
                print(f"Training error: {e}")
                if self._priority_phase is not None:
                    self._priority_phase.invalidate(e)
                    self.training_enabled = False
                    traceback.print_exc()
                    continue  # Retain compiler/outcome failure; no fallback/rescue.
                traceback.print_exc()
                if (self.compiled_online_joint_dist is not None
                        or self.compiled_training_outputs is not None
                        or self.compiled_training_loss is not None):
                    print("[WARN] disabling torch.compile for training after error — falling back to eager")
                    self.compiled_online_joint_dist = None
                    self.compiled_online_q_joint = None
                    self.compiled_online_bc_logits = None
                    self.compiled_training_outputs = None
                    self.compiled_training_loss = None
                    self.compiled_training_loss_diagnostics = None
                    self.compiled_target_joint_dist = None
                time.sleep(0.1)

    def _prefetch_batch(self):
        """Consume producer-prepared replay; retain a portable fallback."""
        if self._prefetcher is not None:
            try:
                return self._prefetcher.get(timeout=0.05)
            except Exception as e:
                print(f"[WARN] replay prefetch failed ({e}) — falling back to synchronous sampling")
                self._prefetcher.close()
                self._prefetcher = None
        try:
            if len(self.memory) < max(RL_CONFIG.min_replay_to_train, RL_CONFIG.batch_size):
                return None
            beta = _beta_schedule(metrics.frame_count)
            t0 = time.perf_counter()
            if self._recomputed_ce_capture is None:
                batch = self.memory.sample(RL_CONFIG.batch_size, beta=beta)
            else:
                batch = self._recomputed_ce_capture.sample(self.memory, RL_CONFIG.batch_size, beta)
            self._pending_batch_sample_ms = (time.perf_counter() - t0) * 1000.0
            return batch
        except Exception:
            self._pending_batch_sample_ms = 0.0
            return None

    def _pause_prefetch(self):
        self._prefetch_paused = True
        if self._prefetcher is not None:
            if not self._prefetcher.invalidate(wait=True, timeout=10.0):
                raise TimeoutError("Replay producer did not quiesce; refusing replay/checkpoint mutation")

    def _resume_prefetch(self):
        if self._prefetcher is not None:
            if not self._prefetcher.invalidate(wait=True, timeout=10.0):
                raise TimeoutError("Replay producer did not quiesce; leaving prefetch paused")
        self._prefetch_paused = False

    # ── Target update ───────────────────────────────────────────────────
    def update_target(self, tau: float = None):
        telemetry = getattr(self, "_pipeline_telemetry", None)
        started = time.perf_counter() if telemetry is not None else 0.0
        succeeded = False
        try:
            if tau is None:
                tau = RL_CONFIG.target_tau
            if tau >= 1.0:
                self.target_net.load_state_dict(self.online_net.state_dict())
            else:
                for tp, op in zip(self.target_net.parameters(), self.online_net.parameters()):
                    tp.data.mul_(1.0 - tau).add_(op.data, alpha=tau)
            self.target_net.eval()
            self.last_target_update_samples = self.optimized_samples
            try:
                metrics.last_target_update_step = metrics.total_training_steps
                metrics.last_target_update_time = time.time()
            except Exception:
                pass
            succeeded = True
        finally:
            if telemetry is not None:
                telemetry.record_target_refresh((time.perf_counter() - started) * 1000.0,
                                                error=not succeeded)

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

    def _load_optimizer_state_dict(self, state_dict: dict):
        """Keep this run's Adam implementation while restoring its moments.

        Older checkpoints contain fused=None in their parameter groups; plain
        load_state_dict would overwrite a newly selected fused CUDA optimizer.
        Set implementation flags before loading so PyTorch also places Adam's
        step counters on CUDA as required by its fused kernels.
        """
        fused = self.optimizer.defaults.get("fused", None)
        foreach = False if fused else self.optimizer.defaults.get("foreach", None)
        restored = dict(state_dict)
        restored["param_groups"] = [
            dict(group, fused=fused, foreach=foreach)
            for group in state_dict.get("param_groups", [])
        ]
        exposure = getattr(self, "_learning_optimizer_exposure", None)
        if exposure is not None:
            exposure.new_epoch("optimizer_restore_begin")
        self.optimizer.load_state_dict(restored)

    @_with_training_lock
    def snapshot_training_state(self) -> dict:
        with self._sync_lock:
            return {
                "online": {k: v.detach().clone().cpu() for k, v in self.online_net.state_dict().items()},
                "target": {k: v.detach().clone().cpu() for k, v in self.target_net.state_dict().items()},
                "optimizer": self._optimizer_state_to_cpu(self.optimizer.state_dict()),
                "scaler": (self.grad_scaler.state_dict() if self.grad_scaler is not None else None),
                "training_steps": int(self.training_steps),
                "optimized_samples": int(self.optimized_samples),
                "baseline_batch_size": int(self.baseline_batch_size),
                "last_target_update_samples": int(self.last_target_update_samples),
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
                "total_optimized_samples": int(getattr(metrics, "total_optimized_samples", 0)),
                "learner_frame_count": int(getattr(metrics, "learner_frame_count", 0)),
                "measurement_frame_count": int(getattr(metrics, "measurement_frame_count", 0)),
                "loaded_measurement_frame_count": int(getattr(metrics, "loaded_measurement_frame_count", 0)),
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

    @_with_training_paused
    def restore_training_state(self, snap: dict, sync_inference: bool = True):
        with self._sync_lock:
            # load_state_dict copies into the existing device tensors, and
            # Optimizer.load_state_dict casts saved state to each param's
            # device/dtype — CPU-held snapshots restore cleanly onto CUDA.
            self.online_net.load_state_dict(snap["online"])
            self.target_net.load_state_dict(snap["target"])
            self._load_optimizer_state_dict(snap["optimizer"])
            if snap.get("scaler") is not None and self.grad_scaler is not None:
                try:
                    self.grad_scaler.load_state_dict(snap["scaler"])
                except Exception:
                    pass
            self.training_steps = int(snap["training_steps"])
            self.optimized_samples = int(snap.get("optimized_samples", self.training_steps * self.baseline_batch_size))
            self.last_target_update_samples = int(snap.get("last_target_update_samples", self._legacy_target_update_samples()))
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

    @_with_training_lock
    def save(self, filepath, is_forced_save=False, show_status=True, save_replay=None):
        try:
            with metrics.lock:
                fc = int(metrics.frame_count)
                lfc = int(getattr(metrics, "learner_frame_count", 0))
                mfc = int(getattr(metrics, "measurement_frame_count", 0))
                ts = int(metrics.total_training_steps)
                er = float(metrics.expert_ratio)
                ep = float(metrics.epsilon)
        except Exception:
            fc, lfc, mfc, ts, er, ep = 0, 0, 0, self.training_steps, RL_CONFIG.expert_ratio_start, RL_CONFIG.epsilon_start

        ckpt = {
            "online_state_dict": self.online_net.state_dict(),
            "target_state_dict": self.target_net.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "training_steps": self.training_steps,
            "optimized_samples": int(self.optimized_samples),
            "baseline_batch_size": int(self.baseline_batch_size),
            "last_target_update_samples": int(self.last_target_update_samples),
            "frame_count": fc,
            "learner_frame_count": lfc,
            "measurement_frame_count": mfc,
            "total_training_steps": ts,
            "expert_ratio": er,
            "epsilon": ep,
            "engine_version": ENGINE_VERSION,
            "lr_anchor_step": float(getattr(self, "lr_anchor_step", 0)),
            "lr_gear": str(getattr(self, "lr_gear", "climb")),
            "state_size": self.state_size,
            "single_frame_state_size": int(getattr(RL_CONFIG, "single_frame_state_size", self.state_size)),
            "frame_stack": int(getattr(RL_CONFIG, "frame_stack", 1)),
        }
        if self._priority_phase is not None:
            ckpt["priority_metric_phase"] = self._priority_phase.snapshot()
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

    @_with_training_paused
    def load(self, filepath, show_status=True) -> bool:
        priority_checkpoint_present = False
        graph_requested = bool(getattr(self, "_exact_graph_requested", False))
        if graph_requested:
            self._exact_graph_loaded = False
            required = getattr(self, "_exact_graph_checkpoint", None)
            if not required or os.path.realpath(filepath) != required or not os.path.isfile(filepath):
                raise ExactInferenceGraphError("Graph mode refuses a missing or unexpected checkpoint path")
        if not os.path.exists(filepath):
            return False
        try:
            if show_status:
                self._text_progress("  Model load", 0.0)
            ckpt = torch.load(filepath, map_location=self.device, weights_only=False)
            priority_checkpoint_present = ckpt.get("priority_metric_phase") is not None
            if self._priority_phase is not None or priority_checkpoint_present:
                try:
                    from .priority_phase import require_checkpoint_phase
                except ImportError:
                    from priority_phase import require_checkpoint_phase
                require_checkpoint_phase(ckpt, self._priority_metric, self._priority_phase)
                if self._priority_phase is not None:
                    self._priority_phase.before_load(filepath, ckpt)
            if show_status:
                self._text_progress("  Model load", 1.0)

            if graph_requested and int(ckpt.get("engine_version", 0)) != ENGINE_VERSION:
                raise ExactInferenceGraphError("Graph resume requires the exact checkpoint engine")
            if int(ckpt.get("engine_version", 0)) < ENGINE_VERSION:
                if graph_requested:
                    raise ExactInferenceGraphError("Graph resume refuses an incompatible checkpoint engine")
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

            if graph_requested and (arch_changed or (set(m1) - {"support"}) or u1
                                    or (set(m2) - {"support"}) or u2):
                raise ExactInferenceGraphError("Graph resume refuses a partial/changed checkpoint actor")
            opt_sd = ckpt.get("optimizer_state_dict")
            opt_loaded = False
            if opt_sd and not arch_changed:
                try:
                    self._load_optimizer_state_dict(opt_sd)
                    opt_loaded = True
                except Exception as e:
                    print(f"Optimizer state skipped: {e}")
            elif opt_sd:
                print("Optimizer state skipped: checkpoint state shape differs from current frame stack.")

            if graph_requested and not opt_loaded:
                raise ExactInferenceGraphError("Graph resume refuses absent/failed optimizer restoration")
            gs_sd = ckpt.get("grad_scaler_state_dict")
            if gs_sd and hasattr(self, "grad_scaler") and self.grad_scaler is not None:
                try:
                    self.grad_scaler.load_state_dict(gs_sd)
                except Exception as e:
                    if graph_requested:
                        raise ExactInferenceGraphError("Graph resume GradScaler restoration failed: " + str(e)) from e
                    print(f"GradScaler state skipped: {e}")

            self.training_steps = ckpt.get("training_steps", 0)
            self.loaded_training_steps = self.training_steps
            self.optimized_samples = int(ckpt.get("optimized_samples", self.training_steps * self.baseline_batch_size))
            self.loaded_optimized_samples = self.optimized_samples
            self.last_target_update_samples = int(ckpt.get("last_target_update_samples", self._legacy_target_update_samples()))
            self.lr_anchor_step = float(ckpt.get("lr_anchor_step", 0))
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
                self.ratchet_warmup_start_step = self.schedule_steps
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
                    metrics.total_optimized_samples = self.optimized_samples
                    metrics.loaded_optimized_samples = self.optimized_samples
                    # Discard an empty-buffer budget observed by the producer
                    # before this checkpoint's clocks/replay were installed.
                    self.__dict__.pop('_replay_pressure_anchor', None)
                    self.__dict__.pop('_replay_warmup_pending', None)
                    if not RESET_METRICS:
                        metrics.expert_ratio = ckpt.get("expert_ratio", RL_CONFIG.expert_ratio_start)
                        metrics.epsilon = ckpt.get("epsilon", RL_CONFIG.epsilon_start)
                        metrics.frame_count = int(ckpt.get("frame_count", 0))
                        metrics.learner_frame_count = int(ckpt.get("learner_frame_count", 0))
                        metrics.measurement_frame_count = int(ckpt.get("measurement_frame_count", 0))
                        metrics.loaded_measurement_frame_count = metrics.measurement_frame_count
                        metrics.loaded_frame_count = metrics.frame_count
                        metrics.total_training_steps = int(ckpt.get("total_training_steps", self.training_steps))
                    else:
                        metrics.expert_ratio = RL_CONFIG.expert_ratio_start
                        metrics.epsilon = RL_CONFIG.epsilon_start
                        metrics.frame_count = 0
                        metrics.learner_frame_count = 0
                        metrics.measurement_frame_count = 0
                        metrics.loaded_measurement_frame_count = 0
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

            if graph_requested:
                if arch_changed:
                    raise ExactInferenceGraphError("Graph resume refuses changed checkpoint geometry")
                self._validate_exact_inference_graphs()
            if self._priority_phase is not None:
                self._priority_phase.finish_load(filepath)
            return True
        except Exception as e:
            if self._priority_phase is not None or priority_checkpoint_present:
                if self._priority_phase is not None:
                    self._priority_phase.invalidate(e)
                raise
            if graph_requested:
                graphs = getattr(self, "_exact_inference_graphs", None)
                error = graphs.fail(e) if graphs is not None else ExactInferenceGraphError(str(e))
                raise error from e
            print(f"Error loading {filepath}: {e}")
            traceback.print_exc()
            return False

    @_with_training_paused
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
            st = torch.from_numpy(batch[0]).float()
            joint_q = self._infer_q_joint(st, return_cpu=True)
            return float(joint_q.min().item()), float(joint_q.max().item())
        except Exception:
            return float("nan"), float("nan")

    @_with_training_paused
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
        exposure = getattr(self, "_learning_optimizer_exposure", None)
        if exposure is not None:
            exposure.new_epoch("attention_reset_begin")
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
            self._train_thread.join(timeout=30.0)
        except Exception:
            pass
        if self._prefetcher is not None:
            self._prefetcher.close()


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
