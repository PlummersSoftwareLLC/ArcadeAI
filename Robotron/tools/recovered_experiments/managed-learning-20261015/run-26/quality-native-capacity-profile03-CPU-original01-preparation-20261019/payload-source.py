import os,sys,unittest,json,subprocess,time
from pathlib import Path
os.chdir('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/profile03')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/profile03')
from Robotron.tools import run_frozen_sidecar
assert str(Path(run_frozen_sidecar.__file__).resolve()).startswith('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/profile03'+'/Robotron/')
# Reproduce the prior prototype's false acceptance on synthetic originals.
baseline_code = '''import sys,json
sys.path.insert(0,OLD_ROOT)
from Robotron.tools.test_run_quality_campaign import Campaign32Tests
case=Campaign32Tests('test_nested_full_tail_unequal_counts_are_all_used_and_receipts_unchanged')
case.setUp()
try:
 case.fill()
 report=case.assess()
 data=json.load(open(case.plan['legs'][1]['receipt_path']))
 rows=data['cohort']['rows']
 result=dict(status='REPRODUCED',synthetic=True,actual_GPU=False,actual_MAME=False,declared_actors=32,distinct_slots=len({r['client_slot'] for r in rows}),distinct_clients=len({r['client_id'] for r in rows}),qualified_improvement=report['qualified_improvement'])
 assert result['distinct_slots']==32 and result['distinct_clients']==16 and result['qualified_improvement']
 print(json.dumps(result))
finally:case.doCleanups()
'''.replace('OLD_ROOT',repr('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/profile01'))
baseline_child=subprocess.run(['/usr/bin/python3.12','-I','-B','-c',baseline_code],capture_output=True,text=True,timeout=45)
assert baseline_child.returncode==0,baseline_child.stderr
baseline=json.loads(baseline_child.stdout)
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality-native-capacity-profile03-CPU-original01-preparation-20261019/prior-native32-fixture-diagnostic.json').open('x') as stream:
 json.dump(baseline,stream,indent=2);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())

class CapturedResult(unittest.TextTestResult):
 def addError(self,test,err):
  if isinstance(err[1],subprocess.CalledProcessError):
   for label in ('stdout','stderr'):
    value=getattr(err[1],label,None)
    if value:self.stream.write(label+': '+(value.decode(errors='replace') if isinstance(value,bytes) else value)+'\n')
  super().addError(test,err)
suite=unittest.defaultTestLoader.loadTestsFromNames(['Robotron.tools.test_compare_frozen_measurements', 'Robotron.tools.test_compare_sidecar_measurements', 'Robotron.tools.test_run_quality_campaign', 'Robotron.tools.test_frozen_sidecar', 'Robotron.tools.test_confirmed_quality_readback', 'Robotron.Scripts.dqn.test_game_journal', 'Robotron.tools.test_eval_capacity'])
result=unittest.TextTestRunner(verbosity=2,resultclass=CapturedResult).run(suite)
cuda_initialized='torch' in sys.modules and sys.modules['torch'].cuda.is_initialized()
assert not cuda_initialized,'CPU proposal validation acquired CUDA'
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),cuda_initialized=cuda_initialized,real_GPU_or_MAME_launched=False,quality_qualified=False,promotion=False,observed_unix_s=time.time(),package_manifest_sha256='40a9fc7148764623c723dc9b8f3ae2368ee5a4c29a39e353e3975371c79d04a1',prior_alias_diagnostic=baseline)
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality-native-capacity-profile03-CPU-original01-preparation-20261019/CPU-report.json').open('x') as f:
 json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
sys.exit(0 if result.wasSuccessful() else 1)
