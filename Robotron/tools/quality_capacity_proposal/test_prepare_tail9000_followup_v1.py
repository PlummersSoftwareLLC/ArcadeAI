"""Preserved preparation body and inert/refusal paths; no actual capture or launch."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import prepare_tail9000_followup_v1 as prepare


class FollowupTests(unittest.TestCase):
    def test_original_CPU_and_campaign_preparation_body_preserved_except_selected_versions(self):
        path = prepare.G/'logs/managed-learning-20261015/run-26/post-supervised-main-next8M-original01-preparation-20261019/prepare-followup.py'
        old = path.read_text()
        self.assertEqual(hashlib.sha256(old.encode()).hexdigest(), '126fed38bd144858f54cd18bb386009a7b9c1754430716bd89c3f800e48c08e2')
        old = old.replace("['prepare_quality32_candidate_CPU_v2.py']", "['prepare_quality32_candidate_CPU_v3.py']")
        old = old.replace("['prepare_quality32_campaign_v3.py']", "['prepare_quality32_campaign_v4.py']")
        def body(source):
            function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'run')
            index = next(i for i, n in enumerate(function.body) if isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'window')
            return ast.dump(ast.Module(body=function.body[index:], type_ignores=[]))
        self.assertEqual(body(old), body(Path(prepare.__file__).read_text()))

    def test_default_CLI_is_inert_even_with_missing_precommit(self):
        result = subprocess.run([sys.executable, '-I', '-B', prepare.__file__, '--step', 'CPU',
            '--precommit', '/missing/tested-followup-precommit.json'], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith('PLAN_ONLY:'))
        self.assertEqual(result.stderr, '')

    def test_wrong_precommit_hash_or_preparer_refuses_before_any_followup_output(self):
        readerpath = prepare.G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
        spec = importlib.util.spec_from_file_location('_followup_test_reader', readerpath)
        reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'tested-followup-precommit.json'
            data = dict(preparer=dict(reader.pin(prepare.__file__), sha256='0'*64))
            fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o444)
            with os.fdopen(fd, 'w') as stream: json.dump(data, stream)
            with self.assertRaisesRegex(ValueError, 'Exact tested root precommit'):
                prepare.run('CPU', path, '1'*64)
            with self.assertRaisesRegex(ValueError, 'Followup preparation source changed'):
                prepare.run('CPU', path, reader.pin(path)['sha256'])
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['tested-followup-precommit.json'])


if __name__ == '__main__':
    unittest.main()
