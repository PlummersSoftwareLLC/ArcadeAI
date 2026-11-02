"""CPU correctness tests for the complete compiled Robotron loss.

Run directly with Python. No CUDA device, replay files, or trainer services are
used. The reference intentionally uses scalar C51 projection and expert subsets
instead of the production vectorized projection and fixed-shape masks.
"""

import copy
from types import SimpleNamespace
import unittest

import torch
import torch.nn.functional as F

try:
    from .loss_kernel import TrainingLoss
except ImportError:
    from loss_kernel import TrainingLoss


class TinyNetwork(torch.nn.Module):
    """Deterministic stand-in exposing the production network's four methods."""

    def __init__(self):
        super().__init__()
        self.encoder = torch.nn.Linear(7, 9)
        self.atoms = torch.nn.Linear(9, 30)
        self.bc_joint_head = torch.nn.Linear(9, 6)
        self.bc_move_head = torch.nn.Linear(9, 2)
        self.bc_fire_head = torch.nn.Linear(9, 3)
        self.register_buffer("support", torch.linspace(-2, 2, 5))

    def training_outputs(self, states):
        hidden = F.relu(self.encoder(states))
        return (
            F.log_softmax(self.atoms(hidden).view(-1, 6, 5), dim=2),
            self.bc_joint_head(hidden),
            self.bc_move_head(hidden),
            self.bc_fire_head(hidden),
        )

    def joint_dist(self, states, log=False):
        atoms = self.atoms(F.relu(self.encoder(states))).view(-1, 6, 5)
        return F.log_softmax(atoms, dim=2) if log else F.softmax(atoms, dim=2)

    def q_values_joint(self, states):
        return (self.joint_dist(states) * self.support).sum(dim=2)


def reference_loss(online, target, args, schedules, cfg):
    """Independent scalar-bin/subset-expert form of the original objective."""
    states, actions, rewards, next_states, dones, horizons, expert, weights = args
    batch_size = len(states)
    rows = torch.arange(batch_size)
    log_p, joint_logits, move_logits, fire_logits = online.training_outputs(states)
    support = online.support

    with torch.no_grad():
        next_q = online.q_values_joint(next_states)
        best_actions = next_q.argmax(dim=1)
        target_p = target.joint_dist(next_states)[rows, best_actions]
        projected = torch.zeros(batch_size, cfg.num_atoms)
        delta_z = (cfg.v_max - cfg.v_min) / (cfg.num_atoms - 1)
        raw_transformed = (
            rewards[:, None]
            + (1 - dones[:, None]) * (cfg.gamma ** horizons[:, None]) * support
        )
        transformed = raw_transformed.clamp(cfg.v_min, cfg.v_max)
        bins = (transformed - cfg.v_min) / delta_z
        for row in range(batch_size):
            for atom in range(cfg.num_atoms):
                position = bins[row, atom]
                lower, upper = int(position.floor()), int(position.ceil())
                if lower == upper:
                    projected[row, lower] += target_p[row, atom]
                else:
                    projected[row, lower] += target_p[row, atom] * (upper - position)
                    projected[row, upper] += target_p[row, atom] * (position - lower)
        # Exact-bin and clipped terminal targets must retain all their mass.
        torch.testing.assert_close(projected.sum(dim=1), torch.ones(batch_size))
        smoothing = cfg.c51_target_smoothing
        projected = projected * (1 - smoothing) + smoothing / cfg.num_atoms

    ce_loss = -(projected * log_p[rows, actions]).sum(dim=1)
    loss = (weights * ce_loss).mean()
    bc_loss = loss.new_zeros(())
    mask = expert.bool()
    expert_count = int(mask.sum())
    expert_fraction = expert_count / batch_size
    bc_weight, q_weight, margin_weight = map(float, schedules)
    if expert_count:
        if bc_weight > 0:
            bc_loss = F.cross_entropy(joint_logits[mask], actions[mask])
            bc_loss = bc_loss + cfg.branch_aux_bc_weight * 0.5 * (
                F.cross_entropy(move_logits[mask], actions[mask] // cfg.num_fire_actions)
                + F.cross_entropy(fire_logits[mask], actions[mask] % cfg.num_fire_actions)
            )
            effective_bc = max(cfg.expert_bc_effective_floor, bc_weight * expert_fraction)
            loss = loss + effective_bc * bc_loss
        joint_q = (log_p[mask].exp() * support).sum(dim=2)
        if q_weight > 0:
            loss = loss + q_weight * expert_fraction * F.cross_entropy(
                joint_q / cfg.expert_q_policy_temperature, actions[mask],
            )
        if margin_weight > 0:
            margins = torch.full_like(joint_q, cfg.expert_q_margin)
            margins.scatter_(1, actions[mask, None], 0)
            expert_q = joint_q.gather(1, actions[mask, None]).squeeze(1)
            per_row = (joint_q + margins).max(dim=1).values - expert_q
            loss = loss + margin_weight * expert_fraction * per_row.mean()

    with torch.no_grad():
        q = (log_p.float().exp() * support).sum(dim=2)
        predicted = q.argmax(dim=1)
        overestimation = (next_q.max(dim=1).values - (target_p * support).sum(dim=1)).mean()
        below_mass, above_mass = 0.0, 0.0
        for row in range(batch_size):
            for atom in range(cfg.num_atoms):
                if raw_transformed[row, atom] < cfg.v_min:
                    below_mass += float(target_p[row, atom]) / batch_size
                elif raw_transformed[row, atom] > cfg.v_max:
                    above_mass += float(target_p[row, atom]) / batch_size
        taken_p = log_p[rows, actions].float().exp()
        edge_mass = (taken_p[:, 0] + taken_p[:, -1]).mean()
        entropy = -(projected * projected.clamp_min(1e-12).log()).sum(dim=1)
        sorted_q = q.sort(dim=1, descending=True).values
        diagnostics = torch.stack((
            q.min(), q.max(), overestimation, q.mean(),
            ((predicted // cfg.num_fire_actions) == (actions // cfg.num_fire_actions)).float().mean(),
            ((predicted % cfg.num_fire_actions) == (actions % cfg.num_fire_actions)).float().mean(),
            q.new_tensor(below_mass), q.new_tensor(above_mass), edge_mass,
            entropy.mean(), (sorted_q[:, 0] - sorted_q[:, 1]).mean(),
            (ce_loss - entropy).mean(),
        ))
    return loss, ce_loss, bc_loss, diagnostics


def clear_inactive_bc_gradients(online, expert, schedules):
    """Mirror the caller's optimizer contract for the always-masked graph.

    Original subset loss left unused BC-head gradients at None. The compiled
    masked graph emits zeros instead, so the caller restores None to avoid
    decaying Adam moments or advancing optimizer clocks on an inactive head.
    """
    if not bool(expert.any()) or float(schedules[0]) <= 0:
        for head in (online.bc_joint_head, online.bc_move_head, online.bc_fire_head):
            for parameter in head.parameters():
                parameter.grad = None


class TestTrainingLoss(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.previous_threads)

    def setUp(self):
        torch.manual_seed(17)
        self.online = TinyNetwork()
        self.target = TinyNetwork()
        self.cfg = SimpleNamespace(
            num_fire_actions=3, num_atoms=5, v_min=-2, v_max=2, gamma=0.95,
            c51_target_smoothing=0.01, branch_aux_bc_weight=0.25,
            expert_bc_effective_floor=0.01, expert_q_policy_temperature=1.7,
            expert_q_margin=0.5,
        )
        self.states = torch.randn(8, 7)
        self.next_states = torch.randn(8, 7)
        self.actions = torch.tensor([0, 1, 2, 3, 4, 5, 0, 2])
        # The first three rows cover below-support, above-support, and exact
        # interior terminal bins. Remaining rows exercise multi-step bootstrap.
        self.rewards = torch.tensor([-4.0, 4.0, 0.0, 0.3, -0.5, 2.0, -2.0, 1.0])
        self.dones = torch.tensor([1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.horizons = torch.tensor([1.0, 3.0, 4.0, 2.0, 3.0, 1.0, 2.0, 4.0])
        self.weights = torch.linspace(0.4, 1.0, 8)

    def args(self, expert):
        return (
            self.states, self.actions, self.rewards, self.next_states,
            self.dones, self.horizons, expert, self.weights,
        )

    def assert_outputs(self, actual, expected):
        for value, reference in zip(actual, expected):
            torch.testing.assert_close(value, reference, rtol=2e-6, atol=2e-7)

    def assert_gradients(self, actual, reference):
        for (name, parameter), (ref_name, ref_parameter) in zip(
                actual.named_parameters(), reference.named_parameters()):
            self.assertEqual(name, ref_name)
            if ref_parameter.grad is None:
                self.assertIsNone(parameter.grad, name)
            else:
                self.assertIsNotNone(parameter.grad, name)
                torch.testing.assert_close(
                    parameter.grad, ref_parameter.grad, rtol=1e-5, atol=2e-7,
                )

    def test_fifteen_reference_value_and_gradient_cases(self):
        expert_masks = (
            torch.zeros(8, dtype=torch.bool),
            torch.tensor([1, 0, 1, 0, 0, 1, 0, 0], dtype=torch.bool),
            torch.ones(8, dtype=torch.bool),
        )
        schedule_cases = (
            [0.0, 0.0, 0.0], [0.4, 0.25, 0.13],
            [0.00001, 0.25, 0.0], [0.0, 0.0, 0.2], [-0.1, -0.2, -0.3],
        )
        for mask_index, expert in enumerate(expert_masks):
            for schedule_values in schedule_cases:
                with self.subTest(expert_mask=mask_index, schedules=schedule_values):
                    online, target = copy.deepcopy(self.online), copy.deepcopy(self.target)
                    ref_online, ref_target = copy.deepcopy(self.online), copy.deepcopy(self.target)
                    schedules = torch.tensor(schedule_values)
                    args = self.args(expert)
                    actual = TrainingLoss(online, target, self.cfg)(*args, schedules)
                    expected = reference_loss(ref_online, ref_target, args, schedules, self.cfg)
                    self.assert_outputs(actual, expected)
                    actual[0].backward()
                    expected[0].backward()
                    # Raw masked BC grads must be zeros when the old path was
                    # absent; then the caller restores None before Adam.
                    for (_, parameter), (_, ref_parameter) in zip(
                            online.named_parameters(), ref_online.named_parameters()):
                        if ref_parameter.grad is None and parameter.grad is not None:
                            self.assertEqual(int(torch.count_nonzero(parameter.grad)), 0)
                    clear_inactive_bc_gradients(online, expert, schedules)
                    self.assert_gradients(online, ref_online)
                    self.assertTrue(all(parameter.grad is None for parameter in target.parameters()))

    def test_unsmoothed_targets_match_reference_values_and_gradients(self):
        self.cfg.c51_target_smoothing = 0.0
        expert = torch.arange(8) % 2 == 0
        schedules = torch.tensor([0.05, 0.05, 0.0])
        ref_online = copy.deepcopy(self.online)
        actual = TrainingLoss(self.online, self.target, self.cfg)(*self.args(expert), schedules)
        expected = reference_loss(ref_online, self.target, self.args(expert), schedules, self.cfg)
        self.assert_outputs(actual, expected)
        actual[0].backward()
        expected[0].backward()
        self.assert_gradients(self.online, ref_online)
        self.assertTrue(torch.isfinite(actual[0]))

        # Exact terminal returns retain their point mass without smoothing;
        # entropy may reach zero while cross entropy and gradients remain valid.
        self.dones = torch.ones(8)
        self.rewards = torch.zeros(8)
        terminal = TrainingLoss(self.online, self.target, self.cfg)(*self.args(expert), schedules)
        self.assertAlmostEqual(float(terminal[3][9]), 0.0, places=7)
        self.assertTrue(torch.isfinite(terminal[0]))

    def test_fullgraph_aot_forward_and_backward(self):
        schedule_cases = (
            (torch.zeros(8, dtype=torch.bool), torch.zeros(3)),
            (torch.ones(8, dtype=torch.bool), torch.tensor([0.4, 0.25, 0.13])),
            (torch.arange(8) % 2 == 0, torch.tensor([0.001, 0.0, 0.3])),
        )
        for diagnostics in (False, True):
            online, target = copy.deepcopy(self.online), copy.deepcopy(self.target)
            kernel = TrainingLoss(online, target, self.cfg, diagnostics=diagnostics)
            try:
                compiled = torch.compile(kernel, backend="aot_eager", fullgraph=True, dynamic=False)
            except RuntimeError as error:
                if "not supported on Python" in str(error):
                    self.skipTest(str(error))
                raise
            for expert, schedules in schedule_cases:
                with self.subTest(diagnostics=diagnostics, schedules=schedules.tolist()):
                    args = self.args(expert)
                    actual, expected = compiled(*args, schedules), kernel(*args, schedules)
                    self.assert_outputs(actual, expected)
                    self.assertEqual(tuple(actual[3].shape), (12,))
                    if not diagnostics:
                        self.assertEqual(int(torch.count_nonzero(actual[3])), 0)
                    actual[0].backward()
                    compiled_grads = [None if p.grad is None else p.grad.clone() for p in online.parameters()]
                    online.zero_grad(set_to_none=True)
                    expected[0].backward()
                    for parameter, gradient in zip(online.parameters(), compiled_grads):
                        if gradient is None:
                            self.assertIsNone(parameter.grad)
                        else:
                            torch.testing.assert_close(gradient, parameter.grad, rtol=1e-5, atol=2e-7)
                    online.zero_grad(set_to_none=True)
                    self.assertTrue(all(parameter.grad is None for parameter in target.parameters()))

    def test_terminal_clipping_mass_excludes_exact_boundaries(self):
        # Only two rows exceed support. Exact endpoints must not count as
        # clipped even though projection places their mass on an edge atom.
        self.rewards = torch.tensor([-4.0, 4.0, -2.0, 2.0, 0.0, 0.0, 0.0, 0.0])
        self.dones = torch.ones(8)
        expert = torch.zeros(8, dtype=torch.bool)
        schedules = torch.zeros(3)
        with torch.no_grad():
            output = TrainingLoss(self.online, self.target, self.cfg)(*self.args(expert), schedules)
        diagnostics = output[3]
        torch.testing.assert_close(diagnostics[6:8], torch.tensor([1 / 8, 1 / 8]))
        atom_probabilities = torch.full((5,), self.cfg.c51_target_smoothing / 5)
        atom_probabilities[0] += 1 - self.cfg.c51_target_smoothing
        entropy = -(atom_probabilities * atom_probabilities.log()).sum()
        torch.testing.assert_close(diagnostics[9], entropy)
        torch.testing.assert_close(diagnostics[11], output[1].mean() - entropy)
        self.assertGreaterEqual(float(diagnostics[8]), 0.0)
        self.assertLessEqual(float(diagnostics[8]), 1.0)
        self.assertGreaterEqual(float(diagnostics[10]), 0.0)

    def test_diagnostic_toggle_preserves_objective_and_gradients(self):
        expert = torch.arange(8) % 2 == 0
        schedules = torch.tensor([0.4, 0.25, 0.13])
        active_online = copy.deepcopy(self.online)
        inactive_online = copy.deepcopy(self.online)
        active = TrainingLoss(active_online, self.target, self.cfg, diagnostics=True)(*self.args(expert), schedules)
        inactive = TrainingLoss(inactive_online, self.target, self.cfg, diagnostics=False)(*self.args(expert), schedules)
        for active_value, inactive_value in zip(active[:3], inactive[:3]):
            torch.testing.assert_close(active_value, inactive_value, rtol=0, atol=0)
        self.assertFalse(active[3].requires_grad)
        active[0].backward()
        inactive[0].backward()
        self.assert_gradients(active_online, inactive_online)

    def test_adam_skips_inactive_bc_head_moments(self):
        online, target = copy.deepcopy(self.online), copy.deepcopy(self.target)
        ref_online, ref_target = copy.deepcopy(self.online), copy.deepcopy(self.target)
        optimizer = torch.optim.Adam(online.parameters(), lr=0.001)
        ref_optimizer = torch.optim.Adam(ref_online.parameters(), lr=0.001)
        kernel = TrainingLoss(online, target, self.cfg)
        cases = (
            (torch.ones(8, dtype=torch.bool), torch.tensor([0.4, 0.25, 0.13])),
            (torch.ones(8, dtype=torch.bool), torch.zeros(3)),
            (torch.zeros(8, dtype=torch.bool), torch.tensor([0.4, 0.25, 0.13])),
        )
        for expert, schedules in cases:
            optimizer.zero_grad(set_to_none=True)
            ref_optimizer.zero_grad(set_to_none=True)
            actual = kernel(*self.args(expert), schedules)
            expected = reference_loss(ref_online, ref_target, self.args(expert), schedules, self.cfg)
            actual[0].backward()
            expected[0].backward()
            clear_inactive_bc_gradients(online, expert, schedules)
            self.assert_gradients(online, ref_online)
            optimizer.step()
            ref_optimizer.step()
            for parameter, reference in zip(online.parameters(), ref_online.parameters()):
                torch.testing.assert_close(parameter, reference, rtol=2e-6, atol=2e-7)
                actual_state, reference_state = optimizer.state[parameter], ref_optimizer.state[reference]
                for key in ("step", "exp_avg", "exp_avg_sq"):
                    torch.testing.assert_close(actual_state[key], reference_state[key], rtol=1e-5, atol=2e-7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
