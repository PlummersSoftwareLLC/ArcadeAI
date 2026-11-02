"""Launch one engineering health-interface probe at the next full managed fleet.

No client signals, policy changes, slot refills or scientific jobs. If the
declared full roster never occurs, preserve an inconclusive bounded wait.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import urllib.request


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args):
    raw = args.job.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job = json.loads(raw)
    assert job['schema'] == 'robotron-next-full-round-engineering-probe-gate-v1'
    assert job['maximum_wait_s'] == 14400 and job['required_active'] == 192
    h = load('_full_round_gate_helpers', Path(job['helpers']['path']))
    h.checked(job['helpers'])
    assert h.pin(Path(__file__).resolve()) == job['driver']
    common = load('_full_round_gate_publication', h.checked(job['worker']))
    health = load('_full_round_gate_health', h.checked(job['health']))
    template = json.loads(h.checked(job['case_template']).read_bytes())
    directory = Path(job['output'])
    directory.mkdir(mode=0o700)
    started = time.monotonic()
    last_published = 0
    attempts = 0
    reason = 'Waiting for the next complete managed round to launch naturally'
    while time.monotonic()-started < job['maximum_wait_s']:
        for value in job['inputs']:
            h.checked(value)
        health.check_inputs(template)
        status = common.read(Path(template['round_root'])/'status.json')
        attempts += 1
        if status['round'] >= job['minimum_round'] and status['active'] == 192:
            try:
                with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
                    raw_API = response.read(1_048_577)
                assert len(raw_API) <= 1_048_576, 'Main API exceeds bound'
                api = json.loads(raw_API)
            except (OSError, ValueError) as failure:
                reason = repr(failure)
                time.sleep(.2)
                continue
            if api['client_count'] == 192:
                case = copy.deepcopy(template)
                case['initial_round'] = status['round']
                try:
                    sample = health.collect(case)
                    health.validate(case, sample)
                    assert sample['status']['active'] == sample['api']['client_count'] == 192
                except (OSError, ValueError, AssertionError) as failure:
                    reason = repr(failure)
                else:
                    health.check_inputs(case, full=True)
                    case_pin = h.put(directory/'full-fleet-case.json', case)
                    sample_pin = h.put(directory/'full-fleet-prelaunch-snapshot.json', sample)
                    assert common.show(job['probe_unit'])['LoadState'] == 'not-found'
                    command = ['systemd-run', '--user', '--unit='+job['probe_unit'],
                        '-p', 'CPUQuota=200%', '-p', 'MemoryMax=512M', '-p', 'TasksMax=128',
                        '-p', 'RuntimeMaxSec=180', '-p', 'Restart=no', '-p', 'RemainAfterExit=yes',
                        '/usr/bin/python3', '-I', '-B', job['probe']['path'], '--execute',
                        '--case', case_pin['path'], '--case-sha256', case_pin['sha256'],
                        '--output', str(directory/'runtime')]
                    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                    h.put(directory/'original-launch.json', dict(argv=command, exit=result.returncode,
                        stdout=result.stdout, stderr=result.stderr, case=case_pin,
                        actual_prelaunch_full_fleet=sample_pin, scientific_job=False))
                    assert result.returncode == 0, 'Original full-fleet probe failed to launch; no retry'
                    common.write(directory/'gate-status.json', dict(state='original_probe_launched',
                        unit=job['probe_unit'], round=status['round'], active=192,
                        updated_unix_s=time.time(), no_game_or_training_changes=True), live=True)
                    return
            else:
                reason = 'All192 managed actors have not registered yet'
        if time.monotonic()-last_published >= 5:
            common.write(directory/'gate-status.json', dict(state='waiting_for_full_round',
                updated_unix_s=time.time(), minimum_round=job['minimum_round'],
                current_round=status['round'], current_active=status['active'], reason=reason,
                attempts=attempts, no_game_or_training_changes=True), live=True)
            last_published = time.monotonic()
        time.sleep(.2 if status['round'] >= job['minimum_round'] else .5)
    h.put(directory/'inconclusive-bound.json', dict(state='wait_bound_inconclusive',
        probe_launched=False, original_wait_preserved=True, no_game_or_training_changes=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256')
    args = parser.parse_args()
    if args.execute:
        run(args)
    else:
        print('PLAN_ONLY: no reads or process actions')
