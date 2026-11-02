"""A full committed game, never a life loss, permits one-game actor exit."""
import json
from pathlib import Path
import struct
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from .game_journal import GameJournal
from .socket_server import SocketServer


class TrainingRoundJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1000.0
        self.cs = dict(client_slot=2, game_uid=1, eval_only=False,
                       journal_experiment="training")
        self.journal = GameJournal(self.temp.name, clock=lambda: self.now,
                                   retire_after_game=True)

    def observe(self, score=0, alive=True, done=False, lives=3, start=False,
                new_game=False, level=1):
        self.now += 1
        frame = SimpleNamespace(game_score=score, level_number=level,
                                player_alive=alive, done=done, lives=lives,
                                start_pressed=start)
        self.journal.observe(9, frame, self.cs, new_game=new_game,
                             context=lambda: dict(experiment="training"))

    def boot(self):
        self.observe(alive=False, level=0)
        self.observe(alive=False, start=True, level=0)
        self.observe()
        self.assertTrue(self.journal.active[9]["known_start"])

    def rows(self, name):
        path = Path(self.temp.name) / name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_estimated_zero_lives_does_not_retire_or_truncate_final_score(self):
        self.boot()
        self.observe(score=1000, alive=False, done=True, lives=0)
        self.observe(score=1200, lives=0)
        self.observe(score=5000, lives=0)
        self.assertIsNone(self.journal.retirement_for_client(9))
        self.assertFalse(any(row["complete"] for row in self.rows("games.jsonl")))
        self.cs["game_uid"] = 2
        self.observe(alive=False, new_game=True)
        row = self.journal.retirement_for_client(9)
        self.assertEqual(row["score"], 5000)
        self.assertTrue(row["eligible"])
        self.assertEqual(row["boundary_reason"], "score_reset")
        self.assertEqual(self.rows("completed_clients.jsonl"), [row])

    def test_alive_attract_frames_do_not_hide_observed_first_start(self):
        for _ in range(20):
            self.observe(alive=True, level=0)
        self.assertFalse(self.journal.active[9]["known_start"])
        self.observe(alive=False, start=True, level=0)
        self.observe(alive=True, level=1)
        self.assertTrue(self.journal.active[9]["known_start"])
        self.observe(score=4200)
        self.cs["game_uid"] = 2
        self.observe(alive=False, new_game=True)
        self.assertEqual(self.journal.retirement_for_client(9)["score"], 4200)

    def test_zero_score_requires_restart_pulse_and_alive_edge(self):
        self.boot()
        for life in range(3):
            self.observe(alive=False, done=True, lives=2-life)
            if life < 2:
                self.observe(lives=2-life)
        self.assertIsNone(self.journal.retirement_for_client(9))
        self.observe(alive=False, start=True, lives=0)
        self.assertIsNone(self.journal.retirement_for_client(9))
        self.observe(alive=True, lives=0)
        row = self.journal.retirement_for_client(9)
        self.assertEqual(row["score"], 0)
        self.assertEqual(row["boundary_reason"], "zero_score_restart")

    def test_attachment_or_disconnect_is_not_a_full_game(self):
        self.observe(score=7000, level=7)
        self.observe(score=8000, level=8)
        self.cs["game_uid"] = 2
        self.observe(alive=False, new_game=True)
        self.assertIsNone(self.journal.retirement_for_client(9))
        self.journal.disconnect(9, lambda: dict(experiment="training"))
        self.assertIsNone(self.journal.retirement_for_client(9))

    def test_only_first_full_game_has_a_retirement_receipt(self):
        self.boot()
        self.observe(score=200)
        self.cs["game_uid"] = 2
        self.observe(alive=False, new_game=True)
        original = self.journal.retirement_for_client(9)
        self.observe(score=300)
        self.cs["game_uid"] = 3
        self.observe(alive=False, new_game=True)
        self.assertEqual(self.journal.retirement_for_client(9), original)
        self.assertEqual(len(self.rows("completed_clients.jsonl")), 1)

    def test_failed_receipt_write_never_allows_exit(self):
        self.boot()
        self.observe(score=200)
        write = self.journal._write
        def fail_receipt(path, row):
            if path == self.journal.retirements_path:
                raise OSError("disk write failed")
            return write(path, row)
        self.cs["game_uid"] = 2
        with patch.object(self.journal, "_write", side_effect=fail_receipt):
            with self.assertRaises(OSError):
                self.observe(alive=False, new_game=True)
        self.assertIsNone(self.journal.retirement_for_client(9))
        self.assertFalse(self.journal.active[9]["finished"])

    def test_reused_connection_does_not_inherit_previous_round_exit(self):
        self.boot()
        self.observe(score=200)
        self.cs["game_uid"] = 2
        self.observe(alive=False, new_game=True)
        self.assertIsNotNone(self.journal.retirement_for_client(9))
        self.journal.disconnect(9, lambda: dict(experiment="training"))
        self.assertIsNone(self.journal.retirement_for_client(9))
        self.boot()
        self.assertIsNone(self.journal.retirement_for_client(9))
        self.assertEqual(len(self.rows("completed_clients.jsonl")), 1)

    def test_score_and_receipt_are_fsynced_before_exit_is_available(self):
        self.boot()
        self.observe(score=200)
        self.cs["game_uid"] = 2
        from . import game_journal
        fsync = game_journal.os.fsync
        seen = []
        def record(fd):
            self.assertIsNone(self.journal.retirements.get(9))
            seen.append(fd)
            return fsync(fd)
        with patch.object(game_journal.os, "fsync", side_effect=record):
            self.observe(alive=False, new_game=True)
        self.assertEqual(len(seen), 4)  # score+directory, receipt+directory
        self.assertIsNotNone(self.journal.retirement_for_client(9))


class TrainingRoundWireAndPreviewTests(unittest.TestCase):
    def server(self):
        server = SocketServer.__new__(SocketServer)
        server.client_lock = threading.RLock()
        server.client_states = {cid: dict(preview_capable=True, proto_v2=True)
                                for cid in range(192)}
        server.preview_cid = 7
        server.preview_disabled = False
        server.metrics = SimpleNamespace(lock=threading.Lock(), web_client_count=1,
                                         preview_capture_enabled=True, hud_enabled=False)
        server._clear_preview_cache = lambda: None
        server._is_eval_client = lambda cid: True
        return server

    def test_exit_bit_is_separate_from_preview_and_hud(self):
        server = self.server()
        server.client_states[7]["retire_after_game"] = True
        response = server._pack_action(-1, -1, 3, cid=7,
                                       preview_enabled=True, hud_enabled=True)
        self.assertEqual(len(response), 6)
        self.assertEqual(struct.unpack(">bbBBBB", response)[2], 0x20 | 0x40 | 0x80 | 3)
        ordinary = server._pack_action(-1, -1, 3, cid=8)
        self.assertEqual(ordinary[2] & 0x20, 0)

    def test_only_selected_of_192_clients_gets_preview_request(self):
        server = self.server()
        self.assertEqual([cid for cid in range(192)
                          if server._preview_flags_for_client(cid)[0]], [7])
        server.preview_cid = 122
        self.assertEqual([cid for cid in range(192)
                          if server._preview_flags_for_client(cid)[0]], [122])

    def test_no_viewer_means_no_client_captures_preview(self):
        server = self.server()
        server.metrics.web_client_count = 0
        self.assertFalse(any(server._preview_flags_for_client(cid)[0] for cid in range(192)))


if __name__ == "__main__":
    unittest.main()
