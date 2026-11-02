#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN TRAINING STEP                                                                            ||
# ||  Joint C51 distributional Bellman update with PER and optional branch/joint BC loss.                         ||
# ==================================================================================================================
"""Single training step for the Robotron Rainbow-lite agent.

The replay buffer stores a joint action index ``move * num_fire + fire`` (0..80).
The Bellman update trains the joint 81-action C51 head.  Auxiliary move/fire
branch heads are kept for expert imitation and diagnostics.
"""

import time, math
from contextlib import nullcontext
import numpy as np
import torch
import torch.nn.functional as F

try:
    from .config import RL_CONFIG, metrics
    from .model import device
    from .replay_buffer import ACTOR_DQN, ACTOR_EPSILON, ACTOR_EXPERT
except ImportError:
    from config import RL_CONFIG, metrics
    from model import device
    from replay_buffer import ACTOR_DQN, ACTOR_EPSILON, ACTOR_EXPERT


def _beta_schedule(frame_count: int) -> float:
    """Anneal PER beta from start → 1.0."""
    learning_frame_count = max(0, frame_count - int(getattr(metrics, 'measurement_frame_count', 0)))
    progress = min(1.0, learning_frame_count / max(1, RL_CONFIG.priority_beta_frames))
    return RL_CONFIG.priority_beta_start + progress * (1.0 - RL_CONFIG.priority_beta_start)


def _bc_weight_schedule(training_step: int) -> float:
    """Anneal behavioural-cloning weight (keyed to training steps, not frames)."""
    cfg = RL_CONFIG
    if training_step < cfg.expert_bc_decay_start_step:
        return cfg.expert_bc_weight
    progress = min(1.0, (training_step - cfg.expert_bc_decay_start_step) / max(1, cfg.expert_bc_decay_steps))
    return cfg.expert_bc_weight + progress * (cfg.expert_bc_min_weight - cfg.expert_bc_weight)


def _margin_weight_schedule(training_step: int) -> float:
    """Anneal the expert Q-margin weight to its floor (keyed to training steps).

    The margin term imitates directly into the acting joint head alongside the
    Q-policy distillation loss; decaying it removes the demonstrator ceiling.
    """
    cfg = RL_CONFIG
    start = float(getattr(cfg, "expert_q_margin_weight", 0.0))
    floor = float(getattr(cfg, "expert_q_margin_min_weight", 0.0))
    start_step = int(getattr(cfg, "expert_q_margin_decay_start_step", 0))
    decay_steps = int(getattr(cfg, "expert_q_margin_decay_steps", 1))
    if training_step < start_step:
        return start
    progress = min(1.0, (training_step - start_step) / max(1, decay_steps))
    return start + progress * (floor - start)


def _q_policy_weight_schedule(training_step: int) -> float:
    """Anneal direct expert imitation on the deployed joint Q policy."""
    cfg = RL_CONFIG
    start = float(getattr(cfg, "expert_q_policy_weight", 0.0))
    floor = float(getattr(cfg, "expert_q_policy_min_weight", 0.0))
    start_step = int(getattr(cfg, "expert_q_policy_decay_start_step", 0))
    decay_steps = int(getattr(cfg, "expert_q_policy_decay_steps", 1))
    if training_step < start_step:
        return start
    progress = min(1.0, (training_step - start_step) / max(1, decay_steps))
    return start + progress * (floor - start)


def _expert_batch_scale(expert_count: int, batch_size: int) -> float:
    return float(max(0, int(expert_count))) / float(max(1, int(batch_size)))


def _state_array_to_device(arr: np.ndarray, use_amp: bool) -> torch.Tensor:
    """Move replay state to the learner device with minimal host-side expansion."""
    t = torch.from_numpy(arr)
    if device.type == "cuda":
        t = t.to(device)
        return t if use_amp else t.float()
    return t.float().to(device)



def train_step(agent, prefetched_batch=None) -> float | None:
    # Checkpoint/restore and source-weight copies must not race an optimizer update.
    lock = getattr(agent, "_training_lock", None)
    context = lock if lock is not None else nullcontext()
    with context:
        try:
            return _train_step_impl(agent, prefetched_batch)
        finally:
            if hasattr(prefetched_batch, "release"):
                prefetched_batch.release()


def replay_pressure_reached(agent) -> bool:
    """Check the sample clock before doing replay or transfer work.

    Shared by the producer, consumer and final training guard. A bounded
    prefetch may finish in-flight work at the boundary, but must not keep
    sampling batches that the learner will throw away.
    """
    with metrics.lock:
        frames = int(metrics.frame_count)
        loaded_frames = int(getattr(metrics, "loaded_frame_count", 0))
        measured_frames = int(getattr(metrics, 'measurement_frame_count', 0))
        loaded_measured_frames = int(getattr(metrics, 'loaded_measurement_frame_count', 0))
        loaded_steps = int(getattr(agent, "loaded_training_steps", 0))
        loaded_samples = int(getattr(metrics, "loaded_optimized_samples",
                                     loaded_steps * RL_CONFIG.baseline_batch_size))
        steps = int(agent.training_steps)
        optimized_samples = int(getattr(agent, "optimized_samples",
                                        steps * RL_CONFIG.baseline_batch_size))
        memory = getattr(agent, 'memory', None)
        minimum = max(int(getattr(RL_CONFIG, 'min_replay_to_train', 0)),
                      int(getattr(RL_CONFIG, 'batch_size', 0)))
        if memory is not None and len(memory) < minimum:
            # Fresh-data warmup earns no future burst of replay updates. This
            # per-run budget anchor changes no persisted model/schedule clock.
            agent._replay_pressure_anchor = (frames, measured_frames, optimized_samples)
            agent._replay_warmup_pending = True
            return True
        if getattr(agent, '_replay_warmup_pending', False):
            # Seal at the first ready observation, even if collection passed
            # the threshold while a manual training pause suppressed polling.
            agent._replay_pressure_anchor = (frames, measured_frames, optimized_samples)
            agent._replay_warmup_pending = False
        anchor = getattr(agent, '_replay_pressure_anchor', None)
        if anchor is not None:
            loaded_frames, loaded_measured_frames, loaded_samples = anchor
    limit = float(getattr(RL_CONFIG, "max_samples_per_frame", 0.0))
    if limit <= 0.0 or frames <= 0:
        return False
    samples = max(0, optimized_samples - loaded_samples)
    learning_frames = frames - loaded_frames - max(0, measured_frames - loaded_measured_frames)
    return samples / max(1, learning_frames) >= limit


def _train_step_impl(agent, prefetched_batch=None) -> float | None:
    """Run one joint C51 distributional training step.

    Returns the scalar loss value, or None if training was skipped.
    """
    if not getattr(metrics, "training_enabled", True) or not agent.training_enabled:
        return None

    if len(agent.memory) < max(RL_CONFIG.min_replay_to_train, RL_CONFIG.batch_size):
        return None

    if replay_pressure_reached(agent):
        return None

    step_t0 = time.perf_counter()

    # ── Sample ──────────────────────────────────────────────────────────
    beta = _beta_schedule(metrics.frame_count)
    sample_ms = 0.0
    sample_prefetched = prefetched_batch is not None
    staged = None
    if prefetched_batch is not None:
        staged = prefetched_batch if hasattr(prefetched_batch, "batch") else None
        batch = staged.batch if staged is not None else prefetched_batch
        sample_ms = float(staged.sample_ms if staged is not None else getattr(agent, "_pending_batch_sample_ms", 0.0))
        agent._pending_batch_sample_ms = 0.0
    else:
        sample_t0 = time.perf_counter()
        batch = agent.memory.sample(RL_CONFIG.batch_size, beta=beta)
        sample_ms = (time.perf_counter() - sample_t0) * 1000.0
    if batch is None:
        return None

    if len(batch) >= 10:
        states, actions, rewards, next_states, dones, horizons, is_expert, actor_kind, indices, weights = batch
    else:
        states, actions, rewards, next_states, dones, horizons, is_expert, indices, weights = batch
        actor_kind = np.where(is_expert > 0, ACTOR_EXPERT, ACTOR_DQN).astype(np.uint8)

    cfg = RL_CONFIG
    use_amp = agent.use_amp and device.type == "cuda"
    transfer_t0 = time.perf_counter()
    if staged is not None and staged.tensors is not None:
        staged.wait_on_current_stream()
        (states_t, actions_t, rewards_t, next_states_t, dones_t,
         horizons_t, is_expert_t, weights_t) = staged.tensors
        transfer_ms = float(staged.transfer_ms)
    else:
        states_t = _state_array_to_device(states, use_amp)
        actions_t = torch.from_numpy(actions).to(device=device, dtype=torch.long)
        rewards_t = torch.from_numpy(rewards).to(device=device, dtype=torch.float32)
        next_states_t = _state_array_to_device(next_states, use_amp)
        dones_t = torch.from_numpy(dones).to(device=device, dtype=torch.float32)
        horizons_t = torch.from_numpy(horizons.astype(np.float32, copy=False)).to(device=device)
        weights_t = torch.from_numpy(weights).to(device=device, dtype=torch.float32)
        is_expert_t = torch.from_numpy(is_expert).to(device=device, dtype=torch.bool)
        transfer_ms = (time.perf_counter() - transfer_t0) * 1000.0

    B = states_t.shape[0]

    # Split joint action → (move, fire) branch indices
    num_fire = cfg.num_fire_actions
    move_actions_t = actions_t // num_fire
    fire_actions_t = actions_t % num_fire

    agent.online_net.train()
    agent._update_lr()

    scaler = agent.grad_scaler
    amp_ctx = torch.autocast(device_type="cuda", dtype=torch.float16) if use_amp else nullcontext()
    compute_t0 = time.perf_counter()

    # ── Joint C51 distributional update ─────────────────────────────────
    num_atoms = cfg.num_atoms
    v_min, v_max = cfg.v_min, cfg.v_max
    delta_z = (v_max - v_min) / (num_atoms - 1)
    support = agent.online_net.support  # (num_atoms,)
    arange = torch.arange(B, device=device)

    diagnostic_due = agent.training_steps % int(getattr(cfg, "diagnostic_interval", 20)) == 0
    schedule_steps = float(getattr(agent, "schedule_steps", agent.training_steps))
    bc_w = _bc_weight_schedule(schedule_steps)
    q_policy_w = _q_policy_weight_schedule(schedule_steps)
    margin_w = _margin_weight_schedule(schedule_steps)
    expert_count = int(np.count_nonzero(is_expert))
    sample_expert_frac = expert_count / max(1, B)
    actor_kind_np = np.asarray(actor_kind, dtype=np.uint8)
    sample_dqn_frac = float(np.mean(actor_kind_np == ACTOR_DQN))
    sample_epsilon_frac = float(np.mean(actor_kind_np == ACTOR_EPSILON))
    gpu_timing = None
    if diagnostic_due and device.type == "cuda":
        gpu_timing = (torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True))
        gpu_timing[0].record()
    kernel = getattr(agent, "compiled_training_loss_diagnostics" if diagnostic_due else "compiled_training_loss", None)
    kernel_active = kernel is not None
    if kernel_active:
        schedule_t = torch.tensor([bc_w, q_policy_w, margin_w], device=device, dtype=torch.float32)
        with amp_ctx:
            weighted_loss, ce_loss, bc_loss, kernel_diag = kernel(
                states_t, actions_t, rewards_t, next_states_t, dones_t,
                horizons_t, is_expert_t, weights_t, schedule_t)
    else:
        with amp_ctx:
            # Current joint action distribution (log-probabilities)
            _joint_dist_online = agent.compiled_online_joint_dist or agent.online_net.joint_dist
            _q_joint_online = agent.compiled_online_q_joint or agent.online_net.q_values_joint
            _joint_dist_target = agent.compiled_target_joint_dist or agent.target_net.joint_dist
            training_fn = getattr(agent, "compiled_training_outputs", None) or agent.online_net.training_outputs
            joint_log_p, joint_logits, move_logits, fire_logits = training_fn(states_t)            # (B, 81, N)
            joint_log_p_a = joint_log_p[arange, actions_t]                   # (B, N)

            # Target distribution (Double-DQN: online selects, target evaluates)
            with torch.no_grad():
                joint_q_next = _q_joint_online(next_states_t)
                joint_best = joint_q_next.argmax(dim=1)          # (B,)

                joint_tp = _joint_dist_target(next_states_t, log=False)  # (B, 81, N)
                joint_tp_a = joint_tp[arange, joint_best]        # (B, N)

                # Shared projected Bellman support (same reward/discount for both branches)
                gamma_n = cfg.gamma ** horizons_t              # (B,)
                Tz = rewards_t.unsqueeze(1) + (1.0 - dones_t.unsqueeze(1)) * gamma_n.unsqueeze(1) * support.unsqueeze(0)
                Tz_raw = Tz
                Tz = Tz.clamp(v_min, v_max)

                b = (Tz - v_min) / delta_z                     # (B, N)
                l = b.floor().long().clamp(0, num_atoms - 1)
                u = b.ceil().long().clamp(0, num_atoms - 1)
                offset = torch.linspace(0, (B - 1) * num_atoms, B, device=device, dtype=torch.long).unsqueeze(1).expand_as(l)
                eq_mask = (l == u)
                neq_mask = ~eq_mask

                m_joint = torch.zeros(B, num_atoms, device=device, dtype=torch.float32)
                m_joint.view(-1).index_add_(0, (l + offset).view(-1), (joint_tp_a * (u.float() - b) * neq_mask.float()).view(-1))
                m_joint.view(-1).index_add_(0, (u + offset).view(-1), (joint_tp_a * (b - l.float()) * neq_mask.float()).view(-1))
                # When l == u the two weights above are both 0 → assign full mass directly.
                m_joint.view(-1).index_add_(0, (l + offset).view(-1), (joint_tp_a * eq_mask.float()).view(-1))

                # Target smoothing: mix a sliver of uniform-over-atoms mass into
                # the projected target so the minimum achievable cross-entropy is
                # bounded away from zero (~0.095 at eps=0.01).  Without it the
                # C51 head sharpens to near-delta distributions, TD loss grinds
                # to ~0.004, gradients vanish, and the policy drifts uncorrected
                # — the gradient-starvation sag that rolled EScr1M 415K→210K on
                # 2026-07-19.  A critic that can never be exactly right can
                # never fully fall asleep.
                smooth_eps = float(getattr(cfg, "c51_target_smoothing", 0.0))
                if smooth_eps > 0.0:
                    m_joint = m_joint * (1.0 - smooth_eps) + smooth_eps / num_atoms

            ce_loss = -(m_joint * joint_log_p_a).sum(dim=1)    # (B,)
            weighted_loss = (weights_t * ce_loss).mean()

        # Fixed-shape masked expert losses preserve subset means without GPU
        # nonzero()/any() synchronization or changing compiler graph shapes.
        schedule_steps = float(getattr(agent, "schedule_steps", agent.training_steps))
        bc_w = _bc_weight_schedule(schedule_steps)
        q_policy_w = _q_policy_weight_schedule(schedule_steps)
        margin_w = _margin_weight_schedule(schedule_steps)
        expert_count = int(np.count_nonzero(is_expert))
        sample_expert_frac = expert_count / max(1, B)
        actor_kind_np = np.asarray(actor_kind, dtype=np.uint8)
        sample_dqn_frac = float(np.mean(actor_kind_np == ACTOR_DQN))
        sample_epsilon_frac = float(np.mean(actor_kind_np == ACTOR_EPSILON))
        bc_loss = weighted_loss.new_zeros(())
        expert_mask = is_expert_t.to(dtype=torch.float32)
        if expert_count:
            with amp_ctx:
                if bc_w > 0:
                    per_row = F.cross_entropy(joint_logits, actions_t, reduction="none")
                    per_row = per_row + float(getattr(cfg, "branch_aux_bc_weight", 0.25)) * 0.5 * (
                        F.cross_entropy(move_logits, move_actions_t, reduction="none")
                        + F.cross_entropy(fire_logits, fire_actions_t, reduction="none"))
                    bc_loss = (per_row * expert_mask).sum() / expert_count
                    effective_bc = max(float(getattr(cfg, "expert_bc_effective_floor", 0.01)), bc_w * sample_expert_frac)
                    weighted_loss = weighted_loss + effective_bc * bc_loss
                if q_policy_w > 0 or margin_w > 0:
                    joint_q = (joint_log_p.exp() * support.view(1, 1, -1)).sum(dim=2)
                    if q_policy_w > 0:
                        temp = max(1e-3, float(getattr(cfg, "expert_q_policy_temperature", 10.0)))
                        per_row = F.cross_entropy(joint_q / temp, actions_t, reduction="none")
                        weighted_loss = weighted_loss + q_policy_w * (per_row * expert_mask).sum() / B
                    if margin_w > 0:
                        expert_q = joint_q.gather(1, actions_t.unsqueeze(1)).squeeze(1)
                        margin = torch.full_like(joint_q, float(getattr(cfg, "expert_q_margin", 0.5)))
                        margin.scatter_(1, actions_t.unsqueeze(1), 0.0)
                        per_row = (joint_q + margin).max(dim=1).values - expert_q
                        weighted_loss = weighted_loss + margin_w * (per_row * expert_mask).sum() / B

    # ── NaN / Inf guard ───────────────────────────────────────────────────
    if not torch.isfinite(weighted_loss):
        print(f"[WARN] Non-finite loss detected ({weighted_loss.item():.4g}), skipping step")
        return None

    # ── Optimise ────────────────────────────────────────────────────────
    try:
        agent.optimizer.zero_grad(set_to_none=True)
    except TypeError:
        agent.optimizer.zero_grad()

    clip_norm = cfg.grad_clip_norm
    if use_amp and scaler is not None:
        scaler.scale(weighted_loss).backward()
        if kernel_active and (not expert_count or bc_w <= 0):
            for head in (agent.online_net.bc_joint_head, agent.online_net.bc_move_head, agent.online_net.bc_fire_head):
                for parameter in head.parameters(): parameter.grad = None
        scaler.unscale_(agent.optimizer)
        grad_norm = torch.nn.utils.clip_grad_norm_(agent.online_net.parameters(), clip_norm)
        scaler.step(agent.optimizer)
        scaler.update()
    else:
        weighted_loss.backward()
        if kernel_active and (not expert_count or bc_w <= 0):
            for head in (agent.online_net.bc_joint_head, agent.online_net.bc_move_head, agent.online_net.bc_fire_head):
                for parameter in head.parameters(): parameter.grad = None
        grad_norm = torch.nn.utils.clip_grad_norm_(agent.online_net.parameters(), clip_norm)
        agent.optimizer.step()

    if gpu_timing is not None:
        gpu_timing[1].record()
    compute_ms = (time.perf_counter() - compute_t0) * 1000.0

    # One CPU readback for priorities + loss/gradient metrics. Diagnostics are
    # decimated and packed into the same readback, avoiding repeated barriers.
    diagnostic_due = agent.training_steps % int(getattr(cfg, "diagnostic_interval", 20)) == 0
    with torch.no_grad():
        scalars = [weighted_loss.detach().float(), grad_norm.detach().float(), bc_loss.detach().float()]
        if diagnostic_due and kernel_active:
            scalars.extend(kernel_diag.detach().float().unbind())
        elif diagnostic_due:
            q = (joint_log_p.detach().float().exp() * support.view(1, 1, -1)).sum(dim=2)
            gap = (joint_q_next.float().max(dim=1).values - (joint_tp_a.float() * support.view(1, -1)).sum(dim=1)).mean()
            pred = q.argmax(dim=1)
            scalars.extend([q.min(), q.max(), gap, q.mean(),
                ((pred // num_fire) == move_actions_t).float().mean(),
                ((pred % num_fire) == fire_actions_t).float().mean()])
            entropy_rows = -(m_joint * m_joint.clamp_min(1e-8).log()).sum(dim=1)
            top_q = q.topk(2, dim=1).values
            action_p = joint_log_p_a.detach().float().exp()
            scalars.extend([
                (joint_tp_a.float() * (Tz_raw < v_min).float()).sum(dim=1).mean(),
                (joint_tp_a.float() * (Tz_raw > v_max).float()).sum(dim=1).mean(),
                (action_p[:, 0] + action_p[:, -1]).mean(),
                entropy_rows.mean(), (top_q[:, 0] - top_q[:, 1]).mean(),
                (ce_loss.detach().float() - entropy_rows).mean()])
        packed = torch.cat((ce_loss.detach().float(), torch.stack(scalars)))
    priority_t0 = time.perf_counter()
    host = packed.cpu().numpy()
    if gpu_timing is not None:
        # The packed CPU readback above already waits for these events.
        metrics.last_train_gpu_compute_ms = gpu_timing[0].elapsed_time(gpu_timing[1])
    td_errors = host[:B]
    loss_val, gn, bc_loss_val = map(float, host[B:B+3])
    if diagnostic_due:
        _q_pred_min, _q_pred_max, _q_overest, q_mean, agree_move, agree_fire = map(float, host[B+3:B+9])
        for name, value in zip(('below_support_mass', 'above_support_mass', 'edge_atom_mass',
                                'target_entropy', 'action_q_gap', 'categorical_kl'), host[B+9:B+15]):
            setattr(metrics, 'c51_' + name, float(value))
    agent.memory.update_priorities(indices, td_errors)
    priority_ms = (time.perf_counter() - priority_t0) * 1000.0

    # Per-slice TD diagnostics (2026-07-22 bank-poisoning tripwire): bank
    # rows ride sentinel indices >= capacity (game HOF first, EpHOF from
    # _ephof_base).  A bank slice whose TD falls while the ring slice's
    # rises means the net is memorizing frozen demonstrations while live
    # play diverges — the exact signature aggregate loss concealed.
    try:
        _cap = int(agent.memory.capacity)
        _eb = int(getattr(agent.memory, "_ephof_base", _cap))
        _idx = np.asarray(indices)
        _a = 0.01
        for _name, _mask in (("ring", _idx < _cap),
                             ("hof", (_idx >= _cap) & (_idx < _eb)),
                             ("ephof", _idx >= _eb)):
            if _mask.any():
                _v = float(td_errors[_mask].mean())
                _prev = getattr(metrics, f"slice_td_{_name}", None)
                setattr(metrics, f"slice_td_{_name}",
                        _v if _prev is None else _prev + _a * (_v - _prev))
    except Exception:
        pass

    # ── Target network update ───────────────────────────────────────────
    agent.training_steps += 1
    agent.optimized_samples = int(getattr(agent, "optimized_samples", (agent.training_steps - 1) * cfg.baseline_batch_size)) + B
    if agent.optimized_samples - int(getattr(agent, "last_target_update_samples", 0)) >= cfg.target_update_period * cfg.baseline_batch_size:
        agent.update_target()

    # ── Sync inference model ────────────────────────────────────────────
    agent._sync_inference(force=False)

    # ── Metrics ─────────────────────────────────────────────────────────
    try:

        metrics.total_training_steps += 1
        metrics.total_optimized_samples = agent.optimized_samples
        if hasattr(metrics, "training_steps_interval"):
            metrics.training_steps_interval += 1
        metrics.memory_buffer_size = len(agent.memory)
        metrics.losses.append(loss_val)
        metrics.last_loss = loss_val
        metrics.last_grad_norm = gn
        metrics.last_bc_loss = bc_loss_val
        metrics.last_bc_weight = float(bc_w)
        metrics.last_sample_dqn_frac = sample_dqn_frac
        metrics.last_sample_epsilon_frac = sample_epsilon_frac
        metrics.last_sample_expert_frac = sample_expert_frac
        metrics.last_inference_sync_age = int(max(0, int(agent.training_steps) - int(getattr(agent, "last_inference_sync", 0))))
        metrics.last_priority_mean = float(np.mean(td_errors))

        if diagnostic_due:
            # Smoothed Q diagnostics: seed on first sample, then EMA.
            _qa = float(getattr(cfg, "q_stat_ema_alpha", 0.002))
            if not metrics.q_ema_init:
                metrics.q_pred_min_ema = _q_pred_min
                metrics.q_pred_max_ema = _q_pred_max
                metrics.q_overest_ema = _q_overest
                metrics.q_ema_init = True
            else:
                metrics.q_pred_min_ema += _qa * (_q_pred_min - metrics.q_pred_min_ema)
                metrics.q_pred_max_ema += _qa * (_q_pred_max - metrics.q_pred_max_ema)
                metrics.q_overest_ema += _qa * (_q_overest - metrics.q_overest_ema)
        metrics.last_train_sample_ms = float(sample_ms)
        metrics.last_train_stage_host_ms = float(getattr(staged, 'stage_host_ms', 0.0))
        metrics.last_train_transfer_ms = float(transfer_ms)
        metrics.last_train_compute_ms = float(compute_ms)
        metrics.last_train_priority_ms = float(priority_ms)

        if diagnostic_due:
            agree = 0.5 * (agree_move + agree_fire)
            metrics.last_q_mean = q_mean
            metrics.last_agreement = agree
            if hasattr(metrics, "agree_sum_interval"):
                metrics.agree_sum_interval += agree
                metrics.agree_move_sum_interval += agree_move
                metrics.agree_fire_sum_interval += agree_fire
                metrics.agree_count_interval += 1
        if hasattr(metrics, "loss_sum_interval"):
            metrics.loss_sum_interval += loss_val
            metrics.loss_count_interval += 1
        total_ms = (time.perf_counter() - step_t0) * 1000.0
        metrics.last_train_step_ms = float(total_ms)
    except Exception:
        pass

    return loss_val
