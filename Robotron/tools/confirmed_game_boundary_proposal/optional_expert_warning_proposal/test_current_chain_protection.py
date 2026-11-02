"""Current-chain protection guards; fixtures do not qualify actual policies."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import protect_confirmed_winner_reviewed3 as protect

HERE=Path(protect.__file__).parent
PREP=HERE.parents[1]/'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018'
SUPPLEMENT=PREP/'R1-optional-expert-warning-supplemental-review-original01-20261019'


class CurrentChainTests(unittest.TestCase):
    def setUp(self):
        self.supplement=json.loads((SUPPLEMENT/'supplemental-review-output/review.json').read_bytes())
        self.failed=json.loads((PREP/'audit-bindings/leg01-audit/review-receipt.json').read_bytes())
        # The authoritative root comes from the already bound campaign path.
        self.receipt_path=Path(self.failed['campaign_directory'])/'01-reference/receipt.json'
        self.receipt=json.loads(self.receipt_path.read_bytes())
        self.leg=dict(index=1,role='reference',summary=self.supplement['statistics'],
            included_game_ids=[row['journal_game_id'] for row in self.receipt['rows']],
            receipt_sha256=protect.digest(self.receipt_path))
        self.plan=self.supplement['plan_sha256'];self.failed_sha=protect.digest(PREP/'audit-bindings/leg01-audit/review-receipt.json')

    def validate(self):
        protect.validate_reference_join(self.supplement,self.failed,self.leg,self.plan,self.failed_sha)

    def test_actual_reference_review_joins_without_rewriting_its_failure(self):
        before=copy.deepcopy((self.supplement,self.failed,self.leg));self.validate()
        self.assertEqual((self.supplement,self.failed,self.leg),before)
        self.assertFalse(self.failed['valid']);self.assertEqual(self.supplement['original_audit_exit'],2)

    def test_only_reference1_with_same202_originals_and_warning_is_allowed(self):
        original=copy.deepcopy((self.supplement,self.failed,self.leg))
        for change in ('candidate','index','count','warning','failed_valid','other_error','receipt_set','proof_prefix'):
            self.supplement,self.failed,self.leg=copy.deepcopy(original)
            if change=='candidate':self.leg['role']='candidate'
            elif change=='index':self.leg['index']=2
            elif change=='count':self.leg['summary']['count']=201
            elif change=='warning':self.supplement['classified_warning']['text']='another warning'
            elif change=='failed_valid':self.failed['valid']=True
            elif change=='other_error':self.failed['error']='ValueError: actor timeout'
            elif change=='receipt_set':self.leg['included_game_ids'][0]='foreign'
            else:self.failed['rom_game_over_evidence']['links'].pop()
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate()

    def test_reruns_gate_changes_or_pretending_original_audit_succeeded_fail(self):
        original=copy.deepcopy(self.supplement)
        for key,value in [('cohort_rerun',True),('original_auditor_rerun',True),
                          ('original_receipts_changed',True),('scientific_gates_changed',True),
                          ('original_audit_exit',0),('original_evaluator_exit',False),
                          ('original_failed_review_sha256','0'*64)]:
            self.supplement=copy.deepcopy(original);self.supplement[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()

    def test_missing_or_duplicate_terminal_ROM_coverage_fails(self):
        original=copy.deepcopy(self.supplement)
        for name in ('original_terminal_readback','rom_game_over_evidence'):
            for change in ('missing','duplicate','failed','wrong_count'):
                self.supplement=copy.deepcopy(original);proof=self.supplement[name]
                if change=='missing':proof['links'].pop()
                elif change=='duplicate':proof['links'][0]=copy.deepcopy(proof['links'][1])
                elif change=='failed':proof['status']='FAIL'
                else:proof['verified_games']=201
                with self.subTest(name=name,change=change),self.assertRaises(ValueError):self.validate()

    def test_actual_preserved_failure_archives_are_verified_with_their_real_codes(self):
        old=json.loads((PREP/'audit-observer-execution/native-terminal-archive/root-original-result-and-owned-release.json').read_bytes())
        audit=json.loads((PREP/'audit-bindings/leg01-controller/root-original-result-and-owned-release.json').read_bytes())
        for closure,code,retained in ((old,1,True),(audit,2,False)):
            evidence={};protect.failed_terminal_archive(closure,closure['original'],evidence,code,retained_tombstone=retained)
            self.assertEqual(len(evidence),1)
            for value in (0,False,None):
                changed=copy.deepcopy(closure);changed['original_exit']=value
                with self.subTest(code=code,value=value),self.assertRaises(ValueError):
                    protect.failed_terminal_archive(changed,closure['original'],{},code,retained_tombstone=retained)

    def test_failed_current_observer_cannot_use_historical_failure_exception(self):
        owner=dict(unit='current.service',timer='current.timer',pid=1,invocation_id='a'*32)
        closure=dict(original=owner,original_exit=1,lifecycle_complete=True,
            owned_release=[dict(unit=x,confirmed_absent=True) for x in ('current.service','current.timer')])
        with self.assertRaises(ValueError):protect.validate_closed_owner(closure,owner)

    def test_publication_algorithm_and_existing_gate_helpers_are_identical(self):
        source=Path(protect.__file__).read_text();parent=(HERE/'protect_confirmed_winner_reviewed2.py').read_text()
        expected=parent[parent.index('def _fsync_directory'):parent.index('def main():')]
        self.assertIn(expected,source)
        old={node.name:node for node in ast.parse(parent).body if isinstance(node,ast.FunctionDef)}
        new={node.name:node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef)}
        for name in ('pin','read_pin','checked_module','validate_closed_owner','validate_review_join','original_terminal_archive','publish'):
            self.assertEqual(ast.dump(old[name]),ast.dump(new[name]))


class ExactGateTests(unittest.TestCase):
    def receipts(self,c1=105,c2=105):
        return [dict(rows=[dict(score=score)]*50) for score in (100,c1,100,c2)]

    def test_both_candidates_individually_clear_exact5percent_and_median(self):
        result=protect.exact_candidate_gates(self.receipts())
        self.assertEqual([row['index'] for row in result],[2,4])
        self.assertTrue(all(row['mean_gate_integer_left']==row['mean_gate_integer_right'] for row in result))

    def test_winning_pooled_candidate_mean_cannot_rescue_either_failure(self):
        for c1,c2 in ((300,104),(104,300)):
            with self.subTest(c1=c1,c2=c2),self.assertRaises(ValueError):
                protect.exact_candidate_gates(self.receipts(c1,c2))

    def test_large_mean_cannot_rescue_lower_median(self):
        data=self.receipts();data[3]['rows']=[dict(score=0)]*26+[dict(score=10000)]*24
        with self.assertRaises(ValueError):protect.exact_candidate_gates(data)

    def test_incomplete_small_or_noninteger_games_do_not_qualify(self):
        for change in ('missing_leg','floor','bool','float','negative'):
            data=self.receipts()
            if change=='missing_leg':data.pop()
            elif change=='floor':data[1]['rows'].pop()
            else:data[1]['rows'][0]=dict(score={'bool':True,'float':105.0,'negative':-1}[change])
            with self.subTest(change=change),self.assertRaises(ValueError):protect.exact_candidate_gates(data)


if __name__=='__main__':unittest.main()
