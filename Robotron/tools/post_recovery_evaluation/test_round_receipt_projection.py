"""Actual retirement/publication race; durable/kernel evidence stays mandatory."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from . import round_health_transport_v4 as transport
from . import test_round_health_transport as previous
from .test_inflight_round_health import fixture as inflight_fixture

ROOT = Path(__file__).resolve().parents[2]
FAILED = ROOT/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/fullgame-native-observer-interface-engineering-original01'


def fixture():
    case, sample = inflight_fixture()
    sample['status']['updated_unix_s'] = sample['unix_s']
    return case, sample


class ExistingTransportPredicates(previous.RoundTransportTests):
    def setUp(self):
        for attribute, value in [('transport', transport), ('joined_fixture', fixture)]:
            current = patch.object(previous, attribute, value)
            current.start()
            self.addCleanup(current.stop)


class ActualReceiptProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = json.loads((FAILED/'case.json').read_bytes())
        root = FAILED/'runtime/main-observations'
        outcome = json.loads((root/'outcome.json').read_bytes())
        cls.previous = json.loads(Path(outcome['samples'][-1]['path']).read_bytes())['snapshot']
        cls.current = json.loads((root/'unaccepted-000003.json').read_bytes())['raw_snapshot']

    def test_actual_score_and_exited_birth_qualify_even_though_published_counts_lag(self):
        self.assertEqual(self.current['status']['completed'], 97)
        self.assertEqual(self.current['status']['active'], 95)
        self.assertEqual(len(self.current['results']), 98)
        self.assertEqual(len(self.current['actors']), 94)
        transport.validate(self.case, self.current, previous=self.previous)
        self.assertEqual(transport.base().observed_counts(self.current)['active'], 94)
        self.assertEqual(self.current['status']['active'], 95)  # Raw projection is never rewritten.

    def test_ahead_stale_future_or_inconsistent_publications_and_forged_census_are_rejected(self):
        for fault in ('ahead', 'stale', 'future', 'partition', 'retired_ahead', 'forged_census'):
            with self.subTest(fault=fault):
                sample = copy.deepcopy(self.current)
                if fault == 'ahead': sample['status']['completed'] = 99
                elif fault == 'stale': sample['status']['updated_unix_s'] = sample['unix_s']-5.01
                elif fault == 'future': sample['status']['updated_unix_s'] = sample['unix_s']+.01
                elif fault == 'partition': sample['status']['active'] -= 1
                elif fault == 'retired_ahead': sample['status']['retired'] = 98
                else: sample['observed_counts'] = dict(total=192, completed=97, retired=97, active=95, frozen=0)
                with self.assertRaises(ValueError): transport.validate(self.case, sample)

    def test_actor_disappearance_without_matching_committed_score_still_fails(self):
        current = copy.deepcopy(self.current)
        retired = next(iter(set(current['results'])-set(self.previous['results'])))
        del current['results'][retired]
        with self.assertRaisesRegex(ValueError, 'vanished'):
            transport.validate(self.case, current, previous=self.previous)

    def test_completed_actor_cannot_continue_executing_behind_a_lagging_projection(self):
        current = copy.deepcopy(self.current)
        retired = next(iter(set(current['results'])-set(self.previous['results'])))
        current['actors'][retired] = copy.deepcopy(self.previous['actors'][retired])
        current['actors'][retired]['state'] = 'S'
        with self.assertRaisesRegex(ValueError, 'Completed actor still executing'):
            transport.validate(self.case, current, previous=self.previous)


if __name__ == '__main__':
    unittest.main()
