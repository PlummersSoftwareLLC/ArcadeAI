"""Root-only metadata prep for one genuinely observed native leg2..4. Default PLAN.

No waiting, auditor/CPU launch, signals, cleanup, model access or state changes.
Root supplies actual evaluator PID/start; only config/case/observation are written.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import time

RUN=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
ROOT_PREP=RUN/'accepted-newgame-forward-recovery-root-control-20261017'
BASE_CASE=ROOT_PREP/'actual-postaccepted-quality-leg01-audit-wait-case.json'
BASE_CASE_SHA='f8ce1a56bea81c85214fab3277569e4644dfbc0296f976d036221baaee70984b'
BASE_CONFIG_SHA='292121e6581e9ba7a300c50dbbda459a4a6314de30d6169cde4bc15d852f5733'
WAITER=RUN/'postaccepted-newgame-quality-R1-audit-wait-source-preparation-20261017/wait_then_audit.py'
WAITER_SHA='0a1c957afbd1a2877a8217f15458525ab535bd148997956e39d10ea45cf4749a'
LIMIT=4<<20


def require(value,message):
    if not value:raise RuntimeError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
        ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def sealed(path,expected):
    path=Path(path)
    require(path.is_absolute() and path==path.resolve(strict=True) and path.suffix in ('.py','.json'),
        'Canonical source/metadata only; no model referents')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
        before=os.fstat(f.fileno());require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and
            before.st_nlink==1 and stat.S_IMODE(before.st_mode)==0o444 and 0<before.st_size<=LIMIT,'Owned bounded444 input required')
        raw=f.read(LIMIT+1)
        require(len(raw)==before.st_size and identity(before)==identity(os.fstat(f.fileno()))==identity(path.lstat()) and
            hashlib.sha256(raw).hexdigest()==expected,'Sealed input SHA/identity differs')
    return raw,dict(path=str(path),sha256=expected,bytes=len(raw),identity=identity(before))


def leg_name(value,number):
    require(type(value) is str and value.count('leg01')==1,'Original leg01 name must contain exactly one selector')
    return value.replace('leg01','leg%02d'%number)


def replace_flag(argv,flag,value):
    require(argv.count(flag)==1 and argv.index(flag)+1<len(argv),'Original exact auditor flag missing/duplicated')
    argv[argv.index(flag)+1]=value


def live_parent(waiter,owner):
    observed=waiter.observe_parent(owner,time.monotonic()+20)
    fields=observed['fields']
    require(fields['MainPID']==str(owner['pid']) and fields['ActiveState']=='active' and
        fields['SubState']=='running' and fields['ControlGroup']==owner['cgroup'] and
        waiter.process_start(owner['pid'])==owner['starttime_ticks'],'Original quality parent must still be live, unchanged and N0')
    return observed


def live_leg(waiter,base,plan,number,pid,start):
    raw,status_pin=waiter.read_file(Path(base['campaign_directory'])/'status.json',readonly=False,status_replacement=True)
    status=waiter.decode(raw);selected=plan['legs'][number-1]
    require(status['plan_sha256']==base['native_plan']['sha256'] and status['plan_path']==base['native_plan_path'] and
        selected['index']==number and selected['role']==('reference','candidate','reference','candidate')[number-1],
        'Same actual plan/requested native role required')
    rows=[x for x in status['legs'] if x['index']==number]
    require(len(rows)==1 and rows[0]['state']=='running' and rows[0]['role']==selected['role'] and rows[0]['pid']==pid and
        all(rows[0][key]==selected[key] for key in ('receipt_path','evaluator_status_path','console_log')),
        'Requested original evaluator must have a matching live native row')
    require(waiter.process_start(pid)==start,'Actual selected evaluator kernel start differs or is absent')
    with open(Path('/proc',str(pid),'cmdline'),'rb') as f:command=f.read(65537)
    require(len(command)<=65536,'Evaluator argv exceeds bound')
    argv=[os.fsdecode(x) for x in command.split(b'\0') if x]
    require(argv==selected['command'] and waiter.process_start(pid)==start,'Actual selected evaluator command/start changed')
    return dict(observed_unix_s=time.time(),status=status_pin,native_record=rows[0],
        evaluator=dict(pid=pid,starttime_ticks=start),argv=argv)


def prepare(args):
    _,self_pin=sealed(Path(__file__).resolve(),args.expected_source_sha256)
    raw,base_pin=sealed(BASE_CASE,BASE_CASE_SHA)
    source,_=sealed(WAITER,WAITER_SHA)
    sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('_root_observed_leg_metadata_waiter',WAITER)
    waiter=importlib.util.module_from_spec(spec);spec.loader.exec_module(waiter)
    require(sealed(WAITER,WAITER_SHA)[0]==source,'Waiter changed during stdlib module loading')
    base=waiter.decode(raw);require(base['leg']==1 and base['schema']==waiter.SCHEMA,'Genuine sealed leg1 case required')
    config_raw=waiter.pinned(base['audit_config'])
    require(base['audit_config']['sha256']==BASE_CONFIG_SHA,'Original leg1 config differs')
    config=waiter.decode(config_raw)
    require(config['argv']==base['auditor_argv'] and config['pins']==[waiter.minimal(p) for p in base['source_pins']],
        'Original ordered FULL8 to MINIMAL5 source pins/argv differ')
    for pin in base['source_pins']:waiter.pinned(pin)
    plan=waiter.decode(waiter.pinned(base['native_plan']))
    current_raw,current_pin=waiter.read_file(base['native_plan_path'],readonly=False)
    require(current_pin['sha256']==base['native_plan']['sha256'] and waiter.decode(current_raw)==plan and len(plan['legs'])==4,
        'Genuine frozen native plan and readonly copy differ')
    require(args.leg in (2,3,4) and args.evaluator_pid>0 and args.evaluator_starttime_ticks>0,
        'Explicit observed next-leg PID/start required; no future guesses')
    owner=base['quality_owner'];parent_before=live_parent(waiter,owner)
    observation=live_leg(waiter,base,plan,args.leg,args.evaluator_pid,args.evaluator_starttime_ticks)
    new_config=copy.deepcopy(config);new_case=copy.deepcopy(base)
    new_config['unit']=leg_name(config['unit'],args.leg)
    new_config['output']=leg_name(config['output'],args.leg)
    argv=copy.deepcopy(base['auditor_argv']);replace_flag(argv,'--leg',str(args.leg))
    old_output=argv[argv.index('--output')+1];replace_flag(argv,'--output',leg_name(old_output,args.leg))
    new_config['argv']=argv  # Resources, observer budget, ordered MINIMAL5 pins remain exact.
    new_case.update(leg=args.leg,evaluator=dict(pid=args.evaluator_pid,starttime_ticks=args.evaluator_starttime_ticks),
        auditor_argv=argv,output_directory=leg_name(base['output_directory'],args.leg))
    out=args.output
    require(out.is_absolute() and out==out.resolve(strict=False) and out.parent==RUN and not out.exists() and
        str(out) not in (new_case['output_directory'],new_config['output'],argv[argv.index('--output')+1]),
        'Fresh direct run26 preparation directory distinct from all future outputs required')
    out.mkdir(mode=0o700)
    result=dict(status='PREPARING_METADATA_ONLY',source=self_pin,base_case=base_pin,base_config=base['audit_config'],
        leg=args.leg,actual_observation=dict(parent_before=parent_before,selected_leg=observation),
        wait_started=False,audit_launched=False,CPU_executed=False,unit_actions=False,model_referents_accessed=False)
    try:
        config_pin=waiter.publish(out/'audit-config.json',new_config);new_case['audit_config']=config_pin
        waiter.validate(new_case)  # ONLY the selected pure metadata/preflight function; never run/main/control.
        final_leg=live_leg(waiter,base,plan,args.leg,args.evaluator_pid,args.evaluator_starttime_ticks)
        parent_after=live_parent(waiter,owner)
        case_pin=waiter.publish(out/'audit-wait-case.json',new_case)
        result.update(status='PREPARED_OBSERVED_ORIGINAL_LEG_METADATA_ONLY',case=case_pin,config=config_pin,
            actual_observation=dict(parent_before=parent_before,selected_leg=observation,
                selected_leg_after_validation=final_leg,parent_after=parent_after))
        result_pin=waiter.publish(out/'preparation-result.json',result)
        print(json.dumps(dict(case=case_pin,config=config_pin,actual_observation=result['actual_observation'],result=result_pin),allow_nan=False))
    except BaseException as error:
        result.update(status='PREPARATION_ERROR_NO_WAIT_OR_LAUNCH',error=repr(error))
        waiter.publish(out/'preparation-result.json',result);raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--expected-source-sha256');p.add_argument('--leg',type=int,choices=(2,3,4))
    p.add_argument('--evaluator-pid',type=int);p.add_argument('--evaluator-starttime-ticks',type=int);p.add_argument('--output',type=Path)
    args=p.parse_args(argv)
    if not args.execute:print('PLAN_ONLY: no reads/imports/runtime/outputs/wait/audit/CPU/unit/actions');return 0
    require(args.expected_source_sha256 and args.leg and args.evaluator_pid and args.evaluator_starttime_ticks and args.output,
        'Explicit source SHA/requested leg/actual evaluator PID+start/new output required')
    prepare(args);return 0


if __name__=='__main__':raise SystemExit(main())
