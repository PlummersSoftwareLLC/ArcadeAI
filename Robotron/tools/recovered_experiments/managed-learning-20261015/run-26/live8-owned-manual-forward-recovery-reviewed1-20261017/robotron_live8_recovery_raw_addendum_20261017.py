#!/usr/bin/env python3
import hashlib,json,os,stat,subprocess,datetime
from pathlib import Path
REPO=Path('/home/dave/source/repos/ArcadeAI');GAME=REPO/'Robotron';RUN=GAME/'logs/managed-learning-20261015/run-26';D=RUN/'live8-owned-manual-forward-recovery-reviewed1-20261017'
def start(pid):return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
def main():
    h=json.loads((D/'root-normal-recovery-health-PASS.json').read_text());owner=h['owner'];assert start(owner['pid'])==owner['starttime_ticks']
    records=[]
    for actor in h['current_binding']['bindings']['actors']:
        assert start(actor['pid'])==actor['starttime_ticks'];mask=sorted(os.sched_getaffinity(actor['pid']));assert start(actor['pid'])==actor['starttime_ticks'];assert mask==list(range(72));records.append(dict(pid=actor['pid'],starttime_ticks=actor['starttime_ticks'],mask=mask,cgroup=Path('/proc',str(actor['pid']),'cgroup').read_text().strip()))
    worker=h['current_binding']['bindings']['worker'];tid=worker['thread']['tid'];thread_stat=Path('/proc',str(owner['pid']),'task',str(tid),'stat');assert int(thread_stat.read_text().rsplit(')',1)[1].split()[19])==worker['thread']['starttime_ticks'];w=sorted(os.sched_getaffinity(tid));assert w==list(range(72));assert int(thread_stat.read_text().rsplit(')',1)[1].split()[19])==worker['thread']['starttime_ticks']
    maps=Path('/proc',str(owner['pid']),'maps').read_bytes();assert len(maps)<8<<20 and start(owner['pid'])==owner['starttime_ticks'];q=D/'actual-new-trainer-proc-maps.txt'
    with q.open('xb') as f:f.write(maps);f.flush();os.fchmod(f.fileno(),0o444)
    model=GAME/'models_dqn/managed-incumbents/fresh3-384M-confirmed.pt';before=model.stat();digest=hashlib.sha256()
    with model.open('rb') as stream:
        assert os.fstat(stream.fileno())==before
        for chunk in iter(lambda:stream.read(4<<20),b''):digest.update(chunk)
        after=os.fstat(stream.fileno());assert (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)==(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
    assert digest.hexdigest()=='ac8bc98038a7860f1682e66311fd48657361eaa8ec7aff1f44bd53cf84090963';assert stat.S_IMODE(before.st_mode)==0o444 and before.st_nlink==1
    report=dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),main=owner,actor_masks=records,inference_worker=dict(binding=worker,mask=w),raw_maps=dict(path=str(q),sha256=hashlib.sha256(maps).hexdigest(),bytes=len(maps)),protected_model=dict(path=str(model),sha256=digest.hexdigest(),bytes=before.st_size,device=before.st_dev,inode=before.st_ino,mode=oct(stat.S_IMODE(before.st_mode)),nlink=before.st_nlink),scope='Fresh read-only raw identity/mask/maps observations and protected-byte rehash after recovery; payload timestamps and RAM bank bytes not compared')
    with (D/'root-raw-health-and-protected-rehash-addendum.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444)
    with (D/Path(__file__).name).open('xb') as f:f.write(Path(__file__).read_bytes());f.flush();os.fchmod(f.fileno(),0o444)
    print(json.dumps(dict(status='PASS',actors=len(records),protected_SHA=digest.hexdigest(),raw_maps_bytes=len(maps))))
if __name__=='__main__':main()
