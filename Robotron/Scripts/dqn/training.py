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
        states, actions, rewards, next_states, dones, horizons, is_expert, actor_kind, indices, weights = batch
    else:
        states, actions, rewards, next_states, dones, horizons, is_expert, indices, weights = batch
        actor_kind = np.where(is_expert > 0, ACTOR_EXPERT, ACTOR_DQN).astype(np.uint8)

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
        _joint_dist_online = agent.compiled_online_joint_dist or agent.online_net.joint_dist
        _q_joint_online = agent.compiled_online_q_joint or agent.online_net.q_values_joint
        _joint_dist_target = agent.compiled_target_joint_dist or agent.target_net.joint_dist
        joint_log_p = _joint_dist_online(states_t, log=True)            # (B, 81, N)
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

            # ── Bootstrap-free MC anchor on hall-of-fame rows ───────────────
            # Everything above is Tz = r + gamma^h * Q_target(s'), i.e. ~92%
            # bootstrap.  Robotron has no positive terminal, so that recursion's
            # only ground truth is a death at v_min: the positive value surface
            # is held up purely by other predictions, and when the high-return
            # data drains from the ring it deflates monotonically at healthy
            # loss (verified twice: Q-max 34->~12, EScr1M 72k->48k, EpLen up).
            # HOF replay alone could not stop it BECAUSE those rows were
            # bootstrapped through the same collapsing net.
            #
            # For HOF rows we know something the recursion does not: what the
            # episode ACTUALLY returned.  Regress them onto that measured value
            # instead (a delta at G projected onto the support).  It cannot
            # deflate with the network and carries no demonstrator ceiling.
            if bool(getattr(cfg, "hof_mc_return_targets", False)):
                mem = agent.memory
                cap = int(getattr(mem, "capacity", 0))
                hof_mc = getattr(mem, "hof_mc_return", None)
                idx_np = np.asarray(indices)
                # HOF rows carry sentinel indices >= capacity encoding their
                # flat slot (replay_buffer.sample), so no signature change.
                hof_rows = idx_np >= cap
                if hof_mc is not None and cap > 0 and bool(hof_rows.any()):
                    g_np = np.zeros(B, dtype=np.float32)
                    ok_np = np.zeros(B, dtype=bool)
                    slots = (idx_np[hof_rows] - cap).astype(np.int64)
                    valid_slot = (slots >= 0) & (slots < hof_mc.shape[0])
                    g_slot = np.full(slots.shape[0], np.nan, dtype=np.float32)
                    g_slot[valid_slot] = hof_mc[slots[valid_slot]]
                    finite = np.isfinite(g_slot)
                    g_np[hof_rows] = np.nan_to_num(g_slot, nan=0.0)
                    ok_np[hof_rows] = finite          # NaN -> keep Bellman target
                    if bool(ok_np.any()):
                        g_t = torch.from_numpy(g_np).to(device=device, dtype=torch.float32)
                        ok_t = torch.from_numpy(ok_np).to(device=device)
                        b_mc = (g_t.clamp(v_min, v_max) - v_min) / delta_z   # (B,)
                        l_mc = b_mc.floor().long().clamp(0, num_atoms - 1)
                        u_mc = b_mc.ceil().long().clamp(0, num_atoms - 1)
                        eq_mc = (l_mc == u_mc)
                        # Two-point projection of a delta at G; when the atom is
                        # hit exactly, all mass lands on it.
                        w_l = torch.where(eq_mc, torch.ones_like(b_mc), u_mc.float() - b_mc)
                        w_u = torch.where(eq_mc, torch.zeros_like(b_mc), b_mc - l_mc.float())
                        m_mc = torch.zeros(B, num_atoms, device=device, dtype=torch.float32)
                        m_mc.scatter_add_(1, l_mc.unsqueeze(1), w_l.unsqueeze(1))
                        m_mc.scatter_add_(1, u_mc.unsqueeze(1), w_u.unsqueeze(1))
                        m_joint = torch.where(ok_t.unsqueeze(1), m_mc, m_joint)

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

    # ── Optional BC loss on expert transitions (joint + auxiliary branches) ──
    bc_loss_val = 0.0
    bc_w = _bc_weight_schedule(metrics.total_training_steps)
    sample_expert_frac = float(is_expert_t.float().mean().item()) if B > 0 else 0.0
    actor_kind_np = np.asarray(actor_kind, dtype=np.uint8)
    sample_dqn_frac = float(np.mean(actor_kind_np == ACTOR_DQN)) if B > 0 else 0.0
    sample_epsilon_frac = float(np.mean(actor_kind_np == ACTOR_EPSILON)) if B > 0 else 0.0
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
            bc_scale = _expert_batch_scale(int(expert_idx.numel()), B)
            weighted_loss = weighted_loss + (bc_w * bc_scale) * bc_loss
            bc_loss_val = float(bc_loss.detach().item())

    q_policy_w = _q_policy_weight_schedule(metrics.total_training_steps)
    margin_w = _margin_weight_schedule(metrics.total_training_steps)
    if (q_policy_w > 0.0 or margin_w > 0.0) and expert_idx is not None and expert_idx.numel() > 0:
        with amp_ctx:
            joint_q_e = (joint_log_p[expert_idx].exp() * support.view(1, 1, -1)).sum(dim=2)
            expert_actions = actions_t[expert_idx]
            bc_scale = _expert_batch_scale(int(expert_idx.numel()), B)
            if q_policy_w > 0.0:
                temp = max(1e-3, float(getattr(cfg, "expert_q_policy_temperature", 10.0)))
                q_policy_loss = F.cross_entropy(joint_q_e / temp, expert_actions)
                weighted_loss = weighted_loss + (q_policy_w * bc_scale) * q_policy_loss
            if margin_w > 0.0:
                expert_q = joint_q_e.gather(1, expert_actions.unsqueeze(1)).squeeze(1)
                margin = torch.full_like(joint_q_e, float(getattr(cfg, "expert_q_margin", 0.5)))
                margin.scatter_(1, expert_actions.unsqueeze(1), 0.0)
                margin_loss = (joint_q_e + margin).max(dim=1).values - expert_q
                weighted_loss = weighted_loss + (margin_w * bc_scale) * margin_loss.mean()

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
        metrics.last_bc_loss = bc_loss_val
        metrics.last_bc_weight = float(bc_w)
        metrics.last_sample_dqn_frac = sample_dqn_frac
        metrics.last_sample_epsilon_frac = sample_epsilon_frac
        metrics.last_sample_expert_frac = sample_expert_frac
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
            pred_joint = joint_q_all.argmax(dim=1)
            pred_move = pred_joint // num_fire
            pred_fire = pred_joint % num_fire
            agree_move = (pred_move == move_actions_t).float().mean().item()
            agree_fire = (pred_fire == fire_actions_t).float().mean().item()
            agree = 0.5 * (agree_move + agree_fire)
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
        if sample_prefetched:
            total_ms += sample_ms
        metrics.last_train_step_ms = float(total_ms)
    except Exception:
        pass

    return loss_val
