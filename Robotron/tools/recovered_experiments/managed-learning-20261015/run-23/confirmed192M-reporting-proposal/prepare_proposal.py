#!/usr/bin/env python3
"""Prepare five reporting files only, using already published192M evidence."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import difflib
import hashlib
import json
import statistics
import math

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
GAME = REPO / "Robotron"
BASE = GAME / "logs/managed-learning-20261015"
RUN = BASE / "run-23"
CANONICAL = {
    "render_learning_progress.py": GAME / "tools/render_learning_progress.py",
    "learning-and-throughput-progress.json": BASE / "learning-and-throughput-progress.json",
    "learning-and-throughput-progress.png": BASE / "learning-and-throughput-progress.png",
    "DELL_SETUP.md": GAME / "DELL_SETUP.md",
    "PIPELINE_REPORTING.md": GAME / "tools/PIPELINE_REPORTING.md",
}
BEFORE_SHAS = {
    "render_learning_progress.py": "bcb9a55007c263da831dd4e9f56fff92dcc6adb9068b61085862f3a8444f7c4d",
    "learning-and-throughput-progress.json": "dfc9207baaa0937804de4e70fa996b1b1dc92061135eaa1d5bfe30ac8c0b4442",
    "learning-and-throughput-progress.png": "c20ba4b664a91c35f797bf78f4bc97219cec9c267820edf3b2a95f67a17e343e",
    "DELL_SETUP.md": "622c27245c15e19f1690b515ea3f594ce1bf5341bdd004d6a70360cba910a0fb",
    "PIPELINE_REPORTING.md": "7ca94f72219c4fadbc34c2892816fb6cfea95820f08567bf71163cd3954c012e",
}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def stat_record(path):
    x = Path(path).stat()
    return dict(size_bytes=x.st_size, mtime_ns=x.st_mtime_ns, inode=x.st_ino,
        device=x.st_dev, mode=oct(x.st_mode & 0o777), nlink=x.st_nlink)


def main():
    before, proposed = HERE / "before", HERE / "proposed"
    before.mkdir(); proposed.mkdir()
    for name, path in CANONICAL.items():
        value = path.read_bytes()
        assert sha(value) == BEFORE_SHAS[name], name
        (before / name).write_bytes(value)
    def evidence(path, expected=None):
        value = Path(path).read_bytes()
        assert expected is None or sha(value) == expected, str(path)
        return json.loads(value)
    campaign_path = BASE / "sidecar-fresh3-192M-confirmed-campaign.json"
    campaign = evidence(campaign_path, "23f01f6e377dd1a34fb3a10ab9f2a14439b58ffd03fed4acccdcb7513349ecaa")
    promotion_path = RUN / "quality192M-root-promotion-audit.json"
    promotion = evidence(promotion_path)
    assert promotion["root_promoted"] is True and promotion["learning_recipe_changed"] is False
    analysis_path = Path(campaign["comparison_report"]["path"])
    analysis = evidence(analysis_path, campaign["comparison_report"]["sha256"])
    assert campaign["gain_gate"] == analysis["management"]
    meta_path = GAME / "models_dqn/managed-incumbents/fresh3-192M-confirmed.pt.json"
    meta = evidence(meta_path, "f5a0ef9c1c0c046abfcdf8c98456dd58644d38a9073ca2f601d140a034a94e09")
    data = evidence(before / "learning-and-throughput-progress.json")
    original = copy.deepcopy(data)
    stats = campaign["descriptive_pools"]["confirmed192M"]
    assert stats == analysis["pooled_candidate_vs_composite"]["candidate"]
    assert stats["count"] == 113 and analysis["global_ids"] == dict(receipts=26, games=2613, overlaps=0)
    label = "GPU0 fixed-transport 192M confirmed"
    sources = campaign["sources"]
    new_group = dict(label=label, backend_series="gpu0-compiled-fixed-transport-3s",
        **{k: stats[k] for k in ("count", "mean", "median", "se")},
        constituent_labels=[s["label"] for s in sources], constituent_counts=[52, 61], actor_slots=list(range(4096, 4112)),
        source_receipts=[s["path"] for s in sources], checkpoint_sha256=meta["sha256"],
        unit="Descriptive original-row pool of two separately validated same-policy full-tail cohorts; not a merged receipt",
        plot_label="192M\nconfirmed\nn=113")
    data["fixed_transport_learning"].append(new_group)
    data["fixed_transport_plot_order"].append(label)
    history_groups = []
    for source in campaign["additional_history"]:
        if "160M" not in source["label"]:
            continue
        receipt = evidence(source["path"], source["sha256"])
        values = [row["score"] for row in receipt["rows"]]
        history_groups.append(dict(label=source["label"], backend_series="gpu0-compiled-fixed-transport-3s",
            role="unpromoted-regression-guard-history", promoted=False, plotted=False,
            count=len(values), mean=statistics.mean(values), median=statistics.median(values),
            se=statistics.stdev(values)/math.sqrt(len(values)), constituent_labels=[source["label"]],
            constituent_counts=[len(values)], actor_slots=list(range(4096, 4112)), source_receipts=[source["path"]],
            checkpoint_sha256=receipt["checkpoint_sha256"], unit="One original valid full-tail unpromoted regression guard; history only"))
    assert [g["count"] for g in history_groups] == [59, 56]
    data["unplotted_guard_history"] = history_groups
    data["schema"] = "robotron-learning-throughput-figure-v7"
    data["created_utc"] = datetime.now(timezone.utc).isoformat()
    data["scope"] = "Confirmed quality through192M; separate unpromoted single96M and two160M guards. Three distinct backend series; dated throughput and bank observations remain descriptive."
    data["plotting"].update(confirmed_stage="192M (fixed-transport GPU0)", fixed_transport_score_axis_maximum=290000)
    data["progress"].update(latest_confirmed_stage="192M", current_managed_reference="192M confirmed original113-game pool",
        previous128M_reference_preserved=True, GPU0_fixed_transport_gain_192M_vs_128M_pct=(stats["mean"] / campaign["descriptive_pools"]["composite128M"]["mean"] - 1)*100)
    data["fixed_transport_provenance"].update(latest_campaign_report=str(campaign_path), **{"192M_policy_saved_clocks": meta["saved_checkpoint_metadata"]})
    data["validation"].update(constituent_game_count=2613, constituent_cohort_count=26,
        current_managed_reference_128M=False, current_managed_reference_192M=True,
        all26_receipts_revalidated=True, all2613_game_ids_disjoint=True,
        pooled_192M_matches_independent_campaign=True, each_192M_leg_passes_original128M_gate=True,
        unpromoted160M_guards_history_only=True, previous_fixed_transport_points_unchanged=True)
    data["confirmed192M_selection"] = dict(promoted_utc=promotion["utc"], count=113,
        reference_for_this_comparison="Original protected128M148 rows", current_managed_reference="192M",
        each_leg=analysis["management"]["each_leg"], comparison=analysis["pooled_candidate_vs_composite"],
        root_promotion_audit=str(promotion_path), protected_checkpoint=str(GAME / meta["checkpoint"])
            if not Path(meta["checkpoint"]).is_absolute() else meta["checkpoint"],
        protected_checkpoint_sha256=meta["sha256"], protected_metadata_sha256=sha(meta_path.read_bytes()),
        saved_policy_clocks=meta["saved_checkpoint_metadata"], optimizer_exposure=meta["optimizer_exposure"],
        scope="Actual ROOT promotion after both separate fixed legs pass. Original113 rows only,128M148 baseline;96M/160M guards history only. No causal batch/compiler attribution.")
    caption = data["caption"].splitlines()
    caption[1] = "A: historical GB300 (*4M/8M select-v1/1000 µs; earlier busy). B: earlier GPU0 transport. C: confirmed 192M +28.9% vs 128M; 96M hollow /160M unplotted guards unpromoted."
    data["caption"] = "\n".join(caption)
    renderer = (before / "render_learning_progress.py").read_text()
    renderer = renderer.replace('*data.get("fixed_transport_learning", []), *data.get("observational_guards", [])]',
        '*data.get("fixed_transport_learning", []), *data.get("observational_guards", []),\n                  *data.get("unplotted_guard_history", [])]')
    renderer = renderer.replace('    event = data.get("bank_output_first_events")',
        '    for guard in data.get("unplotted_guard_history", []):\n        if (guard["role"] != "unpromoted-regression-guard-history" or guard["promoted"] is not False\n                or guard["plotted"] is not False or len(guard["source_receipts"]) != 1):\n            raise ValueError("Unplotted guards must remain separate unpromoted original cohorts")\n    event = data.get("bank_output_first_events")')
    renderer = renderer.replace('"128M incumbent · hollow diamond: single-cohort 96M guard"', '"192M incumbent · hollow: single-cohort 96M guard"')
    renderer = renderer.replace('"64M", "#b87536", positions=positions, gain_reference_index=-2)', '"128M", "#b87536", positions=positions, gain_reference_index=-2)')
    renderer = renderer.replace('Confirmed through 128M; 96M guard unpromoted', 'Confirmed through 192M; 96M / 160M guards unpromoted')
    renderer = renderer.replace('fixed_transport_gain_128M_vs_64M_pct=fixed_gain,',
        'fixed_transport_gain_128M_vs_64M_pct=(fixed_groups[3]["mean"] / fixed_groups[2]["mean"] - 1) * 100,\n                fixed_transport_gain_192M_vs_128M_pct=fixed_gain,')
    (proposed / "render_learning_progress.py").write_text(renderer)
    proposed_renderer_sha = sha(renderer.encode())
    data["plotting"]["renderer_sha256"] = proposed_renderer_sha
    canonical_renderer = str(CANONICAL["render_learning_progress.py"])
    for source in data["sources"]:
        if source["path"] == canonical_renderer:
            source["sha256"] = proposed_renderer_sha
    data["sources"].append(dict(path=str(before / "render_learning_progress.py"), sha256=BEFORE_SHAS["render_learning_progress.py"]))
    extra_paths = [campaign_path, analysis_path, meta_path, promotion_path,
        RUN / "quality192M-two-leg-independent-summary.json", RUN / "quality192M-two-leg-independent-followup.json",
        RUN / "confirmed192M-publication-proposal/independent-review.json"]
    extra_paths.extend(Path(s["path"]) for s in [*campaign["sources"], *campaign["additional_history"]])
    extra_paths.extend(Path(s["path"]) for s in campaign["main_training_isolation_provenance"].values())
    extra_paths.extend(BASE / relative for relative in promotion["evidence_sha256"])
    extra_paths.extend([Path(campaign["lineage"]["path"]), RUN / "quality192M-preparation/quality192M-assessment-plan.json",
        RUN / "quality192M-preparation/analyze192M_assessment.py", RUN / "quality192M-preparation/history-manifest.final.json"])
    known = {row["path"] for row in data["sources"]}
    for path in extra_paths:
        if str(path) not in known:
            assert path.suffix != ".pt"
            data["sources"].append(dict(path=str(path), sha256=sha(path.read_bytes())))
            known.add(str(path))
    model_path = Path(data["confirmed192M_selection"]["protected_checkpoint"])
    data["sources"].append(dict(path=str(model_path), sha256=meta["sha256"]))
    models = {}
    old_prepared = evidence(RUN / "confirmed128M-reporting-proposal/prepared.json")
    for path, record in old_prepared["model_payload_refresh"]["files"].items():
        assert stat_record(path) == record["stat"], path
    for source in data["sources"]:
        if source["path"].endswith(".pt"):
            models[source["path"]] = dict(sha256_attestation=source["sha256"], stat=stat_record(source["path"]))
    (proposed / "learning-and-throughput-progress.json").write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    dell = (before / "DELL_SETUP.md").read_text().replace(
        '16M-to-32M-to-64M-to-128M series separately', '16M-to-32M-to-64M-to-128M-to-192M series separately')
    dell = dell.replace('Root protected and promoted 128M at 12:45:15.271 UTC. It is now the managed\nincumbent and reference;',
        'Root protected and promoted 128M at 12:45:15.271 UTC. It became the managed\nincumbent and reference at that point;')
    dell = dell.replace('Panel C now connects only confirmed policies\nthrough 128M,', 'At that publication, panel C connected confirmed policies\nthrough 128M,')
    dell += '''

The fixed 192M assessment completed both prescribed full-tail cohorts on the
same GPU0 compiled FP32/TF32, 16-slot, fixed-transport/3s backend. All 52 and
61 admitted games remain: means 288,144.71 and 247,667.62, medians 271,225 and
222,650. Each independently passed mean >=216,946.3176 (1.05 times the original
128M 148-game mean) and median >=166,112.5. Both counts meet the existing
50-whole-game validity floor; N<64 is a precision caveat, not grounds for an
extra valid cohort or pooled rescue. Both legs covered all 16 private slots,
retained every late tail and had zero measured runtime errors.

The descriptive original-row pool has 113 games: mean 266,294.25, median
230,150 and SE 11,652.97, a 28.8839% mean gain over the fixed original128M
reference. All 16 pooled actor-slot mean contrasts were positive. Fixed
10,000-draw game and paired-slot bootstrap ratio sensitivities were
[1.160, 1.430] and [1.200, 1.389]. They are descriptive, without repeated-look,
policy-selection or shared-trajectory corrections, not formal confidence.
The 96M single cohort and both completed160M regression guards remain unpromoted
history and enter neither the 113-game candidate pool nor the 148-game reference.
The160M guards are retained in the figure JSON but are not plotted; the96M
guard remains a separate hollow marker.

Root protected and promoted192M at16:52:44.318 UTC on2026-10-16. It is the new
managed incumbent/reference;128M and all earlier protected artifacts remain
preserved. The independent readonly copy is
`models_dqn/managed-incumbents/fresh3-192M-confirmed.pt`, SHA256
`5076199285752a8748ce9566bc74c6b67210a03ae7f04f132f92b786dea102da`.
Its `.pt.json` and
`logs/managed-learning-20261015/sidecar-fresh3-192M-confirmed-campaign.json`
link the final root CPU lineage, original receipts, strict two-leg analysis and
positive final isolation/cleanup audits. The promotion receipt is
`logs/managed-learning-20261015/run-23/quality192M-root-promotion-audit.json`.

The confirmation retains eight generic raw health-alert rows and ten tracebacks
classified as `Inference batcher stopped before completion`, raised only during
deliberate post-cutoff batcher shutdown. Source-order and log evidence are
preserved in `run-23/quality192M-confirm01-shutdown-stack-classification.json`;
they were not erased or recast as healthy runtime inference. This classified
cleanup evidence and both full-game validators support the positive final audit.

Saved clocks were1,156,456 logical updates,3,289,255,936 optimized samples and
196,632,084 learner frames; the81 Adam states each recorded1,155,946 steps.
These clocks remain distinct from process-local applied/AMP-skip counters; no
whole-interval outcome reconciliation is inferred. Supporting all-row medians
rose from level9 to12 and7,914 to 10,065 playable frames; observed deaths9 to12
can reflect longer games and earned extra lives. Wall duration84.36 to109.16s
includes host and inactive intervals. These are diagnostics, not new gates.
The learning recipe remained unchanged. The gain does not establish a causal
batch-size/compiler effect. Panel C appends confirmed192M to the same backend
curve; all older quality series, bank caveats and dated throughput A–B–A data
remain unchanged.
'''
    for a,b in (('original128M','original 128M'),('completed160M','completed 160M'),('The160M','The 160M'),('the96M','the 96M'),('promoted192M','promoted 192M'),('at16:','at 16:'),('on2026','on 2026'),('reference;128M','reference; 128M'),('were1,','were 1,'),('updates,3,','updates, 3,'),('and\n196,','and\n196,'),('the81','the 81'),('recorded1,','recorded 1,'),('level9','level 9'),('to12','to 12'),('and7,','and 7,'),('deaths9','deaths 9'),('duration84','duration 84'),('to109','to 109'),('confirmed192M','confirmed 192M')):
        dell=dell.replace(a,b)
    (proposed / "DELL_SETUP.md").write_text(dell)
    pipeline = (before / "PIPELINE_REPORTING.md").read_text().replace(
        'confirmed 128M promotion and preserved 64M/96M history are documented in',
        'confirmed 128M and192M promotions and preserved64M/96M/160M history are documented in')
    pipeline += '''

## Confirmed192M quality reporting

The192M reference update is separate from host pipeline or exposure telemetry.
Two original full-tail cohorts (52 and61 games) independently passed the fixed
5% mean-gain and median-floor gates against the original128M148-game reference.
The descriptive113-row pool is mean266,294.25, median230,150 and SE11,652.97
(+28.8839% mean); it is not a fabricated valid measurement receipt. Root promoted
the protected192M policy at16:52:44.318 UTC on2026-10-16;128M is preserved.
Both160M guards and the single96M guard remain unpromoted history, not baseline.
The official50-whole-game floor,16-slot/full-tail protocol and runtime failure
rules remain unchanged. Low N and bootstrap/SE precision limits are disclosed.

The final192M campaign and root promotion audit are linked from `../DELL_SETUP.md`.
The confirmation's eight raw generic alerts and ten intentional batcher-stop
cleanup tracebacks are retained with explicit post-cutoff source-order evidence;
the two full cohorts have zero measured runtime errors. Host elapsed duration,
maximum observed level, playable frames and recorded deaths are supporting
diagnostics only. More deaths can accompany earned lives and longer games.
Logical updates/optimized samples, actual saved Adam steps and timestamped
process/epoch application counters stay separate; no whole-interval AMP claim,
new schedule, new telemetry column or causal batch/compiler conclusion follows.
'''
    for a,b in (('and192M','and 192M'),('preserved64M','preserved 64M'),('Confirmed192M','Confirmed 192M'),('The192M','The 192M'),('and61','and 61'),('original128M148','original 128M 148'),('descriptive113','descriptive 113'),('mean266','mean 266'),('median230','median 230'),('SE11','SE 11'),('protected192M','protected 192M'),('at16:','at 16:'),('on2026','on 2026'),(';128M','; 128M'),('Both160M','Both 160M'),('single96M','single 96M'),('official50','official 50'),('floor,16','floor, 16'),('final192M','final 192M')):
        pipeline=pipeline.replace(a,b)
    (proposed / "PIPELINE_REPORTING.md").write_text(pipeline)
    patches=[]
    for name in ("render_learning_progress.py", "DELL_SETUP.md", "PIPELINE_REPORTING.md"):
        target = str(CANONICAL[name].relative_to(REPO))
        patches.extend(difflib.unified_diff((before/name).read_text().splitlines(True),
            (proposed/name).read_text().splitlines(True), fromfile="a/"+target, tofile="b/"+target))
    (HERE / "confirmed192M-reporting.patch").write_text("".join(patches))
    assert data["learning"] == original["learning"] and data["sidecar_learning"] == original["sidecar_learning"]
    assert data["fixed_transport_learning"][:-1] == original["fixed_transport_learning"]
    assert all(data[k] == original[k] for k in ("throughput", "efficiency_update", "batch_aba_throughput", "observational_guards", "bank_output_first_events", "confirmed128M_selection"))
    prepared = dict(schema="robotron-confirmed192M-reporting-preparation-v1", utc=datetime.now(timezone.utc).isoformat(),
        status="PROPOSAL_ONLY_CANONICAL_UNTOUCHED_RENDER_PENDING", before={name:dict(path=str(path),sha256=BEFORE_SHAS[name]) for name,path in CANONICAL.items()},
        model_payload_refresh=dict(payloads_rehashed=False, scope="Inherited root publication/source SHA attestations plus repeated file-stat guards; small sources freshly byte-hashed. No model payload read/hash or load.", files=models),
        proposed={name:dict(path=str(proposed/name),sha256=sha((proposed/name).read_bytes())) for name in CANONICAL if name!="learning-and-throughput-progress.png"},
        patch_sha256=sha((HERE / "confirmed192M-reporting.patch").read_bytes()), old_learning_and_performance_data_unchanged=True,
        current192M_only_after_actual_ROOT_promotion=True, expected_validation=dict(cohorts=26,unique_games=2613,observational_guard_count=1,unplotted_guard_history_count=2,batch_trials=3))
    (HERE / "prepared.json").write_text(json.dumps(prepared,indent=2)+"\n")
    print(json.dumps({k:v for k,v in prepared.items() if k!="model_payload_refresh"},indent=2))


if __name__ == "__main__":
    main()
