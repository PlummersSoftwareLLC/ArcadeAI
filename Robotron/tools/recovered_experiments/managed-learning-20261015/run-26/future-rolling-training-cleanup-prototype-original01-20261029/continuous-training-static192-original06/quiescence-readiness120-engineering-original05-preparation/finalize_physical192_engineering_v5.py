"""Root-only closed-metadata joins; no imports of runtime or scientific code.

The three original scopes must already have passed their exact independent
closer. This program never probes, releases, retries, replays raw samples, or
qualifies private policy quality. It records the observed engineering domain.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
ENG = HERE
MODE_ROOT = HERE.parent
HC = MODE_ROOT/'health-consumer-live-pidfd-current-EVAL-quiescence-original05'
FAMILY_SHA = '22245530f82299b2a3f634d07ba828a91678dc67a6ad5bd869a780d6d4a62651'
MAP_SHA = 'c8231a36c0028567a6a7da884046aa98ceeaf0fc6f0c338e4230fd305fb7e553'
PREPARE_SHA = 'd82dae95ae6eff723a414fceb9afc8918feee636cc250ef88ffd4915387c9ef7'
PROBE_SHA = 'bde9dd42392434476e1515d2650092b0a1abf1f1cfe078a2255247cf02bbfb04'
CLOSE_SHA = '8f812f5cefb8e4e77182062bfb73f77e48598279508dc2d8c2de5c2a8500b026'
REVIEW_SHA = '30ea4d2eb6d97b5ccbd04e262f7b4c45e47af268f7644f7893ad88deba47a133'
MODES = ('warmup','long','abort')
LIMIT = 16 << 20


def require(value, reason):
    if not value:
        raise ValueError(reason)


def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)),uid=info.st_uid,nlink=info.st_nlink)


def pin(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(),
            'Canonical closed metadata/source path required')
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before = identity(os.fstat(fd))
        require(stat.S_ISREG(os.fstat(fd).st_mode) and 0 <= before['bytes'] <= LIMIT,
                'Bounded regular metadata/source required')
        with os.fdopen(os.dup(fd),'rb') as stream:
            raw = stream.read(LIMIT+1)
        require(identity(os.fstat(fd)) == before and identity(path.lstat()) == before
                and len(raw) == before['bytes'],'Selected metadata changed while reading')
    finally:
        os.close(fd)
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)


def read(value, *, immutable=True):
    require(type(value) is dict and set(value) == {'path','sha256','bytes','identity'}
            and set(value['identity']) == {'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'},
            'Exact full8 selected metadata pin required')
    require(pin(value['path']) == value and value['identity']['uid'] == os.getuid()
            and value['identity']['nlink'] == 1
            and (not immutable or value['identity']['mode'] == '0o444'),
            'Selected closed metadata identity/SHA/mode differs')
    raw = Path(value['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == value['sha256'] and pin(value['path']) == value,
            'Selected closed metadata changed')
    return json.loads(raw)


def put(path, body):
    raw = (json.dumps(body,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    require(len(raw) <= LIMIT, 'Bounded final metadata required')
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    directory = os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return pin(path)


def finalize(job_path, job_sha, source_sha):
    own = pin(Path(__file__).resolve())
    require(own['sha256'] == source_sha and own['identity']['mode'] == '0o444',
            'Exact frozen Root-selected finalizer required')
    job_pin = pin(job_path);require(job_pin['sha256'] == job_sha,'Root job SHA differs')
    job = read(job_pin)
    require(job['schema'] == 'robotron-root-finalize-original192-immutable-bootstrap-live-pidfd-engineering-job-v4'
            and set(job) == {'schema','prepared_contexts','launch_index','case','closeouts','output'}
            and set(job['closeouts']) == set(MODES),'Exact three-scope Root selection required')
    prepared = read(job['prepared_contexts']); index = read(job['launch_index']); case = read(job['case'])
    require(prepared['schema'] == 'robotron-original192-immutable-bootstrap-live-pidfd-three-engineering-preparation-v4'
            and prepared['status'] == 'DATA_PREPARED_NOT_LAUNCHED'
            and prepared['source']['sha256'] == PREPARE_SHA
            and pin(prepared['source']['path']) == prepared['source']
            and prepared['case'] == job['case']
            and index['schema'] == 'robotron-original192-immutable-bootstrap-live-pidfd-three-original-launches-v4'
            and len(index['records']) == 3
            and case['schema'] == 'robotron-original192-live-pidfd-current-eval-quiescence-case-v5',
            'Exact actual NEW static case/preparation/index required')
    family = prepared['source_family']; source_map = prepared['source_map']
    require(family['sha256'] == FAMILY_SHA and source_map['sha256'] == MAP_SHA,
            'Frozen static8 family/map differs')
    read(family); mapped = read(source_map)['observer_sources']
    require(mapped == prepared['observer_sources'] and len(mapped) == 8
            and set(mapped) == {'client','worker','health','health_base','registry','durability','control','interpreter'},
            'Exact static8 observer map required')
    inventory_pin = case['input_inventory_authority']; inventory = read(inventory_pin)
    parent = read(inventory['parent_case'])
    prior_physical = read(inventory['prior_physical_case'])
    immediate_prior = read(inventory['immediate_prior_case'])
    require(inventory['schema'] == 'robotron-root-original192-live-pidfd-current-eval-quiescence-input-inventory-v5'
            and inventory['status'] == 'ROOT_SELECTED_EXACT_HELD_INPUTS'
            and inventory['inputs'] == case['inputs']
            and type(inventory['input_count']) is int and inventory['input_count'] == len(case['inputs'])
            and inventory['source_authority'] == case['continuous']['source_authority']
            and parent['schema'] == 'robotron-round-main-health-case-v1' and len(parent['inputs']) == 247
            and set(parent['inputs']) <= set(case['inputs'])
            and inventory['all_prior348_paths_retained'] is True
            and prior_physical['schema'] == 'robotron-continuous-physical-original192-health-case-v2'
            and len(prior_physical['inputs']) == 348
            and immediate_prior['schema'] == 'robotron-physical-original192-immutable-bootstrap-live-pidfd-health-case-v4'
            and len(immediate_prior['inputs']) == 365 and inventory['all_v4_paths_retained'] is True
            and set(prior_physical['inputs']) <= set(immediate_prior['inputs']) <= set(case['inputs'])
            and inventory['immediate_prior_replacements'] == {p:dict(before=v,after=case['inputs'][p])
                for p,v in immediate_prior['inputs'].items() if v != case['inputs'][p]}
            and inventory['prior348_replacements'] == {p:dict(before=v,after=case['inputs'][p])
                for p,v in prior_physical['inputs'].items() if v != case['inputs'][p]}
            and inventory['replacements'] == {p:dict(before=v,after=case['inputs'][p])
                for p,v in parent['inputs'].items() if v != case['inputs'][p]}
            and inventory['added_inputs'] == {p:v for p,v in case['inputs'].items() if p not in parent['inputs']},
            'Exact held inventory/historical247 transitions differ')
    readiness_parent_pin = inventory['readiness120_parent_case']
    readiness_inventory_pin = inventory['readiness120_parent_inventory']
    readiness_parent = read(readiness_parent_pin); readiness_inventory = read(readiness_inventory_pin)
    overlay = case['observer_client_readiness_overlay']
    require(readiness_parent_pin['sha256'] == '95a87d6b9f4112970a8dd3e46dc5ee8b20316514d433592835cd5c962cdbfec6'
            and readiness_inventory_pin['sha256'] == 'cb87a6cdbad00b5ec35139fb7e01089cc2b915839be1118793b8b81e5f41b826'
            and readiness_parent['schema'] == case['schema'] and len(readiness_parent['inputs']) == 382
            and readiness_parent['input_inventory_authority'] == readiness_inventory_pin
            and readiness_inventory['inputs'] == readiness_parent['inputs']
            and inventory['all_prior382_paths_retained'] is True and inventory['prior382_replacements'] == {}
            and set(readiness_parent['inputs']) <= set(case['inputs'])
            and all(case['inputs'][p] == v for p,v in readiness_parent['inputs'].items())
            and overlay['schema'] == 'robotron-HC5-client-readiness120-case-overlay-v1'
            and overlay['parent_case'] == readiness_parent_pin and overlay['parent_inventory'] == readiness_inventory_pin
            and overlay['family'] == family and overlay['source_map'] == source_map
            and overlay['client'] == mapped['client'] and overlay['initial_samples'] == 100
            and overlay['readiness_wait_s'] == 120 and overlay['case_profile_and_protocol_unchanged'] is True,
            'Exact unchanged HC5 parent382 and client-only readiness120 overlay required')
    reviewed_source = prepared['observer_reviewer']
    require(reviewed_source['sha256'] == REVIEW_SHA,'Selected actual static raw reviewer differs')
    require(pin(reviewed_source['path']) == reviewed_source,'Selected frozen reviewer source changed')
    result = {}; parent_births = set(); worker_births = set()
    for mode in MODES:
        records = [r for r in index['records'] if r['kind'] == 'main-current-once-EVAL-quiescence192' and r['mode'] == mode]
        intents = [r for r in prepared['records'] if r['kind'] == 'main-current-once-EVAL-quiescence192' and r['mode'] == mode]
        require(len(records) == len(intents) == 1, 'One exact original per mode required')
        record = records[0]; intent = read(record['intent']); expected = intents[0]
        require(record['intent'] == expected['intent'] and record['unit'] == expected['unit']
                and record['output'] == expected['output'] and intent['case'] == job['case']
                and intent['attempt'] == 1 and type(intent['attempt']) is int
                and intent['no_retry'] is True and intent['engineering_only'] is True,
                'Original mode/intent/no-retry case join differs')
        owner = read(record['original_live_owner']); close_pin = job['closeouts'][mode]; close = read(close_pin)
        require(close['schema'] == 'robotron-original192-immutable-bootstrap-live-pidfd-original-engineering-closeout-v4'
                and close['status'] == 'PASS_ENGINEERING_ONLY' and close['kind'] == 'main-current-once-EVAL-quiescence192'
                and close['mode'] == mode and close['launch_index'] == job['launch_index']
                and close['original_live_owner'] == record['original_live_owner']
                and close['source']['sha256'] == CLOSE_SHA
                and pin(close['source']['path']) == close['source']
                and type(close['original_parent_actual_exit']) is int and close['original_parent_actual_exit'] == 0
                and type(close['worker_actual_exit']) is int and close['worker_actual_exit'] == (1 if mode == 'abort' else 0)
                and close['all_original_births_units_cgroups_and_tmpfs_control_absent'] is True
                and close['actual_parent_CPU_cores'] == 2 and close['actual_parent_memory_bytes'] == 4<<30
                and close['actual_parent_runtime_s'] == (1800 if mode == 'long' else 780)
                and close['scientific_qualification'] is close['quality_qualified'] is close['promotion'] is False,
                'Actual original independent closer/exit/resources/release differs')
        terminal = read(close['parent_terminal']); stopped = read(close['owned_stop'])
        require(owner['unit'] == record['unit'] and terminal['InvocationID'] == owner['invocation_id']
                and terminal['ExecMainPID'] == str(owner['pid']) and terminal['ExecMainCode'] == '1'
                and terminal['ExecMainStatus'] == '0' and terminal['NRestarts'] == '0'
                and terminal['Restart'] == 'no' and close['released_properties']['LoadState'] == 'not-found'
                and stopped['argv'] == ['systemctl','--user','stop',owner['unit']]
                and stopped['returncode'] == 0,'Original parent terminal/owned-release evidence differs')
        pair = (owner['pid'],owner['birth'])
        require(pair not in parent_births,'Reused original parent handle');parent_births.add(pair)
        report = read(close['actual_probe_result'])
        require(report['schema'] == 'robotron-original192-immutable-bootstrap-live-pidfd-health-interface-probe-v4'
                and report['status'] == 'PASS_ENGINEERING_INTERFACE_ONLY' and report['mode'] == mode
                and report['sources'] == mapped and report['retired_API_reviewer_source'] == reviewed_source
                and report['observer_lifecycle'] == close['worker_lifecycle']
                and report['case_inventory_authority'] == inventory_pin
                and report['proof_gap_contract'] == 'robotron-main-proof-gap-2s-v1'
                and report['maximum_gap_s'] == 2.0
                and report['main_health_profile'] == 'PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
                and report['simultaneous192_actors_claimed'] is False
                and report['main_runtime_changed'] is report['private_policy_or_GPU_loaded']
                    is report['scientific_launch_qualified'] is report['quality_qualified'] is False,
                'Actual source-bound probe domain differs')
        if mode == 'long':
            require(report['long_work_contract'] == close['long_work_contract']
                        == 'MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S'
                    and report['long_minimum_work_s'] == 600 and report['long_maximum_work_s'] == 1200
                    and report['long_minimum_observed_samples'] == 3000
                    and type(report['actual_long_work_s']) in (int,float)
                    and 600 <= report['actual_long_work_s'] == close['actual_long_work_s'] <= 1200
                    and type(report['last_validated_long_count']) is int
                    and report['last_validated_long_count'] == close['last_validated_long_count'] >= 3000,
                    'FRESH long lacks both sustained600s and validated3000 samples within1200s')
        native = read(report['original_job']); lifecycle = read(close['worker_lifecycle'])
        worker = read(lifecycle['worker_job']); outcome = read(lifecycle['outcome'])
        worker_owner = read(outcome['owner']); worker_terminal = read(lifecycle['terminal_properties'])
        require(native['runtime']['sha256'] == PROBE_SHA and pin(native['runtime']['path']) == native['runtime']
                and native['main_binding'] == job['case']
                and lifecycle['native_job'] == report['original_job']
                and worker['native_job'] == report['original_job'] and worker['native_runtime'] == native['runtime']
                and worker['case'] == job['case'] and worker['sources'] == mapped
                and worker['parent']['pid'] == owner['pid'] and worker['parent']['birth'] == owner['birth']
                and worker['parent']['invocation_id'] == owner['invocation_id']
                and worker['schema'] == 'robotron-original192-live-pidfd-current-eval-quiescence-observer-proof2s-job-v5'
                and worker['immutable_original192_bootstrap_certificate'] is True
                and worker['fresh_original_keeper_pidfd_census'] is True
                and worker['source_bound_current_once_only_EVAL_quiescence_after_recorded_disconnect_exception'] is True
                and worker['maximum_gap_s'] == 2.0 and worker['interval_s'] == .2
                and worker['initial_samples'] == 100 and worker['work_s'] == 4200 and worker['runtime_s'] == 4260
                and worker['attempt'] == 1 and worker['no_retry'] is True,
                'Actual native/worker/parent/case/source/proof contract differs')
        wp = (worker_owner['pid'],worker_owner['birth'])
        require(wp not in worker_births,'Reused original worker handle');worker_births.add(wp)
        require(lifecycle['all_original_processes_reaped'] is lifecycle['original_scope_released']
                    is lifecycle['launcher_birth_absent'] is True
                and outcome['all_writer_threads_stopped'] is True and outcome['uncommitted_raw'] == []
                and outcome['queued_samples'] == len(outcome['samples']) == close['accepted_samples']
                and outcome['queued_unaccepted'] == len(outcome['unaccepted']) == close['unaccepted_samples'],
                'Actual raw-queue/worker/launcher closure differs')
        control = read(outcome['control_release'])
        require(control['directory_absent'] is True,'Original tmpfs control release missing')
        raw_pin = None; reviewed = report['independently_replayed_raw_review']
        if mode != 'abort':
            raw_pin = pin(Path(record['output'])/'runtime/independent-raw-review.json')
            require(read(raw_pin) == reviewed and reviewed['status'] == 'PASS'
                    and reviewed['lifecycle'] == close['worker_lifecycle']
                    and reviewed['original_job'] == lifecycle['worker_job']
                    and reviewed['original_sources'] == mapped
                    and reviewed['accepted_samples'] == close['accepted_samples'] >= (3000 if mode == 'long' else 101)
                    and reviewed['full_main_input_count'] == len(case['inputs'])
                    and reviewed['proof_gap_contract'] == 'robotron-main-proof-gap-2s-v1'
                    and reviewed['verified_maximum_gap_s'] == 2.0
                    and reviewed['main_health_profile'] == 'PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5'
                    and reviewed['original_cleanup_deadline_handoff_CID_reuse_or_refill_success_from_exception_claimed'] is False
                    and all(reviewed[k] is True for k in ('source_bound_original192_physical_bootstrap_verified',
                        'TRAIN155_original_physical_and_current_TCP_verified',
                        'EVAL37_original_connection_and_strict_retirement_evidence_verified',
                        'EVAL_closed_slots_have_positive_normal0_reap_and_cleanup_verified',
                    'prior_completed_EVAL_prefix_and_current_suffix_verified',
                        'immutable_original192_bootstrap_certificate_verified','fresh_original_keeper_pidfd_census_verified',
                        'authentic_published_normal0_exit_facts_and_monotone_coverage_verified','current_once_only_EVAL_quiescence_with_historical_error_and_ready_false_preserved_verified',
                        'accepted_evidence_and_projection_gaps_verified','fresh_final_sample_verified',
                        'queued_publication_byte_joins_verified','actual_resources_and_exit_and_owned_release_verified'))
                    and outcome['success'] is True and outcome['error'] is None and lifecycle['success'] is True
                    and worker_terminal['ExecMainCode'] == '1' and worker_terminal['ExecMainStatus'] == '0',
                    'Actual complete source-bound independent raw review missing')
        else:
            require(reviewed is None and outcome['success'] is False and lifecycle['success'] is False
                    and worker_terminal['ExecMainCode'] == '1' and worker_terminal['ExecMainStatus'] == '1',
                    'Expected original worker abort failure was not preserved')
        result[mode] = dict(closeout=close_pin,lifecycle=close['worker_lifecycle'],
            actual_probe_result=close['actual_probe_result'],independent_raw_review=raw_pin,
            accepted_samples=close['accepted_samples'],unaccepted_samples=close['unaccepted_samples'],
            original_parent_actual_exit=0,worker_actual_exit=close['worker_actual_exit'])
    require(len(parent_births | worker_births) == 6,'Original parent and worker identities overlap')
    output = Path(job['output'])
    require(output.is_absolute() and output.parent.resolve(strict=True) == Path(job_path).parent.resolve(strict=True)
            and not output.exists(),'One exclusive Root-selected joint output beside job required')
    return put(output,dict(schema='robotron-original192-immutable-bootstrap-live-pidfd-joint-engineering-readiness-v4',
        status='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY',source=own,job=job_pin,
        source_family=family,observer_sources=mapped,observer_reviewer=reviewed_source,
        case=job['case'],input_inventory_authority=inventory_pin,historical_main_input_count=247,
        actual_held_input_count=len(case['inputs']),engineering=result,
        lifecycle=result['long']['lifecycle'],independent_raw_review=result['long']['independent_raw_review'],
        proof_gap_contract='robotron-main-proof-gap-2s-v1',maximum_gap_s=2.0,interval_s=.2,
        main_health_profile='PHYSICAL_ORIGINAL192_LIVE_PIDFD_CURRENT_EVAL_QUIESCENCE_V5',
        current_once_only_EVAL_quiescence_with_historical_error_and_ready_false_preserved_verified=True,
        original_cleanup_deadline_handoff_CID_reuse_or_refill_success_from_exception_claimed=False,
        admission_basis='EVER_BOUND_ORIGINAL192_NOT_SIMULTANEOUS',simultaneous192_actors_claimed=False,
        all_original_engineering_scopes_closed_at_recorded_closer=True,
        all_three_modes_are_fresh_originals_for_this_physical_case=True,
        old_static_or_countbounded_failures_reused_or_requalified=False,
        long_work_contract='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S',
        raw_predicates_replayed_by_this_finalizer=False,fresh_runtime_or_resource_probe_performed=False,
        old_invalid_studies_or_old_whole_round_engineering_requalified=False,
        private_frozen_policy_CPU_or_study_guard_qualified=False,
        scientific_launch_qualified=False,quality_qualified=False,promotion=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--finalize',action='store_true');p.add_argument('--job',type=Path)
    p.add_argument('--job-sha256');p.add_argument('--expected-source-sha256')
    a = p.parse_args()
    if not a.finalize:
        print('PLAN_ONLY_NO_READS_OUTPUTS_IMPORTS_PROBES_OR_ACTIONS');return
    print(json.dumps(finalize(a.job,a.job_sha256,a.expected_source_sha256)),flush=True)


if __name__ == '__main__':
    main()
