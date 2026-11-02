"""Bounded host-side agent timing counters; never synchronize a device.

Inference is deterministically sampled (first call, then every ``sample_every``
calls). Refreshes are all recorded. Durations describe host elapsed time, not
CUDA kernel time: a CPU readback can include waiting for earlier GPU work.
The recorder lock is never held while the agent acquires a model lock.
"""

from bisect import bisect_left
import threading
import time


SCHEMA = "robotron-host-pipeline-v1"
LATENCY_BUCKET_UPPER_MS = (
    0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0,
    50.0, 100.0, 250.0, 500.0, 1000.0, 3000.0, None,
)
BATCH_SIZE_BUCKET_UPPER = (1, 2, 4, 8, 16, 32, 64, 128, 256, None)
_FIELDS = {
    "inference": (
        "batch_size", "training_lock_wait_ms", "sync_lock_wait_ms",
        "input_transfer_host_ms", "dispatch_host_ms", "cpu_readback_host_ms",
        "service_host_ms", "total_host_ms",
    ),
    "actor_refresh": (
        "training_lock_wait_ms", "sync_lock_wait_ms", "copy_host_ms",
        "service_host_ms", "total_host_ms",
    ),
    "target_refresh": ("host_ms",),
    "learner_priority": (
        "readback_host_ms", "cpu_bookkeeping_ms", "replay_lock_wait_ms",
        "locked_priority_ms", "replay_update_host_ms", "total_host_ms",
    ),
}


class _Distribution:
    __slots__ = ("bounds", "count", "total", "maximum", "histogram")

    def __init__(self, bounds):
        self.bounds = bounds[:-1]
        self.count = 0
        self.total = 0.0
        self.maximum = 0.0
        self.histogram = [0] * len(bounds)

    def add(self, value):
        value = max(0.0, float(value))
        self.count += 1
        self.total += value
        self.maximum = max(self.maximum, value)
        self.histogram[bisect_left(self.bounds, value)] += 1

    def snapshot(self):
        return {"count": self.count, "total": self.total, "max": self.maximum,
                "histogram": list(self.histogram)}


class PipelineTelemetry:
    """Fixed-size cumulative counters with an atomic optional drain.

    ``snapshot(reset=True)`` returns the old generation and starts a new one.
    It preserves the inference sampling phase; reporting should use the default
    non-draining snapshot and derive interval deltas from totals/counts.
    Inference ``count``/``errors`` refer to sampled calls; ``eligible_calls``
    counts all entries. Histogram bins have inclusive upper bounds; the final
    ``None`` bound denotes overflow. Missing phases have zero observations.
    A call in flight during a drain is recorded in its completion generation.
    """

    def __init__(self, sample_every=20, *, clock=time.perf_counter):
        if isinstance(sample_every, bool) or int(sample_every) != sample_every or sample_every < 1:
            raise ValueError("sample_every must be a positive integer")
        self.sample_every = int(sample_every)
        self._clock = clock
        self._lock = threading.Lock()
        self._sampling_position = 0
        self._generation = 0
        self._clear()

    def _clear(self):
        self._started = self._clock()
        self._eligible_calls = 0
        self._sections = {}
        for section, fields in _FIELDS.items():
            stats = {"count": 0, "errors": 0}
            if section == "actor_refresh":
                stats["forced_count"] = 0
            for name in fields:
                bounds = BATCH_SIZE_BUCKET_UPPER if name == "batch_size" else LATENCY_BUCKET_UPPER_MS
                stats[name] = _Distribution(bounds)
            self._sections[section] = stats

    def begin_inference(self):
        """Count an eligible subbatch; release this lock before model locks."""
        with self._lock:
            sampled = self._sampling_position % self.sample_every == 0
            self._sampling_position += 1
            self._eligible_calls += 1
            return sampled

    def _record(self, section, measurements, *, error=False, forced=False):
        # Agent callers finish their sync-lock scope before recording.
        with self._lock:
            stats = self._sections[section]
            stats["count"] += 1
            stats["errors"] += int(bool(error))
            if section == "actor_refresh":
                stats["forced_count"] += int(bool(forced))
            for name, value in measurements.items():
                stats[name].add(value)

    def record_inference(self, measurements, *, error=False):
        self._record("inference", measurements, error=error)

    def record_actor_refresh(self, measurements, *, error=False, forced=False):
        self._record("actor_refresh", measurements, error=error, forced=forced)

    def record_target_refresh(self, host_ms, *, error=False):
        self._record("target_refresh", {"host_ms": host_ms}, error=error)

    def record_learner_priority(self, measurements):
        """Existing diagnostic cadence, successful completed phases only.

        Caller has released replay lock; all values are host elapsed ms.
        CPU readback may wait for previously enqueued CUDA work.
        """
        self._record("learner_priority", measurements)

    def snapshot(self, reset=False):
        with self._lock:
            result = {
                "schema": SCHEMA, "available": True, "generation": self._generation,
                "sample_every": self.sample_every,
                "elapsed_s": max(0.0, self._clock() - self._started),
                "inference_eligible_calls": self._eligible_calls,
                "latency_bucket_upper_ms": list(LATENCY_BUCKET_UPPER_MS),
                "batch_size_bucket_upper": list(BATCH_SIZE_BUCKET_UPPER),
            }
            for section, stats in self._sections.items():
                result[section] = {name: value.snapshot() if isinstance(value, _Distribution) else value
                                   for name, value in stats.items()}
            if reset:
                self._generation += 1
                self._clear()
            return result


def unavailable_snapshot():
    """Compatibility for lightweight ``RainbowAgent.__new__`` CPU fakes."""
    result = PipelineTelemetry().snapshot()
    result["available"] = False
    result["elapsed_s"] = 0.0
    return result
