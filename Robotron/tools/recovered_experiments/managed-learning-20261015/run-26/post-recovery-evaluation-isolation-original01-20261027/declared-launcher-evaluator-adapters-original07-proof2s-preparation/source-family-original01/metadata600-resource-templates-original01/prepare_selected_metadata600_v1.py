"""Prepare one distinct captured-policy study in an original CPU-only scope.

This writes frozen metadata only. Every native leg still needs its own exact
CPU guard and final resource checks before the one original launch.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation')
LOCAL=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-evaluator-adapters-original07-proof2s-preparation/source-family-original01')
ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def execute(a):
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=a.job.read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert job['schema']=='robotron-selected-admission-study-CPU-preparation-v1'
    assert job['original_attempt']==1 and job['no_retry']is True
    assert os.environ['CUDA_VISIBLE_DEVICES']==''and 'torch'not in sys.modules
    fields=dict(x.split('=',1)for x in subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=10).splitlines()if'='in x)
    expected=dict(MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],CPUQuotaPerSecUSec='2s',
        MemoryMax=str(4<<30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='10min',NRestarts='0',Restart='no')
    assert all(fields.get(k)==v for k,v in expected.items())
    h=load('_selected_admission_CPU_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    for pin in job['inputs']:h.checked(pin)
    capture=json.loads(h.checked(job['capture_result']).read_bytes())
    assert capture['state']=='captured_CPU_verified'and capture['endpoint']['sha256']==job['candidate_sha256']
    output=Path(job['output']);output.mkdir(mode=0o700);started=time.monotonic()
    preparer=load('_selected_admission_actual_preparer',LOCAL/'prepare_round_study_v10.py')
    prepared=preparer.prepare(Path(job['study_directory']),job['reference_profile'],job['candidate_profile'],
        main_domain_proof=job['deadline_readiness'],lease_recovery=job['lease_recovery'],engineering=False)
    manifest=json.loads(h.checked(prepared).read_bytes());assert manifest['engineering_only']is False
    study=json.loads(h.checked(manifest['study_precommit']).read_bytes())
    assert study['policies']['candidate']['checkpoint']['sha256']==job['candidate_sha256']
    guard=load('_selected_admission_actual_guard_preparer',LOCAL/'prepare_round_cpu_guard_v9.py')
    cpu=guard.prepare(Path(prepared['path']),Path(job['study_directory'])/'four-exact-contexts-CPU-original01')
    for case in manifest['cases']:
        subject=json.loads(h.checked(case['native_job']).read_bytes())
        assert not Path(subject['output']).exists()and not Path(subject['prelaunch_family_guard_closeout']).exists()
    for pin in job['inputs']:h.checked(pin)
    assert 'torch'not in sys.modules
    report=h.put(output/'report.json',dict(schema='robotron-selected-admission-study-original-CPU-preparation-result-v1',
        status='PASS',original_job=h.pin(a.job),actual_PID=os.getpid(),actual_scope=fields,
        native_prepared=prepared,exact_CPU_packet=cpu,selected_sha256=job['candidate_sha256'],
        elapsed_s=time.monotonic()-started,all_four_native_outputs_and_future_guards_absent=True,
        Torch_imported=False,GPU_or_MAME_launched=False,scientific_payload_launched=False,
        exact_selected_context_CPU_qualified=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(status='PASS_METADATA_ONLY',report=report)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--job',type=Path);p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if a.execute:execute(a)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
