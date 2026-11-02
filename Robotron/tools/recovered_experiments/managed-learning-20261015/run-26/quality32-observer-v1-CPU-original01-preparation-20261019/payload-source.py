import os,sys,json,time,unittest,hashlib
from pathlib import Path
sys.path[:0]=['/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-observer-v1-CPU-original01-preparation-20261019/immutable', '/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/profile03']
expected={'/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-observer-v1-CPU-original01-preparation-20261019/immutable/quality32_runtime_guard_v1.py': '4046360a32b087c89433de2f2b836c096c9b7ea79da19061955ed8b990f6698b', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-observer-v1-CPU-original01-preparation-20261019/immutable/control_quality32_review_v1.py': '218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-observer-v1-CPU-original01-preparation-20261019/immutable/test_quality32_runtime_guard_v1.py': '615f88b5a0009d43a98d874a2999359a6f12c8423536a45bc8c7d4844aa9f855'}
for path,sha in expected.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
seen=[]
class Recorded(unittest.TextTestResult):
 def startTest(self,test):seen.append(test.id());super().startTest(test)
suite=unittest.defaultTestLoader.loadTestsFromName('test_quality32_runtime_guard_v1')
result=unittest.TextTestRunner(verbosity=2,resultclass=Recorded).run(suite)
assert len(set(seen))==len(seen)
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),test_ids=seen,source_sha256=expected,numerical_runtime_imported='torch' in sys.modules,cuda_initialized=False,real_GPU_or_MAME_launched=False,new_candidate_captured=False,quality_qualified=False,promotion=False,prospective_observer_tested=True,external_quality_processes_mocked=True,real_own_CPU_process_identity_checked=True,actual_model_loaded=False,actual_policy_published=False,actual_quality_campaign_selected=False,full_observer_review_protection_integration_tested=False,observed_unix_s=time.time())
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-observer-v1-CPU-original01-preparation-20261019/CPU-report.json').open('x') as stream:
 json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
sys.exit(0 if result.wasSuccessful() and 'torch' not in sys.modules else 1)
