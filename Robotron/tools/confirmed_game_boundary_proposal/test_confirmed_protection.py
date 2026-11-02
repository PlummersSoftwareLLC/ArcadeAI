"""Pure protection prerequisites; fixture verdicts never qualify real policies."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import protect_confirmed_winner as protect


class ProtectionPrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.owner=dict(unit='robotron-test.service',timer='robotron-test.timer',
                        pid=101,starttime_ticks=111,invocation_id='a'*32)
        self.closure=dict(original=copy.deepcopy(self.owner),original_exit=0,lifecycle_complete=True,
            owned_release=[dict(unit=name,confirmed_absent=True) for name in
                           ('robotron-test.service','robotron-test.timer')])
        self.ids=['game-'+str(i) for i in range(50)]
        self.leg=dict(index=2,role='candidate',receipt_sha256='b'*64,
                      summary=dict(count=50),included_game_ids=list(self.ids))
        links=[dict(journal_game_id=x) for x in self.ids]
        self.review=dict(schema='robotron-confirmed-original-terminal-leg-v1',valid=True,
            leg=2,role='candidate',plan_sha256='c'*64,receipt_sha256='b'*64,
            statistics=dict(count=50),original_game_ids=list(self.ids),admission_ids=list(self.ids),
            original_terminal_readback=dict(status='PASS',verified_games=50,links=copy.deepcopy(links)),
            rom_game_over_evidence=dict(status='PASS',verified_games=50,links=copy.deepcopy(links)))

    def test_clean_original_closure_and_complete_audit_join_are_read_only(self):
        before=copy.deepcopy((self.closure,self.owner,self.review,self.leg))
        protect.validate_closed_owner(self.closure,self.owner)
        protect.validate_review_join(self.review,self.leg,'c'*64)
        self.assertEqual((self.closure,self.owner,self.review,self.leg),before)

    def test_nonzero_boolean_or_wrong_original_owner_blocks(self):
        for value in (1,False,None):
            record=copy.deepcopy(self.closure);record['original_exit']=value
            with self.assertRaises(ValueError):protect.validate_closed_owner(record,self.owner)
        record=copy.deepcopy(self.closure);record['original']['pid']+=1
        with self.assertRaises(ValueError):protect.validate_closed_owner(record,self.owner)

    def test_unreleased_replaced_or_incomplete_owned_units_block(self):
        for change in ('missing','foreign','not_absent','incomplete'):
            record=copy.deepcopy(self.closure)
            if change=='missing':record['owned_release'].pop()
            if change=='foreign':record['owned_release'][0]['unit']='another.service'
            if change=='not_absent':record['owned_release'][0]['confirmed_absent']=False
            if change=='incomplete':record['lifecycle_complete']=False
            with self.subTest(change=change),self.assertRaises(ValueError):
                protect.validate_closed_owner(record,self.owner)

    def test_legacy_validity_or_missing_ROM_proof_never_qualifies(self):
        for change in ('legacy','invalid','missing_rom','partial_rom','failed_terminal'):
            record=copy.deepcopy(self.review)
            if change=='legacy':record['schema']='robotron-independent-original-journal-leg-v1'
            if change=='invalid':record['valid']=False
            if change=='missing_rom':record.pop('rom_game_over_evidence')
            if change=='partial_rom':record['rom_game_over_evidence']['verified_games']=49
            if change=='failed_terminal':record['original_terminal_readback']['status']='FAIL'
            with self.subTest(change=change),self.assertRaises(ValueError):
                protect.validate_review_join(record,self.leg,'c'*64)

    def test_wrong_native_plan_role_receipt_or_game_set_blocks(self):
        for key,value in [('plan_sha256','0'*64),('leg',4),('role','reference'),
                          ('receipt_sha256','0'*64),('admission_ids',self.ids[:-1])]:
            record=copy.deepcopy(self.review);record[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                protect.validate_review_join(record,self.leg,'c'*64)

    def test_duplicate_and_omitted_originals_or_proof_links_block(self):
        for change in ('duplicate_ids','duplicate_links','omitted_links','wrong_id'):
            record=copy.deepcopy(self.review)
            if change=='duplicate_ids':record['original_game_ids'].append(self.ids[0])
            if change=='duplicate_links':record['rom_game_over_evidence']['links'].append(dict(journal_game_id=self.ids[0]))
            if change=='omitted_links':record['original_terminal_readback']['links'].pop()
            if change=='wrong_id':record['rom_game_over_evidence']['links'][0]['journal_game_id']='foreign'
            with self.subTest(change=change),self.assertRaises(ValueError):
                protect.validate_review_join(record,self.leg,'c'*64)

    def test_established_count_floor_cannot_be_lowered(self):
        leg=copy.deepcopy(self.leg);leg['summary']['count']=49
        with self.assertRaises(ValueError):protect.validate_review_join(self.review,leg,'c'*64)

    def test_publication_algorithm_is_exact_existing_reviewed_body(self):
        original=(HERE/'quality_integration_reviewed4/Robotron/tools/protect_quality_winner.py').read_text()
        body=original[original.index('def _fsync_directory'):original.index('def main(')]
        self.assertIn(body,(HERE/'protect_confirmed_winner.py').read_text())


if __name__=='__main__':unittest.main()
