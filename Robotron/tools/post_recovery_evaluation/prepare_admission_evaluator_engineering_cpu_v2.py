"""Prepare inert nine-source admission evaluator contexts in one bounded CPU scope."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module


def execute(args):
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=args.job.read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw)
    assert os.environ['CUDA_VISIBLE_DEVICES']=='' and 'torch' not in sys.modules
    fields=dict(line.split('=',1) for line in subprocess.check_output(
        ['systemctl','--user','show',job['unit']],text=True,timeout=10).splitlines() if '=' in line)
    expected=dict(MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],
        CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',
        RuntimeMaxUSec='3min',NRestarts='0',Restart='no')
    assert all(fields.get(k)==v for k,v in expected.items())
    h=load('_reconnect_evaluator_prepare_h',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    for pin in job['inputs']:h.checked(pin)
    output=Path(job['output']);output.mkdir(mode=0o700);started=time.monotonic()
    deadline=load('_reconnect_evaluator_deadline_prepare',HERE/'prepare_round_study_v10.py')
    dp=deadline.prepare(output/'deadline-four',job['reference_profile'],job['entry_profile'],
        main_domain_proof=job['deadline_readiness'],lease_recovery=job['lease_recovery'],engineering=True)
    dg=load('_reconnect_evaluator_deadline_guard_prepare',HERE/'prepare_round_cpu_guard_v9.py')
    dguard=dg.prepare(Path(dp['path']),output/'deadline-guards-CPU-original01')
    fg=load('_reconnect_evaluator_fullgame_prepare',HERE/'prepare_fullgame_engineering_v7.py')
    fp=fg.prepare(output/'fullgame-two')
    fguard=load('_reconnect_evaluator_fullgame_guard_prepare',HERE/'prepare_fullgame_cpu_guard_v7.py')
    four=fguard.engineering_four(Path(fp['path']),output/'fullgame-four')
    fgp=fguard.prepare(Path(four['path']),output/'fullgame-guards-CPU-original01')
    for pin in job['inputs']:h.checked(pin)
    assert 'torch' not in sys.modules
    h.put(output/'report.json',dict(schema='robotron-reconnect-evaluator-engineering-preparation-result-v1',
        status='PASS',original_job=h.pin(args.job),actual_PID=os.getpid(),actual_scope=fields,
        deadline_prepared=dp,deadline_CPU_packet=dguard,fullgame_two=fp,fullgame_prepared=four,
        fullgame_CPU_packet=fgp,elapsed_s=time.monotonic()-started,Torch_imported=False,
        GPU_or_MAME_launched=False,scientific_launch_qualified=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(status='PASS',deadline_contexts=4,fullgame_contexts=4)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--job',type=Path);p.add_argument('--job-sha256');p.add_argument('--source-sha256')
    a=p.parse_args()
    if a.execute:execute(a)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
