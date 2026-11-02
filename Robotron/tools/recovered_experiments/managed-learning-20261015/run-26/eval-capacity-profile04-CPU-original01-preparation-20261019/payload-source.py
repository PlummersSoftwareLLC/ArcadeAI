import os,sys,unittest,json,subprocess,time
from pathlib import Path
os.chdir('/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile04')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile04')
from Robotron.tools import run_frozen_sidecar
assert str(Path(run_frozen_sidecar.__file__).resolve()).startswith('/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/profile04'+'/Robotron/')
class CapturedResult(unittest.TextTestResult):
 def addError(self,test,err):
  if isinstance(err[1],subprocess.CalledProcessError):
   for label in ('stdout','stderr'):
    value=getattr(err[1],label,None)
    if value:self.stream.write(label+': '+(value.decode(errors='replace') if isinstance(value,bytes) else value)+'\n')
  super().addError(test,err)
suite=unittest.defaultTestLoader.loadTestsFromNames(['Robotron.tools.test_compare_frozen_measurements', 'Robotron.tools.test_compare_sidecar_measurements', 'Robotron.tools.test_run_quality_campaign', 'Robotron.tools.test_frozen_sidecar', 'Robotron.tools.test_confirmed_quality_readback', 'Robotron.Scripts.dqn.test_game_journal', 'Robotron.tools.test_eval_capacity', 'Robotron.Scripts.dqn.test_measurement_actor'])
result=unittest.TextTestRunner(verbosity=2,resultclass=CapturedResult).run(suite)
cuda_initialized='torch' in sys.modules and sys.modules['torch'].cuda.is_initialized()
assert not cuda_initialized,'CPU proposal validation acquired CUDA'
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),cuda_initialized=cuda_initialized,real_GPU_or_MAME_launched=False,quality_qualified=False,promotion=False,observed_unix_s=time.time())
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/eval-capacity-profile04-CPU-original01-preparation-20261019/CPU-report.json').open('x') as f:
 json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
sys.exit(0 if result.wasSuccessful() else 1)
