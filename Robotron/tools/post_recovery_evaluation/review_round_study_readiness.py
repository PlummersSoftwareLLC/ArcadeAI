"""Review prepared exact jobs and resources without launching an evaluation."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def review(manifest, guards, output):
    h = load('_readiness_helpers', ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    manifest_pin, guards_pin = h.pin(manifest.resolve()), h.pin(guards.resolve())
    study = json.loads(h.checked(manifest_pin).read_bytes())
    receipts = json.loads(h.checked(guards_pin).read_bytes())
    assert study['engineering_only'] is False and receipts['status'] == 'PASS'
    cpu = json.loads(h.checked(receipts['original_all4_CPU_closeout']).read_bytes())
    assert cpu['engineering_only'] is False and cpu['actual_exit'] == 0 and cpu['tests_run'] == 10
    assert cpu['all_six_descriptors_resources_argv_birth_units_cgroup_and_release_verified'] is True
    assert [row['leg'] for row in study['cases']] == ['R1', 'C1', 'R2', 'C2']
    assert len(receipts['guards']) == 4
    configurations, subjects = [], []
    for case, pin in zip(study['cases'], receipts['guards']):
        job = json.loads(h.checked(case['native_job']).read_bytes())
        guard = json.loads(h.checked(pin).read_bytes())
        assert guard['status'] == 'PASS' and guard['native_job'] == case['native_job']
        assert guard['runtime'] == case['runtime'] == job['runtime']
        assert guard['original_all4_CPU_closeout'] == receipts['original_all4_CPU_closeout']
        assert pin['path'] == job['prelaunch_family_guard_closeout']
        for value in job['inputs']:
            h.checked(value)
        assert not Path(job['output']).exists()
        control = load('_readiness_controller', h.checked(case['native_controller']))
        cfg = control.checked_config(case['unqualified_controller_config']['path'])
        for unit in (cfg['unit'], cfg['unit'].removesuffix('.service')+'.timer'):
            assert control.show(unit)['LoadState'] == 'not-found'
        cfg['pins'] += [control.pin(value['path']) for value in
                        (pin, guards_pin, receipts['original_all4_CPU_closeout'])]
        destination = Path(case['unqualified_controller_config']['path']).parent/'controller-config-CPU-QUALIFIED.json'
        new = h.put(destination, cfg)
        assert control.checked_config(new['path']) == cfg
        configurations.append(dict(leg=case['leg'], config=new, controller=case['native_controller']))
        subjects.append(job)
    job = subjects[0]
    h.checked(job['lease'])
    fd = os.open(job['lease']['path'], os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    ports = [job['origin_port'], *job['proxy_ports'].values()]
    for port in ports:
        with socket.socket() as listener:
            listener.bind(('0.0.0.0', port))
    family = json.loads(h.checked(job['source_family_manifest']).read_bytes())
    case = json.loads(h.checked(job['main_binding']).read_bytes())
    health = load('_readiness_health', h.checked(family['main_observer']['health']))
    worker = load('_readiness_observer', h.checked(family['main_observer']['worker']))
    deadline = time.monotonic()+15
    while True:
        try:
            sample = worker.collect(health, case)
            health.validate(case, sample)
            health.check_inputs(case, full=True)
            break
        except (ValueError, OSError):
            assert time.monotonic() < deadline, 'Fresh coherent original main census unavailable'
            time.sleep(.02)
    baseline = h.put(output.with_name('fresh-main-preflight.raw.json'), sample)
    hardware = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_gpu_memory',
                               '--format=csv,noheader'], capture_output=True, text=True, timeout=10)
    assert hardware.returncode == 0
    occupants = [row for row in hardware.stdout.splitlines() if job['gpu_uuid'] in row]
    return h.put(output, dict(schema='robotron-round-study-resource-readiness-v1',
        status='READY' if not occupants else 'WAITING_FOR_PRIVATE_GPU0',
        checked_unix_s=time.time(), prepared_manifest=manifest_pin, exact_four_guards=guards_pin,
        configurations=configurations, all_exact_source_and_checkpoint_pins_verified=True,
        CPU_qualifications_closed=True, original_attempts_unused=True,
        future_service_and_timer_units_absent=True, private_ports_free=ports,
        permanent_lease_identity_verified_and_unlocked=True, fresh_main=baseline,
        main_round=sample['status']['round'], active=sample['status']['active'], completed=sample['status']['completed'],
        GPU0=job['gpu_uuid'], GPU0_occupants=occupants, raw_GPU_readback=hardware.stdout,
        evaluation_started=False, quality_qualified=False, promotion=False,
        checks_must_be_repeated_before_launch=True, source=h.pin(Path(__file__).resolve())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', action='store_true')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--guards', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.review:
        print(json.dumps(review(args.manifest, args.guards, args.output)), flush=True)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
