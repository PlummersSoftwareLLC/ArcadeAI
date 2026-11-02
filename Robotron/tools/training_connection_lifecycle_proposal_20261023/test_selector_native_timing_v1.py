"""Run actual writer guards through common instrumentation plus measurement guards."""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


def load(pin, name):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-guards', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256')
    args = parser.parse_args()
    if not args.run_guards:
        print('PLAN_ONLY'); return 0
    assert hashlib.sha256(args.job.read_bytes()).hexdigest() == args.expected_job_sha256
    job = json.loads(args.job.read_text())
    assert job['schema'] == 'robotron-selector-native-timing-guards-job-v1'
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == job['runner_sha256']
    timing = load(job['timing'], '_native_timing')
    original_guards = load(job['actual_writer_guards'], '_timed_actual_writer_guards')
    journal = load(job['journal'], '_timed_actual_journal')
    modules = {name: load(job[name], '_timed_' + name) for name in ('baseline', 'proposal')}
    results, recordings = {}, {}
    for name, module in modules.items():
        measured = timing.SelectorTiming(module.FixedSlotCohortView, job[name]['sha256'])
        stream = io.StringIO()
        try:
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(original_guards.guards(journal, module))
        finally:
            recordings[name] = measured.finish()
        results[name] = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                             skipped=len(result.skipped), log=stream.getvalue())

    class TimingContracts(unittest.TestCase):
        def test_actual_writer_measurements_complete_finite_and_methods_restored(self):
            for name, data in recordings.items():
                self.assertTrue(data['all_calls_retained'] and data['original_method_restored'])
                self.assertFalse(data['overflowed'])
                self.assertEqual(data['active_calls_at_close'], 0)
                self.assertGreater(len(data['rows']), 10)
                self.assertTrue(any(row[-1] is True for row in data['rows']))
                self.assertTrue(any(row[-1] is False for row in data['rows']))
                for row in data['rows']:
                    self.assertEqual(len(row), 8)
                    self.assertTrue(all(type(value) is int for value in row[:-1]))
                    self.assertGreaterEqual(row[1], row[0])
                    self.assertGreaterEqual(row[2], 0)
                self.assertEqual(modules[name].FixedSlotCohortView.cohort_status.__code__.co_filename, job[name]['path'])

        def test_wrong_selector_source_cannot_be_instrumented(self):
            cls = modules['baseline'].FixedSlotCohortView
            original = cls.cohort_status
            with self.assertRaisesRegex(ValueError, 'Exact original selected'):
                timing.SelectorTiming(cls, 'f' * 64)
            self.assertIs(cls.cohort_status, original)

        def test_lossless_capacity_exhaustion_invalidates_and_method_restores(self):
            module = modules['baseline']
            with tempfile.TemporaryDirectory(prefix='timing-capacity-') as temporary:
                case = original_guards.WriterHarness(journal, module, temporary)
                measured = timing.SelectorTiming(module.FixedSlotCohortView, job['baseline']['sha256'], max_calls=1)
                try:
                    case.status()
                    with self.assertRaisesRegex(RuntimeError, 'capacity exceeded; case invalid'):
                        case.status()
                finally:
                    data = measured.finish()
                self.assertTrue(data['overflowed'] and data['original_method_restored'])
                self.assertFalse(data['all_calls_retained'])
                self.assertEqual(len(data['rows']), 1)
                self.assertTrue(case.status()['valid'])

        def endpoints(self):
            start = dict(read_started_monotonic_ns=1000000000, read_ended_monotonic_ns=1002000000,
                         midpoint_monotonic_ns=1001000000,
                         slots={str(slot): dict(pid=slot, birth=123, accepted=10000, rejected=0, sequence=10000)
                                for slot in range(4096, 4128)})
            end = copy.deepcopy(start)
            for key in ('read_started_monotonic_ns', 'read_ended_monotonic_ns', 'midpoint_monotonic_ns'):
                end[key] += 600000000000
            for row in end['slots'].values():
                row['accepted'] += 6000; row['sequence'] += 6000
            return start, end

        def test_all32_accepted_frame_rates_and_time_uncertainty_brackets(self):
            start, end = self.endpoints()
            result = timing.window_rates(start, end)
            self.assertEqual(result['accepted_frames'], 192000)
            self.assertEqual(result['midpoint_elapsed_s'], 600)
            self.assertEqual(result['aggregate_midpoint_FPS'], 320)
            self.assertLess(result['aggregate_bracket_low_FPS'], 320)
            self.assertGreater(result['aggregate_bracket_high_FPS'], 320)
            self.assertEqual({r['midpoint_FPS'] for r in result['slots'].values()}, {10})
            self.assertFalse(result['useful_training_throughput_claim'] or result['learning_speed_claim'])

        def test_missing_frozen_replaced_rejected_or_reversed_endpoint_fails(self):
            for change in ('missing', 'frozen', 'birth', 'rejected', 'clock'):
                with self.subTest(change=change):
                    start, end = self.endpoints()
                    if change == 'missing': del end['slots']['4096']
                    elif change == 'frozen': end['slots']['4096']['accepted'] = start['slots']['4096']['accepted']
                    elif change == 'birth': end['slots']['4096']['birth'] += 1
                    elif change == 'rejected': end['slots']['4096']['rejected'] = 1
                    else: end['read_started_monotonic_ns'] = 0
                    with self.assertRaises(ValueError): timing.window_rates(start, end)

    stream = io.StringIO()
    contracts = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TimingContracts))
    results['measurement_contracts'] = dict(tests=contracts.testsRun, failures=len(contracts.failures),
        errors=len(contracts.errors), skipped=len(contracts.skipped), log=stream.getvalue())
    passed = all(row['failures'] == row['errors'] == row['skipped'] == 0 for row in results.values())
    passed = passed and [row['tests'] for row in results.values()] == [12, 12, 5]
    assert 'torch' not in sys.modules
    report = dict(schema='robotron-selector-native-timing-guards-result-v1', passed=passed, job=job,
        results=results, original_actual_writer_suite_methods_preserved=True,
        all_original_writer_calls=recordings, no_native_Torch_MAME_or_production_started=True,
        timing_or_throughput_gain_claimed=False)
    with Path(job['report']).open('x') as output:
        json.dump(report, output, indent=2, allow_nan=False); output.write('\n')
        output.flush(); os.fchmod(output.fileno(), 0o444); os.fsync(output.fileno())
    print(json.dumps(dict(passed=passed, tests=29, report=job['report'])))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
