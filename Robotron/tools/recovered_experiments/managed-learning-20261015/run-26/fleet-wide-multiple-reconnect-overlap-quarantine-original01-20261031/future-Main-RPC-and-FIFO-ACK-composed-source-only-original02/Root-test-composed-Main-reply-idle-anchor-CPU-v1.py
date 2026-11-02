"""Test the actual selected reply block AST using fake collaborators only."""
import argparse
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = Path(__file__).resolve().parent
CANDIDATE = HERE / 'socket_server.py'
PARENT = ROOT / 'Scripts/dqn/socket_server.py'
CANDIDATE_SHA = '1692ee2dbfb6f83d0f50234ee1eb30d0cf6bbe45d670a5a9fb52992fd92b56fc'
PARENT_SHA = 'a076501b0601a637b91269a41572be60496754ad1da4b04385d77c51b9f34423'


def selected_block(source, anchored):
    tree = ast.parse(source)
    server = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'SocketServer')
    handler = next(x for x in server.body if isinstance(x, ast.FunctionDef) and x.name == 'handle_client')
    matches = []
    for loop in ast.walk(handler):
        if not isinstance(loop, ast.While):
            continue
        for i, node in enumerate(loop.body):
            if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                    and any(isinstance(kw.value, ast.Constant)
                            and kw.value.value == 'accepted_action_write_completed'
                            for kw in node.value.keywords)):
                block = loop.body[i-1:i+2] if anchored else loop.body[i-1:i+1]
                assert isinstance(block[0], ast.Try)
                if anchored:
                    assert ast.unparse(block[2].test) == 'self.replay_enabled'
                matches.append(copy.deepcopy(block))
    assert len(matches) == 1
    body = matches[0]
    body += ast.parse('iteration_completed = True\nbreak').body
    module = ast.fix_missing_locations(ast.Module(body=[ast.While(
        test=ast.Constant(True), body=body, orelse=[])], type_ignores=[]))
    return compile(module, str(CANDIDATE if anchored else PARENT) + ':selected-reply-AST', 'exec'), handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    candidate, parent = CANDIDATE.read_bytes(), PARENT.read_bytes()
    assert hashlib.sha256(candidate).hexdigest() == CANDIDATE_SHA
    assert hashlib.sha256(parent).hexdigest() == PARENT_SHA
    compiled, handler = selected_block(candidate, True)
    old_compiled, old_handler = selected_block(parent, False)
    def header_idle_ast(method):
        return [ast.dump(n, include_attributes=False) for n in ast.walk(method)
                if isinstance(n, ast.If) and ast.unparse(n.test) == 'hdr is None']
    assert header_idle_ast(handler) == header_idle_ast(old_handler)
    assert len(header_idle_ast(handler)) == 1

    def exercise(*, replay=True, failure=None, old=False):
        events, clock_calls = [], []
        clock = SimpleNamespace(value=165.0)
        def tick():
            clock_calls.append('time')
            return clock.value
        def callback(name, advance=0):
            events.append(name)
            if failure == name:
                raise RuntimeError('injected ' + name)
            clock.value += advance
        def pack(*a, **kw):
            callback('pack')
            return b'action'
        trace = SimpleNamespace(mark=lambda *a: callback('mark'),
                                finish=lambda *a, **kw: callback('trace', 3))
        server = SimpleNamespace(replay_enabled=replay,
            _preview_flags_for_client=lambda *a: (True, False),
            _pack_action=pack,
            _rejected_gaps=SimpleNamespace(event=lambda *a, **kw: callback('gap', 4)))
        namespace = dict(self=server, sock=SimpleNamespace(sendall=lambda data: callback('send', 2)),
            time=SimpleNamespace(time=tick), cid=1, move_cmd=2, fire_cmd=3, src_code=1,
            _response_trace=trace, _gap_ticket='original', last_payload_time=100.0,
            iteration_completed=False)
        exec(old_compiled if old else compiled, namespace)
        return namespace, events, clock_calls, clock.value

    class ReplyIdleTests(unittest.TestCase):
        def test_main_success_excludes_own_65_second_processing_delay(self):
            result, events, calls, end = exercise()
            self.assertEqual(events, ['mark', 'pack', 'send', 'trace', 'gap'])
            self.assertEqual(calls, ['time'])
            self.assertEqual(end, 174.0)
            self.assertEqual(result['last_payload_time'], end)
            self.assertTrue(result['iteration_completed'])
            self.assertLess(175 - result['last_payload_time'], 30)
            original, _, original_calls, _ = exercise(old=True)
            self.assertGreaterEqual(175 - original['last_payload_time'], 30)
            self.assertEqual(original_calls, [])

        def test_private_success_preserves_existing_idle_anchor(self):
            result, events, calls, end = exercise(replay=False)
            self.assertEqual(result['last_payload_time'], 100)
            self.assertTrue(result['iteration_completed'])
            self.assertEqual(calls, [])
            self.assertEqual(events[-1], 'gap')

        def test_failed_action_pack_breaks_without_success_anchor(self):
            result, events, calls, end = exercise(failure='pack')
            self.assertEqual(events, ['mark', 'pack'])
            self.assertFalse(result['iteration_completed'])
            self.assertEqual(result['last_payload_time'], 100)
            self.assertEqual(calls, [])

        def test_failed_send_breaks_without_success_anchor(self):
            result, events, calls, end = exercise(failure='send')
            self.assertEqual(events, ['mark', 'pack', 'send'])
            self.assertFalse(result['iteration_completed'])
            self.assertEqual(result['last_payload_time'], 100)
            self.assertEqual(calls, [])

        def test_failed_trace_after_send_does_not_anchor(self):
            result, events, calls, end = exercise(failure='trace')
            self.assertEqual(events, ['mark', 'pack', 'send', 'trace'])
            self.assertFalse(result['iteration_completed'])
            self.assertEqual(result['last_payload_time'], 100)
            self.assertEqual(calls, [])

        def test_gap_error_propagates_before_anchor(self):
            with self.assertRaisesRegex(RuntimeError, 'injected gap'):
                exercise(failure='gap')

    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReplyIdleTests))
    report = dict(schema='robotron-Root-composed-Main-reply-idle-anchor-CPU-v1',
        candidate_sha256=CANDIDATE_SHA, parent_sha256=PARENT_SHA,
        original_header_idle_AST_exact=True, tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        success=result.wasSuccessful() and not result.skipped, output=stream.getvalue(),
        scope='Actual selected send/finish/anchor AST with fake sockets, clock and callbacks; no whole-handler or live-runtime qualification')
    args.output.parent.mkdir(parents=True, exist_ok=False)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, 'w') as out:
        json.dump(report, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    print(json.dumps({key: report[key] for key in
                      ('tests_run', 'failures', 'errors', 'skipped', 'success', 'scope')}))
    raise SystemExit(0 if report['success'] else 1)


if __name__ == '__main__':
    main()
