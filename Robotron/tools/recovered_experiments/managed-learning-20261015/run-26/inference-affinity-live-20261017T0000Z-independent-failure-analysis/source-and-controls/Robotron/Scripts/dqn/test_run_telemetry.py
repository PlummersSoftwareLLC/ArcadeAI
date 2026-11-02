"""Bounded, read-only reporting and CSV compatibility checks; no GPU sampler."""
import copy
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import run_telemetry as module


def measurement(count=0, total=0, maximum=0):
    return dict(count=count, total=total, max=maximum, histogram=[count, 0])


def raw_snapshot(count=2, total=10, generation=0):
    result = dict(schema='robotron-host-pipeline-v1', available=True,
                  generation=generation, sample_every=20, elapsed_s=count*10,
                  inference_eligible_calls=count*20,
                  latency_bucket_upper_ms=[1, None], batch_size_bucket_upper=[32, None],
                  inference=dict(count=count, errors=0),
                  actor_refresh=dict(count=count, errors=0, forced_count=1),
                  target_refresh=dict(count=count, errors=0))
    for prefix, stage, name in module.PIPELINE_MEASUREMENTS:
        result[stage][name] = measurement(count, total, total)
    return result


class Actor:
    def __init__(self):
        self.calls = []
        self.data = raw_snapshot()
        self.bank = dict(writer_active=False, capture_attempts=4, capture_deferrals=1,
                         snapshot_lock_max_ms=1.2, writes=3, write_failures=0,
                         write_duration_s=2.0, last_write_duration_s=.7, last_error=None,
                         revision=dict(hof=4, ephof=5), saved_revision=dict(hof=4, ephof=3),
                         dirty=dict(hof=False, ephof=True))
        self.memory = SimpleNamespace(get_bank_persistence_stats=lambda: copy.deepcopy(self.bank))

    def pipeline_telemetry_snapshot(self, reset=False):
        self.calls.append(reset)
        if reset:
            raise AssertionError('Reports must never drain counters')
        return copy.deepcopy(self.data)


class PipelineReportingTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.cache = module.PipelineSnapshotCache(clock=lambda: self.now)
        self.actor = Actor()

    def test_shared_cache_is_bounded_read_only_and_detached(self):
        first = self.cache.get(self.actor)
        first['pipeline']['inference']['count'] = 999
        self.assertEqual(self.cache.get(self.actor)['pipeline']['inference']['count'], 2)
        self.assertEqual(self.actor.calls, [False])
        self.now += 1.1
        self.cache.get(self.actor)
        self.assertEqual(self.actor.calls, [False, False])
        self.cache.get(Actor())
        self.assertIsNot(self.cache.agent, self.actor)  # one current agent, no growing registry

    def test_getter_failure_does_not_hide_other_readouts(self):
        self.actor.pipeline_telemetry_snapshot = lambda **kwargs: (_ for _ in ()).throw(ValueError('fixture'))
        result = self.cache.get(self.actor)
        self.assertIn('ValueError', result['pipeline_read_error'])
        self.assertEqual(result['bank']['writes'], 3)
        fields = module.pipeline_report_fields(result)
        self.assertFalse(fields['pipeline_available'])
        self.assertEqual(fields['infer_batch_rows_mean'], '')
        self.assertEqual(fields['bank_snapshot_lock_max_ms'], 1.2)

    def test_interval_means_use_cumulative_deltas_and_generation_reset(self):
        first = self.cache.get(self.actor)
        self.assertEqual(module.pipeline_report_fields(first)['infer_service_host_ms_mean'], 5)
        self.actor.data = raw_snapshot(count=3, total=30)
        self.now += 2
        second = self.cache.get(self.actor)
        fields = module.pipeline_report_fields(second, first)
        self.assertEqual(fields['infer_samples'], 1)
        self.assertEqual(fields['infer_service_host_ms_mean'], 20)
        self.assertEqual(fields['infer_service_host_ms_max_cumulative'], 30)
        self.assertEqual(fields['pipeline_interval_s'], 10)
        self.actor.data = raw_snapshot(count=1, total=7, generation=1)
        self.now += 2
        fields = module.pipeline_report_fields(self.cache.get(self.actor), second)
        self.assertTrue(fields['pipeline_counter_reset'])
        self.assertEqual(fields['infer_service_host_ms_mean'], 7)

    def test_no_observations_stay_blank_and_full_histograms_survive(self):
        self.actor.data = raw_snapshot(count=0, total=0)
        fields = module.pipeline_report_fields(self.cache.get(self.actor))
        self.assertEqual(fields['infer_cpu_readback_host_ms_mean'], '')
        raw = json.loads(fields['pipeline_snapshot_json'])
        self.assertEqual(raw['latency_bucket_upper_ms'], [1, None])
        self.assertEqual(raw['inference']['cpu_readback_host_ms']['histogram'], [0, 0])
        self.assertIn('NA', module.pipeline_console_columns(fields))

    def reporter(self, directory):
        with patch.object(module.RunTelemetry, '_sample_gpu', return_value=None):
            return module.RunTelemetry(directory, 'not-used-by-tests')

    def test_dashboard_reads_do_not_consume_csv_intervals_or_change_schema(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(module, '_PIPELINE_CACHE', self.cache):
            reporter = self.reporter(directory)
            self.cache.get(self.actor)  # dashboard reads first
            reporter.write(dict(frames=100, optimized_samples=800), agent=self.actor)
            self.cache.get(self.actor)
            self.actor.data = raw_snapshot(count=3, total=30)
            self.now += 2
            self.cache.get(self.actor)  # dashboard gets the newer cumulative snapshot first
            reporter.write(dict(optimized_samples=1600, frames=200), agent=self.actor)
            self.assertEqual(self.actor.calls, [False, False])
            with reporter.path.open(newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertEqual(float(rows[1]['infer_service_host_ms_mean']), 20)
            self.assertEqual(json.loads(rows[1]['pipeline_snapshot_json'])['inference']['count'], 3)
            self.assertEqual(json.loads(rows[1]['bank_persistence_json'])['revision']['ephof'], 5)
            self.assertEqual(set(rows[0]), set(rows[1]))
            self.assertNotIn(None, rows[1])

    def test_late_telemetry_availability_does_not_change_header(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(module, '_PIPELINE_CACHE', self.cache):
            reporter = self.reporter(directory)
            self.actor.data['available'] = False
            reporter.write(dict(frames=1, optimized_samples=1), agent=self.actor)
            self.actor.data['available'] = True
            self.now += 2
            reporter.write(dict(frames=2, optimized_samples=2), agent=self.actor)
            with reporter.path.open(newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]['pipeline_available'], 'False')
            self.assertEqual(rows[1]['pipeline_available'], 'True')
            self.assertNotIn(None, rows[1])

    def test_existing_incompatible_csv_is_not_corrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'training.csv'
            original = b'utc,frames\nprevious,10\n'
            path.write_bytes(original)
            reporter = self.reporter(directory)
            with self.assertRaisesRegex(ValueError, 'schema changed'):
                reporter.write(dict(frames=2, optimized_samples=2))
            self.assertEqual(path.read_bytes(), original)

    def test_missing_or_extra_fields_cannot_silently_shift_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            reporter = self.reporter(directory)
            reporter.write(dict(frames=1, optimized_samples=1))
            original = reporter.path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'schema changed'):
                reporter.write(dict(frames=2, optimized_samples=2, unexpected=3))
            self.assertEqual(reporter.path.read_bytes(), original)

    def test_actual_dashboard_exposes_cached_full_snapshots_without_gpu_sampling(self):
        from . import config, metrics_dashboard
        metrics = config.MetricsData()
        state = metrics_dashboard._DashboardState(metrics, self.actor)
        with patch.object(metrics_dashboard, 'pipeline_snapshot', side_effect=self.cache.get), \
                patch.object(state, '_system_snapshot', return_value={}), \
                patch.object(state, '_gpu_snapshot', return_value=[]), \
                patch.object(state, '_get_model_desc', return_value='fixture'):
            result = state._build_snapshot()
        self.assertEqual(result['host_pipeline']['schema'], 'robotron-host-pipeline-v1')
        self.assertEqual(result['bank_persistence']['writes'], 3)
        self.assertIn('not GPU kernel', result['pipeline_timing_scope'])
        self.assertEqual(self.actor.calls, [False])

    def test_actual_console_passes_agent_and_prints_host_columns_with_csv(self):
        from . import config, metrics_display
        actor = self.actor
        class Memory:
            def __len__(self):
                return 6_000_000

            def hof_score_range(self):
                return None

            def get_bank_persistence_stats(self):
                return copy.deepcopy(actor.bank)

        actor.memory, actor.optimized_samples = Memory(), 2048
        actor.get_lr = lambda: .001
        lines = []
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(module, '_PIPELINE_CACHE', self.cache), \
                patch.object(metrics_display, 'metrics', config.MetricsData()), \
                patch.object(metrics_display, '_run_report', self.reporter(directory)), \
                patch.object(metrics_display, '_print_line', side_effect=lambda line, **kw: lines.append(line)):
            metrics_display.display_metrics_row(actor, None)
            self.assertIn('5.0/5.0/5.0', lines[-1])
            self.assertEqual(actor.calls, [False])
            with (Path(directory)/'training.csv').open(newline='') as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(float(row['infer_service_host_ms_mean']), 5)
            self.assertEqual(row['bank_ephof_dirty'], 'True')

    def test_dashboard_retains_full_latest_but_not_raw_history_histograms(self):
        from . import config, metrics_dashboard
        state = metrics_dashboard._DashboardState(config.MetricsData(), self.actor)
        state._sample_count, state._first_sample_time = 10, 0
        raw = dict(ts=1, host_pipeline=raw_snapshot(), bank_persistence=self.actor.bank)
        with patch.object(state, '_build_snapshot', return_value=raw), \
                patch.object(state, '_update_web_client_count_locked'):
            state.sample()
        self.assertEqual(state.latest, raw)
        self.assertIn('host_pipeline', json.loads(state.now_body()))
        self.assertNotIn('host_pipeline', state.history[-1])
        self.assertNotIn('bank_persistence', state.history[-1])


if __name__ == '__main__':
    unittest.main()
