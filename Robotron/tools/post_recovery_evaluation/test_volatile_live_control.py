"""Actual tmpfs publication and exact owned release; no scientific artifacts."""
import json
import os
import secrets
from pathlib import Path
import unittest

from .volatile_live_control_v1 import VolatileLiveControl, path_for


class VolatileControlTests(unittest.TestCase):
    def test_actual_tmpfs_publication_atomic_replacement_and_owned_release(self):
        nonce = secrets.token_hex(16)
        c = VolatileLiveControl(nonce, dict(engineering_only=True))
        try:
            self.assertEqual(c.path, path_for(nonce))
            self.assertEqual(c.owner['device'], Path('/dev/shm').stat().st_dev)
            self.assertEqual(c.owner['mode'], '0o700')
            c.publish(dict(index=1))
            value = dict(index=2)
            c.publish(value)
            value['index'] = 99
            self.assertEqual(json.loads((c.path/'live.json').read_bytes()), dict(index=2))
            self.assertFalse((c.path/'live.next').exists())
        finally:
            release = c.close()
        self.assertTrue(release['directory_absent'])
        self.assertEqual(release['last_publication']['value'], dict(index=2))
        self.assertFalse(c.path.exists())
        with self.assertRaises(ValueError):
            c.close()
        with self.assertRaises(ValueError):
            c.publish(dict(index=3))

    def test_duplicate_nonce_cannot_adopt_an_existing_directory(self):
        nonce = secrets.token_hex(16)
        c = VolatileLiveControl(nonce, {})
        try:
            with self.assertRaises(FileExistsError):
                VolatileLiveControl(nonce, {})
        finally:
            c.close()

    def test_unknown_file_is_preserved_and_prevents_namespace_deletion(self):
        c = VolatileLiveControl(secrets.token_hex(16), {})
        foreign = c.path/'unknown.json'
        foreign.write_text('ENGINEERING ONLY')
        try:
            with self.assertRaisesRegex(ValueError, 'Unknown'):
                c.close()
            self.assertTrue(foreign.exists())
        finally:
            foreign.unlink()  # The fixture creator removes its own file.
            c.close()

    def test_oversized_publication_and_invalid_nonce_are_rejected(self):
        with self.assertRaises(ValueError):
            path_for('../invalid')
        c = VolatileLiveControl(secrets.token_hex(16), {})
        try:
            with self.assertRaisesRegex(ValueError, '128KiB'):
                c.publish(dict(payload='x'*(128<<10)))
            self.assertEqual(os.listdir(c.path), [])
        finally:
            c.close()


if __name__ == '__main__':
    unittest.main()
