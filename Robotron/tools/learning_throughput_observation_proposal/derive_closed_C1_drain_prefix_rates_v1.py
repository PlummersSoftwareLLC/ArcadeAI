"""Derive descriptive rates from a fixed archived observation prefix; inert by default.

No live API, service, source mutation, model/replay data, benchmark or scientific
review is invoked. Exposure counters may lag the top-level metric snapshot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
Q = G / 'logs/managed-learning-20261015/run-26/quality32-reference1597-vs-production1741-original01-preparation-20261021'
REPORT = Q / 'root-live-monitor/1792639335508547483-report.json'
REPORT_SHA = '38e40e77ea00e513afeeb7bdea88d42d1ce286a096663573e09e19efddae7349'
CUTOFF = 1792638815.314243
OUTPUT = Q / 'C1-drain-fixed-prefix-learning-rates-original01.json'


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path):
    path = Path(path)
    before = identity(path.stat())
    raw = path.read_bytes()
    assert identity(path.stat()) == before
    assert before['mode'] == '0o444' and before['uid'] == os.getuid() and before['nlink'] == 1
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw), identity=before)


def read(entry):
    assert pin(entry['path']) == entry
    raw = Path(entry['path']).read_bytes()
    assert pin(entry['path']) == entry
    return json.loads(raw)


def subset(actual, expected):
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        for key, value in expected.items():
            subset(actual[key], value)
    else:
        assert actual == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--derive', action='store_true')
    if not parser.parse_args().derive:
        return
    assert not OUTPUT.exists(), 'Original derivation already consumed'
    report_pin = pin(REPORT)
    assert report_pin['sha256'] == REPORT_SHA
    report = read(report_pin)
    assert report['classification'] == 'LIVE_SUPERVISED_QUALITY32_PREFIX_VERIFIED'
    assert report['current_leg'] == 2 and report['legs'][1]['phase'] == 'draining'
    assert report['accepted_main_observations'] == 1330
    assert report['accepted_main_prefix_last']['path'] == str(Q / 'runtime-bindings/main-samples/1329.json')
    assert pin(report['accepted_main_prefix_last']['path']) == report['accepted_main_prefix_last']
    inputs, before_boundary = [], None
    for index in range(1329, -1, -1):
        entry = pin(Q / f'runtime-bindings/main-samples/{index}.json')
        sample = read(entry)
        if sample['API']['ts'] < CUTOFF:
            before_boundary = dict(index=index, sample=entry, API_ts=sample['API']['ts'])
            break
        inputs.append((index, entry, sample))
    inputs.reverse()
    assert before_boundary is not None and len(inputs) >= 2
    assert inputs[0][0] == before_boundary['index'] + 1
    owner = inputs[0][2]['main_owner']
    held = inputs[0][2]['held_hashes_sha256']
    epochs, owners, cache_ages, inflight, optimizer_available = [], [], [], [], []
    previous = None
    for index, entry, sample in inputs:
        api = sample['API']
        subset(read(sample['API_wire']), api)
        assert sample['main_owner'] == owner and sample['held_hashes_sha256'] == held
        assert sample['supervised_main_fleet_verified'] is True
        assert api['client_count'] == 192 and api['training_enabled'] is True and api['measurement_active'] is False
        assert api['lr'] == 1.25e-5 and api['pipeline_read_error'] == api['bank_persistence_read_error'] == ''
        assert api['bank_persistence']['write_failures'] == 0
        pipeline = api['host_pipeline']
        assert pipeline['available'] is True and pipeline['generation'] == 0
        assert all(pipeline[k]['errors'] == 0 for k in ('inference', 'actor_refresh', 'target_refresh', 'learner_priority'))
        exposure = pipeline['learning_exposure']
        replay, optimizer = exposure['replay'], exposure['optimizer']
        assert replay['enabled'] is True and replay['available'] is True and optimizer['enabled'] is True
        assert replay['process_id'] == optimizer['process_id'] == owner['pid']
        assert optimizer['total']['unavailable'] == 0
        pending = optimizer['total']['attempts_started'] - optimizer['total']['outcomes_recorded']
        assert 0 <= pending <= 1
        epochs.append([replay['instance_monotonic_ns'], replay['epoch'], optimizer['instance_monotonic_ns'], optimizer['epoch']])
        cache_ages.append(api['pipeline_snapshot_age_s'])
        inflight.append(pending)
        optimizer_available.append(optimizer['available'])
        assert 0 <= cache_ages[-1] <= 5
        if previous is not None:
            assert sample['monotonic_s'] > previous['monotonic_s'] and api['ts'] > previous['API']['ts']
            assert all(api[k] >= previous['API'][k] for k in ('frame_count', 'learner_frame_count', 'training_steps', 'optimized_samples'))
            prior = previous['API']['host_pipeline']['learning_exposure']
            assert replay['accepted_total'] >= prior['replay']['accepted_total']
            assert replay['accepted_learner_total'] >= prior['replay']['accepted_learner_total']
            assert all(optimizer['total'][k] >= prior['optimizer']['total'][k] for k in ('applied', 'amp_skipped', 'unavailable'))
        previous = sample
    assert all(value == epochs[0] for value in epochs)
    first, last = inputs[0][2], inputs[-1][2]
    a, b = first['API'], last['API']
    elapsed = b['ts'] - a['ts']
    monotonic_elapsed = last['monotonic_s'] - first['monotonic_s']
    assert elapsed > 0 and abs(elapsed - monotonic_elapsed) < 2
    metric_deltas = {k: b[k] - a[k] for k in ('frame_count', 'learner_frame_count', 'training_steps', 'optimized_samples')}
    ea, eb = a['host_pipeline']['learning_exposure'], b['host_pipeline']['learning_exposure']
    replay_deltas = {k: eb['replay'][k] - ea['replay'][k] for k in ('accepted_total', 'accepted_learner_total')}
    replay_sources = {k: eb['replay']['accepted_by_source_total'][k] - v
                      for k, v in ea['replay']['accepted_by_source_total'].items()}
    assert sum(replay_sources.values()) == replay_deltas['accepted_total']
    assert replay_sources['dqn'] + replay_sources['epsilon'] == replay_deltas['accepted_learner_total']
    optimizer_deltas = {k: eb['optimizer']['total'][k] - ea['optimizer']['total'][k]
                        for k in ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable')}
    assert optimizer_deltas['outcomes_recorded'] == optimizer_deltas['applied'] + optimizer_deltas['amp_skipped'] + optimizer_deltas['unavailable']
    result = dict(schema='robotron-fixed-archived-main-throughput-observation-v1',
        status='DESCRIPTIVE_COUNTER_RATES_NOT_CONTROLLED_SPEED_OR_QUALITY_COMPARISON',
        observed_unix_s=time.time(), source=pin(__file__), bound_original_monitor=report_pin,
        fixed_start_boundary=CUTOFF, selection='Every archived accepted sample after the fixed C1 admission cutoff through the named original report prefix; first and last samples are not selected by performance.',
        immediately_pre_boundary_sample=before_boundary,
        ordered_samples=[dict(index=i, sample=p, original_API_wire=s['API_wire']) for i, p, s in inputs],
        sample_count=len(inputs), first_API_ts=a['ts'], last_API_ts=b['ts'],
        API_interval_s=elapsed, monotonic_interval_s=monotonic_elapsed,
        main_owner=owner, held_hashes_sha256=held, learning_exposure_epoch=epochs[0],
        metric_deltas=metric_deltas, replay_deltas=replay_deltas,
        accepted_replay_source_deltas=replay_sources, optimizer_outcome_deltas=optimizer_deltas,
        metric_rates_per_s={k: v / elapsed for k, v in metric_deltas.items()},
        replay_rates_per_s={k: v / elapsed for k, v in replay_deltas.items()},
        accepted_replay_source_rates_per_s={k: v / elapsed for k, v in replay_sources.items()},
        optimizer_outcome_rates_per_s={k: v / elapsed for k, v in optimizer_deltas.items()},
        logical_draws_per_accepted_learner_insert=metric_deltas['optimized_samples'] / replay_deltas['accepted_learner_total'],
        maximum_pipeline_cache_age_s=max(cache_ages),
        endpoint_pipeline_cache_age_s=[cache_ages[0], cache_ages[-1]],
        optimizer_snapshot_inflight_range=[min(inflight), max(inflight)],
        optimizer_snapshots_available_count=sum(optimizer_available),
        limitations=['Descriptive fixed archived interval only; no controlled before/after comparison or improvement claim.',
                    'Exposure counters are cached and can lag top-level clocks; approximate rates use API timestamps and report cache ages, with no interpolation.',
                    'Applied optimizer outcomes mean calls admitted by the optimizer instrumentation, not proof every parameter changed or Adam tensor advanced.',
                    'Logical sample draws, accepted learner inserts, total ring inserts and raw frames have distinct denominators.',
                    'No replay slot ownership/incidence, bank validity, GPU kernel/energy service time, learning speed benefit or frozen-policy quality is measured.'],
        live_runtime_observed=False, runtime_changed=False, new_benchmark_or_probe=False,
        old_tests_or_reviewers_rerun=False, learning_speed_gain_verified=False,
        quality_qualified=False, promotion=False)
    raw = (json.dumps(result, indent=2) + '\n').encode()
    with OUTPUT.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(dict(status=result['status'], receipt=pin(OUTPUT),
        interval_s=elapsed, metric_rates_per_s=result['metric_rates_per_s'],
        replay_rates_per_s=result['replay_rates_per_s'], optimizer_outcome_rates_per_s=result['optimizer_outcome_rates_per_s'])))


if __name__ == '__main__':
    main()
