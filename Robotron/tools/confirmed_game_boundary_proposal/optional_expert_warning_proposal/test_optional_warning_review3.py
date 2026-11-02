"""Narrow warning classification and one-time original-reference handoff."""
import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

import audit_confirmed_completed_leg_reviewed3 as audit
import watch_confirmed_quality_audits_reviewed3 as watcher

HERE = Path(audit.__file__).parent
PREP = audit.GAME/'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018'
SUPPLEMENT = PREP/'R1-optional-expert-warning-supplemental-review-original01-20261019'


class WarningTests(unittest.TestCase):
    def setUp(self):
        self.job=dict(actors=16,expert_ratio=0,epsilon=0,completion_policy='confirmed_reset_reserves_v1',
                      game_boundary_diagnostics=True)
        self.rows=[dict(eval_only=True,measurement_active=True,
                       start_context=dict(expert_ratio=0.,epsilon=0.),
                       end_context=dict(expert_ratio=0.,epsilon=0.))]

    def allowed(self, number=2, line=None, validated=True):
        return audit.optional_expert_warning(number,audit.OPTIONAL_EXPERT_WARNING if line is None else line,
                                             self.job,self.rows,validated)

    def test_exact_warning_requires_actual_proof_and_frozen_controls(self):
        self.assertTrue(self.allowed())
        self.assertFalse(self.allowed(validated=False))
        for number in (1,3,99):self.assertFalse(self.allowed(number=number))
        for line in ('[WARN] expert unavailable','No module named v3','Traceback (most recent call last):',
                     audit.OPTIONAL_EXPERT_WARNING+' extra'):
            self.assertFalse(self.allowed(line=line))

    def test_training_exploration_changed_protocol_and_missing_context_are_not_exempted(self):
        base=copy.deepcopy(self.job)
        for key,value in (('actors',32),('expert_ratio',.1),('epsilon',.1),('expert_ratio',False),
                          ('completion_policy','wire_lives_v1'),('game_boundary_diagnostics',False)):
            self.job=dict(base,**{key:value})
            with self.subTest(key=key,value=value):self.assertFalse(self.allowed())
        self.job=base
        for key in ('eval_only','measurement_active'):
            row=self.rows[0];row[key]=False;self.assertFalse(self.allowed());row[key]=True
        for key in ('start_context','end_context'):
            value=self.rows[0].pop(key);self.assertFalse(self.allowed());self.rows[0][key]=value
        self.rows=[];self.assertFalse(self.allowed())

    def test_actual_captured_differential_is_read_back(self):
        audit.OPTIONAL_EXPERT_PROOF_VALIDATED=False
        audit.validate_optional_expert_proof()
        self.assertTrue(audit.OPTIONAL_EXPERT_PROOF_VALIDATED)

    def test_failed_or_partial_differential_cannot_authorize_classification(self):
        actual=audit.read_pin(audit.OPTIONAL_EXPERT_PROOF)
        closure=audit.read_pin(audit.OPTIONAL_EXPERT_CLOSURE)
        for change in ('expert_called','missing_case','real_model','wrong_source','exit_failure'):
            proof=copy.deepcopy(actual);control=copy.deepcopy(closure)
            if change=='expert_called':proof['cases'][0]['expert_calls']=1
            elif change=='missing_case':proof['cases'].pop()
            elif change=='real_model':proof['actual_model']=True
            elif change=='wrong_source':proof['manifest']['package_hashes']['socket_server.py']='0'*64
            else:control['original_exit']=1
            audit.OPTIONAL_EXPERT_PROOF_VALIDATED=False
            with self.subTest(change=change),patch.object(audit,'read_pin',side_effect=[proof,control]),self.assertRaises(ValueError):
                audit.validate_optional_expert_proof()
            self.assertFalse(audit.OPTIONAL_EXPERT_PROOF_VALIDATED)

    def test_all_unchanged_scientific_helpers_have_identical_AST(self):
        def functions(path):
            return {node.name:node for node in ast.parse(path.read_text()).body if isinstance(node,ast.FunctionDef)}
        old=functions(HERE/'audit_confirmed_completed_leg_reviewed2.py');new=functions(Path(audit.__file__))
        for name in ('validate_future_plan','validate_cpu_proof','validate_original_context',
                     'classify_actor_lines','validate_rom_terminal','validate_selected_package_and_validations','read_pin'):
            with self.subTest(name=name):self.assertEqual(ast.dump(old[name]),ast.dump(new[name]))
        # Normalize ONLY the documented classification branch and provenance
        # labels. Every original full-row/log/runtime/final-stability predicate
        # in the actual audit body must otherwise be bytecode-AST identical.
        body=copy.deepcopy(new['audit'])
        for node in ast.walk(body):
            if isinstance(node,ast.If) and len(node.orelse)==1 and isinstance(node.orelse[0],ast.If):
                other=node.orelse[0]
                if isinstance(other.test,ast.Call) and isinstance(other.test.func,ast.Name) and other.test.func.id=='optional_expert_warning':
                    node.orelse=[]
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='dict':
                names=[keyword.arg for keyword in node.keywords]
                if 'original_row_and_runtime_predicates_preserved' in names:
                    index=names.index('original_row_and_runtime_predicates_preserved')
                    remove={'original_row_and_runtime_predicates_preserved','all_other_log_predicates_preserved',
                            'exact_disabled_expert_warning_classification'}
                    node.keywords=[keyword for keyword in node.keywords if keyword.arg not in remove]
                    node.keywords.insert(index,ast.keyword(arg='original_row_and_log_predicates_preserved',value=ast.Constant(True)))
        self.assertEqual(ast.dump(old['audit']),ast.dump(body))


class ReferenceHandoffTests(unittest.TestCase):
    def setUp(self):
        self.review=json.loads((SUPPLEMENT/'supplemental-review-output/review.json').read_bytes())
        self.plan=self.review['plan_sha256']

    def test_actual_reference_supplement_is_valid_without_changing_original_failure(self):
        before=copy.deepcopy(self.review)
        watcher.validate_reference_supplement(self.review,self.plan)
        self.assertEqual(self.review,before)
        self.assertFalse(self.review['original_audit_valid'])
        self.assertEqual(self.review['original_audit_exit'],2)

    def test_handoff_rejects_partial_terminal_proofs_other_roles_and_reruns(self):
        for change in ('wrong_plan','candidate','rerun','audit_rerun','gates','floor','missing_ROM','changed_warning'):
            review=copy.deepcopy(self.review);plan=self.plan
            if change=='wrong_plan':plan='0'*64
            elif change=='candidate':review['role']='candidate';review['leg']=2
            elif change=='rerun':review['cohort_rerun']=True
            elif change=='audit_rerun':review['original_auditor_rerun']=True
            elif change=='gates':review['scientific_gates_changed']=True
            elif change=='floor':review['statistics']['count']=201
            elif change=='missing_ROM':review['rom_game_over_evidence']['links'].pop()
            else:review['classified_warning']['text']='another warning'
            with self.subTest(change=change),self.assertRaises(ValueError):
                watcher.validate_reference_supplement(review,plan)

    def test_real_observer_run_skips_reference_and_keeps_seed_after_first_candidate_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);seed=root/'seed.json';seed.write_text(json.dumps(self.review))
            closure=root/'closure.json';closure.write_text(json.dumps(dict(original_exit=0,lifecycle_complete=True,unit_released=True)))
            state_path=root/'state.json';state=dict(plan_sha256=self.plan,legs=[self.review['original_finished_record'],
                dict(index=2,role='candidate',state='finished',returncode=0),dict(index=3,role='reference',state='running')])
            state_path.write_text(json.dumps(state))
            controller=root/'controller';controller.mkdir();audit_dir=root/'audit';audit_dir.mkdir()
            (controller/'root-original-result-and-owned-release.json').write_text(json.dumps(
                dict(original_exit=0,lifecycle_complete=True,unit_released=True)))
            (audit_dir/'review-receipt.json').write_text(json.dumps(dict(valid=True,leg=2,plan_sha256=self.plan,
                schema='robotron-confirmed-original-terminal-leg-v1',statistics=dict(count=50),
                original_terminal_readback=dict(status='PASS',verified_games=50),
                rom_game_over_evidence=dict(status='PASS',verified_games=50))))
            config=root/'config.json';config.write_text(json.dumps(dict(output=str(controller),argv=['audit','--output',str(audit_dir)])))
            job=dict(output=str(root/'observer'),pins=[watcher.pin(seed),watcher.pin(closure),watcher.pin(config)],
                     owner=dict(unit='native'),previous_observer=dict(unit='prior'),
                     reference_supplement=watcher.pin(seed),reference_supplement_closure=watcher.pin(closure),
                     state_path=str(state_path),plan=dict(sha256=self.plan),configs={'2':watcher.pin(config)},
                     controller=dict(path='fixture-controller',sha256='a'*64))
            def owner(value):return value['unit']=='prior'
            def stop_after_first(_):watcher.STOP=True
            with patch.object(watcher,'STOP',False),patch.object(watcher,'original_owner',side_effect=owner),\
                 patch.object(watcher.time,'sleep',side_effect=stop_after_first),\
                 patch.object(watcher.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as child:
                self.assertEqual(watcher.run(job),1)
            result=json.loads((root/'observer/result.json').read_bytes())
            self.assertEqual(result['attempted'],[1,2])
            self.assertEqual(len(result['audits']),2)
            self.assertIn('InterruptedError',result['error'])
            child.assert_called_once()
            self.assertFalse((root/'observer/leg01-original-attempt.json').exists())


if __name__=='__main__':unittest.main()
