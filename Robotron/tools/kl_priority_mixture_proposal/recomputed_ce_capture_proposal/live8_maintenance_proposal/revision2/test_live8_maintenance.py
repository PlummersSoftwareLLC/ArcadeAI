"""Authored CPU/stdlib-only contracts; author has not imported or executed them."""
from contextlib import nullcontext
import copy
import io
import json
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import run_live8_maintenance as tool


class FakeHost:
    def __init__(self, runtime):
        self.r = runtime
        self.paused, self.events = [], []
        self.pid, self.owned, self.dropin_expected = 10, 10, None
        self.known_trainer = dict(pid=10)
        self.stop_calls = 0

    def unit(self, name):
        return dict(MainPID=str(self.pid), ActiveState="active" if self.pid else "failed" if self.r.failed_pid0_state else "inactive")

    def signal_actor(self, actor, signum):
        self.events.append((signum, actor["pid"]))
        if signum == signal.SIGCONT and actor["pid"] in self.r.resume_fail:
            raise RuntimeError("exact actor identity was reused")
        if signum == signal.SIGSTOP and actor["pid"] == self.r.repause_fail and any(x[0] == signal.SIGCONT for x in self.events):
            raise RuntimeError("partial second pause")

    def pause(self, plan):
        for actor in plan["initial"]["bindings"]["actors"]:
            self.paused.append(actor)
            self.signal_actor(actor, signal.SIGSTOP)
            if actor["pid"] == self.r.pause_fail:
                raise KeyboardInterrupt("partial pause signal")

    def wait_paused(self):
        self.events.append(("all_stopped", len(self.paused)))

    def begin_transition_logs(self, *args):
        self.events.append(("arm_logs", self.pid))

    def stop(self, expected=None):
        tool.require(self.pid == self.owned, "unknown replacement")
        self.events.append(("stop", self.pid))
        self.stop_calls += 1
        self.pid = 0

    def write_dropin(self, data, expected, mode=0o644):
        tool.require(self.dropin_expected == expected, "foreign override")
        self.dropin_expected = data
        self.events.append(("dropin", data))


class FakeSources:
    def __init__(self, runtime):
        self.r, self.phase, self.reconciles = runtime, "before", []

    def stage(self):
        if self.r.stage_fail:
            raise RuntimeError("base drift")

    def reconcile(self, phase, absent, blocked):
        absent()
        self.reconciles.append(phase)
        if phase == "after" and self.r.install_fail:
            self.phase = "known_partial"
            raise OSError("partial known source install")
        self.phase = phase


class FakeRuntime:
    def __init__(self, directory):
        self.pause_fail, self.repause_fail, self.resume_fail = None, None, set()
        self.stage_fail = self.install_fail = self.capture_fail = self.unknown = False
        self.missing_recovery_bank = self.pid0_start = self.initial_cpu_fail = False
        self.failed_pid0_state = False
        self.mark_failed_on_start = False
        self.verification_failed = False
        self.output = directory
        self.job = dict(trainer_unit="trainer", experiment="held", model_dir=str(directory), bank_spec={},
            original_dropin=dict(mode=None), before=dict(bindings=dict(actors=[dict(pid=i) for i in (1,2,3)], logs={}), trainer_stdout={}))
        self.host = FakeHost(self)
        self.metrics = SimpleNamespace(block_restore_signals=nullcontext)
        self.banks = SimpleNamespace(stopped_state=lambda spec:dict(banks="both_generation_headers"))
        self.insured = dict(pid=10)
        self.last_retired = None
        self.current_checkpoint = None
        self.original_dropin, self.dropin, self.recovery_dropin, self.phase, self.lineages = None, b"capture", b"normal-no-auto-restart", "before", {}
        self.checkpoints, self.starts, self.proofs = [], [], []
        self.latest = directory / "latest"
        self.latest.write_bytes(b"persisted-newest")

    def initial(self):
        return self.job["before"]

    def trainer_id(self):
        tool.require(self.host.pid == self.host.owned and self.host.pid > 0, "unknown replacement")
        return dict(pid=self.host.pid)

    def absence(self):
        tool.require(self.host.pid == 0, "old trainer is still live")
        tool.require(self.host.unit("trainer")["ActiveState"] == "inactive", "failed unit needs manual recovery")

    def stopped_checkpoint(self, retired, label):
        self.absence()
        self.checkpoints.append((retired["pid"], label))
        if self.initial_cpu_fail:
            self.verification_failed = True
            raise RuntimeError("nonfinite stopped latest")
        self.last_retired = retired
        self.current_checkpoint = dict(source=tool.fingerprint(self.latest))
        return self.current_checkpoint

    def start(self, phase, label):
        self.absence()
        self.starts.append(phase)
        if phase == "after" and self.pid0_start:
            self.host.known_trainer = None
            self.failed_pid0_state = self.mark_failed_on_start
            raise RuntimeError("requested start failed with PID0")
        self.host.owned = 20 if phase == "after" else 30
        self.host.pid = 999 if self.unknown and phase == "after" else self.host.owned
        self.host.known_trainer = dict(pid=self.host.owned)
        self.phase = phase

    def ready(self, phase, banks, *, actors):
        self.trainer_id()
        if phase == "before" and self.missing_recovery_bank:
            raise RuntimeError("missing positive bank startup pair")
        if phase == "after" and self.capture_fail:
            return dict(phase=phase, actors=actors)
        self.proofs.append((phase, actors, bool(self.host.paused)))
        return dict(phase=phase, actors=actors)

    def fault_scan(self):
        return []

    def capture_complete(self):
        if self.capture_fail:
            raise RuntimeError("observer INVALID; no ninth")
        return dict(first8=True)


class MaintenanceContracts(unittest.TestCase):
    def fixture(self, **flags):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        runtime = FakeRuntime(Path(directory.name))
        for key, value in flags.items():
            setattr(runtime, key, value)
        sources = FakeSources(runtime)
        events = []
        operation = tool.Maintenance(runtime, sources, events.append)
        return operation, runtime, sources, events

    def test_literal_default_reads_nothing_and_imports_no_runtime(self):
        with patch.object(tool, "read_job", side_effect=AssertionError("read")), patch.object(tool, "Runtime", side_effect=AssertionError("import")), patch("sys.stdout", new=io.StringIO()) as stdout:
            self.assertEqual(tool.main([]), 0)
        self.assertIn("PLAN_ONLY", stdout.getvalue())

    def test_full_sequence_has_bank_proof_before_resume_and_one_capture_boot(self):
        op, r, sources, events = self.fixture()
        result, error = op.run()
        self.assertIsNone(error)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertFalse(result["manual_recovery_required"])
        self.assertEqual(r.starts, ["after"])
        self.assertEqual(r.proofs, [("after", False, True), ("after", True, False)])
        self.assertEqual([x["phase"] for x in events], ["precommit_verified", "stopped", "stopped_disk_state", "loaded_before_resume", "main192_ready", "terminal"])
        self.assertEqual(sources.phase, "after")
        self.assertIsNone(r.host.dropin_expected)

    def test_partial_pause_signal_attempts_every_registered_actor_without_stop(self):
        op, r, _, _ = self.fixture(pause_fail=2)
        result, error = op.run()
        self.assertIsInstance(error, KeyboardInterrupt)
        self.assertEqual(r.host.stop_calls, 0)
        self.assertEqual([pid for sig,pid in r.host.events if sig == signal.SIGCONT], [1,2])
        self.assertFalse(r.host.paused)

    def test_resume_reused_actor_does_not_block_other_exact_actors(self):
        op, r, _, _ = self.fixture(resume_fail={2})
        result, _ = op.run()
        self.assertTrue(result["manual_recovery_required"])
        resumed = [pid for sig,pid in r.host.events if sig == signal.SIGCONT]
        self.assertIn(1, resumed); self.assertIn(2, resumed); self.assertIn(3, resumed)
        self.assertEqual(result["status"], "FAILED")

    def test_failed_resume_suffix_survives_later_partial_repause_and_final_undo(self):
        op, r, _, _ = self.fixture(resume_fail={3}, repause_fail=2)
        result, _ = op.run()
        self.assertEqual(result["initial_resume"]["failures"][0]["pid"], 3)
        self.assertTrue(result["manual_recovery_required"])
        resumed = [pid for sig,pid in r.host.events if sig == signal.SIGCONT]
        self.assertEqual(resumed, [1,2,3,3,1,2])
        self.assertEqual([actor["pid"] for actor in r.host.paused], [3])

    def test_partial_known_install_restores_whole_before_and_never_boots_mixture(self):
        op, r, sources, _ = self.fixture(install_fail=True)
        result, _ = op.run()
        self.assertEqual(sources.reconciles, ["after", "before"])
        self.assertEqual(sources.phase, "before")
        self.assertEqual(r.starts, ["before"])
        self.assertIn("recovery_boot", result)
        self.assertFalse(result["manual_recovery_required"])
        self.assertEqual(r.checkpoints, [(10,"initial-stopped")])

    def test_unknown_new_pid_is_never_stopped_adopted_or_restarted(self):
        op, r, _, _ = self.fixture(unknown=True)
        result, _ = op.run()
        self.assertEqual(r.host.stop_calls, 1)  # Initial known trainer only.
        self.assertEqual(r.starts, ["after"])
        self.assertTrue(result["manual_recovery_required"])
        self.assertEqual([pid for sig,pid in r.host.events if sig == signal.SIGCONT], [1,2,3])

    def test_initial_control_or_base_drift_causes_no_pause_or_stop(self):
        for location in ("control", "base"):
            with self.subTest(location=location):
                op, r, _, _ = self.fixture(stage_fail=location == "base")
                if location == "control":
                    r.initial = lambda: (_ for _ in ()).throw(RuntimeError("control drift"))
                result, _ = op.run()
                self.assertEqual(result["status"], "FAILED")
                self.assertEqual(r.host.events, [])
                self.assertEqual(r.starts, [])

    def test_failed_checkpoint_is_not_retried_and_never_boots_insurance(self):
        op, r, _, _ = self.fixture(initial_cpu_fail=True)
        result, _ = op.run()
        self.assertTrue(result["manual_recovery_required"])
        self.assertEqual(r.checkpoints, [(10,"initial-stopped")])
        self.assertEqual(r.starts, [])
        self.assertEqual([pid for sig,pid in r.host.events if sig == signal.SIGCONT], [1,2,3])

    def test_failed_pid0_start_can_recover_unchanged_latest_without_none_dereference(self):
        op, r, sources, _ = self.fixture(pid0_start=True)
        result, _ = op.run()
        self.assertEqual(r.starts, ["after", "before"])
        self.assertFalse(result["manual_recovery_required"])
        self.assertEqual(sources.phase, "before")

    def test_after_resume_capture_fault_repauses_and_verifies_newest_forward_save(self):
        op, r, sources, _ = self.fixture(capture_fail=True)
        result, _ = op.run()
        self.assertEqual(r.starts, ["after", "before"])
        self.assertEqual(r.checkpoints, [(10,"initial-stopped"), (20,"recovery-stopped")])
        self.assertEqual(sources.phase, "before")
        second_stop = r.host.events.index(("stop",20))
        self.assertEqual(r.host.events[second_stop-1], ("all_stopped",3))
        self.assertFalse(result["manual_recovery_required"])

    def test_failed_active_state_pid0_is_manual_without_reset_stop_or_untracked_boot(self):
        op, r, sources, _ = self.fixture(pid0_start=True,mark_failed_on_start=True)
        result, _ = op.run()
        self.assertTrue(result["manual_recovery_required"])
        self.assertEqual(r.starts,["after"])
        self.assertEqual(r.host.stop_calls,1)
        self.assertEqual(sources.phase,"after")
        self.assertEqual([pid for sig,pid in r.host.events if sig == signal.SIGCONT],[1,2,3])

    def test_recovery_missing_banks_still_resumes_all_and_requires_manual(self):
        op, r, _, _ = self.fixture(install_fail=True, missing_recovery_bank=True)
        result, _ = op.run()
        self.assertTrue(result["manual_recovery_required"])
        self.assertNotIn("recovery_boot", result)
        self.assertEqual([pid for sig,pid in r.host.events if sig == signal.SIGCONT], [1,2,3])

    def test_journal_failure_does_not_prevent_owned_source_recovery_or_actor_undo(self):
        op, r, sources, _ = self.fixture()
        def broken(value):
            if value["phase"] in ("stopped_disk_state", "terminal"):
                raise OSError("disk full")
        op.emit = broken
        result, error = op.run()
        self.assertIsInstance(error, OSError)
        self.assertEqual(sources.phase, "before")
        self.assertIn("recovery_boot", result)
        self.assertTrue(result["manual_recovery_required"])
        self.assertEqual([pid for sig,pid in r.host.events if sig == signal.SIGCONT], [1,2,3])


class SourceTransactionContracts(unittest.TestCase):
    def fixture(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        directory = Path(root.name); (directory/"archive").mkdir()
        entries = []
        for index in range(2):
            before, after = directory/("old%d"%index), directory/("new%d"%index)
            before.write_bytes(b"before"); after.write_bytes(b"after")
            entries.append(dict(destination=str(before), before=tool.fingerprint(before), after=tool.fingerprint(after)))
        sources = tool.Sources(entries, directory/"archive")
        sources.stage()
        return directory, sources

    def test_unknown_partial_source_is_manual_and_no_known_file_is_overwritten(self):
        directory, sources = self.fixture()
        (directory/"old1").write_bytes(b"external mutation")
        with self.assertRaisesRegex(RuntimeError,"Unknown source"):
            sources.reconcile("after", lambda:None, nullcontext)
        self.assertEqual((directory/"old0").read_bytes(), b"before")

    def test_partial_atomic_install_is_reconciled_to_complete_known_before(self):
        directory, sources = self.fixture()
        original_replace = tool.os.replace
        calls = []
        def fail_second(src,dst):
            calls.append(str(dst))
            if len(calls) == 2:
                raise OSError("injected write failure")
            return original_replace(src,dst)
        with patch.object(tool.os,"replace",side_effect=fail_second):
            with self.assertRaises(OSError):
                sources.reconcile("after",lambda:None,nullcontext)
        self.assertEqual((directory/"old0").read_bytes(),b"after")
        sources.reconcile("before",lambda:None,nullcontext)
        sources.check("before")

    def test_source_temp_write_failure_cleans_only_own_temp_and_does_not_block_restore(self):
        directory, sources = self.fixture()
        original_fdopen = tool.os.fdopen
        class FailedWriter:
            def __init__(self, stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def write(self,data):raise OSError("injected source write")
        def broken(fd,mode):
            return FailedWriter(original_fdopen(fd,mode))
        with patch.object(tool.os,"fdopen",side_effect=broken):
            with self.assertRaisesRegex(OSError,"injected source write"):
                sources.reconcile("after",lambda:None,nullcontext)
        self.assertEqual(list(directory.glob(".live8-maintenance-*")),[])
        sources.reconcile("before",lambda:None,nullcontext)
        sources.check("before")

    def test_known_new_observer_is_removed_on_before_reconciliation_but_unknown_is_not(self):
        root = tempfile.TemporaryDirectory();self.addCleanup(root.cleanup)
        directory=Path(root.name);(directory/"archive").mkdir()
        overlay=directory/"overlay";overlay.write_bytes(b"observer")
        destination=directory/"observer.py"
        sources=tool.Sources([dict(destination=str(destination),before=None,after=tool.fingerprint(overlay))],directory/"archive")
        sources.stage();sources.reconcile("after",lambda:None,nullcontext)
        self.assertEqual(destination.read_bytes(),b"observer")
        sources.reconcile("before",lambda:None,nullcontext)
        self.assertFalse(destination.exists())
        destination.write_bytes(b"external")
        with self.assertRaisesRegex(RuntimeError,"Unknown source"):
            sources.reconcile("before",lambda:None,nullcontext)
        self.assertEqual(destination.read_bytes(),b"external")

    def test_source_install_cannot_run_when_old_trainer_is_live(self):
        directory, sources = self.fixture()
        with self.assertRaisesRegex(RuntimeError,"alive"):
            sources.reconcile("after",lambda:(_ for _ in ()).throw(RuntimeError("alive")),nullcontext)
        sources.check("before")

    def test_control_source_and_environment_comparison_rejects_extra_drift(self):
        initial = dict(unit_files={"trainer":{}},fleet=dict(MainPID="2"),supervisor_start_ticks=3,trainer_stdout={},
            bindings=dict(actors=[1],fleet_cgroup="fleet",control_hashes={"control":"old"},logs={},source_hashes={"loss":"same"}),environment={"DQN_A":"1"})
        for category in ("control", "loss", "environment", "unit"):
            with self.subTest(category=category):
                current = copy.deepcopy(initial)
                if category == "control":current["bindings"]["control_hashes"]["control"]="new"
                if category == "loss":current["bindings"]["source_hashes"]["loss"]="new"
                if category == "environment":current["environment"]["DQN_A"]="2"
                if category == "unit":current["unit_files"]["trainer"]["foreign"]="new"
                with self.assertRaises(RuntimeError):
                    tool.binding_matches(current,initial,initial["bindings"]["source_hashes"],initial["environment"])


class RetainedCaptureContracts(unittest.TestCase):
    def row(self):
        point = dict(current=True, lease_epoch=7, owner_epoch_at_consumption=7)
        return dict(index=1,capture_complete=True,observer_errors=[],optimizer_outcome="amp_skipped",
            draw_batch_join_checked=True,staged_draw_join_checked=True,draw_capture_id="authentic",
            prefetch=dict(**point,sample_ms=1.25,stage_host_ms=.7),
            prefetch_begin=dict(point),prefetch_pre_loss=dict(point),prefetch_exit=dict(point))

    def test_real_five_key_prefetch_and_three_key_checkpoints_are_valid(self):
        row = self.row()
        tool.capture_row_checks(row,1,copy.deepcopy(row),"authentic")

    def test_reused_epoch_or_wrong_draw_or_substitute_outcome_are_rejected(self):
        for kind in ("epoch","draw","unavailable","ninth"):
            with self.subTest(kind=kind):
                row = self.row()
                if kind == "epoch":row["prefetch_exit"]["owner_epoch_at_consumption"]=8
                if kind == "draw":row["draw_capture_id"]="other"
                if kind == "unavailable":row["optimizer_outcome"]="unavailable"
                if kind == "ninth":row["index"]=9
                with self.assertRaises(RuntimeError):
                    tool.capture_row_checks(row,1,copy.deepcopy(row),"authentic")

    def test_exact_latest_boot_pair_required_and_expected_support_message_allowed(self):
        path = "/game/models_dqn/robotron_dqn_latest.pt"
        good = ("Partial load (missing=1, unexpected=0)\nLoaded v28 model from %s\nLoaded model from: %s\n" % (path,path)).encode()
        self.assertEqual(tool.boot_log_proof(good,path)["agent_load_paths"],[path])
        for raw in (b"",good.replace(path.encode(),b"/protected/winner.pt"),good+good,
                    good+b"[RECOMPUTED CE CAPTURE INVALID]\n"):
            with self.subTest(raw=raw):
                with self.assertRaises(RuntimeError):tool.boot_log_proof(raw,path)

    def test_first_completed_real_shaped_pre_clocks_equal_saved_latest_even_for_amp_skip(self):
        row=self.row()
        row["before"]=dict(training_steps=2042467,optimized_samples=6918356992,last_target_update_samples=1,learning_rates=[2.5e-5])
        row["frame_context"]=dict(frame_count=846584430,learner_frame_count=423154160,measurement_frame_count=0)
        saved=dict(training_steps=2042467,optimized_samples=6918356992,frame_count=846584430,learner_frame_count=423154160)
        proof=tool.first_attempt_clock_proof(row,saved,"authentic")
        self.assertEqual(proof["observed"],saved)
        self.assertEqual(proof["optimizer_outcome"],"amp_skipped")
        for key in tool.CLOCKS:
            changed=copy.deepcopy(row)
            target=changed["before"] if key in ("training_steps","optimized_samples") else changed["frame_context"]
            target[key]+=1
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError,"PRE four clocks"):
                tool.first_attempt_clock_proof(changed,saved,"authentic")


class HeldBootDefaultContracts(unittest.TestCase):
    def fixture(self):
        root="/source/Robotron";model=root+"/models_dqn"
        env=dict(DQN_RATCHET="0",DQN_EXACT_GRAPH_CHECKPOINT=model+"/robotron_dqn_latest.pt")
        sources={root+"/Scripts/dqn/config.py":tool.BOOT_CONFIG_SHA256}
        return env,root,model,sources

    def test_absent_held_env_uses_only_exact_pinned_config_default_without_mutating_it(self):
        env,root,model,sources=self.fixture()
        before=copy.deepcopy(env)
        proof=tool.held_boot_paths(env,root,model,sources)
        self.assertEqual(proof["model_dir"],model)
        self.assertEqual(proof["path_source"],"pinned_config_default")
        self.assertEqual(env,before)
        env["ROBOTRON_DQN_MODEL_DIR"]=model
        self.assertEqual(tool.held_boot_paths(env,root,model,sources)["path_source"],"explicit_environment")

    def test_wrong_explicit_modeldir_or_graphcheckpoint_or_ratchet_rejected(self):
        for key,value in (("ROBOTRON_DQN_MODEL_DIR","/other/models"),("DQN_EXACT_GRAPH_CHECKPOINT","/protected/winner.pt"),("DQN_RATCHET","1")):
            with self.subTest(key=key):
                env,root,model,sources=self.fixture();env[key]=value
                with self.assertRaises(RuntimeError):tool.held_boot_paths(env,root,model,sources)

    def test_missing_or_changed_default_source_and_wrong_declared_default_fail_closed(self):
        env,root,model,sources=self.fixture()
        for changed in ({},{root+"/Scripts/dqn/config.py":"0"*64}):
            with self.subTest(changed=changed),self.assertRaisesRegex(RuntimeError,"exact held config"):
                tool.held_boot_paths(env,root,model,changed)
        with self.assertRaisesRegex(RuntimeError,"model directory differs"):
            tool.held_boot_paths(env,root,"/other/models",sources)


if __name__ == "__main__":
    unittest.main()
