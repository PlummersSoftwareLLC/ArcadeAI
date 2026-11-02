"""Copy one actual verified stopped state to an exclusive Root-selected disk root.

Default inert. No restore, hardlinks, deletions, source writes, service actions,
numerical imports or actor admission. Complete stream hashes exist only after
all declared bytes were actually copied and fsynced. Partial outputs are retained.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import traceback

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
H=B/'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01'
VERIFIER=Path(__file__).with_name('verify_current_continuous_stopped_fullstate_cold_bank_v5.py')
VERIFIER_SHA='c244f7b9672f6b4218f284fb95b648033dfea4f6af581e0baae565e1a7cdd599'
ARCHIVE=G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
ARCHIVE_SHA='2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'
DESCRIPTORS=G/'tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/live8_maintenance_proposal/revision4/bank_state_revision2.py'
DESCRIPTORS_SHA='e0c69fb38f5fec86e117edf42b4ff1ce2ff44b82b979c5240116121a7a1ce54f'
FLEET=None  # Exact selected completed cold incarnation, never the old population.
SOURCE_NAMES=('__init__.py','model.py','config.py','learning_control.py','agent.py',
    'replay_buffer.py','training.py','priority_phase.py','main.py','socket_server.py',
    'managed_driver.py','managed_measurement.py','loss_kernel.py')


def require(value,message):
    if not value:raise RuntimeError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def source_identity(path):
    path=Path(path)
    require(path.is_absolute()and path.resolve(strict=True)==path and not path.is_symlink(),'Canonical physical source required')
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode)and info.st_uid==os.getuid()and info.st_nlink==1,'Owned single-link source required')
    return identity(info)


def pin(path):
    path=Path(path);before=source_identity(path)
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb')as stream:
        require(identity(os.fstat(stream.fileno()))==before,'Source open race')
        sha=hashlib.file_digest(stream,'sha256').hexdigest()
        require(identity(os.fstat(stream.fileno()))==before==source_identity(path),'Source changed while hashing')
    return dict(path=str(path),sha256=sha,bytes=before['bytes'],identity=before)


def read_pin(value,as_json=True):
    require(type(value)is dict and set(value)=={'path','sha256','bytes','identity'}and type(value['bytes'])is int and (0<value['bytes'] if as_json else 0<=value['bytes']) and value['bytes']<=8<<20,
        'Bounded metadata/source pin required; no array-body input sweep')
    keys=set(value['identity']);require(keys in(
        {'device','inode','mode','uid','nlink'},
        {'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'}),'Known reduced5/full8 identity required')
    actual=pin(value['path'])
    require(actual['sha256']==value['sha256']and actual['bytes']==value['bytes']
        and all(actual['identity'][k]==v for k,v in value['identity'].items()),'Selected metadata/source pin changed')
    raw=Path(value['path']).read_bytes();require(pin(value['path'])==actual,'Metadata changed while reading')
    return json.loads(raw)if as_json else raw


def load(path,digest,name):
    value=pin(path);require(value['sha256']==digest and value['identity']['mode']=='0o444','Exact readonly source required')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def absent(pid,birth):
    try:
        raw=Path('/proc',str(pid),'stat').read_text()
        require(int(raw[raw.rfind(')')+2:].split()[19])!=birth,'An original process birth remains live')
    except (FileNotFoundError,ProcessLookupError):pass


def empty_owner(owner):
    absent(owner['pid'],owner['starttime_ticks']);group=Path('/sys/fs/cgroup'+owner['cgroup'])
    if group.exists():
        for current in(group,*[p for p in group.rglob('*')if p.is_dir()]):
            require(not(current/'cgroup.threads').read_text().split(),'An original owner cgroup is populated')


def owners_closed(job,v):
    v.old_owner_absent(v.OWNER);empty_owner(FLEET)
    population=read_pin(job['original_population'])
    require(population['trainer']==v.OWNER and population['fleet']==FLEET
        and 0<=len(population['actors'])<=192,'Actual original variable population required')
    pairs={(a['pid'],a['starttime_ticks'])for a in population['actors']}
    require(len(pairs)==len(population['actors']),'Duplicate original physical population')
    for pid,birth in pairs:absent(pid,birth)
    archive=read_pin(job['fleet_terminal_archive'])
    require(archive['owner']==FLEET,'Original fleet archive differs')
    show=read_pin(archive['archives']['show'])
    require(show['argv']==['systemctl','--user','show',FLEET['unit']]
        and type(show['exit'])is int and show['exit']==0 and show['owner']==FLEET,'Original fleet terminal descriptor differs')
    props=dict(line.split('=',1)for line in read_pin(show['stdout'],False).decode().splitlines()if'='in line)
    wanted=dict(Id=FLEET['unit'],InvocationID=FLEET['invocation_id'],MainPID='0',
        ExecMainPID=str(FLEET['pid']),ExecMainCode='1',ExecMainStatus='0',NRestarts='0')
    require(all(props.get(k)==val for k,val in wanted.items()),'Original fleet normal0/no-restart is not proved')
    return dict(trainer=v.OWNER,fleet=FLEET,recorded_original_actor_births_absent=len(pairs),
        original_trainer_and_fleet_cgroups_empty=True)


def normalized_descriptor(row):
    value=dict(row['identity'])
    if 'size'in value:value['bytes']=value.pop('size')
    if type(value.get('mode'))is int:value['mode']=oct(value['mode'])
    require(set(value)=={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'},'Complete stopped storage identity required')
    return value


def selected_files(manifest,report,job):
    entries=[]
    def add(relative,row,kind):
        relative=Path(relative)
        require(not relative.is_absolute()and relative.parts and all(x not in('.','..')for x in relative.parts),
            'Safe exclusive relative backup path required')
        if set(row['identity'])=={'device','inode','mode','uid','nlink'}:
            observed=source_identity(row['path'])
            require(observed['bytes']==row['bytes']and all(observed[k]==val for k,val in row['identity'].items()),
                'Reduced metadata descriptor changed')
        else:observed=normalized_descriptor(row)
        entries.append(dict(relative=str(relative),source=row['path'],identity=observed,
            expected_sha256=row.get('sha256'),kind=kind))
    add('checkpoint/robotron_dqn_latest.pt',manifest['checkpoint'],'checkpoint')
    snap=manifest['ring_and_banks']
    add('ring/_meta.npy',snap['ring']['meta']['descriptor'],'ring_metadata')
    require(len(snap['ring']['arrays'])==10,'All ten ring storage files required')
    for name,row in snap['ring']['arrays'].items():
        selected=(manifest['ring_scalar_payload'][name]['file']if name in manifest['ring_scalar_payload']else row)
        add('ring/'+name+'.npy',selected,'ring_payload')
    require(set(snap['banks'])=={'hof','ephof'},'Both selected current banks required')
    for name,bank in snap['banks'].items():
        generation=bank['selector']['value']['generation']
        require(re.fullmatch(r'gen-[0-9a-f]{32}',generation)is not None,'Exact selected bank generation required')
        prefix='banks/'+name+'/generations/'+generation+'/'
        add('banks/'+name+'/CURRENT.json',bank['selector']['descriptor'],'bank_selector')
        add(prefix+name+'_meta.npz',bank['metadata']['descriptor'],'bank_metadata')
        require(set(bank['arrays'])=={'states','next_states','actions','rewards','dones','horizons','is_expert','actor_kind'},
            'All eight bank field arrays required')
        for field in bank['arrays']:
            add(prefix+name+'_'+field+'.npy',manifest['bank_payload'][name]['fields'][field]['file'],'bank_payload')
    strict_job=read_pin(report['original_job']);context=strict_job['source_control_context']
    source_map=job['current_source_archives']
    require(set(SOURCE_NAMES)<=set(source_map),'All current core source archives required')
    for name,row in source_map.items():
        require(Path(name).name==name and name.endswith('.py'),'Explicit source basename required')
        require(row['path']==str(G/'Scripts/dqn'/name),'Current source archive path differs')
        if name in context['model_package']:require(row==context['model_package'][name],'Strict numerical source archive differs')
        add('sources/'+name,row,'source')
    config=job['configuration_archives']
    require(set(config)=={'learning_control','game_settings','trainer_unit'},'Control/settings/unit snapshots required')
    require(config['learning_control']==context['archived_control']
        and config['trainer_unit']==context['archived_trainer_unit'],
        'Control/unit archive differs from exact verified stopped checkpoint context')
    require(config['game_settings']['path']==str(G/'models_dqn/game_settings.json'),
        'Actual stopped settings path required')
    for name,row in config.items():add('configuration/'+name+('.txt'if name=='trainer_unit'else'.json'),row,'configuration')
    evidence={name:job[name]for name in('restoration_manifest','strict_CPU_report','strict_CPU_owner','strict_CPU_closure',
        'original_population','fleet_terminal_archive')}
    evidence.update(stopped_authority=manifest['stopped_authority'],strict_original_job=report['original_job'])
    for name,row in evidence.items():add('evidence/'+name+'.json',row,'evidence')
    closure=read_pin(job['strict_CPU_closure'])
    for index,row in enumerate(closure.get('native_archives',closure.get('full_original_archives',[]))):
        for kind in('stdout','stderr'):add('evidence/CPU-descriptor-'+str(index)+'-'+kind+'.txt',row[kind],'evidence')
    require(len({x['relative']for x in entries})==len(entries),'Duplicate backup destinations')
    return entries


def publish(path,value,*,replace=False):
    path=Path(path);target=path.with_name(path.name+'.next')if replace else path
    with target.open('x')as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush()
        os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    if replace:os.replace(target,path)  # Only this backup's own progress ledger.
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def copy_file(entry,output,progress,update):
    source=Path(entry['source']);before=source_identity(source)
    require(before==entry['identity'],'Stopped source identity changed before copy: '+str(source))
    target=output/'files'/entry['relative'];target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    require(target.resolve(strict=False)==target and not target.exists(),'Exclusive physical backup file required')
    digest=hashlib.sha256();copied=0;last=0.0
    source_fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    target_fd=None
    try:
        target_fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        require(identity(os.fstat(source_fd))==before,'Source open race')
        require((os.fstat(target_fd).st_dev,os.fstat(target_fd).st_ino)!=(before['device'],before['inode'])
            and os.fstat(target_fd).st_nlink==1,'Independent non-hardlinked backup required')
        while True:
            chunk=os.read(source_fd,4<<20)
            if not chunk:break
            view=memoryview(chunk)
            while view:
                count=os.write(target_fd,view);require(count>0,'Backup write made no progress')
                digest.update(view[:count]);copied+=count;view=view[count:]
            now=time.monotonic()
            if now-last>=5:
                progress.update(active_file=entry['relative'],active_file_bytes=copied,
                    active_file_prefix_sha256=digest.hexdigest(),active_file_complete=False)
                update();last=now
        require(copied==before['bytes']and os.fstat(target_fd).st_size==copied,'Incomplete stopped file copy')
        require(identity(os.fstat(source_fd))==before==source_identity(source),'Source changed during stopped copy')
        if entry['expected_sha256']is not None:require(digest.hexdigest()==entry['expected_sha256'],'Verified source payload changed')
        os.fchmod(target_fd,0o444);os.fsync(target_fd)
        result=dict(relative=entry['relative'],source=str(source),source_identity_before=before,
            source_identity_after=source_identity(source),destination=str(target),destination_identity=identity(os.fstat(target_fd)),
            bytes_copied=copied,stream_sha256=digest.hexdigest(),complete=True,fsync_completed=True,
            expected_source_sha256=entry['expected_sha256'],destination_reread_hash_performed=False)
    except BaseException:
        progress.update(active_file=entry['relative'],active_file_bytes=copied,
            active_file_prefix_sha256=digest.hexdigest(),active_file_complete=False)
        try:update()
        except BaseException:pass
        raise
    finally:
        # Retain partial bytes read-only even on signal, I/O or source failure.
        try:
            if target_fd is not None:
                try:
                    if stat.S_IMODE(os.fstat(target_fd).st_mode)!=0o444:os.fchmod(target_fd,0o444)
                    os.fsync(target_fd)
                finally:os.close(target_fd)
        finally:os.close(source_fd)
    fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return result


def execute(args):
    global FLEET
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and 'LD_PRELOAD'not in os.environ and 'PYTHONPATH'not in os.environ,
        'CPU-hidden isolated backup required')
    self_pin=pin(Path(__file__).resolve());require(self_pin['sha256']==args.source_sha256,'Exact backup source required')
    jp=pin(Path(args.job).resolve());require(jp['sha256']==args.job_sha256 and jp['identity']['mode']=='0o444','Exact immutable Root backup job required')
    job=read_pin(jp)
    require(job['schema']=='robotron-verified-stopped-full-training-backup-job-v1'and job['source']==self_pin
        and job['original_attempt']==1 and job['no_retry']is True,'One original explicit backup job required')
    require(job['unit']=='robotron-current-continuous-backup3600-'+job['strict_CPU_report']['sha256'][:16]+'.service','Exact unique backup unit required')
    show=subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=10)
    fields=dict(x.split('=',1)for x in show.splitlines()if'='in x)
    expected=dict(Id=job['unit'],MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],
        CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='1h',Restart='no',NRestarts='0')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual3600s/2CPU/4G original backup scope differs')
    v=load(VERIFIER,VERIFIER_SHA,'_backup_stopped_verifier')
    reviewer=load(ARCHIVE,ARCHIVE_SHA,'_backup_original_CPU_archives')
    descriptors=load(DESCRIPTORS,DESCRIPTORS_SHA,'_backup_ring_descriptors')
    for value in job['inputs']:read_pin(value,False)
    report=read_pin(job['strict_CPU_report']);manifest=read_pin(job['restoration_manifest'])
    v.select_context(read_pin(report['original_job']));FLEET=v.FLEET
    require(report['schema']=='robotron-stopped-full-training-state-CPU-result-v1'and report['status']=='PASS'
        and report['source']['sha256']==VERIFIER_SHA and report['restoration_manifest']==job['restoration_manifest']
        and manifest['schema']=='robotron-stopped-full-training-state-restoration-manifest-v1'
        and manifest['status']=='VERIFIED_STOPPED_STATE'and manifest['source']==report['source']
        and manifest['original_job']==report['original_job'],'Actual strict stopped verification/report join required')
    owner,closure=(read_pin(job[k])for k in('strict_CPU_owner','strict_CPU_closure'))
    terminal=reviewer.archived_closure(closure,owner,read_pin,exit_zero=True)
    require(report['actual_scope']['Id']==owner['unit']and report['actual_scope']['MainPID']==str(owner['pid'])
        and report['actual_scope']['InvocationID']==owner['invocation_id']
        and all(terminal.get(k)==val for k,val in dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),
            MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='10min').items()),'Actual independently closed strict CPU owner/resources differ')
    absent(owner['pid'],owner['starttime_ticks'])
    require(not Path('/sys/fs/cgroup'+report['actual_scope']['ControlGroup']).exists(),'Strict CPU cgroup remains')
    authority=read_pin(manifest['stopped_authority'])
    require(authority['owner']==manifest['owner']==v.OWNER and authority['actual_exit']==0
        and authority['original_scope_released']is True,'Actual original trainer closure required')
    before_owners=owners_closed(job,v)
    require(descriptors.stopped_state(manifest['ring_and_banks']['spec'])==manifest['ring_and_banks'],
        'Verified stopped storage selection changed before backup')
    entries=selected_files(manifest,report,job);total=sum(x['identity']['bytes']for x in entries)
    output=Path(job['destination_root']);parent=output.parent
    require(output.is_absolute()and output.resolve(strict=False)==output and not output.exists()
        and parent.resolve(strict=True)==parent and parent.is_dir()and parent.stat().st_uid==os.getuid(),
        'New exclusive Root-owned backup root required')
    require(not output.is_relative_to(Path('/dev/shm'))and not output.is_relative_to(G/'models_dqn')
        and not output.is_relative_to(G/'Scripts'),'Backup cannot overwrite live model/ring/source roots')
    require(job['destination_volume']['scope']=='ROOT_SELECTED_SAME_HOST_DISK'
        and parent.stat().st_dev==job['destination_volume']['device']
        and parent.stat().st_dev!=Path('/dev/shm').stat().st_dev,'Exact Root-selected separate disk device required')
    space=os.statvfs(parent);available=space.f_bavail*space.f_frsize;margin=max(32<<30,(total+9)//10)
    require(available>=total+margin,'Insufficient free disk for complete copy plus margin')
    output.mkdir(mode=0o700)
    started=time.monotonic();progress=dict(schema='robotron-stopped-backup-progress-v1',status='COPYING',
        original_job=jp,source=self_pin,planned_bytes=total,required_free_margin=margin,available_bytes_at_start=available,
        completed_files=[],active_file=None,active_file_bytes=0,active_file_complete=False,complete=False)
    def update():
        progress.update(elapsed_s=time.monotonic()-started)
        publish(output/'backup-progress.json',progress,replace=True)
    def interrupted(signum,_frame):raise InterruptedError('Original backup interrupted by signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    update()
    try:
        for entry in entries:
            print(json.dumps(dict(phase='COPY',relative=entry['relative'],bytes=entry['identity']['bytes'])),flush=True)
            result=copy_file(entry,output,progress,update);progress['completed_files'].append(result)
            progress.update(active_file=None,active_file_bytes=0,active_file_prefix_sha256=None,active_file_complete=False);update()
        after_owners=owners_closed(job,v)
        require(descriptors.stopped_state(manifest['ring_and_banks']['spec'])==manifest['ring_and_banks'],
            'Stopped ring/bank selection changed during backup')
        for entry in entries:require(source_identity(entry['source'])==entry['identity'],'Stopped source identity changed after copy')
        for value in job['inputs']:read_pin(value,False)
        require(sum(x['bytes_copied']for x in progress['completed_files'])==total,'Backup byte accounting differs')
        progress.update(status='COMPLETE',complete=True)
        update()
        result=dict(schema='robotron-verified-stopped-full-training-backup-v1',status='COMPLETE_STREAM_HASHED_AND_FSYNCED',
            original_job=jp,source=self_pin,actual_scope=fields,strict_CPU_report=job['strict_CPU_report'],
            restoration_manifest=job['restoration_manifest'],strict_CPU_closure=job['strict_CPU_closure'],
            owners_before=before_owners,owners_after=after_owners,files=progress['completed_files'],total_bytes=total,
            full_ring_states_and_next_states_streamed_and_hashed=True,all_selected_bank_generation_fields_copied=True,
            all_files_independent_single_link_readonly=True,no_sources_written_or_chmodded=True,
            destination_payload_reread_hash_performed=False,restore_performed=False,startup_restore_qualified=False,
            actor_admission_authorized=False,quality_qualified=False,promotion=False,elapsed_s=time.monotonic()-started)
        publish(output/'backup-manifest.json',result)
        print(json.dumps(dict(status=result['status'],manifest=pin(output/'backup-manifest.json'))),flush=True)
        return 0
    except BaseException as error:
        progress.update(status='FAILED_PARTIAL_RETAINED',complete=False,error=repr(error),traceback=traceback.format_exc())
        try:update();publish(output/'backup-failure.json',progress)
        except BaseException as secondary:print('Partial ledger publication failed: '+repr(secondary),file=sys.stderr)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if args.execute:raise SystemExit(execute(args))
    print('PLAN_ONLY_NO_READS_IMPORTS_OUTPUTS_OR_ACTIONS')
