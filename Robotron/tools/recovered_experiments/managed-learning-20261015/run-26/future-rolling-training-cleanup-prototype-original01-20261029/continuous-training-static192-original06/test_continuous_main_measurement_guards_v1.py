"""Staged actual-source guard fixtures; Root alone may execute later.

Only SHA-bound AST definitions/preamble are compiled in the future CPU run.
No production main import, model, checkpoint, server, process or control call.
Collaborators intentionally stop at the first formerly reachable policy action.
"""
import ast
import hashlib
import math
import os
from pathlib import Path
import threading
import time
import types
import unittest

HERE = Path(__file__).resolve().parent
SOURCES = {
    'measurement': (HERE/'managed_measurement_continuous_guard_candidate_v1.py',
                    '39764cfa84572fe36c57e37a5c958d7caa001854c141ebcc161cc973f7b5f3c0'),
    'driver': (HERE/'managed_driver_continuous_guard_candidate_v1.py',
               'a7ec6dffba18e37b814842d498c8a34ba44f93dce4968ab769d480e329a643ec'),
    'main': (HERE/'main_continuous_training_guard_candidate_v1.py',
             '12b7b07077383ecf447b640f7bf20dd86e81a6223cd79083c12bcd448f33a1b4'),
}


class ReachedPolicy(Exception):
    pass


class Poison:
    def __getattr__(self, name):
        raise AssertionError('Guard reached forbidden collaborator: '+name)


def source_tree(role):
    path, digest = SOURCES[role]
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    return ast.parse(raw), str(path)


def namespace(role, mode='1', metrics=None):
    metrics = metrics or types.SimpleNamespace(continuous_training_mode=False,
        measurement_active=False, ratchet_frozen=False, training_enabled=True,
        lock=threading.Lock())
    tree, filename = source_tree(role)
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_continuous_training_mode_enabled')
    environment = {'ROBOTRON_CONTINUOUS_TRAINING_MODE': mode}
    ns = dict(math=math, time=time, Path=Path, MODEL_DIR='/synthetic/models',
        metrics=metrics, os=types.SimpleNamespace(path=os.path,
            getenv=lambda key, default=None: environment.get(key, default)),
        print=lambda *a, **k: None)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                 filename, 'exec'), ns)
    return tree, filename, ns, metrics, environment


def actual_class(role, name, mode='1', metrics=None):
    tree, filename, ns, metrics, environment = namespace(role, mode, metrics)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 filename, 'exec'), ns)
    return ns[name], ns, metrics, environment


class Tests(unittest.TestCase):
    def test_managed_enter_refuses_before_checkpoint_policy_or_flag_mutation(self):
        for mode, sticky in [('1', False), ('0', True)]:
            with self.subTest(mode=mode, sticky=sticky):
                cls, _, metrics, _ = actual_class('measurement', 'ManagedMeasurement', mode)
                metrics.continuous_training_mode = sticky
                obj = cls.__new__(cls)
                obj.metrics, obj.agent, obj._prior = metrics, Poison(), None
                before = vars(metrics).copy()
                with self.assertRaisesRegex(RuntimeError, 'disabled'):
                    obj.enter('request', checkpoint_path='/synthetic/policy.pt')
                self.assertEqual(vars(metrics), before)
                self.assertIsNone(obj._prior)
                self.assertFalse(hasattr(obj, 'label'))

    def test_mode0_managed_entry_reaches_original_checkpoint_preparation(self):
        cls, _, metrics, _ = actual_class('measurement', 'ManagedMeasurement', '0')
        calls = []
        def prepare(path):
            calls.append(path)
            raise ReachedPolicy('Stopped before any actual checkpoint access')
        obj = cls.__new__(cls)
        obj.metrics, obj._prior = metrics, None
        obj.agent = types.SimpleNamespace(prepare_inference_checkpoint=prepare)
        with self.assertRaises(ReachedPolicy):
            obj.enter('private-mode0', checkpoint_path='/synthetic/policy.pt')
        self.assertEqual(calls, ['/synthetic/policy.pt'])
        self.assertIsNone(obj._prior)

    def test_driver_reports_disabled_request_without_controller_save_or_fake_result(self):
        cls, _, metrics, _ = actual_class('driver', 'ManagedMeasurementDriver')
        obj = cls.__new__(cls)
        obj.metrics, obj.agent, obj.controller = metrics, Poison(), Poison()
        obj.request, obj.handled = None, set()
        obj.update(dict(label='request', checkpoint=None, cohort_s=3600, timeout_s=7200))
        status = metrics.managed_measurement_status
        self.assertFalse(status['active'])
        self.assertEqual(status['phase'], 'disabled_continuous_training')
        self.assertTrue(status['measurement_requests_disabled'])
        self.assertTrue(status['request_denied'])
        self.assertFalse(status['complete'])
        self.assertIsNone(status['valid'])
        self.assertIsNone(obj.request)
        self.assertEqual(obj.handled, set())
        metrics.measurement_active = True
        before = dict(status)
        with self.assertRaisesRegex(RuntimeError, 'before any active'):
            obj.update(dict(label='request'))
        self.assertEqual(metrics.managed_measurement_status, before)

    def test_mode0_driver_keeps_original_request_route(self):
        cls, _, metrics, _ = actual_class('driver', 'ManagedMeasurementDriver', '0')
        calls = []
        obj = cls.__new__(cls)
        obj.metrics, obj.agent = metrics, Poison()
        obj.request, obj.handled = None, set()
        obj.controller = types.SimpleNamespace(
            enter=lambda *a, **k: calls.append((a, k)),
            status=lambda: dict(active=True, phase='warming'))
        request = dict(label='private-mode0', checkpoint='/synthetic/policy.pt')
        obj.update(request)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], ('private-mode0',))
        self.assertEqual(calls[0][1]['checkpoint_path'], '/synthetic/policy.pt')
        self.assertEqual(obj.request, request)
        self.assertEqual(metrics.managed_measurement_status['phase'], 'warming')

    def test_direct_ratchet_constructor_and_entry_refuse_before_agent_mutation(self):
        for mode, sticky in [('1', False), ('0', True)]:
            cls, _, metrics, _ = actual_class('main', 'RatchetController', mode)
            metrics.continuous_training_mode = sticky
            with self.assertRaisesRegex(RuntimeError, 'disabled'):
                cls(Poison())
            obj = cls.__new__(cls)
            obj.agent = Poison()
            with self.assertRaisesRegex(RuntimeError, 'disabled'):
                obj._enter_eval()
        cls, _, _, _ = actual_class('main', 'RatchetController', '0')
        class Agent:
            @property
            def behavior_locked(self):
                raise AssertionError('Unexpected read')
            @behavior_locked.setter
            def behavior_locked(self, value):
                raise ReachedPolicy('Original mode0 constructor reached')
        with self.assertRaises(ReachedPolicy):
            cls(Agent())

    def test_actual_main_preamble_refuses_ratchet_and_sets_markers_before_agent(self):
        for mode, ratchet, active, expected_error in [
            ('1', True, False, RuntimeError),
            ('1', False, True, RuntimeError),
            ('yes', False, False, ValueError),
            ('1', False, False, ReachedPolicy),
            ('0', False, False, ReachedPolicy),
        ]:
            with self.subTest(mode=mode, ratchet=ratchet, active=active):
                tree, filename, ns, metrics, _ = namespace('main', mode)
                metrics.measurement_active = active
                events = []
                ns['os'].makedirs = lambda *a, **k: events.append('directory')
                ns['RL_CONFIG'] = types.SimpleNamespace(ratchet_enabled=ratchet, state_size=1)
                ns['_apply_inference_batch_wait_override'] = lambda cfg: events.append('config')
                def agent(**kwargs):
                    events.append('agent')
                    self.assertEqual(metrics.continuous_training_mode, mode == '1')
                    self.assertEqual(metrics.main_measurement_entry_disabled, mode == '1')
                    raise ReachedPolicy('Stop before real agent/checkpoint/server creation')
                ns['RainbowAgent'] = agent
                main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
                cutoff = next(i for i, n in enumerate(main.body)
                    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'agent' for t in n.targets))
                prefix = ast.FunctionDef(name='main_prefix', args=main.args,
                    body=main.body[:cutoff+1], decorator_list=[], returns=None,
                    type_comment=None, type_params=[])
                exec(compile(ast.fix_missing_locations(ast.Module(body=[prefix], type_ignores=[])),
                             filename, 'exec'), ns)
                with self.assertRaises(expected_error):
                    ns['main_prefix']()
                self.assertEqual('agent' in events, expected_error is ReachedPolicy)


if __name__ == '__main__':
    unittest.main()
