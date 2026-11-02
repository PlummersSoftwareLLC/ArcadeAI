#!/usr/bin/env python3
"""Render the saved progress JSON; validate inputs and write only the PNG.

Requires matplotlib and Pillow. Example:
  python tools/render_learning_progress.py logs/managed-learning-20261015/learning-and-throughput-progress.json
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.ticker import FuncFormatter
from PIL import Image

try:
    from .compare_frozen_measurements import validate_receipt
    from .compare_sidecar_measurements import validate_backend, JOB_FIELDS
except ImportError:
    from compare_frozen_measurements import validate_receipt
    from compare_sidecar_measurements import validate_backend, JOB_FIELDS


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b""):
            result.update(block)
    return result.hexdigest()


def check_sources(data):
    for source in data["sources"]:
        if digest(source["path"]) != source["sha256"]:
            raise ValueError(f"Source changed: {source['path']}")


def validate_protected_annotation(data):
    """Actual384M protection stays separate from the historical600s curves."""
    proof = data["protected_incumbent_annotation"]
    if proof["stage"] != "384M":
        raise ValueError("Another incumbent requires separately reviewed reporting evidence")
    def bound(name):
        pin = proof["evidence"][name]
        if digest(pin["path"]) != pin["sha256"]:
            raise ValueError("Changed protected reporting evidence: " + name)
        return json.loads(Path(pin["path"]).read_text())
    def current_incumbent():
        actual = json.loads(Path(proof["state_path"]).read_text())["incumbent"]
        if actual != proof["state_incumbent"]:
            raise ValueError("Managed incumbent changed; do not render stale protection")
        return actual
    incumbent = current_incumbent()
    metadata, summary = bound("metadata"), bound("summary")
    cpu, adoption = bound("CPU_verification"), bound("root_adoption")
    publication, final_gate = bound("publication_review"), bound("independent_final_gate")
    if (str((Path(proof["game_root"]) / incumbent["checkpoint"]).resolve()) != proof["protected_checkpoint"]
            or incumbent["sha256"] != proof["checkpoint_sha256"]
            or metadata["checkpoint_sha256"] != proof["checkpoint_sha256"]
            or metadata["protected_checkpoint"] != proof["protected_checkpoint"]
            or metadata["plan_sha256"] != summary["plan_sha256"]
            or metadata["assessment"]["qualified_improvement"] is not True
            or summary["qualified_improvement"] is not True
            or summary["outcome"] != "qualified_improvement"):
        raise ValueError("Protected confirmation identity/provenance differs")
    adopted = {key: value for key, value in incumbent.items()
               if key not in ("root_promotion_receipt", "root_promotion_receipt_sha256")}
    if (adoption["status"] != "PASS384_PROTECTED_QUALIFIED_MANAGED_INCUMBENT_ADOPTED_NEXT_REFERENCE384"
            or adoption["new_incumbent"] != adopted
            or adoption["next_fixed_reference"] != incumbent["checkpoint"]
            or adoption["publication_review_sha256"] != proof["evidence"]["publication_review"]["sha256"]
            or adoption["all_original_games_audited"] != 377
            or adoption["main_learner_restored_or_restarted"] is not False
            or adoption["training_recipe_affinity_or_model_structure_changed"] is not False
            or publication["original_publication_exit"] != 0
            or publication["publication_child_reaped"] is not True
            or publication["both_independent_candidate_gates_pass"] is not True
            or publication["checkpoint_sha256"] != proof["checkpoint_sha256"]
            or publication["metadata_sha256"] != proof["evidence"]["metadata"]["sha256"]):
        raise ValueError("Publication and actual managed adoption are not established")
    if (cpu["status"] != "PASS" or cpu["sha256"] != proof["checkpoint_sha256"]
            or cpu["cuda_initialized"] is not False or cpu["visible_cuda_devices"] != 0
            or cpu["clocks"]["learner_frame_count"] != 388633116
            or final_gate["status"] != "PASS"
            or not all(item["mean_pass"] and item["median_pass"]
                       for item in final_gate["individual_candidate_gates"])):
        raise ValueError("Actual CPU and independent final gate proof differ")
    if data["fixed_transport_learning"][-1]["checkpoint_sha256"] != "5076199285752a8748ce9566bc74c6b67210a03ae7f04f132f92b786dea102da":
        raise ValueError("Keep the historical600s curve through192M")
    all_ids, candidates, references, candidate_counts = set(), [], [], []
    common = None
    for item, audit_pin in zip(summary["legs"], proof["original_row_audits"]):
        path = item["receipt_path"]
        if (item["returncode"] != 0 or item["valid"] is not True
                or digest(path) != item["receipt_sha256"]
                or metadata["evidence_sha256"].get(path) != item["receipt_sha256"]
                or digest(audit_pin["path"]) != audit_pin["sha256"]):
            raise ValueError("Completed campaign leg differs from protected evidence")
        receipt = json.loads(Path(path).read_text())
        audit = json.loads(Path(audit_pin["path"]).read_text())
        leg = validate_receipt(receipt)
        validate_backend(receipt, verify_checkpoint=False)
        ids = {row["journal_game_id"] for row in leg["rows"]}
        if (all_ids & ids or ids != set(item["included_game_ids"])
                or sorted(ids) != audit["admission_ids"] or audit["valid"] is not True
                or audit["receipt_sha256"] != item["receipt_sha256"]
                or audit["leg"] != item["index"] or audit["role"] != item["role"]
                or receipt["job"]["cohort_s"] != 1200.0
                or receipt["job"]["timeout_s"] != 2400.0
                or receipt["job"]["game_boundary_diagnostics"] is not True
                or receipt["source_hashes"] != metadata["evaluator_source_hashes"]
                or receipt["ended_source_hashes"] != receipt["source_hashes"]):
            raise ValueError("Original full-tail1200s/diagnosticsTRUE evidence differs")
        signature = dict(numeric=receipt["numeric_policy"], runtime=receipt["runtime"],
                         boot=receipt["boot_assets"]["identity"],
                         job={key: value for key, value in receipt["job"].items()
                              if key not in ("checkpoint", "directory", "label")})
        common = signature if common is None else common
        if signature != common:
            raise ValueError("Actual384 confirmation source/backend cohort contexts differ")
        all_ids.update(ids)
        if item["role"] == "candidate":
            if (receipt["checkpoint_sha256"] != proof["checkpoint_sha256"]
                    or any(receipt["clocks"][key] != cpu["clocks"][key]
                           for key in ("training_steps", "optimized_samples", "learner_frame_count"))):
                raise ValueError("Confirmed candidate checkpoint/clocks differ")
            candidates.append(leg["rows"])
            candidate_counts.append(len(leg["rows"]))
        else:
            references.extend(leg["rows"])
    if (len(summary["legs"]) != 4 or len(proof["original_row_audits"]) != 4
            or len(all_ids) != 377 or len(references) != 205 or candidate_counts != [85, 87]):
        raise ValueError("Actual377-game confirmation counts differ")
    ref_scores = [row["score"] for row in references]
    mean_floor, median_floor = 1.05 * statistics.mean(ref_scores), statistics.median(ref_scores)
    if not all(statistics.mean(row["score"] for row in cohort) >= mean_floor
               and statistics.median(row["score"] for row in cohort) >= median_floor
               for cohort in candidates):
        raise ValueError("Both separate candidates must pass the same fresh205-reference gates")
    scores = [row["score"] for cohort in candidates for row in cohort]
    actual = dict(count=len(scores), mean=statistics.mean(scores),
                  median=statistics.median(scores),
                  se=statistics.stdev(scores) / math.sqrt(len(scores)))
    if not all(math.isclose(actual[key], proof["descriptive_candidate_pool"][key], rel_tol=1e-12)
               for key in actual):
        raise ValueError("Separate descriptive confirmation statistics differ")
    current_incumbent()
    return proof


def validate_data(data):
    check_sources(data)
    validate_protected_annotation(data)
    seen, protocols, cohorts = set(), {}, 0
    backend_references = {}
    for group in [*data["learning"], *data.get("sidecar_learning", []),
                  *data.get("fixed_transport_learning", []), *data.get("observational_guards", []),
                  *data.get("unplotted_guard_history", [])]:
        rows, labels, counts = [], [], []
        series = group.get("backend_series", "historical-gb300")
        checkpoint = None
        policy_clocks = None
        for path in group["source_receipts"]:
            receipt = json.loads(Path(path).read_text())
            leg = validate_receipt(receipt)
            identifiers = {row["journal_game_id"] for row in leg["rows"]}
            if seen & identifiers:
                raise ValueError("Constituent cohorts have overlapping games")
            seen.update(identifiers)
            protocols.setdefault(series, leg["protocol"])
            if leg["protocol"] != protocols[series]:
                raise ValueError("Recorded evaluation protocols differ within a backend series")
            if series.startswith("gpu0-"):
                leg = validate_backend(receipt, verify_checkpoint=series == "gpu0-compiled-fixed-transport-3s")
                provenance = data["sidecar_provenance"] if series == "gpu0-compiled-before-transport-fix" else data["fixed_transport_provenance"]
                for field, expected in provenance["matching_receipt_fields"].items():
                    if receipt.get(field) != expected:
                        raise ValueError(f"Sidecar backend/provenance differs: {path} / {field}")
                if receipt["source_hashes"] != receipt["ended_source_hashes"]:
                    raise ValueError("Sidecar sources changed within a quality leg")
                if receipt.get("cleanup_errors") or receipt.get("server_error") or receipt.get("inference_error"):
                    raise ValueError("Sidecar runtime/cleanup failure")
                expected_job = provenance["job_controls"]
                if {key: receipt["job"].get(key) for key in expected_job} != expected_job:
                    raise ValueError("Sidecar job controls differ")
                if receipt["boot_assets"]["identity"] != provenance["boot_identity"]:
                    raise ValueError("Sidecar boot identity differs")
                if receipt["checkpoint_sha256"] != group["checkpoint_sha256"]:
                    raise ValueError("Sidecar policy differs from saved figure identity")
                checkpoint = receipt["checkpoint_sha256"] if checkpoint is None else checkpoint
                if receipt["checkpoint_sha256"] != checkpoint:
                    raise ValueError("Sidecar policy differs within a pooled point")
                policy_clocks = leg["clocks"] if policy_clocks is None else policy_clocks
                if leg["clocks"] != policy_clocks:
                    raise ValueError("Saved actor clocks differ within a pooled point")
                reference = backend_references.setdefault(series, receipt)
                if any(receipt["job"][field] != reference["job"][field] for field in JOB_FIELDS):
                    raise ValueError("Private backend job fields differ within a series")
                if (receipt["boot_assets"]["files"] != reference["boot_assets"]["files"]
                        or receipt["socket_wait"]["sha256"] != reference["socket_wait"]["sha256"]):
                    raise ValueError("Private boot files or pacing binary differ within a series")
            labels.append(leg["label"])
            counts.append(len(leg["rows"]))
            rows.extend(leg["rows"])
            cohorts += 1
        scores = [row["score"] for row in rows]
        expected = dict(count=len(rows), mean=statistics.mean(scores),
                        median=statistics.median(scores),
                        se=statistics.stdev(scores) / math.sqrt(len(scores)))
        if labels != group["constituent_labels"] or counts != group["constituent_counts"]:
            raise ValueError("Constituent cohort labels/counts differ from figure data")
        for key, value in expected.items():
            if not math.isclose(group[key], value, rel_tol=1e-12):
                raise ValueError(f"Figure statistic differs: {group['label']} / {key}")
    trials = [*data["throughput"]["select_v1"], data["throughput"]["busy_32_reference"],
              data["throughput"]["additional_not_plotted"]["trial"]]
    for trial in trials:
        source = json.loads(Path(trial["source"]).read_text())
        for key, expected in trial["means"].items():
            measured = statistics.mean(float(row[key]) for row in source["rows"])
            if not math.isclose(measured, expected, rel_tol=1e-10):
                raise ValueError(f"Throughput statistic differs: {trial['source']} / {key}")
    for guard in data.get("observational_guards", []):
        if (guard["role"] != "single-cohort-regression-guard" or guard["promoted"] is not False
                or len(guard["source_receipts"]) != 1):
            raise ValueError("Guard must remain a separate unpromoted single cohort")
    for guard in data.get("unplotted_guard_history", []):
        if (guard["role"] != "unpromoted-regression-guard-history" or guard["promoted"] is not False
                or guard["plotted"] is not False or len(guard["source_receipts"]) != 1):
            raise ValueError("Unplotted guards must remain separate unpromoted original cohorts")
    event = data.get("bank_output_first_events")
    if event is not None:
        compared = json.loads(Path(event["comparison_source"]).read_bytes())
        if event["comparison"] != compared["comparison"]:
            raise ValueError("Bank event observation differs from its pinned comparison")
    batch_trials = validate_batch_aba(data)
    return dict(validated_cohorts=cohorts, disjoint_games=len(seen),
                validated_batch_trials=batch_trials,
                observational_guard_count=len(data.get("observational_guards", [])),
                separate_backend_series=sorted(protocols))


def quality_series_axis(axis, groups, title, subtitle, baseline_label, baseline_color,
                        *, positions=None, gain_reference_index=0):
    means, errors = [g["mean"] for g in groups], [g["se"] for g in groups]
    positions = list(range(len(groups))) if positions is None else positions
    axis.plot(positions, means, color="#c2bdc9", lw=1.6)
    for index, (mean, error) in enumerate(zip(means, errors)):
        axis.errorbar(positions[index], mean, yerr=error, fmt="o", ms=8, capsize=4,
                      color="#00866a" if index == len(groups)-1 else baseline_color, elinewidth=1.6)
        axis.text(positions[index], mean+error+2500, f"{mean:,.0f}", ha="center", va="bottom",
                  fontsize=10, fontweight="bold")
    axis.set_xticks(positions, [g["plot_label"] for g in groups])
    axis.tick_params(axis="x", length=0, pad=10)
    axis.set_xlim(min(positions)-.4, max(positions)+.4)
    upper = math.ceil(max(m+e+7500 for m, e in zip(means, errors))/10000)*10000
    axis.set_ylim(0, upper)
    axis.set_yticks(range(0, upper+1, 20000))
    axis.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y/1000:g}K"))
    axis.set_ylabel("Mean game score")
    axis.grid(axis="y", color="#e9eef1", lw=.8)
    axis.set_axisbelow(True)
    axis.set_title(title, loc="left", pad=33, fontweight="bold")
    axis.text(0, 1.045, subtitle, transform=axis.transAxes, fontsize=9, color="#667786")
    gain = (means[-1]/means[gain_reference_index]-1)*100
    axis.text(.04, .065, f"+{gain:.1f}% vs {baseline_label}", transform=axis.transAxes,
        color="#00755f", fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=.6", fc="#edf8f2", ec="none"))
    return upper, gain


def observational_guard_overlay(axis, groups, guards, order=None):
    if not guards:
        return axis.get_ylim()[1]
    combined = {group["label"]: group for group in [*groups, *guards]}
    order = list(combined) if order is None else order
    if len(order) != len(combined) or set(order) != set(combined):
        raise ValueError("Quality timeline must contain each confirmed point and guard once")
    labels = [combined[label]["plot_label"] for label in order]
    for guard in guards:
        index = order.index(guard["label"])
        axis.errorbar(index, guard["mean"], yerr=guard["se"], fmt="D", ms=8,
            mfc="white", mec="#bc7a20", mew=1.7, ecolor="#bc7a20", capsize=4, zorder=4)
        axis.text(index, guard["mean"]+guard["se"]+2500, f"{guard['mean']:,.0f}",
            ha="center", va="bottom", fontsize=10, fontweight="bold", color="#9c661b")
    axis.set_xticks(range(len(labels)), labels)
    axis.set_xlim(-.4, len(labels)-.6)
    upper = math.ceil(max([axis.get_ylim()[1], *[g["mean"]+g["se"]+9000 for g in guards]])/10000)*10000
    axis.set_ylim(0, upper)
    axis.set_yticks(range(0, upper+1, 40000))
    return upper


def validate_batch_aba(data):
    trial = data["batch_aba_throughput"]
    decision = json.loads(Path(trial["decision_source"]).read_bytes())
    if (decision["all_three_safety_guards_pass"] is not True
            or decision["threshold_pass"] is not True
            or decision["management_selection"] != "4096"):
        raise ValueError("No passing independently reviewed batch decision")
    legs = trial["legs"]
    if (len(decision["summary_files"]) != 3
            or [leg["batch_size"] for leg in legs] != [2048, 4096, 2048]):
        raise ValueError("Changed A-B-A batch chronology")
    for leg, pin in zip(legs, decision["summary_files"]):
        if digest(leg["source"]) != pin["sha256"]:
            raise ValueError("Changed independent batch summary")
        summary = json.loads(Path(leg["source"]).read_bytes())
        if summary["pass"] is not True or not all(v is True for v in summary["checks"].values()):
            raise ValueError("Batch safety guard failed")
        for key in ("first_utc", "last_utc", "duration_s_observerUTC", "duration_s_APIts",
                    "frame_delta", "sample_delta", "samples_per_s", "frames_per_s",
                    "samples_per_frame", "GPU_energy_J_API1Hz", "samples_per_J_API1Hz"):
            if summary[key] != leg[key]:
                raise ValueError("Batch plot statistic differs: " + key)
        if (summary["sample_delta"] != summary["last_clocks"]["optimized_samples"] - summary["first_clocks"]["optimized_samples"]
                or summary["frame_delta"] != summary["last_clocks"]["frame_count"] - summary["first_clocks"]["frame_count"]):
            raise ValueError("Batch source counter delta differs")
        for actual, expected in ((leg["samples_per_s"], leg["sample_delta"] / leg["duration_s_observerUTC"]),
                                 (leg["frames_per_s"], leg["frame_delta"] / leg["duration_s_observerUTC"]),
                                 (leg["samples_per_J_API1Hz"], leg["sample_delta"] / leg["GPU_energy_J_API1Hz"])):
            if not math.isclose(actual, expected, rel_tol=1e-12):
                raise ValueError("Batch counter/energy rate does not recompute")
    a, b, back = [leg["samples_per_s"] for leg in legs]
    if (not math.isclose(trial["threshold_samples_per_s"], 1.05 * max(a, back), rel_tol=1e-12)
            or trial["threshold_samples_per_s"] != decision["threshold_samples_per_s"]
            or not math.isclose(trial["gain_vs_stronger_A_pct"], (b / max(a, back) - 1) * 100, rel_tol=1e-12)
            or b < trial["threshold_samples_per_s"]):
        raise ValueError("Conservative batch adoption gate differs")
    return len(legs)


def batch_aba_axis(axis, trial):
    rates = [leg["samples_per_s"] for leg in trial["legs"]]
    axis.plot(range(3), rates, color="#c2bdc9", linewidth=1.7, zorder=2)
    for index, rate in enumerate(rates):
        axis.plot(index, rate, "o", color="#00866a" if index == 1 else "#2579ad",
                  markersize=9 if index == 1 else 7, zorder=4)
        axis.text(index, rate + (2000 if index == 1 else -2200), f"{rate:,.0f}",
                  ha="center", va="bottom" if index == 1 else "top",
                  fontsize=10, fontweight="bold")
    gate = trial["threshold_samples_per_s"]
    axis.axhline(gate, color="#cb8b24", linewidth=1.4, linestyle="--", zorder=1)
    axis.text(.97, .67, f"5% gate: {gate:,.0f} samples/s", transform=axis.transAxes,
              ha="right", color="#a36d18", fontsize=9,
              bbox=dict(boxstyle="round,pad=.4", fc="white", ec="none"))
    axis.set_xticks(range(3), [leg["plot_label"] for leg in trial["legs"]])
    axis.tick_params(axis="x", length=0, pad=10)
    axis.set_xlim(-.4, 2.4)
    axis.set_ylim(0, 80000)
    axis.set_yticks(range(0, 80001, 20000))
    axis.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y/1000:g}K"))
    axis.set_ylabel("Training samples/s")
    axis.grid(axis="y", color="#e9eef1", linewidth=.8)
    axis.set_axisbelow(True)
    axis.set_title("D  Settled batch-size A–B–A trial", loc="left", pad=33, fontweight="bold")
    axis.text(0, 1.045, "2026-10-16 UTC · 192 actors · exact inference graphs",
              transform=axis.transAxes, fontsize=9, color="#667786")
    axis.text(.035, .16, f"Selected 4096 · +{trial['gain_vs_stronger_A_pct']:.2f}% vs stronger A return",
              transform=axis.transAxes, color="#00755f", fontsize=10, fontweight="bold",
              bbox=dict(boxstyle="round,pad=.55", fc="#edf8f2", ec="none"))
    energy = [leg["samples_per_J_API1Hz"] for leg in trial["legs"]]
    axis.text(.035, .065, "GPU-only energy: " + " → ".join(f"{value:.2f}" for value in energy) + " samples/J",
              transform=axis.transAxes, fontsize=9, color="#647582")


def render(data, output):
    validation = validate_data(data)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
        "axes.titlesize": 13, "axes.labelsize": 11, "axes.spines.top": False,
        "axes.spines.right": False, "axes.edgecolor": "#c6cdd4",
        "xtick.color": "#536171", "ytick.color": "#536171", "text.color": "#172b3a",
        "axes.labelcolor": "#34495e"})
    fig = plt.figure(figsize=(16.8, 11.7), dpi=220, facecolor="white")
    grid = fig.add_gridspec(2, 2, left=.07, right=.93, top=.86, bottom=.21,
                           wspace=.27, hspace=.63)
    score_ax, sidecar_ax, fixed_ax, rate_ax = [fig.add_subplot(grid[i//2, i%2]) for i in range(4)]
    groups = data["learning"]
    positions = list(range(len(groups)))
    means, errors = [g["mean"] for g in groups], [g["se"] for g in groups]
    score_ax.plot(positions, means, color="#bdc9d1", linewidth=1.6, zorder=1)
    for index, (mean, error) in enumerate(zip(means, errors)):
        color = "#00866a" if index == len(groups)-1 else "#778692" if index == 0 else "#3681b3"
        score_ax.errorbar(index, mean, yerr=error, fmt="o", markersize=7, capsize=4,
                          color=color, elinewidth=1.6, zorder=3)
        score_ax.text(index, mean+error+2000, f"{mean:,.0f}", ha="center", va="bottom",
                      fontsize=10, fontweight="bold")
    score_ax.set_xticks(positions, [g["plot_label"] for g in groups])
    score_ax.tick_params(axis="x", length=0, pad=10)
    score_ax.set_xlim(-.4, len(groups)-.6)
    upper = math.ceil(max(m+e+6000 for m, e in zip(means, errors))/10000)*10000
    score_ax.set_ylim(0, upper)
    score_ax.set_yticks(range(0, upper+1, 10000))
    score_ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y/1000:g}K"))
    score_ax.set_ylabel("Mean game score")
    score_ax.grid(axis="y", color="#e9eef1", linewidth=.8)
    score_ax.set_axisbelow(True)
    score_ax.set_title("A  Historical GB300 quality", loc="left", pad=33, fontweight="bold")
    score_ax.text(0, 1.045, "Greedy wave-1 games · difficulty 5 · ±1 SE",
                  transform=score_ax.transAxes, fontsize=9, color="#667786")
    gain = (means[-1]/means[0]-1)*100
    score_ax.text(.035, .065, f"Historical gain vs original: +{gain:.1f}%",
        transform=score_ax.transAxes, color="#00755f", fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=.6", fc="#edf8f2", ec="none"))

    sidecar_upper, sidecar_gain = quality_series_axis(sidecar_ax, data["sidecar_learning"],
        "B  GPU0 compiled · earlier transport", "Own 8M reference → 16M · ±1 SE",
        "own 8M baseline", "#8064a2")
    fixed_groups = data["fixed_transport_learning"]
    timeline = data.get("fixed_transport_plot_order")
    positions = None if timeline is None else [timeline.index(group["label"]) for group in fixed_groups]
    fixed_upper, fixed_gain = quality_series_axis(fixed_ax, fixed_groups,
        "C  GPU0 compiled · fixed transport, 3s", "Historical600s cohorts through192M · hollow: unpromoted96M guard",
        "128M", "#b87536", positions=positions, gain_reference_index=[g["label"] for g in fixed_groups].index("GPU0 fixed-transport 128M confirmed"))

    fixed_upper = observational_guard_overlay(fixed_ax, fixed_groups,
        data.get("observational_guards", []), order=timeline)

    batch_aba_axis(rate_ax, data["batch_aba_throughput"])
    stage = data["plotting"]["confirmed_stage"]
    protection = data["protected_incumbent_annotation"]
    pool = protection["descriptive_candidate_pool"]
    fig.text(.07, .965, "Robotron · learning progress and training throughput", fontsize=20, fontweight="bold")
    fig.text(.07, .925, f"Protected {protection['stage']} · 1200s / diagnostics ON · n={pool['count']} / mean {pool['mean']:,.0f} · cohorts +9.81% / +9.06% vs fresh256M", fontsize=11, color="#536171")
    for y, line in zip([.115, .085, .055, .025], data["caption"].splitlines()):
        fig.text(.07, y, line, fontsize=8.2, color="#647582", va="top")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.canvas.get_width_height()
    for item in fig.findobj(match=lambda item: isinstance(item, Text)):
        if item.get_visible() and item.get_text():
            box = item.get_window_extent(renderer)
            if not (box.x0 >= -1 and box.y0 >= -1 and box.x1 <= width+1 and box.y1 <= height+1):
                raise ValueError(f"Text extends beyond the figure: {item.get_text()}")
    fig.savefig(output, dpi=220, facecolor="white", metadata={"Title": f"Robotron progress through confirmed {stage}",
                                                           "Description": data["caption"]})
    plt.close(fig)
    with Image.open(output) as png:
        dimensions = png.size
        png.verify()
    check_sources(data)
    return dict(validation, png=str(output), pixel_dimensions=list(dimensions),
                score_axis_maximum=upper, historical_GB300_gain_8M_vs_original_pct=gain,
                sidecar_score_axis_maximum=sidecar_upper,
                sidecar_gain_vs_same_backend_8M_pct=sidecar_gain,
                fixed_transport_score_axis_maximum=fixed_upper,
                fixed_transport_gain_32M_vs_16M_pct=(data["fixed_transport_learning"][1]["mean"] /
                    data["fixed_transport_learning"][0]["mean"] - 1) * 100,
                fixed_transport_gain_latest_vs_16M_pct=(fixed_groups[-1]["mean"] / fixed_groups[0]["mean"] - 1) * 100,
                fixed_transport_gain_128M_vs_64M_pct=(fixed_groups[3]["mean"] / fixed_groups[2]["mean"] - 1) * 100,
                fixed_transport_gain_192M_vs_128M_pct=fixed_gain,
                fixed_transport_gain_64M_vs_32M_pct=(data["fixed_transport_learning"][2]["mean"] /
                    data["fixed_transport_learning"][1]["mean"] - 1) * 100,
                matplotlib=matplotlib.__version__, sources_unchanged=True,
                canvas_text_bounds_checked=True, png_integrity_verified=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.data.with_suffix(".png")
    if output.resolve() == args.data.resolve():
        parser.error("PNG output must differ from the input JSON")
    print(json.dumps(render(json.loads(args.data.read_text()), output), indent=2))


if __name__ == "__main__":
    main()
