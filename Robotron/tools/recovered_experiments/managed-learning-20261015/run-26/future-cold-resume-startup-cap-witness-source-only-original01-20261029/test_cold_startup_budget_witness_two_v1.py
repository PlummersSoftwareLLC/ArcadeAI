"""Two future CPU-only checks of the actual new read-only budget witness.

Explicitly synthetic scalar/config/process-environment collaborators. No full
restore, model/tensor/replay qualification; no selected module import, real
/proc read, service, socket, GPU or operator mode. Author has not run this file.
"""
import ast
import hashlib
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest

SOURCE=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-cold-resume-startup-cap-witness-source-only-original01-20261029/continuous_startup_bridge_cap_witness_v3.py')
SHA='47efc654e1a46f281a094b43a8e55802b5f76cbdb62e830b5769a2f6d6e790f4'

class SyntheticMemory:
    def __init__(self,size=6000000):self.size=size
    def __len__(self):return self.size

class SyntheticProcPath:
    wire=b''
    def __init__(self,path):
        if path!='/proc/self/environ':raise AssertionError('Unexpected real path in synthetic witness')
    def read_bytes(self):return type(self).wire

class ColdStartupBudgetWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw=SOURCE.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=SHA:raise AssertionError('Selected prototype source changed')
        tree=ast.parse(raw);wanted={'require','startup_budget_witness'}
        selected=[node for node in tree.body if isinstance(node,ast.FunctionDef)and node.name in wanted]
        if len(selected)!=2:raise AssertionError('Exact actual function inventory differs')
        cls.env={};cls.ns=dict(os=SimpleNamespace(environ=cls.env),Path=SyntheticProcPath)
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(SOURCE),'exec'),cls.ns)
        cls.actual=staticmethod(cls.ns['startup_budget_witness'])

    def harness(self,cap=8,anchor=None):
        self.env.clear();self.env['DQN_MAX_SAMPLES_PER_FRAME']=str(cap)
        SyntheticProcPath.wire=('DQN_MAX_SAMPLES_PER_FRAME='+str(cap)+'\0OTHER=synthetic\0').encode()
        agent=SimpleNamespace(optimized_samples=90000,loaded_optimized_samples=90000,
            memory=SyntheticMemory(),_replay_warmup_pending=False)
        if anchor is not None:agent._replay_pressure_anchor=anchor
        metrics=SimpleNamespace(lock=threading.Lock(),frame_count=50000,measurement_frame_count=7,
            loaded_frame_count=50000,loaded_measurement_frame_count=7,loaded_optimized_samples=90000)
        cfg=SimpleNamespace(max_samples_per_frame=float(cap),batch_size=4096,min_replay_to_train=4096)
        return agent,metrics,cfg

    def state(self,agent,metrics,cfg):
        return json.dumps(dict(agent={k:v for k,v in vars(agent).items()if k!='memory'},
            memory_size=len(agent.memory),metrics={k:v for k,v in vars(metrics).items()if k!='lock'},
            cfg=vars(cfg)),sort_keys=True)

    def test_actual_cap8_cap12_existing_baseline_is_read_only(self):
        for cap in (8,12):
            for anchor in (None,(50000,7,90000)):
                with self.subTest(cap=cap,anchor=anchor):
                    agent,metrics,cfg=self.harness(cap,anchor);before=self.state(agent,metrics,cfg)
                    result=self.actual(agent,metrics,cfg,cap)
                    self.assertEqual(result['expected_startup_cap'],cap)
                    self.assertEqual(result['runtime_cap'],float(cap))
                    self.assertTrue(result['fresh_per_boot_baseline_verified'])
                    self.assertFalse(result['anchor_installed_or_rebased'])
                    self.assertEqual(result['samples_since_loaded'],0)
                    self.assertEqual(result['unmeasured_frames_since_loaded'],0)
                    self.assertEqual(self.actual(agent,metrics,cfg,cap),result)
                    self.assertEqual(self.state(agent,metrics,cfg),before)

    def test_actual_missing_wrong_cap_and_stale_budget_rejected(self):
        for expected in (None,True,0,32,'12'):
            with self.subTest(expected=expected):
                a,m,c=self.harness()
                with self.assertRaises(RuntimeError):self.actual(a,m,c,expected)
        cases=('missing_initial_env','duplicate_initial_env','wrong_initial_env','wrong_current_env',
               'default32_runtime','wrong_runtime','loaded_sample_skew','current_measurement_skew',
               'agent_loaded_skew','wrong_local_anchor','warmup_pending','insufficient_replay')
        for case in cases:
            with self.subTest(case=case):
                a,m,c=self.harness()
                if case=='missing_initial_env':SyntheticProcPath.wire=b'OTHER=synthetic\0'
                elif case=='duplicate_initial_env':SyntheticProcPath.wire=b'DQN_MAX_SAMPLES_PER_FRAME=8\0DQN_MAX_SAMPLES_PER_FRAME=8\0'
                elif case=='wrong_initial_env':SyntheticProcPath.wire=b'DQN_MAX_SAMPLES_PER_FRAME=12\0'
                elif case=='wrong_current_env':self.env['DQN_MAX_SAMPLES_PER_FRAME']='12'
                elif case=='default32_runtime':c.max_samples_per_frame=32.
                elif case=='wrong_runtime':c.max_samples_per_frame=12.
                elif case=='loaded_sample_skew':m.loaded_optimized_samples-=4096
                elif case=='current_measurement_skew':m.measurement_frame_count+=1
                elif case=='agent_loaded_skew':a.loaded_optimized_samples-=4096
                elif case=='wrong_local_anchor':a._replay_pressure_anchor=(49999,7,90000)
                elif case=='warmup_pending':a._replay_warmup_pending=True
                elif case=='insufficient_replay':a.memory.size=4095
                before=self.state(a,m,c)
                with self.assertRaises(RuntimeError):self.actual(a,m,c,8)
                self.assertEqual(self.state(a,m,c),before)

if __name__=='__main__':unittest.main()
