#!/usr/bin/env python3
"""CPU-only validation of the prepared main-only override; never applies it."""
import ast
from datetime import datetime,timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest

BASE=Path(__file__).resolve().parent
GAME=Path(__file__).resolve().parents[3]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    original=BASE/'main-batch-wait-before.py'
    proposed=BASE/'main-batch-wait-proposed.py'
    patch=BASE/'main-batch-wait-override.patch'
    current=GAME/'Scripts/dqn/main.py'
    tests=GAME/'tools/test_inference_batch_wait_override.py'
    expected=json.loads((BASE/'main-batch-wait-override-proposal.json').read_text())
    assert digest(original)==expected['original_sha256']
    assert digest(proposed)==expected['proposed_sha256']
    assert digest(patch)==expected['patch_sha256']
    live_before=digest(current)
    assert live_before in (digest(original),digest(proposed)),'Live source is neither reviewed revision'
    before=ast.parse(original.read_text());after=ast.parse(proposed.read_text())
    after.body=[n for n in after.body if not isinstance(n,ast.FunctionDef) or n.name!='_apply_inference_batch_wait_override']
    entry=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    entry.body.pop(0)
    ast_unchanged=ast.dump(before,include_attributes=False)==ast.dump(after,include_attributes=False)
    assert ast_unchanged
    spec=importlib.util.spec_from_file_location('main_wait_override_validation_tests',tests)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    suite=unittest.defaultTestLoader.loadTestsFromModule(module)
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    direction=[] if live_before==digest(original) else ['--reverse']
    check=subprocess.run(['git','apply',*direction,'--check',str(patch)],cwd=GAME.parent,text=True,capture_output=True)
    assert check.returncode==0,check.stderr
    assert digest(current)==live_before,'Validation changed live source'
    report=dict(schema='robotron-main-wait-override-validation-v1',created_utc=datetime.now(timezone.utc).isoformat(),
        original_main_sha256=digest(original),proposed_main_sha256=digest(proposed),patch_sha256=digest(patch),
        current_main_sha256=live_before,status='prepared_only_not_applied' if not direction else 'reviewed_source_applied',
        CPU_tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),all_passed=result.wasSuccessful(),
        AST_identical_except_new_helper_and_first_main_call=ast_unchanged,
        original_top_level_function_count=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in before.body),
        git_apply_check='forward --check' if not direction else 'reverse --check',live_source_unchanged_by_validation=True,
        test_output=stream.getvalue(),validation_script_sha256=digest(Path(__file__)),test_script_sha256=digest(tests),
        scope='AST/function extraction only. No Torch/GPU/agent imports, no source or process controls.')
    output=BASE/'main-batch-wait-override-validation.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    assert result.wasSuccessful(),stream.getvalue()
    print(json.dumps({key:report[key] for key in ('status','CPU_tests','all_passed','AST_identical_except_new_helper_and_first_main_call','git_apply_check')},indent=2))
    print(output)


if __name__=='__main__':main()
