"""Prospective CPU regressions; never review or rescue the failed campaign."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

H = Path(__file__).resolve().parent
G = H.parent.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class StartConsistencyTests(unittest.TestCase):
    def original_fixture(self):
        return copy.deepcopy(self.fixture)

    def inputs(self, diagnostic):
        def sample(x):
            return None if x is None else tuple(x[k] for k in (
                'raw_score', 'raw_wave', 'player_alive', 'done', 'start_pressed',
                'lives', 'accepted_frames_before'))
        b = diagnostic['classifier_previous']
        return (sample(diagnostic['previous_accepted_wire']), sample(diagnostic['current_wire']),
                b['raw_score'], b['raw_wave'], b['player_alive'],
                diagnostic['last_start_frame_before'], diagnostic['last_start_frame_after'],
                diagnostic['recent_start'], diagnostic['classifier_new_game'], diagnostic['classifier_verdict'])

    def simulation(self, module, *, late=False, wave=35, reset_finish=False, policy=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        now = [1000.0]
        j = module.GameJournal(temporary.name, clock=lambda: now[0],
                               completion_policy=policy or self.new_terminal.MODE)
        j.run_id = 'deterministic-fixture'
        cs = dict(game_uid=160, client_slot=4119, eval_only=True)
        context = lambda: dict(experiment='fixture', measurement_active=True,
                               measurement_generation=1, epsilon=0., expert_ratio=0., difficulty=5)
        d = copy.deepcopy(self.fixture['successor_game160']['start_context']['game_boundary_diagnostics'])
        def observe(diagnostic, *, reset=False, reserves=10):
            now[0] += 1
            w = diagnostic['current_wire']
            f = SimpleNamespace(game_score=w['raw_score'], level_number=w['raw_wave'],
                player_alive=w['player_alive'], done=w['done'], start_pressed=w['start_pressed'],
                lives=w['lives'], num_lasers=reserves)
            j.observe(23, f, cs, new_game=reset, context=context,
                      boundary_inputs=self.inputs(diagnostic))
        if late:
            start = copy.deepcopy(d)
            start['current_wire'].update(raw_score=0, raw_wave=0, player_alive=False)
            observe(start, reset=True, reserves=0)
        d['current_wire']['raw_wave'] = wave
        observe(d, reset=not late)
        active = copy.deepcopy(j.active[23])
        before = (Path(temporary.name)/'measurement_starts.jsonl').read_bytes()
        cohort = j.cohort_status('fixture', 1000., now[0])
        if reset_finish:
            next_start = copy.deepcopy(d)
            next_start['previous_accepted_wire'] = copy.deepcopy(d['current_wire'])
            next_start['current_wire'].update(raw_score=0, raw_wave=1, player_alive=False,
                accepted_frames_before=d['current_wire']['accepted_frames_before']+1)
            next_start['classifier_previous'] = dict(raw_score=d['current_wire']['raw_score'],
                raw_wave=wave, player_alive=True)
            cs['game_uid'] = 170
            observe(next_start, reset=True, reserves=2)
        else:
            j.disconnect(23, context)
        games = [json.loads(l) for l in (Path(temporary.name)/'games.jsonl').read_text().splitlines()]
        starts = [json.loads(l) for l in (Path(temporary.name)/'measurement_starts.jsonl').read_text().splitlines()]
        return games, starts, active, before, cohort

    def test_original_failure_remains_invalid_in_both_validators(self):
        f = self.original_fixture()
        for validator in (self.old_terminal, self.new_terminal):
            with self.assertRaisesRegex(ValueError, 'next start was not retained'):
                validator.collect_successors([f['game149']], [f['game149'], f['successor_game160']],
                    [dict(validator.start_record(f['game149'])), f['successor_start160']])
        self.assertIs(self.original_receipt['valid'], False)
        self.assertEqual(self.original_receipt['reason'], 'receipt_validation_failed')

    def test_real_live_wave35_boundary_is_rejected_even_without_start_mismatch(self):
        f = self.original_fixture()
        # Diagnose the old semantic gap using its pure predicate only. Do not
        # edit a journal, rebuild a receipt, or repeat scientific review.
        successor = self.old_terminal.start_record(f['successor_start160'])
        self.old_terminal.validate_terminal(f['game149'], successor)
        with self.assertRaisesRegex(ValueError, 'live successor starts above wave1'):
            self.new_terminal.validate_terminal(f['game149'], successor)

    def test_immediate_first_play_diagnostic_does_not_mutate_persisted_start(self):
        games, starts, active, before, cohort = self.simulation(self.new_journal)
        self.assertEqual(self.new_terminal.start_record(games[0]), self.new_terminal.start_record(starts[0]))
        self.assertNotIn('first_play_not_wave_1_inputs', games[0]['start_context'])
        self.assertEqual(games[0]['first_play_not_wave_1_inputs'],
                         self.fixture['successor_game160']['start_context']['first_play_not_wave_1_inputs'])
        self.assertEqual(active['start'], starts[0]['context'])
        self.assertEqual(before, (json.dumps(starts[0], separators=(',', ':'))+'\n').encode())
        self.assertEqual((cohort['started'],cohort['abandoned'],cohort['count']), (1,1,0))

    def test_later_first_play_diagnostic_preserves_start_and_abandonment(self):
        games, starts, active, before, cohort = self.simulation(self.new_journal, late=True)
        self.assertEqual(self.new_terminal.start_record(games[0]), self.new_terminal.start_record(starts[0]))
        self.assertEqual(games[0]['first_play_level'],35)
        self.assertIs(games[0]['eligible'],False)
        self.assertEqual(games[0]['excluded_reason'],'measurement_start_not_wave_1')
        self.assertIs(cohort['valid'],False)

    def test_diagnostic_retained_on_completed_rejected_game(self):
        games, starts, *_ = self.simulation(self.new_journal, reset_finish=True)
        self.assertTrue(games[0]['complete'])
        self.assertFalse(games[0]['eligible'])
        self.assertIn('first_play_not_wave_1_inputs',games[0])
        self.assertEqual(self.new_terminal.start_record(games[0]),self.new_terminal.start_record(starts[0]))

    def test_first_play_wave_one_has_identical_old_and_new_records(self):
        old = self.simulation(self.old_journal, wave=1, reset_finish=True)
        new = self.simulation(self.new_journal, wave=1, reset_finish=True)
        self.assertEqual(old, new)

    def test_legacy_eligibility_and_diagnostics_are_preserved(self):
        old = self.simulation(self.old_journal, policy='wire_lives_v1')
        new = self.simulation(self.new_journal, policy='wire_lives_v1')
        old_games, old_starts, old_active, _, old_cohort = copy.deepcopy(old)
        for row in old_games:
            row['first_play_not_wave_1_inputs']=row['start_context'].pop('first_play_not_wave_1_inputs')
        old_active['first_play_not_wave_1_inputs']=old_active['start'].pop('first_play_not_wave_1_inputs')
        self.assertEqual(old_games,new[0]);self.assertEqual(old_starts,new[1])
        self.assertEqual(old_active,new[2]);self.assertEqual(old_cohort,new[4])

    def test_inactive_reset_then_observed_wrong_wave_cannot_confirm_prior_game(self):
        games, starts = self.existing_terminal_tests.TerminalEvidenceTests().make()
        # This fixture already has an inactive wave1 successor. An observed
        # contradictory first playable wave must invalidate terminal evidence.
        games[-1]['first_play_level']=35
        with self.assertRaisesRegex(ValueError,'first playable wave contradicts'):
            self.new_terminal.collect_successors(games[:1],games,starts)

    def test_inactive_successor_without_play_remains_valid_evidence(self):
        games, starts = self.existing_terminal_tests.TerminalEvidenceTests().make()
        self.assertIsNone(games[-1]['first_play_level'])
        self.assertEqual(len(self.new_terminal.collect_successors(games[:1],games,starts)),1)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--job',required=True)
    parser.add_argument('--job-sha256',required=True)
    args=parser.parse_args()
    jobraw=Path(args.job).read_bytes()
    assert hashlib.sha256(jobraw).hexdigest()==args.job_sha256
    job=json.loads(jobraw)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    reader=load('start_consistency_reader',G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    for p in job['inputs']:reader.read_pin(p,as_json=False)
    assert reader.pin(Path(__file__)) in job['inputs']
    oldroot=H/'profile04/Robotron';newroot=H/'profile05/Robotron'
    oldj=load('start_consistency_old_journal',oldroot/'Scripts/dqn/game_journal.py')
    newj=load('start_consistency_new_journal',newroot/'Scripts/dqn/game_journal.py')
    oldt=load('start_consistency_old_terminal',oldroot/'tools/confirmed_terminal_evidence.py')
    newt=load('start_consistency_new_terminal',newroot/'tools/confirmed_terminal_evidence.py')
    # Reuse exact existing semantic/byte tests with the actual new modules.
    sys.modules['game_journal_candidate_reviewed3']=newj
    sys.modules['confirmed_terminal_evidence_reviewed4']=newt
    existing=load('start_consistency_existing_terminals',G/'tools/confirmed_game_boundary_proposal/test_terminal_evidence_reviewed4.py')
    sys.path.insert(0,str(newroot/'Scripts'))
    journal_tests=__import__('dqn.test_game_journal',fromlist=['GameJournalTests'])
    assert journal_tests.GameJournal is newj.GameJournal or Path(sys.modules[journal_tests.GameJournal.__module__].__file__).resolve()==newroot/'Scripts/dqn/game_journal.py'
    cls=StartConsistencyTests
    cls.old_journal=oldj;cls.new_journal=newj;cls.old_terminal=oldt;cls.new_terminal=newt
    cls.fixture=reader.read_pin(job['fixture']);cls.original_receipt=reader.read_pin(job['original_receipt'])
    cls.existing_terminal_tests=existing
    loader=unittest.defaultTestLoader
    suite=unittest.TestSuite([loader.loadTestsFromTestCase(journal_tests.GameJournalTests),
        loader.loadTestsFromTestCase(existing.TerminalEvidenceTests),
        unittest.TestSuite(existing.OriginalByteTests(n) for n in existing.OriginalByteTests.__dict__ if n.startswith('test_')),
        loader.loadTestsFromTestCase(cls)])
    names=[]
    def flatten(s):
        for test in s:
            if isinstance(test,unittest.TestSuite):flatten(test)
            else:names.append(test.id())
    flatten(suite)
    assert len(names)==job['expected_tests'] and len(set(names))==len(names)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    for p in job['inputs']:reader.read_pin(p,as_json=False)
    assert not any(n in sys.modules for n in ['torch','numpy'])
    report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,selected_tests=names,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        CUDA_hidden=True,numerical_runtime_imported=False,actual_quality_run=False,
        original_scientific_review_retried=False,policy_published=False,source_inputs_unchanged=True,
        original_failed_receipt_remains_invalid=True)
    print(json.dumps(report),flush=True)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
