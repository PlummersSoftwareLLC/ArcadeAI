"""Original metadata contracts for current1741 capture and fixed1597 reference.

Read existing original evidence only; mutations stay in memory. No evaluator,
model runtime, restore, save request, signal, or scientific reviewer is executed.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron');H=G/'tools/quality_capacity_proposal'
P=G/'logs/managed-learning-20261015/run-26/post-production-profile06-fresh-main-next8M-original01-preparation-20261021'


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class CurrentReferenceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader=module(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','_1597_reader')
        cls.runtime=module(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','_1597_archive')
        cls.acquisition=module(H/'quality32_acquisition_v5.py','_1597_acquisition')
        cls.review=module(H/'review_closed_quality32_v9.py','_1597_review')
        cls.supervision=module(H/'supervised_main_fleet_v2.py','_1597_supervision')
        cls.joins=module(H/'supervised_main_observations_v2.py','_1597_joins')
        cls.preparer=module(H/'prepare_quality32_campaign_v8.py','_1597_preparer')
        cls.proof=json.loads((P/'captured-main-registration-original01/root-independent-readback.json').read_bytes())
        pin=cls.reader.pin;C=P/'candidate-CPU-original01'
        evidence=dict(phase_cpu_job=pin(C/'candidate-CPU-job.json'),phase_cpu_report=pin(C/'candidate-CPU-report-readonly.json'),
            phase_cpu_closure=pin(C/'controller-execution/root-original-result-and-owned-release.json'),
            phase_cpu_config=pin(C/'CPU-controller-config.json'),window_job=pin(P/'window-job.json'),
            window_result=pin(P/'window-original01/result.json'),window_latch=pin(P/'window-original01/first-durable-both-horizons.json'),
            source_package=pin(H/'profile06/runtime-source-package.json'),
            current_capture_root=pin(P/'actual-current-candidate-CPU-preparation-root-job.json'))
        cls.original_binding=dict(candidate=cls.proof['candidate'],reference=pin(G/'models_dqn/managed-incumbents/freshCE-LR25-1597M-profile06-confirmed-reset-20261021.pt'),evidence=evidence)
        cls.original_bundle=cls.acquisition.load_bundle(cls.original_binding,cls.read_actual,cls.runtime.archived_closure)
        cls.original_binding['expected_window']={k:copy.deepcopy(cls.original_bundle['window_job'][k])for k in ('owner','experiment','tag')}
        cls.completion=dict(status='PASS',CPU_report=evidence['phase_cpu_report'],cpu_job=evidence['phase_cpu_job'],original_controller_release=evidence['phase_cpu_closure'],actual_candidate=cls.proof['candidate'],quality_qualified=False,promotion=False)
        cls.original_bundle['phase_cpu_completion']=cls.completion
        cls.main=cls.reader.read_pin(cls.proof['current_main_binding'])
        # The old policy supplies the still-original fleet owner only. A new
        # prospective policy is made by a real current read-only process census.
        cls.fleet=cls.reader.read_pin(cls.proof['historical_supervision_policy_archived_not_selected'])['fleet']
        cls.policy,cls.census=cls.supervision.make_policy(cls.main,cls.fleet)

    @classmethod
    def read_actual(cls,entry,as_json=True):return cls.reader.read_pin(entry,as_json=as_json)

    def setUp(self):self.binding,self.bundle=copy.deepcopy((self.original_binding,self.original_bundle))
    def snapshot(self):self.acquisition.validate_snapshot(self.binding,self.bundle)
    def policy_check(self):self.acquisition.validate_window_policy(self.binding,self.bundle)
    def authority(self,callback=None):self.acquisition.validate_CPU_authority(self.binding,self.bundle,self.read_actual,callback or self.runtime.archived_closure)

    def test_original_current_provenance_and_snapshot_pass(self):
        self.assertFalse(self.bundle['current_original_provenance']['views_are_original_producer_bytes']);self.snapshot();self.policy_check()
        self.assertEqual(self.bundle['phase_cpu_report']['clocks']['learner_frame_count'],1741229950)
        self.assertNotIn('torch',sys.modules)

    def test_normal_producer_and_two_readonly_copies_remain_distinct(self):
        job=self.bundle['phase_cpu_job'];candidate=self.binding['candidate']
        self.assertEqual(job['source']['identity']['mode'],'0o664');self.assertEqual(candidate['identity']['mode'],'0o444')
        self.assertEqual(len({(x['identity']['device'],x['identity']['inode'])for x in [job['source'],job['verification_copy'],candidate]}),3);self.snapshot()

    def test_normal_producer_scope_cannot_be_reinterpreted_as_archive(self):
        self.bundle['current_original_provenance']['normal_producer']=self.binding['candidate']
        with self.assertRaises(ValueError):self.snapshot()

    def test_mutable_evaluation_archive_is_rejected(self):
        self.binding['candidate']['identity']['mode']='0o664'
        with self.assertRaises(ValueError):self.snapshot()

    def test_reused_archive_inode_is_rejected(self):
        self.binding['candidate']['identity']['inode']=self.bundle['phase_cpu_job']['verification_copy']['identity']['inode']
        with self.assertRaises(ValueError):self.snapshot()

    def test_cpu_hash_bytes_phase_and_actual_status_are_required(self):
        for path,value in [(('status',),'FAIL'),(('sha256',),'0'*64),(('bytes',),1),(('phase_metadata_verified',),False),(('actual_restore_or_optimizer_step',),True),(('actual_quality_qualification',),True),(('saved_priority_metric_phase','phase_id'),'foreign')]:
            with self.subTest(path=path):
                self.setUp();o=self.bundle['phase_cpu_report']
                for k in path[:-1]:o=o[k]
                o[path[-1]]=value
                with self.assertRaises(ValueError):self.snapshot()

    def test_four_clock_floor_and_both_horizons_are_required(self):
        for key in self.bundle['phase_cpu_job']['clock_floor']:
            self.setUp();self.bundle['phase_cpu_report']['clocks'][key]=0
            with self.subTest(key=key),self.assertRaises(ValueError):self.snapshot()
        for key in ['learner_frames','learner_accepted']:
            self.setUp();self.bundle['window_result']['progress'][key]=7999999
            with self.subTest(key=key),self.assertRaises(ValueError):self.snapshot()

    def test_original_cpu_authority_all_six_and_exact_argv_pass(self):self.authority()

    def test_cpu_nonzero_and_incomplete_original_archives_rejected(self):
        for change in ['nonzero','archive']:
            self.setUp();c=self.bundle['phase_cpu_closure']
            if change=='nonzero':c['original_exit']=1
            else:c['full_original_archives'].pop()
            with self.subTest(change=change),self.assertRaises(ValueError):self.authority()

    def test_unrelated_cpu_command_rejected(self):
        c=self.bundle['phase_cpu_closure'];f=self.runtime.archived_closure(c,c['original'],self.read_actual,exit_zero=True)
        f['ExecStart']=f['ExecStart'].replace(str(self.acquisition.VERIFIER),'/tmp/foreign.py')
        with self.assertRaises(ValueError):self.authority(lambda *a,**k:f)

    def test_completion_must_join_actual_report_job_candidate_and_closure(self):
        for field in ['CPU_report','cpu_job','actual_candidate','original_controller_release']:
            self.setUp();self.bundle['phase_cpu_completion']=copy.deepcopy(self.completion);self.bundle['phase_cpu_completion'][field]['sha256']='0'*64
            with self.subTest(field=field),self.assertRaises(ValueError):self.authority()

    def test_fixed1597_accepts_and_old1059_rejects(self):
        self.policy_check();self.binding['reference']['sha256']='4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
        with self.assertRaises(ValueError):self.policy_check()

    def test_all_original_full_game_qualification_gates_remain_required(self):
        for key,value in [('all_slots',list(range(4096,4127))),('full_tails',False),('minimum_games',49),('max_attempts',2),('extensions',True),('individual_mean_ratio',1.04),('individual_median_ratio',.99),('same_fixed_admission_s',3600),('same_whole_cohort_timeout_s',9001),('mandatory_original_terminal_journal_readback',False),('no_historical_rows',False)]:
            self.setUp();self.bundle['window_job']['quality_precommit'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.policy_check()

    def test_strict_finite_models_adam_and_no_cuda_remain_required(self):
        for change in ['CUDA','Adam','finite','online','target']:
            self.setUp();p=self.bundle['phase_cpu_report']
            if change=='CUDA':p['cuda_initialized']=True
            elif change=='Adam':p['adam_state_count']=80
            elif change=='finite':p['finite']['tensors']=442
            else:p['models'][change+'_state_dict']['strict_cpu_load']=False
            with self.subTest(change=change),self.assertRaises(ValueError):self.policy_check()

    def test_exact_window_owner_experiment_tag_remain_required(self):
        for key in ['owner','experiment','tag']:
            self.setUp();self.binding['expected_window'][key]={} if key=='owner' else 'foreign'
            with self.subTest(key=key),self.assertRaises(ValueError):self.policy_check()

    def test_foreign_capture_root_or_cpu_job_rejected_before_any_reads(self):
        for key in ['current_capture_root','phase_cpu_job']:
            self.setUp();self.binding['evidence'][key]['sha256']='0'*64;calls=[]
            with self.subTest(key=key),self.assertRaises(ValueError):self.acquisition.load_bundle(self.binding,lambda *a,**k:calls.append(a),self.runtime.archived_closure)
            self.assertEqual(calls,[])

    def test_all196_main_holds_and_current_original192_policy_pass(self):
        self.assertEqual(len(self.main['held_hashes']),196)
        self.joins.validate_binding(self.main,self.policy,self.supervision)
        binding=dict(main_holds={k:self.main[k]for k in ['owner','actors','held_hashes','experiment']},expected_window=dict(owner=self.main['owner']))
        main=dict(self.main,supervision_policy={'metadata':'unpublished-test-pin'});binding['main_holds']['supervision_policy']=main['supervision_policy']
        self.review.validate_main_binding(main,binding)

    def test_dropping_one_main_hold_is_rejected(self):
        main=copy.deepcopy(self.main);main['held_hashes'].pop(next(iter(main['held_hashes'])))
        with self.assertRaises(ValueError):self.joins.validate_binding(main,self.policy,self.supervision)
        with self.assertRaises(ValueError):self.supervision.make_policy(main,self.fleet)

    def test_complete_source_dependency_graph_is_consistent(self):
        for name,(path,sha) in self.preparer.SOURCES.items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),sha,name)
        self.assertEqual(self.preparer.SOURCES['reviewer'][1],module(H/'quality32_runtime_guard_v9.py','_1597_guard').REVIEWER_SHA)
        for name,(path,sha) in self.review.DEPENDENCIES.items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),sha,name)
        cohort=module(H/'audit_quality32_evidence_v5.py','_1597_cohort');cohort.dependencies()
        package=self.read_actual(self.binding['evidence']['source_package'])
        for relative,sha in package['files'].items():
            actual=sha['sha256'] if isinstance(sha,dict) else sha
            self.assertEqual(hashlib.sha256((Path(package['root'])/relative).read_bytes()).hexdigest(),actual)

    def test_scientific_decision_and_protection_functions_ast_identical(self):
        for old,new,names in [('review_closed_quality32_v8.py','review_closed_quality32_v9.py',['decision','validate_records','validate_births','validate_leg_scope']),('audit_quality32_evidence_v4.py','audit_quality32_evidence_v5.py',['completed_cohort']),('quality32_acquisition_v4.py','quality32_acquisition_v5.py',['validate_CPU_authority']),('protect_quality32_winner_v6.py','protect_quality32_winner_v7.py',['verify','validate_original_leg','validate_review_command']),('quality32_runtime_guard_v8.py','quality32_runtime_guard_v9.py',['guard_class','prepare'])]:
            def functions(file):return {n.name:ast.dump(n,include_attributes=False)for n in ast.parse((H/file).read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
            a,b=functions(old),functions(new)
            for name in names:self.assertEqual(a[name],b[name],(new,name))

    def test_new_sources_do_not_mutate_original_files_or_import_model_runtime(self):
        self.assertEqual(self.reader.pin(self.proof['normal_producer']['path']),self.proof['normal_producer'])
        self.assertEqual(self.reader.pin(self.proof['candidate']['path']),self.proof['candidate'])
        self.assertNotIn('torch',sys.modules)


if __name__=='__main__':unittest.main()
