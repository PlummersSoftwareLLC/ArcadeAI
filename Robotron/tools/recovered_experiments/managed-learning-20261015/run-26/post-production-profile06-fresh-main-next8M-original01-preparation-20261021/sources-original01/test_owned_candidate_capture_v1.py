"""CPU contracts: real private files, mocked unit/kernel events, no production IO."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


w = load(HERE/'owned_candidate_capture_v1.py','_owned_capture_contract_target')
REAL_PAUSE = load(w.G/'logs/managed-learning-20261015/run-26/profile06-production-continuity-live-controller-original01-preparation-20261021/sources/handoff_poststop_v1.py','_original_archive_helper')
OWNER = dict(pid=123,starttime_ticks=321,unit='synthetic-main.service',invocation_id='a'*32,cgroup='/private/synthetic-main.service')
CONTROLLER = dict(pid=456,starttime_ticks=654,unit='synthetic-capture.service',invocation_id='b'*32,cgroup='/private/synthetic-capture.service')
RESCUE = dict(pid=789,starttime_ticks=987,unit='synthetic-rescue.service',invocation_id='c'*32,cgroup='/private/synthetic-rescue.service')


def production_job():
    return dict(schema='robotron-one-owned-candidate-save-v1',mode='production',case='profile06-candidate-save-original01-20261021',
        owner=dict(pid=3295795,starttime_ticks=64995335,invocation_id='160d2b4b1f6e4e2f8839790658a7d01c',unit='robotron-managed-run-26-d3b365c9-trainer.service'),
        linux=dict(sha256=w.LINUX_SHA),pause_source=dict(sha256=w.PAUSE_SHA),design=dict(sha256=w.DESIGN_SHA),
        model_dir=str(w.G/'models_dqn'),capture_output=str(w.P/'capture-original01'),rescue_output=str(w.P/'capture-rescue-original01'),
        tag='profile06_LR25_next8M_01_20261021',controller_unit='robotron-profile06-candidate-save-original01-20261021-capture.service',
        rescue_unit='robotron-profile06-candidate-save-original01-20261021-rescue.service',job_path='/synthetic/job.json',
        controller_argv_prefix=['/usr/bin/python3.12','-I','-B','/synthetic/capture.py','--capture','--job','/synthetic/job.json','--expected-job-sha256'])


class CaptureContracts(unittest.TestCase):
    def test_full8_pin_includes_mode_timestamps_and_excludes_atime(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source';path.write_bytes(b'original')
            before=w.full_pin(path);path.read_bytes();after=w.full_pin(path)
            self.assertEqual(before,after)
            self.assertEqual(set(before['identity']),{'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'})

    def test_pin_rejects_symlink_and_multiple_links(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source';path.write_bytes(b'original');alias=path.with_name('alias')
            alias.symlink_to(path)
            with self.assertRaises(ValueError):w.full_pin(alias)
            alias.unlink();os.link(path,alias)
            with self.assertRaises(ValueError):w.full_pin(path)

    def test_checked_rejects_timestamp_change_with_identical_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source';path.write_bytes(b'original');before=w.full_pin(path)
            os.utime(path,ns=(path.stat().st_atime_ns,before['identity']['mtime_ns']+1000))
            with self.assertRaises(ValueError):w.checked(before)

    def test_only_separate_archive_is_sealed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source';path.write_bytes(b'original');path.chmod(0o664);before=w.full_pin(path)
            archive=w.publish(path.with_name('archive'),path.read_bytes())
            self.assertEqual(archive['identity']['mode'],'0o444');self.assertEqual(w.full_pin(path),before)

    def test_production_scope_accepts_exact_current_owner(self):
        w.validate_scope(production_job())

    def test_foreign_production_scope_and_helper_versions_rejected(self):
        for key,value in [('tag','../escape'),('model_dir','/tmp/models'),('case','foreign'),('controller_unit','foreign.service'),('rescue_output','/tmp/rescue')]:
            job=production_job();job[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):w.validate_scope(job)
        for key in ['linux','pause_source','design']:
            job=production_job();job[key]['sha256']='0'*64
            with self.subTest(key=key),self.assertRaises(ValueError):w.validate_scope(job)

    def test_old_owner_and_foreign_command_scope_rejected(self):
        job=production_job();job['owner']['pid']=3170722
        with self.assertRaises(ValueError):w.validate_scope(job)
        job=production_job();job['controller_argv_prefix'][-2]='/foreign/job.json'
        with self.assertRaises(ValueError):w.validate_scope(job)

    def test_private_scope_cannot_target_production_model_or_unit(self):
        job=production_job();job.update(mode='private_kernel_fixture',fixture_variant='loss')
        with self.assertRaises(ValueError):w.validate_scope(job)

    def test_both_prospective_horizons_and_exact_owner_required(self):
        baseline=dict(optimizer_identity=dict(process_id=123,epoch=1),replay_identity=dict(process_id=123,epoch=1),
            clocks=dict(learner_frame_count=100),learner_accepted=200)
        for frames,accepted,valid in [(8_000_000,7_999_999,False),(7_999_999,8_000_000,False),(8_000_000,8_000_000,True)]:
            trigger=copy.deepcopy(baseline);trigger['clocks']['learner_frame_count']+=frames;trigger['learner_accepted']+=accepted
            if valid:w.eligible_exposure(baseline,trigger,OWNER)
            else:
                with self.assertRaises(ValueError):w.eligible_exposure(baseline,trigger,OWNER)
        trigger=copy.deepcopy(baseline);trigger['optimizer_identity']['epoch']=2
        with self.assertRaises(ValueError):w.eligible_exposure(baseline,trigger,OWNER)

    def test_exact_recorded_owner_only_is_thawed(self):
        pause=SimpleNamespace(thaw_startup_save=lambda linux,owner:dict(owner=owner))
        job=dict(case='synthetic',owner=OWNER);state=dict(schema='robotron-one-owned-save-state-v1',case='synthetic',controller=CONTROLLER,save_owner=OWNER,paused_owner=OWNER)
        result=w.rescue_state(job,state,CONTROLLER,None,pause)
        self.assertTrue(result['runtime_changed']);self.assertEqual(result['thaw']['owner'],OWNER)

    def test_no_recorded_hold_performs_no_kernel_action(self):
        pause=SimpleNamespace(thaw_startup_save=lambda *_:self.fail('Unowned thaw'))
        job=dict(case='synthetic',owner=OWNER);state=dict(schema='robotron-one-owned-save-state-v1',case='synthetic',controller=CONTROLLER,save_owner=OWNER,paused_owner=None)
        self.assertFalse(w.rescue_state(job,state,CONTROLLER,None,pause)['runtime_changed'])

    def test_foreign_pause_or_controller_is_never_released(self):
        pause=SimpleNamespace(thaw_startup_save=lambda *_:self.fail('Foreign thaw'))
        job=dict(case='synthetic',owner=OWNER);base=dict(schema='robotron-one-owned-save-state-v1',case='synthetic',controller=CONTROLLER,save_owner=OWNER,paused_owner=OWNER)
        for key in ['controller','save_owner','paused_owner']:
            state=copy.deepcopy(base);state[key]=RESCUE
            with self.subTest(key=key),self.assertRaises(ValueError):w.rescue_state(job,state,CONTROLLER,None,pause)

    def exercise_capture(self,root,*,callback=None,archive_failure=False,existing_request=False):
        model=root/'models';(model/'managed-checkpoints').mkdir(parents=True);group=root/'group';group.mkdir()
        (group/'cgroup.events').write_text('frozen 0\n')
        rescue=root/'rescue';rescue.mkdir()
        ready=w.publish(rescue/'ready.json',dict(owner=RESCUE,job_sha256='d'*64))
        birth=w.publish(rescue/'original-controller-birth.json',CONTROLLER)
        job=dict(mode='private_kernel_fixture',case='synthetic',tag='synthetic_tag',owner=OWNER,
            controller_unit=CONTROLLER['unit'],rescue_unit=RESCUE['unit'],controller_argv_prefix=[],
            capture_output=str(root/'out'),model_dir=str(model),rescue_output=str(rescue))
        request=model/'managed_save.request.json'
        if existing_request:request.write_text('foreign')
        calls=[]
        linux=SimpleNamespace(live_owner=lambda owner:calls.append(('live',owner)),full_pin=w.full_pin)
        @contextlib.contextmanager
        def pause(adapter,owner):
            adapter.startup_save_paused_owner=owner;adapter.b.state()
            recorded=json.loads((root/'out/save-publication-state.json').read_bytes())
            self.assertEqual(recorded['paused_owner'],owner)
            (group/'cgroup.events').write_text('frozen 1\n');calls.append(('freeze',owner))
            try:yield group
            finally:
                (group/'cgroup.events').write_text('frozen 0\n');calls.append(('thaw',owner))
                adapter.startup_save_paused_owner=None;adapter.b.state()
                if request.exists() and request.read_bytes()!=b'foreign':
                    value=json.loads(request.read_bytes());source=model/'managed-checkpoints'/(value['tag']+'.pt')
                    source.write_bytes(b'private model stand-in');source.chmod(0o664)
                    slot=request.with_name(request.name+'.completed');slot.write_text(json.dumps(value)+'\n');slot.chmod(0o664)
                    request.unlink()
        def archive(linux,source,destination):
            if archive_failure:raise RuntimeError('injected independent copy failure')
            return REAL_PAUSE.archive(linux,source,destination)
        pause_module=SimpleNamespace(startup_save_pause=pause,publish_request_exclusive=REAL_PAUSE.publish_request_exclusive,archive=archive)
        with patch.object(w,'dependencies',return_value=(linux,pause_module)),patch.object(w,'identity',return_value=CONTROLLER),patch.object(w,'command_matches'),patch.object(w,'wait_rescue',return_value=(ready,birth)):
            code=w.capture(job,'d'*64,after_frozen=callback)
        result=json.loads((root/'out/result.json').read_bytes())
        return code,result,calls,group,model

    def test_complete_capture_records_request_pin_and_preserves_normal_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,group,model=self.exercise_capture(Path(directory))
            self.assertEqual(code,0);self.assertEqual(result['checkpoint']['identity']['mode'],'0o444')
            self.assertEqual(result['source']['identity']['mode'],'0o664')
            self.assertEqual(w.full_pin(result['source']['path']),result['source'])
            publication=json.loads(w.checked(result['publication']))
            self.assertEqual(publication['request']['identity']['nlink'],1)
            self.assertEqual(publication['request']['sha256'],publication['request_archive']['sha256'])
            self.assertIn(('freeze',OWNER),calls);self.assertIn(('thaw',OWNER),calls)

    def test_publication_exception_releases_hold_and_preserves_failure(self):
        def fail(_):raise RuntimeError('injected publication failure')
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,group,model=self.exercise_capture(Path(directory),callback=fail)
            self.assertEqual(code,1);self.assertIn('injected publication failure',result['error'])
            self.assertEqual((group/'cgroup.events').read_text(),'frozen 0\n')
            self.assertIn(('thaw',OWNER),calls);self.assertFalse((model/'managed_save.request.json').exists())

    def test_existing_request_is_not_overwritten_or_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,group,model=self.exercise_capture(Path(directory),existing_request=True)
            self.assertEqual(code,1);self.assertEqual((model/'managed_save.request.json').read_text(),'foreign')
            self.assertNotIn(('freeze',OWNER),calls)

    def test_archive_failure_preserves_normal_producer_and_actual_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls,group,model=self.exercise_capture(Path(directory),archive_failure=True)
            self.assertEqual(code,1);self.assertIn('injected independent copy failure',result['error'])
            self.assertEqual(oct((model/'managed-checkpoints/synthetic_tag.pt').stat().st_mode&0o777),'0o664')
            self.assertFalse(result['original_request_retried'])

    def exercise_watch(self,root,*,foreign=False,alive=False):
        capture=root/'capture';capture.mkdir();state=dict(schema='robotron-one-owned-save-state-v1',case='synthetic',controller=CONTROLLER,
            save_owner=OWNER,paused_owner=RESCUE if foreign else OWNER,deadline_monotonic_s=time.monotonic()-1)
        w.mutable_state(capture/'save-publication-state.json',state)
        job=dict(case='synthetic',owner=OWNER,source=dict(path='/synthetic/capture.py'),job_path='/synthetic/job.json',controller_unit=CONTROLLER['unit'],
            rescue_unit=RESCUE['unit'],rescue_output=str(root/'rescue'),capture_output=str(capture),controller_argv_prefix=[])
        calls=[];linux=SimpleNamespace(show=lambda unit:dict(MainPID=str(CONTROLLER['pid'])),process_start=lambda pid:CONTROLLER['starttime_ticks'] if alive else None,
            live_owner=lambda owner:None)
        pause=SimpleNamespace(thaw_startup_save=lambda linux,owner:calls.append(owner) or dict(owner=owner))
        def owner(linux,unit,**kwargs):return RESCUE if unit==RESCUE['unit'] else CONTROLLER
        with patch.object(w,'dependencies',return_value=(linux,pause)),patch.object(w,'identity',side_effect=owner),patch.object(w,'command_matches'):
            code=w.watch(job,'d'*64)
        return code,json.loads((root/'rescue/result.json').read_bytes()),calls

    def test_actual_watch_loop_recovers_after_original_controller_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls=self.exercise_watch(Path(directory))
            self.assertEqual(code,0);self.assertFalse(result['controller_alive']);self.assertEqual(calls,[OWNER])
            self.assertTrue(result['original_exit_not_normalized'])

    def test_actual_watch_loop_refuses_foreign_pause_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls=self.exercise_watch(Path(directory),foreign=True)
            self.assertEqual(code,1);self.assertEqual(calls,[]);self.assertIn('recovery_error',result)

    def test_watch_deadline_keeps_nonzero_outcome_and_same_live_controller(self):
        with tempfile.TemporaryDirectory() as directory:
            code,result,calls=self.exercise_watch(Path(directory),alive=True)
            self.assertEqual(code,1);self.assertTrue(result['controller_alive']);self.assertEqual(calls,[OWNER])
            self.assertFalse(result['restart_retry'])

    def test_foreign_rescue_readiness_rejected_before_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);w.publish(root/'ready.json',dict(owner=RESCUE,job_sha256='e'*64));w.publish(root/'original-controller-birth.json',CONTROLLER)
            with self.assertRaises(ValueError):w.wait_rescue(dict(rescue_output=str(root)),'d'*64,SimpleNamespace(live_owner=lambda _:self.fail('Foreign ready')),CONTROLLER)

    def test_default_cli_does_not_read_or_create_anything(self):
        with patch.object(w,'full_pin',side_effect=AssertionError('Unexpected IO')),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(w.main([]),0);self.assertIn('PLAN_ONLY',output.getvalue())
