"""One-shot read-only stdlib/proc/API readiness observation, not a benchmark."""
import datetime as dt
import errno
import hashlib
import json
import math
import re
import os
from pathlib import Path
import stat
import subprocess
import time
import urllib.request

OUT=Path(__file__).parent
GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
PRE=RUN/'inference-affinity-v2-live-20261017T0012Z/precommit.json'
OLD=RUN/'live-health-and-384M-readiness-independent-review-20261017/health-and-readiness-receipt.json'
REARM=RUN/'fresh3-384M-gate-rearmed-post-warmup-aa-reviewed1-20261017.json'
MASK=list(range(72))
CHECKS={}
ARTIFACTS={}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(name,value):
    data=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode() if not isinstance(value,bytes) else value
    path=OUT/name
    with path.open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    path.chmod(0o444)
    ARTIFACTS[name]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))

def check(name,value):
    CHECKS[name]=bool(value)

def command(argv):
    result=subprocess.run(argv,text=True,capture_output=True,timeout=10,check=False)
    return dict(argv=argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)

def state(pid):
    fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    return fields[0],int(fields[19])

def identify(pid,actor=False):
    path=Path('/proc')/str(pid)
    before_state,before=state(pid)
    words=[word.decode(errors='surrogateescape') for word in (path/'cmdline').read_bytes().split(b'\0') if word]
    uid=[int(word) for line in (path/'status').read_text().splitlines() if line.startswith('Uid:') for word in line.split()[1:]]
    slot=None
    if actor:
        values=[word.split(b'=',1)[1] for word in (path/'environ').read_bytes().split(b'\0')
                if word.startswith(b'ROBOTRON_CLIENT_SLOT=')]
        if len(values)!=1:raise ValueError('Ambiguous actor slot '+str(pid))
        slot=int(values[0])
    result=dict(pid=pid,starttime_ticks=before,uid=uid,cmdline=words,
        cwd=str((path/'cwd').resolve(strict=True)),exe=str((path/'exe').resolve(strict=True)),client_slot=slot)
    after_state,after=state(pid)
    if after!=before:raise ValueError('Process identity changed '+str(pid))
    return dict(identity=result,state=after_state,affinity=sorted(os.sched_getaffinity(pid)),
                cgroup=(path/'cgroup').read_text().strip())

def api(name):
    started=time.monotonic()
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=4) as response:
        data=response.read(1024**2)
    value=json.loads(data)
    write(name,data)
    return value,dict(monotonic=time.monotonic(),read_duration_s=time.monotonic()-started,
                      unix=time.time(),api_ts=value['ts'])

def api_health(raw,pre):
    hp=raw['host_pipeline'];g=hp['inference_graphs'];n=hp['native_batch_update'];b=raw['bank_persistence']
    e=hp['learning_exposure'];o=e['optimizer'];r=e['replay'];t=o['total']
    pending=t['attempts_started']-t['outcomes_recorded']
    identities=all({key:e[kind][key] for key in ('process_id','instance_monotonic_ns','epoch')}
                   ==pre['exposure_identity'][kind] for kind in ('optimizer','replay'))
    return dict(client_count=raw['client_count'],slots=sorted(row['client_slot'] for row in raw['client_rows']),
        healthy=raw['client_count']==192 and sorted(row['client_slot'] for row in raw['client_rows'])==list(range(192))
            and raw['training_enabled'] and not raw['measurement_active'] and raw['managed_experiment']=='best10M-fresh3-eps10-cap8-nosmooth'
            and raw['epsilon']==.1 and abs(raw['expert_ratio']-.1)<1e-12 and raw['lr']==2.5e-5
            and raw['memory_buffer_size']==6000000 and math.isfinite(raw['loss']) and math.isfinite(raw['grad_norm'])
            and not raw['pipeline_read_error'] and not raw['bank_persistence_read_error'],
        graphs=g['ready'] and g['capture_count']==128 and g['validation_replay_count']==640 and g['postload_validations']==1
            and g['runtime_capture_count']==0 and g['fallback_count']==0 and not g['fatal_error'],
        native=n['enabled'] and n['available'] and n['completed_count']==n['success_count'] and n['fallback_count']==n['error_count']==0,
        persistence=b['output']['backend']=='stream' and b['output']['stream_output_enabled']
            and not b['write_failures'] and not b['last_error'] and not any(v['errors'] for v in b['output']['totals'].values()),
        pipeline_errors={key:hp[key]['errors'] for key in ('inference','actor_refresh','target_refresh','learner_priority')},
        exposure=identities and pending in (0,1) and o['unclassified_started_total']==pending
            and (o['available'] or pending==1) and t['unavailable']==0 and o['prior_epoch_outcomes_total']==0
            and t['outcomes_recorded']==t['applied']+t['amp_skipped']+t['unavailable']
            and r['available'] and r['accepted_by_source_total']['unattributed']==0,
        optimizer_pending=pending,learner_frame_count=raw['learner_frame_count'],frame_count=raw['frame_count'],
        optimized_samples=raw['optimized_samples'],training_steps=raw['training_steps'],loss=raw['loss'],grad_norm=raw['grad_norm'],
        experiment=raw['managed_experiment'],quality_campaign=raw['quality_campaign'])

def main():
    start=time.time();campaign=GAME/'logs/managed-learning-20261015/quality-256M-vs-384M-20261017';leg=campaign/'02-candidate'
    launch=RUN/'quality384M-actual-durable-launch-reviewed1-20261017'
    plan=json.loads((campaign/'plan.json').read_text());status=json.loads((leg/'status.json').read_text());pre=json.loads(PRE.read_text());b=pre['bindings']
    check('actual_plan_hash_81210_exact',sha(campaign/'plan.json')=='81210cb86ad7cd78b3f9a7f4c764b83aad3364d0d8f0e382e29f340245a54704')
    job=plan['legs'][1]['job'];check('C1_fixed_inductor_FP32_16_diagnostics_protocol',job['inference_backend']=='inductor' and job['fp16'] is False and job['replay_enabled'] is False
      and job['actors']==16 and job['actor_slots']==list(range(4096,4112)) and job['cohort_s']==1200 and job['game_boundary_diagnostics'] is True)
    check('C1_active_collecting_ready_all16',status['active'] and status['phase']=='collecting' and not status['complete'] and status['reason'] is None
      and status['boundary']['ready'] and status['boundary']['clients']==status['boundary']['acknowledged']==16
      and status['boundary']['actor_slots']==list(range(4096,4112)) and status['abandoned']==0)
    check('C1_actual_start_cutoff1200s',status['close_ts']-status['start_ts']==1200 and status['start_ts']>=json.loads((campaign/'status.json').read_text())['legs'][1]['started_unix_s'])
    check('candidate384_checkpoint_metadata_bound',status['checkpoint_sha256']==plan['checkpoints']['candidate']['sha256']=='ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963')
    write('C1-status-snapshot.json',status)
    campaign_status=json.loads((campaign/'status.json').read_text());write('campaign-status-snapshot.json',campaign_status)
    controller=identify(3723673);evaluator=identify(3777403)
    check('controller_exact_identity',controller['identity']['starttime_ticks']==30468106 and controller['identity']['uid']==[1001]*4)
    check('evaluator_command_exact_job',evaluator['identity']['cmdline']==plan['legs'][1]['command'] and evaluator['identity']['uid']==[1001]*4)
    unit=command(['systemctl','--user','show','robotron-quality-256M-vs-384M-20261017.service',
      '--property=LoadState,ActiveState,SubState,MainPID,InvocationID,RemainAfterExit,ControlGroup,ExecMainStartTimestampMonotonic'])
    write('controller-unit-show.json',unit);u=dict(line.split('=',1) for line in unit['stdout'].splitlines() if '=' in line)
    check('controller_unit_original_invocation_running_retained',u['ActiveState']=='active' and u['SubState']=='running' and u['MainPID']=='3723673'
      and u['InvocationID']=='611d7a54ae7e4a649b0e1ed3505a7baa' and u['RemainAfterExit']=='yes')
    ownergroup='0::'+u['ControlGroup'];check('evaluator_same_owned_unit_cgroup',controller['cgroup']==evaluator['cgroup']==ownergroup)
    trainer=identify(3032848);actors=[identify(v['pid'],True) for v in b['actors']]
    check('main_identity_mask72_and_original192',trainer['identity']==b['worker']['trainer'] and trainer['affinity']==MASK and len(actors)==192 and
      all(a['identity']==expected and a['affinity']==MASK and a['cgroup']=='0::'+b['fleet_cgroup'] for a,expected in zip(actors,b['actors'])))
    threadpath=Path('/proc/3032848/task/3034065');check('original_inference_thread_mask72',int((threadpath/'stat').read_text().rsplit(')',1)[1].split()[19])==28613780
      and sorted(os.sched_getaffinity(3034065))==MASK)
    raw,api_time=api('main-API.json');health=api_health(raw,pre)
    check('main192_held_recipe_healthy',health['healthy'] and all(health[key] for key in ('graphs','native','persistence','exposure')) and not any(health['pipeline_errors'].values()))
    old=json.loads(OLD.read_text());sources={p:sha(p) for p in b['source_hashes']};controls={p:sha(p) for p in b['control_hashes']}
    check('main_source59_approved_binding_and_control2_held',sources==old['source_hashes'] and controls==b['control_hashes'])
    evaluator_sources={p:sha(GAME/p) for p in plan['evaluator_source_hashes']};execution_sources={p:sha(p) for p in plan['execution_source_hashes']}
    check('evaluator12_execution4_source_hashes_exact',evaluator_sources==plan['evaluator_source_hashes'] and execution_sources==plan['execution_source_hashes'])
    private=[];boot=[];actor_logs=[]
    for slot,pid in sorted((int(slot),pid) for slot,pid in status['actor_pids'].items()):
        actor=identify(pid,True);private.append(actor);words=actor['identity']['cmdline'];root=leg/'actors'/str(slot)
        paths_ok=all(flag in words and words[words.index(flag)+1]==str(root/name)
           for flag,name in (('-nvram_directory','nvram'),('-cfg_directory','cfg'),('-inipath','ini')))
        actor['private_paths_match']=paths_ok
        for rel,expected in plan['boot_assets']['files'].items():
            p=root/rel;boot.append(dict(slot=slot,path=str(p),sha256=sha(p),expected=expected['sha256'],bytes=p.stat().st_size))
        p=root/'console.log'
        with p.open('rb') as stream:
            stream.seek(max(0,p.stat().st_size-32768));data=stream.read(32768)
        write('actor-%d-console-tail.txt'%slot,data);text=data.decode(errors='replace')
        actor_logs.append(dict(slot=slot,path=str(p),connected='Socket connection opened to socket.127.0.0.1:9999' in text,
          wait_active='[robotron-socket-wait]' in text,timeout='[SOCKET ACTION TIMEOUT]' in text,
          refused='Connection refused' in text,traceback='Traceback' in text))
    check('private16_exactslots_ownedcgroup_privatepaths_mask72',len(private)==16 and [a['identity']['client_slot'] for a in private]==list(range(4096,4112)) and
      all(a['identity']['client_slot']==slot and a['cgroup']==ownergroup and a['private_paths_match'] and a['affinity']==MASK
          for a,slot in zip(private,range(4096,4112))))
    check('all16_current_privateboot_smallfiles_match_snapshot',len(boot)==48 and all(v['sha256']==v['expected'] for v in boot))
    check('all16_connected_socketwait_no_timeouts_or_refusals',all(v['connected'] and v['wait_active'] and not v['timeout'] and not v['refused'] and not v['traceback'] for v in actor_logs))
    bootpath=Path(plan['boot_assets']['manifest_path']);check('boot_manifest_still_exact',sha(bootpath)==plan['boot_assets']['manifest_sha256'])
    console=Path(plan['legs'][1]['console_log']);info=console.stat()
    with console.open('rb') as stream:stream.seek(max(0,info.st_size-65536));data=stream.read(65536)
    write('evaluator-console-tail.txt',data);text=data.decode(errors='replace')
    faults=[v for v in ('Traceback','RuntimeError','ExactInferenceGraphError','Training error:','CUDA out of memory','failed','fallback') if v.lower() in text.lower()]
    check('evaluator_listener_and_all16_forcedEVAL_console',all(('slot %d)'%slot) in text for slot in range(4096,4112))
      and 'SocketServer listening on 127.0.0.1:9999' in text and not faults)
    check('console_only_pinned_startup_and_exact_INGEST_diagnostics',all(line.startswith(('[LEARNING CONTROL]','Async inference batching','Raw full-game journal:','SocketServer listening','Client '))
      or re.fullmatch(r'W1017 .* 3777403 torch/_inductor/utils.py:1953\] \[0/0_1\] Not enough SMs to use max_autotune_gemm mode',line)
      or re.fullmatch(r'\[INGEST\] cid=\d+ continuous-play score dip [\d,]+ -> [\d,]+ at wave \d+; kept game id and monotone score',line)
      or not line.strip() for line in text.splitlines()))
    gpu=command(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits']);write('GPU-compute-inventory.json',gpu)
    rows=[[v.strip() for v in line.split(',')] for line in gpu['stdout'].splitlines() if line.strip()]
    pairs={(int(v[0]),v[1]) for v in rows};check('GPU0_only_private_evaluator_GPU1_only_main',gpu['returncode']==0 and pairs=={
      (3777403,'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'),(3032848,'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1')})
    carrier=json.loads((launch/'scheduling-carrier-result.json').read_text());before=json.loads((launch/'original-timer-show-after-carrier-reaped.json').read_text())
    check('carrier_reaped_before_timer_trigger_proof',carrier['returncode']==0 and carrier['carrier_reaped_by_subprocess_run'] is True
      and carrier['returned_unix_s']<plan['created_unix_s'] and 'LastTriggerUSecMonotonic=0' in before['stdout'])
    check('no_pending_save_or_oldCPUwatcher_helpers',not (GAME/'models_dqn/managed_save.request.json').exists() and not Path('/proc/3593422').exists() and not Path('/proc/3718158').exists())
    all_mame=[];other=[];disappear=0;allowed={3723673,3777403,os.getpid()}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:words=[v.decode(errors='replace') for v in (p/'cmdline').read_bytes().split(b'\0') if v]
        except OSError as error:
            if error.errno in (errno.ENOENT,errno.ESRCH):disappear+=1;continue
            raise
        if len(words)>1 and Path(words[0]).name=='mame' and words[1]=='robotron':all_mame.append(int(p.name))
        if int(p.name) in allowed:continue
        names={'checkpoint_at_frame.py','verify_saved_checkpoint.py','cuda_trace_parent.py','cuda_trace_worker.py','forensic_parent.py',
          'forensic_worker.py','cpu_reservation_trial.py','inference_worker_affinity.py','parallel_state_fill_trial.py','run_quality_campaign.py','run_frozen_sidecar.py'}
        if any(Path(word).name in names or Path(word).name.startswith('benchmark_') for word in words):other.append(dict(pid=int(p.name),cmdline=words))
    check('only208_expected_mainplusprivateRobotron_actors',sorted(all_mame)==sorted([a['identity']['pid'] for a in actors+private]))
    check('no_other_active_experiment_or_checkpoint_carrier',not other)
    receipt=dict(schema='robotron384-C1-startup-isolation-independent-v1',status='PASS' if all(CHECKS.values()) else 'AUDIT_NEEDS_REVIEW',
      observed_UTC=dt.datetime.now(dt.timezone.utc).isoformat(),checks=CHECKS,plan_sha256=sha(campaign/'plan.json'),unit=u,
      controller=controller,evaluator=evaluator,main_API_health=health,main_API_read_time=api_time,main_source_hashes=sources,controls=controls,
      evaluator_sources=evaluator_sources,execution_sources=execution_sources,private_actors=private,private_actor_logs=actor_logs,private_boot_files=boot,
      main_identity=trainer,main_actors=actors,carrier_provenance=dict(path=str(launch/'scheduling-carrier-result.json'),sha256=sha(launch/'scheduling-carrier-result.json'),
      returned_unix_s=carrier['returned_unix_s'],timer_before_trigger_sha256=sha(launch/'original-timer-show-after-carrier-reaped.json')),
      source_inferred_backend_proof=dict(requested='inductor',training=False,replay=False,fp16=False,
       constructor_must_complete_before_listener_and_fleet=True,warmed_shapes=list(range(1,17)),serving_thread_checked=True,
       strict_retrace_fallback_guard=True,FP32_TF32='Pinned InferenceActor numeric policy high/FP32/autocast-disabled; actual final report not yet published',
       evidence_paths=['tools/run_frozen_sidecar.py:159','tools/run_frozen_sidecar.py:464','Scripts/dqn/inference_actor.py:278']),
      backend_report_available_in_live_status=False,console_fault_matches=faults,other_experiments=other,proc_disappearances=disappear,
      artifacts=ARTIFACTS,collector_sha256=sha(__file__),
      limits=['Startup/isolation only; no final quality result, valid completed cohort, or promotion assessment',
      'Live status does not publish compile_report/numeric_policy; all1..16 warmup/serving proof is inferred from pinned fail-closed constructor ordering plus actual collecting/listening/connected actors. Final receipt must independently confirm runtime report',
      'Private checkpoint bytes were not loaded or hashed; approved frozen plan/leg metadata bind snapshot SHA, root CPU verification is separate',
      'Actor current private boot files all48 compared; source boot writer metadata/history not rerun',
      'No Torch/NumPy/import/tests/GPU context or inference requests; only readonly main API/proc/source/smalllogs/nvidia-smi, no signals/source/control/state/unit changes'])
    write('startup-isolation-receipt.json',receipt)
    fd=os.open(OUT,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps(dict(status=receipt['status'],checks=len(CHECKS),failed=[k for k,v in CHECKS.items() if not v],
      private_slots=[a['identity']['client_slot'] for a in private],main_learner=raw['learner_frame_count'],
      receipt=str(OUT/'startup-isolation-receipt.json'),sha256=sha(OUT/'startup-isolation-receipt.json')),indent=2))

if __name__=='__main__':main()
