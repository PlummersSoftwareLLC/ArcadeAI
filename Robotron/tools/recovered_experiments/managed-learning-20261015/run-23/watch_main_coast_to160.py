"""Root-authorized compact 5s main-only coast watch; no quality/model reads."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import io
import json
import math
import os
import time
import urllib.request

BASE = Path(__file__).resolve().parent
GAME = BASE.parents[2]
MAIN, SUPERVISOR = 1436155, 1438661
OUTPUT = BASE / "main-coast-to160-health.jsonl"
COMPLETE = BASE / "main-coast-to160-complete.json"
GATE = BASE / "fresh3-160M-gate.json"
DEADLINE = datetime(2026, 10, 16, 14, 45, tzinfo=timezone.utc).timestamp()
PERIOD, GATE_TAIL = 5.0, 120.0
CONTROL = GAME / "models_dqn/learning_control.json"
LOG = BASE / "console.log"
CSV = BASE / "training.csv"

def utc():
    return datetime.now(timezone.utc).isoformat()

def process(pid):
    try:
        fields = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()
        return dict(alive=fields[0] != "Z", start_ticks=int(fields[19]))
    except (OSError, IndexError, ValueError):
        return dict(alive=False, start_ticks=None)

def identity(path):
    x = path.stat()
    return dict(size=x.st_size, mtime_ns=x.st_mtime_ns, inode=x.st_ino, device=x.st_dev)

def finite_scalar(value):
    value = float(value)
    return value if math.isfinite(value) else str(value)

pin = json.loads((BASE / "actor192-all-connected.json").read_bytes())
actors = {int(row["pid"]): int(row["start_ticks"]) for row in pin["actors"]}
attested = json.loads((BASE / "startup-independent-process-source-observation.json").read_bytes())
sources = {str(GAME.parent / name): identity(GAME.parent / name) for name in attested["source_hashes"]}
control_digest = hashlib.sha256(CONTROL.read_bytes()).hexdigest()
initial_owners = {pid: process(pid) for pid in (MAIN, SUPERVISOR)}
assert len(actors) == 192 and all(row["alive"] for row in initial_owners.values())
patterns = ["Training error:", "Traceback (most recent call last):",
            "Batched inference request timed out", "Batched inference failed",
            "disabling torch.compile", "torch.compile unavailable",
            "Non-finite loss", "Partial frame header", "Invalid frame header"]
counts = dict.fromkeys(patterns, 0)
log_offset = LOG.stat().st_size
csv_offset = CSV.stat().st_size
with CSV.open() as f:
    csv_fields = next(csv.reader(f))
log_pending, csv_pending = b"", b""
start, started_utc, mono_start = time.time(), utc(), time.monotonic()
initial_offsets = dict(console=log_offset, csv=csv_offset)
previous_exposure = None
previous_clocks = None
expected_epochs = None
expected_pipeline = None
drop_baseline = None
gate_seen = None
issues_seen, notices_seen = {}, {}
last_announced, rows, gaps = set(), 0, []
largest_gap, last_tick, next_guard, cached_guard = 0.0, None, 0.0, None

with OUTPUT.open("x") as output:
    while time.time() < DEADLINE:
        tick = time.monotonic()
        now = time.time()
        if last_tick is not None:
            gap = tick - last_tick
            largest_gap = max(largest_gap, gap)
            if gap > PERIOD * 1.5:
                gaps.append(dict(utc=utc(), elapsed_s=gap))
        last_tick = tick
        row = dict(utc=utc(), ts=now, monotonic_s=tick, elapsed_s=tick - mono_start)
        issues, notices = [], []
        owners = {str(pid): process(pid) for pid in initial_owners}
        row["owners"] = owners
        if any(not owners[str(pid)]["alive"] or owners[str(pid)]["start_ticks"] != v["start_ticks"]
               for pid, v in initial_owners.items()):
            issues.append("main_owner_identity_or_liveness_changed")
        mismatches = []
        for pid, expected in actors.items():
            value = process(pid)
            if not value["alive"] or value["start_ticks"] != expected:
                mismatches.append(pid)
        row["actor_pin"] = dict(expected=192, matched=192-len(mismatches), mismatched_pids=mismatches)
        if mismatches:
            issues.append("pinned_actor_identity_or_liveness_changed")
        if tick >= next_guard:
            changed = [path for path, expected in sources.items() if identity(Path(path)) != expected]
            cached_guard = dict(utc=row["utc"], source_stat_identity_unchanged=not changed,
                                changed_sources=changed, control_sha256=hashlib.sha256(CONTROL.read_bytes()).hexdigest())
            next_guard = tick + 60
        row["source_control_guard"] = cached_guard
        if not cached_guard["source_stat_identity_unchanged"]:
            issues.append("main_source_stat_identity_changed")
        if cached_guard["control_sha256"] != control_digest:
            issues.append("main_control_bytes_changed")
        try:
            api = json.load(urllib.request.urlopen("http://127.0.0.1:8771/api/now", timeout=2))
            h = api["host_pipeline"]
            g, n, e = h["inference_graphs"], h["native_batch_update"], h["learning_exposure"]
            o, r = e["optimizer"], e["replay"]
            clocks = {key: api[key] for key in ("frame_count", "learner_frame_count", "optimized_samples", "training_steps", "measurement_frames")}
            epochs = dict(optimizer=[o[k] for k in ("schema", "process_id", "instance_monotonic_ns", "epoch", "epoch_reason")],
                          replay=[r[k] for k in ("schema", "process_id", "instance_monotonic_ns", "epoch", "epoch_reason")])
            if expected_epochs is None:
                expected_epochs = epochs
                expected_pipeline = h["generation"]
            if epochs != expected_epochs or h["generation"] != expected_pipeline:
                issues.append("new_counter_epoch_or_pipeline_generation")
            if previous_clocks and any(clocks[k] < previous_clocks[k] for k in clocks):
                issues.append("main_clock_moved_backwards")
            previous_clocks = clocks
            current = dict(amp_skipped=o["total"]["amp_skipped"], unavailable=o["total"]["unavailable"],
                           accepted_learner=r["accepted_learner_total"], applied=o["total"]["applied"],
                           attempts=o["total"]["attempts_started"])
            if previous_exposure:
                if any(current[k] < previous_exposure[k] for k in current):
                    issues.append("exposure_total_moved_backwards")
                if current["amp_skipped"] > previous_exposure["amp_skipped"]:
                    notices.append("recognized_AMP_skip_delta")
            previous_exposure = current
            pending = o["unclassified_started_total"]
            if current["unavailable"] or pending not in (0, 1) or (not o["available"] and pending != 1):
                issues.append("optimizer_telemetry_unavailable_or_unclassified")
            row["health"] = dict(API_ts=api["ts"], clients=api["client_count"], clocks=clocks,
                loss=finite_scalar(api["loss"]), grad_norm=finite_scalar(api["grad_norm"]),
                training_enabled=api["training_enabled"], fps=api["fps"], avg_inf_ms=api["avg_inf_ms"],
                epoch_identity=epochs, optimizer_totals=o["total"], optimizer_pending=pending,
                optimizer_available=o["available"], accepted_learner=r["accepted_learner_total"],
                graph={k:g[k] for k in ("ready", "capture_count", "runtime_capture_count", "fallback_count", "fatal_error")},
                native={k:n[k] for k in ("enabled", "available", "success_count", "fallback_count", "error_count")})
            if api["client_count"] != 192:
                issues.append("main_client_count_not192")
            if not math.isfinite(float(api["loss"])):
                issues.append("nonfinite_loss")
            if not math.isfinite(float(api["grad_norm"])):
                notices.append("sampled_nonfinite_grad_not_automatic_fault")
            if api["pipeline_read_error"] or api["bank_persistence_read_error"]:
                issues.append("API_metadata_read_error")
            if not g["ready"] or g["capture_count"] != 128 or g["runtime_capture_count"] or g["fallback_count"] or g["fatal_error"]:
                issues.append("graph_route_fault")
            if not n["enabled"] or not n["available"] or n["fallback_count"] or n["error_count"]:
                issues.append("native_priority_route_fault")
            bank = api["bank_persistence"]
            b = bank["output"]
            row["bank"] = {k:bank[k] for k in ("capture_attempts", "capture_deferrals", "writes", "write_failures", "writer_active", "last_error")}
            row["bank"].update(output_backend=b.get("backend"), phase_counts={k:{x:v.get(x) for x in ("count", "errors")} for k,v in b.get("totals",{}).items()})
            if bank["write_failures"] or bank["last_error"] or any(v.get("errors") for v in b.get("totals",{}).values()):
                issues.append("bank_persistence_error")
        except (OSError, ValueError, KeyError, TypeError) as error:
            row["API_error"] = f"{type(error).__name__}: {error}"
            issues.append("API_read_failed")
        try:
            with LOG.open("rb") as stream:
                if stream.seek(0,2) < log_offset:
                    issues.append("console_truncated")
                    log_offset, log_pending = 0, b""
                stream.seek(log_offset)
                new = stream.read(1024*1024)
                log_offset += len(new)
            joined = log_pending + new
            cut = joined.rfind(b"\n")
            complete, log_pending = (joined[:cut+1], joined[cut+1:]) if cut >= 0 else (b"", joined)
            for pattern in patterns:
                count = complete.count(pattern.encode())
                counts[pattern] += count
                if count:
                    issues.append("new_console_" + pattern)
            row["log_pattern_counts_since_start"] = dict(counts)
            with CSV.open("rb") as stream:
                if stream.seek(0,2) < csv_offset:
                    issues.append("CSV_truncated")
                    csv_offset, csv_pending = 0, b""
                stream.seek(csv_offset)
                new = stream.read(2*1024*1024)
                csv_offset += len(new)
            joined = csv_pending + new
            cut = joined.rfind(b"\n")
            complete, csv_pending = (joined[:cut+1], joined[cut+1:]) if cut >= 0 else (b"", joined)
            selected = []
            for values in csv.reader(io.StringIO(complete.decode("utf8"))):
                if not values:
                    continue
                if len(values) != len(csv_fields):
                    issues.append("CSV_schema_or_partial_row_error")
                    continue
                item = dict(zip(csv_fields, values))
                dropped = int(item["replay_dropped"])
                if drop_baseline is None:
                    drop_baseline = dropped
                if dropped != drop_baseline:
                    issues.append("CSV_replay_dropped_changed")
                selected.append({k:item[k] for k in ("utc", "steps", "optimized_samples", "learner_frames", "replay_dropped", "loss", "grad_norm")})
                if not math.isfinite(float(item["loss"])):
                    issues.append("CSV_nonfinite_loss")
                if not math.isfinite(float(item["grad_norm"])):
                    notices.append("CSV_sampled_nonfinite_grad_not_automatic_fault")
            if selected:
                row["CSV_health_rows"] = selected
        except (OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
            row["append_read_error"] = f"{type(error).__name__}: {error}"
            issues.append("append_health_read_failed")
        row["offsets"] = dict(console=log_offset, csv=csv_offset)
        if GATE.exists():
            if gate_seen is None:
                gate_seen = now
            row["queued160_gate_observed"] = dict(first_seen_unix_s=gate_seen, stat=identity(GATE))
        row["issues"], row["notices"] = sorted(set(issues)), sorted(set(notices))
        for issue in row["issues"]:
            issues_seen[issue] = issues_seen.get(issue,0) + 1
        for notice in row["notices"]:
            notices_seen[notice] = notices_seen.get(notice,0) + 1
        fresh = set(issues) - last_announced
        if fresh:
            print(json.dumps(dict(alert_utc=row["utc"], health_issues=sorted(fresh))),flush=True)
            last_announced |= fresh
        output.write(json.dumps(row, allow_nan=False) + "\n")
        output.flush()
        rows += 1
        if gate_seen is not None and now >= gate_seen + GATE_TAIL:
            break
        time.sleep(max(0, mono_start + rows*PERIOD - time.monotonic()))

report = dict(schema="robotron-main-coast-to160-health-v1", started_utc=started_utc,
    ended_utc=utc(), elapsed_s=time.monotonic()-mono_start, pid=os.getpid(), main_pid=MAIN,
    supervisor_pid=SUPERVISOR, rows=rows, largest_poll_gap_s=largest_gap, gaps=gaps,
    issues=issues_seen, notices=notices_seen, first_gate_seen_unix_s=gate_seen,
    end_reason="actual_gate_plus120s" if gate_seen is not None else "fixed1445UTC_deadline",
    initial_offsets=initial_offsets, final_offsets=dict(console=log_offset,csv=csv_offset),
    pending_append_bytes=dict(console=len(log_pending),csv=len(csv_pending)),
    source_identity_scope="Startup attested hashes retained; new baseline file stat identities checked every60s, no code hash sweep. Control bytes SHA checked every60s.",
    source_hash_attestation=attested["source_hashes"], expected_source_stats=sources,
    expected_main_start_ticks=initial_owners[MAIN]["start_ticks"],
    actor_pin_path=str(BASE/"actor192-all-connected.json"), actor_pin_count=len(actors),
    scope="Compact main-only coast fault detection, no performance/reliability claim, private quality/game/score/model reads, GPU contexts or process/control writes. Actual160 gate existence/stat only, never inferred saved clocks.")
with COMPLETE.open("x") as out:
    json.dump(report,out,indent=2);out.write("\n")
print(json.dumps(dict(complete_utc=report["ended_utc"],rows=rows,issues=issues_seen,notices=notices_seen,end_reason=report["end_reason"])),flush=True)
