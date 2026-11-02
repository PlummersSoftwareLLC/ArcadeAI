import os,sys,json,time,unittest,hashlib
from pathlib import Path
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-acquisition-v1-CPU-original02-preparation-20261019/immutable')
expected={'/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-acquisition-v1-CPU-original02-preparation-20261019/immutable/quality32_acquisition_v1.py': 'f3dce1d0cba21e6a1efdf85e3350edd673a7515145ede338dbff1b4eb2d7fac4', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-acquisition-v1-CPU-original02-preparation-20261019/immutable/test_quality32_acquisition_v2.py': '9c518a2c94c933c70865b63a9c200f0595e0bcf471a04509894638c5d36f0d6e'}
for path,sha in expected.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
seen=[]
class Recorded(unittest.TextTestResult):
 def startTest(self,test):seen.append(test.id());super().startTest(test)
suite=unittest.defaultTestLoader.loadTestsFromName('test_quality32_acquisition_v2')
result=unittest.TextTestRunner(verbosity=2,resultclass=Recorded).run(suite)
assert len(set(seen))==len(seen)
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),test_ids=seen,source_sha256=expected,numerical_runtime_imported='torch' in sys.modules,cuda_initialized=False,real_GPU_or_MAME_launched=False,new_candidate_captured=False,quality_qualified=False,promotion=False,root_auditor_integration_complete=False,observed_unix_s=time.time())
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-acquisition-v1-CPU-original02-preparation-20261019/CPU-report.json').open('x') as stream:
 json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
sys.exit(0 if result.wasSuccessful() and 'torch' not in sys.modules else 1)
