"""CPU tests for exact rejection capture, using sealed original fixture data.

Changed connections are synthetic; no live reconnect or physical admission is
qualified by these tests.
"""
import argparse
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

CHECK = H = CASE = None


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RejectionCaptureTests(unittest.TestCase):
    def run_metadata(self, case, directory, phase='before', writer=None):
        f, c, e, m, roles, now = case
        return CHECK.retained_metadata_validation(
            writer or H, Path(directory), 7, phase, f, c, e, m, roles, now=now)

    def assert_rejection(self, case, phase='before'):
        with tempfile.TemporaryDirectory(prefix='robotron-rejected-metadata-') as directory:
            with self.assertRaises(ValueError) as caught:
                self.run_metadata(case, directory, phase)
            files = list(Path(directory).iterdir())
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].name, f'00007-v6-{phase}-metadata-rejected.json')
            saved = json.loads(files[0].read_text())
            self.assertEqual(saved['fleet'], case[0])
            self.assertEqual(saved['connections'], case[1])
            self.assertEqual(saved['expected'], case[2])
            self.assertEqual(saved['membership'], case[3])
            self.assertEqual(saved['roles'], case[4])
            self.assertEqual(saved['error'], str(caught.exception))
            self.assertFalse(saved['accepted'])
            self.assertFalse(saved['quality_qualified'])
            self.assertEqual(files[0].stat().st_mode & 0o777, 0o444)

    def test_valid_metadata_has_no_failure_artifact(self):
        with tempfile.TemporaryDirectory(prefix='robotron-valid-metadata-') as directory:
            self.assertEqual(self.run_metadata(copy.deepcopy(CASE), directory), [])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_duplicate_before_snapshot_is_retained_and_rejected(self):
        case = copy.deepcopy(CASE)
        case[1]['connections'].append(copy.deepcopy(case[1]['connections'][0]))
        self.assert_rejection(case)

    def test_duplicate_after_snapshot_is_retained_and_rejected(self):
        case = copy.deepcopy(CASE)
        case[1]['connections'].append(copy.deepcopy(case[1]['connections'][0]))
        self.assert_rejection(case, 'after')

    def test_pending_train_does_not_authorize_duplicate_slot(self):
        case = copy.deepcopy(CASE)
        slot = next(k for k, value in case[4].items() if not value)
        case[0]['slots'][slot]['state'] = 'reconnecting_train'
        case[0]['counts']['active_train'] -= 1
        case[0]['counts']['reconnecting_train'] += 1
        row = copy.deepcopy(next(r for r in case[1]['connections'] if r['client_slot'] == int(slot)))
        row['token'] += ':synthetic-distinct'
        row['client_id'] += 10000
        case[1]['connections'].append(row)
        self.assert_rejection(case)

    def test_foreign_slot_role_and_stale_snapshots_stay_rejected(self):
        for damage in ('foreign', 'role', 'stale'):
            with self.subTest(damage=damage):
                case = copy.deepcopy(CASE)
                if damage == 'foreign':
                    case[1]['connections'][0]['client_slot'] = 8191
                elif damage == 'role':
                    row = case[1]['connections'][0]
                    row['eval_only'] = not row['eval_only']
                else:
                    case[1]['observed_unix_s'] = case[5] - 6
                self.assert_rejection(case)

    def test_failed_capture_cannot_become_success(self):
        case = copy.deepcopy(CASE)
        case[1]['connections'].append(copy.deepcopy(case[1]['connections'][0]))

        def fail(*args):
            raise OSError('synthetic disk failure')

        with tempfile.TemporaryDirectory(prefix='robotron-capture-failure-') as directory:
            with self.assertRaisesRegex(RuntimeError, 'capture also failed') as caught:
                self.run_metadata(case, directory, writer=SimpleNamespace(put=fail))
            self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_real_observe_routes_before_and_after_rejections_to_capture(self):
        for phase in ('before', 'after'):
            with self.subTest(phase=phase):
                f, c, e, m, roles, now = copy.deepcopy(CASE)
                slot = next(k for k, value in roles.items() if not value)
                f['slots'][slot]['state'] = 'reconnecting_train'
                f['counts']['active_train'] -= 1
                f['counts']['reconnecting_train'] += 1
                bad = copy.deepcopy(c)
                bad['connections'].append(copy.deepcopy(c['connections'][0]))
                values = iter([bad] if phase == 'before' else [c, bad])
                guard = CHECK.CurrentV6MainHealth.__new__(CHECK.CurrentV6MainHealth)
                guard.expected, guard.membership, guard.roles = e, m, roles
                guard.samples = []
                guard.supervisor_process = lambda: {}
                guard.base = SimpleNamespace(observe=lambda: {})
                guard.status = lambda: copy.deepcopy(f)
                guard.get_connections = lambda: copy.deepcopy(next(values))
                guard.h = H
                clock = CHECK.time
                CHECK.time = SimpleNamespace(monotonic=lambda: 100, time=lambda: now)
                try:
                    with tempfile.TemporaryDirectory(prefix='robotron-observe-rejection-') as directory:
                        guard.output = Path(directory)
                        with self.assertRaisesRegex(ValueError, 'Duplicate/foreign'):
                            guard.observe()
                        saved = json.loads(next(Path(directory).iterdir()).read_text())
                        self.assertEqual(saved['phase'], phase)
                        self.assertEqual(saved['connections'], bad)
                        self.assertEqual(guard.samples, [])
                finally:
                    CHECK.time = clock


def main():
    global CHECK, H, CASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--fixture-job', required=True, type=Path)
    parser.add_argument('--physical-fixture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path('/home/dave/source/repos/ArcadeAI/Robotron')
    H = load('_metadata_capture_helpers', root / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    CHECK = load('_metadata_capture_source', args.source)
    job = json.loads(args.fixture_job.read_text())
    raw = json.loads(args.physical_fixture.read_text())
    expected = job['current_fleet']
    membership = json.loads(H.checked(expected['original_membership']).read_text())
    roles = json.loads(H.checked(expected['rolemap']).read_text())['slot_eval']
    CASE = (raw['fleet_before'], raw['connections_before'], expected, membership, roles,
            max(raw['fleet_before']['updated_unix_s'], raw['connections_before']['observed_unix_s']))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(RejectionCaptureTests))
    assert 'torch' not in sys.modules
    report = H.put(args.output, dict(
        status='PASS' if result.wasSuccessful() else 'FAIL', tests_run=result.testsRun,
        log=stream.getvalue(), errors=[dict(test=str(t), traceback=v) for t, v in result.errors],
        failures=[dict(test=str(t), traceback=v) for t, v in result.failures],
        source=H.pin(args.source), test_source=H.pin(Path(__file__)),
        fixture_job=H.pin(args.fixture_job), physical_fixture=H.pin(args.physical_fixture),
        changed_connections_are_synthetic=True, live_reconnect_qualification=False,
        validator_relaxed=False, scientific_qualification=False, promotion=False))
    print(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun, report=report)))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
