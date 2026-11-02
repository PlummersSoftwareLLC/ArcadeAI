"""Campaign metadata from synthetic CPU proofs and actual read-only main state.

The candidate and its phase-verifier archives are synthetic, never numerical
authority. Original32 capacity records, source package and main owner are real.
No numerical model, evaluator, training change or policy publication occurs.
"""
import copy
import json
from pathlib import Path
import time
import unittest

import prepare_quality32_campaign_v1 as prepare
import test_closed_quality32_full_path_v3 as fixtures


class CampaignPreparationTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.FullPathTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.reader=self.f.reader;self.root=self.f.root
        self.N=prepare.GAME/'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/capacity32-confirmed1059-raw-API-v1-preparation-20261019'
        main=self.reader.read_pin(self.reader.pin(self.N/'runtime-bindings/main-binding.json'))
        evidence=self.f.acquisition(main)
        suffix=str(time.time_ns())
        self.directory=prepare.GAME/'logs/managed-learning-20261015'/('synthetic-quality32-preparation-unused-'+suffix)
        self.addCleanup(lambda:self.assertFalse(self.directory.exists()))
        lease=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock');info=lease.stat()
        self.job=dict(schema='robotron-quality32-campaign-preparation-job-v1',
            **{key:evidence[key] for key in ('phase_cpu_job','phase_cpu_report','phase_cpu_closure','phase_cpu_config',
                                            'window_job','window_result','window_latch','source_package')},
            reference=self.f.reference,main_binding_template=self.reader.pin(self.N/'runtime-bindings/main-binding.json'),
            output=str(self.root/'new-quality-preparation'),
            native_unit='robotron-quality32-prepare-synthetic-native-'+suffix+'.service',
            outer_unit='robotron-quality32-prepare-synthetic-outer-'+suffix+'.service',
            review_unit='robotron-quality32-prepare-synthetic-review-'+suffix+'.service',
            binary_inputs=[],capacity_review=self.reader.pin(self.N/'independent-original32-pilot-review/review.json'),
            preceding_originals=[dict(owner=self.reader.pin(self.N/(name+'-execution/root-original-live-owner.json')),
                closure=self.reader.pin(self.N/(name+'-execution/native-terminal-archive/root-original-result-and-owned-release.json')))
                for name in ('pilot-root','outer-controller')],
            lease_path=str(lease),lease_identity=dict(device=info.st_dev,inode=info.st_ino),
            campaign_parameters=dict(directory=str(self.directory),reference_label='protected1059',candidate_label='synthetic_candidate',
                hypothesis='additional_CE4096_LR25_learning_improves_full_game_score_vs_protected1059_no_speed_claim',
                boot_assets=str(prepare.GAME/'logs/managed-learning-20261015/sidecar-boot-assets-v1')),
            hypothesis_description='Synthetic test of metadata preparation; no candidate quality or speed claim.')
        self.job_pin=self.f.put(self.root/'campaign-preparation-root-job.json',self.job)

    def update_job(self):
        self.job_pin=self.f.put(self.job_pin['path'],self.job)

    def execute(self):
        return prepare.prepare(self.job,self.job_pin,self.reader)

    def test_full_preparation_and_real_readonly_observer_preflight_no_launch(self):
        result=self.execute();self.assertEqual(result['status'],'PREPARED_NOT_LAUNCHED')
        self.assertFalse(result['quality_qualified']);self.assertFalse(result['actual_runtime_changed'])
        completion=self.reader.read_pin(result['CPU_completion'])
        self.assertEqual(completion['CPU_report'],self.job['phase_cpu_report'])
        binding=self.reader.read_pin(result['binding_template'])
        self.assertEqual(binding['candidate'],self.f.candidate)
        self.assertEqual(binding['reference'],self.f.reference)
        self.assertEqual(len(binding['main_holds']['actors']),192)
        self.assertEqual(len(binding['main_holds']['held_hashes']),193)
        config=self.reader.read_pin(result['native_controller_config'])
        self.assertIn('RuntimeMaxSec=29400',config['properties']);self.assertIn('SendSIGKILL=no',config['properties'])
        self.assertEqual(config['argv'][config['argv'].index('--actors')+1],'32')
        observer=prepare.load(*prepare.SOURCES['observer'],'_test_final_preflight_')
        guard=observer.prepare(config,result['native_controller_config'])
        guard.before_scheduling();self.assertIsNone(guard.identity);self.assertEqual(len(guard.samples),2)
        self.assertFalse(Path(config['output']).exists());self.assertFalse(self.directory.exists())

    def test_original_CPU_nonzero_exit_cannot_be_completed_or_launch_prepared(self):
        closure=self.reader.read_pin(self.job['phase_cpu_closure']);closure['original_exit']=1
        self.job['phase_cpu_closure']=self.f.put(self.job['phase_cpu_closure']['path'],closure);self.update_job()
        with self.assertRaises(ValueError):self.execute()
        self.assertFalse(Path(self.job['output']).exists())

    def test_missing_CPU_report_rejects_before_outputs(self):
        self.job['phase_cpu_report']=dict(path=str(self.root/'missing-CPU-report.json'));self.update_job()
        with self.assertRaises((FileNotFoundError,KeyError)):self.execute()
        self.assertFalse(Path(self.job['output']).exists())

    def test_finite_tensor_scope_cannot_be_forged(self):
        report=self.reader.read_pin(self.job['phase_cpu_report']);report['finite']['tensors']=442
        self.job['phase_cpu_report']=self.f.put(self.job['phase_cpu_report']['path'],report);self.update_job()
        with self.assertRaisesRegex(ValueError,'CPU finite-model/Adam scope'):self.execute()
        self.assertFalse(Path(self.job['output']).exists())

    def test_checkpoint_clocks_below_original_floor_refused(self):
        report=self.reader.read_pin(self.job['phase_cpu_report']);report['clocks']['learner_frame_count']=1
        self.job['phase_cpu_report']=self.f.put(self.job['phase_cpu_report']['path'],report);self.update_job()
        with self.assertRaisesRegex(ValueError,'clock acquisition floor'):self.execute()
        self.assertFalse(Path(self.job['output']).exists())

    def test_changed_actual_completed_slot_pin_cannot_rebind_main(self):
        value=self.reader.read_pin(self.job['window_result'])
        value['completed_slot_transition']['after']['actual_pin']['sha256']='0'*64
        self.job['window_result']=self.f.put(self.job['window_result']['path'],value);self.update_job()
        with self.assertRaisesRegex(ValueError,'completed-slot transition'):self.execute()
        self.assertFalse(Path(self.job['output']).exists())

    def test_wrong_source_package_refused_before_output(self):
        self.job['source_package']=self.f.put(self.root/'foreign-package.json',dict(files={},root='/foreign'))
        self.update_job()
        with self.assertRaises(ValueError):self.execute()
        self.assertFalse(Path(self.job['output']).exists())

    def test_space_or_shell_ambiguous_native_argument_rejected_before_launch(self):
        for value in ('The hypothesis has spaces','quoted"argument','with;separator','with\\escape',''):
            with self.subTest(value=value),self.assertRaises(ValueError):prepare.archive_safe_command(['--hypothesis',value])
        self.job['campaign_parameters']['hypothesis']='A descriptive hypothesis with spaces';self.update_job()
        with self.assertRaisesRegex(ValueError,'unambiguous original archive'):self.execute()
        self.assertFalse(Path(self.job['output']).exists())

    def test_prepared_output_never_overwritten(self):
        result=self.execute();raw=Path(result['native_controller_config']['path']).read_bytes()
        with self.assertRaisesRegex(ValueError,'New original campaign preparation'):self.execute()
        self.assertEqual(Path(result['native_controller_config']['path']).read_bytes(),raw)


if __name__=='__main__':
    unittest.main()
