"""CPU-only durable bank output byte, failure and telemetry regressions."""
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np

from . import bank_output as module


class BankOutputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, path, source, *, stream=True, lengths=(2, 0, 3), stride=5,
              telemetry=None):
        telemetry = telemetry if telemetry is not None else module.BankOutputTelemetry(stream)
        module.write_bank_array(path, source, count=len(lengths), stride=stride,
            lengths=np.asarray(lengths, dtype=np.int32), stream_output=stream,
            telemetry=telemetry, bank="hof", field="states")
        return telemetry

    def test_flag_default_off_explicit_boolean_and_unavailable_error(self):
        for value in (None, "", "0", "false", "NO", " off "):
            env = {} if value is None else {"DQN_STREAM_BANK_OUTPUT": value}
            self.assertFalse(module.stream_output_enabled(env))
        for value in ("1", "true", "YES", " on "):
            self.assertTrue(module.stream_output_enabled({"DQN_STREAM_BANK_OUTPUT": value}))
        with self.assertRaisesRegex(ValueError, "DQN_STREAM_BANK_OUTPUT"):
            module.stream_output_enabled({"DQN_STREAM_BANK_OUTPUT": "unexpected"})
        with patch.object(module.os, "pwrite", None):
            self.assertFalse(module.stream_output_enabled({}))
            with self.assertRaisesRegex(RuntimeError, "pwrite"):
                module.stream_output_enabled({"DQN_STREAM_BANK_OUTPUT": "1"})

    def test_complete_npy_bytes_match_dense_oracle_with_holes_and_special_bits(self):
        # No float arithmetic: retain NaN payloads, signaling bits, signed zero,
        # infinities and subnormals in both native and non-native byte order.
        patterns = [0, 0x80000000, 1, 0x80000001, 0x7f800000, 0xff800000,
                    0x7fc01234, 0x7fa05678, 0x007fffff, 0x00800000,
                    0x7f7fffff, 0xff7fffff, 0x3f800000, 0xbf800000, 0x3f000001]
        sources = [np.asarray(patterns, dtype=order + "u4").view(order + "f4").reshape(5, 3)
                   for order in ("<", ">")]
        sources += [np.arange(15, dtype=dtype).reshape(5, 3)
                    for dtype in (np.int64, np.uint8)]
        sources.append((np.arange(15).reshape(5, 3) % 2).astype(np.bool_))
        for index, source in enumerate(sources):
            dense = np.zeros((15, 3), dtype=source.dtype)
            dense[:2] = source[:2]
            dense[10:13] = source[2:]
            oracle = io.BytesIO()
            np.save(oracle, dense, allow_pickle=False)
            source_bytes = source.tobytes()
            for stream in (False, True):
                with self.subTest(dtype=source.dtype, stream=stream):
                    path = self.root / f"{index}-{stream}.npy"
                    stats = self.write(path, source, stream=stream).snapshot()
                    self.assertEqual(path.read_bytes(), oracle.getvalue())
                    actual = np.load(path, allow_pickle=False)
                    self.assertEqual(actual[2:10].tobytes(), b"\0" * (8 * 3 * source.dtype.itemsize))
                    self.assertEqual(source.tobytes(), source_bytes)
                    self.assertEqual(stats["totals"]["mmap_flush"]["count"], int(not stream))
                    self.assertEqual(stats["totals"]["mmap_close"]["count"], int(not stream))

    def test_invalid_stream_sources_lengths_and_existing_path_fail(self):
        source = np.arange(20, dtype=np.float32).reshape(5, 4)
        for invalid in (source[:, ::-1], source.astype(object)):
            with self.assertRaises(ValueError):
                self.write(self.root / "bad.npy", invalid)
        with self.assertRaises(ValueError):
            self.write(self.root / "bad.npy", source, lengths=(2, 0, 4))
        self.assertFalse((self.root / "bad.npy").exists())
        path = self.root / "existing.npy"
        path.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.write(path, source)
        self.assertEqual(path.read_bytes(), b"keep")

    def test_short_interrupted_writes_preserve_bytes_and_bound_payload_chunks(self):
        original = os.pwrite
        calls, interrupted = [], False
        def short(fd, data, offset):
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise InterruptedError()
            calls.append((offset, len(data)))
            return original(fd, data[:5], offset)
        source = np.arange(48, dtype=np.float32).reshape(12, 4)
        path = self.root / "short.npy"
        with patch.object(module, "CHUNK_BYTES", 19), \
             patch.object(module.os, "pwrite", side_effect=short):
            self.write(path, source, lengths=(12,), stride=16)
        with path.open("rb") as stream:
            self.assertEqual(np.lib.format.read_magic(stream), (1, 0))
            np.lib.format.read_array_header_1_0(stream)
            header_size = stream.tell()
        self.assertTrue(interrupted)
        self.assertLessEqual(max(amount for offset, amount in calls if offset >= header_size), 19)
        dense = np.zeros((16, 4), dtype=np.float32); dense[:12] = source
        expected = io.BytesIO(); np.save(expected, dense, allow_pickle=False)
        self.assertEqual(path.read_bytes(), expected.getvalue())

    def test_zero_progress_payload_write_reports_error_and_closes_descriptor(self):
        original = os.pwrite
        descriptors = []
        def stalled(fd, data, offset):
            if offset > 0:
                descriptors.append(fd)
                return 0
            return original(fd, data, offset)
        stats = module.BankOutputTelemetry(True)
        with patch.object(module.os, "pwrite", side_effect=stalled):
            with self.assertRaisesRegex(OSError, "invalid progress"):
                self.write(self.root / "zero.npy", np.zeros((5, 4), dtype=np.float32), telemetry=stats)
        snap = stats.snapshot()
        self.assertEqual(snap["totals"]["write"]["errors"], 1)
        self.assertEqual(snap["totals"]["file_close"]["count"], 1)
        self.assertIsNone(snap["active"])
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    def test_fsync_failure_is_reported_and_descriptor_is_closed(self):
        descriptors = []
        def fail(fd):
            descriptors.append(fd)
            raise OSError("fsync failed")
        stats = module.BankOutputTelemetry(True)
        with patch.object(module.os, "fsync", side_effect=fail):
            with self.assertRaisesRegex(OSError, "fsync failed"):
                self.write(self.root / "sync.npy", np.zeros((5, 4), dtype=np.float32), telemetry=stats)
        value = stats.snapshot()
        self.assertEqual(value["totals"]["file_fsync"]["errors"], 1)
        self.assertEqual(value["totals"]["file_close"]["count"], 1)
        self.assertIsNone(value["active"])
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    def test_close_failure_propagates_and_counts_failed_close(self):
        original = os.close
        descriptors = []
        def close_then_fail(fd):
            descriptors.append(fd)
            original(fd)
            raise OSError("close failed")
        stats = module.BankOutputTelemetry(True)
        with patch.object(module.os, "close", side_effect=close_then_fail):
            with self.assertRaisesRegex(OSError, "close failed"):
                self.write(self.root / "close.npy", np.zeros((5, 4), dtype=np.float32), telemetry=stats)
        value = stats.snapshot()
        self.assertEqual(value["totals"]["file_close"]["errors"], 1)
        self.assertEqual(value["totals"]["file_fsync"]["errors"], 0)
        self.assertIsNone(value["active"])
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    def test_memmap_flush_failure_still_records_mmap_close(self):
        class Output:
            closed = False
            @property
            def _mmap(self):
                return self
            def __setitem__(self, key, value):
                pass
            def flush(self):
                raise OSError("flush failed")
            def close(self):
                self.closed = True
        output = Output(); stats = module.BankOutputTelemetry(False)
        with patch.object(module.np.lib.format, "open_memmap", return_value=output):
            with self.assertRaisesRegex(OSError, "flush failed"):
                self.write(self.root / "unused.npy", np.zeros((5, 4), dtype=np.float32),
                           stream=False, telemetry=stats)
        self.assertTrue(output.closed)
        self.assertEqual(stats.snapshot()["totals"]["mmap_flush"]["errors"], 1)
        self.assertEqual(stats.snapshot()["totals"]["mmap_close"]["count"], 1)

    def test_telemetry_is_bounded_non_draining_independent_and_live_readable(self):
        stats = module.BankOutputTelemetry(True)
        for _ in range(40):
            with stats.phase("write", bank="hof", field="states", logical_bytes=100, payload_bytes=9):
                pass
        first = stats.snapshot()
        self.assertEqual(first["totals"]["write"]["count"], 40)
        self.assertEqual(first["totals"]["write"]["payload_bytes"], 360)
        self.assertEqual(len(first["recent"]), 32)
        first["totals"]["write"]["count"] = -1
        first["recent"][0]["bank"] = "mutated"
        self.assertEqual(stats.snapshot()["totals"]["write"]["count"], 40)
        self.assertEqual(stats.snapshot()["recent"][0]["bank"], "hof")
        entered, release = threading.Event(), threading.Event()
        def work():
            with stats.phase("file_fsync", bank="ephof", field="next_states"):
                entered.set(); release.wait(5)
        thread = threading.Thread(target=work); thread.start()
        try:
            self.assertTrue(entered.wait(1))
            active = stats.snapshot()["active"]
            self.assertEqual((active["bank"], active["field"], active["phase"]),
                             ("ephof", "next_states", "file_fsync"))
            self.assertGreaterEqual(active["elapsed_host_ms"], 0)
            active["phase"] = "changed"
            self.assertEqual(stats.snapshot()["active"]["phase"], "file_fsync")
        finally:
            release.set(); thread.join(5)
        self.assertIsNone(stats.snapshot()["active"])
        self.assertEqual(stats.snapshot()["totals"]["file_fsync"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
