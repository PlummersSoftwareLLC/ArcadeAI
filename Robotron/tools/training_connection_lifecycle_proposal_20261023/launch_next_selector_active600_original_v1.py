"""Fresh preflight and one original B2/A2 launch in the precommitted order."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
E = G / 'logs/managed-learning-20261015/run-26/quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025/selector-active600-counterbalanced-engineering-original01'


def load(path, name, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--case', choices=['03-B2-proposal', '04-A2-baseline'])
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY'); return 0
    h = load(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', '_next_h',
             '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader = load(G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py', '_next_reader',
                  'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    def read(pin):
        return reader.read_pin(pin)
    designpin = h.pin(E / 'controlled-engineering-design-precommit.json')
    assert designpin['sha256'] == '5b57de8e6ba55561acd5873143ca3ab209d4d23cc27bef04bc3b98291ff44d67'
    design = read(designpin)
    ordered = [row['case'] for row in design['ordered_cases']]
    index = ordered.index(args.case)
    assert index in (2, 3)
    qualified = h.pin(E / 'all-four-initializer-closeouts-and-qualified-original-launch-configs.json')
    assert qualified['sha256'] == '82c1227a1b9bd05dd5f75361b6aa77211d359d8ae36988e3c70a3b77c36f941e'
    record = read(qualified)['cases'][index]
    assert record['case'] == args.case
    directory = E / args.case
    job = read(record['native_job']); config = read(record['launch_config'])
    control = load(Path(record['native_controller']['path']), '_next_control', record['native_controller']['sha256'])
    assert control.checked_config(record['launch_config']['path']) == config
    assert not Path(job['output']).exists() and not Path(config['output']).exists()
    for unit in (config['unit'], config['unit'].removesuffix('.service') + '.timer'):
        assert control.show(unit)['LoadState'] == 'not-found'
    for pin in config['pins']:
        assert control.pin(pin['path']) == pin
    prior = []
    for name in ordered[:index]:
        pin = h.pin(E / name / 'independent-original-active600-all-scopes-raw-and-measurement-closeout.json')
        proof = read(pin)
        assert proof['case'] == name and proof['private_resources_free'] is True
        assert proof['status'].startswith('VALID_ORIGINAL_') and proof['quality_qualified'] is False
        assert proof['all_three_original_scope_descriptors_resources_argv_pins_birth_absence_and_release_verified'] is True
        terminal = read(proof['native_and_observer_terminal_closeout'])
        native = read(terminal['native_owner'])
        worker = read(read(read(terminal['native_result'])['main_observer_lifecycle'])['worker_owner'])
        reviewer = read(proof['independent_reviewer_scope']['owner'])
        for owner in (native, worker, reviewer):
            for unit in (owner['unit'], owner['timer']):
                assert control.show(unit)['LoadState'] == 'not-found'
            proc = Path('/proc', str(owner['pid']), 'stat')
            assert not proc.exists() or int(proc.read_text().rsplit(')', 1)[1].split()[19]) != owner['starttime_ticks']
        prior.append(pin)
    goal = json.loads((G / 'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']
    assert job['checkpoint'] == design['reference_policy']
    h.checked(job['checkpoint'])
    monitor = goal['current_main_monitor']; h.checked(monitor)
    process = subprocess.run(['/usr/bin/python3.12', '-I', '-B', monitor['path']], capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr
    main = json.loads(process.stdout)
    assert main['client_count'] == 192 and main['held_inputs'] == 197 and main['autosave_age_s'] <= 360
    gpu = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory', '--format=csv,noheader'], capture_output=True, text=True, timeout=20)
    assert gpu.returncode == 0 and job['gpu_uuid'] not in gpu.stdout
    lease = h.pin(job['lease']['path'])
    assert all(lease[k] == job['lease'][k] for k in ('path', 'sha256', 'bytes'))
    assert all(lease['identity'][k] == value for k, value in job['lease']['identity'].items())
    fd = os.open(job['lease']['path'], os.O_RDWR | os.O_NOFOLLOW)
    sockets = []
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for port in (19998, *range(20000, 20032)):
            sock = socket.socket(); sockets.append(sock); sock.bind(('127.0.0.1', port))
    finally:
        for sock in sockets:
            sock.close()
        fcntl.flock(fd, fcntl.LOCK_UN); os.close(fd)
    assert h.pin(job['lease']['path']) == lease
    preflight = h.put(directory / 'independent-original-prelaunch-prior-cases-closed-main192-GPU-ports-and-lease.json', dict(
        schema='robotron-active600-next-original-prelaunch-readback-v1', observed_unix_s=time.time(),
        case=args.case, fixed_design=designpin, prior_valid_original_closeouts=prior,
        all_prior_original_native_observer_reviewer_units_and_births_absent=True,
        qualified_launch_config=record['launch_config'], main=main,
        GPU=dict(exit=gpu.returncode, stdout=gpu.stdout, stderr=gpu.stderr),
        lease=lease, all33_private_ports_free=True, permanent_lease_unheld_and_unchanged=True,
        no_original_current_case_previously_launched=True, performance_gates_not_evaluated_early=True,
        engineering_only=True, quality_qualified=False))
    print(json.dumps(dict(preflight=preflight, launching=args.case, config=record['launch_config'],
                          controller=record['native_controller'])), flush=True)
    os.execv('/usr/bin/python3.12', ['/usr/bin/python3.12', '-I', '-B', record['native_controller']['path'],
        '--execute', '--config', record['launch_config']['path'], '--expected-source-sha256', record['native_controller']['sha256']])


if __name__ == '__main__':
    raise SystemExit(main())
