import sys,unittest,importlib,json,os
from pathlib import Path
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/confirmed_game_boundary_proposal')
sys.path.insert(0,'/home/dave/source/repos/ArcadeAI/Robotron/tools/confirmed_game_boundary_proposal'+'/optional_expert_warning_proposal')
a=importlib.import_module('audit_confirmed_completed_leg_reviewed3')
w=importlib.import_module('watch_confirmed_quality_audits_reviewed4')
for name in ('audit_confirmed_completed_leg','audit_confirmed_completed_leg_reviewed2'):sys.modules[name]=a
sys.modules['watch_confirmed_quality_audits']=w
suite=unittest.defaultTestLoader.loadTestsFromNames(['test_confirmed_audit','test_confirmed_audit_watcher.OriginalLegTests','test_rom_terminal_audit','test_optional_warning_review3','test_observer_read_recovery'])
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert 'torch' not in sys.modules
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),Torch_imported=False,quality_qualified=False,promotion=False)
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/observer-read-stability-recovery-original01-20261019/CPU-original01/CPU-report.json').open('x') as f:
 json.dump(report,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
raise SystemExit(0 if result.wasSuccessful() else 1)
