"""Regression coverage for the actual full-fleet in-flight telemetry failure."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from . import round_health_transport_v2 as transport
from . import test_round_health_transport as legacy
from .test_round_observer import RoundObserverV3Tests
from .round_observer_client_v4 import DedicatedMainHealth

ROOT = Path(__file__).resolve().parents[2]
FAILED = ROOT/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/next-full-round-hot-bridge-original01'


def fixture():
    case, sample = legacy.joined_fixture_original()
    value = sample['api']['host_pipeline']['learning_exposure']['optimizer']
    value.update(schema='robotron-optimizer-exposure-v1', since_epoch=copy.deepcopy(value['total']),
                 unclassified_started_total=0)
    return case, sample


class ExistingTransportPredicates(legacy.RoundTransportTests):
    def setUp(self):
        self.module_patch = patch.object(legacy, 'transport', transport)
        self.fixture_patch = patch.object(legacy, 'joined_fixture', fixture)
        self.module_patch.start()
        self.fixture_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.addCleanup(self.fixture_patch.stop)


class ActualInflightRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = json.loads((FAILED/'full-fleet-case.json').read_bytes())
        cls.sample = json.loads((FAILED/'runtime/main-observations/unaccepted-000003.json').read_bytes())['raw_snapshot']

    def test_actual_rejected_192_client_sample_has_same_lineage_one_inflight_and_no_unknown_outcome(self):
        self.assertEqual(self.sample['api']['client_count'], 192)
        value = self.sample['api']['host_pipeline']['learning_exposure']['optimizer']
        self.assertFalse(value['available'])
        self.assertEqual(transport.base().validate_optimizer_accounting(value), 1)
        transport.validate(self.case, self.sample)

    def test_actual_sample_corrupt_accounting_controls_lineage_and_transport_still_rejected(self):
        for fault in ('two_pending', 'unknown_outcome', 'false_balanced', 'true_pending', 'epoch_pending',
                      'classified_pending', 'negative', 'schema', 'disabled', 'lineage', 'epsilon', 'foreign_socket'):
            with self.subTest(fault=fault):
                sample = copy.deepcopy(self.sample)
                value = sample['api']['host_pipeline']['learning_exposure']['optimizer']
                if fault == 'two_pending':
                    for field in ('total', 'since_epoch'):
                        value[field]['attempts_started'] += 1
                    value['unclassified_started_total'] = 2
                elif fault == 'unknown_outcome':
                    for field in ('total', 'since_epoch'):
                        value[field]['unavailable'] = 1
                elif fault == 'false_balanced':
                    for field in ('total', 'since_epoch'):
                        value[field]['attempts_started'] -= 1
                    value['unclassified_started_total'] = 0
                elif fault == 'true_pending': value['available'] = True
                elif fault == 'epoch_pending': value['since_epoch']['attempts_started'] -= 1
                elif fault == 'classified_pending': value['unclassified_started_total'] = 0
                elif fault == 'negative': value['total']['amp_skipped'] = -1
                elif fault == 'schema': value['schema'] = 'foreign'
                elif fault == 'disabled': value['enabled'] = False
                elif fault == 'lineage': value['epoch'] += 1
                elif fault == 'epsilon': sample['api']['epsilon'] = 0
                else: sample['transport']['socket_inodes']['trainer'] = []
                with self.assertRaises(ValueError): transport.validate(self.case, sample)

    def test_accounting_transition_from_pending_to_balanced_preserves_counter_monotonicity(self):
        sample = copy.deepcopy(self.sample)
        sample['monotonic_s'] += .2
        value = sample['api']['host_pipeline']['learning_exposure']['optimizer']
        for field in ('total', 'since_epoch'):
            value[field]['outcomes_recorded'] += 1
            value[field]['applied'] += 1
        value['available'] = True
        value['unclassified_started_total'] = 0
        transport.validate(self.case, sample, previous=self.sample)


class ObserverV4Predicates(RoundObserverV3Tests):
    guard_class = DedicatedMainHealth


legacy.joined_fixture_original = legacy.joined_fixture
if __name__ == '__main__':
    unittest.main()
