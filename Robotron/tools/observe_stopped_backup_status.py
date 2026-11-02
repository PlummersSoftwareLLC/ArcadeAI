"""Read-only backup observation; writes only Root's control and fresh observer runtime."""
import argparse, hashlib, json, math, os, stat, sys, time
from pathlib import Path


def require(ok, reason):
    if not ok: raise ValueError(reason)


def read(path, *, sealed=False):
    p=Path(path);s=p.lstat();require(p.resolve()==p and stat.S_ISREG(s.st_mode)and not p.is_symlink()and s.st_uid==os.getuid()and s.st_nlink==1 and 0<s.st_size<=4<<20,'Bounded owned JSON required')
    require(not sealed or stat.S_IMODE(s.st_mode)==0o444,'Sealed owner/result required')
    raw=p.read_bytes();require(len(raw)==s.st_size,'JSON extent changed');return json.loads(raw),s.st_mtime


def atomic(path, value):
    p=Path(path);tmp=p.with_name(p.name+'.backup-observer-'+str(os.getpid())+'.tmp')
    with tmp.open('x')as f:json.dump(value,f,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    os.replace(tmp,p);fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def accounting(progress):
    require(progress['schema']=='robotron-stopped-backup-progress-v1','Unknown backup progress')
    rows=progress['completed_files'];names=[r['relative']for r in rows]
    require(len(names)==len(set(names))and all(type(r['bytes_copied'])is int and r['bytes_copied']>=0 and r['complete']is True and r['fsync_completed']is True for r in rows),'Invalid completed-file ledger')
    total=progress['planned_bytes'];active=progress['active_file_bytes'];require(type(total)is int and total>0 and type(active)is int and active>=0,'Invalid copy counters')
    copied=sum(r['bytes_copied']for r in rows)+(active if progress['active_file']is not None and progress['active_file']not in names else 0)
    elapsed=progress['elapsed_s'];require(0<=copied<=total and type(elapsed)in(int,float)and math.isfinite(elapsed)and elapsed>=0,'Invalid byte/elapsed accounting')
    return copied,total,elapsed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in('progress','manifest','command-result','owner','control','runtime'):p.add_argument('--'+key,required=True,type=Path)
    p.add_argument('--max-seconds',type=int,default=3700);a=p.parse_args();require(1<=a.max_seconds<=3700,'Observer bound exceeds3700s')
    for key in('progress','manifest','command_result','owner','control','runtime'):setattr(a,key,getattr(a,key).absolute())
    require(a.progress.name=='backup-progress.json'and a.manifest.name=='backup-manifest.json'and a.progress.parent==a.manifest.parent,'Progress and manifest must name the same backup')
    require(a.control.name=='work-control.json'and 'html'not in a.control.parts,'Only private work-control.json may be updated')
    target,_=read(a.owner,sealed=True);pid=target['pid'];born=target['birth']
    require(type(pid)is int and pid>1 and type(born)is int and born>0,'Exact original controller PID/birth required')
    require(not a.runtime.exists()and a.runtime.parent.resolve()==a.runtime.parent,'Fresh observer runtime required');a.runtime.mkdir(mode=0o700)
    atomic(a.runtime/'owner.json',dict(pid=os.getpid(),birth=birth(os.getpid()),target_owner=target,argv=sys.argv,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),started_unix_s=time.time()))
    start=time.monotonic();last_log=-math.inf;last_observation=None;status='OBSERVER_TIME_BOUND_REACHED';success=False;reason=None
    while time.monotonic()-start<a.max_seconds:
        now=time.time();copied=total=0;eta=None;terminal=None;manifest=None;error=None;alive=birth(pid)==born
        stage='Waiting for original backup progress';waiting='The original backup metadata';remaining=None
        try:
            if a.progress.exists():
                progress,stamp=read(a.progress);copied,total,elapsed=accounting(progress);last_observation=stamp
                age=now-stamp;require(age>=-1,'Future backup progress timestamp')
                stage=f'Preserving full training state: {copied/(1<<30):.1f} / {total/(1<<30):.1f} GiB copied'
                waiting='The original stream copy, hashes and disk flush'
                if age>30:stage+='; waiting for flush/progress';waiting='Progress has not advanced for over30s; waiting for original flush or validation'
                elif copied and elapsed>0 and copied<total and progress['status']=='COPYING':
                    remaining=(total-copied)/(copied/elapsed);eta=f'Estimated copy time remaining: {math.ceil(remaining/60)} min; final flush and closure may add time'
                if progress['complete']is True or copied==total:stage='Copy bytes complete; waiting for flush and original controller result';eta=None
                if progress['status']=='FAILED_PARTIAL_RETAINED':stage='Backup reported a partial failure; waiting for original controller result';eta=None
            if a.manifest.exists():manifest,stamp=read(a.manifest,sealed=True);last_observation=max(last_observation or 0,stamp)
            if a.command_result.exists():
                terminal,stamp=read(a.command_result,sealed=True);last_observation=max(last_observation or 0,stamp)
                require(terminal['owner']==target and terminal['original_child_reaped']is True and type(terminal['actual_exit'])is int,'Original command result belongs to another controller')
                success=terminal['actual_exit']==0 and manifest is not None and manifest.get('schema')=='robotron-verified-stopped-full-training-backup-v1'and manifest.get('status')=='COMPLETE_STREAM_HASHED_AND_FSYNCED'
                if success:require(sum(r['bytes_copied']for r in manifest['files'])==manifest['total_bytes']and manifest['original_job']==progress['original_job']and all(r['complete']is True and r['fsync_completed']is True for r in manifest['files'])and all(manifest[k]is True for k in('full_ring_states_and_next_states_streamed_and_hashed','all_selected_bank_generation_fields_copied','all_files_independent_single_link_readonly','no_sources_written_or_chmodded')),'Incomplete manifest ledger')
                status='BACKUP_COMPLETE_ORIGINAL_CONTROLLER_EXIT0'if success else'ORIGINAL_TERMINAL_REQUIRES_REVIEW';stage='Full state backup complete; ready for verified cap12 restore'if success else'Original backup ended; completion evidence requires review';eta=None
                waiting='Root verification and cap12 held restore'if success else'Root review of the original result and retained backup'
            elif not alive:stage+='; waiting for original command result';waiting='Controller birth is absent; absence alone is not backup success';eta=None
        except Exception as exc:
            success=False;error=repr(exc);reason=error;stage='Backup status evidence needs review';waiting=error;eta=None
            if a.command_result.exists():status='ORIGINAL_RESULT_EVIDENCE_INVALID';terminal={}
        reason=error
        control,_=read(a.control);control['mode']='manual';control['main_training_continues']=False;control['observation_unix_s']=last_observation;control['publisher_heartbeat_unix_s']=now
        control.setdefault('next_work',{}).update(state='backup_complete'if success else'preserving_training_state',current_stage=stage,detail='Preserving the full model, Adam, scaler, replay and banks before continuing the8→12→8 throughput trial.',waiting_for=waiting,next_stage='Verified cap12 restore, five-minute warmup, then five-minute measurement',eta=eta,deadline_unix_s=None,updated_unix_s=now,observation_unix_s=last_observation,main_training_continues=False)
        atomic(a.control,control);heartbeat=dict(observed_unix_s=now,progress_observation_unix_s=last_observation,controller_birth_alive=alive,bytes_copied=copied,planned_bytes=total,estimated_copy_remaining_s=remaining if eta else None,stage=stage,error=error);atomic(a.runtime/'heartbeat.json',heartbeat)
        if time.monotonic()-last_log>=30:print(json.dumps(heartbeat),flush=True);last_log=time.monotonic()
        if terminal is not None:break
        time.sleep(min(10,max(0,a.max_seconds-(time.monotonic()-start))))
    if terminal is None:
        control,_=read(a.control);control['next_work'].update(current_stage='Status observer reached its bound; original backup remains untouched',waiting_for='Root review of the original controller result',eta=None);atomic(a.control,control)
    atomic(a.runtime/'result.json',dict(status=status,success=success,error=reason,original_command_exit=terminal.get('actual_exit')if terminal else None,ended_unix_s=time.time(),original_controller_restarted_stopped_or_signalled=False,model_or_array_bodies_read=False))
    return 0 if success else 1


if __name__=='__main__':raise SystemExit(main())
