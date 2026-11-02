"""UNEXECUTED proposal: tiny CPU whole-step/packing and static-source contracts.

No production replay, constructor, CUDA compiler/fused optimizer or learning
claim. Future execution requires a fresh explicitly CUDA-hidden root-owned unit.
The AMP route uses a real CPU GradScaler with explicit device/event adapters.
"""
import ast
from collections import deque
from contextlib import ExitStack, nullcontext
import copy
import hashlib
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
BATCH, WIDTH = 8, 4


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PriorityRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("ROBOTRON_ALLOW_PRIORITY_CPU") != "1" or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
            raise RuntimeError("Explicit CPU permission and CUDAhidden fresh process required")
        if "torch" in sys.modules or "numpy" in sys.modules:
            raise RuntimeError("Fresh interpreter required")
        import torch
        import numpy as np
        cls.torch, cls.np = torch, np
        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)
        cls.package = "priority_route_test_owned"
        package = ModuleType(cls.package)
        package.__path__ = [str(HERE)]
        sys.modules[cls.package] = package
        cls.cfg = SimpleNamespace(batch_size=BATCH, min_replay_to_train=BATCH, max_samples_per_frame=0.,
            priority_beta_frames=10000000, priority_beta_start=.4, diagnostic_interval=2,
            num_fire_actions=2, num_atoms=51, gamma=.995, v_min=-10., v_max=50.,
            c51_target_smoothing=0., branch_aux_bc_weight=.25, expert_bc_effective_floor=.01,
            expert_q_policy_temperature=10., expert_q_margin=.5, grad_clip_norm=10.,
            expert_bc_weight=.2, expert_bc_min_weight=.2, expert_bc_decay_start_step=100000,
            expert_bc_decay_steps=10000, expert_q_policy_weight=.1, expert_q_policy_min_weight=.1,
            expert_q_margin_weight=.3, expert_q_margin_min_weight=.3,
            baseline_batch_size=512, target_update_period=1000, per_priority_metric="ce")
        config = ModuleType(cls.package + ".config")
        config.RL_CONFIG, config.metrics = cls.cfg, None
        sys.modules[config.__name__] = config
        model = ModuleType(cls.package + ".model")
        model.device = torch.device("cpu")
        sys.modules[model.__name__] = model
        replay = ModuleType(cls.package + ".replay_buffer")
        replay.ACTOR_DQN, replay.ACTOR_EPSILON, replay.ACTOR_EXPERT = 0, 1, 2
        sys.modules[replay.__name__] = replay
        lock = json.loads((HERE / "source-lock.json").read_text())
        pin = lock["unchanged_dependencies"]["learning_exposure.py"]
        path = Path(pin["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
            raise RuntimeError("Pinned actual optimizer exposure changed")
        cls.exposure = load(cls.package + ".learning_exposure", path)
        cls.loss = load(cls.package + ".loss_kernel", HERE / "loss_kernel.py")
        cls.training = load(cls.package + ".training", HERE / "training.py")
        cls.base_loss = load(cls.package + ".original_loss", Path(lock["base_sources"]["loss_kernel.py"]["path"]))

    @classmethod
    def tearDownClass(cls):
        if cls.torch.cuda.is_initialized() or cls.torch.cuda.device_count()!=0:
            raise AssertionError("CPU suite must leave CUDA hidden and uninitialized")

    def setUp(self):
        self.cfg.per_priority_metric = "ce"
        self.torch.manual_seed(20261017)

    def build(self, metric, *, diagnostic=False, kernel=True):
        torch, np, cfg = self.torch, self.np, self.cfg
        cfg.per_priority_metric = metric
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.register_buffer("support", torch.linspace(-10., 50., 51))
                self.joint = torch.nn.Linear(WIDTH, 4*51)
                self.bc_joint_head = torch.nn.Linear(WIDTH, 4)
                self.bc_move_head = torch.nn.Linear(WIDTH, 2)
                self.bc_fire_head = torch.nn.Linear(WIDTH, 2)
                self.calls = 0
            def joint_dist(self, states, log=False):
                values = self.joint(states).reshape(-1,4,51)
                return values.log_softmax(-1) if log else values.softmax(-1)
            def q_values_joint(self, states):
                return (self.joint_dist(states)*self.support).sum(-1)
            def training_outputs(self, states):
                self.calls += 1
                return self.joint_dist(states,True), self.bc_joint_head(states), self.bc_move_head(states), self.bc_fire_head(states)
        agent = SimpleNamespace(online_net=Model(), training_enabled=True,
            training_steps=0 if diagnostic else 1, optimized_samples=0, last_target_update_samples=0,
            loaded_training_steps=0, loaded_optimized_samples=0, last_inference_sync=0,
            _priority_metric=metric, _loss_priority_metric=metric, _priority_phase=None,
            _recomputed_ce_capture=None, _training_lock=threading.RLock(), use_amp=False, grad_scaler=None,
            compiled_online_joint_dist=None, compiled_online_q_joint=None, compiled_target_joint_dist=None,
            compiled_training_outputs=None, compiled_training_loss=None, compiled_training_loss_diagnostics=None)
        agent.target_net=copy.deepcopy(agent.online_net)
        agent.optimizer=torch.optim.Adam(agent.online_net.parameters(),lr=2.5e-5,eps=1.5e-4)
        agent._update_lr=lambda:None
        agent.update_target=lambda:None
        agent._sync_inference=lambda force=False:None
        agent._learning_optimizer_exposure=self.exposure.OptimizerExposure()
        metrics=SimpleNamespace(lock=threading.RLock(),training_enabled=True,frame_count=1000000,
            learner_frame_count=1000000,loaded_frame_count=0,measurement_frame_count=0,
            loaded_measurement_frame_count=0,loaded_optimized_samples=0,total_training_steps=0,
            losses=deque(),q_ema_init=False)
        self.training.metrics=metrics
        arrays=(np.linspace(-.2,.2,BATCH*WIDTH,dtype=np.float32).reshape(BATCH,WIDTH),
            np.arange(BATCH,dtype=np.int64)%4,np.linspace(-.1,.3,BATCH,dtype=np.float32),
            np.full((BATCH,WIDTH),.1,dtype=np.float32),np.asarray([0,1]*4,dtype=np.float32),
            np.asarray([1,3]*4,dtype=np.float32),np.asarray([0,1]*4,dtype=np.bool_),
            np.asarray([0,2]*4,dtype=np.uint8),np.asarray([0,0,1,2,100,101,200,201],dtype=np.int64),
            np.asarray([.2,.3,.4,.5,.35,.35,.35,.35],dtype=np.float32))
        class Memory:
            capacity=100
            _ephof_base=200
            def __len__(self):return 100
            def sample(self,*args,**kwargs):return arrays
            def update_priorities(self,indices,values,**kwargs):
                self.updated=(np.array(indices,copy=True),np.array(values,copy=True))
        agent.memory=Memory()
        class Phase:
            def require_ready(self,selected):
                if selected!=metric:raise RuntimeError("metric drift")
            def note_update(self,*args):self.last=args
            def reject_diagnostics(self,values):self.rejected=list(values)
        if metric=="kl":agent._priority_phase=Phase()
        tensors=tuple(torch.from_numpy(arrays[index]) for index in (0,1,2,3,4,5,6,9))
        class Lease:
            batch=arrays
            sample_ms=transfer_ms=0.
            released=0
            def wait_on_current_stream(self):pass
            def release(self):self.released+=1
        lease=Lease();lease.tensors=tensors
        if kernel:
            agent.compiled_training_loss=self.loss.TrainingLoss(agent.online_net,agent.target_net,cfg,False,metric=="kl")
            agent.compiled_training_loss_diagnostics=self.loss.TrainingLoss(agent.online_net,agent.target_net,cfg,True,metric=="kl")
        return agent,lease,metrics

    def test_default_four_outputs_objective_and_gradients_equal_original_on_CPU(self):
        for diagnostic in (False,True):
            with self.subTest(diagnostic=diagnostic):
                agent,lease,_=self.build("ce",diagnostic=diagnostic)
                schedule=self.torch.tensor([.2,.1,.3])
                args=(*lease.tensors,schedule)
                original=self.base_loss.TrainingLoss(agent.online_net,agent.target_net,self.cfg,diagnostic)(*args)
                candidate=self.loss.TrainingLoss(agent.online_net,agent.target_net,self.cfg,diagnostic)(*args)
                self.assertEqual(len(candidate),4)
                for left,right in zip(original,candidate):self.assertTrue(self.torch.equal(left,right))
                parameters=tuple(agent.online_net.parameters())
                left=self.torch.autograd.grad(original[0],parameters,allow_unused=True)
                right=self.torch.autograd.grad(candidate[0],parameters,allow_unused=True)
                for a,b in zip(left,right):
                    self.assertEqual(a is None,b is None)
                    if a is not None:self.assertTrue(self.torch.equal(a,b))

    def test_KL_fifth_vector_does_not_change_CPU_objective_or_first12_diagnostics(self):
        agent,lease,_=self.build("kl",diagnostic=True)
        args=(*lease.tensors,self.torch.tensor([.2,.1,.3]))
        four=self.loss.TrainingLoss(agent.online_net,agent.target_net,self.cfg,True)(*args)
        five=self.loss.TrainingLoss(agent.online_net,agent.target_net,self.cfg,True,True)(*args)
        self.assertEqual(len(five),5);self.assertEqual(five[3].shape,(19,))
        for a,b in zip(four[:3],five[:3]):self.assertTrue(self.torch.equal(a,b))
        self.assertTrue(self.torch.equal(four[3],five[3][:12]))
        self.assertFalse(five[4].requires_grad)
        self.assertTrue(bool((five[4]>=0).all()))
        parameters=tuple(agent.online_net.parameters())
        a=self.torch.autograd.grad(four[0],parameters,allow_unused=True)
        b=self.torch.autograd.grad(five[0],parameters,allow_unused=True)
        for left,right in zip(a,b):
            self.assertEqual(left is None,right is None)
            if left is not None:self.assertTrue(self.torch.equal(left,right))

    def test_signed_negative_values_are_recorded_before_zero_clamp(self):
        m=self.torch.tensor([[.5,.5],[1.,0.]])
        ce=self.torch.tensor([0.,.25],requires_grad=True)
        values,stats=self.loss.categorical_kl_priorities(ce,m)
        self.assertEqual(values.tolist(),[0.,.25])
        self.assertLess(float(stats[0]),0.);self.assertEqual(float(stats[2]),1.)
        self.assertEqual(float(stats[5]),0.);self.assertFalse(stats.requires_grad)

    def test_whole_step_eager_and_kernel_reprioritize_KL_but_retain_CE_metrics(self):
        for kernel in (False,True):
            for diagnostic in (False,True):
                with self.subTest(kernel=kernel,diagnostic=diagnostic):
                    agent,lease,metrics=self.build("kl",kernel=kernel,diagnostic=diagnostic)
                    before=next(agent.online_net.parameters()).detach().clone()
                    self.assertIsNotNone(self.training.train_step(agent,lease))
                    self.assertEqual(lease.released,1)
                    self.assertEqual(agent.online_net.calls,1)
                    self.assertEqual(agent._priority_phase.last[:2],("kl",4))
                    self.assertEqual(len(agent._priority_phase.last[2]),7)
                    self.assertTrue(self.np.all(agent.memory.updated[1]>=0))
                    self.assertFalse(self.torch.equal(before,next(agent.online_net.parameters())))
                    self.assertTrue(agent.optimizer.state)
                    self.assertTrue(all(float(slot["step"])==1. for slot in agent.optimizer.state.values()))
                    self.assertEqual(agent._learning_optimizer_exposure.snapshot()["total"]["applied"],1)
                    self.assertAlmostEqual(metrics.last_priority_mean,float(agent.memory.updated[1].mean()))

    def amp_adapter(self,agent):
        torch=self.torch
        class Event:
            def record(self):pass
            def elapsed_time(self,other):return 0.
        class Proxy:
            def __getattr__(self,name):
                if name=="autocast":return lambda **kwargs:nullcontext()
                if name=="cuda":return SimpleNamespace(Event=lambda **kwargs:Event())
                original=getattr(torch,name)
                if name not in ("arange","tensor","linspace","zeros"):return original
                def factory(*args,**kwargs):
                    if "device" in kwargs:kwargs["device"]="cpu"
                    return original(*args,**kwargs)
                return factory
        agent.use_amp=True
        agent.grad_scaler=torch.amp.GradScaler("cpu",init_scale=65536.)
        if not agent.grad_scaler.is_enabled():raise RuntimeError("Real CPU scaler required")
        def found(scaler,optimizer,*args,**kwargs):
            values=list(scaler._per_optimizer_states[id(optimizer)]["found_inf_per_device"].values())
            self.assertEqual(len(values),1)
            return values[0],"single_cuda_found_inf"
        stack=ExitStack()
        stack.enter_context(mock.patch.object(self.training,"torch",Proxy()))
        stack.enter_context(mock.patch.object(self.training,"device",torch.device("cuda")))
        stack.enter_context(mock.patch.object(self.training,"capture_amp_found_inf",side_effect=found))
        return stack

    def test_whole_step_found_inf_offsets_in_both_ABIs_and_diagnostic_modes(self):
        for metric in ("ce","kl"):
            for diagnostic in (False,True):
                for skipped in (False,True):
                    with self.subTest(metric=metric,diagnostic=diagnostic,skipped=skipped):
                        agent,lease,_=self.build(metric,diagnostic=diagnostic)
                        before=next(agent.online_net.parameters()).detach().clone()
                        with self.amp_adapter(agent),ExitStack() as hooks:
                            if skipped:
                                handle=next(agent.online_net.parameters()).register_hook(lambda grad:grad*float("inf"))
                                hooks.callback(handle.remove)
                            self.assertIsNotNone(self.training.train_step(agent,lease))
                        totals=agent._learning_optimizer_exposure.snapshot()["total"]
                        self.assertEqual((totals["applied"],totals["amp_skipped"],totals["unavailable"]),
                                         (0,1,0) if skipped else (1,0,0))
                        self.assertEqual(self.torch.equal(before,next(agent.online_net.parameters())),skipped)
                        if skipped:self.assertEqual(len(agent.optimizer.state),0)
                        else:self.assertTrue(all(float(slot["step"])==1. for slot in agent.optimizer.state.values()))
                        self.assertTrue(hasattr(agent.memory,"updated"))
                        if metric=="kl":self.assertEqual(agent._priority_phase.last[0],"kl")

    def test_unknown_or_hot_metric_rejected_before_sample_and_lease_released(self):
        for changed in ("invalid","kl"):
            agent,lease,_=self.build("ce")
            self.cfg.per_priority_metric=changed
            with self.assertRaisesRegex(RuntimeError,"restart/rebuild"):
                self.training.train_step(agent,lease)
            self.assertEqual(agent.online_net.calls,0);self.assertEqual(lease.released,1)
            self.assertFalse(hasattr(agent.memory,"updated"))

    def test_nonfinite_KL_payload_fails_before_optimizer_and_is_not_reprioritized(self):
        agent,lease,_=self.build("kl")
        original=agent.compiled_training_loss
        def broken(*args):
            outputs=list(original(*args));outputs[4]=outputs[4]*float("nan");return tuple(outputs)
        agent.compiled_training_loss=broken
        with self.assertRaisesRegex(RuntimeError,"Invalid same-forward"):
            self.training.train_step(agent,lease)
        self.assertEqual(agent._learning_optimizer_exposure.snapshot()["total"]["attempts_started"],0)
        self.assertEqual(lease.released,1);self.assertFalse(hasattr(agent.memory,"updated"))

    def test_material_signed_or_mass_failure_retains_raw_stats_and_stops_before_optimizer(self):
        for stat,value in ((0,-2e-5),(5,2e-5)):
            with self.subTest(stat=stat):
                agent,lease,_=self.build("kl")
                original=agent.compiled_training_loss
                def invalid(*args):
                    outputs=list(original(*args));outputs[3]=outputs[3].clone()
                    outputs[3][12+stat]=value
                    return tuple(outputs)
                agent.compiled_training_loss=invalid
                with self.assertRaisesRegex(RuntimeError,"signed-or-mass"):
                    self.training.train_step(agent,lease)
                self.assertAlmostEqual(agent._priority_phase.rejected[stat],value)
                self.assertEqual(agent._learning_optimizer_exposure.snapshot()["total"]["attempts_started"],0)
                self.assertFalse(hasattr(agent.memory,"updated"));self.assertEqual(lease.released,1)

    def test_original_optimizer_exception_identity_outcome_and_release_are_retained(self):
        for metric in ("ce","kl"):
            with self.subTest(metric=metric):
                agent,lease,_=self.build(metric)
                failure=RuntimeError("original optimizer failure")
                with mock.patch.object(agent.optimizer,"step",side_effect=failure):
                    with self.assertRaises(RuntimeError) as caught:self.training.train_step(agent,lease)
                self.assertIs(caught.exception,failure)
                totals=agent._learning_optimizer_exposure.snapshot()["total"]
                self.assertEqual((totals["applied"],totals["amp_skipped"],totals["unavailable"]),(0,0,1))
                self.assertEqual(lease.released,1);self.assertFalse(hasattr(agent.memory,"updated"))


class StaticDefaultContracts(unittest.TestCase):
    def test_CE_packed_expression_and_four_unpack_remain_present(self):
        source=(HERE/"training.py").read_text()
        self.assertIn('packed = torch.cat((ce_loss.detach().float(), torch.stack(scalars)))',source)
        self.assertIn('weighted_loss, ce_loss, bc_loss, kernel_diag = kernel(',source)
        self.assertIn('outcome_host_index = 2 * B + len(scalars)',source)
        self.assertIn('priority_diagnostic_offset = 2 * B + len(scalars)',source)

    def test_priority_flag_is_static_False_and_optimizer_body_is_unchanged(self):
        lock=json.loads((HERE/"source-lock.json").read_text())
        original=Path(lock["base_sources"]["training.py"]["path"]).read_text()
        candidate=(HERE/"training.py").read_text()
        start='    # ── Optimise';end='    if gpu_timing is not None:'
        self.assertEqual(original[original.index(start):original.index(end,original.index(start))],
                         candidate[candidate.index(start):candidate.index(end,candidate.index(start))])
        self.assertIn('return_priorities=False',(HERE/"loss_kernel.py").read_text())


if __name__=="__main__":
    unittest.main()
