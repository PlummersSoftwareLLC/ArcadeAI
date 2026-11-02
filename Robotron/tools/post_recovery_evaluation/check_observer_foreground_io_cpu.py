"""Run complete observer-loop fault tests once in an original CPU-only engineering scope."""
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

ROOT = Path(__file__).resolve().parents[2]


def execute(args):
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw = Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job = json.loads(raw)
    assert job['schema'] == 'robotron-observer-foreground-io-fault-engineering-job-v1'
    assert os.environ['CUDA_VISIBLE_DEVICES'] == '' and 'torch' not in sys.modules
    path = ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    spec = importlib.util.spec_from_file_location('_durability_CPU_helpers', path)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    for value in job['inputs']:
        h.checked(value)
    sys.path.insert(0, str(ROOT.parent))
    suite = unittest.defaultTestLoader.loadTestsFromName('Robotron.tools.post_recovery_evaluation.test_observer_foreground_io')
    output = io.StringIO()
    started = time.monotonic()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    for value in job['inputs']:
        h.checked(value)
    assert result.wasSuccessful() and result.testsRun == 2, output.getvalue()
    directory = Path(job['output'])
    directory.mkdir(mode=0o700)
    report = dict(schema='robotron-observer-foreground-io-fault-engineering-result-v1', status='PASS',
        original_job=h.pin(Path(args.job)), actual_PID=os.getpid(), tests_run=result.testsRun,
        test_output=output.getvalue(), elapsed_s=time.monotonic()-started,
        Torch_imported='torch' in sys.modules, GPU_or_MAME_launched=False,
        scientific_launch_qualified=False, quality_qualified=False, promotion=False)
    h.put(directory/'report.json', report)
    print(json.dumps(dict(status='PASS', tests_run=result.testsRun)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if args.execute:
        execute(args)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
