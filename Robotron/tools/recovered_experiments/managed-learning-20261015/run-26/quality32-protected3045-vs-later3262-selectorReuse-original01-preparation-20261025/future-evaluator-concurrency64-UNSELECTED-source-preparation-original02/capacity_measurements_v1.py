"""Independent arithmetic over original active-window receipts; no runtime imports."""
import collections
import math
from pathlib import Path


def median_twice(values):
    values = sorted(values)
    if not values:
        raise ValueError('Empty original timing stratum')
    middle = len(values) // 2
    return 2 * values[middle] if len(values) % 2 else values[middle - 1] + values[middle]


def analyse_private(job, job_pin, result, read, h):
    actor_count = job["capacity_shape"]["actor_count"]
    assert type(actor_count) is int and actor_count in (32,64)
    assert job["capacity_shape"] == dict(actor_count=actor_count, games_per_slot=64//actor_count, expected_games=64, identity_count=2*actor_count, inference_max_batch_size=16)
    root = Path(job['output'])
    rate = read(result['active_frame_rate'])
    start, end = result['active_start'], result['active_end']
    assert start == rate['start'] == read(h.pin(root / 'original-active-start.json'))
    assert end == rate['end']
    for point in (start, end):
        assert point['schema'] == 'robotron-selector-active-endpoint-v1'
        for key in ('read_started_monotonic_ns', 'read_ended_monotonic_ns', 'midpoint_monotonic_ns'):
            assert type(point[key]) is int and point[key] > 0
        assert point['read_started_monotonic_ns'] <= point['midpoint_monotonic_ns'] <= point['read_ended_monotonic_ns']
        assert point['midpoint_monotonic_ns'] == (point['read_started_monotonic_ns'] + point['read_ended_monotonic_ns']) // 2
        assert set(point['slots']) == {str(slot) for slot in range(4096, 4096+actor_count)}
    elapsed_ns = end['midpoint_monotonic_ns'] - start['midpoint_monotonic_ns']
    elapsed_s = elapsed_ns / 1e9
    assert elapsed_ns >= 600000000000
    assert elapsed_s == rate['midpoint_elapsed_s']
    lower = (end['read_started_monotonic_ns'] - start['read_ended_monotonic_ns']) / 1e9
    upper = (end['read_ended_monotonic_ns'] - start['read_started_monotonic_ns']) / 1e9
    assert 0 < lower <= elapsed_s <= upper and rate['elapsed_bracket_s'] == [lower, upper]
    frames = 0
    for slot, first in start['slots'].items():
        last, final = end['slots'][slot], result['original_slots'][slot]
        for point in (first, last):
            assert all(type(point[k]) is int for k in ('pid', 'birth', 'accepted', 'rejected', 'sequence'))
            assert point['rejected'] == 0 and 1200 <= point['accepted'] <= point['sequence']
        assert (first['pid'], first['birth']) == (last['pid'], last['birth']) == (final['pid'], final['birth'])
        assert final['frames'] >= last['sequence']
        delta = last['accepted'] - first['accepted']
        assert delta > 0
        frames += delta
        actual = rate['slots'][slot]
        assert actual['accepted_frames'] == delta
        assert actual['midpoint_FPS'] == delta / elapsed_s
        assert actual['bracket_low_FPS'] == delta / upper and actual['bracket_high_FPS'] == delta / lower
    assert rate['accepted_frames'] == frames
    assert rate['aggregate_midpoint_FPS'] == frames / elapsed_s
    assert rate['aggregate_bracket_low_FPS'] == frames / upper
    assert rate['aggregate_bracket_high_FPS'] == frames / lower
    assert rate['useful_training_throughput_claim'] is rate['learning_speed_claim'] is False
    paths = sorted((root / 'status-samples').glob('*.json'))
    assert 2 <= len(paths) <= 200
    assert [path.name for path in paths] == [f'{index:04d}.json' for index in range(len(paths))]
    statuses = []
    previous = start['slots']
    previous_unix = None
    for path in paths:
        pin = h.pin(path)
        row = read(pin)
        assert row['original_job'] == job_pin and row['errors'] == []
        if row['active_start'] is None:
            continue
        assert row['active_start'] == start
        assert type(row['observed_unix_s']) in (int, float) and math.isfinite(row['observed_unix_s'])
        if previous_unix is not None:
            assert 0 < row['observed_unix_s'] - previous_unix <= 6
        previous_unix = row['observed_unix_s']
        assert set(row['slots']) == set(start['slots'])
        current = {}
        for slot, sample in row['slots'].items():
            assert sample['actual_exit'] is sample['error'] is None
            assert sample['prefix_verified'] is True and sample['stop_sent'] is False
            assert (sample['pid'], sample['birth']) == (start['slots'][slot]['pid'], start['slots'][slot]['birth'])
            ledger = sample['ledger']
            assert type(ledger['accepted']) is int and ledger['rejected'] == 0
            # The first status may immediately follow the start snapshot.
            assert ledger['accepted'] >= previous[slot]['accepted']
            if statuses:
                assert ledger['accepted'] > previous[slot]['accepted']
            assert ledger['accepted'] <= end['slots'][slot]['accepted']
            current[slot] = dict(accepted=ledger['accepted'])
        previous = current
        statuses.append(pin)
    assert len(statuses) >= 100
    timing = read(result['selector_call_timing'])
    assert timing['schema'] == 'robotron-selector-native-call-timing-v1'
    assert timing['selector_source_sha256'] == job['quota64_source_pins']['view']['sha256']
    assert timing['clock'] == 'monotonic_ns/thread_time_ns'
    assert timing['columns'] == ['start_monotonic_ns', 'end_monotonic_ns', 'thread_CPU_ns', 'thread_id',
                                 'known_starts', 'completed', 'pending', 'exceptional']
    assert timing['all_calls_retained'] is timing['original_method_restored'] is True
    assert timing['overflowed'] is False and timing['active_calls_at_close'] == 0 and timing['capacity'] == 131072
    assert 0 < len(timing['rows']) <= timing['capacity']
    last_by_thread = {}
    costs = []
    shapes = collections.Counter()
    for row in timing['rows']:
        assert len(row) == 8 and all(type(value) is int for value in row[:-1]) and type(row[-1]) is bool
        before, after, cpu, thread, known, complete, pending, exceptional = row
        assert 0 < before <= after and cpu >= 0 and thread > 0
        assert before >= last_by_thread.get(thread, 0)
        last_by_thread[thread] = after
        if before < start['midpoint_monotonic_ns'] or after > end['midpoint_monotonic_ns']:
            continue
        assert exceptional is False and known >= complete + pending >= 0
        shapes[(known, complete, pending)] += 1
        if (known, complete, pending) == (actor_count, 0, actor_count):
            costs.append(cpu)
    # CPU costs are descriptive across different actor-count shapes.
    return dict(schema='robotron-evaluator-count-active600-independent-measurements-v1', actor_count=actor_count,
        original_active_frame_report=result['active_frame_rate'], original_timing_report=result['selector_call_timing'],
        active_duration_ns=elapsed_ns, active_duration_s=elapsed_s, accepted_frames=frames,
        aggregate_accepted_frame_FPS=frames / elapsed_s, elapsed_bracket_s=[lower, upper],
        all_declared_original_slot_identities_and_counter_advances_verified=True,
        all_active_native_statuses=statuses, all_active_statuses_advance_every_slot=True,
        original_call_count=len(timing['rows']), active_shape_counts=[dict(known=k[0], complete=k[1], pending=k[2], calls=v)
            for k, v in sorted(shapes.items())],
        descriptive_initial_shape=dict(known_starts=actor_count, completed=0, pending=actor_count, count=len(costs),
                           thread_CPU_ns=costs, median_thread_CPU_ns_twice=median_twice(costs) if costs else None),
        exact_rates_and_descriptive_costs_recomputed_without_runtime_measurement_helper=True,
        no_comparison_decision_until_all4_originals_closed=True, quality_qualified=False,
        learning_speed_gain_verified=False, useful_training_throughput_gain_verified=False)

MAIN_RATE_READER = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025/future-evaluator-concurrency64-UNSELECTED-source-preparation-original02/capacity_main_window_v1.py', 'sha256': 'c9bf15a044d3d9c417bb1d6f2bae1bb7e55c4a632dd0e2c7851bb8d1d11d28e6', 'bytes': 9922, 'identity': {'device': 2304, 'inode': 81298653, 'bytes': 9922, 'mtime_ns': 1793031459340167136, 'ctime_ns': 1793031459379167321, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}


def analyse(job, job_pin, result, read, h):
    private = analyse_private(job, job_pin, result, read, h)
    pin = job['main_rate_reader']
    assert pin == MAIN_RATE_READER
    import importlib.util
    import sys
    path = h.checked(pin)
    spec = importlib.util.spec_from_file_location('_capacity_main_rates', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    private['main_rates'] = module.analyse(job, result, read)
    private['main_rate_reader'] = pin
    private['selector_CPU_cross_shape_comparison_used'] = False
    return private
