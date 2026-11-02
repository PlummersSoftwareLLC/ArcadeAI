"""Bounded raw-byte queue: the sampling thread performs no evidence-file I/O.

Pending descriptors identify bytes, never pretend that an inode is durable.
Only the owned writer creates/pins/fsyncs evidence. Initial readiness requires
100 durable samples; final qualification requires a joined writer, complete
ordered pins and a sealed hash chain. Overflow and I/O errors invalidate.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import threading
import time


def require(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':'))+'\n').encode()


def advance(chain, descriptor):
    return hashlib.sha256(bytes.fromhex(chain)+encode(descriptor)).hexdigest()


EMPTY_CHAIN = hashlib.sha256(b'robotron-buffered-durable-raw-prefix-v2').hexdigest()


class BufferedRawWriter:
    CAPACITY = 128
    BYTE_CAPACITY = 128 << 20
    RECORD_LIMIT = 8 << 20

    def __init__(self, directory, binding, *, pin, identity, fsync=os.fsync, open_file=os.open):
        self.directory = Path(directory)
        require(self.directory.is_absolute() and self.directory.resolve(strict=True) == self.directory
                and not self.directory.is_symlink(), 'Canonical original evidence directory required')
        self.directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.binding, self.pin, self.identity = binding, pin, identity
        self.fsync, self.open_file = fsync, open_file
        self.queue = queue.Queue(maxsize=self.CAPACITY)
        self.lock = threading.Lock()
        self.error = None
        self.closing = False
        self.submitted = self.committed = self.sample_count = 0
        self.outstanding_records = self.outstanding_bytes = 0
        self.high_water = self.bytes_high_water = 0
        self.kind_counts = dict(sample=0, unaccepted=0)
        self.pending_records, self.records = [], []
        self.chain = self.sample_chain = EMPTY_CHAIN
        self.ready = self.seal = None
        self.maximum_write_s = self.maximum_fsync_s = 0.
        self.thread = threading.Thread(target=self._run, name='original-buffered-raw-evidence', daemon=False)
        self.thread.start()

    def check(self):
        with self.lock:
            failure = self.error
        require(failure is None, 'Buffered raw writer failed: '+str(failure))

    def _fail(self, failure):
        with self.lock:
            if self.error is None:
                self.error = str(failure)

    def submit(self, path, value, *, kind, index):
        # No stat/open/hash-file/fsync/rename occurs on this thread.
        self.check()
        require(not self.closing and kind in self.kind_counts and index == self.kind_counts[kind],
                'Closed writer or nonconsecutive original record')
        path = Path(path)
        require(path.parent == self.directory and path.name == '%s-%06d.json' % (kind, index),
                'Original raw record path differs')
        meta = dict(sequence=self.submitted, kind=kind, index=index)
        raw = encode(dict(value, durability_record=meta))
        if len(raw) > self.RECORD_LIMIT:
            self._fail('Raw record exceeds bounded8MiB limit')
            self.check()
        pending = dict(schema='robotron-queued-raw-record-v2', path=str(path),
            sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), **meta)
        with self.lock:
            if (self.outstanding_records >= self.CAPACITY
                    or self.outstanding_bytes+len(raw) > self.BYTE_CAPACITY):
                self.error = self.error or 'Raw byte/count queue capacity exceeded; original invalid'
                raise ValueError(self.error)
            require(not self.closing and self.error is None, 'Original writer is terminal')
            self.outstanding_records += 1
            self.outstanding_bytes += len(raw)
            self.high_water = max(self.high_water, self.outstanding_records)
            self.bytes_high_water = max(self.bytes_high_water, self.outstanding_bytes)
            try:
                self.queue.put_nowait((raw, pending))
            except queue.Full as failure:
                self.outstanding_records -= 1
                self.outstanding_bytes -= len(raw)
                self.error = 'Raw count queue overflow; original invalid'
                raise ValueError(self.error) from failure
            self.submitted += 1
            self.kind_counts[kind] += 1
            self.pending_records.append(pending)
        return pending

    def readiness(self):
        self.check()
        with self.lock:
            return self.ready

    def _persist(self, path, raw):
        started = time.monotonic()
        fd = self.open_file(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=self.directory_fd)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            self.maximum_write_s = max(self.maximum_write_s, time.monotonic()-started)
            syncing = time.monotonic()
            self.fsync(stream.fileno())
            self.fsync(self.directory_fd)
            self.maximum_fsync_s = max(self.maximum_fsync_s, time.monotonic()-syncing)
        pinned = self.pin(path)
        require(pinned['sha256'] == hashlib.sha256(raw).hexdigest() and pinned['bytes'] == len(raw)
                and pinned['identity']['mode'] == '0o444', 'Durable raw bytes differ')
        return pinned

    def _seal(self, name, value):
        return self._persist(self.directory/name, encode(value))

    def _run(self):
        failed = False
        while True:
            try:
                item = self.queue.get(timeout=.05)
            except queue.Empty:
                if self.closing:
                    return
                continue
            raw, pending = item
            try:
                if failed:
                    continue  # Invalid outcome only; free every remaining owned buffer.
                require(pending['sequence'] == self.committed, 'Durability sequence differs')
                pinned = self._persist(Path(pending['path']), raw)
                meta = {key:pending[key] for key in ('sequence', 'kind', 'index')}
                descriptor = dict(meta, record=pinned)
                self.chain = advance(self.chain, descriptor)
                if pending['kind'] == 'sample':
                    require(pending['index'] == self.sample_count, 'Durable sample order differs')
                    self.sample_chain = advance(self.sample_chain, descriptor)
                    self.sample_count += 1
                self.records.append(descriptor)
                self.committed += 1
                if self.sample_count == 100 and self.ready is None:
                    ready = self._seal('durable-readiness.json', dict(
                        schema='robotron-buffered-raw-readiness-v2', binding=self.binding,
                        sample_count=100, committed_records=self.committed,
                        chain=self.chain, sample_chain=self.sample_chain,
                        committed_monotonic_s=time.monotonic()))
                    with self.lock:
                        self.ready = ready
            except BaseException as failure:
                failed = True
                self._fail(repr(failure))
            finally:
                with self.lock:
                    self.outstanding_records -= 1
                    self.outstanding_bytes -= len(raw)
                self.queue.task_done()
                # Avoid retaining the final raw byte buffer while idle.
                del raw, pending, item

    def close(self, *, timeout_s=30, successful):
        require(not self.closing, 'Original buffered writer finalization is single-use')
        with self.lock:
            self.closing = True
        self.thread.join(timeout_s)
        require(not self.thread.is_alive(), 'Original buffered writer did not stop')
        try:
            self.check()
            require(self.queue.empty() and self.queue.unfinished_tasks == 0
                    and self.outstanding_records == self.outstanding_bytes == 0
                    and self.committed == self.submitted, 'Raw-byte durability coverage incomplete')
            if successful:
                require(self.ready is not None, 'Durable initial100 prefix missing')
            self.seal = self._seal('durability-seal.json', dict(
                schema='robotron-buffered-raw-final-seal-v2', binding=self.binding,
                committed_records=self.committed, sample_count=self.sample_count,
                chain=self.chain, sample_chain=self.sample_chain, readiness=self.ready,
                all_writer_threads_stopped=True, queue_capacity=self.CAPACITY,
                byte_capacity=self.BYTE_CAPACITY, queue_high_water=self.high_water,
                bytes_high_water=self.bytes_high_water, maximum_write_s=self.maximum_write_s,
                maximum_fsync_s=self.maximum_fsync_s, sealed_monotonic_s=time.monotonic()))
            return self.seal
        finally:
            os.close(self.directory_fd)
