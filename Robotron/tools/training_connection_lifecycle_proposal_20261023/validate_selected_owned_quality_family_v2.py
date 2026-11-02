"""Validate the actually published policy family and original endpoint scope before games."""
import argparse,ast,copy,hashlib,importlib.util,json,os,sys,time,unittest
from pathlib import Path

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
 if not args.execute:print('PLAN_ONLY');return 0
 assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
 raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256;job=json.loads(raw)
 assert job['schema']=='robotron-selected-owned-quality-family-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
 def load(pin,name):
  assert hashlib.sha256(Path(pin['path']).read_bytes()).hexdigest()==pin['sha256']
  spec=importlib.util.spec_from_file_location(name,pin['path']);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
 h=load(job['helpers'],'_actual_h');reader=load(job['reader'],'_actual_r')
 def read(pin):return reader.read_pin(pin)
 ready=read(job['readiness']);family=read(ready['source_family_manifest']);pair=read(ready['quality_pair']);pre=read(job['sequence_precommit']);output=Path(job['output']);output.mkdir(mode=0o700)
 runtime=load(ready['native_runtime'],'_actual_runtime');assessor=load(ready['campaign_assessor'],'_actual_assessor');renderer=load(family['renderer'],'_actual_renderer');sequence=load(family['sequence'],'_actual_sequence');base=load(job['sequence_base'],'_actual_sequence_base')
 negative=[]
 class Contracts(unittest.TestCase):
  def test_01_published_seven_sources_are_exact_tested_renderer_outputs(self):
   templates={k:h.checked(v).read_text()for k,v in family['source_templates'].items()};rendered=renderer.render(templates,pair,ready['quality_pair']['sha256'],ready['case_slug'])
   for key,item in rendered.items():
    self.assertEqual(family[key]['path'],item['path']);self.assertEqual(h.checked(family[key]).read_text(),item['source']);self.assertEqual(family[key]['sha256'],item['sha256'])
   for pin in ready['inputs']:h.checked(pin)
  def test_02_actual_numerical_endpoint_resources_archives_and_release_pass(self):
   instance=sequence.sequence_type(base)(job['sequence_precommit'],h,reader);instance.validate_endpoint_CPU()
   report=read(pre['endpoint_CPU_report']);self.assertEqual({k:report['clocks'][k]for k in pair['candidate']['saved_clocks']},pair['candidate']['saved_clocks'])
   self.assertEqual(pair['reference']['saved_clocks'],renderer.REF_CLOCKS)
  def test_03_original_game_runtime_and_confirmation_math_definitions_unchanged(self):
   def definition(text,name):return next(x for x in ast.parse(text).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))and x.name==name)
   current=h.checked(ready['native_runtime']).read_text()
   for node in ast.parse(h.checked(job['original_runtime']).read_text()).body:
    if isinstance(node,(ast.FunctionDef,ast.ClassDef))and node.name not in ('run','validate_job'):self.assertEqual(ast.dump(node),ast.dump(definition(current,node.name)))
   for name in ['metrics','assess_validated_cohorts']:self.assertEqual(ast.dump(definition(h.checked(job['original_assessor']).read_text(),name)),ast.dump(definition(h.checked(ready['campaign_assessor']).read_text(),name)))
  def test_04_every_new_role_structural_gate_and_original_case_rejection(self):
   template=read(ready['native_job_template'])
   for role,policy_role in runtime.ROLES.items():
    template['sessions']={str(slot):format(index+1,'032x')for index,slot in enumerate(runtime.SLOTS)}
    template['connections']={str(slot):format(index+33,'032x')for index,slot in enumerate(runtime.SLOTS)}
    data=copy.deepcopy(template);data.update(schema='robotron-compiled-full-tail32-quality-original-v1',quality_leg=role,quality_pair_precommit=ready['quality_pair'],minimum_completed_games=50,expected_policy_clocks=runtime.POLICIES[policy_role]['clocks'],checkpoint=pair[policy_role]['policy'],runtime=ready['native_runtime'],main_health_protocol=ready['source_family_manifest'],source_family_manifest=ready['source_family_manifest'],output=str(output/('structural-only-never-launched-'+role)))
    runtime.validate_job(data)
    for key,value in [('minimum_completed_games',49),('admission_s',5399),('whole_cohort_timeout_s',8999),('backend','eager')]:
     wrong=copy.deepcopy(data);wrong[key]=value
     with self.assertRaises(ValueError):runtime.validate_job(wrong)
     negative.append(role+':'+key)
   with self.assertRaises(ValueError):runtime.validate_job(read(job['old_native_job']))
   negative.append('old_invalid_original_cannot_be_adopted')
  def test_05_actual_dependency_and_shared_budget_source_bindings(self):
   self.assertEqual({k:v['sha256']for k,v in ready['main_health_sources'].items()},runtime.HEALTH_DEPENDENCIES)
   self.assertEqual(family['main_prefix_validator']['sha256'],runtime.PREFIX_VALIDATOR_SHA);self.assertEqual(family['main_health_finalizer']['sha256'],runtime.FINALIZER_SHA)
   self.assertEqual(ready['leg_CPU_controller'],ready['campaign_CPU_controller']);self.assertEqual(ready['leg_CPU_controller'],family['leg_CPU_controller'])
   cfg=read(pre['campaign_assessment_config']);self.assertEqual(cfg['argv'][3],ready['campaign_assessor']['path']);self.assertEqual(cfg['argv'][4],'--execute')
   load(ready['campaign_CPU_controller'],'_actual_cpu660').checked_config(pre['campaign_assessment_config']['path'])
  def test_06_all_four_original_leg_directories_are_absent(self):
   root=Path(ready['campaign_directory'])
   for folder in base.FOLDERS:self.assertFalse((root/folder).exists())
   self.assertFalse((root/'original-fresh-sequence-observer-original01-intent.json').exists());self.assertFalse(pre.get('existing_R1_adopted',False))
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
 if not result.wasSuccessful():return 1
 assert 'torch'not in sys.modules
 report=dict(schema='robotron-selected-owned-quality-family-CPU-report-v1',status='ACTUAL_SELECTED_SEVEN_SOURCES_ENDPOINT_AND_UNCHANGED_GATES_PASS',tests=result.testsRun,negative_checks=negative,readiness=job['readiness'],sequence_precommit=job['sequence_precommit'],scientific_case_started=False,quality_qualified=False,production_changed=False,created_unix_s=time.time())
 h.put(output/'report.json',report);print(json.dumps(dict(status=report['status'],tests=result.testsRun,negative_checks=len(negative))),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
