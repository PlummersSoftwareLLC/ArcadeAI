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
except ImportError:
    from config import RL_CONFIG, metrics
    from model import device


def _beta_schedule(frame_count: int) -> float:
    """Anneal PER beta from start → 1.0."""
    progress = min(1.0, frame_count / max(1, RL_CONFIG.priority_beta_frames))
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


def _advisor_q_policy_weight_schedule(training_step: int) -> float:
    """Anneal DAgger-style advisor imitation on learner-visited states."""
    cfg = RL_CONFIG
    start = float(getattr(cfg, "advisor_q_policy_weight", 0.0))
    floor = float(getattr(cfg, "advisor_q_policy_min_weight", 0.0))
    start_step = int(getattr(cfg, "advisor_q_policy_decay_start_step", 0))
    decay_steps = int(getattr(cfg, "advisor_q_policy_decay_steps", 1))
    if training_step < start_step:
        return start
    progress = min(1.0, (training_step - start_step) / max(1, decay_steps))
    return start + progress * (floor - start)


def _advisor_margin_weight_schedule(training_step: int) -> float:
    """Anneal advisor Q-margin imitation on learner-visited states."""
    cfg = RL_CONFIG
    start = float(getattr(cfg, "advisor_q_margin_weight", 0.0))
    floor = float(getattr(cfg, "advisor_q_margin_min_weight", 0.0))
    start_step = int(getattr(cfg, "advisor_q_margin_decay_start_step", 0))
    decay_steps = int(getattr(cfg, "advisor_q_margin_decay_steps", 1))
    if training_step < start_step:
        return start
    progress = min(1.0, (training_step - start_step) / max(1, decay_steps))
    return start + progress * (floor - start)


def _state_array_to_device(arr: np.ndarray, use_amp: bool) -> torch.Tensor:
    """Move replay state to the learner device with minimal host-side expansion."""
    t = torch.from_numpy(arr)
    if device.type == "cuda":
        t = t.to(device)
        return t if use_amp else t.float()
    return t.float().to(device)



def train_step(agent, prefetched_batch=None) -> float | None:
    """Run one joint C51 distributional training step.

    Returns the scalar loss value, or None if training was skipped.
    """
    if not getattr(metrics, "training_enabled", True) or not agent.training_enabled:
        return None

    if len(agent.memory) < max(RL_CONFIG.min_replay_to_train, RL_CONFIG.batch_size):
        return None

    # Keep replay pressure bounded so optimization does not outrun data refresh.
    try:
        with metrics.lock:
            frame_count = int(metrics.frame_count)
            loaded_frame_count = int(getattr(metrics, "loaded_frame_count", 0))
        loaded_training_steps = int(getattr(agent, "loaded_training_steps", 0))
        max_spf = float(getattr(RL_CONFIG, "max_samples_per_frame", 0.0))
        if max_spf > 0.0 and frame_count > 0:
            recent_frames = max(1, frame_count - loaded_frame_count)
            recent_steps = max(0, int(agent.training_steps) - loaded_training_steps)
            sampled_per_frame = (float(recent_steps) * float(RL_CONFIG.batch_size)) / float(recent_frames)
            if sampled_per_frame >= max_spf:
                return None
    except Exception:
        pass

    step_t0 = time.perf_counter()

    # ── Sample ──────────────────────────────────────────────────────────
    beta = _beta_schedule(metrics.frame_count)
    sample_ms = 0.0
    sample_prefetched = prefetched_batch is not None
    if prefetched_batch is not None:
        batch = prefetched_batch
        sample_ms = float(getattr(agent, "_pending_batch_sample_ms", 0.0))
        agent._pending_batch_sample_ms = 0.0
    else:
        sample_t0 = time.perf_counter()
        batch = agent.memory.sample(RL_CONFIG.batch_size, beta=beta)
        sample_ms = (time.perf_counter() - sample_t0) * 1000.0
    if batch is None:
        return None

    if len(batch) >= 10:
        states, actions, rewards, next_states, dones, horizons, is_expert, indices, weights, advisor_actions = batch[:10]
    else:
        states, actions, rewards, next_states, dones, horizons, is_expert, indices, weights = batch
        advisor_actions = np.full_like(actions, -1)

    cfg = RL_CONFIG
    use_amp = agent.use_amp and device.type == "cuda"
    transfer_t0 = time.perf_counter()
    states_t      = _state_array_to_device(states, use_amp)
    actions_t     = torch.from_numpy(actions).to(device=device, dtype=torch.long)
    rewards_t     = torch.from_numpy(rewards).to(device=device, dtype=torch.float32)
    next_states_t = _state_array_to_device(next_states, use_amp)
    dones_t       = torch.from_numpy(dones).to(device=device, dtype=torch.float32)
    horizons_t    = torch.from_numpy(horizons.astype(np.float32, copy=False)).to(device=device, dtype=torch.float32)
    weights_t     = torch.from_numpy(weights).to(device=device, dtype=torch.float32)
    is_expert_t   = torch.from_numpy(is_expert).to(device=device, dtype=torch.bool)
    advisor_actions_t = torch.from_numpy(advisor_actions).to(device=device, dtype=torch.long)
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

    with amp_ctx:
        # Current joint action distribution (log-probabilities)
        joint_log_p = agent.online_net.joint_dist(states_t, log=True)    # (B, 81, N)
        joint_log_p_a = joint_log_p[arange, actions_t]                   # (B, N)

        # Target distribution (Double-DQN: online selects, target evaluates)
        with torch.no_grad():
            joint_q_next = agent.online_net.q_values_joint(next_states_t)
            joint_best = joint_q_next.argmax(dim=1)          # (B,)
            next_q_max = joint_q_next.max(dim=1).values

            joint_tp = agent.target_net.joint_dist(next_states_t, log=False)  # (B, 81, N)
            joint_tp_a = joint_tp[arange, joint_best]        # (B, N)
            target_next_q = (joint_tp_a * support.unsqueeze(0)).sum(dim=1)

            # Shared projected Bellman support (same reward/discount for both branches)
            gamma_n = cfg.gamma ** horizons_t              # (B,)
            bellman_mean = rewards_t + (1.0 - dones_t) * gamma_n * target_next_q
            Tz_unclamped = rewards_t.unsqueeze(1) + (1.0 - dones_t.unsqueeze(1)) * gamma_n.unsqueeze(1) * support.unsqueeze(0)
            target_clip_low_frac = (Tz_unclamped < v_min).float().mean()
            target_clip_high_frac = (Tz_unclamped > v_max).float().mean()
            Tz = Tz_unclamped.clamp(v_min, v_max)

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
            projected_target_q = (m_joint * support.unsqueeze(0)).sum(dim=1)
            projected_mass_sum = m_joint.sum(dim=1)
            target_mass_error = (projected_mass_sum - 1.0).abs()
            target_low_atom_mass = m_joint[:, 0]
            target_high_atom_mass = m_joint[:, -1]

        ce_loss = -(m_joint * joint_log_p_a).sum(dim=1)    # (B,)
        bellman_loss = (weights_t * ce_loss).mean()
        weighted_loss = bellman_loss

    # ── Optional BC loss on expert transitions (joint + auxiliary branches) ──
    bc_loss_val = 0.0
    bellman_loss_val = float(bellman_loss.detach().item())
    bc_loss_contrib_val = 0.0
    q_policy_loss_val = 0.0
    q_policy_loss_contrib_val = 0.0
    margin_loss_val = 0.0
    margin_loss_contrib_val = 0.0
    advisor_policy_loss_val = 0.0
    advisor_policy_loss_contrib_val = 0.0
    advisor_margin_loss_val = 0.0
    advisor_margin_loss_contrib_val = 0.0
    bc_w = _bc_weight_schedule(metrics.total_training_steps)
    sample_expert_frac = float(is_expert_t.float().mean().item()) if B > 0 else 0.0
    expert_idx = is_expert_t.nonzero(as_tuple=True)[0] if is_expert_t.any() else None
    if bc_w > 0.0 and expert_idx is not None and expert_idx.numel() > 0:
        with amp_ctx:
            joint_logits_e, move_logits_e, fire_logits_e = agent.online_net.bc_logits(states_t[expert_idx])
            joint_bc = F.cross_entropy(joint_logits_e, actions_t[expert_idx])
            branch_bc = 0.5 * (
                F.cross_entropy(move_logits_e, move_actions_t[expert_idx])
                + F.cross_entropy(fire_logits_e, fire_actions_t[expert_idx])
            )
            bc_loss = joint_bc + float(getattr(cfg, "branch_aux_bc_weight", 0.25)) * branch_bc
            # Scale BC by sampled expert fraction to avoid over-weighting when
            # expert transitions are sparse but present in most batches.
            bc_scale = float(expert_idx.numel()) / float(B)
            bc_contrib = (bc_w * bc_scale) * bc_loss
            weighted_loss = weighted_loss + bc_contrib
            bc_loss_val = float(bc_loss.detach().item())
            bc_loss_contrib_val = float(bc_contrib.detach().item())

    q_policy_w = _q_policy_weight_schedule(metrics.total_training_steps)
    margin_w = _margin_weight_schedule(metrics.total_training_steps)
    if (q_policy_w > 0.0 or margin_w > 0.0) and expert_idx is not None and expert_idx.numel() > 0:
        with amp_ctx:
            joint_q_e = (joint_log_p[expert_idx].exp() * support.view(1, 1, -1)).sum(dim=2)
            expert_actions = actions_t[expert_idx]
            bc_scale = float(expert_idx.numel()) / float(B)
            if q_policy_w > 0.0:
                temp = max(1e-3, float(getattr(cfg, "expert_q_policy_temperature", 10.0)))
                q_policy_loss = F.cross_entropy(joint_q_e / temp, expert_actions)
                q_policy_contrib = (q_policy_w * bc_scale) * q_policy_loss
                weighted_loss = weighted_loss + q_policy_contrib
                q_policy_loss_val = float(q_policy_loss.detach().item())
                q_policy_loss_contrib_val = float(q_policy_contrib.detach().item())
            if margin_w > 0.0:
                expert_q = joint_q_e.gather(1, expert_actions.unsqueeze(1)).squeeze(1)
                margin = torch.full_like(joint_q_e, float(getattr(cfg, "expert_q_margin", 0.5)))
                margin.scatter_(1, expert_actions.unsqueeze(1), 0.0)
                margin_loss = (joint_q_e + margin).max(dim=1).values - expert_q
                margin_loss_mean = margin_loss.mean()
                margin_contrib = (margin_w * bc_scale) * margin_loss_mean
                weighted_loss = weighted_loss + margin_contrib
                margin_loss_val = float(margin_loss_mean.detach().item())
                margin_loss_contrib_val = float(margin_contrib.detach().item())

    advisor_q_w = _advisor_q_policy_weight_schedule(metrics.total_training_steps)
    advisor_margin_w = _advisor_margin_weight_schedule(metrics.total_training_steps)
    advisor_mask = (
        (~is_expert_t)
        & (advisor_actions_t >= 0)
        & (advisor_actions_t < int(cfg.num_joint_actions))
    )
    advisor_idx = advisor_mask.nonzero(as_tuple=True)[0] if advisor_mask.any() else None
    if (advisor_q_w > 0.0 or advisor_margin_w > 0.0) and advisor_idx is not None and advisor_idx.numel() > 0:
        with amp_ctx:
            joint_q_a = (joint_log_p[advisor_idx].exp() * support.view(1, 1, -1)).sum(dim=2)
            advisor_targets = advisor_actions_t[advisor_idx]
            adv_scale = float(advisor_idx.numel()) / float(B)
            if advisor_q_w > 0.0:
                temp = max(1e-3, float(getattr(cfg, "advisor_q_policy_temperature", 10.0)))
                advisor_policy_loss = F.cross_entropy(joint_q_a / temp, advisor_targets)
                advisor_policy_contrib = (advisor_q_w * adv_scale) * advisor_policy_loss
                weighted_loss = weighted_loss + advisor_policy_contrib
                advisor_policy_loss_val = float(advisor_policy_loss.detach().item())
                advisor_policy_loss_contrib_val = float(advisor_policy_contrib.detach().item())
            if advisor_margin_w > 0.0:
                advisor_q = joint_q_a.gather(1, advisor_targets.unsqueeze(1)).squeeze(1)
                margin = torch.full_like(joint_q_a, float(getattr(cfg, "expert_q_margin", 0.5)))
                margin.scatter_(1, advisor_targets.unsqueeze(1), 0.0)
                advisor_margin_loss = (joint_q_a + margin).max(dim=1).values - advisor_q
                advisor_margin_loss_mean = advisor_margin_loss.mean()
                advisor_margin_contrib = (advisor_margin_w * adv_scale) * advisor_margin_loss_mean
                weighted_loss = weighted_loss + advisor_margin_contrib
                advisor_margin_loss_val = float(advisor_margin_loss_mean.detach().item())
                advisor_margin_loss_contrib_val = float(advisor_margin_contrib.detach().item())

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
        scaler.unscale_(agent.optimizer)
        grad_norm = torch.nn.utils.clip_grad_norm_(agent.online_net.parameters(), clip_norm)
        scaler.step(agent.optimizer)
        scaler.update()
    else:
        weighted_loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(agent.online_net.parameters(), clip_norm)
        agent.optimizer.step()

    compute_ms = (time.perf_counter() - compute_t0) * 1000.0

    # ── Update priorities (mean branch TD error) ────────────────────────
    priority_t0 = time.perf_counter()
    td_errors = ce_loss.detach().cpu().numpy()
    agent.memory.update_priorities(indices, td_errors)
    priority_ms = (time.perf_counter() - priority_t0) * 1000.0

    # ── Target network update ───────────────────────────────────────────
    agent.training_steps += 1
    if agent.training_steps % cfg.target_update_period == 0:
        agent.update_target()

    # ── Sync inference model ────────────────────────────────────────────
    agent._sync_inference(force=False)

    # ── Metrics ─────────────────────────────────────────────────────────
    try:
        loss_val = float(weighted_loss.detach().item())
        gn = float(grad_norm.item()) if isinstance(grad_norm, torch.Tensor) else float(grad_norm)

        metrics.total_training_steps += 1
        if hasattr(metrics, "training_steps_interval"):
            metrics.training_steps_interval += 1
        metrics.memory_buffer_size = len(agent.memory)
        metrics.losses.append(loss_val)
        metrics.last_loss = loss_val
        metrics.last_grad_norm = gn
        imitation_loss_val = (
            bc_loss_contrib_val
            + q_policy_loss_contrib_val
            + margin_loss_contrib_val
            + advisor_policy_loss_contrib_val
            + advisor_margin_loss_contrib_val
        )
        metrics.last_bellman_loss = float(bellman_loss_val)
        metrics.last_imitation_loss = float(imitation_loss_val)
        metrics.last_bc_loss = bc_loss_val
        metrics.last_bc_weight = float(bc_w)
        metrics.last_bc_loss_contrib = float(bc_loss_contrib_val)
        metrics.last_expert_q_policy_loss = float(q_policy_loss_val)
        metrics.last_expert_q_policy_weight = float(q_policy_w)
        metrics.last_expert_q_policy_loss_contrib = float(q_policy_loss_contrib_val)
        metrics.last_expert_q_margin_loss = float(margin_loss_val)
        metrics.last_expert_q_margin_weight = float(margin_w)
        metrics.last_expert_q_margin_loss_contrib = float(margin_loss_contrib_val)
        metrics.last_advisor_q_policy_loss = float(advisor_policy_loss_val)
        metrics.last_advisor_q_policy_weight = float(advisor_q_w)
        metrics.last_advisor_q_policy_loss_contrib = float(advisor_policy_loss_contrib_val)
        metrics.last_advisor_q_margin_loss = float(advisor_margin_loss_val)
        metrics.last_advisor_q_margin_weight = float(advisor_margin_w)
        metrics.last_advisor_q_margin_loss_contrib = float(advisor_margin_loss_contrib_val)
        metrics.last_sample_expert_frac = sample_expert_frac
        metrics.last_sample_advisor_frac = float(advisor_mask.float().mean().item()) if B > 0 else 0.0
        origin_counts = getattr(agent.memory, "last_sample_origin_counts", {}) or {}
        origin_total = max(1, int(sum(int(origin_counts.get(k, 0)) for k in ("per", "expert", "interesting", "recent"))))
        metrics.last_sample_per_frac = float(origin_counts.get("per", 0)) / float(origin_total)
        metrics.last_sample_expert_quota_frac = float(origin_counts.get("expert", 0)) / float(origin_total)
        metrics.last_sample_interesting_frac = float(origin_counts.get("interesting", 0)) / float(origin_total)
        metrics.last_sample_recent_frac = float(origin_counts.get("recent", 0)) / float(origin_total)
        metrics.last_sample_horizon_mean = float(np.mean(horizons)) if len(horizons) else 0.0
        metrics.last_sample_terminal_frac = float(np.mean(dones > 0.5)) if len(dones) else 0.0
        metrics.last_sample_reward_mean = float(np.mean(rewards)) if len(rewards) else 0.0
        metrics.last_sample_reward_abs_mean = float(np.mean(np.abs(rewards))) if len(rewards) else 0.0
        metrics.last_sample_reward_min = float(np.min(rewards)) if len(rewards) else 0.0
        metrics.last_sample_reward_max = float(np.max(rewards)) if len(rewards) else 0.0
        metrics.last_inference_sync_age = int(max(0, int(agent.training_steps) - int(getattr(agent, "last_inference_sync", 0))))
        metrics.last_priority_mean = float(np.mean(td_errors))
        metrics.last_train_sample_ms = float(sample_ms)
        metrics.last_train_transfer_ms = float(transfer_ms)
        metrics.last_train_compute_ms = float(compute_ms)
        metrics.last_train_priority_ms = float(priority_ms)

        # Directional agreement: argmax move/fire matches the stored action
        agree = 0.0
        with torch.no_grad():
            joint_q_all = (joint_log_p.detach().exp() * support.view(1, 1, -1)).sum(dim=2)
            metrics.last_q_mean = float(joint_q_all.mean().item())
            q_action = joint_q_all[arange, actions_t]
            target_q = projected_target_q.detach()
            unclamped_target_q = bellman_mean.detach()
            next_q = next_q_max.detach()
            target_next = target_next_q.detach()
            td_q = target_q - q_action
            top2 = joint_q_all.topk(k=2, dim=1).values if joint_q_all.shape[1] >= 2 else joint_q_all
            if top2.shape[1] >= 2:
                q_gap = top2[:, 0] - top2[:, 1]
            else:
                q_gap = torch.zeros_like(q_action)
            action_rank = 1 + (joint_q_all > q_action.unsqueeze(1)).sum(dim=1)

            metrics.last_current_q_action_mean = float(q_action.mean().item())
            metrics.last_target_q_mean = float(target_q.mean().item())
            metrics.last_unclamped_target_q_mean = float(unclamped_target_q.mean().item())
            metrics.last_next_q_max_mean = float(next_q.mean().item())
            metrics.last_target_next_q_mean = float(target_next.mean().item())
            metrics.last_double_q_gap_mean = float((next_q - target_next).mean().item())
            metrics.last_td_q_mean = float(td_q.mean().item())
            metrics.last_td_q_abs_mean = float(td_q.abs().mean().item())
            metrics.last_q_gap_mean = float(q_gap.mean().item())
            metrics.last_target_clip_low_frac = float(target_clip_low_frac.item())
            metrics.last_target_clip_high_frac = float(target_clip_high_frac.item())
            metrics.last_target_low_atom_mass = float(target_low_atom_mass.mean().item())
            metrics.last_target_high_atom_mass = float(target_high_atom_mass.mean().item())
            metrics.last_target_mass_error_mean = float(target_mass_error.mean().item())

            pred_joint = joint_q_all.argmax(dim=1)
            pred_move = pred_joint // num_fire
            pred_fire = pred_joint % num_fire
            idle_move_idx = int(cfg.num_move_actions - 1)
            idle_fire_idx = int(cfg.num_fire_actions - 1)
            sample_idle_move = move_actions_t == idle_move_idx
            sample_idle_fire = fire_actions_t == idle_fire_idx
            policy_idle_move = pred_move == idle_move_idx
            policy_idle_fire = pred_fire == idle_fire_idx
            sample_counts = torch.bincount(actions_t, minlength=int(cfg.num_joint_actions)).float()
            policy_counts = torch.bincount(pred_joint, minlength=int(cfg.num_joint_actions)).float()

            def _norm_entropy(counts: torch.Tensor) -> float:
                total = counts.sum()
                if total <= 0:
                    return 0.0
                p = counts / total
                p = p[p > 0]
                denom = math.log(max(2, int(counts.numel())))
                return float((-(p * p.log()).sum() / denom).item())

            metrics.last_sample_idle_move_frac = float(sample_idle_move.float().mean().item())
            metrics.last_sample_idle_fire_frac = float(sample_idle_fire.float().mean().item())
            metrics.last_sample_noop_frac = float((sample_idle_move & sample_idle_fire).float().mean().item())
            metrics.last_sample_top_action_frac = float((sample_counts.max() / sample_counts.sum().clamp_min(1.0)).item())
            metrics.last_sample_action_entropy = _norm_entropy(sample_counts)
            metrics.last_policy_idle_move_frac = float(policy_idle_move.float().mean().item())
            metrics.last_policy_idle_fire_frac = float(policy_idle_fire.float().mean().item())
            metrics.last_policy_noop_frac = float((policy_idle_move & policy_idle_fire).float().mean().item())
            metrics.last_policy_top_action_frac = float((policy_counts.max() / policy_counts.sum().clamp_min(1.0)).item())
            metrics.last_policy_action_entropy = _norm_entropy(policy_counts)
            agree_move = (pred_move == move_actions_t).float().mean().item()
            agree_fire = (pred_fire == fire_actions_t).float().mean().item()
            agree = 0.5 * (agree_move + agree_fire)
            metrics.last_agreement = agree

            expert_mask = is_expert_t
            learner_mask = ~is_expert_t
            if expert_mask.any():
                exp_pred_joint = pred_joint[expert_mask]
                exp_actions = actions_t[expert_mask]
                metrics.last_expert_joint_agreement = float((exp_pred_joint == exp_actions).float().mean().item())
                exp_rank = action_rank[expert_mask].float()
                metrics.last_expert_q_rank_mean = float(exp_rank.mean().item())
                exp_q_all = joint_q_all[expert_mask]
                exp_q_action = q_action[expert_mask]
                exp_other = exp_q_all.clone()
                exp_other.scatter_(1, exp_actions.unsqueeze(1), float("-inf"))
                exp_margin = exp_q_action - exp_other.max(dim=1).values
                metrics.last_expert_q_margin_mean = float(exp_margin.mean().item())
            else:
                metrics.last_expert_joint_agreement = 0.0
                metrics.last_expert_q_rank_mean = 0.0
                metrics.last_expert_q_margin_mean = 0.0

            if learner_mask.any():
                metrics.last_learner_joint_agreement = float(
                    (pred_joint[learner_mask] == actions_t[learner_mask]).float().mean().item()
                )
            else:
                metrics.last_learner_joint_agreement = 0.0

            if advisor_mask.any():
                advisor_targets = advisor_actions_t[advisor_mask]
                advisor_pred = pred_joint[advisor_mask]
                advisor_q_all = joint_q_all[advisor_mask]
                advisor_q_action = advisor_q_all.gather(1, advisor_targets.unsqueeze(1)).squeeze(1)
                advisor_rank = 1 + (advisor_q_all > advisor_q_action.unsqueeze(1)).sum(dim=1)
                advisor_other = advisor_q_all.clone()
                advisor_other.scatter_(1, advisor_targets.unsqueeze(1), float("-inf"))
                advisor_margin = advisor_q_action - advisor_other.max(dim=1).values
                metrics.last_advisor_joint_agreement = float((advisor_pred == advisor_targets).float().mean().item())
                metrics.last_advisor_q_rank_mean = float(advisor_rank.float().mean().item())
                metrics.last_advisor_q_margin_mean = float(advisor_margin.mean().item())
            else:
                metrics.last_advisor_joint_agreement = 0.0
                metrics.last_advisor_q_rank_mean = 0.0
                metrics.last_advisor_q_margin_mean = 0.0

        if hasattr(metrics, "agree_sum_interval"):
            metrics.agree_sum_interval += agree
            metrics.agree_move_sum_interval += agree_move
            metrics.agree_fire_sum_interval += agree_fire
            metrics.agree_count_interval += 1
        if hasattr(metrics, "loss_sum_interval"):
            metrics.loss_sum_interval += loss_val
            metrics.loss_count_interval += 1
        total_ms = (time.perf_counter() - step_t0) * 1000.0
        if sample_prefetched:
            total_ms += sample_ms
        metrics.last_train_step_ms = float(total_ms)
    except Exception:
        pass

    return loss_val
