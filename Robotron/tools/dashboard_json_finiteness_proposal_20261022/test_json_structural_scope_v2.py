"""New exact-scope structural guard; does not rerun the prior functional tests."""
import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parent
SOURCE = P.parents[1]/'Scripts/dqn/metrics_dashboard.py'
CANDIDATE = P/'metrics_dashboard_candidate_v1.py'


class DashboardJSONStructuralScopeV2(unittest.TestCase):
    def test_exact_declared_candidate_and_HTML_literal_change_preserve_all_other_Python_logic(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            '3d1aa1950e6b1c5224ace3aecb9c837e433e5c36941b89465b414749f903da27')
        self.assertEqual(hashlib.sha256(CANDIDATE.read_bytes()).hexdigest(),
            '33c9726addb57ea5e8b7b5087c2e75aa179f4035542f5a91bbe3dffdf273d30c')
        spec = importlib.util.spec_from_file_location('_declared_JSON_candidate_builder', P/'prepare_candidate_v1.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        self.assertEqual(builder.build(SOURCE.read_text()), CANDIDATE.read_text())

        def functions(path):
            return {node.name:node for node in ast.walk(ast.parse(path.read_text()))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        old, new = functions(SOURCE), functions(CANDIDATE)
        self.assertEqual(set(new)-set(old), {'_json_safe_diagnostic_snapshot'})
        self.assertEqual(set(old)-set(new), set())
        for name in old:
            if name == 'sample':
                continue  # Actual sampler paths covered by the five retained functional/JS checks.
            a, b = copy.deepcopy(old[name]), copy.deepcopy(new[name])
            if name == '_render_dashboard_html':
                for node in [a, b]:
                    literals = [part for part in ast.walk(node) if isinstance(part, ast.Constant)
                        and isinstance(part.value, str) and len(part.value)>10000
                        and 'function fmtPaddedFloat(' in part.value]
                    self.assertEqual(len(literals), 1)
                    # Exact HTML contents are bound above by the declared builder and full candidate SHA.
                    literals[0].value = '<EXACT_DECLARED_HTML_LITERAL>'
            self.assertEqual(ast.dump(a, include_attributes=False), ast.dump(b, include_attributes=False), name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
