"""CPU source proof for a future handoff component; no live pause or deployment."""
import argparse
import ast
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
TRAINING_SHA = '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4'


class NumericalRegionReached(Exception):
    pass


class Config:
    batch_size = 4096
    baseline_batch_size = 512
    min_replay_to_train = 4096
    max_samples_per_frame = 8

    @property
    def per_priority_metric(self):
        raise NumericalRegionReached('Actual learner passed its final sample-cap guard')


class Memory:
    def __len__(self):
        return 6_000_000


class PendingBatch:
    def __init__(self):
        self.releases = 0

    def release(self):
        self.releases += 1


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return
    source = GAME / 'Scripts/dqn/training.py'
    assert digest(source) == TRAINING_SHA
    tree = ast.parse(source.read_bytes())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ('replay_pressure_reached', 'train_step', '_train_step_impl')]
    assert len(selected) == 3
    namespace = dict(nullcontext=nullcontext)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), namespace)

    class DrainGateTests(unittest.TestCase):
        def setUp(self):
            namespace['RL_CONFIG'] = Config()
            namespace['metrics'] = SimpleNamespace(lock=threading.RLock(), frame_count=1100,
                loaded_frame_count=1000, measurement_frame_count=0,
                loaded_measurement_frame_count=0, loaded_optimized_samples=10_000,
                training_enabled=True)
            self.agent = SimpleNamespace(memory=Memory(), optimized_samples=10_800,
                training_steps=100, loaded_training_steps=90, training_enabled=True,
                _training_lock=threading.RLock(), _recomputed_ce_capture=None)

        def blocked(self):
            batch = PendingBatch()
            before = (self.agent.optimized_samples, self.agent.training_steps,
                      dict(vars(namespace['metrics'])))
            self.assertTrue(namespace['replay_pressure_reached'](self.agent))
            self.assertIsNone(namespace['train_step'](self.agent, prefetched_batch=batch))
            self.assertEqual(batch.releases, 1)
            self.assertEqual(before, (self.agent.optimized_samples, self.agent.training_steps,
                                     dict(vars(namespace['metrics']))))

        def test_exactly_exhausted_budget_blocks_existing_pending_batch(self):
            self.blocked()

        def test_batch_overshoot_blocks_without_another_update(self):
            self.agent.optimized_samples += 4095
            self.blocked()

        def test_one_sample_of_credit_reaches_the_numerical_region(self):
            self.agent.optimized_samples -= 1
            self.assertFalse(namespace['replay_pressure_reached'](self.agent))
            batch = PendingBatch()
            with self.assertRaises(NumericalRegionReached):
                namespace['train_step'](self.agent, prefetched_batch=batch)
            self.assertEqual(batch.releases, 1)

        def test_frozen_frames_do_not_earn_credit(self):
            namespace['metrics'].frame_count += 100
            namespace['metrics'].measurement_frame_count += 100
            self.blocked()

        def test_private_warmup_anchor_changes_the_required_budget(self):
            self.agent._replay_pressure_anchor = (1090, 0, 10_720)
            self.blocked()

        def test_same_API_clocks_cannot_ignore_a_private_anchor(self):
            self.agent._replay_pressure_anchor = (1000, 0, 10_001)
            self.assertFalse(namespace['replay_pressure_reached'](self.agent))

        def test_resume_can_admit_one_batch_at_zero_new_frames(self):
            namespace['metrics'].frame_count = 1000
            self.agent.optimized_samples = 10_000
            self.assertFalse(namespace['replay_pressure_reached'](self.agent))
            self.agent.optimized_samples += 4096
            self.blocked()

        def test_training_pause_also_blocks_without_touching_a_pending_batch(self):
            self.agent.optimized_samples = 10_000
            self.agent.training_enabled = False
            batch = PendingBatch()
            self.assertIsNone(namespace['train_step'](self.agent, prefetched_batch=batch))
            self.assertEqual(batch.releases, 1)

    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DrainGateTests))
    assert digest(source) == TRAINING_SHA
    report = dict(schema='robotron-future-handoff-final-learner-gate-CPU-v1',
        status='PASS' if result.wasSuccessful() else 'FAIL', tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), training_source_sha256=TRAINING_SHA,
        exact_original_functions=[node.name for node in selected],
        numerical_region_is_a_sentinel=True, actual_optimizer_or_replay_executed=False,
        live_trainer_paused_or_changed=False, production_deployment_ready=False,
        findings=[
            'A genuinely exhausted sample budget prevents the actual final learner gate from entering numerical work, even with a pending prefetched batch.',
            'The loaded checkpoint clocks are insufficient if a private warmup anchor exists; future handoff must establish the real anchor provenance.',
            'At zero new frames a newly resumed learner can admit one4096-sample batch before this guard blocks; exact pre-learning resume verification needs an explicit startup hold or must account for that update.',
            'This CPU gate proof does not establish actor shutdown, producer completion, FIFO/bank drain, replay persistence, optimizer restoration or runtime handoff validity.'
        ])
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    assert result.wasSuccessful()


if __name__ == '__main__':
    main()
