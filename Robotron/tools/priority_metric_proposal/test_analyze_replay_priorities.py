import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from .analyze_replay_priorities import bank_generation, counterfactual_weights, per_row_metrics, projected_target, summarize


class PriorityDiagnosticTests(unittest.TestCase):
    def test_perfect_broad_prediction_has_entropy_ce_but_zero_kl(self):
        target = torch.tensor([[.2, .3, .5], [0., 1., 0.]])
        prediction = torch.tensor([[.2, .3, .5], [.2, .6, .2]])
        ce, entropy, kl = per_row_metrics(prediction.log(), target)
        self.assertGreater(float(ce[0]), 1.)
        torch.testing.assert_close(ce[0], entropy[0])
        self.assertEqual(float(kl[0]), 0.)
        self.assertGreater(float(kl[1]), .5)
        self.assertEqual(float(entropy[1]), 0.)

    def test_exact_terminal_and_clipped_projection_retain_mass(self):
        support = torch.tensor([-1., 0., 1.])
        target_p = torch.tensor([[.2, .3, .5]]).expand(4, -1)
        actual = projected_target(target_p, torch.tensor([-3., 0., 3., .25]),
            torch.tensor([1., 1., 1., 0.]), torch.ones(4), support, .9, 0.)
        torch.testing.assert_close(actual[:3], torch.eye(3))
        torch.testing.assert_close(actual.sum(1), torch.ones(4))
        self.assertTrue(torch.isfinite(actual).all())

    def test_beta_one_corrects_expected_contribution_and_zero_kl_is_finite(self):
        result = counterfactual_weights(np.array([0., .001, .2, 3.]), beta=1.)
        self.assertAlmostEqual(result['effective_gradient_contribution_fraction']['minimum'], .25)
        self.assertAlmostEqual(result['effective_gradient_contribution_fraction']['maximum'], .25)
        self.assertTrue(np.isfinite(result['largest_to_smallest_priority_ratio']))
        self.assertLess(result['expected_normalized_weight_under_priority_draw'], 1.)
        json.dumps(result, allow_nan=False)

    def test_current_generation_wins_over_stale_legacy_files_and_invalid_paths_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'generations/gen-current').mkdir(parents=True)
            (path / 'hof_meta.npz').touch()
            pointer = dict(schema='robotron-bank-generation-v1', bank='hof', generation='gen-current')
            (path / 'CURRENT.json').write_text(json.dumps(pointer))
            self.assertEqual(bank_generation(path, 'hof')[0], path / 'generations/gen-current')
            pointer['generation'] = '../escape'
            (path / 'CURRENT.json').write_text(json.dumps(pointer))
            with self.assertRaises(ValueError):
                bank_generation(path, 'hof')

    def test_summary_exposes_entropy_dominated_ranking_difference(self):
        entropy = np.array([1., 2., 3., 4.])
        kl = np.array([.1, .02, .03, .04])
        result = summarize(entropy + kl, entropy, kl)
        self.assertGreater(result['pearson_ce_vs_entropy'], .99)
        self.assertEqual(result['top_decile_overlap_fraction'], 0.)
        self.assertGreater(result['entropy_fraction_of_mean_ce'], .98)


if __name__ == '__main__':
    unittest.main()
