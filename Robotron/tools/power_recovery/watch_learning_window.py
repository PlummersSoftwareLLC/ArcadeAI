"""Observe one new continuation window and preserve its first eligible autosave.

No control writes, learner restarts, game interruption, evaluation, or promotion.
Original failures are terminal. A new process/epoch requires a new declared case.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

FIELDS = ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')
CLOCKS = ('learner_frame_count', 'training_steps', 'optimized_samples', 'frame_count')


def read(path):
    return json.loads(Path(path).read_bytes())


def pin(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path.resolve()), sha256=digest, bytes=path.stat().st_size)


def check_pin(value):
    assert pin(Path(value['path'])) == value, value['path']


def publish(path, value, exclusive=False):
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    temporary = path if exclusive else path.with_name(path.name + '.tmp')
    with temporary.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444 if exclusive else 0o664)
        os.fsync(stream.fileno())
    if not exclusive:
        os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def owner():
    raw = subprocess.check_output(['systemctl', '--user', 'show',
        'robotron-trainer.service', '-p', 'MainPID', '-p', 'InvocationID',
        '-p', 'ActiveState', '-p', 'NRestarts'], text=True)
    data = dict(line.split('=', 1) for line in raw.splitlines())
    assert data['ActiveState'] == 'active' and data['NRestarts'] == '0'
    pid = int(data['MainPID'])
    birth = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
    return dict(pid=pid, birth_ticks=birth, invocation_id=data['InvocationID'])


def api():
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        return json.load(response)


def observe(expected_owner):
    # API publication and round turnover can briefly lag the live process.
    # Retry the same owner; a timeout never restarts or signals the trainer.
    deadline = time.monotonic() + 30
    while True:
        assert owner() == expected_owner
        try:
            sample = api()
            round_status = sample['training_round']
            if (0 <= time.time() - sample['ts'] <= 5
                    and 0 <= sample['pipeline_snapshot_age_s'] <= 5
                    and sample['client_count'] <= round_status['active']):
                return sample
        except (OSError, ValueError, KeyError):
            pass
        if time.monotonic() >= deadline:
            raise TimeoutError('Same live owner unobservable or round counts inconsistent for30s')
        time.sleep(2)


def exposure(sample):
    return sample['host_pipeline']['learning_exposure']


def validate(sample, expected_owner, previous=None):
    assert sample['training_enabled'] is True and sample['measurement_active'] is False
    assert sample['lr'] == 3.125e-6
    assert abs(sample['epsilon'] - .1) < 1e-12 and abs(sample['expert_ratio'] - .1) < 1e-12
    assert math.isfinite(sample['ts']) and 0 <= time.time() - sample['ts'] <= 5
    assert 0 <= sample['pipeline_snapshot_age_s'] <= 5
    round_status = sample['training_round']
    assert round_status['total'] == 192
    assert round_status['retired'] + round_status['active'] == 192
    assert 0 <= round_status['retired'] <= round_status['completed'] <= 192
    rows = sample['client_rows']
    assert len(rows) == sample['client_count'] and len({x['client_slot'] for x in rows}) == len(rows)
    assert all(0 <= x['client_slot'] < 192 for x in rows)
    assert sample['client_count'] <= round_status['active']
    counters = exposure(sample)
    for key in ['optimizer', 'replay']:
        assert counters[key]['available'] is True and counters[key]['enabled'] is True
        assert counters[key]['process_id'] == expected_owner['pid']
        if previous is not None:
            assert all(counters[key][field] == exposure(previous)[key][field] for field in FIELDS)
    optimizer = counters['optimizer']['total']
    assert optimizer['unavailable'] == 0
    assert 0 <= optimizer['attempts_started'] - optimizer['outcomes_recorded'] <= 1
    assert optimizer['outcomes_recorded'] == optimizer['applied'] + optimizer['amp_skipped']
    replay = counters['replay']
    assert replay['accepted_learner_total'] == sum(replay['accepted_by_source_total'][key]
                                                for key in ['dqn', 'epsilon'])
    if previous is not None:
        assert all(sample[key] >= previous[key] for key in CLOCKS)
        assert replay['accepted_learner_total'] >= exposure(previous)['replay']['accepted_learner_total']
        assert optimizer['applied'] >= exposure(previous)['optimizer']['total']['applied']


def additions(sample, anchor):
    return dict(learner_frames=sample['learner_frame_count'] - anchor['learner_frame_count'],
        accepted_DQN_epsilon=exposure(sample)['replay']['accepted_learner_total']
                            - exposure(anchor)['replay']['accepted_learner_total'])


def ready(sample, anchor, minimum):
    return all(value >= minimum for value in additions(sample, anchor).values())


def copy_snapshot(source, destination):
    with source.open('rb') as incoming, destination.open('xb') as outgoing:
        before = os.fstat(incoming.fileno())
        shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
        outgoing.flush()
        os.fchmod(outgoing.fileno(), 0o444)
        os.fsync(outgoing.fileno())
        after = os.fstat(incoming.fileno())
        assert before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
    return pin(destination)


def run(plan_path):
    plan = read(plan_path)
    directory = plan_path.parent
    assert not (directory / 'anchor.raw.json').exists(), 'Original window already started'
    assert plan['minimum_added_each'] == 8_000_000
    for value in plan['inputs']:
        check_pin(value)
    assert owner() == plan['owner']
    anchor = observe(plan['owner'])
    validate(anchor, plan['owner'])
    publish(directory / 'anchor.raw.json', anchor, exclusive=True)
    last = anchor
    last_applied = time.monotonic()
    crossed = None
    with (directory / 'observations.jsonl').open('x') as observations:
        while True:
            for value in plan['inputs']:
                check_pin(value)
            assert owner() == plan['owner']
            current = observe(plan['owner'])
            validate(current, plan['owner'], previous=last)
            if exposure(current)['optimizer']['total']['applied'] > exposure(last)['optimizer']['total']['applied']:
                last_applied = time.monotonic()
            assert time.monotonic() - last_applied < 60, 'No admitted optimizer update for60s'
            added = additions(current, anchor)
            if crossed is None and ready(current, anchor, plan['minimum_added_each']):
                crossed = time.time()
                publish(directory / 'first-threshold.raw.json', current, exclusive=True)
            status = dict(schema='robotron-post-recovery-observation-window-status-v1',
                state='waiting_for_autosave' if crossed else 'collecting',
                updated_unix_s=time.time(), anchor_unix_s=anchor['ts'], minimum_added_each=8_000_000,
                added=added, owner=plan['owner'], round=current['training_round']['round'],
                active=current['client_count'], completed=current['training_round']['completed'],
                applied_updates=exposure(current)['optimizer']['total']['applied']
                                - exposure(anchor)['optimizer']['total']['applied'],
                old_interrupted_window_not_rescued=True, quality_qualified=False,
                causal_learning_speed_qualified=False,
                next_stage='Freeze and CPU-verify a checkpoint, then prepare a matched frozen-policy comparison')
            publish(directory / 'status.json', status)
            publish(Path(plan['dashboard_status']), status)
            observations.write(json.dumps(dict(ts=current['ts'], added=added,
                applied=exposure(current)['optimizer']['total']['applied'],
                round=status['round'], active=status['active'])) + '\n')
            observations.flush()
            source = Path(plan['checkpoint'])
            if crossed is not None and source.stat().st_mtime > crossed + 10:
                endpoint = copy_snapshot(source, directory / 'endpoint.pt')
                publish(directory / 'capture-context.raw.json', current, exclusive=True)
                command = ['systemd-run', '--user', '--wait', '--pipe',
                    '--unit=robotron-post-recovery-endpoint-CPU-original01',
                    '-p', 'CPUQuota=200%', '-p', 'MemoryMax=4G', '-p', 'RuntimeMaxSec=180',
                    'env', 'CUDA_VISIBLE_DEVICES=', 'DQN_BATCH_SIZE=4096', 'DQN_N_STEP=3',
                    'DQN_MAX_SAMPLES_PER_FRAME=8', plan['python'], '-Xgil=0', '-I', '-B',
                    plan['verifier'], '--checkpoint', endpoint['path'],
                    '--report', str(directory / 'endpoint-CPU-verification.json')]
                with (directory / 'endpoint-CPU-console.log').open('x') as log:
                    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=210)
                assert result.returncode == 0, 'Original endpoint CPU validation failed'
                verification = read(directory / 'endpoint-CPU-verification.json')
                assert verification['checkpoint'] == endpoint
                assert verification['clocks']['learner_frame_count'] >= read(
                    directory / 'first-threshold.raw.json')['learner_frame_count']
                assert verification['Adam_step_min'] > plan['entry_Adam_step']
                status.update(state='captured_CPU_verified', endpoint=endpoint,
                              CPU_verification=pin(directory / 'endpoint-CPU-verification.json'),
                              updated_unix_s=time.time())
                publish(directory / 'result.json', status, exclusive=True)
                publish(directory / 'status.json', status)
                publish(Path(plan['dashboard_status']), status)
                return
            last = current
            time.sleep(10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.plan.resolve(strict=True))
    except BaseException as error:
        failure = dict(state='failed', updated_unix_s=time.time(), error=str(error),
                       original_attempt_preserved=True, quality_qualified=False)
        publish(args.plan.parent / 'failure.json', failure, exclusive=True)
        publish(Path(read(args.plan)['dashboard_status']), failure)
        raise
