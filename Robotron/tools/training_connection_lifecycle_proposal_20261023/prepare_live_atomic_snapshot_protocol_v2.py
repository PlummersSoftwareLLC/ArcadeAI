"""Create an unselected live snapshot reader; immutable finish code stays exact."""
import ast,importlib.util,os
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'tools/training_connection_lifecycle_proposal_20261023'
R=G/'logs/managed-learning-20261015/run-26'
D=R/'live-atomic-snapshot-protocol-CPU-original01-preparation-20261024'
spec=importlib.util.spec_from_file_location('_snapshot_prepare_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
proof=R/'original-live-atomic-replace-reproduction-CPU-original01-preparation-20261024/independent-original-four-filesystem-interleaves-and-scope-closeout.json'
h.checked(h.pin(proof))
original=P/'dedicated_main_health_protocol_v1.py'
old=original.read_text();assert old.count('def checked_read(path,uid,*,mode):')==1
new=old.replace('def checked_read(path,uid,*,mode):','def _checked_read_strict(path,uid,*,mode):')
insert='''
def _live_metadata(s,uid):
    require(stat.S_ISREG(s.st_mode)and s.st_uid==uid and s.st_nlink in (0,1)
        and stat.S_IMODE(s.st_mode)==0o644 and 0<s.st_size<=MAX_MESSAGE_BYTES,
        'Original owned bounded regular live snapshot required')

def _checked_read_live(path,uid):
    # A published file is never modified in place. os.replace can retire an
    # already-open inode before either fstat; its immutable bytes stay readable.
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);_live_metadata(before,uid)
        raw=os.read(fd,MAX_MESSAGE_BYTES+1);after=os.fstat(fd);_live_metadata(after,uid)
        stable=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_mode,s.st_uid)
        require(stable(before)==stable(after)and len(raw)==before.st_size,
            'Live snapshot bytes or identity changed during original read')
        require((before.st_nlink,after.st_nlink)in ((1,1),(1,0),(0,0)),
            'Unexpected live snapshot link transition')
        if before.st_nlink==after.st_nlink:
            require(before.st_ctime_ns==after.st_ctime_ns,'Live snapshot metadata changed without retirement')
        if after.st_nlink==0:
            replacement=path.lstat();_live_metadata(replacement,uid)
            # The named replacement may itself retire during lstat. It must
            # still be an owned, bounded regular live inode distinct from fd.
            require((replacement.st_dev,replacement.st_ino)!=(after.st_dev,after.st_ino),
                'Retired live snapshot lacks a distinct owned replacement')
        return decode(raw)
    finally:os.close(fd)

def checked_read(path,uid,*,mode):
    if mode==0o644:return _checked_read_live(path,uid)
    return _checked_read_strict(path,uid,mode=mode)

'''
assert new.count('def publish_live(path,value):')==1
new=new.replace('def publish_live(path,value):',insert+'def publish_live(path,value):')
target=P/'dedicated_main_health_protocol_atomic_snapshot_v2.py';compile(new,str(target),'exec')
old_functions={n.name:n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef)}
new_functions={n.name:n for n in ast.parse(new).body if isinstance(n,ast.FunctionDef)}
equivalent=[]
for name,node in old_functions.items():
    selected=new_functions['_checked_read_strict'if name=='checked_read'else name]
    if name=='checked_read':selected.name='checked_read'
    assert ast.dump(node,include_attributes=False)==ast.dump(selected,include_attributes=False),name
    equivalent.append(name)
with target.open('xb')as f:f.write(new.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
D.mkdir(mode=0o700)
h.put(D/'source-and-reproduction-provenance.json',dict(schema='robotron-prospective-live-atomic-snapshot-reader-provenance-v1',original_protocol=h.pin(original),prospective_protocol=h.pin(target),original_race_reproduction=h.pin(proof),
    original_functions_AST_identical=equivalent,strict_reader_only_renamed=True,immutable_finish_dispatch_unchanged=True,live_payload_and_validation_unchanged=True,
    no_read_retry_or_sample_reordering=True,production_source_changed=False,selected_for_scientific_case=False,quality_qualified=False))
print(h.pin(target)['sha256'])
