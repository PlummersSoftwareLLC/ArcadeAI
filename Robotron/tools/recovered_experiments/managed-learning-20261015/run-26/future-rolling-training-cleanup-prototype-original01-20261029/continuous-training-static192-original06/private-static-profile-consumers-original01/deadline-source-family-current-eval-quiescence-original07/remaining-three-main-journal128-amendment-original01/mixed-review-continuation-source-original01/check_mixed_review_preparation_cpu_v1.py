"""Bounded original CPU-only independent review preparation regressions."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def execute(args):
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-deadline-review-preparation-CPU-engineering-job-v1'
    assert os.environ['CUDA_VISIBLE_DEVICES']=='' and 'torch' not in sys.modules
    spec=importlib.util.spec_from_file_location('_deadline_review_CPU_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    source=h.checked(job['mixed_review_preparer'])
    spec=importlib.util.spec_from_file_location('_mixed_review_actual_metadata_inputs',source)
    mixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(mixed)
    assert mixed.metadata_input_classification(job['inputs'],h)==job['metadata_input_classification']
    os.environ['ROBOTRON_DEADLINE_REVIEW_TEST_PRECOMMIT']=job['review_precommit']['path']
    sys.path.insert(0,str(ROOT.parent));output=io.StringIO();started=time.monotonic()
    test_path=Path(__file__).with_name('test_mixed_review_preparation_v1.py')
    test_pin=h.pin(test_path);assert test_pin['sha256']=='9b51bf6b942b5f57d039ed617a0dfee3df2510ec5b4ada0140ba56a2140b1a88'
    spec=importlib.util.spec_from_file_location('_actual_launcher_review_tests',test_path)
    tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
    suite=unittest.defaultTestLoader.loadTestsFromModule(tests)
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    assert mixed.metadata_input_classification(job['inputs'],h)==job['metadata_input_classification']
    assert result.wasSuccessful() and result.testsRun==6,output.getvalue()
    directory=Path(job['output']);directory.mkdir(mode=0o700)
    h.put(directory/'report.json',dict(schema='robotron-deadline-review-preparation-CPU-engineering-result-v1',status='PASS',
        original_job=h.pin(Path(args.job)),actual_PID=os.getpid(),tests_run=result.testsRun,test_output=output.getvalue(),
        review_precommit=job['review_precommit'],mixed_review_preparer=job['mixed_review_preparer'],
        metadata_input_classification=job['metadata_input_classification'],
        elapsed_s=time.monotonic()-started,Torch_imported='torch'in sys.modules,GPU_or_MAME_launched=False,
        scientific_launch_qualified=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(status='PASS',tests_run=result.testsRun)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if args.execute:execute(args)
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
