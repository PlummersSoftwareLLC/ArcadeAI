"""New future-reviewer log checks; never rerun the original scientific review."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

B=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal')
R=B.parents[1]/'logs/managed-learning-20261015/run-26'
N=R/'compiled32-policy-full-tail-cleanup-v2-real-original01-preparation-20261022'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

q=load('_future_quality_token_reviewer',B/'read_compiled_quality32_original_v2.py')
old=load('_unexecuted_quality_line_reviewer',B/'read_compiled_quality32_original_v1.py')

class QualityShutdownTokensV1(unittest.TestCase):
    def setUp(self):
        self.policy=dict(epsilon=0,expert_ratio=0,training_enabled=False)
        self.ids=set(range(32))
        self.tokens=[f'Client {i} disconnected: EOF'for i in range(32)]

    def audit(self,stdout,stderr='',policy=None,optional=True,ids=None):
        return q.audit_evaluator_logs(stdout,stderr,self.policy if policy is None else policy,optional,
            expected_closed_client_ids=self.ids if ids is None else ids)

    def test_actual_archived_concatenated_shutdown_stream_has_exact_original_closed_client_coverage(self):
        native=json.loads((N/'diagnostic-output-original01/result.json').read_text())
        actual={row['client_id']for row in native['drain_payload']['original_subjects']}
        self.assertEqual(actual,self.ids)
        self.assertTrue(native['complete']);self.assertEqual(native['errors'],[])
        self.assertTrue(all(row['actual_exit']==0 and row['peer_EOF']for row in native['original_slots'].values()))
        stdout=(N/'independent-full-tail-review-original01/original-native-stdout.txt').read_text()
        stderr=(N/'independent-full-tail-review-original01/original-native-stderr.txt').read_text()
        result=self.audit(stdout,stderr,policy=native['policy_before'],ids=actual)
        self.assertEqual(result['exact_shutdown_tokens'],32)
        self.assertEqual(result['closed_client_ids'],sorted(actual))
        self.assertEqual(result['unknown_errors'],0)
        self.assertEqual(sum(len(row['client_ids'])>1 for row in result['allowed_diagnostics']),3)
        with self.assertRaisesRegex(ValueError,'Unclassified original evaluator log diagnostic'):
            old.audit_evaluator_logs(stdout,stderr,native['policy_before'],True)

    def test_exact_shutdown_tokens_accept_normal_lines_or_one_interleaved_line_without_changing_bytes(self):
        for separator in ('','\n',' \t '):
            text=separator.join(f'Client {i} disconnected: '+('EOF'if i%2 else'Broken payload')for i in range(32))
            before=text.encode()
            result=self.audit(text)
            self.assertEqual(result['exact_shutdown_tokens'],32)
            self.assertEqual(result['closed_client_ids'],list(range(32)))
            self.assertEqual(text.encode(),before)

    def test_duplicate_missing_foreign_and_unverified_closed_client_rosters_reject(self):
        for rows in [self.tokens+[self.tokens[0]],self.tokens[:-1],
                self.tokens[:-1]+['Client 32 disconnected: EOF']]:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):self.audit(''.join(rows))
        for ids in [set(range(31)),set(range(31))|{-1},list(range(32)),set(range(31))|{31.0}]:
            with self.subTest(ids=ids):
                with self.assertRaises(ValueError):self.audit(''.join(self.tokens),ids=ids)

    def test_embedded_unknown_bytes_and_root_error_markers_reject_in_both_streams_after_valid_closure(self):
        for extra in ['Traceback','RuntimeError: failure','[SOCKET ACTION TIMEOUT]',
                'Socket open failed: connect','fallback active','unavailable runtime',
                'Error','extra bytes','ErrorClient 31 disconnected: EOF']:
            for position in ('prefix','middle','suffix'):
                with self.subTest(extra=extra,position=position):
                    if position=='prefix':text=extra+''.join(self.tokens)
                    elif position=='middle':text=self.tokens[0]+extra+''.join(self.tokens[1:])
                    else:text=''.join(self.tokens)+extra
                    with self.assertRaises(ValueError):self.audit(text)
        for marker in ['[SOCKET ACTION TIMEOUT]','Socket open failed: connect','Traceback: bad',
                'RuntimeError: stopped','inference unavailable','eager fallback']:
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):self.audit('\n'.join(self.tokens)+'\n'+marker)
                with self.assertRaises(ValueError):self.audit('\n'.join(self.tokens),marker)
        with self.assertRaises(ValueError):self.audit('\n'.join(self.tokens),self.tokens[0])

    def test_optional_expert_diagnostic_remains_exact_single_and_requires_frozen_controls_and_proof(self):
        stream=q.EXPERT+'\n'+'\n'.join(self.tokens)
        self.assertEqual(self.audit(stream)['exact_shutdown_tokens'],32)
        for bad in [q.EXPERT+'\n'+stream,q.EXPERT+' extra\n'+'\n'.join(self.tokens)]:
            with self.assertRaises(ValueError):self.audit(bad)
        with self.assertRaises(ValueError):self.audit(stream,optional=False)
        for key,value in [('epsilon',.1),('expert_ratio',.1),('training_enabled',True)]:
            policy=copy.deepcopy(self.policy);policy[key]=value
            with self.assertRaises(ValueError):self.audit(stream,policy=policy)

    def test_only_future_log_classifier_and_actual_prefix_closed_roster_call_change(self):
        def definitions(path):
            return {node.name:ast.dump(node,include_attributes=False)for node in ast.parse(path.read_text()).body
                if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
        a,b=definitions(Path(old.__file__)),definitions(Path(q.__file__))
        self.assertEqual([key for key in a if a[key]!=b[key]],['audit_evaluator_logs','review'])
        tree=ast.parse(Path(q.__file__).read_text())
        review=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='review')
        calls=[n for n in ast.walk(review)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)
            and n.func.id=='audit_evaluator_logs']
        self.assertEqual(len(calls),1)
        roster=next(k.value for k in calls[0].keywords if k.arg=='expected_closed_client_ids')
        self.assertEqual(ast.dump(roster),ast.dump(ast.parse("{prefix['client_id']for prefix in prefixes.values()}",mode='eval').body))

if __name__=='__main__':unittest.main(verbosity=2)
