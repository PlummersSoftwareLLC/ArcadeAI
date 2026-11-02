"""Finite metadata regressions; no live learner, GPU, process or network work."""
import copy
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_joint_metadata_deferred import selected


def fixture():
    exposure = {
        kind: dict(enabled=True, process_id=123, instance_monotonic_ns=456,
                   epoch=1, epoch_reason='startup', available=True)
        for kind in ('optimizer', 'replay')
    }
    pipe = dict(schema='robotron-host-pipeline-v1', available=True, generation=0,
                learning_exposure=exposure)
    pipe.update({kind: dict(errors=0) for kind in
                 ('inference', 'actor_refresh', 'target_refresh', 'learner_priority')})
    return dict(ts=999.0, pipeline_snapshot_age_s=0.5, pipeline_read_error='',
                bank_persistence_read_error='', client_count=192, training_enabled=True,
                measurement_active=False, managed_experiment='synthetic-continuation',
                lr=1.25e-5, host_pipeline=pipe, training_steps=10,
                optimized_samples=40960, learner_frame_count=500, frame_count=1000)


class MainHealth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P = selected('joint_parent.py')

    def check(self, value, baseline=None):
        return self.P.main_health_contract(value, fixture() if baseline is None else baseline, 123, 1000.0)

    def test_fresh_progress_and_normal_inflight_optimizer_are_admitted(self):
        api = fixture()
        api['learner_frame_count'] += 1
        api['host_pipeline']['learning_exposure']['optimizer']['available'] = False
        self.assertTrue(self.check(api))

    def test_stale_future_nonfinite_and_boolean_timestamps_are_rejected(self):
        for key, value in [('ts', 994.9), ('ts', 1000.1), ('ts', float('nan')),
                           ('ts', float('inf')), ('ts', True),
                           ('pipeline_snapshot_age_s', 5.1),
                           ('pipeline_snapshot_age_s', -0.1),
                           ('pipeline_snapshot_age_s', float('nan')),
                           ('pipeline_snapshot_age_s', True)]:
            with self.subTest(key=key, value=value):
                api = fixture(); api[key] = value
                with self.assertRaises(ValueError): self.check(api)

    def test_each_error_counter_and_read_error_are_rejected(self):
        for kind in ('inference', 'actor_refresh', 'target_refresh', 'learner_priority'):
            for value in (1, -1, False, '0', None):
                with self.subTest(kind=kind, value=value):
                    api = fixture(); api['host_pipeline'][kind]['errors'] = value
                    with self.assertRaises(ValueError): self.check(api)
        for key in ('pipeline_read_error', 'bank_persistence_read_error'):
            api = fixture(); api[key] = 'synthetic read failure'
            with self.assertRaises(ValueError): self.check(api)

    def test_partial_unavailable_reset_and_wrong_pipeline_are_rejected(self):
        for key in fixture():
            api = fixture(); del api[key]
            with self.subTest(missing=key), self.assertRaises(ValueError): self.check(api)
        for key, value in [('schema', 'foreign'), ('available', False),
                           ('generation', 1), ('generation', False)]:
            api = fixture(); api['host_pipeline'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(api)
        api = fixture(); del api['host_pipeline']['learner_priority']['errors']
        with self.assertRaises(ValueError): self.check(api)

    def test_clocks_recipe_and_exposure_identity_cannot_drift(self):
        for key in ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count'):
            for value in (fixture()[key]-1, True):
                api = fixture(); api[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.check(api)
        for key, value in [('managed_experiment', 'foreign'), ('lr', 5e-5),
                           ('client_count', 191), ('training_enabled', False),
                           ('measurement_active', True)]:
            api = fixture(); api[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(api)
        for kind in ('optimizer', 'replay'):
            for key, value in [('process_id', 124), ('instance_monotonic_ns', 457),
                               ('epoch', 2), ('epoch_reason', 'foreign'), ('enabled', False)]:
                api = fixture(); api['host_pipeline']['learning_exposure'][kind][key] = value
                with self.subTest(kind=kind, key=key), self.assertRaises(ValueError): self.check(api)

    def runtime(self, api):
        """Exercise the real runtime_guard with finite fake host adapters."""
        P = self.P
        main = dict(pid=123, unit='synthetic-main', invocation_id='main')
        fleet = dict(pid=124, unit='synthetic-fleet', invocation_id='fleet')
        baseline = dict(main_owner=main, fleet_owner=fleet, actors=[], actual_API='synthetic-baseline',
                        inference_worker=dict(tid=125, starttime_ticks=22, mask=[0]))
        class StatPath:
            def __init__(self, *parts):
                if parts != ('/proc', '123', 'task', '125', 'stat'):
                    raise AssertionError('Unplanned path')
            def read_text(self): return '125 (synthetic) ' + ' '.join(['0']*19+['22'])
        def show(unit):
            row = main if unit == main['unit'] else fleet
            if unit not in (main['unit'], fleet['unit']): raise AssertionError('Unplanned unit')
            return dict(MainPID=str(row['pid']), InvocationID=row['invocation_id'],
                        NRestarts='0', SubState='running')
        def gpu(argv, **kwargs):
            if argv != ['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader,nounits']:
                raise AssertionError('Unplanned subprocess')
            return SimpleNamespace(returncode=0, stdout='123, '+P.GPU1+'\n200, '+P.GPU0+'\n')
        def network(url, **kwargs):
            if url != 'http://127.0.0.1:8771/api/now': raise AssertionError('Unplanned network')
            return io.BytesIO(json.dumps(api).encode())
        with patch.object(P, 'alive', return_value=True), patch.object(P, 'show', side_effect=show), \
                patch.object(P, 'Path', StatPath), patch.object(P.os, 'sched_getaffinity', side_effect=lambda pid: {1} if pid == 0 else {0}), \
                patch.object(P.subprocess, 'run', side_effect=gpu), patch.object(P.urllib.request, 'urlopen', side_effect=network), \
                patch.object(P, 'pinned', return_value=json.dumps(fixture()).encode()), patch.object(P.time, 'time', return_value=1000.0), \
                patch.object(P, 'main_health_contract', wraps=P.main_health_contract) as checked:
            result = P.runtime_guard(dict(cpu_mask=[1]), baseline, {}, {200})
            checked.assert_called_once_with(api, fixture(), 123, 1000.0)
            return result

    def test_actual_runtime_guard_calls_health_contract(self):
        self.assertEqual(self.runtime(fixture())['client_count'], 192)

    def test_actual_runtime_guard_rejects_stale_and_erroring_snapshots(self):
        for error in ('stale', 'pipeline'):
            api = fixture()
            if error == 'stale': api['ts'] = 900.0
            else: api['host_pipeline']['inference']['errors'] = 1
            with self.subTest(error=error), self.assertRaises(ValueError): self.runtime(api)


if __name__ == '__main__':
    unittest.main()
