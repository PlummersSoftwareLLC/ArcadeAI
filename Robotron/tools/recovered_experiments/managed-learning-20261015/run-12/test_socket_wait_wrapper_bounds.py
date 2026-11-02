"""Prepared wrapper-only checks: fake env consumes argv; real MAME never runs."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


BASE = Path(__file__).resolve().parent
GAME = BASE.parents[2]
WRAPPER = BASE / "socket-wait-wrapper-proposed.sh"
BUILDER = BASE / "build-socket-wait-proposed.py"
MANIFEST = json.loads((BASE / "socket-wait-wrapper-bounds-prepared.json").read_text())


class WrapperBoundsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="robotron-wrapper-bounds-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.library = self.directory / "fake-library.so"
        self.library.write_bytes(b"never-loaded")
        # exec env resolves this stub through PATH. It records arguments and
        # exits; it never applies LD_PRELOAD or executes the absolute MAME argv.
        stub = self.directory / "env"
        stub.write_text("#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n")
        stub.chmod(0o700)

    def run_wrapper(self, interval, *, library=True):
        environment = dict(os.environ)
        environment.pop("LD_PRELOAD", None)
        environment.pop("ROBOTRON_SOCKET_WAIT_US", None)
        environment.pop("ROBOTRON_SOCKET_WAIT_LIBRARY", None)
        environment["PATH"] = str(self.directory) + os.pathsep + os.defpath
        if interval is not None:
            environment["ROBOTRON_SOCKET_WAIT_US"] = interval
        if library:
            environment["ROBOTRON_SOCKET_WAIT_LIBRARY"] = str(self.library)
        return subprocess.run(["/bin/bash", str(WRAPPER), "robotron", "-video", "none"],
                              env=environment, text=True, capture_output=True, timeout=3)

    def test_permitted_bounds_and_requested_pilot_values_use_fake_env_only(self):
        for value in ("100", "999", "1000", "1001", "2000", "5000", "9999", "10000"):
            with self.subTest(value=value):
                result = self.run_wrapper(value)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), [
                    "LD_PRELOAD=" + str(self.library), "ROBOTRON_SOCKET_WAIT_PORT=9998",
                    "/usr/games/mame", "robotron", "-video", "none"])
                self.assertEqual(result.stderr, "")

    def test_nonintegers_leading_zero_and_out_of_range_rejected(self):
        for value in ("0", "1", "99", "10001", "100000", "0100", "01000", "010000",
                      "001000", "-1000", "+1000", "1000.0", "1e3", " 1000", "1000 ",
                      "nan", "inf", "1000x", "１０１", "", "1\n000"):
            with self.subTest(value=value):
                result = self.run_wrapper(value)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_missing_configuration_fails_before_fake_or_real_launcher(self):
        for interval, library in ((None, True), ("1000", False)):
            result = self.run_wrapper(interval, library=library)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_only_bound_regex_and_accurate_wrapper_messages_change(self):
        before = (BASE / "socket-wait-wrapper-before.sh").read_text()
        expected = before.replace("between 100 and 1000 microseconds",
                                  "between 100 and 10000 microseconds").replace(
                                      "^([1-9][0-9]{2}|1000)$", "^([1-9][0-9]{2,3}|10000)$")
        self.assertEqual(WRAPPER.read_text(), expected)
        subprocess.run(["/bin/bash", "-n", str(WRAPPER)], check=True, timeout=3)

    def test_builder_only_module_documentation_changes(self):
        before = ast.parse((BASE / "build-socket-wait-before.py").read_text())
        after = ast.parse(BUILDER.read_text())
        self.assertIsInstance(before.body[0], ast.Expr)
        self.assertIsInstance(after.body[0], ast.Expr)
        self.assertEqual(ast.dump(ast.Module(body=before.body[1:], type_ignores=[]), include_attributes=False),
                         ast.dump(ast.Module(body=after.body[1:], type_ignores=[]), include_attributes=False))
        result = subprocess.run([sys.executable, str(BUILDER), "--help"],
                                text=True, capture_output=True, check=True, timeout=3)
        self.assertIn("100..10000", result.stdout)
        self.assertIn("0.1..10 ms", result.stdout)

    def test_actual_wrapper_builder_C_and_Lua_are_still_unmodified(self):
        for name, expected in MANIFEST["sources"].items():
            path = GAME.parent / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, str(path))

    def test_unapplied_patch_checks_cleanly(self):
        subprocess.run(["git", "apply", "--check", str(BASE / "socket-wait-wrapper-bounds.patch")],
                       cwd=GAME.parent, capture_output=True, text=True, check=True, timeout=3)


if __name__ == "__main__":
    unittest.main()
