#!/usr/bin/env python3
"""Build the optional MAME host-wait library and print its absolute cache path.

No Lua headers, Lua library, Python packages, or running MAME instance are
required. A failure leaves the launcher's existing polling fallback available.
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


SOURCE = Path(__file__).resolve().parents[1] / "Scripts" / "robotron_host_wait.c"
FLAGS = ("-O2", "-shared", "-fPIC", "-std=c11")


def default_cache_dir() -> Path:
    configured = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(configured).expanduser() if configured else Path.home() / ".cache"
    if not base.is_absolute():
        base = Path.home() / ".cache"
    return base / "robotron-hostwait"


def build(cache_dir: Path | None = None) -> Path:
    """Publish one complete library; concurrent builders share an advisory lock."""
    if platform.system() != "Linux":
        raise RuntimeError("the optional Robotron host-wait helper requires Linux")
    try:
        import fcntl
    except ImportError as error:
        raise RuntimeError("host-wait cache locking is unavailable") from error

    source = SOURCE.read_bytes()
    identity = source + repr((platform.system(), platform.machine(), FLAGS)).encode()
    fingerprint = hashlib.sha256(identity).hexdigest()[:24]
    cache = (cache_dir or default_cache_dir()).expanduser().resolve()
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    library = cache / f"robotron-hostwait-{fingerprint}.so"

    # Lock the stable lockfile rather than the replaced output inode. Holding
    # it through publication avoids duplicate builds or partial .so readers.
    with (cache / ".build.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if library.is_file() and library.stat().st_size > 0:
            return library
        compiler = shutil.which("gcc") or shutil.which("cc")
        if compiler is None:
            raise RuntimeError("no C compiler found (gcc or cc); host-wait helper unavailable")
        descriptor, temporary = tempfile.mkstemp(prefix=".hostwait-", suffix=".so", dir=cache)
        os.close(descriptor)
        try:
            result = subprocess.run(
                [compiler, *FLAGS, str(SOURCE), "-o", temporary],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                check=False, timeout=30,
            )
            if result.returncode:
                detail = result.stderr.strip() or f"compiler exit {result.returncode}"
                raise RuntimeError(f"host-wait compilation failed: {detail}")
            # mkstemp gives the shared object owner-only read/write access;
            # loading it does not require an executable filesystem mode bit.
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
        print(f"Robotron host-wait helper unavailable: {error}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
