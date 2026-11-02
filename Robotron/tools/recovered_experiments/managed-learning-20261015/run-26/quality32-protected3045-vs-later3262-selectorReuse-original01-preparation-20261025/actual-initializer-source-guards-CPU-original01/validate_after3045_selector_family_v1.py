"""Validate the actual bound family and prepare one isolated, never-launched fixture."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job'); parser.add_argument('--job-sha256'); parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute: print('PLAN_ONLY'); return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw = Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job = json.loads(raw)
    assert job['schema'] == 'robotron-selected-quota64-family-CPU-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''

    def load(pin, name):
        path = Path(pin['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        spec.loader.exec_module(module); return module

    h = load(job['helpers'], '_selected64_h'); reader = load(job['reader'], '_selected64_reader')
    def read(pin): return reader.read_pin(pin)
    ready = read(job['readiness']); family = read(ready['source_family_manifest'])
    pair = read(ready['quality_pair']); pre = read(job['sequence_precommit'])
    modules = {key: load(family[key], '_selected64_' + key) for key in
               ('runtime', 'native_controller', 'leg_reviewer', 'campaign_assessor', 'leg_preparer', 'sequence', 'renderer')}
    runtime = modules['runtime']; reviewer = modules['leg_reviewer']; renderer = modules['renderer']
    base = load(job['sequence_base'], '_selected64_base')
    output = Path(job['output']); output.mkdir(mode=0o700)
    negatives = []; fixture = None; selected_native_prefix = None

    class Contracts(unittest.TestCase):
        def test_01_actual_seven_sources_are_exact_pure_bindings_of_tested_templates(self):
            templates = {key: h.checked(pin).read_text() for key, pin in family['source_templates'].items()}
            rendered = renderer.render(templates, pair, ready['quality_pair']['sha256'])
            for key, item in rendered.items():
                self.assertEqual(family[key]['path'], item['path'])
                self.assertEqual(family[key]['sha256'], item['sha256'])
                self.assertEqual(h.checked(family[key]).read_text(), item['source'])
            for pin in ready['inputs']: h.checked(pin)

        def test_02_actual_numerical_endpoint_and_original_scope_are_valid(self):
            instance = modules['sequence'].sequence_type(base)(job['sequence_precommit'], h, reader)
            instance.validate_endpoint_CPU()
            report = read(pre['endpoint_CPU_report'])
            self.assertEqual({key: report['clocks'][key] for key in renderer.REF_CLOCKS}, pair['candidate']['saved_clocks'])
            self.assertEqual(pair['reference']['saved_clocks'], renderer.REF_CLOCKS)
            self.assertEqual(pair['reference']['policy']['sha256'], renderer.REF_SHA)
            self.assertEqual(report['held_recipe_context']['learning_control_lr_scale'], .125)
            self.assertEqual(report['adam_group']['lr'], 6.25e-6)
            self.assertFalse(report['cuda_initialized'])
            for key, floor in renderer.REF_CLOCKS.items():
                self.assertGreater(pair['candidate']['saved_clocks'][key], floor)

        def test_03_all_four_roles_accept_exact_structural_job_and_review_scope(self):
            template = read(ready['native_job_template'])
            for role, policy_role in runtime.ROLES.items():
                data = copy.deepcopy(template)
                data.update(schema='robotron-compiled-quota64-quality-original-v1', quality_leg=role,
                            quality_pair_precommit=ready['quality_pair'], minimum_completed_games=50,
                            expected_policy_clocks=runtime.POLICIES[policy_role]['clocks'],
                            checkpoint=pair[policy_role]['policy'], runtime=ready['native_runtime'],
                            main_health_protocol=ready['source_family_manifest'], source_family_manifest=ready['source_family_manifest'],
                            sessions={str(slot): format(index + 1, '032x') for index, slot in enumerate(runtime.SLOTS)},
                            connections={str(slot): format(index + 33, '032x') for index, slot in enumerate(runtime.SLOTS)},
                            output=str(output / ('never-launched-structural-' + role)))
                runtime.validate_job(data)
                role_root = output / ('explicit-structural-' + role); role_root.mkdir(mode=0o700)
                jp = h.put(role_root / 'job.json', data)
                scope = dict(schema='robotron-original-all32-quota64-quality-acceptance-v1', job=jp,
                             original_attempt=1, no_retry=True, outer_start_horizon_s=21540,
                             whole_cohort_timeout_s=21600, admission_mode='first_two_known_starts_per_declared_slot',
                             expected_selected_games=64, wall_limit_s=22200, startup_trace_frames=1200,
                             minimum_quality_completed_games=50, quality_minimum_games_remains=50,
                             quality_qualified=False, promotion=False)
                config = dict(unit='robotron-compiled-full-tail32-integration-synthetic-' + role.lower() + '.service',
                              output=str(output / ('never-launched-controller-' + role)), properties=reviewer.PROPERTIES,
                              observation_s=22320, pins=[jp, data['runtime']],
                              argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-I', '-B',
                                    data['runtime']['path'], '--execute', '--job', jp['path'], '--job-sha256', jp['sha256'],
                                    '--source-sha256', data['runtime']['sha256']])
                reviewer.validate_scope(data, jp, scope, config)
                cp = h.put(output / ('structural-controller-' + role + '.json'), config)
                modules['native_controller'].checked_config(cp['path'])
                for key, value in [('minimum_completed_games', 49), ('admission_s', 21541),
                                   ('whole_cohort_timeout_s', 21601), ('backend', 'eager')]:
                    wrong = copy.deepcopy(data); wrong[key] = value
                    with self.assertRaises(ValueError): runtime.validate_job(wrong)
                    negatives.append(role + ':' + key)
                wrong = dict(scope, expected_selected_games=63)
                with self.assertRaisesRegex(ValueError, 'acceptance'): reviewer.validate_scope(data, jp, wrong, config)
                negatives.append(role + ':selected_game_count')

        def test_04_original_numerical_decision_tail_and_runtime_helpers_are_unchanged(self):
            def definitions(pin):
                return {node.name: node for node in ast.parse(h.checked(pin).read_text()).body
                        if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
            original = definitions(job['original_runtime']); current = definitions(ready['native_runtime'])
            for name, node in original.items():
                if name not in ('run', 'validate_job'): self.assertEqual(ast.dump(node), ast.dump(current[name]), name)
            old = definitions(job['original_assessor']); new = definitions(ready['campaign_assessor'])
            self.assertEqual(ast.dump(old['metrics']), ast.dump(new['metrics']))
            def tail(node):
                index = next(index for index, item in enumerate(node.body) if isinstance(item, ast.Assign)
                             and isinstance(item.targets[0], ast.Name) and item.targets[0].id == 'reference')
                return [ast.dump(item) for item in node.body[index:]]
            self.assertEqual(tail(old['assess_validated_cohorts']), tail(new['assess_validated_cohorts']))

        def test_05_selected_observer_health_quota_and_review_resources_match_proofs(self):
            self.assertEqual({key: pin['sha256'] for key, pin in ready['main_health_sources'].items()}, runtime.HEALTH_DEPENDENCIES)
            self.assertEqual({key: pin['sha256'] for key, pin in family['main_observer'].items()}, runtime.OBSERVER_DEPENDENCIES)
            self.assertEqual(family['main_prefix_validator']['sha256'], runtime.PREFIX_VALIDATOR_SHA)
            self.assertEqual(family['main_health_finalizer']['sha256'], runtime.FINALIZER_SHA)
            self.assertEqual(ready['leg_CPU_controller'], family['leg_CPU_controller'])
            self.assertNotEqual(ready['leg_CPU_controller'], ready['campaign_CPU_controller'])
            self.assertEqual(ready['leg_CPU_controller']['sha256'], 'f96b6a954834ed204a4c1207ea336ccc14f5b44242f853c7b61c0a8dad8128ff')
            cfg = read(pre['campaign_assessment_config'])
            self.assertEqual(cfg['argv'][3:5], [ready['campaign_assessor']['path'], '--execute'])
            load(ready['campaign_CPU_controller'], '_selected64_final660').checked_config(pre['campaign_assessment_config']['path'])
            proof = read(ready['quota64_validation']['native600_integration'])
            self.assertEqual(proof['status'], 'PASS_ORIGINAL_QUOTA64_REFERENCE600_ENGINEERING_NOT_QUALITY')
            self.assertEqual(proof['raw_samples'], 3033); self.assertEqual(proof['deep_samples'], 117)
            self.assertTrue(proof['private_resources_free']); self.assertTrue(proof['all32_original_ROM_and1200_prefix_pairs_verified'])
            self.assertTrue(proof['all_three_original_scopes_descriptors_resources_argv_pins_birth_absence_and_release_verified'])
            self.assertFalse(proof['quality_qualified'])
            native_job = read(proof['native_job']); native_family = read(native_job['source_family_manifest'])
            self.assertEqual(native_family['main_observer'], family['main_observer'])
            self.assertEqual(native_family['main_live_control'], family['main_live_control'])
            protocol = read(native_job['main_health_protocol'])
            self.assertEqual(protocol['health_job']['sources'], ready['main_health_sources'])
            self.assertEqual(ready['quota64_validation']['extended_review_capacity']['sha256'], renderer.CAPACITY_PROOF_SHA)
            capacity = read(ready['quota64_validation']['extended_review_capacity'])
            self.assertEqual(capacity['synthetic_resource_samples'], 112000)
            self.assertEqual(capacity['synthetic_prior_groups'], 8192)
            self.assertFalse(capacity['real_six_hour_health_proven'])

        def test_06_actual_preparer_builds_a_consistent_never_launched_R1_fixture(self):
            nonlocal fixture
            root = output / 'explicit-never-launched-preparer-fixture'; root.mkdir(mode=0o700)
            fixture_ready = dict(ready, campaign_directory=str(root))
            rp = h.put(root / 'fixture-readiness.json', fixture_ready)
            fixture = modules['leg_preparer'].prepare(rp, 'R1', h)
            prepared = read(fixture); jp = prepared['job']; data = read(jp)
            reviewer.validate_scope(data, jp, read(prepared['acceptance']), read(prepared['controller_config']))
            runtime.validate_job(data)
            config = read(prepared['independent_review_controller_config'])
            self.assertIn('RuntimeMaxSec=1980', config['properties']); self.assertEqual(config['observation_s'], 2040)
            load(ready['leg_CPU_controller'], '_selected64_leg1980').checked_config(prepared['independent_review_controller_config']['path'])
            review_job = read(prepared['review_job'])
            self.assertEqual(review_job['schema'], 'robotron-original-quota64-independent-leg-review-job-v1')
            self.assertEqual(review_job['sources']['games'], ready['games_auditor'])
            self.assertEqual(review_job['sources']['wire'], ready['wire_auditor'])
            self.assertEqual(review_job['sources']['main_prefix_validator'], family['main_prefix_validator'])
            self.assertEqual(read(data['main_health_protocol'])['health_job']['binding'], data['main_binding'])
            runtime.validate_main_health_contract(data,read(data['main_health_protocol']),family)
            self.assertFalse(Path(data['output']).exists())
            self.assertFalse(Path(read(prepared['controller_config'])['output']).exists())

        def test_07_renderer_rejects_old_candidate_and_changed_scientific_gates(self):
            templates = {key: h.checked(pin).read_text() for key, pin in family['source_templates'].items()}
            def reject(label, changed, reason):
                with self.assertRaisesRegex(ValueError, reason): renderer.render(templates, changed, ready['quality_pair']['sha256'])
                negatives.append(label)
            changed = copy.deepcopy(pair); changed['candidate']['policy']['sha256'] = renderer.FAILED_POLICY
            reject('failed-b66-policy', changed, 'Distinct later candidate')
            for key, floor in renderer.REF_CLOCKS.items():
                changed = copy.deepcopy(pair); changed['candidate']['saved_clocks'][key] = floor
                reject('old-clock-' + key, changed, 'four saved clocks')
            for key, value in [('expected_selected_games', 63), ('games_per_slot', 3),
                               ('minimum_complete_games_per_leg', 49), ('outer_start_horizon_s', 21541),
                               ('whole_cohort_timeout_from_enter_s', 21601), ('candidate_pooling_for_qualification', True)]:
                changed = copy.deepcopy(pair); changed[key] = value
                reject(key, changed, 'scientific gates')

        def test_08_initial_readiness_and_every_independent_selection_descriptor_agree(self):
            descriptor = reviewer.COHORT_SELECTION
            self.assertEqual(descriptor, modules['campaign_assessor'].COHORT_SELECTION)
            self.assertEqual(descriptor, load(ready['wire_auditor'], '_selected64_wire').COHORT_SELECTION)
            self.assertEqual(descriptor, load(ready['games_auditor'], '_selected64_games').COHORT_SELECTION)
            self.assertEqual(descriptor, load(ready['quota64_source_pins']['drain'], '_selected64_drain').COHORT_SELECTION)
            health = load(ready['main_health_sources']['full_health_engine'], '_selected64_health')
            health.dependencies(dict(sources=ready['main_health_sources'], initial_readiness_protocol=ready['initial_readiness_protocol']), h)
            source = h.checked(ready['campaign_assessor']).read_text()
            self.assertIn("leg['schema']=='robotron-original-quota64-independent-cohort-review-v1'", source)
            self.assertIn("cohort_selection=leg['cohort_selection']", source)

        def test_09_actual_scientific_directories_are_fresh_and_defaults_are_inert(self):
            root = Path(ready['campaign_directory'])
            for folder in base.FOLDERS: self.assertFalse((root / folder).exists())
            self.assertFalse((root / 'original-fresh-sequence-observer-original01-intent.json').exists())
            for key in ('runtime', 'leg_reviewer', 'campaign_assessor', 'leg_preparer', 'sequence'):
                result = subprocess.run(['/usr/bin/python3.12', '-I', '-B', family[key]['path']],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0); self.assertIn('PLAN_ONLY', result.stdout)
            with self.assertRaises((ValueError, KeyError)): runtime.validate_job(read(job['old_native_job']))
            negatives.append('old-failed-job-not-adopted')
            self.assertFalse(pre.get('existing_R1_adopted', False))

        def test_10_actual_selected_native_initialization_consumes_the_preparer_protocol(self):
            nonlocal selected_native_prefix
            prepared = read(fixture); jp = prepared['job']; data = read(jp)
            protocol = read(data['main_health_protocol'])
            runtime.validate_main_health_contract(data, protocol, family)
            wrong = dict(protocol, schema='robotron-native-dedicated-main-health-protocol-v5')
            with self.assertRaisesRegex(ValueError, 'Exact prospective main-health'):
                runtime.validate_main_health_contract(data, wrong, family)
            negatives.append('actual-selected-protocol-old-v5-rejected')
            class NoPrivateWork(Exception): pass
            called = []
            class Client:
                @staticmethod
                def DedicatedMainHealth(*args, **kwargs):
                    called.append(True)
                    raise NoPrivateWork('EXPLICIT_SELECTED_FAMILY_FIXTURE_STOP_BEFORE_WORKER_POLICY_TORCH_MAME')
            original_load = runtime.load
            def controlled_load(name, path):
                if name == '_compiled32_dedicated_main_health_client': return Client
                return original_load(name, path)
            try:
                runtime.load = controlled_load
                self.assertEqual(runtime.run(data, jp, h), 1)
            finally: runtime.load = original_load
            self.assertEqual(called, [True])
            selected_native_prefix = h.pin(Path(data['output']) / 'result.json')
            result = read(selected_native_prefix)
            self.assertEqual(result['errors'], ["NoPrivateWork('EXPLICIT_SELECTED_FAMILY_FIXTURE_STOP_BEFORE_WORKER_POLICY_TORCH_MAME')"])
            self.assertEqual(result['original_slots'], {}); self.assertEqual(result['main_samples'], [])
            self.assertIsNone(result['main_observer_lifecycle']); self.assertIsNone(result['policy_before'])
            self.assertTrue(result['original_lease_released']); self.assertTrue(result['immutable_inputs_unchanged'])
            self.assertNotIn('torch', sys.modules)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    for pin in ready['inputs']: h.checked(pin)
    assert 'torch' not in sys.modules
    report = dict(schema='robotron-selected-quota64-family-CPU-report-v1',
                  status='PASS_ACTUAL_SELECTED_QUOTA64_PROTOCOL_FAMILY_AND_PRE_WORKER_NATIVE_INITIALIZATION' if result.wasSuccessful() else 'FAIL_PRESERVED_NO_RETRY',
                  tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), negative_checks=negatives,
                  readiness=job['readiness'], sequence_precommit=job['sequence_precommit'], preparer_fixture=fixture,
                  selected_native_pre_worker_fixture=selected_native_prefix, actual_worker_policy_Torch_MAME_started=False,
                  scientific_case_started=False, quality_qualified=False, main_runtime_changed=False, created_unix_s=time.time())
    pin = h.put(output / 'report.json', report)
    print(json.dumps(dict(report=pin, passed=result.wasSuccessful())), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': raise SystemExit(main())
