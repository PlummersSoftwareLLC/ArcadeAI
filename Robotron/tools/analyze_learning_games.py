#!/usr/bin/env python3
"""Read-only summaries and comparisons of full-game learning journals.

Examples:
  python Robotron/tools/analyze_learning_games.py RUN_DIR --baseline baseline-high-exploration
  python Robotron/tools/analyze_learning_games.py RUN_DIR --baseline baseline-high-exploration \
      --candidate epsilon-50 --skip 0 --limit 50 --output first-block.json
  python Robotron/tools/analyze_learning_games.py RUN_DIR --baseline baseline-high-exploration \
      --candidate epsilon-50 --skip 50 --limit 50 --output confirmation-block.json

Blocks are ordered by completion time within each experiment.  They have no
overlapping games when skip/limit ranges do not overlap.  A completed-game log
cannot establish that every game in a start-side cohort has finished.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import statistics
import sys


BOOTSTRAP_ASSUMPTION = (
    "iid-game approximation: independent resampling of completed games; shared clients, "
    "a changing policy, repeated looks, and multiple comparisons are not accounted for"
)


def percentile(sorted_values, probability):
    if not sorted_values:
        return None
    position = (len(sorted_values)-1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    weight = position-lower
    return sorted_values[lower]*(1-weight) + sorted_values[upper]*weight


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def journal_paths(inputs):
    paths = set()
    for value in inputs:
        path = Path(value).expanduser()
        if path.is_dir():
            paths.update(item.resolve() for item in path.rglob("games.jsonl"))
        elif path.is_file():
            paths.add(path.resolve())
        else:
            raise ValueError(f"Journal path does not exist: {path}")
    if not paths:
        raise ValueError("No games.jsonl journals found")
    return sorted(paths)


def read_games(paths):
    """Take one file snapshot; tolerate a concurrent append's incomplete last line."""
    rows, seen, diagnostics, warnings = [], set(), Counter(), []
    for path in paths:
        data = path.read_bytes()
        lines = data.splitlines()
        for index, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                if index == len(lines) and not data.endswith(b"\n"):
                    diagnostics["incomplete_trailing_lines"] += 1
                    warnings.append(f"Ignored incomplete last line while reading {path}")
                    continue
                raise ValueError(f"Invalid JSON at {path}:{index}")
            diagnostics["raw_records"] += 1
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object at {path}:{index}")
            identifier = row.get("journal_game_id")
            if not identifier:
                diagnostics["missing_game_id"] += 1
                continue
            if identifier in seen:
                diagnostics["duplicate_game_ids"] += 1
                continue
            seen.add(identifier)
            if row.get("eligible") is not True:
                diagnostics["ineligible_records"] += 1
                continue
            if row.get("complete") is not True or row.get("known_start") is not True:
                diagnostics["inconsistent_eligibility"] += 1
                continue
            if row.get("eval_only") is not True:
                diagnostics["training_games"] += 1
                continue
            try:
                values = [float(row[key]) for key in (
                    "score", "playable_frames", "duration_s", "start_unix_s", "end_unix_s")]
            except (KeyError, TypeError, ValueError):
                diagnostics["invalid_numeric_records"] += 1
                continue
            score, frames, duration, start, end = values
            if (not all(math.isfinite(value) for value in values)
                    or score < 0 or frames <= 0 or duration < 0 or end < start):
                diagnostics["invalid_numeric_records"] += 1
                continue
            row.update(score=score, playable_frames=frames, duration_s=duration,
                       start_unix_s=start, end_unix_s=end)
            label = row.get("experiment", "")
            if not isinstance(label, str):
                diagnostics["invalid_experiment"] += 1
                continue
            contexts = (row.get("start_context", {}), row.get("end_context", {}))
            if any(not isinstance(context, dict) or context.get("experiment", label) != label
                   for context in contexts):
                diagnostics["experiment_crossing_records"] += 1
                continue
            rows.append(row)
            diagnostics["eligible_full_eval_games"] += 1
    for key in ("inconsistent_eligibility", "invalid_numeric_records", "missing_game_id",
                "invalid_experiment", "experiment_crossing_records"):
        if diagnostics[key]:
            warnings.append(f"Excluded {diagnostics[key]} records: {key}")
    rows.sort(key=lambda row: (row["end_unix_s"], row["journal_game_id"]))
    return rows, dict(diagnostics), warnings


def select_block(rows, label, skip=0, limit=None):
    available = [row for row in rows if row["experiment"] == label]
    selected = available[skip:] if limit is None else available[skip:skip+limit]
    return selected, dict(order="completion_time", skip=skip, limit=limit,
                         available=len(available), selected=len(selected),
                         game_ids=[row["journal_game_id"] for row in selected])


def summarize(rows, label, selection):
    scores = [row["score"] for row in rows]
    durations = sorted(row["duration_s"] for row in rows)
    n = len(scores)
    sd = statistics.stdev(scores) if n > 1 else None
    result = dict(
        experiment=label, count=n, mean=statistics.mean(scores) if n else None,
        median=statistics.median(scores) if n else None, sd=sd,
        se=sd/math.sqrt(n) if sd is not None else None,
        minimum=min(scores) if n else None, maximum=max(scores) if n else None,
        zero_score_games=scores.count(0), total_score=sum(scores),
        total_observed_playable_frames=sum(row["playable_frames"] for row in rows),
        score_per_observed_playable_frame=None,
        duration_s=dict(mean=statistics.mean(durations) if n else None,
                        median=statistics.median(durations) if n else None,
                        p90=percentile(durations, .9), maximum=max(durations) if n else None),
        selection=selection,
        client_slot_counts=dict(Counter(str(row["client_slot"]) for row in rows)),
    )
    if not n:
        return result
    result["score_per_observed_playable_frame"] = (
        sum(scores)/result["total_observed_playable_frames"])
    first_start = min(row["start_unix_s"] for row in rows)
    last_start = max(row["start_unix_s"] for row in rows)
    first_end = rows[0]["end_unix_s"]
    last_end = rows[-1]["end_unix_s"]
    result["windows"] = dict(
        first_start_utc=utc(first_start), last_start_utc=utc(last_start),
        first_completion_utc=utc(first_end), last_completion_utc=utc(last_end),
        start_span_s=last_start-first_start, completion_span_s=last_end-first_end,
        last_start_to_last_completion_s=last_end-last_start,
    )
    result["clocks"] = {}
    for key in ("fleet_frames", "learner_frames", "optimized_samples", "training_steps"):
        starts = [row.get("start_context", {}).get(key) for row in rows]
        ends = [row.get("end_context", {}).get(key) for row in rows]
        starts = [value for value in starts if isinstance(value, (int, float))]
        ends = [value for value in ends if isinstance(value, (int, float))]
        if starts and ends:
            result["clocks"][key] = dict(first_start=min(starts), last_start=max(starts),
                                         first_completion=min(ends), last_completion=max(ends),
                                         observed_span=max(ends)-min(starts))
    return result


def bootstrap_comparison(baseline, candidate, *, iterations=5000, seed=20261015, confidence=.95):
    """Percentile intervals from deterministic, independently resampled game means."""
    base_scores = [row["score"] for row in baseline]
    candidate_scores = [row["score"] for row in candidate]
    if not base_scores or not candidate_scores:
        return None
    rng = random.Random(seed)
    differences, ratios = [], []
    nb, nc = len(base_scores), len(candidate_scores)
    for _ in range(iterations):
        base_mean = sum(rng.choices(base_scores, k=nb))/nb
        candidate_mean = sum(rng.choices(candidate_scores, k=nc))/nc
        differences.append(candidate_mean-base_mean)
        if base_mean > 0:
            ratios.append(candidate_mean/base_mean)
    differences.sort()
    ratios.sort()
    tail = (1-confidence)/2
    base_mean, candidate_mean = statistics.mean(base_scores), statistics.mean(candidate_scores)
    ratio = candidate_mean/base_mean if base_mean else None
    ratio_ci = [percentile(ratios, tail), percentile(ratios, 1-tail)] if ratios else None
    return dict(
        method="percentile bootstrap", assumption=BOOTSTRAP_ASSUMPTION,
        iterations=iterations, seed=seed, confidence=confidence,
        mean_difference=dict(estimate=candidate_mean-base_mean,
                             ci=[percentile(differences, tail), percentile(differences, 1-tail)]),
        mean_ratio=dict(estimate=ratio, ci=ratio_ci, defined_resamples=len(ratios)),
        relative_change_pct=dict(estimate=100*(ratio-1) if ratio is not None else None,
                                 ci=[100*(value-1) for value in ratio_ci] if ratio_ci else None),
    )


def comparison_warnings(baseline, candidate):
    warnings = []
    for key, name in (("completion_span_s", "completion-window spans"),
                      ("last_start_to_last_completion_s", "completion tails")):
        left, right = baseline.get("windows", {}).get(key), candidate.get("windows", {}).get(key)
        if left is not None and right is not None:
            ratio = (1.0 if left == right else max(left, right)/min(left, right)
                     if min(left, right) > 0 else math.inf)
            if ratio > 1.25:
                warnings.append(f"Baseline/candidate {name} differ by more than 25% "
                                f"({left:.1f}s vs {right:.1f}s); completion selection may differ")
    left, right = baseline["duration_s"]["p90"], candidate["duration_s"]["p90"]
    if left is not None and right is not None and min(left, right) > 0:
        if max(left, right)/min(left, right) > 1.25:
            warnings.append(f"Game-duration p90 differs by more than 25% ({left:.1f}s vs {right:.1f}s); "
                            "long-game tails need particular care")
    left_slots, right_slots = set(baseline["client_slot_counts"]), set(candidate["client_slot_counts"])
    if left_slots != right_slots:
        warnings.append("Baseline/candidate contributing evaluation client slots differ")
    return warnings


def make_report(paths, *, baseline=None, candidate=None, experiments=None, skip=0, limit=None,
                baseline_skip=0, baseline_limit=None, iterations=5000, seed=20261015, confidence=.95):
    rows, diagnostics, warnings = read_games(paths)
    warnings.append("Completion-time samples: unfinished games are absent; this journal cannot prove "
                    "that a start-side cohort has fully drained. Check tails before accepting an improvement.")
    labels = ([baseline] + ([candidate] if candidate else [])) if baseline else (
        experiments or sorted({row["experiment"] for row in rows}))
    groups, selected = {}, {}
    for label in labels:
        is_candidate = label == candidate
        offset = skip if is_candidate else baseline_skip if label == baseline else 0
        length = limit if is_candidate else baseline_limit if label == baseline else None
        block, selection = select_block(rows, label, offset, length)
        selected[label] = block
        groups[label] = summarize(block, label, selection)
        if len(block) < 30:
            warnings.append(f"{label}: n={len(block)} <30 full evaluation games; uncertainty is large")
        if length is not None and len(block) < length:
            warnings.append(f"{label}: requested {length} games after skip={offset}; only {len(block)} available")
    comparison = None
    if candidate:
        comparison = bootstrap_comparison(selected[baseline], selected[candidate],
                                          iterations=iterations, seed=seed, confidence=confidence)
        warnings.extend(comparison_warnings(groups[baseline], groups[candidate]))
        warnings.append(BOOTSTRAP_ASSUMPTION)
        if comparison and comparison["mean_ratio"]["defined_resamples"] < iterations:
            warnings.append("Some bootstrap baseline means are zero; ratio interval conditions on positive "
                            "baseline means. Use the mean-difference interval instead.")
        if comparison is None:
            warnings.append("Comparison unavailable: both labels need at least one eligible full evaluation game")
    return dict(schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(),
                source_journals=[str(path) for path in paths], diagnostics=diagnostics,
                groups=groups, baseline=baseline, candidate=candidate,
                comparison=comparison, warnings=warnings)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("journals", nargs="+", help="games.jsonl files or directories searched recursively")
    parser.add_argument("--experiment", action="append", help="summarize only this label (repeatable)")
    parser.add_argument("--baseline", help="baseline experiment label")
    parser.add_argument("--candidate", help="candidate label; requires --baseline")
    parser.add_argument("--skip", type=int, default=0, help="skip this many candidate completions")
    parser.add_argument("--limit", type=int, help="maximum candidate games; next independent block uses skip+limit")
    parser.add_argument("--baseline-skip", type=int, default=0)
    parser.add_argument("--baseline-limit", type=int)
    parser.add_argument("--bootstrap", type=int, default=5000, help="bootstrap resamples (default 5000)")
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--confidence", type=float, default=.95)
    parser.add_argument("--output", type=Path, help="write the complete report JSON here")
    parser.add_argument("--json", action="store_true", help="print JSON instead of the concise table")
    args = parser.parse_args(argv)
    if args.candidate and (not args.baseline or args.candidate == args.baseline):
        parser.error("--candidate requires a distinct --baseline label")
    if args.experiment and (args.baseline or args.candidate):
        parser.error("Use --experiment for summaries, or --baseline/--candidate for comparison")
    if (args.skip or args.limit is not None) and not args.candidate:
        parser.error("--skip/--limit select candidate blocks and require --candidate")
    if (args.baseline_skip or args.baseline_limit is not None) and not args.baseline:
        parser.error("--baseline-skip/--baseline-limit require --baseline")
    if args.baseline_skip < 0 or args.skip < 0 or any(
            value is not None and value < 1 for value in (args.limit, args.baseline_limit)):
        parser.error("skip must be nonnegative and limit must be positive")
    if args.bootstrap < 100 or not 0 < args.confidence < 1:
        parser.error("--bootstrap must be >=100 and --confidence must be between 0 and 1")
    try:
        paths = journal_paths(args.journals)
        if args.output and args.output.resolve() in paths:
            parser.error("--output must not overwrite a source journal")
        report = make_report(
            paths, baseline=args.baseline, candidate=args.candidate, experiments=args.experiment,
            skip=args.skip, limit=args.limit, baseline_skip=args.baseline_skip,
            baseline_limit=args.baseline_limit, iterations=args.bootstrap, seed=args.seed,
            confidence=args.confidence)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    output = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n")
    if args.json:
        print(output)
    else:
        print(f"{'Experiment':34} {'Games':>6} {'Mean':>10} {'Median':>10} {'SD':>10} {'SE':>10} "
              f"{'Pts/playframe':>13} {'Mean seconds':>13}")
        def fmt(value, precision=0):
            return f"{value:,.{precision}f}" if value is not None else "NA"
        for label, group in report["groups"].items():
            print(f"{label:34} {group['count']:>6} {fmt(group['mean']):>10} {fmt(group['median']):>10} "
                  f"{fmt(group['sd']):>10} {fmt(group['se']):>10} "
                  f"{fmt(group['score_per_observed_playable_frame'], 4):>13} "
                  f"{fmt(group['duration_s']['mean'], 1):>13}")
        if report["comparison"]:
            comparison = report["comparison"]
            difference = comparison["mean_difference"]
            ratio = comparison["mean_ratio"]
            ci = difference["ci"]
            print(f"Mean difference: {difference['estimate']:+,.0f}; "
                  f"{100*comparison['confidence']:.0f}% CI [{ci[0]:+,.0f}, {ci[1]:+,.0f}]")
            if ratio["ci"] is not None:
                print(f"Mean ratio (candidate/baseline): {fmt(ratio['estimate'], 4)}; "
                      f"CI [{ratio['ci'][0]:.4f}, {ratio['ci'][1]:.4f}]")
            print(BOOTSTRAP_ASSUMPTION)
        for warning in report["warnings"]:
            print(f"Warning: {warning}", file=sys.stderr)
        if args.output:
            print(f"JSON report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
