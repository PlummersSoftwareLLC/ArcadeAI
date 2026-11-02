"""Bounded typed file protocol for a prospective independently scoped observer.

Live files are control projections only. Scientific authority still requires the
original worker scope, immutable outcome, all raw samples and independent replay.
Import performs no I/O, process actions or production mutations.
"""
import json,math,os,stat,time,fcntl
from contextlib import contextmanager
from pathlib import Path

LIVE_SCHEMA='robotron-dedicated-main-health-live-v1'
FINISH_SCHEMA='robotron-dedicated-main-health-finish-v1'
OUTCOME_SCHEMA='robotron-dedicated-main-health-outcome-v1'
MAX_MESSAGE_BYTES=65536
LIVE_KEYS={'schema','job','nonce','parent','owner','state','error','latest','initial',
           'observed_samples','emitted_monotonic_s','emitted_unix_s','outcome'}

def require(value,message):
    if not value:raise ValueError(message)

def integer(value,minimum=0):
    require(type(value)is int and value>=minimum,'Exact nonnegative integer required');return value

def finite(value):return type(value)in (int,float)and math.isfinite(value)

def decode(raw):
    require(type(raw)is bytes and 0<len(raw)<=MAX_MESSAGE_BYTES,'Bounded protocol bytes required')
    def pairs(rows):
        result={}
        for key,value in rows:
            require(key not in result,'Duplicate protocol JSON key');result[key]=value
        return result
    def invalid(value):raise ValueError('Nonfinite protocol JSON constant')
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    require(type(value)is dict,'Protocol object required');return value

def _checked_read_strict(path,uid,*,mode):
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode)and before.st_uid==uid and before.st_nlink==1
            and stat.S_IMODE(before.st_mode)==mode and 0<before.st_size<=MAX_MESSAGE_BYTES,
            'Original owned bounded regular protocol file required')
        raw=os.read(fd,MAX_MESSAGE_BYTES+1);after=os.fstat(fd)
        keys=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_nlink)
        require(keys(before)==keys(after)and len(raw)==before.st_size,'Protocol bytes changed during original read')
        return decode(raw)
    finally:os.close(fd)

def _publish_live_unlocked(path,value):
    raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode();require(len(raw)<=MAX_MESSAGE_BYTES,'Live projection exceeded byte bound')
    path=Path(path);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    if path.exists():
        before=path.lstat();require(stat.S_ISREG(before.st_mode)and before.st_uid==os.geteuid()and before.st_nlink==1,'Unknown live projection path')
    with tmp.open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o644);os.fsync(stream.fileno())
    os.replace(tmp,path)

def validate_live(value,job_pin,job,owner,now):
    require(type(value)is dict and set(value)==LIVE_KEYS and value['schema']==LIVE_SCHEMA,'Exact live schema/keys required')
    require(value['job']==job_pin and value['nonce']==job['nonce']and value['parent']==job['parent']
        and value['owner']==owner,'Live job/nonce/parent/original owner differs')
    require(value['state']=='running'and value['error']is None and value['outcome']is None,'Original observer is not running successfully')
    require(finite(now)and finite(value['emitted_monotonic_s'])and 0<=now-value['emitted_monotonic_s']<=.5
        and finite(value['emitted_unix_s']),'Stale/future or malformed live observer clock')
    latest=value['latest'];require(type(latest)is dict,'Original live observation status required')
    index=integer(latest.get('index'));require(integer(value['observed_samples'],1)==index+1,'Original live observation index/count differs')
    phase=latest.get('phase');require(type(phase)is dict and type(phase.get('accepted'))is bool
        and type(phase.get('overlap_pending'))is bool,'Typed original observation phase required')
    ready=value['initial'];require(type(ready)is dict and set(ready)=={'index','unix_s','unaccepted_samples'},'Exact initial readiness fields required')
    integer(ready['unaccepted_samples'])
    if ready['index']is None:require(ready['unix_s']is None and phase['overlap_pending'],'Unqualified initial state must remain pending')
    else:
        integer(ready['index']);require(ready['index']==ready['unaccepted_samples']<=10 and finite(ready['unix_s']),
            'Original first baseline index/time differs')
    return value

def validate_finish(value,job_pin,job,now):
    require(type(value)is dict and set(value)=={'schema','job','nonce','parent','action','created_monotonic_s'},'Exact finish schema/keys required')
    require(value['schema']==FINISH_SCHEMA and value['job']==job_pin and value['nonce']==job['nonce']
        and value['parent']==job['parent']and value['action']in ('close','abort'),
        'Finish job/nonce/parent/action differs')
    require(finite(value['created_monotonic_s'])and value['created_monotonic_s']<=now<job['deadline_monotonic_s'],
        'Future finish or original native deadline exceeded')
    return value['action']


LIVE_LOCK_WAIT_S=.1

def _lock_identity(s):
    return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_nlink)

@contextmanager
def _live_lock(path,uid,*,exclusive):
    path=Path(path);lock=path.with_name(path.name+'.lock')
    flags=os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK
    if exclusive:flags|=os.O_CREAT
    fd=os.open(lock,flags,0o600);acquired=False
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode)and before.st_uid==uid and before.st_nlink==1
            and stat.S_IMODE(before.st_mode)==0o600 and before.st_size==0,
            'Original owned empty single-link live lock required')
        require(_lock_identity(before)==_lock_identity(lock.lstat()),'Live lock named identity differs')
        deadline=time.monotonic()+LIVE_LOCK_WAIT_S
        operation=fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        while True:
            try:fcntl.flock(fd,operation|fcntl.LOCK_NB);acquired=True;break
            except BlockingIOError:
                require(time.monotonic()<deadline,'Bounded original live lock wait exceeded')
                time.sleep(.001)
        require(time.monotonic()<=deadline,'Bounded original live lock acquisition exceeded')
        require(_lock_identity(before)==_lock_identity(os.fstat(fd))==_lock_identity(lock.lstat()),
            'Live lock identity changed before protected operation')
        yield
        require(_lock_identity(before)==_lock_identity(os.fstat(fd))==_lock_identity(lock.lstat()),
            'Live lock identity changed during protected operation')
    finally:
        if acquired:fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)

LIVE_SNAPSHOT_SINGLE_OPEN=True

@contextmanager
def _live_lock_metadata(path,uid):
    """Validate the original lock identity without acquiring a shared flock.

    The source-bound single publisher replaces complete staged files atomically.
    A reader must not suspend that publisher while its cgroup is descheduled.
    """
    lock=Path(path).with_name(Path(path).name+'.lock')
    fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode)and before.st_uid==uid and before.st_nlink==1
            and stat.S_IMODE(before.st_mode)==0o600 and before.st_size==0,
            'Original owned empty single-link live lock required')
        require(_lock_identity(before)==_lock_identity(lock.lstat()),'Live lock named identity differs')
        yield
        require(_lock_identity(before)==_lock_identity(os.fstat(fd))==_lock_identity(lock.lstat()),
            'Live lock identity changed during protected operation')
    finally:os.close(fd)

def _live_file(s,uid,*,allow_unlinked=False):
    require(stat.S_ISREG(s.st_mode)and s.st_uid==uid
        and s.st_nlink in ((0,1)if allow_unlinked else(1,))
        and stat.S_IMODE(s.st_mode)==0o644 and 0<s.st_size<=MAX_MESSAGE_BYTES,
        'Original owned bounded regular protocol file required')

def _read_live_snapshot(path,uid):
    # The held, source-bound publisher only replaces completed staged inodes;
    # it never writes into a published inode. An open descriptor remains a
    # complete version even if rename retires its directory entry mid-read.
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);_live_file(before,uid,allow_unlinked=True)
        raw=os.read(fd,MAX_MESSAGE_BYTES+1);after=os.fstat(fd);_live_file(after,uid,allow_unlinked=True)
        core=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_mode,s.st_uid)
        require(core(before)==core(after)and len(raw)==before.st_size,
            'Protocol bytes changed during original read')
        require((before.st_nlink,after.st_nlink)in ((1,1),(1,0),(0,0)),
            'Unexpected live snapshot link transition')
        if before.st_nlink==after.st_nlink:
            require(before.st_ctime_ns==after.st_ctime_ns,
                'Live snapshot metadata changed without retirement')
        else:require(after.st_ctime_ns>=before.st_ctime_ns,'Live snapshot retirement clock regressed')
        if after.st_nlink==0:
            replacement=path.lstat();_live_file(replacement,uid,allow_unlinked=True)
            require((replacement.st_dev,replacement.st_ino)!=(after.st_dev,after.st_ino)
                or(replacement.st_nlink==0 and core(replacement)==core(after)
                    and replacement.st_ctime_ns==after.st_ctime_ns),
                'Retired live snapshot lacks matching retirement evidence')
        return raw
    finally:os.close(fd)

def checked_read(path,uid,*,mode):
    if mode!=0o644:return _checked_read_strict(path,uid,mode=mode)
    with _live_lock_metadata(path,uid):
        raw=_read_live_snapshot(path,uid)
    return decode(raw)

def _publish_live_serialized_durable_v4(path,value):
    with _live_lock(path,os.geteuid(),exclusive=True):
        return _publish_live_unlocked(path,value)


def publish_live(path,value):
    """Ephemeral control projection; immutable outcome/raw files retain durability.

    Prepare outside the shared lock, then protect only replacement and identity.
    A failed publish leaves its original temporary bytes for diagnosis, no retry.
    """
    raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode()
    require(len(raw)<=MAX_MESSAGE_BYTES,'Live projection exceeded byte bound')
    path=Path(path);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    with tmp.open('xb')as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o644)
    with _live_lock(path,os.geteuid(),exclusive=True):
        if path.exists():
            before=path.lstat()
            require(stat.S_ISREG(before.st_mode)and before.st_uid==os.geteuid()and before.st_nlink==1,'Unknown live projection path')
        os.replace(tmp,path)
