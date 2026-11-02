"""Conditional CE-selected replay sensitivity; default is a literal plan.

No actual target, candidate population, parameter gradient or policy is inferred.
NumPy/Torch and data are used only by a future explicit CPU-only execution.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

SCHEMA = "robotron-live8-four-readout-analysis-inputs-v1"
BATCH, ATTEMPTS = 4096, 8
CE_TOLERANCE = {"rtol": 2e-4, "atol": 2e-5}
PRIORITY_EPSILON, SAMPLE_LEAF_FLOOR = 1e-6, 1e-10
MAX_SMALL_PAYLOAD = 64 << 20
MAX_TOTAL_OUTPUT = 16 << 20
COMMON_PATH = "/home/dave/source/repos/ArcadeAI/Robotron/tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal/offline_actual_ce_analysis_proposal/analyse_actual_ce.py"
COMMON_SHA = "e4ffb0cb95aa4f426005cce351b11cb96b4af30339908183e1f61fbf728875bb"
ACTUAL_ANALYSIS_SHA = "f9235940e47732188dffb3a2b47b5db881d83ca00dd089721892be6296454a43"
ACTUAL_BINDING_SHA = "0c2a528a3b1611b6e746e9ca09653297b62c750e35887bfaa1982dd8258351cf"
WORKER_SHA = "182f008a969f55c2aa5952612f1631b3435cab61cbc5ae42fcd708c4f91a03a7"
RECONSTRUCTION_LOCK_SHA = "683278660704999645e93dfbc7aad1b20423a5755080a76ccad8f3af54c3c82f"
ORIGINS = ("per", "interesting", "recent", "hof", "ephof")
READOUTS = ("emitted", "fresh_actual_ce", "fresh_recomputed_ce", "fresh_recomputed_kl")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ranks(values):
    """Average zero-based ranks; duplicate sampled rows stay separate."""
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result, cursor = [0.0] * len(values), 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[cursor]]:
            end += 1
        for index in ordered[cursor:end]:
            result[index] = (cursor + end - 1) / 2
        cursor = end
    return result


def rank_comparison(left, right):
    require(len(left) == len(right), "Paired rank lengths differ")
    n = len(left)
    if not n:
        return dict(rows=0, spearman=None, top_decile_overlap=None)
    a, b = ranks(left), ranks(right)
    center = (n - 1) / 2
    covariance = math.fsum((x-center)*(y-center) for x,y in zip(a,b))
    aa = math.fsum((x-center)**2 for x in a)
    bb = math.fsum((x-center)**2 for x in b)
    count = max(1, math.ceil(n / 10))
    # Tie-break by original row order only for this explicit top-k description.
    top_a = set(sorted(range(n), key=lambda i:(-left[i],i))[:count])
    top_b = set(sorted(range(n), key=lambda i:(-right[i],i))[:count])
    return dict(rows=n, spearman=covariance/math.sqrt(aa*bb) if aa and bb else None,
        top_decile_overlap=len(top_a & top_b)/count, top_rows=count,
        distinct_left=len(set(left)), distinct_right=len(set(right)),
        top_tie_rule="Original row order; ties are not evidence of a strict ranking")


def fresh_weights(np, metric, draw, parts):
    """Selected-row sensitivity, not a draw from a reconstructed priority tree.

    Preserve metric FP32 -> FP64, epsilon BEFORE alpha, separate sampler floor,
    each vector's FP64 mean PER bank weight, and the final FP32 cast. The
    selected-min normalization cancels an unknown positive tree total away from
    the original raw-weight denominator floor; no new population is asserted.
    """
    metric = np.asarray(metric, dtype=np.float32).astype(np.float64)
    require(metric.ndim == 1 and bool(np.isfinite(metric).all()) and bool((metric >= 0).all()),
        "Fresh metric must be a finite nonnegative row vector")
    alpha, beta = draw["alpha"], draw["beta"]
    require(type(alpha) in (int,float) and math.isfinite(alpha) and 0 <= alpha <= 1
        and type(beta) in (int,float) and math.isfinite(beta) and 0 <= beta <= 1,
        "Captured alpha/beta outside source domain")
    per = list(parts["per"])
    leaves = (np.abs(metric[per]) + PRIORITY_EPSILON) ** alpha
    clamped = np.maximum(SAMPLE_LEAF_FLOOR, leaves)
    weights = np.ones(metric.size, dtype=np.float64)
    if len(per):
        weights[per] = (float(clamped.min()) / clamped) ** beta
        bank_mean = float(np.mean(weights[per]))
        for name in ("hof", "ephof"):
            weights[list(parts[name])] = bank_mean
    return dict(weights_float64=weights.tolist(), weights_float32=weights.astype(np.float32).tolist(),
        per_metric_float32=metric[per].astype(np.float32).tolist(),
        per_leaf_float64=leaves.tolist(), per_clamped_leaf_float64=clamped.tolist(),
        bank_mean_float64=float(np.mean(weights[per])) if len(per) else 1.0,
        normalization="Selected-min relative sensitivity; no candidate tree or sampling probabilities reconstructed",
        raw_weight_denominator_floor_assumption="Equivalent to source max-normalized PER only if its raw-weight denominator floor is inactive; no hypothetical whole-tree max was measured")


def describe(common, weights, ce, parts, expert, known_bc):
    n = len(ce)
    coefficient = common.coefficient_summary(weights)
    contributions = {name:math.fsum(weights[i]*ce[i] for i in rows)/n for name,rows in parts.items()}
    bellman = math.fsum(contributions.values())
    return dict(coefficient=coefficient, bellman_scalar=bellman, by_origin=contributions,
        coefficient_by_origin={name:common.coefficient_summary([weights[i] for i in rows]) for name,rows in parts.items()},
        expert_bellman_scalar=math.fsum(w*c for w,c,e in zip(weights,ce,expert) if e)/n,
        nonexpert_bellman_scalar=math.fsum(w*c for w,c,e in zip(weights,ce,expert) if not e)/n,
        known_ACTUAL_bc_scalar_held_fixed=known_bc,
        bellman_to_known_actual_bc_ratio=bellman/known_bc if known_bc else None,
        scope="Scalar coefficients/objective arithmetic only; not parameter gradients, effective LR or policy quality")


def analyse_vectors(common, np, vectors, draw, actual_accounting, target_report):
    n = len(vectors["actual_ce"])
    require(n > 0, "Empty conditional row population")
    v = {name:common.values(values,n,name) for name,values in vectors.items()}
    require(set(v) == {"emitted_weights","actual_ce","recomputed_ce","recomputed_entropy",
        "recomputed_kl_signed","recomputed_kl_nonnegative"}, "Four-readout input keyset differs")
    require(all(x >= 0 for x in v["actual_ce"]+v["recomputed_ce"])
        and all(0 < x <= 1 for x in v["emitted_weights"]), "CE/weight domain differs")
    signed = np.asarray(v["recomputed_ce"],dtype=np.float32)-np.asarray(v["recomputed_entropy"],dtype=np.float32)
    require(np.array_equal(signed,np.asarray(v["recomputed_kl_signed"],dtype=np.float32))
        and np.array_equal(np.maximum(signed,0),np.asarray(v["recomputed_kl_nonnegative"],dtype=np.float32)),
        "Conditional signed/clamped KL must use the SAME recomputed CE and entropy")
    parts = common.boundaries(draw,n)
    supplied64 = common.values(draw["supplied_weights_float64"],n,"supplied FP64 weights")
    require([common.f32(x) for x in supplied64] == v["emitted_weights"] == draw["supplied_weights_float32"],
        "Emitted weights do not join original draw FP32 cast")
    raw = common.values(draw["per_raw_weights_float64"],len(parts["per"]),"actual raw PER weights")
    denominator = max(1e-12,max(raw)) if raw else None
    require(all(supplied64[i] == raw[j]/denominator for j,i in enumerate(parts["per"])),
        "Actual emitted PER normalizer differs")
    require(all(supplied64[i] == 1 for name in ("interesting","recent") for i in parts[name]),
        "Actual quota coefficients differ")
    means = float(np.mean(np.asarray(supplied64,dtype=np.float64)[list(parts["per"])])) if raw else 1.0
    require(all(supplied64[i] == means for name in ("hof","ephof") for i in parts[name]),
        "Actual bank coefficients differ from source FP64 mean PER")
    expert = common.values(draw["small_batch_fields"]["is_expert"],n,"is_expert")
    require(all(x in (0,1) for x in expert), "Expert mask differs")
    fresh = {name:fresh_weights(np,v[metric],draw,parts) for name,metric in (
        ("fresh_actual_ce","actual_ce"),("fresh_recomputed_ce","recomputed_ce"),
        ("fresh_recomputed_kl","recomputed_kl_nonnegative"))}
    all_weights = {"emitted":v["emitted_weights"],**{name:entry["weights_float32"] for name,entry in fresh.items()}}
    known_bc = actual_accounting["known_bc_contribution_FP64"]
    require(type(known_bc) in (float,int) and math.isfinite(known_bc), "Actual BC accounting differs")
    summaries = {name:dict(
        using_actual_CE=describe(common,weights,v["actual_ce"],parts,expert,known_bc),
        using_recomputed_CE=describe(common,weights,v["recomputed_ce"],parts,expert,known_bc))
        for name,weights in all_weights.items()}
    per = list(parts["per"])
    indices = common.values(draw["indices"],n,"indices")
    frequency = {}
    for i in per:
        require(indices[i].is_integer() and indices[i] >= 0,"Invalid PER index")
        frequency[indices[i]] = frequency.get(indices[i],0)+1
    per_metric = lambda key:[v[key][i] for i in per]
    return dict(rows=n,alpha=draw["alpha"],beta=draw["beta"],origin_counts={k:len(x) for k,x in parts.items()},
        readouts=summaries, weights_float32=all_weights, fresh_selected_row_details=fresh,
        comparisons=dict(
            fresh_actualCE_vs_fresh_recomputedCE=rank_comparison(per_metric("actual_ce"),per_metric("recomputed_ce")),
            fresh_recomputedCE_vs_fresh_recomputedKL=rank_comparison(per_metric("recomputed_ce"),per_metric("recomputed_kl_nonnegative")),
            stored_leaf_vs_fresh_actualCE=rank_comparison(draw["per_raw_leaves"],per_metric("actual_ce"))),
        conditional_KL=dict(signed=common.stats(v["recomputed_kl_signed"]),
            negative_rows=sum(x<0 for x in v["recomputed_kl_signed"]),
            at_or_below_metric_epsilon_rows=sum(x<=PRIORITY_EPSILON for x in v["recomputed_kl_signed"]),
            entropy=common.stats(v["recomputed_entropy"]),target=target_report,
            scope="Conditional CPU FP32 entropy/CE subtraction only; normalization and negative values require interpretation"),
        duplicates=dict(PER_rows=len(per),distinct_PER_indices=len(frequency),
            extra_repeated_PER_observations=len(per)-len(frequency),
            scope="Rows stay separate; hypothetical row metrics are not a coherent last-write leaf tree"),
        actual_auxiliary_accounting_held_fixed=actual_accounting,
        actual_raw_weight_denominator_floor_active=bool(raw and max(raw)<1e-12),
        limitations=["CE-selected paired sensitivity, not KL-selected replay population or tree migration",
            "No executed per-row target/entropy/KL, gradient norm, LR factor, learning-speed or quality inference",
            "A→B is stored-leaf sensitivity, conflating unknown age/metric/generation and insertion/death/elite boosts; B→C is reconstruction sensitivity; C→D is conditional entropy subtraction",
            "Bank weights are independently recoupled to each readout's FP64 PER mean before FP32 cast",
            "Inherited draw.unknown text is sampler-only provenance, not the outer executed acquisition"])


def load_common():
    source = Path(COMMON_PATH)
    data = source.read_bytes()
    require(hashlib.sha256(data).hexdigest() == COMMON_SHA,"Pinned actual-analysis helper changed")
    spec = importlib.util.spec_from_file_location("_four_readout_common",source)
    module = importlib.util.module_from_spec(spec)
    exec(compile(data,str(source),"exec"),module.__dict__)
    return module


def detached_small(torch, value):
    if isinstance(value,torch.Tensor):
        require(value.device.type == "cpu" and value.numel() <= BATCH and bool(torch.isfinite(value).all()),
            "Unexpected/nonfinite small draw tensor")
        return value.tolist()
    if isinstance(value,dict): return {key:detached_small(torch,item) for key,item in value.items()}
    if isinstance(value,(tuple,list)): return [detached_small(torch,item) for item in value]
    return value


def decode(torch, common, entry):
    """Only small retained reconstruction outputs, never the507MB PRE files."""
    loaded, identities = {}, {}
    for name in ("readout","raw","mask"):
        path,before = common.check_pin(entry[name],MAX_SMALL_PAYLOAD)
        loaded[name] = torch.load(path,map_location="cpu",weights_only=True,mmap=True)
        identities[name] = (path,before)
    readout,raw = loaded["readout"],loaded["raw"]
    outputs = raw["raw_outputs"]
    require(isinstance(outputs,tuple) and len(outputs)==5 and isinstance(outputs[4],tuple) and len(outputs[4])==10,
        "Raw conditional five-output ABI differs")
    projected,logp = outputs[4][:2]
    def vector(value):
        require(isinstance(value,torch.Tensor) and value.device.type=="cpu" and value.dtype==torch.float32
            and tuple(value.shape)==(BATCH,) and bool(torch.isfinite(value).all()),"Small CE/readout vector differs")
        return value.tolist()
    for name in ("projected","logp"):
        value = projected if name=="projected" else logp
        require(isinstance(value,torch.Tensor) and value.device.type=="cpu" and value.is_floating_point()
            and tuple(value.shape)==(BATCH,51) and bool(torch.isfinite(value).all()),"Conditional target/logp differs")
    require(projected.dtype==torch.float32,"Conditional projected target is not FP32")
    require(torch.equal(readout["actual_ce"],raw["expected_actual_capture"]["ce"])
        and torch.equal(readout["recomputed_ce"],outputs[1].detach().float()),"Raw/readout CE join differs")
    entropy = -(projected*projected.clamp_min(1e-12).log()).sum(dim=1)
    require(torch.equal(readout["recomputed_entropy"],entropy),"Conditional CPU entropy does not join raw target")
    actual,recomputed = readout["actual_ce"],readout["recomputed_ce"]
    mask = ~torch.isclose(recomputed,actual,**CE_TOLERANCE,equal_nan=False)
    require(isinstance(loaded["mask"]["ce"],torch.Tensor) and loaded["mask"]["ce"].dtype==torch.bool
        and torch.equal(mask,loaded["mask"]["ce"]),"Original native CE violation mask differs")
    vectors = {name:vector(readout[name]) for name in ("emitted_weights","actual_ce","recomputed_ce",
        "recomputed_entropy","recomputed_kl_signed","recomputed_kl_nonnegative")}
    mass = projected.sum(dim=1)
    target_report = dict(negative_entries=int((projected<0).sum()),
        mass_error=common.stats((mass-1).tolist()),max_abs_mass_error=float((mass-1).abs().max()),
        exact_unit_mass_rows=int((mass==1).sum()),
        ce_reduction_max_abs_residual=float((-(projected*logp.float()).sum(dim=1)-recomputed).abs().max()),
        literal_KL_condition="Only a normalized nonnegative target defines literal KL; no silent renormalization",
        scope="Retained conditional target, never actual executed target")
    draw = detached_small(torch,readout["draw"])
    return loaded,identities,vectors,draw,target_report,mask


def tensor_digest(torch, value):
    """Same single-tensor byte convention as the pinned reconstruction helper."""
    digest = hashlib.sha256(str((str(value.dtype),list(value.shape))).encode())
    digest.update(value.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def publish(common, directory, name, value):
    existing = list(directory.iterdir())
    require(len(existing) <= ATTEMPTS+1 and all(path.is_file() and not path.is_symlink() for path in existing),
        "Unexpected output artifact")
    encoded = (json.dumps(value,indent=2,allow_nan=False)+"\n").encode()
    require(sum(path.stat().st_size for path in existing)+len(encoded) <= MAX_TOTAL_OUTPUT,
        "Analysis output exceeds16MiB")
    common.publish(directory/name,value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--binding",type=Path)
    parser.add_argument("--binding-sha256")
    parser.add_argument("--tool-sha256")
    parser.add_argument("--output",type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print("PLAN_ONLY: conditional four-readout sensitivity; no helper/data/numerical imports or output")
        return 0
    common,output = None,None
    try:
        require(args.binding and args.binding_sha256 and args.tool_sha256 and args.output,"Explicit immutable binding/source/output required")
        require(os.environ.get("CUDA_VISIBLE_DEVICES")=="","CUDA must be hidden before interpreter start")
        require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.tool_sha256,"Analysis source changed")
        common = load_common()
        job = common.json_file(dict(path=str(args.binding),sha256=args.binding_sha256,bytes=args.binding.stat().st_size))
        require(job["schema"]==SCHEMA and len(job["attempts"])==ATTEMPTS,"Exactly eight conditional attempts required")
        require(job["actual_analysis"]["sha256"]==ACTUAL_ANALYSIS_SHA
            and job["actual_binding"]["sha256"]==ACTUAL_BINDING_SHA,"Wrong actual acquisition analysis/binding")
        actual_analysis,actual_binding = common.json_file(job["actual_analysis"]),common.json_file(job["actual_binding"])
        phase = common.json_file(job["reconstruction_phase"])
        require(phase["status"]=="OBSERVATIONS_COMPLETE" and phase["variant"]=="recompute8"
            and phase["qualification_pass"] is False and phase["conditional_recomputed"] is True
            and phase["executed_target_observed"] is False and phase["source_lock_sha256"]==RECONSTRUCTION_LOCK_SHA
            and phase["actual_attempts_in_this_process"]==0 and phase["optimizer_steps"]==0
            and phase["update_guard_counts"]==dict(optimizer_step=0,scaler_step=0,scaler_update=0)
            and len(phase["attempts"])==ATTEMPTS,"Complete conditional-only source-bound reconstruction required")
        launch = common.json_file(job["reconstruction_launch_manifest"])
        require(launch["worker_sha256"]==WORKER_SHA and launch["source_lock_sha256"]==RECONSTRUCTION_LOCK_SHA,
            "Reconstruction executable source pins differ")
        require(actual_analysis["status"]=="OBSERVATIONAL_DESCRIPTIONS_COMPLETE"
            and actual_analysis["qualification_pass"] is False and len(actual_analysis["attempts"])==ATTEMPTS
            and len(actual_binding["attempts"])==ATTEMPTS,"Actual-only analysis population differs")
        output = args.output
        require(output.is_absolute() and output==output.resolve(strict=False) and not output.exists(),"New canonical output required")
        output.mkdir(mode=0o700)
        import numpy as np
        import torch
        torch.set_num_threads(2);torch.set_num_interop_threads(2)
        require(not torch.cuda.is_initialized() and torch.cuda.device_count()==0,"Unexpected CUDA context")
        summaries = []
        for index,entry in enumerate(job["attempts"],1):
            result = common.json_file(entry["result"])
            require(result==phase["attempts"][index-1] and result["index"]==entry["index"]==index
                and result["diagnostics"] is (index==7) and result["qualification_pass"] is False
                and result["source_payload"]=={**actual_binding["attempts"][index-1]["payload"],
                    "identity":result["source_payload"]["identity"]},"Original ordered PRE/route/result join differs")
            for key,field in (("readout","four_readout_inputs"),("raw","retained_conditional_payload"),("mask","ce_mismatch_mask")):
                recorded = result[field]["payload"] if key=="readout" else result[field]
                require(entry[key]=={name:recorded[name] for name in ("path","sha256","bytes")},"Retained conditional pin differs")
            loaded,identities,vectors,draw,target_report,mask = decode(torch,common,entry)
            require(draw["capture_id"]==launch["retained_inputs"]["capture_id"],"Conditional draw/capture session differs")
            require(loaded["raw"]["source_capture_payload"]==result["source_payload"]
                and loaded["raw"]["source_capture_receipt"]==result["source_receipt"],"Raw original-source binding differs")
            require(tensor_digest(torch,loaded["readout"]["actual_ce"])==result["ce_comparison"]["expected_sha256"]
                and tensor_digest(torch,loaded["readout"]["recomputed_ce"])==result["ce_comparison"]["actual_sha256"],
                "Exact actual/recomputed CE tensor fingerprints differ")
            require(bool(mask.any()) is (not result["comparison_pass"])
                and int(mask.sum())==result["ce_comparison"]["violations"]
                and result["ce_comparison"]["tolerance"]==CE_TOLERANCE,"Original per-attempt CE decision differs")
            original = actual_analysis["attempts"][index-1]
            require(original["index"]==index and original["optimizer_outcome"]==result["original_optimizer_outcome"],
                "Actual outcome/analysis row differs")
            require(common.stats(vectors["actual_ce"])==original["groups"]["all"]["ce"]
                and common.stats(vectors["emitted_weights"])==original["groups"]["all"]["weights"],
                "Actual analysis CE/emitted-weight descriptions differ")
            report = analyse_vectors(common,np,vectors,draw,original["scalar_accounting"],target_report)
            report.update(index=index,qualification_pass=False,conditional_recomputed=True,
                original_optimizer_outcome=original["optimizer_outcome"],original_CE_comparison=result["ce_comparison"],
                source_bindings=entry,reconstruction_interpretation_requires_review=result["interpretation_requires_review"])
            publish(common,output,"attempt-%02d.json"%index,report)
            summaries.append(dict(index=index,original_CE_comparison=result["ce_comparison"],
                readouts=report["readouts"],comparisons=report["comparisons"],conditional_KL=report["conditional_KL"]))
            del loaded,vectors,draw,mask,report
            require(all(common.identity(path.lstat())==before for path,before in identities.values()),"Small retained input changed")
        require(not torch.cuda.is_initialized(),"CUDA became initialized")
        publish(common,output,"analysis.json",dict(schema=SCHEMA,status="CONDITIONAL_SENSITIVITY_DESCRIPTIONS_COMPLETE",
            qualification_pass=False,attempts=summaries,actual_executed_target_observed=False,
            candidate_KL_population_observed=False,measured_parameter_gradients=False,
            original_CE_tolerance=CE_TOLERANCE,root_binding=dict(path=str(args.binding),sha256=args.binding_sha256),
            scope="All eight CE-selected paired sensitivities; no treatment, ranking identity or learning qualification"))
        descriptor = os.open(output,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        return 0
    except BaseException as error:
        if common is not None and output is not None and output.is_dir():
            try:publish(common,output,"analysis-error.json",dict(status="ANALYSIS_NOT_READY",qualification_pass=False,error=repr(error)))
            except BaseException:pass
        raise


if __name__=="__main__":
    raise SystemExit(main())
