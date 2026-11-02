"""Serialize live publication/read; preserve every original strict read check."""
import ast,importlib.util,os
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'tools/training_connection_lifecycle_proposal_20261023'
R=G/'logs/managed-learning-20261015/run-26'
D=R/'serialized-live-protocol-CPU-original01-preparation-20261024'
spec=importlib.util.spec_from_file_location('_serialized_prepare_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
oldpath=P/'dedicated_main_health_protocol_v1.py';old=oldpath.read_text()
source=old.replace('import json,math,os,stat,time','import json,math,os,stat,time,fcntl\nfrom contextlib import contextmanager')
assert source!=old
source=source.replace('def checked_read(path,uid,*,mode):','def _checked_read_strict(path,uid,*,mode):')
source=source.replace('def publish_live(path,value):','def _publish_live_unlocked(path,value):')
source+='''

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

def publish_live(path,value):
    with _live_lock(path,os.geteuid(),exclusive=True):
        return _publish_live_unlocked(path,value)
'''
target=P/'dedicated_main_health_protocol_serialized_v4.py';compile(source,str(target),'exec')
newnodes={n.name:n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
equivalent=[]
for n in ast.parse(old).body:
    if isinstance(n,ast.FunctionDef):
        selected=newnodes[dict(checked_read='_checked_read_strict',publish_live='_publish_live_unlocked').get(n.name,n.name)]
        selected.name=n.name;assert ast.dump(n)==ast.dump(selected),n.name;equivalent.append(n.name)
with target.open('xb')as f:f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
D.mkdir(mode=0o700)
h.put(D/'source-and-reproduction-provenance.json',dict(schema='robotron-serialized-live-protocol-source-provenance-v1',original_protocol=h.pin(oldpath),prospective_protocol=h.pin(target),
    original_functions_AST_identical=equivalent,original_read_and_publish_only_renamed=True,
    actual_original_race=h.pin(R/'original-live-atomic-replace-reproduction-CPU-original01-preparation-20261024/independent-original-four-filesystem-interleaves-and-scope-closeout.json'),
    failed_snapshot_v2=h.pin(P/'dedicated_main_health_protocol_atomic_snapshot_v2.py'),failed_snapshot_v3=h.pin(P/'dedicated_main_health_protocol_atomic_snapshot_v3.py'),
    actual_kernel_metadata_evidence=h.pin(R/'live-snapshot-retirement-order-CPU-original01-preparation-20261024/independent-original-retirement-order-metadata-and-scope-closeout.json'),
    strict_byte_type_owner_mode_single_link_and_metadata_checks_retained=True,
    immutable_finish_dispatch_unchanged=True,live_payload_schema_and_validation_unchanged=True,
    lock_wait_limit_s=.1,lock_empty_mode='0o600',shared_reader_exclusive_publisher=True,
    no_health_raw_retry_filter_reordering_or_limit_change=True,production_changed=False,quality_qualified=False))
print(h.pin(target)['sha256'])
