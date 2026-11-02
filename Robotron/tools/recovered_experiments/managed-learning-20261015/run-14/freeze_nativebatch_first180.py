#!/usr/bin/env python3
"""Freeze first prespecified settled180s from read-only stdlib observations."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pilot_reducer", BASE / "analyze_nativebatch_pilot.py")
reducer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reducer)
path = BASE / "nativebatch-pilot-observations.jsonl"
raw = path.read_bytes()
prefix = raw[:raw.rfind(b"\n") + 1]
rows = [json.loads(line) for line in prefix.splitlines()]
ready = json.loads((BASE / "actor192-nativebatch-all-connected.json").read_text())
allowed = reducer.epoch(ready["utc"]) + 90
rows = [row for row in rows if reducer.epoch(row["utc"]) >= allowed]
assert rows and all(not row.get("observation_error") for row in rows)
start = reducer.epoch(rows[0]["utc"])
end = next(i for i, row in enumerate(rows) if reducer.epoch(row["utc"]) - start >= 180)
rows = rows[:end + 1]
assert all(row["client_count"] == 192 and row["process_identity"]["pid"] == 967713 for row in rows)
assert len({row["process_identity"]["start_ticks"] for row in rows}) == 1
assert all(0 < reducer.epoch(b["utc"]) - reducer.epoch(a["utc"]) <= 2.5 for a, b in zip(rows, rows[1:]))
keys = ("schema", "generation", "sample_every", "latency_bucket_upper_ms", "batch_size_bucket_upper")
assert len({json.dumps({key: row["host_pipeline"][key] for key in keys}, sort_keys=True) for row in rows}) == 1
for row in rows:
    row["elapsed_s"] = reducer.epoch(row["utc"]) - start
    graph = row["host_pipeline"]["inference_graphs"]
    assert graph["ready"] and graph["capture_count"] == 128 and graph["runtime_capture_count"] == 0
    assert graph["fallback_count"] == 0 and graph["fatal_error"] is None
    native = row["host_pipeline"]["native_batch_update"]
    assert native["enabled"] and native["available"] and native["fallback_count"] == native["error_count"] == 0
    assert row["deadline_lines"] == 0 and not row["parse_error_lines"] and not any(row["console_counts"].values())
phase = reducer.window(rows, "nativepriority_enabled_first180s")
assert phase["native_batch_update"]["delta"]["success_count"] > 0
logs = []
for log in sorted(BASE.glob("fleet*.log")):
    data = log.read_bytes()
    complete = data[:data.rfind(b"\n") + 1]
    assert b"[SOCKET ACTION TIMEOUT]" not in complete
    logs.append(dict(path=str(log), complete_prefix_bytes=len(complete), sha256=hashlib.sha256(complete).hexdigest(), exact_actor_timeout_lines=0))
recent = json.loads((BASE.parent / "run-13/native1000-wait1-fixed180-result.json").read_text())["phase"]
strong = json.loads((BASE / "pilot-baseline.json").read_text())["values"]["samples_per_s"]["mean"]
subset = b"".join((json.dumps(row, separators=(",", ":")) + "\n").encode() for row in rows)
checkpoint = BASE.parents[2] / "models_dqn/managed-checkpoints/fresh3-64M.pt"
checkpoint_evidence = dict(path=str(checkpoint), exists=checkpoint.exists(), timing_caution="File mtime is not a save-start/end receipt. Retain any root checkpoint timing evidence; do not remove overlapping rows.")
if checkpoint.exists():
    stat = checkpoint.stat()
    checkpoint_evidence.update(size=stat.st_size, mtime_utc=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat())
report = dict(schema="robotron-nativebatch-fixed180-result-v1", utc=datetime.now(timezone.utc).isoformat(), phase=phase,
    producer_pid=967713, recent_run13_baseline=recent, strong_baseline_samples_per_s=strong,
    vs_recent_samples_ratio=phase["samples_per_s"] / recent["samples_per_s"], vs_strong_samples_ratio=phase["samples_per_s"] / strong,
    five_percent_gates=dict(recent=recent["samples_per_s"] * 1.05, strong=strong * 1.05,
        recent_pass=phase["samples_per_s"] >= recent["samples_per_s"] * 1.05, strong_pass=phase["samples_per_s"] >= strong * 1.05),
    guards=dict(graphs128=True, runtime_capture0=True, graph_fallback0=True, fatal_none=True, native_enabled_available=True,
        native_fallback_error0=True, main_errors0=True, exact_actor_timeouts0=True), actor_logs=logs, checkpoint_overlap_evidence=checkpoint_evidence,
    source_prefix=dict(path=str(path), complete_prefix_bytes=len(prefix), sha256=hashlib.sha256(prefix).hexdigest()),
    subset=dict(path=str(BASE / "nativebatch-settled180-observations.jsonl"), sha256=hashlib.sha256(subset).hexdigest()),
    limitations=["Sequential operational comparison with evolving model, replay, game density and host scheduling; not randomized causal A/B.",
        "Native success counts all SumTree batch calls, including priority boosts; it is not an optimizer-update counter.",
        "Sampled host timings are not GPU kernel timings. Energy is GPU-only sampled power; observations are autocorrelated."])
with (BASE / "nativebatch-settled180-observations.jsonl").open("xb") as stream:
    stream.write(subset)
with (BASE / "nativebatch-fixed180-result.json").open("x") as stream:
    json.dump(report, stream, indent=2)
    stream.write("\n")
print(json.dumps({key: phase[key] for key in ("utc_start", "utc_end", "duration_s", "samples_per_s", "frames_per_s", "samples_per_frame", "samples_per_joule")}))
print(json.dumps({key: report[key] for key in ("vs_recent_samples_ratio", "vs_strong_samples_ratio", "five_percent_gates", "checkpoint_overlap_evidence")}))
