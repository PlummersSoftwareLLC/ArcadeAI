import copy
import time
import unittest
from unittest.mock import patch

from . import watch_learning_window as window
from .watch_learning_window import additions, observe, ready, validate


def sample(learner=100, accepted=100):
    lineage = dict(process_id=123, instance_monotonic_ns=456, epoch=1,
                   epoch_reason='restore', enabled=True, available=True)
    return dict(ts=time.time(), pipeline_snapshot_age_s=0, training_enabled=True,
        measurement_active=False, lr=3.125e-6, epsilon=.1, expert_ratio=.1, learner_frame_count=learner,
        training_steps=1, optimized_samples=4096, frame_count=200,
        client_count=1, client_rows=[dict(client_slot=0)],
        training_round=dict(total=192, completed=191, retired=191, active=1),
        host_pipeline=dict(learning_exposure=dict(
            optimizer=dict(lineage, total=dict(attempts_started=3, outcomes_recorded=3,
                           applied=2, amp_skipped=1, unavailable=0)),
            replay=dict(lineage, accepted_learner_total=accepted,
                        accepted_by_source_total=dict(dqn=accepted, epsilon=0,
                                                      expert=1000000000, eval=1000000000)))))


class LearningWindowTests(unittest.TestCase):
    def test_both_independent_exposure_thresholds_required(self):
        anchor = sample()
        self.assertFalse(ready(sample(8_000_100, 8_000_099), anchor, 8_000_000))
        self.assertFalse(ready(sample(8_000_099, 8_000_100), anchor, 8_000_000))
        self.assertTrue(ready(sample(8_000_100, 8_000_100), anchor, 8_000_000))
        self.assertEqual(additions(sample(), anchor)['accepted_DQN_epsilon'], 0)

    def test_epoch_change_cannot_rescue_window_with_advancing_counters(self):
        original = sample()
        changed = sample(200, 200)
        changed['host_pipeline']['learning_exposure']['replay']['epoch'] += 1
        with self.assertRaises(AssertionError):
            validate(changed, dict(pid=123), previous=original)

    def test_wrong_producer_or_duplicate_actor_or_unavailable_optimizer_rejected(self):
        for mutate in ['producer', 'actor', 'optimizer']:
            current = sample()
            if mutate == 'producer':
                current['host_pipeline']['learning_exposure']['optimizer']['process_id'] = 999
            elif mutate == 'actor':
                current['client_rows'].append(dict(client_slot=0))
                current['client_count'] = 2
            else:
                current['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable'] = 1
            with self.assertRaises(AssertionError):
                validate(current, dict(pid=123))

    def test_retired_clients_are_allowed_and_clock_rollback_is_not(self):
        current = sample()
        validate(current, dict(pid=123))
        previous = copy.deepcopy(current)
        current['training_steps'] = 0
        with self.assertRaises(AssertionError):
            validate(current, dict(pid=123), previous=previous)

    def test_transient_poll_failure_repolls_same_owner(self):
        with patch.object(window, 'owner', return_value=dict(pid=123)), \
             patch.object(window, 'api', side_effect=[OSError('temporary'), sample()]) as query, \
             patch.object(window.time, 'sleep'):
            self.assertEqual(observe(dict(pid=123))['client_count'], 1)
            self.assertEqual(query.call_count, 2)


if __name__ == '__main__':
    unittest.main()
