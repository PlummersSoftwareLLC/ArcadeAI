"""CPU-only synthetic contract guards; never policy or quality evidence."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job'); parser.add_argument('--job-sha256'); parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY'); return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw = Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job = json.loads(raw)
    assert job['schema'] == 'robotron-quota64-scientific-contract-guards-CPU-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''

    def load(name, pin):
        path = Path(pin['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        spec.loader.exec_module(module); return module

    h = load('_quota64_contract_h', job['helpers'])
    for pin in job['inputs']: h.checked(pin)
    modules = {name: load('_quota64_contract_' + name, pin) for name, pin in job['subjects'].items()}
    assess = modules['assessor']; runtime = modules['runtime']; reviewer = modules['reviewer']
    rejected = []

    def legs(candidate1=1050, candidate2=1050):
        result = []
        for number, role in enumerate(assess.ORDER):
            value = 1000 if role.startswith('R') else candidate1 if role == 'C1' else candidate2
            values = value if isinstance(value, list) else [value] * 64
            assert len(values) == 64
            rows = [dict(journal_game_id=f'explicit-synthetic-{role}-{index}',
                         client_slot=4096 + index // 2, score=score, complete=True,
                         eligible=True, known_start=True, excluded_reason='')
                    for index, score in enumerate(values)]
            cohort = dict(assess.metrics(values), closed=True, complete=True, valid=True,
                          pending=0, abandoned=0, pending_ids=[], abandoned_ids=[],
                          started=64, started_ids=[row['journal_game_id'] for row in rows],
                          rows=rows, closed_by='slot_quota', started_actor_slots=list(assess.SLOTS),
                          slot_admitted_counts={str(slot): 2 for slot in assess.SLOTS})
            result.append(dict(role=role, cohort=cohort, cohort_selection=copy.deepcopy(assess.COHORT_SELECTION),
                               policy_sha256=('a' if role.startswith('R') else 'b') * 64,
                               evidence_verified=True, original_attempt=1, no_retry=True,
                               native_identity=[1000 + number, 2000 + number, f'synthetic-native-{role}'],
                               review_identity=[3000 + number, 4000 + number, f'synthetic-review-{role}']))
        return result

    def decide(rows): return assess.assess_validated_cohorts(rows, 'a' * 64, 'b' * 64)

    class Contracts(unittest.TestCase):
        def reject(self, label, rows, reason):
            with self.assertRaisesRegex(ValueError, reason): decide(rows)
            rejected.append(label)

        def test_01_exact_five_percent_each_confirmation_passes(self):
            result = decide(legs())
            self.assertTrue(result['all_candidate_gates_passed'])
            self.assertFalse(result['candidate_pool_used'])
            self.assertEqual(result['fixed_fresh_reference']['count'], 128)
            self.assertEqual(result['minimum_complete_games_per_leg'], 50)

        def test_02_huge_C1_cannot_rescue_C2_below_five_percent(self):
            result = decide(legs(1000000, 1049))
            self.assertTrue(result['independent_candidates']['C1']['passed'])
            self.assertFalse(result['independent_candidates']['C2']['mean_at_least_105_percent'])
            self.assertFalse(result['all_candidate_gates_passed'])

        def test_03_higher_mean_cannot_rescue_a_lower_median(self):
            result = decide(legs(1050, [900] * 33 + [3000] * 31))
            candidate = result['independent_candidates']['C2']
            self.assertTrue(candidate['mean_at_least_105_percent'])
            self.assertFalse(candidate['median_preserved'])
            self.assertFalse(result['all_candidate_gates_passed'])

        def test_04_zero_scores_are_retained_in_the_denominator(self):
            rows = legs()
            for leg in rows:
                scores = [0] * 16 + ([1000] * 48 if leg['role'].startswith('R') else [1050] * 48)
                for row, score in zip(leg['cohort']['rows'], scores): row['score'] = score
                leg['cohort'].update(assess.metrics(scores))
            result = decide(rows)
            self.assertTrue(result['all_candidate_gates_passed'])
            self.assertEqual(result['fixed_fresh_reference']['count'], 128)
            self.assertEqual(result['fixed_fresh_reference']['mean'], 750)

        def test_05_missing_tail_abandonment_and_ineligibility_reject(self):
            for field, value in [('pending', 1), ('abandoned', 1), ('complete', False), ('valid', False)]:
                rows = legs(); rows[1]['cohort'][field] = value
                self.reject(field, rows, 'Each original full tail')
            for field, value in [('complete', False), ('eligible', False), ('known_start', False), ('excluded_reason', 'partial')]:
                rows = legs(); rows[1]['cohort']['rows'][0][field] = value
                self.reject('row-' + field, rows, 'incomplete/excluded')

        def test_06_fifty_games_do_not_replace_the_precommitted_sixty_four(self):
            rows = legs(); cohort = rows[1]['cohort']
            cohort['rows'] = cohort['rows'][:50]; cohort['started_ids'] = cohort['started_ids'][:50]
            cohort.update(count=50, started=50)
            self.reject('fifty-not-sixty-four', rows, 'denominator')

        def test_07_all_slot_coverage_alone_cannot_hide_one_and_three(self):
            rows = legs(); rows[1]['cohort']['rows'][0]['client_slot'] = 4097
            self.reject('one-three-slot-denominator', rows, 'exactly its two')
            rows = legs(); rows[1]['cohort']['slot_admitted_counts']['4096'] = 3
            self.reject('false-per-slot-count', rows, 'denominator')

        def test_08_changed_selection_or_timeout_closure_rejects(self):
            for field, value in [('games_per_slot', 3), ('minimum_complete_games', 49),
                                 ('strategy', 'best_two'), ('whole_cohort_timeout_from_enter_s', 21601)]:
                rows = legs(); rows[1]['cohort_selection'][field] = value
                self.reject(field, rows, 'selection strategy/bounds')
            rows = legs(); rows[1]['cohort']['closed_by'] = 'outer_timeout'
            self.reject('timeout-closure', rows, 'denominator')

        def test_09_reused_games_processes_and_retry_reject(self):
            rows = legs(); original = rows[0]['cohort']['started_ids'][0]
            rows[1]['cohort']['started_ids'][0] = original
            rows[1]['cohort']['rows'][0]['journal_game_id'] = original
            self.reject('reused-game', rows, 'reused across')
            for field in ('native_identity', 'review_identity'):
                rows = legs(); rows[1][field] = rows[0][field]
                self.reject(field, rows, 'identity reused')
            rows = legs(); rows[1]['original_attempt'] = 2
            self.reject('retry', rows, 'independent actual runtime/review evidence')

        def test_10_changed_policy_statistics_and_cohort_order_reject(self):
            rows = legs(); rows[1]['policy_sha256'] = 'c' * 64
            self.reject('policy', rows, 'policy role changed')
            rows = legs(); rows[1]['cohort']['mean'] += 1
            self.reject('statistics', rows, 'statistics differ')
            rows = legs(); rows[1], rows[2] = rows[2], rows[1]
            self.reject('order', rows, 'R1/C1/R2/C2 order')

        def test_11_unbound_runtime_and_reviewer_fail_before_scientific_actions(self):
            with self.assertRaisesRegex(ValueError, 'UNBOUND template'): runtime.validate_job({})
            with self.assertRaisesRegex(ValueError, 'UNBOUND reviewer'): reviewer.validate_scope({}, {}, {}, {})
            self.assertEqual(modules['preparer'].PAIR_SHA, '0' * 64)
            self.assertEqual(modules['sequence'].PAIR_SHA, '0' * 64)
            self.assertEqual(assess.PAIR_SHA, '0' * 64)

        def test_12_all_independent_components_agree_on_the_same_selection(self):
            self.assertEqual(reviewer.COHORT_SELECTION, assess.COHORT_SELECTION)
            self.assertEqual(modules['wire'].COHORT_SELECTION, assess.COHORT_SELECTION)
            self.assertEqual(modules['games'].COHORT_SELECTION, assess.COHORT_SELECTION)
            self.assertEqual(modules['drain'].COHORT_SELECTION, assess.COHORT_SELECTION)

        def test_14_controller_requires_the_precommitted_resources_and_runtime(self):
            with tempfile.TemporaryDirectory(prefix='explicit-synthetic-controller-', dir=Path(args.job).parent) as folder:
                folder = Path(folder); job_path = str(folder / 'job.json')
                selected = str(reviewer.SELECTED_RUNTIME)
                config = dict(unit='robotron-compiled-full-tail32-integration-explicit-synthetic.service',
                              output=str(folder / 'never-launched'), observation_s=22320,
                              properties=reviewer.PROPERTIES[:],
                              argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-I', '-B',
                                    selected, '--execute', '--job', job_path, '--job-sha256', 'a' * 64,
                                    '--source-sha256', 'b' * 64],
                              pins=[dict(path=job_path, sha256='a' * 64), dict(path=selected, sha256='b' * 64)])
                path = folder / 'synthetic-controller-config.json'
                path.write_text(json.dumps(config))
                self.assertEqual(modules['native_controller'].checked_config(path), config)
                for field, value, reason in [('properties', [p.replace('22260', '22261') for p in config['properties']], 'resources'),
                                             ('observation_s', 22321, 'observation'),
                                             ('argv', config['argv'][:4] + ['/wrong/runtime.py'] + config['argv'][5:], 'argv')]:
                    changed = copy.deepcopy(config); changed[field] = value; path.write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError, reason): modules['native_controller'].checked_config(path)
                    rejected.append('controller-' + field)

        def test_15_only_append_only_outside_membership_is_allowed(self):
            saved = dict(started_ids=['selected'], count=64, retained_outside_cohort_ids=['outside1'])
            fresh = dict(saved, retained_outside_cohort_ids=['outside1', 'outside2'])
            self.assertTrue(reviewer.same_completed_membership(saved, fresh))
            for changed in [dict(fresh, count=63), dict(fresh, retained_outside_cohort_ids=['outside2', 'outside1']),
                            dict(fresh, retained_outside_cohort_ids=['outside1', 'selected']),
                            dict(fresh, retained_outside_cohort_ids=['outside1', 'outside1'])]:
                self.assertFalse(reviewer.same_completed_membership(saved, changed))

        def test_16_synthetic_binding_accepts_exact_bounds_and_rejects_relaxations(self):
            original = (runtime.PAIR_SHA, runtime.CAPACITY_PROOF_SHA, copy.deepcopy(runtime.POLICIES))
            try:
                runtime.PAIR_SHA = 'a' * 64
                runtime.CAPACITY_PROOF_SHA = job['capacity_proof']['sha256']
                clocks = {key: value + 1 for key, value in runtime.NEW_CANDIDATE_CLOCK_FLOOR.items()}
                runtime.POLICIES['candidate'] = dict(sha256='b' * 64, clocks=clocks)
                fixture = json.loads(h.checked(job['shape_fixture']).read_bytes())
                fixture.update(schema='robotron-compiled-quota64-quality-original-v1', quality_leg='C1',
                               quality_pair_precommit=dict(sha256=runtime.PAIR_SHA),
                               expected_policy_clocks=clocks.copy(),
                               checkpoint=dict(fixture['checkpoint'], sha256='b' * 64),
                               admission_s=21540, whole_cohort_timeout_s=21600, wall_limit_s=22200,
                               quota64_validation=job['validation_proofs'], quota64_source_pins=job['component_pins'],
                               output=str(Path(args.job).parent / 'never-created-scientific-output'))
                runtime.validate_job(fixture)
                for field, value, reason in [('admission_s', 21541, 'compiled32 original scope'),
                                             ('whole_cohort_timeout_s', 21601, 'compiled32 original scope'),
                                             ('wall_limit_s', 22201, 'compiled32 original scope'),
                                             ('admission_s', 21540.0, 'Typed fixed'),
                                             ('actor_slots', list(runtime.SLOTS[:-1]), 'compiled32 original scope'),
                                             ('minimum_completed_games', 49, 'minimum50')]:
                    changed = copy.deepcopy(fixture); changed[field] = value
                    with self.assertRaisesRegex(ValueError, reason): runtime.validate_job(changed)
                    rejected.append('runtime-' + field + '-' + str(value))
                for key, floor in runtime.NEW_CANDIDATE_CLOCK_FLOOR.items():
                    runtime.POLICIES['candidate']['clocks'][key] = floor
                    with self.assertRaisesRegex(ValueError, 'UNBOUND template'): runtime.validate_job(fixture)
                    runtime.POLICIES['candidate']['clocks'][key] = floor + 1
                    rejected.append('candidate-clock-' + key)
                self.assertFalse(Path(fixture['output']).exists())
            finally:
                runtime.PAIR_SHA, runtime.CAPACITY_PROOF_SHA, runtime.POLICIES = original

        def test_13_original_numerical_gates_and_metrics_are_unchanged(self):
            original = ast.parse(h.checked(job['original_assessor']).read_text())
            current = ast.parse(h.checked(job['subjects']['assessor']).read_text())
            def function(tree, name): return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
            self.assertEqual(ast.dump(function(original, 'metrics')), ast.dump(function(current, 'metrics')))
            def tail(tree):
                body = function(tree, 'assess_validated_cohorts').body
                index = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                             and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'reference')
                return [ast.dump(node) for node in body[index:]]
            self.assertEqual(tail(original), tail(current))

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    output = Path(job['output']); output.mkdir(mode=0o700)
    report = h.put(output / 'report.json', dict(
        status='PASS_SYNTHETIC_QUOTA64_SCIENTIFIC_CONTRACTS' if result.wasSuccessful() else 'FAIL_PRESERVED_NO_RETRY',
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        targeted_rejections=rejected, sources=job['subjects'], inputs_unchanged=True,
        synthetic_fixtures_only=True, actual_scientific_launch=False, quality_qualified=False,
        created_unix_s=time.time()))
    for pin in job['inputs']: h.checked(pin)
    print(json.dumps(dict(report=report, passed=result.wasSuccessful())), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': raise SystemExit(main())
