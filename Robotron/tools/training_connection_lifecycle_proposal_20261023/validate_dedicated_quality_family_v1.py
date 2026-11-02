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
        candidate=dict(policy=dict(sha256='c'*64),saved_clocks={key:value+1 for key,value in subject.FAILED2715_CLOCKS.items()}))
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
            self.assertIn("PAIR_SHA not in ('"+subject.OLD_PAIR+"','"+subject.FAILED2690_PAIR+"','"+subject.FAILED2700_PAIR+"','"+subject.FAILED2715_PAIR+"')",rendered['runtime']['source'])
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
            with self.assertRaises(ValueError):subject.render(templates,pair,subject.FAILED2690_PAIR,'synthetic')
            negative.append('closed2690_pair_forbidden')
            data=copy.deepcopy(pair);data['candidate']['policy']['sha256']=subject.FAILED2690_POLICY
            with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
            negative.append('closed2690_policy_forbidden')
            for key,floor in subject.FAILED2690_CLOCKS.items():
                data=copy.deepcopy(pair);data['candidate']['saved_clocks'][key]=floor
                with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
                negative.append('closed2690_nonlater_'+key)
            with self.assertRaises(ValueError):subject.render(templates,pair,subject.FAILED2700_PAIR,'synthetic')
            negative.append('closed2700_pair_forbidden')
            data=copy.deepcopy(pair);data['candidate']['policy']['sha256']=subject.FAILED2700_POLICY
            with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
            negative.append('closed2700_policy_forbidden')
            for key,floor in subject.FAILED2700_CLOCKS.items():
                data=copy.deepcopy(pair);data['candidate']['saved_clocks'][key]=floor
                with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
                negative.append('closed2700_nonlater_'+key)
            with self.assertRaises(ValueError):subject.render(templates,pair,subject.FAILED2715_PAIR,'synthetic')
            negative.append('closed2715_pair_forbidden')
            data=copy.deepcopy(pair);data['candidate']['policy']['sha256']=subject.FAILED2715_POLICY
            with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
            negative.append('closed2715_policy_forbidden')
            for key,floor in subject.FAILED2715_CLOCKS.items():
                data=copy.deepcopy(pair);data['candidate']['saved_clocks'][key]=floor
                with self.assertRaises(ValueError):subject.render(templates,data,'f'*64,'synthetic')
                negative.append('closed2715_nonlater_'+key)
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

        def test_readiness_must_close_before_private_policy_setup_and_has_unchanged_game_helpers(self):
            nodes=ast.parse(rendered['runtime']['source'])
            run=next(n for n in nodes.body if isinstance(n,ast.FunctionDef)and n.name=='run')
            calls=[n for n in ast.walk(run)if isinstance(n,ast.Call)]
            checks=sorted([n for n in calls if isinstance(n.func,ast.Name)and n.func.id=='check_main'],key=lambda n:n.lineno)
            self.assertTrue(any(k.arg=='require_closed'and isinstance(k.value,ast.Constant)and k.value.value is True
                for k in checks[0].keywords))
            sidecar=next(n for n in calls if isinstance(n.func,ast.Name)and n.func.id=='load'
                and n.args and isinstance(n.args[0],ast.Constant)and n.args[0].value=='_compiled32_profile06_sidecar')
            marker=next(n for n in ast.walk(run)if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name)and t.id=='main_initial_readiness'for t in n.targets)
                and isinstance(n.value,ast.Call))
            self.assertLess(checks[0].lineno,marker.lineno);self.assertLess(marker.lineno,sidecar.lineno)
            self.assertIn("initial_main_readiness=main_initial_readiness",rendered['runtime']['source'])
            self.assertIn("robotron-native-dedicated-main-health-protocol-v5",rendered['leg_preparer']['source'])
            self.assertIn("initial_readiness_protocol=readiness['initial_readiness_protocol']",rendered['leg_preparer']['source'])
            self.assertEqual(runtime.HEALTH_DEPENDENCIES['mixed_transport'],job['proposed_transport']['sha256'])
            self.assertEqual(runtime.HEALTH_DEPENDENCIES['full_health_engine'],job['proposed_engine']['sha256'])
        def test_pure_readiness_receipt_requires_raw_indices_scope_and_before_load_admission(self):
            jp=dict(path='/explicit-synthetic/native-job.json',sha256='1'*64)
            job_value=dict(runtime=dict(path='/explicit-synthetic/native.py',sha256='2'*64),
                main_health_protocol=dict(path='/explicit-synthetic/protocol.json',sha256='3'*64))
            raw=dict(first_observed_unix_s=1000.,transport=dict(initial_readiness=dict(
                first_qualified_baseline_index=1,unaccepted_samples=1,first_qualified_baseline_unix_s=1000.2)))
            receipt=dict(schema='robotron-native-initial-main-readiness-v1',original_job=jp,
                runtime=job_value['runtime'],main_health_protocol=job_value['main_health_protocol'],
                before_sidecar_Torch_policy_or_MAME=True,first_qualified_baseline_index=1,
                unaccepted_initial_samples=1,first_qualified_baseline_unix_s=1000.2,
                observed_unix_s=1000.3,observed_monotonic_s=501.)
            pin=dict(identity=dict(mtime_ns=1000400000000))
            loaded=dict(identity=dict(mtime_ns=1001000000000))
            admission=dict(open_unix_ns=1002000000000)
            def check(value=receipt,r=raw,p=pin,l=loaded,a=admission):
                return reviewer.validate_initial_readiness(value,p,job_value,jp,r,l,a,500.,600.)
            self.assertTrue(check()['before_private_policy_and_game_setup_verified'])
            for name,mutation in [
                ('wrong_job',lambda x:x.update(original_job=dict(path='/other',sha256='0'*64))),
                ('wrong_runtime',lambda x:x.update(runtime={})),
                ('wrong_protocol',lambda x:x.update(main_health_protocol={})),
                ('setup_too_early',lambda x:x.update(before_sidecar_Torch_policy_or_MAME=False)),
                ('different_ready_index',lambda x:x.update(first_qualified_baseline_index=2)),
                ('boolean_ready_index',lambda x:x.update(first_qualified_baseline_index=True)),
                ('boolean_unaccepted_count',lambda x:x.update(unaccepted_initial_samples=True)),
                ('different_ready_time',lambda x:x.update(first_qualified_baseline_unix_s=1000.4)),
                ('receipt_after_loaded_policy',lambda x:x.update(observed_unix_s=1001.5)),
                ('outside_original_scope',lambda x:x.update(observed_monotonic_s=601.)),
                ('nonfinite_receipt',lambda x:x.update(observed_unix_s=float('nan')))]:
                value=copy.deepcopy(receipt);mutation(value)
                with self.assertRaises((ValueError,KeyError,TypeError)):check(value)
                negative.append(name)
            late_raw=copy.deepcopy(raw);late_raw['transport']['initial_readiness']['first_qualified_baseline_unix_s']=1003.
            late_receipt=copy.deepcopy(receipt);late_receipt['first_qualified_baseline_unix_s']=1003.
            with self.assertRaises(ValueError):check(late_receipt,late_raw)
            with self.assertRaises(ValueError):check(p=dict(identity=dict(mtime_ns=1001500000000)))
            with self.assertRaises(ValueError):check(a=dict(open_unix_ns=1000500000000))
            negative.extend(['readiness_over_two_seconds','receipt_file_after_loaded','admission_before_loaded'])

        def test_real_dedicated_worker_positive_and_twenty_wrong_lifecycle_joins(self):
            self.assertEqual(runtime.OBSERVER_DEPENDENCIES,{key:value['sha256']for key,value in job['observer_sources'].items()})
            self.assertEqual(runtime.FINALIZER_SHA,job['dedicated_finalizer']['sha256'])
            native_source=rendered['runtime']['source']
            self.assertIn('main_guard.start()',native_source)
            self.assertIn("main_samples=finalized_main['statuses']",native_source)
            self.assertIn('main_guard.scope_complete',native_source)
            self.assertIn("main_observer_reviewer=family['main_observer']['reviewer']",rendered['leg_preparer']['source'])
            self.assertIn('main_observer_independently_verified',rendered['leg_reviewer']['source'])
            reader=load('_actual_scope_reader',job['reader'])
            def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
            cj=read(job['client_component_job']);cr=read(job['client_component_report']);cf=read(cj['source_family_manifest']);cp=read(cj['main_health_protocol'])
            owner=read(job['client_component_owner']);argv=read(job['client_component_config'])['argv'];life_pin=cr['observer_lifecycle'];life=read(life_pin)
            review=load('_actual_observer_reviewer',cf['main_observer']['reviewer'])
            expected=review.verify(cj,job['client_component_job'],owner,argv,life_pin,cp,cf,[],read,h)
            self.assertEqual(expected,cr['independent_worker_review'])
            variants=[
                ('life_native',life_pin,lambda d:d.update(native_job={})),
                ('life_failure',life_pin,lambda d:d.update(success=False)),
                ('controller_nonzero',life_pin,lambda d:d.update(actual_controller_exit=1)),
                ('unit_not_released',life_pin,lambda d:d.update(original_scope_released=False)),
                ('missing_outcome',life_pin,lambda d:d.update(worker_outcome=None)),
                ('parent_birth',life['worker_job'],lambda d:d['parent'].update(birth=d['parent']['birth']+1)),
                ('foreign_protocol',life['worker_job'],lambda d:d.update(native_protocol={})),
                ('foreign_health',life['worker_job'],lambda d:d.update(health_job={})),
                ('short_scope',life['worker_job'],lambda d:d.update(unit_runtime_s=180)),
                ('extended_deadline',life['worker_job'],lambda d:d.update(deadline_monotonic_s=d['deadline_monotonic_s']+1)),
                ('signaled_outcome',life['worker_outcome'],lambda d:d.update(signals_received=[15])),
                ('failed_outcome',life['worker_outcome'],lambda d:d.update(success=False)),
                ('writer_alive',life['worker_outcome'],lambda d:d.update(all_writer_threads_stopped=False)),
                ('foreign_nonce',life['worker_outcome'],lambda d:d.update(nonce='f'*32)),
                ('wrong_resources',life['worker_config'],lambda d:d.update(properties=[])),
                ('wrong_argv',life['worker_config'],lambda d:d.update(argv=['foreign'])),
                ('raw_signal_closure',life['worker_closure'],lambda d:d.update(original_exit=None,original_exec_code=2,original_signal=9)),
                ('incomplete_closure',life['worker_closure'],lambda d:d.update(unit_released=False)),
                ('foreign_controller_child',life['controller_child'],lambda d:d.update(argv=['foreign'])),
                ('closed_writer_not_stopped',cr['finalized']['report'],lambda d:d['writer'].update(thread_stopped=False))]
            for name,pin,mutation in variants:
                # Explicit pure negative fixture. Never rewrite any original file.
                changed=copy.deepcopy(read(pin));mutation(changed)
                def fixture_read(entry,as_json=True):
                    if entry==pin and as_json:return copy.deepcopy(changed)
                    return read(entry,as_json)
                with self.assertRaises((ValueError,KeyError,TypeError)):
                    review.verify(cj,job['client_component_job'],owner,argv,life_pin,cp,cf,[],fixture_read,h)
                negative.append('dedicated_join:'+name)

    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    if not result.wasSuccessful():return 1
    assert 'torch'not in sys.modules
    report=dict(status='UNSELECTED_QUALITY_FAMILY_RENDERER_GATES_MATH_AND_SMALL_DISPLAY_CONTRACTS_PASS',tests=result.testsRun,
        negative_checks=negative,rendered_family_bindings_are_synthetic=True,actual_closed_client_scope_also_rechecked=True,no_source_family_published=True,old2690_original_retried=False,no_model_MAME_GPU_or_scientific_case_started=True,
        source_sha256=args.source_sha256,job_sha256=args.job_sha256,quality_qualified=False,production_changed=False,created_unix_s=time.time())
    h.put(output/'report.json',report);print(json.dumps(dict(status=report['status'],tests=result.testsRun,negative_checks=len(negative))),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
