"""CPU-only checks for the native MAME host sleep and its cached builder."""

import concurrent.futures
import contextlib
import ctypes
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

try:
    from . import build_host_wait
except ImportError:
    import build_host_wait


class HostWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "linux" or not (shutil.which("gcc") or shutil.which("cc")):
            raise unittest.SkipTest("native host-wait checks require Linux and a C compiler")
        cls.temporary = tempfile.TemporaryDirectory(prefix="robotron-hostwait-test-")
        cls.cache = Path(cls.temporary.name)
        cls.path = build_host_wait.build(cls.cache)
        cls.library = ctypes.CDLL(str(cls.path))
        cls.wait = cls.library.robotron_socket_wait
        cls.wait.argtypes = [ctypes.c_void_p]
        cls.wait.restype = ctypes.c_int
        cls.wait_us = cls.library.robotron_socket_wait_us
        cls.wait_us.argtypes = []
        cls.wait_us.restype = ctypes.c_uint

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_environment_validation_and_clamp(self):
        for text, expected in (
                ("", 0), ("0", 0), ("-3", 0), ("200", 200), ("1000", 1000),
                ("10000", 10000), ("10001", 10000), ("999999999", 10000),
                ("abc", 0), ("1.5", 0), ("100x", 0), ("1e3", 0),
                ("99999999999999999999999999999999", 0)):
            with self.subTest(value=text), patch.dict(os.environ, {"ROBOTRON_SOCKET_WAIT_US": text}):
                self.assertEqual(self.wait_us(), expected)
        with patch.dict(os.environ):
            os.environ.pop("ROBOTRON_SOCKET_WAIT_US", None)
            self.assertEqual(self.wait_us(), 0)

    def test_lua_entry_sleeps_without_consuming_a_core(self):
        # Exercise the exact Lua entry point with no Lua interpreter or state.
        # Across many calls the wall/CPU difference detects busy-loop waiting.
        with patch.dict(os.environ, {"ROBOTRON_SOCKET_WAIT_US": "1000"}):
            wall_start, cpu_start = time.perf_counter(), time.thread_time()
            for _ in range(100):
                self.assertEqual(self.wait(None), 0)
            wall, cpu = time.perf_counter() - wall_start, time.thread_time() - cpu_start
        self.assertGreaterEqual(wall, .095)
        self.assertLess(cpu, wall * .35, f"host wait consumed {cpu:.4f}s CPU / {wall:.4f}s wall")

    def test_zero_and_invalid_wait_return_immediately(self):
        for text in ("0", "invalid", "-10"):
            with self.subTest(value=text), patch.dict(os.environ, {"ROBOTRON_SOCKET_WAIT_US": text}):
                started = time.perf_counter()
                for _ in range(100):
                    self.assertEqual(self.wait(None), 0)
                self.assertLess(time.perf_counter() - started, .05)

    def test_upper_bound_is_used_by_lua_entry(self):
        with patch.dict(os.environ, {"ROBOTRON_SOCKET_WAIT_US": "500000"}):
            started = time.perf_counter()
            self.assertEqual(self.wait(None), 0)
            elapsed = time.perf_counter() - started
        self.assertGreaterEqual(elapsed, .009)
        self.assertLess(elapsed, .20)

    def test_cache_reuses_complete_library_without_compiler(self):
        before = self.path.stat().st_mtime_ns
        with patch.object(build_host_wait.shutil, "which", return_value=None):
            self.assertEqual(build_host_wait.build(self.cache), self.path)
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_concurrent_builders_publish_same_loadable_file(self):
        cache = self.cache / "concurrent"
        command = [sys.executable, str(Path(build_host_wait.__file__)), "--cache-dir", str(cache)]
        def run_builder(_):
            return subprocess.run(command, capture_output=True, text=True, timeout=40, check=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(run_builder, range(4)))
        paths = {result.stdout.strip() for result in results}
        self.assertEqual(len(paths), 1)
        self.assertTrue(all(not result.stderr for result in results))
        library = ctypes.CDLL(paths.pop())
        self.assertTrue(library.robotron_socket_wait)
        self.assertEqual(len(list(cache.glob("*.so"))), 1)
        self.assertFalse(list(cache.glob(".hostwait-*")))

    def test_failure_has_stderr_and_no_path(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(build_host_wait.shutil, "which", return_value=None), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = build_host_wait.main(["--cache-dir", str(self.cache / "no-compiler")])
        self.assertEqual(status, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("no C compiler", stderr.getvalue())

    def test_library_has_no_lua_dependencies_or_unresolved_lua_symbols(self):
        readelf = shutil.which("readelf")
        if readelf is None:
            self.skipTest("readelf unavailable")
        dynamic = subprocess.run([readelf, "-d", str(self.path)], check=True,
                                 capture_output=True, text=True).stdout
        self.assertNotRegex(dynamic.lower(), r"needed[^\n]*lua")
        symbols = subprocess.run([readelf, "-Ws", str(self.path)], check=True,
                                 capture_output=True, text=True).stdout
        undefined = [line for line in symbols.splitlines() if " UND " in line]
        self.assertFalse(any("lua_" in line.lower() for line in undefined))


if __name__ == "__main__":
    unittest.main()
