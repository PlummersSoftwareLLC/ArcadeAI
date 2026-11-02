"""Engineering-only regression checks for closed-game comparison and packets."""
import copy
import json
from pathlib import Path
import unittest

from . import fullgame_review_pipeline_v2 as p
from . import assess_fullgame_study_v3 as final
from . import prepare_fullgame_reviews_v3 as prepare

I=p.BASE/'post-recovery-evaluation-isolation-original01-20261027'
PRECOMMIT=I/'fullgame-four-source-reader-reviews-engineering-original03/precommitted-four-reviews.json'


class FullgameReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h=p.helpers();cls.commit=p.read(cls.h.pin(PRECOMMIT));cls.prepared=p.read(cls.commit['native_prepared'])
        cls.legs=[]
        for index,(role,name)in enumerate(zip(p.ORDER,['01-reference','02-candidate','03-reference','04-candidate'])):
            root=p.PARENT/name;job=p.read(cls.h.pin(root/'job.json'));result=p.read(cls.h.pin(Path(job['output'])/'result.json'))
            review=p.read(cls.h.pin(root/'independent-quality-leg-review-original01/review.json'))
            native=p.read(cls.h.pin(root/'execution-original01/root-original-identity.json'))
            owner=p.read(cls.h.pin(root/'independent-review-execution-original01/root-original-identity.json'))
            cls.legs.append(dict(role=role,policy_sha256=review['policy']['checkpoint_sha256'],
                cohort=result['before_intentional_stop'],cohort_selection=review['cohort_selection'],
                evidence_verified=True,original_attempt=1,no_retry=True,
                native_identity=[native[k]for k in ('pid','starttime_ticks','invocation_id')],
                review_identity=[owner[k]for k in ('pid','starttime_ticks','invocation_id')]))
        cls.reference_sha=cls.legs[0]['policy_sha256'];cls.candidate_sha=cls.legs[1]['policy_sha256']

    def decide(self,legs):return p.numerical_decision(legs,self.reference_sha,self.candidate_sha,self.h)

    def synthetic(self,reference=1000,c1=1050,c2=1050):
        legs=copy.deepcopy(self.legs)
        numeric=p.load('_fullgame_unit_numeric',p.NUMERIC)
        for leg in legs:
            score=reference if leg['role'].startswith('R')else(c1 if leg['role']=='C1'else c2)
            for row in leg['cohort']['rows']:row['score']=score
            leg['cohort'].update({k:v for k,v in numeric.metrics([score]*64).items()if k in ('count','mean','median','sd','se')})
        return legs

    def restat(self,cohort):
        n=p.load('_fullgame_unit_restat',p.NUMERIC)
        cohort.update({k:v for k,v in n.metrics([row['score']for row in cohort['rows']]).items()if k in ('count','mean','median','sd','se')})

    def test_actual_historical_numeric_cohorts_reproduce_both_confirmations_without_promotion(self):
        result=self.decide(copy.deepcopy(self.legs))
        self.assertTrue(result['full_game_quality_qualified'])
        self.assertEqual(result['effective_complete_game_minimum'],64)
        self.assertFalse(result['promotion'])
        self.assertFalse(result['causal_learning_speed_gain_established'])
        old=p.read(self.h.pin(p.PARENT/'independent-campaign-assessment-original01/assessment.json'))
        self.assertEqual(result['original_quota64_decision'],old['decision'])

    def test_exact_five_percent_boundary_uses_original_integer_comparison(self):
        legs=self.synthetic();self.assertTrue(self.decide(legs)['full_game_quality_qualified'])
        legs[1]['cohort']['rows'][0]['score']-=1;self.restat(legs[1]['cohort'])
        result=self.decide(legs)['original_quota64_decision']
        self.assertFalse(result['independent_candidates']['C1']['mean_at_least_105_percent'])
        self.assertTrue(result['independent_candidates']['C2']['passed'])
        self.assertFalse(result['all_candidate_gates_passed'])

    def test_one_strong_candidate_cannot_rescue_other_by_pooling(self):
        result=self.decide(self.synthetic(c1=100_000_000,c2=1000))
        self.assertFalse(result['full_game_quality_qualified'])
        self.assertFalse(result['original_quota64_decision']['candidate_pool_used'])

    def test_high_mean_cannot_rescue_lost_median(self):
        legs=self.synthetic();rows=legs[1]['cohort']['rows']
        for row in rows:row['score']=0
        rows[0]['score']=1_000_000;self.restat(legs[1]['cohort'])
        result=self.decide(legs)['original_quota64_decision']['independent_candidates']['C1']
        self.assertTrue(result['mean_at_least_105_percent']);self.assertFalse(result['median_preserved']);self.assertFalse(result['passed'])

    def test_all64_slot_and_full_tail_failures_are_rejected(self):
        for fault in ('63_games','pending','abandoned','missing_slot','slot_quota','incomplete_game','unknown_start','duplicate_game','reused_game','wrong_policy','retry','reused_review_scope','cross_kind_scope'):
            legs=self.synthetic();cohort=legs[1]['cohort']
            if fault=='63_games':cohort['count']=63
            elif fault=='pending':cohort['pending']=1
            elif fault=='abandoned':cohort['abandoned']=1
            elif fault=='missing_slot':cohort['started_actor_slots']=cohort['started_actor_slots'][:-1]
            elif fault=='slot_quota':cohort['slot_admitted_counts']['4096']=1
            elif fault=='incomplete_game':cohort['rows'][0]['complete']=False
            elif fault=='unknown_start':cohort['rows'][0]['known_start']=False
            elif fault=='duplicate_game':cohort['rows'][0]['journal_game_id']=cohort['rows'][1]['journal_game_id']
            elif fault=='reused_game':cohort['started_ids'][0]=legs[0]['cohort']['started_ids'][0];cohort['rows'][0]['journal_game_id']=cohort['started_ids'][0]
            elif fault=='wrong_policy':legs[1]['policy_sha256']=self.reference_sha
            elif fault=='retry':legs[1]['original_attempt']=2
            elif fault=='reused_review_scope':legs[1]['review_identity']=legs[0]['review_identity']
            else:legs[1]['review_identity']=legs[0]['native_identity']
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.decide(legs)

    def test_four_actual_review_packets_and_declared_resources_match_consumers(self):
        for case,record in zip(self.prepared['cases'],self.commit['cases']):
            packet=p.read(record['review_job']);cfg=p.read(record['review_config'])
            self.assertEqual(p.cpu_controller(self.h).checked_config(record['review_config']['path']),cfg)
            p.validate_packet(case,packet,cfg,self.h)

    def test_damaged_packet_argv_source_and_resource_rejections(self):
        case=self.prepared['cases'][0];record=self.commit['cases'][0]
        for fault in ('native_job','runtime','source_dependency','output','argv','CPU','memory','runtime_limit','observation','scope_minimum'):
            packet=copy.deepcopy(p.read(record['review_job']));cfg=copy.deepcopy(p.read(record['review_config']))
            if fault=='native_job':packet['native_job']=self.prepared['cases'][1]['native_job']
            elif fault=='runtime':packet['sources']['runtime']['sha256']='f'*64
            elif fault=='source_dependency':packet['sources'].pop('games')
            elif fault=='output':packet['output']+='/wrong'
            elif fault=='argv':cfg['argv'][-1]='f'*64
            elif fault=='CPU':cfg['properties'][0]='CPUQuota=300%'
            elif fault=='memory':cfg['properties'][1]='MemoryMax=8G'
            elif fault=='runtime_limit':cfg['properties'][3]='RuntimeMaxSec=660'
            elif fault=='observation':cfg['observation_s']=2100
            else:packet['acceptance']=self.prepared['cases'][1]['acceptance']
            with self.subTest(fault=fault),self.assertRaises(ValueError):p.validate_packet(case,packet,cfg,self.h)

    def test_engineering_precommit_cannot_qualify_final_production_study(self):
        output=I/'MUST-NOT-EXIST-engineering-fullgame-qualification.json'
        with self.assertRaisesRegex(ValueError,'Engineering reviews cannot qualify'):
            final.assess(PRECOMMIT,self.h.pin(PRECOMMIT)['sha256'],output)
        self.assertFalse(output.exists())

    def test_engineering_native_packet_cannot_prepare_production_reviews(self):
        output=I/'MUST-NOT-EXIST-engineering-production-review-preparation'
        with self.assertRaisesRegex(ValueError,'Exact four-job/domain'):
            prepare.prepare(Path(self.commit['native_prepared']['path']),None,output)
        self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
