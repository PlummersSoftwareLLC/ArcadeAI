"""CPU shutdown/concurrency and unselected native source gate contracts; no MAME/GPU."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-owned-native-health-wiring-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(n,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(n,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_native_wire_h',job['helpers'])
    for pin in [v for v in job.values()if isinstance(v,dict)and 'path'in v]:h.checked(pin)
    finalize=load('_native_wire_final',job['finalizer']);runtime=load('_native_wire_runtime',job['template']);prefix=load('_native_wire_prefix',job['prefix'])
    output=Path(job['output']);output.mkdir(mode=0o700);negative=[];sources=None
    class Guard:
        def __init__(self,close_error=False):
            self.stop=threading.Event();self.close_error=close_error;self.calls=[]
            self.writer=threading.Thread(target=lambda:self.stop.wait(3),name='synthetic-owned-writer',daemon=True);self.writer.start()
            self.collector=SimpleNamespace(writer=SimpleNamespace(thread=self.writer))
        def close(self):
            self.calls.append('close')
            if self.close_error:raise ValueError('original guard failed')
            self.stop.set();self.writer.join(1)
            return dict(explicit_synthetic_guard=True,quality_qualified=False)
        def preserve_failure(self,error):
            self.calls.append('preserve_failure');self.stop.set();self.writer.join(1)
            return dict(error=repr(error),explicit_synthetic_failure=True,quality_qualified=False)
    def folder(name):
        path=output/name;path.mkdir();return path
    class Contracts(unittest.TestCase):
        def test_all_original_game_actor_ROM_wire_lease_functions_are_unchanged(self):
            nonlocal sources
            def definitions(pin):
                tree=ast.parse(Path(pin['path']).read_bytes())
                return {node.name:ast.dump(node,include_attributes=False)for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
            old=definitions(job['original_runtime']);new=definitions(job['template'])
            self.assertEqual(set(old),set(new));self.assertEqual([name for name in old if old[name]!=new[name]],['validate_job','run'])
            tree=ast.parse(Path(job['template']['path']).read_bytes());run=next(node for node in tree.body if isinstance(node,ast.FunctionDef)and node.name=='run')
            watch=next(node for node in ast.walk(run)if isinstance(node,ast.FunctionDef)and node.name=='watch_main')
            locked=next(node for node in ast.walk(watch)if isinstance(node,ast.With))
            self.assertIsInstance(locked.body[0],ast.If);self.assertIn('health_stop.is_set()',ast.unparse(locked.body[0]))
            self.assertIsInstance(locked.body[0].body[0],ast.Return)
            self.assertEqual(ast.unparse(locked.body[1]),'collect_main()')
            sources=dict(all_independent_original_definitions_preserved_except_validate_job_and_run=True,
                watch_stop_rechecked_inside_capture_lock_before_collection=True)
        def test_old_policy_pair_cannot_launch_even_reference_in_new_template(self):
            old=json.loads(h.checked(job['old_native_job']).read_bytes())
            with self.assertRaisesRegex(ValueError,'genuinely later'):runtime.validate_job(old)
            negative.append('old2630_pair_cannot_launch_new_template')
            self.assertEqual(prefix.verified_groups(dict(quality_leg='R1'),dict(prior_case=None),{},None,None),[])
            with self.assertRaises(ValueError):prefix.verified_groups(dict(quality_leg='R1'),dict(prior_case={}),{},None,None)
            with self.assertRaises(ValueError):prefix.verified_groups(dict(quality_leg='C1'),dict(prior_case=None),{},None,None)
            negative.extend(['R1_historical_prefix_forbidden','C1_missing_closed_prefix_forbidden'])
        def test_waiter_already_queued_on_capture_lock_cannot_capture_after_atomic_stop(self):
            guard=Guard();stop=threading.Event();lock=threading.Lock();start=threading.Event();attempt=threading.Event();extra=[]
            def watch():
                assert start.wait(1);attempt.set()
                with lock:
                    if stop.is_set():return
                    extra.append('unwanted capture')
            worker=threading.Thread(target=watch,name='synthetic-queued-health-watch');worker.start()
            def collect():
                start.set();assert attempt.wait(1);return dict(phase=dict(overlap_pending=False))
            result=finalize.finalize(guard,worker,stop,lock,collect,time.monotonic()+2,h,folder('queued-watch'))
            self.assertEqual(extra,[]);self.assertEqual(result['errors'],[])
            self.assertTrue(result['watch_stopped']and result['writer_stopped']);self.assertIsNotNone(result['report'])
        def test_pending_final_evidence_is_sampled_until_complete_without_changing_deadline(self):
            guard=Guard();calls=[];stop=threading.Event();deadline=time.monotonic()+2
            def collect():
                calls.append(time.monotonic());return dict(phase=dict(overlap_pending=len(calls)<2))
            result=finalize.finalize(guard,None,stop,threading.Lock(),collect,deadline,h,folder('pending'))
            self.assertEqual(len(calls),2);self.assertLess(calls[-1],deadline)
            self.assertTrue(result['writer_stopped']);self.assertEqual(result['errors'],[])
        def test_original_failure_is_preserved_and_writer_stops_without_late_capture(self):
            guard=Guard(close_error=True);calls=[]
            result=finalize.finalize(guard,None,threading.Event(),threading.Lock(),lambda:calls.append('unexpected'),
                time.monotonic()+2,h,folder('failed'),case_already_failed=True)
            self.assertEqual(calls,[]);self.assertEqual(guard.calls,['close','preserve_failure'])
            self.assertIsNone(result['report']);self.assertIsNotNone(result['failure']);self.assertTrue(result['writer_stopped'])
            negative.append('failed_case_never_captured_again_to_rescue')
        def test_expired_native_deadline_records_failure_without_extending_capture(self):
            guard=Guard();calls=[]
            result=finalize.finalize(guard,None,threading.Event(),threading.Lock(),lambda:calls.append('late'),
                time.monotonic()-1,h,folder('deadline'))
            self.assertEqual(calls,[]);self.assertTrue(any('no extension'in error for error in result['errors']))
            self.assertTrue(result['writer_stopped']);negative.append('native_deadline_not_extended')
        def test_unknown_watch_completion_never_calls_guard_close_or_hashes_outputs(self):
            guard=Guard()
            class UnknownWatch:
                def join(self,timeout):pass
                def is_alive(self):return True
            try:
                result=finalize.finalize(guard,UnknownWatch(),threading.Event(),threading.Lock(),lambda:None,
                    time.monotonic()+2,h,folder('unknown-watch'),case_already_failed=True)
                self.assertEqual(guard.calls,[]);self.assertFalse(result['watch_stopped'])
                self.assertIsNone(result['report']);self.assertIsNone(result['failure'])
                self.assertEqual(list((output/'unknown-watch').iterdir()),[])
            finally:guard.stop.set();guard.writer.join(1)
            negative.append('unknown_watch_never_closed_or_hashed_as_success')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    receipt=dict(status='UNSELECTED_NATIVE_HEALTH_WIRING_CONCURRENCY_CLOSURE_AND_OLD_POLICY_GATES_PASS',
        tests=result.testsRun,negative_checks=negative,source_contract=sources,
        source_sha256=args.source_sha256,job_sha256=args.job_sha256,
        source_template_still_requires_new_pair_and_full_reader_preparer_sequence_integration=True,
        actual_MAME_or_GPU_started=False,quality_qualified=False,production_changed=False,created_unix_s=time.time())
    h.put(output/'report.json',receipt);print(json.dumps(dict(status=receipt['status'],tests=result.testsRun,negative_checks=len(negative))),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
