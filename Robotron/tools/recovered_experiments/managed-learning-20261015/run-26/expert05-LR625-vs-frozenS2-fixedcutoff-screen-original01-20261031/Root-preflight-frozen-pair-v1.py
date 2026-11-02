"""Root's finite, CPU-only prelaunch check of this frozen policy pair."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

CASE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    started = time.monotonic()
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    prepared = json.loads((CASE / 'prepared-matched-fixed-cutoff-two-arm-DATA-NOT-LAUNCHED-v1.json').read_text())
    assert prepared['ordered_legs'] == ['R1', 'C1']
    source = prepared['selected_sources']['native']
    assert source['sha256'] == '8c8b95fb12c2d12cc118c708bc2a379459ef3a7128b88b9330e974064e2b5fb3'
    assert hashlib.sha256(Path(source['path']).read_bytes()).hexdigest() == source['sha256']
    native = load('_Root_postdose_native_preflight', source['path'])
    helper = native.parent().helpers()
    controller_source = prepared['selected_sources']['controller']
    assert controller_source['sha256'] == '4e0815686c40f9e1205c83433e86eed0f96c699b5c925bfc0277df8a31707d5b'
    controller = load('_Root_postdose_controller_preflight', helper.checked(controller_source))
    outer = load('_Root_postdose_outer_preflight', helper.checked(prepared['selected_sources']['outer']))
    selection = json.loads(helper.checked(prepared['selection']).read_text())
    configs = json.loads(helper.checked(prepared['controller_configs']).read_text())
    assert selection['candidate']['checkpoint']['sha256'] == 'f1c369372c027987bcad328c76924c3abd34feaa13913a02d1f927c1a5354e39'
    cpu = json.loads(helper.checked(selection['candidate']['authority']).read_text())
    assert cpu['optimizer_lrs'] == [6.25e-6] and cpu['CUDA_initialized'] is False
    assert cpu['clocks'] == selection['candidate']['expected_policy_clocks']
    assert cpu['checkpoint']['sha256'] == selection['candidate']['checkpoint']['sha256']
    floor_path = CASE.parent / 'hot-expert05-LR625-applied60k-replay20M-learner16M-original01-20261031/Root-selected-completed-expert05-dose-endpoint-original01.json'
    floor_raw = floor_path.read_bytes()
    assert hashlib.sha256(floor_raw).hexdigest() == '824dd4d9b259d743ab4ce6d095a6c2a55defabc5cf7eee597a49d94109177b85'
    floors = json.loads(floor_raw)['logical_clocks_at_qualified_point']
    assert all(cpu['clocks'][key] >= value for key, value in floors.items())
    main_metadata = json.loads(helper.checked(selection['current_Main_metadata']).read_text())
    current_api = json.loads(helper.checked(main_metadata['sources']['API']).read_text())
    current_policy = json.loads(helper.checked(main_metadata['sources']['policy']).read_text())
    current_settings = json.loads(helper.checked(main_metadata['sources']['game_settings']).read_text())
    assert main_metadata['current_main_inline'] == selection['current_main']
    assert current_settings['expert_pct'] == current_api['game_settings']['expert_pct'] == 5
    assert current_api['expert_ratio'] == .05 and current_api['epsilon'] == .1 and current_api['lr'] == 6.25e-6
    assert current_policy['ratchet_frozen'] is False and current_policy['consumer_error'] is None
    assert main_metadata['role_counts']['TRAIN'] == 155
    assert main_metadata['startup_authority_and_held_are_restoration_origin_only'] is True
    assert main_metadata['new_Main_restore_claimed'] is False
    jobs = {leg: json.loads(helper.checked(prepared['jobs'][leg]['job']).read_text()) for leg in ['R1', 'C1']}
    old_tokens = set()
    for name in ['df519-vs-S2-fixed-cutoff-liveness-screen-original01-20261031',
                 'LR625-postdose-vs-frozenS2-fixedcutoff-screen-original01-20261031',
                 'later-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031']:
        for leg in ['R1', 'C1']:
            history = json.loads((CASE.parent / name / leg / 'job.json').read_text())
            old_tokens.update(history['sessions'].values())
            old_tokens.update(history['connections'].values())
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
    assert 'torch' not in sys.modules
    result = dict(status='PASS_ACTUAL_NATIVE_CONTEXT_PACKAGE_C218_DATA_AND_FROZEN_POLICY_IDENTITIES',
        original_actual_exit=0, display=outer.screen_display(selection), legs=legs,
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
