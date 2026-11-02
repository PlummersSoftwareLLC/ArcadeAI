"""Adversarial numerical gates for a future original campaign assessment."""
import copy
import importlib.util
from pathlib import Path
import statistics
import subprocess
import sys
import unittest

B=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_new_quality_campaign_assessor',B/'assess_quality32_campaign_v1.py')
audit=importlib.util.module_from_spec(spec);sys.modules[spec.name]=audit;spec.loader.exec_module(audit)
REFERENCE='a'*64
CANDIDATE='b'*64

def fixture(values=None):
    values=values or {'R1':[100]*50,'C1':[105]*50,'R2':[100]*50,'C2':[105]*50}
    result=[]
    for index,role in enumerate(('R1','C1','R2','C2')):
        scores=values[role];ids=[f'{role}:new-original:{i}'for i in range(len(scores))]
        rows=[dict(journal_game_id=jid,client_slot=4096+i%32,score=score,
            complete=True,eligible=True,known_start=True,excluded_reason='')for i,(jid,score)in enumerate(zip(ids,scores))]
        cohort=dict(closed=True,complete=True,valid=True,pending=0,abandoned=0,pending_ids=[],abandoned_ids=[],
            count=len(rows),started=len(rows),rows=rows,started_ids=ids,started_actor_slots=list(range(4096,4128)),
            mean=statistics.mean(scores),median=statistics.median(scores),sd=statistics.stdev(scores),
            se=statistics.stdev(scores)/len(scores)**.5)
        result.append(dict(role=role,cohort=cohort,evidence_verified=True,original_attempt=1,no_retry=True,
            policy_sha256=REFERENCE if role.startswith('R')else CANDIDATE,
            native_identity=[1000+index,2000+index,f'native-{index}'],
            review_identity=[3000+index,4000+index,f'review-{index}']))
    return result

class QualityCampaignAssessorV1(unittest.TestCase):
    def assess(self,legs):return audit.assess_validated_cohorts(legs,REFERENCE,CANDIDATE)

    def test_each_exact_105_percent_candidate_passes_against_one_fixed_fresh_reference(self):
        result=self.assess(fixture())
        self.assertEqual(result['fixed_fresh_reference']['count'],100)
        self.assertEqual(result['fixed_fresh_reference']['score_sum'],10000)
        self.assertEqual(result['fixed_fresh_reference']['mean'],100)
        self.assertEqual(result['fixed_fresh_reference']['median'],100)
        self.assertTrue(result['all_candidate_gates_passed'])
        self.assertEqual(result['independent_candidates']['C1']['mean_ratio'],1.05)
        self.assertFalse(result['candidate_pool_used'])
        self.assertNotIn('quality_qualified',result);self.assertNotIn('promotion',result)

    def test_a_higher_other_candidate_or_pooled_average_cannot_rescue_either_failed_confirmation(self):
        for failing in ('C1','C2'):
            values={'R1':[100]*50,'R2':[100]*50,'C1':[200]*50,'C2':[200]*50}
            values[failing]=[104]*50
            self.assertGreater(statistics.mean(values['C1']+values['C2']),105)
            result=self.assess(fixture(values))
            self.assertFalse(result['all_candidate_gates_passed'])
            self.assertFalse(result['independent_candidates'][failing]['mean_at_least_105_percent'])
            self.assertTrue(result['independent_candidates'][failing]['median_preserved'])

    def test_high_mean_with_regressed_candidate_median_cannot_qualify(self):
        values={'R1':[100]*50,'R2':[100]*50,'C1':[90]*26+[200]*24,'C2':[200]*50}
        result=self.assess(fixture(values));candidate=result['independent_candidates']['C1']
        self.assertTrue(candidate['mean_at_least_105_percent'])
        self.assertFalse(candidate['median_preserved']);self.assertFalse(candidate['passed'])
        self.assertFalse(result['all_candidate_gates_passed'])

    def test_all_fresh_reference_games_are_weighted_and_candidate_zero_is_not_filtered(self):
        values={'R1':[100]*50,'R2':[200]*100,'C1':[160]*50,'C2':[210]*50}
        result=self.assess(fixture(values))
        self.assertEqual(result['fixed_fresh_reference']['count'],150)
        self.assertAlmostEqual(result['fixed_fresh_reference']['mean'],25000/150)
        self.assertEqual(result['fixed_fresh_reference']['median'],200)
        self.assertFalse(result['independent_candidates']['C1']['passed'])
        self.assertTrue(result['independent_candidates']['C2']['passed'])
        values={'R1':[100]*50,'R2':[100]*50,'C1':[107]*49+[0],'C2':[200]*50}
        result=self.assess(fixture(values));candidate=result['independent_candidates']['C1']
        self.assertEqual(candidate['count'],50);self.assertEqual(candidate['score_sum'],5243)
        self.assertEqual(candidate['mean'],104.86)
        self.assertFalse(candidate['mean_at_least_105_percent']);self.assertFalse(result['all_candidate_gates_passed'])

    def test_each_leg_minimum_runtime_validity_identity_and_unfiltered_original_denominator_are_required(self):
        for damage in ('count49','runtime','pending','abandoned','retry','unverified','native_reuse',
                'review_reuse','game_reuse','policy','coverage','statistics','nonfinite','excluded'):
            with self.subTest(damage=damage):
                legs=fixture();leg=legs[0]
                if damage=='count49':
                    values={'R1':[100]*49,'R2':[100]*51,'C1':[105]*50,'C2':[105]*50};legs=fixture(values)
                elif damage=='runtime':leg['cohort']['valid']=False
                elif damage=='pending':leg['cohort']['pending']=1
                elif damage=='abandoned':leg['cohort']['abandoned']=1
                elif damage=='retry':leg['no_retry']=False
                elif damage=='unverified':leg['evidence_verified']=False
                elif damage=='native_reuse':legs[2]['native_identity']=leg['native_identity']
                elif damage=='review_reuse':legs[2]['review_identity']=leg['review_identity']
                elif damage=='game_reuse':
                    legs[2]['cohort']['rows'][0]['journal_game_id']=leg['cohort']['started_ids'][0]
                    legs[2]['cohort']['started_ids'][0]=leg['cohort']['started_ids'][0]
                elif damage=='policy':legs[1]['policy_sha256']=REFERENCE
                elif damage=='coverage':leg['cohort']['started_actor_slots'].pop()
                elif damage=='statistics':leg['cohort']['mean']+=1
                elif damage=='nonfinite':leg['cohort']['mean']=float('nan')
                else:leg['cohort']['rows'][0]['eligible']=False
                with self.assertRaises(ValueError):self.assess(legs)
        zero={'R1':[0]*50,'R2':[0]*50,'C1':[1]*50,'C2':[1]*50}
        with self.assertRaises(ValueError):self.assess(fixture(zero))

    def test_default_assessment_cli_is_inert_and_numerical_decision_does_not_install_or_promote(self):
        result=subprocess.run(['/usr/bin/python3.12','-I','-B',audit.__file__],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0);self.assertEqual(result.stdout.strip(),'PLAN_ONLY')
        self.assertEqual(result.stderr,'')
        legs=fixture();before=copy.deepcopy(legs);self.assess(legs);self.assertEqual(legs,before)
        self.assertNotIn('torch',sys.modules)

if __name__=='__main__':unittest.main(verbosity=2)
