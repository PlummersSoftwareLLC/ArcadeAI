"""Cold-only mode, actual native validator and cleanup attribution CPU guards."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
STOP = "ValueError('PRECOMMITTED_ALL64_COLD_STARTUP_PREFIX_ONLY_STOP_NOT_A_QUALITY_RESULT')"


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = load('_cold_native_test', 'run_cold_slot64_prefix_v1.py')
        cls.review = load('_cold_review_test', 'review_cold_slot64_prefix_v1.py')
        cls.guard = load('_cold_chain_test', 'startup_slot64_chain_v1.py')

    def fixture(self):
        policy = dict(measurement_generation=7, experiment='cold-fixed-original')
        admission = dict(generation=7, experiment=policy['experiment'])
        boundary = dict(ready=True, active=True, generation=7, requested_generation=7,
                        clients=64, expected=64, acknowledged=64, pending_client_ids=[],
                        replay_pending_client_ids=[], actor_slots=list(range(4096, 4160)))
        actors = {}
        for slot in range(4096, 4160):
            footer = dict(slot=slot, reason='prefix_complete', sequence=1200, frame_limit=1200,
                          failed=False, machine_exit_requested=False, gate_sequence=100,
                          setup_sequence=101, initialized_sequence=102, latched_sequence=102,
                          first_play_sequence=180)
            summary = dict(dense_prefix_frames=1200, continues_after_prefix=True, footer=footer)
            actors[slot] = dict(proxy=SimpleNamespace(prefix_verified=SimpleNamespace(is_set=lambda: True),
                error=None, handoff=dict(certificate_identifier=f'{slot:064x}'),
                prefix_summary=summary, issuer=SimpleNamespace(nonce=f'{slot:064x}'), sequence=1210),
                child=SimpleNamespace(pid=100000+slot, poll=lambda: None), birth=200000+slot)
        return actors, dict(policy=policy, boundary=boundary, admission=admission,
                            started_monotonic_s=100.0, observed_monotonic_s=150.0, observed_unix_s=200.0)

    def closed_fixture(self):
        actors, kwargs = self.fixture()
        marker = self.native.prefix_only_marker(actors, **kwargs)
        marker.update(runtime_errors_before_intentional_stop=[], server_inference_error_before_intentional_stop=None)
        result = dict(schema='robotron-cold-all64-startup-prefix-result-v1', errors=[STOP],
            active_start=None, active_end=None, active_frame_rate=None,
            policy_before=kwargs['policy'], policy_after=copy.deepcopy(kwargs['policy']),
            controller_exit=dict(generation=7), cold_prefix_marker={'fixture': 'immutable marker pin'},
            private_failure_events=[], original_slots={str(s):dict(pid=r['child'].pid, birth=r['birth'],
                handoff=r['proxy'].handoff, frames=1300, prefix_summary=r['proxy'].prefix_summary) for s,r in actors.items()})
        job = dict(label=kwargs['policy']['experiment'], diagnostic_role='cold_all64_startup_prefix_only', wall_limit_s=360)
        cutoff = dict(schema='robotron-cold-prefix-intentional-cleanup-boundary-v1', original_prefix_marker=result['cold_prefix_marker'],
            begin_monotonic_ns=151000000000, declaration_complete_monotonic_ns=151000000001,
            after_flags_monotonic_ns=151000000002, errors_before_intentional_cleanup=[STOP],
            inference_error_before_intentional_cleanup=None, shutdown_already_set=False,
            shutdown_set_before_owned_signals=True, intentional_cleanup_flag_set=True, before_first_owned_actor_signal=True)
        return job, result, marker, cutoff

    def test_actual_native_cold_scope_and_source_pin(self):
        source = HERE / 'cold-prefix-original01/job.json'
        self.assertTrue(source.is_file(), 'Prepared actual cold job prerequisite')
        with tempfile.TemporaryDirectory() as root:
            job = json.loads(source.read_bytes())
            job['output'] = str(Path(root) / 'future-cold-output')
            job['runtime'] = self.guard.pin(HERE / 'run_cold_slot64_prefix_v1.py')
            self.assertEqual(self.native.validate_job(job), Path(job['output']))
            for field, bad in [('diagnostic_role','timing_load_only'), ('schema','robotron-evaluator-count-active600-engineering-v1'), ('wall_limit_s',960)]:
                wrong = copy.deepcopy(job); wrong[field] = bad
                with self.subTest(field=field), self.assertRaises(ValueError): self.native.validate_job(wrong)
            wrong = copy.deepcopy(job); wrong['runtime']['sha256'] = '0'*64
            with self.assertRaises(ValueError): self.native.validate_job(wrong)
            self.assertFalse(Path(job['output']).exists())

    def test_all64_marker_and_closed_review_positive(self):
        job, result, marker, cutoff = self.closed_fixture()
        self.review.validate_cold_marker(job, result, marker)
        self.review.validate_cleanup_events(result, marker, cutoff)

    def test_missing_highslot_cannot_certify(self):
        actors, kw = self.fixture(); actors.pop(4159)
        with self.assertRaises(ValueError): self.native.prefix_only_marker(actors, **kw)

    def test_native_armed_generation_ACK_and_no_pending_required(self):
        for key, value in [('active',False), ('ready',False), ('clients',32), ('expected',32), ('acknowledged',63), ('requested_generation',8), ('pending_client_ids',[1]), ('replay_pending_client_ids',[1])]:
            actors, kw = self.fixture(); kw['boundary'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.native.prefix_only_marker(actors, **kw)

    def test_native_uncertified_firstplay_nonce_and_gone_actor_rejected(self):
        actors, kw = self.fixture(); actors[4159]['proxy'].prefix_summary['footer']['initialized_sequence'] = 0
        with self.assertRaises(ValueError): self.native.prefix_only_marker(actors, **kw)
        actors, kw = self.fixture(); actors[4159]['proxy'].issuer.nonce = '0'*64
        with self.assertRaises(ValueError): self.native.prefix_only_marker(actors, **kw)
        actors, kw = self.fixture(); actors[4159]['child'].poll = lambda: 0
        with self.assertRaises(ValueError): self.native.prefix_only_marker(actors, **kw)
        actors, kw = self.fixture(); kw['observed_monotonic_s'] = 400.0
        with self.assertRaises(ValueError): self.native.prefix_only_marker(actors, **kw)

    def test_server_shutdown_flag_precedes_owned_terminate(self):
        server = SimpleNamespace(shutdown_event=threading.Event(), inference_only_error=None)
        event = threading.Event()
        cutoff = self.native.begin_intentional_prefix_cleanup(server, {'actual':'marker'}, [STOP], event)
        def terminate():
            self.assertTrue(server.shutdown_event.is_set()); self.assertTrue(event.is_set())
        terminate()
        self.assertLessEqual(cutoff['begin_monotonic_ns'], cutoff['declaration_complete_monotonic_ns'])
        self.assertLessEqual(cutoff['declaration_complete_monotonic_ns'], cutoff['after_flags_monotonic_ns'])

    def test_review_rejects_unarmed_boundary_policy_change_and_600_window(self):
        for variant in ('unarmed','policy','window'):
            job, result, marker, cutoff = self.closed_fixture()
            if variant=='unarmed': marker['boundary']['active'] = False
            if variant=='policy': result['policy_after']['measurement_generation'] = 8
            if variant=='window': result['active_start'] = {'not':'cold'}
            with self.subTest(variant=variant), self.assertRaises(AssertionError): self.review.validate_cold_marker(job,result,marker)

    def test_exact_late_private_error_event_is_retained_and_joined(self):
        job, result, marker, cutoff = self.closed_fixture()
        error = "ValueError('Original full-tail exchange interrupted')"
        message = 'Original slot4159: ' + error
        result['errors'].append(message)
        result['private_failure_events'] = [dict(slot=4159,error=error,message=message,observed_monotonic_ns=151000000003,intentional_cleanup_observed=True)]
        self.review.validate_cold_marker(job,result,marker)
        self.review.validate_cleanup_events(result,marker,cutoff)
        for field, value in [('observed_monotonic_ns',150999999999),('intentional_cleanup_observed',False)]:
            wrong = copy.deepcopy(result); wrong['private_failure_events'][0][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError): self.review.validate_cleanup_events(wrong,marker,cutoff)

    def test_precleanup_or_unknown_fault_is_never_normalized(self):
        job, result, marker, cutoff = self.closed_fixture()
        for key,value in [('inference_error_before_intentional_cleanup','EOF'),('errors_before_intentional_cleanup',[STOP,'fault']),('shutdown_already_set',True)]:
            wrong=copy.deepcopy(cutoff);wrong[key]=value
            with self.subTest(key=key), self.assertRaises(AssertionError): self.review.validate_cleanup_events(result,marker,wrong)
        result['errors'].append('unknown runtime fault')
        with self.assertRaises(AssertionError): self.review.validate_cold_marker(job,result,marker)
        with self.assertRaises(AssertionError): self.review.validate_cleanup_events(result,marker,cutoff)


if __name__ == '__main__':
    unittest.main()
