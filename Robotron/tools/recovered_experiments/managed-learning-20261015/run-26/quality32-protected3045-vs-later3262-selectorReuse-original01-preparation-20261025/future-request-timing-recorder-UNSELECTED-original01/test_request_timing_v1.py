"""CPU guards for a future recorder, not a selected latency experiment."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import random
import sys
import threading
import time
import unittest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('_future_request_timing', HERE / 'request_timing_v1.py')
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)
Recorder = timing.RequestTimingRecorder


def complete(recorder, ticket, offset=0, batch=7):
    # Deliberately enqueue_return after dequeue: consumer can run before put returns.
    for name, stamp in [('dequeue', 20), ('enqueue_return', 25), ('coalesce_end', 30),
                        ('agent_begin', 40), ('agent_end', 70), ('signal', 80)]:
        recorder.mark(ticket, name, batch_id=batch, timestamp_ns=offset + stamp)
    return recorder.finish(ticket, 'completed', timestamp_ns=offset + 100)


class Guards(unittest.TestCase):
    def test_default_inert_has_no_clock_or_ticket_activity(self):
        def forbidden():
            raise AssertionError('disabled recorder invoked clock')
        r = Recorder(clock=forbidden)
        self.assertIsNone(r.begin())
        self.assertFalse(r.mark(None, 'dequeue'))
        self.assertFalse(r.finish(None, 'completed'))
        self.assertEqual(r.snapshot()['counts']['requests'], 0)
        self.assertEqual(r.snapshot()['pending'], 0)

    def test_invalid_configuration_refused(self):
        for args in [dict(enabled=1), dict(sample_every=True), dict(sample_every=0),
                     dict(sample_every=1.5), dict(max_pending=0), dict(max_pending=8193),
                     dict(recent=-1), dict(recent=257), dict(clock=None)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                Recorder(**args)

    def test_concurrent_admission_return_order_and_exact_decomposition(self):
        r = Recorder(enabled=True, sample_every=1)
        t = r.begin(timestamp_ns=10)
        self.assertTrue(complete(r, t))
        s = r.snapshot()
        row = s['recent'][0]
        self.assertEqual(row['request_id'], 0)
        self.assertEqual(row['batch_id'], 7)
        self.assertEqual(row['durations_ns']['request_total_ns'], 90)
        self.assertEqual(row['durations_ns']['admission_return_ns'], 15)
        self.assertEqual(sum(row['durations_ns'][k] for k in timing.SEGMENTS), 90)
        self.assertEqual(s['counts']['valid_completed'], 1)

    def test_same_batch_keeps_distinct_request_queue_and_coalescing_times(self):
        r = Recorder(enabled=True, sample_every=1)
        a, b = r.begin(timestamp_ns=1), r.begin(timestamp_ns=5)
        for t, dequeue in [(a, 10), (b, 15)]:
            r.mark(t, 'dequeue', batch_id=2, timestamp_ns=dequeue)
            r.mark(t, 'enqueue_return', timestamp_ns=18)
            for name, stamp in [('coalesce_end', 20), ('agent_begin', 21), ('agent_end', 40), ('signal', 42)]:
                r.mark(t, name, batch_id=2, timestamp_ns=stamp)
            self.assertTrue(r.finish(t, 'completed', timestamp_ns=50))
        rows = r.snapshot()['recent']
        self.assertNotEqual(rows[0]['request_id'], rows[1]['request_id'])
        self.assertEqual([x['durations_ns']['coalesce_remaining_ns'] for x in rows], [10, 5])
        self.assertEqual([x['batch_id'] for x in rows], [2, 2])

    def test_timeout_late_dispatch_and_duplicate_finish_never_reopen(self):
        r = Recorder(enabled=True, sample_every=1)
        t = r.begin(timestamp_ns=1)
        self.assertTrue(r.finish(t, 'timeout', timestamp_ns=5))
        self.assertFalse(r.mark(t, 'agent_begin', batch_id=1, timestamp_ns=6))
        self.assertFalse(r.finish(t, 'completed', timestamp_ns=10))
        s = r.snapshot()
        self.assertEqual(s['outcomes']['timeout'], 1)
        self.assertEqual(s['outcomes']['completed'], 0)
        self.assertEqual(s['counts']['late_marker'], 1)
        self.assertEqual(s['counts']['duplicate_finish'], 1)
        self.assertEqual(s['pending'], 0)

    def test_cancelled_failed_stopped_are_accounted_without_fabricated_phase_latency(self):
        r = Recorder(enabled=True, sample_every=1)
        for outcome in ['cancelled', 'failed', 'stopped']:
            t = r.begin(timestamp_ns=1)
            self.assertTrue(r.finish(t, outcome, timestamp_ns=3))
        s = r.snapshot()
        self.assertEqual([s['outcomes'][k] for k in ['cancelled', 'failed', 'stopped']], [1, 1, 1])
        self.assertEqual(s['metrics']['request_total_ns']['count'], 0)

    def test_out_of_order_missing_and_cross_batch_markers_invalidate_completed(self):
        r = Recorder(enabled=True, sample_every=1)
        a = r.begin(timestamp_ns=10)
        self.assertFalse(r.finish(a, 'completed', timestamp_ns=50))
        b = r.begin(timestamp_ns=10)
        self.assertTrue(r.mark(b, 'dequeue', batch_id=1, timestamp_ns=20))
        self.assertFalse(r.mark(b, 'agent_begin', batch_id=2, timestamp_ns=30))
        self.assertFalse(r.mark(b, 'dequeue', batch_id=1, timestamp_ns=40))
        self.assertFalse(r.mark(b, 'unknown', timestamp_ns=50))
        self.assertFalse(r.finish(b, 'completed', timestamp_ns=15))
        s = r.snapshot()
        self.assertEqual(s['counts']['invalid_completed'], 2)
        self.assertEqual(s['counts']['duplicate_marker'], 1)
        self.assertEqual(s['counts']['invalid_marker'], 2)
        self.assertEqual(s['counts']['valid_completed'], 0)

    def test_bounded_overflow_releases_capacity_without_resetting_sample_phase(self):
        r = Recorder(enabled=True, sample_every=3, max_pending=2, recent=1)
        tickets = [r.begin(timestamp_ns=1) for _ in range(12)]
        self.assertEqual([t.request_id for t in tickets if t is not None], [0, 3])
        self.assertEqual(r.snapshot()['counts']['overflow'], 2)
        self.assertEqual(r.snapshot()['pending'], 2)
        for t in tickets:
            if t is not None:
                r.finish(t, 'timeout', timestamp_ns=2)
        t = r.begin(timestamp_ns=3)
        self.assertEqual(t.request_id, 12)
        r.finish(t, 'stopped', timestamp_ns=4)
        self.assertEqual(len(r.snapshot()['recent']), 1)
        self.assertEqual(r.snapshot()['pending'], 0)

    def test_snapshots_own_their_nested_storage_and_do_not_drain(self):
        r = Recorder(enabled=True, sample_every=1)
        complete(r, r.begin(timestamp_ns=1))
        s = r.snapshot()
        s['recent'][0]['markers_ns']['signal'] = -1
        s['recent'][0]['durations_ns']['request_total_ns'] = -1
        s['metrics']['request_total_ns']['histogram'][0] = -1
        s['counts']['valid_completed'] = -1
        a = r.snapshot()
        self.assertEqual(a['recent'][0]['markers_ns']['signal'], 80)
        self.assertEqual(a['counts']['valid_completed'], 1)
        self.assertEqual(sum(a['metrics']['request_total_ns']['histogram']), 1)

    def test_foreign_ticket_and_bad_clock_cannot_poison_valid_completion(self):
        a, b = Recorder(enabled=True, sample_every=1), Recorder(enabled=True, sample_every=1)
        t = a.begin(timestamp_ns=1)
        self.assertFalse(b.mark(t, 'dequeue', timestamp_ns=2))
        for bad in [True, -1, 1.5, 1 << 63]:
            self.assertFalse(a.mark(t, 'dequeue', timestamp_ns=bad))
        self.assertTrue(complete(a, t))
        self.assertEqual(b.snapshot()['counts']['foreign_ticket'], 1)
        self.assertEqual(a.snapshot()['counts']['invalid_clock'], 4)

    def test_clock_is_called_outside_recorder_lock_and_exceptions_are_counted(self):
        r = Recorder(enabled=True, sample_every=1)
        r._clock = lambda: r.snapshot()['counts']['requests']
        t = r.begin()
        self.assertIsNotNone(t)
        def failing():
            raise RuntimeError('clock failed')
        r._clock = failing
        self.assertFalse(r.mark(t, 'dequeue'))
        self.assertIsNone(r.begin())
        self.assertEqual(r.snapshot()['counts']['invalid_clock'], 2)
        self.assertTrue(r.finish(t, 'failed', timestamp_ns=100))

    def test_concurrent_ids_outcomes_histograms_and_snapshots_conserve_requests(self):
        r = Recorder(enabled=True, sample_every=1, max_pending=128, recent=4)
        barrier = threading.Barrier(9)
        ids, errors, id_lock = set(), [], threading.Lock()
        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(400):
                    t = r.begin()
                    assert t is not None
                    with id_lock:
                        assert t.request_id not in ids
                        ids.add(t.request_id)
                    for phase in timing.PHASES:
                        assert r.mark(t, phase, batch_id=t.request_id + 1)
                    assert r.finish(t, 'completed')
            except BaseException as exc:
                with id_lock:
                    errors.append(repr(exc))
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=5)
        while any(t.is_alive() for t in threads):
            s = r.snapshot()
            self.assertEqual(s['counts']['sampled'], s['pending'] + sum(s['outcomes'].values()))
            self.assertEqual(s['counts']['valid_completed'], s['metrics']['request_total_ns']['count'])
            time.sleep(0.001)
        for thread in threads:
            thread.join(timeout=5)
        self.assertFalse(errors, errors)
        s = r.snapshot()
        self.assertEqual(len(ids), 3200)
        self.assertEqual(s['counts']['valid_completed'], 3200)
        self.assertEqual(s['pending'], 0)
        self.assertEqual(sum(s['metrics']['request_total_ns']['histogram']), 3200)
        self.assertEqual(len(s['recent']), 4)

    def test_sampling_and_observation_do_not_consume_randomness(self):
        before = random.getstate()
        r = Recorder(enabled=True, sample_every=3)
        selected = []
        for i in range(10):
            t = r.begin(timestamp_ns=1)
            if t is not None:
                selected.append(t.request_id)
                complete(r, t)
        self.assertEqual(selected, [0, 3, 6, 9])
        self.assertEqual(random.getstate(), before)
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('numpy', sys.modules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    if not args.validate:
        print('PLAN_ONLY')
        return 0
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    print(json.dumps(dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                          successful=result.wasSuccessful(), live_integration=False,
                          throughput_gain_verified=False)), flush=True)
    # Keep this original CPU process observable by its owned controller.
    time.sleep(8)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
