"""Six source-bound synthetic lifecycle groups. Root executes, authors do not.

The actual selected Stop class and actual CAS/file helpers are AST-extracted.
Only the kernel/process/socket/unit/clock collaborators are synthetic. No live
unit, /proc, cgroup, network, model, MAME or scientific data is accessed.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import struct
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch


STOP_SOURCE = {
    'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/stop-sources/stop_owned_current_round_training_v3.py',
    'sha256': 'fe4a804db13347a74af512bca37adaf9aeb4660025cc9efe373b22a086ded7db',
}
UTIL_SOURCE = {
    'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027/preview-flags-preserveRAM-trainer-restart-original01/stop-sources/current192_linux_stop_v1.py',
    'sha256': '3268d0bf2e18d3a7aa9c09addd331b1e42353be45c666203f0818caf294d7437',
}


def selected(entry):
    if not isinstance(entry, dict):
        raise ValueError('Unselected future source; no fallback')
    raw = Path(entry['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise ValueError('Exact selected actual source required')
    return ast.parse(raw, filename=entry['path'])


def actual_module():
    tree = selected(STOP_SOURCE)
    names = {'require', 'Stop'}
    body = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
            and node.name in names]
    ns = dict(__name__='_synthetic_actual_stop', Path=Path, json=json, os=os,
              signal=signal, socket=socket, struct=struct, re=re, stat=stat,
              hashlib=hashlib, subprocess=subprocess, time=None, CGROUP=None,
              CLOCKS=('frame_count', 'learner_frame_count', 'training_steps', 'optimized_samples'),
              PERSISTENT=('Thread-1 (serve', 'Thread-2 (_samp', 'Thread-3 (_cons',
                          'Thread-4 (start', 'Thread-5 (stats'))
    exec(compile(ast.Module(body=body, type_ignores=[]), STOP_SOURCE['path'], 'exec'), ns)
    utilities = selected(UTIL_SOURCE)
    keep = {'require', 'full_pin', 'checked', 'publish', 'atomic_owned_replace'}
    un = dict(Path=Path, os=os, json=json, stat=stat, hashlib=hashlib, re=re)
    exec(compile(ast.Module(body=[n for n in utilities.body if isinstance(n, ast.FunctionDef)
                                 and n.name in keep], type_ignores=[]), UTIL_SOURCE['path'], 'exec'), un)
    return ns, types.SimpleNamespace(**{k: un[k] for k in keep})


class Clock:
    def __init__(self):
        self.now = 100.

    def monotonic(self):
        return self.now

    def time(self):
        return 1700000000. + self.now

    def sleep(self, seconds):
        self.now += seconds


class Probe:
    def __init__(self, trace):
        self.trace, self.closed, self.sent = trace, False, []

    def close(self):
        self.trace.append('probe-close')
        self.closed = True

    def sendall(self, value):
        self.sent.append(value)

    def recv(self, size):
        return bytes(size)


class SyntheticCGPath(type(Path())):
    """Emulate only kernel-generated cgroup files/moving a single thread."""
    def write_text(self, data, *args, **kwargs):
        result = super().write_text(data, *args, **kwargs)
        if self.name == 'cgroup.threads' and data.strip():
            for child in self.parent.iterdir():
                if child.is_dir() and (child/'cgroup.threads').exists():
                    if (child/'cgroup.threads').read_text().strip() == data.strip():
                        (child/'cgroup.threads').write_text('')
        return result

    def rmdir(self):
        if (self/'cgroup.threads').exists() and not (self/'cgroup.threads').read_text().strip():
            for child in self.iterdir():
                if child.name in {'cgroup.threads', 'cgroup.freeze', 'cgroup.type', 'cgroup.events'}:
                    child.unlink()
        return super().rmdir()


class Harness:
    def __init__(self, ns, utils, directory):
        self.ns, self.utils, self.directory = ns, utils, directory
        self.trace, self.events = [], []
        self.clock = Clock(); ns['time'] = self.clock
        self.cg = directory/'cgroup'; self.cg.mkdir()
        self.root = self.cg/'trainer'; self.root.mkdir()
        (self.root/'cgroup.procs').write_text('101\n')
        (self.root/'cgroup.threads').write_text('')
        ns['CGROUP'] = self.cg
        s = ns['Stop'].__new__(ns['Stop']); self.s = s
        s.u = utils
        s.owner = dict(pid=101, starttime_ticks=1001, unit='robotron-trainer.service',
                       invocation_id='trainer-original', cgroup='/trainer')
        s.fleet = dict(pid=201, starttime_ticks=2001, unit='robotron-mame.service',
                       invocation_id='fleet-original', cgroup='/fleet')
        self.owners = {x['unit']: copy.deepcopy(x) for x in (s.owner, s.fleet)}
        def live(owner):
            if self.owners.get(owner['unit']) != owner:
                raise ValueError('Exact live original owner changed')
            return dict(MainPID=str(owner['pid']), InvocationID=owner['invocation_id'],
                        ControlGroup=owner['cgroup'], NRestarts='0', SubState='running',
                        KillSignal='15' if owner['pid'] == 201 else '2',
                        KillMode='mixed' if owner['pid'] == 201 else 'control-group',
                        SendSIGKILL='no', Restart='on-failure')
        s.u = types.SimpleNamespace(**vars(utils), live_owner=live)
        s.control = directory/'learning_control.json'
        s.base = (json.dumps(dict(lr_scale=.0625, measurement=None))+'\n').encode()
        s.control.write_bytes(s.base); s.control_pin = utils.full_pin(s.control)
        s.case = 'continuous-stop-synthetic'
        s.out = directory/'output'; s.out.mkdir()
        s.probe = None; s.probe_tid = None; s.probe_id = 7
        s.holds = {}; s.current_pause = None
        s.signal_sent = dict(fleet=False, trainer=False)
        s.final_API = None; s.counter = 0
        s.old_handlers = {}
        s.actor_births = [dict(pid=202, starttime_ticks=2002, slot=0)]
        s.job = dict(boot_saved_clocks=dict(frame_count=1000, optimized_samples=4000,
                                         measurement_frame_count=100), console=str(directory/'console'))
        self.births = {101: 1001, 201: 2001, 202: 2002}
        ns['birth'] = lambda pid, tid=None: self.births.get(tid if tid is not None else pid)
        def event(name, value):
            self.events.append((name, copy.deepcopy(value)))
            return dict(path=str(s.out/name), synthetic=True)
        s.event = event
        s.preflight = lambda: self.trace.append('preflight')
        def population():
            self.trace.append('whole-population-closed')
            self.births.pop(201, None); self.births.pop(202, None)
        s.close_population = population
        def open_probe():
            self.trace.append('open-probe')
            s.probe = Probe(self.trace)
            s.probe_tid = dict(tid=301, starttime_ticks=3001)
            self.births[301] = 3001
        s.open_probe = open_probe
        self.close_probe_birth = True
        def hold(kind, comm):
            self.trace.append('hold-'+kind)
            child = self.root/kind.lower(); child.mkdir()
            for key, value in [('cgroup.threads', ''), ('cgroup.freeze', '1\n'),
                               ('cgroup.type', 'threaded\n'), ('cgroup.events', 'frozen 1\n')]:
                (child/key).write_text(value)
            s.holds[kind] = dict(path=str(child), tid=401 if kind == 'GAME' else 402, birth=4001)
        s.hold = hold
        def pause(purpose):
            self.trace.append('pause-'+purpose)
            s.current_pause = dict(label=s.case+'-'+purpose, generation=1 if purpose == 'drain' else 3)
        s.pause = pause
        s.marker = lambda: self.trace.append('FIFO-'+s.current_pause['label'].rsplit('-', 1)[1])
        s.cancel_pause_and_drain = lambda: self.trace.append('budget-exhausted')
        def sealed():
            self.trace.append('bank-sealed')
            return {'synthetic_bank_seal': True}
        s.seal_banks = sealed
        def stopped(seal):
            self.trace.append('SIGINT-final-save')
            s.signal_sent['trainer'] = True
            return {'synthetic_stopped_authority': True}
        s.stop_trainer = stopped
        def api():
            if self.close_probe_birth and s.probe is None:
                self.births.pop(301, None)
            request = json.loads(s.control.read_bytes()).get('measurement')
            pause = s.current_pause or dict(label=request['label'] if request else s.case+'-drain', generation=1)
            active = s.current_pause is not None or request is not None
            return dict(client_count=0 if s.probe is None else 1,
                client_rows=[] if s.probe is None else [dict(client_id=7)],
                training_enabled=not active, measurement_active=active,
                managed_measurement=dict(pause, active=active,
                                         phase='warming' if active else 'finished'),
                frame_count=1100, measurement_frames=100, optimized_samples=4800,
                host_pipeline=dict(learning_exposure=dict(optimizer=dict(
                    total=dict(attempts_started=10, outcomes_recorded=10, unavailable=0),
                    unclassified_started_total=0))))
        self.default_api = api; s.api = api
        # run waits for the handler birth before its API-zero check.
        self.original_probe = None
        original_open = s.open_probe
        def open_with_reap():
            original_open()
            self.original_probe = s.probe
            close = s.probe.close
            def close_and_reap():
                close()
                if self.close_probe_birth:
                    self.births.pop(301, None)
            s.probe.close = close_and_reap
        s.open_probe = open_with_reap
        def release(kind):
            self.trace.append('release-'+kind)
            old = ns['Path']; ns['Path'] = SyntheticCGPath
            try:
                return ns['Stop'].release(s, kind)
            finally:
                ns['Path'] = old
        s.release = release

    def run(self):
        return self.ns['Stop'].run(self.s)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.ns, self.u = actual_module()

    def harness(self, name):
        directory = self.base/name; directory.mkdir()
        return Harness(self.ns, self.u, directory)

    def test_01_whole_population_closes_before_any_final_save(self):
        h = self.harness('ordered'); s = h.s
        result = h.run()
        self.assertEqual(result['status'], 'ORIGINAL_POPULATION_AND_TRAINER_STOPPED_CPU_VERIFICATION_REQUIRED')
        self.assertEqual(result['cleanup_errors'], [])
        order = ['preflight', 'whole-population-closed', 'open-probe', 'hold-GAME',
                 'pause-drain', 'FIFO-drain', 'budget-exhausted', 'pause-final',
                 'FIFO-final', 'probe-close', 'bank-sealed', 'SIGINT-final-save']
        self.assertEqual(h.trace[:len(order)], order)
        self.assertFalse(s.holds)
        # Actual run cannot continue to probe/save if original population closure fails.
        bad = self.harness('population-not-closed')
        def refuse():
            bad.trace.append('population-refused')
            raise ValueError('Original actor remains')
        bad.s.close_population = refuse
        result = bad.run()
        self.assertIn('Original actor remains', result['error'])
        self.assertNotIn('open-probe', bad.trace)
        self.assertNotIn('SIGINT-final-save', bad.trace)

    def test_02_actual_FIFO_ack_failures_forbid_SIGINT(self):
        for variant in ('not-ready', 'wrong-generation', 'wrong-client', 'closed-response'):
            with self.subTest(variant=variant):
                h = self.harness('FIFO-'+variant); s = h.s
                s.marker = lambda: self.ns['Stop'].marker(s)
                old_api = s.api
                def api():
                    value = old_api()
                    value['managed_measurement']['boundary'] = dict(
                        ready=variant != 'not-ready',
                        generation=s.current_pause['generation']+(variant == 'wrong-generation'),
                        acknowledged_client_ids=[8 if variant == 'wrong-client' else 7])
                    return value
                s.api = api
                if variant == 'closed-response':
                    old_open = s.open_probe
                    def opened():
                        old_open(); s.probe.recv = lambda size: b''
                    s.open_probe = opened
                result = h.run()
                self.assertEqual(result['status'], 'ORIGINAL_STOP_INCOMPLETE')
                self.assertFalse(s.signal_sent['trainer'])
                self.assertNotIn('bank-sealed', h.trace)
                self.assertNotIn('SIGINT-final-save', h.trace)
                self.assertTrue(h.original_probe.closed)
                self.assertFalse(s.holds)

    def test_03_actual_budget_and_producer_fences_forbid_final_save(self):
        for variant in ('insufficient', 'in-flight', 'unavailable', 'foreign-client'):
            with self.subTest(variant=variant):
                h = self.harness('budget-'+variant); s = h.s
                s.cancel_pause_and_drain = lambda: self.ns['Stop'].cancel_pause_and_drain(s)
                old_api = s.api
                def api():
                    value = old_api()
                    if s.control.read_bytes() == s.base:
                        value['measurement_active'] = False; value['training_enabled'] = True
                        value['managed_measurement'].update(active=False, phase='finished')
                    value['client_count'] = 1; value['client_rows'] = [dict(client_id=7)]
                    if variant == 'insufficient': value['optimized_samples'] = 4799
                    if variant == 'in-flight':
                        o = value['host_pipeline']['learning_exposure']['optimizer']
                        o['total']['attempts_started'] = 11; o['unclassified_started_total'] = 1
                    if variant == 'unavailable':
                        value['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable'] = 1
                    if variant == 'foreign-client': value['client_rows'][0]['client_id'] = 8
                    return value
                s.api = api
                result = h.run()
                self.assertIn('error', result)
                self.assertFalse(s.signal_sent['trainer'])
                self.assertNotIn('pause-final', h.trace)
                self.assertNotIn('bank-sealed', h.trace)
                self.assertFalse(s.holds)
                self.assertEqual(s.control.read_bytes(), s.base)

    def test_04_actual_owned_original_stop_is_one_shot_and_not_retargeted(self):
        h = self.harness('original'); s = h.s
        fleet_root = h.cg/'fleet'; fleet_root.mkdir(); (fleet_root/'cgroup.procs').write_text('')
        s.api = lambda: dict(client_count=0)
        s.archive_unit = lambda owner, label: h.trace.append('archive-'+label)
        requests = []
        def manual_stop(argv, **kwargs):
            requests.append(argv); h.births.pop(201, None); h.births.pop(202, None)
            return types.SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        terminal = dict(ExecMainPID='201', ExecMainCode='1', ExecMainStatus='0', NRestarts='0', MainPID='0')
        with patch.object(subprocess, 'run', side_effect=manual_stop):
            self.ns['show'] = lambda unit: terminal
            self.ns['Stop'].close_population(s)
            with self.assertRaisesRegex(ValueError, 'One original manual service stop only'):
                self.ns['Stop'].close_population(s)
        self.assertEqual(requests, [['systemctl', '--user', 'stop', '--no-block', 'robotron-mame.service']])
        # Exact owner incarnation change must fail before any new signal.
        wrong = self.harness('foreign-owner'); wrong.s.api = s.api
        wrong.owners[wrong.s.fleet['unit']]['invocation_id'] = 'replacement'
        with patch.object(subprocess, 'run', side_effect=AssertionError('Never stop replacement')):
            with self.assertRaisesRegex(ValueError, 'Exact live original owner changed'):
                self.ns['Stop'].close_population(wrong.s)
        self.assertFalse(wrong.s.signal_sent['fleet'])
        # A changed terminal result cannot authorize final save or a second signal.
        bad = self.harness('abnormal-terminal'); bad.s.api = s.api
        (bad.cg/'fleet').mkdir(); (bad.cg/'fleet/cgroup.procs').write_text('')
        self.ns['show'] = lambda unit: dict(terminal, ExecMainStatus='1')
        def bad_stop(argv, **kwargs):
            bad.births.pop(201, None); bad.births.pop(202, None)
            return types.SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        with patch.object(subprocess, 'run', side_effect=bad_stop):
            with self.assertRaisesRegex(ValueError, 'normal0/no-restart'):
                self.ns['Stop'].close_population(bad.s)
        self.assertTrue(bad.s.signal_sent['fleet'])
        self.assertFalse(bad.s.signal_sent['trainer'])
        # Unknown StopUnit delivery is recorded exactly once and never retried.
        timeout = self.harness('stop-delivery-unknown')
        with patch.object(subprocess, 'run', side_effect=subprocess.TimeoutExpired(['synthetic'], 15)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.ns['Stop'].request_stop(timeout.s, 'fleet', timeout.s.fleet)
            with self.assertRaisesRegex(ValueError, 'One original manual service stop only'):
                self.ns['Stop'].request_stop(timeout.s, 'fleet', timeout.s.fleet)
        self.assertEqual(run.call_count, 1)
        self.assertIn('unknown', next(v for n, v in timeout.events if n == 'fleet-manual-stop-command.json')['error'])
        # Exercise actual API's ordinary 0/1 in-flight rule; unknown outcomes still fail.
        api_h = self.harness('API-exposure'); api_s = api_h.s
        api_s.job.update(experiment='synthetic-exact', exposure_instances=dict(optimizer=11, replay=12))
        class Response:
            def __init__(self, raw): self.raw = raw
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return self.raw[:size]
        for gap in (0, 1, 2):
            total = dict(attempts_started=10+gap, outcomes_recorded=10, applied=10, amp_skipped=0, unavailable=0)
            exposure = dict(process_id=101, epoch=1, enabled=True,
                instance_monotonic_ns=11, total=total, since_epoch=dict(unavailable=0),
                unclassified_started_total=gap, available=gap == 0)
            raw = json.dumps(dict(ts=api_h.clock.time(), pipeline_snapshot_age_s=0,
                pipeline_read_error='', bank_persistence_read_error='', managed_experiment='synthetic-exact',
                lr=3.125e-6, host_pipeline=dict(available=True, generation=0,
                    inference=dict(errors=0), actor_refresh=dict(errors=0), target_refresh=dict(errors=0),
                    learner_priority=dict(errors=0), learning_exposure=dict(optimizer=exposure,
                        replay=dict(process_id=101, epoch=1, enabled=True, available=True,
                                    instance_monotonic_ns=12))))).encode()
            self.ns['urllib'] = types.SimpleNamespace(request=types.SimpleNamespace(urlopen=lambda *a, **k: Response(raw)))
            if gap < 2:
                self.ns['Stop'].api(api_s)
            else:
                with self.assertRaisesRegex(ValueError, 'Only one ordinary in-flight'):
                    self.ns['Stop'].api(api_s)

    def test_05_failures_release_only_owned_probe_and_exact_holds(self):
        for failure in ('marker', 'interrupt'):
            h = self.harness('cleanup-'+failure); s = h.s
            foreign = h.root/'foreign'; foreign.mkdir()
            (foreign/'cgroup.threads').write_text('909\n'); (foreign/'cgroup.freeze').write_text('1\n')
            def fail():
                h.births[401] = 4001
                (Path(s.holds['GAME']['path'])/'cgroup.threads').write_text('401\n')
                if failure == 'interrupt': raise KeyboardInterrupt('Synthetic controller SIGTERM')
                raise ValueError('Synthetic FIFO failure')
            s.marker = fail
            result = h.run()
            self.assertEqual(result['status'], 'ORIGINAL_STOP_INCOMPLETE')
            self.assertTrue(h.original_probe.closed)
            self.assertFalse(s.holds)
            self.assertEqual(result['cleanup_errors'], [])
            self.assertEqual((foreign/'cgroup.threads').read_text(), '909\n')
            self.assertEqual((foreign/'cgroup.freeze').read_text(), '1\n')
            self.assertFalse(s.signal_sent['trainer'])
        # Actual release refuses any foreign task; no move/thaw/delete is allowed.
        h = self.harness('foreign-thread'); s = h.s
        s.hold('GAME', 'Thread-4 (start'); item = s.holds['GAME']
        child = Path(item['path']); (child/'cgroup.threads').write_text('909\n')
        with self.assertRaisesRegex(ValueError, 'Foreign held task'):
            s.release('GAME')
        self.assertEqual((child/'cgroup.freeze').read_text(), '1\n')
        self.assertEqual((child/'cgroup.threads').read_text(), '909\n')
        self.assertIn('GAME', s.holds)
        # Even owned socket-close failure cannot prevent the remaining cleanup.
        h = self.harness('probe-close-error'); s = h.s
        s.pause = lambda purpose: self.ns['Stop'].pause(s, purpose)
        old_open = s.open_probe
        def opened():
            old_open()
            def close_error(): raise OSError('Synthetic close failure')
            s.probe.close = close_error
        s.open_probe = opened
        s.marker = lambda: (_ for _ in ()).throw(ValueError('Synthetic earlier failure'))
        result = h.run()
        self.assertEqual([x['kind'] for x in result['cleanup_errors']], ['owned_probe_close'])
        self.assertFalse(s.holds)
        self.assertEqual(s.control.read_bytes(), s.base)

    def test_06_actual_control_CAS_never_overwrites_foreign_bytes(self):
        h = self.harness('CAS'); s = h.s
        s.pause = lambda purpose: self.ns['Stop'].pause(s, purpose)
        foreign = b'{"lr_scale":0.03125,"measurement":{"label":"foreign"}}\n'
        def changed_then_fail():
            temporary = s.control.with_name('foreign-control.tmp')
            temporary.write_bytes(foreign); os.replace(temporary, s.control)
            raise ValueError('Stop refused after foreign control replacement')
        s.marker = changed_then_fail
        result = h.run()
        self.assertEqual(s.control.read_bytes(), foreign)
        self.assertEqual(result['status'], 'ORIGINAL_STOP_INCOMPLETE')
        self.assertTrue(h.original_probe.closed); self.assertFalse(s.holds)
        self.assertEqual([x['kind'] for x in result['cleanup_errors']], ['owned_control_restore'])
        self.assertIn('Owned mutable input changed', result['cleanup_errors'][0]['error'])
        self.assertNotIn('SIGINT-final-save', h.trace)
        # Actual helper also refuses same bytes whose held identity was replaced.
        target = self.base/'same-bytes-control'; target.write_bytes(b'base\n')
        prior = self.u.full_pin(target)
        replacement = self.base/'new-inode'; replacement.write_bytes(b'base\n'); os.replace(replacement, target)
        with self.assertRaisesRegex(RuntimeError, 'Owned mutable input changed'):
            self.u.atomic_owned_replace(target, prior, b'changed\n', suffix='synthetic')
        self.assertEqual(target.read_bytes(), b'base\n')


if __name__ == '__main__':
    raise SystemExit('Root CPU driver only; direct author execution is disabled')
