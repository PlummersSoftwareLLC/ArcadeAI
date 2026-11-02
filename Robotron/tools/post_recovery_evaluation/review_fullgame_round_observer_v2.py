"""Replay a closed observer's raw evidence and independently join its scope."""
import hashlib
import json
import os
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def read(value, h):
    path = h.checked(value)
    require(value['identity']['mode'] == '0o444' and path.stat().st_uid == os.getuid(),
            'Closed evidence is not sealed and owned')
    require(path.stat().st_size <= 128 << 20, 'Closed evidence exceeds review bound')
    return json.loads(path.read_bytes())


def absent(process):
    try:
        birth = int(Path('/proc', str(process['pid']), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return True
    return birth != process['birth']


def verify(lifecycle_pin, h, *, require_final_sample=True):
    lifecycle = read(lifecycle_pin, h)
    require(lifecycle['schema'] == 'robotron-round-observer-native-lifecycle-v1'
            and lifecycle['success'] is True and lifecycle['all_original_processes_reaped'] is True
            and lifecycle['original_scope_released'] is True, 'Original observer lifecycle is incomplete')
    job_pin = lifecycle['worker_job']
    job = read(job_pin, h)
    native = read(lifecycle['native_job'], h)
    require(job['native_job'] == lifecycle['native_job'] and job['native_runtime'] == native['runtime'],
            'Original native/worker job or runtime join differs')
    require(job['schema'] == ('robotron-fullgame-round-observer-job-v1' if require_final_sample
                             else 'robotron-round-observer-job-v1'), 'Wrong declared observer protocol version')
    require(job['interval_s'] == .2 and job['initial_samples'] == 100 and job['maximum_gap_s'] == .5
            and job['work_s'] == 22200 and job['runtime_s'] == 22260 and job['attempt'] == 1
            and job['no_retry'] is True, 'Observer bounds or original attempt differ')
    require(lifecycle['native_deadline_monotonic_s'] == job['deadline_monotonic_s']
            == lifecycle['native_started_monotonic_s'] + 22200, 'Native time bound differs')
    for value in [job['native_runtime'], *job['sources'].values()]:
        h.checked(value)
    unit = read(lifecycle['owner'], h)
    owner = unit['owner']
    require(owner['unit'] == job['unit'] == 'robotron-round-health-' + job['nonce'] + '.service',
            'Original unit is not bound to its nonce')
    terminal = read(lifecycle['terminal_properties'], h)
    expected = dict(Id=job['unit'], InvocationID=owner['invocation_id'],
        ExecMainPID=str(owner['pid']), MainPID='0', ExecMainCode='1', ExecMainStatus='0',
        Result='success', NRestarts='0', Restart='no', CPUQuotaPerSecUSec='2s',
        MemoryMax=str(4 << 30), MemorySwapMax='0', TasksMax='128', RuntimeMaxUSec='6h 11min',
        TimeoutStopUSec='5s', SendSIGKILL='no')
    require(all(terminal[key] == value for key, value in expected.items()), 'Actual worker scope/exit/resources differ')
    original = unit['raw_properties']
    require(original['InvocationID'] == owner['invocation_id'] and original['MainPID'] == str(owner['pid'])
            and original['ControlGroup'] == owner['cgroup'] and original['NRestarts'] == '0',
            'Original live worker scope does not join terminal scope')
    worker_argv = ' '.join([job['sources']['interpreter']['path'], '-I', '-B',
        job['sources']['worker']['path'], '--execute', '--job', job_pin['path'], '--job-sha256', job_pin['sha256']])
    require(worker_argv + ' ; ignore_errors=no ;' in terminal['ExecStart']
            and 'CUDA_VISIBLE_DEVICES=' in terminal['ExecStart'] and '-u LD_PRELOAD -u PYTHONPATH' in terminal['ExecStart'],
            'Actual observer command or CUDA isolation differs')
    outcome = read(lifecycle['outcome'], h)
    require(outcome['job'] == job_pin and outcome['nonce'] == job['nonce'] and outcome['sources'] == job['sources']
            and outcome['parent'] == job['parent'] and read(outcome['owner'], h) == owner,
            'Original outcome identity differs')
    require(outcome['success'] is True and outcome['error'] is None and outcome['signals_received'] == []
            and outcome['all_writer_threads_stopped'] is True, 'Original observer did not close successfully')
    started = int(terminal['ExecMainStartTimestampMonotonic']) / 1e6
    ended = int(terminal['ExecMainExitTimestampMonotonic']) / 1e6
    require(0 < started < ended and ended-started <= 22260, 'Actual observer elapsed time differs')
    health = h.load('_closed_round_observer_health', h.checked(job['sources']['health']))
    case = read(job['case'], h)
    health.check_inputs(case, full=True)
    require(100 <= len(outcome['samples']) <= 112000, 'Original sample count exceeds selected time bound')
    previous = None
    records = []
    last_advance = started
    for index, value in enumerate(outcome['samples']):
        row = read(value, h)
        require(row['index'] == index and row['job'] == job_pin and row['nonce'] == job['nonce']
                and row['owner'] == owner, 'Raw sample index or original identity differs')
        sample = row['snapshot']
        wire = sample['raw_API_wire'].encode('utf-8')
        require(hashlib.sha256(wire).hexdigest() == sample['api_wire_sha256']
                and json.loads(wire) == sample['api'], 'Raw API does not join parsed accepted snapshot')
        require(started <= sample['monotonic_s'] <= outcome['ended_monotonic_s'] <= ended,
                'Accepted sample is outside the actual original worker lifetime')
        health.validate(case, sample, previous=previous)
        if previous is not None:
            require(0 <= sample['monotonic_s']-previous['monotonic_s'] <= .5, 'Accepted main evidence gap exceeds500ms')
        if previous is not None and sample['api']['training_steps'] > previous['api']['training_steps']:
            last_advance = sample['monotonic_s']
        require(sample['monotonic_s']-last_advance < 60, 'Saved evidence has no learner-step progress for60s')
        records.append(dict(monotonic_s=sample['monotonic_s'], unix_s=sample['unix_s']))
        previous = sample
    require(len(records) >= 100 and outcome['initial']['index'] == 99
            and outcome['initial']['unix_s'] == records[99]['unix_s'], 'Original100-sample readiness proof differs')
    publications = outcome['publications']
    require(len(publications) == len(records)-1, 'Running projection publication coverage differs')
    for index, publication in enumerate(publications):
        require(publication['index'] == index and 0 <= publication['updated_monotonic_s']-records[index]['monotonic_s'] <= .5,
                'Running projection source age exceeds500ms')
        preceding = started if index == 0 else publications[index-1]['updated_monotonic_s']
        require(0 <= publication['updated_monotonic_s']-preceding <= .5, 'Running projection gap exceeds500ms')
    for retry in outcome['unaccepted']:
        read(retry, h)
    if require_final_sample:
        request = read(outcome['finish_request'], h)
        require(outcome['finish_request']['path'] == str(Path(job['output']) / 'finish-request.json')
                and request['job'] == job_pin and request['nonce'] == job['nonce']
                and request['parent'] == job['parent'] and request['action'] == 'close',
                'Original finish request join differs')
        require(outcome['final_snapshot_after_finish_request'] is True
                and records[-1]['monotonic_s'] >= outcome['finish_observed_monotonic_s']
                >= request['created_monotonic_s'], 'No fresh final main proof after the original close request')
    launcher_pin = lifecycle.get('launcher') or h.pin(Path(job_pin['path']).parent / 'original-launcher.json')
    launcher = read(launcher_pin, h)
    require(launcher['argv'] == unit['argv'] and lifecycle['launcher_exit'] == 0 and absent(launcher)
            and absent(owner), 'An original observer/launcher birth remains or command differs')
    require(lifecycle['released_properties']['ActiveState'] == 'inactive'
            and lifecycle['released_properties']['MainPID'] == '0'
            and not Path('/sys/fs/cgroup' + owner['cgroup']).exists(), 'Original observer scope remains')
    return dict(schema='robotron-round-observer-independent-raw-review-v1', status='PASS',
        lifecycle=lifecycle_pin, original_job=job_pin, original_unit=job['unit'],
        original_sources=job['sources'], accepted_samples=len(records),
        raw_API_and_TCP_and_retirement_snapshots_replayed=True,
        hundred_sample_readiness_verified=True, legacy_500ms_evidence_and_projection_gaps_verified=True, fresh_final_sample_verified=require_final_sample,
        actual_resources_and_exit_and_owned_release_verified=True,
        first_accepted_monotonic_s=records[0]['monotonic_s'],
        initial_qualified_monotonic_s=records[99]['monotonic_s'],
        last_accepted_monotonic_s=records[-1]['monotonic_s'],
        full_main_input_count=len(case['inputs']), scientific_launch_qualified=False, quality_qualified=False)
