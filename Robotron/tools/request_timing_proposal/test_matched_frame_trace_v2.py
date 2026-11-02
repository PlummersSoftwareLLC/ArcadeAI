"""Reuse all thirteen v1 CPU contracts and add fast-path/completion-tail checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import types
import unittest
from unittest.mock import patch

H=Path(__file__).resolve().parent
sys.path.insert(0,str(H))
import matched_frame_trace_v2 as trace
import prepare_matched_trace_sources_v2 as builder

OLD_TEST_SHA='52d0d952a05c2d7e8644f925b88cf85a5bdaf614300b7ff11eadf175cb44dd43'
path=H/'test_matched_frame_trace_v1.py'
if hashlib.sha256(path.read_bytes()).hexdigest()!=OLD_TEST_SHA:raise ValueError('Exact thirteen original contract bodies required')
spec=importlib.util.spec_from_file_location('_matched_v2_original_contract_bodies',path)
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
# Only this isolated test module instance is redirected. No production import,
# source mutation, service controller or second dependency instance is involved.
original.trace=trace;original.builder=builder


class Tests(original.Tests):
    def test_reuses_same_bounded_data_model_and_coverage_decoder(self):
        self.assertIs(trace.Recorder.__init__,trace._base.Recorder.__init__)
        self.assertIs(trace.Recorder.frame,trace._base.Recorder.frame)
        self.assertIs(trace.Recorder.child,trace._base.Recorder.child)
        self.assertIs(trace.validate_snapshot,trace._base.validate_snapshot)
        self.assertEqual(trace.Recorder().snapshot()['implementation'],'fast-scopes-v2')

    def test_uncaptured_paths_share_noop_and_never_call_v1_generators(self):
        connection=trace.connection(5,7);item=('step',5,None,{})
        with patch.object(trace._base,'frame',side_effect=AssertionError('v1 frame called')), \
             patch.object(trace._base,'enqueue',side_effect=AssertionError('v1 enqueue called')), \
             patch.object(trace._base,'consume',side_effect=AssertionError('v1 consume called')):
            scope=trace.frame(connection);self.assertIs(scope,trace._NOOP)
            with scope:pass
            self.assertIs(trace.enqueue(item),trace._NOOP)
            self.assertIs(trace.consume(item),trace._NOOP)
            self.assertEqual(connection[3],1)
            with self.assertRaisesRegex(ArithmeticError,'propagated'):
                with trace.frame(connection):raise ArithmeticError('propagated')

    def test_admitted_frame_inference_and_replay_continue_after_capture_closes(self):
        recorder=self.recorder();agent=self.Agent()
        buffer=self.classes['AsyncReplayBuffer'](agent,max_queue_size=8)
        batcher=self.classes['AsyncInferenceBatcher'](agent,max_wait_ms=0,request_timeout_ms=2000)
        capture=trace.capture(recorder);capture.__enter__()
        scope=trace.frame(trace.connection(1,7));scope.__enter__()
        capture.__exit__(None,None,None)
        try:
            trace.frame_mark('payload_complete')
            buffer.step_async([1.]*4,(1,2),0.,[1.]*4,False,client_id=1,actor='dqn')
            self.assertEqual(batcher.infer([1.]*4,0.,locked_fire=4),(8,4,False))
        finally:
            scope.__exit__(None,None,None)
            self.assertTrue(buffer.barrier_async().wait(2));batcher.stop();buffer.stop()
        report=trace.validate_snapshot(recorder.snapshot())
        self.assertEqual(report['sampled_frames'],1)
        self.assertEqual(report['completed_handler_scopes'],1)
        self.assertEqual(report['inference_requests'],1)
        self.assertEqual(report['accepted_ring_add_events'],1)
        self.assertEqual(report['pending_routes'],0)
        self.assertEqual(report['capture_loss'],dict(capacity_drops=0,event_drops=0,child_drops=0,faults=0))

    def test_pending_command_blocks_next_capture_until_late_insert_finishes(self):
        entered=threading.Event();release=threading.Event();base=self.Agent
        class Blocked(base):
            def step(self,*args,**kwargs):
                entered.set()
                if not release.wait(3):raise RuntimeError('Test synchronization expired')
                return super().step(*args,**kwargs)
        recorder=self.recorder();buffer=self.classes['AsyncReplayBuffer'](Blocked(),max_queue_size=8)
        try:
            with trace.capture(recorder):
                with trace.frame(trace.connection(1,7)):
                    buffer.step_async([1.]*4,(1,2),0.,[1.]*4,False,client_id=1,actor='dqn')
                self.assertTrue(entered.wait(1))
            self.assertEqual(recorder.snapshot()['pending_routes'],1)
            with self.assertRaises(RuntimeError):
                with trace.capture(self.recorder()):pass
        finally:release.set()
        self.assertTrue(buffer.barrier_async().wait(2));buffer.stop()
        report=trace.validate_snapshot(recorder.snapshot())
        self.assertEqual(report['accepted_ring_add_events'],1)
        self.assertEqual(report['incomplete_admitted_commands'],0)
        self.assertEqual(report['pending_routes'],0)
        with trace.capture(self.recorder()):pass

    def test_nested_untracked_consumer_does_not_borrow_parent_ticket(self):
        recorder=self.recorder();item=('step',5,None,{});untracked=('step',6,None,{})
        exposure=types.SimpleNamespace(process_id=1,instance_monotonic_ns=2,epoch=3)
        with trace.capture(recorder):
            with trace.frame(trace.connection(5,7)):
                with trace.enqueue(item):trace.enqueue_succeeded(item)
                trace.dequeued(item)
                with trace.consume(item):
                    with trace.consume(untracked):trace.insert_accepted(exposure,'dqn')
                    trace.insert_accepted(exposure,'dqn')
        report=trace.validate_snapshot(recorder.snapshot())
        self.assertEqual(report['replay_commands'],1)
        self.assertEqual(report['accepted_ring_add_events'],1)
        self.assertEqual(report['pending_routes'],0)

    def test_nested_unsampled_frame_does_not_borrow_parent_ticket(self):
        recorder=trace.Recorder(sample_every=2);connection=trace.connection(5,7)
        with trace.capture(recorder):
            with trace.frame(connection) as outer:
                with trace.frame(connection) as inner:
                    self.assertIsNone(inner)
                    self.assertIsNone(trace.new_request())
                    trace.frame_mark('inner_only')
                self.assertIs(trace._local.frame,outer)
                trace.frame_mark('outer_only')
        snapshot=recorder.snapshot();self.assertEqual(len(snapshot['frames']),1)
        self.assertEqual(snapshot['seen'],2)
        phases={p for p,t,m in snapshot['frames'][0]['events']}
        self.assertIn('outer_only',phases);self.assertNotIn('inner_only',phases)
        self.assertEqual(snapshot['unmatched_inference'],0)

    def test_closed_capture_child_fault_is_counted_without_changing_action(self):
        recorder=self.recorder();batcher=self.classes['AsyncInferenceBatcher'](self.Agent(),max_wait_ms=0,request_timeout_ms=2000)
        capture=trace.capture(recorder);capture.__enter__();scope=trace.frame(trace.connection(1,7));scope.__enter__()
        capture.__exit__(None,None,None)
        def broken(*args,**kwargs):raise OSError('Injected closed-capture child fault')
        recorder.child=broken
        try:self.assertEqual(batcher.infer([1.]*4,0.,locked_fire=4),(8,4,False))
        finally:scope.__exit__(None,None,None);batcher.stop()
        self.assertGreater(recorder.snapshot()['faults'],0)

    def test_v1_and_v2_same_clock_produce_identical_event_trees(self):
        def transcript(module):
            stamps=iter(range(1000,100000,100));recorder=module.Recorder(sample_every=1,clock=lambda:next(stamps))
            exposure=types.SimpleNamespace(process_id=1,instance_monotonic_ns=2,epoch=3)
            item=('step',5,None,{})
            with module.capture(recorder):
                with module.frame([5,7,11,0]):
                    module.frame_mark('payload_complete')
                    request=module.new_request()
                    for phase in ['enqueue_attempt','dequeued','coalescing_end','act_begin','act_end','signal_before','waiter_awake','returned']:
                        module.mark(request,phase)
                    with module.enqueue(item):module.enqueue_succeeded(item)
                    module.dequeued(item)
                    with module.consume(item):
                        module.insert_accepted(exposure,'dqn');module.consumer_mark('agent_step_returned')
                    module.frame_mark('action_write_completed')
            snapshot=recorder.snapshot();snapshot.pop('implementation',None);return snapshot
        before=transcript(trace._base);after=transcript(trace)
        self.assertEqual(before,after)
        self.assertEqual(trace._base.validate_snapshot(before),trace.validate_snapshot(after))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n in sys.modules for n in ('dqn.agent','dqn.socket_server','dqn.replay_buffer'))
    print(json.dumps(dict(schema='robotron-matched-frame-fast-scope-CPU-contracts-v2',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        inherited_v1_contracts=13,added_fast_scope_tail_contracts=8,torch_imported=False,
        production_modules_imported=False,live_source_modified=False,
        scope='Exact selected methods/classes, small CPU arrays and index/tensor shims. No real bank/parser/GPU/MAME workload.')))
    sys.exit(0 if result.wasSuccessful() else 1)
