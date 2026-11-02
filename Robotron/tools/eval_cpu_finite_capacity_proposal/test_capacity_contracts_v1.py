"""Standard-library contracts; no numerical runtime, model, GPU or MAME."""
import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


b = module('_capacity_worker_contract', HERE/'benchmark_cpucheck_capacity_v1.py')
c = module('_capacity_controller_contract', HERE/'control_cpucheck_capacity_v1.py')


class Contracts(unittest.TestCase):
    def job(self):
        return dict(schema='robotron-isolated-cpucheck-capacity-job-v1', gpu_uuid=b.GPU0,
                    candidate_source=dict(path=str(HERE/'inference_actor_cpucheck_v1.py')),
                    numerical_source=dict(path=str(HERE/'numerical_cpucheck_capacity_v1.py')),
                    checkpoint=dict(sha256=b.POLICY_SHA), profile_package=dict(sha256=b.PACKAGE_SHA),
                    output=str(b.ROOT/'logs/managed-learning-20261015/run-26/eval-cpucheck-capacity-original01-preparation-20261019/work'),
                    rounds=12, sample_rows=256, seed=20261020, schedule=['gpu_check', 'cpu_check', 'cpu_check', 'gpu_check'],
                    rows_per_workload=32, cpu_threads=2, compile_options={'triton.cudagraphs': False},
                    quality_qualification=False, mame=False, training=False)

    def test_worker_default_is_plan_only_without_numerical_imports(self):
        text = subprocess.check_output([sys.executable, '-I', '-B', str(HERE/'benchmark_cpucheck_capacity_v1.py')], text=True)
        self.assertIn('PLAN_ONLY', text)
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('numpy', sys.modules)

    def test_fixed_job_scope_and_rejection_of_unselected_parameters(self):
        with patch.object(Path, 'exists', return_value=False):
            b.validate_job(self.job())
        for key, value in [('gpu_uuid', 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'),
                           ('rounds', 13), ('sample_rows', 512), ('rows_per_workload', 16),
                           ('schedule', ['16', '32']), ('cpu_threads', 4), ('seed', 1),
                           ('mame', True), ('training', True), ('quality_qualification', True),
                           ('compile_options', {'triton.cudagraphs': True}), ('output', '/tmp/work')]:
            with self.subTest(key=key), patch.object(Path, 'exists', return_value=False), self.assertRaises(ValueError):
                changed = self.job(); changed[key] = value; b.validate_job(changed)
        with patch.object(Path, 'exists', return_value=True), self.assertRaises(ValueError):
            b.validate_job(self.job())

    def test_conditions_serve_identical32_requests_without_overlap_or_omission(self):
        for condition in ('gpu_check', 'cpu_check'):
            seen = [v for a, z in b.slices_for(condition) for v in range(a, z)]
            self.assertEqual(seen, list(range(32)))
        self.assertEqual(len(b.slices_for('gpu_check')), 2)
        self.assertEqual(len(b.slices_for('cpu_check')), 2)
        with self.assertRaises(ValueError): b.slices_for('64')

    def test_parity_rejects_nonfinite_and_distinguishes_joint_and_locked_actions(self):
        row = list(map(float, range(81)))
        good = b.q_parity([row], [row])
        self.assertTrue(good['q_allclose'] and good['joint_actions_equal'] and good['all_locked_fire_actions_equal'])
        changed = row.copy(); changed[0] = 100
        bad = b.q_parity([row], [changed])
        self.assertFalse(bad['joint_actions_equal']); self.assertFalse(bad['all_locked_fire_actions_equal'])
        near = [v+.00001 for v in row]
        self.assertTrue(b.q_parity([row], [near])['q_allclose'])
        for other in ([], [[1]], [[float('nan')]*81]):
            with self.assertRaises(ValueError): b.q_parity([row], other)

    def test_timing_summary_keeps_wall_units_and_valid_counts(self):
        self.assertEqual(b.summary_ms([9, 1, 2, 3]), dict(calls=4, median_ms=2.5, p95_ms=9, minimum_ms=1, maximum_ms=9))
        for values in ([], [0], [-1], [float('inf')]):
            with self.assertRaises(ValueError): b.summary_ms(values)

    def config(self):
        return dict(unit='robotron-private-inference-cpucheck-benchmark-original01-20261019.service',
                    output='/tmp/new-private-execution', observation_s=660, pins=[],
                    properties=['CPUQuota=200%', 'MemoryMax=12G', 'MemorySwapMax=0', 'RuntimeMaxSec=600',
                                'TasksMax=256', 'TimeoutStopSec=30', 'KillMode=mixed', 'SendSIGKILL=no'],
                    argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-B', '-u',
                          str(HERE/'benchmark_cpucheck_capacity_v1.py'), '--execute', '--job', '/tmp/job.json',
                          '--job-sha256', 'a'*64])

    def check_config(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'config.json'; path.write_text(json.dumps(value))
            return c.checked_config(path)

    def test_controller_rejects_foreign_namespace_runtime_and_worker(self):
        self.assertEqual(self.check_config(self.config()), self.config())
        bad = []
        for key, value in [('unit', 'robotron-main.service'), ('observation_s', 1200), ('argv', ['python', '/tmp/foreign.py'])]:
            item = self.config(); item[key] = value; bad.append(item)
        item = self.config(); item['properties'][0] = 'CPUQuota=1200%'; bad.append(item)
        item = self.config(); item['properties'].append('CPUQuota=200%'); bad.append(item)
        for item in bad:
            with self.assertRaises(ValueError): self.check_config(item)

    def test_original_lifecycle_is_unchanged_from_existing_tested_controller(self):
        parent = ast.parse((HERE.parent/'quality_capacity_proposal/control_quality32_review_v1.py').read_text())
        child = ast.parse((HERE/'control_cpucheck_capacity_v1.py').read_text())
        parent_functions = {v.name: v for v in parent.body if isinstance(v, ast.FunctionDef)}
        child_functions = {v.name: v for v in child.body if isinstance(v, ast.FunctionDef)}
        self.assertEqual(set(parent_functions), set(child_functions))
        for name, original in parent_functions.items():
            if name == 'checked_config': continue
            current = copy.deepcopy(child_functions[name])
            if name == 'launch':
                for node in ast.walk(current):
                    if isinstance(node, ast.Constant) and node.value == 'CUDA_VISIBLE_DEVICES='+b.GPU0:
                        node.value = 'CUDA_VISIBLE_DEVICES='
            self.assertEqual(ast.dump(original), ast.dump(current), name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
