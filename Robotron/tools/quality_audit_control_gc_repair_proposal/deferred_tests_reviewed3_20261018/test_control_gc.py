"""DEFERRED: root alone may run after the current campaign/source freeze release.

These tests execute the exact pinned stdlib-only proposal in a fresh namespace.
All subprocesses and /proc reads are strict scripted fakes. Only private temporary
fixture files and the pinned proposal source are accessible through its Path API.
No real unit, payload, process, clock wait, application import or model is used.
This suite was authored/AST-read only; it has not been imported or executed.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'control_audit_reviewed3.py'
SOURCE_SHA = 'b5a50047e1a2981a41732c756bf908c6b9b935c58d1d0503c0df494e6f863aee'
UNIT = 'robotron-deferred-GC-audit-fixture.service'
TIMER = UNIT.removesuffix('.service') + '.timer'
INV = '1' * 32
TINV = '2' * 32
PID = 43210
START = 98765


class ScriptedIO:
    """No fallback to a real API; even a swallowed unexpected call fails cleanup."""
    def __init__(self):
        self.pending = []
        self.calls = []
        self.unexpected = []

    def expect(self, argv, *, text=False, timeout=40, exit=0, stdout=b'', stderr=b'', expired=False):
        self.pending.append(dict(argv=list(argv), text=text, timeout=timeout, exit=exit,
                                 stdout=stdout, stderr=stderr, expired=expired))

    def run(self, argv, **kwargs):
        self.calls.append(list(argv))
        if not self.pending:
            self.unexpected.append(('unplanned subprocess', list(argv), kwargs))
            raise AssertionError(self.unexpected[-1])
        expected = self.pending.pop(0)
        wanted = dict(capture_output=True, timeout=expected['timeout'])
        if expected['text']:
            wanted['text'] = True
        if list(argv) != expected['argv'] or kwargs != wanted:
            self.unexpected.append(('subprocess differs', expected, list(argv), kwargs))
            raise AssertionError(self.unexpected[-1])
        if expected['expired']:
            raise subprocess.TimeoutExpired(list(argv), expected['timeout'],
                output=expected['stdout'], stderr=expected['stderr'])
        out, err = expected['stdout'], expected['stderr']
        if expected['text']:
            out = out.decode() if isinstance(out, bytes) else out
            err = err.decode() if isinstance(err, bytes) else err
        else:
            out = out.encode() if isinstance(out, str) else out
            err = err.encode() if isinstance(err, str) else err
        return types.SimpleNamespace(returncode=expected['exit'], stdout=out, stderr=err)

    def assert_drained(self):
        if self.unexpected or self.pending:
            raise AssertionError(dict(unexpected=self.unexpected, unconsumed=self.pending))


class FakeClock:
    def __init__(self):
        self.elapsed = 0.0
        self.wall_ticks = 0
        self.sleeps = []
        self.sleep_advance = None

    def monotonic(self):
        return self.elapsed

    def time(self):
        self.wall_ticks += 1
        return 2000000000.0 + self.elapsed + self.wall_ticks / 1000.0

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds if self.sleep_advance is None else self.sleep_advance


class FakeProcPath:
    def __init__(self, harness, parts=()):
        self.harness, self.parts = harness, parts

    def __truediv__(self, part):
        return FakeProcPath(self.harness, self.parts + (str(part),))

    def read_text(self):
        if self.parts != (str(PID), 'stat'):
            self.harness.unexpected_path(('unplanned fake proc read', self.parts))
        self.harness.proc_reads += 1
        # The real control indexes token19 after the closing comm parenthesis.
        return f'{PID} (synthetic auditor) ' + ' '.join(['S'] + ['0'] * 18 + [str(START)])


def encoded(fields):
    return ''.join(f'{key}={value}\n' for key, value in fields.items()).encode()


class Harness:
    def __init__(self, case, *, audit_exit=0):
        self.case = case
        self.tmp = tempfile.TemporaryDirectory(prefix='deferred-GC-stdlib-')
        self.root = Path(self.tmp.name).resolve()
        self.out = self.root / 'execution'
        self.config = self.root / 'config.json'
        self.io = ScriptedIO()
        self.clock = FakeClock()
        self.path_errors = []
        self.proc_reads = 0
        self.audit_exit = audit_exit
        raw = SOURCE.read_bytes()
        case.assertEqual(hashlib.sha256(raw).hexdigest(), SOURCE_SHA)
        self.mod = types.ModuleType('_deferred_gc_control_under_test')
        self.mod.__file__ = str(SOURCE)
        # The pinned module top level imports stdlib and defines functions only.
        exec(compile(raw, str(SOURCE), 'exec'), self.mod.__dict__)
        self.mod.subprocess = types.SimpleNamespace(run=self.io.run, TimeoutExpired=subprocess.TimeoutExpired)
        self.mod.time = self.clock
        self.mod.Path = self.path
        fixture = self.root / 'selected-source-metadata.json'
        fixture.write_text('{"synthetic":true}\n')
        fixture.chmod(0o444)
        self.c = dict(unit=UNIT, output=str(self.out),
            argv=['/usr/bin/python3.12', '-I', '-B', str(self.root / 'never-executed-auditor.py'), '--execute'],
            properties=['CPUQuota=100%', 'MemoryMax=512M', 'MemorySwapMax=0',
                        'TasksMax=128', 'RuntimeMaxSec=60', 'TimeoutStopSec=5'],
            pins=[self.mod.pin(fixture)], observation_s=60)
        self.config.write_text(json.dumps(self.c))
        self.config.chmod(0o444)
        case.addCleanup(self.close)

    def close(self):
        try:
            self.io.assert_drained()
            if self.path_errors:
                raise AssertionError(self.path_errors)
        finally:
            self.tmp.cleanup()

    def unexpected_path(self, detail):
        self.path_errors.append(detail)
        raise AssertionError(detail)

    def path(self, value):
        p = Path(value)
        if str(p) == '/proc':
            return FakeProcPath(self)
        if p != SOURCE and not p.is_relative_to(self.root):
            self.unexpected_path(('outside private fixture/source', str(p)))
        resolved = p.resolve()
        if resolved != SOURCE.resolve() and not resolved.is_relative_to(self.root):
            self.unexpected_path(('outside private fixture/source', str(p)))
        return p

    def service(self, *, live=False, absent=False, invocation=INV, exec_pid=PID):
        if absent:
            return dict(Id=UNIT, LoadState='not-found', MainPID='0')
        return dict(Id=UNIT, LoadState='loaded', InvocationID=invocation, NRestarts='0',
            MainPID=str(PID) if live else '0', ExecMainPID=str(exec_pid),
            ExecMainCode='0' if live else '1', ExecMainStatus='0' if live else str(self.audit_exit),
            ActiveState='active' if live or self.audit_exit == 0 else 'failed',
            SubState='running' if live else 'exited' if self.audit_exit == 0 else 'failed',
            Result='success' if live or self.audit_exit == 0 else 'exit-code')

    def timer(self, *, absent=False, invocation=TINV, target=UNIT):
        if absent:
            return dict(Id=TIMER, LoadState='not-found', ActiveState='inactive', SubState='dead')
        return dict(Id=TIMER, LoadState='loaded', InvocationID=invocation,
                    Unit=target, ActiveState='active', SubState='waiting')

    def show(self, unit, state, *, query=False):
        self.io.expect(['systemctl', '--user', 'show', unit], text=query,
                       timeout=20 if query else 40, stdout=encoded(state))

    def cat(self, unit, *, exit=0):
        data = '[Timer]\nUnit=' + UNIT + '\n' if unit == TIMER else '[Service]\nRestart=no\n'
        self.io.expect(['systemctl', '--user', 'cat', unit], exit=exit,
                       stdout=data.encode() if exit == 0 else b'',
                       stderr=b'Unit not found\n' if exit else b'')

    def journal(self, invocation, *, exit=0, expired=False):
        self.io.expect(['journalctl', '--user', '--no-pager', '-o', 'short-iso',
                        '_SYSTEMD_INVOCATION_ID=' + invocation], exit=exit, expired=expired,
                       stdout=b'partial raw archive\n' if expired else b'closed journal\n',
                       stderr=b'partial timeout stderr\n' if expired else b'')

    def launch_plan(self, *, timer_invocation=TINV, timer_cat_exit=0, schedule_expired=False):
        self.show(UNIT, self.service(absent=True), query=True)
        self.show(TIMER, self.timer(absent=True), query=True)
        props = ['Type=exec', 'RemainAfterExit=yes', 'Restart=no',
            'WorkingDirectory=' + str(self.mod.ROOT), 'StandardOutput=append:' + str(self.out / 'stdout.txt'),
            'StandardError=append:' + str(self.out / 'stderr.txt')] + self.c['properties']
        argv = ['systemd-run', '--user', '--unit=' + UNIT, '--on-active=3s',
            '--timer-property=AccuracySec=100ms'] + ['--property=' + p for p in props] + [
            '/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR=' + str(self.out / 'tmp')] + self.c['argv']
        self.io.expect(argv, expired=schedule_expired, stdout=b'carrier partial\n' if schedule_expired else b'')
        if not schedule_expired:
            self.cat(TIMER, exit=timer_cat_exit)
            self.show(TIMER, self.timer(invocation=timer_invocation))

    def live_prefix(self):
        self.show(UNIT, self.service(live=True), query=True)
        self.show(UNIT, self.service(live=True), query=True)
        self.show(UNIT, self.service(live=True))

    def archive_plan(self, *, timer_absent=False, service_cat_exit=0, journal_exit=0, journal_expired=False):
        self.live_prefix()
        self.show(UNIT, self.service(), query=True)
        self.show(UNIT, self.service())
        self.cat(UNIT, exit=service_cat_exit)
        self.journal(INV, exit=journal_exit, expired=journal_expired)
        self.show(TIMER, self.timer(absent=timer_absent))
        self.cat(TIMER, exit=1 if timer_absent else 0)
        self.journal(TINV)
        if timer_absent and service_cat_exit == journal_exit == 0 and not journal_expired:
            self.show(TIMER, self.timer(absent=True))  # Dedicated failed-cat GC confirmation.

    def original_guard(self):
        self.show(UNIT, self.service(), query=True)

    def timer_release(self, *, absent=False, stop_exit=0, stderr=b'', final_absent=True):
        self.show(TIMER, self.timer(absent=absent))
        if not absent:
            self.io.expect(['systemctl', '--user', 'stop', TIMER], exit=stop_exit, stderr=stderr)
            self.show(TIMER, self.timer(absent=final_absent))

    def service_release(self, *, foreign=False, reset_failed=False):
        self.show(UNIT, self.service(invocation='3' * 32 if foreign else INV))
        if foreign:
            return
        self.io.expect(['systemctl', '--user', 'stop', UNIT])
        self.show(UNIT, self.service() if reset_failed else self.service(absent=True))
        if reset_failed:
            self.io.expect(['systemctl', '--user', 'reset-failed', UNIT], exit=1, stderr=b'reset failed\n')
            self.show(UNIT, self.service())

    def launch(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.mod.launch(str(self.config))

    def observe(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.mod.observe(str(self.config))

    def cli(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.mod.main(['--execute', '--config', str(self.config),
                                  '--expected-source-sha256', SOURCE_SHA])

    def result(self):
        return json.loads((self.out / 'root-original-result-and-owned-release.json').read_bytes())

    def stops(self):
        return [c for c in self.io.calls if c[:3] == ['systemctl', '--user', 'stop']]

    def assert_raw_records(self, result):
        for record in result['full_original_archives']:
            for stream in ('stdout', 'stderr'):
                p = record[stream]
                self.case.assertTrue(Path(p['path']).is_relative_to(self.root))
                b = self.path(p['path']).read_bytes()
                self.case.assertEqual(len(b), p['bytes'])
                self.case.assertEqual(hashlib.sha256(b).hexdigest(), p['sha256'])


class DeferredGCControlTests(unittest.TestCase):
    def test_implicit_timer_cat_launch_and_strict_explicit_target(self):
        implicit = ('[Unit]\nDescription=synthetic timer with implicit same-name service\n'
                    '[Timer]\nOnActiveSec=3s\nAccuracySec=100ms\nRemainAfterElapse=no\n')
        cases = [
            ('implicit', implicit, UNIT, True),
            ('single exact explicit', implicit + 'Unit=' + UNIT + '\n', UNIT, True),
            ('foreign explicit', implicit + 'Unit=other.service\n', UNIT, False),
            ('contradictory explicit', implicit + 'Unit=' + UNIT + '\nUnit=other.service\n', UNIT, False),
            ('duplicate exact', implicit + ('Unit=' + UNIT + '\n') * 2, UNIT, False),
            ('wrong section', '[Unit]\nUnit=' + UNIT + '\n[Timer]\nOnActiveSec=3s\n', UNIT, False),
            ('no Timer section', '[Unit]\nDescription=synthetic\n', UNIT, False),
            ('duplicate Timer section', implicit + '[Timer]\n', UNIT, False),
            ('malformed explicit', implicit + 'Unit = ' + UNIT + '\n', UNIT, False),
            ('implicit but foreign show target', implicit, 'other.service', False),
        ]
        for label, cat_text, show_target, accepted in cases:
            with self.subTest(case=label):
                h = Harness(self)
                h.launch_plan()
                cat = next(x for x in h.io.pending
                           if x['argv'] == ['systemctl', '--user', 'cat', TIMER])
                cat['stdout'] = cat_text.encode()
                shown = next(x for x in h.io.pending
                             if x['argv'] == ['systemctl', '--user', 'show', TIMER]
                             and not x['text'])
                shown['stdout'] = encoded(h.timer(target=show_target))
                if accepted:
                    h.launch()
                    archive = json.loads((h.out / 'root-original-timer-launch-archive.json').read_bytes())
                    self.assertEqual((archive['unit'], archive['timer'], archive['timer_invocation_id']),
                                     (UNIT, TIMER, TINV))
                    self.assertEqual(archive['timer_cat']['exit'], 0)
                    self.assertEqual(archive['timer_show']['exit'], 0)
                    self.assertEqual(Path(archive['timer_cat']['stdout']['path']).read_text(), cat_text)
                    self.assertFalse((h.out / 'root-launch-error-preserved.json').exists())
                else:
                    with self.assertRaises(ValueError):
                        h.launch()
                    error = json.loads((h.out / 'root-launch-error-preserved.json').read_bytes())
                    self.assertEqual(error['status'], 'UNRELEASED_NO_RETRY')
                    self.assertFalse(error['unknown_units_stopped'] or error['payload_retried'])
                    self.assertFalse((h.out / 'root-original-timer-launch-archive.json').exists())
                    with self.assertRaisesRegex(ValueError, 'authenticated one launch'):
                        h.observe()
                self.assertEqual(sum(x[0] == 'systemd-run' for x in h.io.calls), 1)
                self.assertEqual(h.stops(), [])
                self.assertEqual(h.proc_reads, 0)
                self.assertFalse((h.out / 'root-original-identity.json').exists())

    def test_default_plan_has_no_function_level_reads_or_operations(self):
        h = Harness(self)
        h.mod.Path = lambda *_: self.fail('default PLAN read a path')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(h.mod.main([]), 0)
        self.assertEqual(h.io.calls, [])
        self.assertEqual(h.proc_reads, 0)

    def test_audit0_normal_sameprocess_and_all_six_successes(self):
        h = Harness(self)
        h.launch_plan(); h.archive_plan(); h.original_guard(); h.timer_release(); h.service_release()
        self.assertEqual(h.cli(), 0)
        r = h.result()
        self.assertTrue(r['lifecycle_complete'] and r['unit_released'] and r['audit_success'])
        self.assertEqual(r['original_exit'], 0)
        self.assertEqual([x['exit'] for x in r['full_original_archives']], [0] * 6)
        self.assertTrue(r['all_six_original_archive_commands_succeeded'])
        self.assertEqual(h.stops(), [['systemctl', '--user', 'stop', TIMER], ['systemctl', '--user', 'stop', UNIT]])
        self.assertEqual(h.proc_reads, 1)
        h.assert_raw_records(r)

    def test_audit2_timer_GC_has_real_cat1_and_no_fabricated_timer_stop(self):
        h = Harness(self, audit_exit=2)
        h.launch_plan(); h.archive_plan(timer_absent=True); h.original_guard()
        h.timer_release(absent=True); h.service_release()
        self.assertEqual(h.cli(), 2)
        r = h.result()
        self.assertEqual((r['original_exec_code'], r['original_exit'], r['original_result']), (1, 2, 'exit-code'))
        self.assertFalse(r['audit_success'])
        self.assertTrue(r['lifecycle_complete'] and r['unit_released'])
        self.assertEqual([x['exit'] for x in r['full_original_archives']], [0, 0, 0, 0, 1, 0])
        self.assertFalse(r['all_six_original_archive_commands_succeeded'])
        self.assertTrue(r['original_archived_before_release'])
        self.assertIsNone(r['owned_release'][0]['stop'])
        self.assertEqual(h.stops(), [['systemctl', '--user', 'stop', UNIT]])
        h.assert_raw_records(r)

    def test_stop5_accepts_only_each_exact_owned_reason_and_fresh_absence(self):
        for reason in (f'Unit {TIMER} not loaded.\n', f'Failed to stop {TIMER}: Unit {TIMER} not loaded.\n'):
            with self.subTest(reason=reason):
                h = Harness(self, audit_exit=2)
                h.launch_plan(); h.archive_plan(); h.original_guard()
                h.timer_release(stop_exit=5, stderr=reason.encode()); h.service_release()
                self.assertEqual(h.cli(), 2)
                r = h.result(); timer = r['owned_release'][0]
                self.assertTrue(r['unit_released'] and r['lifecycle_complete'])
                self.assertEqual(timer['stop']['exit'], 5)
                self.assertEqual(timer['classification'], 'timer_autoGC_race_stop5_preserved')
                self.assertEqual(Path(timer['stop']['stderr']['path']).read_bytes(), reason.encode())
                self.assertEqual(len(h.stops()), 2)

    def test_wrong_stop5_reason_or_not_absent_keeps_cleanup_incomplete(self):
        for reason, absent in [(b'arbitrary exit5\n', True),
                (b'Failed to stop other.timer: Unit other.timer not loaded.\n', True),
                (b'\xff', True), (f'Unit {TIMER} not loaded.\n'.encode(), False)]:
            with self.subTest(reason=reason, absent=absent):
                h = Harness(self, audit_exit=2)
                h.launch_plan(); h.archive_plan(); h.original_guard()
                h.timer_release(stop_exit=5, stderr=reason, final_absent=absent)
                self.assertEqual(h.cli(), 2)
                r = h.result()
                self.assertFalse(r['unit_released'] or r['lifecycle_complete'])
                self.assertEqual(r['original_exit'], 2)
                self.assertEqual(r['owned_release'][0]['stop']['exit'], 5)
                self.assertFalse(r['owned_release'][0]['confirmed_absent'])
                self.assertEqual(h.stops(), [['systemctl', '--user', 'stop', TIMER]])

    def test_foreign_timer_is_not_stopped(self):
        h = Harness(self, audit_exit=2)
        h.launch_plan(); h.archive_plan(); h.original_guard()
        h.show(TIMER, h.timer(invocation='3' * 32))
        self.assertEqual(h.cli(), 2)
        r = h.result()
        self.assertEqual(r['original_exit'], 2)
        self.assertFalse(r['unit_released'] or r['lifecycle_complete'])
        self.assertEqual(h.stops(), [])
        self.assertIsNone(r['owned_release'][0]['stop'])

    def test_foreign_service_after_timer_release_is_not_stopped(self):
        h = Harness(self, audit_exit=2)
        h.launch_plan(); h.archive_plan(); h.original_guard(); h.timer_release(); h.service_release(foreign=True)
        self.assertEqual(h.cli(), 2)
        r = h.result()
        self.assertTrue(r['owned_release'][0]['confirmed_absent'])
        self.assertFalse(r['owned_release'][1]['confirmed_absent'])
        self.assertFalse(r['unit_released'] or r['lifecycle_complete'])
        self.assertEqual(h.stops(), [['systemctl', '--user', 'stop', TIMER]])

    def test_launch_requires_actual_timer_invocation_and_successful_cat(self):
        for inv, cat_exit in [('', 0), (TINV, 1)]:
            with self.subTest(inv=inv, cat_exit=cat_exit):
                h = Harness(self)
                h.launch_plan(timer_invocation=inv, timer_cat_exit=cat_exit)
                with self.assertRaises(ValueError):
                    h.launch()
                r = json.loads((h.out / 'root-launch-error-preserved.json').read_bytes())
                self.assertFalse(r['unknown_units_stopped'] or r['payload_retried'])
                self.assertEqual(h.stops(), [])
                self.assertFalse((h.out / 'root-original-identity.json').exists())

    def test_observe_cannot_adopt_without_its_own_launch(self):
        h = Harness(self)
        with self.assertRaisesRegex(ValueError, 'authenticated one launch'):
            h.observe()
        self.assertEqual(h.io.calls, [])
        self.assertFalse(h.out.exists())

    def test_changed_launch_archive_refuses_without_cleanup(self):
        h = Harness(self)
        h.launch_plan(); h.launch()
        p = h.out / 'root-original-timer-launch-archive.json'
        p.chmod(0o644); p.write_text('{}\n'); p.chmod(0o444)
        with self.assertRaisesRegex(ValueError, 'archive changed'):
            h.observe()
        self.assertEqual(h.stops(), [])
        self.assertEqual(h.proc_reads, 0)

    def test_changed_selected_PIN_is_rejected_before_scheduling(self):
        h = Harness(self)
        fixture = Path(h.c['pins'][0]['path'])
        fixture.chmod(0o644); fixture.write_text('changed synthetic metadata\n'); fixture.chmod(0o444)
        h.show(UNIT, h.service(absent=True), query=True)
        h.show(TIMER, h.timer(absent=True), query=True)
        with self.assertRaisesRegex(ValueError, 'PIN changed'):
            h.launch()
        self.assertFalse((h.out / 'root-launch-intent.json').exists())
        self.assertEqual(sum(c[0] == 'systemd-run' for c in h.io.calls), 0)
        self.assertEqual(h.stops(), [])

    def test_changed_config_after_launch_is_not_accepted(self):
        h = Harness(self)
        h.launch_plan(); h.launch()
        changed = dict(h.c, observation_s=61)
        h.config.chmod(0o644); h.config.write_text(json.dumps(changed)); h.config.chmod(0o444)
        before = len(h.io.calls)
        with self.assertRaisesRegex(ValueError, 'unchanged config'):
            h.observe()
        self.assertEqual(len(h.io.calls), before)
        self.assertEqual(h.stops(), [])
        self.assertFalse((h.out / 'root-original-result-and-owned-release.json').exists())

    def test_missed_live_identity_is_not_retrospectively_adopted(self):
        h = Harness(self, audit_exit=2)
        h.launch_plan(); h.launch(); h.show(UNIT, h.service(), query=True)
        r = h.observe()
        self.assertIsNone(r['original'])
        self.assertIsNone(r['original_exit'])
        self.assertFalse(r['unit_released'] or r['lifecycle_complete'])
        self.assertEqual(r['full_original_archives'], [])
        self.assertEqual(h.stops(), [])
        self.assertEqual(h.proc_reads, 0)

    def test_deadline_leaves_observed_original_untouched(self):
        h = Harness(self)
        h.launch_plan(); h.launch(); h.live_prefix()
        h.clock.sleep_advance = 61
        r = h.observe()
        self.assertEqual(r['original']['pid'], PID)
        self.assertEqual(r['original']['starttime_ticks'], START)
        self.assertIsNone(r['original_exit'])
        self.assertIn('Observational deadline', r['error'])
        self.assertFalse(r['unit_released'] or r['lifecycle_complete'])
        self.assertEqual(h.stops(), [])
        self.assertEqual(h.clock.sleeps, [2])

    def test_archive_timeout_preserves_partial_bytes_and_unknown_exit(self):
        h = Harness(self, audit_exit=2)
        h.launch_plan(); h.archive_plan(journal_expired=True)
        self.assertEqual(h.cli(), 2)
        r = h.result(); record = r['full_original_archives'][2]
        self.assertIsNone(record['exit'])
        self.assertTrue(record['timed_out'])
        self.assertEqual(Path(record['stdout']['path']).read_bytes(), b'partial raw archive\n')
        self.assertEqual(Path(record['stderr']['path']).read_bytes(), b'partial timeout stderr\n')
        self.assertFalse(r['all_six_original_archive_commands_succeeded'])
        self.assertFalse(r['unit_released'] or r['lifecycle_complete'])
        self.assertEqual(r['original_exit'], 2)
        self.assertEqual(h.stops(), [])
        h.assert_raw_records(r)

    def test_archive_failure_does_not_turn_payload0_into_lifecycle0(self):
        h = Harness(self)
        h.launch_plan(); h.archive_plan(service_cat_exit=7)
        self.assertEqual(h.cli(), 1)
        r = h.result()
        self.assertEqual(r['original_exit'], 0)
        self.assertTrue(r['audit_success'])
        self.assertEqual([x['exit'] for x in r['full_original_archives']], [0, 7, 0, 0, 0, 0])
        self.assertFalse(r['unit_released'] or r['lifecycle_complete'])
        self.assertEqual(h.stops(), [])

    def test_reset_failure_preserves_partial_owned_release_and_audit2(self):
        h = Harness(self, audit_exit=2)
        h.launch_plan(); h.archive_plan(); h.original_guard(); h.timer_release(); h.service_release(reset_failed=True)
        self.assertEqual(h.cli(), 2)
        r = h.result()
        self.assertEqual(r['original_exit'], 2)
        self.assertTrue(r['owned_release'][0]['confirmed_absent'])
        self.assertEqual(r['owned_release'][1]['reset_failed']['exit'], 1)
        self.assertFalse(r['owned_release'][1]['confirmed_absent'])
        self.assertFalse(r['unit_released'] or r['lifecycle_complete'])

    def test_repeated_launch_and_observe_are_refused(self):
        h = Harness(self)
        h.launch_plan(); h.launch()
        with self.assertRaisesRegex(ValueError, 'One scheduling attempt'):
            h.launch()
        h.archive_plan(); h.original_guard(); h.timer_release(); h.service_release()
        self.assertTrue(h.observe()['lifecycle_complete'])
        before = len(h.io.calls)
        with self.assertRaisesRegex(ValueError, 'One observation only'):
            h.observe()
        self.assertEqual(len(h.io.calls), before)

    def test_scheduling_timeout_is_not_retried_or_released(self):
        h = Harness(self)
        h.launch_plan(schedule_expired=True)
        with self.assertRaisesRegex(ValueError, 'never retry'):
            h.launch()
        r = json.loads((h.out / 'root-launch-error-preserved.json').read_bytes())
        raw = json.loads((h.out / 'root-scheduling-carrier-command.json').read_bytes())
        self.assertIsNone(raw['exit'])
        self.assertTrue(raw['timed_out'])
        self.assertFalse(r['unknown_units_stopped'] or r['payload_retried'])
        self.assertEqual(h.stops(), [])
        self.assertEqual(sum(c[0] == 'systemd-run' for c in h.io.calls), 1)


if __name__ == '__main__':
    unittest.main()
