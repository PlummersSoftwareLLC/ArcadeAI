"""Metadata registration uses captured births; synthetic service probes only."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import prepare_supervised_quality32_monitor_v3 as prepare
import monitor_supervised_quality32_v3 as monitor
import test_monitor_supervised_quality32_v3 as fixtures


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.WholeInspectionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.reader = fixtures.fixtures.reader
        self.monitor_pin = self.reader.pin(prepare.MONITOR)
        self.pre = dict(schema='robotron-supervised-quality32-followup-precommit-v1', original_attempt=1, no_retry=True,
            campaign_preparation=str(self.f.Q), native_unit=self.f.native['unit'], outer_unit=self.f.outer['unit'],
            campaign_parameters=dict(directory=str(self.f.campaign)), selected_sources={
                name: self.f.sources[key] for name, key in [('quality32_runtime_guard_v6.py', 'observer'),
                ('supervised_main_fleet_v1.py', 'supervision'), ('supervised_main_observations_v1.py', 'joins'),
                ('review_closed_quality32_v6.py', 'reviewer')]})
        self.f.f.put('runtime-bindings/native-owner.json', dict(self.f.native, observed_live=True))
        self.f.f.put('outer-controller-execution/root-original-live-owner.json', dict(self.f.outer, observed_live=True))
        self.f.f.put('original-native-controller-config.json', self.reader.read_pin(self.f.job['native_config']))
        self.f.f.put('original-outer-launch-plan.json', self.reader.read_pin(self.f.job['outer_plan']))
        self.f.f.put('runtime-bindings/campaign-binding.json', self.f.binding)
        self.f.f.put('runtime-bindings/main-binding.json', self.f.main)
        self.pin = self.f.f.put('precommit.json', self.pre)
        self.actual_checked = self.reader.checked_module
        self.probes = Mock(return_value=dict(live=True))

    def checked(self, name, entry):
        module = self.actual_checked(name, entry)
        if entry == self.monitor_pin:
            module.original_unit = self.probes
        return module

    def run_preparation(self):
        with patch.object(self.reader, 'checked_module', side_effect=self.checked):
            return prepare.prepare(self.pin, self.monitor_pin, self.reader)

    def assert_no_monitor_output(self):
        self.assertFalse((self.f.Q/'root-live-monitor-job.json').exists())
        self.assertFalse((self.f.Q/'root-live-monitor-registration.json').exists())
        self.assertFalse((self.f.Q/'root-live-monitor').exists())

    def test_preparation_binds_same_original_owners_and_new_source_chain(self):
        result = self.run_preparation()
        job = self.reader.read_pin(result['job'])
        self.assertEqual(job['sources'], self.f.sources)
        self.assertEqual(job['monitor_source'], self.monitor_pin)
        self.assertEqual(self.reader.read_pin(job['native_owner'])['pid'], self.f.native['pid'])
        self.assertEqual(self.probes.call_count, 2)
        self.assertIn(result['job']['sha256'], result['command'])
        self.assertFalse(self.reader.read_pin(result['registration'])['scientific_runtime_changed'])
        self.assertFalse((self.f.Q/'root-live-monitor').exists())

    def test_missing_original_birth_refuses_registration_before_any_output(self):
        (self.f.Q/'runtime-bindings/native-owner.json').unlink()
        with self.assertRaises(ValueError):
            self.run_preparation()
        self.assert_no_monitor_output()
        self.probes.assert_not_called()

    def test_ended_original_cannot_be_adopted_as_a_new_live_registration(self):
        self.probes.return_value = dict(live=False)
        with self.assertRaises(ValueError):
            self.run_preparation()
        self.assert_no_monitor_output()

    def test_wrong_units_or_retry_permission_cannot_change_scope(self):
        for problem in ('unit', 'retry'):
            value = copy.deepcopy(self.pre)
            if problem == 'unit':
                value['native_unit'] = 'other.service'
            else:
                value['no_retry'] = False
            self.pin = self.f.f.put('precommit.json', value)
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.run_preparation()
            self.assert_no_monitor_output()

    def test_changed_selected_observer_is_rejected(self):
        self.pre['selected_sources']['quality32_runtime_guard_v6.py'] = dict(self.f.sources['observer'], sha256='f'*64)
        self.pin = self.f.f.put('precommit.json', self.pre)
        with self.assertRaises(ValueError):
            self.run_preparation()
        self.assert_no_monitor_output()
        self.probes.assert_not_called()

    def test_existing_registration_is_never_overwritten(self):
        result = self.run_preparation()
        original = self.reader.read_pin(result['job'], as_json=False)
        with self.assertRaises(ValueError):
            self.run_preparation()
        self.assertEqual(self.reader.read_pin(result['job'], as_json=False), original)

    def test_default_cli_is_inert(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(prepare.__file__))], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith('PLAN_ONLY:'))
        self.assertEqual(result.stderr, '')


class OriginalUnitTests(unittest.TestCase):
    def setUp(self):
        self.reader = fixtures.fixtures.reader
        self.window = fixtures.fixtures.window
        self.runtime = fixtures.fixtures.runtime
        self.control = fixtures.fixtures.module(H/'control_quality32_review_v1.py', 'control_for_root_unit_tests')
        self.pid = os.getpid()
        self.owner = dict(pid=self.pid, starttime_ticks=self.window.process_start(self.pid), unit='synthetic-root-inspector.service',
            invocation_id='a'*32, cgroup='/synthetic-root-inspector')
        self.shown = dict(MainPID=str(self.pid), InvocationID='a'*32, NRestarts='0', ControlGroup=self.owner['cgroup'],
                          ExecMainStartTimestampMonotonic='1000000')
        self.argv = [value.decode() for value in Path('/proc', str(self.pid), 'cmdline').read_bytes().split(b'\0') if value]

    def invoke(self):
        with patch.object(self.control, 'show', return_value=self.shown):
            return monitor.original_unit(self.owner, Path('/missing/original-closure.json'), self.argv,
                self.reader, self.control, self.runtime, self.window)

    def test_live_original_pid_birth_and_argv_are_rejoined(self):
        result = self.invoke()
        self.assertTrue(result['live'])
        self.assertIsNone(result['actual_exit'])

    def test_unit_replacement_restart_or_changed_command_is_rejected(self):
        for key, value in [('InvocationID', 'b'*32), ('NRestarts', '1'), ('ControlGroup', '/foreign')]:
            before = dict(self.shown)
            self.shown[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.invoke()
            self.shown = before
        self.argv = ['different', 'command']
        with self.assertRaises(ValueError):
            self.invoke()

    def test_loaded_terminal_original_reports_actual_exit_without_releasing(self):
        self.owner.update(pid=9900000, starttime_ticks=42)
        self.shown.update(Id=self.owner['unit'], MainPID='0', LoadState='loaded', ExecMainPID=str(self.pid),
            ExecMainCode='1', ExecMainStatus='1', SubState='failed', ExecMainExitTimestampMonotonic='2000000')
        self.shown['ExecMainPID'] = str(self.owner['pid'])
        result = self.invoke()
        self.assertFalse(result['live'])
        self.assertEqual(result['actual_exit'], 1)
        self.assertIsNone(result['closure'])

    def test_absent_unit_without_original_archive_cannot_be_accepted(self):
        self.shown = dict(LoadState='not-found')
        with self.assertRaises(FileNotFoundError):
            self.invoke()


if __name__ == '__main__':
    unittest.main()
