"""Six deferred CLOSED-metadata guards; root alone may execute this source.

Real check_root_capture consumes actual cb321/e406/1365 metadata. Archived text
is authenticated once, then served by an exact in-memory allowlist. No runtime,
control, numerical imports, tensor referents, or live mutable paths are used.
Synthetic negative copies exercise metadata acceptance, not forged-file hashing.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import unittest

HERE = Path(__file__).resolve().parent
RUN = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26')
BINDER = HERE / 'quality_bindings_payload_metadata.py'
BINDER_SHA = 'e00c135d93ea83e0da23dd5b0a13e323f79023f0c3a111de4d2627bde1d13596'
RESULT = RUN / 'postdiagnostic-live8M-candidate-trial01-20261018/result.json'
RELEASE = RUN / 'postdiagnostic-live8M-candidate-original01-root-execution-20261018/root-original-result-and-owned-release.json'
CASE = RUN / 'postdiagnostic-live8M-fresh-root-case-corrected-archive-bindings-20261018/root-case.json'
EXPECTED = {
    RESULT: 'cb321aab0078cd343c1fe72503f7b3f707431ca4f3d7921306dba567c46c34a2',
    RELEASE: 'e4060a8c194905362f107d5c2d59539e152f1720fe0797a16d1d805f272717e5',
    CASE: '1365b1a20032b4698f8dc3c5da23dc561eb6d9f5e3f7d14abcee3fc319f50129',
}


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def closed(path, expected):
    """Only the selected binder or exact closed JSON/archive allowlist."""
    path = Path(path)
    assert path == BINDER or path in EXPECTED or (
        path.parent == RELEASE.parent and path.suffix == '.txt')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        assert stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o444
        assert before.st_uid == os.getuid() and before.st_nlink == 1
        assert 0 <= before.st_size <= 4 << 20
        raw = stream.read((4 << 20) + 1)
        assert identity(before) == identity(os.fstat(stream.fileno())) == identity(path.lstat())
    pin = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
               bytes=len(raw), identity=identity(before))
    assert pin['sha256'] == expected
    return raw, pin


class PayloadCaptureMetadataContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        closed(BINDER, BINDER_SHA)
        spec = importlib.util.spec_from_file_location('_deferred_payload_metadata', BINDER)
        cls.B = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.B)  # Selected stdlib-only metadata module.
        values = {}
        for path, sha in EXPECTED.items():
            raw, pin = closed(path, sha)
            values[path] = (json.loads(raw), pin)
        cls.result, cls.result_pin = values[RESULT]
        cls.release, cls.release_pin = values[RELEASE]
        cls.case, cls.case_pin = values[CASE]
        assert cls.result['root_case'] == cls.case_pin
        cls.texts = {}
        records = list(cls.release['full_original_archives'])
        records += [r[key] for r in cls.release['owned_release'] for key in ('stop', 'final')]
        for record in records:
            for stream in ('stdout', 'stderr'):
                declared = record[stream]
                raw, actual = closed(declared['path'], declared['sha256'])
                assert all(actual[k] == declared[k] for k in ('path', 'sha256', 'bytes'))
                assert all(actual['identity'][k] == v for k, v in declared['identity'].items())
                cls.texts[declared['path']] = (copy.deepcopy(declared), raw.decode('utf-8', 'surrogateescape'))

    def setUp(self):
        self.unexpected = []

    def tearDown(self):
        self.assertEqual(self.unexpected, [])

    def text(self, pin):
        entry = self.texts.get(pin['path'])
        if entry is None or entry[0] != pin:
            self.unexpected.append(pin)
            raise AssertionError('Unplanned archived-text access; no host fallback')
        return entry[1]

    def check(self, release, *, case=None, case_pin=None):
        return self.B.check_root_capture(release, self.result_pin,
            self.case_pin if case_pin is None else case_pin,
            self.case if case is None else case, self.text)

    def test_actual_current_minimal5_payload_and_original_archives_accept(self):
        self.check(self.release)
        payload = self.release['payload_result']
        self.assertEqual(set(payload), {'path', 'sha256', 'bytes', 'identity'})
        self.assertEqual(set(payload['identity']), {'device', 'inode', 'mode', 'uid', 'nlink'})
        self.assertEqual(payload['sha256'], self.result_pin['sha256'])
        self.assertEqual(self.result['status'], 'CAPTURED_PENDING_ROOT_CPU')
        self.assertFalse(self.result['CPU_executed'])

    def test_legacy_absent_payload_keeps_original_success_requirements(self):
        legacy = copy.deepcopy(self.release)
        del legacy['payload_result']
        self.check(legacy)
        for key, value in [('original_exit', 2), ('original_archived_before_release', False),
                           ('unit_released', False)]:
            bad = copy.deepcopy(legacy)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(bad)

    def test_payload_wrong_path_sha_or_size_refuses_before_any_payload_read(self):
        for key, value in [('path', str(RUN / 'SYNTHETIC-wrong-result.json')),
                           ('sha256', '0' * 64), ('bytes', self.result_pin['bytes'] + 1)]:
            bad = copy.deepcopy(self.release)
            bad['payload_result'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(bad)

    def test_payload_identity_members_must_match_exactly(self):
        for key in ('device', 'inode', 'uid', 'nlink', 'mode'):
            bad = copy.deepcopy(self.release)
            before = bad['payload_result']['identity'][key]
            bad['payload_result']['identity'][key] = '0o664' if key == 'mode' else before + 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(bad)

    def test_payload_extra_missing_malformed_and_equal_numeric_types_refuse(self):
        payload = self.release['payload_result']
        variants = [None, [], {}, 'SYNTHETIC-not-a-pin', copy.deepcopy(self.result_pin)]
        extra = copy.deepcopy(payload)
        extra['extra'] = True
        variants.append(extra)
        missing = copy.deepcopy(payload)
        del missing['identity']['inode']
        variants.append(missing)
        extra_identity = copy.deepcopy(payload)
        extra_identity['identity']['bytes'] = self.result_pin['bytes']
        variants.append(extra_identity)
        wrong_identity = copy.deepcopy(payload)
        wrong_identity['identity'] = []
        variants.append(wrong_identity)
        equal_float = copy.deepcopy(payload)
        equal_float['bytes'] = float(equal_float['bytes'])
        variants.append(equal_float)
        equal_bool = copy.deepcopy(payload)
        equal_bool['identity']['nlink'] = True
        variants.append(equal_bool)
        for index, value in enumerate(variants):
            bad = copy.deepcopy(self.release)
            bad['payload_result'] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.check(bad)

    def test_actual_payload_never_waives_source_owner_archive_or_release_checks(self):
        variants = []
        bad = copy.deepcopy(self.release)
        bad['original']['pid'] += 1
        variants.append(bad)
        bad = copy.deepcopy(self.release)
        bad['full_original_archives'][3]['exit'] = 1
        variants.append(bad)
        bad = copy.deepcopy(self.release)
        bad['owned_release'].reverse()
        variants.append(bad)
        bad = copy.deepcopy(self.release)
        bad['owned_release'][0]['stop']['exit'] = 5
        variants.append(bad)
        for index, bad in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.check(bad)
        wrong_case_pin = copy.deepcopy(self.case_pin)
        wrong_case_pin['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.check(self.release, case_pin=wrong_case_pin)
        wrong_output = copy.deepcopy(self.case)
        wrong_output['output_directory'] = str(RUN / 'SYNTHETIC-wrong-output')
        with self.assertRaises(ValueError):
            self.check(self.release, case=wrong_output)


if __name__ == '__main__':
    unittest.main()
