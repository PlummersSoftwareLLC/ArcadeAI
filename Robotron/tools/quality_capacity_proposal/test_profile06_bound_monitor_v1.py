"""Root inspection with actual join/exposure predicates and synthetic OS state."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import monitor_supervised_quality32_v5 as monitor
import supervised_main_fleet_v1 as fleet
import supervised_main_observations_v1 as joins
import quality32_runtime_guard_v8 as observer
import review_closed_quality32_v8 as reviewer
import test_supervised_main_fleet_v1 as census_fixtures
import test_supervised_main_observations_v1 as fixtures


class PrefixTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.JoinTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.modules = dict(supervision=fleet, joins=joins, wire=fixtures.wire)
        self.manifest, self.samples, self.expected = self.f.observations()
        self.pins = [self.f.put('main-samples/'+f'{i:04d}.json', row) for i, row in enumerate(self.samples)]

    def replay(self, pins=None):
        return monitor.accepted_prefix(self.pins if pins is None else pins, self.f.main,
            self.f.policy, self.f.read, self.modules)

    def test_complete_prefix_preserves_original_counts_and_recovery_state(self):
        state, samples, wires, censuses = self.replay()
        self.assertEqual(state, self.expected)
        self.assertEqual([row['API']['client_count'] for row in samples], [192, 191, 191, 192])
        self.assertEqual(len(wires), 4)
        self.assertEqual(len(censuses), 4)
        monitor.validate_prefix_exposure(self.f.main, samples, fixtures.runtime, fixtures.window)
        self.assertEqual(self.f.read(self.pins[1])['API']['client_count'], 191)

    def test_partial_prefix_can_report_pending_without_claiming_closed_quality(self):
        state, samples, wires, censuses = self.replay(self.pins[:2])
        self.assertIsNotNone(state['pending'])
        self.assertFalse(state['full_capacity'])
        monitor.validate_prefix_exposure(self.f.main, samples, fixtures.runtime, fixtures.window)
        state, samples, _, _ = monitor.accepted_prefix(self.pins[2:], self.f.main, self.f.policy,
            self.f.read, self.modules, state, samples, wires, censuses)
        self.assertEqual(state, self.expected)

    def test_original_projection_reused_wire_census_or_forged_state_fails(self):
        for problem in ['projection', 'wire', 'census', 'state', 'role', 'legacy_actor_claim']:
            with self.subTest(problem=problem):
                changed = copy.deepcopy(self.samples[1])
                if problem == 'projection':
                    changed['API']['client_count'] = 192
                elif problem == 'wire':
                    changed.update({key: self.samples[0][key] for key in
                        ('API', 'API_wire', 'API_witness_format', 'API_nonfinite_paths')})
                elif problem == 'census':
                    changed['main_fleet_snapshot'] = self.samples[0]['main_fleet_snapshot']
                elif problem == 'state':
                    changed['main_fleet_state_sha256'] = 'f'*64
                elif problem == 'role':
                    compact = self.f.read(changed['main_fleet_snapshot'])
                    compact['actors']['1']['role_sha256'] = 'f'*64
                    changed['main_fleet_snapshot'] = self.f.put('bad-role.json', compact)
                else:
                    changed['original192_actors_verified'] = True
                pins = [self.pins[0], self.f.put('changed-'+problem+'.json', changed)]
                with self.assertRaises(ValueError):
                    self.replay(pins)

    def test_sequence_holes_are_not_silently_skipped(self):
        directory = self.f.root/'sequence'
        self.f.put('sequence/0000.json', {})
        self.f.put('sequence/0002.json', {})
        with self.assertRaises(ValueError):
            monitor.sample_files(directory)

    def test_progress_and_source_health_checks_remain_active_after_recovery(self):
        _, samples, _, _ = self.replay()
        for problem in ['epoch', 'clock', 'source', 'autosave']:
            changed = copy.deepcopy(samples)
            if problem == 'epoch':
                changed[2]['API']['host_pipeline']['learning_exposure']['optimizer']['epoch'] += 1
            elif problem == 'clock':
                changed[2]['API']['learner_frame_count'] = 0
            elif problem == 'source':
                changed[2]['held_hashes_sha256'] = 'f'*64
            else:
                changed[2]['autosave']['age_s'] = 361
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                monitor.validate_prefix_exposure(self.f.main, changed, fixtures.runtime, fixtures.window)


class WholeInspectionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.JoinTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.manifest, self.samples, self.final = self.f.observations()
        self.Q = self.f.root
        self.bindings = self.Q/'runtime-bindings'
        self.sample_pins = [self.f.put('runtime-bindings/main-samples/'+f'{i:04d}.json', row)
                            for i, row in enumerate(self.samples)]
        (self.bindings/'main-rejections').mkdir()
        self.main = dict(self.f.main)
        self.main.pop('baseline_API_value')
        self.main['baseline_API'] = self.f.put('baseline-API.raw', json.dumps(self.f.baseline, allow_nan=True).encode())
        self.native = dict(pid=900, starttime_ticks=90, unit='synthetic-native.service', cgroup='/synthetic-native')
        self.outer = dict(pid=901, starttime_ticks=91, unit='synthetic-outer.service', cgroup='/synthetic-outer')
        self.campaign = self.Q/'campaign'
        self.campaign.mkdir()
        self.record = dict(index=1, role='reference', state='running', pid=1001,
            receipt_path=str(self.campaign/'receipt.json'), console_log=str(self.campaign/'console.log'),
            evaluator_status_path=str(self.campaign/'status-leg.json'))
        self.plan = dict(legs=[dict(index=1, role='reference', command=['synthetic-evaluator'],
            **{key: self.record[key] for key in ('receipt_path', 'console_log', 'evaluator_status_path')})])
        self.plan_pin = self.f.put('campaign/plan.json', self.plan)
        self.f.put('campaign/status.json', dict(state='running', current_leg=1, plan_sha256=self.plan_pin['sha256'], legs=[self.record]))
        self.evaluator = dict(pid=1001, starttime_ticks=101, affinity=[4, 5])
        self.actors = {str(slot): dict(pid=20000+slot, starttime_ticks=20000+slot, affinity=[4, 5],
            command=['/usr/games/mame', 'synthetic']) for slot in observer.SLOTS}
        self.f.put('runtime-bindings/leg-births/leg1-evaluator.json', self.evaluator)
        self.f.put('runtime-bindings/leg-births/leg1-actors.json', self.actors)
        self.display = dict(phase='collecting', actor_pids={slot: row['pid'] for slot, row in self.actors.items()},
            boundary=dict(ready=True, acknowledged=32), count=50, started=82, pending=32, abandoned=0)
        self.f.put('campaign/status-leg.json', self.display)
        self.roles = {name: self.f.put(name+'.pt', b'synthetic bytes, never loaded') for name in ('reference', 'candidate')}
        self.binding = dict(**self.roles,
            main_holds={key: self.main[key] for key in ('owner', 'actors', 'held_hashes', 'experiment', 'supervision_policy')},
            expected_window=dict(owner=self.main['owner']),
            campaign=dict(native_unit=self.native['unit'], output_directory=str(self.campaign), plan_sha256=self.plan_pin['sha256']))
        self.sources = {key: fixtures.reader.pin(path) for key, (path, _) in monitor.SOURCES.items()}
        self.job = dict(preparation=str(self.Q), campaign=str(self.campaign), sources=self.sources,
            campaign_binding=self.f.put('campaign-binding.json', self.binding), main_binding=self.f.put('main-binding.json', self.main),
            native_config=self.f.put('native-config.json', dict(unit=self.native['unit'], argv=['synthetic-native'], guard_source=self.sources['observer'])),
            outer_plan=self.f.put('outer-plan.json', dict(unit=self.outer['unit'], argv=['synthetic-outer'])),
            native_owner=self.f.put('native-owner.json', self.native), outer_owner=self.f.put('outer-owner.json', self.outer))
        self.window = SimpleNamespace(owner_and_files=Mock(), healthy=fixtures.window.healthy, process_start=Mock(return_value=None))
        self.actuals = {1001: self.evaluator, **{row['pid']: row for row in self.actors.values()}}
        self.private = SimpleNamespace(SLOTS=observer.SLOTS, validate_records=observer.validate_records,
            live_process=lambda pid, parent, group, command: copy.deepcopy(self.actuals[pid]))
        self.modules = dict(supervision=fleet, joins=joins, runtime=fixtures.runtime, window=self.window,
                            observer=self.private, control=Mock(), wire=fixtures.wire, reviewer=reviewer)
        model = self.Q/'models_dqn/robotron_dqn_latest.pt'
        model.parent.mkdir()
        model.write_bytes(b'only a synthetic freshness fixture')
        os.utime(model, (1000125, 1000125))
        self.current = fixtures.api(self.f.main, 1000130.1, 4)
        self.current['fps'] = 7780.

    def run_inspection(self, native_live=True):
        def unit(owner, *args):
            return dict(original=owner, live=native_live if owner['pid'] == 900 else True, actual_exit=None if native_live else 0,
                closure=None, start_monotonic_s=101, exit_monotonic_s=None if native_live else 129)
        def census(policy, state):
            value = census_fixtures.snapshot(policy, state, 130.1)
            return value
        with patch.object(monitor, 'original_unit', side_effect=unit), patch.object(fleet, 'collect', side_effect=census),\
             patch.object(monitor, 'G', self.Q), patch.object(monitor.time, 'time', return_value=1000130.2),\
             patch.object(monitor.time, 'monotonic', return_value=130.2),\
             patch.object(monitor.urllib.request, 'urlopen', return_value=SimpleNamespace(read=lambda bound: json.dumps(self.current, allow_nan=True).encode())):
            return monitor.inspect(self.job, fixtures.reader, self.modules)

    def test_whole_inspection_rejoins_recovery_and_keeps_private32_strict(self):
        report, raw = self.run_inspection()
        self.assertEqual(report['published_main_recoveries'], 1)
        self.assertEqual(report['main']['client_count'], 192)
        self.assertEqual(report['legs'][0]['verified_actor_births'], 32)
        self.assertFalse(report['quality_qualified'])
        self.assertFalse(report['scientific_approval_inferred'])
        self.assertFalse(report['main_or_private_runtime_changed'])
        self.assertEqual(fixtures.wire.parse_wire(raw)['client_count'], 192)
        self.window.owner_and_files.assert_called_once()

    def test_private_actor_replacement_or_affinity_change_is_rejected(self):
        for key in ('starttime_ticks', 'affinity'):
            row = self.actuals[24096]
            original = copy.deepcopy(row)
            row[key] = row[key]+1 if key == 'starttime_ticks' else [6]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_inspection()
            self.actuals[24096] = original

    def test_extra_current_main_client_is_rejected(self):
        self.current['client_count'] = 193
        with self.assertRaises(ValueError):
            self.run_inspection()

    def test_current_counter_restart_or_regression_is_rejected(self):
        for problem in ('epoch', 'clock'):
            value = copy.deepcopy(self.current)
            if problem == 'epoch':
                self.current['host_pipeline']['learning_exposure']['replay']['epoch'] += 1
            else:
                self.current['learner_frame_count'] = 0
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.run_inspection()
            self.current = value

    def test_nonfinite_optional_FPS_is_preserved_in_wire_without_false_health_claim(self):
        self.current['fps'] = float('inf')
        report, raw = self.run_inspection()
        self.assertIsNone(report['main']['fps'])
        self.assertEqual(fixtures.wire.parse_wire(raw)['fps'], float('inf'))

    def test_original_guard_rejection_is_never_ignored(self):
        self.f.put('runtime-bindings/main-rejections/0000.json', dict(error='original guard rejected'))
        with self.assertRaises(ValueError):
            self.run_inspection()

    def test_post_native_exit_can_only_keep_exact_final_registry(self):
        report, _ = self.run_inspection(native_live=False)
        self.assertEqual(report['classification'], 'ORIGINAL_NATIVE_TERMINAL_AWAITING_FINAL_DISPOSITION')
        self.assertFalse(report['quality_qualified'])
        self.assertEqual(report['published_main_recoveries'], 1)

    def test_terminal_private_cleanup_waits_for_original_parent_without_false_live_claim(self):
        self.display.pop('actor_pids')
        self.display.update(phase='finished', complete=True, valid=True, pending=0,
            count=82, socket_wait=dict(actors={slot: dict(pid=actor['pid']) for slot, actor in self.actors.items()}))
        self.f.put('campaign/status-leg.json', self.display)
        self.private.live_process = Mock(side_effect=AssertionError('Already stopped private children are not live'))
        report, _ = self.run_inspection()
        leg = report['legs'][0]
        self.assertEqual(leg['phase'], 'finished_waiting_original_parent_exit')
        self.assertEqual(leg['live_actor_births_verified'], 0)
        self.assertFalse(report['quality_qualified'])

    def test_terminal_private_cleanup_cannot_hide_missing_tail(self):
        self.display.update(phase='finished', complete=True, valid=True, pending=1,
            socket_wait=dict(actors={slot: dict(pid=actor['pid']) for slot, actor in self.actors.items()}))
        self.f.put('campaign/status-leg.json', self.display)
        with self.assertRaises(ValueError):
            self.run_inspection()

    def test_actual_terminal_display_shape_keeps_original_actor_pids_during_cleanup(self):
        self.display.update(phase='finished', complete=True, valid=True, pending=0, count=82)
        self.f.put('campaign/status-leg.json', self.display)
        report, _ = self.run_inspection()
        self.assertEqual(report['legs'][0]['phase'], 'finished_waiting_original_parent_exit')
        self.assertEqual(report['legs'][0]['counts']['pending'], 0)

    def test_changed_plan_or_pending_partition_cannot_be_reported_healthy(self):
        self.display['pending'] = 31
        self.f.put('campaign/status-leg.json', self.display)
        with self.assertRaises(ValueError):
            self.run_inspection()

    def test_missing_private_registry_after_measurement_never_adopted(self):
        (self.bindings/'leg-births/leg1-evaluator.json').unlink()
        with self.assertRaises(ValueError):
            self.run_inspection()

    def test_default_cli_performs_no_inspection(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(monitor.__file__))], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith('PLAN_ONLY:'))
        self.assertEqual(result.stderr, '')


if __name__ == '__main__':
    unittest.main()
