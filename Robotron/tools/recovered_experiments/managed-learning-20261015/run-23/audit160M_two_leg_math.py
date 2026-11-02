"""Read-only final160M two-leg arithmetic/provenance audit; no model loads."""
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

analysis, analysis_sha = snapshot(D / "quality160M-guard-two-leg-final-analysis.json")
first_analysis, first_analysis_sha = snapshot(D / "quality160M-guard-first-analysis.json")
prior_audit, prior_audit_sha = snapshot(D / "quality160M-first-guard-independent-math-audit.json")
plan, plan_sha = snapshot(D / "quality160M-preparation/quality160M-regression-guard-plan.json")
checks = {"adopted_plan_pin": plan_sha == "dc9a1ed23a24dd3457455ac7fbd3f31c88c3764d47b96ba413a2d0974c90583c",
          "prior_first_leg_arithmetic_proof_reused_unchanged":
              prior_audit_sha == "62fa055e56f6e3fc37d14ee218c7b1532bcd8558142c2070e8315a17e18d3eef"
              and prior_audit["pass"] is True and all(prior_audit["checks"].values())
              and first_analysis_sha == prior_audit["analysis_sha256"]}
labels = plan["candidate"]["labels"]
reference_labels = [row["label"] for row in plan["reference"]["sources"]]
sources, legs, raw_receipts = {}, {}, {}
for source in analysis["sources"]:
    receipt, actual = snapshot(source["path"])
    assert actual == source["sha256"]
    leg = validate_receipt(receipt)
    assert leg["label"] == source["label"] and leg["label"] not in legs
    sources[leg["label"]] = source
    legs[leg["label"]] = leg
    raw_receipts[leg["label"]] = receipt
old_sources = {row["label"]: row for row in first_analysis["sources"]}
checks["prior23_receipt_pins_retained_plus_only_requested_second"] = (
    {key:value for key,value in sources.items() if key != labels[1]} == old_sources
    and len(sources) == 24 and sources[labels[1]]["sha256"] ==
        "b41c0bb948168e9f5aa4be91e95b41539a7295b930582a9b4e72ac407162b5d3")
all_ids = [row["journal_game_id"] for leg in legs.values() for row in leg["rows"]]
checks["all24_receipts_and2500_original_game_IDs_globally_disjoint"] = (
    len(all_ids) == len(set(all_ids)) == 2500
    and analysis["global_ids"] == dict(receipts=24, games=2500, overlaps=0))
base = [row for name in reference_labels for row in legs[name]["rows"]]
candidate_rows = {name: legs[name]["rows"] for name in labels}
pooled = [row for name in labels for row in candidate_rows[name]]
base_stats = stats(base)
leg_stats = {name: stats(rows) for name,rows in candidate_rows.items()}
pooled_stats = stats(pooled)
management = analysis["management"]
thresholds = dict(mean=.9*base_stats["mean"], median=.9*base_stats["median"], severe_mean=.8*base_stats["mean"])
checks["reference_only_original128M148_mean_median_unchanged"] = (
    base_stats == management["reference"] == first_analysis["management"]["reference"]
    and all(base_stats[key] == plan["reference"][key] for key in ("count", "mean", "median")))
checks["strict90_mean_median80_plus_median_severe_thresholds_unchanged"] = (
    management["thresholds"] == thresholds == first_analysis["management"]["thresholds"]
    and thresholds["mean"] == plan["precommitted_decisions"]["mean_alarm_below"]
    and thresholds["median"] == plan["precommitted_decisions"]["median_alarm_below"]
    and thresholds["severe_mean"] == plan["precommitted_decisions"]["severe_mean_below"])
expected_legs = []
for name in labels:
    value = dict(leg_stats[name])
    value.update(label=name, mean_alarm=value["mean"] < thresholds["mean"],
                 median_alarm=value["median"] < thresholds["median"], low_N=value["count"] < 64)
    expected_legs.append(value)
checks["both_full_leg_stats_and_individual_N59_N56_flags_exact"] = (
    management["each_leg"] == expected_legs
    and [row["count"] for row in expected_legs] == [59,56]
    and all(row["low_N"] and not row["mean_alarm"] and not row["median_alarm"] for row in expected_legs))
first = expected_legs[0]
needs = first["mean_alarm"] or first["median_alarm"] or first["low_N"]
mean_repeated = all(row["mean_alarm"] for row in expected_legs)
median_repeated = all(row["median_alarm"] for row in expected_legs)
severe = first["mean"] < thresholds["severe_mean"] and first["median_alarm"]
status = ("repeated_same_criterion_alarm_root_review" if mean_repeated or median_repeated else
          "mixed_alarm_inconclusive" if any(row["mean_alarm"] or row["median_alarm"] for row in expected_legs) else
          "low_precision_inconclusive" if sum(row["count"] for row in expected_legs) < 64 else
          "no_preset_alarm_not_proof_of_noninferiority")
expected_management = dict(status=status, reference=base_stats, thresholds=thresholds, each_leg=expected_legs,
    confirmation_required_by_first_leg=bool(needs), confirmation_still_needed=False,
    extra_second_leg_not_requested_by_plan=not needs, repeated_mean_alarm=mean_repeated,
    repeated_median_alarm=median_repeated, repeated_same_criterion_alarm=mean_repeated or median_repeated,
    low_N_leg_labels=[row["label"] for row in expected_legs if row["low_N"]],
    maximum_valid_legs_reached=True, third_valid_cohort_authorized=False,
    severe_first_leg_alert=severe, promotion=False, reference_rebased=False,
    scheduled192M_changed=False, automatic_action=False,
    rule=first_analysis["management"]["rule"])
checks["precommitted_two_leg_management_exact_no_alarm_no_third_or_action"] = management == expected_management
checks["first_leg_original_alarm_flags_comparison_and_denominator_not_rewritten"] = (
    management["each_leg"][0] == first_analysis["management"]["each_leg"][0]
    and analysis["each_candidate_vs_composite"][labels[0]] == first_analysis["each_candidate_vs_composite"][labels[0]]
    and analysis["full_leg_denominators"][:3] == first_analysis["full_leg_denominators"])
comparisons = {labels[1]: (candidate_rows[labels[1]], analysis["each_candidate_vs_composite"][labels[1]]),
               "descriptive_pool_not_a_decision_or_receipt": (pooled, analysis["pooled_candidate_vs_composite"])}
bootstrap_evidence = {}
for name,(rows,comparison) in comparisons.items():
    summary = stats(rows)
    checks[name+"_statistics_contrasts_original_IDs_exact"] = (
        all(comparison["candidate"][key] == value for key,value in summary.items())
        and all(comparison["reference"][key] == value for key,value in base_stats.items())
        and comparison["candidate"]["game_ids"] == [row["journal_game_id"] for row in rows]
        and comparison["mean_difference"] == summary["mean"]-base_stats["mean"]
        and comparison["mean_ratio"] == summary["mean"]/base_stats["mean"]
        and comparison["median_difference"] == summary["median"]-base_stats["median"])
    bootstrap_evidence[name] = {}
    for cluster,key in [(False,"game_bootstrap"),(True,"paired_slot_bootstrap")]:
        value = sensitivity(base,rows,cluster)
        bootstrap_evidence[name][key] = value
        checks[name+"_"+key+"_fixed10000_exact"] = (
            comparison[key]["iterations"] == 10000 and comparison[key]["seed"] == 20261016
            and all(comparison[key][field] == calculated for field,calculated in value.items()))
    contrasts = {}
    for slot in range(4096,4112):
        values = [[row["score"] for row in group if row["client_slot"] == slot] for group in (base,rows)]
        means = [statistics.mean(scores) for scores in values]
        contrasts[str(slot)] = dict(reference_count=len(values[0]),candidate_count=len(values[1]),
            reference_mean=means[0],candidate_mean=means[1],mean_difference=means[1]-means[0],mean_ratio=means[1]/means[0])
    checks[name+"_all16_slot_contrasts_exact"] = (
        comparison["actor_contrasts"] == contrasts
        and comparison["slots_with_positive_mean_contrast"] == sum(value["mean_difference"] > 0 for value in contrasts.values()))
expected_denominators = []
for name in reference_labels+labels:
    leg = legs[name]
    expected_denominators.append(dict(label=name,started=len(leg["rows"]),count=len(leg["rows"]),pending=0,abandoned=0,
        valid=True,complete=True,start_ts=leg["start_ts"],close_ts=leg["close_ts"],
        latest_tail_end_unix_s=max(row["end_unix_s"] for row in leg["rows"]),
        completed_tails_after_admission=sum(row["end_unix_s"] > leg["close_ts"] for row in leg["rows"])))
checks["all_four_original_denominators_full_late_tails_retained"] = analysis["full_leg_denominators"] == expected_denominators
lineage, lineage_sha = snapshot(D/"fresh3-160M-checkpoint-lineage.json")
checks["same_final160M_lineage_actual_clocks_Adam_and_counter_scope"] = (
    lineage_sha == analysis["lineage"]["sha256"] == first_analysis["lineage"]["sha256"]
    == "39567648447348732d8b44dcb6f59d8d20ded5f688462ede5afdcea937fa59e5"
    and all(analysis[key] == first_analysis[key] for key in ("policy_identity", "optimizer_exposure", "exposure_deltas",
        "actual_recorded_batch_exposure", "branch_provenance", "process_counter_evidence"))
    and analysis["process_counter_evidence"]["available"] is False
    and all(raw_receipts[name]["checkpoint_metadata"] == raw_receipts[labels[0]]["checkpoint_metadata"]
            and raw_receipts[name]["checkpoint_sha256"] == lineage["candidate"]["sha256"] for name in labels))
checks["matched_backend_and_separate_unpromoted96_history_unchanged"] = (
    analysis["matched_frozen_backend"] == first_analysis["matched_frozen_backend"]
    and analysis["additional_history"] == first_analysis["additional_history"]
    and all(row["pooled_into_reference"] is False for row in analysis["additional_history"]))
audits = []
for suffix,pin in [("01","1b48331696ad32a7934cbe546a4abb1f44e41e600da6dc692ae80e91444e5802"),
                   ("02","437d9ffc17939b58219b5e988fc8045a03a9a7a279cd6e905003ce435797fd58")]:
    report, actual = snapshot(D/f"quality160M-guard{suffix}-final-isolation-audit.json")
    audits.append(dict(path=str(D/f"quality160M-guard{suffix}-final-isolation-audit.json"),sha256=actual))
    checks["guard"+suffix+"_fulltail_runtime0_owned20cleanup_isolation_proof_pinned"] = (
        actual == pin and report["pass"] is True and all(report["checks"].values())
        and report["receipt_sha256"] == sources[labels[int(suffix)-1]]["sha256"])
small_evidence = []
for row in analysis["evidence"]:
    if Path(row["path"]).suffix == ".pt": continue
    assert hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() == row["sha256"]
    small_evidence.append(row)
checks["small_evidence_reference_boot_source_pins_rechecked_without_model_hashes"] = bool(small_evidence)
checks["no_fabricated_receipt_promotion_protection_rebase_or_control_changes"] = (
    analysis["all_source_receipts_separately_validated"] is True
    and analysis["no_fabricated_measurement_receipt"] is True
    and analysis["promotion"] is analysis["protection"] is analysis["state_or_control_changes"] is False)
result = dict(schema="robotron-160M-two-leg-independent-math-provenance-audit-v1",
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,
    analysis_path=str(D/"quality160M-guard-two-leg-final-analysis.json"),analysis_sha256=analysis_sha,
    prior_first_leg_math_audit_sha256=prior_audit_sha,reference=base_stats,each_leg=leg_stats,
    descriptive_pool=pooled_stats,global_ids=analysis["global_ids"],management=management,
    independently_reproduced_new_bootstrap_sensitivities=bootstrap_evidence,
    final_isolation_audits=audits,small_evidence_pins_checked=small_evidence,
    scope="Final full-receipt arithmetic/provenance only; first-leg proof/history retained unchanged. No partial quality reads, old/new model payload hashing or loading, Torch/GPU calls, controls/process/source mutation or launches. Both individual N<64 flags stay visible; the descriptive115-row pool neither erases them nor grants a third leg, promotion/rebase, automatic action or noninferiority proof. Candidate-time Adam/logical/counter clocks remain separate; natural bank overlap is metadata-only evidence.")
result["pass"] = all(checks.values())
p = D/"quality160M-two-leg-independent-math-audit.json"
with p.open("x") as f:
    json.dump(result,f,indent=2,allow_nan=False); f.write("\n"); f.flush(); os.fchmod(f.fileno(),0o444); os.fsync(f.fileno())
print(json.dumps(dict(PASS=result["pass"],failed=[key for key,value in checks.items() if not value],
    checks=len(checks),analysis_sha256=analysis_sha,audit_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    status=status,each_leg=leg_stats,descriptive_pool=pooled_stats),indent=2))

