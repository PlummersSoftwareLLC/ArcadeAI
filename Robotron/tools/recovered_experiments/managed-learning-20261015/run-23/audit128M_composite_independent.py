"""Read-only final128M arithmetic/provenance check; never loads model tensors."""
import collections
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys

D = Path(__file__).resolve().parent
C = D.parent
G = D.parents[2]
sys.path.insert(0, str(G / "tools"))
from compare_frozen_measurements import validate_receipt

def snapshot(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()

def stats(rows):
    scores = [row["score"] for row in rows]
    sd = statistics.stdev(scores)
    return dict(count=len(scores), mean=statistics.mean(scores), median=statistics.median(scores),
                sd=sd, se=sd / math.sqrt(len(scores)))

def quantile(values, probability):
    values = sorted(values)
    position = (len(values) - 1) * probability
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)

def sensitivity(base, candidate, cluster):
    """Independently reproduce the prespecified seed/draw order and percentile arithmetic."""
    rng = random.Random(20261016)
    groups = []
    for rows in (base, candidate):
        slots = collections.defaultdict(list)
        for row in rows:
            slots[row["client_slot"]].append(row["score"])
        groups.append(dict(sorted(slots.items())))
    differences, ratios = [], []
    for _ in range(10000):
        draw = rng.choices(list(groups[0]), k=len(groups[0])) if cluster else None
        means = []
        for rows, slots in zip((base, candidate), groups):
            scores = ([score for slot in draw for score in slots[slot]] if cluster
                      else [row["score"] for row in rng.choices(rows, k=len(rows))])
            means.append(statistics.fmean(scores))
        differences.append(means[1] - means[0])
        if means[0] > 0:
            ratios.append(means[1] / means[0])
    return dict(mean_difference_ci=[quantile(differences, .025), quantile(differences, .975)],
                mean_ratio_ci=[quantile(ratios, .025), quantile(ratios, .975)])

analysis, analysis_sha = snapshot(D / "quality128M-two-leg-final-analysis.json")
plan, plan_sha = snapshot(C / "run-20/quality128M-preparation/quality128M-promotion-plan.json")
checks = {"precommit_bytes_pinned": plan_sha == "2c76ab8c6d2e7fd2b8f572620f6f0922e17e97338291102b38800527870bfc66"}
sources, legs, raw_receipts = {}, {}, {}
for source in analysis["sources"]:
    receipt, actual_sha = snapshot(source["path"])
    assert actual_sha == source["sha256"]
    leg = validate_receipt(receipt)
    assert source["label"] == leg["label"] and source["label"] not in sources
    sources[source["label"]] = source
    legs[leg["label"]] = leg
    raw_receipts[leg["label"]] = receipt
checks["all22_original_receipt_bytepins_and_full_leg_validators"] = len(sources) == 22

history_sources = {}
campaign_pins = []
def history(path, expected_sha):
    campaign, actual_sha = snapshot(path)
    assert actual_sha == expected_sha
    campaign_pins.append(dict(path=str(path), sha256=actual_sha))
    for source in campaign["sources"]:
        assert source["label"] not in history_sources
        history_sources[source["label"]] = source
    older = campaign.get("historical_segment", {})
    if older.get("path"):
        history(older["path"], older["sha256"])
history(plan["reference"]["campaign"], plan["reference"]["campaign_sha256"])
expected_sources = dict(history_sources)
expected_sources.update({row["label"]: {key: row[key] for key in ("label", "path", "sha256")}
                         for row in plan["additional_history"]})
for label in plan["candidate"]["labels"]:
    expected_sources[label] = sources[label]
checks["global22_source_set_matches_original_campaign_chain_plus96_and_two128"] = expected_sources == sources
all_ids = [row["journal_game_id"] for leg in legs.values() for row in leg["rows"]]
checks["global2385_ids_unique_no_overlap"] = (len(all_ids) == len(set(all_ids)) == 2385
    and analysis["global_ids"] == dict(receipts=22, games=2385, overlaps=0))
reference_labels = [row["label"] for row in plan["reference"]["sources"]]
candidate_labels = plan["candidate"]["labels"]
base = [row for label in reference_labels for row in legs[label]["rows"]]
reference_stats = stats(base)
management = analysis["management"]
checks["original217_reference_summary_no96_rebase"] = (reference_stats == management["reference"]
    and all(reference_stats[key] == plan["reference"][key] for key in ("count", "mean", "median"))
    and analysis["additional_history"] == [dict(label="sidecar-gpu0-96M-regression-guard-01", count=81, pooled_into_reference=False)])
thresholds = dict(mean=1.05 * reference_stats["mean"], median=reference_stats["median"])
checks["precommitted_mean5pct_and_median_thresholds_exact"] = (thresholds == management["thresholds"]
    and thresholds["mean"] == plan["precommitted_decisions"]["mean_at_least_each_leg"]
    and thresholds["median"] == plan["precommitted_decisions"]["median_at_least_each_leg"])
stats_by_label = {label: stats(legs[label]["rows"]) for label in candidate_labels}
for label, stated in zip(candidate_labels, management["each_leg"]):
    actual = stats_by_label[label]
    checks[label + "_separate_statistics_and_criteria"] = (stated["label"] == label
        and all(stated[key] == value for key, value in actual.items())
        and stated["mean_pass"] == (actual["mean"] >= thresholds["mean"])
        and stated["median_pass"] == (actual["median"] >= thresholds["median"])
        and stated["passes_each_criterion"] is True)
checks["two_leg_review_eligibility_without_action_or_third_cohort"] = (
    management["status"] == "two_legs_pass_root_promotion_review"
    and management["promotion_eligible"] is True and management["confirmation_still_needed"] is False
    and all(management[key] is False for key in ("promotion", "protection", "reference_rebased", "automatic_action", "third_valid_cohort_authorized"))
    and all(analysis[key] is False for key in ("promotion", "protection", "state_or_control_changes")))
checks["four_full_denominators_and_all_late_tails_retained"] = True
for label, denominator in zip(reference_labels + candidate_labels, analysis["full_leg_denominators"]):
    receipt, leg = raw_receipts[label], legs[label]
    actual = dict(label=label, started=len(leg["rows"]), count=len(leg["rows"]), pending=0, abandoned=0,
        valid=True, complete=True, start_ts=leg["start_ts"], close_ts=leg["close_ts"],
        latest_tail_end_unix_s=max(row["end_unix_s"] for row in leg["rows"]),
        completed_tails_after_admission=sum(row["end_unix_s"] > leg["close_ts"] for row in leg["rows"]))
    checks["four_full_denominators_and_all_late_tails_retained"] &= actual == denominator
pooled = [row for label in candidate_labels for row in legs[label]["rows"]]
bootstrap_results = {}
for label, rows, comparison in [(label, legs[label]["rows"], analysis["each_candidate_vs_composite"][label]) for label in candidate_labels] + [
        ("pooled_descriptive_only", pooled, analysis["pooled_candidate_vs_composite"])]:
    current = stats(rows)
    comparisons_match = (all(comparison["candidate"][key] == value for key, value in current.items())
        and comparison["mean_difference"] == current["mean"] - reference_stats["mean"]
        and comparison["mean_ratio"] == current["mean"] / reference_stats["mean"]
        and comparison["median_difference"] == current["median"] - reference_stats["median"])
    bootstrap_results[label] = {}
    for cluster, key in [(False, "game_bootstrap"), (True, "paired_slot_bootstrap")]:
        calculated = sensitivity(base, rows, cluster)
        bootstrap_results[label][key] = calculated
        comparisons_match &= all(calculated[name] == comparison[key][name] for name in calculated)
        comparisons_match &= (comparison[key]["iterations"] == 10000 and comparison[key]["seed"] == 20261016)
    contrasts = {}
    for slot in range(4096, 4112):
        scores = [[row["score"] for row in values if row["client_slot"] == slot] for values in (base, rows)]
        means = [statistics.mean(values) for values in scores]
        contrasts[str(slot)] = dict(reference_count=len(scores[0]), candidate_count=len(scores[1]),
            reference_mean=means[0], candidate_mean=means[1], mean_difference=means[1]-means[0], mean_ratio=means[1]/means[0])
    comparisons_match &= (comparison["actor_contrasts"] == contrasts
        and comparison["slots_with_positive_mean_contrast"] == sum(row["mean_difference"] > 0 for row in contrasts.values()))
    checks[label + "_original_rows_contrasts_and_fixed10000_sensitivities_exact"] = comparisons_match

lineage, lineage_sha = snapshot(D / "fresh3-128M-checkpoint-lineage.json")
checks["final_root_lineage_and_actual_saved_clocks_pinned"] = (lineage_sha == analysis["lineage"]["sha256"]
    == "4535f56d71a1fe3c3b6c3f148ae7ab9cc6f9846d6eaa3b420ede0e82bc6eda18"
    and lineage["root_verification"]["status"] == "PASS" and lineage["proposal_only"] is False
    and analysis["policy_identity"]["candidate"]["metadata"] == lineage["candidate"]["saved_metadata"])
metadata = lineage["candidate"]["saved_metadata"]
resume, _ = snapshot(C / "run-20/final-resume-checkpoint.json")
checks["logical_samples_learner_and_adam_exposure_separated_exact"] = (
    analysis["optimizer_exposure"]["candidate128M"] == lineage["candidate"]["optimizer"]
    and analysis["optimizer_exposure"]["minimum_parameter_step_delta"] == 907002 - 606960
    and analysis["optimizer_exposure"]["run20_resume_parameter_steps"] is None
    and all(analysis["exposure_deltas"][name] == {key: metadata[key]-old[key]
        for key in ("training_steps", "optimized_samples", "learner_frame_count")}
        for name, old in [("since64M", plan["reference"]["saved_clocks"]), ("since_run20_resume", resume["saved_metadata"])]))
audits = []
for name, expected in [("quality128M-screen01-final-isolation-audit.json", "225815925087325de6ecd7a53925ab9afa8803f1c5efc9b774b38b24306e9a3d"),
                       ("quality128M-confirm01-final-isolation-audit.json", "58d70b6bb9d9f3a4c3a6a9a6ea127a06fd653442daf7ec5f319eff4cde730a92")]:
    audit, pin = snapshot(D / name)
    audits.append(dict(path=str(D/name), sha256=pin))
    assert pin == expected and audit["pass"] is True and all(audit["checks"].values())
checks["both_independent_publication_compatible_isolation_audits_pinned_PASS"] = len(audits) == 2
small_pins_checked = []
for evidence in analysis["evidence"]:
    if Path(evidence["path"]).suffix == ".pt":
        continue
    raw = Path(evidence["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == evidence["sha256"]
    small_pins_checked.append(evidence)
checks["analysis_small_evidence_bytes_unchanged"] = True
report = dict(schema="robotron-128M-composite-independent-math-provenance-audit-v1",
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), pass_=all(checks.values()), checks=checks,
    analysis=dict(path=str(D/"quality128M-two-leg-final-analysis.json"), sha256=analysis_sha),
    reference=reference_stats, thresholds=thresholds, each_leg=stats_by_label,
    pooled_candidate_descriptive=stats(pooled), pooled_mean_ratio=stats(pooled)["mean"]/reference_stats["mean"],
    global_ids=dict(receipts=len(sources), games=len(all_ids), overlaps=len(all_ids)-len(set(all_ids))),
    original_campaign_chain=campaign_pins, isolation_audits=audits, independently_reproduced_sensitivities=bootstrap_results,
    small_evidence_pins_checked=small_pins_checked,
    scope="No promotion/protection/state/control or source mutation, no Torch/model loads/GPU contexts. PT hashes are not repeated here: exact private128M copies were byte-verified in the pinned isolation audits and root/analyzer records bind prior models. Both separate precommitted leg criteria pass; pooling is descriptive. Sensitivities do not correct repeated looks/selection, shared state or RNG drift; paired slot labels are not identical trajectories.")
report["pass"] = report.pop("pass_")
out = D / "quality128M-two-leg-final-independent-math-audit.json"
with out.open("x") as stream:
    json.dump(report, stream, indent=2, allow_nan=False)
    stream.write("\n")
os.chmod(out, 0o444)
print(json.dumps(dict(pass_=report["pass"], failed=[key for key,value in checks.items() if not value],
    checks=len(checks), audit_sha256=hashlib.sha256(out.read_bytes()).hexdigest(), analysis_sha256=analysis_sha,
    pooled_mean=stats(pooled)["mean"], pooled_mean_ratio=report["pooled_mean_ratio"]), indent=2))
