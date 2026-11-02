"""Independent byte/AST scope checks; no services, models or numerical imports."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

H = Path(__file__).resolve().parent
G = H.parents[1]
P = G/'logs/managed-learning-20261015/run-26/quality32-fresh-candidate-5400-9000-protocol-proposal-20261019'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def functions(path):
    return {node.name: ast.dump(node) for node in ast.parse(path.read_bytes()).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


class SourceScopeTests(unittest.TestCase):
    def test_every_constructed_source_still_matches_exact_report(self):
        report = json.loads((P/'source-construction.json').read_bytes())
        self.assertEqual(len(report['source_hashes']), 133)
        for name, sha in report['source_hashes'].items():
            path = Path(name)
            self.assertEqual(digest(path.read_bytes()), sha, name)
            self.assertEqual(path.stat().st_nlink, 1, name)
            compile(path.read_bytes(), name, 'exec') if path.suffix == '.py' else None
        self.assertFalse(report['candidate_captured'])
        self.assertFalse(report['production_changed'])

    def test_only_declared_ceiling_and_copied_fixture_differ_in_123_runtime_sources(self):
        before = json.loads((H/'profile03/runtime-source-package.json').read_bytes())
        after = json.loads((H/'profile04/runtime-source-package.json').read_bytes())
        self.assertEqual(set(before['files']), set(after['files']))
        self.assertEqual(len(after['files']), 123)
        changed = []
        for relative, sha in before['files'].items():
            old = (Path(before['root'])/relative).read_bytes()
            new = (Path(after['root'])/relative).read_bytes()
            self.assertEqual(digest(old), sha)
            self.assertEqual(digest(new), after['files'][relative])
            if old != new:
                changed.append(relative)
                if relative == 'tools/run_frozen_sidecar.py':
                    self.assertEqual(old.count(b'7200'), 2)
                    self.assertEqual(new, old.replace(b'7200', b'9000'))
                elif relative == 'tools/test_frozen_sidecar.py':
                    self.assertEqual(new, old.replace(b'timeout_s=7200', b'timeout_s=9000')
                                     .replace(b'(3600,7201)', b'(3600,9001)'))
                else:
                    self.fail('Unexpected numerical/parser/ingestion/runtime change: '+relative)
        self.assertEqual(set(changed), {'tools/run_frozen_sidecar.py', 'tools/test_frozen_sidecar.py'})

    def test_all_helper_changes_equal_the_explicit_construction_transitions(self):
        report = json.loads((P/'source-construction.json').read_bytes())
        reader_path = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
        self.assertEqual(digest(reader_path.read_bytes()), 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
        spec = importlib.util.spec_from_file_location('_tail9000_scope_reader', reader_path)
        reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
        for name, value in report['transformed_sources'].items():
            old = reader.read_pin(value['parent'], as_json=False).decode()
            for change in value['replacements']:
                self.assertEqual(old.count(change['before']), change['occurrences'])
                old = old.replace(change['before'], change['after'])
            self.assertEqual((H/name).read_text(), old)

    def test_scientific_decision_evidence_and_publication_functions_unchanged(self):
        for old, new, names in [
            ('audit_quality32_evidence_v1.py', 'audit_quality32_evidence_v2.py', ['completed_cohort']),
            ('quality32_acquisition_v1.py', 'quality32_acquisition_v2.py', ['validate_snapshot', 'validate_CPU_authority']),
            ('review_closed_quality32_v5.py', 'review_closed_quality32_v6.py',
             ['decision', 'validate_records', 'validate_births', 'validate_main_binding']),
            ('quality32_runtime_guard_v4.py', 'quality32_runtime_guard_v5.py', ['live_process', 'validate_records']),
            ('protect_quality32_winner_v3.py', 'protect_quality32_winner_v4.py', None),
            ('monitor_supervised_quality32_v1.py', 'monitor_supervised_quality32_v2.py', None)]:
            before, after = functions(H/old), functions(H/new)
            self.assertEqual(set(before), set(after))
            for name in before if names is None else names:
                self.assertEqual(before[name], after[name], (old, new, name))

    def test_copied_fixtures_preserve_all_original_test_bodies_except_declared_transitions(self):
        report = json.loads((P/'test-fixture-construction.json').read_bytes())
        self.assertEqual(len(report['files']), 10)
        for value in report['files']:
            raw = Path(value['parent']).read_bytes()
            self.assertEqual(digest(raw), value['parent_sha256'])
            text = raw.decode()
            for before, after in value['exact_transitions']:
                self.assertIn(before, text)
                text = text.replace(before, after)
            new = Path(value['target']).read_bytes()
            self.assertEqual(text.encode(), new)
            self.assertEqual(digest(new), value['target_sha256'])
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('numpy', sys.modules)


if __name__ == '__main__':
    unittest.main()

