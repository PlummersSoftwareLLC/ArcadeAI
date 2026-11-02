"""Authored/unexecuted stdlib failed-startup recovery guards; no numeric/runtime calls."""
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('_CE2048_failed_startup_repair',HERE/'run_forward_ce_repair.py')
repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)
CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count')


def fixture():
    owner=dict(pid=9,starttime_ticks=10,invocation_id='a'*32,unit='synthetic.service',cgroup='/synthetic')
    phase=dict(metric='ce',valid=True,phase_id='synthetic_failed_phase')
    source=dict(path='/synthetic/models/robotron_dqn_latest.pt',sha256='b'*64,bytes=100)
    cpu=dict(phase_snapshot=dict(purpose='newest_stopped',owner=owner,observed_clients=0,
        expected_phase=copy.deepcopy(phase),sources={}),source=source,
        verification_copy=dict(source,path='/synthetic/readonly-copy.pt'),clock_floor={key:20 for key in CLOCKS})
    proof=dict(status='PASS',phase_metadata_verified=True,root_job=cpu,sha256=source['sha256'],bytes=100,
        saved_priority_metric_phase=copy.deepcopy(phase),held_recipe_context={'batch_size':4096},clocks={key:21 for key in CLOCKS})
    original=dict(model_dir='/synthetic/models',startup_tag='synthetic_oldstartup',
        before={'environment':{'DQN_BATCH_SIZE':'4096'}},batch_boundary={'after_batch_size':2048})
    failed=dict(status='FAILED',mode='activate_batch2048',manual_recovery_required=True,qualification_pass=False,
        failed_new_owner_stopped=owner)
    report=dict(path='/synthetic/cpu-report.json',identity=dict(mode='0o444',nlink=1,uid=repair.os.getuid()))
    intent=dict(schema='robotron-CE2048-failed-startup-forward-CE4096-repair-intent-v1',mode='return_ce',
        phase_id='synthetic_new4096',target_batch_size=4096,original_failed_activation='failed',
        no_trial_retry=True,newest_checkpoint=source)
    job=dict(schema=repair.SCHEMA,activation_job='original',activation_result='failed',newest_CPU_job='cpu',
        newest_CPU_report=report,newest_CPU_release='release',repair_intent='intent',phase_id='synthetic_new4096',startup_tag='synthetic_newstartup')
    values=dict(original=original,failed=failed,cpu=cpu,report=proof,
        release=dict(status='PASS',original_exit=0,original_archived_before_release=True,unit_released=True,sha256=source['sha256']),intent=intent)
    def read(value):return values['report' if isinstance(value,dict) else value]
    base=SimpleNamespace(read_json=read,pin=lambda *a,**k:None,MAX_SOURCE=4<<20)
    adapter=SimpleNamespace(CLOCKS=CLOCKS,triple=lambda value:{k:value[k] for k in ('path','sha256','bytes')})
    return job,values,base,adapter


class FailedStartupRepairContracts(unittest.TestCase):
    def test_literal_plan_and_missing_bindings_precede_imports_or_reads(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('No read')),             patch.object(repair,'load',side_effect=AssertionError('No dependency import')):
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(repair.main([]),0)
            with self.assertRaisesRegex(RuntimeError,'Explicit root bindings'):repair.main(['--execute'])

    def test_actual_validation_requires_failed2048_and_actual_newest_validCE(self):
        job,values,base,adapter=fixture()
        checked=repair.validate(job,base,adapter)
        self.assertEqual(checked[-1],values['failed']['failed_new_owner_stopped'])
        changes=[('failed','mode','activate_kl'),('failed','status','READY'),('intent','target_batch_size',2048),
            ('report','phase_metadata_verified',False),('release','original_exit',1)]
        for object_name,key,value in changes:
            with self.subTest(object=object_name,key=key):
                job,values,base,adapter=fixture();values[object_name][key]=value
                with self.assertRaises(RuntimeError):repair.validate(job,base,adapter)
        for kind in ['metric','valid','batch','owner','floor']:
            with self.subTest(kind=kind):
                job,values,base,adapter=fixture()
                if kind=='metric':values['report']['saved_priority_metric_phase']['metric']='kl'
                elif kind=='valid':values['report']['saved_priority_metric_phase']['valid']=False
                elif kind=='batch':values['report']['held_recipe_context']['batch_size']=2048
                elif kind=='owner':values['cpu']['phase_snapshot']['owner']={'unknown':True}
                else:values['report']['clocks']['training_steps']=19
                with self.assertRaises(RuntimeError):repair.validate(job,base,adapter)

    def test_actual_start_override_builds_oneCE4096_record_and_restores_constructor(self):
        job,values,base,adapter=fixture();proof=values['report'];source=values['cpu']['source']
        calls=[];ordinary=lambda *a:calls.append('ordinary')
        adapter.start_record=ordinary
        runtime=SimpleNamespace(job=dict(before={'environment':{'DQN_BATCH_SIZE':'4096'}}),
            recovery_saved_phase=copy.deepcopy(proof['saved_priority_metric_phase']),
            current_checkpoint={'source':source},floor={key:20 for key in CLOCKS})
        def start():
            record=adapter.start_record('return_ce','synthetic_new4096','c'*64,'/synthetic/models',source,proof)
            calls.append(record);return {'synthetic_new_owner':True}
        runtime.start_phase=start
        self.assertEqual(repair.start_repair_CE4096(runtime,adapter),{'synthetic_new_owner':True})
        self.assertIs(adapter.start_record,ordinary)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['metric'],'ce');self.assertEqual(calls[0]['previous_metric'],'ce')
        self.assertEqual(calls[0]['checkpoint'],source)
        runtime.job['before']['environment']['DQN_BATCH_SIZE']='2048'
        with self.assertRaises(RuntimeError):repair.start_repair_CE4096(runtime,adapter)
        self.assertIs(adapter.start_record,ordinary)
        self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()
