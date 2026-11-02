"""Experimental one-use host clock bracket; never certifies or admits a game.

The future private adapter must send a nonce bound to its actual response, then
join a post-ROM-acceptance snapshot on the same connection. This component only
establishes the host-time interval. It does not supply ROM, policy-load, local
input-application, first-play, or journal-handoff evidence.
"""
import json
import re
import secrets
import time
from types import MappingProxyType


class Rejected(ValueError):
    pass


def _integer(value, name, minimum=0):
    if type(value) is not int or not minimum <= value <= (1 << 64) - 1:
        raise Rejected("invalid " + name)
    return value


def _hex(value, width, name):
    if type(value) is not str or re.fullmatch("[0-9a-f]{%d}" % width, value) is None:
        raise Rejected("invalid " + name)
    return value


def decode(raw):
    if type(raw) is not bytes or not raw.endswith(b"\n") or len(raw) > 4096:
        raise Rejected("incomplete or oversized acknowledgement")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Rejected("duplicate acknowledgement key")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda value: (_ for _ in ()).throw(Rejected("nonfinite value")))
    except (ValueError, UnicodeError) as error:
        raise Rejected("malformed acknowledgement") from error
    if type(value) is not dict:
        raise Rejected("acknowledgement must be an object")
    return value


class ResponseClock:
    """One original response attempt on one bound connection; errors are final.

    Callbacks execute synchronously. They must use the actual selected transport;
    injection exists for the isolated diagnostic adapter and clock-boundary guard.
    No caller-supplied timestamp is accepted as an interval endpoint.
    """

    def __init__(self, *, session, connection, slot, epoch, exchange, frame,
                 checkpoint_sha256, generation, admission_open_ns,
                 admission_close_ns, clock=time.monotonic_ns):
        self.binding = MappingProxyType(dict(session=_hex(session, 32, "session"),
                            connection=_hex(connection, 32, "connection"),
                            slot=_integer(slot, "slot"), epoch=_integer(epoch, "epoch"),
                            exchange=_integer(exchange, "exchange", 1),
                            frame=_integer(frame, "frame"),
                            checkpoint_sha256=_hex(checkpoint_sha256, 64, "checkpoint"),
                            generation=_integer(generation, "generation", 1)))
        if not 4096 <= self.binding["slot"] < 4128:
            raise Rejected("private slot outside precommitted32")
        self.open = _integer(admission_open_ns, "admission open")
        self.close = _integer(admission_close_ns, "admission close", self.open + 1)
        self.clock = clock
        self.state = "new"
        self.failure = None
        self.events = []
        self.nonce = None

    def _reject(self, reason):
        self.state, self.failure = "rejected", reason
        raise Rejected(reason)

    def send_response(self, send):
        if self.state != "new":
            self._reject("response already attempted; no retry")
        self.state = "sending"
        self.nonce = secrets.token_hex(32)
        token = dict(schema="robotron-startup-clock-token-v1", nonce=self.nonce, **self.binding)
        raw = (json.dumps(token, sort_keys=True, separators=(",", ":")) + "\n").encode()
        try:
            self.lower = _integer(self.clock(), "host clock")
        except Exception:
            self.state, self.failure = "rejected", "invalid host clock before send"
            raise
        if not self.open <= self.lower < self.close:
            self._reject("response outside fixed admission")
        self.events.append(dict(kind="before_response_send", host_ns=self.lower))
        try:
            result = send(raw)
            # socket.sendall returns None. Partial-count APIs are not accepted.
            if result is not None:
                self._reject("sendall completion required")
            completed = _integer(self.clock(), "host clock")
            if completed < self.lower:
                self._reject("host clock went backwards")
        except Exception as error:
            self.state, self.failure = "rejected", "response send failed: " + type(error).__name__
            raise
        self.events.append(dict(kind="response_send_complete", host_ns=completed))
        self.state = "awaiting_snapshot"
        return token

    def receive_snapshot(self, receive, *, connection):
        if self.state != "awaiting_snapshot":
            self._reject("snapshot without one successful unconsumed response")
        if connection != self.binding["connection"]:
            self._reject("connection changed")
        self.state = "receiving_snapshot"
        try:
            raw = receive()
            upper = _integer(self.clock(), "host clock")
            ack = decode(raw)
            expected = dict(schema="robotron-startup-clock-ack-v1", nonce=self.nonce, **self.binding)
            if set(ack) != set(expected) | {"snapshot_frame", "socket_ok", "apply_ok", "debug_bypass", "held_start_before_response"}:
                self._reject("snapshot fields differ")
            if any(type(ack[k]) is not type(v) or ack[k] != v for k, v in expected.items()):
                self._reject("snapshot binding or nonce differs")
            if _integer(ack["snapshot_frame"], "snapshot frame") <= self.binding["frame"]:
                self._reject("snapshot does not follow response frame")
            flags = dict(socket_ok=True, apply_ok=True, debug_bypass=False, held_start_before_response=False)
            if any(type(ack[k]) is not bool or ack[k] is not v for k, v in flags.items()):
                self._reject("failed, bypassed or already-held local input")
            if not self.open <= self.lower <= self.events[-1]["host_ns"] <= upper < self.close:
                self._reject("whole acceptance bracket outside fixed admission")
        except Exception as error:
            self.state, self.failure = "rejected", "snapshot rejected: " + type(error).__name__
            raise
        self.events.append(dict(kind="after_snapshot_receive", host_ns=upper))
        self.state = "observed_uncertified"
        return dict(status="HOST_CLOCK_BRACKET_ONLY_UNCERTIFIED", binding=dict(self.binding),
                    nonce=self.nonce, lower_ns=self.lower, upper_ns=upper,
                    snapshot_frame=ack["snapshot_frame"], events=list(self.events),
                    game_start_certified=False, journal_eligibility_changed=False,
                    transport_identity_authenticated_by_this_component=False)
