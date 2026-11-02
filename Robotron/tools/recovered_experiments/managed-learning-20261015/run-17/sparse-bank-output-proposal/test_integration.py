"""CPU-only proposed-source tests; no production installer or live-bank I/O."""
import ast
import copy
import importlib.util
import io
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

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[3]
sys.path.insert(0, str(HERE / "proposed"))
import bank_output as helper


def disk_owner(proposed=False, stream=False):
    path = HERE / ("proposed" if proposed else "before") / "replay_buffer.py"
    tree = ast.parse(path.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "PrioritizedReplayBuffer")
    names = {"_write_bank_generation", "_resolve_bank_directory", "_fsync_directory"}
    body = [copy.deepcopy(node) for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = dict(np=np, os=os, uuid=uuid, shutil=shutil, json=json,
                     write_bank_array=helper.write_bank_array)
    test_class = ast.ClassDef(name="DiskOwner", bases=[], keywords=[], body=body,
                             decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[test_class], type_ignores=[])),
                 str(path), "exec"), namespace)
    owner = namespace["DiskOwner"]()
    owner._BANK_SCHEMA = "robotron-bank-generation-v1"
    owner._bank_stream_output = stream
    owner._bank_output_telemetry = helper.BankOutputTelemetry(stream)
    return owner


def snapshot():
    bits = np.asarray([0, 0x80000000, 1, 0x80000001, 0x7f800000, 0xff800000,
        0x7fc01234, 0x7fa05678, 0x007fffff, 0x00800000, 0x7f7fffff, 0xff7fffff] * 2,
        dtype=np.uint32)
    states = bits.view(np.float32).reshape(6, 4).copy()
    arrays = dict(states=states, next_states=states[::-1].copy(),
        actions=np.arange(6, dtype=np.int64), rewards=bits[:6].view(np.float32).copy(),
        dones=np.asarray([0, 1] * 3, dtype=np.float32),
        horizons=np.asarray([1, 2, 3] * 2, dtype=np.int32),
        is_expert=np.asarray([0, 1] * 3, dtype=np.uint8),
        actor_kind=np.asarray([0, 1, 2] * 2, dtype=np.uint8))
    meta = dict(ep_len=np.asarray([2, 0, 4], dtype=np.int32),
        ep_score=np.asarray([100, 0, 200], dtype=np.float64),
        ep_game=np.asarray([91, 92, 93], dtype=np.int64),
        ep_level=np.asarray([1, 1, 2], dtype=np.int32),
        stale_age=np.int64(30), stale_age_normal=np.int64(100),
        stride=np.int64(7), state_size=np.int64(4), captured_adds=np.int64(1000),
        mutation_generation=np.int64(5))
    return dict(bank="hof", count=3, stride=7, total=6, arrays=arrays, meta=meta,
                revision=5, epoch=0, last_admit=970)


def selected(owner, path):
    return Path(owner._resolve_bank_directory("hof", str(path))[0])


def child_crash(path, stream, phase):
    owner = disk_owner(proposed=True, stream=stream)
    original = os.replace
    def crash(source, destination):
        if phase == "after_replace":
            original(source, destination)
        os._exit(73)
    with patch("os.replace", side_effect=crash):
        owner._write_bank_generation(snapshot(), path)
    raise AssertionError("Crash point was not reached")


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_explicit_flag_default_off_and_unavailable_optin_fails(self):
        for value in (None, "", "0", "false", "off", "no"):
            self.assertFalse(helper.stream_output_enabled({} if value is None
                else {"DQN_STREAM_BANK_OUTPUT": value}))
        for value in ("1", "true", "yes", "on"):
            self.assertTrue(helper.stream_output_enabled({"DQN_STREAM_BANK_OUTPUT": value}))
        with self.assertRaises(ValueError):
            helper.stream_output_enabled({"DQN_STREAM_BANK_OUTPUT": "sometimes"})
        with patch.object(helper.os, "pwrite", None):
            self.assertFalse(helper.stream_output_enabled({}))
            with self.assertRaises(RuntimeError):
                helper.stream_output_enabled({"DQN_STREAM_BANK_OUTPUT": "1"})

    def test_original_atomic_capture_priority_epoch_and_loader_ast_unchanged(self):
        def methods(path):
            root = ast.parse(path.read_text())
            cls = next(node for node in root.body if isinstance(node, ast.ClassDef)
                       and node.name == "PrioritizedReplayBuffer")
            return {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
        before, after = [methods(HERE / name / "replay_buffer.py") for name in ("before", "proposed")]
        changed = {name for name in before if ast.dump(before[name]) != ast.dump(after[name])}
        self.assertEqual(changed, {"__init__", "get_bank_persistence_stats", "_write_bank_generation"})
        old, new = copy.deepcopy(before["_write_bank_generation"]), copy.deepcopy(after["_write_bank_generation"])
        old_loop = next(node for node in ast.walk(old) if isinstance(node, ast.For)
                        and isinstance(node.target, ast.Tuple))
        new_loop = next(node for node in ast.walk(new) if isinstance(node, ast.For)
                        and isinstance(node.target, ast.Tuple))
        self.assertEqual(ast.dump(old_loop.body[0]), ast.dump(new_loop.body[0]))
        self.assertEqual(len(new_loop.body), 2)
        self.assertEqual(new_loop.body[1].value.func.id, "write_bank_array")
        new_loop.body = copy.deepcopy(old_loop.body)
        self.assertEqual(ast.dump(old), ast.dump(new))
        self.assertEqual((HERE / "before/pipeline_telemetry.py").read_bytes(),
                         (GAME / "Scripts/dqn/pipeline_telemetry.py").read_bytes())

    def test_both_routes_full_npy_bytes_match_original_and_phase_counts(self):
        value = snapshot()
        original = disk_owner(); original_path = self.root / "original"
        original._write_bank_generation(value, str(original_path))
        old_selected = selected(original, original_path)
        for stream in (False, True):
            owner, path = disk_owner(True, stream), self.root / str(stream)
            context = patch.object(np.lib.format, "open_memmap", side_effect=AssertionError("output mmap"))
            if stream:
                context.start()
            try:
                owner._write_bank_generation(value, str(path))
            finally:
                if stream:
                    context.stop()
            new_selected = selected(owner, path)
            for field in value["arrays"]:
                self.assertEqual((old_selected / f"hof_{field}.npy").read_bytes(),
                                 (new_selected / f"hof_{field}.npy").read_bytes())
            with np.load(old_selected / "hof_meta.npz") as a, np.load(new_selected / "hof_meta.npz") as b:
                self.assertEqual(a.files, b.files)
                for key in a.files:
                    self.assertEqual(a[key].tobytes(), b[key].tobytes())
            stats = owner._bank_output_telemetry.snapshot()
            self.assertEqual(stats["backend"], "stream" if stream else "memmap")
            self.assertEqual(stats["totals"]["write"]["count"], 8)
            self.assertEqual(stats["totals"]["file_fsync"]["count"], 8)
            self.assertEqual(stats["totals"]["file_close"]["count"], 8)
            self.assertEqual(stats["totals"]["mmap_flush"]["count"], 0 if stream else 8)
            self.assertEqual(stats["totals"]["mmap_close"]["count"], 0 if stream else 8)
            self.assertEqual(stats, owner._bank_output_telemetry.snapshot())
            self.assertLessEqual(len(stats["recent"]), 32)

    def test_actual_memmap_phase_order_preserved_and_flush_error_closes(self):
        calls = []
        class Output:
            @property
            def _mmap(self):
                return self
            def __setitem__(self, key, value):
                calls.append("assign")
            def flush(self):
                calls.append("flush")
            def close(self):
                calls.append("unmap")
        class ReadFile:
            def fileno(self):
                return 1
            def close(self):
                calls.append("file_close")
        def create(*args, **kwargs):
            calls.append("create"); return Output()
        def file_open(*args):
            calls.append("file_open"); return ReadFile()
        with patch.object(np.lib.format, "open_memmap", side_effect=create), \
             patch("bank_output.open", side_effect=file_open, create=True), \
             patch.object(helper.os, "fsync", side_effect=lambda _: calls.append("fsync")):
            helper.write_bank_array("unused", np.ones((2, 4), dtype=np.float32), count=2,
                stride=4, lengths=[1, 1], stream_output=False,
                telemetry=helper.BankOutputTelemetry(False), bank="hof", field="states")
        self.assertEqual(calls, ["create", "assign", "assign", "flush", "unmap",
                                 "file_open", "fsync", "file_close"])
        stats = helper.BankOutputTelemetry(False)
        with patch.object(np.lib.format, "open_memmap", return_value=Output()), \
             patch.object(Output, "flush", side_effect=OSError("flush error")):
            with self.assertRaisesRegex(OSError, "flush error"):
                helper.write_bank_array("unused", np.ones((1, 4), dtype=np.float32), count=1,
                    stride=4, lengths=[1], stream_output=False, telemetry=stats,
                    bank="hof", field="states")
        self.assertEqual(stats.snapshot()["totals"]["mmap_flush"]["errors"], 1)
        self.assertEqual(stats.snapshot()["totals"]["mmap_close"]["count"], 1)

    def test_stream_bounds_short_writes_invalid_inputs_and_file_fsync_failure(self):
        real = os.pwrite; writes = []
        def short(fd, data, offset):
            writes.append(len(data)); return real(fd, data[:5], offset)
        kwargs = dict(count=1, stride=4, lengths=[2], stream_output=True,
                      telemetry=helper.BankOutputTelemetry(True), bank="hof", field="states")
        source = np.arange(8, dtype=np.float32).reshape(2, 4)
        with patch.object(helper.os, "pwrite", side_effect=short):
            helper.write_bank_array(self.root / "short.npy", source, **kwargs)
        self.assertLessEqual(max(writes), helper.CHUNK_BYTES)
        np.testing.assert_array_equal(np.load(self.root / "short.npy")[:2], source)
        for invalid in (source[:, ::-1], np.empty((2, 4), dtype=object)):
            with self.assertRaises(ValueError):
                helper.write_bank_array(self.root / "invalid.npy", invalid, **kwargs)
        self.assertFalse((self.root / "invalid.npy").exists())
        owner, path = disk_owner(True, True), self.root / "bank"
        owner._write_bank_generation(snapshot(), str(path))
        pointer = (path / "CURRENT.json").read_bytes()
        with patch.object(helper.os, "fsync", side_effect=OSError("fsync failed")):
            with self.assertRaisesRegex(OSError, "fsync failed"):
                owner._write_bank_generation(snapshot(), str(path))
        self.assertEqual((path / "CURRENT.json").read_bytes(), pointer)
        self.assertEqual(len(list((path / "generations").iterdir())), 1)

    def test_both_backends_hard_crash_before_after_current_complete_selection(self):
        for stream in (False, True):
            for phase in ("before_replace", "after_replace"):
                path = self.root / f"{stream}-{phase}"
                owner = disk_owner(True, stream)
                owner._write_bank_generation(snapshot(), str(path))
                old = selected(owner, path)
                result = subprocess.run([sys.executable, "-Xgil=0", str(Path(__file__).resolve()),
                    "--crash-child", str(path), str(int(stream)), phase], timeout=20,
                    env=dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2",
                             OPENBLAS_NUM_THREADS="2"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(result.returncode, 73, result.stderr.decode())
                current = selected(owner, path)
                self.assertEqual(current == old, phase == "before_replace")
                self.assertTrue(old.is_dir())
                for field in snapshot()["arrays"]:
                    self.assertEqual((old / f"hof_{field}.npy").read_bytes(),
                                     (current / f"hof_{field}.npy").read_bytes())


def add_actual_replay_tests():
    sys.path.insert(0, str(GAME / "Scripts"))
    import torch
    torch.set_num_threads(2)
    sys.modules["dqn.bank_output"] = helper
    spec = importlib.util.spec_from_file_location("dqn.proposed_bank_replay", HERE / "proposed/replay_buffer.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    from dqn import test_bank_persistence as base
    from dqn.run_telemetry import PipelineSnapshotCache, pipeline_report_fields
    for enabled in (False, True):
        class ActualBankTests(base.BankPersistenceTests):
            STREAM_OUTPUT = enabled
            def setUp(self):
                current = patch.object(base, "module", module)
                current.start(); self.addCleanup(current.stop)
                flag = patch.dict(os.environ, DQN_STREAM_BANK_OUTPUT=str(int(self.STREAM_OUTPUT)))
                flag.start(); self.addCleanup(flag.stop)
                super().setUp()

            def test_phase_snapshot_acquires_neither_replay_nor_writer_lock(self):
                saved = self.memory._bank_output_telemetry
                memory = self.memory
                class Spy:
                    def snapshot(self):
                        for lock in (memory.lock, memory._bank_writer_lock):
                            if not lock.acquire(blocking=False):
                                raise AssertionError("Bank getter nested another lock")
                            lock.release()
                        return saved.snapshot()
                self.memory._bank_output_telemetry = Spy()
                self.assertEqual(self.memory.get_bank_persistence_stats()["output"]["backend"],
                                 "stream" if self.STREAM_OUTPUT else "memmap")

            def test_raw_reporting_forwards_status_without_csv_schema_change(self):
                self.memory._save_hof(self.memory._hof_dir, False)
                class Agent:
                    memory = self.memory
                    def pipeline_telemetry_snapshot(self, reset=False):
                        return dict(available=False)
                value = PipelineSnapshotCache(interval_s=0).get(Agent())
                fields = pipeline_report_fields(value)
                self.assertEqual(json.loads(fields["bank_persistence_json"])["output"],
                                 value["bank"]["output"])
                self.assertFalse(torch.cuda.is_initialized())

            def test_blocked_actual_output_phase_allows_replay_and_live_status(self):
                entered, release, finished = threading.Event(), threading.Event(), threading.Event()
                memory = self.memory; memory._ephof_enabled = False
                errors = []
                original_map, original_write = np.lib.format.open_memmap, os.pwrite
                class BlockedMap:
                    def __init__(self, output):
                        self.output = output
                    def __setitem__(self, key, value):
                        self.output[key] = value
                    @property
                    def _mmap(self):
                        return self.output._mmap
                    def flush(self):
                        entered.set()
                        if not release.wait(5):
                            raise TimeoutError("Test flush not released")
                        self.output.flush()
                def mapping(path, *args, **kwargs):
                    output = original_map(path, *args, **kwargs)
                    return BlockedMap(output) if str(path).endswith("hof_states.npy") else output
                def writing(fd, data, offset):
                    if (offset >= 128 and not entered.is_set()
                            and os.readlink(f"/proc/self/fd/{fd}").endswith("hof_states.npy")):
                        entered.set()
                        if not release.wait(5):
                            raise TimeoutError("Test write not released")
                    return original_write(fd, data, offset)
                def replay_work():
                    try:
                        for value in range(32):
                            state = np.full(4, value, dtype=np.float32)
                            memory.add(state, 2, 1., state + 1, False)
                        self.assertEqual(memory.sample(8)[0].shape, (8, 4))
                        active = memory.get_bank_persistence_stats()["output"]["active"]
                        self.assertEqual(active["phase"], "write" if self.STREAM_OUTPUT else "mmap_flush")
                        self.assertEqual(active["bank"], "hof")
                        self.assertEqual(active["field"], "states")
                    except BaseException as error:
                        errors.append(error)
                    finally:
                        finished.set()
                context = patch.object(helper.os, "pwrite", side_effect=writing) if self.STREAM_OUTPUT else \
                    patch.object(np.lib.format, "open_memmap", side_effect=mapping)
                with context:
                    memory.save_banks_if_dirty()
                    self.assertTrue(entered.wait(5))
                    thread = threading.Thread(target=replay_work); thread.start()
                    try:
                        self.assertTrue(finished.wait(1), "Output I/O blocked replay/status")
                        self.assertEqual(errors, [])
                    finally:
                        release.set(); thread.join(5); memory._wait_bank_writer(5)
        ActualBankTests.__name__ = "ActualBankStreamTests" if enabled else "ActualBankMemmapTests"
        globals()[ActualBankTests.__name__] = ActualBankTests


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--crash-child":
    child_crash(sys.argv[2], bool(int(sys.argv[3])), sys.argv[4])
else:
    add_actual_replay_tests()
    if __name__ == "__main__":
        unittest.main()
