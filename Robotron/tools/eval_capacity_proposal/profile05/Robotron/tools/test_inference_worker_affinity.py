"""Mock clocks/API/affinity: never pin real threads or launch production work."""
import contextlib
import copy
import io
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

from . import inference_worker_affinity as trial


class FakeHost:
    pid = 109

    def __init__(self, treatment_rate=18):
        self.clock = 0
        self.current_mask = list(range(72))
        self.setter_calls = []
        self.binding = dict(worker=dict(trainer=dict(pid=109, starttime_ticks=11),
            thread=dict(tid=110, starttime_ticks=22)), actors=[], logs={})
        self.counts = dict(applied=100, frames=51200, learner=25600, accepted=25000)
        self.treatment_rate = treatment_rate
        self.pending = 0
        self.reused = False
        self.throw_during_B = False
        self.signal_during_B = False
        self.reuse_during_B = False
        self.throw_after_set = False
        self.b_captures = 0
        self.capture_times = []

    def now(self):
        return self.clock

    def sleep(self, seconds):
        if len(self.current_mask) == 1 and self.signal_during_B:
            raise trial.TrialInterrupted("mock SIGTERM")
        self.clock += seconds
        steps = self.treatment_rate if len(self.current_mask) == 1 else 16
        self.counts["applied"] += int(seconds * steps)
        self.counts["frames"] += int(seconds * steps * 512)
        self.counts["learner"] += int(seconds * steps * 256)
        self.counts["accepted"] += int(seconds * steps * 250)

    def bindings(self):
        return copy.deepcopy(self.binding)

    def thread_identity(self, tid=None):
        value = copy.deepcopy(self.binding["worker"])
        if self.reused:
            value["thread"]["starttime_ticks"] += 1
        return value

    def mask(self, binding):
        return list(self.current_mask)

    def set_mask(self, binding, mask):
        if self.thread_identity() != binding:
            raise trial.GuardFailure("Identity changed")
        self.setter_calls.append(list(mask))
        self.current_mask = list(mask)
        if len(mask) == 1 and self.throw_after_set:
            raise OSError("mock affinity readback failure after application")

    def configure_logs(self, bindings):
        pass

    def verify(self, plan, mask):
        if self.thread_identity() != plan["bindings"]["worker"] or self.current_mask != mask:
            raise trial.GuardFailure("mock binding/affinity mismatch")

    def capture(self):
        self.capture_times.append(self.clock)
        if len(self.current_mask) == 1:
            self.b_captures += 1
            if self.throw_during_B:
                raise OSError("mock API unreachable")
            if self.reuse_during_B:
                self.reused = True
                raise OSError("mock TID replaced")
        applied = self.counts["applied"]
        optimizer = dict(enabled=True, available=not self.pending, process_id=self.pid,
            instance_monotonic_ns=100, epoch=1, total=dict(attempts_started=applied+self.pending,
            outcomes_recorded=applied, applied=applied, amp_skipped=0, unavailable=0),
            unclassified_started_total=self.pending, prior_epoch_outcomes_total=0)
        replay = dict(enabled=True, available=True, process_id=self.pid, instance_monotonic_ns=200,
            epoch=1, accepted_total=self.counts["accepted"], accepted_learner_total=self.counts["accepted"],
            accepted_by_source_total=dict(dqn=self.counts["accepted"], epsilon=0, expert=0, eval=0, unattributed=0))
        return dict(ts=1000+self.clock, observed_unix_s=1000+self.clock, observed_monotonic_s=self.clock,
            frame_count=self.counts["frames"], learner_frame_count=self.counts["learner"],
            optimized_samples=applied*4096, training_steps=applied, client_count=192,
            epsilon=.1, expert_ratio=.1, lr=2.5e-5, training_enabled=True, measurement_active=False,
            loss=1., grad_norm=.2, memory_buffer_size=6000000, pipeline_read_error=None,
            bank_persistence_read_error=None, exposure=dict(optimizer=optimizer, replay=replay),
            graphs=dict(ready=True, capture_count=128, validation_replay_count=640, postload_validations=1,
                runtime_capture_count=0, fallback_count=0, fatal_error=None, replay_count=applied),
            native=dict(enabled=True, available=True, completed_count=applied, success_count=applied,
                fallback_count=0, error_count=0), pipeline_errors=dict(inference=0,actor_refresh=0,target_refresh=0,learner_priority=0),
            bank=dict(backend="stream",stream_enabled=True,write_failures=0,last_error=None,output_errors=0,
                writes=int(self.clock >= 180),write_duration_s=10*int(self.clock >= 180),
                writer_active=150 <= self.clock < 210,snapshot_lock_max_ms=2.),
            csv=dict(replay_dropped=0,batch_size=4096,replay_sample_cap=8), log_errors=[],
            thread_sched=dict(migrations=int(self.clock*100), runtime_ns=int(self.clock*1e8),ready_wait_ns=0))


def plan_for(host, path):
    with patch.object(trial, "online_cpus", return_value=set(range(72))):
        result = trial.prepare(host, path)
    # Coarse deterministic clock advances keep tests small. Production CLI fixes
    # polling to one second; fixed durations and first endpoint remain unchanged.
    result["poll_s"] = 5
    return result


class AffinityTrialTests(unittest.TestCase):
    def test_default_cli_performs_no_writes_or_affinity_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/"new"
            with patch.object(trial, "Host", return_value=FakeHost()), \
                    patch.object(trial, "online_cpus", return_value=set(range(72))), \
                    patch.object(trial, "run_trial") as runner, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(trial.main(["--trainer-pid","109","--fleet-unit","fixture","--output-dir",str(out)]),0)
            runner.assert_not_called()
            self.assertFalse(out.exists())

    def test_one_pending_outcome_and_temporarily_unavailable_are_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            host = FakeHost();host.pending=1
            plan = plan_for(host, Path(directory)/"new")
            row = host.capture()
            self.assertEqual(trial.api_issues(row, plan), [])
            self.assertEqual(row["optimizer_pending"], 1)
            self.assertFalse(row["exposure"]["optimizer"]["available"])

    def test_unavailable_counter_bad_epoch_and_two_pending_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeHost();plan=plan_for(host,Path(directory)/"new")
            row=host.capture();row["exposure"]["optimizer"]["total"]["unavailable"]=1
            self.assertIn("unavailable_outcomes",trial.api_issues(row,plan))
            row=host.capture();row["exposure"]["replay"]["epoch"]+=1
            self.assertIn("exposure_identity:replay",trial.api_issues(row,plan))
            host.pending=2
            self.assertIn("optimizer_pending",trial.api_issues(host.capture(),plan))
            host.pending=0;row=host.capture();row["exposure"]["optimizer"]["available"]=False
            self.assertIn("optimizer_unavailable_without_inflight",trial.api_issues(row,plan))

    def test_full_trial_uses_fixed_windows_keeps_bank_event_and_restores(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeHost();out=Path(directory)/"new";plan=plan_for(host,out)
            result=trial.run_trial(host,plan)
            self.assertEqual(result["state"],"complete")
            self.assertEqual(result["decision"]["outcome"],"qualified")
            self.assertEqual([r["duration_s"] for r in result["results"]],[300,300,300])
            self.assertEqual(result["results"][0]["start"]["observed_monotonic_s"],90)
            self.assertEqual(result["results"][0]["bank_events"]["writes"],1)
            self.assertGreater(result["results"][0]["bank_events"]["writer_active_observations"],0)
            self.assertEqual(host.current_mask,list(range(72)))
            self.assertEqual(host.setter_calls,[[71],list(range(72))])
            self.assertEqual((out/"precommit.json").stat().st_mode & 0o777,0o444)
            observations=[json.loads(line) for line in (out/"observations.jsonl").read_text().splitlines()]
            self.assertEqual(len(observations),3*79)
            self.assertTrue(all(not row["issues"] for row in observations))

    def test_primary_endpoint_is_first_observation_after_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeHost();plan=plan_for(host,Path(directory)/"new");plan["poll_s"]=7
            result=trial.run_trial(host,plan)
            for phase in result["results"]:
                self.assertEqual(phase["duration_s"],301)
                self.assertEqual(phase["start"]["stage"],"primary")
                self.assertLess(phase["duration_s"]-7,300)

    def test_no_improvement_is_rejected_without_changing_final_affinity(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeHost(treatment_rate=16);plan=plan_for(host,Path(directory)/"new")
            result=trial.run_trial(host,plan)
            self.assertEqual(result["decision"]["outcome"],"rejected")
            self.assertFalse(result["decision"]["automatic_promotion"])
            self.assertEqual(host.current_mask,list(range(72)))

    def test_api_exception_after_pinning_restores_original_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeHost();out=Path(directory)/"new";plan=plan_for(host,out);host.throw_during_B=True
            with self.assertRaisesRegex(OSError,"API unreachable"):
                trial.run_trial(host,plan)
            self.assertEqual(host.setter_calls,[[71],list(range(72))])
            status=json.loads((out/"status.json").read_text())
            self.assertEqual(status["state"],"failed");self.assertTrue(status["restoration"]["restored"])

    def test_signal_after_pinning_restores_original_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeHost();out=Path(directory)/"new";plan=plan_for(host,out);host.signal_during_B=True
            with self.assertRaises(trial.TrialInterrupted):trial.run_trial(host,plan)
            self.assertEqual(host.current_mask,list(range(72)))
            self.assertEqual(json.loads((out/"status.json").read_text())["state"],"interrupted")

    def test_reused_thread_is_never_given_old_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeHost();out=Path(directory)/"new";plan=plan_for(host,out);host.reuse_during_B=True
            with self.assertRaises(OSError):trial.run_trial(host,plan)
            self.assertEqual(host.setter_calls,[[71]])
            status=json.loads((out/"status.json").read_text())
            self.assertFalse(status["restoration"]["restored"])

    def test_failure_after_actual_set_but_before_readback_still_restores(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeHost();plan=plan_for(host,Path(directory)/"new");host.throw_after_set=True
            with self.assertRaises(OSError):trial.run_trial(host,plan)
            self.assertEqual(host.current_mask,list(range(72)))

    def test_native_setter_checks_identity_before_any_syscall(self):
        host=trial.Host(109,"fixture");binding=FakeHost().binding["worker"]
        reused=copy.deepcopy(binding);reused["trainer"]["starttime_ticks"]+=1
        with patch.object(host,"thread_identity",return_value=reused),patch.object(trial.os,"sched_setaffinity") as setter:
            with self.assertRaises(trial.GuardFailure):host.set_mask(binding,[71])
        setter.assert_not_called()

    def test_log_guard_ignores_old_errors_but_catches_split_new_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"actor.log";path.write_text("Traceback old\n");s=path.stat()
            host=trial.Host(109,"fixture");host.configure_logs({str(path):dict(device=s.st_dev,inode=s.st_ino)})
            self.assertEqual(host.log_errors(),[])
            with path.open("a") as stream:stream.write("[SOCKET ACTION ")
            self.assertEqual(host.log_errors(),[])
            with path.open("a") as stream:stream.write("TIMEOUT] new\n")
            self.assertEqual(host.log_errors()[0]["marker"],"[SOCKET ACTION TIMEOUT]")

    def test_missing_or_offline_cpu_and_existing_output_refused_without_setter(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeHost();out=Path(directory)/"new"
            with patch.object(trial,"online_cpus",return_value={0,1}):
                with self.assertRaisesRegex(trial.GuardFailure,"online"):trial.prepare(host,out)
            self.assertEqual(host.setter_calls,[]);out.mkdir()
            with self.assertRaisesRegex(trial.GuardFailure,"must be new"):trial.prepare(host,out)

    def test_signal_handler_raises_and_restores_previous_handler(self):
        handlers={sig:object() for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)};registered={}
        def register(sig,fn):registered[sig]=fn
        with patch.object(trial.signal,"getsignal",side_effect=lambda sig:handlers[sig]), \
                patch.object(trial.signal,"signal",side_effect=register):
            with trial.interrupt_handlers():
                with self.assertRaises(trial.TrialInterrupted):registered[signal.SIGTERM](signal.SIGTERM,None)
        self.assertEqual(registered,handlers)


if __name__=="__main__":unittest.main()
