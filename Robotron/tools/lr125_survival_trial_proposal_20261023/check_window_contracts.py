"""CPU contracts for one prospective LR125 window. Does not activate it."""
import ast
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

G = Path(__file__).resolve().parents[2]
P = Path(__file__).resolve().parent
PREP = G / 'logs/managed-learning-20261015/run-26/LR125-survival32M-original01-preparation-20261023'


def load(name, path, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class WindowContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window = load('_lr125_window', P / 'window_observer.py',
            'ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a')
        cls.controller = load('_lr125_controller', P / 'window_controller.py',
            'd6d02c7f9c8e17a925e5a1f766956b4e5ab0342d95c46f0b6bbd585f57cb5c55')
        cls.control = load('_lr125_actual_control', G / 'Scripts/dqn/learning_control.py',
            '29a74b25be391290b07373cdce4680ae7513db31596929f0bc9972aaf0ab220d')
        cls.counters = load('_lr125_actual_counters', G / 'tools/live_lr_recipe_continuation_proposal/observer.py',
            '11380275b544eb7196d33d92b1fbe28a1ae057404120419a2cfa447410c7e430')
        cls.api = json.loads((PREP / 'contract-fixture-current-API.json').read_text())
        cls.before = json.loads((PREP / 'control-before.raw.json').read_text())

    def test_exact_reversible_source_changes_only(self):
        manifest = json.loads((P / 'source-specializations.json').read_text())
        for row in manifest['entries']:
            original = Path(row['original_path']).read_bytes()
            effective = Path(row['effective_path']).read_bytes()
            self.assertEqual(hashlib.sha256(original).hexdigest(), row['original_sha256'])
            self.assertEqual(hashlib.sha256(effective).hexdigest(), row['effective_sha256'])
            reversed_bytes = effective
            for item in reversed(row['replacements']):
                old, new = item['old'].encode(), item['new'].encode()
                self.assertEqual(reversed_bytes.count(new), 1)
                reversed_bytes = reversed_bytes.replace(new, old)
            self.assertEqual(reversed_bytes, original)

    def test_real_control_accepts125_without_changing_epsilon(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'control.json'
            path.write_text(json.dumps(self.before))
            control = self.control.LearningControl(path)
            ramp = control.ramp
            after = dict(self.before, lr_scale=.125, experiment='LR125-contract-only')
            path.write_text(json.dumps(after))
            self.assertTrue(control.refresh())
            self.assertEqual(control.lr_scale, .125)
            self.assertEqual(control.ramp, ramp)
            self.assertEqual(control.epsilon(3_000_000_000, .7), .1)
            for bad in (True, 0, .001, 3, float('nan'), float('inf')):
                path.write_text(json.dumps(dict(after, lr_scale=bad)))
                self.assertFalse(control.refresh())
                self.assertEqual(control.lr_scale, .125)
                self.assertEqual(control.ramp, ramp)

    def test_actual_agent_schedule_at_floor(self):
        path = G / 'Scripts/dqn/agent.py'
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
            '865a0df717b39951b7f7c516e4a962e3d48cf4d3dc11295ff266e58653e6c74b')
        tree = ast.parse(raw)
        found = [node for cls in tree.body if isinstance(cls, ast.ClassDef)
                 for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'get_lr']
        self.assertEqual(len(found), 1)
        function = copy.deepcopy(found[0])
        function.decorator_list = []
        unit = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        cfg = SimpleNamespace(lr=1e-4, lr_min=5e-5, lr_cosine_period=1_000_000,
                              lr_warmup_steps=5000, lr_use_restarts=False)
        lc = SimpleNamespace(lr_scale=.25)
        namespace = dict(math=math, RL_CONFIG=cfg, learning_control=lc)
        exec(compile(unit, str(path) + '::actual-get_lr', 'exec'), namespace)
        actor = SimpleNamespace(lr_gear='climb', lr_anchor_step=0.,
                                lr_manual_scale=1., schedule_steps=70_000_000.)
        self.assertEqual(namespace['get_lr'](actor), 1.25e-5)
        lc.lr_scale = .125
        self.assertEqual(namespace['get_lr'](actor), 6.25e-6)

    def test_original_health_predicates_keep_rejecting_bad_runtime(self):
        api = copy.deepcopy(self.api)
        api.update(managed_experiment='LR125-contract-only', lr=6.25e-6)
        self.window.healthy(api, self.api, 'LR125-contract-only', api['ts'])
        for key, value in [('lr', 1.25e-5), ('client_count', 191),
                           ('measurement_active', True), ('training_enabled', False)]:
            bad = dict(api, **{key: value})
            with self.assertRaises(ValueError):
                self.window.healthy(bad, self.api, 'LR125-contract-only', api['ts'])

    def test_both_independent32M_horizons_required(self):
        baseline = self.counters.normalise(self.api)
        for frames, accepted, expected in [(31_999_999, 32_000_000, False),
                                           (32_000_000, 31_999_999, False),
                                           (32_000_000, 32_000_000, True)]:
            current = copy.deepcopy(baseline)
            current['clocks']['learner_frame_count'] += frames
            current['learner_accepted'] += accepted
            result = self.window.progress(current, baseline, baseline)
            self.assertIs(result['both_horizons'], expected)

    def test_original_epoch_regression_and_unavailable_rejections(self):
        baseline = self.counters.normalise(self.api)
        for mutation in ('epoch', 'counter', 'unavailable'):
            current = copy.deepcopy(baseline)
            if mutation == 'epoch':
                current['replay_identity']['epoch'] += 1
            elif mutation == 'counter':
                current['clocks']['training_steps'] -= 1
            else:
                current['optimizer']['unavailable'] += 1
            with self.assertRaises(ValueError):
                self.window.progress(current, baseline, baseline)

    def test_controller_exact_long_window_resource_limit(self):
        config = dict(unit='robotron-LR125-window-contract-only.service', output='/unselected',
            argv=['/usr/bin/python3.12', '-I', '-B', '/unselected.py'], pins=[], observation_s=14580,
            properties=['CPUQuota=200%', 'MemoryMax=4G', 'RuntimeMaxSec=14520',
                        'MemorySwapMax=0', 'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'
            path.write_text(json.dumps(config))
            self.assertEqual(self.controller.checked_config(path), config)
            config['properties'][2] = 'RuntimeMaxSec=180'
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                self.controller.checked_config(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
