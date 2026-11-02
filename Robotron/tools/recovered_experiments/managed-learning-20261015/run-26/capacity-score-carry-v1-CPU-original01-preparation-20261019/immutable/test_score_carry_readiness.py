"""Original evidence bindings and runtime limits for the corrected-source study."""
import copy
from pathlib import Path
import unittest

import review_original_pilot_inflight_v1 as review
import test_review_original_pilot_inflight_v1 as fixtures


class ScoreCarryReadinessTests(unittest.TestCase):
    def setUp(self):
        self.reader = review.protector()
        self.prior = fixtures.prior_invalid_runtime(self.reader)

    def read(self, entry, as_json=True):
        return self.reader.read_pin(entry, as_json=as_json)

    def test_actual_original_readback_package_and_both_failed_studies_pass(self):
        review.validate_score_carry_readiness(self.prior, self.read)

    def test_missing_any_new_evidence_rejects(self):
        for key in ('score_carry_CPU_readback', 'corrected_source_package',
                    'corrected_parent_package', 'preceding_score_tear_invalid_study'):
            value = dict(self.prior)
            del value[key]
            with self.subTest(key=key), self.assertRaises((KeyError, ValueError)):
                review.validate_score_carry_readiness(value, self.read)

    def check_mutations(self, key, mutations):
        target = self.prior[key]['path']
        original = self.read(self.prior[key])
        for label, mutate in mutations:
            data = copy.deepcopy(original)
            mutate(data)
            def changed(entry, as_json=True):
                if entry['path'] == target and as_json:
                    return data
                return self.read(entry, as_json)
            with self.subTest(change=label), self.assertRaises((ValueError, KeyError)):
                review.validate_score_carry_readiness(self.prior, changed)

    def test_CPU_status_scope_and_both_handler_paths_are_mandatory(self):
        changes = [(key, lambda d, key=key, value=value: d.update({key: value}))
                   for key, value in [('status', 'FAIL'), ('primitive_tests', 13),
                       ('regression_tests', 87), ('production_changed', True),
                       ('GPU_MAME_validation_complete', True), ('quality_qualification', True),
                       ('original_scientific_studies_still_invalid', False), ('handler_runs', [])]]
        changes += [('scenario-count', lambda d: d['handler_runs'][0].update(scenarios=43))]
        self.check_mutations('score_carry_CPU_readback', changes)

    def test_wrong_handler_scope_parent_or_package_rejects(self):
        self.check_mutations('corrected_source_package', [
            ('count', lambda d: d.update(source_count=122)),
            ('runtime-byte', lambda d: d['files'].update({'Scripts/dqn/socket_server.py': '0' * 64})),
            ('unrelated-byte', lambda d: d['files'].update({'Scripts/dqn/model.py': '0' * 64})),
            ('extra-change', lambda d: d['changed_parent_files'].append('Scripts/dqn/model.py')),
            ('wrong-parent', lambda d: d['parent_manifest'].update(sha256='0' * 64)),
        ])

    def test_original_score_tear_remains_invalid_with_zero_valid_games(self):
        self.check_mutations('preceding_score_tear_invalid_study', [
            ('valid', lambda d: d.update(original_study_valid=True)),
            ('retry', lambda d: d.update(original_study_retried=True)),
            ('review-retry', lambda d: d.update(original_scientific_audits_rerun=True)),
            ('false-game', lambda d: d.update(independently_validated_full_games=1)),
            ('erase-original-count', lambda d: d.update(original_reported_count=0)),
        ])

    def test_wrong_original_proof_hash_rejects_before_reads(self):
        prior = copy.deepcopy(self.prior)
        prior['score_carry_CPU_readback']['sha256'] = '0' * 64
        def no_read(*args):
            self.fail('Changed proof hash must reject before any evidence read')
        with self.assertRaises(ValueError):
            review.validate_score_carry_readiness(prior, no_read)

    def test_selected_native_bound_allows_full_tail_beyond_old_5280_limit(self):
        for duration in (1, 5280, 5400, 6000, 6300):
            with self.subTest(duration=duration):
                review.validate_service_interval(duration, 100, 100 + duration)

    def test_invalid_service_clocks_and_excess_bound_reject(self):
        for values in ((0, 1, 2), (1, 0, 2), (1, 2, 1), (3, 1, 2),
                       (6300, 100, 6400.001), (True, 1, 2),
                       (float('nan'), 1, 2), (1, 1, float('inf'))):
            with self.subTest(values=values), self.assertRaises(ValueError):
                review.validate_service_interval(*values)


if __name__ == '__main__':
    unittest.main(verbosity=2)
