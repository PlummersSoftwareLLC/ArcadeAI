"""Dormant differential fixture; root may select it only after the quality freeze.

Runs the actual complete pinned handle_client twice, with the patch applied
only in memory. No project imports, networking, subprocesses, timers, models,
replay files, numerical packages or host process queries are permitted.
Parser, inference, reward kernels and external sinks are explicit stand-ins;
this is handler ordering/equivalence evidence, never a production-cost test.
Authorship does not mean the suite has been executed or passed.
"""
import __future__
import ast
import builtins
from collections import deque
import copy
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path
import re
import struct
import sys
from types import ModuleType, SimpleNamespace
import typing
import unittest
from contextlib import redirect_stdout


HERE = Path(__file__).resolve().parent
GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
SOCKET = GAME / 'Scripts/dqn/socket_server.py'
HELPER = GAME / 'tools/rejected_gap_telemetry_proposal/rejected_gap_telemetry_reviewed3.py'
BASE_SHA = 'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed'
PATCH_SHA = 'bafc74d09e0d305a10f26a65fccbfd0b09915d91e0641dcf45ebfe415ed6feb0'
CANDIDATE_SHA = '2669dc6cb1dc9965dd8e8e5ceac9ffcb44091d0c119a96ddef86b11d4d27e0db'
HELPER_SHA = 'd58610a139644b79f39504e48e1bc43bda9837cc51d743bec623103918c50cbd'
NSTEP_SHA = 'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'
RESET_SHA = '65430d472231e3a1bf0f794cc65603bf5e41c495c446d9a4bab59ad0d3a3a669'
STAGES = frozenset(('after_reset', 'previous_step', 'nstep_before', 'nstep_after',
    'enqueue_called', 'enqueue_returned', 'one_step', 'next_action', 'finish'))
METHODS = frozenset(('handle_client', '_stack_model_state', '_init_client',
    '_sync_client_count_locked', '_is_eval_client', '_parse_client_handshake',
    '_pack_action', '_actor_controls', '_replay_writable', '_account_frame_batch',
    '_sync_measurement_boundary', '_measurement_snapshot', '_reset_new_game_replay_segment'))
GLOBALS = frozenset(('_continuous_play_score_dip', '_wave_advanced', '_apply_fire_hold'))


def authenticated(path, expected):
    # The only host reads in this suite are these explicit source/patch inputs.
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise AssertionError('Pinned source changed; rebase/review required: ' + str(path))
    return raw.decode()


def candidate_source(old):
    lines = old.splitlines(True)
    patch = authenticated(HERE / 'unapplied.patch', PATCH_SHA).splitlines(True)
    if patch[:2] != ['--- a/Robotron/Scripts/dqn/socket_server.py\n',
                     '+++ b/Robotron/Scripts/dqn/socket_server.py\n']:
        raise AssertionError('Unexpected patch destination')
    result, cursor, index = [], 0, 2
    while index < len(patch):
        match = re.fullmatch(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@\n', patch[index])
        if match is None:
            raise AssertionError('Unexpected patch hunk')
        start = int(match.group(1)) - 1
        if start < cursor:
            raise AssertionError('Overlapping patch hunks')
        result.extend(lines[cursor:start])
        cursor, index = start, index + 1
        while index < len(patch) and not patch[index].startswith('@@ '):
            kind, line = patch[index][0], patch[index][1:]
            if kind in (' ', '-'):
                if lines[cursor] != line:
                    raise AssertionError('Patch context differs')
                cursor += 1
            if kind in (' ', '+'):
                result.append(line)
            if kind not in (' ', '+', '-'):
                raise AssertionError('Unexpected patch line')
            index += 1
    result.extend(lines[cursor:])
    candidate = ''.join(result)
    if hashlib.sha256(candidate.encode()).hexdigest() != CANDIDATE_SHA:
        raise AssertionError('Proposed bytes differ')
    return candidate


class FixtureViolation(BaseException):
    """Escapes production except Exception; also recorded and checked afterward."""


class InjectedFailure(RuntimeError):
    pass


class StrictNamespace(SimpleNamespace):
    def __getattr__(self, name):
        self._violations.append('Unplanned dependency: ' + self._label + '.' + name)
        raise FixtureViolation(self._violations[-1])


class Vector(list):
    def copy(self):
        return Vector(self)

    def astype(self, *args, **kwargs):
        return self


class Flag:
    def __init__(self):
        self.value = False

    def set(self):
        self.value = True

    def is_set(self):
        return self.value


class Lock:
    def __init__(self):
        self.held = False

    def __enter__(self):
        if self.held:
            raise FixtureViolation('Unexpected recursive fixture lock')
        self.held = True
        return self

    def __exit__(self, *args):
        self.held = False


def frozen(value):
    """Snapshot all compared data now; never compare aliases mutated later."""
    if value is None or type(value) in (bool, int, float, str, bytes):
        return value
    if isinstance(value, dict):
        return {key: frozen(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, deque)):
        return tuple(frozen(item) for item in value)
    if isinstance(value, Flag):
        return ('flag', value.is_set())
    if hasattr(value, '__dict__'):
        return (type(value).__name__, frozen(vars(value)))
    raise FixtureViolation('Unexpected output type: ' + type(value).__name__)


def frame(marker, score, wave=2, *, alive=True, done=False, start=False,
          actor='dqn', measure=None):
    return SimpleNamespace(state=Vector([marker]), game_score=score, level_number=wave,
        player_alive=alive, done=done, start_pressed=start, num_lasers=0,
        lives=2 if done else 3, preview_pixels=None, save_signal=False,
        subjreward=0, objreward=0, fixture_actor=actor, fixture_measure=measure)


class Driver:
    def __init__(self, frames, *, enabled=True, private=False, measuring=False,
                 n_step=3, send_failure=None, enqueue_failure=None, infer_failure=None,
                 eof_after_gap=False):
        self.frames = copy.deepcopy(frames)
        self.enabled, self.private, self.n_step = enabled, private, n_step
        self.measuring = measuring
        self.send_failure, self.enqueue_failure = send_failure, enqueue_failure
        self.infer_failure, self.eof_after_gap = infer_failure, eof_after_gap
        self.violations, self.trace, self.hooks = [], [], []
        self.wall, self.tick, self.current = 1000., 0, None
        self.parsed = self.sends = self.enqueues = self.inferences = 0
        self.injected = []

    def namespace(self, label, **kwargs):
        return StrictNamespace(_violations=self.violations, _label=label, **kwargs)

    def forbidden(self, *args, **kwargs):
        self.violations.append('Forbidden import/open/input/host operation')
        raise FixtureViolation(self.violations[-1])

    def note(self, name, *args, **kwargs):
        self.trace.append((name, frozen(args), frozen(kwargs)))

    def clock_ns(self):
        self.tick += 1
        return 1000000 + self.tick

    def base_globals(self):
        safe = dict(vars(builtins))
        for name in ('__import__', 'open', 'input', 'breakpoint'):
            safe[name] = self.forbidden
        values = dict(__builtins__=safe, deque=deque, dataclass=dataclass, deepcopy=copy.deepcopy,
            np=self.namespace('np', ndarray=Vector, float32=float,
                asarray=lambda value, **kw: Vector(value),
                concatenate=lambda values: Vector(x for value in values for x in value)),
            time=self.namespace('time', time=lambda: self.wall, perf_counter=lambda: self.wall,
                monotonic_ns=self.clock_ns),
            os=self.namespace('os', getpid=lambda: 7001), struct=struct,
            socket=self.namespace('socket', IPPROTO_TCP=6, TCP_NODELAY=1,
                SOL_SOCKET=1, SO_RCVBUF=8, SO_SNDBUF=7, SHUT_RDWR=2),
            threading=self.namespace('threading', Lock=Lock,
                Timer=lambda *a: self.namespace('timer', start=lambda: self.note('timer_deferred'))),
            traceback=self.namespace('traceback', format_exc=lambda: 'FIXTURE_TRACEBACK\n'),
            sys=self.namespace('sys', stderr=self.namespace('stderr',
                write=lambda text: self.note('stderr', text), flush=lambda: self.note('stderr_flush'))),
            random=self.namespace('random', random=lambda: .5),
            WIRE_PARAMS_COUNT=1, _MAX_FRAME_PAYLOAD_BYTES=1 << 20,
            CLIENT_IDLE_TIMEOUT_S=30, _MAX_SCORE_JUMP=250000,
            _last_implausible_warn_t=0, _WAVE_PROBE=False, _DBG_ACTIONS=False,
            _SRC_NONE=0, _SRC_DQN=1, _SRC_EPSILON=2, _SRC_EXPERT=3, _SRC_EVAL=4,
            STRATIFIED_TRAINING_STARTS=False, FIRE_HOLD_FRAMES=4,
            game_settings=self.namespace('settings', difficulty=1,
                snapshot=lambda: dict(auto_curriculum=False, start_advanced=False, start_level_min=1)),
            combine_action=lambda move, fire: move * 9 + fire,
            split_joint_action=lambda action: divmod(action, 9),
            action_index_to_wire_dir=lambda action: -1 if action == 8 else action,
            _active_group_count=lambda *a: 0,
            _transition_interest_score=lambda *a, **kw: .25,
            _shape_transition_reward=self.reward,
            get_expert_action=lambda *a, **kw: self.expert())
        values.update({name: getattr(typing, name)
            for name in ('Any', 'Deque', 'List', 'Optional', 'Tuple')})
        for name in ('add_episode_to_dqn100k_window', 'add_episode_to_dqn1m_window',
                     'add_episode_to_dqn5m_window', 'add_episode_to_dqn_perframe_window',
                     'add_episode_to_total_windows', 'add_episode_to_eplen_window'):
            values[name] = self.recorder(name)
        return values

    def recorder(self, name):
        return lambda *args, **kwargs: self.note(name, *args, **kwargs)

    def reward(self, frame, previous, *args, **kwargs):
        self.note('reward', frame.state, previous, **kwargs)
        delta = max(0, frame.game_score - previous)
        return (float(delta) / 100., float(delta) / 100., 0., -1. if frame.done else 0., delta)

    def expert(self):
        self.note('expert')
        return 3, 4

    def load(self, source, *, methods=(), functions=(), classes=(), helper=False):
        """Root-time AST extraction, never a project/module import.

        Complete method bodies and decorators are retained. Imports and module
        initialization are excluded; all reachable external dependencies are
        explicit above. Missing/unplanned dependencies cannot fall back to host.
        """
        tree = ast.parse(source)
        selected = []
        if helper:
            selected = [copy.deepcopy(node) for node in tree.body
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.FunctionDef, ast.ClassDef))]
        else:
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name in functions:
                    selected.append(copy.deepcopy(node))
                elif isinstance(node, ast.ClassDef):
                    if node.name in classes:
                        selected.append(copy.deepcopy(node))
                    elif node.name == 'SocketServer':
                        selected.extend(copy.deepcopy(item) for item in node.body
                            if isinstance(item, ast.FunctionDef) and item.name in methods)
            actual = {node.name for node in selected}
            if actual != set(methods) | set(functions) | set(classes):
                raise AssertionError('Missing/duplicate extraction selection')
        name = '_none_ticket_fixture_' + str(len(sys.modules))
        module = ModuleType(name)
        sys.modules[name] = module  # dataclass needs its private module globals.
        module.__dict__.update(self.base_globals())
        unit = ast.Module(body=selected, type_ignores=[])
        code = compile(ast.fix_missing_locations(unit), '<closed-full-handler-fixture>', 'exec',
            flags=__future__.annotations.compiler_flag, dont_inherit=True)
        exec(code, module.__dict__)
        return module

    def run(self, source, helper_source, nstep_source, reset_source):
        module = self.load(source, methods=METHODS, functions=GLOBALS)
        nstep = self.load(nstep_source, classes=('_PendingStep', 'NStepReplayBuffer'))
        reset = self.load(reset_source, functions=('reset_client_replay_segment',))
        helper = self.load(helper_source, helper=True)
        module.NStepReplayBuffer = nstep.NStepReplayBuffer
        module.reset_client_replay_segment = reset.reset_client_replay_segment
        state = self.namespace('metrics', lock=Lock(), measurement_active=self.measuring,
            measurement_generation=1, measurement_frame_count=0, frame_count=0,
            learner_frame_count=0, ratchet_frozen=False, override_expert=False,
            override_epsilon=False, total_training_steps=0, eval_level_1m_average=0)
        for name in ('update_epsilon', 'update_expert_ratio', 'ratchet_note_eval_start',
            'ratchet_note_eval_episode', 'ratchet_note_eval_abandoned', 'note_game_score',
            'note_eval_rate', 'note_eval_wave_clear', 'note_training_terminal',
            'add_eval_episode_reward', 'add_episode_reward', 'increment_total_controls',
            'add_inference_time'):
            setattr(state, name, self.recorder(name))
        state.get_effective_epsilon = lambda: .2 if self.current and self.current.fixture_actor == 'epsilon' else 0.
        state.get_expert_ratio = lambda: 1. if self.current and self.current.fixture_actor == 'expert' else 0.
        def count_learner():
            state.learner_frame_count += 1
            self.note('learner_frame')
        def count_frames(delta):
            state.frame_count += delta
            self.note('fleet_frames', delta)
        state.update_learner_frame_count, state.update_frame_count = count_learner, count_frames
        module.metrics = state
        module.RL_CONFIG = self.namespace('RL_CONFIG', n_step=self.n_step, gamma=.99,
            frame_stack=4, eval_client_stride=0, client_stall_timeout_s=0,
            wave_clear_training_terminal=True, score_new_game_max=100000,
            score_wrap_modulus=100000000, score_torn_read_tolerance=100000,
            max_plausible_score_per_level=35000, eval_epsilon=0.)
        module.RL_CONFIG.ratchet_max_credible_final = 2000000.
        module.RL_CONFIG.ratchet_stuck_void_s = 120.
        Server = type('WholeHandler', (), {name: module.__dict__[name] for name in METHODS})
        server = Server()
        server.game_boundary_diagnostics, server.replay_enabled = False, not self.private
        server._rejected_gaps = helper.RejectedGapTelemetry(enabled=self.enabled,
            clock_ns=self.clock_ns)
        real_event = server._rejected_gaps.event
        def traced_event(kind, connection=None, **data):
            # None calls may differ; every non-None call and all real helper
            # state/counters/witnesses must still match exactly.
            item = ('hook', kind, connection, frozen(data))
            self.hooks.append(item)
            if not (kind in STAGES and connection is None):
                self.trace.append(item)
            return real_event(kind, connection, **data)
        server._rejected_gaps.event = traced_event
        def act(value, epsilon, **kwargs):
            self.inferences += 1
            self.note('inference', value, epsilon, **kwargs)
            if self.inferences == self.infer_failure:
                self.injected.append('inference')
                raise InjectedFailure('inference failure')
            return 1, 2, bool(self.current and self.current.fixture_actor == 'epsilon')
        server.agent = self.namespace('agent', act=act, optimized_samples=123)
        server.inference_batcher = None
        def step(*args, **kwargs):
            self.enqueues += 1
            self.note('replay_step_called', *args, **kwargs)
            if self.enqueues == self.enqueue_failure:
                self.injected.append('enqueue')
                raise InjectedFailure('enqueue failure')
            self.note('replay_step_returned')
        def reset_async(cid):
            self.note('replay_reset', cid)
            flag = Flag(); flag.set()
            return flag
        server.async_buffer = self.namespace('replay', step_async=step,
            reset_client_async=reset_async, boost_pre_death=self.recorder('replay_death'),
            boost_elite_episode=self.recorder('replay_elite'), remove_client=self.recorder('replay_remove'))
        if self.private:
            server.async_buffer = None  # Matches the inference-only constructor gate.
        server.game_journal, server.metrics = None, state
        server.client_lock, server._exception_log_lock = Lock(), Lock()
        server.client_states, server.clients = {}, {0: object()}
        server._eval_override, server._unwrap_stash = {0: self.private}, {}
        server._game_uid_seq, server.shutdown_event, server.running = 0, Flag(), True
        server._ensure_preview_client_selected_locked = lambda: (None, False)
        for name in ('_preview_enabled_for_client', '_hud_enabled_for_client', '_is_preview_client'):
            setattr(server, name, lambda cid: False)
        server._clear_preview_cache = self.recorder('preview_clear')
        server._calc_avg_game_state = self.recorder('average_game_state')
        server._cleanup = self.recorder('cleanup')
        server._fail_inference_only = self.recorder('inference_failure_latch')
        server._journal_observe = lambda cid, f, cs, new, **kw: self.note('journal',
            f.game_score, f.level_number, new, f.done, f.player_alive, **kw)
        server._init_client(0)
        client = server.client_states[0]
        if client['replay_disabled'] != self.private:
            raise AssertionError('Real initializer replay gate differs')
        client.update(measurement_active=self.measuring, measurement_generation=1,
            replay_episode_partial=False)
        payload = struct.pack('>H', 1)
        wire = deque([struct.pack('>H', (1 if self.private else 2) << 14)])
        for unused in self.frames:
            wire.extend((struct.pack('>I', len(payload)), payload))
        def receive(sock, wanted, **kwargs):
            if wire:
                data = wire.popleft()
                if len(data) != wanted:
                    self.violations.append('Unexpected receive length/order')
                    raise FixtureViolation(self.violations[-1])
                return data
            if not self.eof_after_gap:
                server.shutdown_event.set()  # Script end, not an actual shutdown claim.
            raise ConnectionError('fixture EOF')
        def parse(data, **kwargs):
            if self.parsed >= len(self.frames):
                self.violations.append('Parser called beyond script')
                raise FixtureViolation(self.violations[-1])
            self.current = self.frames[self.parsed]
            self.parsed += 1
            self.wall = 1000. + self.parsed / 10.
            self.note('parse', self.parsed)
            if self.current is not None and self.current.fixture_measure is not None:
                state.measurement_active = self.current.fixture_measure
                state.measurement_generation += 1
            return self.current
        def send(data):
            self.sends += 1
            self.note('send_called', data)
            if self.sends == self.send_failure:
                self.injected.append('send')
                raise InjectedFailure('send failure')
            self.note('send_returned')
        server._recv_exact = receive
        module.parse_frame_data, module.slice_model_state = parse, lambda value: value.copy()
        sock = self.namespace('sock', setblocking=self.recorder('setblocking'),
            setsockopt=self.recorder('setsockopt'), sendall=send,
            shutdown=self.recorder('socket_shutdown'), close=self.recorder('socket_close'))
        console = io.StringIO()
        with redirect_stdout(console):
            server.handle_client(sock, 0)
        if self.violations:
            raise AssertionError(self.violations)
        expected_early = any(value is not None for value in
            (self.send_failure, self.enqueue_failure, self.infer_failure))
        expected_injection = (['send'] if self.send_failure is not None else
            ['enqueue'] if self.enqueue_failure is not None else
            ['inference'] if self.infer_failure is not None else [])
        if self.injected != expected_injection:
            raise AssertionError('Did not reach the declared injected failure: ' + repr(self.injected))
        if not expected_early and (wire or self.parsed != len(self.frames)):
            raise AssertionError('Handler ended before consuming the whole script')
        failures = [row for row in self.trace if row[0] == 'inference_failure_latch']
        if not expected_early and not self.eof_after_gap and failures:
            raise AssertionError('Unexpected handler failure: ' + repr(failures))
        snapshot = server._rejected_gaps.snapshot()
        # Only primitive state and genuine nstep pending entries are retained.
        return dict(trace=self.trace, hooks=self.hooks, console=console.getvalue(),
            client=frozen(client), stash=frozen(server._unwrap_stash),
            metrics={key: getattr(state, key) for key in ('frame_count', 'learner_frame_count',
                'measurement_frame_count', 'client_count', 'measurement_active', 'measurement_generation')},
            telemetry=snapshot, counts=(self.parsed, self.sends, self.enqueues, self.inferences),
            cleanup=(server.client_states == {}, server.clients == {0: None}))


class FullHandlerFastpathDeferredTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = authenticated(SOCKET, BASE_SHA)
        cls.new = candidate_source(cls.old)
        cls.helper = authenticated(HELPER, HELPER_SHA)
        cls.nstep = authenticated(GAME / 'Scripts/dqn/nstep_buffer.py', NSTEP_SHA)
        cls.reset = authenticated(GAME / 'Scripts/dqn/frozen_evaluation.py', RESET_SHA)

    def pair(self, frames, **options):
        old = Driver(frames, **options).run(self.old, self.helper, self.nstep, self.reset)
        new = Driver(frames, **options).run(self.new, self.helper, self.nstep, self.reset)
        # Sole declared tolerance: the old 13 stage sites can call event(None),
        # whose exact held implementation returns before clock/lock/state access.
        self.assertEqual({k: v for k, v in old.items() if k != 'hooks'},
                         {k: v for k, v in new.items() if k != 'hooks'})
        retained = [row for row in old['hooks'] if not (row[1] in STAGES and row[2] is None)]
        self.assertEqual(new['hooks'], retained)
        self.assertFalse(new['telemetry']['observer_error'])
        self.assertEqual(new['cleanup'], (True, True))
        return old, new

    def test_ordinary_none_ticket_n3_keeps_replay_actions_metrics_and_flush(self):
        old, new = self.pair([frame(i, 9600 + i * 100) for i in range(1, 12)])
        self.assertGreater(len(old['hooks']), len(new['hooks']))
        self.assertEqual(new['counts'], (11, 11, 8, 11))
        steps = [row for row in new['trace'] if row[0] == 'replay_step_called']
        self.assertEqual([row[2]['horizon'] for row in steps], [3] * 8)
        self.assertEqual(new['metrics']['frame_count'], 11)
        self.assertEqual(new['metrics']['learner_frame_count'], 11)
        self.assertEqual(new['telemetry']['counters']['accepted_frames'], 11)

    def test_real_ticket_parser_classifier_and_newgame_closures(self):
        prefix = [frame(1, 9700), frame(2, 9800), frame(3, 9900)]
        scripts = [prefix + [None, frame(4, 10000), frame(5, 10100)],
            prefix + [frame(8, 500000), frame(4, 10000)],
            [frame(1, 500000), frame(2, 500100), frame(8, 200000), frame(3, 500200)],
            prefix + [None, frame(10, 0, wave=0, alive=False), frame(11, 100, wave=1)]]
        for frames in scripts:
            with self.subTest(scores=[f.game_score if f else None for f in frames]):
                old, new = self.pair(frames)
                counters = new['telemetry']['counters']
                self.assertEqual(counters['accepted_closures'], 1)
                self.assertEqual(len(new['telemetry']['witnesses']), 1)
                self.assertTrue(any(row[1] == 'after_reset' and row[2] is not None for row in new['hooks']))
                self.assertEqual(new['telemetry']['pending_gaps'], 0)
        witness = new['telemetry']['witnesses'][0]
        self.assertTrue(witness['accepted_wire']['new_game'])
        self.assertFalse(witness['same_classifier_game'])

    def test_terminal_tails_group_flush_one_step_and_wave_boundary(self):
        prefix = [frame(1, 9700), frame(2, 9800), frame(3, 9900)]
        unused, terminal = self.pair(prefix + [None, frame(4, 9900, alive=False, done=True)])
        rows = [row for row in terminal['trace'] if row[0] == 'replay_step_called']
        self.assertEqual([row[2]['horizon'] for row in rows], [3, 2, 1])
        unused, group = self.pair([frame(1, 9700), frame(2, 9800, actor='expert'),
            None, frame(3, 9900, actor='expert'), frame(4, 10000)])
        witness = group['telemetry']['witnesses'][0]
        self.assertEqual(witness['nstep']['group_flush_before_input'], 1)
        self.assertEqual(witness['nstep']['matured_including_current_input'], 0)
        unused, one = self.pair(prefix + [None, frame(4, 10000)], n_step=1)
        self.assertEqual(one['telemetry']['counters']['one_step_called'], 1)
        self.pair(prefix + [None, frame(4, 10000, wave=3, alive=False)])

    def test_disabled_measurement_generation_and_private_paths(self):
        prefix = [frame(1, 9700), frame(2, 9800), frame(3, 9900)]
        unused, off = self.pair(prefix + [None, frame(4, 10000)], enabled=False)
        self.assertFalse(off['telemetry']['enabled'])
        self.assertTrue(all(value == 0 for value in off['telemetry']['counters'].values()))
        unused, boundary = self.pair(prefix + [None, frame(4, 10000, measure=True),
            frame(5, 10100, measure=False), frame(6, 10200)])
        self.assertEqual(boundary['telemetry']['counters']['measurement_boundary'], 1)
        self.assertGreater(sum(row[0] == 'replay_reset' for row in boundary['trace']), 0)
        for private in (False, True):
            with self.subTest(private=private):
                unused, measured = self.pair(prefix + [None, frame(4, 10000)],
                    measuring=True, private=private, enabled=not private)
                self.assertEqual(measured['counts'][2], 0)
                self.assertEqual(measured['metrics']['learner_frame_count'], 0)

    def test_send_enqueue_inference_and_pending_disconnect_cleanup(self):
        prefix = [frame(1, 9700), frame(2, 9800), frame(3, 9900)]
        for frames, options in (
            (prefix + [None, frame(4, 10000)], {'send_failure': 4}),
            (prefix + [None, frame(4, 10000)], {'send_failure': 5}),
            (prefix + [None, frame(4, 9900, alive=False, done=True)], {'send_failure': 5}),
            (prefix + [None, frame(4, 10000)], {'enqueue_failure': 1}),
            (prefix + [None, frame(4, 10000)], {'infer_failure': 4}),
            (prefix + [None], {'eof_after_gap': True})):
            with self.subTest(options=options):
                unused, new = self.pair(frames, **options)
                self.assertTrue(any(row[0] == 'socket_close' for row in new['trace']))
                self.assertTrue(any(row[0] == 'replay_remove' for row in new['trace']))
                self.assertEqual(new['telemetry']['active_tracked_clients'], 0)
                self.assertTrue(new['telemetry']['witnesses'])

    def test_only_handle_client_changes_and_body_is_not_replaced_by_mirror(self):
        def functions(source):
            return {(type(node).__name__, node.name): ast.dump(node, include_attributes=False)
                for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef)}
        old, new = functions(self.old), functions(self.new)
        self.assertEqual(set(old), set(new))
        self.assertEqual([name for name in old if old[name] != new[name]],
                         [('FunctionDef', 'handle_client')])
        self.assertEqual(self.new.count('if _gap_ticket is not None:'), 13)
        tree = ast.parse(self.old)
        handler = next(item for node in tree.body if isinstance(node, ast.ClassDef)
            and node.name == 'SocketServer' for item in node.body
            if isinstance(item, ast.FunctionDef) and item.name == 'handle_client')
        self.assertGreater(handler.end_lineno - handler.lineno, 800)


if __name__ == '__main__':
    unittest.main(verbosity=2)
