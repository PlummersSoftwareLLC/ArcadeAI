"""Inactive engineering fixtures, never game/runtime/quality evidence.

No fixture runs on import or without explicit --run-guards and a new report path.
Actual execution must use its subsequently pinned original CPU scope, after the
current scientific sequence and all its original scopes have closed.
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
import threading
from types import SimpleNamespace
import unittest

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
PROFILE = ROOT / 'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn'
HERE = Path(__file__).resolve().parent
SOURCES = {
    'journal': (PROFILE / 'game_journal.py', '96864c78df67f46bc58b1c4af4ce1bceb3791a8842fdcf02871385a1013d1e0f'),
    'measurement': (PROFILE / 'managed_measurement.py', '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6'),
    'view': (HERE / 'fixed_slot_cohort_view_v1.py', '494dcdbcb0ae30f95f4724435e6bf61c68bec3aa7fc3705e39636c0ba60ddbd0'),
}
START = 1000000.0
LABEL = 'engineering-fixture-only-no-quality-evidence'


def load(name, path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Original engineering input changed: ' + str(path))
    module_name = 'quota64_engineering_' + name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def guard_suite(modules):
    journal_module, measurement_module, view_module = (modules[k] for k in ('journal', 'measurement', 'view'))

    class Guards(unittest.TestCase):
        def setUp(self):
            self.temp = tempfile.TemporaryDirectory(prefix='quota64-engineering-fixtures-')
            self.addCleanup(self.temp.cleanup)
            self.now = START + 1
            self.policy = dict(
                checkpoint_sha256='1' * 64, policy_load_id='2' * 64,
                measurement_active=True, training_enabled=False, replay_enabled=False,
                epsilon=0.0, expert_ratio=0.0, measurement_generation=1,
                experiment=LABEL, learner_frame_count=100, training_steps=200,
                optimized_samples=300)
            self.journal = journal_module.GameJournal(
                self.temp.name, clock=lambda: self.now,
                completion_policy='confirmed_reset_reserves_v1')
            self.view = view_module.FixedSlotCohortView(self.journal, policy=self.policy)
            self.close = START + view_module.OUTER_START_HORIZON_S

        def add(self, slot, score=None, *, timestamp=None):
            self.journal.sequence += 1
            ordinal = self.journal.sequence
            key = self.journal.run_id + ':' + str(ordinal)
            context = dict(experiment=LABEL, measurement_active=True,
                           measurement_generation=1, difficulty=5, epsilon=0.0,
                           expert_ratio=0.0, learner_frames=100, training_steps=200,
                           optimized_samples=300)
            game = dict(journal_game_id=key, client_id=slot - 4096,
                        client_slot=slot, game_uid=ordinal, known_start=True,
                        eval_only=True, measurement_active=True, measurement_generation=1,
                        start_unix_s=START + 1 if timestamp is None else timestamp,
                        start_reason='synthetic_engineering_fixture_only', start=context,
                        mixed_experiment=False, mixed_measurement=False,
                        first_play_level=1, result=None, finished=False)
            self.journal.measurement_games[key] = game
            if score is not None:
                self.finish(game, score)
            return game

        def finish(self, game, score):
            game['finished'] = True
            game['result'] = dict(
                **{k: game[k] for k in ('journal_game_id', 'client_id', 'client_slot',
                                       'game_uid', 'start_unix_s')},
                score=score, complete=True, known_start=True, measurement_active=True,
                eval_only=True, first_play_level=1, experiment=LABEL,
                measurement_generation=1, eligible=True, excluded_reason='',
                boundary_reason='synthetic_engineering_fixture_only')

        def populate(self, per_slot=2, *, complete=False):
            return [self.add(slot, 0 if complete else None)
                    for _ in range(per_slot) for slot in view_module.SLOTS]

        def status(self):
            return self.view.cohort_status(LABEL, START, self.close)

        def controller(self, *, warming=False):
            agent = SimpleNamespace(training_steps=200, optimized_samples=300, memory=None)
            metrics = SimpleNamespace(total_training_steps=200,
                                      total_optimized_samples=300, learner_frame_count=100)
            cls = view_module.measurement_type(measurement_module.ManagedMeasurement)
            controller = cls(agent, metrics, self.view,
                             boundary_status=lambda _: dict(ready=True, generation=1,
                                                             actor_slots=list(view_module.SLOTS)),
                             clock=lambda: self.now)
            controller._prior = {}
            controller._owns_mode = True
            controller._entered_ts = START
            controller.timeout_s = 21600
            controller.cohort_s = view_module.OUTER_START_HORIZON_S
            controller._clocks = controller._clock_values()
            controller._replay_guard = {}
            controller.label, controller.generation = LABEL, 1
            controller._boundary = dict(ready=True, generation=1,
                                        actor_slots=list(view_module.SLOTS))
            controller.phase = 'warming' if warming else 'collecting'
            if not warming:
                controller.start_ts, controller.close_ts = START, self.close
            return controller

        def test_empty_and_single_round_cannot_complete(self):
            empty = self.status()
            self.assertFalse(empty['closed'])
            self.assertEqual(empty['started'], 0)
            self.populate(1, complete=True)
            single = self.status()
            self.assertEqual(single['count'], 32)
            self.assertFalse(single['closed'])
            self.assertFalse(single['complete'])

        def test_quota_closes_before_horizon_but_keeps_all_pending(self):
            games = self.populate()
            status = self.status()
            self.assertTrue(status['closed'])
            self.assertEqual(status['closed_by'], 'slot_quota')
            self.assertEqual(status['pending'], 64)
            self.assertEqual(set(status['pending_ids']), {g['journal_game_id'] for g in games})
            self.assertFalse(status['complete'])
            self.assertEqual(set(status['slot_admitted_counts'].values()), {2})

        def test_all64_full_results_including_zeroes_required(self):
            games = self.populate(complete=True)
            games[-1]['result'] = None
            games[-1]['finished'] = False
            partial = self.status()
            self.assertEqual((partial['count'], partial['pending']), (63, 1))
            self.assertFalse(partial['complete'])
            self.finish(games[-1], 6400)
            status = self.status()
            self.assertTrue(status['complete'])
            self.assertEqual(status['count'], 64)
            self.assertEqual(status['mean'], 100)
            self.assertEqual(status['median'], 0)
            self.assertFalse(status['quality_qualified'])
            self.assertFalse(status['full_game_score_verified'])

        def test_third_fast_slot_game_retained_without_outcome_selection(self):
            first = self.add(4096)
            second = self.add(4096, 0)
            third = self.add(4096, 99999999)
            for slot in view_module.SLOTS[1:]:
                self.add(slot, 0)
                self.add(slot, 0)
            status = self.status()
            self.assertEqual(status['pending_ids'], [first['journal_game_id']])
            self.assertIn(second['journal_game_id'], status['started_ids'])
            self.assertEqual(status['retained_outside_cohort_ids'], [third['journal_game_id']])
            self.assertFalse(status['complete'])
            self.assertEqual(status['mean'], 0)

        def test_abandoned_selected_game_never_replaced(self):
            games = self.populate(complete=True)
            selected = games[0]
            selected['result']['eligible'] = False
            selected['result']['excluded_reason'] = 'synthetic_disconnect'
            third = self.add(selected['client_slot'], 99999999)
            status = self.status()
            self.assertEqual(status['abandoned_ids'], [selected['journal_game_id']])
            self.assertIn(third['journal_game_id'], status['retained_outside_cohort_ids'])
            self.assertFalse(status['valid'])

        def test_wrong_policy_generation_or_wave_invalidates_selected(self):
            for mutation in ('clock', 'generation', 'wave'):
                with self.subTest(mutation=mutation):
                    self.journal.measurement_games.clear()
                    self.view = view_module.FixedSlotCohortView(self.journal, policy=self.policy)
                    game = self.add(4096, 0)
                    if mutation == 'clock':
                        game['start']['training_steps'] += 1
                    elif mutation == 'generation':
                        game['measurement_generation'] += 1
                    else:
                        game['first_play_level'] = 17
                    self.add(4096, 0)
                    third = self.add(4096, 99999999)
                    status = self.status()
                    self.assertIn(game['journal_game_id'], status['abandoned_ids'])
                    self.assertIn(third['journal_game_id'], status['retained_outside_cohort_ids'])

        def test_missing_quota_is_sticky_failure_without_invented_ids(self):
            self.populate(1, complete=True)
            self.now = self.close
            status = self.status()
            self.assertTrue(status['closed'])
            self.assertEqual(status['failure_reason'], 'slot_quota_unfilled_at_start_horizon')
            self.assertEqual((status['started'], status['count']), (32, 32))
            self.assertFalse(status['complete'])
            outside = self.add(4096, 0, timestamp=self.close + 1)
            self.assertIn(outside['journal_game_id'], self.status()['retained_outside_cohort_ids'])
            self.assertEqual(self.status()['failure_reason'], status['failure_reason'])
            self.add(4096, 0, timestamp=self.close - 1)
            with self.assertRaisesRegex(ValueError, 'Closed admission membership changed'):
                self.status()

        def test_changed_bounds_or_nonfinite_timestamp_rejected(self):
            self.status()
            for start, close in ((START + 1, self.close + 1), (START, float('nan'))):
                with self.subTest(start=start, close=close), self.assertRaises(ValueError):
                    self.view.cohort_status(LABEL, start, close)

        def test_start_descriptor_disappearance_and_reordering_rejected(self):
            for mutation in ('descriptor', 'disappearance', 'reordering'):
                with self.subTest(mutation=mutation):
                    self.journal.measurement_games.clear()
                    self.view = view_module.FixedSlotCohortView(self.journal, policy=self.policy)
                    first, second = self.add(4096), self.add(4097)
                    self.status()
                    if mutation == 'descriptor':
                        first['start']['training_steps'] += 1
                    elif mutation == 'disappearance':
                        del self.journal.measurement_games[first['journal_game_id']]
                    else:
                        self.journal.measurement_games = {
                            second['journal_game_id']: second, first['journal_game_id']: first}
                    with self.assertRaises(ValueError):
                        self.status()

        def test_completed_results_immutable_even_when_relabelled_ineligible(self):
            for mutation in ('score', 'eligibility', 'disappearance'):
                with self.subTest(mutation=mutation):
                    self.journal.measurement_games.clear()
                    self.view = view_module.FixedSlotCohortView(self.journal, policy=self.policy)
                    game = self.add(4096, 0)
                    self.status()
                    if mutation == 'score':
                        game['result']['score'] = 1
                    elif mutation == 'eligibility':
                        game['result']['eligible'] = False
                    else:
                        game['result'] = None
                    with self.assertRaisesRegex(ValueError, 'completed result changed or disappeared'):
                        self.status()

        def test_foreign_slot_and_noninteger_scores_rejected(self):
            foreign = self.add(9999)
            with self.assertRaisesRegex(ValueError, 'Foreign original slot'):
                self.status()
            del self.journal.measurement_games[foreign['journal_game_id']]
            game = self.add(4096, 1)
            for score in (True, 1.5, -1):
                game['result']['score'] = score
                with self.subTest(score=score), self.assertRaises(ValueError):
                    self.status()

        def test_controller_drains_at_quota_and_finishes_only_after_all64(self):
            games = self.populate()
            controller = self.controller()
            status = controller.tick()
            self.assertEqual(status['phase'], 'draining')
            self.assertFalse(status['complete'])
            for game in games[:-1]:
                self.finish(game, 0)
            self.assertFalse(controller.tick()['complete'])
            self.finish(games[-1], 0)
            status = controller.tick()
            self.assertTrue(status['complete'])
            self.assertTrue(status['valid'])

        def test_original_timeout_keeps_all_pending_and_cannot_extend(self):
            games = self.populate()
            controller = self.controller()
            controller.tick()
            self.now = START + 21600
            status = controller.tick()
            self.assertTrue(status['complete'])
            self.assertFalse(status['valid'])
            self.assertEqual(status['reason'], 'whole_cohort_timeout')
            self.assertEqual(set(status['cohort']['pending_ids']),
                             {game['journal_game_id'] for game in games})
            self.assertEqual((controller.start_ts, controller.close_ts), (START, self.close))
            self.assertEqual(controller.tick()['reason'], 'whole_cohort_timeout')

        def test_original_training_clock_and_replay_guards_retained(self):
            controller = self.controller()
            controller.agent.training_steps += 1
            self.assertEqual(controller.tick()['reason'], 'training_or_learner_clock_moved')
            controller = self.controller()
            controller.agent.memory = SimpleNamespace(_adds_total=1)
            self.assertEqual(controller.tick()['reason'], 'replay_changed_after_boundary')

        def test_controller_rejects_missing_quota_at_outer_horizon(self):
            self.populate(1, complete=True)
            controller = self.controller()
            self.now = self.close
            status = controller.tick()
            self.assertTrue(status['complete'])
            self.assertFalse(status['valid'])
            self.assertEqual(status['reason'], 'slot_quota_unfilled_at_start_horizon')

        def test_install_requires_empty_original_warming_binding(self):
            controller = self.controller(warming=True)
            controller.journal = self.journal
            server = SimpleNamespace(game_journal=self.journal)
            installed = view_module.install_view(server, controller, self.policy)
            self.assertIs(controller.journal, installed)
            self.assertIs(server.game_journal, installed)
            self.assertIs(installed.journal, self.journal)
            self.assertEqual(installed.policy(), self.policy)
            self.assertEqual(installed.games_path, self.journal.games_path)
            with self.assertRaises(ValueError):
                view_module.install_view(server, controller, self.policy)

        def test_install_rejects_existing_games_or_changed_generation(self):
            for mutation in ('existing_game', 'generation', 'collecting'):
                with self.subTest(mutation=mutation):
                    self.journal.measurement_games.clear()
                    controller = self.controller(warming=True)
                    controller.journal = self.journal
                    server = SimpleNamespace(game_journal=self.journal)
                    policy = copy.deepcopy(self.policy)
                    if mutation == 'existing_game':
                        self.add(4096)
                    elif mutation == 'generation':
                        policy['measurement_generation'] = 2
                    else:
                        controller.phase = 'collecting'
                    with self.assertRaises(ValueError):
                        view_module.install_view(server, controller, policy)
                    self.assertIs(server.game_journal, self.journal)
                    self.assertIs(controller.journal, self.journal)

        def test_source_binding_and_frozen_policy_required(self):
            with self.assertRaises(ValueError):
                view_module.FixedSlotCohortView(SimpleNamespace(), policy=self.policy)
            for key, value in (('epsilon', True), ('replay_enabled', True),
                               ('measurement_generation', True), ('checkpoint_sha256', '0' * 64)):
                policy = copy.deepcopy(self.policy)
                policy[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    view_module.FixedSlotCohortView(self.journal, policy=policy)
            changed = self.view.policy()
            changed['experiment'] = 'different'
            self.assertEqual(self.view.policy()['experiment'], LABEL)

        def test_actual_entry_freezes_and_exit_restores_original_flags(self):
            installed = []
            agent = SimpleNamespace(
                training_steps=200, optimized_samples=300, memory=None,
                training_enabled=True, behavior_locked=False, _prefetch_paused=False,
                _training_lock=threading.Lock(),
                capture_inference_policy=lambda: 'synthetic-online-policy',
                install_inference_policy=installed.append)
            agent._pause_prefetch = lambda: setattr(agent, '_prefetch_paused', True)
            agent._resume_prefetch = lambda: setattr(agent, '_prefetch_paused', False)
            metrics = SimpleNamespace(
                total_training_steps=200, total_optimized_samples=300, learner_frame_count=100,
                training_enabled=True, measurement_active=False, ratchet_frozen=False,
                measurement_generation=0, measurement_label='', lock=threading.Lock())
            cls = view_module.measurement_type(measurement_module.ManagedMeasurement)
            controller = cls(agent, metrics, self.journal,
                             boundary_status=lambda _: dict(ready=True, generation=1,
                                                             actor_slots=list(view_module.SLOTS)),
                             clock=lambda: self.now)
            entry = controller.enter(LABEL, cohort_s=view_module.OUTER_START_HORIZON_S,
                                     timeout_s=21600)
            self.assertEqual(entry['phase'], 'warming')
            self.assertFalse(agent.training_enabled)
            self.assertFalse(metrics.training_enabled)
            self.assertTrue(agent.behavior_locked)
            self.assertTrue(agent._prefetch_paused)
            self.assertTrue(metrics.measurement_active)
            server = SimpleNamespace(game_journal=self.journal)
            view_module.install_view(server, controller, self.policy)
            self.assertEqual(controller.tick()['phase'], 'collecting')
            status = controller.exit()
            self.assertEqual(status['reason'], 'controller_exit_before_cohort_complete')
            self.assertEqual(status['phase'], 'finished')
            self.assertTrue(agent.training_enabled)
            self.assertTrue(metrics.training_enabled)
            self.assertFalse(agent.behavior_locked)
            self.assertFalse(agent._prefetch_paused)
            self.assertFalse(metrics.measurement_active)
            self.assertEqual(metrics.measurement_generation, 2)
            self.assertEqual(installed, ['synthetic-online-policy', 'synthetic-online-policy'])

    return unittest.defaultTestLoader.loadTestsFromTestCase(Guards)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-guards', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.run_guards or args.output is None:
        parser.error('Explicit --run-guards and a new --output are required')
    if args.output.exists():
        raise FileExistsError(args.output)
    modules = {name: load(name, *entry) for name, entry in SOURCES.items()}
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(guard_suite(modules))
    report = dict(schema='robotron-fixed-slot64-engineering-guards-v1',
                  engineering_fixtures_only=True, quality_qualified=False,
                  runtime_validity_verified=False, full_game_score_verified=False,
                  tests_run=result.testsRun, successful=result.wasSuccessful(),
                  failures=len(result.failures), errors=len(result.errors),
                  source_sha256={name: entry[1] for name, entry in SOURCES.items()},
                  unittest_output=stream.getvalue())
    with args.output.open('x') as handle:
        os.fchmod(handle.fileno(), 0o444)
        json.dump(report, handle, allow_nan=False, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({k: report[k] for k in ('tests_run', 'successful', 'failures', 'errors',
                                           'engineering_fixtures_only', 'quality_qualified')}))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
