"""CPU ownership/failure checks; real CUDA parity is a separate bounded probe."""
import ast
from contextlib import contextmanager, nullcontext
import copy
import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = ""
import torch

from .exact_inference_graphs import (ExactInferenceGraphs, ExactInferenceGraphError,
                                    private_pool_bytes, storage_signature, disabled_snapshot)

AGENT = Path(__file__).with_name("agent.py")
STAGED = AGENT.parents[2] / "logs/managed-learning-20261015/run-09/agent-exact-graphs-proposed.py"


def methods(namespace, path=None):
    # Run the actual proposed/applied methods without constructing replay/model.
    source = Path(path or AGENT).read_text()
    tree = ast.parse(source)
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "RainbowAgent")
    selected = {"_run_inference", "_infer_q_joint", "_infer_q_branched", "load",
                "pipeline_telemetry_snapshot", "_validate_exact_inference_graphs"}
    nodes = []
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name in selected:
            node = copy.deepcopy(node)
            node.decorator_list = []
            nodes.append(node)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(AGENT), "exec"), namespace)
    return type("AgentMethods", (), {key: namespace[key] for key in selected})


class Tensor:
    def __init__(self, values, *, cuda=False, width=2, events=None):
        self.values = list(values)
        self.shape = (len(values), width)
        self.dtype = "float32"
        self.is_cuda = cuda
        self.device = "cuda:0" if cuda else "cpu"
        self.events = events if events is not None else []
    def copy_(self, other):
        self.events.append("input-copy")
        self.values[:] = other.values
    def record_stream(self, stream): self.events.append("record-stream")
    def detach(self): return self
    def cpu(self):
        self.events.append("cpu-copy")
        return Tensor(self.values, width=self.shape[1], events=self.events)
    def to(self, device):
        self.events.append("to-device")
        return Tensor(self.values, cuda=True, width=self.shape[1], events=self.events)


class Stream:
    def __init__(self, events): self.events = events
    def wait_stream(self, other): self.events.append("wait-stream")


class FakeTorch:
    Tensor = Tensor
    float32 = "float32"
    def __init__(self, events):
        self.cuda = self
        self.caller = Stream(events)
        self.active = self.caller
    def no_grad(self): return nullcontext()
    def current_stream(self, device=None): return self.active
    @contextmanager
    def stream(self, stream):
        previous = self.active
        self.active = stream
        try: yield
        finally: self.active = previous


def bank_fixture():
    events = []
    t = FakeTorch(events)
    bank = ExactInferenceGraphs.__new__(ExactInferenceGraphs)
    bank.torch, bank.device, bank.state_size = t, "cuda:0", 2
    bank.lock, bank._stats_lock = threading.RLock(), threading.Lock()
    bank.stream = Stream(events)
    bank._pending, bank._validating = None, False
    bank._stats = dict(disabled_snapshot(), requested=True, ready=True, fatal_error=None,
                      covered_shapes=list(range(1, 129)), numeric_policy={}, replay_count=0,
                      cpu_return_batches=0, cpu_return_rows=0, validation_replay_count=0,
                      validation_cpu_returns=0, diagnostic_compiled_calls=0)
    bank.slots = {}
    for n in range(1, 129):
        inputs = Tensor([0] * n, cuda=True, events=events)
        outputs = Tensor([0] * n, cuda=True, width=81, events=events)
        def replay(inputs=inputs, outputs=outputs, n=n):
            events.append(("replay", n))
            outputs.values[:] = [value * 3 for value in inputs.values]
        bank.slots[n] = (SimpleNamespace(replay=replay), inputs, outputs)
    return bank, t, events


def actor_fixture():
    bank, t, events = bank_fixture()
    namespace = dict(torch=t, time=time, nullcontext=nullcontext, os=os,
                     ExactInferenceGraphError=ExactInferenceGraphError,
                     disabled_snapshot=disabled_snapshot, unavailable_snapshot=lambda: {},
                     ENGINE_VERSION=28)
    actor = methods(namespace).__new__(methods(namespace))
    actor._exact_inference_graphs, actor._exact_graph_loaded = bank, True
    actor.use_separate_inference, actor.inference_device = True, "cuda:0"
    actor._sync_lock, actor._training_lock = bank.lock, threading.RLock()
    actor._inference_stream = bank.stream
    calls = []
    def compiled(inputs):
        calls.append(len(inputs.values))
        return Tensor([value * 3 for value in inputs.values], cuda=True, width=81, events=events)
    actor.compiled_infer_q_joint = compiled
    bank.compiled = compiled
    actor.infer_net = SimpleNamespace(eval=lambda: None, q_values_joint=compiled,
                                     q_values_branched=compiled)
    return actor, bank, t, events, calls


class ExactGraphCPUChecks(unittest.TestCase):
    def test_private_pool_budget_excludes_unrelated_training_cache(self):
        segments = [{"segment_pool_id": (0, 0), "total_size": 120 << 30},
                    {"segment_pool_id": (1, 4), "total_size": 100},
                    {"segment_pool_id": (1, 4), "total_size": 50},
                    {"segment_pool_id": [1, 8], "total_size": 200}]
        self.assertEqual(private_pool_bytes(segments, {(1, 4), (1, 8)}), 350)
        with self.assertRaises(ExactInferenceGraphError):
            private_pool_bytes(segments, {(1, 9)})

    def test_all_actual_sizes_use_exact_graph_without_compiled_or_padding(self):
        actor, bank, _, events, compiled = actor_fixture()
        for size in reversed(range(1, 129)):
            result = actor._infer_q_joint(Tensor([2] * size), return_cpu=True)
            self.assertEqual(result.values, [6] * size)
        self.assertEqual(compiled, [])
        self.assertEqual([row[1] for row in events if isinstance(row, tuple)], list(reversed(range(1, 129))))
        self.assertNotIn("to-device", events)
        self.assertEqual(bank.snapshot()["cpu_return_batches"], 128)

    def test_cpu_result_is_fresh_and_sync_lock_held_until_copy_finishes(self):
        actor, bank, t, _, _ = actor_fixture()
        first = actor._infer_q_joint(Tensor([7] * 4), True)
        actor._infer_q_joint(Tensor([9] * 4), True)
        self.assertEqual(first.values, [21] * 4)
        active, finish, second_done = threading.Event(), threading.Event(), threading.Event()
        original = bank.slots[4][2].cpu
        def blocked_cpu():
            self.assertTrue(actor._sync_lock._is_owned())
            active.set()
            self.assertTrue(finish.wait(2))
            return original()
        bank.slots[4][2].cpu = blocked_cpu
        failures = []
        def run():
            try: actor._infer_q_joint(Tensor([1] * 4), True)
            except Exception as exc: failures.append(exc)
        thread = threading.Thread(target=run)
        thread.start()
        self.assertTrue(active.wait(2))
        follower = threading.Thread(target=lambda: (run(), second_done.set()))
        follower.start()
        self.assertFalse(second_done.wait(.025))
        finish.set()
        thread.join(2); follower.join(2)
        self.assertFalse(thread.is_alive() or follower.is_alive())
        self.assertFalse(failures)
        self.assertEqual(bank.snapshot()["cpu_return_batches"], 4)

    def test_gpu_and_branched_diagnostics_keep_compiled_stream_ownership(self):
        actor, bank, _, events, compiled = actor_fixture()
        result = actor._infer_q_joint(Tensor([2] * 3), return_cpu=False)
        self.assertTrue(result.is_cuda)
        actor._infer_q_branched(Tensor([3] * 5), return_cpu=True)
        self.assertEqual(compiled, [3, 5])
        self.assertEqual(bank.snapshot()["replay_count"], 0)
        self.assertEqual(bank.snapshot()["diagnostic_compiled_calls"], 1)
        self.assertIn("wait-stream", events)
        self.assertIn("record-stream", events)

    def test_default_off_route_and_eager_failure_fallback_preserved(self):
        actor, _, _, events, compiled = actor_fixture()
        actor._exact_inference_graphs = None
        result = actor._infer_q_joint(Tensor([4] * 3, events=events), True)
        self.assertEqual(result.values, [12] * 3)
        self.assertEqual(compiled, [3])
        self.assertIn("to-device", events)
        actor.compiled_infer_q_joint = lambda _: (_ for _ in ()).throw(ValueError("compiler"))
        self.assertEqual(actor._infer_q_joint(Tensor([4]), True).values, [12])
        self.assertIsNone(actor.compiled_infer_q_joint)

    def test_bad_shape_wrong_stream_or_unfinished_copy_latches_without_fallback(self):
        for defect in ("shape", "dtype", "stream", "pending"):
            with self.subTest(defect=defect):
                actor, bank, t, _, compiled = actor_fixture()
                data = Tensor([1] * (129 if defect == "shape" else 2))
                if defect == "dtype": data.dtype = "float16"
                if defect == "pending": bank._pending = (2, threading.get_ident(), object())
                if defect == "stream":
                    with bank.lock:
                        with self.assertRaises(ExactInferenceGraphError): bank.prepare_input(data)
                else:
                    with self.assertRaises(ExactInferenceGraphError): actor._infer_q_joint(data, True)
                self.assertFalse(bank.snapshot()["ready"])
                with self.assertRaises(ExactInferenceGraphError): actor._infer_q_joint(Tensor([1]), True)
                self.assertEqual(compiled, [])

    def test_replay_readback_and_gpu_compiled_failures_are_fatal(self):
        for defect in ("replay", "cpu", "compiled"):
            actor, bank, _, _, _ = actor_fixture()
            def broken(*args): raise RuntimeError("original " + defect)
            if defect == "replay": bank.slots[2][0].replay = broken
            if defect == "cpu": bank.slots[2][2].cpu = broken
            if defect == "compiled": actor.compiled_infer_q_joint = bank.compiled = broken
            with self.assertRaisesRegex(ExactInferenceGraphError, "original " + defect):
                actor._infer_q_joint(Tensor([1] * 2), defect != "compiled")
            self.assertFalse(bank.snapshot()["ready"])
            self.assertIsNotNone(actor.compiled_infer_q_joint)

    def test_storage_signature_includes_nonpersistent_buffers_and_stride(self):
        net = torch.nn.Linear(2, 2)
        net.register_buffer("nonpersistent", torch.ones(2, 2), persistent=False)
        signature = storage_signature(net)
        self.assertIn("buffer:nonpersistent", signature)
        with torch.no_grad(): net.weight.add_(1)
        self.assertEqual(storage_signature(net), signature)
        net.nonpersistent = net.nonpersistent.t()
        self.assertNotEqual(storage_signature(net), signature)

    def test_snapshot_uses_only_stats_lock_and_returns_detached_metadata(self):
        _, bank, _, _, _ = actor_fixture()
        bank.net = SimpleNamespace(named_parameters=lambda: (_ for _ in ()).throw(AssertionError("model access")))
        bank.torch = SimpleNamespace()
        snap = bank.snapshot()
        snap["covered_shapes"].clear()
        snap["numeric_policy"]["changed"] = True
        self.assertEqual(len(bank.snapshot()["covered_shapes"]), 128)
        self.assertNotIn("changed", bank.snapshot()["numeric_policy"])
        json.dumps(bank.snapshot())

    def test_unvalidated_checkpoint_never_serves_graph(self):
        actor, bank, _, _, compiled = actor_fixture()
        actor._exact_graph_loaded = False
        with self.assertRaisesRegex(ExactInferenceGraphError, "post-load"):
            actor._infer_q_joint(Tensor([1]), True)
        self.assertEqual(compiled, [])

    def test_missing_wrong_corrupt_or_incompatible_checkpoint_never_returns_false_when_requested(self):
        actor, _, t, _, _ = actor_fixture()
        actor._exact_graph_requested = True
        actor.device = "cpu"
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "checkpoint.pt"
            actor._exact_graph_checkpoint = str(file)
            with self.assertRaises(ExactInferenceGraphError): actor.load(str(file), False)
            file.write_bytes(b"dummy")
            with self.assertRaises(ExactInferenceGraphError): actor.load(str(file) + ".other", False)
            t.load = lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("corrupt"))
            with self.assertRaisesRegex(ExactInferenceGraphError, "corrupt"): actor.load(str(file), False)
            t.load = lambda *args, **kwargs: {"engine_version": 0}
            with self.assertRaisesRegex(ExactInferenceGraphError, "engine"): actor.load(str(file), False)
            actor._exact_graph_requested = False
            self.assertFalse(actor.load(str(file), False))
            self.assertFalse(actor.load(str(file) + ".missing", False))

    def test_successful_load_validates_last_and_validation_error_escapes_fresh_fallback(self):
        actor, bank, t, _, _ = actor_fixture()
        actor._exact_graph_requested = True
        actor.device, actor.state_size, actor.baseline_batch_size = "cpu", 2, 512
        actor.target_net = object()
        actor.online_net = object()
        actor._load_compatible = lambda *args: (([], []), [])
        actor._legacy_target_update_samples = lambda: 0
        actor._load_optimizer_state_dict = lambda state: None
        actor._sync_inference = lambda **kwargs: None
        actor.memory = SimpleNamespace(load=lambda *args, **kwargs: True)
        order = []
        namespace = actor.load.__func__.__globals__
        namespace.update(RESET_METRICS=False,
                         metrics=SimpleNamespace(lock=threading.RLock()),
                         RL_CONFIG=SimpleNamespace(expert_ratio_start=.1, epsilon_start=.1))
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "checkpoint.pt"
            file.write_bytes(b"dummy")
            actor._exact_graph_checkpoint = str(file)
            t.load = lambda *args, **kwargs: {"engine_version": 28, "state_size": 2,
                "optimizer_state_dict": {"fake": 1}, "training_steps": 17,
                "optimized_samples": 1234, "lr_gear": "climb"}
            def validated():
                order.append("validated")
                actor._exact_graph_loaded = True
            actor._validate_exact_inference_graphs = validated
            self.assertTrue(actor.load(str(file), False))
            self.assertEqual(order, ["validated"])
            self.assertTrue(actor._exact_graph_loaded)
            def rejected(): raise ExactInferenceGraphError("post-load parity")
            actor._validate_exact_inference_graphs = rejected
            with self.assertRaisesRegex(ExactInferenceGraphError, "post-load parity"):
                actor.load(str(file), False)
            self.assertFalse(actor._exact_graph_loaded)
            self.assertFalse(bank.snapshot()["ready"])
            self.assertEqual((actor.training_steps, actor.optimized_samples), (17, 1234))

    def test_required_checkpoint_failure_happens_before_any_network_allocation(self):
        source = AGENT.read_text()
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "RainbowAgent")
        ctor = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"))
        namespace = dict(os=os, device="cpu", RL_CONFIG=SimpleNamespace(ratchet_enabled=False),
                         LATEST_MODEL_PATH="/missing/latest.pt", MODEL_DIR="/missing",
                         ExactInferenceGraphError=ExactInferenceGraphError)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[ctor], type_ignores=[])), "<actual constructor>", "exec"), namespace)
        with patch.dict(os.environ, {"DQN_EXACT_INFERENCE_GRAPHS": "1", "DQN_EXACT_GRAPH_CHECKPOINT": "/missing/latest.pt"}):
            with self.assertRaisesRegex(ExactInferenceGraphError, "existing"):
                namespace["__init__"](SimpleNamespace(), 2)

    def test_optin_capture_is_before_workers_and_both_worker_paths_gate_readiness(self):
        source = AGENT.read_text()
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "RainbowAgent")
        ctor = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        ctor_text = ast.get_source_segment(source, ctor)
        self.assertLess(ctor_text.index("self._setup_exact_inference_graphs()"), ctor_text.index("ReplayPrefetcher("))
        self.assertLess(ctor_text.index("self._setup_exact_inference_graphs()"), ctor_text.index("self._train_thread.start()"))
        producer = next(n for n in ast.walk(ctor) if isinstance(n, ast.keyword) and n.arg == "enabled_fn")
        predicate = eval(compile(ast.Expression(body=producer.value), "<producer gate>", "eval"),
                         {"metrics": SimpleNamespace(training_enabled=True), "replay_pressure_reached": lambda _: False})
        # Lambda closes over self via its eval globals, as in the constructor.
        owner = SimpleNamespace(running=True, training_enabled=True, _prefetch_paused=False,
                                _exact_graph_requested=True, _exact_graph_loaded=False)
        predicate.__globals__["self"] = owner
        self.assertFalse(predicate())
        owner._exact_graph_loaded = True
        self.assertTrue(predicate())
        worker = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_background_train")
        first_if = next(n for n in worker.body if isinstance(n, ast.While)).body[0]
        condition = compile(ast.Expression(first_if.test), "<learner gate>", "eval")
        owner._exact_graph_loaded = False
        self.assertTrue(eval(condition, {"self": owner}))
        owner._exact_graph_requested = False
        self.assertFalse(eval(condition, {"self": owner}))


if __name__ == "__main__": unittest.main()
