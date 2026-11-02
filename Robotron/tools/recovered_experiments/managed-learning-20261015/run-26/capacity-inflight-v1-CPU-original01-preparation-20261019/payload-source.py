import os,sys,unittest,json,subprocess,time
from pathlib import Path
os.chdir('/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile03')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile03')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/confirmed_game_boundary_proposal')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/capacity-inflight-v1-CPU-original01-preparation-20261019/immutable')
from Robotron.tools import run_frozen_sidecar
assert str(Path(run_frozen_sidecar.__file__).resolve()).startswith('/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile03'+'/Robotron/')
class CapturedResult(unittest.TextTestResult):
 def addError(self,test,err):
  if isinstance(err[1],subprocess.CalledProcessError):
   for label in ('stdout','stderr'):
    value=getattr(err[1],label,None)
    if value:self.stream.write(label+': '+(value.decode(errors='replace') if isinstance(value,bytes) else value)+'\n')
  super().addError(test,err)
suite=unittest.defaultTestLoader.loadTestsFromNames(['Robotron.tools.test_compare_frozen_measurements', 'Robotron.tools.test_compare_sidecar_measurements', 'Robotron.tools.test_run_quality_campaign', 'Robotron.tools.test_frozen_sidecar', 'Robotron.tools.test_confirmed_quality_readback', 'Robotron.Scripts.dqn.test_game_journal', 'Robotron.tools.test_eval_capacity','test_audit_pilot_evidence','test_review_original_pilot_inflight_v1','test_pilot_runtime_guard_inflight_v1','test_inflight_observer_policy'])
result=unittest.TextTestRunner(verbosity=2,resultclass=CapturedResult).run(suite)
cuda_initialized='torch' in sys.modules and sys.modules['torch'].cuda.is_initialized()
assert not cuda_initialized,'CPU proposal validation acquired CUDA'
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),source_sha256={str(p):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/capacity-inflight-v1-CPU-original01-preparation-20261019/immutable').glob('*.py')},cuda_initialized=cuda_initialized,real_GPU_or_MAME_launched=False,quality_qualified=False,promotion=False,observed_unix_s=time.time())
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/capacity-inflight-v1-CPU-original01-preparation-20261019/CPU-report.json').open('x') as f:
 json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
sys.exit(0 if result.wasSuccessful() else 1)
