"""Independently close one original reconnect engineering parent and worker.

Only an already exited, exact owned parent may be stopped. Actual nonzero
exits never qualify. This is engineering evidence, never gameplay authority.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def show(unit):
    result=subprocess.run(['systemctl','--user','show',unit],capture_output=True,text=True,timeout=10)
    require(result.returncode==0,'Original parent observation failed')
    return dict(line.split('=',1)for line in result.stdout.splitlines()if'='in line)


def close(index,expected_sha,kind,mode):
    helper=ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    require(hashlib.sha256(helper.read_bytes()).hexdigest()=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1','Original helper changed')
    h=load('_reconnect_engineering_close_helpers',helper);ip=h.pin(index.resolve())
    require(ip['sha256']==expected_sha,'Exact original engineering launch index required')
    immutable=load('_reconnect_engineering_close_reader',ROOT/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    def read(pin):return immutable.read_pin(pin)
    packet=read(ip);require(packet['schema']=='robotron-static192-countbounded-long-original-engineering-launches-v2','Original launch index schema differs')
    records=[row for row in packet['records']if row['kind']==kind and row['mode']==mode]
    require(len(records)==1,'One exact original engineering scope required')
    record=records[0];out=Path(record['output']);owner=read(record['original_live_owner']);intent=read(record['intent'])
    require(owner['unit']==record['unit']==intent['unit']and intent['schema']=='robotron-static192-countbounded-long-original-engineering-intent-v2'and mode=='long'and intent['attempt']==1 and intent['no_retry']is True
            and intent['engineering_only']is True,'Original parent/source ownership differs')
    require(not(out/'independent-original-engineering-closeout.json').exists(),'Original engineering closeout already consumed')
    for pin in intent['sources'].values():h.checked(pin)
    fields=show(owner['unit'])
    expected=dict(Id=owner['unit'],MainPID='0',ExecMainPID=str(owner['pid']),InvocationID=owner['invocation_id'],
        ExecMainCode='1',ExecMainStatus='0',NRestarts='0',Restart='no',CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),
        MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='30min',TimeoutStopUSec='5s',SendSIGKILL='no')
    require(all(fields.get(key)==value for key,value in expected.items()),'Original parent has not exited0 in its declared resources')
    require(birth(owner['pid'])!=owner['birth'],'Original parent birth remains')
    argv=intent['argv'];start=argv.index('/usr/bin/env')
    require(' '.join(argv[start:])+' ; ignore_errors=no ;'in fields['ExecStart'],'Actual original parent runtime argv differs')
    terminal=h.put(out/'original-terminal-properties.json',fields)
    reportpin=h.pin(out/'runtime/result.json');report=read(reportpin)
    require(report['schema']=='robotron-static192-health-countbounded-native-interface-probe-v2'and report['status']=='PASS_ENGINEERING_INTERFACE_ONLY'and report['mode']==mode
            and report['private_policy_or_GPU_loaded']is report['main_runtime_changed']is report['quality_qualified']is False,
            'Actual engineering result/domain differs')
    require(report['scientific_launch_qualified']is False,'Engineering cannot qualify a scientific launch')
    require(report['proof_gap_contract']=='robotron-main-proof-gap-2s-v1'and report['maximum_gap_s']==2.0
            and report['main_health_profile']=='STATIC_ORIGINAL192_NO_FAULT_ADOPTION'
            and report['simultaneous192_actors_claimed']is False,'Exact prospective static2s report required')
    require(report['long_work_contract']=='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S'
            and report['long_minimum_work_s']==600 and report['long_maximum_work_s']==1200
            and report['long_minimum_observed_samples']==3000
            and type(report['actual_long_work_s'])in(int,float)and 600<=report['actual_long_work_s']<=1200
            and type(report['last_validated_long_count'])is int and report['last_validated_long_count']>=3000,
            'Original long did not satisfy both600s and3000validated samples within1200s')
    native=read(report['original_job']);require(native['main_binding']==intent['case'],'Original case binding differs')
    lifecycle=read(report['observer_lifecycle']);worker=read(lifecycle['worker_job']);outcome=read(lifecycle['outcome'])
    actual_worker=read(outcome['owner']);worker_terminal=read(lifecycle['terminal_properties'])
    require(worker['schema']=='robotron-continuous-static192-observer-proof2s-job-v1'and worker['maximum_gap_s']==2.0
            and worker['interval_s']==.2 and worker['initial_samples']==100,'Exact prospective2s worker bounds required')
    require(lifecycle['all_original_processes_reaped']is lifecycle['original_scope_released']is lifecycle['launcher_birth_absent']is True,
            'Original worker/launcher did not positively close')
    require(birth(actual_worker['pid'])!=actual_worker['birth']
            and show(actual_worker['unit'])['LoadState']=='not-found'
            and not Path('/sys/fs/cgroup'+actual_worker['cgroup']).exists(),'Original worker scope remains')
    require(worker['parent']['pid']==owner['pid']and worker['parent']['birth']==owner['birth']
            and worker['parent']['invocation_id']==owner['invocation_id'],'Original worker parent join differs')
    require(outcome['all_writer_threads_stopped']is True and outcome['uncommitted_raw']==[]
            and outcome['queued_samples']==len(outcome['samples'])and outcome['queued_unaccepted']==len(outcome['unaccepted']),
            'Original queued raw records did not all durably close')
    release=read(outcome['control_release'])
    require(release['directory_absent']is True and not Path(release['original']['path']).exists(),'Original tmpfs control remains')
    if mode in ('warmup','long'):
        reviewed=report['independently_replayed_raw_review']
        require(reviewed['status']=='PASS'and reviewed['accepted_samples']>=(3000 if mode=='long' else 101)
                and reviewed['queued_publication_byte_joins_verified']is reviewed['fresh_final_sample_verified']
                is reviewed['accepted_evidence_and_projection_gaps_verified']is True
                and reviewed['proof_gap_contract']=='robotron-main-proof-gap-2s-v1'and reviewed['verified_maximum_gap_s']==2.0
                and reviewed['main_health_profile']=='STATIC_ORIGINAL192_NO_FAULT_ADOPTION'
                and reviewed['TRAIN155_originals_and_EVAL37_once_partition_verified']is True
                and outcome['success']is True and outcome['error']is None
                and worker_terminal['ExecMainCode']=='1'and worker_terminal['ExecMainStatus']=='0',
                'Original long probe/raw replay did not pass')
    else:
        require(report['independently_replayed_raw_review']is None and outcome['success']is False
                and worker_terminal['ExecMainCode']=='1'and worker_terminal['ExecMainStatus']=='1'
                and lifecycle['success']is False,'Original worker abort exit1 was not preserved')
    command=['systemctl','--user','stop',owner['unit']]
    stopped=subprocess.run(command,capture_output=True,text=True,timeout=10)
    stop=h.put(out/'original-owned-stop-command.json',dict(argv=command,returncode=stopped.returncode,stdout=stopped.stdout,stderr=stopped.stderr))
    require(stopped.returncode==0,'Original exited parent could not be released')
    after=show(owner['unit'])
    require(after['LoadState']=='not-found'and not Path('/sys/fs/cgroup'+owner['properties']['ControlGroup']).exists(),
            'Original parent unit/cgroup remains')
    console=out/'console.txt';fd=os.open(console,os.O_RDONLY|os.O_NOFOLLOW)
    try:os.fchmod(fd,0o444);os.fsync(fd)
    finally:os.close(fd)
    return h.put(out/'independent-original-engineering-closeout.json',dict(
        schema='robotron-static192-countbounded-long-original-engineering-closeout-v2',status='PASS_ENGINEERING_ONLY',
        kind=kind,mode=mode,launch_index=ip,original_live_owner=record['original_live_owner'],parent_terminal=terminal,
        owned_stop=stop,released_properties=after,actual_probe_result=reportpin,worker_lifecycle=report['observer_lifecycle'],
        accepted_samples=len(outcome['samples']),unaccepted_samples=len(outcome['unaccepted']),worker_actual_exit=0 if mode in ('warmup','long')else 1,
        original_parent_actual_exit=0,all_original_births_units_cgroups_and_tmpfs_control_absent=True,
        actual_parent_CPU_cores=2,actual_parent_memory_bytes=4<<30,actual_parent_runtime_s=1800,
        long_work_contract=report['long_work_contract'],actual_long_work_s=report['actual_long_work_s'],
        last_validated_long_count=report['last_validated_long_count'],
        source=h.pin(Path(__file__).resolve()),scientific_qualification=False,quality_qualified=False,promotion=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--index',type=Path);parser.add_argument('--index-sha256');parser.add_argument('--kind',choices=('main-static192',))
    parser.add_argument('--mode',choices=('long',));args=parser.parse_args()
    if args.execute:print(json.dumps(close(args.index,args.index_sha256,args.kind,args.mode)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
