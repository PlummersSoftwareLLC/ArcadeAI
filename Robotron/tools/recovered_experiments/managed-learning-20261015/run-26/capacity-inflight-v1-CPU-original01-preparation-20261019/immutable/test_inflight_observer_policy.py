"""CPU-only accounting and failure-evidence cases for the future observer."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pilot_runtime_guard_inflight_v1 as guard
import review_original_pilot_inflight_v1 as review
import test_pilot_runtime_guard_inflight_v1 as guard_cases
import test_review_original_pilot_inflight_v1 as review_cases


def pending(value, count=1):
    for bucket in ('total', 'since_epoch'):
        value[bucket]['attempts_started'] = value[bucket]['outcomes_recorded'] + count
    value['unclassified_started_total'] = count
    value['available'] = count == 0


def complete(value, count=1):
    for bucket in ('total', 'since_epoch'):
        for field in ('attempts_started', 'outcomes_recorded', 'applied'):
            value[bucket][field] += count


class InflightGuardTests(guard_cases.GuardFixture):
    def optimizer(self):
        return self.api['host_pipeline']['learning_exposure']['optimizer']

    def test_one_coherent_unfinished_update_then_drain_preserves_identity(self):
        value = self.optimizer()
        pending(value)
        self.advance()
        self.g.sample()
        self.assertFalse(self.reader.read_pin(self.g.samples[-1])['API']['host_pipeline']
                         ['learning_exposure']['optimizer']['available'])
        for bucket in ('total', 'since_epoch'):
            value[bucket]['outcomes_recorded'] += 1
            value[bucket]['applied'] += 1
        pending(value, 0)
        self.advance()
        self.g.sample()
        self.assertIsNone(self.g.pending_since)
        self.assertIsNone(self.g.failed)

    def test_advancing_attempt_numbers_do_not_hide_a_missing_drain(self):
        pending(self.optimizer())
        for _ in range(6):
            self.advance()
            self.g.sample()
        self.advance()
        with self.assertRaisesRegex(ValueError, 'did not drain'):
            self.g.sample()
        self.assertEqual(len(self.g.rejected_observations), 1)

    def test_two_unfinished_updates_are_rejected(self):
        pending(self.optimizer(), 2)
        self.advance()
        with self.assertRaisesRegex(ValueError, 'in-flight accounting'):
            self.g.sample()

    def test_availability_must_match_complete_counters(self):
        self.optimizer()['available'] = False
        self.advance()
        with self.assertRaisesRegex(ValueError, 'availability'):
            self.g.sample()

    def test_true_availability_cannot_hide_an_unfinished_update(self):
        pending(self.optimizer())
        self.optimizer()['available'] = True
        self.advance()
        with self.assertRaisesRegex(ValueError, 'availability'):
            self.g.sample()

    def test_boolean_counter_is_not_an_integer_counter(self):
        self.optimizer()['total']['unavailable'] = False
        self.advance()
        with self.assertRaisesRegex(ValueError, 'integers'):
            self.g.sample()

    def test_outcome_conservation_is_required(self):
        self.optimizer()['total']['applied'] += 1
        self.advance()
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            self.g.sample()

    def test_unclassified_outcome_is_rejected_even_with_complete_totals(self):
        value = self.optimizer()
        for bucket in ('total', 'since_epoch'):
            for key in ('attempts_started', 'outcomes_recorded', 'unavailable'):
                value[bucket][key] += 1
        value['available'] = False
        self.advance()
        with self.assertRaisesRegex(ValueError, 'unclassified'):
            self.g.sample()

    def test_consistent_but_regressed_counters_are_rejected(self):
        complete(self.optimizer(), -1)
        with self.assertRaisesRegex(ValueError, 'regressed'):
            self.g.sample()

    def test_failed_observation_keeps_the_complete_rejected_API(self):
        self.g.record_birth(self.owner)
        self.optimizer()['epoch'] += 1
        self.advance()
        expected = self.get_API()
        with patch.object(self.g, 'interrupt_original') as stop:
            self.g.on_tick(dict(MainPID=str(self.owner['pid'])), self.owner)
        stop.assert_called_once()
        witness = self.reader.read_pin(self.g.rejected_observations[0])
        self.assertEqual(witness['attempt']['API'], expected)
        self.assertEqual(witness['original_private_owner'], self.owner)
        self.assertFalse(witness['main_touched'])
        self.api['host_pipeline']['learning_exposure']['optimizer']['epoch'] += 10
        self.assertEqual(self.reader.read_pin(self.g.rejected_observations[0]), witness)
        self.g.finish_main_observation()
        manifest = self.reader.read_pin(self.g.main_manifest)
        self.assertEqual(manifest['status'], 'FAILED')
        self.assertEqual(manifest['rejected_observations'], self.g.rejected_observations)

    def test_failure_before_API_read_records_absence_without_a_second_read(self):
        self.window.owner_and_files.side_effect = ValueError('synthetic source change')
        with patch.object(guard, 'read_API') as api, self.assertRaises(ValueError):
            self.g.sample()
        api.assert_not_called()
        witness = self.reader.read_pin(self.g.rejected_observations[0])
        self.assertIsNone(witness['attempt']['API'])
        self.assertIn('synthetic source change', witness['error'])


class InflightReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = review_cases.MainObservationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_independent_review_accepts_one_coherent_inflight_then_drain(self):
        middle = self.fixture.samples[1]['API']['host_pipeline']['learning_exposure']['optimizer']
        pending(middle)
        last = self.fixture.samples[2]['API']['host_pipeline']['learning_exposure']['optimizer']
        complete(last)
        self.fixture.validate()

    def test_independent_review_rejects_two_unfinished_updates(self):
        pending(self.fixture.samples[1]['API']['host_pipeline']['learning_exposure']['optimizer'], 2)
        with self.assertRaisesRegex(ValueError, 'Unfinished'):
            self.fixture.validate()

    def test_independent_review_requires_baseline_epoch_even_if_all_samples_agree(self):
        for sample in self.fixture.samples:
            sample['API']['host_pipeline']['learning_exposure']['optimizer']['epoch'] += 1
        with self.assertRaisesRegex(ValueError, 'epoch changed'):
            self.fixture.validate()

    def test_independent_review_rejects_progress_with_no_observed_drain_for_a_minute(self):
        first = self.fixture.samples[0]
        self.fixture.samples = []
        for index in range(8):
            sample = copy.deepcopy(first)
            sample['monotonic_s'] += index * 10
            sample['unix_s'] += index * 10
            sample['API']['ts'] = sample['unix_s']
            for key in ('frame_count', 'learner_frame_count', 'optimized_samples', 'training_steps'):
                sample['API'][key] += 100 * index
            optimizer = sample['API']['host_pipeline']['learning_exposure']['optimizer']
            complete(optimizer, index)
            pending(optimizer)
            sample['API']['host_pipeline']['learning_exposure']['replay']['accepted_learner_total'] += index
            sample['autosave']['mtime_ns'] = int((sample['unix_s'] - 5) * 1e9)
            self.fixture.samples.append(sample)
        with self.assertRaisesRegex(ValueError, 'drain within60'):
            self.fixture.validate()

    def test_independent_review_rejects_a_manifest_that_hides_a_rejection(self):
        self.fixture.manifest['rejected_observations'] = [{'path': '/synthetic/rejected.json'}]
        with self.assertRaisesRegex(ValueError, 'scope or result'):
            self.fixture.validate()

    def test_independent_review_rejects_counter_regression_with_advancing_work(self):
        last = self.fixture.samples[2]['API']['host_pipeline']['learning_exposure']['optimizer']
        complete(last, -1)
        with self.assertRaisesRegex(ValueError, 'regressed'):
            self.fixture.validate()


class PriorFailureTests(unittest.TestCase):
    def setUp(self):
        self.reader = review.protector()
        self.prior = review_cases.prior_invalid_runtime(self.reader)

    def test_actual_original_failed_runtime_and_one_rejected_review_remain_failed(self):
        review.validate_prior_invalid_runtime(self.prior, self.reader.read_pin)

    def test_prior_invalid_runtime_cannot_be_reinterpreted_as_valid(self):
        def read(entry, as_json=True):
            result = self.reader.read_pin(entry, as_json=as_json)
            if entry == self.prior['controller_result']:
                result['valid'] = True
            return result
        with self.assertRaisesRegex(ValueError, 'reinterpreted'):
            review.validate_prior_invalid_runtime(self.prior, read)

    def test_missing_original_failed_sample_cannot_be_claimed_reconstructed(self):
        def read(entry, as_json=True):
            result = self.reader.read_pin(entry, as_json=as_json)
            if entry == self.prior['source_diagnostic']:
                result['precise_original_stop_cause_proven'] = True
            return result
        with self.assertRaisesRegex(ValueError, 'missing original'):
            review.validate_prior_invalid_runtime(self.prior, read)


class ActualExposureSourceTests(unittest.TestCase):
    def test_original_telemetry_source_has_a_valid_single_inflight_state(self):
        path = guard.GAME / 'Scripts/dqn/learning_exposure.py'
        spec = importlib.util.spec_from_file_location('_real_exposure_observer_test', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        optimizer = module.OptimizerExposure()
        with self.assertRaises(ValueError):
            review.inspect_optimizer_observation(optimizer.snapshot())
        optimizer.finish(optimizer.begin(), 'unscaled')
        self.assertEqual(review.inspect_optimizer_observation(optimizer.snapshot()), 0)
        ticket = optimizer.begin()
        self.assertEqual(review.inspect_optimizer_observation(optimizer.snapshot()), 1)
        optimizer.finish(ticket, 'unscaled')
        self.assertEqual(review.inspect_optimizer_observation(optimizer.snapshot()), 0)


if __name__ == '__main__':
    unittest.main()
