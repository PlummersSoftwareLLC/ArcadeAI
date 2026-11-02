"""Actual closed boundary checks and false-classifier-reset rejection."""
import copy
import importlib
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import audit_confirmed_completed_leg_reviewed2 as audit
import watch_confirmed_quality_audits_reviewed2 as watcher


class RomTerminalTests(unittest.TestCase):
    def setUp(self):
        self.base=audit.GAME/'logs/managed-learning-20261015/run-26'

    def boundaries(self):
        pairs=[]
        for stem in ('reference','integrated-no-fire-up'):
            directory=self.base/('confirmed-game-boundary-real-MAME-'+stem+'-original01-20261018/confirmed-journal')
            games=[json.loads(x) for x in (directory/'games.jsonl').read_bytes().splitlines()]
            starts=[json.loads(x) for x in (directory/'measurement_starts.jsonl').read_bytes().splitlines()]
            for row in games:
                if row['eligible'] and row['known_start']:
                    candidates=[s for s in starts if s['client_slot']==row['client_slot']
                        and s['game_uid']==row['terminal_confirmation']['next_game_uid']
                        and s['start_unix_s']>=row['end_unix_s']]
                    pairs.append((row,min(candidates,key=lambda s:s['start_unix_s'])))
        return pairs

    def test_all52_actual_closed_validation_boundaries_have_ROM_evidence(self):
        pairs=self.boundaries();self.assertEqual(len(pairs),52)
        for row,successor in pairs:
            audit.validate_rom_terminal(row,successor)

    def test_live_player_or_nonempty_reserves_cannot_be_only_classifier_reset(self):
        row,successor=self.boundaries()[-1]
        row=copy.deepcopy(row)
        for reserve in (1,5,None,True):
            row['terminal_confirmation']['previous_raw_reserves']=reserve
            with self.assertRaises(ValueError):audit.validate_rom_terminal(row,successor)
        row['terminal_confirmation']['previous_raw_reserves']=0
        for key in ('previous_accepted_wire','current_wire'):
            row['terminal_confirmation']['ingest_boundary_inputs'][key]['player_alive']=True
        with self.assertRaises(ValueError):audit.validate_rom_terminal(row,successor)

    def test_latched_old_start_does_not_replace_recent_accepted_restart(self):
        row,successor=self.boundaries()[-1]
        row=copy.deepcopy(row)
        row['terminal_confirmation']['restart_pulse']=True
        row['terminal_confirmation']['ingest_boundary_inputs']['recent_start']=False
        with self.assertRaises(ValueError):audit.validate_rom_terminal(row,successor)

    def test_observer_requires_full_ROM_proof_coverage(self):
        review=dict(valid=True,leg=1,plan_sha256='a'*64,
            schema='robotron-confirmed-original-terminal-leg-v1',statistics=dict(count=50),
            original_terminal_readback=dict(status='PASS',verified_games=50),
            rom_game_over_evidence=dict(status='PASS',verified_games=50))
        watcher.validate_review(review,1,'a'*64)
        for value in ({},dict(status='FAIL',verified_games=50),dict(status='PASS',verified_games=49)):
            review['rom_game_over_evidence']=value
            with self.assertRaises(ValueError):watcher.validate_review(review,1,'a'*64)


if __name__=='__main__':unittest.main()
