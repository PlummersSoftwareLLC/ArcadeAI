"""Test queued CLI/197-input bindings without executing scientific payloads."""
import argparse
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(entry, name):
    assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest() == entry['sha256']
    spec = importlib.util.spec_from_file_location(name, entry['path'])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def functions(path):
    return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(Path(path).read_bytes()).body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


def held_input_predicate(path, function):
    tree = ast.parse(Path(path).read_bytes())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function)
    calls = [value for value in ast.walk(node) if isinstance(value, ast.Call)
             and isinstance(value.func, ast.Name) and value.func.id == 'require'
             and len(value.args) == 2 and isinstance(value.args[1], ast.Constant)
             and value.args[1].value in ('Original main evidence incomplete', 'Held main sources changed between legs')]
    assert len(calls) == 1
    return compile(ast.Expression(calls[0].args[0]), str(path), 'eval')


class QueuedReview197Amendment(unittest.TestCase):
    def test_reviewer_changes_only_held_input_count(self):
        old = Path(PREP['derivations']['leg_reviewer']['original']['path']).read_text()
        new = Path(REVIEW.__file__).read_text()
        self.assertEqual(old.count("len(main['held_hashes'])==196"), 1)
        self.assertEqual(new, old.replace("len(main['held_hashes'])==196", "len(main['held_hashes'])==197"))
        predicate = held_input_predicate(REVIEW.__file__, 'review')
        for count, samples, expected in [(197, 3, True), (196, 3, False), (198, 3, False), (197, 2, False)]:
            with self.subTest(count=count, samples=samples):
                self.assertIs(eval(predicate, {}, dict(main=dict(held_hashes=dict.fromkeys(range(count))),
                    result=dict(main_samples=[None]*samples))), expected)

    def test_assessor_changes_only_exact197_and_unexecuted_R1_config_selector(self):
        old = Path(PREP['derivations']['campaign_assessor']['original']['path']).read_text()
        expected = old.replace('len(main_sources)==196', 'len(main_sources)==197').replace(
            "cpucfg_pin=h.pin(root/'independent-review-controller-config.json');cpucfg=read(cpucfg_pin)",
            "cpucfg_name=('independent-review-controller-config-prospective197-original01.json' if role=='R1' else 'independent-review-controller-config.json')\n"
            "            cpucfg_pin=h.pin(root/cpucfg_name);cpucfg=read(cpucfg_pin)")
        self.assertEqual(Path(ASSESS.__file__).read_text(), expected)
        predicate = held_input_predicate(ASSESS.__file__, 'execute')
        original = dict.fromkeys(range(197))
        self.assertTrue(eval(predicate, {}, dict(main=dict(held_hashes=original), main_sources=original)))
        for count in (196, 198):
            wrong = dict.fromkeys(range(count))
            self.assertFalse(eval(predicate, {}, dict(main=dict(held_hashes=wrong), main_sources=wrong)))
        altered = dict(original)
        altered[0] = 'changed'
        self.assertFalse(eval(predicate, {}, dict(main=dict(held_hashes=altered), main_sources=original)))

    def test_actual_queued_R1_CLI_parses_and_binds_original_job_with_payload_stubbed(self):
        config = json.loads(Path(PREP['new_R1_review_config']['path']).read_bytes())
        with patch.object(sys, 'argv', config['argv'][3:]), patch.object(REVIEW, 'review', return_value=0) as payload:
            self.assertEqual(REVIEW.main(), 0)
        payload.assert_called_once()
        pin = payload.call_args.args[0]
        self.assertEqual(pin['path'], config['argv'][6])
        self.assertEqual(pin['sha256'], config['argv'][8])
        self.assertEqual(config['argv'][3], REVIEW.__file__)
        self.assertEqual(config['argv'][-1], hashlib.sha256(Path(REVIEW.__file__).read_bytes()).hexdigest())

    def test_actual_queued_assessment_CLI_parses_and_binds_amended_job_with_payload_stubbed(self):
        config = json.loads(Path(PREP['new_assessment_config']['path']).read_bytes())
        with patch.object(sys, 'argv', config['argv'][3:]), patch.object(ASSESS, 'execute', return_value=0) as payload:
            self.assertEqual(ASSESS.main(), 0)
        payload.assert_called_once()
        self.assertEqual(payload.call_args.args[0], PREP['new_assessment_job'])
        self.assertEqual(config['argv'][4], '--execute')
        self.assertEqual(config['argv'][9], '--source-sha256')

    def test_superseded_wrong_assessment_CLI_is_rejected_without_scientific_execution(self):
        config = json.loads(Path(PREP['old_unexecuted_assessment_config']['path']).read_bytes())
        with (patch.object(sys, 'argv', config['argv'][3:]), patch.object(ASSESS, 'execute') as payload,
              contextlib.redirect_stderr(io.StringIO())):
            with self.assertRaises(SystemExit) as result:
                ASSESS.main()
        self.assertEqual(result.exception.code, 2)
        payload.assert_not_called()

    def test_original_native_job_acceptance_and_policy_remain_exact(self):
        pin = PREP['R1_native_job_unchanged']
        raw = Path(pin['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), pin['sha256'])
        job = json.loads(raw)
        self.assertEqual(job['admission_s'], 5400)
        self.assertEqual(job['whole_cohort_timeout_s'], 9000)
        self.assertEqual(job['minimum_completed_games'], 50)
        old = json.loads(Path(PREP['old_unexecuted_R1_review_config']['path']).read_bytes())
        new = json.loads(Path(PREP['new_R1_review_config']['path']).read_bytes())
        self.assertEqual(old['unit'], new['unit'])
        self.assertEqual(old['output'], new['output'])
        self.assertEqual(old['argv'][4:10], new['argv'][4:10])
        self.assertEqual(old['properties'], new['properties'])
        self.assertEqual(job['quality_pair_precommit'], READY['quality_pair'])

    def test_numerical_gates_and_original_owned_lifecycle_functions_are_identical(self):
        old_assessor = functions(PREP['derivations']['campaign_assessor']['original']['path'])
        new_assessor = functions(ASSESS.__file__)
        for name in ('metrics', 'assess_validated_cohorts', 'main'):
            self.assertEqual(old_assessor[name], new_assessor[name])
        old_seq = functions(PREP['derivations']['sequencer']['original']['path'])
        new_seq = functions(SEQ.__file__)
        for name in ('invoke_controller_once', 'verify_closed_scope'):
            self.assertEqual(old_seq[name], new_seq[name])
        old_source = Path(PREP['derivations']['sequencer']['original']['path']).read_text()
        def methods(raw):
            cls = next(node for node in ast.parse(raw).body if isinstance(node, ast.ClassDef) and node.name == 'CampaignSequence')
            return {node.name: ast.dump(node, include_attributes=False) for node in cls.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(methods(old_source)['native'], methods(Path(SEQ.__file__).read_text())['native'])
        # The decoder which rejected the old Infinity capture is unchanged.
        self.assertEqual(READY['games_auditor']['sha256'], 'e106cb9d3a2131c34365daaf4638ccba97c94c02de00a4a33dfe4d7ce5876f9b')

    def test_successor_requires_terminal_empty_predecessor_before_scientific_actions(self):
        fixture = object.__new__(SEQ.CampaignSequence)
        source = dict(path=SEQ.__file__, sha256=hashlib.sha256(Path(SEQ.__file__).read_bytes()).hexdigest())
        fixture.h = SimpleNamespace(pin=lambda _: source)
        fixture.precommit = dict(schema='robotron-existing-R1-quality32-sequence-precommit-v1', source=source,
            prior_observer_terminal='terminal', prior_observer_intent='intent')
        fixture.read = lambda entry: dict(status='ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY', original_records=[]) if entry == 'terminal' else dict(pid=123, birth=456)
        with self.assertRaisesRegex(ValueError, 'Prior observer must be terminal'):
            fixture.run()
        fixture.read = lambda entry: dict(status='SEQUENCING_STOPPED_NO_NEW_ACTIONS', original_records=[]) if entry == 'terminal' else dict(pid=123, birth=456)
        with patch.object(SEQ, 'birth', return_value=456), self.assertRaisesRegex(ValueError, 'Prior observer must be terminal'):
            fixture.run()

    def test_new_stop_control_does_not_clear_or_revive_original_control(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            campaign = root/'campaign'
            campaign.mkdir()
            original = campaign/'sequencing-control.json'
            original.write_text('{"stop_new_actions":true}')
            state = root/'state.json'
            state.write_text(json.dumps(dict(active_quality_job=dict(directory=str(campaign)))))
            fixture = object.__new__(SEQ.CampaignSequence)
            fixture.root = campaign
            with patch.object(SEQ, 'R', root/'run-26'):
                fixture.check_new_actions()
                (campaign/'sequencing-control-prospective197-original01.json').write_text('{"stop_new_actions":true}')
                with self.assertRaises(SEQ.StopNewActions):
                    fixture.check_new_actions()
            self.assertEqual(original.read_text(), '{"stop_new_actions":true}')


def main():
    global PREP, READY, REVIEW, ASSESS, SEQ
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw = Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job = json.loads(raw)
    assert not Path(job['output']).exists()
    for entry in job['pins']:
        assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest() == entry['sha256']
    PREP = json.loads(Path(job['preparation']['path']).read_bytes())
    READY = json.loads(Path(PREP['new_readiness']['path']).read_bytes())
    REVIEW = load(READY['leg_reviewer'], '_future197_review_CLI_guards')
    ASSESS = load(READY['campaign_assessor'], '_future197_assessment_CLI_guards')
    SEQ = load(PREP['successor_sequence_source'], '_future197_sequence_guards')
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(QueuedReview197Amendment))
    assert 'torch' not in sys.modules
    report = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), source_sha256=args.source_sha256,
        scientific_payloads_executed=False, CLI_payloads_stubbed=True, actual_games_or_process_operations=False,
        main_runtime_changed=False, original_native_R1_retried=False, original_scientific_review_retried=False,
        quality_qualified=False, promotion=False, created_unix_s=time.time())
    with Path(job['output']).open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(report), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
