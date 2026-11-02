"""CPU-only geometry, selection, timing and refusal guards; never a GPU job."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).resolve().parent
P = N / 'future-evaluator-concurrency64-UNSELECTED-source-preparation-original02'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


H_PATH = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
assert hashlib.sha256(H_PATH.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
h = load('_capacity_guards_h', H_PATH)
INDEX_PATH = P / 'CPU-fixture-index-v2.json'
assert hashlib.sha256(INDEX_PATH.read_bytes()).hexdigest() == '23e79011cceacbc9cc73a03c11e37e4d9d5ce646d17643906e823a2d58b70064'
INDEX = json.loads(INDEX_PATH.read_bytes())
CASES = []
for c in INDEX['cases']:
    modules = {}
    for kind, pin in c['sources'].items():
        modules[kind] = load('_capacity_' + c['role'] + '_' + kind, h.checked(pin))
    CASES.append((c, modules, json.loads(h.checked(c['job']).read_bytes())))


class CapacitySourceGuards(unittest.TestCase):
    def test_01_shapes_and_128_distinct_IDs_keep_64hex_hashes(self):
        for c, modules, job in CASES:
            with self.subTest(role=c['role']):
                n = c['actor_count']
                self.assertEqual(modules['runtime'].validate_job(job, cpu_initializer=True), Path(job['output']))
                for module in modules.values():
                    self.assertEqual(module.ACTOR_COUNT, n)
                    self.assertEqual(module.GAMES_PER_SLOT, 64 // n)
                    if hasattr(module, 'SLOTS'):
                        self.assertEqual(tuple(module.SLOTS), tuple(range(4096, 4096 + n)))
                self.assertEqual(len(set([*job['sessions'].values(), *job['connections'].values()])), 2 * n)
                self.assertTrue(all(len(v) == 32 for v in [*job['sessions'].values(), *job['connections'].values()]))
                self.assertEqual(len(job['checkpoint']['sha256']), 64)
                self.assertEqual(job['capacity_shape']['expected_games'], 64)
                self.assertEqual(job['capacity_shape']['inference_max_batch_size'], 16)

    def test_02_native_mode_refuses_fixture(self):
        for c, m, job in CASES:
            with self.subTest(role=c['role']):
                with self.assertRaises(ValueError):
                    m['runtime'].validate_job(job)
                with self.assertRaises(ValueError):
                    m['runtime'].validate_job(job, cpu_initializer=1)

    def test_03_malformed_geometry_refused(self):
        for c, m, job in CASES:
            for field, value in [('actor_count', 63), ('games_per_slot', 3), ('expected_games', 63),
                                 ('identity_count', 64 if c['actor_count'] == 64 else 128), ('inference_max_batch_size', 32)]:
                bad = copy.deepcopy(job);bad['capacity_shape'][field] = value
                with self.subTest(role=c['role'], field=field), self.assertRaises(ValueError):
                    m['runtime'].validate_job(bad, cpu_initializer=True)

    def test_04_missing_slots_and_duplicate_cross_identity_refused(self):
        for c, m, job in CASES:
            variants = []
            bad = copy.deepcopy(job);bad['actor_slots'].pop();variants.append(bad)
            bad = copy.deepcopy(job);bad['sessions'].pop('4096');variants.append(bad)
            bad = copy.deepcopy(job);bad['connections']['4096'] = bad['sessions']['4096'];variants.append(bad)
            bad = copy.deepcopy(job);bad['sessions']['4096'] = '0' * 32;variants.append(bad)
            for i, bad in enumerate(variants):
                with self.subTest(role=c['role'], variant=i), self.assertRaises(ValueError):
                    m['runtime'].validate_job(bad, cpu_initializer=True)

    def test_05_wrong_GPU_ports_policy_backend_and_scientific_fields_refused(self):
        for c, m, job in CASES:
            variants = []
            for field, value in [('gpu_uuid', 'GPU-wrong'), ('origin_port', 9998), ('backend', 'eager'),
                                 ('wall_limit_s', 961), ('startup_trace_frames', 1199), ('quality_leg', 'C1')]:
                bad = copy.deepcopy(job);bad[field] = value;variants.append(bad)
            bad = copy.deepcopy(job);bad['proxy_ports']['4096'] = 20001;variants.append(bad)
            bad = copy.deepcopy(job);bad['expected_policy_clocks']['training_steps'] += 1;variants.append(bad)
            bad = copy.deepcopy(job);bad['checkpoint']['sha256'] = 'a' * 64;variants.append(bad)
            bad = copy.deepcopy(job);bad['quota64_source_pins']['view']['sha256'] = 'a' * 64;variants.append(bad)
            for i, bad in enumerate(variants):
                with self.subTest(role=c['role'], variant=i), self.assertRaises(ValueError):
                    m['runtime'].validate_job(bad, cpu_initializer=True)

    def test_06_common_controller_resources_and_exact_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'config.json'
            for c, m, job in CASES:
                cfg = json.loads(h.checked(c['config']).read_bytes())
                self.assertEqual(m['controller'].checked_config(c['config']['path']), cfg)
                for old, new in [('MemoryMax=24G', 'MemoryMax=16G'), ('CPUQuota=1200%', 'CPUQuota=1300%'),
                                 ('TasksMax=512', 'TasksMax=1024'), ('SendSIGKILL=no', 'SendSIGKILL=yes')]:
                    bad = copy.deepcopy(cfg);bad['properties'][bad['properties'].index(old)] = new;p.write_text(json.dumps(bad))
                    with self.subTest(role=c['role'], property=old), self.assertRaises(ValueError):
                        m['controller'].checked_config(p)
                bad = copy.deepcopy(cfg);bad['argv'][4] = '/bin/false';p.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    m['controller'].checked_config(p)

    @staticmethod
    def starts(n, rounds=3):
        return [dict(journal_game_id='123:' + str(turn * n + i + 1), experiment='test',
                     client_slot=4096 + i, known_start=True, measurement_active=True,
                     start_unix_s=100 + turn, score=10**9 if turn == 2 else i)
                for turn in range(rounds) for i in range(n)]

    def test_07_raw_first_occurrence_selection_is_score_independent(self):
        for c, m, job in CASES:
            n = c['actor_count'];rows = self.starts(n)
            selected, counts, outside = m['games'].select_original_starts(rows, 'test', 99, 103, source_is_start_order=True)
            self.assertEqual(len(selected), 64)
            self.assertEqual(set(counts.values()), {64 // n})
            self.assertEqual(list(selected), [r['journal_game_id'] for r in rows[:64]])
            self.assertEqual(len(outside), 3 * n - 64)
            reversed_selected = m['games'].select_original_starts(list(reversed(rows)), 'test', 99, 103, source_is_start_order=False)[0]
            self.assertEqual(selected, reversed_selected)

    def test_08_missing_and_late_starts_never_replaced_by_scores(self):
        for c, m, job in CASES:
            n = c['actor_count'];rows = self.starts(n, 64 // n)
            rows[-1]['start_unix_s'] = 104
            selected, counts, outside = m['games'].select_original_starts(rows, 'test', 99, 103, source_is_start_order=True)
            self.assertEqual(len(selected), 63);self.assertEqual(counts[4096 + n - 1], 64 // n - 1)
            self.assertEqual(outside, [rows[-1]['journal_game_id']])
            for mutate in ['known', 'foreign', 'order']:
                bad = copy.deepcopy(rows)
                if mutate == 'known':bad[0]['known_start'] = False
                elif mutate == 'foreign':bad[0]['client_slot'] = 4096 + n
                else:bad[1]['journal_game_id'] = bad[0]['journal_game_id']
                with self.subTest(role=c['role'], mutate=mutate), self.assertRaises(ValueError):
                    m['games'].select_original_starts(bad, 'test', 99, 103, source_is_start_order=True)

    @staticmethod
    def endpoints(n):
        def endpoint(start, accepted):
            return dict(read_started_monotonic_ns=start, read_ended_monotonic_ns=start + 1000000,
                        midpoint_monotonic_ns=start + 500000,
                        slots={str(slot):dict(pid=1000 + slot, birth=100, accepted=accepted, rejected=0)
                               for slot in range(4096, 4096 + n)})
        return endpoint(10**9, 1200), endpoint(601 * 10**9, 121200)

    def test_09_active_rate_covers_all_slots_and_brackets(self):
        for c, m, job in CASES:
            start, end = self.endpoints(c['actor_count']);r = m['timing'].window_rates(start, end)
            self.assertEqual(r['accepted_frames'], c['actor_count'] * 120000)
            self.assertEqual(r['aggregate_midpoint_FPS'], c['actor_count'] * 200)
            self.assertLessEqual(r['aggregate_bracket_low_FPS'], r['aggregate_midpoint_FPS'])
            self.assertGreaterEqual(r['aggregate_bracket_high_FPS'], r['aggregate_midpoint_FPS'])
            self.assertFalse(r['useful_training_throughput_claim']);self.assertFalse(r['learning_speed_claim'])

    def test_10_active_rate_refuses_missing_nonadvancing_rejected_or_replaced(self):
        for c, m, job in CASES:
            for mutation in ['missing', 'stalled', 'rejected', 'replaced', 'clock']:
                start, end = self.endpoints(c['actor_count'])
                if mutation == 'missing':end['slots'].pop('4096')
                elif mutation == 'stalled':end['slots']['4096']['accepted'] = 1200
                elif mutation == 'rejected':end['slots']['4096']['rejected'] = 1
                elif mutation == 'replaced':end['slots']['4096']['birth'] = 101
                else:end['read_started_monotonic_ns'] = start['read_started_monotonic_ns']
                with self.subTest(role=c['role'], mutation=mutation), self.assertRaises(ValueError):
                    m['timing'].window_rates(start, end)

    def test_11_missing_closeout_refuses_before_output_or_GPU_boundary(self):
        for c, m, job in CASES:
            runtime = m['runtime']
            self.assertFalse(Path(job['prelaunch_family_guard_closeout']).exists())
            with patch.object(runtime.PrivateLease, 'acquire', side_effect=AssertionError('GPU lease forbidden')) as lease, \
                 patch.object(runtime.subprocess, 'run', side_effect=AssertionError('subprocess forbidden')) as process, \
                 patch.object(runtime.threading.Thread, 'start', side_effect=AssertionError('thread forbidden')) as thread:
                with self.assertRaises(FileNotFoundError):
                    runtime.run(job, c['job'], h, cpu_initializer=True)
                self.assertFalse(Path(job['output']).exists())
                lease.assert_not_called();process.assert_not_called();thread.assert_not_called()

    def test_12_source_cross_bindings_and_default_inert_structure(self):
        for c, m, job in CASES:
            self.assertEqual(m['drain'].VIEW_SHA, c['sources']['view']['sha256'])
            self.assertEqual(m['runtime'].TIMING_SOURCE_SHA, c['sources']['timing']['sha256'])
            self.assertEqual(m['runtime'].REFERENCE_SHA, job['checkpoint']['sha256'])
            self.assertEqual(m['drain'].COHORT_SELECTION['expected_games'], 64)
            self.assertEqual(m['drain'].COHORT_SELECTION['minimum_complete_games'], 50)
            runtime_text = Path(c['sources']['runtime']['path']).read_text()
            self.assertIn('CPU_INITIALIZER_STOP_BEFORE_GPU_LEASE_WORKER_TORCH_MAME', runtime_text)
            self.assertLess(runtime_text.index("if cpu_initializer:\n            raise RuntimeError"), runtime_text.index('lease_entry = lease.acquire()'))
            self.assertNotIn('torch', sys.modules)
            ast.parse(runtime_text)


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CapacitySourceGuards)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps(dict(schema='robotron-capacity64-CPU-source-guard-results-v1',
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), passed=result.wasSuccessful(),
        source=h.pin(__file__), fixtures=h.pin(INDEX_PATH), native_jobs_launched=False,
        actual_GPU_lease_or_Torch_or_MAME_started=False, actual64_startup_verified=False,
        quality_qualified=False, throughput_gain_verified=False)), flush=True)
    time.sleep(8)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
