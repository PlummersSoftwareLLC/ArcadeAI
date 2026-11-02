"""One explicit bounded CPU verification of the root inspector; inert by default."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
READER = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, tests, queries, outputs or runtime changes')
        return 0
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert hashlib.sha256(READER.read_bytes()).hexdigest() == 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
    spec = importlib.util.spec_from_file_location('root_monitor_verification_reader', READER)
    p = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)
    job_pin = p.pin(args.job)
    assert job_pin['sha256'] == args.job_sha256
    job = p.read_pin(job_pin)
    assert job['schema'] == 'robotron-supervised-quality32-root-monitor-verification-job-v1'
    for row in job['source_copies']:
        assert p.read_pin(row['original'], as_json=False) == p.read_pin(row['copy'], as_json=False)
    for entry in job['dependencies'].values():
        p.read_pin(entry, as_json=False)
    assert job['verifier'] == p.pin(Path(__file__).resolve())
    window = p.checked_module('root_monitor_window_'+str(time.time_ns()), job['dependencies']['window'])
    out = Path(job['output'])
    out.mkdir(mode=0o700)
    result = subprocess.run(['/usr/bin/python3.12', '-I', '-B', job['test_driver']['path']],
                            capture_output=True, timeout=90)
    stdout = window.publish(out/'actual-tests-stdout.txt', result.stdout)
    stderr = window.publish(out/'actual-tests-stderr.txt', result.stderr)
    actual_result = p.read_pin(p.pin(Path(job['test_driver']['path']).parent/'actual-test-result.json'))
    assert result.returncode == 0 and actual_result['passed'] is True and actual_result['tests_run'] == 29
    assert actual_result['failures'] == actual_result['errors'] == 0
    modules = {key: p.checked_module('root_monitor_verify_'+key+'_'+str(time.time_ns()), job['dependencies'][key])
               for key in ('monitor', 'supervision', 'joins', 'wire', 'runtime')}
    monitor, fleet, joins, wire, runtime = (modules[key] for key in ('monitor', 'supervision', 'joins', 'wire', 'runtime'))
    main = p.read_pin(job['main_binding'])
    transition = p.read_pin(job['main_transition'])
    assert transition['current_main_binding'] == job['main_binding']
    window.owner_and_files(main)
    policy, initial = fleet.make_policy(main, transition['fleet'])
    main = dict(main, supervision_policy=window.publish(out/'actual-readonly-policy.json', policy))
    joins.validate_binding(main, policy, fleet)
    state = None
    pins = []
    original_snapshots = []
    for index in range(2):
        if index:
            time.sleep(10)
            window.owner_and_files(main)
            census = fleet.collect(policy, state)
        else:
            census = initial
        raw = urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5).read(wire.MAX_WIRE_BYTES+1)
        api = wire.parse_wire(raw)
        unix, monotonic = time.time(), time.monotonic()
        if index == 0:
            main['baseline_API_value'] = api
        window.healthy(api, main['baseline_API_value'], main['experiment'], unix)
        assert api['quality_campaign']['available'] is False
        compact = joins.pack(census, fleet)
        _, state = joins.joined_census(policy, compact, dict(API=api, unix_s=unix, monotonic_s=monotonic), state, fleet)
        assert state['full_capacity'] is True and not state['used_slots']
        latest = (G/'models_dqn/robotron_dqn_latest.pt').stat()
        age = unix-latest.st_mtime_ns/1e9
        assert 0 <= age <= 360 and latest.st_size > 0
        raw_pin = window.publish(out/(str(index)+'-API-wire.raw'), raw)
        compact_pin = window.publish(out/(str(index)+'-compact-census.json'), compact)
        original_snapshots.append(window.publish(out/(str(index)+'-full-census.json'), census))
        sample = dict(monotonic_s=monotonic, unix_s=unix, main_owner=main['owner'],
            supervised_main_fleet_verified=True, main_fleet_snapshot=compact_pin,
            main_fleet_state_sha256=joins.checksum(state), held_hashes_sha256=joins.checksum(main['held_hashes']),
            autosave=dict(mtime_ns=latest.st_mtime_ns, bytes=latest.st_size, age_s=age),
            **wire.witness_fields(api, raw_pin))
        pins.append(window.publish(out/(str(index)+'-readonly-observation.json'), sample))
    replay, samples, _, _ = monitor.accepted_prefix(pins, main, policy,
        lambda entry, as_json=True: p.read_pin(entry, as_json=as_json), modules)
    monitor.validate_prefix_exposure(main, samples, runtime, window)
    assert replay == state and samples[-1]['API']['learner_frame_count'] > samples[0]['API']['learner_frame_count']
    assert samples[-1]['API']['training_steps'] > samples[0]['API']['training_steps']
    window.owner_and_files(main)
    for row in job['source_copies']:
        assert p.pin(row['original']['path']) == row['original'] and p.pin(row['copy']['path']) == row['copy']
    assert 'torch' not in sys.modules and 'numpy' not in sys.modules
    report = dict(status='ROOT_MONITOR29_TESTS_AND_TWO_ACTUAL_READONLY_CENSUSES_PASS', job=job_pin,
        actual_tests=actual_result, original_test_stdout=stdout, original_test_stderr=stderr,
        actual_readonly_policy=main['supervision_policy'], actual_readonly_observations=pins,
        actual_full_censuses=original_snapshots, actual_replayed_state_sha256=joins.checksum(replay),
        held_main_inputs_verified=195, actual_main_slots=192,
        actual_learner_frame_progress=samples[-1]['API']['learner_frame_count']-samples[0]['API']['learner_frame_count'],
        scope='Root inspector only; private services and scientific qualification were synthetic tests. Two fresh actual main/API censuses are diagnostic observations, not quality evidence.',
        actual_private_quality_started=False, actual_monitor_registered_for_quality=False,
        actual_supervised_restart_induced=False, actual_runtime_changed=False,
        quality_qualified=False, learning_speed_gain_verified=False)
    report_pin = window.publish(out/'verification.json', report)
    print(json.dumps(dict(status=report['status'], report=report_pin), allow_nan=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
