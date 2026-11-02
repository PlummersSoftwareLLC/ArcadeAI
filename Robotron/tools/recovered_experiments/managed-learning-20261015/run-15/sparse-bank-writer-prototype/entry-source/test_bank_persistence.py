"""CPU-only coherent bank capture, publication and writer ownership checks."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np

from . import replay_buffer as module


class BankPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patches = [patch.object(module.RL_CONFIG, name, value) for name, value in dict(
            hof_enabled=True, ephof_enabled=True, hof_max_episodes=3, ephof_max_episodes=3,
            hof_episode_stride=64, ephof_episode_stride=64,
            interesting_replay_bank_size=128).items()]
        for current in self.patches:
            current.start()
            self.addCleanup(current.stop)
        self.memory = self.new_memory()
        self.populate(self.memory, 'hof')
        self.populate(self.memory, 'ephof')

    def new_memory(self):
        memory = module.PrioritizedReplayBuffer(128, 4)
        memory._hof_dir = str(self.root/'hof')
        memory._ephof_dir = str(self.root/'ephof')
        memory._bank_snapshot_chunk_rows = 7
        return memory

    @staticmethod
    def populate(memory, bank):
        lengths = np.asarray([35, 51], dtype=np.int32)
        for number, field in enumerate(memory._BANK_FIELDS):
            target = getattr(memory, f'{bank}_{field}')
            values = np.arange(target.size).reshape(target.shape) % (3 if field == 'actor_kind' else 71)
            target[:] = values.astype(target.dtype)
        getattr(memory, f'{bank}_ep_len')[:2] = lengths
        getattr(memory, f'{bank}_ep_score')[:2] = [50000, 60000]
        getattr(memory, f'{bank}_ep_game')[:2] = [123, 124]
        getattr(memory, f'{bank}_ep_level')[:2] = [5, 6]
        setattr(memory, f'{bank}_ep_count', 2)
        setattr(memory, f'{bank}_total', int(lengths.sum()))
        memory._adds_total = 1000
        setattr(memory, f'_{bank}_last_admit_add', 970)
        setattr(memory, f'_{bank}_last_normal_admit_add', 900)
        memory._bank_revision[bank] += 1
        getattr(memory, f'_{bank}_rebuild_flat_locked')()

    def selected(self, bank='hof'):
        path = getattr(self.memory, f'_{bank}_dir')
        return Path(self.memory._resolve_bank_directory(bank, path)[0])

    def test_both_banks_round_trip_exact_valid_rows_geometry_ages_and_zero_padding(self):
        for bank in ('hof', 'ephof'):
            with self.subTest(bank=bank):
                self.memory._save_bank_sync(bank, getattr(self.memory, f'_{bank}_dir'), False)
                directory = self.selected(bank)
                states = np.load(directory/f'{bank}_states.npy', mmap_mode='r')
                self.assertEqual(states.shape, (128, 4))
                self.assertEqual(states.dtype, np.float32)
                self.assertTrue(np.all(states[35:64] == 0))
                self.assertTrue(np.all(states[64+51:128] == 0))
                restored = self.new_memory()
                restored._adds_total = 2000
                self.assertTrue(restored._load_bank(bank, getattr(self.memory, f'_{bank}_dir'), False))
                for field in self.memory._BANK_FIELDS:
                    source, target = [getattr(value, f'{bank}_{field}') for value in (self.memory, restored)]
                    for episode, length in enumerate([35, 51]):
                        np.testing.assert_array_equal(source[episode*64:episode*64+length], target[episode*64:episode*64+length])
                self.assertEqual(getattr(restored, f'_{bank}_last_admit_add'), 1970)
                self.assertEqual(getattr(restored, f'_{bank}_last_normal_admit_add'), 1900)
                np.testing.assert_array_equal(getattr(restored, f'{bank}_ep_game')[:2], [123, 124])
                self.assertEqual(restored.max_game_uid(), 124)
                self.assertFalse(restored.get_bank_persistence_stats()['dirty'][bank])

    def test_legacy_flat_directory_loads_with_missing_game_metadata(self):
        self.memory._save_hof(self.memory._hof_dir, False)
        generation = self.selected()
        legacy = self.root/'legacy'
        legacy.mkdir()
        for field in self.memory._BANK_FIELDS:
            np.save(legacy/f'hof_{field}.npy', np.load(generation/f'hof_{field}.npy'))
        with np.load(generation/'hof_meta.npz') as meta:
            values = {key: meta[key] for key in meta.files if key not in ('ep_game', 'ep_level')}
            np.savez(legacy/'hof_meta.npz', **values)
        restored = self.new_memory()
        self.assertTrue(restored._load_hof(str(legacy), False))
        np.testing.assert_array_equal(restored.hof_ep_game[:2], [-1, -1])
        np.testing.assert_array_equal(restored.hof_ep_level[:2], [0, 0])
        self.assertEqual(restored.hof_total, 86)

    def test_same_ring_add_admissions_are_distinct_dirty_revisions(self):
        memory = self.new_memory()
        memory.size = 64
        memory.states[:64] = 1
        memory.next_states[:64] = 2
        memory._adds_total = 77
        def admit(uid):
            return memory._bank_admit('hof', range(64), 1000+uid, 0, 2, 64, 3, uid, 1)
        self.assertTrue(admit(1))
        memory._save_hof(memory._hof_dir, False)
        self.assertTrue(admit(2))
        self.assertEqual(memory._hof_last_admit_add, memory._hof_saved_admit_add)
        self.assertTrue(memory.get_bank_persistence_stats()['dirty']['hof'])
        memory.flush_banks()
        self.assertFalse(memory.get_bank_persistence_stats()['dirty']['hof'])

    def test_mutation_during_chunk_copy_defers_without_mixed_publication(self):
        original = module.time.sleep
        def mutate(_):
            with self.memory.lock:
                self.memory.hof_states[0] += 1
                self.memory._bank_revision['hof'] += 1
            original(0)
        with patch.object(module.time, 'sleep', side_effect=mutate):
            self.assertIsNone(self.memory._persist_bank('hof', self.memory._hof_dir, 0))
        self.assertFalse((self.root/'hof/CURRENT.json').exists())
        stats = self.memory.get_bank_persistence_stats()
        self.assertEqual(stats['capture_deferrals'], 2)
        self.assertTrue(stats['dirty']['hof'])

    def test_ring_add_clock_progress_does_not_invalidate_bank_snapshot(self):
        original = module.time.sleep
        def progress(_):
            with self.memory.lock:
                self.memory._adds_total += 1
            original(0)
        with patch.object(module.time, 'sleep', side_effect=progress):
            snapshot = self.memory._capture_bank('hof', 0)
        self.assertIsNotNone(snapshot)
        self.assertEqual(int(snapshot['meta']['stale_age']), 30)
        self.assertEqual(int(snapshot['meta']['stale_age_normal']), 100)

    def test_background_write_never_holds_replay_lock_and_new_admission_stays_dirty(self):
        entered, release = threading.Event(), threading.Event()
        original = self.memory._write_bank_generation
        def blocked(snapshot, path):
            entered.set()
            self.assertTrue(release.wait(5))
            original(snapshot, path)
        self.memory._ephof_enabled = False
        with patch.object(self.memory, '_write_bank_generation', side_effect=blocked):
            started = time.monotonic()
            self.assertEqual(self.memory.save_banks_if_dirty(), ['queued HOF'])
            self.assertLess(time.monotonic()-started, .25)
            self.assertTrue(entered.wait(5))
            self.assertEqual(self.memory.save_banks_if_dirty(), [])
            self.assertTrue(self.memory.lock.acquire(timeout=.2))
            try:
                self.memory.hof_states[0] += 100
                self.memory._bank_revision['hof'] += 1
            finally:
                self.memory.lock.release()
            with self.assertRaises(TimeoutError):
                self.memory.flush_banks(timeout=.01)
            release.set()
            self.memory._wait_bank_writer(5)
        self.assertTrue(self.memory.get_bank_persistence_stats()['dirty']['hof'])
        self.memory.flush_banks()
        self.assertFalse(self.memory.get_bank_persistence_stats()['dirty']['hof'])
        saved = np.load(self.selected()/'hof_states.npy')
        np.testing.assert_array_equal(saved[0], self.memory.hof_states[0])

    def test_failed_write_keeps_previous_current_and_dirty_then_flush_reports_failure(self):
        self.memory._save_hof(self.memory._hof_dir, False)
        pointer = self.root/'hof/CURRENT.json'
        previous = pointer.read_bytes()
        self.memory._bank_revision['hof'] += 1
        with patch.object(module.np, 'savez', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.memory.flush_banks()
        self.assertEqual(pointer.read_bytes(), previous)
        stats = self.memory.get_bank_persistence_stats()
        self.assertEqual(stats['write_failures'], 1)
        self.assertTrue(stats['dirty']['hof'])
        self.memory.flush_banks()
        self.assertFalse(self.memory.get_bank_persistence_stats()['dirty']['hof'])

    def test_current_and_previous_generations_retained_and_malformed_selector_fails_closed(self):
        identifiers = []
        for _ in range(3):
            self.memory._save_hof(self.memory._hof_dir, False)
            identifiers.append(self.selected().name)
        generations = self.root/'hof/generations'
        self.assertEqual(set(p.name for p in generations.iterdir()), set(identifiers[-2:]))
        pointer = self.root/'hof/CURRENT.json'
        pointer.write_text('{broken')
        restored = self.new_memory()
        before = restored.hof_states.copy()
        with self.assertRaises(ValueError):
            restored._load_hof(self.memory._hof_dir, False)
        np.testing.assert_array_equal(before, restored.hof_states)
        existing = set(generations.iterdir())
        with self.assertRaises(ValueError):
            self.memory._save_hof(self.memory._hof_dir, False)
        self.assertEqual(existing, set(generations.iterdir()))

    def test_load_epoch_invalidates_preload_request_without_publication(self):
        self.memory._save_hof(self.memory._hof_dir, False)
        pointer = self.root/'hof/CURRENT.json'
        before = pointer.read_bytes()
        old_epoch = self.memory._bank_load_epoch['hof']
        self.memory._load_hof(self.memory._hof_dir, False)
        self.assertGreater(self.memory._bank_load_epoch['hof'], old_epoch)
        self.assertIsNone(self.memory._persist_bank('hof', self.memory._hof_dir, old_epoch))
        self.assertEqual(pointer.read_bytes(), before)

    def test_explicit_full_save_waits_for_writer_and_retains_bank_generation(self):
        self.memory.size = 0
        self.assertTrue(self.memory.save_banks_if_dirty())
        self.memory.save(str(self.root/'ring'), verbose=False)
        self.assertFalse(self.memory.get_bank_persistence_stats()['writer_active'])
        self.assertTrue((self.root/'hof/CURRENT.json').exists())
        self.assertTrue((self.root/'ephof/CURRENT.json').exists())

    def test_real_replay_add_and_sample_progress_while_disk_writer_is_blocked(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        self.memory._ephof_enabled = False
        original = self.memory._write_bank_generation
        errors = []
        def blocked(snapshot, path):
            entered.set()
            if not release.wait(5):
                raise TimeoutError('test writer was not released')
            original(snapshot, path)
        def actor_and_learner():
            try:
                for value in range(32):
                    state = np.full(4, value, dtype=np.float32)
                    self.memory.add(state, 2, 1.0, state+1, False)
                sample = self.memory.sample(8)
                self.assertEqual(sample[0].shape, (8, 4))
                self.assertEqual(self.memory.size, 32)
            except BaseException as error:
                errors.append(error)
            finally:
                finished.set()
        with patch.object(self.memory, '_write_bank_generation', side_effect=blocked):
            self.memory.save_banks_if_dirty()
            self.assertTrue(entered.wait(5))
            worker = threading.Thread(target=actor_and_learner)
            worker.start()
            try:
                self.assertTrue(finished.wait(1), 'Disk writer blocked replay add/sample')
                self.assertFalse(errors)
            finally:
                release.set()
                worker.join(5)
                self.memory._wait_bank_writer(5)

    def test_failure_after_atomic_selector_replace_remains_dirty_and_retryable(self):
        self.memory._save_hof(self.memory._hof_dir, False)
        old = self.selected().name
        self.memory._bank_revision['hof'] += 1
        original = self.memory._fsync_directory
        def fail_parent(path):
            if str(path) == self.memory._hof_dir:
                raise OSError('directory fsync failed')
            original(path)
        with patch.object(self.memory, '_fsync_directory', side_effect=fail_parent):
            with self.assertRaisesRegex(OSError, 'directory fsync failed'):
                self.memory._save_hof(self.memory._hof_dir, False)
        self.assertNotEqual(self.selected().name, old)
        self.assertTrue((self.root/'hof/generations'/old).is_dir())
        self.assertTrue(self.memory.get_bank_persistence_stats()['dirty']['hof'])
        restored = self.new_memory()
        self.assertTrue(restored._load_hof(self.memory._hof_dir, False))
        self.memory.flush_banks()
        self.assertFalse(self.memory.get_bank_persistence_stats()['dirty']['hof'])

    def test_invalid_selected_generation_never_silently_uses_legacy_files(self):
        self.memory._save_hof(self.memory._hof_dir, False)
        generation = self.selected()
        # A legacy metadata file exists, but CURRENT still has authority.
        (self.root/'hof/hof_meta.npz').write_bytes((generation/'hof_meta.npz').read_bytes())
        (generation/'hof_meta.npz').unlink()
        with self.assertRaisesRegex(ValueError, 'metadata is missing'):
            self.new_memory()._load_hof(self.memory._hof_dir, False)
        pointer = self.root/'hof/CURRENT.json'
        value = json.loads(pointer.read_text())
        value['generation'] = 'gen-'+'0'*32
        pointer.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.new_memory()._load_hof(self.memory._hof_dir, False)

    def test_background_failure_is_recorded_and_explicit_flush_retries_or_raises(self):
        self.memory._ephof_enabled = False
        with patch.object(module.np, 'savez', side_effect=OSError('persistent disk error')):
            self.memory.save_banks_if_dirty()
            self.memory._wait_bank_writer(5)
            self.assertIn('persistent disk error', self.memory.get_bank_persistence_stats()['last_error'])
            with self.assertRaisesRegex(OSError, 'persistent disk error'):
                self.memory.flush_banks()
        self.assertEqual(self.memory.get_bank_persistence_stats()['write_failures'], 2)
        self.memory.flush_banks()
        self.assertFalse(self.memory.get_bank_persistence_stats()['dirty']['hof'])

    def test_snapshot_and_publication_do_not_advance_sampling_rng(self):
        before = np.random.get_state()
        self.memory._save_hof(self.memory._hof_dir, False)
        after = np.random.get_state()
        self.assertEqual(before[0], after[0])
        np.testing.assert_array_equal(before[1], after[1])
        self.assertEqual(before[2:], after[2:])

    def test_real_state_width_capture_keeps_each_locked_copy_bounded(self):
        with patch.object(module.RL_CONFIG, 'hof_max_episodes', 2), \
             patch.object(module.RL_CONFIG, 'hof_episode_stride', 256), \
             patch.object(module.RL_CONFIG, 'ephof_enabled', False):
            memory = module.PrioritizedReplayBuffer(32, 11128)
        memory.hof_ep_count, memory.hof_total = 2, 512
        memory.hof_ep_len[:] = 256
        memory.hof_ep_score[:] = [50000, 60000]
        memory.hof_states.fill(.125)
        memory.hof_next_states.fill(.25)
        memory._bank_revision['hof'] = 1
        calls = []
        original = module.np.copyto
        def copy(target, source, **kwargs):
            calls.append(len(source))
            return original(target, source, **kwargs)
        with patch.object(module.np, 'copyto', side_effect=copy):
            snapshot = memory._capture_bank('hof', 0)
        self.assertIsNotNone(snapshot)
        self.assertLessEqual(max(calls), 128)
        self.assertEqual(snapshot['arrays']['states'].dtype, np.float32)
        self.assertEqual(snapshot['arrays']['states'].shape, (512, 11128))
        self.assertGreater(memory.get_bank_persistence_stats()['snapshot_lock_max_ms'], 0)


if __name__ == '__main__':
    unittest.main()
