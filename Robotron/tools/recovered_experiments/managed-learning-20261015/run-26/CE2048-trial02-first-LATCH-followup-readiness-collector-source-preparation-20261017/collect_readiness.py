"""Fresh first-LATCH follow-up readiness. Read-only queries; new output only; no project imports."""
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
SCHEMA = 'robotron-CE2048-trial02-first-LATCH-policy-followup-exclusive-readiness-v1'
CASE_SCHEMA = 'robotron-first-LATCH-followup-readiness-case-v1'
BINDING_SCHEMA = 'robotron-CE2048-trial02-first-LATCH-policy-followup-quality-bindings-v1'
MAX_FILE = 8 << 20
UID = 1001
GPU_UUIDS = {0:'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0',
             1:'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'}
BLOCKED = {'run_one_trial.py','deadline_guard.py','run_raw_kl_transition.py',
    'verify_phase_snapshot.py','verify_phase_snapshot_2048.py','verify_maintenance_checkpoint.py',
    'cuda_trace_parent.py','cuda_trace_worker.py','checkpoint_at_frame.py','whole_agent_smoke.py',
    'parallel_state_fill_trial.py','inference_worker_affinity.py','cpu_reservation_trial.py',
    'run_forward_ce_repair.py','run_frozen_sidecar.py','run_quality_campaign.py',
    'audit_completed_leg.py','capture_live_CE_candidate.py','root_quality_carrier.py'}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def read_file(path, limit=MAX_FILE, allow_empty=False):
    p=Path(path)
    require(p.is_absolute() and p == p.resolve(strict=True) and p.suffix not in ('.pt','.pth','.npy','.npz'),
        'Only canonical source/metadata files; no model/tensor bodies')
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
        self.out=out; self.commands=[]; self.pins=[]; self.counter=0; self.bytes_written=0

    def write(self,name,raw):
        require(len(raw)<=MAX_FILE and self.bytes_written+len(raw)<=32<<20,'Output archive/budget exceeds bound')
        self.bytes_written+=len(raw)
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
                ('--query-gpu=index,uuid','--query-gpu=uuid,memory.free','--query-compute-apps=pid,gpu_uuid')
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


def proc_bytes(path,limit=65536):
    with open(path,'rb') as f:raw=f.read(limit+1)
    require(len(raw)<=limit,'Process metadata exceeds bound: '+str(path))
    return raw


def process(obs,owner,cgroup,expected):
    pid=owner['pid'];p=Path('/proc',str(pid));before=process_start(pid)
    require(before==owner['starttime_ticks'],'Original process changed: '+str(pid))
    raw_stat=proc_bytes(p/'stat').decode();raw_status=proc_bytes(p/'status').decode()
    raw_cgroup=proc_bytes(p/'cgroup').decode();raw_cmdline=proc_bytes(p/'cmdline')
    actual_argv=[os.fsdecode(x) for x in raw_cmdline.split(b'\0') if x]
    status=dict(line.split(':',1) for line in raw_status.splitlines() if ':' in line)
    actual=dict(pid=pid,starttime_ticks=before,uid=[int(x) for x in status['Uid'].split()],
        argv=actual_argv,cwd=os.readlink(p/'cwd'),exe=os.readlink(p/'exe'),
        mask=sorted(os.sched_getaffinity(pid)),cgroup=cgroup)
    raw_pin=obs.publish('process-%s.json'%pid,dict(raw_stat=raw_stat,raw_status=raw_status,
        raw_cgroup=raw_cgroup,cmdline_hex=raw_cmdline.hex(),selected=actual))
    require(actual['uid']==[UID]*4 and actual_argv and
        all(actual[k]==expected[k] for k in ('pid','starttime_ticks','uid','argv','cwd','exe','mask','cgroup')),
        'Exact process command/UID/cwd/exe/mask differs: '+str(pid))
    require(cgroup in [line.split(':',2)[2] for line in raw_cgroup.splitlines()],
        'Process cgroup differs: '+str(pid))
    require(process_start(pid)==before,'Process changed during inspection')
    return dict(**actual,raw=raw_pin)


def cgroup_empty(group):
    root=Path('/sys/fs/cgroup')/group.lstrip('/')
    if not root.exists():return dict(cgroup=group,absent=True)
    paths=list(root.rglob('cgroup.procs'));require(len(paths)<=512,'Owned cgroup extent exceeds bound')
    require(all(not p.read_text().split() for p in paths),'Owned cgroup still populated: '+group)
    return dict(cgroup=group,absent=False,empty=True)



def unit_name(value):
    require(type(value) is str and re.fullmatch(r'robotron-[A-Za-z0-9_.@-]+\.(service|timer)',value),
        'Explicit exact robotron service/timer required')
    return value


def pin_key(pin):
    return {k:pin[k] for k in ('path','sha256','bytes')}


def known_units(obs,cfg,case):
    evidence=cfg['evidence'];failed=obs.pinned(evidence['failed_trial_closure'])
    require(failed['owned_cleanup_complete'] is True and failed['original_trial_status']=='FAILED'
        and failed['actual_trial_retried'] is False and failed['original_executions']==cfg['original_executions'],
        'Genuine failed-trial closure differs')
    units=set();owners=[]
    for item in cfg['original_executions'].values():
        require(item['archived_before_release'] is True and item['released'] is True,'Original unit was not archived/released')
        owners.append(item['owner']);units.update((item['owner']['unit'],item['timer']['unit']))
    require({x['unit'] for x in failed['owned_release']}==units and
        all(x['final_load_state']=='not-found' for x in failed['owned_release']),
        'Actual failed-trial released unit set differs')
    early=obs.pinned(evidence['early_phase_insurance']);provenance=early['cpu_provenance']
    intent=obs.pinned(provenance['successful_execution']);completion=obs.pinned(provenance['successful_completion'])
    release=obs.pinned(provenance['successful_result'])
    require(intent['kind']=='phase_early_insurance2048' and release['status']=='PASS'
        and release['original_archived_before_release'] is True and release['original_exit']==0
        and release['original_owner']==completion['original_owner']
        and pin_key(release['original_completion'])==pin_key(provenance['successful_completion']),
        'Actual early phase CPU archive/release differs')
    require({x['unit'] for x in release['releases']}=={intent['unit'],intent['timer']} and
        all(x['final_load_state']=='not-found' for x in release['releases']),
        'Early CPU exact released units differ')
    owners.append(completion['original_owner']);units.update((intent['unit'],intent['timer']))
    maintenance=obs.pinned(evidence['maintenance_result']);closure=obs.pinned(evidence['maintenance_closure'])
    release=obs.pinned(evidence['maintenance_release']);archive=obs.pinned(closure['original_terminal_archive'])
    require(maintenance['status']=='READY_CE_FORWARD_REPAIR' and
        closure['actual_current_owner']==maintenance['owner']==cfg['runtime_anchor']['main_owner']
        and pin_key(closure['actual_result'])==pin_key(evidence['maintenance_result'])
        and closure['original_archived_before_release'] is True and closure['owned_cleanup_complete'] is True
        and closure['unit_released'] is True and closure['original_exit']==0
        and release['source_freeze_released'] is True and
        pin_key(release['actual_maintenance_closure'])==pin_key(evidence['maintenance_closure']),
        'Separate maintenance release/current owner differs')
    original=archive['original'];service=unit_name(original['unit']);timer=unit_name(original['timer'])
    require({x['unit'] for x in closure['owned_release']}=={service,timer} and
        all(x['final_load_state']=='not-found' for x in closure['owned_release']),
        'Exact maintenance unit release differs')
    owners.append(dict(pid=original['pid'],starttime_ticks=original['starttime_ticks'],
        cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/'+service))
    units.update((service,timer))
    extra=case['extra_owned_units']
    require(type(extra) is list and 0<len(extra)<=64 and len(set(extra))==len(extra),
        'Root must supply exact fresh CPU/metadata-guard service+timer units')
    for value in extra:
        value=unit_name(value);other=value.removesuffix('.service')+'.timer' if value.endswith('.service') else value.removesuffix('.timer')+'.service'
        require(other in extra,'Each extra root unit requires its exact service/timer pair')
        units.add(value)
    require(type(case['extra_release_evidence']) is list and 0<len(case['extra_release_evidence'])<=32,
        'Actual root extra-unit archive/release evidence required')
    for pin in case['extra_release_evidence']:obs.pinned(pin)
    campaign=cfg['campaign']['unit'];require('.' not in campaign and unit_name(campaign+'.service'),'Campaign unit basename differs')
    units.update((campaign+'.service',campaign+'.timer'))
    require(not units.intersection((cfg['runtime_anchor']['main_owner']['unit'],cfg['runtime_anchor']['fleet_owner']['unit'])),
        'Current main/fleet is not a releasable unit')
    return sorted(units),owners,maintenance


def absent_units(obs,units):
    result=[]
    for unit in units:
        show=obs.show(unit);require(show['LoadState']=='not-found','Owned/new-campaign unit is present: '+unit)
        group='/user.slice/user-1001.slice/user@1001.service/app.slice/'+unit
        result.append(dict(unit=unit,show=show,cgroup=cgroup_empty(group)))
    return result


def check(obs,case):
    require(case['schema']==CASE_SCHEMA and set(case)=={'schema','binding','plan','extra_owned_units','extra_release_evidence'},
        'Exact root readiness case fields required')
    cfg=obs.pinned(case['binding']);plan=obs.pinned(case['plan']);baseline=obs.pinned(cfg['runtime_baseline'])
    require(cfg['schema']==BINDING_SCHEMA and baseline['status']=='PASS','Selected follow-up binding/baseline schema differs')
    anchor=cfg['runtime_anchor'];keys=('main_owner','fleet_owner','inference_worker','actors',
        'source_hashes','control_hashes','unit_files','environment_sha256')
    require(all(baseline[k]==anchor[k] for k in keys),'Binding/baseline exact maps differ')
    require(len(baseline['actors'])==192 and len(baseline['source_hashes'])==61 and
        len(baseline['control_hashes'])==2 and len(baseline['unit_files'])==3,'Current held closure size differs')
    require(plan['output_directory']==cfg['campaign']['output_directory'] and
        all(plan['checkpoints'][role]['source']==cfg[role]['path'] and
            plan['checkpoints'][role]['sha256']==cfg[role]['sha256'] for role in ('reference','candidate')),
        'Actual reviewed plan source/checkpoint binding differs')
    require(len(plan['evaluator_source_hashes'])==12 and len(plan['execution_source_hashes'])==4,'Actual plan12+4 source closure differs')
    units,old_owners,maintenance=known_units(obs,cfg,case);first_units=absent_units(obs,units)
    old_absence=[]
    for owner in old_owners:
        actual=process_start(owner['pid']);require(actual!=owner['starttime_ticks'],'Original helper owner remains')
        old_absence.append(dict(owner=owner,observed_start=actual))
    resources=obs.pinned(baseline['actual_main192_resources']);environment=obs.pinned(baseline['actual_selected_environment'])
    fleet_descriptor=obs.pinned(baseline['actual_fleet_descriptor']);before_API=json.loads(obs.pinned(baseline['actual_API'],raw_only=True))
    require(resources['owner']==baseline['main_owner'] and resources['worker']==baseline['inference_worker']
        and fleet_descriptor['owner']==baseline['fleet_owner'] and fleet_descriptor['process']==resources['fleet'],
        'Saved exact process/worker/fleet witnesses differ')
    owner=baseline['main_owner'];fleet=baseline['fleet_owner'];worker=baseline['inference_worker']
    def unit_owner(o):
        s=obs.show(o['unit']);require(s.get('MainPID')==str(o['pid']) and s.get('InvocationID')==o['invocation_id']
            and s.get('ControlGroup')==o['cgroup'] and s.get('ActiveState')=='active' and s.get('SubState')=='running'
            and s.get('NRestarts')=='0','Current main/fleet unit identity differs')
        return s
    main_show=unit_owner(owner);fleet_show=unit_owner(fleet);require(main_show.get('Restart')=='no','Main Restart differs')
    main=process(obs,owner,owner['cgroup'],resources['main'])
    actual_fleet=process(obs,fleet,fleet['cgroup'],resources['fleet'])
    saved_actors={x['pid']:x for x in resources['actors']};require(len(saved_actors)==192,'Saved actual actor set differs')
    actors=[]
    for actor in baseline['actors']:
        expected=saved_actors[actor['pid']]
        require(all(expected[k]==actor[k] for k in ('pid','starttime_ticks','mask')),'Baseline/process actor identity differs')
        actors.append(process(obs,actor,fleet['cgroup'],expected))
    require(set(saved_actors)=={x['pid'] for x in baseline['actors']} and
        {x['slot'] for x in baseline['actors']}==set(range(192)),'Original192 actor slot/PID set differs')
    thread=Path('/proc',str(owner['pid']),'task',str(worker['tid']))
    raw_thread=dict(stat=proc_bytes(thread/'stat').decode(),status=proc_bytes(thread/'status').decode(),
        cgroup=proc_bytes(thread/'cgroup').decode(),mask=sorted(os.sched_getaffinity(worker['tid'])))
    worker_pin=obs.publish('inference-worker.json',raw_thread)
    thread_status=dict(line.split(':',1) for line in raw_thread['status'].splitlines() if ':' in line)
    require([int(x) for x in thread_status['Uid'].split()]==[UID]*4,'Inference thread UID differs')
    require(thread.exists() and process_start(worker['tid'])==worker['starttime_ticks'] and
        raw_thread['mask']==worker['mask'] and owner['cgroup'] in
        [line.split(':',2)[2] for line in raw_thread['cgroup'].splitlines()],
        'Inference thread identity/mask/cgroup differs')
    selected=dict(os.fsdecode(x).split('=',1) for x in proc_bytes(Path('/proc',str(owner['pid']),'environ'),1<<20).split(b'\0')
        if b'=' in x and os.fsdecode(x).startswith(('DQN_','ROBOTRON_','CUDA_','TORCHINDUCTOR_')))
    selected_pin=obs.publish('selected-environment.json',selected)
    phase=maintenance['startup']['phase']
    require(selected==environment and hashlib.sha256(json.dumps(selected,sort_keys=True).encode()).hexdigest()==baseline['environment_sha256']
        and selected.get('DQN_BATCH_SIZE')=='4096' and selected.get('DQN_PER_PRIORITY_METRIC')=='ce'
        and selected.get('DQN_PRIORITY_PHASE_RECORD')==phase['record']['path']
        and selected.get('DQN_PRIORITY_PHASE_RECORD_SHA256')==phase['record']['sha256'],
        'Exact current maintenance CE4096 environment differs')
    obs.pinned(baseline['actual_maintenance'])
    require(pin_key(baseline['actual_maintenance'])==pin_key(cfg['evidence']['maintenance_result']),
        'Baseline genuine maintenance witness differs')
    predecessor=obs.pinned(cfg['predecessor_quality_plan'])
    require(plan['evaluator_source_hashes']==predecessor['evaluator_source_hashes'] and
        plan['execution_source_hashes']==predecessor['execution_source_hashes'],'Unchanged evaluation12+execution4 closure differs')
    hashes={};resolution=[]
    for name in ('source_hashes','control_hashes','unit_files'):
        for path,digest in baseline[name].items():
            require(Path(path).is_absolute() and (path not in hashes or hashes[path]==digest),'Absolute held source mapping differs')
            hashes[path]=digest
    for name,digest in plan['evaluator_source_hashes'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Evaluator key must be GAME relative')
        path=str(GAME/name);require(path not in hashes or hashes[path]==digest,'Evaluator source overlap differs')
        hashes[path]=digest;resolution.append(dict(declared_key=name,resolved_path=path,sha256=digest))
    for path,digest in plan['execution_source_hashes'].items():
        require(Path(path).is_absolute() and (path not in hashes or hashes[path]==digest),'Absolute execution mapping differs')
        hashes[path]=digest
    checked=[]
    for path,digest in hashes.items():
        _,pin=read_file(path);require(pin['sha256']==digest,'Held source/control/unit file changed: '+path);checked.append(pin)
    helper_processes=[];actor_pids=set();private_processes=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal() or int(p.name)==os.getpid():continue
        try:
            argv=[os.fsdecode(x) for x in proc_bytes(p/'cmdline').split(b'\0') if x]
            groups=proc_bytes(p/'cgroup').decode()
        except OSError as e:
            if e.errno in (errno.ENOENT,errno.ESRCH):continue
            raise
        if any(os.path.basename(x) in BLOCKED for x in argv):helper_processes.append(dict(pid=int(p.name),argv=argv))
        if any('/dev/shm/robotron-snapshot-smoke-' in x for x in argv) or 'robotron-snapshot-smoke-' in groups:
            private_processes.append(dict(pid=int(p.name),argv=argv,cgroup=groups))
        if argv and os.path.basename(argv[0])=='mame' and 'robotron' in argv:actor_pids.add(int(p.name))
    scan_pin=obs.publish('global-process-scan.json',dict(competing_helpers=helper_processes,private_processes=private_processes,
        robotron_actor_pids=sorted(actor_pids)))
    require(not helper_processes and not private_processes,'Competing/private helper process remains')
    require(actor_pids==set(saved_actors),'Global Robotron actor set differs from original192')
    private=[str(p) for p in Path('/dev/shm').glob('robotron-snapshot-smoke-*') if p.is_dir()]
    require(not private,'Private snapshot tmpfs directory remains')
    app=(Path('/sys/fs/cgroup')/owner['cgroup'].lstrip('/')).parent
    groups=[cgroup_empty('/'+str(p.relative_to('/sys/fs/cgroup'))) for p in app.glob('robotron-snapshot-smoke-*')]
    listeners=[];tcp_raw={}
    for table in ('tcp','tcp6'):
        raw=proc_bytes(Path('/proc/net',table),1<<20).decode();tcp_raw[table]=raw
        for row in raw.splitlines()[1:]:
            parts=row.split()
            if parts[3]=='0A' and int(parts[1].rsplit(':',1)[1],16)==9999:listeners.append(row)
    tcp_pin=obs.publish('port9999-tables.json',tcp_raw);require(not listeners,'Port9999 listener remains')
    lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');before=lease.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid==UID,'Existing lease file owner/type differs')
    fd=os.open(lease,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        require(identity(before)==identity(os.fstat(fd))==identity(lease.lstat()),'Lease identity raced')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(identity(before)==identity(os.fstat(fd))==identity(lease.lstat()),'Lease changed during readonly probe')
        fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    require(not os.path.lexists(GAME/'models_dqn/managed_save.request.json'),'Managed save request pending')
    gpu=obs.call(['nvidia-smi','--query-gpu=index,uuid','--format=csv,noheader,nounits'])
    apps=obs.call(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'])
    memory=obs.call(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'])
    require(gpu['returncode']==apps['returncode']==memory['returncode']==0,'GPU observation failed')
    mapping={int(a.strip()):b.strip() for a,b in (line.split(',') for line in gpu['stdout'].splitlines() if line.strip())}
    app_rows=[(int(a.strip()),b.strip()) for a,b in (line.split(',') for line in apps['stdout'].splitlines() if line.strip())]
    free={a.strip():int(b.strip())*(1<<20) for a,b in (line.split(',') for line in memory['stdout'].splitlines() if line.strip())}
    require(mapping==GPU_UUIDS and app_rows==[(owner['pid'],GPU_UUIDS[1])] and free[GPU_UUIDS[0]]>=14*(1<<30),
        'GPU0 ownership/free margin or sole main GPU1 owner differs')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as response:raw=response.read((2<<20)+1)
    require(0<len(raw)<=2<<20,'API response exceeds bound');raw_pin=obs.write('raw-main-API.json',raw)
    api=json.loads(raw);pipeline=api['host_pipeline'];graphs=pipeline['inference_graphs'];age=time.time()-float(api['ts'])
    require(math.isfinite(age) and 0<=age<=5 and api['client_count']==192 and api['training_enabled'] is True
        and api['measurement_active'] is False and api['managed_experiment']==cfg['experiment'],'Fresh held API main192 branch differs')
    require(all(pipeline['learning_exposure'][kind]['process_id']==owner['pid'] for kind in ('optimizer','replay')),
        'API process owner differs')
    require(all(type(api[k]) is int and api[k]>=before_API[k] for k in
        ('training_steps','optimized_samples','learner_frame_count','frame_count')),'API four clocks regressed/unavailable')
    require(graphs['ready'] is True and graphs['capture_count']==128 and graphs['validation_replay_count']==640
        and graphs['postload_validations']>=1 and graphs['runtime_capture_count']==graphs['fallback_count']==0
        and graphs['fatal_error'] is None and all(pipeline[k]['errors']==0 for k in
        ('inference','actor_refresh','target_refresh','learner_priority')),'API graphs/four errors differ')
    latest=GAME/'models_dqn/robotron_dqn_latest.pt';latest_stat=latest.lstat();latest_age=time.time()-latest_stat.st_mtime
    require(stat.S_ISREG(latest_stat.st_mode) and latest_stat.st_uid==UID and 0<latest_stat.st_size<=512<<20
        and math.isfinite(latest_age) and 0<=latest_age<=600,'Latest autosave metadata is not fresh')
    unit_owner(owner);unit_owner(fleet)
    require(all(process_start(x['pid'])==x['starttime_ticks'] for x in [owner,fleet,*baseline['actors']]) and
        process_start(worker['tid'])==worker['starttime_ticks'],'Main/fleet/actor/inference incarnation changed at final bracket')
    last_units=absent_units(obs,units)
    return dict(schema=SCHEMA,status='PASS',observed_unix_s=time.time(),
        candidate=dict(source=cfg['candidate']['path'],sha256=cfg['candidate']['sha256'],bytes=cfg['candidate']['bytes'],
            root_job_sha256=cfg['evidence']['phase_cpu_job']['sha256'],cpu_proof_sha256=cfg['evidence']['phase_cpu_report']['sha256']),
        **{k:baseline[k] for k in keys},
        resources=dict(gpu0_uuid=GPU_UUIDS[0],gpu1_uuid=GPU_UUIDS[1],GPU0_free_bytes=free[GPU_UUIDS[0]],
            GPU0_no_compute_owner=True,GPU1_main_only=True,port9999_clear=True,lease_free=True,
            no_competing_helpers=True,no_private_cgroup_tmpfs_processes=True,no_pending_save=True,
            owned_units_released=True,commands_UID_cwd_exe_checked=True,held_environment_checked=True,unit_files_checked=True),
        observations=dict(main=main,fleet=actual_fleet,actors=actors,inference_worker=worker_pin,
            first_unit_absence=first_units,last_unit_absence=last_units,old_process_absence=old_absence,
            selected_environment=selected_pin,checked_source_control_unit_pins=checked,
            evaluator_source_declared_and_resolved=resolution,global_process_scan=scan_pin,
            lease_identity=identity(before),private_tmpfs=private,private_cgroups=groups,port9999=tcp_pin,
            raw_API=raw_pin,API_summary=dict(ts=api['ts'],age_s=age,client_count=192,
                training_enabled=True,learner_frame_count=api['learner_frame_count'],four_pipeline_errors=0),
            latest_autosave_metadata=dict(path=str(latest),identity=identity(latest_stat),age_s=latest_age,
                max_age_s=600,body_read_or_hash=False)),
        binding=case['binding'],plan=case['plan'],release_actions=False,quality_acceptance=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--case',type=Path)
    parser.add_argument('--case-sha256');parser.add_argument('--output',type=Path)
    parser.add_argument('--expected-source-sha256');args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no reads, queries, locks or output; explicit root case/source/output required');return 0
    require(args.case and args.case_sha256 and args.output and args.expected_source_sha256,'Explicit root case/source/output required')
    out=args.output
    require(out.is_absolute() and RUN in out.parents and out.parent==out.parent.resolve(strict=True)
        and not os.path.lexists(out),'Fresh canonical run26 output required')
    out.mkdir(mode=0o700)
    fd=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    obs=Observation(out);result=dict(schema=SCHEMA,status='FAILED_READINESS_OBSERVATION',
        started_unix_s=time.time(),release_actions=False,quality_acceptance=False)
    try:
        _,source=read_file(__file__);require(source['sha256']==args.expected_source_sha256 and
            source['identity']['mode']=='0o444','Explicit readonly collector source differs')
        raw,pin=read_file(args.case);require(pin['sha256']==args.case_sha256 and
            pin['identity']['mode']=='0o444' and pin['identity']['nlink']==1,'Root case source differs')
        result.update(check(obs,decode(raw)),checker_source=source,root_case=pin)
    except BaseException as e:result['first_error']=dict(type=type(e).__name__,message=str(e))
    result.update(ended_unix_s=time.time(),raw_command_metadata=obs.commands,saved_input_pins=obs.pins)
    obs.publish('runtime-readiness.json',result)
    print(json.dumps(dict(status=result['status'],output=str(out)),allow_nan=False))
    return 0 if result['status']=='PASS' else 2


if __name__=='__main__':
    raise SystemExit(main())
