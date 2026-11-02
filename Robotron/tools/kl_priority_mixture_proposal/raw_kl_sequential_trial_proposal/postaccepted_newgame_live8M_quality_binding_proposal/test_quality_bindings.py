"""Authored UNEXECUTED stdlib metadata guards; no application imports or live I/O.

The full positive calls production validate with real immutable recovery/history
JSON and synthetic future window/capture/CPU/baseline metadata. No checkpoint
body is opened, statted or hashed; future descriptors are explicitly synthetic.
The root may execute these bounded stdlib guards during the current window.
Actual candidate CPU and quality actions retain their original evidence gates.
"""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shlex
from types import SimpleNamespace
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'recovered_CE543_quality_binding_proposal'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


M=module('_future_postfix_quality_binding_contract',HERE/'quality_bindings.py')
H=module('_future_postfix_quality_pure_observer_contract',M.OBSERVER)
C=module('_future_postfix_quality_carrier_contract',HERE/'root_quality_carrier.py')
A=module('_future_postfix_quality_auditor_contract',HERE/'audit_completed_leg.py')


def fixture():
    """Immutable historical inputs, mapped synthetic future metadata, no models."""
    values={};texts={};serial=0

    def put(name,value):
        nonlocal serial
        serial+=1;raw=H.encoded(value)
        path=name if str(name).startswith('/') else '/synthetic/unactivated/'+str(name)
        pin=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
            identity=dict(device=1,inode=serial,bytes=len(raw),mtime_ns=1900000000000000000+serial,
                ctime_ns=1900000000000000000+serial,mode='0o444',uid=os.getuid(),nlink=1))
        values[pin['path']]=copy.deepcopy(value)
        return pin

    def actual_path(path,digest=None):
        path=Path(path)
        if path.suffix!='.json':raise AssertionError('Only saved JSON, never model bodies')
        info=path.lstat();raw=path.read_bytes()
        pin=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=M.identity(info))
        if digest is not None and pin['sha256']!=digest:raise AssertionError('Saved actual metadata changed')
        value=M.read(pin);values[pin['path']]=copy.deepcopy(value)
        return pin,value

    def read(pin):
        if pin['path'] not in values:
            # Production's ordinary reader remains strict. Historical partial
            # pointers must be explicitly re-fingerprinted by the root binding.
            values[pin['path']]=M.read(pin)
        return copy.deepcopy(values[pin['path']])

    recpin,rec=actual_path(M.RECOVERY_RESULT,M.RECOVERY_SHA)
    relpin,rec_release=actual_path(M.RECOVERY_RELEASE,M.RECOVERY_RELEASE_SHA)
    recjob=read(rec['root_job']);failed_job=read(recjob['failed_job'])
    releasepin=failed_job['quality_release'];prior=read(releasepin)
    phase=copy.deepcopy(rec['startup']['phase']);owner=copy.deepcopy(rec['owner'])
    historical=read(rec['startup']['phase_CPU_readonly_archive'])
    held=copy.deepcopy(historical['held_recipe_context'])
    controlpin=historical['root_job']['source_control_context']['archived_control'];control=read(controlpin)
    current_control=copy.deepcopy(controlpin)
    current_control['path']=str(M.GAME/'models_dqn/learning_control.json')
    current_control['identity'].update(device=1,inode=90000,mode='0o644')
    values[current_control['path']]=copy.deepcopy(control)  # Synthetic future current PIN; no live read.
    # a7d native_plan really has only five identity fields. The new root-bound
    # FULLPIN is authenticated independently; no historical fields are invented.
    predecessor_pin,predecessor=actual_path(prior['native_plan']['path'],prior['native_plan']['sha256'])
    refpin,_=actual_path(str(M.REFERENCE)+'.json',M.REFERENCE_META_SHA)
    experiment=control['experiment']
    root=M.RUN/'synthetic-future-postfix8M-capture-UNACTIVATED'
    ready=dict(boot_id=read(rec['start_request'])['boot_id'],
        monotonic_s=rec['healthy192']['api']['observed_monotonic_s'],wall_s=rec['healthy192']['api']['observed_unix_s'])
    start=dict(boot_id=ready['boot_id'],monotonic_s=ready['monotonic_s']+10,wall_s=ready['wall_s']+10)
    clocks0={k:historical['clocks'][k]+1000 for k in M.CLOCKS}

    def api(offset=0,eligible=False,pending=0):
        counts=dict(applied=100+(10 if eligible else 0),amp_skipped=5+(2 if eligible else 0),unavailable=0)
        counts['outcomes_recorded']=sum(counts.values());counts['attempts_started']=counts['outcomes_recorded']+pending
        ident=dict(process_id=owner['pid'],instance_monotonic_ns=999999,epoch=2,epoch_reason='synthetic_existing_epoch')
        cats=dict(dqn=1000000+(7500000 if eligible else 0),epsilon=200000+(500000 if eligible else 0),
            expert=500000+(900000 if eligible else 0),eval=100000+(2200000 if eligible else 0),unattributed=0)
        clocks={k:clocks0[k]+(8000000 if eligible and k=='learner_frame_count' else
            16000000 if eligible and k=='frame_count' else 100000 if eligible else 0)+offset for k in M.CLOCKS}
        return dict(clocks,client_count=192,training_enabled=True,measurement_active=False,managed_experiment=experiment,
            lr=2.5e-5,ts=start['wall_s']+offset,pipeline_snapshot_age_s=.25,pipeline_read_error='',grad_norm=float('nan'),
            host_pipeline=dict(learning_exposure=dict(optimizer=dict(ident,schema='robotron-optimizer-exposure-v1',enabled=True,
                available=pending==0,total=counts,since_epoch=copy.deepcopy(counts),unclassified_started_total=pending),
                replay=dict(ident,schema='robotron-replay-insert-exposure-v1',enabled=True,available=True,
                    accepted_total=sum(cats.values()),accepted_learner_total=cats['dqn']+cats['epsilon'],accepted_by_source_total=cats))))

    completed=put('before-completed.json',{'tag':'synthetic-prior-completed'})
    case=dict(schema='robotron-postaccepted-newgame-live8M-candidate-case-v1',capture_authorized=True,
        recovery=dict(result=recpin,release=relpin),source_freeze_release=releasepin,
        runtime_baseline=put('pre-window-baseline.json',{'synthetic':True}),readiness=put('pre-window-ready.json',{'synthetic':True}),
        control_before=current_control,completed_slot=completed,tag='synthetic-future-first8M-UNACTIVATED',
        window=dict(policy=dict(H.POLICY,cutoff_s=3600),preparation_timeout_s=120),output_directory=str(root),cpu_python='/synthetic/python')
    evidence=dict(capture_case=put('capture-case.json',case))
    B=api();Bpin=put(root/'B-API.raw.json',B)
    window=dict(schema=H.SCHEMA,experiment=experiment,owner=owner,recipe=copy.deepcopy(H.RECIPE),current_phase=phase,
        proofs=dict(root_precommit=evidence['capture_case'],recovery_result=recpin,recovery_release=relpin,control=current_control),
        recovery_ready_clock=ready,baseline=dict(api=Bpin,observed_clock=start),policy=copy.deepcopy(case['window']['policy']))
    evidence['window_job']=put(root/'window-job.json',window)
    latch=api(1,True,1)
    event=H.HorizonObserver(window,B).observe(latch,owner,dict(ok=True),
        dict(boot_id=start['boot_id'],monotonic_s=start['monotonic_s']+1,wall_s=start['wall_s']+1))
    event['sequence']=0
    if event['state']!='LATCH':raise AssertionError('Synthetic positive must reach real pure observer first-LATCH')
    evidence['decision']=put(root/'observations/observation-0000.json',event)
    receipt=dict(event=evidence['decision'],sequence=0,completed_monotonic_s=start['monotonic_s']+2,
        elapsed_s=2,boot_id=start['boot_id'],scope='Synthetic callback file+directory fsync contract only')
    evidence['durability']=put(root/'observations/durability-0000.json',receipt)
    outcome=H.durable_result(event,dict(event=evidence['decision'],durability=evidence['durability'],completion=receipt),window)
    evidence['window_result']=put(root/'window-result.json',outcome)
    candidate=dict(tag=case['tag'],path=str(M.GAME/'models_dqn/managed-checkpoints'/(case['tag']+'.pt')),sha256='e'*64,bytes=275200000)
    source=dict(path=candidate['path'],sha256=candidate['sha256'],bytes=candidate['bytes'],
        identity=dict(device=1,inode=90001,bytes=candidate['bytes'],mtime_ns=1900000000000000000,ctime_ns=1900000000000000000,
            mode='0o444',uid=os.getuid(),nlink=1))
    copied=copy.deepcopy(source);copied['path']=str(root/'capture/verification-copy.pt');copied['identity']['inode']+=1
    request=put('synthetic-request-slot.json',dict(tag=case['tag']));request_archive=put('synthetic-request-archive.json',dict(tag=case['tag']))
    after=copy.deepcopy(request);after['path']='/synthetic/unactivated/completed-slot.json'
    transition=dict(before=dict(actual_pin=completed),request=dict(actual_pin=request,archive=request_archive),
        after=dict(actual_pin=after),request_unix_s=start['wall_s']+1.5,after_unix_s=start['wall_s']+2.5)
    trigger=api(3,True);floor=M.four(trigger)
    acquisition=dict(schema='robotron-owned-phase-snapshot-acquisition-v1',clock_floor=floor,purpose='candidate',client_count=192,
        tag=case['tag'],owner_before=owner,owner_after=owner,stopped_absence=None,source_checkpoint=M.triple(source),
        completed_slot_transition=transition,phase_record_sha256=phase['record']['sha256'],boot_checkpoint=phase['boot_checkpoint'])
    acq=put(root/'capture/acquisition.json',acquisition)
    evidence['trigger_API']=put(root/'capture/trigger-API.json',trigger)
    archived_control=copy.deepcopy(controlpin);archived_control['path']=str(root/'metadata/learning_control.json')
    archived_control['identity']['inode']+=100000;values[archived_control['path']]=copy.deepcopy(control)
    job=dict(schema='robotron-phase-snapshot-checkpoint-CPU-job-v1',verifier_sha256=M.PHASE_SHA,
        strict_phase_base_sha256=M.STRICT_SHA,original_strict_base_sha256=M.BASE_SHA,experiment=experiment,
        source=source,verification_copy=copied,clock_floor=floor,
        source_control_context=dict(held_recipe_context=held,archived_control=archived_control,provenance=[evidence['trigger_API']]),
        phase_snapshot=dict(purpose='candidate',owner=owner,observed_clients=192,phase_record=phase['record'],boot_checkpoint=phase['boot_checkpoint'],
            boot_verification=phase['boot_verification'],expected_phase=phase['expected'],acquisition=acq))
    evidence['phase_cpu_job']=put(root/'candidate-CPU-job.json',job)
    proof=dict(schema='robotron-phase-snapshot-checkpoint-CPU-result-v1',status='PASS',phase_metadata_verified=True,
        script={'sha256':M.PHASE_SHA},strict_phase_base={'sha256':M.STRICT_SHA},original_strict_base={'sha256':M.BASE_SHA},
        root_job=copy.deepcopy(job),sha256=source['sha256'],bytes=source['bytes'],path=copied['path'],source_before=M.flat(source),verification_copy=M.flat(copied),
        actual_restore_or_optimizer_step=False,actual_quality_qualification=False,held_recipe_context=held,
        cuda_initialized=False,visible_cuda_devices=0,finite=dict(tensors=443),adam_state_count=81,adam_group_count=1,
        adam_steps={str(i):100 for i in range(81)},adam_step_min=100.,adam_step_max=100.,adam_group={'lr':2.5e-5},grad_scaler={'scale':1024},
        models={k:{'strict_cpu_load':True} for k in ('online_state_dict','target_state_dict')},clocks={k:floor[k]+20 for k in M.CLOCKS},
        saved_priority_metric_phase=dict(phase['expected'],phase_record_sha256=phase['record']['sha256']),job_file=M.flat(evidence['phase_cpu_job']))
    evidence['phase_cpu_report']=put('synthetic-future-CPU-report.json',proof)
    command=[case['cpu_python'],'-Xgil=0','-I','-B',str(M.PHASE),'--execute','--job',evidence['phase_cpu_job']['path'],
        '--expected-job-sha256',evidence['phase_cpu_job']['sha256'],'--expected-verifier-sha256',M.PHASE_SHA]
    evidence['phase_cpu_completion']=put('synthetic-future-CPU-completion.json',dict(argv=command,exit_code=0))
    publications=[dict(tag=case['tag'],pin=request,archive=request_archive,
        publication=dict(published=True,completed_identity=after['identity']))]
    capture_completion=put(root/'capture-completion.json',dict(status='COMPLETE',tag=case['tag'],owner_before=owner,
        owner_after=owner,transition=transition,request_publications=publications))
    result=dict(schema='robotron-postaccepted-newgame-live8M-candidate-result-v1',status='CAPTURED_PENDING_ROOT_CPU',
        root_case=evidence['capture_case'],root_precommit=evidence['capture_case'],CPU_executed=False,qualification_pass=False,
        model_only=True,replay_RNG_actor_anchor=False,control_changed=False,owner_actions=False,owner=owner,current_phase=phase,
        source=source,verification_copy=copied,acquisition=acq,trigger_API=evidence['trigger_API'],capture_completion=capture_completion,
        cpu_job=evidence['phase_cpu_job'],window_job=evidence['window_job'],window_result=evidence['window_result'],cpu_argv=command,
        candidate_clocks=None,cpu_report=None,cpu_completion=None)
    evidence['capture_result']=put(root/'result.json',result)

    # The original capture root config omits result_path, so its real-format
    # release must omit payload_result. Recovery393 separately retains that key.
    capture_release=copy.deepcopy(rec_release);capture_release.pop('payload_result')
    original=capture_release['original'];original.update(pid=6001,starttime_ticks=6002,unit='synthetic-capture.service',
        timer='synthetic-capture.timer',invocation_id='a'*32,timer_invocation_id='c'*32,observed_live=True)
    service_argv=['/synthetic/python','-Xgil=0','-I','-B',str(M.SELECTOR),'--execute','--case',evidence['capture_case']['path'],
        '--expected-case-sha256',evidence['capture_case']['sha256'],'--output',str(root),'--expected-source-sha256',M.SELECTOR_SHA]
    for i,item in enumerate(capture_release['full_original_archives']):
        unit=original['unit'] if i<3 else original['timer']
        item['argv']=(['systemctl','--user','show',unit] if i%3==0 else ['systemctl','--user','cat',unit] if i%3==1 else
            ['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+original['invocation_id' if i<3 else 'timer_invocation_id']])
        item['stdout']=put('capture-archive-'+str(i)+'.txt',{});item['unix_s']=100+i
        texts[item['stdout']['path']]=('ExecMainPID=6001\nInvocationID='+original['invocation_id']+
            '\nMainPID=0\nNRestarts=0\nExecMainCode=1\nExecMainStatus=0\nResult=success\n' if i==0 else
            'ExecStart='+shlex.join(service_argv)+'\n' if i==1 else 'synthetic original archive\n')
    for i,item in enumerate(capture_release['owned_release']):
        unit=original['timer' if i==0 else 'unit'];item['unit']=unit
        item['stop'].update(argv=['systemctl','--user','stop',unit],exit=0,unix_s=200+i)
        item['final'].update(argv=['systemctl','--user','show',unit],exit=0,stdout=put('capture-final-'+str(i)+'.txt',{}))
        texts[item['final']['stdout']['path']]='LoadState=not-found\n'
    evidence['capture_release']=put('synthetic-capture-release.json',capture_release)

    cpu_owner=dict(pid=7001,starttime_ticks=7002,unit='synthetic-cpu.service',invocation_id='b'*32,cgroup='/synthetic/synthetic-cpu.service')
    show=put('cpu-show.txt',{});cat=put('cpu-cat.txt',{});journal=put('cpu-journal.txt',{})
    cpu_argv=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1',
        'OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','MKL_NUM_THREADS=2','NUMEXPR_NUM_THREADS=2','TMPDIR=/synthetic/private-tmp',*command]
    texts[cat['path']]='ExecStart=\nExecStart='+shlex.join(cpu_argv)+'\n'
    texts[show['path']]='LoadState=loaded\nMainPID=0\nExecMainPID=7001\nInvocationID='+('b'*32)+\
        '\nNRestarts=0\nExecMainCode=1\nExecMainStatus=0\nResult=success\nExecStart={ path=/usr/bin/env ; argv[]='+\
        shlex.join(cpu_argv)+' ; ignore_errors=no ; pid=7001 ; code=exited ; status=0 }\n'
    texts[journal['path']]=''
    cpu_original=dict(pid=7001,starttime_ticks=7002,invocation_id='b'*32,unit='synthetic-cpu.service',
        timer='synthetic-cpu.timer',timer_invocation_id='c'*32,observed_live=True)
    groups={};stream_pins={'service_show':show,'service_cat':cat,'service_journal':journal}
    for kind in ('service','timer'):
        unit=cpu_original['unit' if kind=='service' else 'timer']
        invocation=cpu_original['invocation_id' if kind=='service' else 'timer_invocation_id']
        commands=dict(show=['systemctl','--user','show',unit,'--all'],cat=['systemctl','--user','cat',unit],
            journal=['journalctl','--user','_SYSTEMD_INVOCATION_ID='+invocation,'--no-pager','-o','short-iso-precise'])
        for suffix,argv in commands.items():
            name=kind+'_'+suffix
            if name not in stream_pins:
                stream_pins[name]=put('cpu-'+name+'-stdout.txt',{})
                texts[stream_pins[name]['path']]=('LoadState=loaded\nInvocationID='+invocation+'\nUnit='+cpu_original['unit']+'\n'
                    if suffix=='show' else '[Timer]\nUnit='+cpu_original['unit']+'\n' if suffix=='cat' else '')
            error_pin=put('cpu-'+name+'-stderr.txt',{});texts[error_pin['path']]=''
            command_pin=put('cpu-'+name+'-command.json',dict(argv=argv,returncode=0,stdout=texts[stream_pins[name]['path']],
                stderr='',started_unix_s=1000+len(groups),ended_unix_s=1000+len(groups)+.25))
            groups[name]=dict(command=command_pin,stdout=stream_pins[name],stderr=error_pin)
    archive=put('cpu-original-terminal.json',dict(original=cpu_original,full_original_archives=groups))
    stop_pins=[put('cpu-stop-'+str(i)+'.json',dict(argv=['systemctl','--user','stop',unit],returncode=0,stdout='',stderr='',
        started_unix_s=1100+i,ended_unix_s=1100+i+.25)) for i,unit in enumerate(('synthetic-cpu.timer','synthetic-cpu.service'))]
    cpurelease=put('cpu-owned-release.json',dict(status='PASS',original_exec_code=1,original_exit=0,original_result='success',
        original_archived_before_release=True,unit_released=True,CPU_report=evidence['phase_cpu_report'],cpu_job=evidence['phase_cpu_job'],
        original_pid=7001,original_starttime_ticks=7002,original_invocation='b'*32,original=cpu_original,original_terminal_archive=archive,
        owned_release=[dict(unit=unit,stop=stop_pins[i],stop_returncode=0,final_load_state='not-found')
            for i,unit in enumerate(('synthetic-cpu.timer','synthetic-cpu.service'))]))
    evidence['CPU_execution']=put('synthetic-CPU-execution.json',dict(owner=cpu_owner,timer='synthetic-cpu.timer',show=show,cat=cat,journal=journal,
        archived_before_release=True,released=True,release_receipt=cpurelease,job=evidence['phase_cpu_job'],report=evidence['phase_cpu_report'],
        completion=evidence['phase_cpu_completion'],command=command))
    actual_binding=rec['healthy192']['binding']['bindings']
    fleet=rec['healthy192']['binding']['fleet']
    fleet_owner=dict(pid=int(fleet['MainPID']),starttime_ticks=rec['healthy192']['binding']['supervisor_start_ticks'],
        cgroup=fleet['ControlGroup'],unit=fleet['ControlGroup'].rsplit('/',1)[1],invocation_id='f'*32)
    worker=dict(actual_binding['worker']['thread'],mask=list(range(72)))
    anchor=dict(main_owner=owner,fleet_owner=fleet_owner,
        inference_worker=worker,actors=copy.deepcopy(actual_binding['actors']),
        source_hashes=copy.deepcopy(actual_binding['source_hashes']),control_hashes=copy.deepcopy(actual_binding['control_hashes']),
        unit_files={str(M.RUN/('synthetic-unit-'+str(i))):'f'*64 for i in range(3)},environment_sha256=actual_binding['environment_sha256'])
    # Saved actor anchors need real pid/start/slot/mask shape for readiness_contract.
    for actor in anchor['actors']:
        actor['slot']=actor['client_slot'];actor['mask']=list(range(72))
    fresh=api(30,True);fresh.update({k:proof['clocks'][k]+30 for k in M.CLOCKS})
    fresh_pin=put('synthetic-postCPU-main-API.raw.json',fresh)
    baseline_pin=put('synthetic-postCPU-baseline.json',dict(anchor,status='PASS',actual_API=fresh_pin,actual_maintenance=recpin))
    binding=dict(schema=M.SCHEMA,activation_authorized=True,experiment=experiment,candidate=candidate,
        reference=dict(path=str(M.REFERENCE),sha256=M.REFERENCE_SHA,bytes=275192614,metadata=refpin),evidence=evidence,current_ce_phase=phase,
        runtime_baseline=baseline_pin,runtime_anchor=anchor,predecessor_quality_plan=predecessor_pin,
        campaign=dict(output_directory=str(M.GAME/'logs/managed-learning-20261015/synthetic-future-postfix-quality-UNACTIVATED'),
            preview_directory=str(M.RUN/'synthetic-future-postfix-preview-UNACTIVATED'),execution_directory=str(M.RUN/'synthetic-future-postfix-execution-UNACTIVATED'),
            unit='robotron-quality-synthetic-postfix-UNACTIVATED',reference_label='protected543',candidate_label='future-first8M',hypothesis='Frozen policy only; no causal efficacy or throughput claim.'))
    return SimpleNamespace(binding=binding,values=values,texts=texts,read=read,put=put,api=api,
        actual_release=rec_release,prior=prior,predecessor=predecessor)


def validate(f):
    return M.validate(f.binding,reader=f.read,raw_reader=f.read,text_reader=lambda p:f.texts[p['path']],
        journal_reader=lambda p:f.texts[p['path']].encode(),observer=H)


class PostAcceptedNewgameQualityContracts(unittest.TestCase):
    def test_full_production_validate_accepts_genuine_recovery_and_synthetic_pending1_rawNaN_first8plus8(self):
        f=fixture();bundle=validate(f);e=f.binding['evidence'];event=f.read(e['decision'])
        self.assertEqual(bundle['current_ce_phase'],f.binding['current_ce_phase'])
        self.assertEqual((event['progress']['learner_frames'],event['progress']['learner_accepted']),(8000001,8000000))
        self.assertEqual(event['progress']['physical_accepted'],11100000)
        self.assertEqual(event['progress']['optimizer_pending'],1);self.assertEqual(event['candidate_requests_allowed'],0)
        self.assertTrue(math.isnan(event['first_eligible_observation']['grad_norm']))
        self.assertEqual(f.read(e['window_result'])['candidate_requests_allowed'],1)
        self.assertNotIn('payload_result',f.read(e['capture_release']));self.assertIn('payload_result',f.actual_release)
        self.assertIsNone(bundle['capture']['cpu_report']);self.assertNotIn('ce_return',bundle);self.assertNotIn('restored_control',bundle)
        old=f.prior['native_plan'];self.assertNotEqual(set(old['identity']),set(f.binding['predecessor_quality_plan']['identity']))
        self.assertEqual(M.triple(old),M.triple(f.binding['predecessor_quality_plan']))
        # Independently exercise the real minimal archive reader against genuine393.
        archive=f.actual_release['full_original_archives'][0]['stdout']
        self.assertEqual(set(archive['identity']),{'device','inode','mode','uid','nlink'})
        self.assertIn('ExecMainStatus=0',M.archive_text(archive))

    def test_wrong6M_physical_substitution_failed_or_late_first_grant_refuses(self):
        for kind in ('6M','physical_only','failed','event_grant','late','epoch'):
            f=fixture();e=f.binding['evidence'];window=f.values[e['window_job']['path']]
            if kind=='6M':window['policy']['learner_accepted']=6000000
            elif kind=='failed':f.values[e['window_result']['path']]['status']='EVIDENCE_FAILED'
            elif kind=='event_grant':f.values[e['decision']['path']]['candidate_requests_allowed']=1
            elif kind=='late':f.values[e['durability']['path']]['elapsed_s']=3601
            elif kind=='epoch':f.values[e['decision']['path']]['first_eligible_observation']['host_pipeline']['learning_exposure']['replay']['epoch']+=1
            else:
                event=f.read(e['decision']);api=event['first_eligible_observation'];replay=api['host_pipeline']['learning_exposure']['replay']
                replay['accepted_by_source_total']['dqn']-=2000000;replay['accepted_by_source_total']['expert']+=2000000
                replay['accepted_learner_total']-=2000000
                # Re-sign the synthetic event and receipt to reach semantic8M
                # checking rather than merely breaking an outer SHA join.
                base=H.normalise(f.read(window['baseline']['api']));cur=H.normalise(api);p=event['progress']
                p['learner_accepted']=cur['learner_accepted']-base['learner_accepted']
                p['physical_by_source']={k:cur['categories'][k]-base['categories'][k] for k in H.CATEGORIES}
                ep=f.put(e['decision']['path'],event);receipt=f.read(e['durability']);receipt['event']=ep
                rp=f.put(e['durability']['path'],receipt);pair=dict(event=ep,durability=rp,completion=receipt)
                outcome=H.durable_result(event,pair,window)
                with self.subTest(kind=kind),self.assertRaises(ValueError):M.check_window(f.read(e['capture_case']),
                    dict(f.read(e['capture_result']),_experiment=f.binding['experiment']),window,outcome,
                    f.read(window['baseline']['api']),event,receipt,H)
                continue
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(f)

    def test_b2e_candidate192_halfscale_exactCPU_argv_and_original_exit_required(self):
        for kind in ('d73','startup0','.25','finite','adam','scaler','argv','exit'):
            f=fixture();e=f.binding['evidence'];job=f.values[e['phase_cpu_job']['path']];proof=f.values[e['phase_cpu_report']['path']]
            if kind=='d73':proof['script']['sha256']='d'*64
            elif kind=='startup0':job['phase_snapshot']['observed_clients']=0;proof['root_job']=copy.deepcopy(job)
            elif kind=='.25':proof['held_recipe_context']['learning_control_lr_scale']=.25
            elif kind=='finite':proof['finite']['tensors']=442
            elif kind=='adam':proof['adam_state_count']=80
            elif kind=='scaler':proof['grad_scaler']['scale']=0
            elif kind=='argv':f.values[e['phase_cpu_completion']['path']]['argv'][-1]='f'*64
            else:f.values[e['phase_cpu_completion']['path']]['exit_code']=1
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(f)

    def test_original_capture_and_CPU_archived_identity_command_and_release_are_not_aliases(self):
        for kind in ('payload_alias','capture_failed','capture_argv','capture_release','cpu_show','cpu_command','cpu_release','cpu_missing_timer'):
            f=fixture();e=f.binding['evidence'];released=f.values[e['capture_release']['path']];execution=f.values[e['CPU_execution']['path']]
            if kind=='payload_alias':released['payload_result']=e['capture_result']
            elif kind=='capture_failed':released['original_exit']=1
            elif kind=='capture_argv':
                p=released['full_original_archives'][1]['stdout']['path'];f.texts[p]=f.texts[p].replace(M.SELECTOR_SHA,'0'*64)
            elif kind=='capture_release':released['owned_release'].reverse()
            elif kind=='cpu_show':f.texts[execution['show']['path']]=f.texts[execution['show']['path']].replace('ExecMainPID=7001','ExecMainPID=123')
            elif kind=='cpu_command':
                p=execution['cat']['path'];f.texts[p]=f.texts[p].replace(e['phase_cpu_job']['path'],'/synthetic/unrelated-zero-job.json')
            elif kind=='cpu_release':f.values[execution['release_receipt']['path']]['owned_release'][0]['final_load_state']='loaded'
            else:
                release=f.values[execution['release_receipt']['path']]
                f.values[release['original_terminal_archive']['path']]['full_original_archives'].pop('timer_journal')
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(f)

    def test_exact_first_capture_tuple_single_request_and_trigger_floor_required(self):
        for kind in ('copy_alias','alternate_tag','second_request','foreign_slot','completion_owner','old_floor','source_inode'):
            f=fixture();e=f.binding['evidence'];result=f.values[e['capture_result']['path']];job=f.values[e['phase_cpu_job']['path']]
            acquired=f.values[job['phase_snapshot']['acquisition']['path']];finished=f.values[result['capture_completion']['path']]
            if kind=='copy_alias':f.binding['candidate']['path']=job['verification_copy']['path']
            elif kind=='alternate_tag':f.binding['candidate']['tag']='synthetic-posthoc-alternate'
            elif kind=='second_request':finished['request_publications'].append(copy.deepcopy(finished['request_publications'][0]))
            elif kind=='foreign_slot':acquired['completed_slot_transition']['before']['actual_pin']['sha256']='0'*64
            elif kind=='completion_owner':finished['owner_after']['pid']+=1
            elif kind=='old_floor':f.values[e['trigger_API']['path']]['learner_frame_count']=1
            else:acquired['completed_slot_transition']['after']['actual_pin']['identity']['inode']+=1
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(f)

    def test_current_phase_owner_source_control_and_preserved_invalid_history_required(self):
        for kind in ('oldowner','oldphase','oldsocket','control','stale_baseline','epoch','historical_rescue','historical_inode'):
            f=fixture();e=f.binding['evidence'];baseline=f.values[f.binding['runtime_baseline']['path']]
            if kind=='oldowner':f.binding['runtime_anchor']['main_owner']['pid']=1626184
            elif kind=='oldphase':f.binding['current_ce_phase']['expected']['founder_phase_record_sha256']='0'*64
            elif kind=='oldsocket':baseline['source_hashes'][str(M.GAME/'Scripts/dqn/socket_server.py')]='d99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214'
            elif kind=='control':f.binding['runtime_anchor']['control_hashes'][str(M.GAME/'models_dqn/learning_control.json')]='0'*64
            elif kind=='stale_baseline':f.values[baseline['actual_API']['path']]['optimized_samples']=1
            elif kind=='epoch':f.values[baseline['actual_API']['path']]['host_pipeline']['learning_exposure']['optimizer']['epoch']+=1
            elif kind=='historical_rescue':f.values[f.prior['native_plan']['path']]['evaluator_source_hashes']['Scripts/dqn/socket_server.py']=M.EVALUATOR['Scripts/dqn/socket_server.py']
            else:f.binding['predecessor_quality_plan']['identity']['inode']+=1
            with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):validate(f)

    def test_real_carrier_and_auditor_share2400_3600_gates_readiness_and_proof_delegation(self):
        f=fixture();bundle=validate(f);cfg=f.binding;root=Path(cfg['campaign']['output_directory'])
        plan=copy.deepcopy(f.predecessor);plan['output_directory']=str(root);plan['evaluator_source_hashes']=M.EVALUATOR;plan['execution_source_hashes']=M.EXECUTION
        for role in ('reference','candidate'):
            plan['checkpoints'][role].update(source=cfg[role]['path'],sha256=cfg[role]['sha256'],snapshot=str(root/'checkpoints'/(role+'.pt')))
        for leg in plan['legs']:
            directory=root/('%02d-%s'%(leg['index'],leg['role']))
            leg['job'].update(cohort_s=2400,timeout_s=3600,checkpoint=plan['checkpoints'][leg['role']]['snapshot'],directory=str(directory))
            for flag,value in (('--checkpoint',leg['job']['checkpoint']),('--job-dir',str(directory)),('--cohort-s','2400.0'),('--timeout-s','3600.0')):
                leg['command'][leg['command'].index(flag)+1]=value
            for field,name in (('receipt_path','receipt.json'),('console_log','console.log'),('evaluator_status_path','status.json')):
                leg[field]=str(directory/name)
        attrs=dict(CFG=cfg,BUNDLE=bundle,REFERENCE=Path(cfg['reference']['path']),REFERENCE_SHA=cfg['reference']['sha256'],
            CANDIDATE=Path(cfg['candidate']['path']),OUT=root,BINDINGS=M)
        with mock.patch.multiple(C,**attrs):
            argv=C.default_argv();self.assertEqual(argv[argv.index('--cohort-s')+1],'2400');self.assertEqual(argv[argv.index('--timeout-s')+1],'3600')
            C.validate_plan(plan,cfg['candidate']['sha256'])
            bound=dict(candidate_sha256=cfg['candidate']['sha256'],candidate_bytes=cfg['candidate']['bytes'],
                phase_cpu_job=cfg['evidence']['phase_cpu_job'],phase_cpu_proof=cfg['evidence']['phase_cpu_report'])
            health=bundle['baseline'];ready=copy.deepcopy(health);ready.update(schema='robotron-postaccepted-newgame-live8M-exclusive-readiness-v1',
                status='PASS',observed_unix_s=100,candidate=dict(source=cfg['candidate']['path'],sha256=cfg['candidate']['sha256'],bytes=cfg['candidate']['bytes'],
                    root_job_sha256=bound['phase_cpu_job']['sha256'],cpu_proof_sha256=bound['phase_cpu_proof']['sha256']),resources=dict(gpu0_uuid=C.GPU0,gpu1_uuid=C.GPU1,GPU0_free_bytes=15*(1<<30)))
            ready['resources'].update({k:True for k in ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free','no_competing_helpers',
                'no_private_cgroup_tmpfs_processes','no_pending_save','capture_and_CPU_units_released','commands_UID_cwd_exe_checked','held_environment_checked','unit_files_checked')})
            with mock.patch.object(C.time,'time',return_value=101),mock.patch.object(C,'sha',side_effect=lambda p:cfg['runtime_anchor']['unit_files'][str(p)]):
                C.readiness_contract(ready,bound)
                ready['actors'][0]['starttime_ticks']+=1
                with self.assertRaises(RuntimeError):C.readiness_contract(ready,bound)
            bad=copy.deepcopy(plan);bad['legs'][0]['job']['cohort_s']=1200
            with self.assertRaises(RuntimeError):C.validate_plan(bad,cfg['candidate']['sha256'])
        args=SimpleNamespace(campaign=root,candidate_sha256=cfg['candidate']['sha256'],candidate_bytes=cfg['candidate']['bytes'],
            cpu_job_sha256=cfg['evidence']['phase_cpu_job']['sha256'])
        with mock.patch.multiple(A,CFG=cfg,BINDINGS=M,BUNDLE=bundle,REFERENCE_SHA256=cfg['reference']['sha256']):
            A.validate_future_plan(plan,args,root);A.validate_cpu_proof(bundle['proof'],args)
            for key,value in (('min_full_games_per_leg',49),('max_attempts_per_leg',2),('include_full_completion_tail',False),('admission_extensions',True)):
                bad=copy.deepcopy(plan);bad['precommit'][key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):A.validate_future_plan(bad,args,root)

    def test_default_read_free_and_original_lifecycle_rows_classifiers_scoring_preserved(self):
        def bodies(path):
            source=path.read_text();return {n.name:ast.get_source_segment(source,n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
        old,new=bodies(BASE/'root_quality_carrier.py'),bodies(HERE/'root_quality_carrier.py')
        preserved=('require','sha','write','call','show','pinned_json','launch_argv','source_checks','prepare','launch','observe','archive','configure','main')
        for name in preserved:self.assertEqual(old[name],new[name])
        old,new=bodies(BASE/'audit_completed_leg.py'),bodies(HERE/'audit_completed_leg.py')
        for name in ('require','digest','unique_object','decode','lines','indexed','immutable','validate_cpu_proof','validate_original_context','classify_actor_lines','configure','main'):
            self.assertEqual(old[name],new[name])
        marker='    legdir = directory / f"{args.leg:02d}-{spec[\'role\']}"'
        self.assertEqual(old['audit'][old['audit'].index(marker):],new['audit'][new['audit'].index(marker):])
        source=(HERE/'quality_bindings.py').read_text()
        self.assertNotIn('torch',','.join(n.names[0].name for n in ast.parse(source).body if isinstance(n,ast.Import)))
        with mock.patch('builtins.open',side_effect=AssertionError('default must not read')),\
             mock.patch.object(Path,'read_bytes',side_effect=AssertionError('default must not read')),\
             mock.patch.object(C,'configure',side_effect=AssertionError('default must not import/select')),\
             mock.patch.object(A,'configure',side_effect=AssertionError('default must not import/select')),\
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(C.main([]),0);self.assertEqual(A.main([]),0)
        self.assertIn('PLAN_ONLY',output.getvalue())


if __name__=='__main__':unittest.main()
