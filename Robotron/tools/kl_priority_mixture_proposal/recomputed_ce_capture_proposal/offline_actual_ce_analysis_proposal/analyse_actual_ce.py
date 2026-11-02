"""Offline actual-CE/mixture descriptions. Default is a literal, read-free plan.

This does not reconstruct a target, entropy, KL, parameter gradient or new policy.
Future explicit execution loads one immutable capture at a time on hidden CUDA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys

SCHEMA = "robotron-actual-ce-observational-analysis-inputs-v1"
ATTEMPTS, BATCH = 8, 4096
MAX_JSON, MAX_PAYLOAD, MAX_OUTPUT = 2 << 20, 640 << 20, 8 << 20
ORIGINS = ("per", "interesting", "recent", "hof", "ephof")
TOTALS = ("attempts_started", "outcomes_recorded", "applied", "amp_skipped", "unavailable")
LOSS_SHA = "de9621e3d926a8f49f230f9e271c645a7498d38445622d6ae2761ab2bbd7253a"
PRODUCER_MANIFEST = "356b8b0999b05d3d4cd6e2addfcbee832c7365c9c31f9c08506f8714c0dfeaa2"
# Retained verbatim for a SEPARATE future conditional-recomputation comparison.
# No comparison to a reconstructed target/CE is performed by this analyser.
ORIGINAL_CONDITIONAL_CE_TOLERANCE = {"rtol": 2e-4, "atol": 2e-5}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def values(data, length, name):
    require(isinstance(data, (tuple, list)) and len(data) == length, name + " shape differs")
    require(all(type(x) in (int, float, bool) and math.isfinite(x) for x in data), name + " not finite numeric")
    return [float(x) for x in data]


def stats(data):
    if not data:
        return dict(count=0, sum=0.0, mean=None, minimum=None, median=None, p90=None, maximum=None)
    ordered, n = sorted(data), len(data)
    middle = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2
    return dict(count=n, sum=math.fsum(data), mean=math.fsum(data) / n,
                minimum=ordered[0], median=middle, p90=ordered[math.ceil(.9 * n) - 1], maximum=ordered[-1])


def coefficient_summary(weights):
    total, squares = math.fsum(weights), math.fsum(x * x for x in weights)
    return dict(sum=total, mean=total / len(weights) if weights else None,
                effective_count=total * total / squares if squares else 0.0,
                scope="Coefficient concentration only; not population IS ESS or measured parameter-gradient norm")


def boundaries(draw, n):
    result, cursor = {}, 0
    require(len(draw["origin_boundaries"]) == len(ORIGINS), "Five draw origin boundaries required")
    for expected, record in zip(ORIGINS, draw["origin_boundaries"]):
        name, start, end = record
        require(name == expected and type(start) is int and type(end) is int and start == cursor <= end <= n,
                "Draw origin boundary differs")
        result[name], cursor = range(start, end), end
    require(cursor == n, "Origins do not cover every actual row")
    return result


def outcome(row):
    before, after = row["exposure_before"], row["exposure_at_exit"]
    require(all(before[k] == after[k] for k in ("process_id", "instance_monotonic_ns", "epoch")), "Optimizer identity changed")
    delta = {key: after["total"][key] - before["total"][key] for key in TOTALS}
    require(delta == row["actual_exposure_delta"] and delta["attempts_started"] == delta["outcomes_recorded"] == 1
            and delta["unavailable"] == 0 and delta["applied"] in (0, 1) and delta["amp_skipped"] in (0, 1)
            and delta["applied"] + delta["amp_skipped"] == 1 and row["outcome_available"] and after["available"],
            "Exactly one classified real admission outcome required")
    observation = row["optimizer_observation"]
    require(observation["ticket_finished"] and observation["ticket_owner_matches"]
            and observation["ticket_epoch"] == before["epoch"], "Actual optimizer ticket differs")
    label = "amp_skipped" if delta["amp_skipped"] else "applied_admission"
    require(row["optimizer_outcome"] == label, "Outcome label differs")
    if observation["mode"] == "single_cuda_found_inf":
        require(observation["found_inf"] in (0, 1) and (observation["found_inf"] == 1) == (label == "amp_skipped"),
                "Found-inf contradicts actual outcome")
    else:
        require(observation["mode"] in ("unscaled", "scaler_disabled") and observation["found_inf"] is None
                and label == "applied_admission", "Unsupported optimizer outcome")
    return label


def analyse_rows(ce, weights, draw, *, weighted_loss, bc_loss, schedule, bc_floor=.01):
    """Small detached Python vectors only. Preserve duplicates and original order."""
    n = len(ce)
    require(n > 0, "Empty batch")
    ce, weights = values(ce, n, "CE"), values(weights, n, "weights")
    require(all(x >= 0 for x in ce) and all(0 < x <= 1 for x in weights), "CE/normalized weight domain differs")
    parts = boundaries(draw, n)
    emitted64 = values(draw["supplied_weights_float64"], n, "emitted FP64 weights")
    emitted32 = values(draw["supplied_weights_float32"], n, "emitted FP32 weights")
    require([f32(x) for x in emitted64] == emitted32 == weights, "Actual weights differ from draw-time FP32 cast")
    indices = values(draw["indices"], n, "indices")
    require(all(x.is_integer() and x >= 0 for x in indices), "Invalid selected row index")
    small = draw["small_batch_fields"]
    expert, dones = values(small["is_expert"], n, "expert"), values(small["dones"], n, "dones")
    horizons, actors = values(small["horizons"], n, "horizons"), values(small["actor_kind"], n, "actor kind")
    rewards, actions = values(small["rewards"], n, "rewards"), values(small["actions"], n, "actions")
    require(all(x in (0, 1) for x in expert + dones) and all(x.is_integer() and x > 0 for x in horizons)
            and all(x.is_integer() and 0 <= x < 81 for x in actions)
            and all(x.is_integer() and 0 <= x < 3 for x in actors), "Captured row stratum domain differs")
    per = list(parts["per"])
    raw = values(draw["per_raw_weights_float64"], len(per), "PER raw weights")
    leaves = values(draw["per_raw_leaves"], len(per), "PER raw leaves")
    clamped = values(draw["per_clamped_leaves"], len(per), "PER clamped leaves")
    require(all(x > 0 for x in raw) and clamped == [max(1e-10, x) for x in leaves], "PER raw/clamped leaf evidence differs")
    total, size, beta = draw["tree_total"], draw["size"], draw["beta"]
    require(type(size) is int and 0 < size <= draw["capacity"] and math.isfinite(total) and total > 0
            and math.isfinite(beta) and 0 <= beta <= 1, "Tree size/total/beta differs")
    normalizer = max(1e-12, max(raw)) if raw else None
    require(draw["selected_per_raw_max_weight"] == (max(raw) if raw else None)
            and all(emitted64[i] == raw[j] / normalizer for j, i in enumerate(per)), "Selected PER normalization differs")
    require(all(emitted64[i] == 1 for name in ("interesting", "recent") for i in parts[name]), "Quota weights differ")
    per_mean = math.fsum(emitted64[i] for i in per) / len(per) if per else 1.0
    bank_deltas = {}
    for name in ("hof", "ephof"):
        selected = list(parts[name])
        if selected:
            first = emitted64[selected[0]]
            require(all(emitted64[i] == first for i in selected), "Bank does not carry one same-batch mean weight")
            # NumPy mean and math.fsum differ in rounding. Report this difference;
            # no learner/CE tolerance is changed or used as a metadata tolerance.
            bank_deltas[name] = first - per_mean
    predicted_raw = [(size * (x / total)) ** (-beta) for x in clamped]
    bellman_terms = [w * c / n for w, c in zip(weights, ce)]
    bellman = math.fsum(bellman_terms)
    require(all(type(x) in (int, float) and math.isfinite(x) for x in (weighted_loss, bc_loss, bc_floor))
            and len(schedule) == 3 and all(math.isfinite(x) for x in schedule), "Actual scalar/schedule differs")
    bc_term = max(bc_floor, schedule[0] * math.fsum(expert) / n) * bc_loss
    groups = {"all": list(range(n))}
    groups.update({"origin:" + name: list(selected) for name, selected in parts.items()})
    groups.update({"expert:" + str(kind): [i for i, value in enumerate(expert) if value == kind] for kind in (0, 1)})
    for label, vector in (("done", dones), ("horizon", horizons), ("actor_kind", actors)):
        for value in sorted(set(vector)):
            groups[label + ":" + str(int(value))] = [i for i, observed in enumerate(vector) if observed == value]
    groups["reward:negative"] = [i for i, x in enumerate(rewards) if x < 0]
    groups["reward:zero"] = [i for i, x in enumerate(rewards) if x == 0]
    groups["reward:positive"] = [i for i, x in enumerate(rewards) if x > 0]
    descriptions = {}
    for name, rows in groups.items():
        descriptions[name] = dict(rows=len(rows), fraction=len(rows)/n, ce=stats([ce[i] for i in rows]),
            weights=stats([weights[i] for i in rows]), coefficient=coefficient_summary([weights[i] for i in rows]),
            bellman_objective_contribution=math.fsum(bellman_terms[i] for i in rows),
            full_batch_coefficient_mass=math.fsum(weights[i] for i in rows)/n)
    ring_rows = [i for name in ("per", "interesting", "recent") for i in parts[name]]
    frequencies = {}
    for i in ring_rows:
        frequencies[indices[i]] = frequencies.get(indices[i], 0) + 1
    largest = sorted(bellman_terms, reverse=True)
    return dict(rows=n, groups=descriptions, alpha=draw["alpha"], beta=beta,
        normalizer=dict(raw_max=max(raw) if raw else None, denominator=normalizer,
            denominator_floor_active=bool(raw and max(raw) < 1e-12),
            bank_weight_minus_FP64_fsum_PER_mean=bank_deltas,
            raw_formula_max_abs_error=max((abs(a-b) for a,b in zip(raw,predicted_raw)), default=0.0)),
        scalar_accounting=dict(actual_weighted_loss=weighted_loss, actual_bc_loss=bc_loss,
            bellman_objective_FP64_reduction=bellman, known_bc_contribution_FP64=bc_term,
            combined_other_auxiliary_plus_reduction_residual=weighted_loss-bellman-bc_term,
            schedule=list(schedule),
            scope="Descriptive arithmetic: actual weighted loss also includes unobserved per-row Q-policy/margin auxiliaries and FP32/AMP reduction effects"),
        bellman_objective_concentration={str(fraction):math.fsum(largest[:max(1,math.ceil(n*fraction))])/bellman
            if bellman else None for fraction in (.01,.1)},
        duplicates=dict(ring_rows=len(ring_rows), ring_distinct_indices=len(frequencies),
            ring_duplicate_rows=sum(count for count in frequencies.values() if count > 1),
            ring_repeated_slots=sum(count > 1 for count in frequencies.values()),
            scope="Row observations retained; no slot-generation identity or refreshed-tree/last-write claim"),
        banks={name:{key:value for key,value in draw["banks"][name].items() if key != "selected_slots"} for name in ("hof", "ephof")},
        unknown=draw["unknown"], measured_parameter_gradients=False, executed_per_row_target_entropy_or_KL_observed=False)


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode, info.st_uid, info.st_nlink)


def check_pin(pin, limit):
    require(set(pin) == {"path", "sha256", "bytes"}, "Input pin fields differ")
    path = Path(pin["path"])
    require(path.is_absolute() and path == path.resolve(strict=True), "Canonical nonsymlink input required")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) == 0o444 and before.st_size == pin["bytes"] <= limit,
            "Input must be bounded owned0444 regular single-link file")
    hasher = hashlib.sha256()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), "Input open race")
        while block := stream.read(4 << 20):
            hasher.update(block)
        require(identity(os.fstat(stream.fileno())) == identity(before), "Input changed during hash")
    require(identity(path.lstat()) == identity(before) and hasher.hexdigest() == pin["sha256"], "Input pin changed")
    return path, identity(before)


def json_file(pin):
    path, before = check_pin(pin, MAX_JSON)
    result = json.loads(path.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    require(identity(path.lstat()) == before, "JSON input changed")
    return result


def publish(path, result):
    raw = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
    require(len(raw) <= MAX_OUTPUT, "Analysis output exceeds8MiB")
    with Path(path).open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o444)


def analyse_capture(torch, payload, row):
    require(payload["attempt"] == row["index"] and payload["nonfinite_copies"] == 0
            and payload["capture_id"] == row["draw_capture_id"] == payload["draw"]["capture_id"], "Payload draw/attempt identity differs")
    require(row["capture_complete"] and row["draw_batch_join_checked"] and row["staged_draw_join_checked"]
            and not row["observer_errors"] and row["exception"] is None, "Incomplete actual consumed attempt")
    lease = {key:row["prefetch"][key] for key in ("lease_epoch", "owner_epoch_at_consumption", "current")}
    require(lease["current"] and lease["lease_epoch"] == lease["owner_epoch_at_consumption"]
            and all(row["prefetch_"+name] == lease for name in ("begin", "pre_loss", "exit")), "Consumed lease differs")
    for key in ("index", "draw_capture_id", "optimizer_outcome", "actual_exposure_delta", "optimizer_observation", "before", "at_loss", "after"):
        require(payload["outcome"][key] == row[key], "Embedded actual outcome differs: " + key)
    pre, actual, inputs, draw = payload["pre_context"], payload["actual"], payload["inputs"], payload["draw"]
    require(pre["loss_sha256"] == LOSS_SHA and pre["config"]["batch_size"] == BATCH
            and pre["config"]["num_atoms"] == 51 and draw["schema"] == "robotron-replay-draw-observation-v1", "Held source/geometry differs")
    def vector(value, dtype, shape):
        require(value.device.type == "cpu" and value.dtype == dtype and tuple(value.shape) == shape
                and bool(torch.isfinite(value).all()), "Actual small tensor dtype/shape/finite differs")
        return value.tolist()
    ce = vector(actual["ce"], torch.float32, (BATCH,))
    weights = vector(inputs["weights"], torch.float32, (BATCH,))
    per_count = len(draw["per_raw_leaves"])
    for name,count in (("supplied_weights_float64",BATCH),("per_raw_weights_float64",per_count),
                       ("per_raw_leaves",per_count),("per_clamped_leaves",per_count)):
        vector(draw[name],torch.float64,(count,))
    vector(draw["supplied_weights_float32"],torch.float32,(BATCH,))
    for name in ("actions", "rewards", "dones", "horizons", "is_expert"):
        require(torch.equal(inputs[name], draw["small_batch_fields"][name].to(dtype=inputs[name].dtype)), "Staged/draw small field differs")
    require(torch.equal(inputs["weights"], draw["supplied_weights_float32"]), "Staged/draw weights differ")
    def detached(value):
        if isinstance(value, torch.Tensor):
            require(value.device.type == "cpu" and value.numel() <= BATCH and bool(torch.isfinite(value).all()), "Unexpected small draw tensor")
            return value.tolist()
        if isinstance(value, dict): return {key:detached(part) for key,part in value.items()}
        if isinstance(value, (tuple,list)): return [detached(part) for part in value]
        return value
    report = analyse_rows(ce, weights, detached(draw), weighted_loss=float(actual["weighted_loss"]),
        bc_loss=float(actual["bc_loss"]), schedule=vector(payload["schedule"],torch.float32,(3,)),
        bc_floor=float(pre["config"].get("expert_bc_effective_floor",.01)))
    report.update(index=row["index"], optimizer_outcome=outcome(row), backend=row["backend"],
        before=row["before"], after=row["after"], diagnostic_values=vector(actual["diagnostic_values"],torch.float32,(12,)),
        batch_diagnostics_available=row["backend"].endswith("_diagnostics"),
        diagnostic_scope="Diagnostic route retains actual unweighted batch entropy/KL means at indices9/11; ordinary route returns12 zeros. No per-row target/entropy/KL is observed",
        draw_to_consumed_ns=row["consumed_monotonic_ns"]-draw["lock_observation_finished_monotonic_ns"],
        pre_snapshot_ns=row["pre_snapshot_ns"], drain_ns=row["drain_ns"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--binding", type=Path)
    parser.add_argument("--binding-sha256")
    parser.add_argument("--tool-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print("PLAN_ONLY: future actualCE/mixture descriptions; no input reads/imports/output/runtime actions")
        return 0
    output = None
    try:
        require(args.binding and args.binding_sha256 and args.tool_sha256 and args.output, "Explicit immutable root binding/source/output required")
        require(os.getenv("CUDA_VISIBLE_DEVICES") == "", "CUDA must be hidden before interpreter start")
        require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.tool_sha256, "Tool source differs")
        binding = json_file(dict(path=str(args.binding),sha256=args.binding_sha256,bytes=args.binding.stat().st_size))
        require(binding["schema"] == SCHEMA and binding["population"] == "live_consecutive_consumed_attempts"
                and binding["actual_target_entropy_or_KL_observed"] is False, "Declared population/scope differs")
        require(binding["producer_manifest"]["sha256"] == PRODUCER_MANIFEST, "Wrong source-proposal manifest")
        producer = json_file(binding["producer_manifest"])
        json_file(binding["acquisition_review"])
        maintenance = json_file(binding["maintenance_result"])
        root_job = json_file(binding["maintenance_root_job"])
        require(maintenance["schema"] == "robotron-live8-maintenance-result-v1" and maintenance["status"] == "COMPLETE"
                and maintenance["capture_complete"] and not maintenance["manual_recovery_required"]
                and maintenance["root_job"]["sha256"] == binding["maintenance_root_job"]["sha256"],
                "Completed root-owned live acquisition proof required")
        require(root_job["schema"] == "robotron-live8-maintenance-job-v1" and len(root_job["sources"]) == 5
                and {Path(e["destination"]).name:e["after"]["sha256"] for e in root_job["sources"]} ==
                    {name:producer["files"][name]["sha256"] for name in
                     ("agent.py","training.py","replay_buffer.py","prefetch.py","recomputed_ce_capture.py")},
                "Acquired source overlays differ from reviewed producer")
        context, final = json_file(binding["context"]), json_file(binding["final"])
        require(context["schema"] == "robotron-recomputed-ce-capture-v1" and context["loss_abi"] == 4
                and context["loss_sha256"] == LOSS_SHA and context["attempts"] == ATTEMPTS
                and context["optimizer_recipe_change"] is False and final["complete"]
                and final["status"] == "EIGHT_INPUT_CE_CAPTURES_COMPLETE" and final["attempts_consumed"] == ATTEMPTS
                and not final["observer_errors"] and final["actual_target_entropy_or_KL_observed"] is False,
                "Complete authentic first8 capture required; failures are not replaced")
        require(maintenance["captured"]["final"] == final, "Maintenance final capture differs")
        require(len(binding["attempts"]) == len(final["rows"]) == ATTEMPTS, "Exactly eight attempts required")
        trace = Path(root_job["capture_directory"])
        require(binding["context"]["path"] == str(trace/"context.json") and binding["final"]["path"] == str(trace/"final.json"),
                "Bound capture directory/context/final differs")
        allowed = {"context.json","final.json"} | {"status-%03d.json"%i for i in range(1,129)} | {
            "attempt-%02d%s"%(i,suffix) for i in range(1,9) for suffix in (".entered.json",".json",".payload.pt")}
        require({path.name for path in trace.iterdir()} <= allowed, "Unexpected/ninth capture artifact")
        output = args.output
        require(output.is_absolute() and output == output.resolve(strict=False) and not output.exists(), "New canonical output required")
        output.mkdir(mode=0o700)
        import torch
        torch.set_num_threads(2)
        torch.set_num_interop_threads(2)
        require(not torch.cuda.is_initialized() and torch.cuda.device_count() == 0, "Unexpected CUDA initialization")
        reports, previous = [], None
        for index, entry in enumerate(binding["attempts"], 1):
            require(entry["receipt"]["path"] == str(trace/("attempt-%02d.json"%index))
                    and entry["payload"]["path"] == str(trace/("attempt-%02d.payload.pt"%index)), "Attempt path differs")
            row = json_file(entry["receipt"])
            require(row["index"] == index and row == final["rows"][index-1] and row["draw_capture_id"] == context["capture_id"], "Attempt ordinal/session/final row differs")
            if previous is not None:
                require(row["exposure_before"] == previous["exposure_at_exit"] and all(row["before"][key] == previous["after"][key]
                        for key in ("training_steps","optimized_samples")) and row["consumed_monotonic_ns"] > previous["consumed_monotonic_ns"], "Not consecutive consumed attempts")
            path, before = check_pin(entry["payload"], MAX_PAYLOAD)
            require(entry["payload"] == {key:row["payload"][key] for key in ("path","sha256","bytes")}, "Producer payload pin differs")
            payload = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
            report = analyse_capture(torch,payload,row)
            del payload
            require(identity(path.lstat()) == before, "Payload changed after analysis")
            reports.append(report); previous = row
            publish(output / ("attempt-%02d.json" % index),report)
        result = dict(schema="robotron-actual-ce-observational-analysis-v1",status="OBSERVATIONAL_DESCRIPTIONS_COMPLETE",
            qualification_pass=False, population=binding["population"], attempts=reports,
            outcomes={name:sum(r["optimizer_outcome"]==name for r in reports) for name in ("applied_admission","amp_skipped")},
            mean_batch_Bellman_contribution=math.fsum(r["scalar_accounting"]["bellman_objective_FP64_reduction"] for r in reports)/ATTEMPTS,
            original_conditional_CE_tolerance=ORIGINAL_CONDITIONAL_CE_TOLERANCE,
            conditional_CE_compared=False, executed_per_row_target_entropy_or_KL_observed=False, measured_parameter_gradients=False,
            limitations=["Eight consecutive startup attempts are descriptive, not IID, sustained throughput or quality evidence.",
                "Skipped attempts remain in every all-attempt description; applied_admission is not proof every parameter moved.",
                "CE agreement with an offline reconstruction cannot bound missing executed entropy/KL/rank.",
                "No actual PER population, tree migration, future KL weights or learning improvement is inferred."])
        require(not torch.cuda.is_initialized(), "CUDA became initialized")
        publish(output / "analysis.json",result)
        return 0
    except BaseException as error:
        if output is not None and output.is_dir():
            try: publish(output / "analysis-error.json",dict(status="ANALYSIS_NOT_READY",error=repr(error),qualification_pass=False))
            except BaseException: pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
