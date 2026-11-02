"""Pure, isolated first-game deadline scores. No files, runtime or model actions.

The private caller must bind at the first certified START, observe EVERY
successful origin exchange before clearing its in-flight registration, and
close its entry barrier at D before sealing. Times identify completed host
exchange observations, not the instant the emulated ROM changed its score.
"""
from copy import deepcopy
import math
import statistics
import threading
import time

SLOTS = tuple(range(4096, 4128))
HORIZON_NS = 3_600_000_000_000
MAX_AGE_NS = 3_500_000_000
SCORE_MODULUS = 100_000_000
MEMBER_KEYS = {'slot', 'session', 'connection', 'game_uid', 'journal_game_id',
               'start_certificate_id', 'startup_nonce', 'policy_sha256',
               'measurement_generation', 'experiment', 'policy_clocks'}
CLOCK_KEYS = {'learner_frame_count', 'training_steps', 'optimized_samples'}


def require(value, message):
    if not value:
        raise ValueError(message)


def integer(value, label, minimum=0, maximum=None):
    require(type(value) is int and value >= minimum and
            (maximum is None or value <= maximum), 'Invalid ' + label)
    return value


def hex_value(value, size, label):
    require(type(value) is str and len(value) == size and value != '0' * size
            and all(c in '0123456789abcdef' for c in value), 'Invalid ' + label)


def identifier(value, label):
    require(type(value) is str and 0 < len(value) <= 200 and
            all(ord(c) >= 32 for c in value), 'Invalid ' + label)


class DeadlineScoreRecorder:
    """One immutable first-game member per slot; exact fixed host deadline."""

    def __init__(self, *, clock_ns=time.monotonic_ns):
        self._clock = clock_ns
        self._lock = threading.Lock()
        self._members = {}
        self._last_packets = {}
        self._scores = {}
        self._policy = None
        self._anchor = self._deadline = self._readiness = self._sealed = None
        self._anchor_scores = None
        self._anchor_packets = None
        self._after_deadline_ignored = 0

    def bind(self, slot, member):
        with self._lock:
            require(self._sealed is None, 'Deadline result already sealed')
            require(type(slot) is int and slot in SLOTS, 'Foreign slot')
            require(type(member) is dict and set(member) == MEMBER_KEYS, 'Exact first-game member required')
            value = deepcopy(member)
            require(value['slot'] == slot, 'Member slot differs')
            integer(value['game_uid'], 'first game UID', 1)
            integer(value['measurement_generation'], 'generation', 1)
            for key in ('session', 'connection'):
                hex_value(value[key], 32, key)
            for key in ('start_certificate_id', 'startup_nonce', 'policy_sha256'):
                hex_value(value[key], 64, key)
            for key in ('journal_game_id', 'experiment'):
                identifier(value[key], key)
            clocks = value['policy_clocks']
            require(type(clocks) is dict and set(clocks) == CLOCK_KEYS, 'Exact frozen policy clocks required')
            for key in CLOCK_KEYS:
                integer(clocks[key], key)
            policy = {key: value[key] for key in ('policy_sha256', 'policy_clocks',
                                                 'measurement_generation', 'experiment')}
            require(self._policy is None or self._policy == policy, 'Frozen policy or generation changed')
            if slot in self._members:
                require(self._members[slot] == value, 'First-game binding cannot change')
                return deepcopy(value)
            require(self._anchor is None, 'Membership cannot grow after arming')
            for old in self._members.values():
                for key in ('game_uid', 'journal_game_id', 'start_certificate_id', 'startup_nonce'):
                    require(value[key] != old[key], 'First-game identity reused across slots')
                require(not ({value['session'], value['connection']} &
                             {old['session'], old['connection']}), 'Transport identity reused')
            require(value['session'] != value['connection'], 'Session and connection must differ')
            self._members[slot] = value
            self._policy = policy
            return deepcopy(value)

    def _journal(self, member, selected):
        require(type(selected) is dict, 'Selected journal snapshot required')
        integer(selected['game_uid'], 'selected game UID', 1)
        integer(selected['measurement_generation'], 'selected generation', 1)
        for key in ('journal_game_id', 'game_uid', 'measurement_generation', 'experiment'):
            require(selected[key] == member[key], 'Selected journal identity or policy differs')
        require(selected['known_start'] is selected['measurement_active'] is True and
                selected['mixed_experiment'] is selected['mixed_measurement'] is False,
                'Uncertain start or mixed policy cannot be censored')
        require(selected['first_play_level'] is None or
                (type(selected['first_play_level']) is int and selected['first_play_level'] == 1),
                'First game did not begin on wave 1')
        integer(selected['score'], 'selected journal score')
        integer(selected['playable_frames'], 'playable frames')
        require(type(selected['finished']) is bool, 'Journal finish classification required')
        return selected

    def _terminal(self, member, selected, sample, previous_score):
        row = selected['result']
        require(type(row) is dict and row['complete'] is row['eligible'] is True,
                'Disconnect or abandoned game is not deadline censoring')
        for key, expected in (('journal_game_id', member['journal_game_id']),
                              ('game_uid', member['game_uid']), ('client_slot', member['slot']),
                              ('measurement_generation', member['measurement_generation']),
                              ('experiment', member['experiment']), ('first_play_level', 1)):
            require(row[key] == expected, 'Completed first-game identity differs')
        require(row['known_start'] is row['measurement_active'] is True,
                'Completed game lacks the original known policy start')
        require(previous_score is not None, 'Completed first game lacks its prior accepted-score witness')
        integer(row['score'], 'completed first-game score')
        require(row['score'] == selected['score'] == previous_score['score'],
                'Completed OLDUID score differs from its last selected witness')
        terminal = row['terminal_confirmation']
        require(type(terminal) is dict and terminal['schema'] == 'robotron-confirmed-game-reset-v1',
                'Natural completion needs original confirmed reset evidence')
        require(terminal['previous_game_uid'] == member['game_uid'] and
                terminal['next_game_uid'] == sample['origin_game_uid'] and
                terminal['previous_score'] == row['score'], 'Terminal OLDUID/score join differs')
        identifier(terminal['next_journal_game_id'], 'next journal game ID')
        require(terminal['next_journal_game_id'] != member['journal_game_id'], 'Terminal did not advance journal game ID')
        if terminal['reason'] == 'zero_score_restart':
            require(row['score'] == terminal['next_score'] == 0 and
                    terminal['previous_raw_reserves'] == 0 and
                    type(terminal['next_raw_reserves']) is int and
                    0 < terminal['next_raw_reserves'] < 255 and
                    terminal['restart_pulse'] is True and terminal['next_wave'] in (0, 1),
                    'Unconfirmed zero-score restart')
        else:
            require(terminal['reason'] == 'score_reset' and terminal['classifier_new_game'] is True and
                    terminal['next_game_uid'] != member['game_uid'], 'Unconfirmed score reset')
        return deepcopy(row)

    def observe(self, slot, sample):
        """Credit a completed exchange at/before D, even if commit is delayed.

        The caller retains its in-flight registration through this call. A
        rejected ingest exchange updates activity only; it never invents score.
        """
        with self._lock:
            require(self._sealed is None, 'Observation after closed in-flight barrier')
            require(slot in self._members and type(sample) is dict, 'Unbound deadline member')
            member = self._members[slot]
            now = integer(self._clock(), 'current monotonic clock')
            stamp = integer(sample['completed_exchange_ns'], 'completed exchange clock')
            require(stamp <= now, 'Exchange observation is in the future')
            integer(sample['measurement_generation'], 'exchange generation', 1)
            require(sample['policy_sha256'] == member['policy_sha256'] and
                    sample['measurement_generation'] == member['measurement_generation'],
                    'Exchange frozen policy changed')
            if self._deadline is not None and stamp > self._deadline:
                self._after_deadline_ignored += 1
                return False
            sequence = integer(sample['sequence'], 'exchange sequence', 1, (1 << 32) - 1)
            before = integer(sample['before_ordinal'], 'before accepted ordinal')
            after = integer(sample['accepted_ordinal'], 'accepted ordinal')
            require(after - before in (0, 1), 'Ambiguous accepted-frame increment')
            integer(sample['origin_game_uid'], 'origin game UID', 1)
            previous_packet = self._last_packets.get(slot)
            if previous_packet:
                require(sequence == previous_packet['sequence'] + 1 and
                        before == previous_packet['accepted_ordinal'] and
                        stamp >= previous_packet['completed_exchange_ns'], 'Lost or reordered exchange observations')
            raw = integer(sample['effective_raw_score'], 'effective accepted raw score', 0, SCORE_MODULUS - 1)
            offset = integer(sample['score_offset'], 'score carry offset')
            integer(sample['raw_wire_score'], 'wire score', 0, SCORE_MODULUS - 1)
            integer(sample['coerced_score_dips'], 'coerced score dips')
            full = integer(sample['full_score'], 'unwrapped full score')
            require(offset % SCORE_MODULUS == 0 and full == raw + offset, 'Unwrapped score/carry provenance differs')
            selected = self._journal(member, sample['selected'])
            previous_score = self._scores.get(slot)
            if previous_score and previous_score['status'] == 'completed':
                require(selected['finished'] is True and selected['result'] == previous_score['completed_row'],
                        'Completed first-game result changed')
                require(selected['score'] == previous_score['score'], 'Completed journal score changed')
            elif selected['finished']:
                require(after == before + 1, 'Completion needs its accepted closing exchange')
                completed_row = self._terminal(member, selected, sample, previous_score)
                require(selected['first_play_level'] == 1 and selected['playable_frames'] > 0,
                        'No playable wave-1 first game')
                self._scores[slot] = dict(previous_score, status='completed',
                    completion_observed_ns=stamp, completion_sequence=sequence,
                    completion_accepted_ordinal=after, completed_row=completed_row,
                    completion_source_witness=deepcopy(sample.get('source_witness')))
            else:
                require(selected['result'] is None and sample['origin_game_uid'] == member['game_uid'],
                        'Selected first game disappeared without a confirmed terminal')
                require(selected['score'] == full, 'Selected journal and accepted full score disagree')
                if after == before + 1:
                    require(previous_score is None or full >= previous_score['score'],
                            'Selected unwrapped score decreased')
                    witness = {key: deepcopy(sample[key]) for key in (
                        'sequence', 'completed_exchange_ns', 'before_ordinal', 'accepted_ordinal',
                        'origin_game_uid', 'full_score', 'effective_raw_score', 'score_offset',
                        'raw_wire_score', 'coerced_score_dips', 'policy_sha256', 'measurement_generation')}
                    witness['source_witness'] = deepcopy(sample.get('source_witness'))
                    self._scores[slot] = dict(status='censored', score=full,
                        score_observed_ns=stamp, score_witness=witness,
                        first_play_level=selected['first_play_level'], playable_frames=selected['playable_frames'],
                        completion_observed_ns=None, completed_row=None)
                else:
                    require(previous_score is not None and full == previous_score['score'],
                            'Rejected exchange cannot create a score witness')
            self._last_packets[slot] = dict(sequence=sequence, accepted_ordinal=after,
                origin_game_uid=sample['origin_game_uid'], completed_exchange_ns=stamp,
                source_witness=deepcopy(sample.get('source_witness')))
            return True

    def _fresh(self, when):
        require(set(self._members) == set(self._scores) == set(self._last_packets) == set(SLOTS),
                'All 32 fixed first-game members and score witnesses are required')
        for slot in SLOTS:
            value, activity = self._scores[slot], self._last_packets[slot]
            require(value['first_play_level'] == 1 and value['playable_frames'] > 0,
                    'All first games need certified playable wave 1')
            require(0 <= when - activity['completed_exchange_ns'] <= MAX_AGE_NS, 'Stale slot activity')
            if value['status'] != 'completed':
                require(0 <= when - value['score_observed_ns'] <= MAX_AGE_NS, 'Stale pending score witness')

    def arm(self, readiness):
        with self._lock:
            require(self._anchor is None and self._sealed is None, 'Deadline already armed')
            now = integer(self._clock(), 'anchor clock')
            self._fresh(now)
            require(type(readiness) is dict and readiness['all_first_play_certified'] is True,
                    'All original first-play certificates required')
            require(readiness['policy_sha256'] == self._policy['policy_sha256'] and
                    readiness['measurement_generation'] == self._policy['measurement_generation'],
                    'Readiness frozen policy differs')
            boundary = readiness['boundary']
            generation = self._policy['measurement_generation']
            for key in ('generation', 'requested_generation', 'clients', 'expected', 'acknowledged'):
                integer(boundary[key], 'boundary ' + key, 1)
            require(boundary['ready'] is boundary['active'] is True and
                    boundary['generation'] == boundary['requested_generation'] == generation and
                    boundary['clients'] == boundary['expected'] == boundary['acknowledged'] == 32 and
                    boundary['actor_slots'] == list(SLOTS) and
                    boundary['pending_client_ids'] == boundary['replay_pending_client_ids'] == [],
                    'All 32 actual policy generation acknowledgements required')
            self._anchor, self._deadline, self._readiness = now, now + HORIZON_NS, deepcopy(readiness)
            self._anchor_scores = deepcopy(self._scores)
            self._anchor_packets = deepcopy(self._last_packets)
            return dict(anchor_monotonic_ns=self._anchor, deadline_monotonic_ns=self._deadline,
                        horizon_ns=HORIZON_NS, members=32)

    def seal(self, now_ns, *, barrier):
        with self._lock:
            require(self._deadline is not None and self._sealed is None, 'Deadline not armed or already sealed')
            now = integer(self._clock(), 'seal clock')
            integer(now_ns, 'barrier observation clock')
            require(self._deadline <= now_ns <= now, 'Cannot seal before the fixed deadline')
            require(type(barrier) is dict and barrier['deadline_monotonic_ns'] == self._deadline and
                    barrier['no_new_origin_entries'] is True and type(barrier['inflight']) is int and
                    barrier['inflight'] == 0, 'Origin entry/in-flight barrier is not closed')
            closed = integer(barrier['closed_monotonic_ns'], 'closed barrier clock')
            require(self._deadline <= closed <= now_ns and closed - self._deadline <= MAX_AGE_NS,
                    'Fixed in-flight service bound exceeded')
            self._fresh(self._deadline)
            rows = []
            for slot in SLOTS:
                value = deepcopy(self._scores[slot])
                value.update(slot=slot, member=deepcopy(self._members[slot]),
                    score_at_deadline=value['score'], whole_game_complete=value['status'] == 'completed',
                    score_at_anchor=self._anchor_scores[slot]['score'],
                    activity_at_anchor=deepcopy(self._anchor_packets[slot]),
                    score_witness_at_anchor=deepcopy(self._anchor_scores[slot]['score_witness']),
                    accepted_frame_exposure=(self._last_packets[slot]['accepted_ordinal'] -
                                             self._anchor_packets[slot]['accepted_ordinal']),
                    selected_first_game_accepted_frame_exposure=max(0,
                        value['score_witness']['accepted_ordinal'] -
                        self._anchor_packets[slot]['accepted_ordinal']),
                    score_observed_ns_at_anchor=self._anchor_scores[slot]['score_observed_ns'],
                    playable_frames_at_anchor=self._anchor_scores[slot]['playable_frames'],
                    whole_game_complete_at_anchor=self._anchor_scores[slot]['status'] == 'completed',
                    right_censored=value['status'] != 'completed',
                    score_snapshot_age_ns=self._deadline - value['score_observed_ns'],
                    activity_age_ns=self._deadline - self._last_packets[slot]['completed_exchange_ns'],
                    last_activity=deepcopy(self._last_packets[slot]))
                rows.append(value)
            scores = [row['score_at_deadline'] for row in rows]
            n_completed = sum(row['whole_game_complete'] for row in rows)
            ordered = sorted(scores)
            sd = statistics.stdev(scores)
            self._sealed = dict(schema='robotron-first-game-deadline-score32-v2',
                metric='first_game_score_observed_by_fixed_host_exchange_deadline',
                horizon_ns=HORIZON_NS, anchor_monotonic_ns=self._anchor,
                deadline_monotonic_ns=self._deadline, seal_observed_monotonic_ns=now,
                cutoff_lateness_ns=now - self._deadline, barrier=deepcopy(barrier),
                policy=deepcopy(self._policy), readiness=deepcopy(self._readiness),
                n_scored=32, n_completed=n_completed, n_censored=32 - n_completed,
                score_sum=sum(scores), mean_score=statistics.mean(scores),
                score_gain_since_anchor=sum(row['score_at_deadline'] - row['score_at_anchor'] for row in rows),
                accepted_frame_exposure=sum(row['accepted_frame_exposure'] for row in rows),
                selected_first_game_accepted_frame_exposure=sum(
                    row['selected_first_game_accepted_frame_exposure'] for row in rows),
                accepted_frame_exposure_scope='all actor accepted frames after coherent common anchor, including later games',
                selected_first_game_exposure_scope='accepted old-UID score witnesses after anchor; excludes next-game closing frame',
                median_score=statistics.median(scores), median_twice=ordered[15] + ordered[16],
                sd_score=sd, se_score=sd / math.sqrt(32), rows=rows,
                post_deadline_observations_not_credited=self._after_deadline_ignored,
                fixed_denominator_valid=True, full_game_quality_qualified=False,
                improvement_qualified=False, source_or_runtime_faults_may_not_be_censored=True)
            return deepcopy(self._sealed)
