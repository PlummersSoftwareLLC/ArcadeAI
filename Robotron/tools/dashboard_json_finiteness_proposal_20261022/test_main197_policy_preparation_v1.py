"""CPU guards for retaining all197 holds after the new resume record."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch


def load(entry, name):
    raw = Path(entry['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    spec = importlib.util.spec_from_file_location(name, entry['path'])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Main197Preparation(unittest.TestCase):
    def test_only_exact_count_and_preparer_dependency_changed(self):
        old = Path(JOB['old_supervision']['path']).read_text()
        new = Path(JOB['new_policy_preparer']['path']).read_text()
        expected = old.replace("len(main['held_hashes']) == 196", "len(main['held_hashes']) == 197").replace(
            'all 196 source/control holds required', 'all 197 source/control holds required')
        self.assertEqual(new, expected)
        old = Path(JOB['old_leg_preparer']['path']).read_text()
        new = Path(JOB['new_leg_preparer']['path']).read_text()
        self.assertEqual(new, old.replace(
            "    policy,snapshot=sup.make_policy(main,old_policy['fleet'])",
            "    policy_preparer=load('_fresh_quality197_policy_preparer',h.checked(readiness['main_policy_preparer']))\n"
            "    policy,snapshot=policy_preparer.make_policy(main,old_policy['fleet'])"))

    def test_all197_holds_join_actual_captured192_snapshot(self):
        with patch.object(SUP, 'capture', return_value=SNAPSHOT) as capture:
            policy, snapshot = SUP.make_policy(MAIN, FLEET)
        capture.assert_called_once()
        self.assertEqual(snapshot, SNAPSHOT)
        self.assertEqual(len(MAIN['held_hashes']), 197)
        self.assertEqual(policy['held_hashes_sha256'], hashlib.sha256(json.dumps(
            MAIN['held_hashes'], sort_keys=True, separators=(',', ':')).encode()).hexdigest())
        self.assertEqual(policy['trainer'], MAIN['owner'])
        self.assertEqual(set(policy['baseline_actors']), {str(slot) for slot in range(192)})

    def test_dropping_a_hold_is_rejected_before_capture(self):
        bad = copy.deepcopy(MAIN)
        bad['held_hashes'].pop(next(iter(bad['held_hashes'])))
        with patch.object(SUP, 'capture', side_effect=AssertionError('No census permitted')):
            with self.assertRaisesRegex(ValueError, 'all 197'):
                SUP.make_policy(bad, FLEET)

    def test_extra_or_relabelled_hold_count_is_rejected_before_capture(self):
        bad = copy.deepcopy(MAIN)
        bad['held_hashes']['/unselected-input'] = '0'*64
        with patch.object(SUP, 'capture', side_effect=AssertionError('No census permitted')):
            with self.assertRaisesRegex(ValueError, 'all 197'):
                SUP.make_policy(bad, FLEET)


def main():
    global JOB, SUP, SNAPSHOT, MAIN, FLEET
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw = Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    JOB = json.loads(raw)
    assert not Path(JOB['output']).exists()
    for entry in JOB['pins']:
        assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest() == entry['sha256']
    SUP = load(JOB['new_policy_preparer'], '_main197_policy_guard')
    MAIN = json.loads(Path(JOB['new_prospective_binding']['path']).read_bytes())
    SNAPSHOT = json.loads(Path(JOB['observed_census']['path']).read_bytes())
    FLEET = json.loads(Path(MAIN['supervision_policy']['path']).read_bytes())['fleet']
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Main197Preparation))
    assert 'torch' not in sys.modules
    report = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), source_sha256=args.source_sha256,
        all197_inputs_retained=True, actual_process_operations=False, main_runtime_changed=False,
        quality_qualified=False, promotion=False, created_unix_s=time.time())
    with Path(JOB['output']).open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(report), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
