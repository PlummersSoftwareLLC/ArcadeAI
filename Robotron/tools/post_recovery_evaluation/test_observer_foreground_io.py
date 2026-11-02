"""Reproduce stalls that remain after only fsync moves off the sampling thread.

These synthetic-health fixtures run the actual strict worker loop. They must
fail; their outcomes can never qualify a runtime or a game cohort.
"""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from . import test_async_observer_run as harness_module


class ForegroundIOTests(unittest.TestCase):
    def fixture(self, directory):
        harness = harness_module.SyntheticObserverRunTests()
        return harness.run_fixture(directory, fail_certificate=False)

    def test_foreground_raw_file_creation_stall_invalidates_actual_projection(self):
        actual = Path.open
        injected = []

        def delayed(path, *args, **kwargs):
            if path.name == 'sample-000105.json' and args and args[0] == 'xb':
                injected.append(True)
                time.sleep(.8)
            return actual(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'open', delayed):
            code, outcome, seen = self.fixture(Path(directory))
        self.assertEqual(injected, [True])
        self.assertEqual(code, 1)
        self.assertFalse(outcome['success'])
        self.assertIn('Main projection source exceeds500ms', outcome['error'])
        self.assertTrue(outcome['all_writer_threads_stopped'])

    def test_foreground_live_rename_stall_invalidates_actual_physical_sampling(self):
        actual = os.replace
        writes = []
        injected = []

        def delayed(source, destination, *args, **kwargs):
            if Path(destination).name == 'live.json':
                writes.append(True)
                if len(writes) == 105:
                    injected.append(True)
                    time.sleep(.8)
            return actual(source, destination, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, patch.object(os, 'replace', delayed):
            code, outcome, seen = self.fixture(Path(directory))
        self.assertEqual(injected, [True])
        self.assertEqual(code, 1)
        self.assertFalse(outcome['success'])
        self.assertIn('Accepted main proof gap exceeds500ms', outcome['error'])
        self.assertTrue(outcome['all_writer_threads_stopped'])


if __name__ == '__main__':
    unittest.main()
