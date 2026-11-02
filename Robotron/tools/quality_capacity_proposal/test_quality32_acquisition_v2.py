"""Acquisition-component tests using immutable historical proofs and mutations.

The historical proof remains historical; no new candidate or quality result is
created. Future-window tests change metadata only in memory, without model loads.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

import quality32_acquisition_v1 as review


class AcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_directory = review.GAME/'logs/managed-learning-20261015/run-26'
        cls.binding_path = cls.run_directory/'confirmed-scoring-quality-original01-preparation-20261018/audit-bindings/binding-job.json'
        cls.oldbinding = json.loads(cls.binding_path.read_bytes())
        cls.cpu = cls.run_directory/'confirmed-scoring-candidate-CPU-original01-preparation-20261018'
        path = review.GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
        spec = importlib.util.spec_from_file_location('_acquisition_test_reader', path)
        cls.reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.reader)
        path = review.GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'
        cls.runtime_review = cls.reader.checked_module('_acquisition_test_archives', cls.reader.pin(path))
        for key, name in [('phase_cpu_closure','controller-execution/root-original-result-and-owned-release.json'),
                          ('phase_cpu_completion','CPU-completion.json'),
                          ('phase_cpu_config','CPU-controller-config.json')]:
            cls.oldbinding['evidence'][key] = cls.reader.pin(cls.cpu/name)
        cls.oldbundle = {key: cls.reader.read_pin(entry) for key, entry in cls.oldbinding['evidence'].items()}

    def setUp(self):
        self.binding, self.bundle = copy.deepcopy((self.oldbinding, self.oldbundle))

    def snapshot(self):
        return review.validate_snapshot(self.binding, self.bundle)

    def read(self, entry, as_json=True):
        return self.reader.read_pin(entry, as_json=as_json)

    def authority(self, archived=None):
        return review.validate_CPU_authority(self.binding, self.bundle, self.read,
            archived or self.runtime_review.archived_closure)

    def prospective(self):
        self.binding['reference'] = self.reader.pin(review.GAME/'models_dqn/managed-incumbents/freshCE-LR25-1059M-confirmed-reset-20261018.pt')
        self.binding['candidate']['sha256'] = 'c'*64
        entry = self.reader.pin(review.GAME/'tools/quality_capacity_proposal/profile03/runtime-source-package.json')
        self.binding['evidence']['source_package'] = entry
        window = self.bundle['window_job']
        self.binding['expected_window'] = {key: copy.deepcopy(window[key]) for key in ('owner','experiment','tag')}
        quality = window['quality_precommit']
        quality.update(reference=self.binding['reference']['path'], reference_sha256=review.REFERENCE_SHA,
                       all_slots=review.SLOTS.copy(), source_package=entry)

    def policy(self):
        return review.validate_window_policy(self.binding, self.bundle)

    def test_historical_snapshot_lineage_still_passes_without_reinterpretation(self):
        before = copy.deepcopy((self.binding, self.bundle))
        self.snapshot()
        self.assertEqual((self.binding, self.bundle), before)

    def test_all_previous_snapshot_checks_preserved_except_old_single_window_sha(self):
        source = (review.GAME/'tools/confirmed_game_boundary_proposal/audit_confirmed_completed_leg_reviewed3.py').read_text()
        original = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name=='validate_cpu_proof')
        old = [node for node in original.body if 'cd6a47e2112dffbe68a6ec7da2224337b8b2543702e54b75f4f9982745a68942'
               not in ast.get_source_segment(source,node)]
        current = next(node for node in ast.parse(Path(review.__file__).read_text()).body
                       if isinstance(node, ast.FunctionDef) and node.name=='validate_snapshot')
        self.assertEqual(ast.dump(ast.Module(body=old,type_ignores=[])),
                         ast.dump(ast.Module(body=current.body[3:],type_ignores=[])))

    def test_snapshot_status_actual_source_and_cpu_scope_cannot_change(self):
        for key, value in [('status','FAIL'), ('phase_metadata_verified',False),
                           ('actual_restore_or_optimizer_step',True), ('actual_quality_qualification',True)]:
            original = copy.deepcopy(self.bundle)
            self.bundle['phase_cpu_report'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.snapshot()
            self.bundle = original

    def test_snapshot_hash_bytes_and_phase_source_copy_must_match(self):
        for change in ('sha','bytes','same_inode','not_readonly','phase'):
            original = copy.deepcopy(self.bundle)
            proof = self.bundle['phase_cpu_report']
            if change=='sha': proof['sha256']='a'*64
            elif change=='bytes': proof['bytes']+=1
            elif change=='same_inode': proof['verification_copy']['inode']=proof['source_before']['inode']
            elif change=='not_readonly': proof['verification_copy']['mode']='0o664'
            else: proof['saved_priority_metric_phase']['phase_id']='another'
            with self.subTest(change=change), self.assertRaises(ValueError): self.snapshot()
            self.bundle = original

    def test_snapshot_clock_floor_and_first_both_horizons_are_required(self):
        for change in ('clock_floor','frames','accepted','latch','owner','tag'):
            original = copy.deepcopy(self.bundle)
            if change=='clock_floor': self.bundle['phase_cpu_report']['clocks']['learner_frame_count']=0
            elif change=='frames': self.bundle['window_result']['progress']['learner_frames']=7_999_999
            elif change=='accepted': self.bundle['window_result']['progress']['learner_accepted']=7_999_999
            elif change=='latch': self.bundle['window_latch']['status']='OTHER'
            elif change=='owner': self.bundle['window_result']['owner']['pid']+=1
            else: self.bundle['window_result']['tag']='another'
            with self.subTest(change=change), self.assertRaises(ValueError): self.snapshot()
            self.bundle = original

    def test_original_CPU_exit0_all_six_archives_and_exact_command_pass(self):
        self.authority()
        self.assertNotIn('torch',sys.modules)

    def test_unrelated_successful_CPU_command_cannot_authorize_proof(self):
        closure = self.bundle['phase_cpu_closure']
        fields = self.runtime_review.archived_closure(closure,closure['original'],self.read,exit_zero=True)
        fields['ExecStart']=fields['ExecStart'].replace(str(review.VERIFIER),'/tmp/unrelated.py')
        with self.assertRaisesRegex(ValueError,'Archived successful service'):
            self.authority(lambda *args,**kwargs:fields)

    def test_original_CPU_nonzero_missing_archive_or_foreign_owner_is_rejected(self):
        for change in ('nonzero','missing_archive','owner'):
            original = copy.deepcopy(self.bundle)
            value = self.bundle['phase_cpu_closure']
            if change=='nonzero': value['original_exit']=1
            elif change=='missing_archive': value['full_original_archives'].pop()
            else:value['original']['pid']+=1
            with self.subTest(change=change), self.assertRaises(ValueError): self.authority()
            self.bundle=original

    def test_CPU_completion_must_join_same_report_job_candidate_and_closure(self):
        for field in ('CPU_report','cpu_job','actual_candidate','original_controller_release'):
            original=copy.deepcopy(self.bundle)
            self.bundle['phase_cpu_completion'][field]['sha256']='a'*64
            with self.subTest(field=field),self.assertRaises(ValueError):self.authority()
            self.bundle=original

    def test_CPU_config_and_report_must_bind_actual_verifier_job(self):
        for change in ('config_unit','config_argv','report_script','report_job'):
            original=copy.deepcopy(self.bundle)
            if change=='config_unit':self.bundle['phase_cpu_config']['unit']='foreign.service'
            elif change=='config_argv':self.bundle['phase_cpu_config']['argv'][-1]='a'*64
            elif change=='report_script':self.bundle['phase_cpu_report']['script']['path']='/tmp/foreign.py'
            else:self.bundle['phase_cpu_report']['job_file']['path']='/tmp/foreign.json'
            with self.subTest(change=change),self.assertRaises(ValueError):self.authority()
            self.bundle=original

    def test_historical845_window_cannot_be_used_for_future_reference(self):
        with self.assertRaisesRegex(ValueError,'Protected1059'):self.policy()

    def test_prospective_policy_metadata_can_pass_without_claiming_actual_capture(self):
        self.prospective()
        before=copy.deepcopy((self.binding,self.bundle));self.policy()
        self.assertEqual((self.binding,self.bundle),before)
        # The old actual CPU report cannot represent this synthetic candidate.
        with self.assertRaises(ValueError):self.snapshot()

    def test_future_window_owner_tag_and_experiment_are_exact(self):
        self.prospective()
        for key,value in [('tag','different'),('experiment','different'),('owner',{})]:
            original=copy.deepcopy(self.bundle)
            self.bundle['window_job'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.policy()
            self.bundle=original

    def test_future_policy_requires_original192_first_both_horizons(self):
        self.prospective()
        for change in ('actors','authorized','frames','accepted','one_capture'):
            original=copy.deepcopy(self.bundle);window=self.bundle['window_job']
            if change=='actors':window['actors'].pop()
            elif change=='authorized':window['authorized']=False
            elif change=='frames':window['policy']['learner_frames']=4_000_000
            elif change=='accepted':window['policy']['accepted_dqn_epsilon']=4_000_000
            else:window['policy']['one_capture_only']=False
            with self.subTest(change=change),self.assertRaises(ValueError):self.policy()
            self.bundle=original

    def test_future_quality_gates_slots_source_and_full_tails_cannot_change(self):
        self.prospective()
        for key,value in [('all_slots',list(range(4096,4112))),('full_tails',False),
            ('minimum_games',49),('max_attempts',2),('extensions',True),
            ('individual_mean_ratio',1.04),('individual_median_ratio',.99),
            ('same_fixed_admission_s',3600),('same_whole_cohort_timeout_s',6000),
            ('mandatory_original_terminal_journal_readback',False)]:
            original=copy.deepcopy(self.bundle)
            self.bundle['window_job']['quality_precommit'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.policy()
            self.bundle=original

    def test_strict_finite_model_Adam_and_no_CUDA_scope_required(self):
        self.prospective()
        for change in ('CUDA','finite','Adam','online','target'):
            original=copy.deepcopy(self.bundle);proof=self.bundle['phase_cpu_report']
            if change=='CUDA':proof['cuda_initialized']=True
            elif change=='finite':proof['finite']['tensors']=442
            elif change=='Adam':proof['adam_state_count']=80
            elif change=='online':proof['models']['online_state_dict']['strict_cpu_load']=False
            else:proof['models']['target_state_dict']['strict_cpu_load']=False
            with self.subTest(change=change),self.assertRaises(ValueError):self.policy()
            self.bundle=original

    def test_finite_ordered_latch_and_positive_applied_progress_required(self):
        self.prospective()
        for change in ('NaN','before_baseline','zero_applied','negative_skip','boolean_progress','experiment'):
            original=copy.deepcopy(self.bundle)
            if change=='NaN':self.bundle['window_latch']['observed_monotonic_s']=float('nan')
            elif change=='before_baseline':self.bundle['window_latch']['observed_monotonic_s']=0
            elif change=='experiment':self.bundle['window_latch']['job_experiment']='another'
            else:
                key,value=dict(zero_applied=('applied_updates',0),negative_skip=('amp_skips',-1),
                    boolean_progress=('learner_frames',True))[change]
                self.bundle['window_result']['progress'][key]=value
            with self.subTest(change=change),self.assertRaises(ValueError):self.policy()
            self.bundle=original

    def test_full_component_rejects_old_capture_before_loading_checkpoint_bytes(self):
        binary_reads=[]
        def reader(entry,as_json=True):
            if not as_json:binary_reads.append(entry['path'])
            return self.read(entry,as_json)
        with self.assertRaises(ValueError):
            review.review_acquisition(self.binding,reader,self.runtime_review.archived_closure)
        self.assertEqual(binary_reads,[])

    def test_default_cli_has_no_executor_or_side_effects(self):
        result=subprocess.run([sys.executable,'-I','-B',review.__file__,'--execute'],
            capture_output=True,text=True,check=True,timeout=10)
        self.assertTrue(result.stdout.startswith('PLAN_ONLY:'))
