#!/usr/bin/env python3
"""SOURCE-ONLY prepared GPU0 CE trace parity parent; never auto-launches.

Default prints a literal plan without helper/source/data reads or live queries.
Future --launch requires a separately reviewed exclusive resource window and a
dedicated delegated robotron-snapshot-smoke-*.service. It does not train the
live agent, alter its sources or repair failed observations.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import uuid


HERE = Path(__file__).parent
GAME = HERE.parents[2]
REPO = GAME.parent
SCHEMA = 'robotron-cuda-executed-ce-trace-validation-v1'
SEED = 20261017
VARIANTS = ('base', 'off', 'on')
GIB, MIB = 1 << 30, 1 << 20
BOUNDS = dict(cpu_threads=2, memory_bytes=16*GIB, vram_allocator_bytes=12*GIB,
              vram_process_bytes=13*GIB, artifact_bytes=6*GIB, tmpfs_bytes=128*MIB,
              tasks=128, phase_timeout_s=180, total_timeout_s=600)
SOURCE_LOCK_SHA256 = 'd6ffdaae63d97bce24a18d1b11ed165b9e12484d17d65365415aab3c08beb13b'
LOCK_SHA = SOURCE_LOCK_SHA256
CHECKPOINT_SHA256 = '1225731cb8e976aacee925cb7bbac76a31ea6f81e404fedb5a909019a4373688'
CPU_RECEIPT_SHA256 = '0f1cf4820804971b7b13f02604a6d0f73e5579f34a68a45312d212d4a1a51068'
BLOCKED_NAMES = {
    'cuda_trace_parent.py', 'cuda_trace_worker.py', 'checkpoint_at_frame.py',
    'cpu_reservation_trial.py', 'forensic_parent.py', 'forensic_worker.py',
    'whole_agent_smoke.py', 'whole_agent_smoke_worker.py',
    'restore_serial_after_parallel_trial.py',
}
_BASE = None


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sync_directory(path):
    descriptor = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def checked_module(path, expected, name):
    """Execute only verified helper bytes, exclusively on the explicit path."""
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink()
            and path.is_file(), 'Pinned helper path is not a canonical regular file')
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == expected, 'Pinned helper bytes differ: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


def read_lock():
    path = HERE / 'source-lock.json'
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink(), 'Noncanonical source lock')
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == SOURCE_LOCK_SHA256, 'Reviewed source lock changed')
    lock = json.loads(data)
    require(lock['schema'] == SCHEMA and lock['seed'] == SEED and lock['variants'] == list(VARIANTS)
            and lock['attempts'] == 8 and lock['batch_rows'] == 4096
            and lock['state_width'] == 11128 and lock['joint_actions'] == 81 and lock['atoms'] == 51,
            'Fixed trace validation protocol changed')
    checkpoint = lock['checkpoint']
    require(checkpoint['sha256'] == CHECKPOINT_SHA256 and checkpoint['bytes'] == 275181008
            and checkpoint['receipt_sha256'] == CPU_RECEIPT_SHA256, 'Reviewed trained fixture changed')
    for group in ('immutable_helpers', 'source_files'):
        for name, item in lock[group].items():
            if group == 'source_files':
                require(name == Path(name).name and name not in ('', '.', '..'), 'Private source name escapes package')
            source = Path(item['source'])
            require(source.is_absolute() and source == source.resolve() and not source.is_symlink()
                    and source.is_file() and digest(source) == item['sha256'], 'Pinned source changed: ' + name)
    return lock


def helpers(lock):
    global _BASE
    launcher = lock['immutable_helpers']['launcher']
    worker = lock['immutable_helpers']['worker']
    base = checked_module(launcher['source'], launcher['sha256'], '_ce_trace_owned_launcher')
    old_worker = checked_module(worker['source'], worker['sha256'], '_ce_trace_lifetime_worker')
    # These reviewed FUNCTIONS are reused; no old source_manifest/launch/setup
    # or old snapshot numerical policy is called.
    base.GAME, base.REPO, base.BOUNDS = GAME, REPO, dict(BOUNDS)
    base.QUALITY_NAMES = set(base.QUALITY_NAMES) | BLOCKED_NAMES
    original_guard = base.guard_live_resources

    def resource_guard(**kwargs):
        result = original_guard(**kwargs)
        if kwargs.get('initial', False):
            require(result['gpu']['devices'][base.GPU0_UUID]['free_bytes'] >= 14*GIB,
                    'GPU0 requires at least14GiB free before numerical import')
        return result

    base.guard_live_resources = resource_guard
    _BASE = base
    return base, old_worker


@dataclass(frozen=True)
class Layout:
    output: Path
    nonce: str
    tmpfs_parent: Path = Path('/dev/shm')

    @property
    def tmpfs(self):
        return self.tmpfs_parent / ('robotron-snapshot-smoke-' + self.nonce)

    @property
    def scripts(self):
        return self.output / 'private/Robotron/Scripts'

    def phase(self, variant):
        require(variant in VARIANTS, 'Unknown fixed variant')
        root = self.output / variant
        return dict(root=root, models=root/'models', control=root/'control.json',
                    journal=root/'journal', tmpfs=self.tmpfs/variant, cache=root/'cache')


def configure_environment(layout, variant):
    require(_BASE is not None, 'Verified helper initialization is required')
    paths = layout.phase(variant)
    environment = _BASE.configure_environment(layout, variant)
    environment.update(DQN_BATCH_SIZE='4096', DQN_TORCH_COMPILE='1', DQN_FULL_LOSS_COMPILE='1',
                       DQN_COHERENT_SNAPSHOT='0', DQN_PER_PRIORITY_METRIC='ce',
                       DQN_NATIVE_BATCH_UPDATE='1', DQN_DIRECT_REPLAY_FILL='1',
                       DQN_COMPILE_MODE='default', DQN_DIAGNOSTIC_INTERVAL='20',
                       PYTHONDONTWRITEBYTECODE='1')
    # The inherited whitelist never carries a live observer path. OFF/base
    # keep this variable absent, and ON owns a NEW directory below its phase.
    environment.pop('DQN_EXECUTED_CE_TRACE_DIR', None)
    if variant == 'on':
        environment['DQN_EXECUTED_CE_TRACE_DIR'] = str(paths['root']/'ce-executed-trace-cuda-validation')
    return environment


def file_identity(value):
    return dict(device=value.st_dev, inode=value.st_ino, mode=stat.S_IMODE(value.st_mode),
                uid=value.st_uid, gid=value.st_gid, nlink=value.st_nlink,
                size=value.st_size, mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns)


def stable_file(path, expected_sha, expected_bytes=None, *, read_only=True):
    """Hash an owned source with identical FD/path before/after views.

    Model bytes always use the default readonly requirement. The historical
    CPU verifier JSON is an ordinary writable output; its exact pinned hash,
    mode and full identity are retained without changing the original file.
    """
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink(), 'Noncanonical readonly input')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1,
                'Input must be an owned single-link regular file')
        require(not read_only or not stat.S_IMODE(before.st_mode) & 0o222, 'Model input must be readonly')
        identity = file_identity(before)
        require(file_identity(path.lstat()) == identity, 'Input path/FD identity differs before read')
        observed = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(file_identity(os.fstat(stream.fileno())) == identity and file_identity(path.lstat()) == identity,
                'Input changed while fingerprinting')
    require(observed == expected_sha and (expected_bytes is None or identity['size'] == expected_bytes),
            'Input hash/size differs')
    return dict(path=str(path), sha256=observed, bytes=identity['size'], identity=identity)


def copy_fixture(lock, output, deadline):
    checkpoint = lock['checkpoint']
    receipt = stable_file(checkpoint['receipt'], CPU_RECEIPT_SHA256, read_only=False)
    source = Path(checkpoint['source'])
    source_record = stable_file(source, CHECKPOINT_SHA256, checkpoint['bytes'])
    target = output/'inputs/trained.pt'
    target.parent.mkdir(mode=0o700)
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream, target.open('xb') as copied:
        require(file_identity(os.fstat(stream.fileno())) == source_record['identity']
                and file_identity(source.lstat()) == source_record['identity'], 'Source changed before private copy')
        hasher = hashlib.sha256()
        while chunk := stream.read(MIB):
            require(time.monotonic() < deadline, 'Total deadline exceeded while copying trained fixture')
            copied.write(chunk)
            hasher.update(chunk)
        copied.flush()
        os.fsync(copied.fileno())
        require(hasher.hexdigest() == CHECKPOINT_SHA256 and copied.tell() == checkpoint['bytes'], 'Trained copy differs')
        require(file_identity(os.fstat(stream.fileno())) == source_record['identity']
                and file_identity(source.lstat()) == source_record['identity'], 'Source changed during private copy')
    target.chmod(0o444)
    with target.open('rb') as stream:
        os.fsync(stream.fileno())
    sync_directory(target.parent)
    copied_record = stable_file(target, CHECKPOINT_SHA256, checkpoint['bytes'])
    require((source_record['identity']['device'], source_record['identity']['inode']) !=
            (copied_record['identity']['device'], copied_record['identity']['inode']), 'Fixture copy is not independent')
    require(stable_file(checkpoint['receipt'], CPU_RECEIPT_SHA256, read_only=False) == receipt,
            'CPU verification provenance changed')
    return dict(source=source_record, copied=copied_record, cpu_verification=receipt)


def publish(base, path, value):
    base.json_exclusive(path, value)
    sync_directory(Path(path).parent)


def command(manifest_path, variant):
    return [sys.executable, '-Xgil=0', '-I', '-B', str(HERE/'cuda_trace_worker.py'),
            '--manifest', str(manifest_path), '--variant', variant]


def run_variant(base, layout, manifest_path, variant, cgroup, main, overall_deadline):
    paths = layout.phase(variant)
    deadline = min(overall_deadline, time.monotonic() + BOUNDS['phase_timeout_s'])
    process = owned = None
    token_released = False
    launched = time.monotonic()
    with (paths['root']/'worker.log').open('xb') as log:
        try:
            require(time.monotonic() < deadline, 'Fixed overall deadline reached before variant')
            with base.blocked_handled_signals():
                process = subprocess.Popen(command(manifest_path, variant), cwd=layout.output/'private',
                    env=configure_environment(layout, variant), stdin=subprocess.PIPE,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                owned = base.identity(process.pid)
                require(owned['pgid'] == process.pid, 'Worker process group is not isolated')
                cgroup.attach(process.pid)
            base.guard_live_resources(allowed_pids={os.getpid(), process.pid}, expected_main=main)
            manifest = json.loads(manifest_path.read_text())
            process.stdin.write((manifest['launch_token'] + '\n').encode())
            process.stdin.close()
            token_released = True
            next_guard = 0.0
            while process.poll() is None:
                require(time.monotonic() < deadline, 'Fixed variant/overall deadline exceeded')
                require(base.byte_count(layout.output) <= BOUNDS['artifact_bytes'] and
                        base.byte_count(layout.tmpfs) <= BOUNDS['tmpfs_bytes'], 'Owned storage bound exceeded')
                if time.monotonic() >= next_guard:
                    base.guard_live_resources(allowed_pids={os.getpid(), process.pid}, expected_main=main)
                    next_guard = time.monotonic() + 1
                time.sleep(.1)
            require(process.returncode == 0, 'Worker failed; original log/variant artifacts are retained')
            require(not cgroup.members(), 'Worker left surviving descendants')
        finally:
            # Handler lifetime encloses this block and outer cgroup/tmpfs undo.
            with base.blocked_handled_signals():
                try:
                    if process is not None:
                        if owned is None:
                            # Still-unreaped Popen child received no token, so
                            # its PID cannot have been reused by another owner.
                            if process.stdin and not process.stdin.closed:
                                process.stdin.close()
                            if process.poll() is None:
                                process.terminate()
                            process.wait(timeout=5)
                        elif process.poll() is None or cgroup.members():
                            base.terminate_owned(process, owned, cgroup)
                        else:
                            process.wait(timeout=5)
                finally:
                    if process is not None and process.stdin and not process.stdin.closed:
                        process.stdin.close()
                    if process is not None:
                        publish(base, paths['root']/'child-exit.json', dict(
                            variant=variant, owned_identity=owned, pid=process.pid,
                            actual_returncode=process.returncode, token_released=token_released,
                            elapsed_s=time.monotonic()-launched,
                            scope='Direct owned Popen result; parent service exit retained separately by root'))
    require(time.monotonic() <= overall_deadline, 'Overall deadline exceeded at variant completion')
    result = json.loads((paths['root']/'phase-result.json').read_text())
    expected = 'PARITY_COMPLETE' if variant == 'on' else 'VARIANT_COMPLETE'
    require(result.get('status') == expected and result.get('variant') == variant,
            'Variant did not certify its fixed scope/identity')
    return result


def launch(directory):
    require(not any(name.split('.')[0] in ('numpy', 'torch', 'dqn') for name in sys.modules),
            'Fresh stdlib-only parent is required')
    sys.dont_write_bytecode = True
    lock = read_lock()
    base, _ = helpers(lock)
    directory = base.validate_output(directory, logs_root=GAME/'logs')
    with base.installed_signal_handlers():
        overall_deadline = time.monotonic() + BOUNDS['total_timeout_s']
        initial = base.guard_live_resources(allowed_pids={os.getpid()}, initial=True)
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024 >= 20*GIB, 'Host RAM free margin insufficient')
        require(shutil.disk_usage(directory.parent).free >= 8*GIB and
                shutil.disk_usage('/dev/shm').free >= 256*MIB, 'Disk/tmpfs free margin insufficient')
        delegated = base.cgroup_parent()
        nonce = uuid.uuid4().hex
        layout = Layout(directory, nonce)
        require(not layout.tmpfs.exists(), 'Private tmpfs already exists')
        descriptor = os.open('/dev/shm/robotron-snapshot-smoke-gpu0.lock',
                             os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        lease = os.fdopen(descriptor, 'r+')
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            lease.close()
            raise
        cgroup = root_identity = tmp_identity = None
        results = []
        try:
            base.guard_live_resources(allowed_pids={os.getpid()}, expected_main=initial['main_owners'], initial=True)
            directory.mkdir(mode=0o700)
            root_identity = base.directory_identity(directory)
            layout.tmpfs.mkdir(mode=0o700)
            tmp_identity = base.directory_identity(layout.tmpfs)
            publish(base, directory/'ownership.json', dict(nonce=nonce, parent=base.identity(),
                    output=root_identity, tmpfs=tmp_identity))
            publish(base, layout.tmpfs/'ownership.json', dict(nonce=nonce, parent=base.identity()))
            base.prepare_private_sources(layout, lock['source_files'])
            fixture = copy_fixture(lock, directory, overall_deadline)
            for variant in VARIANTS:
                paths = layout.phase(variant)
                for name in ('root', 'models', 'journal', 'tmpfs', 'cache'):
                    paths[name].mkdir(parents=True, mode=0o700)
                for name in ('inductor', 'triton', 'cuda', 'torch', 'extensions', 'tmp'):
                    (paths['cache']/name).mkdir(mode=0o700)
                publish(base, paths['control'], dict(experiment='isolated-cuda-ce-trace-validation', lr_scale=.5))
            cgroup = base.OwnedCgroup(delegated, nonce)
            manifest = dict(schema=SCHEMA, explicit_launch=True, seed=SEED, variants=list(VARIANTS),
                attempts=8, source_lock_sha256=SOURCE_LOCK_SHA256,
                parent_sha256=digest(__file__), worker_sha256=digest(HERE/'cuda_trace_worker.py'),
                launch_token=uuid.uuid4().hex, nonce=nonce, parent=base.identity(), output=str(directory),
                output_identity=root_identity, tmpfs=str(layout.tmpfs), tmpfs_identity=tmp_identity,
                cgroup=str(cgroup.path), cgroup_identity=cgroup.identity, main_owners=initial['main_owners'],
                gpu_uuid=base.GPU0_UUID, forbidden_gpu_uuid=base.MAIN_GPU_UUID,
                bounds=dict(BOUNDS), sources=lock['source_files'], trained_fixture=fixture,
                numerical_protocol=lock, service_exit_provenance='Root must retain original invocation and terminal fields before owned unit release')
            path = directory/'launch-manifest.json'
            publish(base, path, manifest)
            manifest_sha = digest(path)
            for variant in VARIANTS:
                require(time.monotonic() < overall_deadline, 'Fixed total deadline reached')
                require(digest(path) == manifest_sha and read_lock() == lock, 'Immutable launch protocol changed')
                base.verify_source_copies(layout, lock['source_files'])
                base.guard_live_resources(allowed_pids={os.getpid()}, expected_main=initial['main_owners'], initial=True)
                results.append(run_variant(base, layout, path, variant, cgroup,
                                           initial['main_owners'], overall_deadline))
            require(base.byte_count(layout.output) <= BOUNDS['artifact_bytes'] and
                    base.byte_count(layout.tmpfs) <= BOUNDS['tmpfs_bytes'], 'Final storage bound exceeded')
            base.verify_source_copies(layout, lock['source_files'])
            require(read_lock() == lock and digest(path) == manifest_sha, 'Final immutable source/protocol changed')
            require(stable_file(fixture['source']['path'], CHECKPOINT_SHA256, 275181008) == fixture['source']
                    and stable_file(fixture['copied']['path'], CHECKPOINT_SHA256, 275181008) == fixture['copied']
                    and stable_file(fixture['cpu_verification']['path'], CPU_RECEIPT_SHA256, read_only=False) == fixture['cpu_verification'],
                    'Trained fixture/provenance changed')
            base.guard_live_resources(allowed_pids={os.getpid()}, expected_main=initial['main_owners'])
        except BaseException as error:
            if root_identity is not None:
                base.check_directory(directory, root_identity)
                publish(base, directory/'failure.json', dict(status='VALIDATION_ERROR', error=repr(error)))
            raise
        finally:
            with base.blocked_handled_signals():
                errors = []
                if cgroup is not None:
                    try:
                        cgroup.close()
                    except BaseException as error:
                        errors.append('cgroup: ' + repr(error))
                if tmp_identity is not None and not errors:
                    try:
                        base.check_directory(layout.tmpfs, tmp_identity)
                        require(json.loads((layout.tmpfs/'ownership.json').read_text())['nonce'] == nonce,
                                'Tmpfs ownership changed')
                        shutil.rmtree(layout.tmpfs)
                    except BaseException as error:
                        errors.append('tmpfs: ' + repr(error))
                lease.close()
                if errors:
                    publish(base, directory/'cleanup-failure.json', dict(
                        status='VALIDATION_ERROR', recovery_required=True, errors=errors))
                    raise RuntimeError('Owned cleanup requires recovery: ' + repr(errors))
        aggregate = dict(status='PARITY_COMPLETE', schema=SCHEMA, variants=results,
            source_lock_sha256=SOURCE_LOCK_SHA256, owned_cleanup_complete=True,
            limitations=['Fixed synthetic batch at trained checkpoint; no live replay-population or learning-quality claim',
                         'No actual live Rainbow agent/server lifecycle or throughput comparison',
                         'Storage watcher is cooperative, not a filesystem quota',
                         'Parent service original exit must be independently archived by root before release'])
        publish(base, directory/'result.json', aggregate)
        return aggregate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--launch', action='store_true')
    args = parser.parse_args(argv)
    if not args.launch:
        print(json.dumps(dict(status='PLAN_ONLY_UNEXECUTED', schema=SCHEMA, launch=False,
            variants=list(VARIANTS), batch_rows=4096, attempts=8, bounds=BOUNDS,
            source_lock_sha256=SOURCE_LOCK_SHA256, numerical_imports=False,
            runtime_queries=False, outputs_created=False, automatic_retry=False), indent=2))
        return 0
    require(args.directory is not None, 'Explicit launch requires a NEW absolute output directory')
    result = launch(args.directory)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
