"""Study03 native/observer SMALL readback, default inert; never a raw review.

Only --readback loads closed metadata. C1 is permitted ONLY with --check-only,
without any live resource probe. R2/C2 may write an exclusive peer only after
actual closed exit0 metadata AND explicit --observe-released-resources.
No source/model/MAME/replay mutation, process control, raw kernel/prefix replay
or large binary hash occurs. Existing pinned archive/resource helpers are used
only through the narrow functions named below; CloseOriginal.__init__/scope
and the live main monitor are never loaded/executed during metadata-only use.
"""
import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import time

R = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
Y = R/'deadline-score32-fixed-fleet-admission-original03-preparation-20261026'
QUALIFIED = Y/'qualified-native-envelopes-after-CPU-original01/qualified-four-native-envelopes.json'
QUALIFIED_SHA = '4ea6d7d830b7d0c7fc77c2ec16365004e6c0897f6442bea9f6ff9e47a0e2867d'
RUNBOOK = Y/'C1-terminal-and-R2-readiness-runbook-original01/root-runbook-NOT-EXECUTED.json'
RUNBOOK_SHA = 'dae51601043c5678f9d3328bd9dec2179d93cf97b7610894991525f0a298e7bc'
C1_PROOF = Y/'fixed-RCRC-deadline32-study-original03/C1/original-terminal-small-resource-closeout-original01/independent-original-C1-small-resource-closeout.json'
C1_PROOF_SHA = '7b7740b35aa1df8c0632a47c1cab92ba8584758c59c8a643f6206a6275a52940'
SMALL = 2_000_000
RESULT_MAX = 16 << 20
SLOTS = {str(s) for s in range(4096, 4128)}
GPU0 = 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(path, *, follow=False):
    s = Path(path).stat() if follow else Path(path).lstat()
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pinned(path, *, sha=None, limit=SMALL):
    p = Path(path)
    require(p.is_absolute() and p.resolve() == p and stat.S_ISREG(p.lstat().st_mode), 'Canonical regular metadata/source required')
    before = identity(p)
    require(before['bytes'] <= limit, 'Body outside SMALL metadata scope')
    raw = p.read_bytes()
    require(identity(p) == before, 'Metadata/source changed during read')
    digest = hashlib.sha256(raw).hexdigest()
    require(sha is None or sha == digest, 'Actual metadata/source SHA differs')
    return dict(path=str(p), sha256=digest, bytes=len(raw), identity=before), raw


def json_file(path, *, sha=None, limit=SMALL):
    require(Path(path).suffix == '.json', 'JSON metadata only')
    pin, raw = pinned(path, sha=sha, limit=limit)
    return pin, json.loads(raw)


def stat_pin(pin, *, interpreter=False):
    reduced = {'device', 'inode', 'mode', 'uid', 'nlink'}
    require(set(pin) == {'path', 'sha256', 'bytes', 'identity'}
            and set(pin['identity']) in (reduced, reduced | {'bytes', 'mtime_ns', 'ctime_ns'}), 'Known full/reduced pin ABI required')
    actual = identity(pin['path'], follow=interpreter)
    require(pin['bytes'] == actual['bytes'] and set(pin['identity']) <= set(actual)
            and all(actual[k] == v for k, v in pin['identity'].items()), 'Exact attested stat differs: ' + pin['path'])
    if not interpreter:
        require(stat.S_ISREG(Path(pin['path']).lstat().st_mode) and not Path(pin['path']).is_symlink(), 'Regular original input required')
    return actual


def load(pin, name):
    _, raw = pinned(pin['path'], sha=pin['sha256'])
    stat_pin(pin)
    spec = importlib.util.spec_from_file_location(name, pin['path'])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(raw, pin['path'], 'exec'), module.__dict__)
    return module


def fields(text):
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def current_birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def collect(leg, *, source_sha256, closure_sha256, result_sha256):
    """Closed artifacts only: no /proc, sockets, lease, GPU, HTTP or main probe."""
    require(leg in ('C1', 'R2', 'C2') and all(type(s) is str and len(s) == 64
            for s in (source_sha256, closure_sha256, result_sha256)), 'Actual source/closure/result SHA values required')
    source, _ = pinned(Path(__file__).resolve(), sha=source_sha256)
    require(source['identity']['mode'] == '0o444', 'Frozen readback source required')
    runbook_pin, runbook = json_file(RUNBOOK, sha=RUNBOOK_SHA)
    c1_pin, _ = json_file(C1_PROOF, sha=C1_PROOF_SHA)
    qualified_pin, qualified = json_file(QUALIFIED, sha=QUALIFIED_SHA)
    case = next(c for c in qualified['cases'] if c['leg'] == leg)
    job_pin = case['native_job'];stat_pin(job_pin)
    _, job = json_file(job_pin['path'], sha=job_pin['sha256'])
    config_pin = case['native_launch_config'];stat_pin(config_pin)
    _, config = json_file(config_pin['path'], sha=config_pin['sha256'])
    require(job['leg'] == leg and job['attempt'] == 1 and job['no_retry'] is True
            and job['runtime']['sha256'] == '85b2efdd43c8c1c7a0f48610908bec1ded2b936d066080328b6862fc394ae556', 'Exact original study03 native job required')
    execution = Path(config['output']);output = Path(job['output'])
    owner_pin, owner = json_file(execution/'root-original-identity.json')
    closure_pin, closure = json_file(execution/'root-original-result-and-owned-release.json', sha=closure_sha256)
    # This must precede every future live resource operation or result read.
    require(type(closure['original_exit']) is type(closure['original_exec_code']) is int
            and closure['original_exit'] == 0 and closure['original_exec_code'] == 1
            and closure['original_result'] == 'success' and closure['original'] == owner
            and closure['unit_released'] is closure['lifecycle_complete'] is True,
            'Original native must actually exit0 and be archived/released')
    result_pin, result = json_file(output/'result.json', sha=result_sha256, limit=RESULT_MAX)
    require(result['original_job'] == job_pin and result['leg'] == leg and result['complete'] is True
            and result['errors'] == [] and result['all_original_threads_stopped'] is True
            and result['original_lease_released'] is result['immutable_inputs_unchanged'] is True
            and result['main_health_failure'] is None, 'Native in-process success/ownership is not positive')
    restoration = result['measurement_restoration']
    require(restoration['metric_sealed'] is restoration['all_original_threads_stopped'] is True
            and restoration['measurement_active_after'] is restoration['owns_mode_after'] is False,
            'Native restoration unknown or active')
    prior = runbook['prior_exact_recipes']
    reader = load(prior['immutable_dual_ABI_reader'], '_small_native_reader')
    archive = load(prior['archive_helper'], '_small_native_archive')
    def read(pin, as_json=True):
        # Actual archive5-key/8-key immutable444 ABI; never used for cfg0664.
        return reader.read_pin(pin, as_json=as_json)
    family = read(job['source_family_manifest'])
    lifecycle = read(result['main_observer_lifecycle'])
    require(lifecycle['native_job'] == job_pin and lifecycle['success'] is True
            and type(lifecycle['actual_controller_exit']) is int and lifecycle['actual_controller_exit'] == 0
            and lifecycle['all_owned_worker_and_controller_processes_reaped'] is True
            and lifecycle['original_scope_released'] is True, 'Positive original observer/controller closure required')
    observer_config = read(lifecycle['worker_config'])
    observer_owner = read(lifecycle['worker_owner'])
    observer_closure = read(lifecycle['worker_closure'])
    interpreter_pin, interpreter = json_file(prior['interpreter_link_attestation']['path'], sha=prior['interpreter_link_attestation']['sha256'])
    python = interpreter['path']
    require(str(Path(python).resolve()) == interpreter['resolved_target'], 'Known interpreter target changed')
    for link in interpreter['links']:
        require(os.readlink(link['path']) == link['readlink']
                and identity(link['path']) == link['lstat_identity'], 'Known interpreter link identity changed')
    stat_pin(interpreter['source_pin'], interpreter=True)
    for entry in job['inputs']:
        stat_pin(entry, interpreter=entry['path'] == python)
    stat_pin(job['checkpoint']);stat_pin(job['mame'])
    small_pins = {};large_pins = {}
    allowed_large = {job['checkpoint']['path'], job['mame']['path'], python}
    def config_inputs(cfg):
        for pin in cfg['pins']:
            actual = stat_pin(pin, interpreter=pin['path'] == python)
            if pin['bytes'] > SMALL:
                require(pin['path'] in allowed_large, 'Unexpected large cfg input; no body read')
                large_pins[pin['path']] = pin
            else:
                # Preserve actual declared0664/full/reduced identities directly.
                _, raw = pinned(pin['path'], sha=pin['sha256'])
                require(len(raw) == pin['bytes'] and identity(pin['path']) == actual, 'Small cfg input changed')
                small_pins[pin['path']] = pin
    scopes = []
    for role, op, cp, cfgp, controller, cpu, memory, tasks, stop, native in (
        ('native', owner_pin, closure_pin, config_pin, case['native_controller'], 12, 24 << 30, 512, 30, True),
        ('observer', lifecycle['worker_owner'], lifecycle['worker_closure'], lifecycle['worker_config'],
         family['main_observer']['controller'], 2, 4 << 30, 128, 5, False)):
        own, closed, cfg = (read(v) for v in (op, cp, cfgp))
        require(type(closed['original_exit']) is type(closed['original_exec_code']) is int
                and closed['original_exit'] == 0 and closed['original_exec_code'] == 1, 'Only true original exit0 accepted')
        f = archive.archived_closure(closed, own, read, exit_zero=True)
        require(archive.duration_seconds(f['CPUQuotaPerSecUSec']) == cpu and f['MemoryMax'] == str(memory)
                and f['MemorySwapMax'] == '0' and archive.duration_seconds(f['RuntimeMaxUSec']) == 4260
                and f['TasksMax'] == str(tasks) and f['SendSIGKILL'] == 'no' and f['Restart'] == 'no'
                and archive.duration_seconds(f['TimeoutStopUSec']) == stop, 'Actual original resources differ')
        require(not native or f['KillMode'] == 'mixed', 'Native KillMode differs')
        require(' '.join(cfg['argv']) + ' ; ignore_errors=no ;' in f['ExecStart']
                and 'CUDA_VISIBLE_DEVICES= ' in f['ExecStart'], 'Original argv/empty CUDA launcher differs')
        archives = closed.get('native_archives', closed.get('full_original_archives'))
        cat = read(archives[1]['stdout'], False).decode()
        starts = [line.split('=', 1)[1] for line in cat.splitlines() if line.startswith('ExecStart=') and line != 'ExecStart=']
        actual_argv = shlex.split(starts[0])
        require(len(starts) == 1 and actual_argv[-len(cfg['argv']):] == cfg['argv'], 'Actual archived literal argv differs')
        first, first_show = json_file(Path(cfg['output'])/'original-first-observed-show-command.json')
        live = fields(read(first_show['stdout'], False).decode())
        require(live['InvocationID'] == own['invocation_id'] and live['MainPID'] == str(own['pid'])
                and live['Id'] == own['unit'] and live['ControlGroup'].endswith('/' + own['unit']), 'Exact original live cgroup/identity required')
        require({row['unit'] for row in closed['owned_release']} == {own['unit'], own['timer']}, 'Both owned releases required')
        for row in closed['owned_release']:
            final = row['final']
            require(final['argv'] == ['systemctl', '--user', 'show', row['unit']]
                    and final['exit'] == 0 and final['timed_out'] is False, 'Exact original release observation required')
            released = fields(read(final['stdout'], False).decode())
            require(released['LoadState'] == 'not-found' and released.get('MainPID', '0') == '0', 'Original release not absent')
        config_inputs(cfg)
        scopes.append(dict(role=role, owner=op, closure=cp, config=cfgp, controller=controller,
            actual_exit=0, actual_CPU_cores=cpu, actual_memory_bytes=memory, actual_runtime_limit_s=4260,
            actual_tasks_max=tasks, all_six_original_descriptors_and_actual_resources_verified=True,
            original_live_fullshow=first, original_ControlGroup=live['ControlGroup'],
            original_owner=own, exact_units=[own['unit'], own['timer']]))
    child = read(lifecycle['controller_child'])
    require(child['parent']['job'] == job_pin and child['parent']['pid'] == owner['pid']
            and child['parent']['birth'] == owner['starttime_ticks'], 'Observer controller child parent differs')
    reap = result['original_post_origin_child_reap']
    require(reap['all_original_children_reaped'] is True and reap['unknown_slots'] == []
            and reap['exit_statuses_normalized'] is False
            and set(reap['original_children']) == set(result['original_slots']) == SLOTS, 'All32 actual original reaps required')
    actors = []
    for slot in sorted(SLOTS):
        row, actual = result['original_slots'][slot], reap['original_children'][slot]
        actor_pin, actor = json_file(output/'actors'/slot/'original-actor.json')
        require(actor['slot'] == int(slot) and actor['original_job'] == job_pin
                and actor['pid'] == row['pid'] == actual['pid']
                and actor['starttime_ticks'] == row['birth'] == actual['birth']
                and type(row['actual_exit']) is type(actual['actual_exit']) is int
                and row['actual_exit'] == actual['actual_exit']
                and row['outputs_sealed_after_original_writer_closure'] is True
                and row['original_unsealed_output_paths'] == [], 'Original MAME exit/birth/writer proof differs')
        actors.append(dict(slot=int(slot), pid=actual['pid'], birth=actual['birth'], actual_exit=actual['actual_exit'], original_actor=actor_pin))
    for pin in (result['deadline_anchor'], result['deadline_score_seal'], result['intentional_cleanup'], result['main_health_report']):
        stat_pin(pin)  # Never open the score rows or17MB health report.
    require(restoration['original_cutoff_seal'] == result['deadline_score_seal'], 'Native restored another seal')
    barrier = result['original_barrier']
    require(barrier['no_new_origin_entries'] is True and barrier['inflight'] == 0
            and barrier['entered'] == barrier['finished']
            and barrier['deadline_monotonic_ns'] <= barrier['closed_monotonic_ns'] <= barrier['deadline_monotonic_ns'] + 3_500_000_000,
            'Original zero-inflight cutoff barrier differs')
    proof = dict(schema='robotron-study03-native-observer-SMALL-closeout-v1', leg=leg,
        status='CLOSED_METADATA_VERIFIED_NO_FRESH_RESOURCE_CLAIM', readback_source=source,
        source_recipe_C1=c1_pin, source_recipe_runbook=runbook_pin, qualified_envelope_manifest=qualified_pin,
        native_job=job_pin, native_result=result_pin, original_scopes=scopes,
        all32_original_MAME=actors, actual_MAME_exit_counts=dict(collections.Counter(str(v['actual_exit']) for v in actors)),
        observer_controller_child=lifecycle['controller_child'], original_observer_child=child,
        actual_inprocess_flags_preserved=dict(complete=result['complete'], errors=result['errors'], all_original_threads_stopped=True,
            original_lease_released=True, immutable_inputs_unchanged=True, measurement_metric_sealed=True,
            measurement_active_after=False, owns_mode_after=False),
        deadline_anchor=result['deadline_anchor'], deadline_score_seal=result['deadline_score_seal'],
        actual_zero_inflight_barrier=barrier, native_declared_main_health_report=result['main_health_report'],
        closed_main_health_report_stat_only=True, native_declared_main_observer_lifecycle=result['main_observer_lifecycle'],
        exact_interpreter_link_attestation=interpreter_pin, large_inputs_stat_only=list(large_pins.values()),
        small_source_and_config_pin_count=len(small_pins), fresh_resource_checks_executed=False,
        raw_kernel_prefix_score_rows_model_or_MAME_bodies_read=False,
        selected_source_or_main_or_canonical_state_modified=False, deadline_metric_independently_qualified=False,
        improvement_qualified=False, observed_unix_s=time.time())
    return proof, dict(job=job, result=result, prior=prior, reader=reader, read=read, child=child)


def observe_released_resources(proof, context):
    """Explicit future-only phase, unreachable for C1 metadata validation."""
    require(proof['leg'] in ('R2', 'C2') and proof['status'] == 'CLOSED_METADATA_VERIFIED_NO_FRESH_RESOURCE_CLAIM',
            'Only actually closed R2/C2 may probe resources')
    prior, job = context['prior'], context['job']
    resource = load(prior['resource_helper'], '_small_native_resource')
    h = load(prior['small_pin_helper'], '_small_native_pin_helper')
    for scope in proof['original_scopes']:
        owner = scope['original_owner']
        require(current_birth(owner['pid']) != owner['starttime_ticks'], 'Original native/observer process remains')
        require(not Path('/sys/fs/cgroup' + scope['original_ControlGroup']).exists(), 'Original scope cgroup remains')
        for unit in scope['exact_units']:
            p = subprocess.run(['systemctl', '--user', 'show', unit], capture_output=True, text=True, timeout=5)
            f = fields(p.stdout)
            require(p.returncode == 0 and p.stderr == '' and f.get('Id') == unit
                    and f.get('LoadState') == 'not-found' and f.get('ActiveState') == 'inactive'
                    and f.get('MainPID', '0') == '0' and not f.get('InvocationID'), 'Exact original unit not absent')
            cg = subprocess.run(['systemctl', '--user', 'show', unit, '--property=ControlGroup', '--value'],
                                capture_output=True, text=True, timeout=5)
            require(cg.returncode == 0 and cg.stderr == '' and cg.stdout.strip() == '', 'Original unit cgroup remains')
    for actor in proof['all32_original_MAME']:
        require(current_birth(actor['pid']) != actor['birth'], 'Original MAME process birth remains')
    child = context['child']
    require(current_birth(child['pid']) != child['birth'], 'Original observer controller child remains')
    scratch = resource.CloseOriginal.__new__(resource.CloseOriginal)
    scratch.h = h;scratch.job = copy.deepcopy(job);scratch.count = 64;scratch.case = proof['leg']
    scratch.job['proxy_ports'] = {str(s): 20000 + s - 4096 for s in range(4096, 4160)}
    require(job['origin_port'] == 19998 and job['gpu_uuid'] == GPU0, 'Exact private GPU/port contract required')
    proof['resources'] = scratch.free_resources()  # lease/65ports/GPU only; no constructor/scope call
    private = []
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():continue
        try:
            cmd = directory.joinpath('cmdline').read_bytes().split(b'\0')
            if job['runtime']['path'].encode() in cmd:
                private.append(int(directory.name));continue
            if cmd and b'mame' in cmd[0]:
                env = dict(item.split(b'=', 1) for item in directory.joinpath('environ').read_bytes().split(b'\0') if b'=' in item)
                slot = int(env.get(b'ROBOTRON_CLIENT_SLOT', b'-1'))
                if 4096 <= slot < 4160:private.append(int(directory.name))
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):continue
    require(private == [], 'Private native or reserved-slot MAME remains')
    monitor = job['current_main_monitor']
    _, _ = pinned(monitor['path'], sha=monitor['sha256'])
    require(monitor['sha256'] == 'a16e51a71a066a06dcaa02657024fcd52c0ccc8f3f23ef6c970e4051f538b224', 'Exact current-main monitor required')
    p = subprocess.run(['/usr/bin/python3.12', '-I', '-B', monitor['path']], capture_output=True, text=True, timeout=30)
    require(p.returncode == 0 and p.stderr == '', 'Current-main monitor did not pass')
    main = json.loads(p.stdout)
    require(main['client_count'] == 192 and main['held_inputs'] == 197
            and main['training_enabled'] is True and main['measurement_active'] is False
            and main['bound192_actor_identities_and_affinities_verified'] is True, 'Current main192/197 proof differs')
    proof.update(status='ORIGINAL_NATIVE_OBSERVER32_AND_PRIVATE_RESOURCES_EXTERNALLY_CLOSED',
        fresh_resource_checks_executed=True, all_original_process_births_and_cgroups_absent=True,
        original_units_fresh_not_found=True, private_native_or_highslot_processes=private,
        main=main, current_main_monitor=monitor, observed_unix_s=time.time())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--readback', action='store_true');p.add_argument('--check-only', action='store_true')
    p.add_argument('--observe-released-resources', action='store_true')
    p.add_argument('--leg', choices=('C1', 'R2', 'C2'));p.add_argument('--source-sha256')
    p.add_argument('--closure-sha256');p.add_argument('--result-sha256');p.add_argument('--output')
    a = p.parse_args()
    if not a.readback:
        print('PLAN_ONLY: no metadata reads, resource probes, outputs or actions');return 0
    require(a.leg and a.source_sha256 and a.closure_sha256 and a.result_sha256, 'Explicit actual terminal metadata required')
    require(a.leg != 'C1' or (a.check_only and not a.observe_released_resources), 'C1 is metadata-only validation; no current resource claim')
    require(a.check_only or (a.observe_released_resources and a.output), 'Only full future resource readback may publish')
    proof, context = collect(a.leg, source_sha256=a.source_sha256, closure_sha256=a.closure_sha256, result_sha256=a.result_sha256)
    if a.observe_released_resources:observe_released_resources(proof, context)
    if a.check_only:
        print(json.dumps(dict(status=proof['status'], leg=a.leg, native_result=proof['native_result'],
            original_scopes=len(proof['original_scopes']), original_actor_count=len(proof['all32_original_MAME']),
            fresh_resource_checks_executed=proof['fresh_resource_checks_executed'], receipt_written=False)));return 0
    output = Path(a.output)
    expected = Path(context['job']['output']).parent/'original-terminal-small-resource-closeout-original01'/('independent-original-' + a.leg + '-small-resource-closeout.json')
    require(output == expected and output.is_absolute() and not output.exists()
            and not output.parent.exists() and output.parent.parent.is_dir(), 'Fresh exact original closeout path required')
    output.parent.mkdir(mode=0o700)
    with output.open('x') as f:
        json.dump(proof, f, indent=2, allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(), 0o444)
    result, _ = pinned(output)
    print(json.dumps(result));return 0


if __name__ == '__main__':
    raise SystemExit(main())
