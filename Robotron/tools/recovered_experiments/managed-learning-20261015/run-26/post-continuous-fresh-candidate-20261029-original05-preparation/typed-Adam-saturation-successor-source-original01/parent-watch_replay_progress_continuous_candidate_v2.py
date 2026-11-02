"""Select one future checkpoint using precommitted replay/update/time exposure.

This observational selection never changes training or completes an older window.
The saved policy still requires a separately valid frozen-policy comparison.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import traceback


def load(path):
    spec = importlib.util.spec_from_file_location('_original_exposure_observer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def additions(sample, anchor, elapsed_s):
    exposure = lambda value: value['host_pipeline']['learning_exposure']
    current, initial = exposure(sample), exposure(anchor)
    result = dict(applied_updates=current['optimizer']['total']['applied']-initial['optimizer']['total']['applied'],
        replay_inserts=current['replay']['accepted_total']-initial['replay']['accepted_total'],
        elapsed_s=elapsed_s,
        by_source={key: value-initial['replay']['accepted_by_source_total'][key]
                   for key, value in current['replay']['accepted_by_source_total'].items()})
    assert all(value >= 0 for key, value in result.items() if key != 'by_source')
    assert all(value >= 0 for value in result['by_source'].values())
    assert sum(result['by_source'].values()) == result['replay_inserts']
    return result


def ready(added, thresholds):
    return all(added[key] >= thresholds[key] for key in ('applied_updates', 'replay_inserts', 'elapsed_s'))


def show(unit):
    raw = subprocess.check_output(['systemctl', '--user', 'show', unit], text=True, timeout=5)
    return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)


def verify_CPU(plan, directory, endpoint, observer):
    unit = plan['CPU_unit']
    assert show(unit)['LoadState'] == 'not-found', 'Original CPU unit already exists; no adoption/retry'
    command = ['systemd-run', '--user', '--unit='+unit, '-p', 'CPUQuota=200%', '-p', 'MemoryMax=4G',
        '-p', 'MemorySwapMax=0', '-p', 'TasksMax=128', '-p', 'RuntimeMaxSec=180', '-p', 'Restart=no',
        '-p', 'RemainAfterExit=yes', 'env', 'CUDA_VISIBLE_DEVICES=', 'DQN_BATCH_SIZE=4096',
        'DQN_N_STEP=3', 'DQN_MAX_SAMPLES_PER_FRAME=8', plan['python'], '-Xgil=0', '-I', '-B',
        plan['verifier'], '--checkpoint', endpoint['path'], '--report', str(directory/'endpoint-CPU.json')]
    launched = subprocess.run(command, capture_output=True, text=True, timeout=10)
    observer.publish(directory/'CPU-original-launch.json', dict(argv=command, exit=launched.returncode,
        stdout=launched.stdout, stderr=launched.stderr), exclusive=True)
    assert launched.returncode == 0, 'Original CPU launch failed'
    original = show(unit)
    assert original['MainPID'] != '0', 'Original CPU identity unavailable'
    pid = int(original['MainPID'])
    birth = int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    expected = dict(CPUQuotaPerSecUSec='2s', MemoryMax=str(4 << 30), MemorySwapMax='0',
                    TasksMax='128', RuntimeMaxUSec='3min', Restart='no', NRestarts='0')
    assert all(original[key] == value for key, value in expected.items()), 'Original CPU resources differ'
    observer.publish(directory/'CPU-original-owner.json', dict(unit=unit, pid=pid, birth=birth,
        invocation_id=original['InvocationID'], actual_properties=original), exclusive=True)
    deadline = time.monotonic()+210
    while True:
        actual = show(unit)
        assert actual['InvocationID'] == original['InvocationID'] and actual['NRestarts'] == '0'
        if actual['MainPID'] == '0':
            break
        assert actual['MainPID'] == str(pid) and time.monotonic() < deadline, 'Original CPU completion unknown'
        assert int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]) == birth
        time.sleep(.5)
    observer.publish(directory/'CPU-original-terminal.json', actual, exclusive=True)
    assert all(actual[key] == value for key, value in expected.items())
    assert actual['ExecMainPID'] == str(pid) and actual['ExecMainCode'] == '1' and actual['ExecMainStatus'] == '0'
    assert not Path('/proc', str(pid)).exists(), 'Original CPU birth still present'
    verification = observer.read(directory/'endpoint-CPU.json')
    assert verification['checkpoint'] == endpoint and verification['CUDA_initialized'] is False
    stopped = subprocess.run(['systemctl', '--user', 'stop', unit], capture_output=True, text=True, timeout=10)
    assert stopped.returncode == 0
    released = show(unit)
    assert released['MainPID'] == '0' and released['ActiveState'] == 'inactive'
    assert not Path('/sys/fs/cgroup'+original['ControlGroup']).exists()
    observer.publish(directory/'CPU-owned-release.json', dict(unit=unit, original=original,
        terminal=actual, after_release=released, original_birth_absent=True), exclusive=True)
    return verification


def run(plan_path):
    plan = json.loads(plan_path.read_bytes())
    source = Path(plan['observer_library']['path'])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == plan['observer_library']['sha256']
    observer = load(source)
    observer.configure(plan)
    directory = plan_path.parent
    assert plan['thresholds'] == dict(applied_updates=5000, replay_inserts=1_000_000, elapsed_s=3600)
    assert plan['maximum_wait_s'] == 14400 and plan['original_DQN_window_unchanged'] is True
    assert not (directory/'anchor.raw.json').exists(), 'Original candidate window already started'
    for value in plan['inputs']:
        observer.check_pin(value)
    anchor = observer.observe(plan['owner'], directory, plan['expected_exposure_lineage'])
    observer.validate(anchor, plan['owner'])
    observer.publish(directory/'anchor.raw.json', anchor, exclusive=True)
    started = time.monotonic()
    previous = anchor
    last_update = started
    crossed = None
    with (directory/'observations.jsonl').open('x') as stream:
        while True:
            for value in plan['inputs']:
                observer.check_pin(value)
            current = observer.observe(plan['owner'], directory, plan['expected_exposure_lineage'])
            observer.validate(current, plan['owner'], previous=previous)
            added = additions(current, anchor, time.monotonic()-started)
            if added['applied_updates'] > additions(previous, anchor, 0)['applied_updates']:
                last_update = time.monotonic()
            assert time.monotonic()-last_update < 60, 'No admitted optimizer update for60s'
            status = dict(schema='robotron-replay-progress-candidate-window-status-v1',
                state='waiting_for_autosave' if crossed else 'collecting', updated_unix_s=time.time(),
                owner=plan['owner'], added=added, thresholds=plan['thresholds'],
                original_DQN_window_unchanged=True, quality_qualified=False,
                causal_learning_speed_qualified=False, promotion=False)
            if crossed is None and ready(added, plan['thresholds']):
                crossed = time.time()
                observer.publish(directory/'first-threshold.raw.json', current, exclusive=True)
                status['state'] = 'waiting_for_autosave'
            observer.publish(directory/'status.json', status)
            observer.publish(Path(plan['dashboard_status']), status)
            stream.write(json.dumps(status)+'\n')
            stream.flush()
            checkpoint = Path(plan['checkpoint'])
            if crossed is not None and checkpoint.stat().st_mtime > crossed+10:
                endpoint = observer.copy_snapshot(checkpoint, directory/'endpoint.pt')
                observer.publish(directory/'capture-context.raw.json', current, exclusive=True)
                verification = verify_CPU(plan, directory, endpoint, observer)
                threshold = observer.read(directory/'first-threshold.raw.json')
                assert all(verification['clocks'][key] >= threshold[key] for key in observer.CLOCKS)
                assert verification['clocks']['training_steps'] > anchor['training_steps']
                assert verification['Adam_step_min'] > plan['entry_Adam_step']
                for value in plan['inputs']:
                    observer.check_pin(value)
                status.update(state='captured_CPU_verified', endpoint=endpoint,
                    CPU_verification=observer.pin(directory/'endpoint-CPU.json'), updated_unix_s=time.time())
                observer.publish(directory/'result.json', status, exclusive=True)
                observer.publish(directory/'status.json', status)
                observer.publish(Path(plan['dashboard_status']), status)
                return
            if time.monotonic()-started >= plan['maximum_wait_s']:
                status['state'] = 'exposure_bound_inconclusive'
                observer.publish(directory/'inconclusive.json', status, exclusive=True)
                observer.publish(directory/'status.json', status)
                observer.publish(Path(plan['dashboard_status']), status)
                return
            previous = current
            time.sleep(10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.plan.resolve(strict=True))
    except BaseException as failure:
        plan = json.loads(args.plan.read_bytes())
        observer = load(Path(plan['observer_library']['path']))
        status = dict(state='failed', reason=repr(failure), traceback=traceback.format_exc(),
            updated_unix_s=time.time(), original_attempt_preserved=True, original_DQN_window_unchanged=True)
        observer.publish(args.plan.parent/'failure.json', status, exclusive=True)
        observer.publish(args.plan.parent/'status.json', status)
        observer.publish(Path(plan['dashboard_status']), status)
        raise
