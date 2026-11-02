"""Fixed-shape tensor-only Robotron C51 loss for whole-graph compilation.

The caller owns autocast, finite-loss checks, optimization, PER readback, and
target/inference synchronization. Keeping schedules as a device tensor lets
compiled graphs retain the same guards while learning weights evolve.
"""

import torch
import torch.nn.functional as F


def categorical_priority_values(cross_entropy, projected, metric):
    """Detached replay surprise, independent of the CE training objective."""
    cross_entropy = cross_entropy.detach().float()
    if metric == "ce":
        return cross_entropy
    if metric != "kl":
        raise ValueError("PER priority metric must be ce or kl")
    with torch.no_grad():
        target = projected.detach().float()
        entropy = -(target * target.clamp_min(1e-12).log()).sum(dim=1)
        return (cross_entropy - entropy).clamp_min(0.0)


class TrainingLoss(torch.nn.Module):
    """Bind the online/target networks and immutable loss constants.

    ``schedule_weights`` is a three-element tensor on the states' device:
    behavioral cloning, joint-Q imitation, and expert Q-margin weights.
    Diagnostics are a constructor constant, so separate compiled diagnostic
    and ordinary variants need no data-dependent Python control flow.

    The diagnostic vector is: Q minimum, Q maximum, overestimation, Q mean,
    move agreement, fire agreement, Bellman mass clipped below support,
    Bellman mass clipped above support, taken-action edge-atom probability,
    projected target entropy, top-two action Q gap, and mean categorical KL.
    Probabilities and entropies are unweighted batch means; clipping mass is
    measured before projection and before target smoothing.
    """

    def __init__(self, online_net, target_net, cfg, diagnostics=True, return_priorities=False):
        super().__init__()
        self.online_net = online_net
        self.target_net = target_net
        self.num_fire = int(cfg.num_fire_actions)
        self.num_atoms = int(cfg.num_atoms)
        self.v_min = float(cfg.v_min)
        self.v_max = float(cfg.v_max)
        self.delta_z = (self.v_max - self.v_min) / (self.num_atoms - 1)
        self.gamma = float(cfg.gamma)
        self.smooth_eps = float(getattr(cfg, "c51_target_smoothing", 0.0))
        self.branch_aux = float(getattr(cfg, "branch_aux_bc_weight", 0.25))
        self.bc_floor = float(getattr(cfg, "expert_bc_effective_floor", 0.01))
        self.q_temperature = max(1e-3, float(getattr(cfg, "expert_q_policy_temperature", 10.0)))
        self.q_margin = float(getattr(cfg, "expert_q_margin", 0.5))
        self.diagnostics = bool(diagnostics)
        self.return_priorities = bool(return_priorities)
        self.priority_metric = str(getattr(cfg, "per_priority_metric", "ce"))
        if self.priority_metric not in ("ce", "kl"):
            raise ValueError("PER priority metric must be ce or kl")

    def forward(self, states, actions, rewards, next_states, dones, horizons,
                is_expert, weights, schedule_weights):
        batch_size = states.shape[0]
        support = self.online_net.support
        rows = torch.arange(batch_size, device=states.device)

        joint_log_p, joint_logits, move_logits, fire_logits = self.online_net.training_outputs(states)
        joint_log_p_a = joint_log_p[rows, actions]

        with torch.no_grad():
            joint_q_next = self.online_net.q_values_joint(next_states)
            best = joint_q_next.argmax(dim=1)
            target_p = self.target_net.joint_dist(next_states, log=False)
            target_p_a = target_p[rows, best]
            gamma_n = self.gamma ** horizons
            target_support = rewards[:, None] + (1.0 - dones[:, None]) * gamma_n[:, None] * support[None, :]
            if self.diagnostics:
                target_probabilities = target_p_a.float()
                below_support_mass = (
                    target_probabilities * (target_support < self.v_min)
                ).sum(dim=1).mean()
                above_support_mass = (
                    target_probabilities * (target_support > self.v_max)
                ).sum(dim=1).mean()
            target_support = target_support.clamp(self.v_min, self.v_max)
            bins = (target_support - self.v_min) / self.delta_z
            lower = bins.floor().long().clamp(0, self.num_atoms - 1)
            upper = bins.ceil().long().clamp(0, self.num_atoms - 1)
            offsets = (rows * self.num_atoms)[:, None]
            equal = lower == upper
            unequal = ~equal
            projected = torch.zeros(
                (batch_size, self.num_atoms), device=states.device, dtype=torch.float32,
            )
            flat = projected.view(-1)
            flat.index_add_(
                0, (lower + offsets).reshape(-1),
                (target_p_a * (upper.float() - bins) * unequal.float()).reshape(-1),
            )
            flat.index_add_(
                0, (upper + offsets).reshape(-1),
                (target_p_a * (bins - lower.float()) * unequal.float()).reshape(-1),
            )
            flat.index_add_(
                0, (lower + offsets).reshape(-1),
                (target_p_a * equal.float()).reshape(-1),
            )
            if self.smooth_eps > 0.0:
                projected = projected * (1.0 - self.smooth_eps) + self.smooth_eps / self.num_atoms

        ce_loss = -(projected * joint_log_p_a).sum(dim=1)
        weighted_loss = (weights * ce_loss).mean()

        expert_mask = is_expert.to(dtype=torch.float32)
        expert_count = expert_mask.sum()
        expert_fraction = expert_count / batch_size
        expert_denominator = expert_count.clamp_min(1.0)
        move_actions = actions // self.num_fire
        fire_actions = actions % self.num_fire

        per_row_bc = F.cross_entropy(joint_logits, actions, reduction="none")
        per_row_bc = per_row_bc + self.branch_aux * 0.5 * (
            F.cross_entropy(move_logits, move_actions, reduction="none")
            + F.cross_entropy(fire_logits, fire_actions, reduction="none")
        )
        masked_bc = (per_row_bc * expert_mask).sum() / expert_denominator
        bc_active = (schedule_weights[0] > 0.0) & (expert_count > 0.0)
        bc_loss = torch.where(bc_active, masked_bc, torch.zeros_like(masked_bc))
        effective_bc = (schedule_weights[0] * expert_fraction).clamp_min(self.bc_floor)
        weighted_loss = weighted_loss + effective_bc * bc_loss

        # Keep Q loss in the original arithmetic dtype under the caller's
        # autocast context. Diagnostic reductions below explicitly use fp32.
        joint_q = (joint_log_p.exp() * support[None, None, :]).sum(dim=2)
        per_row_q_policy = F.cross_entropy(joint_q / self.q_temperature, actions, reduction="none")
        weighted_loss = weighted_loss + schedule_weights[1].clamp_min(0.0) * (per_row_q_policy * expert_mask).sum() / batch_size

        expert_q = joint_q.gather(1, actions[:, None]).squeeze(1)
        margin = torch.full_like(joint_q, self.q_margin)
        margin.scatter_(1, actions[:, None], 0.0)
        per_row_margin = (joint_q + margin).max(dim=1).values - expert_q
        weighted_loss = weighted_loss + schedule_weights[2].clamp_min(0.0) * (per_row_margin * expert_mask).sum() / batch_size

        with torch.no_grad():
            if self.diagnostics:
                q = (joint_log_p.detach().float().exp() * support[None, None, :]).sum(dim=2)
                target_q = (target_p_a.float() * support[None, :]).sum(dim=1)
                overestimation = (joint_q_next.float().max(dim=1).values - target_q).mean()
                predicted = q.argmax(dim=1)
                taken_probabilities = joint_log_p_a.detach().float().exp()
                edge_mass = (taken_probabilities[:, 0] + taken_probabilities[:, -1]).mean()
                target_entropy_per_row = -(
                    projected * projected.clamp_min(1e-12).log()
                ).sum(dim=1)
                top_q = q.topk(2, dim=1).values
                q_gap = (top_q[:, 0] - top_q[:, 1]).mean()
                categorical_kl = (ce_loss.detach().float() - target_entropy_per_row).mean()
                diagnostic_values = torch.stack((
                    q.min(), q.max(), overestimation, q.mean(),
                    ((predicted // self.num_fire) == move_actions).float().mean(),
                    ((predicted % self.num_fire) == fire_actions).float().mean(),
                    below_support_mass, above_support_mass, edge_mass,
                    target_entropy_per_row.mean(), q_gap, categorical_kl,
                ))
            else:
                diagnostic_values = torch.zeros(12, device=states.device, dtype=torch.float32)
        if self.return_priorities:
            priorities = categorical_priority_values(ce_loss, projected, self.priority_metric)
            return weighted_loss, ce_loss, bc_loss, diagnostic_values, priorities
        return weighted_loss, ce_loss, bc_loss, diagnostic_values
