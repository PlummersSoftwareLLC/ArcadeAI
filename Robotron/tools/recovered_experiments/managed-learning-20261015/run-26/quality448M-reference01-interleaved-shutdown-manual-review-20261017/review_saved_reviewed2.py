"""One independent stdlib review of saved R1; never imports/reruns its auditor."""
from pathlib import Path
import collections
import datetime
import hashlib
import json
import math
import os
import re
import statistics

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
D = RUN / "quality448M-reference01-independent-original-row-audit-20261017"
EX = RUN / "quality448M-reference01-original-row-audit-root-execution-20261017"
EXPECTED_AUDIT = "03a20f3b7dd4583332ff52296feaaf7271439756868dff0211c969a2f97858de"


def sha(path):
    path = Path(path)
    assert path.suffix != ".pt", "No tensor/checkpoint bytes permitted"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def unique(rows):
    result = {}
    for row in rows:
        key = row["journal_game_id"]
        assert key not in result
        result[key] = row
    return result


def jsonl(name):
    return [json.loads(line) for line in (D / name).read_text().splitlines() if line.strip()]


audit = read(D / "review-receipt.json")
assert sha(D / "review-receipt.json") == EXPECTED_AUDIT
assert audit["valid"] is False and audit["result"] == "rejected_or_needs_review"
assert audit["error"].startswith("ValueError: Unclassified evaluator log issues require review:")
child = read(EX / "actual-child-completion.json")
assert child["original_pid"] == 184786 and child["original_returncode"] == 2
assert child["original_reaped"] is True and child["no_retry"] is True

# Close the original auditor's not-yet-reached final content-stability checks.
checked = {}
status_path = str(Path(audit["campaign_directory"]) / "status.json")
for original, entry in audit["artifacts"].items():
    copy = D / entry["copy"]
    assert sha(copy) == entry["sha256"], copy
    if original != status_path:
        assert sha(original) == entry["sha256"], original
    checked[original] = dict(entry, current_original_rehashed=original != status_path)
status_before = read(D / "campaign-status-observed.json")
leg_record = [row for row in status_before["legs"] if row["index"] == 1]
assert leg_record == [read(EX / "original-finished-leg.json")]
assert leg_record[0]["state"] == "finished" and leg_record[0]["returncode"] == 0
assert [row for row in read(status_path)["legs"] if row["index"] == 1] == leg_record

plan = read(D / "campaign-plan.json")
receipt = read(D / "receipt.json")
assert sha(D / "campaign-plan.json") == "5bb1778efdd6b29c6ac9f5defa0373da1c2c8bc13e6324e0c2c17d4cfc4164b4"
assert receipt["valid"] is True and receipt["complete"] is True and receipt["active"] is False
assert receipt["cohort"]["valid"] and receipt["cohort"]["complete"] and receipt["cohort"]["closed"]
assert receipt["pending"] == receipt["abandoned"] == receipt["cohort"]["pending"] == receipt["cohort"]["abandoned"] == 0
assert not receipt["server_error"] and not receipt["inference_error"]
assert receipt["cleanup_errors"] == receipt["invalidity_reasons"] == []
assert receipt["source_hashes"] == receipt["ended_source_hashes"] == plan["evaluator_source_hashes"]
source_closure = {}
game = Path("/home/dave/source/repos/ArcadeAI/Robotron")
for group in ("evaluator_source_hashes", "execution_source_hashes"):
    for name, value in plan[group].items():
        path = Path(name) if Path(name).is_absolute() else game / name
        assert sha(path) == value
        source_closure[str(path)] = value
assert len(source_closure) == 15

# Original dictionaries and diagnostics are compared without normalization.
starts = unique(jsonl("measurement_starts.jsonl"))
games = unique(jsonl("games.jsonl"))
close, start = receipt["close_ts"], receipt["start_ts"]
assert math.isclose(close - start, 1200, abs_tol=1e-6)
admitted = {key: row for key, row in starts.items()
            if row["experiment"] == receipt["label"] and start <= row["start_unix_s"] <= close}
original = {key: games[key] for key in admitted}
saved_rows = unique(receipt["rows"])
assert set(original) == set(admitted) == set(saved_rows) == set(receipt["cohort"]["started_ids"])
assert len(original) == receipt["started"] == receipt["count"] == 89
slots = set(range(4096, 4112))
assert {row["client_slot"] for row in original.values()} == slots
clients = collections.defaultdict(set)
for key, row in original.items():
    entry = admitted[key]
    assert row == saved_rows[key] and entry["context"] == row["start_context"]
    for field in ("client_id", "client_slot", "game_uid", "start_utc", "start_unix_s",
                  "start_reason", "known_start", "measurement_active", "measurement_generation", "start_frame"):
        assert entry[field] == row[field]
    for field in ("eligible", "complete", "known_start", "eval_only", "measurement_active"):
        assert row[field] is True
    assert not row["excluded_reason"] and row["first_play_level"] == 1
    context = row["start_context"]
    diag = context["game_boundary_diagnostics"]
    assert diag["schema"] == "robotron-game-boundary-inputs-v1" and diag["journal_start_reason"] == entry["start_reason"]
    assert {"previous_accepted_wire", "current_wire", "classifier_previous", "last_start_frame_before",
            "last_start_frame_after", "recent_start", "classifier_new_game", "classifier_verdict"} <= set(diag)
    assert context["epsilon"] == context["expert_ratio"] == 0 and context["difficulty"] == 5
    assert context["training_steps"] == receipt["clocks"]["training_steps"]
    assert context["optimized_samples"] == receipt["clocks"]["optimized_samples"]
    assert context["learner_frames"] == receipt["clocks"]["learner_frame_count"]
    clients[row["client_slot"]].add(row["client_id"])
assert all(len(values) == 1 for values in clients.values())
assert set.union(*clients.values()) == set(receipt["boundary"]["acknowledged_client_ids"])
scores = [row["score"] for row in original.values()]
stats = dict(count=len(scores), started=len(scores), score_sum=sum(scores), mean=statistics.mean(scores),
             median=statistics.median(scores), sd=statistics.stdev(scores), se=statistics.stdev(scores)/math.sqrt(len(scores)))
for source in (receipt, receipt["cohort"]):
    for key, value in stats.items():
        if key != "score_sum":
            assert math.isclose(source[key], value, rel_tol=1e-12, abs_tol=1e-9)
last_end = max(row["end_unix_s"] for row in original.values())
snapshot = receipt["timeout_snapshot_unix_s"]
assert last_end < snapshot

# Exhaustively partition this exact interleaved tail, not arbitrary tracebacks.
console = (D / "evaluator-console.log").read_text().splitlines()
marker = "Stopping async inference batcher..."
assert console.count(marker) == 1
stop_index = console.index(marker)
assert stop_index == 45
flag = re.compile(r"Traceback|\b\w*(?:Error|Exception)\b|\bfailed\b|\bfallback\b|\bunavailable\b|\bdisconnected\b|param mismatch|\[INGEST\] dropped implausible", re.I)
assert not [(i + 1, line) for i, line in enumerate(console[:stop_index]) if flag.search(line)]
tokens = collections.defaultdict(list)
error_clients = []
path = str(game / "Scripts/dqn/socket_server.py")
prefix = re.compile(r"Client (\d+) error: Inference batcher stopped before completion")
for number, line in enumerate(console[stop_index + 1:], stop_index + 2):
    if not line.strip(): kind = "blank"
    elif line.startswith("Client "):
        matches = list(prefix.finditer(line))
        assert matches and "".join(match.group() for match in matches) == line
        error_clients.extend(int(match[1]) for match in matches)
        kind = "concatenated_stopped_client_messages"
    elif line == "Traceback (most recent call last):": kind = "traceback_header"
    elif line == f'  File "{path}", line 2389, in handle_client': kind = "handle_client_frame"
    elif line == f'  File "{path}", line 995, in infer': kind = "infer_frame"
    elif line.strip() == "mv_idx, fr_idx, is_eps = self.inference_batcher.infer(model_state, epsilon, locked_fire=locked_fire)": kind = "infer_call_source"
    elif line.strip() == "raise RuntimeError(error)": kind = "infer_raise_source"
    elif re.fullmatch(r"[~^]+", line.strip()):
        assert line == console[62]
        kind = "exact_call_caret"
    elif line == "RuntimeError: Inference batcher stopped before completion": kind = "stopped_exception_final"
    else:
        assert number == len(console)
        ending = json.loads(line)
        assert ending["valid"] is True and ending["count"] == 89 and ending["label"] == receipt["label"]
        kind = "final_valid_summary"
    tokens[kind].append(number)
assert len(error_clients) == len(set(error_clients)) == 7 and set(error_clients) <= set.union(*clients.values())
for kind in ("traceback_header", "handle_client_frame", "infer_frame", "infer_call_source",
             "infer_raise_source", "exact_call_caret", "stopped_exception_final"):
    assert len(tokens[kind]) == 7

# All sixteen original actor logs retain one strictly post-shutdown timeout.
timeouts = {}
for slot in sorted(slots):
    text = (D / f"actor-{slot}.log").read_text()
    events = [line for line in text.splitlines() if "[SOCKET ACTION TIMEOUT]" in line]
    assert len(events) == 1
    stamp = int(re.search(r"\bunix_s=(\d+)\b", events[0])[1])
    assert stamp > int(snapshot)
    assert receipt["actor_timeout_logs_before_shutdown"][str(slot)] == receipt["actor_timeout_logs"][str(slot)] == 0
    assert receipt["actor_cleanup_timeout_logs"][str(slot)] == receipt["actor_timeout_logs_after_shutdown"][str(slot)] == 1
    timeouts[str(slot)] = dict(events=1, unix_s=stamp, after_shutdown_s=stamp-snapshot)

for original_path, entry in checked.items():
    assert sha(D / entry["copy"]) == entry["sha256"]
    if original_path != status_path: assert sha(original_path) == entry["sha256"]
assert [row for row in read(status_path)["legs"] if row["index"] == 1] == leg_record
assert all(sha(path) == value for path, value in source_closure.items())
assert sha(D / "review-receipt.json") == EXPECTED_AUDIT

result = dict(schema="robotron-quality448-R1-independent-manual-shutdown-supplement-v1",
    status="PASS_COMPLETED_R1_WITH_NARROW_MANUAL_SHUTDOWN_CLASSIFICATION",
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    original_auditor=dict(path=str(D / "review-receipt.json"), sha256=EXPECTED_AUDIT,
        original_returncode=2, original_valid=False, original_result="rejected_or_needs_review", preserved=True),
    original_child_completion=dict(path=str(EX / "actual-child-completion.json"), sha256=sha(EX / "actual-child-completion.json"), **child),
    report_scope="Completed reference leg only; additive owner/peer manual classification anticipated by frozen auditor; no campaign outcome/gate/publication.",
    source_and_receipt_control_flow=[
        "Exact stopped-before-completion request error is assigned only in InferenceBatcher.stop1063; alternate dispatch string1072 also stop-only.",
        "SocketServer.stop2607-2611 sets runningFalse/shutdown_event before unique stop print and batcher.stop.",
        "handle_client2389→infer995 error prints trace regardless, but2459-2460 sticky-latches before shutdown;1164-1168 retains first inference-only failure.",
        "Sidecar526-528 completes all admitted tails before finally539 cleanup;429 sets shutdown event then430 timestamps; cleanup joins handlers before564 captures server_error/568-571 invalidates errors.",
        "Final valid89 receipt has no server/inference/cleanup/invalidity errors; all89 end timestamps precede shutdown snapshot. This does not claim per-line wall timestamps that the console does not contain."],
    console=dict(path=str(D / "evaluator-console.log"), sha256=sha(D / "evaluator-console.log"), lines=len(console),
        stop_marker_line=46, concatenated_client_ids=error_clients, conserved_trace_count=7,
        exhaustive_token_line_numbers=dict(tokens), unknown_or_foreign_tail_lines=[], before_stop_flagged_lines=[]),
    original_rows=dict(statistics=stats, game_ids=sorted(original), all_original_dictionaries_equal_receipt=True,
        registry_context_equals_start_context=True, diagnostics_preserved=True,
        slot_counts=dict(sorted(collections.Counter(str(row["client_slot"]) for row in original.values()).items())),
        full_tail_games=sum(row["end_unix_s"] > close for row in original.values()),
        maximum_after_close_s=max(0,last_end-close), last_admitted_end_unix_s=last_end,
        shutdown_snapshot_unix_s=snapshot, last_tail_before_snapshot_s=snapshot-last_end),
    timeout_evidence=timeouts, original_artifact_hashes_rechecked=checked, plan_source_closure_rechecked=source_closure,
    manual_classification="Only this exact complete seven-trace interleaving after unique owned stop, clean sticky-latch receipt and all full tails is accepted as intentional batcher shutdown. No generic traceback/error suppression.",
    limitations=["Original auditor exit2/validFalse remains immutable; this supplement does not rerun evaluator/auditor or change sources/criteria/rows.",
        "Frozen auditor passed its receipt/backend/boot/pacing/actor-log/row checks before console classification; this stdlib review independently rejoins89 rows and closes its later immutability checks.",
        "No per-thread traceback pairing or console wall timestamps reconstructed; exhaustive equal component counts and source/receipt control flow support this group classification.",
        "Only selected finished record is compared in evolving campaign status; no Candidate01 scores or current policy values inspected.",
        "No PT/model/replay/tensor bytes, framework/application/helper imports, tests, live API/process/GPU/unit queries, restart/retry or canonical mutation."])
result["review_source"] = dict(path=str(Path(__file__).resolve()), sha256=sha(__file__))
output = HERE / "review-receipt.json"
with output.open("x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n"); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
fd = os.open(HERE, os.O_RDONLY | os.O_DIRECTORY)
try: os.fsync(fd)
finally: os.close(fd)
print(json.dumps(dict(status=result["status"], receipt=str(output), sha256=sha(output))))
