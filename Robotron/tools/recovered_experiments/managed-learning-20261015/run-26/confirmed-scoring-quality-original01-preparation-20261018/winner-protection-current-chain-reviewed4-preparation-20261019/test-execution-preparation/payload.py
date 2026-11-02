import sys,unittest,importlib,json,os
from pathlib import Path
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/confirmed_game_boundary_proposal'+'/quality_integration_reviewed4')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/confirmed_game_boundary_proposal')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/confirmed_game_boundary_proposal'+'/optional_expert_warning_proposal')
p=importlib.import_module('protect_confirmed_winner_reviewed4')
sys.modules['protect_confirmed_winner_reviewed3']=p
sys.modules['protect_confirmed_winner']=p
sys.modules['protect_confirmed_winner_reviewed2']=p
suite=unittest.defaultTestLoader.loadTestsFromNames(['Robotron.tools.test_protect_quality_winner','test_confirmed_protection','test_confirmed_protection_archives','test_current_chain_protection','test_polling_recovery_protection'])
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert 'torch' not in sys.modules
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),Torch_imported=False,quality_qualified=False,promotion=False)
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/winner-protection-current-chain-reviewed4-preparation-20261019/test-execution-preparation/CPU-report.json').open('x') as f:
 json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
raise SystemExit(0 if result.wasSuccessful() else 1)
