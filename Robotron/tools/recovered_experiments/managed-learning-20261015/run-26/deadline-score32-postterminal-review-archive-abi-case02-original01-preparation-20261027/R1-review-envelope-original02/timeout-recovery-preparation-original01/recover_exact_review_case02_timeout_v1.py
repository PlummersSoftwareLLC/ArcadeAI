"""Exact terminal timeout recovery; inert unless --check or ROOT --execute.

Never launches a payload or signals a PID. Execute requires the selected parent
controller's completed immutable receipt and no matching live controller, then
archives all six original service/timer descriptors before exact owned release.
True ExecMainCode=2/status15/Result=timeout is retained; no exit normalization.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

UNIT='robotron-deadline32-score60min-r1-original03-postterminal-review-original02-20261027.service'
PID=27950
BIRTH=115134239
INVOCATION='ffaec0eb3cef401db483591551fb1a4b'
TIMER_INVOCATION='399432a250714177b7035dc4ea886bab'


def require(ok,message):
    if not ok:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def context(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Recovery source changed')
    raw=args.manifest.read_bytes();require(hashlib.sha256(raw).hexdigest()==args.manifest_sha256,'Exact recovery manifest changed')
    manifest=json.loads(raw)
    require(manifest['schema']=='robotron-exact-review-case02-terminal-timeout-recovery-inputs-v1','Exact recovery schema required')
    hp=manifest['helpers'];require(hashlib.sha256(Path(hp['path']).read_bytes()).hexdigest()==hp['sha256'],'Selected helper changed')
    h=load('_review_timeout_recovery_helpers',hp['path'])
    for entry in manifest['pins']:h.checked(entry)
    reader=load('_review_timeout_recovery_immutable_reader',h.checked(manifest['reader']))
    def read(entry,as_json=True):return reader.read_pin(entry,as_json=as_json)
    utility=load('_review_timeout_recovery_signalaware_utility',h.checked(manifest['signalaware_utility']))
    controller=load('_review_timeout_recovery_original_controller',h.checked(manifest['original_controller']))
    owner=read(manifest['owner']);cfg=read(manifest['config']);parent=read(manifest['parent_controller_receipt'])
    launch=read(manifest['timer_launch_archive']);review=read(manifest['review_job'])
    require(owner==dict(pid=PID,starttime_ticks=BIRTH,invocation_id=INVOCATION,unit=UNIT,
        timer=UNIT[:-8]+'.timer',timer_invocation_id=TIMER_INVOCATION,observed_live=True),'Exact captured original owner differs')
    require(controller.checked_config(manifest['config']['path'])==cfg and cfg['unit']==UNIT,'Original exact configuration differs')
    require(cfg['properties']==['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=180',
        'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no']and cfg['observation_s']==240,'Exact original CPU scope differs')
    require(cfg['argv'][7]==manifest['review_job']['path']and cfg['argv'][9]==manifest['review_job']['sha256'],
        'Actual original review job argv differs')
    require(parent['original']==owner and parent['status']=='ORIGINAL_OUTCOME_PRESERVED_OWNED_RELEASE_INCOMPLETE'
        and parent['original_exec_code']is None and parent['original_exit']is None and parent['unit_released']is False
        and parent['lifecycle_complete']is False and parent['payload_retried']is False
        and parent['error']=="RuntimeError('Observational deadline: original left untouched')"
        and type(parent['ended_unix_s'])in(int,float)and parent['ended_unix_s']<=time.time(),
        'Original parent completion receipt is missing or differs')
    require(manifest['root_observed_parent_tool_session']==41007 and manifest['root_observed_parent_tool_exit']==1,
        'ROOT observed terminal parent tool must be declared separately from payload signal')
    require(launch['unit']==UNIT and launch['timer']==owner['timer']and launch['timer_invocation_id']==TIMER_INVOCATION
        and launch['scheduling_carrier']['exit']==0 and launch['no_retry']is True and launch['original_attempt']==1,
        'Durable exact original timer launch ownership differs')
    intent=read(launch['launch_intent']);require(all(intent[k]==v for k,v in cfg.items()),'Durable launch/config fields differ')
    require(intent['actual_argv']==launch['scheduling_carrier']['argv']and launch['scheduling_carrier']['argv'][-len(cfg['argv']):]==cfg['argv'],
        'Actual original scheduling/runtime argv differs')
    timer_context=dict(unit=UNIT,timer=owner['timer'],timer_invocation_id=TIMER_INVOCATION)
    timerlaunch=utility.fields(launch['timer_show']);require(utility.timer_state(timerlaunch,timer_context)=='original_loaded',
        'Actual launch-time timer identity does not bind original timer')
    require(launch['timer_cat']['exit']==0 and read(launch['timer_cat']['stdout'],False),'Successful original timer cat required')
    first=read(manifest['original_first_show_command']);require(first['exit']==0 and first['timed_out']is False,'Original live scope observation failed')
    live=dict(line.split('=',1)for line in read(first['stdout'],False).decode().splitlines()if'='in line)
    require(live['Id']==UNIT and live['MainPID']==str(PID)and live['InvocationID']==INVOCATION,'Original live PID/invocation was not captured')
    cgroup=live['ControlGroup'];require(cgroup=='/user.slice/user-'+str(os.geteuid())+'.slice/user@'+str(os.geteuid())+'.service/app.slice/'+UNIT,
        'Actual original live cgroup differs')
    result=dict(manifest=manifest,h=h,read=read,utility=utility,controller=controller,owner=owner,cfg=cfg,parent=parent,
        launch=launch,timer_context=timer_context,review=review,cgroup=cgroup,live_fields=live)
    ownership_check(result)
    require(not Path(manifest['output']).exists(),'Exclusive original recovery directory already exists; no retry/overwrite')
    return result


def controller_absent(ctx):
    found=[];controller_path=ctx['manifest']['original_controller']['path'];config_path=ctx['manifest']['config']['path']
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():continue
        try:
            if proc.stat().st_uid!=os.geteuid():continue
            values=[x.decode(errors='replace')for x in(proc/'cmdline').read_bytes().split(b'\0')if x]
        except (FileNotFoundError,ProcessLookupError):continue
        if controller_path in values and config_path in values:found.append(int(proc.name))
    require(not found,'Original exact parent controller is still running: '+str(found))
    return found


def terminal(ctx,fields):
    ctx['utility'].original_terminal(fields,ctx['owner'])
    expected=dict(Id=UNIT,InvocationID=INVOCATION,MainPID='0',ExecMainPID=str(PID),ExecMainCode='2',ExecMainStatus='15',
        Result='timeout',ActiveState='failed',SubState='failed',NRestarts='0',CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),
        MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no')
    require(all(fields.get(k)==v for k,v in expected.items()),'Exact original terminal signal/timeout/resource state changed')
    require('ControlGroup'in fields and fields['ControlGroup']=='','Terminal ControlGroup missing or nonempty')
    require(all(value in fields['ExecStart']for value in ctx['cfg']['argv']),'Actual original archived argv differs')
    return fields


def ownership_check(ctx):
    require(birth(PID)!=BIRTH,'Original review payload is still running')
    controller_absent(ctx)
    current=terminal(ctx,ctx['utility'].show(UNIT))
    cg=subprocess.run(['systemctl','--user','show',UNIT,'--property=ControlGroup','--value'],capture_output=True,text=True,timeout=10)
    require(cg.returncode==0 and cg.stdout.strip()==''and cg.stderr=='','Explicit original ControlGroup query did not prove empty')
    require(not Path('/sys/fs/cgroup'+ctx['cgroup']).exists(),'Original filesystem cgroup remains')
    ctx['utility'].timer_state(ctx['utility'].show(ctx['owner']['timer']),ctx['timer_context'])
    require(not Path(ctx['review']['output']).exists(),'Original timed-out review unexpectedly has a report; stop for review')
    return current


def check(args):
    ctx=context(args);fields=ownership_check(ctx)
    return dict(schema='robotron-exact-review-case02-readonly-prearchive-predicates-v1',passed=True,
        original_exec_code=2,original_exec_status=15,original_termination_signal=15,original_exit_code=None,original_result='timeout',
        elapsed_original_service_s=(int(fields['ExecMainExitTimestampMonotonic'])-int(fields['ExecMainStartTimestampMonotonic']))/1e6,
        actual_accounting={k:fields[k]for k in('CPUUsageNSec','MemoryPeak','MemorySwapPeak')if k in fields},
        parent_receipt=ctx['manifest']['parent_controller_receipt'],parent_controller_no_longer_running=True,
        original_payload_birth_absent=True,explicit_ControlGroup_empty=True,original_cgroup_absent=True,
        exact_timer_launch_ownership_checked=True,original_report_absent=True,
        mutation_or_archive_commands_executed=False,model_raw_GPU_or_source_changes=False)


def execute(args):
    ctx=context(args);u=ctx['utility'];m=ctx['manifest'];owner=ctx['owner'];out=Path(m['output'])
    # Every guard above runs BEFORE the first exclusive directory/file write.
    out.mkdir(mode=0o700)
    record=dict(schema='robotron-exact-review-case02-timeout-signal-original-owned-release-recovery-v1',
        status='ORIGINAL_TIMEOUT_ARCHIVING_RELEASE_NOT_STARTED',original=owner,original_exec_code=2,
        original_exec_status=15,original_termination_signal=15,original_exit_code=None,original_result='timeout',
        parent_controller_tool_session=41007,parent_controller_tool_exit=1,preserved_parent_receipt=m['parent_controller_receipt'],
        original_config=m['config'],original_timer_launch_archive=m['timer_launch_archive'],
        full_original_archives=[],original_archive_status=[],all_six_original_archive_commands_succeeded=False,
        all_required_original_archives_satisfied=False,original_archived_before_release=False,owned_release=[],
        unit_released=False,lifecycle_complete=False,payload_retried=False,actual_exit_or_signal_normalized=False,
        signals_sent_to_PID=False,live_or_unknown_processes_controlled=False,review_report_absent=True,
        raw_model_GPU_native_source_or_original_metadata_changes=False,error=None)
    try:
        for kind,unit in(('service',UNIT),('timer',owner['timer'])):
            for action in('show','cat','journal'):
                invocation=owner['invocation_id'if kind=='service'else'timer_invocation_id']
                argv=['journalctl','--user','--no-pager','-o','short-iso','_SYSTEMD_INVOCATION_ID='+invocation]if action=='journal'else['systemctl','--user',action,unit]
                receipt=u.command(out,'original-'+kind+'-'+action,argv)
                record['full_original_archives'].append(receipt)
                record['original_archive_status'].append(dict(kind=kind,action=action,exit=receipt['exit'],timed_out=receipt['timed_out']))
        archives=record['full_original_archives'];require(len(archives)==6,'All six original archives required before release')
        terminal(ctx,u.fields(archives[0]));timer_state=u.timer_state(u.fields(archives[3]),ctx['timer_context'])
        record.update(all_six_original_archive_commands_succeeded=all(r['exit']==0 for r in archives),terminal_timer_state=timer_state)
        require(all(r['exit']==0 and r['timed_out']is False for r in archives[:3])and archives[5]['exit']==0
            and archives[5]['timed_out']is False and archives[4]['exit']in(0,1)and archives[4]['timed_out']is False,
            'Unexpected original archive failure; no release')
        if archives[4]['exit']!=0:
            fresh=u.command(out,'original-timer-GC-confirm-show',['systemctl','--user','show',owner['timer']])
            record['timer_GC_confirmation']=fresh;require(u.timer_state(u.fields(fresh),ctx['timer_context'])=='absent','Timer cat failure lacks fresh original absence')
        record.update(all_required_original_archives_satisfied=True,original_archived_before_release=True)
        u.publish(out/'exact-original-terminal-archive-before-release.json',record)
        ownership_check(ctx)
        for kind in('timer','service'):
            row={};record['owned_release'].append(row)
            u.release_original(out,kind,owner,ctx['timer_context'],row)
        require(all(row['confirmed_absent']for row in record['owned_release']),'Both exact original units must be confirmed absent')
        for unit in(UNIT,owner['timer']):require(u.show(unit)['LoadState']=='not-found','Exact original unit remains')
        require(birth(PID)!=BIRTH and not Path('/sys/fs/cgroup'+ctx['cgroup']).exists(),'Original process/cgroup remains after release')
        controller_absent(ctx)
        record.update(status='ORIGINAL_TIMEOUT_SIGNAL15_ARCHIVED_AND_EXACT_OWNED_UNITS_RELEASED',unit_released=True,lifecycle_complete=True)
    except Exception as error:
        record.update(status='ORIGINAL_TIMEOUT_SIGNAL_PRESERVED_RECOVERY_INCOMPLETE',error=repr(error))
    record['ended_unix_s']=time.time();pin=u.publish(out/'root-original-timeout-signal-and-owned-release.json',record)
    print(json.dumps(dict(status=record['status'],receipt=pin,unit_released=record['unit_released'])),flush=True)
    return 0 if record['lifecycle_complete']else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group();mode.add_argument('--check',action='store_true');mode.add_argument('--execute',action='store_true')
    p.add_argument('--manifest',type=Path);p.add_argument('--manifest-sha256');p.add_argument('--expected-source-sha256');args=p.parse_args()
    if not(args.check or args.execute):print('PLAN_ONLY_NO_READS_OR_ACTIONS');return 0
    require(args.manifest and args.manifest_sha256 and args.expected_source_sha256,'Exact root-selected manifest/source arguments required')
    if args.check:print(json.dumps(check(args),indent=2));return 0
    return execute(args)

if __name__=='__main__':raise SystemExit(main())
