"""Gate regression tests using the actual archived rejected four-leg screen.

Production-shaped replay fixtures remain temporary engineering data. They never
change any scores, close a new scientific scope, or authorize a payload.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import prepare_fullgame_study as prep
from . import assess_screen_study as assessor

I=prep.BASE/'post-recovery-evaluation-isolation-original01-20261027'


class FullgamePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='robotron-fullgame-preparation-gates-')
        cls.root=Path(cls.temp.name)
        cls.h=prep.load('_fullgame_preparation_test_helpers',prep.ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
        historical=json.loads((I/'screen-assessment-historical-engineering-original01/historical-manifest.json').read_bytes())
        historical['engineering_only']=False
        manifest=cls.h.put(cls.root/'ENGINEERING-replay-of-failed-originals.json',historical)
        cls.failed=assessor.assess(Path(manifest['path']),manifest['sha256'],cls.root/'ENGINEERING-rejected-assessment.json')
        cls.epoch=json.loads((prep.ROOT/'logs/managed-learning-20261015/state.json').read_bytes())['optimization_goal']['next_fixed_reference_epoch']

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def write(self,name,value):
        return self.h.put(self.root/(name+'.json'),value)

    def test_actual_failed_scores_replayed_without_any_payload_or_gate_changes(self):
        actual=prep.read(self.failed,self.h)
        previous=prep.read(self.h.pin(I/'screen-assessment-historical-engineering-original01/historical-verdict.json'),self.h)
        self.assertEqual(actual['numerical_gates'],previous['numerical_gates'])
        self.assertFalse(actual['screening_passed'])
        self.assertFalse(actual['promotion'])

    def test_failed_original_is_ineligible_before_any_study_is_created(self):
        output=self.root/'must-not-be-created'
        with self.assertRaisesRegex(ValueError,'actual independently qualified passing'):
            prep.prepare(self.failed,self.epoch,None,None,output)
        self.assertFalse(output.exists())

    def test_relabeling_failed_original_as_passed_cannot_rescue_it(self):
        forged=prep.read(self.failed,self.h)
        forged.update(screening_passed=True,policy_decision='REQUIRE_FRESH_COMPLETE_GAME_CONFIRMATION')
        forged=self.write('ENGINEERING-forged-pass-header',forged)
        with self.assertRaisesRegex(ValueError,'Original scopes/scores/independent gates differ'):
            prep.eligible_screen(forged,self.epoch,self.h)

    def test_current_unlaunched_study_has_no_original_R1_qualification(self):
        path=I/'selected-candidate-scaled-observer-study-original01/study/prepared-four-legs-NOT-LAUNCH-QUALIFIED.json'
        output=self.root/'current-no-assessment.json'
        with self.assertRaises(FileNotFoundError):
            assessor.assess(path,hashlib.sha256(path.read_bytes()).hexdigest(),output)
        self.assertFalse(output.exists())

    def test_engineering_historical_replay_cannot_authorize_fullgame(self):
        pin=self.h.pin(I/'screen-assessment-historical-engineering-original01/historical-verdict.json')
        with self.assertRaisesRegex(ValueError,'actual independently qualified passing'):
            prep.eligible_screen(pin,self.epoch,self.h)

    def test_forged_source_status_or_quality_claim_is_rejected(self):
        for fault in ('source','status','historical','quality','promotion'):
            value=prep.read(self.failed,self.h)
            value.update(screening_passed=True,policy_decision='REQUIRE_FRESH_COMPLETE_GAME_CONFIRMATION')
            if fault=='source':value['source']['sha256']='f'*64
            elif fault=='status':value['status']='FAILED'
            elif fault=='historical':value['historical_replay_only']=True
            elif fault=='quality':value['full_game_quality_qualified']=True
            else:value['promotion']=True
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'actual independently qualified passing'):
                prep.eligible_screen(self.write('ENGINEERING-fault-'+fault,value),self.epoch,self.h)

    def test_original_failure_is_rechecked_even_when_header_claims_pass(self):
        value=prep.read(self.failed,self.h)
        value.update(screening_passed=True,policy_decision='REQUIRE_FRESH_COMPLETE_GAME_CONFIRMATION')
        pin=self.write('ENGINEERING-recheck-source',value)
        actual_load=prep.load
        class MissingOriginal:
            @staticmethod
            def assess(*args,**kwargs):raise FileNotFoundError('Original receipt is missing')
        def injected(name,path):
            return MissingOriginal if name=='_fullgame_actual_screen_assessor'else actual_load(name,path)
        with patch.object(prep,'load',side_effect=injected),self.assertRaises(FileNotFoundError):
            prep.eligible_screen(pin,self.epoch,self.h)


if __name__=='__main__':unittest.main()
