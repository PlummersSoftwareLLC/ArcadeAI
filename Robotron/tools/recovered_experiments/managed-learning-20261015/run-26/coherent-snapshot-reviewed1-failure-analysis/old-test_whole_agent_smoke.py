"""CPU/stdlib launcher contracts. No live child, GPU query, signal or cgroup write."""
from contextlib import ExitStack, contextmanager, nullcontext
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from . import whole_agent_smoke as smoke


def process_identity(pid=123, ticks='100'):
    return dict(pid=pid, start_ticks=ticks, ppid=1, pgid=pid)


class WholeAgentSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root/'Robotron'
        (self.game/'logs').mkdir(parents=True)
        self.output = self.game/'logs'/'private-smoke'

    def test_default_cli_is_read_only_dry_run_without_live_queries(self):
        with patch.object(smoke, 'GAME', self.game), \
                patch.object(smoke, 'source_manifest', return_value={'fixture': {}}), \
                patch.object(smoke, 'guard_live_resources', side_effect=AssertionError('live guard')), \
                patch.object(smoke.subprocess, 'Popen', side_effect=AssertionError('spawn')), \
                patch.object(smoke, 'launch', side_effect=AssertionError('launch')), \
                patch('sys.stdout', new_callable=io.StringIO) as stdout:
            before = set(smoke.sys.modules)
            self.assertEqual(smoke.main(['--directory', str(self.output)]), 0)
            plan = json.loads(stdout.getvalue())
        self.assertEqual(plan['status'], 'DRY_RUN_ONLY')
        self.assertFalse(plan['launch'])
        self.assertFalse(self.output.exists())
        self.assertFalse({'numpy', 'torch', 'dqn'} & (set(smoke.sys.modules)-before))

    def test_cli_requires_explicit_launch_switch(self):
        with patch.object(smoke, 'launch', return_value={'status': 'MOCK'}) as launch, \
                patch.object(smoke, 'describe_plan', side_effect=AssertionError('dry')), \
                patch('sys.stdout', new_callable=io.StringIO):
            smoke.main(['--directory', str(self.output), '--launch'])
        launch.assert_called_once_with(self.output)

    def test_output_rejects_existing_relative_outside_missing_parent_and_symlink(self):
        existing = self.game/'logs'/'existing'
        existing.mkdir()
        link = self.game/'logs'/'link'
        link.symlink_to(existing, target_is_directory=True)
        invalid = [Path('relative'), existing, self.root/'outside',
                   self.output/'missing', link/'new']
        for value in invalid:
            with self.subTest(path=value), self.assertRaises(ValueError):
                smoke.validate_output(value, logs_root=self.game/'logs')
        self.assertEqual(smoke.validate_output(self.output, logs_root=self.game/'logs'), self.output)

    def test_private_phase_paths_and_environment_exclude_inherited_controls(self):
        layout = smoke.Layout(self.output, 'nonce', self.root/'tmpfs')
        inherited = {'PATH': '/bin', 'HOME': '/private-home', 'CUDA_VISIBLE_DEVICES': 'wrong',
                     'LD_PRELOAD': '/bad.so', 'PYTHONPATH': '/production',
                     'DQN_BATCH_SIZE': '4096', 'ROBOTRON_OTHER': '/production'}
        with patch.dict(os.environ, inherited, clear=True):
            env = smoke.configure_environment(layout, 'restore')
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'], smoke.GPU0_UUID)
        self.assertEqual(env['DQN_BATCH_SIZE'], '8')
        self.assertEqual(env['DQN_LEARNING_EXPOSURE_COUNTERS'], '1')
        self.assertEqual(env['ROBOTRON_TRAIN_GPU'], '0')
        self.assertEqual(env['ROBOTRON_DQN_MODEL_DIR'], str(layout.phase('restore')['models']))
        self.assertNotIn('PYTHONPATH', env)
        self.assertNotIn('LD_PRELOAD', env)
        self.assertNotIn('ROBOTRON_OTHER', env)
        for key in ('TMPDIR', 'CUDA_CACHE_PATH', 'TORCH_HOME', 'TRITON_CACHE_DIR'):
            self.assertTrue(Path(env[key]).is_relative_to(self.output/'restore'/'cache'))
        self.assertNotEqual(layout.phase('capture')['tmpfs'], layout.phase('restore')['tmpfs'])
        with self.assertRaises(ValueError):
            layout.phase('other')

    def test_source_manifest_rejects_patch_base_and_candidate_drift(self):
        here = self.root/'proposal'
        source = self.game/'Scripts/dqn'
        source.mkdir(parents=True)
        here.mkdir()
        base = source/'fixture.py'
        base.write_text('BASE = 1\n')
        staged = here/'staged/Robotron/Scripts/dqn/fixture.py'
        staged.parent.mkdir(parents=True)
        staged.write_text('BASE = 2\n')
        proposal_patch = here/'coherent-snapshot.patch'
        proposal_patch.write_text('test patch')
        relative = 'Robotron/Scripts/dqn/fixture.py'
        metadata = {'source_files': {relative: {'base_sha256': smoke.digest(base),
                                               'proposed_sha256': smoke.digest(staged)}}}
        (here/'proposal-manifest.json').write_text(json.dumps(metadata))
        with patch.object(smoke, 'HERE', here), patch.object(smoke, 'GAME', self.game), \
                patch.object(smoke, 'REPO', self.root), \
                patch.object(smoke, 'PATCH_SHA256', smoke.digest(proposal_patch)):
            self.assertEqual(smoke.source_manifest()['fixture.py']['source'], str(staged))
            for target in (base, staged, proposal_patch):
                original = target.read_bytes()
                target.write_bytes(original+b'drift')
                with self.subTest(target=target), self.assertRaises(RuntimeError):
                    smoke.source_manifest()
                target.write_bytes(original)

    def test_private_source_copy_rechecks_hash_and_rejects_symlink(self):
        source = self.root/'source.py'
        source.write_text('VALUE = 1\n')
        layout = smoke.Layout(self.output, 'nonce', self.root/'tmpfs')
        record = {'source': str(source), 'sha256': smoke.digest(source)}
        source.write_text('VALUE = 2\n')
        with self.assertRaisesRegex(RuntimeError, 'Source changed'):
            smoke.prepare_private_sources(layout, {'source.py': record})
        record['sha256'] = smoke.digest(source)
        other = smoke.Layout(self.game/'logs'/'second', 'nonce2', self.root/'tmpfs')
        smoke.prepare_private_sources(other, {'source.py': record})
        smoke.verify_source_copies(other, {'source.py': record})
        target = other.scripts/'dqn/source.py'
        self.assertEqual(target.stat().st_mode & 0o222, 0)
        alias = self.root/'alias.py'
        alias.symlink_to(source)
        with self.assertRaises(ValueError):
            smoke.regular(alias)

    def test_quality_scanner_covers_affinity_benchmarks_and_allowed_pids(self):
        proc = self.root/'proc'
        proc.mkdir()
        names = ['run_quality_campaign.py', 'inference_worker_affinity.py',
                 'cpu_affinity_pilot.py', 'benchmark_fixture.py', 'dqn.frozen_main', 'ordinary.py']
        for pid, name in enumerate(names, 100):
            directory = proc/str(pid)
            directory.mkdir()
            (directory/'cmdline').write_bytes(('python\0'+name+'\0').encode())
            fields = ['S', '1', str(pid)]+['0']*17
            fields[19] = '1234'
            (directory/'stat').write_text(str(pid)+' (test) '+' '.join(fields))
        blocked = smoke.scan_quality_processes(proc_root=proc, allowed_pids={100})
        self.assertEqual({item['identity']['pid'] for item in blocked}, {101,102,103,104})

    def test_listening_port_9999_in_ipv4_and_ipv6(self):
        proc = self.root/'net'
        proc.mkdir()
        for family in ('tcp', 'tcp6'):
            for filename in ('tcp', 'tcp6'):
                (proc/filename).write_text('header\n')
            (proc/family).write_text('header\n 0: 0000:270F 0000:0000 0A extra\n')
            self.assertTrue(smoke.listening_9999(proc_net=proc))
            (proc/family).write_text('header\n 0: 0000:270F 0000:0000 01 extra\n')
            self.assertFalse(smoke.listening_9999(proc_net=proc))

    def test_gpu_owner_parser_and_malformed_rows(self):
        value = smoke.parse_compute_apps('123, '+smoke.GPU0_UUID+', 4096\n124, '+smoke.MAIN_GPU_UUID+', N/A\n')
        self.assertEqual(value[0]['bytes'], 4096*smoke.MIB)
        self.assertIsNone(value[1]['bytes'])
        for line in ('pid, GPU-bad, 2', '123, bad, 2', '123, GPU-bad', '123, GPU-bad, unknown'):
            with self.subTest(line=line), self.assertRaises((RuntimeError, ValueError)):
                smoke.parse_compute_apps(line)

    def gpu_guard(self, apps=None, **kwargs):
        value = {'devices': {smoke.GPU0_UUID: {'free_bytes': 16*smoke.GIB},
                             smoke.MAIN_GPU_UUID: {'free_bytes': 16*smoke.GIB}},
                 'apps': [{'pid': 20, 'gpu_uuid': smoke.MAIN_GPU_UUID, 'bytes': 3*smoke.GIB}]
                 if apps is None else apps}
        return smoke.guard_live_resources(query=lambda: value, proc_scan=lambda **kw: [],
                                         port_check=lambda: False, **kwargs)

    def test_gpu_guard_binds_main_start_tick_and_display_owner_budget(self):
        with patch.object(smoke, 'identity', side_effect=lambda pid: process_identity(pid)):
            baseline = self.gpu_guard(initial=True)
            self.assertEqual(baseline['main_owners'], [process_identity(20)])
            self.gpu_guard(expected_main=[process_identity(20)])
            with self.assertRaisesRegex(RuntimeError, 'identity changed'):
                self.gpu_guard(expected_main=[process_identity(20, 'old')])
            with self.assertRaisesRegex(RuntimeError, 'exactly one'):
                self.gpu_guard(apps=[])
            for pid, used, message in ((21, 1, 'another compute owner'),
                                        (22, 12*smoke.GIB, 'memory budget')):
                apps = baseline['gpu']['apps']+[{'pid': pid, 'gpu_uuid': smoke.GPU0_UUID, 'bytes': used}]
                with self.subTest(pid=pid), self.assertRaisesRegex(RuntimeError, message):
                    self.gpu_guard(apps=apps, allowed_pids={22})

    def test_quality_and_port_guards_fail_before_gpu_query(self):
        query = Mock(side_effect=AssertionError('NVIDIA query should not run'))
        for blockers, port in (([{'pid': 1}], False), ([], True)):
            with self.subTest(blockers=blockers, port=port), self.assertRaises(RuntimeError):
                smoke.guard_live_resources(query=query, proc_scan=lambda **kw: blockers,
                                           port_check=lambda: port)
        query.assert_not_called()

    def test_worker_command_isolated_and_invalid_phase_rejected(self):
        command = smoke.worker_command(self.output/'manifest.json', 'capture')
        self.assertEqual(command[1:3], ['-I', '-B'])
        self.assertEqual(command[-2:], ['--phase', 'capture'])
        with self.assertRaises(ValueError):
            smoke.worker_command('manifest', 'other')

    def test_owned_termination_refuses_reused_pid_before_any_signal(self):
        process = Mock(pid=123)
        group = Mock()
        with patch.object(smoke, 'identity', return_value=process_identity(123, 'new')), \
                patch.object(smoke.os, 'killpg') as kill:
            with self.assertRaisesRegex(RuntimeError, 'identity changed'):
                smoke.terminate_owned(process, process_identity(123, 'old'), group)
        kill.assert_not_called()
        group.members.assert_not_called()

    def test_owned_termination_signals_only_matching_group_then_reaps(self):
        process = Mock(pid=123)
        group = Mock()
        group.members.return_value = []
        owned = process_identity()
        with patch.object(smoke, 'identity', return_value=owned), patch.object(smoke.os, 'killpg') as kill:
            smoke.terminate_owned(process, owned, group)
        kill.assert_called_once_with(123, signal.SIGTERM)
        self.assertEqual(process.wait.call_count, 2)

    def test_owned_termination_refuses_foreign_descendant_before_cgroup_kill(self):
        process = Mock(pid=123)
        process.wait.side_effect = [subprocess.TimeoutExpired('child', 5), None]
        group = Mock(path=self.root)
        group.members.return_value = [124]
        (self.root/'cgroup.kill').write_text('untouched')
        with patch.object(smoke, 'identity', side_effect=[process_identity(), dict(process_identity(124), pgid=999)]), \
                patch.object(smoke.os, 'killpg'):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected process'):
                smoke.terminate_owned(process, process_identity(), group)
        self.assertEqual((self.root/'cgroup.kill').read_text(), 'untouched')

    def phase_fixture(self):
        layout = smoke.Layout(self.output, 'phase', self.root/'tmpfs')
        paths = layout.phase('capture')
        paths['root'].mkdir(parents=True)
        manifest = self.output/'manifest.json'
        manifest.write_text(json.dumps({'launch_token': 'secret'}))
        process = Mock(pid=123, stdin=io.BytesIO(), returncode=None)
        process.poll.return_value = None
        group = Mock()
        group.members.return_value = []
        return layout, manifest, process, group

    def test_phase_interruption_drains_owned_child_and_closes_stdin(self):
        layout, manifest, process, group = self.phase_fixture()
        events = []
        @contextmanager
        def blocked():
            events.append('block')
            try: yield
            finally: events.append('unblock')
        with patch.object(smoke.subprocess, 'Popen', return_value=process), \
                patch.object(smoke, 'identity', return_value=process_identity()), \
                patch.object(smoke, 'guard_live_resources', side_effect=smoke.SmokeInterrupted('SIGTERM')), \
                patch.object(smoke, 'blocked_handled_signals', blocked), \
                patch.object(smoke, 'terminate_owned', side_effect=lambda *a, **k: events.append('drain')) as terminate:
            with self.assertRaises(smoke.SmokeInterrupted):
                smoke.run_phase(layout, manifest, 'capture', group, [], 999999999.)
        terminate.assert_called_once_with(process, process_identity(), group)
        self.assertTrue(process.stdin.closed)
        drain = events.index('drain')
        self.assertEqual(events[drain-1:drain+2], ['block', 'drain', 'unblock'])

    def test_identity_acquisition_failure_closes_token_and_reaps_exact_popen_child(self):
        layout, manifest, process, group = self.phase_fixture()
        with patch.object(smoke.subprocess, 'Popen', return_value=process), \
                patch.object(smoke, 'identity', side_effect=FileNotFoundError('stat unavailable')), \
                patch.object(smoke, 'blocked_handled_signals', nullcontext), \
                patch.object(smoke, 'guard_live_resources') as guard, \
                patch.object(smoke, 'terminate_owned') as terminate, \
                patch.object(smoke.os, 'killpg') as kill:
            with self.assertRaises(FileNotFoundError):
                smoke.run_phase(layout, manifest, 'capture', group, [], 999999999.)
        self.assertTrue(process.stdin.closed)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)
        guard.assert_not_called()
        group.attach.assert_not_called()
        terminate.assert_not_called()
        kill.assert_not_called()

    def test_pending_term_during_phase_cleanup_waits_for_drain_and_pipe_close(self):
        layout, manifest, process, group = self.phase_fixture()
        process.drained = False
        blocks = []
        @contextmanager
        def blocked():
            blocks.append('enter')
            try: yield
            finally:
                if len(blocks) == 2:
                    self.assertTrue(process.stdin.closed)
                    self.assertTrue(process.drained)
                    raise smoke.SmokeInterrupted('pending SIGTERM')
        def terminate(*args):
            process.drained = True
        with patch.object(smoke.subprocess, 'Popen', return_value=process), \
                patch.object(smoke, 'identity', return_value=process_identity()), \
                patch.object(smoke, 'guard_live_resources', side_effect=RuntimeError('watch failed')), \
                patch.object(smoke, 'blocked_handled_signals', blocked), \
                patch.object(smoke, 'terminate_owned', side_effect=terminate) as terminate_mock:
            with self.assertRaises(smoke.SmokeInterrupted):
                smoke.run_phase(layout, manifest, 'capture', group, [], 999999999.)
        terminate_mock.assert_called_once()

    def test_signal_handlers_raise_and_restore_prior_handlers(self):
        registered = {}
        previous = {number: object() for number in smoke.HANDLED_SIGNALS}
        with patch.object(smoke.signal, 'getsignal', side_effect=lambda number: previous[number]), \
                patch.object(smoke.signal, 'signal', side_effect=lambda number, handler: registered.__setitem__(number, handler)):
            with smoke.installed_signal_handlers():
                for number in smoke.HANDLED_SIGNALS:
                    with self.subTest(signal=number), self.assertRaises(smoke.SmokeInterrupted):
                        registered[number](number, None)
            self.assertEqual(registered, previous)

    def test_pending_signal_delivered_only_after_protected_cleanup(self):
        events = []
        old = {signal.SIGUSR1}
        def mask(action, values):
            if action == signal.SIG_BLOCK:
                events.append('blocked')
                return old
            self.assertEqual(action, signal.SIG_SETMASK)
            self.assertEqual(values, old)
            self.assertEqual(events[-1], 'owned cleanup complete')
            raise smoke.SmokeInterrupted('pending SIGTERM')
        with patch.object(smoke.signal, 'pthread_sigmask', side_effect=mask):
            with self.assertRaises(smoke.SmokeInterrupted):
                with smoke.blocked_handled_signals():
                    events.append('owned cleanup complete')

    @contextmanager
    def mocked_launch(self, *, phase_error=None, close_error=None):
        """All writable paths are tempfile-owned; all live operations are mocks."""
        tmpfs = self.root/'tmpfs'
        tmpfs.mkdir()
        layout = smoke.Layout(self.output, 'fixed', tmpfs)
        source = self.root/'fixture.py'
        source.write_text('fixture = True\n')
        files = {'fixture.py': {'source': str(source), 'sha256': smoke.digest(source)}}
        group = Mock(path=self.root/'fake-cgroup', identity={'device': 1, 'inode': 2})
        group.members.return_value = []
        if close_error is not None: group.close.side_effect = close_error
        phases = []
        def phase(*args):
            phases.append(args[2])
            if phase_error is not None: raise phase_error
            return {'status': 'PASS', 'archive': str(layout.phase('capture')['models']/'coherent-snapshots/archive')}
        original_open = os.open
        opened = []
        def open_private_lease(path, flags, mode=0o777, *, dir_fd=None):
            if Path(path) == Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock'):
                fd = original_open(self.root/'private-lease', flags, mode)
                opened.append(fd)
                return fd
            return original_open(path, flags, mode, dir_fd=dir_fd)
        with ExitStack() as stack:
            for name, value in [('GAME', self.game), ('Layout', lambda *a, **kw: layout),
                ('source_manifest', lambda: files), ('guard_live_resources', lambda **kw: {'main_owners': [process_identity(20)]}),
                ('cgroup_parent', lambda: self.root), ('OwnedCgroup', lambda *a: group),
                ('run_phase', phase), ('prepare_restore', Mock()), ('verify_source_copies', Mock()),
                ('identity', lambda *a: process_identity()), ('blocked_handled_signals', nullcontext)]:
                stack.enter_context(patch.object(smoke, name, value))
            stack.enter_context(patch.object(smoke.shutil, 'disk_usage', return_value=Mock(free=32*smoke.GIB)))
            stack.enter_context(patch.object(smoke.os, 'open', side_effect=open_private_lease))
            stack.enter_context(patch.object(smoke.fcntl, 'flock'))
            yield layout, group, phases, opened

    def test_mocked_launch_capture_then_fresh_restore_publishes_after_cleanup(self):
        with self.mocked_launch() as (layout, group, phases, opened):
            result = smoke._launch_guarded(self.output)
            self.assertEqual(phases, ['capture', 'restore'])
            self.assertEqual(result['status'], 'PASS')
            self.assertFalse(layout.tmpfs.exists())
            group.close.assert_called_once()
            self.assertEqual(json.loads((self.output/'result.json').read_text())['status'], 'PASS')
            for descriptor in opened:
                with self.assertRaises(OSError): os.fstat(descriptor)

    def test_mocked_launch_interruption_cleans_owned_resources_without_success(self):
        with self.mocked_launch(phase_error=smoke.SmokeInterrupted('SIGTERM')) as (layout, group, phases, opened):
            with patch.object(smoke, 'installed_signal_handlers', nullcontext):
                with self.assertRaises(smoke.SmokeInterrupted): smoke.launch(self.output)
            self.assertFalse(layout.tmpfs.exists())
            group.close.assert_called_once()
            self.assertTrue((self.output/'interrupted.json').is_file())
            self.assertFalse((self.output/'result.json').exists())

    def test_cleanup_failure_retains_tmpfs_and_records_recovery_without_success(self):
        with self.mocked_launch(close_error=RuntimeError('still populated')) as (layout, group, phases, opened):
            with self.assertRaisesRegex(RuntimeError, 'cleanup needs recovery'):
                smoke._launch_guarded(self.output)
            self.assertTrue(layout.tmpfs.exists())
            record = json.loads((self.output/'cleanup-failure.json').read_text())
            self.assertTrue(record['recovery_required'])
            self.assertFalse((self.output/'result.json').exists())
            for descriptor in opened:
                with self.assertRaises(OSError): os.fstat(descriptor)

    def test_missing_cgroup_delegation_fails_before_private_allocation(self):
        with self.mocked_launch() as (layout, group, phases, opened):
            with patch.object(smoke, 'cgroup_parent', side_effect=RuntimeError('no delegation')):
                with self.assertRaisesRegex(RuntimeError, 'no delegation'):
                    smoke._launch_guarded(self.output)
            self.assertFalse(self.output.exists())
            self.assertFalse(layout.tmpfs.exists())
            self.assertEqual(phases, [])
            self.assertEqual(opened, [])

    def test_pending_term_during_launch_cleanup_suppresses_aggregate_success(self):
        with self.mocked_launch() as (layout, group, phases, opened):
            @contextmanager
            def pending_during_cleanup():
                try: yield
                finally:
                    group.close.assert_called_once()
                    self.assertFalse(layout.tmpfs.exists())
                    for descriptor in opened:
                        with self.assertRaises(OSError): os.fstat(descriptor)
                    raise smoke.SmokeInterrupted('pending SIGTERM after owned cleanup')
            with patch.object(smoke, 'blocked_handled_signals', pending_during_cleanup), \
                    patch.object(smoke, 'installed_signal_handlers', nullcontext):
                with self.assertRaises(smoke.SmokeInterrupted): smoke.launch(self.output)
            self.assertFalse((self.output/'result.json').exists())
            self.assertTrue((self.output/'interrupted.json').exists())


if __name__ == '__main__':
    unittest.main()
