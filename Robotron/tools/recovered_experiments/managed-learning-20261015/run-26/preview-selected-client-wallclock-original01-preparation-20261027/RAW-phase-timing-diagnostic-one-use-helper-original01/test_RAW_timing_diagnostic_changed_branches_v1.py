"""Two focused diagnostic-scope/count cases using immutable current221 metadata.

ROOT selection/authority are explicit CPU fixtures. No live process/API reads,
claims, exec, MAME, Torch or models. Negative mutations remain in memory only.
The unchanged three earlier NEXT helper cases are deliberately not rerun.
"""
import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
P = HERE.parent
F = P / 'fast-preview-rgb565-capture-original01-preparation-20261027'
PROOF = F / 'raw-format1-existing-wire-policy-original01/timing-instrumented-RAW-source-only-original01/RAW-phase-timing-source-and-semantics-proof-original01.json'
BINDING = P / 'actual-raw-preview-one-use-original03-20261027/readonly-current-output-to-RAW221-reconciliation-original01/actual-RAW221-main-binding-original01.json'
INPUT = P / 'actual-selected-preview30-trial-original01-20261027/actual-fresh-slot163-original-INPUT-manifest.json'


def load(path, sha, name):
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == sha
    module = types.ModuleType(name); module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.dont_write_bytecode = True
        cls.helper = load(HERE / 'exec_RAW_timing_diagnostic_once_v3.py',
            'b805703e1782f1fa0db2453fb96d6446deb25c0c719d038da170019e274f83a0', '_raw_changed_helper')
        cls.fuse = load(P / 'role-bound-wrapper-trial-original02-single-use/exec_role_bound_mame_once_v2.py',
            'b5fdc64b6777e6db2541f7c535be2fc49e47f5b565dcd714086cdb33d6041723', '_raw_existing_fuse')
        cls.base, _ = cls.fuse.load_base(P / 'role-bound-wrapper-trial-original01/exec_role_bound_mame_v1.py')
        cls.guards = load(P / 'posttrial-slot163-authorities-and-readonly-reconciliation-original02-guard-corrections/posttrial_slot163_output_authority_v2.py',
            '9a8fe7c08e1e941e2d26a2cc3c65124b27129b9f470a0020453e33010bf32027', '_raw_existing_guards')
        cls.binding_pin = cls.pin(BINDING)
        assert cls.binding_pin['sha256'] == '02313a4f2e5c810f1f88383c15d57ddb5bba98d43f2eee11760c4cde0e5e3fbc'
        cls.binding = cls.base.strict_json(cls.base.read_bytes_pin(cls.binding_pin))
        cls.policy = cls.base.strict_json(cls.base.read_bytes_pin(cls.binding['supervision_policy']))
        cls.proof_pin = cls.pin(PROOF)
        assert cls.proof_pin['sha256'] == '3123b38903259d98d98d6297953395e3ea45e4da926675fd7d711b4e2b145295'
        cls.proof = cls.base.strict_json(cls.base.read_bytes_pin(cls.proof_pin))
        cls.input_pin = cls.pin(INPUT)
        cls.manifest = cls.base.read_manifest(cls.input_pin['path'], cls.input_pin['sha256'])

    @classmethod
    def pin(cls, path):
        data = path.read_bytes()
        return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
                    identity=cls.fuse.identity(path.lstat()))

    def fixture(self, directory):
        directory.chmod(0o700)
        pins = {key: dict(path='/CPUfixture/RAW-' + key)
                for key in ('authority', 'selection', 'release', 'fresh')}
        authority = dict(schema='robotron-slot163-RAW-timing-one-use-authority-v1',
            mode=self.helper.MODE, diagnostic_scope=copy.deepcopy(self.helper.DIAGNOSTIC_SCOPE),
            root_selection=pins['selection'],
            current_output_binding=self.binding_pin, base_manifest=self.input_pin,
            fresh_parent_snapshot=pins['fresh'], supervisor_owner=self.policy['fleet'],
            supervisor_process=self.policy['baseline_owners']['fleet']['process'],
            prior_actor=self.policy['baseline_actors']['163'], output_lua=self.proof['candidate'],
            claim_directory=dict(path=str(directory), identity=self.fuse.directory_identity(directory.lstat())))
        selection = dict(schema='robotron-root-slot163-RAW-timing-diagnostic-selection-v1',
            mode=self.helper.MODE, one_original_exec_only=True, persistent_or_rollout_acceptance=False,
            diagnostic_only=True, diagnostic_scope=copy.deepcopy(self.helper.DIAGNOSTIC_SCOPE),
            expected_held_input_count=221, wire_policy=copy.deepcopy(self.helper.RAW_WIRE_POLICY),
            **{key: authority[key] for key in ('current_output_binding', 'base_manifest',
                'fresh_parent_snapshot', 'prior_actor', 'output_lua', 'claim_directory')},
            root_freeze_release=pins['release'], capture_equivalence_proof=self.proof_pin)
        table = {pins['selection']['path']: selection,
            pins['release']['path']: dict(schema='robotron-root-fixed03-preview-freeze-release-v1',
                all_four_legs_qualified=True, all_owned_scopes_closed=True),
            pins['fresh']['path']: dict(actors=self.policy['baseline_actors'], owners=dict(
                fleet=dict(process=self.policy['baseline_owners']['fleet']['process']))),
            self.proof_pin['path']: copy.deepcopy(self.proof)}
        def read(pin, as_json=True):
            if pin['path'] in table:
                return copy.deepcopy(table[pin['path']])
            data = self.base.read_bytes_pin(pin)
            return self.base.strict_json(data) if as_json else data
        return authority, selection, table, read

    def test_actual221_diagnostic_proof_scope_and_only_final_Lua_override(self):
        with tempfile.TemporaryDirectory(prefix='RAW helper no claim ') as d:
            authority, selection, table, read = self.fixture(Path(d))
            manifest = self.helper.validate_authority(authority, read, self.base, self.guards)
            self.assertEqual(len(self.binding['held_hashes']), selection['expected_held_input_count'])
            self.assertEqual(authority['prior_actor']['pid'], 794050)
            self.assertNotEqual(authority['prior_actor']['pid'], 757786)
            self.assertEqual(self.proof['parent'], self.binding['preview_extra_source_pins']['target_lua'])
            self.assertTrue(self.proof['encoded_frame_bytes_unchanged'])
            self.assertTrue(self.proof['diagnostic_only'])
            self.assertFalse(authority['diagnostic_scope']['hard_emission_deadline_claimed'])
            row = manifest['slots']['163']
            environment = dict(row['expected_environment'], LITERAL="spaces $ ; ' preserved")
            command, output = self.helper.prepare_output(authority, manifest, row['expected_args'], environment, self.base)
            expected = ['/usr/games/mame', *row['expected_args']]
            expected[expected.index('-autoboot_script') + 1] = self.proof['candidate']['path']
            self.assertEqual(command, expected)
            self.assertEqual(output['ROBOTRON_EVAL_MODE'], '1')
            self.assertEqual(output['LITERAL'], environment['LITERAL'])
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_changed_count_parent_decoding_and_wire_policy_guards_reject(self):
        for case in ('count220', 'count222', 'oldschema', 'oldparent', 'frameBytesFalse',
                     'clockFallback', 'proofFormat2', 'selectionFormat2', 'oldActor',
                     'hardDeadline', 'persistent'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='RAW guard no claim ') as d:
                authority, selection, table, read = self.fixture(Path(d))
                proof = table[self.proof_pin['path']]
                if case == 'count220': selection['expected_held_input_count'] = 220
                if case == 'count222': selection['expected_held_input_count'] = 222
                if case == 'oldschema': proof['schema'] = 'robotron-preview-fast-capture-byte-equivalence-and-CPU-source-package-v2'
                if case == 'oldparent': proof['parent'] = self.manifest['target_lua']
                if case == 'frameBytesFalse': proof['encoded_frame_bytes_unchanged'] = False
                if case == 'clockFallback': proof['fallback'] = 'ABORT_GAME'
                if case == 'proofFormat2': proof['wire_policy']['format'] = 2
                if case == 'selectionFormat2': selection['wire_policy']['format'] = 2
                if case == 'oldActor':
                    authority['prior_actor'] = copy.deepcopy(authority['prior_actor'])
                    authority['prior_actor']['pid'] = 757786
                    selection['prior_actor'] = authority['prior_actor']
                if case == 'hardDeadline': selection['diagnostic_scope']['hard_emission_deadline_claimed'] = True
                if case == 'persistent': selection['persistent_or_rollout_acceptance'] = True
                with self.assertRaises(ValueError):
                    self.helper.validate_authority(authority, read, self.base, self.guards)
                self.assertEqual(list(Path(d).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
