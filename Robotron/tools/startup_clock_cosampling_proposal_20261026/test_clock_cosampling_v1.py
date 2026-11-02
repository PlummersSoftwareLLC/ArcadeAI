"""Deterministic CPU clock-model guards; no sleeps, stress or host-clock change."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

PATH=Path(__file__).with_name('clock_cosampling_v1.py')
spec=importlib.util.spec_from_file_location('_clock_cosampling_under_test',PATH)
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
OFFSET=1_700_000_000_000_000_000

class Clock:
    def __init__(self,pairs):
        self.monos=iter([x for before,wall,after in pairs for x in (before,after)])
        self.walls=iter([wall for before,wall,after in pairs]);self.mono_reads=self.wall_reads=0
    def mono(self):self.mono_reads+=1;return next(self.monos)
    def wall(self):self.wall_reads+=1;return next(self.walls)

def pair(phase,midpoint,*,offset=OFFSET,span=1000):
    before=midpoint-span//2;after=before+span
    clock=Clock([(before,midpoint+offset,after)])
    return c.sample_pair(phase,deadline_mono_ns=after+1_000_000_000,monotonic_ns=clock.mono,wall_ns=clock.wall)

class Tests(unittest.TestCase):
    def test_01_tight_pair_midpoint_and_explicit_uncertainty(self):
        value=pair('before_authorization',1_000_000,span=1001)
        self.assertEqual(value['selected_index'],1)
        self.assertEqual(value['selected']['midpoint_mono_ns'],1_000_000)
        self.assertEqual(value['selected']['uncertainty_ns'],501)
        self.assertEqual(c.validate_pair(value),value['selected'])

    def test_02_injected_long_preemption_resamples_once_with_full_evidence(self):
        clock=Clock([(1000,OFFSET+250_001_000,500_001_000),(500_001_100,OFFSET+500_001_600,500_002_100)])
        value=c.sample_pair('before_authorization',deadline_mono_ns=1_000_001_000,monotonic_ns=clock.mono,wall_ns=clock.wall)
        self.assertEqual(value['selected_index'],2)
        self.assertEqual(value['attempts'][0]['span_ns'],500_000_000)
        self.assertEqual(value['attempts'][0]['status'],'span_exceeded')
        self.assertEqual(value['attempts'][1]['gap_before_ns'],100)
        self.assertEqual((clock.mono_reads,clock.wall_reads),(4,2))

    def test_03_attempt_limit_is_three_not_an_unbounded_retry(self):
        clock=Clock([(0,OFFSET,2_000_000),(2_000_001,OFFSET+2_000_001,5_000_001),(5_000_002,OFFSET+5_000_002,9_000_002)])
        with self.assertRaises(c.ClockSamplingError) as error:
            c.sample_pair('before_authorization',deadline_mono_ns=1_000_000_000,monotonic_ns=clock.mono,wall_ns=clock.wall)
        self.assertEqual(error.exception.reason,'attempt_limit_exhausted')
        self.assertEqual(len(error.exception.evidence['attempts']),3)
        self.assertEqual((clock.mono_reads,clock.wall_reads),(6,3))
        self.assertIsNone(error.exception.evidence['selected'])

    def test_04_existing_action_deadline_is_never_extended(self):
        clock=Clock([(100,OFFSET+100,20_000_100)])
        with self.assertRaises(c.ClockSamplingError) as error:
            c.sample_pair('after_accepted_frame',deadline_mono_ns=10_000_100,monotonic_ns=clock.mono,wall_ns=clock.wall)
        self.assertEqual(error.exception.reason,'deadline_exhausted')
        self.assertEqual(error.exception.evidence['effective_deadline_mono_ns'],10_000_100)
        self.assertEqual(len(error.exception.evidence['attempts']),1)

    def test_05_one_second_total_budget_caps_a_later_parent_deadline(self):
        clock=Clock([(1,OFFSET+1,1_000_000_002)])
        with self.assertRaises(c.ClockSamplingError) as error:
            c.sample_pair('after_accepted_frame',deadline_mono_ns=5_000_000_000,monotonic_ns=clock.mono,wall_ns=clock.wall)
        self.assertEqual(error.exception.evidence['effective_deadline_mono_ns'],1_000_000_001)
        self.assertEqual(error.exception.reason,'deadline_exhausted')

    def test_06_between_attempt_delay_is_charged_and_logged(self):
        clock=Clock([(0,OFFSET,2_000_000),(1_000_000_001,OFFSET+1_000_000_001,1_000_000_002)])
        with self.assertRaises(c.ClockSamplingError) as error:
            c.sample_pair('before_authorization',deadline_mono_ns=5_000_000_000,monotonic_ns=clock.mono,wall_ns=clock.wall)
        last=error.exception.evidence['attempts'][-1]
        self.assertEqual(last['gap_before_ns'],998_000_001)
        self.assertEqual(last['status'],'deadline_before_pair')
        self.assertEqual(clock.wall_reads,1)

    def test_07_clock_reversal_is_a_fault_not_a_resampling_opportunity(self):
        clock=Clock([(100,OFFSET+100,99)])
        with self.assertRaises(c.ClockSamplingError) as error:
            c.sample_pair('before_authorization',deadline_mono_ns=10000,monotonic_ns=clock.mono,wall_ns=clock.wall)
        self.assertEqual(error.exception.reason,'monotonic_reversed_inside_pair')
        clock=Clock([(0,OFFSET+1_000_000,2_000_000),(2_000_001,OFFSET,2_000_002)])
        with self.assertRaises(c.ClockSamplingError) as error:
            c.sample_pair('before_authorization',deadline_mono_ns=100_000_000,monotonic_ns=clock.mono,wall_ns=clock.wall)
        self.assertEqual(error.exception.reason,'wall_reversed_between_attempts')

    def test_08_forward_and_backward_real_wall_offset_steps_fail(self):
        lower=pair('before_authorization',1_000_000)
        for jump in (80_000_000,-80_000_000):
            with self.subTest(jump=jump),self.assertRaises(c.ClockCoherenceError):
                c.check_coherence(lower,pair('after_accepted_frame',10_000_000,offset=OFFSET+jump))

    def test_09_unchanged_50ms_bound_includes_both_uncertainties(self):
        lower=pair('before_authorization',1_000_000)
        accepted=pair('after_accepted_frame',10_000_000,offset=OFFSET+49_999_000)
        proof=c.check_coherence(lower,accepted)
        self.assertEqual(proof['maximum_possible_error_ns'],50_000_000)
        self.assertEqual(proof['tolerance_ns'],50_000_000)
        with self.assertRaises(c.ClockCoherenceError):
            c.check_coherence(lower,pair('after_accepted_frame',10_000_000,offset=OFFSET+49_999_001))

    def test_10_third_handoff_check_uses_original_lower_anchor(self):
        lower=pair('before_authorization',1_000_000)
        issued=pair('after_accepted_frame',10_000_000,offset=OFFSET+20_000_000)
        handoff=pair('before_journal_handoff',20_000_000,offset=OFFSET+60_000_000)
        self.assertTrue(c.check_coherence(lower,issued)['passed'])
        with self.assertRaises(c.ClockCoherenceError):c.check_coherence(lower,handoff)
        with self.assertRaises(ValueError):c.check_coherence(issued,handoff)

    def test_11_failure_or_fabricated_witness_never_becomes_a_certificate(self):
        good=pair('before_authorization',1_000_000)
        for change in ('deadline','midpoint','uncertainty','gap','status','boolean','tolerance_float'):
            value=copy.deepcopy(good)
            if change=='deadline':value['effective_deadline_mono_ns']+=1
            elif change=='midpoint':value['selected']['midpoint_mono_ns']+=1
            elif change=='uncertainty':value['selected']['uncertainty_ns']=0
            elif change=='gap':value['attempts'][0]['gap_before_ns']=1
            elif change=='status':value['status']='failed'
            elif change=='tolerance_float':value['policy']['coherence_tolerance_ns']=50_000_000.0
            else:value['attempts'][0]['index']=True
            with self.subTest(change=change),self.assertRaises(ValueError):c.validate_pair(value)

    def test_12_skipping_an_already_usable_pair_is_rejected(self):
        clock=Clock([(0,OFFSET,2_000_000),(2_000_001,OFFSET+2_000_501,2_001_001)])
        value=c.sample_pair('before_authorization',deadline_mono_ns=1_000_000_000,monotonic_ns=clock.mono,wall_ns=clock.wall)
        row=value['attempts'][0];row['mono_after_ns']=1000;row['span_ns']=row['elapsed_from_begin_ns']=1000
        value['attempts'][1]['gap_before_ns']=value['attempts'][1]['mono_before_ns']-1000
        with self.assertRaisesRegex(ValueError,'Skipped an already usable'):c.validate_pair(value)

    def test_13_invalid_types_or_wider_policies_fail_closed(self):
        for kwargs in ({'max_attempts':4},{'max_span_ns':1_000_001},{'max_total_ns':1_000_000_001},{'deadline_mono_ns':True}):
            options=dict(deadline_mono_ns=10000);options.update(kwargs)
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):c.sample_pair('before_authorization',**options)
        clock=Clock([(False,OFFSET,1000)])
        with self.assertRaises(c.ClockSamplingError):c.sample_pair('before_authorization',deadline_mono_ns=10000,monotonic_ns=clock.mono,wall_ns=clock.wall)

    def test_14_lossless_JSON_and_four_legacy_field_bounds(self):
        lower=json.loads(json.dumps(pair('before_authorization',1_000_000)))
        upper=json.loads(json.dumps(pair('after_accepted_frame',5_000_000)))
        proof=c.check_coherence(lower,upper);fields=proof['certificate_clock_fields']
        self.assertEqual(fields['lower_before_send_unix_ns'],lower['selected']['wall_ns'])
        self.assertEqual(fields['upper_after_receive_unix_ns'],upper['selected']['wall_ns'])
        self.assertLessEqual(lower['selected']['mono_before_ns'],fields['lower_monotonic_ns'])
        self.assertLessEqual(fields['lower_monotonic_ns'],lower['selected']['mono_after_ns'])
        self.assertLessEqual(upper['selected']['mono_before_ns'],fields['upper_monotonic_ns'])
        self.assertLessEqual(fields['upper_monotonic_ns'],upper['selected']['mono_after_ns'])

    def test_15_old_enclosure_failure_without_wall_step_new_sampling_passes(self):
        # One80ms scheduling pause between old lowerMONO/lowerWALL falsely
        # breaches the old50ms duration comparison despite a constant offset.
        self.assertGreater(abs((100_000_000-80_000_000)-(100_000_000-0)),50_000_000)
        clock=Clock([(0,OFFSET+80_000_000,80_000_000),(80_000_001,OFFSET+80_000_501,80_001_001)])
        lower=c.sample_pair('before_authorization',deadline_mono_ns=500_000_000,monotonic_ns=clock.mono,wall_ns=clock.wall)
        self.assertTrue(c.check_coherence(lower,pair('after_accepted_frame',100_000_000))['passed'])

if __name__=='__main__':unittest.main(verbosity=2)
