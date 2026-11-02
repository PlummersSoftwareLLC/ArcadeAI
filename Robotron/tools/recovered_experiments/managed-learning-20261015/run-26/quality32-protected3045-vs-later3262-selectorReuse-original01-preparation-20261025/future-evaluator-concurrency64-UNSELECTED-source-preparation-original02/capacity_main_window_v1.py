"""Read original main rates over the private active window, using each own clock.

No runtime actions. Original full health replay, source/resource/owner closure
and CE4096 held-recipe verification remain the independent caller's duties.
"""
import base64
from fractions import Fraction
import hashlib
import json
import math


def require(value, message):
    if not value:
        raise ValueError(message)


def number(value):
    if type(value) is Fraction:
        return value
    require(type(value) in (int, float) and math.isfinite(value), 'Finite original clock required')
    return Fraction(str(value))


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'Original nonnegative integer counter required')
    return value


def ratio(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def unpack_api(pin, record):
    transport = record['transport']
    envelope = transport['raw_API']
    raw = base64.b64decode(envelope['base64'], validate=True)
    require(len(raw) == envelope['bytes'] and hashlib.sha256(raw).hexdigest() == envelope['sha256'],
            'Original raw API length or digest differs')
    api = json.loads(raw)
    return dict(sample=pin, index=transport['index'],
                observed=transport['observed_unix_s'], begin=transport['API_begin_unix_s'],
                end=transport['API_end_unix_s'], api=api)


def rates_from_records(records, *, start_unix, end_unix, main_pid):
    """All input rows must come from one original, already replayed health stream."""
    start, end = number(start_unix), number(end_unix)
    require(end - start >= 600, 'Original private active window must span at least600s')
    integer(main_pid, 1)
    selected = []
    identity = None
    previous = None
    previous_index = None
    source_count = 0
    for record in records:
        source_count += 1
        index = integer(record['index'])
        require(index == source_count - 1 and (previous_index is None or index == previous_index + 1), 'Original raw main stream order/gap differs')
        previous_index = index
        api = record['api']
        begin, finish, observed = map(number, (record['begin'], record['end'], record['observed']))
        require(begin <= finish <= observed, 'Invalid raw API observation brackets')
        timestamp = number(api['ts'])
        require(0 <= observed - timestamp <= 2, 'Original metric API snapshot is stale or from the future')
        # Use a conservative two-second inner margin for the independently
        # cached pipeline snapshot, rather than crediting work outside the load.
        if timestamp < start + 2 or timestamp > end:
            continue
        require(api['client_count'] == 192 and api['training_enabled'] is True,
                'Original main192 training coverage required')
        require(not api['pipeline_read_error'], 'Original pipeline read failed')
        age = number(api['pipeline_snapshot_age_s'])
        require(0 <= age <= 2, 'Pipeline snapshot age exceeds2s')
        pipeline = api['host_pipeline']
        require(pipeline['schema'] == 'robotron-host-pipeline-v1' and pipeline['available'] is True,
                'Original cumulative pipeline snapshot unavailable')
        generation = integer(pipeline['generation'])
        pipeline_clock = number(pipeline['elapsed_s'])
        require(pipeline_clock > 0, 'Positive original pipeline clock required')
        exposure = pipeline['learning_exposure']['optimizer']
        require(exposure['schema'] == 'robotron-optimizer-exposure-v1'
                and exposure['available'] is exposure['enabled'] is True,
                'Actual optimizer-admission counter unavailable')
        token = (integer(exposure['process_id'], 1), integer(exposure['instance_monotonic_ns'], 1),
                 integer(exposure['epoch']), generation)
        require(token[0] == main_pid, 'Main optimizer process differs from original binding')
        identity = identity or token
        require(identity == token, 'Main process/optimizer instance/epoch/pipeline generation reset')
        counters = {key:integer(exposure['total'][key]) for key in
                    ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable')}
        require(counters['outcomes_recorded'] == counters['applied'] + counters['amp_skipped'] + counters['unavailable']
                and counters['attempts_started'] >= counters['outcomes_recorded'],
                'Original optimizer outcomes do not reconcile')
        current = dict(sample=record['sample'], index=index, api_clock=timestamp,
                       pipeline_clock=pipeline_clock, fleet_frames=integer(api['frame_count']),
                       optimizer=counters, snapshot_age_s=age)
        if previous:
            require(timestamp >= previous['api_clock'] and pipeline_clock >= previous['pipeline_clock'],
                    'Original API/pipeline clock regressed')
            require(current['fleet_frames'] >= previous['fleet_frames'], 'Main fleet counter reset')
            require(all(counters[k] >= previous['optimizer'][k] for k in counters), 'Optimizer counter reset')
            require(counters['unavailable'] == previous['optimizer']['unavailable'],
                    'Unavailable optimizer outcomes inside active window')
            if timestamp == previous['api_clock']:
                require(current['fleet_frames'] == previous['fleet_frames'], 'Same API clock has different fleet counts')
            if pipeline_clock == previous['pipeline_clock']:
                require(counters == previous['optimizer'], 'Same pipeline snapshot clock has different outcomes')
        selected.append(current)
        previous = current
    require(len(selected) >= 100, 'Insufficient original active-window main observations')
    first, last = selected[0], selected[-1]
    require(2 <= first['api_clock'] - start <= 4 and 0 <= end - last['api_clock'] <= 2,
            'Original main rate endpoints do not cover the private active window')
    api_elapsed = last['api_clock'] - first['api_clock']
    pipeline_elapsed = last['pipeline_clock'] - first['pipeline_clock']
    require(api_elapsed >= 590 and pipeline_elapsed >= 590
            and abs(api_elapsed - pipeline_elapsed) <= 3,
            'Original main API/pipeline duration or clock consistency differs')
    frames = last['fleet_frames'] - first['fleet_frames']
    applied = last['optimizer']['applied'] - first['optimizer']['applied']
    require(frames > 0 and applied > 0, 'Both original main fleet and optimizer admission must advance')
    rows = applied * 4096
    def endpoint(row):
        return dict(sample=row['sample'], index=row['index'], api_clock=ratio(row['api_clock']),
                    pipeline_clock=ratio(row['pipeline_clock']), fleet_frames=row['fleet_frames'],
                    optimizer=row['optimizer'], pipeline_snapshot_age_s=float(row['snapshot_age_s']))
    return dict(schema='robotron-capacity64-main-own-clock-rates-v1',
                bound_main_process_id=main_pid, stable_optimizer_instance_epoch_pipeline_generation=list(identity),
                original_stream_samples=source_count, selected_inner_window_samples=len(selected),
                endpoints=[endpoint(first), endpoint(last)],
                fleet_frames=frames, fleet_elapsed_s=ratio(api_elapsed), fleet_frame_rate=ratio(Fraction(frames) / api_elapsed),
                optimizer_applied_admissions=applied, admitted_rows=rows,
                optimizer_pipeline_elapsed_s=ratio(pipeline_elapsed),
                admitted_optimizer_row_rate=ratio(Fraction(rows) / pipeline_elapsed), held_batch_size=4096,
                own_clocks_kept_separate=True, stable_epochs_and_monotonic_counters_verified=True,
                unavailable_outcomes_within_window=0, quality_qualified=False,
                useful_training_throughput_gain_verified=False, learning_speed_gain_verified=False,
                scope='Applied means optimizer call admitted; it does not prove every parameter/Adam state advanced. Pipeline elapsed is its cumulative snapshot clock, captured before the exposure read; sampling/cache uncertainty remains bounded by the original API age and endpoint checks.')


def analyse(job, result, read):
    closed = read(result['main_health_report'])
    require(closed['held197_final_verified'] is True and closed['no_production_runtime_change'] is True,
            'Original closed main197 health proof required')
    start_m = number(closed['guard_started_monotonic_s'])
    end_m = number(closed['guard_ended_monotonic_s'])
    start_u = number(closed['guard_started_unix_s'])
    end_u = number(closed['guard_ended_unix_s'])
    require(0 < start_m < end_m and 0 < start_u < end_u, 'Original closed clock anchors required')
    offset_start, offset_end = start_u - start_m, end_u - end_m
    require(abs(offset_end - offset_start) <= Fraction(1, 20), 'Wall/monotonic clock mapping drift exceeds50ms')
    private_start = Fraction(result['active_start']['midpoint_monotonic_ns'], 10**9)
    private_end = Fraction(result['active_end']['midpoint_monotonic_ns'], 10**9)
    require(start_m <= private_start < private_end <= end_m, 'Original main guard does not cover private load')
    offset = (offset_start + offset_end) / 2
    binding = read(job['main_binding'])
    records = (unpack_api(pin, read(pin)) for pin in closed['samples'])
    r = rates_from_records(records, start_unix=private_start + offset,
                           end_unix=private_end + offset, main_pid=binding['owner']['pid'])
    r.update(original_closed_main_report=result['main_health_report'], original_main_binding=job['main_binding'],
             original_main_clock_mapping_offsets=[ratio(offset_start), ratio(offset_end)],
             full_original_raw_health_replay_and_held_CE4096_recipe_required_from_caller=True)
    return r
