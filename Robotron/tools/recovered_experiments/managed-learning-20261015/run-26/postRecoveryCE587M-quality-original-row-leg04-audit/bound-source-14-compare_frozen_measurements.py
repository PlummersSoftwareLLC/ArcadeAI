#!/usr/bin/env python3
"""Compare completed frozen-policy receipts without changing training state.

Bootstrap percentile intervals are descriptive sensitivity checks. They do not
correct for repeated looks, policy selection, shared emulator state, or RNG drift.
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import statistics
import sys


MIN_GAMES = 50
FRAME_FIELDS = ("engine_version", "state_size", "single_frame_state_size", "frame_stack",
                "wire_params_count", "wire_version", "frame_protocol")
CLOCK_ALIASES = {"training_steps": ("training_steps", "total_training_steps"),
                 "optimized_samples": ("optimized_samples", "total_optimized_samples"),
                 "learner_frames": ("learner_frame_count",)}
CAUTION = ("Descriptive sensitivity intervals, not formal confidence or a promotion rule: "
           "repeated looks, policy selection, shared emulator state, and RNG drift are not corrected.")


def number(value, name, *, integer=False, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: expected a finite number")
    if value < 0 or (positive and value <= 0) or (integer and int(value) != value):
        raise ValueError(f"{name}: invalid nonnegative {'integer' if integer else 'number'}")
    return int(value) if integer else float(value)


def validate_receipt(receipt):
    """Fail closed on partial cohorts, changing policies, or missing evidence."""
    if not isinstance(receipt, dict):
        raise ValueError("Receipt must be a JSON object")
    cohort = receipt.get("cohort", {})
    if not isinstance(cohort, dict):
        raise ValueError("cohort must be an object")
    if receipt.get("valid") is not True or receipt.get("complete") is not True:
        raise ValueError("Receipt must be valid and complete")
    if receipt.get("active", False) is not False:
        raise ValueError("Receipt is still active")
    for source in (receipt, cohort):
        if source.get("valid", True) is not True or source.get("complete", True) is not True:
            raise ValueError("Contradictory invalid/incomplete cohort")
        if source.get("closed", True) is not True:
            raise ValueError("Cohort admission window is still open")
        for field in ("pending", "abandoned"):
            if field in source and number(source[field], field, integer=True) != 0:
                raise ValueError(f"Cohort has {field} games")
        for field in ("pending_ids", "abandoned_ids", "abandonment_reasons"):
            if source.get(field):
                raise ValueError(f"Cohort has {field}")
    for field in ("pending", "abandoned", "started", "count"):
        if field not in receipt and field not in cohort:
            raise ValueError(f"Missing cohort denominator: {field}")
    rows = receipt.get("rows", cohort.get("rows"))
    if not isinstance(rows, list) or len(rows) < MIN_GAMES:
        raise ValueError(f"At least {MIN_GAMES} whole games per leg are required")
    if "rows" in receipt and "rows" in cohort and receipt["rows"] != cohort["rows"]:
        raise ValueError("Root and cohort rows disagree")
    for source in (receipt, cohort):
        for field in ("started", "count"):
            if field in source and number(source[field], field, integer=True) != len(rows):
                raise ValueError(f"Cohort {field} does not equal the complete row count")
    label = receipt.get("label")
    if not isinstance(label, str) or not label:
        raise ValueError("Receipt needs a measurement label")
    generation = number(receipt.get("generation"), "generation", integer=True)
    start = number(receipt.get("start_ts", cohort.get("start_ts")), "start_ts")
    close = number(receipt.get("close_ts", cohort.get("close_ts")), "close_ts")
    if close <= start:
        raise ValueError("Invalid cohort admission window")
    for key, expected in (("start_ts", start), ("close_ts", close), ("experiment", label)):
        if key in cohort and cohort[key] != expected:
            raise ValueError(f"Root and cohort {key} disagree")
    saved_clocks = receipt.get("clocks", {})
    if not isinstance(saved_clocks, dict):
        raise ValueError("Saved clocks must be an object")
    boundary = receipt.get("boundary", {})
    if not isinstance(boundary, dict) or boundary.get("ready") is not True:
        raise ValueError("A completed actor/replay boundary is required")
    if boundary.get("pending_client_ids") or boundary.get("replay_pending_client_ids"):
        raise ValueError("Actor/replay boundary has pending acknowledgments")
    if boundary.get("generation", generation) != generation:
        raise ValueError("Boundary generation differs from the measured policy")
    if boundary.get("active", True) is not True:
        raise ValueError("Boundary did not acknowledge the measured policy")
    if "expected" in boundary and boundary.get("acknowledged") != boundary["expected"]:
        raise ValueError("Boundary acknowledgment count is incomplete")
    expected_slots = {number(slot, "boundary actor slot", integer=True)
                      for slot in boundary.get("actor_slots", [])}
    if not expected_slots:
        raise ValueError("Boundary actor coverage is missing")
    clocks, protocols, seen, clean_rows = [], [], set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Game row must be an object")
        identifier = row.get("journal_game_id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("Missing or duplicate game ID")
        seen.add(identifier)
        for flag in ("eligible", "complete", "known_start", "eval_only", "measurement_active"):
            if row.get(flag) is not True:
                raise ValueError(f"{identifier}: {flag} must be true")
        if row.get("excluded_reason") or row.get("first_play_level") != 1:
            raise ValueError(f"{identifier}: not an eligible wave-1 full game")
        if row.get("measurement_generation") != generation or row.get("experiment") != label:
            raise ValueError(f"{identifier}: measurement policy changed")
        normalized = dict(row)
        for field in ("score", "duration_s", "start_unix_s", "end_unix_s", "playable_frames"):
            normalized[field] = number(row.get(field), field, positive=field == "playable_frames")
        normalized["client_slot"] = number(row.get("client_slot"), "client_slot", integer=True)
        if not start <= normalized["start_unix_s"] <= close:
            raise ValueError(f"{identifier}: game started outside the admitted cohort")
        duration = normalized["end_unix_s"] - normalized["start_unix_s"]
        if duration < 0 or not math.isclose(duration, normalized["duration_s"], abs_tol=.001):
            raise ValueError(f"{identifier}: invalid duration/end time")
        for field in ("start_context", "end_context"):
            context = row.get(field)
            if not isinstance(context, dict):
                raise ValueError(f"{identifier}: missing {field}")
            if (context.get("experiment") != label or context.get("measurement_active") is not True
                    or context.get("measurement_generation") != generation):
                raise ValueError(f"{identifier}: mixed measurement context")
            if context.get("epsilon") != 0 or context.get("expert_ratio") != 0:
                raise ValueError(f"{identifier}: frozen protocol must be greedy with no expert")
            if context.get("ratchet_frozen", False) is not False:
                raise ValueError(f"{identifier}: overlaps ratchet measurement")
            clock = {key: number(context.get(key), key, integer=True) for key in CLOCK_ALIASES}
            clocks.append(clock)
            protocol = dict(epsilon=0, expert_ratio=0, first_play_level=1,
                            difficulty=number(context.get("difficulty"), "difficulty", integer=True),
                            ratchet_frozen=bool(context.get("ratchet_frozen", False)))
            for key in FRAME_FIELDS:
                value = context.get(key, row.get(key, receipt.get(key)))
                if value is not None:
                    protocol[key] = value
            protocols.append(protocol)
        clean_rows.append(normalized)
    if any(clock != clocks[0] for clock in clocks):
        raise ValueError("Learner/checkpoint clocks vary within the frozen leg")
    for field, aliases in CLOCK_ALIASES.items():
        for alias in aliases:
            saved = saved_clocks.get(alias)
            if saved is not None and number(saved, alias, integer=True) != clocks[0][field]:
                raise ValueError(f"Saved {alias} disagrees with frozen game clocks")
    if any(protocol != protocols[0] for protocol in protocols):
        raise ValueError("Frame/evaluation protocol varies within the frozen leg")
    observed_slots = {row["client_slot"] for row in clean_rows}
    if not expected_slots.issubset(observed_slots):
        raise ValueError("Cohort is missing expected actor slots")
    for source in (receipt, cohort):
        if "started_ids" in source and (len(source["started_ids"]) != len(seen)
                                       or set(source["started_ids"]) != seen):
            raise ValueError("Started game registry disagrees with completed rows")
    return dict(label=label, rows=clean_rows, clocks=clocks[0], protocol=protocols[0],
                expected_actor_slots=sorted(expected_slots), start_ts=start, close_ts=close)


def summarize(leg):
    rows = leg["rows"]
    scores = [row["score"] for row in rows]
    durations = [row["duration_s"] for row in rows]
    frames = [row["playable_frames"] for row in rows]
    return dict(label=leg["label"], count=len(rows), mean=statistics.mean(scores),
                median=statistics.median(scores), se=statistics.stdev(scores)/math.sqrt(len(rows)),
                actor_slot_counts=dict(sorted(Counter(str(row["client_slot"]) for row in rows).items())),
                expected_actor_slots=leg["expected_actor_slots"], clocks=leg["clocks"],
                protocol=leg["protocol"], duration_s=dict(mean=statistics.mean(durations),
                    median=statistics.median(durations), maximum=max(durations), total=sum(durations)),
                playable_frames=dict(total=sum(frames), mean=statistics.mean(frames),
                                     median=statistics.median(frames)),
                admission_window_s=leg["close_ts"]-leg["start_ts"],
                observed_wall_span_s=max(row["end_unix_s"] for row in rows)-leg["start_ts"])


def percentile(values, probability):
    values = sorted(values)
    position = (len(values)-1)*probability
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi]-values[lo])*(position-lo)


def bootstrap(base, candidate, *, iterations, seed, cluster=False):
    rng = random.Random(seed)
    groups = []
    for rows in (base, candidate):
        slots = defaultdict(list)
        for row in rows:
            slots[row["client_slot"]].append(row["score"])
        groups.append(dict(sorted(slots.items())))
    paired = cluster and set(groups[0]) == set(groups[1])
    differences, ratios = [], []
    for _ in range(iterations):
        means = []
        paired_draw = rng.choices(list(groups[0]), k=len(groups[0])) if paired else None
        for rows, slots in zip((base, candidate), groups):
            if cluster:
                draw = paired_draw if paired else rng.choices(list(slots), k=len(slots))
                scores = [score for slot in draw for score in slots[slot]]
            else:
                scores = rng.choices(rows, k=len(rows))
                scores = [row["score"] for row in scores]
            means.append(statistics.fmean(scores))
        differences.append(means[1]-means[0])
        if means[0] > 0:
            ratios.append(means[1]/means[0])
    return dict(method=("paired actor-slot clusters" if paired else "independent actor-slot clusters"
                        if cluster else "independent games"),
                iterations=iterations, seed=seed, percentile=.95,
                mean_difference_ci=[percentile(differences, .025), percentile(differences, .975)],
                mean_ratio_ci=([percentile(ratios, .025), percentile(ratios, .975)] if ratios else None),
                ratio_defined_resamples=len(ratios), actor_clusters=[len(group) for group in groups])


def compare_receipts(baseline, candidate, *, iterations=5000, seed=20261015):
    if iterations < 100:
        raise ValueError("At least 100 bootstrap iterations are required")
    legs = [validate_receipt(receipt) for receipt in (baseline, candidate)]
    if legs[0]["protocol"] != legs[1]["protocol"]:
        raise ValueError("Frame/evaluation protocols differ between legs")
    summaries = [summarize(leg) for leg in legs]
    base_mean, candidate_mean = [summary["mean"] for summary in summaries]
    warnings = [CAUTION]
    if not any(field in legs[0]["protocol"] for field in FRAME_FIELDS):
        warnings.append("Engine/wire/frame-stack metadata was not recorded; only the recorded evaluation protocol is matched.")
    if set(summaries[0]["actor_slot_counts"]) != set(summaries[1]["actor_slot_counts"]):
        warnings.append("Actor coverage differs; actor-cluster resampling is independent between legs.")
    if {row["journal_game_id"] for row in legs[0]["rows"]} & {row["journal_game_id"] for row in legs[1]["rows"]}:
        warnings.append("Game IDs overlap between legs; this is not an independent replication.")
    return dict(baseline=summaries[0], candidate=summaries[1],
                score_delta=candidate_mean-base_mean,
                score_ratio=candidate_mean/base_mean if base_mean else None,
                game_bootstrap=bootstrap(legs[0]["rows"], legs[1]["rows"], iterations=iterations, seed=seed),
                actor_cluster_bootstrap=bootstrap(legs[0]["rows"], legs[1]["rows"],
                                                 iterations=iterations, seed=seed, cluster=True),
                warnings=warnings)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--output", type=Path, help="Write the comparison JSON to this file")
    args = parser.parse_args(argv)
    try:
        report = compare_receipts(json.loads(args.baseline.read_text()),
                                  json.loads(args.candidate.read_text()),
                                  iterations=args.iterations, seed=args.seed)
        report["sources"] = dict(baseline=str(args.baseline), candidate=str(args.candidate))
        if args.output:
            if args.output.resolve() in (args.baseline.resolve(), args.candidate.resolve()):
                raise ValueError("Output must not overwrite an input receipt")
            args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    except (OSError, ValueError, TypeError) as exc:
        print(f"Comparison rejected: {exc}", file=sys.stderr)
        return 2
    print("Leg        N       Mean     Median         SE   Actors    Mean s   Play frames")
    for name in ("baseline", "candidate"):
        leg = report[name]
        print(f"{name:<9} {leg['count']:>4} {leg['mean']:>10,.1f} {leg['median']:>10,.1f} "
              f"{leg['se']:>10,.1f} {len(leg['actor_slot_counts']):>8} "
              f"{leg['duration_s']['mean']:>9.1f} {leg['playable_frames']['total']:>13,.0f}")
        print(f"  Actor game counts: {json.dumps(leg['actor_slot_counts'], sort_keys=True)}")
    ratio = "undefined" if report['score_ratio'] is None else f"{report['score_ratio']:.3f}x"
    print(f"Candidate mean delta: {report['score_delta']:+,.1f}; ratio: {ratio}")
    for key in ("game_bootstrap", "actor_cluster_bootstrap"):
        result = report[key]
        diff = ', '.join(f'{value:+,.1f}' for value in result['mean_difference_ci'])
        ratios = result['mean_ratio_ci']
        ratio_ci = ', '.join(f'{value:.3f}' for value in ratios) if ratios else 'undefined'
        print(f"  {result['method']}, 95% percentile interval: delta [{diff}], ratio [{ratio_ci}]")
    for warning in report["warnings"]:
        print(warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
