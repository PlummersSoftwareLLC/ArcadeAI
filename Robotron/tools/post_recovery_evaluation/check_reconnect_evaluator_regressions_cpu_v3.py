"""Run reconnect-family promotion/refusal regressions without gameplay."""
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

ROOT=Path(__file__).resolve().parents[2]
TESTS=['test_fullgame_preparation_v6','test_fullgame_sequence_v8','test_fullgame_review_pipeline_v7',
       'test_fullgame_winner_protection_v6','test_fullgame_reference_adoption_v6',
       'test_fullgame_review_source_reader_v6','test_reconnect_evaluator_contracts_v3']


def execute(a):
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
    raw=a.job.read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256
    job=json.loads(raw)
    assert os.environ['CUDA_VISIBLE_DEVICES']=='' and 'torch' not in sys.modules
    path=ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    spec=importlib.util.spec_from_file_location('_reconnect_regression_h',path)
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    for pin in job['inputs']:h.checked(pin)
    sys.path.insert(0,str(ROOT.parent));suite=unittest.TestSuite()
    for name in TESTS:suite.addTests(unittest.defaultTestLoader.loadTestsFromName('Robotron.tools.post_recovery_evaluation.'+name))
    started=time.monotonic();capture=io.StringIO()
    result=unittest.TextTestRunner(stream=capture,verbosity=2).run(suite)
    for pin in job['inputs']:h.checked(pin)
    assert 'torch' not in sys.modules
    out=Path(job['output']);out.mkdir(mode=0o700)
    h.put(out/'report.json',dict(schema='robotron-reconnect-evaluator-promotion-regression-result-v1',
        status='PASS'if result.wasSuccessful()else'FAIL',original_job=h.pin(a.job),actual_PID=os.getpid(),
        tests_run=result.testsRun,test_output=capture.getvalue(),elapsed_s=time.monotonic()-started,
        Torch_imported=False,GPU_or_MAME_launched=False,scientific_launch_qualified=False,quality_qualified=False,promotion=False))
    print(capture.getvalue(),flush=True)
    return 0 if result.wasSuccessful()else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--job',type=Path);p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
    if a.execute:raise SystemExit(execute(a))
    print('PLAN_ONLY_NO_READS_OR_ACTIONS')
