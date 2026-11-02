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
REVISION = ENGINEERING.parent / 'capture-bracket-revision02'
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
    require(closed['schema'] == 'robotron-source-bound-reconnect-original-engineering-closeout-v1'
            and closed['status'] == 'PASS_ENGINEERING_ONLY' and closed['kind'] == 'deadline'
            and closed['mode'] == mode and closed['launch_index'] == job['launch_index']
            and closed['original_live_owner'] == record['original_live_owner']
            and closed['original_parent_actual_exit'] == 0
            and closed['worker_actual_exit'] == (0 if mode == 'long' else 1)
            and closed['all_original_births_units_cgroups_and_tmpfs_control_absent'] is True
            and closed['actual_parent_CPU_cores'] == 2 and closed['actual_parent_memory_bytes'] == 4 << 30
            and closed['actual_parent_runtime_s'] == 780, 'Actual original engineering closure differs')
    require(closed['source'] == prepared['sources']['close_declared_launcher_engineering_mmap_v2.py'],
            'Unchanged owned closer source differs')
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
            and probe['retired_API_reviewer_source'] == family['round_observer_reviewer']
            and all(probe[key] is False for key in ('main_runtime_changed','private_policy_or_GPU_loaded',
                'scientific_launch_qualified','quality_qualified')), 'Probe source map or scope differs')
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
                    'fresh_final_sample_verified','legacy_500ms_evidence_and_projection_gaps_verified'))
                and outcome['success'] is lifecycle['success'] is True and outcome['error'] is None,
                'Long run lacks actual successful full raw review')
    else:
        request = read(outcome['finish_request'])
        require(probe['independently_replayed_raw_review'] is None
                and outcome['success'] is lifecycle['success'] is False
                and request['action'] == 'abort' and request['job'] == lifecycle['worker_job']
                and request['nonce'] == worker['nonce'], 'Original expected abort disposition differs')
    small = read(job[mode + '_small'])
    require(small['schema'] == 'robotron-retired-API-original-engineering-SMALL-independent-readback-v1'
            and small['status'] == 'PASS_SMALL_ENGINEERING_ONLY'
            and small['mode'] == mode and small['closeout'] == close_pin
            and small['launch_index'] == job['launch_index']
            and small['original_parent_actual_exit'] == 0
            and small['worker_actual_exit'] == closed['worker_actual_exit']
            and small['all_original_births_units_cgroups_and_tmpfs_control_absent'] is True,
            'Independent small readback is not this original closed scope')
    return dict(closeout=close_pin, independent_small=job[mode + '_small'],
        actual_parent_exit=0, actual_worker_exit=closed['worker_actual_exit'],
        lifecycle=closed['worker_lifecycle'], accepted_samples=closed['accepted_samples'],
        unaccepted_samples=closed['unaccepted_samples'], full_raw_review_rerun_by_finalizer=False)


def finalize(job):
    require(job['schema'] == 'robotron-retired-API-joint-engineering-finalization-job-v1', 'Wrong job schema')
    own = job['source']
    require(own['path'] == str(Path(__file__).resolve()), 'Another finalizer source selected')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == own['sha256'], 'Finalizer bytes differ')
    source_identity(own)
    index = fixed(job['launch_index'], CONTEXTS/'ROOT-two-original-actual-launches-index-original01.json',
        '2b8209357930c2c181d7347e946c2e5a06749b84f957993c0d17a204f72ff549')
    family = fixed(job['source_family'], REVISION/'prepared-retired-API-capture-bracket-ten-source-family-v2.json',
        'd2a287e6f97ad3cee4db0279ae5a05816dccbe14bb820c9f4e91264e2b5388c7')
    prepared = read(index['preparation'])
    require(family['actual_engineering_preparation'] == index['preparation']
            and set(family['observer_sources']) == ROLES and family['logical_dependency_count'] == 10
            and prepared['observer_sources'] == family['observer_sources']
            and prepared['original_held_input_count'] == 247 and prepared['held_inputs_unchanged'] is True,
            'Selected family, original247 case, or actual preparation differs')
    for pin in [*family['observer_sources'].values(), family['round_observer_reviewer']]:
        source_identity(pin)
    focused = fixed(job['focused_small'], REVISION/'focused6-CPU-original01/independent-focused6-original-CPU-SMALL-closeout.json',
        'c7d3dfa7ac91047df31c56d8fdbbe1a552f3954d05e0b88cb8590b7274326a0d')
    require(family['actual_focused_CPU_closeout'] == job['focused_small']
            and focused['status'] == 'PASS_FOCUSED_FIXTURES_ONLY' and focused['actual_tests'] == 6
            and focused['actual_original_ExecMainCode'] == 1 and focused['actual_original_exit'] == 0
            and focused['all_six_original_archives_resources_argv_verified'] is True
            and focused['original_birth_absent'] is focused['original_cgroup_absent'] is True,
            'Actual focused6 independent closure differs')
    require(read(focused['original_closure'])['original_exit'] == 0, 'Focused CPU did not exit0')
    records = {row['mode']:row for row in index['records']}
    require(set(records) == {'long','abort'} and len(index['records']) == 2, 'Exact two original contexts required')
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
    require(output == CONTEXTS/'independent-retired-API-joint-engineering-qualification-original01.json'
            and not output.exists(), 'Exclusive new qualification output required')
    value = dict(schema='robotron-retired-API-joint-engineering-readiness-v1',
        status='ENGINEERING_PASS_AT_RECORDED_OBSERVED_LOAD_ONLY', created_unix_s=time.time(),
        source=own, launch_index=job['launch_index'], source_family=job['source_family'],
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
