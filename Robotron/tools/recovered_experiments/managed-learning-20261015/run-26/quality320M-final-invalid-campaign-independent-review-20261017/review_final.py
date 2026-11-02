"""Read-only stdlib final audit; archive only into this new review directory.

No evaluator/valid-leg auditor is invoked for failed leg4. No model import,
runtime/service/proc/API action, publication, replay read or retry is performed.
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
BASE = RUN.parent
CAMPAIGN = BASE / "quality-256M-vs-320M-20261017"
GAME = BASE.parents[1]
PLAN_SHA = "c25042bbe74dd85da10911e3f0acec24925109871b23eced629ac2a5b9389a10"
GATE_REVIEW_SHA = "9b6e347e6303db64f03988c8194b7156e84c47032c0c0466352170887010cf1f"
PROTECTED_SHA = "4f0ef22962aa51bd900be6e89d866b7df828a7eb58fa17dfd574aa32d4267b11"
READS = {}
COPIES = {}
ARCHIVED_BYTES = 0


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    path = Path(path)
    require(path.stat().st_size <= 8 * 1024**2, "Metadata input exceeds bounded8MiB")
    raw = path.read_bytes()
    require(len(raw) <= 8 * 1024**2, "Metadata input grew beyond budget")
    READS[str(path)] = digest(raw)
    return raw


def seal(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def capture(path, name):
    global ARCHIVED_BYTES
    raw = read(path)
    require(ARCHIVED_BYTES + len(raw) <= 16 * 1024**2, "Archive exceeds bounded16MiB")
    seal(OUT / name, raw)
    ARCHIVED_BYTES += len(raw)
    COPIES[str(path)] = dict(copy=name, sha256=digest(raw), bytes=len(raw))
    return raw


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def main():
    plan_raw = capture(CAMPAIGN / "plan.json", "campaign-plan.json")
    require(digest(plan_raw) == PLAN_SHA, "plan changed")
    plan = decode(plan_raw)
    status = decode(capture(CAMPAIGN / "status.json", "campaign-final-status.json"))
    summary = decode(capture(CAMPAIGN / "summary.json", "campaign-final-summary.json"))
    require(status["plan_sha256"] == summary["plan_sha256"] == PLAN_SHA, "final plan binding")
    require(status["state"] == "finished" and status["outcome"] == summary["outcome"] == "incomplete", "exact final outcome")
    require(summary["qualified_improvement"] is False and summary["stop_signal"] is None, "no qualification/interruption claim")
    require(status["reason"] == summary["reason"] == "All four planned legs must complete", "incomplete reason")
    require([row["index"] for row in status["legs"]] == [1, 2, 3, 4]
            and [row["role"] for row in status["legs"]] == ["reference", "candidate", "reference", "candidate"]
            and [row["returncode"] for row in status["legs"]] == [0, 0, 0, 1]
            and all(row["state"] == "finished" for row in status["legs"]), "terminal records and exits")
    require([row["valid"] for row in summary["legs"]] == [True, True, True, False], "three valid legs and one unusable")
    require("pooled_reference" not in summary and "candidate_checks" not in summary, "do not manufacture valid-four summary")
    require(summary["gate"] == plan["precommit"]["candidate_gate"], "fixed separate-candidate gate")
    receipts, legs, signatures = [], [], []
    for spec, record, saved in zip(plan["legs"], status["legs"], summary["legs"]):
        index, role = spec["index"], spec["role"]
        directory = CAMPAIGN / f"{index:02d}-{role}"
        require(Path(spec["receipt_path"]) == directory / "receipt.json"
                and record["receipt_path"] == saved["receipt_path"] == spec["receipt_path"]
                and saved["returncode"] == record["returncode"], "receipt/exit identity")
        raw = capture(directory / "receipt.json", f"leg{index}-original-receipt.json")
        receipt = decode(raw)
        receipts.append(receipt)
        require(receipt["checkpoint_sha256"] == plan["checkpoints"][role]["sha256"], "checkpoint role identity")
        require(receipt["job"] == spec["job"], "fixed job identity")
        require(receipt["source_hashes"] == receipt["ended_source_hashes"] == plan["evaluator_source_hashes"], "source freeze")
        require(receipt["boot_assets"] == plan["boot_assets"], "fixed boot")
        signatures.append({key: receipt[key] for key in ("numeric_policy", "runtime", "source_hashes", "ended_source_hashes", "engine_version", "state_size", "single_frame_state_size", "frame_stack", "wire_params_count", "wire_version", "frame_protocol", "inference_backend")})
        signatures[-1].update(pacing_sha256=receipt["socket_wait"]["sha256"], boot_identity=receipt["boot_assets"]["identity"],
                             job={key: value for key, value in receipt["job"].items() if key not in ("checkpoint", "directory", "label")})
        if index < 4:
            require(receipt["valid"] is True and receipt["complete"] is True and receipt["cohort"]["complete"] is True, "valid full cohort")
            require(digest(raw) == saved["receipt_sha256"] and len(receipt["rows"]) == saved["summary"]["count"], "summary receipt/count")
            require({row["journal_game_id"] for row in receipt["rows"]} == set(saved["included_game_ids"]), "all original summary rows")
            scores = [row["score"] for row in receipt["rows"]]
            require(statistics.mean(scores) == saved["summary"]["mean"] and statistics.median(scores) == saved["summary"]["median"], "original summary statistics")
        legs.append(dict(index=index, role=role, returncode=record["returncode"], receipt_sha256=digest(raw),
                         valid=receipt["valid"], complete_flag=receipt["complete"], cohort_complete=receipt["cohort"]["complete"],
                         reason=receipt["reason"], full_rows=receipt["count"], admitted=receipt["started"],
                         pending=receipt["pending"], abandoned=receipt.get("abandoned")))
    require(all(signature == signatures[0] for signature in signatures), "recorded frozen backend/protocol mismatch")
    failed = receipts[3]
    require(failed["valid"] is False and failed["complete"] is True and failed["active"] is False
            and failed["cohort"]["complete"] is False and failed["reason"] == "abandoned_cohort_game"
            and failed["invalidity_reasons"] == ["abandoned_cohort_game"]
            and (failed["count"], failed["started"], failed["pending"], failed["abandoned"]) == (69, 81, 11, 1), "preserve original failed cohort")
    require(failed["count"] + failed["pending"] + failed["abandoned"] == failed["started"], "failed cohort partition")
    require(summary["legs"][3]["error"] == "Frozen cohort has not completed", "source-defined incomplete classification")
    for name in ("games.jsonl", "measurement_starts.jsonl", "lives.jsonl"):
        capture(CAMPAIGN / "04-candidate/journal" / name, "failed-leg4-" + name)
    capture(CAMPAIGN / "04-candidate/status.json", "failed-leg4-status.json")
    capture(CAMPAIGN / "04-candidate.console.log", "failed-leg4-evaluator-console.log")
    for slot in range(4096, 4112):
        capture(CAMPAIGN / "04-candidate/actors" / str(slot) / "console.log", f"failed-leg4-actor-{slot}.log")
    prior_path = RUN / "quality320M-completed-reference-and-candidate01-gate-review-20261017/review-receipt.json"
    prior_raw = capture(prior_path, "prior-completed-reference-candidate01-gate-review.json")
    require(digest(prior_raw) == GATE_REVIEW_SHA, "earlier three-leg independent review changed")
    prior = decode(prior_raw)
    for path, expected in prior["input_sha256"].items():
        require(digest(read(path)) == expected, "earlier valid-leg original/archive binding changed")
    reference_scores = [row["score"] for index in (0, 2) for row in receipts[index]["rows"]]
    reference_mean, reference_median = statistics.mean(reference_scores), statistics.median(reference_scores)
    candidate_scores = [row["score"] for row in receipts[1]["rows"]]
    candidate_mean, candidate_median = statistics.mean(candidate_scores), statistics.median(candidate_scores)
    require(len(reference_scores) == 188 and sum(reference_scores) == 67730950, "valid original references")
    require(reference_mean == prior["pooled_fresh_references"]["mean"] and reference_median == prior["pooled_fresh_references"]["median"], "fresh-reference arithmetic unchanged")
    require(candidate_mean < reference_mean * 1.05 and candidate_median < reference_median, "Candidate01 both gates remain false")
    runner_path = GAME / "tools/run_quality_campaign.py"
    runner_raw = capture(runner_path, "frozen-campaign-runner-source.py")
    require(digest(runner_raw) == plan["execution_source_hashes"][str(runner_path)], "runner source binding")
    protected = Path(plan["checkpoints"]["reference"]["source"])
    protected_metadata = decode(capture(protected.with_suffix(protected.suffix + ".json"), "protected256-original-provenance.json"))
    before = protected.stat()
    with protected.open("rb") as stream:
        protected_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    after = protected.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "protected file changed while hashing")
    require(protected_sha == PROTECTED_SHA == plan["checkpoints"]["reference"]["sha256"] == protected_metadata["checkpoint_sha256"], "protected256 bytes intact")
    require(protected_metadata["protected_checkpoint"] == str(protected), "protected provenance path")
    require(all(digest(Path(path).read_bytes()) == expected for path, expected in READS.items()), "input changed during review")
    report = dict(schema="robotron-final-incomplete-quality-campaign-independent-review-v1", review_result="PASS",
                  reviewed_utc=datetime.now(timezone.utc).isoformat(), plan_sha256=PLAN_SHA,
                  recorded_campaign_outcome="incomplete", qualified_improvement=False,
                  independently_usable_cohorts=3, valid_four_cohort_comparison=False, leg_records=legs,
                  failed_candidate02=dict(reason=failed["reason"], invalidity_reasons=failed["invalidity_reasons"],
                      diagnostic_only=dict(completed=69, admitted=81, pending=11, abandoned=1),
                      scoring_or_valid_leg_auditor_applied=False, rows_excluded_from_qualification=True,
                      no_retry_extension_or_substitution=True),
                  completed_candidate01=dict(reference_count=188, reference_score_sum=sum(reference_scores),
                      reference_mean=reference_mean, reference_median=reference_median,
                      required_mean=reference_mean * 1.05, candidate_mean=candidate_mean,
                      candidate_median=candidate_median, mean_gate=False, median_gate=False,
                      scope="Valid completed cohort diagnostic; not a manufactured valid-four outcome."),
                  protected256=dict(path=str(protected), sha256=protected_sha, bytes=after.st_size,
                      identity_verified_by="streaming SHA256 and existing protected provenance; no tensor/model import",
                      remains_preserved=True),
                  source_interpretation=dict(runner_sha256=digest(runner_raw),
                      incomplete_before_backend_validation="load_leg raises IncompleteLeg when receipt.cohort.complete is false, before validate_backend",
                      summary_early_return="assess_campaign leaves outcome incomplete for any missing/incomplete cohort and does not calculate candidate_checks",
                      failed_controller_return="run_campaign returns1 for incomplete/invalid; original service/process exit is root-observed, not queried by this review"),
                  recorded_backend_source_numeric_protocol_equal_all4=True,
                  partial_candidate02_scores_used=False, publication_or_state_changes=False,
                  limitations=["Abandonment is an observed validity failure; underlying actor/game cause is not established here.",
                               "No valid fourth cohort, qualified model, not_improved four-leg result or learning-speed claim is synthesized.",
                               "No runtime/process/service cleanup claim is independently made; root owns those checks.",
                               "Both fresh reference cohorts and Candidate01 retain their original successful audits; the invalid fourth receipt remains preserved."],
                  artifacts=COPIES, input_sha256=READS, archived_bytes=ARCHIVED_BYTES,
                  review_source_sha256=digest(Path(__file__).read_bytes()))
    seal(OUT / "review-receipt.json", (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())
    Path(__file__).chmod(0o444)
    with Path(__file__).open("rb") as stream:
        os.fsync(stream.fileno())
    descriptor = os.open(OUT, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    print(json.dumps(dict(review_result="PASS", campaign_outcome="incomplete", qualified_improvement=False,
                          protected256_sha256=protected_sha, artifacts=len(COPIES), archived_bytes=ARCHIVED_BYTES,
                          receipt=str(OUT / "review-receipt.json"), sha256=digest((OUT / "review-receipt.json").read_bytes()))))


if __name__ == "__main__":
    main()
