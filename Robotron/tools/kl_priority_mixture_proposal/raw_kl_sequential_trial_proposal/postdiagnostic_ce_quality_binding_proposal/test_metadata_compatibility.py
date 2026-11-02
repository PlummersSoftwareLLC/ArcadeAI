"""Deferred metadata/source compatibility guards, never a future candidate proof.

Root alone may run this selected suite. It imports only the new stdlib metadata
modules, reads fixed closed JSON/source, and uses synthetic negative copies.
The sidecar inventory function alone is extracted into a pure fake-path namespace;
no evaluator, server, project numerical import, runtime query or model access.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import stat
import unittest


HERE = Path(__file__).resolve().parent
GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME / 'logs/managed-learning-20261015/run-26'
BINDER_SHA = 'f2d2ceb819fe3fb08edaf2169da8ee0dd8c7f7296eb0f5b96b87d6908d438f62'
CAPTURE_SHA = 'e01a36c197c889d1994e72bee82a8622c8d7fad72477d6d0eaffef2c5e5aefbe'
SIDECAR_SHA = 'db1fd0eac2c68b73425c77767ef0f842374291c855338f6b2ac05ee6b79dc04f'
PREDECESSOR = RUN / 'accepted-newgame-forward-recovery-root-control-20261017/actual-native-postaccepted-quality-plan-readonly.json'
INVALID49 = RUN / 'lr25-first8M-frozen-quality-root-preparation-20261017/actual-native-plan-readonly-copy.json'
INVALID49_RELEASE = RUN / 'lr25-first8M-partial-invalid49-owned-closure-root-20261017/root-explicit-current-partial-invalid49-quality-source-freeze-release.json'
ACTIVATION = RUN / 'rejected-gap-healthy-activation-original01-20261018/result.json'
ADOPTION = RUN / 'rejected-gap-healthy-activation-root-preparation-20261018/root-actual-activation-canonical-adoption.json'


def closed(path, expected):
    assert path.suffix == '.json'
    before = path.lstat()
    assert stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o444
    assert before.st_nlink == 1 and 0 < before.st_size <= 4 << 20
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    return json.loads(raw)


def metadata_pin(path):
    assert path.suffix == '.json'
    raw = path.read_bytes()
    s = path.lstat()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                              mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                              mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink))


def metadata_module(name, filename, expected):
    path = HERE / filename
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PostdiagnosticMetadataContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.B = metadata_module('_postdiagnostic_bindings_guard', 'quality_bindings.py', BINDER_SHA)
        cls.prior = closed(PREDECESSOR, '4093225c8fdec659880cc06a5c54549139708909f7a011696ac03f298d3338e8')
        cls.old = closed(INVALID49, '3a9dc2b00f3e03fd93dd23aa1252fe019983d589bfd5f04a38e01482fb2be834')
        cls.invalid = closed(INVALID49_RELEASE, 'a7d7f523674d8135535779da782eb4ab3aa342b012695960f1ccef03b0fd6e7f')
        cls.old_pin = metadata_pin(INVALID49)
        cls.activation = closed(ACTIVATION, 'f47b861115c62a87097f6eef0750f9c07db8a6876d59c87ab0a5ff0801a19621')

    def test_genuine_historical_maps_survive_current_inventory_change(self):
        B = self.B
        B.check_historical_sources(self.prior, self.invalid, self.old, self.old_pin)
        before_e, before_x = B.EVALUATOR, B.EXECUTION
        try:
            B.EVALUATOR = dict(B.EVALUATOR, **{'tools/run_frozen_sidecar.py': '0' * 64})
            B.EXECUTION = dict(B.EXECUTION, **{str(GAME / 'tools/run_frozen_sidecar.py'): '1' * 64})
            B.check_historical_sources(self.prior, self.invalid, self.old, self.old_pin)
        finally:
            B.EVALUATOR, B.EXECUTION = before_e, before_x
        self.assertEqual(len(B.PRE_DIAGNOSTIC_EVALUATOR), 12)
        self.assertEqual(len(B.INVALID49_EVALUATOR), 12)
        self.assertNotIn('Scripts/dqn/rejected_gap_telemetry.py', B.INVALID49_EVALUATOR)
        tree = ast.parse((HERE / 'quality_bindings.py').read_bytes())
        validate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'validate')
        calls = [n.func.id for n in ast.walk(validate)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertIn('check_historical_sources', calls)

    def test_cross_family_or_false_invalid49_history_is_rejected(self):
        B = self.B
        cases = []
        prior = copy.deepcopy(self.prior)
        prior['evaluator_source_hashes'] = dict(B.EVALUATOR)
        cases.append((prior, self.invalid, self.old, self.old_pin))
        prior = copy.deepcopy(self.prior)
        prior['execution_source_hashes'] = dict(B.EXECUTION)
        cases.append((prior, self.invalid, self.old, self.old_pin))
        old = copy.deepcopy(self.old)
        old['evaluator_source_hashes'] = dict(B.PRE_DIAGNOSTIC_EVALUATOR)
        cases.append((self.prior, self.invalid, old, self.old_pin))
        old = copy.deepcopy(self.old)
        old['execution_source_hashes'] = dict(B.EXECUTION)
        cases.append((self.prior, self.invalid, old, self.old_pin))
        for key, value in [('C1_count', 50), ('quality_acceptance', True), ('all_four_completed', True)]:
            invalid = copy.deepcopy(self.invalid)
            invalid[key] = value
            cases.append((self.prior, invalid, self.old, self.old_pin))
        pin = copy.deepcopy(self.old_pin)
        pin['sha256'] = '0' * 64
        cases.append((self.prior, self.invalid, self.old, pin))
        for index, values in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                B.check_historical_sources(*values)

    def test_real_sidecar_inventory_adds_helper_once_and_only_inventory_changes(self):
        raw = (HERE / 'prepared-after/tools/run_frozen_sidecar.py').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), SIDECAR_SHA)
        after = raw.decode()
        before = after.replace(', "rejected_gap_telemetry.py"))', '))')
        self.assertNotEqual(before, after)
        self.assertEqual(hashlib.sha256(before.encode()).hexdigest(),
                         'cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90')
        tree = ast.parse(raw)
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'source_hashes')
        seen = []
        def fake_sha(path):
            seen.append(str(path.relative_to(PurePosixPath(str(GAME)))))
            return 'synthetic-source-only'
        namespace = dict(Path=PurePosixPath, GAME=PurePosixPath(str(GAME)),
                         __file__=str(GAME / 'tools/run_frozen_sidecar.py'), sha256=fake_sha)
        # Exact single body only; no sidecar imports/initialization or real file hashing.
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                     '<exact-sidecar-source_hashes-only>', 'exec'), namespace)
        sources = namespace['source_hashes']()
        self.assertEqual(set(sources), set(self.B.EVALUATOR))
        self.assertEqual(len(seen), 13)
        self.assertEqual(seen.count('Scripts/dqn/rejected_gap_telemetry.py'), 1)

    def test_actual_diagnostic62_map_and_flag_refuse_partial_or_old_maps(self):
        binding = self.activation['healthy192']['binding']
        sources, env = binding['bindings']['source_hashes'], binding['environment']
        self.B.check_diagnostic_sources(sources, env)
        cases = []
        missing = dict(sources)
        del missing[str(GAME / 'Scripts/dqn/rejected_gap_telemetry.py')]
        cases.append((missing, env))
        wrong = dict(sources)
        wrong[str(GAME / 'Scripts/dqn/socket_server.py')] = self.B.PRE_DIAGNOSTIC_EVALUATOR['Scripts/dqn/socket_server.py']
        cases.append((wrong, env))
        cases.append((dict(sources, **{'synthetic-extra-source': '0' * 64}), env))
        cases.append((sources, dict(env, ROBOTRON_REJECTED_GAP_TELEMETRY='0')))
        for index, values in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.B.check_diagnostic_sources(*values)

    def test_genuine_typed_activation_context_and_wrong_old_owner_or_alias(self):
        C = metadata_module('_postdiagnostic_capture_guard', 'capture_candidate.py', CAPTURE_SHA)
        adoption = closed(ADOPTION, '490c7cb2de233ded3a9cd6c06d7c3c1d0006c3b714a526a584fe085e13a3ed0b')
        job = closed(Path(self.activation['root_job']['path']), self.activation['root_job']['sha256'])
        case = dict(activation=dict(result=adoption['original_result'], adoption=metadata_pin(ADOPTION)),
                    source_freeze_release=job['quality_release'])
        context = C.activation_context(case, None)
        self.assertEqual(context['owner'], C.ACTUAL_OWNER)
        self.assertEqual(context['phase']['record']['sha256'], C.FOUNDER)
        self.assertEqual(context['historical_report']['root_job']['phase_snapshot']['observed_clients'], 0)
        self.assertEqual(context['activation']['status'], 'READY_HEALTHY_DIAGNOSTIC_ACTIVATION')
        original = C.pinned
        try:
            for key, value in [('pid', 2257565), ('starttime_ticks', 38102590)]:
                bad = copy.deepcopy(self.activation)
                bad['owner'][key] = value
                C.pinned = lambda pin, bad=bad: bad if pin['sha256'] == C.ACTIVATION_SHA else original(pin)
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    C.activation_context(case, None)
        finally:
            C.pinned = original
        with self.assertRaises((KeyError, RuntimeError)):
            C.activation_context(dict(recovery=case['activation'], source_freeze_release=job['quality_release']), None)


if __name__ == '__main__':
    unittest.main()
