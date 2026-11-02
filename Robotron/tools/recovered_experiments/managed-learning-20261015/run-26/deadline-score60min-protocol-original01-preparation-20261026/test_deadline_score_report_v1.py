"""Pure report/numerical rule fixtures; no model or native outcomes are read."""
import copy
import importlib.util
import json
from pathlib import Path
import statistics
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_deadline_report', HERE/'deadline_score_report_v1.py')
report = importlib.util.module_from_spec(spec); spec.loader.exec_module(report)


def seal(leg, scores, completed=0):
    rows=[]
    for i,score in enumerate(scores):
        done=i<completed
        rows.append(dict(slot=4096+i,status='completed' if done else 'censored',
            whole_game_complete=done,right_censored=not done,score_at_deadline=score,
            score_at_anchor=score//2,selected_first_game_accepted_frame_exposure=100,
            accepted_frame_exposure=110,score_snapshot_age_ns=10,activity_age_ns=2,
            member=dict(session=f'{leg}:{i}:session',connection=f'{leg}:{i}:connection',journal_game_id=f'{leg}:{i}')))
    return dict(schema=report.SCHEMA,horizon_ns=3_600_000_000_000,n_scored=32,
        n_completed=completed,n_censored=32-completed,rows=rows,score_sum=sum(scores),
        mean_score=statistics.mean(scores),median_score=statistics.median(scores),
        se_score=statistics.stdev(scores)/(32**.5),full_game_quality_qualified=False,
        improvement_qualified=False,policy={'policy_sha256':('a' if leg.startswith('R') else 'b')*64})


def four(candidate1=1050,candidate2=1050):
    return {name:seal(name,[1000 if name.startswith('R') else candidate1 if name=='C1' else candidate2]*32)
            for name in report.ORDER}


class Tests(unittest.TestCase):
    def test_console_preserves_full_integer_and_honest_zero_completed(self):
        value=seal('R1',[100000001]*32)
        text=report.format_console(value)
        self.assertIn('Scored: 32  Completed: 0  Unfinished / right-censored: 32',text)
        self.assertIn('100,000,001',text)
        self.assertIn('First-game frames since anchor  All frames since anchor',text)
        self.assertNotIn('count complete games',text)

    def test_exact_five_percent_passes_and_result_is_json_serializable(self):
        result=report.compare_four(four())
        self.assertTrue(result['both_numeric_gates_passed'])
        self.assertEqual(result['reference_mean_exact'],dict(numerator=64000,denominator=64))
        self.assertFalse(result['automatic_promotion'])
        self.assertTrue(result['independent_source_cutoff_score_and_owned_cleanup_audits_still_required'])
        self.assertEqual(json.loads(json.dumps(result))['reference_n_censored'],64)

    def test_each_candidate_must_pass_without_pooled_rescue(self):
        result=report.compare_four(four(1049,2000))
        self.assertFalse(result['both_numeric_gates_passed'])
        self.assertFalse(result['independent_candidates']['C1']['mean_gain_passed'])
        self.assertTrue(result['independent_candidates']['C2']['numerical_gate_passed'])

    def test_mean_gain_cannot_replace_preserved_median(self):
        values=four();values['C1']=seal('C1',[999]*17+[1108]*15)
        result=report.compare_four(values)['independent_candidates']['C1']
        self.assertTrue(result['mean_gain_passed'])
        self.assertFalse(result['median_preserved'])
        self.assertFalse(result['numerical_gate_passed'])

    def test_zero_score_leg_valid_but_relative_gain_undefined(self):
        values={name:seal(name,[0]*32) for name in report.ORDER}
        self.assertEqual(report.validate(values['R1']),[0]*32)
        for candidate in (0,100):
            values['C1']=seal('C1',[candidate]*32)
            result=report.compare_four(values)
            self.assertFalse(result['both_numeric_gates_passed'])
            gate=result['independent_candidates']['C1']
            self.assertFalse(gate['mean_gain_defined'])
            self.assertFalse(gate['mean_gain_passed'])
            self.assertEqual(gate['mean_gain_reason'],'relative_gain_undefined_zero_reference_score_sum')

    def test_member_reuse_bad_denominator_and_false_completed_labels_rejected(self):
        values=four();values['C1']['rows'][0]['member']=copy.deepcopy(values['R1']['rows'][0]['member'])
        with self.assertRaises(ValueError):report.compare_four(values)
        values=four();values['C1']['rows'][0]['member']['session']=values['R1']['rows'][0]['member']['session']
        with self.assertRaises(ValueError):report.compare_four(values)
        for field,value in [('n_scored',31),('n_censored',31),('full_game_quality_qualified',True)]:
            bad=seal('R1',[1000]*32);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):report.validate(bad)
        bad=seal('R1',[1000]*32);bad['rows'][0]['whole_game_complete']=True
        with self.assertRaises(ValueError):report.validate(bad)


if __name__=='__main__':unittest.main()
