import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import assess_screen_study as assessor

I = assessor.BASE/'post-recovery-evaluation-isolation-original01-20261027'
ENGINEERING = I/'screen-assessment-historical-engineering-original01'
ORIGINAL = assessor.BASE/'deadline-score32-fixed-fleet-admission-original03-preparation-20261026/fixed-RCRC-deadline32-study-original03'


class AssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = ENGINEERING/'historical-manifest.json'
        import hashlib
        cls.digest = hashlib.sha256(cls.manifest.read_bytes()).hexdigest()
        cls.original = json.loads((ORIGINAL/'root-fixed-RCRC-independent-verdict-original01.json').read_bytes())

    def test_actual_historical_four_leg_verdict_exactly_reproduced_without_promotion(self):
        verdict = json.loads((ENGINEERING/'historical-verdict.json').read_bytes())
        self.assertEqual(verdict['numerical_gates'], self.original['numerical_gates'])
        self.assertEqual(verdict['policy_decision'], 'RETAIN_PROTECTED_REFERENCE')
        self.assertFalse(verdict['promotion'])
        self.assertFalse(verdict['full_game_quality_qualified'])
        self.assertTrue(verdict['historical_replay_only'])

    def test_actual_selected_study_cannot_assess_before_any_leg_has_finished(self):
        p = I/'selected-candidate-restored-coordinator-study-original01/study/prepared-four-legs-NOT-LAUNCH-QUALIFIED.json'
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'must-not-exist.json'
            with self.assertRaises(FileNotFoundError):
                assessor.assess(p, hashlib.sha256(p.read_bytes()).hexdigest(), output)
            self.assertFalse(output.exists())

    def test_engineering_replay_cannot_be_used_as_production_authority(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, 'Engineering replay'):
            assessor.assess(self.manifest, self.digest, Path(directory)/'no.json')

    def test_exact_failed_or_foreign_original_receipts_are_rejected(self):
        original_read = assessor.read
        for fault in ('qualification', 'wrong_job', 'native_exit', 'review_exit', 'score_sum', 'score_policy'):
            def injected(pin, as_json=True):
                value = original_read(pin, as_json)
                name = Path(pin['path']).name
                if not as_json:
                    if fault in ('native_exit', 'review_exit') and name == 'original-service-show-stdout.txt':
                        value = value.replace(b'ExecMainStatus=0\n', b'ExecMainStatus=1\n')
                    return value
                value = copy.deepcopy(value)
                if fault == 'qualification' and name == 'root-R1-independent-qualified.json':
                    value['status'] = 'FAILED'
                elif fault == 'wrong_job' and name == 'independent-review.json':
                    value['original_job']['sha256'] = 'f'*64
                elif fault in ('native_exit','review_exit') and name == 'root-original-result-and-owned-release.json':
                    target = 'review-envelope' in pin['path']
                    if target == (fault == 'review_exit'):
                        value['original_exit'] = 1
                elif fault == 'score_sum' and name == 'original-deadline-score-seal.json':
                    value['score_sum'] += 1
                elif fault == 'score_policy' and name == 'original-deadline-score-seal.json':
                    value['policy']['policy_sha256'] = 'f'*64
                return value
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                out = Path(directory)/'no.json'
                with patch.object(assessor, 'read', side_effect=injected), self.assertRaises(ValueError):
                    assessor.assess(self.manifest, self.digest, out, historical_replay=True)
                self.assertFalse(out.exists())

    def test_one_winning_candidate_cannot_rescue_the_other_by_pooling(self):
        spec = importlib.util.spec_from_file_location('original_numbers', assessor.NUMERIC)
        numeric = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(numeric)
        seals = {leg: assessor.read(pin) for leg, pin in self.original['sealed_scores'].items()}
        c1 = seals['C1']
        for row in c1['rows']:
            row['score_at_deadline'] = 100_000_000
        c1.update(score_sum=32*100_000_000, mean_score=100_000_000, median_score=100_000_000)
        gates = numeric.compare_four(seals)
        self.assertTrue(gates['independent_candidates']['C1']['numerical_gate_passed'])
        self.assertFalse(gates['independent_candidates']['C2']['numerical_gate_passed'])
        self.assertGreater((c1['score_sum']+seals['C2']['score_sum'])/64, gates['reference_mean']*1.05)
        self.assertEqual(assessor.decide(gates)['policy_decision'], 'RETAIN_PROTECTED_REFERENCE')
        self.assertFalse(assessor.decide(gates)['candidate_pool_rescue'])

    def test_even_a_passing_screen_cannot_promote_or_claim_full_game_quality(self):
        result = assessor.decide(dict(both_numeric_gates_passed=True))
        self.assertEqual(result['policy_decision'], 'REQUIRE_FRESH_COMPLETE_GAME_CONFIRMATION')
        for field in ('promotion','full_game_quality_qualified','improvement_qualified','causal_learning_speed_gain_established'):
            self.assertFalse(result[field])


if __name__ == '__main__':
    unittest.main()
