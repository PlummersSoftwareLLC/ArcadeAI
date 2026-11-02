"""Explicit bounded CPU proposal tests plus read-only live census; inert by default."""
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
READER_SHA = 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'


def module(path, sha, name):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    return loaded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, tests, queries, outputs or runtime changes')
        return 0
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    reader = module(READER, READER_SHA, 'reader')
    job_pin = reader.pin(Path(args.job))
    assert job_pin['sha256'] == args.job_sha256
    job = reader.read_pin(job_pin)
    assert job['schema'] == 'robotron-supervised-main-fleet-proposal-verification-job-v1'
    for pin in job['sources'].values():
        reader.read_pin(pin, as_json=False)
    assert job['sources']['verifier'] == reader.pin(Path(__file__).resolve())
    loaded = {name: reader.checked_module('proposal_' + name + '_' + str(time.time_ns()), job['sources'][name])
              for name in ('supervision', 'window', 'wire')}
    fleet, window, wire = (loaded[name] for name in ('supervision', 'window', 'wire'))
    out = Path(job['output'])
    out.mkdir(mode=0o700)
    result = subprocess.run(['/usr/bin/python3.12', '-I', '-B', job['sources']['tests']['path']],
                            capture_output=True, timeout=60)
    stdout = window.publish(out/'tests-stdout-original.txt', result.stdout)
    stderr = window.publish(out/'tests-stderr-original.txt', result.stderr)
    tests = window.publish(out/'actual-test-command.json', dict(argv=result.args, exit=result.returncode,
        stdout=stdout, stderr=stderr, tests_are_synthetic=True, no_model_GPU_or_emulator=True))
    assert result.returncode == 0
    binding = reader.read_pin(job['main_binding'])
    transition = reader.read_pin(job['main_transition'])
    assert transition['current_main_binding'] == job['main_binding']
    window.owner_and_files(binding)
    policy, initial = fleet.make_policy(binding, transition['fleet'])
    policy_pin = window.publish(out/'live-research-policy-not-selected.json', policy)
    state = None
    observations = []
    APIs = []
    for index in range(2):
        if index:
            time.sleep(10)
            window.owner_and_files(binding)
            snapshot = fleet.collect(policy, state)
        else:
            snapshot = initial
        response = urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5).read(wire.MAX_WIRE_BYTES + 1)
        api = wire.parse_wire(response)
        window.healthy(api, reader.read_pin(binding['baseline_API']), binding['experiment'], time.time())
        assert api['quality_campaign']['available'] is False
        state = fleet.validate_snapshot(policy, snapshot, api['client_count'], state)
        assert state['full_capacity'] is True and not state['used_slots']
        raw_pin = window.publish(out/('API-' + str(index) + '-wire.raw'), response)
        witness = window.publish(out/('API-' + str(index) + '-witness.json'), wire.witness_fields(api, raw_pin))
        evidence = window.publish(out/('census-' + str(index) + '.json'), snapshot)
        state_pin = window.publish(out/('state-' + str(index) + '.json'), state)
        observations.append(dict(snapshot=evidence, API=witness, state=state_pin))
        APIs.append(api)
    assert APIs[1]['learner_frame_count'] > APIs[0]['learner_frame_count']
    assert APIs[1]['training_steps'] > APIs[0]['training_steps']
    summary = fleet.validate_closed(state)
    window.owner_and_files(binding)
    for pin in job['sources'].values():
        assert reader.pin(pin['path']) == pin
    assert 'torch' not in sys.modules and 'numpy' not in sys.modules
    report = dict(status='UNSELECTED_PROPOSAL_CPU_AND_LIVE_READONLY_CHECK_PASS', job=job_pin,
        actual_tests=tests, research_policy=policy_pin, actual_readonly_observations=observations,
        live_summary=summary, unchanged_held_inputs=195, current_actual_slots=192,
        live_learner_frame_progress=APIs[1]['learner_frame_count'] - APIs[0]['learner_frame_count'],
        live_update_progress=APIs[1]['training_steps'] - APIs[0]['training_steps'],
        real_supervised_transition_exercised=False, synthetic_transition_tests_only=True,
        original_invalid_quality_reinterpreted=False, selected_for_future_quality=False,
        runtime_changed=False, quality_gain_verified=False, learning_speed_gain_verified=False)
    report_pin = window.publish(out/'verification.json', report)
    print(json.dumps(dict(status=report['status'], report=report_pin), allow_nan=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
