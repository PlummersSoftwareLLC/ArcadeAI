"""Root-only retained CPU execution of one sealed trial02 original-row audit."""
import argparse, datetime, hashlib, json, os, re, subprocess, time
from pathlib import Path

REPO = Path('/home/dave/source/repos/ArcadeAI')
RUN = REPO/'Robotron/logs/managed-learning-20261015/run-26'
FUTURE = RUN/'rawKL-trial02-quality-launch-and-startup-root-20261017/future-original-leg-audit-argv.json'
FUTURE_SHA = '1a305e4988fd494abf97f11f968352c2a24caae242bf8d55566fd1e165bc833b'
PLAN_SHA = 'b502625ed8e39f01fa57af1c9f9cc8283794aa14e351e2b9bc9ec1268b267ecf'
BINDING_SHA = '3b16c36da91c63fd4fb218f1fed3c1c5a5fe8caff73534d880aeaeccfe4c81fe'
AUDITOR_SHA = 'fad4437bfde6ad123c631e439b0f90b58e1cd5e5d05f7aaafabfcea728376d88'
QUALITY = 'robotron-quality-448M-vs-rawkl-trial02-first8M-20261017.service'
QUALITY_INV = '325ea02d8cde47869eb8340b3de73f69'

def require(value, message):
    if not value: raise RuntimeError(message)

def sha(path):
    path = Path(path); before = path.stat(); require(not path.is_symlink() and path.is_file(), 'Nonregular pin: '+str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''): h.update(block)
    after = path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) ==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'Pin changed while hashing')
    return h.hexdigest()

def load(path): return json.loads(Path(path).read_bytes())
def pin(path):
    p = Path(path); s = p.stat()
    return dict(path=str(p),sha256=sha(p),bytes=s.st_size,identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(s.st_mode & 0o777),uid=s.st_uid,nlink=s.st_nlink))

def save(path, value):
    data = value if isinstance(value,bytes) else (value.encode() if isinstance(value,str) else (json.dumps(value,indent=2,allow_nan=False)+'\n').encode())
    with Path(path).open('xb') as stream: stream.write(data); stream.flush(); os.fchmod(stream.fileno(),0o444); os.fsync(stream.fileno())
    fd = os.open(Path(path).parent,os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return pin(path)

def call(argv):
    p = subprocess.run(argv,capture_output=True,text=True,timeout=15)
    return dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)

def show(unit):
    raw = call(['systemctl','--user','show',unit,'--all'])
    fields = dict(line.split('=',1) for line in raw['stdout'].splitlines() if '=' in line)
    require(raw['returncode']==0 or fields.get('LoadState')=='not-found','Cannot inspect exact unit: '+unit)
    return fields,raw

def start(pid):
    try: return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError: return None

def names(leg):
    out=RUN/f'rawKL-trial02-quality-leg{leg:02d}-audit-root-execution-reviewed1-20261017'
    unit=f'robotron-rawkl-trial02-quality-leg{leg:02d}-audit-reviewed1-20261017.service'
    return out,unit,unit.removesuffix('.service')+'.timer'

def setup(leg):
    require(sha(FUTURE)==FUTURE_SHA,'Sealed four-command file changed'); future=load(FUTURE)
    require([x['leg'] for x in future['commands']]==[1,2,3,4],'Wrong leg command set')
    argv=future['commands'][leg-1]['argv']; planpath=Path(future['actual_plan']['path'])
    require(argv[:3]==['/usr/bin/python3.12','-I','-B'] and argv[argv.index('--leg')+1]==str(leg),'Wrong sealed command')
    require(argv[argv.index('--plan-sha256')+1]==PLAN_SHA and sha(planpath)==PLAN_SHA,'Actual materialized plan changed')
    require(argv[argv.index('--binding-job-sha256')+1]==BINDING_SHA and argv[argv.index('--source-sha256')+1]==AUDITOR_SHA,'Binding/source argument mismatch')
    binding=Path(argv[argv.index('--binding-job')+1]); require(sha(binding)==BINDING_SHA and sha(argv[3])==AUDITOR_SHA,'Binding/auditor changed')
    plan=load(planpath); cfg=load(binding); out,unit,timer=names(leg)
    require(plan['output_directory']==argv[argv.index('--campaign')+1]==cfg['campaign']['output_directory'],'Campaign mismatch')
    return argv,plan,cfg,out,unit,timer

def launch(leg):
    argv,plan,cfg,out,unit,timer=setup(leg); spec=plan['legs'][leg-1]; campaign=Path(plan['output_directory'])
    statusraw=(campaign/'status.json').read_bytes(); state=json.loads(statusraw); rows=[x for x in state['legs'] if x['index']==leg]
    require(state['plan_sha256']==PLAN_SHA and len(rows)==1,'Original status/plan differs'); record=rows[0]
    require(record['state']=='finished' and record['returncode']==0 and record['pid']>0 and record['role']==spec['role'],'Original selected evaluator not finished0')
    if leg==1: require(record['pid']==638126,'Original R1 evaluator replaced')
    quality,qualityraw=show(QUALITY)
    require(quality['ExecMainPID']=='638119' and quality['InvocationID']==QUALITY_INV and quality['NRestarts']=='0','Original campaign owner changed')
    receiptpath=Path(spec['receipt_path']); receipt=load(receiptpath); cohort=receipt.get('cohort',{})
    require(receipt['complete'] is True and receipt['active'] is False and receipt['valid'] is True and cohort.get('complete',True) is True,'Original full-tail receipt not complete/inactive/valid')
    require(receipt['pending']==receipt['abandoned']==0 and receipt['started']==receipt['count']==len(receipt['rows'])>=50 and {x['client_slot'] for x in receipt['rows']}==set(range(4096,4112)),'Missing original tails/slots')
    require(receipt['job']==spec['job'] and receipt['checkpoint_sha256']==plan['checkpoints'][spec['role']]['sha256'],'Original receipt job/checkpoint differs')
    pins={str(FUTURE):FUTURE_SHA,str(Path(__file__)):sha(__file__),argv[3]:AUDITOR_SHA}
    manifest=Path(argv[3]).with_name('preparation-manifest.json'); manifest_sha='c29dd888a0f8da751fc637290b77c441a549c6c320e2981a81e37782dbd6cf5b'
    require(sha(manifest)==manifest_sha,'Pinned auditor bundle manifest changed'); pins[str(manifest)]=manifest_sha
    for name,x in load(manifest)['files'].items(): pins[x['source']]=x['sha256']
    pins[argv[argv.index('--binding-job')+1]]=BINDING_SHA
    for group in ('evaluator_source_hashes','execution_source_hashes'):
        for path,digest in plan[group].items(): pins[str(Path(path) if Path(path).is_absolute() else REPO/'Robotron'/path)]=digest
    pins.update(cfg['runtime_anchor']['source_hashes']); pins.update(cfg['runtime_anchor']['control_hashes'])
    for evidence in cfg['evidence'].values(): pins[evidence['path']]=evidence['sha256']
    for checkpoint in plan['checkpoints'].values(): pins[checkpoint['source']]=checkpoint['sha256']; pins[checkpoint['snapshot']]=checkpoint['sha256']
    proof=load(cfg['evidence']['phase_cpu_report']['path']); pins[proof['verification_copy']['path']]=proof['verification_copy']['sha256']
    require(all(sha(path)==digest for path,digest in pins.items()),'Frozen source/checkpoint/evidence pin differs')
    require(not out.exists() and not Path(argv[argv.index('--output')+1]).exists() and all(show(x)[0].get('LoadState')=='not-found' for x in (unit,timer)),'New-only audit names required')
    out.mkdir(); (out/'tmp').mkdir(); save(out/'original-finished-leg.json',record); save(out/'original-receipt.json',receiptpath.read_bytes())
    save(out/'original-quality-show-command.json',qualityraw); save(out/'original-quality-show.txt',qualityraw['stdout']); save(out/'original-campaign-status.json',statusraw)
    command=['systemd-run','--user','--unit='+unit,'--on-active=3s','--timer-property=AccuracySec=100ms',
        '--property=Type=exec','--property=RemainAfterExit=yes','--property=Restart=no','--property=CPUQuota=200%',
        '--property=MemoryMax=512M','--property=MemorySwapMax=0','--property=TasksMax=64','--property=RuntimeMaxSec=60',
        '--property=TimeoutStopSec=5','--property=WorkingDirectory='+str(REPO),'--property=StandardOutput=append:'+str(out/'stdout.txt'),
        '--property=StandardError=append:'+str(out/'stderr.txt'),'/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH',
        'CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(out/'tmp'),*argv]
    save(out/'root-runner-source.py',Path(__file__).read_bytes()); save(out/'root-launch-intent.json',dict(unit=unit,timer=timer,argv=command,sealed_auditor_argv=argv,source_pins=pins,plan_sha256=PLAN_SHA,precondition_receipt=pin(out/'original-receipt.json'),precondition_status=pin(out/'original-campaign-status.json'),original_quality_show=pin(out/'original-quality-show.txt')))
    result=call(command); result.update(carrier_reaped_by_subprocess_run=True,returned_monotonic_ns=time.monotonic_ns()); save(out/'root-scheduling-carrier-return.json',result)
    require(result['returncode']==0,'Scheduling failed; preserve, do not retry')
    timerfields,timerraw=show(timer); require(timerfields.get('LoadState')=='loaded' and re.fullmatch('[0-9a-f]{32}',timerfields.get('InvocationID','')),'Original timer identity unavailable; preserve')
    save(out/'root-original-timer-observed-show.json',timerraw)
    until=time.monotonic()+6
    while True:
        fields,raw=show(unit)
        if int(fields.get('ExecMainPID','0'))>0: break
        require(time.monotonic()<until,'Original unit PID not observed; preserve, no relaunch'); time.sleep(.1)
    pid=int(fields['ExecMainPID']); require(fields['NRestarts']=='0' and re.fullmatch('[0-9a-f]{32}',fields['InvocationID']),'Invalid original audit identity')
    require(int(fields['ExecMainStartTimestampMonotonic'])*1000>result['returned_monotonic_ns'],'Audit started before carrier reaped')
    save(out/'root-original-observed-show.json',raw); save(out/'root-observed-original-identity.json',dict(pid=pid,starttime_ticks=start(pid),invocation_id=fields['InvocationID'],unit=unit,timer_invocation_id=timerfields['InvocationID'],launch_intent=pin(out/'root-launch-intent.json'),observed_live=fields['MainPID']==str(pid)))
    print(json.dumps(dict(status='SCHEDULED_ONCE',unit=unit,original_pid=pid,directory=str(out))))

def archive(leg):
    out,unit,timer=names(leg); identity=load(out/'root-observed-original-identity.json'); intent=load(out/'root-launch-intent.json'); argv=intent['sealed_auditor_argv']
    require(intent['unit']==unit and intent['timer']==timer and identity['unit']==unit and sha(out/'root-launch-intent.json')==identity['launch_intent']['sha256'],'Original launch intent/identity differs')
    def terminal():
        fields,raw=show(unit)
        require(fields['MainPID']=='0' and int(fields['ExecMainPID'])==identity['pid'] and fields['InvocationID']==identity['invocation_id'] and fields['NRestarts']=='0' and fields['SubState'] in ('exited','dead','failed'),'Original audit not terminal/same identity')
        return fields,raw
    fields,raw=terminal(); archive_pins={}; commands={}
    for label,target in [('timer',timer),('unit',unit)]:
        observed,shown=show(target) if label=='timer' else (fields,raw)
        require(label!='timer' or observed.get('LoadState')=='not-found' or observed.get('InvocationID')==identity['timer_invocation_id'],'Original timer replaced')
        for kind,data in [('show',shown),('cat',call(['systemctl','--user','cat',target]))]:
            commands[label+'_'+kind]=save(out/f'original-{label}-{kind}-command.json',data); archive_pins[label+'_'+kind]=save(out/f'original-{label}-{kind}.txt',data['stdout'])
            require(kind!='cat' or data['returncode']==0 or label=='timer' and observed.get('LoadState')=='not-found','Cannot archive full original cat')
    journal=call(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+identity['invocation_id'],'--no-pager','-o','short-iso-precise'])
    commands['journal']=save(out/'original-invocation-journal-command.json',journal); archive_pins['journal']=save(out/'original-invocation-journal.txt',journal['stdout']); require(journal['returncode']==0,'Cannot archive invocation journal')
    timerjournal=call(['journalctl','--user','_SYSTEMD_INVOCATION_ID='+identity['timer_invocation_id'],'--no-pager','-o','short-iso-precise'])
    commands['timer_journal']=save(out/'original-timer-invocation-journal-command.json',timerjournal); archive_pins['timer_journal']=save(out/'original-timer-invocation-journal.txt',timerjournal['stdout']); require(timerjournal['returncode']==0,'Cannot archive original timer invocation journal')
    pin_error=audit_error=None; audit=None; auditpin=None
    try: held=all(sha(path)==digest for path,digest in intent['source_pins'].items())
    except Exception as error: held=False; pin_error=f'{type(error).__name__}: {error}'
    evidence={p.name:pin(p) for p in out.iterdir() if p.is_file()}; auditpath=Path(argv[argv.index('--output')+1])/'review-receipt.json'
    try:
        if auditpath.exists(): auditpin=pin(auditpath); audit=load(auditpath)
    except Exception as error: audit_error=f'{type(error).__name__}: {error}'
    original=dict(original_pid=identity['pid'],original_starttime_ticks=identity['starttime_ticks'],original_invocation=identity['invocation_id'],original_exec_code=int(fields['ExecMainCode']),original_exit=int(fields['ExecMainStatus']),original_result=fields['Result'],source_pins_held=held,source_pin_error=pin_error,full_original_archive=archive_pins,raw_command_archives=commands,evidence=evidence,audit_receipt=auditpin,audit_receipt_error=audit_error)
    save(out/'root-original-terminal-archive.json',original); releases=[]
    for target in (timer,unit):
        terminal(); current=start(identity['pid']); require(current is None or identity['starttime_ticks'] is not None and current!=identity['starttime_ticks'],'Original audit process still present/unknown')
        prior,_=show(target)
        if prior.get('LoadState')=='not-found': releases.append(dict(unit=target,already_absent=True)); continue
        require(target!=timer or prior['InvocationID']==identity['timer_invocation_id'],'Original timer identity changed before release')
        stopped=call(['systemctl','--user','stop',target]); save(out/('release-'+target+'-stop.json'),stopped); after,_=show(target)
        known=[f'Unit {target} not loaded.',f'Failed to stop {target}: Unit {target} not loaded.']
        require(stopped['returncode']==0 or stopped['returncode']==5 and after.get('LoadState')=='not-found' and stopped['stderr'].strip() in known,'Unexpected exact-unit stop error')
        reset=None
        if after.get('LoadState')!='not-found' and after.get('ActiveState')=='failed': reset=call(['systemctl','--user','reset-failed',target]); save(out/('release-'+target+'-reset.json'),reset); require(reset['returncode']==0,'Exact reset-failed failed')
        final,_=show(target); require(final.get('LoadState')=='not-found','Exact unit not released'); releases.append(dict(unit=target,returncode=stopped['returncode'],reset_failed=reset,final_load_state='not-found'))
    passed=original['original_exec_code']==1 and original['original_exit']==0 and original['original_result']=='success' and held and isinstance(audit,dict) and audit.get('valid') is True and audit.get('result')=='valid_completed_leg'
    result=dict(status='PASS_COMPLETED_LEG_AUDIT' if passed else 'FAILED_OR_NEEDS_REVIEW',**original,original_archived_before_release=True,owned_release=releases,no_retry=True,qualification_pass=False,scope='One completed original leg only; no campaign gate, parent/trainer action or promotion')
    save(out/'root-result-review-and-release.json',result); print(json.dumps(dict(status=result['status'],original_exit=original['original_exit'],directory=str(out))))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute',action='store_true'); parser.add_argument('--action',choices=('launch','archive')); parser.add_argument('--leg',type=int,choices=(1,2,3,4)); parser.add_argument('--expected-source-sha256'); args=parser.parse_args()
    if not args.execute: print('PLAN_ONLY: no input reads, queries, audit invocation or unit actions')
    else:
        require(args.action and args.leg and args.expected_source_sha256 and sha(__file__)==args.expected_source_sha256,'Explicit exact root runner source/action/leg required')
        {'launch':launch,'archive':archive}[args.action](args.leg)
