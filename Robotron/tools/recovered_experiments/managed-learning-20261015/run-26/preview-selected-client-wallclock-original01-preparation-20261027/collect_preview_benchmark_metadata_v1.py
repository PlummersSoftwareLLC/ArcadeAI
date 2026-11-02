"""Default inert; explicit future fixed-window GET-only metadata collection.

Never registers a viewer, fetches an image, changes preview settings, loads a
model, or controls a process. ROOT must arrange viewer demand/phase beforehand.
Output deliberately excludes policy/game scores and full API bodies.
"""
import argparse
import json
import math
import os
from pathlib import Path
import time
import urllib.request

URL = 'http://127.0.0.1:8771/api/now'  # No cid: this collector is not a viewer.
COUNTERS = ('frame_count', 'learner_frame_count', 'training_steps', 'optimized_samples')
EXPOSURE = ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable')


def require(value, message):
    if not value:
        raise ValueError(message)


def integer(value, label):
    require(type(value) is int and value >= 0, 'Missing/noninteger counter: ' + label)
    return value


def project(raw, begin_ns, end_ns, end_unix_s, *, slot):
    """Keep scalar measurements, lineage, and selected-slot identity only."""
    require('snapshot_error' not in raw, 'Dashboard snapshot failed')
    pipeline = raw.get('host_pipeline') or {}
    optimizer = (pipeline.get('learning_exposure') or {}).get('optimizer') or {}
    rows = [row for row in raw.get('client_rows', []) if row.get('client_slot') == slot]
    require(len(rows) == 1, 'Expected exactly one current selected-slot row')
    row = rows[0]
    seconds = row.get('session_seconds')
    require(type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0,
            'Selected-slot session seconds unavailable')
    frames = round(seconds * 60)
    require(abs(frames - seconds * 60) <= 1e-4, 'Derived selected-slot frame counter is ambiguous')
    return dict(
        schema='robotron-preview-benchmark-scalar-sample-v1',
        request_begin_monotonic_ns=begin_ns, response_end_monotonic_ns=end_ns,
        request_elapsed_s=(end_ns - begin_ns) / 1e9,
        server_snapshot_unix_s=raw['ts'],
        server_snapshot_age_s=end_unix_s - raw['ts'],
        counters={key: integer(raw.get(key), key) for key in COUNTERS},
        client_count=raw.get('client_count'), web_client_count=raw.get('web_client_count'),
        preview_enabled=raw.get('preview_capture_enabled'),
        selected_client_id=raw.get('preview_selected_client_id'),
        cache_client_id=raw.get('game_preview_client_id'),
        cache_sequence=integer(raw.get('game_preview_seq'), 'game_preview_seq'),
        retained_instantaneous_preview_fps=raw.get('game_preview_fps'),
        selected_slot=dict(slot=slot, client_id=row.get('client_id'), eval=row.get('eval'),
                           derived_accepted_frames_from_session_seconds=frames,
                           session_seconds=seconds, selected_preview=row.get('selected_preview')),
        pipeline=dict(schema=pipeline.get('schema'), generation=pipeline.get('generation'),
                      elapsed_s=pipeline.get('elapsed_s'), age_s=raw.get('pipeline_snapshot_age_s'),
                      read_error=raw.get('pipeline_read_error')),
        optimizer=dict(enabled=optimizer.get('enabled'), available=optimizer.get('available'),
                       process_id=optimizer.get('process_id'),
                       instance_monotonic_ns=optimizer.get('instance_monotonic_ns'),
                       epoch=optimizer.get('epoch'),
                       unclassified_started_total=optimizer.get('unclassified_started_total'),
                       total={key: (optimizer.get('total') or {}).get(key) for key in EXPOSURE}),
    )


def summarize(samples, *, phase, client_id, slot, expected_eval, trainer_pid):
    require(len(samples) >= 2, 'At least two endpoints required')
    first, last = samples[0], samples[-1]
    issues = []
    for sample in samples:
        if not (-0.1 <= sample['server_snapshot_age_s'] <= 0.5):
            issues.append('stale_or_clock_inconsistent_dashboard_snapshot')
        if sample['client_count'] != 192:
            issues.append('fleet_not192')
        row = sample['selected_slot']
        if (row['client_id'], row['slot'], row['eval'], row['selected_preview']) != (client_id, slot, expected_eval, True):
            issues.append('selected_slot_identity_or_role_drift')
        if sample['selected_client_id'] != client_id:
            issues.append('selection_changed')
        if sample['web_client_count'] is None or sample['web_client_count'] < 1:
            issues.append('no_registered_viewer_demand')
        if sample['preview_enabled'] is not (phase == 'ON'):
            issues.append('preview_phase_not_observed')
        for key in ('generation',):
            if sample['pipeline'][key] != first['pipeline'][key]:
                issues.append('pipeline_lineage_changed')
        op = sample['optimizer']
        for key in ('process_id', 'instance_monotonic_ns', 'epoch'):
            if op[key] is None or op[key] != first['optimizer'][key]:
                issues.append('optimizer_lineage_changed_or_unavailable')
        if op['process_id'] != trainer_pid or op['enabled'] is not True:
            issues.append('optimizer_owner_or_exposure_unavailable')
        if sample['pipeline']['read_error'] or sample['pipeline']['age_s'] is None or sample['pipeline']['age_s'] > 1.5:
            issues.append('pipeline_snapshot_not_fresh')
    duration = last['server_snapshot_unix_s'] - first['server_snapshot_unix_s']
    require(duration > 0, 'Nonadvancing producer timestamps')
    rates = {}
    for key in COUNTERS:
        values = [sample['counters'][key] for sample in samples]
        if any(after < before for before, after in zip(values, values[1:])):
            issues.append('counter_regression:' + key)
        rates[key] = dict(delta=values[-1] - values[0], producer_interval_s=duration,
                          per_second=(values[-1] - values[0]) / duration)
    seq = [sample['cache_sequence'] for sample in samples]
    if any(after < before for before, after in zip(seq, seq[1:])):
        issues.append('cache_sequence_reset')
    delta = seq[-1] - seq[0]
    if phase == 'ON' and any(sample['cache_client_id'] != client_id for sample in samples):
        issues.append('cached_frame_client_mismatch')
    if phase == 'OFF' and delta != 0:
        issues.append('new_cached_image_during_settled_OFF_window')
    actor = [sample['selected_slot']['derived_accepted_frames_from_session_seconds'] for sample in samples]
    if any(after < before for before, after in zip(actor, actor[1:])):
        issues.append('selected_slot_counter_regression')
    optimizer_rates = None
    a, z = first['optimizer']['total'], last['optimizer']['total']
    elapsed_a, elapsed_z = first['pipeline']['elapsed_s'], last['pipeline']['elapsed_s']
    if (all(type(a[key]) is int and type(z[key]) is int and z[key] >= a[key] for key in EXPOSURE)
            and type(elapsed_a) in (int, float) and type(elapsed_z) in (int, float) and elapsed_z > elapsed_a):
        optimizer_rates = dict(producer_interval_s=elapsed_z - elapsed_a,
                               deltas={key: z[key] - a[key] for key in EXPOSURE},
                               admitted_calls_per_second=(z['applied'] - a['applied']) / (elapsed_z - elapsed_a))
        if z['unavailable'] != a['unavailable']:
            issues.append('unclassified_optimizer_outcome')
    else:
        issues.append('optimizer_counter_delta_unavailable_or_regressed')
    return dict(schema='robotron-preview-benchmark-window-descriptive-summary-v1',
                phase=phase, observations=len(samples), producer_interval_s=duration,
                valid_metadata=not issues, issues=sorted(set(issues)), rates=rates,
                server_decoded_cache_frames=dict(delta=delta, per_second=delta / duration),
                selected_slot_derived_accepted_frames=dict(delta=actor[-1] - actor[0],
                                                          per_second=(actor[-1] - actor[0]) / duration),
                optimizer=optimizer_rates,
                browser_decoded_or_displayed_frames_observed=False,
                nonselected_actor_capture_or_send_counts_observed=False,
                retained_FPS_used_as_measurement=False, throughput_acceptance_or_deployment_decided=False,
                timing_scope='Each rate uses its corresponding cached producer interval; exposure is independently cached at1Hz',
                optimizer_scope='Applied means optimizer call admitted, not proof each parameter moved')


def put(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--phase', choices=('ON', 'OFF'))
    parser.add_argument('--duration-s', type=int, choices=(60, 120, 180), default=60)
    parser.add_argument('--client-id', type=int)
    parser.add_argument('--slot', type=int, default=163)
    parser.add_argument('--expected-role', choices=('eval', 'noneval'), default='eval')
    parser.add_argument('--trainer-pid', type=int)
    parser.add_argument('--output-directory')
    args = parser.parse_args(argv)
    if not args.collect:
        print('PLAN_ONLY: no network, viewer registration, outputs, or controls')
        return 0
    require(args.phase is not None and args.client_id is not None and args.trainer_pid is not None
            and args.output_directory, 'Explicit phase/identity/fresh output required')
    directory = Path(args.output_directory)
    require(directory.is_absolute() and directory.resolve() == directory and not directory.exists()
            and directory.parent.is_dir(), 'Fresh isolated output directory required')
    directory.mkdir(mode=0o700)
    samples = []
    start = time.monotonic_ns()
    # Exactly61 scheduled observations for60s. Slow requests invalidate the
    # window instead of creating a catch-up request burst or extending it.
    error = None
    try:
        for index in range(args.duration_s + 1):
            target = start + index * 1_000_000_000
            remaining = (target - time.monotonic_ns()) / 1e9
            if remaining > 0:
                time.sleep(remaining)
            begin = time.monotonic_ns()
            require(begin - target <= 250_000_000, 'Fixed sample schedule missed')
            with urllib.request.urlopen(URL, timeout=1) as response:
                body = response.read(512 * 1024 + 1)
            require(len(body) <= 512 * 1024, 'Bounded API response exceeded')
            end = time.monotonic_ns()
            require(end - begin <= 500_000_000, 'Slow API read invalidates this fixed window')
            samples.append(project(json.loads(body), begin, end, time.time(), slot=args.slot))
    except Exception as caught:
        error = type(caught).__name__ + ': ' + str(caught)
    put(directory / 'scalar-samples.json', samples)
    if error is not None:
        put(directory / 'descriptive-summary.json', dict(status='INCOMPLETE_INVALID_WINDOW',
            error=error, samples_retained=len(samples), retries=0, acceptance_decided=False))
        return 1
    summary = summarize(samples, phase=args.phase, client_id=args.client_id, slot=args.slot,
                        expected_eval=args.expected_role == 'eval', trainer_pid=args.trainer_pid)
    put(directory / 'descriptive-summary.json', summary)
    print(json.dumps(dict(status='RECORDED_METADATA_ONLY', valid_metadata=summary['valid_metadata'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
