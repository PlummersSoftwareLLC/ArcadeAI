#!/usr/bin/env python3
"""Create reviewable reporting proposals only; no live source or output changes."""
from datetime import datetime, timezone
import copy
import difflib
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

RUN = Path(__file__).resolve().parent
GAME = RUN.parents[2]
CAMPAIGN = RUN.parent
PROPOSAL = RUN / "progress64M-proposal"
sys.path.insert(0, str(GAME / "tools"))
from compare_frozen_measurements import validate_receipt
from compare_sidecar_measurements import validate_backend

CAMPAIGN_SHA = "70192829dead424877aae215a3c5f60ba2610f12ec9e13d12f1b467ed17914ea"
CHECKPOINT_SHA = "fe88785bf9475c50a7a3df6cd04ab52caf46b706a7f6e22c36b99c21bcc93244"


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(part)
    return value.hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def replace_once(text, before, after):
    require(text.count(before) == 1, "Expected exactly one source anchor: " + before[:70])
    return text.replace(before, after)


def write_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    require(not PROPOSAL.exists(), "Proposal directory already exists; preserve prior artifacts")
    renderer, docs = GAME / "tools/render_learning_progress.py", GAME / "DELL_SETUP.md"
    data_path = CAMPAIGN / "learning-and-throughput-progress.json"
    old_data = json.loads(data_path.read_bytes())
    for source in old_data["sources"]:
        require(sha(source["path"]) == source["sha256"], "Historical figure source changed")
    campaign_path = CAMPAIGN / "sidecar-fresh3-64M-confirmed-campaign.json"
    require(sha(campaign_path) == CAMPAIGN_SHA, "Confirmed campaign changed")
    campaign = json.loads(campaign_path.read_bytes())
    require(campaign["stage"] == "confirmed" and campaign["gain_gate"]["confirmation_gate_passed"] is True,
            "Require published confirmed campaign")
    protected = campaign["policy_identity"]["protected_copy"]
    require(sha(protected["path"]) == protected["sha256"] == CHECKPOINT_SHA
        and sha(protected["metadata_path"]) == protected["metadata_sha256"], "Protected policy identity changed")
    PROPOSAL.mkdir()
    before, proposed = PROPOSAL / "before", PROPOSAL / "proposed"
    before.mkdir(); proposed.mkdir()
    for path in (renderer, docs, data_path):
        (before / path.name).write_bytes(path.read_bytes())

    text = renderer.read_text()
    text = replace_once(text, '"Fresh 16M reference → 32M · ±1 SE",',
        '"16M reference → 32M → 64M · latest +25.5% vs 32M",')
    text = replace_once(text,
        'f"Confirmed quality through {stage}; three separate quality series · selected training layout: "\n'
        '             f"{selected[\'actors\']} actors / select-v1 / {selected[\'wait_us\']} µs",',
        'f"Confirmed quality through {stage}; three separate quality series · throughput panel shows historical trials",')
    text = replace_once(text, 'fixed_transport_gain_32M_vs_16M_pct=fixed_gain,',
        'fixed_transport_gain_32M_vs_16M_pct=(data["fixed_transport_learning"][1]["mean"] /\n'
        '                    data["fixed_transport_learning"][0]["mean"] - 1) * 100,\n'
        '                fixed_transport_gain_latest_vs_16M_pct=fixed_gain,\n'
        '                fixed_transport_gain_64M_vs_32M_pct=(data["fixed_transport_learning"][-1]["mean"] /\n'
        '                    data["fixed_transport_learning"][-2]["mean"] - 1) * 100,')
    (proposed / renderer.name).write_text(text)

    text = docs.read_text()
    text = replace_once(text, "explicit interval of 100–1000 microseconds", "explicit interval of 100–10000 microseconds")
    text = replace_once(text, "The current selected training layout is 128 actors at 1000 microseconds. Initial",
        "The initial 2026-10-15 trials selected 128 actors at 1000 microseconds. Initial")
    text = replace_once(text, "controlled timing benchmark; retain the lower-cost 128 layout pending a longer\nconfirmation.",
        "controlled timing benchmark. Later 2026-10-16 trials below use a different main\ninference implementation and select 192 actors.")
    text = replace_once(text, "The progress figure shows this fixed-transport 16M-to-32M series separately from",
        "The progress figure shows this fixed-transport 16M-to-32M-to-64M series separately from")
    text = replace_once(text,
        "Host inference/refresh telemetry is documented in `tools/PIPELINE_REPORTING.md`.\n"
        "Its CPU tests validate reporting and operation order; they do not establish live\n"
        "overhead or a throughput improvement in the newly starting run09.\n",
        "The saved 64M policy passed another two independent full-tail GPU0 compiled\n"
        "cohorts on the same fixed-transport/3s protocol: 110 and 107 complete games,\n"
        "with means 144,405 and 160,058. Each leg independently exceeded the pooled\n"
        "32M mean by at least 5% and its median of 124,125. The descriptive 217-game\n"
        "pool has mean 152,123, median 146,575 and SE 3,283: +25.47% versus the two\n"
        "separately valid 32M cohorts pooled above. All started games, including late\n"
        "tails, completed; all 16 private slots were represented. Game and paired-slot\n"
        "bootstrap ratio sensitivities were [1.184, 1.330] and [1.207, 1.306]. These\n"
        "retain the same sequential-selection and host-pacing caveats, not formal\n"
        "confirmatory confidence. The policy is protected at\n"
        "`models_dqn/managed-incumbents/fresh3-64M-confirmed.pt`, SHA256\n"
        "`fe88785bf9475c50a7a3df6cd04ab52caf46b706a7f6e22c36b99c21bcc93244`;\n"
        "`logs/managed-learning-20261015/sidecar-fresh3-64M-confirmed-campaign.json`\n"
        "records both real receipts, saved policy clocks and unchanged private backend.\n\n"
        "Later efficiency evidence is dated 2026-10-16 UTC and uses fixed first-180s\n"
        "counter windows after settling. The 192-actor run13 reference at\n"
        "07:15:49.799–07:18:49.971 measured 64,825 samples/s. Run14 with native priority\n"
        "updates at 07:27:46.891–07:30:46.907 measured 66,918 samples/s: +3.23% against\n"
        "that recent reference (+1.31% against the older 66,052 reference), below both\n"
        "5% gain gates. Native execution counters confirmed successes with no fallback\n"
        "or native error in these windows. The 256-actor trial at\n"
        "07:34:05.934–07:37:06.048 fell to 60,537 samples/s (−9.54% versus native192)\n"
        "while samples/frame remained about 8; it was rejected and 192 restored. The\n"
        "main layout at this dated observation uses exact-size CUDA graphs, a 1ms\n"
        "collector wait and 1000µs native socket readiness. These sequential operational\n"
        "trials are not randomized same-policy tests or proof that every rate change\n"
        "was caused by the tested implementation. Evidence is in\n"
        "`logs/managed-learning-20261015/run-14/nativebatch-fleet-pilot-campaign.json`.\n\n"
        "The performance windows above had no main inference-deadline errors. Later,\n"
        "six main-only deadline errors clustered at 07:55:40.206 UTC, with affected\n"
        "connections closing and reconnecting; the entire live run is therefore not\n"
        "error-free. They were outside those performance windows and neither private\n"
        "64M quality cohort had a runtime timeout. Main graph/native fatal and fallback\n"
        "counters remained zero in the recorded observation. The nearby archive/save\n"
        "activity is correlation, not an established cause. See\n"
        "`run-14/sidecar-64M-confirm01-main-deadline-observation.json` under the campaign\n"
        "directory. Host inference/refresh telemetry is documented in\n"
        "`tools/PIPELINE_REPORTING.md`; its timers are host elapsed time, not GPU kernel\n"
        "time, and its CPU tests do not establish controlled live instrumentation overhead.\n")
    (proposed / docs.name).write_text(text)

    data = copy.deepcopy(old_data)
    data.update(schema="robotron-learning-throughput-figure-v4", created_utc=datetime.now(timezone.utc).isoformat(),
        scope="Confirmed historical GB300 through8M, earlier-transport GPU0 compiled through16M, separate fixed-transport3s GPU0 compiled16M-to32M-to64M; no cross-series gain. Historical throughput panel and separately dated run13/14 efficiency evidence.")
    rows, counts = [], []
    for source in campaign["sources"]:
        require(sha(source["path"]) == source["sha256"], "64M source receipt changed")
        receipt = json.loads(Path(source["path"]).read_bytes())
        leg = validate_backend(receipt, verify_checkpoint=True)
        counts.append(len(leg["rows"])); rows.extend(leg["rows"])
    scores = [row["score"] for row in rows]
    pool = campaign["descriptive_pools"]["confirmed64M"]
    require(len(rows) == pool["count"] == 217 and counts == [110,107], "Wrong constituent game denominators")
    for key, value in dict(mean=statistics.mean(scores), median=statistics.median(scores),
                           se=statistics.stdev(scores)/math.sqrt(len(scores))).items():
        require(math.isclose(pool[key], value, rel_tol=1e-12), "Campaign pooled statistic differs")
    data["fixed_transport_learning"].append(dict(label="GPU0 fixed-transport 64M confirmed",
        backend_series="gpu0-compiled-fixed-transport-3s", count=pool["count"], mean=pool["mean"],
        median=pool["median"], se=pool["se"], constituent_labels=[s["label"] for s in campaign["sources"]],
        constituent_counts=counts, actor_slots=list(range(4096,4112)), source_receipts=[s["path"] for s in campaign["sources"]],
        checkpoint_sha256=CHECKPOINT_SHA, unit="Descriptive pool of separately validated same-policy cohorts; not a merged receipt",
        plot_label="64M\nconfirmed\nn=217"))
    data["fixed_transport_provenance"]["latest_campaign_report"] = str(campaign_path)
    data["fixed_transport_provenance"]["64M_policy_saved_clocks"] = campaign["policy_identity"]["saved_policy_clocks"]
    data["progress"].update(latest_confirmed_stage="64M",
        GPU0_fixed_transport_gain_64M_vs_32M_pct=(pool["mean"]/data["fixed_transport_learning"][-2]["mean"]-1)*100,
        run09_live_instrumentation_overhead="Not isolated by sequential live trials; CPU operation-order tests do not establish causal overhead.")
    data["plotting"].update(confirmed_stage="64M (fixed-transport GPU0)", renderer=str(renderer),
        renderer_sha256=sha(proposed / renderer.name), fixed_transport_score_axis_maximum=170000,
        proposal_renderer_path=str(proposed / renderer.name))
    data["caption"] = "\n".join([
        "Quality: complete greedy wave-1 games at difficulty 5; mean ±1 SE (not formal confidence intervals). Pools use separate valid cohorts; recovery changes are not a causal ablation.",
        "A: historical GB300 (*4M/8M select-v1/1000 µs; earlier busy polling). B: earlier GPU0 transport. C: fixed-transport/3s GPU0 series. Each uses its own reference; no cross-segment ratios.",
        "D: historical sequential throughput trials. Later 2026-10-16 UTC pilots: native192 +3.23% (below 5% gate); 256 −9.54%, rejected. Sequential evidence, not controlled same-policy tests.",
        "Every quality leg retains all started games and late tails. Host pacing/RNG/batching/repeated looks remain sensitivities. Six later main deadline errors do not belong to private quality cohorts."])
    data["validation"].update(constituent_game_count=2156, constituent_cohort_count=19,
        all19_receipts_revalidated=True, all2156_game_ids_disjoint=True,
        pooled_64M_matches_independent_campaign=True, source_and_protected_64M_checkpoint_hash_match=True,
        current_five_full_private_backends_match=True, old_quality_group_data_unchanged=True,
        canvas_visually_reviewed=False, standalone_canvas_text_bounds_checked=False,
        png_integrity_verified=False, all_sources_unchanged_after_render=False)
    data["efficiency_update"] = dict(observation_date_utc="2026-10-16", source=str(RUN / "nativebatch-fleet-pilot-campaign.json"),
        primary_metric="optimized-sample counter delta / exact settled interval; not console FPS",
        native192_sequential_gain_pct=3.22830713980247, required_gain_pct=5, gain_gate_passed=False,
        actor256_change_pct=-9.53592001643491, actor256_rejected=True, restored_actor_count=192,
        collector_wait_ms=1, socket_readiness_wait_us=1000, exact_graphs=True,
        main_deadline_errors=dict(count=6, utc_cluster="2026-10-16T07:55:40.2057–07:55:40.2070Z",
            outside_primary_performance_windows=True, private64M_runtime_timeouts=0,
            source=str(RUN / "sidecar-64M-confirm01-main-deadline-observation.json")),
        caveats=["Sequential trials are not randomized same-policy comparisons.",
            "Primary 180-second windows are prespecified; full tails are corroboration only.",
            "The six later main errors prohibit claiming the whole live run is error-free.",
            "Save proximity is correlation, not a demonstrated cause."])
    native = json.loads((RUN / "nativebatch-fixed180-result.json").read_bytes())
    fleet256 = json.loads((RUN / "actor256-nativebatch-fixed180-result.json").read_bytes())
    windows = {}
    for label, phase in (("reference192_without_native", native["recent_run13_baseline"]),
                         ("native192", native["phase"]), ("native256", fleet256["phase"])):
        require(math.isclose(phase["samples_per_s"], phase["sample_delta"]/phase["duration_s"], rel_tol=1e-12),
                "Performance counter rate differs from saved interval")
        windows[label] = {key:phase[key] for key in ("utc_start", "utc_end", "duration_s", "clients",
            "frame_delta", "sample_delta", "frames_per_s", "samples_per_s", "samples_per_frame")}
    require(all(value is True for value in native["guards"].values())
        and all(value is True for value in fleet256["guards"].values()), "Primary performance guard failed")
    require(math.isclose(native["vs_recent_samples_ratio"], windows["native192"]["samples_per_s"] /
            windows["reference192_without_native"]["samples_per_s"], rel_tol=1e-12)
        and math.isclose(fleet256["vs_recent_samples_ratio"], windows["native256"]["samples_per_s"] /
            windows["native192"]["samples_per_s"], rel_tol=1e-12), "Sequential throughput ratio differs")
    data["efficiency_update"]["primary_windows"] = windows
    data["efficiency_update"]["native_success_counts"] = dict(native192=native["phase"]["native_batch_update"]["delta"],
        native256=fleet256["phase"]["native_batch_update"]["delta"],
        interpretation="Includes priority boosts as well as optimizer updates; not one success per learner step")
    # Retain the old renderer bytes/hash as a before artifact. The new source is
    # the proposal until root explicitly authorizes canonical application.
    for source in data["sources"]:
        if Path(source["path"]) == renderer:
            source["path"] = str(before / renderer.name)
    paths = [proposed / renderer.name, campaign_path, Path(campaign["comparison_report"]["path"]),
        Path(protected["path"]), Path(protected["metadata_path"]),
        *[Path(s["path"]) for s in campaign["sources"]], RUN / "nativebatch-fleet-pilot-campaign.json",
        RUN / "nativebatch-fixed180-result.json", RUN / "actor256-nativebatch-fixed180-result.json",
        RUN / "sidecar-64M-confirm01-main-deadline-observation.json"]
    for path in paths:
        data["sources"].append(dict(path=str(path), sha256=sha(path)))
    write_json(proposed / data_path.name, data)
    changes = []
    for path in (renderer, docs):
        changes.extend(difflib.unified_diff((before / path.name).read_text().splitlines(True),
            (proposed / path.name).read_text().splitlines(True),
            fromfile="a/" + str(path.relative_to(GAME.parent)), tofile="b/" + str(path.relative_to(GAME.parent))))
    (PROPOSAL / "progress64M-reporting.patch").write_text("".join(changes))
    record = dict(schema="robotron-progress64M-reporting-proposal-v1", utc=datetime.now(timezone.utc).isoformat(),
        proposal_only=True, canonical_sources_and_outputs_unchanged=True,
        before={path.name:dict(path=str(path), sha256=sha(path)) for path in (renderer,docs,data_path)},
        proposed={p.name:dict(path=str(p), sha256=sha(p)) for p in proposed.iterdir()},
        patch_sha256=sha(PROPOSAL / "progress64M-reporting.patch"), campaign_sha256=CAMPAIGN_SHA,
        quality_receipts=19, globally_disjoint_games=2156,
        apply_note="Only root may apply. After approval, use canonical renderer path in the new source record and remove plotting.proposal_renderer_path before final canonical render; preserve the archived original renderer hash.")
    write_json(PROPOSAL / "prepared.json", record)
    print(json.dumps(dict(proposal=str(PROPOSAL), renderer_sha256=sha(proposed/renderer.name), patch_sha256=record["patch_sha256"])))


if __name__ == "__main__":
    main()
