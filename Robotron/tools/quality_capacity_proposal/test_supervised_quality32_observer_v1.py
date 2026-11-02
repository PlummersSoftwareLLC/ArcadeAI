"""Real new observer samples and original raw/rejected wires; OS census mocked."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import quality32_runtime_guard_v4 as observer
import supervised_main_fleet_v1 as fleet
import supervised_main_observations_v1 as joins
import test_supervised_main_fleet_v1 as census_fixtures
import test_supervised_main_observations_v1 as fixtures


class ObserverSamples(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.JoinTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        spec = importlib.util.spec_from_file_location('base_for_supervised_observer', observer.BASE)
        self.base = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.base)
        self.model = self.f.root/'models'
        self.model.mkdir()
        (self.model/'robotron_dqn_latest.pt').write_bytes(b'synthetic size/mtime fixture, never a loaded model')
        self.index = 0
        self.failed_client_count = None
        self.config = dict(unit='robotron-supervised-observer-synthetic.service', output=str(self.f.root/'execution'))
        self.inputs = dict(main=copy.deepcopy(self.f.main), reader=fixtures.reader,
            baseline=self.f.baseline, baseline_wire=json.dumps(self.f.baseline, allow_nan=True).encode(),
            window=SimpleNamespace(MODEL=self.model, owner_and_files=Mock(), healthy=fixtures.window.healthy),
            job=dict(main_supervision_policy=self.f.main['supervision_policy']),
            review_job=dict(closed_context_path=str(self.f.root/'bindings/closed-context.json'),
                runtime_paths=dict(main_observations=str(self.f.root/'bindings/main-observations.json'))),
            supervision=fleet, observations=joins, supervision_policy=self.f.policy)
        self.guard = observer.guard_class(self.base)(self.config, self.inputs)
        self.guard.main.pop('baseline_API_value')
        self.guard.clock = lambda: 1000000 + 100 + self.index * 10 + .02
        self.guard.monotonic = lambda: 100 + self.index * 10 + .02

    def census(self, policy, state):
        replacements = {'168': census_fixtures.replacement(policy, '168')} if self.index == 2 else {}
        return census_fixtures.snapshot(policy, state, 100 + self.index*10,
            missing=['168'] if self.index == 1 else [], replacements=replacements)

    def raw(self):
        count = 191 if self.index in (1, 2) else 192
        if self.failed_client_count is not None and self.index == 1:
            count = self.failed_client_count
        value = fixtures.api(self.f.main, 1000000 + 100 + self.index*10, self.index, count)
        return json.dumps(value, allow_nan=True).encode()

    def next(self, initial=False):
        mtime = int((self.guard.clock()-5)*1e9)
        os.utime(self.model/'robotron_dqn_latest.pt', ns=(mtime, mtime))
        with patch.object(fleet, 'collect', side_effect=self.census), patch.object(self.base, 'read_API_bytes', side_effect=self.raw):
            if initial:
                self.guard.prepare_bindings()
            else:
                self.guard.sample()

    def test_actual_observer_preserves191_raw_wires_and_independently_replays(self):
        self.next(initial=True)
        for index in range(1, 4):
            self.index = index
            self.next()
        joins.finish(self.guard)
        self.assertTrue(self.guard.finished)
        manifest = self.f.read(self.guard.main_manifest)
        self.assertEqual(manifest['status'], 'PASS')
        samples = [self.f.read(pin) for pin in manifest['samples']]
        self.assertEqual([row['API']['client_count'] for row in samples], [192, 191, 191, 192])
        rejoined = fixtures.runtime.validate_raw_API_samples(manifest, samples, self.f.read)
        state, summary = joins.review(self.f.main, self.f.policy, manifest, rejoined, 100.03, 130,
            self.f.read, fixtures.runtime, fixtures.window, fleet)
        self.assertEqual(state, self.guard.fleet_state)
        self.assertEqual(summary['charged_recovery_s'], 30)
        self.assertEqual(self.guard.window.owner_and_files.call_count, 4)
        self.assertEqual(len(self.guard.window.owner_and_files.call_args_list[1].args[0]['actors']), 191)
        self.assertEqual(len(self.guard.main['actors']), 192)

    def test_actual_observer_retains_extra_client_raw_rejection(self):
        self.next(initial=True)
        self.index = 1
        self.failed_client_count = 193
        with self.assertRaises(ValueError):
            self.next()
        self.assertIsNotNone(self.guard.failed)
        self.assertEqual(len(self.guard.rejected_observations), 1)
        rejection = self.f.read(self.guard.rejected_observations[0])
        self.assertTrue(rejection['attempt']['API_received'])
        self.assertEqual(json.loads(self.f.read(rejection['attempt']['API_wire'], False))['client_count'], 193)
        self.assertIsNotNone(rejection['attempt']['main_fleet_snapshot'])
        joins.finish(self.guard)
        self.assertEqual(self.f.read(self.guard.main_manifest)['status'], 'FAILED')

    def test_inherited_exposure_progress_stop_and_private_actor_logic_unchanged(self):
        for method in ('validate_exposure', 'sample', 'before_scheduling', 'on_tick', 'interrupt_original',
                       'finish_main_observation', 'preserve_incomplete_observation'):
            self.assertIs(getattr(type(self.guard), method), getattr(self.base.MainGuard, method))
        def nodes(name):
            return {node.name: ast.dump(node, include_attributes=False) for node in
                    ast.walk(ast.parse((HERE/name).read_text())) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        old, new = nodes('quality32_runtime_guard_v3.py'), nodes('quality32_runtime_guard_v4.py')
        for method in ('live_process', 'validate_records', 'campaign_command', 'validate_config',
                       'record_birth', 'capture_plan', 'capture_actors', 'binding_entry_value', 'close_and_review'):
            self.assertEqual(new[method], old[method], method)
        old, new = nodes('review_closed_quality32_v4.py'), nodes('review_closed_quality32_v5.py')
        for method in ('validate_records', 'validate_births', 'validate_native_command', 'validate_leg_scope', 'decision'):
            self.assertEqual(new[method], old[method], method)


if __name__ == '__main__':
    unittest.main()
