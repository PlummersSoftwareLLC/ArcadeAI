"""CPU-only transport regressions against the actual production source.

Static pre-fix fixtures reproduce the original defects independently of current
source/logs. No production imports, GPU initialization, MAME, or source writes.
"""
import ast
import importlib.util
from pathlib import Path
import queue
import select
import socket
import threading
import time
import unittest

from preview_socket_recovery import ROOT, LUA, SERVER, proposed_lua, proposed_server


def load_protocol(server_source):
    tree = ast.parse(server_source)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name in ("_InferenceRequest", "AsyncInferenceBatcher")]
    server = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SocketServer")
    receive = next(n for n in server.body if isinstance(n, ast.FunctionDef) and n.name == "_recv_exact")
    receive.decorator_list = []
    namespace = dict(queue=queue, select=select, socket=socket, threading=threading, time=time)
    exec(compile(ast.Module(body=classes + [receive], type_ignores=[]),
                 "in_memory_socket_recovery", "exec"), namespace)
    return namespace


class SocketRecoveryProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures = Path(__file__).with_name("fixtures")
        cls.original_lua = (fixtures / "socket_recovery_before.lua").read_text()
        cls.lua_source = (ROOT / LUA).read_text()
        cls.original_server = (fixtures / "socket_recovery_before.py").read_text()
        cls.server_source = (ROOT / SERVER).read_text()
        cls.protocol = load_protocol(cls.server_source)
        spec = importlib.util.spec_from_file_location("existing_socket_wait_tests",
                                                     Path(__file__).with_name("test_socket_wait.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.harness_type = module.SocketWaitTests
        cls.harness_type.setUpClass()

    def harness(self, *, patched=True):
        harness = self.harness_type()
        source = self.lua_source if patched else self.original_lua
        harness.source = source
        harness.exchange = source[source.index("local function process_frame_via_socket("):
                                  source.index("local function determine_meta_commands(")]
        # Use production close_socket too, with a fake transport close method.
        actual_close = source[source.index("local function close_socket()"):
                              source.index("local function open_socket()")]
        actual_close = actual_close.replace("local function close_socket()", "function close_socket()", 1)
        original_run = harness.run_lua

        def run_lua(text, execute=True):
            text = text.replace('''close_socket = function()
    current_socket = nil
    ACTION_RX_BUFFER = ""
    set_preview_stream_enabled(false)
    PREVIEW_HUD_ENABLED = false
end''', actual_close, 1)
            original_run(text, execute=execute)
        harness.run_lua = run_lua
        return harness

    def test_preview_is_noop_and_fixture_patch_matches_live_protocol(self):
        self.assertEqual(proposed_lua(self.lua_source), self.lua_source)
        self.assertEqual(proposed_server(self.server_source), self.server_source)
        before = self.original_lua
        expected_exchange = proposed_lua(before).split("local function process_frame_via_socket(", 1)[1]
        expected_exchange = expected_exchange.split("local function determine_meta_commands(", 1)[0]
        actual_exchange = self.lua_source.split("local function process_frame_via_socket(", 1)[1]
        actual_exchange = actual_exchange.split("local function determine_meta_commands(", 1)[0]
        self.assertEqual(expected_exchange, actual_exchange)
        for name in ("_recv_exact", "_InferenceRequest", "AsyncInferenceBatcher"):
            # Compare parsed source bodies, independent of line-number metadata.
            source_tree = ast.parse(self.server_source)
            fixture_tree = ast.parse(proposed_server(self.original_server))
            def body(tree):
                return next(n for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef))
                            and n.name == name)
            self.assertEqual(ast.dump(body(source_tree)), ast.dump(body(fixture_tree)))

    def test_original_lua_reproduces_late_action_shift(self):
        self.harness(patched=False).exchange_test(r'''
print = function() end
events = {{0.011, string.pack("bbBBBB", 2, 3, 1, 0, 1, 5)},
          {0.012, string.pack("bbBBBB", 4, 5, 1, 0, 1, 5)}}
local m,f,ok = process_frame_via_socket("state_N",77)
assert(ok and m == -1 and f == -1)
m,f,ok = process_frame_via_socket("state_Nplus1",78)
assert(ok and m == 2 and f == 3)
m,f,ok = process_frame_via_socket("state_Nplus2",79)
assert(ok and m == 4 and f == 5)
''', preload=True)

    def test_timeout_closes_full_late_reply_and_reconnect_associates_new_state(self):
        self.timeout_and_reconnect(partial=False)

    def test_timeout_closes_partial_reply_and_reconnect_associates_new_state(self):
        self.timeout_and_reconnect(partial=True)

    def timeout_and_reconnect(self, partial):
        self.harness().exchange_test(r'''
print = function() end
local old_socket = current_socket
local closes = 0
old_socket.close = function(self) closes = closes + 1; self.closed = true end
local old_packet = string.pack("bbBBBB", 2, 3, 1, 0, 1, 5)
events = PARTIAL and {{0, string.sub(old_packet,1,2)}, {0.011, string.sub(old_packet,3)}}
                 or {{0.011, old_packet}}
local m,f,ok = process_frame_via_socket("state_N",77)
assert(not ok and m == -1 and f == -1 and closes == 1)
assert(current_socket == nil and old_socket.closed and #ACTION_RX_BUFFER == 0)
assert(not previews and not PREVIEW_HUD_ENABLED and frames == 77)
-- A separate TCP stream has no access to the old stream's delayed tail.
local old_stream_events = events
assert(#old_stream_events == 1)
local new_socket = {write=old_socket.write, read=old_socket.read, close=function() end}
open_socket = function()
    assert(current_socket == nil)
    current_socket = new_socket
    events = {{wall, string.pack("bbBBBB", 6, 7, 4, 0, 1, 0x85)}}
    return true
end
m,f,ok = process_frame_via_socket("state_Nplus1",78)
assert(ok and m == 6 and f == 7 and SERVER_IS_EVAL)
assert(closes == 1 and current_socket == new_socket and #old_stream_events == 1)
assert(#writes == 2 and string.sub(writes[2],5) == "state_Nplus1")
'''.replace("PARTIAL", str(partial).lower()), preload=True)

    def test_healthy_legacy_and_current_contracts_preserved(self):
        harness = self.harness()
        harness.test_whole_script_still_compiles_in_lua54()
        harness.test_immediate_full_packet_does_not_sleep_or_advance_frame()
        harness.test_split_packet_accumulates_across_empty_reads_before_settle()
        harness.test_tail_arriving_just_before_settle_deadline_is_not_parsed_as_legacy()
        harness.test_three_and_five_byte_legacy_settle_use_wall_time()
        harness.test_read_and_write_exceptions_close_connection_and_return_neutral()

    def test_partial_headers_and_payloads_fail_closed_but_zero_byte_idle_is_safe(self):
        receive = self.protocol["_recv_exact"]
        for expected, prefix in ((4, b"\x00\x00"), (12, b"payload")):
            with self.subTest(expected=expected):
                # Own both endpoints explicitly, including assertion failures.
                a, b = socket.socketpair()
                try:
                    a.setblocking(False)
                    self.assertIsNone(receive(a, expected, timeout_s=.005))
                    b.sendall(prefix)
                    with self.assertRaisesRegex(ConnectionError, "Partial read timeout"):
                        receive(a, expected, timeout_s=.005)
                finally:
                    a.close(); b.close()

    def test_original_partial_header_demonstrates_lost_framing(self):
        receive = load_protocol(self.original_server)["_recv_exact"]
        a, b = socket.socketpair()
        try:
            a.setblocking(False); b.sendall(b"\x00\x00")
            self.assertIsNone(receive(a, 4, timeout_s=.005))
            b.sendall(b"\x00\x08ABCDpayload")
            self.assertEqual(receive(a, 4, timeout_s=.005), b"\x00\x08AB")
        finally:
            a.close(); b.close()

    def test_healthy_fragmented_request_is_assembled_without_changing_bytes(self):
        a, b = socket.socketpair()
        def send_tail():
            time.sleep(.005); b.sendall(b"\x00\x08")
        writer = threading.Thread(target=send_tail)
        try:
            a.setblocking(False); b.sendall(b"\x00\x00"); writer.start()
            self.assertEqual(self.protocol["_recv_exact"](a, 4, timeout_s=.2), b"\x00\x00\x00\x08")
        finally:
            writer.join(1); a.close(); b.close()

    def batcher(self, agent, timeout_ms=100):
        batcher = self.protocol["AsyncInferenceBatcher"](
            agent, max_batch_size=128, max_wait_ms=0, request_timeout_ms=timeout_ms)
        self.addCleanup(batcher.stop)
        return batcher

    def test_inflight_timeout_never_starts_duplicate_solo_work(self):
        agent = FakeAgent(block=True)
        batcher = self.batcher(agent, timeout_ms=20)
        result = []
        handler = threading.Thread(target=lambda: capture(lambda: batcher.infer("state", 0), result))
        handler.start()
        try:
            self.assertTrue(agent.enter.wait(1)); handler.join(1)
            self.assertFalse(handler.is_alive())
            self.assertIsInstance(result[0], TimeoutError)
            self.assertEqual(agent.solo_calls, 0)
        finally:
            agent.release.set(); handler.join(1)
        batcher.stop()
        self.assertEqual(agent.batch_calls, 1)

    def test_original_batcher_reproduces_inflight_duplicate_solo_work(self):
        agent = FakeAgent(block=True)
        def solo(*args, **kwargs):
            agent.solo_calls += 1
            return (4, 5, False)
        agent.act = solo
        batcher = load_protocol(self.original_server)["AsyncInferenceBatcher"](
            agent, max_batch_size=128, max_wait_ms=0, request_timeout_ms=20)
        results = []
        handler = threading.Thread(target=lambda: capture(lambda: batcher.infer("state", 0), results))
        handler.start()
        try:
            self.assertTrue(agent.enter.wait(1)); handler.join(1)
            self.assertEqual(results, [(4, 5, False)])
            self.assertEqual((agent.batch_calls, agent.solo_calls), (1, 1))
        finally:
            agent.release.set(); handler.join(1); batcher.stop()

    def test_queue_admission_and_completion_share_one_absolute_deadline(self):
        protocol = load_protocol(self.server_source)
        ticks = iter((10.0, 10.0, 10.03))
        protocol["time"] = type("Clock", (), {"perf_counter": staticmethod(lambda: next(ticks))})
        waits, puts = [], []
        class Event:
            def wait(self, timeout):
                waits.append(timeout)
                return False
        request = self.protocol["_InferenceRequest"]("state", 0)
        request.event = Event()
        protocol["_InferenceRequest"] = lambda *a, **k: request
        batcher = protocol["AsyncInferenceBatcher"].__new__(protocol["AsyncInferenceBatcher"])
        batcher.running, batcher.request_timeout_s = True, .1
        batcher._request_lock, batcher._pending = threading.Lock(), set()
        batcher.queue = type("Queue", (), {"put": lambda self, req, timeout: puts.append(timeout)})()
        with self.assertRaises(TimeoutError):
            batcher.infer("state", 0)
        self.assertAlmostEqual(puts[0], .1)
        self.assertAlmostEqual(waits[0], .07)
        self.assertTrue(request.cancelled)
        self.assertFalse(batcher._pending)

    def test_queued_timeout_skips_dispatch_and_never_solo_falls_back(self):
        agent = FakeAgent(block=True)
        batcher = self.batcher(agent, timeout_ms=20)
        first, second = [], []
        handler = threading.Thread(target=lambda: capture(lambda: batcher.infer("first", 0), first))
        handler.start(); self.assertTrue(agent.enter.wait(1))
        try:
            capture(lambda: batcher.infer("second", 0), second)
            handler.join(1)
            self.assertIsInstance(second[0], TimeoutError)
        finally:
            agent.release.set(); handler.join(1)
        batcher.stop()
        self.assertEqual((agent.batch_calls, agent.solo_calls), (1, 0))

    def test_queue_full_raises_without_solo_work(self):
        agent = FakeAgent()
        batcher_type = self.protocol["AsyncInferenceBatcher"]
        batcher = batcher_type.__new__(batcher_type)
        batcher.agent, batcher.running, batcher.request_timeout_s = agent, True, .005
        batcher._request_lock, batcher._pending = threading.Lock(), set()
        batcher.queue = queue.Queue(maxsize=1); batcher.queue.put(object())
        with self.assertRaisesRegex(TimeoutError, "admission"):
            batcher.infer("state", 0)
        self.assertEqual(agent.solo_calls, 0)

    def test_batch_error_and_incomplete_results_raise_instead_of_neutral_or_solo(self):
        for outcome in (ValueError("injected failure"), [], [None], [(1, 2)],
                        [(9, 2, False)], [(1, -1, False)], [(1, 2, "bad")]):
            with self.subTest(outcome=outcome):
                agent = FakeAgent(outcome=outcome)
                batcher = self.batcher(agent)
                with self.assertRaisesRegex(RuntimeError, "Batched inference failed"):
                    batcher.infer("state", 0)
                self.assertEqual(agent.solo_calls, 0)
                batcher.stop()

    def test_stopped_requests_raise(self):
        agent = FakeAgent(); batcher = self.batcher(agent); batcher.stop()
        with self.assertRaisesRegex(RuntimeError, "stopped"):
            batcher.infer("state", 0)
        self.assertEqual(agent.solo_calls, 0)

    def test_stop_wakes_inflight_and_queued_waiters_without_late_success(self):
        agent = FakeAgent(block=True); batcher = self.batcher(agent, timeout_ms=2000)
        results = [[], []]
        handlers = [threading.Thread(target=lambda i=i: capture(
            lambda: batcher.infer(str(i), 0), results[i])) for i in range(2)]
        handlers[0].start(); self.assertTrue(agent.enter.wait(1)); handlers[1].start()
        deadline = time.monotonic() + 1
        while batcher.queue.qsize() != 1 and time.monotonic() < deadline:
            time.sleep(.001)
        self.assertEqual(batcher.queue.qsize(), 1)
        with batcher._request_lock:
            pending = list(batcher._pending)
        stopping = threading.Thread(target=batcher.stop); stopping.start()
        try:
            for handler in handlers:
                handler.join(.2); self.assertFalse(handler.is_alive())
            for result in results:
                self.assertIsInstance(result[0], RuntimeError)
                self.assertIn("stopped", str(result[0]))
            self.assertTrue(stopping.is_alive(), "GPU-shaped fake is still blocked")
        finally:
            agent.release.set()
            for handler in handlers:
                handler.join(1)
            stopping.join(1)
        self.assertFalse(stopping.is_alive())
        self.assertEqual((agent.batch_calls, agent.solo_calls), (1, 0))
        self.assertTrue(all(req.action is None and req.error for req in pending))

    def test_healthy_batch_preserves_aligned_actions_epsilon_and_locked_fire(self):
        agent = FakeAgent(); batcher = self.batcher(agent)
        result = batcher.infer("state", .17, locked_fire=6)
        self.assertEqual(result, (2, 6, False))
        self.assertEqual(agent.seen, [(["state"], [.17], [6])])
        self.assertEqual(agent.solo_calls, 0)


def capture(function, destination):
    try:
        destination.append(function())
    except Exception as error:
        destination.append(error)


class FakeAgent:
    def __init__(self, *, block=False, outcome="normal"):
        self.enter, self.release = threading.Event(), threading.Event()
        self.block, self.outcome = block, outcome
        self.batch_calls = self.solo_calls = 0
        self.seen = []

    def act_batch(self, states, epsilons, locked_fires=None):
        self.batch_calls += 1
        self.seen.append((states, epsilons, locked_fires)); self.enter.set()
        if self.block and not self.release.wait(1):
            raise RuntimeError("Test failed to release blocked inference")
        if isinstance(self.outcome, Exception):
            raise self.outcome
        if self.outcome != "normal":
            return self.outcome
        return [(2, fire if fire is not None else 3, False) for fire in locked_fires]

    def act(self, *args, **kwargs):
        self.solo_calls += 1
        raise AssertionError("Solo fallback is forbidden")


if __name__ == "__main__":
    unittest.main()
