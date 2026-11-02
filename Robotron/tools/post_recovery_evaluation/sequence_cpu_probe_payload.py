"""Short CPU-only success/nonzero probe of the original owned-controller helper."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def require(value,reason):
    if not value:raise ValueError(reason)


def execute(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Actual probe source differs')
    require(hashlib.sha256(args.job.read_bytes()).hexdigest()==args.job_sha256,'Actual probe job differs')
    job=json.loads(args.job.read_bytes());require(job['engineering_only']is True and type(job['expected_exit'])is int
        and job['expected_exit']in (0,17)and job['original_attempt']==1 and job['no_retry']is True,'Exact one-use metadata probe required')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and'torch'not in sys.modules,'CPU-only metadata probe required')
    path=Path(__file__).resolve().parents[1]/'startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    spec=importlib.util.spec_from_file_location('_sequence_probe_helpers',path);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    for pin in job['inputs']:h.checked(pin)
    fields=dict(line.split('=',1)for line in subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=5).splitlines()if'='in line)
    expected=dict(MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',Restart='no',NRestarts='0')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual bounded2CPU/4GiB/180s probe scope differs')
    time.sleep(2)
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=h.put(output/'report.json',dict(schema='robotron-sequence-owned-controller-CPU-probe-result-v1',
        status='PASS'if job['expected_exit']==0 else'EXPECTED_ENGINEERING_NONZERO',original_job=h.pin(args.job),
        actual_PID=os.getpid(),actual_scope=fields,expected_exit=job['expected_exit'],Torch_imported=False,
        GPU_or_MAME_launched=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(report=report,expected_exit=job['expected_exit'])),flush=True)
    return job['expected_exit']


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--execute',action='store_true');a.add_argument('--job',type=Path)
    a.add_argument('--job-sha256');a.add_argument('--source-sha256');args=a.parse_args()
    if args.execute:sys.exit(execute(args))
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
