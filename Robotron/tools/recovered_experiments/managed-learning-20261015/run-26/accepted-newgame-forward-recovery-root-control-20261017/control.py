"""Root-only retained invocation observer. Never retries a payload."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path

ROOT=Path('/home/dave/source/repos/ArcadeAI')
def pin(path):
    p=Path(path); b=p.read_bytes(); s=p.stat()
    return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(s.st_mode&0o777),uid=s.st_uid,nlink=s.st_nlink))
def publish(path,value):
    p=Path(path)
    with p.open('x') as f:
        json.dump(value,f,indent=2,allow_nan=False); f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return pin(p)
def command(out,label,argv):
    r=subprocess.run(argv,capture_output=True,timeout=40)
    files={}
    for kind,data in [('stdout',r.stdout),('stderr',r.stderr)]:
        p=out/(label+'-'+kind+'.txt')
        with p.open('xb') as f:f.write(data);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        files[kind]=pin(p)
    receipt=dict(argv=argv,exit=r.returncode,unix_s=time.time(),**files)
    publish(out/(label+'-command.json'),receipt)
    return r,receipt
def show(unit):
    r=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=20)
    return dict(x.split('=',1) for x in r.stdout.splitlines() if '=' in x)
def launch(config):
    c=json.loads(Path(config).read_text());out=Path(c['output']);out.mkdir(mode=0o700);(out/'tmp').mkdir(mode=0o700)
    unit=c['unit'];timer=unit.removesuffix('.service')+'.timer'
    assert show(unit).get('LoadState')=='not-found' and show(timer).get('LoadState')=='not-found'
    for p in c['pins']:assert pin(p['path'])==p
    props=['Type=exec','RemainAfterExit=yes','Restart=no','WorkingDirectory='+str(ROOT),'StandardOutput=append:'+str(out/'stdout.txt'),'StandardError=append:'+str(out/'stderr.txt')]+c['properties']
    argv=['systemd-run','--user','--unit='+unit,'--on-active=3s','--timer-property=AccuracySec=100ms']+['--property='+p for p in props]+['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(out/'tmp')]+c['argv']
    intent=publish(out/'root-launch-intent.json',dict(**c,actual_argv=argv,timer=timer,no_retry=True,original_attempt=1))
    r,receipt=command(out,'root-scheduling-carrier',argv);assert r.returncode==0
    command(out,'original-launch-timer-cat',['systemctl','--user','cat',timer]);command(out,'original-launch-timer-show',['systemctl','--user','show',timer])
    print(json.dumps(dict(scheduled=True,unit=unit,intent=intent)),flush=True)

def observe(config):
    c=json.loads(Path(config).read_text());out=Path(c['output']);unit=c['unit'];timer=unit.removesuffix('.service')+'.timer'
    identity=None;deadline=time.monotonic()+c.get('observation_s',1800)
    while time.monotonic()<deadline:
        s=show(unit);pid=int(s.get('MainPID','0'))
        if identity is None and pid:
            raw=Path('/proc')/str(pid)/'stat';b=raw.read_text();start=int(b[b.rfind(')')+2:].split()[19])
            identity=dict(pid=pid,starttime_ticks=start,invocation_id=s['InvocationID'],unit=unit,timer=timer,timer_invocation_id=show(timer).get('InvocationID'),observed_live=True)
            publish(out/'root-original-identity.json',identity);command(out,'original-first-observed-show',['systemctl','--user','show',unit]);print(json.dumps(identity),flush=True)
        if identity is not None:
            assert s.get('InvocationID')==identity['invocation_id'] and s.get('NRestarts')=='0'
        if s.get('ExecMainCode')=='1' and s.get('SubState') in ('exited','dead','failed'):
            assert identity is not None,'Live original identity missed'
            break
        time.sleep(.1 if identity is None else 2)
    else:raise RuntimeError('Observational deadline: payload left untouched')
    archive=[]
    for kind,u in [('service',unit),('timer',timer)]:
        for action in ('show','cat','journal'):
            args=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+identity['invocation_id' if kind=='service' else 'timer_invocation_id']] if action=='journal' else ['systemctl','--user',action,u]
            _,r=command(out,'original-'+kind+'-'+action,args);archive.append(r)
    original=show(unit);assert original.get('InvocationID')==identity['invocation_id'] and original.get('NRestarts')=='0'
    result=dict(schema='robotron-root-retained-original-result-and-release-v1',original=identity,original_exec_code=int(original['ExecMainCode']),original_exit=int(original['ExecMainStatus']),original_result=original['Result'],full_original_archives=archive,original_archived_before_release=True)
    publish(out/'root-original-terminal-archive.json',result)
    release=[]
    for kind,u in [('timer',timer),('service',unit)]:
        r,record=command(out,'release-'+kind+'-stop',['systemctl','--user','stop',u]);assert r.returncode==0
        st=show(u)
        if st.get('LoadState')!='not-found':
            r,_=command(out,'release-'+kind+'-reset-failed',['systemctl','--user','reset-failed',u]);assert r.returncode==0
        _,final=command(out,'release-'+kind+'-final-show',['systemctl','--user','show',u]);assert show(u).get('LoadState')=='not-found'
        release.append(dict(unit=u,stop=record,final=final))
    result.update(owned_release=release,unit_released=True)
    if c.get('expected_tests'):
        text=(out/'stderr.txt').read_text();assert ('Ran %s tests'%c['expected_tests']) in text and '\nOK\n' in text and 'skipped=' not in text
        result.update(tests_run=c['expected_tests'],tests_passed=c['expected_tests'],tests_skipped=0)
    if c.get('result_path'):result['payload_result']=pin(c['result_path'])
    publish(out/'root-original-result-and-owned-release.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('full_original_archives','owned_release')}),flush=True)

if __name__=='__main__':
    {'launch':launch,'observe':observe}[sys.argv[1]](sys.argv[2])
