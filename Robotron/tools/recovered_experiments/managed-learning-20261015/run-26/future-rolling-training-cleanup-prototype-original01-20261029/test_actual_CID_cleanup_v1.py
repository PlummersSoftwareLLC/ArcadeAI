"""Prospective cleanup regressions; default inert, no production imports.

Only selected, verbatim AST methods from the archived parent/candidate execute.
All sockets, journal persistence and timers are test collaborators. Threads and
queues are real and owned by this fixture. No MAME, API, model, unit or signals.
"""
import ast
from collections import deque
import hashlib
from pathlib import Path
import queue
import socket
import sys
import threading
import time
import traceback
import types
import unittest


HERE = Path(__file__).resolve().parent
PARENT_SHA = "b776ec40b5275fd0b02ea13e0a7203e5e4fcc96eaf3ff8d80640f9fe2b8132d5"
CANDIDATE_SHA = "1a272cd3cd5d73d873c9722ef30bda6aacc84e04d21ed6eb0ec2e5a19f63e045"
JOURNAL_SHA = "4c68e5d9669047abb6cf78cf4354fe8322ee1dd83871439fb19e537b6c31c3ba"


def selected_class(source, name, methods, namespace):
    tree = ast.parse(source)
    original = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    body = [n for n in original.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name in methods]
    if {n.name for n in body} != set(methods):
        raise AssertionError("Missing actual source method")
    selected = ast.ClassDef(name=name, bases=[], keywords=[], body=body,
                           decorator_list=[], type_params=[])
    code = ast.fix_missing_locations(ast.Module(body=[selected], type_ignores=[]))
    exec(compile(code, "<selected-verbatim-actual-methods>", "exec"), namespace)
    return namespace[name]


def eventually(predicate, bound=1.0):
    end = time.monotonic() + bound
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.001)
    raise AssertionError("Owned fixture did not reach its expected state")


class TimerRecord:
    def __init__(self, delay, callback, on_start):
        self.delay, self.callback, self.on_start = delay, callback, on_start
        self.started = False

    def start(self):
        self.started = True
        self.on_start(self)

    def fire(self):
        if not self.started:
            raise AssertionError("Unstarted fixture timer")
        self.callback()


class EarlyDisconnectSocket:
    def setblocking(self, _):
        raise ConnectionError("fixture deliberate orderly teardown entry")

    def shutdown(self, _):
        pass

    def close(self):
        pass


class JournalFixture:
    """Real GameJournal.disconnect plus controlled persistence boundary."""
    def __init__(self, actual, *, block=False, fail=False):
        self.lock = threading.Lock()
        self.active = {0: {"generation": "old", "score": 123456789}}
        self.retirements = {0: {"generation": "old"}}
        self.finished = []
        self.entered, self.release = threading.Event(), threading.Event()
        self.actual, self.block, self.fail = actual, block, fail

    def _finish(self, game, context, reason, complete):
        if self.fail:
            raise OSError("fixture journal persistence failure")
        self.finished.append((game.copy(), context(), reason, complete))

    def disconnect(self, cid, context):
        self.entered.set()
        if self.block and not self.release.wait(2):
            raise AssertionError("Fixture failed to release its journal boundary")
        self.actual(self, cid, context)

    def add_generation(self, cid):
        with self.lock:
            self.active[cid] = {"generation": "new", "score": 19}
            self.retirements[cid] = {"generation": "new"}


class ShortEvent:
    """Accelerated timeout collaborator; records the actual requested bound."""
    def __init__(self):
        self.event = threading.Event()
        self.wait_called = threading.Event()
        self.requested_timeout = None

    def set(self):
        self.event.set()

    def is_set(self):
        return self.event.is_set()

    def wait(self, timeout=None):
        self.requested_timeout = timeout
        self.wait_called.set()
        return self.event.wait(min(float(timeout), .05))


class AsyncFixture:
    """Real enqueue/reset/consumer methods, with no agent or replay body load."""
    def __init__(self, source, *, block_remove=False, short_events=False,
                 enqueue_error=False, consumer_error=False):
        self.events, self.log = [], []

        def event_factory():
            event = ShortEvent() if short_events else threading.Event()
            self.events.append(event)
            return event

        selected = selected_class(source, "AsyncReplayBuffer", {
            "_enqueue_preserving", "step_async", "reset_client_async", "remove_client", "_consume"
        }, {"queue": queue, "threading": types.SimpleNamespace(Event=event_factory),
            "deque": deque, "print": lambda *a, **k: self.log.append(a)})
        self.actual = selected.__new__(selected)
        self.actual.queue = queue.Queue(maxsize=32)
        self.actual.running = True
        self.actual.batch_size = 32
        self.actual._lookback = 8

        class RaisingPop(dict):
            def pop(self, *a, **k):
                raise RuntimeError("fixture reset consumer failed")

        self.actual._client_indices = (RaisingPop({0: deque([7])}) if consumer_error
                                       else {0: deque([7])})
        self.actual._episode_indices = {0: deque([7])}
        self.actual.agent = types.SimpleNamespace(step=lambda value: int(value))
        self.entered, self.release, self.enqueued = (threading.Event() for _ in range(3))
        self.block_remove, self.enqueue_error = block_remove, enqueue_error
        self.consumer = None

    def remove_client(self, cid):
        self.entered.set()
        if self.block_remove and not self.release.wait(2):
            raise AssertionError("Fixture failed to release its reset boundary")
        if self.enqueue_error:
            raise OSError("fixture reset enqueue failed")
        ack = self.actual.remove_client(cid)
        self.enqueued.set()
        return ack

    def step(self, cid, index):
        self.actual.step_async(index, client_id=cid)

    def start(self):
        if self.consumer is None:
            self.consumer = threading.Thread(target=self.actual._consume, daemon=True)
            self.consumer.start()

    def stop(self):
        self.release.set()
        self.start()
        self.actual.running = False
        self.consumer.join(1)
        if self.consumer.is_alive():
            raise AssertionError("Fixture consumer did not terminate")


class HandlerFixture:
    def __init__(self, source, *, journal=None, buffer=None):
        self.timers, self.log, self.errors = [], [], []
        self.timer_allocator_observations = []
        metrics = types.SimpleNamespace(client_count=1,
            ratchet_note_eval_abandoned=lambda _: None)

        def timer_factory(delay, callback):
            def on_start(timer):
                self.timers.append(timer)
                self.timer_allocator_observations.append(self.server._alloc_id())
            return TimerRecord(delay, callback, on_start)

        selected = selected_class(source, "SocketServer", {
            "handle_client", "_alloc_id", "_cleanup", "_sync_client_count_locked",
            "_parse_client_handshake"
        }, {"time": time, "threading": types.SimpleNamespace(
                Timer=timer_factory, current_thread=threading.current_thread),
            "socket": socket, "traceback": traceback, "sys": sys, "metrics": metrics,
            "print": lambda *a, **k: self.log.append(a)})
        self.server = selected.__new__(selected)
        s = self.server
        s.client_lock = threading.Lock()
        s.client_states = {0: {"raw_score_prev": 23456789, "raw_wave_prev": 1,
            "score_offset": 100000000, "wave_offset": 255, "game_uid": 71,
            "game_t0": 10., "eval_only": False, "client_slot": 0}}
        s.clients, s._unwrap_stash, s._eval_override = {}, {}, {0: False}
        s.metrics = metrics
        s.shutdown_event = threading.Event()
        s._response_timing = None
        s._rejected_gaps = types.SimpleNamespace(event=lambda *a, **k: 1)
        s._exception_log_lock = threading.Lock()
        s._ensure_preview_client_selected_locked = lambda: (None, False)
        s._clear_preview_cache = lambda: None
        s._journal_context = lambda cs: {"slot": cs["client_slot"], "game_uid": cs["game_uid"]}
        s._fail_inference_only = lambda reason: self.log.append((reason,))
        s.game_journal, s.async_buffer = journal, buffer
        self.journal, self.buffer = journal, buffer
        self.original = None

    def start(self):
        def run():
            try:
                self.server.handle_client(EarlyDisconnectSocket(), 0)
            except BaseException as exc:
                self.errors.append(exc)
        self.original = threading.Thread(target=run, daemon=True)
        self.server.clients[0] = self.original
        self.original.start()
        return self.original

    def join(self):
        self.original.join(2)
        if self.original.is_alive() or self.errors:
            raise AssertionError(("Handler fixture failed", self.errors))

    def close(self):
        if self.journal is not None:
            self.journal.release.set()
        if self.buffer is not None:
            self.buffer.release.set()
            self.buffer.start()
        if self.original is not None:
            self.original.join(2)
            if self.original.is_alive():
                raise AssertionError("Fixture handler leaked")
        if self.buffer is not None:
            self.buffer.stop()


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = (HERE / "socket_server_parent_b776.py").read_bytes()
        candidate = (HERE / "socket_server_cid_cleanup_candidate_v1.py").read_bytes()
        if hashlib.sha256(parent).hexdigest() != PARENT_SHA:
            raise AssertionError("Archived actual parent source changed")
        if hashlib.sha256(candidate).hexdigest() != CANDIDATE_SHA:
            raise AssertionError("Unselected candidate source changed")
        cls.parent, cls.candidate = parent.decode(), candidate.decode()
        journal_raw = (HERE / "game_journal_parent.py").read_bytes()
        if hashlib.sha256(journal_raw).hexdigest() != JOURNAL_SHA:
            raise AssertionError("Archived actual GameJournal source changed")
        actual_disconnect = selected_class(journal_raw.decode(), "GameJournal", {"disconnect"}, {}).disconnect
        cls.disconnect = staticmethod(actual_disconnect)

    def harness(self, source, **kwargs):
        h = HandlerFixture(source, **kwargs)
        self.addCleanup(h.close)
        return h

    def test_actual_journal_race_old_loses_replacement_candidate_reserves_CID(self):
        for source, expected_next in ((self.parent, 0), (self.candidate, 1)):
            with self.subTest(expected_next=expected_next):
                journal = JournalFixture(self.disconnect, block=True)
                h = self.harness(source, journal=journal)
                h.start()
                self.assertTrue(journal.entered.wait(1))
                new_cid = h.server._alloc_id()
                self.assertEqual(new_cid, expected_next)
                h.server.client_states[new_cid] = {"generation": "new"}
                h.server.clients[new_cid] = threading.Thread()
                journal.add_generation(new_cid)
                journal.release.set()
                h.join()
                self.assertEqual(new_cid in journal.active, source == self.candidate)
                self.assertEqual(new_cid in journal.retirements, source == self.candidate)
                finished = journal.finished[0][0]
                self.assertEqual(finished["generation"], "old" if source == self.candidate else "new")

    def test_actual_replay_race_old_reset_erases_replacement_candidate_preserves_it(self):
        for source, expected_next in ((self.parent, 0), (self.candidate, 1)):
            with self.subTest(expected_next=expected_next):
                buffer = AsyncFixture(self.parent, block_remove=True)
                h = self.harness(source, buffer=buffer)
                h.start()
                self.assertTrue(buffer.entered.wait(1))
                new_cid = h.server._alloc_id()
                self.assertEqual(new_cid, expected_next)
                buffer.step(new_cid, 99)
                buffer.release.set()
                self.assertTrue(buffer.enqueued.wait(1))
                buffer.start()
                h.join()
                eventually(lambda: buffer.events[0].is_set())
                self.assertEqual(new_cid in buffer.actual._client_indices, source == self.candidate)
                self.assertEqual(new_cid in buffer.actual._episode_indices, source == self.candidate)
                if source == self.candidate:
                    self.assertEqual(list(buffer.actual._client_indices[new_cid]), [99])

    def test_actual_FIFO_ack_is_after_reset_processing_not_queue_admission(self):
        buffer = AsyncFixture(self.parent)
        buffer.step(0, 10)
        h = self.harness(self.candidate, buffer=buffer)
        h.start()
        self.assertTrue(buffer.enqueued.wait(1))
        ack = buffer.events[0]
        self.assertFalse(ack.is_set())
        self.assertEqual(list(buffer.actual._client_indices[0]), [7])
        self.assertEqual(h.server._alloc_id(), 1)
        self.assertIs(h.server.clients[0], h.original)
        # Adversarial direct enqueue also demonstrates FIFO reset precedes
        # later commands; the real allocator is still refusing this CID.
        buffer.step(0, 99)
        buffer.start()
        h.join()
        eventually(lambda: list(buffer.actual._client_indices.get(0, [])) == [99])
        self.assertTrue(ack.is_set())
        self.assertEqual(list(buffer.actual._episode_indices[0]), [99])
        self.assertIsNone(h.server.clients[0])
        self.assertEqual(h.server._alloc_id(), 0)
        self.assertEqual(h.timer_allocator_observations, [1])

    def assert_reserved_after_exit(self, h):
        h.join()
        self.assertFalse(h.original.is_alive())
        self.assertIs(h.server.clients[0], h.original)
        self.assertEqual(h.server._alloc_id(), 1)
        h.server._cleanup()
        self.assertIs(h.server.clients[0], h.original)
        self.assertEqual(h.server._alloc_id(), 1)

    def test_journal_failure_keeps_dead_Thread_reserved(self):
        journal = JournalFixture(self.disconnect, fail=True)
        h = self.harness(self.candidate, journal=journal)
        h.start()
        self.assert_reserved_after_exit(h)

    def test_reset_enqueue_exception_keeps_dead_Thread_reserved(self):
        buffer = AsyncFixture(self.parent, enqueue_error=True)
        h = self.harness(self.candidate, buffer=buffer)
        h.start()
        self.assert_reserved_after_exit(h)

    def test_reset_timeout_keeps_dead_Thread_reserved(self):
        buffer = AsyncFixture(self.parent, short_events=True)
        h = self.harness(self.candidate, buffer=buffer)
        h.start()
        self.assert_reserved_after_exit(h)
        self.assertEqual(buffer.events[0].requested_timeout, 5.0)
        self.assertFalse(buffer.events[0].is_set())
        self.assertTrue(any("acknowledgment timed out" in str(row) for row in h.log))

    def test_actual_consumer_exception_cannot_ack_or_authorize_reuse(self):
        buffer = AsyncFixture(self.parent, short_events=True, consumer_error=True)
        buffer.start()
        h = self.harness(self.candidate, buffer=buffer)
        h.start()
        self.assert_reserved_after_exit(h)
        self.assertTrue(any("fixture reset consumer failed" in str(row) for row in buffer.log))
        self.assertFalse(buffer.events[0].is_set())

    def test_old_handler_and_owned_timer_cannot_clear_replacement_Thread(self):
        journal = JournalFixture(self.disconnect, block=True)
        h = self.harness(self.candidate, journal=journal)
        h.start()
        self.assertTrue(journal.entered.wait(1))
        replacement = threading.Thread()
        h.server.clients[0] = replacement
        journal.release.set()
        h.join()
        self.assertIs(h.server.clients[0], replacement)
        self.assertEqual(len(h.timers), 1)
        self.assertEqual(h.timers[0].delay, 1.0)
        h.timers[0].fire()
        self.assertIs(h.server.clients[0], replacement)
        self.assertEqual(h.server._alloc_id(), 1)

    def test_slot_role_parser_and_100M_stash_remain_actual_unchanged_semantics(self):
        old = self.harness(self.parent)
        new = self.harness(self.candidate)
        for slot in range(192):
            for mode in (1, 2):
                raw = (mode << 14) | (slot << 1) | (slot == 0)
                expected = (slot == 0, slot, mode)
                self.assertEqual(old.server._parse_client_handshake(raw), expected)
                self.assertEqual(new.server._parse_client_handshake(raw), expected)
        old.start(); new.start()
        old.join(); new.join()
        for key in ("raw_score_prev", "raw_wave_prev", "score_offset", "wave_offset", "game_uid"):
            self.assertEqual(old.server._unwrap_stash[0][key], new.server._unwrap_stash[0][key])
        self.assertEqual(new.server._unwrap_stash[0]["score_offset"], 100000000)
        # Every non-handler method remains byte-identical, including gameplay,
        # journal admission, score unwrap, slot roles and replay consumption.
        trees = [ast.parse(text) for text in (self.parent, self.candidate)]
        classes = [{n.name: n for n in tree.body if isinstance(n, ast.ClassDef)} for tree in trees]
        for class_name, before in classes[0].items():
            after = classes[1][class_name]
            for before_method in before.body:
                if isinstance(before_method, ast.FunctionDef):
                    if class_name == "SocketServer" and before_method.name == "handle_client":
                        continue
                    after_method = next(n for n in after.body if isinstance(n, ast.FunctionDef)
                                        and n.name == before_method.name)
                    self.assertEqual(ast.dump(before_method, include_attributes=False),
                                     ast.dump(after_method, include_attributes=False))


if __name__ == "__main__":
    unittest.main()
