"""Compatibility of the full-game health consumer with unchanged hot checks."""
import unittest
from pathlib import Path
from . import test_round_observer as previous
from .fullgame_round_observer_client import DedicatedMainHealth


class FullGameObserverTests(previous.RoundObserverV3Tests):
    guard_class = DedicatedMainHealth

    def test_returns_zero_based_index_required_by_the_actual_fullgame_native_consumer(self):
        guard, live = previous.live_fixture(self.guard_class)
        record = guard._accept(live)
        self.assertIs(type(record['index']), int)
        self.assertEqual(record['index'], live['observed_samples']-1)
        self.assertEqual(record['index'], 4)
        self.assertEqual(record['sample'], live['latest_sample'])


    def test_actual_archived_fullgame_native_consumer_accepts_new_record_and_rejects_missing_index(self):
        import ast
        import hashlib
        from types import SimpleNamespace
        from .round_observer_client_v5 import DedicatedMainHealth as DeadlineClient
        root = Path(__file__).resolve().parents[2]
        source = root/'logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-protocol-interface-correction-original01/run_quality32_quota64_selected_original01_v2.py'
        raw = source.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '9ecf99ba66b76b8bd31de06e894124e495d3fedba86ba5a1c36db628ccb95f83')
        run = next(node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        consumer = next(node for node in ast.walk(run) if isinstance(node, ast.FunctionDef) and node.name == 'collect_main')
        module = ast.fix_missing_locations(ast.Module(body=[consumer], type_ignores=[]))
        def require(value, reason):
            if not value: raise ValueError(reason)
        for client, expected in ((self.guard_class, True), (DeadlineClient, False)):
            guard, live = previous.live_fixture(client)
            namespace = dict(main_guard=SimpleNamespace(observe=lambda: guard._accept(live)), require=require, main_samples=[])
            exec(compile(module, str(source), 'exec'), namespace)
            if expected:
                record = namespace['collect_main']()
                self.assertEqual(record['index'], 4)
                self.assertEqual(namespace['main_samples'], [record])
            else:
                with self.assertRaises(KeyError): namespace['collect_main']()


if __name__ == '__main__':
    unittest.main()
