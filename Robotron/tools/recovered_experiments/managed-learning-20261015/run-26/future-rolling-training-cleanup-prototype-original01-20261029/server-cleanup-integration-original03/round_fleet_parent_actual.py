"""Owned training rounds: each slot plays one committed full game, then exits.

Completed slots are never respawned while another slot in that round is active.
The next complete fleet starts only after all scores are durable and actors stop.
These changing-policy training scores are not frozen-policy confirmation results.
"""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import time
import urllib.request


def publish(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class JournalTail:
    def __init__(self, path):
        self.path = path
        self.position = path.stat().st_size if path.exists() else 0
        self.identity = None if not path.exists() else (path.stat().st_dev, path.stat().st_ino)
        self.pending = b""

    def poll(self):
        if not self.path.exists():
            return []
        with self.path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            identity = (info.st_dev, info.st_ino)
            if self.identity is None:
                self.identity = identity
            if identity != self.identity or info.st_size < self.position:
                raise RuntimeError("Completion journal was replaced or truncated")
            stream.seek(self.position)
            raw = stream.read(2_000_000)
            self.position += len(raw)
        pieces = (self.pending + raw).split(b"\n")
        self.pending = pieces.pop()
        if len(self.pending) > 1_000_000:
            raise RuntimeError("Completion journal line exceeded bound")
        return [json.loads(line) for line in pieces if line]


def confirmed_result(row, slots, started):
    return (type(row) is dict and type(row.get("client_slot")) is int
            and row["client_slot"] in slots and row.get("complete") is True
            and row.get("eligible") is True and row.get("known_start") is True
            and row.get("boundary_reason") in ("score_reset", "zero_score_restart")
            and type(row.get("score")) is int and row["score"] >= 0
            and type(row.get("start_unix_s")) in (int, float)
            and row["start_unix_s"] >= started
            and type(row.get("journal_game_id")) is str)


def should_spawn(slot, processes, results):
    return slot not in processes and slot not in results


def stop_owned(processes):
    # Popen objects identify only children created by this supervisor. No name,
    # slot-wide, system-wide or unrelated-process signals are ever used.
    for item in processes.values():
        child = item["process"]
        if child.poll() is None:
            child.send_signal(signal.SIGCONT)
            child.terminate()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and any(x["process"].poll() is None for x in processes.values()):
        time.sleep(.05)
    for item in processes.values():
        child = item["process"]
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


class RoundFleet:
    def __init__(self, roles, journal, output):
        self.roles = roles
        self.slots = set(map(int, roles["slot_eval"]))
        if self.slots != set(range(192)):
            raise ValueError("Exactly slots0..191 required")
        self.journal = JournalTail(journal)
        self.output = output
        self.output.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.stopping = False

    def stop(self, *_):
        self.stopping = True

    def wait_ready(self):
        while not self.stopping:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8771/api/now", timeout=3) as response:
                    api = json.load(response)
                if api["training_enabled"] and api["client_count"] == 0:
                    return
            except (OSError, ValueError):
                pass
            time.sleep(1)

    def spawn(self, slot, directory, number):
        env = dict(os.environ, ROBOTRON_CLIENT_SLOT=str(slot),
                   ROBOTRON_RETIRE_AFTER_GAME="1", ROBOTRON_PREVIEW_FPS="30",
                   ROBOTRON_ACTOR_ROUND=str(number))
        executable = env["MAME_BIN"]
        root = Path(__file__).resolve().parents[2]
        args = [executable, "robotron", "-rompath", str(root / "roms"),
                "-cheat", "-nothrottle", "-sound", "none", "-video", "none",
                "-skip_gameinfo", "-autoboot_script", str(root / "Scripts/main.lua")]
        with (directory / ("slot-%03d.log" % slot)).open("ab") as log:
            child = subprocess.Popen(args, env=env, stdout=log, stderr=subprocess.STDOUT)
        return dict(process=child, started_unix_s=time.time(), frozen=False)

    def run_round(self, number):
        directory = self.output / ("round-%06d" % number)
        directory.mkdir(mode=0o700)
        started = time.time()
        processes, results, stopped, failures = {}, {}, {}, {}
        last_status_monotonic = 0.0
        publish(directory / "started.json", dict(round=number, started_unix_s=started,
                slots=sorted(self.slots), one_full_game_each=True,
                next_round_waits_for_all=True, quality_qualified=False))
        try:
            for slot in sorted(self.slots):
                if self.stopping:
                    return False
                processes[slot] = self.spawn(slot, directory, number)
            while not self.stopping:
                for row in self.journal.poll():
                    if not confirmed_result(row, self.slots, started):
                        continue
                    slot = row["client_slot"]
                    if slot in results:
                        if results[slot]["journal_game_id"] != row["journal_game_id"]:
                            raise RuntimeError("A slot completed more than one game in a round")
                        continue
                    item = processes[slot]
                    if row["start_unix_s"] < item["started_unix_s"]:
                        continue
                    # Preserve the complete raw score receipt before declaring
                    # this actor retired or invoking the no-respawn decision.
                    publish(directory / ("slot-%03d-result.json" % slot),
                            dict(pid=item["process"].pid, round=number, result=row))
                    results[slot] = row
                    item["result_seen_monotonic_s"] = time.monotonic()
                for slot, item in list(processes.items()):
                    child = item["process"]
                    code = child.poll()
                    if slot in results:
                        if code is not None:
                            stopped[slot] = dict(exit=code, frozen=False)
                            if code != 0:
                                raise RuntimeError("Completed actor did not exit normally")
                        elif (not item["frozen"] and time.monotonic()
                              - item["result_seen_monotonic_s"] > 5):
                            child.send_signal(signal.SIGSTOP)
                            deadline = time.monotonic() + 1
                            while time.monotonic() < deadline:
                                state = Path("/proc", str(child.pid), "stat").read_text().rsplit(")", 1)[1].split()[0]
                                if state in ("T", "t"):
                                    break
                                time.sleep(.01)
                            else:
                                raise RuntimeError("Completed actor could not be frozen")
                            item["frozen"] = True
                            stopped[slot] = dict(exit=None, frozen=True)
                    elif code is not None:
                        failures[slot] = failures.get(slot, 0) + 1
                        publish(directory / ("slot-%03d-attempt-%02d-failed.json" % (slot, failures[slot])),
                                dict(slot=slot, pid=child.pid, exit=code,
                                     completed_score_received=False, quality_qualified=False))
                        if failures[slot] >= 3:
                            raise RuntimeError("Actor repeatedly exited without a committed game")
                        del processes[slot]
                for slot in sorted(self.slots):
                    if should_spawn(slot, processes, results):
                        processes[slot] = self.spawn(slot, directory, number)
                display = [dict(slot=slot, score=row["score"], level=row["max_level"],
                                duration_s=row["duration_s"], journal_game_id=row["journal_game_id"])
                           for slot, row in sorted(results.items())]
                status = dict(round=number, total=len(self.slots), completed=len(results),
                              retired=len(stopped), active=len(self.slots)-len(stopped),
                              results=display, directory=str(directory),
                              complete=len(stopped)==len(self.slots), updated_unix_s=time.time())
                if time.monotonic() - last_status_monotonic >= 1 or status["complete"]:
                    publish(self.output / "status.json", status)
                    last_status_monotonic = time.monotonic()
                if len(stopped) == len(self.slots):
                    scores = [row["score"] for row in results.values()]
                    publish(directory / "summary.json", dict(status, mean=statistics.mean(scores),
                            median=statistics.median(scores), all_final_scores_durable=True,
                            changing_policy_training_round=True, quality_qualified=False))
                    text = io.StringIO()
                    writer = csv.DictWriter(text, fieldnames=["slot", "score", "level", "duration_s", "journal_game_id"])
                    writer.writeheader(); writer.writerows(display)
                    with (directory / "scores.csv").open("x") as stream:
                        stream.write(text.getvalue()); stream.flush(); os.fsync(stream.fileno())
                    return True
                time.sleep(.1)
            return False
        finally:
            stop_owned(processes)

    def run(self):
        self.wait_ready()
        existing = [int(p.name.split("-")[1]) for p in self.output.glob("round-*") if p.is_dir()]
        number = max(existing, default=0) + 1
        while not self.stopping:
            if not self.run_round(number):
                return
            number += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roles", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fleet = RoundFleet(json.loads(args.roles.read_bytes()), args.journal, args.output)
    signal.signal(signal.SIGINT, fleet.stop)
    signal.signal(signal.SIGTERM, fleet.stop)
    fleet.run()


if __name__ == "__main__":
    main()
