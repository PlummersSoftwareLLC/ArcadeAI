"""Close one original engineering payload and prepare, never launch, its CPU review."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import fcntl
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
N = R / 'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025'
E = N / 'selector-active600-counterbalanced-engineering-original01'


def load(path, name, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--case', choices=['02-B1-proposal', '03-B2-proposal', '04-A2-baseline'])
    parser.add_argument('--observed-original-session', type=int)
    parser.add_argument('--observed-original-exit', type=int)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY'); return 0
    assert args.observed_original_session > 0 and args.observed_original_exit == 1
    h = load(G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py', '_close_h',
             '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader = load(G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py', '_close_reader',
                  'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    arc = load(G / 'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py', '_close_arc',
               '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
    cpu = load(G / 'tools/training_connection_lifecycle_proposal_20261023/control_owned_health_CPU660_v2.py', '_close_cpu',
               'a524ebb3be864bb03f13fff0af471782b2c6497c321da38ff83b679934cd03d1')
    def read(pin, as_json=True):
        return reader.read_pin(pin, as_json=as_json)
    summarypin = h.pin(E / 'all-four-initializer-closeouts-and-qualified-original-launch-configs.json')
    assert summarypin['sha256'] == '82c1227a1b9bd05dd5f75361b6aa77211d359d8ae36988e3c70a3b77c36f941e'
    records = read(summarypin)['cases']
    record = next(row for row in records if row['case'] == args.case)
    directory = E / args.case
    jobpin = record['native_job']; job = read(jobpin); config = read(record['launch_config'])
    ownerpin = h.pin(directory / 'execution-original01/root-original-identity.json'); owner = read(ownerpin)
    closurepin = h.pin(directory / 'execution-original01/root-original-result-and-owned-release.json')
    closure = read(closurepin)
    fields = arc.archived_closure(closure, owner, read, exit_zero=False)
    assert closure['original_exit'] == 1
    for key, value in dict(Id=owner['unit'], InvocationID=owner['invocation_id'], ExecMainPID=str(owner['pid']),
        ExecMainCode='1', ExecMainStatus='1', CPUQuotaPerSecUSec='12s', MemoryMax=str(16 << 30),
        MemorySwapMax='0', RuntimeMaxUSec='6h 11min', TasksMax='512', TimeoutStopUSec='30s',
        KillMode='mixed', SendSIGKILL='no', Restart='no', NRestarts='0').items():
        assert fields[key] == value, (key, fields[key])
    command = '/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR=' + str(Path(config['output']) / 'tmp') + ' ' + ' '.join(config['argv'])
    assert command + ' ; ignore_errors=no ;' in fields['ExecStart']
    control = load(Path(record['native_controller']['path']), '_close_native_control', record['native_controller']['sha256'])
    assert control.checked_config(record['launch_config']['path']) == config
    for pin in config['pins']:
        assert control.pin(pin['path']) == pin
    for unit in (owner['unit'], owner['timer']):
        assert control.show(unit)['LoadState'] == 'not-found'
    proc = Path('/proc', str(owner['pid']), 'stat')
    assert not proc.exists() or int(proc.read_text().rsplit(')', 1)[1].split()[19]) != owner['starttime_ticks']
    cgroup = fields.get('ControlGroup', '')
    assert not cgroup or not (Path('/sys/fs/cgroup' + cgroup) / 'cgroup.procs').exists() or not (Path('/sys/fs/cgroup' + cgroup) / 'cgroup.procs').read_text().strip()
    resultpin = h.pin(Path(job['output']) / 'result.json'); result = read(resultpin)
    assert result['errors'][0] == "ValueError('PRECOMMITTED_ACTIVE600_SELECTOR_LOAD_STOP_NOT_A_QUALITY_RESULT')"
    assert len(result['errors']) == 33
    slots = []
    for error in result['errors'][1:]:
        match = re.fullmatch(r"Original slot([0-9]+): ValueError\('(Original origin client disappeared|Original startup connection ended during a frame)'\)", error)
        assert match, error
        slots.append(int(match[1]))
    assert sorted(slots) == list(range(4096, 4128))
    assert result['all_original_threads_stopped'] is result['original_lease_released'] is result['immutable_inputs_unchanged'] is True
    assert result['main_health_failure'] is None
    assert len(result['original_slots']) == 32 and all(row['actual_exit'] == 0 and row['outputs_sealed_after_original_writer_closure'] is True for row in result['original_slots'].values())
    reaped = result['original_post_origin_child_reap']
    assert reaped['all_original_children_reaped'] is True and reaped['signals_sent'] is reaped['exit_statuses_normalized'] is False
    family = read(job['source_family_manifest']); protocol = read(job['main_health_protocol'])
    verifier = load(Path(family['main_observer']['reviewer']['path']), '_close_worker_verifier', family['main_observer']['reviewer']['sha256'])
    checked = verifier.verify(job, jobpin, owner, config['argv'], result['main_observer_lifecycle'], protocol, family, [], read, h)
    assert checked['closed_report'] == result['main_health_report']
    rate = read(result['active_frame_rate']); timing = read(result['selector_call_timing'])
    assert rate['midpoint_elapsed_s'] >= 600 and rate['start'] == result['active_start'] and rate['end'] == result['active_end']
    assert timing['all_calls_retained'] is timing['original_method_restored'] is True and timing['overflowed'] is False
    h.checked(job['lease']); fd = os.open(job['lease']['path'], os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    for port in (19998, *range(20000, 20032)):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    gpu = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory', '--format=csv,noheader'], capture_output=True, text=True, timeout=20)
    assert gpu.returncode == 0 and job['gpu_uuid'] not in gpu.stdout
    terminal = dict(schema='robotron-active600-original-native-observer-terminal-closeout-v1',
        status='ORIGINAL_NATIVE1_AND_OBSERVER0_CLOSED_EXPECTED_ENGINEERING_STOP_PENDING_RAW_REVIEW',
        actual_original_tool_session_id=args.observed_original_session, actual_original_tool_exit=1,
        native_job=jobpin, native_result=resultpin, native_owner=ownerpin, native_closure=closurepin,
        native_config=record['launch_config'], actual_native_archives_fields=fields,
        all6_native_descriptors_argv_resources_pins_owner_absence_and_unit_release_verified=True,
        original_observer_independent_review=checked, expected_intentional_stop_and_only32_teardown_errors=True,
        all32_original_actor_exits_zero_and_threads_closed=True, source_pins_unchanged=True,
        private_resources_free=True, GPU_readback=dict(exit=gpu.returncode, stdout=gpu.stdout, stderr=gpu.stderr),
        active_duration_s=rate['midpoint_elapsed_s'], raw_selector_calls=len(timing['rows']),
        raw_main_health_and_startup_and_measurement_review_pending=True, engineering_only=True,
        quality_qualified=False, created_unix_s=time.time())
    terminalpin = h.put(directory / 'independent-original-native-and-observer-owned-terminal-closeout.json', terminal)

    # The already successful A1 reader is the common source, not borrowed data.
    template = E / '01-A1-baseline/independent-original-active600-CPU-original01'
    sourcepin = h.pin(E / 'review_selector_active600_original_v1.py')
    assert sourcepin['sha256'] == '4a349b5db5a0f37dade96ea1cc88bd5e8121955057702da1e80ead567bc02af9'
    helperpin = h.pin(G / 'tools/training_connection_lifecycle_proposal_20261023/analyze_selector_active600_measurements_v1.py')
    assert helperpin['sha256'] == '8535bb675941889076203deff8cfac8982901efb01aa3d9d61932d6c847a33e8'
    review = copy.deepcopy(read(h.pin(template / 'job.json')))
    output = directory / 'independent-original-active600-CPU-original01'
    assert not output.exists()
    output.mkdir(mode=0o700)
    if record['case'] in ('02-B1-proposal', '03-B2-proposal'):
        scientific = read(h.pin(N / 'prepared-source-family-manifest-CPU-validated-v3.json'))
        game_auditor = scientific['games_auditor']
    else:
        game_auditor = read(h.pin(template / 'job.json'))['quota_game_auditor']
    audit = load(Path(game_auditor['path']), '_close_game_descriptor', game_auditor['sha256'])
    drainpin = job['quota64_source_pins']['drain']
    drain = load(Path(drainpin['path']), '_close_drain_descriptor', drainpin['sha256'])
    assert audit.COHORT_SELECTION == drain.COHORT_SELECTION
    assert audit.COHORT_SELECTION['selector_source_sha256'] == job['quota64_source_pins']['view']['sha256']
    review.update(output=str(output / 'output-original01'), native_job=jobpin, native_result=resultpin,
        native_owner=ownerpin, native_closure=closurepin, native_config=record['launch_config'],
        native_controller=record['native_controller'], quota_game_auditor=game_auditor, quota_runtime=drainpin,
        source_family_guard_closeout=record['source_guard_closeout'], original_terminal_readback=terminalpin,
        selector_measurement_reader=helperpin, initializer_closeout=record['initializer_closeout'])
    pins = [value for value in review.values() if isinstance(value, dict) and {'path', 'sha256', 'bytes'} <= value.keys()]
    derivation = h.pin(E / 'independent-active600-review-source-derivation.json')
    review['inputs'] = list({pin['path']: pin for pin in [*job['inputs'], *pins, sourcepin, derivation]}.values())
    reviewpin = h.put(output / 'job.json', review)
    template_config = read(h.pin(template / 'controller-config.json'))
    config = dict(unit='robotron-selector-active600-' + args.case.lower() + '-independent-review-original01-20261025.service',
        output=str(output / 'execution-original01'),
        argv=['/usr/bin/python3.12', '-I', '-B', sourcepin['path'], '--execute', '--job', reviewpin['path'],
              '--job-sha256', reviewpin['sha256'], '--source-sha256', sourcepin['sha256']],
        properties=template_config['properties'], observation_s=template_config['observation_s'],
        pins=[cpu.pin(pin['path']) for pin in [reviewpin, sourcepin, *review['inputs']]])
    configpin = h.put(output / 'controller-config.json', config)
    cpu.checked_config(configpin['path'])
    precommit = h.put(output / 'original-independent-active600-review-precommit.json', dict(
        schema='robotron-active600-original-independent-review-precommit-v1', job=reviewpin, controller=configpin,
        source=sourcepin, source_derivation=derivation, engineering_design=review['engineering_design'],
        decision='Same original full scope/main-health/ROM1200prefix/active600 predicates; no performance comparison until all4 originals valid; no quality claim or retry',
        only_template_source_and_schema_reused=True, current_case_data_bound=True, original_attempt=1, no_retry=True))
    print(json.dumps(dict(native_observer_terminal_closeout=terminalpin, review_config=configpin, precommit=precommit)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
