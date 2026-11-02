"""Unexecuted stdlib guards of real draft methods with synthetic metadata/IO.

No trainer, process, model, application or numerical module is loaded. Private
temporary files below are only small fake lease/metadata fixtures.
"""
import ast
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import run_CE_batch_transition as adapter
from . import owned_lifecycle as owned
from ..batch2048_phase_boundary_reviewed2_proposal import profile_boundary as boundary


class SeenPlan(Exception):
    pass


def spec(mode='activate_batch2048'):
    return boundary.direction(mode, copy.deepcopy(boundary.PROFILE_BINDING))


def environment(batch):
    return dict(DQN_BATCH_SIZE=str(batch), DQN_PER_PRIORITY_METRIC='ce',
        DQN_PRIORITY_PHASE_RECORD='/synthetic/old.json',
        DQN_PRIORITY_PHASE_RECORD_SHA256='a'*64, KEEP_RECIPE='same')


def csv(batch):
    return dict(batch_size=batch, replay_sample_cap=8, replay_dropped=0, utc='synthetic')


def exposure():
    return dict(optimizer=dict(process_id=123), replay=dict(process_id=123))


def fake_base():
    return SimpleNamespace(Runtime=object, fingerprint=lambda *args: None,
        read_json=lambda *args: None, publish=lambda *args: None)


class TransitionWiringContracts(unittest.TestCase):
    def test_default_and_unresolved_launch_never_read_or_import_helpers(self):
        with patch.object(adapter, 'load_v4', side_effect=AssertionError('no helper import')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('no job/source read')), \
                contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(adapter.main([]), 0)
            with self.assertRaises(RuntimeError):
                adapter.main(['--launch', '--job', '/synthetic/unbound.json'])
        self.assertIn('PLAN_ONLY_UNCONSUMED', stream.getvalue())
        self.assertTrue(adapter.DRAFT_BLOCKERS)
        self.assertEqual(adapter.CPU2048_BINDING['script']['sha256'],
            'a331b550191a48ab219cf92f2e1c42fc394e038c93609ecac4fb9a722b75e5cd')

    def test_real_adapter_environment_delegate_uses_direction_and_keeps_ce(self):
        pin = dict(path='/synthetic/new-record.json', sha256='b'*64, bytes=100,
            identity=dict(device=1, inode=2, bytes=100, mtime_ns=3, ctime_ns=4,
                mode='0o444', uid=1001, nlink=1))
        with patch.object(adapter, 'boundary', return_value=boundary):
            for mode in boundary.MODES:
                selected = spec(mode)
                result = adapter.selected_environment(environment(selected['before_batch_size']), selected, pin)
                self.assertEqual(result['DQN_BATCH_SIZE'], str(selected['after_batch_size']))
                self.assertEqual(result['DQN_PER_PRIORITY_METRIC'], 'ce')
                self.assertEqual(result['KEEP_RECIPE'], 'same')

    def test_real_adapter_new_record_delegate_requires_newest_forward_floor(self):
        source = dict(path='/synthetic/models_dqn/robotron_dqn_latest.pt', sha256='c'*64, bytes=275000000)
        clocks = dict.fromkeys(adapter.CLOCKS, 100)
        with patch.object(adapter, 'boundary', return_value=boundary):
            for mode in boundary.MODES:
                selected = spec(mode)
                proof = dict(status='PASS', sha256=source['sha256'], bytes=source['bytes'], clocks=clocks,
                    phase_metadata_verified=True, root_job=dict(phase_snapshot=dict(purpose='newest_stopped')),
                    held_recipe_context=dict(batch_size=selected['before_batch_size']),
                    saved_priority_metric_phase=dict(schema='robotron-priority-metric-phase-v1',
                        phase_id='synthetic_old_ce', metric='ce', valid=True))
                result = adapter.start_record(selected, 'synthetic_new_ce', 'd'*64,
                    '/synthetic/models_dqn', source, proof, clocks)
                self.assertEqual((result['metric'], result['previous_metric']), ('ce', 'ce'))
                stale_floor = dict(clocks, optimized_samples=101)
                with self.assertRaises(ValueError):
                    adapter.start_record(selected, 'synthetic_new_ce', 'd'*64,
                        '/synthetic/models_dqn', source, proof, stale_floor)

    def test_generic_before_founder_keeps_authentic_historical_kl_predecessor(self):
        record = dict(metric='ce', previous_metric='kl', phase_id='synthetic_existing_ce',
            root_precommit_sha256='c'*64, checkpoint=dict(path='/synthetic/latest.pt', sha256='a'*64, bytes=100))
        proof = dict(clocks=dict.fromkeys(adapter.CLOCKS, 100))
        expected = adapter.expected_start(record, dict(sha256='b'*64), proof)
        self.assertEqual(expected['metric'], 'ce')
        self.assertEqual(expected['phase_id'], 'synthetic_existing_ce')
        self.assertEqual(record['previous_metric'], 'kl')

    def test_real_owned_initial_uses_actual_before4096_or2048_csv_plan(self):
        for mode in boundary.MODES:
            selected = spec(mode); seen = []
            current = dict(environment=environment(selected['before_batch_size']),
                bindings=dict(logs=[]))
            snapshot = dict(exposure=exposure())
            def api_issues(row, plan):
                seen.append(copy.deepcopy(plan)); raise SeenPlan()
            host = SimpleNamespace(describe=lambda: current, adopt_initial=lambda value: None,
                metric_host=SimpleNamespace(configure_logs=lambda value: None), capture=lambda: snapshot)
            runtime = SimpleNamespace(output=Path('/synthetic/output'), host=host,
                job=dict(before=current, baseline_csv=csv(selected['before_batch_size']), batch_boundary=selected),
                insured=dict(pid=123), static=lambda: None, trainer_id=lambda: dict(pid=123),
                batch_boundary=boundary,
                metrics=SimpleNamespace(exposure_key=lambda value: dict(process_id=value['process_id']),
                    api_issues=api_issues))
            with tempfile.TemporaryDirectory() as temporary:
                lease = Path(temporary)/'owned-private-lease'; lease.touch()
                original_path = Path
                def scoped_path(value):
                    if str(value) == '/dev/shm/robotron-snapshot-smoke-gpu0.lock':
                        return lease
                    return original_path(value)
                try:
                    with patch.object(owned, 'Path', side_effect=scoped_path), \
                            patch.object(owned.shutil, 'disk_usage', return_value=SimpleNamespace(free=20<<30)):
                        with self.assertRaises(SeenPlan):
                            owned.Runtime.initial(runtime)
                finally:
                    if getattr(runtime, 'lease_fd', None) is not None:
                        os.close(runtime.lease_fd)
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0]['batch_size'], selected['before_batch_size'])
            self.assertEqual(seen[0]['csv_scope'], 'current_producer')

    def test_real_ready_transport_uses_truthful_actor0_and_after192_profiles(self):
        for mode in boundary.MODES:
            for actors in (False, True):
                selected = spec(mode); seen = []
                raw = dict.fromkeys(adapter.CLOCKS, 100)
                raw.update(client_count=192 if actors else 0, managed_experiment='synthetic_branch',
                    host_pipeline=dict(learning_exposure=dict(optimizer=dict(process_id=123,
                        total=dict(outcomes_recorded=1))), inference_graphs=dict(ready=True)))
                row = dict(exposure=exposure(), csv=csv(selected['after_batch_size']))
                current = dict(environment=environment(selected['after_batch_size']), bindings=dict(logs=[]))
                def api_issues(value, plan):
                    seen.append((copy.deepcopy(value), copy.deepcopy(plan))); raise SeenPlan()
                base = fake_base(); cls = adapter.runtime_class(base); runtime = cls.__new__(cls)
                runtime.batch_boundary = boundary
                runtime.job = dict(readiness_timeout_s=10, experiment='synthetic_branch',
                    baseline_csv=csv(selected['before_batch_size']), batch_boundary=selected)
                runtime.current_checkpoint = dict(clocks=dict.fromkeys(adapter.CLOCKS, 100))
                runtime.static=lambda: None; runtime.trainer_id=lambda: dict(pid=123)
                runtime.raw_api=lambda: raw; runtime.inspect=lambda phase: current
                runtime.fault_scan=lambda: []
                runtime.host=SimpleNamespace(metric_host=SimpleNamespace(configure_logs=lambda value: None),
                    capture=lambda: copy.deepcopy(row))
                runtime.metrics=SimpleNamespace(compact_api=lambda value: copy.deepcopy(row),
                    exposure_key=lambda value: dict(process_id=value['process_id']), api_issues=api_issues)
                with self.assertRaises(SeenPlan):
                    runtime.ready_transport('after', {}, actors=actors)
                actual, plan = seen[0]
                self.assertEqual(plan['configured_batch_size'], selected['after_batch_size'])
                self.assertEqual(plan['batch_size'], selected['after_batch_size'] if actors else selected['before_batch_size'])
                self.assertEqual(actual['csv']['batch_size'], plan['batch_size'])
                self.assertEqual(plan['csv_scope'], 'current_producer' if actors else 'pretransition_baseline')

    def test_real2048_producer_collection_fails_closed_without_fabrication(self):
        cls = adapter.runtime_class(fake_base()); runtime = cls.__new__(cls)
        with self.assertRaisesRegex(RuntimeError, 'collector is not implemented'):
            runtime.collect_producer_observation('synthetic', 'startup', {}, {}, {})

    def test_actual_wiring_source_has_no_legacy_mode_or_wrong_env_signature(self):
        text = Path(adapter.__file__).read_text(); tree = ast.parse(text)
        self.assertNotIn("'activate_kl'", text)
        self.assertNotIn("'return_ce'", text)
        self.assertNotIn('local = dict(batch_size=4096', text)
        self.assertIn('self.batch_boundary.override_environment(', text)
        self.assertIn('expected=self.batch_boundary.expected_start(', text)
        self.assertIn('original_strict_base_sha256=ORIGINAL_STRICT_SHA', text)
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        calls = [node for node in main.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)]
        self.assertTrue(any(isinstance(node.value.func, ast.Name) and node.value.func.id == 'require_execution_ready'
            for node in calls))


class CandidateJobBuilt(Exception):
    def __init__(self, job):
        super().__init__('Captured real candidate CPU job before any numerical command')
        self.job = copy.deepcopy(job)


class RealCandidateRouteContracts(unittest.TestCase):
    """Call actual post_stop_ending/cpu_phase, stubbing only evidence/IO edges."""
    def runtime_fixture(self, directory, mode):
        selected = spec(mode); calls = []
        clock_values = dict.fromkeys(adapter.CLOCKS, 100)
        owner = dict(pid=123, starttime_ticks=456,
            unit='robotron-managed-synthetic-trainer.service', invocation_id='a'*32,
            cgroup='/user.slice/synthetic.service')
        def full_pin(path, sha='b'*64, size=100):
            return dict(path=str(path), sha256=sha, bytes=size,
                identity=dict(device=1, inode=2, bytes=size, mtime_ns=3, ctime_ns=4,
                    mode='0o444', uid=1001, nlink=1))
        def publish(path, value):
            calls.append(('publish', Path(path).name))
            if Path(path).name == 'cpu-job.json':
                raise CandidateJobBuilt(value)
            return full_pin(path)
        acquisition = dict(client_count=0, tag='synthetic_first_candidate', clock_floor=clock_values)
        base = fake_base(); base.MAX_SOURCE=4<<20; base.publish=publish
        base.pin=lambda *args: calls.append(('source-pin', args[0]['sha256']))
        base.read_json=lambda pin: copy.deepcopy(acquisition)
        cls=adapter.runtime_class(base); runtime=cls.__new__(cls)
        profile = boundary.PROFILE_BINDING['pin']
        phase = dict(record=full_pin('/synthetic/phase.json'),
            boot_checkpoint=dict(path='/synthetic/latest.pt', sha256='d'*64, bytes=275000000),
            boot_verification=full_pin('/synthetic/boot-CPU.json'), expected=dict(metric='ce'))
        runtime.job=dict(mode=mode, batch_boundary=selected, batch_profile=full_pin(**{
            'path':profile['path'], 'sha':profile['sha256'], 'size':profile['bytes']}),
            running_phase=phase, experiment='synthetic_branch', phase_verifier2048=copy.deepcopy(adapter.CPU2048_BINDING),
            phase_verifier=dict(script=dict(path=str(adapter.PHASE), sha256=adapter.PHASE_SHA, bytes=1),
                strict_base=dict(path=str(adapter.PHASE.parent/'strict_phase_base.py'), sha256=adapter.STRICT_SHA, bytes=1)))
        runtime.batch_boundary=boundary; runtime.output=Path(directory);runtime.cpu_attempts={}
        runtime.floor=copy.deepcopy(clock_values);runtime.retired_owner=runtime.insured=owner
        runtime.static=lambda: calls.append(('static', None))
        runtime.absence=lambda: calls.append(('exact-owned-absence', owner))
        runtime.phase_sources=lambda label: ({}, {})
        runtime.collect_producer_observation=lambda *args: (
            calls.append(('producer', args[1])) or full_pin('/synthetic/producer.json'))
        source=full_pin('/synthetic/managed-checkpoints/synthetic_first_candidate.pt', 'e'*64, 275000000)
        runtime.ending=dict(state='LATCH', owner=owner, decision=full_pin('/synthetic/first-LATCH.json'),
            floor=copy.deepcopy(clock_values), candidate=dict(source=source,
                verification_copy=full_pin('/synthetic/candidate-copy.pt','e'*64,275000000),
                acquisition=full_pin('/synthetic/acquisition.json')))
        return runtime, owner, phase, source, acquisition, calls

    def test_actual_post_stop_ending_builds_before2048_candidate_job(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime, owner, _, source, _, calls = self.runtime_fixture(directory, 'return_batch4096')
            with patch.object(adapter, 'phase_metadata', side_effect=lambda base, phase, context, root: (phase, context, {})):
                with self.assertRaises(CandidateJobBuilt) as caught:
                    runtime.post_stop_ending(owner)
            job=caught.exception.job
            self.assertEqual(job['schema'], 'robotron-batch2048-phase-snapshot-checkpoint-CPU-job-reviewed2-v1')
            self.assertEqual(job['verifier_sha256'], 'a331b550191a48ab219cf92f2e1c42fc394e038c93609ecac4fb9a722b75e5cd')
            self.assertEqual(job['source'], source)
            self.assertEqual(job['phase_snapshot']['purpose'], 'candidate')
            self.assertEqual(job['source_control_context']['held_recipe_context']['batch_size'], 2048)
            self.assertEqual(job['batch2048_context']['role'], 'candidate')
            self.assertEqual(calls[0][0], 'static')
            self.assertEqual(calls[1][0], 'exact-owned-absence')
            self.assertIn(('producer', 'candidate'), calls)
            self.assertFalse(runtime.cpu_attempts)  # trapped before original numerical command

    def test_actual_return_startup_uses4096_and_activation_candidate_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime, owner, phase, source, acquisition, calls = self.runtime_fixture(directory, 'return_batch4096')
            runtime.collect_producer_observation=lambda *args: self.fail('4096 startup cannot claim2048 producer')
            with patch.object(adapter, 'phase_metadata', side_effect=lambda base, phase, context, root: (phase, context, {})):
                with self.assertRaises(CandidateJobBuilt) as caught:
                    runtime.cpu_phase('startup-fixture','startup',owner,source,source,phase,acquisition,'startup-key')
            job=caught.exception.job
            self.assertEqual(job['schema'], 'robotron-phase-snapshot-checkpoint-CPU-job-v1')
            self.assertEqual(job['verifier_sha256'], adapter.PHASE_SHA)
            self.assertEqual(job['source_control_context']['held_recipe_context']['batch_size'], 4096)
            self.assertNotIn('batch2048_context', job)
        with tempfile.TemporaryDirectory() as directory:
            runtime, owner, phase, source, acquisition, calls = self.runtime_fixture(directory, 'activate_batch2048')
            with self.assertRaisesRegex(ValueError, 'Endingcandidate'):
                runtime.cpu_phase('invalid-candidate','candidate',owner,source,source,phase,acquisition,'invalid-key')
            self.assertFalse(any(name == 'publish' for name, value in calls))


if __name__ == '__main__':
    unittest.main()
