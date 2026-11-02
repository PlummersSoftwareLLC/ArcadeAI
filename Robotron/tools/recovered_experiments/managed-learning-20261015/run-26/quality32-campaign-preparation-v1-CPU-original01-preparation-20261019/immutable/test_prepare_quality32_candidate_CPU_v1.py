"""Synthetic captures/archives test metadata preparation, never model loading.

Historical actual window API counters are reused as historical values. Only an
owned temporary model directory receives fake checkpoint/control/slot bytes.
The main owner and trainer unit are queried read-only; no service is launched.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import prepare_quality32_candidate_CPU_v1 as prepare
import test_closed_quality32_full_path_v3 as fixtures


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.FullPathTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.reader=self.f.reader
        self.model=self.root/'synthetic-model-dir';self.model.mkdir()
        self.patch=patch.object(prepare,'MODEL',self.model);self.patch.start();self.addCleanup(self.patch.stop)
        base=prepare.GAME/'logs/managed-learning-20261015/run-26'
        old=base/'post-confirmed-scoring-next8M-original01-root-preparation-20261018/job.json'
        self.window=json.loads(old.read_bytes());originalout=Path(self.window['output'])
        self.result=json.loads((originalout/'result.json').read_bytes())
        self.latch=json.loads((originalout/'first-durable-both-horizons.json').read_bytes())
        self.trigger=self.reader.read_pin(self.result['trigger_API'])
        self.template=base/'confirmed-scoring-candidate-CPU-original01-preparation-20261018/candidate-CPU-job.json'
        self.oldtemplate=self.reader.read_pin(self.reader.pin(self.template))
        self.f.put(self.model/'learning_control.json',(prepare.GAME/'models_dqn/learning_control.json').read_bytes())
        self.tag='synthetic_CPU_preparation_only'
        self.window.update(output=str(self.root/'synthetic-window-output'),tag=self.tag)
        self.window['quality_precommit'].update(reference_sha256=prepare.REFERENCE_SHA,
            all_slots=list(range(4096,4128)),source_package=self.reader.pin(prepare.HERE/'profile03/runtime-source-package.json'))
        self.window['held_hashes']={str(self.model/'held-input.txt'):self.f.put(self.model/'held-input.txt',b'unchanged')['sha256']}
        self.window['held_hashes'][str(self.model/'managed_save.request.json.completed')]='historical before-slot hash'
        checkpoint=self.f.put(self.model/'managed-checkpoints'/(self.tag+'.pt'),b'fake checkpoint bytes; never loaded or numerically verified')
        request_raw=(json.dumps(dict(tag=self.tag))+'\n').encode()
        request_pin=self.f.put(self.model/'managed_save.request.json',request_raw)
        (self.model/'managed_save.request.json').unlink()
        slot=self.f.put(self.model/'managed_save.request.json.completed',request_raw)
        transition=copy.deepcopy(self.result['completed_slot_transition'])
        transition['request']=dict(actual_pin=request_pin,archive=self.f.put(self.root/'request-archive.json',request_raw))
        transition['after']=dict(actual_pin=slot,archive=self.f.put(self.root/'slot-archive.json',request_raw))
        self.result.update(tag=self.tag,checkpoint=checkpoint,completed_slot_transition=transition)
        out=Path(self.window['output'])
        self.f.put(out/'result.json',self.result)
        self.f.put(out/'first-durable-both-horizons.json',self.latch)
        self.f.put(out/'request-publication.json',dict(tag=self.tag,latch=self.latch,synthetic=True))
        self.window_pin=self.f.put(self.root/'window-job.json',self.window)
        self.owner=self.f.owner
        source=base/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py'
        config=dict(unit=self.owner['unit'],output=str(self.root/'synthetic-window-execution'),
            argv=['/usr/bin/python3.12','-I','-B',str(source),'--execute','--job',self.window_pin['path'],
                  '--job-sha256',self.window_pin['sha256']])
        closure=self.f.closure(self.owner,config,'synthetic-window-closure',self.f.start_mono,self.f.end_mono)
        self.job=dict(schema='robotron-quality32-original-candidate-CPU-preparation-v1',
            window_job=self.window_pin,window_source=self.reader.pin(source),
            window_owner=self.f.put(self.root/'synthetic-window-owner.json',self.owner),window_closure=closure,
            CPU_template=self.reader.pin(self.template),CPU_controller=self.reader.pin(prepare.HERE/'control_quality32_review_v1.py'),
            destination=str(self.root/'new-CPU-preparation'),CPU_unit='robotron-quality32-synthetic-candidate-CPU.service')
        self.job_pin=self.f.put(self.root/'root-preparation-job.json',self.job)

    def run_prepare(self):
        return prepare.prepare(self.job,self.job_pin,self.reader)

    def test_normal_metadata_copy_preserves_recipe_phase_actual_boot_and_original_bytes(self):
        before=self.reader.pin(self.result['checkpoint']['path'])
        report=self.run_prepare()
        self.assertEqual(report['status'],'PREPARED_NOT_EXECUTED');self.assertFalse(report['CPU_verified'])
        self.assertFalse(report['numerical_model_loaded']);self.assertFalse(report['quality_qualified'])
        self.assertEqual(self.reader.pin(before['path']),before)
        job=self.reader.read_pin(report['CPU_job']);config=self.reader.read_pin(report['CPU_controller_config'])
        self.assertEqual(job['clock_floor'],{key:self.trigger[key] for key in prepare.CLOCKS})
        self.assertEqual(job['phase_snapshot']['expected_phase'],self.oldtemplate['phase_snapshot']['expected_phase'])
        self.assertEqual(job['source_control_context']['held_recipe_context'],self.oldtemplate['source_control_context']['held_recipe_context'])
        self.assertEqual(job['phase_snapshot']['boot_checkpoint']['sha256'],prepare.BOOT_SHA)
        self.assertNotEqual(report['actual_boot_checkpoint_sha256'],report['phase_record_sha256'])
        self.assertEqual(job['verification_copy']['sha256'],before['sha256'])
        self.assertNotEqual(job['verification_copy']['identity']['inode'],before['identity']['inode'])
        self.assertEqual(job['verification_copy']['identity']['mode'],'0o444')
        self.assertIn('SendSIGKILL=no',config['properties']);self.assertEqual(config['unit'],self.job['CPU_unit'])
        self.assertEqual(config['argv'][4],str(prepare.GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'))
        self.assertNotIn('torch',sys.modules)

    def test_default_CLI_inert_with_missing_job(self):
        value=subprocess.run([sys.executable,'-I','-B',prepare.__file__,'--job','/missing'],capture_output=True,text=True,check=True,timeout=10)
        self.assertTrue(value.stdout.startswith('PLAN_ONLY:'))
        self.assertFalse(Path(self.job['destination']).exists())

    def test_original_failed_window_is_not_a_verification_authority(self):
        closure=self.reader.read_pin(self.job['window_closure']);closure['original_exit']=1
        self.job['window_closure']=self.f.put(self.job['window_closure']['path'],closure)
        self.job_pin=self.f.put(self.job_pin['path'],self.job)
        with self.assertRaises(ValueError):self.run_prepare()
        self.assertFalse(Path(self.job['destination']).exists())

    def test_changed_completed_slot_refuses_before_copy(self):
        self.f.put(self.model/'managed_save.request.json.completed',b'{"tag":"foreign"}\n')
        with self.assertRaisesRegex(ValueError,'completed-slot transition'):self.run_prepare()
        self.assertFalse(Path(self.job['destination']).exists())

    def test_changed_held_source_refuses_before_copy(self):
        self.f.put(self.model/'held-input.txt',b'changed')
        with self.assertRaisesRegex(ValueError,'held window input'):self.run_prepare()
        self.assertFalse(Path(self.job['destination']).exists())

    def test_declared_horizon_must_match_actual_original_API_counters(self):
        self.result['progress']['learner_frames']+=1
        self.latch['progress']=copy.deepcopy(self.result['progress'])
        out=Path(self.window['output']);self.f.put(out/'result.json',self.result)
        self.f.put(out/'first-durable-both-horizons.json',self.latch)
        with self.assertRaisesRegex(ValueError,'Actual trigger/baseline exposure'):self.run_prepare()
        self.assertFalse(Path(self.job['destination']).exists())

    def test_existing_preparation_is_never_overwritten(self):
        report=self.run_prepare();before=Path(report['CPU_job']['path']).read_bytes()
        with self.assertRaisesRegex(ValueError,'New owned CPU preparation'):self.run_prepare()
        self.assertEqual(Path(report['CPU_job']['path']).read_bytes(),before)

    def test_original_command_must_bind_script_job_source_and_owner(self):
        closure=self.reader.read_pin(self.job['window_closure']);record=closure['full_original_archives'][0]
        fields=dict(row.split('=',1) for row in self.reader.read_pin(record['stdout'],as_json=False).decode().splitlines() if '=' in row)
        prepare.validate_window_command(fields,self.owner,self.window_pin,self.job['window_source'])
        for key in ('script','job','unit'):
            value=copy.deepcopy(fields)
            if key=='script':value['ExecStart']=value['ExecStart'].replace(self.job['window_source']['path'],'/foreign.py')
            elif key=='job':value['ExecStart']=value['ExecStart'].replace(self.window_pin['sha256'],'0'*64)
            else:value['Id']='foreign.service'
            with self.subTest(key=key),self.assertRaises(ValueError):
                prepare.validate_window_command(value,self.owner,self.window_pin,self.job['window_source'])

    def test_missing_horizon_changed_role_or_boolean_counters_rejected(self):
        for mutation in ('short','applied','bool','role','slot','qualified','trigger'):
            window=copy.deepcopy(self.window);result=copy.deepcopy(self.result);latch=copy.deepcopy(self.latch);trigger=copy.deepcopy(self.trigger)
            if mutation=='short':result['progress']['learner_accepted']=7999999
            elif mutation=='applied':result['progress']['applied_updates']=0
            elif mutation=='bool':result['progress']['amp_skips']=False
            elif mutation=='role':result['tag']='different'
            elif mutation=='slot':window['quality_precommit']['all_slots'].pop()
            elif mutation=='qualified':result['quality_qualified']=True
            else:trigger['measurement_active']=True
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                prepare.validate_capture(window,result,latch,trigger)


if __name__=='__main__':
    unittest.main()
