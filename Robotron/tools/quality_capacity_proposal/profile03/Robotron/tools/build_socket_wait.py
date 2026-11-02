#!/usr/bin/env python3
"""Build the optional select readiness preload and print its absolute cache path.

The output belongs in LD_PRELOAD for the MAME child only. Enable bounded waits
with ROBOTRON_SOCKET_WAIT_US=100..10000 (0.1..10 ms); the default is disabled. No running
trainer, MAME process, Lua headers or external Python packages are required.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


SOURCE = Path(__file__).resolve().parents[1] / "Scripts" / "robotron_socket_wait.c"
FLAGS = ("-O2", "-shared", "-fPIC", "-std=c11")
LIBRARIES = ("-ldl", "-pthread")


def default_cache_dir() -> Path:
    configured = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(configured).expanduser() if configured else Path.home() / ".cache"
    if not base.is_absolute():
        base = Path.home() / ".cache"
    return base / "robotron-socketwait"


def build(cache_dir: Path | None = None) -> Path:
    """Publish one complete library under a content hash and advisory lock."""
    if platform.system() != "Linux":
        raise RuntimeError("the optional Robotron select-wait preload requires Linux")
    try:
        import fcntl
    except ImportError as error:
        raise RuntimeError("select-wait cache locking is unavailable") from error
    source = SOURCE.read_bytes()
    identity = source + repr((platform.system(), platform.machine(), FLAGS, LIBRARIES)).encode()
    fingerprint = hashlib.sha256(identity).hexdigest()[:24]
    cache = (cache_dir or default_cache_dir()).expanduser().resolve()
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    library = cache / f"robotron-socketwait-{fingerprint}.so"
    with (cache / ".build.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if library.is_file() and library.stat().st_size > 0:
            return library
        compiler = shutil.which("gcc") or shutil.which("cc")
        if compiler is None:
            raise RuntimeError("no C compiler found (gcc or cc); select-wait preload unavailable")
        descriptor, temporary = tempfile.mkstemp(prefix=".socketwait-", suffix=".so", dir=cache)
        os.close(descriptor)
        try:
            result = subprocess.run(
                [compiler, *FLAGS, str(SOURCE), "-o", temporary, *LIBRARIES],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                check=False, timeout=30,
            )
            if result.returncode:
                detail = result.stderr.strip() or f"compiler exit {result.returncode}"
                raise RuntimeError(f"select-wait compilation failed: {detail}")
            os.replace(temporary, library)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return library


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="override the per-user build cache")
    arguments = parser.parse_args(argv)
    try:
        path = build(arguments.cache_dir)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Robotron select-wait preload unavailable: {error}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
