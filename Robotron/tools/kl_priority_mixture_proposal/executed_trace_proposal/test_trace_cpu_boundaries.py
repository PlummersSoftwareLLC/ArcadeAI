"""UNEXECUTED real CPU replay/prefetch/kernel boundaries; never real AMP proof.

Requires a fresh CUDA-hidden interpreter and explicit post-quality permission.
Actual pinned source modules are copied before import. State width8/small CPU
networks cannot qualify production Rainbow4096 CUDA/AMP or optimizer execution.
"""
import copy
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).parent


class TraceCPUBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if "torch" in sys.modules or "numpy" in sys.modules:
            raise RuntimeError("Run this CPU suite separately in a fresh interpreter")
        cls.temp = tempfile.TemporaryDirectory(prefix="robotron-ce-trace-cpu-")
        cls.work = Path(cls.temp.name)
        specification = importlib.util.spec_from_file_location("sampler_fixture", HERE.parent / "sampler_fixture.py")
        cls.fixture = importlib.util.module_from_spec(specification)
        sys.modules[specification.name] = cls.fixture
        specification.loader.exec_module(cls.fixture)
        cls.base, cls.sealed = cls.fixture.load_private_sources(cls.work)
        cls.manifest = json.loads((HERE / "manifest.json").read_text())
        package_dir = cls.work / "packages/kl_fixture_candidate"
        for filename in ("replay_buffer.py", "prefetch.py", "loss_kernel.py", "executed_ce_trace.py"):
            data=(HERE / filename).read_bytes()
            if hashlib.sha256(data).hexdigest() != cls.manifest["overlay_sha256"][filename]:
                raise RuntimeError("Overlay source drift: " + filename)
            (package_dir / ("trace_"+filename)).write_bytes(data)
        cls.replay = importlib.import_module("kl_fixture_candidate.trace_replay_buffer")
        cls.prefetch = importlib.import_module("kl_fixture_candidate.trace_prefetch")
        cls.loss = importlib.import_module("kl_fixture_candidate.trace_loss_kernel")
        cls.trace_module = importlib.import_module("kl_fixture_candidate.trace_executed_ce_trace")
        cls.torch, cls.np = sys.modules["torch"], sys.modules["numpy"]
        cls.torch.set_num_threads(2)
        cls.torch.set_num_interop_threads(2)
        base_loss = cls.work / "base_loss_kernel.py"
        production = HERE.parents[2] / "Scripts/dqn/loss_kernel.py"
        data=production.read_bytes()
        if hashlib.sha256(data).hexdigest() != "de9621e3d926a8f49f230f9e271c645a7498d38445622d6ae2761ab2bbd7253a":
            raise RuntimeError("Base loss source drift")
        base_loss.write_bytes(data)
        spec=importlib.util.spec_from_file_location("private_base_loss",base_loss)
        cls.base_loss=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.base_loss)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.config=sys.modules["kl_fixture_candidate.config"].RL_CONFIG
        self.config.batch_size=4096
        self.config.num_atoms=51
        self.config.replay_prefetch_slots=2
        self.exposure=sys.modules["kl_fixture_candidate.learning_exposure"].OptimizerExposure()

    def test_actual_sampler_metadata_failure_keeps_original_draw_bytes_and_rng(self):
        left=self.fixture.make_buffer(self.base)
        right=self.fixture.make_buffer(self.replay)
        self.np.random.seed(self.fixture.SEED)
        expected=left.sample(4096,beta=1.)
        expected_rng=self.np.random.get_state()
        self.np.random.seed(self.fixture.SEED)
        with mock.patch.object(right,"_record_draw_metadata_locked",side_effect=MemoryError("metadata")):
            actual,metadata=right.sample_with_metadata(4096,beta=1.,capture_id="fault")
        for a,b in zip(expected,actual): self.assertEqual(a.tobytes(),b.tobytes())
        self.np.testing.assert_array_equal(expected_rng[1],self.np.random.get_state()[1])
        self.assertEqual(expected_rng[2:],self.np.random.get_state()[2:])
        self.assertEqual(metadata["observer_error"],"MemoryError")

    def test_post_draw_small_field_failure_does_not_resample_or_change_batch(self):
        left=self.fixture.make_buffer(self.base)
        right=self.fixture.make_buffer(self.replay)
        self.np.random.seed(self.fixture.SEED)
        expected=left.sample(4096,beta=.7)
        expected_rng=self.np.random.get_state()
        original=right._draw_metadata_copy
        original_record=right._record_draw_metadata_locked
        record_finished=False
        def record(*args,**kwargs):
            nonlocal record_finished
            result=original_record(*args,**kwargs)
            record_finished=True
            return result
        # Selected-leaf copies succeed; only the post-sample action copy fails.
        def copy_field(value):
            if record_finished and getattr(value,"dtype",None)==self.np.dtype(self.np.int64) and len(value)==4096:
                raise MemoryError("post draw small fields")
            return original(value)
        self.np.random.seed(self.fixture.SEED)
        with mock.patch.object(right,"_record_draw_metadata_locked",side_effect=record), \
             mock.patch.object(right,"_draw_metadata_copy",side_effect=copy_field):
            actual,metadata=right.sample_with_metadata(4096,beta=.7,capture_id="small-fault")
        for a,b in zip(expected,actual): self.assertEqual(a.tobytes(),b.tobytes())
        self.np.testing.assert_array_equal(expected_rng[1],self.np.random.get_state()[1])
        self.assertEqual(expected_rng[2:],self.np.random.get_state()[2:])
        self.assertEqual(metadata["observer_error"],"MemoryError")

    def test_real_prefetch_lease_epoch_metadata_lifetime_and_discarded_batches(self):
        from types import SimpleNamespace
        memory=self.fixture.make_buffer(self.replay)
        trace=self.trace_module.ExecutedCETrace(self.work / "ce-executed-trace-prefetch",self.config,
            optimizer_exposure=self.exposure,runtime={"scope":"real CPU prefetch only"})
        producer=self.prefetch.ReplayPrefetcher(memory,4096,lambda:1.,"cpu",depth=2,
            min_replay_size=4096,trace_observer=trace,direct_state_fill=True)
        prepared=None
        try:
            prepared=producer.get(timeout=2.)
            self.assertIsNotNone(prepared)
            self.assertIsNotNone(prepared.draw_metadata)
            original_actions=prepared.draw_metadata["small_batch_fields"]["actions"].copy()
            agent=SimpleNamespace(training_steps=0,optimized_samples=0,
                optimizer=SimpleNamespace(param_groups=[{"lr":2.5e-5}]))
            trace.begin(agent,prepared.batch,prepared)
            row=trace.rows[0]
            self.assertEqual(row["prefetch"]["lease_epoch"],prepared._epoch)
            self.assertTrue(row["prefetch"]["is_current_at_consumption"])
            self.assertNotIn("_owner",row["prefetch"])
            prepared.release(); prepared=None
            with memory.lock: memory.actions[:]=80
            producer.invalidate(wait=True,timeout=2.)
            self.np.testing.assert_array_equal(row["draw"]["small_batch_fields"]["actions"],original_actions)
            self.assertEqual(trace.consumed,1)  # produced/discarded leases do not count
        finally:
            if prepared is not None: prepared.release()
            self.assertTrue(producer.close(timeout=2.))
        self.assertFalse(producer._thread.is_alive())

    def test_actual_loss_off4_on5_identical_objective_gradients_and_same_forward_payload(self):
        torch=self.torch
        from types import SimpleNamespace
        cfg=SimpleNamespace(num_fire_actions=2,num_atoms=51,v_min=-10.,v_max=50.,gamma=.99,
            c51_target_smoothing=0.,branch_aux_bc_weight=.25,expert_bc_effective_floor=.01,
            expert_q_policy_temperature=10.,expert_q_margin=.5)
        class CPUModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.register_buffer("support",torch.linspace(-10.,50.,51))
                self.joint=torch.nn.Linear(8,4*51)
                self.bc=torch.nn.Linear(8,4)
                self.move=torch.nn.Linear(8,2)
                self.fire=torch.nn.Linear(8,2)
                self.calls=0
            def training_outputs(self,states):
                self.calls+=1
                logits=self.joint(states).reshape(-1,4,51)
                return logits.log_softmax(-1),self.bc(states),self.move(states),self.fire(states)
            def joint_dist(self,states,log=False):
                logits=self.joint(states).reshape(-1,4,51)
                return logits.log_softmax(-1) if log else logits.softmax(-1)
            def q_values_joint(self,states):
                return (self.joint_dist(states)*self.support).sum(-1)
        for diagnostics in (False,True):
            for compile_cpu in (False,True):
                with self.subTest(diagnostics=diagnostics,compile_cpu=compile_cpu):
                    online=CPUModel(); target=CPUModel()
                    variants=[copy.deepcopy(online) for _ in range(3)]
                    kernels=[self.base_loss.TrainingLoss(variants[0],target,cfg,diagnostics),
                        self.loss.TrainingLoss(variants[1],target,cfg,diagnostics),
                        self.loss.TrainingLoss(variants[2],target,cfg,diagnostics,trace_rows=True)]
                    if compile_cpu:
                        kernels=[torch.compile(kernel,backend="eager",fullgraph=True) for kernel in kernels]
                    states=torch.arange(8*8,dtype=torch.float32).reshape(8,8)/64.
                    actions=torch.arange(8)%4
                    rewards=torch.tensor([-20.,-10.,0.,50.,80.,1.,-1.,2.])
                    dones=torch.tensor([1.,1.,1.,1.,1.,0.,0.,0.])
                    horizons=torch.tensor([1.,2.,3.,1.,2.,3.,2.,1.])
                    flags=torch.tensor([1,0,1,0,1,0,1,0],dtype=torch.bool)
                    weights=torch.linspace(.1,1.,8)
                    schedules=torch.tensor([.1,.2,.3])
                    args=(states,actions,rewards,-states,dones,horizons,flags,weights,schedules)
                    outputs=[kernel(*args) for kernel in kernels]
                    self.assertEqual([len(value) for value in outputs],[4,4,5])
                    for output in outputs[1:]:
                        for expected,actual in zip(outputs[0],output[:4]):
                            self.assertTrue(torch.equal(expected,actual))
                    for output in outputs: output[0].backward()
                    for parameters in zip(*(model.parameters() for model in variants)):
                        for actual in parameters[1:]:
                            self.assertTrue(torch.equal(parameters[0].grad,actual.grad))
                    payload=outputs[2][4]
                    self.assertEqual(len(payload),10)
                    self.assertTrue(all(not value.requires_grad for value in payload))
                    self.assertTrue(torch.equal(outputs[2][1],-(payload[0]*payload[1]).sum(1)))
                    self.assertEqual(variants[2].calls,1)  # no second training forward
        self.assertFalse(torch.cuda.is_initialized())
        self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"],"")

    def test_actual_cpu_tensor_archive_is_detached_with_injected_counter_outcome_only(self):
        from types import SimpleNamespace
        torch=self.torch
        memory=self.fixture.make_buffer(self.replay)
        raw,metadata=memory.sample_with_metadata(4096,beta=1.,capture_id="private-archive-contract")
        batch=self.trace_module.ObservedReplayBatch(raw,metadata)
        trace=self.trace_module.ExecutedCETrace(self.work / "ce-executed-trace-archive",self.config,
            optimizer_exposure=self.exposure,
            runtime={"scope":"synthetic CPU tensor I/O; injected counters; no optimizer or model"})
        agent=SimpleNamespace(training_steps=0,optimized_samples=0,
            optimizer=SimpleNamespace(param_groups=[{"lr":2.5e-5}]))
        target=torch.full((4096,51),1./51.)
        logp=torch.full((4096,51),-float(self.np.log(51.)))
        ce=-(target*logp).sum(1)
        vector=torch.zeros(4096)
        scalar=torch.tensor(0.)
        payload=(target,logp,vector,vector,vector,target,
                 torch.linspace(-10.,50.,51).expand(4096,51),scalar,scalar,scalar)
        trace.begin(agent,batch,None)
        trace.loss(agent,ce,payload,weighted_loss=ce.mean(),bc_loss=scalar,
                   schedule=(0.,0.,0.),backend="synthetic CPU I/O contract")
        expected=target.numpy().copy()
        target.zero_()  # captured arrays must no longer alias source tensors
        ticket=self.exposure.begin()
        self.exposure.finish(ticket,"unscaled")
        trace.outcome("unscaled",None,ticket)
        trace.end(agent,result=1.)
        with self.np.load(trace.directory / "attempt-01.npz",allow_pickle=False) as archive:
            self.np.testing.assert_array_equal(archive["projected_target"],expected)
            self.np.testing.assert_array_equal(archive["draw__indices"],raw[8])
        receipt=json.loads((trace.directory / "attempt-01.json").read_text())
        self.assertTrue(receipt["numerical_capture_complete"])
        self.assertEqual(receipt["optimizer_outcome"],"applied_admission")
        self.assertTrue(all(receipt["array_finite"].values()))
        self.assertFalse(json.loads((trace.directory / "status.json").read_text())["numerical_captures_complete"])
        self.assertFalse(torch.cuda.is_initialized())


if __name__ == "__main__":
    unittest.main()
