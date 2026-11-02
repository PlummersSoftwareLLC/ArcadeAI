"""UNEXECUTED prospective engineering benchmark; never a producer experiment.

Default PLAN reads nothing. Root alone may later run one selected FT3.14/GIL0
process after its release/resource checks. Actual pinned complete handler A and
in-memory guard-only B share the same strict synthetic environment. No sockets,
subprocesses, project imports, model/replay files or numerical libraries exist
in that environment. See the companion manifest for the deliberately limited
interpretation of any future measurements.
"""
import __future__
import argparse
import ast
import builtins
from collections import deque
import copy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import stat
import statistics
import struct
import sys
import sysconfig
import threading
import time
from types import ModuleType, SimpleNamespace
import typing


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME / 'logs/managed-learning-20261015/run-26'
FIXTURE_DIR = GAME / 'tools/rejected_gap_none_ticket_fastpath_proposal'
INPUTS = {
    'fixture': (FIXTURE_DIR / 'test_full_handler_fastpath_deferred.py',
        '5405888c4f13e3d52f16f8f2470861eca0c7a028c934e6ddfe1437e99bebd75a'),
    'socket': (GAME / 'Scripts/dqn/socket_server.py',
        'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed'),
    'patch': (FIXTURE_DIR / 'unapplied.patch',
        'bafc74d09e0d305a10f26a65fccbfd0b09915d91e0641dcf45ebfe415ed6feb0'),
    'helper': (GAME / 'tools/rejected_gap_telemetry_proposal/rejected_gap_telemetry_reviewed3.py',
        'd58610a139644b79f39504e48e1bc43bda9837cc51d743bec623103918c50cbd'),
    'nstep': (GAME / 'Scripts/dqn/nstep_buffer.py',
        'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'),
    'reset': (GAME / 'Scripts/dqn/frozen_evaluation.py',
        '65430d472231e3a1bf0f794cc65603bf5e41c495c446d9a4bab59ad0d3a3a669'),
}
CANDIDATE_SHA = '2669dc6cb1dc9965dd8e8e5ceac9ffcb44091d0c119a96ddef86b11d4d27e0db'
ORDER = ('A', 'B', 'B', 'A', 'B', 'A', 'A', 'B')
WORKERS = 192
INTERNAL_BUDGET_S = 110.
MAX_OUTPUT_BYTES = 4 << 20
PHASES = ('setup', 'warmup', 'data', 'teardown')
EVENTS = frozenset(('setsockopt', 'setblocking', 'parse', 'slice', 'reward',
    'inference', 'send', 'replay_step', 'replay_reset', 'replay_death', 'replay_elite',
    'replay_remove', 'socket_shutdown', 'socket_close', 'journal_dispatch',
    'preview_clear', 'average_game_state', 'cleanup_deferred', 'print',
    'update_epsilon', 'update_expert_ratio', 'ratchet_note_eval_start',
    'ratchet_note_eval_episode', 'ratchet_note_eval_abandoned', 'note_game_score',
    'note_eval_rate', 'note_eval_wave_clear', 'note_training_terminal',
    'add_eval_episode_reward', 'add_episode_reward', 'increment_total_controls',
    'add_inference_time', 'learner_frame', 'fleet_frames',
    'add_episode_to_dqn100k_window', 'add_episode_to_dqn1m_window',
    'add_episode_to_dqn5m_window', 'add_episode_to_dqn_perframe_window',
    'add_episode_to_total_windows', 'add_episode_to_eplen_window'))


def require(value, message):
    if not value:
        raise ValueError(message)


def read_inputs():
    result = {}
    for name, (path, expected) in INPUTS.items():
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_size <= 1 << 20,
                'Selected source must be a bounded regular nonsymlink')
            raw = stream.read((1 << 20) + 1)
            after = os.fstat(stream.fileno())
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_uid', 'st_nlink')
        current = path.lstat()
        require(len(raw) <= 1 << 20 and all(getattr(before, k) == getattr(after, k) ==
            getattr(current, k) for k in fields), 'Selected source changed during authenticated read')
        require(hashlib.sha256(raw).hexdigest() == expected, 'Selected source changed: ' + name)
        result[name] = raw.decode()
    return result


def runtime_identity():
    check = getattr(sys, '_is_gil_enabled', None)
    data = dict(version=sys.version, version_info=list(sys.version_info[:3]),
        executable=sys.executable, Py_GIL_DISABLED=sysconfig.get_config_var('Py_GIL_DISABLED'),
        is_gil_enabled=check() if callable(check) else None)
    require(tuple(sys.version_info[:2]) == (3, 14) and
        data['Py_GIL_DISABLED'] == 1 and data['is_gil_enabled'] is False,
        'Actual FT3.14/GIL0 interpreter required; command flags alone prove nothing')
    return data


def foundation(source, sources):
    """Future root-time extraction of real fixture definitions, never Driver.run."""
    tree = ast.parse(source)
    keep = {'FixtureViolation', 'StrictNamespace', 'Vector', 'Flag'}
    body = [copy.deepcopy(node) for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in keep]
    body += [copy.deepcopy(node) for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in ('frozen', 'candidate_source')]
    body += [copy.deepcopy(node) for node in tree.body if isinstance(node, ast.Assign)
        and all(isinstance(t, ast.Name) and t.id in ('METHODS', 'GLOBALS') for t in node.targets)]
    driver = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Driver')
    body.append(copy.deepcopy(next(node for node in driver.body
        if isinstance(node, ast.FunctionDef) and node.name == 'load')))
    require(len(body) == 9, 'Fixture extraction shape changed')
    def closed_source(path, expected):
        for name, (selected, digest) in INPUTS.items():
            if path == selected and expected == digest:
                return sources[name]
        raise AssertionError('Unplanned foundation source access')
    ns = dict(__name__='_paced_fixture_foundation', __future__=__future__, ast=ast,
        copy=copy, dataclass=dataclass, deque=deque, ModuleType=ModuleType, sys=sys,
        SimpleNamespace=SimpleNamespace, typing=typing, hashlib=hashlib,
        re=re, HERE=FIXTURE_DIR, authenticated=closed_source,
        PATCH_SHA=INPUTS['patch'][1], CANDIDATE_SHA=CANDIDATE_SHA)
    code = compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
        '<authenticated-fixture-foundation>', 'exec',
        flags=__future__.annotations.compiler_flag, dont_inherit=True)
    exec(code, ns)
    return SimpleNamespace(**ns)


class Failures:
    def __init__(self):
        self.lock, self.items, self.total = threading.Lock(), [], 0

    def append(self, value):
        with self.lock:
            self.total += 1
            if len(self.items) < 32:
                self.items.append(str(value)[:500])

    def __getitem__(self, index):
        # The unchanged StrictNamespace raises its just-recorded failure text.
        with self.lock:
            return self.items[index]


class Census:
    def __init__(self):
        self.counts = dict.fromkeys(EVENTS, 0)
        self.digest = hashlib.sha256()

    def record(self, F, name, args, kwargs):
        require(name in EVENTS, 'Unknown synthetic sink event')
        payload = repr((name, F.frozen(args), F.frozen(kwargs))).encode()
        require(len(payload) <= 8192, 'Synthetic sink payload exceeded bound')
        self.counts[name] += 1
        self.digest.update(struct.pack('>I', len(payload)))
        self.digest.update(payload)

    def snapshot(self):
        return dict(counts={k: v for k, v in self.counts.items() if v},
            side_effect_sha256=self.digest.hexdigest())


class Harness:
    def __init__(self, F, sources, version, hz, ticks, lateness_ns, hard_deadline):
        self.F, self.sources, self.version = F, sources, version
        self.hz, self.ticks, self.warm = hz, ticks, round(hz)
        self.period = 1e9 / hz
        self.lateness_ns, self.hard_deadline = lateness_ns, hard_deadline
        self.tls, self.failures = threading.local(), Failures()
        self.start, self.drain = threading.Event(), threading.Event()
        self.ready_condition, self.ready_count = threading.Condition(), 0
        self.origin = self.data_start = self.data_end = 0
        self.contexts, self.threads = [], []
        for cid in range(WORKERS):
            self.contexts.append(SimpleNamespace(cid=cid, phase='setup', tick=-1,
                wire='handshake', frame=None, admitted=0, completed=0,
                data_completed=0, data_after_cutoff=0, body_after_cutoff=0, previous_busy=None,
                service_count=0, service_sum_ns=0, service_max_ns=0,
                wait_count=0, wait_sum_ns=0, lateness_sum_ns=0, lateness_max_ns=0,
                deadline_misses=0, overdue_before_wait=0, early_stopped=False,
                census={p: Census() for p in PHASES}, metric_frames=0,
                learner_frames=0, state_sha256=None, stash_sha256=None,
                error=None, ended=False))

    def ctx(self):
        value = getattr(self.tls, 'ctx', None)
        require(value is not None, 'A sink ran outside its declared actor context')
        return value

    def record(self, name, *args, **kwargs):
        self.ctx().census[self.ctx().phase].record(self.F, name, args, kwargs)

    def callback(self, name):
        return lambda *args, **kwargs: self.record(name, *args, **kwargs)

    def namespace(self, name, **values):
        return self.F.StrictNamespace(_violations=self.failures, _label=name, **values)

    def forbidden(self, *args, **kwargs):
        self.failures.append('Forbidden import/open/input/host fallback in extracted code')
        raise self.F.FixtureViolation('Forbidden target operation')

    def virtual_time(self):
        ctx = getattr(self.tls, 'ctx', None)
        return 1000. if ctx is None else 1000. + (max(0, ctx.tick) + 1) / self.hz

    def globals(self):
        safe = dict(vars(builtins))
        for name in ('__import__', 'open', 'input', 'breakpoint'):
            safe[name] = self.forbidden
        data = dict(__builtins__=safe, deque=deque, dataclass=dataclass,
            deepcopy=copy.deepcopy,
            np=self.namespace('np', ndarray=self.F.Vector, float32=float,
                asarray=lambda value, **kw: self.F.Vector(value),
                concatenate=lambda values: self.F.Vector(x for value in values for x in value)),
            time=self.namespace('time', time=self.virtual_time,
                perf_counter=self.virtual_time, monotonic_ns=time.monotonic_ns),
            os=self.namespace('os', getpid=os.getpid), struct=struct,
            socket=self.namespace('socket', IPPROTO_TCP=6, TCP_NODELAY=1,
                SOL_SOCKET=1, SO_RCVBUF=8, SO_SNDBUF=7, SHUT_RDWR=2),
            threading=self.namespace('threading', Lock=threading.Lock,
                Timer=lambda interval, fn: self.namespace('deferred_timer',
                    start=lambda: self.record('cleanup_deferred', interval))),
            traceback=self.namespace('traceback', format_exc=lambda: 'SYNTHETIC_TRACEBACK\n'),
            sys=self.namespace('sys', stderr=self.namespace('stderr',
                write=lambda text: self.failures.append('Handler stderr: ' + text), flush=lambda: None)),
            print=lambda *args, **kw: self.record('print', *args),
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
            _shape_transition_reward=self.reward, get_expert_action=None)
        data.update({name: getattr(typing, name)
            for name in ('Any', 'Deque', 'List', 'Optional', 'Tuple')})
        for name in EVENTS:
            if name.startswith('add_episode_to_'):
                data[name] = self.callback(name)
        return data

    def reward(self, frame, previous, *args, **kwargs):
        self.record('reward', frame.game_score, previous, frame.state, **kwargs)
        return 1., 1., 0., 0., 1

    def setup(self):
        loader = SimpleNamespace(base_globals=self.globals)
        source = self.sources['socket'] if self.version == 'A' else self.F.candidate_source(self.sources['socket'])
        m = self.F.load(loader, source, methods=self.F.METHODS, functions=self.F.GLOBALS)
        n = self.F.load(loader, self.sources['nstep'], classes=('_PendingStep', 'NStepReplayBuffer'))
        r = self.F.load(loader, self.sources['reset'], functions=('reset_client_replay_segment',))
        h = self.F.load(loader, self.sources['helper'], helper=True)
        m.NStepReplayBuffer, m.reset_client_replay_segment = n.NStepReplayBuffer, r.reset_client_replay_segment
        metrics = self.namespace('metrics', lock=threading.Lock(), measurement_active=False,
            measurement_generation=1, measurement_frame_count=0, frame_count=0,
            learner_frame_count=0, ratchet_frozen=False, override_expert=False,
            override_epsilon=False, total_training_steps=0, eval_level_1m_average=0,
            get_effective_epsilon=lambda: 0., get_expert_ratio=lambda: 0.)
        for name in ('update_epsilon', 'update_expert_ratio', 'ratchet_note_eval_start',
            'ratchet_note_eval_episode', 'ratchet_note_eval_abandoned', 'note_game_score',
            'note_eval_rate', 'note_eval_wave_clear', 'note_training_terminal',
            'add_eval_episode_reward', 'add_episode_reward', 'increment_total_controls',
            'add_inference_time'):
            setattr(metrics, name, self.callback(name))
        def fleet(delta):
            self.ctx().metric_frames += delta
            self.record('fleet_frames', delta)
        def learner():
            self.ctx().learner_frames += 1
            self.record('learner_frame')
        metrics.update_frame_count, metrics.update_learner_frame_count = fleet, learner
        m.metrics = metrics
        m.RL_CONFIG = self.namespace('RL_CONFIG', n_step=3, gamma=.99, frame_stack=4,
            eval_client_stride=0, client_stall_timeout_s=0, wave_clear_training_terminal=True,
            score_new_game_max=100000, score_wrap_modulus=100000000,
            score_torn_read_tolerance=100000, max_plausible_score_per_level=35000,
            eval_epsilon=0., ratchet_max_credible_final=2000000., ratchet_stuck_void_s=120.)
        Server = type('SharedWholeHandler', (), {name: m.__dict__[name] for name in self.F.METHODS})
        server = Server()
        server.game_boundary_diagnostics, server.replay_enabled = False, True
        server._rejected_gaps = h.RejectedGapTelemetry(enabled=True, clock_ns=time.monotonic_ns)
        server.client_lock, server._exception_log_lock = threading.Lock(), threading.Lock()
        server.client_states, server.clients = {}, {cid: object() for cid in range(WORKERS)}
        server._eval_override, server._unwrap_stash = {cid: False for cid in range(WORKERS)}, {}
        server._game_uid_seq, server.shutdown_event, server.running = 0, threading.Event(), True
        server.metrics, server.game_journal, server.inference_batcher = metrics, None, None
        server._ensure_preview_client_selected_locked = lambda: (None, False)
        for name in ('_preview_enabled_for_client', '_hud_enabled_for_client', '_is_preview_client'):
            setattr(server, name, lambda cid: False)
        server._clear_preview_cache = self.callback('preview_clear')
        server._calc_avg_game_state = self.callback('average_game_state')
        server._cleanup = self.forbidden  # Timer stand-in records intent; never executes callback.
        server._fail_inference_only = lambda message: self.failures.append(message)
        server._journal_observe = lambda cid, frame, cs, new, **kw: self.record(
            'journal_dispatch', frame.game_score, frame.level_number, new,
            frame.done, frame.player_alive, **kw)
        def act(value, epsilon, **kw):
            self.record('inference', value, epsilon, **kw)
            return 1, 2, False
        server.agent = self.namespace('agent', act=act, optimized_samples=123)
        def reset(cid):
            self.record('replay_reset', cid)
            flag = self.F.Flag(); flag.set()
            return flag
        server.async_buffer = self.namespace('replay', step_async=self.callback('replay_step'),
            reset_client_async=reset, boost_pre_death=self.callback('replay_death'),
            boost_elite_episode=self.callback('replay_elite'), remove_client=self.callback('replay_remove'))
        server._recv_exact = self.receive
        m.parse_frame_data, m.slice_model_state = self.parse_frame, self.slice_state
        self.server, self.metrics, self.helper_module = server, metrics, h
        for ctx in self.contexts:
            self.tls.ctx = ctx
            server._init_client(ctx.cid)
            # Deterministic connection-local existing UID, no game/reset profile.
            # Global game UID allocation order is not the effect under study.
            server.client_states[ctx.cid].update(game_uid=ctx.cid + 1,
                measurement_active=False, measurement_generation=1, replay_episode_partial=False)
        del self.tls.ctx

    def finish_slot(self, ctx):
        if ctx.previous_busy is not None:
            ended = time.monotonic_ns()
            elapsed = ended - ctx.previous_busy
            if ctx.phase == 'data':
                ctx.service_count += 1
                ctx.service_sum_ns += elapsed
                ctx.service_max_ns = max(ctx.service_max_ns, elapsed)
                ctx.body_after_cutoff += int(ended >= self.data_end)
            ctx.previous_busy = None

    def receive(self, sock, wanted, **kwargs):
        ctx = self.ctx()
        if ctx.wire == 'handshake':
            require(wanted == 2, 'Handshake order')
            ctx.wire = 'header'
            return struct.pack('>H', (2 << 14) | (ctx.cid << 1))
        if ctx.wire == 'payload':
            require(wanted == 2, 'Payload order')
            ctx.wire = 'header'
            return struct.pack('>H', 1)
        require(ctx.wire == 'header' and wanted == 4, 'Header order')
        self.finish_slot(ctx)
        if ctx.tick < 0:
            with self.ready_condition:
                self.ready_count += 1
                self.ready_condition.notify_all()
            if not self.start.wait(timeout=8):
                raise RuntimeError('Bounded start gate expired')
        next_tick = ctx.tick + 1
        if next_tick >= self.warm + self.ticks:
            ctx.phase = 'teardown'
            self.drain.wait(timeout=max(0., self.hard_deadline - time.monotonic()))
            raise ConnectionError('synthetic completed EOF')
        target = self.origin + round(next_tick * self.period + ctx.cid * self.period / WORKERS)
        before = time.monotonic_ns()
        # Every admitted frame must have a future scheduled receive target.
        # Never execute an overdue tick in a saturated catch-up loop.
        if before >= target or before >= self.data_end:
            ctx.overdue_before_wait += 1
            ctx.deadline_misses += 1
            ctx.early_stopped = True
            ctx.phase = 'teardown'
            self.drain.wait(timeout=max(0., self.hard_deadline - time.monotonic()))
            raise ConnectionError('synthetic pacing missed; no catch-up')
        time.sleep((target - before) / 1e9)
        released = time.monotonic_ns()
        late = max(0, released - target)
        ctx.wait_count += 1; ctx.wait_sum_ns += released - before
        ctx.lateness_sum_ns += late; ctx.lateness_max_ns = max(ctx.lateness_max_ns, late)
        if late > self.lateness_ns:
            ctx.deadline_misses += 1
            ctx.early_stopped = True
            ctx.phase = 'teardown'
            self.drain.wait(timeout=max(0., self.hard_deadline - time.monotonic()))
            raise ConnectionError('synthetic lateness budget exceeded; no catch-up')
        if released >= self.data_end:
            ctx.early_stopped = True
            ctx.phase = 'teardown'
            self.drain.wait(timeout=max(0., self.hard_deadline - time.monotonic()))
            raise ConnectionError('synthetic receive cutoff; no extension')
        ctx.tick = next_tick
        ctx.phase = 'warmup' if next_tick < self.warm else 'data'
        ctx.admitted += 1; ctx.previous_busy = released; ctx.wire = 'payload'
        return struct.pack('>I', 2)

    def parse_frame(self, data, **kwargs):
        require(data == struct.pack('>H', 1), 'Synthetic parser payload')
        ctx = self.ctx()
        self.record('parse', ctx.tick)
        ctx.frame = SimpleNamespace(state=self.F.Vector([ctx.cid * 100000 + ctx.tick]),
            game_score=10000 + ctx.tick, level_number=2, player_alive=True, done=False,
            start_pressed=False, num_lasers=0, lives=3, preview_pixels=None,
            save_signal=False, subjreward=0, objreward=0)
        return ctx.frame

    def slice_state(self, value):
        self.record('slice', value)
        return value.copy()

    def send(self, data):
        ctx = self.ctx()
        require(len(data) == 6, 'Six-byte actual pack_action output expected')
        self.record('send', data)
        ctx.completed += 1
        if ctx.phase == 'data':
            ctx.data_completed += 1
            ctx.data_after_cutoff += int(time.monotonic_ns() >= self.data_end)

    def worker(self, ctx):
        self.tls.ctx = ctx
        client = self.server.client_states[ctx.cid]
        sock = self.namespace('socket_sink', setblocking=self.callback('setblocking'),
            setsockopt=self.callback('setsockopt'), sendall=self.send,
            shutdown=self.callback('socket_shutdown'), close=self.callback('socket_close'))
        try:
            self.server.handle_client(sock, ctx.cid)
        except BaseException as error:
            ctx.error = type(error).__name__ + ': ' + str(error)[:400]
            self.failures.append(ctx.error)
        finally:
            self.finish_slot(ctx)
            ctx.phase = 'teardown'
            try:
                ctx.state_sha256 = hashlib.sha256(repr(self.F.frozen(client)).encode()).hexdigest()
                ctx.stash_sha256 = hashlib.sha256(repr(self.F.frozen(
                    self.server._unwrap_stash.get(ctx.cid))).encode()).hexdigest()
            except BaseException as error:
                ctx.error = type(error).__name__ + ': ' + str(error)[:400]
                self.failures.append(ctx.error)
            finally:
                ctx.ended = True

    def run(self):
        after_setup = runtime_after = measured = run_error = None
        try:
            self.setup()
            after_setup = runtime_identity()
            for ctx in self.contexts:
                thread = threading.Thread(target=self.worker, args=(ctx,), daemon=True,
                    name='PacedSyntheticActor' + str(ctx.cid))
                self.threads.append(thread); thread.start()
            setup_end = min(self.hard_deadline, time.monotonic() + 8.)
            with self.ready_condition:
                while self.ready_count != WORKERS and time.monotonic() < setup_end:
                    self.ready_condition.wait(timeout=min(.1, max(0., setup_end - time.monotonic())))
            require(self.ready_count == WORKERS, 'All192 connected actors must reach the pre-frame gate')
            self.origin = time.monotonic_ns() + 250000000
            self.data_start = self.origin + round(self.warm * self.period)
            # Fixed before start: one period lets the last staggered receive finish.
            # It adds no ticks, no catch-up and no post-hoc extension.
            self.data_end = self.data_start + round((self.ticks + 1) * self.period)
            require(self.data_end / 1e9 + 2 < self.hard_deadline, 'Original total budget insufficient; no arm extension')
            self.start.set()
            def until(target):
                remaining = target - time.monotonic_ns()
                if remaining > 0:
                    time.sleep(remaining / 1e9)
            until(self.data_start)
            blocks_before = sys.getallocatedblocks()
            wall_start, cpu_start = time.monotonic_ns(), time.process_time_ns()
            until(self.data_end)
            cpu_end, wall_end = time.process_time_ns(), time.monotonic_ns()
            blocks_after = sys.getallocatedblocks()
            measured = dict(wall_start_ns=wall_start, wall_end_ns=wall_end,
                wall_ns=wall_end-wall_start, process_cpu_ns=cpu_end-cpu_start,
                allocated_blocks_before=blocks_before, allocated_blocks_after=blocks_after,
                allocated_blocks_net_delta=blocks_after-blocks_before,
                process_cumulative_maxrss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        except BaseException as error:
            run_error = type(error).__name__ + ': ' + str(error)[:1000]
        finally:
            if hasattr(self, 'server'):
                self.server.shutdown_event.set()
            self.start.set(); self.drain.set()
            cleanup_end = min(self.hard_deadline, time.monotonic() + 2.)
            for thread in self.threads:
                thread.join(timeout=max(0., cleanup_end - time.monotonic()))
        live_threads = sum(thread.is_alive() for thread in self.threads)
        try:
            runtime_after = runtime_identity()
        except BaseException as error:
            run_error = run_error or type(error).__name__ + ': ' + str(error)[:1000]
        rows = []
        for ctx in self.contexts:
            rows.append(dict(cid=ctx.cid, admitted=ctx.admitted, completed=ctx.completed,
                data_completed=ctx.data_completed, metric_frames=ctx.metric_frames,
                learner_frames=ctx.learner_frames,
                census={phase: ctx.census[phase].snapshot() for phase in PHASES},
                state_sha256=ctx.state_sha256, stash_sha256=ctx.stash_sha256,
                pacing=dict(waits=ctx.wait_count, wait_sum_ns=ctx.wait_sum_ns,
                    lateness_sum_ns=ctx.lateness_sum_ns, lateness_max_ns=ctx.lateness_max_ns,
                    deadline_misses=ctx.deadline_misses, overdue_before_wait=ctx.overdue_before_wait,
                    data_after_cutoff=ctx.data_after_cutoff, body_after_cutoff=ctx.body_after_cutoff,
                    early_stopped=ctx.early_stopped),
                service=dict(count=ctx.service_count, sum_ns=ctx.service_sum_ns, max_ns=ctx.service_max_ns),
                ended=ctx.ended, error=ctx.error))
        # Never wait on a helper lock held by an unfinished synthetic worker.
        snapshot = self.server._rejected_gaps.snapshot() if hasattr(self, 'server') and not live_threads else None
        expected = dict.fromkeys(self.helper_module.COUNTERS, 0) if hasattr(self, 'helper_module') else {}
        expected.update(connections=WORKERS, payloads_complete=WORKERS * (self.warm + self.ticks),
            accepted_frames=WORKERS * (self.warm + self.ticks))
        census_ok = (run_error is None and not live_threads and snapshot is not None and
            snapshot['available'] and not snapshot['observer_error'] and
            snapshot['counters'] == expected and snapshot['active_tracked_clients'] == 0 and
            snapshot['pending_gaps'] == snapshot['accepted_frames_in_progress'] == 0 and
            snapshot['witnesses'] == [] and self.server.client_states == {} and
            all(value is None for value in self.server.clients.values()) and
            all(row['ended'] and row['error'] is None and
                row['completed'] == row['admitted'] == row['metric_frames'] == row['learner_frames'] == self.warm + self.ticks and
                row['data_completed'] == self.ticks and
                row['service']['count'] == self.ticks and
                row['census']['data']['counts'].get('replay_step') == self.ticks for row in rows))
        timing_ok = (measured is not None and
            abs(measured['wall_start_ns'] - self.data_start) <= self.lateness_ns and
            abs(measured['wall_end_ns'] - self.data_end) <= self.lateness_ns and
            all(row['pacing']['deadline_misses'] == row['pacing']['overdue_before_wait'] ==
                row['pacing']['data_after_cutoff'] == row['pacing']['body_after_cutoff'] == 0 and
                not row['pacing']['early_stopped'] for row in rows))
        return dict(version=self.version, workers=WORKERS, runtime_after_setup=after_setup,
            runtime_after_arm=runtime_after, target_hz_per_connection=self.hz,
            warmup_ticks=self.warm, data_ticks=self.ticks,
            scheduled=dict(origin_ns=self.origin, data_start_ns=self.data_start, data_end_ns=self.data_end),
            measured=measured, arm_error=run_error,
            rows=rows, helper=snapshot, expected_helper_counters=expected,
            census_ok=bool(census_ok), timing_ok=bool(timing_ok),
            unexpected_operation_count=self.failures.total, unexpected_operations=self.failures.items,
            threads_still_alive=live_threads, stable_rows_after_all_threads_ended=not live_threads)


def equality_view(arm):
    return [dict(cid=row['cid'], admitted=row['admitted'], completed=row['completed'],
        data_completed=row['data_completed'], metric_frames=row['metric_frames'],
        learner_frames=row['learner_frames'], census=row['census'],
        state_sha256=row['state_sha256'], stash_sha256=row['stash_sha256']) for row in arm['rows']]


def publish(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    require(len(raw) <= MAX_OUTPUT_BYTES, 'Bounded benchmark output exceeded4MiB')
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--hz', type=float)
    parser.add_argument('--ticks', type=int)
    parser.add_argument('--max-lateness-ms', type=float)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--expected-source-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no source/runtime reads, workers, outputs or workload')
        return 0
    require(args.hz is not None and math.isfinite(args.hz) and 10 <= args.hz <= 120 and
        args.ticks is not None and 7.9 <= args.ticks / args.hz <= 8.1 and
        args.max_lateness_ms is not None and math.isfinite(args.max_lateness_ms) and
        0 < args.max_lateness_ms <= 1000 / args.hz and args.output is not None and
        args.expected_source_sha256, 'Explicit bounded root pacing/ticks/tolerance/output/source required')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.expected_source_sha256,
        'Exact selected benchmark source required')
    require(args.output.is_absolute() and args.output.parent == RUN and
        args.output.name.startswith('rejected-gap-none-ticket-paced-'), 'New direct run26 output required')
    actual_runtime = runtime_identity()
    sources = read_inputs()
    F = foundation(sources['fixture'], sources)
    F.candidate_source(sources['socket'])  # Strict complete patch/context/candidate authentication.
    args.output.mkdir(mode=0o700)
    hard_deadline = time.monotonic() + INTERNAL_BUDGET_S
    intent = dict(schema='robotron-paced-full-handler-guard-benchmark-intent-v1',
        runtime_before_setup=actual_runtime, source_sha256=args.expected_source_sha256,
        order=list(ORDER), workers=WORKERS, hz_per_connection=args.hz, data_ticks=args.ticks,
        warmup_ticks=round(args.hz), max_lateness_ms=args.max_lateness_ms,
        fixed_final_completion_allowance_periods=1,
        nominal_arm_s=(round(args.hz)+args.ticks+1)/args.hz,
        nominal_eight_arms_s=8*(round(args.hz)+args.ticks+1)/args.hz,
        source_inputs={name: dict(path=str(p), sha256=s) for name,(p,s) in INPUTS.items()},
        ordinary_no_gap_profile=True, producer_actions=False, source_application=False,
        retries=False, extensions=False, internal_budget_s=INTERNAL_BUDGET_S,
        external_RuntimeMaxSec_required_at_least=120)
    publish(args.output/'intent.json', intent)
    report = dict(schema='robotron-paced-full-handler-guard-benchmark-result-v1',
        status='INCOMPLETE', intent=intent, arms=[], valid=False, errors=[],
        production_gain_claim=False, causal_live_cost_claim=False)
    try:
        for index, version in enumerate(ORDER):
            require(time.monotonic() < hard_deadline, 'Original observational deadline; no extension')
            require(read_inputs() == sources, 'Pinned inputs changed between arms')
            runtime_identity()
            arm = Harness(F, sources, version, args.hz, args.ticks,
                round(args.max_lateness_ms * 1e6), hard_deadline).run()
            arm['index'] = index + 1
            report['arms'].append(arm)
            require(read_inputs() == sources, 'Pinned inputs changed after arm')
            require(arm['threads_still_alive'] == 0, 'Unfinished synthetic threads; no further arm')
            require(arm['arm_error'] is None, 'Failed arm preserved; no further arm')
            require(arm['census_ok'] and arm['timing_ok'] and arm['unexpected_operation_count'] == 0,
                'Invalid original arm preserved; stop without retry, extension or selective discard')
        anchor = equality_view(report['arms'][0])
        equal = all(equality_view(arm) == anchor for arm in report['arms'])
        valid = equal and all(arm['census_ok'] and arm['timing_ok'] and
            arm['unexpected_operation_count'] == 0 for arm in report['arms'])
        report.update(valid=bool(valid), exact_exposure_state_sink_equality=equal,
            status='VALID_PACED_SYNTHETIC_DIFFERENTIAL' if valid else 'INVALID_TIMING_OR_SYNTHETIC_EQUIVALENCE')
        if valid:
            pairs = []
            for left,right in ((0,1),(2,3),(4,5),(6,7)):
                a,b = report['arms'][left],report['arms'][right]
                if a['version'] == 'B':
                    a,b = b,a
                count = WORKERS * args.ticks
                pairs.append(dict(A_index=a['index'], B_index=b['index'],
                    A_process_cpu_ns_per_data_frame=a['measured']['process_cpu_ns']/count,
                    B_process_cpu_ns_per_data_frame=b['measured']['process_cpu_ns']/count,
                    B_over_A_process_cpu=b['measured']['process_cpu_ns']/a['measured']['process_cpu_ns']))
            report.update(paired_synthetic_process_CPU=pairs,
                median_B_over_A_process_CPU=statistics.median(p['B_over_A_process_cpu'] for p in pairs))
    except BaseException as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error)[:1000])
        report.update(valid=False,status='INVALID_ORIGINAL_ATTEMPT_PRESERVED')
    try:
        report['runtime_after_attempt'] = runtime_identity()
    except BaseException as error:
        report['runtime_after_attempt'] = None
        report['errors'].append(type(error).__name__ + ': ' + str(error)[:1000])
        report.update(valid=False, status='INVALID_RUNTIME_ATTESTATION')
    report['measurement_scope'] = dict(
        process_CPU='Entire benchmark process during actual coordinator data timestamps, including pacing, shared real locks, Python fakes, bounded hashes/counters and coordinator overhead. Not isolated helper CPU.',
        wall='Fixed-rate admitted workload; paced wall per frame is not a throughput gain metric. Service elapsed includes full body through next recv entry; no GPU/kernel timing.',
        allocations='getallocatedblocks net process-wide delta only, not allocation count/bytes/peak. maxrss is cumulative process high-water, not arm-local.',
        equivalence='Exact per-client sink hashes/counts, virtual-clock client/stash hashes and helper census. Helper instance monotonic origin is recorded but not an action/state comparison field.',
        unsupported='No real binary parser/NumPy/inference/reward kernels, replay consumer/banks, GameJournal, sockets/OS I/O, preview/HUD/debug or producer workload. Fake overhead/shared-lock contention may dominate; no production gain or live6% attribution.')
    receipt = publish(args.output/'result.json', report)
    print(json.dumps(dict(status=report['status'],valid=report['valid'],arms=len(report['arms']),result=receipt)))
    return 0 if report['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
