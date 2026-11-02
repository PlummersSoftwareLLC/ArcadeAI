"""Synthetic scheduling and actual read-only proof joins; never a real capture."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_tail9000_launcher_tests', P/'run-original-window.py')
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)


class ScheduledOnly(Exception):
    pass


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard, cls.reader, cls.control, cls.raw = launcher.dependencies()
        cls.scope_pin, cls.scope, cls.runtime = launcher.selected_chain(cls.reader, cls.control)
        cls.authority_proof = cls.reader.read_pin(cls.scope['authority_CPU'])

    def setUp(self):
        actual_run = subprocess.run
        def readonly_run(argv, *args, **kwargs):
            if isinstance(argv, (str, bytes)):
                raise AssertionError('Shell scheduling is forbidden in launcher tests')
            executable = Path(argv[0]).name
            if executable == 'systemd-run' or (executable == 'systemctl' and
                    (len(argv) < 3 or argv[1] != '--user' or argv[2] not in ('show', 'cat'))):
                raise AssertionError('All service scheduling/mutation is forbidden in launcher tests')
            return actual_run(argv, *args, **kwargs)
        dependency_patch = patch.object(launcher, 'dependencies', return_value=(self.guard, self.reader, self.control, self.raw))
        dependency_patch.start(); self.addCleanup(dependency_patch.stop)
        command_patch = patch.object(self.control, 'command', side_effect=AssertionError('No selected control command is authorized in tests'))
        command_patch.start(); self.addCleanup(command_patch.stop)
        run_patch = patch.object(subprocess, 'run', side_effect=readonly_run)
        run_patch.start(); self.addCleanup(run_patch.stop)

    def test_process_wide_guard_blocks_fresh_controller_scheduling_and_unit_mutations(self):
        for argv in (['systemd-run', '--user', '/bin/true'], ['systemctl', '--user', 'start', 'anything'],
                     ['systemctl', '--user', 'stop', 'anything'], ['systemctl', '--user', 'reset-failed', 'anything']):
            with self.subTest(argv=argv), self.assertRaisesRegex(AssertionError, 'forbidden'):
                subprocess.run(argv)

    def test_launcher_uses_the_same_dependency_instance_that_tests_intercept(self):
        self.assertIs(launcher.dependencies()[2], self.control)

    def selected(self):
        return launcher.selected_chain(self.reader, self.control)

    def verify_aux(self, proof=None, control=None, runtime=None):
        return launcher.verify_CPU_proof(proof or self.authority_proof, self.scope['authority_source'],
            'authority', self.reader, control or self.control, runtime or self.runtime)

    def test_completed166_actual_CPU_proofs_and_new_package_join_readonly(self):
        pin, scope, runtime = self.selected()
        self.assertEqual(pin, self.scope_pin)
        self.assertEqual(scope['total_actual_passed_CPU_tests'], 166)
        self.assertEqual(scope['source_package']['sha256'], '3ee43f9bd95fdda8f02abc048999a84513da71125dfd6b2e6558f45d2de6caf9')
        self.assertNotIn('torch', sys.modules); self.assertNotIn('numpy', sys.modules)

    def test_construction_is_exact_declared_transition_from_sealed_parent(self):
        report = json.loads((P/'launcher-source-construction.json').read_bytes())
        raw = Path(report['parent']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), report['parent_sha256'])
        value = raw.decode()
        for transition in report['transitions']:
            self.assertEqual(value.count(transition['before']), transition['occurrences'])
            value = value.replace(transition['before'], transition['after'])
        new = (P/'run-original-window.py').read_bytes()
        self.assertEqual(value.encode(), new)
        self.assertEqual(hashlib.sha256(new).hexdigest(), report['target_sha256'])

    def test_original_observation_release_and_dependency_functions_are_AST_identical(self):
        parent = launcher.R/'post-supervised-main-next8M-original01-preparation-20261019/run-original-window.py'
        def functions(path):
            return {n.name: ast.dump(n) for n in ast.parse(path.read_bytes()).body if isinstance(n, ast.FunctionDef)}
        old, new = functions(parent), functions(P/'run-original-window.py')
        for name in ('require', 'load', 'dependencies', 'observe'):
            self.assertEqual(old[name], new[name], name)

    def test_original_scheduling_identity_and_resource_block_remain_AST_identical(self):
        parent = launcher.R/'post-supervised-main-next8M-original01-preparation-20261019/run-original-window.py'
        def scheduling(path):
            function = next(n for n in ast.parse(path.read_bytes()).body if isinstance(n, ast.FunctionDef) and n.name == 'launch')
            index = next(i for i, node in enumerate(function.body) if isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'argv')
            return ast.dump(ast.Module(body=function.body[index:], type_ignores=[]))
        self.assertEqual(scheduling(parent), scheduling(P/'run-original-window.py'))

    def test_simulated_one_scheduling_attempt_preserves_fresh9000_and_first_both_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'run-original-window.py'
            source.write_bytes((P/'run-original-window.py').read_bytes())
            scheduled = Mock(side_effect=ScheduledOnly('synthetic scheduling boundary; no service started'))
            CPU_gate = Mock()
            with patch.object(launcher, 'P', root), patch.object(launcher, 'OUT', root/'unused-window-output'),\
                 patch.object(launcher, '__file__', str(source)), patch.object(launcher, 'require_launcher_CPU', CPU_gate),\
                 patch.object(launcher, 'selected_chain', return_value=(self.scope_pin, self.scope, self.runtime)),\
                 patch.object(self.control, 'command', scheduled):
                with self.assertRaises(ScheduledOnly): launcher.launch()
            CPU_gate.assert_called_once(); scheduled.assert_called_once()
            job = json.loads((root/'job.json').read_bytes())
            self.assertEqual(job['policy'], dict(learner_frames=8_000_000, accepted_dqn_epsilon=8_000_000,
                poll_s=1, maximum_observation_gap_s=30, maximum_API_age_s=5, no_applied_optimizer_s=60, one_capture_only=True))
            self.assertEqual(len(job['actors']), 192); self.assertEqual(len(job['held_hashes']), 195)
            self.assertEqual(job['quality_precommit']['same_fixed_admission_s'], 5400)
            self.assertEqual(job['quality_precommit']['same_whole_cohort_timeout_s'], 9000)
            self.assertEqual(job['quality_precommit']['source_package'], self.scope['source_package'])
            self.assertEqual(job['clock_budget_clarification'], self.scope['clock_budget_clarification'])
            self.assertEqual(job['quality_precommit']['max_attempts'], 1)
            self.assertFalse(job['quality_precommit']['extensions'])
            self.assertEqual(job['tag'], 'scorecarry849_LR25_finalcopy_fresh_next8M_01_20261020')
            selection = json.loads((root/'root-selection.json').read_bytes())
            self.assertEqual(selection['completed_source_scope'], self.scope_pin)
            self.assertEqual(selection['source_package'], self.scope['source_package'])
            self.assertFalse(selection['quality_qualified']); self.assertFalse(selection['promotion'])
            actual = scheduled.call_args.args[2]
            self.assertIn('--property=RuntimeMaxSec=5600', actual)
            self.assertIn('--property=MemoryMax=512M', actual)
            self.assertIn('--property=CPUQuota=100%', actual)
            self.assertIn('--property=SendSIGKILL=no', actual)
            self.assertFalse((root/'unused-window-output').exists())

    def test_default_CLI_inert(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(P/'run-original-window.py')],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0); self.assertTrue(result.stdout.startswith('PLAN_ONLY:'))
        self.assertEqual(result.stderr, '')

    def test_missing_original_launcher_CPU_proof_refuses_without_baseline(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(launcher, 'P', Path(directory)):
            with self.assertRaises(FileNotFoundError):
                launcher.require_launcher_CPU(self.reader, self.control, self.runtime)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_wrong_completed_scope_hash_refuses_before_unit_queries(self):
        pin = self.reader.pin
        def changed(path):
            value = pin(path)
            if Path(path).name == 'root-source-scope-and-selected-chain-readback.json':
                value = dict(value, sha256='0'*64)
            return value
        with patch.object(self.reader, 'pin', side_effect=changed), patch.object(self.control, 'show') as show:
            with self.assertRaises(ValueError): self.selected()
            show.assert_not_called()

    def test_wrong_CPU_source_refuses(self):
        proof = copy.deepcopy(self.authority_proof); proof['source']['sha256'] = '0'*64
        with self.assertRaises(ValueError): self.verify_aux(proof)

    def test_failed_skipped_foreign_or_numerical_CPU_report_refuses(self):
        actual = self.reader.read_pin; key = self.authority_proof['actual_tests']
        for field, value in [('actual_tests_run', 1), ('skipped', 1), ('passed', False),
                             ('numerical_runtime_imported', True), ('actual_quality_run', True)]:
            def changed(entry, as_json=True):
                result = actual(entry, as_json=as_json)
                if entry == key: result = dict(result, **{field: value})
                return result
            with self.subTest(field=field), patch.object(self.reader, 'read_pin', side_effect=changed):
                with self.assertRaises(ValueError): self.verify_aux()

    def test_wrong_archived_CPU_command_or_resource_refuses(self):
        actual = self.runtime.archived_closure
        for field, value in [('RuntimeMaxUSec', '4min'), ('CPUQuotaPerSecUSec', '4s'),
                             ('Restart', 'always'), ('ExecStart', '{ invalid }')]:
            def fields(*args, **kwargs):
                result = actual(*args, **kwargs); return dict(result, **{field: value})
            runtime = SimpleNamespace(archived_closure=fields, duration_seconds=self.runtime.duration_seconds)
            with self.subTest(field=field), self.assertRaises(ValueError): self.verify_aux(runtime=runtime)

    def test_nonzero_actual_CPU_exit_cannot_be_rescued_by_valid_test_report(self):
        actual = self.reader.read_pin; key = self.authority_proof['original_closure']
        def changed(entry, as_json=True):
            result = actual(entry, as_json=as_json)
            return dict(result, original_exit=1) if entry == key else result
        with patch.object(self.reader, 'read_pin', side_effect=changed), self.assertRaises(ValueError): self.verify_aux()

    def test_still_loaded_original_CPU_unit_refuses(self):
        control = SimpleNamespace(show=lambda unit: dict(LoadState='loaded'))
        with self.assertRaises(ValueError): self.verify_aux(control=control)

    def test_foreign_runtime_package_or_extended_entry_deadline_refuses(self):
        actual = self.reader.read_pin
        for kind in ('package', 'clock'):
            def changed(entry, as_json=True):
                result = actual(entry, as_json=as_json)
                if as_json and kind == 'package' and entry == self.scope_pin:
                    result = copy.deepcopy(result); result['source_package']['sha256'] = '0'*64
                elif as_json and kind == 'clock' and entry == self.scope['clock_budget_clarification']:
                    result = dict(result, fixed_entry_based_timeout_s=10000)
                return result
            with self.subTest(kind=kind), patch.object(self.reader, 'read_pin', side_effect=changed):
                with self.assertRaises(ValueError): self.selected()


    def test_new_followup12_scope_must_be_CPU_only_before_baseline(self):
        actual=self.reader.read_pin;key=self.scope['followup_CPU']
        def changed(entry,as_json=True):
            value=actual(entry,as_json=as_json)
            if as_json and entry==key:
                value=copy.deepcopy(value);value['actual_tests']['actual_candidate_captured']=True
            return value
        with patch.object(self.reader,'read_pin',side_effect=changed),self.assertRaises(ValueError):self.selected()
        self.assertFalse((P/'job.json').exists())

    def test_new_guard_source_cannot_be_changed_in_prospective_packet(self):
        actual=self.reader.read_pin
        def changed(entry,as_json=True):
            value=actual(entry,as_json=as_json)
            if as_json and entry==self.scope_pin:
                value=copy.deepcopy(value);value['selected_sources']['quality32_runtime_guard_v6.py']['sha256']='0'*64
            return value
        with patch.object(self.reader,'read_pin',side_effect=changed),self.assertRaises(ValueError):self.selected()
        self.assertFalse((P/'job.json').exists())

    def test_previous_failed_quality_original_must_remain_closed(self):
        bundle=self.reader.read_pin(self.scope['preceding_quality_bundle'])
        owner=self.reader.read_pin(bundle['native_owner']);actual=self.control.show
        def changed(unit):
            return dict(Id=unit,LoadState='loaded') if unit==owner['unit'] else actual(unit)
        with patch.object(self.control,'show',side_effect=changed),self.assertRaises(ValueError):self.selected()
        self.assertFalse((P/'job.json').exists())


if __name__ == '__main__':
    unittest.main()
