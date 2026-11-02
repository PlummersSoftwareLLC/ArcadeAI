"""Authored/unexecuted stdlib recovery metadata guards; all owners and I/O are fake."""
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('_CE2048_trial02_failed_return_repair',Path(__file__).with_name('run_forward_ce_repair.py'))
repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)
CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count')


def fixture():
    owner=dict(pid=9,starttime_ticks=10,invocation_id='a'*32,unit='fake.service',cgroup='/fake')
    phase=dict(metric='ce',valid=True,phase_id='fake_failed_return')
    source=dict(path='/fake/models/robotron_dqn_latest.pt',sha256='b'*64,bytes=100)
    old=dict(owner=owner,purpose='startup',observed_clients=0,phase_record='record',boot_checkpoint='boot',
        boot_verification=dict(path='/fake/boot.json',sha256='d'*64,bytes=10),expected_phase=phase)
    cpu=dict(phase_snapshot=dict(copy.deepcopy(old),purpose='newest_stopped',sources={}),source=source,
        verification_copy=dict(source,path='/fake/readonly.pt'),clock_floor={k:20 for k in CLOCKS})
    proof=dict(status='PASS',phase_metadata_verified=True,root_job=cpu,sha256=source['sha256'],bytes=100,
        saved_priority_metric_phase=copy.deepcopy(phase),held_recipe_context={'batch_size':4096},clocks={k:21 for k in CLOCKS})
    original=dict(model_dir='/fake/models',startup_tag='old_activation',baseline_csv={'batch_size':4096},
        before={'environment':{'DQN_BATCH_SIZE':'4096'}})
    failed=dict(status='FAILED',mode='return_batch4096',manual_recovery_required=True,qualification_pass=False,
        failed_requested_CE_retired=owner,final_resume={'failures':[]})
    startup=dict(status='PASS',phase_metadata_verified=True,root_job={'phase_snapshot':old},
        held_recipe_context={'batch_size':4096},clocks={k:20 for k in CLOCKS})
    report=dict(path='/fake/report.json',identity=dict(mode='0o444',nlink=1,uid=repair.os.getuid()))
    intent=dict(schema='robotron-CE2048-trial02-failed-return-forward-CE4096-repair-intent-v1',mode='return_ce',
        phase_id='fake_new_recovery',target_batch_size=4096,original_failed_trial='trial',original_failed_return='failed',
        no_trial_retry=True,newest_checkpoint=source)
    job=dict(schema=repair.SCHEMA,activation_job='original',trial_result='trial',return_job='returned',return_result='failed',
        failed_startup_CPU_report='startup',newest_CPU_job='cpu',newest_CPU_report=report,newest_CPU_release='release',
        repair_intent='intent',phase_id='fake_new_recovery',startup_tag='fake_new_startup')
    values=dict(original=original,trial=dict(status='FAILED',qualification_pass=False,CE_return='failed'),
        returned=dict(mode='return_batch4096',startup_tag='old_return',batch_boundary={'after_batch_size':4096}),
        failed=failed,startup=startup,cpu=cpu,report=proof,intent=intent,
        release=dict(status='PASS',original_exit=0,original_archived_before_release=True,unit_released=True,sha256=source['sha256']))
    base=NS(read_json=lambda p:values['report' if isinstance(p,dict) else p],pin=lambda *a,**k:None,MAX_SOURCE=4<<20)
    adapter=NS(CLOCKS=CLOCKS,triple=lambda v:{k:v[k] for k in ('path','sha256','bytes')})
    return job,values,base,adapter


class FailedReturnRepairContracts(unittest.TestCase):
    def test_default_plan_and_missing_inputs_do_not_import_or_read(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('No read')),patch.object(repair,'load',side_effect=AssertionError('No import')):
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(repair.main([]),0)
            with self.assertRaisesRegex(RuntimeError,'Explicit root bindings'):repair.main(['--execute'])

    def test_real_validation_requires_failed_return_current_phase_floor_and_original0(self):
        args=fixture();self.assertEqual(repair.validate(args[0],args[2],args[3])[-1],args[1]['failed']['failed_requested_CE_retired'])
        for kind in ('COMPLETE','wrong_return','owner','founder','floor','target2048','exit','old_baseline'):
            job,v,base,adapter=fixture()
            if kind=='COMPLETE':v['trial']['status']='COMPLETE'
            elif kind=='wrong_return':v['trial']['CE_return']='foreign'
            elif kind=='owner':v['failed']['failed_requested_CE_retired']={'pid':999}
            elif kind=='founder':v['cpu']['phase_snapshot']['expected_phase']={'metric':'ce','valid':True,'phase_id':'old_treatment'}
            elif kind=='floor':v['cpu']['clock_floor']['training_steps']=19
            elif kind=='target2048':v['intent']['target_batch_size']=2048
            elif kind=='exit':v['release']['original_exit']=2
            else:v['original']['baseline_csv']['batch_size']=2048
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):repair.validate(job,base,adapter)

    def test_actual_start_builds_one_new_previousCE_record_and_restores_override(self):
        job,v,base,adapter=fixture();calls=[];original=lambda *a:None;adapter.start_record=original
        runtime=NS(job={'before':{'environment':{'DQN_BATCH_SIZE':'4096'}}},recovery_saved_phase=v['report']['saved_priority_metric_phase'],
            current_checkpoint={'source':v['cpu']['source']},floor={k:20 for k in CLOCKS})
        def start():
            calls.append(adapter.start_record('return_ce','fake_new_recovery','c'*64,'/fake/models',v['cpu']['source'],v['report']))
            return {'fake_owner':True}
        runtime.start_phase=start
        self.assertEqual(repair.start_repair_CE4096(runtime,adapter),{'fake_owner':True});self.assertIs(adapter.start_record,original)
        self.assertEqual(len(calls),1);self.assertEqual(calls[0]['previous_metric'],'ce');self.assertEqual(calls[0]['metric'],'ce')

    def wait_fixture(self, rows, issues=None):
        owner={'pid':9};seen=[];clock=[100.0];start=dict(monotonic_s=100,unix_s=1000)
        def capture():
            seen.append('capture');row=copy.deepcopy(rows.pop(0));row.update(observed_unix_s=1002,observed_monotonic_s=clock[0]);return row
        def api(row,plan,previous):
            seen.append('guards')
            if issues:return list(issues)
            return ([] if row['csv']['batch_size']==4096 else ['CSV_recipe'])+([] if row['client_count']==192 else ['client_count'])
        runtime=NS(start_request='start',trainer_id=lambda:owner,inspect=lambda *a:seen.append('inspect'),
            fault_scan=lambda:[{'classification':'intentional_restart_compatible'}],host=NS(capture=capture),job={'baseline_csv':{'batch_size':4096,'replay_dropped':0}},
            metrics=NS(exposure_key=lambda v:v,api_issues=api))
        base=NS(read_json=lambda p:start)
        return runtime,base,seen,clock

    def row(self,batch,utc,clients=192):
        return dict(csv=dict(batch_size=batch,replay_sample_cap=8,utc=utc,replay_dropped=0),client_count=clients,
            exposure={k:{'process_id':9,'epoch':1} for k in ('optimizer','replay')})

    def test_actual_wait_accepts_only_old_pending_then_real_new4096_without_log_reset(self):
        rows=[self.row(2048,'1970-01-01T00:16:39+00:00',0),self.row(4096,'1970-01-01T00:16:41+00:00')]
        runtime,base,seen,clock=self.wait_fixture(rows)
        with patch.object(repair.time,'monotonic',side_effect=lambda:clock[0]),patch.object(repair.time,'sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
            result=repair.wait_current_CSV4096(runtime,base,110)
        self.assertEqual(result['status'],'PASS_CURRENT_OWNER_CE4096_CSV_PUBLICATION');self.assertEqual(len(result['observations']),2)
        self.assertEqual(seen,['inspect','capture','guards','inspect','capture','guards'])
        self.assertEqual(result['CSV']['batch_size'],4096)
        self.assertEqual(result['observations'][0]['compatible_transition_events'],[{'classification':'intentional_restart_compatible'}])

    def test_real_new_wrong_recipe_and_other_errors_or_deadline_fail_without_retry(self):
        for kind in ('newwrong','othererror','deadline'):
            rows=[self.row(2048 if kind=='newwrong' else 4096,'1970-01-01T00:16:41+00:00')]
            runtime,base,seen,clock=self.wait_fixture(rows,['new_runtime_log_error'] if kind=='othererror' else None)
            with self.subTest(kind=kind),patch.object(repair.time,'monotonic',side_effect=lambda:clock[0]),self.assertRaises(RuntimeError):
                repair.wait_current_CSV4096(runtime,base,99 if kind=='deadline' else 110)
            self.assertLessEqual(seen.count('capture'),1)

    def test_inherited_readiness_receives_only_original_start_deadline_remaining(self):
        calls=[];runtime=NS(job={},ready_transport=lambda *a,**k:calls.append(k) or {'ready':True})
        with patch.object(repair.time,'monotonic',side_effect=[105,106]):
            self.assertEqual(repair.ready_with_budget(runtime,{},actors=False,deadline=110),{'ready':True})
        self.assertEqual(runtime.job['readiness_timeout_s'],5);self.assertEqual(calls,[{'actors':False}])
        with patch.object(repair.time,'monotonic',return_value=111),self.assertRaises(RuntimeError):
            repair.ready_with_budget(runtime,{},actors=False,deadline=110)
        self.assertEqual(len(calls),1)

    def test_final_inherited_rearm_keeps_offsets_and_restores_exact_methods(self):
        calls=[];bindings={'/fake/log':{'device':1,'inode':2}}
        reader=NS(configure_logs=lambda selected:(_ for _ in ()).throw(AssertionError('No second reset')),
            log_errors=lambda:calls.append('read-increment') or [])
        runtime=NS(job={},host=NS(metric_host=reader),recovery_armed_logs=(reader,bindings))
        def inspect(phase):calls.append('inspect');return {'bindings':{'logs':bindings}}
        runtime.inspect=inspect;old_configure=reader.configure_logs
        def ready(phase,banks,*,actors):
            current=runtime.inspect(phase);reader.configure_logs(current['bindings']['logs']);calls.append('inherited-ready');return {'ready':True}
        runtime.ready_transport=ready
        with patch.object(repair.time,'monotonic',side_effect=[105,106]):
            self.assertEqual(repair.ready_with_budget(runtime,{},actors=True,deadline=110),{'ready':True})
        self.assertIs(runtime.inspect,inspect);self.assertIs(reader.configure_logs,old_configure)
        self.assertEqual(calls,['inspect','read-increment','inherited-ready'])
        reader.log_errors=lambda:['actual-error']
        with patch.object(repair.time,'monotonic',return_value=105),self.assertRaises(RuntimeError):
            repair.ready_with_budget(runtime,{},actors=True,deadline=110)
        self.assertIs(runtime.inspect,inspect);self.assertIs(reader.configure_logs,old_configure)


if __name__=='__main__':unittest.main()
