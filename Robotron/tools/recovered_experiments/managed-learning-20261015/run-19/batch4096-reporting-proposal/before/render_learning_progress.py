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


def validate_data(data):
    check_sources(data)
    seen, protocols, cohorts = set(), {}, 0
    backend_references = {}
    for group in [*data["learning"], *data.get("sidecar_learning", []),
                  *data.get("fixed_transport_learning", [])]:
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
    return dict(validated_cohorts=cohorts, disjoint_games=len(seen),
                separate_backend_series=sorted(protocols))


def quality_series_axis(axis, groups, title, subtitle, baseline_label, baseline_color):
    means, errors = [g["mean"] for g in groups], [g["se"] for g in groups]
    axis.plot(range(len(groups)), means, color="#c2bdc9", lw=1.6)
    for index, (mean, error) in enumerate(zip(means, errors)):
        axis.errorbar(index, mean, yerr=error, fmt="o", ms=8, capsize=4,
                      color="#00866a" if index == len(groups)-1 else baseline_color, elinewidth=1.6)
        axis.text(index, mean+error+2500, f"{mean:,.0f}", ha="center", va="bottom",
                  fontsize=10, fontweight="bold")
    axis.set_xticks(range(len(groups)), [g["plot_label"] for g in groups])
    axis.tick_params(axis="x", length=0, pad=10)
    axis.set_xlim(-.4, len(groups)-.6)
    upper = math.ceil(max(m+e+7500 for m, e in zip(means, errors))/10000)*10000
    axis.set_ylim(0, upper)
    axis.set_yticks(range(0, upper+1, 20000))
    axis.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y/1000:g}K"))
    axis.set_ylabel("Mean game score")
    axis.grid(axis="y", color="#e9eef1", lw=.8)
    axis.set_axisbelow(True)
    axis.set_title(title, loc="left", pad=33, fontweight="bold")
    axis.text(0, 1.045, subtitle, transform=axis.transAxes, fontsize=9, color="#667786")
    gain = (means[-1]/means[0]-1)*100
    axis.text(.04, .065, f"+{gain:.1f}% vs {baseline_label}", transform=axis.transAxes,
        color="#00755f", fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=.6", fc="#edf8f2", ec="none"))
    return upper, gain


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
    gpu_ax = rate_ax.twinx()
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
    fixed_upper, fixed_gain = quality_series_axis(fixed_ax, data["fixed_transport_learning"],
        "C  GPU0 compiled · fixed transport, 3s", "16M reference → 32M → 64M · latest +25.5% vs 32M",
        "own fixed-transport 16M baseline", "#b87536")

    trials = data["throughput"]["select_v1"]
    actors = [t["actors"] for t in trials]
    rates = [t["means"]["samples_per_s"] for t in trials]
    gpu_util = [t["means"]["gpu_util_pct"] for t in trials]
    selected = data["throughput"]["selected"]
    chosen = next(t for t in trials if t["actors"] == selected["actors"] and t["wait_us"] == selected["wait_us"])
    chosen_rate, chosen_gpu = chosen["means"]["samples_per_s"], chosen["means"]["gpu_util_pct"]
    rate_ax.axvspan(selected["actors"]-9, selected["actors"]+9, color="#e7f6ee", zorder=0)
    rate_ax.plot(actors, rates, "o-", color="#2579ad", linewidth=2, markersize=6, zorder=3)
    gpu_ax.plot(actors, gpu_util, "s--", color="#cb8b24", linewidth=1.7, markersize=5, zorder=2)
    rate_ax.plot(selected["actors"], chosen_rate, "o", color="#00866a", markersize=10, zorder=4)
    reference = data["throughput"]["busy_32_reference"]["means"]
    for axis, value in ((rate_ax, reference["samples_per_s"]), (gpu_ax, reference["gpu_util_pct"])):
        axis.plot(32, value, marker="D", ms=8, mfc="white", mec="#7c8790", ls="none", zorder=5)
    rate_ax.set_xlim(21, 201)
    rate_ax.set_ylim(0, 80000)
    rate_ax.set_xticks(actors)
    rate_ax.set_yticks(range(0, 80001, 20000))
    rate_ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y/1000:g}K"))
    gpu_ax.set_ylim(0, 100)
    gpu_ax.set_yticks(range(0, 101, 20))
    rate_ax.set_xlabel("MAME actors", labelpad=8)
    rate_ax.set_ylabel("Training samples/s", color="#2579ad")
    gpu_ax.set_ylabel("GPU utilization (%)", color="#cb8b24")
    gpu_ax.tick_params(axis="y", colors="#cb8b24")
    gpu_ax.spines["right"].set_visible(True)
    gpu_ax.spines["right"].set_color("#c6cdd4")
    rate_ax.grid(axis="y", color="#e9eef1", linewidth=.8)
    rate_ax.set_axisbelow(True)
    rate_ax.set_title("D  Historical sequential throughput", loc="left", pad=33, fontweight="bold")
    rate_ax.text(0, 1.045, "GB300 · batch 2048 · replay cap: 8 samples/frame",
                 transform=rate_ax.transAxes, fontsize=9, color="#667786")
    rate_ax.annotate(f"Selected {selected['actors']} / {selected['wait_us']} µs\n"
                    f"{chosen_rate/1000:.1f}K samples/s · {chosen_gpu:.1f}% GPU",
        xy=(selected["actors"], chosen_rate), xytext=(91, 75500), fontsize=9,
        color="#00755f", ha="center", va="top",
        arrowprops=dict(arrowstyle="-", color="#00866a", lw=.8),
        bbox=dict(boxstyle="round,pad=.4", fc="white", ec="none", alpha=.9))
    marginal = (rates[-1]/chosen_rate-1)*100
    rate_ax.annotate(f"192: +{marginal:.1f}% throughput\n"
                    f"{trials[-1]['means']['samples_per_frame']:.2f} samples/frame",
        xy=(192, rates[-1]), xytext=(148, 39000), fontsize=9, ha="left", color="#536171",
        arrowprops=dict(arrowstyle="-", color="#9aabb6", lw=.8))
    rate_ax.text(.025, .075, "32 busy reference\n"
                 f"{reference['samples_per_s']/1000:.1f}K samples/s · {reference['gpu_util_pct']:.1f}% GPU",
                 transform=rate_ax.transAxes, fontsize=9, color="#687681")
    rate_ax.legend(handles=[Line2D([], [], color="#2579ad", marker="o", label="Samples/s"),
        Line2D([], [], color="#cb8b24", marker="s", ls="--", label="GPU %"),
        Line2D([], [], color="#7c8790", marker="D", mfc="white", ls="none", label="32 busy ref")],
        loc="upper left", bbox_to_anchor=(0, -.25), ncol=3, frameon=False, fontsize=9, columnspacing=1.5)
    stage = data["plotting"]["confirmed_stage"]
    fig.text(.07, .965, "Robotron · confirmed learning progress and training throughput", fontsize=20, fontweight="bold")
    fig.text(.07, .925, f"Confirmed quality through {stage}; three separate quality series · throughput panel shows historical trials", fontsize=11, color="#536171")
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
                fixed_transport_gain_latest_vs_16M_pct=fixed_gain,
                fixed_transport_gain_64M_vs_32M_pct=(data["fixed_transport_learning"][-1]["mean"] /
                    data["fixed_transport_learning"][-2]["mean"] - 1) * 100,
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
