"""Authored stdlib private-file/mocked-unit guards; no numerical or live unit test."""
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import early_insurance as helper
from . import run_raw_kl_transition as adapter


def identity(value):
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
        mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
        mode=oct(stat.S_IMODE(value.st_mode)), uid=value.st_uid, nlink=value.st_nlink)


def fingerprint(path, limit=None):
    path = Path(path); before = identity(path.stat()); data = path.read_bytes()
    assert limit is None or len(data) <= limit
    assert before == identity(path.stat())
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), identity=before)


def publish(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, allow_nan=True); stream.flush(); os.fsync(stream.fileno())
    Path(path).chmod(0o444)
    return fingerprint(path)


def exclusive_copy(source, target):
    before = fingerprint(source)
    with Path(target).open('xb') as stream:
        stream.write(Path(source).read_bytes())
    Path(target).chmod(0o444)
    assert before == fingerprint(source)
    return before, fingerprint(target)


class EarlyContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        self.model = self.root/'models'; self.model.mkdir(); (self.model/'managed-checkpoints').mkdir()
        self.now = [10.0]; self.calls = []
        self.owner = dict(pid=123, starttime_ticks=7, unit='trainer.service', invocation_id='a'*32, cgroup='/owned')
        self.raw = dict(training_steps=10, optimized_samples=40960, frame_count=2000, learner_frame_count=1000,
            client_count=192, training_enabled=True, measurement_active=False,
            host_pipeline=dict(learning_exposure=dict(optimizer=dict(process_id=123))))
        old = self.model/'managed_save.request.json.completed'; publish(old, dict(tag='previous'))
        self.base = SimpleNamespace(MAX_SOURCE=2<<20, MAX_JSON=2<<20, identity=identity,
            fingerprint=fingerprint, publish=publish, read_json=lambda pin:json.loads(Path(pin['path']).read_text()),
            pin=lambda pin,*args: fingerprint(pin['path']), exclusive_copy=exclusive_copy,
            fsync_directory=lambda path:None,
            validate_python_binding=lambda verifier,pin,**kw:self.calls.append(('python_binding',verifier,pin)))
        record = publish(self.root/'phase.json', dict(metric='kl'))
        boot = publish(self.root/'boot.json', dict(clocks=adapter.four(self.raw)))
        old_provenance = publish(self.root/'old-provenance.json', dict(old=True))
        control = publish(self.root/'control.json', dict(experiment='trial'))
        context = dict(model_package={}, archived_control=control, archived_trainer_unit=old_provenance,
                       provenance=[], held_recipe_context={})
        self.runtime = SimpleNamespace(job=dict(model_dir=str(self.model), game_root=str(self.root),
            experiment='trial', startup_tag='startup', trainer_unit='trainer.service',
            insurance_verification=old_provenance,
            verifier=dict(python='/venv/bin/python', script=dict(path='/strict7d.py',sha256='d'*64),context=context,
                python_binding=dict(successful_execution=old_provenance, successful_completion=old_provenance,
                                    successful_result=old_provenance))),
            pending=None, current_completed=fingerprint(old), trainer_id=lambda:copy.deepcopy(self.owner),
            raw_api=lambda:copy.deepcopy(self.raw), inspect=lambda phase:self.calls.append(('inspect',phase)),
            metrics=SimpleNamespace(block_restore_signals=contextlib.nullcontext),
            record_pin=record, record={}, current_checkpoint=dict(source=dict(path='/latest',sha256='b'*64,bytes=10),verification=boot))
        def guard():
            pending = self.runtime.pending
            request = self.model/'managed_save.request.json'; slot = Path(str(request)+'.completed')
            if pending is not None and not request.exists():
                self.assertEqual(adapter.request_identity(fingerprint(slot)['identity']), adapter.request_identity(pending['pin']['identity']))
        self.runtime.request_guard = guard
        self.base.pin=lambda pin,*args:None  # Source/executable guard effects are explicit mocks.
        def sources(label):
            self.calls.append(('sources',label));return {},copy.deepcopy(context)
        self.runtime.phase_sources = sources
        self.spec = dict(tag='early', cpu_unit='robotron-early-fixture.service', save_timeout_s=60,cpu_timeout_s=120)
        self.phase = dict(record=record,boot_checkpoint=dict(path='/latest',sha256='b'*64,bytes=10))

    def snapshot(self, name='snapshot'):
        return helper.Snapshot(adapter,self.base,self.runtime,self.spec,self.root/name,
                               clock=lambda:self.now[0],wall=lambda:100+self.now[0])

    def complete(self, snapshot):
        request=self.model/'managed_save.request.json'
        snapshot.target.write_bytes(b'opaque private fixture, never decoded')
        os.replace(request,str(request)+'.completed')
        self.assertEqual(snapshot.tick()['status'],'COMPLETE')

    def test_real_request_lifecycle_leaves_flags_and_actors_unchanged(self):
        snap=self.snapshot();before=copy.deepcopy(self.raw);snap.start(self.raw,adapter.four(self.raw))
        self.assertEqual(snap.result()['status'],'PENDING');self.assertEqual(self.raw,before)
        self.assertIsNotNone(self.runtime.pending);self.assertFalse(snap.target.exists())
        self.complete(snap);self.assertIsNone(self.runtime.pending)
        self.assertEqual(self.runtime.current_completed,snap.completed)
        self.assertEqual(self.calls,[])

    def test_main_ticks_never_copy_model_bytes_and_foreign_completion_fails(self):
        snap=self.snapshot();snap.start(self.raw,adapter.four(self.raw))
        original=self.base.exclusive_copy
        def copy_small(source,target):
            self.assertNotEqual(Path(source).suffix,'.pt');return original(source,target)
        self.base.exclusive_copy=copy_small
        self.assertEqual(snap.tick()['status'],'PENDING')
        foreign=self.root/'foreign';publish(foreign,dict(tag='early'))
        (self.model/'managed_save.request.json').unlink()
        os.replace(foreign,self.model/'managed_save.request.json.completed')
        self.assertEqual(snap.tick()['status'],'FAILED')

    def test_timeout_and_failed_request_never_retry_or_replace_pending(self):
        snap=self.snapshot();snap.start(self.raw,adapter.four(self.raw));pending=self.runtime.pending
        self.now[0]+=61
        self.assertEqual(snap.tick()['status'],'FAILED');self.assertIs(self.runtime.pending,pending)
        with self.assertRaises(RuntimeError):snap.start(self.raw,adapter.four(self.raw))

    def test_independent_freeze_is_once_and_carries_authentic_phase_request_floor(self):
        snap=self.snapshot();snap.start(self.raw,adapter.four(self.raw));self.complete(snap)
        frozen=snap.freeze(phase=self.phase)
        self.assertEqual(frozen['source']['sha256'],frozen['verification_copy']['sha256'])
        self.assertNotEqual(frozen['source']['identity']['inode'],frozen['verification_copy']['identity']['inode'])
        self.assertEqual(frozen['source']['identity']['mode'],'0o444')
        acquisition=self.base.read_json(frozen['acquisition'])
        self.assertEqual(acquisition['client_count'],192);self.assertEqual(acquisition['clock_floor'],adapter.four(self.raw))
        self.assertEqual(acquisition['owner_before'],self.owner)
        self.assertEqual(self.base.read_json(acquisition['completed_slot_transition']['after']['archive']),dict(tag='early'))
        with self.assertRaises(RuntimeError):snap.freeze(phase=self.phase)

    def test_failed_freeze_cannot_retry_and_symlink_is_not_adopted(self):
        snap=self.snapshot();snap.start(self.raw,adapter.four(self.raw));self.complete(snap)
        original=snap.target;saved=self.root/'other';original.rename(saved);original.symlink_to(saved)
        with self.assertRaises(OSError):snap.freeze(phase=self.phase)
        original.unlink();saved.rename(original)
        with self.assertRaises(RuntimeError):snap.freeze(phase=self.phase)

    def make_early(self, executor=None):
        submitted=[]
        early=helper.EarlyInsurance(adapter,self.base,self.runtime,self.spec,self.root/'early',
            executor=executor,spawn=lambda function:submitted.append(function),clock=lambda:self.now[0],
            wall=lambda:100+self.now[0],run=lambda argv,**kw:'actual mocked unit text')
        return early,submitted

    def begin_early(self, executor=None):
        early,submitted=self.make_early(executor)
        with patch.object(adapter,'expected_start',return_value=dict(metric='kl')):
            self.assertEqual(early.start()['status'],'PENDING')
        self.complete(early.snapshot);early.tick()
        return early,submitted

    def test_completed_early_tick_submits_once_without_copy_or_CPU_on_poll_thread(self):
        early,submitted=self.begin_early()
        self.assertEqual(len(submitted),1);self.assertEqual(early.result()['status'],'PENDING')
        self.assertFalse((early.snapshot.output/'model-readonly-copy.pt').exists())
        for _ in range(3):early.tick()
        self.assertEqual(len(submitted),1)

    def test_background_returns_new_insurance_and_actual_provenance_context(self):
        class Executor:
            def run_once(inner,early,job_pin,verifier,directory):
                job=self.base.read_json(job_pin)
                self.assertEqual(job['mode'],'insurance');self.assertEqual(job['insurance']['trainer'],self.owner)
                self.assertEqual(job['source_control_context']['archived_trainer_unit']['path'],str(early.output/'trainer-unit-cat.txt'))
                pin=publish(directory/'report.json',dict(status='PASS'))
                return dict(insurance_report=pin,successful_execution=pin,successful_completion=pin,successful_result=pin)
        early,submitted=self.begin_early(Executor());submitted[0]()
        result=early.result();self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['verifier']['python_binding']['successful_result'],result['insurance_report'])
        self.assertEqual(result['insurance_report'],result['insurance_verification'])
        self.assertEqual(self.calls[-1][0],'python_binding')
        saved=self.base.read_json(result['saved_receipt']);self.assertEqual(saved['tag'],'early')
        self.assertTrue(saved['no_trainer_actor_stop_or_recipe_source_change'])

    def test_background_first_failure_is_retained_and_never_resubmitted(self):
        calls=[]
        class Executor:
            def run_once(inner,*args):calls.append('firstCPU');raise RuntimeError('original CPU failure')
        early,submitted=self.begin_early(Executor());submitted[0]()
        self.assertEqual(early.result()['status'],'FAILED');self.assertIn('original CPU failure',early.result()['error'])
        early.tick();self.assertEqual(calls,['firstCPU']);self.assertEqual(len(submitted),1)
        self.assertTrue((early.output/'early-insurance-failure.json').exists())

    def test_registration_precedes_actual_identity_and_replacement_is_rejected(self):
        early,_=self.make_early();self.assertIsNone(early.registration())
        request=dict(unit=self.spec['cpu_unit'],owner=None)
        early.register_request(request);self.assertIsNone(early.registration()['owner'])
        cpu=dict(self.owner,unit=self.spec['cpu_unit']);early.adopt_cpu(cpu);early.adopt_cpu(cpu)
        with self.assertRaises(RuntimeError):early.adopt_cpu(dict(cpu,starttime_ticks=999))
        with self.assertRaises(RuntimeError):early.register_request(request)

    def test_carrier_birth_is_locked_and_registered_before_wait_then_reaped_once(self):
        early,_=self.make_early();early.register_request(dict(unit=self.spec['cpu_unit'],owner=None,carrier=None))
        class Process:
            pid=456;returncode=None
            def communicate(inner,timeout):
                registered=early.registration()['carrier']
                self.assertEqual((registered['pid'],registered['starttime_ticks']),(456,99))
                self.assertFalse(registered['reaped']);inner.returncode=0;return 'scheduled',''
            def poll(inner):return inner.returncode
            def terminate(inner):inner.returncode=-15
        process=Process()
        def create(*args,**kwargs):self.assertTrue(early._lock.locked());return process
        data='456 (carrier) S '+' '.join(['0']*18+['99'])
        with patch.object(helper.subprocess,'Popen',side_effect=create),patch.object(Path,'read_text',return_value=data):
            self.assertEqual(early.schedule(['systemd-run','exact']),'scheduled')
            self.assertTrue(early.registration()['carrier']['reaped'])
            with self.assertRaises(RuntimeError):early.schedule(['systemd-run','retry'])

    def retained_case(self, exit_code=0, registered=True):
        early,_=self.make_early();directory=self.root/'unit';directory.mkdir()
        report_root=self.root/'numeric';report_root.mkdir()
        verifier=copy.deepcopy(self.runtime.job['verifier'])
        job=publish(self.root/'job.json',dict(output_directory=str(report_root)))
        report=publish(report_root/'cpu-verification.json',dict(status='PASS',mode='insurance',
            job_file=dict(sha256=job['sha256']),root_job=self.base.read_json(job)))
        owner=dict(self.owner,unit=self.spec['cpu_unit']);events=[];started=[False];released=set()
        def run(argv,**kw):
            if argv[0]=='systemd-run':
                events.append('schedule');self.assertIsNotNone(early.registration());self.assertIsNone(early.registration()['owner'])
                if registered:early.adopt_cpu(owner)
                started[0]=True;return 'scheduled'
            if argv[:3]==['systemctl','--user','show']:
                name=argv[3]
                if not started[0] or name in released or name.endswith('.timer'):return 'LoadState=not-found\n'
                return ('LoadState=loaded\nActiveState=inactive\nSubState=dead\nExecMainPID=123\nExecMainCode=1\n'
                    +'ExecMainStatus='+str(exit_code)+'\nResult='+('success' if exit_code==0 else 'exit-code')+'\n'
                    +'InvocationID='+'a'*32+'\nControlGroup=/owned\nExecMainStartTimestampMonotonic=12000000\nNRestarts=0\n')
            if argv[:3]==['systemctl','--user','stop']:
                self.assertTrue((directory/'original-execution-completion.json').exists())
                self.assertIsNotNone(early.registration()['terminal_archive'])
                events.append('release');released.add(argv[3]);return ''
            return 'original unit/journal text'
        executor=helper.RetainedCPU(self.base,run=run,schedule=lambda helper,argv:run(argv,timeout=2),
                                    clock=lambda:11,sleep=lambda _:None)
        return executor,early,job,verifier,directory,events,report

    def test_retained_unit_records_original_before_release_and_exact_7d_argv(self):
        executor,early,job,verifier,directory,events,report=self.retained_case()
        result=executor.run_once(early,job,verifier,directory)
        self.assertEqual(result['insurance_report'],report)
        execution=self.base.read_json(result['successful_execution'])
        self.assertEqual(execution['command'][1:5],['-Xgil=0','-I','-B','-u'])
        self.assertIn('--property=MemoryMax=3G',execution['argv'])
        self.assertIn('--property=TasksMax=64',execution['argv'])
        self.assertNotIn('/usr/bin/env',execution['argv'])
        self.assertIn('--property=UnsetEnvironment=LD_PRELOAD PYTHONPATH',execution['argv'])
        self.assertIn('--setenv=CUDA_VISIBLE_DEVICES=',execution['argv'])
        self.assertEqual(events,['schedule','release'])
        self.assertTrue(self.base.read_json(result['successful_result'])['original_archived_before_release'])
        registry=early.registration()
        self.assertEqual(registry['terminal_archive'],result['successful_completion'])
        self.assertEqual(registry['release'],result['successful_result'])

    def test_original_CPU_failure_is_archived_and_failed_unit_not_released(self):
        executor,early,job,verifier,directory,events,_=self.retained_case(1)
        with self.assertRaises(RuntimeError):executor.run_once(early,job,verifier,directory)
        self.assertEqual(events,['schedule'])
        completion=self.base.read_json(fingerprint(directory/'original-execution-completion.json'))
        self.assertEqual(completion['original_exit'],1);self.assertFalse(completion['unit_released'])
        self.assertIsNotNone(early.registration()['terminal_archive'])
        self.assertIsNone(early.registration()['release'])

    def test_registered_CPU_already_gone_uses_retained_terminal_before_release(self):
        executor,early,job,verifier,directory,_,_=self.retained_case()
        original=Path.read_text
        def no_proc(path,*args,**kwargs):
            self.assertFalse(str(path).startswith('/proc/'),'No vanished process may invent a fresh identity')
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',new=no_proc):
            result=executor.run_once(early,job,verifier,directory)
        completion=self.base.read_json(result['successful_completion'])
        self.assertEqual(completion['original_owner'],early.registration()['owner'])
        self.assertEqual(completion['original_nrestarts'],0)

    def test_unregistered_fast_terminal_is_archived_but_never_adopted_or_released(self):
        executor,early,job,verifier,directory,events,_=self.retained_case(registered=False)
        with self.assertRaises(RuntimeError):executor.run_once(early,job,verifier,directory)
        self.assertEqual(events,['schedule']);self.assertIsNone(early.registration()['owner'])
        self.assertIsNone(early.registration()['terminal_archive'])
        self.assertTrue((directory/'original-execution-completion.json').exists())

    def test_wrong_live_client_scope_refuses_without_request(self):
        early,_=self.make_early();self.raw['client_count']=0
        with self.assertRaises(RuntimeError):early.start()
        self.assertFalse((self.model/'managed_save.request.json').exists())


if __name__ == '__main__':unittest.main()
