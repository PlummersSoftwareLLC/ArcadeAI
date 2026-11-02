"""Synthetic plan and original-cohort checks; no GPU/MAME/policy qualification."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import audit_quality32_evidence_v3 as review
import test_audit_pilot_evidence as evidence_tests
from journal_consistency_test_support_v1 import campaign
from Robotron.tools import test_run_quality_campaign as campaign_tests


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.fixture = campaign_tests.Campaign32Tests('test_plan_has_fixed_defaults_new_jobs_hashes_and_no_side_effects')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        config = replace(campaign.Campaign(**vars(self.fixture.config)), cohort_s=5400, timeout_s=9000,
            mame=Path('/usr/games/mame'), rompath=review.GAME/'roms',
            boot_assets=review.GAME/'logs/managed-learning-20261015/sidecar-boot-assets-v1')
        with patch.object(campaign.sys, 'executable', str(review.GAME.parent/'.venv-gb300/bin/python')):
            plan = campaign.make_plan(config)
        directory = review.GAME/'logs/managed-learning-20261015'/'synthetic-future32-no-launch'
        self.plan = json.loads(json.dumps(plan).replace(str(config.directory), str(directory)))
        self.plan['checkpoints']['reference']['sha256'] = review.REFERENCE_SHA
        self.binding = {key: copy.deepcopy(self.plan[key]) for key in (
            'output_directory', 'checkpoints', 'evaluator_source_hashes', 'execution_source_hashes')}

    def validate(self):
        return review.validate_plan(self.plan, self.binding, campaign.evaluator.GAME)

    def test_complete_matched32_plan_with_individual_gates_passes_without_changes(self):
        before = copy.deepcopy((self.plan, self.binding))
        self.validate()
        self.assertEqual((self.plan, self.binding), before)
        self.assertFalse(Path(self.plan['output_directory']).exists())

    def test_all_four_roles_and_order_are_required(self):
        original = copy.deepcopy(self.plan)
        for change in ('missing', 'role', 'duplicate'):
            self.plan = copy.deepcopy(original)
            if change == 'missing': self.plan['legs'].pop()
            elif change == 'role': self.plan['legs'][2]['role'] = 'candidate'
            else: self.plan['legs'][3]['index'] = 3
            with self.subTest(change=change), self.assertRaises(ValueError): self.validate()

    def test_no_pooling_rescue_retries_extensions_or_dropped_tails(self):
        original = copy.deepcopy(self.plan)
        changes = [('min_full_games_per_leg', 49), ('max_attempts_per_leg', 2),
            ('admission_extensions', True), ('include_full_completion_tail', False),
            ('include_every_admitted_game', False), ('automatic_promotion', True),
            ('historical_or_interrupted_receipts_used', True)]
        for field, value in changes:
            self.plan = copy.deepcopy(original)
            self.plan['precommit'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate()
        for field, value in [('each_candidate_individually', False), ('minimum_mean_ratio', 1.04),
                             ('minimum_median_ratio', .99)]:
            self.plan = copy.deepcopy(original)
            self.plan['precommit']['candidate_gate'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate()

    def test_old_reference_same_candidate_or_foreign_snapshot_cannot_pass(self):
        for change in ('old_ref', 'same_candidate', 'snapshot'):
            original = copy.deepcopy(self.plan)
            if change == 'old_ref': self.plan['checkpoints']['reference']['sha256'] = 'a'*64
            elif change == 'same_candidate': self.plan['checkpoints']['candidate']['sha256'] = review.REFERENCE_SHA
            else: self.plan['checkpoints']['candidate']['snapshot'] = '/tmp/another.pt'
            with self.subTest(change=change), self.assertRaises(ValueError): self.validate()
            self.plan = original

    def test_every_leg_keeps_same_fixed_protocol(self):
        original = copy.deepcopy(self.plan)
        changes = [('actors', 16), ('actors', 32.0), ('actor_slots', review.SLOTS[:-1]),
            ('cohort_s', 3600), ('timeout_s', 6000), ('epsilon', .1), ('expert_ratio', .1),
            ('completion_policy', 'score_reset'), ('game_boundary_diagnostics', False),
            ('start_level', 5), ('difficulty', 4), ('fp16', True), ('replay_enabled', True),
            ('inference_max_batch_size', 32), ('wait_us', 500), ('gpu_uuid', 'wrong'),
            ('port', 9998), ('cpu_threads', 4)]
        for index in range(4):
            for field, value in changes:
                self.plan = copy.deepcopy(original)
                self.plan['legs'][index]['job'][field] = value
                with self.subTest(index=index, field=field), self.assertRaises(ValueError): self.validate()

    def test_full_command_cannot_override_precommitted_job(self):
        original = copy.deepcopy(self.plan)
        for change in ('duplicate_actors', 'cohort', 'port', 'checkpoint', 'diagnostics', 'foreign_script'):
            self.plan = copy.deepcopy(original)
            command = self.plan['legs'][1]['command']
            if change == 'duplicate_actors': command.extend(['--actors', '16'])
            elif change == 'diagnostics': command.remove('--game-boundary-diagnostics')
            elif change == 'foreign_script': command[4] = '/tmp/another.py'
            else:
                flag = dict(cohort='--cohort-s', port='--port', checkpoint='--checkpoint')[change]
                command[command.index(flag)+1] = 'changed'
            with self.subTest(change=change), self.assertRaises(ValueError): self.validate()

    def test_root_source_binding_cannot_be_changed(self):
        self.plan['evaluator_source_hashes']['Scripts/dqn/socket_server.py'] = 'a'*64
        with self.assertRaises(ValueError): self.validate()

    def test_default_cli_is_inert_even_with_unrecognized_execute_flag(self):
        child = subprocess.run([sys.executable, '-I', '-B', review.__file__, '--execute'],
            capture_output=True, text=True, check=True, timeout=10)
        self.assertTrue(child.stdout.startswith('PLAN_ONLY:'))


class OriginalCohortTests(evidence_tests.EvidenceTests):
    def games(self):
        import audit_pilot_evidence as helpers
        import audit_confirmed_completed_leg_reviewed3 as auditor
        from Robotron.tools import compare_sidecar_measurements as backend
        return review.completed_cohort(self.data, self.root, backend, helpers, auditor)['original_games']

    def test_startup_clients_cannot_include_duplicates_or_boolean_aliases(self):
        for ids in (list(range(32))+[0], [False]+list(range(1,32))):
            self.data['boundary']['acknowledged_client_ids'] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError): self.games()

    def test_negative_client_cannot_replace_a_valid_client(self):
        for row in self.data['rows']:
            if row['client_id'] == 0:
                row['client_id'] = -1
                self.data['terminal_successors'][row['journal_game_id']]['client_id'] = -1
        self.data['boundary']['acknowledged_client_ids'][0] = -1
        self.write_originals()
        with self.assertRaises(ValueError): self.games()

    def test_full_cohort_component_cannot_certify_root_or_policy(self):
        import audit_pilot_evidence as helpers
        import audit_confirmed_completed_leg_reviewed3 as auditor
        from Robotron.tools import compare_sidecar_measurements as backend
        result = review.completed_cohort(self.data, self.root, backend, helpers, auditor)
        self.assertFalse(result['quality_qualified'])
        self.assertFalse(result['promotion'])
        self.assertTrue(result['root_acquisition_campaign_lifecycle_and_main_hold_checks_still_required'])


class BoundDependenciesTests(unittest.TestCase):
    def test_actual_package_and_handler_branch_bindings_load_without_numerical_runtime(self):
        root, backend, helpers, auditor = review.dependencies()
        self.assertEqual(root, campaign.evaluator.GAME)
        self.assertTrue(auditor.OPTIONAL_EXPERT_PROOF_VALIDATED)
        self.assertEqual(helpers.HANDLER_SHA,
            '84901c887437e99873d65c2348f18ca9e2f022a393f3c5282d68064c9f1fbf40')
        self.assertNotIn('torch', sys.modules)
