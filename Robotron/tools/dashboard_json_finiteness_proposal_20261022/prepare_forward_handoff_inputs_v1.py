"""Prepare the dashboard-only forward handoff; no runtime or source mutation."""
import argparse
import copy
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G/'logs/managed-learning-20261015/run-26'
P = G/'tools/dashboard_json_finiteness_proposal_20261022'
Q = R/'quality32-protected1741-vs-normal2202-start-certified-original01-preparation-20261022'
H = R/'dashboard-JSON-production-continuity-main-inputs-original01-preparation-20261022'
PRIOR = R/'profile06-production-continuity-main-inputs-original01-preparation-20261021'
PRIOR_LIVE = PRIOR/'live-original01'
OLD = '3d1aa1950e6b1c5224ace3aecb9c837e433e5c36941b89465b414749f903da27'
NEW = '33c9726addb57ea5e8b7b5087c2e75aa179f4035542f5a91bbe3dffdf273d30c'


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-readonly', action='store_true')
    args = parser.parse_args()
    if not args.prepare_readonly:
        print('PLAN_ONLY')
        return 0
    spec = importlib.util.spec_from_file_location('_JSON_forward_inputs_h', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = h
    spec.loader.exec_module(h)
    require(h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1', 'Helper changed')
    state = json.loads((R.parent/'state.json').read_bytes())
    goal = state['optimization_goal']
    fix = goal['future_dashboard_JSON_fix']
    require(fix['production_applied'] is False and goal['actual_running_wait'] is None, 'Unexpected deployment or active scope')
    readiness = json.loads(h.checked(fix['readiness']).read_bytes())
    require(fix['readiness']['sha256'] == 'd4c8abdfd886209908c5a834a4238cb2871097bd13f73600268f6ac8155eb106'
            and readiness['production_patch_applied'] is False, 'Exact tested candidate readiness required')
    holds = json.loads(h.checked(fix['closed_source_holds_archive']).read_bytes())
    require(fix['closed_source_holds_archive']['sha256'] == '1eabe3490125cc7a02084713eb256f7e93b9c04d5f343efe4e0ed6e708f479b0'
            and len(holds['files']) == 196, 'Original196 archive required')
    for row in holds['files']:
        h.checked(row['archive'])
        require(h.pin(row['original_path']) == row['original_observed_pin'], 'A held original source changed')
    failed_pin = h.pin(Q/'01-reference/independent-quality-leg-review-original01/review.json')
    require(failed_pin['sha256'] == 'faa19ec62f6a2bdda1e338c538d61af739c511f580e92e45bf74c300cdb24ad2', 'Original failed review changed')
    insurance_pin = h.pin(Q/'future-dashboard-JSON-forward-insurance-original02-preparation/independent-CPU-closed-readback.json')
    require(insurance_pin['sha256'] == '385755762289fe8efd7f8f1a4f43c3f0feb7fe50f0a57f2dbcfc5de462420326', 'Insurance closure changed')
    insurance = json.loads(h.checked(insurance_pin).read_bytes())
    require(insurance['actual_exit'] == 0 and insurance['main_restart_or_restore'] is False, 'Actual insurance verification required')
    binding = holds['original_main_binding']
    main_binding = json.loads(h.checked(binding).read_bytes())
    owner = main_binding['owner']
    require(owner['pid'] == 3295795 and owner['starttime_ticks'] == 64995335
            and owner['invocation_id'] == '160d2b4b1f6e4e2f8839790658a7d01c', 'Only current original main is selected')
    guard_path = R/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py'
    require(h.pin(guard_path)['sha256'] == 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3', 'Guard changed')
    guard = h.load('_JSON_forward_inputs_guard', guard_path)
    guard.owner_and_files(main_binding)
    require(not H.exists(), 'Fresh preparation only; preserve any original outcome')
    H.mkdir(mode=0o700)

    def put_raw(path, raw):
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        return h.pin(path)

    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        wire = response.read()
    api_pin = put_raw(H/'current-main-baseline-API.raw.json', wire)
    def reject_constant(value):
        raise ValueError('Nonfinite original producer JSON: '+value)
    api = json.loads(wire, parse_constant=reject_constant)
    api = api.get('now', api)
    baseline = json.loads(h.checked(main_binding['baseline_API']).read_bytes())
    guard.healthy(api, baseline.get('now', baseline), main_binding['experiment'], time.time())
    require(api['memory_buffer_size'] == 6000000, 'Current full replay required')

    def show(unit, output):
        result = subprocess.run(['systemctl', '--user', 'show', unit], capture_output=True, timeout=15, check=True)
        pin = put_raw(H/output, result.stdout)
        return dict(line.split('=', 1) for line in result.stdout.decode().splitlines() if '=' in line), pin

    shown, show_pin = show(owner['unit'], 'original-main-service-show.txt')
    require(shown['MainPID'] == str(owner['pid']) and shown['InvocationID'] == owner['invocation_id']
            and shown['ControlGroup'] == owner['cgroup'] and shown['NRestarts'] == '0', 'Current service changed')
    prior_prep_pin = h.pin(PRIOR/'prepared-inputs.json')
    require(prior_prep_pin['sha256'] == 'ac0f2ff0bd79e0fc6c780585fd8899f8ba1cfeb0c16fd001b7ad024af55e2a5a', 'Prior inputs changed')
    prior_prepared = json.loads(h.checked(prior_prep_pin).read_bytes())
    registration_pin = h.pin(R/'profile06-production-continuity-live-controller-original01-preparation-20261021/completed-registration/root-independent-registration.json')
    require(registration_pin['sha256'] == '76c975840447a1d677678e70cec5886263b022430df8a3dd23084a4e641cbef9', 'Prior registration changed')
    registration = json.loads(h.checked(registration_pin).read_bytes())
    require(registration['newest_state_preserved'] is True and registration['original192_PIDs_and_affinities_preserved'] is True, 'Prior actual handoff proof required')
    replacement = h.pin(PRIOR_LIVE/'actual-replacement-birth.json')
    require(json.loads(h.checked(replacement).read_bytes()) == owner, 'Current owner does not match original replacement')
    boot_pin = registration['newest_stopped_CPU']
    boot = json.loads(h.checked(boot_pin).read_bytes())
    phase_pin = h.pin(PRIOR_LIVE/'resume-phase-record.json')
    phase = json.loads(h.checked(phase_pin).read_bytes())
    startup_pin = registration['startup_CPU']
    startup = json.loads(h.checked(startup_pin).read_bytes())
    require(boot['status'] == startup['status'] == 'PASS' and boot['phase_metadata_verified'] is True
            and phase['checkpoint']['sha256'] == boot['sha256'] and phase['checkpoint']['bytes'] == boot['bytes'], 'Original boot/phase proof differs')
    require(registration['startup_update_count'] == 1 and startup['clocks']['optimized_samples'] == boot['clocks']['optimized_samples']+4096
            and startup['clocks']['training_steps'] == boot['clocks']['training_steps']+1
            and all(startup['clocks'][key] == boot['clocks'][key] for key in ('frame_count', 'learner_frame_count')), 'Actual startup delta differs')
    replay_pin = h.pin(PRIOR_LIVE/'actual-stopped-ring-and-banks.json')
    replay = json.loads(h.checked(replay_pin).read_bytes())
    require(replay['ring']['meta']['size'] == 6000000, 'Actual original boot replay required')
    anchor = json.loads(h.checked(prior_prepared['component_proofs']['original_boot_anchor']).read_bytes())
    for entry in anchor['source_pins'].values():
        h.checked(entry)
    selected = {key.decode(): value.decode() for item in Path('/proc', str(owner['pid']), 'environ').read_bytes().split(b'\0')
                if item and (key := item.split(b'=', 1)[0]) in
                (b'DQN_MAX_SAMPLES_PER_FRAME', b'DQN_RATCHET', b'DQN_EXACT_INFERENCE_GRAPHS', b'DQN_PRIORITY_PHASE_RECORD', b'DQN_PRIORITY_PHASE_RECORD_SHA256')
                for value in [item.split(b'=', 1)[1]]}
    require(selected == dict(DQN_MAX_SAMPLES_PER_FRAME='8', DQN_RATCHET='0', DQN_EXACT_INFERENCE_GRAPHS='1',
                            DQN_PRIORITY_PHASE_RECORD=phase_pin['path'], DQN_PRIORITY_PHASE_RECORD_SHA256=phase_pin['sha256']), 'Current boot environment differs')
    exposure = api['host_pipeline']['learning_exposure']
    require(exposure['optimizer']['process_id'] == exposure['replay']['process_id'] == owner['pid']
            and exposure['optimizer']['epoch'] == exposure['replay']['epoch'] == 1
            and api['host_pipeline']['inference_graphs']['postload_validations'] == 1
            and os.readlink(Path('/proc', str(owner['pid']), 'fd/0')) == '/dev/null', 'Current no-reset boot provenance differs')
    census = []
    for task in Path('/proc', str(owner['pid']), 'task').iterdir():
        try:
            raw = (task/'stat').read_text()
            census.append(dict(tid=int(task.name), starttime_ticks=int(raw.rsplit(')', 1)[1].split()[19]),
                               comm=(task/'comm').read_text().strip(), wchan=(task/'wchan').read_text().strip()))
        except FileNotFoundError:
            continue
    listeners = [row for row in census if row['comm'].endswith(' (start')]
    require(len(listeners) == 1, 'Unique original accept thread required')
    census_pin = h.put(H/'original-main-native-thread-census.json', dict(owner=owner, threads=census, read_only=True))
    listener_pin = h.put(H/'original-listener-birth.json', dict(owner=owner, tid=listeners[0]['tid'],
        starttime_ticks=listeners[0]['starttime_ticks'], comm=listeners[0]['comm'], cgroup=owner['cgroup'],
        current_wchan=listeners[0]['wchan'], original_census=census_pin, actual_cgroup_move_or_freeze=False))
    fleet = json.loads(h.checked(prior_prepared['original_fleet']).read_bytes())
    fleet_show, fleet_show_pin = show(fleet['unit'], 'original-fleet-service-show.txt')
    fleet_stat = Path('/proc', str(fleet['pid']), 'stat').read_text()
    require(fleet_show['MainPID'] == str(fleet['pid']) and fleet_show['InvocationID'] == fleet['invocation_id']
            and fleet_show['ControlGroup'] == fleet['cgroup'] and fleet_show['NRestarts'] == '0'
            and int(fleet_stat.rsplit(')', 1)[1].split()[19]) == fleet['starttime_ticks']
            and Path('/sys/fs/cgroup'+fleet['cgroup']+'/cgroup.freeze').read_text().strip() == '0', 'Original fleet differs')
    fleet['original192_actors'] = copy.deepcopy(main_binding['actors'])
    require(len(fleet['original192_actors']) == 192 and {row['slot'] for row in fleet['original192_actors']} == set(range(192)), 'All current192 slots required')
    fleet['actual_actor_freeze_or_stop'] = False
    fleet_pin = h.put(H/'original-fleet-owner.json', fleet)
    fresh_main = copy.deepcopy(main_binding)
    fresh_main['baseline_API'] = api_pin
    main_pin = h.put(H/'original-main-binding.json', fresh_main)
    anchor.update(owner=owner, original_boot_activation=registration_pin, original_boot_strict_CPU=boot_pin,
        original_phase_record=phase_pin, original_boot_saved_clocks=boot['clocks'], original_boot_replay_snapshot=replay_pin,
        original_startup_CPU=startup_pin, actual_original_replacement_birth=replacement, current_API=api_pin,
        selected_environment=selected, actual_private_anchor_read=False, inferred_replay_pressure_anchor=None,
        actual_optimizer_or_replay_executed=False, trainer_changed=False)
    anchor['evidence']['main196_inputs_and_original192_actors_unchanged'] = True
    anchor['evidence'].pop('main195_inputs_and_original192_actors_unchanged', None)
    eligible = api['frame_count']-boot['clocks']['frame_count']-max(0, api['measurement_frames']-boot['clocks']['measurement_frame_count'])
    samples = api['optimized_samples']-boot['clocks']['optimized_samples']
    require(eligible > 0 and samples > 0, 'Current boot progress required')
    anchor['budget_observation'] = dict(eligible_fleet_frames=eligible, logical_samples_since_boot=samples,
        samples_per_eligible_frame=samples/eligible, configured_cap=8, scope='Passive cached clocks only; final drained coherent witness required.')
    anchor['current_owner_provenance'] = dict(current_main_binding=main_pin, current_service_show=show_pin,
        prior_current_owner_completed_handoff=registration_pin, original_replacement_birth=replacement,
        strict_stopped_boot_CPU=boot_pin, actual_startup_CPU=startup_pin, preactor_startup_update_count=1,
        preactor_startup_sample_delta=4096, original_replay_snapshot=replay_pin)
    anchor_pin = h.put(H/'current-owner-original-boot-anchor-source-readback.json', anchor)
    original_pin = h.pin(G/'Scripts/dqn/metrics_dashboard.py')
    candidate_pin = h.pin(P/'metrics_dashboard_candidate_v1.py')
    require(original_pin['sha256'] == OLD and candidate_pin['sha256'] == NEW, 'Exact tested dashboard transaction required')
    original = h.checked(original_pin).read_bytes()
    candidate = h.checked(candidate_pin).read_bytes()
    original_archive = put_raw(H/'installed-dashboard-before.py', original)
    candidate_archive = put_raw(H/'proposed-metrics-dashboard.py', candidate)
    patch_pin = put_raw(H/'selected-dashboard-patch.diff', ''.join(difflib.unified_diff(
        original.decode().splitlines(True), candidate.decode().splitlines(True),
        fromfile='Scripts/dqn/metrics_dashboard.py', tofile='Scripts/dqn/metrics_dashboard.py')).encode())
    proofs = dict(original_boot_anchor=anchor_pin, current_original_handoff_registration=registration_pin,
        dashboard_JSON_composed_readiness=fix['readiness'], original_closed196=fix['closed_source_holds_archive'],
        original_failed_quality_review=failed_pin, current_normal_autosave_insurance=insurance_pin)
    prepared = dict(schema='robotron-prospective-main-score-carry-handoff-inputs-v1',
        status='PREPARED_IMMUTABLE_PROPOSAL_LIVE_CONTROLLER_NOT_SELECTED', created_unix_s=time.time(),
        original_main=main_pin, original_listener=listener_pin, original_fleet=fleet_pin,
        installed_before=original_archive, proposed_source=candidate_archive, selected_source_relative='Scripts/dqn/metrics_dashboard.py',
        patch=patch_pin, component_proofs=proofs, tested_bank_witness=prior_prepared['tested_bank_witness'],
        current_boot_CPU=boot_pin, current_boot_phase_record=phase_pin, current_boot_replay_snapshot=replay_pin,
        current_boot_checkpoint=phase['checkpoint'], current_original_startup_CPU=startup_pin,
        all196_holds_and_original192_verified=True, original_scientific_case_remains_invalid=True,
        production_source_changed=False, main_or_fleet_cgroup_changed=False, learning_recipe_changed=False,
        prior_original_live_job_not_reused=True, actual_newest_stopped_model_acquired=False,
        qualification=False, promotion=False, learning_speed_gain_verified=False,
        remaining_before_any_live_execution=['Prepare current-owner dashboard-only backend and poststop inputs.',
            'Verify source transaction and owned recovery contracts against the new bundle.',
            'Precommit one controller and independent rescue; release closed-study source freeze prospectively.',
            'Drain/seal current input and budget, stop once, CPU-verify newest stopped full state and replay/banks, install exact dashboard and phase record, start once, verify startup and original192 learning.'])
    guard.owner_and_files(main_binding)
    for entry in (binding, registration_pin, replacement, boot_pin, phase_pin, startup_pin, replay_pin, original_pin, candidate_pin):
        h.checked(entry)
    prepared_pin = h.put(H/'prepared-inputs.json', prepared)
    report = h.put(H/'readonly-preparation-result.json', dict(
        schema='robotron-dashboard-JSON-current-main-readonly-handoff-inputs-v1', status='CURRENT_OWNER_FORWARD_INPUTS_PREPARED_NO_LIVE_HANDOFF',
        source=h.pin(__file__), prepared=prepared_pin, owner=owner, normal_insurance=insurance_pin,
        prior_original_registration=registration_pin, actual_boot_CPU=boot_pin, actual_boot_phase=phase_pin,
        actual_boot_replay_snapshot=replay_pin, actual_current_listener=listener_pin, actual_current_fleet=fleet_pin,
        original196_archives_verified=True, all196_holds_and_current192_births_affinities_verified=True,
        original_scientific_review_remains_invalid=True, production_applied=False,
        main_pause_stop_restart_restore=False, deployment_ready=False, created_unix_s=time.time()))
    print(json.dumps(dict(report=report, prepared=prepared_pin, owner=owner)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
