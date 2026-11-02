"""CPU contracts for proposed matched handler/inference/replay instrumentation.

Extract selected classes/methods. No complete production module is imported.
Replay writes use small CPU arrays and an index-tree shim, never a real bank.
"""
import ast
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import random
import socket
import struct
import sys
import threading
import time
import traceback
import types
import unittest

H=Path(__file__).resolve().parent;G=H.parents[1]
sys.path.insert(0,str(H))
import matched_frame_trace_v1 as trace
import prepare_matched_trace_sources_v1 as builder


def extract(nodes,scope):
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<CPU-extracted-matched-source>','exec'),scope)
    return scope


def setup_sources():
    original={name:(G/'Scripts/dqn'/name).read_text() for name in
              ['socket_server.py','agent.py','learning_exposure.py','replay_buffer.py']}
    proposed=dict(socket_server=builder.socket_source(original['socket_server.py']),
        agent=builder.agent_source(original['agent.py']),
        exposure=builder.exposure_source(original['learning_exposure.py'],builder.EXPOSURE_SHA))
    return original,proposed


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np=np;cls.original,cls.proposed=setup_sources()
        exposure_node=next(n for n in ast.parse(cls.proposed['exposure']).body
            if isinstance(n,ast.ClassDef) and n.name=='ReplayInsertExposure')
        exposure_scope=extract([exposure_node],dict(os=os,time=time,_request_trace=trace))
        cls.Exposure=exposure_scope['ReplayInsertExposure']
        config=types.SimpleNamespace()
        nodes=[n for n in ast.parse(cls.proposed['socket_server']).body if isinstance(n,ast.ClassDef)
               and n.name in ('AsyncReplayBuffer','_InferenceRequest','AsyncInferenceBatcher')]
        cls.classes=extract(nodes,dict(queue=queue,threading=threading,time=time,deque=deque,
            RL_CONFIG=config,_request_trace=trace,metrics=types.SimpleNamespace(note_replay_drop=lambda n:None)))
        replay_tree=ast.parse(cls.original['replay_buffer.py'])
        replay_class=next(n for n in replay_tree.body if isinstance(n,ast.ClassDef) and n.name=='PrioritizedReplayBuffer')
        add=next(n for n in replay_class.body if isinstance(n,ast.FunctionDef) and n.name=='add')
        kind=next(n for n in replay_class.body if isinstance(n,ast.FunctionDef) and n.name=='actor_kind_from_name')
        kind.decorator_list=[]
        mem_scope=extract([add,kind],dict(np=np,RL_CONFIG=config,ACTOR_DQN=0,ACTOR_EPSILON=1,
            ACTOR_EXPERT=2,ACTOR_KIND_COUNT=3))
        class Tree:
            def __init__(self):self.max_priority=1.;self.size=self.data_ptr=0
            def add(self,priority):
                index=self.data_ptr;self.data_ptr=(index+1)%1024;self.size=min(1024,self.size+1);return index
        class Memory:
            add=mem_scope['add'];actor_kind_from_name=staticmethod(mem_scope['actor_kind_from_name'])
            def __init__(self):
                self.capacity=1024;self.lock=threading.RLock();self.tree=Tree();self.alpha=.6
                self.size=self._adds_total=self._n_expert=self._n_interesting=0
                self._n_actor=np.zeros(3,dtype=np.int64)
                for name in ['states','next_states']:setattr(self,name,np.zeros((1024,4),dtype=np.float32))
                for name in ['actions','rewards','dones','horizons','is_expert','actor_kind','interesting']:
                    setattr(self,name,np.zeros(1024,dtype=np.float32))
                self._interesting_bank=np.zeros(1024,dtype=np.int64)
                self._interesting_bank_ptr=self._interesting_bank_count=0
                self._insert_exposure=cls.Exposure()
        agent_tree=ast.parse(cls.proposed['agent']);agent_class=next(n for n in agent_tree.body
            if isinstance(n,ast.ClassDef) and n.name=='RainbowAgent')
        methods=[n for n in agent_class.body if isinstance(n,ast.FunctionDef) and n.name in ('step','act_batch')]
        scope=extract(methods,dict(np=np,_request_trace=trace,random=random.Random(123),
            torch=types.SimpleNamespace(from_numpy=lambda a:a),RL_CONFIG=config,
            combine_action=lambda m,f:m*9+f,split_joint_action=lambda j:divmod(j,9),
            NUM_MOVE=9,NUM_FIRE=9,NUM_JOINT=81))
        class Agent:
            step=scope['step'];act_batch=scope['act_batch']
            def __init__(self):self.memory=Memory()
            def _safe_epsilon_action(self,state):return 2,3,True
            def _infer_q_joint(self,state,return_cpu):
                rows=np.tile(np.arange(81,dtype=np.float32),(len(state),1))
                return types.SimpleNamespace(numpy=lambda:rows)
        cls.Agent=Agent

    def recorder(self,**kwargs):return trace.Recorder(sample_every=1,**kwargs)

    def test_operational_AST_preserved_for_all_three_copies(self):
        for key,name in [('socket_server','socket_server.py'),('agent','agent.py'),('exposure','learning_exposure.py')]:
            self.assertEqual(builder.stripped_tree(self.original[name]),builder.stripped_tree(self.proposed[key]))

    def test_source_hash_drift_refused(self):
        for name,fn in [('socket_server.py',builder.socket_source),('agent.py',builder.agent_source)]:
            with self.assertRaisesRegex(ValueError,'Pinned source'):fn(self.original[name]+'\n')
        with self.assertRaises(ValueError):builder.exposure_source(self.original['learning_exposure.py'],'0'*64)

    def test_joined_frame_inference_commands_and_actual_CPU_ring_adds(self):
        agent=self.Agent();buffer=self.classes['AsyncReplayBuffer'](agent,batch_size=4,max_queue_size=8)
        batcher=self.classes['AsyncInferenceBatcher'](agent,max_wait_ms=0,request_timeout_ms=2000)
        recorder=self.recorder();state=self.np.array([1.,2.,3.,4.],dtype=self.np.float32)
        try:
            with trace.capture(recorder):
                with trace.frame(trace.connection(10,7)):
                    trace.frame_mark('payload_complete')
                    buffer.step_async(state,(1,2),.5,state,False,client_id=10,actor='dqn',horizon=3)
                    buffer.step_async(state,(2,3),.25,state,True,client_id=10,actor='epsilon',horizon=1)
                    action=batcher.infer(state,0.,locked_fire=4)
                    self.assertEqual(action,(8,4,False))
                    trace.frame_mark('action_write_completed')
                self.assertTrue(buffer.barrier_async().wait(2))
        finally:batcher.stop();buffer.stop()
        snapshot=recorder.snapshot();report=trace.validate_snapshot(snapshot)
        self.assertEqual(report['sampled_frames'],1)
        self.assertEqual(report['replay_commands'],2)
        self.assertEqual(report['inference_requests'],1)
        self.assertEqual(report['accepted_ring_add_events'],2)
        self.assertEqual(report['pending_routes'],0)
        self.assertEqual(report['capture_loss'],dict(capacity_drops=0,event_drops=0,child_drops=0,faults=0))
        self.assertEqual(agent.memory._insert_exposure.snapshot()['accepted_learner_total'],2)
        self.np.testing.assert_array_equal(agent.memory.states[:2],[state,state])
        self.np.testing.assert_array_equal(agent.memory.horizons[:2],[3,1])
        self.np.testing.assert_array_equal(agent.memory.actions[:2],[11,21])
        self.assertEqual([r['metadata']['command'] for r in snapshot['frames'][0]['commands']],['step','step'])
        self.assertEqual(report['unmatched_commands'],{'barrier':1})
        json.dumps(snapshot,allow_nan=False) # No input arrays or objects retained.

    def test_concurrent_frame_and_command_identity_never_crosses_actors(self):
        agent=self.Agent();buffer=self.classes['AsyncReplayBuffer'](agent,batch_size=8,max_queue_size=32)
        batcher=self.classes['AsyncInferenceBatcher'](agent,max_wait_ms=1,request_timeout_ms=2000)
        recorder=self.recorder(max_frames=128)
        def actor(cid):
            connection=trace.connection(cid,cid)
            for turn in range(4):
                state=self.np.full(4,cid*10+turn,dtype=self.np.float32)
                with trace.frame(connection):
                    buffer.step_async(state,(cid%9,turn%9),0.,state,False,client_id=cid,actor='dqn',horizon=3)
                    self.assertEqual(batcher.infer(state,0.,locked_fire=turn%9),(8,turn%9,False))
        try:
            with trace.capture(recorder):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    for future in [pool.submit(actor,cid) for cid in range(8)]:future.result(timeout=5)
                self.assertTrue(buffer.barrier_async().wait(2))
        finally:batcher.stop();buffer.stop()
        snapshot=recorder.snapshot();report=trace.validate_snapshot(snapshot)
        self.assertEqual(report['accepted_ring_add_events'],32)
        self.assertEqual(report['inference_requests'],32)
        self.assertEqual(report['pending_routes'],0)
        for row in snapshot['frames']:
            self.assertEqual(row['commands'][0]['metadata']['client_id'],row['connection'][0])
            self.assertEqual(len(row['commands']),1)
            self.assertEqual(len(row['inference']),1)
        self.assertEqual(report['capture_loss'],dict(capacity_drops=0,event_drops=0,child_drops=0,faults=0))

    def test_sparse_sampling_is_not_reported_as_unmatched_inference(self):
        agent=self.Agent();batcher=self.classes['AsyncInferenceBatcher'](agent,max_wait_ms=0,request_timeout_ms=2000)
        recorder=trace.Recorder(sample_every=3)
        try:
            with trace.capture(recorder):
                connection=trace.connection(1,1)
                for _ in range(10):
                    with trace.frame(connection):batcher.infer([0.,0.,0.,0.],0.)
        finally:batcher.stop()
        report=trace.validate_snapshot(recorder.snapshot())
        self.assertEqual(report['sampled_frames'],4)
        self.assertEqual(report['inference_requests'],4)
        self.assertEqual(report['unmatched_inference'],0)

    def test_queue_backpressure_is_visible_before_inference(self):
        base=self.Agent;entered=threading.Event();release=threading.Event();full=threading.Event()
        class Blocked(base):
            def step(self,*args,**kwargs):
                entered.set()
                if not release.wait(3):raise RuntimeError('Test synchronization expired')
                return super().step(*args,**kwargs)
        class ObservedQueue(queue.Queue):
            def put(self,*args,**kwargs):
                try:return super().put(*args,**kwargs)
                except queue.Full:full.set();raise
        # Only the exact class's Queue constructor is intercepted, not service
        # controls or a separate dependency instance.
        node=next(n for n in ast.parse(self.proposed['socket_server']).body if isinstance(n,ast.ClassDef) and n.name=='AsyncReplayBuffer')
        scope=extract([node],dict(queue=types.SimpleNamespace(Queue=ObservedQueue,Full=queue.Full,Empty=queue.Empty),
            threading=threading,time=time,deque=deque,RL_CONFIG=types.SimpleNamespace(),_request_trace=trace))
        agent=Blocked();buffer=scope['AsyncReplayBuffer'](agent,batch_size=1,max_queue_size=1);recorder=self.recorder()
        state=[1.,2.,3.,4.]
        def submit_frame(cid):
            with trace.frame(trace.connection(cid,cid)):
                buffer.step_async(state,(1,2),0.,state,False,client_id=cid,actor='dqn')
        with trace.capture(recorder):
            with ThreadPoolExecutor(max_workers=1) as pool:
                try:
                    submit_frame(1);self.assertTrue(entered.wait(1));submit_frame(2)
                    third=pool.submit(submit_frame,3);self.assertTrue(full.wait(1));self.assertFalse(third.done())
                finally:release.set()
                third.result(timeout=2)
            self.assertTrue(buffer.barrier_async().wait(2));buffer.stop()
        snapshot=recorder.snapshot();self.assertEqual(trace.validate_snapshot(snapshot)['accepted_ring_add_events'],3)
        third=next(row for row in snapshot['frames'] if row['connection'][0]==3)
        events={p:t for p,t,m in third['commands'][0]['events']}
        self.assertGreater(events['enqueue_succeeded']-events['enqueue_attempt'],0)
        self.assertEqual(third['inference'],[])

    def test_consumer_failure_is_not_an_accepted_insert(self):
        class Failed(self.Agent):
            def step(self,*args,**kwargs):raise ArithmeticError('Injected matched consumer fault')
        buffer=self.classes['AsyncReplayBuffer'](Failed(),batch_size=1,max_queue_size=4);recorder=self.recorder()
        try:
            with trace.capture(recorder):
                with trace.frame(trace.connection(1,1)):
                    buffer.step_async([1.]*4,(1,2),0.,[1.]*4,False,client_id=1,actor='dqn')
                self.assertTrue(buffer.barrier_async().wait(2))
        finally:buffer.stop()
        snapshot=recorder.snapshot();report=trace.validate_snapshot(snapshot)
        self.assertEqual(report['accepted_ring_add_events'],0)
        self.assertIn('consumer_error',[p for p,t,m in snapshot['frames'][0]['commands'][0]['events']])

    def test_stopped_enqueue_return_does_not_claim_admission(self):
        buffer=self.classes['AsyncReplayBuffer'](self.Agent());buffer.stop();recorder=self.recorder()
        with trace.capture(recorder):
            with trace.frame(trace.connection(1,1)):
                buffer.step_async([1.]*4,(1,2),0.,[1.]*4,False,client_id=1,actor='dqn')
        snapshot=recorder.snapshot();report=trace.validate_snapshot(snapshot)
        self.assertEqual(report['pending_routes'],0)
        self.assertEqual(report['accepted_ring_add_events'],0)
        events=snapshot['frames'][0]['commands'][0]['events']
        self.assertEqual(events[-1][2],{'admitted':False})

    def test_stop_drain_keeps_command_identity_and_actual_insert_hooks(self):
        base=self.Agent;entered=threading.Event();release=threading.Event();drained=threading.Event()
        class Blocked(base):
            def step(self,state,*args,**kwargs):
                if state[0]==1:
                    entered.set()
                    if not release.wait(3):raise RuntimeError('Test synchronization expired')
                result=super().step(state,*args,**kwargs)
                if state[0]==2:drained.set()
                return result
        buffer=self.classes['AsyncReplayBuffer'](Blocked(),batch_size=1,max_queue_size=4);recorder=self.recorder()
        with trace.capture(recorder):
            with trace.frame(trace.connection(1,1)):
                buffer.step_async([1.]*4,(1,2),0.,[1.]*4,False,client_id=1,actor='dqn')
            self.assertTrue(entered.wait(1))
            with trace.frame(trace.connection(2,2)):
                buffer.step_async([2.]*4,(1,2),0.,[2.]*4,False,client_id=2,actor='dqn')
            with ThreadPoolExecutor(max_workers=1) as pool:
                stopped=pool.submit(buffer.stop)
                try:self.assertTrue(drained.wait(1))
                finally:release.set()
                stopped.result(timeout=3)
        report=trace.validate_snapshot(recorder.snapshot())
        self.assertEqual(report['accepted_ring_add_events'],2)
        self.assertEqual(report['pending_routes'],0)
        self.assertEqual(report['incomplete_admitted_commands'],0)

    def test_clock_fault_does_not_change_actions_or_CPU_ring_writes(self):
        def broken():raise OSError('Injected matched clock failure')
        recorder=self.recorder(clock=broken);agent=self.Agent()
        buffer=self.classes['AsyncReplayBuffer'](agent,max_queue_size=4)
        batcher=self.classes['AsyncInferenceBatcher'](agent,max_wait_ms=0,request_timeout_ms=2000)
        try:
            with trace.capture(recorder):
                with trace.frame(trace.connection(1,1)):
                    buffer.step_async([1.]*4,(1,2),0.,[1.]*4,False,client_id=1,actor='dqn')
                    self.assertEqual(batcher.infer([1.]*4,0.,locked_fire=7),(8,7,False))
                self.assertTrue(buffer.barrier_async().wait(2))
        finally:batcher.stop();buffer.stop()
        self.assertEqual(agent.memory._insert_exposure.snapshot()['accepted_total'],1)
        snapshot=recorder.snapshot();self.assertGreater(snapshot['faults'],0);self.assertEqual(snapshot['pending_routes'],0)

    def test_bounds_snapshot_detachment_and_nested_capture(self):
        recorder=self.recorder(max_frames=1,max_children=1,max_events=2)
        with trace.capture(recorder):
            with self.assertRaises(RuntimeError):
                with trace.capture(self.recorder()):pass
            connection=trace.connection(1,1)
            with trace.frame(connection):
                first=trace.new_request();trace.new_request()
                trace.mark(first,'extra1');trace.mark(first,'extra2')
            before=recorder.snapshot()
            with trace.frame(connection):pass
        snapshot=recorder.snapshot();self.assertEqual(before['capacity_drops'],0)
        self.assertEqual(snapshot['capacity_drops'],1)
        self.assertEqual(snapshot['child_drops'],1)
        self.assertEqual(snapshot['event_drops'],1)
        self.assertEqual(snapshot['pending_routes'],0)

    def test_body_exceptions_propagate_with_frame_closure(self):
        recorder=self.recorder()
        with trace.capture(recorder):
            with self.assertRaisesRegex(ArithmeticError,'same error'):
                with trace.frame(trace.connection(1,1)):raise ArithmeticError('same error')
        self.assertEqual([p for p,t,m in recorder.snapshot()['frames'][0]['events']],
                         ['handler_begin','handler_exception','handler_exit'])

    def test_real_handler_continue_and_EOF_paths_have_distinct_frame_scopes(self):
        node=builder.method(self.proposed['socket_server'],'handle_client','SocketServer')
        class Timer:
            def __init__(self,*a,**kw):pass
            def start(self):pass
        safe_threading=types.SimpleNamespace(Timer=Timer)
        metrics=types.SimpleNamespace(measurement_active=False,ratchet_note_eval_abandoned=lambda t:None)
        scope=extract([node],dict(_request_trace=trace,threading=safe_threading,socket=socket,struct=struct,
            time=time,sys=sys,traceback=traceback,metrics=metrics,_MAX_FRAME_PAYLOAD_BYTES=1024,
            WIRE_PARAMS_COUNT=4,CLIENT_IDLE_TIMEOUT_S=180.,parse_frame_data=lambda *a,**kw:None,_SRC_NONE=0))
        class Sock:
            def setblocking(self,*a):pass
            def setsockopt(self,*a):pass
            def sendall(self,data):self.sent=data
            def shutdown(self,*a):pass
            def close(self):pass
        server=types.SimpleNamespace(running=True,replay_enabled=True,shutdown_event=threading.Event(),
            _rejected_gaps=types.SimpleNamespace(event=lambda *a,**kw:None),
            client_lock=threading.RLock(),client_states={5:{}},_eval_override={},_unwrap_stash={},clients={5:True},
            _parse_client_handshake=lambda n:(False,7,0),_ensure_preview_client_selected_locked=lambda:(None,False),
            _preview_enabled_for_client=lambda cid:False,_hud_enabled_for_client=lambda cid:False,
            _is_preview_client=lambda cid:False,_pack_action=lambda *a,**kw:b'neutral',
            _sync_client_count_locked=lambda:None,game_journal=None,async_buffer=None,
            _fail_inference_only=lambda *a:None,_cleanup=lambda:None)
        payload=struct.pack('>H',4);responses=iter([b'\0\0',struct.pack('>I',len(payload)),payload,b''])
        def receive(*a,**kw):
            value=next(responses)
            if value==b'':server.shutdown_event.set()
            return value
        server._recv_exact=receive;recorder=self.recorder();sock=Sock()
        with trace.capture(recorder):scope['handle_client'](server,sock,5)
        snapshot=recorder.snapshot();self.assertEqual(sock.sent,b'neutral')
        self.assertEqual(len(snapshot['frames']),2)
        self.assertEqual([row['connection'][3] for row in snapshot['frames']],[1,2])
        self.assertEqual(snapshot['frames'][0]['connection'][:3],snapshot['frames'][1]['connection'][:3])
        phases=[{p for p,t,m in row['events']} for row in snapshot['frames']]
        self.assertTrue({'payload_complete','parse_begin','parse_end','handler_exit'}<=phases[0])
        self.assertTrue({'handler_exception','handler_exit'}<=phases[1])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and not any(n in sys.modules for n in ('dqn.agent','dqn.socket_server','dqn.replay_buffer'))
    print(json.dumps(dict(schema='robotron-matched-frame-CPU-contracts-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        torch_imported=False,production_modules_imported=False,live_source_modified=False,
        scope='CPU arrays and index/tensor shims; selected exact classes/methods only. No live parser, GPU, replay bank or MAME workload.')))
    sys.exit(0 if result.wasSuccessful() else 1)
