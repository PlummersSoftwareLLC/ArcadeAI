"""Reject inferred completion before any original pair closure observations."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('_pair_closure',Path(__file__).with_name('verify_post_reboot_screen_closure_v1.py'))
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)


class ClosurePrerequisites(unittest.TestCase):
    def test_actual_terminal_zero_record(self):
        C.validate_terminal_record(dict(original_tool_session=50607,original_tool_terminal_observed=True,
            actual_tool_result=dict(exit_code=0)))

    def test_running_missing_failed_and_boolean_exits_never_prove_completion(self):
        valid=dict(original_tool_session=50607,original_tool_terminal_observed=True,actual_tool_result=dict(exit_code=0))
        bad=[{},dict(valid,original_tool_session=True),dict(valid,original_tool_session=50608),
            dict(valid,original_tool_terminal_observed=False),dict(valid,actual_tool_result={}),
            dict(valid,actual_tool_result=dict(exit_code=False)),
            dict(valid,actual_tool_result=dict(exit_code=1)),
            dict(valid,actual_tool_result=dict(exit_code=0,session_id=50607))]
        for record in bad:
            with self.subTest(record=record),self.assertRaises(ValueError):C.validate_terminal_record(copy.deepcopy(record))

    def test_default_cli_does_not_load_dependencies_or_follow_a_record(self):
        with patch.object(sys,'argv',['checker','--terminal-record','/this/path/must/not/be/read.json']),patch.object(C,'load',side_effect=AssertionError('Default CLI must be inert')):
            self.assertEqual(C.main(),0)


if __name__=='__main__':unittest.main()
