"""Independently close a passed metadata-only2CPU/4GiB/600s engineering scope."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def require(value,reason):
    if not value:raise ValueError(reason)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def close(directory):
    h=load('_metadata_scope_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    directory=directory.resolve();cfg_pin=h.pin(directory/'controller-config.json');cfg=json.loads(h.checked(cfg_pin).read_bytes())
    job_pin=h.pin(directory/'job.json');job=json.loads(h.checked(job_pin).read_bytes())
    control=load('_metadata_scope_control',Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/durable-e078-selected-context600-original01-preparation/control_metadata600_v1.py'))
    require(control.checked_config(cfg_pin['path'])==cfg,'Actual selected CPU configuration differs')
    require(cfg['properties']==['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=600','TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no']
            and cfg['observation_s']==660,'Exact bounded CPU declaration required')
    require(cfg['unit']==job['unit']and cfg['argv'][0:3]==['/usr/bin/python3','-I','-B']
            and cfg['argv'][4:8]==['--execute','--job',job_pin['path'],'--job-sha256']
            and cfg['argv'][8]==job_pin['sha256'],'Actual job/argv differs')
    for pin in job['inputs']:h.checked(pin)
    require('--source-sha256'in cfg['argv']and h.pin(cfg['argv'][3])['sha256']==cfg['argv'][-1],'Actual CPU driver source differs')
    root=Path(cfg['output']);owner_pin=h.pin(root/'root-original-identity.json');closure_pin=h.pin(root/'root-original-result-and-owned-release.json')
    immutable=load('_metadata_scope_immutable',ROOT/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    def read(pin,as_json=True):
        return immutable.read_pin(pin,as_json=as_json)
    owner=read(owner_pin);closure=read(closure_pin)
    archive=load('_metadata_scope_archive',ROOT/'tools/eval_capacity_proposal/review_original_pilot_score_carry_v1.py')
    terminal=archive.archived_closure(closure,owner,read,exit_zero=True)
    live_command=read(h.pin(root/'original-first-observed-show-command.json'))
    live=dict(line.split('=',1)for line in read(live_command['stdout'],False).decode().splitlines()if'='in line)
    expected=dict(Id=cfg['unit'],MainPID=str(owner['pid']),InvocationID=owner['invocation_id'],CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='10min',TasksMax='128',TimeoutStopUSec='5s',SendSIGKILL='no',Restart='no',NRestarts='0')
    require(all(live.get(k)==v for k,v in expected.items()),'Actual original live owner/resources differ')
    require(all(token in terminal['ExecStart']for token in cfg['argv'])and'CUDA_VISIBLE_DEVICES='in terminal['ExecStart'],'Actual source/CPU isolation/argv differs')
    proc=Path('/proc',str(owner['pid']),'stat')
    require(not proc.exists()or int(proc.read_text().rsplit(')',1)[1].split()[19])!=owner['starttime_ticks'],'Original CPU birth remains')
    require(all(control.show(unit)['LoadState']=='not-found'for unit in (owner['unit'],owner['timer'])),'Owned unit/timer remains')
    require(not Path('/sys/fs/cgroup'+live['ControlGroup']).exists(),'Original cgroup remains')
    report_pin=h.pin(Path(job['output'])/'report.json');report=read(report_pin)
    require(report['status']=='PASS'and report['actual_PID']==owner['pid']and report['original_job']==job_pin
            and report['Torch_imported']is report['GPU_or_MAME_launched']is False,'Actual engineering outcome differs')
    require(report.get('quality_qualified',False)is report.get('promotion',False)is False,'Engineering cannot qualify or promote')
    return h.put(directory/'independent-original-CPU-scope-closeout.json',dict(schema='robotron-engineering-original-CPU-independent-closeout-v1',status='PASS_ENGINEERING_ONLY',
        original_job=job_pin,original_config=cfg_pin,original_owner=owner_pin,original_closure=closure_pin,actual_report=report_pin,
        actual_exit=0,actual_CPU_cores=2,actual_memory_bytes=4<<30,actual_runtime_limit_s=600,
        all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified=True,
        source=h.pin(Path(__file__).resolve()),scientific_launch_qualified=False,quality_qualified=False,promotion=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--close',action='store_true');parser.add_argument('--directory',type=Path);args=parser.parse_args()
    if args.close:print(json.dumps(close(args.directory)),flush=True)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
