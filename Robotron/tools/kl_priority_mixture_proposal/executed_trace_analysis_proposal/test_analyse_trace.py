"""Authored, UNEXECUTED synthetic CPU fixtures; no training/Torch/CUDA imports.

Future explicit unittest execution imports NumPy and writes only TemporaryDirectory.
These tests are not evidence of successful acquisition or numerical validation.
"""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from . import analyse_trace as tool


def fixture(np, counts=(901, 737, 1434, 410, 614)):
    n, atoms = tool.BATCH, tool.ATOMS
    target = np.zeros((n, atoms), dtype=np.float32)
    target[:, 0] = 1
    target[::2, 0] = target[::2, 1] = .5
    q0 = np.linspace(.05, .95, n, dtype=np.float32)
    probabilities = np.repeat(((1-q0)/50)[:, None], atoms, axis=1)
    probabilities[:, 0] = q0
    logp = np.log(probabilities).astype(np.float32)
    ce = -(target * logp).sum(axis=1, dtype=np.float32)
    boundaries, cursor = [], 0
    for name, count in zip(tool.ORIGINS, counts):
        boundaries.append([name, cursor, cursor+count]); cursor += count
    assert cursor == n
    part = {name:slice(a,b) for name,a,b in boundaries}
    ring_end = sum(counts[:3])
    indices = np.arange(n, dtype=np.int64)
    if ring_end > 1:
        indices[1] = indices[0]  # retain two different CE values at one slot
    indices[ring_end:] += 8192
    raw = np.linspace(.2, 4, counts[0], dtype=np.float64)
    clamped = np.maximum(1e-10, raw)
    raw_weights = (8192 * (clamped / 6000)) ** (-.7)
    per = raw_weights/max(1e-12, float(raw_weights.max())) if len(raw) else raw_weights
    emitted64 = tool.mixed_weights(per, part, np)
    expert = np.zeros(n, dtype=np.uint8); expert[::3] = 1
    fields = dict(actions=np.arange(n, dtype=np.int64)%81,
                  rewards=np.zeros(n, dtype=np.float32), dones=np.zeros(n, dtype=np.uint8),
                  horizons=np.full(n, 3, dtype=np.uint8), is_expert=expert,
                  actor_kind=np.arange(n, dtype=np.uint8)%3)
    fields["dones"][::7] = 1
    schedule = [.4, .2, .1]
    raw_bc = np.full(n, 2, dtype=np.float32)
    raw_q, raw_margin = np.full(n, .2, dtype=np.float32), np.full(n, .4, dtype=np.float32)
    count = expert.sum()
    bc_loss = np.asarray((raw_bc*expert).sum(dtype=np.float32)/max(1,count), dtype=np.float32)
    bc = np.asarray(max(.01, schedule[0]*float(count)/n)*bc_loss, dtype=np.float32)
    qp = np.asarray(schedule[1]*(raw_q*expert).sum(dtype=np.float32)/n, dtype=np.float32)
    margin = np.asarray(schedule[2]*(raw_margin*expert).sum(dtype=np.float32)/n, dtype=np.float32)
    loss = np.asarray((emitted64.astype(np.float32)*ce).mean(dtype=np.float32), dtype=np.float32)
    loss = np.asarray(np.asarray(np.asarray(loss+bc, dtype=np.float32)+qp, dtype=np.float32)+margin, dtype=np.float32)
    arrays = dict(ce=ce, projected_target=target, taken_action_log_probabilities=logp,
        target_action_probabilities=probabilities.copy(), unclipped_target_support=np.zeros((n,atoms), dtype=np.float32),
        per_row_bc=raw_bc, per_row_q_policy=raw_q, per_row_margin=raw_margin,
        bc_loss=bc_loss, bc_contribution=bc, q_policy_contribution=qp, margin_contribution=margin,
        weighted_loss=loss)
    draw = dict(schema="robotron-replay-draw-observation-v1", observer_error=None,
        capture_id="synthetic-only", beta=.7, alpha=.7, capacity=8192, size=8192,
        tree_total=6000., origin_boundaries=boundaries, indices=indices,
        per_raw_leaves=raw, per_clamped_leaves=clamped,
        per_raw_weights_float64=raw_weights,
        selected_per_raw_max_weight=float(raw_weights.max()) if len(raw) else None,
        selected_per_min_clamped_leaf=float(clamped.min()) if len(raw) else None,
        supplied_weights_float64=emitted64, supplied_weights_float32=emitted64.astype(np.float32),
        small_batch_fields=fields, lock_observation_started_monotonic_ns=1,
        lock_observation_finished_monotonic_ns=2,
        unknown={"priority_metric":"not proven by stored leaves", "slot_insert_generation":"unknown"})
    cfg = dict(batch_size=n, num_atoms=atoms, v_min=-10., v_max=50., expert_bc_effective_floor=.01)
    return arrays, draw, cfg, schedule


def outcome_row(index=1, skipped=False):
    totals = dict(attempts_started=index-1, outcomes_recorded=index-1,
                  applied=index-1, amp_skipped=0, unavailable=0)
    before = dict(process_id=42, instance_monotonic_ns=123, epoch=0,
                  total=totals, available=index>1)
    after = copy.deepcopy(before)
    after["available"] = True
    after["total"]["attempts_started"] += 1
    after["total"]["outcomes_recorded"] += 1
    after["total"]["amp_skipped" if skipped else "applied"] += 1
    delta = {k:after["total"][k]-before["total"][k] for k in tool.TOTALS}
    return dict(index=index, status="returned_loss", exception=None, result=1.,
        numerical_capture_complete=True, observer_errors=[],
        exposure_before=before, exposure_at_exit=after, actual_exposure_delta=delta,
        optimizer_observation=dict(ticket_finished=True, ticket_owner_matches=True,
                                   ticket_epoch=0, mode="single_cuda_found_inf", found_inf=1. if skipped else 0.),
        optimizer_outcome="amp_skipped" if skipped else "applied_admission", outcome_available=True,
        consumed_monotonic_ns=100+index, draw_to_consume_ns=98+index,
        prefetch=None, backend="synthetic_cpu_fixture_no_optimizer",
        before={"training_steps":index-1}, after={"training_steps":index})


class SyntheticMechanicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np

    def test_three_distinct_vectors_exact_actual_and_bank_recoupling(self):
        np = self.np
        arrays, draw, cfg, schedule = fixture(np)
        result, vectors = tool.analyse_arrays(arrays, draw, cfg, schedule, np)
        self.assertTrue(np.array_equal(vectors["actual_emitted"], draw["supplied_weights_float32"]))
        self.assertFalse(np.array_equal(vectors["fresh_ce"], vectors["fresh_kl"]))
        self.assertFalse(np.array_equal(vectors["actual_emitted"], vectors["fresh_ce"]))
        for name in tool.VECTORS:
            w = vectors[name]
            self.assertTrue(np.all(w[901:3072] == 1))
            # Bank mean is computed in float64 BEFORE fp32 row casting.
            leaves = vectors["fresh_ce_leaf" if name=="fresh_ce" else "fresh_kl_leaf"][:901] if name!="actual_emitted" else None
            per64 = tool.selected_min_weights(leaves,.7,np) if leaves is not None else draw["per_raw_weights_float64"]/draw["selected_per_raw_max_weight"]
            self.assertTrue(np.all(w[3072:] == np.float32(per64.mean())))
        self.assertEqual(result["origins"], dict(zip(tool.ORIGINS,(901,737,1434,410,614))))

    def test_selected_min_not_global_tree_min_and_common_scaling_cancel(self):
        np = self.np
        leaves = np.array([2.,4.,8.])
        expected = np.array([1.,.5,.25]) ** .7
        self.assertTrue(np.allclose(tool.selected_min_weights(leaves,.7,np), expected))
        self.assertTrue(np.allclose(tool.selected_min_weights(leaves*17,.7,np), expected))
        self.assertEqual(tool.selected_min_weights(leaves,0.,np).tolist(), [1.,1.,1.])

    def test_priority_epsilon_cast_and_abs_match_update_not_priority_space_floor(self):
        np = self.np
        metric = np.array([0.,-2.,1e-8],dtype=np.float32)
        expected = (np.abs(metric.astype(np.float64))+1e-6)**.7
        self.assertTrue(np.array_equal(tool.priority_leaf(metric,.7,np),expected))
        self.assertNotEqual(float(expected[0]),1e-6)

    def test_entropy_is_from_actual_projection_not_preprojection_or_ce_recompute(self):
        np = self.np
        arrays, draw, cfg, schedule = fixture(np)
        _, vectors = tool.analyse_arrays(arrays, draw, cfg, schedule, np)
        self.assertAlmostEqual(float(vectors["target_entropy_fp32"][0]),float(np.log(2)),places=6)
        self.assertEqual(float(vectors["target_entropy_fp32"][1]),0.)
        self.assertTrue(np.array_equal(vectors["fresh_ce_leaf"],tool.priority_leaf(arrays["ce"],.7,np)))

    def test_roundoff_negative_kl_is_retained_and_clamped_not_silently_relabelled(self):
        np = self.np
        arrays, draw, cfg, schedule = fixture(np)
        arrays["taken_action_log_probabilities"][:] = np.log(np.maximum(arrays["projected_target"],1e-12))
        exact = -(arrays["projected_target"]*arrays["taken_action_log_probabilities"]).sum(axis=1,dtype=np.float32)
        arrays["ce"] = np.nextafter(exact,np.full_like(exact,-np.inf))
        aux = sum(float(arrays[k]) for k in ("bc_contribution","q_policy_contribution","margin_contribution"))
        arrays["weighted_loss"] = np.asarray((draw["supplied_weights_float32"]*arrays["ce"]).mean()+aux,dtype=np.float32)
        report, vectors = tool.analyse_arrays(arrays,draw,cfg,schedule,np)
        self.assertGreater(report["kl_roundoff"]["raw_negative"],0)
        self.assertTrue(np.all(vectors["kl_clamped_fp32"]>=0))
        self.assertEqual(report["kl_roundoff"]["material_negative"],0)
        self.assertFalse(report["interpretation_not_ready"])

    def test_duplicate_order_retained_and_conflicting_ce_not_averaged(self):
        np = self.np
        arrays, draw, cfg, schedule = fixture(np)
        report, vectors = tool.analyse_arrays(arrays,draw,cfg,schedule,np)
        self.assertEqual(vectors["indices"][0],vectors["indices"][1])
        self.assertNotEqual(vectors["fresh_ce_leaf"][0],vectors["fresh_ce_leaf"][1])
        self.assertEqual(report["duplicates"]["slots_with_distinct_ce"],1)

    def test_material_negative_kl_explicitly_blocks_interpretation(self):
        np=self.np
        arrays,draw,cfg,schedule=fixture(np)
        # Deliberately inconsistent log-probability semantics, but exact finite
        # CE identity/mass: clamping alone must never label raw KL ready.
        arrays["projected_target"][:]=0; arrays["projected_target"][:,0]=1
        arrays["taken_action_log_probabilities"][:]=0
        arrays["taken_action_log_probabilities"][:,0]=.1
        arrays["ce"]=np.full(tool.BATCH,-.1,dtype=np.float32)
        aux=sum(float(arrays[k]) for k in ("bc_contribution","q_policy_contribution","margin_contribution"))
        arrays["weighted_loss"]=np.asarray((draw["supplied_weights_float32"]*arrays["ce"]).mean()+aux,dtype=np.float32)
        report,_=tool.analyse_arrays(arrays,draw,cfg,schedule,np)
        self.assertTrue(report["interpretation_not_ready"])
        self.assertEqual(report["kl_roundoff"]["material_negative"],4096)

    def test_empty_banks_and_shortfall_origins_use_observed_partition(self):
        np = self.np
        arrays, draw, cfg, schedule = fixture(np,(1000,0,3096,0,0))
        report, vectors = tool.analyse_arrays(arrays,draw,cfg,schedule,np)
        self.assertEqual(report["groups"]["origin:hof"]["count"],0)
        self.assertTrue(np.all(vectors["fresh_kl"][1000:]==1))

    def test_weighted_ce_origin_contributions_sum_to_full_objective_aux_unweighted(self):
        np = self.np
        arrays, draw, cfg, schedule = fixture(np)
        report, _ = tool.analyse_arrays(arrays,draw,cfg,schedule,np)
        groups = report["groups"]
        for name in tool.VECTORS:
            self.assertAlmostEqual(sum(groups["origin:"+origin]["vectors"][name]["weighted_ce_contribution"] for origin in tool.ORIGINS),
                                   groups["all"]["vectors"][name]["weighted_ce_contribution"],places=10)
        self.assertAlmostEqual(sum(groups["origin:"+origin]["auxiliary_contributions"]["bc"] for origin in tool.ORIGINS),
                               float(arrays["bc_contribution"]),places=6)
        self.assertGreater(report["captured_auxiliary_total"],0)

    def test_malformed_mass_and_emitted_bank_weight_rejected(self):
        np = self.np
        arrays, draw, cfg, schedule = fixture(np)
        arrays["projected_target"][0]*=2
        with self.assertRaisesRegex(ValueError,"target mass"):
            tool.analyse_arrays(arrays,draw,cfg,schedule,np)
        arrays, draw, cfg, schedule = fixture(np)
        draw["supplied_weights_float64"][-1]=1.
        with self.assertRaisesRegex(ValueError,"mixed emitted"):
            tool.analyse_arrays(arrays,draw,cfg,schedule,np)

    def test_denominator_floor_exact_actual_path_is_not_replaced_by_selected_min(self):
        np = self.np
        arrays, draw, cfg, schedule = fixture(np)
        draw["tree_total"] = 1e-30
        raw = (8192*(draw["per_clamped_leaves"]/draw["tree_total"]))**(-.7)
        draw["per_raw_weights_float64"], draw["selected_per_raw_max_weight"] = raw,float(raw.max())
        part={name:slice(a,b) for name,a,b in draw["origin_boundaries"]}
        w=tool.mixed_weights(raw/1e-12,part,np)
        draw["supplied_weights_float64"],draw["supplied_weights_float32"]=w,w.astype(np.float32)
        aux=sum(float(arrays[k]) for k in ("bc_contribution","q_policy_contribution","margin_contribution"))
        arrays["weighted_loss"]=np.asarray((w.astype(np.float32)*arrays["ce"]).mean()+aux,dtype=np.float32)
        report,_=tool.analyse_arrays(arrays,draw,cfg,schedule,np)
        self.assertTrue(report["normalization"]["actual_denominator_floor_active"])


class GuardAndProtocolTests(unittest.TestCase):
    def test_eight_complete_synthetic_persisted_rows_join_original_summaries(self):
        import numpy as np
        arrays, draw, cfg, schedule=fixture(np)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); trace=root/"trace"; trace.mkdir(); output=root/"analysis"; output.mkdir()
            context=dict(schema="robotron-executed-ce-trace-v1",attempts=8,config=cfg,
                         runtime={"scope":"synthetic fixture only; no optimizer run"})
            (trace/"context.json").write_text(json.dumps(context))
            summaries=[]
            for i in range(1,9):
                captured={key:value.copy() for key,value in arrays.items()}
                def extract(value,prefix):
                    if isinstance(value,np.ndarray):
                        captured[prefix]=value
                        return dict(array=prefix,dtype=str(value.dtype),shape=list(value.shape))
                    if isinstance(value,dict): return {key:extract(item,prefix+"__"+key) for key,item in value.items()}
                    if isinstance(value,list): return [extract(item,prefix+"__"+str(j)) for j,item in enumerate(value)]
                    return value
                row=outcome_row(i); row["result"]=float(arrays["weighted_loss"])
                row["schedule"]=schedule
                summary=copy.deepcopy(row)
                summary["draw"]=extract(draw,"draw")
                summary["array_finite"]={key:True for key in captured}
                np.savez(trace/("attempt-%02d.npz"%i),**captured)
                (trace/("attempt-%02d.json"%i)).write_text(json.dumps(summary))
                summaries.append(row)
            status=dict(schema=context["schema"],status="EIGHT_NUMERICAL_CAPTURES_COMPLETE",
                        attempts_consumed=8,numerical_captures_complete=True,observer_errors=[],
                        observer_reporting_failed=False,rows=summaries)
            (trace/"status.json").write_text(json.dumps(status))
            report=tool.analyse(trace,{"provenance":{"population":"private_fixed_batch_reuse"}},output,np)
            self.assertEqual(report["optimizer_outcomes"],dict(applied_admission=8,amp_skipped=0))
            self.assertEqual(report["aggregate"]["all"]["rows"],32768)
            self.assertEqual(len(list(output.glob("weights-*.npz"))),8)
            self.assertFalse((output/"completion.json").exists()) # only execute() can seal after source/input recheck

    def test_default_literal_plan_performs_no_reads_or_numpy_import(self):
        original_import=__import__
        def guarded_import(name,*args,**kwargs):
            if name.startswith("numpy"):
                raise AssertionError("Numerical import on default path")
            return original_import(name,*args,**kwargs)
        with mock.patch("builtins.__import__",side_effect=guarded_import), \
             mock.patch.object(Path,"read_bytes",side_effect=AssertionError("read")), \
             mock.patch.object(Path,"mkdir",side_effect=AssertionError("mkdir")), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(tool.main([]),0)
        self.assertEqual(output.getvalue(),tool.PLAN+"\n")

    def test_exact_eight_status_rejects_seven_ninth_or_failure_no_trimming(self):
        context=dict(schema="robotron-executed-ce-trace-v1",attempts=8,config=dict(batch_size=4096,num_atoms=51))
        status=dict(schema=context["schema"],attempts_consumed=8,status="EIGHT_NUMERICAL_CAPTURES_COMPLETE",
                    numerical_captures_complete=True,observer_errors=[],observer_reporting_failed=False,
                    rows=[dict(index=i) for i in range(1,9)])
        tool.check_headers(context,status)
        for count in (7,9):
            damaged=copy.deepcopy(status); damaged["attempts_consumed"]=count
            with self.assertRaises(ValueError): tool.check_headers(context,damaged)
        damaged=copy.deepcopy(status); damaged["observer_errors"]=["metadata failed"]
        with self.assertRaises(ValueError): tool.check_headers(context,damaged)

    def test_actual_applied_and_skip_outcomes_kept_unavailable_or_reused_epoch_rejected(self):
        self.assertEqual(tool.check_outcome(outcome_row()),"applied_admission")
        self.assertEqual(tool.check_outcome(outcome_row(skipped=True)),"amp_skipped")
        row=outcome_row(); row["exposure_at_exit"]["epoch"]+=1
        with self.assertRaisesRegex(ValueError,"identity"): tool.check_outcome(row)
        row=outcome_row(); row["optimizer_observation"]["ticket_owner_matches"]=False
        with self.assertRaises(ValueError): tool.check_outcome(row)
        row=outcome_row(); row["optimizer_observation"]["ticket_epoch"]=1
        with self.assertRaisesRegex(ValueError,"ticket epoch"): tool.check_outcome(row)
        row=outcome_row(skipped=True); row["optimizer_observation"]["found_inf"]=0.
        with self.assertRaisesRegex(ValueError,"contradiction"): tool.check_outcome(row)

    def test_failure_preserved_in_new_output_no_overwrite_or_numpy_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/"new-output"
            args=type("Args",(),dict(output=str(output),trace="missing",binding="missing",binding_sha256="x",tool_sha256="bad"))()
            self.assertEqual(tool.execute(args),1)
            failure=json.loads((output/"failure.json").read_text())
            self.assertEqual(failure["status"],"INVALID_OR_INCOMPLETE_ANALYSIS")
            self.assertFalse((output/"completion.json").exists())
            with self.assertRaisesRegex(ValueError,"new absolute output"):
                tool.execute(args)

    def test_hash_bound_ninth_file_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); trace=root/"trace"; trace.mkdir()
            for name in tool.expected_files(): (trace/name).write_bytes(b"{}")
            review=root/"review.json"; review.write_bytes(b"{}")
            bound=dict(schema="robotron-ce-trace-analysis-input-binding-v1",producer_source_sha256=tool.PRODUCER,
                producer_manifest_sha256=tool.PRODUCER_MANIFEST,
                provenance=dict(population="private_fixed_batch_reuse",priority_recipe="ce",checkpoint_sha256="a"*64,
                    executed_prototype_source_sha256={key:value for key,value in tool.PRODUCER.items() if key!="agent.py"},
                    agent_overlay_imported=False,agent_lifecycle_exercised=False,
                    acquisition_review_path=str(review),acquisition_review_sha256=tool.digest(b"{}")),
                trace_sha256={name:tool.digest(b"{}") for name in tool.expected_files()})
            binding=root/"binding.json"; binding.write_text(json.dumps(bound))
            binding_sha=tool.digest(binding.read_bytes()); tool_sha=tool.digest(Path(tool.__file__).read_bytes())
            tool.verify_binding(trace,binding,binding_sha,tool_sha)
            (trace/"attempt-09.json").write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError,"exactly18"): tool.verify_binding(trace,binding,binding_sha,tool_sha)
            (trace/"attempt-09.json").unlink(); (trace/"attempt-01.npz").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError,"SHA mismatch"): tool.verify_binding(trace,binding,binding_sha,tool_sha)


if __name__ == "__main__":
    unittest.main()
