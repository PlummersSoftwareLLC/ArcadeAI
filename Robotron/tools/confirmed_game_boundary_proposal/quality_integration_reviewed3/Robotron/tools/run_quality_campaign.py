#!/usr/bin/env python3
"""Precommit and run four fresh frozen cohorts: reference, candidate, reference, candidate.

Without --launch, print a plan without creating files or processes. A launched
campaign never resumes, retries, extends admission, changes learning, or promotes
checkpoints. Run it under an external durable supervisor such as systemd-run;
this program does not create or change services. Stop the runner with SIGTERM or
SIGINT: it forwards SIGINT to its owned evaluator and waits for private cleanup.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import statistics
import subprocess
import sys
import time

try:
    from . import run_frozen_sidecar as evaluator
    from .compare_frozen_measurements import summarize
    from .compare_sidecar_measurements import JOB_FIELDS, validate_backend
except ImportError:
    import run_frozen_sidecar as evaluator
    from compare_frozen_measurements import summarize
    from compare_sidecar_measurements import JOB_FIELDS, validate_backend


GPU0_UUID = "GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0"
BOOT_ASSETS = evaluator.GAME / "logs/managed-learning-20261015/sidecar-boot-assets-v1"
ORDER = ("reference", "candidate", "reference", "candidate")
LIMITATIONS = (
    "Sequential R/C/R/C cohorts share an evolving host environment; they are not simultaneous controls.",
    "Private initialized boot assets, greedy play, and fixed slots do not establish independent emulator RNG streams.",
    "The 5% mean and median gates are precommitted descriptive qualification rules, not statistical confidence or proof of a plateau breakthrough.",
    "This campaign measures frozen-policy quality, not learning speed; training continues independently.",
    "Repeated policy selection and shared actor/game histories are not corrected. Qualification does not change the incumbent or learning settings.",
)


class IncompleteLeg(ValueError):
    """A receipt was written before its frozen cohort completed."""


@dataclass(frozen=True)
class Campaign:
    reference: Path
    candidate: Path
    directory: Path
    reference_label: str = "reference"
    candidate_label: str = "candidate"
    gpu_uuid: str = GPU0_UUID
    boot_assets: Path = BOOT_ASSETS
    port: int = 9999
    cohort_s: float = 1200
    timeout_s: float = 2400
    mame: Path = Path("/usr/games/mame")
    rompath: Path = evaluator.GAME / "roms"
    hypothesis: str = "The candidate checkpoint improves greedy, full-game score over the protected reference."
    game_boundary_diagnostics: bool = True

    def jobs(self):
        counts = Counter()
        jobs = []
        for index, role in enumerate(ORDER, 1):
            counts[role] += 1
            label = f"{getattr(self, role + '_label')}-{counts[role]:02d}"
            directory = self.directory / f"{index:02d}-{role}"
            checkpoint = self.directory / "checkpoints" / f"{role}.pt"
            jobs.append((role, evaluator.Job(checkpoint, directory, label, "cuda",
                self.gpu_uuid, self.port, self.cohort_s, self.timeout_s, 1000,
                self.mame, self.rompath, 2, self.boot_assets, "inductor",
                game_boundary_diagnostics=self.game_boundary_diagnostics)))
        return jobs

    def validate(self):
        if self.directory != self.directory.resolve() or self.directory.exists():
            raise ValueError("Campaign output must be a new, absolute, resolved directory")
        if self.reference_label == self.candidate_label:
            raise ValueError("Reference and candidate labels must differ")
        if not self.hypothesis.strip():
            raise ValueError("A precommitted hypothesis is required")
        for role, job in self.jobs():
            # Validate real source files before campaign snapshots exist.
            replace(job, checkpoint=getattr(self, role)).validate(require_boot_assets=True)


def command(job):
    argv = [sys.executable, "-Xgil=0", "-B", "-u", str(Path(evaluator.__file__).resolve()),
        "--checkpoint", str(job.checkpoint), "--job-dir", str(job.directory),
        "--label", job.label, "--device", "cuda", "--gpu-uuid", job.gpu_uuid,
        "--inference-backend", "inductor", "--port", str(job.port),
        "--cohort-s", str(job.cohort_s), "--timeout-s", str(job.timeout_s),
        "--wait-us", str(job.wait_us), "--cpu-threads", str(job.cpu_threads),
        "--mame", str(job.mame), "--rompath", str(job.rompath),
        "--boot-assets", str(job.boot_assets), "--launch"]
    if job.game_boundary_diagnostics:
        argv.append("--game-boundary-diagnostics")
    return argv


def execution_sources():
    paths = [Path(__file__).resolve(), Path(evaluator.__file__).resolve(),
             Path(__file__).with_name("compare_sidecar_measurements.py"),
             Path(__file__).with_name("compare_frozen_measurements.py")]
    return {str(path): evaluator.sha256(path) for path in paths}


def make_plan(campaign):
    campaign.validate()
    checkpoints = {role: dict(source=str(getattr(campaign, role)),
        snapshot=str(campaign.directory / "checkpoints" / f"{role}.pt"),
        sha256=evaluator.sha256(getattr(campaign, role)))
        for role in ("reference", "candidate")}
    return dict(schema_version=1, output_directory=str(campaign.directory),
        created_unix_s=time.time(), hypothesis=campaign.hypothesis,
        precommit=dict(order=list(ORDER), new_same_length_reference_cohorts=True,
            historical_or_interrupted_receipts_used=False, min_full_games_per_leg=50,
            all_actor_slots=list(evaluator.SLOTS), include_every_admitted_game=True,
            include_full_completion_tail=True, max_attempts_per_leg=1,
            admission_extensions=False, automatic_promotion=False,
            automatic_rollback=False, learning_changes=False,
            candidate_gate=dict(each_candidate_individually=True,
                reference="all games pooled from both fresh reference legs",
                minimum_mean_ratio=1.05, minimum_median_ratio=1.0)),
        checkpoints=checkpoints, boot_assets=evaluator.boot_module().load_snapshot(campaign.boot_assets),
        evaluator_source_hashes=evaluator.source_hashes(), execution_source_hashes=execution_sources(),
        legs=[dict(index=index, role=role, job=job.plan(), command=command(job),
            console_log=str(campaign.directory / f"{index:02d}-{role}.console.log"),
            receipt_path=str(job.directory / "receipt.json"),
            evaluator_status_path=str(job.directory / "status.json"))
            for index, (role, job) in enumerate(campaign.jobs(), 1)],
        limitations=list(LIMITATIONS))


def write_immutable(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    Path(path).chmod(0o444)


def snapshot_checkpoints(plan):
    directory = Path(plan["output_directory"]) / "checkpoints"
    directory.mkdir()
    for entry in plan["checkpoints"].values():
        source, snapshot = Path(entry["source"]), Path(entry["snapshot"])
        if evaluator.sha256(source) != entry["sha256"]:
            raise ValueError("Source checkpoint changed after precommit")
        with source.open("rb") as input_stream, snapshot.open("xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        snapshot.chmod(0o444)
        if (evaluator.sha256(snapshot) != entry["sha256"]
                or evaluator.sha256(source) != entry["sha256"]):
            raise ValueError("Checkpoint changed while making the campaign snapshot")


def check_precommit(plan):
    if execution_sources() != plan["execution_source_hashes"]:
        raise ValueError("Campaign/evaluator/comparison source changed after precommit")
    if evaluator.source_hashes() != plan["evaluator_source_hashes"]:
        raise ValueError("Evaluation source changed after precommit")
    boot_path = plan["legs"][0]["job"]["boot_assets"]
    if evaluator.boot_module().load_snapshot(boot_path) != plan["boot_assets"]:
        raise ValueError("Boot assets changed after precommit")
    for entry in plan["checkpoints"].values():
        if evaluator.sha256(entry["snapshot"]) != entry["sha256"]:
            raise ValueError("Campaign checkpoint snapshot changed after precommit")


def load_leg(spec, plan, *, verify_checkpoint=True):
    path = Path(spec["receipt_path"])
    raw = path.read_bytes()
    receipt = json.loads(raw)
    if isinstance(receipt, dict) and (receipt.get("complete") is not True
            or receipt.get("active", False) is not False
            or isinstance(receipt.get("cohort"), dict) and receipt["cohort"].get("complete", True) is not True):
        raise IncompleteLeg("Frozen cohort has not completed")
    leg = validate_backend(receipt, verify_checkpoint=verify_checkpoint)
    expected = spec["job"]
    if any(receipt["job"].get(field) != expected.get(field)
           for field in (*JOB_FIELDS, "label", "directory", "checkpoint")):
        raise ValueError("Receipt does not match its precommitted job")
    # Missing historical fields mean the original default OFF. New plans and
    # receipts always carry an explicit bool, checked separately from scoring.
    boundary_flag = receipt["job"].get("game_boundary_diagnostics", False)
    if (type(boundary_flag) is not bool
            or boundary_flag != expected.get("game_boundary_diagnostics", False)):
        raise ValueError("Boundary diagnostics differs from the precommitted job")
    if receipt["label"] != expected["label"]:
        raise ValueError("Receipt label does not match its precommitted label")
    if receipt["checkpoint_sha256"] != plan["checkpoints"][spec["role"]]["sha256"]:
        raise ValueError("Receipt checkpoint does not match its precommitted hash")
    if receipt["source_hashes"] != plan["evaluator_source_hashes"]:
        raise ValueError("Receipt source hashes differ from precommit")
    if receipt["boot_assets"] != plan["boot_assets"]:
        raise ValueError("Receipt boot snapshot differs from precommit")
    if (leg["expected_actor_slots"] != list(evaluator.SLOTS)
            or {row["client_slot"] for row in leg["rows"]} != set(evaluator.SLOTS)):
        raise ValueError("Every one of the 16 precommitted slots must contribute full games")
    return receipt, leg, hashlib.sha256(raw).hexdigest()


def assess_campaign(plan, records, *, verify_checkpoint=True):
    """Read-only assessment: do not truncate to 50, the close time, or equal Ns."""
    report = dict(outcome="incomplete", qualified_improvement=False,
                  reason="All four planned legs must complete", legs=[],
                  limitations=plan["limitations"], gate=plan["precommit"]["candidate_gate"])
    validated, identifiers = [], set()
    invalid, missing = [], []
    anchor = None
    for spec in plan["legs"]:
        record = next((row for row in records if row["index"] == spec["index"]), {})
        evidence = dict(index=spec["index"], role=spec["role"],
            receipt_path=spec["receipt_path"], console_log=spec["console_log"],
            returncode=record.get("returncode"))
        try:
            path = Path(spec["receipt_path"])
            if not path.is_file():
                raise FileNotFoundError("No completed receipt")
            receipt, leg, digest = load_leg(spec, plan, verify_checkpoint=verify_checkpoint)
            if record.get("returncode") != 0:
                raise ValueError("Evaluator did not exit successfully")
            signature = dict(job=dict({field: receipt["job"][field] for field in JOB_FIELDS},
                game_boundary_diagnostics=receipt["job"].get("game_boundary_diagnostics", False)),
                numeric_policy=receipt["numeric_policy"], runtime=receipt["runtime"],
                source_hashes=receipt["source_hashes"], protocol=leg["protocol"],
                boot_identity=receipt["boot_assets"]["identity"],
                wire_binary=receipt["socket_wait"]["sha256"])
            if anchor is not None and signature != anchor:
                raise ValueError("Backend, runtime, source, or game protocol differs between campaign legs")
            anchor = signature
            ids = {row["journal_game_id"] for row in leg["rows"]}
            if identifiers & ids:
                raise ValueError("Game IDs overlap across campaign legs")
            identifiers.update(ids)
            evidence.update(valid=True, receipt_sha256=digest, summary=summarize(leg),
                included_game_ids=[row["journal_game_id"] for row in leg["rows"]])
            validated.append((spec["role"], leg, evidence))
        except (FileNotFoundError, IncompleteLeg) as error:
            evidence.update(valid=False, error=str(error))
            missing.append(spec["index"])
        except (OSError, ValueError, TypeError, KeyError) as error:
            evidence.update(valid=False, error=str(error))
            invalid.append(spec["index"])
        report["legs"].append(evidence)
    if invalid:
        report.update(outcome="invalid", reason=f"Invalid legs: {invalid}; missing legs: {missing}")
        return report
    if missing or len(validated) != 4:
        return report
    reference_rows = [row for role, leg, _ in validated if role == "reference" for row in leg["rows"]]
    scores = [row["score"] for row in reference_rows]
    mean, median = statistics.fmean(scores), statistics.median(scores)
    report["pooled_reference"] = dict(count=len(scores), mean=mean, median=median,
        actor_slot_counts=dict(sorted(Counter(str(row["client_slot"]) for row in reference_rows).items())))
    if mean <= 0:
        report.update(outcome="invalid", reason="Pooled reference mean must be positive to assess a relative improvement")
        return report
    checks = []
    for role, leg, evidence in validated:
        if role != "candidate":
            continue
        summary = evidence["summary"]
        checks.append(dict(index=evidence["index"], mean=summary["mean"], median=summary["median"],
            mean_ratio=summary["mean"]/mean if mean else None,
            mean_pass=summary["mean"] >= mean * 1.05,
            median_pass=summary["median"] >= median))
    qualified = all(check["mean_pass"] and check["median_pass"] for check in checks)
    report.update(candidate_checks=checks, qualified_improvement=qualified,
        outcome="qualified_improvement" if qualified else "not_improved",
        reason="Both candidate legs satisfy the fixed mean and median gates" if qualified else
               "At least one candidate leg misses the fixed mean or median gate")
    return report


def run_campaign(campaign, *, popen=subprocess.Popen):
    plan = make_plan(campaign)
    campaign.directory.mkdir(parents=True, exist_ok=False)
    write_immutable(campaign.directory / "plan.json", plan)
    plan_hash = evaluator.sha256(campaign.directory / "plan.json")
    records, current, stop_signal = [], None, None
    progress = dict(state="preparing", outcome="incomplete", plan_sha256=plan_hash,
        plan_path=str(campaign.directory / "plan.json"), legs=records,
        limitations=plan["limitations"])
    status_path = campaign.directory / "status.json"

    def publish():
        progress["updated_unix_s"] = time.time()
        evaluator.write_json(status_path, progress)

    def stop(signum, _frame):
        nonlocal stop_signal
        if stop_signal is None:
            stop_signal = signum
            if current is not None and current.poll() is None:
                try:
                    current.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass

    previous = {signum: signal.signal(signum, stop) for signum in (signal.SIGTERM, signal.SIGINT)}
    failure = None
    try:
        publish()
        snapshot_checkpoints(plan)
        for spec in plan["legs"]:
            if stop_signal is not None:
                break
            check_precommit(plan)
            if evaluator.sha256(campaign.directory / "plan.json") != plan_hash:
                raise ValueError("Immutable campaign plan changed")
            record = dict(index=spec["index"], role=spec["role"], state="running",
                started_unix_s=time.time(), receipt_path=spec["receipt_path"],
                evaluator_status_path=spec["evaluator_status_path"], console_log=spec["console_log"])
            records.append(record)
            progress.update(state="running", current_leg=spec["index"])
            publish()
            with Path(spec["console_log"]).open("x") as log:
                current = popen(spec["command"], stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, cwd=evaluator.GAME.parent,
                    start_new_session=True, close_fds=True)
                record["pid"] = current.pid
                if stop_signal is not None and current.poll() is None:
                    current.send_signal(signal.SIGINT)
                publish()
                while True:
                    try:
                        returncode = current.wait(timeout=5)
                        break
                    except subprocess.TimeoutExpired:
                        publish()
            current = None
            record.update(returncode=returncode, ended_unix_s=time.time(), state="finished")
            publish()
            if stop_signal is not None or returncode != 0:
                break
            # Stop immediately on an unusable receipt, even if the child exits 0.
            load_leg(spec, plan)
            check_precommit(plan)
    except (OSError, ValueError, TypeError, KeyError) as error:
        failure = f"{type(error).__name__}: {error}"
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    report = assess_campaign(plan, records)
    if stop_signal is not None:
        report.update(outcome="incomplete", qualified_improvement=False,
                      reason=f"Campaign interrupted by signal {stop_signal}; no retry or extension")
    elif failure:
        report.update(outcome="invalid", qualified_improvement=False, reason=failure)
    report.update(plan_path=str(campaign.directory / "plan.json"), plan_sha256=plan_hash,
                  ended_unix_s=time.time(), stop_signal=stop_signal)
    evaluator.write_json(campaign.directory / "summary.json", report)
    progress.update(state="finished", outcome=report["outcome"], reason=report["reason"],
                    summary_path=str(campaign.directory / "summary.json"))
    publish()
    print(json.dumps({key: report[key] for key in ("outcome", "qualified_improvement", "reason")}))
    return 1 if report["outcome"] in ("invalid", "incomplete") else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=
        "Durable launch example: systemd-run --user --unit=robotron-quality-UNIQUE "
        "--property=KillMode=mixed --property=TimeoutStopSec=60 "
        "<python> <this-script> <arguments> --launch. Use a fresh unit and output directory.")
    parser.add_argument("--reference-checkpoint", type=Path, required=True)
    parser.add_argument("--candidate-checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-label", default="reference")
    parser.add_argument("--candidate-label", default="candidate")
    parser.add_argument("--gpu-uuid", default=GPU0_UUID)
    parser.add_argument("--boot-assets", type=Path, default=BOOT_ASSETS)
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--cohort-s", type=float, default=1200)
    parser.add_argument("--timeout-s", type=float, default=2400)
    parser.add_argument("--mame", type=Path, default=Path("/usr/games/mame"))
    parser.add_argument("--rompath", type=Path, default=evaluator.GAME / "roms")
    parser.add_argument("--hypothesis", default=Campaign.__dataclass_fields__["hypothesis"].default)
    parser.add_argument("--game-boundary-diagnostics", action="store_true", default=True,
                        help="precommit the same opt-in boundary diagnostics for all four legs")
    parser.add_argument("--launch", action="store_true", help="run the precommitted campaign; default prints its plan")
    args = parser.parse_args(argv)
    campaign = Campaign(args.reference_checkpoint.resolve(), args.candidate_checkpoint.resolve(),
        args.output_dir.resolve(), args.reference_label, args.candidate_label, args.gpu_uuid,
        args.boot_assets.resolve(), args.port, args.cohort_s, args.timeout_s,
        args.mame.resolve(), args.rompath.resolve(), args.hypothesis,
        game_boundary_diagnostics=args.game_boundary_diagnostics)
    try:
        if args.launch:
            return run_campaign(campaign)
        print(json.dumps(make_plan(campaign), indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Campaign rejected: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
