#!/usr/bin/env python3
"""Bounded1Hz stdlib-only console/API/file/proc observer; never controls work."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.request

BASE = Path(__file__).resolve().parent
GAME = BASE.parents[2]
PID = 967713
DURATION = 360
MODEL = GAME / "models_dqn"
LOG = BASE / "console.log"
OUT = BASE / "autosave-stall-observations.jsonl"


def identity(path):
    value = path.read_text(); fields = value[value.rfind(")") + 2:].split()
    return dict(start_ticks=int(fields[19]), state=fields[0], minor_faults=int(fields[7]),
        major_faults=int(fields[9]), user_ticks=int(fields[11]), system_ticks=int(fields[12]))


def stat(path):
    try:
        value = path.stat()
        return dict(path=str(path), inode=value.st_ino, size=value.st_size, mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns)
    except FileNotFoundError:
        return dict(path=str(path), missing=True)


started = time.monotonic()
producer = identity(Path(f"/proc/{PID}/stat"))
tasks = {}
for directory in Path(f"/proc/{PID}/task").iterdir():
    try:
        name = (directory / "comm").read_text().strip()
        if name in ("TrainWorker", "InferBatchWorke", "InferBatchWork", "ReplayPrefetch", "ReplayWorker") or int(directory.name) == PID:
            tasks[directory.name] = name
    except FileNotFoundError:
        pass
original = LOG.read_bytes()
position = len(original)
console_identity = LOG.stat().st_ino
deadline_total = original.count(b"Batched inference request timed out")
previous_utc = None
with OUT.open("x") as output:
    for index in range(DURATION + 1):
        tick = time.monotonic()
        utc = datetime.now(timezone.utc).isoformat()
        row = dict(utc=utc, elapsed_s=tick-started, index=index, pid=PID, process=identity(Path(f"/proc/{PID}/stat")))
        assert row["process"]["start_ticks"] == producer["start_ticks"], "Producer identity changed"
        status = Path(f"/proc/{PID}/status").read_text()
        row["process_memory"] = {line.split(":", 1)[0]: line.split(":", 1)[1].strip()
            for line in status.splitlines() if line.startswith(("VmSize:", "VmRSS:", "VmSwap:", "Threads:"))}
        try:
            with urllib.request.urlopen("http://127.0.0.1:8771/api/now", timeout=2) as stream:
                current = json.load(stream)
            row["api"] = {key: current.get(key) for key in ("ts", "frame_count", "learner_frame_count", "optimized_samples",
                "training_steps", "client_count", "fps", "avg_inf_ms", "train_priority_ms", "train_step_ms", "gpu1_util",
                "host_pipeline", "bank_persistence", "pipeline_read_error", "bank_persistence_read_error")}
        except Exception as error:
            row["api_error"] = repr(error)
        info = LOG.stat()
        assert info.st_ino == console_identity and info.st_size >= position, "Console replaced/truncated"
        with LOG.open("rb") as stream:
            stream.seek(position)
            appended = stream.read()
        row["console_append"] = dict(start_byte=position, end_byte=position+len(appended),
            sha256=hashlib.sha256(appended).hexdigest(), poll_interval_start_utc=previous_utc,
            interesting_lines=[line.decode(errors="replace")[:600] for line in appended.splitlines()
                if any(term in line for term in (b"timed out", b"[BANKS]", b"checkpoint", b"archived ->", b"Traceback"))])
        deadline_total += appended.count(b"Batched inference request timed out")
        row["console_deadline_total"] = deadline_total
        position += len(appended)
        files = [MODEL / ("robotron_dqn_" + name + suffix) for name in ("latest", "best") for suffix in (".pt", ".pt.bak", ".pt.tmp")]
        row["checkpoint_files"] = [stat(path) for path in files]
        row["bank_selectors"] = []
        for bank in ("hof", "ephof"):
            path = MODEL / f"robotron_dqn_latest_replay_{bank}/CURRENT.json"
            value = path.read_bytes(); selected = json.loads(value)
            generation = path.parent / "generations" / selected["generation"]
            row["bank_selectors"].append(dict(bank=bank, selector=stat(path), sha256=hashlib.sha256(value).hexdigest(),
                value=selected, files=[stat(child) for child in sorted(generation.iterdir())]))
        row["threads"] = {}
        for tid, name in tasks.items():
            directory = Path(f"/proc/{PID}/task/{tid}")
            try:
                row["threads"][tid] = dict(name=name, stat=identity(directory / "stat"),
                    wchan=(directory / "wchan").read_text().strip(), schedstat=(directory / "schedstat").read_text().strip())
            except FileNotFoundError:
                row["threads"][tid] = dict(name=name, ended=True)
        row["pressure"] = {name: Path(f"/proc/pressure/{name}").read_text() for name in ("cpu", "memory", "io")}
        output.write(json.dumps(row, separators=(",", ":")) + "\n"); output.flush()
        if index % 30 == 0 or row["console_append"]["interesting_lines"]:
            print(json.dumps(dict(utc=utc, index=index, deadlines=deadline_total, events=row["console_append"]["interesting_lines"])), flush=True)
        previous_utc = utc
        if index < DURATION:
            time.sleep(max(0, 1-(time.monotonic()-tick)))
