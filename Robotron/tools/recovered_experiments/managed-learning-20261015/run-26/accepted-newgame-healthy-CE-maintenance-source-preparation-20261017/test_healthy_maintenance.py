"""Authored metadata/mocked-order guards; no test execution by the author."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import types
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
R=HERE.parent
SPEC=importlib.util.spec_from_file_location('_newgame_healthy_metadata',HERE/'run_healthy_ce_maintenance.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)


def read(path):return json.loads(Path(path).read_text())

def fixture():
    # Genuine historical saved small JSON leaves, never checkpoint/stat/body.
    release=read(R/'lr25-prechange-entry-numeric-CPU-root-execution-20261017/root-original-entry-CPU-result-and-owned-release.json')
    entry_pin=release['CPU_report'];entry=read(entry_pin['path'])
    prior_path=R/'CE2048-trial02-failed-return-forward-CE4096-repair-20261017/result.json'
    prior=read(prior_path);prior_job=read(prior['root_job']['path'])
    cfg=copy.deepcopy(read(prior_job['activation_job']['path']))
    pin=lambda name,sha='a'*64:dict(path='/synthetic-future/'+name,sha256=sha,bytes=1,identity=dict(mode='0o444',uid=M.os.getuid(),nlink=1))
    cfg.update(mode='return_ce',running_phase=copy.deepcopy(prior['startup']['phase']),
        phase_id='synthetic_newgame_maintenance_CE',request_id='synthetic_newgame_start',startup_tag='synthetic_newgame_startup')
    cfg['before']['trainer'].update(MainPID=str(M.CURRENT_OWNER['pid']),ControlGroup=M.CURRENT_OWNER['cgroup'])
    cfg['before']['bindings']['worker']['trainer'].update(pid=M.CURRENT_OWNER['pid'],starttime_ticks=M.CURRENT_OWNER['starttime_ticks'])
    cfg['before']['environment'].update(DQN_BATCH_SIZE='4096',DQN_PER_PRIORITY_METRIC='ce',
        DQN_PRIORITY_PHASE_RECORD=cfg['running_phase']['record']['path'],DQN_PRIORITY_PHASE_RECORD_SHA256=M.CURRENT_PHASE_RECORD_SHA)
    cfg['sources']=[dict(destination=str(M.SOCKET),before=dict(pin('old_socket',M.BEFORE_SHA),path=str(M.SOCKET)),after=pin('new_socket',M.AFTER_SHA))]
    cfg['static_pins']=[p for p in cfg['static_pins'] if p['path']!=str(M.SOCKET)]
    cfg['verifier']['context']=copy.deepcopy(entry['root_job']['source_control_context'])
    cfg['helper_pins']['controller']=dict(pin('adapter',M.ADAPTER_SHA),path=str(M.ADAPTER))
    true_v4=M.GAME/'tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/live8_maintenance_proposal/revision4/run_live8_maintenance.py'
    true_v4_sha='fdf7c8bfb123b494252acf83d724a51acda95bb7f00877eace28b60d0377ed18'
    cfg['helper_pins']['v4']=dict(pin('v4',true_v4_sha),path=str(true_v4))
    release_pin=pin('CURRENT_partial_release');guard_pin=pin('CURRENT_original_seven_guards')
    intent_pin=pin('healthy_maintenance_intent');cfg['trial_core']=intent_pin
    prior_pin=dict(pin('prior', 'b4019062ff5275e842156a643818a6d8205d702e0fce0c5a51ab18d493f5d3b0'),path=str(prior_path))
    patch_pin=copy.deepcopy(read(M.ACTUAL_PATCH_GUARDS['path'])['source_manifest'])
    owned_release_pin=pin('entry_owned_release')
    job=dict(schema=M.SCHEMA,activation_authorized=True,transition=cfg,entry_CPU=entry_pin,entry_CPU_release=owned_release_pin,
        quality_release=release_pin,patch_manifest=patch_pin,patch_guard_result=guard_pin,maintenance_intent=intent_pin)
    current_release=read(M.ACTUAL_RELEASE['path'])
    guards=read(M.ACTUAL_PATCH_GUARDS['path'])
    guards['freeze_release']=release_pin
    intent=dict(schema='robotron-accepted-newgame-healthy-CE-maintenance-intent-v1',owner=M.CURRENT_OWNER,
        running_phase=cfg['running_phase'],phase_id=cfg['phase_id'],socket_before_sha256=M.BEFORE_SHA,socket_after_sha256=M.AFTER_SHA,
        quality_release=release_pin,patch_guard_result=guard_pin,boot_newest_only=True,no_weight_or_optimizer_rollback=True,
        retain_original_fleet=True,target_batch_size=4096,target_lr_scale=.5,prior_maintenance=prior_pin,
        original_failed_trial=prior_job['trial_result'],original_failed_return=prior_job['return_result'])
    values={entry_pin['path']:entry,owned_release_pin['path']:release,release_pin['path']:current_release,
        guard_pin['path']:guards,intent_pin['path']:intent,patch_pin['path']:{},prior_pin['path']:prior,
        prior['root_job']['path']:prior_job,cfg['running_phase']['record']['path']:read(cfg['running_phase']['record']['path']),
        cfg['running_phase']['boot_verification']['path']:read(cfg['running_phase']['boot_verification']['path'])}
    base=types.SimpleNamespace(MAX_JSON=2<<20,MAX_SOURCE=2<<20,pin=lambda *a:None,
        read_json=lambda p:copy.deepcopy(values[p['path']]),validate_python_binding=lambda *a,**k:None)
    # The exact existing pure expected_start body, extracted without module import.
    adapter_path=M.ADAPTER;tree=__import__('ast').parse(adapter_path.read_text())
    n=next(n for n in tree.body if isinstance(n,__import__('ast').FunctionDef) and n.name=='expected_start')
    ns={'four':lambda value:{k:value[k] for k in ('training_steps','optimized_samples','learner_frame_count','frame_count')}}
    exec(compile(__import__('ast').Module(body=[n],type_ignores=[]),str(adapter_path),'exec'),ns)
    adapter=types.SimpleNamespace(PHASE_SHA=entry['root_job']['verifier_sha256'],STRICT_SHA=entry['root_job']['strict_phase_base_sha256'],
        PHASE=Path(cfg['phase_verifier']['script']['path']),V4=true_v4,V4_SHA=true_v4_sha,
        triple=lambda p:{k:p[k] for k in ('path','sha256','bytes')},
        CLOCKS=('training_steps','optimized_samples','learner_frame_count','frame_count'),
        FLAGS=('DQN_RECOMPUTED_CE_CAPTURE_DIR','DQN_EXECUTED_CE_TRACE_DIR'),expected_start=ns['expected_start'],
        CANDIDATE={name:cfg['before']['bindings']['source_hashes'][str(M.GAME/'Scripts/dqn'/name)]
            for name in ('agent.py','training.py','loss_kernel.py','config.py','priority_phase.py')})
    return job,base,adapter,values,entry


class HealthyMaintenanceContracts(unittest.TestCase):
    def checked(self,job,base,adapter):
        with mock.patch.object(M,'ACTUAL_RELEASE',adapter.triple(job['quality_release'])),mock.patch.object(M,'ACTUAL_PATCH_GUARDS',adapter.triple(job['patch_guard_result'])):
            return M.validate(job,base,adapter)

    def test_actual_historical_phase_entry_shape_and_newest_only_scope(self):
        job,base,adapter,values,entry=fixture()
        self.assertNotEqual(entry['saved_priority_metric_phase']['phase_id'],M.CURRENT_PHASE_RECORD_SHA)
        cfg,actual=self.checked(job,base,adapter)
        self.assertEqual(actual,entry)
        self.assertEqual(cfg['running_phase']['expected']['phase_id'],'ce4096_forward_after_failed_return_trial02_20261017')
        self.assertNotEqual(cfg['insurance_verification'],job['entry_CPU'])
        for mutation in ('phase_id_is_hash','wrong_owner','two_sources','wrong_after','old_release','old_v4'):
            j=copy.deepcopy(job);v=copy.deepcopy(values)
            if mutation=='phase_id_is_hash':v[j['entry_CPU']['path']]['saved_priority_metric_phase']['phase_id']=M.CURRENT_PHASE_RECORD_SHA
            if mutation=='wrong_owner':j['transition']['before']['bindings']['worker']['trainer']['pid']+=1
            if mutation=='two_sources':j['transition']['sources']*=2
            if mutation=='wrong_after':j['transition']['sources'][0]['after']['sha256']='f'*64
            if mutation=='old_release':v[j['quality_release']['path']]['schema']='old-winning-all4-release'
            if mutation=='old_v4':j['transition']['helper_pins']['v4']['sha256']='6f961e5c'+'0'*56
            b=copy.copy(base);b.read_json=lambda p:copy.deepcopy(v[p['path']])
            with self.subTest(mutation=mutation),self.assertRaises(RuntimeError):self.checked(j,b,adapter)

    def test_unbound_or_missing_current_release_and_original_seven_refuse(self):
        job,base,adapter,values,entry=fixture()
        with mock.patch.object(M,'ACTUAL_RELEASE',None),self.assertRaises(RuntimeError):M.validate(job,base,adapter)
        for key in ('source_freeze_released','owned_cleanup_complete','R2_C2_not_run'):
            values[job['quality_release']['path']][key]=False
            with self.subTest(key=key),self.assertRaises(RuntimeError):self.checked(job,base,adapter)
            values[job['quality_release']['path']][key]=True
        values[job['patch_guard_result']['path']]['tests_run']=6
        with self.assertRaises(RuntimeError):self.checked(job,base,adapter)

    def route(self,fail_newest=False):
        events=[];job,base,adapter,values,entry=fixture();cfg=job['transition'];boot=dict(source={},verification={'path':'newest-report'})
        proof=copy.deepcopy(entry);proof['status']='FAIL' if fail_newest else 'PASS';values['newest-report']=proof
        runtime=types.SimpleNamespace(job=cfg,insured=M.CURRENT_OWNER,floor={k:1 for k in ('training_steps','optimized_samples','learner_frame_count','frame_count')},
            output=Path('/synthetic-future/output'),cpu_attempts={},pending=None,start_request=None,record_pin={})
        runtime.initial_api={k:2 for k in runtime.floor}
        runtime.initial_api.update(ts=1,exposure=dict(optimizer=dict(process_id=M.CURRENT_OWNER['pid']),replay=dict(process_id=M.CURRENT_OWNER['pid'])))
        runtime.initial=lambda:events.append('fresh_initial') or cfg['before']
        runtime.host=types.SimpleNamespace(begin_transition_logs=lambda *a:events.append('arm_transition'),pause=lambda *a:events.append('pause192'),
            metric_host=types.SimpleNamespace(configure_logs=lambda *a:events.append('arm_runtime')))
        runtime.stop_owned=lambda *a:events.append('stop_exact_old') or M.CURRENT_OWNER
        def stopped(*args):
            events.append('NEW_stopped_latest_CPU');runtime.current_checkpoint=boot;return boot
        runtime.stopped_checkpoint=stopped
        runtime.banks=types.SimpleNamespace(stopped_state=lambda *a:events.append('stopped_ring_banks') or {},assert_unchanged=lambda *a:events.append('banks_unchanged'))
        runtime.absence=lambda:None;runtime.metrics=types.SimpleNamespace(block_restore_signals=contextlib.nullcontext,exposure_key=lambda x:dict(x))
        raw_before=dict({k:2 for k in runtime.floor},client_count=192,training_enabled=True,measurement_active=False,
            managed_experiment=cfg['experiment'],lr=2.5e-5,ts=1,host_pipeline=dict(learning_exposure=runtime.initial_api['exposure']))
        raws=iter([raw_before,dict(client_count=0),dict(client_count=0)])
        runtime.raw_api=lambda:next(raws)
        runtime.startup_snapshot=lambda raw:events.append('startup0_CPU') or dict(phase_CPU={})
        runtime.inspect=lambda *a:dict(bindings=dict(logs={}))
        sources=types.SimpleNamespace(stage=lambda:events.append('stage_sources'),reconcile=lambda *a:events.append('WRITE_socket_after_absence'))
        base.resume_all=lambda host:events.append('resume192') or dict(failures=[])
        base.publish=lambda *a:dict(path='saved-api');adapter.clock_max=lambda *xs:{k:max(x[k] for x in xs) for k in runtime.floor}
        adapter.source_state=lambda s:[];adapter.zero_replay=lambda *a:events.append('zero_new_process_exposure')
        def start(*a):events.append('ONE_new_CE_start');runtime.start_request={'path':'start'};return dict(pid=999)
        oldread=base.read_json;base.read_json=lambda p:dict(monotonic_s=0) if p['path']=='start' else oldread(p)
        with mock.patch.object(M,'start_repair_CE4096',side_effect=start),mock.patch.object(M,'archive_report',return_value={}),\
            mock.patch.object(M,'ready_with_budget',side_effect=lambda *a,**kw:events.append('ready192' if kw['actors'] else 'ready0') or {}),\
            mock.patch.object(M,'wait_current_CSV4096',side_effect=lambda *a:events.append('genuine_current_CSV4096') or {}):
            outcome=M.maintain(runtime,sources,base,adapter)
        return events,outcome

    def test_real_maintenance_order_and_failure_before_source_write_final_resume(self):
        events,outcome=self.route()
        self.assertEqual(outcome['status'],'READY_HEALTHY_CE_MAINTENANCE')
        for a,b in zip(('fresh_initial','pause192','stop_exact_old','NEW_stopped_latest_CPU','stopped_ring_banks','WRITE_socket_after_absence','ONE_new_CE_start','startup0_CPU','genuine_current_CSV4096'),
            ('pause192','stop_exact_old','NEW_stopped_latest_CPU','stopped_ring_banks','WRITE_socket_after_absence','ONE_new_CE_start','startup0_CPU','genuine_current_CSV4096','ready192')):
            self.assertLess(events.index(a),events.index(b))
        self.assertEqual(events.count('ONE_new_CE_start'),1);self.assertEqual(events[-1],'resume192')
        events,outcome=self.route(fail_newest=True)
        self.assertEqual(outcome['status'],'FAILED');self.assertNotIn('WRITE_socket_after_absence',events)
        self.assertNotIn('ONE_new_CE_start',events);self.assertEqual(events[-1],'resume192')

    def test_default_PLAN_does_not_read_or_load(self):
        with mock.patch.object(M,'load',side_effect=AssertionError('load')),mock.patch.object(Path,'read_bytes',side_effect=AssertionError('read')):
            with contextlib.redirect_stdout(io.StringIO()) as output:self.assertEqual(M.main([]),0)
        self.assertIn('PLAN_ONLY',output.getvalue())


if __name__=='__main__':unittest.main()
