"""The polling failure cannot erase an audit failure or change a score gate."""
import ast
import copy
import json
from pathlib import Path
import unittest

import protect_confirmed_winner_reviewed4 as protect
from test_observer_read_recovery import real_job,PREP


class PollingProtectionTests(unittest.TestCase):
    def setUp(self):
        current=json.loads((PREP/'audit-bindings-reviewed4/watcher-job.json').read_bytes())
        prior=current['failed_polling_predecessor']
        failure=json.loads(Path(prior['result']['path']).read_bytes())
        old=json.loads(Path(prior['job']['path']).read_bytes())
        handoff=json.loads((Path(current['output'])/'original-polling-failure-handoff.json').read_bytes())
        # This fixture exercises only the handoff flags, never a qualification.
        result=dict(failed_polling_predecessor=prior,remaining_original_audits_resumed_without_retry=True)
        self.args=[prior,failure,old,current,handoff,result]

    def test_actual_unchanged_handoff_is_accepted_without_rewriting_failure(self):
        before=copy.deepcopy(self.args);protect.validate_polling_handoff(*self.args)
        self.assertEqual(before,self.args)
        self.assertEqual(self.args[1]['error'],"ValueError('File changed while reading')")

    def test_any_remaining_attempt_other_failure_or_training_change_fails(self):
        for key,value in (('attempted',[1,2]),('status','PASS'),('error','audit failure'),
                          ('training_touched',True),('quality_owner_touched',True),('promotion',True),('audits',[])):
            args=copy.deepcopy(self.args);args[1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):protect.validate_polling_handoff(*args)

    def test_original_cohort_reference_or_audit_bindings_cannot_change(self):
        for key in ('owner','plan','configs','reference_supplement','reference_supplement_closure'):
            args=copy.deepcopy(self.args);args[3][key]['different']=True
            with self.subTest(key=key),self.assertRaises(ValueError):protect.validate_polling_handoff(*args)

    def test_handoff_cannot_erase_failed_outcome_or_allow_retries(self):
        for key,value in (('remaining_original_audit_attempts',[2]),('original_failed_outcome_preserved',False),
                          ('cohort_rerun',True),('auditor_rerun',True),('scientific_gates_changed',True),('promotion',True)):
            args=copy.deepcopy(self.args);args[4][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):protect.validate_polling_handoff(*args)

    def test_final_observer_must_preserve_exact_predecessor_and_no_retry(self):
        for key,value in (('failed_polling_predecessor',{}),('remaining_original_audits_resumed_without_retry',False)):
            args=copy.deepcopy(self.args);args[5][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):protect.validate_polling_handoff(*args)

    def test_actual_failed_poller_archive_remains_exit1(self):
        archive=json.loads(Path(self.args[0]['archive']['path']).read_bytes())
        evidence={};protect.failed_terminal_archive(archive,self.args[0]['owner'],evidence,1,retained_tombstone=True)
        self.assertEqual(len(evidence),1)
        with self.assertRaises(ValueError):protect.original_terminal_archive(archive,self.args[0]['owner'],{})

    def test_score_terminal_ROM_and_publication_helpers_are_unchanged(self):
        def functions(path):
            return {node.name:ast.dump(node) for node in ast.parse(path.read_bytes()).body if isinstance(node,ast.FunctionDef)}
        old=functions(Path(protect.__file__).with_name('protect_confirmed_winner_reviewed3.py'))
        new=functions(Path(protect.__file__))
        for name in ('exact_candidate_gates','validate_reference_join','validate_review_join',
                     'original_terminal_archive','failed_terminal_archive','verify_audit_artifacts',
                     'validate_closed_owner','publish','_fsync_directory'):
            with self.subTest(name=name):self.assertEqual(old[name],new[name])


if __name__=='__main__':unittest.main()
