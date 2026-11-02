"""Actual observer sample/rejection and independent raw-wire join; CPU fixtures."""
import copy
import importlib.util
import json
import math
from pathlib import Path
from unittest.mock import Mock, patch

from test_pilot_runtime_guard_inflight_v1 import GuardFixture, guard, reviewer
import test_review_original_pilot_inflight_v1 as review_cases


class RawGuardWitnessTests(GuardFixture):
    def samples(self):
        return [self.reader.read_pin(pin) for pin in self.g.samples]

    def read(self, entry, as_json=True):
        return self.reader.read_pin(entry, as_json=as_json)

    def test_full_sample_accepts_nonfinite_diagnostics_and_archives_exact_response(self):
        for value in (float('inf'), float('-inf'), float('nan')):
            self.api['grad_norm'] = value
            self.advance()
            self.g.sample()
            sample = self.samples()[-1]
            raw = self.read(sample['API_wire'], False)
            self.assertEqual(json.loads(raw)['learner_frame_count'], self.api['learner_frame_count'])
            self.assertFalse(math.isfinite(json.loads(raw)['grad_norm']))
            self.assertNotIn('grad_norm', sample['API'])
            self.assertIsNone(self.g.failed)
            self.assertFalse(self.g.rejected_observations)

    def test_actual_health_still_rejects_nonfinite_critical_value_after_raw_archive(self):
        path = guard.GAME  # Fixture GAME is private; load immutable real health explicitly.
        actual = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/'
            'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')
        spec = importlib.util.spec_from_file_location('_actual_raw_guard_health', actual)
        health = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(health)
        self.g.window.healthy = health.healthy
        self.api['lr'] = float('inf')
        self.advance()
        with self.assertRaises(ValueError): self.g.sample()
        self.assertEqual(len(self.g.rejected_observations), 1)
        witness = self.read(self.g.rejected_observations[0])
        raw = self.read(witness['attempt']['API_wire'], False)
        self.assertEqual(json.loads(raw)['lr'], float('inf'))
        self.assertTrue(witness['attempt']['API_parsed'])

    def test_optimizer_failure_with_nonfinite_diagnostic_retains_one_complete_rejection(self):
        self.api['grad_norm'] = float('inf')
        self.api['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable'] += 1
        self.advance()
        with self.assertRaises(ValueError): self.g.sample()
        self.assertEqual(len(self.g.rejected_observations), 1)
        witness = self.read(self.g.rejected_observations[0])
        api = json.loads(self.read(witness['attempt']['API_wire'], False))
        self.assertTrue(math.isinf(api['grad_norm']))
        self.assertEqual(api['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable'], 1)

    def test_malformed_response_is_archived_before_parser_rejects(self):
        self.advance()
        raw = b'{"truncated":'
        with patch.object(guard, 'read_API_bytes', return_value=raw), self.assertRaises(ValueError):
            self.g.sample()
        witness = self.read(self.g.rejected_observations[0])
        self.assertEqual(self.read(witness['attempt']['API_wire'], False), raw)
        self.assertTrue(witness['attempt']['API_received'])
        self.assertFalse(witness['attempt']['API_parsed'])

    def test_fetch_failure_preserves_explicit_absence_without_another_fetch(self):
        self.advance()
        with patch.object(guard, 'read_API_bytes', side_effect=TimeoutError('CPU transport fixture')) as fetch:
            with self.assertRaises(TimeoutError): self.g.sample()
        fetch.assert_called_once()
        witness = self.read(self.g.rejected_observations[0])
        self.assertIsNone(witness['attempt']['API_wire'])
        self.assertFalse(witness['attempt']['API_received'])

    def test_independent_review_rejoins_original_nonfinite_payload(self):
        self.api['grad_norm'] = float('inf')
        self.advance()
        self.g.sample()
        original = self.samples()
        manifest = dict(API_witness_format=guard.raw_witness_module().FORMAT)
        decoded = reviewer.validate_raw_API_samples(manifest, original, self.read)
        self.assertTrue(math.isinf(decoded[-1]['API']['grad_norm']))
        self.assertNotIn('grad_norm', original[-1]['API'])
        altered = copy.deepcopy(original)
        altered[-1]['API']['learner_frame_count'] += 1
        with self.assertRaises(ValueError): reviewer.validate_raw_API_samples(manifest, altered, self.read)

    def test_independent_review_requires_format_and_unique_original_wire_paths(self):
        self.advance()
        self.g.sample()
        with self.assertRaises(ValueError): reviewer.validate_raw_API_samples({}, self.samples(), self.read)
        samples = self.samples()
        samples[-1] = copy.deepcopy(samples[0])
        with self.assertRaises(ValueError):
            reviewer.validate_raw_API_samples(dict(API_witness_format=guard.raw_witness_module().FORMAT), samples, self.read)

    def test_original_nonfinite_runtime_cannot_be_claimed_repaired(self):
        prior = review_cases.prior_invalid_runtime(self.reader)
        reviewer.validate_prior_nonfinite_runtime(prior, self.read)
        target = prior['prior_nonfinite_runtime']['path']
        original = self.read(prior['prior_nonfinite_runtime'])
        for key, value in [('original_reported_full_games', 1),
                           ('original_failed_API_snapshot_retained', True),
                           ('exact_failed_nonfinite_field_known', True)]:
            altered = copy.deepcopy(original)
            altered[key] = value
            def changed(entry, as_json=True):
                return altered if entry['path'] == target and as_json else self.read(entry, as_json)
            with self.subTest(key=key), self.assertRaises(ValueError):
                reviewer.validate_prior_nonfinite_runtime(prior, changed)
