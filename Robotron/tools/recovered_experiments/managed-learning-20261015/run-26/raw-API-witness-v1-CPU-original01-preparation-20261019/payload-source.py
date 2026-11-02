import sys,unittest,json,os,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'immutable'))
suite=unittest.defaultTestLoader.loadTestsFromName('test_raw_api_witness_v1')
r=unittest.TextTestRunner(verbosity=2).run(suite)
assert 'torch' not in sys.modules
report=dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests_run=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),cuda_initialized=False,real_GPU_MAME_or_live_actions=False,observer_integration_complete=False,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).parent/'immutable').glob('*.py')},observed_unix_s=time.time())
with Path(__file__).with_name('CPU-report.json').open('x') as f:
 json.dump(report,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
raise SystemExit(0 if r.wasSuccessful() else 1)
