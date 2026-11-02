"""Low-rate GPU sampling and durable, numeric per-run learning reports."""
import csv
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import threading
import time


PIPELINE_MEASUREMENTS = (
    ('infer_batch_rows', 'inference', 'batch_size'),
    *[(f'infer_{name}', 'inference', name) for name in (
        'training_lock_wait_ms', 'sync_lock_wait_ms', 'input_transfer_host_ms',
        'dispatch_host_ms', 'cpu_readback_host_ms', 'service_host_ms', 'total_host_ms')],
    *[(f'actor_refresh_{name}', 'actor_refresh', name) for name in (
        'training_lock_wait_ms', 'sync_lock_wait_ms', 'copy_host_ms',
        'service_host_ms', 'total_host_ms')],
    ('target_refresh_host_ms', 'target_refresh', 'host_ms'),
)
PIPELINE_FIELDS = (
    'pipeline_available', 'pipeline_generation', 'pipeline_sample_every',
    'pipeline_snapshot_age_s', 'pipeline_interval_s', 'pipeline_counter_reset',
    'infer_eligible_calls', 'infer_eligible_calls_total',
    *[f'{prefix}_{field}' for prefix in ('infer', 'actor_refresh', 'target_refresh')
      for field in ('samples', 'samples_total', 'errors', 'errors_total')],
    'actor_refresh_forced', 'actor_refresh_forced_total',
    *[f'{prefix}_{field}' for prefix, _, _ in PIPELINE_MEASUREMENTS
      for field in ('mean', 'max_cumulative')],
    'pipeline_read_error', 'pipeline_snapshot_json',
    'bank_available', 'bank_writer_active', 'bank_capture_attempts_total',
    'bank_capture_deferrals_total', 'bank_snapshot_lock_max_ms', 'bank_writes_total',
    'bank_write_failures_total', 'bank_write_duration_s_total',
    'bank_last_write_duration_s', 'bank_last_error',
    *[f'bank_{bank}_{field}' for bank in ('hof', 'ephof')
      for field in ('revision', 'saved_revision', 'dirty')],
    'bank_read_error', 'bank_persistence_json',
)


class PipelineSnapshotCache:
    """One agent, at most one read/second; readers never drain agent counters.

    Call outside metrics/model locks. Only reporting threads acquire this lock;
    the agent and bank getters briefly acquire their own telemetry/replay locks.
    """
    def __init__(self, interval_s=1.0, clock=time.monotonic):
        self.interval_s, self.clock = float(interval_s), clock
        self.lock = threading.Lock()
        self.agent, self.snapshot, self.sampled_at = None, None, 0.0

    def get(self, agent):
        with self.lock:
            now = self.clock()
            if self.snapshot is None or self.agent is not agent or now-self.sampled_at >= self.interval_s:
                result = dict(pipeline={}, bank={}, pipeline_read_error='', bank_read_error='')
                try:
                    getter = getattr(agent, 'pipeline_telemetry_snapshot', None)
                    if callable(getter):
                        result['pipeline'] = getter(reset=False)
                except Exception as exc:
                    result['pipeline_read_error'] = f'{type(exc).__name__}: {exc}'[:300]
                try:
                    getter = getattr(getattr(agent, 'memory', None), 'get_bank_persistence_stats', None)
                    if callable(getter):
                        result['bank'] = getter()
                except Exception as exc:
                    result['bank_read_error'] = f'{type(exc).__name__}: {exc}'[:300]
                self.agent, self.snapshot, self.sampled_at = agent, copy.deepcopy(result), now
            result = copy.deepcopy(self.snapshot)
            result['sampled_monotonic_s'] = self.sampled_at
            result['age_s'] = max(0.0, self.clock()-self.sampled_at)
            return result


_PIPELINE_CACHE = PipelineSnapshotCache()


def pipeline_snapshot(agent):
    return _PIPELINE_CACHE.get(agent)


def pipeline_report_fields(snapshot, previous=None):
    """Interval means from cumulative sums; maxima remain explicitly cumulative.

    Only the console/CSV reporter owns ``previous``. API reads cannot advance
    its interval or reset the producer. The complete raw histograms are saved.
    """
    fields = dict.fromkeys(PIPELINE_FIELDS, '')
    current, bank = snapshot.get('pipeline') or {}, snapshot.get('bank') or {}
    available = bool(current.get('available', False))
    old = (previous or {}).get('pipeline') or {}
    reset = bool(old and old.get('generation') != current.get('generation'))
    if reset or not old.get('available', False):
        old = {}
    fields.update(pipeline_available=available, bank_available=bool(bank),
                  pipeline_snapshot_age_s=snapshot.get('age_s', 0.0),
                  pipeline_read_error=snapshot.get('pipeline_read_error', ''),
                  bank_read_error=snapshot.get('bank_read_error', ''),
                  pipeline_snapshot_json=json.dumps(current, separators=(',', ':'), allow_nan=False),
                  bank_persistence_json=json.dumps(bank, separators=(',', ':'), allow_nan=False))
    if available:
        # Generation changes identify explicit producer drains. A counter
        # regression is also treated as a new segment rather than a negative rate.
        if int(current.get('inference_eligible_calls', 0)) < int(old.get('inference_eligible_calls', 0)):
            old, reset = {}, True
        fields.update(pipeline_generation=current.get('generation', 0),
                      pipeline_sample_every=current.get('sample_every', ''),
                      pipeline_counter_reset=reset,
                      pipeline_interval_s=max(0.0, float(current.get('elapsed_s', 0))-float(old.get('elapsed_s', 0))))
        def delta(value, before):
            return max(0, value-before)
        eligible = int(current.get('inference_eligible_calls', 0))
        fields['infer_eligible_calls_total'] = eligible
        fields['infer_eligible_calls'] = delta(eligible, int(old.get('inference_eligible_calls', 0)))
        for prefix, stage in (('infer', 'inference'), ('actor_refresh', 'actor_refresh'), ('target_refresh', 'target_refresh')):
            current_stage, old_stage = current.get(stage, {}), old.get(stage, {})
            for output, field in (('samples', 'count'), ('errors', 'errors')):
                value = int(current_stage.get(field, 0))
                fields[f'{prefix}_{output}_total'] = value
                fields[f'{prefix}_{output}'] = delta(value, int(old_stage.get(field, 0)))
        forced = int(current.get('actor_refresh', {}).get('forced_count', 0))
        fields['actor_refresh_forced_total'] = forced
        fields['actor_refresh_forced'] = delta(forced, int(old.get('actor_refresh', {}).get('forced_count', 0)))
        for prefix, stage, name in PIPELINE_MEASUREMENTS:
            metric = current.get(stage, {}).get(name, {})
            old_metric = old.get(stage, {}).get(name, {})
            count = delta(int(metric.get('count', 0)), int(old_metric.get('count', 0)))
            total = delta(float(metric.get('total', 0)), float(old_metric.get('total', 0)))
            fields[f'{prefix}_mean'] = total/count if count else ''
            fields[f'{prefix}_max_cumulative'] = metric.get('max', '') if metric.get('count', 0) else ''
    for name in ('writer_active', 'snapshot_lock_max_ms', 'last_write_duration_s', 'last_error'):
        fields[f'bank_{name}'] = bank.get(name, '')
    for name in ('capture_attempts', 'capture_deferrals', 'writes', 'write_failures', 'write_duration_s'):
        fields[f'bank_{name}_total'] = bank.get(name, '')
    for bank_name in ('hof', 'ephof'):
        for name in ('revision', 'saved_revision', 'dirty'):
            fields[f'bank_{bank_name}_{name}'] = bank.get(name, {}).get(bank_name, '')
    return fields


def pipeline_console_columns(fields):
    def value(key, precision=1):
        number = fields.get(key)
        return f'{number:.{precision}f}' if isinstance(number, (int, float)) else 'NA'
    timings = '/'.join(value(key) for key in (
        'infer_sync_lock_wait_ms_mean', 'infer_service_host_ms_mean', 'infer_cpu_readback_host_ms_mean'))
    refresh = '/'.join(value(key) for key in ('actor_refresh_total_host_ms_mean', 'target_refresh_host_ms_mean'))
    return (f"{value('infer_batch_rows_mean'):>5} {timings:>20} {refresh:>15} "
            f"{value('bank_snapshot_lock_max_ms'):>7}")


class RunTelemetry:
    def __init__(self, directory, gpu):
        self.started = time.monotonic()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'training.csv'
        self.gpu = gpu
        self.lock = threading.Lock()
        self.samples = []
        self.error = ''
        self.previous = None
        self.previous_pipeline = None
        self.previous_pipeline_agent = None
        self.last_pipeline_fields = dict.fromkeys(PIPELINE_FIELDS, '')
        self.fieldnames = None
        threading.Thread(target=self._sample_gpu, daemon=True, name='GPU-telemetry').start()

    def _sample_gpu(self):
        while True:
            try:
                output = subprocess.check_output([
                    'nvidia-smi', '-i', self.gpu,
                    '--query-gpu=utilization.gpu,utilization.memory,memory.used,power.draw,temperature.gpu',
                    '--format=csv,noheader,nounits'], text=True, timeout=3)
                values = tuple(float(v.strip()) for v in output.strip().split(','))
                with self.lock:
                    self.samples.append(values)
                    self.samples = self.samples[-120:]
                    self.error = ''
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                with self.lock:
                    self.error = str(exc)
            time.sleep(1)

    def write(self, values, *, agent=None):
        now = time.monotonic()
        row = dict(utc=datetime.now(timezone.utc).isoformat(), elapsed_s=now-self.started, **values)
        current = (now, values['frames'], values['optimized_samples'])
        if self.previous is not None:
            dt = max(1e-6, now-self.previous[0])
            row['frames_per_s'] = (current[1]-self.previous[1])/dt
            row['samples_per_s'] = (current[2]-self.previous[2])/dt
        else:
            row['frames_per_s'] = row['samples_per_s'] = 0.0
        self.previous = current
        row['samples_per_frame'] = row['samples_per_s']/max(1e-6, row['frames_per_s'])
        with self.lock:
            samples, self.samples = self.samples, []
            error = self.error
        keys = ('gpu_util_pct', 'gpu_memory_util_pct', 'gpu_memory_mib', 'gpu_power_w', 'gpu_temperature_c')
        for i, key in enumerate(keys):
            row[key] = sum(s[i] for s in samples)/len(samples) if samples else ''
        row['gpu_samples'] = len(samples)
        row['gpu_error'] = error
        power = row['gpu_power_w']
        row['samples_per_joule'] = row['samples_per_s']/power if power else ''
        snapshot = pipeline_snapshot(agent)
        previous = self.previous_pipeline if self.previous_pipeline_agent is agent else None
        self.last_pipeline_fields = pipeline_report_fields(snapshot, previous)
        row.update(self.last_pipeline_fields)
        exists = self.path.exists() and self.path.stat().st_size > 0
        if self.fieldnames is None:
            if exists:
                with self.path.open(newline='') as stream:
                    self.fieldnames = next(csv.reader(stream))
            else:
                self.fieldnames = list(row)
        if set(row) != set(self.fieldnames):
            raise ValueError('Training CSV schema changed; use a new run directory before reloading telemetry')
        with self.path.open('a', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=self.fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerow(row)
        self.previous_pipeline = snapshot
        self.previous_pipeline_agent = agent
        def fmt(key, precision=0):
            value = row[key]
            return f'{value:.{precision}f}' if isinstance(value, (int, float)) else 'NA'
        return (f"{row['samples_per_s']:>9.0f} {fmt('gpu_util_pct'):>5} "
                f"{fmt('gpu_power_w'):>6} {fmt('gpu_memory_mib'):>8} "
                f"{fmt('samples_per_joule', 1):>7}")


def create_report(config, model_dir):
    directory = os.getenv('ROBOTRON_RUN_DIR') or str(
        Path(model_dir).parent / 'logs' / ('run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')))
    reporter = RunTelemetry(directory, os.getenv('CUDA_VISIBLE_DEVICES', '0').split(',')[0])
    import torch
    metadata = dict(started_utc=datetime.now(timezone.utc).isoformat(),
                    reporting_schema='robotron-training-host-pipeline-v1',
                    pipeline_timing_scope='Host elapsed milliseconds, not GPU kernel duration',
                    pipeline_read_mode='Cumulative reset=False; CSV owns interval deltas',
                    config=vars(config), torch=torch.__version__,
                    gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU',
                    environment={k: v for k, v in os.environ.items()
                                 if k.startswith(('DQN_', 'ROBOTRON_', 'CUDA_VISIBLE'))})
    (reporter.directory / 'metadata.json').write_text(json.dumps(metadata, indent=2, default=str))
    print(f'Numeric training report: {reporter.path}', flush=True)
    return reporter
