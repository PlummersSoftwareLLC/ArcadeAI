"""Bounded replay sampling and reusable asynchronous device staging.

The replay ring remains in Grace CPU memory. A small number of pinned staging
buffers feed CUDA HBM on a dedicated stream over the Grace/Blackwell C2C link.
Only minibatches are pinned; the large replay ring is never page-locked.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field

import numpy as np
import torch


# Replay tuple fields consumed by the learner, in its original transfer order.
_FIELD_INDICES = (0, 1, 2, 3, 4, 5, 6, 9)
_FIELD_DTYPES = (
    torch.float32, torch.long, torch.float32, torch.float32,
    torch.float32, torch.float32, torch.bool, torch.float32,
)


@dataclass
class _Slot:
    host: tuple = ()
    device: tuple = ()
    signature: tuple = ()
    copy_start: object = None
    ready: object = None
    released: object = None
    has_release: bool = False
    state_views: tuple = ()


@dataclass
class PreparedBatch:
    """One slot leased to the learner until ``release()`` is called.

    ``tensors`` contains states, actions, rewards, next states, dones, horizons,
    expert flags, and PER weights. ``batch`` retains the ten-field replay tuple
    for its CPU metadata. The learner must wait on its compute stream before
    reading the tensors and release in a finally block after enqueueing work.
    """

    batch: tuple
    tensors: tuple
    sample_ms: float
    _owner: object = field(repr=False)
    _slot: _Slot = field(repr=False)
    _epoch: int = field(repr=False)
    stage_host_ms: float = 0.0
    draw_metadata: object = field(default=None, repr=False)
    _consumer_stream: object = field(default=None, repr=False)
    _released: bool = field(default=False, repr=False)
    _release_lock: object = field(default_factory=threading.Lock, repr=False)

    @property
    def is_current(self) -> bool:
        return self._epoch == self._owner._epoch and not self._owner._stop.is_set()

    @property
    def transfer_ms(self) -> float:
        # Do not add a synchronization solely to update a dashboard metric.
        if self._owner._cuda and self._slot.ready.query():
            return float(self._slot.copy_start.elapsed_time(self._slot.ready))
        return 0.0

    def wait_on_current_stream(self):
        """Order the learner's work after H2D copies without blocking the CPU."""
        if self._released:
            raise RuntimeError("Cannot use a released replay minibatch")
        if self._owner._cuda:
            with torch.cuda.device(self._owner.device):
                stream = torch.cuda.current_stream(self._owner.device)
                if self._consumer_stream is not None and self._consumer_stream != stream:
                    raise RuntimeError("A replay minibatch must be consumed on one CUDA stream")
                stream.wait_event(self._slot.ready)
                self._consumer_stream = stream
        return self.tensors

    def release(self):
        """Release the slot only after the learner's CUDA reads have completed."""
        with self._release_lock:
            if self._released:
                return
            if self._owner._cuda:
                with torch.cuda.device(self._owner.device):
                    # A skipped/discarded batch may never have joined a compute
                    # stream; its copy stream still protects staging-buffer reuse.
                    stream = self._consumer_stream or self._owner._copy_stream
                    self._slot.released.record(stream)
                    self._slot.has_release = True
            self._released = True
            self._owner._recycle(self._slot)


class ReplayPrefetcher:
    """Single replay producer with a bounded pool of independently leased slots.

    Sampling keeps the replay buffer's existing locking and quota semantics.
    Default staging copies happen after sample returns, outside that lock.
    Opt-in direct filling writes final state buffers under the replay lock and
    stages metadata afterwards. CPU machines use the same ownership protocol.
    """

    def __init__(self, memory, batch_size, beta_fn, device, use_amp=False,
                 depth=2, enabled_fn=None, min_replay_size=None, direct_state_fill=False,
                 trace_observer=None):
        self.memory = memory
        self.batch_size = max(1, int(batch_size))
        self.beta_fn = beta_fn
        self.device = torch.device(device)
        self.use_amp = bool(use_amp)
        self.trace_observer = trace_observer
        # Default remains the proven allocating sample/stage path. Unrelated
        # replay implementations without sample_into retain that fallback.
        self.direct_state_fill = bool(direct_state_fill and callable(getattr(memory, "sample_into", None))
                                      and int(getattr(memory, "state_size", 0)) > 0)
        self.depth = max(1, int(depth))
        self.enabled_fn = enabled_fn or (lambda: True)
        self.min_replay_size = max(
            self.batch_size,
            self.batch_size if min_replay_size is None else int(min_replay_size),
        )
        self._cuda = self.device.type == "cuda"
        self._stop = threading.Event()
        self._epoch = 0
        self._state = threading.Condition()
        self._active_epoch = None
        self._error = None
        self.produced_batches = 0
        self.direct_state_batches = 0
        self._ready = queue.Queue(maxsize=self.depth)
        self._free = queue.Queue(maxsize=self.depth)
        self._slots = [_Slot() for _ in range(self.depth)]
        self._copy_stream = None
        if self._cuda:
            with torch.cuda.device(self.device):
                self._copy_stream = torch.cuda.Stream(device=self.device)
                for slot in self._slots:
                    slot.copy_start = torch.cuda.Event(enable_timing=True)
                    slot.ready = torch.cuda.Event(enable_timing=True)
                    slot.released = torch.cuda.Event()
        for slot in self._slots:
            self._free.put_nowait(slot)
        self._thread = threading.Thread(
            target=self._produce, name="robotron-replay-prefetch", daemon=True,
        )
        self._thread.start()

    def _recycle(self, slot):
        if not self._stop.is_set():
            self._free.put_nowait(slot)

    def _ensure_slot(self, slot, shapes):
        signature = tuple(zip(shapes, _FIELD_DTYPES))
        if slot.signature != signature:
            slot.host = tuple(
                torch.empty(shape, dtype=dtype, pin_memory=self._cuda)
                for shape, dtype in zip(shapes, _FIELD_DTYPES)
            )
            slot.device = tuple(
                torch.empty_like(host, device=self.device) for host in slot.host
            ) if self._cuda else slot.host
            slot.signature = signature
            slot.state_views = (slot.host[0].numpy(), slot.host[3].numpy())

    def _direct_state_outputs(self, slot):
        rows, columns = self.batch_size, int(self.memory.state_size)
        self._ensure_slot(slot, ((rows, columns), (rows,), (rows,), (rows, columns),
                                 (rows,), (rows,), (rows,), (rows,)))
        return slot.state_views

    def _stage(self, slot, batch):
        if len(batch) != 10:
            raise ValueError("Replay prefetch requires the ten-field replay tuple")
        source = tuple(np.asarray(batch[i]) for i in _FIELD_INDICES)
        self._ensure_slot(slot, tuple(arr.shape for arr in source))
        # Reuse allocations; conversion of tiny metadata fields occurs on CPU.
        # Keep states fp32: existing fp32 hall-of-fame rows must not be rounded
        # simply because autocast is enabled for the model's tensor operations.
        for index, (host, arr) in enumerate(zip(slot.host, source)):
            if self.direct_state_fill and index in (0, 3):
                view = slot.state_views[0 if index == 0 else 1]
                if (arr.shape == view.shape and arr.dtype == view.dtype
                        and arr.strides == view.strides and arr.ctypes.data == view.ctypes.data):
                    continue
            host.copy_(torch.from_numpy(arr))
        if self._cuda:
            with torch.cuda.stream(self._copy_stream):
                slot.copy_start.record(self._copy_stream)
                for target, host in zip(slot.device, slot.host):
                    target.copy_(host, non_blocking=True)
                slot.ready.record(self._copy_stream)

    def _produce(self):
        slot = None
        try:
            if self._cuda:
                torch.cuda.set_device(self.device)
            while not self._stop.is_set():
                if not self.enabled_fn() or len(self.memory) < self.min_replay_size:
                    self._stop.wait(0.02)
                    continue
                try:
                    slot = self._free.get(timeout=0.05)
                except queue.Empty:
                    continue
                if self._stop.is_set():
                    break
                # Producer-only wait: the learner remains free to enqueue work.
                # Host and CUDA storage are both protected until the prior
                # consumer's release event has passed.
                if self._cuda and slot.has_release:
                    slot.released.synchronize()
                    slot.has_release = False
                with self._state:
                    # enabled_fn may have changed while this producer waited
                    # for a leased slot. Serialize this check with invalidate
                    # so a paused producer cannot publish after a replay reset.
                    if not self.enabled_fn() or len(self.memory) < self.min_replay_size:
                        self._recycle(slot)
                        slot = None
                        continue
                    epoch = self._epoch
                    self._active_epoch = epoch
                try:
                    sample_t0 = time.perf_counter()
                    if self.direct_state_fill:
                        states_out, next_states_out = self._direct_state_outputs(slot)
                        if self.trace_observer is None:
                            batch = self.memory.sample_into(
                                self.batch_size, states_out, next_states_out, beta=float(self.beta_fn()),
                            )
                        else:
                            batch = self.trace_observer.sample(self.memory, self.batch_size,
                                float(self.beta_fn()), state_out=(states_out, next_states_out))
                        self.direct_state_batches += int(batch is not None)
                    else:
                        if self.trace_observer is None:
                            batch = self.memory.sample(self.batch_size, beta=float(self.beta_fn()))
                        else:
                            batch = self.trace_observer.sample(self.memory, self.batch_size,
                                float(self.beta_fn()))
                    sample_ms = (time.perf_counter() - sample_t0) * 1000.0
                    if batch is None:
                        self._recycle(slot)
                        slot = None
                        self._stop.wait(0.01)
                        continue
                    self.produced_batches += 1
                    stage_t0 = time.perf_counter()
                    self._stage(slot, batch)
                    stage_host_ms = (time.perf_counter()-stage_t0)*1000.0
                    prepared = PreparedBatch(
                        tuple(batch), slot.device, sample_ms, self, slot, epoch,
                        stage_host_ms=stage_host_ms,
                        draw_metadata=getattr(batch, "draw_metadata", None),
                    )
                    with self._state:
                        if epoch != self._epoch or self._stop.is_set():
                            prepared.release()
                        else:
                            # The slot pool bounds all queued + leased batches,
                            # so a free slot always implies a free queue entry.
                            self._ready.put_nowait(prepared)
                    slot = None
                finally:
                    with self._state:
                        self._active_epoch = None
                        self._state.notify_all()
        except Exception as exc:
            with self._state:
                self._error = exc
                self._active_epoch = None
                self._state.notify_all()
            self._stop.set()
        finally:
            # Shutdown never frees buffers while an outstanding H2D copy uses
            # their pinned storage. Leased buffers remain owned by their batch.
            if self._cuda:
                try:
                    self._copy_stream.synchronize()
                except Exception as exc:
                    with self._state:
                        if self._error is None:
                            self._error = exc
                        self._state.notify_all()
                    self._stop.set()

    def _raise_error(self):
        if self._error is not None:
            raise RuntimeError("Replay prefetch producer failed") from self._error

    def get(self, timeout=0.05):
        """Lease a current batch, or return None while replay/pipeline warms up."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            self._raise_error()
            remaining = max(0.0, deadline - time.monotonic())
            try:
                prepared = self._ready.get(timeout=remaining)
            except queue.Empty:
                self._raise_error()
                return None
            if prepared.is_current:
                return prepared
            prepared.release()
            if time.monotonic() >= deadline:
                return None

    def invalidate(self, wait=True, timeout=2.0):
        """Discard queued old replay; call around replay restore/clear operations.

        Pause via ``enabled_fn`` before mutating replay, invalidate before and
        after the mutation, then resume. Leased batches expose ``is_current``;
        their owner still must release them. Returns whether any old-generation
        producer work has finished within the requested timeout.
        """
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._state:
            self._epoch += 1
            epoch = self._epoch
            while True:
                try:
                    prepared = self._ready.get_nowait()
                except queue.Empty:
                    break
                prepared.release()
            if wait:
                while self._active_epoch is not None and self._active_epoch < epoch:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0.0:
                        return False
                    self._state.wait(remaining)
        self._raise_error()
        return True

    def close(self, timeout=5.0):
        """Stop sampling and join without waiting for learner-owned leases."""
        self._stop.set()
        with self._state:
            self._epoch += 1
            while True:
                try:
                    prepared = self._ready.get_nowait()
                except queue.Empty:
                    break
                prepared.release()
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout=max(0.0, float(timeout)))
        return not self._thread.is_alive()
