"""New independent full-tail journal contract; no neural model or real MAME.

Consumed host-drain modules supply fixture definitions only. This scope drives
the actual immutable journal with NEW synthetic accepted reset primitives and
checks the new auditor. No consumed test methods or scientific readers run.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


audit=load('_new_original_full_tail_journal_auditor',HERE/'audit_full_tail_games_v1.py')
defs=load('_consumed_all32_drain_fixture_definitions_only',HERE/'test_cohort_drain_v1.py')


class Fixture:
    def __init__(self):
        self.f=defs.Fixture()
        self.certified={}
        unknown={r['client_slot']:r for r in self.f.journal.completed}
        for slot,binding in self.f.bindings.items():
            game=self.f.journal.measurement_games[binding['journal_game_id']]
            self.certified[slot]=dict(binding,previous_journal_game_id=unknown[slot]['journal_game_id'],
                                      game_uid=game['game_uid'])

    def finish(self,slot,score=None,next_wave=1):
        f=self.f;cid=slot-4000;cs=f.states[slot]
        score=(slot-4096)*100 if score is None else score
        cs['frames']+=1
        f.journal.observe(cid,defs.frame(game_score=score,player_alive=True,num_lasers=0),cs,
                          context=lambda:f.context)
        f.advance(100_000);cs['frames']+=1
        f.journal.observe(cid,defs.frame(game_score=score,done=True,num_lasers=0,lives=1),cs,
                          context=lambda:f.context)
        previous=(score%100_000_000,1,False,True,False,1,cs['frames'])
        f.advance(100_000);cs['frames']+=1
        if score>0:cs['game_uid']+=1
        current=(0,next_wave,False,False,True,3,cs['frames'])
        boundary=(previous,current,score%100_000_000,1,False,cs['frames']-1,cs['frames'],True,score>0,'accept')
        f.journal.observe(cid,defs.frame(start_pressed=True,num_lasers=2,level_number=next_wave),cs,
            new_game=score>0,context=lambda:f.context,boundary_inputs=boundary)

    def complete(self,extra=False):
        f=self.f
        if extra:
            self.finish(4096)
            f.advance(100_000)
            f.journal.observe(96,defs.frame(player_alive=True,game_score=9_000_000),f.states[4096],
                              context=lambda:f.context)
        f.closed()
        for slot in defs.SLOTS:
            self.finish(slot,score=9_000_000 if extra and slot==4096 else None,
                        next_wave=1 if slot==4096 else 7)
        f.controller.tick()
        self.cohort=copy.deepcopy(f.controller.status()['cohort'])
        assert self.cohort['complete']and self.cohort['valid']
        for slot in defs.SLOTS:f.journal.disconnect(slot-4000,lambda:f.context)
        self.payloads={name:(Path(f.temp.name)/name).read_bytes()for name in
                       ('games.jsonl','measurement_starts.jsonl','lives.jsonl')}
        return self

    def args(self):return copy.deepcopy(dict(payloads=self.payloads,cohort=self.cohort,
        policy=self.f.policy,window=self.f.window,certified=self.certified))

    def close(self):self.f.close()


def update_row(payloads,name,identifier,change):
    rows=audit.lines(payloads[name])
    for row in rows:
        if row['journal_game_id']==identifier:change(row)
    payloads[name]=b''.join(audit.canonical(row)+b'\n'for row in rows)


class OriginalFullTailJournalReview(unittest.TestCase):
    def fixture(self,extra=False):
        f=Fixture();self.addCleanup(f.close);return f.complete(extra=extra)

    def test_actual_journal_zero_score_all32_preserves_unknown_same_UID_and_old_inactive_wave(self):
        f=self.fixture();result=audit.review(**f.args())
        self.assertEqual(result['statistics']['count'],32)
        self.assertEqual(result['statistics']['mean'],1550)
        self.assertEqual(result['statistics']['score_sum'],49600)
        self.assertEqual(len(result['terminal_links']),32);self.assertEqual(len(result['rom_links']),32)
        self.assertEqual(sum(x['verified_lives']for x in result['life_links']),32)
        self.assertFalse(result['quality_qualified']);self.assertFalse(result['promotion'])
        self.assertFalse(result['full_game_score_verified'])
        self.assertEqual(result['quality_minimum_games_unchanged'],50)
        rows=audit.indexed(audit.lines(f.payloads['games.jsonl']),'fixture')
        binding=f.certified[4096]
        self.assertEqual(rows[binding['previous_journal_game_id']]['game_uid'],rows[binding['journal_game_id']]['game_uid'])
        self.assertFalse(rows[binding['previous_journal_game_id']]['eligible'])
        self.assertTrue(any(r['terminal_confirmation']and r['terminal_confirmation']['next_wave']==7
                            for r in rows.values()))
        self.assertNotIn('torch',sys.modules)

    def test_extra33rd_admitted_high_score_game_and_zero_are_in_original_denominator(self):
        f=self.fixture(extra=True);result=audit.review(**f.args())
        self.assertEqual(result['statistics']['count'],33)
        self.assertEqual(result['statistics']['score_sum'],9_049_600)
        self.assertEqual(len(result['admitted_ids']),33)
        self.assertEqual(len(result['rom_links']),33)
        self.assertFalse(result['quality_qualified'])

    def test_missing_pending_filtered_duplicated_or_forged_statistics_fail(self):
        f=self.fixture()
        for damage in ('missing_start','missing_game','dropped_cohort','pending','duplicate','statistics'):
            with self.subTest(damage=damage):
                args=f.args();identifier=args['cohort']['started_ids'][0]
                if damage in ('missing_start','missing_game'):
                    name='measurement_starts.jsonl'if damage=='missing_start'else 'games.jsonl'
                    args['payloads'][name]=b''.join(audit.canonical(r)+b'\n'for r in audit.lines(args['payloads'][name])
                        if r['journal_game_id']!=identifier)
                elif damage=='dropped_cohort':args['cohort']['rows'].pop()
                elif damage=='pending':args['cohort']['pending']=1
                elif damage=='duplicate':args['payloads']['games.jsonl']+=args['payloads']['games.jsonl'].splitlines(True)[0]
                else:args['cohort']['mean']+=1
                with self.assertRaises(ValueError):audit.review(**args)

    def test_terminal_ROM_exhaustion_inactive_restart_and_original_successor_are_required(self):
        f=self.fixture()
        for damage in ('reserves','alive','restart','successor','classifier'):
            with self.subTest(damage=damage):
                args=f.args();row=args['cohort']['rows'][1];identifier=row['journal_game_id']
                terminal=row['terminal_confirmation'];diagnostic=terminal['ingest_boundary_inputs']
                if damage=='reserves':terminal['previous_raw_reserves']=1
                elif damage=='alive':
                    diagnostic['previous_accepted_wire']['player_alive']=True
                    diagnostic['current_wire']['player_alive']=True;terminal['next_alive']=True
                elif damage=='restart':diagnostic['recent_start']=False
                elif damage=='successor':terminal['next_journal_game_id']='invented'
                else:diagnostic['classifier_verdict']='reject'
                update_row(args['payloads'],'games.jsonl',identifier,lambda value:value.update(row))
                with self.assertRaises(ValueError):audit.review(**args)

    def test_original_life_identity_number_score_clocks_and_fixed_controls_are_checked(self):
        f=self.fixture()
        for damage in ('missing','number','client','score','clock','epsilon','generation'):
            with self.subTest(damage=damage):
                args=f.args();row=args['cohort']['rows'][1];identifier=row['journal_game_id']
                if damage=='missing':
                    args['payloads']['lives.jsonl']=b''.join(audit.canonical(r)+b'\n'for r in
                        audit.lines(args['payloads']['lives.jsonl'])if r['journal_game_id']!=identifier)
                else:
                    def change(value):
                        if damage=='number':value['life']=2
                        elif damage=='client':value['client_id']+=1
                        elif damage=='score':value['life_score']+=1
                        elif damage=='clock':value['context']['learner_frames']+=1
                        elif damage=='epsilon':value['context']['epsilon']=.1
                        else:value['context']['measurement_generation']+=1
                    update_row(args['payloads'],'lives.jsonl',identifier,change)
                with self.assertRaises(ValueError):audit.review(**args)

    def test_certificate_unknown_attachment_fixed_window_and_strict_JSON_are_preserved(self):
        f=self.fixture()
        for damage in ('certificate','unknown','window','slot','JSON'):
            with self.subTest(damage=damage):
                args=f.args();binding=args['certified'][4096]
                if damage=='certificate':binding['certificate_identifier']='f'*64
                elif damage=='unknown':
                    update_row(args['payloads'],'games.jsonl',binding['previous_journal_game_id'],
                        lambda row:row.update(known_start=True))
                elif damage=='window':args['window']['close_unix_ns']+=1
                elif damage=='slot':binding['slot']=4097
                else:args['payloads']['games.jsonl']=b'{"journal_game_id":"x","journal_game_id":"y"}\n'
                with self.assertRaises(ValueError):audit.review(**args)


if __name__=='__main__':unittest.main(verbosity=2)
