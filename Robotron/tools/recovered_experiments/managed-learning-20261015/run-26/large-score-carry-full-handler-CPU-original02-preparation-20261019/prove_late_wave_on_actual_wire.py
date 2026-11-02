"""Private full-handler score-carry regression; no listener, model or live replay."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import threading
from unittest.mock import patch

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = Path(__file__).resolve().parent
OLD_SHA = '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408'
HELPER_SHA = '4352967c4c29c24938520b55729df0e82f755b1cd13c0a13bba79767253cd5f5'


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publish(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())


def function(source):
    return next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                and n.name == '_continuous_play_score_dip')


def prepare(work):
    require(sha(GAME / 'Scripts/dqn/socket_server.py') == OLD_SHA, 'Installed handler changed')
    require(sha(HERE / 'late_wave_guard.py') == HELPER_SHA, 'Prospective helper changed')
    work.mkdir(mode=0o700)
    package = work / 'private/Scripts/dqn'
    package.mkdir(parents=True)
    files = {p.name: p.read_bytes() for p in (GAME / 'Scripts/dqn').glob('*.py')
             if not p.name.startswith('test_')}
    require(len(files) <= 64 and sum(map(len, files.values())) < 4 << 20, 'Private copy budget')
    original = files['socket_server.py'].decode()
    replacement = (HERE / 'late_wave_guard.py').read_text()
    old_node = function(original)
    new_node = function(replacement)
    lines = original.splitlines(keepends=True)
    new_lines = replacement.splitlines(keepends=True)
    candidate = ''.join(lines[:old_node.lineno - 1] +
                        new_lines[new_node.lineno - 1:new_node.end_lineno] +
                        lines[old_node.end_lineno:])
    def remainder(source):
        tree = ast.parse(source)
        tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef)
                     and n.name == '_continuous_play_score_dip')]
        return ast.dump(tree)
    require(remainder(original) == remainder(candidate), 'Change escaped selected helper')
    files['socket_server.py'] = candidate.encode()
    for name, data in files.items():
        (package / name).write_bytes(data)
    (work / 'original_socket_server.py').write_text(original)
    wire_helper = GAME / 'tools/game_boundary_diagnostics_proposal/wire_integration_validation/test_wire_integration.py'
    (work / 'wire_carrier.py').write_bytes(wire_helper.read_bytes())
    for name in ('models', 'control', 'cache', 'journal'):
        (work / name).mkdir()
    (work / 'models/game_settings.json').write_text('{}\n')
    (work / 'control/learning_control.json').write_text('{}\n')
    manifest = dict(schema='robotron-private-large-score-carry-wire-input-v1',
        installed_sources={str(p): sha(p) for p in (GAME / 'Scripts/dqn').glob('*.py')
                           if not p.name.startswith('test_')},
        package_hashes={name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
        original_socket_sha256=OLD_SHA, helper_sha256=HELPER_SHA,
        candidate_socket_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
        all_other_handler_AST_and_package_bytes_unchanged=True)
    publish(work / 'input.json', manifest)


def frames(case, torn):
    def f(score=0, wave=1, alive=True, done=False, reserves=18, start=False):
        return dict(score=score, wave=wave, alive=alive, done=done, reserves=reserves, start=start)
    if case == 'score_wrap':
        return [f(99999975, 250)] * 350 + [f(475, 250), f(1000, 250)]
    if case == 'wave_wrap':
        return [f(90000, 254)] * 350 + [f(95000, 255), f(96000, 0), f(96500, 1)]
    if case in ('zero_real_restart', 'zero_no_restart', 'truncated_nonzero'):
        spec = importlib.util.spec_from_file_location('_old_wire_cases', GAME /
            'tools/confirmed_game_boundary_proposal/optional_expert_warning_proposal/prove_unused_expert_on_actual_wire.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.specs(case)
    previous, low = {'million': (999975, 475), 'two_million': (1999975, 1000475),
                     'ten_million': (9999975, 475)}[case]
    wave = min(250, previous // 30000 + 1)
    rows = [f(20000, 2), f(0, 0, False, reserves=0, start=True), f(0, 1)]
    rows += [f(score, min(250, max(1, score // 30000 + 1)))
             for score in range(100000, previous, 100000)]
    rows += [f(previous, wave)] * 350
    rows += [f(low if torn else previous, wave), f(previous + 500, wave)]
    rows += [f(previous + 500, wave)] * 8
    rows += [f(previous + 1000, wave, False, True, reserves=0),
             f(0, 0, False, reserves=3, start=True), f(0, 1, reserves=3)]
    rows += [f(100, 1, reserves=3)] * 8
    return rows


def child(work):
    import numpy as np
    import torch
    sys.path.insert(0, str(work / 'private/Scripts'))
    from dqn import config, socket_server as module
    manifest = json.loads((work / 'input.json').read_bytes())
    require(all(sha(work / 'private/Scripts/dqn' / name) == value
                for name, value in manifest['package_hashes'].items()), 'Private source drift')
    namespace = {'require': require, 'copy': copy}
    node = next(n for n in ast.parse((work / 'wire_carrier.py').read_bytes()).body
                if isinstance(n, ast.ClassDef) and n.name == 'MemoryWire')
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'wire_carrier.py', 'exec'), namespace)
    Carrier = namespace['MemoryWire']
    proposed = module._continuous_play_score_dip
    old_namespace = dict(module.__dict__)
    exec(compile(ast.Module(body=[function((work / 'original_socket_server.py').read_text())],
                           type_ignores=[]), 'original_socket_server.py', 'exec'), old_namespace)
    original = old_namespace['_continuous_play_score_dip']
    config.RL_CONFIG.n_step = 3
    config.RL_CONFIG.gamma = .995
    config.RL_CONFIG.inference_batch_max_size = 16
    module.get_expert_action = None
    reports = []

    def run(case, replay, patched, torn):
        random.seed(20261019)
        module._continuous_play_score_dip = proposed if patched else original
        label = f'{case}-{int(replay)}-{int(patched)}-{int(torn)}'
        directory = work / 'journal' / label
        os.environ['ROBOTRON_RUN_DIR'] = str(directory)
        os.environ['ROBOTRON_GAME_COMPLETION_POLICY'] = 'confirmed_reset_reserves_v1'
        os.environ['ROBOTRON_GAME_BOUNDARY_DIAGNOSTICS'] = '1'
        metrics = config.MetricsData()
        config.metrics = module.metrics = metrics
        for key, value in dict(measurement_active=not replay, measurement_generation=1,
            measurement_label='large-carry-wire', managed_experiment='large-carry-wire',
            frame_count=2000, learner_frame_count=1000, measurement_frame_count=1000,
            total_training_steps=7, total_optimized_samples=3584, training_enabled=replay,
            ratchet_frozen=False, preview_capture_enabled=False, hud_enabled=False,
            override_epsilon=True, override_expert=True, epsilon=0., expert_ratio=0.).items():
            setattr(metrics, key, value)

        class Memory:
            def __init__(self):
                self.lock = threading.RLock()
                self.size = 0
                self.actor_kind = np.zeros(10000, dtype=np.uint8)
                self.calls = []
            def max_game_uid(self): return 0
            def apply_pre_death_penalty(self, indices): self.calls.append(('penalty', list(indices)))
            def boost_priorities(self, indices, value): self.calls.append(('boost', list(indices), value))
            def mark_interesting(self, indices, value): self.calls.append(('interest', list(indices), value))
            def hof_admit(self, indices, score, **kw): self.calls.append(('hof', list(indices), score, kw))
            def ephof_admit(self, indices, score, **kw): self.calls.append(('ephof', list(indices), score, kw))

        def digest_array(value): return hashlib.sha256(np.asarray(value).tobytes()).hexdigest()
        def transition(args, kw):
            return dict(state=digest_array(args[0]), action=list(args[1]), reward=float(args[2]),
                        next_state=digest_array(args[3]), done=bool(args[4]), metadata=kw)

        class Actor:
            optimized_samples, training_steps = 3584, 7
            def __init__(self): self.memory = Memory(); self.calls = []; self.steps = []
            def act(self, state, epsilon, locked_fire=None):
                require(state.shape == (config.RL_CONFIG.state_size,) and np.isfinite(state).all(), 'Bad actual model input')
                expected_epsilon = float(config.RL_CONFIG.epsilon_hard_floor) if replay else 0.
                require(epsilon == expected_epsilon, 'Actual actor exploration control changed')
                self.calls.append(dict(state=digest_array(state), epsilon=float(epsilon),
                                       locked_fire=locked_fire))
                return 8, 8, False
            def act_batch(self, states, epsilons, locked_fires=None):
                return [self.act(s, e, locked_fire=f) for s, e, f in
                        zip(states, epsilons, locked_fires or [None] * len(states))]
            def step(self, *args, **kw):
                self.steps.append(transition(args, kw)); self.memory.size += 1
                return len(self.steps) - 1

        actor = Actor()
        server = module.SocketServer('private-large-carry', 0, actor, replay_enabled=replay)
        require(server.server_socket is None and server.inference_batcher.max_batch_size == 16, 'Listener/batch profile changed')
        server.running = True
        server._init_client(7)
        source = frames(case, torn)
        wire = bytearray(struct.pack('>H', ((2 if replay else 1) << 14) | (4097 << 1)))
        for index, row in enumerate(source):
            state = np.zeros(module.WIRE_PARAMS_COUNT, dtype='>f4')
            state[0] = (index % 17) / 17
            payload = struct.pack(module._HDR_FMT_V2, module.WIRE_PARAMS_COUNT, 0., 0.,
                int(row['done']), row['score'], int(row['alive']), 0, int(row['start']),
                20000, row['reserves'], row['wave'], row.get('lives', 7)) + state.tobytes()
            wire.extend(struct.pack('>I', len(payload)) + payload)
        connection = Carrier(server, bytes(wire))
        rewards, enqueues, resets = [], [], []
        shape = module._shape_transition_reward
        def record_reward(*args, **kw):
            value = shape(*args, **kw)
            rewards.append([float(x) for x in value])
            return value
        timer = type('NoTimer', (), {'start': lambda self: None})()
        buffer, batcher = server.async_buffer, server.inference_batcher
        contexts = []
        if buffer is not None:
            step = buffer.step_async
            reset = buffer.reset_client_async
            def record_step(*args, **kw):
                enqueues.append(dict(uid=server.client_states[7]['game_uid'], transition=transition(args, kw)))
                return step(*args, **kw)
            def record_reset(cid):
                client = server.client_states.get(cid, {})
                resets.append(dict(uid=client.get('game_uid'), frames=client.get('frames')))
                return reset(cid)
            contexts = [patch.object(buffer, 'step_async', side_effect=record_step),
                        patch.object(buffer, 'reset_client_async', side_effect=record_reset)]
        try:
            from contextlib import ExitStack
            with ExitStack() as stack:
                for context in contexts: stack.enter_context(context)
                stack.enter_context(patch.object(module.select, 'select', side_effect=connection.ready))
                stack.enter_context(patch.object(module.threading, 'Timer', return_value=timer))
                stack.enter_context(patch.object(module.socket, 'socket', side_effect=AssertionError('No real socket permitted')))
                stack.enter_context(patch.object(module, '_shape_transition_reward', side_effect=record_reward))
                server.handle_client(connection, 7)
                if buffer is not None: require(buffer.barrier_async().wait(5), 'Owned replay FIFO did not drain')
        finally:
            server.stop()
        require(not batcher._thread.is_alive(), 'Owned batcher remains')
        require(buffer is None or not buffer._thread.is_alive(), 'Owned replay consumer remains')
        require(connection.closed and connection.shutdown_called and connection.offset == len(wire), 'Handler stopped before consuming input')
        require(len(connection.actions) == len(source), 'Actual wire action count differs')
        require(server.inference_only_error is None, 'Actual handler error: ' + str(server.inference_only_error))
        require(metrics.total_training_steps == 7 and metrics.total_optimized_samples == 3584, 'Real learner clocks advanced')
        if replay:
            queued = copy.deepcopy([entry['transition'] for entry in enqueues])
            for entry in queued: entry['metadata'].pop('client_id', None)
            require(queued == actor.steps, 'Actual replay FIFO changed or dropped a transition')
        games = [json.loads(line) for line in (directory / 'games.jsonl').read_text().splitlines()]
        semantic = [dict(uid=x['game_uid'], known=x['known_start'], score=x['score'],
                        first_wave=x['first_play_level'], complete=x['complete'], eligible=x['eligible'],
                        reason=x['boundary_reason'], excluded=x['excluded_reason'],
                        previous_reserves=(x.get('terminal_confirmation') or {}).get('previous_raw_reserves')) for x in games]
        result = dict(actions=[x.hex() for x in connection.actions], state_hashes=actor.calls,
            reward_trace=rewards, replay_enqueues=enqueues, replay_steps=actor.steps,
            replay_resets=resets, bank_calls=actor.memory.calls, journal=semantic,
            final_client=connection.final_client, frames=metrics.frame_count,
            learner_frames=metrics.learner_frame_count, measurement_frames=metrics.measurement_frame_count,
            policy_rng_sha256=hashlib.sha256(repr(random.getstate()).encode()).hexdigest())
        publish(work / (label + '.json'), result)
        reports.append(dict(case=case, replay=replay, patched=patched, torn=torn,
                            frames=len(source), replay_rows=len(actor.steps), journal_rows=len(games)))
        return result

    for replay in (False, True):
        for case in ('million', 'two_million', 'ten_million'):
            old_clean = run(case, replay, False, False)
            new_clean = run(case, replay, True, False)
            old_torn = run(case, replay, False, True)
            new_torn = run(case, replay, True, True)
            require(old_clean == new_clean, 'Clean path changed: ' + case)
            require(new_clean == new_torn, 'Torn carry changed corrected semantics: ' + case)
            require(old_torn != old_clean, 'Original full-handler defect did not reproduce: ' + case)
            require(any(x['known'] and x['eligible'] for x in new_torn['journal']), 'Corrected true terminal missing')
        for case in ('score_wrap', 'wave_wrap', 'truncated_nonzero', 'zero_real_restart', 'zero_no_restart'):
            require(run(case, replay, False, False) == run(case, replay, True, False),
                    'Existing reset/wrap behavior changed: ' + case)
    require(not torch.cuda.is_initialized(), 'CPU fixture initialized CUDA')
    publish(work / 'child-result.json', dict(status='PASS', cases=reports,
        actual_binary_parser_handler_batcher=True, actual_nstep_and_async_replay_queue=True,
        synthetic_agent_and_memory_sink=True, real_model_GPU_MAME_listener_or_live_replay=False,
        synthetic_actions_fixed=True, actual_training_epsilon_hard_floor_preserved=True,
        production_changed=False, original_failed_study_remains_invalid=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    if args.child:
        child(args.work); return
    if not args.execute:
        print('PLAN_ONLY'); return
    prepare(args.work)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DQN_', 'ROBOTRON_'))
           and k not in ('LD_PRELOAD', 'PYTHONPATH')}
    env.update(CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', DQN_FRAME_STACK='4', DQN_N_STEP='3',
        DQN_LEARNING_EXPOSURE_COUNTERS='0', DQN_NATIVE_BATCH_UPDATE='0', OMP_NUM_THREADS='2',
        MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2',
        ROBOTRON_DQN_MODEL_DIR=str(args.work / 'models'),
        ROBOTRON_DQN_CONTROL_PATH=str(args.work / 'control/learning_control.json'),
        ROBOTRON_RUN_DIR=str(args.work / 'journal'), XDG_CACHE_HOME=str(args.work / 'cache'),
        TORCH_HOME=str(args.work / 'cache/torch'), TORCHINDUCTOR_CACHE_DIR=str(args.work / 'cache/inductor'),
        TRITON_CACHE_DIR=str(args.work / 'cache/triton'), CUDA_CACHE_PATH=str(args.work / 'cache/cuda'))
    argv = [str(GAME.parent / '.venv-gb300/bin/python'), '-Xgil=0', '-I', '-B',
            str(Path(__file__).resolve()), '--child', '--work', str(args.work)]
    with (args.work / 'child.stdout.txt').open('x') as stdout, (args.work / 'child.stderr.txt').open('x') as stderr:
        result = subprocess.run(argv, env=env, stdout=stdout, stderr=stderr, timeout=130)
    manifest = json.loads((args.work / 'input.json').read_bytes())
    require(all(sha(path) == value for path, value in manifest['installed_sources'].items()), 'Installed sources changed')
    require(result.returncode == 0, 'Original full-handler child failed; preserve without runtime retry')
    require('AsyncReplayBuffer error:' not in (args.work / 'child.stdout.txt').read_text(), 'Replay consumer swallowed a fixture failure')
    require('Traceback' not in (args.work / 'child.stderr.txt').read_text(), 'Handler swallowed a fixture exception')
    report = json.loads((args.work / 'child-result.json').read_bytes())
    publish(args.work / 'result.json', dict(status='PASS', child_exit=0, cases=report['cases'],
        input_manifest=manifest, production_changed=False, no_live_training_or_replay_touched=True))
    print(json.dumps(dict(status='PASS', cases=len(report['cases']), child_exit=0)))


if __name__ == '__main__':
    main()
