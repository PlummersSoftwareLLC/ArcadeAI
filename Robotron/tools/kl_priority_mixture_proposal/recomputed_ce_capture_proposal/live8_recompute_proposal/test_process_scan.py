"""Prepared stdlib/private-proc regressions; no live discovery or GPU work.

Authoring is source-only. Root separately authorizes any future execution.
"""
import ast
import contextlib
import copy
import errno
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import cuda_trace_parent as parent


class ProcessScanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='robotron-private-proc-')
        self.addCleanup(self.temporary.cleanup)
        self.proc = Path(self.temporary.name) / 'proc'
        self.proc.mkdir()
        self.calls = []

        def identity(pid, root):
            self.calls.append(pid)
            return json.loads((Path(root) / str(pid) / 'identity.json').read_text())

        self.base = SimpleNamespace(QUALITY_NAMES={'run_frozen_sidecar.py', 'cuda_trace_worker.py'},
                                    identity=identity)
        self.observations = dict(unclassified_cmdline_disappearances=0, last_pid=None, last_errno=None)

    def process(self, pid, words, *, with_identity=True):
        directory = self.proc / str(pid)
        directory.mkdir()
        (directory / 'cmdline').write_bytes(b'\0'.join(word.encode() for word in words) + b'\0')
        identity = dict(pid=pid, start_ticks=pid * 10)
        if with_identity:
            (directory / 'identity.json').write_text(json.dumps(identity))
        return directory, identity

    def scan(self, **kwargs):
        return parent.scan_quality_processes(self.base, proc_root=self.proc,
                                              observations=self.observations, **kwargs)

    def test_actual_enoent_unclassified_candidate_does_not_hide_later_blocked_process(self):
        (self.proc / '101').mkdir()
        words = ['python3', '/private/run_frozen_sidecar.py']
        _, identity = self.process(102, words)
        self.assertEqual(self.scan(), [dict(identity=identity, command=words)])
        self.assertEqual(self.calls, [102])
        self.assertEqual(self.observations, dict(unclassified_cmdline_disappearances=1,
                                                 last_pid=101, last_errno=errno.ENOENT))

    def test_esrch_from_initial_open_is_recorded_and_scan_continues(self):
        directory, _ = self.process(111, ['ordinary-process'])
        _, identity = self.process(112, ['cuda_trace_worker.py'])
        original_open = Path.open

        def raced_open(path, *args, **kwargs):
            if path == directory / 'cmdline':
                raise ProcessLookupError(errno.ESRCH, 'vanished before open')
            return original_open(path, *args, **kwargs)

        with patch.object(Path, 'open', autospec=True, side_effect=raced_open):
            self.assertEqual(self.scan(), [dict(identity=identity, command=['cuda_trace_worker.py'])])
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 1)
        self.assertEqual((self.observations['last_pid'], self.observations['last_errno']), (111, errno.ESRCH))

    def test_esrch_from_initial_file_read_is_recorded_and_scan_continues(self):
        directory, _ = self.process(121, ['ordinary-process'])
        self.process(122, ['ordinary-process'])
        original_open = Path.open

        class VanishedAfterOpen:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, *_):
                raise ProcessLookupError(errno.ESRCH, 'vanished during fread')

        def raced_open(path, *args, **kwargs):
            if path == directory / 'cmdline':
                return VanishedAfterOpen()
            return original_open(path, *args, **kwargs)

        with patch.object(Path, 'open', autospec=True, side_effect=raced_open):
            self.assertEqual(self.scan(), [])
        self.assertEqual(self.observations, dict(unclassified_cmdline_disappearances=1,
                                                 last_pid=121, last_errno=errno.ESRCH))

    def test_exact_allowed_pid_bypass_occurs_before_cmdline_or_identity_access(self):
        directory, _ = self.process(131, ['cuda_trace_worker.py'], with_identity=False)
        original_read = Path.read_bytes

        def forbidden_read(path):
            self.assertNotEqual(path, directory / 'cmdline', 'allowed PID was read')
            return original_read(path)

        with patch.object(Path, 'read_bytes', autospec=True, side_effect=forbidden_read):
            self.assertEqual(self.scan(allowed_pids={131}), [])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 0)

    def test_nonmatching_argv_requires_no_identity_and_malformed_utf8_remains_decodable(self):
        directory, _ = self.process(141, ['ordinary-process'], with_identity=False)
        (directory / 'cmdline').write_bytes(b'ordinary\xff\0--other\0')
        (self.proc / 'nonnumeric').mkdir()
        self.assertEqual(self.scan(), [])
        self.assertEqual(self.calls, [])

    def test_blocked_predicate_preserves_all_argv_module_and_benchmark_forms(self):
        commands = [
            ['python3', '/private/run_frozen_sidecar.py'],
            ['carrier', '--label', '/private/cuda_trace_worker.py'],
            ['python3', '-m', 'package.run_frozen_sidecar'],
            ['/private/benchmark_sampler.py', '--unrelated'],
            ['python3', '-m', 'package.benchmark_sampler'],
        ]
        expected = []
        for pid, words in enumerate(commands, start=151):
            _, identity = self.process(pid, words)
            expected.append(dict(identity=identity, command=words))
        actual = self.scan()
        self.assertEqual(sorted(actual, key=lambda item: item['identity']['pid']), expected)
        self.assertEqual(sorted(self.calls), list(range(151, 156)))
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 0)

    def test_classified_identity_enoent_is_fatal_with_pid_and_original_cause(self):
        self.process(161, ['run_frozen_sidecar.py'], with_identity=False)
        with self.assertRaisesRegex(RuntimeError, 'Classified blocked process identity failed PID161') as caught:
            self.scan()
        self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)
        self.assertEqual(caught.exception.__cause__.errno, errno.ENOENT)
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 0)

    def test_classified_identity_esrch_and_other_errors_are_all_fatal(self):
        self.process(171, ['cuda_trace_worker.py'])
        for number in (errno.ESRCH, errno.EACCES, errno.EIO, errno.ESTALE):
            with self.subTest(errno=number), patch.object(self.base, 'identity',
                    side_effect=OSError(number, 'classified identity unavailable')):
                with self.assertRaisesRegex(RuntimeError, 'PID171') as caught:
                    self.scan()
                self.assertEqual(caught.exception.__cause__.errno, number)
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 0)

    def test_initial_permission_failure_is_fatal_with_context(self):
        directory, _ = self.process(181, ['ordinary-process'])
        original_read = Path.read_bytes

        def denied(path):
            if path == directory / 'cmdline':
                raise PermissionError(errno.EACCES, 'denied')
            return original_read(path)

        with patch.object(Path, 'read_bytes', autospec=True, side_effect=denied):
            with self.assertRaisesRegex(RuntimeError, 'Cannot establish process ownership: 181') as caught:
                self.scan()
        self.assertEqual(caught.exception.__cause__.errno, errno.EACCES)
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 0)

    def test_initial_eio_estale_and_other_errno_are_not_disappearances(self):
        directory, _ = self.process(191, ['ordinary-process'])
        original_read = Path.read_bytes
        for number in (errno.EIO, errno.ESTALE, errno.EBUSY):
            def failed(path):
                if path == directory / 'cmdline':
                    raise OSError(number, 'not a disappearance')
                return original_read(path)

            with self.subTest(errno=number), patch.object(Path, 'read_bytes', autospec=True, side_effect=failed):
                with self.assertRaises(OSError) as caught:
                    self.scan()
                self.assertEqual(caught.exception.errno, number)
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 0)

    def test_directory_enumeration_failure_is_fatal_even_for_enoent_esrch(self):
        for number in (errno.ENOENT, errno.ESRCH, errno.EACCES, errno.EIO):
            def failed_iterator(_):
                raise OSError(number, 'proc enumeration failed')

            with self.subTest(errno=number), patch.object(Path, 'iterdir', autospec=True,
                                                         side_effect=failed_iterator):
                with self.assertRaises(OSError) as caught:
                    self.scan()
                self.assertEqual(caught.exception.errno, number)
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 0)

    def test_directory_enumeration_midstream_failure_is_not_skipped(self):
        directory, _ = self.process(201, ['ordinary-process'])

        def partial_iterator(_):
            yield directory
            raise ProcessLookupError(errno.ESRCH, 'enumerator failed')

        with patch.object(Path, 'iterdir', autospec=True, side_effect=partial_iterator):
            with self.assertRaises(ProcessLookupError):
                self.scan()
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 0)

    def test_decode_failure_after_read_is_outside_disappearance_catch(self):
        self.process(211, ['ordinary-process'])

        class BadPart:
            def decode(self, **_):
                raise ProcessLookupError(errno.ESRCH, 'not a cmdline I/O failure')

        class BadRaw:
            def split(self, _):
                return [BadPart()]

        with patch.object(Path, 'read_bytes', return_value=BadRaw()):
            with self.assertRaises(ProcessLookupError):
                self.scan()
        self.assertEqual(self.observations['unclassified_cmdline_disappearances'], 0)

    def test_bounded_counter_accumulates_and_last_disappearance_replaces_previous(self):
        (self.proc / '221').mkdir()
        self.assertEqual(self.scan(), [])
        (self.proc / '221' / 'cmdline').write_bytes(b'ordinary-process\0')
        (self.proc / '222').mkdir()
        self.assertEqual(self.scan(), [])
        self.assertEqual(self.observations, dict(unclassified_cmdline_disappearances=2,
                                                 last_pid=222, last_errno=errno.ENOENT))

    def test_helpers_wire_dynamic_scan_log_counter_once_per_changed_guard_and_keep_failures(self):
        (self.proc / '231').mkdir()
        self.base.GPU0_UUID = 'private-test-gpu'
        self.base.guard_live_resources = lambda **kwargs: dict(blocked=self.base.scan_quality_processes(
            proc_root=self.proc, allowed_pids=kwargs.get('allowed_pids', ())), gpu=dict(devices={
                self.base.GPU0_UUID: dict(free_bytes=14 * parent.GIB)}))
        lock = dict(immutable_helpers=dict(launcher=dict(source='never-imported-launcher', sha256='unused'),
                                          worker=dict(source='never-imported-worker', sha256='unused')))
        old_base = parent._BASE
        self.addCleanup(setattr, parent, '_BASE', old_base)
        with patch.object(parent, 'checked_module', side_effect=[self.base, SimpleNamespace()]), \
                contextlib.redirect_stderr(io.StringIO()) as captured:
            base, _ = parent.helpers(lock)
            self.assertEqual(base.guard_live_resources(initial=True)['blocked'], [])
            (self.proc / '231' / 'cmdline').write_bytes(b'ordinary-process\0')
            self.assertEqual(base.guard_live_resources()['blocked'], [])
        lines = captured.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith('[PROCESS SCAN] '))
        record = json.loads(lines[0].removeprefix('[PROCESS SCAN] '))
        self.assertEqual(record['scope'], 'initial unclassified cmdline only')
        self.assertEqual(record['process_id'], parent.os.getpid())
        self.assertEqual(record['unclassified_cmdline_disappearances'], 1)
        self.assertEqual((record['last_pid'], record['last_errno']), (231, errno.ENOENT))
        self.assertEqual(base.BOUNDS, parent.BOUNDS)
        self.assertTrue(parent.BLOCKED_NAMES <= base.QUALITY_NAMES)

    def test_helpers_log_changed_counter_even_when_later_classified_guard_fails(self):
        vanished = self.proc / '241'
        vanished.mkdir()
        blocked, _ = self.process(242, ['cuda_trace_worker.py'], with_identity=False)

        def ordered_entries(path):
            self.assertEqual(path, self.proc)
            return iter([vanished, blocked])

        self.base.guard_live_resources = lambda **kwargs: self.base.scan_quality_processes(proc_root=self.proc)
        lock = dict(immutable_helpers=dict(launcher=dict(source='never-imported-launcher', sha256='unused'),
                                          worker=dict(source='never-imported-worker', sha256='unused')))
        old_base = parent._BASE
        self.addCleanup(setattr, parent, '_BASE', old_base)
        with patch.object(parent, 'checked_module', side_effect=[self.base, SimpleNamespace()]), \
                patch.object(Path, 'iterdir', autospec=True, side_effect=ordered_entries), \
                contextlib.redirect_stderr(io.StringIO()) as captured:
            base, _ = parent.helpers(lock)
            with self.assertRaisesRegex(RuntimeError, 'PID242'):
                base.guard_live_resources()
        record = json.loads(captured.getvalue().strip().removeprefix('[PROCESS SCAN] '))
        self.assertEqual(record['unclassified_cmdline_disappearances'], 1)
        self.assertEqual(record['last_pid'], 241)

    def test_predicate_and_storage_functions_are_ast_identical_to_pinned_sources(self):
        lock = json.loads((parent.HERE / 'source-lock.json').read_text())
        old = ast.parse(Path(lock['immutable_helpers']['launcher']['source']).read_text())
        current = ast.parse((parent.HERE / 'cuda_trace_parent.py').read_text())
        previous_bytes = (parent.HERE.parents[1] / 'cuda_trace_validation_proposal/process_scan_revision/cuda_trace_parent.py').read_bytes()
        self.assertEqual(hashlib.sha256(previous_bytes).hexdigest(),
                         '38fab41957a4b3ff53f878f477e18b741497e34b4836fcde444aa4c1be851abe')
        storage = ast.parse(previous_bytes)

        def function(tree, name):
            return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)

        class RemoveBase(ast.NodeTransformer):
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name) and node.value.id == 'base' and node.attr == 'QUALITY_NAMES':
                    return ast.copy_location(ast.Name(id='QUALITY_NAMES', ctx=ast.Load()), node)
                return self.generic_visit(node)

        def predicate(tree):
            scanner = function(tree, 'scan_quality_processes')
            return next(node for node in ast.walk(scanner) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name) and node.func.id == 'any')

        self.assertEqual(ast.dump(RemoveBase().visit(copy.deepcopy(predicate(current)))), ast.dump(predicate(old)))
        for name in ('storage_directory_identity', 'owned_byte_count', 'scan_quality_processes',
                     'helpers', 'command', 'stable_file'):
            before, after = function(storage, name), function(current, name)
            self.assertEqual(ast.dump(before), ast.dump(after), name)

        def lifecycle_prefix(node):
            # Everything through child teardown and reading phase-result is exact;
            # only the subsequent diagnostic role-result validation is different.
            end = next(index for index, statement in enumerate(node.body)
                       if isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name)
                           and target.id == 'result' for target in statement.targets))
            return ast.Module(body=node.body[:end + 1], type_ignores=[])

        self.assertEqual(ast.dump(lifecycle_prefix(function(storage, 'run_variant'))),
                         ast.dump(lifecycle_prefix(function(current, 'run_variant'))))

    def test_literal_default_and_fixed_geometry_worker_lock_and_bounds(self):
        with patch.object(parent, 'read_lock', side_effect=AssertionError('no source/data reads')), \
                patch.object(parent, 'helpers', side_effect=AssertionError('no helper imports')), \
                patch.object(parent, 'scan_quality_processes', side_effect=AssertionError('no process query')), \
                patch.object(parent.subprocess, 'Popen', side_effect=AssertionError('no child')), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('no output')), \
                contextlib.redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(parent.main([]), 0)
        result = json.loads(captured.getvalue())
        self.assertEqual(result['status'], 'PLAN_ONLY_UNEXECUTED')
        self.assertFalse(result['runtime_queries'])
        self.assertEqual(parent.GAME, Path(__file__).parents[4])
        self.assertEqual(parent.VARIANTS, ('recompute8',))
        self.assertEqual(result['attempts'], 8)
        self.assertEqual(result['actual_training_attempts'], 0)
        self.assertFalse(hasattr(parent, 'copy_fixture'))
        self.assertEqual(result['compiled_loss_outputs'], 4)
        self.assertEqual(result['offline_outputs'], 5)
        self.assertFalse(result['qualification_pass'])
        self.assertEqual(parent.BOUNDS, dict(cpu_threads=2, memory_bytes=16 * (1 << 30),
            vram_allocator_bytes=12 * (1 << 30), vram_process_bytes=13 * (1 << 30),
            artifact_bytes=6 * (1 << 30), tmpfs_bytes=128 * (1 << 20), tasks=128,
            phase_timeout_s=180, total_timeout_s=600))
        lock_bytes = (parent.HERE / 'source-lock.json').read_bytes()
        self.assertEqual(hashlib.sha256(lock_bytes).hexdigest(),
                         '683278660704999645e93dfbc7aad1b20423a5755080a76ccad8f3af54c3c82f')
        lock = json.loads(lock_bytes)
        frozen = lock['frozen_science_helpers']
        self.assertEqual(frozen['sha256'],
                         'ba0039d406676f092309c6bf2248ddcf169af8960f60ed18b698ece1ea602f93')
        self.assertEqual(hashlib.sha256(Path(frozen['source']).read_bytes()).hexdigest(), frozen['sha256'])


if __name__ == '__main__':
    unittest.main()
