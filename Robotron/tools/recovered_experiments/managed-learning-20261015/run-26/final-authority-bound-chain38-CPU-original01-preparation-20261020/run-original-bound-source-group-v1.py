"""Bound original source-binding regressions; no actual cohort or publication."""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import time
import unittest
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
H=G/'tools/quality_capacity_proposal'
GROUPS=dict(campaign9=('test_prepare_quality32_campaign_v5',9),monitor18=('test_monitor_supervised_quality32_v3',18),monitor_preparation11=('test_prepare_supervised_quality32_monitor_v3',11))
def main():
    p=argparse.ArgumentParser();p.add_argument('--group',choices=GROUPS,required=True);a=p.parse_args()
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    time.sleep(2)
    sys.path[:0]=[str(H),str(G/'logs/managed-learning-20261015/run-26/supervised-quality32-chain-CPU-original01-preparation-20261019/immutable'),str(H/'profile03')]
    name,count=GROUPS[a.group];m=importlib.import_module(name)
    suite=unittest.defaultTestLoader.loadTestsFromModule(m);ids=[]
    def collect(s):
        for test in s:
            if isinstance(test,unittest.TestSuite):collect(test)
            else:ids.append(test.id())
    collect(suite);assert suite.countTestCases()==count and len(ids)==len(set(ids))==count
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    assert 'torch' not in sys.modules and not any(n.startswith('dqn.') for n in sys.modules)
    value=dict(schema='robotron-final-authority-bound-chain-CPU-group-v1',group=a.group,tests=result.testsRun,loaded_count=count,selected_tests=ids,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),successful=result.wasSuccessful() and not result.skipped,CUDA_hidden=True,numerical_runtime_imported=False,actual_quality_run=False,actual_policy_publication=False)
    print(json.dumps(value),flush=True)
    return 0 if value['successful'] else 1
if __name__=='__main__':raise SystemExit(main())
