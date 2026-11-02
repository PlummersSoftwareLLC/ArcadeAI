"""Dormant stdlib metadata guards; AUTHOR UNEXECUTED.

Future root execution only. Extract TWO authenticated pure launcher functions,
never import its module or call preflight/run_original/execute/main. Embedded
old job/report paths are compared as strings and never followed. Numerical
binder checks are strict scripted delegation boundaries, not numerical tests.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import unittest


HERE = Path(__file__).resolve().parent
SOURCE_SHA = '24e81273f99fa540bdebd3a1d3eb7fab85f5e5e4af2c2fdaab8bfa74996b53f3'
FIXTURE_SHA = 'cbdee237e7d48b7efc6bf2b1e8eb37b70bdd33124110cf568b9a8667f91f6f0f'


def local_source(name, expected):
    # Exactly these new, sealed local files; no embedded path is opened.
    if name not in ('run_candidate_cpu.py', 'closed-fingerprint-reference.json'):
        raise AssertionError('Unexpected fixture/source file')
    path = HERE / name
    before = path.lstat()
    raw = path.read_bytes()
    after = path.lstat()
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns,
                          s.st_ctime_ns, s.st_mode, s.st_uid, s.st_nlink)
    if not (stat.S_ISREG(before.st_mode) and not path.is_symlink()
            and stat.S_IMODE(before.st_mode) == 0o444
            and identity(before) == identity(after)
            and hashlib.sha256(raw).hexdigest() == expected):
        raise AssertionError('Sealed local source/fixture differs')
    return raw


class JobFingerprintContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = local_source('run_candidate_cpu.py', SOURCE_SHA).decode()
        cls.reference = json.loads(local_source('closed-fingerprint-reference.json', FIXTURE_SHA))
        names = {'check_report_job_file', 'check_CPU_semantics'}
        tree = ast.parse(source)
        selected = [node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name in names]
        if {node.name for node in selected} != names or len(selected) != 2:
            raise AssertionError('Exact pure source seams missing')
        for node in selected:
            if any(isinstance(child, (ast.Import, ast.ImportFrom)) for child in ast.walk(node)):
                raise AssertionError('Pure seams cannot import anything')
        # No subprocess, os, runtime reader, open, import hook or launcher API.
        namespace = {'Path': PurePosixPath, '__builtins__': {
            'type': type, 'dict': dict, 'set': set, 'str': str, 'int': int, 'list': list,
            'all': all, 'len': len, 'AssertionError': AssertionError}}
        program = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
        exec(compile(program, '<two sealed metadata seams only>', 'exec'), namespace)
        cls.fingerprint = staticmethod(namespace['check_report_job_file'])
        cls.semantic = staticmethod(namespace['check_CPU_semantics'])

    def setUp(self):
        self.unexpected = []
        self.job_pin = copy.deepcopy(self.reference['job_pin'])
        self.flat = copy.deepcopy(self.reference['report_job_file'])

    def tearDown(self):
        # Checked OUTSIDE target AssertionError catches: scripted API errors
        # cannot masquerade as a successful negative test.
        self.assertEqual(self.unexpected, [])

    def semantic_inputs(self, *, fail=None, allow_delegates=True):
        owner = self
        report = {'status': 'PASS', 'job_file': copy.deepcopy(self.flat)}
        terminal = {'original_exec_code': 1, 'original_exit': 0, 'original_result': 'success'}
        completion = {'argv': ['synthetic-numeric-command'], 'exit_code': 0}
        groups = {'service_cat': {'stdout': {'scripted': 'cat'}},
                  'service_show': {'stdout': {'scripted': 'show'}}}
        job = {'scripted': 'job'}
        candidate = {'scripted': 'candidate'}

        class Bindings:
            def __init__(self):
                self.calls = []

            def expect(self, condition, description):
                if not condition:
                    owner.unexpected.append(description)
                    raise AssertionError(description)

            def archive_text(self, *args, **kwargs):
                self.expect(False, 'No archive reader may run in these pure fixtures')

            def check_cpu(self, actual_job, actual_report, actual_completion, actual_candidate):
                self.expect(allow_delegates, 'Unexpected numerical delegate after refused metadata')
                self.expect(actual_job is job and actual_report is report
                            and actual_completion is completion and actual_candidate is candidate,
                            'Numerical delegate arguments changed')
                self.calls.append('cpu')
                if fail == 'cpu':
                    raise ValueError('scripted strict CPU refusal')

            def check_CPU_command(self, actual_execution, actual_completion, text_reader):
                self.expect(allow_delegates, 'Unexpected command delegate after refused metadata')
                self.expect(actual_execution == {'cat': groups['service_cat']['stdout'],
                                                  'show': groups['service_show']['stdout']}
                            and actual_completion is completion and text_reader == self.archive_text,
                            'Command delegate arguments changed')
                self.calls.append('command')
                if fail == 'command':
                    raise ValueError('scripted original command refusal')

            def __getattr__(self, name):
                self.expect(False, 'Unexpected binder API: ' + name)

        bindings = Bindings()
        context = {'B': bindings, 'job_pin': copy.deepcopy(self.job_pin),
                   'job': job, 'candidate': candidate}
        return context, terminal, report, completion, groups

    def test_authentic_closed_flat10_and_full8_projection_then_real_delegation_seam(self):
        self.assertEqual(self.reference['closed_original_report_status'], 'PASS')
        self.assertEqual(self.reference['closed_original_wrapper_status'], 'FAIL')
        self.assertNotEqual(self.flat, self.job_pin)  # Original shape-only trap.
        self.assertEqual(set(self.job_pin), {'path', 'sha256', 'bytes', 'identity'})
        self.assertEqual(len(self.job_pin['identity']), 8)
        self.assertEqual(len(self.flat), 10)
        self.assertIsNone(self.fingerprint(self.flat, self.job_pin))
        args = self.semantic_inputs()
        self.assertIsNone(self.semantic(*args))
        self.assertEqual(args[0]['B'].calls, ['cpu', 'command'])

    def test_every_declared_path_hash_and_identity_value_mismatch_refuses(self):
        for key, value in self.flat.items():
            with self.subTest(flat_field=key):
                altered = copy.deepcopy(self.flat)
                altered[key] = (value + 1 if type(value) is int else
                                '0' * 64 if key == 'sha256' else value + '-different')
                with self.assertRaises(AssertionError):
                    self.fingerprint(altered, self.job_pin)
        for key in self.job_pin['identity']:
            with self.subTest(full_identity_field=key):
                altered = copy.deepcopy(self.job_pin)
                value = altered['identity'][key]
                altered['identity'][key] = value + 1 if type(value) is int else value + '-different'
                if key == 'bytes':
                    altered['bytes'] = altered['identity'][key]
                with self.assertRaises(AssertionError):
                    self.fingerprint(self.flat, altered)
        altered = copy.deepcopy(self.job_pin)
        altered['bytes'] += 1  # Explicit outer/identity byte-count disagreement.
        with self.assertRaises(AssertionError):
            self.fingerprint(self.flat, altered)

    def test_exact_fieldsets_and_types_reject_missing_extra_and_bool_integer_aliases(self):
        for key in self.flat:
            with self.subTest(missing_flat=key):
                altered = copy.deepcopy(self.flat); del altered[key]
                with self.assertRaises(AssertionError):
                    self.fingerprint(altered, self.job_pin)
        altered = dict(self.flat, unexpected=0)
        with self.assertRaises(AssertionError):
            self.fingerprint(altered, self.job_pin)
        for key in self.job_pin:
            altered = copy.deepcopy(self.job_pin); del altered[key]
            with self.subTest(missing_full=key), self.assertRaises(AssertionError):
                self.fingerprint(self.flat, altered)
        for key in self.job_pin['identity']:
            altered = copy.deepcopy(self.job_pin); del altered['identity'][key]
            with self.subTest(missing_identity=key), self.assertRaises(AssertionError):
                self.fingerprint(self.flat, altered)
        for target in ('top', 'identity'):
            altered = copy.deepcopy(self.job_pin)
            (altered if target == 'top' else altered['identity'])['extra'] = 1
            with self.assertRaises(AssertionError):
                self.fingerprint(self.flat, altered)
        # Equality alone would allow True==1. Use a valid synthetic projection
        # with one-valued integers, then change only its TYPE in each location.
        numeric = {'device', 'inode', 'bytes', 'mtime_ns', 'ctime_ns', 'uid', 'nlink'}
        base_pin = copy.deepcopy(self.job_pin)
        for key in numeric:
            base_pin['identity'][key] = 1
        base_pin['bytes'] = 1
        base_flat = dict(path=base_pin['path'], sha256=base_pin['sha256'], **base_pin['identity'])
        for key in numeric:
            altered = copy.deepcopy(base_flat); altered[key] = True
            with self.subTest(bool_flat=key), self.assertRaises(AssertionError):
                self.fingerprint(altered, base_pin)
            altered_pin = copy.deepcopy(base_pin); altered_pin['identity'][key] = True
            with self.subTest(bool_full=key), self.assertRaises(AssertionError):
                self.fingerprint(base_flat, altered_pin)
        altered_pin = copy.deepcopy(base_pin); altered_pin['bytes'] = True
        with self.assertRaises(AssertionError):
            self.fingerprint(base_flat, altered_pin)
        for key in ('path', 'sha256', 'mode'):
            altered = copy.deepcopy(self.flat); altered[key] = 1
            with self.subTest(non_string=key), self.assertRaises(AssertionError):
                self.fingerprint(altered, self.job_pin)

    def test_missing_failed_report_and_native_or_completion_error_never_delegate(self):
        mutations = [('report_none', None), ('report_empty', {}), ('report_fail', 'FAIL'),
                     ('missing_job_file', None), ('native_code', 2), ('native_exit', 7),
                     ('native_result', 'exit-code'), ('native_code_bool', True),
                     ('native_exit_bool', False), ('completion_exit', 3),
                     ('completion_exit_bool', False), ('completion_extra', None)]
        for kind, value in mutations:
            with self.subTest(kind=kind):
                args = list(self.semantic_inputs(allow_delegates=False))
                if kind in ('report_none', 'report_empty'):
                    args[2] = value
                elif kind == 'report_fail':
                    args[2]['status'] = value
                elif kind == 'missing_job_file':
                    del args[2]['job_file']
                elif kind in ('native_code', 'native_code_bool'):
                    args[1]['original_exec_code'] = value
                elif kind in ('native_exit', 'native_exit_bool'):
                    args[1]['original_exit'] = value
                elif kind == 'native_result':
                    args[1]['original_result'] = value
                elif kind in ('completion_exit', 'completion_exit_bool'):
                    args[3]['exit_code'] = value
                else:
                    args[3]['extra'] = 0
                with self.assertRaises((AssertionError, KeyError)):
                    self.semantic(*args)
                self.assertEqual(args[0]['B'].calls, [])

    def test_strict_numerical_or_command_delegate_refusal_propagates_once_without_retry(self):
        for failing, calls in [('cpu', ['cpu']), ('command', ['cpu', 'command'])]:
            with self.subTest(delegate=failing):
                args = self.semantic_inputs(fail=failing)
                with self.assertRaisesRegex(ValueError, 'scripted'):
                    self.semantic(*args)
                self.assertEqual(args[0]['B'].calls, calls)
