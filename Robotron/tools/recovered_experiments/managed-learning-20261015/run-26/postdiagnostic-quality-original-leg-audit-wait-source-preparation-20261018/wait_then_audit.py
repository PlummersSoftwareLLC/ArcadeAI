"""Root-only passive explicit original-leg wait, then ONE retained metadata audit. Default PLAN."""
import argparse
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN=GAME/'logs/managed-learning-20261015/run-26'
PACK=GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/postdiagnostic_ce_quality_binding_proposal'
CONTROL=GAME/'tools/quality_audit_control_gc_repair_proposal/control_audit_reviewed3.py'
CONTROL_SHA='b5a50047e1a2981a41732c756bf908c6b9b935c58d1d0503c0df494e6f863aee'
MANIFEST_SHA='045f2ac9bcaf065c3dde018fb7e753852022e7c46b4ab664e3aa5b40e9e65e19'
AUDITOR_SHA='4493bfbcd06c5e93af26e2bb9dc22494289ed690dbc204cda3af0cd4af537c7d'
OBSERVER=PACK/'observer.py'
OBSERVER_SHA='579f2eee9afe9a4429f52b809c428f15696013a2834b2ca50a80a047d5c4194a'
SCHEMA='robotron-postdiagnostic-quality-original-leg-audit-wait-case-v1'
LIMIT=4<<20
WAIT_S=3600
POLL_S=15


def require(value,message):
    if not value:raise RuntimeError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


class StatusReplacementRace(RuntimeError):
    pass


def read_file(path,readonly=True,status_replacement=False):
    path=Path(path)
    require(path.is_absolute() and path==path.resolve(strict=True) and path.suffix not in ('.pt','.pth','.npy','.npz'),
        'Canonical bounded source/metadata only; no tensor referents')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
        before=os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink in ((0,1) if status_replacement else (1,)) and
            0<before.st_size<=LIMIT and (not readonly or stat.S_IMODE(before.st_mode)==0o444),'Owned metadata type/mode/bound differs')
        raw=f.read(LIMIT+1);after=os.fstat(f.fileno());current=path.lstat()
        stable=('device','inode','bytes','mtime_ns','mode','uid')
        if status_replacement and (before.st_dev,before.st_ino)!=(current.st_dev,current.st_ino):
            require(len(raw)==before.st_size and all(identity(before)[k]==identity(after)[k] for k in stable) and
                after.st_nlink in (0,1) and stat.S_ISREG(current.st_mode) and current.st_uid==os.getuid() and current.st_nlink==1,
                'Mutable status changed beyond an atomic path replacement')
            raise StatusReplacementRace('Atomic native status replacement during read')
        require(len(raw)==before.st_size and identity(before)==identity(after)==identity(current),
            'Opened metadata or path changed during observation')
    return raw,dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=identity(before))


def decode(raw):
    return json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite metadata: '+x)))


def pinned(pin):
    require(set(pin)=={'path','sha256','bytes','identity'},'Actual full metadata PIN required')
    raw,actual=read_file(pin['path']);require(actual==pin,'Immutable metadata PIN differs');return raw


def minimal(pin):
    return dict(path=pin['path'],sha256=pin['sha256'],bytes=pin['bytes'],
        identity={k:pin['identity'][k] for k in ('device','inode','mode','uid','nlink')})


def publish(path,value):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode();require(len(raw)<=LIMIT,'Compact output exceeds bound')
    with path.open('xb') as f:f.write(raw);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return read_file(path)[1]


def process_start(pid):
    try:
        with open(Path('/proc',str(pid),'stat'),'rb') as f:raw=f.read(65537)
    except OSError as e:
        if e.errno in (errno.ENOENT,errno.ESRCH):return None
        raise
    require(len(raw)<=65536,'Process metadata exceeds bound')
    return int(raw.rsplit(b')',1)[1].split()[19])


def validate(case,wrapper_exists=False):
    require(set(case)=={'schema','quality_owner','native_plan','native_plan_path','leg','evaluator','campaign_directory',
        'auditor_argv','audit_config','source_pins','output_directory'} and case['schema']==SCHEMA,'Exact root case required')
    owner=case['quality_owner'];evaluator=case['evaluator'];leg=case['leg']
    require(set(owner)=={'unit','pid','starttime_ticks','invocation_id','cgroup'} and
        re.fullmatch(r'robotron-quality-[A-Za-z0-9_-]+\.service',owner['unit']) and
        type(owner['pid']) is int and owner['pid']>0 and type(owner['starttime_ticks']) is int and owner['starttime_ticks']>0 and
        re.fullmatch('[0-9a-f]{32}',owner['invocation_id']) and owner['cgroup'].endswith('/'+owner['unit']) and
        type(leg) is int and 1<=leg<=4 and set(evaluator)=={'pid','starttime_ticks'} and
        all(type(x) is int and x>0 for x in evaluator.values()),'Original owner/explicit leg/evaluator identity required')
    pins=case['source_pins'];require(isinstance(pins,list),'Explicit source/metadata PIN list required')
    by_path={p['path']:p for p in pins};require(len(by_path)==len(pins),'Duplicate selected source path')
    for pin in pins:pinned(pin)
    for path,sha in ((CONTROL,CONTROL_SHA),(PACK/'preparation-manifest.json',MANIFEST_SHA),
                     (PACK/'audit_completed_leg.py',AUDITOR_SHA),(OBSERVER,OBSERVER_SHA)):
        require(str(path) in by_path and by_path[str(path)]['sha256']==sha,'Selected immutable source family differs')
    manifest=decode(pinned(by_path[str(PACK/'preparation-manifest.json')]))
    require(isinstance(manifest['files'],list) and len(manifest['files'])==16 and
        all(by_path.get(p['path'])==p for p in manifest['files']),
        'All16 immutable selected pack files required; historical upstreams are not replayed')
    plan=decode(pinned(case['native_plan']));campaign=Path(case['campaign_directory'])
    require(campaign.is_absolute() and campaign==campaign.resolve(strict=True) and campaign.parent==GAME/'logs/managed-learning-20261015' and
        plan['output_directory']==str(campaign) and case['native_plan_path']==str(campaign/'plan.json') and
        len(plan['legs'])==4 and plan['legs'][leg-1]['index']==leg and
        plan['legs'][leg-1]['role']==('reference','candidate','reference','candidate')[leg-1],
        'Exact actual native plan/selected leg/campaign required')
    raw,current=read_file(case['native_plan_path'],readonly=False)
    require(current['sha256']==case['native_plan']['sha256'] and decode(raw)==plan,'Actual native plan differs from immutable copy')
    argv=case['auditor_argv'];require(isinstance(argv,list) and len(argv)>5 and Path(argv[0]).is_absolute() and
        argv[1:4]==['-I','-B',str(PACK/'audit_completed_leg.py')] and argv.count('--execute')==1,'Direct original selected auditor argv required')
    tail=[x for x in argv[4:] if x!='--execute'];require(len(tail)==16,'Exact eight auditor argument pairs required')
    flags=dict(zip(tail[::2],tail[1::2]));require(len(flags)==8 and set(flags)=={'--game','--campaign','--plan-sha256','--source-sha256',
        '--binding-job','--binding-job-sha256','--leg','--output'} and flags['--game']==str(GAME) and
        flags['--campaign']==str(campaign) and flags['--plan-sha256']==case['native_plan']['sha256'] and
        flags['--source-sha256']==AUDITOR_SHA and flags['--leg']==str(leg) and
        flags['--binding-job'] in by_path and by_path[flags['--binding-job']]['sha256']==flags['--binding-job-sha256'],
        'Original selected audit source/actual native plan/binding selection differs')
    config=decode(pinned(case['audit_config']))
    require(set(config)=={'unit','output','argv','properties','pins','observation_s'} and config['argv']==argv and
        re.fullmatch(r'robotron-[A-Za-z0-9_-]+\.service',config['unit']) and config['unit']!=owner['unit'] and
        config['pins']==[minimal(p) for p in pins] and type(config['observation_s']) in (int,float) and
        60<=config['observation_s']<=180,'Exact retained original audit config required; omit result_path/expected_tests')
    properties=dict(x.split('=',1) for x in config['properties'])
    require(len(properties)==len(config['properties']) and properties.get('CPUQuota')=='100%' and
        properties.get('MemoryMax')=='512M' and properties.get('RuntimeMaxSec')=='60' and
        set(properties)<= {'CPUQuota','MemoryMax','RuntimeMaxSec','MemorySwapMax','TasksMax','TimeoutStopSec'} and
        properties.get('MemorySwapMax','0')=='0' and properties.get('TasksMax','128') in ('128','256') and
        properties.get('TimeoutStopSec','5')=='5','Bounded CPU100/512M/60s audit scope differs')
    paths=[Path(case['output_directory']),Path(config['output']),Path(flags['--output'])]
    require(len(set(paths))==3 and all(p.is_absolute() and p==p.resolve(strict=False) and p.parent==RUN and
        (p.is_dir() if wrapper_exists and i==0 else not p.exists()) for i,p in enumerate(paths)),
        'Distinct NEW wrapper/execution/audit output directories required')
    return owner,evaluator,plan,config,flags


def observe_parent(owner,deadline):
    left=deadline-time.monotonic();require(left>0,'Fixed3600s passive wait exhausted; no audit launched')
    r=subprocess.run(['systemctl','--user','show',owner['unit'],'--all'],capture_output=True,timeout=min(10,left))
    require(len(r.stdout)<=LIMIT and len(r.stderr)<=LIMIT and r.returncode==0,'Original parent observation failed')
    fields=dict(x.split('=',1) for x in r.stdout.decode('utf-8','surrogateescape').splitlines() if '=' in x)
    require(fields.get('LoadState')=='loaded' and fields.get('ExecMainPID')==str(owner['pid']) and
        fields.get('InvocationID')==owner['invocation_id'] and fields.get('NRestarts')=='0' and
        fields.get('ControlGroup') in ('',owner['cgroup']),'Original quality parent incarnation changed')
    if fields.get('MainPID')==str(owner['pid']):require(process_start(owner['pid'])==owner['starttime_ticks'],'Live parent PID/start differs')
    else:require(fields.get('MainPID')=='0' and fields.get('ExecMainCode')=='1','Original parent neither same live nor retained terminal')
    return dict(fields=fields,argv=['systemctl','--user','show',owner['unit'],'--all'],returncode=r.returncode,
        stderr=r.stderr.decode('utf-8','surrogateescape'))


def run(args):
    raw,self_pin=read_file(Path(__file__).resolve());require(self_pin['sha256']==args.expected_source_sha256,'Wrapper source differs')
    _,case_pin=read_file(args.case);require(case_pin['sha256']==args.expected_case_sha256,'Root case SHA differs')
    case=decode(pinned(case_pin));owner,evaluator,plan,config,flags=validate(case);selected=plan['legs'][case['leg']-1]
    out=Path(case['output_directory']);out.mkdir(mode=0o700)
    result=dict(status='WAITING_ORIGINAL_LEG',leg=case['leg'],case=case_pin,source=self_pin,wait_s=WAIT_S,poll_s=POLL_S,
        wait_started_unix_s=time.time(),observations=0,transient_observations=0,audit_launch_attempted=False,audit_observe_attempted=False,
        quality_acceptance=False,quality_relaunched=False,main_or_control_actions=False)
    publish(out/'start.json',result);deadline=time.monotonic()+WAIT_S
    try:
        while True:
            try:
                result['last_parent_observation']=observe_parent(owner,deadline)
                raw,pin=read_file(Path(case['campaign_directory'])/'status.json',readonly=False,status_replacement=True)
            except (StatusReplacementRace,subprocess.TimeoutExpired) as transient:
                result.update(transient_observations=result['transient_observations']+1,
                    last_transient=dict(type=type(transient).__name__,error=str(transient),observed_unix_s=time.time()))
                left=deadline-time.monotonic();require(left>0,'Fixed3600s passive wait exhausted after observation transient')
                time.sleep(min(POLL_S,left));continue
            status=decode(raw)
            require(status['plan_sha256']==case['native_plan']['sha256'] and status['plan_path']==case['native_plan_path'],
                'Native status plan binding differs')
            records=[x for x in status['legs'] if x['index']==case['leg']]
            require(len(records)==1 and records[0]['role']==selected['role'] and records[0]['pid']==evaluator['pid'] and
                all(records[0][k]==selected[k] for k in ('receipt_path','evaluator_status_path','console_log')),
                'Original selected evaluator role/PID/paths differ')
            leg=records[0];result.update(observations=result['observations']+1,last_observed_unix_s=time.time(),
                last_native_status=pin,last_leg_record=leg,native_campaign_state=status['state'])
            observed_start=process_start(evaluator['pid'])
            if leg['state']=='finished':
                require(type(leg['returncode']) is int and observed_start!=evaluator['starttime_ticks'],
                    'Finished original evaluator exit/absence differs')
                require(time.monotonic()<=deadline,'Original leg completion observed beyond fixed3600s wait')
                break
            require(leg['state']=='running','Original leg state is not waitable')
            require(observed_start in (None,evaluator['starttime_ticks']),'Original running evaluator PID was reused')
            if observed_start is None:
                result.update(transient_observations=result['transient_observations']+1,
                    last_transient=dict(type='EvaluatorExitedAwaitingNativeFinished',observed_unix_s=time.time()))
            left=deadline-time.monotonic();require(left>0,'Fixed3600s passive wait exhausted; no audit launched')
            time.sleep(min(POLL_S,left))
        # Reauthenticate fixed inputs immediately before the sole action. No
        # model paths are dereferenced and no native exit is relabelled.
        validate(case,wrapper_exists=True)
        control_raw,control_pin=read_file(CONTROL)
        require(control_pin['sha256']==CONTROL_SHA,'Exact selected GC-aware root control source differs')
        sys.dont_write_bytecode=True
        spec=importlib.util.spec_from_file_location('_one_original_leg_root_control',CONTROL)
        control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)
        result['audit_launch_attempted']=True
        control.launch(case['audit_config']['path'])
        result['audit_observe_attempted']=True
        control.observe(case['audit_config']['path'])  # Same process; never a second tool invocation.
        released_path=Path(config['output'])/'root-original-result-and-owned-release.json'
        released_raw,released_pin=read_file(released_path);released=decode(released_raw)
        # Preserve the original payload and every raw lifecycle outcome even
        # when the subsequent completeness guard refuses this one attempt.
        result.update(original_audit_result=released_pin,original_audit_exit=released.get('original_exit'),
            original_audit_result_value=released.get('original_result'),original_native_leg_exit=leg['returncode'],
            audit_lifecycle_complete=released.get('lifecycle_complete'),audit_unit_released=released.get('unit_released'),
            audit_archive_status=released.get('original_archive_status'),
            audit_all_six_archive_commands_succeeded=released.get('all_six_original_archive_commands_succeeded'),
            audit_owned_release=released.get('owned_release'),audit_valid=None)
        original=released.get('original')
        require(released.get('schema')=='robotron-root-audit-original-result-and-GC-aware-owned-release-v1' and
            isinstance(original,dict) and original['unit']==config['unit'] and original['observed_live'] is True and
            released['original_archived_before_release'] is True and released['lifecycle_complete'] is True and
            released['unit_released'] is True and released['original_exec_code']==1 and type(released['original_exit']) is int and
            released['audit_success'] is (released['original_exit']==0) and released['payload_retried'] is False and
            'payload_result' not in released,'Actual original audit/GC-aware lifecycle is incomplete or differs')
        result['status']='ORIGINAL_AUDIT_TERMINAL_ARCHIVED_AND_RELEASED'
        report_path=Path(flags['--output'])/'review-receipt.json'
        if report_path.exists():
            report_raw,report_pin=read_file(report_path);report=decode(report_raw)
            result.update(audit_report=report_pin,audit_valid=report.get('valid'),audit_report_result=report.get('result'))
        result['ended_unix_s']=time.time();publish(out/'end.json',result)
        return 0 if released['original_exit']==0 else 2
    except BaseException as error:
        result.update(status='ERROR_PRESERVED_NO_RETRY',error=repr(error),ended_unix_s=time.time())
        publish(out/'end.json',result);raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--case',type=Path);p.add_argument('--expected-case-sha256');p.add_argument('--expected-source-sha256')
    args=p.parse_args(argv)
    if not args.execute:print('PLAN_ONLY: no reads/imports/runtime/wait/outputs/unit/audit/actions');return 0
    require(args.case and args.expected_case_sha256 and args.expected_source_sha256,'Explicit sealed source/case required')
    return run(args)


if __name__=='__main__':raise SystemExit(main())
