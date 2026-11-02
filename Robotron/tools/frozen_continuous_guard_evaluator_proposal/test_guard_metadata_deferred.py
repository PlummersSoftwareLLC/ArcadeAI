"""Dormant metadata-only guards; authored but UNEXECUTED.

Future execution extracts named real companion functions into a closed namespace.
It never imports the companions, DQN, Torch, a numerical verifier, or a launcher.
Only the two explicitly pinned source files are read. Runtime/wire installation is
covered separately by the selected installer's own future full-wire tests.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import types
import unittest


HERE = Path(__file__).resolve().parent
SIDE = HERE / 'run_frozen_sidecar.py'
CAMPAIGN = HERE / 'run_quality_campaign.py'
SIDE_SHA = 'c3a2ef29245b9d6a2e8309520f67d3b1f92061c38b395fa4ef8773631287dea3'
CAMPAIGN_SHA = '6d6fd8e4aa201d7099927af508742e8112cca3a5e6ca621731306664789ed8db'
RECEIPT = '/closed/leg/receipt.json'


def functions(path, expected, names, namespace):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise AssertionError('Pinned companion source differs')
    tree = ast.parse(raw, filename=str(path))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError('Exact named production functions required')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


class ClosedPath(PurePosixPath):
    reads = None
    unexpected = None

    def resolve(self, strict=False):
        return self

    def read_bytes(self):
        if self.reads is None or str(self) not in self.reads:
            self.unexpected.append(('read_bytes', str(self)))
            raise AssertionError('Unexpected closed-world read')
        return self.reads[str(self)]

    def stat(self, *args, **kwargs):
        self.unexpected.append(('stat', str(self)))
        raise AssertionError('No target filesystem stat in metadata namespace')


def pin(path, digest='a' * 64, size=10):
    return dict(path=path, sha256=digest, bytes=size,
        identity=dict(device=2304, inode=100, bytes=size, mtime_ns=1,
            ctime_ns=1, mode='0o444', uid=1001, nlink=1))


class EffectiveGuardMetadataTests(unittest.TestCase):
    def setUp(self):
        self.unexpected = []
        ClosedPath.unexpected = self.unexpected
        ClosedPath.reads = {}
        self.addCleanup(self.assert_closed)
        self.selection = dict(schema='selected', canonical_base_socket=pin('/closed/socket.py'),
            installer=pin('/closed/effective_guard.py'), effective_helper=pin('/closed/effective_guard_body.py'),
            stable_source_fingerprint='b' * 64)

    def assert_closed(self):
        self.assertEqual(self.unexpected, [])

    def test_actual_guard_selection_requires_exact_manifest_and_both_source_pins(self):
        installer = ClosedPath('/closed/effective_guard.py')
        body = ClosedPath('/closed/effective_guard_body.py')
        manifest_path = ClosedPath('/closed/manifest.json')
        manifest = dict(files=[self.selection['installer'], self.selection['effective_helper']])
        table = {str(manifest_path): (json.dumps(manifest).encode(), pin(str(manifest_path), 'c' * 64)),
            '/closed/socket.py': (b'base', self.selection['canonical_base_socket']),
            '/closed/sidecar.py': (b'companion', pin('/closed/sidecar.py'))}
        authenticated = []

        def source_record(path, expected=None, **kwargs):
            key = str(path)
            if key not in table:
                self.unexpected.append(('source_record', key))
                raise AssertionError('Unexpected source record')
            return copy.deepcopy(table[key])

        def authenticate(value):
            if value not in (self.selection['installer'], self.selection['effective_helper']):
                self.unexpected.append(('authenticate', value))
                raise AssertionError('Unexpected source PIN')
            authenticated.append(value['path'])

        ns = dict(__file__='/closed/sidecar.py', Path=ClosedPath, json=json, re=re,
            hashlib=hashlib, source_record=source_record, authenticate_source_pin=authenticate,
            GUARD_MANIFEST=manifest_path, GUARD_MANIFEST_SHA='c' * 64,
            GUARD_INSTALLER=installer, GUARD_INSTALLER_SHA='a' * 64,
            GUARD_BODY=body, GUARD_BODY_SHA='a' * 64,
            BASE_SOCKET=ClosedPath('/closed/socket.py'), BASE_SOCKET_SHA='a' * 64,
            GUARD_NAME='_continuous_play_score_dip')
        functions(SIDE, SIDE_SHA, ('require', 'unique_object', 'guard_selection'), ns)
        result = ns['guard_selection'](manifest_path, 'c' * 64)
        self.assertEqual(authenticated, [str(installer), str(body)])
        self.assertEqual(result['canonical_base_socket'], self.selection['canonical_base_socket'])
        self.assertEqual(result['installer'], self.selection['installer'])
        self.assertEqual(result['effective_helper'], self.selection['effective_helper'])
        self.assertTrue(result['canonical_source_hashes_are_base_provenance'])
        self.assertRegex(result['stable_source_fingerprint'], r'^[0-9a-f]{64}$')
        for path, sha in ((ClosedPath('/closed/other.json'), 'c' * 64), (manifest_path, 'd' * 64)):
            with self.subTest(path=str(path), sha=sha), self.assertRaises(ValueError):
                ns['guard_selection'](path, sha)
        for files in ([self.selection['installer']], [self.selection['installer']] * 2 + [self.selection['effective_helper']]):
            table[str(manifest_path)] = (json.dumps(dict(files=files)).encode(), pin(str(manifest_path), 'c' * 64))
            with self.subTest(files=len(files)), self.assertRaises(ValueError):
                ns['guard_selection'](manifest_path, 'c' * 64)

    def test_actual_runtime_verification_preserves_provenance_and_excludes_local_ids(self):
        ns = dict(hashlib=hashlib, sys=sys, marshal=__import__('marshal'), GUARD_NAME='_continuous_play_score_dip')
        functions(SIDE, SIDE_SHA, ('require', 'verify_guard', 'stable_effective_implementation'), ns)
        helper = lambda frame, client, previous_score, previous_wave, recent_start: True
        module = types.SimpleNamespace(_continuous_play_score_dip=helper)
        token = types.SimpleNamespace(module=module, config=object())
        facts = dict(base_socket=self.selection['canonical_base_socket'], installer=self.selection['installer'],
            effective_helper=self.selection['effective_helper'], function_code_globals_config_identity=True,
            only_one_module_global_replaced=True, effective_source_is_not_base_source=True)

        def verify(observed):
            if observed is not token:
                self.unexpected.append(('verify', observed))
                raise AssertionError('Wrong runtime token')
            return copy.deepcopy(facts)

        evidence = ns['verify_guard'](types.SimpleNamespace(verify=verify), token, self.selection)
        self.assertRegex(evidence['runtime_code_sha256'], r'^[0-9a-f]{64}$')
        stable = dict(evidence, selection=self.selection, verification_count=3)
        changed_local = copy.deepcopy(stable)
        changed_local['local_identity'] = dict(module=999)
        changed_local['verification_count'] = 900
        self.assertEqual(ns['stable_effective_implementation'](stable),
            ns['stable_effective_implementation'](changed_local))
        for key in ('base_socket', 'effective_helper', 'only_one_module_global_replaced'):
            old = copy.deepcopy(facts[key])
            facts[key] = False
            with self.subTest(field=key), self.assertRaises(ValueError):
                ns['verify_guard'](types.SimpleNamespace(verify=verify), token, self.selection)
            facts[key] = old

    def campaign_namespace(self):
        source = {'canonical/socket.py': 'a' * 64}
        execution = {'/closed/campaign.py': 'b' * 64}
        job = dict(checkpoint='/closed/reference.pt', directory='/closed/leg', label='reference',
            game_boundary_diagnostics=True, continuous_guard_manifest='/closed/manifest.json',
            continuous_guard_manifest_sha256='c' * 64)
        plan = dict(effective_implementation=self.selection, evaluator_source_hashes=source,
            execution_source_hashes=execution, boot_assets={'identity': 'boot'},
            checkpoints={'reference': dict(snapshot='/closed/reference.pt', sha256='d' * 64)},
            legs=[dict(job=dict(job, boot_assets='/closed/boot')) for _ in range(4)])
        calls = []

        def selection(path, sha):
            calls.append(('selection', path, sha))
            if path != '/closed/manifest.json' or sha != 'c' * 64:
                self.unexpected.append(('selection', path, sha))
                raise AssertionError('Unexpected manifest selector')
            return copy.deepcopy(self.selection)

        def sha(path):
            if path != '/closed/reference.pt':
                self.unexpected.append(('checkpoint hash', path))
                raise AssertionError('No actual model read')
            calls.append(('sha', path))
            return 'd' * 64

        def boot(path):
            if str(path) != '/closed/boot':
                self.unexpected.append(('boot', str(path)))
                raise AssertionError('Unexpected boot path')
            calls.append(('boot', str(path)))
            return {'identity': 'boot'}

        evaluator = types.SimpleNamespace(guard_selection=selection, source_hashes=lambda: source,
            sha256=sha, boot_module=lambda: types.SimpleNamespace(load_snapshot=boot), SLOTS=tuple(range(4096, 4112)))
        ns = dict(Path=ClosedPath, json=json, re=re, hashlib=hashlib, evaluator=evaluator,
            execution_sources=lambda: execution, JOB_FIELDS=(),
            IncompleteLeg=type('IncompleteLeg', (ValueError,), {}))
        functions(CAMPAIGN, CAMPAIGN_SHA, ('check_precommit', 'load_leg'), ns)
        return ns, plan, job, calls

    def test_actual_precommit_requires_identical_guard_for_every_leg(self):
        ns, plan, _, calls = self.campaign_namespace()
        ns['check_precommit'](plan)
        self.assertEqual(calls, [('selection', '/closed/manifest.json', 'c' * 64),
            ('boot', '/closed/boot'), ('sha', '/closed/reference.pt')])
        for field, value in (('continuous_guard_manifest', '/closed/other.json'),
                             ('continuous_guard_manifest_sha256', 'e' * 64)):
            bad = copy.deepcopy(plan)
            bad['legs'][2]['job'][field] = value
            calls.clear()
            with self.subTest(field=field), self.assertRaises(ValueError):
                ns['check_precommit'](bad)
            self.assertEqual(calls, [('selection', '/closed/manifest.json', 'c' * 64)])
        bad = copy.deepcopy(plan)
        bad['effective_implementation']['effective_helper']['sha256'] = 'e' * 64
        with self.assertRaises(ValueError):
            ns['check_precommit'](bad)

    def test_actual_load_leg_requires_successful_effective_verification(self):
        ns, plan, job, _ = self.campaign_namespace()
        backend_calls = []

        def backend(value, *, verify_checkpoint):
            backend_calls.append(verify_checkpoint)
            return dict(expected_actor_slots=list(range(4096, 4112)),
                rows=[dict(client_slot=slot) for slot in range(4096, 4112)])

        ns['validate_backend'] = backend
        effective = dict(selection=copy.deepcopy(self.selection), verified_before_serving=True,
            verified_after_cleanup=True, verification_error=None, verification_count=3,
            local_identity_before={'function': 1}, local_identity_after={'function': 1},
            runtime_code_sha256='a' * 64, python_version='synthetic', python_cache_tag='synthetic')
        receipt = dict(complete=True, active=False, cohort=dict(complete=True), job=job,
            label='reference', checkpoint_sha256='d' * 64,
            source_hashes=plan['evaluator_source_hashes'], boot_assets=plan['boot_assets'],
            effective_implementation=effective)
        spec = dict(receipt_path=RECEIPT, job=job, role='reference')

        def call(value):
            ClosedPath.reads = {RECEIPT: json.dumps(value).encode()}
            return ns['load_leg'](spec, plan, verify_checkpoint=False)

        returned, _, digest = call(receipt)
        self.assertEqual(returned, receipt)
        self.assertRegex(digest, r'^[0-9a-f]{64}$')
        mutations = [('verified_before_serving', False), ('verified_after_cleanup', False),
            ('verification_error', 'guard drift'), ('verification_count', True),
            ('verification_count', 1), ('runtime_code_sha256', 'z' * 64),
            ('local_identity_after', {'function': 2})]
        for field, value in mutations:
            bad = copy.deepcopy(receipt)
            bad['effective_implementation'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                call(bad)
        for field in ('continuous_guard_manifest', 'continuous_guard_manifest_sha256'):
            bad = copy.deepcopy(receipt)
            bad['job'][field] = 'wrong'
            with self.subTest(job_field=field), self.assertRaises(ValueError):
                call(bad)
        bad = copy.deepcopy(receipt)
        bad.pop('effective_implementation')
        with self.assertRaises(ValueError):
            call(bad)
        self.assertGreater(len(backend_calls), 1)


if __name__ == '__main__':
    unittest.main()
