"""One current-campaign resource observation. No release or source/state writes."""
import argparse
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import urllib.request

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME/'logs/managed-learning-20261015/run-26'
INPUT_SHA = '42336c185c7156a037fe38757b1c36b2e97bd531db01a49531d893b51f6a1560'
MAX_FILE = 8 << 20
UID = 1001
GPU_UUIDS = {0:'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0',
             1:'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'}
BLOCKED = {'run_one_trial.py','deadline_guard.py','run_raw_kl_transition.py',
    'verify_phase_snapshot.py','verify_phase_snapshot_2048.py','verify_maintenance_checkpoint.py',
    'cuda_trace_parent.py','cuda_trace_worker.py','checkpoint_at_frame.py','whole_agent_smoke.py',
    'parallel_state_fill_trial.py','inference_worker_affinity.py','cpu_reservation_trial.py',
    'run_forward_ce_repair.py','run_frozen_sidecar.py','run_quality_campaign.py',
    'audit_completed_leg.py','capture_live_CE_candidate.py'}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def read_file(path, limit=MAX_FILE, allow_empty=False):
    p=Path(path)
    require(p.suffix != '.pt','Model bodies are outside this checker')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==UID and
            (0 if allow_empty else 1)<=before.st_size<=limit,'Unbounded/unowned file: '+str(p))
        with os.fdopen(fd,'rb',closefd=False) as f:
            raw=f.read(limit+1)
        require(len(raw)==before.st_size and identity(os.fstat(fd))==identity(before)==identity(p.lstat()),
            'File identity changed: '+str(p))
    finally:
        os.close(fd)
    return raw,dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))


def decode(raw):
    return json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))


class Observation:
    def __init__(self,out):
        self.out=out; self.commands=[]; self.pins=[]; self.counter=0

    def write(self,name,raw):
        require(len(raw)<=MAX_FILE,'Output archive exceeds bound')
        p=self.out/name
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:
            require(f.write(raw)==len(raw),'Short output write')
            f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        fd=os.open(self.out,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
        _,pin=read_file(p,allow_empty=True)
        return pin

    def publish(self,name,value):
        return self.write(name,(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode())

    def pinned(self,pin,raw_only=False):
        raw,actual=read_file(pin['path'],allow_empty=pin['bytes']==0)
        require(all(actual[k]==pin[k] for k in ('path','sha256','bytes')),'Saved digest differs: '+pin['path'])
        if 'identity' in pin:require(actual['identity']==pin['identity'],'Saved full identity differs: '+pin['path'])
        require(actual['identity']['mode']=='0o444' and actual['identity']['nlink']==1,
            'Saved input is not owned single-link0444: '+pin['path'])
        self.pins.append(actual)
        return raw if raw_only else decode(raw)

    def call(self,argv):
        # No shell; this is the complete allowlist of external read-only queries.
        require((len(argv)==5 and argv[:3]==['systemctl','--user','show'] and argv[-1]=='--all')
            or (len(argv)==3 and argv[0]=='nvidia-smi' and argv[1] in
                ('--query-gpu=index,uuid','--query-compute-apps=pid,gpu_uuid')
                and argv[2]=='--format=csv,noheader,nounits'),'Non-observation command refused')
        value=dict(argv=argv,started_unix_s=time.time(),timeout_s=10)
        try:
            r=subprocess.run(argv,capture_output=True,check=False,timeout=10)
            value.update(returncode=r.returncode,stdout=r.stdout.decode('utf-8','surrogateescape'),
                stderr=r.stderr.decode('utf-8','surrogateescape'),timed_out=False)
        except subprocess.TimeoutExpired as e:
            value.update(returncode=None,stdout=(e.stdout or b'').decode('utf-8','surrogateescape'),
                stderr=(e.stderr or b'').decode('utf-8','surrogateescape'),timed_out=True)
        value['ended_unix_s']=time.time()
        require(len(value['stdout'].encode('utf-8','surrogateescape'))<=MAX_FILE and
            len(value['stderr'].encode('utf-8','surrogateescape'))<=MAX_FILE,'Query output exceeds bound')
        pin=self.publish('%03d-command.json'%self.counter,value);self.counter+=1;self.commands.append(pin)
        require(not value['timed_out'],'Read-only query timed out: '+argv[0])
        return value

    def show(self,unit):
        raw=self.call(['systemctl','--user','show',unit,'--all'])
        fields=dict(line.split('=',1) for line in raw['stdout'].splitlines() if '=' in line)
        require(raw['returncode']==0 and 'LoadState' in fields,'Unit observation failed: '+unit)
        return fields


def process_start(pid):
    try:raw=Path('/proc',str(pid),'stat').read_text()
    except OSError as e:
        if e.errno in (errno.ENOENT,errno.ESRCH):return None
        raise
    return int(raw[raw.rfind(')')+2:].split()[19])


def process(owner,cgroup,mask=None,argv=None,cwd=None,exe=None):
    pid=owner['pid'];p=Path('/proc',str(pid));before=process_start(pid)
    require(before==owner['starttime_ticks'],'Original process changed: '+str(pid))
    status=dict(line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line)
    require([int(x) for x in status['Uid'].split()]==[UID]*4,'Process UID differs')
    actual_argv=[os.fsdecode(x) for x in (p/'cmdline').read_bytes().split(b'\0') if x]
    require(actual_argv and (argv is None or actual_argv==argv),'Process command differs: '+str(pid))
    require(cgroup in [line.split(':',2)[2] for line in (p/'cgroup').read_text().splitlines()],
        'Process cgroup differs: '+str(pid))
    if cwd is not None:require(os.readlink(p/'cwd')==cwd,'Process cwd differs')
    if exe is not None:require(os.readlink(p/'exe')==exe,'Process exe differs')
    actual_mask=sorted(os.sched_getaffinity(pid))
    if mask is not None:require(actual_mask==mask,'Process affinity differs: '+str(pid))
    require(process_start(pid)==before,'Process changed during inspection')
    return dict(pid=pid,starttime_ticks=before,uid=[UID]*4,argv=actual_argv,mask=actual_mask,cgroup=cgroup)


def cgroup_empty(group):
    root=Path('/sys/fs/cgroup')/group.lstrip('/')
    if not root.exists():return dict(cgroup=group,absent=True)
    paths=list(root.rglob('cgroup.procs'));require(len(paths)<=512,'Owned cgroup extent exceeds bound')
    require(all(not p.read_text().split() for p in paths),'Owned cgroup still populated: '+group)
    return dict(cgroup=group,absent=False,empty=True)


def retained_parent(fields,owner):
    require(fields.get('LoadState')!='not-found' and fields.get('MainPID')=='0'
        and fields.get('ExecMainPID')==str(owner['pid']) and fields.get('InvocationID')==owner['invocation_id']
        and fields.get('ExecMainCode')=='1' and fields.get('ExecMainStatus')=='0'
        and fields.get('Result')=='success' and fields.get('NRestarts')=='0'
        and fields.get('ControlGroup') in ('',owner['cgroup']),'Original retained parent terminal differs')


def parent_phase(obs,phase,owner,timer):
    service=obs.show(owner['unit']);clock=obs.show(timer['unit'])
    if phase=='before':
        retained_parent(service,owner)
        require(clock['LoadState']=='not-found' or clock.get('InvocationID')==timer['invocation_id'],
            'Original timer replaced')
    else:require(service['LoadState']==clock['LoadState']=='not-found','Exact parent/timer not released')


def release_units(obs,inputs):
    observations=[]
    for item in inputs['releases']:
        saved=obs.pinned(item['pin']);unit=item['service'];expected={unit,unit.removesuffix('.service')+'.timer'}
        if 'supplemental_original_pid' in saved:
            pid,inv,code,status=(saved[k] for k in ('supplemental_original_pid','supplemental_original_invocation',
                'supplemental_original_exec_code','supplemental_original_exit'))
        elif 'original_exec_main_code' in saved:
            pid,inv,code,status=(saved[k] for k in ('original_pid','invocation_id','original_exec_main_code','original_exec_main_status'))
        else:
            pid,inv,code,status=(saved[k] for k in ('original_pid','original_invocation','original_exec_code','original_exit'))
        require(pid==item['pid'] and inv==item['invocation_id'] and int(code)==1 and int(status)==item['exit_status'],
            'Genuine original helper identity/exit differs')
        if 'owned_release' in saved:
            entries=saved['owned_release'];require({x['unit'] for x in entries}==expected,'Owned release unit set differs')
            require(saved['original_archived_before_release'] is True and saved['unit_released'] is True,
                'Original archive/release predicate absent')
            require(all(x.get('final_LoadState')=='not-found' or x.get('already_absent') is True for x in entries),
                'Saved exact unit was not released')
        else:
            require(set(saved['after_release'])==expected,'Root after-release unit set differs')
            require(saved['original_terminal_archive']['path'].endswith('/root-original-terminal-archive.json'),
                'Original terminal archive missing')
            obs.pinned(saved['original_terminal_archive'])
            for unit_name,raw in saved['after_release'].items():
                require(raw['returncode']==0 and 'LoadState=not-found' in raw['stdout'].splitlines(),
                    'Saved unit absence differs: '+unit_name)
        for unit_name in sorted(expected):require(obs.show(unit_name)['LoadState']=='not-found','Owned helper unit remains')
        pid=item['pid'];tick=item['starttime_ticks'];actual=process_start(pid)
        # Unknown historical ticks stay unknown; require this PID itself absent.
        require(actual is None if tick is None else actual!=tick,'Original helper process remains')
        group='/user.slice/user-1001.slice/user@1001.service/app.slice/'+item['service']
        observations.append(dict(unit=item['service'],pid=pid,expected_start=tick,observed_start=actual,
            cgroup=cgroup_empty(group),release=item['pin']))
    return observations


def check(obs,phase,inputs):
    cfg=obs.pinned(inputs['binding']);plan=obs.pinned(inputs['plan']);inventory=obs.pinned(inputs['inventory'])
    archive=obs.pinned(inputs['parent_archive']);baseline=obs.pinned(cfg['runtime_baseline'])
    resources=obs.pinned(baseline['actual_main192_resources']);environment=obs.pinned(baseline['actual_selected_environment'])
    fleet_descriptor=obs.pinned(baseline['actual_fleet_descriptor'])
    before_API=json.loads(obs.pinned(baseline['actual_API'],raw_only=True))
    require(cfg['runtime_anchor']['main_owner']==baseline['main_owner']==resources['owner']==inputs['main_owner'],
        'Current main owner differs')
    require(all(baseline[k]==cfg['runtime_anchor'][k] for k in ('fleet_owner','inference_worker','actors',
        'source_hashes','control_hashes','unit_files','environment_sha256')),'Binding/baseline maps differ')
    require(len(baseline['actors'])==192 and len(baseline['source_hashes'])==61 and
        len(baseline['control_hashes'])==2 and len(baseline['unit_files'])==3,'Actual baseline closure size differs')
    require(len(plan['evaluator_source_hashes'])==12 and len(plan['execution_source_hashes'])==4,'Plan12+4 differs')
    require(archive['original_controller']=={k:inventory['original_controller'][k] for k in
        ('pid','starttime_ticks','invocation_id','cgroup')} and archive['original_exec_main_code']==1
        and archive['original_exec_main_status']==0 and archive['original_result']=='success'
        and archive['original_nrestarts']==archive['original_current_main_pid']==0,'Original parent archive differs')
    for section in archive['full_archives'].values():
        raw=obs.pinned(section['command']);plain=obs.pinned(section['plain'],raw_only=True)
        require(raw['returncode']==0 and raw['stdout'].encode('utf-8','surrogateescape')==plain,
            'Original full archive command/plain mismatch')
    parent=inventory['original_controller'];timer=inventory['original_timer'];parent_phase(obs,phase,parent,timer)
    originals=[dict(pid=parent['pid'],starttime_ticks=parent['starttime_ticks'])]
    for leg in inventory['legs']:originals.extend([leg['evaluator'],*leg['actors']])
    require(len(originals)==len({(x['pid'],x['starttime_ticks']) for x in originals})==69,'Original69 inventory differs')
    absent=[]
    for x in originals:
        actual=process_start(x['pid']);require(actual!=x['starttime_ticks'],'Original quality process remains')
        absent.append(dict(pid=x['pid'],expected_start=x['starttime_ticks'],observed_start=actual))
    parent_group=cgroup_empty(parent['cgroup']);helpers=release_units(obs,inputs)
    owner=baseline['main_owner'];fleet=baseline['fleet_owner'];worker=baseline['inference_worker']
    def unit_owner(o):
        s=obs.show(o['unit']);require(s.get('MainPID')==str(o['pid']) and s.get('InvocationID')==o['invocation_id']
            and s.get('ControlGroup')==o['cgroup'] and s.get('ActiveState')=='active' and s.get('SubState')=='running',
            'Current main/fleet unit identity differs')
        return s
    main_show=unit_owner(owner);unit_owner(fleet);require(main_show.get('Restart')=='no','Main Restart differs')
    main=process(owner,owner['cgroup'],resources['main_mask'],
        [str(GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','Scripts/run_dqn.py'],str(GAME))
    require(fleet_descriptor['owner']==fleet,'Fleet descriptor owner differs')
    fleet_actual=process(fleet,fleet['cgroup'],argv=fleet_descriptor['argv'],cwd=fleet_descriptor['cwd'],exe=fleet_descriptor['exe'])
    actors=[]
    for a in baseline['actors']:
        require(resources['actor_masks'][str(a['pid'])]==a['mask'],'Saved actor mask maps differ')
        p=process(a,fleet['cgroup'],a['mask'],cwd=str(GAME),exe='/usr/games/mame')
        require(p['argv'][0]=='/usr/games/mame' and 'robotron' in p['argv'],'Original actor command differs');actors.append(p)
    thread=Path('/proc',str(owner['pid']),'task',str(worker['tid']))
    require(thread.exists() and process_start(worker['tid'])==worker['starttime_ticks'] and
        sorted(os.sched_getaffinity(worker['tid']))==worker['mask']==resources['inference_mask'],
        'Inference thread identity/mask differs')
    selected=dict(os.fsdecode(x).split('=',1) for x in Path('/proc',str(owner['pid']),'environ').read_bytes().split(b'\0')
        if b'=' in x and os.fsdecode(x).startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_')))
    require(selected==environment,'Selected current environment differs')
    require(hashlib.sha256(json.dumps(selected,sort_keys=True).encode()).hexdigest()==baseline['environment_sha256'],
        'Baseline normalized environment SHA differs')
    hashes=dict(baseline['source_hashes']);hashes.update(baseline['control_hashes']);hashes.update(baseline['unit_files'])
    evaluator_resolution=[]
    for name,digest in plan['evaluator_source_hashes'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Evaluator key must be GAME relative')
        path=str(GAME/name);require(path not in hashes or hashes[path]==digest,'Evaluator/source overlap differs');hashes[path]=digest
        evaluator_resolution.append(dict(declared_key=name,resolved_path=path,sha256=digest))
    for path,digest in plan['execution_source_hashes'].items():
        require(Path(path).is_absolute(),'Execution source key must be absolute')
        require(path not in hashes or hashes[path]==digest,'Execution/source overlap differs');hashes[path]=digest
    checked=[]
    for path,digest in hashes.items():
        _,pin=read_file(path);require(pin['sha256']==digest,'Frozen source/control/unit changed: '+path);checked.append(pin)
    actor_pids=set();helper_processes=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal() or int(p.name)==os.getpid():continue
        try:argv=[os.fsdecode(x) for x in (p/'cmdline').read_bytes().split(b'\0') if x]
        except OSError as e:
            if e.errno in (errno.ENOENT,errno.ESRCH):continue
            raise
        if any(os.path.basename(x) in BLOCKED for x in argv):helper_processes.append(dict(pid=int(p.name),argv=argv))
        if argv and os.path.basename(argv[0])=='mame' and 'robotron' in argv:actor_pids.add(int(p.name))
    require(not helper_processes,'Private helper process remains')
    require(actor_pids=={x['pid'] for x in baseline['actors']},'Global Robotron actors differ from original192')
    private=[str(p) for p in Path('/dev/shm').glob('robotron-snapshot-smoke-*') if p.is_dir()]
    require(not private,'Private snapshot tmpfs directory remains')
    app=(Path('/sys/fs/cgroup')/owner['cgroup'].lstrip('/')).parent
    groups=[cgroup_empty('/'+str(p.relative_to('/sys/fs/cgroup'))) for p in app.glob('robotron-snapshot-smoke-*')]
    listeners=[]
    for table in ('tcp','tcp6'):
        for row in Path('/proc/net',table).read_text().splitlines()[1:]:
            parts=row.split()
            if parts[3]=='0A' and int(parts[1].rsplit(':',1)[1],16)==9999:listeners.append(row)
    require(not listeners,'Port9999 listener remains')
    lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');before=lease.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid==UID,'Lease file owner/type differs')
    fd=os.open(lease,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        require(identity(before)==identity(os.fstat(fd))==identity(lease.lstat()),'Lease identity raced')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(identity(before)==identity(os.fstat(fd))==identity(lease.lstat()),'Lease changed during probe')
    finally:os.close(fd)
    gpu=obs.call(['nvidia-smi','--query-gpu=index,uuid','--format=csv,noheader,nounits'])
    apps=obs.call(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'])
    require(gpu['returncode']==apps['returncode']==0,'GPU observation failed')
    mapping={int(a.strip()):b.strip() for a,b in (line.split(',') for line in gpu['stdout'].splitlines() if line.strip())}
    app_rows=[(int(a.strip()),b.strip()) for a,b in (line.split(',') for line in apps['stdout'].splitlines() if line.strip())]
    require(mapping==GPU_UUIDS and app_rows==[(owner['pid'],GPU_UUIDS[1])],'GPU0 busy or main not sole GPU1 app')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as response:raw=response.read((2<<20)+1)
    require(0<len(raw)<=2<<20,'API response exceeds bound');raw_pin=obs.write('raw-main-API.json',raw)
    api=json.loads(raw);pipeline=api['host_pipeline'];graphs=pipeline['inference_graphs'];age=time.time()-float(api['ts'])
    require(math.isfinite(age) and 0<=age<=5 and api['client_count']==192 and api['training_enabled'] is True,
        'API main192/freshness differs')
    require(pipeline['learning_exposure']['optimizer']['process_id']==owner['pid'] and
        pipeline['learning_exposure']['replay']['process_id']==owner['pid'],'API process owner differs')
    require(all(type(api[k]) is int and api[k]>=before_API[k] for k in
        ('training_steps','optimized_samples','learner_frame_count','frame_count')),'API four clocks regressed/unavailable')
    require(graphs['ready'] is True and graphs['capture_count']==128 and graphs['validation_replay_count']==640
        and graphs['postload_validations']>=1 and graphs['runtime_capture_count']==graphs['fallback_count']==0
        and graphs['fatal_error'] is None and all(pipeline[k]['errors']==0 for k in
            ('inference','actor_refresh','target_refresh','learner_priority')),'API graphs or four error counters differ')
    latest=GAME/'models_dqn/robotron_dqn_latest.pt';latest_stat=latest.lstat();latest_age=time.time()-latest_stat.st_mtime
    require(stat.S_ISREG(latest_stat.st_mode) and latest_stat.st_uid==UID and 0<latest_stat.st_size<=512<<20
        and math.isfinite(latest_age) and 0<=latest_age<=600,'Latest model autosave metadata is not fresh')
    unit_owner(owner);unit_owner(fleet);require(process_start(owner['pid'])==owner['starttime_ticks'] and
        process_start(fleet['pid'])==fleet['starttime_ticks'] and process_start(worker['tid'])==worker['starttime_ticks'],
        'Current owner changed at final bracket')
    parent_phase(obs,phase,parent,timer)
    return dict(original69_absence=absent,original_cgroup=parent_group,helper_releases=helpers,
        main=main,fleet=fleet_actual,actors=actors,inference_worker=worker,selected_environment=selected,
        checked_source_control_unit_pins=checked,evaluator_source_declared_and_resolved=evaluator_resolution,
        GPU0_free=True,main_sole_GPU1=True,lease_unheld=True,
        lease_identity=identity(before),port9999_unused=True,no_private_tmpfs_or_helpers=True,private_cgroups=groups,
        raw_API=raw_pin,API_summary=dict(ts=api['ts'],age_s=age,client_count=192,training_enabled=True,
            learner_frame_count=api['learner_frame_count'],frame_count=api['frame_count'],optimized_samples=api['optimized_samples'],
            graphs_ready=True,capture_count=128,validation_replay_count=640,four_pipeline_errors=0),
        latest_autosave_metadata=dict(path=str(latest),identity=identity(latest_stat),age_s=latest_age,max_age_s=600,
            body_read_or_hash=False))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('before','after'));parser.add_argument('--output',type=Path)
    parser.add_argument('--expected-source-sha256');args=parser.parse_args(argv)
    if args.phase is None and args.output is None:
        print('PLAN_ONLY: no reads, queries, locks or output; root must select phase/output/source SHA');return 0
    require(args.phase is not None and args.output is not None,'Both --phase and --output are required')
    out=args.output
    require(out.is_absolute() and out.parent==RUN and not out.exists() and not out.is_symlink(),
        'Fresh direct-run26 output required')
    # Output is the sole durable mutation; even input/query failures retain their first error.
    out.mkdir(mode=0o700)
    fd=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    obs=Observation(out);result=dict(status='FAILED_RESOURCE_OBSERVATION',phase=args.phase,
        started_unix_s=time.time(),resource_pass=False,acceptance=False,source_freeze_released=False,release_actions=False)
    try:
        _,source=read_file(__file__);require(source['sha256']==args.expected_source_sha256,'Explicit checker source SHA differs')
        raw,pin=read_file(Path(__file__).with_name('inputs.json'))
        require(pin['sha256']==INPUT_SHA and pin['identity']['mode']=='0o444','Selected input source differs')
        inputs=decode(raw);result['checker_source']=source;result['inputs_source']=pin
        result['observations']=check(obs,args.phase,inputs)
        result.update(status='PASS_CURRENT_CAMPAIGN_RESOURCE_OBSERVATION',resource_pass=True)
    except BaseException as e:
        result['first_error']=dict(type=type(e).__name__,message=str(e))
    result.update(ended_unix_s=time.time(),raw_command_metadata=obs.commands,saved_input_pins=obs.pins)
    obs.publish('resource-observation.json',result)
    print(json.dumps(dict(status=result['status'],resource_pass=result['resource_pass'],output=str(out)),allow_nan=False))
    return 0 if result['resource_pass'] else 2


if __name__=='__main__':
    raise SystemExit(main())
