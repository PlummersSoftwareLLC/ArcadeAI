"""Inactive prospective quota64 cohort view; no imports of the numerical runtime.

This changes selection, never the established GameJournal score/life writer.
It is not selected by a runtime, drain authority or scientific audit. Those
integrations and actual scoped guards remain required before a future study.
"""
import copy
import hashlib
import inspect
import json
import math
from pathlib import Path
import re
import statistics

SLOTS = tuple(range(4096, 4128))
GAMES_PER_SLOT = 2
EXPECTED_GAMES = 64
MINIMUM_GAMES = 50
OUTER_START_HORIZON_S = 21540
JOURNAL_SHA = '96864c78df67f46bc58b1c4af4ce1bceb3791a8842fdcf02871385a1013d1e0f'
MEASUREMENT_SHA = '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6'


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), 'Finite timestamp required')
    return value


def bind_source(cls, name, expected):
    try:
        source = inspect.getsourcefile(cls)
    except TypeError as exc:
        raise ValueError('Exact original ' + name + ' source required') from exc
    require(cls.__name__ == name and source is not None
            and hashlib.sha256(Path(source).read_bytes()).hexdigest() == expected,
            'Exact original ' + name + ' source required')


def policy_copy(value):
    require(type(value) is dict, 'Original loaded policy required')
    result = copy.deepcopy(value)
    require(result['measurement_active'] is True
            and result['training_enabled'] is result['replay_enabled'] is False
            and type(result['epsilon']) in (int, float)
            and type(result['expert_ratio']) in (int, float)
            and result['epsilon'] == result['expert_ratio'] == 0,
            'Frozen greedy policy required')
    require(type(result['experiment']) is str and bool(result['experiment'].strip()),
            'Original experiment required')
    for key in ('measurement_generation', 'learner_frame_count', 'training_steps', 'optimized_samples'):
        require(type(result[key]) is int and result[key] >= (1 if key == 'measurement_generation' else 0),
                'Invalid loaded policy clock/generation')
    for key in ('checkpoint_sha256', 'policy_load_id'):
        require(type(result[key]) is str and re.fullmatch('[0-9a-f]{64}', result[key])
                and result[key] != '0' * 64, 'Invalid loaded policy identity')
    canonical(result)
    return result


class FixedSlotCohortView:
    """Delegate all writing to the pinned journal and select first two starts.

    The existing start/close arguments denote the immutable outer start horizon.
    Admission closes when all quotas are filled, independently of game outcomes.
    It never closes successfully by keeping only faster completed games.
    """
    __slots__ = ('journal', '_policy', '_bounds', '_known_order', '_starts', '_results',
                 '_closed_ids', '_failure_reason', '_closed_by')

    def __init__(self, journal, *, policy):
        bind_source(type(journal), 'GameJournal', JOURNAL_SHA)
        require(journal.completion_policy == 'confirmed_reset_reserves_v1',
                'Original confirmed-reset score writer required')
        self.journal = journal
        self._policy = policy_copy(policy)
        self._bounds = None
        self._known_order = ()
        self._starts = {}
        self._results = {}
        self._closed_ids = None
        self._failure_reason = None
        self._closed_by = None

    def __getattr__(self, name):
        return getattr(self.journal, name)

    def policy(self):
        return copy.deepcopy(self._policy)

    def _context_ok(self, context):
        p = self._policy
        return (type(context) is dict
                and context.get('experiment') == p['experiment']
                and context.get('measurement_active') is True
                and type(context.get('measurement_generation')) is int
                and context['measurement_generation'] == p['measurement_generation']
                and type(context.get('difficulty')) is int and context['difficulty'] == 5
                and type(context.get('epsilon')) in (int, float)
                and type(context.get('expert_ratio')) in (int, float)
                and context.get('epsilon') == context.get('expert_ratio') == 0
                and all(type(context.get(key)) is int and context[key] == p[loaded]
                        for key, loaded in (('learner_frames', 'learner_frame_count'),
                                            ('training_steps', 'training_steps'),
                                            ('optimized_samples', 'optimized_samples'))))

    def _descriptor(self, game):
        return canonical({key: game[key] for key in (
            'journal_game_id', 'client_id', 'client_slot', 'game_uid', 'known_start',
            'eval_only', 'measurement_active', 'measurement_generation',
            'start_unix_s', 'start_reason', 'start')})

    def cohort_status(self, experiment, start_ts, close_ts):
        require(experiment == self._policy['experiment'], 'Original experiment changed')
        number(start_ts); number(close_ts)
        require(close_ts - start_ts == OUTER_START_HORIZON_S,
                'Exact prospective outer start horizon required')
        bounds = (experiment, start_ts, close_ts)
        with self.journal.lock:
            if self._bounds is None:
                self._bounds = bounds
            require(self._bounds == bounds, 'Original outer start horizon changed')
            known = []
            last_sequence = 0
            for key, game in self.journal.measurement_games.items():
                if not game['known_start'] or game['start'].get('experiment') != experiment:
                    continue
                require(key == game['journal_game_id'], 'Original journal key changed')
                prefix, separator, ordinal = key.rpartition(':')
                require(separator and prefix == self.journal.run_id
                        and re.fullmatch('[1-9][0-9]*', ordinal),
                        'Original journal ID differs')
                sequence = int(ordinal)
                require(last_sequence < sequence <= self.journal.sequence,
                        'Original known-start occurrence order changed')
                last_sequence = sequence
                require(type(game['client_slot']) is int and game['client_slot'] in SLOTS,
                        'Foreign original slot')
                number(game['start_unix_s'])
                descriptor = self._descriptor(game)
                if key in self._starts:
                    require(self._starts[key] == descriptor, 'Original known-start descriptor changed')
                known.append(game)
            order = tuple(game['journal_game_id'] for game in known)
            require(order[:len(self._known_order)] == self._known_order,
                    'Original known starts disappeared, reordered or were inserted late')
            self._known_order = order
            for game in known:
                self._starts.setdefault(game['journal_game_id'], self._descriptor(game))
            counts = {slot: 0 for slot in SLOTS}
            selected, outside = [], []
            for game in known:
                slot = game['client_slot']
                if start_ts <= game['start_unix_s'] <= close_ts and counts[slot] < GAMES_PER_SLOT:
                    selected.append(game)
                    counts[slot] += 1
                else:
                    outside.append(game['journal_game_id'])
            selected_ids = tuple(game['journal_game_id'] for game in selected)
            if self._closed_ids is not None:
                require(selected_ids == self._closed_ids, 'Closed admission membership changed')
            rows, pending, abandoned, reasons = [], [], [], {}
            for game in selected:
                key = game['journal_game_id']
                row = game['result']
                if key in self._results:
                    require(row == self._results[key], 'Original completed result changed or disappeared')
                if (game['mixed_experiment'] or game['mixed_measurement']
                        or game['measurement_active'] is not True
                        or type(game['measurement_generation']) is not int
                        or game['measurement_generation'] != self._policy['measurement_generation']
                        or not self._context_ok(game['start'])):
                    abandoned.append(key); reasons[key] = 'selected_policy_or_generation_changed'
                elif game['first_play_level'] not in (None, 1):
                    abandoned.append(key); reasons[key] = 'measurement_start_not_wave_1'
                elif row is None:
                    require(key not in self._results, 'Original completed result disappeared')
                    pending.append(key)
                elif row['eligible'] is not True:
                    abandoned.append(key)
                    reasons[key] = row['excluded_reason'] or row['boundary_reason']
                else:
                    require(game['finished'] is True and row['complete'] is True
                            and row['known_start'] is row['measurement_active'] is row['eval_only'] is True
                            and row['first_play_level'] == 1 and row['experiment'] == experiment
                            and type(row['measurement_generation']) is int
                            and row['measurement_generation'] == self._policy['measurement_generation']
                            and all(row[k] == game[k] for k in
                                    ('journal_game_id', 'client_id', 'client_slot', 'game_uid', 'start_unix_s'))
                            and type(row['score']) is int and row['score'] >= 0,
                            'Original eligible result identity differs')
                    if key in self._results:
                        require(self._results[key] == row, 'Original completed result changed')
                    else:
                        self._results[key] = copy.deepcopy(row)
                    rows.append(copy.deepcopy(row))
            now = number(self.journal.clock())
            quota_filled = len(selected) == EXPECTED_GAMES and all(
                value == GAMES_PER_SLOT for value in counts.values())
            horizon_closed = now >= close_ts
            if self._closed_ids is None and (quota_filled or horizon_closed):
                self._closed_ids = selected_ids
                self._closed_by = 'slot_quota' if quota_filled else 'outer_horizon'
                if not quota_filled:
                    self._failure_reason = 'slot_quota_unfilled_at_start_horizon'
            failure = self._failure_reason
            closed = self._closed_ids is not None
            started_ids = [game['journal_game_id'] for game in selected]
        rows.sort(key=lambda row: (row['start_unix_s'], row['journal_game_id']))
        scores = [row['score'] for row in rows]
        n = len(scores)
        sd = statistics.stdev(scores) if n > 1 else 0.0
        return dict(
            schema='robotron-fixed-slot64-cohort-status-v1',
            admission_mode='first_two_known_starts_per_declared_slot',
            timestamp_close_role='outer_start_horizon', experiment=experiment,
            start_ts=start_ts, close_ts=close_ts, closed=closed,
            closed_by=self._closed_by,
            expected_games=EXPECTED_GAMES, games_per_slot=GAMES_PER_SLOT,
            minimum_complete_games=MINIMUM_GAMES, all_slot_quotas_admitted=quota_filled,
            slot_admitted_counts={str(k): v for k, v in counts.items()},
            complete=quota_filled and failure is None and not pending and not abandoned and n == EXPECTED_GAMES,
            valid=not abandoned and failure is None, failure_reason=failure,
            rows=rows, count=n, mean=statistics.mean(scores) if n else 0.0,
            median=statistics.median(scores) if n else 0.0, sd=sd,
            se=sd / math.sqrt(n) if n else 0.0,
            started=len(started_ids), pending=len(pending), abandoned=len(abandoned),
            started_ids=started_ids, pending_ids=pending, abandoned_ids=abandoned,
            abandonment_reasons=reasons,
            started_actor_slots=sorted(slot for slot, count in counts.items() if count),
            retained_outside_cohort_ids=outside,
            quality_qualified=False, full_game_score_verified=False,
            caller_startup_ROM_wire_runtime_and_final_quality_audits_required=True)


def measurement_type(base_class):
    """Retain the original freeze/replay/timeout checks; expose quota closure."""
    bind_source(base_class, 'ManagedMeasurement', MEASUREMENT_SHA)

    class FixedSlotManagedMeasurement(base_class):
        def tick(self):
            if self._prior is not None:
                require(type(self.journal) is FixedSlotCohortView,
                        'Actual fixed-slot journal view must be installed before ticking')
            super().tick()
            if self._prior is not None and not self._terminal:
                if self._cohort.get('failure_reason'):
                    self._finish(False, self._cohort['failure_reason'])
                elif self._cohort.get('closed'):
                    self.phase = 'draining'
            return self.status()

    return FixedSlotManagedMeasurement


def install_view(server, controller, policy):
    """Install only after measurement entry, before any actor or journal game."""
    require(type(controller).__name__ == 'FixedSlotManagedMeasurement'
            and inspect.getsourcefile(type(controller)) == str(Path(__file__))
            and len(type(controller).__bases__) == 1
            and controller.journal is server.game_journal
            and controller._prior is not None and not controller._terminal
            and controller.phase == 'warming' and controller.start_ts is None,
            'Original warming controller/journal binding required')
    bind_source(type(controller).__bases__[0], 'ManagedMeasurement', MEASUREMENT_SHA)
    journal = server.game_journal
    bind_source(type(journal), 'GameJournal', JOURNAL_SHA)
    with journal.lock:
        require(not journal.measurement_games and not journal.active,
                'Never replace a view after original games exist')
    view = FixedSlotCohortView(journal, policy=policy)
    require(view.policy()['experiment'] == controller.label
            and view.policy()['measurement_generation'] == controller.generation,
            'Original controller/policy binding differs')
    controller.journal = view
    server.game_journal = view
    return view
