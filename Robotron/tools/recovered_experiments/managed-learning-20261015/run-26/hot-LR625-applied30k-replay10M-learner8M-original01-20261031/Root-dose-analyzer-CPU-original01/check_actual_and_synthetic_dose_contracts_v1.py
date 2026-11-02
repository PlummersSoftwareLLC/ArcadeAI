"""Root-only pure CPU dose checks; immutable samples, no live observations/actions."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
L = HERE.parent
SOURCE = L / 'selected-source/analyze_LR625_dose_v1.py'
SHA = '92e205d416f5bd3c39414bd99e6dee739c19cc5901b62390ae8f954ec117b4b2'


def main():
    assert sys.argv[1:] == ['--execute']
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SHA
    spec = importlib.util.spec_from_file_location('_Root_actual_dose_analyzer', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = json.loads((L / 'Root-actual-LR625-dose-anchor-sample-original01.json').read_text())
    actual = json.loads((L / 'dose-observations-original01/000001-sample.json').read_text())
    exposure = raw['api_now']['host_pipeline']['learning_exposure']
    anchor = dict(schema='robotron-LR625-dose-anchor-v1', main_owner=raw['observed_main_owner'],
        expected_lr=6.25e-6, control_sha256=raw['observed_control_sha256'],
        observed_unix_s=raw['observed_unix_s'], api_ts=raw['api_now']['ts'],
        optimizer_identity={k: exposure['optimizer'][k] for k in module.IDS},
        replay_identity={k: exposure['replay'][k] for k in module.IDS},
        base=module.counters(raw['api_now']), targets=dict(module.TARGETS))
    before = copy.deepcopy((anchor, actual))
    result = module.analyze(anchor, actual)
    assert result['status'] == 'VALID' and result['deltas'] == dict(applied_updates=3371,
        replay_additions=1265372, learner_frames=901993) and not result['all_reached']
    assert result['estimated_remaining_s'] > 0 and (anchor, actual) == before
    checks = ['actual immutable sample, exact three deltas, finite ETA, no mutation']
    def case(label, change, expected):
        sample = copy.deepcopy(actual)
        change(sample)
        answer = module.analyze(anchor, sample)
        assert answer['status'] == expected, (label, answer)
        checks.append(label)
    case('owner change rejected', lambda s: s['observed_main_owner'].update(birth=1), 'REJECTED')
    case('control change rejected', lambda s: s.update(observed_control_sha256='1'*64), 'REJECTED')
    case('epoch change rejected', lambda s: s['api_now']['host_pipeline']['learning_exposure']['optimizer'].update(epoch=2), 'REJECTED')
    case('stale cached sample waits', lambda s: s['api_now'].update(ts=anchor['api_ts']), 'PENDING')
    case('missing observations wait', lambda s: s.pop('api_now'), 'PENDING')
    def unavailable(s):
        o = s['api_now']['host_pipeline']['learning_exposure']['optimizer']
        for k in ['attempts_started', 'outcomes_recorded', 'unavailable']: o['total'][k] += 1
        o['available'] = False
    case('new unavailable outcome rejected', unavailable, 'REJECTED')
    def pending(s):
        o = s['api_now']['host_pipeline']['learning_exposure']['optimizer']
        o['total']['attempts_started'] += 1
        o['unclassified_started_total'] = 1
        o['available'] = False
    case('one in-flight outcome waits', pending, 'PENDING')
    def endpoint(learner=8000000):
        sample = copy.deepcopy(raw)
        sample['observed_unix_s'] += 2400
        sample['api_now']['ts'] += 2400
        sample['continuous_policy']['observed_unix_s'] = sample['observed_unix_s'] - .01
        sample['api_now']['pipeline_snapshot_age_s'] = .2
        api = sample['api_now']
        for k in ['attempts_started', 'outcomes_recorded', 'applied']:
            api['host_pipeline']['learning_exposure']['optimizer']['total'][k] += 30000
        replay = api['host_pipeline']['learning_exposure']['replay']
        replay['accepted_total'] += 10000000
        replay['accepted_learner_total'] += 8000000
        for key, value in dict(dqn=7200000, epsilon=800000, expert=1000000, eval=1000000).items():
            replay['accepted_by_source_total'][key] += value
        api['learner_frame_count'] += learner
        api['training_steps'] += 30000
        return sample
    answer = module.analyze(anchor, endpoint())
    assert answer['status'] == 'VALID' and answer['all_reached'] and answer['estimated_remaining_s'] == 0
    checks.append('all three thresholds reached')
    answer = module.analyze(anchor, endpoint(7999999))
    assert answer['status'] == 'VALID' and not answer['all_reached'] and answer['remaining']['learner_frames'] == 1
    checks.append('one frame below third target cannot finish dose')
    sample = copy.deepcopy(actual)
    previous = copy.deepcopy(result['counters'])
    for k in ['attempted', 'outcomes', 'applied']: previous[k] += 1
    sample['previous'] = dict(counters=previous, api_ts=actual['api_now']['ts']-.1)
    assert module.analyze(anchor, sample)['status'] == 'REJECTED'
    checks.append('above-anchor counter decrease from previous valid sample rejected')
    output = dict(status='PASS_PURE_ACTUAL_AND_SYNTHETIC_DOSE_CONTRACTS', actual_exit=0,
        checks=checks, checks_count=len(checks), source_sha256=SHA,
        actual_sample_deltas=result['deltas'], live_API_or_proc_or_model_or_control_actions=False,
        scope='Actual readonly source on existing immutable samples plus synthetic CPU fixtures; not a training/quality result.')
    with (HERE / 'report.json').open('x') as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    print(json.dumps(dict(status=output['status'], checks=len(checks))))


if __name__ == '__main__':
    main()
