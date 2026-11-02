"""Activate the selected hot LR change once, then exec its original controller.

No automatic rollback: failures after the control CAS preserve the changed state
for inspection. This keeps the newest learner, optimizer, replay and actors.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

G = Path(__file__).resolve().parents[2]
R = G / 'logs/managed-learning-20261015/run-26'
P = Path(__file__).resolve().parent
D = R / 'LR125-survival32M-original01-preparation-20261023'


def load(name, path, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha, path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    assert sys.argv[1:] == ['--execute-selected-once',
        '29774518a61133985742b3ebf7af2823986e6d7eb4e5e71ccb3af4519c2df675']
    h = load('_lr125_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader = load('_lr125_reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    read = lambda pin, as_json=True: reader.read_pin(pin, as_json=as_json)
    rt = load('_lr125_archives', G / 'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
        '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445')
    ctl = load('_lr125_ctl', P / 'window_controller.py',
        'd6d02c7f9c8e17a925e5a1f766956b4e5ab0342d95c46f0b6bbd585f57cb5c55')
    guard = load('_lr125_guard', P / 'window_observer.py',
        'ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a')
    counters_path = G / 'tools/live_lr_recipe_continuation_proposal/observer.py'
    counters = load('_lr125_counters', counters_path,
        '11380275b544eb7196d33d92b1fbe28a1ae057404120419a2cfa447410c7e430')
    selected_pin = h.pin(D / 'treatment-selection-precommit.json')
    assert selected_pin['sha256'] == sys.argv[2]
    selected = read(selected_pin)
    for pin in selected['sources'].values():
        assert h.pin(pin['path']) == pin
    for pin in selected['evidence'].values():
        read(pin)
    read(selected['future_quality']['reference_policy'], False)
    cpu_out = D / 'CPU-contracts-execution-original01'
    closure_pin = h.pin(cpu_out / 'root-original-result-and-owned-release.json')
    closure = read(closure_pin)
    fields = rt.archived_closure(closure, closure['original'], read, exit_zero=True)
    assert fields['CPUQuotaPerSecUSec'] == '2s' and fields['MemoryMax'] == '4294967296'
    assert fields['MemorySwapMax'] == '0' and fields['RuntimeMaxUSec'] == '3min'
    assert fields['TasksMax'] == '128' and fields['SendSIGKILL'] == 'no'
    assert fields['TimeoutStopUSec'] == '5s' and fields['Restart'] == 'no'
    for unit in (closure['original']['unit'], closure['original']['timer']):
        assert ctl.show(unit)['LoadState'] == 'not-found'
        assert not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', unit).exists()
    assert guard.process_start(closure['original']['pid']) != closure['original']['starttime_ticks']
    stderr = (cpu_out / 'stderr.txt').read_text()
    assert 'Ran 7 tests' in stderr and stderr.rstrip().endswith('OK')
    config = read(h.pin(D / 'CPU-contracts-controller-config-original01.json'))
    for pin in config['pins']:
        assert ctl.pin(pin['path']) == pin
    assert ' '.join(config['argv']) + ' ; ignore_errors=no ;' in fields['ExecStart']
    goal = json.loads((R.parent / 'state.json').read_bytes())['optimization_goal']
    assert goal['status'] == 'active' and goal['source_freeze'] is False and goal['full_source_freeze'] is False
    monitor = R / 'dashboard-JSON-production-continuity-live-controller-original01-preparation-20261022/completed-registration/root-current-main-readonly-monitor.py'
    before_health = json.loads(subprocess.check_output(['/usr/bin/python3.12', '-I', '-B', str(monitor)]))
    assert before_health['owner'] == selected['current_owner']
    binding = read(selected['current_binding'])
    control_path = G / 'models_dqn/learning_control.json'
    assert h.pin(control_path) == selected['before_control']
    before_raw = control_path.read_bytes()
    assert before_raw == read(selected['before_control_archive'], False)
    control = json.loads(before_raw)
    assert control['lr_scale'] == .25 and not control.get('measurement')
    after = dict(control, **selected['control_delta'])
    assert {k for k in after if after[k] != control[k]} == {'experiment', 'lr_scale'}
    out = D / 'activation-original01'
    assert not out.exists() and not (D / 'window-execution-original01').exists()
    assert ctl.show('robotron-LR125-survival32M-window-original01-20261023.service')['LoadState'] == 'not-found'
    assert ctl.show('robotron-LR125-survival32M-window-original01-20261023.timer')['LoadState'] == 'not-found'
    out.mkdir(mode=0o700)
    h.put(out / 'preflight.json', dict(selection=selected_pin, CPU_contract_closure=closure_pin,
        source=h.pin(Path(__file__).resolve()), main_health=before_health,
        current_binding=selected['current_binding'], control_before=selected['before_control'],
        actual_all_six_CPU_archives_and_resources_verified=True, all197_inputs_and_original192_actors_verified=True))
    with (out / 'canonical-state-before.raw.json').open('xb') as stream:
        stream.write((R.parent / 'state.json').read_bytes())
        stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    changed = False
    try:
        encoded = (json.dumps(after, indent=2, allow_nan=False) + '\n').encode()
        temporary = control_path.with_name('learning_control.lr125-original01.tmp')
        with temporary.open('xb') as stream:
            stream.write(encoded); stream.flush(); os.fchmod(stream.fileno(), 0o664); os.fsync(stream.fileno())
        guard.owner_and_files(binding)
        assert h.pin(control_path) == selected['before_control'] and control_path.read_bytes() == before_raw
        os.replace(temporary, control_path)
        changed = True
        fd = os.open(control_path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        after_pin = h.pin(control_path)
        assert control_path.read_bytes() == encoded
        transaction = h.put(out / 'control-transaction.json', dict(selection=selected_pin,
            before=selected['before_control'], before_archive=selected['before_control_archive'],
            after=after_pin, after_value=after, only_label_and_lr_scale_changed=True,
            main_or_actor_restart=False, optimizer_or_replay_reset=False, created_unix_s=time.time()))
        new_binding = dict(binding, schema='robotron-current-main-LR125-post-hot-control-binding-v1',
            experiment=after['experiment'], prior_binding=selected['current_binding'],
            held_hashes=dict(binding['held_hashes'], **{str(control_path): after_pin['sha256']}))
        # Supersede old supervision projection explicitly; later isolated quality
        # must prepare its own fresh current-recipe supervision policy.
        new_binding['historical_supervision_policy_not_selected'] = binding['supervision_policy']
        new_binding.pop('supervision_policy')
        deadline = time.monotonic() + 60
        first_target = None
        baseline = None
        while time.monotonic() < deadline:
            guard.owner_and_files(new_binding)
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
                raw = response.read(2 << 20)
            api = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            if api['managed_experiment'] == after['experiment'] and api['lr'] == 6.25e-6:
                guard.healthy(api, read(binding['baseline_API']), after['experiment'], time.time())
                current = counters.normalise(api)
                if first_target is None:
                    first_target = time.monotonic()
                    first_identity = (current['optimizer_identity'], current['replay_identity'])
                assert (current['optimizer_identity'], current['replay_identity']) == first_identity
                if time.monotonic() - first_target >= 10 and current['unclassified'] == 0:
                    baseline = (raw, api, time.monotonic())
                    break
            time.sleep(.25)
        assert baseline is not None, 'No mature post-refresh pending0 baseline; do not reverse control automatically'
        raw, api, monotonic = baseline
        baseline_pin = guard.publish(out / 'post-control-baseline-API.raw.json', raw)
        new_binding['baseline_API'] = baseline_pin
        assert len(new_binding['held_hashes']) == 197
        binding_pin = h.put(out / 'current-main-binding.json', new_binding)
        job = dict(new_binding, authorized=True, counter_module=guard.pin(counters_path),
            baseline_monotonic_s=monotonic, cutoff_s=14400,
            output=str(D / 'window-output-original01'), tag='LR125_survival32M_original01_20261023',
            treatment_selection=selected_pin, control_transaction=transaction,
            horizon_learner_frames=32000000, horizon_accepted_DQN_epsilon=32000000)
        job_pin = h.put(out / 'window-job.json', job)
        argv = ['/usr/bin/python3.12', '-I', '-B', str(P / 'window_observer.py'),
                '--execute', '--job', job_pin['path'], '--job-sha256', job_pin['sha256']]
        window_config = dict(unit='robotron-LR125-survival32M-window-original01-20261023.service',
            output=str(D / 'window-execution-original01'), argv=argv,
            properties=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0',
                        'RuntimeMaxSec=14520', 'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'],
            observation_s=14580, pins=[ctl.pin(path) for path in
                (P / 'window_controller.py', P / 'window_observer.py', job_pin['path'],
                 counters_path, control_path)])
        config_pin = h.put(out / 'window-controller-config.json', window_config)
        ctl.checked_config(config_pin['path'])
        h.put(out / 'activation-readback.json', dict(status='CONTROL_APPLIED_POST_REFRESH_BASELINE_READY_WINDOW_NOT_YET_LAUNCHED',
            control_transaction=transaction, current_main_binding=binding_pin, baseline_API=baseline_pin,
            baseline_monotonic_s=monotonic, job=job_pin, controller_config=config_pin,
            same_owner=selected['current_owner'], source197_and_original192_actors_verified=True,
            actual_live_lr=api['lr'], actual_experiment=api['managed_experiment'],
            actual_window_started=False, quality_campaign_started=False, promotion=False,
            learner_frame_count=api['learner_frame_count'], created_unix_s=time.time()))
        command = ['/usr/bin/python3.12', '-I', '-B', str(P / 'window_controller.py'),
                   '--execute', '--config', config_pin['path'], '--expected-source-sha256',
                   'd6d02c7f9c8e17a925e5a1f766956b4e5ab0342d95c46f0b6bbd585f57cb5c55']
        print(json.dumps(dict(activation='APPLIED_VERIFIED_STARTING_ORIGINAL_WINDOW_CONTROLLER',
            binding=binding_pin, job=job_pin, controller_config=config_pin)), flush=True)
        os.execv(command[0], command)
    except BaseException as error:
        h.put(out / 'activation-failure.json', dict(status='FAILED_PRESERVED_DO_NOT_RETRY_OR_IMPLICITLY_REVERSE',
            error=repr(error), control_CAS_applied=changed, original_control=selected['before_control'],
            actual_control=h.pin(control_path), trainer_restarted=False, created_unix_s=time.time()))
        raise


if __name__ == '__main__':
    main()
