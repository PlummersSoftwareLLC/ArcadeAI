import sys,unittest,json,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'immutable'))
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in ['test_monitor_supervised_quality32_v1','test_prepare_supervised_quality32_monitor_v1'])
count=suite.countTestCases();result=unittest.TextTestRunner(verbosity=2).run(suite)
assert 'torch' not in sys.modules and 'numpy' not in sys.modules
report=dict(passed=result.wasSuccessful(),tests_run=result.testsRun,loaded_cases=count,failures=len(result.failures),errors=len(result.errors),real_private_or_quality_services=False)
with Path(__file__).with_name('actual-test-result.json').open('x') as f:
 json.dump(report,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
sys.exit(0 if result.wasSuccessful() and result.testsRun==29 else 1)
