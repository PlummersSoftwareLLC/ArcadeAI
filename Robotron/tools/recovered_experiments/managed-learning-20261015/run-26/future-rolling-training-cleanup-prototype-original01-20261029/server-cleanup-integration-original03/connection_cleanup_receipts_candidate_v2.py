"""Inert prospective server-local cleanup receipts, not a refill authority.

This revision is staged with a prospective server/HTTP getter, never installed.
Server connection identity is not an actor PID proof. A supervisor must separately
join its original Popen birth, socket observation, durable game and actual reap.
"""
import copy
import hashlib
import json
from pathlib import Path
import secrets
import threading
import time


class ConnectionCleanupReceipts:
    def __init__(self, server_stamp, replay_health, *, maximum_records=4096):
        if (type(server_stamp) is not dict or set(server_stamp) != {'pid', 'birth', 'source_sha256'}
                or any(type(server_stamp[k]) is not int or server_stamp[k] <= 0 for k in ('pid', 'birth'))
                or type(server_stamp['source_sha256']) is not str
                or len(server_stamp['source_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in server_stamp['source_sha256'])
                or not callable(replay_health)
                or type(maximum_records) is not int or not 1 <= maximum_records <= 4096):
            raise ValueError('Exact bounded server-local cleanup contract required')
        self.stamp = copy.deepcopy(server_stamp)
        self.incarnation = secrets.token_hex(16)
        self.replay_health = replay_health
        self.maximum_records = maximum_records
        self.lock = threading.Lock()
        self.records = {}
        self.sequence = 0

    def begin(self, cid, slot, eval_only, connection_ns, handler, *, endpoints):
        if (type(cid) is not int or cid < 0 or type(slot) is not int or not 0 <= slot < 192
                or type(eval_only) is not bool or type(connection_ns) is not int or connection_ns <= 0
                or not isinstance(handler, threading.Thread)
                or handler is not threading.current_thread() or not handler.is_alive()):
            raise ValueError('Exact original handler/slot/role incarnation required')
        if (type(endpoints) is not dict or set(endpoints) != {'server', 'peer'}
                or any(type(endpoints[k]) is not list or len(endpoints[k]) != 2
                       or type(endpoints[k][0]) is not str or not 1 <= len(endpoints[k][0]) <= 45
                       or type(endpoints[k][1]) is not int or not 1 <= endpoints[k][1] <= 65535
                       for k in endpoints)):
            raise ValueError('Actual socket endpoint pair required')
        with self.lock:
            if len(self.records) >= self.maximum_records:
                raise RuntimeError('Cleanup receipt capacity exhausted; no receipt was overwritten')
            self.sequence += 1
            token = f"{self.stamp['pid']}:{self.stamp['birth']}:{self.incarnation}:{self.sequence}"
            self.records[token] = dict(cid=cid, slot=slot, eval_only=eval_only,
                connection_ns=connection_ns, endpoints=copy.deepcopy(endpoints), handler=handler, timer=None,
                timer_done=None, reset_ack=None, journal_ok=False, terminal=None,
                terminal_sha=None, error=None, recorded=False, began_ns=time.monotonic_ns())
            return token

    def finish(self, token, *, journal_ok, reset_ack, timer, timer_done,
               terminal_receipt, error=None):
        if type(journal_ok) is not bool or (error is not None and type(error) is not str):
            raise ValueError('Explicit cleanup outcome required')
        if (not isinstance(timer, threading.Timer) or timer.ident is None
                or not isinstance(timer_done, threading.Event)
                or (reset_ack is not None and not isinstance(reset_ack, threading.Event))):
            raise ValueError('Actual started owned timer and acknowledgment events required')
        terminal = None
        if terminal_receipt is not None:
            # Canonical bytes are the existing GameJournal JSON-line form.
            encoded = json.dumps(terminal_receipt, allow_nan=False, separators=(',', ':')).encode()
            if len(encoded) > 65536:
                raise ValueError('Terminal cleanup evidence exceeds its 64 KiB storage bound')
            terminal = json.loads(encoded)
        with self.lock:
            record = self.records[token]
            if record['handler'] is not threading.current_thread() or record['recorded']:
                raise ValueError('Another handler or duplicate cleanup publication')
            if terminal is not None and (type(terminal) is not dict
                    or terminal.get('client_id') != record['cid']
                    or type(terminal.get('client_id')) is not int
                    or terminal.get('client_slot') != record['slot']
                    or type(terminal.get('client_slot')) is not int
                    or terminal.get('eval_only') is not record['eval_only']
                    or any(terminal.get(k) is not True for k in ('complete', 'eligible', 'known_start'))
                    or terminal.get('boundary_reason') not in ('score_reset', 'zero_score_restart')
                    or type(terminal.get('journal_game_id')) is not str or not terminal['journal_game_id']
                    or type(terminal.get('score')) is not int or terminal['score'] < 0):
                raise ValueError('Exact durable natural-game identity required; disconnect is not completion')
            terminal_sha = None if terminal is None else hashlib.sha256(
                (json.dumps(terminal, allow_nan=False, separators=(',', ':')) + '\n').encode()).hexdigest()
            record.update(journal_ok=journal_ok, reset_ack=reset_ack, timer=timer,
                timer_done=timer_done, terminal=terminal, terminal_sha=terminal_sha,
                error=error, recorded=True, recorded_ns=time.monotonic_ns())

    def snapshot(self, token):
        # This method only reads already retained objects. It never joins,
        # signals, polls procfs, advances a clock, or executes replay work.
        with self.lock:
            r = self.records[token]
            handler_dead = not r['handler'].is_alive()
            timer_dead = r['timer'] is not None and not r['timer'].is_alive()
            timer_ok = r['timer_done'] is not None and r['timer_done'].is_set()
            ack = r['reset_ack'] is not None and r['reset_ack'].is_set()
            try:
                health = self.replay_health()
                healthy = (type(health) is dict and set(health) == {'admission_open', 'consumer_error'}
                           and type(health['admission_open']) is bool and health['consumer_error'] is None)
                admission_open = healthy and health['admission_open']
            except Exception:
                healthy = admission_open = False
            ready = bool(r['recorded'] and r['journal_ok'] and r['error'] is None
                         and ack and handler_dead and timer_dead and timer_ok and healthy)
            return dict(schema='robotron-prospective-connection-cleanup-receipt-v2',
                token=token, server_stamp=copy.deepcopy(self.stamp), client_id=r['cid'],
                server_cleanup_incarnation=self.incarnation,
                client_slot=r['slot'], eval_only=r['eval_only'], connection_ns=r['connection_ns'],
                socket_endpoints=copy.deepcopy(r['endpoints']),
                handler_native_id=r['handler'].native_id, original_handler_stopped=handler_dead,
                original_owned_timer_stopped=timer_dead, owned_timer_callback_succeeded=timer_ok,
                journal_disconnect_succeeded=r['journal_ok'], FIFO_reset_executed=ack,
                replay_consumer_healthy=healthy, replay_admission_open=admission_open,
                cleanup_error=r['error'], ready_for_external_join=ready,
                terminal_receipt=copy.deepcopy(r['terminal']), terminal_line_sha256=r['terminal_sha'],
                training_refill_candidate=bool(ready and admission_open and not r['eval_only']
                                               and r['terminal'] is not None),
                owned_actor_PID_birth_exit_reap_proved=False,
                supervisor_join_and_generation_admission_still_required=True,
                runtime_integration_qualified=False, safe_refill_qualified=False)

    def lookup_terminal(self, journal_game_id, cid, slot):
        if (type(journal_game_id) is not str or not journal_game_id
                or type(cid) is not int or type(slot) is not int):
            raise ValueError('Exact journal/connection/slot lookup required')
        with self.lock:
            found = [token for token, row in self.records.items()
                     if row['terminal'] is not None
                     and row['terminal']['journal_game_id'] == journal_game_id
                     and row['cid'] == cid and row['slot'] == slot]
        if len(found) != 1:
            raise ValueError('No unique original terminal cleanup receipt')
        return self.snapshot(found[0])

    def lookup_active(self, cid, slot):
        if type(cid) is not int or type(slot) is not int:
            raise ValueError('Exact active connection lookup required')
        with self.lock:
            found = [token for token, row in self.records.items()
                     if row['cid'] == cid and row['slot'] == slot
                     and not row['recorded'] and row['handler'].is_alive()]
        if len(found) != 1:
            raise ValueError('No unique active connection incarnation')
        return self.snapshot(found[0])


def current_server_stamp(source_path):
    """Read the actual current process birth and its installed source bytes once."""
    path = Path(source_path)
    stable = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns,
                        s.st_ctime_ns, s.st_mode, s.st_uid, s.st_nlink)
    before = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if stable(before) != stable(path.stat()):
        raise RuntimeError('Installed server source changed during incarnation binding')
    process = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    return dict(pid=int(Path('/proc/self').resolve().name), birth=int(process[19]),
                source_sha256=digest)
