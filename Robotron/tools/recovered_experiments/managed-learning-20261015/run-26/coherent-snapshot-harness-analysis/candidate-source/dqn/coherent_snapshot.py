"""Opt-in coherent persisted-start snapshots; no deterministic continuation claim.

This proposal is not installed in the trainer. Run capture on its main thread.
The frame gate parks Python handlers, not the MAME process or its RNG. A long
archive can exceed MAME's action deadline; both branches require fresh clients.
"""
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import threading
import time
import uuid


class SnapshotFrameGate:
    """Registered handler/accept workers park between complete frame mutations.

    Active workers never disappear between frames: close waits until each has
    flushed pending frame counters and parked, or has finished all cleanup.
    A public queue becoming empty is deliberately not part of this proof.
    """
    def __init__(self, enabled=False):
        self.enabled = bool(enabled)
        self._condition = threading.Condition()
        self._closed = False
        self._owner = None
        self._generation = 0
        self._workers = {}
        self._errors = []

    def register(self, name):
        if not self.enabled:
            return None
        with self._condition:
            while self._closed:
                self._condition.wait()
            token = object()
            self._workers[token] = dict(name=str(name), parked=False)
            return token

    def checkpoint(self, token, flush=lambda: None):
        if token is None or not self._closed:
            return
        with self._condition:
            state = self._workers[token]
            if self._closed:
                try:
                    flush()
                except BaseException as error:
                    self._errors.append(type(error).__name__ + ': ' + str(error))
                    self._condition.notify_all()
                    raise
                state['parked'] = True
                self._condition.notify_all()
                while self._closed:
                    self._condition.wait()
                state['parked'] = False

    def unregister(self, token):
        if token is None:
            return
        with self._condition:
            if token not in self._workers:
                raise RuntimeError('Unknown or already released frame worker')
            del self._workers[token]
            self._condition.notify_all()

    def close(self, owner, timeout):
        if not self.enabled:
            raise RuntimeError('Coherent snapshots were not explicitly enabled at startup')
        deadline = time.monotonic() + max(0., timeout)
        with self._condition:
            if self._owner is not None:
                raise RuntimeError('A snapshot gate already has an owner')
            self._owner, self._closed = owner, True
            self._generation += 1
            self._errors.clear()
            while any(not item['parked'] for item in self._workers.values()):
                if self._errors:
                    raise RuntimeError('Client boundary flush failed: ' + '; '.join(self._errors))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Client/accept workers did not reach the snapshot boundary')
                self._condition.wait(remaining)
            return self.proof(owner)

    def proof(self, owner):
        with self._condition:
            if self._owner != owner or not self._closed:
                raise RuntimeError('Snapshot gate ownership changed')
            if self._errors or any(not item['parked'] for item in self._workers.values()):
                raise RuntimeError('The client mutation boundary is not quiescent')
            return dict(generation=self._generation,
                        parked_workers=sorted(item['name'] for item in self._workers.values()),
                        active_workers=0, flush_errors=[])

    def open(self, owner):
        with self._condition:
            if self._owner != owner:
                raise RuntimeError('Refusing to release another snapshot owner')
            self._closed, self._owner = False, None
            self._condition.notify_all()

    def owned_by(self, owner):
        with self._condition:
            return self._owner == owner


def process_identity():
    # /proc stat's comm can contain spaces or parentheses; split after final ).
    fields = Path('/proc/self/stat').read_text().rsplit(') ', 1)[1].split()
    return dict(pid=os.getpid(), start_ticks=fields[19])


def snapshot_activity(metrics, clock=time.monotonic):
    """Small lock-only UI/API status; never reads model, replay or telemetry."""
    with metrics.lock:
        active = bool(getattr(metrics, 'coherent_snapshot_active', False))
        status = dict(getattr(metrics, 'coherent_snapshot_status', {}) or {})
    started = status.pop('started_monotonic_s', None)
    elapsed = max(0., clock() - started) if started is not None else 0.
    failed = bool(status.get('recovery_required', False))
    return dict(status, active=active, elapsed_s=elapsed,
                label=('Snapshot failed · recovery required' if failed else 'Saving matched-start snapshot')
                      if active else '',
                metrics_scope='Application snapshot status is fresh; copied training metrics remain frozen/cached during archive')


def snapshot_dashboard_overlay(metrics, cached, wall_clock=time.time, clock=time.monotonic):
    """Keep /api/now responsive even if a sampler waits on archive replay locks."""
    activity = snapshot_activity(metrics, clock)
    if not activity['active']:
        return None
    result = dict(cached)
    result.update(ts=wall_clock(), snapshot_base_metrics_ts=cached.get('ts'),
                  coherent_snapshot_active=True, coherent_snapshot=activity,
                  training_enabled=False, fps=0.)
    return result


def _json(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False, default=str)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _directory_sync(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _regular_file(path):
    information = path.lstat()
    if not stat.S_ISREG(information.st_mode):
        raise ValueError(f'Snapshot source is not a regular, nonsymlink file: {path}')
    return information


def _signature(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def copy_checked(source, destination, check_deadline, chunk_bytes=16 * 1024 * 1024, progress=None):
    """Exclusive independent copy, fsync and readback hash; no hardlinks/reflinks.

    Deadlines are checked between operations. An individual filesystem or model
    serialization call cannot safely be interrupted; this is not a hard I/O SLA.
    """
    source, destination = Path(source), Path(destination)
    check_deadline()
    before = _regular_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    digest = hashlib.sha256()
    copied_bytes = 0
    with os.fdopen(descriptor, 'rb') as original, destination.open('xb') as copied:
        if _signature(os.fstat(original.fileno())) != _signature(before):
            raise RuntimeError('Snapshot source identity changed before opening')
        while block := original.read(chunk_bytes):
            check_deadline()
            digest.update(block)
            copied.write(block)
            copied_bytes += len(block)
            if progress is not None:
                progress('copying', copied_bytes)
        copied.flush()
        os.fsync(copied.fileno())
        if _signature(os.fstat(original.fileno())) != _signature(before):
            raise RuntimeError('Snapshot source changed during copying')
    if _signature(source.lstat()) != _signature(before):
        raise RuntimeError('Snapshot source path was replaced during copying')
    readback = hashlib.sha256()
    if progress is not None:
        progress('verifying', copied_bytes)
    with destination.open('rb') as copied:
        while block := copied.read(chunk_bytes):
            check_deadline()
            readback.update(block)
    if digest.digest() != readback.digest():
        raise RuntimeError('Snapshot copy failed readback verification')
    after = destination.stat()
    if (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino):
        raise RuntimeError('Snapshot destination aliases live storage')
    return dict(bytes=before.st_size, sha256=digest.hexdigest(),
                source=str(source), source_device=before.st_dev, source_inode=before.st_ino)


def runtime_state(agent, cfg, control=None, game_settings=None):
    ramp = getattr(control, 'ramp', None)
    return dict(config=vars(cfg), lr_manual_scale=getattr(agent, 'lr_manual_scale', 1.),
                lr_gear=getattr(agent, 'lr_gear', None), lr_anchor_step=getattr(agent, 'lr_anchor_step', None),
                optimizer_group_lrs=[float(group['lr']) for group in getattr(getattr(agent, 'optimizer', None), 'param_groups', [])],
                control=(dict(label=control.label, lr_scale=control.lr_scale,
                              ramp=vars(ramp) if ramp is not None else None) if control is not None else None),
                game_settings=game_settings.snapshot() if game_settings is not None else None)


def state_guard(agent, metrics, memory, cfg, control=None, game_settings=None):
    with metrics.lock:
        clocks = {name:int(getattr(metrics, name, 0)) for name in
                  ('frame_count', 'learner_frame_count', 'measurement_frame_count',
                   'total_training_steps', 'total_optimized_samples')}
    policy_controls = {name:getattr(metrics, name, None) for name in
                       ('epsilon', 'expert_ratio', 'override_expert', 'override_epsilon',
                        'manual_pulse_active', 'manual_pulse_frames_remaining', 'managed_experiment')}
    return dict(clocks=clocks, policy_controls=policy_controls,
                runtime=json.dumps(runtime_state(agent, cfg, control, game_settings),
                                               sort_keys=True, allow_nan=False, default=str),
                training_steps=int(agent.training_steps),
                optimized_samples=int(agent.optimized_samples),
                last_target_update_samples=int(agent.last_target_update_samples),
                replay_size=int(memory.size), replay_pointer=int(memory.tree.data_ptr),
                replay_adds=int(memory._adds_total), max_priority=float(memory.tree.max_priority),
                bank_revisions=dict(memory._bank_revision), bank_saved_revisions=dict(memory._bank_saved_revision),
                bank_epochs=dict(memory._bank_load_epoch),
                banks={bank:dict(episodes=int(getattr(memory, bank + '_ep_count')),
                                transitions=int(getattr(memory, bank + '_total')))
                       for bank in ('hof', 'ephof')})


def persisted_sources(memory, ring):
    """Verify current saved metadata/tree and freshly captured bank generations.

    Caller holds bank-persist then replay locks. Do not call memory.save here:
    replay.lock is a plain Lock and save re-acquires it.
    """
    import numpy as np
    if memory._mmap_dir is None or Path(memory._mmap_dir).resolve() != ring:
        raise ValueError('Snapshot requires the existing live mmap ring')
    if ring.is_symlink():
        raise ValueError('Live ring directory must not be a symlink')
    meta = np.load(ring / '_meta.npy', allow_pickle=False)
    expected = np.asarray([memory.tree.data_ptr, memory.size, memory.tree.max_priority])
    if not np.array_equal(meta, expected):
        raise RuntimeError('Saved replay pointer/size/max priority does not match memory')
    priority = np.load(ring / 'priorities.npy', mmap_mode='r', allow_pickle=False)
    if not np.array_equal(priority[:memory.size],
                          memory.tree.tree[memory.tree.capacity:memory.tree.capacity + memory.size]):
        raise RuntimeError('Saved replay priority leaves do not match memory')
    sources = [(ring / name, Path('ring') / name) for name in ('_meta.npy', 'priorities.npy')]
    for name, (attribute, dtype, shape) in memory._storage_specs().items():
        value = getattr(memory, attribute)
        path = ring / (name + '.npy')
        _regular_file(path)
        if (not isinstance(value, np.memmap) or Path(value.filename).resolve() != path
                or value.dtype != dtype or value.shape != shape):
            raise RuntimeError('Live replay array backing/geometry differs: ' + name)
        sources.append((path, Path('ring') / path.name))
    banks = {}
    for bank in ('hof', 'ephof'):
        if not getattr(memory, '_' + bank + '_enabled') or not getattr(memory, bank + '_ep_count'):
            banks[bank] = dict(empty=True)
            continue
        base = Path(getattr(memory, '_' + bank + '_dir'))
        if base.is_symlink():
            raise ValueError('Bank base directory must not be a symlink')
        selected, generation = memory._resolve_bank_directory(bank, str(base))
        if generation is None:
            raise RuntimeError('A fresh atomic bank generation is required')
        selected = Path(selected)
        pointer = json.loads((base / 'CURRENT.json').read_text())
        if pointer.get('mutation_generation') != memory._bank_revision[bank]:
            raise RuntimeError('Bank selector is not a fresh snapshot of memory')
        if memory._bank_saved_revision[bank] != memory._bank_revision[bank]:
            raise RuntimeError('Bank is still dirty')
        with np.load(selected / (bank + '_meta.npz'), allow_pickle=False) as metadata:
            if (int(metadata['captured_adds']) != memory._adds_total
                    or int(metadata['mutation_generation']) != memory._bank_revision[bank]
                    or int(metadata['stale_age']) != memory._adds_total - getattr(memory, '_' + bank + '_last_admit_add')
                    or int(metadata['stale_age_normal']) != memory._adds_total - getattr(memory, '_' + bank + '_last_normal_admit_add')):
                raise RuntimeError('Bank metadata ages/capture clock differ from memory')
        relative = Path('banks') / bank
        sources.append((base / 'CURRENT.json', relative / 'CURRENT.json'))
        for field in (*memory._BANK_FIELDS, 'meta'):
            name = bank + '_' + field + ('.npz' if field == 'meta' else '.npy')
            _regular_file(selected / name)
            sources.append((selected / name, relative / 'generations' / generation / name))
        banks[bank] = dict(pointer=pointer, generation=generation)
    return sources, banks


def capture_snapshot(agent, metrics, server, cfg, model_dir, request, *,
                     copier=copy_checked, identity=process_identity, monotonic=time.monotonic,
                     inspect_sources=persisted_sources, control=None, game_settings=None,
                     synchronize_device=None):
    """Main-thread-only transaction. Failure publishes no COMPLETE certificate.

    No process signals or trainer restarts occur. On safe cleanup the application
    gate reopens; MAME may have timed out, so interruption-free games are not
    promised. A cleanup failure keeps training and the frame gate paused.
    """
    required = {'tag', 'request_id', 'expected_pid', 'expected_start_ticks',
                'expected_ring_dir', 'expected_ring_device', 'expected_ring_inode', 'timeout_s'}
    if set(request) != required:
        raise ValueError('Snapshot request fields do not match the supported schema')
    tag, owner = request['tag'], request['request_id']
    if (not isinstance(tag, str) or not 1 <= len(tag) <= 80
            or any(char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for char in tag)
            or not isinstance(owner, str) or len(owner) != 32
            or any(char not in '0123456789abcdef' for char in owner)):
        raise ValueError('Invalid snapshot tag/request identity')
    timeout = float(request['timeout_s'])
    if not math.isfinite(timeout) or not 1 <= timeout <= 14400:
        raise ValueError('Snapshot timeout must be within 1..14400 seconds')
    expected = dict(pid=request['expected_pid'], start_ticks=str(request['expected_start_ticks']))
    if identity() != expected:
        raise ValueError('Snapshot request belongs to a different trainer process')
    if bool(getattr(metrics, 'measurement_active', False)) or bool(getattr(metrics, 'ratchet_frozen', False)):
        raise RuntimeError('Snapshot cannot overlap a frozen measurement/ratchet')
    if bool(getattr(metrics, 'coherent_snapshot_active', False)):
        raise RuntimeError('A coherent snapshot is already active')
    if not bool(getattr(metrics, 'coherent_snapshot_keyboard_disabled', False)):
        raise RuntimeError('Coherent snapshots require keyboard mutation threads disabled at startup')
    memory, gate, consumer = agent.memory, server.snapshot_gate, server.async_buffer
    if not gate.enabled or consumer is None or not server.running or server.shutdown_event.is_set():
        raise RuntimeError('Snapshot requires an enabled running training server/replay consumer')
    if Path(agent._ring_dir).is_symlink():
        raise ValueError('Live replay directory must not be a symlink')
    ring = Path(agent._ring_dir).resolve()
    if memory._mmap_dir is None or Path(memory._mmap_dir).resolve() != ring:
        raise ValueError('Snapshot requires the existing live mmap ring')
    ring_info = ring.stat()
    if (str(ring) != request['expected_ring_dir']
            or ring_info.st_dev != request['expected_ring_device']
            or ring_info.st_ino != request['expected_ring_inode']):
        raise ValueError('Snapshot live replay directory identity differs')
    directory = Path(model_dir).resolve() / 'coherent-snapshots'
    directory.mkdir(exist_ok=True)
    if directory.is_symlink():
        raise ValueError('Snapshot output root must not be a symlink')
    destination = directory / (tag + '-' + owner)
    destination.mkdir()  # Exclusive: never reuse or overwrite an earlier artifact.
    input_paths = dict(learning_control=Path(control.path) if control is not None else Path(model_dir) / 'learning_control.json',
                       game_settings=Path(model_dir) / 'game_settings.json')
    deadline = monotonic() + timeout
    def check():
        if monotonic() >= deadline:
            raise TimeoutError('Coherent snapshot cooperative deadline expired')
        if (identity() != expected or agent.memory is not memory
                or server.async_buffer is not consumer or server.snapshot_gate is not gate):
            raise RuntimeError('Snapshot process/replay/consumer identity changed')
        if not server.running or server.shutdown_event.is_set():
            raise RuntimeError('Trainer server stopped during snapshot')
        now = ring.stat()
        if (now.st_dev, now.st_ino) != (ring_info.st_dev, ring_info.st_ino):
            raise RuntimeError('Live replay directory was replaced')
    def acquire(lock, description):
        check()
        if not lock.acquire(timeout=max(0., deadline - monotonic())):
            raise TimeoutError(description + ' did not quiesce')
    prior = dict(training_enabled=agent.training_enabled,
                 metrics_training_enabled=metrics.training_enabled,
                 prefetch_paused=agent._prefetch_paused)
    train_locked = prefetch_touched = False
    manifest = error = cleanup_error = None
    with metrics.lock:
        metrics.coherent_snapshot_active = True
        metrics.coherent_snapshot_status = dict(phase='waiting_for_clients', copied_bytes=0,
                                               total_bytes=None, current_file=None,
                                               started_monotonic_s=monotonic(), recovery_required=False)
    def publish_status(**values):
        with metrics.lock:
            metrics.coherent_snapshot_status = dict(metrics.coherent_snapshot_status, **values)
    try:
        _json(destination / 'INCOMPLETE.json', dict(phase='waiting_for_clients', request=request))
        boundary = gate.close(owner, max(0., deadline - monotonic()))
        publish_status(phase='pausing_learner_and_prefetch')
        # Game-settings HTTP writers register with the same gate. This point
        # follows their entire in-flight transaction; external file edits are
        # detected, never silently imported into an older in-memory control.
        input_signatures = {name:(_signature(_regular_file(path)) if path.exists() else None)
                            for name, path in input_paths.items()}
        if control is not None:
            raw = control.path.read_text() if control.path.exists() else '{}'
            if raw != control._raw:
                raise RuntimeError('Control file differs from the loaded runtime control')
        if game_settings is not None:
            settings_path = input_paths['game_settings']
            if (not settings_path.exists()
                    or json.loads(settings_path.read_text()) != game_settings.snapshot()):
                raise RuntimeError('Saved game settings differ from the loaded runtime settings')
        agent.training_enabled = False
        with metrics.lock:
            metrics.training_enabled = False
        acquire(agent._training_lock, 'Learner')
        train_locked = True
        prefetch_touched = True
        agent._pause_prefetch()
        check()
        synchronize = synchronize_device or getattr(agent, 'synchronize_snapshot_device', None)
        if not callable(synchronize):
            raise RuntimeError('An owned learner device synchronization barrier is required')
        device_barrier = synchronize()
        check()
        publish_status(phase='draining_async_replay')
        failures = int(getattr(consumer, 'snapshot_command_failures', 0))
        barrier = consumer.barrier_async(timeout=max(0., deadline - monotonic()))
        if not barrier.wait(max(0., deadline - monotonic())):
            raise TimeoutError('FIFO replay barrier did not finish preceding private/public commands')
        if int(getattr(consumer, 'snapshot_command_failures', 0)) != failures:
            raise RuntimeError('Async replay command failed while draining to snapshot')
        check()
        publish_status(phase='persisting_live_ring_and_banks')
        memory._wait_bank_writer(timeout=max(0., deadline - monotonic()))
        # This call acquires replay.lock itself. Never move it inside the lock
        # scope below; it also refreshes bank staleness metadata even if clean.
        memory.save(str(ring), verbose=False)
        check()
        memory._wait_bank_writer(timeout=max(0., deadline - monotonic()))
        with ExitStack() as held:
            acquire(memory._bank_persist_lock, 'Bank persistence')
            held.callback(memory._bank_persist_lock.release)
            acquire(memory.lock, 'Replay')
            held.callback(memory.lock.release)
            sources, banks = inspect_sources(memory, ring)
            # Archive the small frozen source files as provenance. A module
            # modified during the copy invalidates publication; this is not a
            # claim that arbitrary hot-reloaded Python code can be recovered.
            code_names = ('agent.py', 'config.py', 'model.py', 'training.py', 'replay_buffer.py',
                          'socket_server.py', 'prefetch.py', 'nstep_buffer.py', 'learning_control.py',
                          'main.py', 'metrics_dashboard.py', 'coherent_snapshot.py')
            code_paths = [Path(__file__).parent / name for name in code_names
                          if (Path(__file__).parent / name).exists()]
            code_signatures = {str(path):_signature(_regular_file(path)) for path in code_paths}
            sources.extend((path, Path('source') / path.name) for path in code_paths)
            baseline = state_guard(agent, metrics, memory, cfg, control, game_settings)
            boundary = gate.proof(owner)
            total_bytes = sum(_regular_file(path).st_size for path, _ in sources)
            total_bytes += sum(_regular_file(path).st_size for path in input_paths.values() if path.exists())
            available = os.statvfs(destination)
            if available.f_bavail * available.f_frsize < total_bytes + 1024 ** 3:
                raise OSError('Insufficient destination space for independent replay/bank copies')
            _json(destination / 'INCOMPLETE.json', dict(phase='copying', request=request,
                                                       source_bytes=total_bytes, boundary=boundary))
            publish_status(phase='saving_model', total_bytes=total_bytes)
            model = destination / 'model.pt'
            agent.save(str(model), show_status=False, save_replay=False)
            if not _regular_file(model).st_size:
                raise RuntimeError('Saved model is empty')
            with model.open('rb') as saved:
                os.fsync(saved.fileno())
                model_hash = hashlib.file_digest(saved, 'sha256').hexdigest()
            files = {'model.pt':dict(bytes=model.stat().st_size, sha256=model_hash)}
            completed_bytes = 0
            def archive_one(source, relative):
                nonlocal completed_bytes
                publish_status(phase='copying', current_file=str(relative), copied_bytes=completed_bytes)
                if copier is copy_checked:
                    def progress(phase, count):
                        publish_status(phase=phase, current_file=str(relative), copied_bytes=completed_bytes + count)
                    result = copier(source, destination / relative, check, progress=progress)
                else:
                    result = copier(source, destination / relative, check)
                completed_bytes += result['bytes']
                publish_status(copied_bytes=completed_bytes)
                return result
            for source, relative in sources:
                check()
                files[str(relative)] = archive_one(source, relative)
            runtime = runtime_state(agent, cfg, control, game_settings)
            _json(destination / 'runtime.json', runtime)
            for name, source in input_paths.items():
                signature = _signature(_regular_file(source)) if source.exists() else None
                if signature != input_signatures[name]:
                    raise RuntimeError('Recipe/settings input changed during snapshot')
                if source.exists():
                    files[name + '.json'] = archive_one(source, Path(name + '.json'))
            for name, expected_signature in input_signatures.items():
                source = input_paths[name]
                signature = _signature(_regular_file(source)) if source.exists() else None
                if signature != expected_signature:
                    raise RuntimeError('Recipe/settings input changed after copying')
            with (destination / 'runtime.json').open('rb') as recorded:
                files['runtime.json'] = dict(bytes=os.fstat(recorded.fileno()).st_size,
                                             sha256=hashlib.file_digest(recorded, 'sha256').hexdigest())
            after = state_guard(agent, metrics, memory, cfg, control, game_settings)
            if any(_signature(_regular_file(Path(path))) != signature
                   for path, signature in code_signatures.items()):
                raise RuntimeError('Trainer source files changed during snapshot')
            if baseline != after or gate.proof(owner) != boundary:
                raise RuntimeError('Model/replay/clocks/client proof changed after save or during archive')
            check()
            manifest = dict(schema='robotron-coherent-persisted-start-v1', request=request,
                            boundary=boundary, device_barrier=device_barrier,
                            before=baseline, after=after, files=files, banks=banks,
                            limitations=[
                                'Python client mutations parked; MAME processes/game time/RNG are not frozen or saved.',
                                'MAME action deadlines can expire during archive; both experiment branches require equally fresh client/server resets.',
                                'Python/NumPy/Torch/MAME RNG, actor histories, pending n-step tails and async adaptive histories are not restored.',
                                'Matches persisted model/optimizer/scaler/replay/banks; does not establish deterministic trajectories or exact continuation.',
                                'Timeout checks are cooperative between I/O operations; a blocking syscall/model/bank serialization cannot be safely interrupted.'])
            for path in sorted(destination.rglob('*'), reverse=True):
                if path.is_dir():
                    _directory_sync(path)
    except BaseException as caught:
        error = caught
    finally:
        try:
            publish_status(phase='restoring_paused_state')
            if train_locked:
                if prefetch_touched and not prior['prefetch_paused']:
                    agent._resume_prefetch()
                elif prior['prefetch_paused']:
                    agent._prefetch_paused = True
            if gate.owned_by(owner):
                # Open before learner flags: clients may reconnect, but a stale
                # leased learner batch still sees the paused training flags.
                gate.open(owner)
            with metrics.lock:
                metrics.training_enabled = prior['metrics_training_enabled']
                metrics.coherent_snapshot_active = False
            agent.training_enabled = prior['training_enabled']
            publish_status(phase='failed' if error is not None else 'complete')
        except BaseException as caught:
            cleanup_error = caught
            agent.training_enabled = False
            with metrics.lock:
                metrics.training_enabled = False
                metrics.coherent_snapshot_active = True
            publish_status(phase='cleanup_failed', recovery_required=True, error=repr(caught))
        finally:
            if train_locked:
                agent._training_lock.release()
    if error is not None or cleanup_error is not None:
        failure = dict(valid=False, error=repr(error), cleanup_error=repr(cleanup_error),
                       training_left_paused=cleanup_error is not None, request=request)
        _json(destination / 'FAILED.json', failure)
        if cleanup_error is not None:
            raise RuntimeError('Snapshot cleanup failed; application gate and training remain paused') from cleanup_error
        raise error
    # Publish only after copying, invariant checks, fsync and successful cleanup.
    # Hardlinking only this tiny newly-created manifest provides no-overwrite
    # atomic publication; replay/model/bank data are independent copied files.
    temporary = destination / 'COMPLETE.prepared.json'
    _json(temporary, manifest)
    os.link(temporary, destination / 'COMPLETE.json')
    temporary.unlink()
    _directory_sync(destination)
    return dict(valid=True, directory=str(destination), manifest=manifest)


def consume_snapshot_request(agent, metrics, server, cfg, model_dir, *, ratchet_on=False,
                             control=None, game_settings=None):
    """Explicit startup opt-in and one atomic claimed request; main thread only."""
    if os.getenv('DQN_COHERENT_SNAPSHOT', '0').strip().lower() not in ('1', 'true', 'yes', 'on'):
        return None
    path = Path(model_dir) / 'coherent_snapshot.request.json'
    if not path.exists():
        return None
    claimed = path.with_name(path.name + '.claimed-' + uuid.uuid4().hex)
    os.rename(path, claimed)
    result = None
    try:
        if ratchet_on:
            raise RuntimeError('Coherent snapshot is unavailable with ratchet mode')
        _regular_file(claimed)
        request = json.loads(claimed.read_text())
        result = capture_snapshot(agent, metrics, server, cfg, model_dir, request,
                                  control=control, game_settings=game_settings)
    except Exception as error:
        result = dict(valid=False, error=repr(error))
    _json(claimed.with_suffix(claimed.suffix + '.result.json'), result)
    return result
