"""Explicit newest-state CE4096 repair of the original failed trial02 CE4096 return.

Literal PLAN by default. No trial restart, source rollback or newest CPU rerun.
"""
import argparse
import copy
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import signal
import stat
import sys
import traceback
import time

SCHEMA = 'robotron-CE2048-trial02-failed-return-forward-CE4096-repair-job-v1'
HERE = Path(__file__).resolve().parent
TRIAL = HERE.parent/'live_one_trial_installed_ce_revision2_proposal/run_one_trial.py'
TRIAL_SHA = '1d007e6407e807575149084aff63ad0df27e677bf6f40f373d5267973893b85f'
DEADLINE = TRIAL.parent/'deadline_guard.py'
DEADLINE_SHA = '8df7491a59025e07387bdf0d392ca2b748511d7adae3cf087abf342a5acfe36a'


def require(value, message):
    if not value: raise RuntimeError(message)


def load(path, digest, name):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Pinned repair dependency changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return module


def validate(job, base, adapter):
    require(job['schema'] == SCHEMA, 'Explicit failed-return forward-repair job required')
    original = base.read_json(job['activation_job']); trial = base.read_json(job['trial_result'])
    returned = base.read_json(job['return_job']); failed = base.read_json(job['return_result'])
    startup = base.read_json(job['failed_startup_CPU_report'])
    cpu = base.read_json(job['newest_CPU_job']); proof = base.read_json(job['newest_CPU_report'])
    release = base.read_json(job['newest_CPU_release']); intent = base.read_json(job['repair_intent'])
    spec = cpu['phase_snapshot']; owner = failed['failed_requested_CE_retired']
    require(trial['status'] == 'FAILED' and trial['qualification_pass'] is False
        and trial['CE_return'] == job['return_result']
        and failed['status'] == 'FAILED' and failed['mode'] == 'return_batch4096'
        and failed['manual_recovery_required'] is True and failed['qualification_pass'] is False
        and not failed['final_resume']['failures'] and returned['mode'] == 'return_batch4096',
        'Only the original FAILED trial and failed requested CE4096 return are maintenance predecessors')
    require(startup['status'] == 'PASS' and startup['phase_metadata_verified'] is True
        and startup['root_job']['phase_snapshot']['purpose'] == 'startup'
        and startup['root_job']['phase_snapshot']['observed_clients'] == 0
        and startup['root_job']['phase_snapshot']['owner'] == owner
        and startup['held_recipe_context']['batch_size'] == 4096,
        'Actual failed-return CE4096 startup proof and exact retired owner required')
    old_phase = startup['root_job']['phase_snapshot']
    require(spec['phase_record'] == old_phase['phase_record']
        and spec['boot_checkpoint'] == old_phase['boot_checkpoint']
        and spec['expected_phase'] == old_phase['expected_phase']
        and all(spec['boot_verification'][key] == old_phase['boot_verification'][key] for key in ('sha256','bytes')),
        'Current failed-return founder/boot lineage differs; old treatment founder cannot substitute')
    require(proof['status'] == 'PASS' and proof['phase_metadata_verified'] is True
        and proof['root_job'] == cpu and proof['sha256'] == cpu['source']['sha256'] == cpu['verification_copy']['sha256']
        and proof['bytes'] == cpu['source']['bytes'] == cpu['verification_copy']['bytes']
        and spec['purpose'] == 'newest_stopped' and spec['owner'] == owner and spec['observed_clients'] == 0,
        'Actual separate newest-stopped/client0 phase CPU proof required')
    require(job['newest_CPU_report']['identity']['mode'] == '0o444'
        and job['newest_CPU_report']['identity']['nlink'] == 1
        and job['newest_CPU_report']['identity']['uid'] == os.getuid(), 'Independent readonly boot CPU archive required')
    require(release['status'] == 'PASS' and release['original_exit'] == 0
        and release['original_archived_before_release'] is True and release['unit_released'] is True
        and release['sha256'] == proof['sha256'], 'Actual newest CPU original exit/archive/release proof missing')
    require(intent['schema'] == 'robotron-CE2048-trial02-failed-return-forward-CE4096-repair-intent-v1'
        and intent['mode'] == 'return_ce' and intent['phase_id'] == job['phase_id']
        and intent['target_batch_size'] == 4096
        and intent['original_failed_trial'] == job['trial_result']
        and intent['original_failed_return'] == job['return_result'] and intent['no_trial_retry'] is True
        and intent['newest_checkpoint'] == adapter.triple(cpu['source']), 'Repair intent boot/failed predecessor differs')
    require(cpu['source']['path'] == str(Path(original['model_dir'])/'robotron_dqn_latest.pt')
        and cpu['source']['path'] != cpu['verification_copy']['path']
        and proof['saved_priority_metric_phase']['metric'] == 'ce'
        and proof['saved_priority_metric_phase']['valid'] is True
        and spec['expected_phase']['metric'] == 'ce' and spec['expected_phase']['valid'] is True,
        'Repair requires newest valid actual CE state, never candidate/insurance/protected bytes')
    require(proof['held_recipe_context']['batch_size'] == 4096
        and original['before']['environment']['DQN_BATCH_SIZE'] == '4096'
        and original['baseline_csv']['batch_size'] == 4096
        and returned['batch_boundary']['after_batch_size'] == 4096,
        'Actual4096 reconstruction/next-start and honest historical4096 startup baseline required')
    require(all(proof['clocks'][key] >= cpu['clock_floor'][key] >= startup['clocks'][key]
        for key in adapter.CLOCKS), 'Newest floor below actual failed-return startup clocks')
    require(job['startup_tag'] not in (original['startup_tag'], returned['startup_tag'])
        and job['phase_id'] != spec['expected_phase']['phase_id'],
        'NEW CE phase/startup identities required; failed return cannot be resubmitted')
    for pair in spec['sources'].values(): base.pin(pair['current'], base.MAX_SOURCE); base.pin(pair['archive'], base.MAX_SOURCE)
    base.pin(cpu['source']); base.pin(cpu['verification_copy'])
    return original, failed, cpu, proof, owner


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


def runtime_for_repair(job, base, adapter, original, cpu, proof, owner, output):
    configured = copy.deepcopy(original)
    configured.update(mode='return_ce', sources=[], output_directory=str(output), trial_core=job['repair_intent'],
        phase_id=job['phase_id'], request_id=job['request_id'], startup_tag=job['startup_tag'],
        current_completed_request=job['current_completed_request'], settings_lifecycle=job['settings_lifecycle'],
        original_dropin=job['current_dropin'], completed_dormant_capture=None, ending_proof=None)
    configured['before']['bindings']['source_hashes'].update({pair['current']['path']:pair['current']['sha256']
        for pair in cpu['phase_snapshot']['sources'].values()})
    configured['verifier']['context'] = copy.deepcopy(cpu['source_control_context'])
    spec = cpu['phase_snapshot']
    configured['running_phase'] = dict(record=spec['phase_record'], boot_checkpoint=spec['boot_checkpoint'],
        boot_verification=spec['boot_verification'], expected=spec['expected_phase'])
    # Ordinary ea4c ending requires a successful READY/horizon, which does not
    # exist. This new explicitly authorized repair validates its actual FAILED
    # predecessor + completed newest CPU above; only bypass that constructor limb.
    ordinary = adapter.validate_ending
    try:
        adapter.validate_ending = lambda selected, pinned_base: None
        runtime = adapter.runtime_class(base)(configured, output)
    finally:
        adapter.validate_ending = ordinary
    runtime.phase = 'after'; runtime.insured = copy.deepcopy(owner)
    runtime.floor = adapter.four(proof['clocks'])
    runtime.recovery_saved_phase = copy.deepcopy(proof['saved_priority_metric_phase'])
    runtime.current_checkpoint = dict(source=cpu['source'], verification=job['newest_CPU_report'], clocks=runtime.floor)
    runtime.retired_owner = runtime.retirement_candidate = copy.deepcopy(owner)
    runtime.host.trainer_cgroup = owner['cgroup']
    runtime.host.owned_fleet_cgroup = original['before']['bindings']['fleet_cgroup']
    # These are absence-only identities, not a fabricated live-process adoption.
    runtime.host.retired_trainers = [dict(pid=owner['pid'], starttime_ticks=owner['starttime_ticks'])]
    runtime.host.metric_host = runtime.metrics.Host(0, original['fleet_unit'])
    runtime.host.metric_host.configure_logs(original['before']['bindings']['logs'])
    runtime.host.begin_transition_logs(original['before']['bindings']['logs'], original['before']['trainer_stdout'])
    runtime.absence(); runtime.static()
    for actor in original['before']['bindings']['actors']:
        require(runtime.metrics.identity.identify_process(actor['pid'], 'mame') == actor
            and sorted(os.sched_getaffinity(actor['pid'])) == original['actor_masks'][str(actor['pid'])],
            'Original actor identity/mask changed')
    lease = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
    before = lease.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid(), 'Existing owned regular lease required')
    runtime.lease_fd = os.open(lease, os.O_RDONLY | os.O_NOFOLLOW)
    require(base.identity(os.fstat(runtime.lease_fd)) == base.identity(before), 'Lease open race')
    fcntl.flock(runtime.lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return runtime



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


def restore(runtime, base, adapter):
    result = dict(status='RUNNING', original_trial_failed=True, trial_retried=False, qualification_pass=False,
        recovery_target_batch_size=4096,failed_return_configured_batch_size=4096,
        CPU_scope='Strict4096 newest-state continuation after failed CE4096 return; no trial qualification')
    try:
        runtime.absence(); runtime.host.pause(dict(initial=runtime.job['before']))
        banks = runtime.banks.stopped_state(runtime.job['bank_spec'])
        for path, digest in runtime.expected_sources('after').items():
            require(base.fingerprint(path, base.MAX_SOURCE)['sha256'] == digest, 'Installed source drift')
        owner = start_repair_CE4096(runtime, adapter)  # ONE fresh4096 start, never a2048 retry
        start = base.read_json(runtime.start_request)
        deadline = start['monotonic_s'] + runtime.job['timeouts']['ready_s']
        loaded = ready_with_budget(runtime, banks, actors=False, deadline=deadline)
        raw = runtime.raw_api(); adapter.zero_replay(raw, owner['pid'])
        startup = runtime.startup_snapshot(raw)
        original_report = startup['phase_CPU']
        startup['phase_CPU_readonly_archive'] = archive_report(base, original_report, runtime.output/'CE-startup-CPU-readonly.json')
        raw = runtime.raw_api(); require(raw['client_count'] == 0, 'Actors admitted before CE proof')
        adapter.zero_replay(raw, owner['pid']); before = base.publish(runtime.output/'API-before-resume.json', raw)
        runtime.inspect('after'); runtime.banks.assert_unchanged(banks, runtime.job['bank_spec'])
        # Arm once BEFORE admission; waiting must never reset these log offsets.
        current = runtime.inspect('after')
        runtime.host.metric_host.configure_logs(current['bindings']['logs'])
        runtime.recovery_armed_logs = (runtime.host.metric_host, copy.deepcopy(current['bindings']['logs']))
        undo = base.resume_all(runtime.host); require(not undo['failures'], 'Original actors could not resume')
        csv_wait = wait_current_CSV4096(runtime, base, deadline)
        healthy = ready_with_budget(runtime, banks, actors=True, deadline=deadline)
        result.update(status='READY_CE_FORWARD_REPAIR', owner=owner, boot_checkpoint=runtime.current_checkpoint,
            start_request=runtime.start_request, phase_record=runtime.record_pin, loaded=loaded,
            startup=startup, before_resume_API=before, CSV_publication=csv_wait, healthy192=healthy, manual_recovery_required=False)
    except BaseException as error:
        result.update(status='FAILED', error=repr(error), traceback=traceback.format_exc(), manual_recovery_required=True)
        if runtime.start_request is not None:
            try:
                if runtime.host.unit(runtime.job['trainer_unit'])['MainPID'] != '0':
                    require(runtime.host.known_trainer is not None, 'Unknown replacement; no stop authority')
                    for actor in runtime.job['before']['bindings']['actors']:
                        if actor not in runtime.host.paused:
                            with runtime.metrics.block_restore_signals():
                                runtime.host.paused.append(actor); runtime.host.signal_actor(actor, signal.SIGSTOP)
                    runtime.host.wait_paused(); result['failed_CE_retired'] = runtime.stop_owned()
            except BaseException as cleanup: result['stop_error'] = repr(cleanup)
    finally:
        result['final_resume'] = base.resume_all(runtime.host)
        result['CPU_ledger'] = runtime.cpu_attempts
        if result['final_resume']['failures']: result['manual_recovery_required'] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path); parser.add_argument('--expected-job-sha256'); parser.add_argument('--expected-source-sha256')
    args = parser.parse_args(argv)
    if not args.execute: print('PLAN_ONLY: explicit newest-state CE forward repair; no reads/actions'); return 0
    require(args.job and args.expected_job_sha256 and args.expected_source_sha256, 'Explicit root bindings required')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.expected_source_sha256, 'Repair source changed')
    trial = load(TRIAL, TRIAL_SHA, '_repair_trial_helpers'); deadline = load(DEADLINE, DEADLINE_SHA, '_repair_metadata')
    jp, _ = deadline.pin(args.job); require(jp['sha256'] == args.expected_job_sha256, 'Repair job changed')
    job = deadline.read_pin(jp); adapter = trial.load(trial.ADAPTER, trial.ADAPTER_SHA, '_repair_phase_runtime'); base = adapter.load_v4()
    original, failed, cpu, proof, owner = validate(job, base, adapter)
    output = Path(job['output_directory'])
    require(output.is_absolute() and output == output.resolve(strict=False)
        and output.is_relative_to(Path(original['game_root'])/'logs') and not output.exists(), 'Repair output must be NEW owned logs')
    output.mkdir(mode=0o700)
    trial.bounded_copy_dispatch(base, dict(output_directory=str(output), return_intent=dict(output_directory=str(output))),
        dict(original, output_directory=str(output), verifier=dict(original['verifier'], context=cpu['source_control_context'])))
    trial.raw_api_publication(base, deadline, dict(output_directory=str(output), return_intent=dict(output_directory=str(output))),
        dict(output_directory=str(output)))
    runtime = None
    try:
        runtime = runtime_for_repair(job, base, adapter, original, cpu, proof, owner, output)
        with runtime.metrics.interrupt_handlers(): result = restore(runtime, base, adapter)
        result['root_job'] = jp; base.publish(output/'result.json', result)
        return 0 if result['status'] == 'READY_CE_FORWARD_REPAIR' and not result['manual_recovery_required'] else 1
    finally:
        if runtime is not None: runtime.close()


if __name__ == '__main__': raise SystemExit(main())
