"""Read-only first160M guard arithmetic/provenance audit; no model loads."""
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

analysis, analysis_sha = snapshot(D / "quality160M-guard-first-analysis.json")
plan, plan_sha = snapshot(D / "quality160M-preparation/quality160M-regression-guard-plan.json")
checks = {"adopted_plan_pin": plan_sha == "dc9a1ed23a24dd3457455ac7fbd3f31c88c3764d47b96ba413a2d0974c90583c"}
sources, legs = {}, {}
for source in analysis["sources"]:
    receipt, actual = snapshot(source["path"])
    assert actual == source["sha256"]
    leg = validate_receipt(receipt)
    assert leg["label"] == source["label"] and leg["label"] not in legs
    sources[leg["label"]] = source
    legs[leg["label"]] = leg
history_sources = {}
def history(path, expected):
    campaign, actual = snapshot(path)
    assert actual == expected
    for source in campaign["sources"]:
        assert source["label"] not in history_sources
        history_sources[source["label"]] = source
    older = campaign.get("historical_segment", {})
    if older.get("path"):
        history(older["path"], older["sha256"])
history(plan["reference"]["campaign"], plan["reference"]["campaign_sha256"])
for row in plan["history"]["additional_history"]:
    history_sources[row["label"]] = {key:row[key] for key in ("label", "path", "sha256")}
label = plan["candidate"]["labels"][0]
expected_sources = dict(history_sources)
expected_sources[label] = sources[label]
checks["all_original23_receipt_pins_history_and_full_leg_validators"] = len(sources) == 23 and sources == expected_sources
all_ids = [row["journal_game_id"] for leg in legs.values() for row in leg["rows"]]
checks["global2444_ids_disjoint_original22plus59"] = (len(all_ids) == len(set(all_ids)) == 2444
    and analysis["global_ids"] == dict(receipts=23, games=2444, overlaps=0))
reference_labels = [row["label"] for row in plan["reference"]["sources"]]
base = [row for name in reference_labels for row in legs[name]["rows"]]
current = legs[label]["rows"]
base_stats, current_stats = stats(base), stats(current)
management = analysis["management"]
checks["original128_reference148_without_history_pooling"] = (base_stats == management["reference"]
    and all(base_stats[key] == plan["reference"][key] for key in ("count", "mean", "median")))
thresholds = dict(mean=.9*base_stats["mean"], median=.9*base_stats["median"], severe_mean=.8*base_stats["mean"])
checks["strict_precommitted90_mean_median80_severe_thresholds"] = (management["thresholds"] == thresholds
    and thresholds["mean"] == plan["precommitted_decisions"]["mean_alarm_below"]
    and thresholds["median"] == plan["precommitted_decisions"]["median_alarm_below"]
    and thresholds["severe_mean"] == plan["precommitted_decisions"]["severe_mean_below"])
first = management["each_leg"][0]
mean_alarm = current_stats["mean"] < thresholds["mean"]
median_alarm = current_stats["median"] < thresholds["median"]
checks["first59_original_statistics_and_no_point_or_severe_alarm"] = (len(management["each_leg"]) == 1
    and first["label"] == label and all(first[key] == value for key,value in current_stats.items())
    and first["mean_alarm"] == mean_alarm == False and first["median_alarm"] == median_alarm == False
    and management["severe_first_leg_alert"] == (current_stats["mean"] < thresholds["severe_mean"] and median_alarm) == False)
checks["N59_precision_only_requests_one_sameSHA_confirmation_no_action"] = (current_stats["count"] == 59
    and first["low_N"] is True and management["status"] == "exact_checkpoint_confirmation_required"
    and management["confirmation_required_by_first_leg"] is True and management["confirmation_still_needed"] is True
    and management["maximum_valid_legs_reached"] is False and management["third_valid_cohort_authorized"] is False
    and management["promotion"] is management["reference_rebased"] is management["automatic_action"] is False
    and management["low_N_leg_labels"] == [label]
    and analysis["promotion"] is analysis["protection"] is analysis["state_or_control_changes"] is False)
comparison = analysis["each_candidate_vs_composite"][label]
checks["original_row_contrast_and_descriptive_pool_exact"] = (analysis["pooled_candidate_vs_composite"] == comparison
    and all(comparison["candidate"][key] == value for key,value in current_stats.items())
    and comparison["mean_difference"] == current_stats["mean"]-base_stats["mean"]
    and comparison["mean_ratio"] == current_stats["mean"]/base_stats["mean"]
    and comparison["median_difference"] == current_stats["median"]-base_stats["median"])
bootstraps = {}
for cluster,key in [(False,"game_bootstrap"),(True,"paired_slot_bootstrap")]:
    calculated = sensitivity(base,current,cluster)
    bootstraps[key] = calculated
    checks[key+"_fixed10000_sensitivity_exact"] = all(comparison[key][name] == value for name,value in calculated.items()) and comparison[key]["iterations"] == 10000 and comparison[key]["seed"] == 20261016
contrasts = {}
for slot in range(4096,4112):
    values = [[row["score"] for row in rows if row["client_slot"] == slot] for rows in (base,current)]
    means = [statistics.mean(scores) for scores in values]
    contrasts[str(slot)] = dict(reference_count=len(values[0]),candidate_count=len(values[1]),reference_mean=means[0],candidate_mean=means[1],mean_difference=means[1]-means[0],mean_ratio=means[1]/means[0])
checks["all16_actor_contrasts_and_counts_exact"] = (comparison["actor_contrasts"] == contrasts
    and comparison["slots_with_positive_mean_contrast"] == sum(row["mean_difference"]>0 for row in contrasts.values()))
checks["all_three_full_denominators_and_late_tails_retained"] = True
for name, denominator in zip(reference_labels+[label],analysis["full_leg_denominators"]):
    leg=legs[name]
    expected=dict(label=name,started=len(leg["rows"]),count=len(leg["rows"]),pending=0,abandoned=0,valid=True,complete=True,start_ts=leg["start_ts"],close_ts=leg["close_ts"],latest_tail_end_unix_s=max(row["end_unix_s"]for row in leg["rows"]),completed_tails_after_admission=sum(row["end_unix_s"]>leg["close_ts"]for row in leg["rows"]))
    checks["all_three_full_denominators_and_late_tails_retained"] &= expected == denominator
lineage, lineage_sha = snapshot(D/"fresh3-160M-checkpoint-lineage.json")
checks["final_root160_lineage_candidate_actual_saved_clocks_exact"] = (lineage_sha == analysis["lineage"]["sha256"] == "39567648447348732d8b44dcb6f59d8d20ded5f688462ede5afdcea937fa59e5"
    and analysis["policy_identity"]["candidate"]["sha256"] == "85cd646d34162f59b0a04853f87f615815b68c8d6d08f6ec3924661dcf7504b5"
    and analysis["policy_identity"]["candidate"]["metadata"] == lineage["candidate"]["saved_metadata"])
checks["logical_samples_learner_Adam_and_counter_clocks_separate"] = (analysis["exposure_deltas"]["since128M"] == dict(training_steps=123549,optimized_samples=506056704,learner_frame_count=32000925)
    and analysis["optimizer_exposure"]["minimum_parameter_step_delta"] == 123492
    and analysis["process_counter_evidence"]["available"] is False)
audit,audit_sha = snapshot(D/"quality160M-guard01-final-isolation-audit.json")
checks["positive_fulltail_runtime0_owned20cleanup_main192_audit_pinned"] = (audit_sha == "1b48331696ad32a7934cbe546a4abb1f44e41e600da6dc692ae80e91444e5802" and audit["pass"] is True and all(audit["checks"].values()))
small_pins=[]
for row in analysis["evidence"]:
    if Path(row["path"]).suffix == ".pt":continue
    assert hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() == row["sha256"]
    small_pins.append(row)
checks["analysis_small_source_reference_boot_proof_pins_unchanged"] = bool(small_pins)
result=dict(schema="robotron-160M-first-guard-independent-math-provenance-audit-v1",utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,analysis_sha256=analysis_sha,analysis_path=str(D/"quality160M-guard-first-analysis.json"),reference=base_stats,first=current_stats,thresholds=thresholds,mean_ratio=current_stats["mean"]/base_stats["mean"],global_ids=analysis["global_ids"],management=management,independently_reproduced_bootstrap_sensitivities=bootstraps,isolation_audit_sha256=audit_sha,small_evidence_pins_checked=small_pins,scope="No partial outcomes read before fullreceipt. Original-row/statistical/provenance arithmetic only; no model payload hash/load repeated, Torch/GPU, controls/process/source changes or cohort launch. N59 is precision-trigger only; no point/severe alarm. Descriptive sequential-look sensitivities are not noninferiority proof, promotion/rebase or a pool-based rescue.")
result["pass"]=all(checks.values())
p=D/"quality160M-first-guard-independent-math-audit.json"
with p.open("x")as f:json.dump(result,f,indent=2,allow_nan=False);f.write("\n")
p.chmod(0o444)
print(json.dumps(dict(PASS=result["pass"],failed=[k for k,v in checks.items()if not v],checks=len(checks),audit_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),analysis_sha256=analysis_sha,mean_ratio=result["mean_ratio"]),indent=2))
