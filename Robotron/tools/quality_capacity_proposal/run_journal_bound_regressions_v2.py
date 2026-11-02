"""Original CPU integration tests for the prospective journal package bindings."""
import argparse
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
H=G/'tools/quality_capacity_proposal'
GROUPS={
 'review':('test_journal_bound_closed_review_v1',6),
 'acquisition':('test_journal_bound_acquisition_v1',19),
 'cohorts':('test_journal_bound_cohorts_v1',28),
 'CPU_preparation':('test_journal_bound_CPU_preparation_v1',11),
 'protection':('test_journal_bound_protection_v1',10),
 'campaign':('test_journal_bound_campaign_v1',9),
 'monitor':('test_journal_bound_monitor_v1',18),
 'monitor_preparation':('test_journal_bound_monitor_preparation_v1',11),
}


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


class OriginalROMGuardTests(unittest.TestCase):
    def test_existing_final_ROM_guard_also_rejects_actual_ambiguous_reset(self):
        auditor=load('journal_bound_actual_ROM_guard',G/'tools/confirmed_game_boundary_proposal/audit_confirmed_completed_leg_reviewed3.py')
        fixture=self.fixture
        with self.assertRaisesRegex(ValueError,'exhausted ROM reserve counter'):
            auditor.validate_rom_terminal(fixture['game149'],fixture['successor_start160'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--job-sha256',required=True);args=p.parse_args()
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    rp=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    assert hashlib.sha256(rp.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
    reader=load('journal_bound_cpu_reader',rp)
    inputs={x['path']:x for x in job['inputs']}
    assert len(inputs)==len(job['inputs'])
    for item in inputs.values():reader.read_pin(item,as_json=False)
    assert reader.pin(Path(__file__))==inputs[str(Path(__file__))]
    sys.path[:0]=[str(H),str(G/'logs/managed-learning-20261015/run-26/supervised-quality32-chain-CPU-original01-preparation-20261019/immutable'),str(H/'profile05')]
    suite=unittest.TestSuite();names=[];counts={}
    for group,(module,count) in GROUPS.items():
        loaded=unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(module))
        assert loaded.countTestCases()==count,(group,loaded.countTestCases())
        suite.addTest(loaded);counts[group]=count
    OriginalROMGuardTests.fixture=reader.read_pin(job['fixture'])
    suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(OriginalROMGuardTests));counts['unchanged_final_ROM']=1
    def collect(s):
        for test in s:
            if isinstance(test,unittest.TestSuite):collect(test)
            else:names.append(test.id())
    collect(suite)
    assert len(names)==len(set(names))==job['expected_tests']==113
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    modules={}
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if path and Path(path).is_relative_to(G) and Path(path).suffix=='.py':
            resolved=str(Path(path).resolve())
            assert resolved in inputs,('Unbound imported source',name,resolved)
            modules[name]=inputs[resolved]
    for item in inputs.values():reader.read_pin(item,as_json=False)
    assert 'torch' not in sys.modules and 'numpy' not in sys.modules
    report=dict(status='PASS' if result.wasSuccessful() and not result.skipped else 'FAIL',tests=result.testsRun,
        groups=counts,selected_tests=names,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        imported_modules=modules,all_imported_repository_sources_bound=True,all_inputs_unchanged=True,
        CUDA_hidden=True,numerical_runtime_imported=False,actual_quality_run=False,
        production_policy_published=False,synthetic_protection_publication_tested=True,
        original_scientific_review_retried=False,source_selected_for_science=False)
    print(json.dumps(report),flush=True)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
