"""Root-only CPU contracts: actual helper AST, fake clock/Event; no live work.

The final case uses the unchanged registry snapshot AST to retain a prior error.
No production module import, socket, process, replay/model, or real wait occurs.
"""
import argparse
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest


def checked_source(path, expected):
    path = Path(path)
    before = path.lstat()
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns,
                          s.st_ctime_ns, s.st_mode, s.st_uid, s.st_nlink)
    if (path.resolve() != path or not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid() or before.st_nlink != 1
            or not 0 < before.st_size <= 200000):
        raise ValueError("Bounded canonical source required")
    raw = path.read_bytes()
    if identity(before) != identity(path.lstat()) or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Source identity or SHA changed")
    return ast.parse(raw)


class Clock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now


class Event:
    def __init__(self, clock, at=None, *, oversleep=0.0, error_on=None, lie=False):
        self.clock, self.at, self.oversleep = clock, at, oversleep
        self.error_on, self.lie, self.waits = error_on, lie, []
    def is_set(self): return self.at is not None and self.clock.now >= self.at
    def wait(self, timeout):
        self.waits.append(timeout)
        if self.error_on == len(self.waits): raise RuntimeError("fake wait failure")
        if self.is_set(): return True
        end = self.clock.now + timeout
        self.clock.now = min(end, self.at) if self.at is not None and self.clock.now < self.at <= end else end
        self.clock.now += self.oversleep
        return True if self.lie else self.is_set()


class Lock:
    def __enter__(self): return self
    def __exit__(self, *args): return False


class Contracts(unittest.TestCase):
    wait_ack = None
    registry_snapshot = None

    def evaluate(self, at, **options):
        clock = Clock(); event = Event(clock, at, **options)
        result = self.wait_ack(event, clock=clock)
        return result, event, clock

    def test01_immediate_fast_path(self):
        result, event, _ = self.evaluate(0.0)
        self.assertTrue(result['acknowledged']); self.assertFalse(result['grace_used'])
        self.assertEqual(result['elapsed_s'], 0.0)
        self.assertEqual(event.waits, [5.0])

    def test02_initial_boundary(self):
        for at in (4.999, 5.0):
            result, event, _ = self.evaluate(at)
            self.assertFalse(result['grace_used']); self.assertEqual(event.waits, [5.0])

    def test03_grace_and_total_boundary(self):
        for at in (5.001, 6.999, 7.0):
            result, event, _ = self.evaluate(at)
            self.assertTrue(result['grace_used']); self.assertEqual(result['elapsed_s'], at)
            self.assertEqual(event.waits, [5.0, 2.0]); self.assertTrue(event.is_set())

    def test04_missing_ACK_stops_at_seven(self):
        clock = Clock(); event = Event(clock)
        with self.assertRaises(TimeoutError): self.wait_ack(event, clock=clock)
        self.assertEqual(clock.now, 7.0); self.assertEqual(event.waits, [5.0, 2.0])
        self.assertFalse(event.is_set())

    def test05_after_deadline_ACK_rejected(self):
        clock = Clock(); event = Event(clock, 7.001)
        with self.assertRaises(TimeoutError): self.wait_ack(event, clock=clock)
        self.assertEqual(clock.now, 7.0); self.assertFalse(event.is_set())

    def test06_scheduler_overrun_rejected_even_ACK_true(self):
        clock = Clock(); event = Event(clock, 1.0, oversleep=7.0)
        with self.assertRaises(TimeoutError): self.wait_ack(event, clock=clock)
        self.assertTrue(event.is_set()); self.assertEqual(event.waits, [5.0])
        for grace in (False, True):
            clock = Clock()
            class LateObservation:
                waits = 0
                def wait(self, timeout):
                    self.waits += 1
                    clock.now = 5.0 if grace and self.waits == 1 else 6.9
                    return not (grace and self.waits == 1)
                def is_set(self):
                    if grace and self.waits == 1: return False
                    clock.now = 7.001
                    return True
            with self.assertRaises(TimeoutError): self.wait_ack(LateObservation(), clock=clock)

    def test07_wait_errors_propagate(self):
        for phase in (1, 2):
            clock = Clock(); event = Event(clock, error_on=phase)
            with self.assertRaisesRegex(RuntimeError, 'fake wait failure'): self.wait_ack(event, clock=clock)
            self.assertFalse(event.is_set()); self.assertEqual(len(event.waits), phase)

    def test08_clock_invalid_or_backwards_rejected(self):
        for values in ([float('nan')], [False], [0.0, -1.0], [0.0, float('inf')], [0.0, 5.0, 4.0]):
            source = iter(values); event = Event(Clock())
            with self.assertRaises(ValueError): self.wait_ack(event, clock=lambda: next(source))

    def test09_wait_return_without_actual_ACK_never_succeeds(self):
        clock = Clock(); event = Event(clock, lie=True)
        with self.assertRaises(TimeoutError): self.wait_ack(event, clock=clock)
        self.assertFalse(event.is_set()); self.assertEqual(clock.now, 7.0)

    def test10_late_ACK_does_not_clear_old_registry_error(self):
        clock = Clock(); event = Event(clock, 8.0)
        with self.assertRaises(TimeoutError): self.wait_ack(event, clock=clock)
        clock.now = 8.0
        stopped = SimpleNamespace(is_alive=lambda: False, native_id=123)
        row = dict(handler=stopped, timer=stopped, timer_done=SimpleNamespace(is_set=lambda: True),
                   reset_ack=event, recorded=True, journal_ok=True, error='Original connection cleanup failed',
                   cid=91, slot=64, eval_only=False, connection_ns=100, endpoints={}, terminal=None, terminal_sha=None)
        book = SimpleNamespace(lock=Lock(), records={'old': row}, stamp={}, incarnation='unchanged',
                               replay_health=lambda: dict(admission_open=True, consumer_error=None))
        snapshot = self.registry_snapshot(book, 'old')
        self.assertTrue(snapshot['FIFO_reset_executed'])
        self.assertFalse(snapshot['ready_for_external_join'])
        self.assertEqual(snapshot['cleanup_error'], 'Original connection cleanup failed')
        self.assertEqual(row['error'], 'Original connection cleanup failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('helper', 'helper-sha256', 'registry-source', 'registry-sha256', 'report'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    helper = checked_source(args.helper, args.helper_sha256)
    registry = checked_source(args.registry_source, args.registry_sha256)
    selected = [node for node in helper.body if isinstance(node, (ast.FunctionDef, ast.Assign))]
    if [node.name for node in selected if isinstance(node, ast.FunctionDef)] != ['wait_for_fifo_reset_ack']:
        raise ValueError('Exact one-function helper required')
    namespace = dict(math=math, time=SimpleNamespace(monotonic=None))
    exec(compile(ast.Module(body=selected, type_ignores=[]), args.helper, 'exec'), namespace)
    original = next(node for node in registry.body if isinstance(node, ast.ClassDef) and node.name == 'ConnectionCleanupReceipts')
    snapshot = next(node for node in original.body if isinstance(node, ast.FunctionDef) and node.name == 'snapshot')
    snapshot_namespace = dict(copy=copy)
    exec(compile(ast.Module(body=[snapshot], type_ignores=[]), args.registry_source, 'exec'), snapshot_namespace)
    Contracts.wait_ack = staticmethod(namespace['wait_for_fifo_reset_ack'])
    Contracts.registry_snapshot = staticmethod(snapshot_namespace['snapshot'])
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    report = Path(args.report)
    if report.parent.parent != Path(__file__).resolve().parent or not report.parent.name.startswith('Root-actual-grace-CPU-'):
        raise ValueError('Fresh dedicated Root CPU report directory required')
    report.parent.mkdir(exist_ok=False)
    with report.open('x') as stream:
        json.dump(dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
                       failures=len(result.failures), errors=len(result.errors), helper_sha256=args.helper_sha256,
                       registry_sha256=args.registry_sha256, scope='Actual helper and original snapshot AST; fake clock/Event only'), stream, sort_keys=True)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
