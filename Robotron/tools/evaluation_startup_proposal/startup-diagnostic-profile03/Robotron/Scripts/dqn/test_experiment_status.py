"""Read-only campaign UI evidence, independent of Torch, emulators, and network."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .experiment_status import ExperimentStatusReader


class ExperimentStatusTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "Robotron"
        self.campaign = self.root / "logs/campaign"
        self.state_path = self.root / "logs/state.json"
        self.now = 1000.0
        self.monotonic = 0.0
        self.write(self.state_path, {"active_quality_job": {
            "directory": "Robotron/logs/campaign"}})
        self.plan = {"checkpoints": {
            "reference": {"source": "/private/models/fixed123M.pt"},
            "candidate": {"source": "/private/models/new456M.pt"}}, "legs": [
                self.spec(1, "reference"), self.spec(2, "candidate"),
                self.spec(3, "reference"), self.spec(4, "candidate")]}
        self.status = {"state": "running", "updated_unix_s": 995,
                       "current_leg": 1, "outcome": "incomplete",
                       "legs": [{"index": 1, "role": "reference", "state": "running"}]}
        self.data = {"phase": "collecting", "count": 23, "started": 39,
                     "pending": 16, "mean": 200000, "median": 190000,
                     "se": 12000, "valid": None, "complete": False,
                     "start_ts": 900, "close_ts": 2100,
                     "rows": [{"game_uid": "private-game", "score": 123}],
                     "job": {"command": "private command", "directory": "/private"}}
        self.write(self.campaign / "plan.json", self.plan)
        self.write(self.campaign / "status.json", self.status)
        self.write(self.campaign / "01-reference/status.json", self.data)
        self.reader = ExperimentStatusReader(
            self.root, self.state_path, clock=lambda: self.now,
            monotonic=lambda: self.monotonic)

    def spec(self, index, role):
        directory = f"{index:02d}-{role}"
        return {"index": index, "role": role,
                "job": {"label": role + "-cohort"},
                "evaluator_status_path": f"{directory}/status.json",
                "receipt_path": f"{directory}/receipt.json"}

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def refresh(self):
        self.monotonic += 2.1
        return self.reader.snapshot()

    def test_collecting_reports_full_game_counts_and_no_private_payloads(self):
        result = self.reader.snapshot()
        self.assertTrue(result["available"])
        self.assertFalse(result["stale"])
        self.assertEqual(result["comparison"], "123M vs 456M")
        self.assertEqual(result["total_legs"], 4)
        self.assertEqual(result["legs"][0]["phase"], "collecting")
        self.assertEqual(result["legs"][0]["count"], 23)
        self.assertEqual(result["legs"][0]["pending"], 16)
        self.assertIsNone(result["legs"][0]["valid"])
        serialized = json.dumps(result, allow_nan=False)
        for private in ("private", "rows", "game_uid", "command", "receipt_path"):
            self.assertNotIn(private, serialized)

    def test_draining_still_shows_unfinished_admitted_games(self):
        self.data.update(phase="draining", pending=1, started=125, count=124)
        self.write(self.campaign / "01-reference/status.json", self.data)
        leg = self.reader.snapshot()["legs"][0]
        self.assertEqual((leg["phase"], leg["count"], leg["pending"]), ("draining", 124, 1))
        self.assertFalse(leg["complete"])
        self.assertEqual(leg["admission_close_unix_s"], 2100)

    def test_finished_receipt_overrides_status_and_preserves_invalid_reason(self):
        self.status.update(state="finished", outcome="invalid", reason="incomplete cohort")
        self.status["legs"][0]["state"] = "finished"
        self.write(self.campaign / "status.json", self.status)
        self.write(self.campaign / "01-reference/receipt.json", dict(
            self.data, phase="finished", count=125, pending=0, complete=True,
            valid=False, reason="source identity changed"))
        self.now += 10000
        result = self.reader.snapshot()
        self.assertFalse(result["stale"])
        self.assertEqual(result["outcome"], "invalid")
        self.assertEqual(result["legs"][0]["count"], 125)
        self.assertFalse(result["legs"][0]["valid"])
        self.assertEqual(result["legs"][0]["reason"], "source identity changed")

    def test_running_status_is_stale_even_if_other_data_is_available(self):
        self.now = 1030
        result = self.reader.snapshot()
        self.assertTrue(result["available"])
        self.assertTrue(result["stale"])
        self.assertEqual(result["age_s"], 35)

    def test_corrupt_transient_read_keeps_previous_data_but_marks_error(self):
        first = self.reader.snapshot()
        (self.campaign / "status.json").write_text('{"state":')
        result = self.refresh()
        self.assertEqual(result["legs"], first["legs"])
        self.assertTrue(result["stale"])
        self.assertIn("read_error", result)
        self.assertNotIn(str(self.root), result["read_error"])
        self.write(self.campaign / "status.json", self.status)
        self.assertNotIn("read_error", self.refresh())

    def test_disappearing_live_child_keeps_counts_and_marks_stale(self):
        self.reader.snapshot()
        (self.campaign / "01-reference/status.json").unlink()
        result = self.refresh()
        self.assertEqual(result["legs"][0]["pending"], 16)
        self.assertTrue(result["stale"])
        self.assertIn("read_error", result)

    def test_cache_is_detached_and_reads_at_most_once_every_two_seconds(self):
        with patch.object(self.reader, "_load", wraps=self.reader._load) as read:
            result = self.reader.snapshot()
            result["legs"][0]["count"] = 999
            self.monotonic = 1.9
            self.assertEqual(self.reader.snapshot()["legs"][0]["count"], 23)
            self.assertEqual(read.call_count, 1)
            self.monotonic = 2.0
            self.reader.snapshot()
            self.assertEqual(read.call_count, 2)

    def test_campaign_and_child_path_escape_are_rejected(self):
        self.write(self.state_path, {"active_quality_job": {"directory": "../outside"}})
        result = self.reader.snapshot()
        self.assertFalse(result["available"])
        self.assertTrue(result["stale"])
        self.write(self.state_path, {"active_quality_job": {"directory": str(self.campaign)}})
        self.status["legs"][0]["evaluator_status_path"] = str(self.state_path)
        self.write(self.campaign / "status.json", self.status)
        self.assertIn("read_error", self.refresh())

    def test_child_symlink_escape_and_oversized_files_are_rejected(self):
        child = self.campaign / "01-reference/status.json"
        child.unlink()
        child.symlink_to(self.state_path)
        self.assertIn("read_error", self.reader.snapshot())
        child.unlink()
        child.write_bytes(b" " * (1024 * 1024 + 1))
        self.assertIn("read_error", self.refresh())

    def test_at_most_four_declared_legs_and_json_finite_numbers(self):
        self.plan["legs"].append(self.spec(5, "candidate"))
        self.write(self.campaign / "plan.json", self.plan)
        self.data["mean"] = float("nan")
        self.write(self.campaign / "01-reference/status.json", self.data)
        result = self.reader.snapshot()
        self.assertEqual(len(result["legs"]), 4)
        self.assertIsNone(result["legs"][0]["mean"])
        json.dumps(result, allow_nan=False)

    def test_absent_campaign_is_unavailable_and_startup_status_is_optional(self):
        self.write(self.state_path, {})
        self.assertFalse(self.reader.snapshot()["available"])
        self.write(self.state_path, {"active_quality_job": {"directory": str(self.campaign)}})
        (self.campaign / "01-reference/status.json").unlink()
        result = self.refresh()
        self.assertEqual(result["legs"][0]["phase"], "running")
        self.assertNotIn("read_error", result)


if __name__ == "__main__":
    unittest.main()
