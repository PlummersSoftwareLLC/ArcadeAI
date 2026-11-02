"""Prospective, actual-source episode fixtures. Root alone may run these.

Real temporary GameJournal appends/fsyncs and SHA-bound server/NStep/FIFO AST
are exercised. Wire parsing, reward values, inference, physical ownership and
bank admission are explicit synthetic collaborators. No real process, socket,
model/checkpoint, service, GPU or production module is imported or controlled.
The frame harness omits reporting and inference while retaining the exact
ingest/journal/replay/terminal suites in their production order.
"""
import ast
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import statistics
import struct
import tempfile
import threading
import time
from types import SimpleNamespace
from typing import Any, Deque, List, Optional, Tuple
import unittest

import numpy as np


HERE = Path(__file__).resolve().parent
GAME = HERE.parents[4]
# Author-frozen actual sources. This file is staged only; Root owns execution.
SOURCES = {
    'server': (HERE/'socket_server_continuous_train_candidate_v1.py',
               '49d24b2fe8d0051eff0512b1baea3bdf2c04c00b58e0f212cfe73f7ce6af4987'),
    'journal': (HERE/'game_journal_continuous_train_candidate_v1.py',
                '6aa78cb40434793853d17a1032cc6454ac86b0168828848d9d390336ba8678f0'),
    'nstep': (GAME/'Scripts/dqn/nstep_buffer.py',
              'e46f03e9a626b3a24dea702344b0bbf050f1fdc5af672fc8fc9d18e6afef74c1'),
    'frozen': (GAME/'Scripts/dqn/frozen_evaluation.py',
               '65430d472231e3a1bf0f794cc65603bf5e41c495c446d9a4bab59ad0d3a3a669'),
}


def checked_tree(role):
    path, expected = SOURCES[role]
    if not isinstance(expected, str) or len(expected) != 64:
        raise RuntimeError('Unfrozen episode fixture source: '+role)
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, role
    return ast.parse(raw), str(path)


def compile_nodes(nodes, ns, filename):
    code = ast.Module(body=nodes, type_ignores=[])
    exec(compile(ast.fix_missing_locations(code), filename, 'exec'), ns)


def function(name, arguments, statements):
    # Parsing a signature supplies the interpreter's precise AST argument ABI.
    result = ast.parse('def '+name+'('+arguments+'):\n    pass\n').body[0]
    result.body = statements
    return result


class Metrics:
    measurement_active = False
    measurement_generation = 0
    measurement_frame_count = 0
    ratchet_frozen = False
    epsilon = 0.02
    expert_ratio = 0.0
    override_epsilon = False
    frame_count = learner_frame_count = total_training_steps = 0
    def __getattr__(self, name):
        if name.startswith(('add_', 'note_', 'ratchet_note_')):
            return lambda *args, **kwargs: None
        raise AttributeError(name)


class ReplayAgent:
    """Synthetic ring append, retaining every actual FIFO consumer call."""
    optimized_samples = 0
    def __init__(self):
        self.rows = []
    def step(self, *args, **kwargs):
        self.rows.append((args, kwargs))
        return len(self.rows)-1


class Socket:
    def __init__(self):
        self.messages = []
    def sendall(self, value):
        self.messages.append(value)


def build_actual_sources():
    metrics = Metrics()
    ns = dict(ast=ast, deque=deque, dataclass=dataclass, datetime=datetime,
        timezone=timezone, hashlib=hashlib, json=json, math=math, os=os,
        Path=Path, queue=queue, statistics=statistics, struct=struct,
        threading=threading, time=time, Any=Any, Deque=Deque, List=List,
        Optional=Optional, Tuple=Tuple, np=np, metrics=metrics)
    cfg = SimpleNamespace(n_step=3, gamma=0.9, frame_stack=3,
        lives_start=3, client_stall_timeout_s=0, eval_epsilon=0.0,
        epsilon_hard_floor=0.02, wave_clear_training_terminal=False)
    ns['RL_CONFIG'] = cfg
    ns['game_settings'] = SimpleNamespace(epsilon_pct=-1, expert_pct=-1,
        difficulty=5, snapshot=lambda: dict(auto_curriculum=False,
                                          start_advanced=False, start_level_min=1))
    ns.update(STRATIFIED_TRAINING_STARTS=False, _MAX_SCORE_JUMP=250_000,
        _last_implausible_warn_t=0.0, _SRC_NONE=0,
        slice_model_state=lambda value: np.asarray(value, dtype=np.float32),
        _shape_transition_reward=lambda *args, **kwargs: (1.0, 1.0, 0.0, 0.0, 0),
        _transition_interest_score=lambda *args, **kwargs: 0.0,
        _wave_advanced=lambda *args, **kwargs: False,
        _active_group_count=lambda *args, **kwargs: 0,
        combine_action=lambda move, fire: int(move)*9+int(fire),
        split_joint_action=lambda action: divmod(int(action), 9),
        print=lambda *args, **kwargs: None)
    for name in ('add_episode_to_dqn100k_window', 'add_episode_to_dqn1m_window',
                 'add_episode_to_dqn5m_window', 'add_episode_to_dqn_perframe_window',
                 'add_episode_to_total_windows', 'add_episode_to_eplen_window'):
        ns[name] = lambda *args, **kwargs: None

    tree, filename = checked_tree('nstep')
    compile_nodes([n for n in tree.body if isinstance(n, ast.ClassDef)], ns, filename)
    tree, filename = checked_tree('frozen')
    compile_nodes([n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == 'reset_client_replay_segment'], ns, filename)
    tree, filename = checked_tree('journal')
    compile_nodes([n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))], ns, filename)
    tree, filename = checked_tree('server')
    compile_nodes([n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == '_continuous_play_score_dip'], ns, filename)
    server = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
    wanted = {'_init_client', '_sync_client_count_locked', '_is_eval_client',
        '_reset_new_game_replay_segment', '_stack_model_state', '_replay_writable',
        '_journal_context', '_journal_observe', '_confirmed_journal_boundary', '_pack_action'}
    cls = ast.ClassDef(name='ActualServerMethods', bases=[], keywords=[],
        body=[n for n in server.body if isinstance(n, ast.FunctionDef) and n.name in wanted],
        decorator_list=[])
    compile_nodes([cls], ns, filename)
    replay = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AsyncReplayBuffer')
    wanted = {'_enqueue_preserving', 'step_async', 'boost_pre_death',
              'boost_elite_episode', 'reset_client_async', '_consume'}
    cls = ast.ClassDef(name='ActualReplayMethods', bases=[], keywords=[],
        body=[n for n in replay.body if isinstance(n, ast.FunctionDef) and n.name in wanted],
        decorator_list=[])
    compile_nodes([cls], ns, filename)

    handle = next(n for n in server.body if isinstance(n, ast.FunctionDef) and n.name == 'handle_client')
    loop = next(n for n in ast.walk(handle) if isinstance(n, ast.While)
                and any(isinstance(x, ast.Assign) and ast.unparse(x.targets[0]) == '_verdict'
                        for x in n.body))
    children = loop.body
    def first(predicate):
        values = [i for i, n in enumerate(children) if predicate(n)]
        assert len(values) == 1, values
        return values[0]
    ingest = first(lambda n: isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == '_verdict')
    journal_end = first(lambda n: isinstance(n, ast.If)
        and ast.unparse(n.test) == "cs.pop('_journal_boundary_reset', False)")
    previous = first(lambda n: isinstance(n, ast.If)
        and ast.unparse(n.test).startswith("cs.get('last_state') is not None and cs.get('last_action')"))
    terminal = first(lambda n: isinstance(n, ast.If) and ast.unparse(n.test) == 'frame.done')
    was_done = first(lambda n: isinstance(n, ast.If) and ast.unparse(n.test) == "cs.get('was_done')")
    inactive = first(lambda n: isinstance(n, ast.If) and ast.unparse(n.test) == 'not frame.player_alive')
    action_start = first(lambda n: isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) == "cs['last_state']")
    action_end = first(lambda n: isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) == "cs['prev_action_source']")
    assert ingest < journal_end < previous < terminal < was_done < inactive < action_start < action_end
    setup = ast.parse('''_response_trace = None
_gap_connection = None
_gap_ticket = None
''').body
    select = ast.parse('''mv_idx, effective_fire = 8, 8
action_source = 'eval' if cs['eval_only'] else 'dqn'
''').body
    # Exact suites, including continue/break behavior, execute once. The
    # synthetic action replaces model inference, not any episode bookkeeping.
    body = (children[ingest:journal_end+1] + [children[previous], children[terminal],
        children[was_done], children[inactive]] + select + children[action_start:action_end+1])
    iteration = ast.For(target=ast.Name(id='_fixture_once', ctx=ast.Store()),
        iter=ast.Tuple(elts=[ast.Constant(None)], ctx=ast.Load()), body=body, orelse=[])
    compile_nodes([function('actual_frame_suites', 'self,cid,frame,sock',
        setup+[iteration]+ast.parse('return locals()').body)], ns, filename)
    return ns, metrics


class Harness:
    def __init__(self, directory, *, eval_only=False, continuous=True):
        self.ns, self.metrics = build_actual_sources()
        self.cid, self.slot, self.tick = 11, 83, 0
        # Labels only: no /proc observation or real process is claimed.
        self.synthetic_pid, self.synthetic_birth = 12345, 67890
        self.producer = threading.current_thread()
        self.agent = ReplayAgent()
        self.buffer = self.ns['ActualReplayMethods']()
        self.buffer.running = True
        self.buffer.batch_size = 1
        self.buffer._client_indices, self.buffer._episode_indices = {}, {}
        self.buffer._lookback = 100
        self.buffer.agent = self.agent
        self.buffer.boosts, self.buffer.elites = [], []
        self.buffer._do_boost = lambda cid: self.buffer.boosts.append(
            (cid, tuple(self.buffer._client_indices.get(cid, ()))))
        self.buffer._do_elite_episode_boost = lambda cid, *args: self.buffer.elites.append(
            (cid, args, tuple(self.buffer._episode_indices.get(cid, ()))))
        outer = self.buffer
        class FiniteQueue(queue.Queue):
            def get(self, block=True, timeout=None):
                try:
                    return super().get(block=False)
                except queue.Empty:
                    outer.running = False
                    raise
        self.buffer.queue = FiniteQueue()
        self.server = self.ns['ActualServerMethods']()
        s = self.server
        s.metrics, s.agent, s.async_buffer = self.metrics, self.agent, self.buffer
        s.client_states, s.clients, s.client_lock = {}, {}, threading.Lock()
        s._eval_override, s._unwrap_stash, s._game_uid_seq = {self.cid: eval_only}, {}, 0
        s.replay_enabled, s.continuous_training_mode = True, continuous
        s.game_boundary_diagnostics = False
        s._journal_last_error = 0.0
        s._journal_experiment_label = lambda: 'continuous-fixture'
        s._sync_measurement_boundary = lambda *args: False
        s._preview_flags_for_client = lambda cid: (False, False)
        s._fail_inference_only = lambda reason: (_ for _ in ()).throw(AssertionError(reason))
        def owner(cid, cs):
            assert threading.current_thread() is self.producer
            assert cid == self.cid and s.client_states[cid] is cs
        s._require_connection_producer = owner
        s._rejected_gaps = SimpleNamespace(event=lambda *args, **kwargs: None)
        s._init_client(self.cid)
        self.cs = s.client_states[self.cid]
        self.cs['client_slot'] = self.slot
        self.cs['proto_v2'] = True
        self.connected_since = self.cs['connected_since']
        self.journal = self.ns['GameJournal'](directory, lives_start=3,
            retire_after_game=True, continuous_train=continuous)
        s.game_journal = self.journal
        self.sock = Socket()
        self.boundary_evidence = []
        real_boundary = s._confirmed_journal_boundary
        def boundary(cid, frame, cs, reason, row):
            # The entire old result is present on disk before UID mutation.
            raw = self.journal.games_path.read_bytes().splitlines()[-1]
            assert raw == json.dumps(row, allow_nan=False, separators=(',', ':')).encode()
            assert json.loads(raw) == row
            before = cs['game_uid']
            real_boundary(cid, frame, cs, reason, row)
            self.boundary_evidence.append((before, cs['game_uid'], dict(row), raw))
        s._confirmed_journal_boundary = boundary

    def frame(self, *, score=0, alive=True, done=False, start=False,
              lives=3, marker=1, wave=1):
        self.tick += 1
        self.buffer.running = True
        frame = SimpleNamespace(game_score=score, level_number=wave,
            player_alive=alive, done=done, start_pressed=start, lives=lives,
            num_lasers=max(0, lives), state=np.array([marker, self.tick], dtype=np.float32))
        result = self.ns['actual_frame_suites'](self.server, self.cid, frame, self.sock)
        assert self.cs['frames'] == self.tick
        assert self.cs['connected_since'] == self.connected_since
        assert self.server.client_states[self.cid] is self.cs
        self.drain()
        return result

    def drain(self):
        self.buffer.running = True
        self.buffer._consume()
        self.buffer.running = True

    def rows(self, name='games.jsonl'):
        path = self.journal.directory/name
        return [] if not path.exists() else [json.loads(line) for line in path.read_text().splitlines()]

    def assert_replay_stays_in_one_game(self, test):
        test.assertTrue(self.agent.rows)
        for args, kwargs in self.agent.rows:
            state, _, _, next_state, _ = args
            markers = set(np.concatenate((state[::2], next_state[::2])).astype(int))
            test.assertEqual(len(markers), 1)
            test.assertEqual(kwargs['actor'], 'eval' if self.cs['eval_only'] else 'dqn')
            test.assertIn(kwargs['horizon'], (1, 2, 3))

    def zero_game(self, marker, *, already_started=False):
        if not already_started:
            self.frame(start=True, marker=marker)
        for life in range(3):
            self.frame(marker=marker, lives=3-life)
            self.frame(marker=marker, lives=2-life, alive=False, done=True)
            self.frame(marker=marker, lives=2-life, alive=False,
                       start=(life == 2))


class Tests(unittest.TestCase):
    def test_positive_games_same_connection_mint_once_flush_terminal_and_keep_raw_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            h = Harness(directory)
            h.frame(start=True, marker=1)
            h.frame(score=100, marker=1)
            h.frame(score=200, marker=1, alive=False, done=True, lives=0)
            self.assertFalse(h.cs['nstep']._deque)
            self.assertEqual(h.cs['deaths_this_game'], 1)
            old_end = len(h.agent.rows)
            self.assertEqual(old_end, 2)
            self.assertTrue(all(row[0][-1] for row in h.agent.rows))
            h.frame(score=200, marker=1, alive=False, start=True, lives=0)
            h.frame(score=0, marker=2, start=True)
            self.assertEqual(h.cs['game_uid'], 2)
            self.assertEqual(h.cs['deaths_this_game'], 0)
            self.assertFalse(h.cs['nstep']._deque)
            self.assertEqual(len(h.agent.rows), old_end)  # first new frame is not replay
            self.assertEqual(h.buffer._episode_indices.get(h.cid), None)
            np.testing.assert_array_equal(h.cs['last_state'][::2], [2, 2, 2])
            h.frame(score=300, marker=2)
            h.frame(score=400, marker=2, alive=False, done=True, lives=0)
            h.frame(score=400, marker=2, alive=False, start=True, lives=0)
            h.frame(score=0, marker=3, start=True)
            rows = [row for row in h.rows() if row['eligible']]
            self.assertEqual([(r['game_uid'], r['score'], r['boundary_reason'], r['deaths'])
                              for r in rows], [(1, 200, 'score_reset', 1), (2, 400, 'score_reset', 1)])
            self.assertEqual(len({r['journal_game_id'] for r in rows}), 2)
            self.assertTrue(all(r['complete'] and r['known_start'] and not r['eval_only'] for r in rows))
            self.assertEqual(h.rows('completed_clients.jsonl'), [])
            self.assertFalse(h.cs['retire_after_game'])
            self.assertEqual(h.boundary_evidence, [])  # positive classifier owns UID
            self.assertEqual([r['game_uid'] for r in h.rows('lives.jsonl')], [1, 2])
            self.assertEqual([e[1][-1] for e in h.buffer.elites], [1, 2])
            self.assertTrue(all(len(e[2]) == 2 for e in h.buffer.elites))
            h.assert_replay_stays_in_one_game(self)

    def test_all_zero_games_callback_precedes_begin_life_and_first_eligible_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            h = Harness(directory)
            h.zero_game(1)
            self.assertEqual(h.cs['game_uid'], 1)
            self.assertEqual(h.cs['deaths_this_game'], 3)
            old_end = len(h.agent.rows)
            h.frame(marker=2, start=True)
            self.assertEqual((h.cs['game_uid'], h.cs['deaths_this_game']), (2, 0))
            self.assertEqual(h.journal.active[h.cid]['game_uid'], 2)
            self.assertEqual(h.journal.active[h.cid]['observed_frames'], 1)
            self.assertEqual(len(h.agent.rows), old_end)
            self.assertFalse(h.cs['nstep']._deque)
            self.assertNotIn(h.cid, h.buffer._episode_indices)
            np.testing.assert_array_equal(h.cs['last_state'][::2], [2, 2, 2])
            h.zero_game(2, already_started=True)
            h.frame(marker=3, start=True)
            rows = [r for r in h.rows() if r['eligible']]
            self.assertEqual([(r['game_uid'], r['score'], r['deaths'], r['boundary_reason'])
                for r in rows], [(1, 0, 3, 'zero_score_restart'), (2, 0, 3, 'zero_score_restart')])
            self.assertEqual([(b[0], b[1]) for b in h.boundary_evidence], [(1, 2), (2, 3)])
            self.assertEqual([r['game_uid'] for r in h.rows('lives.jsonl')], [1, 1, 1, 2, 2, 2])
            self.assertEqual([r['life'] for r in h.rows('lives.jsonl')], [1, 2, 3, 1, 2, 3])
            self.assertEqual(h.rows('completed_clients.jsonl'), [])
            self.assertFalse(h.cs['retire_after_game'])
            h.assert_replay_stays_in_one_game(self)

    def test_confirmed_zero_boundary_discards_uncertain_suffix_without_inventing_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            h = Harness(directory)
            h.zero_game(1)
            h.cs['last_state'] = np.array([99, 0]*3, dtype=np.float32)
            h.cs['last_action'], h.cs['ep_frames'] = (8, 8), 9
            h.cs['frame_history'].append(np.array([99, 0], dtype=np.float32))
            h.cs['nstep'].add(h.cs['last_state'], 80, 7.0, h.cs['last_state'], False)
            count = len(h.agent.rows)
            h.frame(marker=2, start=True)
            self.assertEqual(len(h.agent.rows), count)
            self.assertTrue(h.cs['replay_episode_partial'])
            self.assertFalse(h.cs['nstep']._deque)
            np.testing.assert_array_equal(h.cs['last_state'][::2], [2, 2, 2])
            self.assertNotIn(h.cid, h.buffer._episode_indices)
            self.assertEqual(h.cs['ep_frames'], 0)

    def test_fifo_reset_separates_exact_old_and_new_episode_indices_without_clearing_ring(self):
        with tempfile.TemporaryDirectory() as directory:
            h = Harness(directory)
            s = np.array([1, 0]*3, dtype=np.float32)
            h.buffer.step_async(s, (8, 8), 1.0, s, False, client_id=h.cid,
                                actor='dqn', horizon=1)
            h.buffer.boost_elite_episode(h.cid, 20, 1, 1.0, 1, game_uid=1)
            ack = h.buffer.reset_client_async(h.cid)
            t = np.array([2, 0]*3, dtype=np.float32)
            h.buffer.step_async(t, (8, 8), 1.0, t, False, client_id=h.cid,
                                actor='dqn', horizon=1)
            self.assertFalse(ack.is_set())
            self.assertEqual([item[0] for item in h.buffer.queue.queue],
                             ['step', 'elite', 'reset_client', 'step'])
            h.drain()
            self.assertTrue(ack.is_set())
            self.assertEqual(len(h.agent.rows), 2)
            self.assertEqual(h.buffer.elites[0][2], (0,))
            self.assertEqual(tuple(h.buffer._client_indices[h.cid]), (1,))
            self.assertEqual(tuple(h.buffer._episode_indices[h.cid]), (1,))

    def test_retirement_is_eval_only_in_mode_and_both_zero_and_positive_stay_durable(self):
        for zero in (False, True):
            for continuous, eval_only in ((True, False), (True, True), (False, False)):
                with self.subTest(zero=zero, continuous=continuous, eval_only=eval_only):
                    with tempfile.TemporaryDirectory() as directory:
                        h = Harness(directory, eval_only=eval_only, continuous=continuous)
                        if zero:
                            h.zero_game(1)
                            h.frame(marker=2, start=True)
                        else:
                            h.frame(marker=1, start=True)
                            h.frame(marker=1, score=100, alive=False, done=True, lives=0)
                            h.frame(marker=2, score=0, start=True)
                        completed = [r for r in h.rows() if r['eligible']]
                        self.assertEqual(len(completed), 1)
                        retire = not continuous or eval_only
                        self.assertEqual(len(h.rows('completed_clients.jsonl')), int(retire))
                        self.assertEqual(h.cs['retire_after_game'], retire)
                        action = h.server._pack_action(0, 0, 1, h.cid)
                        self.assertEqual(bool(action[2] & 0x20), retire)
                        if retire:
                            self.assertEqual(h.rows('completed_clients.jsonl')[0], completed[0])
                        # TRAIN action never leaks a stale retirement flag in mode.
                        if continuous and not eval_only:
                            h.cs['retire_after_game'] = True
                            self.assertFalse(h.server._pack_action(0, 0, 1, h.cid)[2] & 0x20)

    def test_confirmed_callback_rejects_wrong_row_or_foreign_connection_before_uid_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            h = Harness(directory)
            h.zero_game(1)
            row = dict(boundary_reason='zero_score_restart', complete=True,
                client_id=h.cid, client_slot=h.slot, game_uid=1, score=0)
            frame = SimpleNamespace(game_score=0)
            actual = h.ns['ActualServerMethods']._confirmed_journal_boundary
            for field, value in [('boundary_reason', 'score_reset'), ('complete', False),
                ('client_id', 12), ('client_slot', 84), ('game_uid', 2), ('score', 1)]:
                with self.subTest(field=field):
                    before = (h.cs['game_uid'], h.cs['deaths_this_game'], h.server._game_uid_seq)
                    with self.assertRaises(RuntimeError):
                        actual(h.server, h.cid, frame, h.cs, 'zero_score_restart', dict(row, **{field:value}))
                    self.assertEqual(before, (h.cs['game_uid'], h.cs['deaths_this_game'], h.server._game_uid_seq))
            with self.assertRaises(AssertionError):
                actual(h.server, h.cid, frame, dict(h.cs), 'zero_score_restart', row)


if __name__ == '__main__':
    unittest.main()
