"""Durable launch tests use temporary paths and mocked systemd operations."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from . import start_managed_training as launcher


class ManagedTrainingTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory) / "Robotron"
        for relative in ("models_dqn/robotron_dqn_latest.pt", "starttrainer.sh", "startmame.sh",
                         "tools/mame_with_socket_wait.sh", "tools/build_socket_wait.py",
                         "Scripts/wait_for_trainer.py", "Scripts/robotron_socket_wait.c"):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture")
        python = root.parent / ".venv-gb300/bin/python"
        python.parent.mkdir(parents=True)
        python.write_text("fixture")
        return root

    def test_plan_is_read_only_and_records_supervision_and_recipe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            run = Path(directory) / "new run"
            result = launcher.plan(run, robotron_dir=root)
            self.assertFalse(run.exists())
            self.assertEqual(result["trainer_environment"]["DQN_BATCH_SIZE"], "4096")
            self.assertEqual(result["trainer_environment"]["DQN_RATCHET"], "0")
            self.assertTrue(result["trainer_environment"]["CUDA_VISIBLE_DEVICES"].startswith("GPU-"))
            self.assertTrue(result["fleet_environment"]["ROBOTRON_FLEET_ID"].startswith("managed-"))
            fleet = result["fleet_command"]
            self.assertIn("--property=KillMode=mixed", fleet)
            self.assertIn("--property=Wants=" + result["trainer_unit"], fleet)
            self.assertFalse(any(item.startswith("--property=Requires=") for item in fleet))
            self.assertIn("--property=After=" + result["trainer_unit"], fleet)
            self.assertIn("--property=KillSignal=SIGINT", result["trainer_command"])
            self.assertEqual(fleet[-6:], ["192", "novideo", "nonaudio", "--supervise", "--socket-address", "dell:9998"])

    def test_existing_logs_or_missing_checkpoint_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            run = Path(directory) / "existing"
            run.mkdir(); (run / "console.log").write_text("keep")
            with self.assertRaisesRegex(ValueError, "new or empty"):
                launcher.plan(run, robotron_dir=root)
            (root / "models_dqn/robotron_dqn_latest.pt").write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "nonempty"):
                launcher.plan(Path(directory) / "new", robotron_dir=root)

    def test_any_existing_mame_prevents_launch_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            result = launcher.plan(Path(directory) / "new", robotron_dir=root)
            with patch.object(launcher, "active_robotron_processes", return_value=[dict(pid=1,kind="mame")]), \
                    patch.object(launcher.subprocess, "run") as runner:
                with self.assertRaisesRegex(ValueError, "Existing Robotron"):
                    launcher.launch(result)
                runner.assert_not_called()
            self.assertFalse(Path(result["run_dir"]).exists())

    def test_live_process_detection_does_not_match_command_text(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            records = {1: ["/usr/games/mame", "robotron"], 2: ["/venv/bin/python", "-Xgil=0", "Scripts/run_dqn.py"],
                       3: ["/bin/bash", "-c", "mame robotron Scripts/run_dqn.py"]}
            for pid, argv in records.items():
                path = proc / str(pid); path.mkdir(); (path / "cmdline").write_bytes("\0".join(argv).encode()+b"\0")
            self.assertEqual([row["pid"] for row in launcher.active_robotron_processes(proc)], [1, 2])

    def test_launch_records_commands_before_starting_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            result = launcher.plan(Path(directory) / "new", robotron_dir=root)
            calls = []
            def run(command, **kwargs):
                saved = json.loads((Path(result["run_dir"]) / "launch.json").read_text())
                self.assertEqual(saved["state"], "prepared")
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, result["fleet_environment"]["ROBOTRON_SOCKET_WAIT_LIBRARY"]+"\n")
            with patch.object(launcher, "assert_idle"), patch.object(launcher.subprocess, "run", side_effect=run):
                launcher.launch(result)
            self.assertEqual(calls, [result["socket_wait_build_command"], result["trainer_command"], result["fleet_command"]])
            self.assertEqual(json.loads((Path(result["run_dir"]) / "launch.json").read_text())["state"], "launched")

    def test_default_cli_does_not_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            result = {"schema": launcher.SCHEMA}
            with patch.object(launcher, "plan", return_value=result), patch.object(launcher, "assert_idle"), \
                    patch.object(launcher, "launch") as start, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.main(["--run-dir", str(Path(directory) / "new")]), 0)
            start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
