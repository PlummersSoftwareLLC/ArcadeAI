"""CPU/mocked race tests; never imports a trainer, Torch, MAME or live replay."""
import ast
from collections import deque
import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import uuid
from urllib.parse import urlparse

import numpy as np

from .coherent_snapshot import (SnapshotFrameGate, capture_snapshot, copy_checked, process_identity,
                                snapshot_activity, snapshot_dashboard_overlay)
from .build_proposal import prepare


class FakeMemory:
    _BANK_FIELDS = ('states', 'next_states', 'actions', 'rewards', 'dones', 'horizons', 'is_expert', 'actor_kind')

    def __init__(self, directory):
        self.lock = threading.Lock()  # Deliberately non-reentrant, like production.
        self._bank_persist_lock = threading.RLock()
        self._mmap_dir = str(directory / 'ring')
        Path(self._mmap_dir).mkdir()
        self.capacity, self.size, self._adds_total = 4, 3, 3
        self.tree = SimpleNamespace(data_ptr=3, capacity=4, max_priority=2.,
                                    tree=np.array([0., 4., 2., 2., .5, 1.5, 2., 0.]))
        self._bank_revision = dict(hof=1, ephof=1)
        self._bank_saved_revision = dict(hof=0, ephof=0)
        self._bank_load_epoch = dict(hof=0, ephof=0)
        self.writer = None
        self.save_calls = 0
        self.generations = []
        for name, (attribute, dtype, shape) in self._storage_specs().items():
            value = np.lib.format.open_memmap(Path(self._mmap_dir) / (name + '.npy'),
                                              mode='w+', dtype=dtype, shape=shape)
            value[:] = 0
            setattr(self, attribute, value)
        for bank in ('hof', 'ephof'):
            setattr(self, '_' + bank + '_enabled', True)
            setattr(self, bank + '_ep_count', 1)
            setattr(self, bank + '_total', 2)
            setattr(self, '_' + bank + '_last_admit_add', 2)
            setattr(self, '_' + bank + '_last_normal_admit_add', 1)
            setattr(self, '_' + bank + '_dir', str(directory / bank))

    def _storage_specs(self):
        return {name:(name, np.dtype(dtype), (4, 3) if 'states' in name else (4,))
                for name, dtype in [('states', 'float16'), ('next_states', 'float16'),
                                    ('actions', 'int64'), ('rewards', 'float32'),
                                    ('dones', 'float32'), ('horizons', 'int32'),
                                    ('is_expert', 'uint8'), ('actor_kind', 'uint8'), ('interesting', 'float32')]}

    def _wait_bank_writer(self, timeout=None):
        if self.writer:
            self.writer.join(timeout)
            if self.writer.is_alive():
                raise TimeoutError('Bank writer still active')

    def _resolve_bank_directory(self, bank, directory):
        pointer = json.loads((Path(directory) / 'CURRENT.json').read_text())
        return str(Path(directory) / 'generations' / pointer['generation']), pointer['generation']

    def save(self, directory, verbose=False):
        # The caller must not already hold replay.lock, or this fixture fails.
        if not self.lock.acquire(timeout=.1):
            raise RuntimeError('Replay save was called under the plain replay lock')
        try:
            self.save_calls += 1
            np.save(Path(directory) / '_meta.npy', np.array([3, 3, 2.]))
            np.save(Path(directory) / 'priorities.npy', self.tree.tree[4:])
        finally:
            self.lock.release()
        with self._bank_persist_lock:
            for bank in ('hof', 'ephof'):
                base = Path(getattr(self, '_' + bank + '_dir'))
                generation = 'gen-' + uuid.uuid4().hex
                selected = base / 'generations' / generation
                selected.mkdir(parents=True)
                for field in self._BANK_FIELDS:
                    np.save(selected / (bank + '_' + field + '.npy'), np.zeros(2))
                np.savez(selected / (bank + '_meta.npz'), captured_adds=self._adds_total,
                         mutation_generation=self._bank_revision[bank], stale_age=1, stale_age_normal=2)
                (base / 'CURRENT.json').write_text(json.dumps(dict(generation=generation,
                    mutation_generation=self._bank_revision[bank], schema='robotron-bank-generation-v1', bank=bank)))
                self._bank_saved_revision[bank] = self._bank_revision[bank]
                self.generations.append(selected)


class FakeAgent:
    def __init__(self, memory):
        self.memory = memory
        self._ring_dir = memory._mmap_dir
        self._training_lock = threading.RLock()
        self.training_enabled = True
        self._prefetch_paused = False
        self.training_steps = 9
        self.optimized_samples = 9 * 4096
        self.last_target_update_samples = 0
        self.pause_error = self.resume_error = None
        self.model_saved = threading.Event()
        self.device_barrier = threading.Event()
        self.lr_manual_scale = 1.
        self.lr_gear = 'climb'
        self.lr_anchor_step = 0.
        self.optimizer = SimpleNamespace(param_groups=[dict(lr=2.5e-5)])

    def synchronize_snapshot_device(self):
        assert self._prefetch_paused and not self.training_enabled
        self.device_barrier.set()
        return dict(device='cpu', mode='mocked_cpu_barrier')

    def _pause_prefetch(self):
        self._prefetch_paused = True
        if self.pause_error:
            raise self.pause_error

    def _resume_prefetch(self):
        if self.resume_error:
            raise self.resume_error
        self._prefetch_paused = False

    def save(self, destination, **kwargs):
        assert kwargs['save_replay'] is False
        Path(destination).write_bytes(json.dumps(dict(steps=self.training_steps,
            samples=self.optimized_samples, optimizer='preserved', target='preserved',
            optimizer_group_lrs=[group['lr'] for group in self.optimizer.param_groups])).encode())
        self.model_saved.set()


class FakeConsumer:
    snapshot_command_failures = 0
    def barrier_async(self, timeout=None):
        event = threading.Event()
        event.set()
        return event


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.memory = FakeMemory(self.directory)
        self.agent = FakeAgent(self.memory)
        self.metrics = SimpleNamespace(lock=threading.Lock(), training_enabled=True,
                                       frame_count=100, learner_frame_count=80,
                                       coherent_snapshot_keyboard_disabled=True)
        self.server = SimpleNamespace(snapshot_gate=SnapshotFrameGate(True), async_buffer=FakeConsumer(),
                                      running=True, shutdown_event=threading.Event())
        information = Path(self.agent._ring_dir).stat()
        self.request = dict(tag='test', request_id=uuid.uuid4().hex, expected_pid=os.getpid(),
            expected_start_ticks=process_identity()['start_ticks'], expected_ring_dir=self.agent._ring_dir,
            expected_ring_device=information.st_dev, expected_ring_inode=information.st_ino, timeout_s=5)

    def capture(self, **kwargs):
        return capture_snapshot(self.agent, self.metrics, self.server, SimpleNamespace(batch_size=4096),
                                self.directory, self.request, **kwargs)

    def assert_no_certificate(self):
        self.assertEqual(list((self.directory / 'coherent-snapshots').rglob('COMPLETE.json')), [])

    def test_success_persists_matching_model_ring_priorities_and_pinned_bank_generations(self):
        result = self.capture()
        destination = Path(result['directory'])
        certificate = json.loads((destination / 'COMPLETE.json').read_text())
        self.assertEqual(certificate['before'], certificate['after'])
        np.testing.assert_array_equal(np.load(destination / 'ring/_meta.npy'), [3, 3, 2.])
        np.testing.assert_array_equal(np.load(destination / 'ring/priorities.npy'), [.5, 1.5, 2., 0.])
        self.assertEqual(json.loads((destination / 'model.pt').read_text())['samples'], self.agent.optimized_samples)
        recorded_model = json.loads((destination / 'model.pt').read_text())
        recorded_runtime = json.loads((destination / 'runtime.json').read_text())
        self.assertEqual(recorded_model['optimizer_group_lrs'], recorded_runtime['optimizer_group_lrs'])
        for bank in ('hof', 'ephof'):
            pointer = json.loads((destination / 'banks' / bank / 'CURRENT.json').read_text())
            self.assertTrue((destination / 'banks' / bank / 'generations' / pointer['generation']).is_dir())
        self.assertTrue(self.agent.training_enabled)
        self.assertTrue(self.metrics.training_enabled)
        self.assertFalse(self.metrics.coherent_snapshot_active)
        self.assertFalse(self.agent._prefetch_paused)
        self.assertEqual(self.memory.save_calls, 1)
        self.assertIn('does not establish', ' '.join(certificate['limitations']))
        self.assertTrue(self.agent.device_barrier.is_set())
        self.memory.states[0, 0] = 55  # Later live mutations cannot alter the archived copy.
        self.assertEqual(float(np.load(destination / 'ring/states.npy')[0, 0]), 0.)

    def test_disabled_keyboard_is_a_required_startup_guarantee_not_a_per_key_check(self):
        prepare()
        staged = Path(__file__).parent / 'staged/Robotron/Scripts/dqn'
        module = ast.parse((staged / 'main.py').read_text())
        main = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        assignment = next(node for node in main.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Attribute) and target.attr == 'coherent_snapshot_keyboard_disabled'
                    for target in node.targets))
        condition = next(node for node in main.body if isinstance(node, ast.If)
            and 'coherent_snapshot_keyboard_disabled' in ast.unparse(node.test))
        def forbidden_keyboard():
            raise AssertionError('Snapshot opt-in must never create a keyboard thread')
        namespace = dict(metrics=SimpleNamespace(), _env_enabled=lambda *args:True,
                         IS_INTERACTIVE=True, KeyboardHandler=forbidden_keyboard)
        exec(compile(ast.Module(body=[assignment, condition], type_ignores=[]), 'staged_keyboard_startup', 'exec'), namespace)
        self.assertTrue(namespace['metrics'].coherent_snapshot_keyboard_disabled)
        self.metrics.coherent_snapshot_keyboard_disabled = False
        with self.assertRaisesRegex(RuntimeError, 'disabled at startup'):
            self.capture()
        self.assertEqual(self.memory.save_calls, 0)

    def test_actual_http_settings_mutation_parks_before_ram_writes_and_waits_for_existing_transaction(self):
        prepare()
        staged = Path(__file__).parent / 'staged/Robotron/Scripts/dqn'
        module = ast.parse((staged / 'metrics_dashboard.py').read_text())
        method = next(node for node in ast.walk(module) if isinstance(node, ast.FunctionDef) and node.name == 'do_POST')
        saved = threading.Event()
        class Settings:
            epsilon_pct = 10
            def save(self): saved.set()
            def snapshot(self): return dict(epsilon_pct=self.epsilon_pct)
        settings = Settings()
        namespace = dict(urlparse=urlparse, json=json, game_settings=settings,
                         state=SimpleNamespace(metrics=SimpleNamespace(global_server=self.server)))
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'staged_settings_post', 'exec'), namespace)
        payload = b'{"epsilon_pct":5}'
        handler = SimpleNamespace(path='/api/game_settings', headers={'Content-Length':str(len(payload))},
                                  rfile=io.BytesIO(payload), _send=lambda *args, **kwargs:None)
        gate = self.server.snapshot_gate
        gate.close('settings-owner', 1)
        worker = threading.Thread(target=lambda: namespace['do_POST'](handler))
        worker.start()
        try:
            self.assertFalse(saved.wait(.02))
            self.assertEqual(settings.epsilon_pct, 10)
        finally:
            gate.open('settings-owner')
            worker.join(1)
        self.assertTrue(saved.is_set())
        self.assertEqual(settings.epsilon_pct, 5)
        # An HTTP request already admitted before freeze must finish RAM+save
        # before close can return its quiescent proof.
        reading, release = threading.Event(), threading.Event()
        class PendingBody:
            def read(self, count):
                reading.set()
                release.wait(1)
                return payload
        handler.rfile = PendingBody()
        saved.clear()
        worker = threading.Thread(target=lambda: namespace['do_POST'](handler))
        worker.start()
        self.assertTrue(reading.wait(1))
        proofs = []
        closer = threading.Thread(target=lambda: proofs.append(gate.close('existing-writer', 1)))
        closer.start()
        try:
            self.assertFalse(saved.wait(.02))
            self.assertFalse(proofs)
            release.set()
            worker.join(1)
            closer.join(1)
            self.assertTrue(saved.is_set())
            self.assertTrue(proofs)
        finally:
            release.set()
            if gate.owned_by('existing-writer'):
                gate.open('existing-writer')
            worker.join(1)
            closer.join(1)

    def test_owned_device_barrier_occurs_before_persistence_and_sync_failure_cannot_publish(self):
        events = []
        original_save = self.memory.save
        def save(*args, **kwargs):
            self.assertEqual(events, ['device-synchronized'])
            return original_save(*args, **kwargs)
        self.memory.save = save
        def synchronize():
            self.assertFalse(self.agent.training_enabled)
            self.assertTrue(self.agent._prefetch_paused)
            events.append('device-synchronized')
            return dict(device='mocked-owned-device', mode='injected')
        self.capture(synchronize_device=synchronize)
        self.request['request_id'] = uuid.uuid4().hex
        self.agent.model_saved.clear()
        count = self.memory.save_calls
        def failure(): raise RuntimeError('device synchronization failed')
        with self.assertRaisesRegex(RuntimeError, 'device synchronization failed'):
            self.capture(synchronize_device=failure)
        self.assertFalse(self.agent.model_saved.is_set())
        self.assertEqual(self.memory.save_calls, count)
        self.assertTrue(self.agent.training_enabled)
        self.assertFalse(self.metrics.coherent_snapshot_active)

    def test_proposed_agent_barrier_synchronizes_only_owned_cuda_device_with_no_real_gpu(self):
        prepare()
        staged = Path(__file__).parent / 'staged/Robotron/Scripts/dqn'
        module = ast.parse((staged / 'agent.py').read_text())
        method = next(node for node in ast.walk(module) if isinstance(node, ast.FunctionDef)
                      and node.name == 'synchronize_snapshot_device')
        synchronized = []
        namespace = dict(torch=SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda device:synchronized.append(device))))
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'staged_owned_device_barrier', 'exec'), namespace)
        owned = SimpleNamespace(type='cuda')
        agent = SimpleNamespace(_training_lock=threading.RLock(), training_enabled=False,
                                _prefetch_paused=True, device=owned)
        with agent._training_lock:
            result = namespace['synchronize_snapshot_device'](agent)
        self.assertEqual(synchronized, [owned])
        self.assertEqual(result['mode'], 'owned_cuda_device_synchronized')
        agent.device = SimpleNamespace(type='cpu')
        self.assertEqual(namespace['synchronize_snapshot_device'](agent)['mode'], 'cpu_noop')
        self.assertEqual(synchronized, [owned])
        agent.training_enabled = True
        with self.assertRaises(RuntimeError):
            namespace['synchronize_snapshot_device'](agent)

    def test_optimizer_rate_or_manual_scale_drift_after_model_save_rejects_archive(self):
        for mutation in (lambda:setattr(self.agent, 'lr_manual_scale', .5),
                         lambda:self.agent.optimizer.param_groups[0].update(lr=1.25e-5)):
            self.request['request_id'] = uuid.uuid4().hex
            self.agent.lr_manual_scale = 1.
            self.agent.optimizer.param_groups[0]['lr'] = 2.5e-5
            changed = False
            def copier(source, destination, check):
                nonlocal changed
                if not changed:
                    mutation()
                    changed = True
                return copy_checked(source, destination, check)
            with self.assertRaisesRegex(RuntimeError, 'changed after save'):
                self.capture(copier=copier)
        self.assert_no_certificate()

    def test_existing_prefetch_invalidation_waits_for_old_producer_and_discards_queued_generation(self):
        # Execute the actual production invalidate method without importing
        # Torch or constructing any CUDA tensors/streams.
        repository = Path(__file__).resolve().parents[3]
        module = ast.parse((repository / 'Robotron/Scripts/dqn/prefetch.py').read_text())
        method = next(node for node in ast.walk(module) if isinstance(node, ast.FunctionDef)
                      and node.name == 'invalidate')
        namespace = dict(time=time, queue=queue)
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'actual_prefetch_invalidate', 'exec'), namespace)
        released = []
        queued = queue.Queue()
        queued.put(SimpleNamespace(release=lambda:released.append('discarded')))
        producer = SimpleNamespace(_epoch=0, _state=threading.Condition(), _ready=queued,
                                   _active_epoch=0, _raise_error=lambda:None)
        finished = []
        worker = threading.Thread(target=lambda: finished.append(namespace['invalidate'](producer, wait=True, timeout=1)))
        worker.start()
        time.sleep(.02)
        self.assertFalse(finished)
        self.assertEqual(released, ['discarded'])
        with producer._state:
            producer._active_epoch = None
            producer._state.notify_all()
        worker.join(1)
        self.assertEqual(finished, [True])
        self.assertEqual(producer._epoch, 1)

    def test_stale_loaded_control_and_unsaved_ram_settings_cannot_be_certified(self):
        path = self.directory / 'learning_control.json'
        path.write_text('{"lr_scale":0.25}')
        control = SimpleNamespace(path=path, _raw='{"lr_scale":0.5}',
                                  label='test', lr_scale=.5, ramp=None)
        with self.assertRaisesRegex(RuntimeError, 'loaded runtime control'):
            self.capture(control=control)
        self.assert_no_certificate()
        self.request['request_id'] = uuid.uuid4().hex
        control._raw = path.read_text()
        settings = SimpleNamespace(snapshot=lambda:dict(epsilon_pct=10))
        (self.directory / 'game_settings.json').write_text('{"epsilon_pct":5}')
        with self.assertRaisesRegex(RuntimeError, 'loaded runtime settings'):
            self.capture(control=control, game_settings=settings)
        self.assert_no_certificate()

    def test_snapshot_status_and_api_are_fresh_without_model_or_replay_reads(self):
        self.metrics.coherent_snapshot_active = True
        self.metrics.coherent_snapshot_status = dict(phase='copying', started_monotonic_s=10.,
            copied_bytes=60, total_bytes=100, recovery_required=False, current_file='ring/states.npy')
        status = snapshot_activity(self.metrics, clock=lambda:25.)
        self.assertEqual(status['elapsed_s'], 15.)
        self.assertEqual(status['label'], 'Saving matched-start snapshot')
        self.assertEqual(status['copied_bytes'], 60)
        cached = dict(ts=100., training_enabled=True, fps=9000., learner_frame_count=80)
        overlay = snapshot_dashboard_overlay(self.metrics, cached, wall_clock=lambda:200., clock=lambda:25.)
        self.assertEqual(overlay['ts'], 200.)
        self.assertEqual(overlay['snapshot_base_metrics_ts'], 100.)
        self.assertFalse(overlay['training_enabled'])
        self.assertEqual(overlay['fps'], 0.)
        self.assertTrue(overlay['coherent_snapshot_active'])
        self.assertEqual(cached['fps'], 9000.)
        # Execute the actual proposed endpoint helper while an unrelated replay
        # lock is held. It must not call the telemetry/model/replay readers.
        prepare()
        staged = Path(__file__).parent / 'staged/Robotron/Scripts/dqn'
        module = ast.parse((staged / 'metrics_dashboard.py').read_text())
        method = next(node for node in ast.walk(module) if isinstance(node, ast.FunctionDef) and node.name == 'now_body')
        namespace = dict(json=json, snapshot_dashboard_overlay=snapshot_dashboard_overlay)
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'staged_now_body', 'exec'), namespace)
        state = SimpleNamespace(metrics=self.metrics, lock=threading.Lock(), latest=cached,
                                _cached_now_body=json.dumps(cached).encode())
        with self.memory.lock:
            body = json.loads(namespace['now_body'](state))
        self.assertTrue(body['coherent_snapshot']['active'])
        self.assertEqual(body['coherent_snapshot']['label'], 'Saving matched-start snapshot')
        self.metrics.coherent_snapshot_status = dict(phase='cleanup_failed', recovery_required=True)
        self.assertEqual(snapshot_activity(self.metrics)['label'], 'Snapshot failed · recovery required')
        self.metrics.coherent_snapshot_active = False
        self.assertIsNone(snapshot_dashboard_overlay(self.metrics, cached))

    def test_frame_gate_flushes_before_proof_and_new_handlers_cannot_enter(self):
        gate = self.server.snapshot_gate
        ready, finish = threading.Event(), threading.Event()
        flushed = []
        def worker():
            token = gate.register('client:7')
            ready.set()
            try:
                while not finish.is_set():
                    gate.checkpoint(token, lambda: flushed.append('frame counters flushed'))
                    finish.wait(.001)
            finally:
                gate.unregister(token)
        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(ready.wait(1))
        owner = 'gate-test'
        try:
            proof = gate.close(owner, 1)
            self.assertEqual(proof['parked_workers'], ['client:7'])
            self.assertEqual(flushed, ['frame counters flushed'])
            entered = threading.Event()
            def newcomer():
                token = gate.register('late client')
                entered.set()
                gate.unregister(token)
            other = threading.Thread(target=newcomer)
            other.start()
            self.assertFalse(entered.wait(.02))
            self.assertEqual(gate.proof(owner), proof)
        finally:
            finish.set()
            gate.open(owner)
            thread.join(1)
            other.join(1)
        self.assertTrue(entered.is_set())

    def test_public_queue_empty_does_not_skip_unfinished_consumer_private_batch(self):
        prepare()
        source = (Path(__file__).parent / 'staged/Robotron/Scripts/dqn/socket_server.py').read_text()
        node = next(item for item in ast.parse(source).body if isinstance(item, ast.ClassDef)
                    and item.name == 'AsyncReplayBuffer')
        namespace = dict(queue=queue, threading=threading, deque=deque, time=time,
                         RL_CONFIG=SimpleNamespace(), metrics=SimpleNamespace())
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'staged_socket_server.py', 'exec'), namespace)
        started, release = threading.Event(), threading.Event()
        class Agent:
            def step(self, *args, **kwargs):
                started.set()
                release.wait(2)
                return -1
        consumer = namespace['AsyncReplayBuffer'](Agent())
        consumer.step_async('pending private row')
        self.assertTrue(started.wait(1))
        self.assertTrue(consumer.queue.empty())
        self.server.async_buffer = consumer
        completed, errors = [], []
        def capture():
            try:
                completed.append(self.capture())
            except BaseException as error:
                errors.append(error)
        worker = threading.Thread(target=capture)
        worker.start()
        try:
            self.assertFalse(self.agent.model_saved.wait(.05))
            release.set()
            worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(completed)
        finally:
            release.set()
            consumer.stop()
            worker.join(3)

    def test_bank_generation_lifetime_and_replay_writes_are_locked_through_copy(self):
        attempts, acquired = threading.Event(), threading.Event()
        started = False
        writers = []
        def copier(source, destination, check):
            nonlocal started
            if not started:
                started = True
                def writer():
                    attempts.set()
                    with self.memory._bank_persist_lock, self.memory.lock:
                        acquired.set()
                thread = threading.Thread(target=writer)
                writers.append(thread)
                thread.start()
                self.assertTrue(attempts.wait(1))
                self.assertFalse(acquired.wait(.03))
            self.assertFalse(acquired.is_set())
            return copy_checked(source, destination, check, chunk_bytes=23)
        result = self.capture(copier=copier)
        for writer in writers:
            writer.join(1)
        self.assertTrue(acquired.is_set())
        # Later live bank GC cannot invalidate the independent archive copy.
        import shutil
        for generation in self.memory.generations:
            shutil.rmtree(generation)
        manifest = result['manifest']
        for bank, selected in manifest['banks'].items():
            self.assertTrue((Path(result['directory']) / 'banks' / bank / 'generations' / selected['generation']).is_dir())

    def test_post_save_unguarded_clock_mutation_rejects_publication(self):
        changed = False
        def copier(source, destination, check):
            nonlocal changed
            if not changed:
                self.metrics.learner_frame_count += 1  # Deliberately violates producer contract.
                changed = True
            return copy_checked(source, destination, check)
        with self.assertRaisesRegex(RuntimeError, 'changed after save'):
            self.capture(copier=copier)
        self.assert_no_certificate()
        self.assertTrue(self.agent.training_enabled)

    def test_copy_error_restores_flags_without_publishing_and_preserves_preexisting_pause(self):
        self.agent.training_enabled = self.metrics.training_enabled = False
        self.agent._prefetch_paused = True
        with self.assertRaisesRegex(OSError, 'simulated disk failure'):
            self.capture(copier=lambda *a: (_ for _ in ()).throw(OSError('simulated disk failure')))
        self.assert_no_certificate()
        self.assertFalse(self.agent.training_enabled)
        self.assertFalse(self.metrics.training_enabled)
        self.assertTrue(self.agent._prefetch_paused)
        self.assertFalse(self.metrics.coherent_snapshot_active)

    def test_prefetch_pause_timeout_fails_safely_and_cleanup_failure_stays_paused(self):
        self.agent.pause_error = TimeoutError('producer still active')
        with self.assertRaisesRegex(TimeoutError, 'producer still active'):
            self.capture()
        self.assert_no_certificate()
        self.assertFalse(self.agent._prefetch_paused)
        self.assertTrue(self.agent.training_enabled)
        self.request['request_id'] = uuid.uuid4().hex
        self.agent.pause_error = None
        self.agent.resume_error = TimeoutError('resume invalidation failed')
        with self.assertRaisesRegex(RuntimeError, 'cleanup failed'):
            self.capture()
        self.assert_no_certificate()
        self.assertFalse(self.agent.training_enabled)
        self.assertTrue(self.metrics.coherent_snapshot_active)
        self.assertTrue(self.server.snapshot_gate.owned_by(self.request['request_id']))
        self.assertEqual(snapshot_activity(self.metrics)['label'], 'Snapshot failed · recovery required')
        self.assertEqual(snapshot_activity(self.metrics)['phase'], 'cleanup_failed')
        # Test-only recovery; no live process is touched.
        self.server.snapshot_gate.open(self.request['request_id'])

    def test_bank_writer_timeout_cannot_be_mistaken_for_finished_persistence(self):
        release = threading.Event()
        writer = threading.Thread(target=lambda: release.wait(2))
        writer.start()
        self.memory.writer = writer
        self.request['timeout_s'] = 1
        try:
            with self.assertRaisesRegex(TimeoutError, 'Bank writer still active'):
                self.capture()
            self.assert_no_certificate()
            self.assertEqual(self.memory.save_calls, 0)
        finally:
            release.set()
            writer.join(1)

    def test_identity_invalid_optin_and_measurement_guards_precede_mutation(self):
        for field, value in [('expected_pid', os.getpid() + 1), ('expected_start_ticks', 'wrong'),
                             ('expected_ring_inode', -1), ('tag', '../escape')]:
            original = self.request[field]
            self.request[field] = value
            with self.assertRaises(ValueError):
                self.capture()
            self.request[field] = original
        self.server.snapshot_gate.enabled = False
        with self.assertRaises(RuntimeError):
            self.capture()
        self.server.snapshot_gate.enabled = True
        self.metrics.measurement_active = True
        with self.assertRaises(RuntimeError):
            self.capture()
        self.assertEqual(self.memory.save_calls, 0)
        self.assertTrue(self.agent.training_enabled)

    def test_control_mutation_and_stale_priority_metadata_are_rejected(self):
        control = self.directory / 'learning_control.json'
        control.write_text('{"lr_scale":0.5}')
        changed = False
        def copier(source, destination, check):
            nonlocal changed
            if not changed:
                control.write_text('{"lr_scale":0.25}')
                changed = True
            return copy_checked(source, destination, check)
        with self.assertRaisesRegex(RuntimeError, 'Recipe/settings'):
            self.capture(copier=copier)
        self.assert_no_certificate()
        self.request['request_id'] = uuid.uuid4().hex
        actual_save = self.memory.save
        def save_bad_metadata(*args, **kwargs):
            actual_save(*args, **kwargs)
            np.save(Path(self.memory._mmap_dir) / '_meta.npy', [0, 3, 2.])
        self.memory.save = save_bad_metadata
        with self.assertRaisesRegex(RuntimeError, 'pointer/size'):
            self.capture()
        self.assert_no_certificate()

    def test_source_replacement_and_cooperative_copy_timeout_leave_no_false_archive(self):
        source, destination = self.directory / 'source', self.directory / 'copy'
        source.write_bytes(b'abc' * 100)
        checks = 0
        def check():
            nonlocal checks
            checks += 1
            if checks == 3:
                raise TimeoutError('deadline')
        with self.assertRaises(TimeoutError):
            copy_checked(source, destination, check, chunk_bytes=7)
        destination.unlink()
        checks = 0
        def replace_source():
            nonlocal checks
            checks += 1
            if checks == 2:
                replacement = self.directory / 'replacement'
                replacement.write_bytes(b'x' * 300)
                os.replace(replacement, source)
        with self.assertRaisesRegex(RuntimeError, 'changed|replaced'):
            copy_checked(source, destination, replace_source, chunk_bytes=7)

    def test_gate_timeout_and_failed_counter_flush_do_not_claim_quiescence(self):
        gate = SnapshotFrameGate(True)
        token = gate.register('hung client')
        with self.assertRaises(TimeoutError):
            gate.close('owner', .01)
        gate.open('owner')
        gate.unregister(token)
        token = gate.register('bad counter flush')
        errors = []
        def closer():
            try:
                gate.close('owner2', 1)
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=closer)
        thread.start()
        while not gate.owned_by('owner2'):
            time.sleep(.001)
        try:
            with self.assertRaisesRegex(ValueError, 'bad counters'):
                gate.checkpoint(token, lambda: (_ for _ in ()).throw(ValueError('bad counters')))
            gate.unregister(token)
            thread.join(1)
            self.assertTrue(errors)
        finally:
            gate.open('owner2')


if __name__ == '__main__':
    unittest.main(verbosity=2)
