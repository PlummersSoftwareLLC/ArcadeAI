"""Root-only stopped latest acquisition and strict CPU DATA assembly; default inert.

Root supplies the positively passed actual stopped authority. This program never
queries runtime, imports Torch/target modules, executes a controller, changes a
source/control, or reads replay/array bodies. It streams one published checkpoint
into an independent readonly copy; payload qualification remains strict CPU's job.
"""
import argparse,hashlib,json,os,stat,subprocess,time
from pathlib import Path
ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
LATEST=ROOT/'models_dqn/robotron_dqn_latest.pt'
PREPARER={'bytes': 24007, 'identity': {'bytes': 24007, 'ctime_ns': 1793471846081147948, 'device': 2304, 'inode': 82727975, 'mode': '0o444', 'mtime_ns': 1793471846081092748, 'nlink': 1, 'uid': 1001}, 'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-current-main-cold-cap-state-preservation-original01-20261030/current-A2-LR9375-route-source-only-original01-20261031/prepare_current_A2_LR9375_preservation_v7.py', 'sha256': 'af3ce5206aa5b14789a41f031b31e73ec6d1c9f52832d85eb32408da6c5694be'}
OWNER={'pid': 208501, 'starttime_ticks': 27823352, 'invocation_id': 'a1d8e91029684e31a6f245117cf736d3', 'cgroup': '/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-trainer.service', 'unit': 'robotron-trainer.service'}
FLEET={'pid': 965562, 'unit': 'robotron-mame.service', 'invocation_id': 'b84d5ab18e7c4a5c8a81da0be7f895a0', 'cgroup': '/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-mame.service', 'starttime_ticks': 30270092}


def require(ok,why):
    if not ok:raise ValueError(why)


def ident(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def metadata(path,*,limit=4<<20,allow_empty=False):
    path=Path(path);before=path.lstat();require(path.is_absolute()and path.resolve()==path and not path.is_symlink()
        and stat.S_ISREG(before.st_mode)and before.st_uid==os.getuid()and before.st_nlink==1
        and (0<=before.st_size if allow_empty else 0<before.st_size)and before.st_size<=limit,'Canonical bounded owned metadata/source required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        require(ident(os.fstat(fd))==ident(before),'Metadata open identity changed')
        with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(limit+1)
        require(ident(os.fstat(fd))==ident(before),'Metadata changed while read')
    finally:os.close(fd)
    require(ident(path.lstat())==ident(before)and len(raw)==before.st_size,'Metadata path/size changed')
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=ident(before)),raw


def read(value):
    p,raw=metadata(value['path']);require(p==value and p['identity']['mode']=='0o444','Exact immutable full8 metadata required');return json.loads(raw)


def put(path,value,*,allow_empty=False):
    raw=value if isinstance(value,bytes)else(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb')as stream:stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return metadata(path,allow_empty=allow_empty)[0]


def copy_stopped(target):
    before=LATEST.lstat();require(LATEST.resolve()==LATEST and not LATEST.is_symlink()and stat.S_ISREG(before.st_mode)
        and before.st_uid==os.getuid()and before.st_nlink==1 and 0<before.st_size<=512<<20,'Owned bounded published stopped latest required')
    destination=target/'actual-stopped-A2-latest-independent-copy.pt';source_fd=os.open(LATEST,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        require(ident(os.fstat(source_fd))==ident(before),'Stopped checkpoint changed on open')
        digest=hashlib.sha256();count=0;output_fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(output_fd,'wb')as output,os.fdopen(source_fd,'rb',closefd=False)as source:
            while True:
                block=source.read(8<<20)
                if not block:break
                count+=len(block);require(count<=before.st_size,'Stopped source grew while copying');digest.update(block);output.write(block)
            require(count==before.st_size and ident(os.fstat(source_fd))==ident(before),'Stopped source size/identity changed during copy')
            output.flush();os.fchmod(output.fileno(),0o444);os.fsync(output.fileno())
        # Rehash the independent sealed destination, never deserialize a model.
        copied_before=destination.lstat();require(stat.S_ISREG(copied_before.st_mode)and copied_before.st_uid==os.getuid()
            and copied_before.st_nlink==1 and stat.S_IMODE(copied_before.st_mode)==0o444
            and copied_before.st_size==count and(copied_before.st_dev,copied_before.st_ino)!=(before.st_dev,before.st_ino),'Independent readonly destination required')
        copied_fd=os.open(destination,os.O_RDONLY|os.O_NOFOLLOW);verify=hashlib.sha256();verified=0
        try:
            require(ident(os.fstat(copied_fd))==ident(copied_before),'Copy changed on verification open')
            with os.fdopen(copied_fd,'rb',closefd=False)as stream:
                while True:
                    block=stream.read(8<<20)
                    if not block:break
                    verified+=len(block);require(verified<=count,'Independent copy grew');verify.update(block)
            require(ident(os.fstat(copied_fd))==ident(copied_before),'Copy changed during verification')
        finally:os.close(copied_fd)
        require(verified==count and verify.hexdigest()==digest.hexdigest()and ident(destination.lstat())==ident(copied_before)
            and ident(os.fstat(source_fd))==ident(before)and ident(LATEST.lstat())==ident(before),'Source/copy hashes or bracketed identities differ')
    finally:os.close(source_fd)
    directory=os.open(target,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return(dict(path=str(LATEST),sha256=digest.hexdigest(),bytes=count,identity=ident(before)),
           dict(path=str(destination),sha256=verify.hexdigest(),bytes=verified,identity=ident(copied_before)))


def prepare(args):
    own,_=metadata(Path(__file__).resolve());require(own['sha256']==args.expected_source_sha256 and own['identity']['mode']=='0o444','Frozen selected acquisition source required')
    ap,raw=metadata(args.stopped_authority);require(ap['sha256']==args.stopped_authority_sha256 and ap['identity']['mode']=='0o444','Exact actual stopped authority required');authority=json.loads(raw)
    require(authority['schema']=='robotron-continuous-budget-stopped-preservation-authority-v1'and authority['owner']==OWNER and authority['fleet']==FLEET
        and type(authority['actual_exit'])is int and authority['actual_exit']==0 and authority['original_scope_released']is True,'Actual same-current Main normal0 stopped authority required')
    selection_pin=authority['original_selection'];selection=read(selection_pin)
    require(selection['owner']==OWNER and selection['fleet']==FLEET and selection['expected_current_cap']==8
        and selection['expected_control_sha256']=='c13002750cdbb8c0d3a2017fba8a6d52283d15e8a07339dd8c104e3f94f46f1e'
        and type(selection['expected_lr_scale'])is float and selection['expected_lr_scale']==.1875,'Exact stopped A2/.1875 selection required')
    require(metadata(PREPARER['path'])[0]==PREPARER,'Frozen strict CPU DATA preparer changed')
    target=args.output.absolute();require(target.parent==HERE and target.resolve()==target and not target.exists(),'Fresh direct-child acquisition directory required');target.mkdir(mode=0o700)
    started=time.time();source,copied=copy_stopped(target)
    require(metadata(ap['path'])[0]==ap and metadata(selection_pin['path'])[0]==selection_pin,'Stopped authority/selection changed during acquisition')
    acquisition=put(target/'Root-stopped-A2-checkpoint-and-independent-copy.json',dict(schema='robotron-root-stopped-checkpoint-and-independent-copy-v1',
        stopped_authority=ap,original_selection=selection_pin,source_checkpoint=source,verification_copy=copied,
        all_original_writers_stopped_before_copy=True,stopped_precondition='Root-selected actual passed normal0 stopped authority; no runtime liveness query is performed here',
        one_source_FD_and_source_full8_bracket=True,independent_copy_rehashed=True,model_payload_deserialized_or_qualified=False,observed_unix_s=time.time(),elapsed_s=time.time()-started))
    argv=['/usr/bin/python3.12','-I','-B',PREPARER['path'],'--prepare-cpu','--selection',selection_pin['path'],'--selection-sha256',selection_pin['sha256'],
        '--stopped-authority',ap['path'],'--stopped-authority-sha256',ap['sha256'],'--checkpoint-acquisition',acquisition['path'],'--checkpoint-acquisition-sha256',acquisition['sha256'],
        '--output',str(target/'CPU-DATA'),'--source-sha256',PREPARER['sha256']]
    result=subprocess.run(argv,capture_output=True,timeout=60)
    stdout=put(target/'assembler-stdout.txt',result.stdout,allow_empty=True);stderr=put(target/'assembler-stderr.txt',result.stderr,allow_empty=True)
    command=put(target/'Root-strict-CPU-DATA-assembler-command.json',dict(argv=argv,actual_exit=result.returncode,stdout=stdout,stderr=stderr))
    require(result.returncode==0,'Strict CPU DATA assembler failed; no controller was executed')
    require(metadata(PREPARER['path'])[0]==PREPARER and metadata(ap['path'])[0]==ap and metadata(selection_pin['path'])[0]==selection_pin,'Selected source/authority/selection changed after DATA assembly')
    pp,raw=metadata(target/'CPU-DATA/prepared-current-continuous-stopped600-NOT-LAUNCHED.json');require(pp['identity']['mode']=='0o444','Immutable prepared CPU metadata required');prepared=json.loads(raw)
    return put(target/'prepared-current-A2-stopped-checkpoint-and-CPU-DATA-NOT-LAUNCHED.json',dict(schema='robotron-root-current-A2-stopped-checkpoint-and-CPU-DATA-preparation-v1',status='CHECKPOINT_COPIED_CPU_DATA_PREPARED_NOT_LAUNCHED',
        source=own,stopped_authority=ap,original_selection=selection_pin,checkpoint_acquisition=acquisition,assembler_command=command,prepared_CPU=pp,
        Root_controller_argv_NOT_EXECUTED=prepared['Root_controller_argv'],CPU_backup_install_release_or_launch_executed=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--expected-source-sha256')
    p.add_argument('--stopped-authority',type=Path);p.add_argument('--stopped-authority-sha256');p.add_argument('--output',type=Path,default=HERE/'actual-stopped-checkpoint-and-CPU-original01');a=p.parse_args()
    if a.prepare:print(json.dumps(prepare(a)),flush=True)
    else:print('PLAN_ONLY_NO_READS_WRITES_OR_ACTIONS')
