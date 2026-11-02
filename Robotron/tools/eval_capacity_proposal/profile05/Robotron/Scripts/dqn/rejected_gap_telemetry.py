"""UNSELECTED bounded observation only; never changes a socket/replay decision.

No file, socket, model, replay-array or device I/O. Each event uses one short
diagnostic lock. The first 32 closure witnesses are retained, never sampled by
policy RNG or overwritten. Physical insertion/training and Lua application are
outside this observer's claims. Root must test and select it after the freeze.
"""
from copy import deepcopy
import os
import threading
import time


SCHEMA = "robotron-rejected-gap-observation-v1"
MAX_CLIENTS = 256
MAX_WITNESSES = 32
MAX_COUNT = (1 << 63) - 1
REASONS = ("parse_none", "crash_jump", "crash_drop")
COUNTERS = (
    "connections", "tracking_overflow", "payloads_complete", "param_mismatch",
    "short_payload", "receive_header_idle", "receive_header_eof", "receive_invalid_length",
    "receive_broken_payload", "parse_none", "crash_jump", "crash_drop", "accepted_frames",
    "neutral_write_ok", "neutral_write_failed", "gaps_opened", "accepted_closures",
    "disconnect_closures", "same_classifier_game", "new_game_classified",
    "measurement_boundary", "previous_step_entered", "nstep_add_called",
    "one_step_called", "matured_total", "group_flush_before_input",
    "matured_including_current_input", "enqueue_calls", "enqueue_returns",
    "including_current_input_enqueue_calls", "witness_overflow",
)


def _actor(value):
    return value if value in ("dqn", "epsilon", "expert", "eval", "measurement", "none") else "other"


def _group(value):
    # Exact held NStepReplayBuffer._actor_group semantics: every nonexpert is learner.
    return "expert" if value == "expert" else "learner"


def _state(cs):
    """Only primitive metadata; never retain/copy a state, reward array or client dict."""
    cs = cs or {}
    action = cs.get("last_action")
    if action is not None:
        action = [int(action[0]), int(action[1])]
    nstep = cs.get("nstep")
    pending = getattr(nstep, "_deque", ())
    return dict(game_uid=int(cs.get("game_uid") or 0), slot=int(cs.get("client_slot", -1)),
        accepted_frames=int(cs.get("frames", 0)), last_state_present=cs.get("last_state") is not None,
        last_action=action, previous_source=_actor(cs.get("prev_action_source")),
        history_length=len(cs.get("frame_history", ())), nstep_pending=len(pending),
        measurement_generation=int(cs.get("measurement_generation", 0)),
        measurement_active=bool(cs.get("measurement_active", False)),
        was_done=bool(cs.get("was_done", False)), player_alive=bool(cs.get("player_alive", False)),
        accepted_score=int(cs.get("last_game_score", 0)), accepted_wave=int(cs.get("last_level_number", 0)))


class RejectedGapTelemetry:
    def __init__(self, *, enabled=False, clock_ns=time.monotonic_ns):
        self.enabled = bool(enabled)
        self._clock = clock_ns
        self._lock = threading.Lock()
        self._pid = os.getpid()
        self._instance = clock_ns()
        self._next_connection = 0
        self._clients = {}
        self._witnesses = []
        self._counts = dict.fromkeys(COUNTERS, 0)
        self._fault = False
        self._saturated = False

    def _inc(self, key, value=1):
        value = int(value)
        if value < 0:
            raise ValueError("Negative diagnostic increment")
        new = self._counts[key] + value
        self._saturated |= new > MAX_COUNT
        self._counts[key] = min(MAX_COUNT, new)

    def _close(self, client, row, outcome):
        row["outcome"] = outcome
        row["closed_monotonic_ns"] = self._clock()
        if len(self._witnesses) < MAX_WITNESSES:
            self._witnesses.append(row)
        else:
            self._inc("witness_overflow")
        client["pending"] = client["closing"] = None

    def event(self, kind, connection=None, **data):
        """Fail open for application behavior, fail visibly for diagnostic validity.

        Returned connection/ticket is diagnostic only. Callers never branch any
        action/replay/reset decision on it. Ordinary events with no gap allocate
        no witness. A fault makes available=False; zero counters then prove nothing.
        """
        if not self.enabled or (connection is None and kind != "connect"):
            return None
        try:
            with self._lock:
                return self._event(kind, connection, data)
        except Exception:
            self._fault = True
            return None

    def _event(self, kind, connection, data):
        if kind == "connect":
            if len(self._clients) >= MAX_CLIENTS:
                self._inc("tracking_overflow")
                return None
            self._next_connection += 1
            key = self._next_connection
            self._clients[key] = dict(cid=int(data["cid"]), sequence=0, pending=None, closing=None)
            self._inc("connections")
            return key
        if connection is None:
            return None
        client = self._clients[connection]
        if kind == "received":
            client["sequence"] += 1
            self._inc("payloads_complete")
            return None
        if kind in ("receive_header_idle", "receive_header_eof", "receive_invalid_length", "receive_broken_payload", "param_mismatch", "short_payload"):
            self._inc(kind)
            return None
        if kind == "reject":
            reason = data["reason"]
            if reason not in REASONS:
                raise ValueError("Unknown reject category")
            self._inc(reason)
            row = client["pending"]
            if row is None:
                self._inc("gaps_opened")
                row = dict(connection_sequence=connection, cid=client["cid"],
                    first_receive_sequence=client["sequence"], first_monotonic_ns=self._clock(),
                    reject_before=_state(data.get("cs")), reasons=dict.fromkeys(REASONS, 0),
                    neutral_write_ok=0, neutral_write_failed=0, before_reset=None, after_reset=None,
                    previous_step_entered=False, nstep=None, enqueue_calls=0, enqueue_returns=0,
                    including_current_input_enqueue_calls=0, next_action=None)
                client["pending"] = row
            row["reasons"][reason] = min(MAX_COUNT, row["reasons"][reason] + 1)
            row["last_receive_sequence"] = client["sequence"]
            row["last_monotonic_ns"] = self._clock()
            return None
        if kind == "neutral_result":
            key = "neutral_write_ok" if data["ok"] else "neutral_write_failed"
            self._inc(key)
            if client["pending"] is not None:
                client["pending"][key] = min(MAX_COUNT, client["pending"][key] + 1)
            return None
        if kind == "accepted":
            self._inc("accepted_frames")
            row = client["pending"]
            if row is None:
                return None
            client["pending"] = None
            client["closing"] = row
            row["first_accepted_receive_sequence"] = client["sequence"]
            row["first_accepted_monotonic_ns"] = self._clock()
            row["before_reset"] = _state(data["cs"])
            row["accepted_wire"] = {k: data[k] for k in ("score", "wave", "alive", "done", "new_game")}
            # Continuity is unknown until the real first-frame/reset paths complete.
            row["same_classifier_game"] = None
            self._inc("accepted_closures")
            self._inc("new_game_classified", int(data["new_game"]))
            return connection
        if kind == "disconnect":
            row = client["closing"] or client["pending"]
            if row is not None:
                self._inc("disconnect_closures")
                self._close(client, row, "handler_ended_without_completed_accepted_frame")
            del self._clients[connection]
            return None
        row = client["closing"]
        if row is None:
            return None
        if kind == "after_reset":
            row["after_reset"] = _state(data["cs"])
            uid = row["reject_before"]["game_uid"]
            row["same_classifier_game"] = (uid > 0 and not row["accepted_wire"]["new_game"] and
                uid == row["before_reset"]["game_uid"] == row["after_reset"]["game_uid"])
            self._inc("same_classifier_game", int(row["same_classifier_game"]))
            row["replay_writable_after_reset"] = bool(data["writable"])
            row["measurement_boundary"] = (
                row["reject_before"]["measurement_generation"] != row["after_reset"]["measurement_generation"] or
                row["reject_before"]["measurement_active"] != row["after_reset"]["measurement_active"])
            self._inc("measurement_boundary", int(row["measurement_boundary"]))
        elif kind == "previous_step":
            row["previous_step_entered"] = True
            self._inc("previous_step_entered")
        elif kind == "nstep_before":
            pending = getattr(data["nstep"], "_deque", ())
            # Held add() flushes ALL old prefixes before appending a different actor group.
            flush = len(pending) if pending and _group(pending[-1].actor) != _group(data["actor"]) else 0
            row["nstep"] = dict(input_actor=_actor(data["actor"]), training_done=bool(data["done"]),
                pending_before=len(pending), group_flush_before_input=flush, matured_total=None,
                matured_including_current_input=None)
            self._inc("nstep_add_called")
        elif kind == "nstep_after":
            count = int(data["count"]); flush = row["nstep"]["group_flush_before_input"]
            if count < flush:
                raise ValueError("Held nstep emission ordering differs")
            row["nstep"].update(matured_total=count, matured_including_current_input=count-flush)
            self._inc("matured_total", count); self._inc("group_flush_before_input", flush)
            self._inc("matured_including_current_input", count-flush)
        elif kind == "one_step":
            row["nstep"] = dict(input_actor=_actor(data["actor"]), training_done=bool(data["done"]),
                pending_before=0, group_flush_before_input=0, matured_total=1,
                matured_including_current_input=1)
            self._inc("one_step_called"); self._inc("matured_total"); self._inc("matured_including_current_input")
        elif kind == "enqueue_called":
            i = row["enqueue_calls"]; row["enqueue_calls"] += 1
            includes = i >= row["nstep"]["group_flush_before_input"]
            row["including_current_input_enqueue_calls"] += int(includes)
            self._inc("enqueue_calls"); self._inc("including_current_input_enqueue_calls", int(includes))
        elif kind == "enqueue_returned":
            row["enqueue_returns"] += 1
            self._inc("enqueue_returns")
        elif kind == "next_action":
            row["next_action"] = _state(data["cs"])["last_action"]
            row["next_action_source"] = _actor(data["cs"].get("prev_action_source"))
        elif kind == "finish":
            self._close(client, row, data["outcome"])
        else:
            raise ValueError("Unknown observation stage")
        return None

    def snapshot(self):
        """Bounded readonly metadata copy; never drain counters or retain caller objects."""
        with self._lock:
            return dict(schema=SCHEMA, enabled=self.enabled,
                available=self.enabled and not self._fault and not self._saturated and self._counts["tracking_overflow"] == 0,
                process_id=self._pid, instance_monotonic_ns=self._instance,
                observer_error=self._fault, counter_saturated=self._saturated,
                counters=dict(self._counts), active_tracked_clients=len(self._clients),
                pending_gaps=sum(c["pending"] is not None for c in self._clients.values()),
                accepted_frames_in_progress=sum(c["closing"] is not None for c in self._clients.values()),
                witness_limit=MAX_WITNESSES, witnesses=deepcopy(self._witnesses),
                scope="Unthrottled tracked payload/gap events. UID continuity is classifier-only. Send/queue calls do not prove client application, physical replay insertion, sampling, learning or causal efficacy.")
