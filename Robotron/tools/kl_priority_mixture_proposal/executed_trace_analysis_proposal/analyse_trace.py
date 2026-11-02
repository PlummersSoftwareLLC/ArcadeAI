"""Bounded offline analysis of a separately acquired eight-attempt CE trace.

Default invocation is a literal plan: no input/source reads or NumPy import.
This new proposal has not been executed, imported or numerically validated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import zipfile

PLAN = "PLAN ONLY: no inputs read. Future explicit --execute requires --trace DIR --binding FILE --binding-sha256 SHA --tool-sha256 SHA --output NEW_DIR. Analyses exactly eight complete captures; no acquisition, training, GPU, LR-factor or learning-gain claim."
ATTEMPTS, BATCH, ATOMS = 8, 4096, 51
MAX_INPUT_BYTES, MAX_ARRAY_BYTES = 128 * 1024**2, 64 * 1024**2
MAX_JSON_BYTES = 1024**2
ORIGINS = ("per", "interesting", "recent", "hof", "ephof")
VECTORS = ("actual_emitted", "fresh_ce", "fresh_kl")
# Frozen comparison tolerances acknowledge NumPy CPU vs GPU reduction order.
RTOL, ATOL, MASS_ATOL = 3e-5, 8e-5, 3e-5
PRODUCER = {
    "agent.py": "05e2da8b4aa836635166ede19fd67c7234dc31b9a2e4aa23148e845b37a06353",
    "prefetch.py": "02871bc515ba23f8d353131e9b6b6b4e390692803578febee7c8d643dd308a27",
    "replay_buffer.py": "c79174e026021f6a1383fde707373a1ea61f2656aceec35755dfbd47b7374f8f",
    "loss_kernel.py": "ce527c840f1b0cce3f77fece52923c7023519605db92d7c5e691b1b573ee6d2f",
    "training.py": "c10cf8deaea99c9c74edbebf82d1f1c1badfdc4d33186f3874d6bc80c1e6a938",
    "executed_ce_trace.py": "d9b02b3108cdb7aa9cf895ce585810287ca5cde6ddc6b1b872721731e49648eb",
}
PRODUCER_MANIFEST = "d7fcb2e36a7b08d472341d8f7f294d384f2591f17225832da83d350bff4e3316"
DESIGN_SHA = "2c14712ebbdf85b5c2f6d00b5ea6cadddd6d378bc0bb480d02f1755a7bd63378"
TOTALS = ("attempts_started", "outcomes_recorded", "applied", "amp_skipped", "unavailable")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_regular(path, limit):
    path = Path(path)
    require(not path.is_symlink(), "Symlink input: " + str(path))
    before = path.stat()
    require(path.is_file() and before.st_size <= limit, "Nonregular or oversized input: " + str(path))
    data = path.read_bytes()
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Input changed during read")
    require(len(data) <= limit, "Input grew beyond bound")
    return data


def parse_json(data):
    def no_constant(value):
        raise ValueError("Nonfinite JSON constant: " + value)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(data, parse_constant=no_constant, object_pairs_hook=unique)


def write_json(path, value):
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with Path(path).open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def expected_files():
    return {"context.json", "status.json"} | {
        "attempt-%02d.%s" % (i, suffix)
        for i in range(1, ATTEMPTS + 1) for suffix in ("json", "npz")}


def verify_binding(trace, binding, binding_sha, tool_sha):
    """Validate external immutable identities before importing NumPy.

    An acquisition receipt is hash-bound, not automatically proven true by its
    presence. Its scientific/runtime review remains a separate prerequisite.
    """
    require(digest(read_regular(__file__, 128 * 1024)) == tool_sha, "Tool SHA mismatch")
    raw = read_regular(binding, MAX_JSON_BYTES)
    require(digest(raw) == binding_sha, "Binding SHA mismatch")
    bound = parse_json(raw)
    require(bound["schema"] == "robotron-ce-trace-analysis-input-binding-v1", "Binding schema")
    require(bound["producer_source_sha256"] == PRODUCER, "Producer source map mismatch")
    require(bound["producer_manifest_sha256"] == PRODUCER_MANIFEST, "Producer manifest mismatch")
    root = Path(__file__).resolve().parent.parent
    for name, sha in PRODUCER.items():
        require(digest(read_regular(root / "executed_trace_proposal" / name, 512 * 1024)) == sha,
                "Pinned producer changed: " + name)
    require(digest(read_regular(root / "executed_trace_proposal/manifest.json", MAX_JSON_BYTES)) ==
            PRODUCER_MANIFEST, "Producer manifest source changed")
    require(digest(read_regular(root / "DESIGN.txt", 64 * 1024)) == DESIGN_SHA, "Design changed")
    provenance = bound["provenance"]
    require(provenance["population"] in ("live_consecutive_draws", "private_fixed_batch_reuse"), "Population scope")
    require(provenance["priority_recipe"] == "ce", "Held recipe is not CE")
    # Six pinned files identify the reviewed prototype bundle, NOT imports.
    executed = provenance["executed_prototype_source_sha256"]
    require(isinstance(executed, dict) and executed and all(name in PRODUCER and sha == PRODUCER[name]
            for name, sha in executed.items()), "Executed prototype source subset")
    require(type(provenance["agent_overlay_imported"]) is bool and
            provenance["agent_overlay_imported"] == ("agent.py" in executed) and
            type(provenance["agent_lifecycle_exercised"]) is bool and
            (not provenance["agent_lifecycle_exercised"] or provenance["agent_overlay_imported"]), "Agent execution scope")
    if provenance["population"] == "live_consecutive_draws":
        require(executed == PRODUCER and provenance["agent_lifecycle_exercised"], "Live acquisition requires actual agent instrumentation")
    for key in ("checkpoint_sha256", "acquisition_review_sha256"):
        value = provenance[key]
        require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
                "Missing external identity: " + key)
    require(digest(read_regular(provenance["acquisition_review_path"], MAX_JSON_BYTES)) ==
            provenance["acquisition_review_sha256"], "Acquisition review changed")
    trace = Path(trace)
    require(trace.is_dir() and not trace.is_symlink(), "Trace directory required")
    # No ninth attempt, extra partial file, or unbound file is silently dropped.
    require({p.name for p in trace.iterdir()} == expected_files(), "Trace must contain exactly18 completed files")
    require(set(bound["trace_sha256"]) == expected_files(), "Binding must cover all18 trace files")
    total = 0
    for name in sorted(expected_files()):
        data = read_regular(trace / name, MAX_INPUT_BYTES if name.endswith("npz") else MAX_JSON_BYTES)
        total += len(data)
        require(total <= MAX_INPUT_BYTES, "Trace exceeds128MiB input budget")
        require(digest(data) == bound["trace_sha256"][name], "Trace SHA mismatch: " + name)
    return bound


def check_headers(context, status):
    require(context["schema"] == status["schema"] == "robotron-executed-ce-trace-v1", "Trace schema")
    require(context["attempts"] == status["attempts_consumed"] == ATTEMPTS, "Exactly8 consumed attempts required")
    require(status["status"] == "EIGHT_NUMERICAL_CAPTURES_COMPLETE" and
            status["numerical_captures_complete"] is True and
            not status["observer_errors"] and not status["observer_reporting_failed"], "Incomplete or invalid trace")
    require([row["index"] for row in status["rows"]] == list(range(1, 9)), "Status ordinals")
    require(context["config"]["batch_size"] == BATCH and context["config"]["num_atoms"] == ATOMS, "Trace geometry")
    require(context["config"].get("per_priority_metric", "ce") == "ce", "CE config required")


def check_outcome(row):
    before, after = row["exposure_before"], row["exposure_at_exit"]
    require(all(before[k] == after[k] for k in ("process_id", "instance_monotonic_ns", "epoch")), "Exposure identity changed")
    delta = {key: after["total"][key] - before["total"][key] for key in TOTALS}
    observed = row["optimizer_observation"]
    require(delta == row["actual_exposure_delta"] and delta["attempts_started"] ==
            delta["outcomes_recorded"] == 1 and delta["unavailable"] == 0 and
            delta["applied"] in (0, 1) and delta["amp_skipped"] in (0, 1) and
            delta["applied"] + delta["amp_skipped"] == 1 and after["available"] and
            observed["ticket_finished"] and observed["ticket_owner_matches"] and row["outcome_available"],
            "Unavailable actual optimizer outcome")
    outcome = "amp_skipped" if delta["amp_skipped"] else "applied_admission"
    require(row["optimizer_outcome"] == outcome, "Outcome label mismatch")
    require(observed["ticket_epoch"] == before["epoch"], "Stale outcome ticket epoch")
    mode, found_inf = observed["mode"], observed["found_inf"]
    if mode == "single_cuda_found_inf":
        require(type(found_inf) in (int, float) and found_inf in (0, 1) and
                (found_inf == 1) == (outcome == "amp_skipped"), "Found-inf/outcome contradiction")
    else:
        require(mode in ("unscaled", "scaler_disabled") and found_inf is None and
                outcome == "applied_admission", "Unsupported outcome mode")
    return outcome


def restore_metadata(value, arrays):
    if isinstance(value, dict):
        if "array" in value:
            require(set(value) == {"array", "dtype", "shape"}, "Invalid array reference")
            array = arrays[value["array"]]
            require(str(array.dtype) == value["dtype"] and list(array.shape) == value["shape"], "Metadata array descriptor mismatch")
            return array
        return {key: restore_metadata(item, arrays) for key, item in value.items()}
    if isinstance(value, list):
        return [restore_metadata(item, arrays) for item in value]
    return value


def load_arrays(path, np):
    # np.savez is uncompressed; inspect archive lengths before allocations.
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(len(entries) <= 64 and len({e.filename for e in entries}) == len(entries), "NPZ member count/duplicates")
        require(all(e.compress_type == zipfile.ZIP_STORED and e.filename.endswith(".npy") and
                    "/" not in e.filename and e.file_size <= MAX_ARRAY_BYTES for e in entries), "NPZ format/bounds")
        require(sum(e.file_size for e in entries) <= MAX_ARRAY_BYTES, "Per-attempt NPZ budget")
    with np.load(path, allow_pickle=False) as archive:
        result = {key: archive[key] for key in archive.files}
    require(all(a.dtype.kind in "biuf" and np.isfinite(a).all() for a in result.values()), "Nonfinite/unsupported captured array")
    return result


def priority_leaf(metric, alpha, np):
    # Exactly update_priorities: FP32 executed CE is first cast to FP64.
    return (np.abs(np.asarray(metric).astype(np.float64)) + 1e-6) ** alpha


def selected_min_weights(leaves, beta, np):
    leaves = np.maximum(1e-10, np.asarray(leaves, dtype=np.float64))
    return (leaves.min() / leaves) ** beta if len(leaves) else leaves.copy()


def mixed_weights(per_weights, boundaries, np):
    weights = np.ones(BATCH, dtype=np.float64)
    p = boundaries["per"]
    weights[p] = per_weights
    if per_weights.size:
        for name in ("hof", "ephof"):
            weights[boundaries[name]] = float(np.mean(per_weights))
    return weights


def describe_values(values, np):
    values = np.asarray(values, dtype=np.float64)
    if not values.size:
        return {"count": 0, "sum": 0.0, "mean": None, "min": None, "max": None}
    return dict(count=int(values.size), sum=float(values.sum()), mean=float(values.mean()),
                min=float(values.min()), max=float(values.max()))


def analyse_arrays(arrays, draw, cfg, schedule, np):
    """Pure CPU mechanics; arrays and row order are never mutated/deduplicated."""
    required = {"ce", "projected_target", "taken_action_log_probabilities", "target_action_probabilities",
                "unclipped_target_support", "per_row_bc", "per_row_q_policy", "per_row_margin",
                "weighted_loss", "bc_loss", "bc_contribution", "q_policy_contribution", "margin_contribution"}
    require(required <= set(arrays) and all(np.isfinite(arrays[name]).all() for name in required), "Missing/nonfinite same-forward field")
    ce, target, logp = (arrays[k] for k in ("ce", "projected_target", "taken_action_log_probabilities"))
    require(ce.dtype == target.dtype == logp.dtype == np.float32 and ce.shape == (BATCH,) and
            target.shape == logp.shape == (BATCH, ATOMS), "FP32 same-forward geometry")
    require(all(arrays[name].shape == (BATCH, ATOMS) for name in
                ("target_action_probabilities", "unclipped_target_support")), "Target/support geometry")
    require(np.all(target >= 0) and np.all(np.abs(target.sum(axis=1, dtype=np.float64) - 1) <= MASS_ATOL), "Invalid projected target mass")
    reconstructed_ce = -(target * logp).sum(axis=1, dtype=np.float32)
    require(np.allclose(ce, reconstructed_ce, rtol=RTOL, atol=ATOL), "Captured CE vs same-forward target/logp")
    require(draw["schema"] == "robotron-replay-draw-observation-v1" and draw.get("observer_error") is None, "Draw observation failed")
    beta, alpha = float(draw["beta"]), float(draw["alpha"])
    require(math.isfinite(beta) and 0 <= beta <= 1 and math.isfinite(alpha) and alpha > 0, "Invalid beta/alpha")
    require(len(draw["origin_boundaries"]) == 5, "Origin count")
    boundaries, cursor = {}, 0
    for expected, (name, start, stop) in zip(ORIGINS, draw["origin_boundaries"]):
        require(name == expected and type(start) is int and type(stop) is int and start == cursor and start <= stop <= BATCH, "Origin partition")
        boundaries[name], cursor = slice(start, stop), stop
    require(cursor == BATCH, "Origin rows missing")
    per = boundaries["per"]
    ring_end = boundaries["recent"].stop
    indices = draw["indices"]
    require(indices.shape == (BATCH,) and indices.dtype.kind in "iu" and np.all(indices >= 0), "Indices")
    require(np.all(indices[:ring_end] < draw["capacity"]) and np.all(indices[ring_end:] >= draw["capacity"]), "Ring/bank sentinels")
    raw = draw["per_raw_leaves"]
    require(raw.dtype == np.float64 and raw.shape == (per.stop,) and np.all(raw >= 0), "PER leaves")
    clamped = np.maximum(1e-10, raw)
    require(np.array_equal(clamped, draw["per_clamped_leaves"]), "Captured clamped leaves mismatch")
    require((float(clamped.min()) if len(clamped) else None) == draw["selected_per_min_clamped_leaf"], "Selected PER minimum mismatch")
    size, total = draw["size"], float(draw["tree_total"])
    require(type(size) is int and BATCH <= size <= draw["capacity"] and math.isfinite(total) and total > 0, "Draw size/total")
    unnormalised = (size * (clamped / total)) ** (-beta)
    require(np.array_equal(unnormalised, draw["per_raw_weights_float64"]), "Raw emitted-weight reconstruction mismatch")
    max_raw = float(unnormalised.max()) if len(raw) else None
    require(max_raw == draw["selected_per_raw_max_weight"], "Raw max mismatch")
    actual_per = unnormalised / max(1e-12, max_raw) if len(raw) else unnormalised
    actual64 = mixed_weights(actual_per, boundaries, np)
    require(np.array_equal(actual64, draw["supplied_weights_float64"]) and
            np.array_equal(actual64.astype(np.float32), draw["supplied_weights_float32"]), "Actual mixed emitted weights mismatch")
    # FP32 entropy/CE-H is the candidate convention, not a FP64 replacement CE.
    entropy = -(target * np.log(np.maximum(target, np.float32(1e-12)))).sum(axis=1, dtype=np.float32)
    raw_kl = ce - entropy
    kl = np.maximum(np.float32(0), raw_kl)
    ce_leaf, kl_leaf = priority_leaf(ce, alpha, np), priority_leaf(kl, alpha, np)
    fresh_ce64 = mixed_weights(selected_min_weights(ce_leaf[per], beta, np), boundaries, np)
    fresh_kl64 = mixed_weights(selected_min_weights(kl_leaf[per], beta, np), boundaries, np)
    weights = {name: value.astype(np.float32) for name, value in zip(VECTORS, (actual64, fresh_ce64, fresh_kl64))}
    small = draw["small_batch_fields"]
    for name in ("actions", "rewards", "dones", "horizons", "is_expert", "actor_kind"):
        require(small[name].shape == (BATCH,), "Small-field geometry: " + name)
    expert = small["is_expert"].astype(np.float32)
    require(np.all((expert == 0) | (expert == 1)), "Expert mask is not binary")
    for name in ("per_row_bc", "per_row_q_policy", "per_row_margin"):
        require(arrays[name].shape == (BATCH,), "Auxiliary vector geometry")
    for name in ("bc_loss", "weighted_loss", "bc_contribution", "q_policy_contribution", "margin_contribution"):
        require(arrays[name].shape == (), "Auxiliary scalar geometry")
    require(len(schedule) == 3 and all(math.isfinite(x) for x in schedule), "Schedule")
    count = float(expert.sum())
    bc_active = schedule[0] > 0 and count > 0
    bc_per = arrays["per_row_bc"] * expert / max(1, count) if bc_active else np.zeros(BATCH, dtype=np.float32)
    auxiliary_rows = {
        "bc": bc_per * max(float(cfg.get("expert_bc_effective_floor", .01)), schedule[0] * count / BATCH),
        "q_policy": arrays["per_row_q_policy"] * expert * max(0, schedule[1]) / BATCH,
        "margin": arrays["per_row_margin"] * expert * max(0, schedule[2]) / BATCH,
    }
    for name, values in auxiliary_rows.items():
        require(np.isclose(values.sum(dtype=np.float64), arrays[name + "_contribution"], rtol=RTOL, atol=ATOL), "Auxiliary reconstruction: " + name)
    require(np.isclose(bc_per.sum(dtype=np.float64), arrays["bc_loss"], rtol=RTOL, atol=ATOL), "BC loss reconstruction")
    auxiliary_total = sum(float(arrays[name + "_contribution"]) for name in auxiliary_rows)
    actual_objective = float(np.mean(weights["actual_emitted"] * ce, dtype=np.float32)) + auxiliary_total
    require(np.isclose(actual_objective, arrays["weighted_loss"], rtol=RTOL, atol=ATOL), "Original weighted objective mismatch")
    groups = {"all": np.ones(BATCH, dtype=bool)}
    for name, part in boundaries.items():
        selected = np.zeros(BATCH, dtype=bool); selected[part] = True
        groups["origin:" + name] = selected
    groups["expert:0"], groups["expert:1"] = expert == 0, expert == 1
    for kind in np.unique(small["actor_kind"]):
        groups["actor_kind:" + str(int(kind))] = small["actor_kind"] == kind
    contributions = {}
    for label, mask in groups.items():
        contributions[label] = dict(count=int(mask.sum()), source_fraction=float(mask.mean()),
            vectors={name: dict(weight=describe_values(w[mask], np),
                               weighted_ce_contribution=float((w[mask].astype(np.float64) * ce[mask]).sum() / BATCH))
                     for name, w in weights.items()},
            auxiliary_contributions={name: float(value[mask].sum(dtype=np.float64)) for name, value in auxiliary_rows.items()})
    ring_indices = indices[:ring_end]
    _, inverse, counts = np.unique(ring_indices, return_inverse=True, return_counts=True)
    duplicated = counts[inverse] > 1
    conflicting = 0
    for group in np.flatnonzero(counts > 1):
        values = ce[:ring_end][inverse == group]
        conflicting += int(values.max() != values.min())
    # Direct positive-support KL is a FP64 diagnostic only; never feeds leaves.
    positive = target > 0
    log_target = np.zeros_like(target, dtype=np.float64)
    np.log(target.astype(np.float64), out=log_target, where=positive)
    direct_kl64 = (target.astype(np.float64) * (log_target - logp)).sum(axis=1)
    negative_tolerance = ATOL + RTOL * np.abs(ce)
    vectors = dict(weights, actual_emitted_float64=actual64, fresh_ce_float64=fresh_ce64,
                   fresh_kl_float64=fresh_kl64,
                   ce=ce, target_entropy_fp32=entropy, raw_kl_fp32=raw_kl,
                   kl_clamped_fp32=kl, direct_kl_float64=direct_kl64,
                   kl_roundoff_sensitive=np.abs(raw_kl) <= negative_tolerance,
                   fresh_ce_leaf=ce_leaf, fresh_kl_leaf=kl_leaf, indices=indices)
    material_negative = int((raw_kl < -negative_tolerance).sum())
    report = dict(alpha=alpha, beta=beta, origins={name: part.stop-part.start for name, part in boundaries.items()},
        reconstruction=dict(actual_emitted_weights="exact float64+float32 equality", ce_max_abs_error=float(np.max(np.abs(ce-reconstructed_ce))),
                            actual_objective=actual_objective, captured_objective=float(arrays["weighted_loss"])),
        normalization=dict(actual_raw_max=max_raw, actual_denominator_floor_active=max_raw is not None and max_raw < 1e-12,
            fresh="selected-min-normalized sensitivities; hypothetical refreshed whole-tree total and denominator-floor domain are not reconstructed"),
        target_mass_max_error=float(np.max(np.abs(target.sum(axis=1, dtype=np.float64)-1))),
        metrics={name: describe_values(value, np) for name, value in
                 (("ce", ce), ("target_entropy", entropy), ("raw_kl", raw_kl), ("clamped_kl", kl))},
        interpretation_not_ready=material_negative > 0,
        interpretation_scope="Numerical raw-KL warning only; false does not qualify implementation, acquisition or learning",
        kl_roundoff=dict(raw_negative=int((raw_kl < 0).sum()), material_negative=material_negative,
            absolute_raw_le_1e_5=int((np.abs(raw_kl) <= 1e-5).sum()),
            clamped_zero_rows=int((kl == 0).sum()),
            ce_minus_entropy_vs_direct_max_abs=float(np.max(np.abs(raw_kl-direct_kl64))),
            note="NumPy FP32 entropy/log/reductions reconstruct the candidate convention, not an executed GPU KL kernel. Near-zero CPU/GPU/reduction differences may strongly change epsilon-scale leaves; clamping does not validate material negatives"),
        duplicates=dict(ring_rows=ring_end, duplicate_rows=int(duplicated.sum()), repeated_slots=int((counts>1).sum()),
            slots_with_distinct_ce=conflicting, interpretation="Original row order retained. Per-row fresh leaves are sensitivities, not an ordered last-write refreshed tree or slot-generation proof."),
        population=dict(done_rows=int((small["dones"] != 0).sum()),
            horizons={str(int(v)): int((small["horizons"] == v).sum()) for v in np.unique(small["horizons"])},
            below_support_rows=int((arrays["unclipped_target_support"] < cfg["v_min"]).any(axis=1).sum()),
            above_support_rows=int((arrays["unclipped_target_support"] > cfg["v_max"]).any(axis=1).sum())),
        groups=contributions, captured_auxiliary_total=auxiliary_total,
        paired_differences={label: dict(weight_delta=describe_values(weights[right].astype(np.float64)-weights[left], np),
            weighted_ce_contribution_delta=float(((weights[right].astype(np.float64)-weights[left])*ce).sum()/BATCH))
            for label,left,right in (("emitted_to_fresh_ce", "actual_emitted", "fresh_ce"),
                                     ("fresh_ce_to_fresh_kl", "fresh_ce", "fresh_kl"))},
        banks={name: {key:value for key,value in bank.items() if key != "selected_slots"}
               for name,bank in draw.get("banks", {}).items()},
        unknown=draw.get("unknown", {}))
    return report, vectors


def analyse(trace, bound, output, np):
    context = parse_json(read_regular(trace / "context.json", MAX_JSON_BYTES))
    status = parse_json(read_regular(trace / "status.json", MAX_JSON_BYTES))
    check_headers(context, status)
    write_json(output / "captured-context.json", context)
    rows, outcomes = [], {"applied_admission": 0, "amp_skipped": 0}
    capture_ids, last_consume, previous_exposure = set(), None, None
    for i in range(1, 9):
        row = parse_json(read_regular(trace / ("attempt-%02d.json" % i), MAX_JSON_BYTES))
        require(row["index"] == i and row["status"] == "returned_loss" and row["exception"] is None and
                row["result"] is not None and math.isfinite(row["result"]) and row["numerical_capture_complete"] and
                not row["observer_errors"] and not row.get("unavailable_auxiliary"), "Incomplete original attempt %d" % i)
        require({k:v for k,v in row.items() if k not in ("draw", "array_finite")} == status["rows"][i-1], "Status/row summary mismatch")
        outcome = check_outcome(row); outcomes[outcome] += 1
        if previous_exposure is not None:
            require(all(row["exposure_before"][key] == previous_exposure[key] for key in
                        ("process_id", "instance_monotonic_ns", "epoch", "total")), "Nonconsecutive exposure stream")
        previous_exposure = row["exposure_at_exit"]
        arrays = load_arrays(trace / ("attempt-%02d.npz" % i), np)
        require(set(row["array_finite"]) == set(arrays) and all(v is True for v in row["array_finite"].values()), "Finite manifest mismatch")
        draw = restore_metadata(row["draw"], arrays)
        capture_ids.add(draw["capture_id"])
        require(last_consume is None or row["consumed_monotonic_ns"] > last_consume, "Consumed order")
        last_consume = row["consumed_monotonic_ns"]
        require(draw["lock_observation_started_monotonic_ns"] <= draw["lock_observation_finished_monotonic_ns"] <= last_consume and
                row["draw_to_consume_ns"] == last_consume-draw["lock_observation_finished_monotonic_ns"], "Draw/consume timeline")
        if row["prefetch"] is not None:
            lease = row["prefetch"]
            require(lease["is_current_at_consumption"] and lease["lease_epoch"] == lease["owner_epoch_at_consumption"], "Invalid consumed lease")
        result, vectors = analyse_arrays(arrays, draw, context["config"], row["schedule"], np)
        require(np.isclose(row["result"], arrays["weighted_loss"], rtol=RTOL, atol=ATOL), "Returned loss differs from same-forward objective")
        result.update(index=i, optimizer_outcome=outcome, backend=row["backend"],
                      before=row["before"], after=row["after"], draw_to_consume_ns=row["draw_to_consume_ns"])
        with (output / ("weights-%02d.npz" % i)).open("xb") as stream:
            np.savez(stream, **vectors); stream.flush(); os.fsync(stream.fileno())
        write_json(output / ("analysis-%02d.json" % i), result)
        rows.append(result)
    require(len(capture_ids) == 1, "Mixed observer sessions")
    aggregate = {}
    for group in sorted({group for row in rows for group in row["groups"]}):
        # Equal4096 batch sizes: arithmetic average is the eight-attempt
        # contribution, including skipped attempts. No applied-only selection.
        aggregate[group] = dict(
            rows=sum(row["groups"].get(group, {}).get("count", 0) for row in rows),
            source_fraction=sum(row["groups"].get(group, {}).get("count", 0) for row in rows)/(8*BATCH),
            vectors={name: dict(weight_sum=sum(row["groups"].get(group, {}).get("vectors", {}).get(name, {}).get("weight", {}).get("sum", 0.) for row in rows),
                mean_batch_weighted_ce_contribution=sum(row["groups"].get(group, {}).get("vectors", {}).get(name, {}).get("weighted_ce_contribution", 0.) for row in rows)/8)
                for name in VECTORS},
            mean_batch_auxiliary_contributions={name:sum(row["groups"].get(group, {}).get("auxiliary_contributions", {}).get(name, 0.) for row in rows)/8
                                                for name in ("bc", "q_policy", "margin")})
    report = dict(schema="robotron-executed-ce-weight-sensitivity-analysis-v1", status="COMPUTED_OFFLINE_SENSITIVITY",
        attempts=8, rows_per_attempt=BATCH, provenance=bound["provenance"], optimizer_outcomes=outcomes,
        reviewed_prototype_source_sha256=PRODUCER, producer_manifest_sha256=PRODUCER_MANIFEST, rows=rows, aggregate=aggregate,
        interpretation_not_ready=any(row["interpretation_not_ready"] for row in rows),
        interpretation_scope="Material-negative raw-KL warning; no result of this analyser qualifies KL execution or learning",
        tolerances=dict(rtol=RTOL, atol=ATOL, target_mass_atol=MASS_ATOL),
        interpretation=["actual_emitted to fresh_ce: same-row priority-age sensitivity, not an isolated causal estimate",
            "fresh_ce to fresh_kl: same-row entropy-subtraction sensitivity, each with its own mean-PER bank weights",
            "All8 attempts retained, including AMP-skips. Applied admission does not certify parameter/Adam movement.",
            "CE-selected rows; not KL sampling, a coherent migrated tree, unbiased expected gradients, an LR factor, or learning/quality gain.",
            "Fresh leaf vectors are formula evaluations on all rows for inspection; bank entries never become PER leaves or receive priority updates.",
            "Stored expert/actor_kind are observable; actor_kind cannot recover evaluation identity.",
            "Full states, unsampled population, stale slot generations, priority metric identity, insertion hints/caps/boosts and conversion ages are not reconstructed."])
    write_json(output / "report.json", report)
    return report


def execute(args):
    output = Path(args.output)
    require(output.is_absolute() and not output.exists() and output.parent.is_dir(), "Explicit new absolute output with existing parent required")
    require(not output.resolve().is_relative_to(Path(args.trace).resolve()), "Output cannot be inside the input trace")
    output.mkdir()  # retain every partial analysis and failure; never overwrite/retry
    try:
        write_json(output / "request.json", dict(trace=args.trace, binding=args.binding,
            binding_sha256=args.binding_sha256, tool_sha256=args.tool_sha256))
        trace = Path(args.trace)
        bound = verify_binding(trace, args.binding, args.binding_sha256, args.tool_sha256)
        write_json(output / "input-binding.json", bound)
        import numpy as np  # only explicit future execution, never default PLAN
        analyse(trace, bound, output, np)
        # Recheck all input hashes after analysis; no concurrent writer accepted.
        verify_binding(trace, args.binding, args.binding_sha256, args.tool_sha256)
        hashes = {p.name:digest(read_regular(p, MAX_ARRAY_BYTES)) for p in output.iterdir()}
        write_json(output / "completion.json", dict(status="COMPLETE", artifacts_sha256=hashes))
        return 0
    except BaseException as error:
        try:
            write_json(output / "failure.json", dict(status="INVALID_OR_INCOMPLETE_ANALYSIS", error=type(error).__name__, message=str(error)[:1000]))
        except Exception:
            pass
        return 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--execute" not in argv:
        print(PLAN)
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    for option in ("trace", "binding", "binding-sha256", "tool-sha256", "output"):
        parser.add_argument("--" + option, required=True)
    return execute(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
