#!/usr/bin/env python3
"""Default-dry-run adapter for the pinned OLD-source backward-only diagnostic.

No numerical imports occur here. This is forensic work, not snapshot validation.
The archived launcher supplies resource, identity, signal and owned cleanup code.
"""
from __future__ import annotations
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]
REPO=GAME.parent
LOCK_SHA='1eb72d795240af72135ad34c9dbb39f3ff9d313bb19d75d100d63e83b6e07fb4'
PROPOSAL_SHA='ad92cee9f1cbefe2451007e3a6c47a505905bcf5daf93877eb7362b7ee3cec48'
SCHEMA='robotron-offline-amp-backward-v1'
SEED=20261016
CASES=(('fp16_amp_default',65536.),('fp16_amp_scale1',1.),('fp32_unscaled',None))
BLOCKED_NAMES={'forensic_parent.py','forensic_worker.py','whole_agent_smoke.py','whole_agent_smoke_worker.py',
               'restore_serial_after_parallel_trial.py'}


def require(condition,message):
    if not condition:raise RuntimeError(message)


def digest(path):
    import hashlib
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def checked_module(path,expected,name):
    path=Path(path)
    require(not path.is_symlink() and path.is_file(),'Pinned module is not regular: '+str(path))
    data=path.read_bytes()
    import hashlib
    require(hashlib.sha256(data).hexdigest()==expected,'Pinned module differs: '+str(path))
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    # Execute precisely the verified bytes; never emit __pycache__ beside the
    # immutable archived receipt, even if the caller forgot Python's -B flag.
    exec(compile(data,str(path),'exec'),module.__dict__)
    return module


def read_lock():
    path=HERE/'source-lock.json'
    require(not path.is_symlink() and digest(path)==LOCK_SHA,'Forensic source lock changed')
    lock=json.loads(path.read_text())
    require(digest(HERE/'PROPOSAL.txt')==PROPOSAL_SHA==lock['proposal_text_sha256'],'Forensic proposal changed')
    require(lock['seed']==SEED and lock['backward_calls_per_case']==1 and lock['retries_allowed']==0 and
            lock['optimizer_steps_allowed']==lock['scaler_steps_allowed']==lock['scaler_updates_allowed']==0 and
            lock['fresh_scaler_per_amp_case'] is True,'Forensic limits changed')
    require([(item['name'],item['initial_scale']) for item in lock['case_order']]==list(CASES),'Forensic case order changed')
    root=Path(lock['source_root'])
    require(root==root.resolve() and len(lock['source_files'])==54,'Expected exactly54 archival sources')
    for name,item in lock['source_files'].items():
        path=Path(item['source'])
        require(path==root/name and Path(name).name==name and not path.is_symlink() and
                path.is_file() and path.stat().st_size==item['bytes'] and digest(path)==item['sha256'],
                'Frozen forensic source differs: '+name)
    for record in ('old_failure_receipt','old_launch_manifest'):
        item=lock[record]
        require(digest(item['path'])==item['sha256'],'Old failure evidence differs: '+record)
    return lock


def helpers(lock):
    modules={}
    for path,expected in lock['reusable_archived_helpers'].items():
        key='worker' if Path(path).name.endswith('_worker.py') else 'launcher'
        modules[key]=checked_module(path,expected,'_forensic_archived_'+key)
    require(set(modules)=={'worker','launcher'},'Missing archived helper')
    base=modules['launcher']
    # Archived helper __file__ is in logs; explicitly supply the real repository
    # anchors used for private-path validation. Never call its source_manifest.
    base.GAME,base.REPO=GAME,REPO
    base.QUALITY_NAMES=set(base.QUALITY_NAMES)|BLOCKED_NAMES
    return base,modules['worker']


def describe(directory):
    lock=read_lock()
    base,_=helpers(lock)
    directory=base.validate_output(directory,logs_root=GAME/'logs')
    return dict(status='DRY_RUN_ONLY',schema=SCHEMA,launch=False,output=str(directory),
        forensic_old_sources=True,current_merged_snapshot_qualification=False,source_lock_sha256=LOCK_SHA,
        proposal_sha256=PROPOSAL_SHA,source_files=lock['source_files'],seed=SEED,cases=list(CASES),
        backward_calls_per_case=1,optimizer_steps_allowed=0,retries_allowed=0,bounds=base.BOUNDS,
        gpu_uuid=base.GPU0_UUID,forbidden_gpu_uuid=base.MAIN_GPU_UUID,
        numerical_imports=False,live_queries=False,outputs_created=False)


def command(manifest):
    return [sys.executable,'-I','-B',str(HERE/'forensic_worker.py'),'--manifest',str(manifest)]


def run_child(base,layout,manifest_path,cgroup,main,deadline):
    """Same token/identity/owned-group lifecycle as the pinned run_phase."""
    paths=layout.phase('capture')
    deadline=min(deadline,time.monotonic()+base.BOUNDS['phase_timeout_s'])
    process=owned=None
    with (paths['root']/'worker.log').open('xb') as log:
        try:
            with base.blocked_handled_signals():
                process=subprocess.Popen(command(manifest_path),cwd=layout.output/'private',
                    env=base.configure_environment(layout,'capture'),stdin=subprocess.PIPE,
                    stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                owned=base.identity(process.pid)
                cgroup.attach(process.pid)
                require(owned['pgid']==process.pid,'Worker process group is not isolated')
            base.guard_live_resources(allowed_pids={os.getpid(),process.pid},expected_main=main)
            manifest=json.loads(manifest_path.read_text())
            process.stdin.write((manifest['launch_token']+'\n').encode());process.stdin.close()
            next_guard=0.
            while process.poll() is None:
                require(time.monotonic()<deadline,'Forensic phase deadline exceeded')
                require(base.byte_count(layout.output)<=base.BOUNDS['artifact_bytes'] and
                        base.byte_count(layout.tmpfs)<=base.BOUNDS['tmpfs_bytes'],'Forensic storage bound exceeded')
                if time.monotonic()>=next_guard:
                    base.guard_live_resources(allowed_pids={os.getpid(),process.pid},expected_main=main)
                    next_guard=time.monotonic()+1
                time.sleep(.1)
            require(process.returncode==0,'Forensic worker failed; retained worker.log/case evidence')
            require(not cgroup.members(),'Forensic child left descendants')
        finally:
            with base.blocked_handled_signals():
                try:
                    if process is not None:
                        if owned is None:
                            if process.stdin and not process.stdin.closed:process.stdin.close()
                            if process.poll() is None:process.terminate()
                            process.wait(timeout=5)
                        elif process.poll() is None or cgroup.members():
                            base.terminate_owned(process,owned,cgroup)
                finally:
                    if process is not None and process.stdin and not process.stdin.closed:process.stdin.close()
    result=json.loads((paths['root']/'phase-result.json').read_text())
    require(result['status']=='OBSERVATIONS_COMPLETE','Three-case forensic observations were not completed')
    return result


def launch(directory):
    require(not any(name.split('.')[0] in ('torch','numpy','dqn') for name in sys.modules),
            'A fresh stdlib-only parent is required')
    lock=read_lock()
    base,_=helpers(lock)
    directory=base.validate_output(directory,logs_root=GAME/'logs')
    with base.installed_signal_handlers():
        initial=base.guard_live_resources(allowed_pids={os.getpid()},initial=True)
        mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024>=16*base.GIB,'Host RAM margin insufficient')
        require(shutil.disk_usage(directory.parent).free>=8*base.GIB and
                shutil.disk_usage('/dev/shm').free>=256*base.MIB,'Disk/tmpfs margin insufficient')
        delegated=base.cgroup_parent()
        nonce=uuid.uuid4().hex
        layout=base.Layout(directory,nonce)
        require(not layout.tmpfs.exists(),'Private tmpfs already exists')
        descriptor=os.open('/dev/shm/robotron-snapshot-smoke-gpu0.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        lease=os.fdopen(descriptor,'r+')
        try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:
            lease.close();raise
        cgroup=root_identity=tmp_identity=None
        result=None
        try:
            base.guard_live_resources(allowed_pids={os.getpid()},expected_main=initial['main_owners'],initial=True)
            directory.mkdir(mode=0o700);root_identity=base.directory_identity(directory)
            layout.tmpfs.mkdir(mode=0o700);tmp_identity=base.directory_identity(layout.tmpfs)
            base.json_exclusive(directory/'ownership.json',dict(nonce=nonce,parent=base.identity(),output=root_identity,tmpfs=tmp_identity))
            base.json_exclusive(layout.tmpfs/'ownership.json',dict(nonce=nonce,parent=base.identity()))
            base.prepare_private_sources(layout,lock['source_files'])
            paths=layout.phase('capture')
            for key in ('root','models','journal','tmpfs','cache'):paths[key].mkdir(parents=True,mode=0o700)
            for name in ('inductor','triton','cuda','torch','extensions','tmp'):(paths['cache']/name).mkdir(mode=0o700)
            base.json_exclusive(paths['control'],dict(experiment='isolated-snapshot-smoke',lr_scale=.5))
            cgroup=base.OwnedCgroup(delegated,nonce)
            manifest=dict(schema=SCHEMA,explicit_launch=True,seed=SEED,cases=list(CASES),source_lock_sha256=LOCK_SHA,
                parent_sha256=digest(__file__),worker_sha256=digest(HERE/'forensic_worker.py'),
                launch_token=uuid.uuid4().hex,nonce=nonce,parent=base.identity(),output=str(directory),
                output_identity=root_identity,tmpfs=str(layout.tmpfs),tmpfs_identity=tmp_identity,
                cgroup=str(cgroup.path),cgroup_identity=cgroup.identity,main_owners=initial['main_owners'],
                gpu_uuid=base.GPU0_UUID,forbidden_gpu_uuid=base.MAIN_GPU_UUID,bounds=base.BOUNDS,
                sources=lock['source_files'],forensic_old_sources=True,current_merged_snapshot_qualification=False)
            path=directory/'launch-manifest.json';base.json_exclusive(path,manifest)
            result=run_child(base,layout,path,cgroup,initial['main_owners'],time.monotonic()+base.BOUNDS['total_timeout_s'])
            base.verify_source_copies(layout,lock['source_files']);read_lock()
            base.guard_live_resources(allowed_pids={os.getpid()},expected_main=initial['main_owners'])
        except BaseException as error:
            if root_identity is not None:
                base.check_directory(directory,root_identity)
                base.json_exclusive(directory/'failure.json',dict(status='DIAGNOSTIC_ERROR',error=repr(error)))
            raise
        finally:
            with base.blocked_handled_signals():
                errors=[]
                if cgroup is not None:
                    try:cgroup.close()
                    except BaseException as error:errors.append('cgroup: '+repr(error))
                if tmp_identity is not None and not errors:
                    try:
                        base.check_directory(layout.tmpfs,tmp_identity)
                        require(json.loads((layout.tmpfs/'ownership.json').read_text())['nonce']==nonce,'Tmpfs ownership changed')
                        shutil.rmtree(layout.tmpfs)
                    except BaseException as error:errors.append('tmpfs: '+repr(error))
                lease.close()
                if errors:
                    base.json_exclusive(directory/'cleanup-failure.json',dict(status='DIAGNOSTIC_ERROR',recovery_required=True,errors=errors))
                    raise RuntimeError('Owned cleanup requires recovery: '+repr(errors))
        base.json_exclusive(directory/'result.json',result)
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--launch',action='store_true')
    args=parser.parse_args(argv)
    result=launch(args.directory) if args.launch else describe(args.directory)
    print(json.dumps(result,indent=2,allow_nan=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
