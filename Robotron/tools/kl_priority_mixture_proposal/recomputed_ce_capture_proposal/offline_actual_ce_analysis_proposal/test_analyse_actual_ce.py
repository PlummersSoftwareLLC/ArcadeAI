"""Authored/unexecuted stdlib math and error contracts; no payload/Torch imports.

Eight-row synthetic vectors validate descriptions only, not live4096/CUDA data.
"""
from contextlib import redirect_stdout
import copy
import io
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from . import analyse_actual_ce as tool


def fixture():
    raw = [2.,1.,.5]
    mean = (1.+.5+.25)/3
    original = [1.,.5,.25,1.,1.,mean,mean,mean]
    emitted = [tool.f32(x) for x in original]
    draw = dict(origin_boundaries=[('per',0,3),('interesting',3,4),('recent',4,5),('hof',5,6),('ephof',6,8)],
        supplied_weights_float64=original, supplied_weights_float32=emitted,
        indices=[0,0,1,2,2,16,22,22], per_raw_weights_float64=raw,
        per_raw_leaves=[1.,4.,16.], per_clamped_leaves=[1.,4.,16.],
        tree_total=64.,size=16,capacity=16,beta=.5,alpha=.6,selected_per_raw_max_weight=2.,
        small_batch_fields=dict(actions=list(range(8)),is_expert=[0,1,0,0,0,1,1,1],
            dones=[0,0,1,0,1,0,0,1],horizons=[1,2,3,1,2,3,1,2],
            actor_kind=[0,1,2,0,1,2,0,1],rewards=[-1.,0.,1.,-1.,0.,1.,0.,1.]),
        banks={name:dict(episodes=2,transitions=3,revision=7,load_epoch=1,selected_slots=[0]) for name in ('hof','ephof')},
        unknown=dict(tree_metric_identity='not independently identified',slot_insert_generation='not stored'))
    ce = [float(i) for i in range(1,9)]
    return ce,emitted,draw


def analyse(ce,weights,draw):
    return tool.analyse_rows(ce,weights,draw,weighted_loss=5.,bc_loss=2.,schedule=[.1,.2,.3])


def row(label):
    identity = dict(process_id=123,instance_monotonic_ns=456,epoch=1)
    before = dict(identity,total=dict.fromkeys(tool.TOTALS,0))
    totals = dict(attempts_started=1,outcomes_recorded=1,applied=int(label=='applied_admission'),
                  amp_skipped=int(label=='amp_skipped'),unavailable=0)
    return dict(exposure_before=before,exposure_at_exit=dict(identity,total=totals,available=True),
        actual_exposure_delta=totals,outcome_available=True,optimizer_outcome=label,
        optimizer_observation=dict(ticket_finished=True,ticket_owner_matches=True,ticket_epoch=1,
            mode='single_cuda_found_inf',found_inf=float(label=='amp_skipped')))


class ActualCEAnalysisTests(unittest.TestCase):
    def test_default_is_literal_without_file_access_or_numerical_import(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('file read')), \
             patch.object(Path,'read_text',side_effect=AssertionError('file read')), \
             patch.object(tool,'json_file',side_effect=AssertionError('input')), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(tool.main([]),0)
        self.assertIn('PLAN_ONLY',output.getvalue())

    def test_equal_and_concentrated_coefficient_effective_count(self):
        self.assertEqual(tool.coefficient_summary([1.]*8)['effective_count'],8.)
        self.assertEqual(tool.coefficient_summary([1.,0.,0.])['effective_count'],1.)
        first = tool.coefficient_summary([1.,.5,.25])
        scaled = tool.coefficient_summary([.1,.05,.025])
        self.assertTrue(math.isclose(first['effective_count'],scaled['effective_count']))
        self.assertNotEqual(first['sum'],scaled['sum'])
        self.assertIn('not population',first['scope'])

    def test_actual_selected_normalizer_and_mean_bank_coupling(self):
        ce,weights,draw = fixture(); result = analyse(ce,weights,draw)
        self.assertEqual(result['normalizer']['raw_max'],2.)
        self.assertFalse(result['normalizer']['denominator_floor_active'])
        self.assertEqual(result['normalizer']['raw_formula_max_abs_error'],0.)
        self.assertEqual(result['groups']['origin:interesting']['weights']['mean'],1.)
        self.assertEqual(result['groups']['origin:hof']['weights']['mean'],tool.f32(7/12))
        self.assertAlmostEqual(result['normalizer']['bank_weight_minus_FP64_fsum_PER_mean']['hof'],0.)

    def test_denominator_floor_is_used_without_selected_min_simplification(self):
        # Deliberately synthetic arithmetic-domain branch, not a claim these
        # raw weights come from the fixture's unchanged leaves/tree total.
        ce,weights,draw = fixture()
        draw['per_raw_weights_float64']=[2e-14,1e-14,.5e-14]
        draw['selected_per_raw_max_weight']=2e-14
        normalized = [x/1e-12 for x in draw['per_raw_weights_float64']]
        mean = sum(normalized)/3
        draw['supplied_weights_float64']=normalized+[1.,1.,mean,mean,mean]
        draw['supplied_weights_float32']=[tool.f32(x) for x in draw['supplied_weights_float64']]
        result = analyse(ce,draw['supplied_weights_float32'],draw)
        self.assertTrue(result['normalizer']['denominator_floor_active'])
        self.assertEqual(result['normalizer']['raw_max'],2e-14)
        self.assertEqual(result['normalizer']['denominator'],1e-12)
        self.assertEqual(result['groups']['origin:per']['weights']['maximum'],tool.f32(.02))

    def test_origin_and_strata_partitions_preserve_repeated_rows(self):
        ce,weights,draw=fixture(); result=analyse(ce,weights,draw)
        self.assertEqual(sum(result['groups']['origin:'+name]['rows'] for name in tool.ORIGINS),8)
        self.assertEqual(sum(result['groups']['expert:'+str(k)]['rows'] for k in (0,1)),8)
        self.assertEqual(result['duplicates']['ring_duplicate_rows'],4)
        self.assertEqual(result['duplicates']['ring_distinct_indices'],3)
        self.assertEqual(result['groups']['all']['ce']['sum'],36.)
        self.assertAlmostEqual(sum(result['groups']['origin:'+name]['bellman_objective_contribution'] for name in tool.ORIGINS),
                               result['scalar_accounting']['bellman_objective_FP64_reduction'])

    def test_objective_and_coefficient_mass_are_distinct_from_gradient(self):
        ce,weights,draw=fixture(); result=analyse(ce,weights,draw)
        accounting=result['scalar_accounting']
        self.assertEqual(accounting['known_bc_contribution_FP64'],.1)
        self.assertAlmostEqual(accounting['combined_other_auxiliary_plus_reduction_residual'],
            5.-sum(w*c for w,c in zip(weights,ce))/8-.1)
        self.assertFalse(result['measured_parameter_gradients'])
        self.assertFalse(result['executed_per_row_target_entropy_or_KL_observed'])
        self.assertIn('unobserved per-row',accounting['scope'])

    def test_draw_boundaries_and_actual_weight_cast_mismatch_reject(self):
        for mutation in ('gap','order','cast','quota','bank'):
            with self.subTest(mutation=mutation):
                ce,weights,draw=fixture()
                if mutation=='gap':draw['origin_boundaries'][1]=('interesting',4,4)
                if mutation=='order':draw['origin_boundaries'][1]=('recent',3,4)
                if mutation=='cast':weights[0]=.9
                if mutation=='quota':
                    draw['supplied_weights_float64'][3]=.5
                    draw['supplied_weights_float32'][3]=weights[3]=.5
                if mutation=='bank':
                    draw['supplied_weights_float64'][7]=.25
                    draw['supplied_weights_float32'][7]=weights[7]=.25
                with self.assertRaises(ValueError):analyse(ce,weights,draw)

    def test_nonfinite_negative_and_zero_data_fail_without_replacing_rows(self):
        for bad in (float('nan'),float('inf'),-1.):
            ce,weights,draw=fixture(); ce[0]=bad
            with self.assertRaises(ValueError):analyse(ce,weights,draw)
        ce,weights,draw=fixture();weights[0]=0.
        with self.assertRaises(ValueError):analyse(ce,weights,draw)

    def test_actual_skip_and_admission_remain_separate_and_ticket_bound(self):
        for label in ('amp_skipped','applied_admission'):
            self.assertEqual(tool.outcome(row(label)),label)
        for change in ('found_inf','ticket','epoch','unavailable'):
            with self.subTest(change=change):
                record=row('amp_skipped')
                if change=='found_inf':record['optimizer_observation']['found_inf']=0.
                if change=='ticket':record['optimizer_observation']['ticket_finished']=False
                if change=='epoch':record['exposure_at_exit']['epoch']=2
                if change=='unavailable':record['exposure_at_exit']['total']['unavailable']=1
                with self.assertRaises(ValueError):tool.outcome(record)

    def test_no_mutation_no_target_kl_estimate_and_original_tolerance_retained(self):
        ce,weights,draw=fixture(); before=copy.deepcopy((ce,weights,draw))
        result=analyse(ce,weights,draw)
        self.assertEqual((ce,weights,draw),before)
        self.assertEqual(result['unknown'],draw['unknown'])
        self.assertFalse(result['executed_per_row_target_entropy_or_KL_observed'])
        self.assertEqual(tool.ORIGINAL_CONDITIONAL_CE_TOLERANCE,dict(rtol=2e-4,atol=2e-5))


if __name__=='__main__':
    unittest.main()
