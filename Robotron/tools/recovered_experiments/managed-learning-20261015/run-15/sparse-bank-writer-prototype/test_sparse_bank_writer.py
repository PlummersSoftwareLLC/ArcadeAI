"""Bounded CPU-only tests; writes only TemporaryDirectories, never live banks."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

import numpy as np

from sparse_bank_writer import (FIELDS, PhaseTelemetry, write_generation,
                                write_sparse_npy)

HERE = Path(__file__).resolve().parent
ROBOTRON = HERE.parents[3]
REPLAY_SOURCE = ROBOTRON / "Scripts/dqn/replay_buffer.py"


def reference_owner_class():
    """Run the ACTUAL source's disk methods without importing torch/learner."""
    parsed = ast.parse(REPLAY_SOURCE.read_text())
    original = next(node for node in parsed.body if isinstance(node, ast.ClassDef)
                    and node.name == "PrioritizedReplayBuffer")
    names = {"_write_bank_generation", "_resolve_bank_directory", "_fsync_directory"}
    body = [copy.deepcopy(node) for node in original.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in names]
    for node in original.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "_BANK_SCHEMA"
                for target in node.targets):
            body.append(copy.deepcopy(node))
    owner = ast.ClassDef(name="ReferenceOwner", bases=[], keywords=[], body=body,
                         decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[owner], type_ignores=[]))
    namespace = dict(np=np, os=os, uuid=uuid, shutil=shutil, json=json)
    exec(compile(module, str(REPLAY_SOURCE), "exec"), namespace)
    return namespace["ReferenceOwner"]


def fixture_snapshot(bank="hof"):
    lengths = np.asarray([3, 0, 5], dtype=np.int32)
    bits = np.asarray([0, 0x80000000, 0x7f800000, 0xff800000,
        0x7fc01234, 0x7fa05678, 1, 0x80000001, 0x3f800001, 0xffc04321,
        0x007fffff, 0x00800000, 0x7f7fffff, 0xff7fffff, 0x3f000000,
        0xbf800000] * 2, dtype=np.uint32)
    states = bits.view(np.float32).reshape(8, 4).copy()
    arrays = dict(states=states, next_states=states[::-1].copy(),
        actions=np.arange(8, dtype=np.int64), rewards=bits[:8].view(np.float32).copy(),
        dones=np.asarray([0, 1] * 4, dtype=np.bool_),
        horizons=np.asarray([1, 2, 3, 1, 3, 2, 1, 3], dtype=np.uint8),
        is_expert=np.asarray([1, 0, 0, 0] * 2, dtype=np.bool_),
        actor_kind=np.asarray([0, 1, 2, 1] * 2, dtype=np.uint8))
    meta = dict(ep_len=lengths, ep_score=np.asarray([100, 0, 200], dtype=np.float64),
        ep_game=np.asarray([91, 92, 93], dtype=np.int64),
        ep_level=np.asarray([1, 1, 2], dtype=np.int32),
        stale_age=np.int64(30), stale_age_normal=np.int64(100),
        stride=np.int64(7), state_size=np.int64(4), captured_adds=np.int64(1000),
        mutation_generation=np.int64(5))
    return dict(bank=bank, count=3, stride=7, total=8, arrays=arrays, meta=meta,
                revision=5, epoch=0, last_admit=970)


def selected(owner, path, bank="hof"):
    return Path(owner._resolve_bank_directory(bank, str(path))[0])


def crash_child(directory, phase):
    owner = reference_owner_class()()
    def crash(name, field):
        if name == phase:
            os._exit(73)
    write_generation(owner, fixture_snapshot(), directory, enabled=True,
                     phase_hook=crash, chunk_bytes=19)
    raise AssertionError("Crash hook not reached")


class SparseWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.owner = reference_owner_class()()

    def test_default_off_delegates_unchanged_and_records_nothing(self):
        token = object()
        class FakeOwner:
            def _write_bank_generation(self, snapshot, directory):
                self.args = snapshot, directory
                return token
        owner, stats = FakeOwner(), PhaseTelemetry()
        snapshot = fixture_snapshot()
        self.assertIs(write_generation(owner, snapshot, self.root,
                                      telemetry=stats), token)
        self.assertEqual(owner.args, (snapshot, self.root))
        self.assertEqual(stats.snapshot()["totals"], {})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_complete_npy_bytes_and_metadata_match_actual_memmap_writer(self):
        snapshot = fixture_snapshot()
        before = {name: value.tobytes() for name, value in snapshot["arrays"].items()}
        old, new = self.root / "old", self.root / "new"
        self.owner._write_bank_generation(snapshot, str(old))
        stats = PhaseTelemetry()
        with patch.object(np.lib.format, "open_memmap", side_effect=AssertionError("output mmap")):
            write_generation(self.owner, snapshot, new, enabled=True,
                             telemetry=stats, chunk_bytes=7)
        old_selected, new_selected = selected(self.owner, old), selected(self.owner, new)
        for field in FIELDS:
            self.assertEqual((old_selected / f"hof_{field}.npy").read_bytes(),
                             (new_selected / f"hof_{field}.npy").read_bytes(), field)
            self.assertEqual(snapshot["arrays"][field].tobytes(), before[field])
        with np.load(old_selected / "hof_meta.npz") as a, np.load(new_selected / "hof_meta.npz") as b:
            self.assertEqual(a.files, b.files)
            for name in a.files:
                self.assertEqual(a[name].tobytes(), b[name].tobytes(), name)
        telemetry = stats.snapshot()
        self.assertEqual(telemetry["totals"]["write"]["count"], 8)
        self.assertEqual(telemetry["totals"]["close"]["count"], 10)
        self.assertEqual(telemetry["totals"]["fsync"]["count"], 10)
        self.assertEqual(telemetry["totals"]["write"]["payload_bytes"],
                         sum(value.nbytes for value in snapshot["arrays"].values()))
        self.assertIsNone(telemetry["active"])

    def test_dtype_bits_non_native_endian_padding_empty_rows_and_zero_count(self):
        for dtype in ("<f4", ">f4", "<f8", "i1", "<i2", ">i8", "u8", "?", "S3", "c8"):
            for lengths in ([0, 2, 1], [0, 0, 0], []):
                with self.subTest(dtype=dtype, lengths=lengths):
                    source = np.zeros((sum(lengths), 2), dtype=dtype)
                    if source.size:
                        # Raw byte patterns preserve every representation, including NaN bits.
                        source.view(np.uint8).reshape(-1)[:] = np.arange(source.nbytes, dtype=np.uint8)
                    target = self.root / ("case" + str(len(list(self.root.iterdir()))) + ".npy")
                    write_sparse_npy(target, source, count=len(lengths), stride=5,
                        lengths=np.asarray(lengths, dtype=np.int32), chunk_bytes=3)
                    actual = np.load(target, allow_pickle=False)
                    self.assertEqual(actual.shape, (len(lengths) * 5, 2))
                    self.assertEqual(actual.dtype, source.dtype)
                    cursor = 0
                    for episode, length in enumerate(lengths):
                        self.assertEqual(actual[episode * 5:episode * 5 + length].tobytes(),
                                         source[cursor:cursor + length].tobytes())
                        self.assertEqual(actual[episode * 5 + length:(episode + 1) * 5].tobytes(),
                                         b"\0" * ((5 - length) * 2 * source.dtype.itemsize))
                        cursor += length
                    if lengths:
                        old = self.root / (target.stem + "-old.npy")
                        mapped = np.lib.format.open_memmap(old, mode="w+", dtype=source.dtype,
                                                          shape=actual.shape)
                        cursor = 0
                        for episode, length in enumerate(lengths):
                            mapped[episode * 5:episode * 5 + length] = source[cursor:cursor + length]
                            cursor += length
                        mapped.flush(); mapped._mmap.close()
                        self.assertEqual(target.read_bytes(), old.read_bytes())

    def test_invalid_input_and_existing_file_never_silently_overwrite(self):
        valid = np.arange(8, dtype=np.float32).reshape(4, 2)
        for source, count, stride, lengths in [
            (valid[:, ::-1], 1, 4, [4]), (valid, 1, 3, [4]),
            (valid, 1, 4, [-1]), (valid, 1, 4, [3]),
            (valid, 2, 4, [4]), (valid, 1, 4, [4.0]),
            (np.empty((4, 2), dtype=object), 1, 4, [4])]:
            path = self.root / "invalid.npy"
            with self.assertRaises(ValueError):
                write_sparse_npy(path, source, count=count, stride=stride, lengths=lengths)
            self.assertFalse(path.exists())
        path = self.root / "existing.npy"; path.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            write_sparse_npy(path, valid, count=1, stride=4, lengths=[4])
        self.assertEqual(path.read_bytes(), b"keep")

    def test_short_interrupted_and_zero_progress_writes(self):
        original = os.pwrite
        count = 0
        amounts = []
        def short(fd, data, offset):
            nonlocal count
            count += 1
            if count == 1:
                raise InterruptedError()
            amounts.append(len(data))
            return original(fd, data[:3], offset)
        path = self.root / "short.npy"
        source = np.arange(64, dtype=np.float32).reshape(8, 8)
        with patch("sparse_bank_writer.os.pwrite", side_effect=short):
            write_sparse_npy(path, source, count=2, stride=8, lengths=[3, 5], chunk_bytes=17)
        np.testing.assert_array_equal(np.load(path)[8:13], source[3:])
        self.assertLessEqual(max(amounts[43:]), 17)
        with patch("sparse_bank_writer.os.pwrite", return_value=0):
            with self.assertRaisesRegex(OSError, "invalid progress"):
                write_sparse_npy(self.root / "fail.npy", source, count=2, stride=8, lengths=[3, 5])

    def test_generation_failure_cleanup_and_previous_retention(self):
        snapshot = fixture_snapshot()
        path = self.root / "bank"
        write_generation(self.owner, snapshot, path, enabled=True)
        pointer = (path / "CURRENT.json").read_bytes()
        old = selected(self.owner, path)
        for phase in ("after_header", "after_write", "after_fsync", "after_close",
                      "after_metadata", "before_replace"):
            def fail(name, field):
                if name == phase:
                    raise OSError("injected " + phase)
            with self.assertRaisesRegex(OSError, "injected"):
                write_generation(self.owner, snapshot, path, enabled=True, phase_hook=fail)
            self.assertEqual((path / "CURRENT.json").read_bytes(), pointer)
            self.assertEqual(list((path / "generations").iterdir()), [old])
            self.assertFalse(list(path.glob("*.tmp")))
        names = [old.name]
        for revision in (6, 7):
            snapshot["revision"] = revision
            write_generation(self.owner, snapshot, path, enabled=True)
            names.append(selected(self.owner, path).name)
        self.assertEqual({item.name for item in (path / "generations").iterdir()}, set(names[-2:]))

    def test_postreplace_failure_keeps_complete_new_and_previous_generation(self):
        snapshot = fixture_snapshot(); path = self.root / "bank"
        write_generation(self.owner, snapshot, path, enabled=True)
        old = selected(self.owner, path)
        def fail(name, field):
            if name == "after_replace":
                raise OSError("after atomic replace")
        with self.assertRaisesRegex(OSError, "after atomic replace"):
            write_generation(self.owner, snapshot, path, enabled=True, phase_hook=fail)
        new = selected(self.owner, path)
        self.assertNotEqual(old, new)
        self.assertTrue(old.is_dir())
        for field in FIELDS:
            self.assertEqual((old / f"hof_{field}.npy").read_bytes(),
                             (new / f"hof_{field}.npy").read_bytes())

    def test_file_fsync_error_preserves_current_and_closes_output(self):
        path = self.root / "bank"
        write_generation(self.owner, fixture_snapshot(), path, enabled=True)
        pointer = (path / "CURRENT.json").read_bytes()
        original, failed_fd = os.fsync, []
        def fail(fd):
            if os.readlink(f"/proc/self/fd/{fd}").endswith("hof_states.npy"):
                failed_fd.append(fd)
                raise OSError("data fsync failed")
            return original(fd)
        with patch("sparse_bank_writer.os.fsync", side_effect=fail):
            with self.assertRaisesRegex(OSError, "data fsync failed"):
                write_generation(self.owner, fixture_snapshot(), path, enabled=True)
        self.assertEqual((path / "CURRENT.json").read_bytes(), pointer)
        self.assertEqual(len(list((path / "generations").iterdir())), 1)
        self.assertEqual(len(failed_fd), 1)
        with self.assertRaises(OSError):
            os.fstat(failed_fd[0])

    def test_real_state_width_complete_file_identity_with_large_zero_holes(self):
        source = np.full((2, 11128), .125, dtype=np.float32)
        source[1].view(np.uint32)[::7] = 0x80000000
        old, new = self.root / "old.npy", self.root / "new.npy"
        mapped = np.lib.format.open_memmap(old, mode="w+", dtype=source.dtype,
                                          shape=(512, 11128))
        mapped[0] = source[0]; mapped[256] = source[1]
        mapped.flush(); mapped._mmap.close()
        write_sparse_npy(new, source, count=2, stride=256, lengths=[1, 1], chunk_bytes=4096)
        self.assertEqual(old.read_bytes(), new.read_bytes())
        # Two valid rows in 512 padded rows; no test creates a 17.5 GB mapping.
        self.assertGreater(new.stat().st_size, 20 * 1024 * 1024)

    def test_hard_process_exit_before_and_after_selector_replace(self):
        for phase in ("after_write", "after_metadata", "before_replace", "after_replace"):
            with self.subTest(phase=phase):
                path = self.root / phase
                write_generation(self.owner, fixture_snapshot(), path, enabled=True)
                old = selected(self.owner, path)
                result = subprocess.run([sys.executable, "-Xgil=0", str(Path(__file__).resolve()),
                    "--crash-child", str(path), phase], env=dict(os.environ,
                    CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2"),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
                self.assertEqual(result.returncode, 73, result.stderr.decode())
                current = selected(self.owner, path)
                if phase == "after_replace":
                    self.assertNotEqual(current, old)
                else:
                    self.assertEqual(current, old)
                self.assertTrue(old.is_dir())
                for field in FIELDS:
                    self.assertEqual((current / f"hof_{field}.npy").read_bytes(),
                                     (old / f"hof_{field}.npy").read_bytes())
                with np.load(current / "hof_meta.npz", allow_pickle=False) as meta:
                    self.assertEqual(int(meta["mutation_generation"]), 5)

    def test_malformed_selector_does_not_create_orphan_and_rng_unchanged(self):
        path = self.root / "bank"
        write_generation(self.owner, fixture_snapshot(), path, enabled=True)
        (path / "CURRENT.json").write_text("{bad")
        before = set((path / "generations").iterdir())
        with self.assertRaises(ValueError):
            write_generation(self.owner, fixture_snapshot(), path, enabled=True)
        self.assertEqual(before, set((path / "generations").iterdir()))
        state = np.random.get_state()
        write_generation(self.owner, fixture_snapshot(), self.root / "rng", enabled=True)
        after = np.random.get_state()
        self.assertEqual(state[0], after[0])
        np.testing.assert_array_equal(state[1], after[1])
        self.assertEqual(state[2:], after[2:])

    def test_telemetry_active_phase_non_draining_bounded_and_errors(self):
        stats = PhaseTelemetry()
        started, release = threading.Event(), threading.Event()
        def work():
            with stats.phase("write", field="states", payload_bytes=11):
                started.set(); release.wait(5)
        thread = threading.Thread(target=work); thread.start()
        try:
            self.assertTrue(started.wait(1))
            self.assertEqual(stats.snapshot()["active"]["phase"], "write")
            self.assertEqual(stats.snapshot()["totals"], {})
        finally:
            release.set(); thread.join(5)
        for _ in range(70):
            with stats.phase("close"):
                pass
        with self.assertRaises(OSError):
            with stats.phase("fsync"):
                raise OSError("failed")
        a = stats.snapshot(); b = stats.snapshot()
        self.assertEqual(a, b)
        self.assertEqual(len(a["recent"]), 64)
        self.assertEqual(a["totals"]["close"]["count"], 70)
        self.assertEqual(a["totals"]["fsync"]["errors"], 1)


def add_actual_replay_tests():
    """Reuse every existing capture/flush/epoch/dirty/loader concurrency check."""
    sys.path.insert(0, str(ROBOTRON / "Scripts"))
    import torch
    torch.set_num_threads(2)
    from dqn.test_bank_persistence import BankPersistenceTests
    class ActualReplayStreamingTests(BankPersistenceTests):
        def new_memory(self):
            memory = super().new_memory()
            stats = PhaseTelemetry()
            memory._prototype_phase_stats = stats
            memory._write_bank_generation = lambda snapshot, path: write_generation(
                memory, snapshot, path, enabled=True, telemetry=stats, chunk_bytes=16384)
            return memory

        def test_blocked_actual_output_pwrite_allows_replay_add_sample_and_stats(self):
            entered, release, finished = threading.Event(), threading.Event(), threading.Event()
            self.memory._ephof_enabled = False
            original = os.pwrite
            errors = []
            def blocked(fd, data, offset):
                if (offset >= 128 and not entered.is_set()
                        and os.readlink(f"/proc/self/fd/{fd}").endswith("hof_states.npy")):
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError("test output was not released")
                return original(fd, data, offset)
            def replay_work():
                try:
                    for value in range(32):
                        state = np.full(4, value, dtype=np.float32)
                        self.memory.add(state, 2, 1.0, state + 1, False)
                    self.assertEqual(self.memory.sample(8)[0].shape, (8, 4))
                    self.assertEqual(self.memory._prototype_phase_stats.snapshot()["active"]["phase"], "write")
                    self.assertTrue(self.memory.get_bank_persistence_stats()["writer_active"])
                except BaseException as error:
                    errors.append(error)
                finally:
                    finished.set()
            with patch("sparse_bank_writer.os.pwrite", side_effect=blocked):
                self.memory.save_banks_if_dirty()
                self.assertTrue(entered.wait(5))
                thread = threading.Thread(target=replay_work)
                thread.start()
                try:
                    self.assertTrue(finished.wait(1), "Blocked pwrite held replay/stats lock")
                    self.assertEqual(errors, [])
                finally:
                    release.set(); thread.join(5)
                    self.memory._wait_bank_writer(5)

        def test_save_preserves_cpu_rngs_and_replay_clocks_and_tree(self):
            import random
            before_py, before_np, before_torch = random.getstate(), np.random.get_state(), torch.get_rng_state()
            before = (self.memory._adds_total, self.memory.size, self.memory.tree.data_ptr,
                      self.memory.tree.tree.copy())
            self.memory._save_hof(self.memory._hof_dir, False)
            self.assertEqual(random.getstate(), before_py)
            after_np = np.random.get_state()
            self.assertEqual(after_np[0], before_np[0])
            np.testing.assert_array_equal(after_np[1], before_np[1])
            self.assertEqual(after_np[2:], before_np[2:])
            self.assertTrue(torch.equal(torch.get_rng_state(), before_torch))
            self.assertFalse(torch.cuda.is_initialized())
            self.assertEqual((self.memory._adds_total, self.memory.size, self.memory.tree.data_ptr), before[:3])
            self.assertEqual(self.memory.tree.tree.tobytes(), before[3].tobytes())
    ActualReplayStreamingTests.__name__ = "ActualReplayStreamingTests"
    globals()[ActualReplayStreamingTests.__name__] = ActualReplayStreamingTests


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--crash-child":
    crash_child(sys.argv[2], sys.argv[3])
else:
    add_actual_replay_tests()
    if __name__ == "__main__":
        unittest.main()
