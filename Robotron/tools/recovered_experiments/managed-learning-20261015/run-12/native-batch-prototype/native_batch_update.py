"""Offline prototype only. No production module import or live replay access."""
import ctypes
import hashlib
from pathlib import Path
import platform
import subprocess

import numpy as np


DIRECTORY = Path(__file__).resolve().parent
FLAGS = ("-O3", "-fno-fast-math", "-ffp-contract=off", "-shared", "-fPIC", "-std=c11")
_FUNCTION = None
_LIBRARY = None


def load():
    global _FUNCTION, _LIBRARY
    if _FUNCTION is None:
        source = DIRECTORY / "batch_update.c"
        identity = source.read_bytes() + repr((FLAGS, platform.machine())).encode()
        cache = DIRECTORY / "private-cache"
        cache.mkdir(exist_ok=True)
        target = cache / ("batch-update-" + hashlib.sha256(identity).hexdigest()[:20] + ".so")
        if not target.is_file():
            subprocess.run(["/usr/bin/gcc", *FLAGS, str(source), "-o", str(target)],
                           check=True, capture_output=True, timeout=30)
        library = ctypes.CDLL(str(target))
        function = library.robotron_sumtree_batch_update
        function.argtypes = (ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64,
                             ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64)
        function.restype = ctypes.c_int
        _LIBRARY, _FUNCTION = library, function
    return _FUNCTION


def try_batch_update(tree, capacity, indices, priorities):
    """Return False without mutation for every unsupported ABI input.

    The owner must hold its existing replay lock while CDLL releases the GIL.
    Non-finite priorities retain the original NumPy path and its diagnostics.
    """
    if (not isinstance(tree, np.ndarray) or tree.dtype != np.dtype(np.float64)
            or tree.ndim != 1 or not tree.flags.c_contiguous
            or not tree.flags.aligned or not tree.flags.writeable
            or not isinstance(capacity, (int, np.integer))
            or capacity < 1 or capacity > (2**63 - 1) // 2
            or tree.size != 2 * capacity):
        return False
    if (not isinstance(indices, np.ndarray) or indices.dtype != np.dtype(np.int64)
            or indices.ndim != 1 or not indices.flags.c_contiguous
            or not indices.flags.aligned or not isinstance(priorities, np.ndarray)
            or priorities.dtype != np.dtype(np.float64) or priorities.ndim != 1
            or not priorities.flags.c_contiguous or not priorities.flags.aligned
            or indices.size != priorities.size or indices.size == 0):
        return False
    if (np.may_share_memory(tree, indices) or np.may_share_memory(tree, priorities)
            or int(indices.min()) < 0 or int(indices.max()) >= capacity
            or not np.isfinite(priorities).all()):
        return False
    return bool(load()(tree.ctypes.data, tree.size, capacity,
                       indices.ctypes.data, priorities.ctypes.data, indices.size))


def batch_update(owner, indices, priorities, original):
    """Model the proposed hook; preserve the original path on ABI rejection."""
    if try_batch_update(owner.tree, owner.capacity, indices, priorities):
        maximum = float(priorities.max())
        if maximum > owner.max_priority:
            owner.max_priority = maximum
        return True
    original(owner, indices, priorities)
    return False
