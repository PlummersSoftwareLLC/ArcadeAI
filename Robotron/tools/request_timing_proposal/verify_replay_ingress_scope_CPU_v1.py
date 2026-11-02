"""CPU mechanism checks for the gap before inference timing. Inert by default.

Extract only the exact AsyncReplayBuffer class. Never import the live module,
connect to the trainer, access a replay bank or launch/signals services.
"""
import argparse
import ast
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
import time
import types
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
SOURCE=G/'Scripts/dqn/socket_server.py'
SOURCE_SHA='84901c887437e99873d65c2348f18ca9e2f022a393f3c5282d68064c9f1fbf40'


def extract(queue_type=queue.Queue):
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:
        raise ValueError('Exact held source required')
    node=next(n for n in ast.parse(raw).body if isinstance(n,ast.ClassDef) and n.name=='AsyncReplayBuffer')
    namespace=dict(queue=types.SimpleNamespace(Queue=queue_type,Full=queue.Full,Empty=queue.Empty),
        threading=threading,time=time,deque=deque,RL_CONFIG=types.SimpleNamespace(),
        metrics=types.SimpleNamespace(note_replay_drop=lambda n: None))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<extracted-AsyncReplayBuffer>','exec'),namespace)
    return namespace['AsyncReplayBuffer']


class Agent:
    def __init__(self,blocked=False,fail=None):
        self.entered=threading.Event();self.release=threading.Event()
        self.blocked,self.fail=blocked,fail
        self.calls=[];self.accepted=[]
    def step(self,value,**kwargs):
        if self.blocked and value==1:
            self.entered.set()
            if not self.release.wait(3):
                raise RuntimeError('Test synchronization expired')
        self.calls.append((value,kwargs))
        if value==self.fail:
            raise ArithmeticError('Injected CPU consumer failure')
        self.accepted.append(value)
        return len(self.accepted)-1


class Tests(unittest.TestCase):
    def test_full_queue_blocks_before_inference_and_preserves_FIFO_metadata(self):
        retried=threading.Event()
        class ObservedQueue(queue.Queue):
            def put(self,item,block=True,timeout=None):
                try:return super().put(item,block=block,timeout=timeout)
                except queue.Full:
                    if item[0]=='step' and item[2][0]==3:retried.set()
                    raise
        agent=Agent(blocked=True);buffer=extract(ObservedQueue)(agent,batch_size=1,max_queue_size=1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            try:
                buffer.step_async(1,client_id=5,actor='dqn',horizon=3)
                self.assertTrue(agent.entered.wait(1))
                buffer.step_async(2,client_id=5,actor='epsilon',horizon=3)
                self.assertEqual(buffer.queue.qsize(),1)
                third=pool.submit(buffer.step_async,3,client_id=5,actor='dqn',horizon=2)
                self.assertTrue(retried.wait(1),'Exact put(timeout=.1) must encounter a full queue')
                self.assertFalse(third.done())
                self.assertEqual(agent.accepted,[])
            finally:
                agent.release.set()
            third.result(timeout=2)
            self.assertTrue(buffer.barrier_async().wait(2))
            buffer.stop()
        self.assertEqual(agent.accepted,[1,2,3])
        self.assertEqual(agent.calls,[(1,dict(actor='dqn',horizon=3)),
            (2,dict(actor='epsilon',horizon=3)),(3,dict(actor='dqn',horizon=2))])
        self.assertEqual(buffer.dropped_steps,0)
        self.assertEqual(list(buffer._client_indices[5]),[0,1,2])

    def test_enqueue_return_does_not_prove_replay_acceptance(self):
        agent=Agent(blocked=True);buffer=extract()(agent,batch_size=1,max_queue_size=2)
        try:
            self.assertIsNone(buffer.step_async(1,client_id=5,actor='dqn'))
            self.assertTrue(agent.entered.wait(1))
            self.assertEqual(agent.accepted,[])
            self.assertIsNone(buffer.step_async(2,client_id=5,actor='epsilon'))
            self.assertEqual(agent.accepted,[])
        finally:
            agent.release.set()
        self.assertTrue(buffer.barrier_async().wait(2));buffer.stop()
        self.assertEqual(agent.accepted,[1,2])

    def test_consumer_error_continues_and_is_not_an_accepted_insert(self):
        agent=Agent(fail=1);buffer=extract()(agent,batch_size=1,max_queue_size=8)
        try:
            for value in [1,2,3]:buffer.step_async(value,client_id=5,actor='dqn')
            self.assertTrue(buffer.barrier_async().wait(2))
        finally:buffer.stop()
        self.assertEqual([v for v,kw in agent.calls],[1,2,3])
        self.assertEqual(agent.accepted,[2,3])
        self.assertEqual(list(buffer._client_indices[5]),[0,1])

    def test_reset_ack_waits_for_prior_commands_and_clears_indices(self):
        agent=Agent(blocked=True);buffer=extract()(agent,batch_size=1,max_queue_size=8)
        try:
            buffer.step_async(1,client_id=5,actor='dqn')
            self.assertTrue(agent.entered.wait(1))
            ack=buffer.reset_client_async(5)
            self.assertFalse(ack.is_set())
        finally:agent.release.set()
        self.assertTrue(ack.wait(2));buffer.stop()
        self.assertEqual(agent.accepted,[1])
        self.assertNotIn(5,buffer._client_indices)
        self.assertNotIn(5,buffer._episode_indices)

    def test_stopped_producer_return_is_not_queue_admission(self):
        agent=Agent();buffer=extract()(agent,batch_size=1,max_queue_size=1)
        buffer.stop()
        self.assertIsNone(buffer.step_async(99,client_id=5,actor='dqn'))
        self.assertEqual(agent.accepted,[])
        self.assertTrue(buffer.queue.empty())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no source reads, extraction, threads, trainer connections or output files');return 0
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert 'torch' not in sys.modules and 'dqn.socket_server' not in sys.modules
    print(json.dumps(dict(schema='robotron-replay-ingress-scope-CPU-v1',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),successful=result.wasSuccessful(),
        source_sha256=SOURCE_SHA,live_queue_observed=False,production_changed=False,
        quality_gain_verified=False,learning_speed_gain_verified=False)))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':sys.exit(main())
