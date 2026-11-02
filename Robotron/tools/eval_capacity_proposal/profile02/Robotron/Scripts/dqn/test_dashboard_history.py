"""Dashboard history stays bounded while preserving chart fields and horizon."""

from collections import deque
import copy
import json
import unittest

from .dashboard_history import bounded_history, compact_history_row


class DashboardHistoryTests(unittest.TestCase):
    def test_live_client_details_and_raw_diagnostics_are_not_retained(self):
        clients = [{"client_id": index, "score": 1000, "status": "playing"}
                   for index in range(192)]
        snapshot = {
            "ts": 123.5, "fps": 8700.0, "training_steps": 100,
            "reward_total": 2.5, "gpu0_util": 97, "q_min": None,
            "training_enabled": True, "managed_experiment": "quality-check",
            "client_rows": clients, "host_pipeline": {"histogram": [1] * 50},
            "gpus": [{"util": 97}], "bank_persistence": {"writes": 3},
            "game_settings": {"difficulty": 5}, "preview_pixels": b"pixels",
            "tuple_data": (1, 2),
        }
        before = copy.deepcopy(snapshot)
        result = compact_history_row(snapshot)
        self.assertEqual(result, {
            "ts": 123.5, "fps": 8700.0, "training_steps": 100,
            "reward_total": 2.5, "gpu0_util": 97, "q_min": None,
            "training_enabled": True, "managed_experiment": "quality-check",
        })
        self.assertEqual(snapshot, before)
        self.assertIsNot(result, snapshot)
        clients[0]["score"] = -1
        self.assertNotIn("client_rows", result)

    def test_existing_uncompacted_history_is_compacted_in_response(self):
        rows = deque([{"ts": index, "fps": 10, "client_rows": [{"id": index}]}
                      for index in range(40_000)], maxlen=40_000)
        result = bounded_history(rows)
        self.assertLessEqual(len(result), 2400)
        self.assertEqual((result[0]["ts"], result[-1]["ts"]), (0, 39_999))
        self.assertTrue(all(set(row) == {"ts", "fps"} for row in result))
        self.assertEqual(len(rows), 40_000)
        self.assertIn("client_rows", rows[0])

    def test_even_time_sampling_handles_uneven_sample_density(self):
        timestamps = [0, .1, .2, .3, 10, 20, 30, 40]
        result = bounded_history([{"ts": ts} for ts in timestamps], limit=5)
        self.assertEqual([row["ts"] for row in result], [0, 10, 20, 30, 40])

    def test_large_gaps_and_duplicate_timestamps_remain_bounded(self):
        rows = [{"ts": ts} for ts in [0] * 100 + [1000] * 100]
        result = bounded_history(rows, limit=20)
        self.assertLessEqual(len(result), 20)
        self.assertEqual(result[0]["ts"], 0)
        self.assertEqual(result[-1]["ts"], 1000)

    def test_invalid_or_reset_times_fall_back_to_ordered_indices(self):
        for times in ([1, 2, 0, 1, 2], [None] * 5, [float("nan")] * 5):
            rows = [{"ts": ts, "index": index} for index, ts in enumerate(times)]
            result = bounded_history(rows, limit=3)
            self.assertEqual([row["index"] for row in result], [0, 2, 4])

    def test_small_history_empty_and_one_point_limits(self):
        self.assertEqual(bounded_history([]), [])
        rows = [{"ts": 1}, {"ts": 2}, {"ts": 3}]
        self.assertEqual(bounded_history(rows), rows)
        self.assertIsNot(bounded_history(rows)[0], rows[0])
        self.assertEqual(bounded_history(rows, limit=1), [{"ts": 3}])
        self.assertEqual(bounded_history(rows, limit=2), [{"ts": 1}, {"ts": 3}])

    def test_bad_limits_fail_explicitly(self):
        for limit in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                bounded_history([], limit=limit)

    def test_compaction_removes_payload_growth_with_number_of_clients(self):
        scalar_fields = {"ts": 1, "fps": 8700, "loss": .2, "gpu0_util": 97}
        small = {**scalar_fields, "client_rows": [{"id": 1}]}
        large = {**scalar_fields, "client_rows": [{"id": i, "score": i * 100}
                                                   for i in range(192)]}
        self.assertEqual(json.dumps(compact_history_row(small)),
                         json.dumps(compact_history_row(large)))
        self.assertGreater(len(json.dumps(large)), len(json.dumps(compact_history_row(large))) * 10)


if __name__ == "__main__":
    unittest.main()
