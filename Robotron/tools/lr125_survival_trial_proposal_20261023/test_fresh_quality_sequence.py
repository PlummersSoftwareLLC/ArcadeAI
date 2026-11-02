"""Injected-I/O scheduling contracts; no real jobs, models or scientific reviews.

The original scoped archive/launch implementations are separately source bound.
These cases test the new fresh-R1 orchestration, failure stops and CPU admission.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

G = Path(__file__).resolve().parents[2]
PATH = G / 'tools/startup_policy_journal_proposal/sequence_fresh_quality32_lr125_v1.py'
spec = importlib.util.spec_from_file_location('_fresh_quality_sequence', PATH)
sequence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sequence)
ORDER = ('R1', 'C1', 'R2', 'C2')
FOLDERS = ('01-reference', '02-candidate', '03-reference', '04-candidate')


class OperatorStop(Exception):
    pass


def require(value, message):
    if not value:
        raise ValueError(message)


class MetadataIO:
    def __init__(self):
        self.values = {}

    def pin(self, path):
        return dict(path=str(path), sha256=hashlib.sha256(str(path).encode()).hexdigest(), bytes=1)

    def put(self, path, value):
        if str(path) in self.values:
            raise FileExistsError(path)
        self.values[str(path)] = copy.deepcopy(value)
        return self.pin(path)

    def read(self, pin, as_json=True):
        return copy.deepcopy(self.values[pin['path']])

    def checked(self, pin):
        return Path(pin['path'])


class FreshSequenceContracts(unittest.TestCase):
    def fixture(self, failure=None, final_valid=True):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        calls = []
        h = MetadataIO()

        def prepare(ready, role, helper):
            calls.append(('prepare', role))
            (root / FOLDERS[ORDER.index(role)]).mkdir()

        def invoke(directory, prefix, source, config, helper, on_live=None):
            role = 'campaign' if prefix else ORDER[FOLDERS.index(directory.name)]
            calls.append(('invoke', role))
            if failure == ('invoke', role):
                raise ValueError('Injected original controller failure')
            if on_live:
                on_live(dict(pid=100, starttime_ticks=10), dict(pid=200, starttime_ticks=20))

        base = SimpleNamespace(CampaignSequence=object, ORDER=ORDER, FOLDERS=FOLDERS, require=require,
            StopNewActions=OperatorStop, os=os, birth=lambda pid: None,
            load=lambda name, path: SimpleNamespace(prepare=prepare),
            invoke_controller_once=invoke, verify_closed_scope=lambda *args: dict(synthetic_verified=True))
        obj = sequence.sequence_type(base)()
        obj.h, obj.root, obj.events = h, root, root / 'events'
        obj.precommit_pin = h.pin(root / 'precommit.json')
        obj.precommit = dict(schema='robotron-fresh-LR125-quality32-sequence-precommit-v1',
            source=h.pin(PATH), campaign_assessment_config=h.pin(root / 'assessment-config.json'))
        obj.ready_pin = h.pin(root / 'readiness.json')
        obj.ready = dict(leg_preparer=h.pin(root / 'preparer.py'), native_controller=h.pin(root / 'native.py'),
                         CPU_controller=h.pin(root / 'CPU.py'))
        obj.records, obj.rt, obj.ctl = [], None, None
        obj.read = h.read
        obj.validate_endpoint_CPU = lambda: calls.append(('CPU_admitted', 'before_R1'))
        obj.check_new_actions = lambda: None
        obj.register = lambda stage, role, *args, **kwargs: calls.append(('register', stage, role))

        def native(directory, role):
            calls.append(('validate_native', role))
            if failure == ('native', role):
                raise ValueError('Injected invalid original native')
            return dict(synthetic_native=True)

        def review(directory, role):
            calls.append(('review', role))
            if failure == ('review', role):
                raise ValueError('Injected invalid original review')
            return dict(synthetic_review=True)

        obj.native, obj.review = native, review
        h.values[str(root / 'independent-campaign-assessment-original01/assessment.json')] = dict(
            valid=final_valid, quality_qualified=False)
        return obj, base, h, calls

    def test_all_four_originals_start_fresh_in_order_with_review_between_each(self):
        obj, base, h, calls = self.fixture()
        self.assertEqual(obj.run(), 0)
        actual = [c for c in calls if c[0] in ('prepare', 'invoke', 'validate_native', 'review')]
        expected = [(kind, role) for role in ORDER
                    for kind in ('prepare', 'invoke', 'validate_native', 'review')] + [('invoke', 'campaign')]
        self.assertEqual(actual, expected)
        self.assertEqual(calls[0], ('CPU_admitted', 'before_R1'))
        outcome = h.values[str(obj.root / 'original-fresh-sequence-observer-original01-outcome.json')]
        self.assertEqual(len(outcome['original_records']), 4)
        self.assertFalse(outcome['existing_R1_adopted'])
        self.assertFalse(outcome['promotion'])
        self.assertFalse(outcome['quality_qualified'])

    def test_failure_in_any_original_native_or_review_stops_without_retry(self):
        for stage in ('invoke', 'native', 'review'):
            for role in ORDER:
                with self.subTest(stage=stage, role=role):
                    obj, base, h, calls = self.fixture(failure=(stage, role))
                    self.assertEqual(obj.run(), 1)
                    self.assertEqual([c[1] for c in calls if c[0] == 'prepare'], list(ORDER[:ORDER.index(role) + 1]))
                    self.assertEqual(sum(c == ('invoke', role) for c in calls), 1)
                    self.assertNotIn(('invoke', 'campaign'), calls)

    def test_existing_R1_directory_or_consumed_intent_refuses_before_launch(self):
        for existing in ('R1', 'intent'):
            obj, base, h, calls = self.fixture()
            path = obj.root / ('01-reference' if existing == 'R1' else
                               'original-fresh-sequence-observer-original01-intent.json')
            if existing == 'R1':
                path.mkdir()
            else:
                path.write_text('{}')
            with self.assertRaises(ValueError):
                obj.run()
            self.assertFalse(any(c[0] in ('prepare', 'invoke') for c in calls))

    def test_invalid_final_assessment_stays_failed_without_relaunch_or_promotion(self):
        obj, base, h, calls = self.fixture(final_valid=False)
        self.assertEqual(obj.run(), 1)
        self.assertEqual(sum(c == ('invoke', 'campaign') for c in calls), 1)
        outcome = h.values[str(obj.root / 'original-fresh-sequence-observer-original01-outcome.json')]
        self.assertEqual(outcome['status'], 'ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY')
        self.assertFalse(outcome['quality_qualified'])
        self.assertFalse(outcome['promotion'])

    def test_R1_review_uses_the_same_new_configuration_name_as_later_roles(self):
        obj, base, h, calls = self.fixture()
        directory = obj.root / '01-reference'
        reviewer = dict(path='/synthetic/new-reviewer.py', sha256='f' * 64)
        obj.ready.update(leg_reviewer=reviewer, quality_pair=dict(path='/synthetic/pair.json', sha256='e' * 64))
        job_pin = h.pin(directory / 'independent-review-job.json')
        cfg_path = directory / 'independent-review-controller-config.json'
        h.values[str(cfg_path)] = dict(argv=['/usr/bin/python3.12', '-I', '-B', reviewer['path'],
            '--observe', '--job', job_pin['path'], '--job-sha256', job_pin['sha256'],
            '--expected-source-sha256', reviewer['sha256']])
        h.values[str(directory / 'independent-quality-leg-review-original01/review.json')] = dict(
            valid=True, full_game_score_verified=True, quality_leg='R1',
            quality_pair_precommit=obj.ready['quality_pair'], review_job=job_pin)
        invoked = []
        base.invoke_controller_once = lambda directory, prefix, source, config, helper, on_live=None: invoked.append(config)
        type(obj).review(obj, directory, 'R1')
        self.assertEqual([p['path'] for p in invoked], [str(cfg_path)])

    def test_wrong_saved_LR_or_candidate_CPU_receipt_refuses_before_scope_operations(self):
        for mutation in ('status', 'lr', 'hash', 'CUDA', 'phase'):
            obj, base, h, calls = self.fixture()
            report_pin, pair_pin = h.pin(obj.root / 'CPU-report.json'), h.pin(obj.root / 'pair.json')
            obj.precommit['endpoint_CPU_report'] = report_pin
            obj.ready['quality_pair'] = pair_pin
            report = dict(status='PASS', phase_metadata_verified=True, cuda_initialized=False,
                visible_cuda_devices=0, held_recipe_context=dict(learning_control_lr_scale=.125),
                adam_group=dict(lr=6.25e-6), sha256='d' * 64)
            if mutation == 'status': report['status'] = 'FAIL'
            if mutation == 'lr': report['adam_group']['lr'] = 1.25e-5
            if mutation == 'hash': report['sha256'] = 'c' * 64
            if mutation == 'CUDA': report['cuda_initialized'] = True
            if mutation == 'phase': report['phase_metadata_verified'] = False
            h.values[report_pin['path']] = report
            h.values[pair_pin['path']] = dict(candidate=dict(policy=dict(sha256='d' * 64), CPU_report=report_pin))
            with self.assertRaises(ValueError):
                type(obj).validate_endpoint_CPU(obj)
            self.assertFalse(any(c[0] in ('prepare', 'invoke') for c in calls))


if __name__ == '__main__':
    unittest.main(verbosity=2)
