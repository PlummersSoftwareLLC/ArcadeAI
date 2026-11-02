"""Default inert. Join closed engineering artifacts; never launch or probe."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import time

HERE = Path(__file__).resolve().parent
ENGINEERING = HERE.parent
CONTEXTS = ENGINEERING / 'actual-current-main-contexts-original01'
REVISION = ENGINEERING.parent / 'source-family-original01'
ISOLATION = ENGINEERING.parent.parent
LIMIT = 16 << 20
ROLES = {'client','worker','health','health_base','API_projection','round_admission',
         'launcher_census','durability','control','interpreter'}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def read(pin):
    require(type(pin) is dict, 'Actual closed-artifact pin required; future None is not proof')
    path = Path(pin['path'])
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(),
            'Exact canonical closed artifact required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
            and before.st_nlink == 1 and before.st_size <= LIMIT
            and identity(before) == pin['identity'] and before.st_size == pin['bytes'],
            'Closed-artifact full identity or bound differs')
    with path.open('rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Artifact opened another inode')
        raw = stream.read(LIMIT + 1)
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Artifact changed while open')
    require(identity(path.lstat()) == identity(before)
            and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'Artifact bytes changed')
    return json.loads(raw)


def fixed(pin, path, sha):
    require(pin['path'] == str(path) and pin['sha256'] == sha, 'Selected artifact differs')
    return read(pin)


def source_identity(pin):
    path = Path(pin['path'])
    require(path.resolve(strict=True) == path and not path.is_symlink()
            and identity(path.lstat()) == pin['identity'], 'Selected source identity changed')


def mode_evidence(job, mode, record, prepared, family):
    close_pin = job[mode + '_closeout']
    require(close_pin['path'] == str(Path(record['output']) / 'independent-original-engineering-closeout.json'),
            'Another engineering scope closeout was supplied')
    closed = read(close_pin)
    require(closed['schema'] == 'robotron-proof2s-original-engineering-closeout-v1'
            and closed['status'] == 'PASS_ENGINEERING_ONLY' and closed['kind'] == 'deadline'
            and closed['mode'] == mode and closed['launch_index'] == job['launch_index']
            and closed['original_live_owner'] == record['original_live_owner']
            and closed['original_parent_actual_exit'] == 0
            and closed['worker_actual_exit'] == (0 if mode == 'long' else 1)
            and closed['all_original_births_units_cgroups_and_tmpfs_control_absent'] is True
            and closed['actual_parent_CPU_cores'] == 2 and closed['actual_parent_memory_bytes'] == 4 << 30
            and closed['actual_parent_runtime_s'] == 780, 'Actual original engineering closure differs')
    require(closed['source'] == prepared['sources']['close_two_second_engineering_v1.py'],
            'Selected prospective2s owned closer source differs')
    source_identity(closed['source'])
    owner, intent = read(record['original_live_owner']), read(record['intent'])
    terminal, probe = read(closed['parent_terminal']), read(closed['actual_probe_result'])
    require(owner['unit'] == record['unit'] == intent['unit'] == terminal['Id']
            and terminal['ExecMainPID'] == str(owner['pid'])
            and terminal['InvocationID'] == owner['invocation_id']
            and terminal['MainPID'] == '0' and terminal['ExecMainCode'] == '1'
            and terminal['ExecMainStatus'] == '0' and terminal['Result'] == 'success'
            and terminal['NRestarts'] == '0' and terminal['Restart'] == 'no'
            and terminal['CPUQuotaPerSecUSec'] == '2s' and terminal['MemoryMax'] == str(4 << 30)
            and terminal['MemorySwapMax'] == '0' and terminal['TasksMax'] == '128'
            and terminal['RuntimeMaxUSec'] == '13min', 'Original parent identity, exit, or resource bound differs')
    require(probe['status'] == 'PASS_ENGINEERING_INTERFACE_ONLY' and probe['mode'] == mode
            and probe['sources'] == prepared['observer_sources'] == family['observer_sources']
            and probe['retired_API_reviewer_source'] == family['reviewer']
            and all(probe[key] is False for key in ('main_runtime_changed','private_policy_or_GPU_loaded',
                'scientific_launch_qualified','quality_qualified')), 'Probe source map or scope differs')
    require(probe['proof_gap_contract'] == 'robotron-main-proof-gap-2s-v1'
            and probe['maximum_gap_s'] == 2.0, 'Probe uses another observation contract')
    native = read(probe['original_job'])
    lifecycle = read(closed['worker_lifecycle'])
    worker = read(lifecycle['worker_job'])
    outcome = read(lifecycle['outcome'])
    worker_owner = read(outcome['owner'])
    worker_terminal = read(lifecycle['terminal_properties'])
    require(native['main_binding'] == intent['case'] == prepared['case']
            and lifecycle['native_job'] == probe['original_job']
            and probe['observer_lifecycle'] == closed['worker_lifecycle']
            and worker['case'] == prepared['case'] and worker['sources'] == family['observer_sources']
            and outcome['job'] == lifecycle['worker_job'] and outcome['nonce'] == worker['nonce']
            and outcome['parent'] == worker['parent']
            and worker['parent']['pid'] == owner['pid'] and worker['parent']['birth'] == owner['birth']
            and worker['parent']['invocation_id'] == owner['invocation_id'], 'Actual parent, job, case, or ten-map join differs')
    require(worker['schema'] == 'robotron-round-observer-declared-launcher-proof2s-job-v1'
            and worker['interval_s'] == .2 and worker['initial_samples'] == 100
            and worker['maximum_gap_s'] == 2.0, 'Exact prospective2s worker contract required')
    require(all(lifecycle[key] is True for key in ('all_original_processes_reaped',
                'original_scope_released','launcher_birth_absent'))
            and outcome['all_writer_threads_stopped'] is True and outcome['uncommitted_raw'] == []
            and outcome['queued_samples'] == len(outcome['samples']) == closed['accepted_samples']
            and outcome['queued_unaccepted'] == len(outcome['unaccepted']) == closed['unaccepted_samples']
            and worker_terminal['ExecMainPID'] == str(worker_owner['pid'])
            and worker_terminal['InvocationID'] == worker_owner['invocation_id']
            and worker_terminal['MainPID'] == '0' and worker_terminal['ExecMainCode'] == '1'
            and worker_terminal['ExecMainStatus'] == str(closed['worker_actual_exit']), 'Worker or raw writer closure differs')
    release = read(outcome['control_release'])
    require(release['directory_absent'] is True and release['original'] == read(outcome['control_owner'])
            and release['original']['path'] == worker['live_control_path'], 'Original volatile control closure differs')
    if mode == 'long':
        reviewed = probe['independently_replayed_raw_review']
        require(reviewed['status'] == 'PASS' and reviewed['accepted_samples'] >= 3000
                and all(reviewed[key] is True for key in ('queued_publication_byte_joins_verified',
                    'fresh_final_sample_verified','accepted_evidence_and_projection_gaps_verified'))
                and reviewed['proof_gap_contract'] == 'robotron-main-proof-gap-2s-v1'
                and reviewed['verified_maximum_gap_s'] == 2.0
                and outcome['success'] is lifecycle['success'] is True and outcome['error'] is None,
                'Long run lacks actual successful full raw review')
    else:
        request_pin = job['abort_request']
        require(request_pin['path'] == str(Path(record['output'])/'runtime/main-observations/finish-request.json'),
                'Exact original abort request artifact required')
        request = read(request_pin)
        require(probe['independently_replayed_raw_review'] is None
                and outcome['success'] is lifecycle['success'] is False
                and outcome['finish_request'] is outcome['finish_observed_monotonic_s'] is None
                and outcome['final_snapshot_after_finish_request'] is False
                and outcome['error'] == "ValueError('Original parent aborted or never became ready')"
                and outcome['signals_received'] == []
                and request['action'] == 'abort' and request['job'] == lifecycle['worker_job']
                and request['nonce'] == worker['nonce'] and request['parent'] == worker['parent']
                and type(request['created_monotonic_s']) in (int,float)
                and lifecycle['native_started_monotonic_s'] <= outcome['initial']['durable_ready_monotonic_s']
                <= request['created_monotonic_s'] <= outcome['ended_monotonic_s'],
                'Original expected abort disposition differs')
    small = read(job[mode + '_small'])
    require(small['schema'] == 'robotron-proof2s-original-engineering-SMALL-independent-readback-v1'
            and small['status'] == 'PASS_SMALL_ENGINEERING_ONLY'
            and small['mode'] == mode and small['closeout'] == close_pin
            and small['launch_index'] == job['launch_index']
            and small['original_parent_actual_exit'] == 0
            and small['worker_actual_exit'] == closed['worker_actual_exit']
            and small['all_original_births_units_cgroups_and_tmpfs_control_absent'] is True,
            'Independent small readback is not this original closed scope')
    raw_pin = None
    if mode == 'long':
        require(small['original_full_raw_review_PASS_joined_but_not_rerun_by_peer'] is True
                and small['exact_ten_source_map_matches_prepared_and_frozen_family'] is True
                and small['all247_historical_main_inputs_unchanged'] is True,
                'Long independent SMALL/raw source-domain join differs')
        raw_pin = small['independent_raw_review']
        require(read(raw_pin) == reviewed and reviewed['original_sources'] == family['observer_sources']
                and reviewed['lifecycle'] == closed['worker_lifecycle']
                and reviewed['original_job'] == lifecycle['worker_job']
                and reviewed['full_main_input_count'] == 247, 'Actual long full raw review pin differs')
    return dict(closeout=close_pin, independent_small=job[mode + '_small'],
        independent_raw_review=raw_pin,
        actual_parent_exit=0, actual_worker_exit=closed['worker_actual_exit'],
        lifecycle=closed['worker_lifecycle'], accepted_samples=closed['accepted_samples'],
        unaccepted_samples=closed['unaccepted_samples'], full_raw_review_rerun_by_finalizer=False)


def finalize(job):
    require(job['schema'] == 'robotron-proof2s-joint-engineering-finalization-job-v1', 'Wrong job schema')
    own = job['source']
    require(own['path'] == str(Path(__file__).resolve()), 'Another finalizer source selected')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == own['sha256'], 'Finalizer bytes differ')
    source_identity(own)
    index = fixed(job['launch_index'], CONTEXTS/'ROOT-two-original-actual-launches-index-original01.json',
        'b71802fb8abb325c29af3ecc27d9a12b0e2569229619d96430b77ea1963efc53')
    require(index['schema'] == 'robotron-proof2s-two-original-engineering-launches-v1',
            'Actual prospective2s launch index required')
    family = fixed(job['source_family'], REVISION/'prepared-proof2s-observer-sources-NOT-QUALIFIED.json',
        'ab870d1e08ddc27a7ed6456ce4a3be821fc247829c867a94f8c4db96947ff0ef')
    prepared = read(index['preparation'])
    require(index['preparation']['path'] == str(CONTEXTS/'prepared-two-original-observer-contexts-NOT-LAUNCHED.json')
            and prepared['schema'] == 'robotron-proof2s-two-observer-engineering-preparation-v1'
            and prepared['source']['path'] == str(ENGINEERING/'prepare_two_second_engineering_v1.py')
            and prepared['source']['sha256'] == '1ed6c1331b4c67bfb785b9dd0b5e4282de4eac250dcc5651a116c60babf4e05c'
            and prepared['sources']['prepared-proof2s-observer-sources-NOT-QUALIFIED.json'] == job['source_family']
            and set(family['observer_sources']) == ROLES
            and prepared['logical_observer_dependency_count'] == len(family['observer_sources']) == 10
            and prepared['observer_sources'] == family['observer_sources']
            and prepared['original_held_input_count'] == 247 and prepared['held_inputs_unchanged'] is True,
            'Selected family, original247 case, or actual preparation differs')
    for pin in [*family['observer_sources'].values(), family['reviewer'], prepared['source']]:
        source_identity(pin)
    focused = fixed(job['focused_small'], ENGINEERING.parent/'focused-CPU-original01-preparation/actual-focused-CPU-original01/independent-original-CPU-scope-closeout.json',
        '858f4115e41c94af6e8c753b62975ba4eec8114616548030218a7e3a2d6e945e')
    require(focused['schema'] == 'robotron-engineering-original-CPU-independent-closeout-v1'
            and focused['status'] == 'PASS_ENGINEERING_ONLY' and focused['actual_exit'] == 0
            and focused['actual_CPU_cores'] == 2 and focused['actual_memory_bytes'] == 4 << 30
            and focused['actual_runtime_limit_s'] == 180
            and focused['all_six_original_descriptors_and_resources_argv_birth_unit_timer_cgroup_and_owned_release_verified'] is True,
            'Actual focused7 original CPU closure differs')
    require(read(focused['original_closure'])['original_exit'] == 0, 'Focused CPU did not exit0')
    focused_report = read(focused['actual_report']); focused_job = read(focused['original_job'])
    require(focused_report['schema'] == 'robotron-proof2s-focused-original-CPU-report-v1'
            and focused_report['status'] == 'PASS' and focused_report['tests_run'] == 7
            and focused_report['failures'] == focused_report['errors'] == []
            and focused_report['original_job'] == focused['original_job']
            and focused_report['source'] == focused_job['source']
            and focused_report['source']['sha256'] == '047e393b60651c65717a7b5d80ab950bae5a32cc6ebd4ea991c672d54b2ab220'
            and focused_report['fixture'] == focused_job['fixture']
            and focused_report['fixture']['sha256'] == '582bbf8fbf1696becb174338cacc13dc443fe7164b66826280deb2681f9242cd'
            and focused_report['Torch_imported'] is focused_report['GPU_or_MAME_launched'] is False
            and focused_report['admission_TCP_and_live_collection_mocked_not_qualified'] is True
            and focused_report['old_500ms_failed_studies_remain_invalid'] is True,
            'Actual focused7 source/fixture/report scope differs')
    records = {row['mode']:row for row in index['records']}
    require(set(records) == {'long','abort'} and len(index['records']) == 2, 'Exact two original contexts required')
    prepared_records = {row['mode']:row for row in prepared['records']}
    require(set(prepared_records) == {'long','abort'} and len(prepared['records']) == 2,
            'Exact two prepared original contexts required')
    for mode in ('long','abort'):
        require(all(records[mode][key] == prepared_records[mode][key]
                    for key in ('kind','mode','output','unit','intent')),
                'Actual launch differs from the selected original preparation')
    modes = {mode:mode_evidence(job, mode, records[mode], prepared, family) for mode in ('long','abort')}
    old = fixed(job['old192_usage'], ISOLATION/'declared-launcher192-usage-smoke-original01-preparation/prepared-original03/ROOT-independent-original-owned192-usage-closeout.json',
        'b886b608c5bec16c9a46a365109408089b7cba097a61e3f9301b6d993ba29b8d')
    require(old['status'] == 'PASS_USAGE_FIXTURE_ONLY' and old['original_parent_actual_exit'] == 0
            and old['all192_original_Popen_actual_exit0_and_reaped'] is True
            and old['all_original_births_and_own_unit_cgroup_absent'] is True
            and old['forced_cleanup'] is False
            and old['actual_simultaneous192_MAME_or_full500ms_qualified'] is False
            and old['scientific_or_quality_qualified'] is False, 'Historical usage fixture scope differs')
    output = Path(job['output'])
    require(output == CONTEXTS/'independent-proof2s-joint-engineering-qualification-original01.json'
            and not output.exists(), 'Exclusive new qualification output required')
    value = dict(schema='robotron-proof2s-joint-engineering-readiness-v1',
        status='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY', created_unix_s=time.time(),
        source=own, launch_index=job['launch_index'], source_family=job['source_family'],
        proof_gap_contract='robotron-main-proof-gap-2s-v1', maximum_gap_s=2.0,
        focused_small=job['focused_small'], engineering=modes, observer_sources=family['observer_sources'],
        historical_main_input_count=247, old192_usage=dict(closeout=job['old192_usage'],
            all192_original_Popen0_reaped=True, gate192_paired_capture_s=old['gate192_paired_capture_s'],
            sequential_stage_counts=old['actual_peak_sequential_stage_counts'],
            simultaneous192_MAME_or_full500ms_qualified=False),
        current_resource_availability_claimed=False, actual_retired_projection_branch_coverage_not_inferred=True,
        raw_corpus_replayed_by_finalizer=False, old_failed_R1_requalified=False,
        fullgame22200_exact_engineering_qualified=False, scientific_launch_qualified=False,
        quality_qualified=False, promotion=False, future_endpoint_CPU_profiles_and_selected_context_guards_required=True)
    raw = (json.dumps(value, indent=2, sort_keys=True)+'\n').encode()
    fd = os.open(output, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o444)
    return dict(path=str(output), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--finalize', action='store_true'); parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256'); args = parser.parse_args()
    if not args.finalize:
        print('INERT: no reads, outputs, imports, probes, launches, or controls'); return
    raw = args.job.read_bytes()
    require(len(raw) <= LIMIT and hashlib.sha256(raw).hexdigest() == args.job_sha256, 'Exact actual finalization job required')
    print(json.dumps(finalize(json.loads(raw))), flush=True)


if __name__ == '__main__':
    main()
