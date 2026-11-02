"""Primitive-only regression proof; full-handler validation remains separate."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SOURCE = ROOT / 'Scripts/dqn/socket_server.py'
SOURCE_SHA = '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408'


def helper(path):
    tree = ast.parse(path.read_bytes())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == '_continuous_play_score_dip')
    namespace = {'RL_CONFIG': SimpleNamespace(score_torn_read_tolerance=100_000)}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[function.name]


class LateWaveGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA
        cls.old = staticmethod(helper(SOURCE))
        cls.new = staticmethod(helper(Path(__file__).with_name('late_wave_guard.py')))

    def frame(self, **changes):
        data = dict(game_score=475, level_number=35, player_alive=True,
                    done=False, start_pressed=False, num_lasers=18)
        data.update(changes)
        return SimpleNamespace(**data)

    def test_original_captured_event_reproduces_the_missing_large_dip_guard(self):
        path = ROOT / 'logs/managed-learning-20261015/capacity32-confirmed1059-inflight-v1-original01-20261019/receipt.json'
        row = json.loads(path.read_bytes())['rows'][0]
        event = row['terminal_confirmation']
        self.assertEqual((event['previous_score'], event['next_score'], event['next_wave']),
                         (999975, 475, 35))
        self.assertEqual((event['previous_raw_reserves'], event['next_raw_reserves']), (18, 18))
        self.assertFalse(self.old(self.frame(), {'player_alive': True}, 999975, 35, False))
        self.assertTrue(self.new(self.frame(), {'player_alive': True}, 999975, 35, False))

    def test_restored_score_is_a_normal_500_point_increase(self):
        self.assertEqual(1000475 - 999975, 500)
        self.assertFalse(self.new(self.frame(game_score=1000475),
                                  {'player_alive': True}, 999975, 35, False))

    def test_larger_decimal_carry_tiers_remain_the_same_game(self):
        for previous, current in ((999975, 475), (1999975, 1000475),
                                  (9999975, 475), (19999975, 10000475)):
            with self.subTest(previous=previous, current=current):
                self.assertTrue(self.new(self.frame(game_score=current),
                                         {'player_alive': True}, previous, 35, False))

    def test_large_same_wave_live_drop_is_not_turned_into_a_new_game(self):
        self.assertTrue(self.new(self.frame(game_score=250000),
                                 {'player_alive': True}, 1500000, 35, False))

    def test_inactive_previous_player_remains_a_possible_real_reset(self):
        self.assertFalse(self.new(self.frame(), {'player_alive': False}, 999975, 35, False))

    def test_inactive_current_player_remains_a_possible_real_reset(self):
        self.assertFalse(self.new(self.frame(player_alive=False),
                                  {'player_alive': True}, 999975, 35, False))

    def test_done_frame_is_not_hidden(self):
        self.assertFalse(self.new(self.frame(done=True), {'player_alive': True}, 999975, 35, False))

    def test_restart_button_is_not_hidden(self):
        self.assertFalse(self.new(self.frame(start_pressed=True),
                                  {'player_alive': True}, 999975, 35, False))

    def test_wave_reset_is_not_hidden(self):
        self.assertFalse(self.new(self.frame(level_number=1),
                                  {'player_alive': True}, 999975, 35, False))

    def test_large_early_wave_drop_keeps_the_original_ambiguity_rule(self):
        self.assertFalse(self.new(self.frame(level_number=1),
                                  {'player_alive': True}, 999975, 1, False))

    def test_large_recent_restart_drop_is_not_hidden(self):
        self.assertFalse(self.new(self.frame(), {'player_alive': True}, 999975, 35, True))

    def test_existing_small_dip_domain_is_preserved(self):
        for wave in (0, 1, 2, 35):
            for recent in (False, True):
                for score in (0, 50, 10000):
                    frame = self.frame(level_number=wave, game_score=score)
                    with self.subTest(wave=wave, recent=recent, score=score):
                        self.assertEqual(self.new(frame, {'player_alive': True}, 20000, wave, recent),
                                         self.old(frame, {'player_alive': True}, 20000, wave, recent))

    def test_missing_previous_wave_is_not_continuity(self):
        self.assertFalse(self.new(self.frame(), {'player_alive': True}, 999975, None, False))

    def test_non_decreasing_score_is_not_a_dip(self):
        for score in (999975, 1000475):
            self.assertFalse(self.new(self.frame(game_score=score),
                                      {'player_alive': True}, 999975, 35, False))


if __name__ == '__main__':
    unittest.main()
