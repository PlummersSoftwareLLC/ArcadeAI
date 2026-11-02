"""Root-only fresh LR25 capture-case collection. Default PLAN reads nothing.

Only readonly runtime observations and new immutable metadata publication;
no control changes, requests, units, numerical CPU or capture/window actions.
"""
import argparse, copy, errno, hashlib, importlib.util, json, os, sys, time
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
P=R/'LR25-continuation-original01-root-preparation-20261018'
OUT=R/'LR25-continuation-fresh-preflight-runtime-original02-20261018'
CASE=P/'original01-capture-case.json'
CAPTURE_OUT=R/'LR25-continuation-capture-trial01-20261018'
FAMILY=G/'tools/live_lr_recipe_continuation_proposal'
CAPTURE_SHA='96f7035b30e827c1d16cedb9073a6c89d7ccee6dea1e95b9b1433d34529dfbae'
QUERIES=R/'CE2048-trial02-first-LATCH-followup-readiness-collector-source-preparation-20261017/collect_readiness.py'
QUERY_SHA='9a8b4a20f090597f1ffad1a8c959c0cf886e3b119a17343857c7ce1d0f563f9b'
OLD=R/'postdiagnostic-quality-runtime-payload-original01-20261018/runtime-baseline.json'
OLD_SHA='5f9bfb2be737f8df500d4d95f63745e67d112f2972f0c8346875298722faf58f'
ANCHOR=('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')
RELEASES=(
 ('postdiagnostic-quality-native-parent-owned-closure-root-20261018/root-original-native-parent-result-and-owned-release.json','6e0f9ce725e9e8a1e9006cdd7a615785a543bc5c9b3d43deac317489004723dd'),
 ('rejected-gap-none-ticket-full-handler-six-tests-original01-root-execution-20261018/root-original-result-and-owned-release.json','fa4408e15f9ee677a3c3dd53465f8770ed59705826389c8e1378127914cce35c'),
 ('LR25-continuation-22-metadata-guards-original01-root-execution-20261018/root-original-result-and-owned-release.json','f108e64585413ad36fd78623cd023339bbfa3beb366d30a290a2f03eef3d414b'),
 ('LR25-continuation-22-corrected-metadata-guards-original01-root-execution-20261018/root-original-result-and-owned-release.json','ce485ed9dd03a924fdf209d4537f7bb76715e38768aa2dd0fc373628ca964bb4'),
 ('rejected-gap-none-ticket-paced-original01-root-execution-20261018/root-original-result-and-owned-release.json','a9b85b266bc847a4c998e35a743fc99ac87e07c182ad70f4a5a60560656be6a9'))


def require(value,message):
    if not value:raise RuntimeError(message)


def load(path,sha,name):
    raw=path.read_bytes();require(hashlib.sha256(raw).hexdigest()==sha,'Source changed: '+str(path))
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module)
    require(path.read_bytes()==raw,'Source changed during load');return module


def collect(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Collector source changed')
    require(not OUT.exists() and not CASE.exists() and not CAPTURE_OUT.exists(),'Fresh observation/case/capture destinations required')
    C=load(FAMILY/'capture_candidate.py',CAPTURE_SHA,'_fresh_lr25_case_capture')
    M=load(QUERIES,QUERY_SHA,'_fresh_lr25_readonly_queries')
    modules={name:C.load(name) for name in ('entry','driver','ops','capture','observer','recipe')}
    entry,driver,ops,capture,observer=(modules[k] for k in ('entry','driver','ops','capture','observer'))
    observer.configure_recipe(modules['recipe']);files=capture.Files(ops)
    template=json.loads((FAMILY/'capture-case-TEMPLATE.json').read_bytes())
    context=C.activation_context(template,files);owner=context['owner']
    _,oldpin=C.fingerprint(OLD);require(oldpin['sha256']==OLD_SHA,'Historical descriptor baseline changed')
    old=C.pinned(oldpin);old_resources=C.pinned(old['actual_main192_resources']);old_env=C.pinned(old['actual_selected_environment'])
    require(old['main_owner']==owner and len(old)==16 and len(old['actors'])==192 and
        len(old['source_hashes'])==62 and len(old['control_hashes'])==2 and len(old['unit_files'])==3,
        'Historical descriptor authority differs')
    modules['recipe'].check_release(context['quality_release'],owner,old['actors'])
    old_api=json.loads(C.pinned(old['actual_API'],raw_only=True))
    floor={k:max(context['historical_floor'][k],capture.four(old_api)[k]) for k in C.CLOCKS}
    floor['learner_frame_count']=max(floor['learner_frame_count'],context['quality_release']['main_health']['learner_frame_count'])
    health=entry.EntryHealth(driver,ops,files,observer,old,owner,old_env,old_resources,floor)
    control_path=G/'models_dqn/learning_control.json';control_raw,control_pin=C.fingerprint(control_path)
    control=json.loads(control_raw)
    require(control['lr_scale']==.5 and control.get('measurement') is None,'Actual unchanged .5 control required')
    # Readonly concrete health validates all held sources/controls, owner, GPU,
    # lease/port and process identities before historical descriptors are used.
    raw,api=health.check_health(control['experiment'],2.5e-5)
    slot=G/'models_dqn/managed_save.request.json.completed'
    completed=files.fingerprint(slot,4<<20)
    entry.slot_guard(dict(completed_slot=completed),files)
    OUT.mkdir(mode=0o700);files.fsync_directory(OUT.parent);obs=M.Observation(OUT)
    initial_api=obs.write('actual-main-API-before.raw.json',raw)
    for who in (owner,old['fleet_owner']):
        show=obs.show(who['unit'])
        require(show['MainPID']==str(who['pid']) and show['InvocationID']==who['invocation_id'] and
            show['ControlGroup']==who['cgroup'] and show['ActiveState']=='active' and show['SubState']=='running' and
            show['NRestarts']=='0','Fresh original owner/fleet differs')
        if who==owner:require(show['Restart']=='no','Main restart policy differs')
    for who,descriptor in ((owner,old_resources['main']),(old['fleet_owner'],old_resources['fleet'])):
        M.process(obs,who,who['cgroup'],descriptor)
    by_pid={a['pid']:a for a in old['actors']}
    require(len(by_pid)==192 and {a['slot'] for a in old['actors']}==set(range(192)),'Original actor slots differ')
    for descriptor in old_resources['actors']:
        M.process(obs,by_pid[descriptor['pid']],old['fleet_owner']['cgroup'],descriptor)
    require(len(old_resources['actors'])==192 and {a['pid'] for a in old_resources['actors']}==set(by_pid),'Original resource actors differ')
    worker=old['inference_worker'];task=Path('/proc',str(owner['pid']),'task',str(worker['tid']))
    status=M.proc_bytes(task/'status').decode();stat_raw=M.proc_bytes(task/'stat').decode()
    parsed=dict(line.split(':',1) for line in status.splitlines() if ':' in line)
    require([int(x) for x in parsed['Uid'].split()]==[os.getuid()]*4 and
        int(stat_raw.rsplit(')',1)[1].split()[19])==worker['starttime_ticks'] and
        sorted(os.sched_getaffinity(worker['tid']))==worker['mask'],'Original inference thread identity/mask differs')
    obs.publish('actual-worker-status.json',dict(raw_status=status,raw_stat=stat_raw,expected=worker))
    env=dict(os.fsdecode(x).split('=',1) for x in M.proc_bytes(Path('/proc',str(owner['pid']),'environ'),1<<20).split(b'\0')
        if b'=' in x and os.fsdecode(x).startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_')))
    require(env==old_env and env['ROBOTRON_REJECTED_GAP_TELEMETRY']=='1','Fresh actual environment differs')
    env_pin=obs.publish('actual-selected-environment.json',env)
    held={**old['source_hashes'],**old['control_hashes'],**old['unit_files']};pins={}
    require(len(held)==67,'Exact62+2+3 held file closure required')
    for path,sha in held.items():
        _,actual=C.fingerprint(path);require(actual['sha256']==sha,'Held source/control/unit changed: '+path);pins[path]=actual
    obs.publish('actual-held-source-control-unit-67.json',pins)
    resource_pin=obs.publish('actual-main192-resources.json',old_resources)
    fleet_pin=obs.publish('actual-fleet-descriptor.json',dict(owner=old['fleet_owner'],process=old_resources['fleet']))
    blocked=set(M.BLOCKED)|{'capture_candidate.py','capture_entry.py','run_hot_window.py','run_forward_recovery.py',
        'run_healthy_ce_maintenance.py','run_healthy_activation.py','verify_recipe_phase_snapshot.py',
        'verify_phase_snapshot_lr25.py','sequence_leg_audit.py','sequence_R1_audit.py','benchmark_cost.py',
        'benchmark_cost_reviewed2.py','benchmark_callstyle.py','benchmark_callstyle_reviewed.py',
        'collect_quality_readiness.py','collect_quality_readiness_payload_metadata.py','root_quality_carrier_payload_metadata.py',
        'audit_completed_leg_payload_metadata.py'}
    competing=[];private=[];global_actors=set()
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal() or int(p.name)==os.getpid():continue
        try:argv=[os.fsdecode(x) for x in M.proc_bytes(p/'cmdline').split(b'\0') if x];group=M.proc_bytes(p/'cgroup').decode()
        except OSError as error:
            if error.errno in (errno.ENOENT,errno.ESRCH):continue
            raise
        if any(os.path.basename(a) in blocked for a in argv):competing.append(dict(pid=int(p.name),argv=argv))
        if 'robotron-snapshot-smoke-' in group or any('/dev/shm/robotron-snapshot-smoke-' in a for a in argv):private.append(int(p.name))
        if argv and os.path.basename(argv[0])=='mame' and 'robotron' in argv:global_actors.add(int(p.name))
    obs.publish('actual-global-process-scan.json',dict(competing=competing,private=private,robotron_actors=sorted(global_actors)))
    require(not competing and not private and global_actors==set(by_pid),'Competing/private/global MAME inventory differs')
    app=(Path('/sys/fs/cgroup')/owner['cgroup'].lstrip('/')).parent
    private_groups=[M.cgroup_empty('/'+str(p.relative_to('/sys/fs/cgroup'))) for p in app.glob('robotron-snapshot-smoke-*')]
    units=set();releases=[];absences=[]
    for relative,sha in RELEASES:
        _,rp=C.fingerprint(R/relative);require(rp['sha256']==sha,'Closed original release differs')
        value=C.pinned(rp);original=value['original']
        require(value['original_archived_before_release'] is True and value['unit_released'] is True and
            original['observed_live'] is True and type(original['pid']) is int and original['pid']>0 and
            type(original['starttime_ticks']) is int and original['starttime_ticks']>0 and
            original['timer']==original['unit'].removesuffix('.service')+'.timer' and
            [row['unit'] for row in value['owned_release']]==[original['timer'],original['unit']],
            'Exact archived original and timer-first owned pair required; failure outcomes remain unchanged')
        observed=M.process_start(original['pid']);require(observed!=original['starttime_ticks'],'Released original process remains')
        releases.append(rp);absences.append(dict(original=original,observed_start=observed))
        units.update((original['unit'],original['timer']))
    def check_absent():
        for unit in sorted(units):
            require(obs.show(unit)['LoadState']=='not-found','Owned original unit retained: '+unit)
            if unit.endswith('.service'):M.cgroup_empty(str(Path(owner['cgroup']).parent/unit))
    check_absent()
    obs.publish('actual-five-owned-releases.json',dict(releases=releases,original_absences=absences,private_cgroups=private_groups,units_not_found=sorted(units)))
    gpu=obs.call(['nvidia-smi','--query-gpu=index,uuid','--format=csv,noheader,nounits'])
    memory=obs.call(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'])
    require(gpu['returncode']==memory['returncode']==0,'GPU observations failed')
    require({int(a.strip()):b.strip() for a,b in (line.split(',') for line in gpu['stdout'].splitlines() if line.strip())}==M.GPU_UUIDS,'GPU UUID map differs')
    free={a.strip():int(b.strip())*(1<<20) for a,b in (line.split(',') for line in memory['stdout'].splitlines() if line.strip())}
    require(free[M.GPU_UUIDS[0]]>=14*(1<<30),'GPU0 free margin below14GiB')
    # Repeat concrete health after process/global/resource/absence observations.
    raw,api=health.check_health(control['experiment'],2.5e-5);entry.slot_guard(dict(completed_slot=completed),files);check_absent()
    require(all(api['host_pipeline']['learning_exposure'][kind]['process_id']==owner['pid'] for kind in ('optimizer','replay')) and
        api['ts']>=context['quality_release']['main_health']['ts'],'Final API owner/time predates genuine current release')
    final_api=obs.write('actual-main-API.raw.json',raw)
    baseline=copy.deepcopy(old);baseline.update(actual_API=final_api,observed_unix_s=time.time(),actual_selected_environment=env_pin,
        actual_main192_resources=resource_pin,actual_fleet_descriptor=fleet_pin)
    require(len(baseline)==16,'Exact baseline16 required')
    baseline_pin=obs.publish('runtime-baseline.json',baseline);anchor={k:baseline[k] for k in ANCHOR};obs.publish('runtime-anchor.json',anchor)
    ready=dict(schema='robotron-live-ce-lr-continuation-before-control-readiness-v1',status='PASS',observed_unix_s=time.time(),**anchor,
        resources=dict(gpu0_uuid=M.GPU_UUIDS[0],gpu1_uuid=M.GPU_UUIDS[1],GPU0_free_bytes=free[M.GPU_UUIDS[0]],
            GPU0_no_compute_owner=True,GPU1_main_only=True,port9999_clear=True,lease_free=True,no_competing_helpers=True,
            no_private_cgroup_tmpfs_processes=True,no_pending_save=True,owned_units_released=True),release_evidence=releases)
    ready_pin=obs.publish('runtime-readiness.json',ready)
    case=copy.deepcopy(template);case.update(capture_authorized=True,runtime_baseline=baseline_pin,readiness=ready_pin,
        control_before=control_pin,completed_slot=completed,experiment='CE4096-LR25-continuation-trial01-20261018',
        tags=dict(barrier='CE4096-LR25-barrier-trial01-20261018',endpoint='CE4096-LR25-first8M-trial01-20261018'),
        window=dict(policy=dict(observer.POLICY,cutoff_s=3600),preparation_timeout_s=180),
        output_directory=str(CAPTURE_OUT),cpu_python='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python')
    C.validate(case,CAPTURE_OUT,modules,files)
    case_pin=ops.publish(CASE,case)
    result=obs.publish('collection-result.json',dict(status='PASS_FRESH_CAPTURE_CASE_READONLY_ONLY',root_case=case_pin,
        baseline=baseline_pin,readiness=ready_pin,historical_descriptor_authority=oldpin,fresh_API=final_api,
        control_changed=False,request_started=False,CPU_executed=False,unit_actions=False,capture_started=False))
    print(json.dumps(dict(status='PASS',result=result,case=case_pin,baseline=baseline_pin,readiness=ready_pin),allow_nan=False))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--expected-source-sha256')
    args=parser.parse_args(argv)
    if not args.execute:print('PLAN_ONLY_NO_READS_OR_ACTIONS');return 0
    require(type(args.expected_source_sha256) is str and len(args.expected_source_sha256)==64,'Exact root-selected sealed source SHA required')
    collect(args);return 0


if __name__=='__main__':raise SystemExit(main())
