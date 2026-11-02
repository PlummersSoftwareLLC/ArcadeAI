"""CPU-only parity and fail-closed checks; never initialize a RainbowAgent."""

import copy
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = ""

import numpy as np
import torch

from . import inference_actor as module
from .agent import RainbowAgent, ENGINE_VERSION
from .managed_measurement import ManagedMeasurement
from .model import RainbowNet, NUM_FIRE, NUM_JOINT, NUM_MOVE


class TinyNet(torch.nn.Module):
    def __init__(self, size):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.arange(NUM_JOINT * size).float().reshape(NUM_JOINT, size) / 100)
        self.bias = torch.nn.Parameter(torch.linspace(-1, 1, NUM_JOINT))
        self.register_buffer("support", torch.linspace(-10, 50, 51))

    def q_values_joint(self, states):
        return states @ self.weight.T + self.bias


def checkpoint(state, state_size=4, frame_stack=1):
    return dict(engine_version=ENGINE_VERSION, state_size=state_size,
                single_frame_state_size=state_size // frame_stack, frame_stack=frame_stack,
                training_steps=7, optimized_samples=14336, learner_frame_count=90, frame_count=100,
                online_state_dict=state)


class InferenceActorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="robotron-inference-actor-")
        self.path = Path(self.temporary.name) / "actor.pt"
        self.cfg = SimpleNamespace(state_size=4, single_frame_state_size=4, frame_stack=1)
        self.config_patch = patch.object(module, "RL_CONFIG", self.cfg)
        self.net_patch = patch.object(module, "RainbowNet", TinyNet)
        self.config_patch.start()
        self.net_patch.start()
        self.state = TinyNet(4).state_dict()
        self.data = checkpoint(self.state)
        torch.save(self.data, self.path)

    def tearDown(self):
        self.net_patch.stop()
        self.config_patch.stop()
        self.temporary.cleanup()

    def actor(self):
        return module.InferenceActor(self.path, device="cpu")

    def test_greedy_and_locked_fire_parity_with_production_agent_methods(self):
        actor = self.actor()
        states = np.asarray([[1, 2, 3, 4], [-1, -2, -3, -4], [0, 0, 0, 0]], dtype=np.float32)
        fake_agent = SimpleNamespace(_infer_q_joint=actor._infer_q_joint)
        locks = [None, -4, 99]
        expected = RainbowAgent.act_batch(fake_agent, states, [0, 0, 0], locks)
        self.assertEqual(actor.act_batch(states, [0, 0, 0], locks), expected)
        for state, lock, expected_action in zip(states, locks, expected):
            self.assertEqual(actor.act(state, 0, lock), expected_action)
            self.assertEqual(RainbowAgent.act(fake_agent, state, 0, lock), expected_action)
        q = actor.infer_net.q_values_joint(torch.from_numpy(states))
        self.assertTrue(torch.equal(actor._infer_q_joint(torch.from_numpy(states), return_cpu=True), q))
        self.assertEqual(actor.act_batch([], []), [])

    def test_tie_breaking_and_short_locked_fire_list_match_production(self):
        actor = self.actor()
        with torch.no_grad():
            actor.infer_net.weight.zero_()
            actor.infer_net.bias.zero_()
        rows = [np.zeros(4, dtype=np.float32)] * 3
        fake_agent = SimpleNamespace(_infer_q_joint=actor._infer_q_joint)
        self.assertEqual(actor.act_batch(rows, [0, 0, 0], [5]),
                         RainbowAgent.act_batch(fake_agent, rows, [0, 0, 0], [5]))
        self.assertEqual(actor.act(rows[0], 0), (0, 0, False))
        self.assertEqual(actor.act(rows[0], 0, 5), (0, 5, False))

    def test_checkpoint_metadata_identity_and_legacy_default_are_immutable(self):
        actor = self.actor()
        metadata = actor.checkpoint_metadata
        self.assertEqual(metadata["measurement_frame_count"], 0)
        self.assertEqual(metadata["defaulted_metadata_fields"], ("measurement_frame_count",))
        metadata["training_steps"] = 999
        self.assertEqual(actor.training_steps, 7)
        with self.assertRaises(AttributeError):
            actor.checkpoint_sha256 = "changed"
        with self.assertRaises(AttributeError):
            actor.training_steps = 99
        self.assertEqual(actor.numeric_policy["weights"], "float32")
        self.assertFalse(actor.numeric_policy["autocast"])
        self.assertFalse(actor.numeric_policy["compiled"])
        self.assertIsNone(actor.memory)
        self.assertIsNone(actor.optimizer)
        self.assertTrue(all(not p.requires_grad for p in actor.infer_net.parameters()))

    def test_mutation_and_training_apis_fail_closed(self):
        actor = self.actor()
        for name in ("step", "train", "train_step", "save", "load", "update_target", "add_replay",
                     "save_replay", "load_replay", "clear_replay", "start_training_thread",
                     "snapshot_training_state", "restore_training_state"):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                getattr(actor, name)()
        with self.assertRaises(RuntimeError):
            actor.training_enabled = True
        self.assertFalse(actor.training_enabled)
        actor.training_enabled = False

    def test_optional_raw_metric_clocks_are_preserved_without_reconciling_branches(self):
        self.data.update(total_training_steps=3, total_optimized_samples=2048,
                         last_target_update_samples=1024, measurement_frame_count=10)
        torch.save(self.data, self.path)
        actor = self.actor()
        metadata = actor.checkpoint_metadata
        self.assertEqual(metadata["total_training_steps"], 3)
        self.assertEqual(metadata["total_optimized_samples"], 2048)
        self.assertEqual(metadata["last_target_update_samples"], 1024)
        self.assertEqual(metadata["defaulted_metadata_fields"], ())
        self.assertEqual(actor.training_steps, 7)
        self.assertEqual(actor.optimized_samples, 14336)

    def test_strict_checkpoint_rejections_precede_any_policy_install(self):
        actor = self.actor()
        cases = [
            lambda x: x.update(engine_version=27),
            lambda x: x.update(state_size=5),
            lambda x: x.update(frame_stack=2),
            lambda x: x.update(single_frame_state_size=5),
            lambda x: x.update(optimized_samples=-1),
            lambda x: x.pop("learner_frame_count"),
            lambda x: x.update(measurement_frame_count=None),
            lambda x: x.update(total_training_steps=True),
            lambda x: x.update(total_optimized_samples=-1),
            lambda x: x.update(last_target_update_samples=1.5),
            lambda x: x["online_state_dict"].pop("bias"),
            lambda x: x["online_state_dict"].update(extra=torch.zeros(1)),
            lambda x: x["online_state_dict"].update(bias=torch.zeros(NUM_JOINT + 1)),
            lambda x: x["online_state_dict"].update(bias=x["online_state_dict"]["bias"].double()),
            lambda x: x["online_state_dict"]["bias"].fill_(float("nan")),
            lambda x: x["online_state_dict"]["support"].add_(1),
        ]
        before = actor.capture_inference_policy()
        for index, mutate in enumerate(cases):
            data = copy.deepcopy(self.data)
            mutate(data)
            path = self.path.with_name(f"bad-{index}.pt")
            torch.save(data, path)
            with self.subTest(index=index), self.assertRaises(ValueError):
                actor.prepare_inference_checkpoint(path)
        self.assertIsNone(actor.inference_error)
        self.assertTrue(all(torch.equal(before[k], actor.infer_net.state_dict()[k]) for k in before))

    def test_selected_file_replacement_does_not_change_identity_or_restoration_copy(self):
        actor = self.actor()
        sha256 = actor.checkpoint_sha256
        modified = copy.deepcopy(self.data)
        modified["online_state_dict"]["bias"].add_(10)
        torch.save(modified, self.path)
        with self.assertRaisesRegex(ValueError, "identity changed"):
            actor.prepare_inference_checkpoint(self.path)
        self.assertEqual(actor.checkpoint_sha256, sha256)
        captured = actor.capture_inference_policy()
        self.assertTrue(torch.equal(captured["bias"], self.data["online_state_dict"]["bias"]))
        captured["bias"].zero_()
        self.assertFalse(torch.equal(captured["bias"], actor.capture_inference_policy()["bias"]))

    def test_invalid_inference_requests_latch_fatal_instead_of_neutral_fallback(self):
        requests = [lambda a: a.act(np.zeros(4, dtype=np.float32), .1),
                    lambda a: a.act(np.zeros(3, dtype=np.float32), 0),
                    lambda a: a.act(np.full(4, np.nan, dtype=np.float32), 0),
                    lambda a: a.act_batch([np.zeros(4)], []),
                    lambda a: a.act(np.zeros(4), 0, float("nan"))]
        for request in requests:
            actor = self.actor()
            with self.assertRaises((ValueError, RuntimeError)):
                request(actor)
            self.assertIsNotNone(actor.inference_error)
            with self.assertRaisesRegex(RuntimeError, "latched fatal"):
                actor.act(np.zeros(4), 0)

    def test_runtime_model_failure_and_nonfinite_q_latch_fatal(self):
        for result in (None, torch.full((1, NUM_JOINT), float("nan"))):
            actor = self.actor()
            error = RuntimeError("injected model failure") if result is None else None
            with patch.object(actor.infer_net, "q_values_joint", return_value=result, side_effect=error):
                with self.assertRaises((RuntimeError, ValueError)):
                    actor.act(np.zeros(4), 0)
            self.assertIsNotNone(actor.inference_error)

    def test_install_preserves_storage_counters_identity_and_original_policy(self):
        actor = self.actor()
        original = actor.capture_inference_policy()
        replacement = {key: value.clone() for key, value in original.items()}
        replacement["bias"].add_(1)
        with self.assertRaises(RuntimeError):
            actor.install_inference_policy(replacement)
        actor.behavior_locked = True
        storage = {key: value.data_ptr() for key, value in actor.infer_net.state_dict().items()}
        clocks = actor.training_steps, actor.optimized_samples, actor.checkpoint_sha256
        actor.install_inference_policy(replacement)
        self.assertEqual(storage, {key: value.data_ptr() for key, value in actor.infer_net.state_dict().items()})
        self.assertEqual(clocks, (actor.training_steps, actor.optimized_samples, actor.checkpoint_sha256))
        self.assertTrue(torch.equal(actor.capture_inference_policy()["bias"], original["bias"]))
        actor.install_inference_policy(actor.capture_inference_policy())
        self.assertTrue(torch.equal(actor.infer_net.state_dict()["bias"], original["bias"]))

    def test_managed_measurement_full_enter_exit_restores_original_without_clocks(self):
        actor = self.actor()
        replacement = copy.deepcopy(self.data)
        replacement["online_state_dict"]["bias"].add_(1)
        other = self.path.with_name("reference.pt")
        torch.save(replacement, other)
        metrics = SimpleNamespace(lock=threading.RLock(), training_enabled=False,
                                  total_training_steps=7, total_optimized_samples=14336,
                                  learner_frame_count=90, measurement_active=False,
                                  measurement_generation=0, measurement_label="")
        clock = [100.0]
        cohort = dict(complete=False, valid=False, started=1, pending=1, abandoned=0,
                      count=0, rows=[], started_actor_slots=[0])
        controller = ManagedMeasurement(actor, metrics,
            SimpleNamespace(cohort_status=lambda *args: dict(cohort)),
            boundary_status=lambda generation: dict(ready=True, generation=generation, actor_slots=[0]),
            clock=lambda: clock[0])
        before = actor.capture_inference_policy()
        controller.enter("reference", checkpoint_path=other, cohort_s=1, timeout_s=10)
        controller.tick()
        self.assertTrue(torch.equal(actor.infer_net.state_dict()["bias"], replacement["online_state_dict"]["bias"]))
        clock[0] = 102
        cohort.update(complete=True, valid=True, pending=0, count=1, mean=0, rows=[{"score": 0}])
        self.assertTrue(controller.tick()["valid"])
        self.assertEqual(controller.exit()["phase"], "finished")
        self.assertTrue(all(torch.equal(before[key], actor.infer_net.state_dict()[key]) for key in before))
        self.assertEqual((actor.training_steps, actor.optimized_samples, metrics.learner_frame_count), (7, 14336, 90))
        self.assertFalse(actor.training_enabled)

    def test_inference_and_installs_are_serialized(self):
        actor = self.actor()
        actor.behavior_locked = True
        original = actor.capture_inference_policy()
        replacement = {key: value.clone() for key, value in original.items()}
        replacement["bias"].add_(10)
        values, errors = [], []
        def reader():
            try:
                for _ in range(30):
                    values.append(float(actor._infer_q_joint(torch.zeros(1, 4), return_cpu=True)[0, 0]))
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=reader)
        thread.start()
        for index in range(20):
            actor.install_inference_policy(original if index % 2 else replacement)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertTrue(set(values).issubset({-1.0, 9.0}))

    def test_unsupported_precision_and_devices_fail_closed(self):
        with self.assertRaises(ValueError):
            module.InferenceActor(self.path, inference_dtype=torch.float16)
        with self.assertRaises(ValueError):
            module.InferenceActor(self.path, device="meta")
        with self.assertRaises(ValueError):
            module.InferenceActor(self.path, device="cpu", inference_backend="inductor")
        with self.assertRaises(ValueError):
            module.InferenceActor(self.path, inference_backend="unknown")

    def prepare_fake_compiled(self, actor, compiler=None, graph_state=None):
        graph_state = graph_state or dict(unique_graphs=2, graph_breaks=0, unimplemented=0)
        state_patch = patch.object(actor, "_compiled_graph_state", return_value=graph_state)
        state_patch.start()
        self.addCleanup(state_patch.stop)
        compile_patch = patch.object(torch, "compile", side_effect=compiler or (lambda fn, **kwargs: fn))
        mocked = compile_patch.start()
        self.addCleanup(compile_patch.stop)
        actor._prepare_compiled_inference()
        return mocked, state_patch

    def test_compiled_warm_serving_context_thread_storage_and_policy_restore(self):
        import torch._dynamo as dynamo
        actor = self.actor()
        pointers = {key:value.data_ptr() for key,value in actor.infer_net.state_dict().items()}
        observations = []

        def compiler(fn, **kwargs):
            def compiled(states):
                observations.append((len(states), torch.is_inference_mode_enabled(), threading.current_thread().name))
                return fn(states)
            return compiled

        with dynamo.config.patch(error_on_recompile=False, suppress_errors=False):
            mocked, _ = self.prepare_fake_compiled(actor, compiler)
            self.assertEqual(mocked.call_args.kwargs,
                             dict(backend="inductor", dynamic=True, options={"triton.cudagraphs":False}))
            self.assertEqual({row[0] for row in observations}, set(range(1,17)))
            self.assertTrue(all(row[1] for row in observations))
            self.assertTrue(any(row[2] == "CompileServingProbe" for row in observations))
            self.assertTrue(dynamo.config.error_on_recompile)
            self.assertEqual(actor.numeric_policy["backend"], "inductor")
            self.assertTrue(actor.numeric_policy["serving_thread_checked"])
            self.assertEqual(actor.compile_report["graph_state"]["unique_graphs"], 2)
            expected = actor.act(np.ones(4,dtype=np.float32),0)
            actor.behavior_locked = True
            actor.install_inference_policy(actor.capture_inference_policy())
            self.assertEqual(actor.act(np.ones(4,dtype=np.float32),0), expected)
            self.assertEqual(pointers,{key:value.data_ptr() for key,value in actor.infer_net.state_dict().items()})
            self.assertIsNone(actor.inference_error)

    def test_compiled_runtime_failure_does_not_fall_back_to_eager(self):
        import torch._dynamo as dynamo
        actor = self.actor()
        with dynamo.config.patch(error_on_recompile=False, suppress_errors=False):
            self.prepare_fake_compiled(actor)
            failing = lambda states: (_ for _ in ()).throw(RuntimeError("compiled runtime failed"))
            actor.compiled_infer_q_joint = failing
            with patch.object(actor.infer_net,"q_values_joint",side_effect=AssertionError("eager fallback")) as eager:
                with self.assertRaisesRegex(RuntimeError,"compiled runtime failed"):
                    actor.act(np.zeros(4,dtype=np.float32),0)
                eager.assert_not_called()
            self.assertIs(actor.compiled_infer_q_joint, failing)
            self.assertIsNotNone(actor.inference_error)

    def test_compiled_managed_measurement_preserves_callable_guard_storage_and_clocks(self):
        import torch._dynamo as dynamo
        actor=self.actor()
        with dynamo.config.patch(error_on_recompile=False,suppress_errors=False):
            self.prepare_fake_compiled(actor)
            function=actor.compiled_infer_q_joint
            guard=dict(actor._compile_guard)
            pointers={key:value.data_ptr() for key,value in actor.infer_net.state_dict().items()}
            metrics=SimpleNamespace(lock=threading.RLock(),training_enabled=False,
                total_training_steps=7,total_optimized_samples=14336,learner_frame_count=90,
                measurement_active=False,measurement_generation=0,measurement_label="")
            clock=[100.0]
            cohort=dict(complete=False,valid=False,started=1,pending=1,abandoned=0,count=0,rows=[],started_actor_slots=[0])
            controller=ManagedMeasurement(actor,metrics,SimpleNamespace(cohort_status=lambda *args:dict(cohort)),
                boundary_status=lambda generation:dict(ready=True,generation=generation,actor_slots=[0]),clock=lambda:clock[0])
            expected=actor.act(np.ones(4,dtype=np.float32),0)
            controller.enter("compiled",checkpoint_path=self.path,cohort_s=1,timeout_s=10)
            controller.tick()
            clock[0]=102
            cohort.update(complete=True,valid=True,pending=0,count=1,rows=[{"score":0}])
            self.assertTrue(controller.tick()["valid"])
            controller.exit()
            self.assertIs(actor.compiled_infer_q_joint,function)
            self.assertEqual(actor._compile_guard,guard)
            self.assertEqual(pointers,{key:value.data_ptr() for key,value in actor.infer_net.state_dict().items()})
            self.assertEqual((actor.training_steps,actor.optimized_samples,metrics.learner_frame_count),(7,14336,90))
            self.assertEqual(actor.act(np.ones(4,dtype=np.float32),0),expected)

    def test_compiled_guard_rejects_postwarm_graph_or_strict_setting_changes(self):
        import torch._dynamo as dynamo
        for change in ("graphs", "suppression", "recompile", "batch"):
            with self.subTest(change=change), dynamo.config.patch(error_on_recompile=False,suppress_errors=False):
                actor=self.actor()
                self.prepare_fake_compiled(actor)
                if change=="graphs":
                    actor._compiled_graph_state.return_value=dict(unique_graphs=3,graph_breaks=0,unimplemented=0)
                elif change=="suppression":dynamo.config.suppress_errors=True
                elif change=="recompile":dynamo.config.error_on_recompile=False
                with self.assertRaises((RuntimeError,ValueError)):
                    if change=="batch":actor.act_batch(np.zeros((17,4),dtype=np.float32),[0]*17)
                    else:actor.act(np.zeros(4,dtype=np.float32),0)
                self.assertIsNotNone(actor.inference_error)

    def test_compile_rejects_fallback_graphbreak_and_serving_thread_failures(self):
        import torch._dynamo as dynamo
        for state in (dict(unique_graphs=0,graph_breaks=0,unimplemented=0),
                      dict(unique_graphs=2,graph_breaks=1,unimplemented=0),
                      dict(unique_graphs=2,graph_breaks=0,unimplemented=1)):
            with self.subTest(state=state), dynamo.config.patch(error_on_recompile=False,suppress_errors=False):
                with self.assertRaisesRegex(RuntimeError,"complete supported graphs"):
                    self.prepare_fake_compiled(self.actor(), graph_state=state)
        def compiler(fn,**kwargs):
            def compiled(states):
                if threading.current_thread().name=="CompileServingProbe":
                    raise RuntimeError("serving-thread compile guard")
                return fn(states)
            return compiled
        with dynamo.config.patch(error_on_recompile=False,suppress_errors=False):
            actor=self.actor()
            with self.assertRaisesRegex(RuntimeError,"serving-thread warmup failed"):
                self.prepare_fake_compiled(actor,compiler)
            self.assertIsNotNone(actor.inference_error)


class RealNetworkParityTests(unittest.TestCase):
    def test_actual_rainbow_net_fp32_q_and_production_action_helpers(self):
        # One real model/checkpoint verifies the adapter did not only satisfy
        # the lightweight fake's interface. No RainbowAgent is instantiated.
        torch.set_num_threads(2)
        cfg = module.RL_CONFIG
        with tempfile.TemporaryDirectory(prefix="robotron-real-inference-") as directory:
            path = Path(directory) / "actor.pt"
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(4126)
                original = RainbowNet(cfg.state_size).cpu().float().eval()
            torch.save(checkpoint(original.state_dict(), cfg.state_size, cfg.frame_stack), path)
            actor = module.InferenceActor(path, device="cpu")
            rng = np.random.default_rng(115)
            states = rng.normal(0, .1, (3, cfg.state_size)).astype(np.float32)
            with torch.inference_mode():
                expected_q = original.q_values_joint(torch.from_numpy(states))
            actual_q = actor._infer_q_joint(torch.from_numpy(states), return_cpu=True)
            self.assertTrue(torch.equal(expected_q, actual_q))
            fake_agent = SimpleNamespace(_infer_q_joint=actor._infer_q_joint)
            for locks in ([None, None, None], [0, 4, 8]):
                self.assertEqual(actor.act_batch(states, [0, 0, 0], locks),
                                 RainbowAgent.act_batch(fake_agent, states, [0, 0, 0], locks))
            self.assertFalse(actor.infer_net.training)


if __name__ == "__main__":
    unittest.main()
