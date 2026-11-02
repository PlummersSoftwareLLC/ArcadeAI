"""CPU-only tests of qualification protocol boundaries; no emulator or model."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

import post_continuity_audit_completed_leg as audit
import run_quality_campaign as campaign


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.directory=audit.CAMPAIGN_ROOT/'quality-post-continuity-test-only'
        reference=audit.GAME/'models_dqn/managed-incumbents/freshCE-LR25-845M-confirmed-20261018.pt'
        candidate=audit.GAME/'models_dqn/managed-checkpoints/test-only.pt'
        c=campaign.Campaign(reference,candidate,self.directory,cohort_s=3600,timeout_s=6000,
                            game_boundary_diagnostics=True)
        # Explicit synthetic plan; make_plan() would read real checkpoints.
        self.plan=dict(output_directory=str(self.directory),
            evaluator_source_hashes={'Scripts/dqn/socket_server.py':
                '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408'},
            execution_source_hashes={'synthetic-only':'0'*64},
            checkpoints={role:dict(source=str(path), snapshot=str(self.directory/'checkpoints'/(role+'.pt')),
                sha256=('fda8dcdf80a794b2715843dc892890296363c7586c60bae435a0925e32997ecd'
                        if role=='reference' else '1'*64))
                for role,path in [('reference',reference),('candidate',candidate)]},
            legs=[dict(index=i,role=role,job=job.plan(),command=['--game-boundary-diagnostics'])
                  for i,(role,job) in enumerate(c.jobs(),1)],
            precommit=dict(order=['reference','candidate','reference','candidate'],
                new_same_length_reference_cohorts=True,historical_or_interrupted_receipts_used=False,
                min_full_games_per_leg=50,all_actor_slots=audit.SLOTS,include_every_admitted_game=True,
                include_full_completion_tail=True,max_attempts_per_leg=1,admission_extensions=False,
                automatic_promotion=False,automatic_rollback=False,learning_changes=False,
                candidate_gate=dict(each_candidate_individually=True,
                    reference='all games pooled from both fresh reference legs',minimum_mean_ratio=1.05,
                    minimum_median_ratio=1.0)))
        audit.CFG=dict(campaign={k:copy.deepcopy(self.plan[k]) for k in
            ('output_directory','evaluator_source_hashes','execution_source_hashes')},
            **{role:dict(path=self.plan['checkpoints'][role]['source'],
                sha256=self.plan['checkpoints'][role]['sha256']) for role in ('reference','candidate')})
        audit.CFG['campaign']['plan_sha256']='2'*64
        self.args=SimpleNamespace(campaign=self.directory,plan_sha256='2'*64)

    def validate(self):
        return audit.validate_future_plan(self.plan,self.args,self.directory)

    def test_selected_fixed_long_profile(self):
        self.validate()

    def test_cannot_substitute_another_native_plan(self):
        self.args.plan_sha256='3'*64
        with self.assertRaises(ValueError): self.validate()

    def test_cannot_lower_50_game_floor_or_rescue_by_retry_extension_or_pooling(self):
        original=copy.deepcopy(self.plan)
        changes=[('min_full_games_per_leg',49),('max_attempts_per_leg',2),
                 ('admission_extensions',True),('historical_or_interrupted_receipts_used',True),
                 ('include_full_completion_tail',False)]
        for key,value in changes:
            with self.subTest(key=key):
                self.plan=copy.deepcopy(original);self.plan['precommit'][key]=value
                with self.assertRaises(ValueError): self.validate()

    def test_each_candidate_must_pass_mean_and_median(self):
        for key,value in [('each_candidate_individually',False),('minimum_mean_ratio',1.0),
                          ('minimum_median_ratio',.99)]:
            with self.subTest(key=key):
                changed=copy.deepcopy(self.plan)
                changed['precommit']['candidate_gate'][key]=value
                with self.assertRaises(ValueError):
                    audit.validate_future_plan(changed,self.args,self.directory)

    def test_leg_specific_profile_changes_fail(self):
        for key,value in [('cohort_s',2400),('timeout_s',7200),('difficulty',4),
                          ('epsilon',.1),('game_boundary_diagnostics',False),('cpu_threads',4)]:
            with self.subTest(key=key):
                changed=copy.deepcopy(self.plan);changed['legs'][1]['job'][key]=value
                with self.assertRaises(ValueError):
                    audit.validate_future_plan(changed,self.args,self.directory)

    def test_old_effective_guard_or_old_canonical_source_fails(self):
        self.plan['effective_implementation']={'synthetic-only':True}
        with self.assertRaises(ValueError): self.validate()
        del self.plan['effective_implementation']
        self.plan['evaluator_source_hashes']['Scripts/dqn/socket_server.py']='0'*64
        audit.CFG['campaign']['evaluator_source_hashes']=self.plan['evaluator_source_hashes']
        with self.assertRaises(ValueError): self.validate()


if __name__=='__main__':
    unittest.main()
