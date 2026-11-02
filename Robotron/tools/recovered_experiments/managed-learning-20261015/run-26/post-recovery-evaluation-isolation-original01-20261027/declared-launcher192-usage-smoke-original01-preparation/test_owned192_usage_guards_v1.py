"""NEW three pure/temp-file guard cases. No fork, MAME, API, proc or unit action."""
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().with_name('run_owned192_usage_smoke_v1.py')
r=types.ModuleType('_usage_guard_tests');r.__file__=str(SOURCE)
exec(compile(SOURCE.read_bytes(),str(SOURCE),'exec'),r.__dict__)


class Tests(unittest.TestCase):
    def test_raw_sweeps_have_small_indexes_and_reject_oversize_before_write(self):
        with tempfile.TemporaryDirectory()as d:
            root=Path(d)
            value=r.commit_sweep(root,0,0,[dict(slot='0',stage='mame',within_original5s_birth_age=False)],dict(mame=1))
            self.assertNotIn('records',value);self.assertEqual(value['actual_stable_MAME_slots'],['0'])
            self.assertEqual(json.loads(Path(value['raw']['path']).read_text())['records'][0]['slot'],'0')
            self.assertEqual(value['outside5s_birth_age'],1)
            with self.assertRaisesRegex(ValueError,'before write'):r.put(root/'oversize.json',dict(data='a'*(8<<20)))
            self.assertFalse((root/'oversize.json').exists())

    def test_cleanup_requires_exact_original_birth_and_reaps_truthful_signal_exit(self):
        class Child:
            pid=123;code=None;called=False
            def poll(self):return self.code
            def terminate(self):self.called=True;self.code=-15
            def kill(self):self.called=True;self.code=-9
        child=Child()
        with patch.object(r,'birth',return_value=456):result=r.cleanup({'0':child},{'0':456})
        self.assertEqual(child.poll(),-15);self.assertEqual(result,[dict(slot='0',pid=123,birth=456,action='terminate')])
        other=Child()
        with patch.object(r,'birth',return_value=999),self.assertRaisesRegex(ValueError,'unowned/reused'):r.cleanup({'0':other},{'0':456})
        self.assertFalse(other.called)

    def test_rotated_CIDs_allowed_but_role_duplicate_and_epoch_changes_rejected(self):
        lineage={k:dict(process_id=1,instance_monotonic_ns=2,epoch=1,epoch_reason='same')for k in ('optimizer','replay')}
        case=dict(slot_eval={'0':False,'1':True},exposure=lineage)
        before=dict(client_count=2,client_rows=[dict(client_slot=0,client_id=1,eval=False),dict(client_slot=1,client_id=2,eval=True)],host_pipeline=dict(learning_exposure=copy.deepcopy(lineage)))
        after=copy.deepcopy(before)
        for row in after['client_rows']:row['client_id']+=100
        self.assertEqual(r.main_API_projection(case,before,after)['after'][0]['client_id'],101)
        for fault in ('role','duplicate','epoch','boolslot'):
            value=copy.deepcopy(after)
            if fault=='role':value['client_rows'][0]['eval']=True
            if fault=='duplicate':value['client_rows'][0]['client_id']=value['client_rows'][1]['client_id']
            if fault=='epoch':value['host_pipeline']['learning_exposure']['optimizer']['epoch']=2
            if fault=='boolslot':value['client_rows'][0]['client_slot']=False
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):r.main_API_projection(case,before,value)


if __name__=='__main__':unittest.main(verbosity=2)
