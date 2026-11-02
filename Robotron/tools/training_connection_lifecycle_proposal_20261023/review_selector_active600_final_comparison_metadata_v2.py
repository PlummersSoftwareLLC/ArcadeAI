"""Bind all four original engineering closeouts to the fixed exact gates."""
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


def load(pin, name):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY'); return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    assert hashlib.sha256(args.job.read_bytes()).hexdigest() == args.job_sha256
    job = json.loads(args.job.read_text())
    assert job['schema'] == 'robotron-selector-active600-original-final-comparison-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    h = load(job['helpers'], '_final_h'); reader = load(job['reader'], '_final_reader')
    arc = load(job['archive'], '_final_archive'); comparator = load(job['comparator'], '_final_exact_gates')
    def read(pin, as_json=True):
        return reader.read_pin(pin, as_json=as_json)
    for pin in job['inputs']:
        h.checked(pin)
    design = read(job['design'])
    assert job['design']['sha256'] == '5b57de8e6ba55561acd5873143ca3ab209d4d23cc27bef04bc3b98291ff44d67'
    ordered = [r['case'] for r in design['ordered_cases']]
    assert ordered == ['01-A1-baseline', '02-B1-proposal', '03-B2-proposal', '04-A2-baseline']
    qualified = read(job['qualified_cases'])['cases']
    assert [r['case'] for r in qualified] == ordered
    assert len(job['case_closeouts']) == len(job['case_review_configs']) == 4
    output = Path(job['output']); assert not output.exists() and output.parent.is_dir()

    def scope(ownerpin, closurepin, configpin, exit_code, runtime, quota, memory, tasks, stop, native=False):
        owner, closure, config = read(ownerpin), read(closurepin), read(configpin)
        fields = arc.archived_closure(closure, owner, read, exit_zero=exit_code == 0)
        assert closure['original_exit'] == exit_code
        expected = dict(Id=owner['unit'], InvocationID=owner['invocation_id'], ExecMainPID=str(owner['pid']),
            ExecMainCode='1', ExecMainStatus=str(exit_code), CPUQuotaPerSecUSec=quota, MemoryMax=str(memory),
            MemorySwapMax='0', RuntimeMaxUSec=runtime, TasksMax=str(tasks), TimeoutStopUSec=stop,
            SendSIGKILL='no', Restart='no', NRestarts='0')
        if native:
            expected['KillMode'] = 'mixed'
        for key, value in expected.items():
            assert fields[key] == value, (key, fields[key], value)
        command = '/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR=' + str(Path(config['output']) / 'tmp') + ' ' + ' '.join(config['argv'])
        assert command + ' ; ignore_errors=no ;' in fields['ExecStart']
        for pin in config['pins']:
            current = h.pin(pin['path'])
            assert all(current[key] == pin[key] for key in ('path', 'sha256', 'bytes'))
            assert all(current['identity'][key] == value for key, value in pin['identity'].items())
        for unit in (owner['unit'], owner['timer']):
            process = subprocess.run(['systemctl', '--user', 'show', unit], capture_output=True, text=True, timeout=5)
            assert process.returncode == 0
            state = dict(line.split('=', 1) for line in process.stdout.splitlines() if '=' in line)
            assert state['LoadState'] == 'not-found'
        proc = Path('/proc', str(owner['pid']), 'stat')
        assert not proc.exists() or int(proc.read_text().rsplit(')', 1)[1].split()[19]) != owner['starttime_ticks']
        cgroup = fields.get('ControlGroup', '')
        assert not cgroup or not (Path('/sys/fs/cgroup' + cgroup) / 'cgroup.procs').exists() or not (Path('/sys/fs/cgroup' + cgroup) / 'cgroup.procs').read_text().strip()
        start = int(fields['ExecMainStartTimestampMonotonic'])
        end = int(fields['ExecMainExitTimestampMonotonic'])
        assert 0 < start < end <= int(time.monotonic() * 1e6)
        return dict(owner=ownerpin, closure=closurepin, config=configpin,
            actual_exit=exit_code, original6_descriptors_argv_resources_pins_and_release_verified=True,
            start_monotonic_us=start, end_monotonic_us=end)

    mathproof = read(job['math_guard_closeout'])
    assert mathproof['all13_original_math_contracts_passed'] is True
    # Prior CPU closeouts use ABI5; verify every declared field against full8.
    for old_key, job_key in (('comparison_source', 'comparator'), ('fixed_design', 'design')):
        declared, current = mathproof[old_key], job[job_key]
        h.checked(current)
        assert all(declared[key] == current[key] for key in ('path', 'sha256', 'bytes'))
        assert all(current['identity'][key] == value for key, value in declared['identity'].items())
    assert mathproof['actual_observed_tool_exit'] == 0
    mathscope = scope(mathproof['owner'], mathproof['closure'], job['math_guard_config'],
                      0, '3min', '2s', 4 << 30, 128, '5s')
    measurements, validated, all_sessions = {}, [], []
    previous_review_end = None
    for index, name in enumerate(ordered):
        casepin = job['case_closeouts'][index]; proof = read(casepin); declared = qualified[index]
        assert proof['case'] == name and proof['private_resources_free'] is True
        assert proof['all_three_original_scope_descriptors_resources_argv_pins_birth_absence_and_release_verified'] is True
        assert (proof['actual_native_exit'], proof['actual_observer_exit'], proof['actual_reviewer_exit']) == (1, 0, 0)
        assert proof['quality_qualified'] is proof['scientific_case'] is False
        assert proof['native_job'] == declared['native_job']
        native = read(proof['native_job']); result = read(proof['native_result']); report = read(proof['independent_report'])
        assert native['engineering_case'] == name and native['engineering_implementation'] == design['ordered_cases'][index]['implementation']
        implementation = native['engineering_implementation']
        assert native['diagnostic_precommit'] == job['design']
        assert native['checkpoint'] == design['reference_policy'] and native['expected_policy_clocks'] == design['reference_saved_clocks']
        common = design['common_runtime']
        for key in ('source_package', 'boot_seed', 'seed_runtime', 'gpu_uuid', 'backend', 'device',
                    'cpu_threads', 'actor_slots', 'origin_port', 'proxy_ports', 'lease', 'main_binding'):
            assert native[key] == common[key], key
        for key in ('view', 'drain'):
            assert native['quota64_source_pins'][key]['sha256'] == design['implementations'][implementation][key]['sha256']
        assert native['quota64_source_pins']['bridge'] == design['common_bridge']
        all_sessions += [*native['sessions'].values(), *native['connections'].values()]
        assert report['native_job'] == proof['native_job'] and report['native_result'] == proof['native_result']
        assert report['private_resources_free'] is True and report['quality_qualified'] is False
        assert report['native_expected_exit1_verified'] is report['all_original_fixed_query_kernel_epochs_and_raw_headers_independently_replayed'] is True
        assert len(report['all32_original_startup_prefixes']) == 32
        assert all(row['all1200_original_pairs_and_loaded_ROM_verified'] for row in report['all32_original_startup_prefixes'])
        assert report['raw_replay']['samples'] == proof['raw_samples'] and report['raw_replay']['deep_samples'] == proof['deep_samples']
        assert report['raw_replay']['maximum_observation_gap_s'] <= .5
        terminal = read(proof['native_and_observer_terminal_closeout'])
        assert terminal['native_result'] == proof['native_result'] and terminal['native_config'] == declared['launch_config']
        native_scope = scope(terminal['native_owner'], terminal['native_closure'], declared['launch_config'],
                             1, '6h 11min', '12s', 16 << 30, 512, '30s', native=True)
        life = read(result['main_observer_lifecycle'])
        assert life['success'] is life['all_owned_worker_and_controller_processes_reaped'] is life['original_scope_released'] is True
        worker_scope = scope(life['worker_owner'], life['worker_closure'], life['worker_config'],
                             0, '6h 11min', '2s', 4 << 30, 128, '5s')
        reviewer = proof['independent_reviewer_scope']
        review_scope = scope(reviewer['owner'], reviewer['closure'], job['case_review_configs'][index],
                             0, '11min', '2s', 4 << 30, 128, '5s')
        if previous_review_end is not None:
            assert previous_review_end < native_scope['start_monotonic_us']
        previous_review_end = review_scope['end_monotonic_us']
        if index == 3:
            assert mathscope['end_monotonic_us'] < native_scope['start_monotonic_us']
        measurement = report['timing_analysis']
        assert measurement['active_duration_ns'] == proof['active_duration_ns']
        assert measurement['accepted_frames'] == proof['active_accepted_frames']
        assert measurement['fixed_stratum']['count'] == proof['fixed_stratum_call_count']
        assert measurement['fixed_stratum']['median_thread_CPU_ns_twice'] == proof['fixed_stratum_median_CPU_ns_twice']
        for pin in (measurement['original_active_frame_report'], measurement['original_timing_report']):
            h.checked(pin)
        measurements[name] = measurement
        validated.append(dict(case=name, closeout=casepin, independent_report=proof['independent_report'],
            native_scope=native_scope, worker_scope=worker_scope, independent_review_scope=review_scope))
    assert len(all_sessions) == len(set(all_sessions)) == 256
    decision = comparator.compare(measurements, design)
    lease = design['common_runtime']['lease']; h.checked(lease)
    fd = os.open(lease['path'], os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    for port in (19998, *range(20000, 20032)):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    gpu = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory', '--format=csv,noheader'], capture_output=True, text=True, timeout=10)
    assert gpu.returncode == 0 and design['common_runtime']['gpu_uuid'] not in gpu.stdout
    h.checked(job['main_monitor'])
    process = subprocess.run(['/usr/bin/python3.12', '-I', '-B', job['main_monitor']['path']], capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr
    main = json.loads(process.stdout)
    assert main['client_count'] == 192 and main['held_inputs'] == 197
    for pin in job['inputs']:
        h.checked(pin)
    output.mkdir(mode=0o700)
    passed = decision['both_independent_B_gates_passed']
    reportpin = h.put(output / 'report.json', dict(
        schema='robotron-selector-active600-original-final-comparison-report-v1',
        status='ENGINEERING_GATES_PASSED_ISOLATED_SELECTOR_SUPPORTED' if passed else 'ENGINEERING_GATES_FAILED_NO_DEPLOYMENT',
        original_job=h.pin(args.job), fixed_design=job['design'], all_four_originals_valid=True,
        case_evidence=validated, exact_math_guard_scope=mathscope, decision=decision,
        original_order_and_no_overlap_verified=True, all256_session_connection_ids_distinct=True,
        current_private_resources_free=True, current_main=main,
        engineering_only=True, source_installed=False, scientific_case=False, quality_qualified=False,
        policy_promoted=False, main_runtime_changed=False, learning_speed_gain_verified=False,
        useful_training_throughput_gain_verified=False, created_unix_s=time.time()))
    print(json.dumps(dict(report=reportpin, engineering_gates_passed=passed)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
