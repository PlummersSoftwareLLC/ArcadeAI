"""Isolated deadline32 hooks; import performs no I/O or runtime actions.

The caller supplies a SHA-bound private StartupProxy class and the real pure
recorder. One sequential proxy owns each origin request/reply. It registers
before forwarding and records the successful completed exchange before leaving
the in-flight barrier. No model, main server or source file is modified here.
"""
import copy
import hashlib
import inspect
from pathlib import Path
import struct
import threading
import time

SLOTS = tuple(range(4096, 4128))
MAX_DRAIN_NS = 3_500_000_000
REQUEST = struct.Struct('>4sIII')


def require(ok, message):
    if not ok:
        raise ValueError(message)


class DeadlineRetired(RuntimeError):
    """Explicit post-seal private control path; never a natural game terminal."""


class FirstGameRegistration:
    """Satisfy original START registration without a full-tail STOP permit.

    This NEW deadline scope never pretends that unfinished games completed.
    After sealing, the private owner tears down its exact original processes.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.registered = {}

    @property
    def permit(self):
        return None

    def register_start(self, **value):
        keys = {'slot', 'session', 'connection', 'nonce', 'client_id', 'journal_game_id', 'certificate_identifier'}
        require(set(value) == keys and type(value['slot']) is int and value['slot'] in SLOTS,
                'Exact first-game registration required')
        with self.lock:
            old = self.registered.get(value['slot'])
            require(old is None or old == value, 'First-game registration cannot change')
            self.registered[value['slot']] = copy.deepcopy(value)


class DeadlineExchangeGate:
    """Stop new origin entries at D; drain every registered exchange once."""

    def __init__(self, *, clock_ns=time.monotonic_ns):
        self.clock = clock_ns
        self.condition = threading.Condition()
        self.deadline = None
        self.closed = False
        self.inflight = {}
        self.serial = self.entered = self.finished = 0
        self.sealed = threading.Event()
        self.teardown_declared = threading.Event()

    def arm(self, deadline_monotonic_ns):
        with self.condition:
            require(self.deadline is None and not self.closed, 'Gate already armed or closed')
            require(type(deadline_monotonic_ns) is int and deadline_monotonic_ns > self.clock(), 'Future exact deadline required')
            self.deadline = deadline_monotonic_ns

    def enter(self, slot):
        with self.condition:
            require(type(slot) is int and slot in SLOTS and slot not in self.inflight, 'Foreign or duplicate slot exchange')
            now = self.clock()
            if self.closed or (self.deadline is not None and now >= self.deadline):
                self.closed = True
                return None
            self.serial += 1
            ticket = (slot, self.serial, now)
            self.inflight[slot] = ticket
            self.entered += 1
            return ticket

    def leave(self, ticket):
        with self.condition:
            require(self.inflight.get(ticket[0]) == ticket, 'Foreign or repeated exchange completion')
            del self.inflight[ticket[0]]
            self.finished += 1
            self.condition.notify_all()

    def close_and_drain(self):
        with self.condition:
            require(self.deadline is not None and self.clock() >= self.deadline, 'Cannot close before fixed deadline')
            self.closed = True
            # Monotonic work budget is fixed relative to D, never reanchored.
            hard_end = self.deadline + MAX_DRAIN_NS
            while self.inflight:
                remaining = hard_end - self.clock()
                require(remaining > 0, 'Unsettled origin exchange exceeded service bound')
                self.condition.wait(min(remaining / 1e9, .05))
            closed = self.clock()
            require(closed <= hard_end and self.entered == self.finished, 'Incomplete or late origin barrier')
            return dict(schema='robotron-deadline32-origin-barrier-v1', deadline_monotonic_ns=self.deadline,
                no_new_origin_entries=True, inflight=0, closed_monotonic_ns=closed,
                entered=self.entered, finished=self.finished, fixed_drain_bound_ns=MAX_DRAIN_NS)

    def mark_sealed(self):
        with self.condition:
            require(self.closed and not self.inflight, 'Cannot announce a seal before the origin barrier')
            self.sealed.set()

    def declare_teardown(self, *, server_shutdown_is_set):
        with self.condition:
            require(self.sealed.is_set() and self.closed and not self.inflight
                    and server_shutdown_is_set is True,
                    'Scored rows must be sealed before intentional private teardown')
            self.teardown_declared.set()

    def retire_received_request(self, proxy, peer, origin, raw):
        # No origin forwarding, score mutation, socket close or process signal.
        # The native handler catches ONLY this dedicated, positively gated path.
        end = self.deadline + MAX_DRAIN_NS
        for event in (self.sealed, self.teardown_declared):
            remaining = max(0.0, (end - self.clock()) / 1e9)
            require(event.wait(remaining), 'Deadline data/teardown barrier did not finish within service bound')
        require(self.closed and self.clock() >= self.deadline, 'Premature deadline retirement')
        raise DeadlineRetired('Selected deadline snapshot sealed; retire original slot ' + str(proxy.subject['slot']))


def _client_snapshot(server, cid):
    with server.client_lock:
        cs = server.client_states.get(cid)
        require(cs is not None, 'Original origin client disappeared')
        keys = ('frames', 'game_uid', 'game_score', 'raw_score_prev',
                'measurement_generation', 'measurement_active', 'client_slot', 'eval_only')
        value = {key: cs[key] for key in keys}
        # Frozen SocketServer allocates this key only on a carry, reset or
        # reconnect. Its accepted-score path uses get(..., 0) before allocation.
        # Keep raw_score_prev strict: no accepted raw score is invented here.
        offset = cs.get('score_offset', 0)
        require(type(offset) is int and offset >= 0, 'Actual score carry is invalid')
        value['score_offset'] = offset
        value['actual_score_offset_present'] = 'score_offset' in cs
        # This source counter is allocated on its first coercion; missing is zero.
        value['coerced_score_dips'] = cs.get('coerced_score_dips', 0)
        return value


def selected_journal_snapshot(server, journal_game_id):
    with server.game_journal.lock:
        game = server.game_journal.measurement_games.get(journal_game_id)
        require(game is not None, 'Selected first game is missing from retained measurement journal')
        keys = ('journal_game_id', 'game_uid', 'known_start', 'first_play_level',
                'measurement_active', 'measurement_generation', 'mixed_experiment',
                'mixed_measurement', 'score', 'playable_frames', 'finished')
        value = {key: game[key] for key in keys}
        value['experiment'] = game['start']['experiment']
        value['result'] = copy.deepcopy(game['result'])
        return value


def bind_first_member(proxy, recorder, policy):
    require(proxy.handoff is not None and proxy.issuer is not None, 'First START is not certified')
    selected = selected_journal_snapshot(proxy.server, proxy.handoff['journal_game_id'])
    member = dict(slot=proxy.subject['slot'], session=proxy.subject['session'], connection=proxy.subject['connection'],
        game_uid=selected['game_uid'], journal_game_id=selected['journal_game_id'],
        start_certificate_id=proxy.handoff['certificate_identifier'], startup_nonce=proxy.issuer.nonce,
        policy_sha256=policy['policy_sha256'], measurement_generation=policy['measurement_generation'],
        experiment=policy['experiment'], policy_clocks=copy.deepcopy(policy['policy_clocks']))
    recorder.bind(proxy.subject['slot'], member)
    return member


def completed_exchange_sample(proxy, raw_request, before_ordinal, member, policy, *,
                              completed_exchange_ns, clock_ns=time.monotonic_ns):
    begin = clock_ns()
    require(type(completed_exchange_ns) is int and 0 <= completed_exchange_ns <= begin,
            'Successful exchange completion must precede its observation')
    origin = _client_snapshot(proxy.server, proxy.cid)
    selected = selected_journal_snapshot(proxy.server, member['journal_game_id'])
    # Avoid nested locks. The sequential proxy has not forwarded another request;
    # any change during this two-phase read is an operational fault, not censoring.
    require(_client_snapshot(proxy.server, proxy.cid) == origin, 'Origin state changed during post-reply journal snapshot')
    require(origin['client_slot'] == member['slot'] and origin['eval_only'] is True
            and origin['measurement_active'] is True
            and origin['measurement_generation'] == member['measurement_generation'],
            'Actual origin slot/evaluation/policy generation changed')
    magic, sequence, payload_size, meta_size = REQUEST.unpack_from(raw_request)
    require(magic == b'RSG2' and sequence == proxy.sequence and len(raw_request) == REQUEST.size + payload_size + meta_size,
            'Completed original request identity differs')
    payload = raw_request[REQUEST.size:REQUEST.size + payload_size]
    require(payload_size == 7597 and struct.unpack_from('>H', payload)[0] == 1890, 'Original preview-free wire geometry differs')
    raw_wire_score = struct.unpack_from('>I', payload, 19)[0]
    end = clock_ns()
    return dict(sequence=sequence, completed_exchange_ns=completed_exchange_ns, before_ordinal=before_ordinal,
        accepted_ordinal=origin['frames'], origin_game_uid=origin['game_uid'],
        full_score=origin['game_score'], effective_raw_score=origin['raw_score_prev'],
        score_offset=origin['score_offset'], raw_wire_score=raw_wire_score,
        coerced_score_dips=origin['coerced_score_dips'], policy_sha256=policy['policy_sha256'],
        measurement_generation=origin['measurement_generation'], selected=selected,
        source_witness=dict(schema='robotron-deadline32-completed-origin-snapshot-v1',
            process_return_monotonic_ns=completed_exchange_ns,
            snapshot_begin_monotonic_ns=begin, snapshot_end_monotonic_ns=end,
            raw_header_hex=payload[:33].hex(), original_payload_sha256=hashlib.sha256(payload).hexdigest(),
            origin_state=origin, ledger_snapshot=copy.deepcopy(proxy.ledger.summary()),
            selected_journal_game_id=member['journal_game_id']))


def build_deadline_proxy(base_class, *, expected_base_sha256, recorder, gate, policy, on_cutoff,
                         clock_ns=time.monotonic_ns):
    """Explicit private integration; caller binds the clock-corrected base SHA.

    on_cutoff parks the already received request until the cutoff rows are sealed
    and ROOT-owned teardown is declared. It MUST NOT forward it or start a new
    selected game. A runtime must classify this new post-D control path explicitly.
    """
    require(type(expected_base_sha256) is str and len(expected_base_sha256) == 64, 'Exact private base source SHA required')
    source = inspect.getsourcefile(base_class)
    require(source is not None and hashlib.sha256(Path(source).read_bytes()).hexdigest() == expected_base_sha256,
            'Actual private startup proxy source differs')
    require(callable(on_cutoff), 'Explicit new cutoff retirement path required')

    class DeadlineStartupProxy(base_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            require(self.subject['slot'] in SLOTS, 'Deadline comparison is exactly the established32 slots')
            self.deadline_member = None

        def process(self, peer, origin, raw):
            ticket = gate.enter(self.subject['slot'])
            if ticket is None:
                return on_cutoff(self, peer, origin, raw)
            try:
                before = self.state()['frames']
                result = super().process(peer, origin, raw)
                completed_exchange_ns = clock_ns()
                # Binding happens at the original first handoff, before first play.
                # It is never rebound when later games start in this same process.
                if self.handoff is not None:
                    if self.deadline_member is None:
                        self.deadline_member = bind_first_member(self, recorder, policy)
                    sample = completed_exchange_sample(self, raw, before, self.deadline_member, policy,
                        completed_exchange_ns=completed_exchange_ns, clock_ns=clock_ns)
                    recorder.observe(self.subject['slot'], sample)
                return result
            finally:
                gate.leave(ticket)

    return DeadlineStartupProxy


def arm_ready32(proxies, boundary, recorder, gate, policy):
    require(set(proxies) == set(SLOTS), 'All32 original proxies required')
    require(all(p.prefix_verified.is_set() and p.sequence > 1200 and p.error is None
                and p.handoff is not None and p.deadline_member is not None for p in proxies.values()),
            'All32 raw first-play startup prefixes must be certified')
    anchor = recorder.arm(dict(all_first_play_certified=True, policy_sha256=policy['policy_sha256'],
        measurement_generation=policy['measurement_generation'], boundary=copy.deepcopy(boundary)))
    gate.arm(anchor['deadline_monotonic_ns'])
    return anchor
