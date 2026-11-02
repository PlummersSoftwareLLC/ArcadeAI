"""UNEXECUTED stdlib/tempfile watcher tests; no helpers, runtime or GPU work."""
import errno
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import cuda_trace_parent as parent


class StorageWatcherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='robotron-private-watcher-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.root = self.directory / 'output'
        self.cache = self.root / 'base/cache'
        self.triton = self.cache / 'triton'
        self.triton.mkdir(parents=True)
        (self.root / 'science.pt').write_bytes(b'scientific!')
        (self.cache / 'persistent.bin').write_bytes(b'cached!')
        self.root_identity = parent.storage_directory_identity(self.root)
        self.cache_identity = parent.storage_directory_identity(self.cache)
        self.events = dict(ignored_enoent=0, last_relative_path=None)

    def count(self, *, active=True, observer=None, extra_caches=()):
        caches = (((self.cache, self.cache_identity),) if active else ()) + tuple(extra_caches)
        return parent.owned_byte_count(self.root, self.root_identity,
                                       volatile_caches=caches, events=self.events, observer=observer)

    def observer(self):
        directory = self.root / 'on/ce-executed-trace-cuda-validation'
        directory.mkdir(parents=True)
        return dict(path=str(directory), identity=None, ignored_temp_enoent=0,
                    last_temp_name=None, status_replacements=0)

    def test_nested_source_geometry_and_fixed_protocol_unchanged(self):
        self.assertEqual(parent.GAME, Path(__file__).parents[4])
        self.assertEqual(parent.REPO, parent.GAME.parent)
        self.assertEqual((parent.GAME/'Scripts/dqn/config.py').parts[-4:],
                         ('Robotron', 'Scripts', 'dqn', 'config.py'))
        self.assertEqual(parent.VARIANTS, ('capture', 'recompute'))
        self.assertEqual(parent.BOUNDS['artifact_bytes'], 6 * (1 << 30))
        self.assertEqual(parent.BOUNDS['phase_timeout_s'], 180)
        self.assertEqual(parent.BOUNDS['total_timeout_s'], 600)
        lock_bytes = (parent.HERE/'source-lock.json').read_bytes()
        self.assertEqual(hashlib.sha256(lock_bytes).hexdigest(),
                         '28870c3cf7594cc0ac8f73eb3760e3665d5d4448668f4bf9010268427ec80dd3')
        frozen = json.loads(lock_bytes)['frozen_science_helpers']
        self.assertEqual(frozen['sha256'],
                         'ba0039d406676f092309c6bf2248ddcf169af8960f60ed18b698ece1ea602f93')
        self.assertEqual(hashlib.sha256(Path(frozen['source']).read_bytes()).hexdigest(), frozen['sha256'])

    def test_literal_default_does_not_import_helpers_or_touch_storage_or_launch(self):
        with patch.object(parent, 'read_lock', side_effect=AssertionError('no source reads')), \
                patch.object(parent, 'helpers', side_effect=AssertionError('no helper imports')), \
                patch.object(parent, 'owned_byte_count', side_effect=AssertionError('no storage queries')), \
                patch.object(parent.subprocess, 'Popen', side_effect=AssertionError('no child')), \
                contextlib.redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(parent.main([]), 0)
        self.assertIn('PLAN_ONLY_UNEXECUTED', captured.getvalue())

    def test_existing_scientific_and_cache_bytes_counted(self):
        self.assertEqual(self.count(), len(b'scientific!') + len(b'cached!'))
        self.assertEqual(self.events['ignored_enoent'], 0)

    def test_cache_file_removed_between_enumeration_and_stat_is_only_enoent_allowance(self):
        victim = self.triton / 'tmp.removed'
        victim.write_bytes(b'temporary')
        real_stat = os.stat
        fired = []
        def raced(path, *args, **kwargs):
            if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                fired.append(True)
                victim.unlink()
            return real_stat(path, *args, **kwargs)
        with patch.object(parent.os, 'stat', side_effect=raced):
            self.assertEqual(self.count(), len(b'scientific!') + len(b'cached!'))
        self.assertEqual(self.events['ignored_enoent'], 1)
        self.assertEqual(self.events['last_relative_path'], 'triton/tmp.removed')

    def test_cache_file_and_directory_renamed_after_enumeration(self):
        real_stat, real_open = os.stat, os.open
        for directory in (False, True):
            with self.subTest(directory=directory):
                victim = self.triton / ('tmp.dir' if directory else 'tmp.file')
                if directory:
                    victim.mkdir()
                else:
                    victim.write_bytes(b'temporary')
                renamed = self.triton / (victim.name + '.renamed')
                fired = []
                def raced_stat(path, *args, **kwargs):
                    if not directory and path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                        fired.append(True)
                        victim.rename(renamed)
                    return real_stat(path, *args, **kwargs)
                def raced_open(path, *args, **kwargs):
                    if directory and path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                        fired.append(True)
                        victim.rename(renamed)
                    return real_open(path, *args, **kwargs)
                with patch.object(parent.os, 'stat', side_effect=raced_stat), \
                        patch.object(parent.os, 'open', side_effect=raced_open):
                    self.assertEqual(self.count(), len(b'scientific!') + len(b'cached!'))
                self.assertTrue(fired)
                if directory:
                    renamed.rmdir()
                else:
                    renamed.unlink()
        self.assertEqual(self.events['ignored_enoent'], 2)

    def test_cache_directory_removed_during_scandir_is_tolerated(self):
        victim = self.triton / 'tmp.enumeration'
        victim.mkdir()
        identity = victim.stat()
        real_scandir = os.scandir
        fired = []
        def raced(descriptor):
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) == (identity.st_dev, identity.st_ino) and not fired:
                fired.append(True)
                victim.rmdir()
                raise FileNotFoundError(errno.ENOENT, 'private cache directory removed')
            return real_scandir(descriptor)
        with patch.object(parent.os, 'scandir', side_effect=raced):
            self.assertEqual(self.count(), len(b'scientific!') + len(b'cached!'))
        self.assertTrue(fired)
        self.assertGreaterEqual(self.events['ignored_enoent'], 1)

    def test_cache_symlink_and_directory_symlink_are_strict(self):
        for directory in (False, True):
            with self.subTest(directory=directory):
                target = self.directory / ('external-dir' if directory else 'external-file')
                if directory:
                    target.mkdir()
                else:
                    target.write_bytes(b'external private fixture')
                link = self.triton / 'link'
                link.symlink_to(target, target_is_directory=directory)
                with self.assertRaisesRegex(RuntimeError, 'symlink'):
                    self.count()
                link.unlink()

    def test_permission_io_stale_and_process_lookup_errors_never_ignored(self):
        victim = self.triton / 'strict-error'
        victim.write_bytes(b'cached')
        real_stat = os.stat
        for code in (errno.EACCES, errno.EIO, errno.ESTALE, errno.ESRCH):
            def error(path, *args, **kwargs):
                if path == victim.name and kwargs.get('dir_fd') is not None:
                    raise OSError(code, 'private injected I/O error')
                return real_stat(path, *args, **kwargs)
            with self.subTest(errno=code), patch.object(parent.os, 'stat', side_effect=error):
                with self.assertRaises(OSError) as caught:
                    self.count()
                self.assertEqual(caught.exception.errno, code)
        self.assertEqual(self.events['ignored_enoent'], 0)

    def test_noncache_scientific_file_disappearance_fails(self):
        victim = self.root / 'science.pt'
        real_stat = os.stat
        def raced(path, *args, **kwargs):
            if path == victim.name and kwargs.get('dir_fd') is not None and victim.exists():
                victim.unlink()
            return real_stat(path, *args, **kwargs)
        with patch.object(parent.os, 'stat', side_effect=raced):
            with self.assertRaises(FileNotFoundError):
                self.count()
        self.assertEqual(self.events['ignored_enoent'], 0)

    def test_noncache_directory_enumeration_disappearance_fails(self):
        victim = self.root / 'scientific-data'
        victim.mkdir()
        identity = victim.stat()
        real_scandir = os.scandir
        def raced(descriptor):
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) == (identity.st_dev, identity.st_ino):
                raise FileNotFoundError(errno.ENOENT, 'private noncache directory lost')
            return real_scandir(descriptor)
        with patch.object(parent.os, 'scandir', side_effect=raced):
            with self.assertRaises(FileNotFoundError):
                self.count()
        self.assertEqual(self.events['ignored_enoent'], 0)

    def test_inactive_cache_enoent_is_strict_after_child_reap(self):
        victim = self.triton / 'stale.tmp'
        victim.write_bytes(b'temporary')
        real_stat = os.stat
        def lost(path, *args, **kwargs):
            if path == victim.name and kwargs.get('dir_fd') is not None:
                raise FileNotFoundError(errno.ENOENT, 'no active writer allowed')
            return real_stat(path, *args, **kwargs)
        with patch.object(parent.os, 'stat', side_effect=lost):
            with self.assertRaises(FileNotFoundError):
                self.count(active=False)
        self.assertEqual(self.events['ignored_enoent'], 0)

    def test_cache_boundary_missing_or_replaced_is_never_ignored(self):
        renamed = self.root / 'base/cache-renamed'
        self.cache.rename(renamed)
        with self.assertRaises(FileNotFoundError):
            self.count()
        self.cache.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'boundary changed'):
            self.count()
        self.assertEqual(self.events['ignored_enoent'], 0)

    def test_root_replacement_during_walk_fails_final_identity_check(self):
        real_scandir = os.scandir
        fired = []
        def raced(descriptor):
            info = os.fstat(descriptor)
            if dict(device=info.st_dev, inode=info.st_ino) == self.root_identity and not fired:
                fired.append(True)
                self.root.rename(self.directory / 'old-output')
                self.root.mkdir()
            return real_scandir(descriptor)
        with patch.object(parent.os, 'scandir', side_effect=raced):
            with self.assertRaisesRegex(RuntimeError, 'storage root identity changed'):
                self.count()
        self.assertTrue(fired)

    def test_active_cache_atomic_regular_publication_counts_max_size_and_records(self):
        victim = self.triton / 'kernel.bin'
        victim.write_bytes(b'old')
        real_stat = os.stat
        fired = []
        def raced(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                fired.append(True)
                temporary = self.triton / 'new.tmp'
                temporary.write_bytes(b'new expanded kernel')
                os.replace(temporary, victim)
            return info
        with patch.object(parent.os, 'stat', side_effect=raced):
            self.assertEqual(self.count(), len(b'scientific!') + len(b'cached!') + len(b'new expanded kernel'))
        self.assertEqual(self.events['regular_cache_replacements'], 1)
        self.assertEqual(self.events['last_cache_replacement_relative_path'], 'triton/kernel.bin')

    def test_noncache_regular_replacement_is_strict(self):
        victim = self.root / 'science.pt'
        real_stat = os.stat
        fired = []
        def raced(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                fired.append(True)
                temporary = self.root / 'replacement.tmp'
                temporary.write_bytes(b'new scientific bytes')
                os.replace(temporary, victim)
            return info
        with patch.object(parent.os, 'stat', side_effect=raced):
            with self.assertRaisesRegex(RuntimeError, 'entry replaced'):
                self.count()

    def test_only_exact_direct_observer_json_temporary_disappearance_allowed(self):
        observer = self.observer()
        directory = Path(observer['path'])
        names = ['context.json.tmp', 'status.json.tmp'] + ['attempt-%02d.json.tmp' % i for i in range(1, 9)]
        real_stat = os.stat
        for name in names:
            victim = directory / name
            victim.write_bytes(b'temporary JSON')
            fired = []
            def raced(path, *args, **kwargs):
                if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                    fired.append(True)
                    victim.unlink()
                return real_stat(path, *args, **kwargs)
            with self.subTest(name=name), patch.object(parent.os, 'stat', side_effect=raced):
                self.assertEqual(self.count(observer=observer), len(b'scientific!') + len(b'cached!'))
            self.assertTrue(fired)
        self.assertEqual(observer['ignored_temp_enoent'], 10)
        self.assertEqual(self.events['ignored_enoent'], 0)

    def test_observer_status_atomic_regular_replacement_is_exact_exception(self):
        observer = self.observer()
        directory = Path(observer['path'])
        victim = directory / 'status.json'
        victim.write_bytes(b'old status')
        real_stat = os.stat
        fired = []
        def raced(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                fired.append(True)
                temporary = directory / 'status.json.tmp'
                temporary.write_bytes(b'new expanded status')
                os.replace(temporary, victim)
            return info
        with patch.object(parent.os, 'stat', side_effect=raced):
            self.assertEqual(self.count(observer=observer),
                             len(b'scientific!') + len(b'cached!') + len(b'new expanded status'))
        self.assertEqual(observer['status_replacements'], 1)

    def test_persistent_observer_context_attempt_or_status_disappearance_fails(self):
        observer = self.observer()
        directory = Path(observer['path'])
        real_stat = os.stat
        for name in ('context.json', 'attempt-01.json', 'attempt-08.json', 'status.json'):
            victim = directory / name
            victim.write_bytes(b'persistent evidence')
            fired = []
            def raced(path, *args, **kwargs):
                if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                    fired.append(True)
                    victim.unlink()
                return real_stat(path, *args, **kwargs)
            with self.subTest(name=name), patch.object(parent.os, 'stat', side_effect=raced):
                with self.assertRaises(FileNotFoundError):
                    self.count(observer=observer)
        self.assertEqual(observer['ignored_temp_enoent'], 0)

    def test_wrong_temp_names_outside_directory_and_nested_names_are_strict(self):
        observer = self.observer()
        directory = Path(observer['path'])
        nested = directory / 'nested'
        nested.mkdir()
        victims = [directory/'attempt-00.json.tmp', directory/'attempt-09.json.tmp',
                   directory/'other.json.tmp', self.root/'status.json.tmp', nested/'status.json.tmp']
        real_stat = os.stat
        for victim in victims:
            victim.write_bytes(b'undeclared temporary')
            fired = []
            def raced(path, *args, **kwargs):
                if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                    fired.append(True)
                    victim.unlink()
                return real_stat(path, *args, **kwargs)
            with self.subTest(path=str(victim)), patch.object(parent.os, 'stat', side_effect=raced):
                with self.assertRaises(FileNotFoundError):
                    self.count(observer=observer)
        self.assertEqual(observer['ignored_temp_enoent'], 0)

    def test_observer_directory_cannot_disappear_or_be_replaced_after_pinning(self):
        observer = self.observer()
        directory = Path(observer['path'])
        self.count(observer=observer)
        self.assertIsNotNone(observer['identity'])
        directory.rename(self.root/'saved-observer')
        with self.assertRaises(FileNotFoundError):
            self.count(observer=observer)
        directory.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'Observer directory identity changed'):
            self.count(observer=observer)

    def test_observer_temporary_symlink_other_io_and_directory_named_tmp_are_strict(self):
        observer = self.observer()
        directory = Path(observer['path'])
        victim = directory / 'status.json.tmp'
        victim.symlink_to(self.root/'science.pt')
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            self.count(observer=observer)
        victim.unlink()
        victim.write_bytes(b'temporary')
        real_stat = os.stat
        def denied(path, *args, **kwargs):
            if path == victim.name and kwargs.get('dir_fd') is not None:
                raise PermissionError(errno.EACCES, 'private JSON unreadable')
            return real_stat(path, *args, **kwargs)
        with patch.object(parent.os, 'stat', side_effect=denied):
            with self.assertRaises(PermissionError):
                self.count(observer=observer)
        victim.unlink()
        victim.mkdir()
        real_open = os.open
        def lost_directory(path, *args, **kwargs):
            if path == victim.name and kwargs.get('dir_fd') is not None:
                raise FileNotFoundError(errno.ENOENT, 'directory is not an allowed regular temporary')
            return real_open(path, *args, **kwargs)
        with patch.object(parent.os, 'open', side_effect=lost_directory):
            with self.assertRaises(FileNotFoundError):
                self.count(observer=observer)
        self.assertEqual(observer['ignored_temp_enoent'], 0)

    def test_exact_observer_status_temporary_reuse_allows_regular_replacement_only(self):
        observer = self.observer()
        directory = Path(observer['path'])
        real_stat = os.stat
        for name in ('status.json.tmp', 'context.json.tmp', 'attempt-01.json.tmp'):
            victim = directory / name
            victim.write_bytes(b'old temporary')
            fired = []
            def raced(path, *args, **kwargs):
                info = real_stat(path, *args, **kwargs)
                if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                    fired.append(True)
                    replacement = directory / 'test-owned-replacement'
                    replacement.write_bytes(b'larger replacement temporary')
                    os.replace(replacement, victim)
                return info
            with self.subTest(name=name), patch.object(parent.os, 'stat', side_effect=raced):
                if name == 'status.json.tmp':
                    self.assertEqual(self.count(observer=observer),
                                     len(b'scientific!') + len(b'cached!') + len(b'larger replacement temporary'))
                else:
                    with self.assertRaisesRegex(RuntimeError, 'entry replaced'):
                        self.count(observer=observer)
            victim.unlink()
        self.assertEqual(observer['status_tmp_replacements'], 1)

    def test_observer_directory_may_be_not_created_but_is_pinned_on_first_appearance(self):
        directory = self.root / 'on/ce-executed-trace-cuda-validation'
        observer = dict(path=str(directory), identity=None)
        self.assertEqual(self.count(observer=observer), len(b'scientific!') + len(b'cached!'))
        self.assertIsNone(observer['identity'])
        directory.mkdir(parents=True)
        self.count(observer=observer)
        self.assertEqual(observer['identity'], parent.storage_directory_identity(directory))

    def test_second_pinned_native_compiler_cache_allows_only_its_own_temporary_loss(self):
        native = self.root / 'private/Robotron/Scripts/dqn/__pycache__'
        native.mkdir(parents=True)
        identity = parent.storage_directory_identity(native)
        victim = native / 'sumtree-build-private.so'
        victim.write_bytes(b'compiled bytes')
        real_stat = os.stat
        fired = []
        def raced(path, *args, **kwargs):
            if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                fired.append(True)
                victim.unlink()
            return real_stat(path, *args, **kwargs)
        with patch.object(parent.os, 'stat', side_effect=raced):
            self.assertEqual(self.count(extra_caches=((native, identity),)), len(b'scientific!') + len(b'cached!'))
        self.assertEqual(self.events['last_cache_root'], str(native))
        native.rename(native.with_name('saved-cache'))
        native.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'boundary changed'):
            self.count(extra_caches=((native, identity),))

    def test_second_native_cache_atomic_shared_library_publication_counts_bytes(self):
        native = self.root / 'private/Robotron/Scripts/dqn/__pycache__'
        native.mkdir(parents=True)
        identity = parent.storage_directory_identity(native)
        victim = native / 'sumtree-private.so'
        victim.write_bytes(b'old native')
        real_stat = os.stat
        fired = []
        def raced(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if path == victim.name and kwargs.get('dir_fd') is not None and not fired:
                fired.append(True)
                temporary = native / 'sumtree-build-private.so'
                temporary.write_bytes(b'new shared library')
                os.replace(temporary, victim)
            return info
        with patch.object(parent.os, 'stat', side_effect=raced):
            self.assertEqual(self.count(extra_caches=((native, identity),)),
                             len(b'scientific!') + len(b'cached!') + len(b'new shared library'))
        self.assertEqual(self.events['regular_cache_replacements'], 1)
        self.assertEqual(self.events['last_cache_root'], str(native))


if __name__ == '__main__':
    unittest.main(verbosity=2)
