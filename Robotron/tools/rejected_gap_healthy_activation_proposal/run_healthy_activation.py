#!/usr/bin/env python3
"""Root-only one healthy CE4096 newest-state diagnostic activation.

Default PLAN performs no reads. This file never selects protected/entry weights,
starts a fleet, retries a CPU/start, clears replay, or rolls sources back.
"""
import argparse
import copy
from contextlib import contextmanager
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
import traceback

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME/'logs/managed-learning-20261015/run-26'
HEALTHY = RUN/'accepted-newgame-healthy-CE-maintenance-source-preparation-20261017/run_healthy_ce_maintenance.py'
HEALTHY_SHA = 'f007ad2723fd5fe5b2fd4c0c95723e23b931c60c0938b63114f73e1f71c4b1ae'
COVERAGE = RUN/'accepted-newgame-failed-maintenance-forward-recovery-source-preparation-20261017/run_forward_recovery.py'
COVERAGE_SHA = 'b6d06f94c454cb4106aab0bf6316c62f9b85e134744f176f6389004e976f606e'
COMBINED = GAME/'tools/rejected_gap_observation_combined_proposal/preparation-manifest.json'
COMBINED_SHA = '333802efb4a58337b0c79293c3736b642117352ca2467bc6e6eb49a1739f5bf9'
RELEASE = RUN/'accepted-newgame-forward-recovery-root-control-20261017/root-confirmed704-protected-canonical-adoption-and-source-freeze-release-20261018.json'
RELEASE_SHA = '46f10a5e95dee9bc324f6e4496720f055d5248495946635b6c5eb450d9d8a145'
REGRESSION = RUN/'accepted-newgame-forward-recovery-root-control-20261017/root-postquality43-original-PASS-and-healthy-activation-next-loop-20261018.json'
REGRESSION_SHA = 'b5e9a829164428d827df53c90009bfe0fa631cf9a440b55d5019271f8a96589a'
SCHEMA = 'robotron-rejected-gap-healthy-activation-job-v1'
INTENT_SCHEMA = 'robotron-rejected-gap-healthy-activation-intent-v1'
RESULT_SCHEMA = 'robotron-rejected-gap-healthy-activation-result-v1'
FLAG = 'ROBOTRON_REJECTED_GAP_TELEMETRY'
PLAN = 'PLAN_ONLY: unselected healthy four-file diagnostic activation; no reads/actions'
DELTAS = {
 'socket_server.py': ('4a1f6a3cc7c82d8c85e1af93ceac0ca7457663d5f5ba7c7d893e3c2b3003e26c', 'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed'),
 'metrics_dashboard.py': ('3013d511f1d933fe6012df5cecd7f8a8861824bdd41580cbe241b7498916f1c6', '3d1aa1950e6b1c5224ace3aecb9c837e433e5c36941b89465b414749f903da27'),
 'experiment_status.py': ('e7048ec8365bca60f7bd320794c635e491407b33113e37a617f06f9f9d56c237', 'aa1d018902be0875ff237e9cb3fa1bb29f066f4480123cf783a99091551d722c'),
 'rejected_gap_telemetry.py': (None, 'd58610a139644b79f39504e48e1bc43bda9837cc51d743bec623103918c50cbd'),
}
HELPER_HASHES = {
 'live_host': '0993ed57c6c32ad629b7ed078133e77fb0c54b211c8a324ef9bf7327d62b97f3',
 'metrics': '579dafd9410f9e97872074c444e5fb0e79b24a67e7476568c27faaf3341fd9ed',
 'identity': 'ee1fa4f3018eccc479cfe4e484883505115aaeeb8778801657d2a37af6b071f0',
 'protection': 'e45965d3057ec8542ab2b05fd2250209e53986a0977fbb1294aa54f64a11f0f0',
 'bank_state': 'e0c69fb38f5fec86e117edf42b4ff1ce2ff44b82b979c5240116121a7a1ce54f',
 'controller': 'fd4e9d7b9b562c2bd6c663b9651d02b4167a3f552fcacb71cb8571440f3e9bf5',
 'v4': 'fdf7c8bfb123b494252acf83d724a51acda95bb7f00877eace28b60d0377ed18',
 'phase_script': 'b2e732dc731b2b601f7499d2cafd5841896daf2b0713d496b98cb6b8d7279519',
 'phase_strict': '9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8',
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def load(path, digest, name):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Pinned activation dependency changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fixed(base, H, pin, path, digest):
    require(pin['path'] == str(path) and pin['sha256'] == digest, 'Wrong fixed source/closed authority')
    return H.immutable(base, pin)


def check_sources(cfg, base):
    entries = cfg['sources']
    expected = {str(GAME/'Scripts/dqn'/name): values for name, values in DELTAS.items()}
    require(len(entries) == 4 and {e['destination'] for e in entries} == set(expected), 'Exactly four diagnostic source destinations required')
    before_map = cfg['before']['bindings']['source_hashes']
    require(len(before_map) == 61, 'Authentic unchanged61 source map required')
    for entry in entries:
        path = entry['destination']; old, new = expected[path]
        require(set(entry) == {'destination', 'before', 'after'}, 'Exact source lifecycle fields required')
        if old is None:
            require(entry['before'] is None and path not in before_map, 'New telemetry helper must be absent from old map')
        else:
            require(entry['before']['path'] == path and entry['before']['sha256'] == old and before_map[path] == old, 'Held source before differs')
            base.pin(entry['before'], base.MAX_SOURCE)
        after = entry['after']
        require(after['path'] != path and after['sha256'] == new and after['identity']['mode'] == '0o444'
            and after['identity']['uid'] == os.getuid() and after['identity']['nlink'] == 1, 'Exact independent readonly combined source required')
        base.pin(after, base.MAX_SOURCE)
    require(not any(p['path'] in expected for p in cfg['static_pins']), 'Four mutable sources must use Sources lifecycle, not static inode pins')
    after_map = dict(before_map)
    after_map.update({path: values[1] for path, values in expected.items()})
    require(len(after_map) == 62, 'Expected source map must extend61 to62')
    return after_map


def check_regressions(base, H, aggregate, release_pin):
    require(aggregate['tests_run'] == aggregate['tests_passed'] == 43 and aggregate['tests_skipped'] == 0
        and aggregate['quality_publication_canonical_adoption_and_freeze_release'] == release_pin
        and aggregate['combined_source_applied'] is False,
        'Actual original43 guards under current release required')
    bases = aggregate['source_bases_still_unchanged']
    expected = {str(GAME/'Scripts/dqn'/name): values[0] for name,values in DELTAS.items()}
    require(isinstance(bases,list) and len(bases)==4 and {x['path'] for x in bases}==set(expected)
        and all((x.get('absent') is True and set(x)=={'path','absent'}) if expected[x['path']] is None
            else x.get('sha256')==expected[x['path']] and x.get('absent',False) is False for x in bases),
        'Actual four held-source descriptors/new-helper absence required')
    suites = aggregate['suites']
    require([s['suite'] for s in suites] == ['GC-control', 'rejected-gap', 'combined-observation'], 'Exact original19+12+12 suites required')
    for suite, count in zip(suites, (19, 12, 12)):
        value = H.immutable(base, suite['result'])
        require(value['original'] == suite['original'] and value['original_exec_code'] == 1
            and value['original_exit'] == suite['original_exit'] == 0 and value['original_result'] == 'success'
            and value['tests_run'] == value['tests_passed'] == count and value['tests_skipped'] == 0
            and value['original_archived_before_release'] is True and value['unit_released'] is True
            and len(value['full_original_archives']) == 6 and len(value['owned_release']) == 2
            and [x['unit'] for x in value['owned_release']] == [value['original']['timer'], value['original']['unit']]
            and all(x['stop']['exit'] == 0 and x['final']['exit'] == 0 for x in value['owned_release'])
            and suite['all_six_archive_exits0'] is True and suite['timer_first_owned_release'] is True
            and suite['units_fresh_not_found'] is True and suite['original_pid_absent'] is True and suite['attempts'] == 1,
            'Original successful test outcome/archive/release must remain preserved')


def validate(job, base, adapter, H):
    require(set(job) == {'schema', 'activation_authorized', 'transition', 'entry_CPU', 'entry_CPU_release',
        'quality_release', 'regression_result', 'combined_manifest', 'activation_intent'}, 'Exact healthy activation job fields required')
    require(job['schema'] == SCHEMA and job['activation_authorized'] is True, 'Explicit root healthy activation authorization required')
    cfg = copy.deepcopy(job['transition'])
    release = fixed(base, H, job['quality_release'], RELEASE, RELEASE_SHA)
    require(release['schema'] == 'robotron-root-confirmed-protection-adoption-and-sourcefreeze-release-v1'
        and release['source_freeze_released'] is True and release['source_changed'] is False
        and release['both_independent_candidate_gates_pass'] is True and release['C1_original_failed_audit_preserved'] is True,
        'Actual current published quality source freeze release required')
    combined = fixed(base, H, job['combined_manifest'], COMBINED, COMBINED_SHA)
    require(combined['activation_authorized'] is False and Path(combined['selection']['only_patch']['path']).name == 'combined-unapplied-reviewed2.patch'
        and combined['selection']['only_patch']['sha256'] == 'ecc2a1fc887e181b08c8fa7fc3df30a39a736277d112f1303dc9f5afb56d046b'
        and combined['selection']['only_preservation']['sha256'] == '94a52d22c6885627e292f57319e52f0bfe59eeae97551bb2cbf23ba190ca5947', 'Only exact reviewed2 combined bytes selected')
    aggregate = fixed(base, H, job['regression_result'], REGRESSION, REGRESSION_SHA)
    check_regressions(base, H, aggregate, job['quality_release'])
    entry = H.immutable(base, job['entry_CPU']); entry_release = H.immutable(base, job['entry_CPU_release'])
    spec = entry['root_job']['phase_snapshot']; owner = spec['owner']; phase = cfg['running_phase']; env = cfg['before']['environment']
    require(entry['schema'] == 'robotron-phase-snapshot-checkpoint-CPU-result-v1' and entry['status'] == 'PASS'
        and entry['phase_metadata_verified'] is True and spec['purpose'] == 'candidate' and spec['observed_clients'] == 192
        and entry['root_job']['verifier_sha256'] == adapter.PHASE_SHA and entry['root_job']['strict_phase_base_sha256'] == adapter.STRICT_SHA
        and entry['held_recipe_context']['batch_size'] == 4096 and entry['held_recipe_context']['learning_control_lr_scale'] == 0.5,
        'Genuine same-owner historical b2e candidate192 .5 floor required; never boot source')
    require(entry_release['original_exec_code'] == 1 and entry_release['original_exit'] == 0
        and entry_release['original_result'] == 'success' and entry_release['unit_released'] is True
        and entry_release['original_archived_before_release'] is True, 'Original historical candidate CPU release required')
    # The actual launcher uses CPU_report; reports from unrelated retained units cannot supply this floor.
    require(entry_release['CPU_report'] == job['entry_CPU'], 'Historical CPU release must bind this exact readonly report')
    require(spec['phase_record'] == phase['record'] and spec['boot_checkpoint'] == phase['boot_checkpoint']
        and spec['expected_phase'] == phase['expected']
        and adapter.triple(spec['boot_verification']) == adapter.triple(phase['boot_verification']), 'Actual running phase differs from historical same-owner floor')
    record = H.immutable(base, phase['record']); boot = H.immutable(base, phase['boot_verification'])
    require(record['metric'] == 'ce' and record['action'] == 'start' and record['previous_metric'] == 'ce'
        and record['checkpoint'] == phase['boot_checkpoint'] and phase['expected'] == adapter.expected_start(record, phase['record'], boot)
        and boot['status'] == 'PASS' and boot['phase_metadata_verified'] is True
        and boot['sha256'] == phase['boot_checkpoint']['sha256'] and boot['bytes'] == phase['boot_checkpoint']['bytes']
        and entry['saved_priority_metric_phase']['valid'] is True and entry['saved_priority_metric_phase']['metric'] == 'ce'
        and entry['saved_priority_metric_phase']['phase_id'] == record['phase_id'], 'Authentic current CE founder/boot metadata required')
    require(set(owner) == {'pid','starttime_ticks','unit','invocation_id','cgroup'} and type(owner['pid']) is int
        and owner['pid'] > 0 and type(owner['starttime_ticks']) is int and owner['starttime_ticks'] > 0
        and re.fullmatch('[0-9a-f]{32}', owner['invocation_id'] or ''), 'Exact actual healthy owner required')
    before = cfg['before']; process = before['bindings']['worker']['trainer']
    require(cfg['game_root'] == str(GAME) and cfg['model_dir'] == str(GAME/'models_dqn') and cfg['mode'] == 'return_ce'
        and cfg['trainer_unit'] == owner['unit'] and before['trainer']['MainPID'] == str(owner['pid'])
        and before['trainer']['ControlGroup'] == owner['cgroup'] and process['pid'] == owner['pid']
        and process['starttime_ticks'] == owner['starttime_ticks'] and before['trainer']['ActiveState'] == 'active', 'Fresh healthy BEFORE must bind actual same owner')
    require(cfg['experiment'] == entry['root_job']['experiment'] and env.get('DQN_BATCH_SIZE') == '4096'
        and env.get('DQN_PER_PRIORITY_METRIC') == 'ce' and env.get('DQN_PRIORITY_PHASE_RECORD') == phase['record']['path']
        and env.get('DQN_PRIORITY_PHASE_RECORD_SHA256') == phase['record']['sha256'] and env.get('DQN_RATCHET') == '0'
        and env.get(FLAG, '0') == '0' and not any(env.get(k) for k in adapter.FLAGS)
        and env.get('DQN_EXACT_GRAPH_CHECKPOINT') == str(GAME/'models_dqn/robotron_dqn_latest.pt')
        and (env.get('ROBOTRON_DQN_MODEL_DIR','').strip() or str(GAME/'models_dqn')) == cfg['model_dir'], 'Held .5/CE4096/latest-only recipe and disabled telemetry required')
    actors = before['bindings']['actors']
    require(len(actors) == 192 and [a['client_slot'] for a in actors] == list(range(192))
        and len({a['pid'] for a in actors}) == 192 and set(cfg['actor_masks']) == {str(a['pid']) for a in actors}
        and all(v == list(range(72)) for v in cfg['actor_masks'].values()) and cfg['worker_mask'] == list(range(72)), 'Exact original192 slot/identity/mask set required')
    check_sources(cfg, base)
    require(all(before['bindings']['source_hashes'][str(GAME/'Scripts/dqn'/name)]==sha for name,sha in adapter.CANDIDATE.items()),
        'Held numerical candidate5 source map differs')
    require(cfg['timeouts'] == dict(ready_s=600, save_s=60, cpu_s=120)
        and cfg['baseline_csv']['batch_size'] == 4096 and cfg['baseline_csv']['replay_sample_cap'] == 8
        and cfg['bank_spec'] == dict(ring='/dev/shm/robotron_dqn_latest_replay',model_dir=cfg['model_dir'],capacity=6000000,state_size=11128,
            episode_capacity=192,bank_strides=dict(hof=1536,ephof=2048)), 'Unchanged cap8/6M replay/banks/deadlines required')
    require(re.fullmatch('[A-Za-z0-9_-]{1,100}', cfg['phase_id'] or '') and cfg['phase_id'] != record['phase_id']
        and re.fullmatch('[A-Za-z0-9_-]{1,120}', cfg['request_id'] or '') and re.fullmatch('[A-Za-z0-9_-]{1,80}', cfg['startup_tag'] or '')
        and re.fullmatch('[0-9a-f-]{36}', cfg['boot_id'] or ''), 'Fresh phase/request/startup/current boot identities required')
    intent = H.immutable(base, job['activation_intent'])
    require(set(intent) == {'schema','owner','running_phase','phase_id','sources','quality_release','regression_result',
        'combined_manifest','boot_newest_only','no_weight_or_optimizer_rollback','retain_original_fleet','target_batch_size',
        'target_lr_scale','telemetry_environment','fleet_actions_forbidden'} and intent['schema'] == INTENT_SCHEMA
        and intent['owner'] == owner and intent['running_phase'] == phase and intent['phase_id'] == cfg['phase_id']
        and intent['sources'] == cfg['sources'] and cfg['trial_core'] == job['activation_intent']
        and all(intent[k] == job[k] for k in ('quality_release','regression_result','combined_manifest'))
        and intent['boot_newest_only'] is True and intent['no_weight_or_optimizer_rollback'] is True
        and intent['retain_original_fleet'] is True and intent['fleet_actions_forbidden'] is True
        and intent['target_batch_size'] == 4096 and intent['target_lr_scale'] == 0.5
        and intent['telemetry_environment'] == {FLAG:'1'}, 'Exact healthy four-source activation intent required')
    require(cfg['current_completed_request']['path'] == str(GAME/'models_dqn/managed_save.request.json.completed')
        and cfg['settings_lifecycle']['initial']['path'] == str(GAME/'models_dqn/game_settings.json')
        and cfg['settings_lifecycle']['policy'] == 'same_bytes_after_owned_stop_only'
        and cfg['original_dropin']['path'] == str(Path('/run/user')/str(os.getuid())/'systemd/user'/(cfg['trainer_unit']+'.d')/'91-per-priority-phase.conf'), 'Exact mutable settings/completed/91 lifecycle paths required')
    require(set(cfg['helper_pins']) == set(HELPER_HASHES) and all(cfg['helper_pins'][k]['sha256'] == v for k,v in HELPER_HASHES.items())
        and cfg['helper_pins']['controller']['path'] == str(H.ADAPTER) and cfg['helper_pins']['v4']['path'] == str(adapter.V4)
        and cfg['phase_verifier']['script'] == cfg['helper_pins']['phase_script']
        and cfg['phase_verifier']['strict_base'] == cfg['helper_pins']['phase_strict'], 'Exact proven selected helper family/b2e/9ef required')
    require(cfg['verifier']['context'] == entry['root_job']['source_control_context']
        and before['bindings']['control_hashes'][str(GAME/'models_dqn/learning_control.json')] == cfg['verifier']['context']['archived_control']['sha256'], 'Held .5 control and authentic numerical context required')
    for value in cfg['helper_pins'].values():base.pin(value, base.MAX_SOURCE)
    for value in cfg['static_pins']:base.pin(value, base.MAX_SOURCE)
    base.pin(cfg['current_completed_request'], base.MAX_JSON)
    base.validate_python_binding(cfg['verifier'], cfg['insurance_verification'], hash_executable=True)
    return cfg, entry


def trainer_command_allowed(args, trainer):
    return args == ('daemon-reload',) or args in (('start','--no-block',trainer), ('stop','--no-block',trainer))


def actor_guard(runtime, *, paused=None):
    """Exact original identities, slots, cgroup, supervisor, masks and global set."""
    before = runtime.job['before']; host = runtime.host
    fleet = host.unit(runtime.job['fleet_unit'])
    require(fleet['MainPID'] == before['fleet']['MainPID'] and fleet['ActiveState'] == 'active'
        and fleet['ControlGroup'] == before['fleet']['ControlGroup'], 'Original fleet supervisor/cgroup changed')
    stat_text = (Path('/proc')/fleet['MainPID']/'stat').read_text()
    require(runtime.metrics.identity.stat_fields(stat_text)['starttime_ticks'] == before['supervisor_start_ticks'], 'Original fleet supervisor PID reused')
    actors, _ = runtime.metrics.discover_fleet_actors(before['bindings']['fleet_cgroup'])
    require(actors == before['bindings']['actors'], 'Original full192 actor descriptor/slot set changed')
    for actor in actors:
        require(sorted(os.sched_getaffinity(actor['pid'])) == runtime.job['actor_masks'][str(actor['pid'])], 'Original actor mask changed')
        if paused is True:require(host.actor_stopped(actor), 'An original actor is not paused')
    global_actors = set()
    for item in Path('/proc').iterdir():
        if not item.name.isdecimal():continue
        try:argv = (item/'cmdline').read_bytes().split(b'\0')
        except OSError as error:
            if error.errno in (errno.ENOENT, errno.ESRCH):continue
            raise
        if argv and os.path.basename(os.fsdecode(argv[0])) == 'mame' and b'robotron' in argv:
            global_actors.add(int(item.name))
    require(global_actors == {a['pid'] for a in actors}, 'Extra/missing global Robotron actors; no replacement adoption')
    return dict(supervisor_pid=int(fleet['MainPID']), supervisor_starttime_ticks=before['supervisor_start_ticks'],
        actor_count=len(actors), original_actor_set_unchanged=True, original_masks_unchanged=True, paused_required=paused)


@contextmanager
def diagnostic_environment(adapter):
    original = adapter.selected_environment
    def selected(before, metric, record):
        value = original(before, metric, record)
        value[FLAG] = '1'
        return value
    adapter.selected_environment = selected
    try:yield
    finally:adapter.selected_environment = original


def make_runtime(base, adapter, H, cfg, output, entry):
    runtime = H.runtime_class(base, adapter)(cfg, output, entry)
    original_command = runtime.host.command
    def only_trainer(*args):
        require(trainer_command_allowed(args, cfg['trainer_unit']), 'Fleet/startmame/non-owned service actions forbidden')
        return original_command(*args)
    runtime.host.command = only_trainer
    original_inspect = runtime.inspect
    def inspect(phase):
        value = original_inspect(phase)
        actor_guard(runtime)
        return value
    runtime.inspect = inspect
    return runtime


def activate(runtime, sources, base, adapter, H, coverage_module):
    result = dict(schema=RESULT_SCHEMA,status='RUNNING',maintenance_only=True,qualification_pass=False,
        old_owner=copy.deepcopy(runtime.insured),ancestor_phase=copy.deepcopy(runtime.job['running_phase']),
        source_application_attempts=0,owned_start_attempts=0,manual_recovery_required=True)
    try:
        before = runtime.initial()
        runtime.floor = adapter.clock_max(runtime.floor, runtime.initial_api)
        raw = runtime.raw_api()
        require(raw['client_count'] == 192 and raw['training_enabled'] is True and raw['measurement_active'] is False
            and raw['managed_experiment'] == runtime.job['experiment'] and raw['lr'] == 2.5e-5
            and raw['ts'] >= runtime.initial_api['ts'] and all(raw[k] >= runtime.initial_api[k] for k in adapter.CLOCKS)
            and all(runtime.metrics.exposure_key(raw['host_pipeline']['learning_exposure'][k]) == runtime.metrics.exposure_key(runtime.initial_api['exposure'][k]) for k in ('optimizer','replay')),
            'Fresh healthy192 recipe/epoch/clocks must precede any pause/source application')
        runtime.floor = adapter.clock_max(runtime.floor, raw)
        result['fresh_before_raw_API'] = base.publish(runtime.output/'pre-ending-health.json', raw)
        sources.stage()
        actor_guard(runtime)
        runtime.host.begin_transition_logs(before['bindings']['logs'], before['trainer_stdout'])
        runtime.host.pause(dict(initial=runtime.job['before']))
        result['paused_original192'] = actor_guard(runtime, paused=True)
        retired = runtime.stop_owned(before); result['retired_owner'] = retired
        actor_guard(runtime, paused=True)
        newest = runtime.stopped_checkpoint(retired, 'newest-stopped')
        proof = base.read_json(newest['verification'])
        phase_record = base.read_json(runtime.job['running_phase']['record'])
        require(proof['status'] == 'PASS' and proof['phase_metadata_verified'] is True
            and proof['held_recipe_context']['batch_size'] == 4096 and proof['held_recipe_context']['learning_control_lr_scale'] == 0.5
            and proof['root_job']['phase_snapshot']['purpose'] == 'newest_stopped'
            and proof['root_job']['phase_snapshot']['observed_clients'] == 192
            and proof['saved_priority_metric_phase']['phase_id'] == phase_record['phase_id']
            and proof['saved_priority_metric_phase']['metric'] == 'ce' and proof['saved_priority_metric_phase']['valid'] is True
            and all(proof['clocks'][k] >= runtime.floor[k] for k in adapter.CLOCKS), 'Actual newest stopped healthy CE/.5 CPU must pass before source write')
        runtime.recovery_saved_phase = copy.deepcopy(proof['saved_priority_metric_phase'])
        runtime.floor = adapter.clock_max(runtime.floor, proof['clocks'])
        result['newest_stopped'] = newest
        banks = runtime.banks.stopped_state(runtime.job['bank_spec']); result['stopped_banks_and_ring'] = banks
        actor_guard(runtime, paused=True)
        result['source_application_attempts'] = 1
        sources.reconcile('after', runtime.absence, runtime.metrics.block_restore_signals)
        result['source_transaction'] = adapter.source_state(sources)
        actor_guard(runtime, paused=True)
        result['owned_start_attempts'] = 1
        owner = H.start_repair_CE4096(runtime, adapter)
        start = base.read_json(runtime.start_request); deadline = start['monotonic_s'] + 600
        loaded = H.ready_with_budget(runtime, banks, actors=False, deadline=deadline)
        actor_guard(runtime, paused=True)
        raw = runtime.raw_api(); adapter.zero_replay(raw, owner['pid'])
        startup = runtime.startup_snapshot(raw)
        startup['phase_CPU_readonly_archive'] = H.archive_report(base, startup['phase_CPU'], runtime.output/'CE-startup-CPU-readonly.json')
        raw = runtime.raw_api(); require(raw['client_count'] == 0, 'No actor admission before startup strictCPU0')
        adapter.zero_replay(raw, owner['pid'])
        before_resume = base.publish(runtime.output/'API-before-resume.json', raw)
        runtime.inspect('after'); runtime.banks.assert_unchanged(banks, runtime.job['bank_spec'])
        result['before_resume_original192'] = actor_guard(runtime, paused=True)
        runtime.host.metric_host.configure_logs(runtime.job['before']['bindings']['logs'])
        coverage = coverage_module.TransitionCoverage(runtime, base, runtime.output/'transition-coverage')
        result['initial_resume'] = base.resume_all(runtime.host)
        require(not result['initial_resume']['failures'], 'Original actors could not resume')
        reconnect = coverage_module.reconnect_and_strict(runtime, base, H, banks, deadline, coverage)
        result['final_original192'] = actor_guard(runtime)
        result.update(status='READY_HEALTHY_DIAGNOSTIC_ACTIVATION',owner=owner,boot_checkpoint=newest,
            start_request=runtime.start_request,phase_record=runtime.record_pin,loaded=loaded,startup=startup,
            before_resume_API=before_resume,reconnect=reconnect,healthy192=reconnect['healthy192'],manual_recovery_required=False)
    except BaseException as error:
        result.update(status='FAILED',error=repr(error),traceback=traceback.format_exc(),manual_recovery_required=True)
        if runtime.start_request is not None:
            try:
                if runtime.host.unit(runtime.job['trainer_unit'])['MainPID'] != '0':
                    require(runtime.host.known_trainer is not None, 'Unknown replacement; no stop authority')
                    for actor in runtime.job['before']['bindings']['actors']:
                        if actor not in runtime.host.paused:
                            with runtime.metrics.block_restore_signals():
                                runtime.host.paused.append(actor); runtime.host.signal_actor(actor, signal.SIGSTOP)
                    runtime.host.wait_paused(); result['failed_new_owner_retired'] = runtime.stop_owned()
            except BaseException as cleanup:result['stop_error'] = repr(cleanup)
        try:result['known_source_state'] = adapter.source_state(sources)
        except BaseException as evidence:result['evidence_error'] = repr(evidence)
    finally:
        # Emergency undo never depends on source/log/health success; all matching
        # registered original actors are attempted. First failure remains FAILED.
        with runtime.metrics.block_restore_signals():result['final_resume'] = base.resume_all(runtime.host)
        result['CPU_ledger'] = copy.deepcopy(runtime.cpu_attempts)
        result['owned_request_at_terminal'] = runtime.pending
        if result['final_resume']['failures']:result['manual_recovery_required'] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true'); parser.add_argument('--job',type=Path)
    parser.add_argument('--expected-job-sha256'); parser.add_argument('--expected-source-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print(PLAN); return 0
    require(args.job and args.expected_job_sha256 and args.expected_source_sha256, 'Explicit immutable root job/source bindings required')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.expected_source_sha256, 'Activation source changed')
    require(not any(n == 'torch' or n.startswith(('torch.','numpy','dqn')) for n in sys.modules), 'Fresh stdlib-only parent required')
    H = load(HEALTHY, HEALTHY_SHA, '_diagnostic_healthy_primitives')
    C = load(COVERAGE, COVERAGE_SHA, '_diagnostic_coverage_primitives')
    metadata = H.load(H.DEADLINE,H.DEADLINE_SHA,'_diagnostic_metadata')
    jp,_ = metadata.pin(args.job)
    require(jp['sha256'] == args.expected_job_sha256 and jp['identity']['mode'] == '0o444'
        and jp['identity']['uid'] == os.getuid() and jp['identity']['nlink'] == 1, 'Immutable root job differs')
    job = metadata.read_pin(jp)
    adapter = H.load(H.ADAPTER,H.ADAPTER_SHA,'_diagnostic_phase_primitives'); base = adapter.load_v4()
    base.BLOCKED = base.BLOCKED | frozenset({Path(__file__).name,'run_healthy_ce_maintenance.py','run_forward_recovery.py'})
    cfg,entry = validate(job,base,adapter,H)
    output = Path(cfg['output_directory'])
    require(output.is_absolute() and output == output.resolve(strict=False) and output.is_relative_to(RUN)
        and output.parent == RUN and output.parent.is_dir() and not output.exists(), 'NEW direct run26 output required')
    output.mkdir(mode=0o700)
    roots = dict(output_directory=str(output),return_intent=dict(output_directory=str(output)))
    trial = H.load(H.TRIAL,H.TRIAL_SHA,'_diagnostic_trial_primitives')
    trial.bounded_copy_dispatch(base,roots,cfg); trial.raw_api_publication(base,metadata,roots,cfg)
    runtime = None
    try:
        with diagnostic_environment(adapter):
            runtime = make_runtime(base,adapter,H,cfg,output,entry)
            directory = output/'source-transaction'; directory.mkdir(mode=0o700)
            sources = base.Sources(cfg['sources'],directory)
            with runtime.metrics.interrupt_handlers():result = activate(runtime,sources,base,adapter,H,C)
            result['root_job'] = jp; base.publish(output/'result.json',result)
            return 0 if result['status'] == 'READY_HEALTHY_DIAGNOSTIC_ACTIVATION' and not result['manual_recovery_required'] else 1
    finally:
        if runtime is not None:runtime.close()


if __name__ == '__main__':
    raise SystemExit(main())
