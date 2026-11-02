"""Pure reference-state fixtures and real engineering-boundary rejections only."""
import copy
from pathlib import Path
import unittest

from . import adopt_fullgame_reference as a


class ReferenceAdoptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w=a.protection();cls.p=cls.w.pipeline();cls.h=cls.p.helpers()

    def fixture(self):
        root=Path('/ENGINEERING-FIXTURE-ONLY')
        old=dict(path=str(root/'models_dqn/managed-incumbents/old.pt'),sha256='a'*64)
        new=dict(path=str(root/'models_dqn/managed-incumbents/new.pt'),sha256='b'*64)
        previous=dict(path=str(root/'old-epoch.json'),sha256='c'*64);ep=dict(path=str(root/'new-epoch.json'),sha256='d'*64)
        close=dict(protected_checkpoint=new,protected_metadata=dict(path=new['path']+'.json'),previous_reference_epoch=previous,
            saved_clocks=dict(training_steps=100),actual_CPU_closeout=dict(path=str(root/'cpu.json')))
        verified=dict(reference=dict(policy=old),prior_protected_files=dict(path=str(root/'prior.json')),
            assessment=dict(synthetic_historical_quality_fixture_only=True))
        epoch=a.epoch_value(dict(path=str(root/'publication-close.json')),close,verified)
        state=dict(active_quality_job=None,learner=dict(training_steps=999,lr=3.125e-6),optimization_goal=dict(
            next_fixed_reference_epoch=previous,current_fixed_reference_policy=old,protected_incumbent='old',next_fixed_reference='old',
            scientific_job_running=False,performance_job_running=False,current_fixed_reference_pool=[1,2],next_fixed_reference_score_pool=[3,4]))
        return root,copy.deepcopy(state),epoch,ep

    def test_new_epoch_requires_fresh_reference_scores_and_preserves_historical_quality_as_context_only(self):
        root,state,epoch,ep=self.fixture()
        self.assertIsNone(epoch['next_reference_score_pool'])
        self.assertFalse(epoch['prior_candidate_games_reused_as_next_reference'])
        self.assertTrue(epoch['requires_new_R1_plus_R2_in_next_controlled_campaign'])
        self.assertEqual(epoch['candidate_gates_each']['minimum_complete_games'],64)
        self.assertEqual(epoch['quality_confirmation_only'],dict(synthetic_historical_quality_fixture_only=True))

    def test_pure_state_update_moves_all_four_policy_aliases_and_clears_both_score_pools(self):
        root,state,epoch,ep=self.fixture();before=copy.deepcopy(state);result=a.updated_state(state,ep,epoch,root);g=result['optimization_goal']
        self.assertEqual(g['next_fixed_reference_epoch'],ep)
        self.assertEqual(g['current_fixed_reference_policy'],epoch['reference_policy'])
        self.assertEqual(g['protected_incumbent'],g['next_fixed_reference'])
        self.assertEqual(g['next_fixed_reference'],'models_dqn/managed-incumbents/new.pt')
        self.assertIsNone(g['current_fixed_reference_pool']);self.assertIsNone(g['next_fixed_reference_score_pool'])
        self.assertEqual(g['previous_fixed_reference_epoch'],before['optimization_goal']['next_fixed_reference_epoch'])
        self.assertEqual(result['learner'],before['learner']);self.assertEqual(state,before)

    def test_engineering_epoch_score_reuse_or_weakened_confirmation_is_rejected(self):
        for fault in ('engineering','schema','pooled_scores','reuse_candidate','missing_R2','minimum50','mean','median','slot_coverage','retry'):
            root,state,epoch,ep=self.fixture()
            if fault=='engineering':epoch['engineering_only']=True
            elif fault=='schema':epoch['schema']='ENGINEERING'
            elif fault=='pooled_scores':epoch['next_reference_score_pool']=[11,12]
            elif fault=='reuse_candidate':epoch['prior_candidate_games_reused_as_next_reference']=True
            elif fault=='missing_R2':epoch['requires_new_R1_plus_R2_in_next_controlled_campaign']=False
            elif fault=='minimum50':epoch['candidate_gates_each']['minimum_complete_games']=50
            elif fault=='mean':epoch['candidate_gates_each']['mean_ratio_at_least']=1.01
            elif fault=='median':epoch['candidate_gates_each']['median_preserved']=False
            elif fault=='slot_coverage':epoch['candidate_gates_each']['all32_slots']=False
            else:epoch['candidate_gates_each']['no_scientific_retry']=False
            with self.subTest(fault=fault),self.assertRaises(ValueError):a.updated_state(state,ep,epoch,root)

    def test_changed_reference_or_active_workload_cannot_be_overwritten(self):
        for fault in ('epoch','policy','scientific','performance','active_registration'):
            root,state,epoch,ep=self.fixture();g=state['optimization_goal']
            if fault=='epoch':g['next_fixed_reference_epoch']['sha256']='f'*64
            elif fault=='policy':g['current_fixed_reference_policy']['sha256']='f'*64
            elif fault=='scientific':g['scientific_job_running']=True
            elif fault=='performance':g['performance_job_running']=True
            else:state['active_quality_job']=dict(state='finished',directory='/ENGINEERING-other-sequence')
            with self.subTest(fault=fault),self.assertRaises(ValueError):a.updated_state(state,ep,epoch,root)

    def test_engineering_CPU_scope_cannot_establish_a_real_publication_closeout(self):
        I=self.p.BASE/'post-recovery-evaluation-isolation-original01-20261027';directory=I/'fullgame-protection-gates-CPU-original01'
        with self.assertRaisesRegex(ValueError,'Engineering or foreign protection jobs'):
            a.close_publication(directory)
        self.assertFalse((directory/'independent-winner-publication-closeout.json').exists())

    def test_engineering_job_cannot_prepare_a_real_publication_scope(self):
        I=self.p.BASE/'post-recovery-evaluation-isolation-original01-20261027';directory=I/'fullgame-protection-gates-CPU-original01'
        config_before=(directory/'controller-config.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'Production winner protection job required'):
            a.prepare_publication_scope(directory/'job.json')
        self.assertEqual((directory/'controller-config.json').read_bytes(),config_before)
        self.assertFalse((directory/'prepared-publication-scope-NOT-LAUNCHED.json').exists())

    def test_engineering_CPU_receipt_cannot_adopt_a_reference_or_modify_real_state(self):
        I=self.p.BASE/'post-recovery-evaluation-isolation-original01-20261027';directory=I/'fullgame-protection-gates-CPU-original01'
        state=self.p.ROOT/'logs/managed-learning-20261015/state.json';before=state.read_bytes();output=directory/'MUST-NOT-EXIST-reference-epoch.json'
        with self.assertRaisesRegex(ValueError,'Actual independently closed winner publication'):
            a.adopt(directory/'independent-original-CPU-scope-closeout.json',output)
        self.assertFalse(output.exists());self.assertEqual(state.read_bytes(),before)


if __name__=='__main__':unittest.main()
