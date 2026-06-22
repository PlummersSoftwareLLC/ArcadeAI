#!/usr/bin/env python3
# ==================================================================================================================
# ||  ROBOTRON AI • DQN TRAINING STEP                                                                            ||
# ||  Branching C51 distributional Bellman update with PER and optional BC loss.                                  ||
# ==================================================================================================================
"""Single training step for the branching Rainbow-lite agent.

The replay buffer stores a joint action index ``move * num_fire + fire`` (0..80).
Each step we split that into per-branch indices, run the C51 distributional
Bellman projection independently for the move and fire branches (sharing the
reward / discount / support), and sum the two cross-entropy losses.  The PER
priority for a transition is the summed branch TD error.
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


def train_step(agent, prefetched_batch=None) -> float | None:
    """Run one branching C51 distributional training step.

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

    # ── Sample ──────────────────────────────────────────────────────────
    beta = _beta_schedule(metrics.frame_count)
    batch = prefetched_batch if prefetched_batch is not None else agent.memory.sample(RL_CONFIG.batch_size, beta=beta)
    if batch is None:
        return None

    states, actions, rewards, next_states, dones, horizons, is_expert, indices, weights = batch

    states_t      = torch.from_numpy(states).float().to(device)
    actions_t     = torch.from_numpy(actions).long().to(device)
    rewards_t     = torch.from_numpy(rewards).float().to(device)
    next_states_t = torch.from_numpy(next_states).float().to(device)
    dones_t       = torch.from_numpy(dones).float().to(device)
    horizons_t    = torch.from_numpy(horizons.astype(np.float32)).float().to(device)
    weights_t     = torch.from_numpy(weights).float().to(device)
    is_expert_t   = torch.from_numpy(is_expert).bool().to(device)

    B = states_t.shape[0]
    cfg = RL_CONFIG

    # Split joint action → (move, fire) branch indices
    num_fire = cfg.num_fire_actions
    move_actions_t = actions_t // num_fire
    fire_actions_t = actions_t % num_fire

    agent.online_net.train()
    agent._update_lr()

    use_amp = agent.use_amp and device.type == "cuda"
    scaler = agent.grad_scaler
    amp_ctx = torch.autocast(device_type="cuda", dtype=torch.float16) if use_amp else nullcontext()

    # ── Branching C51 distributional update ─────────────────────────────
    num_atoms = cfg.num_atoms
    v_min, v_max = cfg.v_min, cfg.v_max
    delta_z = (v_max - v_min) / (num_atoms - 1)
    support = agent.online_net.support  # (num_atoms,)
    arange = torch.arange(B, device=device)

    with amp_ctx:
        # Current distributions (log-probabilities), per branch
        move_log_p, fire_log_p = agent.online_net(states_t, log=True)   # each (B, A, N)
        move_log_p_a = move_log_p[arange, move_actions_t]               # (B, N)
        fire_log_p_a = fire_log_p[arange, fire_actions_t]               # (B, N)

        # Target distribution (Double-DQN: online selects, target evaluates)
        with torch.no_grad():
            move_q_next, fire_q_next = agent.online_net.q_values_branched(next_states_t)
            move_best = move_q_next.argmax(dim=1)          # (B,)
            fire_best = fire_q_next.argmax(dim=1)          # (B,)

            move_tp, fire_tp = agent.target_net(next_states_t, log=False)  # each (B, A, N)
            move_tp_a = move_tp[arange, move_best]         # (B, N)
            fire_tp_a = fire_tp[arange, fire_best]         # (B, N)

            # Shared projected Bellman support (same reward/discount for both branches)
            gamma_n = cfg.gamma ** horizons_t              # (B,)
            Tz = rewards_t.unsqueeze(1) + (1.0 - dones_t.unsqueeze(1)) * gamma_n.unsqueeze(1) * support.unsqueeze(0)
            Tz = Tz.clamp(v_min, v_max)

            b = (Tz - v_min) / delta_z                     # (B, N)
            l = b.floor().long().clamp(0, num_atoms - 1)
            u = b.ceil().long().clamp(0, num_atoms - 1)
            offset = torch.linspace(0, (B - 1) * num_atoms, B, device=device, dtype=torch.long).unsqueeze(1).expand_as(l)
            eq_mask = (l == u)
            neq_mask = ~eq_mask

            def _project(target_p_a: torch.Tensor) -> torch.Tensor:
                """Distribute a target distribution onto the fixed support."""
                m = torch.zeros(B, num_atoms, device=device, dtype=torch.float32)
                m.view(-1).index_add_(0, (l + offset).view(-1), (target_p_a * (u.float() - b) * neq_mask.float()).view(-1))
                m.view(-1).index_add_(0, (u + offset).view(-1), (target_p_a * (b - l.float()) * neq_mask.float()).view(-1))
                # When l == u the two weights above are both 0 → assign full mass directly.
                m.view(-1).index_add_(0, (l + offset).view(-1), (target_p_a * eq_mask.float()).view(-1))
                return m

            m_move = _project(move_tp_a)
            m_fire = _project(fire_tp_a)

        # Per-branch cross-entropy, averaged across the two heads so the C51
        # loss/priority scale matches a single-head baseline (summing would
        # double the TD scale and interact with LR / PER beta).
        ce_move = -(m_move * move_log_p_a).sum(dim=1)      # (B,)
        ce_fire = -(m_fire * fire_log_p_a).sum(dim=1)      # (B,)
        ce_loss = 0.5 * (ce_move + ce_fire)                # (B,)
        weighted_loss = (weights_t * ce_loss).mean()

    # ── Optional BC loss on expert transitions (per branch) ─────────────
    bc_loss_val = 0.0
    bc_w = _bc_weight_schedule(metrics.total_training_steps)
    if bc_w > 0.0 and is_expert_t.any():
        with amp_ctx:
            expert_idx = is_expert_t.nonzero(as_tuple=True)[0]
            if expert_idx.numel() > 0:
                move_q_e, fire_q_e = agent.online_net.q_values_branched(states_t[expert_idx])
                bc_loss = (F.cross_entropy(move_q_e, move_actions_t[expert_idx])
                           + F.cross_entropy(fire_q_e, fire_actions_t[expert_idx]))
                # Scale BC by sampled expert fraction to avoid over-weighting when
                # expert transitions are sparse but present in most batches.
                bc_scale = float(expert_idx.numel()) / float(B)
                weighted_loss = weighted_loss + (bc_w * bc_scale) * bc_loss
                bc_loss_val = float(bc_loss.detach().item())

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

    # ── Update priorities (mean branch TD error) ────────────────────────
    td_errors = ce_loss.detach().cpu().numpy()
    agent.memory.update_priorities(indices, td_errors)

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
        metrics.last_bc_loss = bc_loss_val
        metrics.last_priority_mean = float(np.mean(td_errors))

        # Directional agreement: argmax move/fire matches the stored action
        agree = 0.0
        with torch.no_grad():
            move_q_all, fire_q_all = agent.online_net.q_values_branched(states_t)
            metrics.last_q_mean = float(((move_q_all.mean() + fire_q_all.mean()) * 0.5).item())
            pred_move = move_q_all.argmax(dim=1)
            pred_fire = fire_q_all.argmax(dim=1)
            agree_move = (pred_move == move_actions_t).float().mean().item()
            agree_fire = (pred_fire == fire_actions_t).float().mean().item()
            agree = 0.5 * (agree_move + agree_fire)
            metrics.last_agreement = agree

        if hasattr(metrics, "agree_sum_interval"):
            metrics.agree_sum_interval += agree
            metrics.agree_count_interval += 1
        if hasattr(metrics, "loss_sum_interval"):
            metrics.loss_sum_interval += loss_val
            metrics.loss_count_interval += 1
    except Exception:
        pass

    return loss_val
