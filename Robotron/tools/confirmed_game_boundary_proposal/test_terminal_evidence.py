"""Reject score truncation even when a receipt and admission registry agree."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from game_journal_candidate_reviewed3 import GameJournal
from confirmed_terminal_evidence import MODE, collect_successors, validate_receipt_terminals, validate_terminal


class TerminalEvidenceTests(unittest.TestCase):
    def make(self, zero=False):
        with tempfile.TemporaryDirectory() as directory:
            now = [1000.]
            j = GameJournal(directory, clock=lambda: now[0], completion_policy=MODE)
            cs = dict(game_uid=1, client_slot=4096, eval_only=True)
            context = lambda: dict(experiment='test', measurement_active=True,
                                   measurement_generation=1, epsilon=0., expert_ratio=0., difficulty=5)
            previous = [20000, 2, True, False, False, 3, 0]
            def observe(score, *, alive=True, reserves=2, reset=False, start=False, recent=False):
                now[0] += 1
                current = (score, 1, alive, False, start, 0, previous[6]+1)
                inputs = (tuple(previous), current, previous[0], previous[1], previous[2],
                          0, 0, recent, reset, 'accept')
                frame = SimpleNamespace(game_score=score, level_number=1, player_alive=alive,
                                        done=False, start_pressed=start, num_lasers=reserves, lives=0)
                j.observe(1, frame, cs, new_game=reset, context=context, boundary_inputs=inputs)
                previous[:] = current
            observe(0, alive=False, reserves=3, reset=True)
            observe(0 if zero else 459825)
            observe(0 if zero else 739300, alive=False, reserves=0)
            if not zero:
                cs['game_uid'] = 2
            observe(0, alive=False, reserves=2, reset=not zero, recent=True)
            j.disconnect(1, context)
            games = [json.loads(x) for x in (Path(directory)/'games.jsonl').read_text().splitlines()]
            starts = [json.loads(x) for x in (Path(directory)/'measurement_starts.jsonl').read_text().splitlines()]
            return games, starts

    def test_nonzero_and_zero_use_original_successor_registry(self):
        for zero in (False, True):
            games, starts = self.make(zero)
            before = copy.deepcopy((games, starts))
            successors = collect_successors(games[:1], games, starts)
            receipt = dict(job=dict(completion_policy=MODE, game_boundary_diagnostics=True),
                           terminal_successors=successors)
            proof = validate_receipt_terminals(receipt, games[:1])
            self.assertEqual(proof[0]['score'], 0 if zero else 739300)
            self.assertEqual((games, starts), before)

    def test_agreeing_truncated_receipt_and_raw_row_still_fail_final_baseline(self):
        games, starts = self.make()
        games[0]['score'] = 459825
        games[0]['terminal_confirmation']['previous_score'] = 459825
        with self.assertRaisesRegex(ValueError, 'final classifier baseline'):
            collect_successors(games[:1], games, starts)

    def test_missing_or_changed_original_successor_is_rejected(self):
        for mutation in (lambda g,s: s.pop(), lambda g,s: g.pop(),
                         lambda g,s: s[-1]['context'].update(epsilon=.1),
                         lambda g,s: s[-1].update(game_uid=99),
                         lambda g,s: s.append(copy.deepcopy(s[-1]))):
            games, starts = self.make()
            mutation(games, starts)
            with self.assertRaises(ValueError):
                collect_successors(games[:1], games, starts)

    def test_legacy_or_self_consistent_only_records_fail_closed(self):
        games, starts = self.make()
        for mutation in (lambda r:r.pop('completion_policy'),
                         lambda r:r.pop('terminal_confirmation'),
                         lambda r:r['terminal_confirmation'].pop('ingest_boundary_inputs'),
                         lambda r:r.update(boundary_reason='wire_lives_exhausted')):
            row = copy.deepcopy(games[0]); mutation(row)
            with self.assertRaises(ValueError):
                validate_terminal(row, starts[-1])

    def test_raw_game_row_must_equal_receipt_not_just_its_start(self):
        games, starts = self.make()
        row = copy.deepcopy(games[0]); row['deaths'] = 42
        with self.assertRaisesRegex(ValueError, 'admitted row differs'):
            collect_successors([row], games, starts)

    def test_zero_requires_reserve_restart_and_next_original_start(self):
        games, starts = self.make(True)
        for field, value in (('previous_raw_reserves', 1), ('next_raw_reserves', 255),
                             ('next_raw_reserves', True), ('restart_pulse', False),
                             ('next_wave', 2), ('classifier_new_game', True)):
            row = copy.deepcopy(games[0]); row['terminal_confirmation'][field] = value
            with self.assertRaises(ValueError):
                validate_terminal(row, starts[-1])

    def test_successor_inputs_cannot_be_replaced_by_unrelated_reset(self):
        games, starts = self.make()
        successor = copy.deepcopy(starts[-1])
        successor['context']['game_boundary_diagnostics']['classifier_previous']['raw_score'] = 1
        with self.assertRaisesRegex(ValueError, 'successor accepted inputs'):
            validate_terminal(games[0], successor)

    def test_missing_policy_and_partial_successor_coverage_rejected(self):
        games, starts = self.make()
        successors = collect_successors(games[:1], games, starts)
        for job in ({}, dict(completion_policy=MODE, game_boundary_diagnostics=False)):
            with self.assertRaises(ValueError):
                validate_receipt_terminals(dict(job=job, terminal_successors=successors), games[:1])
        with self.assertRaises(ValueError):
            validate_receipt_terminals(dict(job=dict(completion_policy=MODE,
                game_boundary_diagnostics=True), terminal_successors={}), games[:1])


if __name__ == '__main__':
    unittest.main()
