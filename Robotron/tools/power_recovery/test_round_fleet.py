import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from .round_fleet import JournalTail, RoundFleet, confirmed_result, should_spawn, stop_owned


def result(slot, started):
    return dict(client_slot=slot, complete=True, eligible=True, known_start=True,
                boundary_reason="score_reset", score=slot, start_unix_s=started,
                journal_game_id="game-" + str(slot), max_level=1, duration_s=1)


class RoundFleetTests(unittest.TestCase):
    def test_191_completed_slots_are_not_respawned_while_last_slot_runs(self):
        results = {slot: result(slot, 100) for slot in range(191)}
        self.assertEqual([slot for slot in range(192) if should_spawn(slot, {}, results)], [191])
        results[191] = result(191, 100)
        self.assertFalse(any(should_spawn(slot, {}, results) for slot in range(192)))

    def test_partial_journal_line_waits_and_replacement_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_bytes(b"")
            tail = JournalTail(path)
            path.write_bytes(b'{"score":')
            self.assertEqual(tail.poll(), [])
            with path.open("ab") as stream:
                stream.write(b'0}\n')
            self.assertEqual(tail.poll(), [dict(score=0)])
            self.assertEqual(tail.poll(), [])
            path.write_bytes(b"")
            with self.assertRaises(RuntimeError):
                tail.poll()

    def test_unconfirmed_partial_foreign_and_old_games_cannot_retire_slots(self):
        row = result(0, 100)
        self.assertTrue(confirmed_result(row, set(range(192)), 100))
        for mutation in [dict(complete=False), dict(eligible=False), dict(known_start=False),
                         dict(boundary_reason="wire_lives_exhausted"), dict(score=-1),
                         dict(score=True), dict(client_slot=192), dict(start_unix_s=99)]:
            self.assertFalse(confirmed_result(dict(row, **mutation), set(range(192)), 100))

    def test_real_round_loop_waits_for_last_actor_and_records_all192_once(self):
        class Child:
            def __init__(self, slot):
                self.pid = 100000 + slot
                self.done = slot < 191
            def poll(self):
                return 0 if self.done else None
            def wait(self, timeout=None):
                return 0
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roles = dict(slot_eval={str(slot): False for slot in range(192)})
            fleet = RoundFleet(roles, root / "journal.jsonl", root / "output")
            children = {slot: Child(slot) for slot in range(192)}
            calls = []
            def spawn(slot, *_):
                calls.append(slot)
                return dict(process=children[slot], started_unix_s=0, frozen=False)
            class Tail:
                count = 0
                def poll(self):
                    self.count += 1
                    if self.count == 1:
                        return [result(slot, time.time()+1) for slot in range(191)]
                    children[191].done = True
                    return [result(191, time.time()+1)]
            fleet.journal = Tail()
            with patch.object(fleet, "spawn", side_effect=spawn), patch("time.sleep"):
                self.assertTrue(fleet.run_round(1))
            self.assertEqual(calls, list(range(192)))
            final = json.loads((root / "output/round-000001/summary.json").read_text())
            self.assertEqual(final["completed"], 192)
            self.assertEqual(final["retired"], 192)
            self.assertEqual(final["active"], 0)
            self.assertFalse(final["quality_qualified"])
            self.assertEqual(len(list((root / "output/round-000001").glob("slot-*-result.json"))), 192)

    def test_owned_cleanup_reaps_child_that_ignores_graceful_signal(self):
        child = subprocess.Popen([sys.executable, "-c",
            "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print('ready',flush=True);time.sleep(30)"],
            stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: child.kill() if child.poll() is None else None)
        self.assertEqual(child.stdout.readline().strip(), "ready")
        stop_owned({0: dict(process=child)})
        self.assertIsNotNone(child.poll())
        child.stdout.close()


if __name__ == "__main__":
    unittest.main()
