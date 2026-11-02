import sys,json,os,time,unittest,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'immutable'),'/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/profile03']
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
precommit=json.loads((ROOT/'source-copy-and-test-group-precommit.json').read_text())
for row in precommit['sources']:
 for entry in row.values():
  assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256']
group=sys.argv[1];selected=precommit['groups'][group]
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in selected)
count=suite.countTestCases();started=time.monotonic()
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert 'torch' not in sys.modules and 'numpy' not in sys.modules
for row in precommit['sources']:
 for entry in row.values():
  assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256']
report=dict(group=group,actual_tests_run=result.testsRun,loaded_test_count=count,passed=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors),elapsed_s=time.monotonic()-started,selected_tests=selected,synthetic_quality_and_model_metadata_only=True,live_readonly_main_preflight=group=='A',actual_quality_run=False,actual_policy_publication=False)
p=ROOT/('group-'+group+'-actual-test-result.json')
with p.open('x') as stream:
 json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
sys.exit(0 if result.wasSuccessful() and result.testsRun==count else 1)
