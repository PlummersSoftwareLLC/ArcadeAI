"""NEW generic source tests only; no old8/9/7 suite or live rollout.

Historical records seed synthetic current/mixed OUTPUT metadata. Only fake
executables and the exact frozen server's role-routing AST are evaluated.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
P = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load('_generic_preview_subset', HERE / 'declared_preview_subset_v1.py')
        cls.collector = load('_generic_map_collector', HERE / 'supervised_main_fleet_declared_subset_v1.py')
        prior = P / 'posttrial-slot163-authorities-and-readonly-reconciliation-original01'
        cls.fixtures = load('_old_fixture_definitions_NO_OLD_TESTS', prior / 'test_prospective_slot163_components_v1.py')
        cls.fixtures.Tests.setUpClass()
        corrected = P / 'posttrial-slot163-authorities-and-readonly-reconciliation-original02-guard-corrections'
        cls.rec = load('_corrected_prior_reconciler', corrected / 'prepare_slot163_readonly_reconciliation_v2.py')
        cls.accepted = load('_corrected_accepted_authority', corrected / 'posttrial_slot163_output_authority_v2.py')

    def fixture(self):
        fixture = self.fixtures.Tests(); fixture.rec = self.rec
        plan, old_read, values = fixture.fixture()
        prepared = fixture.prepare(plan, old_read)
        manifest = fixture.manifest; input_actors = fixture.census['actual_snapshot']['actors']
        before = dict(schema='robotron-preview-current-mixed-output-registry-v1',
            override_slots=[163], actors=copy.deepcopy(values['new_registry_snapshot']['actors']))
        before_roles = self.rec.roles(values['after_API'])
        after = copy.deepcopy(before); after['override_slots'] = [0, 1, 163]
        after_roles = copy.deepcopy(before_roles)
        for slot in (0, 1):
            actor = after['actors'][str(slot)]; actor['pid'] = 98_000_000 + slot
            actor['starttime_ticks'] += 30_000
            actor['command'][actor['command'].index('-autoboot_script') + 1] = manifest['target_lua']['path']
            actor['environment']['ROBOTRON_EVAL_MODE'] = '1' if manifest['slots'][str(slot)]['eval'] else '2'
            after_roles[str(slot)]['connection_id'] = 1_000_000 + slot
        return fixture, plan, old_read, values, prepared, manifest, input_actors, before, before_roles, after, after_roles

    def complete_plan(self):
        fixture, oldplan, oldread, values, prepared, manifest, inputs, before, roles, after, after_roles = self.fixture()
        pins = {key: dict(path='/CPUfixture/generic-' + key) for key in
            ('authority', 'selection', 'parent', 'policy', 'transition', 'binding', 'registry', 'snapshot', 'API', 'rollout')}
        table = {pins['policy']['path']: prepared['policy'], pins['transition']['path']: prepared['transition']}
        def read(entry, as_json=True):
            if entry['path'] in table: return copy.deepcopy(table[entry['path']])
            return oldread(entry, as_json)
        binding = self.rec.finalize(prepared, pins['policy'], pins['transition'], read)
        table[pins['binding']['path']] = binding
        manifest_pin = fixture.original_manifest_pin()
        authority = dict(schema='robotron-slot163-posttrial-output-authority-v1', mode=self.accepted.ACCEPT,
            root_selection=pins['selection'], fresh_parent_snapshot=pins['parent'],
            supervisor_owner=fixture.policy['fleet'],
            supervisor_process=values['before_snapshot']['owners']['fleet']['process'],
            prior_actor=before['actors']['163'], base_manifest=manifest_pin,
            output_lua=manifest['target_lua'], claim_directory=None)
        table[pins['authority']['path']] = authority
        table[pins['parent']['path']] = values['before_snapshot']
        table[pins['selection']['path']] = dict(schema='robotron-root-slot163-output-selection-v1',
            mode=authority['mode'], base_manifest=manifest_pin, output_lua=authority['output_lua'],
            fresh_parent_snapshot=pins['parent'], prior_actor=authority['prior_actor'],
            root_freeze_release=oldplan['root_freeze_release'], accepted_output_binding=pins['binding'],
            operational_benchmark_accepted=True)
        current = dict(before, actual_snapshot=pins['snapshot'], actual_API=pins['API'], actual_roles=roles)
        table[pins['registry']['path']] = current
        table[pins['snapshot']['path']] = values['new_registry_snapshot']
        table[pins['API']['path']] = values['after_API']
        plan = dict(schema='robotron-accepted-preview-declared-subset-plan-v1', override_slots=[0, 1, 163],
            accepted_one_slot_authority=pins['authority'], input_manifest=manifest_pin,
            current_output_registry=pins['registry'], fresh_parent_snapshot=pins['parent'],
            ROOT_rollout_selection=pins['rollout'])
        table[pins['rollout']['path']] = dict(schema='robotron-root-preview-declared-subset-selection-v1',
            accepted_one_slot_authority=pins['authority'], input_manifest=manifest_pin,
            current_output_registry=pins['registry'], fresh_parent_snapshot=pins['parent'],
            override_slots=[0, 1, 163], maximum_new_overrides=2)
        return fixture, plan, read, table, pins

    def test_train_eval_and_mixed_output_modes_use_original_INPUT(self):
        fixture, _, _, _, _, manifest, _, _, _, _, _ = self.fixture()
        self.assertFalse(manifest['slots']['0']['eval']); self.assertTrue(manifest['slots']['1']['eval'])
        for slot, mode, source in ((0, '2', 'target_lua'), (1, '1', 'target_lua'),
                                   (2, '0', 'original_lua'), (163, '1', 'target_lua')):
            row = manifest['slots'][str(slot)]; incoming = dict(row['expected_environment'])
            command, output = self.core.prepare_output(manifest, [0, 1, 163], row['expected_args'], incoming, fixture.execbase)
            self.assertEqual(command[command.index('-autoboot_script') + 1], manifest[source]['path'])
            expected = dict(incoming); expected['ROBOTRON_EVAL_MODE'] = mode
            self.assertEqual(output, expected)
            if slot in (0, 1):
                with self.assertRaises(ValueError):
                    self.core.prepare_output(manifest, [0, 1, 163], command[1:], output, fixture.execbase)

    def test_real_frozen_server_role_override_beats_new_CID_default(self):
        game = Path('/home/dave/source/repos/ArcadeAI/Robotron')
        source = (game / 'Scripts/dqn/socket_server.py').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), 'b552b2e83a9cc10cf7e4125cef22f571abe9189bd2ad3e63c6f48aa7df0e4516')
        tree = ast.parse(source)
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_is_eval_client')
        gate = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
            and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name)
            and n.test.left.id == 'eval_mode' and isinstance(n.test.ops[0], ast.Eq)
            and isinstance(n.test.comparators[0], ast.Constant) and n.test.comparators[0].value == 1
            and '_eval_override' in ast.unparse(n))
        namespace = dict(RL_CONFIG=types.SimpleNamespace(eval_client_stride=5, eval_client_offset=9))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), '<actual-role-method>', 'exec'), namespace)
        for mode, cid, expected in ((2, 4, False), (1, 0, True)):
            owner = types.SimpleNamespace(_eval_override={})
            env = dict(namespace, self=owner, eval_mode=mode, cid=cid, cs0={})
            exec(compile(ast.fix_missing_locations(ast.Module(body=[gate], type_ignores=[])), '<actual-handshake-override>', 'exec'), env)
            self.assertIs(namespace['_is_eval_client'](owner, cid), expected)
            self.assertIs(env['cs0']['eval_only'], expected)

    def test_declared_transition_changes_only_added_train_and_eval_slots(self):
        _, _, _, _, _, manifest, inputs, before, roles, after, after_roles = self.fixture()
        proof = self.core.validate_bounded_transition(before, after, manifest, inputs, roles, after_roles, 2)
        self.assertEqual(proof['newly_observed_upgraded_slots'], [0, 1])
        self.assertEqual(proof['contracts']['0']['eval_mode'], '2')
        self.assertEqual(proof['contracts']['1']['eval_mode'], '1')
        self.assertEqual(proof['contracts']['2']['eval_mode'], '0')
        for kind in ('oversize', 'unselected', 'role_drift', 'hot_relabel', 'remove'):
            changed = copy.deepcopy(after); changed_roles = copy.deepcopy(after_roles); cap = 2
            if kind == 'oversize': cap = 1
            if kind == 'unselected': changed['actors']['10']['pid'] += 1
            if kind == 'role_drift': changed_roles['0']['eval'] = True
            if kind == 'hot_relabel': changed['actors']['0']['pid'] = before['actors']['0']['pid']
            if kind == 'remove': changed['override_slots'] = [0, 1]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.core.validate_bounded_transition(before, changed, manifest, inputs, roles, changed_roles, cap)

    def test_generic_collector_validates_mixed_contracts_without163_special_case(self):
        fixture, _, _, values, _, manifest, inputs, _, _, after, roles = self.fixture()
        snapshot = copy.deepcopy(values['new_registry_snapshot']); snapshot['actors'] = after['actors']
        snapshot['previous_birth_probes'] = {slot: value['starttime_ticks'] for slot, value in after['actors'].items()}
        policy = self.core.prepare_policy(fixture.policy, manifest, [0, 1, 163], snapshot, roles,
                                         fixture.old['held_hashes'], inputs, self.collector)
        self.collector.validate_policy(policy)
        wrong = copy.deepcopy(policy); wrong['preview_slot_contracts']['0']['eval_mode'] = '1'
        with self.assertRaises(ValueError): self.collector.validate_policy(wrong)
        wrong = copy.deepcopy(policy); wrong['baseline_actors']['1']['environment']['ROBOTRON_EVAL_MODE'] = '0'
        with self.assertRaises(ValueError): self.collector.validate_policy(wrong)

    def test_complete_future_plan_uses_corrected_accepted_authority_and_separate_OUTPUT(self):
        fixture, plan, read, table, pins = self.complete_plan()
        context = self.core.validate_plan(plan, read, fixture.execbase, self.accepted, self.rec.roles)
        self.assertEqual(context['newly_declared_slots'], [0, 1])
        self.assertEqual(context['source_contracts']['0']['eval_mode'], '2')
        self.assertEqual(context['manifest']['slots']['0']['expected_environment']['ROBOTRON_EVAL_MODE'], '0')
        for kind in ('unaccepted', 'too_many', 'unfilled', 'OUTPUT_as_INPUT'):
            fixture, changed, read, table, pins = self.complete_plan()
            if kind == 'unaccepted': table[pins['selection']['path']]['operational_benchmark_accepted'] = False
            if kind == 'too_many': table[pins['rollout']['path']]['maximum_new_overrides'] = 1
            if kind == 'unfilled': changed['accepted_one_slot_authority'] = None
            if kind == 'OUTPUT_as_INPUT': table[pins['registry']['path']]['actors']['163']['environment']['ROBOTRON_EVAL_MODE'] = '0'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.core.validate_plan(changed, read, fixture.execbase, self.accepted, self.rec.roles)

    def test_subset_and_whole_collector_derivation_are_bounded(self):
        for value in ([0, 0], [192], [-1], [True], [1, 0], None):
            with self.subTest(value=value), self.assertRaises(ValueError): self.core.subset(value)
        proof = json.loads((HERE / 'bounded-collector-source-transform-definitions.json').read_text())
        selected = Path(proof['selected_path']).read_text()
        reverse = selected.replace(proof['inserted_contract_validator'], '', 1)
        for old, new in reversed(proof['exact_replacements']):
            self.assertEqual(reverse.count(new), 1); reverse = reverse.replace(new, old)
        self.assertEqual(reverse, Path(proof['parent_path']).read_text())

    def test_fake_train_and_eval_exec_and_default_cli_remain_inert(self):
        fixture, _, _, _, _, manifest, _, _, _, _, _ = self.fixture()
        with tempfile.TemporaryDirectory(prefix='generic preview fake ') as directory:
            fake = Path(directory) / 'fake MAME.py'
            fake.write_text('#!/usr/bin/python3.12\nimport os,json,sys\nprint(json.dumps(dict(argv=sys.argv,mode=os.environ["ROBOTRON_EVAL_MODE"])))\n')
            fake.chmod(0o555)
            for slot, mode in ((0, '2'), (1, '1')):
                row = manifest['slots'][str(slot)]
                command, env = self.core.prepare_output(manifest, [0, 1, 163], row['expected_args'],
                                                        dict(row['expected_environment']), fixture.execbase)
                self.assertEqual(command[0], '/usr/games/mame')
                env.pop('LD_PRELOAD')  # Test harness only, no MAME/shim execution.
                observed = subprocess.run([str(fake), *command[1:]], env=env,
                                          capture_output=True, text=True, timeout=10)
                self.assertEqual(observed.returncode, 0, observed.stderr)
                value = json.loads(observed.stdout); self.assertEqual(value['mode'], mode)
                self.assertEqual(value['argv'][value['argv'].index('-autoboot_script') + 1], manifest['target_lua']['path'])
        inert = subprocess.run(['/usr/bin/python3.12', '-I', '-B', str(HERE / 'declared_preview_subset_v1.py')],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(inert.returncode, 0); self.assertIn('PLAN_ONLY', inert.stdout)


if __name__ == '__main__':
    unittest.main()
