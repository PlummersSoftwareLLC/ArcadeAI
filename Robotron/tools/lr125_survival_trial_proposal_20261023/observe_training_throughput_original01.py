"""One passive 120-second observation of existing clocks; no training controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = G / 'logs/managed-learning-20261015/run-26/quality32-protected1741-vs-currentLR125-firstSave-original01-preparation-20261023'


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def write(path, value):
    raw = value if isinstance(value, bytes) else json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def cpu_stat(unit):
    root = Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', unit)
    return {name: (root / name).read_text() for name in ('cpu.stat', 'cpu.pressure', 'memory.current', 'memory.events')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe', action='store_true')
    args = parser.parse_args()
    if not args.observe:
        print('PLAN_ONLY'); return 0
    target = N / 'passive-training-throughput-original01'
    target.mkdir(mode=0o700)
    original = dict(main=(3615927, 78856521), native=(2451014, 87906951), sequence=(2450672, 87906238))
    assert all(birth(pid) == ticks for pid, ticks in original.values())
    write(target / 'intent.json', dict(pid=os.getpid(), birth=birth(os.getpid()), source=str(Path(__file__).resolve()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), original_owners=original,
        duration_s=120, interval_s=5, original_attempt=1, no_retry=True, passive_only=True, created_unix_s=time.time()))
    print(json.dumps(dict(passive_pid=os.getpid(), birth=birth(os.getpid()), output=str(target))), flush=True)
    rows = []; started = time.monotonic()
    try:
        for index in range(25):
            if index:
                time.sleep(max(0, started + index * 5 - time.monotonic()))
            assert all(birth(pid) == ticks for pid, ticks in original.values()), 'Original main/eval/sequence owner changed'
            begin = time.monotonic()
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
                raw = response.read(1048577)
            assert len(raw) <= 1048576
            api = json.loads(raw)
            wire = write(target / f'{index:02d}-API.raw.json', raw)
            pipeline = api['host_pipeline']; exposure = pipeline['learning_exposure']
            assert exposure['optimizer']['process_id'] == exposure['replay']['process_id'] == original['main'][0]
            assert api['client_count'] == 192 and api['training_enabled'] is True and api['measurement_active'] is False
            assert all(pipeline[key]['errors'] == 0 for key in ('inference', 'actor_refresh', 'target_refresh', 'learner_priority'))
            assert api['bank_persistence']['write_failures'] == 0
            native = json.loads((N / '01-reference/diagnostic-output-original01/status.json').read_bytes())
            assert native['original_pid'] == original['native'][0] and not native['errors']
            assert time.time() - native['observed_unix_s'] < 20
            rows.append(dict(index=index, monotonic_s=begin, unix_s=time.time(), API=wire,
                API_latency_s=time.monotonic()-begin,
                main_cgroup=cpu_stat('robotron-managed-run-26-d3b365c9-trainer.service'),
                eval_cgroup=cpu_stat('robotron-compiled-full-tail32-integration-quality1741-currentlr125-firstsave-r1-original01-20261023.service'),
                memory_pressure=Path('/proc/pressure/memory').read_text(), cpu_pressure=Path('/proc/pressure/cpu').read_text(),
                eval_phase=native['controller']['phase'], eval_completed=native['controller']['cohort']['count'],
                eval_min_sequence=min(row['sequence'] for row in native['slots'].values())))
        result = dict(status='PASSIVE_120S_OBSERVATION_COMPLETE', samples=rows,
                      elapsed_s=time.monotonic()-started, quality_qualified=False,
                      causal_throughput_or_learning_speed_gain_verified=False, production_changed=False)
    except Exception as error:
        result = dict(status='PASSIVE_ORIGINAL_OBSERVATION_FAILED_NO_RETRY', error=repr(error), samples=rows,
                      elapsed_s=time.monotonic()-started, quality_qualified=False, production_changed=False)
    result['ended_unix_s'] = time.time()
    receipt = write(target / 'result.json', result)
    print(json.dumps(dict(result=receipt, status=result['status'], samples=len(rows))), flush=True)
    return 0 if result['status'] == 'PASSIVE_120S_OBSERVATION_COMPLETE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
