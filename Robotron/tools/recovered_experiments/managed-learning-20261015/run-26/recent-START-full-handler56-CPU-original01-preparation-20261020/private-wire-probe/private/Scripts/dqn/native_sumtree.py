"""Optional exact native sum-tree propagation with a portable Python fallback.

Build once during module import, before replay/actor producer threads start.
Only the fixed sibling C source is compiled; no shell, user-provided compiler
arguments, or arbitrary source paths are accepted. The replay lock remains the
owner's responsibility because ctypes.CDLL deliberately releases the GIL.
"""

import ctypes
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sysconfig
import tempfile
import threading

import numpy as np


_FLOAT64 = np.dtype(np.float64)
_FLOAT16 = np.dtype(np.float16)
_INT64 = np.dtype(np.int64)
_LIBRARY = None
_FUNCTION = None
_GATHER_FUNCTION = None
_BATCH_FUNCTION = None
NATIVE_BATCH_ENABLED = os.getenv("DQN_NATIVE_BATCH_UPDATE", "0").strip().lower() in ("1", "true", "yes", "on")
NATIVE_BATCH_AVAILABLE = False
_BATCH_STATS_LOCK = threading.Lock()
_BATCH_COUNTS = {"success": 0, "fallback": 0, "error": 0}
NATIVE_AVAILABLE = False
NATIVE_GATHER_AVAILABLE = False
NATIVE_STATUS = "not initialized"


def _neoverse_v2():
    if platform.machine().lower() not in ("aarch64", "arm64"):
        return False
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text().lower()
    except OSError:
        return False
    fields = [line.split(":", 1) for line in cpuinfo.splitlines() if ":" in line]
    parts = [value.strip() for key, value in fields if key.strip() == "cpu part"]
    vendors = [value.strip() for key, value in fields if key.strip() == "cpu implementer"]
    # Linux reports ARM Neoverse-V2 as implementer 0x41, part 0xd4f. Requiring
    # every listed CPU avoids executing V2 instructions on mixed ARM systems.
    return (bool(parts) and all(value == "0xd4f" for value in parts)
            and bool(vendors) and all(value == "0x41" for value in vendors)
            and "asimdhp" in cpuinfo and "sve" in cpuinfo)


def _load_native():
    global _LIBRARY, _FUNCTION, _GATHER_FUNCTION, _BATCH_FUNCTION
    global NATIVE_BATCH_AVAILABLE
    global NATIVE_AVAILABLE, NATIVE_GATHER_AVAILABLE, NATIVE_STATUS
    try:
        directory = Path(__file__).resolve().parent
        source = directory / "sumtree.c"
        # Version the cache by exact source, platform, and arithmetic flags.
        flags = ("-O3", "-fno-fast-math", "-ffp-contract=off", "-shared", "-fPIC", "-std=c11")
        grace_v2 = _neoverse_v2()
        if grace_v2:
            flags += ("-mcpu=neoverse-v2", "-DROBOTRON_NEOVERSE_V2=1")
        identity = source.read_bytes() + repr((platform.system(), platform.machine(), flags)).encode()
        fingerprint = hashlib.sha256(identity).hexdigest()[:20]
        cache = directory / "__pycache__"
        cache.mkdir(exist_ok=True)
        suffix = sysconfig.get_config_var("SHLIB_SUFFIX") or ".so"
        library_path = cache / ("sumtree-" + fingerprint + suffix)
        if not library_path.is_file():
            compiler = next((path for path in ("/usr/bin/gcc", "/usr/bin/cc", "/usr/bin/clang")
                             if os.path.isfile(path) and os.access(path, os.X_OK)), None)
            if compiler is None:
                compiler = shutil.which("gcc") or shutil.which("cc")
            if compiler is None:
                raise OSError("no C compiler available")
            descriptor, temporary = tempfile.mkstemp(prefix="sumtree-build-", suffix=suffix, dir=cache)
            os.close(descriptor)
            try:
                subprocess.run(
                    [compiler, *flags, str(source), "-o", temporary],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=30,
                )
                # Concurrent startups build separate temporary files. Replacement
                # publishes a complete library and leaves already-loaded mappings
                # intact; no partially written .so is ever observable.
                os.replace(temporary, library_path)
            finally:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
        library = ctypes.CDLL(str(library_path))
        function = library.robotron_sumtree_propagate
        function.argtypes = (ctypes.c_void_p, ctypes.c_int64)
        function.restype = None
        _LIBRARY, _FUNCTION = library, function
        NATIVE_AVAILABLE = True
        NATIVE_STATUS = "exact float64 native propagation"
        batch = getattr(library, "robotron_sumtree_batch_update", None)
        if batch is not None:
            batch.argtypes = (ctypes.c_void_p, ctypes.c_int64, ctypes.c_int64,
                              ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64)
            batch.restype = ctypes.c_int
            _BATCH_FUNCTION = batch
            NATIVE_BATCH_AVAILABLE = True
        if grace_v2:
            gather = library.robotron_gather_fp16_rows
            gather.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                               ctypes.c_int64, ctypes.c_int64)
            gather.restype = ctypes.c_int
            _GATHER_FUNCTION = gather
            NATIVE_GATHER_AVAILABLE = True
            NATIVE_STATUS += "; Neoverse-V2 direct fp16 row conversion"
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError) as error:
        NATIVE_STATUS = "Python fallback: " + type(error).__name__


def propagate(tree, index):
    """Update parents natively when supported, returning False for fallback.

    Retrieve the pointer from the actual current array on every call: replay
    loading can replace a SumTree's ndarray or memmap at any time under its
    replay lock. Hold ``tree`` locally for the complete GIL-released C call.
    """
    if _FUNCTION is None:
        return False
    if (tree.dtype != _FLOAT64 or tree.ndim != 1
            or not tree.flags.c_contiguous or not tree.flags.writeable
            or not tree.flags.aligned):
        return False
    index = int(index)
    if index < 1 or index >= tree.size:
        return False
    _FUNCTION(tree.ctypes.data, index)
    return True


def gather_fp16_rows(source, indices, out=None):
    """Gather fp16 rows into allocated or preallocated fp32, or return None.

    Source may be read-only, including a replay memmap. Validate every selected
    row before entering native code; optional out must be writable contiguous
    aligned fp32, exact shape, and disjoint from source and indices. The caller
    must hold its replay lock while ctypes releases the GIL.
    """
    if _GATHER_FUNCTION is None:
        return None
    if (not isinstance(source, np.ndarray) or source.dtype != _FLOAT16
            or source.ndim != 2 or not source.flags.c_contiguous
            or not source.flags.aligned):
        return None
    if (not isinstance(indices, np.ndarray) or indices.dtype != _INT64
            or indices.ndim != 1 or not indices.flags.c_contiguous
            or not indices.flags.aligned):
        return None
    count, columns = int(indices.size), int(source.shape[1])
    if count and (int(indices.min()) < 0 or int(indices.max()) >= source.shape[0]):
        return None
    if out is not None and (
            not isinstance(out, np.ndarray) or out.dtype != np.dtype(np.float32)
            or out.shape != (count, columns) or not out.flags.c_contiguous
            or not out.flags.writeable or not out.flags.aligned
            or np.may_share_memory(out, source) or np.may_share_memory(out, indices)):
        return None
    output = np.empty((count, columns), dtype=np.float32) if out is None else out
    if count and columns:
        success = _GATHER_FUNCTION(
            source.ctypes.data, indices.ctypes.data, output.ctypes.data, count, columns,
        )
        if not success:
            return None
    return output


def _batch_update_enabled(tree, capacity, indices, priorities):
    if _BATCH_FUNCTION is None:
        return False
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
    return bool(_BATCH_FUNCTION(tree.ctypes.data, tree.size, capacity,
                       indices.ctypes.data, priorities.ctypes.data, indices.size))



def batch_update(tree, capacity, indices, priorities):
    """Default-off exact path; count completed enabled calls, never CUDA work.

    The existing replay lock owns validation and the GIL-released C call.
    Unsupported/unavailable inputs return False for the original NumPy path.
    Unexpected exceptions are counted and re-raised, never silently retried.
    """
    if not NATIVE_BATCH_ENABLED:
        return False
    try:
        used = _batch_update_enabled(tree, capacity, indices, priorities)
    except Exception:
        with _BATCH_STATS_LOCK:
            _BATCH_COUNTS["error"] += 1
        raise
    with _BATCH_STATS_LOCK:
        _BATCH_COUNTS["success" if used else "fallback"] += 1
    return used


def batch_update_status():
    """Cumulative process-local scalars only; no reset, replay or CUDA lock.

    Each enabled completed call contributes once to success/fallback/error.
    Disabled calls do no counting. Snapshot never holds another owner lock.
    """
    with _BATCH_STATS_LOCK:
        return {"schema": "robotron-native-batch-update-v1",
                "enabled": bool(NATIVE_BATCH_ENABLED),
                "available": bool(NATIVE_BATCH_AVAILABLE and _BATCH_FUNCTION is not None),
                "completed_count": sum(_BATCH_COUNTS.values()),
                "success_count": _BATCH_COUNTS["success"],
                "fallback_count": _BATCH_COUNTS["fallback"],
                "error_count": _BATCH_COUNTS["error"]}


_load_native()
