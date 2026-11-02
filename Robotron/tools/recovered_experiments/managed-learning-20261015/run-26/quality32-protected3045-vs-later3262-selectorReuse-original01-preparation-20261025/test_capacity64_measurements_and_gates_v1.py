"""Bounded CPU guards of original-rate readers and separate fixed ABBA gates."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).resolve().parent
P = N / 'future-evaluator-concurrency64-UNSELECTED-source-preparation-original02'


def load(name, path, digest=None):
    if digest:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


h = load('_capacity_reader_tests_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
         '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
reader = load('_capacity_reader_tests_reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
              'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
private = load('_capacity_reader_tests_private', P / 'capacity_measurements_v1.py',
               '29f67a6e838e617b8f08c171c84b37e6e778c49b541206c50c9128dcaee24a79')
main_rates = load('_capacity_reader_tests_main', P / 'capacity_main_window_v1.py',
                  'c9bf15a044d3d9c417bb1d6f2bae1bb7e55c4a632dd0e2c7851bb8d1d11d28e6')
gates = load('_capacity_reader_tests_gates', P / 'compare_capacity64_fixed_gates_v1.py',
             '46878c8ec4651f54bed1875bc1b84513198890d0c00d0dfff4d8672a44d70422')


def synthetic_main():
    result = []
    for i in range(601):
        # The pipeline's own interval is intentionally599s across API598s.
        pipeline_clock = 1000 + Fraction(i * 599, 598)
        exposure = dict(schema='robotron-optimizer-exposure-v1', available=True, enabled=True,
                        process_id=1234, instance_monotonic_ns=789, epoch=1,
                        total=dict(attempts_started=1000 + i * 10, outcomes_recorded=1000 + i * 10,
                                   applied=1000 + i * 10, amp_skipped=0, unavailable=0))
        api = dict(ts=10000 + i, frame_count=100000 + i * 7000, client_count=192, training_enabled=True,
                   pipeline_read_error='', pipeline_snapshot_age_s=.5,
                   host_pipeline=dict(schema='robotron-host-pipeline-v1', available=True, generation=0,
                                      elapsed_s=float(pipeline_clock), learning_exposure=dict(optimizer=exposure)))
        result.append(dict(index=i, sample=dict(synthetic_only_index=i), begin=10000 + i + .01,
                           end=10000 + i + .02, observed=10000 + i + .03, api=api))
    return result


def get_main(rows):
    return main_rates.rates_from_records(rows, start_unix=10000, end_unix=10600, main_pid=1234)


def math_records():
    records = {}
    for i, name in enumerate(gates.ORDER):
        fleet, admitted = Fraction(7000), Fraction(409600)
        duration = 600000000000
        fps = 1000 if i in (0, 3) else 1200
        main = dict(schema='robotron-capacity64-main-own-clock-rates-v1', held_batch_size=4096,
                    own_clocks_kept_separate=True, stable_epochs_and_monotonic_counters_verified=True,
                    unavailable_outcomes_within_window=0, quality_qualified=False, bound_main_process_id=1234,
                    stable_optimizer_instance_epoch_pipeline_generation=[1234, 789, 1, 0],
                    fleet_frames=int(fleet * 600), fleet_elapsed_s=main_rates.ratio(Fraction(600)),
                    fleet_frame_rate=main_rates.ratio(fleet), optimizer_applied_admissions=60000,
                    admitted_rows=4096 * 60000, optimizer_pipeline_elapsed_s=main_rates.ratio(Fraction(600)),
                    admitted_optimizer_row_rate=main_rates.ratio(admitted))
        records[name] = dict(schema='robotron-evaluator-count-active600-independent-measurements-v1',
                             actor_count=32 if i in (0, 3) else 64, active_duration_ns=duration,
                             accepted_frames=fps * 600, all_declared_original_slot_identities_and_counter_advances_verified=True,
                             all_active_statuses_advance_every_slot=True,
                             exact_rates_and_descriptive_costs_recomputed_without_runtime_measurement_helper=True,
                             no_comparison_decision_until_all4_originals_closed=True,
                             selector_CPU_cross_shape_comparison_used=False, quality_qualified=False, main_rates=main)
    return records


class MeasurementGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.fixtures = []
        for count in (32, 64):
            root = Path(cls.temp.name) / str(count);root.mkdir()
            values = {}
            def put(name, value):
                pin = h.put(root / name, value);values[pin['path']] = copy.deepcopy(value);return pin
            job = dict(output=str(root), capacity_shape=dict(actor_count=count, games_per_slot=64 // count,
                       expected_games=64, identity_count=2 * count, inference_max_batch_size=16),
                       quota64_source_pins=dict(view=dict(sha256='a' * 64)))
            job_pin = put('job.json', job)
            def endpoint(ns, accepted):
                return dict(schema='robotron-selector-active-endpoint-v1', read_started_monotonic_ns=ns,
                            read_ended_monotonic_ns=ns + 1000000, midpoint_monotonic_ns=ns + 500000,
                            slots={str(k):dict(pid=k, birth=20, accepted=accepted, rejected=0, sequence=accepted)
                                   for k in range(4096, 4096 + count)})
            start, end = endpoint(10**9, 1200), endpoint(601 * 10**9, 121200)
            put('original-active-start.json', start)
            timing_source = load('_capacity_reader_test_timing_' + str(count),
                                 P / ('A32' if count == 32 else 'B64') / 'selector_native_timing_v1.py')
            rate = timing_source.window_rates(start, end)
            rate_pin = put('rate.json', rate)
            status_root = root / 'status-samples';status_root.mkdir()
            for i in range(100):
                slots = {str(k):dict(pid=k, birth=20, actual_exit=None, error=None, prefix_verified=True,
                                    stop_sent=False, ledger=dict(accepted=1200 + i * 1000, rejected=0))
                         for k in range(4096, 4096 + count)}
                put('status-samples/' + f'{i:04d}.json', dict(original_job=job_pin, errors=[], active_start=start,
                                                         observed_unix_s=1000 + i * 6, slots=slots))
            timing = dict(schema='robotron-selector-native-call-timing-v1', selector_source_sha256='a' * 64,
                          clock='monotonic_ns/thread_time_ns',
                          columns=['start_monotonic_ns', 'end_monotonic_ns', 'thread_CPU_ns', 'thread_id',
                                   'known_starts', 'completed', 'pending', 'exceptional'],
                          all_calls_retained=True, original_method_restored=True, overflowed=False,
                          active_calls_at_close=0, capacity=131072,
                          rows=[[2 * 10**9 + i * 1000000, 2 * 10**9 + i * 1000000 + 100, 50, 1,
                                 count, 0, count, False] for i in range(100)])
            timing_pin = put('timing.json', timing)
            result = dict(active_start=start, active_end=end, active_frame_rate=rate_pin,
                          selector_call_timing=timing_pin, original_slots={str(k):dict(pid=k, birth=20, frames=121200)
                          for k in range(4096, 4096 + count)})
            cls.fixtures.append((count, job, job_pin, result, values))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_01_private_actual32_and64_reader_coverage(self):
        for count, job, jp, result, values in self.fixtures:
            with self.subTest(count=count):
                actual = private.analyse_private(job, jp, result, lambda pin:copy.deepcopy(values[pin['path']]), h)
                self.assertEqual(actual['accepted_frames'], count * 120000)
                self.assertEqual(actual['aggregate_accepted_frame_FPS'], count * 200)
                self.assertEqual(actual['actor_count'], count)
                self.assertEqual(len(actual['all_active_native_statuses']), 100)

    def test_02_CPU_shape_cost_is_descriptive_not_a_cross_shape_gate(self):
        for count, job, jp, result, original in self.fixtures:
            values = copy.deepcopy(original)
            for row in values[result['selector_call_timing']['path']]['rows']:row[4] += 1
            r = private.analyse_private(job, jp, result, lambda pin:copy.deepcopy(values[pin['path']]), h)
            self.assertEqual(r['descriptive_initial_shape']['count'], 0)
            self.assertIsNone(r['descriptive_initial_shape']['median_thread_CPU_ns_twice'])

    def test_03_private_missing_slot_rejection_identity_and_forged_rate_refused(self):
        for count, job, jp, original_result, original_values in self.fixtures:
            for mutation in ['missing', 'rejected', 'identity', 'rate', 'overflow', 'status']:
                result, values = copy.deepcopy(original_result), copy.deepcopy(original_values)
                rate = values[result['active_frame_rate']['path']]
                if mutation == 'missing':
                    result['active_end']['slots'].pop('4096');rate['end'] = result['active_end']
                elif mutation == 'rejected':
                    result['active_end']['slots']['4096']['rejected'] = 1;rate['end'] = result['active_end']
                elif mutation == 'identity':
                    result['original_slots']['4096']['birth'] += 1
                elif mutation == 'rate':rate['aggregate_midpoint_FPS'] += .01
                elif mutation == 'overflow':values[result['selector_call_timing']['path']]['overflowed'] = True
                else:values[str(Path(job['output']) / 'status-samples/0050.json')]['slots']['4096']['error'] = 'stopped'
                with self.subTest(count=count, mutation=mutation), self.assertRaises((AssertionError, KeyError)):
                    private.analyse_private(job, jp, result, lambda pin:copy.deepcopy(values[pin['path']]), h)

    def test_04_parent_inverse_derivation_is_exact(self):
        proof = json.loads((P / 'measurement-reader-source-derivation-original01.json').read_text())
        source = Path(proof['derived']['path']).read_text().split('\nMAIN_RATE_READER = ', 1)[0]
        for before, after in reversed(proof['exact_changes']):
            self.assertEqual(source.count(after), 1);source = source.replace(after, before)
        self.assertEqual(source, Path(proof['parent']['path']).read_text())

    def test_05_main_rates_use_separate_own_clocks(self):
        r = get_main(synthetic_main())
        self.assertEqual(gates.fraction(r['fleet_frame_rate']), 7000)
        self.assertEqual(gates.fraction(r['optimizer_pipeline_elapsed_s']), 599)
        self.assertEqual(r['optimizer_applied_admissions'], 5980)
        self.assertEqual(gates.fraction(r['admitted_optimizer_row_rate']), Fraction(5980 * 4096, 599))

    def test_06_main_reset_epoch_generation_or_wrong_process_refused(self):
        for mutation in ['epoch', 'generation', 'process', 'instance', 'counter']:
            rows = synthetic_main();p = rows[300]['api']['host_pipeline'];e = p['learning_exposure']['optimizer']
            if mutation == 'epoch':e['epoch'] += 1
            elif mutation == 'generation':p['generation'] += 1
            elif mutation == 'process':e['process_id'] += 1
            elif mutation == 'instance':e['instance_monotonic_ns'] += 1
            else:e['total']['applied'] = 0;e['total']['amp_skipped'] = e['total']['outcomes_recorded']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):get_main(rows)

    def test_07_main_unavailable_stale_or_nonfinite_refused(self):
        for mutation in ['unavailable', 'stale', 'disabled', 'nan', 'clock', 'missing_index']:
            rows = synthetic_main();a = rows[300]['api'];p = a['host_pipeline'];e = p['learning_exposure']['optimizer']
            if mutation == 'unavailable':e['total']['applied'] -= 1;e['total']['unavailable'] += 1
            elif mutation == 'stale':a['pipeline_snapshot_age_s'] = 2.1
            elif mutation == 'disabled':e['available'] = False
            elif mutation == 'nan':p['elapsed_s'] = float('nan')
            elif mutation == 'clock':p['elapsed_s'] = 1
            else:rows.pop(300)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):get_main(rows)

    def test_08_raw_API_digest_and_bytes_refused(self):
        r = dict(transport=dict(raw_API=dict(base64='e30=', bytes=2, sha256='0' * 64)))
        with self.assertRaises(ValueError):main_rates.unpack_api({}, r)

    def test_09_actual_historical_main_decode_and_own_clock_replay(self):
        # Original historical data tests this new reader, and never supplies new
        # ABBA measurements, native validity or64-startup evidence.
        root = N / 'selector-active600-counterbalanced-engineering-original01/02-B1-proposal'
        job = json.loads((root / 'job.json').read_text())
        result = json.loads((root / 'diagnostic-output-original01/result.json').read_text())
        actual = main_rates.analyse(job, result, lambda p:reader.read_pin(p))
        self.assertGreater(actual['fleet_frames'], 0)
        self.assertGreater(actual['optimizer_applied_admissions'], 0)
        self.assertGreaterEqual(actual['selected_inner_window_samples'], 100)
        self.assertEqual(actual['bound_main_process_id'], 3615927)
        self.assertFalse(actual['learning_speed_gain_verified'])
        HISTORICAL_READBACK.append(actual)

    def test_10_exact_threshold_passes_without_rounding(self):
        result = gates.compare(math_records(), gates.SPEC)
        self.assertTrue(result['both_independent_B_gates_passed'])
        self.assertFalse(result['candidate_B_pool_used'])

    def test_11_no_B_pool_or_one_repeat_rescue(self):
        for name in gates.ORDER[1:3]:
            records = math_records();records[name]['accepted_frames'] -= 1
            other = gates.ORDER[2] if name == gates.ORDER[1] else gates.ORDER[1]
            records[other]['accepted_frames'] *= 10
            result = gates.compare(records, gates.SPEC)
            self.assertFalse(result['both_independent_B_gates_passed'])
            self.assertFalse(result['independent_B_gates'][name]['passed'])

    def test_12_fixed_A_reference_is_mean_of_rates_not_pooled_frames(self):
        records = math_records();a2 = records[gates.ORDER[3]]
        a2['active_duration_ns'] *= 2  # Same frames, half the original A2 rate.
        result = gates.compare(records, gates.SPEC)
        self.assertEqual(gates.fraction(result['fixed_A_reference']['private']), 750)

    def test_13_each_main_gate_is_independent(self):
        for field in ['fleet', 'admitted']:
            records = math_records();r = records[gates.ORDER[1]]['main_rates']
            if field == 'fleet':
                r['fleet_frames'] = int(r['fleet_frames'] * .94)
                r['fleet_frame_rate'] = main_rates.ratio(Fraction(r['fleet_frames'], 600))
            else:
                r['optimizer_applied_admissions'] = 56400;r['admitted_rows'] = 56400 * 4096
                r['admitted_optimizer_row_rate'] = main_rates.ratio(Fraction(r['admitted_rows'], 600))
            self.assertFalse(gates.compare(records, gates.SPEC)['both_independent_B_gates_passed'])

    def test_14_gate_contract_drift_or_incomplete_originals_refused(self):
        for mutation in ['pool', 'threshold', 'CPU', 'missing', 'validity', 'shape', 'epoch', 'forged_rate', 'bool']:
            records = math_records();spec = copy.deepcopy(gates.SPEC);r = records[gates.ORDER[2]]
            if mutation == 'pool':spec['candidate_B_pooling'] = True
            elif mutation == 'threshold':spec['private_accepted_frame_min_ratio'] = [119, 100]
            elif mutation == 'CPU':spec['selector_CPU_cost_gate'] = True
            elif mutation == 'missing':records.pop(gates.ORDER[3])
            elif mutation == 'validity':r['all_active_statuses_advance_every_slot'] = False
            elif mutation == 'shape':r['actor_count'] = 63
            elif mutation == 'epoch':r['main_rates']['stable_optimizer_instance_epoch_pipeline_generation'][2] += 1
            elif mutation == 'forged_rate':r['main_rates']['fleet_frame_rate']['numerator'] += 1
            else:r['active_duration_ns'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):gates.compare(records, spec)


HISTORICAL_READBACK = []


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MeasurementGuards))
    report = dict(schema='robotron-capacity64-measurement-and-exact-gate-CPU-results-v1', tests_run=result.testsRun,
                  passed=result.wasSuccessful(), failures=len(result.failures), errors=len(result.errors),
                  source=h.pin(__file__), private_reader=h.pin(private.__file__), main_reader=h.pin(main_rates.__file__),
                  comparator=h.pin(gates.__file__), historical_main_reader_positive_readback=HISTORICAL_READBACK,
                  synthetic32_64_reader_fixtures_only=True, actual64_startup_verified=False,
                  native_launch_ready=False, quality_qualified=False, throughput_gain_verified=False,
                  learning_speed_gain_verified=False)
    target = P / 'CPU-measurements-and-gates-original01' / 'actual-CPU-measurement-and-gate-results.json'
    print(json.dumps(dict(report=h.put(target, report), tests_run=result.testsRun, passed=result.wasSuccessful())), flush=True)
    time.sleep(8)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
