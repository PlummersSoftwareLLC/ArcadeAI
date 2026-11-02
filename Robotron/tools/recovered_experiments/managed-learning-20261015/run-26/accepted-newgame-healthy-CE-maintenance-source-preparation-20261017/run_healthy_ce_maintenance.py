#!/usr/bin/env python3
"""One healthy newest-state CE4096 maintenance for the reviewed socket fix.

Literal PLAN is read-free. No protected/entry/insurance rollback, trial, quality,
policy rescue, replay clearing, or automatic second start is performed.
"""
import argparse
import base64
import copy
import datetime
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

SCHEMA = 'robotron-accepted-newgame-healthy-CE-maintenance-job-v1'
RESULT_SCHEMA = 'robotron-accepted-newgame-healthy-CE-maintenance-result-v1'
GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
Q = GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal'
TRIAL = Q/'live_one_trial_installed_ce_revision2_proposal/run_one_trial.py'
TRIAL_SHA = '1d007e6407e807575149084aff63ad0df27e677bf6f40f373d5267973893b85f'
DEADLINE = TRIAL.parent/'deadline_guard.py'
DEADLINE_SHA = '8df7491a59025e07387bdf0d392ca2b748511d7adae3cf087abf342a5acfe36a'
ADAPTER = TRIAL.parent/'run_raw_kl_transition.py'
ADAPTER_SHA = 'fd4e9d7b9b562c2bd6c663b9651d02b4167a3f552fcacb71cb8571440f3e9bf5'
SOCKET = GAME/'Scripts/dqn/socket_server.py'
BEFORE_SHA = 'd99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214'
AFTER_SHA = '4a1f6a3cc7c82d8c85e1af93ceac0ca7457663d5f5ba7c7d893e3c2b3003e26c'
PATCH_MANIFEST = GAME/'logs/managed-learning-20261015/run-26/accepted-newgame-replay-boundary-unapplied-source-preparation-20261017/preparation-manifest.json'
PATCH_MANIFEST_SHA = '92ed9c74e2501c68522a083fa0f1cbb53be4020840140f899cd1f76d7d6c3830'
CURRENT_OWNER = dict(pid=1626184,starttime_ticks=36413669,unit='robotron-managed-run-26-d3b365c9-trainer.service',invocation_id='168cea96ca864434b5cf12a3651ee39e',cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-managed-run-26-d3b365c9-trainer.service')
CURRENT_PHASE_ID = 'ce4096_forward_after_failed_return_trial02_20261017'
CURRENT_PHASE_RECORD_SHA = '9b3b839fe39044538412f0f78a8c28feae60170ea2d1c363d21efeead17d84d1'
ACTUAL_RELEASE = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/lr25-first8M-partial-invalid49-owned-closure-root-20261017/root-explicit-current-partial-invalid49-quality-source-freeze-release.json', 'sha256': 'a7d7f523674d8135535779da782eb4ab3aa342b012695960f1ccef03b0fd6e7f', 'bytes': 3993}
ACTUAL_PATCH_GUARDS = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/accepted-newgame-boundary-seven-guards-root-execution-20261017/root-original-seven-guard-result-and-owned-release.json', 'sha256': 'd64b8d5fb74e7c5904fce6623924ebd682646a3baa34e7d6220e769181a0c7ed', 'bytes': 6503}
PLAN = 'PLAN_ONLY: one authorized healthy CE4096 newest-state socket maintenance; no reads/actions'

def require(value, message):
    if not value: raise RuntimeError(message)

def load(path, digest, name):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Pinned repair dependency changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


def immutable(base, item):
    base.pin(item, base.MAX_JSON)
    require(item['identity']['mode']=='0o444' and item['identity']['uid']==os.getuid()
        and item['identity']['nlink']==1, 'Owned readonly metadata required')
    return base.read_json(item)


def validate(job, base, adapter):
    require(set(job)=={'schema','activation_authorized','transition','entry_CPU','entry_CPU_release',
        'quality_release','patch_manifest','patch_guard_result','maintenance_intent'}, 'Exact healthy maintenance job fields required')
    require(job['schema']==SCHEMA and job['activation_authorized'] is True, 'Explicit healthy maintenance authorization required')
    cfg=copy.deepcopy(job['transition']); entry=immutable(base,job['entry_CPU'])
    entry_release=immutable(base,job['entry_CPU_release']); intent=immutable(base,job['maintenance_intent'])
    release=immutable(base,job['quality_release']); guards=immutable(base,job['patch_guard_result'])
    require(ACTUAL_RELEASE is not None and adapter.triple(job['quality_release'])==ACTUAL_RELEASE, 'Exact actual CURRENT release unbound/different')
    require(release['schema']=='robotron-lr25-partial-invalid49-explicit-quality-source-freeze-release-v1'
        and release['source_freeze_released'] is True and release['owned_cleanup_complete'] is True
        and release['binding_job']['sha256']=='0e9975256cb6735248b8c137d5fac9862926666503a8280ba111625856e77471'
        and release['native_plan']['sha256']=='3a9dc2b00f3e03fd93dd23aa1252fe019983d589bfd5f04a38e01482fb2be834'
        and release['original_parent']==dict(pid=2027753,starttime_ticks=37482172,invocation_id='c120d301051a4816ac278f01b37bd51a',exit_code=1)
        and release['native_outcome']=='invalid' and release['completed_legs']==[1,2]
        and release['R2_C2_not_run'] is True and release['C1_count']==49 and release['minimum_count']==50
        and release['quality_acceptance'] is False and release['all_four_completed'] is False,
        'Actual partial INVALID49 current campaign closure/release required, never an old winning/all4 release')
    require(job['patch_manifest']['path']==str(PATCH_MANIFEST) and job['patch_manifest']['sha256']==PATCH_MANIFEST_SHA,
        'Wrong reviewed unapplied patch family')
    immutable(base,job['patch_manifest'])
    require(ACTUAL_PATCH_GUARDS is not None and adapter.triple(job['patch_guard_result'])==ACTUAL_PATCH_GUARDS, 'Exact actual original seven-guard receipt unbound/different')
    require(guards['schema']=='robotron-accepted-newgame-boundary-seven-guards-original-result-v1'
        and guards['status']=='PASS' and guards['original_exec_code']==1 and guards['original_exit']==0
        and guards['original_result']=='success' and guards['tests_run']==guards['tests_passed']==7
        and guards['tests_skipped']==0 and guards['original_attempts']==1
        and guards['original_archived_before_release'] is True and guards['unit_released'] is True
        and adapter.triple(guards['source_manifest'])==adapter.triple(job['patch_manifest'])
        and adapter.triple(guards['freeze_release'])==adapter.triple(job['quality_release'])
        and guards['test_source']['sha256']=='cf116f2790bc2b901d7f70197584511cb587d1ca70e08ec0d61e986c0d6c7625'
        and guards['source_peer']['sha256']=='830a9948e0c981e4e45c0a7eb64aac368fa6924e1ba3d90f805b39674b17d5f2'
        and guards['source_application'] is False and guards['actual_deployment'] is False
        and len(guards['owned_release'])==2
        and all(item['final_load_state']=='not-found' for item in guards['owned_release']),
        'Genuine root seven-guard original PASS and owned release required')
    prior=immutable(base,intent['prior_maintenance'])
    require(intent['prior_maintenance']['sha256']=='b4019062ff5275e842156a643818a6d8205d702e0fce0c5a51ab18d493f5d3b0'
        and prior['status']=='READY_CE_FORWARD_REPAIR' and prior['owner']==CURRENT_OWNER
        and prior['startup']['phase']==cfg['running_phase'], 'Actual separate CE4096 maintenance ancestor required')
    prior_job=immutable(base,prior['root_job'])
    require(intent['original_failed_trial']==prior_job['trial_result']
        and intent['original_failed_return']==prior_job['return_result'], 'Full original failed trial/return ancestry must remain retained')
    spec=entry['root_job']['phase_snapshot']; phase=cfg['running_phase']; env=cfg['before']['environment']
    require(entry['status']=='PASS' and entry['schema']=='robotron-phase-snapshot-checkpoint-CPU-result-v1'
        and entry['phase_metadata_verified'] is True and spec['purpose']=='candidate'
        and spec['observed_clients']==192 and spec['owner']==CURRENT_OWNER
        and entry['root_job']['verifier_sha256']==adapter.PHASE_SHA
        and entry['root_job']['strict_phase_base_sha256']==adapter.STRICT_SHA
        and entry['held_recipe_context']['batch_size']==4096
        and entry['held_recipe_context']['learning_control_lr_scale']==0.5,
        'Genuine current-owner historical .5/B4096 live192 b2e entry proof required')
    require(entry_release['status']=='PASS' and entry_release['CPU_report']==job['entry_CPU']
        and entry_release['original_exec_code']==1 and entry_release['original_exit']==0
        and entry_release['original_result']=='success' and entry_release['unit_released'] is True
        and entry_release['original_archived_before_release'] is True,
        'Actual original entry CPU0 archive required; this is not fresh health')
    require(spec['phase_record']==phase['record'] and spec['boot_checkpoint']==phase['boot_checkpoint']
        and spec['expected_phase']==phase['expected']
        and all(spec['boot_verification'][k]==phase['boot_verification'][k] for k in ('sha256','bytes')),
        'Historical entry/current running CE descriptor differs')
    record=immutable(base,phase['record']); boot=immutable(base,phase['boot_verification'])
    require(record['metric']=='ce' and record['action']=='start' and record['previous_metric']=='ce'
        and record['phase_id']==CURRENT_PHASE_ID and phase['record']['sha256']==CURRENT_PHASE_RECORD_SHA
        and record['checkpoint']==phase['boot_checkpoint']
        and phase['expected']==adapter.expected_start(record,phase['record'],boot)
        and boot['status']=='PASS' and boot['phase_metadata_verified'] is True
        and boot['sha256']==phase['boot_checkpoint']['sha256'] and boot['bytes']==phase['boot_checkpoint']['bytes']
        and entry['saved_priority_metric_phase']['valid'] is True
        and entry['saved_priority_metric_phase']['phase_id']==CURRENT_PHASE_ID
        and entry['saved_priority_metric_phase']['metric']=='ce', 'Genuine healthy CE9b3 founder/boot required')
    require(cfg['game_root']==str(GAME) and cfg['model_dir']==str(GAME/'models_dqn')
        and cfg['trainer_unit']==CURRENT_OWNER['unit'] and cfg['mode']=='return_ce'
        and cfg['experiment']==entry['root_job']['experiment']
        and env.get('DQN_BATCH_SIZE')=='4096' and env.get('DQN_PER_PRIORITY_METRIC')=='ce'
        and env.get('DQN_PRIORITY_PHASE_RECORD')==phase['record']['path']
        and env.get('DQN_PRIORITY_PHASE_RECORD_SHA256')==phase['record']['sha256']
        and env.get('DQN_RATCHET')=='0'
        and env.get('DQN_EXACT_GRAPH_CHECKPOINT')==str(GAME/'models_dqn/robotron_dqn_latest.pt')
        and (env.get('ROBOTRON_DQN_MODEL_DIR','').strip() or str(GAME/'models_dqn'))==cfg['model_dir']
        and not any(env.get(k) for k in adapter.FLAGS), 'Held CE4096/current phase/no ratchet/capture recipe required')
    require(cfg['before']['trainer']['MainPID']==str(CURRENT_OWNER['pid'])
        and cfg['before']['trainer']['ControlGroup']==CURRENT_OWNER['cgroup']
        and cfg['before']['bindings']['worker']['trainer']['pid']==CURRENT_OWNER['pid']
        and cfg['before']['bindings']['worker']['trainer']['starttime_ticks']==CURRENT_OWNER['starttime_ticks'], 'Fresh BEFORE must name exact healthy owner')
    require(len(cfg['before']['bindings']['actors'])==192
        and len({a['pid'] for a in cfg['before']['bindings']['actors']})==192
        and set(cfg['actor_masks'])=={str(a['pid']) for a in cfg['before']['bindings']['actors']}
        and all(v==list(range(72)) for v in cfg['actor_masks'].values()) and cfg['worker_mask']==list(range(72)),
        'Original192 actor and inference masks required')
    require(len(cfg['sources'])==1, 'Only one reviewed socket transaction allowed')
    change=cfg['sources'][0]
    require(set(change)=={'destination','before','after'} and change['destination']==str(SOCKET)
        and change['before']['path']==str(SOCKET) and change['before']['sha256']==BEFORE_SHA
        and change['after']['sha256']==AFTER_SHA and change['after']['path']!=str(SOCKET)
        and change['after']['identity']['mode']=='0o444'
        and cfg['before']['bindings']['source_hashes'][str(SOCKET)]==BEFORE_SHA,
        'Exactly the reviewed accepted-newgame socket before/after bytes required')
    for value in (change['before'],change['after']):base.pin(value,base.MAX_SOURCE)
    require(all(p['path']!=str(SOCKET) for p in cfg['static_pins']), 'Mutable socket must use source lifecycle, not static inode PIN')
    require(cfg['timeouts']==dict(ready_s=600,save_s=60,cpu_s=120)
        and cfg['baseline_csv']['batch_size']==4096 and cfg['baseline_csv']['replay_sample_cap']==8,
        'Unchanged readiness/CPU deadlines and B4096/cap8 baseline required')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,100}',cfg['phase_id'] or '') and cfg['phase_id']!=CURRENT_PHASE_ID
        and re.fullmatch(r'[A-Za-z0-9_-]{1,120}',cfg['request_id'] or '')
        and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',cfg['startup_tag'] or ''), 'NEW phase/request/startup identities required')
    require(cfg['trial_core']==job['maintenance_intent'] and intent['schema']=='robotron-accepted-newgame-healthy-CE-maintenance-intent-v1'
        and intent['owner']==CURRENT_OWNER and intent['running_phase']==phase
        and intent['phase_id']==cfg['phase_id'] and intent['socket_before_sha256']==BEFORE_SHA
        and intent['socket_after_sha256']==AFTER_SHA and intent['quality_release']==job['quality_release']
        and intent['patch_guard_result']==job['patch_guard_result']
        and intent['boot_newest_only'] is True and intent['no_weight_or_optimizer_rollback'] is True
        and intent['retain_original_fleet'] is True and intent['target_batch_size']==4096
        and intent['target_lr_scale']==0.5, 'Exact current-owner one-source newest-state maintenance intent required')
    require(cfg['current_completed_request']['path']==str(GAME/'models_dqn/managed_save.request.json.completed'), 'Wrong actual completed slot')
    require(cfg['original_dropin']['path']==str(Path('/run/user')/str(os.getuid())/'systemd/user'/(cfg['trainer_unit']+'.d')/'91-per-priority-phase.conf'), 'Wrong existing owned phase override')
    require(cfg['phase_verifier']['script']['path']==str(adapter.PHASE) and cfg['phase_verifier']['script']['sha256']==adapter.PHASE_SHA
        and cfg['phase_verifier']['strict_base']['sha256']==adapter.STRICT_SHA,
        'Unchanged strict b2e/9ef phase verification required')
    require(cfg['helper_pins']['controller']['path']==str(ADAPTER) and cfg['helper_pins']['controller']['sha256']==ADAPTER_SHA
        and cfg['helper_pins']['v4']['path']==str(adapter.V4) and cfg['helper_pins']['v4']['sha256']==adapter.V4_SHA
        and cfg['helper_pins']['phase_script']==cfg['phase_verifier']['script']
        and cfg['helper_pins']['phase_strict']==cfg['phase_verifier']['strict_base'], 'Recurring proven runtime/CPU source PINs differ')
    require(len(cfg['before']['bindings']['source_hashes'])==61
        and all(cfg['before']['bindings']['source_hashes'][str(GAME/'Scripts/dqn'/name)]==sha for name,sha in adapter.CANDIDATE.items()),
        'Held61 map and original numerical candidate5 must remain exact')
    for value in cfg['helper_pins'].values():base.pin(value,base.MAX_SOURCE)
    for value in cfg['static_pins']:base.pin(value,base.MAX_SOURCE)
    for value in (cfg['current_completed_request'],cfg['phase_verifier']['script'],cfg['phase_verifier']['strict_base']):base.pin(value,base.MAX_SOURCE)
    # These real legacy7d records establish ONLY interpreter provenance. They do
    # not establish current ownership, fresh health or a restart/rollback source.
    base.validate_python_binding(cfg['verifier'],cfg['insurance_verification'],hash_executable=True)
    require(cfg['verifier']['context']==entry['root_job']['source_control_context'], 'Use authentic .5 numerical reconstruction context')
    require(cfg['before']['bindings']['control_hashes'][str(GAME/'models_dqn/learning_control.json')]==cfg['verifier']['context']['archived_control']['sha256'],
        'Actual current learning control must remain the archived .5 entry bytes')
    return cfg,entry


def runtime_class(base, adapter):
    parent=adapter.runtime_class(base)
    class HealthyRuntime(parent):
        def __init__(self,job,output,entry):
            self.job,self.output=copy.deepcopy(job),output
            self.job['readiness_timeout_s']=job['timeouts']['ready_s']
            tools=Path(job['helper_pins']['live_host']['path']).parent
            sys.dont_write_bytecode=True;sys.path.insert(0,str(tools))
            self.primitives=base.load_module(job['helper_pins']['live_host']['path'],'healthy_ce_owned_primitives')
            self.metrics=self.primitives.metrics
            for key,module in (('metrics',self.metrics),('identity',self.metrics.identity),('protection',self.primitives.protection)):
                require(str(Path(module.__file__).resolve())==job['helper_pins'][key]['path'],'Unexpected dependency '+key)
            self.banks=base.load_module(job['helper_pins']['bank_state']['path'],'healthy_ce_bank_state')
            outer=self
            class Host(self.primitives.LiveHost):
                def runtime_dropin(self):return Path(job['original_dropin']['path'])
                def no_sidecars(self):super().no_sidecars();outer.exclusive()
            self.host=Host(job['trainer_unit'],job['fleet_unit']);self.phase='before'
            self.lineages={};self.current_checkpoint=None;self.last_retired=None;self.retirement_candidate=None;self.retired_owner=None
            self.cpu_attempts={};self.verification_failed=False;self.lease_fd=None;self.pending=None
            self.current_completed=copy.deepcopy(job['current_completed_request'])
            self.settings=base.SettingsLifecycle(job['settings_lifecycle'],job['model_dir'])
            self.historical_entry=copy.deepcopy(entry)
            self.insured=copy.deepcopy(entry['root_job']['phase_snapshot']['owner'])
            self.floor=adapter.four(entry['clocks'])
            self.original_dropin=None if job['original_dropin']['content_base64'] is None else base64.b64decode(job['original_dropin']['content_base64'])
            require(self.host._dropin_bytes()==self.original_dropin,'Owned phase override drift')
            self.host.dropin_expected=self.original_dropin;self.record=None;self.record_pin=None;self.start_request=None
            self.recovery_dropin=None;self.dropin=None;self.ending=None
    return HealthyRuntime


def archive_report(base, pin, target):
    """Byte-identical independent0444 archive; never chmod original CPU output."""
    base.pin(pin, base.MAX_JSON)
    source = Path(pin['path'])
    with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as src, target.open('xb') as dst:
        require(base.identity(os.fstat(src.fileno())) == pin['identity'], 'CPU report open race')
        dst.write(src.read(base.MAX_JSON + 1)); dst.flush(); os.fchmod(dst.fileno(), 0o444); os.fsync(dst.fileno())
        require(base.identity(os.fstat(src.fileno())) == pin['identity'], 'Original CPU report changed')
    base.fsync_directory(target.parent); base.pin(pin, base.MAX_JSON)
    archived = base.fingerprint(target, base.MAX_JSON)
    require(archived['sha256'] == pin['sha256'] and archived['bytes'] == pin['bytes']
        and (archived['identity']['device'], archived['identity']['inode']) !=
            (pin['identity']['device'], pin['identity']['inode']), 'Independent report archive differs')
    return archived

def start_repair_CE4096(runtime, adapter):
    """One new generic CE phase; this report does not claim producerCSV2048."""
    ordinary=adapter.start_record
    def recovery_record(mode,phase_id,core_sha,model_dir,checkpoint,boot_proof):
        require(mode=='return_ce' and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',phase_id or '')
            and runtime.job['before']['environment']['DQN_BATCH_SIZE']=='4096',
            'Recovery only starts CE4096')
        previous=boot_proof.get('saved_priority_metric_phase')
        require(boot_proof['status']=='PASS' and boot_proof['phase_metadata_verified'] is True
            and boot_proof['held_recipe_context']['batch_size']==4096
            and adapter.triple(checkpoint)==adapter.triple(runtime.current_checkpoint['source'])
            and boot_proof['sha256']==checkpoint['sha256'] and boot_proof['bytes']==checkpoint['bytes']
            and checkpoint['path']==str(Path(model_dir)/'robotron_dqn_latest.pt')
            and previous==runtime.recovery_saved_phase
            and previous['metric']=='ce' and previous['valid'] is True
            and previous['phase_id']!=phase_id,
            'One actual newest validCE checkpoint required for recovery phase')
        require(all(boot_proof['clocks'][key]>=runtime.floor[key] for key in adapter.CLOCKS),
            'Recovery newest clocks below actual floor')
        require(len(core_sha)==64 and all(c in '0123456789abcdef' for c in core_sha),
            'Exact immutable recovery intent SHA required')
        return dict(schema='robotron-priority-metric-start-v1',phase_id=phase_id,metric='ce',action='start',
            previous_metric='ce',checkpoint=adapter.triple(checkpoint),model_dir=model_dir,
            root_precommit_sha256=core_sha)
    try:
        adapter.start_record=recovery_record
        return runtime.start_phase()
    finally:
        adapter.start_record=ordinary

def ready_with_budget(runtime, banks, *, actors, deadline):
    remaining = deadline - time.monotonic()
    require(remaining > 0, 'Original start-based readiness deadline expired')
    runtime.job['readiness_timeout_s'] = remaining
    if not actors:
        result = runtime.ready_transport('after', banks, actors=False)
    else:
        reader, bindings = runtime.recovery_armed_logs
        original_inspect, original_configure = runtime.inspect, reader.configure_logs
        def held_inspect(phase):
            value = original_inspect(phase)
            require(runtime.host.metric_host is reader and value['bindings']['logs'] == bindings,
                'Armed runtime log reader or identities changed')
            return value
        def keep_offsets(selected):
            require(runtime.host.metric_host is reader and selected == bindings,
                'Final readiness cannot rearm another log reader')
            require(not reader.log_errors(), 'Runtime log error between CSV and final readiness')
        try:
            runtime.inspect, reader.configure_logs = held_inspect, keep_offsets
            result = runtime.ready_transport('after', banks, actors=True)
        finally:
            runtime.inspect, reader.configure_logs = original_inspect, original_configure
    require(time.monotonic() <= deadline, 'Original start-based readiness deadline expired')
    return result

def wait_current_CSV4096(runtime, base, deadline):
    """Wait only for a genuine post-start row; a mismatched NEW row is fatal."""
    start = base.read_json(runtime.start_request)
    owner = runtime.trainer_id(); previous = None; plan = None; observations = []
    while time.monotonic() < deadline:
        runtime.inspect('after')  # Exact owner/env/source/fleet/affinity each observation.
        require(runtime.trainer_id() == owner, 'CSV wait cannot adopt another owner')
        compatible_events = runtime.fault_scan()  # Existing strict classifier raises on any unapproved event.
        row = runtime.host.capture()  # Existing finite API/log checks; no offset reset here.
        csv = row['csv']; stamp = datetime.datetime.fromisoformat(csv['utc'].replace('Z', '+00:00'))
        require(stamp.tzinfo is not None, 'CSV UTC must be an authentic aware timestamp')
        current = stamp.timestamp() >= start['unix_s']
        require(stamp.timestamp() <= row['observed_unix_s'] + 2, 'CSV timestamp is in the future')
        require(csv['replay_sample_cap'] == 8 and csv['batch_size'] in (2048, 4096), 'Unexpected CSV recipe')
        if plan is None:
            keys = {kind:runtime.metrics.exposure_key(row['exposure'][kind]) for kind in ('optimizer','replay')}
            require(all(value['process_id'] == owner['pid'] for value in keys.values()), 'CSV wait API belongs to another owner')
            plan = dict(batch_size=4096, replay_cap=8, initial_snapshot=dict(csv=runtime.job['baseline_csv']), exposure_identity=keys)
        issues = runtime.metrics.api_issues(row, plan, previous)
        # Client connections may still be forming. Only an OLD row's batch is pending.
        pending = {'client_count'} | ({'CSV_recipe'} if not current else set())
        require(not [issue for issue in issues if issue not in pending], 'CSV publication guards: ' + repr(issues))
        require(not current or csv['batch_size'] == 4096, 'New producer CSV has wrong batch recipe')
        observations.append(dict(csv=dict(csv), client_count=row['client_count'], observed_unix_s=row['observed_unix_s'],
            observed_monotonic_s=row['observed_monotonic_s'], post_start_CSV=current, compatible_transition_events=compatible_events))
        if current and row['client_count'] == 192:
            require(time.monotonic() <= deadline, 'Original start-based readiness deadline expired')
            return dict(status='PASS_CURRENT_OWNER_CE4096_CSV_PUBLICATION', owner=owner, start_request=runtime.start_request,
                deadline_monotonic_s=deadline, observations=observations, CSV=csv)
        previous = row
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise RuntimeError('Current CE4096 CSV publication exceeded original readiness deadline')

def maintain(runtime,sources,base,adapter):
    result=dict(schema=RESULT_SCHEMA,status='RUNNING',qualification_pass=False,maintenance_only=True,
        ancestor_phase=copy.deepcopy(runtime.job['running_phase']),old_owner=copy.deepcopy(runtime.insured),
        limitations=['Newest graceful checkpoint plus retained mmap/bank generations; no coherent anchor claim.',
            'Only priority phase bookkeeping starts anew; newest learned weights/Adam/scaler/clocks are not rolled back.'])
    try:
        before=runtime.initial()  # Actual fresh describe/API; the entry proof is historical only.
        runtime.floor=adapter.clock_max(runtime.floor,runtime.initial_api)
        result['fresh_before_API']=copy.deepcopy(runtime.initial_api)
        raw_before=runtime.raw_api()
        require(raw_before['client_count']==192 and raw_before['training_enabled'] is True
            and raw_before['measurement_active'] is False and raw_before['managed_experiment']==runtime.job['experiment']
            and raw_before['lr']==2.5e-5 and raw_before['ts']>=runtime.initial_api['ts']
            and all(raw_before[k]>=runtime.initial_api[k] for k in adapter.CLOCKS)
            and all(runtime.metrics.exposure_key(raw_before['host_pipeline']['learning_exposure'][kind])
                ==runtime.metrics.exposure_key(runtime.initial_api['exposure'][kind]) for kind in ('optimizer','replay')),
            'Fresh before-pause raw API must retain the original owner/epochs/recipe/clocks')
        runtime.floor=adapter.clock_max(runtime.floor,raw_before)
        result['fresh_before_raw_API']=base.publish(runtime.output/'pre-ending-health.json',raw_before)
        sources.stage()
        runtime.host.begin_transition_logs(before['bindings']['logs'],before['trainer_stdout'])
        runtime.host.pause(dict(initial=runtime.job['before']))
        retired=runtime.stop_owned(before);result['retired_owner']=retired
        boot=runtime.stopped_checkpoint(retired,'newest-stopped')
        proof=base.read_json(boot['verification'])
        require(proof['status']=='PASS' and proof['phase_metadata_verified'] is True
            and proof['held_recipe_context']['batch_size']==4096
            and proof['saved_priority_metric_phase']['phase_id']==CURRENT_PHASE_ID
            and proof['saved_priority_metric_phase']['metric']=='ce' and proof['saved_priority_metric_phase']['valid'] is True,
            'Actual NEW stopped-latest strict CE9b3 state required BEFORE socket write')
        runtime.recovery_saved_phase=copy.deepcopy(proof['saved_priority_metric_phase'])
        runtime.floor=adapter.clock_max(runtime.floor,proof['clocks'])
        result['newest_stopped']=boot
        banks=runtime.banks.stopped_state(runtime.job['bank_spec']);result['stopped_banks_and_ring']=banks
        sources.reconcile('after',runtime.absence,runtime.metrics.block_restore_signals)
        result['source_transaction']=adapter.source_state(sources)
        owner=start_repair_CE4096(runtime,adapter)
        start=base.read_json(runtime.start_request);deadline=start['monotonic_s']+runtime.job['timeouts']['ready_s']
        loaded=ready_with_budget(runtime,banks,actors=False,deadline=deadline)
        raw=runtime.raw_api();adapter.zero_replay(raw,owner['pid'])
        startup=runtime.startup_snapshot(raw)
        startup['phase_CPU_readonly_archive']=archive_report(base,startup['phase_CPU'],runtime.output/'CE-startup-CPU-readonly.json')
        raw=runtime.raw_api();require(raw['client_count']==0,'Actors admitted before startup proof')
        adapter.zero_replay(raw,owner['pid']);before_resume=base.publish(runtime.output/'API-before-resume.json',raw)
        runtime.inspect('after');runtime.banks.assert_unchanged(banks,runtime.job['bank_spec'])
        current=runtime.inspect('after');runtime.host.metric_host.configure_logs(current['bindings']['logs'])
        runtime.recovery_armed_logs=(runtime.host.metric_host,copy.deepcopy(current['bindings']['logs']))
        result['initial_resume']=base.resume_all(runtime.host)
        require(not result['initial_resume']['failures'],'Original actors could not resume')
        csv_wait=wait_current_CSV4096(runtime,base,deadline)
        healthy=ready_with_budget(runtime,banks,actors=True,deadline=deadline)
        result.update(status='READY_HEALTHY_CE_MAINTENANCE',owner=owner,boot_checkpoint=boot,
            start_request=runtime.start_request,phase_record=runtime.record_pin,loaded=loaded,startup=startup,
            before_resume_API=before_resume,CSV_publication=csv_wait,healthy192=healthy,manual_recovery_required=False)
    except BaseException as error:
        result.update(status='FAILED',error=repr(error),traceback=traceback.format_exc(),manual_recovery_required=True)
        if runtime.start_request is not None:
            try:
                if runtime.host.unit(runtime.job['trainer_unit'])['MainPID']!='0':
                    require(runtime.host.known_trainer is not None,'Unknown replacement; no stop authority')
                    for actor in runtime.job['before']['bindings']['actors']:
                        if actor not in runtime.host.paused:
                            with runtime.metrics.block_restore_signals():
                                runtime.host.paused.append(actor);runtime.host.signal_actor(actor,signal.SIGSTOP)
                    runtime.host.wait_paused();result['failed_new_CE_retired']=runtime.stop_owned()
            except BaseException as cleanup:result['stop_error']=repr(cleanup)
        try:result['known_source_state']=adapter.source_state(sources)
        except BaseException as evidence:result['evidence_error']=repr(evidence)
    finally:
        result['final_resume']=base.resume_all(runtime.host)
        result['CPU_ledger']=copy.deepcopy(runtime.cpu_attempts)
        result['owned_request_at_terminal']=runtime.pending
        if result['final_resume']['failures']:result['manual_recovery_required']=True
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path);parser.add_argument('--expected-job-sha256');parser.add_argument('--expected-source-sha256')
    args=parser.parse_args(argv)
    if not args.execute:print(PLAN);return 0
    require(args.job and args.expected_job_sha256 and args.expected_source_sha256,'Explicit root job/source bindings required')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.expected_source_sha256,'Maintenance source changed')
    require(not any(n=='torch' or n.startswith(('torch.','numpy','dqn')) for n in sys.modules),'Fresh stdlib-only parent required')
    trial=load(TRIAL,TRIAL_SHA,'_healthy_ce_trial_primitives')
    metadata=load(DEADLINE,DEADLINE_SHA,'_healthy_ce_metadata')
    jp,_=metadata.pin(args.job);require(jp['sha256']==args.expected_job_sha256,'Maintenance root job changed')
    require(jp['identity']['mode']=='0o444' and jp['identity']['uid']==os.getuid() and jp['identity']['nlink']==1,'Immutable root job required')
    job=metadata.read_pin(jp)
    adapter=load(ADAPTER,ADAPTER_SHA,'_healthy_ce_adapter');base=adapter.load_v4()
    cfg,entry=validate(job,base,adapter)
    output=Path(cfg['output_directory'])
    require(output.is_absolute() and output==output.resolve(strict=False) and output.is_relative_to(GAME/'logs')
        and output.parent.is_dir() and not output.exists(),'NEW owned output required')
    output.mkdir(mode=0o700)
    roots=dict(output_directory=str(output),return_intent=dict(output_directory=str(output)))
    trial.bounded_copy_dispatch(base,roots,cfg);trial.raw_api_publication(base,metadata,roots,cfg)
    runtime=None
    try:
        runtime=runtime_class(base,adapter)(cfg,output,entry)
        source_dir=output/'source-transaction';source_dir.mkdir(mode=0o700)
        sources=base.Sources(cfg['sources'],source_dir)
        with runtime.metrics.interrupt_handlers():result=maintain(runtime,sources,base,adapter)
        result['root_job']=jp;base.publish(output/'result.json',result)
        return 0 if result['status']=='READY_HEALTHY_CE_MAINTENANCE' and not result['manual_recovery_required'] else 1
    finally:
        if runtime is not None:runtime.close()


if __name__=='__main__':raise SystemExit(main())
