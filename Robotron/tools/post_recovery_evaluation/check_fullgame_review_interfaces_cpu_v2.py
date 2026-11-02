"""One metadata-only four-review interface and numerical-gate CPU check.

Uses the actual future reviewer resource declaration (2CPU/4GiB/1980s maximum).
No original scientific review, MAME, Torch, GPU, quality qualification or retry.
"""
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


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def execute(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256,'Actual CPU driver differs')
    require(hashlib.sha256(args.job.read_bytes()).hexdigest()==args.job_sha256,'Actual original CPU job differs')
    job=json.loads(args.job.read_bytes());require(job['original_attempt']==1 and job['no_retry']is True,'One original CPU attempt required')
    require(os.environ.get('CUDA_VISIBLE_DEVICES')==''and'torch'not in sys.modules,'CPU-only metadata process required')
    p=load('_fullgame_review_CPU_pipeline',Path(__file__).with_name('fullgame_review_pipeline_v2.py'));h=p.helpers()
    fields=dict(line.split('=',1)for line in subprocess.check_output(['systemctl','--user','show',job['unit']],text=True,timeout=5).splitlines()if'='in line)
    expected=dict(MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],CPUQuotaPerSecUSec='2s',MemoryMax=str(4<<30),MemorySwapMax='0',RuntimeMaxUSec='33min',TasksMax='128',NRestarts='0',Restart='no')
    require(all(fields.get(k)==v for k,v in expected.items()),'Actual2CPU/4GiB/1980s bounded review scope differs')
    started=time.monotonic()
    for pin in job['inputs']:h.checked(pin)
    commit=p.read(job['review_precommit']);prepared=p.read(commit['native_prepared'])
    require(commit['engineering_only']is prepared['engineering_only']is True,'Metadata engineering domain required')
    native=load('_fullgame_review_CPU_actual_native',p.HERE/'run_fullgame_rounds_v2.py')
    contexts=[]
    for case in prepared['cases']:
        subject=p.read(case['native_job']);ctx=native.validate_completed_context(subject,h)
        require(ctx['pair']['engineering_only']is True,'Engineering context required')
        contexts.append(dict(leg=case['leg'],native_job=case['native_job'],actual_native_prebody_valid=True))
    sys.path.insert(0,str(p.ROOT.parent))
    suite=unittest.defaultTestLoader.loadTestsFromNames(['Robotron.tools.post_recovery_evaluation.test_fullgame_review_pipeline_v2','Robotron.tools.post_recovery_evaluation.test_fullgame_review_source_reader','Robotron.tools.post_recovery_evaluation.test_fullgame_sequence_v3'])
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    require(result.wasSuccessful()and result.testsRun==22,'Actual metadata/gate regression suite failed: '+stream.getvalue())
    for pin in job['inputs']:h.checked(pin)
    require('torch'not in sys.modules,'Numerical runtime imported')
    output=Path(job['output']);output.mkdir(mode=0o700)
    report=h.put(output/'report.json',dict(schema='robotron-fullgame-source-reader-integration-CPU-result-v1',status='PASS',
        original_job=h.pin(args.job),actual_PID=os.getpid(),actual_scope=fields,actual_native_contexts=contexts,
        tests_run=result.testsRun,numerical_mutation_cases=13,review_packet_mutation_cases=10,test_output=stream.getvalue(),
        elapsed_s=time.monotonic()-started,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        Torch_imported=False,GPU_or_MAME_launched=False,actual_scientific_reviews_exercised=False,
        positive_production_final_assessment_exercised=False,historical_numerical_replay_only=True,
        full_game_quality_qualified=False,promotion=False))
    print(json.dumps(dict(status='PASS',tests=result.testsRun,contexts=len(contexts),report=report)),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--execute',action='store_true');a.add_argument('--job',type=Path)
    a.add_argument('--job-sha256');a.add_argument('--source-sha256');args=a.parse_args()
    if args.execute:execute(args)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
