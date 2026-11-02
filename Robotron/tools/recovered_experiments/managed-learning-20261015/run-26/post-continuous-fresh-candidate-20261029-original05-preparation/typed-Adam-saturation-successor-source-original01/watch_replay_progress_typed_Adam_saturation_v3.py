"""Select one future checkpoint using precommitted replay/update/time exposure.

This observational selection never changes training or completes an older window.
The saved policy still requires a separately valid frozen-policy comparison.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import traceback


def load(path):
    spec = importlib.util.spec_from_file_location('_original_exposure_observer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def additions(sample, anchor, elapsed_s):
    exposure = lambda value: value['host_pipeline']['learning_exposure']
    current, initial = exposure(sample), exposure(anchor)
    result = dict(applied_updates=current['optimizer']['total']['applied']-initial['optimizer']['total']['applied'],
        replay_inserts=current['replay']['accepted_total']-initial['replay']['accepted_total'],
        elapsed_s=elapsed_s,
        by_source={key: value-initial['replay']['accepted_by_source_total'][key]
                   for key, value in current['replay']['accepted_by_source_total'].items()})
    assert all(value >= 0 for key, value in result.items() if key != 'by_source')
    assert all(value >= 0 for value in result['by_source'].values())
    assert sum(result['by_source'].values()) == result['replay_inserts']
    return result


def ready(added, thresholds):
    return all(added[key] >= thresholds[key] for key in ('applied_updates', 'replay_inserts', 'elapsed_s'))


def show(unit):
    raw = subprocess.check_output(['systemctl', '--user', 'show', unit], text=True, timeout=5)
    return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)


def verify_CPU(plan, directory, endpoint, observer):
    unit = plan['CPU_unit']
    assert show(unit)['LoadState'] == 'not-found', 'Original CPU unit already exists; no adoption/retry'
    command = ['systemd-run', '--user', '--unit='+unit, '-p', 'CPUQuota=200%', '-p', 'MemoryMax=4G',
        '-p', 'MemorySwapMax=0', '-p', 'TasksMax=128', '-p', 'RuntimeMaxSec=180', '-p', 'Restart=no',
        '-p', 'RemainAfterExit=yes', 'env', 'CUDA_VISIBLE_DEVICES=', 'DQN_BATCH_SIZE=4096',
        'DQN_N_STEP=3', 'DQN_MAX_SAMPLES_PER_FRAME=8', plan['python'], '-Xgil=0', '-I', '-B',
        plan['verifier'], '--checkpoint', endpoint['path'], '--report', str(directory/'endpoint-CPU.json')]
    launched = subprocess.run(command, capture_output=True, text=True, timeout=10)
    observer.publish(directory/'CPU-original-launch.json', dict(argv=command, exit=launched.returncode,
        stdout=launched.stdout, stderr=launched.stderr), exclusive=True)
    assert launched.returncode == 0, 'Original CPU launch failed'
    original = show(unit)
    assert original['MainPID'] != '0', 'Original CPU identity unavailable'
    pid = int(original['MainPID'])
    birth = int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    expected = dict(CPUQuotaPerSecUSec='2s', MemoryMax=str(4 << 30), MemorySwapMax='0',
                    TasksMax='128', RuntimeMaxUSec='3min', Restart='no', NRestarts='0')
    assert all(original[key] == value for key, value in expected.items()), 'Original CPU resources differ'
    observer.publish(directory/'CPU-original-owner.json', dict(unit=unit, pid=pid, birth=birth,
        invocation_id=original['InvocationID'], actual_properties=original), exclusive=True)
    deadline = time.monotonic()+210
    while True:
        actual = show(unit)
        assert actual['InvocationID'] == original['InvocationID'] and actual['NRestarts'] == '0'
        if actual['MainPID'] == '0':
            break
        assert actual['MainPID'] == str(pid) and time.monotonic() < deadline, 'Original CPU completion unknown'
        assert int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]) == birth
        time.sleep(.5)
    observer.publish(directory/'CPU-original-terminal.json', actual, exclusive=True)
    assert all(actual[key] == value for key, value in expected.items())
    assert actual['ExecMainPID'] == str(pid) and actual['ExecMainCode'] == '1' and actual['ExecMainStatus'] == '0'
    assert not Path('/proc', str(pid)).exists(), 'Original CPU birth still present'
    verification = observer.read(directory/'endpoint-CPU.json')
    assert verification['checkpoint'] == endpoint and verification['CUDA_initialized'] is False
    stopped = subprocess.run(['systemctl', '--user', 'stop', unit], capture_output=True, text=True, timeout=10)
    assert stopped.returncode == 0
    released = show(unit)
    assert released['MainPID'] == '0' and released['ActiveState'] == 'inactive'
    assert not Path('/sys/fs/cgroup'+original['ControlGroup']).exists()
    observer.publish(directory/'CPU-owned-release.json', dict(unit=unit, original=original,
        terminal=actual, after_release=released, original_birth_absent=True), exclusive=True)
    return verification



def selected_entry_amendment(plan, observer, directory):
    """Adopt the SAME passed entry before any anchor; no old exposure is credited."""
    def read_pin(pin):
        observer.check_pin(pin)
        return observer.read(pin['path'])
    assert plan['prior_unstarted_plan']['path'] == str(directory/'window-plan.json')
    amendment = read_pin(plan['capture_source_amendment'])
    assert amendment['schema'] == 'robotron-root-original05-typed-Adam-entry-source-amendment-v1'
    assert amendment['status'] == 'ROOT_SELECTED_NEW_SOURCES_SAME_PASSED_ENTRY_BEFORE_OWN_ANCHOR'
    assert amendment['prior_unstarted_plan'] == plan['prior_unstarted_plan']
    prior = read_pin(plan['prior_unstarted_plan'])
    allowed = {'verifier', 'inputs', 'prior_unstarted_plan', 'capture_source_amendment',
               'entry_verification', 'entry_typed_authority'}
    assert {k:v for k,v in plan.items() if k not in allowed} == {k:v for k,v in prior.items() if k not in allowed}
    assert all(k not in prior for k in ('prior_unstarted_plan','capture_source_amendment','entry_typed_authority'))
    assert amendment['root_selection'] == prior['root_selection'] == plan['root_selection']
    assert amendment['old_plan_or_entry_modified'] is False and amendment['old_window_counts_reused'] is False
    family = read_pin(amendment['source_family'])
    assert family['schema'] == 'robotron-original05-typed-Adam-saturation-source-family-v1'
    assert family['status'] == 'SOURCE_ONLY_UNSELECTED_NOT_EXECUTED'
    selected = amendment['selected_sources']
    assert selected == family['selected_sources']
    assert selected['watcher'] == observer.pin(Path(__file__))
    assert selected['verifier']['path'] == plan['verifier'] and selected['library'] == plan['observer_library']
    for pin in selected.values(): observer.check_pin(pin)
    added = amendment['new_evidence_inputs']
    assert all(pin in added or pin in prior['inputs'] for pin in
               [*selected.values(), amendment['source_family'], plan['prior_unstarted_plan'], plan['entry_typed_authority']])
    expected = {pin['path']:pin for pin in prior['inputs']}
    for pin in [*added, plan['capture_source_amendment']]:
        assert pin['path'] not in expected or expected[pin['path']] == pin
        expected[pin['path']] = pin
    assert plan['inputs'] == list(expected.values())
    assert amendment['preserved_original_entry_authority']['path'] == str(directory/'entry-CPU-authority.json')
    original = read_pin(amendment['preserved_original_entry_authority'])
    assert original['Root_selection'] == plan['root_selection']
    old_cpu = read_pin(original['actual_CPU_verification'])
    assert prior['entry_verification'] == original['actual_CPU_verification']
    authority = read_pin(plan['entry_typed_authority'])
    assert authority['schema'] == 'robotron-root-same-original05-entry-typed-Adam-CPU-authority-v1'
    assert authority['status'] == 'SAME_IMMUTABLE_ENTRY_CPU_VERIFIED_AND_ORIGINAL_TYPED_SCOPE_CLOSED'
    assert authority['preserved_original_entry_authority'] == amendment['preserved_original_entry_authority']
    assert authority['checkpoint'] == original['endpoint'] and authority['verifier'] == selected['verifier']
    assert type(authority['original_exit']) is int and authority['original_exit'] == 0 and authority['original_scope_released'] is True
    receipt_keys = ('actual_CPU_verification','original_CPU_owner','original_CPU_terminal','original_CPU_release')
    assert all(authority[k] in added for k in receipt_keys)
    for key in receipt_keys: observer.check_pin(authority[key])
    owner = read_pin(authority['original_CPU_owner']); live = owner['actual_properties']
    terminal = read_pin(authority['original_CPU_terminal']); release = read_pin(authority['original_CPU_release'])
    assert type(owner['pid']) is int and owner['pid'] > 1 and type(owner['birth']) is int and owner['birth'] > 0
    assert owner['unit'] == live['Id'] == terminal['Id'] == release['unit']
    assert live['MainPID'] == str(owner['pid']) and terminal['ExecMainPID'] == str(owner['pid'])
    assert owner['invocation_id'] == live['InvocationID'] == terminal['InvocationID']
    assert terminal['MainPID'] == '0' and terminal['ExecMainCode'] == '1' and terminal['ExecMainStatus'] == '0'
    resources = dict(Type='simple', Restart='no', NRestarts='0', CPUQuotaPerSecUSec='2s',
        MemoryMax=str(4 << 30), MemorySwapMax='0', TasksMax='128', RuntimeMaxUSec='3min')
    assert all(live[key] == terminal[key] == value for key,value in resources.items())
    assert release['original'] == live and release['terminal'] == terminal and release['original_birth_absent'] is True
    assert bool(live['ControlGroup']) and release['after_release']['MainPID'] == '0' and release['after_release']['ActiveState'] == 'inactive'
    typed = read_pin(authority['actual_CPU_verification'])
    assert authority['actual_CPU_verification'] == plan['entry_verification']
    assert typed['checkpoint'] == old_cpu['checkpoint'] == original['endpoint']
    assert typed['clocks'] == old_cpu['clocks'] and typed['Adam_step_min'] == old_cpu['Adam_step_min'] == plan['entry_Adam_step']
    assert typed['Adam_step_max'] == old_cpu['Adam_step_max'] and typed['Adam_parameters'] == old_cpu['Adam_parameters'] == 81
    assert typed['CUDA_initialized'] is False and typed['verification_source'] == selected['verifier']
    assert typed['online_target_shapes_and_finiteness_verified'] is True and typed['priority_phase_valid'] is True
    assert not (directory/'anchor.raw.json').exists()
    return typed


def endpoint_progress_proof(verification, entry, plan, anchor, threshold, added, observer):
    """Applied telemetry proves dose; float32 Adam steps may cease growing at2**24."""
    assert ready(added, plan['thresholds'])
    a = observer.exposure(anchor); t = observer.exposure(threshold)
    for kind in ('optimizer','replay'):
        assert all(a[kind][key] == t[kind][key] == plan['expected_exposure_lineage'][kind][key]
                   for key in observer.FIELDS)
    applied = t['optimizer']['total']['applied'] - a['optimizer']['total']['applied']
    replay = t['replay']['accepted_total'] - a['replay']['accepted_total']
    assert applied >= plan['thresholds']['applied_updates'] and replay >= plan['thresholds']['replay_inserts']
    assert t['optimizer']['total']['unavailable'] == a['optimizer']['total']['unavailable'] == 0
    assert all(type(row[key]) is int and row[key] >= 0 for row in
               (verification['clocks'],entry['clocks'],anchor,threshold) for key in observer.CLOCKS)
    assert all(verification['clocks'][key] >= threshold[key] and verification['clocks'][key] >= entry['clocks'][key]
               for key in observer.CLOCKS)
    assert verification['clocks']['training_steps'] > entry['clocks']['training_steps']
    assert verification['clocks']['optimized_samples'] > entry['clocks']['optimized_samples']
    assert verification['clocks']['training_steps'] - anchor['training_steps'] >= applied
    assert verification['clocks']['optimized_samples'] - anchor['optimized_samples'] >= 4096 * applied
    assert verification['verification_source']['path'] == plan['verifier']
    assert verification['verification_source'] == entry['verification_source']
    assert verification['Adam_parameters'] == entry['Adam_parameters'] == 81
    raw = verification['Adam_raw_step_proof']; start = entry['Adam_raw_step_proof']
    assert raw['schema'] == start['schema'] == 'robotron-raw-checkpoint-Adam-scalar-step-proof-v1'
    assert raw['all_steps_finite'] is start['all_steps_finite'] is True
    assert raw['parameter_group_flags'] == start['parameter_group_flags']
    assert raw['inspected_before_optimizer_load_state_dict'] is start['inspected_before_optimizer_load_state_dict'] is True
    assert verification['online_target_shapes_and_finiteness_verified'] is True
    if verification['Adam_step_min'] > plan['entry_Adam_step']:
        kind = 'ORDINARY_STRICT_Adam_STEP_ADVANCE'
    else:
        assert verification['Adam_step_min'] == verification['Adam_step_max'] == plan['entry_Adam_step'] == 16777216.0
        assert entry['Adam_step_min'] == entry['Adam_step_max'] == 16777216.0
        for proof in (raw,start):
            assert proof['parameters'] == 81 and proof['all_steps_are_scalar_tensors'] is True
            assert proof['raw_dtype_counts'] == {'torch.float32':81} and proof['all_raw_scalar_float32'] is True
            assert proof['all_raw_scalar_float32_exact_2p24'] is True
            assert proof['raw_step_min'] == proof['raw_step_max'] == 16777216.0
            assert proof['counter_reset_or_optimizer_change'] is False
        kind = 'EXACT_RAW_FLOAT32_2P24_Adam_SATURATION_WITH_OWN_APPLIED_DOSE'
    return dict(schema='robotron-fresh-capture-applied-dose-and-Adam-progress-proof-v1',classification=kind,
        own_threshold_applied_updates=applied,own_threshold_replay_inserts=replay,
        own_elapsed_s=added['elapsed_s'],entry_clocks=entry['clocks'],endpoint_clocks=verification['clocks'],
        anchor_training_steps=anchor['training_steps'],anchor_optimized_samples=anchor['optimized_samples'],
        integer_clocks_are_not_substituted_for_actual_applied_outcomes=True,
        raw_Adam_step_reset_or_training_change=False,quality_qualified=False)


def run(plan_path):
    plan = json.loads(plan_path.read_bytes())
    source = Path(plan['observer_library']['path'])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == plan['observer_library']['sha256']
    observer = load(source)
    observer.configure(plan)
    directory = plan_path.parent
    assert plan['thresholds'] == dict(applied_updates=5000, replay_inserts=1_000_000, elapsed_s=3600)
    assert plan['maximum_wait_s'] == 14400 and plan['original_DQN_window_unchanged'] is True
    assert not (directory/'anchor.raw.json').exists(), 'Original candidate window already started'
    for value in plan['inputs']:
        observer.check_pin(value)
    entry = selected_entry_amendment(plan, observer, directory)
    anchor = observer.observe(plan['owner'], directory, plan['expected_exposure_lineage'])
    observer.validate(anchor, plan['owner'])
    observer.publish(directory/'anchor.raw.json', anchor, exclusive=True)
    started = time.monotonic()
    previous = anchor
    last_update = started
    crossed = None
    with (directory/'observations.jsonl').open('x') as stream:
        while True:
            for value in plan['inputs']:
                observer.check_pin(value)
            current = observer.observe(plan['owner'], directory, plan['expected_exposure_lineage'])
            observer.validate(current, plan['owner'], previous=previous)
            added = additions(current, anchor, time.monotonic()-started)
            if added['applied_updates'] > additions(previous, anchor, 0)['applied_updates']:
                last_update = time.monotonic()
            assert time.monotonic()-last_update < 60, 'No admitted optimizer update for60s'
            status = dict(schema='robotron-replay-progress-candidate-window-status-v1',
                state='waiting_for_autosave' if crossed else 'collecting', updated_unix_s=time.time(),
                owner=plan['owner'], added=added, thresholds=plan['thresholds'],
                original_DQN_window_unchanged=True, quality_qualified=False,
                causal_learning_speed_qualified=False, promotion=False)
            if crossed is None and ready(added, plan['thresholds']):
                crossed = time.time()
                observer.publish(directory/'first-threshold.raw.json', current, exclusive=True)
                status['state'] = 'waiting_for_autosave'
            observer.publish(directory/'status.json', status)
            observer.publish(Path(plan['dashboard_status']), status)
            stream.write(json.dumps(status)+'\n')
            stream.flush()
            checkpoint = Path(plan['checkpoint'])
            if crossed is not None and checkpoint.stat().st_mtime > crossed+10:
                endpoint = observer.copy_snapshot(checkpoint, directory/'endpoint.pt')
                observer.publish(directory/'capture-context.raw.json', current, exclusive=True)
                verification = verify_CPU(plan, directory, endpoint, observer)
                threshold = observer.read(directory/'first-threshold.raw.json')
                assert all(verification['clocks'][key] >= threshold[key] for key in observer.CLOCKS)
                assert verification['clocks']['training_steps'] > anchor['training_steps']
                progress = endpoint_progress_proof(verification, entry, plan, anchor, threshold, added, observer)
                for value in plan['inputs']:
                    observer.check_pin(value)
                status.update(state='captured_CPU_verified', endpoint=endpoint, progress_proof=progress,
                    CPU_verification=observer.pin(directory/'endpoint-CPU.json'), updated_unix_s=time.time())
                observer.publish(directory/'result.json', status, exclusive=True)
                observer.publish(directory/'status.json', status)
                observer.publish(Path(plan['dashboard_status']), status)
                return
            if time.monotonic()-started >= plan['maximum_wait_s']:
                status['state'] = 'exposure_bound_inconclusive'
                observer.publish(directory/'inconclusive.json', status, exclusive=True)
                observer.publish(directory/'status.json', status)
                observer.publish(Path(plan['dashboard_status']), status)
                return
            previous = current
            time.sleep(10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.plan.resolve(strict=True))
    except BaseException as failure:
        plan = json.loads(args.plan.read_bytes())
        observer = load(Path(plan['observer_library']['path']))
        status = dict(state='failed', reason=repr(failure), traceback=traceback.format_exc(),
            updated_unix_s=time.time(), original_attempt_preserved=True, original_DQN_window_unchanged=True)
        observer.publish(args.plan.parent/'failure.json', status, exclusive=True)
        observer.publish(args.plan.parent/'status.json', status)
        observer.publish(Path(plan['dashboard_status']), status)
        raise
