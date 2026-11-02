"""Bounded read-only driver counters; no profiler or CUDA workload is launched."""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).parent
OUT = N / 'readonly-GPU-driver-series300-original01'
EXPECTED = {(437094, 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'),
            (3615927, 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1')}
OWNERS = {437094: 105466651, 3615927: 78856521}


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def observe():
    helper = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    spec = importlib.util.spec_from_file_location('_driver_h', helper)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    assert OUT.parent == N and OUT.resolve() == OUT and not OUT.exists()
    OUT.mkdir(mode=0o700)
    h.put(OUT / 'observer-intent.json', dict(
        schema='robotron-readonly-driver-series-intent-v1', source=h.pin(__file__),
        pid=os.getpid(), birth=birth(os.getpid()), duration_s=300, interval_s=25,
        expected_original_owners=[dict(pid=p, gpu_uuid=u) for p, u in sorted(EXPECTED)],
        GPU_workload_launched=False, profiler_attached=False,
        created_unix_s=time.time()))
    started = time.monotonic()
    samples = []
    transition = False
    errors = []
    for index in range(13):
        if index:
            time.sleep(max(0, 25 * index - (time.monotonic() - started)))
        native_result = N / '01-reference/diagnostic-output-original01/result.json'
        status = json.loads((native_result.parent / 'status.json').read_bytes())
        if native_result.exists() or status['controller'].get('complete') is True:
            transition = True
            break
        if time.monotonic() - started > 330:
            errors.append('Read-only overall observation budget exceeded')
            break
        row = dict(index=index, observed_unix_s=time.time(), commands=[], errors=[])
        try:
            assert all(birth(pid) == value for pid, value in OWNERS.items()), 'Original owner birth changed'
            commands = [
                ['nvidia-smi', '--query-gpu=index,uuid,name,utilization.gpu,utilization.memory,memory.used,power.draw',
                 '--format=csv,noheader,nounits'],
                ['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory',
                 '--format=csv,noheader,nounits']]
            for argv in commands:
                begin = time.time()
                result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
                row['commands'].append(dict(argv=argv, started_unix_s=begin,
                    ended_unix_s=time.time(), returncode=result.returncode,
                    stdout=result.stdout, stderr=result.stderr))
                assert result.returncode == 0, 'Driver query failed'
            devices = list(csv.reader(io.StringIO(row['commands'][0]['stdout']), skipinitialspace=True))
            owners = list(csv.reader(io.StringIO(row['commands'][1]['stdout']), skipinitialspace=True))
            actual = {(int(r[0]), r[1].strip()) for r in owners}
            row['only_expected_compute_owners'] = actual == EXPECTED
            row['devices'] = [dict(index=int(r[0]), gpu_uuid=r[1].strip(), name=r[2].strip(),
                utilization_gpu_percent=float(r[3]), utilization_memory_percent=float(r[4]),
                memory_used_MiB=float(r[5]), power_W=float(r[6])) for r in devices]
            assert actual == EXPECTED, 'Unexpected compute owner or missing original compute owner'
        except Exception as error:
            row['errors'].append(repr(error))
        pin = h.put(OUT / f'{index:02d}-driver-sample.json', row)
        samples.append(pin)
        print(json.dumps(dict(sample=pin, errors=row['errors'],
            devices=row.get('devices', []))), flush=True)
        if row['errors']:
            errors.extend(row['errors'])
            break
    receipt = h.put(OUT / 'observer-receipt.json', dict(
        schema='robotron-readonly-driver-series-receipt-v1', created_unix_s=time.time(),
        intent=h.pin(OUT / 'observer-intent.json'), samples=samples,
        planned_duration_s=300, elapsed_s=time.monotonic() - started,
        original_science_transition_observed=transition, errors=errors,
        GPU_workload_launched=False, profiler_attached=False,
        scientific_sources_or_runtime_changed=False,
        quality_qualified=False, full_game_speed_gain_verified=False,
        learning_speed_gain_verified=False,
        limits=['Decimated driver counters do not identify kernel, transfer, scheduling or wait costs.',
                'Utilization alone does not establish a causal bottleneck, capacity gain or learning speed.']))
    print(json.dumps(dict(receipt=receipt, errors=errors, transition_observed=transition)), flush=True)
    return 2 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe', action='store_true')
    args = parser.parse_args()
    if not args.observe:
        print('PLAN_ONLY: no input reads, driver queries, files or workloads')
        return 0
    return observe()


if __name__ == '__main__':
    raise SystemExit(main())
