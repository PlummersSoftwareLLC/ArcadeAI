"""Private full-handler proof of a measurement FIFO acknowledgement.

No listener is opened. The existing binary wire parser, handler, measurement
boundary, replay consumer and inference batcher run from unchanged source copies.
Numerical inference, memory storage, the socket carrier and housekeeping timers
are test doubles. This does not authorize sending a probe to a live trainer.
"""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import threading
from unittest.mock import patch


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SOCKET_SHA = '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408'


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


def prepare(work):
    require(digest(GAME/'Scripts/dqn/socket_server.py') == SOCKET_SHA, 'Held handler changed')
    files = {p.name: p.read_bytes() for p in (GAME/'Scripts/dqn').glob('*.py')
             if not p.name.startswith('test_')}
    require(len(files) <= 64 and sum(map(len, files.values())) < 4 << 20, 'Source-copy budget')
    work.mkdir(mode=0o700)
    package = work/'private/Scripts/dqn'
    package.mkdir(parents=True)
    for name, raw in files.items():
        with (package/name).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
    helper = GAME/'tools/game_boundary_diagnostics_proposal/wire_integration_validation/test_wire_integration.py'
    with (work/'wire-carrier.py').open('xb') as stream:
        stream.write(helper.read_bytes())
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    for name in ('models', 'control', 'cache', 'journal'):
        (work/name).mkdir()
    (work/'models/game_settings.json').write_text('{}\n')
    (work/'control/learning_control.json').write_text('{}\n')
    publish(work/'input.json', dict(package_hashes={name: hashlib.sha256(raw).hexdigest()
        for name, raw in files.items()}, source_bytes=sum(map(len, files.values())),
        wire_carrier_sha256=digest(helper), installed_handler_sha256=SOCKET_SHA,
        all_private_package_bytes_identical_to_installed=True))


def execute(work):
    # All package configuration and caches are private before any numerical
    # import. CUDA remains hidden, and this proof does not instantiate a model.
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
        TORCHINDUCTOR_CACHE_DIR=str(work/'cache/inductor'),
        TORCH_EXTENSIONS_DIR=str(work/'cache/extensions'),
        TRITON_CACHE_DIR=str(work/'cache/triton'), CUDA_CACHE_PATH=str(work/'cache/cuda'))
    import numpy as np
    import torch
    manifest = json.loads((work/'input.json').read_bytes())
    package = work/'private/Scripts/dqn'
    require(all(digest(package/name) == value for name, value in manifest['package_hashes'].items()),
            'Private package source drift')
    require(digest(work/'wire-carrier.py') == manifest['wire_carrier_sha256'], 'Carrier drift')
    sys.path.insert(0, str(work/'private/Scripts'))
    from dqn import config, socket_server as module
    namespace = dict(require=require, copy=copy)
    node = next(n for n in ast.parse((work/'wire-carrier.py').read_bytes()).body
                if isinstance(n, ast.ClassDef) and n.name == 'MemoryWire')
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'wire-carrier.py', 'exec'), namespace)
    Carrier = namespace['MemoryWire']
    config.RL_CONFIG.inference_batch_max_size = 16
    module.get_expert_action = None
    cases = []

    def frame(score, wave=1, *, alive=True, done=False, start=False, reserves=2):
        return dict(score=score, wave=wave, alive=alive, done=done,
                    start=start, reserves=reserves)

    scenarios = {
        'wave1': [frame(n * 100) for n in range(8)],
        'late_wave': [frame(400000 + n * 100, 36) for n in range(8)],
        'death_and_restart': [frame(100), frame(200), frame(200, alive=False, done=True, reserves=0),
            frame(0, 0, alive=False, start=True, reserves=3),
            frame(0), frame(100), frame(200), frame(300)],
    }
    for case, frames in scenarios.items():
        metrics = config.MetricsData()
        config.metrics = module.metrics = metrics
        for key, value in dict(measurement_active=True, measurement_generation=1,
            measurement_label='private-FIFO-proof', frame_count=2000, learner_frame_count=1000,
            measurement_frame_count=1000, total_training_steps=7, total_optimized_samples=3584,
            training_enabled=False, ratchet_frozen=False, preview_capture_enabled=False,
            hud_enabled=False, override_epsilon=True, override_expert=True,
            epsilon=0., expert_ratio=0.).items():
            setattr(metrics, key, value)
        os.environ['ROBOTRON_RUN_DIR'] = str(work/'journal'/case)

        class Memory:
            def __init__(self):
                self.calls = []

            def max_game_uid(self):
                return 0

            def __getattr__(self, name):
                self.calls.append(name)
                raise AssertionError('Measurement wire touched replay memory: ' + name)

        class Actor:
            training_steps, optimized_samples = 7, 3584

            def __init__(self):
                self.memory = Memory()
                self.entered, self.release, self.completed = (threading.Event() for _ in range(3))
                self.steps, self.actions = [], []

            def step(self, value, *args, **kwargs):
                require(value == 50001 and not args and not kwargs,
                        'Probe unexpectedly enqueued replay experience')
                self.entered.set()
                require(self.release.wait(30), 'Fixture did not release older replay work')
                self.steps.append(value)
                self.completed.set()
                return value

            def act(self, state, epsilon, locked_fire=None):
                require(epsilon == 0. and np.isfinite(state).all(), 'Probe inference controls changed')
                require(state.shape == (config.RL_CONFIG.state_size,), 'Decoded state shape differs')
                self.actions.append(hashlib.sha256(state.tobytes()).hexdigest())
                return 8, 8, False

            def act_batch(self, states, epsilons, locked_fires=None):
                return [self.act(state, epsilon, locked_fire=locked) for state, epsilon, locked in
                        zip(states, epsilons, locked_fires or [None] * len(states))]

        actor = Actor()
        server = module.SocketServer('private-measurement-wire', 0, actor, replay_enabled=True)
        require(server.server_socket is None and server.async_buffer is not None
                and server.inference_batcher is not None, 'Private actual server scope differs')
        server.running = True
        server._init_client(7)
        # This older controlled command stands for pre-pause work. Its actual
        # FIFO consumer is held while the real handler queues its reset marker.
        server.async_buffer.step_async(50001, client_id=6)
        require(actor.entered.wait(5), 'Original replay worker did not enter the held step')
        wire = bytearray(struct.pack('>H', (1 << 14) | (4097 << 1)))
        state = np.zeros(module.WIRE_PARAMS_COUNT, dtype='>f4').tobytes()
        for row in frames:
            payload = struct.pack(module._HDR_FMT_V2, module.WIRE_PARAMS_COUNT, 0., 0.,
                int(row['done']), row['score'], int(row['alive']), 0, int(row['start']),
                20000, row['reserves'], row['wave'], 3) + state
            wire.extend(struct.pack('>I', len(payload)) + payload)
        before_close, close_allowed = threading.Event(), threading.Event()

        class PausedCarrier(Carrier):
            def recv(self, count):
                if self.offset == len(self.wire):
                    before_close.set()
                    require(close_allowed.wait(30), 'Fixture owner did not allow carrier closure')
                return super().recv(count)

        connection = PausedCarrier(server, bytes(wire))
        timer = type('NoTimer', (), {'start': lambda self: None})()
        thread = threading.Thread(target=server.handle_client, args=(connection, 7))
        try:
            with patch.object(module.select, 'select', side_effect=connection.ready), \
                 patch.object(module.threading, 'Timer', return_value=timer), \
                 patch.object(module.socket, 'socket', side_effect=AssertionError('No network permitted')):
                thread.start()
                require(before_close.wait(10), 'Handler did not process every frame/action')
                require(len(connection.actions) == len(frames), 'Actual wire actions incomplete')
                pending = server.measurement_boundary_status(1)
                require(pending['clients'] == 1 and pending['ready'] is False
                        and pending['replay_pending_client_ids'] == [7],
                        'A TCP action incorrectly sufficed for FIFO readiness')
                require(not actor.completed.is_set(), 'Older controlled replay work finished too early')
                marker = server.client_states[7]['measurement_reset_event']
                require(marker is not None and not marker.is_set(), 'Actual FIFO marker missing')
                actor.release.set()
                require(marker.wait(5), 'Actual measurement reset did not acknowledge older replay work')
                ready = server.measurement_boundary_status(1)
                require(ready['ready'] and ready['acknowledged_client_ids'] == [7]
                        and ready['actor_slots'] == [4097], 'Actual boundary status did not join the reset')
                require(actor.completed.is_set(), 'Marker acknowledged before older work finished')
                close_allowed.set()
                thread.join(5)
                require(not thread.is_alive(), 'Actual handler did not finish')
        finally:
            actor.release.set()
            close_allowed.set()
            thread.join(10)
            require(not thread.is_alive(), 'Fixture leaked its actual handler')
            require(server.async_buffer.barrier_async().wait(5), 'Final private FIFO drain failed')
            server.stop()
            require(not server.async_buffer._thread.is_alive()
                    and not server.inference_batcher._thread.is_alive(), 'Fixture leaked a worker')
        require(metrics.frame_count == 2000 + len(frames)
                and metrics.measurement_frame_count == 1000 + len(frames),
                'Probe raw/measurement frame accounting differs')
        require(metrics.learner_frame_count == 1000 and metrics.total_training_steps == 7
                and metrics.total_optimized_samples == 3584, 'Probe advanced learning clocks')
        require(actor.steps == [50001] and not actor.memory.calls,
                'Probe added replay experience or accessed replay/banks')
        require(actor.training_steps == 7 and actor.optimized_samples == 3584,
                'Probe advanced actor training clocks')
        require(server.inference_only_error is None, 'Handler recorded an unexpected failure')
        cases.append(dict(case=case, frames=len(frames), TCP_actions=len(connection.actions),
            action_before_FIFO_ack=True, boundary_ready_only_after_actual_older_step=True,
            probe_replay_steps=0, probe_eligible_frame_credit=0, bank_accesses=0,
            all_owned_threads_joined=True, original_marker_status=pending,
            acknowledged_marker_status=ready))
    require(not torch.cuda.is_initialized() and torch.cuda.device_count() == 0,
            'Private CPU proof touched CUDA')
    require(all(digest(package/name) == value for name, value in manifest['package_hashes'].items()),
            'Private source drift after execution')
    publish(work/'CPU-report.json', dict(status='PASS', cases=cases,
        actual_full_binary_parser_handler_FIFO_and_batcher=True,
        installed_package_bytes_unchanged=True, physical_network_used=False,
        actual_model_or_optimizer_instantiated=False, actual_replay_storage_used=False,
        CUDA_initialized=False, CUDA_devices=0, live_trainer_changed=False,
        deployment_ready=False, limitations=[
            'The actual full handler runs against an in-memory socket carrier and a numerical actor double.',
            'A prospective live probe still requires independently proved absence of every earlier producer, an active managed measurement and exclusive maintenance ownership.',
            'Only managed boundary reset-event readiness proves FIFO acknowledgement; a TCP action alone does not.',
            'This does not establish a live shutdown, listener isolation, real bank persistence or exact checkpoint restoration.'
        ]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    require(not (args.prepare and args.execute), 'Select preparation or execution')
    if args.prepare:
        prepare(args.work)
    elif args.execute:
        execute(args.work)
    else:
        print('PLAN_ONLY')


if __name__ == '__main__':
    main()
