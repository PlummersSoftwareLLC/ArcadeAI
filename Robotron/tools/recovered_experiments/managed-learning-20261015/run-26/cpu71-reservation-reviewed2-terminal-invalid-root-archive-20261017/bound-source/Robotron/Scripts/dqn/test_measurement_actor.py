"""Frozen actor isolation: no replay bridges, learner clocks, or legacy eval writes."""
from collections import deque
import struct
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from . import socket_server as server_module
from .nstep_buffer import NStepReplayBuffer


def fake_metrics(active=True, generation=1):
    state = SimpleNamespace(
        lock=threading.Lock(), measurement_active=active, measurement_generation=generation,
        measurement_frame_count=0, frame_count=0, learner_frame_count=0,
        ratchet_frozen=False, override_expert=False, override_epsilon=False,
        measurement_label="frozen-A", managed_experiment="training-label", epsilon=.7,
        expert_ratio=.4, total_training_steps=0,
    )
    for name in ("update_epsilon", "update_expert_ratio", "update_learner_frame_count",
                 "ratchet_note_eval_start", "ratchet_note_eval_episode", "ratchet_note_eval_abandoned",
                 "note_game_score", "note_eval_rate", "note_eval_wave_clear", "note_training_terminal",
                 "add_eval_episode_reward", "add_episode_reward", "increment_total_controls",
                 "add_inference_time"):
        setattr(state, name, Mock())
    state.get_effective_epsilon = Mock(return_value=.7)
    state.get_expert_ratio = Mock(return_value=.4)
    state.update_frame_count = Mock(side_effect=lambda delta: setattr(
        state, "frame_count", state.frame_count+delta))
    return state


class MeasurementActorTests(unittest.TestCase):
    def test_low_score_carry_tear_is_continuous_play_instead_of_fresh_game(self):
        frame = SimpleNamespace(game_score=11300, level_number=3, player_alive=True,
                                done=False, start_pressed=False)
        client = dict(player_alive=True)
        self.assertTrue(server_module._continuous_play_score_dip(frame, client, 11350, 3, False))
        # Even an old autoboot pulse during a prior life is not a reset at a
        # positive score in the middle of uninterrupted, same-wave live play.
        self.assertTrue(server_module._continuous_play_score_dip(frame, client, 11350, 3, True))
        frame.game_score = 0
        self.assertTrue(server_module._continuous_play_score_dip(frame, client, 11350, 3, False))
        self.assertFalse(server_module._continuous_play_score_dip(frame, client, 11350, 3, True))

    def test_real_start_edges_and_wave_reset_are_not_hidden_by_carry_guard(self):
        frame = SimpleNamespace(game_score=0, level_number=1, player_alive=True,
                                done=False, start_pressed=False)
        client = dict(player_alive=True)
        self.assertFalse(server_module._continuous_play_score_dip(frame, client, 20000, 3, False))
        self.assertFalse(server_module._continuous_play_score_dip(
            frame, dict(player_alive=False), 20000, 1, False))
        frame.start_pressed = True
        self.assertFalse(server_module._continuous_play_score_dip(frame, client, 20000, 1, False))
        frame.start_pressed = False
        frame.player_alive = False
        self.assertFalse(server_module._continuous_play_score_dip(frame, client, 20000, 1, False))

    def test_all_actors_are_greedy_and_measurement_source_is_never_replayed(self):
        state = fake_metrics()
        with patch.object(server_module, "metrics", state):
            for eval_only in (False, True):
                self.assertEqual(server_module.SocketServer._actor_controls(dict(eval_only=eval_only)),
                                 (0.0, 0.0, "measurement"))
            state.measurement_active = False
            self.assertFalse(server_module.SocketServer._replay_writable(
                dict(prev_action_source="measurement")))
            self.assertTrue(server_module.SocketServer._replay_writable(dict(prev_action_source="dqn")))

    def test_raw_measurement_frames_do_not_advance_schedules_or_manual_pulses(self):
        state = fake_metrics()
        published_debits = []
        def publish_raw_frames(delta):
            published_debits.append(state.measurement_frame_count)
            state.frame_count += delta
        state.update_frame_count.side_effect = publish_raw_frames
        with patch.object(server_module, "metrics", state):
            server_module.SocketServer._account_frame_batch(8, 8)
            self.assertEqual((state.frame_count, state.measurement_frame_count), (8, 8))
            state.update_epsilon.assert_not_called()
            state.update_expert_ratio.assert_not_called()
            state.measurement_active = False
            server_module.SocketServer._account_frame_batch(8, 3)
            self.assertEqual((state.frame_count, state.measurement_frame_count), (16, 11))
            state.update_epsilon.assert_called_once_with(frames_advanced=5)
            state.update_expert_ratio.assert_called_once()
            self.assertEqual(published_debits, [8, 11])

    def test_boundary_clears_pending_transitions_and_waits_for_fifo_ack_on_entry_and_exit(self):
        state = fake_metrics()
        server = server_module.SocketServer.__new__(server_module.SocketServer)
        server.client_lock = threading.Lock()
        server.game_journal = Mock()
        acknowledgments = [threading.Event(), threading.Event()]
        server.async_buffer = Mock(reset_client_async=Mock(side_effect=acknowledgments))
        nstep = NStepReplayBuffer(3, .99)
        nstep.add(np.zeros(2), 0, 1, np.ones(2), False)
        client = dict(client_slot=7, last_state=np.zeros(2), last_action=(1, 1),
                      prev_action_source="epsilon", frame_history=deque([np.zeros(2)]),
                      nstep=nstep, fire_hold_count=3, fire_hold_dir=4)
        server.client_states = {2: client}
        with patch.object(server_module, "metrics", state):
            self.assertFalse(server.measurement_boundary_status(1)["ready"])
            server._sync_measurement_boundary(2, client, 1000)
            self.assertIsNone(client["last_state"])
            self.assertIsNone(client["last_action"])
            self.assertEqual(len(nstep._deque), 0)
            self.assertEqual(list(client["frame_history"]), [])
            self.assertEqual(client["fire_hold_count"], 0)
            self.assertTrue(client["replay_episode_partial"])
            self.assertEqual(server.measurement_boundary_status(1)["replay_pending_client_ids"], [2])
            acknowledgments[0].set()
            self.assertTrue(server.measurement_boundary_status(1)["ready"])
            client["last_state"], client["last_action"] = np.ones(2), (2, 2)
            state.measurement_active, state.measurement_generation = False, 2
            server._sync_measurement_boundary(2, client, 1500)
            self.assertIsNone(client["last_state"])
            self.assertIsNone(client["last_action"])
            self.assertFalse(server.measurement_boundary_status(2)["ready"])
            acknowledgments[1].set()
            self.assertTrue(server.measurement_boundary_status(2)["ready"])
            self.assertFalse(server.measurement_boundary_status(2)["active"])
        self.assertEqual(server.async_buffer.reset_client_async.call_count, 2)

    def test_async_episode_reset_runs_after_prior_steps_and_before_new_steps(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def step(value):
            if value == "old-1":
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("test release timed out")
            calls.append(value)
            return len(calls)-1
        buffer = server_module.AsyncReplayBuffer(SimpleNamespace(step=step), batch_size=1)
        try:
            buffer.step_async("old-1", client_id=4)
            self.assertTrue(entered.wait(2))
            buffer.step_async("old-2", client_id=4)
            reset_ack = buffer.reset_client_async(4)
            buffer.step_async("new-1", client_id=4)
            barrier_ack = buffer.barrier_async()
            self.assertFalse(reset_ack.is_set())
            release.set()
            self.assertTrue(barrier_ack.wait(3))
            self.assertTrue(reset_ack.is_set())
            self.assertEqual(calls, ["old-1", "old-2", "new-1"])
            self.assertEqual(list(buffer._client_indices[4]), [2])
            self.assertEqual(list(buffer._episode_indices[4]), [2])
        finally:
            release.set()
            buffer.stop()

    def test_socket_loop_measurement_writes_no_replay_or_legacy_eval_for_any_actor(self):
        for legacy_eval in (False, True):
            with self.subTest(legacy_eval=legacy_eval):
                state = fake_metrics()
                server = server_module.SocketServer.__new__(server_module.SocketServer)
                server.agent = SimpleNamespace(act=Mock(return_value=(0, 0, True)), optimized_samples=123)
                server.async_buffer = Mock()
                server.inference_batcher = None
                server.game_journal = None
                server.metrics = state
                server.client_lock = threading.Lock()
                server.client_states, server.clients = {}, {0: object()}
                server._eval_override, server._unwrap_stash = {0: legacy_eval}, {}
                server._game_uid_seq = 0
                server.shutdown_event = threading.Event()
                server.running = True
                server._ensure_preview_client_selected_locked = Mock(return_value=(None, False))
                server._preview_enabled_for_client = Mock(return_value=False)
                server._hud_enabled_for_client = Mock(return_value=False)
                server._is_preview_client = Mock(return_value=False)
                server._clear_preview_cache = Mock()
                payload = struct.pack(">H", server_module.WIRE_PARAMS_COUNT)
                receive = [struct.pack(">H", 0)]
                frames = []
                # Include the live failure pattern: a small score dip while
                # continuously alive at wave3.  It must not mint another game
                # uid or feed a bogus final to the start-side cohort.
                for score, wave, done in ((0, 1, False), (100, 1, False),
                                          (11350, 3, False), (11300, 3, False),
                                          (13050, 3, False), (13050, 3, True)):
                    receive.extend([struct.pack(">I", len(payload)), payload])
                    frames.append(server_module.FrameData(
                        state=np.zeros(1), subjreward=0, objreward=0, done=done,
                        player_alive=not done, save_signal=False, start_pressed=False,
                        level_number=wave, game_score=score, num_lasers=0, lives=2 if done else 3))
                receive.append(ConnectionError("test EOF"))
                server._recv_exact = Mock(side_effect=receive)
                sock = Mock()
                with patch.object(server_module, "metrics", state), \
                     patch.object(server_module, "parse_frame_data", side_effect=frames), \
                     patch.object(server_module, "slice_model_state", return_value=np.zeros(2)), \
                     patch.object(server_module.threading, "Timer"):
                    server._init_client(0)
                    server.handle_client(sock, 0)
                self.assertEqual(state.measurement_frame_count, 6)
                self.assertEqual(state.frame_count, 6)
                self.assertEqual(server.agent.act.call_count, 5)
                self.assertEqual(server._unwrap_stash[0]["game_uid"], 1)
                self.assertEqual(frames[3].game_score, 11350)
                for call in server.agent.act.call_args_list:
                    self.assertEqual(call.args[1], 0.0)
                for name in ("update_epsilon", "update_expert_ratio", "update_learner_frame_count",
                             "note_eval_rate", "note_eval_wave_clear", "note_training_terminal",
                             "add_eval_episode_reward", "add_episode_reward", "note_game_score"):
                    getattr(state, name).assert_not_called()
                for name in ("step_async", "boost_pre_death", "boost_elite_episode"):
                    getattr(server.async_buffer, name).assert_not_called()
                for call in sock.sendall.call_args_list:
                    *_, advanced, wave, difficulty = struct.unpack(">bbBBBB", call.args[0])
                    self.assertEqual((advanced, wave), (0, 1))
                    self.assertTrue(difficulty & 0x80)


if __name__ == "__main__":
    unittest.main(verbosity=2)
