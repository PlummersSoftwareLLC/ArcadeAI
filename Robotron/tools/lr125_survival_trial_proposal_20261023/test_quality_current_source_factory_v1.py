"""Prospective CPU contracts using declared synthetic endpoint bindings only.

No actual endpoint, job publication, model, GPU, game or scientific review is
created. The new binding must preserve every existing scientific predicate.
"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import tempfile
from types import ModuleType
import unittest

P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_lr125_factory', P / 'quality_current_source_factory_v1.py')
factory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(factory)


def binding():
    return copy.deepcopy(factory.FIXED_BINDING)


def definitions(raw):
    return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(raw).body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


class QualitySourceContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bound = binding()
        self.files, self.manifest = factory.render(self.bound)
        self.modules = {}
        for role, raw in self.files.items():
            module = ModuleType('_synthetic_lr125_' + role)
            module.__file__ = str(factory.B / factory.NEW[role])
            exec(compile(raw, module.__file__, 'exec'), module.__dict__)
            self.modules[role] = module

    def fixture(self, leg):
        old = factory.G / 'logs/managed-learning-20261015/run-26/quality32-protected1741-vs-normal2259-after-JSON-original01-preparation-20261022/native-current197-job-template.json'
        job = json.loads(old.read_text())
        runtime = self.modules['runtime']
        policy = runtime.POLICIES[runtime.ROLES[leg]]
        job.update(schema='robotron-compiled-full-tail32-quality-original-v1', quality_leg=leg,
            quality_pair_precommit={'sha256': self.bound['pair_sha256']}, minimum_completed_games=50,
            expected_policy_clocks=copy.deepcopy(policy['clocks']), admission_s=5400,
            output=str(Path(self.temp.name) / 'never-created-native-output'))
        job['checkpoint']['sha256'] = policy['sha256']
        job['main_sources']['window']['sha256'] = factory.NEW_WINDOW
        return job

    def test_all_five_sources_reverse_exactly_without_publication(self):
        self.assertFalse(self.manifest['publication_performed'])
        for role, raw in self.files.items():
            for item in reversed(self.manifest['entries'][role]['literal_replacements']):
                raw = raw.replace(item['effective'].encode(), item['original'].encode())
            self.assertEqual(raw, (factory.B / factory.OLD[role][0]).read_bytes())
        self.assertEqual(self.modules['reviewer'].RUNTIME_SHA,
                         self.manifest['entries']['runtime']['effective_sha256'])

    def test_only_declared_metadata_functions_change(self):
        expected = dict(runtime=['validate_job'], controller=['checked_config'],
                        reviewer=['validate_scope'], preparer=['prepare'], assessor=['execute'])
        for role, raw in self.files.items():
            old = definitions((factory.B / factory.OLD[role][0]).read_bytes())
            new = definitions(raw)
            self.assertEqual(old.keys(), new.keys())
            self.assertEqual([name for name in old if old[name] != new[name]], expected[role])

    def test_reject_old_pair_candidate_clocks_reference_types_and_LR25_health(self):
        cases = []
        bad = binding(); bad['pair_sha256'] = factory.OLD_PAIR; cases.append(bad)
        bad = binding(); bad['main_window_sha256'] = factory.OLD_WINDOW; cases.append(bad)
        bad = binding(); bad['candidate']['sha256'] = factory.REFERENCE['sha256']; cases.append(bad)
        bad = binding(); bad['candidate']['sha256'] = 'c97f7d82118c6d743d3ce9649a709ef49f93946e349f55c5e9ab47339a27af9b'; cases.append(bad)
        bad = binding(); bad['candidate']['clocks']['learner_frame_count'] = 2_432_273_305; cases.append(bad)
        bad = binding(); bad['candidate']['clocks']['training_steps'] = 9_730_000.; cases.append(bad)
        bad = binding(); bad['reference']['clocks']['training_steps'] = 7_128_160.; cases.append(bad)
        bad = binding(); bad['candidate'] = None; cases.append(bad)
        for bad in cases:
            with self.assertRaises(ValueError):
                factory.render(bad)

    def test_each_new_role_accepts_only_its_fixed_policy_and_clocks(self):
        runtime = self.modules['runtime']
        for leg in ('R1', 'C1', 'R2', 'C2'):
            job = self.fixture(leg)
            self.assertEqual(runtime.validate_job(job), Path(job['output']))
            other = 'candidate' if runtime.ROLES[leg] == 'reference' else 'reference'
            bad = copy.deepcopy(job); bad['checkpoint']['sha256'] = runtime.POLICIES[other]['sha256']
            with self.assertRaises(ValueError):
                runtime.validate_job(bad)
            bad = copy.deepcopy(job); bad['expected_policy_clocks'] = runtime.POLICIES[other]['clocks']
            with self.assertRaises(ValueError):
                runtime.validate_job(bad)

    def test_fixed_minimum_admission_tail_and_new_main_health_are_required(self):
        runtime = self.modules['runtime']
        for key, values in [('minimum_completed_games', (49, 51, 50., True)),
                            ('admission_s', (5399, 5401, 5400.)),
                            ('whole_cohort_timeout_s', (8999, 9001)),
                            ('wall_limit_s', (9599, 9601))]:
            for value in values:
                job = self.fixture('C1'); job[key] = value
                with self.assertRaises(ValueError):
                    runtime.validate_job(job)
        job = self.fixture('C1'); job['main_sources']['window']['sha256'] = factory.OLD_WINDOW
        with self.assertRaises(ValueError):
            runtime.validate_job(job)

    def test_future_controller_keeps_exact_resources_and_requires_new_runtime_path(self):
        runtime = str(factory.B / factory.NEW['runtime'])
        future = factory.G / 'logs/managed-learning-20261015/run-26/never-launched-LR125-fixture/job.json'
        cfg = dict(unit='robotron-compiled-full-tail32-integration-lr125-fixture.service',
            output=str(Path(self.temp.name) / 'never-created-controller-output'),
            argv=['/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python', '-Xgil=0', '-I', '-B', runtime,
                  '--execute', '--job', str(future), '--job-sha256', '1' * 64, '--source-sha256', '2' * 64],
            properties=self.modules['reviewer'].PROPERTIES,
            pins=[dict(path=str(future), sha256='1' * 64), dict(path=runtime, sha256='2' * 64)],
            observation_s=9720)
        path = Path(self.temp.name) / 'config.json'; path.write_text(json.dumps(cfg))
        self.assertEqual(self.modules['controller'].checked_config(path), cfg)
        bad = copy.deepcopy(cfg); bad['argv'][4] = str(factory.B / factory.OLD['runtime'][0])
        path.write_text(json.dumps(bad))
        with self.assertRaises(ValueError):
            self.modules['controller'].checked_config(path)
        bad = copy.deepcopy(cfg); bad['properties'][-1] = 'SendSIGKILL=yes'
        path.write_text(json.dumps(bad))
        with self.assertRaises(ValueError):
            self.modules['controller'].checked_config(path)

    def test_new_units_dates_and_uniform_original_R1_review_configuration(self):
        prep = self.files['preparer'].decode()
        self.assertNotIn('quality1741-2259-json-', prep)
        self.assertNotIn('original01-20261022', prep)
        self.assertIn('quality1741-currentlr125-firstsave-', prep)
        self.assertIn('quality32-currentlr125-firstsave-', prep)
        assessor = self.files['assessor'].decode()
        self.assertNotIn('independent-review-controller-config-prospective197-original01.json', assessor)
        self.assertIn("cpucfg_name='independent-review-controller-config.json'", assessor)

    def test_separate_candidate_gates_cannot_be_rescued_by_other_candidate(self):
        assessor = self.modules['assessor']
        legs = []
        for index, role in enumerate(('R1', 'C1', 'R2', 'C2')):
            score = 104 if role == 'C1' else 200 if role == 'C2' else 100
            rows = [dict(journal_game_id=f'synthetic-{role}-{i}', client_slot=4096 + i % 32,
                score=score, complete=True, eligible=True, known_start=True, excluded_reason='') for i in range(50)]
            cohort = dict(closed=True, complete=True, valid=True, pending=0, abandoned=0,
                pending_ids=[], abandoned_ids=[], rows=rows,
                started_ids=[r['journal_game_id'] for r in rows], count=50, started=50,
                started_actor_slots=list(range(4096, 4128)), mean=score, median=score, sd=0., se=0.)
            legs.append(dict(role=role, evidence_verified=True, original_attempt=1, no_retry=True,
                policy_sha256=self.bound['reference' if role.startswith('R') else 'candidate']['sha256'],
                native_identity=(100 + index, 1000 + index), review_identity=(200 + index, 2000 + index),
                cohort=cohort))
        result = assessor.assess_validated_cohorts(legs, self.bound['reference']['sha256'],
                                                  self.bound['candidate']['sha256'])
        self.assertFalse(result['all_candidate_gates_passed'])
        self.assertFalse(result['independent_candidates']['C1']['passed'])
        self.assertTrue(result['independent_candidates']['C2']['passed'])
        self.assertFalse(result['candidate_pool_used'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
