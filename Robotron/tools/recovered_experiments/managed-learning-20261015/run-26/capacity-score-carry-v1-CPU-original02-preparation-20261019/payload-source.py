import os,sys,unittest,json,subprocess,time
from pathlib import Path
os.chdir('/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile05')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile05')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/confirmed_game_boundary_proposal')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/capacity-score-carry-v1-CPU-original02-preparation-20261019/immutable')
from Robotron.tools import run_frozen_sidecar
assert str(Path(run_frozen_sidecar.__file__).resolve()).startswith('/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile05'+'/Robotron/')
class CapturedResult(unittest.TextTestResult):
 def addError(self,test,err):
  if isinstance(err[1],subprocess.CalledProcessError):
   for label in ('stdout','stderr'):
    value=getattr(err[1],label,None)
    if value:self.stream.write(label+': '+(value.decode(errors='replace') if isinstance(value,bytes) else value)+'\n')
  super().addError(test,err)
first_names=['Robotron.tools.test_compare_frozen_measurements','Robotron.tools.test_compare_sidecar_measurements','Robotron.tools.test_run_quality_campaign','Robotron.tools.test_frozen_sidecar','Robotron.tools.test_confirmed_quality_readback','Robotron.Scripts.dqn.test_game_journal','Robotron.tools.test_eval_capacity','test_audit_pilot_evidence']
first=unittest.TextTestRunner(verbosity=2,resultclass=CapturedResult).run(unittest.defaultTestLoader.loadTestsFromNames(first_names))
assert first.testsRun==104
helper_report=dict(status='PASS' if first.wasSuccessful() else 'FAIL',tests_run=first.testsRun,failures=len(first.failures),errors=len(first.errors),skipped=len(first.skipped),cuda_initialized=False,real_GPU_or_MAME_launched=False,quality_qualified=False,promotion=False,scope='First104 actual cases of this original172-case CPU run; no cases repeated.',source_sha256=__import__('hashlib').sha256(Path(__file__).with_name('immutable').joinpath('audit_pilot_evidence.py').read_bytes()).hexdigest())
with Path(__file__).with_name('helper-CPU-report.json').open('x') as f:
 json.dump(helper_report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
rest=unittest.TextTestRunner(verbosity=2,resultclass=CapturedResult).run(unittest.defaultTestLoader.loadTestsFromNames(['test_review_original_pilot_inflight_v1','test_pilot_runtime_guard_inflight_v1','test_inflight_observer_policy','test_score_carry_readiness']))
class Combined:
 testsRun=first.testsRun+rest.testsRun
 failures=first.failures+rest.failures
 errors=first.errors+rest.errors
 skipped=first.skipped+rest.skipped
 @staticmethod
 def wasSuccessful():return first.wasSuccessful() and rest.wasSuccessful()
result=Combined()
cuda_initialized='torch' in sys.modules and sys.modules['torch'].cuda.is_initialized()
assert not cuda_initialized,'CPU proposal validation acquired CUDA'
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),source_sha256={str(p):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/capacity-score-carry-v1-CPU-original02-preparation-20261019/immutable').glob('*.py')},cuda_initialized=cuda_initialized,real_GPU_or_MAME_launched=False,quality_qualified=False,promotion=False,observed_unix_s=time.time())
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/capacity-score-carry-v1-CPU-original02-preparation-20261019/CPU-report.json').open('x') as f:
 json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
sys.exit(0 if result.wasSuccessful() else 1)
