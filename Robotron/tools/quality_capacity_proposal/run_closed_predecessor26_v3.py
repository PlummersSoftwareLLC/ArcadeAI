"""CPU checks for the newly bound closed predecessor; no diagnostic launch."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
A=G/'tools/evaluation_startup_proposal'


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--job-sha256',required=True);a=p.parse_args()
    time.sleep(2)
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    readerpath=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    assert hashlib.sha256(readerpath.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
    spec=importlib.util.spec_from_file_location('closed26_bound_reader',readerpath);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    for entry in job['inputs']:r.read_pin(entry,as_json=False)
    sys.path.insert(0,str(A))
    import test_startup_probe_core_v3 as tests
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(tests.Tests)
    assert suite.countTestCases()==26
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    for entry in job['inputs']:r.read_pin(entry,as_json=False)
    assert 'torch' not in sys.modules and 'numpy' not in sys.modules
    print(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),
        errors=len(result.errors),skipped=len(result.skipped),CUDA_hidden=True,numerical_runtime_imported=False,
        scope='UNCHANGED_COORDINATOR_AND_EXACT_CLOSED_INVALID_PREDECESSOR_BINDINGS',
        actual_native_review_outer_exits=[1,2,1],actual_startup_diagnostic_launched=False,
        actual_candidate_captured=False,source_selected_for_science=False,quality_qualified=False)),flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
