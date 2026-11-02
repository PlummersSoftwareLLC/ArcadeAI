"""UNEXECUTED regression source; private candidate, fake clocks and temp files."""
import json
from pathlib import Path
import tempfile
import unittest

from .experiment_status_candidate import ExperimentStatusReader


class StartupGraceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / 'Robotron'
        self.campaign = self.root / 'logs/campaign'
        self.state_path = self.root / 'logs/state.json'
        self.status_path = self.campaign / 'status.json'
        self.child_path = self.campaign / '01-reference/status.json'
        self.now, self.monotonic = 1000., 0.
        self.status = dict(state='running', current_leg=1, updated_unix_s=self.now,
                           legs=[dict(index=1, role='reference', state='running', started_unix_s=960.)])
        self.write(self.state_path, dict(active_quality_job=dict(directory=str(self.campaign))))
        self.write(self.campaign / 'plan.json', dict(legs=[dict(index=1, role='reference',
            job=dict(label='reference'), evaluator_status_path='01-reference/status.json',
            receipt_path='01-reference/receipt.json')]))
        self.write(self.status_path, self.status)
        self.reader = ExperimentStatusReader(self.root, self.state_path,
                                             clock=lambda: self.now, monotonic=lambda: self.monotonic)

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def refresh(self):
        self.monotonic += 2.1
        return self.reader.snapshot()

    def test_missing_first_status_after40seconds_is_initializing_and_fresh(self):
        value = self.reader.snapshot()
        self.assertFalse(value['stale'])
        self.assertNotIn('read_error', value)
        self.assertEqual(value['legs'][0]['phase'], 'initializing')
        self.assertIsNone(value['legs'][0]['count'])
        self.assertIsNone(value['legs'][0]['started'])

    def test_exact120second_deadline_is_inclusive_then_expires(self):
        self.now = 1080.
        self.status['updated_unix_s'] = self.now
        self.write(self.status_path, self.status)
        self.assertFalse(self.reader.snapshot()['stale'])
        self.now += .001
        self.status['updated_unix_s'] = self.now
        self.write(self.status_path, self.status)
        value = self.refresh()
        self.assertTrue(value['stale'])
        self.assertIn('read_error', value)

    def test_fresh_heartbeat_does_not_slide_leg_start_deadline(self):
        for now in (1000., 1040., 1079.):
            self.now = now
            self.status['updated_unix_s'] = now
            self.write(self.status_path, self.status)
            self.assertFalse(self.refresh()['stale'])
        self.now = 1081.
        self.status['updated_unix_s'] = self.now
        self.write(self.status_path, self.status)
        self.assertTrue(self.refresh()['stale'])

    def test_controller_heartbeat_older_than30seconds_remains_stale(self):
        self.status['updated_unix_s'] = 969.
        self.write(self.status_path, self.status)
        value = self.reader.snapshot()
        self.assertTrue(value['stale'])
        self.assertIn('read_error', value)

    def test_previously_observed_count_including_zero_disappearing_fails_immediately(self):
        for count in (0, 7):
            with self.subTest(count=count):
                reader = ExperimentStatusReader(self.root, self.state_path,
                    clock=lambda: self.now, monotonic=lambda: self.monotonic)
                self.write(self.child_path, dict(phase='collecting', count=count, started=count + 1))
                self.assertEqual(reader.snapshot()['legs'][0]['count'], count)
                self.child_path.unlink()
                self.monotonic += 2.1
                value = reader.snapshot()
                self.assertTrue(value['stale'])
                self.assertIn('read_error', value)
                self.assertEqual(value['legs'][0]['count'], count)

    def test_finished_receipt_missing_never_uses_startup_grace(self):
        self.status['legs'][0]['state'] = 'finished'
        self.write(self.status_path, self.status)
        value = self.reader.snapshot()
        self.assertTrue(value['stale'])
        self.assertIn('read_error', value)

    def test_count_zero_history_survives_valid_json_omitting_count(self):
        self.write(self.child_path, dict(phase='collecting', count=0, started=16))
        self.assertEqual(self.reader.snapshot()['legs'][0]['count'], 0)
        self.write(self.child_path, dict(phase='collecting', started=16))
        intermediate = self.refresh()
        self.assertIsNone(intermediate['legs'][0]['count'])
        self.assertNotIn('read_error', intermediate)
        self.child_path.unlink()
        value = self.refresh()
        self.assertTrue(value['stale'])
        self.assertIn('read_error', value)

    def test_new_campaign_same_leg_index_gets_its_own_startup_grace(self):
        self.write(self.child_path, dict(phase='collecting', count=0, started=16))
        self.assertEqual(self.reader.snapshot()['legs'][0]['count'], 0)
        new_campaign = self.root / 'logs/new-campaign'
        plan = json.loads((self.campaign / 'plan.json').read_text())
        self.write(new_campaign / 'plan.json', plan)
        self.write(new_campaign / 'status.json', self.status)
        self.write(self.state_path, dict(active_quality_job=dict(directory=str(new_campaign))))
        value = self.refresh()
        self.assertFalse(value['stale'])
        self.assertNotIn('read_error', value)
        self.assertEqual(value['legs'][0]['phase'], 'initializing')
        self.assertIsNone(value['legs'][0]['count'])

    def test_missing_or_future_start_cannot_create_indefinite_grace(self):
        for started in (None, 1001.):
            with self.subTest(started=started):
                self.status['legs'][0]['started_unix_s'] = started
                self.write(self.status_path, self.status)
                self.assertIn('read_error', self.refresh())

    def test_noncurrent_running_leg_missing_status_is_not_initializing(self):
        self.status['current_leg'] = 2
        self.write(self.status_path, self.status)
        self.assertIn('read_error', self.reader.snapshot())

    def test_status_appears_and_transitions_to_real_collecting_counts(self):
        self.assertEqual(self.reader.snapshot()['legs'][0]['phase'], 'initializing')
        self.write(self.child_path, dict(phase='collecting', count=0, started=16, pending=16))
        value = self.refresh()
        self.assertFalse(value['stale'])
        self.assertEqual((value['legs'][0]['phase'], value['legs'][0]['count']), ('collecting', 0))


if __name__ == '__main__':
    unittest.main()
