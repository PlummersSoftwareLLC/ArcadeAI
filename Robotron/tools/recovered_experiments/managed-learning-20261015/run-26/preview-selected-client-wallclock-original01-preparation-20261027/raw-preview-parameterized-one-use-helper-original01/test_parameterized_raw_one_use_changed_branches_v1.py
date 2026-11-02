"""Two focused RAW/count branch cases using immutable current215 source metadata.

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
PROOF = F / 'raw-format1-existing-wire-policy-original01/decoded-RGB565-and-RAW-wire-policy-proof-original01.json'
BINDING = P / 'actual-fast-capture-one-use-original02-20261027/readonly-current207-to-fast215-reconciliation-original01/actual-fast215-main-binding-original01.json'
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
        cls.helper = load(HERE / 'exec_next_once_raw_preview_v2.py',
            'ecdb78d2843e240ba75286c6647be7b9acdf4a232dce45e6af5b1266318641c6', '_raw_changed_helper')
        cls.fuse = load(P / 'role-bound-wrapper-trial-original02-single-use/exec_role_bound_mame_once_v2.py',
            'b5fdc64b6777e6db2541f7c535be2fc49e47f5b565dcd714086cdb33d6041723', '_raw_existing_fuse')
        cls.base, _ = cls.fuse.load_base(P / 'role-bound-wrapper-trial-original01/exec_role_bound_mame_v1.py')
        cls.guards = load(P / 'posttrial-slot163-authorities-and-readonly-reconciliation-original02-guard-corrections/posttrial_slot163_output_authority_v2.py',
            '9a8fe7c08e1e941e2d26a2cc3c65124b27129b9f470a0020453e33010bf32027', '_raw_existing_guards')
        cls.binding_pin = cls.pin(BINDING)
        assert cls.binding_pin['sha256'] == '2e8e91718c577861d120f1720316f6e78a58fa16d4f089775f6d679769b9c18e'
        cls.binding = cls.base.strict_json(cls.base.read_bytes_pin(cls.binding_pin))
        cls.policy = cls.base.strict_json(cls.base.read_bytes_pin(cls.binding['supervision_policy']))
        cls.proof_pin = cls.pin(PROOF)
        assert cls.proof_pin['sha256'] == '317a794b983d90937ea93d530ba24a8189cbd7713e75d6903db5de17eb829db3'
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
        authority = dict(schema='robotron-slot163-next-one-use-capture-authority-v1',
            mode=self.helper.MODE, root_selection=pins['selection'],
            current_output_binding=self.binding_pin, base_manifest=self.input_pin,
            fresh_parent_snapshot=pins['fresh'], supervisor_owner=self.policy['fleet'],
            supervisor_process=self.policy['baseline_owners']['fleet']['process'],
            prior_actor=self.policy['baseline_actors']['163'], output_lua=self.proof['candidate'],
            claim_directory=dict(path=str(directory), identity=self.fuse.directory_identity(directory.lstat())))
        selection = dict(schema='robotron-root-slot163-next-capture-experiment-selection-v1',
            mode=self.helper.MODE, one_original_exec_only=True, persistent_or_rollout_acceptance=False,
            expected_held_input_count=215, wire_policy=copy.deepcopy(self.helper.RAW_WIRE_POLICY),
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

    def test_actual215_decoded_RAW_proof_and_only_final_Lua_override(self):
        with tempfile.TemporaryDirectory(prefix='RAW helper no claim ') as d:
            authority, selection, table, read = self.fixture(Path(d))
            manifest = self.helper.validate_authority(authority, read, self.base, self.guards)
            self.assertEqual(len(self.binding['held_hashes']), selection['expected_held_input_count'])
            self.assertEqual(authority['prior_actor']['pid'], 757786)
            self.assertNotEqual(authority['prior_actor']['pid'], 658236)
            self.assertEqual(self.proof['parent'], self.binding['preview_extra_source_pins']['target_lua'])
            self.assertFalse(self.proof['encoded_bytes_equality_required'])
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
        for case in ('count214', 'count216', 'oldschema', 'oldparent', 'decodedFalse',
                     'encodedRequired', 'proofFormat2', 'selectionFormat2', 'oldActor'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='RAW guard no claim ') as d:
                authority, selection, table, read = self.fixture(Path(d))
                proof = table[self.proof_pin['path']]
                if case == 'count214': selection['expected_held_input_count'] = 214
                if case == 'count216': selection['expected_held_input_count'] = 216
                if case == 'oldschema': proof['schema'] = 'robotron-preview-fast-capture-byte-equivalence-and-CPU-source-package-v2'
                if case == 'oldparent': proof['parent'] = self.manifest['target_lua']
                if case == 'decodedFalse': proof['decoded_RGB565_equality_all_cases'] = False
                if case == 'encodedRequired': proof['encoded_bytes_equality_required'] = True
                if case == 'proofFormat2': proof['wire_policy']['format'] = 2
                if case == 'selectionFormat2': selection['wire_policy']['format'] = 2
                if case == 'oldActor':
                    authority['prior_actor'] = copy.deepcopy(authority['prior_actor'])
                    authority['prior_actor']['pid'] = 658236
                    selection['prior_actor'] = authority['prior_actor']
                with self.assertRaises(ValueError):
                    self.helper.validate_authority(authority, read, self.base, self.guards)
                self.assertEqual(list(Path(d).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
