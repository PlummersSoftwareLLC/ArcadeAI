"""Bounded display guards; temporary fixtures and historical read-only evidence."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


def load(pin, name):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def suite(job, display, old_display, renderer):
    class Guards(unittest.TestCase):
        def setUp(self):
            self.temporary = tempfile.TemporaryDirectory(prefix='bounded-display-')
            self.addCleanup(self.temporary.cleanup)
            self.root = Path(self.temporary.name)

        def pin(self, path):
            return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        bytes=path.stat().st_size, identity=display.projection_metadata(path))

        def write(self, path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                # Only this method's isolated synthetic files can be changed.
                self.assertTrue(path.is_relative_to(self.root))
                path.chmod(0o600)
            path.write_text(json.dumps(value, allow_nan=False) + '\n')
            path.chmod(0o444)
            return self.pin(path)

        def fixture(self, *, qualified=True, controller_exit=0, release=True, status='ORIGINAL_FOUR_LEG_CAMPAIGN_COMPLETE'):
            pre = self.write(self.root / 'original-fresh-sequence-precommit.json',
                dict(schema='robotron-fresh-LR125-quality32-sequence-precommit-v1'))
            closure = self.write(self.root / 'campaign-assessment-execution-original01/root-original-result-and-owned-release.json',
                dict(original_exit=0, lifecycle_complete=True, unit_released=release))
            result = self.write(self.root / 'campaign-assessment-controller-original-result.json',
                dict(actual_exit=controller_exit, closure=closure))
            report = self.root / 'independent-campaign-assessment-original01/assessment.json'
            report.parent.mkdir()
            with report.open('xb') as stream:
                stream.truncate(17 << 20)
                os.fchmod(stream.fileno(), 0o444)
            outcome = dict(schema='robotron-original-certified-quality32-sequence-outcome-v1',
                precommit=pre, original_attempts_per_leg=1, no_retries=True,
                existing_R1_adopted=False, quality_qualified=qualified, status=status,
                campaign_assessment=dict(result=result, closure=closure), assessment_report=self.pin(report))
            self.outcome_path = self.root / 'original-fresh-sequence-observer-original01-outcome.json'
            self.write(self.outcome_path, outcome)
            return outcome

        def guarded_projection(self, root=None):
            root = root or self.root
            original = Path.read_bytes
            report = root / 'independent-campaign-assessment-original01/assessment.json'
            def guarded(path):
                self.assertNotEqual(path, report, 'Display opened the large assessment contents')
                return original(path)
            with patch.object(Path, 'read_bytes', guarded):
                return display.project_campaign(root)

        def test_01_actual_historical_158MB_campaign_finishes_without_opening_report(self):
            root = Path(job['historical_campaign'])
            report = root / 'independent-campaign-assessment-original01/assessment.json'
            self.assertGreater(report.stat().st_size, 150 << 20)
            original = Path.read_bytes
            def guarded(path):
                self.assertNotEqual(path, report)
                return original(path)
            with patch.object(Path, 'read_bytes', guarded):
                self.assertEqual(old_display.read(report), {})
                self.assertEqual(display.project_campaign(root), dict(state='finished', outcome='qualified', reason=None))

        def test_02_qualified_sparse_oversized_assessment_projects_without_open(self):
            self.fixture()
            self.assertEqual(self.guarded_projection(), dict(state='finished', outcome='qualified', reason=None))

        def test_03_valid_not_improved_is_distinct_from_qualified(self):
            self.fixture(qualified=False)
            self.assertEqual(self.guarded_projection(), dict(state='finished', outcome='not_improved', reason=None))

        def test_04_missing_original_outcome_remains_pending(self):
            self.assertIsNone(self.guarded_projection())

        def test_05_nonboolean_quality_flag_rejected(self):
            self.fixture(qualified=1)
            self.assertIsNone(self.guarded_projection())

        def test_06_failed_final_controller_cannot_finish(self):
            self.fixture(controller_exit=1)
            self.assertIsNone(self.guarded_projection())

        def test_07_unreleased_original_scope_cannot_finish(self):
            self.fixture(release=False)
            self.assertIsNone(self.guarded_projection())

        def test_08_different_original_closure_binding_rejected(self):
            outcome = self.fixture()
            outcome['campaign_assessment']['closure']['sha256'] = 'e' * 64
            self.write(self.outcome_path, outcome)
            self.assertIsNone(self.guarded_projection())

        def test_09_changed_original_precommit_rejected(self):
            self.fixture()
            self.write(self.root / 'original-fresh-sequence-precommit.json', dict(schema='changed'))
            self.assertIsNone(self.guarded_projection())

        def test_10_wrong_report_path_rejected(self):
            outcome = self.fixture()
            outcome['assessment_report']['path'] = str(self.root / 'foreign-report.json')
            self.write(self.outcome_path, outcome)
            self.assertIsNone(self.guarded_projection())

        def test_11_report_identity_change_rejected_without_reading_contents(self):
            self.fixture()
            report = self.root / 'independent-campaign-assessment-original01/assessment.json'
            report.chmod(0o600)
            report.chmod(0o444)
            self.assertIsNone(self.guarded_projection())

        def test_12_oversized_sequence_summary_rejected_before_open(self):
            self.fixture()
            self.outcome_path.chmod(0o600)
            with self.outcome_path.open('wb') as stream:
                stream.truncate(display.PROJECTION_MAX_BYTES + 1)
            self.outcome_path.chmod(0o444)
            original = Path.read_bytes
            def guarded(path):
                self.assertNotEqual(path, self.outcome_path)
                return original(path)
            with patch.object(Path, 'read_bytes', guarded):
                self.assertIsNone(display.project_campaign(self.root))

        def test_13_original_failed_sequence_projects_invalid(self):
            self.fixture(qualified=False, status='ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY')
            self.assertEqual(self.guarded_projection()['state'], 'failed')
            self.assertEqual(self.guarded_projection()['outcome'], 'invalid')

        def test_14_small_receipt_digest_mismatch_rejected(self):
            outcome = self.fixture()
            outcome['campaign_assessment']['result']['sha256'] = 'e' * 64
            self.write(self.outcome_path, outcome)
            self.assertIsNone(self.guarded_projection())

        def test_15_actual_rendered_family_only_display_and_renderer_bindings_changed(self):
            original = json.loads(Path(job['original_family']['path']).read_text())
            family = json.loads(Path(job['family']['path']).read_text())
            templates = {k: Path(v['path']).read_text() for k, v in family['source_templates'].items()}
            pair = json.loads(Path(family['quality_pair']['path']).read_text())
            rendered = renderer.render(templates, pair, family['quality_pair']['sha256'])
            for key, item in rendered.items():
                self.assertEqual(family[key]['path'], item['path'])
                self.assertEqual(family[key]['sha256'], item['sha256'])
                self.assertEqual(Path(family[key]['path']).read_text(), item['source'])
                if key != 'display_source':
                    self.assertEqual(family[key], original[key])
            def definitions(pin):
                return {n.name: ast.dump(n) for n in ast.parse(Path(pin['path']).read_text()).body
                        if isinstance(n, ast.FunctionDef)}
            before, after = definitions(original['display_source']), definitions(family['display_source'])
            for name in before:
                if name != 'main':
                    self.assertEqual(before[name], after[name], name)
            self.assertEqual(family['quality_pair'], original['quality_pair'])

        def test_16_actual_display_loop_finishes_and_clears_current_leg(self):
            self.fixture()
            self.write(self.root / 'pair.json', {role: dict(saved_clocks=dict(learner_frame_count=10))
                                                for role in ('reference', 'candidate')})
            ready = self.write(self.root / 'new-original-quality-launch-readiness.json',
                dict(campaign_directory=str(self.root), quality_pair=dict(path=str(self.root / 'pair.json')),
                     display_source=dict(sha256=job['display']['sha256'])))
            (self.root / 'display').mkdir()
            with patch.object(sys, 'argv', ['display', '--run', '--campaign', str(self.root), '--readiness-sha256', ready['sha256']]), \
                 patch.object(display, 'project', side_effect=lambda root, index: dict(index=index + 1, state='finished')):
                self.assertEqual(display.main(), 0)
            status = json.loads((self.root / 'status.json').read_text())
            self.assertEqual((status['state'], status['outcome'], status['current_leg']), ('finished', 'qualified', None))
    return unittest.defaultTestLoader.loadTestsFromTestCase(Guards)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-guards', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256')
    args = parser.parse_args()
    if not args.run_guards:
        print('PLAN_ONLY'); return 0
    assert hashlib.sha256(args.job.read_bytes()).hexdigest() == args.expected_job_sha256
    job = json.loads(args.job.read_text())
    assert job['schema'] == 'robotron-bounded-display-guards-job-v1'
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == job['runner_sha256']
    display = load(job['display'], '_bounded_display')
    old = load(job['old_display'], '_old_display')
    renderer = load(job['renderer'], '_bounded_renderer')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite(job, display, old, renderer))
    passed = result.wasSuccessful() and result.testsRun == 16 and not result.skipped
    assert 'torch' not in sys.modules
    value = dict(schema='robotron-bounded-display-guards-result-v1', passed=passed,
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        log=stream.getvalue(), job=job, historical_campaign_read_only=True,
        large_assessment_contents_not_opened_by_display=True, no_Torch_or_native_worker_started=True,
        scientific_runtime_or_quality_gates_changed=False)
    with Path(job['report']).open('x') as output:
        json.dump(value, output, indent=2, allow_nan=False); output.write('\n')
        output.flush(); os.fchmod(output.fileno(), 0o444); os.fsync(output.fileno())
    print(json.dumps(dict(passed=passed, tests=result.testsRun, report=job['report'])))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
