#!/usr/bin/env python3
"""Revalidate a finished four-leg campaign; publish a protected copy only with --publish.

This does not change the learner, learning controls, managed incumbent, or services.
The published metadata retains the fresh reference and both candidate receipts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

try:
    from . import run_quality_campaign as campaign
except ImportError:
    import run_quality_campaign as campaign


def digest(path):
    return campaign.evaluator.sha256(Path(path))


def review(directory):
    """Fail closed on unfinished, stale, changed, or inconsistent evidence."""
    directory = Path(directory).resolve(strict=True)
    paths = {name: directory / f"{name}.json" for name in ("plan", "status", "summary")}
    raw = {name: path.read_bytes() for name, path in paths.items()}
    data = {name: json.loads(value) for name, value in raw.items()}
    plan, status, summary = (data[name] for name in ("plan", "status", "summary"))
    plan_hash = hashlib.sha256(raw["plan"]).hexdigest()
    if (plan["output_directory"] != str(directory)
            or status.get("plan_path") != str(paths["plan"])
            or summary.get("plan_path") != str(paths["plan"])
            or status.get("plan_sha256") != plan_hash
            or summary.get("plan_sha256") != plan_hash):
        raise ValueError("Campaign path or plan hash does not match its receipts")
    if status.get("state") != "finished" or summary.get("stop_signal") is not None:
        raise ValueError("Campaign must finish without interruption before review")
    specs = plan["legs"]
    if (len(specs) != 4 or [row.get("index") for row in specs] != [1, 2, 3, 4]
            or [row.get("role") for row in specs] != list(campaign.ORDER)):
        raise ValueError("Planned legs must have unique indices and exact reference/candidate order")
    if set(plan["checkpoints"]) != {"reference", "candidate"}:
        raise ValueError("Plan must bind exactly the reference and candidate checkpoint identities")
    for role, entry in plan["checkpoints"].items():
        if Path(entry["snapshot"]) != directory / "checkpoints" / f"{role}.pt":
            raise ValueError("Checkpoint snapshot path differs from its planned role")
    records = status["legs"]
    if (len(records) != 4 or [row.get("index") for row in records] != [1, 2, 3, 4]
            or [row.get("role") for row in records] != list(campaign.ORDER)
            or any(row.get("state") != "finished" or row.get("returncode") != 0 for row in records)):
        raise ValueError("All four planned evaluators must finish successfully in order")
    expected_gate = dict(each_candidate_individually=True,
        reference="all games pooled from both fresh reference legs",
        minimum_mean_ratio=1.05, minimum_median_ratio=1.0)
    precommit = plan["precommit"]
    if (precommit.get("candidate_gate") != expected_gate
            or precommit.get("order") != list(campaign.ORDER)
            or precommit.get("min_full_games_per_leg") != 50
            or precommit.get("max_attempts_per_leg") != 1
            or precommit.get("admission_extensions") is not False
            or precommit.get("historical_or_interrupted_receipts_used") is not False
            or precommit.get("include_every_admitted_game") is not True
            or precommit.get("include_full_completion_tail") is not True
            or precommit.get("new_same_length_reference_cohorts") is not True):
        raise ValueError("Campaign does not use the established confirmation criteria")
    campaign.check_precommit(plan)
    evidence = {str(path): hashlib.sha256(raw[name]).hexdigest() for name, path in paths.items()}
    for index, spec in enumerate(specs, 1):
        expected = directory / f"{index:02d}-{spec['role']}" / "receipt.json"
        if (Path(spec["receipt_path"]) != expected
                or Path(spec["job"]["directory"]) != expected.parent
                or spec["job"]["checkpoint"] != plan["checkpoints"][spec["role"]]["snapshot"]):
            raise ValueError("Receipt/job path or checkpoint identity differs from its planned role")
        evidence[str(expected)] = digest(expected)
    report = campaign.assess_campaign(plan, records)
    if (len(report.get("candidate_checks", [])) != 2
            or [row.get("index") for row in report["candidate_checks"]] != [2, 4]):
        raise ValueError("Exactly two independent candidate cohort checks are required")
    if any(summary.get(key) != value for key, value in report.items()):
        raise ValueError("Saved summary differs from independently recomputed original-row assessment")
    if status.get("outcome") != report["outcome"]:
        raise ValueError("Final status and original-row assessment disagree")
    if report["outcome"] not in ("qualified_improvement", "not_improved"):
        raise ValueError("Campaign is incomplete or invalid")
    campaign.check_precommit(plan)
    if any(digest(Path(path)) != value for path, value in evidence.items()):
        raise ValueError("Evidence changed during review")
    return dict(schema="robotron-protected-quality-winner-v1",
        reviewed_utc=datetime.now(timezone.utc).isoformat(), campaign_directory=str(directory),
        plan_sha256=plan_hash, evidence_sha256=evidence,
        checkpoints=plan["checkpoints"], evaluator_source_hashes=plan["evaluator_source_hashes"],
        execution_source_hashes=plan["execution_source_hashes"], boot_assets=plan["boot_assets"],
        assessment=report, scope="Frozen-policy quality qualification only; no live learner rollback or learning-speed claim.")


def _fsync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(directory, destination, label):
    """Create new immutable files without replacing any prior protected policy."""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", label) is None:
        raise ValueError("Label must be a simple filename component")
    audited = review(directory)
    if not audited["assessment"]["qualified_improvement"]:
        raise ValueError("Both candidate cohorts must qualify independently before publication")
    destination = Path(destination).resolve(strict=True)
    final = destination / f"{label}.pt"
    metadata = final.with_suffix(".pt.json")
    if final.exists() or metadata.exists():
        raise FileExistsError("Protected checkpoint or metadata already exists; never overwrite")
    entry = audited["checkpoints"]["candidate"]
    partials = []
    try:
        fd, name = tempfile.mkstemp(prefix=f".{label}.", suffix=".partial", dir=destination)
        partials.append(Path(name))
        with os.fdopen(fd, "wb") as output, Path(entry["snapshot"]).open("rb") as source:
            shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        if digest(name) != entry["sha256"]:
            raise ValueError("Protected copy does not match the precommitted candidate")
        # Revalidate all receipts and source identities after copying, before publishing.
        after = review(directory)
        if (after["evidence_sha256"] != audited["evidence_sha256"]
                or after["checkpoints"] != audited["checkpoints"]):
            raise ValueError("Campaign evidence changed while copying the winner")
        audited.update(published_utc=datetime.now(timezone.utc).isoformat(),
            protected_checkpoint=str(final), checkpoint_sha256=entry["sha256"],
            managed_incumbent_updated=False, live_learner_restored=False)
        fd, meta_name = tempfile.mkstemp(prefix=f".{label}.", suffix=".partial", dir=destination)
        partials.append(Path(meta_name))
        with os.fdopen(fd, "w") as stream:
            json.dump(audited, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        for path in partials:
            path.chmod(0o444)
        # Hard links publish exclusively and atomically on the destination filesystem.
        # If metadata publication fails, retain the checkpoint as an unpromoted orphan.
        os.link(name, final)
        _fsync_directory(destination)
        os.link(meta_name, metadata)
        _fsync_directory(destination)
    finally:
        for path in partials:
            path.unlink(missing_ok=True)
    return audited


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--label")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args(argv)
    if args.publish and (args.destination is None or args.label is None):
        parser.error("--publish requires --destination and --label")
    result = publish(args.campaign_dir, args.destination, args.label) if args.publish else review(args.campaign_dir)
    print(json.dumps(dict(outcome=result["assessment"]["outcome"],
        candidate_checks=result["assessment"]["candidate_checks"],
        pooled_reference=result["assessment"]["pooled_reference"],
        protected_checkpoint=result.get("protected_checkpoint"),
        managed_incumbent_updated=False), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
