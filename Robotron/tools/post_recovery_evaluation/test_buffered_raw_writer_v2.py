"""Fault tests for a producer that enqueues bytes without filesystem writes."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

from . import buffered_raw_writer_v2 as buffered
from . import round_observer_v6 as common


class BufferedWriterTests(unittest.TestCase):
    def make(self, directory, **kwargs):
        return buffered.BufferedRawWriter(directory, dict(engineering_only=True),
            pin=common.pin, identity=common.identity, **kwargs)

    def submit(self, writer, index, value=None):
        return writer.submit(writer.directory/('sample-%06d.json' % index),
            dict(snapshot=value if value is not None else dict(step=index)), kind='sample', index=index)

    def test800ms_file_creation_stall_does_not_block_producer_or_fake_durable_readiness(self):
        entered, release = threading.Event(), threading.Event()
        caller = threading.get_ident()
        calls = []

        def delayed(name, *args, **kwargs):
            calls.append(threading.get_ident())
            if name == 'sample-000000.json':
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('Engineering gate not released')
            return os.open(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            writer = self.make(Path(directory), open_file=delayed)
            pending = [self.submit(writer, 0)]
            self.assertTrue(entered.wait(2))
            times = [time.monotonic()]
            try:
                for index in range(1, 5):
                    time.sleep(.2)
                    pending.append(self.submit(writer, index))
                    times.append(time.monotonic())
                self.assertLess(max(b-a for a,b in zip(times,times[1:])), .5)
                self.assertIsNone(writer.readiness())
                self.assertEqual(writer.committed, 0)
                self.assertTrue(all('identity' not in row for row in pending))
                self.assertTrue(all(row['schema'] == 'robotron-queued-raw-record-v2' for row in pending))
            finally:
                release.set()
            for index in range(5, 101):
                pending.append(self.submit(writer, index))
            pin = writer.close(successful=True)
            self.assertFalse(writer.thread.is_alive())
            seal = common.read(common.checked(pin))
            self.assertGreaterEqual(seal['maximum_write_s'], .8)
            self.assertEqual(seal['sample_count'], len(pending))
            chain = buffered.EMPTY_CHAIN
            for original, record in zip(pending, writer.records):
                self.assertEqual(original['sha256'], record['record']['sha256'])
                self.assertEqual(original['bytes'], record['record']['bytes'])
                self.assertEqual(record['sequence'], original['sequence'])
                common.checked(record['record'])
                chain = buffered.advance(chain, record)
            self.assertEqual(chain, seal['chain'])
            self.assertEqual(chain, seal['sample_chain'])
            prefix = common.read(common.checked(seal['readiness']))
            self.assertEqual(prefix['sample_count'], prefix['committed_records'])
            self.assertEqual(prefix['sample_count'], 100)
            # Only the final seal is intentionally written by the closing thread.
            self.assertNotIn(caller, calls[:-1])
            self.assertEqual(calls[-1], caller)

    def test_outstanding_byte_bound_fails_without_a_success_seal(self):
        entered, release = threading.Event(), threading.Event()

        def delayed(name, *args, **kwargs):
            if name == 'sample-000000.json':
                entered.set()
                if not release.wait(3):
                    raise TimeoutError('Engineering gate not released')
            return os.open(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            writer = self.make(Path(directory), open_file=delayed)
            writer.BYTE_CAPACITY = 1024  # Small fixture exercises the actual admission logic.
            self.submit(writer, 0, 'x'*600)
            self.assertTrue(entered.wait(2))
            try:
                with self.assertRaisesRegex(ValueError, 'capacity exceeded'):
                    self.submit(writer, 1, 'x'*600)
                self.assertLessEqual(writer.bytes_high_water, 1024)
            finally:
                release.set()
            with self.assertRaisesRegex(ValueError, 'capacity exceeded'):
                writer.close(successful=False)
            self.assertFalse(writer.thread.is_alive())
            self.assertFalse((Path(directory)/'durability-seal.json').exists())

    def test_create_error_preserves_failure_and_closes_original_directory_fd(self):
        before = len(list(Path('/proc/self/fd').iterdir()))
        def fail(*args, **kwargs):
            raise OSError('injected raw creation failure')
        with tempfile.TemporaryDirectory() as directory:
            writer = self.make(Path(directory), open_file=fail)
            self.submit(writer, 0)
            with self.assertRaisesRegex(ValueError, 'raw creation failure'):
                writer.close(successful=False)
            self.assertFalse(writer.thread.is_alive())
            self.assertFalse((Path(directory)/'durability-seal.json').exists())
        self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), before)

    def test_prefix_and_single_use_rules_cannot_be_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = self.make(Path(directory))
            self.submit(writer, 0)
            with self.assertRaisesRegex(ValueError, 'initial100'):
                writer.close(successful=True)
            self.assertFalse(writer.thread.is_alive())
            with self.assertRaises(ValueError):
                writer.close(successful=False)
            with self.assertRaises(ValueError):
                self.submit(writer, 1)


if __name__ == '__main__':
    unittest.main()
