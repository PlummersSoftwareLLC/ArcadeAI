"""CPU-only checks of the prepared main-process-only batch-wait override."""
import ast
from contextlib import redirect_stdout
import io
import math
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT=Path(__file__).resolve().parents[1]
ARTIFACT=ROOT/'logs/managed-learning-20261015/run-10'
BEFORE=ARTIFACT/'main-batch-wait-before.py'
PROPOSED=ARTIFACT/'main-batch-wait-proposed.py'
NAME='_apply_inference_batch_wait_override'


def load_helper():
    tree=ast.parse(PROPOSED.read_text())
    function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==NAME)
    namespace={'os':os,'math':math}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(PROPOSED),'exec'),namespace)
    return namespace[NAME]


class BatchWaitOverrideTests(unittest.TestCase):
    def call(self,raw,cfg=None):
        cfg=cfg if cfg is not None else SimpleNamespace(inference_batch_wait_ms=1.0,other=77)
        environment={} if raw is None else {'DQN_INFERENCE_BATCH_WAIT_MS':raw}
        output=io.StringIO()
        with mock.patch.dict(os.environ,environment,clear=True),redirect_stdout(output):
            result=load_helper()(cfg)
        return result,cfg,output.getvalue()

    def test_absent_leaves_config_and_stdout_untouched(self):
        cfg=SimpleNamespace(unrelated=object());saved=dict(vars(cfg))
        result,cfg,output=self.call(None,cfg)
        self.assertIsNone(result);self.assertEqual(vars(cfg),saved);self.assertEqual(output,'')

    def test_explicit_two_ms_only_changes_wait_and_logs(self):
        result,cfg,output=self.call('2')
        self.assertEqual(result,2.0);self.assertEqual(vars(cfg),{'inference_batch_wait_ms':2.0,'other':77})
        self.assertEqual(output,'[INFERENCE] DQN_INFERENCE_BATCH_WAIT_MS=2 ms (main process)\n')

    def test_finite_inclusive_bounds_and_whitespace(self):
        for raw,expected in [('0',0.0),('10',10.0),(' 2.5 ',2.5),('2e0',2.0)]:
            with self.subTest(raw=raw):self.assertEqual(self.call(raw)[1].inference_batch_wait_ms,expected)

    def test_invalid_values_fail_without_mutation_or_log(self):
        for raw in ('nan','NaN','inf','-inf','-0.1','10.1','1e1000','',' ','true','nonsense'):
            with self.subTest(raw=raw):
                cfg=SimpleNamespace(inference_batch_wait_ms=1.0);out=io.StringIO()
                with mock.patch.dict(os.environ,{'DQN_INFERENCE_BATCH_WAIT_MS':raw},clear=True),redirect_stdout(out):
                    with self.assertRaisesRegex(ValueError,'finite number in'):
                        load_helper()(cfg)
                self.assertEqual(cfg.inference_batch_wait_ms,1.0);self.assertEqual(out.getvalue(),'')

    def test_hook_is_before_any_agent_or_server_construction(self):
        main=next(n for n in ast.parse(PROPOSED.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        self.assertEqual(main.body[0].value.func.id,NAME)
        calls=[n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        hook=next(n for n in calls if n.func.id==NAME)
        for constructor in ('RainbowAgent','SocketServer'):
            self.assertTrue(all(hook.lineno<n.lineno for n in calls if n.func.id==constructor))

    def test_only_new_helper_and_main_entry_hook_change_AST(self):
        before=ast.parse(BEFORE.read_text());after=ast.parse(PROPOSED.read_text())
        after.body=[n for n in after.body if not isinstance(n,ast.FunctionDef) or n.name!=NAME]
        main=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name=='main');main.body.pop(0)
        self.assertEqual(ast.dump(before,include_attributes=False),ast.dump(after,include_attributes=False))


if __name__=='__main__':unittest.main()
