"""Synthetic arithmetic contracts only; never evaluator/runtime/playing evidence."""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-guards', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256')
    args = parser.parse_args()
    if not args.run_guards:
        print('PLAN_ONLY'); return 0
    assert hashlib.sha256(args.job.read_bytes()).hexdigest() == args.job_sha256
    job = json.loads(args.job.read_text())
    assert job['schema'] == 'robotron-selector-active600-exact-gate-guards-job-v1'
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == job['runner_sha256']
    # Avoid adding a CPU job during any of the four measured native windows.
    assert len(job['native_units']) == 4
    for unit in job['native_units']:
        process = subprocess.run(['systemctl', '--user', 'show', unit], capture_output=True, text=True, timeout=5)
        assert process.returncode == 0
        fields = dict(line.split('=', 1) for line in process.stdout.splitlines() if '=' in line)
        assert fields['LoadState'] == 'not-found'
    pin = job['comparator']
    assert hashlib.sha256(Path(pin['path']).read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location('_exact_gate_contract', pin['path'])
    comparator = importlib.util.module_from_spec(spec); spec.loader.exec_module(comparator)
    assert hashlib.sha256(Path(job['design']['path']).read_bytes()).hexdigest() == job['design']['sha256']
    design = json.loads(Path(job['design']['path']).read_bytes())
    names = [row['case'] for row in design['ordered_cases']]

    def measurement(cost=1000, frames=60000, duration=600000000000, count=100):
        return dict(schema='robotron-active600-independent-selector-measurements-v1',
            active_duration_ns=duration, accepted_frames=frames, quality_qualified=False,
            exact_rates_and_stratum_recomputed_without_runtime_measurement_helper=True,
            all32_original_slot_identities_and_counter_advances_verified=True,
            all_active_statuses_advance_every_slot=True,
            fixed_stratum=dict(known_starts=32, completed=0, pending=32, count=count,
                thread_CPU_ns=[cost] * count, median_thread_CPU_ns_twice=2 * cost))

    def cases():
        return {names[0]: measurement(), names[1]: measurement(cost=900, frames=57000),
                names[2]: measurement(cost=900, frames=57000), names[3]: measurement()}

    class Contracts(unittest.TestCase):
        def test_exact_CPU_and_FPS_boundaries_pass_both(self):
            result = comparator.compare(cases(), design)
            self.assertTrue(result['both_independent_B_gates_passed'])
            self.assertTrue(all(row['CPU_gate_left_integer'] == row['CPU_gate_right_integer']
                                and row['FPS_gate_left_integer'] == row['FPS_gate_right_integer']
                                for row in result['independent_B_gates'].values()))
            self.assertFalse(result['quality_qualified'] or result['policy_promoted'])

        def test_one_CPU_nanosecond_above_boundary_fails_B1(self):
            data = cases(); data[names[1]] = measurement(cost=901, frames=57000)
            result = comparator.compare(data, design)
            self.assertFalse(result['independent_B_gates']['B1']['CPU_gate_passed'])
            self.assertTrue(result['independent_B_gates']['B2']['passed'])
            self.assertFalse(result['both_independent_B_gates_passed'])

        def test_one_accepted_frame_below_boundary_fails_B2(self):
            data = cases(); data[names[2]] = measurement(cost=900, frames=56999)
            result = comparator.compare(data, design)
            self.assertFalse(result['independent_B_gates']['B2']['FPS_gate_passed'])
            self.assertFalse(result['both_independent_B_gates_passed'])

        def test_large_B2_gain_cannot_rescue_failed_B1(self):
            data = cases(); data[names[1]] = measurement(cost=901, frames=56999)
            data[names[2]] = measurement(cost=1, frames=600000)
            result = comparator.compare(data, design)
            self.assertFalse(result['both_independent_B_gates_passed'])
            self.assertTrue(result['independent_B_gates']['B2']['passed'])
            self.assertFalse(result['candidate_B_pool_used'])

        def test_large_exact_FPS_integers_do_not_round_into_a_pass(self):
            scale = (1 << 60) + 1
            data = {name: measurement(frames=20 * scale) for name in (names[0], names[3])}
            data[names[1]] = measurement(cost=900, frames=19 * scale - 1)
            data[names[2]] = measurement(cost=900, frames=19 * scale)
            result = comparator.compare(data, design)
            self.assertFalse(result['independent_B_gates']['B1']['FPS_gate_passed'])
            self.assertTrue(result['independent_B_gates']['B2']['FPS_gate_passed'])

        def test_large_exact_CPU_integers_do_not_round_into_a_pass(self):
            scale = (1 << 60) + 1
            data = {name: measurement(cost=10 * scale) for name in (names[0], names[3])}
            data[names[1]] = measurement(cost=9 * scale + 1, frames=57000)
            data[names[2]] = measurement(cost=9 * scale, frames=57000)
            result = comparator.compare(data, design)
            self.assertFalse(result['independent_B_gates']['B1']['CPU_gate_passed'])
            self.assertTrue(result['independent_B_gates']['B2']['CPU_gate_passed'])

        def test_all_A_calls_form_reference_without_median_of_medians(self):
            data = cases(); data[names[3]] = measurement(cost=2000, count=300)
            for name in (names[1], names[2]): data[name] = measurement(cost=1800, frames=57000)
            result = comparator.compare(data, design)
            self.assertEqual(result['fixed_reference_call_count'], 400)
            self.assertEqual(result['fixed_reference_median_CPU_ns_twice'], 4000)
            self.assertTrue(result['both_independent_B_gates_passed'])

        def test_reference_FPS_is_mean_of_rates_not_pooled_frames_per_time(self):
            data = cases(); data[names[3]] = measurement(frames=120200, duration=601000000000)
            for name in (names[1], names[2]): data[name] = measurement(cost=900, frames=85500)
            result = comparator.compare(data, design)
            self.assertEqual(result['fixed_reference_mean_accepted_frame_FPS'], 150)
            self.assertTrue(result['both_independent_B_gates_passed'])

        def test_missing_original_is_rejected(self):
            data = cases(); del data[names[3]]
            with self.assertRaises(ValueError): comparator.compare(data, design)

        def test_minimum_stratum_count_applies_to_each_original(self):
            for name in names:
                data = cases(); data[name] = measurement(count=99)
                with self.subTest(case=name), self.assertRaises(ValueError): comparator.compare(data, design)

        def test_wrong_shape_or_dishonest_count_or_median_rejected(self):
            for field, value in [('known_starts', 33), ('pending', 31), ('completed', 1), ('count', 101), ('median_thread_CPU_ns_twice', 1)]:
                data = cases(); data[names[1]]['fixed_stratum'][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError): comparator.compare(data, design)

        def test_short_window_noninteger_or_unverified_record_rejected(self):
            for field, value in [('active_duration_ns', 599999999999), ('accepted_frames', True),
                                 ('quality_qualified', True), ('all_active_statuses_advance_every_slot', False),
                                 ('exact_rates_and_stratum_recomputed_without_runtime_measurement_helper', False)]:
                data = cases(); data[names[2]][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError): comparator.compare(data, design)

        def test_changed_order_threshold_pooling_or_zero_reference_rejected(self):
            for change in ('order', 'CPU', 'FPS', 'pool'):
                altered = copy.deepcopy(design)
                if change == 'order': altered['ordered_cases'].reverse()
                elif change == 'CPU': altered['fixed_engineering_gates']['B1']['minimum_selector_median_CPU_reduction'] = .01
                elif change == 'FPS': altered['fixed_engineering_gates']['B1']['minimum_accepted_frame_FPS_ratio'] = .90
                else: altered['fixed_engineering_gates']['candidate_B_pooling_for_gate'] = True
                with self.subTest(change=change), self.assertRaises(ValueError): comparator.compare(cases(), altered)
            data = cases()
            for name in (names[0], names[3]): data[name] = measurement(cost=0)
            with self.assertRaises(ValueError): comparator.compare(data, design)

    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    passed = result.wasSuccessful() and result.testsRun == 13 and not result.skipped
    report = dict(schema='robotron-selector-active600-exact-gate-guards-result-v1',
        passed=passed, tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        log=stream.getvalue(), job=job, synthetic_arithmetic_only=True, original_engineering_measurements_not_read=True,
        runtime_or_quality_result=False)
    with Path(job['report']).open('x') as output:
        json.dump(report, output, indent=2, allow_nan=False); output.write('\n')
        output.flush(); os.fchmod(output.fileno(), 0o444); os.fsync(output.fileno())
    print(json.dumps(dict(passed=passed, tests=13, report=job['report'])))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
