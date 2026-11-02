"""Staged one-slot exec adapter. Import/check never launches any process.

The shell entry preserves the existing wrapper's wait validation. This adapter
revalidates its immutable manifest, changes only slot163's Lua/explicit role,
then execs MAME. No supervisor, signal, restart, installation or retry logic.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

MAME_EXECUTABLE = '/usr/games/mame'
TRIAL_SLOT = 163
SCHEMA = 'robotron-one-slot-preview-role-bound-launch-manifest-v1'
PIN_KEYS = {'path', 'sha256', 'bytes', 'identity'}
IDENTITY_KEYS = {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'mode', 'uid', 'nlink'}
MANIFEST_KEYS = {'schema', 'scope', 'original_wrapper', 'original_lua', 'target_lua',
                 'wait_library', 'role_census', 'override_slot', 'slots'}
ROW_KEYS = {'slot', 'connection_id', 'eval', 'pid', 'birth', 'expected_args',
            'expected_environment', 'action'}
MAX_SMALL_BYTES = 2_000_000


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def read_bytes_pin(entry):
    require(type(entry) is dict and set(entry) == PIN_KEYS, 'Exact full source pin required')
    require(type(entry['path']) is str and Path(entry['path']).is_absolute()
            and '..' not in Path(entry['path']).parts, 'Absolute canonical source path required')
    require(type(entry['bytes']) is int and 0 < entry['bytes'] <= MAX_SMALL_BYTES,
            'Bounded small source only')
    require(type(entry['sha256']) is str and re.fullmatch('[0-9a-f]{64}', entry['sha256']),
            'Source SHA256 required')
    require(type(entry['identity']) is dict and set(entry['identity']) == IDENTITY_KEYS,
            'Exact source identity required')
    p = Path(entry['path'])
    before = p.lstat()
    require(stat.S_ISREG(before.st_mode) and p.resolve(strict=True) == p,
            'Source path must be a regular file with no symlink components')
    require(identity(before) == entry['identity'] and before.st_size == entry['bytes'],
            'Selected source identity differs')
    with p.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        require(identity(opened) == identity(before), 'Source changed before open')
        raw = stream.read(MAX_SMALL_BYTES + 1)
        after_open = os.fstat(stream.fileno())
    require(identity(after_open) == identity(before) == identity(p.lstat()),
            'Source changed across read')
    require(len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256'],
            'Selected source SHA/size differs')
    return raw


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON key')
        value[key] = item
    return value


def strict_json(raw):
    def invalid_constant(_):
        raise ValueError('Nonfinite JSON is forbidden')
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def read_manifest(path, expected_sha):
    p = Path(path)
    require(p.is_absolute() and p.resolve(strict=True) == p, 'Exact manifest path required')
    s = p.lstat()
    require(stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode) == 0o444
            and s.st_nlink == 1 and 0 < s.st_size <= MAX_SMALL_BYTES,
            'Frozen bounded regular manifest required')
    with p.open('rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(s), 'Manifest changed before open')
        raw = stream.read(MAX_SMALL_BYTES + 1)
        require(identity(os.fstat(stream.fileno())) == identity(s), 'Manifest changed during read')
    require(identity(p.lstat()) == identity(s) and len(raw) == s.st_size
            and hashlib.sha256(raw).hexdigest() == expected_sha, 'Manifest SHA/identity differs')
    value = strict_json(raw)
    validate_manifest(value)
    return value


def validate_manifest(value):
    require(type(value) is dict and set(value) == MANIFEST_KEYS, 'Exact manifest schema required')
    require(value['schema'] == SCHEMA and value['scope'] == 'one-slot163-preview-trial'
            and type(value['override_slot']) is int and value['override_slot'] == TRIAL_SLOT,
            'Only the prospective slot163 trial is supported')
    for key in ('original_wrapper', 'original_lua', 'target_lua', 'wait_library'):
        read_bytes_pin(value[key])
    require(value['original_wrapper']['sha256'] ==
            '26464f5e7bf9137744a9a867c606aebc97c0beffd99331b93777c38fdee1aea8',
            'Exact original socket-wait wrapper source required')
    require(value['target_lua']['sha256'] ==
            '507f3f5a799d49791d2c6cbca3f4600167a166c4a410723d4d29225d18b6e0ab',
            'Exact selected preview Lua required')
    require(value['original_lua']['sha256'] ==
            '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf',
            'Exact original Lua required')
    census = strict_json(read_bytes_pin(value['role_census']))
    require(census['schema'] == 'robotron-preview-rollout-readonly192-census-and-role-map-v1',
            'Actual role census required')
    actors = census['actual_snapshot']['actors']
    roles = {str(row['slot']): row for row in census['actual192_role_map']}
    wanted = {str(slot) for slot in range(192)}
    require(set(actors) == set(roles) == wanted
            and len(census['actual192_role_map']) == 192, 'Exact192 observed role/actor members required')
    require(len({row['connection_id'] for row in roles.values()}) == 192,
            'Observed connection IDs must be unique')
    require(type(value['slots']) is dict and set(value['slots']) == wanted, 'Exact192 manifest slots required')
    for key, row in value['slots'].items():
        require(type(row) is dict and set(row) == ROW_KEYS, 'Exact per-slot contract required')
        original, role = actors[key], roles[key]
        require(type(row['slot']) is int and str(row['slot']) == key
                and type(row['connection_id']) is int and row['connection_id'] >= 0
                and type(row['eval']) is bool and type(row['pid']) is int
                and type(row['birth']) is int and row['pid'] > 0 and row['birth'] > 0,
                'Exact slot/role/original identity required')
        require((row['pid'], row['birth']) == (original['pid'], original['starttime_ticks'])
                and (row['connection_id'], row['eval']) == (role['connection_id'], role['eval']),
                'Slot contract differs from actual actor/CID/role evidence')
        require(row['expected_args'] == original['command'][1:]
                and original['command'][0] == MAME_EXECUTABLE
                and row['expected_environment'] == original['environment'],
                'Original argv/environment contract differs')
        require(row['action'] == ('override' if row['slot'] == TRIAL_SLOT else 'passthrough'),
                'Only one slot may change Lua/role')
        require(row['expected_args'].count('-autoboot_script') == 1
                and row['expected_args'][row['expected_args'].index('-autoboot_script') + 1]
                == value['original_lua']['path'], 'Single original Lua argument required')
    require(value['slots'][str(TRIAL_SLOT)]['eval'] is True,
            'Observed selected slot must retain its actual eval role')


def prepare_launch(manifest, args, environment):
    """Pure argv/environment construction after immutable manifest validation."""
    require(type(args) is list and all(type(x) is str and '\0' not in x for x in args),
            'Literal argv list required')
    require(type(environment) is dict and all(type(k) is str and type(v) is str
            and '\0' not in k + v and '=' not in k for k, v in environment.items()),
            'String environment required')
    slot = environment.get('ROBOTRON_CLIENT_SLOT', '')
    require(re.fullmatch('0|[1-9][0-9]{0,2}', slot) and slot in manifest['slots'],
            'Known unambiguous launcher slot required')
    row = manifest['slots'][slot]
    require(args == row['expected_args'], 'Incoming MAME argv differs from observed original')
    expected = row['expected_environment']
    # These two values were installed by the original wrapper only at exec.
    # The new helper is deliberately started without preloading the MAME shim.
    for key, value in expected.items():
        if key not in ('LD_PRELOAD', 'ROBOTRON_SOCKET_WAIT_PORT'):
            require(environment.get(key) == value, 'Incoming actor environment differs: ' + key)
    skipped = {'LD_PRELOAD', 'ROBOTRON_SOCKET_WAIT_PORT'}
    controlled = lambda e: {key for key in e if key.startswith('ROBOTRON_') and key not in skipped}
    require(controlled(environment) == controlled(expected), 'Unexpected actor control environment')
    library = environment.get('ROBOTRON_SOCKET_WAIT_LIBRARY', '')
    require(library == manifest['wait_library']['path'] and library.startswith('/')
            and not re.search(r'[\s:]', library), 'Exact original wait library required')
    require(re.fullmatch(r'([1-9][0-9]{2,3}|10000)', environment.get('ROBOTRON_SOCKET_WAIT_US', '')),
            'Original bounded wait interval required')
    result_args, result_env = list(args), dict(environment)
    result_env['LD_PRELOAD'] = library
    result_env['ROBOTRON_SOCKET_WAIT_PORT'] = '9998'
    if row['action'] == 'override':
        at = result_args.index('-autoboot_script') + 1
        result_args[at] = manifest['target_lua']['path']
        result_env['ROBOTRON_EVAL_MODE'] = '1' if row['eval'] else '2'
    return [MAME_EXECUTABLE, *result_args], result_env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--expected-source-sha256', required=True)
    parser.add_argument('mame_args', nargs=argparse.REMAINDER)
    options = parser.parse_args(argv)
    source = Path(__file__)
    require(source.resolve(strict=True) == source and stat.S_IMODE(source.lstat().st_mode) == 0o444
            and hashlib.sha256(source.read_bytes()).hexdigest() == options.expected_source_sha256,
            'Exact frozen helper source required')
    manifest = read_manifest(options.manifest, options.manifest_sha256)
    args = options.mame_args
    require(args and args[0] == '--', 'Explicit literal argv boundary required')
    command, environment = prepare_launch(manifest, args[1:], dict(os.environ))
    if options.execute:
        os.execve(command[0], command, environment)
        raise AssertionError('execve returned without replacing the helper')
    print(json.dumps(dict(status='CHECK_ONLY_NO_EXEC', slot=int(environment['ROBOTRON_CLIENT_SLOT']),
                          changed_slot=TRIAL_SLOT, real_MAME_executed=False)))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        print('ROLE_BOUND_MAME_REFUSED: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(2)
