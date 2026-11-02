"""CPU-only isolation tests. No CUDA context, emulator, socket listener or replay files."""
import contextlib
from dataclasses import replace
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from Robotron.tools import run_frozen_sidecar as sidecar


class FakeProcess:
    def __init__(self, pid):
        self.pid, self.returncode = pid, None
        self.terminated, self.killed = False, False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


class SidecarIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boot_temp = tempfile.TemporaryDirectory()
        seed = Path(cls.boot_temp.name)
        (seed/'source.nvram').write_bytes(bytes([0xf0])*1024)
        (seed/'source.cfg').write_text('<mameconfig version="10"><system name="robotron" /></mameconfig>')
        (seed/'source.ini').write_text('pluginspath /usr/share/games/mame/plugins\n')
        cls.boot_assets = seed/'snapshot'
        with patch.object(sidecar.boot_module(), '_scan_writable_sources', return_value=dict(
                checked_processes=0, active_writers=0, policy='Runner fixture')):
            sidecar.boot_module().capture_snapshot(cls.boot_assets,
                nvram_source=seed/'source.nvram', cfg_source=seed/'source.cfg', ini_source=seed/'source.ini')

    @classmethod
    def tearDownClass(cls):
        for directory in [cls.boot_assets, *cls.boot_assets.rglob('*')]:
            if directory.is_dir():
                directory.chmod(0o755)
        cls.boot_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkpoint = self.root / 'immutable.pt'
        self.checkpoint.write_bytes(b'immutable checkpoint fixture')
        self.job = sidecar.Job(self.checkpoint, self.root / 'job', 'gpu0-baseline',
                               'cpu', mame=Path('/bin/true'), rompath=self.root,
                               boot_assets=self.boot_assets)

    def test_plan_is_read_only_and_does_not_import_training(self):
        command = [sys.executable, str(Path(sidecar.__file__)), '--checkpoint', str(self.checkpoint),
                   '--job-dir', str(self.job.directory), '--label', self.job.label,
                   '--device', 'cpu', '--mame', '/bin/true', '--rompath', str(self.root)]
        command.extend(['--boot-assets', str(self.boot_assets)])
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        plan = json.loads(result.stdout)
        self.assertFalse(self.job.directory.exists())
        self.assertEqual(plan['actor_slots'], list(range(4096, 4112)))
        self.assertEqual(plan['actors'], 16)
        self.assertEqual(plan['port'], 9999)
        self.assertFalse(plan['replay_enabled'])
        self.assertFalse(plan['fp16'])
        self.assertEqual(plan['inference_backend'], 'eager')

    def test_long_fixed_admission_and_tails_remain_bounded(self):
        replace(self.job, cohort_s=3600, timeout_s=6000).validate()
        replace(self.job, cohort_s=3600, timeout_s=9000).validate()
        for admission, timeout in ((3600,9001),(6000,6000),(float('nan'),6000),(3600,float('inf'))):
            with self.subTest(admission=admission, timeout=timeout), self.assertRaises(ValueError):
                replace(self.job, cohort_s=admission, timeout_s=timeout).validate()

    def test_compile_backend_is_explicit_cuda_only_and_plan_does_not_start_cuda(self):
        with self.assertRaisesRegex(ValueError, 'requires CUDA'):
            replace(self.job, inference_backend='inductor').validate()
        command = [sys.executable, str(Path(sidecar.__file__)), '--checkpoint', str(self.checkpoint),
                   '--job-dir', str(self.job.directory), '--label', self.job.label,
                   '--device', 'cuda', '--gpu-uuid', 'GPU-test-explicit-device',
                   '--inference-backend', 'inductor', '--mame', '/bin/true',
                   '--rompath', str(self.root), '--boot-assets', str(self.boot_assets)]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout)['inference_backend'], 'inductor')
        self.assertFalse(self.job.directory.exists())

    def test_backend_constructor_must_finish_or_raise_before_actor_is_returned(self):
        job = replace(self.job, device='cuda', inference_backend='inductor')
        factory = Mock(side_effect=RuntimeError('strict compile warmup failed'))
        with self.assertRaisesRegex(RuntimeError, 'strict compile warmup failed'):
            sidecar.build_inference_actor(factory, self.checkpoint, job)
        factory.assert_called_once_with(self.checkpoint, device='cuda', inference_backend='inductor')
        factory = Mock(return_value=SimpleNamespace(inference_backend='eager',
                                                   numeric_policy=dict(compiled=False)))
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            sidecar.build_inference_actor(factory, self.checkpoint, job)

    def test_reject_production_port_output_and_reused_journal(self):
        for job in (replace(self.job, port=9998),
                    replace(self.job, directory=sidecar.GAME / 'models_dqn' / 'sidecar'),
                    replace(self.job, directory=Path('/dev/shm/private-sidecar')),
                    replace(self.job, device='cuda', gpu_uuid='0'),
                    replace(self.job, cohort_s=float('nan'))):
            with self.subTest(job=job), self.assertRaises(ValueError):
                job.validate()
        self.job.directory.mkdir()
        with self.assertRaises(ValueError):
            self.job.validate()

    def test_missing_initialized_boot_assets_blocks_run_before_torch_or_processes(self):
        missing = replace(self.job, boot_assets=None)
        with patch.object(sidecar, 'configure_environment') as configure, \
                self.assertRaisesRegex(ValueError, 'boot-assets'):
            sidecar.run(missing)
        configure.assert_not_called()
        self.assertFalse(self.job.directory.exists())

    def test_checkpoint_copy_is_independent_and_read_only(self):
        self.job.directory.mkdir()
        copied, digest = sidecar.copy_checkpoint(self.job)
        self.assertEqual(digest, sidecar.sha256(self.checkpoint))
        self.assertNotEqual(copied.stat().st_ino, self.checkpoint.stat().st_ino)
        self.assertEqual(copied.stat().st_mode & 0o222, 0)
        self.checkpoint.write_bytes(b'different source')
        self.assertEqual(copied.read_bytes(), b'immutable checkpoint fixture')

    def test_environment_is_isolated_before_any_training_import(self):
        script = '''
import json, os, sys
from pathlib import Path
from Robotron.tools.run_frozen_sidecar import Job, configure_environment
job=Job(Path(sys.argv[1]), Path(sys.argv[2]), 'test', 'cpu')
configure_environment(job)
assert 'torch' not in sys.modules
assert 'dqn.config' not in sys.modules
print(json.dumps({key:os.environ.get(key) for key in (
'ROBOTRON_DQN_MODEL_DIR','ROBOTRON_DQN_CONTROL_PATH','ROBOTRON_RUN_DIR',
'CUDA_VISIBLE_DEVICES','LD_PRELOAD','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS',
'TORCHINDUCTOR_COMPILE_THREADS','TORCHINDUCTOR_CACHE_DIR','TRITON_CACHE_DIR',
'TORCH_EXTENSIONS_DIR')}))
'''
        env = dict(os.environ, ROBOTRON_RUN_DIR='/production/log',
                   ROBOTRON_DQN_MODEL_DIR='/production/model',
                   ROBOTRON_DQN_CONTROL_PATH='/production/control', CUDA_VISIBLE_DEVICES='1')
        env.pop('LD_PRELOAD', None)
        result = subprocess.run([sys.executable, '-c', script, str(self.checkpoint),
                                 str(self.job.directory)], env=env, capture_output=True,
                                text=True, check=True)
        values = json.loads(result.stdout)
        for key in ('ROBOTRON_DQN_MODEL_DIR', 'ROBOTRON_DQN_CONTROL_PATH', 'ROBOTRON_RUN_DIR'):
            self.assertTrue(Path(values[key]).is_relative_to(self.job.directory))
        self.assertEqual(values['CUDA_VISIBLE_DEVICES'], '')
        self.assertIsNone(values['LD_PRELOAD'])
        self.assertEqual(values['OPENBLAS_NUM_THREADS'], '2')
        self.assertEqual(values['TORCHINDUCTOR_COMPILE_THREADS'], '2')
        for key in ('TORCHINDUCTOR_CACHE_DIR', 'TRITON_CACHE_DIR', 'TORCH_EXTENSIONS_DIR'):
            self.assertTrue(Path(values[key]).is_relative_to(self.job.directory))

    def test_private_fleet_owns_only_its_handles_and_private_paths(self):
        calls = []
        def popen(command, **kwargs):
            process = FakeProcess(20000 + len(calls))
            calls.append((command, kwargs, process))
            return process
        fleet = sidecar.PrivateFleet(self.job, Path('/tmp/test-shim.so'), popen=popen)
        with patch.dict(os.environ, {'LD_PRELOAD': '/production/shim.so',
                                     'ROBOTRON_SOCKET_WAIT_ACTIVE': 'stale'}):
            fleet.launch()
            self.assertEqual(len(fleet.processes), 16)
            for slot, (command, kwargs, process) in zip(sidecar.SLOTS, calls):
                self.assertEqual(command[:2], ['/bin/true', 'robotron'])
                self.assertNotIn('startmame.sh', ' '.join(command))
                self.assertTrue(kwargs['cwd'].is_relative_to(self.job.directory))
                self.assertTrue(kwargs['start_new_session'])
                self.assertTrue(kwargs['close_fds'])
                self.assertEqual(kwargs['env']['ROBOTRON_SOCKET_ADDRESS'], '127.0.0.1:9999')
                self.assertEqual(kwargs['env']['ROBOTRON_SOCKET_WAIT_PORT'], '9999')
                self.assertEqual(kwargs['env']['ROBOTRON_CLIENT_SLOT'], str(slot))
                self.assertEqual(kwargs['env']['ROBOTRON_EVAL_MODE'], '1')
                self.assertEqual(kwargs['env']['LD_PRELOAD'], '/tmp/test-shim.so')
                self.assertNotIn('ROBOTRON_SOCKET_WAIT_ACTIVE', kwargs['env'])
                for flag in ('-cfg_directory', '-nvram_directory', '-inipath',
                             '-state_directory', '-snapshot_directory', '-diff_directory',
                             '-input_directory', '-share_directory', '-comment_directory'):
                    self.assertTrue(Path(command[command.index(flag)+1]).is_relative_to(kwargs['cwd']))
                restored = kwargs['cwd']/'nvram/robotron/nvram'
                self.assertEqual(restored.read_bytes(), (self.boot_assets/'nvram/robotron/nvram').read_bytes())
                self.assertNotEqual(restored.stat().st_ino, (self.boot_assets/'nvram/robotron/nvram').stat().st_ino)
                self.assertTrue(restored.stat().st_mode & 0o200)
            fleet.stop()
            self.assertEqual(os.environ['LD_PRELOAD'], '/production/shim.so')
        self.assertTrue(all(item[2].terminated for item in calls))
        self.assertTrue(all(item[1]['stdout'].closed for item in calls))

    def test_partial_launch_failure_cleans_owned_processes(self):
        owned = []
        def popen(*args, **kwargs):
            if len(owned) == 3:
                raise OSError('launch failure')
            owned.append(FakeProcess(len(owned)+1))
            return owned[-1]
        fleet = sidecar.PrivateFleet(self.job, Path('/tmp/test-shim.so'), popen=popen)
        with self.assertRaisesRegex(OSError, 'launch failure'):
            fleet.launch()
        self.assertEqual(len(owned), 3)
        self.assertTrue(all(process.terminated for process in owned))
        self.assertEqual(fleet.streams, [])

    def test_actor_restore_identity_must_match_initial_boot_seed_before_spawn(self):
        spawn = Mock()
        fleet = sidecar.PrivateFleet(self.job, Path('/tmp/test-shim.so'), popen=spawn,
                                     expected_boot_identity='0'*64)
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            fleet.launch()
        spawn.assert_not_called()

    def test_backend_evidence_requires_own_pid_and_exact_port_interval(self):
        fleet = sidecar.PrivateFleet(self.job, Path('/tmp/test-shim.so'),
                                     popen=lambda *args, **kwargs: FakeProcess(12345))
        fleet.launch()
        try:
            for slot in sidecar.SLOTS:
                path = self.job.directory/'actors'/str(slot)/'console.log'
                path.write_text('[robotron-socket-wait] pid=12345 fd=8 port=9999 interval_us=1000\n')
            self.assertTrue(all(row['matching_activation'] for row in fleet.backend_evidence().values()))
            path.write_text('[robotron-socket-wait] pid=12345 fd=8 port=9998 interval_us=1000\n')
            self.assertFalse(fleet.backend_evidence()[sidecar.SLOTS[-1]]['matching_activation'])
        finally:
            fleet.stop()

    def test_disabled_wait_removes_inherited_preload_from_mame(self):
        with patch.dict(os.environ, {'LD_PRELOAD': '/unrelated.so'}):
            _, environment, _ = sidecar.mame_spec(replace(self.job, wait_us=0), sidecar.SLOTS[0])
        self.assertNotIn('LD_PRELOAD', environment)
        self.assertEqual(environment['ROBOTRON_SOCKET_WAIT_US'], '0')

    def test_primary_connection_failure_survives_secondary_cleanup_timeout(self):
        result = dict(valid=False, reason='server_or_actor_connection_failed',
                      server_error='Client 0 disconnected: explicit eval required',
                      error='RuntimeError: original failure')
        sidecar.retain_invalidity_reasons(result, ['socket_wait_backend_not_verified',
                                                  'actor_action_receive_timeout'])
        self.assertEqual(result['reason'], 'server_or_actor_connection_failed')
        self.assertEqual(result['error'], 'RuntimeError: original failure')
        self.assertEqual(result['server_error'], 'Client 0 disconnected: explicit eval required')
        self.assertEqual(result['invalidity_reasons'], ['server_or_actor_connection_failed',
                         'socket_wait_backend_not_verified', 'actor_action_receive_timeout'])

    def test_boundary_waits_for_exact_all_sixteen_high_slots(self):
        server = Mock()
        server.inference_only_error = None
        base = dict(ready=True, clients=16, actor_slots=list(sidecar.SLOTS))
        server.measurement_boundary_status.return_value = base
        self.assertTrue(sidecar.fixed_boundary(server, 1)['ready'])
        for bad in (dict(base, clients=1), dict(base, actor_slots=list(range(16))),
                    dict(base, actor_slots=[4096]*16), dict(base, ready=False)):
            server.measurement_boundary_status.return_value = bad
            self.assertFalse(sidecar.fixed_boundary(server, 1)['ready'])
        # A reconnect may restore all live slots between polls. The permanent
        # error latch must still prevent that replacement fleet's admission.
        server.measurement_boundary_status.return_value = base
        server.inference_only_error = 'earlier actor disconnect'
        self.assertFalse(sidecar.fixed_boundary(server, 1)['ready'])

    def test_protocol_guard_rejects_mode_settings_actor_or_checkpoint_drift(self):
        self.job.directory.mkdir()
        checkpoint, _ = sidecar.copy_checkpoint(self.job)
        identity = sidecar.checkpoint_identity(checkpoint)
        settings = dict(start_advanced=False, start_level_min=1, epsilon_pct=0,
                        expert_pct=0, auto_curriculum=False, difficulty=5)
        config = SimpleNamespace(game_settings=SimpleNamespace(snapshot=lambda: dict(settings)),
                                 metrics=SimpleNamespace(measurement_active=True))
        actor = SimpleNamespace(training_enabled=False, memory=None, inference_error=None)
        sidecar.check_protocol(config, actor, identity, checkpoint)
        for name, value in (('difficulty', 4), ('epsilon_pct', 1), ('start_level_min', 2)):
            original, settings[name] = settings[name], value
            with self.assertRaisesRegex(RuntimeError, 'settings'):
                sidecar.check_protocol(config, actor, identity, checkpoint)
            settings[name] = original
        config.metrics.measurement_active = False
        with self.assertRaises(RuntimeError):
            sidecar.check_protocol(config, actor, identity, checkpoint)
        config.metrics.measurement_active = True
        actor.inference_error = 'inference failed'
        with self.assertRaisesRegex(RuntimeError, 'inference failed'):
            sidecar.check_protocol(config, actor, identity, checkpoint)
        actor.inference_error = None
        checkpoint.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'checkpoint'):
            sidecar.check_protocol(config, actor, identity, checkpoint)

    def test_cleanup_attempts_remaining_steps_after_each_failure(self):
        fleet = SimpleNamespace(stop=Mock(side_effect=RuntimeError('fleet failed')))
        server = SimpleNamespace(shutdown_event=threading.Event(), client_lock=threading.Lock(),
                                 clients={}, inference_batcher=None,
                                 stop=Mock(side_effect=RuntimeError('server failed')))
        worker = threading.Thread(target=lambda: None)
        controller = SimpleNamespace(exit=Mock(side_effect=RuntimeError('restore failed')))
        with patch.object(sidecar.signal, 'signal') as restore_signal:
            errors = sidecar.cleanup_job(fleet, server, worker, controller, {2: 'prior'})
        self.assertEqual(len(errors), 3)
        self.assertTrue(server.shutdown_event.is_set())
        server.stop.assert_called_once()
        controller.exit.assert_called_once()
        restore_signal.assert_called_once_with(2, 'prior')

    def test_cleanup_does_not_restore_policy_while_inference_thread_is_live(self):
        batcher = Mock(spec=threading.Thread)
        batcher.is_alive.return_value = True
        fleet = SimpleNamespace(stop=Mock(return_value=[]))
        server = SimpleNamespace(shutdown_event=threading.Event(), client_lock=threading.Lock(),
            clients={}, inference_batcher=SimpleNamespace(_thread=batcher), stop=Mock())
        worker = threading.Thread(target=lambda: None)
        controller = SimpleNamespace(exit=Mock())
        errors = sidecar.cleanup_job(fleet, server, worker, controller, {})
        self.assertTrue(any('still live' in error for error in errors))
        controller.exit.assert_not_called()

    def test_fresh_server_import_has_no_replay_training_or_native_build_dependencies(self):
        script = (
            "import sys\nfrom Robotron.Scripts.dqn import socket_server\n"
            "for name in sys.modules:\n"
            " if name.startswith(('Robotron.Scripts.dqn.', 'dqn.')):\n"
            "  assert name.rsplit('.',1)[-1] not in ('agent','replay_buffer','native_sumtree','training'), name\n")
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
                   ROBOTRON_DQN_MODEL_DIR=str(self.root/'isolated-models'),
                   ROBOTRON_DQN_CONTROL_PATH=str(self.root/'isolated-control'))
        subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, check=True)


class ServerNoReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The test command sets CUDA_VISIBLE_DEVICES='' before this import.
        cls.module = importlib.import_module('Robotron.Scripts.dqn.socket_server')

    def test_inference_only_constructor_never_creates_or_inspects_replay(self):
        class Actor:
            @property
            def memory(self):
                raise AssertionError('replay state must never be inspected')
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {'ROBOTRON_RUN_DIR': directory}), \
                patch.object(self.module, 'AsyncReplayBuffer', side_effect=AssertionError('replay consumer')), \
                patch.object(self.module, 'AsyncInferenceBatcher', return_value=Mock(max_batch_size=16, max_wait_s=.001)):
            server = self.module.SocketServer('127.0.0.1', 9999, Actor(), replay_enabled=False)
            self.assertIsNone(server.async_buffer)
            self.assertIsNotNone(server.game_journal)
            fake_metrics = SimpleNamespace(client_count=0, measurement_active=False,
                                            ratchet_note_eval_start=Mock())
            with patch.object(self.module, 'metrics', fake_metrics):
                server._init_client(0)
                client = server.client_states[0]
                self.assertTrue(client['replay_disabled'])
                self.assertFalse(server._replay_writable(client))

    def test_default_server_still_constructs_replay_consumer(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {'ROBOTRON_RUN_DIR': directory}), \
                patch.object(self.module, 'AsyncReplayBuffer', return_value=Mock()) as replay, \
                patch.object(self.module, 'AsyncInferenceBatcher', return_value=Mock(max_batch_size=16, max_wait_s=.001)):
            actor = SimpleNamespace(memory=SimpleNamespace(max_game_uid=lambda: 42))
            server = self.module.SocketServer('127.0.0.1', 9998, actor)
            replay.assert_called_once_with(actor)
            self.assertEqual(server._game_uid_seq, 42)

    def test_missing_journal_fails_closed(self):
        with patch.object(self.module.GameJournal, 'from_environment', side_effect=OSError('no journal')), \
                patch.object(self.module, 'AsyncInferenceBatcher', return_value=Mock(max_batch_size=16, max_wait_s=.001)):
            with self.assertRaisesRegex(RuntimeError, 'requires a full-game journal'):
                self.module.SocketServer('127.0.0.1', 9999, Mock(), replay_enabled=False)

    def test_inactive_mode_or_invalid_handshake_closes_before_inference(self):
        for active, eval_mode, preview in ((False, 1, 0), (False, 1, 1), (True, 0, 0), (True, 2, 1)):
            with self.subTest(active=active, eval_mode=eval_mode, preview=preview):
                state = SimpleNamespace(client_count=0, measurement_active=active,
                    ratchet_note_eval_start=Mock(), ratchet_note_eval_abandoned=Mock())
                with tempfile.TemporaryDirectory() as directory, \
                        patch.dict(os.environ, {'ROBOTRON_RUN_DIR': directory}), \
                        patch.object(self.module, 'metrics', state), \
                        patch.object(self.module, 'AsyncInferenceBatcher', return_value=Mock(max_batch_size=16, max_wait_s=.001)), \
                        patch.object(self.module.threading, 'Timer'):
                    actor = SimpleNamespace(memory=None, act=Mock())
                    server = self.module.SocketServer('127.0.0.1', 9999, actor, replay_enabled=False)
                    server.running = True
                    server._init_client(0)
                    server.game_journal = None
                    server._recv_exact = Mock(return_value=struct.pack('>H',
                                                eval_mode*16384 + 4096*2 + preview))
                    sock = Mock()
                    server.handle_client(sock, 0)
                    actor.act.assert_not_called()
                    sock.close.assert_called_once()
                    self.assertEqual(server._recv_exact.call_count, 1)
                    self.assertIsNotNone(server.inference_only_error)

    def test_real_headless_eval_capability_handshake_never_requests_preview_or_replay(self):
        from Robotron.Scripts.dqn.test_measurement_actor import fake_metrics
        import numpy as np
        state = fake_metrics()
        # Capability and even a hypothetical viewer cannot enable a stream in
        # the permanently inference-only server.
        state.preview_capture_enabled, state.web_client_count, state.hud_enabled = True, 2, True
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {'ROBOTRON_RUN_DIR': directory}), \
                patch.object(self.module, 'metrics', state), \
                patch.object(self.module, 'AsyncReplayBuffer', side_effect=AssertionError('replay created')), \
                patch.object(self.module, 'AsyncInferenceBatcher', return_value=Mock(max_batch_size=16, max_wait_s=.001)), \
                patch.object(self.module.threading, 'Timer'):
            actor = SimpleNamespace(memory=None, optimized_samples=123, act=Mock(return_value=(0, 0, False)))
            server = self.module.SocketServer('127.0.0.1', 9999, actor, replay_enabled=False)
            server.running, server.game_journal, server.inference_batcher = True, None, None
            server._init_client(0)
            client = server.client_states[0]
            payload = struct.pack('>H', self.module.WIRE_PARAMS_COUNT)
            server._recv_exact = Mock(side_effect=[bytes.fromhex('6001'),
                struct.pack('>I', len(payload)), payload, ConnectionError('test EOF')])
            frame = self.module.FrameData(state=np.zeros(1), subjreward=0, objreward=0, done=False,
                player_alive=True, save_signal=False, start_pressed=False,
                level_number=1, game_score=0, num_lasers=0, lives=3)
            sock = Mock()
            with patch.object(self.module, 'parse_frame_data', return_value=frame), \
                    patch.object(self.module, 'slice_model_state', return_value=np.zeros(2)):
                server.handle_client(sock, 0)
            self.assertTrue(client['preview_capable'])
            self.assertEqual(client['client_slot'], 4096)
            self.assertTrue(client['eval_only'])
            self.assertTrue(server.preview_disabled)
            self.assertIsNone(server.preview_cid)
            self.assertIsNone(server.async_buffer)
            self.assertFalse(server._replay_writable(client))
            actor.act.assert_called_once()
            self.assertEqual(actor.act.call_args.args[1], 0)
            self.assertEqual(sock.sendall.call_count, 1)
            action = sock.sendall.call_args.args[0]
            self.assertEqual(len(action), 6)
            self.assertEqual(action[2] & 0xc0, 0)  # no preview or HUD request bits
            self.assertEqual(action[3:5], bytes([0, 1]))
            self.assertEqual(action[5], 0x85)  # factory difficulty5, unbounded eval
            self.assertIn('test EOF', server.inference_only_error)

    def test_runtime_journal_failure_is_fatal_only_for_inference_only_server(self):
        server = self.module.SocketServer.__new__(self.module.SocketServer)
        server.replay_enabled = False
        server.inference_only_error = None
        server._inference_error_lock = threading.Lock()
        server.game_journal = SimpleNamespace(observe=Mock(side_effect=OSError('disk full')))
        with self.assertRaisesRegex(RuntimeError, 'journal failed'):
            server._journal_observe(0, object(), {}, False)
        self.assertIn('disk full', server.inference_only_error)
        server._fail_inference_only('another failure after reconnect')
        self.assertIn('disk full', server.inference_only_error)


class TimeoutAccountingTests(unittest.TestCase):
    def test_timeout_during_slow_prescan_is_runtime_even_when_output_flushes_late(self):
        server = SimpleNamespace(shutdown_event=threading.Event(), client_lock=threading.Lock(),
                                 clients={}, inference_batcher=None, stop=Mock(return_value=None))
        moment = [100.25]
        def before_shutdown():
            self.assertFalse(server.shutdown_event.is_set())
            moment[0] = 102.25  # A timeout at101 occurs while all logs are scanned.
            return {4096: 0}  # Its output has not flushed yet.
        def cutoff_clock():
            self.assertTrue(server.shutdown_event.is_set())
            return moment[0]
        fleet = SimpleNamespace(timeout_logs=before_shutdown, stop=lambda: [],
            timeout_events=lambda: {4096: [dict(unix_s=101), dict(unix_s=106)]})
        evidence, errors = sidecar.cleanup_with_timeout_evidence(fleet, server,
            threading.Thread(target=lambda: None), SimpleNamespace(exit=Mock()), {}, clock=cutoff_clock)
        self.assertEqual(errors, [])
        self.assertEqual(evidence['timeout_snapshot_unix_s'], 102.25)
        self.assertEqual(evidence['actor_timeout_logs'][4096], 1)
        self.assertEqual(evidence['actor_cleanup_timeout_logs'][4096], 1)

    def test_snapshot_precedes_shutdown_and_cleanup_generated_events_are_diagnostic(self):
        server = SimpleNamespace(shutdown_event=threading.Event(), client_lock=threading.Lock(),
                                 clients={}, inference_batcher=None, stop=Mock(return_value=None))
        events = []
        def before_shutdown():
            self.assertFalse(server.shutdown_event.is_set())
            return {4096: 0}
        def stop():
            self.assertTrue(server.shutdown_event.is_set())
            events.append(dict(unix_s=104))
            return []
        fleet = SimpleNamespace(timeout_logs=before_shutdown, stop=stop,
                                 timeout_events=lambda: {4096: list(events)})
        worker = threading.Thread(target=lambda: None)
        result, errors = sidecar.cleanup_with_timeout_evidence(fleet, server, worker,
            SimpleNamespace(exit=Mock()), {}, clock=lambda: 100.25)
        self.assertEqual(errors, [])
        self.assertEqual(result['actor_timeout_logs'][4096], 0)
        self.assertEqual(result['actor_cleanup_timeout_logs'][4096], 1)

    def test_completed_full_tail_receipt_survives_only_deliberate_cleanup_timeouts(self):
        from Robotron.tools.test_compare_frozen_measurements import receipt
        from Robotron.tools.compare_frozen_measurements import validate_receipt
        data = receipt()
        evidence = sidecar.timeout_evidence({4096: 0}, {4096: [dict(unix_s=104)]}, 100.25)
        data.update(evidence)
        sidecar.retain_invalidity_reasons(data, ['actor_action_receive_timeout']
            if any(data['actor_timeout_logs'].values()) else [])
        self.assertTrue(data['valid'])
        self.assertEqual(data['actor_timeout_logs'], {4096: 0})
        self.assertEqual(data['actor_cleanup_timeout_logs'], {4096: 1})
        self.assertEqual(data['actor_timeout_logs_after_shutdown'], {4096: 1})
        validated = validate_receipt(data)
        self.assertEqual(len(validated['rows']), 50)
        self.assertGreater(validated['rows'][-1]['end_unix_s'], data['close_ts'])

    def test_runtime_or_late_flushed_or_ambiguous_timeouts_still_invalidate(self):
        from Robotron.tools.test_compare_frozen_measurements import receipt
        for before, event in ((1, dict(unix_s=99)), (0, dict(unix_s=99)),
                              (0, dict(unix_s=100)), (0, dict(unix_s=None))):
            with self.subTest(before=before, event=event):
                data = receipt()
                data.update(sidecar.timeout_evidence({4096: before}, {4096: [event]}, 100.25))
                self.assertEqual(data['actor_timeout_logs'], {4096: 1})
                sidecar.retain_invalidity_reasons(data, ['actor_action_receive_timeout'])
                self.assertFalse(data['valid'])

    def test_timeout_counts_cannot_drop_and_cleanup_does_not_clear_other_failures(self):
        evidence = sidecar.timeout_evidence({4096: 2}, {4096: []}, 100)
        self.assertEqual(evidence['actor_timeout_logs'][4096], 2)
        result = dict(valid=False, reason='whole_cohort_timeout', pending=2)
        result.update(sidecar.timeout_evidence({4096: 0}, {4096: [dict(unix_s=104)]}, 100))
        sidecar.retain_invalidity_reasons(result, [])
        self.assertFalse(result['valid'])
        self.assertEqual(result['reason'], 'whole_cohort_timeout')
        self.assertEqual(result['pending'], 2)

    def test_file_snapshot_counts_only_timeouts_and_parses_late_flush_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            job = SimpleNamespace(directory=Path(directory), actor_slots=sidecar.SLOTS)
            fleet = sidecar.PrivateFleet.__new__(sidecar.PrivateFleet)
            fleet.job = job
            path = job.directory/'actors/4096/console.log'
            path.parent.mkdir(parents=True)
            path.write_text('[robotron-socket-wait] startup\n')
            before = fleet.timeout_logs()
            path.write_text('[robotron-socket-wait] startup\n'
                '[SOCKET ACTION TIMEOUT] slot=4096 unix_s=99\n'
                '[SOCKET ACTION TIMEOUT] slot=4096 unix_s=104\n')
            result = sidecar.timeout_evidence(before, fleet.timeout_events(), 100.5)
            self.assertEqual(result['actor_timeout_logs'][4096], 1)
            self.assertEqual(result['actor_cleanup_timeout_logs'][4096], 1)


if __name__ == '__main__':
    unittest.main()
