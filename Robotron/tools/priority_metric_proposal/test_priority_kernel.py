"""Exercise staged, unapplied proposal with real CPU loss/backward and Adam."""
import ast
import copy
import importlib.util
import os
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '2'
import numpy as np
import torch

from Robotron.Scripts.dqn import test_loss_kernel as original_cases
from .analyze_replay_priorities import per_row_metrics, projected_target
from .build_proposal import OUTPUT

STAGED = Path(os.environ.get('ROBOTRON_PRIORITY_PROPOSAL_DIR', str(OUTPUT))) / 'staged/Robotron/Scripts/dqn'


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, STAGED / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loss = load_module('proposal_loss_kernel', 'loss_kernel.py')


class ProposedKernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        case = original_cases.TestTrainingLoss()
        case.setUp()
        self.case = case
        self.cfg = copy.copy(case.cfg)
        self.expert = torch.arange(8) % 2 == 0
        self.schedules = torch.tensor([.4, .25, .13])

    def test_ce_default_keeps_all_original_values_and_backward(self):
        from Robotron.Scripts.dqn.loss_kernel import TrainingLoss
        original_online = copy.deepcopy(self.case.online)
        proposed_online = copy.deepcopy(self.case.online)
        old = TrainingLoss(original_online, self.case.target, self.cfg)(*self.case.args(self.expert), self.schedules)
        new = loss.TrainingLoss(proposed_online, self.case.target, self.cfg)(*self.case.args(self.expert), self.schedules)
        self.assertEqual(len(new), 4)
        for a, b in zip(old, new):
            torch.testing.assert_close(a, b, rtol=0, atol=0)
        old[0].backward()
        new[0].backward()
        for a, b in zip(original_online.parameters(), proposed_online.parameters()):
            if a.grad is None:
                self.assertIsNone(b.grad)
            else:
                torch.testing.assert_close(a.grad, b.grad, rtol=0, atol=0)

    def test_kl_is_per_row_target_divergence_detached_and_objective_identical(self):
        args = self.case.args(self.expert)
        self.cfg.per_priority_metric = 'ce'
        ce_online = copy.deepcopy(self.case.online)
        ce = loss.TrainingLoss(ce_online, self.case.target, self.cfg, return_priorities=True)(*args, self.schedules)
        self.cfg.per_priority_metric = 'kl'
        kl_online = copy.deepcopy(self.case.online)
        kl = loss.TrainingLoss(kl_online, self.case.target, self.cfg, return_priorities=True)(*args, self.schedules)
        for a, b in zip(ce[:4], kl[:4]):
            torch.testing.assert_close(a, b, rtol=0, atol=0)
        with torch.no_grad():
            rows = torch.arange(8)
            best = kl_online.q_values_joint(self.case.next_states).argmax(1)
            targets = self.case.target.joint_dist(self.case.next_states)[rows, best]
            targets = projected_target(targets, self.case.rewards, self.case.dones, self.case.horizons,
                                       kl_online.support, self.cfg.gamma, self.cfg.c51_target_smoothing)
            log_p = kl_online.joint_dist(self.case.states, log=True)[rows, self.case.actions]
            expected_ce, entropy, expected_kl = per_row_metrics(log_p, targets)
        torch.testing.assert_close(ce[4], expected_ce)
        torch.testing.assert_close(kl[4], expected_kl)
        self.assertFalse(kl[4].requires_grad)
        self.assertTrue(torch.all(kl[4] >= 0))
        self.assertGreater(float(entropy.mean()), 0.)
        ce[0].backward()
        kl[0].backward()
        for a, b in zip(ce_online.parameters(), kl_online.parameters()):
            torch.testing.assert_close(a.grad, b.grad, rtol=0, atol=0)

    def test_compiled_kl_priorities_and_gradients_match_with_diagnostics_on_and_off(self):
        self.cfg.per_priority_metric = 'kl'
        for diagnostics in (False, True):
            online = copy.deepcopy(self.case.online)
            kernel = loss.TrainingLoss(online, self.case.target, self.cfg,
                                       diagnostics=diagnostics, return_priorities=True)
            compiled = torch.compile(kernel, backend='aot_eager', fullgraph=True, dynamic=False)
            actual = compiled(*self.case.args(self.expert), self.schedules)
            expected = kernel(*self.case.args(self.expert), self.schedules)
            self.assertEqual(len(actual), 5)
            for a, b in zip(actual, expected):
                torch.testing.assert_close(a, b)
            actual[0].backward()
            gradients = [parameter.grad.clone() for parameter in online.parameters()]
            online.zero_grad(set_to_none=True)
            expected[0].backward()
            for old, parameter in zip(gradients, online.parameters()):
                torch.testing.assert_close(old, parameter.grad)

    def test_environment_validation_defaults_and_rejects_invalid_values(self):
        module = ast.parse((STAGED / 'config.py').read_text())
        function = next(node for node in module.body if isinstance(node, ast.FunctionDef)
                        and node.name == '_validated_per_priority_metric')
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'config.py', 'exec'), namespace)
        validate = namespace['_validated_per_priority_metric']
        self.assertEqual(validate('ce'), 'ce')
        self.assertEqual(validate(' KL '), 'kl')
        for value in ('', 'td', 'kll', None):
            with self.assertRaises(ValueError):
                validate(value)
        self.cfg.per_priority_metric = 'invalid'
        with self.assertRaises(ValueError):
            loss.TrainingLoss(self.case.online, self.case.target, self.cfg)

    def test_training_readback_routes_distinct_priorities_and_keeps_ce_slice_metrics(self):
        """Real CPU eager/kernel training catches packed-vector offset errors."""
        for mode in ('ce', 'kl'):
            for kernel_active in (False, True):
                with self.subTest(mode=mode, kernel=kernel_active):
                    cfg = copy.copy(self.cfg)
                    cfg.__dict__.update(per_priority_metric=mode, batch_size=8, min_replay_to_train=0,
                        max_samples_per_frame=0., baseline_batch_size=512, priority_beta_frames=10_000_000,
                        priority_beta_start=.4, diagnostic_interval=1, grad_clip_norm=10., target_update_period=1000,
                        expert_bc_decay_start_step=0, expert_bc_decay_steps=100, expert_bc_weight=.4,
                        expert_bc_min_weight=.4, expert_q_policy_decay_start_step=0,
                        expert_q_policy_decay_steps=100, expert_q_policy_weight=.25, expert_q_policy_min_weight=.25,
                        expert_q_margin_decay_start_step=0, expert_q_margin_decay_steps=100,
                        expert_q_margin_weight=.13, expert_q_margin_min_weight=.13)
                    metrics = SimpleNamespace(lock=threading.RLock(), frame_count=1000,
                        training_enabled=True, total_training_steps=0, q_ema_init=False, losses=[])
                    config_module = ModuleType('config')
                    config_module.RL_CONFIG, config_module.metrics = cfg, metrics
                    model_module = ModuleType('model')
                    model_module.device = torch.device('cpu')
                    replay_module = ModuleType('replay_buffer')
                    replay_module.ACTOR_DQN, replay_module.ACTOR_EPSILON, replay_module.ACTOR_EXPERT = 0, 1, 2
                    exposure_module = ModuleType('learning_exposure')
                    exposure_module.capture_amp_found_inf = lambda *a, **k: None
                    with patch.dict(sys.modules, dict(config=config_module, model=model_module,
                            replay_buffer=replay_module, learning_exposure=exposure_module, loss_kernel=loss)):
                        training = load_module('proposal_training', 'training.py')
                    online, target = copy.deepcopy(self.case.online), copy.deepcopy(self.case.target)
                    priorities_received = []
                    class Memory:
                        capacity = 100
                        def __len__(self): return 8
                        def update_priorities(self, indices, values, **kwargs):
                            priorities_received.append(np.array(values, copy=True))
                    kernel = loss.TrainingLoss(online, target, cfg, return_priorities=True)
                    expected = kernel(*self.case.args(self.expert), self.schedules)
                    optimizer = torch.optim.Adam(online.parameters(), lr=.0001)
                    agent = SimpleNamespace(memory=Memory(), training_enabled=True, use_amp=False,
                        online_net=online, target_net=target, optimizer=optimizer, grad_scaler=None,
                        training_steps=0, optimized_samples=0, _update_lr=lambda:None,
                        compiled_training_loss_diagnostics=kernel if kernel_active else None,
                        compiled_training_outputs=None, compiled_online_joint_dist=None,
                        compiled_online_q_joint=None, compiled_target_joint_dist=None,
                        _sync_inference=lambda **kwargs:None)
                    args = self.case.args(self.expert)
                    batch = tuple(value.numpy() for value in args[:6]) + (
                        self.expert.numpy(), np.where(self.expert.numpy(),2,0).astype(np.uint8),
                        np.arange(8), args[7].numpy())
                    actual_loss = training.train_step(agent, prefetched_batch=batch)
                    self.assertAlmostEqual(actual_loss, float(expected[0].detach()), places=6)
                    np.testing.assert_allclose(priorities_received[0], expected[4].numpy(), rtol=2e-6, atol=2e-7)
                    self.assertAlmostEqual(metrics.slice_td_ring, float(expected[1].mean().detach()), places=6)
                    self.assertAlmostEqual(metrics.last_priority_mean, float(expected[4].mean()), places=6)
                    self.assertAlmostEqual(metrics.c51_target_entropy, float(expected[3][9]), places=6)
                    self.assertEqual(agent.optimized_samples, 8)
                    self.assertEqual(agent.training_steps, 1)


if __name__ == '__main__':
    unittest.main()
