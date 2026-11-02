"""Record actual running trial02 evidence and update canonical dashboard state."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

REPO = Path('/home/dave/source/repos/ArcadeAI')
RUN = REPO / 'Robotron/logs/managed-learning-20261015/run-26'
OUT = RUN / 'goal-continuation-KL-trial02-running-root-20261017'
STATE = RUN.parent / 'state.json'


def pin(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return pin(path)


def show(expected):
    r = subprocess.run(['systemctl', '--user', 'show', expected['unit']],
                       capture_output=True, text=True, timeout=20, check=True)
    fields = dict(line.split('=', 1) for line in r.stdout.splitlines() if '=' in line)
    assert fields['ActiveState'] == 'active' and fields['SubState'] == 'running'
    assert fields['MainPID'] == str(expected['pid'])
    assert fields['InvocationID'] == expected['invocation_id']
    assert fields['NRestarts'] == '0'
    ticks = int(Path('/proc', str(expected['pid']), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    assert ticks == expected['starttime_ticks']
    return dict(expected=expected, fields=fields, observed_monotonic_s=time.monotonic())


def main():
    activation_path = RUN / 'rawKL-trial02-activation-20261017/result.json'
    controller = RUN / 'rawKL-trial02-controller-20261017'
    activation = load(activation_path)
    observer = load(controller / 'observer-job.json')
    assert activation['status'] == 'READY'
    assert activation['owner'] == observer['owner']
    assert activation['owner']['pid'] == 546648
    assert observer['boot_four_clocks']['learner_frame_count'] == 503951038
    assert not (controller / 'result.json').exists()
    assert not (controller / 'deadline-result.json').exists()
    latest = sorted(controller.glob('observation-*.json'))[-1]
    observation = load(latest)
    assert observation['state'] == 'CONTINUE'
    assert 0 <= time.monotonic() - observation['observed_monotonic_s'] < 10
    OUT.mkdir(mode=0o700)
    state = load(STATE)
    assert state['active_runtime']['trainer_pid'] == 511524
    old_runtime = save(OUT / 'previous-CE511524-runtime-canonical-asof.json', state['active_runtime'])
    old_state = pin(STATE)
    parents = dict(
        controller=dict(unit='robotron-rawkl-trial02-controller-20261017.service', pid=545337,
                        starttime_ticks=33273360, invocation_id='6879051172d24f729778398f171a37d4'),
        deadline=dict(unit='robotron-rawkl-trial02-deadline-20261017.service', pid=542640,
                      starttime_ticks=33266229, invocation_id='f7935f091de1400e86572b845b9852a4'))
    current_units = {role: show(owner) for role, owner in {**parents, 'trainer': activation['owner']}.items()}
    units_pin = save(OUT / 'actual-live-parent-and-trainer-identities.json', current_units)
    early = controller / 'early-insurance'
    insurance = load(early / 'saved-insurance-receipt.json')
    cpu = load(early / 'cpu-output/cpu-verification.json')
    release = load(early / 'CPU-execution/result-review-and-release.json')
    assert insurance['trainer'] == activation['owner'] and cpu['status'] == 'PASS' and cpu['mode'] == 'insurance'
    assert release['original_pid'] == 548969 and release['original_exit'] == 0
    assert release['original_archived_before_release'] is True
    assert all(item['final_load_state'] == 'not-found' for item in release['releases'])
    insurance_record = dict(
        status='actual_current_KL192_early_insurance_CPU_PASS',
        receipt=pin(early / 'saved-insurance-receipt.json'),
        CPU_verification=pin(early / 'cpu-output/cpu-verification.json'),
        CPU_original_terminal_release=pin(early / 'CPU-execution/result-review-and-release.json'),
        source=insurance['source'], copy=insurance['copy'], saved_clocks=cpu['clocks'],
        owner=activation['owner'], not_boot_input=True, not_horizon_candidate=True)
    t0 = observer['start_request']['monotonic_s']
    limits = dict(boot_id=observer['start_request']['boot_id'],
                  start_monotonic_s=t0, start_unix_s=observer['start_request']['unix_s'],
                  first_candidate_learner_target=511951038, minimum_physical_accepted_delta=6000000,
                  latch_durability_cutoff_monotonic_s=t0 + 3240,
                  stop_intent_latest_monotonic_s=t0 + 3310,
                  KL_owner_absence_ceiling_monotonic_s=t0 + 3600,
                  no_deadline_extension=True, no_reanchor_or_retry=True)
    now = datetime.now(timezone.utc).isoformat()
    progress = dict(
        schema='robotron-goal-continuation-running-KL-trial02-root-v1', status='PASS_RUNNING_PREFIX_ONLY',
        utc=now, goal_remains_active=True, previous_state_asof=old_state,
        previous_runtime_archive=old_runtime, actual_units=units_pin,
        activation=pin(activation_path), phase_record=activation['phase_record'],
        boot_four_clocks=observer['boot_four_clocks'], newest_boot=activation['boot_checkpoint'],
        startup0_phase_CPU=activation['startup_phase_proof']['phase_CPU'],
        early_KL192_insurance=insurance_record,
        full_192_source_control_mask_health=pin(RUN / 'rawKL-trial02-running-prefix-root-health-20261017/root-running-prefix-health-PASS.json'),
        latest_observation=pin(latest), observed_progress=observation['progress'],
        observed_elapsed_s=observation['elapsed_s'], fixed_limits=limits,
        qualification_pass=False, candidate_produced=False, quality_campaign_launched=False,
        frozen_policy_quality_or_causal_learning_speed_claim=False,
        next_action='Continue actual immutable trial; inspect first terminal, candidate CPU and newest-state CE return before fresh R/C/R/C against protected448.',
        original_trial01_failure_and_forward_newest_CE_repair_preserved=True)
    progress_pin = save(OUT / 'root-progress-receipt.json', progress)
    optimization = state['optimization_goal']
    revision = optimization['future_kl_priority_calibration']['optional_sequential_KL_source']['installed_CE_revision2']
    revision.update(status='actual_trial02_KL192_running_startup0_and_early192_CPU_PASS',
                    activation=pin(activation_path), startup0_phase_CPU=activation['startup_phase_proof']['phase_CPU'],
                    current_prefix_health=progress['full_192_source_control_mask_health'])
    revision['actual_trial'].update(new_owner=activation['owner'], boot_four_clocks=observer['boot_four_clocks'],
                                    actual_start=observer['start_request'], fixed_limits=limits,
                                    early_KL192_insurance=insurance_record,
                                    latest_saved_observation=pin(latest), observed_progress=observation['progress'],
                                    observed_elapsed_s=observation['elapsed_s'], qualification_pass=False)
    state['stage'] = 'run26_448M_confirmed_rawKL_trial02_running_awaiting_first_8M_horizon'
    state['active_diagnostic_job'].update(state='running', new_owner=activation['owner'],
                                        start=observer['start_request'], latest_saved_observation=pin(latest),
                                        root_progress=progress_pin, qualification_pass=False)
    optimization['active_diagnostic_job'].update(state='running', new_owner=activation['owner'], root_progress=progress_pin)
    optimization['pending_preKL_current_owner_insurance'].update(
        status='historical_CE511524_insurance_CPU_PASS_before_actual_trial02_activation',
        historical_previous_owner_not_current=True, future_KL_early192_insurance_remains_distinct=True)
    runtime = state['active_runtime']
    runtime.update(
        status='actual_KL_trial02_running_192_startup0_and_early192_CPU_PASS',
        trainer_pid=activation['owner']['pid'], trainer_start_ticks=str(activation['owner']['starttime_ticks']),
        trainer_invocation_id=activation['owner']['invocation_id'],
        last_verified_prior_trainer_pid=511524, previous_runtime_asof=old_runtime,
        priority_metric='kl', phase_record=activation['phase_record'],
        all_connected_unix_s=observer['start_request']['unix_s'] + activation['healthy192_monotonic_s'] - t0,
        resume_checkpoint_sha256=activation['boot_checkpoint']['source']['sha256'],
        resume_checkpoint_CPU_verification=activation['boot_checkpoint']['verification'],
        resume_learner_frame_count=observer['boot_four_clocks']['learner_frame_count'],
        resume_fleet_frame_count=observer['boot_four_clocks']['frame_count'],
        resume_training_steps=observer['boot_four_clocks']['training_steps'],
        resume_optimized_samples=observer['boot_four_clocks']['optimized_samples'],
        controlled_trial_precommit=revision['final_core'],
        startup_audit=str(activation_path), startup_audit_sha256=pin(activation_path)['sha256'],
        startup0_phase_CPU=activation['startup_phase_proof']['phase_CPU'],
        current_health=progress['full_192_source_control_mask_health'],
        current_early_insurance=insurance_record,
        learning_rule_change_scope='New KL replay-priority phase from newest validated CE state; CE optimizer objective unchanged; original trial01 update preserved; no quality or learning-speed claim.')
    text = ('448M remains confirmed. Trial02 is actually running KL priorities with all192; '
            'newest-state CE boot, startup0 phase CPU and genuine KL192 early insurance all PASS. '
            'Waiting for first +8M learner AND +6M physical accepted horizon within original deadlines; '
            'no candidate or quality result yet. Original trial01 failure and forward repair remain preserved.')
    optimization.update(latest_progress=text, latest_root_progress=progress_pin,
                        last_progress_receipt=progress_pin['path'], last_progress_receipt_sha256=progress_pin['sha256'],
                        last_review_utc=now,
                        last_review_learner_frames=observer['boot_four_clocks']['learner_frame_count'] + observation['progress']['learner_frames'])
    state.update(updated_utc=now, updated_unix_s=time.time(), last_review_utc=now)
    raw = (json.dumps(state, indent=2, allow_nan=False) + '\n').encode()
    assert len(raw) < 1024 * 1024
    assert pin(STATE) == old_state
    tmp = STATE.with_name('state.json.trial02-running-root.tmp')
    with tmp.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), STATE.stat().st_mode & 0o777)
        os.fsync(stream.fileno())
    os.replace(tmp, STATE)
    fd = os.open(STATE.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    assert load(STATE)['active_runtime']['trainer_pid'] == 546648
    save(OUT / 'root-canonical-update-result.json', dict(status='PASS', state=pin(STATE), root_progress=progress_pin))
    print(json.dumps(dict(status='PASS_RUNNING_PREFIX_ONLY', root_progress=progress_pin, state_bytes=len(raw))))


if __name__ == '__main__':
    main()
