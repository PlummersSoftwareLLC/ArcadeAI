"""Root-only wait -> one sealed R1 audit launch -> original terminal archive. Default PLAN."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

RUN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
CASE_SCHEMA = 'robotron-first-LATCH-followup-R1-audit-sequencer-case-v1'
EXPECTED = {
    'native_plan':'fdb13f963f7433d8dcd816934fe266f327760a7953d47a1208f752f284d5fe85',
    'launch_record':'343537e2b5ab1752d8bcef52568c743f7115c8ed49b1a2cc03687861bc47fa51',
    'commands':'4707ed548be028ff2953a23834854ce7543415fce2b114a2de9237aaf923864b',
    'runner':'8f0967f763ae524cc7399bfef58fd2d04a125e796e4daa75ac7c8d81efc7430e',
    'runner_manifest':'766fcc1ba18fb60539bc4f488d80fb888312e1254c77a9f42c6e5e73751c1d8c',
    'runner_peer':'7aeddd133d20ff0410bee498833920810a59119a844426f7cdfdfeb0f66aedaf',
    'launch_peer':'35c63c7b9b81ab59aefb4e65e09069ccc78d5dc6616f82d8ebc06fab32864f39'}
MAX_FILE = 4 << 20
MAX_OUTPUT = 32 << 20
WAIT_S = 3000
POLL_S = 15
UID = 1001


def require(value,message):
    if not value:raise RuntimeError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def raw_file(path,readonly=True):
    p=Path(path)
    require(p.is_absolute() and p==p.resolve(strict=True) and p.suffix not in ('.pt','.pth','.npy','.npz'),
        'Only canonical bounded source/metadata files; no model bodies')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid==UID and before.st_nlink==1
            and 0<before.st_size<=MAX_FILE and (not readonly or stat.S_IMODE(before.st_mode)==0o444),
            'Owned bounded metadata mode/type differs: '+str(p))
        with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(MAX_FILE+1)
        require(len(raw)==before.st_size and identity(before)==identity(os.fstat(fd))==identity(p.lstat()),
            'Metadata changed during read: '+str(p))
    finally:os.close(fd)
    return raw,dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))


def decode(raw):
    return json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))


def pinned(pin,full=True):
    require(set(pin)=={'path','sha256','bytes','identity'},'Explicit metadata PIN required')
    raw,actual=raw_file(pin['path'])
    require(all(actual[k]==pin[k] for k in ('path','sha256','bytes')),'Metadata digest differs')
    require(pin['identity']==actual['identity'] if full else
        all(actual['identity'][k]==v for k,v in pin['identity'].items()),'Metadata identity differs')
    return raw,actual


class Evidence:
    def __init__(self,out):self.out=out;self.total=0;self.counter=0;self.commands=[]

    def save(self,name,value):
        raw=value if isinstance(value,bytes) else (json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
        require(len(raw)<=MAX_FILE and self.total+len(raw)<=MAX_OUTPUT,'Evidence byte budget exceeded')
        self.total+=len(raw);p=self.out/name
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:
            require(f.write(raw)==len(raw),'Short evidence write');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        fd=os.open(self.out,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
        return raw_file(p)[1]

    def call(self,argv,timeout):
        value=dict(argv=argv,started_unix_s=time.time(),timeout_s=timeout)
        try:
            p=subprocess.run(argv,capture_output=True,check=False,timeout=timeout)
            value.update(returncode=p.returncode,stdout=p.stdout.decode('utf-8','surrogateescape'),
                stderr=p.stderr.decode('utf-8','surrogateescape'),timed_out=False)
        except subprocess.TimeoutExpired as e:
            value.update(returncode=None,stdout=(e.stdout or b'').decode('utf-8','surrogateescape'),
                stderr=(e.stderr or b'').decode('utf-8','surrogateescape'),timed_out=True)
        value['ended_unix_s']=time.time()
        pin=self.save('%03d-command.json'%self.counter,value);self.counter+=1;self.commands.append(pin)
        return value,pin

    def show(self,unit,timeout=10):
        require(re.fullmatch(r'robotron-[A-Za-z0-9_.@-]+\.(service|timer)',unit),'Exact unit name required')
        raw,pin=self.call(['systemctl','--user','show',unit,'--all'],timeout)
        fields=dict(line.split('=',1) for line in raw['stdout'].splitlines() if '=' in line)
        require(not raw['timed_out'] and raw['returncode']==0 and fields.get('LoadState')=='loaded',
            'Exact retained unit observation failed: '+unit)
        return fields,pin


def process_start(pid):
    try:
        with open(Path('/proc',str(pid),'stat'),'rb') as f:raw=f.read(65537)
    except OSError as e:
        if e.errno in (errno.ENOENT,errno.ESRCH):return None
        raise
    require(len(raw)<=65536,'Process metadata exceeds bound')
    return int(raw.rsplit(b')',1)[1].split()[19])


def remain(deadline,maximum):
    left=deadline-time.monotonic();require(left>0,'Fixed monotonic3000s observation budget exhausted')
    return min(left,maximum)


def pause(deadline):time.sleep(remain(deadline,POLL_S))


def quality_owner(evidence,owner,deadline):
    fields,pin=evidence.show(owner['unit'],remain(deadline,10))
    require(fields.get('ExecMainPID')==str(owner['pid']) and fields.get('InvocationID')==owner['invocation_id']
        and fields.get('NRestarts')=='0' and fields.get('ControlGroup') in ('',owner['cgroup']),
        'Original quality parent identity changed')
    require(fields.get('MainPID')=='0' or fields.get('MainPID')==str(owner['pid'])
        and process_start(owner['pid'])==owner['starttime_ticks'],'Original live quality parent PID/start changed')
    return pin


def validate_case(case):
    require(set(case)=={'schema',*EXPECTED} and case['schema']==CASE_SCHEMA,'Exact sequencer case fields required')
    values={}
    for name,digest in EXPECTED.items():
        require(case[name]['sha256']==digest,'Selected original source/metadata family differs: '+name)
        raw,_=pinned(case[name]);values[name]=raw.decode() if name=='runner' else decode(raw)
    launch=values['launch_record'];commands=values['commands'];plan=values['native_plan'];manifest=values['runner_manifest']
    require(commands['actual_plan']=={k:launch['actual_plan'][k] for k in ('path','sha256')}
        and launch['actual_plan']['sha256']==case['native_plan']['sha256']
        and launch['actual_plan']['bytes']==case['native_plan']['bytes'],'Actual native plan binding differs')
    owner={k:v for k,v in launch['owner'].items() if k!='observed_live'}
    require(commands['quality_owner']==owner and commands['R1_evaluator']==launch['R1_evaluator']
        and launch['owner']['observed_live'] is True,'Saved genuine original quality/R1 owner differs')
    require(manifest['files']['run_original_leg_audit.py']==case['runner']
        and values['runner_peer']['status']=='SOURCE_ONLY_PASS'
        and values['runner_peer']['manifest']==case['runner_manifest']
        and values['launch_peer']['status']=='PASS_SAVED_ACTUAL_LAUNCH_PLAN_AND_FOUR_AUDIT_COMMAND_BINDINGS',
        'Sealed runner/source-peer/actual-launch peer differs')
    require([x['leg'] for x in commands['commands']]==[1,2,3,4] and len(plan['legs'])==4
        and plan['legs'][0]['role']=='reference','Original four-command/R1 plan selection differs')
    native_raw,native_pin=raw_file(launch['actual_plan']['path'],readonly=False)
    require(native_pin['sha256']==case['native_plan']['sha256'] and decode(native_raw)==plan,
        'Current frozen native plan differs from readonly copy')
    return values,owner


def run(evidence,case,result):
    values,owner=validate_case(case);commands=values['commands'];plan=values['native_plan'];runner=case['runner']['path']
    deadline=time.monotonic()+WAIT_S;result['wait_started_unix_s']=time.time()
    result['fixed_wait_s']=WAIT_S;result['poll_s']=POLL_S
    campaign=Path(plan['output_directory']);expected_plan=case['native_plan']['sha256'];r1=commands['R1_evaluator']
    observations=[];result['wait_observations']=observations
    while True:
        remain(deadline,10);parent_pin=quality_owner(evidence,owner,deadline)
        raw,status_pin=raw_file(campaign/'status.json',readonly=False);state=decode(raw)
        require(state['plan_sha256']==expected_plan,'Current native campaign status plan differs')
        records=[x for x in state['legs'] if x['index']==1]
        require(len(records)==1 and records[0]['role']=='reference' and records[0]['pid']==r1['pid'],
            'Original R1 evaluator identity/role differs')
        record=records[0];require(record['state'] in ('running','finished'),'Original R1 state is not waitable')
        snapshot=evidence.save('%03d-native-status.json'%len(observations),raw)
        observations.append(dict(observed_unix_s=time.time(),parent_show=parent_pin,status=snapshot,
            native_status_identity=status_pin['identity'],R1_state=record['state']))
        if record['state']=='finished':
            require(record['returncode']==0,'Original R1 evaluator failed; no audit launch')
            break
        pause(deadline)
    result['wait_observations']=observations
    launch_argv=['/usr/bin/python3.12','-I','-B',runner,'--execute','--action','launch','--leg','1',
        '--expected-source-sha256',EXPECTED['runner'],'--future-commands',case['commands']['path'],
        '--expected-future-sha256',EXPECTED['commands']]
    result['launch_attempted']=True
    result['launch_attempt_intent']=evidence.save('one-launch-attempt-intent.json',
        dict(argv=launch_argv,case=case,only_one_attempt=True,ready_native_record=record))
    launched,launch_pin=evidence.call(launch_argv,remain(deadline,120));result['launch_execution']=launch_pin
    require(not launched['timed_out'] and launched['returncode']==0,'Original audit launch wrapper failed/uncertain; preserve without retry')
    audit_out=RUN/'CE2048-trial02-first-LATCH-followup-quality-original-row-leg01-audit-root-execution-reviewed1-20261017'
    raw,identity_pin=raw_file(audit_out/'root-observed-original-identity.json');original=decode(raw)
    intent_raw,intent_pin=pinned(original['launch_intent'],full=False);intent=decode(intent_raw)
    unit=original['unit'];timer=intent['timer']
    expected_unit='robotron-CE2048-trial02-first-LATCH-followup-quality-original-row-leg01-audit-reviewed1-20261017.service'
    require(unit==intent['unit']==expected_unit and timer==unit.removesuffix('.service')+'.timer'
        and original['launch_intent']['path']==str(audit_out/'root-launch-intent.json')
        and intent['sealed_auditor_argv']==commands['commands'][0]['argv']
        and intent['plan_sha256']==expected_plan and intent['source_pins'][runner]==EXPECTED['runner']
        and type(original['pid']) is int and original['pid']>0
        and re.fullmatch('[0-9a-f]{32}',original['invocation_id'])
        and re.fullmatch('[0-9a-f]{32}',original['timer_invocation_id']),
        'Genuine original audit identity/launch intent differs')
    result['original_audit_identity']=original;result['original_identity_pin']=identity_pin
    terminal_observations=[];result['wait_observations']=observations
    while True:
        remain(deadline,10);fields,show_pin=evidence.show(unit,remain(deadline,10))
        require(fields.get('ExecMainPID')==str(original['pid']) and fields.get('InvocationID')==original['invocation_id']
            and fields.get('NRestarts')=='0','Original audit unit identity changed')
        main_pid=int(fields.get('MainPID','0'))
        require(main_pid in (0,original['pid']),'Original audit MainPID changed')
        if main_pid:
            require(original['starttime_ticks'] is not None and process_start(main_pid)==original['starttime_ticks'],
                'Original live audit PID/start unavailable or changed')
        terminal_observations.append(dict(observed_unix_s=time.time(),show=show_pin))
        if main_pid==0:
            require(fields.get('SubState') in ('exited','dead','failed'),'Original audit is not terminal')
            break
        pause(deadline)
    result['terminal_observations']=terminal_observations
    archive_argv=['/usr/bin/python3.12','-I','-B',runner,'--execute','--action','archive','--leg','1',
        '--expected-source-sha256',EXPECTED['runner']]
    result['archive_attempted']=True
    result['archive_attempt_intent']=evidence.save('one-archive-attempt-intent.json',dict(argv=archive_argv,
        original_identity=original,launch_intent=intent_pin,only_one_attempt=True))
    archived,archive_pin=evidence.call(archive_argv,remain(deadline,120));result['archive_execution']=archive_pin
    require(not archived['timed_out'] and archived['returncode']==0,'Original audit archive wrapper failed/uncertain; no extra cleanup/retry')
    raw,summary_pin=raw_file(audit_out/'root-result-review-and-release.json');summary=decode(raw)
    result['original_audit_result']=summary;result['original_audit_result_pin']=summary_pin
    require(summary['original_pid']==original['pid'] and summary['original_invocation']==original['invocation_id']
        and summary['original_archived_before_release'] is True and summary['no_retry'] is True
        and summary['qualification_pass'] is False and {x['unit'] for x in summary['owned_release']}=={unit,timer}
        and all(x.get('final_load_state')=='not-found' or x.get('already_absent') is True for x in summary['owned_release']),
        'Original owned archive/release summary differs')
    raw,terminal_pin=raw_file(audit_out/'root-original-terminal-archive.json');terminal=decode(raw)
    require(all(summary[k]==terminal[k] for k in ('original_pid','original_invocation','original_exec_code',
        'original_exit','original_result','source_pins_held','audit_receipt')),'Original terminal archive/summary differs')
    result['original_terminal_archive']=terminal_pin
    audit=None
    if summary['audit_receipt'] is not None:
        raw,audit_pin=pinned(summary['audit_receipt'],full=False);audit=decode(raw);result['audit_receipt']=audit_pin
    passed=summary['status']=='PASS_COMPLETED_LEG_AUDIT' and summary['original_exec_code']==1 and summary['original_exit']==0
    passed=passed and summary['original_result']=='success' and summary['source_pins_held'] is True
    passed=passed and isinstance(audit,dict) and audit.get('valid') is True and audit.get('result')=='valid_completed_leg'
    result.update(status='PASS_ORIGINAL_R1_AUDIT_ARCHIVED_AND_RELEASED' if passed else 'FAILED_OR_NEEDS_REVIEW',
        audit_pass=passed,original_auditor_exit=summary['original_exit'],archive_wrapper_exit=archived['returncode'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--case',type=Path)
    parser.add_argument('--case-sha256');parser.add_argument('--expected-source-sha256');parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no reads, queries, audit calls or output');return 0
    require(args.case and args.case_sha256 and args.expected_source_sha256 and args.output,'Explicit root case/source/output required')
    out=args.output
    require(out.is_absolute() and RUN in out.parents and out.parent==out.parent.resolve(strict=True)
        and not os.path.lexists(out),'Fresh canonical run26 output required')
    out.mkdir(mode=0o700);fd=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    evidence=Evidence(out);result=dict(status='FAILED_SEQUENCER',started_unix_s=time.time(),launch_attempted=False,
        archive_attempted=False,audit_pass=False,no_retry=True,quality_or_main_actions=False,quality_qualification=False)
    try:
        _,source=raw_file(__file__);require(source['sha256']==args.expected_source_sha256,'Explicit sequencer source differs')
        raw,case_pin=raw_file(args.case);require(case_pin['sha256']==args.case_sha256,'Explicit root case differs')
        case=decode(raw);result['source']=source;result['root_case']=case_pin
        result['intent']=evidence.save('root-sequencer-intent.json',dict(case=case,source=source,wait_s=WAIT_S,poll_s=POLL_S,
            only_original_R1_audit=True,no_retry=True,quality_or_main_actions=False))
        run(evidence,case,result)
    except BaseException as e:result['first_error']=dict(type=type(e).__name__,message=str(e))
    result.update(ended_unix_s=time.time(),raw_command_metadata=evidence.commands)
    evidence.save('root-sequencer-result.json',result)
    print(json.dumps(dict(status=result['status'],audit_pass=result['audit_pass'],output=str(out)),allow_nan=False))
    return 0 if result['audit_pass'] else 2


if __name__=='__main__':raise SystemExit(main())
