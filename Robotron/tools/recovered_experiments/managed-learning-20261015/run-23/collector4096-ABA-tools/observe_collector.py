#!/usr/bin/env python3
"""Inert, read-only1Hz collector comparison observer. Explicit CLI starts work.

Adapted from run23/exposure-health-observer.py and its corrected exposure check.
No model/training imports, GPU probes, process/control writes or quality reads.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.request

HERE = Path(__file__).resolve().parent
RUN23 = HERE.parent
GAME = RUN23.parents[2]
CLOCKS = ('optimized_samples', 'frame_count', 'learner_frame_count', 'training_steps', 'measurement_frames')
API_FIELDS = (*CLOCKS, 'ts', 'host_pipeline', 'bank_persistence', 'pipeline_snapshot_age_s',
    'pipeline_read_error', 'bank_persistence_read_error', 'client_count', 'epsilon', 'expert_ratio',
    'lr', 'fps', 'steps_per_sec', 'rpl_per_frame', 'train_sample_ms', 'train_transfer_ms',
    'train_compute_ms', 'train_priority_ms', 'train_step_ms', 'avg_inf_ms', 'loss', 'grad_norm',
    'training_enabled', 'measurement_active', 'gpus', 'gpu1_util', 'gpu1_power_w', 'memory_buffer_size')
ERROR_PATTERNS = ('Batched inference request timed out', 'Batched inference failed',
    'Error receiving', 'Traceback', 'Training error:', 'ExactInferenceGraphError',
    'Non-finite loss', 'disabling torch.compile', 'torch.compile unavailable',
    'Partial read timeout', 'Invalid payload length', 'idle timeout', ' error:', ' disconnected')
ACTOR_PATTERNS = ('[SOCKET ACTION TIMEOUT]', 'socket_read_error', 'socket_write_error',
                  'Socket read error:', 'Socket write error:', 'Socket open failed:')
CSV_FIELDS = ('utc', 'replay_dropped', 'replay_pressure_waits', 'prefetched_batches')


def utc(value=None):
    return datetime.fromtimestamp(time.time() if value is None else value, timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe(value):
    """Retain nonfinite diagnostics as strings in standards-compliant raw JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    return value


def process(pid):
    try:
        fields = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()
        return dict(alive=fields[0] not in ('Z', 'X'), start_ticks=int(fields[19]))
    except (OSError, ValueError, IndexError):
        return dict(alive=False, start_ticks=None)


def stat_id(path):
    value = path.stat()
    return {key: getattr(value, 'st_' + key) for key in ('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns', 'mode', 'nlink')}


def load_health_check():
    path = RUN23 / 'exposure_health_checks.py'
    raw = path.read_bytes()
    spec = importlib.util.spec_from_file_location('collector_exposure_health', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if path.read_bytes() != raw:
        raise ValueError('Exposure checker changed while importing')
    return module.snapshot_errors, dict(path=str(path), sha256=sha(raw))


class AppendReader:
    """Read new complete lines only; never join unrelated truncated epochs."""
    def __init__(self, path):
        self.path = path
        self.file_identity = (path.stat().st_dev, path.stat().st_ino) if path.exists() else None
        self.initial_end_offset = path.stat().st_size if path.exists() else 0
        self.offset = self.initial_end_offset
        if self.offset:
            with path.open('rb') as stream:
                stream.seek(self.offset - 1)
                if stream.read(1) != b'\n':
                    width = 4096
                    while True:
                        begin = max(0, self.offset - width)
                        stream.seek(begin)
                        tail = stream.read(self.offset - begin)
                        boundary = tail.rfind(b'\n') + 1
                        if boundary or not begin:
                            self.offset = begin + boundary
                            break
                        if width >= 1024 * 1024:
                            raise ValueError('Initial partial line exceeds1MiB: ' + str(path))
                        width *= 2
        self.initial_offset = self.offset
        self.initial_partial_prefix_bytes = self.initial_end_offset - self.initial_offset
        self.pending = b''

    def read(self):
        if not self.path.exists():
            raise ValueError('Append file disappeared: ' + str(self.path))
        current = self.path.stat()
        if self.file_identity is None:
            self.file_identity = (current.st_dev, current.st_ino)
        if (current.st_dev, current.st_ino) != self.file_identity:
            raise ValueError('Append file identity changed: ' + str(self.path))
        if self.path.stat().st_size < self.offset:
            raise ValueError('Append file truncated: ' + str(self.path))
        with self.path.open('rb') as stream:
            stream.seek(self.offset)
            raw = stream.read(1024 * 1024)
            self.offset += len(raw)
        raw = self.pending + raw
        cut = raw.rfind(b'\n') + 1
        self.pending = raw[cut:]
        return raw[:cut].decode(errors='replace').splitlines()


def select_window(rows, anchor, duration):
    """Select timestamps, never health/outcomes; bad endpoint rows stay selected."""
    first = next((i for i, row in enumerate(rows) if row['observer_unix_s'] >= anchor), None)
    if first is None:
        raise ValueError('No sample at/after prospective anchor')
    last = next((i for i in range(first, len(rows))
                 if rows[i]['observer_unix_s'] - rows[first]['observer_unix_s'] >= duration), None)
    if last is None:
        raise ValueError('Fixed first duration endpoint not reached')
    return first, last


def rates(a, z):
    elapsed = z['observer_unix_s'] - a['observer_unix_s']
    unavailable = dict(available=False, start_utc=a['utc'], end_utc=z['utc'], duration_s=elapsed,
        clock_deltas=None, samples_per_s=None, fleet_frames_per_s=None,
        nonmeasurement_fleet_frames_per_s=None, learner_frames_per_s=None,
        samples_per_nonmeasurement_fleet_frame=None)
    try:
        if elapsed <= 0 or any(type(row[key]) is not int for row in (a, z) for key in CLOCKS):
            raise ValueError('Nonpositive elapsed or malformed endpoint clock')
        deltas = {key: z[key] - a[key] for key in CLOCKS}
        fleet = deltas['frame_count'] - deltas['measurement_frames']
        if any(value < 0 for value in deltas.values()):
            raise ValueError('Backward endpoint clock')
    except (KeyError, TypeError, ValueError) as exc:
        unavailable['reason'] = str(exc)
        return unavailable
    return dict(available=True, start_utc=a['utc'], end_utc=z['utc'], duration_s=elapsed, clock_deltas=deltas,
        samples_per_s=deltas['optimized_samples'] / elapsed,
        fleet_frames_per_s=deltas['frame_count'] / elapsed,
        nonmeasurement_fleet_frames_per_s=fleet / elapsed,
        learner_frames_per_s=deltas['learner_frame_count'] / elapsed,
        samples_per_nonmeasurement_fleet_frame=deltas['optimized_samples'] / fleet if fleet > 0 else None)


def weighted(rows, key):
    """Full-window trapezoid; no deletion/interpolation across bad power rows."""
    elapsed = rows[-1]['observer_unix_s'] - rows[0]['observer_unix_s']
    integral = 0.0
    covered = 0.0
    for a, z in zip(rows, rows[1:]):
        x, y = a.get(key), z.get(key)
        dt = z['observer_unix_s'] - a['observer_unix_s']
        if (isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                and isinstance(y, (int, float)) and not isinstance(y, bool) and math.isfinite(y)
                and dt > 0):
            integral += (x + y) * .5 * dt
            covered += dt
    full = abs(covered - elapsed) < 1e-7
    return dict(available=full, covered_s=covered, requested_s=elapsed,
                integral=integral if full else None, mean=integral / elapsed if full else None)


def pipeline_deltas(a, z):
    result = {}
    for section, current in (z.get('host_pipeline') or {}).items():
        before = (a.get('host_pipeline') or {}).get(section)
        if not isinstance(current, dict) or not isinstance(before, dict):
            continue
        metrics = {}
        for name, metric in current.items():
            old = before.get(name)
            if not isinstance(metric, dict) or not isinstance(old, dict) or not {'count', 'total'} <= metric.keys():
                continue
            count = metric['count'] - old['count']
            total = metric['total'] - old['total']
            metrics[name] = dict(count_delta=count, total_delta=total,
                mean=total / count if count else None, unit='rows' if name == 'batch_size' else 'ms',
                end_cumulative_max=metric.get('max'),
                histogram_delta=[x-y for x, y in zip(metric.get('histogram', []), old.get('histogram', []))])
        if metrics:
            result[section] = metrics
    return result


def summary(rows, anchor, duration):
    first, last = select_window(rows, anchor, duration)
    w, guarded = rows[first:last+1], rows[:last+1]
    a, z = w[0], w[-1]
    result = rates(a, z)
    result.update(schema='robotron-collector4096-fixed-window-summary-v1',
        valid=result['available'] and not any(row['issues'] for row in guarded), source_row_indexes=[first, last],
        rows=len(w), guard_rows_including_settle=len(guarded), prospective_anchor_unix_s=anchor,
        issues=[dict(utc=r['utc'], issues=r['issues']) for r in guarded if r['issues']],
        notices=[dict(utc=r['utc'], notices=r['notices']) for r in guarded if r['notices']],
        blocks30s=[], last30s=None)
    for start in range(0, int(duration // 30) * 30, 30):
        x = next(r for r in w if r['observer_unix_s'] >= a['observer_unix_s'] + start)
        y = next(r for r in w if r['observer_unix_s'] >= a['observer_unix_s'] + start + 30)
        result['blocks30s'].append(rates(x, y))
    tail = next(r for r in w if r['observer_unix_s'] >= z['observer_unix_s'] - 30)
    result['last30s'] = rates(tail, z)
    energy = weighted(w, 'gpu1_power_w')
    energy.update(scope='Sampled/cached physicalGPU1-only power; excludes GPU0, CPU/MAME and whole-system energy.',
        start_utc=a['utc'], end_utc=z['utc'],
        samples_per_joule=result['clock_deltas']['optimized_samples'] / energy['integral']
        if result['available'] and energy['available'] and energy['integral'] > 0 else None)
    result['energy'] = energy
    result['gpu_util'] = weighted(w, 'gpu1_util')
    result['timing_means'] = {key: weighted(w, key) for key in
        ('train_sample_ms', 'train_transfer_ms', 'train_compute_ms', 'train_priority_ms', 'train_step_ms', 'avg_inf_ms')}
    result['conditional_pipeline_deltas'] = pipeline_deltas(a, z)
    result['API_clock_duration_s'] = z['ts'] - a['ts'] if isinstance(z.get('ts'), (int, float)) and isinstance(a.get('ts'), (int, float)) else None
    result['monotonic_duration_s'] = (z['observer_monotonic_ns'] - a['observer_monotonic_ns']) / 1e9
    result['wall_monotonic_duration_difference_s'] = result['duration_s'] - result['monotonic_duration_s']
    result['largest_poll_gap_s'] = max(y['observer_unix_s'] - x['observer_unix_s'] for x, y in zip(w, w[1:]))
    try:
        ea, ez = a['host_pipeline']['learning_exposure'], z['host_pipeline']['learning_exposure']
        result['optimizer_counter_delta'] = {key: ez['optimizer']['total'][key] - value for key, value in ea['optimizer']['total'].items()}
        result['accepted_replay_by_source_delta'] = {key: ez['replay']['accepted_by_source_total'][key] - value for key, value in ea['replay']['accepted_by_source_total'].items()}
    except (KeyError, TypeError):
        result['exposure_delta_unavailable'] = True
    result['scope'] = ['First observed timestamp>=prospective anchor; FIRST timestamp>=duration later. All settle/primary/error rows retained, no reanchor.',
        'API counters/optimizer outcomes/diagnostics are asynchronously cached, not an atomic per-update join.',
        'Rare supported AMP skips and Inf gradient diagnostics are retained, not automatically invalid. Nonfinite loss and unavailable outcomes remain faults.',
        'Conditional pipeline host durations are not GPU kernel time; end cumulative maxima are not window maxima.',
        'No winner/promotion/control decision; caller applies the existing root-adopted ABA plan after all three fixed legs.',
        'Queue depth is absent from current API/CSV. Appended CSV pressure/dropped/prefetched counts are retained with their original timestamps as secondary lagged signals.']
    return result


def validate_api(row, previous, pid, expected_clients, snapshot_errors):
    errors, notices = [], []
    try:
        hp, bank = row['host_pipeline'], row['bank_persistence']
        if any(type(row[key]) is not int or row[key] < 0 for key in CLOCKS):
            errors.append('clock_nonnegative_integer_contract')
        graphs, native = hp['inference_graphs'], hp['native_batch_update']
        for condition, name in (
            (row['client_count'] == expected_clients, 'client_count'),
            (row['training_enabled'] and not row['measurement_active'], 'training_active_measurement_inactive'),
            (row['epsilon'] == .1 and abs(row['expert_ratio'] - .1) < 1e-12 and row['lr'] == 2.5e-5 and row['memory_buffer_size'] == 6000000, 'held_controls'),
            (math.isfinite(float(row['loss'])), 'finite_loss'),
            (not row['pipeline_read_error'] and not row['bank_persistence_read_error'], 'API_metadata_reads'),
            (graphs['ready'] and graphs['capture_count'] == 128 and graphs['validation_replay_count'] == 640
             and graphs['postload_validations'] == 1 and not graphs['runtime_capture_count']
             and not graphs['fallback_count'] and not graphs['fatal_error'], 'exact_graph_route'),
            (native['enabled'] and native['available'] and native['success_count'] == native['completed_count']
             and not native['fallback_count'] and not native['error_count'], 'native_route'),
            (bank['output']['backend'] == 'stream' and bank['output']['stream_output_enabled']
             and not bank['write_failures'] and not bank['last_error']
             and not any(v['errors'] for v in bank['output']['totals'].values()), 'bank_stream_route')):
            if not condition:
                errors.append(name)
        before = previous['host_pipeline']['learning_exposure'] if previous and 'host_pipeline' in previous else None
        errors.extend(snapshot_errors(hp['learning_exposure'], before, pid))
        if not math.isfinite(float(row['grad_norm'])):
            notices.append('nonfinite_grad_diagnostic_not_automatic_fault')
        if before and hp['learning_exposure']['optimizer']['total']['amp_skipped'] > before['optimizer']['total']['amp_skipped']:
            notices.append('AMP_skip_counter_bracket_not_per_update_attribution')
        if previous and all(key in previous for key in CLOCKS):
            if any(row[key] < previous[key] for key in CLOCKS) or row['measurement_frames'] != previous['measurement_frames']:
                errors.append('clock_regression_or_measurement_clock_changed')
            old = previous['host_pipeline']
            for key in ('schema', 'generation', 'sample_every', 'latency_bucket_upper_ms', 'batch_size_bucket_upper'):
                if hp[key] != old[key]:
                    errors.append('pipeline_metadata_changed.' + key)
            for section in ('inference', 'actor_refresh', 'target_refresh', 'learner_priority'):
                if hp[section].get('errors', 0):
                    errors.append('pipeline_section_error.' + section)
                for name, metric in hp[section].items():
                    before_metric = old[section].get(name)
                    if isinstance(metric, dict) and isinstance(before_metric, dict) and 'count' in metric:
                        if (metric['count'] < before_metric['count'] or metric['total'] < before_metric['total']
                                or len(metric.get('histogram', [])) != len(before_metric.get('histogram', []))
                                or any(x < y for x, y in zip(metric.get('histogram', []), before_metric.get('histogram', [])))):
                            errors.append('pipeline_distribution_regressed.' + section + '.' + name)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        errors.append('health_snapshot_malformed:' + str(exc))
    return errors, notices


def manifest_identities(manifest, trainer_pid):
    actors = manifest['actors']
    if (type(manifest['trainer_pid']) is not int or manifest['trainer_pid'] != trainer_pid
            or type(manifest['client_count']) is not int or manifest['client_count'] != 192
            or not isinstance(actors, list) or len(actors) != 192
            or not all(type(item['pid']) is int and item['pid'] > 0
                       and type(item['start_ticks']) is int and item['start_ticks'] > 0
                       and type(item['slot']) is int for item in actors)
            or {item['slot'] for item in actors} != set(range(192))):
        raise ValueError('Require exact integer root-pinned192 actor identities')
    actor_map = {item['pid']: item['start_ticks'] for item in actors}
    supervisors = manifest['supervisor_pids']
    if (len(actor_map) != 192 or not isinstance(supervisors, list) or not supervisors
            or not all(type(pid) is int and pid > 0 for pid in supervisors)
            or len(set(supervisors)) != len(supervisors)):
        raise ValueError('Require unique actor and exact integer supervisor identities')
    return actor_map, supervisors


def actor_log_bindings(actor_rows, run_dir, slot0_log=None, readlink=os.readlink):
    """Bind every actual actor stdout; never consume a terminal/pipe descriptor.

    Slots1..191 use the launcher-defined append files as well as regular fd1/2
    targets. Slot0's terminal/pipe stream needs its root-pinned tee log.
    """
    result = {}
    for actor in actor_rows:
        pid, slot = actor['pid'], actor['slot']
        paths, descriptors = set(), {}
        for fd in (1, 2):
            target = readlink('/proc/' + str(pid) + '/fd/' + str(fd))
            if target.endswith(' (deleted)'):
                raise ValueError('Owned actor log descriptor was unlinked')
            descriptors[str(fd)] = target
            if target.startswith('/') and Path(target).is_file():
                paths.add(Path(target))
        if slot:
            fallback = GAME / 'logs' / ('mame_instance_' + str(slot) + '.log')
        elif slot0_log is not None:
            fallback = slot0_log
        else:
            candidates = list(run_dir.glob('*fleet*.log'))
            if len(candidates) != 1:
                raise ValueError('Need explicit --slot0-log when its tee log is ambiguous or absent')
            fallback = candidates[0]
        if not fallback.is_file():
            raise ValueError('Owned actor stdout log missing: ' + str(fallback))
        paths.add(fallback)
        result[str(pid)] = dict(slot=slot, descriptors=descriptors, paths=sorted(str(path) for path in paths))
    return result


def observe(args):
    if not args.run_dir.is_dir() or args.trainer_pid <= 0 or not re.fullmatch(r'[A-Za-z0-9_-]+', args.label):
        raise ValueError('Require existing run-dir, positive trainer-pid and simple unique label')
    if not math.isfinite(args.anchor_unix_s) or not math.isfinite(args.duration) or args.duration < 30:
        raise ValueError('Require finite prospective anchor/duration>=30s')
    check_exposure, check_pin = load_health_check()
    manifest_raw = args.actor_manifest.read_bytes()
    manifest = json.loads(manifest_raw)
    actors, supervisor_pids = manifest_identities(manifest, args.trainer_pid)
    trainer = process(args.trainer_pid)
    if not trainer['alive']:
        raise ValueError('Trainer not alive')
    supervisor_baseline = {pid: process(pid) for pid in supervisor_pids}
    if not all(value['alive'] and type(value['start_ticks']) is int for value in supervisor_baseline.values()):
        raise ValueError('Pinned supervisors must be alive before observation')
    supervisors = {pid: value['start_ticks'] for pid, value in supervisor_baseline.items()}
    attestation = RUN23 / 'startup-independent-process-source-observation.json'
    attestation_raw = attestation.read_bytes()
    known = json.loads(attestation_raw)
    source_hashes = {str(GAME.parent / name): value for name, value in known['source_hashes'].items()}
    source_hashes.update({str(GAME / name): value for name, value in known['private12_hashes'].items()})
    for path, expected in source_hashes.items():
        if sha(Path(path).read_bytes()) != expected:
            raise ValueError('Initial source hash differs: ' + path)
    source_stats = {path: stat_id(Path(path)) for path in source_hashes}
    control = GAME / 'models_dqn/learning_control.json'
    control_sha = sha(control.read_bytes())
    output = args.run_dir / ('collector-' + args.label + '-observations.jsonl')
    completion_path = args.run_dir / ('collector-' + args.label + '-complete.json')
    report_path = args.run_dir / ('collector-' + args.label + '-summary.json')
    if any(path.exists() for path in (output, completion_path, report_path)):
        raise FileExistsError('Refuse any existing or partial observer publication')
    console = AppendReader(args.run_dir / 'console.log')
    actor_bindings = actor_log_bindings(manifest['actors'], args.run_dir, args.slot0_log)
    actor_logs = {Path(path): AppendReader(Path(path)) for item in actor_bindings.values() for path in item['paths']}
    csv_path = args.run_dir / 'training.csv'
    with csv_path.open() as stream:
        fields = next(csv.reader(stream))
    if not set(CSV_FIELDS) <= set(fields):
        raise ValueError('CSV queue-loss/pressure field contract missing')
    csv_reader = AppendReader(csv_path)
    with csv_path.open('rb') as stream:
        size = csv_path.stat().st_size
        stream.seek(max(0, size - 262144))
        tail_raw = stream.read()
        tail = tail_raw[:tail_raw.rfind(b'\n') + 1].splitlines()
    last_csv = None
    for values in csv.reader(io.StringIO(b'\n'.join(tail[1:]).decode(errors='replace'))):
        if len(values) == len(fields):
            candidate = dict(zip(fields, values))
            last_csv = {key: candidate[key] for key in CSV_FIELDS}
    drop_baseline = int(last_csv['replay_dropped']) if last_csv else None
    counts = dict.fromkeys(ERROR_PATTERNS, 0)
    actor_counts = dict.fromkeys(ACTOR_PATTERNS, 0)
    rows, previous, last_guard = [], None, None
    started, started_mono = time.time(), time.monotonic()
    with output.open('x') as stream:
        while True:
            now = time.time()
            row = dict(utc=utc(now), observer_unix_s=now, observer_monotonic_ns=time.monotonic_ns(),
                       trainer_pid=args.trainer_pid, index=len(rows), issues=[], notices=[])
            try:
                with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=2) as response:
                    api = json.load(response)
                row.update({key: api.get(key) for key in API_FIELDS})
                problems, notices = validate_api(row, previous, args.trainer_pid, 192, check_exposure)
                row['issues'].extend(problems); row['notices'].extend(notices)
                previous = row
            except (OSError, ValueError, KeyError, TypeError) as exc:
                row['issues'].append('API_read:' + repr(exc))
            row['trainer_identity'] = process(args.trainer_pid)
            if row['trainer_identity'] != trainer:
                row['issues'].append('trainer_identity_changed')
            row['actor_mismatches'] = [pid for pid, start in actors.items() if process(pid) != dict(alive=True, start_ticks=start)]
            row['supervisor_mismatches'] = [pid for pid, start in supervisors.items() if process(pid) != dict(alive=True, start_ticks=start)]
            if row['actor_mismatches'] or row['supervisor_mismatches']:
                row['issues'].append('pinned_fleet_identity_changed')
            if last_guard is None or now - last_guard['checked_unix_s'] >= 30:
                try:
                    last_guard = dict(checked_unix_s=now, source_stat_unchanged=all(stat_id(Path(path)) == value for path, value in source_stats.items()),
                        control_sha256=sha(control.read_bytes()), manifest_unchanged=args.actor_manifest.read_bytes() == manifest_raw,
                        exposure_checker_unchanged=sha(Path(check_pin['path']).read_bytes()) == check_pin['sha256'],
                        actor_stdout_descriptors_unchanged=all(os.readlink('/proc/' + pid + '/fd/' + fd) == target
                            for pid, binding in actor_bindings.items() for fd, target in binding['descriptors'].items()))
                except OSError as exc:
                    last_guard = dict(checked_unix_s=now, error=repr(exc))
            row['source_control_guard'] = last_guard
            if (last_guard.get('error') or not last_guard.get('source_stat_unchanged') or not last_guard.get('manifest_unchanged')
                    or last_guard.get('control_sha256') != control_sha or not last_guard.get('exposure_checker_unchanged')):
                row['issues'].append('source_control_manifest_or_checker_changed')
            if not last_guard.get('actor_stdout_descriptors_unchanged'):
                row['issues'].append('actor_stdout_descriptors_changed')
            try:
                for line in console.read():
                    for pattern in counts:
                        counts[pattern] += line.count(pattern)
                actor_events = []
                for path, reader in actor_logs.items():
                    for line in reader.read():
                        for marker in actor_counts:
                            actor_counts[marker] += line.count(marker)
                        if any(marker in line for marker in actor_counts):
                            actor_events.append(dict(path=str(path), line=line))
                row['new_actor_transport_events'] = actor_events
                csv_rows = []
                for values in csv.reader(csv_reader.read()):
                    if len(values) != len(fields):
                        raise ValueError('CSV append row shape changed')
                    item = dict(zip(fields, values)); last_csv = {key: item[key] for key in CSV_FIELDS}; csv_rows.append(last_csv)
                    if drop_baseline is None:
                        drop_baseline = int(last_csv['replay_dropped'])
                    if int(last_csv['replay_dropped']) != drop_baseline:
                        row['issues'].append('CSV_replay_dropped_changed')
                row['new_CSV_queue_signals'] = csv_rows
            except (OSError, ValueError, KeyError) as exc:
                row['issues'].append('append_read:' + repr(exc))
            row['console_error_counts'] = dict(counts)
            row['actor_transport_counts'] = dict(actor_counts)
            row['queue_signals'] = dict(queue_depth_available=False, reason='Not exported by current API/CSV', latest_CSV=last_csv)
            row['append_offsets'] = dict(console=console.offset, csv=csv_reader.offset,
                actor_logs={str(path): value.offset for path, value in actor_logs.items()})
            if any(counts.values()) or any(actor_counts.values()):
                row['issues'].append('new_transport_training_compile_or_actor_timeout')
            row = safe(row)
            stream.write(json.dumps(row, allow_nan=False, separators=(',', ':')) + '\n'); stream.flush()
            rows.append(row)
            if row['issues'] and (len(rows) == 1 or row['issues'] != rows[-2]['issues']):
                print(json.dumps(dict(ALERT=row['utc'], issues=row['issues'])), flush=True)
            try:
                first, last = select_window(rows, args.anchor_unix_s, args.duration)
                break
            except ValueError:
                pass
            time.sleep(max(0, started_mono + len(rows) - time.monotonic()))
    raw = output.read_bytes()
    report = summary(rows, args.anchor_unix_s, args.duration)
    report.update(label=args.label, trainer_pid=args.trainer_pid, trainer_start_ticks=trainer['start_ticks'],
        supervisor_initial_identities=supervisor_baseline,
        actor_stdout_bindings=actor_bindings,
        actor_log_initial_offsets={str(path):dict(complete_prefix_offset=reader.initial_offset,
            initial_file_end=reader.initial_end_offset,partial_prefix_bytes=reader.initial_partial_prefix_bytes,
            file_identity=reader.file_identity) for path,reader in actor_logs.items()},
        actor_manifest=dict(path=str(args.actor_manifest), sha256=sha(manifest_raw)),
        source_attestation=dict(path=str(attestation), sha256=sha(attestation_raw)), source_hashes=source_hashes,
        initial_source_stats=source_stats, initial_control_sha256=control_sha, exposure_checker=check_pin,
        raw_complete_prefix=dict(path=str(output), bytes=len(raw), sha256=sha(raw)),
        console_initial_byte_offset=console.initial_offset, console_initial_file_end=console.initial_end_offset,
        console_initial_partial_prefix_bytes=console.initial_partial_prefix_bytes,
        CSV_initial_byte_offset=csv_reader.initial_offset, CSV_initial_file_end=csv_reader.initial_end_offset,
        CSV_initial_partial_prefix_bytes=csv_reader.initial_partial_prefix_bytes,
        queue_signals_start_end=[rows[first]['queue_signals'], rows[last]['queue_signals']])
    complete = dict(complete=True, started_utc=utc(started), finished_utc=utc(), observer_pid=os.getpid(),
        first_primary_index=first, last_primary_index=last, primary_start_unix_s=rows[first]['observer_unix_s'],
        primary_end_unix_s=rows[last]['observer_unix_s'], requested_anchor_unix_s=args.anchor_unix_s,
        requested_duration_s=args.duration, raw=report['raw_complete_prefix'])
    for path, data in ((report_path, report), (completion_path, complete)):
        with path.open('x') as stream:
            json.dump(safe(data), stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(complete_utc=complete['finished_utc'], label=args.label, valid=report['valid'],
        samples_per_s=report['samples_per_s'], samples_per_frame=report['samples_per_nonmeasurement_fleet_frame'],
        summary=str(report_path))), flush=True)
    return 0 if report['valid'] else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--trainer-pid', type=int, required=True)
    parser.add_argument('--actor-manifest', type=Path, required=True)
    parser.add_argument('--anchor-unix-s', type=float, required=True)
    parser.add_argument('--duration', type=float, default=180, choices=(180,))
    parser.add_argument('--label', required=True)
    parser.add_argument('--slot0-log', type=Path, help='Root-pinned slot0 tee log if not the sole run-dir/*fleet*.log')
    args = parser.parse_args(argv)
    return observe(args)


if __name__ == '__main__':
    raise SystemExit(main())
