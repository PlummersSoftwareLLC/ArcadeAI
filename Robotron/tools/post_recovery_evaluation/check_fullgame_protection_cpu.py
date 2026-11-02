"""Bounded protection gate/publisher-fixture tests; never publish a real policy."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import unittest


def require(value,reason):
    if not value:raise ValueError(reason)


def execute(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Actual protection CPU driver differs')
    require(hashlib.sha256(args.job.read_bytes()).hexdigest()==args.job_sha256,'Actual original protection CPU job differs')
    job=json.loads(args.job.read_bytes());require(job['engineering_only']is True and job['original_attempt']==1 and job['no_retry']is True,'One original metadata CPU job required')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and'torch'not in sys.modules,'CPU only required')
    path=Path(__file__).with_name('fullgame_review_pipeline_v2.py');spec=importlib.util.spec_from_file_location('_protection_CPU_pipeline',path)
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p);h=p.helpers()
    fields=dict(line.split('=',1)for line in subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=5).splitlines()if'='in line)
    expected=dict(MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='3min',TasksMax='128',Restart='no',NRestarts='0')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual2CPU/4GiB/180s protection guard scope differs')
    started=time.monotonic()
    for pin in job['inputs']:h.checked(pin)
    sys.path.insert(0,str(p.ROOT.parent));suite=unittest.defaultTestLoader.loadTestsFromName('Robotron.tools.post_recovery_evaluation.test_fullgame_winner_protection')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    require(result.wasSuccessful()and result.testsRun==6,'Actual protection gate/fixture suite failed: '+stream.getvalue())
    for pin in job['inputs']:h.checked(pin)
    require('torch'not in sys.modules,'Numerical runtime imported')
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=h.put(output/'report.json',dict(schema='robotron-fullgame-protection-guards-CPU-result-v1',status='PASS',original_job=h.pin(args.job),
        actual_PID=os.getpid(),actual_scope=fields,tests_run=result.testsRun,invalid_header_vectors=12,test_output=stream.getvalue(),
        elapsed_s=time.monotonic()-started,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        Torch_imported=False,GPU_or_MAME_launched=False,real_protected_policy_published=False,
        synthetic_tiny_publication_fixtures_only=True,positive_production_verifier_exercised=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(status='PASS',tests=result.testsRun,report=report)),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--execute',action='store_true');a.add_argument('--job',type=Path)
    a.add_argument('--job-sha256');a.add_argument('--source-sha256');args=a.parse_args()
    if args.execute:execute(args)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
