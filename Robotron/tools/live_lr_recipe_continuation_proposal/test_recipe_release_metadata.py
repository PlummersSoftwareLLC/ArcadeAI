"""Unexecuted stdlib metadata guards; root alone may execute this future suite.

The positive release fixture is the authentic closed 567c JSON. No referenced
model, live process, control, or campaign file is opened by these tests.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
RECIPE_SHA = 'f11e4c8d6725c04c4495b416318713f675ba9305ffe6f7c4009a3bff9b860d0e'
RELEASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/postdiagnostic-live8M-candidate-root-preparation-20261018/root-final779-not-improved-campaign-disposition-and-source-freeze-release-20261018.json')
RELEASE_SHA = '567c32a2d89efca4b0dbd972eea0425880d5005ddd0cdf863952367fc24c0e9a'


class RecipeReleaseMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = HERE / 'recipe.py'
        if hashlib.sha256(source.read_bytes()).hexdigest() != RECIPE_SHA:
            raise AssertionError('Recipe source changed')
        raw = RELEASE.read_bytes()
        if hashlib.sha256(raw).hexdigest() != RELEASE_SHA:
            raise AssertionError('Authentic closed release changed')
        cls.release = json.loads(raw)
        cls.owner = dict(cls.release['main_original'], unit='unused-pure-metadata', cgroup='unused-pure-metadata')
        spec = importlib.util.spec_from_file_location('_recipe_release_metadata_guard', source)
        cls.recipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.recipe)

    def test_authentic_closed_not_improved_release_and_original_actor_join(self):
        value = copy.deepcopy(self.release)
        self.assertIs(self.recipe.check_release(value, self.owner), value)
        actors = [{k: row[k] for k in ('slot', 'pid', 'starttime_ticks')}
                  for row in value['original192actors_preserved']]
        actors.reverse()  # The identity join is independent of record order.
        self.assertIs(self.recipe.check_release(value, self.owner, actors), value)
        self.assertIs(value['candidate_qualified'], False)
        self.assertIs(value['both_independent_candidate_gates_pass'], False)

    def test_rejects_boolean_missing_duplicate_and_lost_mask_records(self):
        cases = []
        bad = copy.deepcopy(self.release); bad['original192actors_preserved'] = True; cases.append(bad)
        bad = copy.deepcopy(self.release); del bad['original192actors_preserved']; cases.append(bad)
        for field, replacement in (('slot', 1), ('pid', self.release['original192actors_preserved'][1]['pid']),
                                   ('starttime_ticks', True), ('mask_matches', False)):
            bad = copy.deepcopy(self.release)
            bad['original192actors_preserved'][0][field] = replacement
            cases.append(bad)
        bad = copy.deepcopy(self.release); bad['original192actors_preserved'][0]['extra'] = 0; cases.append(bad)
        for bad in cases:
            with self.subTest(records=repr(bad.get('original192actors_preserved'))[:90]):
                with self.assertRaises((ValueError, KeyError)):
                    self.recipe.check_release(bad, self.owner)

    def test_baseline_replacement_and_false_success_are_refused(self):
        actors = [{k: row[k] for k in ('slot', 'pid', 'starttime_ticks')}
                  for row in self.release['original192actors_preserved']]
        for key in ('slot', 'pid', 'starttime_ticks'):
            bad = copy.deepcopy(actors); bad[0][key] += 1000000
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.recipe.check_release(self.release, self.owner, bad)
        for key in ('candidate_qualified', 'both_independent_candidate_gates_pass', 'promotion'):
            bad = copy.deepcopy(self.release); bad[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.recipe.check_release(bad, self.owner)
        bad_owner = dict(self.owner, starttime_ticks=self.owner['starttime_ticks'] + 1)
        with self.assertRaises(ValueError):
            self.recipe.check_release(self.release, bad_owner)

    def test_two_exact_recipes_and_control_changes_only_label_and_lr(self):
        before = dict(experiment='historical-label', reason='unchanged', lr_scale=.5,
                      epsilon_ramp=dict(start=.1, end=.1, duration_frames=0))
        for scale, lr in ((.25, 1.25e-5), (.5, 2.5e-5)):
            recipe = self.recipe.for_scale(scale)
            self.assertEqual(recipe['scheduled_lr'], lr)
            after = dict(before, experiment='new-label', lr_scale=scale)
            self.recipe.check_control(before, after, 'new-label', recipe)
            context = self.recipe.held_context(recipe, self.recipe.HELD_50)
            self.assertEqual(self.recipe.from_held(context), recipe)
            self.assertEqual(context['optimizer_lr'], lr)
            for key, replacement in (('reason', 'changed'), ('epsilon_ramp', dict(start=.05, end=.05))):
                bad = dict(after); bad[key] = replacement
                with self.subTest(scale=scale, key=key), self.assertRaises(ValueError):
                    self.recipe.check_control(before, bad, 'new-label', recipe)
        for scale in (1., .125, True, 0):
            with self.subTest(scale=scale), self.assertRaises(ValueError):
                self.recipe.for_scale(scale)


if __name__ == '__main__':
    unittest.main()
