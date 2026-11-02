"""Authored CPU NumPy/pure-arithmetic tests; no author execution or tensor reads."""
from contextlib import redirect_stdout
import builtins
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from . import analyse_four_readouts as tool


class FourReadoutArithmetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        cls.common = tool.load_common()

    def fixture(self):
        weights = [.25,1.,1.,1.,.625,.625]
        draw = dict(alpha=1.,beta=1.,size=10,capacity=100,tree_total=20.,
            origin_boundaries=[("per",0,2),("interesting",2,3),("recent",3,4),("hof",4,5),("ephof",5,6)],
            indices=[7,7,8,9,100,200],per_raw_leaves=[4.,1.],per_clamped_leaves=[4.,1.],
            per_raw_weights_float64=[.5,2.],supplied_weights_float64=weights.copy(),
            supplied_weights_float32=weights.copy(),small_batch_fields=dict(is_expert=[1,0,0,1,1,0]))
        vectors = dict(emitted_weights=weights,actual_ce=[1.,3.,2.,2.,2.,2.],
            recomputed_ce=[3.,1.,2.,2.,2.,2.],recomputed_entropy=[2.75,.75,1.75,1.75,1.75,1.75],
            recomputed_kl_signed=[.25]*6,recomputed_kl_nonnegative=[.25]*6)
        accounting = dict(known_bc_contribution_FP64=.01,
            combined_other_auxiliary_plus_reduction_residual=.03)
        target = dict(negative_entries=0,max_abs_mass_error=0.,exact_unit_mass_rows=6)
        return vectors,draw,accounting,target

    def report(self,*values):
        return tool.analyse_vectors(self.common,self.np,*values)

    def test_four_vectors_separate_age_reconstruction_and_conditional_entropy(self):
        vectors,draw,accounting,target=self.fixture()
        result=self.report(vectors,draw,accounting,target)
        weights=result["weights_float32"]
        self.assertEqual(weights["emitted"][:2],[.25,1.])
        self.assertEqual(weights["fresh_actual_ce"][0],1.)
        self.assertLess(weights["fresh_actual_ce"][1],.34)
        self.assertLess(weights["fresh_recomputed_ce"][0],.34)
        self.assertEqual(weights["fresh_recomputed_ce"][1],1.)
        self.assertEqual(weights["fresh_recomputed_kl"],[1.]*6)
        self.assertAlmostEqual(result["comparisons"]["fresh_actualCE_vs_fresh_recomputedCE"]["spearman"],-1.)
        self.assertIsNone(result["comparisons"]["fresh_recomputedCE_vs_fresh_recomputedKL"]["spearman"])

    def test_metric_epsilon_is_before_alpha_and_separate_from_sampler_floor(self):
        vectors,draw,_,_=self.fixture();draw["alpha"]=.7
        parts=self.common.boundaries(draw,6)
        result=tool.fresh_weights(self.np,[0.,1.,2.,2.,2.,2.],draw,parts)
        leaf=result["per_leaf_float64"][0]
        self.assertAlmostEqual(leaf,10.**(-4.2),places=14)
        self.assertGreater(leaf,1e-6)
        self.assertEqual(result["per_clamped_leaf_float64"][0],leaf)
        self.assertEqual(result["weights_float32"][0],1.)

    def test_each_bank_gets_own_FP64_PER_mean_before_final_FP32_cast(self):
        vectors,draw,accounting,target=self.fixture()
        result=self.report(vectors,draw,accounting,target)
        fresh=result["fresh_selected_row_details"]["fresh_actual_ce"]
        expected_ratio=(1.+1e-6)/(3.+1e-6)
        expected_mean=(1.+expected_ratio)/2.
        self.assertEqual(fresh["weights_float64"][4],expected_mean)
        self.assertEqual(fresh["weights_float64"][5],expected_mean)
        cast_first=(fresh["weights_float32"][0]+fresh["weights_float32"][1])/2.
        self.assertNotEqual(fresh["weights_float64"][4],cast_first)
        self.assertEqual(result["weights_float32"]["fresh_recomputed_kl"][4:], [1.,1.])

    def test_interesting_and_recent_remain_one_for_every_readout(self):
        result=self.report(*self.fixture())
        for weights in result["weights_float32"].values():
            self.assertEqual(weights[2:4],[1.,1.])

    def test_scalar_readouts_hold_either_actual_or_conditional_CE_explicitly(self):
        result=self.report(*self.fixture())
        actual=result["readouts"]["emitted"]["using_actual_CE"]
        conditional=result["readouts"]["emitted"]["using_recomputed_CE"]
        self.assertEqual(actual["bellman_scalar"],9.75/6)
        self.assertEqual(conditional["bellman_scalar"],8.25/6)
        self.assertAlmostEqual(actual["expert_bellman_scalar"],3.5/6)
        self.assertEqual(actual["known_ACTUAL_bc_scalar_held_fixed"],.01)
        self.assertIn("not parameter gradients",actual["scope"])
        self.assertEqual(actual["coefficient_by_origin"]["hof"]["mean"],.625)

    def test_duplicate_PER_indices_remain_two_observations_not_a_fresh_tree(self):
        result=self.report(*self.fixture())
        self.assertEqual(result["duplicates"]["PER_rows"],2)
        self.assertEqual(result["duplicates"]["distinct_PER_indices"],1)
        self.assertEqual(result["duplicates"]["extra_repeated_PER_observations"],1)
        self.assertEqual(len(result["fresh_selected_row_details"]["fresh_actual_ce"]["per_leaf_float64"]),2)

    def test_signed_negative_KL_is_reported_and_only_then_clamped_for_metric(self):
        vectors,draw,accounting,target=self.fixture()
        vectors["recomputed_entropy"][0]=4.
        vectors["recomputed_kl_signed"][0]=-1.
        vectors["recomputed_kl_nonnegative"][0]=0.
        target=dict(target,negative_entries=1,max_abs_mass_error=.01)
        result=self.report(vectors,draw,accounting,target)
        self.assertEqual(result["conditional_KL"]["negative_rows"],1)
        self.assertEqual(result["conditional_KL"]["at_or_below_metric_epsilon_rows"],1)
        self.assertEqual(result["conditional_KL"]["target"]["negative_entries"],1)
        self.assertEqual(result["fresh_selected_row_details"]["fresh_recomputed_kl"]["per_leaf_float64"][0],1e-6)

    def test_inconsistent_conditional_subtraction_or_clamp_is_fatal(self):
        for field in ("recomputed_kl_signed","recomputed_kl_nonnegative"):
            with self.subTest(field=field):
                vectors,draw,accounting,target=self.fixture();vectors[field][0]=.75
                with self.assertRaisesRegex(ValueError,"SAME recomputed"):
                    self.report(vectors,draw,accounting,target)

    def test_bad_origins_actual_weight_normalizer_or_bank_mean_is_fatal(self):
        for kind in ("origin","normalizer","bank"):
            with self.subTest(kind=kind):
                vectors,draw,accounting,target=self.fixture()
                if kind=="origin":draw["origin_boundaries"][1]=("interesting",1,3)
                if kind=="normalizer":draw["per_raw_weights_float64"][0]=.75
                if kind=="bank":
                    for key in ("supplied_weights_float64","supplied_weights_float32"):draw[key][4]=.75
                    vectors["emitted_weights"][4]=.75
                with self.assertRaises(ValueError):self.report(vectors,draw,accounting,target)

    def test_nonfinite_and_negative_CE_or_fresh_metric_are_not_fabricated(self):
        for bad in (float("nan"),float("inf"),-1.):
            with self.subTest(value=bad):
                vectors,draw,accounting,target=self.fixture();vectors["actual_ce"][0]=bad
                with self.assertRaises(ValueError):self.report(vectors,draw,accounting,target)

    def test_rank_ties_and_empty_PER_are_explicit(self):
        self.assertIsNone(tool.rank_comparison([1.,1.],[2.,3.])["spearman"])
        self.assertIsNone(tool.rank_comparison([],[])["top_decile_overlap"])
        self.assertEqual(tool.ranks([2.,1.,1.]),[2.,.5,.5])
        vectors,draw,_,_=self.fixture()
        parts=dict(per=range(0),interesting=range(2),recent=range(2,4),hof=range(4,5),ephof=range(5,6))
        fresh=tool.fresh_weights(self.np,vectors["actual_ce"],draw,parts)
        self.assertEqual(fresh["weights_float32"],[1.]*6)


class ReadFreeDefault(unittest.TestCase):
    def test_default_plan_reads_no_helper_or_input_and_imports_no_numerical_module(self):
        original_import=builtins.__import__
        def guarded_import(name,*args,**kwargs):
            if name.split(".")[0] in ("numpy","torch"):
                raise AssertionError("numerical import")
            return original_import(name,*args,**kwargs)
        with patch.object(tool,"load_common",side_effect=AssertionError("helper read")), \
                patch.object(builtins,"__import__",side_effect=guarded_import), \
                patch.object(Path,"read_bytes",side_effect=AssertionError("file read")), \
                patch.object(Path,"read_text",side_effect=AssertionError("JSON read")), \
                patch.object(Path,"mkdir",side_effect=AssertionError("output")), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(tool.main([]),0)
        self.assertIn("PLAN_ONLY",output.getvalue())


if __name__=="__main__":
    unittest.main()
