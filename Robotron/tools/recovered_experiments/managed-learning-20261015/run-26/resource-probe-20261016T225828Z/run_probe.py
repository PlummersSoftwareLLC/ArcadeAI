"""Launch exactly one bounded user resource probe; never retry its config."""
import hashlib,json,os,subprocess,time
from pathlib import Path

OUT=Path(__file__).resolve().parent
UNIT='robotron-snapshot-smoke-resource-probe-20261016T225828Z.service'
EXPECTED={2410677:26962745,2689385:27786562,2863595:28203928}

def save(name,value):
    with (OUT/name).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')

def protected():
    result=[]
    for pid,ticks in EXPECTED.items():
        p=Path('/proc')/str(pid);parts=(p/'stat').read_text().rsplit(') ',1)[1].split();actual=int(parts[19])
        if actual!=ticks:raise RuntimeError('Protected identity changed: '+str(pid))
        result.append(dict(pid=pid,start_ticks=actual,cgroup=(p/'cgroup').read_text().strip(),cmdline=(p/'cmdline').read_bytes().decode().split('\0')))
    return result

def show():
    keys=('Id','MainPID','ExecMainPID','ControlGroup','ActiveState','SubState','Result','Delegate','DelegateControllers','DelegateSubgroup','RuntimeMaxUSec','KillMode','KillSignal','MemoryMax','MemorySwapMax','TasksMax','CPUQuotaPerSecUSec','CPUQuotaPeriodUSec','Restart')
    r=subprocess.run(['systemctl','--user','show',UNIT,*['--property='+key for key in keys]],capture_output=True,text=True,timeout=5)
    return dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)

before=protected();save('protected-before.json',before)
properties=('Type=exec','Delegate=cpu memory pids','DelegateSubgroup=snapshot-supervisor','RuntimeMaxSec=40s','KillMode=control-group','TimeoutStopSec=5s','MemoryMax=268435456','MemorySwapMax=0','TasksMax=32','CPUQuota=100%','Restart=no','StandardOutput=append:'+str(OUT/'service.log'),'StandardError=append:'+str(OUT/'service.log'))
command=['systemd-run','--user','--unit='+UNIT,*['--property='+p for p in properties],'--','/usr/bin/python3','-I','-B',str(OUT/'probe.py')]
save('launch-manifest.json',dict(unit=UNIT,command=command,one_attempt=True,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'probe.py',OUT/'run_probe.py',Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/coherent_snapshot_proposal/whole_agent_smoke.py'))}))
launched=False
try:
    r=subprocess.run(command,capture_output=True,text=True,timeout=10);save('systemd-run.json',dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));launched=r.returncode==0
    if not launched:raise RuntimeError('Dedicated unit launch refused; no retry or relaxed fallback')
    deadline=time.monotonic()+15
    while not (OUT/'attached.json').exists() and not (OUT/'result.json').exists():
        if time.monotonic()>=deadline:raise TimeoutError('Dedicated cgroup probe did not reach attachment')
        time.sleep(.05)
    save('unit-attached.json',show())
    with (OUT/'release.flag').open('x') as stream:stream.write('outer properties recorded\n')
    deadline=time.monotonic()+15
    while not (OUT/'result.json').exists():
        if time.monotonic()>=deadline:raise TimeoutError('Dedicated probe did not finish')
        time.sleep(.05)
    result=json.loads((OUT/'result.json').read_text());save('unit-final.json',show())
    print(json.dumps(dict(unit=UNIT,status=result['status'],effective_caps=result.get('effective_caps'),cleanup=result['cleanup'],errors=result['errors']),indent=2))
except BaseException as error:
    save('driver-error.json',dict(type=type(error).__name__,message=str(error),unit_state=show()))
    raise
finally:
    after=protected();save('protected-after.json',after)
    if after!=before:raise RuntimeError('Protected process/cgroup bindings changed')
    # Only this exact unique service may be stopped during fault cleanup.
    if launched:
        deadline=time.monotonic()+3
        state=show()
        while 'ActiveState=active\n' in state['stdout'] and time.monotonic()<deadline:
            time.sleep(.05);state=show()
        if 'ActiveState=active\n' in state['stdout']:
            r=subprocess.run(['systemctl','--user','stop',UNIT],capture_output=True,text=True,timeout=8)
            save('owned-unit-cleanup.json',dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='artifact-sha256.json'}
    save('artifact-sha256.json',files)
