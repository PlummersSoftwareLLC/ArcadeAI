"""Authored only: stdlib wrapper guards, no checkpoint or numerical fixtures."""
import contextlib
import copy
from datetime import datetime
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

SOURCE = Path(__file__).with_name('verify_candidate_checkpoint.py')


def load_wrapper():
    spec = importlib.util.spec_from_file_location('_candidate_guard_test_module', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixtures(module):
    model_dir = Path('/fixture/models_dqn')
    tag = 'fresh3-448M'
    source = str(model_dir / 'managed-checkpoints' / (tag + '.pt'))
    trainer = dict(pid=101, starttime_ticks=202,
        unit='robotron-managed-run-26-test-trainer.service', invocation_id='a' * 32,
        cgroup='/user.slice/robotron-managed-run-26-test-trainer.service')
    gate_owner = dict(pid=303, starttime_ticks=404,
        unit='robotron-checkpoint-448M-owned.service', invocation_id='b' * 32,
        cgroup='/user.slice/robotron-checkpoint-448M-owned.service')
    pin = lambda name: dict(path='/fixture/' + name, sha256='c' * 64, bytes=12, identity={})
    gate_pin, completion_pin, owner_pin = pin('gate.json'), pin('completion.json'), pin('owner.json')
    completion_pin['path'] = str(model_dir / 'managed_save.request.json.completed')
    job = dict(experiment='best10M-fresh3-eps10-cap8-nosmooth',
        source=dict(path=source, sha256='d' * 64, bytes=275000001),
        candidate=dict(tag=tag, target_learner_frames=452629023,
            gate=gate_pin, completed_request=completion_pin, capture_execution=owner_pin))
    gate = dict(tag=tag, target=452629023, experiment=job['experiment'], checkpoint=source,
        trigger_snapshot=dict(training_steps=2100000, optimized_samples=7200000000,
            learner_frame_count=452629101, frame_count=906000000, client_count=192),
        saved_utc='2026-10-17T10:00:00+00:00')
    owner = dict(schema=module.CAPTURE_SCHEMA, trainer_before=trainer, trainer_after=dict(trainer),
        experiment=job['experiment'], model_dir=str(model_dir), tag=tag, target_learner_frames=452629023,
        gate_path=gate_pin['path'], gate_sha256=gate_pin['sha256'], checkpoint_path=source,
        checkpoint_sha256=job['source']['sha256'], checkpoint_bytes=job['source']['bytes'],
        gate_unit=gate_owner, original_exec_code=1, original_exit=0, original_result='success',
        original_terminal_archived_before_release=True, terminal_archive=pin('terminal.json'))
    documents = {gate_pin['path']: gate, completion_pin['path']: {'tag': tag}, owner_pin['path']: owner}
    checked = []
    def integer(value, name, minimum=0):
        module.require(type(value) is int and value >= minimum, name)
        return value
    def trainer_identity(value):
        module.require(set(value) == set(trainer) and type(value['pid']) is int and value['pid'] > 0,
                       'trainer identity')
        return value
    def check_pin(value, evidence, label, **kwargs):
        checked.append((label, value))
        return value
    base = SimpleNamespace(CLOCKS=('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count'),
        datetime=datetime, integer=integer, trainer_identity=trainer_identity,
        pinned_json=lambda value, evidence, label: documents[value['path']], check_pin=check_pin)
    return job, gate, owner, documents, base, model_dir, checked


class CandidateGuardTests(unittest.TestCase):
    def setUp(self):
        self.module = load_wrapper()
        self.job, self.gate, self.owner, self.docs, self.base, self.model_dir, self.checked = fixtures(self.module)

    def validate(self):
        evidence = {}
        result = self.module.validate_candidate(self.job, self.base, evidence, self.model_dir)
        return result, evidence

    def test_real_gate_shape_supplies_exact_four_clock_floor(self):
        floor, evidence = self.validate()
        self.assertEqual(floor, {key: self.gate['trigger_snapshot'][key] for key in self.base.CLOCKS})
        self.assertEqual(floor['learner_frame_count'], 452629101)
        self.assertNotIn('host_pipeline', self.gate['trigger_snapshot'])
        self.assertEqual(self.checked, [('candidate_original_terminal_archive', self.owner['terminal_archive'])])
        self.assertEqual(evidence['candidate_capture_execution'], self.owner)

    def test_gate_target_tag_branch_and_path_each_reject(self):
        for key, wrong in [('target', 388629023), ('tag', 'fresh3-384M'),
                           ('experiment', 'different'), ('checkpoint', '/fixture/latest.pt')]:
            original = self.gate[key]
            with self.subTest(key=key):
                self.gate[key] = wrong
                with self.assertRaises(RuntimeError): self.validate()
            self.gate[key] = original

    def test_early_target_missing_clock_and_wrong_clients_reject(self):
        original = copy.deepcopy(self.gate['trigger_snapshot'])
        variants = [dict(original, learner_frame_count=452629022), dict(original, client_count=191),
                    dict(original, client_count=True), {key:value for key,value in original.items() if key != 'frame_count'}]
        for trigger in variants:
            with self.subTest(trigger=trigger):
                self.gate['trigger_snapshot'] = trigger
                with self.assertRaises(RuntimeError): self.validate()
        self.gate['trigger_snapshot'] = original

    def test_completion_slot_and_tag_are_actual(self):
        completion = self.job['candidate']['completed_request']
        self.docs[completion['path']] = {'tag': 'fresh3-384M'}
        with self.assertRaises(RuntimeError): self.validate()
        self.docs[completion['path']] = {'tag': 'fresh3-448M'}
        completion['path'] = '/fixture/archived-completed-copy.json'
        with self.assertRaises(RuntimeError): self.validate()

    def test_moving_latest_is_never_eligible(self):
        self.job['source']['path'] = str(self.model_dir / 'robotron_dqn_latest.pt')
        with self.assertRaises(RuntimeError): self.validate()

    def test_owner_replacement_or_candidate_identity_drift_reject(self):
        original = copy.deepcopy(self.owner)
        mutations = [('trainer_after', dict(self.owner['trainer_before'], pid=999)),
            ('gate_sha256', 'e' * 64), ('checkpoint_sha256', 'f' * 64),
            ('checkpoint_bytes', self.owner['checkpoint_bytes'] + 1), ('target_learner_frames', 388629023)]
        for key, wrong in mutations:
            with self.subTest(key=key):
                self.owner[key] = wrong
                with self.assertRaises(RuntimeError): self.validate()
            self.owner.clear(); self.owner.update(copy.deepcopy(original))

    def test_original_helper_exit_and_archive_are_mandatory(self):
        original = dict(self.owner)
        for key, wrong in [('original_exit', 1), ('original_exit', False), ('original_exec_code', 2),
                ('original_exec_code', True), ('original_result', 'timeout'),
                ('original_terminal_archived_before_release', False)]:
            with self.subTest(key=key, wrong=wrong):
                self.owner[key] = wrong
                with self.assertRaises(RuntimeError): self.validate()
            self.owner.clear(); self.owner.update(original)

    def test_exact_gate_unit_identity_is_mandatory(self):
        original = dict(self.owner['gate_unit'])
        for key, wrong in [('pid', 0), ('starttime_ticks', 0), ('unit', 'unrelated.service'),
                           ('invocation_id', 'unknown'), ('cgroup', '/user.slice/wrong.service')]:
            with self.subTest(key=key):
                self.owner['gate_unit'][key] = wrong
                with self.assertRaises(RuntimeError): self.validate()
            self.owner['gate_unit'] = dict(original)

    def test_archive_pin_errors_propagate_without_a_floor(self):
        self.base.check_pin = mock.Mock(side_effect=OSError('preserved terminal missing'))
        with self.assertRaisesRegex(OSError, 'terminal missing'): self.validate()

    def test_default_literal_plan_reads_no_paths_or_helpers(self):
        stdout = io.StringIO()
        with mock.patch.object(self.module, 'load_base', side_effect=AssertionError('helper read')), \
             mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('file read')), \
             mock.patch.object(Path, 'resolve', side_effect=AssertionError('path resolution')), \
             contextlib.redirect_stdout(stdout):
            self.assertEqual(self.module.main([]), 0)
        self.assertTrue(stdout.getvalue().startswith('PLAN_ONLY:'))


if __name__ == '__main__':
    unittest.main()
