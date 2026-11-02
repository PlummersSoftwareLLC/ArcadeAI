"""One ROOT-selected RAW phase-timing diagnostic OUTPUT; no acceptance or actions.

INPUT remains original4947 cached oldLua/env0. NEW owned authority names the
ROOT-selected current OUTPUT actor/binding/count, not original2258553. A new one-use directory is consumed
before one exec. No install, signal, retry, rearm, observation or publication.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys

MODE = 'DIAGNOSTICRAW_TIMING_ONE_USE_SLOT163'
INPUT_SHA = '494797d8c8e0f6e9511ce93cb295baa03ec796928c7b606ca20f5deecc9c411d'
MINIMUM_HELD_INPUT_COUNT = 215
RAW_WIRE_POLICY = dict(format=1, name='raw_rgb565be', RLE_enabled=False)
DIAGNOSTIC_SCOPE = dict(stdout_observation_budget_s=10, aggregation_target_s=5,
    existing_stdout_only=True, hard_emission_deadline_claimed=False,
    clock_requirement='host_wall', cpu_scope='process_cpu_all_threads',
    fallback='header_only_no_timing_no_abort')
DIAGNOSTIC_PHASES = ['frame_period', 'capture_total', 'snapshot_size', 'snapshot_pixels',
                     'convert', 'serialize', 'socket_write', 'action_wait']
SOURCE_SHAS = dict(
    fuse='b5fdc64b6777e6db2541f7c535be2fc49e47f5b565dcd714086cdb33d6041723',
    guards='9a8fe7c08e1e941e2d26a2cc3c65124b27129b9f470a0020453e33010bf32027',
    collector='1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0')
AUTHORITY_KEYS = {'schema', 'mode', 'root_selection', 'current_output_binding', 'base_manifest',
                  'fresh_parent_snapshot', 'supervisor_owner', 'supervisor_process',
                  'prior_actor', 'output_lua', 'claim_directory', 'diagnostic_scope'}


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_authority(authority, read, base, guards):
    require(type(authority) is dict and set(authority) == AUTHORITY_KEYS
            and authority['schema'] == 'robotron-slot163-RAW-timing-one-use-authority-v1'
            and authority['mode'] == MODE and all(v is not None for v in authority.values()),
            'Actual NEXT experiment facts remain unfilled or unknown')
    selection = read(authority['root_selection'])
    require(selection['schema'] == 'robotron-root-slot163-RAW-timing-diagnostic-selection-v1'
            and selection['mode'] == MODE and selection['one_original_exec_only'] is True
            and selection['persistent_or_rollout_acceptance'] is False
            and selection.get('diagnostic_only') is True
            and selection.get('diagnostic_scope') == authority['diagnostic_scope'] == DIAGNOSTIC_SCOPE
            and all(selection[key] == authority[key] for key in ('current_output_binding', 'base_manifest',
                'fresh_parent_snapshot', 'prior_actor', 'output_lua', 'claim_directory')),
            'Explicit ROOT diagnostic-only one-use target and bounded observation scope required')
    expected_count = selection.get('expected_held_input_count')
    require(type(expected_count) is int and MINIMUM_HELD_INPUT_COUNT <= expected_count <= 4096
            and selection.get('wire_policy') == RAW_WIRE_POLICY,
            'ROOT must select exact existing held-input count and RAW format1 wire policy')
    release = read(selection['root_freeze_release'])
    require(release['schema'] == 'robotron-root-fixed03-preview-freeze-release-v1'
            and release['all_four_legs_qualified'] is True and release['all_owned_scopes_closed'] is True,
            'Original fixed comparison freeze is not released')
    require(authority['base_manifest']['sha256'] == INPUT_SHA, 'Exact original cached INPUT4947 required')
    manifest = base.read_manifest(authority['base_manifest']['path'], authority['base_manifest']['sha256'])
    base.read_bytes_pin(authority['base_manifest'])
    require(manifest['target_lua']['sha256'] ==
            '507f3f5a799d49791d2c6cbca3f4600167a166c4a410723d4d29225d18b6e0ab'
            and authority['output_lua'] != manifest['target_lua'],
            'Keep old INPUT507 authority distinct from experimental OUTPUT target')
    read(authority['output_lua'], False)
    binding = read(authority['current_output_binding']); policy = read(binding['supervision_policy'])
    current_output_lua = binding['preview_extra_source_pins']['target_lua']
    require(current_output_lua['sha256'] == binding['preview_expected_target_sha256']
            and authority['output_lua'] != current_output_lua,
            'Current OUTPUT source and different ROOT RAW target must be explicit')
    read(current_output_lua, False)
    proof = read(selection['capture_equivalence_proof'])
    require(current_output_lua['sha256'] ==
                'cbd8109f8d62f65c26c38ea91c73b3285fda0812895ee5e5fbf4e8565afedbd1'
            and authority['output_lua']['sha256'] ==
                'cc32f15cf43f972209554e23dd4438e4f191938e75a98903007729725951305f'
            and proof['schema'] == 'robotron-preview-RAW-phase-timing-source-and-semantics-v1'
            and proof['parent'] == current_output_lua and proof['candidate'] == authority['output_lua']
            and proof['diagnostic_only'] is True and proof['wire_policy'] == RAW_WIRE_POLICY
            and proof['gameplay_protocol_decoded_pixels_unchanged'] is True
            and proof['encoded_frame_bytes_unchanged'] is True
            and proof['telemetry_wire_fields_unchanged'] is True
            and proof['server_source_unchanged'] is True
            and proof['existing_stdout_only'] is True and proof['selected_slot'] == 163
            and proof['aggregation_target_s'] == DIAGNOSTIC_SCOPE['aggregation_target_s']
            and proof['clock_requirement'] == DIAGNOSTIC_SCOPE['clock_requirement']
            and proof['cpu_scope'] == DIAGNOSTIC_SCOPE['cpu_scope']
            and proof['fallback'] == DIAGNOSTIC_SCOPE['fallback']
            and proof['VERSION_header_once'] is True and proof['phase_names'] == DIAGNOSTIC_PHASES
            and type(proof['actual_CPU_exit']) is int and proof['actual_CPU_exit'] == 0,
            'Exact unchanged-RAW phase-timing diagnostic source/clock/stdout proof required')
    result = read(proof['semantic_checks'])
    require(result['schema'] == 'robotron-RAW-phase-timing-Lua54-semantics-v1'
            and all(result[key] is True for key in ('actual_Lua_syntax', 'full_source_exact_delta',
                'decoded_capture_bytes_equality', 'socket_write_bytes_and_reply_semantics_unchanged',
                'selected_only_bounded_aggregation', 'fallback_header_only_no_abort')),
            'Actual Lua54 diagnostic semantics proof required')
    require(len(binding['held_hashes']) == expected_count
            and binding['preview_actual_roles']['163']['eval'] is True
            and policy['baseline_actors']['163'] == authority['prior_actor']
            and policy['fleet'] == authority['supervisor_owner'],
            'Exact ROOT-selected binding/count/current OUTPUT/original supervisor required')
    selected = next(row for row in binding['actors'] if row['slot'] == 163)
    require((selected['pid'], selected['starttime_ticks']) ==
            (authority['prior_actor']['pid'], authority['prior_actor']['starttime_ticks']),
            'Current OUTPUT binding process differs')
    census = base.strict_json(base.read_bytes_pin(manifest['role_census']))
    original = census['actual_snapshot']['actors']['163']; prior = authority['prior_actor']
    require(prior['pid'] != original['pid'] and prior['starttime_ticks'] > original['starttime_ticks']
            and prior['environment']['ROBOTRON_EVAL_MODE'] == '1'
            and prior['command'][prior['command'].index('-autoboot_script') + 1] == current_output_lua['path'],
            'Never authorize against old cached INPUT2258553 instead of current OUTPUT')
    fresh = read(authority['fresh_parent_snapshot'])
    require(fresh['actors'] == policy['baseline_actors']
            and fresh['owners']['fleet']['process'] == authority['supervisor_process']
            and authority['supervisor_process']['environment']['ROBOTRON_EVAL_MODE'] == '0',
            'Fresh current OUTPUT/original cached supervisor differs')
    guards.validate_private_claim_directory(authority['claim_directory'])
    return manifest


def prepare_output(authority, manifest, args, environment, base):
    command, output = base.prepare_launch(manifest, args, environment)
    if environment['ROBOTRON_CLIENT_SLOT'] == '163':
        require(authority['mode'] == MODE and authority['output_lua'] != manifest['target_lua'],
                'Unknown capture experiment target')
        at = command.index('-autoboot_script') + 1
        require(command[at] == manifest['target_lua']['path'] and output['ROBOTRON_EVAL_MODE'] == '1',
                'Reviewed INPUT preparation/explicit eval changed')
        command[at] = authority['output_lua']['path']
    return command, output


def dispatch(authority, authority_pin, args, environment, read, base, guards, fuse,
             collector, exec_function=None):
    require(read(authority_pin) == authority, 'Actual immutable NEXT authority differs')
    manifest = validate_authority(authority, read, base, guards)
    command, output = prepare_output(authority, manifest, args, environment, base)
    def parent_check():
        guards.validate_private_claim_directory(authority['claim_directory'])
        observed = fuse.verify_parent(authority, collector)  # NEW current OUTPUT identity
        observed['prior_owned_output_identity'] = dict(pid=authority['prior_actor']['pid'],
            starttime_ticks=authority['prior_actor']['starttime_ticks'])
        observed['prior_owned_output_absent'] = True
        return observed
    fuse.dispatch(authority, authority_pin, command, output, parent_check, exec_function)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print('PLAN_ONLY: no NEXT authority, exec, claim, install or process action')
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--base-helper', required=True)
    parser.add_argument('--fuse-helper', required=True)
    parser.add_argument('--collector-source', required=True)
    parser.add_argument('--accepted-guards', required=True)
    parser.add_argument('--authority', required=True)
    parser.add_argument('--authority-sha256', required=True)
    parser.add_argument('--expected-source-sha256', required=True)
    parser.add_argument('mame_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    source = Path(__file__); st = source.lstat()
    require(source.resolve(strict=True) == source and stat.S_IMODE(st.st_mode) == 0o444
            and hashlib.sha256(source.read_bytes()).hexdigest() == args.expected_source_sha256,
            'Exact frozen NEXT helper required')
    # Bootstrap only the exact already-reviewed fuse; it then supplies stable8
    # full source identity reads and the original immutable base loader.
    fuse_path = Path(args.fuse_helper); raw = fuse_path.read_bytes()
    require(fuse_path.resolve(strict=True) == fuse_path and stat.S_IMODE(fuse_path.lstat().st_mode) == 0o444
            and hashlib.sha256(raw).hexdigest() == SOURCE_SHAS['fuse'], 'Exact reviewed fuse required')
    import types
    fuse = types.ModuleType('_next_capture_fuse'); fuse.__file__ = str(fuse_path)
    sys.modules[fuse.__name__] = fuse; exec(compile(raw, str(fuse_path), 'exec'), fuse.__dict__)
    base, _ = fuse.load_base(args.base_helper)
    def read(pin, as_json=True):
        raw = base.read_bytes_pin(pin)
        return base.strict_json(raw) if as_json else raw
    def component(role, path):
        p = Path(path); q = p.lstat(); pin = dict(path=str(p), sha256=SOURCE_SHAS[role], bytes=q.st_size, identity=fuse.identity(q))
        require(stat.S_IMODE(q.st_mode) == 0o444, 'Frozen reviewed component required')
        return fuse.module_bytes('_next_capture_' + role, p, read(pin, False))
    guards = component('guards', args.accepted_guards); collector = component('collector', args.collector_source)
    p = Path(args.authority); st = p.lstat()
    require(stat.S_IMODE(st.st_mode) == 0o444, 'Frozen actual NEXT authority required')
    authority_pin = dict(path=str(p), sha256=args.authority_sha256, bytes=st.st_size, identity=fuse.identity(st))
    authority = read(authority_pin)
    require(args.mame_args[:1] == ['--'], 'Literal MAME argv separator required')
    if args.execute:
        dispatch(authority, authority_pin, args.mame_args[1:], dict(os.environ), read,
                 base, guards, fuse, collector)
    else:
        manifest = validate_authority(authority, read, base, guards)
        prepare_output(authority, manifest, args.mame_args[1:], dict(os.environ), base)
        print('CHECK_ONLY_NO_CLAIM_NO_EXEC')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        print('NEXT_CAPTURE_ONCE_REFUSED: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(2)
