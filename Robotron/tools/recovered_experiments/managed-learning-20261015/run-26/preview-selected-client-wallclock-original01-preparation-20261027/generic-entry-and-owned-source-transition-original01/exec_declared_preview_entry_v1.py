"""Default-inert entry for the reviewed accepted-preview transform.

No install, publication, stop, retry, batch or claim. Explicit execution requires
an actual ROOT accepted one-slot benchmark, fresh-parent plan and owned physical
wrapper-source commit. Cached supervisor INPUT remains oldLua/env0.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import types

EXPECTED_MODULES = {
    'base': 'bfff44be287802cc226470050594bf4231051db4f35f087ddaca2bb3be69becc',
    'fuse': 'b5fdc64b6777e6db2541f7c535be2fc49e47f5b565dcd714086cdb33d6041723',
    'collector': '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0',
    'core': '47dd609018b9f9dbf175f11caf8da2a5e87f8c9e66d43ee0b79c87aa0eb96cd5',
    'accepted': '9a8fe7c08e1e941e2d26a2cc3c65124b27129b9f470a0020453e33010bf32027',
    'roles': '4d70789d61a7227cc78949df212940379b6e71eb2f7ee0df9e7ce22634404bb6',
    'transition': '8447849e5a6a3e1f7e4eba8c58f38a8b213426745066aa7ad5e0590e062c1363',
}


def require(value, message):
    if not value:
        raise ValueError(message)


def load_module(name, path, raw):
    module = types.ModuleType(name); module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def small_frozen_path(path, expected_sha):
    """Bootstrap only: immutable source, canonical regular owned full identity."""
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path, 'Canonical frozen path required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o444
            and before.st_uid == os.getuid() and before.st_nlink == 1
            and 0 < before.st_size <= 2_000_000, 'Small immutable owned file required')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        require(opened == before, 'Frozen source changed before open')
        raw = stream.read(2_000_001)
        require(os.fstat(stream.fileno()) == before, 'Frozen source changed during read')
    require(path.lstat() == before and len(raw) == before.st_size
            and hashlib.sha256(raw).hexdigest() == expected_sha, 'Frozen source SHA/identity differs')
    return raw, before


def load_runtime(config_pin, config, entry_pin):
    require(type(config.get('modules')) is dict and set(config['modules']) == set(EXPECTED_MODULES),
            'Exact reviewed module roles required')
    for role, expected in EXPECTED_MODULES.items():
        require(config['modules'][role]['sha256'] == expected, 'Unreviewed module: ' + role)
    fuse_pin = config['modules']['fuse']
    raw, _ = small_frozen_path(fuse_pin['path'], EXPECTED_MODULES['fuse'])
    fuse = load_module('_preview_entry_fuse', fuse_pin['path'], raw)
    base, _ = fuse.load_base(config['modules']['base']['path'])

    def read(pin, as_json=True):
        if as_json:
            require(pin['identity']['mode'] == '0o444' and pin['identity']['uid'] == os.getuid()
                    and pin['identity']['nlink'] == 1, 'Immutable owned JSON evidence required')
        raw = base.read_bytes_pin(pin)
        return base.strict_json(raw) if as_json else raw

    require(read(config_pin) == config and config['entry_source'] == entry_pin,
            'Selected immutable config/self source differs')
    modules = dict(base=base, fuse=fuse)
    for role, pin in config['modules'].items():
        require(pin['identity']['mode'] == '0o444' and pin['identity']['uid'] == os.getuid()
                and pin['identity']['nlink'] == 1, 'Frozen owned implementation required: ' + role)
        raw = read(pin, False)
        if role not in modules:
            modules[role] = load_module('_preview_entry_' + role, pin['path'], raw)
    modules['transition'].validate_config(config)
    return modules, read


def prepare_context(config_pin, config, entry_pin, modules, read):
    """Actual full plan/source transition before any possible exec."""
    transition = modules['transition']; transition.validate_config(config)
    plan = read(config['plan'])
    context = modules['core'].validate_plan(plan, read, modules['base'], modules['accepted'], modules['roles'].roles)
    commit, commit_pin = transition.read_owned_commit(config, modules['accepted'], modules['base'])
    source = transition.validate_commit(commit, config_pin, config, entry_pin, read)
    prior = read(config['prior_binding']); prior_policy = read(prior['supervision_policy'])
    require(context['current_registry']['actors'] == prior_policy['baseline_actors'],
            'Plan current OUTPUT and source-adoption prior registry differ')
    return dict(plan=plan, context=context, source=source, actual_owned_commit=commit_pin)


def admit(prepared, args, environment, modules, read, exec_function=None):
    """Literal argv/env transform; all parent checks precede one execve."""
    slot = environment['ROBOTRON_CLIENT_SLOT']
    context = prepared['context']
    # The same exact direct-parent/current-output-absence check applies even
    # for undeclared passthrough slots. It sends no signal and creates no retry.
    modules['fuse'].verify_parent(dict(supervisor_owner=context['parent_owner'],
        supervisor_process=context['parent_process'],
        prior_actor=context['current_registry']['actors'][slot]), modules['collector'])
    modules['core'].dispatch(prepared['plan'], args, environment, read, modules['base'],
        modules['accepted'], modules['roles'].roles, modules['fuse'], modules['collector'], exec_function)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print('PLAN_ONLY: no config/commit/benchmark, no exec or source action')
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--expected-source-sha256', required=True)
    parser.add_argument('mame_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    source = Path(__file__)
    raw, source_stat = small_frozen_path(source, args.expected_source_sha256)
    config_raw, config_stat = small_frozen_path(args.config, args.config_sha256)
    # Bootstrap only the exact already-reviewed base reader; no config-selected
    # source executes before its role's hardcoded implementation SHA is checked.
    import json
    config = json.loads(config_raw, object_pairs_hook=unique_object,
                        parse_constant=invalid_constant)
    fuse_pin = config['modules']['fuse']
    fuse_raw, _ = small_frozen_path(fuse_pin['path'], EXPECTED_MODULES['fuse'])
    fuse = load_module('_preview_entry_bootstrap_fuse', fuse_pin['path'], fuse_raw)
    base, _ = fuse.load_base(config['modules']['base']['path'])
    entry_pin = dict(path=str(source), sha256=hashlib.sha256(raw).hexdigest(),
                     bytes=len(raw), identity=base.identity(source_stat))
    config_pin = dict(path=args.config, sha256=args.config_sha256,
                      bytes=len(config_raw), identity=base.identity(config_stat))
    modules, read = load_runtime(config_pin, config, entry_pin)
    prepared = prepare_context(config_pin, config, entry_pin, modules, read)
    if args.check:
        print(json.dumps(dict(status='CHECK_ONLY_NO_EXEC', source_transition=prepared['source'],
            owned_commit=prepared['actual_owned_commit'], override_slots=prepared['plan']['override_slots'])))
        return 0
    require(args.mame_args[:1] == ['--'], 'Literal argv separator required')
    admit(prepared, args.mame_args[1:], dict(os.environ), modules, read)
    return 0


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate config JSON key')
        result[key] = value
    return result


def invalid_constant(_):
    raise ValueError('Nonfinite config JSON forbidden')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        print('DECLARED_PREVIEW_ENTRY_REFUSED: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(2)
