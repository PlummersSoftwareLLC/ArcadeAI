"""Repeat only the registered read-only observer; never launch/restart a study."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time

OUT=Path(__file__).resolve().parent
Q=OUT.parent
REG=Q/'root-live-monitor-registration.json'
assert hashlib.sha256(REG.read_bytes()).hexdigest()=='40cb1f8f51ebab5519728e87edbb34dbd38a41fdb7146ac663b5832033ded5eb'
command=json.loads(REG.read_bytes())['command']
assert '--observe' in command and '--prepare' not in command

def publish(path,raw):
    with path.open('xb') as f:
        f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    s=path.stat()
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
        identity=dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
                      ctime_ns=s.st_ctime_ns,mode=oct(s.st_mode&0o7777),uid=s.st_uid,nlink=s.st_nlink))

observations=[]
draining=[]
status='OBSERVATION_LIMIT_NO_TERMINAL_INFERENCE'
for number in range(8):
    before=time.time()
    child=subprocess.run(command,capture_output=True)
    after=time.time()
    stdout=publish(OUT/f'{number:02d}-observer-stdout.bin',child.stdout)
    stderr=publish(OUT/f'{number:02d}-observer-stderr.bin',child.stderr)
    record=dict(index=number,before_unix_s=before,after_unix_s=after,
                returncode=child.returncode,stdout=stdout,stderr=stderr)
    if child.returncode!=0:
        observations.append(record)
        status='OBSERVER_FAILURE_RETAINED_ORIGINAL_STUDY_NOT_RESTARTED'
        break
    value=json.loads(child.stdout)
    assert value['classification']=='LIVE_SUPERVISED_QUALITY32_PREFIX_VERIFIED'
    assert value['current_leg']==2 and len(value['original_owners'])==2
    assert all(x['live'] is True for x in value['original_owners'])
    leg=next(x for x in value['legs'] if x['index']==2)
    assert leg['live_actor_births_verified']==32 and value['main']['client_count']==192
    record.update(report=value['receipt'],phase=leg['phase'],counts=leg['counts'])
    observations.append(record)
    print(json.dumps(dict(index=number,phase=leg['phase'],counts=leg['counts'],report=value['receipt']['path'])),flush=True)
    if leg['phase']=='draining':
        draining.append(record)
        if len(draining)>=2:
            assert len({x['counts']['started'] for x in draining})==1
            assert all(x['counts']['abandoned']==0 for x in draining)
            status='C1_ADMISSION_CLOSED_TWO_DRAINING_OBSERVATIONS_FIXED_STARTS'
            break
    else:
        assert leg['phase']=='collecting'
    time.sleep(10)
result=dict(status=status,observations=observations,draining_observations=len(draining),
    original_study_restarted=False,current_cohort_altered=False,scientific_review_rerun=False,
    quality_qualified=False,learning_speed_gain_verified=False)
entry=publish(OUT/'original-C1-close-watch-result.json',
              (json.dumps(result,indent=2,allow_nan=False)+'\n').encode())
print(json.dumps(dict(status=status,readback=entry)),flush=True)
