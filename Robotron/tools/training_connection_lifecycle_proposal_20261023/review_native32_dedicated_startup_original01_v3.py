"""Read-only original startup diagnostic review; never a quality cohort review."""
import argparse
import ast
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def load(pin, name):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw_job = Path(args.job).read_bytes()
    assert hashlib.sha256(raw_job).hexdigest() == args.job_sha256
    review_job = json.loads(raw_job)
    assert review_job['schema'] == 'robotron-independent-dedicated-startup-diagnostic-review-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    h = load(review_job['helpers'], '_startup_root_helpers')
    reader = load(review_job['reader'], '_startup_root_reader')
    def read(pin, as_json=True):
        return reader.read_pin(pin, as_json=as_json)
    for pin in review_job['inputs']:
        h.checked(pin)
    arc = load(review_job['archive'], '_startup_root_archive')
    wire = load(review_job['startup_auditor'], '_startup_root_wire')
    reviewer = load(review_job['native_helpers'], '_startup_root_native_helpers')
    wire.dependencies()
    jp = review_job['native_job']
    job = read(jp)
    runtime = load(job['runtime'], '_startup_root_runtime')
    # Completed-output review must not call the pre-launch fresh-output validator.
    assert job['schema'] == 'robotron-native32-dedicated-observer-startup-diagnostic-v1'
    assert job['actor_slots'] == list(range(4096, 4128)) and job['startup_trace_frames'] == 1200
    assert job['origin_port'] == 19998 and job['proxy_ports'] == {str(s):20000+s-4096 for s in range(4096,4128)}
    assert job['backend'] == 'inductor' and job['device'] == 'cuda' and job['cpu_threads'] == 2
    assert job['admission_s'] == 5400 and job['whole_cohort_timeout_s'] == 9000
    assert job['checkpoint']['sha256'] == 'e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
    assert job['diagnostic_only'] is True and 'quality_leg' not in job
    assert job['wall_limit_s'] == 120
    precommit = read(job['diagnostic_precommit'])
    assert precommit['expected_native_original_exit'] == 1
    result = read(review_job['native_result'])
    cfg = read(review_job['native_config'])
    owner = read(review_job['native_owner'])
    closure = read(review_job['native_closure'])
    fields = arc.archived_closure(closure, owner, read, exit_zero=False)
    assert closure['original_exit'] == 1 and closure['payload_retried'] is False
    expected_fields = dict(Id=cfg['unit'], InvocationID=owner['invocation_id'],
        ExecMainPID=str(owner['pid']), ExecMainCode='1', ExecMainStatus='1',
        NRestarts='0', CPUQuotaPerSecUSec='12s', MemoryMax=str(16 << 30),
        MemorySwapMax='0', RuntimeMaxUSec='3min', TasksMax='512',
        TimeoutStopUSec='30s', KillMode='mixed', SendSIGKILL='no', Restart='no')
    assert all(fields[k] == v for k, v in expected_fields.items())
    assert cfg['properties'] == ['CPUQuota=1200%', 'MemoryMax=16G', 'MemorySwapMax=0',
        'RuntimeMaxSec=180', 'TasksMax=512', 'TimeoutStopSec=30', 'KillMode=mixed', 'SendSIGKILL=no']
    expected_argv = ['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-I', '-B',
        job['runtime']['path'], '--execute', '--job', jp['path'], '--job-sha256', jp['sha256'],
        '--source-sha256', job['runtime']['sha256']]
    assert cfg['argv'] == expected_argv and cfg['observation_s'] == 240
    command = '/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR=' + str(Path(cfg['output'])/'tmp') + ' ' + ' '.join(expected_argv)
    assert command + ' ; ignore_errors=no ;' in fields['ExecStart']
    for pin in cfg['pins']:
        actual = h.pin(pin['path'])
        assert all(actual[k] == pin[k] for k in ('path', 'sha256', 'bytes'))
        assert all(actual['identity'][k] == v for k, v in pin['identity'].items())
    control = load(review_job['native_controller'], '_startup_root_control')
    control.checked_config(review_job['native_config']['path'])
    absent_units = {}
    for unit in (owner['unit'], owner['timer']):
        live = control.show(unit)
        assert live['LoadState'] == 'not-found'
        absent_units[unit] = dict(Id=live['Id'], LoadState=live['LoadState'], MainPID=live.get('MainPID'))
    assert reviewer.birth(owner['pid']) != owner['starttime_ticks']
    cgroup = '/user.slice/user-1001.slice/user@1001.service/app.slice/' + owner['unit']
    assert not Path('/sys/fs/cgroup' + cgroup).exists()
    started = int(fields['ExecMainStartTimestampMonotonic']) / 1e6
    ended = int(fields['ExecMainExitTimestampMonotonic']) / 1e6
    assert 0 < started < ended <= time.monotonic() and ended-started < 180
    assert result['complete'] is False and result['diagnostic_only'] is True
    assert result['errors'][0] == "ValueError('PRECOMMITTED_DEDICATED_STARTUP_ONLY_STOP_AFTER_ALL32_PREFIXES_NOT_A_QUALITY_RESULT')"
    assert result['main_health_failure'] is None and result['main_observation_failures'] == []
    assert result['original_lease_released'] is result['immutable_inputs_unchanged'] is result['all_original_threads_stopped'] is True
    assert result['original_unsealed_journal_paths'] == []
    assert result['quality_qualified'] is result['full_game_score_verified'] is False
    assert result['before_intentional_stop'] is None and result['drain_identifier'] is None
    cohort = result['after_intentional_stop']
    assert cohort['complete'] is cohort['valid'] is False
    assert cohort['count'] == cohort['pending'] == 0 and cohort['started'] == cohort['abandoned'] == 32
    assert cohort['started_actor_slots'] == list(range(4096, 4128))
    out = Path(job['output'])
    marker = read(review_job['prefix_stop_marker'])
    assert marker['reason'] == 'PRECOMMITTED_DEDICATED_STARTUP_ONLY_STOP'
    assert marker['quality_qualified'] is False and set(marker['prefixes']) == set(result['original_slots'])
    assert started < marker['observed_monotonic_s'] < ended
    loaded_pin = h.pin(out/'original-loaded-policy.json')
    loaded = read(loaded_pin)
    policy = result['policy_before']
    assert loaded['policy'] == policy and policy['checkpoint_sha256'] == job['checkpoint']['sha256'] == precommit['checkpoint']['sha256']
    assert policy['training_enabled'] is policy['replay_enabled'] is False
    assert policy['epsilon'] == policy['expert_ratio'] == 0
    assert all(policy[k] == job['expected_policy_clocks'][k] for k in ('learner_frame_count', 'training_steps', 'optimized_samples'))
    numeric = policy['numeric_policy']
    assert numeric['compiled'] is True and numeric['backend'] == 'inductor' and numeric['device'] == 'cuda:0'
    assert numeric['weights'] == numeric['inputs'] == numeric['support'] == 'float32' and numeric['autocast'] is False
    assert numeric['warm_shapes'] == list(range(1, 17)) and numeric['max_batch_size'] == 16
    assert numeric['serving_thread_checked'] is True and numeric['graph_breaks'] == 0
    assert loaded['compile_report']['all_shapes_verified'] == list(range(1, 17))
    assert loaded['gpu_uuid'] == loaded['CUDA_VISIBLE_DEVICES'] == job['gpu_uuid'] == 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
    assert loaded['memory_is_none'] is loaded['optimizer_is_none'] is True and loaded['replay_enabled'] is False
    acquired = result['acquired_checkpoint']
    h.checked(acquired)
    assert acquired['path'] == str(out/'checkpoint.pt') and acquired['sha256'] == job['checkpoint']['sha256']
    assert (acquired['identity']['device'], acquired['identity']['inode']) != (job['checkpoint']['identity']['device'], job['checkpoint']['identity']['inode'])
    admission = read(h.pin(out/'original-fixed-admission.json'))
    payloads = {name: read(pin, False) for name, pin in result['journal'].items()}
    games = wire.games_audit
    starts = games.indexed(games.lines(payloads['measurement_starts.jsonl']), 'start')
    game_rows = games.indexed(games.lines(payloads['games.jsonl']), 'game')
    assert len(starts) == 32 and len(game_rows) == 64
    internal = dict(result, _admission=admission)
    reaped = result['original_post_origin_child_reap']
    assert reaped['all_original_children_reaped'] is True and reaped['unknown_slots'] == []
    assert reaped['signals_sent'] is reaped['exit_statuses_normalized'] is False
    prefixes = {}
    actor_logs = []
    for slot in range(4096, 4128):
        entry = result['original_slots'][str(slot)]
        private = out/'actors'/str(slot)
        actor = read(h.pin(private/'original-actor.json'))
        assert actor['argv'] == runtime.actor_command(job, private) and '-seconds_to_run' not in actor['argv']
        assert actor['original_job'] == jp and actor['boot_restore'] == entry['boot_restore']
        assert entry['pid'] == actor['pid'] == reaped['original_children'][str(slot)]['pid']
        assert entry['birth'] == actor['starttime_ticks'] == reaped['original_children'][str(slot)]['birth']
        assert entry['actual_exit'] == reaped['original_children'][str(slot)]['actual_exit'] == 0
        assert entry['outputs_sealed_after_original_writer_closure'] is True and entry['original_unsealed_output_paths'] == []
        assert marker['prefixes'][str(slot)] == entry['prefix_summary']
        assert set(entry['files']) == {'producer.jsonl','lifecycle.jsonl','proxy.jsonl','actor-stdout.txt','actor-stderr.txt','boot.lua'}
        assert all(pin['path'] == str(private/name) for name,pin in entry['files'].items())
        wire.validate_original_file_identity(actor['lifecycle_identity'], entry['files']['lifecycle.jsonl'])
        wire.validate_original_file_identity(actor['trace_identity'], entry['files']['producer.jsonl'])
        prefixes[slot] = wire.audit_startup_diagnostic_slot(slot, entry, job, internal, starts, game_rows, read, h.pin, expected_job_sha256=jp['sha256'])
        restore = read(entry['boot_restore'])
        assert restore['seed'] == job['boot_seed'] and restore['identity'] == job['boot_seed']['identity']
        assert restore['restored_paths'] == {name:str(private/name) for name in restore['files']}
        originals = {Path(e['path']).relative_to(Path(job['boot_seed']['directory'])).as_posix():e for e in job['boot_seed']['inputs'] if Path(e['path']).name != 'manifest.json'}
        assert set(restore['files']) == set(originals)
        assert all(restore['files'][name] == {key:originals[name][key] for key in ('bytes','sha256')} for name in originals)
        actor_logs.append(reviewer.audit_actor_logs(read(entry['files']['actor-stdout.txt'], False).decode(), read(entry['files']['actor-stderr.txt'], False).decode(), slot, entry['pid'], job['proxy_ports'][str(slot)]))
    for key in ('pid', 'nonce', 'client_id', 'journal_game_id', 'certificate_identifier'):
        assert len({entry[key] for entry in prefixes.values()}) == 32
    # Do not call the scientific complete-game or full-tail audit on this cutoff.
    protocol = read(job['main_health_protocol'])
    family = read(job['source_family_manifest'])
    assert protocol['prior_case'] is None and family['runtime'] == job['runtime']
    assert protocol['health_job']['binding'] == job['main_binding']
    assert len(read(job['main_binding'])['held_hashes']) == 197
    worker_reviewer = load(family['main_observer']['reviewer'], '_startup_root_worker_reviewer')
    checked = worker_reviewer.verify(job, jp, owner, cfg['argv'], result['main_observer_lifecycle'], protocol, family, [], read, h)
    assert checked['closed_report'] == result['main_health_report']
    closed = read(result['main_health_report'])
    life = read(result['main_observer_lifecycle'])
    worker_fields = arc.archived_closure(read(life['worker_closure']), read(life['worker_owner']), read, exit_zero=True)
    assert started <= int(worker_fields['ExecMainStartTimestampMonotonic'])/1e6 < int(worker_fields['ExecMainExitTimestampMonotonic'])/1e6 <= ended
    assert closed['actual_status'] == result['main_samples'] and len(closed['samples']) == len(closed['actual_status']) == 316
    assert closed['writer']['all_original_samples_persisted'] is closed['writer']['thread_stopped'] is True
    assert closed['health_job'] == protocol['health_job'] and closed['held197_final_verified'] is True
    engine = load(protocol['health_job']['sources']['full_health_engine'], '_startup_root_health_engine')
    raw = engine.replay(protocol['health_job'], closed['samples'], read(closed['initial_cursors']), read, h, prior_groups=[], original_statuses=closed['actual_status'])
    assert raw['transport'] == closed['transport'] and raw['deep_samples'] == closed['deep_samples'] == 13
    assert started <= result['native_started_monotonic_s'] <= closed['guard_started_monotonic_s'] <= raw['first_deep_monotonic_s'] <= raw['last_deep_monotonic_s'] <= closed['guard_ended_monotonic_s'] <= ended
    assert result['native_deadline_monotonic_s'] == result['native_started_monotonic_s'] + 120
    assert marker['observed_monotonic_s'] < closed['guard_ended_monotonic_s'] <= result['native_deadline_monotonic_s']
    assert raw['first_deep_monotonic_s']-started <= 30 and ended-raw['last_deep_monotonic_s'] <= 30
    assert raw['final_learner_frames'] > raw['first_learner_frames'] and raw['final_training_steps'] > raw['first_training_steps']
    initial = reviewer.validate_initial_readiness(read(result['initial_main_readiness']), result['initial_main_readiness'], job, jp, raw, loaded_pin, admission, started, ended)
    h.checked(job['lease'])
    fd = os.open(job['lease']['path'], os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    for port in [19998, *range(20000, 20032)]:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    gpu = subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'], check=True, capture_output=True, text=True, timeout=10)
    assert job['gpu_uuid'] not in gpu.stdout
    assert 'torch' not in sys.modules
    output = Path(review_job['output'])
    output.mkdir(mode=0o700)
    report = h.put(output/'report.json', dict(schema='robotron-independent-native32-dedicated-startup-diagnostic-review-result-v1',
        status='ALL32_STARTUP_AND_DEDICATED_OBSERVER_INTEGRATION_VERIFIED_NO_QUALITY_RESULT',
        native_job=jp, native_result=review_job['native_result'], native_scope_closure=review_job['native_closure'],
        expected_native_original_exit=1, native_actual_interval=[started,ended], post_release_units=absent_units,
        all_actual_native_archives_resources_argv_pins_release_and_birth_absence_verified=True,
        original_errors_retained=result['errors'], all32_original_prefixes=prefixes, actor_logs=actor_logs,
        protected_policy_loaded=policy, original_incomplete_games=32, original_completed_quality_games=0,
        worker_independent_scope_review=checked, original_raw_replay=raw, original_initial_readiness=initial,
        private_lease_unchanged_and_free=True, all33_private_ports_free=True, private_GPU_empty=True,
        actual_native_MAME_startup_integration=True, scientific_case=False, full_game_validation_performed=False,
        quality_qualified=False, playing_gain_verified=False, learning_speed_gain_verified=False,
        production_runtime_changed=False, created_unix_s=time.time()))
    print(json.dumps(dict(report=report, prefixes=len(prefixes), raw_samples=raw['samples'], deep_samples=raw['deep_samples'], quality_qualified=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
