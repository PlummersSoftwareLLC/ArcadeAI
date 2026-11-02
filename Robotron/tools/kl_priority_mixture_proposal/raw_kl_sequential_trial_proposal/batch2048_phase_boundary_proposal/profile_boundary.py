"""Unconsumed pure CE batch boundary; no imports of runtime/application code.

These functions supply the narrow fd4e/fdf integration seam, not an executable
transition. Root must authenticate actual source/profile/metadata bytes first.
"""
import copy
import json
from pathlib import PurePosixPath
import re

PROFILE_BINDING_JSON = '{"pin":{"bytes":764,"path":"/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_profile_horizon_proposal/profile.json","sha256":"e755e22ade5cb56537b08f41f412e856da09435d88e4e71e09b22aba521eac50"},"value":{"LR_compensation":false,"batch_size":2048,"before_batch_size":4096,"deliberate_recipe_changes":["DQN_BATCH_SIZE"],"held_recipe_context":{"baseline_batch_size":512,"batch_size":2048,"c51_target_smoothing":0,"epsilon":0.1,"expert_ratio":0.1,"fused":true,"gamma":0.995,"learning_control_lr_scale":0.5,"lr_anchor_step":0.0,"lr_gear":"climb","max_samples_per_frame":8,"n_step":3,"num_atoms":51,"optimizer_eps":0.00015,"optimizer_lr":2.5e-05,"v_max":50.0,"v_min":-10.0},"priority_metric":"ce","profile_id":"ce_batch2048_efficacy_screen_v1","return_batch_size":4096,"schema":"robotron-ce-batch2048-efficacy-profile-v1"}}'
PROFILE_BINDING = json.loads(PROFILE_BINDING_JSON)
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
FLAGS = ('DQN_RECOMPUTED_CE_CAPTURE_DIR', 'DQN_EXECUTED_CE_TRACE_DIR')
PHASE_KEYS = ('DQN_PER_PRIORITY_METRIC', 'DQN_PRIORITY_PHASE_RECORD',
              'DQN_PRIORITY_PHASE_RECORD_SHA256')
MODES = {'activate_batch2048': (4096, 2048), 'return_batch4096': (2048, 4096)}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    require(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value), 'Missing exact SHA256')
    return value


def canonical_path(value):
    require(type(value) is str and value.startswith('/') and not value.startswith('//') and '\0' not in value and
            str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts,
            'Absolute canonical metadata path required')
    return value


def triple(pin):
    require(isinstance(pin, dict), 'Missing source PIN')
    value = {key: pin[key] for key in ('path', 'sha256', 'bytes')}
    canonical_path(value['path']); digest(value['sha256'])
    require(type(value['bytes']) is int and value['bytes'] > 0, 'Invalid source byte count')
    return value


def full_metadata_pin(pin):
    value = triple(pin)
    require(set(pin) == {'path', 'sha256', 'bytes', 'identity'}, 'Actual full metadata PIN required')
    identity = pin['identity']
    require(isinstance(identity, dict) and set(identity) ==
            {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'nlink'},
            'Incomplete actual metadata identity')
    require(all(type(identity[key]) is int and identity[key] >= 0
                for key in ('device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'uid', 'nlink'))
            and identity['bytes'] == value['bytes'] and identity['mode'] == '0o444'
            and identity['nlink'] == 1, 'Readonly single-link metadata required')
    return copy.deepcopy(pin)


def four(value):
    result = {key: value[key] for key in CLOCKS}
    require(all(type(item) is int and item > 0 for item in result.values()),
            'Actual positive four-clock values required')
    return result


def direction(mode, binding):
    require(mode in MODES, 'Only the two declared CE batch transitions exist')
    require(json.dumps(binding, sort_keys=True, separators=(',', ':'), allow_nan=False)
            == PROFILE_BINDING_JSON, 'Exact pinned CE batch profile required')
    before, after = MODES[mode]
    return dict(schema='robotron-ce-batch-profile-boundary-v1', mode=mode,
        before_batch_size=before, after_batch_size=after, priority_metric='ce',
        profile_binding=copy.deepcopy(binding))


def checked_spec(spec):
    require(isinstance(spec, dict) and
            json.dumps(spec, sort_keys=True, separators=(',', ':'), allow_nan=False) ==
            json.dumps(direction(spec['mode'], spec['profile_binding']),
                       sort_keys=True, separators=(',', ':'), allow_nan=False),
            'Boundary spec changed or is incomplete')
    return spec


def selected_environment(before, spec, phase_record_pin):
    spec = checked_spec(spec)
    require(isinstance(before, dict) and before.get('DQN_BATCH_SIZE') == str(spec['before_batch_size'])
            and before.get('DQN_PER_PRIORITY_METRIC') == 'ce', 'Actual before CE batch differs')
    require(not any(before.get(flag) for flag in FLAGS), 'Unexpected capture flag')
    record = full_metadata_pin(phase_record_pin)
    result = dict(before)
    for flag in FLAGS:
        result.pop(flag, None)
    result.update(DQN_BATCH_SIZE=str(spec['after_batch_size']), DQN_PER_PRIORITY_METRIC='ce',
        DQN_PRIORITY_PHASE_RECORD=record['path'], DQN_PRIORITY_PHASE_RECORD_SHA256=record['sha256'])
    return result


def override_environment(before, spec, phase_record_pin):
    """Only the four owned startup keys belong in the dedicated drop-in."""
    selected = selected_environment(before, spec, phase_record_pin)
    return {key: selected[key] for key in ('DQN_BATCH_SIZE', *PHASE_KEYS)}


def start_record(spec, phase_id, root_precommit_sha256, model_dir,
                 checkpoint, boot_proof, required_floor):
    checked_spec(spec); digest(root_precommit_sha256); canonical_path(model_dir)
    require(type(phase_id) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', phase_id),
            'New explicit CE phase ID required')
    source = triple(checkpoint)
    require(source['path'] == model_dir + '/robotron_dqn_latest.pt', 'Only actual newest latest may boot')
    require(boot_proof.get('status') == 'PASS' and boot_proof['sha256'] == source['sha256']
            and boot_proof['bytes'] == source['bytes'], 'Exact actual newest CPU proof required')
    require(boot_proof.get('phase_metadata_verified') is True
            and boot_proof['root_job']['phase_snapshot']['purpose'] == 'newest_stopped'
            and boot_proof['held_recipe_context']['batch_size'] == spec['before_batch_size'],
            'Actual before-profile newest-stopped phase CPU proof required')
    clocks, floor = four(boot_proof['clocks']), four(required_floor)
    require(all(clocks[key] >= floor[key] for key in CLOCKS), 'Newest state predates required forward floor')
    previous = boot_proof.get('saved_priority_metric_phase')
    require(isinstance(previous, dict) and previous.get('schema') == 'robotron-priority-metric-phase-v1'
            and type(previous.get('phase_id')) is str
            and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', previous['phase_id']) and previous.get('metric') == 'ce'
            and previous.get('valid') is True and previous.get('phase_id') != phase_id,
            'A new CE phase must follow actual valid newest CE; no KL or old boot')
    return dict(schema='robotron-priority-metric-start-v1', phase_id=phase_id,
        metric='ce', action='start', previous_metric='ce', checkpoint=source,
        model_dir=model_dir, root_precommit_sha256=root_precommit_sha256)


def expected_start(record, record_pin, boot_proof):
    require(record['metric'] == 'ce' and record['previous_metric'] == 'ce'
            and record['action'] == 'start', 'Explicit new CE start required')
    require(record['checkpoint']['sha256'] == boot_proof['sha256']
            and record['checkpoint']['bytes'] == boot_proof['bytes'], 'Founder boot proof differs')
    return dict(metric='ce', phase_id=record['phase_id'],
        root_precommit_sha256=record['root_precommit_sha256'],
        founder_phase_record_sha256=triple(record_pin)['sha256'], last_resume_record_sha256=None,
        started_from=dict(record['checkpoint'], clocks=four(boot_proof['clocks'])), valid=True)


def csv_guard_plan(spec, stage, baseline_csv, exposure_identity, current_environment):
    """Keep the actual pre-stop CSV at actor0; require new CSV after192.

The returned plan is for unchanged metrics.api_issues. No row is rewritten and
no baseline row is labelled as new-producer CSV. Environment provenance and
actual PIN authentication remain the invoking root adapter's responsibility.
"""
    spec = checked_spec(spec)
    require(stage in ('before', 'startup0', 'running192'), 'Unknown lifecycle CSV stage')
    require(baseline_csv['batch_size'] == spec['before_batch_size']
            and baseline_csv['replay_sample_cap'] == 8, 'Genuine before-profile CSV required')
    configured = spec['before_batch_size'] if stage == 'before' else spec['after_batch_size']
    require(current_environment.get('DQN_BATCH_SIZE') == str(configured)
            and current_environment.get('DQN_PER_PRIORITY_METRIC') == 'ce', 'Observed current CE profile differs')
    observed = spec['after_batch_size'] if stage == 'running192' else spec['before_batch_size']
    return dict(batch_size=observed, replay_cap=8,
        initial_snapshot=dict(csv=copy.deepcopy(baseline_csv)),
        exposure_identity=copy.deepcopy(exposure_identity),
        configured_batch_size=configured,
        csv_scope='pretransition_baseline' if stage == 'startup0' else 'current_producer',
        boundary_profile_sha256=spec['profile_binding']['pin']['sha256'])


def phase_cpu_boundary(spec, purpose, *, profile_pin=None, producer_observation=None):
    """Select metadata context only; never run or claim numerical verification.

Early insurance requires a distinct maintenance-verifier lifecycle adaptation;
it cannot be represented as an existing phase purpose or a startup proof.
"""
    spec = checked_spec(spec)
    require(purpose in ('startup', 'candidate', 'newest_stopped'),
            'Early insurance is not a phase-CPU purpose; separate adapter required')
    batch = spec['before_batch_size'] if purpose == 'newest_stopped' else spec['after_batch_size']
    if batch == 4096:
        require(profile_pin is None and producer_observation is None,
                'Do not attach a2048 producer context to original4096 proof')
        return dict(batch_size=4096, verifier_family='original_phase4096',
            job_schema='robotron-phase-snapshot-checkpoint-CPU-job-v1',
            result_schema='robotron-phase-snapshot-checkpoint-CPU-result-v1', additional_job_fields={})
    actual_profile = full_metadata_pin(profile_pin)
    require(triple(actual_profile) == PROFILE_BINDING['pin'], 'Wrong actual profile file PIN')
    producer = full_metadata_pin(producer_observation)
    role = 'treatment_startup' if purpose == 'startup' else purpose
    return dict(batch_size=2048, verifier_family='explicit_profile_phase2048',
        job_schema='robotron-batch2048-phase-snapshot-checkpoint-CPU-job-v1',
        result_schema='robotron-batch2048-phase-snapshot-checkpoint-CPU-result-v1',
        additional_job_fields=dict(batch2048_context=dict(profile=actual_profile,
            role=role, producer_observation=producer)))


def main():
    print(json.dumps(dict(status='PLAN_ONLY_UNACTIVATED_BOUNDARY_SLICE',
        actual_transition=False, imports_runtime=False, source_changes=False,
        whole_trial_ready=False, profile_binding=PROFILE_BINDING), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
