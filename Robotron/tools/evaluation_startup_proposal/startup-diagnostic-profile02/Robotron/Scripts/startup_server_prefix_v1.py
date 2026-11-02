"""Bounded private diagnostic only; never admit games or modify policy/actions."""
from contextlib import contextmanager
import json
import re
import struct
import threading

SCHEMA = 'robotron-server-startup-prefix-v1'
LUA_SCHEMA = 'robotron-lua-startup-prefix-v1'
HEADER = struct.Struct('>HddBIBBBIBBB')
_active = None
_capture_lock = threading.RLock()


def require(value, message):
    if not value:
        raise ValueError(message)


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, 'Invalid diagnostic integer')
    return value


def configuration(sessions, limit):
    require(isinstance(sessions, dict) and 1 <= len(sessions) <= 32, 'Explicit slot/session map required')
    integer(limit, 16, 16384)
    for slot, session in sessions.items():
        integer(slot, 0, 8191)
        require(isinstance(session, str) and re.fullmatch('[0-9a-f]{32}', session), 'Invalid session identity')
    return dict(sessions)


def wire_fields(payload):
    require(type(payload) is bytes and HEADER.size <= len(payload) <= 2 * 1024 * 1024,
            'Invalid bounded wire payload')
    n, subj, obj, done, score, alive, save, start, replay, reserves, wave, lives = HEADER.unpack_from(payload)
    require(n == 11128 and len(payload) >= HEADER.size + n * 4 + 4, 'Wrong fixed v2 wire shape')
    preview_offset = HEADER.size + n * 4
    preview_len = struct.unpack_from('>I', payload, preview_offset)[0]
    require(preview_len == 0 and len(payload) == preview_offset + 4, 'Private diagnostic requires no preview')
    require(done in (0, 1) and alive in (0, 1) and start in (0, 1), 'Invalid wire flags')
    return dict(payload_bytes=len(payload), wire_n=n, wire_done=done, wire_score=score,
                wire_alive=alive, wire_start=start, wire_reserves=reserves, wire_wave=wave, wire_lives=lives)


class Recorder:
    def __init__(self, sessions, write, *, limit=4096):
        self.sessions = configuration(sessions, limit)
        require(callable(write), 'Explicit bounded diagnostic writer required')
        self.write, self.limit = write, limit
        self.lock = threading.RLock()
        self.clients = {}
        self.epochs = {slot: 0 for slot in sessions}
        self.counts = {slot: 0 for slot in sessions}
        self.events = self.rows = self.faults = 0
        self.closed = self.failed = False
        self.max_events = len(sessions) * (limit + 16) + 4
        self._emit(dict(kind='header', limit=limit,
                        sessions={str(k): v for k, v in sorted(sessions.items())}))

    def _emit(self, row):
        if self.closed:
            return False
        if self.events >= self.max_events:
            self.closed = self.failed = True
            self.faults += 1
            return False
        try:
            line = json.dumps(dict(schema=SCHEMA, **row), separators=(',', ':'), allow_nan=False) + '\n'
            require(len(line.encode()) <= 2048, 'Diagnostic event exceeds fixed bound')
            require(self.write(line) is True, 'Diagnostic writer failed')
        except Exception:
            self.closed = self.failed = True
            self.faults += 1
            return False
        self.events += 1
        return True

    def _fault(self, reason):
        self.faults += 1
        self._emit(dict(kind='fault', reason=reason))

    def notify(self, method, *args):
        with self.lock:
            if self.closed:
                return
            try:
                getattr(self, '_' + method)(*args)
            except Exception:
                self._fault('observer_error')

    def _connect(self, cid, slot):
        integer(cid, 0, 2**63 - 1)
        require(slot in self.sessions and type(slot) is int, 'Undeclared slot')
        require(cid not in self.clients and len(self.clients) < len(self.sessions), 'Client capacity exceeded')
        require(not any(c['slot'] == slot for c in self.clients.values()), 'Concurrent duplicate slot')
        self.epochs[slot] += 1
        self.clients[cid] = dict(slot=slot, epoch=self.epochs[slot], exchange=0,
                                 accepted=0, pending=None, done=self.counts[slot] >= self.limit)
        self._emit(dict(kind='connection', slot=slot, session=self.sessions[slot],
                        cid=cid, epoch=self.epochs[slot]))

    def _client(self, cid):
        integer(cid, 0, 2**63 - 1)
        require(cid in self.clients, 'No declared connection')
        return self.clients[cid]

    def _received(self, cid, payload):
        c = self._client(cid)
        if c['done']:
            return
        require(c['pending'] is None, 'Prior received frame has no send outcome')
        c['exchange'] += 1
        c['pending'] = dict(kind='frame', slot=c['slot'], session=self.sessions[c['slot']],
            cid=cid, epoch=c['epoch'], exchange=c['exchange'], accepted=False,
            accepted_ordinal=0, action_observed=False, **wire_fields(payload))

    def _accepted(self, cid, accepted_ordinal):
        c = self._client(cid)
        if c['done']:
            return
        integer(accepted_ordinal, 1, 2**63 - 1)
        require(c['pending'] is not None and not c['pending']['accepted']
                and accepted_ordinal == c['accepted'] + 1, 'Accepted ordinal differs')
        c['accepted'] = accepted_ordinal
        c['pending'].update(accepted=True, accepted_ordinal=accepted_ordinal)

    def _action(self, cid, payload):
        c = self._client(cid)
        if c['done']:
            return
        require(c['pending'] is not None and not c['pending']['action_observed'], 'Unmatched action')
        require(type(payload) is bytes and len(payload) in (3, 5, 6), 'Unexpected action bytes')
        c['pending'].update(action_observed=True, action_hex=payload.hex())

    def _sent(self, cid, success):
        c = self._client(cid)
        if c['done']:
            return
        require(type(success) is bool and c['pending'] is not None
                and c['pending']['action_observed'], 'No matched action send')
        row, c['pending'] = c['pending'], None
        row['send_ok'] = success
        if not success:
            self.faults += 1
        if self._emit(row):
            self.counts[c['slot']] += 1
            self.rows += 1
        c['done'] = self.counts[c['slot']] >= self.limit
        if all(n >= self.limit for n in self.counts.values()):
            self.close('capacity')

    def _disconnect(self, cid):
        c = self.clients.pop(cid, None)
        if c is None:
            return
        if c['pending'] is not None:
            self._fault('pending_frame_on_disconnect')
        self._emit(dict(kind='disconnect', slot=c['slot'], session=self.sessions[c['slot']],
                        cid=cid, epoch=c['epoch'], pending_frame=c['pending'] is not None))

    def close(self, reason='context_exit'):
        with self.lock:
            if self.closed:
                return
            require(reason in ('capacity', 'context_exit'), 'Invalid diagnostic close')
            pending = sum(c['pending'] is not None for c in self.clients.values())
            self.faults += pending
            self._emit(dict(kind='footer', rows=self.rows, faults=self.faults,
                counts={str(k): v for k, v in sorted(self.counts.items())}, pending_frames=pending,
                reason=reason, captured_prefix_only=True))
            self.closed = True


def private_server(server):
    return (getattr(server, 'replay_enabled', None) is False
            and getattr(server, 'async_buffer', object()) is None
            and getattr(getattr(server, 'agent', None), 'training_enabled', None) is False)


@contextmanager
def capture(recorder, server):
    global _active
    require(isinstance(recorder, Recorder) and not recorder.closed, 'Fresh recorder required')
    require(private_server(server), 'Only a private inference-only server can be captured')
    with _capture_lock:
        require(_active is None, 'One diagnostic capture at a time')
        _active = server, recorder
    try:
        yield recorder
    finally:
        with _capture_lock:
            require(_active is not None and _active[0] is server and _active[1] is recorder,
                    'Capture owner changed')
            _active = None
        recorder.close()


def notify(server, method, *args):
    with _capture_lock:
        active = _active
    if active is None or active[0] is not server:
        return
    recorder = active[1]
    try:
        if not private_server(server):
            recorder.notify('configuration_changed')
            return
        recorder.notify(method, *args)
    except Exception:
        # A diagnostic fault must not change the original socket action/outcome.
        try:
            with recorder.lock:
                recorder._fault('notification_error')
        except Exception:
            recorder.closed = recorder.failed = True


def send(server, sock, cid, payload):
    notify(server, 'action', cid, payload)
    try:
        result = sock.sendall(payload)
    except BaseException:
        notify(server, 'sent', cid, False)
        raise
    notify(server, 'sent', cid, True)
    return result


def decode_lines(raw, maximum_events):
    require(type(raw) is bytes and raw and raw.endswith(b'\n')
            and len(raw) <= maximum_events * 2048, 'Incomplete or oversized diagnostic prefix')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate diagnostic JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('Nonfinite diagnostic JSON: ' + value)
    lines = raw.splitlines()
    require(len(lines) <= maximum_events and all(len(x) + 1 <= 2048 for x in lines), 'Event bound exceeded')
    rows = [json.loads(x, object_pairs_hook=unique, parse_constant=nonfinite) for x in lines]
    require(all(isinstance(x, dict) for x in rows), 'Diagnostic row is not an object')
    return rows


def reconcile(lua_prefixes, server_prefix, sessions, *, limit=4096):
    """Strict observational join. A match is never proof of a known game start."""
    sessions = configuration(sessions, limit)
    require(isinstance(lua_prefixes, dict) and set(lua_prefixes) == set(sessions), 'Declared Lua slots differ')
    server = decode_lines(server_prefix, len(sessions) * (limit + 16) + 4)
    require(all(x.get('schema') == SCHEMA for x in server), 'Server schema differs')
    require(server[0].get('kind') == 'header' and server[-1].get('kind') == 'footer', 'Server closure missing')
    require(type(server[0].get('limit')) is int and server[0]['limit'] == limit
            and server[0].get('sessions') == {str(k): v for k, v in sessions.items()}, 'Server declaration differs')
    footer = server[-1]
    require(type(footer.get('faults')) is int and footer['faults'] == 0
            and type(footer.get('pending_frames')) is int and footer['pending_frames'] == 0
            and footer.get('captured_prefix_only') is True, 'Server capture has faults or pending work')
    allowed = {'header', 'connection', 'frame', 'disconnect', 'footer'}
    require(all(x.get('kind') in allowed for x in server)
            and sum(x['kind'] == 'header' for x in server) == 1
            and sum(x['kind'] == 'footer' for x in server) == 1, 'Unexpected server records')
    wire_keys = ('payload_bytes','wire_n','wire_done','wire_score','wire_alive','wire_start',
                 'wire_reserves','wire_wave','wire_lives')
    matched = accepted = 0
    counts = {}
    for slot, session in sorted(sessions.items()):
        relevant = [x for x in server[1:-1] if x.get('slot') == slot]
        require(all(type(x.get('slot')) is int and x.get('session') == session
                    and type(x.get('epoch')) is int and x['epoch'] == 1 for x in relevant),
                'Server session/epoch differs')
        connections = [x for x in relevant if x['kind'] == 'connection']
        require(len(connections) == 1 and relevant[0] == connections[0], 'Reconnect or missing connection')
        cid = connections[0].get('cid')
        require(type(cid) is int and all(type(x.get('cid')) is int and x['cid'] == cid for x in relevant),
                'Server connection ID differs')
        frames = [x for x in relevant if x['kind'] == 'frame']
        disconnects = [x for x in relevant if x['kind'] == 'disconnect']
        require(len(disconnects) <= 1 and (not disconnects or (relevant[-1] == disconnects[0]
                and disconnects[0].get('pending_frame') is False)), 'Invalid disconnect ordering')
        lua = decode_lines(lua_prefixes[slot], limit + 32)
        require(all(x.get('schema') == LUA_SCHEMA and type(x.get('slot')) is int and x.get('slot') == slot
                    and x.get('session') == session for x in lua), 'Lua schema/slot/session differs')
        require(lua[0].get('kind') == 'header' and lua[-1].get('kind') == 'footer'
                and type(lua[0].get('limit')) is int and lua[0]['limit'] == limit, 'Lua closure/declaration differs')
        require(type(lua[-1].get('faults')) is int and lua[-1]['faults'] == 0
                and lua[-1].get('pending_frame') is False
                and lua[-1].get('captured_prefix_only') is True, 'Lua capture has faults or pending work')
        require([x['kind'] for x in lua].count('connection') == 1
                and lua[1].get('kind') == 'connection' and type(lua[1].get('epoch')) is int
                and lua[1]['epoch'] == 1,
                'Lua reconnect or missing initial connection')
        require(all(x.get('kind') == 'frame' for x in lua[2:-1]), 'Unexpected Lua event')
        actual = lua[2:-1]
        require(0 < len(actual) == len(frames) <= limit
                and type(lua[-1].get('rows')) is int and lua[-1]['rows'] == len(actual)
                and type(lua[-1].get('attempts')) is int and lua[-1]['attempts'] == len(actual),
                'Prefix coverage differs')
        ordinal = 0
        for exchange, (left, right) in enumerate(zip(actual, frames), 1):
            require(type(left.get('frame')) is int and left['frame'] == exchange - 1
                    and type(left.get('epoch')) is int and left['epoch'] == right.get('epoch') == 1
                    and type(left.get('exchange')) is type(right.get('exchange')) is int
                    and left['exchange'] == right['exchange'] == exchange, 'Frame/exchange order differs')
            require(all(type(left.get(k)) is type(right.get(k)) is int and left[k] == right[k] for k in wire_keys),
                    'Original Lua/server wire fields differ')
            require(left['wire_n'] == 11128 and left['payload_bytes'] == HEADER.size + 11128*4 + 4,
                    'Matched wire shape differs')
            for key in ('wire_done','wire_alive','wire_start'):
                integer(left[key],0,1)
            for key in ('wire_reserves','wire_wave','wire_lives'):
                integer(left[key],0,255)
            integer(left['wire_score'],0,2**32-1)
            require(left.get('wire_observed') is True and left.get('response_observed') is True
                    and left.get('socket_ok') is True and left.get('apply_ok') is True
                    and right.get('action_observed') is True and right.get('send_ok') is True,
                    'Incomplete receive/action/input result')
            action = right.get('action_hex')
            require(isinstance(action, str) and re.fullmatch('(?:[0-9a-f]{2}){3,6}', action)
                    and len(action) in (6,10,12) and action == left.get('response_hex'), 'Action bytes differ')
            move, fire = struct.unpack('bb', bytes.fromhex(action)[:2])
            require(type(left.get('move')) is type(left.get('fire')) is int
                    and left['move'] == move and left['fire'] == fire
                    and type(left.get('start_input')) is int and left['start_input'] == left['wire_start']
                    and type(left.get('coin_input')) is int and left['coin_input'] in (0,1), 'Applied inputs differ')
            status = integer(left.get('raw_status'), 0, 255)
            require(left['wire_alive'] == int((status & 1) == 0), 'Raw STATUS/wire alive differs')
            require(integer(left.get('raw_reserves'),0,255) == left['wire_reserves']
                    and integer(left.get('raw_wave'),0,255) == left['wire_wave'], 'Raw ROM/wire counters differ')
            require(isinstance(left.get('raw_score_hex'),str)
                    and re.fullmatch('[0-9a-f]{8}',left['raw_score_hex']), 'Raw BCD bytes missing')
            require(type(right.get('accepted')) is bool and type(right.get('accepted_ordinal')) is int,
                    'Accepted stamp is malformed')
            if right['accepted']:
                ordinal += 1
                require(right['accepted_ordinal'] == ordinal, 'Accepted ordinal skipped or duplicated')
            else:
                require(right['accepted_ordinal'] == 0, 'Rejected frame borrowed accepted ordinal')
                require(move == fire == -1 and bytes.fromhex(action)[2] & 0x0f == 0,
                        'Rejected frame lacks neutral action')
        matched += len(actual)
        accepted += ordinal
        counts[str(slot)] = len(actual)
    require(all(x.get('slot') in sessions for x in server[1:-1]), 'Undeclared server slot')
    require(type(footer.get('rows')) is int and footer['rows'] == matched
            and footer.get('counts') == counts and all(type(v) is int for v in footer['counts'].values()),
            'Server footer coverage differs')
    return dict(status='MATCHED_DIAGNOSTIC_PREFIX_ONLY',matched_frames=matched,
        accepted_frames=accepted,rejected_frames=matched-accepted,actor_slots=len(sessions),
        raw_ROM_start_acceptance_proven=False,start_eligibility_changed=False,
        protocol_selected=False,quality_qualified=False,learning_speed_gain_verified=False)
