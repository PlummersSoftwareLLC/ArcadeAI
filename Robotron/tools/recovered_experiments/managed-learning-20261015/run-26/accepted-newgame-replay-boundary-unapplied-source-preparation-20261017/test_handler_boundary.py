"""UNEXECUTED source proposal: actual full handler, fake wire/CPU-only stand-ins.

No project imports, Torch, sockets, processes, models, replay files or live I/O.
The complete pinned handle_client body runs; parsing, inference and reward math
are injected because these guards concern handler ordering, not those kernels.
The original source is a positive reproducer, never an execution target here.
"""
import ast
import copy
from collections import deque
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import re
import struct
import sys
import threading
import time
from types import ModuleType, SimpleNamespace
import typing
import unittest
from unittest.mock import Mock
from contextlib import redirect_stdout


HERE = Path(__file__).resolve().parent
GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SOCKET = GAME / 'Scripts/dqn/socket_server.py'
BASE_SHA = 'd99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214'
NSTEP_SHA = 'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'
RESET_SHA = '65430d472231e3a1bf0f794cc65603bf5e41c495c446d9a4bab59ad0d3a3a669'
PATCH_SHA = 'c0ed76c79e90fbde22b80b6cb9aea5e2391fc2711141dcae0904cfe94d7b8d44'
CANDIDATE_SHA = '4a1f6a3cc7c82d8c85e1af93ceac0ca7457663d5f5ba7c7d893e3c2b3003e26c'


def authenticated(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise AssertionError('Source changed; rebase/review required: ' + str(path))
    return raw.decode()


def candidate_source():
    """Apply only the authenticated unified diff in memory; no source writes."""
    old = authenticated(SOCKET, BASE_SHA).splitlines(True)
    patch = authenticated(HERE / 'unapplied.patch', PATCH_SHA).splitlines(True)
    result, cursor, index = [], 0, 2
    while index < len(patch):
        match = re.fullmatch(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@\n', patch[index])
        if match is None:
            raise AssertionError('Unexpected patch hunk')
        start = int(match.group(1)) - 1
        result.extend(old[cursor:start])
        cursor, index = start, index + 1
        while index < len(patch) and not patch[index].startswith('@@ '):
            kind, line = patch[index][0], patch[index][1:]
            if kind in (' ', '-'):
                if old[cursor] != line:
                    raise AssertionError('Patch context differs')
                cursor += 1
            if kind in (' ', '+'):
                result.append(line)
            if kind not in (' ', '+', '-'):
                raise AssertionError('Unexpected patch line')
            index += 1
    result.extend(old[cursor:])
    result = ''.join(result)
    if hashlib.sha256(result.encode()).hexdigest() != CANDIDATE_SHA:
        raise AssertionError('Candidate bytes differ')
    return result


class Vector(list):
    def copy(self):
        return Vector(self)

    def astype(self, *args, **kwargs):
        return self


NP = SimpleNamespace(ndarray=Vector, float32=float,
                     asarray=lambda value, **kw: Vector(value),
                     concatenate=lambda values: Vector(x for value in values for x in value))


def load_methods(source, selected):
    """Compile real whole methods/classes with only stdlib fixture globals."""
    tree = ast.parse(source)
    body = [copy.deepcopy(node) for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in selected]
    module = ModuleType('_boundary_guard_' + str(len(sys.modules)))
    sys.modules[module.__name__] = module  # dataclass resolves __module__ here.
    module.__dict__.update({name: getattr(typing, name)
                            for name in ('Any', 'Deque', 'List', 'Optional', 'Tuple')})
    module.__dict__.update(deque=deque, dataclass=dataclass, np=NP,
                           time=time, struct=struct, socket=SimpleNamespace(
                               IPPROTO_TCP=6, TCP_NODELAY=1, SOL_SOCKET=1,
                               SO_RCVBUF=8, SO_SNDBUF=7, SHUT_RDWR=2),
                           threading=SimpleNamespace(Timer=lambda *a: SimpleNamespace(start=lambda: None)),
                           traceback=SimpleNamespace(print_exc=lambda: None),
                           random=SimpleNamespace(random=lambda: .5),
                           WIRE_PARAMS_COUNT=1, _MAX_FRAME_PAYLOAD_BYTES=1 << 20,
                           CLIENT_IDLE_TIMEOUT_S=30, _MAX_SCORE_JUMP=250000,
                           _last_implausible_warn_t=0, _WAVE_PROBE=False, _DBG_ACTIONS=False,
                           _SRC_NONE=0, _SRC_DQN=1, _SRC_EPSILON=2, _SRC_EXPERT=3, _SRC_EVAL=4,
                           STRATIFIED_TRAINING_STARTS=False, FIRE_HOLD_FRAMES=4,
                           game_settings=SimpleNamespace(difficulty=1, snapshot=lambda: dict(
                               auto_curriculum=False, start_advanced=False, start_level_min=1)),
                           combine_action=lambda move, fire: move * 9 + fire,
                           split_joint_action=lambda action: divmod(action, 9),
                           action_index_to_wire_dir=lambda action: -1 if action == 8 else action,
                           _active_group_count=lambda *a: 0,
                           _transition_interest_score=lambda *a, **kw: 0,
                           _shape_transition_reward=lambda *a, **kw: (1., 1., 0., 0., 0),
                           get_expert_action=None)
    for name in ('add_episode_to_dqn100k_window', 'add_episode_to_dqn1m_window',
                 'add_episode_to_dqn5m_window', 'add_episode_to_dqn_perframe_window',
                 'add_episode_to_total_windows', 'add_episode_to_eplen_window'):
        module.__dict__[name] = Mock()
    unit = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)]
                           + body, type_ignores=[])
    exec(compile(ast.fix_missing_locations(unit), '<pinned-whole-handler-fixture>', 'exec'), module.__dict__)
    return module


def frame(marker, score, wave=2, alive=True, done=False, start=False):
    return SimpleNamespace(state=Vector([marker]), game_score=score, level_number=wave,
                           player_alive=alive, done=done, start_pressed=start,
                           num_lasers=0, lives=2 if done else 3, preview_pixels=None,
                           save_signal=False, subjreward=0, objreward=0)


class Replay:
    def __init__(self):
        self.commands, self.rows, self.elite = [], [], []

    def step_async(self, *args, **kwargs):
        self.rows.append((copy.deepcopy(args), dict(kwargs)))
        self.commands.append(('step', copy.deepcopy(args), dict(kwargs)))

    def reset_client_async(self, cid):
        self.commands.append(('reset', cid))
        event = threading.Event()
        event.set()
        return event

    def boost_pre_death(self, cid):
        self.commands.append(('death', cid))

    def boost_elite_episode(self, *args, **kwargs):
        self.elite.append((args, kwargs))

    def remove_client(self, cid):
        self.commands.append(('remove', cid))


def run_handler(source, frames, *, measuring=False, private=False):
    names = {'handle_client', '_stack_model_state', '_init_client', '_sync_client_count_locked',
             '_is_eval_client', '_parse_client_handshake', '_pack_action', '_actor_controls',
             '_replay_writable', '_account_frame_batch', '_sync_measurement_boundary',
             '_measurement_snapshot', '_continuous_play_score_dip', '_wave_advanced',
             '_apply_fire_hold', '_reset_new_game_replay_segment'}
    module = load_methods(source, names)
    nstep = load_methods(authenticated(GAME / 'Scripts/dqn/nstep_buffer.py', NSTEP_SHA),
                         {'_PendingStep', 'NStepReplayBuffer'})
    reset = load_methods(authenticated(GAME / 'Scripts/dqn/frozen_evaluation.py', RESET_SHA),
                         {'reset_client_replay_segment'})
    module.NStepReplayBuffer = nstep.NStepReplayBuffer
    module.reset_client_replay_segment = reset.reset_client_replay_segment
    state = SimpleNamespace(lock=threading.Lock(), measurement_active=measuring, measurement_generation=1,
                            measurement_frame_count=0, frame_count=0, learner_frame_count=0,
                            ratchet_frozen=False, override_expert=False, override_epsilon=False,
                            total_training_steps=0, eval_level_1m_average=0)
    for name in ('update_epsilon', 'update_expert_ratio', 'ratchet_note_eval_start',
                 'ratchet_note_eval_episode', 'ratchet_note_eval_abandoned', 'note_game_score',
                 'note_eval_rate', 'note_eval_wave_clear', 'note_training_terminal',
                 'add_eval_episode_reward', 'add_episode_reward', 'increment_total_controls',
                 'add_inference_time'):
        setattr(state, name, Mock())
    state.get_effective_epsilon = lambda: 0.
    state.get_expert_ratio = lambda: 0.
    state.update_learner_frame_count = lambda: setattr(state, 'learner_frame_count', state.learner_frame_count + 1)
    state.update_frame_count = lambda delta: setattr(state, 'frame_count', state.frame_count + delta)
    module.metrics = state
    module.RL_CONFIG = SimpleNamespace(n_step=3, gamma=.99, frame_stack=4, eval_client_stride=0,
                                      client_stall_timeout_s=0, wave_clear_training_terminal=True,
                                      score_new_game_max=100000, score_wrap_modulus=100000000,
                                      score_torn_read_tolerance=100000, max_plausible_score_per_level=35000)
    # Whole methods retain decorators; assemble them into a fixture class.
    attrs = {name: module.__dict__[name] for name in names if name in module.__dict__}
    Server = type('WholeHandlerServer', (), attrs)
    server = Server()
    server.game_boundary_diagnostics = False
    server.replay_enabled = not private
    server.agent = SimpleNamespace(act=Mock(return_value=(1, 2, False)), optimized_samples=123)
    server.async_buffer, server.inference_batcher = Replay(), None
    server.game_journal, server.metrics = None, state
    server.client_lock = threading.Lock()
    server.client_states, server.clients = {}, {0: object()}
    server._eval_override, server._unwrap_stash = {0: private}, {}
    server._game_uid_seq = 0
    server.shutdown_event = threading.Event()
    server.running = True
    server._ensure_preview_client_selected_locked = lambda: (None, False)
    server._preview_enabled_for_client = lambda cid: False
    server._hud_enabled_for_client = lambda cid: False
    server._is_preview_client = lambda cid: False
    server._clear_preview_cache = lambda: None
    server._calc_avg_game_state = lambda: None
    server._cleanup = lambda: None
    server._fail_inference_only = Mock()
    server.journal = []
    server._journal_observe = lambda cid, f, cs, new, **kw: server.journal.append(
        (f.game_score, f.level_number, bool(new), f.done, f.player_alive))
    server._init_client(0)
    client = server.client_states[0]
    if client['replay_disabled'] is not private:
        raise AssertionError('Real initializer did not retain the server replay gate')
    client.update(measurement_active=measuring, measurement_generation=1, replay_episode_partial=False)
    old_act = server.agent.act
    seen_states = []
    def act(value, *args, **kwargs):
        seen_states.append(list(value))
        return old_act(value, *args, **kwargs)
    server.agent.act = act
    payload = struct.pack('>H', 1)
    recv = deque([struct.pack('>H', (1 if private else 2) << 14)])
    for _ in frames:
        recv.extend((struct.pack('>I', len(payload)), payload))
    def receive(*args, **kwargs):
        if recv:
            return recv.popleft()
        server.shutdown_event.set()  # honest fixture EOF, not handler shutdown behavior.
        raise ConnectionError('fixture EOF')
    server._recv_exact = receive
    parsed = iter(copy.deepcopy(frames))
    module.parse_frame_data = lambda *a, **kw: next(parsed)
    module.slice_model_state = lambda value: value.copy()
    sock = SimpleNamespace(setblocking=lambda *a: None, setsockopt=lambda *a: None,
                           sendall=Mock(), shutdown=lambda *a: None, close=lambda: None)
    with redirect_stdout(io.StringIO()):
        server.handle_client(sock, 0)
    # Unexpected handler exceptions are caught by production; assert they did
    # not silently masquerade as successful test completion.
    server._fail_inference_only.assert_not_called()
    if recv or len(server.journal) != sum(f is not None and f.game_score != 500000 for f in frames):
        raise AssertionError('Handler stopped before the scripted accepted frames')
    return SimpleNamespace(server=server, client=client, state=state, replay=server.async_buffer,
                           states=seen_states, replies=[struct.unpack('>bbBBBB', c.args[0])
                                                       for c in sock.sendall.call_args_list])


def old_prefix():
    return [frame(1, 9700), frame(2, 9800), frame(3, 9900)]


class AcceptedNewGameHandlerTests(unittest.TestCase):
    def test_missed_death_reject_then_inactive_reset_has_no_cross_game_row(self):
        for rejected in (frame(9, 500000, alive=False, done=True), None):
            with self.subTest(rejected_by='classifier' if rejected else 'parser'):
                frames = old_prefix() + [rejected, frame(10, 0, wave=0, alive=False)]
                old = run_handler(authenticated(SOCKET, BASE_SHA), frames)
                new = run_handler(candidate_source(), frames)
                self.assertEqual(len(old.replay.rows), 1)  # Actual original reproducer.
                args, kw = old.replay.rows[0]
                self.assertEqual((args[4], kw['horizon']), (False, 3))
                self.assertEqual(args[3][0], 10)
                self.assertEqual(new.replay.rows, [])
                self.assertEqual(new.server.journal, old.server.journal)
                self.assertEqual(new.replies[3][:3], (-1, -1, 0))
                self.assertEqual(new.state.frame_count, 4)  # Rejected wire frame excluded.

    def test_playable_reset_isolates_history_fifo_and_partial_life_hof(self):
        frames = old_prefix() + [frame(10, 0, wave=1, start=True), frame(11, 100, wave=1),
                                 frame(12, 200, wave=1), frame(13, 300, wave=1),
                                 frame(14, 300, wave=1, alive=False, done=True)]
        new = run_handler(candidate_source(), frames)
        self.assertEqual(new.states[3], [10] * 4)
        self.assertTrue(new.replay.rows)
        self.assertTrue(all(min(args[0]) >= 10 and min(args[3]) >= 10 for args, kw in new.replay.rows))
        self.assertEqual(new.replay.commands[0][0], 'reset')
        self.assertLess(next(i for i, c in enumerate(new.replay.commands) if c[0] == 'reset'),
                        next(i for i, c in enumerate(new.replay.commands) if c[0] == 'step'))
        self.assertEqual(new.replay.elite, [])  # Missed old terminal leaves partial life.
        self.assertEqual(new.state.add_episode_reward.call_count, 0)

    def test_observed_natural_death_preserves_terminal_tails_and_fresh_life_hof(self):
        frames = old_prefix() + [frame(4, 9900, alive=False, done=True),
                                 frame(10, 0, wave=1, start=True),
                                 frame(11, 100, wave=1, alive=False, done=True)]
        old = run_handler(authenticated(SOCKET, BASE_SHA), frames)
        new = run_handler(candidate_source(), frames)
        self.assertEqual(new.replay.rows, old.replay.rows)
        self.assertEqual([kw['horizon'] for args, kw in new.replay.rows[:3]], [3, 2, 1])
        self.assertEqual(len(new.replay.elite), 2)
        self.assertEqual(new.state.add_episode_reward.call_count, 2)

    def test_wave_clear_wrap_and_continuous_dip_match_original_handler(self):
        cases = [old_prefix() + [frame(4, 10000, wave=3, alive=False)],
                 [frame(1, 99999900), frame(2, 0), frame(3, 100)],
                 [frame(1, 11350, wave=3), frame(2, 11300, wave=3), frame(3, 13050, wave=3)]]
        for frames in cases:
            with self.subTest(scores=[f.game_score for f in frames]):
                old = run_handler(authenticated(SOCKET, BASE_SHA), frames)
                new = run_handler(candidate_source(), frames)
                self.assertEqual(new.replay.rows, old.replay.rows)
                self.assertEqual(new.server.journal, old.server.journal)
                self.assertEqual(new.states, old.states)

    def test_measurement_and_private_frozen_handler_paths_remain_identical(self):
        frames = old_prefix() + [frame(10, 0, wave=1, start=True),
                                 frame(11, 100, wave=1, alive=False, done=True)]
        for private in (False, True):
            with self.subTest(private=private):
                old = run_handler(authenticated(SOCKET, BASE_SHA), frames, measuring=True, private=private)
                new = run_handler(candidate_source(), frames, measuring=True, private=private)
                self.assertEqual(new.replay.commands, old.replay.commands)
                self.assertEqual(new.replay.rows, [])
                self.assertEqual(new.server.journal, old.server.journal)
                self.assertEqual(new.states, old.states)

    def test_same_game_reject_only_gap_is_separate_and_intentionally_unfixed(self):
        frames = old_prefix() + [frame(9, 500000), frame(10, 10000)]
        old = run_handler(authenticated(SOCKET, BASE_SHA), frames)
        new = run_handler(candidate_source(), frames)
        self.assertEqual(new.replay.rows, old.replay.rows)
        self.assertEqual(len(new.replay.rows), 1)
        self.assertEqual(new.replies[3][:3], (-1, -1, 0))
        self.assertFalse(any(c[0] == 'reset' for c in new.replay.commands))

    def test_patch_changes_only_newgame_boundary_and_helper(self):
        old, new = ast.parse(authenticated(SOCKET, BASE_SHA)), ast.parse(candidate_source())
        old_nodes = {(type(n).__name__, n.name): ast.dump(n, include_attributes=False)
                     for n in ast.walk(old) if isinstance(n, ast.FunctionDef)}
        new_nodes = {(type(n).__name__, n.name): ast.dump(n, include_attributes=False)
                     for n in ast.walk(new) if isinstance(n, ast.FunctionDef)}
        self.assertEqual(set(new_nodes) - set(old_nodes), {('FunctionDef', '_reset_new_game_replay_segment')})
        self.assertEqual([key for key in old_nodes if old_nodes[key] != new_nodes[key]],
                         [('FunctionDef', 'handle_client')])


if __name__ == '__main__':
    unittest.main(verbosity=2)
