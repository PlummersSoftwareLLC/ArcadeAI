"""SOURCE-AUTHORED/UNEXECUTED stdlib metadata guards; no numerical body tests."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import verify_phase_snapshot as verifier


class PhaseContracts(unittest.TestCase):
    def phase_case(self):
        boot = dict(training_steps=10, optimized_samples=100, learner_frame_count=1000, frame_count=2000)
        origin = dict(path='/historical/models/latest.pt', sha256='a'*64, bytes=250000000, clocks=boot)
        expected = dict(metric='kl', phase_id='phase_A', root_precommit_sha256='b'*64,
            founder_phase_record_sha256='c'*64, last_resume_record_sha256=None, started_from=origin, valid=True)
        phase = dict(schema=verifier.PHASE_SCHEMA, metric='kl', phase_id='phase_A', root_precommit_sha256='b'*64,
            phase_record_sha256='c'*64, last_resume_record_sha256=None, started_from=copy.deepcopy(origin),
            predecessor=None, initial_tree='mixed/unknown', priority_update_calls=3, ring_rows_submitted=12000,
            last_diagnostics=None, last_rejected_diagnostics=None, valid=True, invalid_reason=None)
        current = {key:value+5 for key,value in boot.items()}
        return dict(current, priority_metric_phase=phase), expected, boot

    def test_default_plan_does_not_read_or_load_helpers(self):
        with patch.object(verifier, 'load_base', side_effect=AssertionError('no helper')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('no input')), \
                patch.object(Path, 'read_text', side_effect=AssertionError('no input')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(verifier.main([]), 0)
        self.assertIn('PLAN_ONLY', output.getvalue())

    def test_strict_body_only_signature_and_callback_and_one_load(self):
        original = verifier.ORIGINAL_PATH.read_bytes()
        adapted = verifier.STRICT_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), verifier.ORIGINAL_SHA256)
        self.assertEqual(hashlib.sha256(adapted).hexdigest(), verifier.STRICT_SHA256)
        restored = adapted.replace(b'def validate_checkpoint(path, floor, evidence, *, metadata_callback=None):',
                                  b'def validate_checkpoint(path, floor, evidence):')
        restored = restored.replace(b'    if metadata_callback is not None:\n        metadata_callback(checkpoint, evidence)\n', b'')
        self.assertEqual(restored, original)
        self.assertEqual(adapted.count(b'torch.load('), 1)
        self.assertLess(adapted.index(b"f'Private source changed: {name}'"), adapted.index(b'metadata_callback(checkpoint, evidence)'))

    def test_start_metadata_accepts_overshoot_and_nonzero_updates(self):
        checkpoint, expected, boot = self.phase_case(); evidence = {}
        verifier.verify_phase(checkpoint, evidence, expected, boot, boot, 'start')
        self.assertEqual(evidence['phase_current_overshoot_from_actual_boot'], dict.fromkeys(verifier.CLOCKS, 5))
        self.assertEqual(evidence['saved_priority_metric_phase']['priority_update_calls'], 3)
        checkpoint['priority_metric_phase']['metric'] = 'ce'
        self.assertEqual(evidence['saved_priority_metric_phase']['metric'], 'kl')

    def test_wrong_phase_core_founder_record_validity_or_origin_is_refused(self):
        for field, value in [('metric','ce'), ('phase_id','other'), ('root_precommit_sha256','d'*64),
                             ('phase_record_sha256','e'*64), ('last_resume_record_sha256','f'*64),
                             ('valid',False), ('invalid_reason','error')]:
            checkpoint, expected, boot = self.phase_case(); checkpoint['priority_metric_phase'][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                verifier.verify_phase(checkpoint, {}, expected, boot, boot, 'start')
        for changed in ('sha256', 'clocks'):
            checkpoint, expected, boot = self.phase_case()
            if changed == 'sha256':checkpoint['priority_metric_phase']['started_from']['sha256'] = 'd'*64
            else:checkpoint['priority_metric_phase']['started_from']['clocks']['training_steps'] += 1
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                verifier.verify_phase(checkpoint, {}, expected, boot, boot, 'start')

    def test_each_saved_current_clock_must_cover_actual_boot_and_floor(self):
        for key in verifier.CLOCKS:
            checkpoint, expected, boot = self.phase_case();checkpoint[key] = boot[key]-1
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                verifier.verify_phase(checkpoint, {}, expected, boot, boot, 'start')

    def test_resume_keeps_original_founder_separate_from_newest_boot(self):
        checkpoint, expected, founder_boot = self.phase_case()
        previous = copy.deepcopy(checkpoint['priority_metric_phase'])
        previous['predecessor'] = dict(phase_id='older_CE', metric='ce', valid=True)
        newest_boot = {key:value+100 for key,value in founder_boot.items()}
        expected['last_resume_record_sha256'] = 'd'*64
        checkpoint.update({key:value+1 for key,value in newest_boot.items()})
        phase = checkpoint['priority_metric_phase'];phase['last_resume_record_sha256'] = 'd'*64
        phase['predecessor'] = copy.deepcopy(previous['predecessor']);phase['priority_update_calls'] += 2
        evidence = {};verifier.verify_phase(checkpoint, evidence, expected, newest_boot, newest_boot, 'resume', previous)
        self.assertEqual(evidence['saved_priority_metric_phase']['started_from']['clocks'], founder_boot)
        self.assertEqual(evidence['phase_current_overshoot_from_actual_boot'], dict.fromkeys(verifier.CLOCKS, 1))
        phase['priority_update_calls'] = previous['priority_update_calls']-1
        with self.assertRaises(RuntimeError):verifier.verify_phase(checkpoint, {}, expected, newest_boot, newest_boot, 'resume', previous)


class AcquisitionContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='phase-cpu-wrapper-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name); self.base = verifier.load_base()
        self.writes = 0
        self.game = self.root/'Game'; (self.game/'Scripts/dqn').mkdir(parents=True)
        self.models = self.game/'models_dqn';self.models.mkdir();(self.models/'managed-checkpoints').mkdir()
        self.archives = self.root/'archives';self.archives.mkdir()
        self.base.GAME = self.game
        self.owner = dict(pid=1234,starttime_ticks=5678,unit='robotron-managed-phase-test-trainer.service',
            invocation_id='a'*32,cgroup='/user.slice/robotron-managed-phase-test-trainer.service')
        self.clock = dict(training_steps=10,optimized_samples=100,learner_frame_count=1000,frame_count=2000)
        self.evidence = {};self.job,self.spec,self.proof = self.fixture()

    def pin(self,path):
        value = self.base.fingerprint(path)
        return dict(path=value['path'],sha256=value['sha256'],bytes=value['bytes'],
            identity={key:value[key] for key in ('device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink')})

    def write(self,name,value):
        self.writes += 1
        path=self.archives/('%03d-'%self.writes+name)
        path.write_text(json.dumps(value,sort_keys=True)+'\n');path.chmod(0o444)
        return self.pin(path)

    def historical(self,actual,value,name):
        actual.write_text(json.dumps(value,sort_keys=True)+'\n')
        return dict(actual_pin=self.pin(actual),archive=self.write(name,value))

    def fixture(self):
        sources={};model_package={}
        for name in verifier.SOURCE_NAMES:
            current=self.game/'Scripts/dqn'/name;current.write_text('private source '+name+'\n')
            archive=self.archives/(name+'.copy');archive.write_bytes(current.read_bytes());archive.chmod(0o444)
            sources[name]=dict(current=self.pin(current),archive=self.pin(archive))
            if name in self.base.MODEL_NAMES:model_package[name]=sources[name]['current']
        boot=dict(path=str(self.models/'robotron_dqn_latest.pt'),sha256='a'*64,bytes=250000000)
        boot_proof=self.write('boot.json',dict(status='PASS',sha256=boot['sha256'],bytes=boot['bytes'],clocks=self.clock))
        record=dict(schema='robotron-priority-metric-start-v1',phase_id='phase_A',metric='kl',action='start',
            previous_metric='unknown',checkpoint=boot,model_dir=str(self.models),root_precommit_sha256='b'*64)
        record_pin=self.write('phase-record.json',record)
        expected=dict(metric='kl',phase_id='phase_A',root_precommit_sha256='b'*64,
            founder_phase_record_sha256=record_pin['sha256'],last_resume_record_sha256=None,
            started_from=dict(boot,clocks=self.clock),valid=True)
        source=self.models/'managed-checkpoints'/'startup_tag.pt';source.write_bytes(b'private text, never a model')
        request=self.historical(self.models/'managed_save.request.json',dict(tag='startup_tag'),'request.json')
        completed=self.historical(self.models/'managed_save.request.json.completed',dict(tag='startup_tag'),'completed.json')
        transition=dict(before=None,request=request,after=completed,before_unix_s=1,request_unix_s=2,after_unix_s=3)
        spec=dict(purpose='startup',owner=self.owner,observed_clients=0,phase_record=record_pin,
            boot_checkpoint=boot,boot_verification=boot_proof,expected_phase=expected,sources=sources)
        job=dict(experiment='test_phase',source=self.pin(source),clock_floor=self.clock,
            source_control_context=dict(model_package=model_package),phase_snapshot=spec)
        proof=dict(schema=verifier.ACQUISITION_SCHEMA,purpose='startup',experiment='test_phase',model_dir=str(self.models),
            owner_before=self.owner,owner_after=self.owner,source_checkpoint={k:job['source'][k] for k in ('path','sha256','bytes')},
            clock_floor=self.clock,phase_record_sha256=record_pin['sha256'],boot_checkpoint=boot,client_count=0,
            tag='startup_tag',completed_slot_transition=transition,stopped_absence=None)
        return job,spec,proof

    def call(self):
        self.evidence = {}
        self.spec['acquisition']=self.write('acquisition.json',self.proof)
        return verifier.check_acquisition(self.job,self.base,self.evidence,self.models)

    def test_startup_client_zero_and_reused_current_completed_slot_are_honest(self):
        (self.models/'managed_save.request.json.completed').write_text('{"tag":"later_request"}')
        self.call()
        self.assertEqual(self.evidence['phase_acquisition']['client_count'],0)
        self.assertNotIn(str(self.models/'managed_save.request.json.completed'),
            [value['path'] for value in self.evidence['bound_files'].values()])

    def test_loss_source_missing_or_wrong_archive_is_refused(self):
        with self.subTest(problem='missing'):
            entry=self.spec['sources'].pop('loss_kernel.py')
            with self.assertRaises(RuntimeError):self.call()
            self.spec['sources']['loss_kernel.py']=entry
        with self.subTest(problem='wrong bytes'):
            archive=self.write('wrong-loss.py',dict(wrong='loss'))
            self.spec['sources']['loss_kernel.py']['archive']=archive
            with self.assertRaises(RuntimeError):self.call()

    def test_source_archive_writable_or_actual_client_scope_wrong_is_refused(self):
        archive=Path(self.spec['sources']['config.py']['archive']['path']);archive.chmod(0o644)
        self.spec['sources']['config.py']['archive']=self.pin(archive)
        with self.assertRaises(RuntimeError):self.call()
        archive.chmod(0o444);self.spec['sources']['config.py']['archive']=self.pin(archive)
        self.proof['client_count']=192
        with self.assertRaises(RuntimeError):self.call()

    def test_stale_completed_tag_or_wrong_request_is_not_a_new_capture(self):
        before=self.historical(self.models/'managed_save.request.json.completed',dict(tag='startup_tag'),'before.json')
        self.proof['completed_slot_transition']['before']=before
        with self.assertRaises(RuntimeError):self.call()
        self.proof['completed_slot_transition']['before']=None
        self.proof['completed_slot_transition']['request']=self.historical(
            self.models/'managed_save.request.json',dict(tag='wrong'),'wrong-request.json')
        with self.assertRaises(RuntimeError):self.call()

    def test_unknown_owner_or_boot_proof_mismatch_is_refused(self):
        self.proof['owner_after']=dict(self.owner,pid=9999)
        with self.assertRaises(RuntimeError):self.call()
        self.proof['owner_after']=self.owner
        self.spec['boot_verification']=self.write('wrong-boot.json',dict(status='PASS',sha256='c'*64,bytes=250000000,clocks=self.clock))
        with self.assertRaises(RuntimeError):self.call()

    def test_newest_stopped_uses_known_absence_without_insurance_or_live192(self):
        latest=self.models/'robotron_dqn_latest.pt';latest.write_bytes(b'newest private text')
        self.job['source']=self.pin(latest);self.spec['purpose']='newest_stopped'
        self.proof.update(purpose='newest_stopped',source_checkpoint={k:self.job['source'][k] for k in ('path','sha256','bytes')},
            tag=None,completed_slot_transition=None)
        absence=dict(schema=self.base.ABSENCE_SCHEMA,trainer=self.owner,unit_main_pid=0,unit_active_state='inactive',
            old_process_absent=True,owned_cgroup_empty=True,latest_path=str(latest))
        self.proof['stopped_absence']=self.write('absence.json',absence)
        with patch.object(self.base,'exact_absence',return_value=dict(old_PID_state='absent')) as check:
            self.call();check.assert_called_once_with(self.owner)
        self.assertIn('absence_before',self.evidence)
        self.assertNotIn('insurance',self.evidence)


if __name__ == '__main__':
    unittest.main()
