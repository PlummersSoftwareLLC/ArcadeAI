#!/usr/bin/env python3
"""Default-dry-run, explicitly launched private whole-agent CUDA smoke.

The parent imports only the standard library. A launched worker cannot import
numerical modules until its private paths, source identities, resource cgroup,
process identity and GPU/quality guards pass. This does not authorize a launch.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]
REPO = GAME.parent
GPU0_UUID = 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
MAIN_GPU_UUID = 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'
PATCH_SHA256 = '31dd8553f505f383c21b3df5631efb5a8064dab73c4503b30176940f15f70717'
GIB = 1 << 30
MIB = 1 << 20
BOUNDS = dict(cpu_threads=2, memory_bytes=12*GIB, vram_allocator_bytes=10*GIB,
              vram_process_bytes=11*GIB, artifact_bytes=4*GIB, tmpfs_bytes=128*MIB,
              tasks=96, total_timeout_s=300, phase_timeout_s=140)
QUALITY_NAMES = {'run_quality_campaign.py', 'run_frozen_sidecar.py', 'frozen_main.py',
                 'parallel_state_fill_trial.py', 'smoke_agent_cuda_graphs.py',
                 'inference_worker_affinity.py', 'cpu_affinity_pilot.py'}
HANDLED_SIGNALS = (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)


class SmokeInterrupted(RuntimeError):
    pass


@contextmanager
def installed_signal_handlers():
    previous={number:signal.getsignal(number) for number in HANDLED_SIGNALS}
    def interrupted(number,frame):
        raise SmokeInterrupted('Smoke interrupted by '+signal.Signals(number).name)
    for number in HANDLED_SIGNALS:signal.signal(number,interrupted)
    try:
        yield
    finally:
        for number,handler in previous.items():signal.signal(number,handler)


@contextmanager
def blocked_handled_signals():
    previous=signal.pthread_sigmask(signal.SIG_BLOCK,HANDLED_SIGNALS)
    try:
        yield
    finally:
        # Pending handled signals run only after the protected cleanup finished.
        signal.pthread_sigmask(signal.SIG_SETMASK,previous)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(pid=None, proc_root=Path('/proc')):
    pid = os.getpid() if pid is None else int(pid)
    fields = (Path(proc_root)/str(pid)/'stat').read_text().rsplit(') ', 1)[1].split()
    return dict(pid=pid, start_ticks=fields[19], ppid=int(fields[1]), pgid=int(fields[2]))


def regular(path):
    value = Path(path).lstat()
    if not stat.S_ISREG(value.st_mode):
        raise ValueError('Expected regular nonsymlink file: '+str(path))
    return value


def directory_identity(path):
    value = Path(path).lstat()
    if not stat.S_ISDIR(value.st_mode):
        raise ValueError('Expected nonsymlink directory: '+str(path))
    return dict(device=value.st_dev, inode=value.st_ino)


def check_directory(path, expected):
    if directory_identity(path) != expected:
        raise RuntimeError('Owned directory identity changed: '+str(path))


def json_exclusive(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def validate_output(path, *, logs_root=None):
    path = Path(path)
    logs_root = GAME/'logs' if logs_root is None else Path(logs_root)
    if not path.is_absolute() or path != path.resolve() or path.exists():
        raise ValueError('Output must be a new absolute nonsymlink path')
    if not path.is_relative_to(logs_root.resolve()) or path == logs_root.resolve():
        raise ValueError('Output must be a new child of Robotron/logs')
    for parent in path.parents:
        if parent.exists() and parent.is_symlink():
            raise ValueError('Output ancestor is a symlink')
    if not path.parent.is_dir():
        raise ValueError('Output parent must already exist')
    return path


@dataclass(frozen=True)
class Layout:
    output: Path
    nonce: str
    tmpfs_parent: Path = Path('/dev/shm')

    @property
    def tmpfs(self):
        return self.tmpfs_parent/('robotron-snapshot-smoke-'+self.nonce)

    @property
    def scripts(self):
        return self.output/'private/Robotron/Scripts'

    def phase(self, phase):
        if phase not in ('capture', 'restore'):
            raise ValueError('Invalid smoke phase')
        root = self.output/phase
        return dict(root=root, models=root/'models', control=root/'control.json',
                    journal=root/'journal', tmpfs=self.tmpfs/phase, cache=root/'cache')


def source_manifest():
    metadata = json.loads((HERE/'proposal-manifest.json').read_text())
    if digest(HERE/'coherent-snapshot.patch') != PATCH_SHA256:
        raise RuntimeError('Snapshot patch differs from the reviewed immutable patch')
    source = GAME/'Scripts/dqn'
    files = {}
    for path in sorted(source.iterdir()):
        if path.suffix == '.py' or path.name == 'sumtree.c':
            regular(path)
            files[path.name] = dict(source=str(path), sha256=digest(path))
    for relative, item in metadata['source_files'].items():
        base = REPO/relative
        if item['base_sha256'] is None:
            if base.exists():
                raise RuntimeError('New proposal module now exists in production')
        elif digest(base) != item['base_sha256']:
            raise RuntimeError('Production proposal base changed: '+relative)
        candidate = HERE/'staged'/relative
        regular(candidate)
        if digest(candidate) != item['proposed_sha256']:
            raise RuntimeError('Staged proposal differs from reviewed manifest: '+relative)
        files[candidate.name] = dict(source=str(candidate), sha256=digest(candidate))
    return files


def describe_plan(output):
    output = validate_output(output)
    files = source_manifest()
    return dict(status='DRY_RUN_ONLY', launch=False, output=str(output),
                gpu_uuid=GPU0_UUID, forbidden_gpu_uuid=MAIN_GPU_UUID, bounds=BOUNDS,
                numerical_imports=False, live_guards='Not queried in dry run',
                source_patch_sha256=PATCH_SHA256, source_files=files,
                phases=['private actual-agent capture', 'fresh-process private restore and next update'],
                state_size=11128, capacity=128, batch_size=8,
                exclusions=['No production model/replay/control/settings reads', 'No MAME or dashboard',
                            'No compiled/graph or parallel replay proposal', 'No playing-performance claim'])


def scan_quality_processes(*, proc_root=Path('/proc'), allowed_pids=()):
    blocked = []
    allowed = set(allowed_pids)
    for entry in Path(proc_root).iterdir():
        if not entry.name.isdigit() or int(entry.name) in allowed:
            continue
        try:
            raw = (entry/'cmdline').read_bytes()
            words = [part.decode(errors='replace') for part in raw.split(b'\0') if part]
            names = [Path(word).name for word in words]
            if any(name in QUALITY_NAMES or name.startswith('benchmark_') or
                   word.rsplit('.',1)[-1]+'.py' in QUALITY_NAMES or
                   word.rsplit('.',1)[-1].startswith('benchmark_') for name, word in zip(names, words)):
                blocked.append(dict(identity=identity(int(entry.name), proc_root), command=words))
        except FileNotFoundError:
            continue  # Process exited during the read.
        except PermissionError as error:
            raise RuntimeError('Cannot establish process ownership: '+entry.name) from error
    return blocked


def listening_9999(*, proc_net=Path('/proc/net')):
    for name in ('tcp', 'tcp6'):
        rows = (Path(proc_net)/name).read_text().splitlines()[1:]
        for line in rows:
            fields = line.split()
            if len(fields) < 4:
                raise RuntimeError('Malformed kernel socket table')
            if fields[3] == '0A' and int(fields[1].rsplit(':', 1)[1], 16) == 9999:
                return True
    return False


def parse_compute_apps(text):
    result = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = [part.strip() for part in line.split(',')]
        if len(fields) != 3 or not fields[0].isdigit() or not fields[1].startswith('GPU-'):
            raise RuntimeError('Malformed NVIDIA compute-owner query')
        used = None if fields[2] in ('N/A', '[N/A]', 'Not Supported', '[Not Supported]') else int(fields[2])*MIB
        result.append(dict(pid=int(fields[0]), gpu_uuid=fields[1], bytes=used))
    return result


def query_nvidia():
    common = ['--format=csv,noheader,nounits']
    gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=uuid,memory.free,memory.total', *common],
                                  text=True, timeout=5)
    apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_gpu_memory', *common],
                                   text=True, timeout=5)
    devices = {}
    for line in gpu.splitlines():
        values = [item.strip() for item in line.split(',')]
        if len(values) != 3 or not values[1].isdigit() or not values[2].isdigit():
            raise RuntimeError('Malformed NVIDIA device query')
        devices[values[0]] = dict(free_bytes=int(values[1])*MIB, total_bytes=int(values[2])*MIB)
    return dict(devices=devices, apps=parse_compute_apps(apps))


def guard_live_resources(*, allowed_pids=(), expected_main=None, initial=False,
                         query=None, proc_scan=None, port_check=None):
    query = query_nvidia if query is None else query
    proc_scan = scan_quality_processes if proc_scan is None else proc_scan
    port_check = listening_9999 if port_check is None else port_check
    if proc_scan(allowed_pids=allowed_pids):
        raise RuntimeError('Quality/sidecar/performance process is still present')
    if port_check():
        raise RuntimeError('Quality port 9999 is listening')
    value = query()
    if GPU0_UUID not in value['devices'] or MAIN_GPU_UUID not in value['devices']:
        raise RuntimeError('Approved display/main GPU identities are unavailable')
    for row in value['apps']:
        if row['gpu_uuid'] == GPU0_UUID:
            if row['pid'] not in allowed_pids:
                raise RuntimeError('Display GPU0 has another compute owner')
            if row['bytes'] is not None and row['bytes'] > BOUNDS['vram_process_bytes']:
                raise RuntimeError('Owned smoke exceeded its display-GPU memory budget')
    main = sorted(row['pid'] for row in value['apps'] if row['gpu_uuid'] == MAIN_GPU_UUID)
    main_identity = [identity(pid) for pid in main]
    if len(main_identity) != 1:
        raise RuntimeError('Require exactly one existing main-training GPU owner')
    if expected_main is not None and main_identity != expected_main:
        raise RuntimeError('Main training GPU process identity changed')
    if initial and value['devices'][GPU0_UUID]['free_bytes'] < 12*GIB:
        raise RuntimeError('Display GPU0 lacks the required free memory margin')
    return dict(main_owners=main_identity, gpu=value)


def configure_environment(layout, phase):
    paths = layout.phase(phase)
    # Deliberately exclude inherited DQN/ROBOTRON/PYTHONPATH/preload/visible GPU knobs.
    environment = {name:os.environ[name] for name in ('PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'TZ')
                   if name in os.environ}
    environment.update(CUDA_VISIBLE_DEVICES=GPU0_UUID, ROBOTRON_TRAIN_GPU='0', ROBOTRON_INFERENCE_GPU='0',
        ROBOTRON_DQN_MODEL_DIR=str(paths['models']), ROBOTRON_DQN_CONTROL_PATH=str(paths['control']),
        ROBOTRON_RUN_DIR=str(paths['journal']), OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
        OPENBLAS_NUM_THREADS='2', TORCHINDUCTOR_COMPILE_THREADS='2', PYTHONNOUSERSITE='1',
        DQN_FRAME_STACK='4', DQN_BATCH_SIZE='8', DQN_FUSED_ADAM='1', DQN_REPLAY_PREFETCH='1',
        DQN_TORCH_COMPILE='0', DQN_FULL_LOSS_COMPILE='0', DQN_EXACT_INFERENCE_GRAPHS='0',
        DQN_PARALLEL_STATE_FILL='0', DQN_COHERENT_SNAPSHOT='1', DQN_C51_TARGET_SMOOTHING='0',
        DQN_N_STEP='3', DQN_MAX_SAMPLES_PER_FRAME='8', DQN_NATIVE_BATCH_UPDATE='0',
        DQN_LEARNING_EXPOSURE_COUNTERS='1')
    for name, subdir in dict(TORCHINDUCTOR_CACHE_DIR='inductor', TRITON_CACHE_DIR='triton',
            CUDA_CACHE_PATH='cuda', TORCH_HOME='torch', TORCH_EXTENSIONS_DIR='extensions', TMPDIR='tmp').items():
        environment[name] = str(paths['cache']/subdir)
    return environment


def prepare_private_sources(layout, files):
    target = layout.scripts/'dqn'
    target.mkdir(parents=True, mode=0o700)
    for name, record in files.items():
        source = Path(record['source'])
        regular(source)
        if digest(source) != record['sha256']:
            raise RuntimeError('Source changed while preparing private package')
        with (target/name).open('xb') as output:
            output.write(source.read_bytes())
        if digest(target/name) != record['sha256']:
            raise RuntimeError('Private source copy failed verification')
        (target/name).chmod(0o444)


def cgroup_parent(*, proc_file=Path('/proc/self/cgroup'), mount=Path('/sys/fs/cgroup')):
    rows = Path(proc_file).read_text().splitlines()
    unified = [line.split(':', 2)[2] for line in rows if line.startswith('0::')]
    if len(unified) != 1:
        raise RuntimeError('A delegated cgroup v2 is required')
    current = Path(mount)/unified[0].lstrip('/')
    if current != current.resolve() or not current.is_dir():
        raise RuntimeError('Invalid cgroup parent')
    parent=current.parent
    if (current.name!='snapshot-supervisor' or not parent.name.startswith('robotron-snapshot-smoke-')
            or not parent.name.endswith('.service')):
        raise RuntimeError('Launch from a dedicated delegated service with DelegateSubgroup=snapshot-supervisor; session cgroups are forbidden')
    if parent.stat().st_uid!=os.getuid() or (parent/'cgroup.procs').read_text().split():
        raise RuntimeError('Delegated service root must be owned and empty of processes')
    if not os.access(parent, os.W_OK | os.X_OK):
        raise RuntimeError('Current cgroup is not delegated; no unbounded fallback')
    required={'cpu','memory','pids'}
    if not required<=set((parent/'cgroup.controllers').read_text().split()):
        raise RuntimeError('Dedicated service lacks required delegated controllers')
    if not os.access(parent/'cgroup.subtree_control',os.W_OK):
        raise RuntimeError('Dedicated subtree controller is not writable')
    return parent


class OwnedCgroup:
    def __init__(self, parent, nonce):
        parent=Path(parent)
        if parent!=cgroup_parent():
            raise RuntimeError('Cgroup creation is outside the verified dedicated service')
        # Only the verified, empty dedicated service root may be modified. The
        # launcher remains in snapshot-supervisor and workers become siblings.
        if (parent/'cgroup.procs').read_text().split():
            raise RuntimeError('Delegated root gained an internal process')
        required={'cpu','memory','pids'}
        enabled=set((parent/'cgroup.subtree_control').read_text().split())
        if not required<=enabled:
            (parent/'cgroup.subtree_control').write_text(' '.join('+'+name for name in sorted(required-enabled)))
        self.path = Path(parent)/('robotron-snapshot-smoke-'+nonce)
        self.path.mkdir(mode=0o700)
        self.identity = directory_identity(self.path)
        try:
            for name, value in {'memory.max':BOUNDS['memory_bytes'], 'memory.swap.max':0,
                    'memory.oom.group':1, 'pids.max':BOUNDS['tasks'], 'cpu.max':'200000 100000'}.items():
                file = self.path/name
                if not file.exists():
                    raise RuntimeError('Required cgroup controller is not delegated: '+name)
                file.write_text(str(value))
        except BaseException:
            self.path.rmdir()
            raise

    def attach(self, pid):
        check_directory(self.path, self.identity)
        (self.path/'cgroup.procs').write_text(str(pid))

    def members(self):
        check_directory(self.path, self.identity)
        return [int(pid) for pid in (self.path/'cgroup.procs').read_text().split()]

    def close(self):
        if self.members():
            raise RuntimeError('Owned cgroup still contains processes; recovery required')
        self.path.rmdir()


def byte_count(root):
    total = 0
    for path in Path(root).rglob('*'):
        value = path.lstat()
        if stat.S_ISLNK(value.st_mode):
            raise RuntimeError('Unexpected symlink in owned artifacts: '+str(path))
        if stat.S_ISREG(value.st_mode):
            total += value.st_size
    return total


def verify_source_copies(layout, files):
    for name, record in files.items():
        if digest(layout.scripts/'dqn'/name) != record['sha256']:
            raise RuntimeError('Private source changed during smoke: '+name)


def terminate_owned(process, process_identity, cgroup, *, grace_s=5):
    # The group leader identity must still match before a group signal. If it
    # has exited, only the unique cgroup may identify surviving descendants.
    try:
        now = identity(process.pid)
    except FileNotFoundError:
        now = None
    if now is not None:
        if now != process_identity or now['pgid'] != process.pid:
            raise RuntimeError('Child identity changed; refusing process-group signal')
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        pass
    members = cgroup.members()
    if members:
        # All members must retain this launch's dedicated process-group ID.
        for pid in members:
            try:
                if identity(pid)['pgid'] != process.pid:
                    raise RuntimeError('Unexpected process in smoke cgroup; refusing kill')
            except FileNotFoundError:
                continue
        kill = cgroup.path/'cgroup.kill'
        if not kill.is_file():
            raise RuntimeError('Owned cgroup.kill unavailable; recovery required')
        kill.write_text('1')
    process.wait(timeout=5)
    deadline = time.monotonic()+5
    while cgroup.members():
        if time.monotonic() >= deadline:
            raise RuntimeError('Owned child group did not exit; recovery required')
        time.sleep(.05)


def worker_command(manifest, phase):
    if phase not in ('capture', 'restore'):
        raise ValueError('Invalid phase')
    return [sys.executable, '-I', '-B', str(HERE/'whole_agent_smoke_worker.py'),
            '--manifest', str(manifest), '--phase', phase]


def prepare_restore(layout, archive):
    paths = layout.phase('restore')
    shutil.copyfile(archive/'model.pt', paths['models']/'robotron_dqn_latest.pt')
    shutil.copytree(archive/'ring', paths['tmpfs']/'robotron_dqn_latest_replay')
    for bank in ('hof', 'ephof'):
        shutil.copytree(archive/'banks'/bank, paths['models']/('robotron_dqn_latest_replay_'+bank))
    shutil.copyfile(archive/'learning_control.json', paths['control'])
    shutil.copyfile(archive/'game_settings.json', paths['models']/'game_settings.json')


def run_phase(layout, manifest_path, phase, cgroup, expected_main, overall_deadline):
    paths = layout.phase(phase)
    environment = configure_environment(layout, phase)
    phase_limit = min(overall_deadline, time.monotonic()+BOUNDS['phase_timeout_s'])
    with (paths['root']/'worker.log').open('xb') as log:
        process = owned = None
        try:
            with blocked_handled_signals():
                process = subprocess.Popen(worker_command(manifest_path, phase), cwd=layout.output/'private',
                    env=environment, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
                owned = identity(process.pid)
                cgroup.attach(process.pid)
                if owned['pgid'] != process.pid:
                    raise RuntimeError('Worker process group was not isolated')
            guard_live_resources(allowed_pids={os.getpid(), process.pid}, expected_main=expected_main)
            manifest = json.loads(manifest_path.read_text())
            process.stdin.write((manifest['launch_token']+'\n').encode())
            process.stdin.close()
            next_guard = 0.
            while process.poll() is None:
                if time.monotonic() >= phase_limit:
                    raise TimeoutError('Owned smoke phase exceeded its deadline')
                if byte_count(layout.output)>BOUNDS['artifact_bytes'] or byte_count(layout.tmpfs)>BOUNDS['tmpfs_bytes']:
                    raise RuntimeError('Owned smoke storage budget exceeded')
                if time.monotonic() >= next_guard:
                    guard_live_resources(allowed_pids={os.getpid(), process.pid}, expected_main=expected_main)
                    next_guard=time.monotonic()+1
                time.sleep(.1)
            if process.returncode:
                raise RuntimeError('Owned '+phase+' worker failed; see '+str(paths['root']/'worker.log'))
            if cgroup.members():
                raise RuntimeError('Worker left surviving descendants')
        finally:
            with blocked_handled_signals():
                try:
                    if process is not None:
                        if owned is None:
                            # No token was released. This still-unreaped Popen
                            # child cannot have its PID reused; close its token
                            # pipe, terminate that exact child and reap it.
                            if process.stdin and not process.stdin.closed:process.stdin.close()
                            if process.poll() is None:process.terminate()
                            process.wait(timeout=5)
                        elif process.poll() is None or cgroup.members():
                            terminate_owned(process, owned, cgroup)
                finally:
                    if process is not None and process.stdin and not process.stdin.closed:
                        process.stdin.close()
    result = json.loads((paths['root']/'phase-result.json').read_text())
    if result.get('status') != 'PASS':
        raise RuntimeError('Worker did not certify its phase')
    return result


def _launch_guarded(output):
    if any(name in sys.modules for name in ('numpy', 'torch', 'dqn')):
        raise RuntimeError('Launch requires a fresh standard-library-only parent')
    output = validate_output(output)
    files = source_manifest()
    initial = guard_live_resources(allowed_pids={os.getpid()}, initial=True)
    mem = dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    if int(mem['MemAvailable'].split()[0])*1024 < 16*GIB:
        raise RuntimeError('Host RAM free margin is insufficient')
    if shutil.disk_usage(output.parent).free < 8*GIB or shutil.disk_usage('/dev/shm').free < 256*MIB:
        raise RuntimeError('Private artifact/tmpfs free margin is insufficient')
    delegated = cgroup_parent()  # No unbounded fallback.
    nonce = uuid.uuid4().hex
    layout = Layout(output, nonce)
    if layout.tmpfs.exists():
        raise RuntimeError('Private tmpfs nonce already exists')
    lease_path = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
    descriptor = os.open(lease_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    lease = os.fdopen(descriptor, 'r+')
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        lease.close()
        raise
    cgroup = None
    root_identity = tmp_identity = None
    result = None
    try:
        guard_live_resources(allowed_pids={os.getpid()}, expected_main=initial['main_owners'], initial=True)
        output.mkdir(mode=0o700)
        root_identity = directory_identity(output)
        layout.tmpfs.mkdir(mode=0o700)
        tmp_identity = directory_identity(layout.tmpfs)
        json_exclusive(output/'ownership.json', dict(nonce=nonce, parent=identity(), output=root_identity, tmpfs=tmp_identity))
        json_exclusive(layout.tmpfs/'ownership.json', dict(nonce=nonce, parent=identity()))
        prepare_private_sources(layout, files)
        for phase in ('capture','restore'):
            paths=layout.phase(phase)
            for key in ('root','models','journal','tmpfs','cache'):
                paths[key].mkdir(parents=True,exist_ok=True,mode=0o700)
            for subdir in ('inductor','triton','cuda','torch','extensions','tmp'):
                (paths['cache']/subdir).mkdir(mode=0o700)
        json_exclusive(layout.phase('capture')['control'], dict(experiment='isolated-snapshot-smoke',lr_scale=.5))
        cgroup=OwnedCgroup(delegated,nonce)
        manifest=dict(schema='robotron-private-whole-agent-smoke-v1',explicit_launch=True,
            launch_token=uuid.uuid4().hex,nonce=nonce,parent=identity(),output=str(output),
            output_identity=root_identity,tmpfs=str(layout.tmpfs),tmpfs_identity=tmp_identity,
            cgroup=str(cgroup.path),cgroup_identity=cgroup.identity,main_owners=initial['main_owners'],
            gpu_uuid=GPU0_UUID,forbidden_gpu_uuid=MAIN_GPU_UUID,bounds=BOUNDS,sources=files,
            worker_sha256=digest(HERE/'whole_agent_smoke_worker.py'),launcher_sha256=digest(__file__))
        manifest_path=output/'launch-manifest.json'
        json_exclusive(manifest_path,manifest)
        deadline=time.monotonic()+BOUNDS['total_timeout_s']
        capture=run_phase(layout,manifest_path,'capture',cgroup,initial['main_owners'],deadline)
        archive=Path(capture['archive'])
        if (not archive.is_absolute() or archive!=archive.resolve() or
                not archive.is_relative_to(layout.phase('capture')['models']/'coherent-snapshots')):
            raise RuntimeError('Capture returned an unowned archive path')
        prepare_restore(layout,archive)
        restored=run_phase(layout,manifest_path,'restore',cgroup,initial['main_owners'],deadline)
        verify_source_copies(layout,files)
        guard_live_resources(allowed_pids={os.getpid()},expected_main=initial['main_owners'])
        result=dict(status='PASS',schema=manifest['schema'],gpu_uuid=GPU0_UUID,capture=capture,restore=restored,
            limitations=['Synthetic private data only; no MAME frame/game lifecycle','No full-size archive or disk-pressure validation',
                        'No compiled/graph or combined parallel-replay coverage','No deterministic RNG or playing-performance claim'],
            cgroup_enforced=True,storage_bound='Fixed tiny geometry plus cooperative byte watcher; no filesystem quota')
    except BaseException as error:
        if root_identity is not None:
            check_directory(output,root_identity)
            json_exclusive(output/'failure.json',dict(status='FAIL',error=repr(error)))
        raise
    finally:
        with blocked_handled_signals():
            cleanup_errors=[]
            if cgroup is not None:
                try:
                    cgroup.close()
                except BaseException as error:
                    cleanup_errors.append('cgroup: '+repr(error))
            if tmp_identity is not None and not cleanup_errors:
                try:
                    check_directory(layout.tmpfs,tmp_identity)
                    if json.loads((layout.tmpfs/'ownership.json').read_text())['nonce'] != nonce:
                        raise RuntimeError('Private tmpfs ownership marker changed; refusing cleanup')
                    shutil.rmtree(layout.tmpfs)
                except BaseException as error:
                    cleanup_errors.append('tmpfs: '+repr(error))
            lease.close()
            if cleanup_errors:
                if root_identity is not None:
                    check_directory(output,root_identity)
                    json_exclusive(output/'cleanup-failure.json',dict(status='FAIL',recovery_required=True,errors=cleanup_errors))
                raise RuntimeError('Owned cleanup needs recovery: '+'; '.join(cleanup_errors))
    # Publish aggregate success after process/cgroup/tmpfs cleanup, retain artifacts.
    json_exclusive(output/'result.json',result)
    return result


def launch(output):
    # Install before any launched mutation and retain through all owned cleanup.
    with installed_signal_handlers():
        try:
            return _launch_guarded(output)
        except SmokeInterrupted as error:
            output=Path(output)
            marker=output/'ownership.json'
            if marker.is_file() and not marker.is_symlink():
                ownership=json.loads(marker.read_text())
                if ownership.get('parent')==identity():
                    check_directory(output,ownership['output'])
                    if not (output/'interrupted.json').exists():
                        json_exclusive(output/'interrupted.json',dict(status='FAIL',interrupted=repr(error)))
            raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--launch',action='store_true')
    args=parser.parse_args(argv)
    value=launch(args.directory) if args.launch else describe_plan(args.directory)
    print(json.dumps(value,indent=2,allow_nan=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
