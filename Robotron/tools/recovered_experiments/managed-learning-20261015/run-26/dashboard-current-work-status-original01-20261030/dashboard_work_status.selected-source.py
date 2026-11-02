"""Publish current work and observed progress for the training report."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import time


def read(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        raise ValueError("Work status metadata exceeds its size limit")
    return json.loads(raw)


def atomic(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    temporary = path.with_name("." + path.name + "." + str(os.getpid()) + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def process_live(owner):
    try:
        raw = Path("/proc", str(owner["pid"]), "stat").read_text()
        return int(raw.rsplit(")", 1)[1].split()[19]) == owner["birth"]
    except (OSError, ValueError):
        return False


def benchmark_progress(config, work, now):
    result_path = Path(config["result"])
    if result_path.is_file():
        result = read(result_path)
        passed = result.get("actual_exit") == 0 and result.get("report_exists") is True
        work["current_stage"] = ("Snapshot validation complete; preparing the restart trial" if passed else
                                 "Snapshot validation needs review")
        work["waiting_for"] = ("Final restart-preservation checks before the first cap-8 interval" if passed else
                               "Review of the preserved validation result before selecting the next action")
        work["eta"] = "The snapshot check has ended. The next stage has no confirmed start time yet."
        return {"state": "complete" if passed else "needs_review", "total": 8147}
    owner = read(config["owner"])
    if not process_live(owner):
        work["current_stage"] = "Verifying the offline validation result"
        work["waiting_for"] = "The original command's final result record"
        work["eta"] = "No completion estimate is available while the final result is being checked."
        return {"state": "result_pending", "total": 8147}
    path = Path(config["progress"])
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 65536))
        lines = stream.read().splitlines()
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if isinstance(row, dict) and isinstance(row.get("progress"), dict):
            rows.append(row)
    if not rows:
        work["eta"] = "Waiting for the first measured progress update."
        return {"state": "starting", "total": 8147}
    last = rows[-1]
    done, total = last["progress"]["completed"], last["progress"]["total"]
    if type(done) is not int or total != 8147 or not 0 <= done <= total:
        raise ValueError("Unexpected offline validation progress")
    age = max(0, now - path.stat().st_mtime)
    work["current_stage"] = f"Checking faster report validation: {done:,} / {total:,} snapshots"
    work["eta"] = "This check is running. Restart and state verification follow; their duration is not yet known."
    if len(rows) >= 2 and age < 60:
        first = rows[max(0, len(rows) - 10)]
        count = done - first["progress"]["completed"]
        seconds = last["elapsed_s"] - first["elapsed_s"]
        if count > 0 and seconds > 0:
            remaining = max(0, (total - done) * seconds / count - age)
            work["estimated_completion_unix_s"] = now + remaining
            work["eta"] = ("Estimated finish of this snapshot check: " +
                time.strftime("%I:%M %p %Z", time.localtime(now + remaining)).lstrip("0") +
                ". Restart and state verification follow; this estimate excludes those later steps.")
    if age >= 60:
        work["eta"] = "The original process is live, but its progress update is delayed. No current ETA is available."
    return {"state": "running", "completed": done, "total": total,
            "last_progress_age_s": age, "updated_unix_s": now}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--max-seconds", type=int, default=28800)
    args = parser.parse_args()
    args.runtime.mkdir(mode=0o700, exist_ok=False)
    lock = (args.public.parent / ".dashboard-work-writer.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    pid = os.getpid()
    birth = int(Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()[19])
    atomic(args.runtime / "owner.json", dict(pid=pid, birth=birth, started_unix_s=time.time()))
    deadline = time.monotonic() + args.max_seconds
    last_log = 0
    while time.monotonic() < deadline and not (args.runtime / "STOP").exists():
        now = time.time()
        try:
            control = read(args.control)
            public = read(args.public)
            work = dict(public.get("next_work", {}))
            work.update(control["next_work"])
            work.pop("estimated_completion_unix_s", None)
            if control.get("mode") == "offline_validation":
                public["offline_validation"] = benchmark_progress(control["benchmark"], work, now)
            work["updated_unix_s"] = now
            public["next_work"] = work
            public["updated_unix_s"] = now
            atomic(args.public, public)
            heartbeat = dict(pid=pid, birth=birth, updated_unix_s=now,
                             current_stage=work.get("current_stage"),
                             progress=public.get("offline_validation"))
            atomic(args.runtime / "heartbeat.json", heartbeat)
            if now - last_log >= 30:
                print(json.dumps(heartbeat), flush=True)
                last_log = now
        except Exception as error:
            print(json.dumps(dict(status="work_status_update_delayed", error=repr(error),
                                  updated_unix_s=now)), flush=True)
        time.sleep(5)
    atomic(args.runtime / "result.json", dict(actual_exit=0, original_pid=pid, birth=birth,
                                              ended_unix_s=time.time(), public_writer_released=True))


if __name__ == "__main__":
    main()
