#!/usr/bin/env python3
"""One root-bound phase snapshot; default prints a literal PLAN without reads."""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import io
import shlex
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import sys
import traceback
import types

HERE = Path(__file__).parent
ORIGINAL_PATH = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/live8-maintenance-checkpoint-CPU-verifier-proposal-20261017/verify_maintenance_checkpoint.py')
ORIGINAL_SHA256 = '7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
STRICT_PATH = HERE / 'strict_phase_base_2048.py'
STRICT_SHA256 = '47677509f170c4c3b6a1c03918e02ab13996af1ceafffac29b7536c2fad61f80'
SCHEMA = 'robotron-batch2048-phase-snapshot-checkpoint-CPU-job-reviewed2-v1'
RESULT_SCHEMA = 'robotron-batch2048-phase-snapshot-checkpoint-CPU-result-reviewed2-v1'
ACQUISITION_SCHEMA = 'robotron-owned-phase-snapshot-acquisition-v1'
PHASE_SCHEMA = 'robotron-priority-metric-phase-v1'
PROFILE_PATH = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_profile_horizon_proposal/profile.json')
PROFILE_SHA256 = 'e755e22ade5cb56537b08f41f412e856da09435d88e4e71e09b22aba521eac50'
PROFILE_BYTES = 764
PROFILE_SCHEMA = 'robotron-ce-batch2048-efficacy-profile-v1'
BASE_4096_SHA256 = '9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
SOURCE_NAMES = ('__init__.py', 'model.py', 'config.py', 'learning_control.py',
                'agent.py', 'training.py', 'loss_kernel.py', 'priority_phase.py')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(value, label):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'Invalid SHA: ' + label)
    return value


def clocks(value, label):
    require(isinstance(value, dict) and set(value) == set(CLOCKS), 'Four clocks required: ' + label)
    require(all(type(v) is int and v > 0 for v in value.values()), 'Positive integer clocks required: ' + label)
    return value


def triple(value, label):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256', 'bytes'}, 'Checkpoint triple required: ' + label)
    path = Path(value['path'])
    # Historical boot/origin paths may now contain newer bytes. Never resolve or
    # open them as if their old content still occupied the path.
    require(path.is_absolute() and '..' not in path.parts and str(path) == value['path'], 'Invalid historical path: ' + label)
    sha(value['sha256'], label)
    require(type(value['bytes']) is int and value['bytes'] > 0, 'Invalid bytes: ' + label)
    return value


def load_base():
    original = ORIGINAL_PATH.read_bytes()
    require(hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256, 'Original strict verifier changed')
    data = STRICT_PATH.read_bytes()
    require(hashlib.sha256(data).hexdigest() == STRICT_SHA256, 'Phase strict helper changed')
    normalized = data.replace(b'HELD_RECIPE_CONTEXT = dict(batch_size=2048', b'HELD_RECIPE_CONTEXT = dict(batch_size=4096').replace(
        b"DQN_BATCH_SIZE='2048'", b"DQN_BATCH_SIZE='4096'").replace(
        b"    raise RuntimeError('Private2048 numerical base: use the profile-bound phase entrypoint')\n", b'')
    require(hashlib.sha256(normalized).hexdigest() == BASE_4096_SHA256, 'Only exact batch/private-entry changes allowed')
    data4096 = normalized
    old = b'def validate_checkpoint(path, floor, evidence):'
    new = b'def validate_checkpoint(path, floor, evidence, *, metadata_callback=None):'
    hook = b'    if metadata_callback is not None:\n        metadata_callback(checkpoint, evidence)\n'
    require(data.count(new) == 1 and data.count(hook) == 1 and
            data4096.replace(new, old).replace(hook, b'') == original,
            'Only the optional signature/end-metadata callback may differ')
    module = types.ModuleType('_phase_snapshot_strict_body')
    module.__file__ = str(STRICT_PATH)
    exec(compile(data, str(STRICT_PATH), 'exec'), module.__dict__)
    return module


def immutable(pin, base, evidence, label, *, as_json=False):
    value = base.pinned_json(pin, evidence, label) if as_json else base.check_pin(pin, evidence, label, metadata=True)
    observed = evidence['bound_files'][label]
    require(observed['mode'] == '0o444' and observed['uid'] == os.getuid() and observed['nlink'] == 1,
            'Owned readonly metadata/source archive required: ' + label)
    return value


def read_job(args, base):
    require(args.job is not None, 'Explicit root job required')
    sha(args.expected_job_sha256, 'root job'); sha(args.expected_verifier_sha256, 'entrypoint')
    source = base.fingerprint(Path(__file__).resolve())
    require(source['sha256'] == args.expected_verifier_sha256, 'Entrypoint source changed')
    path = base.canonical(str(args.job))
    require(path.stat().st_size <= base.MAX_JOB, 'Root job exceeds1MiB')
    pin = base.fingerprint(path)
    require(pin['sha256'] == args.expected_job_sha256 and pin['mode'] == '0o444' and
            pin['uid'] == os.getuid() and pin['nlink'] == 1, 'Root job must be exact owned0444 metadata')
    job = json.loads(path.read_text())
    require(base.fingerprint(path) == pin, 'Root job changed while parsing')
    fields = {'schema', 'verifier_sha256', 'strict_phase_base_sha256', 'original_strict_base_sha256',
              'experiment', 'source', 'verification_copy', 'clock_floor', 'source_control_context',
              'output_directory', 'phase_snapshot', 'batch2048_context'}
    require(isinstance(job, dict) and set(job) == fields and job['schema'] == SCHEMA and
            job['verifier_sha256'] == source['sha256'] and job['strict_phase_base_sha256'] == STRICT_SHA256 and
            job['original_strict_base_sha256'] == ORIGINAL_SHA256, 'Phase root job/source schema differs')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,120}', job['experiment'] or ''), 'Invalid experiment')
    clocks(job['clock_floor'], 'current acquisition floor')
    output = base.canonical(job['output_directory'], exists=False)
    require(not output.exists() and output.parent.is_dir() and output.parent.stat().st_uid == os.getuid(),
            'Output must be NEW under owned parent')
    return job, pin, source, output


def precise_unit(unit, owner):
    require(unit['argv'] == ['systemctl', '--user', '--timestamp=us+utc', 'show', owner['unit'], '--all']
            and unit.get('environment_overrides') == {'TZ': 'UTC'} and unit['returncode'] == 0,
            'Exact successful UTC microsecond producer unit show required')
    shown = dict(line.split('=', 1) for line in unit['stdout'].splitlines() if '=' in line)
    require(shown.get('MainPID') == shown.get('ExecMainPID') == str(owner['pid'])
            and shown.get('InvocationID') == owner['invocation_id'] and shown.get('NRestarts') == '0'
            and shown.get('Restart') == 'no' and shown.get('ControlGroup') == owner['cgroup'],
            'Actual producer unit owner differs')
    text = shown.get('ExecMainStartTimestamp', '')
    require(re.fullmatch(r'[A-Z][a-z]{2} [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6} UTC', text),
            'Authoritative unit start must retain UTC microseconds')
    start = datetime.strptime(text, '%a %Y-%m-%d %H:%M:%S.%f UTC').replace(tzinfo=timezone.utc)
    require(start.strftime('%a %Y-%m-%d %H:%M:%S.%f UTC') == text,
            'Unit start calendar differs')
    mono = shown.get('ExecMainStartTimestampMonotonic', '')
    require(mono.isdecimal() and int(mono) > 0, 'Original unit monotonic start missing')
    environment = dict(part.split('=', 1) for part in shlex.split(shown.get('Environment', '')) if '=' in part)
    require(environment.get('DQN_BATCH_SIZE') == '2048' and environment.get('DQN_PER_PRIORITY_METRIC') == 'ce',
            'Dedicated producer unit2048/CE environment missing')
    delta = start - datetime(1970, 1, 1, tzinfo=timezone.utc)
    micros = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    return shown, micros


def check_producer_csv_origin(job, observation, environment, unit, row, base, evidence):
    """Validate archived root collection facts; never reopen the live source CSV."""
    origin = immutable(observation['csv_origin'], base, evidence, 'batch2048/producer_csv_origin', as_json=True)
    fields = {'schema', 'owner_before', 'owner_after', 'environment_before', 'environment_after',
              'unit_before', 'unit_after', 'csv_archive', 'source_csv', 'header_bytes',
              'row_start_offset', 'row_end_offset', 'header_sha256', 'row_sha256',
              'observed_before_unix_s', 'observed_after_unix_s'}
    require(isinstance(origin, dict) and set(origin) == fields
            and origin['schema'] == 'robotron-root-batch2048-producer-CSV-origin-v2', 'Exact producer CSV origin required')
    owner = observation['owner']
    require(base.trainer_identity(origin['owner_before']) == base.trainer_identity(origin['owner_after']) == owner,
            'CSV collection owner changed')
    require(origin['environment_before'] == observation['environment'] and origin['unit_before'] == observation['trainer_unit']
            and origin['csv_archive'] == observation['csv'], 'CSV origin does not join original observations')
    env_after = immutable(origin['environment_after'], base, evidence, 'batch2048/environment_after', as_json=True)
    unit_after = immutable(origin['unit_after'], base, evidence, 'batch2048/unit_after', as_json=True)
    require(env_after == environment, 'Producer environment changed across CSV collection')
    before_fields, start_us = precise_unit(unit, owner)
    after_fields, after_start_us = precise_unit(unit_after, owner)
    stable = ('MainPID', 'ExecMainPID', 'InvocationID', 'ControlGroup', 'NRestarts', 'Restart',
              'ExecMainStartTimestamp', 'ExecMainStartTimestampMonotonic', 'Environment')
    require(all(before_fields.get(k) == after_fields.get(k) for k in stable) and start_us == after_start_us,
            'Original producer unit changed across CSV collection')
    declared_start = Decimal(str(observation['producer_started_unix_s']))
    require(declared_start == Decimal(start_us) / 1000000, 'Declared producer start differs from original precise unit start')
    times = [origin[k] for k in ('observed_before_unix_s', 'observed_after_unix_s')]
    require(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in times)
            and declared_start <= Decimal(str(times[0])) <= Decimal(str(times[1]))
            and times[1] == observation['observed_unix_s'], 'CSV collection chronology differs')
    raw = Path(observation['csv']['path']).read_bytes()
    lines = raw.splitlines(keepends=True)
    require(len(lines) == 2 and all(line.endswith(b'\n') for line in lines), 'Archive must retain exact complete header and one row bytes')
    parsed = list(csv.reader(io.StringIO(raw.decode('utf-8'))))
    require(len(parsed) == 2 and len(parsed[0]) == len(parsed[1]) and len(set(parsed[0])) == len(parsed[0])
            and dict(zip(parsed[0], parsed[1])) == row, 'CSV header/row geometry or parse differs')
    require(type(origin['header_bytes']) is int and origin['header_bytes'] == len(lines[0])
            and origin['header_sha256'] == hashlib.sha256(lines[0]).hexdigest()
            and origin['row_sha256'] == hashlib.sha256(lines[1]).hexdigest(), 'CSV byte archive differs from source-row evidence')
    source = origin['source_csv']
    require(isinstance(source, dict) and set(source) == {'path', 'regular_file', 'opened_nofollow',
            'fd_before', 'path_before', 'fd_after', 'path_after'} and source['regular_file'] is True
            and source['opened_nofollow'] is True, 'Exact regular nofollow source CSV evidence required')
    run_dir = environment.get('ROBOTRON_RUN_DIR')
    require(type(run_dir) is str and Path(run_dir).is_absolute() and '..' not in Path(run_dir).parts
            and source['path'] == str(Path(run_dir) / 'training.csv'), 'CSV source is not the actual producer run-directory file')
    identity_keys = {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'nlink'}
    for key in ('fd_before', 'path_before', 'fd_after', 'path_after'):
        value = source[key]
        require(isinstance(value, dict) and set(value) == identity_keys
                and all(type(value[k]) is int and value[k] >= 0 for k in identity_keys - {'mode'})
                and value['uid'] == os.getuid() and value['nlink'] == 1
                and value['mode'] in ('0o600', '0o640', '0o644', '0o660', '0o664'), 'CSV source identity/ownership differs')
    first, last = source['fd_before'], source['fd_after']
    require(first == source['path_before'] and last == source['path_after']
            and all(first[k] == last[k] for k in ('device', 'inode', 'uid', 'nlink', 'mode'))
            and last['bytes'] >= first['bytes'] and last['mtime_ns'] >= first['mtime_ns'], 'CSV FD/path replaced or truncated across read')
    begin, end = origin['row_start_offset'], origin['row_end_offset']
    require(type(begin) is int and type(end) is int and begin >= len(lines[0])
            and end == begin + len(lines[1]) and end <= first['bytes'] <= last['bytes'], 'CSV source row offsets differ')
    stamp = row.get('utc', '')
    require(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)', stamp),
            'CSV UTC must be timezone-aware with retained producer precision')
    actual = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    delta = actual - datetime(1970, 1, 1, tzinfo=timezone.utc)
    row_us = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    require(start_us <= row_us and Decimal(row_us) / 1000000 <= Decimal(str(times[1])),
            'CSV row predates the exact new owner or comes from the future')
    require(row.get('experiment') == job['experiment'] and row.get('measurement_active') == 'False',
            'CSV experiment/nonmeasurement mode differs')
    floor = clocks(evidence['actual_boot_clocks'], 'genuine already-verified boot clocks')
    for source_name, name in (('steps', 'training_steps'), ('optimized_samples', 'optimized_samples'),
                              ('learner_frames', 'learner_frame_count'), ('frames', 'frame_count')):
        value = row.get(source_name, '')
        require(value.isdecimal() and int(value) >= floor[name], 'CSV clock predates genuine boot: ' + name)
    evidence.update(producer_CSV_origin_verified=True, producer_CSV_row_utc=stamp,
                    producer_start_unix_us=start_us, producer_CSV_origin=origin)


def check_batch2048_context(job, base, evidence):
    context = job['batch2048_context']
    require(isinstance(context, dict) and set(context) == {'profile', 'role', 'producer_observation'}, 'Exact2048 profile/producer bindings required')
    pin = context['profile']
    require(pin['path'] == str(PROFILE_PATH) and pin['sha256'] == PROFILE_SHA256 and pin['bytes'] == PROFILE_BYTES,
            'Only the exact reviewed2048 profile is accepted')
    profile = immutable(pin, base, evidence, 'batch2048/profile', as_json=True)
    require(profile['schema'] == PROFILE_SCHEMA and profile['profile_id'] == 'ce_batch2048_efficacy_screen_v1'
            and profile['batch_size'] == 2048 and profile['before_batch_size'] == profile['return_batch_size'] == 4096
            and profile['priority_metric'] == 'ce' and profile['LR_compensation'] is False
            and profile['deliberate_recipe_changes'] == ['DQN_BATCH_SIZE']
            and profile['held_recipe_context'] == base.HELD_RECIPE_CONTEXT, 'Exact2048 held recipe differs')
    roles = {'treatment_startup': 'startup', 'early_insurance': 'candidate', 'candidate': 'candidate', 'newest_stopped': 'newest_stopped'}
    role = context['role']; spec = job['phase_snapshot']
    require(role in roles and spec['purpose'] == roles[role], 'Explicit producer role/acquisition purpose differs')
    if role == 'treatment_startup':require(spec['observed_clients'] == 0, 'Treatment startup must be genuine client0')
    if role == 'early_insurance':require(spec['observed_clients'] == 192, 'Early insurance must be genuine client192')
    observation = immutable(context['producer_observation'], base, evidence, 'batch2048/producer', as_json=True)
    fields = {'schema', 'experiment', 'profile_sha256', 'owner', 'source_checkpoint', 'acquisition_sha256',
              'environment', 'trainer_unit', 'csv', 'csv_scope', 'csv_origin', 'producer_started_unix_s', 'observed_unix_s'}
    require(isinstance(observation, dict) and set(observation) == fields
            and observation['schema'] == 'robotron-root-batch2048-producer-observation-v1'
            and observation['profile_sha256'] == PROFILE_SHA256 and observation['experiment'] == job['experiment']
            and base.trainer_identity(observation['owner']) == job['phase_snapshot']['owner']
            and observation['source_checkpoint'] == {k:job['source'][k] for k in ('path', 'sha256', 'bytes')}
            and observation['acquisition_sha256'] == job['phase_snapshot']['acquisition']['sha256']
            and job['phase_snapshot']['expected_phase']['metric'] == 'ce', 'Actual2048 producer/CE/acquisition/checkpoint join differs')
    environment = immutable(observation['environment'], base, evidence, 'batch2048/environment', as_json=True)
    require(isinstance(environment, dict) and environment.get('DQN_BATCH_SIZE') == '2048'
            and environment.get('DQN_PER_PRIORITY_METRIC') == 'ce', 'Actual producer selected environment differs')
    unit = immutable(observation['trainer_unit'], base, evidence, 'batch2048/trainer_unit', as_json=True)
    owner = observation['owner']
    require(unit['argv'] == ['systemctl', '--user', '--timestamp=us+utc', 'show', owner['unit'], '--all']
            and unit.get('environment_overrides') == {'TZ': 'UTC'} and unit['returncode'] == 0,
            'Exact successful original UTC microsecond producer unit show required')
    shown = dict(line.split('=', 1) for line in unit['stdout'].splitlines() if '=' in line)
    require(shown.get('MainPID') == shown.get('ExecMainPID') == str(owner['pid'])
            and shown.get('InvocationID') == owner['invocation_id'] and shown.get('NRestarts') == '0'
            and shown.get('Restart') == 'no' and shown.get('ControlGroup') == owner['cgroup'], 'Actual producer unit owner differs')
    unit_env = dict(part.split('=', 1) for part in shlex.split(shown.get('Environment', '')) if '=' in part)
    require(unit_env.get('DQN_BATCH_SIZE') == '2048' and unit_env.get('DQN_PER_PRIORITY_METRIC') == 'ce',
            'Dedicated producer unit2048/CE environment missing')
    immutable(observation['csv'], base, evidence, 'batch2048/csv')
    rows = list(csv.DictReader(io.StringIO(Path(observation['csv']['path']).read_text())))
    require(len(rows) == 1, 'One genuine archived CSV header/row required')
    times = [observation[k] for k in ('producer_started_unix_s', 'observed_unix_s')]
    require(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in times) and times[0] <= times[1], 'Producer observation chronology differs')
    verified = observation['csv_scope'] == 'producer2048'
    if verified:
        require(rows[0].get('batch_size') == '2048', 'Actual producer CSV2048 required')
        check_producer_csv_origin(job, observation, environment, unit, rows[0], base, evidence)
    else:
        require(role == 'treatment_startup' and spec['purpose'] == 'startup' and spec['observed_clients'] == 0
                and observation['csv_scope'] == 'pretransition_baseline4096' and rows[0].get('batch_size') == '4096',
                'Only explicit treatment startup client0 may retain baseline CSV4096')
        origin = immutable(observation['csv_origin'], base, evidence, 'batch2048/pretransition_csv_origin', as_json=True)
        require(set(origin) == {'schema', 'scope', 'profile_sha256', 'owner', 'csv', 'captured_unix_s', 'transition_started_unix_s'}
                and origin['schema'] == 'robotron-root-pretransition-batch2048-CSV-v1' and origin['scope'] == 'pretransition_baseline4096'
                and origin['profile_sha256'] == PROFILE_SHA256 and origin['csv'] == observation['csv']
                and base.trainer_identity(origin['owner']) != owner, 'Genuine existing pretransition CSV PIN/scope required')
        before = [origin[k] for k in ('captured_unix_s', 'transition_started_unix_s')]
        require(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in before)
                and before[0] <= before[1] < times[0] <= times[1]
                and type(origin['csv']['identity'].get('mtime_ns')) is int
                and origin['csv']['identity']['mtime_ns'] / 1e9 <= before[0], 'Pretransition CSV archive/start chronology differs')
    evidence.update(batch2048_profile=profile, batch2048_producer=observation, configured_batch_size=2048,
        producer_CSV_verified=verified, observed_CSV_batch_size=int(rows[0]['batch_size']), actual_producer_batch_size=2048 if verified else None,
        producer_batch_scope='Root-pinned configured2048/CE environment+unit. A labeled treatment-startup baseline4096 CSV is not2048 producer evidence; all later roles require actual2048 CSV. Saved baseline512/boot profile never selects active batch.')


def historical_archive(pair, actual_path, base, evidence, label):
    """Join root's historical mutable-slot PIN to its immutable byte archive."""
    require(isinstance(pair, dict) and set(pair) == {'actual_pin', 'archive'}, 'Historical slot/archive pair required')
    old = pair['actual_pin']
    require(set(old) == {'path', 'sha256', 'bytes', 'identity'} and old['path'] == str(actual_path), 'Wrong historical slot path')
    sha(old['sha256'], label)
    require(type(old['bytes']) is int and old['bytes'] > 0 and isinstance(old['identity'], dict) and
            set(old['identity']) == {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'nlink'} and
            old['identity']['bytes'] == old['bytes'], 'Incomplete historical slot identity')
    value = immutable(pair['archive'], base, evidence, label, as_json=True)
    require(pair['archive']['sha256'] == old['sha256'] and pair['archive']['bytes'] == old['bytes'] and
            pair['archive']['path'] != old['path'], 'Historical slot archive bytes differ or alias mutable path')
    return value


def check_acquisition(job, base, evidence, model_dir):
    spec = job['phase_snapshot']
    fields = {'purpose', 'owner', 'observed_clients', 'phase_record', 'boot_checkpoint',
              'boot_verification', 'expected_phase', 'acquisition', 'sources'}
    require(isinstance(spec, dict) and set(spec) == fields and
            spec['purpose'] in ('startup', 'candidate', 'newest_stopped'), 'Honest phase_snapshot role required')
    owner = base.trainer_identity(spec['owner'])
    require(type(spec['observed_clients']) is int and spec['observed_clients'] in (0, 192), 'Explicit actual0or192 client scope required')
    for name, pair in spec['sources'].items():
        require(name in SOURCE_NAMES and set(pair) == {'current', 'archive'}, 'Invalid phase source pair')
        require(pair['current']['path'] == str(base.GAME / 'Scripts/dqn' / name), 'Phase source path escaped')
        current = base.check_pin(pair['current'], evidence, 'phase_source/' + name, metadata=True)
        archive = immutable(pair['archive'], base, evidence, 'phase_source_archive/' + name)
        require(current['sha256'] == archive['sha256'] and current['bytes'] == archive['bytes'] and
                (current['device'], current['inode']) != (archive['device'], archive['inode']), 'Source archive must independently match actual installed source')
        if name in base.MODEL_NAMES:
            require(pair['current'] == job['source_control_context']['model_package'][name], 'Numerical/current source context differs')
    require(set(spec['sources']) == set(SOURCE_NAMES), 'Four model plus candidate-five source union required')
    record = immutable(spec['phase_record'], base, evidence, 'phase_record', as_json=True)
    boot = immutable(spec['boot_verification'], base, evidence, 'boot_CPU_proof', as_json=True)
    triple(spec['boot_checkpoint'], 'actual boot checkpoint')
    require(boot.get('status') == 'PASS' and boot['sha256'] == spec['boot_checkpoint']['sha256'] and
            boot['bytes'] == spec['boot_checkpoint']['bytes'], 'Actual boot CPU proof/checkpoint bytes differ')
    boot_clocks = {key: boot['clocks'][key] for key in CLOCKS}; clocks(boot_clocks, 'actual boot CPU clocks')
    require(all(job['clock_floor'][key] >= boot_clocks[key] for key in CLOCKS), 'Acquisition floor predates actual boot')
    expected = spec['expected_phase']
    require(isinstance(expected, dict) and set(expected) == {'metric', 'phase_id', 'root_precommit_sha256',
            'founder_phase_record_sha256', 'last_resume_record_sha256', 'started_from', 'valid'} and
            expected['metric'] in ('ce', 'kl') and expected['valid'] is True and
            re.fullmatch(r'[A-Za-z0-9_-]{1,100}', expected['phase_id'] or ''), 'Expected phase identity differs')
    for key in ('root_precommit_sha256', 'founder_phase_record_sha256'):sha(expected[key], key)
    if expected['last_resume_record_sha256'] is not None:sha(expected['last_resume_record_sha256'], 'resume record')
    require(isinstance(expected['started_from'], dict) and set(expected['started_from']) == {'path', 'sha256', 'bytes', 'clocks'}, 'Expected founder checkpoint/clocks required')
    triple({k:expected['started_from'][k] for k in ('path', 'sha256', 'bytes')}, 'founder checkpoint')
    clocks(expected['started_from']['clocks'], 'founder clocks')
    require(set(record) == {'schema', 'phase_id', 'metric', 'action', 'previous_metric', 'checkpoint', 'model_dir', 'root_precommit_sha256'} and
            record['schema'] == 'robotron-priority-metric-start-v1' and record['phase_id'] == expected['phase_id'] and
            record['metric'] == expected['metric'] and record['root_precommit_sha256'] == expected['root_precommit_sha256'] and
            record['checkpoint'] == spec['boot_checkpoint'] and record['model_dir'] == str(model_dir) and
            record['action'] in ('start', 'resume'), 'Current startup record/actual boot binding differs')
    predecessor = boot.get('saved_priority_metric_phase')
    if record['action'] == 'start':
        require(expected['founder_phase_record_sha256'] == spec['phase_record']['sha256'] and
                expected['last_resume_record_sha256'] is None and
                expected['started_from'] == dict(spec['boot_checkpoint'], clocks=boot_clocks), 'New phase must name actual boot, not a historical founder')
        require(record['previous_metric'] == ('unknown' if predecessor is None else predecessor['metric']) and
                (predecessor is None or predecessor['phase_id'] != expected['phase_id']), 'New phase predecessor/identity differs')
    else:
        require(isinstance(predecessor, dict) and predecessor.get('valid') is True and record['previous_metric'] == expected['metric'] and
                all(predecessor[key] == expected[key] for key in ('metric', 'phase_id', 'root_precommit_sha256', 'started_from')) and
                predecessor['phase_record_sha256'] == expected['founder_phase_record_sha256'] and
                expected['last_resume_record_sha256'] == spec['phase_record']['sha256'], 'Resume must preserve original founder and name only current resume record')
    proof = immutable(spec['acquisition'], base, evidence, 'phase_acquisition', as_json=True)
    require(proof['schema'] == ACQUISITION_SCHEMA and proof['purpose'] == spec['purpose'] and
            proof['experiment'] == job['experiment'] and proof['model_dir'] == str(model_dir) and
            proof['owner_before'] == proof['owner_after'] == owner and proof['client_count'] == spec['observed_clients'] and
            proof['source_checkpoint'] == {key:job['source'][key] for key in ('path', 'sha256', 'bytes')} and
            proof['clock_floor'] == job['clock_floor'] and proof['phase_record_sha256'] == spec['phase_record']['sha256'] and
            proof['boot_checkpoint'] == spec['boot_checkpoint'], 'Root-owned phase acquisition/owner/floor/source differs')
    if spec['purpose'] == 'newest_stopped':
        require(proof['tag'] is None and proof['completed_slot_transition'] is None and
                job['source']['path'] == str(model_dir / 'robotron_dqn_latest.pt'), 'Stopped source must be actual newest latest')
        absence = immutable(proof['stopped_absence'], base, evidence, 'phase_stopped_absence', as_json=True)
        require(absence.get('schema') == base.ABSENCE_SCHEMA and absence.get('trainer') == owner and
                absence.get('unit_main_pid') == 0 and absence.get('unit_active_state') == 'inactive' and
                absence.get('old_process_absent') is True and absence.get('owned_cgroup_empty') is True and
                absence.get('latest_path') == job['source']['path'], 'Actual known retired owner absence required')
        evidence['absence_before'] = base.exact_absence(owner)
    else:
        tag = proof['tag']; require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}', tag or ''), 'Unique actual snapshot tag required')
        require(proof['stopped_absence'] is None and job['source']['path'] == str(model_dir / 'managed-checkpoints' / (tag + '.pt')), 'Tagged snapshot source differs')
        transition = proof['completed_slot_transition']; require(isinstance(transition, dict) and set(transition) == {'before', 'request', 'after', 'before_unix_s', 'request_unix_s', 'after_unix_s'}, 'Actual request/slot transition bracket required')
        times = [transition[key] for key in ('before_unix_s', 'request_unix_s', 'after_unix_s')]
        require(all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in times) and times[0] <= times[1] <= times[2], 'Snapshot transition chronology differs')
        slot = model_dir / 'managed_save.request.json.completed'
        if transition['before'] is not None:
            previous = historical_archive(transition['before'], slot, base, evidence, 'completed_slot_before_archive')
            require(previous != {'tag':tag}, 'Same old completed tag is not a fresh transition')
        requested = historical_archive(transition['request'], model_dir / 'managed_save.request.json', base, evidence, 'request_archive')
        completed = historical_archive(transition['after'], slot, base, evidence, 'completed_slot_after_archive')
        require(requested == completed == {'tag':tag}, 'Actual request/completion tag differs')
    # Every context archive is immutable; historical mutable slots themselves are
    # never reread, and no current owner/API is inferred from their old metadata.
    for label, observed in evidence['bound_files'].items():
        if label.startswith(('archived_', 'provenance/')):
            require(observed['mode'] == '0o444' and observed['uid'] == os.getuid() and observed['nlink'] == 1, 'Readonly context archive required: ' + label)
    evidence.update(actual_boot_checkpoint=spec['boot_checkpoint'], actual_boot_clocks=boot_clocks,
                    phase_startup_record=record, phase_acquisition=proof,
                    owner_scope='Root-pinned historical acquisition; only newest_stopped performs exact named old-owner absence reads')
    return spec, boot, record


def verify_phase(checkpoint, evidence, expected, boot_clocks, floor, action, predecessor=None):
    phase = checkpoint.get('priority_metric_phase')
    require(isinstance(phase, dict) and phase.get('schema') == PHASE_SCHEMA and phase.get('valid') is True and
            phase.get('invalid_reason') is None, 'Saved valid phase metadata missing')
    for key in ('metric', 'phase_id', 'root_precommit_sha256', 'started_from', 'valid'):
        require(phase.get(key) == expected[key], 'Saved phase mismatch: ' + key)
    require(phase.get('phase_record_sha256') == expected['founder_phase_record_sha256'] and
            phase.get('last_resume_record_sha256') == expected['last_resume_record_sha256'], 'Saved founder/resume record differs')
    for key in ('priority_update_calls', 'ring_rows_submitted'):
        require(type(phase.get(key)) is int and phase[key] >= 0, 'Invalid phase counter: ' + key)
        if action == 'resume':require(phase[key] >= predecessor[key], 'Resume regressed phase counter: ' + key)
    expected_predecessor = (None if predecessor is None else
        {key:predecessor.get(key) for key in ('phase_id', 'metric', 'valid')}) if action == 'start' else predecessor.get('predecessor')
    require(phase.get('predecessor') == expected_predecessor, 'Saved predecessor lineage differs')
    current = {key:checkpoint[key] for key in CLOCKS}
    require(all(type(current[k]) is int and current[k] >= max(floor[k], boot_clocks[k], expected['started_from']['clocks'][k]) for k in CLOCKS), 'Saved current clocks predate acquisition/actual boot/founder')
    evidence.update(saved_priority_metric_phase=copy.deepcopy(phase), phase_metadata_verified=True,
        phase_current_clocks=current, phase_current_overshoot_from_floor={k:current[k]-floor[k] for k in CLOCKS},
        phase_current_overshoot_from_actual_boot={k:current[k]-boot_clocks[k] for k in CLOCKS},
        phase_scope='Saved snapshot metadata under pinned actual sources: snapshot() requires finish_load. Current clocks may advance; this is not exact restoration/coherent-anchor or leaf-migration proof.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256'); parser.add_argument('--expected-verifier-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: explicit phase_snapshot root job required; no reads, imports, outputs or runtime queries')
        return 0
    evidence = base = output = None
    try:
        require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and 'LD_PRELOAD' not in os.environ and 'PYTHONPATH' not in os.environ, 'Start CUDAhidden without preload/PYTHONPATH')
        require(not any(n == 'torch' or n.startswith('torch.') or n == 'numpy' or n.startswith('dqn') for n in sys.modules), 'Fresh stdlib-only interpreter required')
        base = load_base(); job, job_pin, self_pin, output = read_job(args, base)
        base.DIRECTORY = output; output.mkdir(mode=0o700, exist_ok=False)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); resource.setrlimit(resource.RLIMIT_FSIZE, (32 << 20, 32 << 20))
        evidence = dict(schema=RESULT_SCHEMA, status='RUNNING', utc=base.now(), root_job=job, job_file=job_pin,
                        script=self_pin, role='phase_snapshot', scope='Strict CPU checkpoint plus saved phase lineage; no quality/learning/coherent restore claim')
        base_pin = base.fingerprint(STRICT_PATH); original_pin = base.fingerprint(ORIGINAL_PATH)
        require(base_pin['sha256'] == STRICT_SHA256 and original_pin['sha256'] == ORIGINAL_SHA256, 'Strict source changed')
        evidence.update(strict_phase_base=base_pin, original_strict_base=original_pin)
        model_dir = base.check_context(job, evidence)
        spec, boot, record = check_acquisition(job, base, evidence, model_dir)
        check_batch2048_context(job, base, evidence)
        copied = base.check_root_copy(job, evidence)
        base.validate_checkpoint(copied, job['clock_floor'], evidence, metadata_callback=lambda checkpoint, ev:
            verify_phase(checkpoint, ev, spec['expected_phase'], evidence['actual_boot_clocks'], job['clock_floor'],
                         record['action'], boot.get('saved_priority_metric_phase')))
        if spec['purpose'] == 'newest_stopped':evidence['absence_after'] = base.exact_absence(spec['owner'])
        for label, before in evidence['bound_files'].items():require(base.fingerprint(before['path']) == before, 'Bound file changed: ' + label)
        require(base.fingerprint(args.job) == job_pin and base.fingerprint(Path(__file__).resolve()) == self_pin and
                base.fingerprint(STRICT_PATH) == base_pin and base.fingerprint(ORIGINAL_PATH) == original_pin, 'Job/verifier source changed')
        evidence.update(status='PASS', finished_utc=base.now(), path=str(copied), sha256=job['verification_copy']['sha256'],
                        bytes=job['verification_copy']['bytes'], actual_restore_or_optimizer_step=False, actual_quality_qualification=False)
        base.publish(output / 'cpu-verification.json', evidence)
        print(json.dumps(dict(status='PASS', role='phase_snapshot', purpose=spec['purpose'], sha256=evidence['sha256'],
                              clocks=evidence['clocks'], saved_priority_metric_phase=evidence['saved_priority_metric_phase']), indent=2))
        return 0
    except BaseException as error:
        if evidence is not None:
            evidence.update(status='FAIL', finished_utc=base.now(), error=repr(error), traceback=traceback.format_exc())
            try:base.publish(output / 'verification-error.json', evidence)
            except BaseException as secondary:print('Secondary evidence error: ' + repr(secondary), file=sys.stderr)
        traceback.print_exc(); return 1


if __name__ == '__main__':
    raise SystemExit(main())
