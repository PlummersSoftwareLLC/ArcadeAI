"""UNEXECUTED source proposal: whole copied training implementation on CPU.

Requires explicit released-window permission and a fresh CUDA-hidden process.
Real CPU replay/prefetch/loss/Adam/GradScaler are used. The CUDA-branch test has
explicit CPU device/autocast/found-inf adapters: it cannot qualify CUDA AMP.
No AST extraction, actual Rainbow/agent constructor, checkpoint or live data.
"""
import copy
from contextlib import ExitStack, nullcontext
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock


HERE = Path(__file__).parent
SEALED = HERE.parent / "executed_trace_proposal"
GAME = HERE.parents[2]
MANIFEST_SHA256 = "d7fcb2e36a7b08d472341d8f7f294d384f2591f17225832da83d350bff4e3316"
FIXTURE_SHA256 = "10872d08f11556bff08031b0265fc488347be717e5e2a91ff84fcf461ce298e8"
BATCH, WIDTH, SEED = 4096, 8, 20261017


def checked(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("Pinned source drift: " + str(path))
    return data


def load_file(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


class CPUCudaBranchAdapter:
    """Only for full-step control flow; does not advertise real CUDA coverage.

    PreparedBatch already owns CPU tensors. The source's explicit device
    factories and autocast are redirected; all math/Adam/scaler stay real CPU.
    Diagnostic CUDA events are prohibited rather than replaced with fake times.
    """
    def __init__(self, torch):
        self.original = torch

    def __getattr__(self, name):
        if name == "autocast":
            return lambda **kwargs: nullcontext()
        value = getattr(self.original, name)
        if name not in ("arange", "tensor", "linspace", "zeros"):
            return value
        def cpu_factory(*args, **kwargs):
            if "device" in kwargs:
                if self.original.device(kwargs["device"]).type != "cuda":
                    raise AssertionError("Unexpected adapted device factory")
                kwargs["device"] = "cpu"
            return value(*args, **kwargs)
        return cpu_factory


class WholeTrainStepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("ROBOTRON_ALLOW_WHOLE_STEP_CPU") != "1" or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
            raise RuntimeError("Explicit CPU suite permission and CUDA_VISIBLE_DEVICES='' required")
        if "torch" in sys.modules or "numpy" in sys.modules:
            raise RuntimeError("Fresh interpreter required")
        cls.temp = tempfile.TemporaryDirectory(prefix="robotron-whole-ce-step-")
        cls.work = Path(cls.temp.name)
        manifest = json.loads(checked(SEALED / "manifest.json", MANIFEST_SHA256))
        cls.manifest = manifest
        fixture_path = HERE.parent / "sampler_fixture.py"
        checked(fixture_path, FIXTURE_SHA256)
        cls.fixture = load_file("whole_step_sampler_fixture", fixture_path)
        cls.fixture.load_private_sources(cls.work)
        package = "kl_fixture_candidate"
        cls.package_dir = cls.work / "packages" / package
        for filename in ("replay_buffer.py", "prefetch.py", "loss_kernel.py", "executed_ce_trace.py", "training.py"):
            data = checked(SEALED / filename, manifest["overlay_sha256"][filename])
            (cls.package_dir / ("whole_" + filename)).write_bytes(data)
        for filename, expected in (("training", manifest["base_sha256"]["Robotron/Scripts/dqn/training.py"]),
                                   ("loss_kernel", "de9621e3d926a8f49f230f9e271c645a7498d38445622d6ae2761ab2bbd7253a")):
            data = checked(GAME / "Scripts/dqn" / (filename + ".py"), expected)
            (cls.package_dir / ("base_" + filename + ".py")).write_bytes(data)
        import torch
        cls.torch, cls.np = torch, sys.modules["numpy"]
        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)
        stub_path = cls.package_dir / "model_dependency_stub.py"
        stub_path.write_text("# CPU test-owned dependency: training imports only device.\n")
        model_stub = ModuleType(package + ".model")
        model_stub.__file__ = str(stub_path)
        model_stub.device = torch.device("cpu")
        sys.modules[package + ".model"] = model_stub
        cls.replay = importlib.import_module(package + ".whole_replay_buffer")
        # Only ACTOR constants are imported by full training; both numerical
        # paths subsequently use the same actual replay overlay object.
        sys.modules[package + ".replay_buffer"] = cls.replay
        cls.prefetch = importlib.import_module(package + ".whole_prefetch")
        cls.loss = importlib.import_module(package + ".whole_loss_kernel")
        cls.base_loss = importlib.import_module(package + ".base_loss_kernel")
        cls.observer = importlib.import_module(package + ".whole_executed_ce_trace")
        cls.training = importlib.import_module(package + ".whole_training")
        cls.base_training = importlib.import_module(package + ".base_training")
        cls.config = sys.modules[package + ".config"]
        cls.exposure_module = sys.modules[package + ".learning_exposure"]
        for name, module in list(sys.modules.items()):
            if name.startswith(package + "."):
                if not Path(module.__file__).resolve().is_relative_to(cls.package_dir.resolve()):
                    raise RuntimeError("Escaped copied package: " + name)
        if torch.cuda.is_initialized() or torch.cuda.device_count() != 0:
            raise RuntimeError("CUDA must remain hidden and uninitialized")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(prefix="case-", dir=self.work))
        self.cfg = self.config.RL_CONFIG
        # Explicit miniature-network/synthetic-fixture overrides only. The
        # complete training body, replay draw and trace fixed4096/51 stay real.
        for key, value in dict(batch_size=BATCH, min_replay_to_train=BATCH,
                num_atoms=51, num_fire_actions=2, gamma=.995, v_min=-10., v_max=50.,
                max_samples_per_frame=0., diagnostic_interval=2, replay_prefetch_slots=2,
                target_update_period=1, baseline_batch_size=512, c51_target_smoothing=0.,
                expert_bc_weight=.2, expert_bc_min_weight=.2, expert_bc_decay_start_step=100000,
                expert_q_policy_weight=.1, expert_q_policy_min_weight=.1,
                expert_q_margin_weight=.3, expert_q_margin_min_weight=.3).items():
            setattr(self.cfg, key, value)
        self.torch.manual_seed(SEED)
        self.np.random.seed(SEED)
        self._serial = 0

    def metrics_for(self, module):
        metrics = self.config.MetricsData()
        metrics.training_enabled = True
        metrics.frame_count = metrics.learner_frame_count = 1000000
        module.metrics = metrics
        return metrics

    def build(self, module=None, *, trace=True, kernel=False):
        torch, cfg = self.torch, self.cfg
        module = module or self.training
        metrics = self.metrics_for(module)
        memory = self.fixture.make_buffer(self.replay)
        memory.actions[:] %= 4
        memory.hof_actions[:] %= 4
        memory.ephof_actions[:] %= 4
        torch.manual_seed(SEED)
        class TinyModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.register_buffer("support", torch.linspace(-10., 50., 51))
                self.joint = torch.nn.Linear(WIDTH, 4 * 51)
                self.bc_joint_head = torch.nn.Linear(WIDTH, 4)
                self.bc_move_head = torch.nn.Linear(WIDTH, 2)
                self.bc_fire_head = torch.nn.Linear(WIDTH, 2)
                self.training_calls = self.next_calls = self.dist_calls = 0
            def joint_dist(self, states, log=False):
                self.dist_calls += 1
                logits = self.joint(states).reshape(-1, 4, 51)
                return logits.log_softmax(-1) if log else logits.softmax(-1)
            def q_values_joint(self, states):
                self.next_calls += 1
                return (self.joint_dist(states) * self.support).sum(-1)
            def training_outputs(self, states):
                self.training_calls += 1
                return (self.joint_dist(states, log=True), self.bc_joint_head(states),
                        self.bc_move_head(states), self.bc_fire_head(states))
        agent = SimpleNamespace(online_net=TinyModel(), memory=memory, training_enabled=True,
            training_steps=0, optimized_samples=0, last_target_update_samples=0, last_inference_sync=0,
            baseline_batch_size=512, loaded_training_steps=0, use_amp=False, grad_scaler=None,
            compiled_online_joint_dist=None, compiled_online_q_joint=None, compiled_target_joint_dist=None,
            compiled_training_outputs=None, compiled_training_loss=None, compiled_training_loss_diagnostics=None,
            _learning_optimizer_exposure=self.exposure_module.OptimizerExposure(),
            _training_lock=threading.RLock(), _executed_ce_trace=None,
            target_calls=0, inference_calls=0, priorities=[])
        agent.target_net = copy.deepcopy(agent.online_net)
        agent.infer_net = copy.deepcopy(agent.online_net)
        agent.optimizer = torch.optim.Adam(agent.online_net.parameters(), lr=2.5e-5, eps=1.5e-4)
        def update_lr():
            for group in agent.optimizer.param_groups:
                group["lr"] = 2.5e-5
        def update_target():
            agent.target_calls += 1
            agent.target_net.load_state_dict(agent.online_net.state_dict())
            agent.last_target_update_samples = agent.optimized_samples
        def sync_inference(force=False):
            if force:
                raise AssertionError("Unexpected forced sync")
            agent.inference_calls += 1
            agent.infer_net.load_state_dict(agent.online_net.state_dict())
            agent.last_inference_sync = agent.training_steps
        agent._update_lr, agent.update_target, agent._sync_inference = update_lr, update_target, sync_inference
        original_update = memory.update_priorities
        def priorities(indices, errors, **kwargs):
            agent.priorities.append((self.np.array(indices, copy=True), self.np.array(errors, copy=True)))
            return original_update(indices, errors, **kwargs)
        memory.update_priorities = priorities
        if trace:
            self._serial += 1
            agent._executed_ce_trace = self.observer.ExecutedCETrace(
                self.case / ("ce-executed-trace-%d" % self._serial), cfg,
                optimizer_exposure=agent._learning_optimizer_exposure,
                runtime={"scope": "whole private CPU training implementation; tiny network/state8",
                         "production_cuda_amp": "NOT_VALIDATED"})
        if kernel:
            loss_module = self.base_loss if module is self.base_training else self.loss
            kwargs = {} if module is self.base_training else {"trace_rows": trace}
            agent.compiled_training_loss = loss_module.TrainingLoss(agent.online_net, agent.target_net, cfg, False, **kwargs)
            agent.compiled_training_loss_diagnostics = loss_module.TrainingLoss(agent.online_net, agent.target_net, cfg, True, **kwargs)
        return agent, metrics

    def assert_tree_equal(self, left, right):
        if isinstance(left, self.torch.Tensor):
            self.assertTrue(self.torch.equal(left, right))
        elif isinstance(left, self.np.ndarray):
            self.np.testing.assert_array_equal(left, right)
        elif isinstance(left, dict):
            self.assertEqual(set(left), set(right))
            for key in left:
                self.assert_tree_equal(left[key], right[key])
        elif isinstance(left, (list, tuple)):
            self.assertEqual(len(left), len(right))
            for a, b in zip(left, right):
                self.assert_tree_equal(a, b)
        else:
            self.assertEqual(left, right)

    def snapshot(self, agent):
        return copy.deepcopy(dict(online=agent.online_net.state_dict(), target=agent.target_net.state_dict(),
            infer=agent.infer_net.state_dict(), adam=agent.optimizer.state_dict(),
            steps=agent.training_steps, samples=agent.optimized_samples,
            last_target=agent.last_target_update_samples, last_infer=agent.last_inference_sync))

    def assert_progress(self, before, agent):
        after = self.snapshot(agent)
        self.assertTrue(any(not self.torch.equal(before["online"][key], after["online"][key])
                            for key in before["online"]))
        self.assertTrue(after["adam"]["state"])
        for slot in after["adam"]["state"].values():
            self.assertGreater(float(slot["step"]), 0.)
        return after

    def test_full_impl_base_candidate_off_on_same_ce_adam_clocks_priorities_rng(self):
        for kernel in (False, True):
            with self.subTest(kernel=kernel):
                agents, results, rngs, metrics_list = [], [], [], []
                for module, enabled in ((self.base_training, False), (self.training, False), (self.training, True)):
                    agent, metrics = self.build(module, trace=enabled, kernel=kernel)
                    before = self.snapshot(agent)
                    self.np.random.seed(SEED)
                    results.append(module.train_step(agent))
                    rngs.append(self.np.random.get_state())
                    agents.append(agent)
                    metrics_list.append(metrics)
                    self.assert_progress(before, agent)
                    self.assertEqual(agent.online_net.training_calls, 1)
                    self.assertEqual(agent.target_calls, 1)
                    self.assertEqual(agent.inference_calls, 1)
                    self.assertEqual(agent._learning_optimizer_exposure.snapshot()["total"]["applied"], 1)
                self.assertEqual(results, [results[0]] * 3)
                for agent in agents[1:]:
                    self.assert_tree_equal(self.snapshot(agents[0]), self.snapshot(agent))
                    self.assert_tree_equal(agents[0].priorities, agent.priorities)
                for rng in rngs[1:]:
                    self.np.testing.assert_array_equal(rngs[0][1], rng[1])
                    self.assertEqual(rngs[0][2:], rng[2:])
                for metrics in metrics_list[1:]:
                    for key in ("total_training_steps", "total_optimized_samples", "last_loss", "last_grad_norm",
                                "last_bc_loss", "last_priority_mean", "c51_target_entropy", "c51_categorical_kl"):
                        self.assertEqual(getattr(metrics_list[0], key), getattr(metrics, key))
                row = agents[-1]._executed_ce_trace.rows[0]
                self.assertEqual(row["optimizer_outcome"], "applied_admission")
                self.assertTrue(row["numerical_capture_complete"])
                arrays = row["arrays"]
                # NumPy/Torch reduction order need not be bit-identical; the
                # actual returned loss/weights/Adam control parity above is.
                self.np.testing.assert_allclose(arrays["ce"],
                    -(arrays["projected_target"] * arrays["taken_action_log_probabilities"]).sum(1),
                    rtol=2e-6, atol=1e-6)

    def cpu_amp_branch(self, agent):
        """Real CPU scaler + injected CUDA-adapter identity, never CUDA proof."""
        stack = ExitStack()
        agent.use_amp = True
        agent.training_steps = 1  # no CUDA event route in this CPU-only adapter
        self.cfg.diagnostic_interval = 1000
        agent.grad_scaler = self.torch.amp.GradScaler("cpu", init_scale=65536., enabled=True)
        if not agent.grad_scaler.is_enabled():
            raise RuntimeError("Actual CPU GradScaler unavailable; do not silently substitute")
        def cpu_found_inf(scaler, optimizer, device, **kwargs):
            self.assertIs(scaler, agent.grad_scaler)
            self.assertIs(optimizer, agent.optimizer)
            state = scaler._per_optimizer_states[id(optimizer)]
            self.assertEqual(state["stage"].name, "UNSCALED")
            found = list(state["found_inf_per_device"].values())
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].device.type, "cpu")
            # Production exposure's enum is deliberately injected at this
            # boundary; this does NOT validate capture_amp_found_inf(CUDA).
            return found[0], "single_cuda_found_inf"
        stack.enter_context(mock.patch.object(self.training, "device", self.torch.device("cuda")))
        stack.enter_context(mock.patch.object(self.training, "torch", CPUCudaBranchAdapter(self.torch)))
        stack.enter_context(mock.patch.object(self.training, "capture_amp_found_inf", side_effect=cpu_found_inf))
        return stack

    def producer(self, agent):
        return self.prefetch.ReplayPrefetcher(agent.memory, BATCH, lambda: 1., "cpu", depth=2,
            min_replay_size=BATCH, direct_state_fill=True, trace_observer=agent._executed_ce_trace)

    def test_full_impl_real_cpu_scaler_skip_transfer_forward_errors_first8_no_ninth(self):
        agent, _ = self.build(kernel=True)
        trace = agent._executed_ce_trace
        producer = self.producer(agent)
        skip_before = skip_after = None
        try:
            with self.cpu_amp_branch(agent):
                for ordinal in range(1, 10):
                    batch = producer.get(timeout=5.)
                    self.assertIsNotNone(batch)
                    with ExitStack() as hooks:
                        if ordinal == 2:
                            skip_before = self.snapshot(agent)
                            scale_before = agent.grad_scaler.get_scale()
                            handle = next(agent.online_net.parameters()).register_hook(
                                lambda gradient: gradient * float("inf"))
                            hooks.callback(handle.remove)
                        failure = RuntimeError("whole-step injected failure-%d" % ordinal)
                        if ordinal == 3:
                            hooks.enter_context(mock.patch.object(agent.online_net, "training_outputs", side_effect=failure))
                        if ordinal == 4:
                            hooks.enter_context(mock.patch.object(batch, "wait_on_current_stream", side_effect=failure))
                        if ordinal in (3, 4):
                            with self.assertRaises(RuntimeError) as caught:
                                self.training.train_step(agent, batch)
                            self.assertIs(caught.exception, failure)
                        else:
                            self.assertIsNotNone(self.training.train_step(agent, batch))
                        if ordinal == 2:
                            skip_after = self.snapshot(agent)
                            self.assert_tree_equal(skip_before["online"], skip_after["online"])
                            self.assert_tree_equal(skip_before["adam"], skip_after["adam"])
                            self.assertEqual(agent.grad_scaler.get_scale(), scale_before / 2.)
                        self.assertTrue(batch._released)
                        self.assertEqual(trace.consumed, min(ordinal, 8))
            self.assertEqual([row["index"] for row in trace.rows], list(range(1, 9)))
            self.assertEqual(trace.rows[1]["optimizer_outcome"], "amp_skipped")
            self.assertEqual(trace.rows[1]["optimizer_observation"]["found_inf"], 1.)
            self.assertEqual([trace.rows[index]["status"] for index in (2, 3)], ["learner_exception"] * 2)
            self.assertFalse((trace.directory / "attempt-09.json").exists())
            self.assertFalse(json.loads((trace.directory / "status.json").read_text())["numerical_captures_complete"])
            total = agent._learning_optimizer_exposure.snapshot()["total"]
            self.assertEqual((total["applied"], total["amp_skipped"], total["unavailable"]), (6, 1, 0))
            self.assertEqual(agent.training_steps, 8)  #6applied+1skip+initial1, errors add0
            self.assertEqual(len(agent.priorities), 7)  # skip still updates CE priorities
        finally:
            self.assertTrue(producer.close(timeout=5.))
            self.assertFalse(producer._thread.is_alive())
        self.assertFalse(self.torch.cuda.is_initialized())

    def test_guard_rejected_real_prefetch_lease_is_released_without_consumption(self):
        agent, metrics = self.build()
        producer = self.producer(agent)
        try:
            batch = producer.get(timeout=5.)
            self.assertIsNotNone(batch)
            metrics.training_enabled = False
            self.assertIsNone(self.training.train_step(agent, batch))
            self.assertTrue(batch._released)
            self.assertEqual(agent._executed_ce_trace.consumed, 0)
            self.assertFalse(agent.optimizer.state)
        finally:
            self.assertTrue(producer.close(timeout=5.))

    def test_optimizer_error_retains_original_exception_and_unavailable_outcome(self):
        agent, _ = self.build(kernel=True)
        original = RuntimeError("real optimizer call rejected")
        before = self.snapshot(agent)
        with mock.patch.object(agent.optimizer, "step", side_effect=original):
            with self.assertRaises(RuntimeError) as caught:
                self.training.train_step(agent)
        self.assertIs(caught.exception, original)
        self.assert_tree_equal(before, self.snapshot(agent))
        row = agent._executed_ce_trace.rows[0]
        self.assertEqual(row["status"], "learner_exception")
        self.assertEqual(row["actual_exposure_delta"]["unavailable"], 1)
        self.assertFalse(row["numerical_capture_complete"])

    def test_late_priority_error_keeps_actual_admission_and_real_adam_progress(self):
        agent, _ = self.build(kernel=True)
        before = self.snapshot(agent)
        original = OSError("private priority failure after Adam")
        with mock.patch.object(agent.memory, "update_priorities", side_effect=original):
            with self.assertRaises(OSError) as caught:
                self.training.train_step(agent)
        self.assertIs(caught.exception, original)
        self.assert_progress(before, agent)
        self.assertEqual(agent.training_steps, before["steps"])
        row = agent._executed_ce_trace.rows[0]
        self.assertEqual(row["optimizer_outcome"], "applied_admission")
        self.assertTrue(row["outcome_available"])
        self.assertFalse(row["numerical_capture_complete"])

    def test_observer_entry_and_disk_faults_do_not_disable_kernel_or_optimizer(self):
        for where in ("loss", "_persist_row"):
            with self.subTest(where=where):
                agent, _ = self.build(kernel=True)
                kernel = agent.compiled_training_loss_diagnostics
                before = self.snapshot(agent)
                with mock.patch.object(agent._executed_ce_trace, where, side_effect=OSError("observer-only")):
                    self.assertIsNotNone(self.training.train_step(agent))
                self.assert_progress(before, agent)
                self.assertIs(agent.compiled_training_loss_diagnostics, kernel)
                self.assertEqual(agent.training_steps, 1)
                self.assertTrue(agent._executed_ce_trace.errors)
                self.assertFalse(agent._executed_ce_trace.rows[0]["numerical_capture_complete"])

    def test_nonfinite_loss_consumes_ordinal_without_adam_or_admission(self):
        agent, _ = self.build(kernel=True)
        before = self.snapshot(agent)
        original = agent.compiled_training_loss_diagnostics
        def nonfinite(*args):
            result = original(*args)
            return (result[0] * float("nan"), *result[1:])
        agent.compiled_training_loss_diagnostics = nonfinite
        self.assertIsNone(self.training.train_step(agent))
        self.assert_tree_equal(before, self.snapshot(agent))
        trace = agent._executed_ce_trace
        self.assertEqual(trace.consumed, 1)
        self.assertEqual(trace.rows[0]["status"], "returned_none")
        self.assertEqual(trace.rows[0]["actual_exposure_delta"]["attempts_started"], 0)
        self.assertFalse(trace.rows[0]["numerical_capture_complete"])

    def test_unsupported_outcome_is_unavailable_even_if_real_cpu_adam_applied(self):
        agent, _ = self.build(kernel=True)
        before = self.snapshot(agent)
        producer = self.producer(agent)
        try:
            with self.cpu_amp_branch(agent), mock.patch.object(self.training, "capture_amp_found_inf",
                    return_value=(None, "unsupported_cpu_test_boundary")):
                batch = producer.get(timeout=5.)
                self.assertIsNotNone(batch)
                self.assertIsNotNone(self.training.train_step(agent, batch))
                self.assertTrue(batch._released)
            self.assert_progress(before, agent)
            row = agent._executed_ce_trace.rows[0]
            self.assertEqual(row["optimizer_outcome"], "unavailable")
            self.assertEqual(row["actual_exposure_delta"]["unavailable"], 1)
            self.assertFalse(row["numerical_capture_complete"])
        finally:
            self.assertTrue(producer.close(timeout=5.))
            self.assertFalse(producer._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
