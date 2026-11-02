"""Current capture metadata contracts; unit/process/provenance callbacks mocked.

Use actual immutable current plan/template inputs, synthesized capture records,
and real small private files for copy/mode checks. Never load a model or launch.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

HERE=Path(__file__).resolve().parent
P=HERE.parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
N=P.parent/'profile06-production-continuity-live-controller-original01-preparation-20261021'
H=P.parent/'profile06-production-continuity-main-inputs-original01-preparation-20261021'


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


v=load(HERE/'current_window_provenance_v1.py','_current_capture_values_target')
p=load(HERE/'prepare_current_candidate_CPU_v1.py','_current_capture_preparer_target')
files=load(P/'sources-original02/owned_candidate_capture_v1.py','_current_capture_contract_files')
reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_current_capture_contract_reader')
linux=load(N/'sources/handoff_linux_v1.py','_current_capture_contract_publish')
controller=load(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py','_current_capture_contract_controller')


def values():
    plan=json.loads((P/'tested-window-plan-original01.json').read_bytes());binding=reader.read_pin(plan['binding'])
    owner=plan['owner'];tag=plan['capture_tag'];source_path=G/'models_dqn/managed-checkpoints'/(tag+'.pt')
    before_raw=(H/'live-original01/startup-slot-after.json').read_bytes();request=(json.dumps(dict(tag=tag))+'\n').encode()
    def entry(path,mode,inode,sha,bytes):
        return dict(path=str(path),sha256=sha,bytes=bytes,identity=dict(device=2304,inode=inode,bytes=bytes,
            mtime_ns=1000000000,ctime_ns=1000000000,mode=mode,uid=1001,nlink=1))
    source=entry(source_path,'0o664',1,'a'*64,275186008)
    archive=entry(P/'capture-original01/candidate-readonly.pt','0o444',2,'a'*64,275186008)
    slot=G/'models_dqn/managed_save.request.json.completed'
    before=dict(actual_pin=entry(slot,'0o664',3,hashlib.sha256(before_raw).hexdigest(),len(before_raw)),archive={})
    after=dict(actual_pin=entry(slot,'0o664',4,hashlib.sha256(request).hexdigest(),len(request)),archive={})
    captured=dict(status='ORIGINAL_CAPTURE_ARCHIVED_NORMAL_PRODUCER_PRESERVED',owner=owner,controller=dict(pid=123),
        source=source,checkpoint=archive,normal_producer_mode_preserved=True,original_request_retried=False,
        completed_slot_transition=dict(before=before,after=after))
    result=dict(status='CAPTURED_FIRST_BOTH_HORIZONS',owner=owner,checkpoint=archive,normal_producer=source,
        CPU_verified=False,quality_qualified=False,promotion=False,latch=dict(path='original-latch'),completed_slot_transition=captured['completed_slot_transition'])
    capture_job=dict(mode='production',owner=owner,tag=tag,source=plan['capture_source'],controller_source=plan['capture_source'],
        main_binding=plan['binding'],latch=result['latch'])
    publication=dict(owner=owner,controller=captured['controller'],request=entry(G/'models_dqn/managed_save.request.json','0o444',5,
        hashlib.sha256(request).hexdigest(),len(request)),hold_started_unix_s=1000.0,request_unix_s=1000.1,hold_released_unix_s=1000.2)
    watch=dict(status='ORIGINAL_CONTROLLER_EXIT_OBSERVED',controller_alive=False,restart_retry=False,
        recovery=dict(status='NO_RECORDED_SAVE_HOLD',runtime_changed=False))
    return plan,binding,result,captured,capture_job,publication,watch,request,before_raw,request


class CurrentCaptureContracts(unittest.TestCase):
    def test_new_fixed_reference_preserves_all_fresh_independent_gates(self):
        plan,*_=values();q=v.quality_policy(plan['reference'],plan['source_package'])
        self.assertEqual(q['reference_sha256'],v.REFERENCE_SHA);self.assertEqual(q['all_slots'],list(range(4096,4128)))
        self.assertEqual((q['individual_mean_ratio'],q['individual_median_ratio']),(1.05,1.0))
        self.assertTrue(q['full_tails']);self.assertFalse(q['extensions']);self.assertTrue(q['no_historical_rows'])

    def test_old_reference_and_unselected_package_rejected(self):
        plan,*_=values()
        for key in ['reference','source_package']:
            bad=copy.deepcopy(plan);bad[key]['sha256']='0'*64
            with self.assertRaises(ValueError):v.quality_policy(bad['reference'],bad['source_package'])

    def test_normal_producer_and_distinct_readonly_capture_values_pass(self):
        v.validate_capture_values(*values())

    def reject(self,mutate):
        data=list(values());mutate(data)
        with self.assertRaises(ValueError):v.validate_capture_values(*data)

    def test_readonly_producer_is_rejected_instead_of_chmodded(self):
        self.reject(lambda a:a[3]['source']['identity'].update(mode='0o444'))

    def test_writable_evaluation_archive_is_rejected(self):
        self.reject(lambda a:a[3]['checkpoint']['identity'].update(mode='0o664'))

    def test_source_archive_alias_and_byte_mismatch_rejected(self):
        self.reject(lambda a:a[3]['checkpoint']['identity'].update(inode=1))
        self.reject(lambda a:a[3]['checkpoint'].update(sha256='b'*64))

    def test_noncanonical_source_or_private_fixture_capture_rejected(self):
        self.reject(lambda a:a[3]['source'].update(path='/tmp/other.pt'))
        self.reject(lambda a:a[4].update(mode='private_kernel_fixture'))

    def test_foreign_capture_owner_or_source_rejected(self):
        self.reject(lambda a:a[4].update(owner=dict(pid=3170722)))
        self.reject(lambda a:a[4].update(source=dict(sha256='0'*64)))

    def test_request_hardlink_count_and_writable_request_rejected(self):
        self.reject(lambda a:a[5]['request']['identity'].update(nlink=2))
        self.reject(lambda a:a[5]['request']['identity'].update(mode='0o664'))

    def test_request_checksum_and_completion_tag_mismatch_rejected(self):
        self.reject(lambda a:a[5]['request'].update(sha256='0'*64))
        self.reject(lambda a:a.__setitem__(9,b'{"tag":"foreign"}\n'))

    def test_previous_completed_slot_must_match_original_held_baseline(self):
        self.reject(lambda a:a[1]['held_hashes'].update({str(G/'models_dqn/managed_save.request.json.completed'):'0'*64}))

    def test_watch_recovery_or_live_controller_cannot_be_normalized_to_success(self):
        self.reject(lambda a:a[6].update(controller_alive=True))
        self.reject(lambda a:a[6].update(recovery=dict(status='EXACT_RECORDED_SAVE_OWNER_THAWED',runtime_changed=True)))
        self.reject(lambda a:a[6].update(status='ORIGINAL_WATCH_FAILURE_PRESERVED'))

    def test_publication_time_reversal_or_nonfinite_values_rejected(self):
        self.reject(lambda a:a[5].update(hold_released_unix_s=999.0))
        self.reject(lambda a:a[5].update(request_unix_s=float('nan')))

    def test_CPU_or_quality_flag_cannot_be_prematurely_true(self):
        self.reject(lambda a:a[2].update(CPU_verified=True))
        self.reject(lambda a:a[2].update(quality_qualified=True))

    def test_historical_slot_keeps_full8_and_checks_real_archive_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'slot';path.write_bytes(b'{"tag":"private"}\n');path.chmod(0o664)
            original=files.full_pin(path);archive=files.publish(path.with_name('archive'),path.read_bytes())
            pair=dict(actual_pin=original,archive=archive)
            self.assertEqual(v.historical_slot(pair,path,lambda e,flag:files.checked(e)),path.read_bytes())
            bad=copy.deepcopy(pair);bad['actual_pin']['identity'].pop('ctime_ns')
            with self.assertRaises(ValueError):v.historical_slot(bad,path,lambda e,flag:files.checked(e))
            self.assertEqual(files.full_pin(path),original)

    def test_original_resource_bounds_accept_hours_and_reject_weakened_scope(self):
        fields=dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='1h 35min',
            TasksMax='128',TimeoutStopUSec='5s',Restart='no',SendSIGKILL='no')
        v.resources(fields,5700)
        for key,value in [('MemoryMax',str(8<<30)),('RuntimeMaxUSec','1h'),('Restart','on-failure'),('SendSIGKILL','yes')]:
            bad=dict(fields);bad[key]=value
            with self.assertRaises(ValueError):v.resources(bad,5700)

    def test_original_command_rejects_substituted_job_or_wrapper(self):
        config=dict(output='/private/execution',argv=['/usr/bin/python3.12','-I','-B','/private/window.py','--job','/private/job.json'])
        argv=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1','TMPDIR=/private/execution/tmp']+config['argv']
        fields=dict(ExecStart='{ path=/usr/bin/env ; argv[]='+shlex.join(argv)+' ; ignore_errors=no ; metadata ; }')
        v.command(fields,config)
        bad=copy.deepcopy(config);bad['argv'][-1]='/private/foreign.json'
        with self.assertRaises(ValueError):v.command(fields,bad)

    def test_same_PID_with_another_birth_or_invocation_is_rejected(self):
        owner=dict(pid=1,starttime_ticks=2,unit='private.service',invocation_id='a'*32)
        v.common_owner(dict(owner,cgroup='/private'),owner)
        for key,value in [('starttime_ticks',3),('invocation_id','b'*32)]:
            bad=dict(owner);bad[key]=value
            with self.assertRaises(ValueError):v.common_owner(bad,owner)

    def exercise_preparation(self,root,*,guard_failure=False,producer_readonly=False):
        template_pin=files.full_pin(H/'live-original01/startup/CPU-job.json');template=reader.read_pin(template_pin)
        binding=reader.read_pin(json.loads((P/'tested-window-plan-original01.json').read_bytes())['binding'])
        model=root/'models';(model/'managed-checkpoints').mkdir(parents=True)
        tag='private_metadata_copy';source=model/'managed-checkpoints'/(tag+'.pt')
        source.write_bytes(b'PRIVATE_NON_MODEL_COPY_CONTRACT');source.chmod(0o444 if producer_readonly else 0o664)
        original=files.full_pin(source);candidate=files.publish(root/'evaluation.pt',source.read_bytes())
        control_raw=reader.read_pin(template['source_control_context']['archived_control'],as_json=False)
        (model/'learning_control.json').write_bytes(control_raw)
        unit=reader.read_pin(template['source_control_context']['archived_trainer_unit'],as_json=False)
        marker=files.publish(root/'original-fixture-marker.json',dict(scope='mocked closed provenance callback'))
        proof=dict(window_view=dict(owner=template['phase_snapshot']['owner'],experiment=template['experiment'],tag=tag,
            phase=dict(record=template['phase_snapshot']['phase_record'])),normal_producer=original,evaluation_candidate=candidate,
            clock_floor={key:template['clock_floor'][key] for key in v.CLOCKS},main_after=binding,
            original_window_result=marker,original_window_latch=marker,original_capture_result=marker,
            original_capture_job=marker,original_watch_result=marker,original_publication=marker,
            phase_CPU_transition=dict(before=None,request=dict(),after=dict(),before_unix_s=1,request_unix_s=2,after_unix_s=3))
        rawroot=dict(schema='robotron-current-window-candidate-CPU-preparation-v1',provenance_source=files.full_pin(HERE/'current_window_provenance_v1.py'),
            CPU_template=template_pin,CPU_controller=files.full_pin(G/'tools/quality_capacity_proposal/control_quality32_review_v1.py'),
            linux_source=files.full_pin(N/'sources/handoff_linux_v1.py'),main_guard=files.full_pin(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py'),
            archive_checker=files.full_pin(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'),
            window_plan=marker,window_job=marker,window_owner=marker,window_closure=marker,
            destination=str(root/'candidate-CPU-original01'),CPU_unit='robotron-profile06-production-next8M-candidate-CPU-original01-20261021.service')
        root_pin=files.publish(root/'root-job.json',rawroot)
        guarded=Mock(side_effect=ValueError('injected changed main holds') if guard_failure else None)
        def selected(entry,name,read):
            if 'provenance_' in name:return SimpleNamespace(review=lambda *args:proof)
            if 'archives_' in name:return SimpleNamespace(archived_closure=object())
            if 'linux_' in name:return SimpleNamespace(live_owner=lambda owner:None,publish=linux.publish,process_start=lambda pid:None,show=lambda unit:{})
            if 'main_guard_' in name:return SimpleNamespace(owner_and_files=guarded)
            if 'CPU_controller_' in name:return controller
            self.fail('Unexpected dependency '+name)
        with (patch.object(p,'P',root),patch.object(p,'MODEL',model),patch.object(p,'checked',side_effect=selected),
            patch.object(p.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=unit))):
            if guard_failure or producer_readonly:
                with self.assertRaises(ValueError):p.prepare(rawroot,root_pin,reader)
                result=None
            else:result=p.prepare(rawroot,root_pin,reader)
        return result,original,candidate,guarded,root/'candidate-CPU-original01'

    def test_real_private_copy_keeps_normal_producer_and_evaluation_archive_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            result,source,candidate,guarded,destination=self.exercise_preparation(Path(directory))
            self.assertEqual(files.full_pin(source['path']),source);self.assertEqual(source['identity']['mode'],'0o664')
            self.assertEqual(result['candidate'],candidate);self.assertEqual(result['verification_copy']['identity']['mode'],'0o444')
            self.assertEqual(len({entry['identity']['inode'] for entry in [source,candidate,result['verification_copy']]}),3)
            job=reader.read_pin(result['CPU_job']);self.assertEqual(job['source'],source)
            self.assertEqual(job['phase_snapshot']['purpose'],'candidate');self.assertEqual(job['phase_snapshot']['boot_checkpoint']['sha256'],p.BOOT_SHA)
            self.assertFalse(result['CPU_verified']);guarded.assert_called_once()

    def test_failed_main_hold_check_creates_no_CPU_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            result,source,candidate,guarded,destination=self.exercise_preparation(Path(directory),guard_failure=True)
            self.assertIsNone(result);self.assertFalse(destination.exists());self.assertEqual(files.full_pin(source['path']),source)

    def test_readonly_producer_is_not_accepted_by_metadata_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            result,source,candidate,guarded,destination=self.exercise_preparation(Path(directory),producer_readonly=True)
            self.assertIsNone(result);self.assertFalse(destination.exists());self.assertEqual(files.full_pin(source['path']),source)

    def test_default_CPU_preparer_performs_no_IO_or_launch(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Unexpected IO')),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(p.main([]),0);self.assertIn('PLAN_ONLY',output.getvalue())
