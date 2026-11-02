"""Root-only fresh readonly runtime preparation; default PLAN has no reads.

Creates fresh observation files and a prospective case only. Never calls the
capture run(), publishes a model request, changes control, or starts a unit.
"""
import argparse, errno, hashlib, importlib.util, json, os, stat, sys, time
from pathlib import Path

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
SELECTOR=Path(__file__).with_name('capture_candidate.py')
QUERIES=RUN/'CE2048-trial02-first-LATCH-followup-readiness-collector-source-preparation-20261017/collect_readiness.py'
QUERY_SHA='9a8b4a20f090597f1ffad1a8c959c0cf886e3b119a17343857c7ce1d0f563f9b'
RECOVERY=('accepted-newgame-failed-maintenance-forward-recovery-20261017/result.json','28d6232fb7f1346dd55ac5aa92a8d590ffbbbdc6c0d6d4bfd5618419053e5c88')
RELEASE=('accepted-newgame-forward-recovery-parent-root-execution-20261017/root-original-result-and-owned-release.json','393eb75b2550891de755339fb7533725d83ed8fc61dc69245dbb19d572d0148d')
EXTRA_RELEASES=[
 ('accepted-newgame-failed-maintenance-newest-stopped-CPU-root-execution-20261017/root-original-newest-stopped-CPU-result-and-owned-release.json','3e90385ae2883edd5a8076b2463b56dadf145f7cced5c51095214ddc290c2b5b'),
 ('accepted-newgame-maintenance-failed-reconnect-root-evidence-20261017/root-original-failed-parent-archive-and-owned-release.json','0e2e1c683315080c6149250b74615bf20646defe795a57b96cc6e2e6044b0429'),
 ('accepted-newgame-forward-recovery-six-guards-root-execution-20261017/root-original-result-and-owned-release.json','cd2bab99d1a6ab0c484c9271ad0862c2cfb378268324f8c0a603fcfc4faedec9'),
 ('postaccepted-newgame-observer-six-guards-root-execution-20261017/root-original-result-and-owned-release.json','a898fc5b17d323f800930a5d0e0aa8e5512a7f3ee20246905ac144c14b3d61e9')]

def require(value,message):
    if not value:raise RuntimeError(message)

def load(path,sha,name):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Pinned source changed: '+str(path))
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module)
    require(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Source changed during import');return module

def prepare(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Builder source changed')
    C=load(SELECTOR,args.selector_sha256,'_fresh8M_case_selector')
    require(C.fingerprint(SELECTOR)[1]['identity']['mode']=='0o444','Selector must be sealed')
    M=load(QUERIES,QUERY_SHA,'_fresh8M_readonly_queries')
    modules={name:C.load(name) for name in C.DEPS};entry=modules['entry'];driver=modules['driver']
    ops=modules['ops'];capture=modules['capture'];observer=modules['observer'];files=capture.Files(ops)
    out=args.output;capture_out=RUN/'postaccepted-newgame-live8M-candidate-trial01-20261017'
    require(out.is_absolute() and out==out.resolve(strict=False) and out.parent==RUN and not out.exists()
        and not capture_out.exists(),'Both preparation and future capture outputs must be fresh direct run26 paths')
    out.mkdir(mode=0o700);ops.sync_directory(out.parent);obs=M.Observation(out)
    def fixed(value):
        path,digest=value;raw,pin=C.fingerprint(RUN/path);require(pin['sha256']==digest,'Fixed saved input changed')
        return pin,C.pinned(pin)
    recovery_pin,recovery=fixed(RECOVERY);release_pin,release=fixed(RELEASE)
    failed_job=C.pinned(C.pinned(recovery['root_job'])['failed_job'])
    freeze=failed_job['quality_release'];C.pinned(freeze)
    context=C.recovery_context(dict(recovery=dict(result=recovery_pin,release=release_pin),source_freeze_release=freeze),files)
    owner=context['owner'];binding=recovery['healthy192']['binding'];saved=binding['bindings']
    require(owner['pid']==2257565 and owner['starttime_ticks']==38102590 and
        owner['invocation_id']=='2cd616ad4ca9405c9584701229cfbf0a' and
        context['phase']['record']['sha256']=='cb904195a747ca5dc549a8db7d03ea11cebe6930d61bedde903cf907eb28dfcc',
        'Exact completed current recovery owner and phase required')
    main_show=obs.show(owner['unit']);fleet_unit=failed_job['transition']['fleet_unit'];fleet_show=obs.show(fleet_unit)
    fleet=dict(unit=fleet_unit,pid=int(fleet_show['MainPID']),starttime_ticks=saved.get('supervisor_start_ticks',binding['supervisor_start_ticks']),
        invocation_id=fleet_show['InvocationID'],cgroup=fleet_show['ControlGroup'])
    require(fleet['pid']==int(binding['fleet']['MainPID']) and fleet['cgroup']==saved['fleet_cgroup'],
        'Fresh fleet must be the actual saved original supervisor')
    for o,s in ((owner,main_show),(fleet,fleet_show)):
        require(s['MainPID']==str(o['pid']) and s['InvocationID']==o['invocation_id'] and s['ControlGroup']==o['cgroup'] and
            s['ActiveState']=='active' and s['SubState']=='running' and s['NRestarts']=='0','Current owner/fleet unit changed')
    require(main_show['Restart']=='no','Main restart policy changed')
    def descriptor(identity,mask,group):
        return dict(pid=identity['pid'],starttime_ticks=identity['starttime_ticks'],uid=identity['uid'],
            argv=identity['cmdline'],cwd=identity['cwd'],exe=identity['exe'],mask=mask,cgroup=group)
    mask=failed_job['transition']['worker_mask'];main=descriptor(saved['worker']['trainer'],mask,owner['cgroup'])
    M.process(obs,owner,owner['cgroup'],main)
    fleet_process=dict(pid=fleet['pid'],starttime_ticks=fleet['starttime_ticks'],uid=[os.getuid()]*4,
        argv=['bash',str(GAME/'startmame.sh'),'192','novideo','nonaudio','--supervise','--socket-address','dell:9998'],
        cwd=str(GAME),exe='/usr/bin/bash',mask=mask,cgroup=fleet['cgroup'])
    M.process(obs,fleet,fleet['cgroup'],fleet_process)
    actors=[];actor_resources=[]
    for a in saved['actors']:
        amask=failed_job['transition']['actor_masks'][str(a['pid'])]
        actors.append(dict(pid=a['pid'],starttime_ticks=a['starttime_ticks'],slot=a['client_slot'],mask=amask))
        expected=descriptor(a,amask,fleet['cgroup']);M.process(obs,a,fleet['cgroup'],expected);actor_resources.append(expected)
    require(len(actors)==192 and len({a['pid'] for a in actors})==192 and {a['slot'] for a in actors}==set(range(192)),
        'Exact original192 actors/slots required')
    worker=dict(saved['worker']['thread'],mask=mask)
    env=dict(os.fsdecode(x).split('=',1) for x in M.proc_bytes(Path('/proc',str(owner['pid']),'environ'),1<<20).split(b'\0')
        if b'=' in x and os.fsdecode(x).startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_')))
    require(env==binding['environment'],'Current selected environment changed from genuine READY')
    env_pin=obs.publish('actual-selected-environment.json',env)
    resources=dict(owner=owner,main=main,fleet=fleet_process,worker=worker,actors=actor_resources,main_unit=owner['unit'],fleet_unit=fleet_unit)
    resource_pin=obs.publish('actual-main192-resources.json',resources)
    fleet_pin=obs.publish('actual-fleet-descriptor.json',dict(owner=fleet,process=fleet_process))
    raw,api=driver.Driver.api(None);api_pin=obs.write('actual-main-API.raw.json',raw)
    require(all(api['host_pipeline']['learning_exposure'][kind]['process_id']==owner['pid'] for kind in ('optimizer','replay')),
        'Fresh API exposure must belong to actual current owner')
    unit_files={path:sha for group in binding['unit_files'].values() for path,sha in group.items()}
    baseline=dict(main_owner=owner,fleet_owner=fleet,inference_worker=worker,actors=actors,
        source_hashes=saved['source_hashes'],control_hashes=saved['control_hashes'],unit_files=unit_files,
        environment_sha256=hashlib.sha256(json.dumps(env,sort_keys=True).encode()).hexdigest(),status='PASS',
        schema='robotron-current-main192-runtime-baseline-v1',observed_unix_s=time.time(),actual_main192_resources=resource_pin,
        actual_API=api_pin,actual_selected_environment=env_pin,actual_fleet_descriptor=fleet_pin,actual_maintenance=recovery_pin,
        scope='Fresh current2257565 observation; original transition only supplies genuine held recipe/masks, never current owner authority')
    health=entry.EntryHealth(driver,ops,files,observer,baseline,owner,env,resources,context['historical_floor'])
    control_path=GAME/'models_dqn/learning_control.json';control_raw,control_pin=C.fingerprint(control_path);control=json.loads(control_raw)
    health.check_health(control['experiment'],2.5e-5)  # Parameterized actual process/source/control/unit/env/API/GPU/lease checks.
    blocked=set(M.BLOCKED)|{'capture_candidate.py','capture_entry.py','run_hot_window.py','run_forward_recovery.py',
        'run_healthy_ce_maintenance.py','verify_phase_snapshot_lr25.py','sequence_leg_audit.py','sequence_R1_audit.py'}
    competing=[];private=[];global_actors=set()
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal() or int(p.name)==os.getpid():continue
        try:argv=[os.fsdecode(x) for x in M.proc_bytes(p/'cmdline').split(b'\0') if x];group=M.proc_bytes(p/'cgroup').decode()
        except OSError as e:
            if e.errno in (errno.ENOENT,errno.ESRCH):continue
            raise
        if any(os.path.basename(a) in blocked for a in argv):competing.append(dict(pid=int(p.name),argv=argv))
        if 'robotron-snapshot-smoke-' in group or any('/dev/shm/robotron-snapshot-smoke-' in a for a in argv):private.append(int(p.name))
        if argv and os.path.basename(argv[0])=='mame' and 'robotron' in argv:global_actors.add(int(p.name))
    obs.publish('actual-global-process-scan.json',dict(competing=competing,private=private,robotron_actors=sorted(global_actors)))
    require(not competing and not private and global_actors=={a['pid'] for a in actors},'Helper/private/global actor inventory differs')
    app=(Path('/sys/fs/cgroup')/owner['cgroup'].lstrip('/')).parent
    groups=[M.cgroup_empty('/'+str(p.relative_to('/sys/fs/cgroup'))) for p in app.glob('robotron-snapshot-smoke-*')]
    release_pins=[];absences=[]
    extras=EXTRA_RELEASES+list(zip(args.extra_release,args.extra_release_sha256))
    require(len(args.extra_release)==len(args.extra_release_sha256),'Extra release path/SHA pairs required')
    for pair in [RELEASE]+extras:
        pin,value=fixed(pair);release_pins.append(pin)
        require(value['original_archived_before_release'] is True and len(value['owned_release'])==2,'Actual archived owned release required')
        for item in value['owned_release']:
            unit=item['unit'];require(unit.endswith(('.service','.timer')) and unit not in (owner['unit'],fleet_unit),'Invalid absence target')
            require(obs.show(unit)['LoadState']=='not-found','Owned helper unit reappeared')
            if unit.endswith('.service'):M.cgroup_empty(str(Path(owner['cgroup']).parent/unit))
        if 'original' in value:
            previous=value['original'];observed=M.process_start(previous['pid'])
            require(observed!=previous['starttime_ticks'],'Released original helper process remains')
            absences.append(dict(pid=previous['pid'],expected_start=previous['starttime_ticks'],observed_start=observed))
    obs.publish('actual-owned-release-and-cgroup-checks.json',dict(releases=release_pins,original_absences=absences,private_cgroups=groups))
    gpu=obs.call(['nvidia-smi','--query-gpu=index,uuid','--format=csv,noheader,nounits'])
    memory=obs.call(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'])
    require(gpu['returncode']==memory['returncode']==0,'GPU observation failed')
    require({int(a.strip()):b.strip() for a,b in (line.split(',') for line in gpu['stdout'].splitlines() if line.strip())}==M.GPU_UUIDS,'Actual GPU index/UUID map changed')
    free={a.strip():int(b.strip())*(1<<20) for a,b in (line.split(',') for line in memory['stdout'].splitlines() if line.strip())}
    _,fresh_api=health.check_health(control['experiment'],2.5e-5)
    require(all(fresh_api['host_pipeline']['learning_exposure'][kind]['process_id']==owner['pid'] for kind in ('optimizer','replay')),
        'Final API exposure owner changed')
    require(free[M.GPU_UUIDS[0]]>=14*(1<<30),'GPU0 memory below14GiB')
    latest=GAME/'models_dqn/robotron_dqn_latest.pt';latest_info=latest.lstat();latest_age=time.time()-latest_info.st_mtime
    require(stat.S_ISREG(latest_info.st_mode) and latest_info.st_uid==os.getuid() and 0<latest_info.st_size<=512<<20 and
        0<=latest_age<=600,'Actual latest autosave metadata not fresh')
    obs.publish('actual-latest-autosave-metadata.json',dict(path=str(latest),identity=M.identity(latest_info),age_s=latest_age,body_read_or_hash=False))
    completed_path=GAME/'models_dqn/managed_save.request.json.completed';_,completed=C.fingerprint(completed_path)
    baseline_pin=obs.publish('runtime-baseline.json',baseline)
    keys=('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')
    readiness=dict(schema='robotron-postaccepted-newgame-live8M-exclusive-readiness-v1',status='PASS',observed_unix_s=time.time(),
        **{k:baseline[k] for k in keys},resources=dict(GPU0_free_bytes=free[M.GPU_UUIDS[0]],GPU0_no_compute_owner=True,
        GPU1_main_only=True,port9999_clear=True,lease_free=True,no_competing_helpers=True,
        no_private_cgroup_tmpfs_processes=True,no_pending_save=True,owned_units_released=True),release_evidence=release_pins)
    ready_pin=obs.publish('runtime-readiness.json',readiness)
    case=dict(schema=C.SCHEMA,capture_authorized=True,recovery=dict(result=recovery_pin,release=release_pin),source_freeze_release=freeze,
        runtime_baseline=baseline_pin,readiness=ready_pin,control_before=control_pin,completed_slot=completed,
        tag='CE4096-accepted-newgame-fresh8M-trial01-20261017',window=dict(policy=dict(observer.POLICY,cutoff_s=3600),preparation_timeout_s=120),
        output_directory=str(capture_out),cpu_python=saved['worker']['trainer']['cmdline'][0])
    require(os.path.realpath(case['cpu_python'])==main['exe'],'Future CPU interpreter/executable identity differs')
    C.validate(case,capture_out,modules,files)  # Pure source/saved metadata validation; no request/window/CPU.
    case_pin=obs.publish('root-case.json',case)
    obs.publish('preparation-result.json',dict(status='PASS_FRESH_CURRENT_RUNTIME_AND_CASE',case=case_pin,selector=C.fingerprint(SELECTOR)[1],
        builder=C.fingerprint(Path(__file__).resolve())[1],capture_started=False,CPU_executed=False,control_changed=False,new_owner=None))
    print(json.dumps(dict(status='PASS',case=case_pin,capture_output=str(capture_out)),allow_nan=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--expected-source-sha256');p.add_argument('--selector-sha256');p.add_argument('--output',type=Path)
    p.add_argument('--extra-release',action='append',default=[]);p.add_argument('--extra-release-sha256',action='append',default=[])
    args=p.parse_args()
    if not args.execute:print('PLAN_ONLY: no reads/imports/runtime/case/capture/actions');return
    require(args.expected_source_sha256 and args.selector_sha256 and args.output,'Explicit pinned sources/new output required')
    prepare(args)

if __name__=='__main__':main()
