"""Source-only post-trial exec component; default CLI has no action.

INPUT always remains the original supervisor's oldLua/env0 contract. Accepted
OUTPUT is selected RAWcbd810/env1 only after actual27FPS/budget qualification;
rollback OUTPUT is060f/env1 under a NEW one-use permit. Cached INPUT manifest
still has its original507 target authority and is returned UNCHANGED.
ROOT authenticates modules/immutable selection and supplies future actual facts.
"""
import argparse
import hashlib
import math
import os
from pathlib import Path
import stat
import sys
import types

ACCEPT = 'ACCEPTED_PERSISTENT_PREVIEW_SLOT163'
ROLLBACK = 'ONE_USE_ORIGINAL_LUA_EVAL_PRESERVING_ROLLBACK_SLOT163'
PREVIEW_SHA = 'cbd8109f8d62f65c26c38ea91c73b3285fda0812895ee5e5fbf4e8565afedbd1'
RAW_WIRE_POLICY = dict(format=1, name='raw_rgb565be', RLE_enabled=False)
ORIGINAL_SHA = '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf'


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_private_claim_directory(directory):
    """Restore b5's exact four-key identity, plus canonical directory/nlink2.

    Keeping this identity ABI unchanged lets reserve_once recheck the same
    dev/inode/mode/uid on its O_NOFOLLOW directory fd. nlink2 is checked here
    and again by the parent callback after the atomic claim, before exec.
    """
    require(type(directory) is dict and set(directory) == {'path', 'identity'}
            and type(directory['path']) is str and type(directory['identity']) is dict,
            'Exact private claim-directory schema required')
    expected = directory['identity']
    require(set(expected) == {'device', 'inode', 'mode', 'uid'}
            and type(expected['device']) is int and expected['device'] > 0
            and type(expected['inode']) is int and expected['inode'] > 0
            and type(expected['uid']) is int and expected['uid'] == os.getuid()
            and expected['mode'] == '0o700', 'Private0700 owned claim identity required')
    path = Path(directory['path'])
    require(path.is_absolute() and str(path) == directory['path']
            and '..' not in path.parts and path.resolve(strict=True) == path,
            'Canonical nonsymlink claim directory required')
    observed = path.lstat()
    require(stat.S_ISDIR(observed.st_mode) and observed.st_nlink == 2
            and dict(device=observed.st_dev, inode=observed.st_ino,
                     mode=oct(stat.S_IMODE(observed.st_mode)), uid=observed.st_uid) == expected,
            'Actual private claim-directory identity/nlink differs')
    return directory


def validate_RAW_benchmark(authority, selection, read):
    """Prospective strict27FPS/one-percent gate; no practical fallback."""
    require(authority['wire_policy'] == RAW_WIRE_POLICY
            and authority['benchmark_verdict'] is not None,
            'Actual RAW operational verdict is unfilled')
    verdict = read(authority['benchmark_verdict'])
    require(verdict['schema'] == 'robotron-root-selected-RAW-preview-operational-benchmark-verdict-v1'
            and verdict['accepted'] is True
            and verdict['selected_target'] == authority['output_lua']
            and verdict['wire_policy'] == RAW_WIRE_POLICY
            and verdict['actual_output_binding'] == selection['accepted_output_binding']
            and verdict['actual_benchmark_report'] is not None,
            'Actual immutable RAW target/binding/report verdict differs')
    require(verdict['benchmark_target_fps'] == 30 and verdict['minimum_fresh_cache_fps'] == 27
            and verdict['both_ON_windows_target_met'] is True
            and verdict['useful_throughput_within_one_percent_point_budget'] is True,
            'Original30FPS target/27FPS threshold/one-percent point budget not qualified')
    observed = verdict['observed_ON_fresh_cache_fps']
    change = verdict['relative_useful_throughput_point_change']
    require(type(observed) is list and len(observed) == 2
            and all(type(v) in (int, float) and math.isfinite(v) and v >= 27 for v in observed)
            and type(change) in (int, float) and math.isfinite(change) and change >= -0.01,
            'Actual two ON rates or useful-throughput point estimate failed')
    report = read(verdict['actual_benchmark_report'])
    require(report['schema'] == 'robotron-root-selected-RAW-preview-operational-benchmark-report-v1'
            and report['selected_target'] == verdict['selected_target']
            and report['wire_policy'] == verdict['wire_policy']
            and report['actual_output_binding'] == verdict['actual_output_binding']
            and report['observed_ON_fresh_cache_fps'] == observed
            and report['relative_useful_throughput_point_change'] == change
            and report['actual_raw_benchmark_evidence'] is not None,
            'Actual benchmark report/criteria join differs')
    read(report['actual_raw_benchmark_evidence'])


def validate_authority(authority, read, base):
    require(set(authority) == {'schema', 'mode', 'root_selection', 'fresh_parent_snapshot',
            'supervisor_owner', 'supervisor_process', 'prior_actor', 'base_manifest',
            'output_lua', 'claim_directory', 'wire_policy', 'benchmark_verdict'}
            and authority['schema'] == 'robotron-slot163-posttrial-output-authority-v1'
            and authority['mode'] in (ACCEPT, ROLLBACK), 'Exact163 post-trial authority required')
    require(all(authority[key] is not None for key in
                ('root_selection', 'fresh_parent_snapshot', 'supervisor_owner',
                 'supervisor_process', 'prior_actor', 'base_manifest', 'output_lua')),
            'Future actual authority/parent/registry facts are unfilled')
    selection = read(authority['root_selection'])
    require(selection['schema'] == 'robotron-root-slot163-output-selection-v1'
            and selection['mode'] == authority['mode']
            and selection['base_manifest'] == authority['base_manifest']
            and selection['output_lua'] == authority['output_lua']
            and selection['fresh_parent_snapshot'] == authority['fresh_parent_snapshot']
            and selection['prior_actor'] == authority['prior_actor']
            and selection['wire_policy'] == authority['wire_policy']
            and selection['benchmark_verdict'] == authority['benchmark_verdict'], 'ROOT selection differs')
    release = read(selection['root_freeze_release'])
    require(release['schema'] == 'robotron-root-fixed03-preview-freeze-release-v1'
            and release['all_four_legs_qualified'] is True
            and release['all_owned_scopes_closed'] is True, 'Fixed study freeze is not released')
    manifest = base.read_manifest(authority['base_manifest']['path'], authority['base_manifest']['sha256'])
    base.read_bytes_pin(authority['base_manifest'])
    fresh = read(authority['fresh_parent_snapshot'])
    require(fresh['owners']['fleet']['process'] == authority['supervisor_process'],
            'Fresh original supervisor snapshot differs')
    owner = authority['supervisor_owner']; process = authority['supervisor_process']
    require((process['pid'], process['starttime_ticks'], process['cgroup']) ==
            (owner['pid'], owner['starttime_ticks'], owner['cgroup']), 'Fresh parent identity differs')
    require(process['environment']['ROBOTRON_EVAL_MODE'] == '0',
            'Cached supervisor INPUT is still autoenv0')
    require(authority['prior_actor']['pid'] > 0 and authority['prior_actor']['starttime_ticks'] > 0,
            'Exact prior owned process required')
    expected_pin = authority['output_lua'] if authority['mode'] == ACCEPT else manifest['original_lua']
    expected_sha = PREVIEW_SHA if authority['mode'] == ACCEPT else ORIGINAL_SHA
    require(authority['output_lua'] == expected_pin
            and authority['output_lua']['sha256'] == expected_sha, 'Explicit different output source authority required')
    base.read_bytes_pin(authority['output_lua'])
    if authority['mode'] == ACCEPT:
        validate_RAW_benchmark(authority, selection, read)
        require(authority['claim_directory'] is None and selection['accepted_output_binding'] is not None,
                'Persistent admission needs actual accepted output binding, no trial-fuse rearm')
        require(selection['operational_benchmark_accepted'] is True,
                'Persistent preview needs the actual preselected benchmark verdict')
        binding = read(selection['accepted_output_binding'])
        require(binding['preview_expected_target_sha256'] == PREVIEW_SHA
                and binding['preview_actual_roles']['163']['eval'] is True
                and binding['supervision_policy'] is not None
                and binding['preview_slot163_transition'] is not None,
                'Accepted output registry/source/role missing')
        policy = read(binding['supervision_policy'])
        transition = read(binding['preview_slot163_transition'])
        require(transition['schema'] == 'robotron-owned-slot163-next-output-readonly-reconciliation-evidence-v1'
                and transition['actual_eval_preserved'] is True
                and transition['original191_exact'] is True
                and policy['baseline_actors']['163']['environment']['ROBOTRON_EVAL_MODE'] == '1'
                and policy['baseline_actors']['163']['command'][
                    policy['baseline_actors']['163']['command'].index('-autoboot_script') + 1]
                    == authority['output_lua']['path'],
                'Actual adopted output policy/transition are missing')
        actor = next(row for row in binding['actors'] if row['slot'] == 163)
        require((actor['pid'], actor['starttime_ticks']) ==
                (authority['prior_actor']['pid'], authority['prior_actor']['starttime_ticks']),
                'Accepted output process differs from prior-process authority')
    else:
        require(authority['wire_policy'] is None and authority['benchmark_verdict'] is None,
                'Original-Lua rollback cannot inherit RAW acceptance')
        require(authority['claim_directory'] is not None
                and selection['closed_trial_outcome'] is not None
                and selection['explicit_rollback_selected'] is True,
                'Rollback requires separate closed-trial authority and NEW one-use directory')
        validate_private_claim_directory(authority['claim_directory'])
        outcome = read(selection['closed_trial_outcome'])
        require(outcome['schema'] == 'robotron-root-closed-slot163-preview-trial-outcome-v1'
                and outcome['prior_owned_process'] == authority['prior_actor']
                and outcome['original_trial_permit_retained'] is True
                and outcome['actual_outcome_preserved'] is True, 'Actual failed/rolled-back trial provenance missing')
        claim = read(outcome['original_trial_claim'])
        original_permit = read(outcome['original_trial_permit'])
        require(claim['schema'] == 'robotron-slot163-exec-reservation-consumed-v1'
                and claim['original_permit'] == outcome['original_trial_permit']
                and claim['manifest'] == authority['base_manifest']
                and (claim['claimant_pid'], claim['claimant_birth']) ==
                (authority['prior_actor']['pid'], authority['prior_actor']['starttime_ticks']),
                'Rollback must retire the actual trial OUTPUT claimant, not old INPUT actor')
        require(authority['claim_directory']['path'] != original_permit['claim_directory']['path']
                and (authority['claim_directory']['identity']['device'], authority['claim_directory']['identity']['inode']) !=
                (original_permit['claim_directory']['identity']['device'], original_permit['claim_directory']['identity']['inode']),
                'Rollback requires a distinct NEW claim directory, never trial permit rearm')
    return manifest


def accepted_target(authority, read, base):
    require(authority['mode'] == ACCEPT, 'Only accepted RAW authority supplies fleet target')
    validate_authority(authority, read, base)
    return authority['output_lua']


def prepare_output(authority, manifest, args, environment, base):
    """Reuse original bfff INPUT validation; never forge its fixed507f pin."""
    command, result_environment = base.prepare_launch(manifest, args, environment)
    if environment['ROBOTRON_CLIENT_SLOT'] == '163':
        require(authority['mode'] in (ACCEPT, ROLLBACK), 'Unknown output authority')
        expected = authority['output_lua'] if authority['mode'] == ACCEPT else manifest['original_lua']
        require(authority['output_lua'] == expected
                and expected['sha256'] == (PREVIEW_SHA if authority['mode'] == ACCEPT else ORIGINAL_SHA),
                'Wrong explicit source for selected mode')
        at = command.index('-autoboot_script') + 1
        require(command[at] == manifest['target_lua']['path'], 'Frozen base preparation changed')
        command[at] = expected['path']
        require(result_environment['ROBOTRON_EVAL_MODE'] == '1', 'Original eval role lost')
    return command, result_environment


def dispatch(authority, authority_pin, manifest, args, environment,
             base, fuse, collector, read, exec_function=None):
    """Definitions only; selection/source validation always precedes exec."""
    require(read(authority_pin) == authority, 'Actual immutable output authority differs')
    require(validate_authority(authority, read, base) == manifest, 'Input manifest differs')
    command, output_environment = prepare_output(authority, manifest, args, environment, base)
    def parent_check():
        # Deliberately use the NEW authority's output identity, not read_permit
        # from v2 (which binds the original INPUT census actor2258553).
        if authority['mode'] == ROLLBACK:
            validate_private_claim_directory(authority['claim_directory'])
        observed = fuse.verify_parent(authority, collector)
        observed['prior_owned_output_identity'] = dict(pid=authority['prior_actor']['pid'],
                    starttime_ticks=authority['prior_actor']['starttime_ticks'])
        observed['prior_owned_output_absent'] = True
        return observed
    if environment['ROBOTRON_CLIENT_SLOT'] != '163':
        (os.execve if exec_function is None else exec_function)(command[0], command, output_environment)
    elif authority['mode'] == ACCEPT:
        parent_check()
        (os.execve if exec_function is None else exec_function)(command[0], command, output_environment)
    else:
        fuse.dispatch(authority, authority_pin, command, output_environment, parent_check, exec_function)
    raise AssertionError('execve returned without replacing the launcher')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print('PLAN_ONLY: no live authority, exec, claim, install or process action')
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--base-helper', required=True)
    parser.add_argument('--fuse-helper', required=True)
    parser.add_argument('--collector-source', required=True)
    parser.add_argument('--authority', required=True)
    parser.add_argument('--authority-sha256', required=True)
    parser.add_argument('--expected-source-sha256', required=True)
    parser.add_argument('mame_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    source = Path(__file__)
    require(source.resolve(strict=True) == source and stat.S_IMODE(source.lstat().st_mode) == 0o444
            and hashlib.sha256(source.read_bytes()).hexdigest() == args.expected_source_sha256,
            'Exact frozen post-trial helper required')
    fuse_path = Path(args.fuse_helper)
    fuse_bytes = fuse_path.read_bytes()
    require(fuse_path.resolve(strict=True) == fuse_path and stat.S_IMODE(fuse_path.lstat().st_mode) == 0o444
            and hashlib.sha256(fuse_bytes).hexdigest() ==
            'b5fdc64b6777e6db2541f7c535be2fc49e47f5b565dcd714086cdb33d6041723',
            'Exact already-reviewed single-use component required')
    fuse = types.ModuleType('_posttrial_original_fuse'); fuse.__file__ = str(fuse_path)
    sys.modules[fuse.__name__] = fuse
    exec(compile(fuse_bytes, str(fuse_path), 'exec'), fuse.__dict__)
    base, _ = fuse.load_base(args.base_helper)
    def read(entry, as_json=True):
        raw = base.read_bytes_pin(entry)
        return base.strict_json(raw) if as_json else raw
    collector_path = Path(args.collector_source)
    s = collector_path.lstat()
    collector_pin = dict(path=str(collector_path), sha256=fuse.COLLECTOR_SHA,
                         bytes=s.st_size, identity=fuse.identity(s))
    collector = fuse.module_bytes('_posttrial_original_collector', collector_path,
                                  base.read_bytes_pin(collector_pin))
    authority_path = Path(args.authority); s = authority_path.lstat()
    require(stat.S_IMODE(s.st_mode) == 0o444, 'Frozen actual authority required')
    authority_pin = dict(path=str(authority_path), sha256=args.authority_sha256,
                         bytes=s.st_size, identity=fuse.identity(s))
    authority = read(authority_pin)
    manifest = validate_authority(authority, read, base)
    require(args.mame_args and args.mame_args[0] == '--', 'Literal argv boundary required')
    if args.execute:
        dispatch(authority, authority_pin, manifest, args.mame_args[1:], dict(os.environ),
                 base, fuse, collector, read)
    else:
        prepare_output(authority, manifest, args.mame_args[1:], dict(os.environ), base)
        print('CHECK_ONLY: no claim or exec')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        print('POSTTRIAL_SLOT163_REFUSED: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(2)
