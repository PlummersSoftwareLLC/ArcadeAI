"""UNEXECUTED private full-v2-handler boundary/replay integration proposal.

Future root execution imports only a generated private package. Real parser,
handler, history, nstep, AsyncReplayBuffer, Agent.step and portable replay/bank
methods are exercised; inference is a dummy actor, not a model. No performance,
incidence, production activation or policy-quality claim follows from this test.
"""
import ast
from collections import deque
import copy
import difflib
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import MethodType
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
GAME = HERE.parents[1]
RUN = GAME/'logs/managed-learning-20261015/run-26'
BASE_SHA = 'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed'
PATCH_SHA = 'cb4784e6b2c3fabeba3b0e7284be9df2c94466d35195ac616c38b41767f76878'
ANCESTOR = GAME/'tools/continuous_zero_dip_wave2_proposal/preparation-reviewed2-manifest.json'
ANCESTOR_SHA = '947981d64af6c3cfce1d7191f1a02ce40f8ca79b5273aaee0dcc7a43b1760fd4'
WIRE = GAME/'tools/game_boundary_diagnostics_proposal/wire_integration_validation/test_wire_integration.py'
OLD = '        and (int(frame.game_score) > 0 or not recent_start)\n'
NEW = ('        and (int(frame.game_score) > 0 or not recent_start\n'
       '             or int(frame.level_number) >= 2)\n')
REPLAY_METHODS = frozenset(('__init__', '__len__', 'actor_kind_from_name', 'max_game_uid',
    'add', '_bank_span', '_bank_admit', 'hof_admit', 'ephof_admit',
    '_hof_rebuild_flat_locked', '_ephof_rebuild_flat_locked', 'boost_priorities',
    'apply_pre_death_penalty', '_append_interesting_bank_locked', 'mark_interesting'))
CASES = ('zero_recovery', 'inactive_wave1_reset', 'current_start', 'wave_reset', 'natural_death')
EVENT = 45


def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(pin):
    path = Path(pin['path'])
    require(path.is_absolute() and path.suffix not in ('.pt', '.pth'), 'Source only')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read((4 << 20)+1)
        after = os.fstat(stream.fileno())
    def identity(s):
        return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
            mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)),
            uid=s.st_uid, nlink=s.st_nlink)
    require(identity(before) == identity(after) == identity(path.lstat()) == pin['identity']
        and len(raw) == pin['bytes'] <= 4 << 20 and digest(raw) == pin['sha256'],
        'Pinned source changed: '+str(path))
    return raw


def inputs():
    manifest = json.loads((HERE/'preparation-manifest.json').read_text())
    pins = {p['path']: p for p in manifest['files']+manifest['upstreams']}
    require(len(pins) == len(manifest['files'])+len(manifest['upstreams']), 'Duplicate source')
    for pin in pins.values():
        checked(pin)
    ancestor = json.loads(checked(pins[str(ANCESTOR)]))
    require(pins[str(ANCESTOR)]['sha256'] == ANCESTOR_SHA, 'Wrong CPU6 ancestry')
    original = checked(pins[str(GAME/'Scripts/dqn/socket_server.py')]).decode()
    require(digest(original.encode()) == BASE_SHA and original.count(OLD) == 1, 'Exact f44 required')
    candidate = original.replace(OLD, NEW, 1)
    require(candidate.replace(NEW, OLD, 1) == original, 'Nonfinite candidate delta')
    expected = ''.join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
        fromfile='a/Robotron/Scripts/dqn/socket_server.py', tofile='b/Robotron/Scripts/dqn/socket_server.py'))
    require(checked(pins[str(HERE/'unapplied.patch')]).decode() == expected
        and digest(expected.encode()) == PATCH_SHA, 'Patch differs from cb478')
    return manifest, pins, ancestor, original, candidate


def module_from(pin, name):
    checked(pin)
    spec = importlib.util.spec_from_file_location(name, pin['path'])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replay_classes(pins, config, np):
    """Exact held bodies, portable SumTree branch; no replay-module import.

    The full module imports native_sumtree, which can compile/read a host cache.
    Selecting exact pure class/method nodes avoids that unrelated execution.
    Persistence/sample/load methods are absent, not redirected to shared paths.
    """
    from dqn.bank_output import BankOutputTelemetry, stream_output_enabled
    from dqn.learning_exposure import ReplayInsertExposure, exposure_enabled
    from dqn.model import combine_action, NUM_JOINT
    ledger = []
    class ForbiddenOperation(BaseException):
        pass
    def forbidden(*args, **kwargs):
        ledger.append('Unexpected host/persistence operation')
        raise ForbiddenOperation(ledger[-1])
    import builtins
    safe = dict(vars(builtins))
    for key in ('open', '__import__', 'input', 'breakpoint'):
        safe[key] = forbidden
    scope = dict(__builtins__=safe, __name__='private_exact_replay', np=np,
        threading=threading, deque=deque, RL_CONFIG=config.RL_CONFIG,
        ReplayInsertExposure=ReplayInsertExposure, exposure_enabled=exposure_enabled,
        BankOutputTelemetry=BankOutputTelemetry, stream_output_enabled=stream_output_enabled,
        _native_propagate=None, _native_batch_update=None,
        ACTOR_DQN=0, ACTOR_EPSILON=1, ACTOR_EXPERT=2, ACTOR_KIND_COUNT=3,
        TYPE_ONEHOT_OFFSET=config.TYPE_ONEHOT_OFFSET, TYPE_CLASS_COUNT=config.TYPE_CLASS_COUNT,
        decode_token_types=config.decode_token_types, combine_action=combine_action,
        NUM_JOINT=NUM_JOINT)
    from dqn import actor_tags
    for key in ('ACTOR_DQN', 'ACTOR_EPSILON', 'ACTOR_EXPERT', 'ACTOR_KIND_COUNT'):
        scope[key] = getattr(actor_tags, key)
    raw = checked(pins[str(GAME/'Scripts/dqn/replay_buffer.py')]).decode()
    tree = ast.parse(raw)
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    require('SumTree' in classes and 'PrioritizedReplayBuffer' in classes, 'Actual replay classes missing')
    replay = copy.deepcopy(classes['PrioritizedReplayBuffer'])
    replay.body = [n for n in replay.body if isinstance(n, ast.FunctionDef) and n.name in REPLAY_METHODS]
    require({n.name for n in replay.body} == REPLAY_METHODS, 'Replay dependency omission')
    chosen = [copy.deepcopy(classes['SumTree']), replay]
    require(not any(isinstance(n, (ast.Import, ast.ImportFrom)) for c in chosen for n in ast.walk(c)),
        'Unexpected import in selected class body')
    exec(compile(ast.Module(body=chosen, type_ignores=[]), '<exact-private-replay-bodies>', 'exec'), scope)
    agent = ast.parse(checked(pins[str(GAME/'Scripts/dqn/agent.py')]).decode())
    owner = next(n for n in agent.body if isinstance(n, ast.ClassDef) and n.name == 'RainbowAgent')
    step = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == 'step')
    require(not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(step)), 'Step imports changed')
    exec(compile(ast.Module(body=[copy.deepcopy(step)], type_ignores=[]), '<exact-private-Agent.step>', 'exec'), scope)
    return scope['PrioritizedReplayBuffer'], scope['step'], ledger, forbidden


def trajectory(case):
    def frame(score, wave, alive=True, done=False, start=False, lives=3):
        return dict(score=score, wave=wave, alive=alive, done=done, start=start, lives=lives)
    # Short synthetic prefix; seed accepted clock separately, never wrap ring.
    rows = [frame(0, 1, alive=False, lives=0)]
    rows += [frame(9000, 1) for _ in range(40)]
    rows += [frame(9900, 2) for _ in range(4)]
    require(len(rows) == EVENT, 'Fixed event position')
    event = dict(zero_recovery=frame(0, 2),
        inactive_wave1_reset=frame(0, 1, alive=False, lives=0),
        current_start=frame(0, 2, start=True), wave_reset=frame(0, 1),
        natural_death=frame(99000, 2, alive=False, done=True, lives=0))[case]
    if case == 'natural_death':
        return rows+[event]
    return rows+[event]+[frame(10000+2600*i, 2) for i in range(35)]+[
        frame(101000, 2, alive=False, done=True, lives=0)]


def array_hash(np, value):
    return digest(np.asarray(value, dtype=np.float32).tobytes())


def run_case(module, config, np, work, case, wire_module, Replay, real_step, ledger, forbidden):
    specs = trajectory(case)
    directory = work/'journal'/case
    os.environ['ROBOTRON_RUN_DIR'] = str(directory)
    metrics = config.MetricsData()
    config.metrics = module.metrics = metrics
    for name, value in dict(measurement_active=False, measurement_generation=0,
        managed_experiment='private-boundary-replay', frame_count=2000, learner_frame_count=1000,
        measurement_frame_count=0, total_training_steps=7, total_optimized_samples=3584,
        training_enabled=True, ratchet_frozen=False, preview_capture_enabled=False, hud_enabled=False).items():
        setattr(metrics, name, value)
    memory = Replay(256, config.RL_CONFIG.state_size)
    require(memory._mmap_dir is None and memory._hof_dir is None and memory._ephof_dir is None,
        'RAM-only private replay required')
    steps, bank_calls, rewards = [], [], {}
    class Actor:
        optimized_samples, training_steps = 3584, 7
        def __init__(self):
            self.memory = memory
        def act(self, state, epsilon, locked_fire=None):
            require(state.shape == (config.RL_CONFIG.state_size,) and np.isfinite(state).all(), 'Real state invalid')
            return 8, 8, False
        def step(self, *args, **kwargs):
            idx = real_step(self, *args, **kwargs)
            state, action, reward, next_state, done = args[:5]
            steps.append(dict(index=idx, state=array_hash(np, state), next_state=array_hash(np, next_state),
                reward=float(reward), done=bool(done), horizon=int(kwargs.get('horizon', 1)), actor=kwargs.get('actor')))
            return idx
        save = forbidden
    actor = Actor()
    real_bank = Replay._bank_admit
    def bank_spy(self, bank, indices, score, floor, per_game_cap, stride, max_eps, game_uid, level):
        indices = list(indices)
        accepted = real_bank(self, bank, indices, score, floor, per_game_cap, stride, max_eps, game_uid, level)
        witness = dict(bank=bank, accepted=bool(accepted), score=score, game_uid=game_uid,
            input_indices=indices, stride=stride)
        if accepted:
            slot = int(np.where(getattr(self, bank+'_ep_game')[:getattr(self, bank+'_ep_count')] == game_uid)[0][-1])
            selected = self._bank_span(np.asarray(indices, dtype=np.int64), stride)
            n = int(getattr(self, bank+'_ep_len')[slot]); require(n == len(selected), 'Bank span differs')
            base = slot*stride
            for name in ('states', 'next_states', 'actions', 'rewards', 'dones', 'horizons', 'is_expert', 'actor_kind'):
                require(np.array_equal(getattr(self, bank+'_'+name)[base:base+n], getattr(self, name)[selected]),
                    'Actual bank did not copy actual ring field '+name)
            witness.update(copied_rows=n, all_eight_fields_match_ring=True)
        bank_calls.append(witness)
        return accepted
    memory._bank_admit = MethodType(bank_spy, memory)
    server = module.SocketServer('private-memory-wire', 0, actor, replay_enabled=True)
    require(server.server_socket is None and server.inference_batcher is None and server.async_buffer is not None,
        'Actual replay consumer only; no listener/batcher')
    require(server.game_journal.directory == directory, 'Journal escaped private case')
    server.running = True
    server.preview_disabled = True
    server._init_client(7)
    server._game_uid_seq = 70
    server.client_states[7].update(raw_score_prev=991500, raw_wave_prev=35, frames=204028,
        last_start_frame=203799, player_alive=False, game_uid=70,
        measurement_active=False, measurement_generation=0, replay_episode_partial=False)
    header = struct.pack('>H', (2 << 14) | (4107 << 1))  # actual force-noeval v2 handshake
    wire = bytearray(header)
    for i, spec in enumerate(specs):
        state = np.zeros(module.WIRE_PARAMS_COUNT, dtype='>f4')
        state[0] = (i+1)/1000.0  # unique bounded synthetic state/history witness
        payload = struct.pack(module._HDR_FMT_V2, module.WIRE_PARAMS_COUNT, 0.0, 0.0,
            int(spec['done']), spec['score'], int(spec['alive']), 0, int(spec['start']),
            0, 0, spec['wave'], spec['lives'])+state.tobytes()
        wire.extend(struct.pack('>I', len(payload))+payload)
    class RecordingWire(wire_module.MemoryWire):
        def __init__(self):
            super().__init__(server, bytes(wire))
            self.snapshots = {}
        def sendall(self, payload):
            super().sendall(payload)
            require(server.async_buffer.barrier_async().wait(5), 'Original consumer FIFO barrier failed')
            index = len(self.actions)-1
            if index in (EVENT-1, EVENT, EVENT+1, len(specs)-1):
                cs = server.client_states[7]
                pending = [dict(state=array_hash(np, x.state), reward=x.reward, done=x.done)
                    for x in cs['nstep']._deque]
                self.snapshots[str(index)] = dict(uid=cs['game_uid'], partial=cs.get('replay_episode_partial', False),
                    pending=pending, history=[array_hash(np, x) for x in cs['frame_history']],
                    step_count=len(steps), memory_size=memory.size, hof=memory.hof_ep_count,
                    ephof=memory.ephof_ep_count, accepted_frames=cs['frames'],
                    last_start_frame=cs.get('last_start_frame'), last_state=array_hash(np, cs['last_state'])
                    if cs.get('last_state') is not None else None)
    connection = RecordingWire()
    actual_reward = module._shape_transition_reward
    def reward_spy(*args, **kwargs):
        value = actual_reward(*args, **kwargs)
        rewards[str(len(connection.actions))] = float(value[0])
        return value
    timer = type('NoTimer', (), {'start': lambda self: None})()
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err), \
                patch.object(module.select, 'select', side_effect=connection.ready), \
                patch.object(module.threading, 'Timer', return_value=timer), \
                patch.object(module.socket, 'socket', side_effect=forbidden), \
                patch.object(module, '_shape_transition_reward', side_effect=reward_spy), \
                patch.object(subprocess, 'Popen', side_effect=forbidden):
            server.handle_client(connection, 7)
        require(server.async_buffer.barrier_async().wait(5), 'Cleanup FIFO reset did not finish')
    finally:
        # No late producer: synchronous handler has returned before stop/drain.
        server.async_buffer.stop()
        server.async_buffer._thread.join(5)
    require(not server.async_buffer._thread.is_alive() and server.async_buffer.queue.empty(), 'Consumer not reaped')
    require(not ledger and 'error' not in (out.getvalue()+err.getvalue()).lower(), 'Unexpected swallowed failure')
    require(connection.offset == len(wire) and connection.closed and connection.shutdown_called
        and len(connection.actions) == len(specs), 'Actual full wire/actions/cleanup incomplete')
    require(not server.client_states and server.clients.get(7) is None and server.async_buffer.dropped_steps == 0,
        'Client state/drop cleanup failed')
    require(memory._adds_total == len(steps) == memory.size <= memory.capacity,
        'No ring overwrite permitted; separate stale-slot issue is out of scope')
    require(memory._bank_writer_thread is None and not server.async_buffer._episode_indices
        and not server.async_buffer._client_indices, 'Unexpected persistence or stale episode tracking')
    games_path = directory/'games.jsonl'
    games = [json.loads(line) for line in games_path.read_bytes().splitlines()]
    game_summary = [{k:g[k] for k in ('game_uid', 'score', 'first_play_level', 'complete',
        'eligible', 'excluded_reason', 'boundary_reason')} for g in games]
    bank_census = {bank:dict(episodes=getattr(memory, bank+'_ep_count'), rows=getattr(memory, bank+'_total'),
        offers=list(getattr(memory, '_'+bank+'_recent_offers'))) for bank in ('hof', 'ephof')}
    return dict(case=case, frames=len(specs), actions=len(connection.actions), snapshots=connection.snapshots,
        steps=steps, event_reward=rewards.get(str(EVENT)), bank_calls=bank_calls, banks=bank_census,
        games=game_summary, no_wrap=True, original_consumer_joined=True, no_persistence=True)


def child(work, variant):
    require(os.environ.get('ROBOTRON_ALLOW_PRODUCTION_BOUNDARY_REPLAY_TEST') == '1'
        and os.environ.get('CUDA_VISIBLE_DEVICES') == '' and variant in ('baseline', 'candidate'), 'Explicit CPU gate')
    require(not any(n in sys.modules for n in ('numpy', 'torch', 'dqn')), 'Fresh child required')
    require(sys.version_info[:2] == (3, 14) and sysconfig.get_config_var('Py_GIL_DISABLED')
        and not sys._is_gil_enabled(), 'Native free-threaded Python 3.14 required')
    manifest, pins, ancestor, before, after = inputs()
    package = work/'private/Scripts/dqn'
    require(work.is_relative_to(RUN) and package.is_dir(), 'Private run26 work only')
    for name, pin in ancestor['private_package_sources'].items():
        expected = after.encode() if name == 'socket_server.py' and variant == 'candidate' else checked(pin)
        require((package/name).read_bytes() == expected, 'Private package drift '+name)
    sys.path.insert(0, str(package.parent))
    import numpy as np
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    require(not torch.cuda.is_initialized() and torch.cuda.device_count() == 0, 'CUDA must stay hidden')
    from dqn import config, socket_server as module
    require(Path(config.MODEL_DIR) == work/'models' and config.learning_control.path == work/'control/learning_control.json',
        'Default control/model path escaped private work')
    # Only storage capacities change. Production HOF/EpHOF floors and rewards remain.
    for key, value in dict(inference_batching_enabled=False, interesting_replay_bank_size=256,
        hof_enabled=True, ephof_enabled=True, hof_max_episodes=2, ephof_max_episodes=2,
        hof_episode_stride=64, ephof_episode_stride=64).items():
        setattr(config.RL_CONFIG, key, value)
    require(config.RL_CONFIG.n_step == 3 and config.RL_CONFIG.frame_stack == 4, 'Held n3/history4 required')
    require(config.RL_CONFIG.hof_min_game_score == 50000
        and config.RL_CONFIG.ephof_min_episode_score == 25000, 'Production admission floors changed')
    for key, value in dict(start_advanced=False, start_level_min=1, epsilon_pct=0,
        expert_pct=0, auto_curriculum=False, difficulty=5).items():
        setattr(config.game_settings, key, value)
    Replay, real_step, ledger, forbidden = replay_classes(pins, config, np)
    wire_module = module_from(pins[str(WIRE)], '_private_original_memorywire')
    cases = [run_case(module, config, np, work, case, wire_module, Replay, real_step, ledger, forbidden)
             for case in CASES]
    primary = cases[0]; pre = primary['snapshots'][str(EVENT-1)]; event = primary['snapshots'][str(EVENT)]
    require(pre['uid'] == 71 and len(pre['pending']) == 2 and len(pre['history']) == 4,
        'Scenario did not establish actual pending nstep/history')
    require(event['accepted_frames']-1 == 204073 and event['accepted_frames']-1-event['last_start_frame'] == 274,
        'Seeded accepted-clock condition drift')
    pending_states = [x['state'] for x in pre['pending']]
    if variant == 'candidate':
        require(event['uid'] == 71 and not event['partial'] and len(event['pending']) == 2,
            'Corrected continuity/reset witness failed')
        require(len(event['history']) == 4 and event['history'][:-1] == pre['history'][1:],
            'Actual history was cleared or reordered across the zero')
        wanted = pre['pending'][0]['reward']+config.RL_CONFIG.gamma*pre['pending'][1]['reward'] \
            +config.RL_CONFIG.gamma**2*primary['event_reward']
        row = primary['steps'][pre['step_count']]
        require(row['state'] == pending_states[0] and row['horizon'] == 3 and not row['done']
            and math.isclose(row['reward'], wanted, rel_tol=1e-7, abs_tol=1e-7),
            'Real cross-zero nstep return differs')
        require(all(any(x['state'] == state for x in primary['steps']) for state in pending_states),
            'Pending transitions were silently lost')
        require(all(primary['banks'][bank]['episodes'] == 1 for bank in ('hof', 'ephof'))
            and len(primary['bank_calls']) == 2 and all(x['accepted'] and x['all_eight_fields_match_ring']
            for x in primary['bank_calls']), 'Natural life did not enter both actual banks')
        require(len(primary['games']) == 1 and primary['games'][0]['eligible']
            and primary['games'][0]['score'] == 101000, 'Real journal continuity failed')
    else:
        require(event['uid'] == 72 and event['partial'] and not event['pending'], 'Old false-reset not reproduced')
        require(not any(x['state'] in pending_states for x in primary['steps']), 'Old dropped tail unexpectedly survived')
        require(all(primary['banks'][bank]['episodes'] == 0 for bank in ('hof', 'ephof'))
            and not primary['bank_calls'], 'Old partial life unexpectedly entered banks')
        require(len(primary['games']) == 2 and primary['games'][0]['boundary_reason'] == 'score_reset',
            'Old false journal split not reproduced')
    require('dqn.native_sumtree' not in sys.modules and 'dqn.replay_buffer' not in sys.modules
        and not any('dqn.'+n in sys.modules for n in ('agent', 'training', 'prefetch', 'metrics_dashboard')),
        'Forbidden whole learner/replay/native/cache import')
    loaded = {}
    for name, mod in list(sys.modules.items()):
        if name == 'dqn' or name.startswith(('dqn.', 'v3.')):
            path = Path(mod.__file__).resolve(); require(path.is_relative_to(package), 'Module escaped package')
            loaded[name] = digest(path.read_bytes())
    for name, pin in ancestor['private_package_sources'].items():
        expected = after.encode() if name == 'socket_server.py' and variant == 'candidate' else checked(pin)
        require((package/name).read_bytes() == expected, 'Private source changed after execution')
    require(not torch.cuda.is_initialized(), 'CUDA initialized')
    (work/'result.json').write_text(json.dumps(dict(status='PASS', variant=variant, cases=cases,
        loaded_private_modules=loaded, actual_handler_parser_nstep_history_async_step_ring_banks=True,
        replay_scope='Exact selected held methods; portable SumTree, RAM-only tiny banks, dummy inference; no learner or persistence.'),
        indent=2, allow_nan=False)+'\n')


class BoundaryReplayIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.pins, cls.ancestor, cls.before, cls.after = inputs()

    def test_exact_unapplied_predicate_and_all_other_functions_unchanged(self):
        def functions(source):
            return {n.name:ast.dump(n) for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)}
        a, b = functions(self.before), functions(self.after)
        self.assertEqual(set(a), set(b))
        self.assertEqual([k for k in a if a[k] != b[k]], ['_continuous_play_score_dip'])

    def test_private_full_handler_replay_banks_and_genuine_controls(self):
        require(os.environ.get('ROBOTRON_ALLOW_PRODUCTION_BOUNDARY_REPLAY_TEST') == '1'
            and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'Explicit future CPU gate required')
        require(sys.version_info[:2] == (3, 14) and sysconfig.get_config_var('Py_GIL_DISABLED')
            and not sys._is_gil_enabled(), 'Native free-threaded Python 3.14 required')
        root = Path(os.environ['ROBOTRON_BOUNDARY_REPLAY_TEST_WORK_ROOT']).resolve(strict=True)
        require(root.is_relative_to(RUN) and not any(x in sys.modules for x in ('numpy', 'torch', 'dqn')),
            'Fresh stdlib parent/root-owned ignored work required')
        wire = module_from(self.pins[str(WIRE)], '_private_wire_parent')
        results = {}
        for variant in ('baseline', 'candidate'):
            with tempfile.TemporaryDirectory(prefix='boundary-replay-'+variant+'-', dir=root) as temporary:
                work = Path(temporary); package = work/'private/Scripts/dqn'; package.mkdir(parents=True)
                for name, pin in self.ancestor['private_package_sources'].items():
                    raw = self.after.encode() if variant == 'candidate' and name == 'socket_server.py' else checked(pin)
                    (package/name).write_bytes(raw)
                for name in ('models', 'control', 'journal', 'cache', 'tmpfs'): (work/name).mkdir()
                (work/'models/game_settings.json').write_text('{}\n')
                (work/'control/learning_control.json').write_text('{}\n')
                env = wire.child_environment(work)
                env.update(ROBOTRON_ALLOW_PRODUCTION_BOUNDARY_REPLAY_TEST='1',
                    ROBOTRON_REJECTED_GAP_TELEMETRY='0', ROBOTRON_GAME_BOUNDARY_DIAGNOSTICS='0',
                    DQN_STREAM_BANK_OUTPUT='0', DQN_LEARNING_EXPOSURE_COUNTERS='0', DQN_N_STEP='3')
                argv = [sys.executable, '-Xgil=0', '-I', '-B', str(Path(__file__).resolve()),
                    '--private-child', str(work), variant]
                process = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, start_new_session=True)
                try:
                    stdout, stderr = process.communicate(timeout=70)
                except subprocess.TimeoutExpired:
                    process.kill(); stdout, stderr = process.communicate(timeout=10)
                    self.fail('Original owned child timeout/reaped; no retry\n'+stdout+'\n'+stderr)
                self.assertEqual(process.returncode, 0, stdout+'\n'+stderr)
                results[variant] = json.loads((work/'result.json').read_text())
                self.assertEqual(results[variant]['status'], 'PASS')
                print(json.dumps(dict(variant=variant, child_argv=argv, exit=process.returncode,
                    result=results[variant]), allow_nan=False))
        old = {x['case']:x for x in results['baseline']['cases']}
        new = {x['case']:x for x in results['candidate']['cases']}
        self.assertEqual(set(old), set(CASES)); self.assertEqual(set(new), set(CASES))
        for case in CASES[1:]:
            with self.subTest(unchanged_control=case):
                self.assertEqual(old[case], new[case])


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--private-child':
        child(Path(sys.argv[2]).resolve(strict=True), sys.argv[3])
    else:
        unittest.main()
