"""Independent stdlib-only arithmetic over completed legs 1, 2, 3 only.

No current campaign status or leg4 input is opened. Writes create-only review
evidence beside this file; no framework/helper or model/replay data is imported.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics


OUT = Path(__file__).resolve().parent
RUN = OUT.parent
ROOT = RUN.parent
CAMPAIGN = ROOT / "quality-256M-vs-320M-20261017"
PLAN_SHA = "c25042bbe74dd85da10911e3f0acec24925109871b23eced629ac2a5b9389a10"
SLOTS = set(range(4096, 4112))
LEGS = (
    (1, "reference", 95, "quality320M-reference01-independent-original-row-audit-reviewed2-20261017", "addfbdb20c6f5d9905c52e63cfca2594695b0266e9de8022c849df6630cd5f1d"),
    (2, "candidate", 92, "quality320M-candidate01-independent-original-row-audit-reviewed2-20261017", "f098af5ce7444f4f3e4622b80ca73f28e0f6977326420f34aaf863535c5d9cc8"),
    (3, "reference", 93, "quality320M-reference02-independent-original-row-audit-reviewed2-20261017", "eafdeb12c0245d2ca18f14ad8ea3bdba0c9f083bb2bc3b7928620002981d2777"),
)
READS = {}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    READS[str(path)] = digest(raw)
    return raw


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def json_lines(raw):
    require(raw.endswith(b"\n"), "partial JSONL")
    return [decode(line) for line in raw.splitlines()]


def by_id(rows):
    result = {}
    for row in rows:
        key = row["journal_game_id"]
        require(isinstance(key, str) and key and key not in result, "missing/duplicate game ID")
        result[key] = row
    return result


def summaries(rows):
    scores = [row["score"] for row in rows]
    require(all(type(score) is int and score >= 0 for score in scores), "invalid score")
    return dict(count=len(scores), score_sum=sum(scores), mean=statistics.mean(scores),
                median=statistics.median(scores), sd=statistics.stdev(scores),
                se=statistics.stdev(scores) / math.sqrt(len(scores)))


def near(a, b):
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)


def inspect_leg(plan, index, role, expected_count, audit_name, audit_sha):
    directory = CAMPAIGN / f"{index:02d}-{role}"
    archive = RUN / audit_name
    review_raw = read(archive / "review-receipt.json")
    require(digest(review_raw) == audit_sha, "prior audit changed")
    review = decode(review_raw)
    require(review["valid"] is True and review["result"] == "valid_completed_leg"
            and review["leg"] == index and review["role"] == role
            and review["plan_sha256"] == PLAN_SHA, "completed audit identity")
    payload = {}
    for name in ("receipt.json", "games.jsonl", "measurement_starts.jsonl"):
        original_path = directory / name if name == "receipt.json" else directory / "journal" / name
        original = read(original_path)
        copied = read(archive / name)
        require(original == copied, "original/archive differ")
        require(digest(original) == review["artifacts"][str(original_path)]["sha256"], "prior artifact binding")
        payload[name] = original
    receipt = decode(payload["receipt.json"])
    require(digest(payload["receipt.json"]) == review["receipt_sha256"], "receipt digest")
    require(receipt["valid"] is True and receipt["complete"] is True
            and receipt["active"] is False and receipt["pending"] == 0
            and not receipt["server_error"] and not receipt["inference_error"]
            and receipt["cleanup_errors"] == [], "completed clean receipt")
    spec = plan["legs"][index - 1]
    require(spec["index"] == index and spec["role"] == role and receipt["job"] == spec["job"], "planned job")
    require(receipt["checkpoint_sha256"] == plan["checkpoints"][role]["sha256"], "role checkpoint")
    require(receipt["source_hashes"] == receipt["ended_source_hashes"] == plan["evaluator_source_hashes"], "frozen evaluator sources")
    require(receipt["boot_assets"] == plan["boot_assets"], "boot snapshot")
    require(not any(receipt["actor_timeout_logs"].values()), "runtime actor timeout")
    require(set(map(int, receipt["actor_timeout_logs"])) == SLOTS, "timeout slots")
    require(near(receipt["close_ts"] - receipt["start_ts"], spec["job"]["cohort_s"]), "admission duration")
    starts = by_id(json_lines(payload["measurement_starts.jsonl"]))
    journal = by_id(json_lines(payload["games.jsonl"]))
    admitted = {key: row for key, row in starts.items()
                if row["experiment"] == receipt["label"]
                and receipt["start_ts"] <= row["start_unix_s"] <= receipt["close_ts"]}
    outcomes = {key: journal[key] for key in admitted if key in journal}
    receipt_rows = by_id(receipt["rows"])
    require(len(admitted) == len(outcomes) == len(receipt_rows) == expected_count, "all admitted full tails")
    require(expected_count >= plan["precommit"]["min_full_games_per_leg"], "minimum full games")
    require(outcomes == receipt_rows == by_id(receipt["cohort"]["rows"]), "all original dictionaries unchanged")
    require(set(admitted) == set(receipt["cohort"]["started_ids"]), "independent admission coverage")
    slot_counts = {slot: sum(row["client_slot"] == slot for row in outcomes.values()) for slot in sorted(SLOTS)}
    require({row["client_slot"] for row in outcomes.values()} == SLOTS and all(slot_counts.values()), "all16 slot coverage")
    for key, entry in admitted.items():
        row = outcomes[key]
        require(entry["known_start"] is True and entry["measurement_active"] is True, "known measured admission")
        require(row["eligible"] is True and row["complete"] is True and row["excluded_reason"] == "", "eligible full original outcome")
        for field in ("client_id", "client_slot", "game_uid", "start_utc", "start_unix_s", "start_reason", "known_start", "measurement_active", "measurement_generation", "start_frame"):
            require(entry[field] == row[field], "admission/outcome identity")
        require(entry["context"] == row["start_context"], "same start context")
        for context in (row["start_context"], row["end_context"]):
            require(context["epsilon"] == context["expert_ratio"] == 0 and context["difficulty"] == 5, "greedy difficulty5")
            for field, clock in (("training_steps", "training_steps"), ("optimized_samples", "optimized_samples"), ("learner_frames", "learner_frame_count")):
                require(context[field] == receipt["clocks"][clock], "frozen row clocks")
    rows = list(outcomes.values())
    stats = summaries(rows)
    for field in ("count", "mean", "median", "sd", "se"):
        require(near(stats[field], receipt[field]) and near(stats[field], receipt["cohort"][field]), "raw statistics")
    require(stats == {key: review["statistics"][key] for key in stats}, "prior independent statistics")
    tail = dict(games=sum(row["end_unix_s"] > receipt["close_ts"] for row in rows),
                maximum_after_close_s=max(0, max(row["end_unix_s"] for row in rows) - receipt["close_ts"]))
    require(tail == review["completion_tail"], "full completion tail")
    require(receipt["timeout_snapshot_unix_s"] >= max(row["end_unix_s"] for row in rows), "cleanup after full tails")
    signature = {key: receipt[key] for key in ("numeric_policy", "runtime", "source_hashes", "ended_source_hashes", "engine_version", "state_size", "single_frame_state_size", "frame_stack", "wire_params_count", "wire_version", "frame_protocol", "inference_backend")}
    signature.update(job={key: value for key, value in receipt["job"].items() if key not in ("checkpoint", "directory", "label")},
                     boot_identity=receipt["boot_assets"]["identity"], pacing_sha256=receipt["socket_wait"]["sha256"])
    return rows, signature, dict(index=index, role=role, label=receipt["label"], checkpoint_sha256=receipt["checkpoint_sha256"],
                                prior_audit_sha256=audit_sha, receipt_sha256=review["receipt_sha256"],
                                statistics=stats, completion_tail=tail, slot_counts=slot_counts,
                                original_game_ids=sorted(outcomes), scores=[row["score"] for row in rows])


def main():
    plan_raw = read(CAMPAIGN / "plan.json")
    require(digest(plan_raw) == PLAN_SHA, "campaign plan changed")
    plan = decode(plan_raw)
    require([row["role"] for row in plan["legs"]] == ["reference", "candidate", "reference", "candidate"], "precommitted order")
    gate = plan["precommit"]["candidate_gate"]
    require(gate == dict(each_candidate_individually=True, reference="all games pooled from both fresh reference legs", minimum_mean_ratio=1.05, minimum_median_ratio=1.0), "unchanged separate candidate gates")
    require(plan["precommit"]["include_every_admitted_game"] and plan["precommit"]["include_full_completion_tail"]
            and plan["precommit"]["max_attempts_per_leg"] == 1 and not plan["precommit"]["admission_extensions"], "fixed admission/tail protocol")
    results = [inspect_leg(plan, *leg) for leg in LEGS]
    require(all(result[1] == results[0][1] for result in results), "crossleg backend/runtime/numeric/protocol/source/job mismatch")
    ids = [set(row["journal_game_id"] for row in result[0]) for result in results]
    require(all(not ids[i] & ids[j] for i in range(3) for j in range(i)), "crossleg game overlap")
    references = results[0][0] + results[2][0]
    pooled = summaries(references)
    candidate = summaries(results[1][0])
    required_mean = pooled["mean"] * gate["minimum_mean_ratio"]
    required_median = pooled["median"] * gate["minimum_median_ratio"]
    report = dict(schema="robotron-independent-completed-reference-candidate01-gate-review-v1", result="PASS",
                  reviewed_utc=datetime.now(timezone.utc).isoformat(), plan_sha256=PLAN_SHA,
                  scope="Completed legs1,2,3 original admissions/outcomes/receipts only; no Candidate02, campaign status, runtime or model tensors read.",
                  formal_four_leg_campaign_outcome="incomplete_not_assessed_by_this_review",
                  candidate02_results_read=False, crossleg_signature_equal=True,
                  source_signature=results[0][1], legs=[result[2] for result in results],
                  pooled_fresh_references=pooled,
                  pooled_reference_median_method="statistics.median of all188 original scores, not median of leg medians",
                  candidate01=dict(statistics=candidate, mean_ratio=candidate["mean"] / pooled["mean"],
                                   required_mean=required_mean, required_median=required_median,
                                   mean_gate=candidate["mean"] >= required_mean,
                                   median_gate=candidate["median"] >= required_median,
                                   separate_cohort_qualifies=candidate["mean"] >= required_mean and candidate["median"] >= required_median),
                  implications=["Candidate01 fails both separate precommitted gates.",
                                "Candidate02 cannot replace or pool away a failed Candidate01 requirement.",
                                "The unchanged full four-leg protocol must still finish; no retry, shortened tail or publication is authorized by this review."],
                  limitations=plan["limitations"], input_sha256=dict(READS),
                  review_source_sha256=digest(Path(__file__).read_bytes()))
    require(pooled["count"] == 188 and pooled["score_sum"] == 67730950, "independent reference total discrepancy")
    require(not report["candidate01"]["mean_gate"] and not report["candidate01"]["median_gate"], "independent gate discrepancy")
    require(all(digest(Path(path).read_bytes()) == expected for path, expected in READS.items()), "archived input changed while read")
    destination = OUT / "review-receipt.json"
    raw = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    Path(__file__).chmod(0o444)
    with Path(__file__).open("rb") as stream:
        os.fsync(stream.fileno())
    descriptor = os.open(OUT, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    print(json.dumps(dict(result=report["result"], pooled=pooled, candidate01=report["candidate01"],
                          receipt=str(destination), sha256=digest(raw))))


if __name__ == "__main__":
    main()
