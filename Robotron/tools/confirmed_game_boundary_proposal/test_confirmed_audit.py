"""CPU-only tests of qualification protocol boundaries; no emulator or model."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
import json

import audit_confirmed_completed_leg as audit
import importlib.util
import sys
sys.path.insert(0,str(audit.EVAL_GAME/'tools'))
import run_quality_campaign as campaign


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.directory=audit.CAMPAIGN_ROOT/'quality-post-continuity-test-only'
        reference=audit.GAME/'models_dqn/managed-incumbents/freshCE-LR25-845M-confirmed-20261018.pt'
        candidate=audit.GAME/'models_dqn/managed-checkpoints/test-only.pt'
        c=campaign.Campaign(reference,candidate,self.directory,cohort_s=5400,timeout_s=7200,
                            game_boundary_diagnostics=True)
        # Explicit synthetic plan; make_plan() would read real checkpoints.
        self.plan=dict(output_directory=str(self.directory),
            evaluator_source_hashes={'Scripts/dqn/socket_server.py':
                '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408',
                'Scripts/dqn/game_journal.py':'3b8dc9ecf592cdb868443e9c1b21cde3ef398ac0a79a2d00c1c70a811bdeb90e',
                'tools/confirmed_terminal_evidence.py':'2416a19e63d9bcea7521795c139bbde269dc229124a1d34c5fc2a6a4d4aa6502'},
            execution_source_hashes={'synthetic-only':'0'*64},
            checkpoints={role:dict(source=str(path), snapshot=str(self.directory/'checkpoints'/(role+'.pt')),
                sha256=('fda8dcdf80a794b2715843dc892890296363c7586c60bae435a0925e32997ecd'
                        if role=='reference' else '1'*64))
                for role,path in [('reference',reference),('candidate',candidate)]},
            legs=[dict(index=i,role=role,job=job.plan(),command=[str(audit.GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',str(audit.EVAL_GAME/'tools/run_frozen_sidecar.py'),'--game-boundary-diagnostics'])
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
        for key,value in [('cohort_s',2400),('timeout_s',6000),('difficulty',4),
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

    def test_legacy_completion_policy_and_scorer_are_rejected(self):
        for key, value in [('completion_policy','wire_lives_v1'),
                           ('completion_policy',None), ('game_boundary_diagnostics',False)]:
            plan = copy.deepcopy(self.plan)
            for spec in plan['legs']:
                spec['job'][key] = value
            with self.assertRaises(ValueError):
                audit.validate_future_plan(plan,self.args,self.directory)
        changed = copy.deepcopy(self.plan)
        changed['evaluator_source_hashes']['Scripts/dqn/game_journal.py'] = '10827d786becfd19c386bddfbce85f1ab5ace5349d87717305e4044a2843edb0'
        audit.CFG['campaign']['evaluator_source_hashes'] = changed['evaluator_source_hashes']
        with self.assertRaises(ValueError):
            audit.validate_future_plan(changed,self.args,self.directory)

    def test_original_canonical_command_cannot_substitute_for_private_source(self):
        changed = copy.deepcopy(self.plan)
        changed['legs'][0]['command'][4] = str(audit.GAME/'tools/run_frozen_sidecar.py')
        with self.assertRaises(ValueError):
            audit.validate_future_plan(changed,self.args,self.directory)


class ActualValidationBindingTests(unittest.TestCase):
    def setUp(self):
        base = audit.GAME/'logs/managed-learning-20261015/run-26'
        audit.BUNDLE = dict(source_package=json.loads((audit.EVAL_GAME.parent/'runtime-source-package.json').read_bytes()),
            validation_reference=json.loads((base/'confirmed-game-boundary-real-MAME-reference-original01-20261018/result.json').read_bytes()),
            validation_integrated=json.loads((base/'confirmed-game-boundary-real-MAME-integrated-no-fire-up-original01-20261018/result.json').read_bytes()),
            window_job=json.loads((base/'post-confirmed-scoring-next8M-original01-root-preparation-20261018/job.json').read_bytes()))

    def test_actual_package_and_completed_real_validations_match(self):
        audit.validate_selected_package_and_validations()

    def test_missing_zero_score_or_readback_validation_is_rejected(self):
        original = copy.deepcopy(audit.BUNDLE)
        for section, key, value in [('progress','zero_completed',0),
                                     ('progress','zero_slots',[]),
                                     ('original_terminal_readback','status','FAIL'),
                                     ('original_terminal_readback','verified_games',0)]:
            audit.BUNDLE = copy.deepcopy(original)
            audit.BUNDLE['validation_integrated'][section][key] = value
            with self.assertRaises(ValueError):
                audit.validate_selected_package_and_validations()

    def test_failed_or_partial_real_validation_is_rejected(self):
        for field, value in [('status','FAIL_PRESERVED'),('source_unchanged',False),
                             ('owned_actors_absent',False),('quality_qualification',True),
                             ('cleanup_errors',['lost handler'])]:
            with self.subTest(field=field):
                self.setUp()
                audit.BUNDLE['validation_reference'][field] = value
                with self.assertRaises(ValueError):
                    audit.validate_selected_package_and_validations()

    def test_wrong_main_owner_or_private_source_is_rejected(self):
        audit.BUNDLE['validation_reference']['main_after']['pid'] += 1
        with self.assertRaises(ValueError):
            audit.validate_selected_package_and_validations()
        self.setUp()
        audit.BUNDLE['source_package']['files']['Scripts/dqn/game_journal.py'] = '0'*64
        with self.assertRaises(ValueError):
            audit.validate_selected_package_and_validations()


if __name__=='__main__':
    unittest.main()



