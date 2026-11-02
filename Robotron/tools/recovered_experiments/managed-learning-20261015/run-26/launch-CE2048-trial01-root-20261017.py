"""Root-only retained-unit scheduling for the one immutable CE2048 trial."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPO=Path('/home/dave/source/repos/ArcadeAI')
RUN=REPO/'Robotron/logs/managed-learning-20261015/run-26'
PREP=RUN/'CE2048-trial01-final-root-preparation-20261017'
EXEC=RUN/'CE2048-trial01-root-execution-20261017'
UNITS=dict(deadline='robotron-ce2048-trial01-deadline-20261017.service',controller='robotron-ce2048-trial01-controller-20261017.service')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
def call(argv):return subprocess.run(argv,capture_output=True,text=True,timeout=20)
def show(unit):
    result=call(['systemctl','--user','show',unit])
    fields=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    assert result.returncode==0 or fields.get('LoadState')=='not-found',result.stderr
    return fields,result.stdout
def start_ticks(pid):
    return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])

def launch(kind,job_sha):
    jobpath=PREP/'one-trial-job-FINAL.json';assert sha(jobpath)==job_sha
    job=json.loads(jobpath.read_text());src=job['sources'][kind]
    assert sha(Path(src['path']))==src['sha256']
    unit=UNITS[kind];timer=unit.removesuffix('.service')+'.timer'
    assert all(show(name)[0]['LoadState']=='not-found' for name in (unit,timer))
    if kind=='deadline':EXEC.mkdir(mode=0o700)
    out=EXEC/kind;out.mkdir(mode=0o700);(out/'tmp').mkdir()
    command=['/usr/bin/python3.12','-I','-B','-u',src['path'],'--execute','--job',str(jobpath),'--expected-job-sha256',job_sha]
    armed=None
    if kind=='deadline':
        command+=['--expected-source-sha256',src['sha256']]
    else:
        armed_path=Path(job['output_directory'])/'deadline-armed.json';armed=json.loads(armed_path.read_text())
        fields,_=show(UNITS['deadline'])
        assert fields['MainPID']==str(armed['pid']) and start_ticks(armed['pid'])==armed['starttime_ticks']
        assert fields['ActiveState']=='active' and fields['NRestarts']=='0'
        assert sha(jobpath)==armed['job']['sha256'] and armed['source']==job['sources']['deadline']
        assert not (armed_path.parent/'deadline-result.json').exists()
        command+=['--expected-controller-sha256',src['sha256'],'--expected-armed-sha256',sha(armed_path)]
    limits=(['--property=CPUQuota=100%','--property=MemoryMax=256M','--property=TasksMax=32','--property=RuntimeMaxSec=6000']
        if kind=='deadline' else ['--property=CPUQuota=200%','--property=MemoryMax=4G','--property=TasksMax=128','--property=RuntimeMaxSec=7200','--property=KillSignal=SIGINT','--property=TimeoutStopSec=900','--property=SendSIGKILL=no'])
    argv=['systemd-run','--user','--unit='+unit,'--property=Type=exec','--property=RemainAfterExit=yes','--property=Restart=no',
        '--property=MemorySwapMax=0','--property=WorkingDirectory='+str(REPO),
        '--property=StandardOutput=append:'+str(out/'stdout.txt'),'--property=StandardError=append:'+str(out/'stderr.txt'),
        *limits,'--on-active=3s','--timer-property=AccuracySec=100ms',
        '/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1',
        'OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','MKL_NUM_THREADS=2','NUMEXPR_NUM_THREADS=2','TMPDIR='+str(out/'tmp'),*command]
    save(out/'root-launch-intent.json',dict(kind=kind,unit=unit,argv=argv,job_sha256=job_sha,
        source=src,armed=armed,root_runner_sha256=sha(Path(__file__)),requested_monotonic_s=time.monotonic()))
    result=call(argv);save(out/'root-scheduling-carrier-return.json',dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
    assert result.returncode==0,result.stderr
    print(json.dumps(dict(status='SCHEDULED',kind=kind,unit=unit,directory=str(out))))

def inspect(kind):
    out=EXEC/kind;fields,text=show(UNITS[kind]);pid=int(fields.get('MainPID','0'))
    actual=dict(unit=UNITS[kind],pid=pid,original_pid=int(fields['ExecMainPID']),invocation=fields['InvocationID'],
        starttime_ticks=None if not pid else start_ticks(pid),active=fields['ActiveState'],sub=fields['SubState'],
        nrestarts=fields['NRestarts'],result=fields['Result'])
    save(out/('root-observed-identity-'+str(time.monotonic_ns())+'.json'),actual)
    print(json.dumps(actual))

if __name__=='__main__':
    if sys.argv[1]=='launch':launch(sys.argv[2],sys.argv[3])
    elif sys.argv[1]=='inspect':inspect(sys.argv[2])
    else:raise SystemExit('launch KIND JOB_SHA or inspect KIND')
