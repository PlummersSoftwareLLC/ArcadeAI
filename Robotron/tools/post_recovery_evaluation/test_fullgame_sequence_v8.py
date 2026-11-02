"""Sequencing failures must stop later originals; engineering never launches."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json

from . import sequence_fullgame_study_v8 as s


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
        commit=I/'fullgame-single-journal-admission-four-reviews-engineering-original01/precommitted-four-reviews.json'
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

    def test_registration_failure_or_canonical_change_still_preserves_outcome_without_dispatch(self):
        p=s.pipeline();h=p.helpers();I=p.BASE/'post-recovery-evaluation-isolation-original01-20261027'
        commit=p.read(h.pin(I/'fullgame-single-journal-admission-four-reviews-engineering-original01/precommitted-four-reviews.json'))
        prepared=p.read(commit['native_prepared']);cases=[]
        for case,review in zip(prepared['cases'],commit['cases']):
            cases.append(dict(**case,qualified_native_config=case['unqualified_controller_config'],review=review))
        for during_initial in (True,False):
            with self.subTest(during_initial=during_initial),tempfile.TemporaryDirectory()as directory:
                # Test only failure-record preservation. The production constructor
                # refuses this engineering domain; no preflight/scientific dispatch
                # is allowed from this intentionally isolated method fixture.
                instance=s.Sequence.__new__(s.Sequence);instance.p=p;instance.h=h;instance.helper=s.original_helper(p,h)
                instance.root=Path(directory);instance.events=instance.root/'events';instance.number=0;instance.closed=False
                instance.job=dict(inputs=[],cases=cases);instance.pin=h.pin(I/'fullgame-single-journal-admission-four-reviews-engineering-original01/precommitted-four-reviews.json')
                def projection(*args,**kwargs):
                    if during_initial or not kwargs.get('initial'):raise ValueError('Canonical active sequence changed')
                with (patch.object(instance,'preflight',return_value=dict(engineering_only=True)),
                      patch.object(instance,'project',side_effect=projection),
                      patch.object(s,'walk_original_phases',side_effect=AssertionError('No dispatch permitted')if during_initial else s.StopNewActions('Canonical owner changed'))as walk):
                    self.assertEqual(instance.run(),1)
                    self.assertEqual(walk.call_count,0 if during_initial else 1)
                outcome=json.loads((instance.root/'original-sequence-outcome.json').read_bytes())
                self.assertIn('canonical_projection_error',outcome)
                self.assertEqual(outcome['status'],'ORIGINAL_FAILURE_PRESERVED_NO_RETRY'if during_initial else'STOPPED_NO_NEW_ACTIONS')


if __name__=='__main__':unittest.main()
