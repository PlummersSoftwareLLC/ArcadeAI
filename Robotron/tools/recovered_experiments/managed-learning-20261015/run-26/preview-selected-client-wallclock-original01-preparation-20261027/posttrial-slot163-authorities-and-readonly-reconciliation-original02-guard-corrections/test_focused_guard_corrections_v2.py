"""Only NEW private-directory/cardinality guards; no old8/9 suite rerun.

Reuse the historical CPU fixture builder as data/functions, never its test
methods. Future PID/CID/pins remain synthetic. Real directories/claims are
temporary CPU fixtures; no installed wrapper/MAME/control/canonical action.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
P = HERE.parent
OLD = P / 'posttrial-slot163-authorities-and-readonly-reconciliation-original01'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prior_fixtures = load('_prior_fixture_definitions_only', OLD / 'test_prospective_slot163_components_v1.py')
        cls.prior_fixtures.Tests.setUpClass()  # Loads definitions/historical files, NO old tests.
        cls.rec = load('_corrected_reconciler', HERE / 'prepare_slot163_readonly_reconciliation_v2.py')
        cls.out = load('_corrected_output', HERE / 'posttrial_slot163_output_authority_v2.py')
        cls.fuse = load('_original_fuse_for_new_guard_tests', P / 'role-bound-wrapper-trial-original02-single-use/exec_role_bound_mame_once_v2.py')

    def fixture(self):
        fixture = self.prior_fixtures.Tests()
        fixture.rec = self.rec; fixture.out = self.out
        plan, read, values = fixture.fixture()
        return fixture, plan, read, values

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='corrected private fuse ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.new_dir = self.root / 'NEW private directory'; self.new_dir.mkdir(mode=0o700)
        self.old_dir = self.root / 'OLD consumed directory'; self.old_dir.mkdir(mode=0o700)

    def directory(self, path=None):
        path = self.new_dir if path is None else path
        return dict(path=str(path), identity=self.fuse.directory_identity(path.lstat()))

    def rollback_context(self):
        fixture, plan, old_read, values = self.fixture()
        prior = values['after_old_birth_probe_snapshot']['actors']['163']
        manifest_pin = fixture.original_manifest_pin()
        pins = {key: dict(path='/CPUfixture/' + key) for key in ('selection', 'fresh', 'outcome', 'claim', 'permit', 'authority')}
        authority = dict(schema='robotron-slot163-posttrial-output-authority-v1', mode=self.out.ROLLBACK,
            root_selection=pins['selection'], fresh_parent_snapshot=pins['fresh'],
            supervisor_owner=fixture.policy['fleet'],
            supervisor_process=values['before_snapshot']['owners']['fleet']['process'],
            prior_actor=prior, base_manifest=manifest_pin,
            output_lua=fixture.manifest['original_lua'], claim_directory=self.directory())
        table = {
            pins['authority']['path']: authority,
            pins['fresh']['path']: values['before_snapshot'],
            pins['selection']['path']: dict(schema='robotron-root-slot163-output-selection-v1', mode=self.out.ROLLBACK,
                base_manifest=manifest_pin, output_lua=authority['output_lua'], fresh_parent_snapshot=pins['fresh'],
                prior_actor=prior, root_freeze_release=plan['root_freeze_release'],
                closed_trial_outcome=pins['outcome'], explicit_rollback_selected=True),
            pins['outcome']['path']: dict(schema='robotron-root-closed-slot163-preview-trial-outcome-v1',
                prior_owned_process=prior, original_trial_permit_retained=True, actual_outcome_preserved=True,
                original_trial_claim=pins['claim'], original_trial_permit=pins['permit']),
            pins['claim']['path']: dict(schema='robotron-slot163-exec-reservation-consumed-v1',
                original_permit=pins['permit'], manifest=manifest_pin,
                claimant_pid=prior['pid'], claimant_birth=prior['starttime_ticks']),
            pins['permit']['path']: dict(claim_directory=self.directory(self.old_dir))}
        def read(entry, as_json=True):
            if entry['path'] in table: return copy.deepcopy(table[entry['path']])
            return old_read(entry, as_json)
        return fixture, authority, pins['authority'], read

    def test_positive_reconciler_has_exact197_plus10_disjoint_sources(self):
        fixture, plan, read, _ = self.fixture()
        prepared = fixture.prepare(plan, read)
        binding = prepared['binding_requiring_actual_policy_and_transition_pins']
        self.assertEqual(len(binding['held_hashes']), 207)
        self.assertEqual(len({p['path'] for p in plan['extra_pins'].values()}), 10)
        self.assertTrue(set(p['path'] for p in plan['extra_pins'].values()).isdisjoint(fixture.old['held_hashes']))
        self.assertTrue(all(binding['held_hashes'][p] == sha for p, sha in fixture.old['held_hashes'].items()))
        self.assertIsNone(binding['supervision_policy'])

    def test_duplicate_or_old_overlapping_source_paths_cannot_reduce_the_union(self):
        for kind in ('alias', 'old_overlap'):
            fixture, plan, read, _ = self.fixture()
            if kind == 'alias': plan['extra_pins']['readonly_monitor'] = copy.deepcopy(plan['extra_pins']['reconciler'])
            else:
                path, sha = next(iter(fixture.old['held_hashes'].items()))
                plan['extra_pins']['readonly_monitor'] = dict(path=path, sha256=sha, bytes=10, identity={})
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'DISTINCT'):
                fixture.prepare(plan, read)

    def test_wrong_original_source_cardinality_is_not_silently_generalized(self):
        fixture, plan, read, values = self.fixture()
        values['prior_binding']['held_hashes']['/CPUfixture/foreign-extra'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'original197'): fixture.prepare(plan, read)

    def test_positive_private_directory_retains_b5_four_key_identity_ABI(self):
        directory = self.directory()
        self.assertEqual(self.out.validate_private_claim_directory(directory), directory)
        self.assertEqual(set(directory['identity']), {'device', 'inode', 'mode', 'uid'})
        self.assertEqual(self.new_dir.stat().st_nlink, 2)
        fixture, authority, _, read = self.rollback_context()
        self.assertEqual(self.out.validate_authority(authority, read, fixture.execbase), fixture.manifest)

    def test_world_writable_uid_schema_symlink_inode_and_nlink_fail_closed(self):
        for kind in ('world', 'wrong_uid', 'extra_key', 'missing_key', 'identity_extra', 'symlink', 'wrong_inode', 'nlink'):
            path = self.root / ('dir-' + kind); path.mkdir(mode=0o700)
            directory = self.directory(path)
            if kind == 'world': path.chmod(0o777); directory = self.directory(path)
            if kind == 'wrong_uid': directory['identity']['uid'] += 1
            if kind == 'extra_key': directory['unexpected'] = True
            if kind == 'missing_key': del directory['identity']['uid']
            if kind == 'identity_extra': directory['identity']['nlink'] = 2
            if kind == 'symlink':
                link = self.root / 'symlink'; link.symlink_to(path); directory['path'] = str(link)
            if kind == 'wrong_inode': directory['identity']['inode'] += 1
            if kind == 'nlink': (path / 'unexpected-child-directory').mkdir()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.out.validate_private_claim_directory(directory)

    def test_full_rollback_authority_rejects_actual0777_even_when_identity_agrees(self):
        fixture, authority, _, read = self.rollback_context()
        self.new_dir.chmod(0o777)
        authority['claim_directory'] = self.directory()
        # Reader returns the same changed authority, so this tests the privacy guard,
        # not a mere authority-vs-dictionary mismatch.
        with self.assertRaisesRegex(ValueError, '0700'):
            self.out.validate_authority(authority, read, fixture.execbase)

    def test_real_rollback_claim_rechecks_private_mode_before_and_after_claim(self):
        fixture, authority, authority_pin, read = self.rollback_context()
        row = fixture.manifest['slots']['163']; environment = dict(row['expected_environment'])
        observed = dict(pid=authority['supervisor_owner']['pid'],
            starttime_ticks=authority['supervisor_owner']['starttime_ticks'], prior_actor_birth_absent=True)
        called = []
        real_reserve = self.fuse.reserve_once
        def reserve_then_change(*args):
            real_reserve(*args)
            self.new_dir.chmod(0o777)
        with patch.object(self.fuse, 'verify_parent', return_value=observed), \
                patch.object(self.fuse, 'reserve_once', side_effect=reserve_then_change):
            with self.assertRaises(ValueError):
                self.out.dispatch(authority, authority_pin, fixture.manifest, row['expected_args'], environment,
                    fixture.execbase, self.fuse, object(), read, lambda *args: called.append(args))
        self.assertEqual(called, [])
        self.assertTrue((self.new_dir / self.fuse.CLAIM_NAME).exists())
        self.new_dir.chmod(0o700)
        with self.assertRaisesRegex(ValueError, 'ALREADY_CONSUMED'):
            self.fuse.reserve_once(authority, authority_pin, ['/temporary-fake-only'], observed)


if __name__ == '__main__':
    unittest.main()
