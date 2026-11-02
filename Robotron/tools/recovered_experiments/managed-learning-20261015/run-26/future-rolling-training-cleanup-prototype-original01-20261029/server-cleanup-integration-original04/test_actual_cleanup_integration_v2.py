"""Unexecuted prospective integration fixtures. Root alone operates CPU scopes.

Exact source AST methods run only with a temporary real GameJournal, owned
synthetic threads/Timers, fake actor/socket and no model/production imports.
The actual handler finally and actual HTTP GET branch are extracted verbatim.
"""
import ast
from collections import deque
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import queue
import socket
import tempfile
import threading
import time
import types
import unittest
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
P = HERE.parent
SOURCES = {
    'server': (HERE/'socket_server_cleanup_receipts_candidate_v4.py', '33e581c2cebd0aaefa488ec09ec26fd9662817975c055c2433617cebc54b4525'),
    'helper': (HERE/'connection_cleanup_receipts_candidate_v3.py', '555923d6b24cbc9950be22a8dda4321cdea4b3e5eacde2036232860b3f784803'),
    'journal': (P/'game_journal_parent.py', '4c68e5d9669047abb6cf78cf4354fe8322ee1dd83871439fb19e537b6c31c3ba'),
    'dashboard': (P/'server-cleanup-integration-original03/metrics_dashboard_cleanup_getter_candidate_v1.py', '61967c5469e1479f210ed21759fcb24d2a6054606830616fb2318b942e4ac81f'),
}


def raw(role):
    path, expected = SOURCES[role]
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected
    return data


def definitions(role):
    path = SOURCES[role][0]
    raw(role)
    spec = importlib.util.spec_from_file_location('_cleanup_fixture_'+role, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def node_class(role, name):
    return next(n for n in ast.parse(raw(role)).body
                if isinstance(n, ast.ClassDef) and n.name == name)


def compile_body(body, name, namespace):
    tree = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name=name,
        bases=[], keywords=[], body=copy.deepcopy(body), decorator_list=[], type_params=[])], type_ignores=[]))
    exec(compile(tree, str(SOURCES['server'][0]), 'exec'), namespace)
    return namespace[name]


def server_class():
    parent = node_class('server', 'SocketServer')
    names = {'_require_connection_producer', 'connection_cleanup_snapshot',
             '_sync_measurement_boundary', '_reset_new_game_replay_segment',
             '_cleanup', '_sync_client_count_locked'}
    methods = [n for n in parent.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in methods} == names
    handler = next(n for n in parent.body if isinstance(n, ast.FunctionDef) and n.name == 'handle_client')
    outer = next(n for n in handler.body if isinstance(n, ast.Try) and n.finalbody)
    # No rewrite of any original finally statement, including nested callback.
    final = ast.parse('def invoke_finally(self, sock, cid, _cleanup_token):\n'
        '    _response_trace = None\n    _gap_connection = None\n'
        '    local_accum = local_measurement_accum = 0\n').body[0]
    final.body += copy.deepcopy(outer.finalbody)
    handshake = next(n for n in ast.walk(outer) if isinstance(n, ast.With)
        and any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                and x.func.attr == 'begin' for x in ast.walk(n)))
    bind = ast.parse('def bind(self, sock, cid, preview_capable, client_slot, eval_mode, _response_connection_ns):\n'
                     '    _cleanup_token = None\n').body[0]
    bind.body += [copy.deepcopy(handshake), ast.parse('return _cleanup_token').body[0]]
    metrics = types.SimpleNamespace(client_count=0,
        ratchet_note_eval_abandoned=lambda *a: None)
    ns = dict(threading=threading, time=time, socket=socket, metrics=metrics,
        reset_client_replay_segment=lambda cs, score: cs.update(reset_score=score),
        print=lambda *a, **k: None)
    cls = compile_body([*methods, final, bind], 'ActualServerMethods', ns)
    cls.fixture_metrics = metrics
    return cls


def buffer_class():
    parent = node_class('server', 'AsyncReplayBuffer')
    names = {'__init__', '_enqueue_preserving', 'step_async', 'reset_client_async',
             '_consume', 'remove_client', 'stop', 'cleanup_health'}
    methods = [n for n in parent.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in methods} == names
    return compile_body(methods, 'ActualReplayBuffer', dict(threading=threading,
        time=time, queue=queue, deque=deque, RL_CONFIG=types.SimpleNamespace(), print=lambda *a, **k: None))


def wait_for(predicate, timeout=2):
    end = time.monotonic()+timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.001)
    raise AssertionError('Owned synthetic collaborator did not reach expected state')


class FakeSocket:
    def __init__(self):
        self.calls = []
    def getsockname(self):
        return ('127.0.0.1', 9999)
    def getpeername(self):
        return ('127.0.0.1', 44007)
    def shutdown(self, how):
        self.calls.append(('shutdown', how))
    def close(self):
        self.calls.append(('close',))


class Agent:
    def __init__(self):
        self.entered, self.release = threading.Event(), threading.Event()
    def step(self, value):
        self.entered.set()
        if not self.release.wait(3):
            raise RuntimeError('Unreleased fixture agent')
        return value


class HandlerFixture:
    def __init__(self, test, *, block_replay=False, timer_failure=False, no_ack=False):
        self.test = test
        self.directory = tempfile.TemporaryDirectory()
        test.addCleanup(self.directory.cleanup)
        self.module = definitions('helper')
        self.journal = definitions('journal').GameJournal(self.directory.name, retire_after_game=True)
        self.context = lambda: dict(experiment='fixture', measurement_active=False, measurement_generation=1)
        cs = dict(client_slot=3, eval_only=False, game_uid=71)
        def frame(score, level):
            return types.SimpleNamespace(game_score=score, level_number=level,
                player_alive=True, done=False, start_pressed=True, lives=3)
        self.journal.observe(7, frame(0, 1), cs, new_game=True, context=self.context)
        self.journal.observe(7, frame(150000123, 300), cs, context=self.context)
        cs['game_uid'] = 72
        self.journal.observe(7, frame(0, 1), cs, new_game=True, context=self.context)
        self.terminal = self.journal.retirement_for_client(7)
        self.terminal_line = Path(self.journal.retirements_path).read_bytes().splitlines(keepends=True)[-1]
        self.agent = Agent()
        self.buffer = buffer_class()(self.agent)
        self.remove_entered = threading.Event()
        self.acks = []
        original_remove = self.buffer.remove_client
        def remove(cid):
            ack = original_remove(cid)
            self.acks.append(ack)
            self.remove_entered.set()
            if no_ack:
                # Real Event remains unset; override wait only to avoid a5s
                # negative fixture delay. The actual finally's branch remains.
                ack.wait = lambda timeout=None: False
            return ack
        self.buffer.remove_client = remove
        if block_replay:
            self.buffer.step_async(41, client_id=7)
            assert self.agent.entered.wait(1)
        else:
            self.agent.release.set()
        s = self.server = server_class()()
        s.metrics = s.fixture_metrics
        s.clients, s.client_states = {}, {7:dict(cs)}
        s.client_lock = threading.Lock()
        s._unwrap_stash, s._eval_override = {}, {}
        s._ensure_preview_client_selected_locked = lambda: (None, False)
        s.shutdown_event = threading.Event()
        s._fail_inference_only = lambda *a: None
        s._rejected_gaps = types.SimpleNamespace(event=lambda *a, **k: None)
        s._journal_context = lambda cs: self.context()
        s._measurement_snapshot = lambda: (False, 1)
        s.game_journal, s.async_buffer = self.journal, self.buffer
        s._cleanup_receipts = self.module.ConnectionCleanupReceipts(
            dict(pid=700000001, birth=17, source_sha256=SOURCES['server'][1]), self.buffer.cleanup_health)
        self.book = s._cleanup_receipts
        self.timer_errors = []
        self.old_hook = threading.excepthook
        if timer_failure:
            def fail():
                raise RuntimeError('expected owned Timer failure')
            s._cleanup = fail
            threading.excepthook = lambda args: self.timer_errors.append(args.exc_value)
        self.finished, self.handler_release = threading.Event(), threading.Event()
        self.errors, self.tokens = [], []
        self.socket = FakeSocket()
        def run():
            try:
                s.clients[7] = threading.current_thread()
                token = s.bind(self.socket, 7, False, 3, 2, 123)
                self.tokens.append(token)
                s.invoke_finally(self.socket, 7, token)
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.finished.set()
                self.handler_release.wait(3)
        self.handler = threading.Thread(target=run, daemon=True)
        test.addCleanup(self.close)
        self.handler.start()

    def close(self):
        self.agent.release.set()
        self.handler_release.set()
        self.handler.join(2)
        for row in self.book.records.values():
            if row['timer'] is not None:
                row['timer'].join(2)
        try:
            self.buffer.stop(timeout_s=2)
        finally:
            threading.excepthook = self.old_hook
        assert not self.handler.is_alive() and not self.buffer._thread.is_alive()


class Tests(unittest.TestCase):
    def server(self, enabled=True):
        s = server_class()()
        s.client_lock = threading.Lock()
        s._eval_override = {}
        s.clients = {7:threading.current_thread()}
        cs = dict(client_slot=3, eval_only=False, measurement_generation=0, measurement_active=False)
        s.client_states = {7:cs}
        s._cleanup_receipts = None if not enabled else definitions('helper').ConnectionCleanupReceipts(
            dict(pid=700000001, birth=17, source_sha256=SOURCES['server'][1]),
            lambda: dict(admission_open=True, consumer_error=None))
        s._ensure_preview_client_selected_locked = lambda: (None, False)
        s._measurement_snapshot = lambda: (False, 1)
        s.game_journal = types.SimpleNamespace(policy_boundary=lambda *a: None)
        s._journal_context = lambda cs: {}
        calls = []
        def reset(cid):
            self.assertTrue(s.client_lock.acquire(blocking=False))
            s.client_lock.release()
            calls.append(cid)
            return threading.Event()
        s.async_buffer = types.SimpleNamespace(reset_client_async=reset)
        if enabled:
            s.bind(FakeSocket(), 7, False, 3, 2, 123)
        return s, cs, calls

    def test_actual_reset_fence_binds_original_handler_state_and_token_before_enqueue(self):
        for fault in ('wrong_handler', 'stale_state', 'stale_token', 'wrong_slot', 'wrong_role'):
            s, cs, calls = self.server()
            if fault == 'wrong_handler': s.clients[7] = threading.Thread()
            if fault == 'stale_state': s.client_states[7] = dict(cs)
            if fault == 'stale_token': cs['_cleanup_token'] = 'not-original'
            if fault == 'wrong_slot': cs['client_slot'] = 4
            if fault == 'wrong_role': cs['eval_only'] = True
            with self.subTest(fault=fault), self.assertRaises((ValueError, RuntimeError)):
                s._sync_measurement_boundary(7, cs, 12)
            self.assertEqual(calls, [])
        s, cs, calls = self.server()
        s._sync_measurement_boundary(7, cs, 12)
        self.assertEqual(calls, [7])
        self.assertEqual(cs['measurement_generation'], 1)
        s._reset_new_game_replay_segment(7, cs, 0)
        self.assertEqual(calls, [7, 7])

    def test_actual_handshake_binds_role_slot_endpoints_and_mode0_has_no_receipt_dependency(self):
        s, cs, _ = self.server()
        value = s.connection_cleanup_snapshot(7, 3)
        self.assertEqual(value['socket_endpoints'], dict(server=['127.0.0.1',9999], peer=['127.0.0.1',44007]))
        self.assertEqual((value['client_id'],value['client_slot'],value['eval_only'],value['connection_ns']), (7,3,False,123))
        self.assertEqual(value['token'], cs['_cleanup_token'])
        self.assertFalse(value['owned_actor_PID_birth_exit_reap_proved'])
        with self.assertRaises(ValueError):
            s._cleanup_receipts.require_active_owner(value['token'],7,3,True,threading.current_thread())
        with self.assertRaises(ValueError):
            s._cleanup_receipts.require_active_owner('unknown-token',7,3,False,threading.current_thread())
        for endpoints in ({'server':['127.0.0.1',9999]},
                          {'server':['127.0.0.1',True],'peer':['127.0.0.1',44007]},
                          {'server':['127.0.0.1',9999],'peer':['127.0.0.1',0]}):
            with self.subTest(endpoints=endpoints), self.assertRaises(ValueError):
                s._cleanup_receipts.begin(8,4,False,124,threading.current_thread(),endpoints=endpoints)
        with self.assertRaises(ValueError): s.connection_cleanup_snapshot(7, 4)
        with self.assertRaises(ValueError): s.connection_cleanup_snapshot(8, 3)
        s, cs, calls = self.server(enabled=False)
        s.clients.clear()  # Mode0 retains the parent's no-receipt behavior.
        s._sync_measurement_boundary(7, cs, 12)
        self.assertEqual(calls,[7])
        self.assertNotIn('_cleanup_token',cs)
        with self.assertRaises(ValueError): s.connection_cleanup_snapshot(7,3)

    def test_actual_finally_preserves_real_durable_terminal_before_disconnect_and_liveness(self):
        f = HandlerFixture(self)
        self.assertTrue(f.finished.wait(1)); self.assertEqual(f.errors,[])
        self.assertIsNone(f.journal.retirement_for_client(7))
        value = f.book.lookup_terminal(f.terminal['journal_game_id'],7,3)
        self.assertEqual(value['terminal_line_sha256'],hashlib.sha256(f.terminal_line).hexdigest())
        self.assertEqual(value['terminal_receipt']['score'],150000123)
        self.assertEqual(value['terminal_receipt']['game_uid'],71)
        self.assertFalse(value['ready_for_external_join'])
        self.assertTrue(f.handler.is_alive())
        timer = f.book.records[f.tokens[0]]['timer']
        f.handler_release.set(); f.handler.join(1)
        if timer.is_alive(): self.assertFalse(f.book.snapshot(f.tokens[0])['ready_for_external_join'])
        timer.join(2)
        value = f.book.lookup_terminal(f.terminal['journal_game_id'],7,3)
        self.assertTrue(value['ready_for_external_join'])
        self.assertTrue(value['training_refill_candidate'])
        self.assertFalse(value['safe_refill_qualified'])
        for args in (('wrong',7,3),(f.terminal['journal_game_id'],8,3),(f.terminal['journal_game_id'],7,4)):
            with self.assertRaises(ValueError): f.book.lookup_terminal(*args)

    def test_actual_finally_waits_for_FIFO_ACK_and_failed_ACK_leaves_tombstone(self):
        f = HandlerFixture(self,block_replay=True)
        self.assertTrue(f.remove_entered.wait(1))
        self.assertFalse(f.acks[0].is_set())
        self.assertFalse(f.finished.is_set())
        self.assertIs(f.server.clients[7],f.handler)
        f.agent.release.set()
        self.assertTrue(f.finished.wait(1)); self.assertEqual(f.errors,[])
        self.assertTrue(f.acks[0].is_set())
        f.close()
        bad = HandlerFixture(self,block_replay=True,no_ack=True)
        self.assertTrue(bad.finished.wait(1)); self.assertEqual(bad.errors,[])
        self.assertIs(bad.server.clients[7],bad.handler)
        bad.close()
        self.assertFalse(bad.book.snapshot(bad.tokens[0])['ready_for_external_join'])

    def test_actual_Timer_failure_and_measurement_state_never_authorize_refill(self):
        f = HandlerFixture(self,timer_failure=True)
        self.assertTrue(f.finished.wait(1)); self.assertEqual(f.errors,[])
        f.close()
        self.assertEqual([str(x)for x in f.timer_errors],['expected owned Timer failure'])
        value = f.book.snapshot(f.tokens[0])
        self.assertFalse(value['owned_timer_callback_succeeded'])
        self.assertFalse(value['ready_for_external_join'])
        good = HandlerFixture(self)
        self.assertTrue(good.finished.wait(1))
        good.handler_release.set(); good.handler.join(1)
        good.book.records[good.tokens[0]]['timer'].join(2)
        self.assertTrue(good.server.connection_cleanup_snapshot(7,3,good.terminal['journal_game_id'])['training_refill_candidate'])
        good.server._measurement_snapshot = lambda: (True,2)
        self.assertFalse(good.server.connection_cleanup_snapshot(7,3,good.terminal['journal_game_id'])['training_refill_candidate'])

    def test_actual_GET_branch_is_bounded_uncached_and_never_touches_viewer_or_controls(self):
        tree = ast.parse(raw('dashboard'))
        method = next(n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name=='do_GET')
        sends=[];calls=[]
        def getter(cid,slot,jid):
            calls.append((cid,slot,jid))
            if cid!=7 or slot!=3:raise ValueError('No exact active connection')
            return dict(token='fixture:original',safe_refill_qualified=False)
        state=types.SimpleNamespace(metrics=types.SimpleNamespace(global_server=types.SimpleNamespace(connection_cleanup_snapshot=getter)),
            touch_web_client=lambda *a: self.fail('Cleanup GET changed viewer bookkeeping'))
        cls=compile_body([method],'ActualHTTPGet',dict(urlparse=urlparse,parse_qs=parse_qs,json=json,state=state))
        handler=cls();handler._send=lambda body,content_type,status=200,**kwargs:sends.append((status,json.loads(body)))
        for path,code in [('/api/connection_cleanup?client_id=7&slot=3',200),
                          ('/api/connection_cleanup?client_id=7&slot=3&journal_game_id=123:71',200),
                          ('/api/connection_cleanup?client_id=7&slot=4',404),
                          ('/api/connection_cleanup?client_id=7&client_id=8&slot=3',400),
                          ('/api/connection_cleanup?client_id=7&slot=3&action=reset',400),
                          ('/api/connection_cleanup?client_id=7&slot=3&journal_game_id='+('1'*513),400)]:
            handler.path=path;handler.do_GET();self.assertEqual(sends[-1][0],code)
        self.assertEqual(calls,[(7,3,None),(7,3,'123:71'),(7,4,None)])


if __name__=='__main__':
    unittest.main()
