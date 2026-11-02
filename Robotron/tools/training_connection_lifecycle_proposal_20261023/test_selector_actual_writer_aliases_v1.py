"""Explicit CPU engineering guards against actual GameJournal.observe objects.

No Torch, emulator, trainer writes, import-time execution or quality evidence.
Both selector sources must pass the same independently defined writer contract.
"""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest


def checked_load(name, pin):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class WriterHarness:
    """Use accepted-frame API to create every game/result; never inject rows."""
    def __init__(self, journal_module, selector, directory):
        self.now = 1000001.0
        self.bounds = ('actual-writer-engineering-only', 1000000.0, 1021540.0)
        self.shared = dict(scope='synthetic CPU guard; no ROM or runtime proof',
                           certificate=dict(paths=[dict(sha256='a' * 64)], markers=[1, 2]))
        self.policy = dict(checkpoint_sha256='1' * 64, policy_load_id='2' * 64,
            measurement_active=True, training_enabled=False, replay_enabled=False,
            epsilon=0.0, expert_ratio=0.0, measurement_generation=1,
            experiment=self.bounds[0], learner_frame_count=100, training_steps=200,
            optimized_samples=300, nested_policy=dict(values=[1, 2]))
        self.journal = journal_module.GameJournal(directory, clock=lambda: self.now,
            completion_policy='confirmed_reset_reserves_v1')
        self.view = selector.FixedSlotCohortView(self.journal, policy=self.policy)
        self.uids = {}
        self.context_sequence = 0

    def context(self):
        self.context_sequence += 1
        return dict(experiment=self.bounds[0], measurement_active=True,
            measurement_generation=1, difficulty=5, epsilon=0.0, expert_ratio=0.0,
            learner_frames=100, training_steps=200, optimized_samples=300,
            startup_certificate=self.shared,
            end_only=dict(context_sequence=self.context_sequence, values=[1, 2]))

    def observe(self, slot, *, reset=False, score=0, alive=True, known=True):
        if reset or slot not in self.uids:
            self.uids[slot] = self.uids.get(slot, 0) + 1
        self.now += .01
        frame = SimpleNamespace(game_score=score, level_number=1 if alive else 0,
            player_alive=alive, lives=3, num_lasers=2, start_pressed=reset, done=False)
        cs = dict(client_slot=slot, game_uid=self.uids[slot], eval_only=True)
        self.journal.observe(slot - 4096, frame, cs, new_game=reset and known,
                             context=self.context)
        return self.journal.active[slot - 4096]

    def status(self):
        return self.view.cohort_status(*self.bounds)

    def pair(self, slot=4096):
        first = self.observe(slot, reset=True)
        self.observe(slot, score=100)
        second = self.observe(slot, reset=True)
        self.observe(slot, score=200)
        third = self.observe(slot, reset=True)
        return first, second, third


def guards(journal_module, selector):
    class ActualWriterGuards(unittest.TestCase):
        def setUp(self):
            self.directory = tempfile.TemporaryDirectory(prefix='selector-actual-writer-')
            self.addCleanup(self.directory.cleanup)
            self.case = WriterHarness(journal_module, selector, self.directory.name)

        def test_actual_observe_writer_aliases_and_persisted_records(self):
            c = self.case
            first, second, third = c.pair()
            for game in (first, second):
                result = game['result']
                self.assertIs(result['start_context'], game['start'])
                self.assertIs(result['start_frame'], game['start_frame'])
                self.assertIs(result['start_context']['startup_certificate'], c.shared)
                self.assertIs(result['end_context']['startup_certificate'], c.shared)
                self.assertIs(c.journal.measurement_games[game['journal_game_id']], game)
                self.assertTrue(result['eligible'] and result['complete'])
            self.assertIs(first['start']['startup_certificate'], second['start']['startup_certificate'])
            written = [json.loads(line) for line in c.journal.games_path.read_text().splitlines()]
            self.assertEqual(written, [first['result'], second['result']])
            starts = [json.loads(line) for line in c.journal.measurement_starts_path.read_text().splitlines()]
            self.assertEqual([r['journal_game_id'] for r in starts], [g['journal_game_id'] for g in (first, second, third)])

        def test_actual_full64_keeps_extra_starts_and_zero_score(self):
            c = self.case
            first = c.observe(4096, reset=True)
            c.status()
            c.observe(4096, score=0)
            c.observe(4096, reset=True)
            self.assertEqual(c.status()['count'], 1)
            c.observe(4096, score=200)
            c.observe(4096, reset=True)
            for slot in selector.SLOTS[1:]:
                c.pair(slot)
            status = c.status()
            self.assertTrue(status['complete'] and status['valid'])
            self.assertEqual((status['count'], status['started'], status['pending']), (64, 64, 0))
            self.assertEqual(len(status['retained_outside_cohort_ids']), 32)
            self.assertEqual(set(status['slot_admitted_counts'].values()), {2})
            self.assertEqual(status['mean'], (31 * 300 + 200) / 64)
            self.assertEqual(next(r['score'] for r in status['rows'] if r['journal_game_id'] == first['journal_game_id']), 0)
            self.assertFalse(status['quality_qualified'] or status['full_game_score_verified'])

        def test_nested_returned_rows_independent_from_writer_cache_and_each_other(self):
            c = self.case
            first, second, _ = c.pair()
            original = copy.deepcopy([first['result'], second['result']])
            status = c.status()
            a, b = status['rows']
            self.assertIsNot(a['start_context']['startup_certificate'], c.shared)
            self.assertIsNot(a['start_context']['startup_certificate'], b['start_context']['startup_certificate'])
            a['start_context']['startup_certificate']['certificate']['paths'][0]['sha256'] = 'changed'
            a['start_frame']['lives'] = 999
            a['end_context']['end_only']['values'].append(3)
            self.assertEqual(b, original[1])
            self.assertEqual([first['result'], second['result']], original)
            self.assertEqual(c.status()['rows'], original)

        def test_policy_nested_copy_independent_from_input_and_return(self):
            c = self.case
            c.policy['nested_policy']['values'].append(9)
            returned = c.view.policy()
            self.assertEqual(returned['nested_policy']['values'], [1, 2])
            returned['nested_policy']['values'].append(8)
            self.assertEqual(c.view.policy()['nested_policy']['values'], [1, 2])

        def test_pending_actual_start_nested_mutation_rejected(self):
            c = self.case
            game = c.observe(4096, reset=True)
            c.status()
            game['start']['startup_certificate']['certificate']['paths'][0]['sha256'] = 'changed'
            with self.assertRaisesRegex(ValueError, 'known-start descriptor changed'):
                c.status()

        def test_extra_actual_start_still_checked_after_all_quotas_closed(self):
            c = self.case
            games = [c.pair(slot) for slot in selector.SLOTS]
            self.assertTrue(c.status()['closed'])
            games[-1][2]['start']['end_only']['values'].append(8)
            with self.assertRaisesRegex(ValueError, 'known-start descriptor changed'):
                c.status()

        def test_actual_completed_end_context_mutation_rejected(self):
            c = self.case
            first, _, _ = c.pair()
            c.status()
            first['result']['end_context']['end_only']['values'].append(7)
            with self.assertRaisesRegex(ValueError, 'completed result changed or disappeared'):
                c.status()

        def test_actual_completed_start_frame_alias_mutation_rejected(self):
            c = self.case
            first, _, _ = c.pair()
            c.status()
            self.assertIs(first['start_frame'], first['result']['start_frame'])
            first['start_frame']['lives'] += 1
            with self.assertRaisesRegex(ValueError, 'completed result changed or disappeared'):
                c.status()

        def test_actual_completed_start_context_alias_mutation_rejected(self):
            c = self.case
            first, _, _ = c.pair()
            c.status()
            self.assertIs(first['start'], first['result']['start_context'])
            first['result']['start_context']['end_only']['values'].append(7)
            with self.assertRaisesRegex(ValueError, 'known-start descriptor changed'):
                c.status()

        def test_selector_read_does_not_mutate_actual_writer_or_aliases(self):
            c = self.case
            first, second, _ = c.pair()
            before = copy.deepcopy(c.journal.measurement_games)
            files = {p.name: p.read_bytes() for p in Path(self.directory.name).glob('*.jsonl')}
            for _ in range(3):
                c.status()
            self.assertEqual(c.journal.measurement_games, before)
            self.assertEqual({p.name: p.read_bytes() for p in Path(self.directory.name).glob('*.jsonl')}, files)
            self.assertIs(first['start'], first['result']['start_context'])
            self.assertIs(second['start_frame'], second['result']['start_frame'])
            self.assertIs(first['start']['startup_certificate'], second['start']['startup_certificate'])

        def test_disconnect_abandons_actual_selected_game_without_replacement(self):
            c = self.case
            first = c.observe(4096, reset=True)
            c.status()
            c.journal.disconnect(0, c.context)
            c.observe(4096, reset=True)
            c.observe(4096, reset=True)
            status = c.status()
            self.assertFalse(status['valid'] or status['complete'])
            self.assertEqual(status['abandoned_ids'], [first['journal_game_id']])
            self.assertEqual((status['started'], len(status['retained_outside_cohort_ids'])), (2, 1))

        def test_initial_attachment_remains_written_partial_outside_known_starts(self):
            c = self.case
            attachment = c.observe(4096, reset=False, known=False)
            c.observe(4096, reset=True)
            status = c.status()
            self.assertFalse(attachment['known_start'] or attachment['result']['eligible'])
            self.assertEqual(attachment['result']['excluded_reason'], 'startup_attachment')
            self.assertEqual((status['started'], status['count'], status['pending']), (1, 0, 1))
            self.assertNotIn(attachment['journal_game_id'], status['started_ids'])
    return unittest.defaultTestLoader.loadTestsFromTestCase(ActualWriterGuards)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-guards', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256')
    args = parser.parse_args()
    if not args.run_guards:
        print('PLAN_ONLY: actual-writer alias guards; no import or execution')
        return
    assert hashlib.sha256(args.job.read_bytes()).hexdigest() == args.expected_job_sha256
    job = json.loads(args.job.read_text())
    assert job['schema'] == 'robotron-selector-actual-writer-alias-guards-job-v1'
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == job['runner_sha256']
    report = Path(job['report'])
    assert not report.exists()
    journal = checked_load('_actual_alias_journal', job['journal'])
    results = {}
    for name in ('baseline', 'proposal'):
        selector = checked_load('_actual_alias_' + name, job[name])
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(guards(journal, selector))
        results[name] = dict(tests=result.testsRun, failures=len(result.failures),
                             errors=len(result.errors), skipped=len(result.skipped), log=stream.getvalue())
    passed = all(v['tests'] == 12 and v['failures'] == v['errors'] == v['skipped'] == 0 for v in results.values())
    value = dict(schema='robotron-selector-actual-writer-alias-guards-result-v1', passed=passed,
        job=job, results=results, actual_GameJournal_observe_and_jsonl_writer=True,
        decoded_fixture_objects_used=False, Torch_imported='torch' in sys.modules,
        runtime_or_quality_evidence=False, production_changed=False)
    assert value['Torch_imported'] is False
    with report.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(dict(passed=passed, tests_per_implementation=12, report=str(report))))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
