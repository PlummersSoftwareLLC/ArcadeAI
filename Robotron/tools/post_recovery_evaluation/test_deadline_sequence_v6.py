"""One original failure or operator stop must prevent every later launch."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import sequence_deadline_study_v6 as s


class DeadlineSequenceTests(unittest.TestCase):
    def exercise(self,fail=None,stop=None,cases=None):
        cases=cases or [dict(leg=leg)for leg in s.ORDER];seen=[]
        def action(kind,case=None):
            leg=case['leg']if case else'final';seen.append((kind,leg))
            if (kind,leg)==fail:raise ValueError('Original failed')
            return dict(kind=kind,original=True)
        def before(kind,case):
            leg=case['leg']if case else'final'
            if (kind,leg)==stop:raise s.StopNewActions('Operator stop')
        try:
            result=s.walk(cases,lambda case:action('wait_original_R1',case),
                lambda case:action('native',case),lambda case,native:action('review',case),
                lambda records:action('assessment'),before)
        except (ValueError,s.StopNewActions):result=None
        return seen,result

    def expected(self):
        return [('wait_original_R1','R1'),('review','R1')]+[(kind,leg)for leg in s.ORDER[1:]for kind in ('native','review')]+[('assessment','final')]

    def test_R1_is_only_observed_and_each_next_native_follows_independent_review(self):
        seen,result=self.exercise();self.assertEqual(seen,self.expected())
        self.assertNotIn(('native','R1'),seen);self.assertEqual(len(seen),len(set(seen)))
        self.assertEqual([row['leg']for row in result[0]],s.ORDER)

    def test_each_original_failure_prevents_later_launches_and_retry(self):
        for index,event in enumerate(self.expected()):
            seen,result=self.exercise(fail=event)
            self.assertEqual(seen,self.expected()[:index+1]);self.assertIsNone(result)

    def test_operator_stop_at_any_boundary_launches_nothing_later(self):
        for index,event in enumerate(self.expected()):
            seen,result=self.exercise(stop=event)
            self.assertEqual(seen,self.expected()[:index]);self.assertIsNone(result)

    def test_reordered_missing_or_duplicate_legs_fail_before_waiting(self):
        for roles in (['C1','R1','R2','C2'],['R1','C1','R2'],['R1','C1','R2','R2']):
            seen,result=self.exercise(cases=[dict(leg=leg)for leg in roles])
            self.assertEqual(seen,[]);self.assertIsNone(result)




    def test_already_qualified_R1_cannot_reenter_any_native_or_review_launcher(self):
        instance=s.Sequence.__new__(s.Sequence);qualified=dict(path='/ENGINEERING-existing-qualification')
        instance.review_precommit=Path('/ENGINEERING-precommit');instance.job=dict(R1_prequalified=qualified)
        instance.p=SimpleNamespace(prepare_leg=lambda *args:(_ for _ in ()).throw(AssertionError('No new R1 review preparation')))
        instance.helper=SimpleNamespace(invoke_controller_once=lambda *args:(_ for _ in ()).throw(AssertionError('No new R1 native/review launch')))
        events=[];instance.project=lambda *args,**kwargs:events.append(args)
        with patch.object(s,'verify_existing_R1',return_value=qualified):
            self.assertEqual(instance.review(dict(leg='R1'),dict(existing=True)),qualified)
        self.assertEqual(events,[('ORIGINAL_R1_INDEPENDENTLY_QUALIFIED',dict(leg='R1'))])

    def test_default_invocation_cannot_start_or_prepare_any_scope(self):
        result=subprocess.run(['/usr/bin/python3','-I','-B',str(Path(s.__file__))],capture_output=True,text=True,timeout=10,check=True)
        self.assertEqual(result.stdout.strip(),'PLAN_ONLY_NO_READS_OR_ACTIONS')

    def test_failure_while_original_scope_lives_preserves_registration_and_payload(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);state=root/'state.json'
            scope=dict(pid=os.getpid(),starttime_ticks=12345,unit='ENGINEERING-never-controlled')
            raw=json.dumps(dict(active_quality_job=dict(actual_original_scope=scope))).encode();state.write_bytes(raw)
            writes=[];events=[]
            instance=s.Sequence.__new__(s.Sequence)
            instance.pin=dict(engineering=True);instance.job={};instance.packet=dict(cases=[dict(leg='R1')]);instance.output=root
            instance.h=SimpleNamespace(put=lambda path,value:(writes.append((path,value))or dict(path=str(path))))
            instance.helper=SimpleNamespace(birth=lambda pid:12345)
            instance.check=lambda *args:(_ for _ in ()).throw(s.StopNewActions('No new actions'))
            instance.event=lambda label,value:events.append((label,value))
            instance.project=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('Do not project closed over live original'))
            with patch.object(s,'STATE',state):self.assertEqual(instance.run(),1)
            self.assertEqual(state.read_bytes(),raw)
            self.assertEqual(writes[0][1]['original_scope_still_running_preserved'],scope)
            self.assertEqual(events[-1][0],'sequence-stopped-original-scope-preserved')

    def test_failure_projection_error_still_preserves_original_outcome(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);state=root/'state.json';state.write_text('{"active_quality_job":{}}')
            writes=[];instance=s.Sequence.__new__(s.Sequence);instance.pin={};instance.job={}
            instance.packet=dict(cases=[dict(leg='R1')]);instance.output=root
            instance.h=SimpleNamespace(put=lambda path,value:(writes.append(value)or dict(path=str(path))))
            instance.helper=SimpleNamespace(birth=lambda pid:None)
            instance.check=lambda *args:(_ for _ in ()).throw(ValueError('Original failed'))
            instance.project=lambda *args,**kwargs:(_ for _ in ()).throw(ValueError('Canonical owner changed'))
            with patch.object(s,'STATE',state):self.assertEqual(instance.run(),1)
            self.assertIn('canonical_projection_error',writes[0]);self.assertIn('Original failed',writes[0]['error'])



    def test_old_failed_study_precommit_cannot_be_reused_by_new_source_family(self):
        p=s.preparation();isolation=p.BASE/'post-recovery-evaluation-isolation-original01-20261027'
        old=isolation/'distinct684b-deadline-independent-review-precommit-original01/precommitted-four-reviews.json'
        owner=isolation/'distinct684b-family8-original-launch-original01/actual-original-R1-live-owner.json'
        with tempfile.TemporaryDirectory()as temporary:
            output=Path(temporary)/'never-created'
            with self.assertRaisesRegex(ValueError,'Preparation source changed'):
                s.prepare(old,owner,output)
            with self.assertRaisesRegex(ValueError,'Preparation source changed'):
                s.verify_existing_R1(old)
            self.assertFalse(output.exists())

    def test_review_preparer_derivation_changes_only_selected_reviewer_filename(self):
        import ast
        p=s.preparation();here=Path(p.__file__).parent
        old=(here/'prepare_deadline_independent_review_v3.py').read_text()
        expected=old.replace('review_deadline32_rounds_v10.py','review_deadline32_rounds_v11.py')
        self.assertEqual(ast.dump(ast.parse(expected)),ast.dump(ast.parse(Path(p.__file__).read_text())))

    def test_continuation_derivation_preserves_all_original_owned_lifecycle_predicates(self):
        import ast
        here=Path(s.__file__).parent
        expected=(here/'sequence_deadline_study_v5.py').read_text().replace(
            'prepare_deadline_independent_review_v3.py','prepare_deadline_independent_review_v4.py').replace(
            'Original684b fixed-cutoff comparison: ','Original prospective fixed-cutoff comparison: ')
        self.assertEqual(ast.dump(ast.parse(expected)),ast.dump(ast.parse(Path(s.__file__).read_text())))

if __name__=='__main__':unittest.main()
