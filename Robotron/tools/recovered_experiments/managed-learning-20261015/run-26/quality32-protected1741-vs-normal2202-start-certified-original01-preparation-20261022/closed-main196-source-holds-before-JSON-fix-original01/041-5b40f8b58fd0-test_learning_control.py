import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from .learning_control import LearningControl, EpsilonRamp


class LearningControlTests(unittest.TestCase):
    def test_learning_rate_scale_validation_is_persistent_and_atomic_on_error(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'control.json'
            path.write_text(json.dumps(dict(experiment='gentle', lr_scale=.5)))
            control = LearningControl(path)
            self.assertEqual(control.lr_scale, .5)
            for value in (0, 3, float('nan'), True, 'bad'):
                path.write_text(json.dumps(dict(experiment='bad', lr_scale=value)))
                self.assertFalse(control.refresh())
                self.assertEqual(control.lr_scale, .5)
                self.assertEqual(control.label, 'gentle')
            self.assertEqual(LearningControl(path.with_name('absent')).lr_scale, 1)

    def test_managed_learning_rate_multiplies_schedule_and_manual_scale(self):
        import sys
        from .agent import RainbowAgent
        module = sys.modules[RainbowAgent.__module__]
        agent = RainbowAgent.__new__(RainbowAgent)
        agent.baseline_batch_size = 512
        agent.optimized_samples = 512 * 200
        agent.lr_manual_scale = .8
        config = SimpleNamespace(lr=.001, lr_min=.0001, lr_warmup_steps=10,
                                 lr_cosine_period=1000)
        control = SimpleNamespace(lr_scale=1)
        with patch.object(module, 'RL_CONFIG', config), patch.object(module, 'learning_control', control):
            natural = agent.get_lr()
            control.lr_scale = .5
            self.assertAlmostEqual(agent.get_lr(), natural * .5)
            agent.lr_gear = 'hold'
            control.lr_scale = 1
            hold = agent.get_lr()
            control.lr_scale = .5
            self.assertAlmostEqual(agent.get_lr(), hold * .5)
        self.assertEqual(agent.optimized_samples, 512 * 200)

    def test_ramp_boundary_and_resume_anchor(self):
        ramp = EpsilonRamp(1000, .96, .5, 2000)
        self.assertAlmostEqual(ramp.value(0), .96)
        self.assertAlmostEqual(ramp.value(2000), .73)
        self.assertAlmostEqual(ramp.value(99999), .5)

    def test_invalid_control_keeps_last_valid_schedule(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'control.json'
            control = LearningControl(path)
            self.assertEqual(control.epsilon(20, .9), .9)
            path.write_text(json.dumps(dict(experiment='trial', epsilon_ramp=dict(anchor=10,start=.8,end=.5,duration=100))))
            self.assertTrue(control.refresh())
            self.assertAlmostEqual(control.epsilon(60,.9),.65)
            path.write_text('{broken')
            self.assertFalse(control.refresh())
            self.assertAlmostEqual(control.epsilon(60,.9),.65)
            path.unlink()
            self.assertTrue(control.refresh())
            self.assertEqual(control.epsilon(60,.9),.9)


    def test_measurement_validation_retains_last_valid_control(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'control.json'
            value=dict(experiment='hold',measurement=dict(label='frozen-current',cohort_s=120,timeout_s=600))
            path.write_text(json.dumps(value))
            control=LearningControl(path)
            self.assertEqual(control.measurement['label'],'frozen-current')
            value['measurement']['cohort_s']=float('nan')
            path.write_text(json.dumps(value))
            self.assertFalse(control.refresh())
            self.assertEqual(control.measurement['cohort_s'],120)
            value['measurement']=dict(label='../bad',cohort_s=120,timeout_s=600)
            path.write_text(json.dumps(value))
            self.assertFalse(control.refresh())
            self.assertEqual(control.measurement['label'],'frozen-current')


    def test_frozen_metric_getters_and_learner_clock(self):
        from .config import MetricsData
        state=MetricsData()
        state.measurement_active=True
        state.learner_frame_count=10
        state.epsilon=.7
        state.manual_pulse_active=True
        state.manual_pulse_frames_remaining=100
        self.assertEqual(state.get_effective_epsilon(),0)
        self.assertEqual(state.get_expert_ratio(),0)
        state.update_learner_frame_count(50)
        state.update_epsilon(50)
        self.assertEqual(state.learner_frame_count,10)
        self.assertEqual(state.manual_pulse_frames_remaining,100)
        state.measurement_active=False
        state.update_learner_frame_count(50)
        self.assertEqual(state.learner_frame_count,60)


if __name__ == '__main__':
    unittest.main()
