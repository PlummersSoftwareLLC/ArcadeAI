"""Private 192-handler frozen-input handoff component, never a live upgrade.

Uses unchanged installed parser/handler, listener, measurement enter/exit, FIFO,
batcher and final learner gate. Actors are controlled local socket senders;
inference policy, prefetch, memory and numerical learning are explicit doubles.
Only this bounded CPU unit's accept thread is placed in a temporary cgroup.
"""
import argparse
import ast
from contextlib import nullcontext
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import socket
import struct
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SOCKET_SHA = '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408'
TRAINING_SHA = '90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4'


def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())


def prepare(work, freeze_helper):
    require(digest(GAME/'Scripts/dqn/socket_server.py') == SOCKET_SHA, 'Installed handler changed')
    require(digest(GAME/'Scripts/dqn/training.py') == TRAINING_SHA, 'Installed final learner gate changed')
    files = {p.name: p.read_bytes() for p in (GAME/'Scripts/dqn').glob('*.py')
             if not p.name.startswith('test_')}
    require(len(files) <= 64 and sum(map(len, files.values())) < 4 << 20, 'Source-copy budget exceeded')
    work.mkdir(mode=0o700)
    package = work/'private/Scripts/dqn'
    package.mkdir(parents=True)
    for name, data in files.items():
        with (package/name).open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
    with (work/'freeze-helper.py').open('xb') as stream:
        stream.write(freeze_helper.read_bytes())
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    for name in ('models', 'control', 'cache', 'journal', 'freeze-attempts'):
        (work/name).mkdir()
    (work/'models/game_settings.json').write_text('{}\n')
    (work/'control/learning_control.json').write_text('{}\n')
    publish(work/'input.json', dict(package_hashes={n: hashlib.sha256(v).hexdigest()
        for n, v in files.items()}, freeze_helper_sha256=digest(freeze_helper),
        all_package_bytes_identical_to_installed=True, source_bytes=sum(map(len, files.values()))))


class NumericalRegionReached(Exception):
    pass


class GateConfig:
    batch_size = 4096
    baseline_batch_size = 512
    min_replay_to_train = 500_000
    max_samples_per_frame = 8

    @property
    def per_priority_metric(self):
        raise NumericalRegionReached('Actual final guard admitted numerical work')


class PendingBatch:
    def __init__(self):
        self.releases = 0

    def release(self):
        self.releases += 1


def execute(work, *, two_pause=False):
    require(hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled(),
            'Actual free-threaded interpreter required')
    for key in list(os.environ):
        if key.startswith(('DQN_', 'ROBOTRON_')):
            del os.environ[key]
    os.environ.update(CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
        ROBOTRON_DQN_MODEL_DIR=str(work/'models'),
        ROBOTRON_DQN_CONTROL_PATH=str(work/'control/learning_control.json'),
        ROBOTRON_RUN_DIR=str(work/'journal'), DQN_FRAME_STACK='4',
        DQN_NATIVE_BATCH_UPDATE='0', DQN_LEARNING_EXPOSURE_COUNTERS='0',
        OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
        XDG_CACHE_HOME=str(work/'cache'), TORCH_HOME=str(work/'cache/torch'),
        TORCH_EXTENSIONS_DIR=str(work/'cache/extensions'),
        TORCHINDUCTOR_CACHE_DIR=str(work/'cache/inductor'),
        TRITON_CACHE_DIR=str(work/'cache/triton'), CUDA_CACHE_PATH=str(work/'cache/cuda'))
    if two_pause:
        os.environ['DQN_CLIENT_IDLE_TIMEOUT_S'] = '3'
    import numpy as np
    import torch
    manifest = json.loads((work/'input.json').read_bytes())
    package = work/'private/Scripts/dqn'
    require(all(digest(package/n) == v for n, v in manifest['package_hashes'].items()), 'Package drift')
    require(digest(work/'freeze-helper.py') == manifest['freeze_helper_sha256'], 'Freeze helper drift')
    spec = importlib.util.spec_from_file_location('_tested_private_freeze', work/'freeze-helper.py')
    freezer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freezer)
    cgroup = Path('/proc/self/cgroup').read_text().strip()
    require(cgroup.startswith('0::/'), 'Unified private cgroup required')
    root = Path('/sys/fs/cgroup' + cgroup[3:])
    require(root.name.startswith(freezer.UNIT_PREFIX), 'Only the private CPU unit is allowed')
    watchdog = json.loads((work/'watchdog-ready.json').read_bytes())
    require(watchdog['unit'] == root.name and watchdog['pid'] != os.getpid()
        and freezer.starttime(Path('/proc', str(watchdog['pid']), 'stat')) == watchdog['starttime_ticks'],
        'Original external rescue owner is not live')
    sys.path.insert(0, str(work/'private/Scripts'))
    from dqn import config, socket_server as module
    from dqn.managed_measurement import ManagedMeasurement
    config.RL_CONFIG.inference_batch_max_size = 16
    module.get_expert_action = None
    metrics = config.MetricsData()
    config.metrics = module.metrics = metrics
    for key, value in dict(measurement_active=False, measurement_generation=0,
        measurement_label='', frame_count=2000, loaded_frame_count=2000,
        learner_frame_count=1000, measurement_frame_count=1000,
        loaded_measurement_frame_count=1000, loaded_optimized_samples=3072,
        total_training_steps=7, total_optimized_samples=3584,
        training_enabled=True, ratchet_frozen=False, preview_capture_enabled=False,
        hud_enabled=False, override_epsilon=True, override_expert=True,
        epsilon=0., expert_ratio=0.).items():
        setattr(metrics, key, value)

    class Memory:
        size, _adds_total, hof_total, ephof_total = 6_000_000, 0, 0, 0
        tree = SimpleNamespace(data_ptr=0)

        def __init__(self):
            self.calls = []

        def __len__(self):
            return self.size

        def max_game_uid(self):
            return 0

        def __getattr__(self, name):
            self.calls.append(name)
            raise AssertionError('Private measurement unexpectedly touched replay/banks: ' + name)

    class Actor:
        training_steps, optimized_samples, loaded_training_steps = 7, 3584, 6
        training_enabled, behavior_locked, _prefetch_paused = True, False, False
        _recomputed_ce_capture = None

        def __init__(self):
            self.memory = Memory()
            self._training_lock = threading.RLock()
            self.entered, self.release, self.completed = (threading.Event() for _ in range(3))
            self.steps, self.step_attempts, self.controls = [], [], []
            self.actions = 0
            self.action_lock = threading.Lock()

        def step(self, value, *args, **kwargs):
            self.step_attempts.append(type(value).__name__)
            require(type(value) is int and value == 50001 and not args and not kwargs,
                    'Frozen actor frame became a replay step')
            self.entered.set()
            require(self.release.wait(120), 'Fixture owner did not release older replay work')
            self.steps.append(value)
            self.completed.set()
            return value

        def act_batch(self, states, epsilons, locked_fires=None):
            require(all(e == 0. for e in epsilons), 'Measurement exploration changed')
            require(all(s.shape == (config.RL_CONFIG.state_size,) and np.isfinite(s).all()
                        for s in states), 'Decoded actor state differs')
            with self.action_lock:
                self.actions += len(states)
            return [(8, 8, False) for _ in states]

        def _pause_prefetch(self):
            self._prefetch_paused = True
            self.controls.append('pause_prefetch_double')

        def _resume_prefetch(self):
            self._prefetch_paused = False
            self.controls.append('resume_prefetch_double')

        def capture_inference_policy(self):
            return dict(test_policy=True, steps=self.training_steps, samples=self.optimized_samples)

        def install_inference_policy(self, policy):
            require(policy == self.capture_inference_policy(), 'Fixture tried to change its policy')
            self.controls.append('install_same_policy_double')

    actor = Actor()
    server = module.SocketServer('127.0.0.1', 0, actor, replay_enabled=True)
    replay_worker, inference_worker = server.async_buffer, server.inference_batcher
    controller = ManagedMeasurement(actor, metrics, server.game_journal,
        boundary_status=server.measurement_boundary_status)
    listener = threading.Thread(target=server.start, name='FrozenInputAccept', daemon=True)
    clients, sockets, actions = {}, [], 0
    captured_handlers = []
    timer = type('NoTimer', (), {'start': lambda self: None})()
    raw_state = np.zeros(module.WIRE_PARAMS_COUNT, dtype='>f4').tobytes()

    def connect(slot, evaluation):
        client = socket.create_connection(server.server_socket.getsockname(), timeout=3)
        client.settimeout(5)
        client.sendall(struct.pack('>H', ((1 if evaluation else 2) << 14) | (slot << 1)))
        clients[slot] = client
        sockets.append(client)
        return client

    def packet(slot, ordinal):
        # Exercise genuine death/restart edges on every sixteenth actor.
        score, wave, alive, done, start, reserves = ordinal * 100, 1, True, False, False, 2
        if slot < 192 and slot % 16 == 0:
            if ordinal == 2:
                alive, done, reserves = False, True, 0
            elif ordinal == 3:
                score, wave, alive, start, reserves = 0, 0, False, True, 3
            elif ordinal >= 4:
                score = (ordinal - 4) * 100
        payload = struct.pack(module._HDR_FMT_V2, module.WIRE_PARAMS_COUNT, 0., 0.,
            int(done), score, int(alive), 0, int(start), 20000, reserves, wave, 3) + raw_state
        return struct.pack('>I', len(payload)) + payload

    def receive_action(client):
        received = bytearray()
        while len(received) < 6:
            chunk = client.recv(6-len(received))
            require(chunk, 'Actual handler closed before its v2 response')
            received.extend(chunk)
        require(len(received) == 6, 'Actual response framing changed')

    def exchange(slots, ordinal):
        nonlocal actions
        for slot in slots:
            clients[slot].sendall(packet(slot, ordinal))
        for slot in slots:
            receive_action(clients[slot])
            actions += 1

    def client_map():
        with server.client_lock:
            return {cs['client_slot']: cid for cid, cs in server.client_states.items()}

    def queues_empty():
        local_port = server.server_socket.getsockname()[1]
        ports = {c.getsockname()[1] for c in sockets}
        matched = []
        for line in Path('/proc/self/net/tcp').read_text().splitlines()[1:]:
            row = line.split()
            local = int(row[1].rsplit(':', 1)[1], 16)
            remote = int(row[2].rsplit(':', 1)[1], 16)
            if local == local_port and remote in ports and row[3] == '01':
                matched.append((remote, int(row[4].split(':')[1], 16)))
        return len(matched) == 193 and all(count == 0 for _, count in matched)

    gate_namespace = dict(metrics=metrics, RL_CONFIG=GateConfig(), nullcontext=nullcontext)
    training = ast.parse((package/'training.py').read_bytes())
    functions = [n for n in training.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('replay_pressure_reached', 'train_step', '_train_step_impl')]
    require(len(functions) == 3, 'Exact final training functions missing')
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(package/'training.py'), 'exec'),
         gate_namespace)

    def assert_blocked():
        require(gate_namespace['replay_pressure_reached'](actor), 'Sealed-input budget was not exhausted')
        batch = PendingBatch()
        require(gate_namespace['train_step'](actor, prefetched_batch=batch) is None
                and batch.releases == 1, 'Actual final learner gate did not block/release the batch')

    def finish_original_tail(original_handlers, held, frames_before, measured_before):
        eligible_before = frames_before - measured_before
        controller.exit()
        require(actor.training_enabled and metrics.training_enabled
                and not metrics.measurement_active and not actor._prefetch_paused,
                'Actual measurement exit did not restore its controls')
        assert_blocked()
        server.stop()
        for thread in original_handlers.values():
            thread.join(5)
        require(not any(t.is_alive() for t in original_handlers.values()), 'Actual handler did not finish')
        require(not replay_worker._thread.is_alive() and not inference_worker._thread.is_alive(),
                'Actual worker did not finish')
        require(metrics.frame_count == frames_before+192
                and metrics.measurement_frame_count == measured_before+192,
                'Pending measured cleanup tails did not debit both clocks equally')
        require(metrics.frame_count-metrics.measurement_frame_count == eligible_before,
                'Cleanup granted eligible frame credit')
        assert_blocked()
        # Positive control: misclassifying these192 tails as ordinary
        # frames really would pass the original final cap guard.
        metrics.measurement_frame_count -= 192
        require(not gate_namespace['replay_pressure_reached'](actor), 'Negative credit control is ineffective')
        try:
            gate_namespace['train_step'](actor, prefetched_batch=PendingBatch())
            raise AssertionError('Positive control did not reach the numerical sentinel')
        except NumericalRegionReached:
            pass
        finally:
            metrics.measurement_frame_count += 192
        assert_blocked()
        return dict(actors=192, probe=1, decoded_frames=192*9+8, v2_actions=actions,
            distinct_actual_handler_TIDs=len({t.native_id for t in original_handlers.values()}),
            actual_controller_warmed_on_all193_FIFO_markers=True,
            original192_pending_tails_measured_after_flags_restore=True,
            pending_measured_frames=192, extra_replay_steps=0,
            final_gate_blocked_before_and_after_cleanup=True,
            wrong_measurement_debit_positive_control_reached_numerical_sentinel=True,
            listener_hold=held)

    def finish_with_two_pauses(original_handlers, original_map, probe_id, held, frames_before, measured_before):
        """Exercise the actual idle/final-marker/main-finally ordering."""
        original192 = [thread for cid,thread in original_handlers.items() if cid != probe_id]
        require(len(original192) == 192, 'Original192 native handlers missing')
        eligible_before = frames_before-measured_before
        first_generation = controller.generation
        probe_ordinal = 8
        deadline = time.monotonic()+5
        while any(thread.is_alive() for thread in original192) and time.monotonic()<deadline:
            for _ in range(8):
                exchange([8191],probe_ordinal)
                probe_ordinal += 1
            time.sleep(.15)
            require(controller.tick()['phase'] == 'collecting', 'First actual pause unexpectedly ended')
        require(not any(thread.is_alive() for thread in original192), 'Original192 handlers did not idle out')
        require(client_map() == {8191:probe_id}, 'An actor or unknown input producer remains')
        require(metrics.frame_count == frames_before+192+(probe_ordinal-8)
                and metrics.measurement_frame_count == measured_before+192+(probe_ordinal-8),
                'Original192 measured pending tails did not settle before the final pause')
        require(metrics.frame_count-metrics.measurement_frame_count == eligible_before,
                'Idle cleanup created ordinary replay credit')
        controller.exit()
        require(actor.training_enabled and metrics.training_enabled and not metrics.measurement_active
                and not actor._prefetch_paused, 'First pause did not restore actual controls')
        # No wire data is sent between these two supported pauses.
        assert_blocked()
        controller.enter('private192-final-pause-proof',cohort_s=120,timeout_s=180)
        require(controller.generation == first_generation+2 and actor._prefetch_paused
                and not actor.training_enabled, 'Distinct final pause did not re-enter its real barrier')
        require(controller.tick()['phase'] == 'warming', 'Final pause lacks a new probe generation')
        for _ in range(8):
            exchange([8191],probe_ordinal)
            probe_ordinal += 1
        marker = server.client_states[probe_id]['measurement_reset_event']
        require(marker.wait(3), 'Final actual probe FIFO reset did not acknowledge')
        final = controller.tick()
        require(final['phase'] == 'collecting' and final['boundary']['ready']
                and final['boundary']['acknowledged_client_ids'] == [probe_id],
                'Final FIFO marker did not follow all192 completed native handlers')
        clients[8191].close()
        original_handlers[probe_id].join(3)
        require(not original_handlers[probe_id].is_alive() and not client_map(), 'Owned probe handler remains')
        require(replay_worker.barrier_async().wait(3), 'Final actual cleanup FIFO did not finish')
        sealed = dict(frame_count=metrics.frame_count,measurement_frame_count=metrics.measurement_frame_count,
            learner_frame_count=metrics.learner_frame_count,training_steps=metrics.total_training_steps,
            optimized_samples=metrics.total_optimized_samples)
        saved = []
        def save(path,*,save_replay):
            require(save_replay is True and not actor._prefetch_paused and actor.training_enabled,
                    'Actual main finally did not restore controls before its save')
            assert_blocked()
            saved.append(dict(frame_count=metrics.frame_count,measurement_frame_count=metrics.measurement_frame_count,
                learner_frame_count=metrics.learner_frame_count,training_steps=metrics.total_training_steps,
                optimized_samples=metrics.total_optimized_samples))
        actor.save = save
        actor.stop = lambda: None
        tree = ast.parse((package/'main.py').read_bytes())
        finalizers = [node.finalbody for node in ast.walk(tree) if isinstance(node,ast.Try)
            and any(isinstance(v,ast.Expr) and isinstance(v.value,ast.Call)
                and isinstance(v.value.func,ast.Attribute) and isinstance(v.value.func.value,ast.Name)
                and v.value.func.value.id == 'agent' and v.value.func.attr == 'save' for v in node.finalbody)]
        require(len(finalizers) == 1, 'Actual original main shutdown body is ambiguous')
        namespace = dict(managed_measurements=SimpleNamespace(close=controller.exit),ratchet=None,metrics=metrics,
            agent=actor,LATEST_MODEL_PATH=str(work/'models/private-final.pt'),game_settings=SimpleNamespace(save=lambda:None),
            IS_INTERACTIVE=False,kb=None,server=server,srv_thread=SimpleNamespace(join=lambda **kwargs:None),dashboard=None)
        exec(compile(ast.Module(body=finalizers[0],type_ignores=[]),str(package/'main.py'),'exec'),namespace)
        require(saved == [sealed], 'Model/phase save clocks differ from the final source seal')
        require(not replay_worker._thread.is_alive() and not inference_worker._thread.is_alive(), 'An actual worker remains')
        require(dict(frame_count=metrics.frame_count,measurement_frame_count=metrics.measurement_frame_count,
            learner_frame_count=metrics.learner_frame_count,training_steps=metrics.total_training_steps,
            optimized_samples=metrics.total_optimized_samples) == sealed, 'Clocks moved across actual main finally')
        return dict(actors=192,probe=1,decoded_frames=192*9+probe_ordinal,v2_actions=actions,
            distinct_actual_handler_TIDs=len({t.native_id for t in original_handlers.values()}),
            actual_two_supported_pause_generations=[first_generation,first_generation+2],
            original192_native_handlers_completed_before_final_pause=True,
            final_FIFO_marker_acknowledged_after_original192_cleanup=True,owned_probe_native_handler_finished=True,
            no_probe_frames_between_supported_pauses=True,actual_main_finally_AST_executed=True,
            final_checkpoint_operation_is_a_clock_capture_double=True,save_and_post_stop_clocks_identical=sealed,
            pending_measured_frames=192,extra_replay_steps=0,final_numerical_gate_blocked=True,listener_hold=held)

    result = {}
    try:
        with patch.object(module.threading, 'Timer', return_value=timer):
            listener.start()
            require(freezer.wait_for(lambda: server.running), 'Actual listener did not start')
            for slot in range(192):
                connect(slot, False)
            connect(8191, True)
            require(freezer.wait_for(lambda: set(client_map()) == set(range(192)) | {8191}, 5),
                    'All193 original handshakes were not decoded')
            original_map = client_map()
            probe_id = original_map[8191]
            original_handlers = dict(server.clients)
            require(len(original_handlers) == 193, 'Original handler census incomplete')
            captured_handlers = list(original_handlers.values())
            controller.enter('private192-frozen-input-proof', cohort_s=120, timeout_s=180)
            require(not actor.training_enabled and not metrics.training_enabled
                    and metrics.measurement_active and actor._prefetch_paused,
                    'Actual measurement entry did not pause its controls')
            replay_worker.step_async(50001, client_id=999)
            require(actor.entered.wait(5), 'Actual FIFO did not enter older work')
            for ordinal in range(9):
                for begin in range(0, 192, 16):
                    exchange(range(begin, begin+16), ordinal)
            pending = controller.tick()
            require(pending['phase'] == 'warming' and not pending['boundary']['ready']
                    and pending['boundary']['pending_client_ids'] == [probe_id],
                    'Probe did not keep actual measurement warming')
            require(len(pending['boundary']['replay_pending_client_ids']) == 192,
                    'TCP responses bypassed actual FIFO reset acknowledgement')
            require(all(server.client_states[cid]['frames'] == 9
                        for slot, cid in original_map.items() if slot != 8191),
                    'A controlled actor frame was rejected')
            require(queues_empty(), 'Sealed sender still has queued server receive bytes')
            with freezer.private_listener_hold(root, listener, work, 1) as held:
                require(freezer.wait_for(lambda: all(
                    Path('/proc/self/task', str(t.native_id), 'wchan').read_text().strip().startswith(
                        'poll_schedule_timeout') for t in original_handlers.values()), 3),
                    'Original actual handlers were not all in input receive waits')
                require(client_map() == original_map and queues_empty(),
                        'Actual input ownership changed during hold')
                actor.release.set()
                require(replay_worker.barrier_async().wait(5), 'Older replay work did not drain')
                waiting_probe = controller.tick()
                require(waiting_probe['phase'] == 'warming'
                        and waiting_probe['boundary']['acknowledged'] == 192
                        and waiting_probe['boundary']['pending_client_ids'] == [probe_id]
                        and not waiting_probe['boundary']['replay_pending_client_ids'],
                        'The actual192 actor reset markers did not finish before the probe')
                for ordinal in range(8):
                    exchange([8191], ordinal)
                marker = server.client_states[probe_id]['measurement_reset_event']
                require(marker.wait(5), 'Actual probe marker did not acknowledge')
                collecting = controller.tick()
                require(collecting['boundary']['ready'] and collecting['boundary']['acknowledged'] == 193
                        and collecting['phase'] == 'collecting', 'Actual controller did not join the FIFO marker')
                require(actor.completed.is_set() and actor.steps == [50001], 'Older FIFO work differs')
                require(queues_empty(), 'Owned probe left queued input after its actions')
                frames_before = metrics.frame_count
                measured_before = metrics.measurement_frame_count
                require(frames_before == 2000+192*8+8 and measured_before == 1000+192*8+8,
                        'Actual pre-cleanup BATCH8 accounting differs')
                if two_pause:
                    result = finish_with_two_pauses(original_handlers,original_map,probe_id,held,frames_before,measured_before)
                else:
                    result = finish_original_tail(original_handlers,held,frames_before,measured_before)
            listener.join(5)
            require(not listener.is_alive(), 'Actual accept thread did not finish after its restored cgroup')
            require(server.inference_only_error is None, 'Actual handler recorded an isolation failure')
            require(actor.step_attempts == ['int'] and actor.steps == [50001]
                    and not actor.memory.calls, 'Frozen input touched replay or banks')
            expected_neutral = 12 * 2
            publish(work/'post-stop-clock-and-response-witness.json', dict(
                wire_responses=actions, actual_inference_rows=actor.actions,
                expected_neutral_responses=expected_neutral,
                learner_frames=metrics.learner_frame_count,
                metric_training_steps=metrics.total_training_steps,
                agent_training_steps=actor.training_steps,
                metric_optimized_samples=metrics.total_optimized_samples,
                agent_optimized_samples=actor.optimized_samples))
            require(actor.actions + expected_neutral == actions,
                    'Actual inference/neutral response counts differ from the accepted frames')
            require(metrics.learner_frame_count == 1000
                    and metrics.total_training_steps == actor.training_steps == 7
                    and metrics.total_optimized_samples == actor.optimized_samples == 3584,
                    'Unexpected learning-clock change')
            result.update(inference_rows=actor.actions, inactive_neutral_responses=expected_neutral)
    finally:
        actor.release.set()
        for client in sockets:
            client.close()
        server.stop()
        if listener.ident is not None:
            listener.join(5)
        for thread in set(captured_handlers + [t for t in server.clients.values() if t is not None]):
            if thread.ident is not None:
                thread.join(5)
        for worker in [replay_worker, inference_worker]:
            worker._thread.join(5)
        require(not listener.is_alive() and not replay_worker._thread.is_alive()
                and not inference_worker._thread.is_alive(), 'Fixture leaked an owned worker')
    require(not (work/'watchdog-triggered.json').exists(), 'Rescue was used; original proof invalid')
    require(not any(p.is_dir() for p in root.iterdir())
            and (root/'cgroup.type').read_text().strip() == 'domain', 'Temporary cgroup remains')
    require(not torch.cuda.is_initialized() and torch.cuda.device_count() == 0, 'CPU proof touched CUDA')
    require(all(digest(package/n) == v for n, v in manifest['package_hashes'].items()), 'Source drift after proof')
    publish(work/'CPU-report.json', dict(status='PASS', result=result, two_pause=two_pause,
        gil_enabled=sys._is_gil_enabled(), kernel=os.uname().release,
        source_package_unchanged=True, actual_full_handler_listener_measurement_FIFO_and_batcher=True,
        CUDA_initialized=False, CUDA_devices=0, actual_model_or_optimizer_used=False,
        actual_replay_storage_or_bank_persistence_used=False, production_or_fleet_changed=False,
        handoff_ready=False, limitations=[
            'Real193 local TCP connections/native handlers; senders are owned test sockets rather than MAME processes.',
            'Policy installation, prefetch, memory and checkpoint save are doubles. Final numerical work is a sentinel.',
            'This proves ordering/accounting; actual model/replay/bank handoff and a replacement remain unexecuted.'
        ]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--freeze-helper', type=Path)
    parser.add_argument('--two-pause', action='store_true')
    args = parser.parse_args()
    require(not (args.prepare and args.execute), 'Select preparation or execution')
    if args.prepare:
        require(args.freeze_helper is not None, 'Exact tested helper required')
        prepare(args.work, args.freeze_helper)
    elif args.execute:
        execute(args.work, two_pause=args.two_pause)
    else:
        print('PLAN_ONLY')


if __name__ == '__main__':
    main()
