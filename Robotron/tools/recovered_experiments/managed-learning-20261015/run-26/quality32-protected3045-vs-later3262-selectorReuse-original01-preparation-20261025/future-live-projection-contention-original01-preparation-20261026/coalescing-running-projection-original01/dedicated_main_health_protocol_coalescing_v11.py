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

def checked_read(path,uid,*,mode):
    if mode!=0o644:return _checked_read_strict(path,uid,mode=mode)
    with _live_lock(path,uid,exclusive=False):
        return _checked_read_strict(path,uid,mode=mode)

def _publish_live_serialized_durable_v4(path,value):
    with _live_lock(path,os.geteuid(),exclusive=True):
        return _publish_live_unlocked(path,value)


def _publish_live_required_v5(path,value):
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


_RUNNING_PUBLICATIONS=dict(attempts=0,published=0,coalesced_busy_reader=0,errors=0)

def publication_stats():
    # The bound observer calls emit only on its sole control/collection thread.
    return dict(_RUNNING_PUBLICATIONS)

@contextmanager
def _try_running_publish_lock(path,uid):
    path=Path(path);lock=path.with_name(path.name+'.lock')
    fd=os.open(lock,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CREAT,0o600)
    acquired=False
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode)and before.st_uid==uid and before.st_nlink==1
            and stat.S_IMODE(before.st_mode)==0o600 and before.st_size==0,
            'Original owned empty single-link live lock required')
        require(_lock_identity(before)==_lock_identity(lock.lstat()),'Live lock named identity differs')
        deadline=time.monotonic()+LIVE_LOCK_WAIT_S
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True;break
            except BlockingIOError:
                if time.monotonic()>=deadline:break
                time.sleep(.001)
        if acquired:require(time.monotonic()<=deadline,'Bounded original live lock acquisition exceeded')
        require(_lock_identity(before)==_lock_identity(os.fstat(fd))==_lock_identity(lock.lstat()),
            'Live lock identity changed before protected operation')
        yield acquired
        require(_lock_identity(before)==_lock_identity(os.fstat(fd))==_lock_identity(lock.lstat()),
            'Live lock identity changed during protected operation')
    finally:
        if acquired:fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)

def publish_live(path,value):
    """Coalesce only a running control projection when its reader is busy.

    Every raw observation still runs and is durably retained. Cached projections
    remain subject to the unchanged500ms freshness gate. Starting, closed and
    failed publications keep the original strict100ms behavior and preserved
    failure bytes. No errors other than verified flock contention are coalesced.
    """
    if type(value)is not dict or value.get('state')!='running':
        return _publish_live_required_v5(path,value)
    _RUNNING_PUBLICATIONS['attempts']+=1
    try:
        raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode()
        require(len(raw)<=MAX_MESSAGE_BYTES,'Live projection exceeded byte bound')
        path=Path(path);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
        with tmp.open('xb')as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o644)
            staged=_lock_identity(os.fstat(stream.fileno()))
        with _try_running_publish_lock(path,os.geteuid())as acquired:
            if acquired:
                if path.exists():
                    before=path.lstat()
                    require(stat.S_ISREG(before.st_mode)and before.st_uid==os.geteuid()and before.st_nlink==1,
                        'Unknown live projection path')
                os.replace(tmp,path)
        if not acquired:
            # Context exit has verified the original lock metadata unchanged.
            # Discard only our exact completed, uncommitted control projection.
            require(_lock_identity(tmp.lstat())==staged,'Owned staged live projection identity changed')
            tmp.unlink()
            _RUNNING_PUBLICATIONS['coalesced_busy_reader']+=1
            return False
        _RUNNING_PUBLICATIONS['published']+=1
        return True
    except BaseException:
        _RUNNING_PUBLICATIONS['errors']+=1
        raise
