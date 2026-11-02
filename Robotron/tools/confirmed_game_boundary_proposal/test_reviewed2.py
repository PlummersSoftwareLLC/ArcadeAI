"""Private revised proposal regressions; no installed module changes."""
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('game_journal_candidate', HERE/'game_journal_candidate_reviewed2.py')
candidate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = candidate
spec.loader.exec_module(candidate)
sys.path.insert(0, str(HERE))
import test_confirmed_boundaries as base


class RecentStartTests(base.ConfirmedBoundaryTests):
    def observe_restart(self, recent, new_game=False):
        from types import SimpleNamespace
        frame = SimpleNamespace(game_score=0, level_number=1, player_alive=False,
                                done=False, lives=0, num_lasers=2, start_pressed=False)
        # The accepted-ingest tuple has recent_start at 7, new_game at 8.
        inputs = (None, None, 0, 1, False, 3, 3, recent, new_game, 'accept')
        self.journal.observe(1, frame, self.cs, new_game=new_game,
                             context=self.context, boundary_inputs=inputs)

    def test_recent_start_only_confirms_zero_reserve_replenishment(self):
        self.begin(score=0)
        self.frame(score=0, alive=False, reserves=0, lives=0)
        self.observe_restart(True)
        self.assertEqual(self.journal.summary()['count'], 1)
        self.assertEqual(self.rows()[0]['boundary_reason'], 'zero_score_restart')
        self.assertTrue(self.rows()[0]['terminal_confirmation']['restart_pulse'])

    def test_no_restart_evidence_does_not_confirm_replenishment(self):
        self.begin(score=0)
        self.frame(score=0, alive=False, reserves=0, lives=0)
        self.observe_restart(False)
        self.assertEqual(self.journal.summary()['count'], 0)


if __name__ == '__main__':
    unittest.main()
