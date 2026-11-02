import argparse,hashlib,importlib.util,json,os,sys,time,unittest
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
if not a.execute:print('PLAN_ONLY');raise SystemExit(0)
assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;j=json.loads(raw);assert not Path(j['output']).exists()
for e in j['pins']:assert hashlib.sha256(Path(e['path']).read_bytes()).hexdigest()==e['sha256']
s=importlib.util.spec_from_file_location('_new2259_protection_guards',j['test']['path']);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
r=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(m))
assert 'torch'not in sys.modules
for e in j['pins']:assert hashlib.sha256(Path(e['path']).read_bytes()).hexdigest()==e['sha256']
report=dict(status='PASS'if r.wasSuccessful()else'FAIL',tests_run=r.testsRun,failures=len(r.failures),errors=len(r.errors),main_runtime_changed=False,actual_production_policy_publication=False,actual_scientific_review_rerun=False,synthetic_temporary_receipts_and_copies_only=True,quality_qualified=False,promotion=False,created_unix_s=time.time())
with Path(j['output']).open('x')as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
print(json.dumps(report),flush=True);raise SystemExit(0 if r.wasSuccessful()else 1)
