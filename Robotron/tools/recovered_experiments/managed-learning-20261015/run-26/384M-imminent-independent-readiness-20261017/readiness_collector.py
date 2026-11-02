"""One-shot read-only stdlib/proc/API readiness observation, not a benchmark."""
import datetime as dt
import errno
import hashlib
import json
import math
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
    start=time.time()
    pre=json.loads(PRE.read_text());old=json.loads(OLD.read_text());rearm=json.loads(REARM.read_text())
    check('baseline_precommit_c45_exact',sha(PRE)=='c45a70c7528ef2c1a40893c37cc9b925a140685e3a43563f7bd187b978119b97')
    check('rearm_receipt_2194_exact',sha(REARM)=='2194da68c964a0b8dc6b373d138baefcfa1570810c36cbb964eea4e7a0fb7f54')
    first,first_read=api('api-first.json')
    b=pre['bindings'];main=identify(3032848)
    check('trainer_exact_precommit_identity',main['identity']==b['worker']['trainer'])
    check('trainer_healthy_and_leader72',main['state'] in ('R','S','D') and main['affinity']==MASK)
    tid=3034065;threadpath=Path('/proc/3032848/task')/str(tid)
    threadfields=(threadpath/'stat').read_text().rsplit(')',1)[1].split()
    threads=[int(path.name) for path in Path('/proc/3032848/task').iterdir() if (path/'comm').read_text().strip()=='InferBatchWorke']
    thread=dict(tid=tid,starttime_ticks=int(threadfields[19]),affinity=sorted(os.sched_getaffinity(tid)),matches=threads)
    check('inference_exact_unique_identity_mask72',thread['starttime_ticks']==28613780 and threads==[tid] and thread['affinity']==MASK)
    actors=[identify(row['pid'],True) for row in b['actors']]
    actor_problems=[row['identity']['pid'] for row,expected in zip(actors,b['actors'])
        if row['identity']!=expected or row['affinity']!=MASK or row['state'] not in ('R','S','D')
            or row['cgroup']!='0::'+b['fleet_cgroup']]
    check('all192_original_actor_identities_cgroups_masks',not actor_problems and len(actors)==192)
    supervisor=identify(2258189)
    check('fleet_supervisor_exact_ticks_and_mask',supervisor['identity']['starttime_ticks']==26614335 and supervisor['affinity']==MASK
          and supervisor['cgroup']=='0::'+b['fleet_cgroup'])
    units={}
    for label,unit,pid,ticks in (
      ('trainer','robotron-managed-run-26-d3b365c9-trainer.service',3032848,28609635),
      ('fleet','robotron-managed-run-26-d3b365c9-fleet.service',2258189,26614335),
      ('watcher',rearm['unit'],3593422,30108625)):
        record=command(['systemctl','--user','show',unit,'--property=ActiveState,SubState,MainPID,InvocationID,ControlGroup,ExecStart,RemainAfterExit'])
        write(label+'-unit-show.json',record)
        values=dict(line.split('=',1) for line in record['stdout'].splitlines() if '=' in line)
        units[label]=values
        check(label+'_unit_live_exact_pid',record['returncode']==0 and values['ActiveState']=='active'
              and values['SubState']=='running' and values['MainPID']==str(pid) and state(pid)[1]==ticks)
    check('trainer_invocation_b14',units['trainer']['InvocationID'].startswith('b14'))
    check('fleet_invocation_5ade',units['fleet']['InvocationID'].startswith('5ade'))
    check('watcher_invocation_2eca_exact',units['watcher']['InvocationID']==rearm['invocation_id'])
    watcher=identify(3593422)
    check('watcher_argv_target_label_output_exact',watcher['identity']['cmdline']==rearm['actual_argv'])
    check('original_gate_deadline_held',rearm['original_deadline_unix_s']==1792220146.61131 and time.time()<rearm['original_deadline_unix_s'])
    waitlog=Path(rearm['waiting_log']).read_bytes();write('watcher-waiting-log.txt',waitlog)
    check('watcher_no_capture_request_yet',hashlib.sha256(waitlog).hexdigest()==
          old['artifacts']['checkpoint-waiting-log.txt']['sha256'])
    pending=[GAME/'models_dqn/managed-checkpoints/fresh3-384M.pt',RUN/'fresh3-384M-gate.json',GAME/'models_dqn/managed_save.request.json']
    pending_state={str(path):path.exists() for path in pending}
    check('no384_candidate_report_pending_request',not any(pending_state.values()))
    current_sources={path:sha(path) for path in b['source_hashes']}
    diffs={path:dict(previous=b['source_hashes'][path],current=value) for path,value in current_sources.items()
           if value!=b['source_hashes'][path]}
    expected={
        str(GAME/'Scripts/dqn/socket_server.py'):'d99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214',
        str(GAME/'Scripts/dqn/game_journal.py'):'10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0',
        str(GAME/'Scripts/dqn/test_measurement_actor.py'):'c1d2c2270aaf90c6fce61968bd9b4bffa7bc1a48f61ca8c752e5f29cd5e2abc9'}
    check('source59_exact_except_approved3',len(current_sources)==59 and {path:item['current'] for path,item in diffs.items()}==expected)
    controls={path:sha(path) for path in b['control_hashes']}
    check('both_controls_exact',controls==b['control_hashes'])
    env=dict(part.decode(errors='surrogateescape').split('=',1) for part in Path('/proc/3032848/environ').read_bytes().split(b'\0') if b'=' in part)
    selected={key:value for key,value in env.items() if key.startswith(('DQN_','ROBOTRON_')) or key=='CUDA_VISIBLE_DEVICES'}
    envsha=hashlib.sha256(json.dumps(selected,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    check('selected_exec_environment_exact',envsha==b['environment_sha256'])
    paths={
      'runbook':(RUN/'fresh-quality-256M-vs-384M-diagnostics-bound-runbook-20261017.txt','229c57f79f4f50696b8c8f2470f4636b7e5787dec95922d4bf8f260882004700'),
      'verifier':(RUN/'quality384M-checkpoint-verification-preparation-20261017/verify_saved_checkpoint.py','527f2b9928bae9d58f7d8cd9984dfa126aa32f671af3e48935087870a1c9edd9'),
      'auditor':(RUN/'quality384M-original-row-leg-audit-preparation-20261017/audit_completed_leg.py','47debecaf6a851d00b7d8717cdb342a9b551fe197e659a0c04594195412f7044'),
      'sidecar':(GAME/'tools/run_frozen_sidecar.py','cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90'),
      'campaign':(GAME/'tools/run_quality_campaign.py','574e56f28499c751c639ee8a3474eecd5ca8de8c896da3dd44d5e4fc2fe60128')}
    ready_sources={name:dict(path=str(path),sha256=sha(path),expected=expected) for name,(path,expected) in paths.items()}
    check('future_verifier_runbook_auditor_execution_sources_exact',all(row['sha256']==row['expected'] for row in ready_sources.values()))
    gpu=command(['nvidia-smi','--query-gpu=index,uuid,name,memory.used,memory.free','--format=csv,noheader,nounits'])
    apps=command(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'])
    write('gpu-inventory.json',dict(devices=gpu,apps=apps))
    app_rows=[[v.strip() for v in line.split(',')] for line in apps['stdout'].splitlines() if line.strip()]
    check('GPU0_no_compute_and_GPU1_only_exact_main',apps['returncode']==0 and app_rows
        and all(row[0]=='3032848' and row[1]=='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1' for row in app_rows))
    devices=[[v.strip() for v in line.split(',')] for line in gpu['stdout'].splitlines() if line.strip()]
    check('GPU0_uuid_free_margin',gpu['returncode']==0 and any(row[0]=='0' and row[1]=='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
          and float(row[4])>=14*1024 for row in devices))
    listeners=[]
    for filename in ('tcp','tcp6'):
        for line in (Path('/proc/net')/filename).read_text().splitlines()[1:]:
            fields=line.split()
            if int(fields[1].rsplit(':',1)[1],16)==9999 and fields[3]=='0A':listeners.append(dict(table=filename,row=line))
    check('port9999_no_listener_passive',not listeners)
    blocked_names={'run_quality_campaign.py','run_frozen_sidecar.py','frozen_main.py','parallel_state_fill_trial.py',
      'smoke_agent_cuda_graphs.py','inference_worker_affinity.py','cpu_affinity_pilot.py','cpu_reservation_trial.py',
      'cuda_trace_parent.py','cuda_trace_worker.py','forensic_parent.py','forensic_worker.py',
      'whole_agent_smoke.py','whole_agent_smoke_worker.py','checkpoint_at_frame.py','verify_saved_checkpoint.py',
      'audit_payloads.py','restore_serial_after_parallel_trial.py'}
    blocked=[];all_mame=[];vanished=0
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():continue
        pid=int(entry.name)
        try:words=[part.decode(errors='replace') for part in (entry/'cmdline').read_bytes().split(b'\0') if part]
        except OSError as error:
            if error.errno in (errno.ENOENT,errno.ESRCH):vanished+=1;continue
            raise
        if len(words)>1 and Path(words[0]).name=='mame' and words[1]=='robotron':all_mame.append(pid)
        if pid in (os.getpid(),3593422):continue
        if any(Path(word).name in blocked_names or Path(word).name.startswith('benchmark_')
               or word.rsplit('.',1)[-1]+'.py' in blocked_names
               or word.rsplit('.',1)[-1].startswith(('benchmark_','test_')) for word in words):
            blocked.append(dict(pid=pid,cmdline=words,start_ticks=state(pid)[1]))
    check('no_competing_named_process_or_carrier',not blocked)
    check('exact192_global_robotron_mame',sorted(all_mame)==sorted(row['pid'] for row in b['actors']))
    fleet_members=[int(v) for v in (Path('/sys/fs/cgroup')/b['fleet_cgroup'].lstrip('/')/'cgroup.procs').read_text().split()]
    check('fleet_cgroup_contains_exact_original_mame',sorted(pid for pid in fleet_members if pid in all_mame)==sorted(all_mame))
    shared=Path('/dev/shm');owned_tmpfs=[str(path) for path in shared.iterdir() if path.is_dir() and path.name.startswith('robotron-snapshot-smoke-')]
    check('no_owned_snapshot_tmpfs_directory',not owned_tmpfs)
    lock=shared/'robotron-snapshot-smoke-gpu0.lock';locks=[]
    if lock.exists():
        info=lock.stat();key='%02x:%02x:%d'%(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino)
        locks=[line for line in Path('/proc/locks').read_text().splitlines() if key in line.split()]
    check('snapshot_GPU0_lease_has_no_recorded_lock',not locks)
    remaining=5-(time.monotonic()-first_read['monotonic'])
    if remaining>0:time.sleep(remaining)
    final,last_read=api('api-final.json')
    firsthealth=api_health(first,pre);lasthealth=api_health(final,pre)
    for label,value in (('first',firsthealth),('final',lasthealth)):
        check(label+'_API_healthy_192_held_recipe',value['healthy'])
        check(label+'_API_graph_native_persistence_exposure',all(value[key] for key in ('graphs','native','persistence','exposure'))
              and not any(value['pipeline_errors'].values()))
    elapsed=final['ts']-first['ts'];delta=final['learner_frame_count']-first['learner_frame_count']
    rate=delta/elapsed if elapsed>0 else None
    remain=388629023-final['learner_frame_count'];eta=remain/rate if rate and rate>0 else None
    window=dict(first_read=first_read,last_read=last_read,first_learner=first['learner_frame_count'],final_learner=final['learner_frame_count'],
        API_elapsed_s=elapsed,learner_delta=delta,learner_per_s=rate,remaining=remain,eta_s=eta,
        target_eta_UTC=dt.datetime.fromtimestamp(final['ts']+eta,dt.timezone.utc).isoformat() if eta is not None else None,
        scope='Short two API endpoints, not a controlled speed comparison or capture guarantee')
    check('learner_progressing_below_exact_capture_target',delta>0 and remain>0)
    check('owned_main_and_watcher_still_same_at_end',state(3032848)[1]==28609635 and state(3593422)[1]==30108625)
    write('owner-identities.json',dict(trainer=main,inference=thread,supervisor=supervisor,watcher=watcher,actors=actors,
        actor_problems=actor_problems,fleet_members=fleet_members))
    receipt=dict(schema='robotron-imminent384-independent-readiness-v1',status='PASS' if all(CHECKS.values()) else 'AUDIT_NEEDS_REVIEW',
        observed_UTC=dt.datetime.now(dt.timezone.utc).isoformat(),start_unix=start,end_unix=time.time(),checks=CHECKS,
        baseline_precommit=dict(path=str(PRE),sha256=sha(PRE)),source_hashes=current_sources,source_differences=diffs,
        controls=controls,selected_environment_sha256=envsha,ready_sources=ready_sources,API_first=firsthealth,API_final=lasthealth,
        window=window,units=units,watcher_rearm_sha256=sha(REARM),original_gate_deadline_unix=rearm['original_deadline_unix_s'],
        pending_candidate_paths=pending_state,blocked_processes=blocked,unclassified_disappearances=vanished,
        passive9999_listeners=listeners,snapshot_tmpfs=owned_tmpfs,snapshot_lease_locks=locks,
        artifacts=ARTIFACTS,collector_sha256=sha(__file__),
        limitations=['Only leader/inference/192 actor masks, not every trainer/newborn TID',
          'Selected /proc environment is exec-time, not every later Python environment mutation',
          'No runtime log-history byte scan, model/replay/tensor read, testing, numerical import, GPU context, socket probe/bind, signals or service mutations',
          'API-only HTTP requests and nvidia-smi compute inventory; free GPU0 means no compute owner, display use may exist',
          'Future candidate SHA/bytes/saved clocks/CPU proof/new frozen quality plan remain unknown; readiness does not certify pending candidate',
          'All future4 quality legs require diagnostics true and independent original-row/full-tail audits; no reused reference pool'])
    write('readiness-receipt.json',receipt)
    fd=os.open(OUT,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps(dict(status=receipt['status'],checks=len(CHECKS),failed=[key for key,value in CHECKS.items() if not value],
        receipt=str(OUT/'readiness-receipt.json'),sha256=sha(OUT/'readiness-receipt.json'),window=window),indent=2))

if __name__=='__main__':main()
