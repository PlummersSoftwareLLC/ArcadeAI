"""CPU-only checks of bounded counters, model-lock timing and output ownership."""

from contextlib import contextmanager
import copy
import json
import os
import random
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = ""

import numpy as np
import torch

from .agent import RainbowAgent
from .pipeline_telemetry import PipelineTelemetry


def tiny_agent(*, separate=True, sample_every=1):
    agent = RainbowAgent.__new__(RainbowAgent)
    agent._sync_lock, agent._training_lock = threading.RLock(), threading.RLock()
    agent._pipeline_telemetry = PipelineTelemetry(sample_every)
    agent.use_separate_inference = separate
    agent.device = agent.inference_device = torch.device("cpu")
    agent._inference_stream = None
    agent.online_net = torch.nn.Linear(2, 2)
    agent.infer_net = torch.nn.Linear(2, 2) if separate else agent.online_net
    agent.target_net = torch.nn.Linear(2, 2)
    agent.training_steps, agent.optimized_samples = 7, 123456
    agent.last_inference_sync = agent.last_inference_sync_samples = 0
    agent.last_target_update_samples, agent.baseline_batch_size = 0, 512
    agent.behavior_locked = False
    return agent


class TestPipelineCounters(unittest.TestCase):
    def test_sampling_buckets_snapshots_and_reset_phase_without_rng(self):
        recorder = PipelineTelemetry(sample_every=3, clock=lambda: 10.0)
        py_rng, np_rng, torch_rng = random.getstate(), np.random.get_state(), torch.get_rng_state()
        sampled = []
        for batch in (1, 4, 8, 17, 256, 512, 3):
            if recorder.begin_inference():
                sampled.append(batch)
                recorder.record_inference({"batch_size": batch, "dispatch_host_ms": batch / 2})
        self.assertEqual(sampled, [1, 17, 3])
        snap = recorder.snapshot()
        self.assertEqual(snap["inference_eligible_calls"], 7)
        self.assertEqual(snap["inference"]["count"], 3)
        self.assertEqual(snap["inference"]["batch_size"]["total"], 21)
        self.assertEqual(snap["inference"]["batch_size"]["max"], 17)
        self.assertEqual(sum(snap["inference"]["batch_size"]["histogram"]), 3)
        self.assertEqual(snap["inference"]["cpu_readback_host_ms"]["count"], 0)
        self.assertEqual(snap["elapsed_s"], 0)
        snap["inference"]["batch_size"]["histogram"][0] = 10000
        self.assertEqual(recorder.snapshot()["inference"]["batch_size"]["histogram"][0], 1)
        drained = recorder.snapshot(reset=True)
        self.assertEqual(drained["generation"], 0)
        self.assertEqual(recorder.snapshot()["generation"], 1)
        self.assertFalse(recorder.begin_inference())  # Sampling phase was not reset.
        self.assertEqual(recorder.snapshot()["inference"]["count"], 0)
        self.assertEqual(random.getstate(), py_rng)
        after = np.random.get_state()
        self.assertEqual(after[0], np_rng[0])
        np.testing.assert_array_equal(after[1], np_rng[1])
        self.assertEqual(after[2:], np_rng[2:])
        self.assertTrue(torch.equal(torch.get_rng_state(), torch_rng))
        json.dumps(recorder.snapshot(), allow_nan=False)

    def test_overflow_is_bounded_and_reset_preserves_concurrent_records(self):
        recorder = PipelineTelemetry()
        start = threading.Barrier(5)
        errors = []

        def writer():
            try:
                start.wait()
                for _ in range(1000):
                    recorder.record_inference({"batch_size": 512, "total_host_ms": 4000})
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for thread in threads:
            thread.start()
        start.wait()
        count = 0
        while any(thread.is_alive() for thread in threads):
            snap = recorder.snapshot(reset=True)
            count += snap["inference"]["count"]
            self.assertEqual(sum(snap["inference"]["batch_size"]["histogram"]),
                             snap["inference"]["count"])
            time.sleep(0.0001)
        for thread in threads:
            thread.join(timeout=2)
        final = recorder.snapshot()
        count += final["inference"]["count"]
        self.assertEqual(count, 4000)
        self.assertFalse(errors)
        recorder.record_inference({"batch_size": 999999, "total_host_ms": 999999})
        final = recorder.snapshot()
        self.assertEqual(len(final["inference"]["batch_size"]["histogram"]), 10)
        self.assertGreaterEqual(final["inference"]["batch_size"]["histogram"][-1], 1)
        self.assertGreaterEqual(final["inference"]["total_host_ms"]["histogram"][-1], 1)

    def test_non_draining_reads_are_monotone_and_invalid_period_rejected(self):
        for invalid in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                PipelineTelemetry(invalid)
        recorder = PipelineTelemetry()
        recorder.record_target_refresh(2)
        first = recorder.snapshot()
        recorder.record_target_refresh(1, error=True)
        second = recorder.snapshot()
        self.assertEqual(second["target_refresh"]["count"], 2)
        self.assertEqual(second["target_refresh"]["errors"], 1)
        self.assertEqual(second["target_refresh"]["host_ms"]["total"], 3)
        self.assertEqual(second["target_refresh"]["host_ms"]["max"], 2)
        self.assertGreaterEqual(second["elapsed_s"], first["elapsed_s"])


class TestAgentPipelineTelemetry(unittest.TestCase):
    def test_tensor_tuple_and_raw_result_identity_without_extra_cuda_calls(self):
        agent = tiny_agent(sample_every=2)
        data = torch.tensor([[1.0, 2.0], [3.0, 4.0]], requires_grad=True)
        original = data.detach().clone()
        with patch.object(torch.cuda, "synchronize", side_effect=AssertionError("new GPU barrier")):
            result = agent._run_inference(lambda x: (x * 2, x.sum(dim=1)), data, return_cpu=True)
            torch.testing.assert_close(result[0], data.detach() * 2)
            torch.testing.assert_close(result[1], data.detach().sum(dim=1))
            self.assertFalse(result[0].requires_grad)
            produced = torch.ones(2, 2)
            self.assertIs(agent._run_inference(lambda x: produced, data), produced)
            agent._run_inference(lambda x: x, data[:1], return_cpu=True)
        torch.testing.assert_close(data, original)
        snap = agent.pipeline_telemetry_snapshot()
        self.assertEqual(snap["inference_eligible_calls"], 3)
        self.assertEqual(snap["inference"]["count"], 2)
        self.assertEqual(snap["inference"]["batch_size"]["total"], 3)
        self.assertEqual(snap["inference"]["training_lock_wait_ms"]["count"], 0)
        self.assertEqual(snap["inference"]["cpu_readback_host_ms"]["count"], 2)

    def test_actual_sync_and_training_lock_waits_are_separate(self):
        for separate, name in ((True, "sync_lock_wait_ms"), (False, "training_lock_wait_ms")):
            with self.subTest(separate=separate):
                agent = tiny_agent(separate=separate)
                lock = agent._sync_lock if separate else agent._training_lock
                started, result, failure = threading.Event(), [], []

                def worker():
                    started.set()
                    try:
                        result.append(agent._run_inference(lambda x: x + 1, torch.zeros(4, 2), True))
                    except BaseException as exc:
                        failure.append(exc)

                with lock:
                    thread = threading.Thread(target=worker)
                    thread.start()
                    self.assertTrue(started.wait(2))
                    # Wait for entry rather than merely thread scheduling.
                    deadline = time.monotonic() + 2
                    while agent.pipeline_telemetry_snapshot()["inference_eligible_calls"] == 0:
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(0.001)
                    time.sleep(0.025)
                    # Snapshot requires only its stats lock even though the worker
                    # is blocked on a model lock held by this thread.
                    self.assertEqual(agent.pipeline_telemetry_snapshot()["inference"]["count"], 0)
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())
                self.assertFalse(failure)
                torch.testing.assert_close(result[0], torch.ones(4, 2))
                stats = agent.pipeline_telemetry_snapshot()["inference"]
                self.assertGreaterEqual(stats[name]["total"], 20)
                self.assertGreaterEqual(stats["total_host_ms"]["total"], stats["service_host_ms"]["total"])
                self.assertGreaterEqual(stats["total_host_ms"]["total"], stats[name]["total"])

    def test_snapshot_does_not_wait_for_forward_and_recording_releases_sync_lock(self):
        agent = tiny_agent()
        active, finish = threading.Event(), threading.Event()
        original_record = agent._pipeline_telemetry.record_inference

        def record(*args, **kwargs):
            self.assertFalse(agent._sync_lock._is_owned())
            return original_record(*args, **kwargs)

        def forward(data):
            active.set()
            self.assertTrue(finish.wait(2))
            return data

        with patch.object(agent._pipeline_telemetry, "record_inference", side_effect=record):
            thread = threading.Thread(target=lambda: agent._run_inference(forward, torch.ones(1, 2)))
            thread.start()
            self.assertTrue(active.wait(2))
            self.assertEqual(agent.pipeline_telemetry_snapshot()["inference"]["count"], 0)
            finish.set()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(agent.pipeline_telemetry_snapshot()["inference"]["count"], 1)

    def test_forward_failure_remains_failure_and_records_incomplete_phases(self):
        agent = tiny_agent()

        def broken(_):
            raise LookupError("original forward error")

        with self.assertRaisesRegex(LookupError, "original forward error"):
            agent._run_inference(broken, torch.zeros(3, 2), True)
        stats = agent.pipeline_telemetry_snapshot()["inference"]
        self.assertEqual(stats["errors"], 1)
        self.assertEqual(stats["dispatch_host_ms"]["count"], 1)
        self.assertEqual(stats["cpu_readback_host_ms"]["count"], 0)
        self.assertEqual(stats["total_host_ms"]["count"], 1)
        self.assertTrue(agent._sync_lock.acquire(blocking=False))
        agent._sync_lock.release()

    def test_refresh_cadence_values_clocks_errors_and_optional_recorder(self):
        agent = tiny_agent()
        before = copy.deepcopy(agent.online_net.state_dict())
        actor_storage = agent.infer_net.weight.data_ptr()
        agent._sync_inference(force=True)
        self.assertEqual(agent.infer_net.weight.data_ptr(), actor_storage)
        for name, value in before.items():
            torch.testing.assert_close(agent.infer_net.state_dict()[name], value)
        self.assertEqual(agent.last_inference_sync_samples, 123456)
        agent._sync_inference()  # No sample credit accrued: do not count a skipped refresh.
        agent.behavior_locked = True
        agent.optimized_samples += 1000000
        agent._sync_inference()  # Frozen actor is also skipped.
        self.assertEqual(agent.pipeline_telemetry_snapshot()["actor_refresh"]["count"], 1)
        self.assertEqual(agent.pipeline_telemetry_snapshot()["actor_refresh"]["forced_count"], 1)
        agent.behavior_locked = False
        agent._sync_inference()
        self.assertEqual(agent.pipeline_telemetry_snapshot()["actor_refresh"]["count"], 2)
        metadata = SimpleNamespace(total_training_steps=19)
        module = sys.modules[RainbowAgent.__module__]
        with patch.object(module, "metrics", metadata):
            agent.update_target(tau=1)
            old_target = copy.deepcopy(agent.target_net.state_dict())
            with torch.no_grad():
                agent.online_net.weight.add_(2)
            agent.update_target(tau=0.25)
        torch.testing.assert_close(agent.target_net.weight, old_target["weight"] + 0.5)
        self.assertEqual(agent.last_target_update_samples, agent.optimized_samples)
        self.assertEqual(metadata.last_target_update_step, 19)
        self.assertEqual(agent.pipeline_telemetry_snapshot()["target_refresh"]["count"], 2)
        with patch.object(agent.target_net, "load_state_dict", side_effect=ValueError("copy failure")):
            with self.assertRaisesRegex(ValueError, "copy failure"):
                agent.update_target(tau=1)
        self.assertEqual(agent.pipeline_telemetry_snapshot()["target_refresh"]["errors"], 1)
        with patch.object(agent.infer_net, "load_state_dict", side_effect=ValueError("actor copy failure")):
            with self.assertRaisesRegex(ValueError, "actor copy failure"):
                agent._sync_inference(force=True)
        self.assertEqual(agent.pipeline_telemetry_snapshot()["actor_refresh"]["errors"], 1)
        del agent._pipeline_telemetry
        self.assertFalse(agent.pipeline_telemetry_snapshot()["available"])
        agent._sync_inference(force=True)
        agent.update_target(tau=1)
        torch.testing.assert_close(agent._run_inference(lambda x: x + 1, torch.zeros(1, 2)), torch.ones(1, 2))

    def test_existing_cuda_stream_dependency_sequence_is_unchanged_using_cpu_fakes(self):
        # No CUDA context or device tensor is created. Compare enabled/absent
        # instrumentation through the real stream branch and actor-copy method.
        for return_cpu in (False, True):
            runs = []
            for enabled in (False, True):
                calls = []

                class Tensor:
                    shape = (3, 2)
                    is_cuda = True
                    def to(self, device):
                        calls.append("input.to")
                        return self
                    def record_stream(self, stream):
                        calls.append("output.record." + stream.name)
                    def detach(self):
                        calls.append("output.detach")
                        return self
                    def cpu(self):
                        calls.append("output.cpu")
                        return self

                class Stream:
                    def __init__(self, name): self.name = name
                    def wait_stream(self, stream): calls.append(self.name + ".wait." + stream.name)
                    def wait_event(self, event): calls.append(self.name + ".wait_event." + event.name)

                class Event:
                    def __init__(self, name="source"): self.name = name
                    def record(self, stream): calls.append(self.name + ".record." + stream.name)

                @contextmanager
                def stream_context(stream):
                    calls.append("enter." + stream.name)
                    try:
                        yield
                    finally:
                        calls.append("exit." + stream.name)

                agent = tiny_agent()
                if not enabled:
                    del agent._pipeline_telemetry
                agent.device = agent.inference_device = torch.device("cuda:0")
                agent._inference_stream = Stream("infer")
                agent._sync_event = Event("copied")
                caller = Stream("caller")
                data, output_a, output_b = Tensor(), Tensor(), Tensor()

                def forward(value):
                    self.assertIs(value, data)
                    calls.append("forward")
                    return output_a, output_b

                with patch.object(torch.cuda, "current_stream", return_value=caller), \
                     patch.object(torch.cuda, "stream", side_effect=stream_context), \
                     patch.object(torch.cuda, "Event", side_effect=Event), \
                     patch.object(torch.cuda, "synchronize", side_effect=AssertionError("new GPU barrier")):
                    self.assertEqual(agent._run_inference(forward, data, return_cpu), (output_a, output_b))
                    agent._sync_inference(force=True)
                runs.append(calls)
                if enabled:
                    self.assertEqual(agent.pipeline_telemetry_snapshot()["actor_refresh"]["count"], 1)
                    self.assertEqual(agent.pipeline_telemetry_snapshot()["inference"]["cpu_readback_host_ms"]["count"],
                                     int(return_cpu))
            self.assertEqual(runs[0], runs[1])
            expected = ["infer.wait.caller", "enter.infer", "input.to", "output.record.infer", "forward"]
            expected += (["output.detach", "output.cpu"] * 2 if return_cpu else [])
            expected += ["exit.infer"]
            if not return_cpu:
                expected += ["caller.wait.infer", "output.record.caller", "output.record.caller"]
            expected += ["source.record.caller", "enter.infer", "infer.wait_event.source",
                         "copied.record.infer", "exit.infer", "caller.wait_event.copied"]
            self.assertEqual(runs[0], expected)


if __name__ == "__main__":
    unittest.main()
