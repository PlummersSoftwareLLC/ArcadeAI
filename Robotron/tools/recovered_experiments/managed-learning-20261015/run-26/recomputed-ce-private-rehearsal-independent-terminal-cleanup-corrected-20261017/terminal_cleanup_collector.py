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
    start=time.time();pre=json.loads(PRE.read_text());b=pre['bindings'];old=json.loads(OLD.read_text())
    check('exact_c45_precommit',sha(PRE)=='c45a70c7528ef2c1a40893c37cc9b925a140685e3a43563f7bd187b978119b97')

    reporting=RUN/'confirmed384M-reporting-root-adoption-20261017/root-reporting-adoption-receipt.json'
    check('actual_reporting_adoption_pin',sha(reporting)=='0e82f70a3e72a6d4eead0e30e9d1e56f263d34b9c9f8e426393a879baa0baa2b')
    readiness=RUN/'recomputed-ce-private-rehearsal-source-launch-readiness-independent-20261017/review-receipt.json'
    check('private_source_readiness2b11_pin',sha(readiness)=='2b11d882937dfda5f3f63b231c1540735e4610644b1cc60c764f8c179c0560be')
    prior=json.loads(readiness.read_text());source45=[]
    for spec in prior['checks']:
        p=Path(spec['path'])
        if p.suffix=='.pt':raise ValueError('Unexpected model in source-only pin set')
        source45.append(dict(path=str(p),expected=spec['sha256'],actual=sha(p)))
    check('all45_private_source_readiness_pins_held',len(source45)==45 and all(v['expected']==v['actual'] for v in source45))
    write('private-rehearsal45-source-pins.json',source45)
    fixture=prior['fixed_fixture'];fp=Path(fixture['source']);fs=fp.lstat()
    check('saved320_fixture_readonly_stat_only',stat.S_ISREG(fs.st_mode) and stat.S_IMODE(fs.st_mode)==0o444 and fs.st_uid==os.getuid() and fs.st_nlink==1 and fs.st_size==275181008)
    check('saved320_CPU_receipt_unchanged',sha(fixture['receipt'])==fixture['receipt_sha256']=='0f1cf4820804971b7b13f02604a6d0f73e5579f34a68a45312d212d4a1a51068')

    output=RUN/'recomputed-ce-private-rehearsal-reviewed1-20261017'
    archivepath=RUN/'recomputed-ce-private-rehearsal-original-terminal-root-archive-20261017/archive-receipt.json'
    check('root_original_terminal_archive5f4021_pin',sha(archivepath)=='5f4021b286bef961a3df056e08a297765efd7e553686f0dec45944502ca6cd8e')
    archive=json.loads(archivepath.read_text());manifest=json.loads((output/'launch-manifest.json').read_text())
    result=json.loads((output/'result.json').read_text());owner=json.loads((output/'ownership.json').read_text())
    unitname='robotron-snapshot-smoke-recomputed-ce-reviewed1-20261017.service';invocation='136170c1b57f4cd2b1fa243f6c820748'
    initialunit=command(['systemctl','--user','show',unitname]);write('original-private-terminal-full-show.json',initialunit)
    u=dict(line.split('=',1) for line in initialunit['stdout'].splitlines() if '=' in line)
    check('same_original_retained_parent_terminal_success',initialunit['returncode']==0 and u.get('InvocationID')==invocation and u.get('ExecMainPID')=='3987420' and u.get('MainPID')=='0' and u.get('ExecMainCode')=='1' and u.get('ExecMainStatus')=='0' and u.get('Result')=='success' and u.get('SubState')=='exited' and u.get('RemainAfterExit')=='yes')
    cat=command(['systemctl','--user','cat',unitname]);write('original-private-terminal-unit-cat.json',cat)
    check('archived_original_parent_identity_and_exit_match',archive['original_invocation']==invocation and archive['original_exec_main_pid']==3987420 and archive['original_start_ticks']=='31155810' and archive['original_exec_main_code']==1 and archive['original_exec_main_status']==0 and archive['unit_released'] is False)
    identity=output.lstat();check('owned_output_identity_nonce_parent_held',owner['nonce']==manifest['nonce'] and owner['output']==manifest['output_identity']==dict(device=identity.st_dev,inode=identity.st_ino) and owner['parent']==manifest['parent'] and manifest['parent']['pid']==3987420 and manifest['parent']['start_ticks']=='31155810' and manifest['parent']['pgid']==3987420 and owner['tmpfs']==manifest['tmpfs_identity'])
    check('manifest_exact_reviewed_parent_worker_lock',manifest['parent_sha256']=='90e31926cd3222e32ae7aa5890d47ad65737f3241f3327d96751f2a22e1f5749' and manifest['worker_sha256']=='53ab48313f79bc6cdae6ba2ab70969a229ec478ff94b7d52a331c8c64dd37464' and manifest['source_lock_sha256']=='28870c3cf7594cc0ac8f73eb3760e3665d5d4448668f4bf9010268427ec80dd3')
    retained=[]
    for item in archive['retained_artifacts']:
        retained.append(dict(source=item['source'],archive=item['archive'],expected=item['sha256'],source_sha256=sha(item['source']),archive_sha256=sha(item['archive'])))
    check('all_root_archived_small_original_artifacts_match',all(v['source_sha256']==v['archive_sha256']==v['expected'] for v in retained))
    write('root-archived-small-artifacts-bindings.json',retained)
    private_sources=[]
    package=Path(manifest['native_compiler_cache']['path']).parent
    for name,spec in manifest['sources'].items():
        p=package/name
        if p.suffix!='.py' and name!='sumtree.c':raise ValueError('Unexpected non-source private package member')
        private_sources.append(dict(name=name,source=spec['source'],copy=str(p),expected=spec['sha256'],source_sha256=sha(spec['source']),copy_sha256=sha(p)))
    check('actual_private_source_copies_match_original_pins',all(v['source_sha256']==v['copy_sha256']==v['expected'] for v in private_sources))
    write('actual-private-source-bindings.json',private_sources)
    absent=[];children=[]
    def absence(pid,ticks,label):
        try:current=state(pid);same=current[1]==int(ticks)
        except OSError as error:
            if error.errno not in (errno.ENOENT,errno.ESRCH):raise
            current=None;same=False
        absent.append(dict(label=label,pid=pid,owned_start_ticks=str(ticks),current_state_start=None if current is None else list(current),original_owned_process_present=same))
    absence(3987420,31155810,'parent')
    for role in ('capture','recompute'):
        p=output/role/'child-exit.json';child=json.loads(p.read_text());ident=child['owned_identity']
        absence(ident['pid'],ident['start_ticks'],role);children.append(child)
        check(role+'_actual_Popen_exit0_token_owned_and_reaped',child['variant']==role and child['pid']==ident['pid'] and ident['ppid']==3987420 and ident['pgid']==ident['pid'] and child['actual_returncode']==0 and child['token_released'] is True)
    check('parent_and_both_original_children_absent_identity_safe',len(absent)==3 and not any(v['original_owned_process_present'] for v in absent))
    check('exact_owned_tmpfs_removed',not Path(manifest['tmpfs']).exists())
    check('exact_owned_child_cgroup_removed',not Path(manifest['cgroup']).exists())
    servicegroup=Path(manifest['cgroup']).parent;owned_members=[]
    if servicegroup.exists():
        for p in [servicegroup/'cgroup.procs',*servicegroup.rglob('*/cgroup.procs')]:
            owned_members.append(dict(path=str(p),pids=[int(v) for v in p.read_text().split()]))
    check('retained_private_service_cgroup_absent_or_empty',not any(v['pids'] for v in owned_members))
    check('no_parent_or_phase_failure_record',not any((output/name).exists() for name in ('failure.json','cleanup-failure.json')) and not any((output/role/'phase-failure.json').exists() for role in ('capture','recompute')))
    check('parent_declares_fixed_diagnostic_complete_without_qualification',result['status']=='OBSERVATIONS_COMPLETE' and result['qualification_pass'] is False and result['owned_cleanup_complete'] is True and [v['variant'] for v in result['variants']]==['capture','recompute'])
    capture,recompute=result['variants']
    check('scope_one_original4_capture_fresh_conditional_recompute',capture['consumed_attempts']==1 and capture['capture_complete'] is True and capture['loss_abi']==4 and capture['optimizer_outcome']=='amp_skipped' and capture['lease_released'] is True and capture['producer_closed'] is True and recompute['conditional_recomputed'] is True and recompute['executed_target_observed'] is False and recompute['optimizer_steps']==0 and recompute['explicit_worker_backward_calls']==0)
    context=dict(archive_receipt_sha256=sha(archivepath),manifest_sha256=sha(output/'launch-manifest.json'),result_sha256=sha(output/'result.json'),nonce=manifest['nonce'],parent=manifest['parent'],output_identity=manifest['output_identity'],tmpfs=manifest['tmpfs'],tmpfs_identity=manifest['tmpfs_identity'],cgroup=manifest['cgroup'],cgroup_identity=manifest['cgroup_identity'],launch_token_sha256=hashlib.sha256(manifest['launch_token'].encode()).hexdigest(),owned_process_absence=absent,owned_children=children,service_cgroup_members=owned_members,declared_result_scope=dict(status=result['status'],qualification_pass=result['qualification_pass'],comparison_pass=result['comparison_pass'],interpretation_requires_review=result['interpretation_requires_review'],capture_outcome=capture['optimizer_outcome']))
    write('actual-owned-private-context-and-child-exits.json',context)

    first,first_read=api('api-first.json')
    trainer=identify(3032848)
    check('main_exact_original_identity_mask72',trainer['identity']==b['worker']['trainer'] and trainer['affinity']==MASK and trainer['state'] in ('R','S','D'))
    tid=3034065;tp=Path('/proc/3032848/task')/str(tid)
    thread=dict(tid=tid,starttime_ticks=int((tp/'stat').read_text().rsplit(')',1)[1].split()[19]),affinity=sorted(os.sched_getaffinity(tid)))
    matches=[int(p.name) for p in Path('/proc/3032848/task').iterdir() if (p/'comm').read_text().strip()=='InferBatchWorke']
    check('inference_unique_original_ticks_mask72',thread['starttime_ticks']==28613780 and thread['affinity']==MASK and matches==[tid])
    actors=[identify(row['pid'],True) for row in b['actors']]
    check('exact_original192_actor_identities_masks_cgroup',len(actors)==192 and all(row['identity']==expected and row['affinity']==MASK
        and row['state'] in ('R','S','D') and row['cgroup']=='0::'+b['fleet_cgroup'] for row,expected in zip(actors,b['actors'])))
    supervisor=identify(2258189)
    check('fleet_supervisor_exact_ticks_mask_cgroup',supervisor['identity']['starttime_ticks']==26614335 and supervisor['affinity']==MASK and supervisor['cgroup']=='0::'+b['fleet_cgroup'])
    units={}
    specifications=[('trainer','robotron-managed-run-26-d3b365c9-trainer.service',3032848,'b14bebd992f84c80adc1fa21a7df3213'),
      ('fleet','robotron-managed-run-26-d3b365c9-fleet.service',2258189,'5ade9b2810524877921946df11ea597e'),
      ('released_watcher','robotron-checkpoint-384M-run26-rearmed-post-warmup-aa-reviewed1-20261017.service',0,None),
      ('released_CPUhelper','robotron-verify384-checkpoint-cpu-reviewed1-20261017.service',0,None)]
    for label,unit,pid,inv in specifications:
        result=command(['systemctl','--user','show',unit,'--property=LoadState,ActiveState,SubState,MainPID,InvocationID,ControlGroup'])
        write(label+'-unit-show.json',result)
        values=dict(line.split('=',1) for line in result['stdout'].splitlines() if '=' in line);units[label]=values
        check(label+'_current_unit_status',values.get('MainPID')==str(pid) and
          ((values.get('LoadState')=='not-found') if pid==0 else
           (values.get('ActiveState')=='active' and values.get('SubState')=='running' and values.get('InvocationID')==inv)))
    check('released_watcher_and_CPUhelper_PIDs_absent',not Path('/proc/3593422').exists() and not Path('/proc/3718158').exists())
    sources={path:sha(path) for path in b['source_hashes']};controls={path:sha(path) for path in b['control_hashes']}
    check('source59_current_approved_binding_exact',sources==old['source_hashes'] and len(sources)==59)
    check('control2_exact',controls==b['control_hashes'])
    rawenv=dict(part.decode(errors='surrogateescape').split('=',1) for part in Path('/proc/3032848/environ').read_bytes().split(b'\0') if b'=' in part)
    selected={key:value for key,value in rawenv.items() if key.startswith(('DQN_','ROBOTRON_')) or key=='CUDA_VISIBLE_DEVICES'}
    envsha=hashlib.sha256(json.dumps(selected,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    check('selected_exec_recipe_environment_exact',envsha==b['environment_sha256'])
    devices=command(['nvidia-smi','--query-gpu=index,uuid,name,memory.used,memory.free','--format=csv,noheader,nounits'])
    apps=command(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_gpu_memory','--format=csv,noheader,nounits'])
    write('GPU-inventory.json',dict(devices=devices,apps=apps))
    app_rows=[[v.strip() for v in line.split(',')] for line in apps['stdout'].splitlines() if line.strip()]
    gpu_rows=[[v.strip() for v in line.split(',')] for line in devices['stdout'].splitlines() if line.strip()]
    check('GPU0_no_compute_GPU1_only_main',apps['returncode']==0 and bool(app_rows) and
      all(row[0]=='3032848' and row[1]=='GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1' for row in app_rows))
    check('GPU0_stableUUID_free14GiB',devices['returncode']==0 and any(row[0]=='0' and row[1]=='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0' and float(row[4])>=14*1024 for row in gpu_rows))
    listeners=[]
    for name in ('tcp','tcp6'):
        for line in (Path('/proc/net')/name).read_text().splitlines()[1:]:
            f=line.split()
            if int(f[1].rsplit(':',1)[1],16)==9999 and f[3]=='0A':listeners.append(dict(table=name,row=line))
    check('passive9999_no_listener',not listeners)
    blocked_names={'run_quality_campaign.py','run_frozen_sidecar.py','frozen_main.py','parallel_state_fill_trial.py',
      'smoke_agent_cuda_graphs.py','inference_worker_affinity.py','cpu_affinity_pilot.py','cpu_reservation_trial.py',
      'cuda_trace_parent.py','cuda_trace_worker.py','forensic_parent.py','forensic_worker.py','whole_agent_smoke.py',
      'whole_agent_smoke_worker.py','checkpoint_at_frame.py','verify_saved_checkpoint.py','audit_payloads.py',
      'restore_serial_after_parallel_trial.py','root_CPU_controller.py'}
    blocked=[];allmame=[];disappeared=0
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:words=[v.decode(errors='replace') for v in (p/'cmdline').read_bytes().split(b'\0') if v]
        except OSError as error:
            if error.errno in (errno.ENOENT,errno.ESRCH):disappeared+=1;continue
            raise
        if len(words)>1 and Path(words[0]).name=='mame' and words[1]=='robotron':allmame.append(int(p.name))
        if int(p.name)==os.getpid():continue
        if any(Path(word).name in blocked_names or Path(word).name.startswith('benchmark_') or word.rsplit('.',1)[-1]+'.py' in blocked_names
          or word.rsplit('.',1)[-1].startswith(('benchmark_','test_')) for word in words):
            blocked.append(dict(pid=int(p.name),cmdline=words,start_ticks=state(int(p.name))[1]))
    check('no_competing_helper_test_carrier_or_evaluator',not blocked)
    check('globalRobotronMAME_exact_original192',sorted(allmame)==sorted(row['pid'] for row in b['actors']))
    members=[int(v) for v in (Path('/sys/fs/cgroup')/b['fleet_cgroup'].lstrip('/')/'cgroup.procs').read_text().split()]
    check('fleet_cgroup_holds_all192_original_actors',all(pid in members for pid in allmame))
    shared=Path('/dev/shm');tmpfs=[str(p) for p in shared.iterdir() if p.is_dir() and p.name.startswith('robotron-snapshot-smoke-')]
    check('no_owned_private_tmpfs',not tmpfs)
    locks=[];lease=shared/'robotron-snapshot-smoke-gpu0.lock'
    if lease.exists():
        info=lease.stat();key='%02x:%02x:%d'%(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino)
        locks=[line for line in Path('/proc/locks').read_text().splitlines() if key in line.split()]
    check('no_recorded_GPU0_lease_lock',not locks)
    appcgroup=Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')
    privategroups=[]
    for group in appcgroup.iterdir():
        if group.name.startswith(('robotron-snapshot-smoke-','robotron-verify384-')) and group.is_dir():
            owned=[]
            for file in [group/'cgroup.procs',*group.rglob('*/cgroup.procs')]:
                owned.extend(int(v) for v in file.read_text().split())
            privategroups.append(dict(path=str(group),pids=sorted(set(owned))))
    check('no_private_diagnostic_or_CPU_cgroup_processes',not any(row['pids'] for row in privategroups))
    request=GAME/'models_dqn/managed_save.request.json';check('no_pending_model_save_request',not request.exists())
    remaining=5-(time.monotonic()-first_read['monotonic'])
    if remaining>0:time.sleep(remaining)
    final,last_read=api('api-final.json');firsthealth=api_health(first,pre);lasthealth=api_health(final,pre)
    for label,value in (('first',firsthealth),('final',lasthealth)):
        check(label+'_API192_held_recipe_finite_healthy',value['healthy'])
        check(label+'_graph_native_persistence_exposure',all(value[key] for key in ('graphs','native','persistence','exposure')) and not any(value['pipeline_errors'].values()))
    check('learner_and_training_clocks_advance',final['learner_frame_count']>first['learner_frame_count'] and final['training_steps']>first['training_steps'] and final['optimized_samples']>first['optimized_samples'])
    check('owned_main_inference_supervisor_ticks_held_at_end',state(3032848)[1]==28609635 and state(2258189)[1]==26614335 and int((tp/'stat').read_text().rsplit(')',1)[1].split()[19])==28613780)
    finalunit=command(['systemctl','--user','show',unitname]);write('original-private-terminal-full-show-recheck.json',finalunit)
    fu=dict(line.split('=',1) for line in finalunit['stdout'].splitlines() if '=' in line)
    check('same_retained_original_terminal_fields_held_at_end',finalunit['returncode']==0 and all(fu.get(k)==u.get(k) for k in ('InvocationID','MainPID','ExecMainPID','ExecMainCode','ExecMainStatus','Result','SubState')))
    write('main-inference-fleet192-owners.json',dict(trainer=trainer,inference=thread,supervisor=supervisor,actors=actors,fleet_members=members))
    receipt=dict(schema='robotron-recomputed-private-original-terminal-owned-cleanup-v1',status='OWNED_TERMINAL_CLEANUP_PASS' if all(CHECKS.values()) else 'AUDIT_NEEDS_REVIEW',
      observed_start_UTC=dt.datetime.fromtimestamp(start,dt.timezone.utc).isoformat(),observed_end_UTC=dt.datetime.now(dt.timezone.utc).isoformat(),checks=CHECKS,
      baseline_precommit=dict(path=str(PRE),sha256=sha(PRE)),units=units,source_hashes=sources,control_hashes=controls,selected_exec_environment_sha256=envsha,
      API_first=firsthealth,API_final=lasthealth,API_read_times=dict(first=first_read,last=last_read),
      learner_delta=final['learner_frame_count']-first['learner_frame_count'],training_step_delta=final['training_steps']-first['training_steps'],
      blocked_processes=blocked,unclassified_proc_disappearances=disappeared,passive9999=listeners,private_tmpfs=tmpfs,private_cgroups=privategroups,lease_locks=locks,
      artifacts=ARTIFACTS,collector_sha256=sha(__file__),
      limits=['Operational terminal/owned-cleanup only. Source-pinned JSON records declare one captured AMPskip and conditional CE comparison; no tensor/scientific revalidation or four-output parity/learning/adoption claim',
      'Source59 bindings use approved prior health source map with documented socket/journal/two-line fixture revisions; no main reload claim',
      'Leader/inference/192actor masks checked, not every trainer/newborn TID; exec-time environment not all later Python mutations',
      'No model/tensor/numerical import/test/default or helper invocation; no checkpoint/socket bind/probe/signals/services/source/state mutations',
      'Only readonly API HTTP and passive proc/net/nvidia-smi inventory; display use onGPU0 may remain',
      'Root original136170c1 terminal archive5f4021 bound; same live retained unit preserved before/after; no unit release/actions by this audit', 'Saved320 fixture STAT ONLY, no model/tensor bytes read; exact45 source pins and actual private source-copy bindings checked', 'Private parent and both original Popen child processes absent by PID/start identity; tmpfs and exact owned child cgroup removed, servicegroup empty, lease free', 'No full runtime log-history or scientific numeric audit; small closed root-archived JSON/log bytes only'])
    receipt['private_terminal_context']=dict(unit=unitname,invocation=invocation,original_ExecMainPID=3987420,original_start_ticks=31155810,original_ExecMainCode=u.get('ExecMainCode'),original_ExecMainStatus=u.get('ExecMainStatus'),root_archive_sha256=sha(archivepath),context_artifact='actual-owned-private-context-and-child-exits.json',unit_released_by_auditor=False)
    write('cleanup-readiness-receipt.json',receipt)
    fd=os.open(OUT,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    print(json.dumps(dict(status=receipt['status'],checks=len(CHECKS),failed=[k for k,v in CHECKS.items() if not v],
      learner_first=first['learner_frame_count'],learner_final=final['learner_frame_count'],learner_delta=receipt['learner_delta'],
      steps_delta=receipt['training_step_delta'],receipt=str(OUT/'cleanup-readiness-receipt.json'),sha256=sha(OUT/'cleanup-readiness-receipt.json')),indent=2))

if __name__=='__main__':main()
