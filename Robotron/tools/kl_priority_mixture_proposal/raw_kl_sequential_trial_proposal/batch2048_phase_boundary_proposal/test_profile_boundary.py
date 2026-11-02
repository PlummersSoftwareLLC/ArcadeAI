"""Authored, unexecuted pure metadata guards; synthetic PINs are not evidence."""
import contextlib
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from . import profile_boundary as helper


def spec(mode='activate_batch2048'):
    return helper.direction(mode, copy.deepcopy(helper.PROFILE_BINDING))


def metadata(path='/synthetic/record.json', sha='a'*64, size=100):
    return dict(path=path, sha256=sha, bytes=size,
        identity=dict(device=1, inode=2, bytes=size, mtime_ns=3, ctime_ns=4,
            mode='0o444', uid=1001, nlink=1))


def environment(batch):
    return dict(DQN_BATCH_SIZE=str(batch), DQN_PER_PRIORITY_METRIC='ce',
        DQN_PRIORITY_PHASE_RECORD='/synthetic/old-record.json',
        DQN_PRIORITY_PHASE_RECORD_SHA256='b'*64, DQN_N_STEP='3',
        DQN_MAX_SAMPLES_PER_FRAME='8', KEEP_RECIPE='unchanged')


def clocks():
    return dict(training_steps=100, optimized_samples=409600,
        learner_frame_count=10000, frame_count=20000)


def boot(batch):
    checkpoint = dict(path='/synthetic/models_dqn/robotron_dqn_latest.pt',
        sha256='c'*64, bytes=275000000)
    proof = dict(status='PASS', sha256=checkpoint['sha256'], bytes=checkpoint['bytes'],
        clocks=clocks(), phase_metadata_verified=True,
        root_job=dict(phase_snapshot=dict(purpose='newest_stopped')),
        held_recipe_context=dict(batch_size=batch),
        saved_priority_metric_phase=dict(schema='robotron-priority-metric-phase-v1',
            phase_id='synthetic_previous_ce', metric='ce', valid=True))
    return checkpoint, proof


def record_args(mode='activate_batch2048'):
    boundary = spec(mode)
    checkpoint, proof = boot(boundary['before_batch_size'])
    return dict(spec=boundary, phase_id='synthetic_new_ce', root_precommit_sha256='d'*64,
        model_dir='/synthetic/models_dqn', checkpoint=checkpoint,
        boot_proof=proof, required_floor=clocks())


def csv(batch):
    return dict(batch_size=batch, replay_sample_cap=8, replay_dropped=0, utc='synthetic')


class ProfileBoundaryContracts(unittest.TestCase):
    def test_default_has_no_runtime_file_or_transition_actions(self):
        with patch('builtins.open', side_effect=AssertionError('no file IO')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('no file IO')), \
                contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(helper.main(), 0)
        output = json.loads(stream.getvalue())
        self.assertFalse(output['actual_transition'])
        self.assertFalse(output['whole_trial_ready'])
        self.assertFalse(output['imports_runtime'])

    def test_only_two_directions_and_exact_profile_types_are_accepted(self):
        self.assertEqual((spec()['before_batch_size'], spec()['after_batch_size']), (4096, 2048))
        returning = spec('return_batch4096')
        self.assertEqual((returning['before_batch_size'], returning['after_batch_size']), (2048, 4096))
        for mode in ('activate_kl', 'return_ce', 'unknown'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                spec(mode)
        bad = copy.deepcopy(helper.PROFILE_BINDING)
        bad['value']['batch_size'] = 2048.0
        with self.assertRaises(ValueError):
            helper.direction('activate_batch2048', bad)
        changed = spec(); changed['after_batch_size'] = 2048.0
        with self.assertRaises(ValueError):
            helper.checked_spec(changed)

    def test_selected_environment_changes_only_batch_and_new_phase_pointers(self):
        for mode in helper.MODES:
            boundary = spec(mode); before = environment(boundary['before_batch_size'])
            before_copy = copy.deepcopy(before); pin = metadata()
            after = helper.selected_environment(before, boundary, pin)
            self.assertEqual(before, before_copy)
            self.assertEqual(after['DQN_BATCH_SIZE'], str(boundary['after_batch_size']))
            self.assertEqual(after['DQN_PER_PRIORITY_METRIC'], 'ce')
            changed = {key for key in before if before[key] != after[key]}
            self.assertEqual(changed, {'DQN_BATCH_SIZE', 'DQN_PRIORITY_PHASE_RECORD',
                'DQN_PRIORITY_PHASE_RECORD_SHA256'})
            self.assertEqual(after['KEEP_RECIPE'], 'unchanged')
            override = helper.override_environment(before, boundary, pin)
            self.assertEqual(set(override), {'DQN_BATCH_SIZE', *helper.PHASE_KEYS})
            self.assertEqual(override, {key: after[key] for key in override})

    def test_wrong_before_metric_batch_or_capture_session_is_refused(self):
        for key, value in (('DQN_BATCH_SIZE', '2048'), ('DQN_PER_PRIORITY_METRIC', 'kl'),
                ('DQN_RECOMPUTED_CE_CAPTURE_DIR', '/synthetic/capture'),
                ('DQN_EXECUTED_CE_TRACE_DIR', '/synthetic/trace')):
            before = environment(4096); before[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                helper.selected_environment(before, spec(), metadata())

    def test_both_directions_start_new_ce_from_actual_newest_cpu_state(self):
        for mode in helper.MODES:
            args = record_args(mode); record = helper.start_record(**args)
            self.assertEqual(record['metric'], 'ce')
            self.assertEqual(record['previous_metric'], 'ce')
            self.assertEqual(record['action'], 'start')
            self.assertEqual(record['checkpoint'], args['checkpoint'])
            self.assertEqual(record['root_precommit_sha256'], args['root_precommit_sha256'])
            expected = helper.expected_start(record, metadata(), args['boot_proof'])
            self.assertEqual(expected['started_from'], dict(args['checkpoint'], clocks=clocks()))
            self.assertIsNone(expected['last_resume_record_sha256'])

    def test_no_old_boot_wrong_profile_candidate_cpu_or_kl_phase_can_start(self):
        cases = []
        args = record_args(); args['checkpoint']['path'] = '/synthetic/old-insurance.pt'; cases.append(args)
        args = record_args(); args['boot_proof']['sha256'] = 'e'*64; cases.append(args)
        args = record_args(); args['boot_proof']['held_recipe_context']['batch_size'] = 2048; cases.append(args)
        args = record_args(); args['boot_proof']['root_job']['phase_snapshot']['purpose'] = 'candidate'; cases.append(args)
        args = record_args(); args['boot_proof']['phase_metadata_verified'] = False; cases.append(args)
        args = record_args(); args['boot_proof']['saved_priority_metric_phase']['metric'] = 'kl'; cases.append(args)
        args = record_args(); args['boot_proof']['saved_priority_metric_phase']['valid'] = False; cases.append(args)
        args = record_args(); args['phase_id'] = 'synthetic_previous_ce'; cases.append(args)
        for index, args in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                helper.start_record(**args)

    def test_all_four_forward_floors_prevent_newest_state_rollback(self):
        for mode in helper.MODES:
            for key in helper.CLOCKS:
                args = record_args(mode)
                args['required_floor'][key] += 1
                with self.subTest(mode=mode, key=key), self.assertRaises(ValueError):
                    helper.start_record(**args)

    def test_startup0_preserves_before4096_csv_and_running_requires2048_plan(self):
        baseline = csv(4096); original = copy.deepcopy(baseline)
        startup = helper.csv_guard_plan(spec(), 'startup0', baseline, {}, environment(2048))
        self.assertEqual(startup['configured_batch_size'], 2048)
        self.assertEqual(startup['batch_size'], 4096)
        self.assertEqual(startup['csv_scope'], 'pretransition_baseline')
        self.assertEqual(startup['initial_snapshot']['csv'], original)
        running = helper.csv_guard_plan(spec(), 'running192', baseline, {}, environment(2048))
        self.assertEqual(running['batch_size'], 2048)
        self.assertEqual(running['csv_scope'], 'current_producer')
        self.assertEqual(baseline, original)

    def test_return_startup_csv_remains2048_until_real4096_producer(self):
        returning = spec('return_batch4096'); baseline = csv(2048)
        before = helper.csv_guard_plan(returning, 'before', baseline, {}, environment(2048))
        self.assertEqual(before['batch_size'], 2048)
        startup = helper.csv_guard_plan(returning, 'startup0', baseline, {}, environment(4096))
        self.assertEqual((startup['batch_size'], startup['configured_batch_size']), (2048, 4096))
        running = helper.csv_guard_plan(returning, 'running192', baseline, {}, environment(4096))
        self.assertEqual(running['batch_size'], 4096)
        for baseline_batch, env_batch in ((4096, 4096), (2048, 2048)):
            with self.subTest(baseline=baseline_batch, env=env_batch), self.assertRaises(ValueError):
                helper.csv_guard_plan(returning, 'startup0', csv(baseline_batch), {}, environment(env_batch))

    def test_phase_cpu_uses_actual_producer_profile_and_has_no_insurance_forgery(self):
        binding = helper.PROFILE_BINDING['pin']
        profile = metadata(binding['path'], binding['sha256'], binding['bytes'])
        producer = metadata('/synthetic/producer-observation.json', 'f'*64)
        for mode in helper.MODES:
            boundary = spec(mode)
            for purpose in ('startup', 'candidate', 'newest_stopped'):
                expected = boundary['before_batch_size'] if purpose == 'newest_stopped' else boundary['after_batch_size']
                if expected == 4096:
                    result = helper.phase_cpu_boundary(boundary, purpose)
                    self.assertEqual(result['additional_job_fields'], {})
                    self.assertEqual(result['job_schema'], 'robotron-phase-snapshot-checkpoint-CPU-job-v1')
                else:
                    result = helper.phase_cpu_boundary(boundary, purpose,
                        profile_pin=profile, producer_observation=producer)
                    context = result['additional_job_fields']['batch2048_context']
                    self.assertEqual(context['profile'], profile)
                    self.assertEqual(context['producer_observation'], producer)
                    self.assertEqual(context['role'], 'treatment_startup' if purpose == 'startup' else purpose)
                    self.assertEqual(result['result_schema'], 'robotron-batch2048-phase-snapshot-checkpoint-CPU-result-v1')
                self.assertEqual(result['batch_size'], expected)
        with self.assertRaises(ValueError):
            helper.phase_cpu_boundary(spec(), 'early_insurance',
                profile_pin=profile, producer_observation=producer)
        writable = copy.deepcopy(producer); writable['identity']['mode'] = '0o644'
        with self.assertRaises(ValueError):
            helper.phase_cpu_boundary(spec(), 'startup', profile_pin=profile,
                producer_observation=writable)
        with self.assertRaises(ValueError):
            helper.phase_cpu_boundary(spec(), 'newest_stopped', profile_pin=profile,
                producer_observation=producer)


if __name__ == '__main__':
    unittest.main()
