"""Execute observer/reviewer paths with explicitly synthetic reconnect proofs."""
import argparse
import ast
import copy
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
GUARD = OWNED = SUP = H = CASE = JOB = REVIEW_HEALTH = None


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(value, message):
    if not value:
        raise ValueError(message)


class ObserverTests(unittest.TestCase):
    def overlap(self):
        case = copy.deepcopy(CASE)
        old = next(row for row in case['connections']['connections'] if row['client_slot'] == 0)
        new = copy.deepcopy(old)
        new.update(token=old['token']+':synthetic-new', client_id=10000,
                   connection_ns=old['connection_ns']+1)
        new['socket_endpoints']['peer'][1] += 1
        case['connections']['connections'].append(new)
        case['new'] = new
        return case

    def rebound(self):
        case = self.overlap()
        old_pin = case['fleet']['slots']['0']['current_physical_binding']
        old = copy.deepcopy(case['bindings']['0'])
        new_pin = dict(path='/synthetic-new-binding.json', sha256='a'*64, bytes=1)
        cleanup_pin = dict(path='/synthetic-old-token-cleanup.json', sha256='b'*64, bytes=1)
        new = copy.deepcopy(old)
        tcp = dict(inode=123456, local=case['new']['socket_endpoints']['peer'],
                   remote=case['new']['socket_endpoints']['server'])
        new['data'].update(connection=case['new'], previous_binding=old_pin,
                           old_token_cleanup=cleanup_pin, process_owned_TCP=tcp)
        cleanup = dict(old['data']['connection'], schema='robotron-prospective-connection-cleanup-receipt-v2',
                       server_stamp=case['expected']['trainer']['server_stamp'],
                       observed_unix_s=case['now'], cleanup_error=None,
                       ready_for_external_join=True, replay_admission_open=True)
        cleanup.update({key: True for key in SUP.CLEANUP_FLAGS})
        retired = copy.deepcopy(old)
        retired.update(kind='train-binding-retired', data=dict(previous_binding=old_pin,
            cleanup=cleanup, actor_not_replaced=True, actor_exit_or_game_completion_claimed=False))
        case['pins'][new_pin['path']] = new
        case['pins'][cleanup_pin['path']] = retired
        case['fleet']['slots']['0']['current_physical_binding'] = new_pin
        case['bindings']['0'] = new
        case['connections']['connections'] = [row for row in case['connections']['connections']
                                               if row['client_slot'] != 0] + [case['new']]
        case['cleanup'] = retired
        return case

    def guard(self, case, directory, *, after=None, wrong_actor=False):
        guard = GUARD.CurrentV6MainHealth.__new__(GUARD.CurrentV6MainHealth)
        guard.expected, guard.membership, guard.roles = case['expected'], case['membership'], case['roles']
        guard.samples, guard.pending_since, guard.previous_observed = [], None, None
        guard.h, guard.output, guard.owned_overlap, guard.supervisor = H, Path(directory), OWNED, SUP
        guard.base = SimpleNamespace(observe=lambda: copy.deepcopy(case['base']), finish=lambda worker: None)
        guard.supervisor_process = lambda: {}
        guard.status = lambda: copy.deepcopy(case['fleet'])
        values = iter([case['connections'], after or case['connections']])
        guard.get_connections = lambda: copy.deepcopy(next(values))
        guard.read = lambda pin: (copy.deepcopy(case['pins'][pin['path']])
                                 if pin['path'] in case['pins'] else
                                 json.loads(H.checked(pin).read_text()))
        by_pid = {event['data']['actor']['pid']: event for event in case['bindings'].values()}

        def actor(pid):
            value = copy.deepcopy(by_pid[pid]['data']['actor'])
            if wrong_actor and value['environment']['ROBOTRON_CLIENT_SLOT'] == '0':
                value['birth'] += 1
            return value

        def tcp(pid, endpoints):
            if case.get('new') and endpoints == case['new']['socket_endpoints']:
                return dict(inode=123456, local=endpoints['peer'], remote=endpoints['server'])
            event = by_pid[pid]
            require(endpoints == event['data']['connection']['socket_endpoints'], 'Synthetic TCP mismatch')
            return copy.deepcopy(event['data']['process_owned_TCP'])

        guard.physical = SimpleNamespace(actor=actor, tcp_binding=tcp)
        return guard

    def observe(self, guard, now=100):
        saved = GUARD.time
        GUARD.time = SimpleNamespace(monotonic=lambda: now, time=lambda: CASE['now'])
        try:
            return guard.observe()
        finally:
            GUARD.time = saved

    def test_owned_overlap_retains_full_snapshots_and_is_never_accepted(self):
        case = self.overlap()
        with tempfile.TemporaryDirectory(prefix='robotron-owned-observe-') as directory:
            guard = self.guard(case, directory)
            sample = self.observe(guard)
            raw = json.loads(H.checked(sample['physical_v6']).read_text())
            self.assertTrue(sample['phase']['overlap_pending'])
            self.assertFalse(raw['accepted'])
            self.assertIsNone(raw['joined'])
            self.assertEqual(len(raw['connections_before']['connections']), 193)
            self.assertEqual(raw['pending_slots'], [0])
            for phase in ('before', 'after'):
                metadata = raw['owned_TRAIN_metadata_'+phase]
                self.assertEqual(list(metadata['overlaps']), ['0'])
                self.assertEqual(OWNED.replay_pending(case['fleet'], case['connections'],
                    case['expected'], case['membership'], case['roles'], metadata,
                    now=case['now'], strict_validator=GUARD.validate_metadata, read_pin=guard.read), metadata)

    def test_after_only_overlap_is_unaccepted_and_proved(self):
        overlapping = self.overlap()
        unique = copy.deepcopy(CASE)
        unique['new'] = overlapping['new']
        with tempfile.TemporaryDirectory(prefix='robotron-after-overlap-') as directory:
            guard = self.guard(unique, directory, after=overlapping['connections'])
            raw = json.loads(H.checked(self.observe(guard)['physical_v6']).read_text())
            self.assertFalse(raw['accepted'])
            self.assertEqual(raw['owned_TRAIN_metadata_before']['overlaps'], {})
            self.assertEqual(list(raw['owned_TRAIN_metadata_after']['overlaps']), ['0'])

    def test_unproved_overlap_retains_rejected_before_inputs(self):
        with tempfile.TemporaryDirectory(prefix='robotron-foreign-overlap-') as directory:
            guard = self.guard(self.overlap(), directory, wrong_actor=True)
            with self.assertRaisesRegex(ValueError, 'same original MAME'):
                self.observe(guard)
            files = list(Path(directory).glob('*owned-metadata-rejected.json'))
            self.assertEqual(len(files), 1)
            raw = json.loads(files[0].read_text())
            self.assertEqual(raw['phase'], 'before')
            self.assertFalse(raw['accepted'])
            self.assertEqual(guard.samples, [])

    def test_overlap_does_not_extend_ten_second_deadline(self):
        with tempfile.TemporaryDirectory(prefix='robotron-overlap-limit-') as directory:
            guard = self.guard(self.overlap(), directory)
            guard.pending_since = 89
            with self.assertRaisesRegex(ValueError, 'within10s'):
                self.observe(guard, 100)
            self.assertEqual(guard.samples, [])

    def test_overlap_does_not_extend_fifteen_second_gap(self):
        with tempfile.TemporaryDirectory(prefix='robotron-overlap-gap-') as directory:
            guard = self.guard(self.overlap(), directory)
            guard.previous_observed = 84
            with self.assertRaisesRegex(ValueError, '15s'):
                self.observe(guard, 100)

    def test_final_pending_sample_cannot_close_as_valid(self):
        with tempfile.TemporaryDirectory(prefix='robotron-pending-finish-') as directory:
            guard = self.guard(self.overlap(), directory)
            self.observe(guard)
            with self.assertRaisesRegex(ValueError, 'Final original physical'):
                guard.finish(None)

    def test_reviewer_rejects_tampered_ownership_and_pending_result(self):
        case = self.overlap()
        with tempfile.TemporaryDirectory(prefix='robotron-replay-tamper-') as directory:
            guard = self.guard(case, directory)
            raw = json.loads(H.checked(self.observe(guard)['physical_v6']).read_text())
            for damage in ('TCP', 'binding', 'pending', 'qualified'):
                with self.subTest(damage=damage):
                    metadata = copy.deepcopy(raw['owned_TRAIN_metadata_before'])
                    if damage == 'TCP':
                        metadata['overlaps']['0']['proof']['TCP']['local'] = ['foreign', 1]
                    elif damage == 'binding':
                        metadata['overlaps']['0']['binding']['epoch'] = 'foreign'
                    elif damage == 'pending':
                        metadata['pending_slots'] = []
                    else:
                        metadata['census_qualified'] = True
                    with self.assertRaises(ValueError):
                        OWNED.replay_pending(case['fleet'], case['connections'], case['expected'],
                            case['membership'], case['roles'], metadata, now=case['now'],
                            strict_validator=GUARD.validate_metadata, read_pin=guard.read)

    def test_unique_rebind_with_original_cleanup_can_be_accepted(self):
        with tempfile.TemporaryDirectory(prefix='robotron-clean-rebind-') as directory:
            guard = self.guard(self.rebound(), directory)
            raw = json.loads(H.checked(self.observe(guard)['physical_v6']).read_text())
            self.assertTrue(raw['accepted'])
            self.assertEqual(raw['joined']['live_originals'], 192)

    def test_missing_unclosed_or_foreign_cleanup_cannot_be_accepted(self):
        for damage in ('missing', 'unclosed', 'foreign'):
            with self.subTest(damage=damage), tempfile.TemporaryDirectory(prefix='robotron-bad-cleanup-') as directory:
                case = self.rebound()
                if damage == 'missing':
                    case['bindings']['0']['data']['old_token_cleanup'] = None
                elif damage == 'unclosed':
                    case['cleanup']['data']['cleanup']['original_handler_stopped'] = False
                else:
                    case['cleanup']['epoch'] = 'foreign'
                guard = self.guard(case, directory)
                with self.assertRaises(ValueError):
                    self.observe(guard)
                self.assertEqual(guard.samples, [])

    def test_actual_reviewer_health_loop_handles_pending_and_closed_rebind(self):
        # Execute the real generated reviewer's health-loop AST, with controller
        # boundaries and changed process/socket/cleanup data explicitly synthetic.
        with tempfile.TemporaryDirectory(prefix='robotron-reviewer-flow-') as directory:
            samples = []
            cases = [copy.deepcopy(CASE), self.overlap(), self.rebound()]
            rebound = cases[-1]
            cleanup_pin = H.put(Path(directory)/'synthetic-retired-token.json', rebound['cleanup'])
            rebound['bindings']['0']['data']['old_token_cleanup'] = cleanup_pin
            binding_pin = H.put(Path(directory)/'synthetic-new-binding.json', rebound['bindings']['0'])
            rebound['fleet']['slots']['0']['current_physical_binding'] = binding_pin
            rebound['pins'][cleanup_pin['path']] = rebound['cleanup']
            rebound['pins'][binding_pin['path']] = rebound['bindings']['0']
            pending_since, previous = None, None
            for moment, case in zip((100, 105, 109), cases):
                guard = self.guard(case, directory)
                guard.samples = list(samples)
                guard.pending_since, guard.previous_observed = pending_since, previous
                samples.append(self.observe(guard, moment))
                pending_since, previous = guard.pending_since, guard.previous_observed
            pins = {}
            for case in cases:
                pins.update(case['pins'])

            def read(pin):
                if pin['path'] in pins:
                    return copy.deepcopy(pins[pin['path']])
                return json.loads(H.checked(pin).read_text())

            result = dict(main_samples=samples,
                          main_health_report=H.put(Path(directory)/'synthetic-Main-report.json', dict(samples=samples)),
                          main_observer_lifecycle=dict(original_observer_thread_closed=True, no_child_scope_created=True))
            answer = REVIEW_HEALTH(result, JOB, H, read)
            self.assertEqual((answer['accepted'], answer['pending']), (2, 1))
            raw = read(samples[1]['physical_v6'])
            raw['owned_TRAIN_metadata_before']['overlaps']['0']['proof']['TCP']['local'] = ['foreign', 1]
            damaged_read = lambda pin: copy.deepcopy(raw) if pin == samples[1]['physical_v6'] else read(pin)
            with self.assertRaises(ValueError):
                REVIEW_HEALTH(result, JOB, H, damaged_read)


def main():
    global GUARD, OWNED, SUP, H, CASE, JOB, REVIEW_HEALTH
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'owned-source', 'reviewer', 'fixture-job', 'physical-fixture', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    H = load('_owned_observer_test_h', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    GUARD = load('_owned_observer_test_guard', args.source)
    OWNED = load('_owned_observer_test_owned', args.owned_source)
    JOB = json.loads(args.fixture_job.read_text())
    SUP = load('_owned_observer_test_cleanup', H.checked(JOB['current_fleet']['supervisor']['source']))
    raw = json.loads(args.physical_fixture.read_text())
    expected = JOB['current_fleet']
    pins = {row['current_physical_binding']['path']: raw['bindings'][key]
            for key, row in raw['fleet_before']['slots'].items()}
    CASE = dict(fleet=raw['fleet_before'], connections=raw['connections_before'], expected=expected,
        membership=json.loads(H.checked(expected['original_membership']).read_text()),
        roles=json.loads(H.checked(expected['rolemap']).read_text())['slot_eval'],
        bindings=raw['bindings'], pins=pins, now=raw['connections_before']['observed_unix_s'], base=raw['base'])
    JOB['current_v6_health_source'] = H.pin(args.source)
    JOB['owned_TRAIN_overlap_source'] = H.pin(args.owned_source)
    tree = ast.parse(args.reviewer.read_text())
    review = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and
                  any(isinstance(child, ast.Constant) and child.value == '_eng_review_actual_v6_health'
                      for child in ast.walk(node)))
    start = next(i for i, node in enumerate(review.body) if isinstance(node, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'source' for t in node.targets)
                 and '_eng_review_actual_v6_health' in ast.unparse(node))
    finish = next(i for i in range(start, len(review.body)) if isinstance(review.body[i], ast.For)
                  and isinstance(review.body[i].target, ast.Name) and review.body[i].target.id == 'pin'
                  and 'bindings.values()' in ast.unparse(review.body[i].iter))
    fn = ast.parse('def review_health(result,job,h,read):\n    pass').body[0]
    fn.body = copy.deepcopy(review.body[start:finish+1])
    fn.body.append(ast.parse('return dict(accepted=accepted,pending=pending,max_gap=max_gap)').body[0])
    env = dict(load=load, require=require, math=math)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<actual-reviewer-health-loop>', 'exec'), env)
    REVIEW_HEALTH = env['review_health']
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ObserverTests))
    assert 'torch' not in sys.modules
    report = H.put(args.output, dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests_run=result.testsRun,
        log=stream.getvalue(), errors=[dict(test=str(t),traceback=v) for t,v in result.errors],
        failures=[dict(test=str(t),traceback=v) for t,v in result.failures],
        source=H.pin(args.source), owned_source=H.pin(args.owned_source), reviewer=H.pin(args.reviewer),
        test_source=H.pin(Path(__file__)), fixture_job=H.pin(args.fixture_job), physical_fixture=H.pin(args.physical_fixture),
        actual_observer_and_extracted_reviewer_health_AST_executed=True,
        changed_socket_process_cleanup_inputs_are_synthetic=True,
        full_reviewer_native_or_live_overlap_qualification=False, promotion=False))
    print(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun, report=report)))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
