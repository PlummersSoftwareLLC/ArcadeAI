"""Actual archived reconnect counterexample and adversarial ownership checks."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import unittest

from . import api_reconnect_projection_v1 as projection
from . import round_health_transport_v4 as old
from . import round_health_transport_v5 as new

ROOT=Path(__file__).resolve().parents[2]
ISOLATION=ROOT/'logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027'
LEG=ISOLATION/'distinct684b-buffered-family8-study-original01/C1'
RAW=LEG/'deadline-output-original01/main-observations'


class ReconnectProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        job=json.loads((LEG/'job.json').read_bytes())
        cls.case=json.loads(Path(job['main_binding']['path']).read_bytes())
        cls.before=json.loads((RAW/'sample-001870.json').read_bytes())['snapshot']
        cls.previous=json.loads((RAW/'sample-001871.json').read_bytes())['snapshot']
        cls.sample=json.loads((RAW/'unaccepted-000019.json').read_bytes())['raw_snapshot']

    def test_actual_original_rejection_and_physical_TCP_pass_are_reproduced(self):
        old.validate_transport(self.sample)
        with self.assertRaisesRegex(ValueError,'Unknown, duplicate or missing API client'):
            old.validate(self.case,self.sample,previous=self.previous)

    def test_actual_archived_reconnect_is_certified_without_rewriting_raw_data(self):
        sample=copy.deepcopy(self.sample);before=json.dumps(sample,sort_keys=True)
        new.validate(self.case,sample,previous=self.previous)
        self.assertEqual(json.dumps(sample,sort_keys=True),before)
        proof=projection.verify(self.case,sample,self.previous)
        self.assertEqual(len(proof),1);self.assertEqual(proof[0]['slot'],'71')
        self.assertEqual((proof[0]['old_client_id'],proof[0]['new_client_id']),(75,7))
        self.assertLess(proof[0]['new_registration_effective_age_s'],.5)
        self.assertTrue(proof[0]['unchanged_physical_TCP_ownership_verified'])
        self.assertFalse(proof[0]['raw_API_rewritten'])

    def test_ordinary_actual_unique_slot_sample_retains_original_behavior(self):
        old.validate(self.case,self.previous,previous=self.before)
        new.validate(self.case,self.previous,previous=self.before)

    def test_changed_registration_age_ID_role_and_predecessor_are_rejected(self):
        faults=('unknown_slot','duplicate_ID','third_row','API_count','old_ID','new_ID_owner',
                'new_age','API_age','MAME_birth','role','no_predecessor','gap','round')
        for fault in faults:
            sample=copy.deepcopy(self.sample);previous=copy.deepcopy(self.previous)
            older=next(row for row in sample['api']['client_rows']if row['client_id']==75)
            newer=next(row for row in sample['api']['client_rows']if row['client_id']==7)
            if fault=='unknown_slot':newer['client_slot']=999
            elif fault=='duplicate_ID':newer['client_id']=75
            elif fault=='third_row':
                row=dict(newer,client_id=9999);sample['api']['client_rows'].append(row);sample['api']['client_count']+=1
            elif fault=='API_count':sample['api']['client_count']+=1
            elif fault=='old_ID':older['client_id']=9999
            elif fault=='new_ID_owner':previous['api']['client_rows'].append(dict(newer,client_slot=1))
            elif fault=='new_age':newer['connected_seconds']=.6
            elif fault=='API_age':sample['api']['ts']=sample['unix_s']-.6
            elif fault=='MAME_birth':sample['actors']['71']['starttime_ticks']+=1
            elif fault=='role':newer['eval']=True
            elif fault=='no_predecessor':previous=None
            elif fault=='gap':sample['monotonic_s']=previous['monotonic_s']+.501
            else:sample['status']['round']+=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):projection.verify(self.case,sample,previous)

    def test_foreign_physical_TCP_client_and_missing_retirement_remain_invalid(self):
        sample=copy.deepcopy(self.sample);lines=sample['transport']['raw_tables']['tcp'].splitlines()
        row=next(line.split()for line in lines[1:]if line.split()[3]=='01'and int(line.split()[1].split(':')[1],16)==9998)
        row[9]='999999999999';sample['transport']['raw_tables']['tcp']=sample['transport']['raw_tables']['tcp'].rstrip('\n')+'\n'+' '.join(row)+'\n'
        with self.assertRaisesRegex(ValueError,'not owned'):new.validate(self.case,sample,previous=self.previous)
        sample=copy.deepcopy(self.sample);sample['results'].pop('163');sample['receipt_hashes'].pop('163')
        with self.assertRaises(ValueError):new.validate(self.case,sample,previous=self.previous)

    def test_wrong_controls_and_exposure_lineage_remain_invalid(self):
        for fault in ('lr','epsilon','replay_epoch','optimizer_epoch'):
            sample=copy.deepcopy(self.sample)
            if fault=='lr':sample['api']['lr']*=2
            elif fault=='epsilon':sample['api']['epsilon']=.2
            else:sample['api']['host_pipeline']['learning_exposure'][fault.split('_')[0]]['epoch']+=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):new.validate(self.case,sample,previous=self.previous)

    def test_all_other_original_main_health_predicates_are_AST_identical(self):
        old_tree=ast.parse((Path(old.__file__).with_name('round_main_health_v4.py')).read_bytes())
        new_tree=ast.parse((Path(new.__file__).with_name('round_main_health_v5.py')).read_bytes())
        originals={node.name:node for node in old_tree.body if isinstance(node,ast.FunctionDef)}
        current={node.name:node for node in new_tree.body if isinstance(node,ast.FunctionDef)}
        for name,node in originals.items():
            if name!='validate':self.assertEqual(ast.dump(node),ast.dump(current[name]),name)
        original=originals['validate'];changed=copy.deepcopy(current['validate'])
        original_index=next(i for i,node in enumerate(original.body)
            if isinstance(node,ast.Expr)and isinstance(node.value,ast.Call)
            and any(isinstance(arg,ast.Constant)and arg.value=='Unknown, duplicate or missing API client'for arg in node.value.args))
        replacement=changed.body[original_index]
        self.assertIsInstance(replacement,ast.If);self.assertIsInstance(replacement.test,ast.UnaryOp)
        self.assertEqual(ast.dump(replacement.test.operand),ast.dump(original.body[original_index].value.args[0]))
        self.assertEqual(ast.dump(replacement.body[0].value),ast.dump(ast.parse('certify_API_reconnect(case,sample,previous)').body[0].value))
        self.assertEqual(replacement.orelse,[])
        changed.body[original_index]=original.body[original_index]
        self.assertEqual(ast.dump(changed),ast.dump(original))

    def test_original_failed_C1_remains_invalid_without_score_or_retry(self):
        result=json.loads((LEG/'deadline-output-original01/result.json').read_bytes())
        self.assertEqual(result['status'],'ORIGINAL_DEADLINE32_FAILED_NO_RETRY')
        self.assertFalse(result['complete']);self.assertIsNone(result['deadline_score_seal'])
        self.assertFalse((LEG/'root-C1-independent-qualified.json').exists())


if __name__=='__main__':unittest.main()
