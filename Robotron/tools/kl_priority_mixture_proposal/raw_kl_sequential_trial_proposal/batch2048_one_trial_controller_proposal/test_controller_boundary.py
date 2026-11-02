"""Authored, unexecuted stdlib guards for the unconsumed CE2048 boundary only."""
import ast
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
OLD = HERE.parent / 'live_one_trial_installed_ce_revision2_proposal'


def source_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


controller = source_module('_CE2048_controller_guards', HERE / 'run_one_trial.py')
deadline = source_module('_CE2048_deadline_guards', HERE / 'deadline_guard.py')


def profile_pin():
    return dict(path=deadline.PROFILE_PATH, sha256=deadline.PROFILE_SHA,
        bytes=deadline.PROFILE_BYTES, identity={'test_fixture': True})


def authorized():
    profile = profile_pin()
    binding = dict(pin={k: profile[k] for k in ('path', 'sha256', 'bytes')},
        value=copy.deepcopy(deadline.PROFILE_VALUE))
    core = dict(activation_authorized=True, status=deadline.FINAL_CORE_STATUS,
        mode='activate_batch2048', phase_id='synthetic_CE2048', batch_profile=profile)
    activation = dict(mode='activate_batch2048', phase_id='synthetic_CE2048',
        batch_boundary=dict(mode='activate_batch2048', before_batch_size=4096,
            after_batch_size=2048, priority_metric='ce', profile_binding=binding))
    return core, activation


class ControllerBoundaryContracts(unittest.TestCase):
    def test_literal_defaults_and_execute_refusal_precede_reads_imports_or_arm(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('input read')):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(controller.main([]), 0)
                self.assertEqual(deadline.main([]), 0)
            for module in (controller, deadline):
                with self.assertRaisesRegex(RuntimeError, 'UNCONSUMED CE2048'):
                    module.main(['--execute'])

    def test_authorization_consumes_exact_real_boundary_shape_and_profile(self):
        core, activation = authorized()
        reads = []
        deadline.validate_authorization(core, activation,
            read=lambda value: reads.append(value) or copy.deepcopy(deadline.PROFILE_VALUE))
        self.assertTrue(reads)
        self.assertTrue(all(value == profile_pin() for value in reads))
        self.assertNotIn('before_metric', activation['batch_boundary'])

    def test_wrong_mode_metric_batch_profile_and_draft_authorization_refuse(self):
        changes = [
            ('core', 'mode', 'activate_kl'), ('core', 'activation_authorized', False),
            ('core', 'status', 'DRAFT'), ('boundary', 'priority_metric', 'kl'),
            ('boundary', 'after_batch_size', 4096),
        ]
        for where, key, value in changes:
            with self.subTest(where=where, key=key):
                core, activation = authorized()
                (core if where == 'core' else activation['batch_boundary'])[key] = value
                with self.assertRaises(RuntimeError):
                    deadline.validate_authorization(core, activation,
                        read=lambda _: copy.deepcopy(deadline.PROFILE_VALUE))
        core, activation = authorized()
        core['batch_profile']['sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'Exact immutable'):
            deadline.validate_authorization(core, activation,
                read=lambda _: self.fail('wrong profile must not be read'))

    def test_actual_observer_job_adds2048_and_exact_profile_without_reanchoring(self):
        profile = dict(pin={k: profile_pin()[k] for k in ('path', 'sha256', 'bytes')},
            value=copy.deepcopy(deadline.PROFILE_VALUE))
        start = dict(boot_id='synthetic_boot', monotonic_s=100, unix_s=1000,
            phase_record={'sha256': 'p'}, trial_core={'sha256': 'c'})
        before = {'original_physical_baseline': 'kept'}
        activation = dict(start_request='start', before_resume_api_PIN='before', owner={'pid': 9},
            boot_four_clocks={'learner_frame_count': 11}, healthy192_monotonic_s=110,
            trial_core=start['trial_core'], phase_record=start['phase_record'])
        seen = []
        horizon = SimpleNamespace(SCHEMA='robotron-ce-batch2048-horizon-job-v1', POLICY={'fixed': True},
            validate_job=lambda value: seen.append(copy.deepcopy(value)))
        base = SimpleNamespace(read_json=lambda value: {'start': start, 'before': before}[value])
        job = controller.observer_job(None, horizon, base, activation, {'sha256': 'a'}, profile)
        self.assertEqual(job['batch_size'], 2048)
        self.assertEqual(job['profile_binding'], profile)
        self.assertEqual(job['start_request']['monotonic_s'], 100)
        self.assertEqual(job['healthy192_monotonic_s'], 110)
        self.assertEqual(job['before_resume_api'], before)
        self.assertEqual(seen, [job])

    def test_actual_live_plan_is2048_while_preserving_before_csv_and_epochs(self):
        metrics = SimpleNamespace(exposure_key=lambda value: tuple(value[k]
            for k in ('process_id', 'instance_monotonic_ns', 'epoch')))
        runtime = SimpleNamespace(metrics=metrics)
        exposure = {kind: dict(process_id=9, instance_monotonic_ns=10, epoch=0)
            for kind in ('optimizer', 'replay')}
        observer = dict(batch_size=2048, before_resume_api=dict(host_pipeline=dict(learning_exposure=exposure)))
        csv = {'batch_size': 4096, 'replay_dropped': 0}
        plan = controller.live_api_plan(runtime, observer, csv)
        self.assertEqual(plan['batch_size'], 2048)
        self.assertEqual(plan['initial_snapshot']['csv'], csv)
        self.assertEqual(plan['exposure_identity']['optimizer'], (9, 10, 0))
        observer['batch_size'] = 4096
        with self.assertRaises(RuntimeError):
            controller.live_api_plan(runtime, observer, csv)

    def test_actual_candidate_uses_typed_phase_floor_and_original_one_snapshot(self):
        calls = []
        clocks = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')
        early_floor = {key: 20 for key in clocks}
        event_floor = {key: 30 for key in clocks}
        owner = {'synthetic_owner': 9}
        phase = {'record': {'synthetic_phase': True}}
        class Snapshot:
            def __init__(self, *args): calls.append(('snapshot', args[3]))
            def start(self, raw, floor): calls.append(('start', floor))
            def tick(self): return {'status': 'COMPLETE'}
            def freeze(self, **kwargs): calls.append(('freeze', kwargs)); return {'one_candidate': True}
        def typed(base, result_pin, actual_owner, record, profile):
            calls.append(('typed', result_pin, actual_owner, record, profile))
            return dict(clock_floor=early_floor)
        helper = SimpleNamespace(Snapshot=Snapshot, phase_insurance_floor=typed)
        adapter = SimpleNamespace(four=lambda value: value,
            clock_max=lambda a, b: {k: max(a[k], b[k]) for k in clocks})
        runtime = SimpleNamespace(trainer_id=lambda: owner, job={'before': 'held'},
            raw_api=lambda: {'synthetic_API': True}, host=SimpleNamespace(pause=lambda value: calls.append(('pause', value))))
        clock = iter([100, 101, 102])
        deadline_mock = SimpleNamespace(clock=lambda: {'monotonic_s': next(clock)})
        result = controller.ending_candidate(adapter, None, deadline_mock, helper, runtime,
            dict(tag='synthetic_candidate', phase=phase, profile=profile_pin()), Path('/synthetic/new'),
            dict(state='LATCH', first_eligible_observation=event_floor),
            dict(status='PASS', result_pin={'synthetic_result': True}),
            dict(start_request={'monotonic_s': 1}))
        self.assertEqual(result, {'one_candidate': True})
        self.assertEqual([x for x in calls if x[0] == 'start'], [('start', event_floor)])
        self.assertEqual(len([x for x in calls if x[0] == 'snapshot']), 1)
        self.assertEqual(calls[0][0], 'typed')
        self.assertEqual(calls[0][-1], profile_pin())

    def test_actual_return_builder_uses_phase_result_and_no_legacy_alias(self):
        calls = []
        class JobBuilt(Exception):
            def __init__(self,value): self.value=value
        def publish(path,value):
            calls.append(('publish',path.name))
            if path.name=='return-job.json': raise JobBuilt(value)
            return dict(path=str(path),sha256='r'*64)
        record={'synthetic_record':True}
        phase=dict(record=record,expected={'metric':'ce'})
        runtime=SimpleNamespace(absence=lambda:calls.append('absence'),
            job=dict(schema='synthetic_reviewed3',verifier=dict(python='/synthetic/python',context={'held':'original'}),
                batch_boundary={'profile_binding':{'synthetic_binding':True}},settings_lifecycle={},original_dropin={},helper_pins={}),
            batch_boundary=SimpleNamespace(direction=lambda mode,binding:dict(mode=mode,profile_binding=binding)),
            current_completed={'synthetic_completed':True},settings=SimpleNamespace(current={'synthetic_settings':True}),
            host=SimpleNamespace(dropin_expected=b'[Service]\nRestart=no\n'))
        helper=SimpleNamespace(phase_insurance_floor=lambda *args:calls.append('typed') or dict(
            role='early_insurance',legacy_7d_insurance=False,eligible_quality_candidate=False))
        activation=dict(owner={'synthetic_owner':True},startup_phase_proof={'phase':phase},
            trial_core={'synthetic_core':True},start_request={'synthetic_start':True})
        trial=dict(profile=profile_pin(),return_intent=dict(phase_id='synthetic_return',request_id='synthetic_request',
            startup_tag='synthetic_startup',output_directory='/synthetic/return'),
            early_insurance=dict(collector={'synthetic_collector':True},python_identity={'synthetic_python':True}),
            pre_ending_csv={'batch_size':2048},activation_receipt={'synthetic_activation':True},sources={'adapter':{'synthetic_adapter':True}})
        early=dict(result_pin={'synthetic_result':True},producer_capture={'synthetic_capture':True})
        with self.assertRaises(JobBuilt) as built:
            controller.make_return_job(SimpleNamespace(SCHEMA='synthetic_reviewed3'),SimpleNamespace(publish=publish),
                runtime,trial,activation,None,None,None,early,{'synthetic_before':True},Path('/synthetic/new'),helper=helper)
        result=built.exception.value
        self.assertEqual(calls[:2],['absence','typed'])
        self.assertEqual(result['mode'],'return_batch4096')
        self.assertEqual(result['phase_early_insurance_result'],early['result_pin'])
        self.assertEqual(result['producer_capture'],early['producer_capture'])
        self.assertIsNone(result['insurance_verification'])
        self.assertIsNone(result['insurance_receipt'])
        self.assertNotIn('python_binding',result['verifier'])
        self.assertNotIn('script',result['verifier'])
        self.assertEqual(result['verifier']['python_identity'],trial['early_insurance']['python_identity'])
        self.assertEqual(result['running_phase'],phase)

    def test_exact_stop_deadline_latch_and_registered_cpu_primitives_preserved(self):
        def functions(path):
            source = path.read_text()
            return {n.name: ast.get_source_segment(source, n) for n in ast.parse(source).body
                if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        for file, names in [
            ('deadline_guard.py', ('identity', 'pin', 'read_pin', 'publish', 'clock', 'process_start',
                'show', 'classify', 'ActionLock', 'request_stop', 'read_adoption', 'supervise')),
            ('run_one_trial.py', ('durable_event', 'ReceiptJournal', 'registered_terminal', 'owned_cpu',
                'physical_retirement', 'require_deadline_retirement', 'inherit_retirement')),
        ]:
            before, after = functions(OLD / file), functions(HERE / file)
            for name in names:
                with self.subTest(file=file, name=name):
                    self.assertEqual(before[name], after[name])
        source = (HERE / 'run_one_trial.py').read_text()
        self.assertIn("'verify_phase_snapshot_2048.py'", source)
        self.assertIn('require(owned_cpu(registration, entry, argv, runtime,', source)


if __name__ == '__main__':
    unittest.main()
