#!/usr/bin/env python3
"""UNSELECTED four-member frozen-quality prototype. Default PLAN is read-free.

Future execution requires a new root case, capacity evidence and (for R/C) a
closed four-member A/A review. This file never changes the live trainer.
"""
from __future__ import annotations

import argparse
from collections import Counter
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import shutil
import stat
import statistics
import subprocess
import sys
import time
import urllib.request

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]
BASE = GAME / 'tools/frozen_continuous_guard_evaluator_proposal'
GPU0 = 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
GPU1 = 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'
LEASE = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
ORDER = ('reference', 'candidate', 'reference', 'candidate')
PROFILE = dict(members=4, actors_per_member=16, logical_slots=list(range(4096, 4112)),
    gpu_uuid=GPU0, inference_backend='inductor', fp16=False, replay_enabled=False,
    epsilon=0, expert_ratio=0, difficulty=5, start_level=1, cpu_threads=2,
    wait_us=1000, cohort_s=2400, timeout_s=3600, min_games=50,
    all_admitted_tails=True, max_attempts=1, admission_extensions=False,
    hold_completed_members_until_joint_stop=True, max_admission_skew_s=1.0)
CASE_KEYS = {'schema', 'authorized', 'mode', 'experiment', 'output_directory',
    'reference', 'candidate', 'python', 'parent_unit', 'cpu_mask', 'ports',
    'main_baseline', 'prior_disposition', 'capacity_review', 'aa_review',
    'boot_assets', 'effective_guard_manifest'}
PIN_KEYS = {'path', 'sha256', 'bytes', 'identity'}
ID_KEYS = {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'nlink'}
CARRIER = dict(Type='exec', Restart='no', RemainAfterExit='yes',
    KillMode='control-group', KillSignal='2', TimeoutStopUSec='4min', SendSIGKILL='yes')


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def pin(path):
    path = Path(path)
    require(path.is_absolute() and not path.is_symlink(), 'Absolute regular path required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'Single regular file required')
    raw = path.read_bytes()
    after = path.lstat()
    require(identity(before) == identity(after), 'File identity changed while reading')
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw), identity=identity(after)), raw


def pinned(value):
    require(type(value) is dict and set(value) == PIN_KEYS and set(value['identity']) == ID_KEYS,
        'Exact FULLPIN required')
    actual, raw = pin(value['path'])
    require(actual == value and value['identity']['mode'] == '0o444', 'Readonly FULLPIN mismatch')
    return raw


def decoded(raw):
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite metadata')))


def publish(path, value):
    path = Path(path)
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return pin(path)[0]


def process_start(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


def alive(owner):
    return (type(owner['starttime_ticks']) is int and owner['starttime_ticks'] > 0
        and process_start(owner['pid']) == owner['starttime_ticks']
        and ('cgroup' not in owner or process_cgroup(owner['pid']) == owner['cgroup']))


def with_lease(kwargs, descriptor):
    require(type(descriptor) is int and descriptor >= 3 and 'pass_fds' not in kwargs,
        'One inherited common lease description required')
    return dict(kwargs, close_fds=True, pass_fds=(descriptor,))


def lease_identity(descriptor):
    info = os.fstat(descriptor)
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid(),
        'Owned single regular lease required')
    return {key: identity(info)[key] for key in ('device', 'inode', 'mode', 'uid', 'nlink')}


def descriptor_retained(pid, descriptor, expected):
    info = os.stat(Path('/proc', str(pid), 'fd', str(descriptor)))
    observed = {key: identity(info)[key] for key in ('device', 'inode', 'mode', 'uid', 'nlink')}
    fdinfo = Path('/proc', str(pid), 'fdinfo', str(descriptor)).read_text()
    require(observed == expected and any('FLOCK' in line and 'ADVISORY' in line and 'WRITE' in line
        for line in fdinfo.splitlines() if line.startswith('lock:')), 'Inherited locked description was closed or replaced')
    return observed


def process_cgroup(pid):
    values = [line[3:] for line in Path('/proc', str(pid), 'cgroup').read_text().splitlines()
        if line.startswith('0::')]
    require(len(values) == 1, 'Unified owned cgroup required')
    return values[0]


def carrier_contract(fields, pid, cgroup):
    require(all(fields.get(key) == value for key, value in CARRIER.items())
        and fields.get('MainPID') == str(pid) and fields.get('NRestarts') == '0'
        and fields.get('SubState') == 'running' and fields.get('InvocationID')
        and fields.get('ControlGroup') == cgroup and cgroup.startswith('/user.slice/'),
        'Dedicated future systemd carrier contract is unavailable')


def cgroup_members(cgroup):
    path = Path('/sys/fs/cgroup' + cgroup) / 'cgroup.procs'
    return {int(value) for value in path.read_text().split()}


def manifest(path, digest):
    actual, raw = pin(path)
    require(actual['sha256'] == digest and actual['identity']['mode'] == '0o444', 'Manifest pin differs')
    value = decoded(raw)
    require(value['schema'] == 'robotron-parallel-frozen-quality-source-v1'
        and value['status'] == 'UNSELECTED_UNEXECUTED', 'Wrong proposal manifest')
    for item in [*value['files'].values(), *value['upstreams'].values()]:
        observed, _ = pin(item['path'])
        require(observed == item, 'Declared source identity changed')
    require(value['files']['joint_parent.py']['path'] == str(HERE / 'joint_parent.py')
        and value['files']['joint_member.py']['path'] == str(HERE / 'joint_member.py'), 'Wrong source directory')
    return value, actual


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, 'Pinned loader unavailable')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_case(case, *, reader=pinned):
    require(type(case) is dict and set(case) == CASE_KEYS, 'Exact joint case fields required')
    require(case['schema'] == 'robotron-parallel-frozen-quality-case-v1' and case['authorized'] is True,
        'Explicit new root selection required')
    require(case['mode'] in ('aa_validation', 'rc_confirmation'), 'Unknown scientific mode')
    require(type(case['experiment']) is str and 0 < len(case['experiment']) <= 120, 'Bounded label required')
    directory = Path(case['output_directory'])
    require(directory.is_absolute() and directory == directory.resolve()
        and directory.is_relative_to(GAME / 'logs') and not directory.exists(), 'New private campaign directory required')
    require(type(case['ports']) is list and len(case['ports']) == 4
        and all(type(p) is int and 1024 <= p <= 65535 and p != 9998 for p in case['ports'])
        and len(set(case['ports'])) == 4, 'Four distinct nonproduction ports required')
    require(type(case['cpu_mask']) is list and case['cpu_mask']
        and all(type(x) is int and x >= 0 for x in case['cpu_mask'])
        and case['cpu_mask'] == sorted(set(case['cpu_mask'])), 'Explicit parent/child CPU mask required')
    require(type(case['parent_unit']) is str and case['parent_unit'].startswith('robotron-parallel-quality-')
        and case['parent_unit'].endswith('.service'), 'New owned parent unit required')
    for name in ('reference', 'candidate', 'main_baseline', 'prior_disposition',
                 'capacity_review', 'boot_assets', 'effective_guard_manifest'):
        reader(case[name])
    require(type(case['python']) is dict and set(case['python']) == PIN_KEYS
        and set(case['python']['identity']) == ID_KEYS, 'Pinned interpreter required')
    require(case['python']['path'] == str(Path(sys.executable).resolve()), 'Exact selected interpreter required')
    baseline = decoded(reader(case['main_baseline']))
    require(baseline['schema'] == 'robotron-current-main192-runtime-baseline-v1' and baseline['status'] == 'PASS'
        and 0 <= time.time() - baseline['observed_unix_s'] < 180, 'Fresh root main baseline required')
    actors = baseline['actors']
    require(len(actors) == 192 and sorted(a['slot'] for a in actors) == list(range(192))
        and len({a['pid'] for a in actors}) == 192, 'Original192 baseline required')
    main_mask = set(baseline['inference_worker']['mask'])
    require(not main_mask.intersection(case['cpu_mask']), 'Private CPU placement must exclude held main mask')
    prior = decoded(reader(case['prior_disposition']))
    require(prior.get('source_freeze_released') is True, 'Actual complete predecessor disposition/release required')
    capacity = decoded(reader(case['capacity_review']))
    require(capacity['schema'] == 'robotron-parallel-quality-root-capacity-review-v1'
        and capacity['status'] == 'PASS' and capacity['profile'] == PROFILE
        and capacity['main_baseline'] == case['main_baseline']
        and capacity['prior_disposition'] == case['prior_disposition']
        and type(capacity['minimum_GPU0_free_bytes']) is int and capacity['minimum_GPU0_free_bytes'] > 0,
        'Explicit fresh capacity review for this profile required')
    if case['mode'] == 'aa_validation':
        require(case['candidate'] == case['reference'] and case['aa_review'] is None,
            'A/A requires one protected checkpoint four times; never qualifies a candidate')
    else:
        aa = decoded(reader(case['aa_review']))
        require(aa['schema'] == 'robotron-parallel-quality-closed-AA-review-v1'
            and aa['status'] == 'PASS' and aa['profile'] == PROFILE
            and aa['all_four_valid'] is True and aa['latency_capacity_accepted'] is True
            and aa['qualification'] is False and aa['promotion'] is False,
            'Closed full-profile A/A and latency review required before R/C')
    return baseline, capacity


def show(unit):
    value = subprocess.run(['systemctl', '--user', 'show', unit, '--all'],
        capture_output=True, text=True, timeout=10)
    require(value.returncode == 0, 'Owned unit show failed')
    return dict(line.split('=', 1) for line in value.stdout.splitlines() if '=' in line)


def runtime_guard(case, baseline, capacity, allowed_gpu0, *, full=False):
    main = baseline['main_owner']
    require(alive(main), 'Original main PID/start changed')
    fields = show(main['unit'])
    require(fields['MainPID'] == str(main['pid']) and fields['InvocationID'] == main['invocation_id']
        and fields['NRestarts'] == '0' and fields['SubState'] == 'running', 'Main incarnation changed')
    fleet = baseline['fleet_owner']
    fleet_fields = show(fleet['unit'])
    require(alive(fleet) and fleet_fields['MainPID'] == str(fleet['pid'])
        and fleet_fields['InvocationID'] == fleet['invocation_id'] and fleet_fields['SubState'] == 'running',
        'Original fleet supervisor changed')
    for actor in baseline['actors']:
        require(alive(actor) and sorted(os.sched_getaffinity(actor['pid'])) == actor['mask'],
            'Original actor identity or mask changed')
    require(sorted(os.sched_getaffinity(0)) == case['cpu_mask'], 'Parent CPU placement differs')
    worker = baseline['inference_worker']
    ticks = int(Path('/proc', str(main['pid']), 'task', str(worker['tid']), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    require(ticks == worker['starttime_ticks'] and sorted(os.sched_getaffinity(worker['tid'])) == worker['mask'],
        'Original inference worker changed')
    if full:
        for path, digest in {**baseline['source_hashes'], **baseline['control_hashes'], **baseline['unit_files']}.items():
            require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, 'Held inventory changed')
        environment = {part.split(b'=', 1)[0].decode(): part.split(b'=', 1)[1].decode()
            for part in Path('/proc', str(main['pid']), 'environ').read_bytes().split(b'\0')
            if b'=' in part and part.split(b'=', 1)[0].decode().startswith(('DQN_', 'ROBOTRON_', 'CUDA_', 'TORCHINDUCTOR_'))}
        require(hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest() == baseline['environment_sha256'],
            'Held main environment changed')
    apps = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader,nounits'],
        capture_output=True, text=True, timeout=10)
    require(apps.returncode == 0, 'GPU ownership unavailable')
    owners = [(int(line.split(',')[0]), line.split(',')[1].strip())
        for line in apps.stdout.splitlines() if line.strip()]
    require({pid for pid, gpu in owners if gpu == GPU0}.issubset(set(allowed_gpu0))
        and [(pid, gpu) for pid, gpu in owners if gpu == GPU1] == [(main['pid'], GPU1)], 'Foreign GPU owner')
    if not allowed_gpu0:
        value = subprocess.run(['nvidia-smi', '--query-gpu=uuid,memory.free', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=10)
        require(value.returncode == 0, 'GPU memory unavailable')
        free = {line.split(',')[0].strip(): int(line.split(',')[1]) * (1 << 20)
            for line in value.stdout.splitlines() if line.strip()}
        require(free[GPU0] >= capacity['minimum_GPU0_free_bytes'], 'Capacity review free-memory floor failed')
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as stream:
        raw = stream.read((2 << 20) + 1)
    require(len(raw) <= 2 << 20, 'Main API oversized')
    api = json.loads(raw)
    original_api = json.loads(pinned(baseline['actual_API']))
    require(api['client_count'] == 192 and api['training_enabled'] is True
        and api['measurement_active'] is False and api['managed_experiment'] == original_api['managed_experiment']
        and api['lr'] == original_api['lr']
        and api['host_pipeline']['learning_exposure']['replay']['process_id'] == main['pid'],
        'Main healthy continuation changed')
    for kind in ('optimizer', 'replay'):
        now = api['host_pipeline']['learning_exposure'][kind]
        before = original_api['host_pipeline']['learning_exposure'][kind]
        require(all(now[key] == before[key] for key in ('process_id', 'instance_monotonic_ns', 'epoch')),
            'Held optimizer/replay exposure identity changed')
    return dict(main_owner=main, observed_unix_s=time.time(), client_count=192,
        learner_frame_count=api['learner_frame_count'], allowed_GPU0_pids=sorted(allowed_gpu0))


def member_message(path, case_sha, record, stage):
    value = decoded(Path(path).read_bytes())
    require(value['schema'] == 'robotron-parallel-quality-member-message-v1'
        and value['case_sha256'] == case_sha and value['index'] == record['index']
        and value['stage'] == stage and value['owner'] == record['owner'], 'Foreign member message')
    return value


def prepared_contract(value, spec, plan):
    numeric = value['numeric_policy']
    require(value['checkpoint_sha256'] == plan['checkpoints'][spec['role']]['sha256']
        and value['serving_started'] is False and numeric['compiled'] is True
        and numeric['backend'] == 'inductor' and numeric['weights'] == numeric['inputs'] == 'float32'
        and numeric['autocast'] is False and value['compile_report']['all_shapes_verified'] == list(range(1, 17))
        and value['inherited_lease_descriptor'] == plan['lease']['descriptor']
        and value['lease_identity'] == plan['lease']['identity'], 'Member preparation differs')


def connected_contract(value, parent):
    actors = value['actors']
    require(value['boundary']['ready'] is True and value['boundary']['actor_slots'] == PROFILE['logical_slots']
        and len(actors) == 16 and sorted(a['slot'] for a in actors) == PROFILE['logical_slots']
        and len({a['pid'] for a in actors}) == 16 and all(a['cgroup'] == parent['cgroup']
            and type(a['starttime_ticks']) is int and a['starttime_ticks'] > 0 for a in actors),
        'Exact owned16 readiness required')


def wait_stage(record, stage, case_sha, deadline, records, stopped, health, *, clock=time.monotonic, sleep=time.sleep):
    path = Path(record['directory']) / (stage + '.json')
    while True:
        require(not stopped(), 'Parent interrupted')
        require(all(item['process'].poll() is None and alive(item['owner']) for item in records),
            'A member exited before the joint stage')
        if path.exists():
            return member_message(path, case_sha, record, stage)
        require(clock() < deadline, 'Fixed joint preparation/readiness deadline expired')
        health()
        sleep(.1)


def stop_members(records, *, timeout=240, clock=time.monotonic):
    """Signal only original Popen children. A missed deadline is NOT release."""
    errors = []
    for record in records:
        process = record['process']
        if process.poll() is None:
            if not alive(record['owner']):
                errors.append('Original member identity lost before SIGINT')
            else:
                try:
                    process.send_signal(signal.SIGINT)
                except OSError as error:
                    errors.append(f'Original member SIGINT failed: {error}')
    deadline = clock() + timeout
    for record in records:
        try:
            record['process'].wait(timeout=max(.001, deadline - clock()))
        except subprocess.TimeoutExpired:
            errors.append('Original member did not reap within cleanup budget')
    return errors


def common_signature(receipt, leg, evaluator, job_fields):
    # Every full port/job is checked against its OWN plan by load_leg first.
    # Only the transport namespace is removed from cross-member science equality.
    return dict(job={key: receipt['job'][key] for key in job_fields if key != 'port'},
        numeric_policy=receipt['numeric_policy'], runtime=receipt['runtime'],
        source_hashes=receipt['source_hashes'], protocol=leg['protocol'],
        effective_implementation=evaluator.stable_effective_implementation(receipt['effective_implementation']),
        boot_identity=receipt['boot_assets']['identity'], wire_binary=receipt['socket_wait']['sha256'])


def assess(plan, records, campaign, *, all_padding_valid):
    report = dict(outcome='invalid', qualified_improvement=False, reason='All four valid originals required', legs=[])
    validated, identifiers, anchor = [], set(), None
    for spec, record in zip(plan['legs'], records):
        require(record['process'].returncode == 0, 'Member original exit was nonzero')
        receipt, leg, digest = campaign.load_leg(spec, plan)
        require(len(leg['rows']) >= PROFILE['min_games'], 'Fewer than50 original full games')
        parallel = receipt['parallel_profile']
        require(parallel['profile'] == PROFILE and parallel['case'] == plan['case']
            and parallel['manifest'] == plan['source_manifest'] and parallel['parent'] == plan['parent']
            and parallel['member_owner'] == record['owner'] and parallel['held_through_joint_stop'] is True
            and parallel['unscored_padding_faults_validated'] is True and parallel['actor_closure_complete'] is True,
            'Actual parallel lifecycle provenance differs')
        signature = common_signature(receipt, leg, campaign.evaluator, campaign.JOB_FIELDS)
        require(anchor is None or anchor == signature, 'Common scientific profile differs')
        anchor = signature
        ids = {row['journal_game_id'] for row in leg['rows']}
        require(not identifiers.intersection(ids), 'Cross-member game IDs overlap')
        identifiers.update(ids)
        evidence = dict(index=spec['index'], role=spec['role'], valid=True,
            receipt_sha256=digest, summary=campaign.summarize(leg), included_game_ids=sorted(ids))
        report['legs'].append(evidence)
        validated.append((spec['role'], leg, evidence))
    require(len(validated) == 4 and all_padding_valid is True, 'Padding or member coverage invalid')
    if plan['mode'] == 'aa_validation':
        report.update(outcome='AA_VALIDATION_COMPLETE_NOT_QUALIFICATION',
            reason='Four same-checkpoint cohorts; root latency/capacity review remains required',
            qualification=False, promotion=False)
        return report
    # The following gate limb is copied verbatim from the pinned sequential campaign.
    reference_rows = [row for role, leg, _ in validated if role == "reference" for row in leg["rows"]]
    scores = [row["score"] for row in reference_rows]
    mean, median = statistics.fmean(scores), statistics.median(scores)
    report["pooled_reference"] = dict(count=len(scores), mean=mean, median=median,
        actor_slot_counts=dict(sorted(Counter(str(row["client_slot"]) for row in reference_rows).items())))
    if mean <= 0:
        report.update(outcome="invalid", reason="Pooled reference mean must be positive to assess a relative improvement")
        return report
    checks = []
    for role, leg, evidence in validated:
        if role != "candidate":
            continue
        summary = evidence["summary"]
        checks.append(dict(index=evidence["index"], mean=summary["mean"], median=summary["median"],
            mean_ratio=summary["mean"]/mean if mean else None,
            mean_pass=summary["mean"] >= mean * 1.05,
            median_pass=summary["median"] >= median))
    qualified = all(check["mean_pass"] and check["median_pass"] for check in checks)
    report.update(candidate_checks=checks, qualified_improvement=qualified,
        outcome="qualified_improvement" if qualified else "not_improved",
        reason="Both candidate legs satisfy the fixed mean and median gates" if qualified else
               "At least one candidate leg misses the fixed mean or median gate")
    return report


def execute(args):
    inventory, manifest_pin = manifest(args.manifest, args.manifest_sha256)
    case_pin, raw = pin(args.case)
    require(case_pin['sha256'] == args.case_sha256 and case_pin['identity']['mode'] == '0o444', 'Root case pin differs')
    case = decoded(raw)
    baseline, capacity = validate_case(case)
    require(sys.version_info[:2] == (3, 14) and hasattr(sys, '_is_gil_enabled')
        and not sys._is_gil_enabled(), 'Native free-threaded CPython314 required')
    require(pin(case['python']['path'])[0] == case['python'], 'Interpreter changed')
    own = show(case['parent_unit'])
    cgroup = process_cgroup(os.getpid())
    carrier_contract(own, os.getpid(), cgroup)
    require(str(HERE / 'joint_parent.py') in own.get('ExecStart', '')
        and str(args.case) in own.get('ExecStart', '') and args.case_sha256 in own.get('ExecStart', '')
        and args.manifest_sha256 in own.get('ExecStart', ''), 'Durable carrier argv differs')
    require(cgroup_members(cgroup) == {os.getpid()}, 'Dedicated parent cgroup contains foreign work')
    descriptor = os.open(LEASE, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    lease = os.fdopen(descriptor, 'r+')
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    lease_record = dict(descriptor=lease.fileno(), identity=lease_identity(lease.fileno()))
    records, streams, signals = [], [], []
    prior = {s: signal.signal(s, lambda number, _frame: signals.append(number)) for s in (signal.SIGINT, signal.SIGTERM)}
    directory = Path(case['output_directory'])
    failure, report, released = None, None, False
    cleanup_attempted, cleanup_errors = False, []
    try:
        before = runtime_guard(case, baseline, capacity, set(), full=True)
        for path in ('/proc/net/tcp', '/proc/net/tcp6'):
            require(not any(row.split()[3] == '0A' and int(row.split()[1].rsplit(':', 1)[1], 16) in case['ports']
                for row in Path(path).read_text().splitlines()[1:]), 'A planned port is already bound')
        directory.mkdir(parents=True, exist_ok=False)
        (directory / 'control').mkdir()
        parent = dict(pid=os.getpid(), starttime_ticks=process_start(os.getpid()), cgroup=cgroup)
        campaign = load(BASE / 'run_quality_campaign.py', '_parallel_quality_original_campaign')
        evaluator = campaign.evaluator
        require(evaluator.source_hashes() == inventory['base_evaluator_sources'], 'Canonical E13 changed')
        boot = evaluator.boot_module().load_snapshot(Path(case['boot_assets']['path']).parent)
        guard = evaluator.guard_selection(case['effective_guard_manifest']['path'], case['effective_guard_manifest']['sha256'])
        plan = dict(schema='robotron-parallel-frozen-quality-plan-v1', mode=case['mode'], profile=PROFILE,
            case=case_pin, source_manifest=manifest_pin, parent=parent, unit=case['parent_unit'],
            invocation_id=own['InvocationID'], carrier_contract=CARRIER, lease_path=str(LEASE),
            lease=lease_record, output_directory=str(directory),
            checkpoints={}, boot_assets=boot, evaluator_source_hashes=inventory['base_evaluator_sources'],
            effective_implementation=guard, legs=[], before=before)
        (directory / 'checkpoints').mkdir()
        for role in ('reference', 'candidate'):
            source = case[role]
            target = directory / 'checkpoints' / (role + '.pt')
            before_pin, _ = pin(source['path'])
            require(before_pin == source, 'Selected source changed before snapshot')
            with Path(source['path']).open('rb') as reader, target.open('xb') as writer:
                shutil.copyfileobj(reader, writer, 1 << 20)
                writer.flush(); os.fchmod(writer.fileno(), 0o444); os.fsync(writer.fileno())
            copied, _ = pin(target)
            require(copied['sha256'] == source['sha256'] and pin(source['path'])[0] == source, 'Checkpoint snapshot mismatch')
            plan['checkpoints'][role] = dict(source=source['path'], snapshot=str(target), sha256=source['sha256'])
        for index, role in enumerate(ORDER, 1):
            job = evaluator.Job(Path(plan['checkpoints'][role]['snapshot']), directory / f'{index:02d}-{role}',
                case['experiment'] + '-' + str(index), 'cuda', GPU0, case['ports'][index - 1],
                2400, 3600, 1000, Path('/usr/games/mame'), GAME / 'roms', 2,
                Path(case['boot_assets']['path']).parent, 'inductor', game_boundary_diagnostics=True,
                continuous_guard_manifest=Path(case['effective_guard_manifest']['path']),
                continuous_guard_manifest_sha256=case['effective_guard_manifest']['sha256'])
            plan['legs'].append(dict(index=index, role=role, job=job.plan(), receipt_path=str(job.directory / 'receipt.json')))
        # The boot_assets case PIN selects manifest.json; Job needs its directory.
        plan_pin = publish(directory / 'plan.json', plan)
        publish(directory / 'parent-ownership.json', dict(parent=parent, case=case_pin, plan=plan_pin, lease=str(LEASE)))
        preparation_deadline = time.monotonic() + 1800
        for spec in plan['legs']:
            index = spec['index']
            log = (directory / f'member-{index:02d}.console.log').open('xb'); streams.append(log)
            argv = [case['python']['path'], '-Xgil=0', '-I', '-B', '-u', str(HERE / 'joint_member.py'),
                '--execute', '--manifest', str(args.manifest), '--manifest-sha256', args.manifest_sha256,
                '--case', str(args.case), '--case-sha256', args.case_sha256, '--member', str(index)]
            process = subprocess.Popen(argv, **with_lease(dict(stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, cwd=GAME.parent, start_new_session=True,
                env={**os.environ, 'CUDA_VISIBLE_DEVICES': '',
                    'ROBOTRON_PARALLEL_GPU0_LEASE_FD': str(lease.fileno())}), lease.fileno()))
            owner = dict(pid=process.pid, starttime_ticks=process_start(process.pid), cgroup=None)
            record = dict(index=index, process=process, owner=owner, directory=spec['job']['directory'], argv=argv)
            records.append(record)
            owner['cgroup'] = process_cgroup(process.pid)
            require(owner['starttime_ticks'] is not None, 'Live member start was missed')
            require(owner['cgroup'] == cgroup, 'Member escaped dedicated parent cgroup')
            prepared = wait_stage(record, 'prepared', case_pin['sha256'], preparation_deadline, records, lambda: bool(signals),
                lambda: runtime_guard(case, baseline, capacity, {x['process'].pid for x in records}))
            prepared_contract(prepared, spec, plan)
        publish(directory / 'control/start.json', dict(case_sha256=case_pin['sha256'], parent=parent,
            issued_unix_s=time.time(), issued_monotonic_s=time.monotonic()))
        readiness_deadline = time.monotonic() + 180
        for record in records:
            connected = wait_stage(record, 'connected', case_pin['sha256'], readiness_deadline, records, lambda: bool(signals), lambda: None)
            connected_contract(connected, parent)
        start = decoded((directory / 'control/start.json').read_bytes())
        joint_deadline = start['issued_monotonic_s'] + 3600
        publish(directory / 'control/admit.json', dict(case_sha256=case_pin['sha256'], parent=parent,
            issued_unix_s=time.time(), issued_monotonic_s=time.monotonic(), joint_deadline_monotonic_s=joint_deadline))
        last_health = 0.0
        while True:
            require(not signals and all(x['process'].poll() is None and alive(x['owner']) for x in records),
                'Joint member failure or interruption')
            require(time.monotonic() < joint_deadline, 'Fixed whole-cohort joint budget expired')
            if time.monotonic() - last_health >= 5:
                runtime_guard(case, baseline, capacity, {x['process'].pid for x in records})
                last_health = time.monotonic()
            if all((Path(x['directory']) / 'cohort_complete.json').exists() for x in records):
                completed = [member_message(Path(x['directory']) / 'cohort_complete.json', case_pin['sha256'], x, 'cohort_complete') for x in records]
                starts = [x['cohort_start_unix_s'] for x in completed]
                require(max(starts) - min(starts) <= PROFILE['max_admission_skew_s'], 'Admission start skew exceeded precommit')
                break
            time.sleep(.1)
        publish(directory / 'control/stop.json', dict(case_sha256=case_pin['sha256'], parent=parent,
            reason='all_four_original_cohorts_complete', issued_unix_s=time.time()))
        cleanup_attempted = True
        cleanup_errors = stop_members(records)
        require(not cleanup_errors, '; '.join(cleanup_errors))
        for record in records:
            closure = member_message(Path(record['directory']) / 'closed.json', case_pin['sha256'], record, 'closed')
            require(closure['all_padding_valid'] is True and closure['actor_closure_complete'] is True, 'Member or padding closure failed')
        require(manifest(args.manifest, args.manifest_sha256) == (inventory, manifest_pin), 'Source closure changed')
        report = assess(plan, records, campaign, all_padding_valid=True)
        require(report['outcome'] != 'invalid', 'Invalid fixed-gate assessment cannot close successfully')
        require(cgroup_members(cgroup) == {os.getpid()}, 'Unreaped private descendants remain; normal success refused')
        report.update(after=runtime_guard(case, baseline, capacity, set(), full=True), source_manifest=manifest_pin,
            qualification_is_descriptive=True, automatic_promotion=False, retry=False)
        publish(directory / 'summary.json', report)
    except BaseException as error:
        failure = f'{type(error).__name__}: {error}'
        if directory.exists():
            publish(directory / 'failure.json', dict(outcome='invalid', error=failure, qualification=False,
                original_member_outcomes=[dict(index=x['index'], owner=x['owner'], returncode=x['process'].poll()) for x in records]))
    finally:
        if not cleanup_attempted:
            cleanup_attempted = True
            cleanup_errors = stop_members(records)
        for stream in streams:
            stream.close()
        # A missing closure is not resource release; remaining inherited FD
        # holders and the dedicated cgroup require outside-root closure.
        closures_ok = True
        for record in records:
            path = Path(record['directory']) / 'closed.json'
            try:
                closed = member_message(path, case_pin['sha256'], record, 'closed')
                closures_ok &= closed['actor_closure_complete'] is True
                closures_ok &= all(not alive(x) for x in closed['actors'])
            except Exception:
                closures_ok = False
        closures_ok &= all(x['process'].poll() is not None for x in records)
        closures_ok &= cgroup_members(cgroup) == {os.getpid()}
        if not closures_ok or cleanup_errors:
            failure = failure or 'Owned member/descendant closure incomplete'
            if directory.exists() and not (directory / 'cleanup-incomplete.json').exists():
                publish(directory / 'cleanup-incomplete.json', dict(status='NATIVE_FAILURE_EXTERNAL_OWNED_CGROUP_CLOSURE_REQUIRED',
                    reason='Missing/failed member or descendant closure', errors=cleanup_errors,
                    recovery_required=True, qualification=False, automatic_retry=False,
                    parent_FD_closes_at_exit_inherited_member_and_actor_descriptions_remain=True,
                    outside_root_must_archive_and_verify_cgroup_GPU_ports_empty_before_reuse=True))
        # On failure, systemd owns the precommitted cgroup stop/240s/KILL bound.
        # Child holders inherit this SAME open description; nobody calls LOCK_UN.
        # Closing the parent's FD is not a resource-release claim. Root closure is external.
        lease.close(); released = bool(closures_ok and not cleanup_errors)
        for number, handler in prior.items():
            signal.signal(number, handler)
    print(json.dumps(dict(outcome=(report or {}).get('outcome', 'invalid'), error=failure,
        lease_released=released, automatic_promotion=False)))
    return 0 if failure is None and report is not None else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--case', type=Path)
    parser.add_argument('--case-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: unselected joint four-member profile; no reads/imports/processes/controls; full A/A and capacity review required')
        return 0
    require(all((args.manifest, args.manifest_sha256, args.case, args.case_sha256)), 'Explicit pinned future root inputs required')
    return execute(args)


if __name__ == '__main__':
    raise SystemExit(main())
