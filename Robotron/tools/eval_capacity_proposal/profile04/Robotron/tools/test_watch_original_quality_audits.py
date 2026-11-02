"""No runtime queries: original-leg admission and no-retry boundaries."""
import copy
import unittest
from watch_original_quality_audits import select_ready


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


if __name__=='__main__':unittest.main()
