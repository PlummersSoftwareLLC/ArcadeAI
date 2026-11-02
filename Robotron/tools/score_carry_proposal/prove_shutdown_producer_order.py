"""Exercise held shutdown code with CPU threads; never connect to a trainer.

This is a prospective handoff component proof, not a production shutdown tool.
The socket cleanup body, frame accounting, replay FIFO and final learner gate
are extracted without rewriting their bodies. Actors, sockets, numerical work,
journal IO and delayed housekeeping are explicit test doubles.
"""
import argparse
import ast
from collections import deque
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import queue
import socket
import sys
import threading
import time
from types import SimpleNamespace
import unittest


SOCKET_SHA = '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408'
TRAINING_SHA = '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(socket_source, training_source):
    assert digest(socket_source) == SOCKET_SHA
    assert digest(training_source) == TRAINING_SHA
    tree = ast.parse(socket_source.read_bytes())
    server = next(n for n in tree.body
                  if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
    methods = {n.name: n for n in server.body if isinstance(n, ast.FunctionDef)}
    handler = methods['handle_client']
    outer = [n for n in handler.body if isinstance(n, ast.Try)]
    assert len(outer) == 1 and outer[0].finalbody
    cleanup = ast.FunctionDef(name='_disconnect_finally', args=ast.arguments(
        posonlyargs=[], args=[ast.arg(arg=n) for n in (
            'self', 'sock', 'cid', 'local_accum', 'local_measurement_accum',
            '_gap_connection')], vararg=None, kwonlyargs=[], kw_defaults=[],
        kwarg=None, defaults=[]), body=outer[0].finalbody, decorator_list=[],
        returns=None, type_comment=None, type_params=[])
    selected = [next(n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == 'AsyncReplayBuffer'),
                methods['_sync_client_count_locked'],
                methods['_account_frame_batch'], cleanup]
    # These methods retain their original staticmethod decorators. Bind the
    # descriptor to the fixture class, as on the original SocketServer.
    namespace = dict(queue=queue, deque=deque, time=time, socket=socket)
    exec(compile(ast.fix_missing_locations(ast.Module(
        body=selected, type_ignores=[])), str(socket_source), 'exec'), namespace)
    training = ast.parse(training_source.read_bytes())
    functions = [n for n in training.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('replay_pressure_reached', 'train_step', '_train_step_impl')]
    assert len(functions) == 3
    namespace['nullcontext'] = nullcontext
    exec(compile(ast.Module(body=functions, type_ignores=[]),
                 str(training_source), 'exec'), namespace)
    return namespace, dict(cleanup_lines=[outer[0].finalbody[0].lineno,
                                        outer[0].finalbody[-1].end_lineno],
                           unmodified_body_names=[
                               'AsyncReplayBuffer', 'SocketServer.handle_client.finally',
                               'SocketServer._sync_client_count_locked',
                               'SocketServer._account_frame_batch'] + [n.name for n in functions])


class NumericalRegionReached(Exception):
    pass


class Config:
    batch_size = 4096
    baseline_batch_size = 512
    min_replay_to_train = 500_000
    max_samples_per_frame = 8

    @property
    def per_priority_metric(self):
        raise NumericalRegionReached('Final actual learner guard admitted numerical work')


class Metrics:
    def __init__(self):
        self.lock = threading.RLock()
        self.client_count = 0
        self.frame_count = self.loaded_frame_count = 1000
        self.measurement_frame_count = self.loaded_measurement_frame_count = 0
        self.loaded_optimized_samples = 10_000
        self.training_enabled = True
        self.measurement_active = False
        self.frame_publications = []
        self.epsilon_frames = 0

    def update_frame_count(self, *, delta):
        with self.lock:
            self.frame_count += delta
            self.frame_publications.append((self.frame_count, self.measurement_frame_count))

    def update_epsilon(self, *, frames_advanced):
        with self.lock:
            self.epsilon_frames += frames_advanced

    def update_expert_ratio(self):
        pass

    def ratchet_note_eval_abandoned(self, *args):
        pass


class Memory:
    def __len__(self):
        return 6_000_000


class Actor:
    def __init__(self):
        self.lock = threading.Lock()
        self.steps = []
        self.memory = Memory()
        self.optimized_samples = 10_000
        self.training_steps = 100
        self.loaded_training_steps = 90
        self.training_enabled = True
        self._training_lock = threading.RLock()
        self._recomputed_ce_capture = None
        self.entered = threading.Event()
        self.release = threading.Event()
        self.completed = threading.Event()
        self.hold = False

    def step(self, value):
        self.entered.set()
        if self.hold and not self.release.wait(30):
            raise RuntimeError('Fixture owner did not release its held step')
        with self.lock:
            self.steps.append(value)
        self.completed.set()
        return value


class PendingBatch:
    def __init__(self):
        self.releases = 0

    def release(self):
        self.releases += 1


class Sock:
    def shutdown(self, how):
        assert how == socket.SHUT_RDWR

    def close(self):
        pass


def tests(namespace, findings):
    class ShutdownTests(unittest.TestCase):
        def setUp(self):
            self.metrics = Metrics()
            self.config = Config()
            self.actor = Actor()
            self.timers = []
            timers = self.timers

            class HousekeepingTimer:
                def __init__(self, interval, callback):
                    self.interval, self.callback = interval, callback

                def start(self):
                    timers.append((self.interval, self.callback))

            namespace.update(metrics=self.metrics, RL_CONFIG=self.config,
                threading=SimpleNamespace(Thread=threading.Thread, Event=threading.Event,
                    Lock=threading.Lock, Timer=HousekeepingTimer))
            self.buffer = namespace['AsyncReplayBuffer'](self.actor)
            self.threads = []
            self.release_journal = threading.Event()

        def tearDown(self):
            self.release_journal.set()
            self.actor.release.set()
            for thread in self.threads:
                thread.join(10)
                self.assertFalse(thread.is_alive(), 'Fixture left a producer/stop caller alive')
            if self.buffer.running:
                self.assertTrue(self.buffer.barrier_async().wait(5))
                self.buffer.stop()
            self.buffer._thread.join(10)
            self.assertFalse(self.buffer._thread.is_alive(), 'Fixture left its FIFO worker alive')

        def blocked_batch(self):
            batch = PendingBatch()
            before = (self.actor.optimized_samples, self.actor.training_steps)
            self.assertTrue(namespace['replay_pressure_reached'](self.actor))
            self.assertIsNone(namespace['train_step'](self.actor, prefetched_batch=batch))
            self.assertEqual(batch.releases, 1)
            self.assertEqual(before, (self.actor.optimized_samples, self.actor.training_steps))

        def test_192_cleanup_producers_can_outlive_zero_clients_and_early_barrier(self):
            owner = self

            class Server:
                _disconnect_finally = namespace['_disconnect_finally']
                _sync_client_count_locked = namespace['_sync_client_count_locked']
                _account_frame_batch = namespace['_account_frame_batch']

                def _ensure_preview_client_selected_locked(self):
                    return None, False

                def _journal_context(self, state):
                    return state

                def _cleanup(self):
                    raise AssertionError('Delayed housekeeping must remain a declared test double')

            server = Server()
            server.metrics = self.metrics
            server.client_lock = threading.Lock()
            server.client_states = {i: dict(raw_score_prev=None) for i in range(192)}
            server.clients = dict.fromkeys(range(192), True)
            server._unwrap_stash, server._eval_override = {}, {}
            server._rejected_gaps = SimpleNamespace(event=lambda *a, **kw: None)
            server.async_buffer = self.buffer
            server.shutdown_event = threading.Event()
            server.shutdown_event.set()
            arrived, errors = set(), []
            condition = threading.Condition()
            identities = {}

            def disconnect(cid, context):
                with condition:
                    arrived.add(cid)
                    condition.notify_all()
                if not owner.release_journal.wait(30):
                    raise RuntimeError('Fixture journal gate did not release')

            server.game_journal = SimpleNamespace(disconnect=disconnect)
            for cid in range(192):
                self.buffer.step_async(cid, client_id=cid)
            self.assertTrue(self.buffer.barrier_async().wait(5))
            self.assertEqual(len(self.buffer._episode_indices), 192)

            def producer(cid):
                try:
                    identities[cid] = threading.get_native_id()
                    server._disconnect_finally(Sock(), cid, 3, 0, None)
                except BaseException as error:
                    with condition:
                        errors.append(repr(error))
                        condition.notify_all()

            for cid in range(192):
                thread = threading.Thread(target=producer, args=(cid,))
                self.threads.append(thread)
                thread.start()
            with condition:
                self.assertTrue(condition.wait_for(lambda: len(arrived) == 192 or errors, timeout=10))
            self.assertEqual(errors, [])
            self.assertEqual(self.metrics.client_count, 0)
            self.assertEqual(self.metrics.frame_count, 1000 + 192 * 3)
            self.assertEqual(len(set(identities.values())), 192)
            self.assertTrue(all(t.is_alive() for t in self.threads))
            early = self.buffer.barrier_async()
            self.assertTrue(early.wait(5))
            self.assertEqual(len(self.buffer._episode_indices), 192,
                             'An early barrier cannot cover resets producers have not queued')
            before = (self.metrics.frame_count, self.metrics.measurement_frame_count)
            self.assertEqual(before, (self.metrics.frame_count, self.metrics.measurement_frame_count))
            self.release_journal.set()
            for thread in self.threads:
                thread.join(10)
                self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue(self.buffer.barrier_async().wait(5))
            self.assertEqual(self.buffer._episode_indices, {})
            self.assertEqual(self.buffer._client_indices, {})
            self.assertEqual(sorted(self.actor.steps), list(range(192)))
            self.assertEqual(len(self.timers), 192)
            self.assertEqual(before, (self.metrics.frame_count, self.metrics.measurement_frame_count))
            self.actor.optimized_samples = 10_000 + 192 * 3 * 8
            self.blocked_batch()
            findings['producer_cleanup'] = dict(producers=192, distinct_native_threads=192,
                zero_clients_before_last_reset=True, early_barrier_ack_before_last_reset=True,
                after_all_producers_joined_barrier_clears_all_192=True,
                local_unmeasured_frames_flushed=576, final_sample_guard_blocks=True,
                delayed_housekeeping_is_stubbed=True)

        def test_running_fifo_barrier_waits_for_older_inflight_step(self):
            self.actor.hold = True
            self.buffer.step_async(71, client_id=7)
            self.assertTrue(self.actor.entered.wait(5))
            barrier = self.buffer.barrier_async()
            self.assertFalse(barrier.wait(.05))
            self.assertFalse(self.actor.completed.is_set())
            self.actor.release.set()
            self.assertTrue(barrier.wait(5))
            self.assertEqual(self.actor.steps, [71])
            findings['running_fifo'] = dict(barrier_covers_older_worker_step=True)

        def test_stop_caller_can_ack_barrier_before_worker_finishes_and_return_alive(self):
            self.actor.hold = True
            self.buffer.step_async(81, client_id=8)
            self.assertTrue(self.actor.entered.wait(5))
            barrier = self.buffer.barrier_async()
            returned = threading.Event()

            def stop():
                self.buffer.stop()
                returned.set()

            thread = threading.Thread(target=stop)
            self.threads.append(thread)
            started = time.monotonic()
            thread.start()
            self.assertTrue(barrier.wait(5))
            self.assertFalse(self.actor.completed.is_set())
            self.assertTrue(returned.wait(8), 'Original stop uses a real five-second join timeout')
            self.assertTrue(self.buffer._thread.is_alive())
            self.assertFalse(self.actor.completed.is_set())
            elapsed = time.monotonic() - started
            self.actor.release.set()
            self.buffer._thread.join(5)
            self.assertFalse(self.buffer._thread.is_alive())
            self.assertEqual(self.actor.steps, [81])
            findings['stop_race'] = dict(barrier_ack_before_older_step_completed=True,
                stop_returned_with_worker_alive=True, elapsed_s=elapsed,
                actual_timeout_unchanged=True, worker_joined_after_fixture_release=True)

        def test_local_measurement_flush_does_not_grant_sample_credit(self):
            namespace['_account_frame_batch'].__func__(100, 40)
            self.assertEqual(self.metrics.frame_publications, [(1100, 40)])
            self.assertEqual(self.metrics.epsilon_frames, 60)
            self.actor.optimized_samples = 10_000 + 60 * 8
            self.blocked_batch()
            findings['frame_accounting'] = dict(raw_frames=100, measured_frames=40,
                eligible_frames=60, measured_debit_precedes_frame_publication=True)

        def test_one_sample_credit_reaches_the_original_numerical_boundary(self):
            namespace['_account_frame_batch'].__func__(100, 40)
            self.actor.optimized_samples = 10_000 + 60 * 8 - 1
            batch = PendingBatch()
            with self.assertRaises(NumericalRegionReached):
                namespace['train_step'](self.actor, prefetched_batch=batch)
            self.assertEqual(batch.releases, 1)
            findings['positive_control'] = dict(one_sample_credit_reaches_sentinel=True)

    return ShutdownTests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--socket-source', type=Path, required=True)
    parser.add_argument('--training-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return
    assert hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled(), 'Use actual free-threaded Python'
    namespace, source_scope = extract(args.socket_source, args.training_source)
    findings = {}
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(tests(namespace, findings)))
    assert digest(args.socket_source) == SOCKET_SHA
    assert digest(args.training_source) == TRAINING_SHA
    report = dict(schema='robotron-future-handoff-producer-FIFO-order-CPU-v1',
        status='PASS' if result.wasSuccessful() else 'FAIL', tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors),
        free_threaded_python=sys.version, gil_enabled=sys._is_gil_enabled(),
        socket_source_sha256=SOCKET_SHA, training_source_sha256=TRAINING_SHA,
        source_scope=source_scope, findings=findings, live_network_used=False,
        actual_model_optimizer_replay_banks_or_GPU_used=False,
        production_changed=False, production_handoff_ready=False,
        limitations=[
            'Exact cleanup body and FIFO use real CPU threads and queue; this does not run the full wire handler or emulator.',
            'Journal IO and housekeeping timers are declared doubles. Bank persistence and numerical work are not exercised.',
            'Joining fixture producer threads establishes the ordering requirement; detecting every real live producer remains a separate deployment prerequisite.',
            'An original stop return, zero clients, an empty queue or a barrier during concurrent stop is insufficient proof of a drained replay worker.',
            'No live measurement pause, trainer shutdown, model load, replay save or policy-quality trial is performed.'
        ])
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
