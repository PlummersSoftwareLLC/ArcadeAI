"""Actual full-game consumer ABI and duration-only observer adaptation checks."""
import ast
import copy
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

from . import fullgame_round_observer_v2 as worker
from .fullgame_round_observer_client_v4 import DedicatedMainHealth
from .fullgame_round_observer_client_v3 import DedicatedMainHealth as MissingIndexPredecessor

HERE = Path(__file__).resolve().parent


class FullgameAsyncConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, client=DedicatedMainHealth):
        guard = client.__new__(client)
        guard.common = worker
        guard.jobpin = dict(path='/ENGINEERING-job', sha256='a'*64)
        guard.job = dict(nonce='b'*32)
        guard.worker_owner = dict(pid=os.getpid(), birth=worker.birth(os.getpid()))
        guard.last_live = guard.initial = None
        prefix = worker.write(self.root/('prefix-'+client.__module__+'.json'), dict(
            schema='robotron-durable-raw-readiness-v1',
            binding=dict(job=guard.jobpin, nonce=guard.job['nonce'], owner=guard.worker_owner),
            sample_count=100, committed_records=100, committed_monotonic_s=time.monotonic()))
        live = dict(schema='robotron-round-observer-live-v1', job=guard.jobpin,
            nonce=guard.job['nonce'], owner=guard.worker_owner, state='running',
            observed_samples=104, updated_monotonic_s=time.monotonic(), latest_sample={},
            initial=dict(index=99, unix_s=time.time(), unaccepted_samples=0, durable_prefix=prefix,
                         durable_ready_monotonic_s=time.monotonic()), phase=dict(overlap_pending=False))
        live['updated_monotonic_s'] = time.monotonic()
        return guard, live

    def consumer(self, guard, live):
        path = HERE/'run_fullgame_rounds_v3.py'
        body = next(node for node in ast.parse(path.read_bytes()).body
                    if isinstance(node, ast.FunctionDef) and node.name == 'run')
        consumer = next(node for node in ast.walk(body)
                        if isinstance(node, ast.FunctionDef) and node.name == 'collect_main')
        module = ast.fix_missing_locations(ast.Module(body=[consumer], type_ignores=[]))
        def require(value, reason):
            if not value:
                raise ValueError(reason)
        namespace = dict(main_guard=SimpleNamespace(observe=lambda: guard._accept(live)),
                         main_samples=[], require=require)
        exec(compile(module, str(path), 'exec'), namespace)
        return namespace

    def test_actual_fullgame_collect_main_accepts_durable_record_with_latest_zero_based_index(self):
        guard, live = self.fixture()
        namespace = self.consumer(guard, live)
        row = namespace['collect_main']()
        self.assertEqual(row['index'], 103)
        self.assertEqual(row['initial']['index'], 99)
        self.assertEqual(namespace['main_samples'], [row])

    def test_missing_index_predecessor_reproduces_actual_fullgame_consumer_failure(self):
        guard, live = self.fixture(MissingIndexPredecessor)
        namespace = self.consumer(guard, live)
        with self.assertRaises(KeyError):
            namespace['collect_main']()
        self.assertEqual(namespace['main_samples'], [])

    def test_hot500ms_gap_and_durable_initial_prefix_cannot_be_relaxed(self):
        guard, live = self.fixture()
        guard._accept(live)
        for fault in ('stale', 'missing_prefix', 'wrong_prefix', 'early_ready', 'regression'):
            value = copy.deepcopy(live)
            if fault == 'stale':
                value['updated_monotonic_s'] -= .6
            elif fault == 'missing_prefix':
                value['initial'].pop('durable_prefix')
            elif fault == 'wrong_prefix':
                value['initial']['durable_prefix']['sha256'] = 'f'*64
            elif fault == 'early_ready':
                value['initial']['durable_ready_monotonic_s'] -= 1
            else:
                value['observed_samples'] -= 1
            with self.subTest(fault=fault), self.assertRaises((ValueError, KeyError)):
                guard._accept(value)

    def test_fullgame_worker_differs_only_in_schema_and_declared_time_bounds(self):
        expected = (HERE/'round_observer_v6.py').read_text()
        expected = expected.replace('robotron-round-observer-job-v6', 'robotron-fullgame-round-observer-job-v2')
        expected = expected.replace("job['work_s'] == 4200 and job['runtime_s'] == 4260",
                                    "job['work_s'] == 22200 and job['runtime_s'] == 22260")
        expected = expected.replace('Exact deadline observer bounds required', 'Exact complete-game observer bounds required')
        self.assertEqual(ast.dump(ast.parse(expected)), ast.dump(ast.parse(Path(worker.__file__).read_bytes())))

    def test_fullgame_reviewer_differs_only_in_schema_duration_and_manifest_capacity(self):
        expected = (HERE/'review_round_observer_v7.py').read_text()
        for old, new in [('robotron-round-observer-job-v6','robotron-fullgame-round-observer-job-v2'),
                         ("job['work_s'] == 4200 and job['runtime_s'] == 4260", "job['work_s'] == 22200 and job['runtime_s'] == 22260"),
                         ("lifecycle['native_started_monotonic_s'] + 4200", "lifecycle['native_started_monotonic_s'] + 22200"),
                         ("RuntimeMaxUSec='1h 11min'", "RuntimeMaxUSec='6h 11min'"),
                         ('ended-started <= 4260','ended-started <= 22260'), ('<= 22000','<= 112000'),
                         ('64 << 20','128 << 20')]:
            expected = expected.replace(old, new)
        self.assertEqual(ast.dump(ast.parse(expected)), ast.dump(ast.parse((HERE/'review_fullgame_round_observer_v3.py').read_bytes())))


if __name__ == '__main__':
    unittest.main()
