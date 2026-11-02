"""No runtime queries: original-leg admission and no-retry boundaries."""
import copy
import unittest
from watch_confirmed_quality_audits import select_ready, validate_review


class OriginalLegTests(unittest.TestCase):
    def setUp(self):
        self.plan={'sha256':'a'*64}
        self.state=dict(plan_sha256='a'*64,legs=[dict(index=1,role='reference',state='finished',returncode=0)])

    def test_only_finished_original_once(self):
        self.assertEqual(select_ready(self.plan,self.state,[]),1)
        self.assertIsNone(select_ready(self.plan,self.state,[1]))
        self.state['legs'].append(dict(index=2,role='candidate',state='running'))
        self.assertEqual(select_ready(self.plan,self.state,[]),1)
        self.assertIsNone(select_ready(self.plan,self.state,[1]))

    def test_four_ordered_originals(self):
        self.state['legs']=[dict(index=i,role='reference' if i%2 else 'candidate',state='finished',returncode=0) for i in range(1,5)]
        for i in range(1,5):self.assertEqual(select_ready(self.plan,self.state,list(range(1,i))),i)
        self.assertIsNone(select_ready(self.plan,self.state,[1,2,3,4]))

    def test_nonzero_missing_or_boolean_exit_is_not_zero(self):
        for value in (None,1,False):
            with self.subTest(value=value):
                self.state['legs'][0]['returncode']=value
                with self.assertRaises(ValueError):select_ready(self.plan,self.state,[])

    def test_missing_reordered_duplicate_or_role_changed_fails(self):
        for change in ('missing','duplicate','role'):
            state=copy.deepcopy(self.state)
            if change=='missing':state['legs'][0]['index']=2
            elif change=='duplicate':state['legs'].append(copy.deepcopy(state['legs'][0]))
            else:state['legs'][0]['role']='candidate'
            with self.subTest(change=change),self.assertRaises(ValueError):select_ready(self.plan,state,[])

    def test_wrong_native_plan_fails(self):
        self.state['plan_sha256']='b'*64
        with self.assertRaises(ValueError):select_ready(self.plan,self.state,[])


class TerminalReviewTests(unittest.TestCase):
    def setUp(self):
        self.review=dict(valid=True, leg=1, plan_sha256='a'*64,
            schema='robotron-confirmed-original-terminal-leg-v1',
            statistics=dict(count=50), original_terminal_readback=dict(status='PASS',verified_games=50))

    def test_complete_original_terminal_proof_is_accepted_without_mutation(self):
        before=copy.deepcopy(self.review)
        validate_review(self.review,1,'a'*64)
        self.assertEqual(self.review,before)

    def test_legacy_or_missing_terminal_proof_cannot_be_adopted(self):
        for change in ('schema','missing','failed','partial','floor','boolean'):
            row=copy.deepcopy(self.review)
            if change=='schema':row['schema']='robotron-independent-original-journal-leg-v1'
            if change=='missing':row.pop('original_terminal_readback')
            if change=='failed':row['original_terminal_readback']['status']='FAIL'
            if change=='partial':row['original_terminal_readback']['verified_games']=49
            if change=='floor':row['statistics']['count']=row['original_terminal_readback']['verified_games']=49
            if change=='boolean':row['original_terminal_readback']['verified_games']=True
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_review(row,1,'a'*64)

    def test_wrong_original_leg_or_plan_fails(self):
        for leg,digest in ((2,'a'*64),(1,'b'*64)):
            with self.assertRaises(ValueError):validate_review(self.review,leg,digest)


if __name__=='__main__':unittest.main()



