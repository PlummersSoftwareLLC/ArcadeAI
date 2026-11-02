"""One NEW focused temp-file case; prior8 methods are not rerun."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Tests(unittest.TestCase):
    def test_actual_stale_atime_read_passes_but_SHA_or_stable_identity_changes_do_not(self):
        new = load('_fixed_stable8_entry', HERE / 'exec_declared_preview_entry_v2.py')
        old = load('_old_atime_negative_control', HERE / 'exec_declared_preview_entry_v1.py')
        with tempfile.TemporaryDirectory(prefix='entry stale atime ') as directory:
            path = Path(directory) / 'frozen source only.txt'
            raw = b'CPU fixture, no MAME or live source'; expected = hashlib.sha256(raw).hexdigest()
            path.write_bytes(raw); path.chmod(0o444)
            current = path.lstat(); os.utime(path, ns=(0, current.st_mtime_ns))
            before = path.lstat()
            with self.assertRaisesRegex(ValueError, 'changed during read'):
                old.small_frozen_path(path, expected)
            after = path.lstat()
            self.assertNotEqual(before.st_atime_ns, after.st_atime_ns)
            self.assertEqual(new.stable_source_identity(before), new.stable_source_identity(after))
            # Reset stale access time and exercise the ACTUAL corrected reader.
            os.utime(path, ns=(0, after.st_mtime_ns)); before = path.lstat()
            observed, selected = new.small_frozen_path(path, expected)
            self.assertEqual(observed, raw); self.assertEqual(selected.st_atime_ns, 0)
            self.assertNotEqual(path.lstat().st_atime_ns, 0)
            self.assertEqual(new.stable_source_identity(before), new.stable_source_identity(path.lstat()))
            with self.assertRaisesRegex(ValueError, 'SHA/identity differs'):
                new.small_frozen_path(path, '0' * 64)
            # A stable metadata change still changes the exact comparison tuple.
            before = path.lstat(); path.chmod(0o644)
            self.assertNotEqual(new.stable_source_identity(before), new.stable_source_identity(path.lstat()))
            with self.assertRaisesRegex(ValueError, 'immutable owned'):
                new.small_frozen_path(path, expected)


if __name__ == '__main__':
    unittest.main()
