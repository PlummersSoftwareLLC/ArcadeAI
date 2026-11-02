#!/usr/bin/env python3
"""Prepare reporting proposals only; run outside root's quiet timing windows."""
from datetime import datetime, timezone
import copy
import difflib
import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
CAMPAIGN, GAME = RUN.parent, RUN.parents[2]
PROPOSAL = RUN / "batch4096-reporting-proposal"


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Changed source anchor: " + old[:70])
    return text.replace(old, new)


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


ADDED_VALIDATOR = '''def validate_batch_aba(data):
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


'''


def main():
    if PROPOSAL.exists():
        raise ValueError("Preserve the existing proposal instead of overwriting it")
    decision_path = CAMPAIGN / "run-18/batch2048-4096-ABA-independent-decision.json"
    decision = json.loads(decision_path.read_bytes())
    if not (decision["threshold_pass"] and decision["all_three_safety_guards_pass"]):
        raise ValueError("Require the final passing independently reviewed A-B-A decision")
    PROPOSAL.mkdir()
    before, proposed = PROPOSAL / "before", PROPOSAL / "proposed"
    before.mkdir(); proposed.mkdir()
    renderer, docs = GAME / "tools/render_learning_progress.py", GAME / "DELL_SETUP.md"
    data_path = CAMPAIGN / "learning-and-throughput-progress.json"
    for path in (renderer, docs, data_path, data_path.with_suffix(".png")):
        (before / path.name).write_bytes(path.read_bytes())
    data = json.loads(data_path.read_bytes())
    for source in data["sources"]:
        if sha(source["path"]) != source["sha256"]:
            raise ValueError("Historical source bytes changed")
    text = renderer.read_text()
    text = replace_once(text, "def render(data, output):", ADDED_VALIDATOR + "def render(data, output):")
    text = replace_once(text, "    return dict(validated_cohorts=cohorts, disjoint_games=len(seen),",
        "    batch_trials = validate_batch_aba(data)\n    return dict(validated_cohorts=cohorts, disjoint_games=len(seen),\n                validated_batch_trials=batch_trials,")
    text = replace_once(text, "    gpu_ax = rate_ax.twinx()\n", "")
    first = text.index('    trials = data["throughput"]["select_v1"]\n')
    last = text.index('    stage = data["plotting"]["confirmed_stage"]\n', first)
    text = text[:first] + '    batch_aba_axis(rate_ax, data["batch_aba_throughput"])\n' + text[last:]
    text = replace_once(text, 'three separate quality series · throughput panel shows historical trials',
        'three separate quality series · selected training: batch 4096 / 192 actors')
    (proposed / renderer.name).write_text(text)

    new_note = '''\nThe selected learner batch is now 4096 after a completed sequential A–B–A trial
on 2026-10-16 UTC. All legs retained 192 actors, exact inference graphs, direct
pinned replay fill, native priority updates, 1ms collector wait, 1000µs socket
readiness and replay cap 8. Each primary window followed 90 seconds of settling:

| Chronological leg | UTC window | Batch | Samples/s | Counter FPS | GPU-only samples/J |
| --- | --- | ---: | ---: | ---: | ---: |
| A, run16 | 08:24:31.463–08:27:31.477 | 2048 | 66,463.74 | 8,314.19 | 160.85 |
| B, run17 | 08:34:44.489–08:37:44.504 | 4096 | 71,332.63 | 8,913.69 | 166.70 |
| A return, run18 | 08:43:02.112–08:46:02.127 | 2048 | 67,521.54 | 8,431.75 | 161.90 |

B exceeded the stronger A return by 5.644%, clearing the prespecified
`1.05 * max(A, Areturn)` gate of 70,897.615 samples/s. All three recorded runtime,
actor, graph/native and replay-pressure guards passed; the windows had no new
deadline errors, native/graph fallback, nonfinite/training errors or replay
drops. This statement applies to these three fixed windows, not the entire
training campaign. The independent decision and full summaries are linked by
`logs/managed-learning-20261015/run-18/batch2048-4096-ABA-independent-decision.json`.
Rates use raw sample/frame counter deltas over the recorded observer-UTC
intervals, rather than console-smoothed FPS. Energy integrates sampled GPU
power only and excludes CPU/system power.

This selects throughput, not improved learning quality. Adam advances once per
batch, so 4096 halves optimizer updates per processed sample; diagnostic cadence
20 also halves diagnostics per sample. LR and imitation schedules retain their
sample clock (`optimized_samples / 512`) with no LR scaling. The hard target
period stays 512,000 samples, while actor refresh quantizes from 26,624 to
28,672 samples. The sequential runs evolve policy/replay/RNG trajectories and
do not establish learning equivalence or formal statistical confidence. The
protected 64M policy and all fixed-backend quality gates remain separate.
The progress figure retains the three quality segments unchanged and now shows
this batch chronology in panel D; historical actor-scaling trial data remain in
its JSON and archived earlier figure. No new run19 performance result is claimed.
'''
    doc_text = replace_once(docs.read_text(),
        "**Fleet size: 16 headless clients**, with batch 2048. This was selected for\n"
        "the best measured balance of training throughput and experience collection. Stop the fleet\n",
        "**Managed selection (2026-10-16): 192 headless clients, learner batch 4096**,\n"
        "after the completed A–B–A throughput comparison documented below. Generic\n"
        "launcher/service defaults are separate; selected runs set `DQN_BATCH_SIZE=4096`\n"
        "and retain the measured exact-inference-graph profile. Stop the fleet\n")
    doc_text = replace_once(doc_text,
        "updates. Compilation is warmed on one thread; CUDA graph capture is disabled\n"
        "for this concurrent training/inference configuration.",
        "updates. Compilation is warmed on one thread; automatic Inductor graph\n"
        "capture stays disabled. The managed selection uses separately validated\n"
        "exact-size actor CUDA graphs; training graphs remain uncaptured.")
    (proposed / docs.name).write_text(doc_text + new_note)
    legs = []
    for phase, batch, number, pin, clock_label in zip(("A", "B", "A return"), (2048,4096,2048), (16,17,18),
            decision["summary_files"], ("08:24–08:27", "08:34–08:37", "08:43–08:46")):
        path = GAME.parent / pin["path"]
        if sha(path) != pin["sha256"]:
            raise ValueError("Independent summary changed")
        summary = json.loads(path.read_bytes())
        leg = {key:summary[key] for key in ("first_utc", "last_utc", "duration_s_observerUTC", "duration_s_APIts",
            "frame_delta", "sample_delta", "samples_per_s", "frames_per_s", "samples_per_frame",
            "GPU_energy_J_API1Hz", "samples_per_J_API1Hz")}
        leg.update(phase=phase, batch_size=batch, run=number, source=str(path),
            plot_label=f"{phase} · {batch}\nrun{number}\n{clock_label}")
        legs.append(leg)
    data["batch_aba_throughput"] = dict(decision_source=str(decision_path), legs=legs,
        threshold_samples_per_s=decision["threshold_samples_per_s"],
        gain_vs_stronger_A_pct=(decision["B_to_max_A_ratio"]-1)*100,
        selected_batch=4096, actors=192, fixed_controls="exactgraphs/directfill/nativepriority/collector1ms/socket1000us/cap8",
        scope="Sequential operational selection; not learning equivalence, formal confidence or a run19 result",
        rate_elapsed_clock="observer UTC; both observer and API timestamp durations retained",
        energy_scope="GPU-only power samples; excludes CPU/system power")
    data["schema"] = "robotron-learning-throughput-figure-v5"
    data["created_utc"] = datetime.now(timezone.utc).isoformat()
    data["scope"] = ("Confirmed64M quality in three separate backend series; panelD completed run16–18 "
        "sequential batch-size A-B-A selects4096 for throughput only. Historical actor trials and "
        "dated run13/14 efficiency evidence remain in data; no cross-backend ratio or run19 claim.")
    data["plotting"].update(renderer_sha256=sha(proposed/renderer.name),
        proposal_renderer_path=str(proposed/renderer.name))
    data["caption"] = "\n".join([
        "Quality: complete greedy wave-1 games at difficulty 5; mean ±1 SE (not formal confidence intervals). Pools use separate valid cohorts; recovery changes are not a causal ablation.",
        "A: historical GB300 (*4M/8M select-v1/1000 µs; earlier busy). B: earlier GPU0 transport. C: fixed-transport/3s GPU0. Own references; no cross-segment ratios. All started games and late tails retained.",
        "D: 2026-10-16 UTC A–B–A fixed first-180s trials after 90s settling. Counter samples/s; energy is GPU-only. Sequential policy/replay/RNG drift remains; not a formal confidence statement.",
        "Batch 4096 changes optimizer/diagnostic cadence and actor-refresh quantization. Throughput selection does not establish better learning quality. No run19 result is included."])
    data["progress"]["selected_training_batch"] = 4096
    data["progress"]["selected_training_actors"] = 192
    data["validation"].update(canvas_visually_reviewed=False, standalone_canvas_text_bounds_checked=False,
        png_integrity_verified=False, all_sources_unchanged_after_render=False)
    for source in data["sources"]:
        if Path(source["path"]) == renderer:
            source["path"] = str(before / renderer.name)
    for path in [proposed/renderer.name, decision_path, *[Path(leg["source"]) for leg in legs]]:
        data["sources"].append(dict(path=str(path), sha256=sha(path)))
    write_json(proposed / data_path.name, data)
    diff = []
    for path in (renderer, docs):
        diff.extend(difflib.unified_diff((before/path.name).read_text().splitlines(True),
            (proposed/path.name).read_text().splitlines(True),
            fromfile="a/"+str(path.relative_to(GAME.parent)), tofile="b/"+str(path.relative_to(GAME.parent))))
    (PROPOSAL/"batch4096-reporting.patch").write_text("".join(diff))
    write_json(PROPOSAL/"prepared.json", dict(schema="robotron-batch4096-reporting-proposal-v1",
        utc=datetime.now(timezone.utc).isoformat(), proposal_only=True,
        before={path.name:dict(path=str(path),sha256=sha(path)) for path in (renderer,docs,data_path,data_path.with_suffix(".png"))},
        proposed={path.name:dict(path=str(path),sha256=sha(path)) for path in proposed.iterdir()},
        patch_sha256=sha(PROPOSAL/"batch4096-reporting.patch"), production_sources_changed=False,
        apply_note="After root approval, canonicalize the new renderer source record and remove proposal_renderer_path; render and verify all sources again."))
    print(json.dumps(dict(proposal=str(PROPOSAL),patch_sha256=sha(PROPOSAL/"batch4096-reporting.patch"))))


if __name__ == "__main__":
    main()
