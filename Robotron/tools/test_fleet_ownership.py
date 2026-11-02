"""Exercise real /proc ownership filtering without launching or killing MAME."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "startmame.sh"


@unittest.skipUnless(shutil.which("gcc") and Path("/proc").is_dir(), "Linux and gcc required")
class FleetOwnershipTests(unittest.TestCase):
    def test_tagged_missing_client_never_uses_unscoped_process_fallback(self):
        source = SCRIPT.read_text()
        start = source.index("kill_client_by_id() {")
        function = source[start:source.index("\n}\n", start)+3]
        stubs = "\nlist_robotron_pids() { return 0; }\nps() { echo BROAD_PS_FALLBACK >&2; }\n"
        for tag in ['test-owned','']:
            result = subprocess.run(["bash", "-c", function + stubs + "kill_client_by_id 123"],
                                    env={**os.environ, "ROBOTRON_FLEET_ID": tag},
                                    text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("BROAD_PS_FALLBACK", result.stderr)
            self.assertIn("No Robotron MAME process found", result.stdout)

    def test_listing_matches_exact_tag_and_manual_listing_excludes_managed_clients(self):
        source = SCRIPT.read_text()
        start = source.index("list_robotron_pids() {")
        function = source[start:source.index("\n}\n", start)+3]
        with tempfile.TemporaryDirectory(prefix="robotron-owner-test-") as directory:
            executable = Path(directory) / "mame"
            subprocess.run(["gcc", "-x", "c", "-o", str(executable), "-"],
                           input="#include <unistd.h>\nint main(void) { for (;;) pause(); }\n",
                           text=True, capture_output=True, check=True, timeout=15)
            tag = "test-" + Path(directory).name
            processes = []
            try:
                for value in (tag, tag + "-other", None):
                    environment = dict(os.environ)
                    environment.pop("ROBOTRON_FLEET_ID", None)
                    if value is not None:
                        environment["ROBOTRON_FLEET_ID"] = value
                    processes.append(subprocess.Popen([str(executable), "robotron"], env=environment))
                def listing(value):
                    environment = dict(os.environ)
                    environment["ROBOTRON_FLEET_ID"] = value
                    result = subprocess.run(["bash", "-c", function + "\nlist_robotron_pids"],
                                            env=environment, text=True, capture_output=True, check=True, timeout=5)
                    return {int(line) for line in result.stdout.splitlines()}
                self.assertEqual(listing(tag), {processes[0].pid})
                self.assertEqual(listing(tag + "-other"), {processes[1].pid})
                self.assertEqual(listing(tag + "-missing"), set())
                self.assertIn(processes[2].pid,listing(""))
                self.assertFalse({processes[0].pid,processes[1].pid}&listing(""))
                self.assertTrue(all(process.poll() is None for process in processes))
            finally:
                # Only terminate the exact fake child handles owned by this test.
                for process in processes:
                    process.terminate()
                for process in processes:
                    process.wait(timeout=3)

    def test_untagged_systemd_evaluators_are_excluded_from_manual_listing(self):
        source=SCRIPT.read_text();start=source.index('list_robotron_pids() {')
        function=source[start:source.index('\n}\n',start)+3]
        # Real readable /proc records, with only the cgroup text substituted.
        pid=os.getpid()
        stubs='''
pgrep() { printf '%s\\n' "$TEST_PID"; }
grep() {
    if [[ "${3:-}" == "/proc/$TEST_PID/cgroup" ]]; then
        printf '0::/user.slice/app.slice/robotron-private-quality.service\\n' | command grep -Eq "$2"
    else
        command grep "$@"
    fi
}
'''
        result=subprocess.run(['bash','-c',function+stubs+'\nlist_robotron_pids'],
            env={**os.environ,'TEST_PID':str(pid),'ROBOTRON_FLEET_ID':''},
            capture_output=True,text=True,check=True,timeout=5)
        self.assertEqual(result.stdout,'')


if __name__ == "__main__":
    unittest.main()
