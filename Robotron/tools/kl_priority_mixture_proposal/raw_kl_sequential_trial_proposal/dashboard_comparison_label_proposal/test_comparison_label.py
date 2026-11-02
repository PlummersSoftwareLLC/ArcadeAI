"""Authored stdlib display regressions; no live state, learner or model data."""
import json
from pathlib import Path
import tempfile
import unittest

from .experiment_status import ExperimentStatusReader


class ComparisonLabelContracts(unittest.TestCase):
    def plan(self):
        return dict(checkpoints=dict(
            reference=dict(source='/private/models/fresh3-448M-confirmed.pt'),
            candidate=dict(source='/private/models/rawkl-first8M-20261017-trial02.pt')))

    def test_actual_state_override_reaches_snapshot_and_distinguishes_increment_from_total(self):
        # Real private JSON traversal verifies the new field's actual state path.
        # 8M names the trial increment; the frozen candidate has511985990 total.
        label = '448M vs KL candidate (~512M total)'
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory) / 'Robotron'; logs = game / 'logs'; campaign = logs / 'campaign'
            campaign.mkdir(parents=True)
            state = logs / 'state.json'
            state.write_text(json.dumps(dict(active_quality_job=dict(
                directory=str(campaign), comparison_label=label))))
            (campaign / 'plan.json').write_text(json.dumps(self.plan()))
            (campaign / 'status.json').write_text(json.dumps(dict(
                state='running', updated_unix_s=1000, legs=[])))
            reader = ExperimentStatusReader(game_root=game, state_path=state,
                clock=lambda: 1000, monotonic=lambda: 1)
            result = reader.snapshot()
            self.assertTrue(result['available'])
            self.assertEqual(result['comparison'], label)
            self.assertFalse(result['stale'])
            self.assertEqual(result['legs'], [])

    def test_missing_blank_or_nontext_override_preserves_legacy_milestone_fallback(self):
        for active in ({}, {'comparison_label': None}, {'comparison_label': ''},
                       {'comparison_label': ' \t\n '}, {'comparison_label': 512},
                       {'comparison_label': {'total': 512}}):
            with self.subTest(active=active):
                self.assertEqual(ExperimentStatusReader._comparison(self.plan(), active, []), '448M vs 8M')
        plan = dict(checkpoints=dict(reference=dict(source='/models/fresh3-384M.pt'),
                                     candidate=dict(source='/models/fresh3-448M.pt')))
        self.assertEqual(ExperimentStatusReader._comparison(plan, {}, []), '384M vs 448M')
        self.assertEqual(ExperimentStatusReader._comparison({}, {}, [
            dict(role='reference', label='held reference'), dict(role='candidate', label='new candidate')]),
            'held reference vs new candidate')

    def test_explicit_label_uses_existing_bounded_path_redaction_and_whitespace_rules(self):
        active = dict(comparison_label=' \n448M\t vs  KL candidate (~512M total)  ')
        self.assertEqual(ExperimentStatusReader._comparison(self.plan(), active, []),
                         '448M vs KL candidate (~512M total)')
        label = 'reference /private/model.pt vs candidate ' + 'x' * 300
        result = ExperimentStatusReader._comparison(self.plan(), dict(comparison_label=label), [])
        self.assertEqual(len(result), 160)
        self.assertNotIn('/private/model.pt', result)
        self.assertTrue(result.startswith('reference [path] vs candidate '))


if __name__ == '__main__':
    unittest.main()
