"""Bank field output and bounded host phase telemetry; never takes replay locks.

Streaming is explicitly opt-in at buffer construction. Both routes preserve
the padded .npy geometry. Generation publication/capture/revision logic remains
in replay_buffer; this helper does not read live replay storage.
"""
from collections import deque
from contextlib import contextmanager
import errno
import io
import math
import os
import threading
import time

import numpy as np


CHUNK_BYTES = 8 * 1024 * 1024
PHASES = ("create", "write", "mmap_flush", "mmap_close", "file_open",
          "file_fsync", "file_close")


def stream_output_enabled(environ=None):
    """Read once at replay construction; invalid explicit settings fail closed."""
    value = (os.environ if environ is None else environ).get("DQN_STREAM_BANK_OUTPUT", "0")
    value = str(value).strip().lower()
    if value not in ("0", "false", "no", "off", "", "1", "true", "yes", "on"):
        raise ValueError("DQN_STREAM_BANK_OUTPUT must be a boolean (default 0)")
    enabled = value in ("1", "true", "yes", "on")
    if enabled and not (callable(getattr(os, "pwrite", None))
                        and callable(getattr(os, "ftruncate", None))):
        raise RuntimeError("DQN_STREAM_BANK_OUTPUT requires pwrite and ftruncate")
    return enabled


class BankOutputTelemetry:
    """Cumulative/non-draining field-file host timings, bounded to seven phases.

    A single serialized bank writer owns this recorder. Its scalar lock never
    acquires replay, writer, model, or reporting locks. A snapshot is taken only
    after releasing those locks. No device calls, learning clocks or RNG change.
    """

    def __init__(self, stream_output=False):
        self.backend = "stream" if stream_output else "memmap"
        self._lock = threading.Lock()
        self._started = time.monotonic_ns()
        self._active = None
        self._recent = deque(maxlen=32)
        self._totals = {name: dict(count=0, errors=0, host_total_ms=0.0,
            host_max_ms=0.0, logical_bytes=0, payload_bytes=0) for name in PHASES}

    @contextmanager
    def phase(self, name, *, bank, field, logical_bytes=0, payload_bytes=0):
        if name not in self._totals:
            raise ValueError("Unknown bank output phase")
        started = time.monotonic_ns()
        event = dict(bank=bank, field=field, phase=name,
                     logical_bytes=int(logical_bytes), payload_bytes=int(payload_bytes))
        with self._lock:
            self._active = dict(event, started_monotonic_ns=started)
        failed = True
        try:
            yield
            failed = False
        finally:
            ended = time.monotonic_ns()
            elapsed_ms = (ended - started) / 1e6
            with self._lock:
                total = self._totals[name]
                total["count"] += 1
                total["errors"] += int(failed)
                total["host_total_ms"] += elapsed_ms
                total["host_max_ms"] = max(total["host_max_ms"], elapsed_ms)
                total["logical_bytes"] += int(logical_bytes)
                total["payload_bytes"] += int(payload_bytes)
                self._recent.append(dict(event, host_ms=elapsed_ms,
                    ended_monotonic_ns=ended, error=failed))
                self._active = None

    def snapshot(self):
        with self._lock:
            active = dict(self._active) if self._active else None
            if active:
                active["elapsed_host_ms"] = (time.monotonic_ns()
                                             - active["started_monotonic_ns"]) / 1e6
            return dict(schema="robotron-bank-output-v1", available=True,
                stream_output_enabled=self.backend == "stream", backend=self.backend,
                scope="host elapsed; field files only; not device/disk service time",
                started_monotonic_ns=self._started, active=active,
                totals={name: dict(value) for name, value in self._totals.items()},
                recent=[dict(value) for value in self._recent])


def _pwrite_all(fd, data, offset):
    while data:
        try:
            amount = os.pwrite(fd, data, offset)
        except InterruptedError:
            continue
        if not isinstance(amount, int) or not 0 < amount <= len(data):
            raise OSError(errno.EIO, "bank output pwrite made invalid progress")
        offset += amount
        data = data[amount:]


def _stream_array(path, source, *, count, stride, lengths, telemetry, bank, field):
    # Existing compact snapshots are C-contiguous fixed-width row arrays.
    # Fail explicitly if an unexpected source violates that contract.
    if (not isinstance(source, np.ndarray) or source.ndim < 1
            or source.dtype.hasobject or source.dtype.itemsize <= 0
            or not source.flags.c_contiguous):
        raise ValueError("Stream bank source must be contiguous, fixed-width and object-free")
    lengths = np.asarray(lengths)
    if (not isinstance(count, int) or isinstance(count, bool) or count < 0
            or not isinstance(stride, int) or isinstance(stride, bool) or stride <= 0
            or lengths.ndim != 1 or lengths.dtype.kind not in "iu"
            or len(lengths) != count or np.any(lengths < 0)
            or np.any(lengths > stride)
            or sum(int(value) for value in lengths) != source.shape[0]):
        raise ValueError("Stream bank episode lengths/geometry differ from compact rows")
    shape = (count * stride, *source.shape[1:])
    row_bytes = math.prod(source.shape[1:]) * source.dtype.itemsize
    logical_bytes = count * stride * row_bytes
    # This public v1 writer is byte-identical to open_memmap(version=None) for
    # all current bank descriptors/shapes. Oversized exotic descriptors fail
    # before opening a file, rather than silently changing the file format.
    header = io.BytesIO()
    np.lib.format.write_array_header_1_0(header, dict(
        descr=np.lib.format.dtype_to_descr(source.dtype), fortran_order=False, shape=shape))
    header_bytes = header.getvalue()
    with telemetry.phase("file_open", bank=bank, field=field):
        fd = os.open(os.fspath(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | getattr(os, "O_CLOEXEC", 0), 0o666)
    try:
        with telemetry.phase("create", bank=bank, field=field):
            _pwrite_all(fd, memoryview(header_bytes), 0)
            os.ftruncate(fd, len(header_bytes) + logical_bytes)
        with telemetry.phase("write", bank=bank, field=field,
                             logical_bytes=logical_bytes, payload_bytes=source.nbytes):
            raw = memoryview(source).cast("B") if source.size else memoryview(b"")
            cursor = 0
            for episode, length in enumerate(lengths):
                amount = int(length) * row_bytes
                destination = len(header_bytes) + episode * stride * row_bytes
                for first in range(0, amount, CHUNK_BYTES):
                    size = min(CHUNK_BYTES, amount - first)
                    _pwrite_all(fd, raw[cursor + first:cursor + first + size], destination + first)
                cursor += amount
        with telemetry.phase("file_fsync", bank=bank, field=field):
            os.fsync(fd)
    finally:
        with telemetry.phase("file_close", bank=bank, field=field):
            os.close(fd)


def _memmap_array(path, source, *, count, stride, lengths, telemetry, bank, field):
    # Original operation order and assignment arithmetic are preserved.
    with telemetry.phase("create", bank=bank, field=field):
        output = np.lib.format.open_memmap(path, mode="w+", dtype=source.dtype,
                                          shape=(count * stride, *source.shape[1:]))
    try:
        with telemetry.phase("write", bank=bank, field=field,
                             logical_bytes=count * stride * math.prod(source.shape[1:]) * source.dtype.itemsize,
                             payload_bytes=source.nbytes):
            cursor = 0
            for episode, length in enumerate(lengths):
                length = int(length)
                begin = episode * stride
                output[begin:begin + length] = source[cursor:cursor + length]
                cursor += length
        with telemetry.phase("mmap_flush", bank=bank, field=field):
            output.flush()
    finally:
        with telemetry.phase("mmap_close", bank=bank, field=field):
            output._mmap.close()
    with telemetry.phase("file_open", bank=bank, field=field):
        stream = open(path, "rb")
    try:
        with telemetry.phase("file_fsync", bank=bank, field=field):
            os.fsync(stream.fileno())
    finally:
        with telemetry.phase("file_close", bank=bank, field=field):
            stream.close()


def write_bank_array(path, source, *, count, stride, lengths, stream_output,
                     telemetry, bank, field):
    writer = _stream_array if stream_output else _memmap_array
    return writer(path, source, count=count, stride=stride, lengths=lengths,
                  telemetry=telemetry, bank=bank, field=field)
