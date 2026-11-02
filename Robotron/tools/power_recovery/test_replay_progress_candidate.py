import copy
import unittest

from .watch_replay_progress_candidate import additions, ready


def snapshot():
    return dict(host_pipeline=dict(learning_exposure=dict(
        optimizer=dict(total=dict(applied=100, attempts_started=100)),
        replay=dict(accepted_total=10, accepted_by_source_total=dict(
            dqn=4, epsilon=1, expert=2, eval=3, unattributed=0)))))


class ReplayCandidateTests(unittest.TestCase):
    thresholds = dict(applied_updates=5000, replay_inserts=1_000_000, elapsed_s=3600)

    def test_fresh_eval_inserts_count_without_relabeling_DQN_data(self):
        anchor = snapshot()
        sample = copy.deepcopy(anchor)
        counters = sample['host_pipeline']['learning_exposure']
        counters['optimizer']['total']['applied'] += 5000
        counters['replay']['accepted_total'] += 1_000_000
        counters['replay']['accepted_by_source_total']['eval'] += 1_000_000
        added = additions(sample, anchor, 3600)
        self.assertTrue(ready(added, self.thresholds))
        self.assertEqual(added['by_source']['dqn'], 0)
        self.assertEqual(added['by_source']['epsilon'], 0)

    def test_every_precommitted_target_is_required(self):
        for missing in self.thresholds:
            with self.subTest(missing=missing):
                added = dict(self.thresholds)
                added[missing] -= 1
                self.assertFalse(ready(added, self.thresholds))

    def test_attempts_and_older_counts_cannot_replace_new_applied_updates(self):
        anchor = snapshot()
        sample = copy.deepcopy(anchor)
        sample['host_pipeline']['learning_exposure']['optimizer']['total']['attempts_started'] += 999999
        added = additions(sample, anchor, 3600)
        self.assertEqual(added['applied_updates'], 0)
        self.assertEqual(added['replay_inserts'], 0)
        self.assertFalse(ready(added, self.thresholds))

    def test_counter_rollback_and_inconsistent_attribution_rejected(self):
        for kind in ('rollback', 'attribution'):
            with self.subTest(kind=kind):
                anchor = snapshot()
                sample = copy.deepcopy(anchor)
                replay = sample['host_pipeline']['learning_exposure']['replay']
                replay['accepted_total'] += -1 if kind == 'rollback' else 1
                with self.assertRaises(AssertionError):
                    additions(sample, anchor, 1)


if __name__ == '__main__':
    unittest.main()
