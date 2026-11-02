"""New prospective tests only; Root owns execution. No production imports.

Selected actual AsyncReplayBuffer methods execute with a fake agent and real
owned threads/queues. Receipt tests exercise the complete new inert prototype.
No model, API, MAME, process control, source installation or prior9 rerun.
"""
import ast
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import queue
import threading
import time
import types
import unittest

HERE = Path(__file__).resolve().parent
CANDIDATE_SHA = '9e1d3b22925edb97a40cbd8d7338c07fe66da3af8595ec04cd43079e73561867'
RECEIPTS_SHA = '6afbefc6de287177380b790465f2b399fa9f9f03dc56e66a67956b992f773566'


def wait_for(predicate, seconds=2):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.001)
    raise AssertionError('Owned synthetic collaborator did not reach its expected state')


def buffer_class():
    path = HERE/'socket_server_bounded_cleanup_candidate_v2.py'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CANDIDATE_SHA
    parent = next(n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef)
                  and n.name == 'AsyncReplayBuffer')
    names = {'__init__', '_enqueue_preserving', 'step_async', 'reset_client_async',
             'barrier_async', '_consume', 'remove_client', 'stop', 'cleanup_health'}
    body = [n for n in parent.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == names
    tree = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='ActualBuffer',
        bases=[], keywords=[], body=body, decorator_list=[], type_params=[])], type_ignores=[]))
    ns = dict(threading=threading, queue=queue, time=time, deque=deque,
              RL_CONFIG=types.SimpleNamespace(), print=lambda *a, **k: None)
    exec(compile(tree, str(path), 'exec'), ns)
    return ns['ActualBuffer']


def receipt_class():
    path = HERE/'connection_cleanup_receipts_v1.py'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RECEIPTS_SHA
    spec = importlib.util.spec_from_file_location('_prospective_cleanup_receipt_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ConnectionCleanupReceipts


class Agent:
    def __init__(self, *, block_first=False, failure=None):
        self.calls = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block_first, self.failure = block_first, failure

    def step(self, value):
        self.calls.append((value, threading.get_ident()))
        self.entered.set()
        if self.block_first and value == 1 and not self.release.wait(3):
            raise AssertionError('Fixture step was not released')
        if self.failure == 'ordinary':
            raise RuntimeError('fixture consumer step failed')
        if self.failure == 'abrupt':
            raise SystemExit('fixture original consumer exits without drain')
        return value


class ReceiptFixture:
    def __init__(self, book, row=None, *, eval_only=False):
        self.book, self.row = book, row
        self.eval_only = eval_only
        self.published = threading.Event()
        self.handler_release, self.timer_release = threading.Event(), threading.Event()
        self.ack, self.timer_done = threading.Event(), threading.Event()
        self.errors, self.tokens, self.timers = [], [], []
        self.handler = threading.Thread(target=self.run, daemon=True)
        self.handler.start()

    def run(self):
        try:
            token = self.book.begin(0, 0, self.eval_only, 123, threading.current_thread())
            self.tokens.append(token)
            def callback():
                if not self.timer_release.wait(3):
                    return  # No success event on timeout.
                self.timer_done.set()
            timer = threading.Timer(.001, callback)
            self.timers.append(timer)
            timer.start()
            self.book.finish(token, journal_ok=True, reset_ack=self.ack, timer=timer,
                             timer_done=self.timer_done, terminal_receipt=self.row)
        except BaseException as error:
            self.errors.append(error)
        finally:
            self.published.set()
            self.handler_release.wait(3)

    def close(self):
        self.handler_release.set()
        self.timer_release.set()
        self.handler.join(2)
        for timer in self.timers:
            timer.join(2)
        assert not self.handler.is_alive() and all(not t.is_alive() for t in self.timers)


class Tests(unittest.TestCase):
    def buffer(self, agent, maximum=8):
        b = buffer_class()(agent, batch_size=8, max_queue_size=maximum)
        def cleanup():
            agent.release.set()
            try:
                b.stop(timeout_s=2)
            except (RuntimeError, TimeoutError):
                # Failure is expected in negative fixtures; still require the
                # exact owned consumer to terminate, with no external action.
                b._thread.join(2)
            self.assertFalse(b._thread.is_alive())
        self.addCleanup(cleanup)
        return b

    def terminal(self, **changes):
        row = dict(client_id=0, client_slot=0, eval_only=False, complete=True,
                   eligible=True, known_start=True, boundary_reason='score_reset',
                   journal_game_id='synthetic:71', game_uid=71, score=150000123)
        row.update(changes)
        return row

    def book(self, provider=None, maximum=32):
        return receipt_class()(dict(pid=700000001, birth=17, source_sha256='a'*64),
            provider or (lambda: dict(admission_open=True, consumer_error=None)),
            maximum_records=maximum)

    def receipt(self, book, row=None, **kwargs):
        f = ReceiptFixture(book, row, **kwargs)
        self.addCleanup(f.close)
        self.assertTrue(f.published.wait(1))
        return f

    def test_actual_FIFO_reset_ack_follows_processing_and_preserves_later_episode(self):
        agent = Agent(block_first=True)
        b = self.buffer(agent)
        b.step_async(1, client_id=0)
        self.assertTrue(agent.entered.wait(1))
        ack = b.remove_client(0)
        self.assertFalse(ack.is_set())
        b.step_async(99, client_id=0)
        agent.release.set()
        self.assertTrue(ack.wait(1))
        wait_for(lambda: list(b._episode_indices.get(0, [])) == [99])
        self.assertEqual([n for n, _ in agent.calls], [1, 99])
        self.assertEqual({ident for _, ident in agent.calls}, {b._thread.ident})
        b.stop(timeout_s=1)
        self.assertTrue(b._drain_complete.is_set())

    def test_actual_disconnect_enqueue_deadline_never_returns_an_unqueued_ack(self):
        agent = Agent(block_first=True)
        b = self.buffer(agent, maximum=1)
        b.step_async(1, client_id=0)
        self.assertTrue(agent.entered.wait(1))
        b.step_async(2, client_id=0)
        began = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, 'not enqueued'):
            b.remove_client(0)
        self.assertGreaterEqual(time.monotonic()-began, .9)
        with b.queue.mutex:
            self.assertEqual([item[0] for item in b.queue.queue], ['step'])
        agent.release.set()
        b.stop(timeout_s=1)
        self.assertEqual([n for n, _ in agent.calls], [1, 2])
        # Exercise the actual enqueue method's deadline edge without waiting:
        # capacity appears only at the absolute deadline, so it must not put.
        original = buffer_class()._enqueue_preserving
        clock = types.SimpleNamespace(now=0.0)
        clock.monotonic = lambda: clock.now
        pending = queue.Queue(maxsize=1)
        pending.put(('prior',))
        class CapacityAtDeadline:
            def __enter__(self):
                return self
            def __exit__(self, *ignored):
                return False
            def wait(self, timeout):
                pending.get_nowait()
                clock.now = 1.0
        actual = types.FunctionType(original.__code__, dict(original.__globals__, time=clock))
        holder = types.SimpleNamespace(running=True, _consumer_error=None,
            _thread=types.SimpleNamespace(is_alive=lambda: True),
            _admission=CapacityAtDeadline(), queue=pending)
        with self.assertRaisesRegex(TimeoutError, 'not enqueued'):
            actual(holder, ('late',), timeout_s=1.0)
        self.assertTrue(pending.empty())

    def test_actual_stop_seals_late_producer_and_single_consumer_drains_after_timeout(self):
        agent = Agent(block_first=True)
        b = self.buffer(agent, maximum=1)
        b.step_async(1, client_id=0)
        self.assertTrue(agent.entered.wait(1))
        b.step_async(2, client_id=0)
        result = []
        def late_reset():
            try:
                result.append(b.remove_client(0))
            except BaseException as error:
                result.append(error)
        producer = threading.Thread(target=late_reset, daemon=True)
        producer.start()
        with self.assertRaisesRegex(TimeoutError, 'remains alive'):
            b.stop(timeout_s=.05)
        producer.join(1)
        self.assertFalse(producer.is_alive())
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], RuntimeError)
        self.assertFalse(b._drain_complete.is_set())
        self.assertEqual([n for n, _ in agent.calls], [1])
        with self.assertRaisesRegex(RuntimeError, 'sealed'):
            b.step_async(3, client_id=0)
        agent.release.set()
        b.stop(timeout_s=1)
        self.assertEqual([n for n, _ in agent.calls], [1, 2])
        self.assertEqual({ident for _, ident in agent.calls}, {b._thread.ident})

    def test_actual_consumer_exception_blocks_admission_and_persistence_qualification(self):
        agent = Agent(failure='ordinary')
        b = self.buffer(agent)
        b.step_async(1, client_id=0)
        wait_for(lambda: b._consumer_error is not None)
        self.assertIn('fixture consumer step failed', b.cleanup_health()['consumer_error'])
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            b.remove_client(0)
        with self.assertRaisesRegex(RuntimeError, 'persistence is unqualified'):
            b.stop(timeout_s=1)
        self.assertTrue(b._drain_complete.is_set())
        self.assertFalse(b._thread.is_alive())

    def test_actual_abrupt_consumer_death_is_not_a_successful_sealed_drain(self):
        b = self.buffer(Agent(failure='abrupt'))
        b.step_async(1, client_id=0)
        b._thread.join(1)
        self.assertFalse(b._thread.is_alive())
        self.assertFalse(b._drain_complete.is_set())
        self.assertIsNotNone(b.cleanup_health()['consumer_error'])
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            b.remove_client(0)
        with self.assertRaisesRegex(RuntimeError, 'never acknowledged'):
            b.stop(timeout_s=1)

    def test_actual_poststop_enqueue_refuses_and_never_silently_drops(self):
        b = self.buffer(Agent())
        b.stop(timeout_s=1)
        self.assertEqual(b.cleanup_health(), dict(admission_open=False, consumer_error=None))
        for operation in (lambda: b.step_async(1, client_id=0), lambda: b.remove_client(0), b.barrier_async):
            with self.assertRaisesRegex(RuntimeError, 'sealed'):
                operation()
        self.assertTrue(b.queue.empty())

    def test_receipt_requires_handler_timer_success_and_FIFO_ack_without_physical_fiction(self):
        book = self.book()
        row = self.terminal()
        f = self.receipt(book, row)
        self.assertEqual(f.errors, [])
        token = f.tokens[0]
        self.assertFalse(book.snapshot(token)['ready_for_external_join'])
        f.ack.set()
        self.assertFalse(book.snapshot(token)['ready_for_external_join'])
        f.handler_release.set(); f.handler.join(1)
        self.assertFalse(book.snapshot(token)['ready_for_external_join'])
        f.timer_release.set(); f.timers[0].join(1)
        value = book.lookup_terminal('synthetic:71', 0, 0)
        self.assertTrue(value['ready_for_external_join'])
        self.assertTrue(value['training_refill_candidate'])
        row['score'] = 0
        self.assertEqual(book.snapshot(token)['terminal_receipt']['score'], 150000123)
        self.assertFalse(value['owned_actor_PID_birth_exit_reap_proved'])
        self.assertFalse(value['runtime_integration_qualified'])
        self.assertFalse(value['safe_refill_qualified'])

    def test_receipt_identity_roles_failure_and_capacity_remain_fail_closed(self):
        for changes in ({'client_id':1},{'client_slot':1},{'eval_only':True},
                        {'complete':False},{'known_start':False},{'eligible':False},
                        {'score':True},{'score':-1},{'oversized_fixture':'x'*65536}):
            with self.subTest(changes=changes):
                book = self.book()
                f = self.receipt(book, self.terminal(**changes))
                self.assertEqual(len(f.errors), 1)
                self.assertIsInstance(f.errors[0], ValueError)
                f.close()
                self.assertFalse(book.snapshot(f.tokens[0])['ready_for_external_join'])
        state = dict(admission_open=True, consumer_error=None)
        book = self.book(lambda: state.copy(), maximum=1)
        f = self.receipt(book, self.terminal())
        f.ack.set(); f.close()
        self.assertTrue(book.snapshot(f.tokens[0])['training_refill_candidate'])
        state['admission_open'] = False
        self.assertFalse(book.snapshot(f.tokens[0])['training_refill_candidate'])
        state['consumer_error'] = 'consumer failed'
        self.assertFalse(book.snapshot(f.tokens[0])['ready_for_external_join'])
        other = self.receipt(book, self.terminal(journal_game_id='synthetic:72'))
        self.assertIsInstance(other.errors[0], RuntimeError)
        self.assertEqual(len(book.records), 1)
        with self.assertRaises(ValueError):
            book.lookup_terminal('unknown', 0, 0)


if __name__ == '__main__':
    unittest.main()
