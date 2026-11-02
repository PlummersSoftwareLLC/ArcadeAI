"""Root one-shot dose observation and CONTROL report; never changes learning controls."""
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time
import urllib.request

R = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = R / 'logs/managed-learning-20261015/run-26'
L = B / 'hot-LR625-applied30k-replay10M-learner8M-original01-20261031'
SOURCE = L / 'selected-source/analyze_LR625_dose_v1.py'
SHA = '92e205d416f5bd3c39414bd99e6dee739c19cc5901b62390ae8f954ec117b4b2'


def dump(path, value, *, exclusive=False):
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    temp = path if exclusive else path.with_name('.' + path.name + '.' + str(os.getpid()) + '.tmp')
    with temp.open('xb') as stream:
        stream.write(raw); stream.flush()
        if exclusive: os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    if not exclusive: os.replace(temp, path)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def get(route):
    with urllib.request.urlopen('http://127.0.0.1:8771/api/' + route, timeout=8) as stream:
        return json.load(stream)


def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SHA
    spec = importlib.util.spec_from_file_location('_Root_selected_LR625_dose', SOURCE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    raw_anchor = json.loads((L / 'Root-actual-LR625-dose-anchor-sample-original01.json').read_text())
    exposure = raw_anchor['api_now']['host_pipeline']['learning_exposure']
    anchor = dict(schema='robotron-LR625-dose-anchor-v1', main_owner=raw_anchor['observed_main_owner'],
        expected_lr=6.25e-6, control_sha256=raw_anchor['observed_control_sha256'],
        observed_unix_s=raw_anchor['observed_unix_s'], api_ts=raw_anchor['api_now']['ts'],
        optimizer_identity={k: exposure['optimizer'][k] for k in module.IDS},
        replay_identity={k: exposure['replay'][k] for k in module.IDS},
        base=module.counters(raw_anchor['api_now']), targets=dict(module.TARGETS))
    projection = L / 'Root-projected-LR625-dose-anchor-v1.json'
    if not projection.exists(): dump(projection, anchor, exclusive=True)
    else: assert json.loads(projection.read_text()) == anchor
    started = time.time(); api = get('now'); policy = get('continuous_training_policy')
    stat = Path('/proc/208501/stat')
    birth = int(stat.read_text().rsplit(')', 1)[1].split()[19]) if stat.exists() else -1
    control_sha = hashlib.sha256((R / 'models_dqn/learning_control.json').read_bytes()).hexdigest()
    sample = dict(schema='robotron-Root-hot-LR625-dose-observation-v1',
        observed_unix_s=time.time(), observation_started_unix_s=started,
        observed_main_owner=dict(pid=208501, birth=birth), observed_control_sha256=control_sha,
        api_now=api, continuous_policy=policy, nonatomic_cached_API_snapshots=True)
    directory = L / 'dose-observations-original01'; directory.mkdir(exist_ok=True)
    index = max([int(p.name.split('-')[0]) for p in directory.glob('*-sample.json')] or [0]) + 1
    sample_ref = dump(directory / (f'{index:06d}-sample.json'), sample, exclusive=True)
    previous = L / 'last-valid-dose-counters.json'
    if previous.exists(): sample['previous'] = json.loads(previous.read_text())
    result = module.analyze(anchor, sample)
    if result['status'] == 'VALID':
        for key in ['epsilon', 'expert_ratio']:
            value, expected = api.get(key), raw_anchor['api_now'][key]
            if type(value) not in (int, float) or not math.isfinite(value):
                result = module.result('PENDING', 'Acting setting observation unavailable: ' + key)
                break
            if not math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-12):
                result = module.result('REJECTED', 'Non-LR acting setting changed: ' + key)
                break
        if result['status'] == 'VALID' and policy.get('ratchet_frozen') is not False:
            result = module.result('REJECTED', 'Main ratchet state changed')
    result.update(observed_unix_s=sample['observed_unix_s'], sample=sample_ref,
        source_sha256=SHA, actual_LR=api.get('lr'), actual_epsilon=api.get('epsilon'), actual_expert=api.get('expert_ratio'), Main_FPS=api.get('fps'),
        Main_clients=api.get('client_count'), Main_loss=api.get('loss'), Main_grad_norm=api.get('grad_norm'))
    result_ref = dump(directory / (f'{index:06d}-analysis.json'), result, exclusive=True)
    if result['status'] == 'VALID':
        dump(previous, dict(counters=result['counters'], api_ts=result['api_ts']))
    dump(L / 'live-dose-status.json', result)
    row = {key: result.get(key) for key in ['observed_unix_s', 'status', 'reason', 'all_reached',
        'elapsed_s', 'estimated_remaining_s', 'actual_LR', 'Main_FPS', 'Main_clients', 'Main_loss', 'Main_grad_norm']}
    for group in ['deltas', 'remaining', 'rates_per_s']:
        for key in module.TARGETS: row[group + '_' + key] = result.get(group, {}).get(key)
    e = api['host_pipeline']['learning_exposure']; opt = e['optimizer']; replay = e['replay']
    for key, value in opt['total'].items(): row['optimizer_' + key + '_total'] = value
    row.update(replay_accepted_total=replay['accepted_total'], learner_frame_count=api['learner_frame_count'],
        pipeline_snapshot_age_s=api.get('pipeline_snapshot_age_s'), pipeline_read_error=api.get('pipeline_read_error'))
    for key in ['dqn', 'epsilon', 'expert', 'eval', 'unattributed']:
        row['replay_' + key + '_total'] = replay['accepted_by_source_total'][key]
    for key in ['bc_loss', 'q_mean', 'q_min', 'q_max', 'train_sample_ms', 'train_transfer_ms',
                'train_compute_ms', 'train_priority_ms', 'train_step_ms', 'avg_inf_ms', 'cpu_util',
                'gpu0_util', 'gpu1_util', 'gpu0_power_w', 'gpu1_power_w']:
        row[key] = api.get(key)
    row['c51_diagnostics_json'] = json.dumps(api.get('c51_diagnostics'), separators=(',', ':'))
    table = L / 'actual-training-dose-and-stability.csv'; first = not table.exists()
    with table.open('a') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        if first: writer.writeheader()
        writer.writerow(row)
    control = B / 'dashboard-current-work-status-original01-20261030/work-control.json'
    old = control.read_bytes(); page = json.loads(old); work = page['next_work']
    if result['status'] == 'VALID':
        d, left = result['deltas'], result['remaining']
        if result['all_reached']:
            work.update(state='LR625_dose_reached_waiting_policy_publication',
                current_stage='LR625 training dose reached · preparing the later policy checkpoint',
                waiting_for='A published checkpoint saved after the completed dose, then CPU verification.',
                eta='All three training thresholds are met. The next checkpoint publication and verification are being checked.')
        else:
            estimate = result['estimated_remaining_s']
            work.update(state='LR625_training_dose_running',
                current_stage=f"LR625 trial · {d['applied_updates']:,}/30,000 applied updates · {d['learner_frames']/1e6:.2f}/8M learner frames",
                waiting_for=f"{left['applied_updates']:,} more applied updates, {left['replay_additions']/1e6:.2f}M fresh replay additions and {left['learner_frames']/1e6:.2f}M learner frames; all three thresholds are required.",
                eta=('Waiting for enough measured progress to estimate the dose.' if estimate is None else
                     f'About {math.ceil(estimate/60)} minutes remaining in the training dose at the observed rate. Checkpoint publication, CPU verification and score tests follow; this estimate excludes those later steps.'))
        work['learning_trial'].update(deltas=d, remaining=left, elapsed_s=result['elapsed_s'],
            estimated_dose_remaining_s=result['estimated_remaining_s'])
    else:
        work.update(state='LR625_counter_observation_pending' if result['status'] == 'PENDING' else 'LR625_trial_needs_review',
            current_stage='LR625 trial · ' + ('waiting for a fresh counter observation' if result['status'] == 'PENDING' else 'observation requires review'),
            waiting_for=result['reason'], eta='Counter observation is being checked; no current completion estimate is asserted.')
    work.update(updated_unix_s=sample['observed_unix_s'], observation_unix_s=sample['observed_unix_s'],
        estimated_completion_unix_s=None, deadline_unix_s=None, main_training_continues=True,
        actual_dose_observation=result_ref)
    page['observation_unix_s'] = sample['observed_unix_s']
    assert control.read_bytes() == old, 'Another CONTROL write occurred; preserve this observation'
    dump(control, page)
    print(json.dumps({key: result.get(key) for key in ['observed_unix_s', 'status', 'reason', 'all_reached',
        'deltas', 'remaining', 'estimated_remaining_s', 'actual_LR', 'actual_epsilon', 'actual_expert', 'Main_FPS', 'Main_clients', 'Main_loss', 'Main_grad_norm']}, allow_nan=False))


if __name__ == '__main__':
    main()

