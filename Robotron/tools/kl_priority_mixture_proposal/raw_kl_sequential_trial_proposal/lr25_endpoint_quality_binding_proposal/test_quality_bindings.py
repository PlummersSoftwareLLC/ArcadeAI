"""UNEXECUTED authored stdlib guards; actual historical JSON, synthetic future endpoint.

No application/numerical imports, live I/O or checkpoint-body operations. The
positive tests call production validate over mapped immutable metadata fixtures.
"""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).parent

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

M=module('_lr25_quality_binding_contract',HERE/'quality_bindings.py')
H=module('_lr25_quality_pure_observer_contract',M.OBSERVER)
C=module('_lr25_quality_carrier_contract',HERE/'root_quality_carrier.py')
A=module('_lr25_quality_auditor_contract',HERE/'audit_completed_leg.py')


def fixture():
    values={};serial=0
    def put(name,value,pin=None):
        nonlocal serial
        serial+=1;raw=H.encoded(value)
        if pin is None:
            pin=dict(path='/synthetic/unactivated/'+name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                identity=dict(device=1,inode=serial,bytes=len(raw),mtime_ns=1900000000000000000+serial,
                    ctime_ns=1900000000000000000+serial,mode='0o444',uid=os.getuid(),nlink=1))
        values[pin['path']]=copy.deepcopy(value);return pin
    def actual(key):
        p=Path(M.KNOWN_ACTUAL[key]['path']);raw=p.read_bytes()
        pin=dict(M.KNOWN_ACTUAL[key],identity=M.identity(p.lstat()))
        return put(p.name,json.loads(raw),pin)
    evidence={key:actual(key) for key in M.KNOWN_ACTUAL}
    driver=values[evidence['driver_job']['path']];pre=values[evidence['precommit']['path']];entry=values[evidence['entry_CPU']['path']]
    phase=pre['current_phase'];owner=pre['owner'];root=Path(driver['output_directory'])
    def api(offset=0,eligible=False,pending=0,restored=False):
        counts=dict(applied=100+(10 if eligible else 0),amp_skipped=5+(2 if eligible else 0),unavailable=0)
        counts['outcomes_recorded']=sum(counts.values());counts['attempts_started']=counts['outcomes_recorded']+pending
        ident=dict(process_id=owner['pid'],instance_monotonic_ns=9999,epoch=2,epoch_reason='synthetic_existing_epoch')
        cats=dict(dqn=1000000+(5500000 if eligible else 0),epsilon=200000+(500000 if eligible else 0),
            expert=500000+(1000000 if eligible else 0),eval=100000+(2000000 if eligible else 0),unattributed=0)
        clocks={k:entry['clocks'][k]+100+(8000000 if eligible and k=='learner_frame_count' else
            16000000 if eligible and k=='frame_count' else 100000 if eligible else 0)+offset for k in M.CLOCKS}
        return dict(clocks,client_count=192,training_enabled=True,measurement_active=False,
            managed_experiment=json.loads(Path(entry['root_job']['source_control_context']['archived_control']['path']).read_text())['experiment'] if restored else pre['experiment'],lr=2.5e-5 if restored else 1.25e-5,
            ts=1000000+offset,pipeline_snapshot_age_s=.25,pipeline_read_error='',grad_norm=float('nan'),
            host_pipeline=dict(learning_exposure=dict(optimizer=dict(ident,schema='robotron-optimizer-exposure-v1',enabled=True,
                available=pending==0,total=counts,since_epoch=copy.deepcopy(counts),unclassified_started_total=pending),
                replay=dict(ident,schema='robotron-replay-insert-exposure-v1',enabled=True,available=True,
                    accepted_total=sum(cats.values()),accepted_learner_total=cats['dqn']+cats['epsilon'],accepted_by_source_total=cats))))
    B=api();bp=put('raw-B-API.json',B);bp['path']=str(root/'raw-B-API.json');values[bp['path']]=B
    barrier_clock=dict(boot_id='syntheticboot',monotonic_s=999,wall_s=999999)
    evidence['barrier']=put('barrier.json',dict(frozen={'synthetic':'barrier only'},completed_clock=barrier_clock))
    original=json.loads(Path(entry['root_job']['source_control_context']['archived_control']['path']).read_text())
    original_pin=put('original-control-readonly.json',original)
    # Actual before hash is fixed in driver, so fixture archives faithfully use it.
    original_pin.update(sha256=driver['control_before']['sha256'],bytes=driver['control_before']['bytes'])
    original_pin['identity']['bytes']=original_pin['bytes']
    control25=dict(original,experiment=pre['experiment'],lr_scale=.25)
    c25=put('control25-readonly.json',control25);old=c25['path'];c25['path']=str(root/'control25-readonly.json');values[c25['path']]=values.pop(old)
    window=dict(schema=H.SCHEMA,experiment=pre['experiment'],owner=owner,recipe=copy.deepcopy(H.RECIPE),current_phase=phase,
        proofs=dict(root_precommit=evidence['driver_job'],control_after=c25,entry_CPU=evidence['entry_CPU'],barrier=evidence['barrier']),
        barrier_completed_clock=barrier_clock,baseline=dict(api=bp,observed_clock=dict(boot_id='syntheticboot',monotonic_s=1000,wall_s=1000000)),
        policy=driver['window']['policy'])
    evidence['window_job']=put('window-job.json',window)
    observer=H.HorizonObserver(window,B);latch=api(1,True,1)
    event=observer.observe(latch,owner,dict(ok=True),dict(boot_id='syntheticboot',monotonic_s=1001,wall_s=1000001));event['sequence']=0
    evidence['decision']=put('event',event);old=evidence['decision']['path'];evidence['decision']['path']=str(root/'observations/observation-0000.json');values[evidence['decision']['path']]=values.pop(old)
    receipt=dict(event=evidence['decision'],sequence=0,completed_monotonic_s=1002,elapsed_s=2,boot_id='syntheticboot',scope='synthetic actual callback contract')
    evidence['durability']=put('receipt',receipt);old=evidence['durability']['path'];evidence['durability']['path']=str(root/'observations/durability-0000.json');values[evidence['durability']['path']]=values.pop(old)
    pair=dict(event=evidence['decision'],durability=evidence['durability'],completion=receipt)
    outcome=H.durable_result(event,pair,window);evidence['window_result']=put('window-result.json',outcome)
    candidate=dict(tag=driver['tags']['endpoint'],path=str(M.GAME/'models_dqn/managed-checkpoints'/(driver['tags']['endpoint']+'.pt')),
        sha256='e'*64,bytes=275200000)
    source=put('unused-source',{});source.update({k:candidate[k] for k in ('path','sha256','bytes')});source['identity']['bytes']=candidate['bytes']
    copied=copy.deepcopy(source);copied['path']='/synthetic/unactivated/readonly-copy.pt';copied['identity']['inode']+=1000
    floor={k:max(entry['clocks'][k],B[k],latch[k]) for k in M.CLOCKS}
    transition=dict(request_unix_s=1000001.5,after_unix_s=1000002,
        request=dict(actual_pin=dict(identity=dict(inode=100),sha256='f'*64),archive=dict(sha256='f'*64)),
        after=dict(actual_pin=dict(identity=dict(inode=100),sha256='f'*64),archive=dict(sha256='f'*64)))
    acquisition=dict(clock_floor=floor,purpose='candidate',client_count=192,tag=candidate['tag'],owner_before=owner,owner_after=owner,
        source_checkpoint=M.triple(source),completed_slot_transition=transition)
    acq=put('acquisition.json',acquisition)
    trigger=api(3,True);trigger.update({k:floor[k]+10 for k in M.CLOCKS})
    evidence['endpoint_trigger']=put('trigger',trigger);old=evidence['endpoint_trigger']['path'];evidence['endpoint_trigger']['path']=str(root/'endpoint/trigger-API.json');values[evidence['endpoint_trigger']['path']]=values.pop(old)
    archive25=put('endpoint-learning-control.json',control25)
    job=dict(schema=M.CPU_JOB_SCHEMA,verifier_sha256=M.PHASE_SHA,strict_phase_base_sha256=M.STRICT_SHA,original_strict_base_sha256=M.BASE_SHA,
        experiment=pre['experiment'],source=source,verification_copy=copied,clock_floor=floor,
        source_control_context=dict(archived_control=archive25,provenance=[evidence['endpoint_trigger']]),
        phase_snapshot=dict(purpose='candidate',owner=owner,observed_clients=192,phase_record=phase['record'],boot_checkpoint=phase['boot_checkpoint'],
            boot_verification=phase['boot_verification'],expected_phase=phase['expected'],acquisition=acq),
        lr25_context=dict(schema='robotron-live-CE-lr25-hot-control-context-v1',precommit=evidence['precommit'],entry_CPU=evidence['entry_CPU']))
    evidence['phase_cpu_job']=put('cpu-job.json',job)
    proof=dict(schema=M.CPU_RESULT_SCHEMA,status='PASS',phase_metadata_verified=True,lr25_hot_context_verified=True,
        script={'sha256':M.PHASE_SHA},strict_phase_base={'sha256':M.STRICT_SHA},original_strict_base={'sha256':M.BASE_SHA},
        root_job=job,sha256=candidate['sha256'],bytes=candidate['bytes'],path=copied['path'],source_before=M.flat(source),verification_copy=M.flat(copied),
        actual_restore_or_optimizer_step=False,actual_quality_qualification=False,finite=dict(tensors=443),adam_state_count=81,adam_group_count=1,
        adam_uninitialized_parameter_names=['legacy'+str(i) for i in range(18)],adam_steps={str(i):100 for i in range(81)},
        adam_step_min=100.,adam_step_max=100.,adam_group={'lr':1.25e-5},grad_scaler={'scale':1024},cuda_initialized=False,visible_cuda_devices=0,
        models={k:{'strict_cpu_load':True} for k in ('online_state_dict','target_state_dict')},clocks={k:floor[k]+20 for k in M.CLOCKS},
        saved_priority_metric_phase=dict(phase['expected'],phase_record_sha256=M.FOUNDER),job_file=M.flat(evidence['phase_cpu_job']),
        lr25_precommit=evidence['precommit'],lr25_entry_checkpoint=pre['entry_checkpoint'],lr25_entry_clocks=M.four(entry['clocks']))
    evidence['phase_cpu_report']=put('cpu-report.json',proof)
    command=['/synthetic/python','-Xgil=0','-I','-B',str(M.PHASE),'--execute','--job',evidence['phase_cpu_job']['path'],
        '--expected-job-sha256',evidence['phase_cpu_job']['sha256'],'--expected-verifier-sha256',M.PHASE_SHA]
    evidence['phase_cpu_completion']=put('numerical-completion.json',dict(argv=command,exit_code=0))
    restorearchive=put('restored-control.json',original);restorearchive.update(sha256=original_pin['sha256'],bytes=original_pin['bytes']);restorearchive['identity']['bytes']=original_pin['bytes']
    after=copy.deepcopy(driver['control_before']);after['identity']['inode']+=1000
    restore=dict(before=dict(c25),after=after,archive=restorearchive,completed_clock=dict(boot_id='syntheticboot',monotonic_s=1010,wall_s=1000010))
    evidence['restored_control']=put('restore',restore);old=evidence['restored_control']['path'];evidence['restored_control']['path']=str(root/'control50-restored-receipt.json');values[evidence['restored_control']['path']]=values.pop(old)
    result=dict(status='CAPTURED_PENDING_ROOT_CPU',CPU_executed=False,qualification_pass=False,original_control_bytes_restored=True,
        no_owner_stop_or_model_restore=True,CPU_must_run_separately=True,window_status='LATCH_DURABLE',root_job=evidence['driver_job'],owner=owner,
        window_job=evidence['window_job'],window_result=evidence['window_result'],endpoint_CPU_job=evidence['phase_cpu_job'],
        endpoint=dict(source=source,verification_copy=copied,acquisition=acq),original_control_archive=original_pin)
    evidence['driver_result']=put('driver-result.json',result)
    identity=values[evidence['driver_identity']['path']]
    original_return=put('genuine-root-wrapper-original-return.json',dict(returncode=0,stdout='actual synthetic original wrapper output',stderr='',
        pid=identity['pid'],starttime_ticks=identity['starttime_ticks'],argv=identity['argv'],original_process_untouched=True,observation_timeout=False))
    old=original_return['path'];original_return['path']=str(Path(evidence['driver_identity']['path']).with_name('root-original-driver-return.json'));values[original_return['path']]=values.pop(old)
    evidence['driver_completion']=put('driver-completion.json',dict(schema='robotron-root-original-direct-driver-completion-v1',original_return=original_return,
        original_identity=evidence['driver_identity'],returncode=0,result=evidence['driver_result'],one_attempt=True,argv=identity['argv']))
    er=dict(status='PASS',original_exit=0,original_archived_before_release=True,unit_released=True,CPU_report=evidence['entry_CPU'])
    evidence['entry_CPU_release']=put('entry-release.json',er)
    cpu_owner=dict(pid=500,starttime_ticks=600,unit='synthetic-cpu.service',invocation_id='b'*32,cgroup='/synthetic/synthetic-cpu.service')
    show=put('cpu-show.txt',{});cat=put('cpu-cat.txt',{});journal=put('cpu-journal.txt',{})
    texts={show['path']:'LoadState=loaded\nMainPID=0\nExecMainPID=500\nInvocationID='+('b'*32)+'\nNRestarts=0\nExecMainCode=1\nExecMainStatus=0\nResult=success\n',
        cat['path']:'synthetic retained unit',journal['path']:''}
    service_argv=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1',
        'OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','MKL_NUM_THREADS=2','NUMEXPR_NUM_THREADS=2','TMPDIR=/synthetic/private-tmp',*command]
    texts[cat['path']]='ExecStart=\nExecStart='+ ' '.join(json.dumps(x) for x in service_argv)+'\n'
    texts[show['path']]+='ExecStart={ path=/usr/bin/env ; argv[]='+ ' '.join(service_argv)+' ; ignore_errors=no ; pid=500 ; code=exited ; status=0 }\n'
    archive=put('terminal.json',dict(
        full_original_archives={'service_show':{'stdout':show},'service_cat':{'stdout':cat},'service_journal':{'stdout':journal}}))
    release=put('CPU-release.json',dict(status='PASS',original_exec_code=1,original_exit=0,original_result='success',
        original_archived_before_release=True,unit_released=True,CPU_report=evidence['phase_cpu_report'],cpu_job=evidence['phase_cpu_job'],
        original_pid=500,original_starttime_ticks=600,original_invocation='b'*32,original_terminal_archive=archive,
        owned_release=[dict(unit='synthetic-cpu.timer',stop_returncode=0,final_load_state='not-found'),dict(unit='synthetic-cpu.service',stop_returncode=0,final_load_state='not-found')]))
    evidence['CPU_execution']=put('CPU-execution.json',dict(owner=cpu_owner,timer='synthetic-cpu.timer',show=show,cat=cat,journal=journal,
        archived_before_release=True,released=True,release_receipt=release,job=evidence['phase_cpu_job'],report=evidence['phase_cpu_report'],
        completion=evidence['phase_cpu_completion'],command=command))
    anchor=dict(main_owner=owner,fleet_owner={'pid':700},inference_worker={'tid':701},actors=[{'pid':1000+i,'starttime_ticks':2000+i,'slot':i,'mask':list(range(72))} for i in range(192)],
        source_hashes={str(M.GAME/'Scripts/dqn'/k):v for k,v in M.CANDIDATE_SOURCES.items()},control_hashes={str(M.GAME/'models_dqn/learning_control.json'):original_pin['sha256'],'/synthetic/other-control':'a'*64},
        unit_files={str(i):'a'*64 for i in range(3)},environment_sha256='b'*64)
    anchor['source_hashes'].update({'/synthetic/source'+str(i):'c'*64 for i in range(56)})
    fresh=api(30,True,restored=True);fresh.update({k:floor[k]+30 for k in M.CLOCKS});fresh_pin=put('fresh-api.json',fresh)
    baseline=dict(anchor,status='PASS',actual_API=fresh_pin)
    baseline_pin=put('baseline.json',baseline)
    refmeta=put('protected543.json',dict(schema='robotron-protected-quality-winner-v1',protected_checkpoint=str(M.REFERENCE),checkpoint_sha256=M.REFERENCE_SHA,assessment={'qualified_improvement':True}))
    refmeta['path']=str(M.REFERENCE)+'.json';refmeta['sha256']=M.REFERENCE_META_SHA;values[refmeta['path']]=dict(schema='robotron-protected-quality-winner-v1',protected_checkpoint=str(M.REFERENCE),checkpoint_sha256=M.REFERENCE_SHA,assessment={'qualified_improvement':True})
    releasevalue=values[evidence['prior_release']['path']];previous=releasevalue['plan']
    values[previous['path']]=dict(evaluator_source_hashes=M.EVALUATOR,execution_source_hashes=M.EXECUTION,boot_assets={})
    binding=dict(schema=M.SCHEMA,activation_authorized=True,experiment=original['experiment'],candidate_experiment=pre['experiment'],
        reference=dict(path=str(M.REFERENCE),sha256=M.REFERENCE_SHA,bytes=275192614,metadata=refmeta),candidate=candidate,evidence=evidence,
        runtime_baseline=baseline_pin,runtime_anchor=anchor,predecessor_quality_plan=previous,
        campaign=dict(output_directory=str(M.GAME/'logs/managed-learning-20261015/synthetic-new-quality'),preview_directory=str(M.GAME/'logs/managed-learning-20261015/run-26/synthetic-preview'),
            execution_directory=str(M.GAME/'logs/managed-learning-20261015/run-26/synthetic-execution'),unit='robotron-quality-synthetic-new',reference_label='543',candidate_label='LR25',hypothesis='Frozen policy only.'))
    return binding,values,texts


def validate(binding,values,texts):
    return M.validate(binding,reader=lambda p:copy.deepcopy(values[p['path']]),raw_reader=lambda p:copy.deepcopy(values[p['path']]),
        text_reader=lambda p:texts[p['path']],journal_reader=lambda p:texts[p['path']].encode(),observer=H)


class LR25QualityContracts(unittest.TestCase):
    def test_full_production_validate_accepts_pending1_rawNaN_and_same_owner_restoration(self):
        b,v,t=fixture();out=validate(b,v,t)
        self.assertEqual(out['driver']['status'],'CAPTURED_PENDING_ROOT_CPU');self.assertEqual(out['current_phase'],v[b['evidence']['precommit']['path']]['current_phase'])
        event=v[b['evidence']['decision']['path']]
        self.assertEqual(event['progress']['optimizer_pending'],1);self.assertEqual(event['candidate_requests_allowed'],0)
        self.assertNotIn('maintenance',out);self.assertNotIn('ce_return',out)

    def test_original_failed_or_late_window_cannot_select_a_candidate(self):
        for kind in ('driver','outcome','late','grant'):
            b,v,t=fixture();e=b['evidence']
            if kind=='driver':v[e['driver_result']['path']]['status']='FAILED'
            elif kind=='outcome':v[e['window_result']['path']]['status']='INCOMPLETE'
            elif kind=='grant':v[e['decision']['path']]['candidate_requests_allowed']=1
            else:v[e['durability']['path']]['elapsed_s']=3601
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(b,v,t)

    def test_endpoint_must_be_exact_predeclared_tag_and_original_frozen_tuple(self):
        for kind in ('entry','barrier','copy','acquisition'):
            b,v,t=fixture();e=b['evidence'];d=v[e['driver_job']['path']];r=v[e['driver_result']['path']]
            if kind=='entry':b['candidate']['tag']=Path(v[e['precommit']['path']]['entry_checkpoint']['path']).stem
            elif kind=='barrier':b['candidate']['tag']=d['tags']['barrier']
            elif kind=='copy':r['endpoint']['verification_copy']['sha256']='0'*64
            else:r['endpoint']['acquisition']['sha256']='0'*64
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(b,v,t)

    def test_direct_endpoint_guard_excludes_actual_entry_checkpoint_tag_not_report_name(self):
        b,v,t=fixture();e=b['evidence'];pre=v[e['precommit']['path']];driver=copy.deepcopy(v[e['driver_job']['path']])
        driver['tags']['endpoint']=Path(pre['entry_checkpoint']['path']).stem
        candidate=dict(b['candidate'],tag=driver['tags']['endpoint'])
        window=v[e['window_job']['path']];B=H.normalise(v[window['baseline']['api']['path']])
        current=H.normalise(v[e['decision']['path']]['first_eligible_observation']);job=v[e['phase_cpu_job']['path']]
        with self.assertRaises(ValueError):M.check_endpoint(driver,v[e['driver_result']['path']],job,
            v[job['phase_snapshot']['acquisition']['path']],candidate,v[e['endpoint_trigger']['path']],
            M.four(v[e['entry_CPU']['path']]['clocks']),B,current,pre['entry_checkpoint'])

    def test_exact_max_floor_allows_newer_trigger_but_rejects_old_or_changed_floor(self):
        b,v,t=fixture();e=b['evidence'];job=v[e['phase_cpu_job']['path']]
        self.assertTrue(all(v[e['endpoint_trigger']['path']][k]>job['clock_floor'][k] for k in M.CLOCKS));validate(b,v,t)
        for kind in ('oldtrigger','floor'):
            b,v,t=fixture();e=b['evidence'];job=v[e['phase_cpu_job']['path']]
            if kind=='oldtrigger':v[e['endpoint_trigger']['path']]['optimized_samples']=job['clock_floor']['optimized_samples']-1
            else:job['clock_floor']['optimized_samples']+=1
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(b,v,t)

    def test_cpu_old2048_missing_phase_or_original_failure_refuses(self):
        for kind in ('schema','clients','phase','numeric','argv','exit'):
            b,v,t=fixture();e=b['evidence']
            if kind=='schema':v[e['phase_cpu_report']['path']]['schema']='robotron-batch2048-phase-snapshot-checkpoint-CPU-result-reviewed2-v1'
            elif kind=='clients':v[e['phase_cpu_job']['path']]['phase_snapshot']['observed_clients']=0
            elif kind=='phase':v[e['phase_cpu_report']['path']]['lr25_hot_context_verified']=False
            elif kind=='numeric':v[e['phase_cpu_report']['path']]['adam_state_count']=80
            elif kind=='argv':v[e['phase_cpu_completion']['path']]['argv'].append('--foreign')
            else:v[e['phase_cpu_completion']['path']]['exit_code']=1
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(b,v,t)

    def test_control_labels_and_bytes_are_separate_and_original_driver_exit_required(self):
        for kind in ('runtime_label','restore','driver_exit','unrelated_zero','cpu_release','foreign_command'):
            b,v,t=fixture();e=b['evidence']
            if kind=='runtime_label':b['experiment']=b['candidate_experiment']
            elif kind=='restore':v[e['restored_control']['path']]['after']['sha256']='0'*64
            elif kind=='driver_exit':v[e['driver_completion']['path']]['returncode']=1
            elif kind=='unrelated_zero':v[v[e['driver_completion']['path']]['original_return']['path']]['pid']+=1
            elif kind=='foreign_command':t[v[e['CPU_execution']['path']]['cat']['path']]=t[v[e['CPU_execution']['path']]['cat']['path']].replace(M.PHASE_SHA,'0'*64)
            else:v[v[e['CPU_execution']['path']]['release_receipt']['path']]['unit_released']=False
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(b,v,t)

    def test_same_B_learner_acceptance_epoch_and_partition_are_required(self):
        for kind in ('learner_inserts','epoch','partition'):
            b,v,t=fixture();e=b['evidence'];event=v[e['decision']['path']]
            if kind=='learner_inserts':event['progress']['learner_accepted']=5999999
            elif kind=='epoch':event['first_eligible_observation']['host_pipeline']['learning_exposure']['replay']['epoch']+=1
            else:event['first_eligible_observation']['host_pipeline']['learning_exposure']['optimizer']['total']['applied']+=1
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(b,v,t)

    def test_production_auditor_selector_delegates_exact_new_cpu_binding(self):
        b,v,t=fixture();out=validate(b,v,t)
        with mock.patch.multiple(A,BINDINGS=M,CFG=b,BUNDLE=out):
            A.validate_cpu_proof(out['proof'],SimpleNamespace(cpu_job_sha256=b['evidence']['phase_cpu_job']['sha256'],candidate_sha256=b['candidate']['sha256'],candidate_bytes=b['candidate']['bytes']))

    def test_real_carrier_inputs_select_driver_restoration_and_no_old_aliases(self):
        b,v,t=fixture();out=validate(b,v,t);cp=SimpleNamespace(stat=lambda:SimpleNamespace(st_size=b['candidate']['bytes'],st_mode=0o444));rp=SimpleNamespace(stat=lambda:SimpleNamespace(st_mode=0o444))
        with mock.patch.multiple(C,CFG=b,BUNDLE=out,CANDIDATE=cp,REFERENCE=rp,REFERENCE_SHA=b['reference']['sha256'],BINDING_PIN={}),mock.patch.object(C,'sha',side_effect=lambda p:b['candidate']['sha256'] if p is cp else b['reference']['sha256']):
            bound,_=C.inputs(None)
        self.assertEqual(bound['current_ce_phase'],out['current_phase']);self.assertEqual(bound['restored_control'],b['evidence']['restored_control'])
        for key in ('failed_return','maintenance_result','ce_return','trial_result'):self.assertNotIn(key,bound)

    def test_real_carrier_readiness_requires_new_schema_same_owner_and_closed_CPU(self):
        b,v,t=fixture();out=validate(b,v,t)
        b['runtime_anchor']['unit_files']={'/synthetic/unit'+str(i):'a'*64 for i in range(3)}
        out['baseline']['unit_files']=b['runtime_anchor']['unit_files']
        resources={k:True for k in ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free',
            'no_competing_helpers','no_private_cgroup_tmpfs_processes','no_pending_save','owned_units_released',
            'commands_UID_cwd_exe_checked','held_environment_checked','unit_files_checked')}
        resources.update(gpu0_uuid=C.GPU0,gpu1_uuid=C.GPU1,GPU0_free_bytes=14*(1<<30))
        bound=dict(candidate_sha256=b['candidate']['sha256'],candidate_bytes=b['candidate']['bytes'],
            phase_cpu_job=b['evidence']['phase_cpu_job'],phase_cpu_proof=b['evidence']['phase_cpu_report'])
        ready=dict(copy.deepcopy(b['runtime_anchor']),schema='robotron-lr25-first-durable-endpoint-exclusive-readiness-v1',
            status='PASS',observed_unix_s=100,resources=resources,candidate=dict(source=b['candidate']['path'],
                sha256=bound['candidate_sha256'],bytes=bound['candidate_bytes'],root_job_sha256=bound['phase_cpu_job']['sha256'],
                cpu_proof_sha256=bound['phase_cpu_proof']['sha256']))
        with mock.patch.multiple(C,CFG=b,BUNDLE=out,CANDIDATE=Path(b['candidate']['path'])),mock.patch.object(C.time,'time',return_value=101),mock.patch.object(C,'sha',return_value='a'*64):
            C.readiness_contract(ready,bound)
            for kind in ('old_schema','owner','release','stale'):
                wrong=copy.deepcopy(ready)
                if kind=='old_schema':wrong['schema']='robotron-CE2048-trial02-first-LATCH-policy-followup-exclusive-readiness-v1'
                elif kind=='owner':wrong['main_owner']['pid']+=1
                elif kind=='release':wrong['resources']['owned_units_released']=False
                else:wrong['observed_unix_s']-=181
                with self.subTest(kind=kind),self.assertRaises(RuntimeError):C.readiness_contract(wrong,bound)

    def test_readonly_reader_is_metadata_only_and_default_carrier_PLAN_is_read_free(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'tiny.json';p.write_text('{}\n');p.chmod(0o444)
            raw=p.read_bytes();pin=dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=M.identity(p.lstat()))
            self.assertEqual(M.read(pin),{})
            wrong=copy.deepcopy(pin);wrong['sha256']='0'*64
            with self.assertRaises(ValueError):M.read(wrong)
        with mock.patch.object(C,'configure',side_effect=AssertionError('No configuration')),mock.patch.object(C,'sha',side_effect=AssertionError('No reads')),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(C.main([]),0)

    def test_original_protocol_lifecycle_and_row_scoring_classifier_sources_are_preserved(self):
        def funcs(path):
            text=path.read_text();return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
        old=funcs(HERE.parent/'CE2048_trial02_first_LATCH_policy_followup_quality_carrier_proposal/root_quality_carrier.py');new=funcs(HERE/'root_quality_carrier.py')
        for name in ('require','sha','write','call','show','pinned_json','default_argv','launch_argv','validate_plan','source_checks','prepare','launch','observe','archive'):self.assertEqual(old[name],new[name],name)
        old=funcs(HERE.parent/'CE2048_trial02_first_LATCH_policy_followup_quality_binding_proposal/audit_completed_leg.py');new=funcs(HERE/'audit_completed_leg.py')
        for name in set(old)-{'audit'}:self.assertEqual(old[name],new[name],name)
        before=old['audit'];after=new['audit']
        oldline="original_failed_return=CFG['evidence']['failed_return'],separate_maintenance=CFG['evidence']['maintenance_result'],\n            followup_precommit=CFG['evidence']['followup_precommit']"
        newline="original_driver=CFG['evidence']['driver_result'],hot_window=CFG['evidence']['window_result'],\n            hot_precommit=CFG['evidence']['precommit'],restored_control=CFG['evidence']['restored_control']"
        self.assertEqual(before.replace(oldline,newline).replace("report['trial02_binding']","report['lr25_binding']"),after)


if __name__=='__main__':unittest.main()
