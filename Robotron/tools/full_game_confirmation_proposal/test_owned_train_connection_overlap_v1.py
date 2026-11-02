"""CPU contract tests; altered sockets and process fields are synthetic."""
import argparse
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SOURCE = STRICT = H = FIXTURE = None


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PendingOverlapTests(unittest.TestCase):
    def case(self, slot=0):
        case = copy.deepcopy(FIXTURE)
        old = next(row for row in case['connections']['connections'] if row['client_slot'] == slot)
        candidate = copy.deepcopy(old)
        candidate.update(token=old['token'] + ':synthetic-new',
                         client_id=old['client_id'] + 10000,
                         connection_ns=old['connection_ns'] + 1)
        candidate['socket_endpoints']['peer'][1] += 1
        case['connections']['connections'].append(candidate)
        case['candidate'] = candidate
        case['slot'] = slot
        return case

    def check(self, case, actor=None, tcp=None, read=None):
        slot = case['slot']
        binding = case['bindings'][str(slot)]
        return SOURCE.capture_pending(
            case['fleet'], case['connections'], case['expected'], case['membership'],
            case['roles'], now=case['now'], strict_validator=STRICT.validate_metadata,
            read_pin=read or (lambda pin: copy.deepcopy(binding)),
            physical_actor=actor or (lambda pid: copy.deepcopy(binding['data']['actor'])),
            tcp_binding=tcp or (lambda pid, ep: dict(inode=123456, local=ep['peer'], remote=ep['server'])))

    def test_exact_old_and_owned_new_are_only_pending(self):
        case = self.case()
        before = copy.deepcopy(case)
        result = self.check(case)
        self.assertEqual(result['pending_slots'], [0])
        self.assertEqual(list(result['overlaps']), ['0'])
        self.assertFalse(result['census_qualified'])
        self.assertEqual(case, before)
        # The original validator still rejects the untouched full snapshot.
        with self.assertRaisesRegex(ValueError, 'Duplicate/foreign'):
            STRICT.validate_metadata(case['fleet'], case['connections'], case['expected'],
                                     case['membership'], case['roles'], now=case['now'])

    def test_unique_snapshot_uses_original_strict_path(self):
        case = self.case()
        case['connections']['connections'].remove(case['candidate'])
        def forbidden(*args):
            raise AssertionError('Unique path must not add ownership callbacks')
        self.assertEqual(self.check(case, actor=forbidden)['pending_slots'], [])

    def test_already_pending_fleet_state_stays_pending(self):
        case = self.case()
        case['fleet']['slots']['0']['state'] = 'reconnecting_train'
        case['fleet']['counts']['active_train'] -= 1
        case['fleet']['counts']['reconnecting_train'] += 1
        self.assertEqual(self.check(case)['pending_slots'], [0])

    def test_foreign_slot_or_role_is_rejected(self):
        for damage in ('slot', 'role'):
            with self.subTest(damage=damage):
                case = self.case()
                if damage == 'slot':
                    case['candidate']['client_slot'] = 8191
                else:
                    case['candidate']['eval_only'] = True
                with self.assertRaises(ValueError):
                    self.check(case)

    def test_eval_overlap_is_rejected(self):
        slot = next(int(k) for k, v in FIXTURE['roles'].items() if v)
        with self.assertRaises(ValueError):
            self.check(self.case(slot))

    def test_three_connections_or_duplicate_token_or_cid_rejected(self):
        for damage in ('third', 'token', 'cid'):
            with self.subTest(damage=damage):
                case = self.case()
                old = case['bindings']['0']['data']['connection']
                if damage == 'third':
                    case['connections']['connections'].append(copy.deepcopy(case['candidate']))
                elif damage == 'token':
                    case['candidate']['token'] = old['token']
                else:
                    case['candidate']['client_id'] = old['client_id']
                with self.assertRaises(ValueError):
                    self.check(case)

    def test_changed_or_absent_old_binding_rejected(self):
        for damage in ('changed', 'absent'):
            with self.subTest(damage=damage):
                case = self.case()
                old = next(r for r in case['connections']['connections']
                           if r['client_slot'] == 0 and r is not case['candidate'])
                if damage == 'changed':
                    old['socket_endpoints']['peer'][1] += 9
                else:
                    old['token'] += ':foreign'
                with self.assertRaises(ValueError):
                    self.check(case)

    def test_old_or_boolean_connection_clock_rejected(self):
        for value in (True, 0):
            with self.subTest(value=value):
                case = self.case()
                case['candidate']['connection_ns'] = value
                with self.assertRaises(ValueError):
                    self.check(case)

    def test_wrong_actor_identity_or_environment_rejected(self):
        for field in ('pid', 'birth', 'parent', 'exe', 'cgroup', 'uid', 'command', 'environment'):
            with self.subTest(field=field):
                case = self.case()
                value = copy.deepcopy(case['bindings']['0']['data']['actor'])
                if field == 'environment':
                    value[field]['ROBOTRON_CLIENT_SLOT'] = '999'
                elif field in ('pid', 'birth', 'parent', 'uid'):
                    value[field] += 1
                elif field == 'command':
                    value[field] = ['foreign']
                else:
                    value[field] = 'foreign'
                with self.assertRaises(ValueError):
                    self.check(case, actor=lambda pid: copy.deepcopy(value))

    def test_actor_change_during_tcp_probe_rejected(self):
        case = self.case()
        one = copy.deepcopy(case['bindings']['0']['data']['actor'])
        two = copy.deepcopy(one)
        two['birth'] += 1
        answers = iter([one, two])
        with self.assertRaises(ValueError):
            self.check(case, actor=lambda pid: next(answers))

    def test_missing_or_foreign_process_owned_tcp_rejected(self):
        def missing(*args):
            raise ValueError('No unique actual process socket')
        with self.assertRaises(ValueError):
            self.check(self.case(), tcp=missing)
        with self.assertRaises(ValueError):
            self.check(self.case(), tcp=lambda *args: dict(inode=123, local=['foreign', 1], remote=['foreign', 2]))

    def test_unreadable_or_foreign_binding_lineage_rejected(self):
        def unreadable(*args):
            raise ValueError('Immutable pin changed')
        with self.assertRaises(ValueError):
            self.check(self.case(), read=unreadable)
        for field in ('epoch', 'source_authority', 'slot', 'incarnation'):
            with self.subTest(field=field):
                case = self.case()
                binding = copy.deepcopy(case['bindings']['0'])
                binding[field] = 'foreign'
                with self.assertRaises(ValueError):
                    self.check(case, read=lambda pin: binding)

    def test_all_original_freshness_fault_and_membership_guards_remain(self):
        for damage in ('stale', 'fault', 'epoch', 'membership'):
            with self.subTest(damage=damage):
                case = self.case()
                if damage == 'stale':
                    case['connections']['observed_unix_s'] = case['now'] - 6
                elif damage == 'fault':
                    case['fleet']['slots']['0']['faults'] = 1
                elif damage == 'epoch':
                    case['fleet']['epoch'] = 'foreign'
                else:
                    case['membership']['epoch'] = 'foreign'
                with self.assertRaises(ValueError):
                    self.check(case)


def main():
    global SOURCE, STRICT, H, FIXTURE
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'strict-source', 'fixture-job', 'physical-fixture', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    H = load('_owned_overlap_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    SOURCE = load('_owned_overlap_source', args.source)
    STRICT = load('_owned_overlap_strict', args.strict_source)
    job = json.loads(args.fixture_job.read_text())
    raw = json.loads(args.physical_fixture.read_text())
    expected = job['current_fleet']
    FIXTURE = dict(fleet=raw['fleet_before'], connections=raw['connections_before'],
                   expected=expected, membership=json.loads(H.checked(expected['original_membership']).read_text()),
                   roles=json.loads(H.checked(expected['rolemap']).read_text())['slot_eval'],
                   bindings=raw['bindings'], now=raw['connections_before']['observed_unix_s'])
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(PendingOverlapTests))
    assert 'torch' not in sys.modules
    report = H.put(args.output, dict(status='PASS' if result.wasSuccessful() else 'FAIL',
        tests_run=result.testsRun, log=stream.getvalue(),
        errors=[dict(test=str(t), traceback=v) for t, v in result.errors],
        failures=[dict(test=str(t), traceback=v) for t, v in result.failures],
        source=H.pin(args.source), test_source=H.pin(Path(__file__)),
        strict_source=H.pin(args.strict_source), fixture_job=H.pin(args.fixture_job),
        physical_fixture=H.pin(args.physical_fixture), modified_fields_and_socket_callbacks_are_synthetic=True,
        real_reconnect_or_observer_integration_qualified=False, scientific_qualification=False,
        promotion=False))
    print(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun, report=report)))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
