"""Inactive prospective quota64 host drain; NOT selected by any runtime.

The first two starts per slot remain mandatory irrespective of outcome.
Admission timestamps describe the outer start horizon, while quota closure
permits full-tail drain before that horizon. No qualification is conferred.
Actual scoped guards and runtime integration remain outstanding.
"""
GAMES_PER_SLOT = 1
ACTOR_COUNT = 64
import copy
import hashlib
import inspect
import json
from pathlib import Path
import re
import threading
import time
JOURNAL_SHA = '96864c78df67f46bc58b1c4af4ce1bceb3791a8842fdcf02871385a1013d1e0f'
CONTROLLER_SHA = '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6'
SLOTS = tuple(range(4096, 4096 + ACTOR_COUNT))
VIEW_SHA = '2e8d0aa660686875a87c8d44f5978b9dcfb60d07ac179080724f760e4ccc01fd'
COHORT_SELECTION = dict(schema='robotron-fixed-slot64-selection-v1', strategy='first_known_start_per_declared_slot', actor_slots=list(SLOTS), games_per_slot=GAMES_PER_SLOT, expected_games=64, minimum_complete_games=50, outer_start_horizon_s=21540, whole_cohort_timeout_from_enter_s=21600, timestamp_close_role='outer_start_horizon', selector_source_sha256='2e8d0aa660686875a87c8d44f5978b9dcfb60d07ac179080724f760e4ccc01fd')

def require(value, message):
    if not value:
        raise ValueError(message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def same_completed_membership(saved, fresh):
    """Permit append-only outside starts after the terminal controller tick.

    Every selected member, result and accounting field must still match.
    Extra starts remain in the original raw journals for independent audit.
    """
    key = 'retained_outside_cohort_ids'
    if type(saved) is not dict or type(fresh) is not dict:
        return False
    left, right = (saved.get(key), fresh.get(key))
    if type(left) is not list or type(right) is not list:
        return False
    if right[:len(left)] != left or len(right) != len(set(right)):
        return False
    if set(right) & set(fresh.get('started_ids', [])):
        return False
    return canonical({k: v for k, v in saved.items() if k != key}) == canonical({k: v for k, v in fresh.items() if k != key})

def integer(value, minimum=0, maximum=(1 << 64) - 1):
    require(type(value) is int and minimum <= value <= maximum, 'Invalid host drain integer')
    return value

def hex_value(value, length):
    require(type(value) is str and re.fullmatch('[0-9a-f]{%d}' % length, value) and (value != '0' * length), 'Invalid host drain identity')
    return value

def bound_source(obj, name, sha):
    source = inspect.getsourcefile(type(obj))
    require(type(obj).__name__ == name and source is not None and (hashlib.sha256(Path(source).read_bytes()).hexdigest() == sha), 'Exact selected ' + name + ' source required')

class _DrainPermit:
    __slots__ = ('payload', 'identifier', 'used_slots')

    def __init__(self, payload):
        self.payload = canonical(payload)
        self.identifier = hashlib.sha256(self.payload).hexdigest()
        self.used_slots = set()

class CohortDrain:

    def __init__(self, journal, controller, *, subjects, policy_reader, admission_reader, wall_ns=time.time_ns, monotonic_ns=time.monotonic_ns):
        bound_source(journal, 'FixedSlotCohortView', VIEW_SHA)
        bound_source(journal.journal, 'GameJournal', JOURNAL_SHA)
        bound_source(controller, 'FixedSlotManagedMeasurement', VIEW_SHA)
        require(len(type(controller).__bases__) == 1 and type(controller).__bases__[0].__name__ == 'ManagedMeasurement' and (hashlib.sha256(Path(inspect.getsourcefile(type(controller).__bases__[0])).read_bytes()).hexdigest() == CONTROLLER_SHA), 'Exact original measurement base required')
        require(journal.completion_policy == 'confirmed_reset_reserves_v1' and controller.journal is journal, 'Actual confirmed controller/journal binding required')
        require(type(subjects) is list and len(subjects) == ACTOR_COUNT, 'Original32 subjects required')
        self.subjects = {}
        for subject in subjects:
            require(set(subject) == {'slot', 'session', 'connection'}, 'Exact actor subject required')
            slot = integer(subject['slot'], 4096, 4096 + ACTOR_COUNT - 1)
            hex_value(subject['session'], 32)
            hex_value(subject['connection'], 32)
            require(slot not in self.subjects, 'Duplicate original slot')
            self.subjects[slot] = copy.deepcopy(subject)
        require(tuple(sorted(self.subjects)) == SLOTS and len({s['session'] for s in subjects}) == ACTOR_COUNT and (len({s['connection'] for s in subjects}) == ACTOR_COUNT), 'Distinct all32 actor subjects required')
        self.journal, self.controller = (journal, controller)
        self.policy_reader, self.admission_reader = (policy_reader, admission_reader)
        self.wall_ns, self.monotonic_ns = (wall_ns, monotonic_ns)
        self.lock = threading.Lock()
        self.state = 'waiting'
        self.registrations = {}
        self.frozen_ids = None
        self.permit = None
        self.policy, self.window = self._subject()
        require(journal.policy() == self.policy, 'Actual quota view and certificate policy differ')
        status = self._controller()
        require(status['phase'] in ('collecting', 'draining'), 'Admission must already be established')
        self.start_ts, self.close_ts = (status['start_ts'], status['close_ts'])
        self.clock_anchor = (integer(wall_ns()), integer(monotonic_ns()))

    def _subject(self):
        policy = copy.deepcopy(self.policy_reader())
        require(policy['measurement_active'] is True and policy['training_enabled'] is policy['replay_enabled'] is False and (type(policy['epsilon']) in (int, float)) and (type(policy['expert_ratio']) in (int, float)) and (policy['epsilon'] == policy['expert_ratio'] == 0), 'Frozen greedy policy required')
        require(canonical(policy.get('cohort_selection')) == canonical(COHORT_SELECTION), 'Certificate policy must bind the exact quota64 strategy and bounds')
        integer(policy['measurement_generation'], 1)
        for key in ('checkpoint_sha256', 'policy_load_id'):
            hex_value(policy[key], 64)
        for key in ('learner_frame_count', 'training_steps', 'optimized_samples'):
            integer(policy[key])
        require(type(policy['experiment']) is str and bool(policy['experiment'].strip()), 'Experiment required')
        window = copy.deepcopy(self.admission_reader())
        require(type(window) is dict and set(window) == {'open_unix_ns', 'close_unix_ns', 'generation', 'experiment'}, 'Exact fixed admission required')
        integer(window['open_unix_ns'])
        integer(window['close_unix_ns'], window['open_unix_ns'] + 1)
        require(type(window['generation']) is int and window['generation'] == policy['measurement_generation'] and (window['experiment'] == policy['experiment']), 'Policy/admission mismatch')
        require(window['close_unix_ns'] - window['open_unix_ns'] == 21540000000000, 'Original outer start horizon differs')
        return (policy, window)

    def _controller(self):
        status = copy.deepcopy(self.controller.status())
        require(status['active'] is True and status['label'] == self.policy['experiment'] and (type(status['generation']) is int) and (status['generation'] == self.policy['measurement_generation']) and (int(status['start_ts'] * 1000000000.0) == self.window['open_unix_ns']) and (int(status['close_ts'] * 1000000000.0) == self.window['close_unix_ns']), 'Actual controller window/generation changed')
        return status

    def _live(self):
        require(self.state != 'failed', 'Drain authority failed; no rescue or retry')
        require(self._subject() == (self.policy, self.window), 'Loaded policy/clocks or admission moved')
        now, mono = (integer(self.wall_ns()), integer(self.monotonic_ns()))
        wall0, mono0 = self.clock_anchor
        require(now >= wall0 and mono >= mono0 and (abs(now - wall0 - (mono - mono0)) <= 50000000), 'Host drain clocks disagree or reversed')
        status = self._controller()
        require(status['valid'] is not False, 'Original controller invalidated the cohort')
        return (now, mono, status)

    def register_start(self, *, slot, session, connection, nonce, client_id, journal_game_id, certificate_identifier):
        """Join the bridge's actual successful handoff to the real journal row."""
        with self.lock:
            try:
                self._live()
                require(self.permit is None and slot not in self.registrations, 'Original handoff already registered')
                require(self.subjects.get(slot) == dict(slot=slot, session=session, connection=connection), 'Foreign original handoff subject')
                hex_value(nonce, 64)
                hex_value(certificate_identifier, 64)
                integer(client_id)
                with self.journal.lock:
                    game = copy.deepcopy(self.journal.measurement_games.get(journal_game_id))
                require(game is not None and game['client_id'] == client_id and (game['client_slot'] == slot) and (game['known_start'] is game['measurement_active'] is game['eval_only'] is True) and (game['start_reason'] == 'prospective_certified_first_start_v2') and (game['measurement_generation'] == self.policy['measurement_generation']) and (self.start_ts <= game['start_unix_s'] <= self.close_ts), 'Actual original certified game differs')
                certificate = game['start']['startup_certificate']
                body = {k: v for k, v in certificate.items() if k != 'identifier'}
                require(certificate['identifier'] == certificate_identifier == digest(body) and body['schema'] == 'robotron-prospective-startup-journal-certificate-v2' and all((body[k] == v for k, v in dict(slot=slot, session=session, connection=connection, nonce=nonce).items())) and (body['policy'] == self.policy) and (body['admission'] == self.window), 'Original startup certificate binding differs')
                origin = body['evidence']['origin_acceptance']
                require(origin['accepted'] is True and origin['client_id'] == client_id and (origin['client_slot'] == slot) and (origin['game_uid'] == game['game_uid']), 'Original accepted startup UID differs')
                require(journal_game_id not in {r['journal_game_id'] for r in self.registrations.values()}, 'Original certified journal ID reused')
                self.registrations[slot] = dict(slot=slot, session=session, connection=connection, nonce=nonce, client_id=client_id, journal_game_id=journal_game_id, certificate_identifier=certificate_identifier)
            except Exception:
                self.state = 'failed'
                raise

    def _cohort(self, now):
        cohort = copy.deepcopy(self.journal.cohort_status(self.policy['experiment'], self.start_ts, self.close_ts))
        ids = tuple(sorted(cohort['started_ids']))
        require(len(ids) == len(set(ids)) == cohort['started'], 'Original cohort denominator differs')
        require(cohort['valid'] is True and cohort['abandoned'] == 0 and (not cohort['abandoned_ids']), 'An admitted game was abandoned or invalid')
        require(cohort['count'] + cohort['pending'] == cohort['started'], 'Original cohort accounting differs')
        require(cohort['schema'] == 'robotron-fixed-slot64-cohort-status-v1' and cohort['admission_mode'] == COHORT_SELECTION['strategy'] and (cohort['timestamp_close_role'] == 'outer_start_horizon') and (cohort['expected_games'] == 64) and (cohort['games_per_slot'] == GAMES_PER_SLOT) and (cohort['minimum_complete_games'] == 50), 'Original quota strategy changed')
        if now >= self.window['close_unix_ns']:
            require(cohort['closed'] is True, 'Journal and host outer-horizon clocks disagree')
        if cohort['closed']:
            require(cohort['closed_by'] == 'slot_quota' and cohort['all_slot_quotas_admitted'] is True and (cohort['started'] == 64) and (cohort['slot_admitted_counts'] == {str(slot): GAMES_PER_SLOT for slot in SLOTS}), 'Every original slot quota is required before full-tail drain')
            if self.frozen_ids is None:
                self.frozen_ids = ids
            require(ids == self.frozen_ids, 'Original admission membership changed after close')
        return cohort

    def _complete_rows(self, cohort):
        require(cohort['count'] == cohort['started'] == 64 and cohort['slot_admitted_counts'] == {str(slot): GAMES_PER_SLOT for slot in SLOTS}, 'Every one of the64 selected full games is mandatory')
        require(set(self.registrations) == set(SLOTS) and set(cohort['started_actor_slots']) == set(SLOTS) and {r['journal_game_id'] for r in self.registrations.values()}.issubset(self.frozen_ids), 'All32 original certified starts must remain admitted')
        require(cohort['closed'] is cohort['complete'] is cohort['valid'] is True and cohort['pending'] == cohort['abandoned'] == 0 and (not cohort['pending_ids']) and (cohort['count'] == cohort['started'] >= ACTOR_COUNT), 'Every admitted full tail must finish')
        rows = cohort['rows']
        require(len(rows) == cohort['count'] and {r['journal_game_id'] for r in rows} == set(self.frozen_ids), 'Completed membership differs from the frozen denominator')
        with self.journal.lock:
            games = {key: copy.deepcopy(self.journal.measurement_games.get(key)) for key in set(self.frozen_ids) | {r['terminal_confirmation']['next_journal_game_id'] for r in rows if type(r.get('terminal_confirmation')) is dict}}
        for row in rows:
            slot = row['client_slot']
            registration = self.registrations.get(slot)
            require(registration is not None and row['client_id'] == registration['client_id'] and (row['known_start'] is row['complete'] is row['eligible'] is row['eval_only'] is row['measurement_active'] is True) and (row['excluded_reason'] == '') and (row['first_play_level'] == 1) and (row['playable_frames'] > 0) and (row['measurement_generation'] == self.policy['measurement_generation']) and (row['experiment'] == self.policy['experiment']) and (row['completion_policy'] == 'confirmed_reset_reserves_v1'), 'Original completed row is not an eligible confirmed full game')
            game = games.get(row['journal_game_id'])
            require(game is not None and game['finished'] is True and (game['result'] == row), 'Completed row differs from the retained actual journal member')
            terminal = row['terminal_confirmation']
            require(type(terminal) is dict and terminal['schema'] == 'robotron-confirmed-game-reset-v1' and (terminal['reason'] == row['boundary_reason']) and (terminal['previous_score'] == row['score']) and (terminal['previous_game_uid'] == row['game_uid']) and (terminal['reason'] in ('score_reset', 'zero_score_restart')), 'Actual terminal reset is missing')
            next_game = games.get(terminal['next_journal_game_id'])
            require(next_game is not None and next_game['journal_game_id'] != row['journal_game_id'] and (next_game['known_start'] is next_game['measurement_active'] is True) and (next_game['client_id'] == row['client_id']) and (next_game['client_slot'] == slot) and (next_game['game_uid'] == terminal['next_game_uid']) and (next_game['start_frame']['score'] == terminal['next_score']) and (next_game['start_frame']['level'] == terminal['next_wave']) and (next_game['start_frame']['raw_reserves'] == terminal['next_raw_reserves']) and (next_game['measurement_generation'] == row['measurement_generation']) and (next_game['start']['experiment'] == row['experiment']) and (next_game['start_unix_s'] >= row['end_unix_s']), 'Actual next-reset journal join differs')
        return digest(dict(started_ids=list(self.frozen_ids), rows=rows))

    def try_issue(self):
        """None means keep playing; errors permanently invalidate this authority."""
        with self.lock:
            try:
                now, mono, status = self._live()
                cohort = self._cohort(now)
                require(self.permit is None, 'Original drain permit already issued')
                if not cohort['closed'] or cohort['pending']:
                    require(status['complete'] is False, 'Controller completed before actual cohort')
                    return None
                if status['complete'] is False:
                    return None
                require(status['complete'] is status['valid'] is True and status['phase'] == 'complete', 'Actual controller has not certified full-tail completion')
                fingerprint = self._complete_rows(cohort)
                require(same_completed_membership(status['cohort'], cohort), 'Controller completion and fresh actual selected members differ')
                self.permit = _DrainPermit(dict(schema='robotron-host-fixed-slot64-complete-cohort-drain-v1', cohort_selection=copy.deepcopy(COHORT_SELECTION), retained_outside_start_ids=cohort['retained_outside_cohort_ids'], policy=self.policy, admission=self.window, started_ids=list(self.frozen_ids), started=cohort['started'], count=cohort['count'], cohort_sha256=fingerprint, original_subjects=[self.registrations[s] for s in SLOTS], issued_unix_ns=now, issued_monotonic_ns=mono, quality_qualified=False))
                self.state = 'issued'
                return self.permit
            except Exception:
                self.state = 'failed'
                raise

    def authorize_slot(self, permit, *, slot, session, connection, nonce, sequence):
        """Consume before send. A failed send never permits a second STOP."""
        with self.lock:
            try:
                now, mono, status = self._live()
                require(self.state == 'issued' and isinstance(permit, _DrainPermit) and (permit is self.permit) and (hashlib.sha256(permit.payload).hexdigest() == permit.identifier), 'Original registered drain permit required')
                integer(sequence, 1201, (1 << 32) - 1)
                registration = self.registrations.get(slot)
                require(registration is not None and all((registration[k] == v for k, v in dict(slot=slot, session=session, connection=connection, nonce=nonce).items())) and (slot not in permit.used_slots), 'Original slot drain authorization already consumed or foreign')
                cohort = self._cohort(now)
                fingerprint = self._complete_rows(cohort)
                body = json.loads(permit.payload)
                require(status['complete'] is status['valid'] is True and status['phase'] == 'complete' and same_completed_membership(status['cohort'], cohort) and (fingerprint == body['cohort_sha256']), 'Original completed cohort changed before STOP')
                permit.used_slots.add(slot)
                return dict(schema='robotron-host-cohort-drain-slot-consumption-v1', permit_identifier=permit.identifier, cohort_sha256=fingerprint, slot=slot, session=session, connection=connection, nonce=nonce, sequence=sequence, authorized_unix_ns=now, authorized_monotonic_ns=mono, consumed_before_send=True)
            except Exception:
                self.state = 'failed'
                raise
