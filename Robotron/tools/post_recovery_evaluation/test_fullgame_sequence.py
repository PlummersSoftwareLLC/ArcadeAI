"""Sequencing failures must stop later originals; engineering never launches."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import sequence_fullgame_study as s


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.cases=[dict(leg=role)for role in ('R1','C1','R2','C2')]

    def exercise(self,fail=None,stop=None):
        seen=[]
        def before(kind,case):
            role=case['leg']if case else'final'
            if (kind,role)==stop:raise s.StopNewActions('Operator stop; no next original')
        def native(case):
            key=('native',case['leg']);seen.append(key)
            if key==fail:raise ValueError('Original native/controller failed')
            return dict(original=True)
        def review(case,native):
            key=('review',case['leg']);seen.append(key)
            self.assertTrue(native['original'])
            if key==fail:raise ValueError('Original review/closure failed')
            return dict(valid=True)
        def assess(records):
            seen.append(('assessment','final'));self.assertEqual(len(records),4)
            if ('assessment','final')==fail:raise ValueError('Original final assessment failed')
            return dict(promotion=False)
        try:result=s.walk_original_phases(self.cases,native,review,assess,before)
        except (ValueError,s.StopNewActions):result=None
        return seen,result

    def test_all_original_native_review_pairs_precede_final_assessment_once(self):
        seen,result=self.exercise()
        self.assertEqual(seen,[(kind,role)for role in ('R1','C1','R2','C2')for kind in ('native','review')]+[('assessment','final')])
        self.assertEqual(len(seen),len(set(seen)))
        self.assertFalse(result[1]['promotion'])

    def test_failure_of_any_original_prevents_all_later_scheduling_and_retry(self):
        expected=[(kind,role)for role in ('R1','C1','R2','C2')for kind in ('native','review')]+[('assessment','final')]
        for index,phase in enumerate(expected):
            with self.subTest(phase=phase):
                seen,result=self.exercise(fail=phase)
                self.assertEqual(seen,expected[:index+1]);self.assertIsNone(result)

    def test_stop_between_phases_does_not_restart_or_schedule_next_original(self):
        expected=[(kind,role)for role in ('R1','C1','R2','C2')for kind in ('native','review')]+[('assessment','final')]
        for index,phase in enumerate(expected):
            with self.subTest(phase=phase):
                seen,result=self.exercise(stop=phase)
                self.assertEqual(seen,expected[:index]);self.assertIsNone(result)

    def test_changed_order_rejected_before_any_action(self):
        self.cases[0],self.cases[1]=self.cases[1],self.cases[0]
        seen,result=self.exercise();self.assertEqual(seen,[]);self.assertIsNone(result)

    def test_engineering_reviews_cannot_prepare_scientific_sequence(self):
        p=s.pipeline();I=p.BASE/'post-recovery-evaluation-isolation-original01-20261027'
        commit=I/'fullgame-four-independent-reviews-engineering-original02/precommitted-four-reviews.json'
        with tempfile.TemporaryDirectory()as directory:
            output=Path(directory)/'must-not-exist'
            with self.assertRaisesRegex(ValueError,'Engineering review precommit cannot prepare'):
                s.prepare(commit,None,output)
            self.assertFalse(output.exists())

    def test_engineering_sequence_cannot_reach_controller_or_state_constructor(self):
        p=s.pipeline();h=p.helpers()
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'ENGINEERING-sequence.json'
            pin=h.put(path,dict(schema='robotron-recovered-fullgame-sequence-precommit-v1',engineering_only=True))
            with (patch.object(s,'original_helper',side_effect=AssertionError('Controller helper must not be reached')),
                self.assertRaisesRegex(ValueError,'Production original sequence/source')):
                s.Sequence(path,pin['sha256'])


if __name__=='__main__':unittest.main()
