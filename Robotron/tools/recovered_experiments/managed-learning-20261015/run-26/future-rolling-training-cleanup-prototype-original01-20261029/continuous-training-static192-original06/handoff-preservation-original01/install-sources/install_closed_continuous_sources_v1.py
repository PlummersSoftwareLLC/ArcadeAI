"""Default-inert Root cutover of exactly eleven selected Python source paths.

No unit configuration/start/stop, model/control/replay write, source rollback or
retry is provided. All old bytes are independently backed up and archived before
one atomic file replacement. Every partial attempt remains visible and closed.
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
H=G/'logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01'
PLAN=H/'startup-bridge-sources/complete-continuous-mode-and-startup-hold-eleven-source-plan-v1.json'
PLAN_SHA='34b60d3ce082565f46982681a3a9c3c1ce7af7f5616df787ba21a3ed1bd7a5f4'
BACKUP=H/'backup-sources/copy_verified_stopped_training_state_v4.py'
BACKUP_SHA='586889f547f83baac9b189365bcd5e868afe6b2c9501797fd83e2f0f67b3a805'
VERIFIER=H/'state-sources/verify_stopped_full_training_state_v2.py'
VERIFIER_SHA='560bdf7dc1045252949c02afebd3ae8f8d45f34f7809e7b2d4025145388a8f88'
ARCHIVE=G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
ARCHIVE_SHA='2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'
NEW_FILES={'connection_cleanup_receipts.py','continuous_startup_bridge.py'}
OUTPUT=H/'source-install-original01'


def require(value,message):
    if not value:raise RuntimeError(message)


def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,mode=oct(stat.S_IMODE(info.st_mode)),uid=info.st_uid,nlink=info.st_nlink)


def physical(path):
    path=Path(path)
    require(path.is_absolute()and path.resolve(strict=True)==path and not path.is_symlink(),'Canonical physical file required')
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode)and info.st_uid==os.getuid()and info.st_nlink==1,'Owned single-link regular file required')
    return identity(info)


def bounded_pin(path):
    path=Path(path);before=physical(path)
    require(0<=before['bytes']<=8<<20,'Bounded source/metadata only; no model or array body hashing')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb')as stream:
        require(identity(os.fstat(stream.fileno()))==before,'Selected open identity changed')
        raw=stream.read((8<<20)+1)
        require(before==identity(os.fstat(stream.fileno()))==physical(path),'Selected file changed while reading')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)


def read(value,as_json=True):
    require(type(value)is dict and set(value)=={'path','sha256','bytes','identity'},'Exact selected file pin required')
    actual=bounded_pin(value['path']);keys=set(value['identity'])
    require(keys in({'device','inode','mode','uid','nlink'},set(actual['identity'])),'Known full8/reduced5 only')
    require(actual['sha256']==value['sha256']and actual['bytes']==value['bytes']
        and all(actual['identity'][k]==x for k,x in value['identity'].items()),'Selected file identity or bytes changed')
    if as_json:require(actual['identity']['mode']=='0o444'and actual['bytes']>0,'Immutable selected JSON required')
    raw=Path(value['path']).read_bytes();require(bounded_pin(value['path'])==actual,'Selected read raced')
    return json.loads(raw)if as_json else raw


def load(path,sha,name):
    require(path is not None and type(sha)is str and re.fullmatch('[0-9a-f]{64}',sha),'Frozen dependency binding required')
    p=bounded_pin(path);require(p['sha256']==sha and p['identity']['mode']=='0o444','Exact inert dependency source required')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def publish(path,value,*,progress=False):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=8<<20,'Bounded cutover receipt required')
    temporary=path.with_name(path.name+'.next')if progress else path
    with temporary.open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    if progress:os.replace(temporary,path)  # Only this owned attempt's progress file.
    sync_dir(path.parent)
    return bounded_pin(path)


def must_be_absent(path):
    try:path.lstat()
    except FileNotFoundError:return
    raise RuntimeError('Selected new destination/stage already exists: '+str(path))


def closed_owners(backup,verifier,job):
    value=backup.owners_closed(job,verifier)
    # Exact old processes cannot be replaced by a new permanent-unit process
    # between backup and any source write. This function observes, never acts.
    for owner in(verifier.OWNER,backup.FLEET):
        raw=subprocess.check_output(['systemctl','--user','show',owner['unit']],text=True,timeout=5)
        fields=dict(x.split('=',1)for x in raw.splitlines()if'='in x)
        require(fields.get('Id')==owner['unit']and fields.get('MainPID')=='0'
            and fields.get('NRestarts')=='0'and fields.get('InvocationID')==owner['invocation_id']
            and fields.get('ActiveState')in('inactive','failed')and fields.get('SubState')in('dead','failed'),
            'An old permanent unit is active, replaced or not positively stopped')
    return value


def verify_closed_state(job,backup,verifier,archive):
    report=read(job['strict_CPU_report']);manifest=read(job['restoration_manifest'])
    require(report['schema']=='robotron-stopped-full-training-state-CPU-result-v1'and report['status']=='PASS'
        and report['source']['path']==str(VERIFIER)and report['source']['sha256']==VERIFIER_SHA
        and report['restoration_manifest']==job['restoration_manifest']
        and manifest['schema']=='robotron-stopped-full-training-state-restoration-manifest-v1'
        and manifest['status']=='VERIFIED_STOPPED_STATE'and manifest['source']==report['source']
        and manifest['original_job']==report['original_job']and manifest['owner']==verifier.OWNER,
        'Exact independently verified stopped report/manifest required')
    strict_owner=read(job['strict_CPU_owner']);strict_closure=read(job['strict_CPU_closure'])
    terminal=archive.archived_closure(strict_closure,strict_owner,read,exit_zero=True)
    require(report['actual_scope']['MainPID']==str(strict_owner['pid'])
        and report['actual_scope']['InvocationID']==strict_owner['invocation_id']
        and all(terminal.get(k)==v for k,v in dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),
            MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='10min').items()),'Stopped CPU resources/actual owner differ')
    saved=read(manifest['stopped_authority'])
    require(saved['owner']==verifier.OWNER and saved['actual_exit']==0 and saved['original_scope_released']is True,
        'Original trainer normal terminal closure required')
    full=read(job['full_backup_report']);bj=read(full['original_job'])
    require(full['schema']=='robotron-verified-stopped-full-training-backup-v1'
        and full['status']=='COMPLETE_STREAM_HASHED_AND_FSYNCED'
        and full['source']['path']==str(BACKUP)and full['source']['sha256']==BACKUP_SHA
        and full['strict_CPU_report']==job['strict_CPU_report']and full['restoration_manifest']==job['restoration_manifest']
        and full['strict_CPU_closure']==job['strict_CPU_closure']
        and all(full[k]is True for k in('full_ring_states_and_next_states_streamed_and_hashed',
            'all_selected_bank_generation_fields_copied','all_files_independent_single_link_readonly','no_sources_written_or_chmodded')),
        'Actual completed FULL preserving backup required')
    require(bj['source']==full['source']and bj['schema']=='robotron-verified-stopped-full-training-backup-job-v1'
        and bj['original_attempt']==1 and bj['no_retry']is True and bj['strict_CPU_report']==job['strict_CPU_report']
        and bj['restoration_manifest']==job['restoration_manifest']and bj['strict_CPU_closure']==job['strict_CPU_closure']
        and bj['strict_CPU_owner']==job['strict_CPU_owner'],'Actual backup job must join same stopped state')
    owner=read(job['full_backup_owner']);closure=read(job['full_backup_closure'])
    terminal=archive.archived_closure(closure,owner,read,exit_zero=True)
    require(full['actual_scope']['MainPID']==str(owner['pid'])and full['actual_scope']['InvocationID']==owner['invocation_id']
        and full['actual_scope']['Id']==bj['unit']==owner['unit']
        and all(terminal.get(k)==v for k,v in dict(CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),
            MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='1h').items()),'FULL backup original0/resource closure differs')
    for current,scope in((strict_owner,report['actual_scope']),(owner,full['actual_scope'])):
        backup.absent(current['pid'],current['starttime_ticks'])
        require(not Path('/sys/fs/cgroup'+scope['ControlGroup']).exists(),'A verifier/backup cgroup remains')
    expected=backup.selected_files(manifest,report,bj)
    rows={x['relative']:x for x in full['files']};require(len(rows)==len(full['files'])==len(expected),'FULL backup inventory coverage differs')
    root=Path(bj['destination_root']);require(job['full_backup_report']['path']==str(root/'backup-manifest.json'),'Actual complete backup report path differs')
    total=0
    for entry in expected:
        row=rows[entry['relative']];target=root/'files'/entry['relative']
        require(row['source']==entry['source']and row['source_identity_before']==row['source_identity_after']==entry['identity']
            and row['destination']==str(target)and row['complete']is row['fsync_completed']is True
            and row['bytes_copied']==entry['identity']['bytes']and re.fullmatch('[0-9a-f]{64}',row['stream_sha256'])
            and row['expected_source_sha256']==entry['expected_sha256'],'FULL backup file evidence differs')
        require(physical(target)==row['destination_identity']and row['destination_identity']['mode']=='0o444',
            'A completed FULL backup copy changed')
        if entry['expected_sha256']is not None:require(row['stream_sha256']==entry['expected_sha256'],'Expected backup stream digest differs')
        total+=row['bytes_copied']
    require(total==full['total_bytes'],'FULL backup total byte accounting differs')
    control=job['unchanged_learning_control'];require(control['path']==str(G/'models_dqn/learning_control.json')
        and control['sha256']==bj['configuration_archives']['learning_control']['sha256'],'Exact stopped canonical control required')
    read(control,False)
    return dict(report=report,manifest=manifest,backup_report=full,backup_job=bj,backup_rows=rows,expected_files=expected,
        original_owners=closed_owners(backup,verifier,bj))


def protected_unchanged(state,control,destinations):
    for entry in state['expected_files']:
        if entry['source']not in destinations:
            require(physical(entry['source'])==entry['identity'],'An untouched model/replay/settings/evidence file changed')
    read(control,False)


def archive_old_sources(plan,state,output):
    records=[]
    for row in plan['rows']:
        target=Path(row['destination']);require(target.parent==G/'Scripts/dqn','Exact reviewed source directory required')
        old=row['previous_source_before_Root_handoff']
        if old is None:
            require(target.name in NEW_FILES,'Only the two reviewed added modules may lack old bytes')
            must_be_absent(target);records.append(dict(destination=str(target),original_absent=True,archive=None));continue
        require(bounded_pin(target)==old,'Current source differs from reviewed pre-handoff bytes/full8')
        copies=[x for x in state['backup_rows'].values()if x['source']==str(target)]
        require(len(copies)==1,'Every existing source must exist exactly once in completed FULL backup')
        copied=copies[0];require(copied['stream_sha256']==old['sha256']and copied['bytes_copied']==old['bytes'],
            'FULL backup old source digest differs')
        archive_pin=bounded_pin(copied['destination']);require(archive_pin['sha256']==old['sha256']and archive_pin['bytes']==old['bytes'],
            'Actual independent old source backup bytes differ')
        raw=read(old,False);path=output/'old-sources'/target.name
        with path.open('xb')as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        sync_dir(path.parent);local=bounded_pin(path);require(local['sha256']==old['sha256'],'Local source archive differs')
        records.append(dict(destination=str(target),original_absent=False,old_source=old,full_backup_copy=archive_pin,
            local_archive=local,original_mode=old['identity']['mode']))
    require({Path(x['destination']).name for x in records if x['original_absent']}==NEW_FILES,'Exact two absent modules required')
    return records


def execute(args):
    own=bounded_pin(Path(__file__).resolve());require(own['sha256']==args.expected_source_sha256
        and own['identity']['mode']=='0o444','Exact frozen installer source required')
    selected=bounded_pin(Path(args.selection));require(selected['sha256']==args.selection_sha256,'Exact Root install selection required')
    job=read(selected);require(job['schema']=='robotron-root-closed-state-eleven-source-install-job-v1'
        and job['source']==own and job['original_attempt']==1 and job['no_retry']is True
        and job['output_directory']==str(OUTPUT),'One original closed-state cutover selection required')
    plan=read(job['source_plan']);require(job['source_plan']['path']==str(PLAN)and job['source_plan']['sha256']==PLAN_SHA
        and len(plan['rows'])==11,'Exact frozen eleven-source row plan required')
    require(not OUTPUT.exists()and OUTPUT.parent.resolve(strict=True)==OUTPUT.parent,'Fresh owned one-attempt output required')
    OUTPUT.mkdir(mode=0o700);(OUTPUT/'old-sources').mkdir(mode=0o700)
    progress=dict(schema='robotron-continuous-source-install-progress-v1',status='VERIFYING_GATES',original_selection=selected,
        source=own,source_plan=job['source_plan'],rows=[],active_destination=None,stage='prerequisites',started_unix_s=time.time())
    def update():return publish(OUTPUT/'install-progress.json',progress,progress=True)
    def interrupted(signum,_frame):raise InterruptedError('Original source cutover interrupted by signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    update()
    try:
        backup=load(BACKUP,BACKUP_SHA,'_cutover_backup_source');verifier=load(VERIFIER,VERIFIER_SHA,'_cutover_stopped_verifier')
        archive=load(ARCHIVE,ARCHIVE_SHA,'_cutover_original_archives')
        state=verify_closed_state(job,backup,verifier,archive)
        destinations={x['destination']for x in plan['rows']};require(len(destinations)==11,'Duplicate source destination')
        require({x['destination']:x['source']['sha256']for x in plan['rows']}==plan['exact_installed_path_SHA_map'],
            'Source row plan and expected eleven digests differ')
        data={}
        for row in plan['rows']:data[row['destination']]=read(row['source'],False)
        protected_unchanged(state,job['unchanged_learning_control'],destinations)
        progress['old_archives']=archive_old_sources(plan,state,OUTPUT);progress.update(status='ARCHIVED_ALL_OLD_SOURCES',stage='install')
        update()
        for row in plan['rows']:
            dest=Path(row['destination']);old=row['previous_source_before_Root_handoff']
            progress['active_destination']=str(dest);update()
            closed_owners(backup,verifier,state['backup_job']);protected_unchanged(state,job['unchanged_learning_control'],destinations)
            if old is None:must_be_absent(dest)
            else:require(bounded_pin(dest)==old,'Source ownership changed before atomic cutover')
            if row['action']=='KEEP_EXACT_UNCHANGED':
                require(row['source']==old and old['sha256']==plan['exact_installed_path_SHA_map'][str(dest)],'Only exact unchanged config can be kept')
                progress['rows'].append(dict(destination=str(dest),action='KEPT_ORIGINAL_OBJECT',installed_source=old));update();continue
            stage=dest.with_name('.robotron-continuous-install-original01-'+dest.name)
            must_be_absent(stage);mode=int(old['identity']['mode'],8)if old is not None else 0o664
            require(mode==0o664,'Original source permissions must remain0664; reviewed new modules use0664')
            with stage.open('xb')as stream:
                stream.write(data[str(dest)]);stream.flush();os.fchmod(stream.fileno(),mode);os.fsync(stream.fileno())
            staged=bounded_pin(stage);require(staged['sha256']==row['source']['sha256'],'Staged candidate source differs')
            progress.update(stage='ATOMIC_REPLACEMENT_PENDING',staged_source=staged);update()
            closed_owners(backup,verifier,state['backup_job'])
            if old is None:
                must_be_absent(dest);os.link(stage,dest,follow_symlinks=False);stage.unlink()
            else:
                require(bounded_pin(dest)==old,'Original source replaced before commit');os.replace(stage,dest)
            sync_dir(dest.parent);installed=bounded_pin(dest)
            require(installed['sha256']==row['source']['sha256']and installed['identity']['mode']==oct(mode),
                'Installed bytes/mode differ')
            progress['rows'].append(dict(destination=str(dest),action='INSTALLED_ATOMIC_FILE',installed_source=installed))
            progress.update(stage='install',active_destination=None,staged_source=None);update()
        sources=[bounded_pin(row['destination'])for row in plan['rows']]
        require({x['path']:x['sha256']for x in sources}==plan['exact_installed_path_SHA_map'],'Final exact eleven installed bytes differ')
        require(next(x for x in sources if x['path']==str(G/'Scripts/dqn/config.py'))==next(
            x['previous_source_before_Root_handoff']for x in plan['rows']if x['destination']==str(G/'Scripts/dqn/config.py')),
            'Unchanged config object was rewritten')
        closed_owners(backup,verifier,state['backup_job']);protected_unchanged(state,job['unchanged_learning_control'],destinations)
        progress.update(status='INSTALLED_EXACT_ELEVEN_SOURCES_TRAINER_NOT_STARTED',stage='complete',active_destination=None,
            installed_sources=sources,old_trainer_and_population_closed=True,model_replay_control_untouched=True,
            strict_CPU_report=job['strict_CPU_report'],restoration_manifest=job['restoration_manifest'],
            full_backup_report=job['full_backup_report'],unit_configuration_changed=False,trainer_started=False,
            rollback_attempted=False,retry_attempted=False,actual_held_restoration_or_static192_qualified=False)
        update();receipt=publish(OUTPUT/'source-install-receipt.json',progress)
        print(json.dumps(dict(status=progress['status'],receipt=receipt,installed_sources=sources)),flush=True);return 0
    except BaseException as error:
        progress.update(status='FAILED_PARTIAL_RETAINED',error=repr(error),traceback=traceback.format_exc(),
            automatic_rollback=False,automatic_start=False,automatic_retry=False,Root_reconciliation_required=True)
        try:update();publish(OUTPUT/'source-install-failure.json',progress)
        except BaseException as secondary:print('Failure ledger publication failed: '+repr(secondary),file=sys.stderr)
        print(json.dumps(dict(status=progress['status'],error=repr(error),retained_output=str(OUTPUT))),flush=True);return 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--selection');p.add_argument('--selection-sha256');p.add_argument('--expected-source-sha256');args=p.parse_args()
    if args.execute:return execute(args)
    print('PLAN_ONLY_NO_READS_IMPORTS_WRITES_OR_ACTIONS');return 0


if __name__=='__main__':raise SystemExit(main())
