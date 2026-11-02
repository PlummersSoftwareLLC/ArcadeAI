"""Default-inert Root preflight for future post-repair LR625 DATA.

Only Root executes after actual dose/copy/CPU and fresh sealed Main context.
This source authoring pass does not create DATA or qualify a future candidate.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

EXPECTED_CONTROL_SHA256 = '3b1a46f7de088698487877ff30171f7dbe1c9d289f39778065a16e85b48a5521'
CASE_BASENAME = 'post-repair-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--prepared')
    parser.add_argument('--prepared-sha256')
    parser.add_argument('--selection', help='Exact Root input selection consumed by the DATA assembler')
    parser.add_argument('--selection-sha256')
    args = parser.parse_args()
    if not args.execute:
        parser.print_help()
        return
    assert all((args.prepared, args.prepared_sha256, args.selection, args.selection_sha256))
    started = time.monotonic()
    CASE = Path(args.prepared).resolve().parent
    assert CASE.name == CASE_BASENAME
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    prepared_raw = Path(args.prepared).read_bytes()
    input_raw = Path(args.selection).read_bytes()
    assert hashlib.sha256(prepared_raw).hexdigest() == args.prepared_sha256
    assert hashlib.sha256(input_raw).hexdigest() == args.selection_sha256
    prepared = json.loads(prepared_raw)
    binding = json.loads(input_raw)
    assert binding['schema'] == 'robotron-Root-post-repair-LR625-frozen-screen-DATA-inputs-v1'
    assert binding['status'] == 'ROOT_SELECTED_ACTUAL_DOSE_COPY_CPU_AND_MAIN_CONTEXT_FOR_DATA_ONLY'
    assert all(binding['Root_prerequisites'][key] is True for key in (
        'original55529_tool_terminal0', 'original55529_process_absent', 'CONTROL_handoff_complete'))
    assert prepared['ordered_legs'] == ['R1', 'C1']
    source = prepared['selected_sources']['native']
    assert source['sha256'] == '8c8b95fb12c2d12cc118c708bc2a379459ef3a7128b88b9330e974064e2b5fb3'
    assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() == source['sha256']
    native = load('_Root_postdose_native_preflight', source['path'])
    helper = native.parent().helpers()
    controller_source = prepared['selected_sources']['controller']
    assert controller_source['sha256'] == '42838b75136c28d5dbaf5d34ac0b29aa7cbbc1f3e692c821c383a5ebf5764f0a'
    controller = load('_Root_postdose_controller_preflight', helper.checked(controller_source))
    outer = load('_Root_postdose_outer_preflight', helper.checked(prepared['selected_sources']['outer']))
    selection = json.loads(helper.checked(prepared['selection']).read_text())
    configs = json.loads(helper.checked(prepared['controller_configs']).read_text())
    assert selection['candidate'] == binding['candidate']
    assert selection['current_main'] == binding['current_main']
    assert selection['current_Main_metadata'] == binding['current_Main_metadata']
    cpu = json.loads(helper.checked(selection['candidate']['authority']).read_text())
    assert cpu['optimizer_lrs'] == [5e-5 * .125] and cpu['CUDA_initialized'] is False
    assert cpu['clocks'] == selection['candidate']['expected_policy_clocks']
    assert cpu['checkpoint']['sha256'] == selection['candidate']['checkpoint']['sha256']
    point = json.loads(helper.checked(binding['candidate_completed_dose_point']).read_text())
    floors = point['logical_clocks_at_qualified_point']
    assert floors == binding['candidate_minimum_saved_clocks']
    assert set(floors) == {'training_steps', 'frame_count', 'learner_frame_count', 'optimized_samples'}
    assert all(type(value) is int and value >= 0 for value in floors.values())
    for key in ('candidate_published_policy_copy', 'candidate_original_CPU_closeout',
                'candidate_named_acknowledgement', 'dose_observer_positive_closeout'):
        helper.checked(binding[key])
    if binding.get('candidate_CPU_metadata_peer') is not None:
        helper.checked(binding['candidate_CPU_metadata_peer'])
    assert all(cpu['clocks'][key] >= value for key, value in floors.items())
    main_metadata = json.loads(helper.checked(selection['current_Main_metadata']).read_text())
    current_api = json.loads(helper.checked(main_metadata['sources']['API']).read_text())
    current_policy = json.loads(helper.checked(main_metadata['sources']['policy']).read_text())
    current_settings = json.loads(helper.checked(main_metadata['sources']['game_settings']).read_text())
    assert main_metadata['current_main_inline'] == selection['current_main']
    assert selection['current_main']['owner']['pid'] == 1644742
    assert selection['current_main']['owner']['starttime_ticks'] == 36415496
    assert all(selection['current_main']['exposure'][kind]['process_id'] == 1644742
               for kind in ('optimizer', 'replay'))
    assert binding['current_Main_snapshot_sources']
    for name, entry in binding['current_Main_snapshot_sources'].items():
        assert main_metadata['sources'][name] == entry
        helper.checked(entry)
    control_entries = [entry for entry in binding['current_Main_snapshot_sources'].values()
                       if entry['sha256'] == EXPECTED_CONTROL_SHA256]
    assert len(control_entries) == 1
    control = json.loads(helper.checked(control_entries[0]).read_text())
    assert type(control['lr_scale']) is float and control['lr_scale'] == .125
    assert type(current_settings['expert_pct']) is type(current_api['game_settings']['expert_pct']) is int
    assert current_settings['expert_pct'] == current_api['game_settings']['expert_pct'] == -1
    for key, expected in [('expert_ratio', .1), ('epsilon', .1), ('lr', 5e-5 * .125)]:
        value = current_api[key]
        assert type(value) in (int, float) and math.isfinite(value) and math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-12)
    assert current_policy['ratchet_frozen'] is False and current_policy['consumer_error'] is None
    assert main_metadata['role_counts'] == binding['current_Main_observed_role_counts']
    assert main_metadata['role_counts']['TRAIN'] == 155
    # Authenticate this actual owner's selected origin; do not reuse old F's
    # same-208501/no-new-restore historical predicates for the repaired Main.
    authority = json.loads(helper.checked(selection['current_main']['startup_authority']).read_text())
    held = json.loads(helper.checked(selection['current_main']['startup_held']).read_text())
    assert authority['schema'] == 'robotron-root-continuous-main-startup-qualified-v1'
    assert authority['new_held_report'] == selection['current_main']['startup_held']
    assert authority['all_model_optimizer_replay_banks_clocks_preserved'] is True
    assert authority['new_mode_source_and_CPU_qualified'] is True
    assert held['schema'] == 'robotron-continuous-main-held-exact-restoration-report-v1'
    assert held['status'] == 'VERIFIED_HELD_BEFORE_FIRST_UPDATE'
    owner = selection['current_main']['owner']
    expected_owner = {key: owner[key] for key in ('pid', 'unit', 'invocation_id', 'cgroup')}
    expected_owner['birth'] = owner['starttime_ticks']
    for recorded in (authority['trainer'], held['owner']):
        assert all(recorded[key] == value for key, value in expected_owner.items())
        assert type(recorded['uid']) is int and recorded['uid'] == 1001
    for key in ('all_online_target_Adam_scaler_payloads_equal',
                'optimizer_implementation_flags_exactly_equal',
                'training_and_memory_locks_held_until_Root_release',
                'dashboard_and_GAME_listener_not_created'):
        assert held[key] is True
    for key in ('optimizer_attempts_before_release', 'new_replay_inserts_before_release'):
        assert type(held[key]) is int and held[key] == 0
    for key in ('samples_since_loaded', 'unmeasured_frames_since_loaded'):
        assert type(held['startup_budget'][key]) is int and held['startup_budget'][key] == 0
    assert held['startup_budget']['fresh_per_boot_baseline_verified'] is True
    assert held['startup_budget']['anchor_installed_or_rebased'] is False
    assert held['startup_budget']['model_optimizer_scaler_replay_or_lifetime_clock_changed'] is False
    for key in ('full_original_mmap_adoption', 'all_eight_scalar_replay_payloads_equal',
                'all_PER_leaf_priorities_equal'):
        assert held['replay'][key] is True
    for bank in ('hof', 'ephof'):
        assert held['replay']['banks'][bank]['all_valid_field_payloads_and_episode_metadata_equal'] is True
    identity_keys = ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')
    for kind in ('optimizer', 'replay'):
        assert {key: held['exposure'][kind][key] for key in identity_keys} == selection['current_main']['exposure'][kind]
    for family in ('total', 'since_epoch'):
        assert all(type(value) is int and value == 0 for value in held['exposure']['optimizer'][family].values())
    for key in ('accepted_total', 'accepted_learner_total', 'accepted_since_epoch', 'accepted_learner_since_epoch'):
        assert type(held['exposure']['replay'][key]) is int and held['exposure']['replay'][key] == 0
    for family in ('accepted_by_source_total', 'accepted_by_source_since_epoch'):
        assert all(type(value) is int and value == 0 for value in held['exposure']['replay'][family].values())
    # These are historical held-startup facts. Do not reopen/hash its mutable
    # checkpoint or claim that a currently training model remains unchanged.
    jobs = {leg: json.loads(helper.checked(prepared['jobs'][leg]['job']).read_text()) for leg in ['R1', 'C1']}
    old_tokens = set()
    for name in ['df519-vs-S2-fixed-cutoff-liveness-screen-original01-20261031',
                 'LR625-postdose-vs-frozenS2-fixedcutoff-screen-original01-20261031',
                 'later-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031',
                 'expert05-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031',
                 'LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031']:
        for leg in ['R1', 'C1']:
            history = json.loads((CASE.parent / name / leg / 'job.json').read_text())
            old_tokens.update(history['sessions'].values())
            old_tokens.update(history['connections'].values())
    assert len(old_tokens) == 640
    tokens = [value for job in jobs.values() for key in ['sessions', 'connections'] for value in job[key].values()]
    assert len(tokens) == len(set(tokens)) == 128 and not set(tokens) & old_tokens
    checked = set()
    legs = []
    for leg, job in jobs.items():
        native.validate_job(job)
        context = native.validate_completed_context(job, helper)
        for entry in job['inputs']:
            key = (entry['path'], entry['sha256'])
            if key not in checked:
                helper.checked(entry)
                checked.add(key)
        helper.checked(job['checkpoint'])
        config = configs['configs'][leg]
        config_path = config['path']
        assert controller.pin(config_path) == config
        actual = controller.checked_config(config_path)
        assert actual['argv'] == prepared['jobs'][leg]['argv']
        assert not Path(actual['output']).exists()
        assert job['current_main'] == selection['current_main']
        assert job['expected_policy_clocks'] == selection['reference' if leg == 'R1' else 'candidate']['expected_policy_clocks']
        legs.append(dict(leg=leg, validate_job='PASS', validate_completed_context='PASS',
            C218_checked_config='PASS', actual_components=len(context['modules']),
            package_pins=len(context['package_pins']), inputs=len(job['inputs']),
            checkpoint_sha256=job['checkpoint']['sha256'],
            expected_policy_clocks=job['expected_policy_clocks'], native_output_absent=True,
            controller_output_absent=True))
    assert all(row['actual_components'] == 12 and row['package_pins'] == 123 for row in legs)
    assert 'torch' not in sys.modules
    result = dict(status='PASS_ACTUAL_NATIVE_CONTEXT_PACKAGE_C218_DATA_AND_FROZEN_POLICY_IDENTITIES',
        original_actual_exit=0, prepared_sha256=args.prepared_sha256,
        Root_input_selection_sha256=args.selection_sha256, display=outer.screen_display(selection), legs=legs,
        all128_tokens_distinct_and_disjoint_from_prior_study=True,
        distinct_dependency_stream_hashes_checked=len(checked), both_frozen_policy_stream_SHA_checked=True,
        torch_imported=False, model_tensor_loaded=False, native_or_controller_launched=False,
        runtime_outputs_created=False, elapsed_s=time.monotonic()-started,
        observed_unix_s=time.time())
    path = CASE / 'Root-actual-metadata-preflight-original01.json'
    with path.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(result))


if __name__ == '__main__':
    main()
