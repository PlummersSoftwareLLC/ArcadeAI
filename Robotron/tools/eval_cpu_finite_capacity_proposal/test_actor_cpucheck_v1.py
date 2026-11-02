"""CPU fixtures for the isolated actor copy; never initialize CUDA or MAME."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ['CUDA_VISIBLE_DEVICES'] = ''
for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[name] = '2'
private = tempfile.TemporaryDirectory(prefix='robotron-cpucheck-contract-')
for name, leaf in dict(ROBOTRON_DQN_MODEL_DIR='models', ROBOTRON_DQN_CONTROL_PATH='control.json',
                       ROBOTRON_RUN_DIR='reports').items():
    os.environ[name] = str(Path(private.name)/leaf)

HERE = Path(__file__).resolve().parent
PROFILE = HERE.parent/'quality_capacity_proposal/profile03/Robotron'
sys.path.insert(0, str(PROFILE/'Scripts'))
import numpy as np
import torch
torch.set_num_threads(2)
torch.set_num_interop_threads(1)
from dqn import test_inference_actor as existing

source = HERE/'inference_actor_cpucheck_v1.py'
spec = importlib.util.spec_from_file_location('dqn.inference_actor_cpucheck_candidate', source)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
existing.module = candidate


class AdditionalFailures(unittest.TestCase):
    def setUp(self):
        self.fixture = existing.InferenceActorTests('test_runtime_model_failure_and_nonfinite_q_latch_fatal')
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()

    def test_nonfinite_q_latches_for_both_return_paths(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            for return_cpu in (False, True):
                actor = self.fixture.actor()
                with patch.object(actor.infer_net, 'q_values_joint', return_value=torch.full((1, 81), value)):
                    with self.assertRaisesRegex(ValueError, 'invalid shape or non-finite'):
                        actor._infer_q_joint(torch.zeros(1, 4), return_cpu=return_cpu)
                self.assertIsNotNone(actor.inference_error)
                with self.assertRaisesRegex(RuntimeError, 'latched fatal'):
                    actor.act(np.zeros(4), 0)

    def test_invalid_q_shape_latches_before_cpu_copy(self):
        actor = self.fixture.actor()

        class WrongShape:
            shape = (1, 80)
            def detach(self):
                raise AssertionError('Shape rejection must precede a copy')

        with patch.object(actor.infer_net, 'q_values_joint', return_value=WrongShape()):
            with self.assertRaisesRegex(ValueError, 'invalid shape or non-finite'):
                actor._infer_q_joint(torch.zeros(1, 4), return_cpu=True)
        self.assertIsNotNone(actor.inference_error)

    def test_cpu_copy_precedes_output_finite_check_and_preserves_exact_values(self):
        actor = self.fixture.actor()
        copied = torch.arange(81, dtype=torch.float32).reshape(1, 81)
        events = []

        class DeviceOutput:
            shape = (1, 81)
            def detach(self):
                return self
            def cpu(self):
                events.append('copy')
                return copied

        real_isfinite = torch.isfinite
        def finite(tensor):
            if tensor is copied:
                self.assertEqual(events, ['copy'])
                events.append('output_finite')
            return real_isfinite(tensor)

        with patch.object(actor.infer_net, 'q_values_joint', return_value=DeviceOutput()), \
             patch.object(torch, 'isfinite', side_effect=finite):
            result = actor._infer_q_joint(torch.zeros(1, 4), return_cpu=True)
        self.assertIs(result, copied)
        self.assertEqual(events, ['copy', 'output_finite'])
        self.assertIsNone(actor.inference_error)

    def test_copy_failure_latches_without_returning_actions(self):
        actor = self.fixture.actor()

        class FailedCopy:
            shape = (1, 81)
            def detach(self):
                return self
            def cpu(self):
                raise RuntimeError('injected copy failure')

        with patch.object(actor.infer_net, 'q_values_joint', return_value=FailedCopy()):
            with self.assertRaisesRegex(RuntimeError, 'injected copy failure'):
                actor.act(np.zeros(4), 0)
        self.assertIsNotNone(actor.inference_error)


class SourceScope(unittest.TestCase):
    def test_all_other_class_methods_and_module_definitions_are_unchanged(self):
        original = PROFILE/'Scripts/dqn/inference_actor.py'
        package = json.loads((PROFILE.parent/'runtime-source-package.json').read_bytes())
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),
                         package['files']['Scripts/dqn/inference_actor.py'])
        before, after = ast.parse(original.read_text()), ast.parse(source.read_text())
        for tree in (before, after):
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == '_infer_q_joint':
                    node.body = [ast.Pass()]
        self.assertEqual(ast.dump(before), ast.dump(after))


if __name__ == '__main__':
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(existing.InferenceActorTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(AdditionalFailures),
        unittest.defaultTestLoader.loadTestsFromTestCase(SourceScope),
    ])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if torch.cuda.is_initialized():
        raise RuntimeError('CPU fixture initialized CUDA')
    private.cleanup()
    raise SystemExit(0 if result.wasSuccessful() else 1)
