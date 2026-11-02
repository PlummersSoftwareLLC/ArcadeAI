#!/usr/bin/env python3
"""One root-bound phase snapshot; default prints a literal PLAN without reads."""
import argparse
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
STRICT_PATH = HERE / 'strict_phase_base_lr25.py'
STRICT_SHA256 = '0854f1437510a4264bc922d241e76350ee3209963bd4f28ce9b8a826e6cb159b'
SCHEMA = 'robotron-lr25-phase-snapshot-checkpoint-CPU-job-v1'
RESULT_SCHEMA = 'robotron-lr25-phase-snapshot-checkpoint-CPU-result-v1'
ACQUISITION_SCHEMA = 'robotron-owned-phase-snapshot-acquisition-v1'
PHASE_SCHEMA = 'robotron-priority-metric-phase-v1'
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
SOURCE_NAMES = ('__init__.py', 'model.py', 'config.py', 'learning_control.py',
                'agent.py', 'training.py', 'loss_kernel.py', 'priority_phase.py')

BASE_REPLACEMENTS = ((b'learning_control_lr_scale=.5', b'learning_control_lr_scale=.25'),
    (b'optimizer_lr=2.5e-5', b'optimizer_lr=1.25e-5'),
    (b"control['lr_scale'] == .5", b"control['lr_scale'] == .25"))
BASE_CLI_REFUSAL = b"    if args.execute:\n        raise RuntimeError('Use verify_phase_snapshot_lr25.py: explicit hot-change context and CE lineage required')\n"
FOUNDER_SHA256 = '9b3b839fe39044538412f0f78a8c28feae60170ea2d1c363d21efeead17d84d1'
ENTRY_PHASE_SHA256 = 'b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519'
ENTRY_STRICT_SHA256 = '9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8'


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
    previous_path = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/phase_snapshot_cpu_verifier_proposal/strict_phase_base.py')
    previous = previous_path.read_bytes()
    require(hashlib.sha256(previous).hexdigest() == '9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8', 'Sealed4096 phase base changed')
    data = STRICT_PATH.read_bytes()
    require(hashlib.sha256(data).hexdigest() == STRICT_SHA256, 'LR25 strict helper changed')
    reversed_data = data
    for before, after in BASE_REPLACEMENTS:
        require(reversed_data.count(after) == 1, 'Exact finite LR25 source delta required')
        reversed_data = reversed_data.replace(after, before)
    require(reversed_data.count(BASE_CLI_REFUSAL) == 1 and reversed_data.replace(BASE_CLI_REFUSAL, b'') == previous,
            'Only held LR25 values/control guard and direct-CLI refusal may differ from sealed9ef')
    old = b'def validate_checkpoint(path, floor, evidence):'
    new = b'def validate_checkpoint(path, floor, evidence, *, metadata_callback=None):'
    hook = b'    if metadata_callback is not None:\n        metadata_callback(checkpoint, evidence)\n'
    require(previous.count(new) == 1 and previous.count(hook) == 1 and
            previous.replace(new, old).replace(hook, b'') == original,
            'Original numerical body/callback provenance differs')
    module = types.ModuleType('_phase_snapshot_lr25_strict_body')
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
              'output_directory', 'phase_snapshot', 'lr25_context'}
    require(isinstance(job, dict) and set(job) == fields and job['schema'] == SCHEMA and
            job['verifier_sha256'] == source['sha256'] and job['strict_phase_base_sha256'] == STRICT_SHA256 and
            job['original_strict_base_sha256'] == ORIGINAL_SHA256, 'Phase root job/source schema differs')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,120}', job['experiment'] or ''), 'Invalid experiment')
    clocks(job['clock_floor'], 'current acquisition floor')
    output = base.canonical(job['output_directory'], exists=False)
    require(not output.exists() and output.parent.is_dir() and output.parent.stat().st_uid == os.getuid(),
            'Output must be NEW under owned parent')
    return job, pin, source, output


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


def check_lr25_context(job, base, evidence):
    """Root-authenticated hot-change metadata; original phase boot is not a new LR boot."""
    context = job['lr25_context']
    require(isinstance(context, dict) and set(context) == {'schema', 'precommit', 'entry_CPU'} and
            context['schema'] == 'robotron-live-CE-lr25-hot-control-context-v1', 'Explicit LR25 hot-control context required')
    pre = immutable(context['precommit'], base, evidence, 'lr25_precommit', as_json=True)
    fields = {'schema', 'status', 'experiment', 'owner', 'current_phase', 'entry_checkpoint', 'entry_CPU',
              'source_freeze_release', 'quality_closed', 'lr_scale_before', 'lr_scale_after',
              'optimizer_lr_before', 'optimizer_lr_after', 'no_weight_or_optimizer_reset', 'no_replay_clear'}
    require(isinstance(pre, dict) and set(pre) == fields and
            pre['schema'] == 'robotron-live-CE-lr25-hot-change-precommit-v1' and
            pre['status'] == 'ROOT_PRECOMMITTED_AFTER_QUALITY_CLOSURE_AND_FREEZE_RELEASE' and
            pre['quality_closed'] is True and pre['no_weight_or_optimizer_reset'] is True and pre['no_replay_clear'] is True,
            'Actual future root precommit/closed-quality/no-reset declaration required')
    spec = job['phase_snapshot']; phase = pre['current_phase']
    require(isinstance(phase, dict) and set(phase) == {'record', 'boot_checkpoint', 'boot_verification', 'expected'} and
            spec['purpose'] in ('candidate', 'newest_stopped') and
            (spec['purpose'] != 'candidate' or spec['observed_clients'] == 192) and
            pre['experiment'] == job['experiment'] and pre['owner'] == spec['owner'] and
            phase['record'] == spec['phase_record'] and phase['boot_checkpoint'] == spec['boot_checkpoint'] and
            phase['boot_verification'] == spec['boot_verification'] and phase['expected'] == spec['expected_phase'] and
            phase['expected']['metric'] == 'ce' and phase['expected']['valid'] is True and
            phase['expected']['founder_phase_record_sha256'] == FOUNDER_SHA256,
            'Actual same owner/current CE founder and original phase boot required; no invented LR startup')
    require(type(pre['lr_scale_before']) in (int, float) and pre['lr_scale_before'] == .5 and
            type(pre['lr_scale_after']) in (int, float) and pre['lr_scale_after'] == .25 and
            type(pre['optimizer_lr_before']) in (int, float) and pre['optimizer_lr_before'] == 2.5e-5 and
            type(pre['optimizer_lr_after']) in (int, float) and pre['optimizer_lr_after'] == 1.25e-5,
            'Sole explicit scale .5 to .25/effective LR2.5e-5 to1.25e-5 required')
    released = immutable(pre['source_freeze_release'], base, evidence, 'lr25_quality_source_freeze_release', as_json=True)
    require(released.get('source_freeze_released') is True, 'Actual prior quality source-freeze release required')
    require(context['entry_CPU'] == pre['entry_CPU'], 'Fresh verified pre-change entry proof differs')
    entry = immutable(context['entry_CPU'], base, evidence, 'lr25_prechange_entry_CPU', as_json=True)
    entry_job = entry['root_job']; es = entry_job['phase_snapshot']
    require(entry['schema'] == 'robotron-phase-snapshot-checkpoint-CPU-result-v1' and entry['status'] == 'PASS' and
            entry['phase_metadata_verified'] is True and entry['script']['sha256'] == ENTRY_PHASE_SHA256 and
            entry['strict_phase_base']['sha256'] == ENTRY_STRICT_SHA256 and
            entry_job['source_control_context']['held_recipe_context'] == dict(base.HELD_RECIPE_CONTEXT,
                learning_control_lr_scale=.5, optimizer_lr=2.5e-5) and
            es['purpose'] == 'candidate' and es['observed_clients'] == 192 and es['owner'] == spec['owner'] and
            es['expected_phase'] == spec['expected_phase'] and
            entry['saved_priority_metric_phase']['metric'] == 'ce' and
            entry['saved_priority_metric_phase']['valid'] is True and
            entry['saved_priority_metric_phase']['phase_record_sha256'] == FOUNDER_SHA256 and
            pre['entry_checkpoint'] == {k:entry_job['source'][k] for k in ('path','sha256','bytes')} and
            entry['sha256'] == pre['entry_checkpoint']['sha256'] and entry['bytes'] == pre['entry_checkpoint']['bytes'],
            'Genuine newest-state pre-change .5 CE4096 snapshot/CPU proof required; no protected rollback or legacy alias')
    triple(pre['entry_checkpoint'], 'pre-change live entry checkpoint')
    entry_clocks = {k:entry['clocks'][k] for k in CLOCKS}; clocks(entry_clocks, 'pre-change entry clocks')
    require(all(job['clock_floor'][k] >= entry_clocks[k] for k in CLOCKS), 'LR25 acquisition predates genuine entry state')
    evidence.update(lr25_hot_context_verified=True, lr25_precommit=context['precommit'],
                    lr25_entry_checkpoint=pre['entry_checkpoint'], lr25_entry_clocks=entry_clocks,
                    lr25_scope='Hot control only; same CE founder/owner; original boot is historical; no exact first-new-LR call, coherent replay or causal efficacy claim')


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
        check_lr25_context(job, base, evidence)
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
