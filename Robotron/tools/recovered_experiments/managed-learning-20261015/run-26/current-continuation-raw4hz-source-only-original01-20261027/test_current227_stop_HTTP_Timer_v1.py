"""NEW focused CPU checks of staged source definitions; no real backend/job.

AST-selected definitions execute with explicit fake/temp collaborators. No
application main, Torch, GPU, actual /proc/cgroup, unit, socket or signal access.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
S = HERE / 'stop-sources'
LINUX = S / 'current227_linux_stop_v1.py'
RECOVERY = S / 'current227_stop_recovery_v1.py'
POSTSTOP = S / 'current227_poststop_only_v1.py'
CONTROLLER = HERE / 'stop_and_preserve_current_trainer_only_v2.py'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def definitions(path, names, **scope):
    tree = ast.parse(path.read_text())
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
            selected.append(node)
    actual = {n.name for n in selected if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
    actual |= {t.id for n in selected if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    assert actual == set(names), (path, actual, names)
    namespace = dict(require=require, json=json, os=os, Path=Path, re=re, **scope)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return types.SimpleNamespace(**namespace)


def controller():
    return definitions(CONTROLLER, {'HandoffError', 'ObservationPending', 'require', 'Handoff'})


def committed(alive=False):
    owner = dict(pid=3615927, starttime_ticks=78856521, unit='CPU-fixture-original.service')
    objects = {'prepared': dict(original_main='base'), 'base': dict(owner=owner)}
    linux = types.SimpleNamespace(checked=lambda key: json.dumps(objects[key]),
        process_start=lambda pid: owner['starttime_ticks'] if alive else None,
        show=lambda unit: dict(MainPID='0', ActiveState='inactive'), live_owner=lambda owner: None)
    module = definitions(POSTSTOP, {'recover_committed'}, load_linux=lambda job: linux)
    state = dict(original_owner=owner, case='scorecarry-CPUfixture', original_stop_sent=True,
                 dashboard_accept_held=False, poststop={})
    job = dict(prepared='prepared', case=state['case'])
    return module, job, state, linux


class Backend:
    """Explicit fake lifecycle, with actual committed-recovery function."""
    def __init__(self, verification_fails=False):
        self.stages = []; self.calls = []; self.fleet_frozen = False
        self.verification_fails = verification_fails; self.outcome = None
        self.original_stops = self.starts = 0
    def before_stage(self, stage): self.stages.append(stage)
    def after_stage(self, stage, value): pass
    def bind_observation_pending(self, exception): pass
    def preflight(self): return {}
    def open_probe(self, context): return {}
    def pause(self, purpose, probe): return dict(purpose=purpose)
    def measured_progress(self, pause): return {}
    def hold_listener(self, context): return {}
    def freeze_fleet(self, context): self.fleet_frozen = True; return {}
    def seal_inputs(self, *args): return {}
    def marker(self, *args): return {}
    def finish_original_handlers(self, *args): return {}
    def cancel_pause(self, *args): return {}
    def drain_budget(self, *args): return dict(budget_exhausted=True)
    def close_probe(self, *args): return {}
    def no_producers(self, *args): return {}
    def seal_banks(self, *args):
        return dict(input_sources_sealed=True, all_handlers_finished=True, prefetch_paused=True,
                    budget_exhausted=True, bank_shutdown_intent_verified=True)
    def hold_dashboard_finish_cleanup(self, *args):
        return dict(HTTP_accept_held=True, cleanup_Timer_and_unknown_autothreads_absent=True,
                    no_API_after_hold=True)
    def stop_original(self, *args):
        self.original_stops += 1
        return dict(actual_exit=0, original_absent=True)
    def verify_stopped(self, *args):
        if self.verification_fails: raise RuntimeError('injected strict stopped verifier failure')
        return dict(actual_original_CPU_exit=0, strict_phase_verified=True,
                    newest_stopped_source=True, replay_bank_consistency_verified=True)
    def recover(self, owner, **kwargs):
        m, job, state, _ = committed()
        return m.recover_committed(job, state, observation_pending=False)
    def finish(self, outcome): self.outcome = outcome


class VirtualCgroupPath(type(Path())):
    """Temp files stand in for virtual cgroup controls; rmdir drops controls."""
    def rmdir(self):
        for p in self.iterdir():
            if p.is_file(): p.unlink()
        super().rmdir()


class Tests(unittest.TestCase):
    def test_actual_native_classifier_exact_five_and_bare_unknown_threads(self):
        m = definitions(LINUX, {'CURRENT_NONINPUT_NATIVE', 'possible_input_or_cleanup'})
        self.assertEqual(len(m.CURRENT_NONINPUT_NATIVE), 5)
        for tid, (birth, name) in m.CURRENT_NONINPUT_NATIVE.items():
            self.assertFalse(m.possible_input_or_cleanup(tid, birth, name))
            with self.assertRaises(RuntimeError): m.possible_input_or_cleanup(tid, birth + 1, name)
        for name in ('Thread-12345678', 'Thread-9 (handle', 'Thread-9 (proces', 'Thread-9', 'Timer-1', 'Timer'):
            self.assertTrue(m.possible_input_or_cleanup(9999999, 12, name), name)

    def test_actual_controller_order_one_stop_no_install_or_start(self):
        b = Backend(); h = controller().Handoff(b); result = h.run()
        self.assertEqual(result['status'], 'CURRENT_TRAINER_STOPPED_AND_FULL_STATE_HOT_REPLAY_PRESERVED')
        self.assertEqual(b.original_stops, 1); self.assertTrue(b.fleet_frozen)
        expected = ['first_supported_pause', 'all192_acknowledged_and_advanced8_measured_frames',
            'exact_accept_thread_held', 'original_emulator_fleet_frozen',
            'input_ownership_and_receive_queues_sealed', 'first_FIFO_marker_acknowledged',
            'original192_handlers_finished', 'first_pause_restored_with_no_input',
            'actual_original_budget_exhausted', 'final_supported_pause_prefetch_quiesced',
            'final_FIFO_marker_acknowledged', 'owned_probe_closed_and_handler_finished',
            'no_remaining_input_producers', 'real_bank_shutdown_intent_sealed',
            'dashboard_accept_held_and_cleanup_finished', 'original_main_graceful_stop',
            'newest_stopped_checkpoint_CPU_verified']
        self.assertEqual([s for s in b.stages if s in expected], expected)
        self.assertFalse(result['source_install_performed']); self.assertFalse(result['replacement_started'])
        with self.assertRaises(Exception): h.run()
        # Actual post-fence methods have no dashboard API invocation.
        tree = ast.parse(LINUX.read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LinuxBackend')
        for name in ('hold_dashboard_finish_cleanup', 'stop_original', 'release_dashboard_after_save_return'):
            method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                 and n.func.attr == 'api' for n in ast.walk(method)), name)

    def test_strict_verification_failure_keeps_fleet_held_and_never_starts(self):
        b = Backend(verification_fails=True); result = controller().Handoff(b).run()
        self.assertEqual(result['status'], 'ORIGINAL_HANDOFF_FAILURE_PRESERVED')
        self.assertEqual(result['failed_stage'], 'newest_stopped_checkpoint_CPU_verified')
        self.assertEqual(result['recovery']['status'], 'COMMITTED_FORWARD_RECOVERY_REQUIRED')
        self.assertTrue(b.fleet_frozen); self.assertEqual(b.original_stops, 1)
        self.assertFalse(result['recovery']['restart_retry']); self.assertFalse(result['recovery']['replay_cleared'])
        for name in ('install', 'start_once', 'verify_startup', 'startup_snapshot', 'verify_progress'):
            tree = ast.parse(POSTSTOP.read_text()); cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Poststop')
            fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertIsInstance(fn.body[0], ast.Raise)

    def test_actual_precommit_recovery_HTTP_before_game_control_fleet(self):
        events = []; objects = {'prepared': dict(original_main='base', original_fleet='fleet',
            original_listener='listener', original_dashboard_accept='dashboard'), 'base': dict(owner={}),
            'fleet': {}, 'listener': {}, 'dashboard': {}}
        raw = b'{"measurement":null}'
        linux = types.SimpleNamespace(checked=lambda key: raw if key == 'control' else json.dumps(objects[key]),
            full_pin=lambda path: dict(sha256='same'), live_owner=lambda owner: None,
            GAME=Path('/CPUfixture/Robotron'), OLD_SOCKET_SHA='same')
        state = dict(original_stop_sent=False)
        objects['state'] = state
        linux.full_pin = lambda path: 'state' if path == 'state-path' else dict(sha256='same')
        def action(name): return lambda *args: events.append(name) or dict(status=name)
        m = definitions(RECOVERY, {'recover'}, load=lambda *args: linux,
            hashlib=hashlib, validate_state=lambda *args: None,
            release_original_dashboard=action('HTTP'), release_original_listener=action('GAME'),
            restore_original_control=action('CONTROL'), thaw_original_fleet=action('FLEET'))
        result = m.recover(dict(backend_source={}, prepared='prepared', base_control_archive='control',
            base_control_sha256=hashlib.sha256(raw).hexdigest()), 'state-path', observation_pending=False)
        self.assertEqual(events, ['HTTP', 'GAME', 'CONTROL', 'FLEET'])
        self.assertEqual(result['status'], 'PRESTOP_ORIGINAL_RESOURCES_RESTORED')

    def test_actual_empty_domain_partial_hold_cleanup_and_nonempty_reject(self):
        m = definitions(RECOVERY, {'release_original_dashboard', 'release_original_listener'})
        # Bind only the Path collaborator to temp virtual-cgroup controls.
        for function in (m.release_original_dashboard, m.release_original_listener):
            function.__globals__['Path'] = VirtualCgroupPath
        linux = types.SimpleNamespace(live_owner=lambda owner: None)
        with tempfile.TemporaryDirectory(prefix='current227 empty hold CPU ') as td:
            for component, fn in (('dashboard', m.release_original_dashboard), ('listener', m.release_original_listener)):
                child = Path(td)/component; child.mkdir()
                for name, value in (('cgroup.type', 'domain'), ('cgroup.threads', ''), ('cgroup.events', 'populated 0\n')):
                    (child/name).write_text(value)
                state = dict(original_owner={}, dashboard_child=str(child), listener_child=str(child))
                result = fn(linux, state, {})
                self.assertIn('before_threaded_type', result['status']); self.assertFalse(child.exists())
                child.mkdir()
                for name, value in (('cgroup.type', 'domain'), ('cgroup.threads', '123\n'), ('cgroup.events', 'populated 1\n')):
                    (child/name).write_text(value)
                with self.assertRaises(RuntimeError): fn(linux, state, {})
                self.assertTrue(child.exists())

    def test_real_marker_function_releases_HTTP_only_not_persistence(self):
        released = []; objects = {'prepared': dict(original_dashboard_accept='dashboard'), 'dashboard': {}}
        linux = types.SimpleNamespace(checked=lambda key: json.dumps(objects[key]), live_owner=lambda owner: None)
        m = definitions(RECOVERY, {'release_HTTP_if_save_function_returned'},
            release_original_dashboard=lambda *args: released.append('HTTP') or dict(status='released'))
        with tempfile.TemporaryDirectory(prefix='current227 save return CPU ') as td:
            path = Path(td)/'console'; path.write_bytes(b'prior buffered output\n'); s = path.stat()
            owner = dict(pid=3615927, starttime_ticks=78856521)
            state = dict(original_owner=owner, original_stop_sent=True, original_stop_stdout_binding=dict(
                owner=owner, path=str(path), device=s.st_dev, inode=s.st_ino, uid=s.st_uid, nlink=s.st_nlink, offset=s.st_size))
            job = dict(prepared='prepared')
            self.assertIsNone(m.release_HTTP_if_save_function_returned(job,state,linux)); self.assertEqual(released,[])
            with path.open('ab') as f: f.write(b'Final model & settings saved\n')
            result = m.release_HTTP_if_save_function_returned(job,state,linux)
            self.assertEqual(released,['HTTP']); self.assertTrue(result['save_function_returned_signal_only'])
            self.assertTrue(result['persistence_success_not_inferred'])
            # Actual final-save validator rejects this return marker alone.
            validator = definitions(POSTSTOP, {'final_save_console'})
            with self.assertRaises(RuntimeError): validator.final_save_console(b'Final model & settings saved\n')

    def test_committed_HTTP_observer_rechecks_original_birth_after_marker(self):
        for retires_at_marker in (False, True):
            m, job, state, linux = committed(alive=True)
            state['dashboard_accept_held'] = True; job['recovery_source'] = {}
            present = [True]; releases = []
            linux.process_start = lambda pid: state['original_owner']['starttime_ticks'] if present[0] else None
            def release(*args):
                releases.append('HTTP-only')
                if retires_at_marker: present[0] = False
                return dict(save_function_returned_signal_only=True, persistence_success_not_inferred=True)
            linux.module = lambda *args: types.SimpleNamespace(release_HTTP_if_save_function_returned=release)
            m.recover_committed.__globals__['time'] = types.SimpleNamespace(monotonic=lambda: 0,
                sleep=lambda _: self.fail('Return marker should end this deterministic observer'))
            result = m.recover_committed(job,state,observation_pending=True)
            self.assertEqual(releases,['HTTP-only'])
            self.assertEqual(result['original_handle_preserved'],not retires_at_marker)
            self.assertEqual(result['status'],'COMMITTED_FORWARD_RECOVERY_REQUIRED' if retires_at_marker
                             else 'SAME_ORIGINAL_HANDLE_OBSERVATION_PENDING')
            self.assertFalse(result['restart_retry']); self.assertFalse(result['replay_cleared'])


if __name__ == '__main__': unittest.main()
