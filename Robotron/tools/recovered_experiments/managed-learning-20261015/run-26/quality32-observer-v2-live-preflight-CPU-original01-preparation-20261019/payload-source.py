import json,os,sys,time,unittest,copy,hashlib,importlib.util
from pathlib import Path
sys.path[:0]=['/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-observer-integration-v2-CPU-original01-preparation-20261019/immutable', '/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/profile03']
import test_closed_quality32_full_path_v3 as fixtures
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
N=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/capacity32-confirmed1059-raw-API-v1-preparation-20261019')
source=G/'tools/quality_capacity_proposal/quality32_runtime_guard_v2.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='f17debdf0ce4954b2c28476b40e94c39b5423dd556e1fe6fd3e274008f0182cb'
spec=importlib.util.spec_from_file_location('_actual_readonly_preflight',source);observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
class Preflight(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.FullPathTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.reader=self.f.reader;original,entry,main=self.f.build();context=self.reader.read_pin(self.reader.pin(original['closed_context_path']))
  template=self.reader.read_pin(original['binding']);template.pop('campaign')
  suffix=str(time.time_ns());area=self.f.root/'prospective-preflight';area.mkdir()
  campaign=G/'logs/managed-learning-20261015'/('synthetic-quality32-preflight-unused-'+suffix)
  self.addCleanup(lambda:self.assertFalse(campaign.exists()))
  config=dict(unit='robotron-quality32-preflight-synthetic-native-'+suffix+'.service',output=str(area/'native-execution'),
   properties=['CPUQuota=1200%','MemoryMax=12G','MemorySwapMax=0','RuntimeMaxSec=29400','TasksMax=512','TimeoutStopSec=120','KillMode=mixed','SendSIGKILL=no'],
   pins=[],observation_s=30000,guard_source=self.reader.pin(source))
  self.job=dict(schema='robotron-original-quality32-control-job-v1',reviewer_source=self.reader.pin(observer.REVIEWER),
   review_controller_source=self.reader.pin(observer.HERE/'control_quality32_review_v1.py'),
   capacity_review=self.reader.pin(N/'independent-original32-pilot-review/review.json'),preceding_originals=[
    dict(owner=self.reader.pin(N/(name+'-execution/root-original-live-owner.json')),
     closure=self.reader.pin(N/(name+'-execution/native-terminal-archive/root-original-result-and-owned-release.json')))
     for name in ('pilot-root','outer-controller')],binding_template=self.f.put(area/'binding-template.json',template),
   main_binding=context['main_binding'],main_guard_source=original['main_guard_source'],
   binding_directory=str(area/'bindings'),review_output=str(area/'review'),review_execution=str(area/'review-execution'),
   review_unit='robotron-quality32-preflight-synthetic-review-'+suffix+'.service',
   binary_inputs=[self.reader.pin(G/'roms/robotron.zip'),self.reader.pin(Path('/usr/games/mame'))],
   lease_path=original['lease_path'],lease_identity=original['lease_identity'],launch_pins=[],
   campaign_parameters=dict(directory=str(campaign),reference_label='synthetic-reference',candidate_label='synthetic-candidate',
    hypothesis='Read-only live preflight with synthetic phase metadata; no evaluation selection or model verification.',
    boot_assets=str(G/'logs/managed-learning-20261015/sidecar-boot-assets-v1')))
  config['argv']=observer.campaign_command(self.job,template)
  self.config=config;self.area=area
 def prepare(self):
  self.config['pilot_controller_job']=self.f.put(self.area/'control-job.json',self.job)
  entry=self.f.put(self.area/'native-config.json',self.config)
  return observer.prepare(self.config,entry)
 def test_full_preflight_real_main192_closed_capacity_idle_GPU_no_launch(self):
  guard=self.prepare();guard.validate_config(self.config);guard.before_scheduling()
  self.assertEqual(len(guard.main['actors']),192);self.assertEqual(len(guard.main['held_hashes']),193)
  self.assertEqual(len(guard.samples),2);self.assertIsNone(guard.identity);self.assertFalse(guard.births)
  self.assertFalse(Path(self.config['output']).exists());self.assertFalse(Path(self.job['review_execution']).exists())
  self.assertTrue((self.area/'bindings/main-binding.json').exists())
  self.assertNotIn('torch',sys.modules)
 def test_missing_original_capacity_review_rejects_before_output(self):
  self.job['capacity_review']=dict(path=str(self.area/'missing-original-review.json'))
  with self.assertRaises((FileNotFoundError,KeyError)):self.prepare()
  self.assertFalse((self.area/'bindings').exists());self.assertFalse(Path(self.config['output']).exists())
seen=[]
class Recorded(unittest.TextTestResult):
 def startTest(self,test):seen.append(test.id());super().startTest(test)
result=unittest.TextTestRunner(verbosity=2,resultclass=Recorded).run(unittest.defaultTestLoader.loadTestsFromTestCase(Preflight))
report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),test_ids=seen,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),observed_unix_s=time.time(),actual_main192_and193_holds_checked=True,actual_closed_original32_review_and_native_outer_closures_checked=True,actual_idle_GPU_port_lease_checked=True,external_OS_state_mocked=False,synthetic_candidate_and_phase_CPU_metadata=True,new_candidate_numerically_verified=False,numerical_runtime_imported='torch' in sys.modules,cuda_initialized=False,real_GPU_or_MAME_launched=False,actual_quality_campaign_selected=False,actual_policy_published=False,promotion=False)
with Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-observer-v2-live-preflight-CPU-original01-preparation-20261019/CPU-report.json').open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
sys.exit(0 if result.wasSuccessful() and 'torch' not in sys.modules else 1)
