"""Pure CPU/stdlib tests for narrowly admitting proven AMP-skipped attempts."""
import copy
import math
import unittest

from . import whole_agent_smoke_worker as worker


def exposure(*, attempts=0, applied=0, skipped=0, unavailable=0):
    return dict(schema='robotron-optimizer-exposure-v1', enabled=True,
                available=attempts > 0 and unavailable == 0,
                process_id=123, instance_monotonic_ns=456, epoch=0,
                total=dict(attempts_started=attempts, outcomes_recorded=attempts,
                           applied=applied, amp_skipped=skipped, unavailable=unavailable),
                unclassified_started_total=0, prior_epoch_outcomes_total=0,
                last_reason='single_cuda_found_inf')


def attempt_pair(outcome='amp_skipped', *, initial=True):
    before = dict(adam_steps={'trunk.weight': 0., 'head.weight': 0.},
                  online_sha256='a'*64, adam_nonzero_state_sha256='c'*64,
                  scale=65536., exposure=exposure())
    if not initial:
        before['adam_steps'] = {'trunk.weight': 4., 'head.weight': 3.}
        before['exposure'] = exposure(attempts=5, applied=4, skipped=1)
    after = copy.deepcopy(before)
    total = after['exposure']['total']
    total['attempts_started'] += 1
    total['outcomes_recorded'] += 1
    total[outcome] += 1
    after['exposure']['available'] = True
    if outcome == 'amp_skipped':
        after['scale'] /= 2
    elif outcome == 'applied':
        after['adam_steps']['trunk.weight'] += 1
        after['online_sha256'] = 'b'*64
        after['adam_nonzero_state_sha256'] = 'd'*64
    return before, after


class AmpAttemptClassificationTests(unittest.TestCase):
    def classify(self, before, after, *, gradients=True, persistent=True, loss=.25):
        original = copy.deepcopy((before, after))
        try:
            return worker.classify_optimizer_attempt(before, after, loss=loss,
                gradients_finite=gradients, persistent_finite=persistent)
        finally:
            self.assertEqual((before, after), original, 'Classifier mutated its evidence')

    def rejected(self, before, after, **kwargs):
        with self.assertRaises(RuntimeError):
            self.classify(before, after, **kwargs)

    def test_first_proven_amp_skip_allows_nonfinite_gradients_with_zero_initial_exposure(self):
        before, after = attempt_pair()
        self.assertFalse(before['exposure']['available'])
        self.assertEqual(self.classify(before, after, gradients=False), 'amp_skipped')

    def test_proven_later_amp_skip_requires_same_adam_slots_online_and_moments(self):
        before, after = attempt_pair(initial=False)
        self.assertEqual(self.classify(before, after, gradients=False), 'amp_skipped')

    def test_proven_skip_does_not_require_observed_bad_gradient_if_exposure_proves_skip(self):
        before, after = attempt_pair()
        self.assertEqual(self.classify(before, after), 'amp_skipped')

    def test_applied_requires_exposure_and_actual_step_and_parameter_progress(self):
        for initial in (True, False):
            with self.subTest(initial=initial):
                before, after = attempt_pair('applied', initial=initial)
                self.assertEqual(self.classify(before, after), 'applied')

    def test_applied_may_grow_a_finite_positive_scaler(self):
        before, after = attempt_pair('applied')
        after['scale'] *= 2
        self.assertEqual(self.classify(before, after), 'applied')

    def test_applied_nonfinite_gradients_are_never_accepted(self):
        before, after = attempt_pair('applied')
        self.rejected(before, after, gradients=False)

    def test_nonfinite_persistent_state_never_qualifies_even_for_exposure_skip(self):
        for outcome in ('amp_skipped', 'applied'):
            with self.subTest(outcome=outcome):
                before, after = attempt_pair(outcome)
                self.rejected(before, after, gradients=False, persistent=False)

    def test_nonfinite_or_missing_loss_never_qualifies(self):
        for value in (None, math.nan, math.inf, -math.inf):
            with self.subTest(loss=value):
                before, after = attempt_pair()
                self.rejected(before, after, gradients=False, loss=value)

    def test_nonfinite_nonpositive_or_increasing_skip_scales_are_rejected(self):
        for side in ('before', 'after'):
            for value in (0., -1., math.nan, math.inf, -math.inf):
                with self.subTest(side=side, scale=value):
                    before, after = attempt_pair()
                    (before if side == 'before' else after)['scale'] = value
                    self.rejected(before, after, gradients=False)
        for scale in (65536., 131072.):
            with self.subTest(skip_scale=scale):
                before, after = attempt_pair()
                after['scale'] = scale
                self.rejected(before, after, gradients=False)

    def test_skip_rejects_online_or_nonzero_adam_moment_changes(self):
        for key in ('online_sha256', 'adam_nonzero_state_sha256'):
            with self.subTest(key=key):
                before, after = attempt_pair()
                after[key] = 'e'*64
                self.rejected(before, after, gradients=False)

    def test_skip_rejects_per_parameter_progress_hidden_by_unchanged_maximum(self):
        before, after = attempt_pair(initial=False)
        before['adam_steps'] = {'trunk.weight': 5., 'head.weight': 0.}
        after['adam_steps'] = {'trunk.weight': 5., 'head.weight': 1.}
        self.rejected(before, after, gradients=False)

    def test_changed_adam_slot_set_and_nonfinite_or_negative_steps_fail(self):
        for side in ('before', 'after'):
            for value in (math.nan, math.inf, -1.):
                with self.subTest(side=side, step=value):
                    before, after = attempt_pair()
                    (before if side == 'before' else after)['adam_steps']['head.weight'] = value
                    self.rejected(before, after, gradients=False)
        for action in ('add', 'remove'):
            with self.subTest(action=action):
                before, after = attempt_pair()
                if action == 'add': after['adam_steps']['unknown.weight'] = 0.
                else: after['adam_steps'].pop('head.weight')
                self.rejected(before, after, gradients=False)
        before, after = attempt_pair()
        before['adam_steps'] = after['adam_steps'] = {}
        self.rejected(before, after, gradients=False)

    def test_applied_without_changed_weights_or_step_advance_fails(self):
        for key in ('online_sha256', 'adam_steps'):
            with self.subTest(missing=key):
                before, after = attempt_pair('applied')
                after[key] = copy.deepcopy(before[key])
                self.rejected(before, after)

    def test_applied_rejects_any_step_regression_despite_other_step_progress(self):
        before, after = attempt_pair('applied', initial=False)
        after['adam_steps']['head.weight'] -= 1
        self.rejected(before, after)

    def test_exposure_identity_schema_enabled_and_mode_must_match(self):
        mutations = [('process_id', 999), ('instance_monotonic_ns', 999), ('epoch', 1),
                     ('schema', 'unknown'), ('enabled', False),
                     ('last_reason', 'unsupported_torch'), ('available', False),
                     ('unclassified_started_total', 1), ('prior_epoch_outcomes_total', 1)]
        for key, value in mutations:
            with self.subTest(field=key):
                before, after = attempt_pair()
                after['exposure'][key] = value
                self.rejected(before, after, gradients=False)

    def test_unavailable_before_is_allowed_only_for_zero_initial_totals(self):
        before, after = attempt_pair(initial=False)
        before['exposure']['available'] = False
        self.rejected(before, after, gradients=False)

    def test_unavailable_mixed_multiple_or_missing_optimizer_outcome_fails(self):
        edits = [dict(unavailable=1, amp_skipped=0), dict(applied=1),
                 dict(attempts_started=2), dict(outcomes_recorded=0),
                 dict(attempts_started=2, outcomes_recorded=2, amp_skipped=2),
                 dict(amp_skipped=0), dict(amp_skipped=-1)]
        for change in edits:
            with self.subTest(change=change):
                before, after = attempt_pair()
                after['exposure']['total'].update(change)
                self.rejected(before, after, gradients=False)

    def test_malformed_evidence_fails_with_runtime_error(self):
        for key in ('adam_steps', 'online_sha256', 'adam_nonzero_state_sha256', 'scale', 'exposure'):
            with self.subTest(missing=key):
                before, after = attempt_pair()
                after.pop(key)
                self.rejected(before, after, gradients=False)


if __name__ == '__main__':
    unittest.main()
