"""Regression for actual CPU-report clock shape and one-update startup path."""
import unittest
import activate_reviewed2 as activation


class StartupScope(unittest.TestCase):
    def fixture(self):
        return dict(training_steps=10, optimized_samples=40960, learner_frame_count=1000, frame_count=2000)

    def test_diagnostic_fields_do_not_expand_the_four_clock_job(self):
        source = dict(self.fixture(), epsilon=.1, expert_ratio=.1, baseline_batch_size=512,
                      state_size=11128, lr_gear='climb')
        self.assertEqual(activation.clock_floor(source), self.fixture())
        self.assertEqual(set(activation.clock_floor(source)), set(activation.CLOCKS))

    def test_one_actual_update_is_retained_without_inventing_actor_frames(self):
        before = self.fixture()
        self.assertEqual(activation.startup_delta(before,before), 0)
        after = dict(before, training_steps=11, optimized_samples=45056)
        self.assertEqual(activation.startup_delta(after,before), 1)
        self.assertEqual(activation.clock_floor(after), after)

    def test_extra_regressed_inconsistent_or_actor_updates_are_rejected(self):
        before = self.fixture()
        for changed in (dict(before, training_steps=12, optimized_samples=49152),
                        dict(before, training_steps=9, optimized_samples=36864),
                        dict(before, training_steps=11), dict(before, optimized_samples=45056),
                        dict(before, learner_frame_count=1001), dict(before, frame_count=2001),
                        dict(before, training_steps=True)):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                activation.startup_delta(changed,before)


if __name__ == '__main__':
    unittest.main()
