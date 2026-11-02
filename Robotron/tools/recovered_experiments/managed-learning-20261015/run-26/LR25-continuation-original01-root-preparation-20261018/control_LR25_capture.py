"""Root LR25 original01 capture control derived from b5a5.
Only the explicit resource/config gate and docstring change. All lifecycle functions unchanged.
No execution or learning efficacy claim.
"""
import argparse,hashlib,json,os,re,subprocess,sys,time
from pathlib import Path

ROOT=Path('/home/dave/source/repos/ArcadeAI')
_LAUNCHES={}

def require(condition,message):
    if not condition:raise ValueError(message)

def pin(path):
    p=Path(path); b=p.read_bytes(); s=p.stat()
    return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(s.st_mode&0o777),uid=s.st_uid,nlink=s.st_nlink))

def publish(path,value):
    p=Path(path)
    with p.open('x') as f:
        json.dump(value,f,indent=2,allow_nan=False); f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return pin(p)

def command(out,label,argv):
    started=time.time();failure=None
    try:
        r=subprocess.run(argv,capture_output=True,timeout=40)
        stdout,stderr,exit_code=r.stdout,r.stderr,r.returncode
    except subprocess.TimeoutExpired as error:
        stdout,stderr,exit_code=error.stdout or b'',error.stderr or b'',None
        failure='TimeoutExpired: command completion unknown; no success inferred'
    files={}
    for kind,data in [('stdout',stdout),('stderr',stderr)]:
        p=out/(label+'-'+kind+'.txt')
        with p.open('xb') as f:f.write(data);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        files[kind]=pin(p)
    receipt=dict(argv=argv,exit=exit_code,unix_s=time.time(),started_unix_s=started,
                 timed_out=failure is not None,error=failure,**files)
    publish(out/(label+'-command.json'),receipt)
    return receipt

def fields(record):
    require(record['exit']==0 and not record['timed_out'],'Show command did not complete successfully')
    return dict(x.split('=',1) for x in Path(record['stdout']['path']).read_text().splitlines() if '=' in x)

def show(unit):
    r=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=20)
    require(r.returncode==0,'Original unit observation failed')
    return dict(x.split('=',1) for x in r.stdout.splitlines() if '=' in x)

def checked_config(config):
    c=json.loads(Path(config).read_text())
    require(set(c)=={'unit','output','argv','properties','pins','observation_s'},'Exact six-field LR25 capture config required')
    require(c['unit']=='robotron-LR25-continuation-capture-original01-20261018.service','Only unique original01 LR25 capture unit authorized')
    props=dict(x.split('=',1) for x in c['properties'])
    require(len(props)==len(c['properties']) and props==dict(CPUQuota='200%',MemoryMax='3G',RuntimeMaxSec='3900',
        MemorySwapMax='0',TasksMax='128',TimeoutStopSec='5'),'Exact LR25 capture caps required')
    require(type(c['observation_s']) is int and c['observation_s']==3960,'Exact bounded LR25 capture observation required')
    require(isinstance(c['argv'],list) and c['argv'] and all(isinstance(x,str) for x in c['argv']),'Explicit selected capture argv required')
    return c

def timer_state(s,context):
    require(s.get('Id')==context['timer'],'Queried timer ID differs')
    if s.get('LoadState')=='not-found':return 'absent'
    require(s.get('LoadState')=='loaded' and s.get('InvocationID')==context['timer_invocation_id'] and
            s.get('Unit')==context['unit'],'Unknown or replaced timer; no action authorized')
    return 'original_loaded'

def original_terminal(s,identity):
    require(s.get('Id')==identity['unit'] and s.get('InvocationID')==identity['invocation_id'] and
        s.get('NRestarts')=='0' and s.get('MainPID')=='0' and
        s.get('ExecMainPID')==str(identity['pid']) and s.get('ExecMainCode')=='1' and
        s.get('SubState') in ('exited','dead','failed'),'Original terminal service identity differs')
    require(re.fullmatch(r'\d+',s.get('ExecMainStatus','')) is not None,
            'Original audit exit is unavailable')

def launch(config):
    c=checked_config(config);key=str(Path(config).resolve())
    require(key not in _LAUNCHES,'One scheduling attempt only in this process')
    _LAUNCHES[key]=dict(attempted=True,ready=False)
    out=Path(c['output']);out.mkdir(mode=0o700);(out/'tmp').mkdir(mode=0o700)
    unit=c['unit'];timer=unit.removesuffix('.service')+'.timer'
    try:
        require(show(unit).get('LoadState')=='not-found' and show(timer).get('LoadState')=='not-found',
                'Both exact future unit names must be absent')
        for p in c['pins']:require(pin(p['path'])==p,'A selected source/metadata PIN changed')
        props=['Type=exec','RemainAfterExit=yes','Restart=no','WorkingDirectory='+str(ROOT),
            'StandardOutput=append:'+str(out/'stdout.txt'),'StandardError=append:'+str(out/'stderr.txt')]+c['properties']
        argv=['systemd-run','--user','--unit='+unit,'--on-active=3s','--timer-property=AccuracySec=100ms']+['--property='+p for p in props]+['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(out/'tmp')]+c['argv']
        intent=publish(out/'root-launch-intent.json',dict(**c,actual_argv=argv,timer=timer,no_retry=True,original_attempt=1))
        scheduled=command(out,'root-scheduling-carrier',argv)
        require(scheduled['exit']==0,'Scheduling carrier failed or timed out; never retry')
        cat=command(out,'original-launch-timer-cat',['systemctl','--user','cat',timer])
        shown=command(out,'original-launch-timer-show',['systemctl','--user','show',timer]);s=fields(shown)
        context=dict(unit=unit,timer=timer,timer_invocation_id=s.get('InvocationID'))
        require(re.fullmatch(r'[0-9a-f]{32}',context['timer_invocation_id'] or '') is not None,
                'Launch-time original timer invocation was not captured')
        require(cat['exit']==0 and timer_state(s,context)=='original_loaded',
                'Successful exact launch-time timer cat/show required')
        cat_text=Path(cat['stdout']['path']).read_text()
        cat_units=[];timer_headers=0;in_timer=False
        for line in cat_text.splitlines():
            line=line.strip()
            if not line or line.startswith(('#',';')):continue
            if line.startswith('['):
                in_timer=line=='[Timer]';timer_headers+=int(in_timer)
            if re.match(r'Unit\s*=',line):cat_units.append((in_timer,line))
        require(timer_headers==1 and (not cat_units or cat_units==[(True,'Unit='+unit)]),
                'Launch-time timer cat target is malformed, duplicate or foreign')
        archive=dict(schema='robotron-root-exact-audit-timer-launch-archive-v1',**context,
            launch_intent=intent,scheduling_carrier=scheduled,timer_cat=cat,timer_show=shown,
            original_attempt=1,no_retry=True)
        archived=publish(out/'root-original-timer-launch-archive.json',archive)
        _LAUNCHES[key]=dict(ready=True,config=pin(config),context=context,launch_archive=archived)
        print(json.dumps(dict(scheduled=True,unit=unit,intent=intent,timer_launch_archive=archived)),flush=True)
    except Exception as error:
        publish(out/'root-launch-error-preserved.json',dict(status='UNRELEASED_NO_RETRY',
            error=repr(error),original_attempt=1,unit=unit,timer=timer,
            unknown_units_stopped=False,payload_retried=False))
        raise

def release_original(out,kind,identity,context,record):
    unit=identity['unit'] if kind=='service' else context['timer']
    record.update(unit=unit,stop=None,reset_failed=None,confirmed_absent=False)
    before=command(out,'release-'+kind+'-before-show',['systemctl','--user','show',unit])
    record['before']=before;s=fields(before)
    state=timer_state(s,context) if kind=='timer' else ('absent' if s.get('LoadState')=='not-found' else 'original_loaded')
    if kind=='service':
        require(s.get('Id')==unit,'Queried service ID differs')
        if state!='absent':original_terminal(s,identity)
    if state=='absent':
        record.update(classification='already_absent_with_original_launch_and_terminal_evidence',
                      confirmed_absent=True,final=before)
        return record
    stopped=command(out,'release-'+kind+'-stop',['systemctl','--user','stop',unit]);record['stop']=stopped
    after=command(out,'release-'+kind+'-after-stop-show',['systemctl','--user','show',unit]);record['after_stop']=after;s=fields(after)
    state=timer_state(s,context) if kind=='timer' else ('absent' if s.get('LoadState')=='not-found' else 'original_loaded')
    if kind=='service':
        require(s.get('Id')==unit,'Queried service ID differs')
        if state!='absent':original_terminal(s,identity)
    if state=='absent':
        if stopped['exit']!=0:
            data=Path(stopped['stderr']['path']).read_bytes()
            require(kind=='timer' and stopped['exit']==5 and
                len(data)==stopped['stderr']['bytes'] and
                hashlib.sha256(data).hexdigest()==stopped['stderr']['sha256'] and
                data.decode().strip() in {f'Unit {unit} not loaded.',
                    f'Failed to stop {unit}: Unit {unit} not loaded.'},
                'Unexpected stop failure retained; no exact owned timer-GC reason')
        record.update(classification='owned_stop_completed' if stopped['exit']==0 else
            'timer_autoGC_race_stop5_preserved',confirmed_absent=True,final=after)
        return record
    require(stopped['exit']==0,'Owned stop failed; unit remains and no reset authorized')
    require(s.get('ActiveState')=='failed','Original unit still present without an exact failed state')
    reset=command(out,'release-'+kind+'-reset-failed',['systemctl','--user','reset-failed',unit]);record['reset_failed']=reset
    final=command(out,'release-'+kind+'-final-show',['systemctl','--user','show',unit]);record['final']=final
    require(reset['exit']==0 and fields(final).get('Id')==unit and fields(final).get('LoadState')=='not-found',
            'Exact original reset/absence was not confirmed')
    record.update(classification='owned_stop_and_original_failed_state_reset',confirmed_absent=True)
    return record

def observe(config):
    c=checked_config(config);key=str(Path(config).resolve());out=Path(c['output'])
    launch_record=_LAUNCHES.get(key)
    require(launch_record and launch_record.get('ready') and launch_record['config']==pin(config),
            'Observe only this process\'s authenticated one launch, with unchanged config')
    require(not launch_record.get('observation_started'),'One observation only; no cleanup retry/adoption')
    launch_record['observation_started']=True
    require(pin(launch_record['launch_archive']['path'])==launch_record['launch_archive'],
            'Original launch timer archive changed')
    context=launch_record['context'];unit=context['unit'];timer=context['timer']
    result=dict(schema='robotron-root-audit-original-result-and-GC-aware-owned-release-v1',
        original=None,original_exec_code=None,original_exit=None,original_result=None,
        timer_launch_archive=launch_record['launch_archive'],full_original_archives=[],
        original_archive_status=[],all_six_original_archive_commands_succeeded=False,
        original_archived_before_release=False,owned_release=[],unit_released=False,
        lifecycle_complete=False,audit_success=None,payload_retried=False,error=None)
    identity=None;deadline=time.monotonic()+c['observation_s']
    try:
        while time.monotonic()<deadline:
            s=show(unit);pid=int(s.get('MainPID','0'))
            if identity is None and pid:
                raw=(Path('/proc')/str(pid)/'stat').read_text();start=int(raw[raw.rfind(')')+2:].split()[19])
                again=show(unit)
                require(s.get('Id')==unit and s.get('NRestarts')=='0' and
                    re.fullmatch(r'[0-9a-f]{32}',s.get('InvocationID','')) is not None and
                    again.get('MainPID')==str(pid) and again.get('InvocationID')==s.get('InvocationID') and
                    again.get('NRestarts')=='0','Original live identity was not bracketed')
                identity=dict(pid=pid,starttime_ticks=start,invocation_id=s['InvocationID'],unit=unit,
                    timer=timer,timer_invocation_id=context['timer_invocation_id'],observed_live=True)
                result['original']=identity
                publish(out/'root-original-identity.json',identity)
                command(out,'original-first-observed-show',['systemctl','--user','show',unit])
            if identity is not None:
                require(s.get('Id')==unit and s.get('InvocationID')==identity['invocation_id'] and
                    s.get('NRestarts')=='0' and pid in (0,identity['pid']),'Original service changed; leave untouched')
            if s.get('ExecMainCode')=='1' and s.get('SubState') in ('exited','dead','failed'):
                require(identity is not None,'Original live identity missed; no retrospective adoption')
                original_terminal(s,identity);break
            time.sleep(.01 if identity is None else 2)
        else:raise RuntimeError('Observational deadline: original left untouched')
        result.update(original_exec_code=1,original_exit=int(s['ExecMainStatus']),
            original_result=s['Result'],audit_success=int(s['ExecMainStatus'])==0)
        for kind,u in [('service',unit),('timer',timer)]:
            for action in ('show','cat','journal'):
                argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+identity['invocation_id' if kind=='service' else 'timer_invocation_id']] if action=='journal' else ['systemctl','--user',action,u]
                r=command(out,'original-'+kind+'-'+action,argv)
                result['full_original_archives'].append(r)
                result['original_archive_status'].append(dict(kind=kind,action=action,
                    exit=r['exit'],timed_out=r['timed_out']))
        archives=result['full_original_archives'];original_terminal(fields(archives[0]),identity)
        archived_timer_state=timer_state(fields(archives[3]),context)
        result.update(original_archived_before_release=True,
            all_six_original_archive_commands_succeeded=all(r['exit']==0 for r in archives),
            terminal_timer_state=archived_timer_state)
        publish(out/'root-original-terminal-archive.json',result)
        require(all(r['exit']==0 for r in archives[:3]) and archives[5]['exit']==0 and
            archives[4]['exit'] in (0,1),'Unexpected archive command failure; preserve and leave untouched')
        # A failed terminal cat is not a success: require a fresh absence read
        # and the exact launch identity before permitting the timer-GC exception.
        if archives[4]['exit']!=0:
            r=command(out,'original-timer-GC-confirm-show',['systemctl','--user','show',timer])
            result['timer_GC_confirmation']=r
            require(timer_state(fields(r),context)=='absent','Timer cat failed while timer remains; no release')
        original_terminal(show(unit),identity)
        for kind in ('timer','service'):
            record={};result['owned_release'].append(record)
            release_original(out,kind,identity,context,record)
        require(all(r['confirmed_absent'] for r in result['owned_release']),
                'Both exact original units must be confirmed absent')
        result.update(unit_released=True,lifecycle_complete=True,
            status='ORIGINAL_AUDIT_EXIT0_ARCHIVED_AND_RELEASED' if result['original_exit']==0 else
                   'ORIGINAL_AUDIT_NONZERO_PRESERVED_ARCHIVED_AND_RELEASED')
    except Exception as error:
        result.update(status='ORIGINAL_OUTCOME_PRESERVED_OWNED_RELEASE_INCOMPLETE',error=repr(error))
    result['ended_unix_s']=time.time()
    result_pin=publish(out/'root-original-result-and-owned-release.json',result)
    print(json.dumps(dict(status=result['status'],original_exit=result['original_exit'],
        unit_released=result['unit_released'],receipt=result_pin)),flush=True)
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true');p.add_argument('--config');p.add_argument('--expected-source-sha256')
    args=p.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no configuration/source reads, unit queries, payload, outputs or actions');return 0
    require(args.config and args.expected_source_sha256 and
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,
        'Explicit root config and exact selected source SHA required')
    launch(args.config);result=observe(args.config)
    if result['original_exit'] not in (None,0):return result['original_exit']
    return 0 if result['lifecycle_complete'] else 1

if __name__=='__main__':sys.exit(main())
