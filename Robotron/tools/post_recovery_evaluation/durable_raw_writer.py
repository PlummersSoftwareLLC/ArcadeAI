"""Bounded single-owner durability queue for immutable observer evidence.

The sampling thread writes and pins bytes; this thread alone owns queued file
descriptors and fsyncs them. Readiness is announced only after a sealed durable
100-sample prefix. Success requires a joined writer and a sealed complete chain.
No entry is dropped, retried, coalesced, or overwritten.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import stat
import threading
import time


def require(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def advance(chain, descriptor):
    return hashlib.sha256(bytes.fromhex(chain) + encode(descriptor)).hexdigest()


EMPTY_CHAIN = hashlib.sha256(b'robotron-durable-raw-prefix-v1').hexdigest()


class DurableRawWriter:
    CAPACITY = 128

    def __init__(self, directory, binding, *, pin, identity, fsync=os.fsync):
        self.directory = Path(directory)
        self.binding = binding
        self.pin, self.identity, self.fsync = pin, identity, fsync
        self.queue = queue.Queue(maxsize=self.CAPACITY)
        self.lock = threading.Lock()
        self.error = None
        self.closing = False
        self.submitted = 0
        self.committed = 0
        self.sample_count = 0
        self.chain = EMPTY_CHAIN
        self.sample_chain = EMPTY_CHAIN
        self.high_water = 0
        self.maximum_file_fsync_s = 0.
        self.maximum_directory_fsync_s = 0.
        self.ready = None
        self.seal = None
        self.thread = threading.Thread(target=self._run, name='original-raw-proof-durability', daemon=False)
        self.thread.start()

    def check(self):
        with self.lock:
            error = self.error
        require(error is None, 'Raw evidence durability writer failed: ' + str(error))

    def submit(self, path, value, *, kind, index):
        require(not self.closing and kind in ('sample', 'unaccepted'), 'Raw writer closed or wrong record kind')
        self.check()
        path = Path(path)
        require(path.parent == self.directory, 'Raw record outside original directory')
        fd = None
        try:
            with path.open('xb') as stream:
                stream.write(encode(dict(value, durability_record=dict(
                    sequence=self.submitted, kind=kind, index=index))))
                stream.flush()
                os.fchmod(stream.fileno(), 0o444)
                fd = os.dup(stream.fileno())
            pinned = self.pin(path)
            descriptor = dict(sequence=self.submitted, kind=kind, index=index, record=pinned)
            self.queue.put_nowait((fd, descriptor))
            fd = None  # Ownership passed to the writer, including all failure paths.
            self.submitted += 1
            self.high_water = max(self.high_water, self.queue.qsize())
            self.check()
            return pinned
        except queue.Full as failure:
            with self.lock:
                if self.error is None:
                    self.error = 'Raw durability queue capacity exceeded; original observation invalid'
            raise ValueError(self.error) from failure
        finally:
            if fd is not None:
                os.close(fd)

    def readiness(self):
        self.check()
        with self.lock:
            return self.ready

    def _sync_directory(self):
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        started = time.monotonic()
        try:
            self.fsync(fd)
        finally:
            os.close(fd)
            self.maximum_directory_fsync_s = max(self.maximum_directory_fsync_s, time.monotonic()-started)

    def _seal(self, name, value):
        path = self.directory / name
        with path.open('xb') as stream:
            stream.write(encode(value))
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            self.fsync(stream.fileno())
        self._sync_directory()
        return self.pin(path)

    def _run(self):
        failed = False
        try:
            while True:
                item = self.queue.get()
                if item is None:
                    self.queue.task_done()
                    break
                fd, descriptor = item
                try:
                    if failed:
                        continue  # Drain/close owned descriptors; failure can never seal success.
                    expected = descriptor['record']
                    require(descriptor['sequence'] == self.committed, 'Raw durability sequence differs')
                    require(self.identity(os.fstat(fd)) == expected['identity'], 'Queued file descriptor changed')
                    require(self.identity(Path(expected['path']).stat()) == expected['identity'], 'Queued path changed')
                    started = time.monotonic()
                    self.fsync(fd)
                    self.maximum_file_fsync_s = max(self.maximum_file_fsync_s, time.monotonic()-started)
                    self._sync_directory()
                    require(self.identity(os.fstat(fd)) == expected['identity']
                            and self.pin(Path(expected['path'])) == expected, 'Durable evidence changed')
                    self.chain = advance(self.chain, descriptor)
                    if descriptor['kind'] == 'sample':
                        require(descriptor['index'] == self.sample_count, 'Durable sample order differs')
                        self.sample_chain = advance(self.sample_chain, descriptor)
                        self.sample_count += 1
                    self.committed += 1
                    if self.sample_count == 100 and self.ready is None:
                        ready = self._seal('durable-readiness.json', dict(
                            schema='robotron-durable-raw-readiness-v1', binding=self.binding,
                            sample_count=100, committed_records=self.committed,
                            chain=self.chain, sample_chain=self.sample_chain,
                            committed_monotonic_s=time.monotonic()))
                        with self.lock:
                            self.ready = ready
                except BaseException as failure:
                    failed = True
                    with self.lock:
                        if self.error is None:
                            self.error = repr(failure)
                finally:
                    os.close(fd)
                    self.queue.task_done()
        except BaseException as failure:
            with self.lock:
                if self.error is None:
                    self.error = repr(failure)

    def close(self, *, timeout_s=30, successful):
        require(not self.closing, 'Raw durability finalization is single-use')
        self.closing = True
        deadline = time.monotonic() + timeout_s
        try:
            self.queue.put(None, timeout=max(.001, deadline-time.monotonic()))
        except queue.Full as failure:
            raise ValueError('Raw durability queue could not close') from failure
        self.thread.join(max(0, deadline-time.monotonic()))
        require(not self.thread.is_alive(), 'Original durability writer did not stop; success forbidden')
        self.check()
        require(self.queue.empty() and self.queue.unfinished_tasks == 0 and self.committed == self.submitted,
                'Original raw durability coverage incomplete')
        if successful:
            require(self.ready is not None, 'Durable initial100 prefix missing')
        self.seal = self._seal('durability-seal.json', dict(
            schema='robotron-durable-raw-final-seal-v1', binding=self.binding,
            committed_records=self.committed, sample_count=self.sample_count,
            chain=self.chain, sample_chain=self.sample_chain, readiness=self.ready,
            all_writer_threads_stopped=True, queue_capacity=self.CAPACITY, queue_high_water=self.high_water,
            maximum_file_fsync_s=self.maximum_file_fsync_s,
            maximum_directory_fsync_s=self.maximum_directory_fsync_s,
            sealed_monotonic_s=time.monotonic()))
        return self.seal
