"""CPU source-family renderer, unchanged qualification gates and small display contracts."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import types
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-owned-quality-family-CPU-job-v1'and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    def load(name,pin):
        path=Path(pin['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256']
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    h=load('_family_h',job['helpers'])
    for pin in [*job['templates'].values(),job['subject'],job['original_runtime'],job['original_assessor'],job['old_native_job']]:h.checked(pin)
    subject=load('_family_renderer',job['subject']);templates={key:Path(pin['path']).read_text()for key,pin in job['templates'].items()}
    pair=dict(reference=dict(policy=dict(sha256=subject.REFERENCE),saved_clocks=subject.REF_CLOCKS),
        candidate=dict(policy=dict(sha256='c'*64),saved_clocks=dict(learner_frame_count=2630798738,
            training_steps=10464228,optimized_samples=41285679105,frame_count=5142595638)))
    rendered=subject.render(templates,pair,'f'*64,'explicit-synthetic-fixture')
    def module(key):
        value=rendered[key];m=types.ModuleType('_family_'+key);m.__file__=value['path']
        exec(compile(value['source'],value['path'],'exec'),m.__dict__);return m
    runtime=module('runtime');reviewer=module('leg_reviewer');assessor=module('campaign_assessor');display=module('display_source')
    output=Path(job['output']);output.mkdir(mode=0o700);negative=[]
    def definition(source,name):return next(n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name==name)
    def cohort(role,scores):
        stats=assessor.metrics(scores);ids=[role+str(i)for i in range(len(scores))]
        return dict(stats,closed=True,complete=True,valid=True,pending=0,abandoned=0,pending_ids=[],abandoned_ids=[],
            started=len(scores),started_ids=ids,started_actor_slots=list(range(4096,4128)),
            rows=[dict(journal_game_id=identifier,client_slot=4096+i%32,score=score,complete=True,eligible=True,
                known_start=True,excluded_reason='')for i,(identifier,score)in enumerate(zip(ids,scores))])
    def decision(one,two):
        legs=[]
        for index,(role,scores)in enumerate([('R1',[100]*64),('C1',one),('R2',[100]*64),('C2',two)]):
            legs.append(dict(role=role,cohort=cohort(role,scores),evidence_verified=True,original_attempt=1,no_retry=True,
                policy_sha256=subject.REFERENCE if role.startswith('R')else'c'*64,
                native_identity=[100+index,1,'a'+str(index)],review_identity=[200+index,1,'b'+str(index)]))
        return assessor.assess_validated_cohorts(legs,subject.REFERENCE,'c'*64)
    class Contracts(unittest.TestCase):
        def test_top_level_bindings_change_without_replacing_historical_forbidden_literals(self):
            self.assertEqual(runtime.PAIR_SHA,'f'*64);self.assertEqual(reviewer.PAIR_SHA,'f'*64)
            self.assertEqual(runtime.POLICIES['candidate']['clocks'],pair['candidate']['saved_clocks'])
            self.assertIn("PAIR_SHA!='"+subject.OLD_PAIR+"'",rendered['runtime']['source'])
            self.assertEqual(hashlib.sha256(rendered['runtime']['source'].encode()).hexdigest(),reviewer.RUNTIME_SHA)
            self.assertIn(rendered['runtime']['path'],rendered['native_controller']['source'])
            self.assertIn(Path(rendered['runtime']['path']).name,rendered['leg_reviewer']['source'])
        def test_wrong_reference_old_candidate_pair_and_unsafe_names_reject(self):
            for name,mutation in [('wrong_reference',lambda p:p['reference']['policy'].update(sha256='0'*64)),
                ('old_candidate',lambda p:p['candidate']['saved_clocks'].update(learner_frame_count=2630798737)),
                ('old_candidate_digest',lambda p:p['candidate']['policy'].update(sha256=subject.OLD_POLICY)),
                ('noninteger_clock',lambda p:p['candidate']['saved_clocks'].update(training_steps=1.0))]:
                data=copy.deepcopy(pair);mutation(data)
                with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
                negative.append(name)
            with self.assertRaises(ValueError):subject.render(templates,pair,subject.OLD_PAIR,'synthetic')
            with self.assertRaises(ValueError):subject.render(templates,pair,'f'*64,'../unsafe')
            negative.extend(['old_pair_digest','unsafe_case_slug'])
        def test_original_game_actor_lease_and_exact_confirmation_math_ASTs_are_preserved(self):
            old=Path(job['original_runtime']['path']).read_text()
            for node in ast.parse(old).body:
                if isinstance(node,(ast.FunctionDef,ast.ClassDef))and node.name not in ('run','validate_job'):
                    self.assertEqual(ast.dump(node,include_attributes=False),ast.dump(definition(rendered['runtime']['source'],node.name),include_attributes=False))
            old=Path(job['original_assessor']['path']).read_text()
            for name in ('metrics','assess_validated_cohorts'):
                self.assertEqual(ast.dump(definition(old,name),include_attributes=False),ast.dump(definition(rendered['campaign_assessor']['source'],name),include_attributes=False))
        def test_changed_source_cannot_adopt_old_native_job_and_cannot_reduce_minimum_or_cutoffs(self):
            old=json.loads(Path(job['old_native_job']['path']).read_bytes())
            with self.assertRaises(ValueError):runtime.validate_job(old)
            negative.append('old_native_job_not_adopted')
            data=copy.deepcopy(old);data.update(quality_pair_precommit=dict(sha256='f'*64),
                main_health_protocol=dict(path='/synthetic',sha256='0'*64,bytes=0,identity={}),
                source_family_manifest=dict(path='/synthetic',sha256='0'*64,bytes=0,identity={}),output=str(output/'never-launched'))
            runtime.validate_job(data)  # Structural gate only: no engine/job/artifact is launched or published.
            for name,key,value in [('minimum49','minimum_completed_games',49),('short_admission','admission_s',1),
                ('short_whole_cohort','whole_cohort_timeout_s',100),('different_backend','backend','eager')]:
                altered=copy.deepcopy(data);altered[key]=value
                with self.assertRaises(ValueError):runtime.validate_job(altered)
                negative.append(name)
        def test_each_candidate_mean_and_median_gate_still_applies_independently(self):
            self.assertTrue(decision([105]*64,[105]*64)['all_candidate_gates_passed'])
            value=decision([104]*64,[106]*64);self.assertFalse(value['all_candidate_gates_passed']);self.assertFalse(value['candidate_pool_used'])
            self.assertFalse(value['independent_candidates']['C1']['mean_at_least_105_percent'])
            value=decision([90]*48+[200]*16,[130]*64)
            self.assertFalse(value['all_candidate_gates_passed']);self.assertFalse(value['independent_candidates']['C1']['median_preserved'])
            negative.extend(['pooled_candidate_rescue_forbidden','mean_gain_does_not_rescue_lost_median'])
        def test_display_uses_small_closed_projection_and_rejects_signaled_reviewer_success(self):
            root=output/'explicit-synthetic-display';directory=root/'01-reference';(directory/'diagnostic-output-original01').mkdir(parents=True);(root/'display').mkdir()
            def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            summary=dict(valid=True,complete=True,cohort=dict(count=64,started=64,pending=0,mean=105,median=105,se=0))
            write(directory/'original-closed-display-summary.json',summary)
            for name in ['controller-original-result.json','independent-review-controller-original-result.json']:
                closed=directory/(name+'.explicit-synthetic-closure.json');write(closed,dict(original_exit=0,lifecycle_complete=True,unit_released=True))
                write(directory/name,dict(actual_exit=0,closure=dict(path=str(closed))))
            row=display.project(root,0);self.assertEqual(row['state'],'finished')
            saved=json.loads((root/'display/01-reference.json').read_text());self.assertEqual(saved['mean'],105);self.assertTrue(saved['valid'])
            write(directory/'independent-review-controller-original-result.json',dict(actual_exit=1))
            row=display.project(root,0);self.assertEqual(row['state'],'failed')
            negative.append('signaled_reviewer_cannot_be_displayed_complete_from_old_summary')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    assert 'torch'not in sys.modules
    report=dict(status='UNSELECTED_QUALITY_FAMILY_RENDERER_GATES_MATH_AND_SMALL_DISPLAY_CONTRACTS_PASS',tests=result.testsRun,
        negative_checks=negative,synthetic_bindings_only=True,no_source_family_published=True,no_model_MAME_GPU_or_scientific_case_started=True,
        source_sha256=args.source_sha256,job_sha256=args.job_sha256,quality_qualified=False,production_changed=False,created_unix_s=time.time())
    h.put(output/'report.json',report);print(json.dumps(dict(status=report['status'],tests=result.testsRun,negative_checks=len(negative))),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
