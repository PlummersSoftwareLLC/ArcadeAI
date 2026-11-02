"""NEW three focused CPU cases. Fake parent/exec; claims ONLY in temp dirs.

Uses existing immutable original4947 INPUT and actual207 metadata as historical
fixtures. No fresh process/API reads and no actual actor/production claim.
"""
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
A = P / 'actual-selected-preview30-trial-original01-20261027'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class CapturedExec(Exception):
    pass


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.next = load('_next_capture_experiment', HERE / 'exec_next_once_fast_preview_v1.py')
        cls.fuse = load('_existing_one_use_fuse', P / 'role-bound-wrapper-trial-original02-single-use/exec_role_bound_mame_once_v2.py')
        cls.base, _ = cls.fuse.load_base(P / 'role-bound-wrapper-trial-original01/exec_role_bound_mame_v1.py')
        cls.guards = load('_corrected_private_directory_guards', P / 'posttrial-slot163-authorities-and-readonly-reconciliation-original02-guard-corrections/posttrial_slot163_output_authority_v2.py')
        cls.manifest_pin = cls.pin(A / 'actual-fresh-slot163-original-INPUT-manifest.json')
        cls.manifest = cls.base.read_manifest(cls.manifest_pin['path'], cls.manifest_pin['sha256'])
        folder = A / 'engineering-reconciliation600-and-CID49-adapter-original01'
        cls.binding_pin = cls.pin(folder / 'actual-selected207-main-binding-original01.json')
        cls.binding = cls.base.strict_json(cls.base.read_bytes_pin(cls.binding_pin))
        cls.policy = cls.base.strict_json(cls.base.read_bytes_pin(cls.binding['supervision_policy']))

    @classmethod
    def pin(cls, path):
        raw = path.read_bytes()
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                    identity=cls.fuse.identity(path.lstat()))

    def fixture(self, directory):
        directory.chmod(0o700); ds = directory.lstat()
        keys = ('authority', 'selection', 'release', 'fresh', 'proof')
        pins = {key: dict(path='/CPUfixture/next-' + key) for key in keys}
        # The final selected capture package is actual byte-equivalence evidence;
        # only ROOT selection and parent admission are explicit CPU fixtures.
        package = self.pin(HERE / 'capture-proof-and-source-package-final-v4.json')
        proof = self.base.strict_json(self.base.read_bytes_pin(package))
        authority = dict(schema='robotron-slot163-next-one-use-capture-authority-v1', mode=self.next.MODE,
            root_selection=pins['selection'], current_output_binding=self.binding_pin,
            base_manifest=self.manifest_pin, fresh_parent_snapshot=pins['fresh'],
            supervisor_owner=self.policy['fleet'],
            supervisor_process=self.policy['baseline_owners']['fleet']['process'],
            prior_actor=self.policy['baseline_actors']['163'], output_lua=proof['candidate'],
            claim_directory=dict(path=str(directory), identity=self.fuse.directory_identity(ds)))
        table = {pins['authority']['path']: authority,
            pins['release']['path']: dict(schema='robotron-root-fixed03-preview-freeze-release-v1',
                all_four_legs_qualified=True, all_owned_scopes_closed=True),
            pins['fresh']['path']: dict(actors=self.policy['baseline_actors'], owners=dict(fleet=dict(
                process=self.policy['baseline_owners']['fleet']['process']))),
            pins['selection']['path']: dict(schema='robotron-root-slot163-next-capture-experiment-selection-v1',
                mode=self.next.MODE, one_original_exec_only=True, persistent_or_rollout_acceptance=False,
                **{key: authority[key] for key in ('current_output_binding','base_manifest','fresh_parent_snapshot',
                    'prior_actor','output_lua','claim_directory')},
                root_freeze_release=pins['release'], capture_equivalence_proof=package)}
        def read(pin, as_json=True):
            if pin['path'] in table: return copy.deepcopy(table[pin['path']])
            raw = self.base.read_bytes_pin(pin)
            return self.base.strict_json(raw) if as_json else raw
        return authority, pins, table, read

    def test_current_OUTPUT_single_temp_reservation_and_duplicate_refusal(self):
        with tempfile.TemporaryDirectory(prefix='next preview fake claim ') as d:
            authority, pins, table, read = self.fixture(Path(d))
            seen = []; executed = []
            def parent(selected, collector):
                seen.append(copy.deepcopy(selected['prior_actor']))
                return dict(pid=selected['supervisor_owner']['pid'],
                    starttime_ticks=selected['supervisor_owner']['starttime_ticks'],
                    prior_actor_birth_absent=True)
            fuse = types.SimpleNamespace(verify_parent=parent, dispatch=self.fuse.dispatch)
            def fake_exec(path, command, env):
                executed.append((path,command,env)); raise CapturedExec()
            row = self.manifest['slots']['163']; env = dict(row['expected_environment'], LITERAL="space $ ; ' unchanged")
            with self.assertRaises(CapturedExec):
                self.next.dispatch(authority,pins['authority'],row['expected_args'],env,read,
                    self.base,self.guards,fuse,None,fake_exec)
            self.assertEqual(len(seen),2)
            self.assertEqual(seen[0]['pid'],658236); self.assertNotEqual(seen[0]['pid'],2258553)
            command = executed[0][1]; output = executed[0][2]
            expected = list(row['expected_args']); expected[expected.index('-autoboot_script')+1] = authority['output_lua']['path']
            self.assertEqual(command,['/usr/games/mame',*expected]); self.assertEqual(output['ROBOTRON_EVAL_MODE'],'1')
            self.assertEqual(output['LITERAL'],env['LITERAL'])
            claim = json.loads((Path(d)/self.fuse.CLAIM_NAME).read_text())
            self.assertEqual(claim['manifest'],self.manifest_pin)
            self.assertEqual(claim['observed_parent']['prior_owned_output_identity']['pid'],658236)
            with self.assertRaisesRegex(ValueError,'ALREADY_CONSUMED'):
                self.next.dispatch(authority,pins['authority'],row['expected_args'],env,read,
                    self.base,self.guards,fuse,None,fake_exec)
            self.assertEqual(len(executed),1)

    def test_all191_unselected_output_is_literal_original_passthrough(self):
        with tempfile.TemporaryDirectory(prefix='next preview passthrough ') as d:
            authority,pins,table,read = self.fixture(Path(d))
            self.next.validate_authority(authority,read,self.base,self.guards)
            for key,row in self.manifest['slots'].items():
                if key=='163': continue
                env = dict(row['expected_environment'])
                command,output = self.next.prepare_output(authority,self.manifest,row['expected_args'],env,self.base)
                self.assertEqual(command,['/usr/games/mame',*row['expected_args']])
                self.assertEqual(output,env)
            self.assertEqual(list(Path(d).iterdir()),[])

    def test_old_INPUT_actor_wrong_mode_nonprivate_or_unfilled_authority_refuses(self):
        for kind in ('oldINPUT','mode','unfilled','nonprivate','selection'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='next preview negative ') as d:
                authority,pins,table,read = self.fixture(Path(d))
                if kind=='oldINPUT': authority['prior_actor']=copy.deepcopy(self.policy['baseline_actors']['163']);authority['prior_actor']['pid']=2258553
                if kind=='mode': authority['mode']='FAKE_PERSISTENT_ACCEPTANCE'
                if kind=='unfilled': authority['root_selection']=None
                if kind=='nonprivate': Path(d).chmod(0o777)
                if kind=='selection': table[pins['selection']['path']]['persistent_or_rollout_acceptance']=True
                with self.assertRaises(ValueError): self.next.validate_authority(authority,read,self.base,self.guards)
                self.assertEqual(list(Path(d).iterdir()),[])
        process = subprocess.run(['/usr/bin/python3.12','-I','-B',str(HERE/'exec_next_once_fast_preview_v1.py')],
                                 capture_output=True,text=True,timeout=5)
        self.assertEqual(process.returncode,0);self.assertIn('PLAN_ONLY',process.stdout)


if __name__=='__main__':
    unittest.main()
