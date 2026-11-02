"""UNEXECUTED source proposal; root alone may test after freeze release.

Future tests reconstruct the sealed patch and compile only exact selected AST
bodies. No project import, server startup, model, real HTTP/proc/subprocess or
clock sleep occurs. Eight real test threads use bounded stdlib synchronization;
their fake stderr tests call serialization, not OS stream atomicity/performance.
"""
import ast
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from queue import Queue
import re
import threading
import traceback
import types
import unittest
from urllib.parse import parse_qs, urlparse


D = Path(__file__).resolve().parent.parent
G = D.parents[1]
PATCH = D / 'combined-unapplied-reviewed2.patch'
PATCH_SHA = 'ecc2a1fc887e181b08c8fa7fc3df30a39a736277d112f1303dc9f5afb56d046b'
MANIFEST_SHA = '333802efb4a58337b0c79293c3736b642117352ca2467bc6e6eb49a1739f5bf9'
BASES = {
    'Robotron/Scripts/dqn/socket_server.py': '4a1f6a3cc7c82d8c85e1af93ceac0ca7457663d5f5ba7c7d893e3c2b3003e26c',
    'Robotron/Scripts/dqn/metrics_dashboard.py': '3013d511f1d933fe6012df5cecd7f8a8861824bdd41580cbe241b7498916f1c6',
    'Robotron/Scripts/dqn/experiment_status.py': 'e7048ec8365bca60f7bd320794c635e491407b33113e37a617f06f9f9d56c237',
}
CANDIDATES = {
    'Robotron/Scripts/dqn/rejected_gap_telemetry.py': 'd58610a139644b79f39504e48e1bc43bda9837cc51d743bec623103918c50cbd',
    'Robotron/Scripts/dqn/socket_server.py': 'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed',
    'Robotron/Scripts/dqn/metrics_dashboard.py': '3d1aa1950e6b1c5224ace3aecb9c837e433e5c36941b89465b414749f903da27',
    'Robotron/Scripts/dqn/experiment_status.py': 'aa1d018902be0875ff237e9cb3fa1bb29f066f4480123cf783a99091551d722c',
}


def authenticated(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise AssertionError('Selected fixture source changed: ' + str(path))
    return raw.decode()


def reconstruct():
    patch = authenticated(PATCH, PATCH_SHA)
    authenticated(D / 'preparation-manifest.json', MANIFEST_SHA)
    bases = {name: authenticated(G.parent / name, sha) for name, sha in BASES.items()}
    candidates = {}
    # Patch headers are column-zero, unlike all context/addition/removal lines.
    sections = re.split(r'(?m)(?=^--- )', patch)
    for section in filter(None, sections):
        rows = section.splitlines(keepends=True)
        name = rows[1].strip().removeprefix('+++ b/')
        if name not in CANDIDATES or name in candidates:
            raise AssertionError('Unexpected/duplicate patched file: ' + name)
        before = bases.get(name, '')
        lines, output, pos, i = before.splitlines(keepends=True), [], 0, 2
        while i < len(rows):
            match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*\n', rows[i])
            if match is None:
                raise AssertionError('Unexpected diff header')
            start = max(0, int(match[1]) - 1)
            if start < pos:
                raise AssertionError('Overlapping diff ranges')
            output.extend(lines[pos:start]); pos = start; i += 1
            while i < len(rows) and not rows[i].startswith('@@ '):
                mark, text = rows[i][0], rows[i][1:]
                if mark in ' -':
                    if lines[pos] != text:
                        raise AssertionError('Patch context differs')
                    if mark == ' ':
                        output.append(text)
                    pos += 1
                elif mark == '+':
                    output.append(text)
                else:
                    raise AssertionError('Unexpected diff line')
                i += 1
        output.extend(lines[pos:])
        candidate = ''.join(output)
        if hashlib.sha256(candidate.encode()).hexdigest() != CANDIDATES[name]:
            raise AssertionError('Reconstructed candidate differs: ' + name)
        candidates[name] = candidate
    if set(candidates) != set(CANDIDATES):
        raise AssertionError('Incomplete combined source fixture')
    return bases, candidates


def method(tree, class_name, name):
    cls = next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_name)
    return next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)


def compile_class(name, methods, namespace, extra=()):
    # Exact function/decorator bodies; only the surrounding dependency container
    # is synthetic. No original constructors/startup/import statements execute.
    namespace.setdefault('__name__', '_deferred_combined_stdlib')
    cls = ast.ClassDef(name=name, bases=[], keywords=[], body=deepcopy(methods),
                       decorator_list=[], type_params=[])
    module = ast.fix_missing_locations(ast.Module(body=[*deepcopy(extra), cls], type_ignores=[]))
    exec(compile(module, '<sealed combined AST fixture>', 'exec'), namespace)
    return namespace[name]


def snapshot():
    return dict(schema='robotron-rejected-gap-observation-v1', enabled=True,
                available=True, observer_error=False, counter_saturated=False,
                process_id=123, instance_monotonic_ns=456,
                counters=dict(payloads_complete=12, tracking_overflow=0),
                witnesses=[dict(cid=1, same_classifier_game=True)])


class Getter:
    def __init__(self, value=None, error=None):
        self.value = snapshot() if value is None else value
        self.error, self.calls, self.unexpected = error, 0, []

    def rejected_gap_snapshot(self):
        self.calls += 1
        if self.calls != 1:
            self.unexpected.append('Repeated snapshot call')
            raise AssertionError('Unexpected repeated snapshot/drain attempt')
        if self.error is not None:
            raise self.error
        return deepcopy(self.value)


class OwnedLock:
    def __init__(self):
        self.lock, self.owner = threading.Lock(), None

    def __enter__(self):
        self.lock.acquire(); self.owner = threading.get_ident()

    def __exit__(self, *args):
        self.owner = None; self.lock.release()


class CombinedObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.source = reconstruct()
        cls.dashboard = ast.parse(cls.source['Robotron/Scripts/dqn/metrics_dashboard.py'])
        cls.reader = ast.parse(cls.source['Robotron/Scripts/dqn/experiment_status.py'])
        cls.socket = ast.parse(cls.source['Robotron/Scripts/dqn/socket_server.py'])
        cls.APIState = compile_class('_DashboardState',
            [method(cls.dashboard, '_DashboardState', 'rejected_gap_body')], dict(json=json))
        cls.route_namespace = dict(json=json, urlparse=urlparse, parse_qs=parse_qs)
        cls.Handler = compile_class('DashboardHandler', [method(cls.dashboard, 'DashboardHandler', name)
            for name in ('do_GET', 'do_POST')], cls.route_namespace)
        helpers = [node for node in cls.reader.body if isinstance(node, ast.FunctionDef)
                   and node.name in ('_number', '_text', '_mapping')]
        limits = [node for node in cls.reader.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id in
                      ('_STATUS_LIMIT', '_PLAN_LIMIT', '_RECEIPT_LIMIT', '_MAX_LEGS') for target in node.targets)]
        cls.Reader = compile_class('ExperimentStatusReader', [method(cls.reader, 'ExperimentStatusReader', name)
            for name in ('_load', '_comparison')], dict(math=math, re=re), [*helpers, *limits])

    def api(self, server):
        unexpected = []
        class State(self.APIState):
            def __getattr__(instance, name):
                unexpected.append(('state', name)); raise AssertionError('Unexpected state attribute')
        class Metrics:
            global_server = server
            def __getattr__(instance, name):
                unexpected.append(('metrics', name)); raise AssertionError('Unexpected metrics attribute')
        state = State(); state.metrics = Metrics()
        def forbidden(*args, **kwargs):
            unexpected.append((args, kwargs)); raise AssertionError('Unexpected dashboard operation')
        for name in ('touch_web_client', 'sample', 'now_body', 'payload'):
            setattr(state, name, forbidden)
        self.addCleanup(lambda: self.assertEqual(unexpected, []))
        if isinstance(server, Getter):
            self.addCleanup(lambda: self.assertEqual(server.unexpected, []))
        return state

    def test_real_GET_route_readonly_success_has_no_heartbeat_or_now_work(self):
        server = Getter(); original = deepcopy(server.value); state = self.api(server)
        self.route_namespace['state'] = state
        handler = self.Handler(); handler.path = '/api/rejected_gaps?cid=synthetic'
        sent = []; handler._send = lambda *args, **kwargs: sent.append((args, kwargs))
        handler.do_GET()
        self.assertEqual(len(sent), 1)
        args, kwargs = sent[0]; self.assertEqual(args[1], 'application/json'); self.assertEqual(kwargs, {})
        body = json.loads(args[0]); self.assertTrue(body['available']); self.assertEqual(body['reason'], 'available')
        self.assertEqual(body['snapshot'], original); self.assertEqual(server.value, original)
        self.assertEqual(server.calls, 1); self.assertLessEqual(len(args[0]), 128 * 1024)

    def test_disabled_fault_saturation_and_overflow_remain_unavailable(self):
        cases = [('disabled', dict(enabled=False, available=False)),
                 ('observer_error', dict(observer_error=True, available=False)),
                 ('counter_saturated', dict(counter_saturated=True, available=False)),
                 ('observer_unavailable', dict(available=False, counters=dict(tracking_overflow=1)))]
        for reason, changes in cases:
            with self.subTest(reason=reason):
                value = snapshot(); value.update(changes); server = Getter(value)
                body = json.loads(self.api(server).rejected_gap_body())
                self.assertIs(body['available'], False); self.assertEqual(body['reason'], reason)
                self.assertEqual(body['snapshot'], value); self.assertEqual(server.calls, 1)

    def test_missing_server_getter_and_snapshot_error_have_no_success_zeroes(self):
        cases = [(None, 'server_unavailable'), (object(), 'getter_unavailable'),
                 (Getter(error=RuntimeError('synthetic getter error')), 'snapshot_error')]
        for server, reason in cases:
            with self.subTest(reason=reason):
                body = json.loads(self.api(server).rejected_gap_body())
                self.assertIs(body['available'], False); self.assertEqual(body['reason'], reason)
                self.assertIsNone(body['snapshot']); self.assertNotIn('synthetic getter error', str(body))

    def test_bad_schema_flags_NaN_and_oversize_are_bounded_unavailable(self):
        changes = [dict(schema='foreign'), dict(enabled='true'), dict(enabled=False),
                   dict(observer_error=True), dict(counter_saturated=True), dict(extra=float('nan')),
                   dict(extra='x' * (128 * 1024))]
        for change in changes:
            with self.subTest(change=list(change)):
                value = snapshot(); value.update(change); server = Getter(value)
                raw = self.api(server).rejected_gap_body()
                body = json.loads(raw, parse_constant=lambda value: self.fail('Nonfinite response: ' + value))
                self.assertLessEqual(len(raw), 128 * 1024); self.assertIs(body['available'], False)
                self.assertEqual(body['reason'], 'response_too_large' if isinstance(change.get('extra'), str) else 'snapshot_error')
                self.assertIsNone(body['snapshot']); self.assertEqual(server.calls, 1)

    def test_POST_does_not_enable_reset_or_read_a_body(self):
        server = Getter(); self.route_namespace['state'] = self.api(server)
        handler = self.Handler(); handler.path = '/api/rejected_gaps'; sent = []
        handler._send = lambda *args, **kwargs: sent.append((args, kwargs))
        handler.do_POST()
        self.assertEqual(sent, [((b'Not Found', 'text/plain; charset=utf-8'), dict(status=404))])
        self.assertEqual(server.calls, 0)

    def reader_fixture(self):
        reader = self.Reader(); root = PurePosixPath('/synthetic'); logs = root / 'logs'; campaign = logs / 'campaign'
        reader.game_root, reader.logs_root, reader.state_path = root, logs, logs / 'state.json'
        reader._last_good = {}; reader._clock = lambda: 200.0
        specs, progress, data = [], [], {}
        for index, role in enumerate(('reference', 'candidate', 'reference', 'candidate'), 1):
            receipt = campaign / f'{index}-{role}.json'
            label = 'protected543-01' if role == 'reference' else 'postaccepted-newgame-704M-01'
            specs.append(dict(index=index, role=role, receipt_path=str(receipt), job=dict(label=label)))
            progress.append(dict(index=index, role=role, state='finished', receipt_path=str(receipt)))
            frames = 543235763 if role == 'reference' else 704405115
            data[receipt] = dict(label=label, checkpoint_sha256=role + '-sha',
                checkpoint_metadata=dict(learner_frame_count=frames), clocks=dict(learner_frame_count=frames),
                complete=True, valid=True, count=50, mean=1.0)
        data[reader.state_path] = dict(active_quality_job=dict(directory=str(campaign)))
        data[campaign / 'status.json'] = dict(state='finished', current_leg=4, updated_unix_s=100, legs=progress)
        data[campaign / 'plan.json'] = dict(legs=specs, checkpoints={role:dict(sha256=role + '-sha',
            source=f'/NEVER-READ/{role}-first8M-999M.pt') for role in ('reference', 'candidate')})
        unexpected, reads = [], []
        def under(value, boundary, relative):
            path = PurePosixPath(value)
            if not path.is_absolute(): path = relative / path
            if '..' in path.parts or not path.is_relative_to(boundary) or path not in {*data, campaign}:
                unexpected.append(('path', str(path))); raise AssertionError('Unexpected reader path')
            return path
        def read(path, limit):
            reads.append((path, limit))
            expected = 1024 * 1024 if path.name in ('state.json', 'status.json') else 512 * 1024 if path.name == 'plan.json' else 8 * 1024 * 1024
            if path not in data or limit != expected:
                unexpected.append(('read', str(path), limit)); raise AssertionError('Unexpected reader read')
            return deepcopy(data[path])
        reader._under, reader._read = under, read
        self.addCleanup(lambda: self.assertEqual(unexpected, []))
        return reader, data, campaign, reads

    def test_real_reader_load_uses_SHA_bound_saved_totals_not_window_filename(self):
        reader, data, campaign, reads = self.reader_fixture()
        result = reader._load()
        self.assertEqual(result['comparison'], '543.2M vs 704.4M')
        self.assertEqual(len(reads), 7); self.assertEqual([leg['count'] for leg in result['legs']], [50] * 4)
        self.assertTrue(all(path.is_relative_to(PurePosixPath('/synthetic/logs')) for path, _ in reads))

    def test_missing_foreign_SHA_and_conflicting_clock_use_explicit_role_label(self):
        for mode in ('missing', 'foreign_SHA', 'conflict'):
            with self.subTest(mode=mode):
                reader, data, campaign, _ = self.reader_fixture()
                for index in (2, 4):
                    row = data[campaign / f'{index}-candidate.json']
                    if mode == 'missing': row.pop('checkpoint_metadata'); row.pop('clocks')
                    elif mode == 'foreign_SHA': row['checkpoint_sha256'] = 'foreign'
                if mode == 'conflict': data[campaign / '4-candidate.json']['checkpoint_metadata']['learner_frame_count'] += 1
                self.assertEqual(reader._load()['comparison'], '543.2M vs postaccepted-newgame-704M-01')

    def test_only_positive_finite_integer_clocks_are_labels_and_clocks_fallback_is_real(self):
        for invalid in (None, 0, -1, True, 704405115.0, float('nan'), float('inf'), '704405115'):
            with self.subTest(invalid=repr(invalid)):
                reader, data, campaign, _ = self.reader_fixture()
                for index in (2, 4):
                    data[campaign / f'{index}-candidate.json']['checkpoint_metadata']['learner_frame_count'] = invalid
                self.assertEqual(reader._load()['comparison'], '543.2M vs postaccepted-newgame-704M-01')
        reader, data, campaign, _ = self.reader_fixture()
        for index in (2, 4): data[campaign / f'{index}-candidate.json'].pop('checkpoint_metadata')
        self.assertEqual(reader._load()['comparison'], '543.2M vs 704.4M')

    def test_comparison_missing_clock_never_parses_filename_and_sanitizes_labels(self):
        plan = dict(checkpoints={role:dict(source=f'/secret/{role}-first8M-999M.pt') for role in ('reference', 'candidate')})
        self.assertEqual(self.Reader._comparison(plan, {}, []), 'reference vs candidate')
        legs = [dict(role='reference', label='  Explicit reference  '),
                dict(role='candidate', label='Candidate /private/path\n' + 'x' * 200)]
        value = self.Reader._comparison(plan, {}, legs)
        self.assertTrue(value.startswith('Explicit reference vs Candidate [path] ')); self.assertNotIn('8M', value)
        self.assertLessEqual(len(value.split(' vs ', 1)[1]), 160)

    def logging_server(self, *, shutdown=False, replay=False):
        handle = method(self.socket, 'SocketServer', 'handle_client')
        outer = next(node for node in handle.body if isinstance(node, ast.Try))
        generic = next(node for node in outer.handlers if isinstance(node.type, ast.Name) and node.type.id == 'Exception')
        base_tree = ast.parse(self.base['Robotron/Scripts/dqn/socket_server.py'])
        base_handle = method(base_tree, 'SocketServer', 'handle_client')
        base_outer = next(node for node in base_handle.body if isinstance(node, ast.Try))
        base_generic = next(node for node in base_outer.handlers if isinstance(node.type, ast.Name) and node.type.id == 'Exception')
        self.assertEqual(ast.dump(generic.body[0]), ast.dump(base_generic.body[0]))
        latch = method(self.socket, 'SocketServer', '_fail_inference_only')
        self.assertEqual(ast.dump(latch), ast.dump(method(base_tree, 'SocketServer', '_fail_inference_only')))
        wrapper = ast.parse('def record(self, cid, error):\n    try:\n        raise error\n    except Exception as e:\n        pass\n').body[0]
        wrapper.body[0].handlers[0].body = deepcopy(generic.body)
        writes, flushes = [], []
        class Stream:
            def write(stream, text):
                self.assertEqual(server._exception_log_lock.owner, threading.get_ident())
                if not shutdown and not replay:
                    self.assertIsNotNone(server.inference_only_error)  # latch precedes write
                writes.append(text)
            def flush(stream):
                self.assertEqual(server._exception_log_lock.owner, threading.get_ident())
                flushes.append(threading.get_ident())
        namespace = dict(traceback=traceback, sys=types.SimpleNamespace(stderr=Stream()))
        Logging = compile_class('Logging', [latch, wrapper], namespace)
        server = Logging(); server._exception_log_lock = OwnedLock(); server._inference_error_lock = threading.Lock()
        server.inference_only_error = None; server.replay_enabled = replay; server.shutdown_event = threading.Event()
        if shutdown: server.shutdown_event.set()
        return server, writes, flushes

    def test_eight_concurrent_actual_exception_bodies_write_complete_records_under_lock(self):
        server, writes, flushes = self.logging_server()
        barrier, failures = threading.Barrier(9, timeout=5), Queue()
        def worker(cid):
            try:
                barrier.wait(); server.record(cid, RuntimeError(f'synthetic-{cid}'))
            except BaseException as error: failures.put(repr(error))
        threads = [threading.Thread(target=worker, args=(cid,), daemon=True) for cid in range(8)]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join(timeout=5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertTrue(failures.empty(), list(failures.queue)); self.assertEqual((len(writes), len(flushes)), (8, 8))
        for cid in range(8):
            record = next(text for text in writes if text.startswith(f'Client {cid} error: synthetic-{cid}\n'))
            self.assertEqual(record.count('Traceback (most recent call last):'), 1)
            self.assertTrue(record.endswith(f'RuntimeError: synthetic-{cid}\n'))
            self.assertEqual(len(re.findall(r'(?m)^Client \d+ error:', record)), 1)

    def test_shutdown_and_replay_main_keep_the_actual_fatal_latch_semantics(self):
        for shutdown, replay in ((True, False), (False, True)):
            with self.subTest(shutdown=shutdown, replay=replay):
                server, writes, flushes = self.logging_server(shutdown=shutdown, replay=replay)
                server.record(9, RuntimeError('synthetic failure'))
                self.assertIsNone(server.inference_only_error); self.assertEqual((len(writes), len(flushes)), (1, 1))

    def test_existing_now_history_sampler_HTML_POST_and_latch_text_are_preserved(self):
        base = ast.parse(self.base['Robotron/Scripts/dqn/metrics_dashboard.py'])
        for name in ('now_body', 'payload', 'sample'):
            self.assertEqual(ast.dump(method(base, '_DashboardState', name)), ast.dump(method(self.dashboard, '_DashboardState', name)))
        for name in ('_render_dashboard_html',):
            original = next(node for node in base.body if isinstance(node, ast.FunctionDef) and node.name == name)
            candidate = next(node for node in self.dashboard.body if isinstance(node, ast.FunctionDef) and node.name == name)
            self.assertEqual(ast.dump(original), ast.dump(candidate))
        self.assertEqual(ast.dump(method(base, 'DashboardHandler', 'do_POST')), ast.dump(method(self.dashboard, 'DashboardHandler', 'do_POST')))
        init = method(self.socket, 'SocketServer', '__init__')
        locks = [node for node in ast.walk(init) if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Attribute) and target.attr == '_exception_log_lock'
                         for target in node.targets)]
        self.assertEqual(len(locks), 1)
        self.assertEqual(ast.dump(locks[0].value), ast.dump(ast.parse('threading.Lock()', mode='eval').body))


if __name__ == '__main__':
    unittest.main()
