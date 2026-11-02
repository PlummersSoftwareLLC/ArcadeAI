import os,sys,unittest,json,time,hashlib
from pathlib import Path
sys.path[:0]=['/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-evidence-v1-CPU-original01-preparation-20261019/immutable','/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/profile03']
expected={'/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-evidence-v1-CPU-original01-preparation-20261019/immutable/audit_quality32_evidence_v1.py': '5b8388c5a8aa37979209c89c14a91d015f65f6463e975947c42042dfed611a33', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-evidence-v1-CPU-original01-preparation-20261019/immutable/test_audit_quality32_evidence_v1.py': '1edda5e6a61ff337dfda1cd4aa7dbf184332b9a3185fcb4840453a963ed2d690', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-evidence-v1-CPU-original01-preparation-20261019/immutable/audit_pilot_evidence.py': 'bb93048c6cee1e844e72b0baa5bb8a7c1c9d18f838d16e28e4cc40913e97ad1a', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-evidence-v1-CPU-original01-preparation-20261019/immutable/audit_confirmed_completed_leg_reviewed3.py': 'de901669780868cb842e9c9068ce11261a1d1f359c1940bb5bba6b2646c37ade', '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-evidence-v1-CPU-original01-preparation-20261019/immutable/test_audit_pilot_evidence.py': '4aae02642e19f59bda8934f1357c4625f0ba5b05c8cd04e8ed1ebc65f8150414'}
for path,sha in expected.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
seen=[]
class Recorded(unittest.TextTestResult):
 def startTest(self,test):
  seen.append(test.id());super().startTest(test)
suite=unittest.defaultTestLoader.loadTestsFromName('test_audit_quality32_evidence_v1')
result=unittest.TextTestRunner(verbosity=2,resultclass=Recorded).run(suite)
assert len(set(seen))==len(seen)
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),test_ids=seen,source_sha256=expected,cuda_initialized=False,numerical_runtime_imported='torch' in sys.modules,real_GPU_or_MAME_launched=False,quality_qualified=False,promotion=False,root_auditor_integration_complete=False,observed_unix_s=time.time())
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-evidence-v1-CPU-original01-preparation-20261019/CPU-report.json').open('x') as stream:
 json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
sys.exit(0 if result.wasSuccessful() and 'torch' not in sys.modules else 1)
