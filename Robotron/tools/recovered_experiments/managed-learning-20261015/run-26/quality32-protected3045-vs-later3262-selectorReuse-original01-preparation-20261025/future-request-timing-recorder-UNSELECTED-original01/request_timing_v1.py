"""Unselected bounded host timing recorder; no inference or application imports.

Markers describe one original request on one monotonic clock. Queue admission
return can follow consumer dequeue, so it is reported separately from the
disjoint request decomposition. This component has no live integration.
"""
from bisect import bisect_left
from collections import deque
import threading
import time

PHASES = ('enqueue_return', 'dequeue', 'coalesce_end', 'agent_begin', 'agent_end', 'signal')
CHAIN = ('enqueue_begin', 'dequeue', 'coalesce_end', 'agent_begin', 'agent_end', 'signal', 'waiter_return')
OUTCOMES = ('completed', 'timeout', 'cancelled', 'failed', 'stopped')
SEGMENTS = ('enqueue_to_dequeue_ns', 'coalesce_remaining_ns', 'dispatch_preparation_ns',
            'act_batch_host_ns', 'completion_preparation_ns', 'signal_to_return_ns')
METRICS = SEGMENTS + ('request_total_ns', 'admission_return_ns')
BOUNDS_NS = (10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 2_000_000,
             5_000_000, 10_000_000, 20_000_000, 50_000_000, 100_000_000,
             250_000_000, 500_000_000, 1_000_000_000, 3_000_000_000)


class _Ticket:
    __slots__ = ('request_id', '_owner', '_marks', '_batch_id', '_closed')

    def __init__(self, request_id, owner, started):
        self.request_id, self._owner = request_id, owner
        self._marks = {'enqueue_begin': started}
        self._batch_id, self._closed = None, False


class _Distribution:
    def __init__(self):
        self.count = self.total = self.maximum = 0
        self.histogram = [0] * (len(BOUNDS_NS) + 1)

    def add(self, value):
        self.count += 1
        self.total += value
        self.maximum = max(self.maximum, value)
        self.histogram[bisect_left(BOUNDS_NS, value)] += 1

    def snapshot(self):
        return dict(count=self.count, total_ns=self.total, max_ns=self.maximum,
                    histogram=list(self.histogram))


class RequestTimingRecorder:
    """Default inert, sampled, non-draining recorder with bounded pending rows.

    Hooks must call outside application locks/waits. No state/action payload is
    accepted. Runtime recording errors invalidate observations without changing
    caller actions or raising an instrumentation exception. Configuration errors
    are rejected at construction. No lock is held while invoking the clock.
    """

    def __init__(self, *, enabled=False, sample_every=20, max_pending=256, recent=16,
                 clock=time.perf_counter_ns):
        if type(enabled) is not bool:
            raise ValueError('enabled must be a bool')
        for name, value, lo, hi in [('sample_every', sample_every, 1, 1_000_000),
                                    ('max_pending', max_pending, 1, 8192), ('recent', recent, 0, 256)]:
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError('invalid ' + name)
        if not callable(clock):
            raise ValueError('clock must be callable')
        self.enabled, self.sample_every = enabled, sample_every
        self.max_pending = max_pending
        self._clock, self._lock, self._owner = clock, threading.Lock(), object()
        self._next_id = 0
        self._pending, self._recent = {}, deque(maxlen=recent)
        self._counts = dict(requests=0, sampled=0, unsampled=0, overflow=0,
                            invalid_clock=0, invalid_marker=0, duplicate_marker=0,
                            foreign_ticket=0, late_marker=0, duplicate_finish=0,
                            invalid_completed=0, valid_completed=0)
        self._outcomes = dict.fromkeys(OUTCOMES, 0)
        self._metrics = {name: _Distribution() for name in METRICS}

    def _stamp(self, value):
        if value is None:
            try:
                value = self._clock()
            except Exception:
                value = None
        if type(value) is not int or not 0 <= value < 1 << 63:
            with self._lock:
                self._counts['invalid_clock'] += 1
            return None
        return value

    def begin(self, *, timestamp_ns=None):
        if not self.enabled:
            return None
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._counts['requests'] += 1
            if request_id % self.sample_every:
                self._counts['unsampled'] += 1
                return None
            if len(self._pending) >= self.max_pending:
                self._counts['overflow'] += 1
                return None
        stamp = self._stamp(timestamp_ns)
        if stamp is None:
            return None
        with self._lock:
            if len(self._pending) >= self.max_pending:
                self._counts['overflow'] += 1
                return None
            ticket = _Ticket(request_id, self._owner, stamp)
            self._pending[request_id] = ticket
            self._counts['sampled'] += 1
            return ticket

    def _owned(self, ticket, *, finishing=False):
        if not isinstance(ticket, _Ticket) or ticket._owner is not self._owner:
            self._counts['foreign_ticket'] += 1
            return False
        if ticket._closed:
            self._counts['duplicate_finish' if finishing else 'late_marker'] += 1
            return False
        if self._pending.get(ticket.request_id) is not ticket:
            self._counts['foreign_ticket'] += 1
            return False
        return True

    def mark(self, ticket, phase, *, batch_id=None, timestamp_ns=None):
        if ticket is None or not self.enabled:
            return False
        if phase not in PHASES or (batch_id is not None and
                (type(batch_id) is not int or not 0 < batch_id < 1 << 63)):
            with self._lock:
                self._counts['invalid_marker'] += 1
            return False
        stamp = self._stamp(timestamp_ns)
        if stamp is None:
            return False
        with self._lock:
            if not self._owned(ticket):
                return False
            if phase in ticket._marks:
                self._counts['duplicate_marker'] += 1
                return False
            if batch_id is not None:
                if ticket._batch_id is not None and ticket._batch_id != batch_id:
                    self._counts['invalid_marker'] += 1
                    return False
                ticket._batch_id = batch_id
            ticket._marks[phase] = stamp
            return True

    def finish(self, ticket, outcome, *, timestamp_ns=None):
        if ticket is None or not self.enabled:
            return False
        if outcome not in OUTCOMES:
            with self._lock:
                self._counts['invalid_marker'] += 1
            return False
        stamp = self._stamp(timestamp_ns)
        if stamp is None:
            return False
        with self._lock:
            if not self._owned(ticket, finishing=True):
                return False
            ticket._closed = True
            del self._pending[ticket.request_id]
            marks = dict(ticket._marks, waiter_return=stamp)
            self._outcomes[outcome] += 1
            valid = all(marks['enqueue_begin'] <= value <= stamp for value in marks.values())
            durations = {}
            if outcome == 'completed':
                valid = (valid and ticket._batch_id is not None and all(k in marks for k in CHAIN)
                         and 'enqueue_return' in marks)
                if valid:
                    values = [marks[k] for k in CHAIN]
                    valid = all(a <= b for a, b in zip(values, values[1:]))
                if valid:
                    durations = dict(zip(SEGMENTS, (b - a for a, b in zip(values, values[1:]))))
                    durations['request_total_ns'] = stamp - marks['enqueue_begin']
                    durations['admission_return_ns'] = marks['enqueue_return'] - marks['enqueue_begin']
                    assert sum(durations[k] for k in SEGMENTS) == durations['request_total_ns']
                    for name, value in durations.items():
                        self._metrics[name].add(value)
                    self._counts['valid_completed'] += 1
                else:
                    self._counts['invalid_completed'] += 1
            self._recent.append(dict(request_id=ticket.request_id, batch_id=ticket._batch_id,
                                     outcome=outcome, valid=valid, markers_ns=marks, durations_ns=durations))
            return valid

    def snapshot(self):
        with self._lock:
            return dict(schema='robotron-unselected-request-timing-component-v1', enabled=self.enabled,
                        sample_every=self.sample_every, max_pending=self.max_pending,
                        pending=len(self._pending), recent_capacity=self._recent.maxlen,
                        counts=dict(self._counts), outcomes=dict(self._outcomes),
                        metrics={k: v.snapshot() for k, v in self._metrics.items()},
                        bucket_upper_ns=list(BOUNDS_NS) + [None],
                        recent=[dict(row, markers_ns=dict(row['markers_ns']), durations_ns=dict(row['durations_ns']))
                                for row in self._recent],
                        non_draining=True, live_integration=False, causal_speed_gain_verified=False)
