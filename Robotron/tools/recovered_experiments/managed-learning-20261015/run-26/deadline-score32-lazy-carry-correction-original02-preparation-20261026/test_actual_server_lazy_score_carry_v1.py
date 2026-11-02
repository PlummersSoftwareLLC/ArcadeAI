"""Actual frozen server init/accepted ingest -> REAL proxy/journal -> NEW hooks.

The exact server AST suites avoid importing Torch/numpy/config. Only sockets,
ROM observations, policy and the replay-disabled nstep collaborator are fake.
No previous test methods, live health, model bodies, MAME, GPU or services run.
"""
import ast
from collections import deque
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'deadline-score60min-protocol-original01-preparation-20261026'
GAME = HERE.parents[3]
SERVER = GAME / 'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/socket_server.py'
NEW_HOOK_SHA256 = 'e5af51da649f64bb6749f817112414b357a0cb72a461e7639e2dfd3162438675'


def load(name, path, expected=None):
    if expected: assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); sys.modules[name] = value
    spec.loader.exec_module(value); return value


defs = load('_lazycarry_frozen_integration_fixture_defs_ONLY', OLD / 'test_deadline32_native_integration_v1.py',
            '33cc8a43ee895aeea6462258cb15ed3a5ca931a571238497ae3fcf477d7f2504')


def actual_server_suites(metrics):
    raw = SERVER.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'b552b2e83a9cc10cf7e4125cef22f571abe9189bd2ad3e63c6f48aa7df0e4516'
    tree = ast.parse(raw)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    handler = methods['handle_client']
    unwrap = next(n for n in ast.walk(handler) if isinstance(n, ast.With) and any(
        isinstance(a, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_cs0' for t in a.targets)
        for a in n.body))
    accepted = next(n for n in ast.walk(handler) if isinstance(n, ast.With) and any(
        isinstance(a, ast.AugAssign) and isinstance(a.target, ast.Subscript)
        and isinstance(a.target.value, ast.Name) and a.target.value.id == 'cs'
        and isinstance(a.target.slice, ast.Constant) and a.target.slice.value == 'frames'
        for a in n.body))
    parent_body = next(n.body for n in ast.walk(handler) if hasattr(n, 'body') and unwrap in n.body)
    index = parent_body.index(unwrap); initializers = parent_body[index - 5:index]
    assert [n.targets[0].id for n in initializers] == ['_verdict', '_wrap_note', '_prev_for_log', '_is_new_game', '_boundary_inputs']
    fn = ast.parse('def accepted_ingest(self,cid,frame):\n _gap_connection=None\n for _once in (0,):\n  pass\n return dict(verdict=_verdict,frame=frame,new_game=_is_new_game,boundary_inputs=_boundary_inputs)').body[0]
    fn.body[1].body = deepcopy(initializers) + [deepcopy(unwrap)] + ast.parse(
        "if _verdict != 'accept':\n return dict(verdict=_verdict,frame=frame,new_game=False,boundary_inputs=_boundary_inputs)").body + [deepcopy(accepted)]
    selected = [deepcopy(methods[name]) for name in ('_init_client', '_measurement_snapshot', '_sync_measurement_boundary', '_journal_observe')]
    for method in selected: method.decorator_list = []
    dip = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_continuous_play_score_dip')
    max_jump = next(n for n in tree.body if isinstance(n, ast.Assign) and
                    any(isinstance(t, ast.Name) and t.id == '_MAX_SCORE_JUMP' for t in n.targets))
    frozen = ast.parse((SERVER.parent / 'frozen_evaluation.py').read_bytes())
    reset = next(n for n in frozen.body if isinstance(n, ast.FunctionDef) and n.name == 'reset_client_replay_segment')
    namespace = dict(time=time, deque=deque, metrics=metrics,
        RL_CONFIG=SimpleNamespace(n_step=3, gamma=.995, frame_stack=4),
        NStepReplayBuffer=lambda **kwargs: SimpleNamespace(reset=lambda: None))
    compiled = ast.Module(body=[deepcopy(max_jump), deepcopy(dip), deepcopy(reset), *selected, fn], type_ignores=[])
    # Every executed ingest lock suite and initializer is copied exactly.
    assert ast.dump(fn.body[1].body[5], include_attributes=False) == ast.dump(unwrap, include_attributes=False)
    assert ast.dump(fn.body[1].body[-1], include_attributes=False) == ast.dump(accepted, include_attributes=False)
    exec(compile(ast.fix_missing_locations(compiled), str(SERVER) + '::EXACT-init-and-accepted-ingest-CPU', 'exec'), namespace)
    return namespace


class Tests(unittest.TestCase):
    def fixture(self):
        original_components = defs.actual_components
        def components():
            values = original_components(); selected = defs.h.pin(HERE / 'deadline_proxy_hooks_v2.py')
            assert selected['sha256'] == NEW_HOOK_SHA256
            values['hooks'] = selected; return values
        owner = defs.Tests(); self.addCleanup(owner.doCleanups)
        with patch.object(defs, 'actual_components', side_effect=components):
            f, modules, recorder, gate, registry, policy = owner.fixture()
        self.assertEqual(Path(modules['hooks'].__file__).resolve(), HERE / 'deadline_proxy_hooks_v2.py')
        self.assertEqual(hashlib.sha256(Path(modules['hooks'].__file__).read_bytes()).hexdigest(), NEW_HOOK_SHA256)
        api = actual_server_suites(f.fleet.metrics)
        f.server._is_eval_client = lambda _: True
        f.server._sync_client_count_locked = lambda: None
        f.server.replay_enabled = False; f.server.async_buffer = None
        f.server.game_boundary_diagnostics = False; f.server._unwrap_stash = {}; f.server._game_uid_seq = 4096
        f.server._rejected_gaps = SimpleNamespace(event=lambda *args, **kwargs: None)
        f.server._measurement_snapshot = api['_measurement_snapshot']
        f.server._journal_experiment_label = lambda: f.fleet.policy['experiment']
        f.server._fail_inference_only = lambda error: setattr(f.server, 'inference_only_error', error)
        api['_init_client'](f.server, 96)
        f.cs = f.server.client_states[96]; f.cs['client_slot'] = 4096  # Actual forced-slot handshake effect only.
        f.fleet.states[4096] = f.cs
        self.assertNotIn('score_offset', f.cs); self.assertIsNone(f.cs.get('raw_score_prev'))
        f.frame = defs.definitions.bridge_defs.defs.frame(game_score=0, level_number=0, player_alive=False, num_lasers=0)
        original_step = f.step
        def step(**changes):
            frame = f.frame
            header = modules['clock_codec'].V2_HEADER.pack(1890, 0., 0., int(frame.done), int(frame.game_score),
                int(frame.player_alive), 0, int(frame.start_pressed), 20000, int(frame.num_lasers), int(frame.level_number), int(frame.lives))
            payload = header + bytes(1890 * 4) + bytes(4)
            with patch.object(defs.definitions.bridge_defs, 'PAYLOAD', payload): return original_step(**changes)
        f.step = step
        class Origin:
            sent = None
            def __init__(self): self.sent = []; self.buffer = b''
            def settimeout(self, value): pass
            def setsockopt(self, *args): pass
            def sendall(self, raw):
                if len(raw) == 2: return
                self.sent.append(raw)
                fields = modules['clock_codec'].V2_HEADER.unpack_from(raw, 4)
                frame = deepcopy(f.frame)
                frame.done, frame.game_score, frame.player_alive, frame.start_pressed = bool(fields[3]), fields[4], bool(fields[5]), bool(fields[7])
                frame.num_lasers, frame.level_number, frame.lives = fields[9], fields[10], fields[11]
                accepted = api['accepted_ingest'](f.server, 96, frame)
                if accepted['verdict'] != 'accept': raise ValueError('Fixture frame unexpectedly rejected')
                api['_sync_measurement_boundary'](f.server, 96, f.cs, frame.game_score)
                api['_journal_observe'](f.server, 96, frame, f.cs, accepted['new_game'], boundary_inputs=accepted['boundary_inputs'])
                self.buffer = defs.definitions.bridge_defs.ACTION
            def recv(self, count):
                count = min(count, 2); value, self.buffer = self.buffer[:count], self.buffer[count:]; return value
        f.origin = Origin()
        return f, modules, recorder, gate, registry, policy

    def test_actual_initial_state_and_certified_INIT_never_invent_carry_or_raw_score(self):
        f, modules, recorder, gate, registry, policy = self.fixture()
        observed = []; original = modules['hooks'].completed_exchange_sample
        def checked(proxy, *args, **kwargs):
            self.assertIsNotNone(proxy.handoff); observed.append(proxy.sequence); return original(proxy, *args, **kwargs)
        with patch.object(modules['hooks'], 'completed_exchange_sample', side_effect=checked): f.prefix(); f.step()
        self.assertEqual(min(observed), f.proxy.handoff_sequence)
        self.assertNotIn('score_offset', f.cs); self.assertEqual(f.cs['raw_score_prev'], 0)
        witness = recorder._scores[4096]['score_witness']; origin = witness['source_witness']['origin_state']
        self.assertEqual((witness['full_score'], witness['effective_raw_score'], witness['score_offset']), (0, 0, 0))
        self.assertIs(origin['actual_score_offset_present'], False)
        self.assertEqual(f.fleet.journal.measurement_games[f.proxy.handoff['journal_game_id']]['score'], 0)
        old = load('_original_failed_hooks_negative_control', OLD / 'deadline_proxy_hooks_v1.py',
                   'e1ab38d4cf7632eb8c4c0940d7a75075c492eb097b4a470d38e0c9d22e883fce')
        with self.assertRaisesRegex(KeyError, 'score_offset'): old._client_snapshot(f.server, 96)
        self.assertEqual(gate.inflight, {})

    def test_actual_accepted_unwrap_path_allocates_first_100M_carry_and_matches_journal(self):
        f, modules, recorder, gate, registry, policy = self.fixture(); f.prefix(); f.step()
        for raw_score in [*range(250_000, 99_999_975, 250_000), 99_999_975]:
            f.frame.game_score = raw_score; f.step(score_hex=f'{raw_score:08d}')
        self.assertNotIn('score_offset', f.cs)
        f.frame.game_score = 25; f.step(score_hex='00000025')
        witness = recorder._scores[4096]['score_witness']
        self.assertEqual((f.cs['raw_score_prev'], f.cs['score_offset'], f.cs['game_score']), (25, 100_000_000, 100_000_025))
        self.assertEqual((witness['raw_wire_score'], witness['full_score']), (25, 100_000_025))
        self.assertIs(witness['source_witness']['origin_state']['actual_score_offset_present'], True)
        game = f.fleet.journal.measurement_games[f.proxy.deadline_member['journal_game_id']]
        self.assertEqual(game['score'], 100_000_025); self.assertFalse(game['finished'])
        self.assertEqual(gate.inflight, {})

    def test_missing_required_origin_and_present_invalid_carry_are_rejected(self):
        f, modules, recorder, gate, registry, policy = self.fixture(); f.prefix(); f.step()
        for key in ('raw_score_prev', 'game_score', 'frames', 'measurement_generation'):
            value = f.cs.pop(key)
            with self.subTest(missing=key), self.assertRaises(KeyError): modules['hooks']._client_snapshot(f.server, 96)
            f.cs[key] = value
        for bad in (None, -1, 0.0, False):
            f.cs['score_offset'] = bad
            with self.subTest(carry=bad), self.assertRaises(ValueError): modules['hooks']._client_snapshot(f.server, 96)
        f.cs.pop('score_offset')
        self.assertEqual(recorder._scores[4096]['score'], 0)


if __name__ == '__main__': unittest.main(verbosity=2)
