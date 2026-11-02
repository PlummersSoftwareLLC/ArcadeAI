"""Read and close the original invalid extra-client attempt; never reschedule."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
N = R / 'quality32-protected1741-vs-currentLR125-firstSave-original01-preparation-20261023'
D = N / 'closed-invalid-extra-remote-slot0-independent-root-original01'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    h = load('_closed_helpers', G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    reader = load('_closed_reader', G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    rt = load('_closed_archive', G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py')
    ctl = load('_closed_ctl', G/'tools/quality_capacity_proposal/control_quality32_review_v1.py')
    base = load('_closed_birth', G/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py')
    window = load('_closed_window', G/'tools/lr125_survival_trial_proposal_20261023/window_observer.py')
    read = lambda entry, as_json=True: reader.read_pin(entry, as_json=as_json)
    leg = N/'01-reference'; output = leg/'diagnostic-output-original01'
    native_pin = h.pin(output/'result.json'); native = read(native_pin)
    assert native['status'] == 'ORIGINAL_COMPILED_QUALITY32_INVALID_NO_RETRY'
    assert native['original_attempt'] == 1 and native['no_retry'] is True and native['complete'] is False
    scopes = []
    specs = [(leg/'execution-original01', leg/'controller-config.json', 1, False),
             (N/'winner-protection-currentLR125-future-original01/guards-CPU-execution-original01',
              N/'winner-protection-currentLR125-future-original01/guards-controller-config.json', 0, True)]
    for directory, config_path, code, cpu in specs:
        cp = h.pin(config_path); config = read(cp)
        op = h.pin(directory/'root-original-identity.json'); owner = read(op)
        clp = h.pin(directory/'root-original-result-and-owned-release.json'); closure = read(clp)
        assert closure['original_exit'] == code
        fields = rt.archived_closure(closure, owner, read, exit_zero=cpu)
        assert fields['Id'] == config['unit'] and fields['NRestarts'] == '0'
        assert ' '.join(config['argv'])+' ; ignore_errors=no ;' in fields['ExecStart']
        assert rt.duration_seconds(fields['CPUQuotaPerSecUSec']) == (2 if cpu else 12)
        assert fields['MemoryMax'] == str((4 if cpu else 16)<<30) and fields['MemorySwapMax'] == '0'
        assert rt.duration_seconds(fields['RuntimeMaxUSec']) == (180 if cpu else 9660)
        assert fields['TasksMax'] == ('128' if cpu else '512')
        assert fields['Restart'] == fields['SendSIGKILL'] == 'no'
        assert rt.duration_seconds(fields['TimeoutStopUSec']) == (5 if cpu else 30)
        assert base.birth(owner['pid']) != owner['starttime_ticks']
        for unit in (owner['unit'], owner['timer']):
            assert ctl.show(unit)['LoadState'] == 'not-found'
            assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', unit).exists()
        for entry in config['pins']:
            assert ctl.pin(entry['path']) == entry
        scopes.append(dict(config=cp, owner=op, closure=clp, actual_fields=fields, original_exit=code,
                           all_six_descriptors_verified=True, owned_process_units_cgroups_absent=True))
    root_result = read(h.pin(leg/'controller-original-result.json'))
    assert root_result['actual_exit'] == 1 and root_result['live_registration_errors'] == []
    assert native['all_original_threads_stopped'] is native['original_lease_released'] is native['immutable_inputs_unchanged'] is True
    reap = native['original_post_origin_child_reap']
    assert reap['all_original_children_reaped'] is True and len(reap['original_children']) == 32
    assert reap['signals_sent'] is reap['exit_statuses_normalized'] is False
    for row in reap['original_children'].values():
        assert row['actual_exit'] == 0 and base.birth(row['pid']) != row['birth']
    assert all(not (N/name).exists() for name in ('02-candidate', '03-reference', '04-candidate'))
    outcome_pin = h.pin(N/'original-fresh-sequence-observer-original01-outcome.json'); outcome = read(outcome_pin)
    assert outcome['status'] == 'ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY' and outcome['original_records'] == []
    for filename in ('original-fresh-sequence-observer-original01-intent.json', 'display-observer-original-intent.json'):
        intent = read(h.pin(N/filename)); assert base.birth(intent['pid']) != intent['birth']
    failure_pin = native['main_observation_failures'][0]; failure = read(failure_pin)
    failed = failure['original_observation']; failed_api = read(failed['raw_API']); census = read(failed['snapshot'])
    assert failure['accepted'] is False and failed_api['client_count'] == 193 and len(census['actors']) == 192
    duplicates = [row for row in failed_api['client_rows'] if row['client_slot'] == 0]
    assert {row['client_id'] for row in duplicates} == {41, 142}
    prep = read(h.pin(N/'fresh-study-launch-preparation-original01/readback.json'))
    binding = read(prep['binding']); window.owner_and_files(binding)
    lease = read(h.pin(output/'original-lease.json'))['coordinator']; h.checked(lease)
    fd = os.open(lease['path'], os.O_RDWR|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB); fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    sockets = []
    try:
        for port in (19998, *range(20000, 20032)):
            sock = socket.socket(); sockets.append(sock); sock.bind(('127.0.0.1', port))
    finally:
        for sock in sockets: sock.close()
    gpu = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_memory', '--format=csv,noheader'], capture_output=True, text=True, timeout=10)
    assert gpu.returncode == 0 and 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0' not in gpu.stdout
    assert native['before_intentional_stop'] is None
    at_exit = native['controller_exit']['cohort']; after = native['after_intentional_stop']
    assert at_exit['count'] == after['count'] == 0 and at_exit['started'] == after['started'] == 32
    assert at_exit['pending'] == 32 and after['abandoned'] == 32 and after['pending'] == 0
    future = read(h.pin(N/'winner-protection-currentLR125-future-original01/precommit.json'))
    for suffix in ('.pt', '.pt.json'):
        assert not (Path(future['destination'])/(future['label']+suffix)).exists()
    stderr = N/'winner-protection-currentLR125-future-original01/guards-CPU-execution-original01/stderr.txt'
    assert 'Ran 6 tests' in stderr.read_text() and stderr.read_text().rstrip().endswith('OK')
    refusal = h.put(D/'first-root-closeout-null-before-stop-refusal.json', dict(
        error="TypeError: 'NoneType' object is not subscriptable at original inline closeout line46",
        cause='Invalid runtime has no before_intentional_stop; original controller_exit and after_intentional_stop are separate preserved partial/abandoned cohorts.',
        original_runtime_retried=False, root_readback_published=False, created_unix_s=time.time()))
    proof = h.put(D/'readback.json', dict(schema='robotron-closed-invalid-quality-extra-remote-client-readback-v1',
        status='ORIGINAL_FRESH_R1_CLOSED_INVALID_EXTRA_DUPLICATE_SLOT0_NO_RETRY', original_runtime=native_pin,
        original_sequence_outcome=outcome_pin, scopes=scopes, actual_original_descriptors_verified=12,
        all32_original_MAME_exits_zero_and_absent=True, all_original_threads_stopped=True,
        permanent_GPU0_lease_unchanged_unheld=True, all33_private_ports_available=True,
        private_GPU0_compute_apps_absent=True, original_failed_health_observation=failure_pin,
        failed_raw_API=failed['raw_API'], failed_census=failed['snapshot'], failed_owned_actor_census=192,
        failed_API_connections=193, failed_duplicate_slot0=duplicates, extra_remote_peer='192.168.1.13',
        extra_remote_slot=0, extra_remote_client_id=142,
        current_socket_peers=h.pin(D/'current-training-socket-peers.txt'),
        current_API_at_first_closeout=h.pin(D/'current-main-API.raw.json'),
        original192_births_affinities_and_all197_hashes_unchanged_at_close=True,
        completed_games=0, pending_at_controller_exit=32, abandoned_after_shutdown=32,
        valid_before_intentional_stop_exists=False, unlaunched_legs=['C1','R2','C2'],
        frozen_candidate_retried=False, scores_reused=False, policy_qualification=False, promotion=False,
        future_protection_guards_passed=6, future_protection_permitted_for_this_invalid_case=False,
        remote_client_signaled_or_disconnected=False, prior_root_closeout_refusal=refusal,
        created_unix_s=time.time()))
    print(json.dumps(dict(closed=proof, native_exit=1, protection_guards_exit=0, original_MAME_exits_zero=32,
                          descriptors_verified=12, completed_games=0, abandoned_after_shutdown=32)))


if __name__ == '__main__':
    main()
