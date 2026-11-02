"""Observe original post-reboot pair closure only after tool50607 terminates.

Default inert. This is an ownership/resource check, not a score or policy
qualification. Never signal, adopt, restart, release or retry an owner here.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
CASE=G/'logs/managed-learning-20261015/run-26/post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
HELPER=G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
READER=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
ARCHIVE=G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
CGROUP=Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice')
RETAINED={
    'trainer':dict(pid=599082,birth=1650370,unit='robotron-trainer.service',invocation='bd90079895534cbb9c0813cebe1f6e8c'),
    'fleet':dict(pid=604589,birth=1680519,unit='robotron-mame.service',invocation='d319a04ef7c3497fbe7040d3349e8b51')}


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path,sha):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Selected dependency changed')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def validate_terminal_record(record):
    require(type(record.get('original_tool_session')) is int and record['original_tool_session']==50607
        and record.get('original_tool_terminal_observed') is True,
        'Root must actually observe the original tool50607 terminal; files/timeouts are insufficient')
    result=record.get('actual_tool_result',{})
    require(type(result.get('exit_code')) is int and result['exit_code']==0
        and result.get('session_id') is None,'Original tool must actually return exit0 without a running session')


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except (FileNotFoundError,ProcessLookupError):return None


def absent(owners):
    rows=[]
    for owner in owners:
        current=birth(owner['pid'])
        require(current!=owner['birth'],'An original pair process remains live')
        rows.append(dict(**owner,observed_birth=current,original_birth_absent=True))
    return rows


def retained():
    records={}
    for key,owner in RETAINED.items():
        require(birth(owner['pid'])==owner['birth'],'A retained trainer/fleet incarnation changed')
        result=subprocess.run(['systemctl','--user','show',owner['unit'],
            '--property=Id,MainPID,InvocationID,ActiveState,ControlGroup,NRestarts'],capture_output=True,text=True,timeout=10)
        fields=dict(line.split('=',1)for line in result.stdout.splitlines()if'='in line)
        require(result.returncode==0 and fields['Id']==owner['unit'] and fields['MainPID']==str(owner['pid'])
            and fields['InvocationID']==owner['invocation'] and fields['ActiveState']=='active' and fields['NRestarts']=='0'
            and fields['ControlGroup']==str(CGROUP/owner['unit']).removeprefix('/sys/fs/cgroup')
            and birth(owner['pid'])==owner['birth'],'Retained exact unit identity differs')
        records[key]=dict(owner=owner,fields=fields)
    return records


def verify(terminal_pin,h,reader,archive):
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    terminal=read(terminal_pin);validate_terminal_record(terminal)
    prepared_pin=h.pin(CASE/'prepared.json');prepared=read(prepared_pin)
    selected=read(prepared['selection']);configs=read(prepared['controller_configs'])
    require(prepared['ordered_legs']==configs['ordered_legs']==['R1','C1'],'Exact original pair required')
    sequence=read(h.pin(CASE/'original-sequence-child.json'))
    exit_pin=h.pin(CASE/'original-sequence-actual-exit.json');exit_record=read(exit_pin)
    require(type(exit_record['actual_exit']) is int and exit_record['actual_exit']==0
        and exit_record['original_Popen_reaped'] is True
        and exit_record['original_pid']==sequence['pid'] and exit_record['original_birth']==sequence['birth'],
        'Sole original Popen owner must have reaped its actual child0')
    outer_pin=h.pin(CASE/'Root-controller-runtime-original01/result.json');outer=read(outer_pin)
    require(type(outer['actual_exit']) is int and outer['actual_exit']==0 and outer['error'] is None
        and outer['legs']==['R1','C1'] and outer['reporter_thread_closed'] is True
        and outer['report_update_errors']==[] and outer['native_or_original_controller_retried'] is False,
        'Clean original outer result and actual reporter closure required')
    wrapper=read(h.pin(CASE/'original-sequence-launch-intent.json'))
    require(sequence['argv']==wrapper['argv'] and sequence['pid']==629745 and sequence['birth']==1777464,
        'Selected original outer differs')
    owners=[dict(role='outer',pid=sequence['pid'],birth=sequence['birth'])]
    # Parent birth must come from the Root tool-exit observation, not a lookup
    # after it exits or an inferred value from a missing process.
    parent=terminal['original_wrapper_owner']
    wrapper_owner_pin=h.pin(CASE/'original-wrapper-owner-observed-live-original01.json')
    wrapper_owner=read(wrapper_owner_pin)
    require(parent['pid']==sequence['parent_pid'] and type(parent['birth']) is int and parent['birth']>0,
        'Root-held original wrapper PID/birth required')
    require(all(parent[key]==wrapper_owner[key] for key in ('pid','birth'))
        and wrapper_owner['same_original_birth_bracketed_live'] is True,
        'Original wrapper birth must match its retained live observation')
    owners.append(dict(role='Popen_wrapper',pid=parent['pid'],birth=parent['birth']))
    closures={};lease=None
    for leg in ('R1','C1'):
        job_pin=prepared['jobs'][leg]['job'];job=read(job_pin)
        config=read(configs['configs'][leg]);output=Path(config['output'])
        owner=read(h.pin(output/'root-original-identity.json'))
        closure_pin=h.pin(output/'root-original-result-and-owned-release.json');closure=read(closure_pin)
        fields=archive.archived_closure(closure,owner,read,exit_zero=True)
        require(config['argv']==prepared['jobs'][leg]['argv'] and config['argv'][7]==job_pin['path']
            and config['argv'][9]==job_pin['sha256'],'Actual original config/job argv differs')
        expected=dict(CPUQuotaPerSecUSec='12s',MemoryMax=str(24<<30),MemorySwapMax='0',
            RuntimeMaxUSec='1h 11min',TasksMax='512',TimeoutStopUSec='30s',KillMode='mixed',SendSIGKILL='no',Restart='no')
        require(all(fields.get(k)==v for k,v in expected.items()),'Original resource bounds differ')
        command='/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR='+str(output/'tmp')+' '+' '.join(config['argv'])
        require(command+' ; ignore_errors=no ;'in fields['ExecStart'],'Actual scoped payload command differs')
        result_pin=h.pin(Path(job['output'])/'result.json');result=read(result_pin)
        require(result['original_job']==job_pin and result['complete'] is True and result['errors']==[]
            and result['all_original_threads_stopped'] is result['original_lease_released'] is True
            and result['original_post_origin_child_reap']['all_original_children_reaped'] is True
            and result['immutable_inputs_unchanged'] is True,'Original native/writer/reap closure differs')
        require(job['current_main']==selected['current_main'] and result['current_main']==job['current_main']
            and result['lease']['owner_pid']==owner['pid'] and result['lease']['owner_birth']==owner['starttime_ticks'],
            'Original native/lease/Main binding differs')
        require(job['actor_slots']==list(range(4096,4128))
            and set(result['original_slots'])=={str(s)for s in job['actor_slots']},'All32 selected original actors required')
        owners.append(dict(role='native',leg=leg,pid=owner['pid'],birth=owner['starttime_ticks']))
        for slot in job['actor_slots']:
            actor=read(h.pin(Path(job['output'])/'actors'/str(slot)/'original-actor.json'))
            final=result['original_slots'][str(slot)];reaped=result['original_post_origin_child_reap']['original_children'][str(slot)]
            require(actor['slot']==slot and actor['original_job']==job_pin
                and actor['session']==job['sessions'][str(slot)] and actor['connection']==job['connections'][str(slot)]
                and actor['pid']==final['pid']==reaped['pid']
                and actor['starttime_ticks']==final['birth']==reaped['birth']
                and type(final['actual_exit']) is int and final['actual_exit']==reaped['actual_exit']
                and final['outputs_sealed_after_original_writer_closure'] is True,
                'Original actor identity or actual child exit differs')
            owners.append(dict(role='MAME',leg=leg,slot=slot,pid=actor['pid'],birth=actor['starttime_ticks'],actual_exit=final['actual_exit']))
        for pin in job['inputs']:h.checked(pin)
        h.checked(result['acquired_checkpoint'])
        if lease is None:lease=job['lease']
        require(job['lease']==lease==result['lease']['coordinator'],'Both arms must use the same original coordinator')
        closures[leg]=dict(native=result_pin,closure=closure_pin,owner=owner)
    require(len(owners)==len({(r['pid'],r['birth'])for r in owners})==68,'All68 distinct original owners required')
    before=absent(owners);retained_before=retained();units={}
    for proof in closures.values():
        for unit in (proof['owner']['unit'],proof['owner']['timer']):
            command=subprocess.run(['systemctl','--user','show',unit,'--property=Id,LoadState'],capture_output=True,text=True,timeout=10)
            values=dict(line.split('=',1)for line in command.stdout.splitlines()if'='in line)
            require(command.returncode==0 and values==dict(Id=unit,LoadState='not-found')
                and not (CGROUP/unit).exists(),'An original unit/cgroup remains')
            units[unit]=values
    require(h.pin(lease['path'])==lease,'Original coordinator identity changed')
    fd=os.open(lease['path'],os.O_RDWR|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(h.pin(lease['path'])==lease,'Coordinator changed while probed')
        fcntl.flock(fd,fcntl.LOCK_UN)
    finally:os.close(fd)
    after=absent(owners);retained_after=retained()
    return dict(status='PASS_ORIGINAL_PAIR_TOOL_PROCESSES_UNITS_AND_LEASE_CLOSED',
        observed_unix_s=time.time(),terminal_record=terminal_pin,prepared=prepared_pin,
        original_wrapper_exit=exit_pin,outer_result=outer_pin,legs=closures,
        original_wrapper_live_observation=wrapper_owner_pin,
        original_owner_count=68,absent_before=before,absent_after=after,
        retained_before=retained_before,retained_after=retained_after,units=units,original_coordinator=lease,
        score_validation_performed=False,raw_gameplay_qualified=False,promotion=False,
        signals_stops_restarts_or_retries_performed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--terminal-record',type=Path)
    parser.add_argument('--terminal-record-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Exact selected checker source SHA required')
    require(args.terminal_record is not None and args.terminal_record.parent==CASE,'Exact case-local Root terminal record required')
    h=load('_pair_close_h',HELPER,'2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    pin=h.pin(args.terminal_record);require(pin['sha256']==args.terminal_record_sha256,'Exact Root terminal observation SHA required')
    reader=load('_pair_close_reader',READER,'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    archive=load('_pair_close_archive',ARCHIVE,'2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
    result=verify(pin,h,reader,archive)
    out=h.put(CASE/'Root-original50607-positive-closure-original01.json',result)
    print(json.dumps(dict(status=result['status'],report=out)))
    return 0


if __name__=='__main__':raise SystemExit(main())
