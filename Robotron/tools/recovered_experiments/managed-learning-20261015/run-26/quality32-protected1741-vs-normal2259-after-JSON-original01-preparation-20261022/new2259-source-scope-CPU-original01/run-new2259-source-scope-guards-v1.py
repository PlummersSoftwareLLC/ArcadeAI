import argparse,hashlib,importlib.util,json,os,sys,time,unittest
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job');p.add_argument('--job-sha256');p.add_argument('--source-sha256');a=p.parse_args()
if not a.execute:print('PLAN_ONLY');raise SystemExit(0)
assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.source_sha256
raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;j=json.loads(raw);assert not Path(j['output']).exists()
for e in j['pins']:assert hashlib.sha256(Path(e['path']).read_bytes()).hexdigest()==e['sha256']
suite=unittest.TestSuite()
for i,e in enumerate(j['tests']):
 s=importlib.util.spec_from_file_location('_new2259_guards_'+str(i),e['path']);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(m))
r=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)
assert 'torch' not in sys.modules
for e in j['pins']:assert hashlib.sha256(Path(e['path']).read_bytes()).hexdigest()==e['sha256']
report=dict(schema='robotron-distinct2259-source-and-composed-scope-guards-v1',status='PASS' if r.wasSuccessful() else 'FAIL',tests_run=r.testsRun,failures=len(r.failures),errors=len(r.errors),tested_job=a.job,source_sha256=a.source_sha256,main_runtime_changed=False,scientific_cohort_launched=False,quality_qualified=False,promotion=False,created_unix_s=time.time())
with Path(j['output']).open('x')as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
print(json.dumps(report),flush=True);raise SystemExit(0 if r.wasSuccessful() else 1)
