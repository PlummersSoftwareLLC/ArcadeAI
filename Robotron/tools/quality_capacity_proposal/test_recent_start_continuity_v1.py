"""Pure primitive regression tests; this cannot qualify a runtime or policy."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
H=G/'tools/quality_capacity_proposal'


def helper(path,config):
    node=next(n for n in ast.parse(path.read_bytes()).body
              if isinstance(n,ast.FunctionDef) and n.name=='_continuous_play_score_dip')
    ns={'RL_CONFIG':config}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
    return ns[node.name]


class Tests(unittest.TestCase):
    def setUp(self):
        self.config=SimpleNamespace(score_torn_read_tolerance=100000,lives_start=3,score_wrap_modulus=100000000)
        self.old=helper(H/'profile04/Robotron/Scripts/dqn/socket_server.py',self.config)
        self.new=helper(H/'recent_start_continuity_proposal_v1.py',self.config)

    def frame(self,**changes):
        d=dict(game_score=3000,level_number=35,player_alive=True,done=False,start_pressed=False,num_lasers=10)
        d.update(changes);return SimpleNamespace(**d)

    def client(self,**changes):
        d=dict(player_alive=True,num_lasers=10);d.update(changes);return d

    def test_actual_captured_recent_start_boundary_is_preserved_as_continuous_play(self):
        game=self.fixture['successor_game160'];d=game['start_context']['game_boundary_diagnostics']
        self.assertEqual((d['classifier_previous']['raw_score'],d['current_wire']['raw_score']),(999000,3000))
        self.assertEqual((game['start_frame']['raw_reserves'],self.fixture['game149']['terminal_confirmation']['previous_raw_reserves']),(10,10))
        self.assertTrue(d['recent_start'])
        self.assertFalse(self.old(self.frame(),self.client(),999000,35,True))
        self.assertTrue(self.new(self.frame(),self.client(),999000,35,True))

    def test_restored_carry_fits_original_jump_budget_after_monotone_baseline(self):
        # This proves only the existing scalar classifier branches. Whole
        # parser/handler/replay execution remains a separate mandatory test.
        baseline=999000
        self.assertTrue(self.new(self.frame(),self.client(),baseline,35,True))
        restored=1003000
        self.assertLessEqual(restored-baseline,250000)
        self.assertGreater(restored-3000,250000)
        self.assertFalse(self.new(self.frame(game_score=restored),self.client(),baseline,35,True))

    def test_current_inactive_player_does_not_hide_a_restart(self):
        self.assertFalse(self.new(self.frame(player_alive=False),self.client(),999000,35,True))

    def test_previous_inactive_player_does_not_hide_a_restart(self):
        self.assertFalse(self.new(self.frame(),self.client(player_alive=False),999000,35,True))

    def test_done_frame_does_not_hide_a_restart(self):
        self.assertFalse(self.new(self.frame(done=True),self.client(),999000,35,True))

    def test_current_start_pulse_remains_ambiguous(self):
        self.assertFalse(self.new(self.frame(start_pressed=True),self.client(),999000,35,True))

    def test_wave_change_and_wave_one_preserve_existing_rule(self):
        for current,previous in [(1,35),(1,1),(0,35),(36,35)]:
            self.assertFalse(self.new(self.frame(level_number=current),self.client(),999000,previous,True))

    def test_starting_and_exhausted_reserves_remain_ambiguous(self):
        for reserves in [0,1,2]:
            self.assertFalse(self.new(self.frame(num_lasers=reserves),self.client(num_lasers=reserves),999000,35,True))

    def test_changed_reserves_remain_ambiguous(self):
        for before,after in [(10,9),(9,10),(10,2),(0,10)]:
            self.assertFalse(self.new(self.frame(num_lasers=after),self.client(num_lasers=before),999000,35,True))

    def test_unknown_invalid_or_boolean_reserves_do_not_expand_domain(self):
        for reserves in [None,-1,255,256,True,10.0]:
            self.assertFalse(self.new(self.frame(num_lasers=reserves),self.client(num_lasers=reserves),999000,35,True))

    def test_missing_previous_reserves_do_not_expand_domain(self):
        self.assertFalse(self.new(self.frame(),{'player_alive':True},999000,35,True))

    def test_configured_starting_lives_set_the_banked_reserve_floor(self):
        self.config.lives_start=5
        self.assertFalse(self.new(self.frame(num_lasers=4),self.client(num_lasers=4),999000,35,True))
        self.assertTrue(self.new(self.frame(num_lasers=5),self.client(num_lasers=5),999000,35,True))

    def test_possible_100M_wrap_is_not_clamped_by_new_recent_start_case(self):
        self.assertFalse(self.new(self.frame(game_score=3000),self.client(),99999000,35,True))
        self.assertEqual(self.old(self.frame(),self.client(),99999000,35,True),
                         self.new(self.frame(),self.client(),99999000,35,True))

    def test_possible_configured_wrap_uses_existing_configured_modulus(self):
        self.config.score_wrap_modulus=1000000
        self.assertFalse(self.new(self.frame(),self.client(),999000,35,True))

    def test_original_small_dip_domain_is_unchanged(self):
        for wave in (0,1,2,35):
            for recent in (False,True):
                for score in (0,50,10000):
                    f=self.frame(game_score=score,level_number=wave)
                    self.assertEqual(self.old(f,self.client(),20000,wave,recent),
                                     self.new(f,self.client(),20000,wave,recent))

    def test_original_nonrecent_large_dip_domain_is_unchanged(self):
        for reserves in (None,0,2,10,255):
            f=self.frame(num_lasers=reserves)
            self.assertEqual(self.old(f,self.client(num_lasers=reserves),999000,35,False),
                             self.new(f,self.client(num_lasers=reserves),999000,35,False))

    def test_non_decreasing_scores_and_unknown_previous_wave_are_not_dips(self):
        for score in [999000,1003000]:
            self.assertFalse(self.new(self.frame(game_score=score),self.client(),999000,35,True))
        self.assertFalse(self.new(self.frame(),self.client(),999000,None,True))

    def test_original_failed_receipt_remains_invalid(self):
        self.assertFalse(self.receipt['valid'])
        self.assertEqual(self.receipt['reason'],'receipt_validation_failed')


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--job-sha256',required=True);a=p.parse_args()
    time.sleep(2)  # Keep the original CPU service birth observable.
    raw=Path(a.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.job_sha256;job=json.loads(raw)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    rp=G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    assert hashlib.sha256(rp.read_bytes()).hexdigest()=='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
    spec=importlib.util.spec_from_file_location('recent_start_test_reader',rp);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    for item in job['inputs']:r.read_pin(item,as_json=False)
    Tests.fixture=r.read_pin(job['fixture']);Tests.receipt=r.read_pin(job['original_receipt'])
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);assert suite.countTestCases()==18
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    for item in job['inputs']:r.read_pin(item,as_json=False)
    assert 'torch' not in sys.modules and 'numpy' not in sys.modules
    print(json.dumps(dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        CUDA_hidden=True,numerical_runtime_imported=False,scope='PURE_PRIMITIVE_ONLY',
        full_handler_validated=False,actual_wire_validated=False,source_selected_for_science=False,
        original_quality_remains_invalid=True,quality_qualified=False,learning_speed_gain_verified=False)),flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
