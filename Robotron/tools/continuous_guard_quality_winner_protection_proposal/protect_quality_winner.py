#!/usr/bin/env python3
"""UNSELECTED: revalidate the exact effective-guard campaign before optional protection.

Without --publish this performs the original read-only review, including hashes
of immutable checkpoint snapshots and closed cohort evidence. It is not PLAN-only.
The canonical E13 is base provenance; the mandatory isolated-evaluator guard,
checked native profile and four runtime receipt joins remain explicit metadata.
No guard is installed or recompiled here. Root alone may select publication only
after all four valid audits, owned native closure and both independent gates.
This tool does not change training, controls, services, incumbent or freeze state.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
COMPANION = GAME/'tools/frozen_continuous_guard_evaluator_proposal/run_quality_campaign.py'
COMPANION_SHA = '6d6fd8e4aa201d7099927af508742e8112cca3a5e6ca621731306664789ed8db'
CHECKER_SOURCE = GAME/'tools/continuous_guard_same_lr25_continuation_proposal/effective_provenance.py'
CHECKER_SHA = 'f157895d90707fc725bda2381c9422c6e9ac22ab924597551d0d4d1f2d973556'
READER_SOURCE = GAME/'tools/continuous_guard_same_lr25_continuation_proposal/quality_bindings.py'
READER_SHA = '2934df1534c1ff82fdd30e0dec930146fdeb74c2589547abd76967df3fe40989'


def source_record(path, expected):
    """Authenticate bounded source bytes/identity; never a tensor/body reader."""
    path = Path(path)
    if not path.is_absolute() or path != path.resolve(strict=True) or path.suffix != '.py':
        raise ValueError('Exact absolute source file required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read((512 << 10)+1)
        after = os.fstat(stream.fileno())
    def identity(value):
        return dict(device=value.st_dev,inode=value.st_ino,bytes=value.st_size,
            mtime_ns=value.st_mtime_ns,ctime_ns=value.st_ctime_ns,
            mode=oct(stat.S_IMODE(value.st_mode)),uid=value.st_uid,nlink=value.st_nlink)
    actual = identity(before)
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
            or before.st_nlink != 1 or stat.S_IMODE(before.st_mode) != 0o444
            or len(raw) != before.st_size or not 0 < len(raw) <= 512 << 10
            or actual != identity(after) or actual != identity(path.lstat())
            or hashlib.sha256(raw).hexdigest() != expected):
        raise ValueError('Selected owned readonly source hash/identity differs')
    return dict(path=str(path),sha256=expected,bytes=len(raw),identity=actual)


def load_checked(name, path, expected):
    """One explicit module path/hash, fresh private name, no fallback or install."""
    before = source_record(path,expected)
    if name in sys.modules:
        raise ValueError('Protection dependency was already loaded under its private name')
    spec = importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise ValueError('Selected source loader unavailable')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if Path(module.__file__).resolve() != path or source_record(path,expected) != before:
        raise ValueError('Selected module source changed while loading')
    return module,before


# These sources are stdlib-only; importing them does not construct SocketServer,
# install/compile the native guard, import DQN/Torch, launch or touch a model.
campaign,CAMPAIGN_PIN = load_checked('_guard_protection_campaign',COMPANION,COMPANION_SHA)
CHECKER,CHECKER_PIN = load_checked('_guard_protection_effective_checker',CHECKER_SOURCE,CHECKER_SHA)
METADATA,READER_PIN = load_checked('_guard_protection_metadata_reader',READER_SOURCE,READER_SHA)
# Authenticate the finite comparison modules actually imported by the companion,
# in addition to its unchanged on-disk execution_sources/precommit checks.
SUPPORT_PINS = {}
for function, expected_path, expected_sha in (
        (campaign.summarize,GAME/'tools/compare_frozen_measurements.py',
         '53f744737a722fec2760c0001dc5747b19b05e07a1de8699764c781f04da6be0'),
        (campaign.validate_backend,GAME/'tools/compare_sidecar_measurements.py',
         '879590b64e760037a81da2ff574d5994d9259cf1746b8e406177e2220d37c746')):
    support = sys.modules[function.__module__]
    if (Path(support.__file__).resolve() != expected_path
            or function.__globals__ is not support.__dict__
            or getattr(support,function.__name__) is not function):
        raise ValueError('Loaded comparison implementation is not the selected module')
    SUPPORT_PINS[str(expected_path)] = source_record(expected_path,expected_sha)


def guard_provenance(plan, specs, evidence):
    """Check all four original runtime records with the already selected checker."""
    for selected in (CAMPAIGN_PIN,CHECKER_PIN,READER_PIN,*SUPPORT_PINS.values()):
        if source_record(selected['path'],selected['sha256']) != selected:
            raise ValueError('Protection dependency identity changed since import')
    selection = plan['effective_implementation']
    profile = CHECKER.check_selection(selection,METADATA.read)
    stable, joins = None,[]
    for spec in specs:
        path = Path(spec['receipt_path'])
        raw = path.read_bytes()
        receipt_sha = hashlib.sha256(raw).hexdigest()
        if evidence.get(str(path)) != receipt_sha:
            raise ValueError('Runtime provenance receipt differs from reviewed evidence')
        effective = json.loads(raw)['effective_implementation']
        checked = CHECKER.check_runtime(effective,selection,METADATA.read)
        if stable is not None and checked != stable:
            raise ValueError('Checked effective runtime differs across the four receipts')
        stable = checked
        joins.append(dict(index=spec['index'],role=spec['role'],receipt_path=str(path),
            receipt_sha256=receipt_sha,verified_before_serving=effective['verified_before_serving'],
            verified_after_cleanup=effective['verified_after_cleanup'],
            verification_error=effective['verification_error'],
            verification_count=effective['verification_count'],
            local_identity_before=effective['local_identity_before'],
            local_identity_after=effective['local_identity_after']))
    if len(joins) != 4 or [row['index'] for row in joins] != [1,2,3,4]:
        raise ValueError('Exactly four original runtime provenance joins required')
    return dict(effective_implementation=selection,stable_effective_implementation=stable,
        effective_implementation_receipts=joins,canonical_source_hashes_are_base_provenance=True,
        effective_implementation_scope='One setup-time helper override in isolated evaluators only; live main canonical f44 is unchanged.',
        effective_implementation_provenance=dict(campaign=CAMPAIGN_PIN,checker=CHECKER_PIN,
            metadata_reader=READER_PIN,comparison_sources=list(SUPPORT_PINS.values()),
            native_profile=CHECKER.CLOSED['native_profile'],verified_native_profile=profile))


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
    effective_evidence = guard_provenance(plan,specs,evidence)
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
        **effective_evidence,
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
