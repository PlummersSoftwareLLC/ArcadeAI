#!/usr/bin/env python3
"""Isolated CPU proposal: concurrently fill two disjoint replay state fields.

This module is not imported by the trainer. It calls the existing production
``_fill_state_rows`` helper; it never selects replay samples or touches CUDA.
"""

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
import threading

import numpy as np

from Robotron.Scripts.dqn.replay_buffer import _fill_state_rows


@dataclass(frozen=True)
class FieldFill:
    output: np.ndarray
    ring: np.ndarray
    indices: np.ndarray
    banks: tuple = ()

    def run(self, fill_fn):
        return fill_fn(self.output, self.ring, self.indices, self.banks)


def validate_fields(fields):
    """Reject output aliases and malformed shapes before scheduling any work.

    Inputs must remain stable until both fields finish. The benchmark enforces
    this with private read-only source copies; production would retain the
    existing replay lock, index arrays and source references for this interval.
    """
    if len(fields) != 2:
        raise ValueError("Exactly two independent state fields are required")
    inputs = []
    for field in fields:
        output = field.output
        if (not isinstance(output, np.ndarray) or output.ndim != 2
                or output.dtype != np.dtype(np.float32)
                or not output.flags.c_contiguous or not output.flags.writeable
                or not output.flags.aligned):
            raise ValueError("Output must be a writable contiguous aligned fp32 matrix")
        count = 0
        for source, indices in ((field.ring, field.indices), *field.banks):
            if (not isinstance(source, np.ndarray) or source.ndim != 2
                    or source.shape[1] != output.shape[1]):
                raise ValueError("Source width differs from output")
            if (not isinstance(indices, np.ndarray) or indices.ndim != 1
                    or indices.dtype != np.dtype(np.int64)
                    or not indices.flags.c_contiguous or not indices.flags.aligned):
                raise ValueError("Indices must be contiguous aligned int64")
            count += len(indices)
            inputs.extend((source, indices))
        if count != len(output):
            raise ValueError("Output row count differs from selected rows")
    if fields[0].output.shape != fields[1].output.shape:
        raise ValueError("State and next-state output shapes differ")
    if np.may_share_memory(fields[0].output, fields[1].output):
        raise ValueError("Output fields may not alias each other")
    for field in fields:
        if any(np.may_share_memory(field.output, source) for source in inputs):
            raise ValueError("Output may not alias any source or index array")


def fill_sequential(fields):
    validate_fields(fields)
    return tuple(field.run(_fill_state_rows) for field in fields)


class ParallelFill:
    """Persistent two-worker executor with a synchronous ownership boundary.

    All futures are drained before return or exception propagation, including
    when submission of the second field fails. A failed output pair is invalid
    and must be discarded. The caller may reuse it only after this method has
    returned. Serializing calls and close also prevents a later request from
    overtaking an outstanding one on this executor.
    """

    def __init__(self, fill_fn=None):
        self._fill_fn = fill_fn if fill_fn is not None else _fill_state_rows
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="replay-proposal")
        self._call_lock = threading.Lock()
        self._closed = False

    def fill(self, fields):
        fields = tuple(fields)
        with self._call_lock:
            if self._closed:
                raise RuntimeError("Parallel fill is closed")
            validate_fields(fields)
            futures = []
            try:
                for field in fields:
                    futures.append(self._executor.submit(field.run, self._fill_fn))
            finally:
                # Do not let the first exception release buffer ownership while
                # its sibling is still writing. Also cover partial submission.
                wait(futures)
            return tuple(future.result() for future in futures)

    def close(self):
        with self._call_lock:
            if not self._closed:
                self._closed = True
                self._executor.shutdown(wait=True, cancel_futures=False)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
