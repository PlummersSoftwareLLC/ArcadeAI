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
    require(path.stat().st_size <= 64 << 20, 'Closed evidence exceeds review bound')
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
    require(job['schema'] == 'robotron-continuous-physical-original192-observer-proof2s-job-v2', 'Wrong declared observer protocol version')
    require(job['interval_s'] == .2 and job['initial_samples'] == 100 and job['maximum_gap_s'] == 2.0
            and job['work_s'] == 4200 and job['runtime_s'] == 4260 and job['attempt'] == 1
            and job['no_retry'] is True, 'Observer bounds or original attempt differ')
    require(job.get('source_bound_retired_API_projection') is True
            and job.get('source_bound_original192_physical_bootstrap') is True
            and job.get('source_bound_physical_original192_partition') is True
            and set(job['sources']) == {'client','worker','health','health_base','registry','durability','control','interpreter'}
            and job['sources']['health_base'] == h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-physical-original192-v4-cohort-original03/continuous_physical192_health_v3.py'))
            and job['sources']['registry'] == h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-physical-original192-v4-cohort-original03/continuous_physical192_registry_v3.py'))
            and job['sources']['health'] == h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-physical-original192-v4-cohort-original03/continuous_physical192_transport_v3.py')),
            'Exact source-bound physical original192 observer dependencies required')
    require(lifecycle['native_deadline_monotonic_s'] == job['deadline_monotonic_s']
            == lifecycle['native_started_monotonic_s'] + 4200, 'Native time bound differs')
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
        MemoryMax=str(4 << 30), MemorySwapMax='0', TasksMax='128', RuntimeMaxUSec='1h 11min',
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
    require(outcome['schema'] == 'robotron-round-observer-outcome-v2'
            and outcome['uncommitted_raw'] == []
            and outcome['queued_samples'] == len(outcome['samples'])
            and outcome['queued_unaccepted'] == len(outcome['unaccepted']), 'Queued original raw coverage differs')
    require(outcome['success'] is True and outcome['error'] is None and outcome['signals_received'] == []
            and outcome['all_writer_threads_stopped'] is True, 'Original observer did not close successfully')
    started = int(terminal['ExecMainStartTimestampMonotonic']) / 1e6
    ended = int(terminal['ExecMainExitTimestampMonotonic']) / 1e6
    require(0 < started < ended and ended-started <= 4260, 'Actual observer elapsed time differs')
    health = h.load('_closed_round_observer_health', h.checked(job['sources']['health']))
    case = read(job['case'], h)
    health.check_inputs(case, full=True)
    require(100 <= len(outcome['samples']) <= 22000, 'Original sample count exceeds selected time bound')
    durable = h.load('_closed_bounded_raw_durability', h.checked(job['sources']['durability']))
    durability_records = []
    previous = None
    records = []
    last_advance = started
    for index, value in enumerate(outcome['samples']):
        row = read(value, h)
        require(row['index'] == index and row['job'] == job_pin and row['nonce'] == job['nonce']
                and row['owner'] == owner, 'Raw sample index or original identity differs')
        descriptor = dict(row['durability_record'], record=value)
        require(descriptor['kind'] == 'sample' and descriptor['index'] == index, 'Durable sample descriptor differs')
        durability_records.append(descriptor)
        sample = row['snapshot']
        wire = sample['raw_API_wire'].encode('utf-8')
        require(hashlib.sha256(wire).hexdigest() == sample['api_wire_sha256']
                and json.loads(wire) == sample['api'], 'Raw API does not join parsed accepted snapshot')
        require(started <= sample['monotonic_s'] <= outcome['ended_monotonic_s'] <= ended,
                'Accepted sample is outside the actual original worker lifetime')
        health.validate(case, sample, previous=previous)
        if previous is not None:
            require(0 <= sample['monotonic_s']-previous['monotonic_s'] <= job['maximum_gap_s'], 'Accepted main evidence gap exceeds2s')
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
        require(publication['index'] == index and 0 <= publication['updated_monotonic_s']-records[index]['monotonic_s'] <= job['maximum_gap_s'],
                'Running projection source age exceeds2s')
        pin = outcome['samples'][index]
        require(0 < pin['bytes'] <= 8 << 20
                and publication['queued_raw'] == dict(sequence=durability_records[index]['sequence'],
                    sha256=pin['sha256'], bytes=pin['bytes']), 'Queued publication bytes differ from durable raw sample')
        preceding = started if index == 0 else publications[index-1]['updated_monotonic_s']
        require(0 <= publication['updated_monotonic_s']-preceding <= job['maximum_gap_s'], 'Running projection gap exceeds2s')
    for index, retry in enumerate(outcome['unaccepted']):
        row = read(retry, h)
        descriptor = dict(row['durability_record'], record=retry)
        require(descriptor['kind'] == 'unaccepted' and descriptor['index'] == index, 'Durable retry descriptor differs')
        durability_records.append(descriptor)
    durability_records.sort(key=lambda row: row['sequence'])
    chain = sample_chain = durable.EMPTY_CHAIN
    sample_count = 0
    initial_prefix = None
    for sequence, descriptor in enumerate(durability_records):
        require(descriptor['sequence'] == sequence, 'Raw durability sequence missing or duplicated')
        chain = durable.advance(chain, descriptor)
        if descriptor['kind'] == 'sample':
            sample_count += 1
            sample_chain = durable.advance(sample_chain, descriptor)
            if sample_count == 100:
                initial_prefix = dict(chain=chain, sample_chain=sample_chain, committed_records=sequence+1)
    binding = dict(job=job_pin, nonce=job['nonce'], owner=owner)
    seal = read(outcome['durability_seal'], h)
    require(seal['schema'] == 'robotron-buffered-raw-final-seal-v2' and seal['binding'] == binding
            and seal['committed_records'] == len(durability_records) and seal['sample_count'] == len(records)
            and seal['chain'] == chain and seal['sample_chain'] == sample_chain
            and seal['readiness'] == outcome['initial']['durable_prefix']
            and seal['all_writer_threads_stopped'] is True and seal['queue_capacity'] == 128
            and 0 < seal['queue_high_water'] <= 128 and seal['byte_capacity'] == 128 << 20
            and 0 < seal['bytes_high_water'] <= 128 << 20
            and records[-1]['monotonic_s'] <= seal['sealed_monotonic_s'] <= outcome['ended_monotonic_s'],
            'Final durable coverage, joined writer or original binding differs')
    prefix = read(seal['readiness'], h)
    require(prefix['schema'] == 'robotron-buffered-raw-readiness-v2' and prefix['binding'] == binding
            and prefix['sample_count'] == 100
            and all(prefix[key] == value for key, value in initial_prefix.items())
            and records[99]['monotonic_s'] <= prefix['committed_monotonic_s']
            <= outcome['initial']['durable_ready_monotonic_s'] < records[-1]['monotonic_s'],
            'Initial100 durable raw prefix does not replay')
    control = h.load('_closed_original_tmpfs_control', h.checked(job['sources']['control']))
    control_owner = read(outcome['control_owner'], h)
    release = read(outcome['control_release'], h)
    final_live = read(outcome['final_live'], h)
    require(job['raw_queue_protocol'] == 'pending-byte-digest-v2'
            and job['live_control_path'] == str(control.path_for(job['nonce']))
            and control_owner['schema'] == 'robotron-owned-volatile-live-directory-v1'
            and control_owner['path'] == job['live_control_path']
            and control_owner['identity']['device'] == Path('/dev/shm').stat().st_dev
            and control_owner['identity']['uid'] == os.getuid() and control_owner['identity']['mode'] == '0o700'
            and control_owner['binding'] == binding
            and control_owner['volatile_not_scientific_raw_evidence'] is True,
            'Original tmpfs directory/nonce/owner binding differs')
    require(release['schema'] == 'robotron-owned-volatile-live-release-v1'
            and release['original'] == control_owner and release['directory_absent'] is True
            and not Path(job['live_control_path']).exists()
            and {row['name'] for row in release['removed_files']} <= {'live.json','live.next'}
            and all(row['identity']['uid'] == os.getuid() and row['bytes'] <= 128 << 10
                    for row in release['removed_files'])
            and outcome['final_live']['path'] == str(Path(job['output'])/'final-live.json')
            and release['last_publication']['value'] == final_live
            and release['last_publication']['sha256'] == outcome['final_live']['sha256']
            and release['last_publication']['bytes'] == outcome['final_live']['bytes'],
            'Original volatile projection copy or exact owned release differs')
    entry = final_live['latest_sample']
    last_index = len(records)-2
    require(final_live['schema'] == 'robotron-round-observer-live-v2'
            and final_live['job'] == job_pin and final_live['nonce'] == job['nonce']
            and final_live['owner'] == owner and final_live['control'] == control_owner
            and final_live['state'] == 'running' and final_live['initial'] == outcome['initial']
            and final_live['observed_samples'] == len(records)-1
            and final_live['updated_monotonic_s'] == publications[-1]['updated_monotonic_s']
            and entry == dict(schema='robotron-queued-raw-record-v2', kind='sample', index=last_index,
                path=outcome['samples'][last_index]['path'], **publications[-1]['queued_raw']),
            'Final volatile projection does not join its final running publication and durable sample')
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
        main_health_profile='PHYSICAL_ORIGINAL192_TRAIN_CURRENT_TCP_EVAL_ORIGINAL_ONCE',
        source_bound_original192_physical_bootstrap_verified=True,
        TRAIN155_original_physical_and_current_TCP_verified=True,
        EVAL37_original_connection_and_strict_retirement_evidence_verified=True,
        EVAL_closed_slots_have_positive_normal0_reap_and_cleanup_verified=True,
        prior_completed_EVAL_prefix_and_current_suffix_verified=True,
        lifecycle=lifecycle_pin, original_job=job_pin, original_unit=job['unit'],
        original_sources=job['sources'], accepted_samples=len(records),
        raw_API_and_TCP_and_retirement_snapshots_replayed=True,
        hundred_sample_readiness_verified=True, proof_gap_contract='robotron-main-proof-gap-2s-v1', verified_maximum_gap_s=job['maximum_gap_s'], accepted_evidence_and_projection_gaps_verified=True, fresh_final_sample_verified=require_final_sample,
        actual_resources_and_exit_and_owned_release_verified=True,
        first_accepted_monotonic_s=records[0]['monotonic_s'],
        initial_qualified_monotonic_s=outcome['initial']['durable_ready_monotonic_s'],
        bounded_writer_all_raw_records_durable_and_joined=True, durability_seal=outcome['durability_seal'],
        queued_publication_byte_joins_verified=True, original_tmpfs_control_released=True,
        control_release=outcome['control_release'],
        last_accepted_monotonic_s=records[-1]['monotonic_s'],
        full_main_input_count=len(case['inputs']), scientific_launch_qualified=False, quality_qualified=False)
