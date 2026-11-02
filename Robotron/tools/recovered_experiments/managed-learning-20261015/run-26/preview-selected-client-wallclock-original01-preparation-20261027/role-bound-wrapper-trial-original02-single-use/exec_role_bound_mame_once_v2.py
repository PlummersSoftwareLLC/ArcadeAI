"""Staged one-use slot163 fuse around the frozen v1 argv/role adapter.

No installation, process signals, retry, cleanup or supervisor control. A claim
is a consumed reservation BEFORE exec, never evidence that MAME succeeded.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

BASE_SHA = 'bfff44be287802cc226470050594bf4231051db4f35f087ddaca2bb3be69becc'
COLLECTOR_SHA = '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0'
PERMIT_KEYS = {'schema', 'scope', 'base_helper', 'base_manifest', 'collector_source',
               'supervisor_owner', 'supervisor_process', 'prior_actor', 'claim_directory'}
CLAIM_NAME = 'slot163-MAME-exec-reservation.json'


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def module_bytes(name, path, raw):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def load_base(path):
    p = Path(path)
    s = p.lstat()
    require(p.is_absolute() and p.resolve(strict=True) == p and stat.S_ISREG(s.st_mode)
            and stat.S_IMODE(s.st_mode) == 0o444, 'Exact frozen v1 helper required')
    raw = p.read_bytes()
    require(identity(p.lstat()) == identity(s) and hashlib.sha256(raw).hexdigest() == BASE_SHA,
            'Frozen v1 source differs')
    pin = dict(path=str(p), sha256=BASE_SHA, bytes=len(raw), identity=identity(s))
    base = module_bytes('_role_bound_v1_fuse_base', p, raw)
    require(base.read_bytes_pin(pin) == raw, 'Full v1 source pin differs')
    return base, pin


def read_permit(base, path, sha, base_pin):
    p = Path(path)
    s = p.lstat()
    require(stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode) == 0o444,
            'Frozen permit required')
    pin = dict(path=str(p), sha256=sha, bytes=s.st_size, identity=identity(s))
    permit = base.strict_json(base.read_bytes_pin(pin))
    require(type(permit) is dict and set(permit) == PERMIT_KEYS
            and permit['schema'] == 'robotron-slot163-single-use-launch-permit-v1'
            and permit['scope'] == 'ONE_ORIGINAL_SLOT163_MAME_EXEC_RESERVATION_NO_REARM',
            'Exact one-use permit schema required')
    require(permit['base_helper'] == base_pin, 'Permit selects another v1 helper')
    manifest = base.read_manifest(permit['base_manifest']['path'], permit['base_manifest']['sha256'])
    base.read_bytes_pin(permit['base_manifest'])
    census = base.strict_json(base.read_bytes_pin(manifest['role_census']))
    policy = base.strict_json(base.read_bytes_pin(census['supervision_policy']))
    require(permit['supervisor_owner'] == policy['fleet']
            and permit['supervisor_process'] == census['actual_snapshot']['owners']['fleet']['process'],
            'Permit supervisor differs from original census')
    require(permit['prior_actor'] == census['actual_snapshot']['actors']['163'],
            'Permit prior actor differs from original census')
    require(permit['collector_source']['sha256'] == COLLECTOR_SHA,
            'Exact original process/owner collector required')
    raw = base.read_bytes_pin(permit['collector_source'])
    collector = module_bytes('_role_bound_fuse_collector', permit['collector_source']['path'], raw)
    directory = permit['claim_directory']
    require(type(directory) is dict and set(directory) == {'path', 'identity'}
            and type(directory['path']) is str and Path(directory['path']).is_absolute()
            and set(directory['identity']) == {'device', 'inode', 'mode', 'uid'}
            and directory['identity']['mode'] == '0o700'
            and directory['identity']['uid'] == os.getuid(), 'Exact private claim directory required')
    return permit, manifest, collector, pin


def process_birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def verify_parent(permit, collector):
    owner = permit['supervisor_owner']
    require(os.getppid() == owner['pid'], 'Launcher is not a direct child of original supervisor')
    observed = collector.unit_observation(owner)
    collector.validate_owner(owner, observed)
    require(observed['process'] == permit['supervisor_process']
            and os.getppid() == owner['pid'], 'Original supervisor configuration/birth changed')
    prior = permit['prior_actor']
    require(process_birth(prior['pid']) != prior['starttime_ticks'],
            'Original selected actor still lives; duplicate launch forbidden')
    return dict(pid=owner['pid'], starttime_ticks=owner['starttime_ticks'],
                invocation_id=owner['invocation_id'], cgroup=owner['cgroup'],
                direct_parent_verified=True, prior_actor_birth_absent=True)


def directory_identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid)


def reserve_once(permit, permit_pin, command, observed_parent):
    """One kernel O_EXCL claim; never delete/rearm, even after a partial write."""
    directory = permit['claim_directory']
    path = Path(directory['path'])
    require(path.resolve(strict=True) == path, 'Claim directory symlink forbidden')
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        require(directory_identity(os.fstat(descriptor)) == directory['identity'],
                'Claim directory ownership/identity changed')
        try:
            fd = os.open(CLAIM_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o444, dir_fd=descriptor)
        except FileExistsError:
            raise ValueError('SLOT163_PERMIT_ALREADY_CONSUMED_NO_ADDITIONAL_MAME_EXEC') from None
        # From the successful open onward the permit is consumed, including
        # interruption, fsync failure, later owner failure, and exec failure.
        with os.fdopen(fd, 'wb') as stream:
            raw = (json.dumps(dict(schema='robotron-slot163-exec-reservation-consumed-v1',
                    status='CONSUMED_RESERVATION_NOT_PROOF_OF_SUCCESSFUL_EXEC',
                    original_permit=permit_pin, manifest=permit['base_manifest'],
                    slot=163, claimant_pid=os.getpid(), claimant_birth=process_birth(os.getpid()),
                    observed_parent=observed_parent, command=command,
                    reserved_monotonic_ns=time.monotonic_ns(), reserved_unix_ns=time.time_ns(),
                    additional_exec_attempts_allowed=False), sort_keys=True) + '\n').encode()
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def dispatch(permit, permit_pin, command, environment, parent_check, exec_function=None):
    """CLI supplies real owner verification and execve; CPU tests inject probes."""
    selected = environment['ROBOTRON_CLIENT_SLOT'] == '163'
    if selected:
        observed = parent_check()
        reserve_once(permit, permit_pin, command, observed)
        parent_check()  # Changes after consumption fail without rearming.
    (os.execve if exec_function is None else exec_function)(command[0], command, environment)
    raise AssertionError('execve returned without replacing the launcher')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--base-helper', required=True)
    parser.add_argument('--permit', required=True)
    parser.add_argument('--permit-sha256', required=True)
    parser.add_argument('--expected-source-sha256', required=True)
    parser.add_argument('mame_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    source = Path(__file__)
    require(source.resolve(strict=True) == source and stat.S_IMODE(source.lstat().st_mode) == 0o444
            and hashlib.sha256(source.read_bytes()).hexdigest() == args.expected_source_sha256,
            'Exact frozen fuse source required')
    base, base_pin = load_base(args.base_helper)
    permit, manifest, collector, permit_pin = read_permit(base, args.permit, args.permit_sha256, base_pin)
    require(args.mame_args and args.mame_args[0] == '--', 'Literal argv boundary required')
    command, environment = base.prepare_launch(manifest, args.mame_args[1:], dict(os.environ))
    if args.execute:
        dispatch(permit, permit_pin, command, environment, lambda: verify_parent(permit, collector))
    else:
        print(json.dumps(dict(status='CHECK_ONLY_NO_CLAIM_NO_EXEC', slot=int(environment['ROBOTRON_CLIENT_SLOT']))))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        print('ROLE_BOUND_ONE_USE_REFUSED: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        raise SystemExit(2)
