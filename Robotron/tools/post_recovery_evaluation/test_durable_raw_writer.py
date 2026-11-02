"""Fault and ordering tests for the actual bounded evidence writer."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

from . import durable_raw_writer as durable
from . import round_observer_v6 as worker
from .round_observer_client_v7 import DedicatedMainHealth


class DurableWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.binding = dict(job={'path': '/engineering-only'}, nonce='a'*32, owner={'pid': os.getpid()})
        self.writer = None

    def tearDown(self):
        if self.writer is not None and not self.writer.closing:
            try:
                self.writer.close(successful=False)
            except ValueError:
                pass
        self.temp.cleanup()

    def create(self, fsync=os.fsync):
        self.writer = durable.DurableRawWriter(self.directory, self.binding,
            pin=worker.pin, identity=worker.identity, fsync=fsync)
        return self.writer

    def submit(self, writer, index, kind='sample'):
        return writer.submit(self.directory/('%s-%06d.json' % (kind, index)),
            dict(snapshot=dict(monotonic_s=time.monotonic())), kind=kind, index=index)

    def test_700ms_fsync_stall_does_not_block_sampling_or_fake_readiness(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def delayed(fd):
            calls.append(fd)
            if len(calls) == 1:
                entered.set()
                self.assertTrue(release.wait(3))
            os.fsync(fd)

        writer = self.create(delayed)
        pins = [self.submit(writer, 0)]
        self.assertTrue(entered.wait(2))
        self.assertIsNone(writer.readiness())
        captured = [time.monotonic()]
        try:
            for index in range(1, 5):
                time.sleep(.2)
                started = time.monotonic()
                pins.append(self.submit(writer, index))
                self.assertLess(time.monotonic()-started, .5)
                captured.append(time.monotonic())
            self.assertLess(max(b-a for a, b in zip(captured, captured[1:])), .5)
            self.assertEqual(writer.committed, 0)
        finally:
            release.set()
        for index in range(5, 101):
            pins.append(self.submit(writer, index))
        seal_pin = writer.close(successful=True)
        seal = worker.read(worker.checked(seal_pin))
        self.assertGreater(seal['maximum_file_fsync_s'], .7)
        self.assertEqual(seal['committed_records'], len(pins))
        self.assertEqual(seal['sample_count'], 101)
        self.assertFalse(writer.thread.is_alive())
        chain = sample_chain = durable.EMPTY_CHAIN
        for index, pin in enumerate(pins):
            descriptor = dict(sequence=index, kind='sample', index=index, record=pin)
            chain = durable.advance(chain, descriptor)
            sample_chain = durable.advance(sample_chain, descriptor)
            row = worker.read(worker.checked(pin))
            self.assertEqual(row['durability_record'], dict(sequence=index, kind='sample', index=index))
        self.assertEqual(seal['chain'], chain)
        self.assertEqual(seal['sample_chain'], sample_chain)
        prefix = worker.read(worker.checked(seal['readiness']))
        self.assertEqual(prefix['sample_count'], 100)
        self.assertEqual(prefix['committed_records'], 100)

    def test_bounded_queue_fails_without_descriptor_leaks_or_success(self):
        entered, release = threading.Event(), threading.Event()

        def stalled(fd):
            entered.set()
            self.assertTrue(release.wait(3))
            os.fsync(fd)

        writer = self.create(stalled)
        self.submit(writer, 0)
        self.assertTrue(entered.wait(2))
        try:
            for index in range(1, 129):
                self.submit(writer, index)
            before = len(list(Path('/proc/self/fd').iterdir()))
            with self.assertRaisesRegex(ValueError, 'queue capacity'):
                self.submit(writer, 129)
            self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), before)
        finally:
            release.set()
        with self.assertRaisesRegex(ValueError, 'queue capacity'):
            writer.close(successful=False)
        self.assertFalse(writer.thread.is_alive())
        self.assertEqual(writer.high_water, 128)
        self.assertEqual(writer.committed, 129)

    def test_io_failure_is_preserved_and_every_owned_descriptor_closed(self):
        def fail(fd):
            raise OSError('injected durability I/O failure')

        before = len(list(Path('/proc/self/fd').iterdir()))
        writer = self.create(fail)
        try:
            self.submit(writer, 0)
        except ValueError:
            pass
        with self.assertRaisesRegex(ValueError, 'injected durability'):
            writer.close(successful=False)
        self.assertFalse(writer.thread.is_alive())
        self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), before)
        self.assertFalse((self.directory/'durability-seal.json').exists())

    def test_success_requires_durable_100_prefix_and_no_reuse(self):
        writer = self.create()
        self.submit(writer, 0)
        with self.assertRaisesRegex(ValueError, 'initial100'):
            writer.close(successful=True)
        self.assertFalse(writer.thread.is_alive())
        with self.assertRaises(ValueError):
            writer.close(successful=False)
        with self.assertRaises(ValueError):
            self.submit(writer, 1)

    def test_path_replacement_fails_instead_of_sealing_wrong_inode(self):
        entered, release = threading.Event(), threading.Event()

        def stalled(fd):
            entered.set()
            self.assertTrue(release.wait(3))
            os.fsync(fd)

        writer = self.create(stalled)
        pinned = self.submit(writer, 0)
        self.assertTrue(entered.wait(2))
        path = Path(pinned['path'])
        path.unlink()
        path.write_text('{}')
        release.set()
        with self.assertRaises(ValueError):
            writer.close(successful=False)
        self.assertFalse((self.directory/'durability-seal.json').exists())

    def test_live_consumer_requires_matching_durable_prefix_and_strict_freshness(self):
        writer = self.create()
        for index in range(100):
            self.submit(writer, index)
        writer.close(successful=True)
        guard = DedicatedMainHealth.__new__(DedicatedMainHealth)
        guard.common = worker
        guard.jobpin = self.binding['job']
        guard.job = dict(nonce=self.binding['nonce'])
        guard.worker_owner = dict(pid=os.getpid(), birth=worker.birth(os.getpid()))
        guard.last_live = guard.initial = None
        # Use a fresh certificate bound to this live consumer, kept immutable.
        cert = worker.read(worker.checked(writer.ready))
        cert['binding']['owner'] = guard.worker_owner
        pin = worker.write(self.directory/'consumer-prefix.json', cert)
        now = time.monotonic()
        live = dict(schema='robotron-round-observer-live-v1', job=guard.jobpin,
            nonce=guard.job['nonce'], owner=guard.worker_owner, state='running',
            updated_monotonic_s=now, observed_samples=100,
            initial=dict(index=99, durable_prefix=pin, durable_ready_monotonic_s=now),
            phase=dict(overlap_pending=False), latest_sample={})
        guard._accept(live)
        for field in ('missing', 'stale', 'changed_prefix', 'early_ready'):
            bad = copy.deepcopy(live)
            if field == 'missing':
                bad['initial'].pop('durable_prefix')
            elif field == 'stale':
                bad['updated_monotonic_s'] -= .6
            elif field == 'changed_prefix':
                bad['initial']['index'] = 98
            else:
                bad['initial']['durable_ready_monotonic_s'] = cert['committed_monotonic_s']-.01
            with self.subTest(field=field), self.assertRaises((ValueError, KeyError)):
                guard._accept(bad)


if __name__ == '__main__':
    unittest.main()
