"""Identity/rollback tests; affinity syscalls are mocked, never run on live tasks."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import cpu_affinity_pilot as pilot


def process_record():
    return dict(kind="trainer", identity=dict(pid=100, starttime_ticks=9),
                default_original_affinity=[0, 1, 2, 3], target_affinity=list(range(56, 72)),
                threads=[dict(tid=100, starttime_ticks=10, original_affinity=[0, 1, 2, 3]),
                         dict(tid=101, starttime_ticks=11, original_affinity=[2])])


def snapshot(record):
    return dict(schema=pilot.SCHEMA, robotron_dir=str(pilot.ROBOTRON), uid=pilot.os.getuid(),
                boot_id=pilot.boot_id(), ready=True, problems=[], state="prepared",
                trainer_pid=100, actor_count=32, processes=[record])


class CpuAffinityPilotTests(unittest.TestCase):
    def test_real_child_thread_identity_is_readable_but_unrelated_command_is_refused(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        try:
            info = pilot.read_thread(child.pid, child.pid)
            self.assertEqual(info["tid"], child.pid)
            self.assertGreater(info["starttime_ticks"], 0)
            with self.assertRaises(ValueError), patch.object(pilot.os, "sched_setaffinity") as setter:
                pilot.identify_process(child.pid, "trainer")
            setter.assert_not_called()
        finally:
            child.terminate()
            child.wait(timeout=3)

    def test_reused_process_is_skipped_without_any_affinity_syscall(self):
        record = process_record()
        replacement = dict(record["identity"], starttime_ticks=999)
        with patch.object(pilot, "identify_process", return_value=replacement), \
                patch.object(pilot.os, "sched_setaffinity") as setter:
            result = pilot.restore_process(record)
        self.assertEqual(result["changed_threads"], 0)
        self.assertIn("saved identity", result["skipped"])
        setter.assert_not_called()

    def test_restore_preserves_original_threads_and_defaults_new_or_reused_threads(self):
        record = process_record()
        record["threads"].append(dict(tid=102, starttime_ticks=12, original_affinity=[3]))
        starts = {100: 10, 101: 11, 102: 999, 103: 1000}
        masks = {tid: set(range(56, 72)) for tid in starts}
        def info(pid, tid): return dict(tid=tid, starttime_ticks=starts[tid])
        def set_mask(tid, mask): masks[tid] = set(mask)
        with patch.object(pilot, "identify_process", return_value=record["identity"]), \
                patch.object(pilot, "thread_ids", return_value=list(starts)), \
                patch.object(pilot, "read_thread", side_effect=info), \
                patch.object(pilot.os, "sched_getaffinity", side_effect=lambda tid: masks[tid]), \
                patch.object(pilot.os, "sched_setaffinity", side_effect=set_mask):
            result = pilot.restore_process(record)
        self.assertEqual(masks[100], {0, 1, 2, 3})
        self.assertEqual(masks[101], {2})
        self.assertEqual(masks[102], {0, 1, 2, 3})
        self.assertEqual(masks[103], {0, 1, 2, 3})
        self.assertEqual(result["new_threads_using_leader_default"], [102, 103])

    def test_thread_replaced_after_inspection_is_not_targeted(self):
        record = process_record()
        with patch.object(pilot, "identify_process", return_value=record["identity"]), \
                patch.object(pilot, "read_thread", return_value=dict(tid=100, starttime_ticks=888)), \
                patch.object(pilot.os, "sched_setaffinity") as setter:
            with self.assertRaises(ProcessLookupError):
                pilot.set_verified_affinity(record, dict(tid=100, starttime_ticks=10), {56})
        setter.assert_not_called()

    def test_partial_apply_failure_rolls_back_from_durable_original_snapshot(self):
        record = process_record(); plan = snapshot(record)
        masks = {thread["tid"]: set(thread["original_affinity"]) for thread in record["threads"]}
        original_masks = copy.deepcopy(masks)
        failed = []
        def info(pid, tid): return dict(tid=tid, starttime_ticks=10 if tid == 100 else 11)
        def set_mask(tid, mask):
            self.assertTrue(path.exists(), "No mutation may precede durable snapshot")
            saved = json.loads(path.read_text())
            self.assertEqual(saved["processes"][0]["threads"], record["threads"])
            if tid == 101 and mask == set(range(56, 72)) and not failed:
                failed.append(True)
                raise PermissionError("test apply failure")
            masks[tid] = set(mask)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"snapshot.json"
            with patch.object(pilot, "identify_process", return_value=record["identity"]), \
                    patch.object(pilot, "capture_process", return_value=copy.deepcopy(record)), \
                    patch.object(pilot, "thread_ids", return_value=[100, 101]), \
                    patch.object(pilot, "read_thread", side_effect=info), \
                    patch.object(pilot.os, "sched_getaffinity", side_effect=lambda tid: masks[tid]), \
                    patch.object(pilot.os, "sched_setaffinity", side_effect=set_mask):
                with self.assertRaises(PermissionError):
                    pilot.apply_plan(plan, path)
            self.assertEqual(masks, original_masks)
            self.assertEqual(json.loads(path.read_text())["state"], "restored")

    def test_atomic_initial_snapshot_cannot_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"snapshot.json"
            pilot.atomic_json(path, dict(original=True), exclusive=True)
            with self.assertRaises(FileExistsError):
                pilot.atomic_json(path, dict(replacement=True), exclusive=True)
            self.assertEqual(json.loads(path.read_text()), dict(original=True))

    def test_process_replaced_during_snapshot_refresh_is_refused_before_publication(self):
        record = process_record(); replacement = copy.deepcopy(record)
        replacement["identity"]["starttime_ticks"] = 999
        with patch.object(pilot, "verify_process"), \
                patch.object(pilot, "capture_process", return_value=replacement), \
                patch.object(pilot, "atomic_json") as writer, \
                patch.object(pilot.os, "sched_setaffinity") as setter:
            with self.assertRaises(ProcessLookupError):
                pilot.apply_plan(snapshot(record), Path("unused.json"))
        writer.assert_not_called(); setter.assert_not_called()

    def test_default_status_performs_no_affinity_or_file_writes(self):
        plan = snapshot(process_record())
        with patch.object(pilot, "make_plan", return_value=plan), \
                patch.object(pilot.os, "sched_setaffinity") as setter, \
                patch.object(pilot, "atomic_json") as writer, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pilot.main([]), 0)
        setter.assert_not_called(); writer.assert_not_called()

    def test_snapshot_from_another_boot_is_refused_before_writes(self):
        plan = snapshot(process_record()); plan["boot_id"] = "another-boot"
        with patch.object(pilot.os, "sched_setaffinity") as setter:
            with self.assertRaises(ValueError):
                pilot.validate_snapshot(plan)
        setter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
