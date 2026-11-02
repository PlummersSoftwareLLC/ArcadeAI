"""Private CPU regression: observed truncated prefixes must await real resets.

The 142 cases use the observed terminal score and later accepted classifier
baseline, not a fabricated claim to replay complete original wire streams.
"""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from game_journal_candidate import GameJournal

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
EVIDENCE=ROOT/'logs/managed-learning-20261015/run-26/post-continuity-original-terminal-score-truncation-forensic-archive-20261018/root-original-terminal-score-contradiction.json'


class ConfirmedBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=1000.;self.cs=dict(game_uid=1,client_slot=4096,eval_only=True,
            journal_experiment='private-confirmed',journal_measurement_active=True,
            journal_measurement_generation=1)
        self.journal=GameJournal(self.temp.name,clock=lambda:self.now,
            completion_policy='confirmed_reset_reserves_v1')

    def context(self):
        return dict(experiment='private-confirmed',measurement_active=True,
            measurement_generation=1,epsilon=0.,expert_ratio=0.,difficulty=5)

    def frame(self,score=0,alive=True,done=False,lives=3,reserves=2,start=False,
              level=1,new_game=False):
        self.now+=1
        value=SimpleNamespace(game_score=score,player_alive=alive,done=done,
            lives=lives,num_lasers=reserves,start_pressed=start,level_number=level)
        self.journal.observe(1,value,self.cs,new_game=new_game,context=self.context)

    def begin(self,score=100):
        self.frame(score=0,alive=False,reserves=3,new_game=True)
        self.frame(score=score,reserves=2)

    def reset(self):
        self.cs['game_uid']+=1
        self.frame(score=0,alive=False,reserves=3,new_game=True)

    def rows(self):
        p=Path(self.temp.name)/'games.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def test_wire_exhaustion_cannot_truncate_later_score(self):
        self.begin()
        self.frame(score=459825,alive=False,done=True,lives=0,reserves=1)
        self.assertEqual(self.journal.summary()['count'],0)
        self.frame(score=739300,lives=0,reserves=0)
        self.assertEqual(self.journal.summary()['count'],0)
        self.reset()
        self.assertEqual(self.journal.summary()['count'],1)
        self.assertEqual(self.rows()[0]['score'],739300)
        self.assertEqual(self.rows()[0]['boundary_reason'],'score_reset')
        self.assertEqual(self.rows()[0]['terminal_confirmation']['previous_score'],739300)

    def test_142_original_truncated_prefixes_retain_later_observed_baseline(self):
        evidence=json.loads(EVIDENCE.read_text());self.assertEqual(evidence['linked_later_real_resets'],142)
        for item in evidence['links']:
            with self.subTest(id=item['id']),tempfile.TemporaryDirectory() as directory:
                j=GameJournal(directory,clock=lambda:self.now,
                    completion_policy='confirmed_reset_reserves_v1')
                cs=dict(self.cs);cs['game_uid']=1
                def observe(score,alive=True,done=False,lives=3,new_game=False):
                    self.now+=1
                    f=SimpleNamespace(game_score=score,level_number=1,player_alive=alive,
                        done=done,lives=lives,num_lasers=2,start_pressed=False)
                    j.observe(1,f,cs,new_game=new_game,context=self.context)
                observe(0,False,new_game=True);observe(0)
                observe(item['registered_terminal_score'],False,True,0)
                self.assertEqual(j.summary()['count'],0)
                observe(item['next_classifier_baseline'])
                cs['game_uid']=2;observe(0,False,new_game=True)
                self.assertEqual(j.summary()['count'],1)
                self.assertEqual(j.summary()['mean'],item['next_classifier_baseline'])

    def test_zero_score_game_needs_real_reserve_replenishment(self):
        self.begin(score=0)
        for reserve in (1,0,0):
            self.frame(score=0,alive=False,done=True,lives=0,reserves=reserve)
            self.frame(score=0,lives=0,reserves=reserve)
        self.assertEqual(self.journal.summary()['count'],0)
        self.frame(score=0,alive=False,lives=0,reserves=0,start=True)
        self.assertEqual(self.journal.summary()['count'],0)
        self.frame(score=0,alive=False,lives=3,reserves=3)
        self.assertEqual(self.journal.summary()['count'],1)
        row=self.rows()[0]
        self.assertEqual(row['score'],0);self.assertTrue(row['eligible'])
        self.assertEqual(row['boundary_reason'],'zero_score_restart')
        self.assertEqual(row['terminal_confirmation']['previous_raw_reserves'],0)
        self.assertEqual(row['terminal_confirmation']['next_raw_reserves'],3)

    def test_wave2_or_missing_reserves_cannot_fake_zero_restart(self):
        for raw in (None,255,True):
            with self.subTest(raw=raw),tempfile.TemporaryDirectory() as directory:
                self.journal=GameJournal(directory,clock=lambda:self.now,
                    completion_policy='confirmed_reset_reserves_v1')
                self.begin(score=0)
                self.frame(score=0,alive=False,lives=0,reserves=0,start=True)
                self.frame(score=0,alive=False,lives=3,reserves=raw)
                self.assertEqual(self.journal.summary()['count'],0)
        self.journal=GameJournal(self.temp.name,clock=lambda:self.now,
            completion_policy='confirmed_reset_reserves_v1')
        self.begin(score=0)
        self.frame(score=0,alive=False,lives=0,reserves=0,start=True)
        self.frame(score=0,alive=False,lives=3,reserves=3,level=2)
        self.assertEqual(self.journal.summary()['count'],0)

    def test_positive_score_reserve_increase_is_not_zero_restart(self):
        self.begin(score=100)
        self.frame(score=100,alive=False,lives=0,reserves=0,start=True)
        self.frame(score=100,reserves=3)
        self.assertEqual(self.journal.summary()['count'],0)

    def test_unexplained_uid_change_is_partial(self):
        self.begin(score=100)
        self.cs['game_uid']+=1;self.frame(score=100)
        self.assertEqual(self.journal.summary()['count'],0)
        self.assertFalse(self.rows()[0]['complete']);self.assertFalse(self.rows()[0]['eligible'])
        self.assertEqual(self.rows()[0]['boundary_reason'],'unconfirmed_game_uid_changed')

    def test_late_tail_waits_for_confirmed_reset_and_keeps_full_score(self):
        self.begin();start=self.now-1;close=self.now+.5
        self.frame(score=100,alive=False,done=True,lives=0)
        pending=self.journal.cohort_status('private-confirmed',start,close)
        self.assertTrue(pending['closed']);self.assertFalse(pending['complete'])
        self.assertEqual((pending['started'],pending['count'],pending['pending']),(1,0,1))
        self.now+=100;self.frame(score=900000);self.reset()
        completed=self.journal.cohort_status('private-confirmed',start,close)
        self.assertTrue(completed['complete']);self.assertEqual(completed['count'],1)
        self.assertEqual(completed['rows'][0]['score'],900000)

    def test_disconnect_never_becomes_a_completed_game(self):
        self.begin();self.frame(score=100,alive=False,done=True,lives=0)
        self.journal.disconnect(1,self.context)
        self.assertEqual(self.journal.summary()['count'],0)
        self.assertFalse(self.rows()[0]['complete'])

    def test_unwrapped_score_remains_continuous(self):
        self.begin(score=99999900)
        self.frame(score=100000300,alive=False,done=True,lives=0)
        self.assertEqual(self.journal.summary()['count'],0)
        self.reset();self.assertEqual(self.rows()[0]['score'],100000300)


if __name__=='__main__':unittest.main()
