"""Common engineering instrumentation; never install in the learning process.

The CPU interval excludes record bookkeeping. Common timer/wrapper overhead
remains identical for both engineering implementations. The wrapper
returns the actual original result and preserves original exceptions.
"""
import hashlib
import inspect
from pathlib import Path
import threading
import time


class SelectorTiming:
    def __init__(self, view_class, expected_source_sha256, *, max_calls=131072):
        path = Path(inspect.getsourcefile(view_class))
        if (view_class.__name__ != 'FixedSlotCohortView'
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected_source_sha256
                or view_class.cohort_status.__code__.co_filename != str(path)):
            raise ValueError('Exact original selected class and method source required')
        if type(max_calls) is not int or not 1 <= max_calls <= 131072:
            raise ValueError('Bounded original telemetry capacity required')
        self.view_class = view_class
        self.original = view_class.cohort_status
        self.source_sha256 = expected_source_sha256
        self.max_calls = max_calls
        self.lock = threading.Lock()
        self.rows = []
        self.active = 0
        self.closed = False
        self.overflowed = False

        def measured(instance, *args, **kwargs):
            with self.lock:
                if self.closed:
                    raise RuntimeError('Selector telemetry already closed')
                self.active += 1
            result = None
            exceptional = True
            thread = threading.get_ident()
            cpu_start = time.thread_time_ns()
            wall_start = time.monotonic_ns()
            try:
                result = self.original(instance, *args, **kwargs)
                exceptional = False
                return result
            finally:
                cpu_end = time.thread_time_ns()
                wall_end = time.monotonic_ns()
                shape = (-1, -1, -1) if exceptional else (
                    result['started'] + len(result['retained_outside_cohort_ids']),
                    result['count'], result['pending'])
                row = [wall_start, wall_end, cpu_end - cpu_start, thread, *shape, exceptional]
                with self.lock:
                    self.active -= 1
                    if len(self.rows) >= self.max_calls:
                        self.overflowed = True
                        raise RuntimeError('Selector telemetry capacity exceeded; case invalid')
                    self.rows.append(row)

        self.measured = measured
        view_class.cohort_status = measured

    def finish(self):
        with self.lock:
            if self.closed or self.active or self.view_class.cohort_status is not self.measured:
                raise RuntimeError('Unknown selector telemetry writer or unfinished calls')
            self.view_class.cohort_status = self.original
            self.closed = True
            return dict(schema='robotron-selector-native-call-timing-v1',
                selector_source_sha256=self.source_sha256, clock='monotonic_ns/thread_time_ns',
                columns=['start_monotonic_ns', 'end_monotonic_ns', 'thread_CPU_ns', 'thread_id',
                         'known_starts', 'completed', 'pending', 'exceptional'],
                rows=[row[:] for row in self.rows], capacity=self.max_calls,
                all_calls_retained=not self.overflowed, overflowed=self.overflowed,
                original_method_restored=True,
                active_calls_at_close=self.active, production_instrumentation=False)


def active_endpoint(actors):
    if set(actors) != set(range(4096, 4128)):
        raise ValueError('All32 original slots required for an active endpoint')
    start = time.monotonic_ns()
    slots = {}
    for slot in sorted(actors):
        row = actors[slot]
        child = row['child']
        if child is None or child.poll() is not None or not row['proxy'].prefix_verified.is_set():
            raise ValueError('Original actor/prefix is not active')
        current_birth = int(Path('/proc', str(child.pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
        if current_birth != row['birth']:
            raise ValueError('Original active actor birth changed')
        ledger = row['proxy'].ledger.summary()
        if any(type(ledger[key]) is not int or ledger[key] < 0 for key in ('accepted', 'rejected', 'sequence')):
            raise ValueError('Original ledger counters differ')
        if ledger['rejected'] != 0:
            raise ValueError('Rejected original evaluator frames')
        slots[str(slot)] = dict(pid=child.pid, birth=row['birth'], accepted=ledger['accepted'],
                                rejected=ledger['rejected'], sequence=ledger['sequence'])
    end = time.monotonic_ns()
    return dict(schema='robotron-selector-active32-endpoint-v1', read_started_monotonic_ns=start,
                read_ended_monotonic_ns=end, midpoint_monotonic_ns=(start + end) // 2, slots=slots)


def window_rates(start, end):
    expected = {str(slot) for slot in range(4096, 4128)}
    if set(start['slots']) != expected or set(end['slots']) != expected:
        raise ValueError('Both active endpoints need all32 original slots')
    lower = (end['read_started_monotonic_ns'] - start['read_ended_monotonic_ns']) / 1e9
    upper = (end['read_ended_monotonic_ns'] - start['read_started_monotonic_ns']) / 1e9
    elapsed = (end['midpoint_monotonic_ns'] - start['midpoint_monotonic_ns']) / 1e9
    if not 0 < lower <= elapsed <= upper:
        raise ValueError('Nonpositive or inconsistent monotonic measurement brackets')
    slots = {}
    for slot in sorted(expected):
        first, last = start['slots'][slot], end['slots'][slot]
        if (first['pid'], first['birth']) != (last['pid'], last['birth']):
            raise ValueError('Original slot identity changed across active window')
        if first['rejected'] != 0 or last['rejected'] != 0:
            raise ValueError('Rejected frames in active window')
        delta = last['accepted'] - first['accepted']
        if type(delta) is not int or delta <= 0:
            raise ValueError('Every original slot must advance accepted frames')
        slots[slot] = dict(accepted_frames=delta, midpoint_FPS=delta / elapsed,
                           bracket_low_FPS=delta / upper, bracket_high_FPS=delta / lower)
    frames = sum(row['accepted_frames'] for row in slots.values())
    return dict(schema='robotron-selector-active32-accepted-frame-rate-v1',
                start=start, end=end, midpoint_elapsed_s=elapsed,
                elapsed_bracket_s=[lower, upper], slots=slots, accepted_frames=frames,
                aggregate_midpoint_FPS=frames / elapsed,
                aggregate_bracket_low_FPS=frames / upper, aggregate_bracket_high_FPS=frames / lower,
                useful_training_throughput_claim=False, learning_speed_claim=False)
