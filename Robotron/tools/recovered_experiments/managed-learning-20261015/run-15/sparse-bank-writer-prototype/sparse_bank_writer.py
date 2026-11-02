"""Isolated DEFAULT-OFF bank output writer experiment; never imported by production.

The input is the existing compact/coherent replay-bank snapshot. This module
does not acquire replay/model locks, inspect replay storage, create output
memmaps, or change the snapshot/capture/dirty-revision protocol. It retains the
existing generation/CURRENT/fsync/previous-generation publication order.

This tests a possible mitigation for a host stall, not its established cause.
"""
from collections import deque
from contextlib import contextmanager
import errno
import io
import json
import math
import os
import shutil
import threading
import time
import uuid

import numpy as np


SCHEMA = "robotron-bank-generation-v1"
FIELDS = ("states", "next_states", "actions", "rewards", "dones",
          "horizons", "is_expert", "actor_kind")
MAX_CHUNK_BYTES = 8 * 1024 * 1024


class PhaseTelemetry:
    """Bounded scalar host timings, with no replay/model lock acquisition.

    All phases are wall-clock host durations. fsync includes filesystem/kernel
    waiting; close is an ordinary descriptor close (there is no output mmap).
    completed phases include failed phases; no device timer or barrier is used.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._totals = {}
        self._recent = deque(maxlen=64)
        self._active = None

    @contextmanager
    def phase(self, name, *, field=None, logical_bytes=0, payload_bytes=0):
        started = time.perf_counter_ns()
        event = dict(phase=name, field=field, logical_bytes=int(logical_bytes),
                     payload_bytes=int(payload_bytes))
        with self._lock:
            self._active = dict(event, started_monotonic_ns=started)
        failed = True
        try:
            yield
            failed = False
        finally:
            duration = (time.perf_counter_ns() - started) / 1e6
            with self._lock:
                total = self._totals.setdefault(name, dict(count=0, errors=0,
                    host_total_ms=0.0, host_max_ms=0.0, logical_bytes=0,
                    payload_bytes=0))
                total["count"] += 1
                total["errors"] += int(failed)
                total["host_total_ms"] += duration
                total["host_max_ms"] = max(total["host_max_ms"], duration)
                total["logical_bytes"] += int(logical_bytes)
                total["payload_bytes"] += int(payload_bytes)
                self._recent.append(dict(event, host_ms=duration, error=failed))
                self._active = None

    def snapshot(self):
        with self._lock:
            return dict(schema="sparse-bank-writer-phases-v1", scope="host elapsed",
                active=dict(self._active) if self._active else None,
                totals={key: dict(value) for key, value in self._totals.items()},
                recent=[dict(value) for value in self._recent])


def _pwrite_all(fd, view, offset):
    """Bounded writes, preserving raw dtype bits and handling short writes."""
    while view:
        try:
            amount = os.pwrite(fd, view, offset)
        except InterruptedError:
            continue
        if not isinstance(amount, int) or amount <= 0 or amount > len(view):
            raise OSError(errno.EIO, "pwrite made invalid progress")
        offset += amount
        view = view[amount:]


def _validate_array(source, count, stride, lengths):
    if not isinstance(source, np.ndarray) or source.ndim < 1:
        raise ValueError("Snapshot source must be a NumPy row array")
    if source.dtype.hasobject or not source.flags.c_contiguous:
        raise ValueError("Snapshot source must be C-contiguous and object-free")
    if source.dtype.itemsize <= 0:
        raise ValueError("Snapshot dtype must have positive itemsize")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("count must be a nonnegative Python integer")
    if not isinstance(stride, int) or isinstance(stride, bool) or stride <= 0:
        raise ValueError("stride must be a positive Python integer")
    lengths = np.asarray(lengths)
    if (lengths.ndim != 1 or lengths.dtype.kind not in "iu"
            or len(lengths) != count or np.any(lengths > stride)
            or np.any(lengths < 0)):
        raise ValueError("Invalid per-episode valid lengths")
    total = sum(int(length) for length in lengths)
    if source.shape[0] != total:
        raise ValueError("Compact row count differs from episode lengths")
    return tuple(int(value) for value in source.shape[1:]), lengths


def write_sparse_npy(path, source, *, count, stride, lengths, telemetry=None,
                     chunk_bytes=MAX_CHUNK_BYTES, phase_hook=None, field=None):
    """Write exactly the bytes open_memmap(w+) writes, without an output mmap.

    Newly exclusive-created/truncated file holes are zero. Only valid episode
    prefixes are pwrite'd, in bounded views of the already-owned compact source;
    no dense padded array or source-to-bytes copy is made. All current bank
    dtypes/shapes use the public NumPy v1 header writer, which emits the SAME
    canonical header as open_memmap(version=None) for this geometry. An exotic
    descriptor too large for v1 fails before creating a file; it is not silently
    reformatted. Tests pin compatibility against the installed NumPy version.
    """
    trailing, lengths = _validate_array(source, count, stride, lengths)
    if (not isinstance(chunk_bytes, int) or isinstance(chunk_bytes, bool)
            or not 1 <= chunk_bytes <= MAX_CHUNK_BYTES):
        raise ValueError("chunk_bytes must be an integer in [1, 8 MiB]")
    telemetry = telemetry if telemetry is not None else PhaseTelemetry()
    header = io.BytesIO()
    np.lib.format.write_array_header_1_0(header, dict(
        descr=np.lib.format.dtype_to_descr(source.dtype), fortran_order=False,
        shape=(count * stride, *trailing)))
    header_bytes = header.getvalue()
    row_bytes = math.prod(trailing) * source.dtype.itemsize
    logical_bytes = count * stride * row_bytes
    payload_bytes = source.nbytes
    fd = os.open(os.fspath(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL
                 | getattr(os, "O_CLOEXEC", 0), 0o666)
    hook = phase_hook if phase_hook is not None else lambda *_: None
    try:
        with telemetry.phase("header_and_truncate", field=field,
                             logical_bytes=logical_bytes):
            _pwrite_all(fd, memoryview(header_bytes), 0)
            os.ftruncate(fd, len(header_bytes) + logical_bytes)
        hook("after_header", field)
        with telemetry.phase("write", field=field, logical_bytes=logical_bytes,
                             payload_bytes=payload_bytes):
            raw = memoryview(source).cast("B") if source.size else memoryview(b"")
            cursor = 0
            for episode, length in enumerate(lengths):
                amount = int(length) * row_bytes
                destination = len(header_bytes) + episode * stride * row_bytes
                for first in range(0, amount, chunk_bytes):
                    part = min(chunk_bytes, amount - first)
                    _pwrite_all(fd, raw[cursor + first:cursor + first + part],
                                destination + first)
                cursor += amount
        hook("after_write", field)
        with telemetry.phase("fsync", field=field):
            os.fsync(fd)
        hook("after_fsync", field)
    finally:
        with telemetry.phase("close", field=field):
            os.close(fd)
    hook("after_close", field)
    return dict(logical_bytes=logical_bytes, payload_bytes=payload_bytes,
                file_bytes=len(header_bytes) + logical_bytes)


def write_generation(owner, snapshot, dirpath, *, enabled=False, telemetry=None,
                     phase_hook=None, chunk_bytes=MAX_CHUNK_BYTES):
    """DEFAULT-OFF adapter for tests only; production never imports this file.

    The owner is the existing replay object and supplies its current resolver,
    fsync-directory method, and legacy writer. The enabled path acquires NONE
    of its locks. Existing _persist_bank remains responsible for coherent
    capture and revision/epoch bookkeeping before/after disk I/O.
    """
    if not enabled:
        return owner._write_bank_generation(snapshot, dirpath)
    bank = snapshot["bank"]
    if bank not in ("hof", "ephof") or set(snapshot["arrays"]) != set(FIELDS):
        raise ValueError("Invalid bank or field set")
    lengths = snapshot["meta"]["ep_len"]
    for source in snapshot["arrays"].values():
        _validate_array(source, snapshot["count"], snapshot["stride"], lengths)
    telemetry = telemetry if telemetry is not None else PhaseTelemetry()
    hook = phase_hook if phase_hook is not None else lambda *_: None
    os.makedirs(dirpath, exist_ok=True)
    generations = os.path.join(dirpath, "generations")
    os.makedirs(generations, exist_ok=True)
    identifier = "gen-" + uuid.uuid4().hex
    directory = os.path.join(generations, identifier)
    pointer = os.path.join(dirpath, "CURRENT.json")
    previous = None
    if os.path.isfile(pointer):
        previous = owner._resolve_bank_directory(bank, dirpath)[1]
    os.mkdir(directory)
    temporary_pointer = pointer + "." + uuid.uuid4().hex + ".tmp"
    published = False
    try:
        for field, source in snapshot["arrays"].items():
            write_sparse_npy(os.path.join(directory, f"{bank}_{field}.npy"),
                source, count=snapshot["count"], stride=snapshot["stride"],
                lengths=lengths, telemetry=telemetry, chunk_bytes=chunk_bytes,
                phase_hook=hook, field=field)
        meta_path = os.path.join(directory, f"{bank}_meta.npz")
        stream = open(meta_path, "xb")
        try:
            with telemetry.phase("metadata_write"):
                np.savez(stream, **snapshot["meta"])
                stream.flush()
            with telemetry.phase("fsync", field="metadata"):
                os.fsync(stream.fileno())
        finally:
            with telemetry.phase("close", field="metadata"):
                stream.close()
        hook("after_metadata", None)
        with telemetry.phase("directory_fsync", field="generation"):
            owner._fsync_directory(directory)
            owner._fsync_directory(generations)
        selected = dict(schema=owner._BANK_SCHEMA, bank=bank,
                        generation=identifier, previous=previous,
                        mutation_generation=snapshot["revision"])
        stream = open(temporary_pointer, "x")
        try:
            with telemetry.phase("selector_write"):
                json.dump(selected, stream, sort_keys=True, allow_nan=False)
                stream.write("\n")
                stream.flush()
            with telemetry.phase("fsync", field="selector"):
                os.fsync(stream.fileno())
        finally:
            with telemetry.phase("close", field="selector"):
                stream.close()
        hook("before_replace", None)
        with telemetry.phase("publish_replace"):
            os.replace(temporary_pointer, pointer)
            published = True
        hook("after_replace", None)
        with telemetry.phase("directory_fsync", field="bank"):
            owner._fsync_directory(dirpath)
        hook("after_publish_fsync", None)
        with telemetry.phase("cleanup"):
            keep = {identifier, previous}
            for name in os.listdir(generations):
                if (name.startswith("gen-") and len(name) == 36 and name not in keep
                        and all(char in "0123456789abcdef" for char in name[4:])):
                    shutil.rmtree(os.path.join(generations, name))
    finally:
        if os.path.exists(temporary_pointer):
            os.unlink(temporary_pointer)
        if not published:
            shutil.rmtree(directory, ignore_errors=True)
