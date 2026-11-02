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
import stat
import subprocess
import time
import traceback
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



# This adapter is configured only by a new Root-selected exposure plan. It
# confers no scientific main-observer, private-evaluation, or quality proof.
_CONTEXT = None

def configure(plan):
    global _CONTEXT
    assert _CONTEXT is None, 'Configure exactly once per original process'
    context = plan['continuous_context']
    assert context['owner'] == plan['owner']
    assert context['server_stamp'] == dict(pid=654315, birth=16564768,
        source_sha256='a076501b0601a637b91269a41572be60496754ad1da4b04385d77c51b9f34423')
    assert context['owner'] == dict(pid=654315, birth_ticks=16564768,
        invocation_id='c9a7ad073c8043af8b9499acb4ae4372')
    assert type(context['policy_generation']) is int and context['policy_generation'] >= 0
    roles = context['slot_eval']
    assert set(roles) == {str(slot) for slot in range(192)}
    assert all(type(v) is bool for v in roles.values()) and sum(roles.values()) == 37
    assert context['environment'] == {
        'DQN_BATCH_SIZE':'4096','DQN_N_STEP':'3','DQN_MAX_SAMPLES_PER_FRAME':'8',
        'DQN_PER_PRIORITY_METRIC':'ce','ROBOTRON_CONTINUOUS_TRAINING_MODE':'1'}
    lineage = plan['expected_exposure_lineage']
    assert set(lineage) == {'optimizer','replay'}
    assert all(set(v) == set(FIELDS) and v['process_id'] == 654315 and v['epoch'] == 1
               and type(v['instance_monotonic_ns']) is int and v['instance_monotonic_ns'] > 0
               for v in lineage.values())
    assert lineage['optimizer']['epoch_reason'] == 'optimizer_restore_begin'
    assert lineage['replay']['epoch_reason'] == 'directory_adopt_begin'
    _CONTEXT = json.loads(json.dumps(context,allow_nan=False))
    check_context_inputs()


def check_context_inputs():
    assert _CONTEXT is not None, 'Explicit current continuous exposure plan required'
    for value in _CONTEXT['source_and_control_inputs']:
        path=Path(value['path']);before=path.lstat()
        assert stat.S_ISREG(before.st_mode) and not path.is_symlink()
        identity=lambda s:dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,
            mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns,mode=stat.S_IMODE(s.st_mode),
            uid=s.st_uid,nlink=s.st_nlink)
        assert identity(before) == value['identity'] and before.st_uid == os.getuid()
        assert before.st_nlink == 1 and before.st_size <= 2*1024*1024
        data=path.read_bytes();after=path.lstat()
        assert identity(after) == value['identity'] and len(data) == value['bytes']
        assert hashlib.sha256(data).hexdigest() == value['sha256']


def continuous_roster(sample):
    assert _CONTEXT is not None
    rows=sample['client_rows'];roles=_CONTEXT['slot_eval']
    if (sample['training_round'] is not None or type(sample['client_count']) is not int
            or len(rows) != sample['client_count'] or not 155 <= len(rows) <= 192):return False
    slots=[row['client_slot'] for row in rows]
    if (any(type(slot) is not int or not 0 <= slot < 192 for slot in slots)
            or len(set(slots)) != len(slots)):return False
    if any(type(row['eval']) is not bool or row['eval'] != roles[str(row['client_slot'])]
           for row in rows):return False
    # All continuous TRAIN slots must be represented. Absent EVAL rows are not
    # interpreted as completed/reaped/qualified; this is only an exposure census.
    return {str(row['client_slot']) for row in rows if not row['eval']} == {
        slot for slot,is_eval in roles.items() if not is_eval}


def capture_continuous_policy():
    before=time.monotonic()
    with urllib.request.urlopen('http://127.0.0.1:8771/api/continuous_training_policy',timeout=5) as response:
        data=response.read(65537)
    after=time.monotonic()
    assert len(data) <= 65536, 'Bounded current policy metadata required'
    return dict(before_monotonic_s=before,after_monotonic_s=after,
        raw_wire=data.decode('utf-8'),value=json.loads(data))


def validate_continuous_policy(capture):
    assert _CONTEXT is not None
    value=capture['value']
    assert json.loads(capture['raw_wire']) == value
    before=capture['before_monotonic_s'];after=capture['after_monotonic_s']
    assert 0 <= before <= after <= time.monotonic() and after-before <= 5
    assert value['schema'] == 'robotron-continuous-main-policy-v1'
    assert value['server_stamp'] == _CONTEXT['server_stamp']
    assert value['continuous_training_mode'] is True
    assert value['main_measurement_entry_disabled'] is True
    assert value['measurement_active'] is False and value['ratchet_frozen'] is False
    assert type(value['measurement_generation']) is int
    assert value['measurement_generation'] == _CONTEXT['policy_generation']
    assert value['training_enabled'] is True and value['replay_admission_open'] is True
    assert value['consumer_error'] is None
    assert math.isfinite(value['observed_unix_s']) and 0 <= time.time()-value['observed_unix_s'] <= 5
    assert type(value['observed_monotonic_ns']) is int
    assert before <= value['observed_monotonic_ns']/1e9 <= after
    return value


def observe(expected_owner, directory=None, expected_lineage=None):
    """Accept only a balanced exposure sample; re-poll the same live owner.

    OptimizerExposure.available is intentionally false during a started update.
    That publication is retained as unaccepted evidence, never counted as a
    completed update and never substituted for an actual unavailable outcome.
    """
    deadline = time.monotonic() + 30
    while True:
        check_context_inputs()
        assert expected_owner == _CONTEXT['owner']
        assert owner() == expected_owner, 'Original trainer identity changed'
        sample = None
        reason = 'API response unavailable'
        try:
            sample = api()
            sample['_continuous_policy_capture'] = capture_continuous_policy()
            assert owner() == expected_owner, 'Original trainer changed during policy read'
        except (OSError, ValueError) as error:
            reason = repr(error)
        if sample is not None:
            counters = exposure(sample)
            for key in ['optimizer', 'replay']:
                counter = counters[key]
                assert counter.get('enabled') is True, key + ' exposure disabled'
                assert counter.get('process_id') == expected_owner['pid'], key + ' producer changed'
                if expected_lineage is not None:
                    assert all(counter[field] == expected_lineage[key][field] for field in FIELDS), key + ' epoch changed'
            optimizer = counters['optimizer']['total']
            assert optimizer['unavailable'] == 0, 'Unclassified optimizer outcome; not a transient publication'
            pending = optimizer['attempts_started'] - optimizer['outcomes_recorded']
            assert pending in (0, 1), 'Invalid optimizer in-flight count'
            balanced = (pending == 0 and counters['optimizer']['available'] is True
                        and counters['replay']['available'] is True)
            validate_continuous_policy(sample['_continuous_policy_capture'])
            fresh = (0 <= time.time() - sample['ts'] <= 5
                     and 0 <= sample['pipeline_snapshot_age_s'] <= 5)
            coherent_round = continuous_roster(sample)
            if balanced and fresh and coherent_round:
                return sample
            reason = ('in_flight_optimizer_attempt' if pending else
                      'unavailable_or_stale_telemetry_or_round_publication')
        if directory is not None:
            counter = len(list(directory.glob('unaccepted-*.json')))
            publish(directory / ('unaccepted-%06d.json' % counter),
                    dict(reason=reason, unix_s=time.time(), raw_API=sample), exclusive=True)
        if time.monotonic() >= deadline:
            raise TimeoutError('Same live owner has no acceptable balanced exposure sample for30s: ' + reason)
        time.sleep(2)


def exposure(sample):
    return sample['host_pipeline']['learning_exposure']


def validate(sample, expected_owner, previous=None):
    assert sample['training_enabled'] is True and sample['measurement_active'] is False
    assert sample['lr'] == 3.125e-6
    assert abs(sample['epsilon'] - .1) < 1e-12 and abs(sample['expert_ratio'] - .1) < 1e-12
    assert math.isfinite(sample['ts']) and 0 <= time.time() - sample['ts'] <= 5
    assert 0 <= sample['pipeline_snapshot_age_s'] <= 5
    check_context_inputs()
    assert expected_owner == _CONTEXT['owner']
    validate_continuous_policy(sample['_continuous_policy_capture'])
    assert continuous_roster(sample), 'Current continuous TRAIN155 census or None-round contract differs'
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
    anchor = observe(plan['owner'], directory, plan['expected_exposure_lineage'])
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
            current = observe(plan['owner'], directory, plan['expected_exposure_lineage'])
            for value in plan['inputs']:
                check_pin(value)
            validate(current, plan['owner'], previous=last)
            if exposure(current)['optimizer']['total']['applied'] > exposure(last)['optimizer']['total']['applied']:
                last_applied = time.monotonic()
            assert time.monotonic() - last_applied < 60, 'No admitted optimizer update for60s'
            added = additions(current, anchor)
            if crossed is None and ready(current, anchor, plan['minimum_added_each']):
                crossed = time.time()
                publish(directory / 'first-threshold.raw.json', current, exclusive=True)
            status = dict(schema='robotron-post-recovery-observation-window-status-v2',
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
                    '--unit=robotron-post-recovery-endpoint-CPU-original02',
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
                for value in plan['inputs']:
                    check_pin(value)
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
        status_path = args.plan.parent / 'status.json'
        failure = read(status_path) if status_path.exists() else {}
        failure.update(state='failed', updated_unix_s=time.time(), error=repr(error),
                       traceback=traceback.format_exc(), original_attempt_preserved=True,
                       quality_qualified=False)
        publish(args.plan.parent / 'failure.json', failure, exclusive=True)
        publish(status_path, failure)
        publish(Path(read(args.plan)['dashboard_status']), failure)
        raise
