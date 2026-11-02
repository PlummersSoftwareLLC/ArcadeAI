"""Original terminal file checks cannot be skipped by checkpoint-only options."""
from pathlib import Path
import unittest

from . import test_run_quality_campaign as campaign_tests


class ConfirmedOriginalReadbackTests(unittest.TestCase):
    def campaign(self):
        test = campaign_tests.CampaignTests()
        test.setUp()
        self.addCleanup(test.doCleanups)
        test.fill()
        self.assertTrue(test.assess()['qualified_improvement'])
        return test

    def test_missing_original_journal_blocks_even_without_checkpoint_verification(self):
        test = self.campaign()
        spec = test.plan['legs'][1]
        (Path(spec['job']['directory'])/'journal/games.jsonl').unlink()
        result = test.assess()
        self.assertFalse(result['qualified_improvement'])
        self.assertEqual(result['outcome'], 'invalid')
        from . import run_quality_campaign
        result = run_quality_campaign.assess_campaign(test.plan, test.records(), verify_checkpoint=False)
        self.assertFalse(result['qualified_improvement'])

    def test_original_byte_mutation_blocks_agreeing_score_receipt(self):
        test = self.campaign()
        spec = test.plan['legs'][1]
        path = Path(spec['job']['directory'])/'journal/games.jsonl'
        path.write_bytes(path.read_bytes()+b'\n')
        result = test.assess()
        self.assertFalse(result['qualified_improvement'])
        self.assertEqual(result['outcome'], 'invalid')
        self.assertIn('original journal bytes changed', result['legs'][1]['error'])

    def test_plan_requires_confirmed_policy_and_diagnostics_on_every_leg(self):
        from dataclasses import replace
        test = self.campaign()
        for role, job in test.config.jobs():
            self.assertEqual(job.completion_policy, 'confirmed_reset_reserves_v1')
            self.assertTrue(job.game_boundary_diagnostics)
            with self.assertRaisesRegex(ValueError, 'Confirmed full-game resets'):
                replace(job, completion_policy='wire_lives_v1').validate()
            with self.assertRaisesRegex(ValueError, 'Confirmed full-game resets'):
                replace(job, game_boundary_diagnostics=False).validate()
