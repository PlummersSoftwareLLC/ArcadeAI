"""Execute one precommitted synthetic CPU test group; inert without --execute."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
H = G/'tools/quality_capacity_proposal'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    parser.add_argument('--group')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no source reads, tests, queries, outputs or launches')
        return 0
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    path = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
    spec = importlib.util.spec_from_file_location('_tail9000_worker_reader', path)
    reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
    entry = reader.pin(args.job); assert entry['sha256'] == args.job_sha256
    job = reader.read_pin(entry)
    assert job['schema'] == 'robotron-tail9000-original-CPU-groups-v1'
    for pin in job['sources']:
        reader.read_pin(pin, as_json=False)
    assert reader.pin(__file__) in job['sources']
    sys.path[:0] = job['import_paths']
    selected = job['groups'][args.group]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in selected)
    count = suite.countTestCases(); assert count > 0
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert 'torch' not in sys.modules and 'numpy' not in sys.modules
    for pin in job['sources']:
        assert reader.pin(pin['path']) == pin
    report = dict(group=args.group, actual_tests_run=result.testsRun, loaded_test_count=count,
        passed=result.wasSuccessful(), failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), elapsed_s=time.monotonic()-started, selected_tests=selected,
        synthetic_checkpoint_and_quality_artifacts_only=True, actual_quality_run=False,
        actual_policy_publication=False, CUDA_hidden=True, numerical_runtime_imported=False,
        live_readonly_main_preflight=args.group=='A')
    destination = Path(job['output'])/('group-'+args.group+'-actual-test-result.json')
    with destination.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
        stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    print(json.dumps(report, allow_nan=False), flush=True)
    return 0 if result.wasSuccessful() and result.testsRun == count and not result.skipped else 1


if __name__ == '__main__':
    raise SystemExit(main())
