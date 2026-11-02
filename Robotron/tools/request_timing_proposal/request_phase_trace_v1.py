"""Bounded, opt-in request timing for an isolated future diagnostic.

Importing does not enable tracing. No file, process, GPU or network operations.
Never install into the running frozen study. Host intervals are not GPU times.
"""
from collections import Counter
from contextlib import contextmanager
import math
import threading
import time

_active = None
_local = threading.local()
_activation_lock = threading.Lock()
PHASES = frozenset('begin enqueue_attempt enqueue_return dequeued coalescing_end '
    'act_begin act_end validation_end signal_before waiter_awake returned '
    'queue_full wait_timeout cancelled returned_error missing_action stop_cancel '
    'stop_queue_signal finish_cancelled dispatch_error epsilon_begin epsilon_end '
    'state_pack_begin state_pack_end model_begin model_end reduce_begin reduce_end'.split())


class Recorder:
    def __init__(self, *, max_requests=4096, sample_every=64, clock=time.perf_counter_ns):
        if type(max_requests) is not int or not 1 <= max_requests <= 65536:
            raise ValueError('Bounded request capacity required')
        if type(sample_every) is not int or not 1 <= sample_every <= 1048576:
            raise ValueError('Positive bounded deterministic sampling required')
        self.max_requests, self.sample_every, self.clock = max_requests, sample_every, clock
        self.lock = threading.Lock()
        self.seen = self.capacity_drops = self.event_drops = self.errors = 0
        self.rows = {}

    def begin(self):
        with self.lock:
            sequence = self.seen
            self.seen += 1
            if sequence % self.sample_every:
                return None
            if len(self.rows) >= self.max_requests:
                self.capacity_drops += 1
                return None
            self.rows[sequence] = []
        ticket = (self, sequence)
        mark(ticket, 'begin')
        return ticket

    def snapshot(self):
        with self.lock:
            return dict(schema='robotron-host-request-phases-v1', clock='perf_counter_ns',
                sample_every=self.sample_every, max_requests=self.max_requests,
                seen=self.seen, capacity_drops=self.capacity_drops,
                event_drops=self.event_drops, errors=self.errors,
                rows=[dict(request_id=k, events=[list(e) for e in v])
                      for k, v in sorted(self.rows.items())])


@contextmanager
def capture(recorder):
    global _active
    if not isinstance(recorder, Recorder):
        raise TypeError('Explicit recorder required')
    with _activation_lock:
        if _active is not None:
            raise RuntimeError('A trace is already active')
        _active = recorder
    try:
        yield recorder
    finally:
        with _activation_lock:
            _active = None


def new_request():
    recorder = _active
    if recorder is None:
        return None
    try:
        return recorder.begin()
    except Exception:
        with recorder.lock:
            recorder.errors += 1
        return None


def mark(ticket, phase):
    if ticket is None:
        return
    recorder, sequence = ticket
    try:
        with recorder.lock:
            stamp = recorder.clock()
            if phase not in PHASES or type(stamp) is not int or stamp < 0:
                raise ValueError('Unknown phase or invalid monotonic timestamp')
            events = recorder.rows[sequence]
            if len(events) >= 64:
                recorder.event_drops += 1
            else:
                events.append((phase, stamp))
    except Exception:
        with recorder.lock:
            recorder.errors += 1


def batch_begin(tickets):
    _local.tickets = tuple(t for t in tickets if t is not None)


def batch_mark(phase):
    for ticket in getattr(_local, 'tickets', ()):
        mark(ticket, phase)


def batch_end():
    _local.tickets = ()


DECOMPOSITION = (
    ('pre_enqueue', 'begin', 'enqueue_attempt'),
    ('admission_and_queue', 'enqueue_attempt', 'dequeued'),
    ('coalescing_and_filter', 'dequeued', 'coalescing_end'),
    ('batch_list_packing', 'coalescing_end', 'act_begin'),
    ('act_batch', 'act_begin', 'act_end'),
    ('validation_and_finish_lock', 'act_end', 'signal_before'),
    ('signal_to_waiter', 'signal_before', 'waiter_awake'),
    ('waiter_result_lock', 'waiter_awake', 'returned'),
)
SUBPHASES = (
    ('epsilon_partition', 'epsilon_begin', 'epsilon_end'),
    ('greedy_state_packing', 'state_pack_begin', 'state_pack_end'),
    ('model_host', 'model_begin', 'model_end'),
    ('action_reduction', 'reduce_begin', 'reduce_end'),
)


def analyze(snapshot):
    """Reject malformed traces; include failures/censoring, never invent phases."""
    if snapshot.get('schema') != 'robotron-host-request-phases-v1' or snapshot.get('clock') != 'perf_counter_ns':
        raise ValueError('Exact trace schema and clock required')
    for key in ('seen', 'capacity_drops', 'event_drops', 'errors', 'sample_every', 'max_requests'):
        if type(snapshot.get(key)) is not int or snapshot[key] < 0:
            raise ValueError('Invalid trace counter')
    if not 1 <= snapshot['sample_every'] <= 1048576 or not 1 <= snapshot['max_requests'] <= 65536:
        raise ValueError('Invalid sampling or capacity')
    rows = snapshot.get('rows')
    if not isinstance(rows, list) or len(rows) > snapshot['max_requests']:
        raise ValueError('Invalid bounded rows')
    seen_ids, outcomes, intervals = set(), Counter(), {}
    partition_residuals = []
    for row in rows:
        key = row.get('request_id')
        if type(key) is not int or key < 0 or key >= snapshot['seen'] or key in seen_ids or key % snapshot['sample_every']:
            raise ValueError('Duplicate, unsampled or invalid request ID')
        seen_ids.add(key)
        events = row.get('events')
        if not isinstance(events, list) or len(events) > 64:
            raise ValueError('Invalid event list')
        phases, previous = {}, -1
        for event in events:
            if not isinstance(event, (tuple, list)) or len(event) != 2:
                raise ValueError('Invalid event')
            phase, stamp = event
            if phase not in PHASES or phase in phases or type(stamp) is not int or stamp < previous:
                raise ValueError('Duplicate phase, invalid clock or nonmonotonic request')
            phases[phase], previous = stamp, stamp
        if 'returned' in phases:
            if any(k in phases for k in ('cancelled', 'returned_error', 'missing_action', 'queue_full', 'wait_timeout', 'stop_cancel', 'dispatch_error')):
                raise ValueError('Success conflicts with failure')
            needed = {p for _, a, b in DECOMPOSITION for p in (a, b)}
            if not needed <= phases.keys():
                raise ValueError('Successful request lacks matched partition')
            outcome = 'returned'
        elif 'queue_full' in phases:
            outcome = 'admission_timeout'
        elif 'wait_timeout' in phases:
            outcome = 'wait_timeout'
        elif 'returned_error' in phases or 'missing_action' in phases:
            outcome = 'returned_error'
        else:
            outcome = 'incomplete'
        outcomes[outcome] += 1
        # A timeout may still finish in flight. Do not mix its partial work into
        # the successful request distribution or silently discard its count.
        if outcome != 'returned':
            continue
        pieces = []
        for name, begin, end in DECOMPOSITION + SUBPHASES:
            if begin in phases and end in phases:
                elapsed = phases[end] - phases[begin]
                if elapsed < 0:
                    raise ValueError('Phase order differs')
                intervals.setdefault(name, []).append(elapsed)
                if (name, begin, end) in DECOMPOSITION:
                    pieces.append(elapsed)
            elif begin in phases or end in phases:
                raise ValueError('Unpaired successful subphase')
        elapsed = phases['returned'] - phases['begin']
        intervals.setdefault('end_to_end', []).append(elapsed)
        partition_residuals.append(elapsed - sum(pieces))
    def stats(values):
        values = sorted(values)
        def pct(q):
            return values[max(0, math.ceil(q * len(values)) - 1)] / 1e6
        return dict(count=len(values), p50_ms=pct(.5), p95_ms=pct(.95), p99_ms=pct(.99),
                    mean_ms=sum(values)/len(values)/1e6)
    return dict(status='HOST_PHASE_TRACE_ANALYZED', outcomes=dict(outcomes),
        intervals={k: stats(v) for k, v in intervals.items()},
        partition_residual_ns=partition_residuals,
        capture_loss=dict(capacity_drops=snapshot['capacity_drops'],
                          event_drops=snapshot['event_drops'], errors=snapshot['errors']),
        production_measurement=False, quality_gain_verified=False,
        learning_speed_gain_verified=False,
        limitations=['Host intervals include instrumentation overhead.',
            'Admission and queue residence are combined; enqueue return may follow dequeue.',
            'Signal-to-waiter includes Event.set and scheduling, not pure wake-up cost.',
            'Batch subphases are replicated per request and must not be summed as CPU work.'])
