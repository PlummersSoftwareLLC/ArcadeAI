"""REAL native loader -> clock proxy -> recorder; external ROM/socket inputs fake.

Consumes fixture definitions only, never any previous test method. No model,
MAME, GPU, live main health, native run(), service, or production action.
"""
from copy import deepcopy
import ast
import hashlib
import importlib.util
import inspect
import json
import socket
from pathlib import Path
import struct
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PRIVATE = HERE / 'private-startup-clock32-original01'
GAME = HERE.parents[3]


def load(name, path, expected=None):
    raw = path.read_bytes()
    if expected: assert hashlib.sha256(raw).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); sys.modules[name] = result
    spec.loader.exec_module(result); return result


h = load('_native_integration_actual_helpers', GAME / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
         '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
native = load('_native_integration_actual_runtime', HERE / 'run_deadline32_leg_v1.py')
definitions = load('_native_integration_clock_fixture_definitions_ONLY', PRIVATE / 'test_startup_deadline32_clock_v1.py',
                   'e7d828e08e10b233a3c70e62a08dc45cce6378e562f9d8c5d22fb766d4d16c2e')


def actual_components():
    derived = json.loads((PRIVATE / 'source-derivation.json').read_text())
    paths = {
        'clock_sampler': derived['clock_component'],
        'clock_authority': derived['selected_sources']['startup_handoff_deadline32_v1.py'],
        'clock_codec': derived['selected_sources']['wire_codec_deadline32_v1.py'],
        'clock_readiness': derived['selected_sources']['boot_readiness_deadline32_v1.py'],
        'clock_ledger': derived['selected_sources']['tail_ledger_deadline32_v1.py'],
        'clock_proxy': derived['selected_sources']['full_startup_proxy_deadline32_v1.py'],
        'prefix_auditor': dict(path=str(PRIVATE / 'audit_startup_deadline32_clock_v2.py'),
                              sha256='e0217fffc18039b65a5168f266600bcff999df3c0e10a65e4a73ffa53bdda5a3'),
        'score_auditor': h.pin(HERE / 'audit_deadline32_score_v1.py')}
    core = json.loads((HERE / 'recorder-component-preparation-v3.json').read_text())
    paths['recorder'] = core['source']
    for key, manifest, filename in (
        ('hooks', 'proxy-hooks-component-preparation-v1.json', 'deadline_proxy_hooks_v1.py'),
        ('report', 'report-component-preparation-v1.json', 'deadline_score_report_v1.py'),
        ('lifecycle', 'lifecycle-component-preparation-v1.json', 'deadline_measurement_lifecycle_v1.py')):
        paths[key] = json.loads((HERE / manifest).read_text())['files'][filename]
    result = {}
    for key, value in paths.items():
        actual = h.pin(value['path']); assert actual['sha256'] == value['sha256']
        result[key] = actual
    assert set(result) == native.COMPONENT_KEYS
    return result


class ActualOrigin:
    """Simulate accepted server exchange only; journal/clock/proxy/ledger are REAL."""
    def __init__(self, fixture):
        self.f = fixture; self.sent = []; self.buffer = b''; self.accept = True
    def settimeout(self, value): pass
    def setsockopt(self, *args): pass
    def sendall(self, raw):
        if len(raw) == 2: return
        size = struct.unpack_from('>I', raw)[0]
        assert size == 7597 and len(raw) == size + 4
        self.sent.append(raw)
        f = self.f
        if self.accept:
            with f.server.client_lock:
                f.cs['frames'] += 1
                if getattr(f, 'confirmed_new_game', False): f.cs['game_uid'] += 1
                f.cs.update(game_score=f.frame.game_score, level_number=f.frame.level_number,
                    player_alive=f.frame.player_alive, num_lasers=f.frame.num_lasers, lives=f.frame.lives,
                    raw_score_prev=f.frame.game_score % 100_000_000,
                    score_offset=f.frame.game_score // 100_000_000 * 100_000_000)
            f.fleet.journal.observe(96, f.frame, f.cs, context=lambda: f.fleet.context,
                                   new_game=getattr(f, 'confirmed_new_game', False))
        self.buffer = definitions.bridge_defs.ACTION
    def recv(self, count):
        count = min(count, 2); result, self.buffer = self.buffer[:count], self.buffer[count:]
        return result


class Tests(unittest.TestCase):
    def fixture(self):
        job = dict(components=actual_components())
        modules = native.load_components(job, h)
        f = definitions.BridgeFixture(); self.addCleanup(f.close)
        f.cs.update(measurement_active=True, measurement_generation=1,
                    raw_score_prev=100, score_offset=0, coerced_score_dips=0)
        clock = lambda: f.fleet.mono
        recorder = modules['recorder'].DeadlineScoreRecorder(clock_ns=clock)
        gate = modules['hooks'].DeadlineExchangeGate(clock_ns=clock)
        registry = modules['hooks'].FirstGameRegistration()
        policy = dict(policy_sha256=f.fleet.policy['checkpoint_sha256'], measurement_generation=1,
            experiment=f.fleet.policy['experiment'], policy_clocks={key: f.fleet.policy[key]
                for key in ('learner_frame_count', 'training_steps', 'optimized_samples')})
        bridge = modules['hooks'].build_deadline_proxy(modules['clock_proxy'].StartupProxy,
            expected_base_sha256=job['components']['clock_proxy']['sha256'], recorder=recorder,
            gate=gate, policy=policy, on_cutoff=gate.retire_received_request, clock_ns=clock)
        old = f.proxy
        f.proxy = bridge(f.server, **f.subject, trace_path=f.path, trace_identity=old.trace.identity,
            rom_sha256=old.rom_sha256, policy_reader=lambda: f.fleet.policy,
            admission_reader=lambda: f.fleet.window, frame_parser=lambda _: deepcopy(f.frame),
            emit=f.logs.append, stop_event=old.stop_event, drain_reader=lambda: registry,
            wall_ns=lambda: f.fleet.wall, monotonic_ns=clock)
        f.proxy.cid = 96; f.origin = ActualOrigin(f)
        return f, modules, recorder, gate, registry, policy

    def test_actual_native_loader_proves_real_nested_private_chain_and_rejects_legacy_alias(self):
        job = dict(components=actual_components())
        modules = native.load_components(job, h)
        for key, field in [('clock_authority', 'authority'), ('clock_codec', 'codec')]:
            actual = Path(inspect.getsourcefile(getattr(modules['clock_proxy'], field))).resolve()
            self.assertEqual(actual, Path(job['components'][key]['path']))
        wrong = deepcopy(job)
        wrong['components']['clock_authority'] = h.pin(GAME / 'tools/startup_policy_journal_proposal/startup_handoff_v2.py')
        with self.assertRaisesRegex(ValueError, 'nested source differs'):
            native.load_components(wrong, h)

    def test_real_1200_prefix_first_bind_then_1201_callback_is_coherent(self):
        f, modules, recorder, gate, registry, policy = self.fixture()
        f.prefix(); f.step()
        member = f.proxy.deadline_member
        self.assertEqual(member['journal_game_id'], f.proxy.handoff['journal_game_id'])
        self.assertEqual(member['startup_nonce'], f.proxy.issuer.nonce)
        self.assertEqual(member['start_certificate_id'], registry.registered[4096]['certificate_identifier'])
        self.assertTrue(f.proxy.prefix_verified.is_set()); self.assertEqual(f.proxy.sequence, 1201)
        packet = recorder._last_packets[4096]; value = recorder._scores[4096]
        self.assertEqual((packet['sequence'], packet['accepted_ordinal']), (1201, f.cs['frames']))
        self.assertEqual(value['first_play_level'], 1); self.assertEqual(value['status'], 'censored')
        self.assertEqual(value['score_witness']['source_witness']['origin_state']['frames'], f.cs['frames'])
        self.assertEqual(gate.inflight, {}); self.assertEqual(gate.entered, gate.finished)
        self.assertIsNone(registry.permit)

    def test_actual_proxy_fullscore_terminal_OLDUID_and_later_game_activity(self):
        f, modules, recorder, gate, registry, policy = self.fixture()
        f.prefix(); f.step()
        f.frame.game_score = 100_000_025
        payload = bytearray(definitions.bridge_defs.PAYLOAD); struct.pack_into('>I', payload, 19, 25)
        with patch.object(definitions.bridge_defs, 'PAYLOAD', bytes(payload)):
            f.step(score_hex='00000025')
        witness = recorder._scores[4096]['score_witness']
        self.assertEqual((witness['full_score'], witness['effective_raw_score'], witness['score_offset']),
                         (100_000_025, 25, 100_000_000))
        self.assertEqual(witness['raw_wire_score'], 25)
        original_member = deepcopy(f.proxy.deadline_member)
        f.frame.game_score = 0; f.confirmed_new_game = True; f.step()
        value = recorder._scores[4096]
        self.assertEqual((value['status'], value['score']), ('completed', 100_000_025))
        self.assertEqual(value['completed_row']['game_uid'], original_member['game_uid'])
        self.assertNotEqual(f.cs['game_uid'], original_member['game_uid'])
        f.confirmed_new_game = False; f.frame.game_score = 500; f.step()
        self.assertEqual(f.proxy.deadline_member, original_member)
        self.assertEqual(recorder._scores[4096]['score'], 100_000_025)
        self.assertEqual(recorder._last_packets[4096]['origin_game_uid'], f.cs['game_uid'])
        self.assertEqual(gate.inflight, {})

    def test_actual_origin_context_and_snapshot_race_faults_are_not_censored(self):
        f, modules, recorder, gate, registry, policy = self.fixture()
        f.prefix(); f.step()
        # Encode the just-completed sequence through the real codec, without forwarding.
        metadata = f.meta(); metadata['sequence'] = f.proxy.sequence
        raw = modules['clock_codec'].encode_request(definitions.bridge_defs.PAYLOAD, metadata)
        for field, bad in [('eval_only', False), ('measurement_active', False), ('measurement_generation', 2), ('client_slot', 4097)]:
            previous = f.cs[field]; f.cs[field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                modules['hooks'].completed_exchange_sample(f.proxy, raw, f.cs['frames'] - 1,
                    f.proxy.deadline_member, policy, completed_exchange_ns=f.fleet.mono,
                    clock_ns=lambda: f.fleet.mono)
            f.cs[field] = previous
        original = modules['hooks'].selected_journal_snapshot
        def racing(*args):
            result = original(*args); f.cs['frames'] += 1; return result
        with patch.object(modules['hooks'], 'selected_journal_snapshot', side_effect=racing), self.assertRaisesRegex(ValueError, 'changed during'):
            modules['hooks'].completed_exchange_sample(f.proxy, raw, f.cs['frames'] - 1,
                f.proxy.deadline_member, policy, completed_exchange_ns=f.fleet.mono, clock_ns=lambda: f.fleet.mono)
        self.assertEqual(recorder._last_packets[4096]['sequence'], 1201)

    def test_REAL_server_finally_writer_outlives_registry_and_owned_workers_are_retained(self):
        path = GAME / 'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/socket_server.py'
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'b552b2e83a9cc10cf7e4125cef22f571abe9189bd2ad3e63c6f48aa7df0e4516')
        source = ast.parse(raw)
        server_class = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
        handler = next(n for n in server_class.body if isinstance(n, ast.FunctionDef) and n.name == 'handle_client')
        suites = [n.finalbody for n in ast.walk(handler) if isinstance(n, ast.Try) and n.finalbody and
                  any(isinstance(c, ast.Attribute) and c.attr == 'ratchet_note_eval_abandoned'
                      for n2 in n.finalbody for c in ast.walk(n2))]
        self.assertEqual(len(suites), 1)
        fn = ast.parse('def exact_finally(self,cid,sock,local_accum,local_measurement_accum,_gap_connection):\n pass').body[0]
        fn.body = deepcopy(suites[0])
        self.assertEqual([ast.dump(n, include_attributes=False) for n in fn.body],
                         [ast.dump(n, include_attributes=False) for n in suites[0]])
        namespace = dict(threading=threading, socket=socket, time=time,
                         metrics=SimpleNamespace(ratchet_note_eval_abandoned=lambda _: None))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                     str(path) + '::EXACT-handle-client-finally-CPU', 'exec'), namespace)
        begin = threading.Event(); release = threading.Event(); journal_blocked = threading.Event()
        journal_release = threading.Event(); inference_release = threading.Event(); events = []
        class Server:
            def _cleanup(self): events.append('owned_timer_finished')
        server = Server(); server.client_lock = threading.Lock(); server.clients = {}
        server.client_states = {0: dict(game_uid=1, raw_score_prev=0)}
        server._unwrap_stash = {}; server._eval_override = {}; server.async_buffer = None
        server.shutdown_event = threading.Event(); server.shutdown_event.set()
        server._rejected_gaps = SimpleNamespace(event=lambda *a: None)
        server._ensure_preview_client_selected_locked = lambda: (None, False)
        server._sync_client_count_locked = lambda: None
        server._journal_context = lambda _: {}
        def disconnect(*args):
            journal_blocked.set()
            if not journal_release.wait(3): raise RuntimeError('CPU fixture journal release timed out')
            events.append('journal_writer_finished')
        server.game_journal = SimpleNamespace(disconnect=disconnect)
        server._fail_inference_only = lambda message: events.append('unexpected_error:' + message)
        sock = SimpleNamespace(shutdown=lambda *_: None, close=lambda: None)
        def handler_finally():
            if begin.wait(3): namespace['exact_finally'](server, 0, sock, 0, 0, None)
        clients = [threading.Thread(target=handler_finally, daemon=True)] + [
            threading.Thread(target=release.wait, daemon=True) for _ in range(31)]
        inference = threading.Thread(target=inference_release.wait, name='InferBatchWorker-CPU-fixture', daemon=True)
        server.inference_batcher = SimpleNamespace(_thread=inference)
        for index, thread in enumerate(clients): server.clients[index] = thread; thread.start()
        inference.start()
        def final_cleanup():
            begin.set(); release.set(); journal_release.set(); inference_release.set()
            for thread in [*clients, inference]: thread.join(3)
            for timer in native.owned_cleanup_timers(server): timer.join(3)
        self.addCleanup(final_cleanup)
        retained, actual_inference = native.capture_origin_writers(server)
        self.assertEqual(set(retained), set(clients)); self.assertIs(actual_inference, inference)
        begin.set(); self.assertTrue(journal_blocked.wait(2))
        self.assertIsNone(server.clients[0]); self.assertTrue(retained[0].is_alive())
        current, _ = native.capture_origin_writers(server, require_all32=False)
        self.assertEqual(len(current), 31)
        with self.assertRaises(ValueError): native.capture_origin_writers(server)
        journal_release.set(); release.set()
        for thread in retained: thread.join(2); self.assertFalse(thread.is_alive())
        self.assertTrue(actual_inference.is_alive())  # It remains known even if server drops its pointer.
        server.inference_batcher = None
        inference_release.set(); actual_inference.join(2); self.assertFalse(actual_inference.is_alive())
        unrelated = threading.Timer(10, lambda: None); unrelated.daemon = True; unrelated.start()
        self.addCleanup(lambda: (unrelated.cancel(), unrelated.join(2)))
        timers = native.owned_cleanup_timers(server)
        self.assertEqual(len(timers), 1); self.assertNotIn(unrelated, timers)
        for timer in timers: timer.join(2); self.assertFalse(timer.is_alive())
        self.assertEqual(events, ['journal_writer_finished', 'owned_timer_finished'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
