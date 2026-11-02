"""New review-v2 marker/composition scope after the original6 log-rule failure.

Only fixture-producing helpers are reused; no consumed test method or reader
main runs. Actor PIDs, command descriptors and policy receipts are synthetic.
No model/GPU/MAME or main mutation is performed.
"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest

HERE=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


previous=load('_consumed_final_scope_fixture_helpers_only',HERE/'test_full_tail_final_scope_v1.py')
review=load('_new_original_final_review_marker_v2',HERE/'read_compiled_full_tail32_original_v2.py')


class FinalReviewMarkerIntegrationV2(unittest.TestCase):
    def metadata(self):
        fixture=previous.FinalFullTailScope()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_corrected_review_composes_exact_v2_scope_controller_raw_prefix_and_runtime_closure(self):
        fixture=self.metadata();directory,job,jp,config,scope=fixture.documents()
        review.validate_scope(job,jp,scope,config)
        self.assertEqual(previous.runtime.validate_job(job),directory/'uncreated-output')
        path=directory/'new-controller-composition.json';path.write_text(json.dumps(config))
        self.assertEqual(previous.control.checked_config(path),config)
        original=fixture.result();policy,cohort=review.validate_runtime_result(original,job)
        self.assertEqual(cohort['count'],32);self.assertFalse(original['quality_qualified'])
        wrong=copy.deepcopy(original);wrong['original_slots']['4096']['actual_exit']=None
        with self.assertRaises(ValueError):review.validate_runtime_result(wrong,job)
        f=previous.defs.Fixture();self.addCleanup(f.close)
        prefix=previous.wire.audit_slot_prefix(4096,f.entry,f.job,f.result,f.starts,f.games,f.read,previous.h.pin,
            expected_job_sha256=previous.defs.audit.JOB_SHA)
        self.assertEqual(prefix['session'],f.subject['session'])
        self.assertTrue(prefix['prefix_ledger']['raw_prefix_ledger_recomputed'])
        with self.assertRaises(ValueError):previous.wire.audit_slot_prefix(4096,f.entry,f.job,f.result,f.starts,
            f.games,f.read,previous.h.pin,expected_job_sha256='b'*64)
        lifecycle=directory/'original-lifecycle-inode.jsonl';lifecycle.touch(mode=0o600);s=lifecycle.stat()
        initial=dict(device=s.st_dev,inode=s.st_ino,mode='0o600',uid=s.st_uid,nlink=1)
        lifecycle.write_bytes(b'synthetic completed bytes\n');lifecycle.chmod(0o444)
        self.assertTrue(previous.wire.validate_original_file_identity(initial,previous.h.pin(lifecycle))
                        ['final_owned_seal_verified'])
        bad_scope=dict(scope,quality_minimum_games_remains=32)
        with self.assertRaises(ValueError):review.validate_scope(job,jp,bad_scope,config)
        self.assertNotIn('torch',sys.modules)

    def test_root_transport_markers_and_unknown_errors_reject_after_valid_closure_and_narrow_allowances(self):
        fixture=self.metadata();_,job,_,_,_=fixture.documents();result=fixture.result()
        policy,_=review.validate_runtime_result(result,job)
        clean=review.EXPERT+'\nClient 0 disconnected: EOF\n'
        self.assertEqual(review.audit_evaluator_logs(clean,'',policy,True)['unknown_errors'],0)
        markers=['[SOCKET ACTION TIMEOUT]',
            '[SOCKET ACTION TIMEOUT] slot=4096 unix_s=123 partial_bytes=0',
            'Socket open failed: socket.127.0.0.1:20000 (Connection refused)',
            'RuntimeError: Inference batcher stopped before completion',
            '[WARN] unexpected fallback','[WARN] unknown unavailable']
        for stream in ('stdout','stderr'):
            for marker in markers:
                with self.subTest(stream=stream,marker=marker),self.assertRaises(ValueError):
                    review.audit_evaluator_logs(clean+'\n'+marker if stream=='stdout'else clean,
                        marker if stream=='stderr'else '',policy,True)
        with self.assertRaises(ValueError):review.audit_evaluator_logs(clean,'',policy,False)
        with self.assertRaises(ValueError):review.audit_evaluator_logs(clean,'',dict(policy,expert_ratio=.1),True)
        actor='\n'.join(['MAME interface initialized.','[PATCH] RRCHRIS runtime ROM patch disabled.',
            'Socket connection opened to socket.127.0.0.1:20000','[DIFFICULTY] GA1 poked to 5'])
        stderr=review.ALSA+'\n[robotron-socket-wait] pid=999999999 fd=9 port=20000 interval_us=1000\n'
        self.assertEqual(review.audit_actor_logs(actor,stderr,4096,999999999,20000)['action_timeouts'],0)
        with self.assertRaises(ValueError):review.audit_actor_logs(actor+'\n'+markers[0],stderr,4096,999999999,20000)

    def test_only_marker_pattern_changed_and_native_identity_resource_time_checks_stay_strict(self):
        old=ast.parse((HERE/'read_compiled_full_tail32_original_v1.py').read_text())
        new=ast.parse((HERE/'read_compiled_full_tail32_original_v2.py').read_text())
        def without_flag(tree):
            tree.body=[n for n in tree.body if not(isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name)and t.id=='FLAG'for t in n.targets))]
            return ast.dump(tree,include_attributes=False)
        self.assertEqual(without_flag(old),without_flag(new))
        fixture=self.metadata();_,_,_,config,_=fixture.documents();now=time.monotonic()
        owner=dict(unit=config['unit'],invocation_id='d'*32,pid=999999999)
        fields=dict(Id=owner['unit'],InvocationID=owner['invocation_id'],ExecMainPID=str(owner['pid']),
            ExecMainCode='1',ExecMainStatus='0',NRestarts='0',CPUQuotaPerSecUSec='12s',MemoryMax=str(16<<30),
            MemorySwapMax='0',RuntimeMaxUSec='9660s',TasksMax='512',TimeoutStopUSec='30s',KillMode='mixed',
            SendSIGKILL='no',Restart='no',ExecStart='argv[]='+' '.join(config['argv'])+' ; ignore_errors=no ;',
            ExecMainStartTimestampMonotonic=str(int((now-2)*1e6)),ExecMainExitTimestampMonotonic=str(int((now-1)*1e6)))
        start,end=review.validate_native_fields(fields,config,owner,previous.rt.duration_seconds)
        self.assertLess(start,end)
        for key,value in [('ExecMainStatus','1'),('MemoryMax',str(4<<30)),('ExecStart','wrong'),
            ('InvocationID','e'*32),('RuntimeMaxUSec','900s')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                review.validate_native_fields(dict(fields,**{key:value}),config,owner,previous.rt.duration_seconds)


if __name__=='__main__':unittest.main(verbosity=2)
