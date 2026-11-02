"""Unexecuted stdlib guards: actual typed consumer/static/CPU publication seams."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


adapter = module('_CE2048_typed_transition_guards', HERE / 'run_CE_batch_transition.py')
profile_boundary = module('_CE2048_pure_boundary_guards', adapter.BOUNDARY)


def pin(path, sha='1' * 64, size=10):
    return dict(path=str(path), sha256=sha, bytes=size, identity=dict(device=1, inode=2,
        bytes=size, mtime_ns=1, ctime_ns=1, mode='0o444', uid=1, nlink=1))


OWNER = dict(pid=9, starttime_ticks=100, unit='synthetic.service', invocation_id='a' * 32,
    cgroup='/synthetic.service')
CLOCKS = {key: 20 for key in adapter.CLOCKS}
PROFILE = pin(profile_boundary.PROFILE_BINDING['pin']['path'],
    profile_boundary.PROFILE_BINDING['pin']['sha256'], profile_boundary.PROFILE_BINDING['pin']['bytes'])


def before():
    # Genuine LiveHost shape deliberately has no trainer.InvocationID.
    return dict(trainer=dict(MainPID='9', ControlGroup=OWNER['cgroup']),
        bindings=dict(worker=dict(trainer=dict(pid=9, starttime_ticks=100))))


def return_job():
    return dict(mode='return_batch4096', before=before(), trainer_unit=OWNER['unit'], experiment='synthetic',
        model_dir='/synthetic/models_dqn', verifier=dict(python='/synthetic/venv/bin/python',
            python_identity={'synthetic_identity': True}, context={}),
        insurance_verification=None, insurance_receipt=None,
        phase_early_insurance_result=pin('/synthetic/phase-early.json'),
        running_phase={'record': pin('/synthetic/phase-record.json')}, batch_profile=PROFILE,
        producer_capture=pin('/synthetic/capture.json'))


class BuiltCPUJob(Exception):
    def __init__(self, value): self.value = value


class PhaseInsuranceTransportContracts(unittest.TestCase):
    def test_default_and_launch_refusal_precede_any_base_or_job_reads(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('input read')):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(adapter.main([]), 0)
            with self.assertRaisesRegex(RuntimeError, 'UNCONSUMED DRAFT'):
                adapter.main(['--launch'])

    def test_4096_preactivation_retains_actual_legacy_proof_and_owner_shape(self):
        calls = []
        job = return_job()
        job.update(mode='activate_batch2048', phase_early_insurance_result=None, producer_capture=None,
            insurance_verification='legacy_report', insurance_receipt='legacy_saved')
        proof = dict(status='PASS', mode='insurance', clocks=CLOCKS,
            root_job=dict(experiment='synthetic', source_control_context={'model_dir': job['model_dir']},
                insurance=dict(trainer=OWNER, tag='synthetic_legacy'), source={'sha256': 's'}))
        saved = dict(tag='synthetic_legacy', source={'sha256': 's'})
        base = SimpleNamespace(validate_python_binding=lambda *a, **k: calls.append(k),
            read_json=lambda p: {'legacy_report': proof, 'legacy_saved': saved}[p])
        result = adapter.insurance_context(job, base, hash_executable=True)
        self.assertEqual(result['owner'], OWNER)
        self.assertEqual(result['clock_floor'], CLOCKS)
        self.assertTrue(result['legacy_7d_insurance'])
        self.assertEqual(calls, [{'hash_executable': True}])

    def test_return_consumes_phase_kind_and_separate_python_without_legacy_alias(self):
        calls = []
        job = return_job()
        result = dict(owner=OWNER, producer_capture=job['producer_capture'], python=job['verifier']['python'])
        typed = dict(owner=OWNER, clock_floor=CLOCKS, report=pin('/synthetic/report.json'),
            tag='synthetic_early', legacy_7d_insurance=False)
        report = dict(root_job=dict(experiment='synthetic', source_control_context={'model_dir': job['model_dir']}))
        helper = SimpleNamespace(readonly_json=lambda base, p: report if p == typed['report'] else result,
            phase_insurance_floor=lambda *args: calls.append(('typed', args[2:])) or typed,
            check_python_identity=lambda *a, **k: calls.append(('python', k)))
        base = SimpleNamespace(validate_python_binding=lambda *a, **k: self.fail('legacy7d provenance used'))
        with patch.object(adapter, 'phase_early_module', return_value=helper):
            observed = adapter.insurance_context(job, base, hash_executable=False)
        self.assertEqual(observed, typed)
        self.assertEqual(calls[0][1], (OWNER, job['running_phase']['record'], PROFILE))
        self.assertEqual(calls[1], ('python', {'hash_executable': False}))
        for changed in ('insurance_verification', 'insurance_receipt'):
            wrong = copy.deepcopy(job); wrong[changed] = pin('/synthetic/forged.json')
            with self.assertRaisesRegex(RuntimeError, 'must not relabel'):
                adapter.insurance_context(wrong, base, hash_executable=False)

    def test_actual_static_does_not_reenter_inherited_7d_script_or_proof(self):
        calls = []
        base = SimpleNamespace(Runtime=object, fingerprint=lambda *a: None,
            read_json=lambda *a: None, publish=lambda *a: None, MAX_SOURCE=1 << 20,
            pin=lambda value, maximum: calls.append(('pin', value)))
        helper = SimpleNamespace(ReadonlyMetadataBase=lambda value: value)
        with patch.object(adapter, 'phase_early_module', return_value=helper):
            cls = adapter.runtime_class(base)
        runtime = cls.__new__(cls)
        runtime.job = return_job(); runtime.job.update(helper_pins={'only': 'source'}, static_pins=['static'])
        runtime.exclusive = lambda: calls.append('exclusive')
        runtime.settings = SimpleNamespace(check=lambda: calls.append('settings'))
        with patch.object(adapter, 'insurance_context', side_effect=lambda *a, **k: calls.append(('typed_context', k))):
            runtime.static()
        self.assertEqual(calls, ['exclusive', ('pin', 'source'), 'settings', ('pin', 'static'),
            ('typed_context', {'hash_executable': False})])

    def test_actual_retired_candidate_cpu_publishes_final_acquisition_before_bind(self):
        calls = []
        phase = dict(record=pin('/synthetic/phase.json'), boot_checkpoint={'path': '/synthetic/latest.pt'},
            boot_verification=pin('/synthetic/boot.json'), expected={'metric': 'ce'})
        pairs = {name: {'current': pin('/synthetic/' + name)} for name in adapter.SOURCE_NAMES}
        capture = dict(spec=dict(owner=OWNER, phase_record=phase['record'],
            source_pins={name: value['current'] for name, value in pairs.items()}))
        def publish(path, value):
            calls.append(('publish', path.name))
            if path.name == 'cpu-job.json': raise BuiltCPUJob(value)
            return pin(path)
        collector = SimpleNamespace(capture_live=lambda *a: self.fail('retired owner reobserved'),
            bind_capture=lambda capture_pin, source, final_pin, output:
                calls.append(('bind', final_pin['path'])) or pin(output / 'producer-observation.json'))
        base = SimpleNamespace(Runtime=object, fingerprint=lambda *a: None, read_json=lambda *a: None,
            publish=publish, MAX_SOURCE=1 << 20, pin=lambda *a: None)
        helper = SimpleNamespace(ReadonlyMetadataBase=lambda value: value,
            load_collector=lambda *a: collector, readonly_json=lambda *a: capture)
        with patch.object(adapter, 'phase_early_module', return_value=helper):
            cls = adapter.runtime_class(base)
        runtime = cls.__new__(cls); runtime.cpu_attempts = {}
        runtime.batch_boundary = profile_boundary
        runtime.job = return_job()
        runtime.job.update(batch_boundary=profile_boundary.direction('return_batch4096',
            profile_boundary.PROFILE_BINDING), producer_collector={'synthetic': True},
            phase_verifier2048=copy.deepcopy(adapter.CPU2048_BINDING))
        runtime.phase_sources = lambda label: (pairs, {'provenance': []})
        runtime.capture_startup_producer = lambda *a: self.fail('candidate is not startup')
        acquisition = dict(client_count=0, clock_floor=CLOCKS)
        with tempfile.TemporaryDirectory() as temporary:
            runtime.output = Path(temporary)
            with patch.object(adapter, 'phase_metadata', side_effect=lambda b, p, c, d: (p, c, {})):
                with self.assertRaises(BuiltCPUJob) as built:
                    runtime.cpu_phase('candidate', 'candidate', OWNER, pin('/synthetic/model.pt'),
                        pin('/synthetic/copy.pt'), phase, acquisition, 'one_candidate')
        names = [v[1] for v in calls if v[0] == 'publish']
        self.assertIn('acquisition.json', names)
        self.assertLess(next(i for i, v in enumerate(calls) if v == ('publish', 'acquisition.json')),
            next(i for i, v in enumerate(calls) if v[0] == 'bind'))
        job = built.exception.value
        self.assertEqual(job['schema'], 'robotron-batch2048-phase-snapshot-checkpoint-CPU-job-reviewed2-v1')
        self.assertEqual(job['source_control_context']['held_recipe_context']['batch_size'], 2048)
        self.assertEqual(job['phase_snapshot']['purpose'], 'candidate')
        self.assertEqual(job['batch2048_context']['role'], 'candidate')
        self.assertEqual(runtime.cpu_attempts, {})

    def test_before_owner_rejects_foreign_identity_without_phantom_invocation_field(self):
        job = return_job()
        self.assertEqual(adapter.before_owner(job, OWNER), OWNER)
        self.assertNotIn('InvocationID', job['before']['trainer'])
        for key, value in [('pid', 10), ('starttime_ticks', 101), ('unit', 'foreign.service'),
                           ('cgroup', '/foreign'), ('invocation_id', 'invalid')]:
            wrong = dict(OWNER, **{key: value})
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                adapter.before_owner(job, wrong)

    def test_raw_api_whitelist_is_two_owned_names_not_global_nan_permission(self):
        base = SimpleNamespace(Runtime=object, fingerprint=lambda *a: None, read_json=lambda *a: None,
            publish=lambda *a: None)
        helper = SimpleNamespace(ReadonlyMetadataBase=lambda value: value,
            publish_text=lambda *a: self.fail('foreign raw path must refuse before writer'))
        with patch.object(adapter, 'phase_early_module', return_value=helper):
            cls = adapter.runtime_class(base)
        runtime = cls.__new__(cls); runtime.output = Path('/synthetic/new')
        for name in ('metadata.json', '../API-before-resume.json', 'trigger-API.json'):
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                runtime.publish_raw_API(name, {'loss': float('nan')})


if __name__ == '__main__':
    unittest.main()
