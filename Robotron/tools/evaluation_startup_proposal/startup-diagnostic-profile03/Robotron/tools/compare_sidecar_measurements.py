#!/usr/bin/env python3
"""Compare full frozen cohorts only after matching their private backend.

This extends the whole-game validator with evidence specific to the isolated
GPU evaluator. It never changes training, checkpoints, or evaluation receipts.
"""
import argparse
import hashlib
import json
from pathlib import Path

try:
    from .compare_frozen_measurements import compare_receipts, validate_receipt
except ImportError:
    from compare_frozen_measurements import compare_receipts, validate_receipt


JOB_FIELDS = (
    "device", "gpu_uuid", "actors", "actor_slots", "port", "cohort_s",
    "timeout_s", "wait_us", "epsilon", "expert_ratio", "difficulty",
    "start_level", "replay_enabled", "fp16", "mame", "rompath",
    "cpu_threads", "boot_assets", "inference_backend", "inference_max_batch_size",
    "completion_policy", "game_boundary_diagnostics",
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_backend(receipt, *, verify_checkpoint=False):
    leg = validate_receipt(receipt)
    try:
        from .confirmed_terminal_evidence import validate_receipt_terminals
    except ImportError:
        from confirmed_terminal_evidence import validate_receipt_terminals
    rows = receipt.get("rows", receipt.get("cohort", {}).get("rows", []))
    validate_receipt_terminals(receipt, rows)
    job = receipt.get("job", {})
    if any(field not in job for field in JOB_FIELDS):
        raise ValueError("Missing private backend settings")
    count = job["actors"]
    if type(count) is not int or count not in (16, 32):
        raise ValueError("Explicit 16- or 32-actor private profile required")
    expected_slots = list(range(4096, 4096 + count))
    if (job["device"] != "cuda"
            or job["actor_slots"] != expected_slots
            or job["inference_max_batch_size"] != 16
            or job["port"] == 9998 or job["replay_enabled"] is not False
            or job["fp16"] is not False or job["epsilon"] != 0
            or job["expert_ratio"] != 0 or job["difficulty"] != 5
            or job["start_level"] != 1):
        raise ValueError("Unexpected private frozen protocol")
    if (leg["expected_actor_slots"] != expected_slots
            or {row["client_slot"] for row in leg["rows"]} != set(expected_slots)):
        raise ValueError("Every declared private actor slot must contribute full games")
    if any(receipt.get(key) for key in (
            "server_error", "inference_error", "cleanup_errors", "invalidity_reasons")):
        raise ValueError("Private evaluation has runtime or cleanup errors")
    slots = {str(slot) for slot in job["actor_slots"]}
    timeouts = receipt.get("actor_timeout_logs", {})
    if set(timeouts) != slots or any(value != 0 for value in timeouts.values()):
        raise ValueError("Missing timeout evidence or measured runtime timeouts")
    sources = receipt.get("source_hashes")
    if not sources or sources != receipt.get("ended_source_hashes"):
        raise ValueError("Private evaluation source changed or was not recorded")
    numeric = receipt.get("numeric_policy", {})
    if (numeric.get("autocast") is not False or numeric.get("weights") != "float32"
            or numeric.get("inputs") != "float32" or numeric.get("support") != "float32"):
        raise ValueError("Unexpected numeric policy")
    if (job["inference_backend"] not in ("eager", "inductor")
            or job["inference_backend"] != receipt.get("inference_backend")):
        raise ValueError("Declared inference backend differs from actual backend")
    if job["inference_backend"] == "inductor":
        compile_report = receipt.get("compile_report", {})
        graph = compile_report.get("graph_state", {})
        if (numeric.get("backend") != "inductor" or numeric.get("execution") != "torch.compile"
                or numeric.get("compiled") is not True or numeric.get("suppress_errors") is not False
                or numeric.get("error_on_recompile") is not True
                or numeric.get("serving_thread_checked") is not True
                or numeric.get("warm_shapes") != list(range(1, 17))
                or compile_report.get("all_shapes_verified") != list(range(1, 17))
                or not isinstance(graph.get("unique_graphs"), int)
                or isinstance(graph.get("unique_graphs"), bool) or graph["unique_graphs"] < 1
                or graph.get("graph_breaks") != 0 or graph.get("unimplemented") != 0):
            raise ValueError("Strict compilation evidence is incomplete")
    elif (numeric.get("backend") != "eager" or numeric.get("compiled") is not False
          or numeric.get("execution") != "eager"):
        raise ValueError("Eager backend numeric evidence is inconsistent")
    boot = receipt.get("boot_assets", {})
    identity = boot.get("identity")
    restores = receipt.get("boot_restores", {})
    if not identity or not boot.get("files") or set(restores) != slots:
        raise ValueError("Private boot identity/coverage missing")
    for row in restores.values():
        if row.get("identity") != identity or row.get("files") != boot.get("files"):
            raise ValueError("Actor did not restore the matching private boot snapshot")
    wait = receipt.get("socket_wait", {})
    actors = wait.get("actors", {})
    if (wait.get("port") != job["port"] or wait.get("wait_us") != job["wait_us"]
            or not wait.get("sha256") or set(actors) != slots
            or not all(row.get("matching_activation") is True for row in actors.values())):
        raise ValueError("Private wire pacing evidence is incomplete")
    digest = receipt.get("checkpoint_sha256", "")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("Missing checkpoint identity")
    if verify_checkpoint and sha256(receipt["checkpoint_path"]) != digest:
        raise ValueError("Frozen checkpoint copy does not match receipt")
    return leg


def validate_original_backend(receipt, directory, *, verify_checkpoint=False):
    """Read both original journals even when checkpoint readback is disabled.

    This validates one standalone receipt; it does not qualify a policy or
    authorize a mixed-profile quality comparison.
    """
    leg = validate_backend(receipt, verify_checkpoint=verify_checkpoint)
    directory = Path(directory).resolve(strict=True)
    if receipt["job"].get("directory") != str(directory):
        raise ValueError("Exact declared private job directory required")
    try:
        from .confirmed_terminal_evidence import verify_original_journal_bytes
    except ImportError:
        from confirmed_terminal_evidence import verify_original_journal_bytes
    payloads = {name: (directory/"journal"/name).read_bytes()
                for name in ("games.jsonl", "measurement_starts.jsonl")}
    links = verify_original_journal_bytes(receipt, payloads)
    if len(links) != len(leg["rows"]):
        raise ValueError("Original terminal readback must cover every full game")
    return dict(leg=leg, original_terminal_readback=dict(
        status="PASS", verified_games=len(links), links=links))


def compare_sidecars(baseline, candidate, *, iterations=5000, verify_checkpoint=False):
    legs = [validate_backend(row, verify_checkpoint=verify_checkpoint)
            for row in (baseline, candidate)]
    for field in JOB_FIELDS:
        if baseline["job"][field] != candidate["job"][field]:
            raise ValueError(f"Private backend differs: {field}")
    for field in ("numeric_policy", "runtime", "source_hashes"):
        if not baseline.get(field) or baseline[field] != candidate.get(field):
            raise ValueError(f"Private backend differs: {field}")
    if (baseline["boot_assets"]["identity"] != candidate["boot_assets"]["identity"]
            or baseline["socket_wait"]["sha256"] != candidate["socket_wait"]["sha256"]):
        raise ValueError("Private boot snapshot or wire pacing binary differs")
    if {r["journal_game_id"] for r in legs[0]["rows"]} & {
            r["journal_game_id"] for r in legs[1]["rows"]}:
        raise ValueError("Game IDs overlap across frozen cohorts")
    report = compare_receipts(baseline, candidate, iterations=iterations)
    report["matched_private_backend"] = {field: baseline["job"][field] for field in JOB_FIELDS}
    report["backend_validated"] = True
    report["checkpoint_copies_verified"] = verify_checkpoint
    report["checkpoint_sha256"] = dict(baseline=baseline["checkpoint_sha256"],
                                       candidate=candidate["checkpoint_sha256"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; comparison evidence is not overwritten")
    try:
        report = compare_sidecars(json.loads(args.baseline.read_text()),
                                  json.loads(args.candidate.read_text()),
                                  iterations=args.iterations, verify_checkpoint=True)
        report["sources"] = {name: dict(path=str(path.resolve()), sha256=sha256(path))
                             for name, path in (("baseline", args.baseline),
                                                ("candidate", args.candidate))}
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Comparison rejected: {error}\n")
    for name in ("baseline", "candidate"):
        row = report[name]
        print(f"{name}: {row['count']} full games; mean {row['mean']:,.1f}; "
              f"median {row['median']:,.1f}; SE {row['se']:,.1f}")
    print(f"Mean change: {100*(report['score_ratio']-1):+.2f}%")
    print(report["warnings"][0])


if __name__ == "__main__":
    main()
