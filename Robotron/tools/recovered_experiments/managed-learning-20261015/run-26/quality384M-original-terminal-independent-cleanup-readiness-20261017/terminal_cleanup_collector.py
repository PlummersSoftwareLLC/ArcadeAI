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
    start=time.time();campaign=GAME/'logs/managed-learning-20261015/quality-256M-vs-384M-20261017'
    unitname='robotron-quality-256M-vs-384M-20261017.service'
    invocation='611d7a54ae7e4a649b0e1ed3505a7baa'
    rawunit=command(['systemctl','--user','show',unitname])
    unit=dict(line.split('=',1) for line in rawunit['stdout'].splitlines() if '=' in line)
    assert rawunit['returncode']==0 and unit.get('InvocationID')==invocation and unit.get('ExecMainPID')=='3723673'
    assert unit.get('MainPID')=='0' and unit.get('SubState') in ('exited','failed','dead'),unit
    write('original-terminal-unit-full-show.json',rawunit)
    check('exact_original_retained_unit_terminal',unit.get('LoadState')=='loaded' and unit.get('RemainAfterExit')=='yes')
    cat=command(['systemctl','--user','cat',unitname]);write('original-terminal-unit-cat.json',cat)
    launch=RUN/'quality384M-actual-durable-launch-reviewed1-20261017'
    originalcat=json.loads((launch/'original-unit-cat.json').read_text())
    check('original_unit_bytes_held',cat['returncode']==0 and cat['stdout']==originalcat['stdout'])
    pre=json.loads(PRE.read_text());b=pre['bindings'];old=json.loads(OLD.read_text())
    check('exact_c45_precommit',sha(PRE)=='c45a70c7528ef2c1a40893c37cc9b925a140685e3a43563f7bd187b978119b97')
    first,first_read=api('api-first.json')
    trainer=identify(3032848);actors=[identify(row['pid'],True) for row in b['actors']]
    check('main_exact_original_identity_mask72',trainer['identity']==b['worker']['trainer'] and trainer['affinity']==MASK and trainer['state'] in ('R','S','D'))
    tp=Path('/proc/3032848/task/3034065')
    thread=dict(tid=3034065,starttime_ticks=int((tp/'stat').read_text().rsplit(')',1)[1].split()[19]),affinity=sorted(os.sched_getaffinity(3034065)))
    matches=[int(p.name) for p in Path('/proc/3032848/task').iterdir() if (p/'comm').read_text().strip()=='InferBatchWorke']
    check('inference_unique_original_ticks_mask72',thread['starttime_ticks']==28613780 and thread['affinity']==MASK and matches==[3034065])
    check('exact_original192_actor_identities_masks_cgroup',len(actors)==192 and all(row['identity']==expected and row['affinity']==MASK and row['state'] in ('R','S','D') and row['cgroup']=='0::'+b['fleet_cgroup'] for row,expected in zip(actors,b['actors'])))
    supervisor=identify(2258189)
    check('fleet_supervisor_exact_ticks_mask_cgroup',supervisor['identity']['starttime_ticks']==26614335 and supervisor['affinity']==MASK and supervisor['cgroup']=='0::'+b['fleet_cgroup'])
    units={}
    for label,name,pid,inv in [('trainer','robotron-managed-run-26-d3b365c9-trainer.service',3032848,'b14bebd992f84c80adc1fa21a7df3213'),('fleet','robotron-managed-run-26-d3b365c9-fleet.service',2258189,'5ade9b2810524877921946df11ea597e')]:
        result=command(['systemctl','--user','show',name,'--property=LoadState,ActiveState,SubState,MainPID,InvocationID,ControlGroup'])
        write(label+'-unit-show.json',result);values=dict(line.split('=',1) for line in result['stdout'].splitlines() if '=' in line);units[label]=values
        check(label+'_original_unit_running',result['returncode']==0 and values.get('MainPID')==str(pid) and values.get('ActiveState')=='active' and values.get('SubState')=='running' and values.get('InvocationID')==inv)
    sources={p:sha(p) for p in b['source_hashes']};controls={p:sha(p) for p in b['control_hashes']}
    check('source59_approved3_differences_exact',len(sources)==59 and sources==old['source_hashes'])
    check('control2_exact',len(controls)==2 and controls==b['control_hashes'])
    planpath=campaign/'plan.json';plan=json.loads(planpath.read_text())
    check('actual_plan_81210_held',sha(planpath)=='81210cb86ad7cd78b3f9a7f4c764b83aad3364d0d8f0e382e29f340245a54704')
    evsources={p:sha(GAME/p) for p in plan['evaluator_source_hashes']};exsources={p:sha(p) for p in plan['execution_source_hashes']}
    check('evaluator12_execution4_held',evsources==plan['evaluator_source_hashes'] and exsources==plan['execution_source_hashes'])
    bound=RUN/'quality384M-actual-default-plan-prelaunch-20261017/root-default-plan-source-archive-review.json'
    check('original_bound20_review_pin',sha(bound)=='27f39b2483a3c7c4e7362e6d600ff73464043b480248684db55b30c66cc51b6a')
    frozen={p:dict(expected=v['sha256'],current=sha(p),archived=sha(v['copy']),copy=v['copy']) for p,v in json.loads(bound.read_text())['source_entries'].items()}
    check('all20_frozen_current_and_archived_sources_held',len(frozen)==20 and all(v['current']==v['archived']==v['expected'] for v in frozen.values()))
    rawenv=dict(part.decode(errors='surrogateescape').split('=',1) for part in Path('/proc/3032848/environ').read_bytes().split(b'\0') if b'=' in part)
    selected={key:value for key,value in rawenv.items() if key.startswith(('DQN_','ROBOTRON_')) or key=='CUDA_VISIBLE_DEVICES'}
    envsha=hashlib.sha256(json.dumps(selected,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    check('selected_exec_recipe_environment_exact',envsha==b['environment_sha256'])
    prior=[]
    names=['quality384M-reference01-independent-startup-isolation-20261017','quality384M-candidate01-independent-startup-isolation-20261017','quality384M-reference02-independent-startup-isolation-20261017','quality384M-candidate02-independent-startup-isolation-20261017']
    refs=[]
    for name in names:
        p=RUN/name/'startup-isolation-receipt.json';r=json.loads(p.read_text());refs.append(dict(path=str(p),sha256=sha(p)))
        for row in [r['evaluator'],*r['private_actors']]:
            identity=row['identity'];pid=identity['pid']
            try:current=state(pid);owned=current[1]==identity['starttime_ticks']
            except OSError as error:
                if error.errno not in (errno.ENOENT,errno.ESRCH):raise
                current=None;owned=False
            prior.append(dict(pid=pid,original_start_ticks=identity['starttime_ticks'],current_state_start=None if current is None else list(current),original_owned_process_present=owned,provenance=name))
    try:current=state(3723673);controller_owned=current[1]==30468106
    except OSError as error:
        if error.errno not in (errno.ENOENT,errno.ESRCH):raise
        current=None;controller_owned=False
    check('original_controller_process_absent_identity_safe',not controller_owned)
    check('all_original64_privateactors_and4_evaluators_absent_identity_safe',len(prior)==68 and not any(v['original_owned_process_present'] for v in prior))
    originalgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+unitname
    cgpath=Path('/sys/fs/cgroup')/originalgroup.lstrip('/')
    cgrows=[]
    if cgpath.exists():
        for p in [cgpath/'cgroup.procs',*cgpath.rglob('*/cgroup.procs')]:
            cgrows.append(dict(path=str(p),pids=[int(v) for v in p.read_text().split()]))
    check('original_quality_cgroup_absent_or_empty',not any(v['pids'] for v in cgrows))
    write('original-private-owned-process-absence.json',dict(startup_receipts=refs,original_processes=prior,controller=dict(pid=3723673,original_start_ticks=30468106,current_state_start=None if current is None else list(current)),cgroup=str(cgpath),cgroup_present=cgpath.exists(),members=cgrows))
    devices=command(['nvidia-smi','--query-gpu=index,uuid,name,memory.used,memory.free','--format=csv,noheader,nounits'])
    apps=command(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'])
    write('GPU-inventory.json',dict(devices=devices,apps=apps))
    app_rows=[[v.strip() for v in line.split(',')] for line in apps['stdout'].splitlines() if line.strip()]
    gpu_rows=[[v.strip() for v in line.split(',')] for line in devices['stdout'].splitlines() if line.strip()]
    check('GPU0_no_compute_GPU1_only_main',apps['returncode']==0 and bool(app_rows) and all(v[0]=='3032848' and v[1]=='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1' for v in app_rows))
    check('GPU0_stableUUID_free14GiB',devices['returncode']==0 and any(v[0]=='0' and v[1]=='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0' and float(v[4])>=14*1024 for v in gpu_rows))
    listeners=[]
    for name in ('tcp','tcp6'):
        for line in (Path('/proc/net')/name).read_text().splitlines()[1:]:
            f=line.split()
            if int(f[1].rsplit(':',1)[1],16)==9999 and f[3]=='0A':listeners.append(dict(table=name,row=line))
    check('passive9999_no_listener',not listeners)
    names={'run_quality_campaign.py','run_frozen_sidecar.py','frozen_main.py','parallel_state_fill_trial.py','smoke_agent_cuda_graphs.py','inference_worker_affinity.py','cpu_affinity_pilot.py','cpu_reservation_trial.py','cuda_trace_parent.py','cuda_trace_worker.py','forensic_parent.py','forensic_worker.py','whole_agent_smoke.py','whole_agent_smoke_worker.py','checkpoint_at_frame.py','verify_saved_checkpoint.py','audit_payloads.py','restore_serial_after_parallel_trial.py','root_CPU_controller.py'}
    blocked=[];allmame=[];disappeared=0
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:words=[v.decode(errors='replace') for v in (p/'cmdline').read_bytes().split(b'\0') if v]
        except OSError as error:
            if error.errno in (errno.ENOENT,errno.ESRCH):disappeared+=1;continue
            raise
        if len(words)>1 and Path(words[0]).name=='mame' and words[1]=='robotron':allmame.append(int(p.name))
        if int(p.name)==os.getpid():continue
        if any(Path(word).name in names or Path(word).name.startswith('benchmark_') or word.rsplit('.',1)[-1]+'.py' in names or word.rsplit('.',1)[-1].startswith(('benchmark_','test_')) for word in words):
            blocked.append(dict(pid=int(p.name),cmdline=words,start_ticks=state(int(p.name))[1]))
    check('no_competing_helper_test_carrier_or_evaluator',not blocked)
    check('globalRobotronMAME_exact_original192',sorted(allmame)==sorted(v['pid'] for v in b['actors']))
    members=[int(v) for v in (Path('/sys/fs/cgroup')/b['fleet_cgroup'].lstrip('/')/'cgroup.procs').read_text().split()]
    check('fleet_cgroup_holds_all192_original_actors',all(pid in members for pid in allmame))
    shared=Path('/dev/shm');tmpfs=[str(p) for p in shared.iterdir() if p.is_dir() and p.name.startswith('robotron-snapshot-smoke-')]
    check('no_owned_private_tmpfs',not tmpfs)
    locks=[];lease=shared/'robotron-snapshot-smoke-gpu0.lock'
    if lease.exists():
        info=lease.stat();key='%02x:%02x:%d'%(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino)
        locks=[line for line in Path('/proc/locks').read_text().splitlines() if key in line.split()]
    check('no_recorded_GPU0_lease_lock',not locks)
    appcgroup=Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice');privategroups=[]
    for group in appcgroup.iterdir():
        if group.name.startswith(('robotron-snapshot-smoke-','robotron-verify384-')) and group.is_dir():
            owned=[]
            for p in [group/'cgroup.procs',*group.rglob('*/cgroup.procs')]:owned.extend(int(v) for v in p.read_text().split())
            privategroups.append(dict(path=str(group),pids=sorted(set(owned))))
    check('no_private_diagnostic_or_CPU_cgroup_processes',not any(v['pids'] for v in privategroups))
    check('no_pending_model_save_request',not (GAME/'models_dqn/managed_save.request.json').exists())
    remaining=5-(time.monotonic()-first_read['monotonic'])
    if remaining>0:time.sleep(remaining)
    final,last_read=api('api-final.json');firsthealth=api_health(first,pre);lasthealth=api_health(final,pre)
    for label,value in (('first',firsthealth),('final',lasthealth)):
        check(label+'_API192_held_recipe_finite_healthy',value['healthy'])
        check(label+'_graphs_native_persistence_exposure',all(value[key] for key in ('graphs','native','persistence','exposure')) and not any(value['pipeline_errors'].values()))
    check('learner_and_training_clocks_advance',final['learner_frame_count']>first['learner_frame_count'] and final['training_steps']>first['training_steps'] and final['optimized_samples']>first['optimized_samples'])
    check('main_inference_supervisor_ticks_held_at_end',state(3032848)[1]==28609635 and state(2258189)[1]==26614335 and int((tp/'stat').read_text().rsplit(')',1)[1].split()[19])==28613780)
    endunit=command(['systemctl','--user','show',unitname]);write('original-terminal-unit-full-show-recheck.json',endunit)
    lastunit=dict(line.split('=',1) for line in endunit['stdout'].splitlines() if '=' in line)
    check('retained_original_terminal_fields_held_through_audit',endunit['returncode']==0 and all(lastunit.get(k)==unit.get(k) for k in ('InvocationID','MainPID','ExecMainPID','ExecMainCode','ExecMainStatus','Result','SubState')))
    write('main-inference-fleet192-owners.json',dict(trainer=trainer,inference=thread,supervisor=supervisor,actors=actors,fleet_members=members))
    summary=json.loads((campaign/'summary.json').read_text())
    write('campaign-summary-metadata-snapshot.json',summary)
    receipt=dict(schema='robotron384-original-terminal-owned-cleanup-readiness-v1',status='CLEANUP_READINESS_PASS' if all(CHECKS.values()) else 'AUDIT_NEEDS_REVIEW',observed_start_UTC=dt.datetime.fromtimestamp(start,dt.timezone.utc).isoformat(),observed_end_UTC=dt.datetime.now(dt.timezone.utc).isoformat(),checks=CHECKS,original_unit=dict(unit=unitname,invocation=invocation,ExecMainPID=3723673,start_ticks=30468106,ExecMainCode=unit.get('ExecMainCode'),ExecMainStatus=unit.get('ExecMainStatus'),Result=unit.get('Result'),SubState=unit.get('SubState'),released_by_auditor=False),units=units,plan_sha256=sha(planpath),source_hashes=sources,controls=controls,evaluator_sources=evsources,execution_sources=exsources,frozen20_sources=frozen,selected_exec_environment_sha256=envsha,API_first=firsthealth,API_final=lasthealth,API_read_times=dict(first=first_read,last=last_read),learner_delta=final['learner_frame_count']-first['learner_frame_count'],training_step_delta=final['training_steps']-first['training_steps'],blocked_processes=blocked,unclassified_proc_disappearances=disappeared,passive9999=listeners,private_tmpfs=tmpfs,private_cgroups=privategroups,lease_locks=locks,artifacts=ARTIFACTS,collector_sha256=sha(__file__),saved_summary_scope=dict(outcome=summary.get('outcome'),qualified_improvement=summary.get('qualified_improvement'),reason=summary.get('reason')),quality_qualification_assessed_by_this_audit=False,limits=['Cleanup/readiness only, separate from actual original-row scientific audits and strict protection review; no promotion or release authorized/performed by this receipt','Identity-aware original private-process absence handles PID reuse; main192 identities/full leader masks/inference mask checked, not every trainer/newborn TID','No model/tensor/framework/numerical import/test/default or helper invocation; source and small metadata only','Only readonly main HTTP API plus passive proc/net/systemd/nvidia-smi; no port probe or bind, signals, service writes, source/control/state changes','No new full log-history or scientific/backend validation; original original-row audits and root terminal archive remain required','Retained terminal quality unit is deliberately allowed; original exit evidence stays available for root archive/review'])
    write('cleanup-readiness-receipt.json',receipt);fd=os.open(OUT,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps(dict(status=receipt['status'],checks=len(CHECKS),failed=[k for k,v in CHECKS.items() if not v],original_exit=dict(code=unit.get('ExecMainCode'),status=unit.get('ExecMainStatus'),result=unit.get('Result')),learner_first=first['learner_frame_count'],learner_final=final['learner_frame_count'],private_originals_checked=len(prior),receipt=str(OUT/'cleanup-readiness-receipt.json'),sha256=sha(OUT/'cleanup-readiness-receipt.json')),indent=2))
if __name__=='__main__':main()
