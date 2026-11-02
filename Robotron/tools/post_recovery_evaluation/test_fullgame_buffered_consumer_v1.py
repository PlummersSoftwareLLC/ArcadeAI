"""Actual buffered full-game consumer, resource and private predicate checks."""
import ast
import copy
import os
from pathlib import Path
import secrets
import tempfile
import time
from types import SimpleNamespace
import unittest

from . import fullgame_round_observer_v3 as worker
from . import volatile_live_control_v1 as control
from .fullgame_round_observer_client_v5 import DedicatedMainHealth
from . import fullgame_round_contract_v4 as contract

HERE=Path(__file__).resolve().parent


class FullgameBufferedConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.guard=DedicatedMainHealth.__new__(DedicatedMainHealth)
        guard=self.guard;guard.common=worker;guard.control_module=control
        guard.jobpin=dict(path='/ENGINEERING-job',sha256='a'*64)
        guard.job=dict(nonce=secrets.token_hex(16));guard.worker_owner=dict(pid=os.getpid(),birth=worker.birth(os.getpid()))
        guard.last_live=guard.initial=None;guard.output=self.root
        self.live_control=control.VolatileLiveControl(guard.job['nonce'],dict(job=guard.jobpin,nonce=guard.job['nonce'],owner=guard.worker_owner))
        guard.control_path=self.live_control.path
        prefix=worker.write(self.root/'prefix.json',dict(schema='robotron-buffered-raw-readiness-v2',
            binding=dict(job=guard.jobpin,nonce=guard.job['nonce'],owner=guard.worker_owner),
            sample_count=100,committed_records=100,committed_monotonic_s=time.monotonic()))
        self.live=dict(schema='robotron-round-observer-live-v2',control=self.live_control.descriptor(),job=guard.jobpin,
            nonce=guard.job['nonce'],owner=guard.worker_owner,state='running',observed_samples=104,
            updated_monotonic_s=time.monotonic(),latest_sample=dict(schema='robotron-queued-raw-record-v2',
            path=str(self.root/'sample-000103.json'),sha256='c'*64,bytes=700000,sequence=104,kind='sample',index=103),
            initial=dict(index=99,unix_s=time.time(),unaccepted_samples=0,durable_prefix=prefix,
                         durable_ready_monotonic_s=time.monotonic()),phase=dict(overlap_pending=False))
        self.live['updated_monotonic_s']=time.monotonic()

    def tearDown(self):
        self.live_control.close();self.temp.cleanup()

    def test_actual_native_collect_main_accepts_queued_bytes_and_zero_based_index(self):
        path=HERE/'run_fullgame_rounds_v4.py'
        run=next(n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='run')
        collect=next(n for n in ast.walk(run)if isinstance(n,ast.FunctionDef)and n.name=='collect_main')
        tree=ast.fix_missing_locations(ast.Module(body=[collect],type_ignores=[]))
        namespace=dict(main_guard=SimpleNamespace(observe=lambda:self.guard._accept(self.live)),main_samples=[],require=worker.require)
        exec(compile(tree,str(path),'exec'),namespace)
        row=namespace['collect_main']()
        self.assertEqual(row['index'],103);self.assertEqual(row['initial']['index'],99)
        self.assertEqual(row['sample'],self.live['latest_sample'])
        self.assertEqual(namespace['main_samples'],[row])
        self.assertFalse(Path(row['sample']['path']).exists())

    def test_stale_or_changed_projection_pending_descriptor_and_readiness_rejected(self):
        faults=('stale','owner','control','pending_index','pending_path','pending_digest','pending_size','early_ready','regression','readiness_removed')
        for fault in faults:
            self.guard.last_live=self.guard.initial=None;self.guard._accept(self.live)
            value=copy.deepcopy(self.live)
            if fault=='stale':value['updated_monotonic_s']-=.6
            elif fault=='owner':value['owner']['birth']+=1
            elif fault=='control':value['control']['identity']['inode']+=1
            elif fault=='pending_index':value['latest_sample']['index']-=1
            elif fault=='pending_path':value['latest_sample']['path']='/ENGINEERING-wrong-sample'
            elif fault=='pending_digest':value['latest_sample']['sha256']='z'*64
            elif fault=='pending_size':value['latest_sample']['bytes']=9<<20
            elif fault=='early_ready':value['initial']['durable_ready_monotonic_s']-=1
            elif fault=='regression':value['observed_samples']-=1
            else:value['initial']=None
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.guard._accept(value)

    def test_uncommitted_initial_raw_prefix_cannot_enable_private_readiness(self):
        self.live['initial']['durable_prefix']['sha256']='f'*64
        with self.assertRaises(ValueError):self.guard._accept(self.live)

    def test_all_private_count_life_tail_score_cleanup_predicates_preserved(self):
        proof=contract.validate_derivation(HERE/'run_fullgame_rounds_v4.py',HERE/'review_fullgame_rounds_v4.py')
        self.assertTrue(proof['private_count_life_game_tail_score_cleanup_and_timeout_predicates_preserved'])
        self.assertFalse(proof['scientific_launch_qualified'])

    def test_worker_differs_only_in_schema_and_complete_game_time_bounds(self):
        expected=(HERE/'round_observer_v7.py').read_text()
        for old,new in [('robotron-round-observer-job-v7','robotron-fullgame-round-observer-job-v3'),
                        ("job['work_s'] == 4200 and job['runtime_s'] == 4260","job['work_s'] == 22200 and job['runtime_s'] == 22260"),
                        ('Exact deadline observer bounds required','Exact complete-game observer bounds required')]:expected=expected.replace(old,new)
        self.assertEqual(ast.dump(ast.parse(expected)),ast.dump(ast.parse(Path(worker.__file__).read_bytes())))

    def test_raw_reviewer_differs_only_in_schema_time_and_manifest_capacity(self):
        expected=(HERE/'review_round_observer_v8.py').read_text()
        for old,new in [('robotron-round-observer-job-v7','robotron-fullgame-round-observer-job-v3'),
                        ("job['work_s'] == 4200 and job['runtime_s'] == 4260","job['work_s'] == 22200 and job['runtime_s'] == 22260"),
                        ("lifecycle['native_started_monotonic_s'] + 4200","lifecycle['native_started_monotonic_s'] + 22200"),
                        ("RuntimeMaxUSec='1h 11min'","RuntimeMaxUSec='6h 11min'"),
                        ('ended-started <= 4260','ended-started <= 22260'),('<= 22000','<= 112000'),('64 << 20','128 << 20')]:expected=expected.replace(old,new)
        self.assertEqual(ast.dump(ast.parse(expected)),ast.dump(ast.parse((HERE/'review_fullgame_round_observer_v4.py').read_bytes())))


if __name__=='__main__':unittest.main()
