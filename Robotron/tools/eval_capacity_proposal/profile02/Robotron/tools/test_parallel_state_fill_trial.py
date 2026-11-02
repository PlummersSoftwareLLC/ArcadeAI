"""No real services, signals, affinity, drop-ins, GPUs, or trainer restarts."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import signal
import tempfile
import types
import unittest
from unittest.mock import patch

from . import parallel_state_fill_trial as trial
from .test_inference_worker_affinity import FakeHost as MetricFixture


TRAINER="robotron-managed-fixture-x-trainer.service"
FLEET="robotron-managed-fixture-x-fleet.service"

# Actual production print forms from agent/replay and their main-loop callers.
# Neither broad WARN nor normal support-only Partial load is a failure marker.
RECIPE_PERSISTENCE_FAILURE_LINES=(
    "[WARN] compiled inference failed (RuntimeError: mock) — falling back to eager",
    "[WARN] disabling torch.compile for training after error — falling back to eager",
    "  [WARN] replay live-mmap init failed: mock",
    "Optimizer state skipped: mock",
    "GradScaler state skipped: mock",
    "  Optimizer state absent/stale — armed 8,000-step LR warmup",
    "⚠  Incompatible checkpoint engine version — starting fresh.",
    "  Replay buffer skipped — checkpoint state shape differs from current frame stack.",
    "  No replay buffer found — starting with empty buffer.",
    "  Replay buffer load failed: mock",
    "  [WARN] Backup copy failed: mock",
    "  [WARN] HOF load failed: mock",
    "  [WARN] EpHOF load failed: mock",
    "[BANKS] background HOF save failed: mock",
    "[BANKS] background EPHOF save failed: mock",
    "  HOF load skipped: stride/state_size mismatch with config",
    "  EPHOF load skipped: stride/state_size mismatch with config",
    "  Failed to read replay meta: mock",
    "  Missing array file: states.npy",
    "  [WARN] live-mmap backing unavailable (mock) — using RAM arrays",
    "  [WARN] live-mmap promotion failed (mock) — saves remain full-copy",
    "  Replay mmap adoption skipped: mock",
    "  Failed to read replay buffer: mock",
    "  Replay buffer file is empty.",
    "  Replay buffer is empty — nothing to save.",
    "  State size mismatch: saved=1, expected=11128",
    "  Saved buffer (7,000,000) exceeds capacity (6,000,000), truncating to most recent.",
    "  Pruned legacy interesting flags: 4,000,000 -> 1,800,000",
    "  Replay buffer flushed.",
    "Model load failed/incompatible, starting fresh",
    "No model found, starting fresh",
    "[BANKS] periodic save failed: mock",
    "  [WARN] Best-checkpoint save failed: mock",
    "  [WARN] peak archive failed: mock",
    "[MANAGED CHECKPOINT] rejected request: mock",
)


class FakeLive(MetricFixture):
    trainer_unit=TRAINER
    fleet_unit=FLEET

    def __init__(self):
        super().__init__()
        self.pid=200
        self.flag="0"
        self.configured_flag="0"
        self.active=True
        self.paused=[]
        self.pause_issues=[]
        self.restart_in_progress=False
        self.dropin_expected=None
        self.events=[]
        self.generation=1
        self.actor_states={n:dict(ticks=n+1000,stopped=False) for n in range(1,5)}
        self.partial_pause=False
        self.fail_B_start=False
        self.hung=False
        self.signal_in_B=False
        self.stall_route=False
        self.runtime_fault_B=False
        self.runtime_fault_A_marker=None
        self.extra_env={}
        self.metric_host=types.SimpleNamespace(configure_logs=lambda _:None)

    def no_sidecars(self):pass

    def describe(self):
        binding=copy.deepcopy(self.binding)
        binding.update(actors=[dict(pid=n,starttime_ticks=n+1000,client_slot=n-1) for n in range(1,5)],
            fleet_cgroup="/owned/fleet",source_hashes={"source":"fixed"},control_hashes={"control":"fixed"},logs={})
        binding["worker"]=dict(trainer=dict(pid=self.pid,starttime_ticks=self.pid+10000),
                               thread=dict(tid=self.pid+1,starttime_ticks=self.pid+10001))
        value=dict(trainer=dict(MainPID=str(self.pid) if self.active else "0"),fleet=dict(MainPID="77"),
            supervisor_start_ticks=999,bindings=binding,unit_files={"trainer":"same","fleet":"same"},
            environment={"DQN_BATCH_SIZE":"4096",trial.FLAG:self.flag,**self.extra_env},
            trainer_stdout=dict(path='/mock/trainer.out',device=1,inode=2))
        self.current=value
        return copy.deepcopy(value)

    verify=trial.LiveHost.verify
    pause=trial.LiveHost.pause
    resume=trial.LiveHost.resume
    def wait_paused(self):
        if not all(self.actor_states[actor["pid"]]["stopped"] for actor in self.paused):
            raise trial.metrics.GuardFailure("mock missing pause acknowledgement")

    def signal_actor(self,actor,signum):
        current=self.actor_states[actor["pid"]]
        if current["ticks"]!=actor["starttime_ticks"]:raise trial.metrics.GuardFailure("reused actor")
        if self.partial_pause and signum==signal.SIGSTOP and actor["pid"]==3:
            raise OSError("mock partial pause")
        self.events.append(("signal",actor["pid"],signum))
        current["stopped"]=signum==signal.SIGSTOP

    def begin_transition_logs(self,bindings,trainer_stdout=None):self.events.append(("arm_transition",))
    def bank_load_proof(self,current):
        self.events.append(('bank_load_proof',))
        if not self.paused or not all(actor['stopped'] for actor in self.actor_states.values()):
            raise trial.metrics.GuardFailure('mock actors resumed before bank proof')
        return dict(counts={bank:dict(episodes=192,transitions=100000) for bank in ('HOF','EPHOF')})
    def transition_log_events(self):return [dict(marker="mock deliberate restart closure",intentional_restart_compatible=True)]

    def stop(self,expected=None):
        self.events.append(("stop",self.flag));self.restart_in_progress=True
        if self.hung:raise trial.metrics.GuardFailure("old trainer still alive")
        self.active=False

    def write_dropin(self,data,expected,mode=0o644):
        if expected!=self.dropin_expected:raise trial.metrics.GuardFailure("external drop-in change")
        self.events.append(("dropin",data));self.dropin_expected=data
        self.configured_flag="1" if data and data.endswith(b"=1\n") else "0"

    def start(self):
        if self.active:raise trial.metrics.GuardFailure("refuse duplicate trainer")
        self.events.append(("start",self.configured_flag));self.flag=self.configured_flag
        self.pid+=10;self.generation+=1;self.active=True
        self.counts=dict(applied=100,frames=51200,learner=25600,accepted=25000)

    def ready(self,plan,flag,actors=False):
        if flag=="1" and self.fail_B_start:
            self.active=False
            raise trial.metrics.GuardFailure("failed startup with PID0")
        if actors:self.restart_in_progress=False
        return self.verify(plan,flag)

    def serial_running(self,plan):return self.active and self.flag=="0"

    def unit(self,name):return dict(MainPID=str(self.pid) if self.active else "0",ActiveState="active" if self.active else "inactive")

    def sleep(self,seconds):
        if self.flag=="1" and self.signal_in_B:raise trial.metrics.TrialInterrupted("mock SIGTERM")
        self.clock+=seconds
        rate=18 if self.flag=="1" else 16
        for key,scale in (("applied",1),("frames",512),("learner",256),("accepted",250)):
            self.counts[key]+=int(seconds*rate*scale)

    def capture(self):
        row=super().capture()
        row["exposure"]["optimizer"].update(instance_monotonic_ns=self.pid*1000,epoch=self.generation)
        row["exposure"]["replay"].update(instance_monotonic_ns=self.pid*1000+1,epoch=self.generation)
        row["parallel_state_fill"]=dict(requested=self.flag=="1",native_available=True,
            executor_created=self.flag=="1",closed=False,
            completed_batches=(100 if self.stall_route else self.counts["applied"]) if self.flag=="1" else 0)
        if self.flag=="1" and self.runtime_fault_B:row["log_errors"]=[dict(marker="Traceback")]
        if self.flag=="0" and self.runtime_fault_A_marker:row["log_errors"]=[dict(marker=self.runtime_fault_A_marker)]
        return row


def fake_plan(host,path):
    return dict(schema=trial.SCHEMA,output_directory=str(path),initial=host.describe(),
        original_dropin=dict(content_base64=None,mode=None),batch_size=4096,replay_cap=8,
        settle_s=90,window_s=300,poll_s=5,binding_check_s=30,
        gates=dict(applied_rate_ratio=1.05,accepted_learner_rate_ratio=1.,amp_skip_fraction_allowance=.001,SPF_min=7.6,SPF_max=8.4))


class ParallelTrialTests(unittest.TestCase):
    def run_fake(self,host,out):
        with patch.object(trial,"check_static"),patch.object(trial.metrics.os,"sched_setaffinity") as affinity:
            result=trial.run(host,fake_plan(host,out))
            affinity.assert_not_called()
            return result

    def test_equivalent_three_restarts_full_windows_epochs_and_restoration(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeLive();out=Path(directory)/"new";result=self.run_fake(host,out)
            self.assertEqual(result["decision"]["outcome"],"qualified")
            self.assertEqual([e for e in host.events if e[0]=="stop"],[("stop","0"),("stop","0"),("stop","1")])
            self.assertEqual([e for e in host.events if e[0]=="start"],[("start","0"),("start","1"),("start","0")])
            self.assertEqual([r["duration_s"] for r in result["results"]],[300,300,300])
            self.assertEqual(len({r["start"]["exposure"]["optimizer"]["process_id"] for r in result["results"]}),3)
            self.assertEqual(result["results"][0]["bank_events"]["writes"],1)
            self.assertIsNone(host.dropin_expected)
            self.assertTrue(result["recovery"]["original_dropin_restored"])
            self.assertTrue(all(not a["stopped"] for a in host.actor_states.values()))
            self.assertTrue(all(t["log_events"] for t in result["transitions"]))

    def test_normal_inflight_step_is_retained_and_not_a_fault(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeLive();host.pending=1
            result=self.run_fake(host,Path(directory)/"new")
            self.assertEqual(result["results"][1]["start"]["optimizer_pending"],1)
            self.assertEqual(result["decision"]["outcome"],"qualified")

    def test_default_cli_never_launches_or_creates_output(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/"new"
            with patch.object(trial,"prepare",return_value=dict(schema=trial.SCHEMA)),patch.object(trial,"run") as run,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(trial.main(["--trainer-unit",TRAINER,"--fleet-unit",FLEET,"--quality-campaign",directory,"--recovery-checkpoint",directory,"--output-dir",str(out)]),0)
            run.assert_not_called();self.assertFalse(out.exists())

    def test_completed_older_quality_campaign_cannot_satisfy_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            host=trial.LiveHost(TRAINER,FLEET)
            review=dict(assessment=dict(outcome="not_improved"),checkpoints=dict(candidate=dict(
                source=str(trial.metrics.GAME/"models_dqn/managed-checkpoints/fresh3-227M.pt"),sha256="old")))
            with patch.object(trial.protection,"review",return_value=review),patch.object(host,"describe") as describe:
                with self.assertRaisesRegex(trial.metrics.GuardFailure,"intended completed 256M"):
                    trial.prepare(host,Path(directory)/"new",directory,Path(directory)/"checkpoint")
            describe.assert_not_called()
            self.assertFalse((Path(directory)/"new").exists())

    def test_partial_pause_resumes_every_registered_actor_without_stopping_trainer(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeLive();host.partial_pause=True
            with self.assertRaisesRegex(OSError,"partial pause"):self.run_fake(host,Path(directory)/"new")
            self.assertTrue(all(not a["stopped"] for a in host.actor_states.values()))
            self.assertFalse(any(e[0]=="stop" for e in host.events))

    def test_signal_during_treatment_recovers_serial_and_resumes_all(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeLive();host.signal_in_B=True;out=Path(directory)/"new"
            with self.assertRaises(trial.metrics.TrialInterrupted):self.run_fake(host,out)
            self.assertTrue(host.active);self.assertEqual(host.flag,"0");self.assertIsNone(host.dropin_expected)
            self.assertTrue(all(not a["stopped"] for a in host.actor_states.values()))
            self.assertEqual(json.loads((out/"status.json").read_text())["state"],"interrupted")

    def test_failed_treatment_startup_returns_to_original_service(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeLive();host.fail_B_start=True;out=Path(directory)/"new"
            with self.assertRaisesRegex(trial.metrics.GuardFailure,"failed startup"):self.run_fake(host,out)
            self.assertTrue(host.active);self.assertEqual(host.flag,"0");self.assertIsNone(host.dropin_expected)
            self.assertTrue(all(not a["stopped"] for a in host.actor_states.values()))
            self.assertEqual(json.loads((out/"status.json").read_text())["recovery"]["errors"],[])

    def test_hung_old_process_never_spawns_a_second_trainer(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeLive();host.hung=True
            with self.assertRaisesRegex(trial.metrics.GuardFailure,"old trainer"):self.run_fake(host,Path(directory)/"new")
            self.assertFalse(any(e[0]=="start" for e in host.events));self.assertTrue(host.active)
            self.assertTrue(all(not a["stopped"] for a in host.actor_states.values()))

    def test_missing_reused_actor_is_not_signalled_but_other_paused_actors_resume(self):
        host=FakeLive();plan=fake_plan(host,Path("unused"));host.pause(plan)
        before=len(host.events);host.actor_states[2]["ticks"]+=1
        with self.assertRaisesRegex(trial.metrics.GuardFailure,"missing/reused"):host.resume()
        later=host.events[before:]
        self.assertFalse(any(e[0]=="signal" and e[1]==2 for e in later))
        self.assertTrue(all(not host.actor_states[n]["stopped"] for n in (1,3,4)))

    def test_only_treatment_flag_may_differ_between_phase_environments(self):
        host=FakeLive();plan=fake_plan(host,Path("unused"));host.flag="1"
        host.verify(plan,"1")
        host.extra_env["DQN_N_STEP"]="9"
        with self.assertRaisesRegex(trial.metrics.GuardFailure,"other than the treatment"):host.verify(plan,"1")

    def test_parallel_route_must_advance_and_runtime_fault_never_qualifies(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeLive();host.stall_route=True
            result=self.run_fake(host,Path(directory)/"stalled")
            self.assertEqual(result["decision"]["outcome"],"rejected")
            self.assertFalse(result["decision"]["checks"]["B_parallel_route_advanced"])
            host=FakeLive();host.runtime_fault_B=True
            with self.assertRaisesRegex(trial.metrics.GuardFailure,"Post-restart"):self.run_fake(host,Path(directory)/"fault")
            self.assertEqual(host.flag,"0")

    def test_verify_midphase_preserves_armed_log_reader_and_detects_new_fault(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"runtime.log";path.write_text("old\n");info=path.stat()
            fake=FakeLive();current=fake.describe();current["bindings"]["logs"]={str(path):dict(device=info.st_dev,inode=info.st_ino)}
            worker=current["bindings"]["worker"]
            first=trial.metrics.Host(fake.pid,FLEET);first.worker=worker
            second=trial.metrics.Host(fake.pid,FLEET);second.worker=worker
            host=trial.LiveHost(TRAINER,FLEET);plan=dict(initial=copy.deepcopy(current))
            with patch.object(host,"_inspect",side_effect=[(current,first),(current,second)]):
                host.verify(plan);host.metric_host.configure_logs(current["bindings"]["logs"])
                host.verify(plan)
            self.assertIs(host.metric_host,first)
            with path.open("a") as stream:stream.write("[SOCKET ACTION TIMEOUT] new\n")
            self.assertEqual(host.metric_host.log_errors()[0]["marker"],"[SOCKET ACTION TIMEOUT]")

    def test_real_verify_replacement_then_recover_never_adopts_or_stops_unknown_pid(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"trial.conf"
            treatment=("[Service]\nEnvironment="+trial.FLAG+"=1\n").encode();path.write_bytes(treatment)
            fixture=FakeLive();baseline=fixture.describe()
            cgroup="/user.slice/"+TRAINER
            baseline["trainer"]["ControlGroup"]=cgroup
            plan=dict(initial=copy.deepcopy(baseline),original_dropin=dict(content_base64=None,mode=None))
            host=trial.LiveHost(TRAINER,FLEET)
            original_reader=trial.metrics.Host(fixture.pid,FLEET)
            original_reader.worker=baseline["bindings"]["worker"]
            with patch.object(host,"_inspect",return_value=(baseline,original_reader)):
                host.describe();host.adopt_initial(baseline)
            saved_owner=copy.deepcopy(host.known_trainer)
            actors=copy.deepcopy(baseline["bindings"]["actors"][:2]);host.paused=actors
            host.dropin_expected=treatment
            replacement=copy.deepcopy(baseline);replacement["trainer"]["MainPID"]="999"
            replacement["bindings"]["worker"]["trainer"]=dict(pid=999,starttime_ticks=9999)
            replacement["bindings"]["fleet_cgroup"]="/unexpected/fleet"
            replacement["environment"][trial.FLAG]="1"
            replacement_reader=trial.metrics.Host(999,FLEET)
            replacement_reader.worker=replacement["bindings"]["worker"]
            with patch.object(host,"_inspect",return_value=(replacement,replacement_reader)):
                with self.assertRaisesRegex(trial.metrics.GuardFailure,"unknown replacement"):
                    host.verify(plan,"1")
            self.assertEqual(host.known_trainer,saved_owner)
            self.assertIs(host.metric_host,original_reader)
            self.assertEqual(host.current,baseline)
            self.assertEqual(host.owned_fleet_cgroup,"/owned/fleet")
            by_pid={actor["pid"]:actor for actor in actors}
            status={}
            with patch.object(host,"runtime_dropin",return_value=path),patch.object(host,"no_sidecars"),\
                    patch.object(host,"unit",return_value=dict(MainPID="999",ActiveState="active")),\
                    patch.object(host,"command") as command,\
                    patch.object(trial.metrics.identity,"identify_process",side_effect=lambda pid,role:by_pid[pid]),\
                    patch.object(Path,"read_text",return_value="0::/owned/fleet\n"),\
                    patch.object(trial.os,"kill") as kill:
                trial.recover(host,plan,status)
            command.assert_called_once_with("daemon-reload")
            self.assertEqual(kill.call_args_list,[((actor["pid"],signal.SIGCONT),) for actor in actors])
            self.assertEqual(host.known_trainer,saved_owner)
            self.assertEqual(host.paused,[])
            self.assertFalse(path.exists())
            self.assertTrue(status["recovery"]["original_dropin_restored"])
            self.assertTrue(status["recovery"]["manual_recovery_required"])
            self.assertIn("PID changed before recovery",status["recovery"]["errors"][0])

    def test_fallback_logs_are_transition_faults_and_invalidate_serial_control(self):
        markers=("replay prefetch failed","falling back to synchronous sampling",
                 "fused Adam unavailable","torch.compile unavailable")
        with tempfile.TemporaryDirectory() as directory:
            for number,marker in enumerate(markers):
                with self.subTest(marker=marker):
                    path=Path(directory)/("runtime"+str(number));path.write_text("");info=path.stat()
                    host=trial.LiveHost(TRAINER,FLEET)
                    host.begin_transition_logs({str(path):dict(device=info.st_dev,inode=info.st_ino)})
                    with path.open("a") as stream:stream.write("[WARN] "+marker+" (mock)\n")
                    event=host.transition_log_events()[0]
                    self.assertEqual(event["marker"],marker)
                    self.assertFalse(event["intentional_restart_compatible"])
                    fake=FakeLive();fake.runtime_fault_A_marker=marker
                    with self.assertRaisesRegex(trial.metrics.GuardFailure,"Post-restart"):
                        self.run_fake(fake,Path(directory)/("output"+str(number)))

    def test_numerical_environment_bindings_include_backend_thread_and_preload_settings(self):
        payload=b"DQN_BATCH_SIZE=4096\0OMP_NUM_THREADS=4\0LD_PRELOAD=/mock.so\0PYTORCH_CUDA_ALLOC_CONF=backend:cudaMallocAsync\0TORCHINDUCTOR_FOO=1\0TRITON_CACHE_DIR=/cache\0UNRELATED_SECRET=redacted\0"
        with patch.object(Path,"read_bytes",return_value=payload):
            result=trial.selected_environment(123)
        self.assertEqual(result["OMP_NUM_THREADS"],"4")
        self.assertEqual(result["LD_PRELOAD"],"/mock.so")
        self.assertIn("PYTORCH_CUDA_ALLOC_CONF",result)
        self.assertIn("TORCHINDUCTOR_FOO",result)
        self.assertIn("TRITON_CACHE_DIR",result)
        self.assertNotIn("UNRELATED_SECRET",result)

    def test_persistence_warning_increment_rejects_otherwise_intentional_shutdown(self):
        markers=("[WARN] HOF save failed:","[WARN] EpHOF save failed:","Replay buffer save failed:")
        with tempfile.TemporaryDirectory() as directory:
            for number,marker in enumerate(markers):
                with self.subTest(marker=marker):
                    path=Path(directory)/("persistence"+str(number))
                    path.write_text(marker+" old, outside transition\n");info=path.stat()
                    host=trial.LiveHost(TRAINER,FLEET)
                    host.begin_transition_logs({str(path):dict(device=info.st_dev,inode=info.st_ino)})
                    self.assertEqual(host.transition_log_events(),[])
                    with path.open("a") as stream:
                        stream.write("Traceback (most recent call last):\nTimeoutError: Batched inference request timed out\n")
                        stream.write(marker+" disk error in current controlled shutdown\n")
                    events=host.transition_log_events()
                    warning=next(event for event in events if event["marker"]==marker)
                    shutdown_traceback=next(event for event in events if event["marker"]=="Traceback")
                    self.assertFalse(warning["intentional_restart_compatible"])
                    self.assertTrue(shutdown_traceback["intentional_restart_compatible"])
                    self.assertGreater(warning["segment"]["start_byte"],0)
                    fake=FakeLive();fake.transition_log_events=lambda:events
                    with self.assertRaisesRegex(trial.metrics.GuardFailure,"Unexpected or ambiguous fault"):
                        self.run_fake(fake,Path(directory)/("output"+str(number)))
                    self.assertTrue(fake.active)
                    self.assertEqual(fake.flag,"0")
                    self.assertTrue(all(not actor["stopped"] for actor in fake.actor_states.values()))

    def test_consolidated_recipe_and_persistence_failures_reject_incremental_transitions(self):
        with tempfile.TemporaryDirectory() as directory:
            for number,line in enumerate(RECIPE_PERSISTENCE_FAILURE_LINES):
                with self.subTest(production_line=line):
                    path=Path(directory)/("recipe"+str(number));path.write_text(line+" old\n");info=path.stat()
                    host=trial.LiveHost(TRAINER,FLEET)
                    host.begin_transition_logs({str(path):dict(device=info.st_dev,inode=info.st_ino)})
                    self.assertEqual(host.transition_log_events(),[])
                    with path.open("a") as stream:
                        stream.write("Traceback (most recent call last):\nTimeoutError: Batched inference request timed out\n"+line+"\n")
                    events=host.transition_log_events()
                    failures=[event for event in events if not event["intentional_restart_compatible"]]
                    self.assertTrue(failures,line)
                    self.assertTrue(all(event["segment"]["start_byte"]>0 for event in failures))
                    fake=FakeLive();fake.transition_log_events=lambda:events
                    with self.assertRaisesRegex(trial.metrics.GuardFailure,"Unexpected or ambiguous fault"):
                        self.run_fake(fake,Path(directory)/("output"+str(number)))
                    self.assertTrue(fake.active);self.assertEqual(fake.flag,"0")
                    self.assertTrue(all(not actor["stopped"] for actor in fake.actor_states.values()))

    def test_expected_c51_support_override_partial_message_and_unrelated_warn_are_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"normal.log";path.write_text("");info=path.stat()
            host=trial.LiveHost(TRAINER,FLEET)
            host.begin_transition_logs({str(path):dict(device=info.st_dev,inode=info.st_ino)})
            with path.open("a") as stream:
                stream.write("  Info: skipped 1 expected checkpoint keys:\n    support: keeping configured C51 support\n")
                stream.write("Checkpoint load complete (expected C51 support override)\nPartial load (missing=1, unexpected=0)\n")
                stream.write("[WARN] unrelated benign startup notice\n")
            self.assertEqual(host.transition_log_events(),[])

    def test_bank_proof_reads_only_new_trainer_stdout_and_keeps_fault_reader_armed(self):
        pair="  HOF loaded: 192 episodes / 4,920,123 transitions\n  EPHOF loaded: 192 episodes / 4,811,222 transitions\n"
        warning="  [WARN] Backup copy failed: mock current shutdown fault\n"
        cases=(
            ('success','',pair+warning,'',None),
            ('missing_ephof','','  HOF loaded: 192 episodes / 4,920,123 transitions\n','', 'startup pair'),
            ('zero_episodes','',pair.replace('HOF loaded: 192','HOF loaded: 0',1),'','empty'),
            ('zero_transitions','',pair.replace('4,811,222','0'),'','empty'),
            ('old_outside_increment',pair,'','','startup pair'),
            ('actor_only','','',pair,'startup pair'),
            ('actor_cannot_supply_missing_bank','','  HOF loaded: 192 episodes / 4,920,123 transitions\n',pair,'startup pair'),
            ('duplicate_bank','',pair+'  HOF loaded: 192 episodes / 1,234 transitions\n','','startup pair'),
        )
        with tempfile.TemporaryDirectory() as directory:
            for name,old,new,actor_output,error in cases:
                with self.subTest(case=name):
                    root=Path(directory)/name;root.mkdir()
                    stdout=root/'trainer.out';actor_log=root/'actor.out'
                    stdout.write_text(old);actor_log.write_text('')
                    bindings={str(path):dict(device=path.stat().st_dev,inode=path.stat().st_ino) for path in (stdout,actor_log)}
                    current=FakeLive().describe();current['trainer_stdout']=dict(path=str(stdout),**bindings[str(stdout)])
                    owner=current['bindings']['worker']['trainer']
                    host=trial.LiveHost(TRAINER,FLEET);host.known_trainer=dict(identity=owner)
                    host.begin_transition_logs(bindings,current['trainer_stdout'])
                    offsets=copy.deepcopy(host.transition_logs.log_offsets)
                    with stdout.open('a') as stream:stream.write(new)
                    with actor_log.open('a') as stream:stream.write(actor_output)
                    original_resolve=Path.resolve
                    def resolve(path,*args,**kwargs):
                        if str(path)==f"/proc/{owner['pid']}/fd/1":return stdout
                        return original_resolve(path,*args,**kwargs)
                    with patch.object(host,'no_sidecars'),patch.object(trial.metrics.identity,'identify_process',return_value=owner),patch.object(Path,'resolve',resolve):
                        if error:
                            with self.assertRaisesRegex(trial.metrics.GuardFailure,error):host.bank_load_proof(current)
                        else:
                            proof=host.bank_load_proof(current)
                            self.assertEqual(proof['counts'],{'HOF':dict(episodes=192,transitions=4920123),'EPHOF':dict(episodes=192,transitions=4811222)})
                            self.assertEqual(proof['start_byte'],len(old.encode()))
                            self.assertEqual(proof['end_byte'],len((old+new).encode()))
                            self.assertEqual(proof['sha256'],hashlib.sha256(new.encode()).hexdigest())
                    self.assertEqual(host.transition_logs.log_offsets,offsets)
                    if not error:
                        events=host.transition_log_events()
                        self.assertEqual(events[0]['marker'],'[WARN] Backup copy failed:')
                        self.assertFalse(events[0]['intentional_restart_compatible'])

    def test_failed_positive_bank_proof_never_resumes_actors_into_unverified_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            host=FakeLive()
            def fail(current):
                host.events.append(('failed_bank_proof',))
                self.assertTrue(all(actor['stopped'] for actor in host.actor_states.values()))
                raise trial.metrics.GuardFailure('mock missing startup banks')
            host.bank_load_proof=fail
            with self.assertRaisesRegex(trial.metrics.GuardFailure,'missing startup banks'):
                self.run_fake(host,Path(directory)/'new')
            failure=host.events.index(('failed_bank_proof',))
            self.assertFalse(any(event[0]=='signal' and event[2]==signal.SIGCONT for event in host.events[:failure]))
            self.assertTrue(all(not actor['stopped'] for actor in host.actor_states.values()))

    def recovery_fixture(self, directory, *, serial=False):
        host=FakeLive();plan=fake_plan(host,Path(directory)/'unused')
        host.flag=host.configured_flag='0' if serial else '1'
        host.dropin_expected=b'[Service]\nEnvironment=DQN_PARALLEL_STATE_FILL='+host.flag.encode()+b'\n'
        host.restart_in_progress=True
        status=dict(state='running',decision=dict(outcome='qualified'))
        return host,plan,status

    def test_recovery_primary_proves_banks_and_scans_faults_before_actor_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            host,plan,status=self.recovery_fixture(directory)
            def scan():
                host.events.append(('scan_recovery_faults',))
                return []
            host.transition_log_events=scan
            trial.recover(host,plan,status)
            proof=status['recovery']['serial_replacements'][0]
            self.assertTrue(proof['bank_verified']);self.assertEqual(proof['state'],'verified')
            self.assertIn('bank_load_proof',proof);self.assertEqual(proof['log_events'],[])
            names=[event[0] for event in host.events]
            self.assertLess(names.index('arm_transition'),names.index('start'))
            self.assertLess(names.index('start'),names.index('bank_load_proof'))
            self.assertLess(names.index('bank_load_proof'),names.index('scan_recovery_faults'))
            resumed=next(i for i,event in enumerate(host.events) if event[0]=='signal' and event[2]==signal.SIGCONT)
            self.assertLess(names.index('scan_recovery_faults'),resumed)
            self.assertFalse(status['recovery']['manual_recovery_required'])

    def test_first_A_serial_running_failed_bank_proof_requires_manual_invalid_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            host,plan,status=self.recovery_fixture(directory,serial=True)
            def missing(current):
                host.events.append(('missing_recovery_banks',))
                raise trial.metrics.GuardFailure('recovery has no startup banks')
            host.bank_load_proof=missing
            trial.recover(host,plan,status)
            self.assertTrue(host.active);self.assertEqual(host.flag,'0')
            self.assertTrue(status['recovery']['manual_recovery_required'])
            self.assertEqual(status['decision']['outcome'],'invalid')
            self.assertIn('unverified',status['recovery']['final_environment'])
            attempt=status['recovery']['serial_replacements'][0]
            self.assertFalse(attempt['bank_verified']);self.assertIn('no startup banks',attempt['error'])
            self.assertTrue(all(not actor['stopped'] for actor in host.actor_states.values()))

    def test_pid0_fallback_rearms_and_proves_each_new_serial_replacement(self):
        for missing in (False,True):
            with self.subTest(missing_banks=missing),tempfile.TemporaryDirectory() as directory:
                host,plan,status=self.recovery_fixture(directory)
                stop=host.stop
                calls=[]
                def fail_first_stop(expected=None):
                    stop(expected);calls.append(1)
                    if len(calls)==1:raise trial.metrics.GuardFailure('primary stop failed after PID0')
                host.stop=fail_first_stop
                if missing:
                    def absent(current):raise trial.metrics.GuardFailure('fallback banks missing')
                    host.bank_load_proof=absent
                trial.recover(host,plan,status)
                attempts=status['recovery']['serial_replacements']
                self.assertEqual([row['path'] for row in attempts],['primary','fallback'])
                self.assertEqual([row['state'] for row in attempts],['failed','failed' if missing else 'verified'])
                self.assertEqual(attempts[1]['bank_verified'],not missing)
                self.assertEqual(sum(event[0]=='arm_transition' for event in host.events),2)
                self.assertEqual(sum(event[0]=='start' for event in host.events),1)
                self.assertTrue(status['recovery']['manual_recovery_required']) # Original failure retained.
                self.assertEqual(status['decision']['outcome'],'invalid')
                if missing:self.assertIn('fallback banks missing',attempts[1]['error'])
                else:self.assertIn('bank_load_proof',attempts[1])
                self.assertTrue(all(not actor['stopped'] for actor in host.actor_states.values()))

    def test_positive_recovery_bank_counts_cannot_hide_current_persistence_fault(self):
        with tempfile.TemporaryDirectory() as directory:
            host,plan,status=self.recovery_fixture(directory)
            host.transition_log_events=lambda:[dict(marker='[WARN] HOF save failed:',intentional_restart_compatible=False)]
            trial.recover(host,plan,status)
            attempt=status['recovery']['serial_replacements'][0]
            self.assertIn('bank_load_proof',attempt)
            self.assertFalse(attempt['bank_verified'])
            self.assertEqual(attempt['log_events'][0]['marker'],'[WARN] HOF save failed:')
            self.assertTrue(status['recovery']['manual_recovery_required'])
            self.assertEqual(status['decision']['outcome'],'invalid')

    def test_recovery_uses_actual_new_stdout_increment_not_old_positive_bank_lines(self):
        pair='  HOF loaded: 192 episodes / 4,920,123 transitions\n  EPHOF loaded: 192 episodes / 4,811,222 transitions\n'
        warning='[WARN] HOF save failed: current shutdown fault\n'
        for startup in ('good','missing','warning'):
            with self.subTest(startup=startup),tempfile.TemporaryDirectory() as directory:
                stdout=Path(directory)/'trainer.out';stdout.write_text(pair)
                info=stdout.stat();binding=dict(path=str(stdout),device=info.st_dev,inode=info.st_ino)
                host=FakeLive();describe=host.describe
                def actual_bindings():
                    current=describe();current['trainer_stdout']=copy.deepcopy(binding)
                    current['bindings']['logs']={str(stdout):dict(device=info.st_dev,inode=info.st_ino)}
                    host.current=current;return current
                host.describe=actual_bindings
                plan=fake_plan(host,Path(directory)/'unused')
                host.flag=host.configured_flag='1';host.dropin_expected=b'[Service]\nEnvironment=DQN_PARALLEL_STATE_FILL=1\n';host.restart_in_progress=True
                host.begin_transition_logs=types.MethodType(trial.LiveHost.begin_transition_logs,host)
                host.bank_load_proof=types.MethodType(trial.LiveHost.bank_load_proof,host)
                host.transition_log_events=types.MethodType(trial.LiveHost.transition_log_events,host)
                start=host.start
                def start_with_current_log():
                    start();host.known_trainer=dict(identity=dict(pid=host.pid,starttime_ticks=host.pid+10000))
                    with stdout.open('a') as stream:
                        stream.write('  HOF loaded: 192 episodes / 4,920,123 transitions\n' if startup=='missing' else pair)
                        if startup=='warning':stream.write(warning)
                host.start=start_with_current_log
                original_resolve=Path.resolve
                def resolve(path,*args,**kwargs):
                    if str(path)==f'/proc/{host.pid}/fd/1':return stdout
                    return original_resolve(path,*args,**kwargs)
                identity=lambda pid,kind:dict(pid=pid,starttime_ticks=pid+10000)
                status={}
                with patch.object(Path,'resolve',resolve),patch.object(trial.metrics.identity,'identify_process',side_effect=identity):
                    trial.recover(host,plan,status)
                attempt=status['recovery']['serial_replacements'][0]
                self.assertEqual(attempt['bank_verified'],startup=='good')
                self.assertEqual(status['recovery']['manual_recovery_required'],startup!='good')
                if startup=='good':self.assertEqual(attempt['bank_load_proof']['start_byte'],len(pair.encode()))
                elif startup=='missing':self.assertIn('startup pair',attempt['error'])
                else:self.assertEqual(attempt['log_events'][0]['marker'],'[WARN] HOF save failed:')
                self.assertTrue(all(not actor['stopped'] for actor in host.actor_states.values()))

    def test_recovery_keeps_missing_bank_error_when_fault_reader_also_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            host,plan,status=self.recovery_fixture(directory)
            host.bank_load_proof=lambda current:(_ for _ in ()).throw(trial.metrics.GuardFailure('missing banks'))
            host.transition_log_events=lambda:(_ for _ in ()).throw(trial.metrics.GuardFailure('log read failed'))
            trial.recover(host,plan,status)
            attempt=status['recovery']['serial_replacements'][0]
            self.assertEqual(attempt['startup_error'],'missing banks')
            self.assertEqual(attempt['log_read_error'],'log read failed')
            self.assertEqual(attempt['error'],'missing banks')
            self.assertTrue(status['recovery']['manual_recovery_required'])

    def test_startup_without_known_pid_can_stop_empty_failed_unit(self):
        host=trial.LiveHost(TRAINER,FLEET);host.known_trainer=None
        snapshots=[dict(MainPID="0",ActiveState="failed"),dict(MainPID="0",ActiveState="inactive")]
        with patch.object(host,"no_sidecars"),patch.object(host,"unit",side_effect=snapshots),patch.object(host,"command") as command,patch.object(host,"assert_retired_absent"):
            host.stop()
        command.assert_called_once_with("stop","--no-block",TRAINER)

    def test_unknown_live_startup_pid_is_not_stopped(self):
        host=trial.LiveHost(TRAINER,FLEET)
        with patch.object(host,"no_sidecars"),patch.object(host,"unit",return_value=dict(MainPID="999")),patch.object(host,"command") as command:
            with self.assertRaisesRegex(trial.metrics.GuardFailure,"unknown live"):host.stop()
        command.assert_not_called()

    def test_old_pid_alive_even_with_zero_unit_pid_blocks_start(self):
        host=trial.LiveHost(TRAINER,FLEET);host.retired_trainers=[dict(pid=123,starttime_ticks=456)]
        with patch.object(Path,"read_text",return_value="fake"),patch.object(trial.metrics.identity,"stat_fields",return_value=dict(starttime_ticks=456)),patch.object(host,"command") as command:
            with self.assertRaisesRegex(trial.metrics.GuardFailure,"still alive"):host.start()
        command.assert_not_called()

    def test_lingering_trainer_in_owned_cgroup_blocks_start(self):
        host=trial.LiveHost(TRAINER,FLEET);cgroup="/user.slice/"+TRAINER
        with patch.object(host,"unit",return_value=dict(ControlGroup=cgroup)),patch.object(Path,"exists",return_value=True),patch.object(Path,"read_text",return_value="987"),patch.object(Path,"read_bytes",return_value=b"python\0Scripts/run_dqn.py\0"),patch.object(host,"command") as command:
            with self.assertRaisesRegex(trial.metrics.GuardFailure,"owned service cgroup"):host.start()
        command.assert_not_called()


if __name__=="__main__":unittest.main()
