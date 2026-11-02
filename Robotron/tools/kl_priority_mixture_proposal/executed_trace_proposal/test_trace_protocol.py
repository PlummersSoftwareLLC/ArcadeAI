"""Unexecuted stdlib/mock contracts; no real AMP/model outcome validation."""
import ast
from contextlib import nullcontext
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock


HERE = Path(__file__).parent
ROOT = HERE.parents[3]


def load_file(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


class FakeArray:
    nbytes = 4
    def __init__(self): self.flags = SimpleNamespace(writeable=True)
    def copy(self): return FakeArray()


class FakeTensor:
    dtype = "float32"
    def __init__(self, shape=()): self.shape = shape
    def numel(self):
        result=1
        for size in self.shape: result*=size
        return result
    def detach(self): return self
    def float(self): return self
    def cpu(self): return self
    def numpy(self): return FakeArray()


class TraceProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="robotron-ce-trace-protocol-")
        self.environment=mock.patch.dict(os.environ,{"DQN_PER_PRIORITY_METRIC":"ce"})
        self.environment.start()
        self.work = Path(self.temp.name)
        self.module = load_file("private_executed_trace", HERE / "executed_ce_trace.py")
        # Actual scalar-only production exposure class, privately copied.
        source = ROOT / "Robotron/Scripts/dqn/learning_exposure.py"
        import hashlib
        data = source.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         "30d9191e9fc845d80e52a7a891244fcf0c7041cf60529f6559b15e6d47ac5c7f")
        target = self.work / "exposure.py"
        target.write_bytes(data)
        self.exposure_module = load_file("private_trace_exposure", target)
        self.exposure = self.exposure_module.OptimizerExposure()
        self.cfg = SimpleNamespace(batch_size=4096, num_atoms=51, replay_prefetch_slots=3)
        self.trace = self.module.ExecutedCETrace(self.work / "ce-executed-trace-test", self.cfg,
            optimizer_exposure=self.exposure, runtime={"test": "CPU mocked protocol only"})
        self.agent = SimpleNamespace(training_steps=0, optimized_samples=0,
            optimizer=SimpleNamespace(param_groups=[{"lr": 2.5e-5}]))
        self.metadata = {"capture_id": "private-contract", "observer_error": None,
                         "lock_observation_finished_monotonic_ns": 0}
        self.batch = self.module.ObservedReplayBatch(tuple(range(10)), self.metadata)

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def outcome(self, found_inf=0.):
        ticket = self.exposure.begin()
        self.exposure.finish(ticket, "single_cuda_found_inf", found_inf)
        self.trace.outcome("single_cuda_found_inf", found_inf, ticket)

    def payload(self):
        return tuple(FakeTensor(shape) for shape in
            ((4096,51),(4096,51),(4096,),(4096,),(4096,),
             (4096,51),(4096,51),(),(),()))

    def test_first8_consumed_ordinals_include_skip_and_learner_failure_no_ninth(self):
        with mock.patch.object(self.trace, "_persist_row"):
            for index in range(8):
                self.trace.begin(self.agent, self.batch, None)
                if index == 2:
                    self.trace.end(self.agent, exception=RuntimeError("forward failed"))
                    continue
                self.trace.loss(self.agent, FakeTensor((4096,)), self.payload(),
                    weighted_loss=FakeTensor(), bc_loss=FakeTensor(), schedule=(.1,.1,.1), backend="mock")
                self.outcome(1. if index == 3 else 0.)
                self.trace.end(self.agent, result=1.)
            self.trace.begin(self.agent, self.batch, None)
        self.assertEqual(self.trace.consumed, 8)
        self.assertEqual([row["index"] for row in self.trace.rows], list(range(1,9)))
        self.assertEqual(self.trace.rows[2]["status"], "learner_exception")
        self.assertEqual(self.trace.rows[3]["optimizer_outcome"], "amp_skipped")
        self.assertFalse(self.trace.want_draw())
        status = json.loads((self.trace.directory / "status.json").read_text())
        self.assertFalse(status["numerical_captures_complete"])

    def test_clock_failure_after_reservation_cannot_replace_consumed_ordinal(self):
        with mock.patch.object(self.trace, "_clocks", side_effect=OSError("observer clocks")):
            self.trace.begin(self.agent, self.batch, None)
        self.trace.end(self.agent, exception=RuntimeError("original transfer"))
        self.assertEqual(self.trace.consumed, 1)
        self.assertEqual(self.trace.rows[0]["index"], 1)
        self.assertTrue(self.trace.errors)
        self.assertIsNone(self.trace.current)

    def test_exposure_unavailable_or_unfinished_ticket_is_not_advertised_applied(self):
        with mock.patch.object(self.trace, "_persist_row"):
            self.trace.begin(self.agent, self.batch, None)
            ticket = self.exposure.begin()
            self.trace.outcome("unsupported", None, ticket)
            self.trace.end(self.agent, result=1.)
        self.assertEqual(self.trace.rows[0]["optimizer_outcome"], "unavailable")
        self.assertFalse(self.trace.rows[0]["outcome_available"])

    def test_real_exposure_identity_epoch_change_is_retained_as_unavailable(self):
        with mock.patch.object(self.trace, "_persist_row"):
            self.trace.begin(self.agent, self.batch, None)
            self.outcome()
            self.exposure.new_epoch("test concurrent restore")
            self.trace.end(self.agent, result=1.)
        self.assertFalse(self.trace.rows[0]["outcome_available"])

    def test_observer_readback_fault_does_not_replace_attempt_or_raise(self):
        self.trace.begin(self.agent, self.batch, None)
        broken = FakeTensor((4096,))
        broken.cpu = mock.Mock(side_effect=OSError("observer readback"))
        self.trace.loss(self.agent, broken, self.payload(), weighted_loss=FakeTensor(),
                        bc_loss=FakeTensor(), schedule=(0.,0.,0.), backend="mock")
        with mock.patch.object(self.trace, "_persist_row"):
            self.outcome()
            self.trace.end(self.agent, result=1.)
        self.assertEqual(self.trace.consumed, 1)
        self.assertFalse(self.trace.rows[0]["numerical_capture_complete"])
        self.assertTrue(any("readback" in item for item in self.trace.errors))

    def test_disk_failure_latches_invalid_and_does_not_escape_or_erase_known_outcome(self):
        self.trace.begin(self.agent, self.batch, None)
        self.outcome()
        with mock.patch.object(self.trace, "_persist_row", side_effect=OSError("disk full")):
            self.trace.end(self.agent, result=1.)
        self.assertEqual(self.trace.rows[0]["optimizer_outcome"], "applied_admission")
        self.assertFalse(self.trace.rows[0]["numerical_capture_complete"])
        self.assertTrue(self.trace.errors)

    def test_observer_attachment_failure_keeps_original_single_draw(self):
        raw = tuple(range(10))
        memory = SimpleNamespace(sample_with_metadata=mock.Mock(return_value=(raw,self.metadata)),
                                 sample=mock.Mock(side_effect=AssertionError("resampled")))
        with mock.patch.object(self.module, "ObservedReplayBatch", side_effect=MemoryError("attach")):
            actual = self.trace.sample(memory,4096,1.)
        self.assertIs(actual, raw)
        memory.sample_with_metadata.assert_called_once()
        memory.sample.assert_not_called()
        self.assertTrue(self.trace.errors)

    def test_actual_sampler_error_is_never_swallowed_or_retried(self):
        failure = OSError("original storage error")
        memory = SimpleNamespace(sample_with_metadata=mock.Mock(side_effect=failure), sample=mock.Mock())
        with self.assertRaises(OSError) as caught:
            self.trace.sample(memory,4096,1.)
        self.assertIs(caught.exception, failure)
        memory.sample_with_metadata.assert_called_once()
        memory.sample.assert_not_called()

    def test_producer_failure_does_not_attach_to_different_current_consumer(self):
        self.trace.begin(self.agent,self.batch,None)
        worker = threading.Thread(target=lambda:self.trace.invalidate("future_draw", OSError("copy")))
        worker.start(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertTrue(self.trace.errors)
        self.assertEqual(self.trace.rows[0]["observer_errors"], [])

    def test_real_wrapper_preserves_original_error_and_release_when_observer_raises(self):
        tree = ast.parse((HERE / "training.py").read_text())
        functions = [node for node in tree.body if isinstance(node,ast.FunctionDef)
                     and node.name in ("_trace_observe","train_step")]
        original = RuntimeError("original learner")
        def implementation(agent,batch): raise original
        observer = SimpleNamespace(end=mock.Mock(side_effect=OSError("observer")),
                                   invalidate=mock.Mock(side_effect=OSError("reporting")))
        namespace = dict(nullcontext=nullcontext,_train_step_impl=implementation)
        exec(compile(ast.Module(body=functions,type_ignores=[]),"private_wrapper","exec"),namespace)
        agent = SimpleNamespace(_executed_ce_trace=observer,_training_lock=threading.RLock())
        prepared = SimpleNamespace(release=mock.Mock())
        with self.assertRaises(RuntimeError) as caught:
            namespace["train_step"](agent,prepared)
        self.assertIs(caught.exception,original)
        prepared.release.assert_called_once()

    def test_real_wrapper_observer_only_fault_returns_original_loss(self):
        tree = ast.parse((HERE / "training.py").read_text())
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef)
                   and node.name in ("_trace_observe","train_step")]
        namespace=dict(nullcontext=nullcontext,_train_step_impl=lambda agent,batch:1.25)
        exec(compile(ast.Module(body=functions,type_ignores=[]),"private_wrapper","exec"),namespace)
        observer=SimpleNamespace(end=mock.Mock(side_effect=OSError("observer")),invalidate=mock.Mock())
        agent=SimpleNamespace(_executed_ce_trace=observer,_training_lock=threading.RLock())
        self.assertEqual(namespace["train_step"](agent),1.25)
        observer.invalidate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
