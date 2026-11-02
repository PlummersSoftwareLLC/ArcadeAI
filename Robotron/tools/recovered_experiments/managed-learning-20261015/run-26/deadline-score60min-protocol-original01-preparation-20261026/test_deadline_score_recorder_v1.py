"""Focused CPU fixtures for the new deadline estimand; no runtime/model work."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from deadline_score_recorder_v1 import DeadlineScoreRecorder, HORIZON_NS, MAX_AGE_NS, SLOTS


class Clock:
    def __init__(self):
        self.now = 10_000_000_000

    def __call__(self):
        return self.now


def member(slot):
    return dict(slot=slot, session=f'{slot:032x}', connection=f'{slot + 10000:032x}',
        game_uid=slot, journal_game_id=f'original:{slot}', start_certificate_id=f'{slot:064x}',
        startup_nonce=f'{slot + 10000:064x}', policy_sha256='c' * 64,
        measurement_generation=1, experiment='new-deadline-original',
        policy_clocks=dict(learner_frame_count=4_000_000_000,
                           training_steps=15_000_000, optimized_samples=60_000_000_000))


def sample(slot, stamp, *, sequence=1201, before=9, score=100, offset=0, raw=None,
           accepted=True, first_play=1, origin_uid=None, selected=None):
    if raw is None:
        raw = score - offset
    if selected is None:
        selected = dict(journal_game_id=f'original:{slot}', game_uid=slot, known_start=True,
            first_play_level=first_play, measurement_active=True, measurement_generation=1,
            mixed_experiment=False, mixed_measurement=False, experiment='new-deadline-original',
            score=score, playable_frames=0 if first_play is None else sequence,
            finished=False, result=None)
    return dict(sequence=sequence, completed_exchange_ns=stamp, before_ordinal=before,
        accepted_ordinal=before + int(accepted), origin_game_uid=slot if origin_uid is None else origin_uid,
        full_score=score, effective_raw_score=score - offset, score_offset=offset,
        raw_wire_score=raw, coerced_score_dips=0, policy_sha256='c' * 64,
        measurement_generation=1, selected=selected,
        source_witness=dict(payload_sha256='d' * 64, raw_header_hex='0000', fixture_only=True))


def terminal_sample(slot, stamp, score, *, sequence=1203, before=11, zero_same_uid=False):
    next_uid = slot if zero_same_uid else slot + 50000
    terminal = dict(schema='robotron-confirmed-game-reset-v1',
        reason='zero_score_restart' if zero_same_uid else 'score_reset', previous_score=score,
        next_score=0, previous_game_uid=slot, next_game_uid=next_uid,
        next_journal_game_id=f'next:{slot}', classifier_new_game=not zero_same_uid,
        previous_raw_reserves=0, next_raw_reserves=2, restart_pulse=True, next_wave=1)
    result = dict(journal_game_id=f'original:{slot}', game_uid=slot, client_slot=slot,
        complete=True, eligible=True, known_start=True, measurement_active=True,
        measurement_generation=1, experiment='new-deadline-original', first_play_level=1,
        score=score, terminal_confirmation=terminal)
    selected = dict(journal_game_id=f'original:{slot}', game_uid=slot, known_start=True,
        first_play_level=1, measurement_active=True, measurement_generation=1,
        mixed_experiment=False, mixed_measurement=False, experiment='new-deadline-original',
        score=score, playable_frames=2000, finished=True, result=result)
    return sample(slot, stamp, sequence=sequence, before=before, score=0,
                  origin_uid=next_uid, selected=selected)


def readiness():
    return dict(all_first_play_certified=True, policy_sha256='c' * 64, measurement_generation=1,
        boundary=dict(ready=True, active=True, generation=1, requested_generation=1,
                      clients=32, expected=32, acknowledged=32, actor_slots=list(SLOTS),
                      pending_client_ids=[], replay_pending_client_ids=[]))


class DeadlineTests(unittest.TestCase):
    def ready(self, initial_score=100, missing=None):
        clock = Clock()
        recorder = DeadlineScoreRecorder(clock_ns=clock)
        for slot in SLOTS:
            if slot == missing:
                continue
            recorder.bind(slot, member(slot))
            recorder.observe(slot, sample(slot, clock.now, score=initial_score))
        return recorder, clock

    def armed(self, initial_score=100):
        recorder, clock = self.ready(initial_score)
        armed = recorder.arm(readiness())
        self.assertEqual(armed['deadline_monotonic_ns'] - armed['anchor_monotonic_ns'], HORIZON_NS)
        return recorder, clock, armed['deadline_monotonic_ns']

    def recent(self, recorder, clock, deadline, score=200, skip=None):
        clock.now = deadline - 10
        for slot in SLOTS:
            if slot != skip:
                recorder.observe(slot, sample(slot, clock.now, sequence=1202, before=10, score=score))

    def seal(self, recorder, clock, deadline, **changes):
        clock.now = max(clock.now, deadline + 10)
        barrier = dict(deadline_monotonic_ns=deadline, no_new_origin_entries=True,
                       inflight=0, closed_monotonic_ns=deadline + 5)
        barrier.update(changes)
        return recorder.seal(clock.now, barrier=barrier)

    def test_all32_censored_including_zero_is_a_valid_fixed_denominator(self):
        recorder, clock, deadline = self.armed(0)
        self.recent(recorder, clock, deadline, score=0)
        result = self.seal(recorder, clock, deadline)
        self.assertEqual((result['n_scored'], result['n_completed'], result['n_censored']), (32, 0, 32))
        self.assertEqual((result['score_sum'], result['mean_score'], result['median_score']), (0, 0, 0))
        self.assertFalse(result['full_game_quality_qualified'])
        self.assertTrue(all(row['right_censored'] and not row['whole_game_complete'] for row in result['rows']))

    def test_accepted_100M_carry_and_torn_read_keep_fullscore_and_witness(self):
        recorder, clock, deadline = self.armed(99_999_975)
        self.recent(recorder, clock, deadline, score=99_999_975)
        # Use a real declared slot, with a genuine carry to 100,000,025.
        slot = 4096
        value = sample(slot, deadline - 5, sequence=1203, before=11,
                       score=100_000_025, offset=100_000_000, raw=25)
        clock.now = deadline - 5
        recorder.observe(slot, value)
        torn = sample(slot, deadline - 1, sequence=1204, before=12,
                      score=100_000_025, offset=100_000_000, raw=0)
        torn['coerced_score_dips'] = 1
        clock.now = deadline - 1
        recorder.observe(slot, torn)
        row = self.seal(recorder, clock, deadline)['rows'][0]
        self.assertEqual(row['score_at_deadline'], 100_000_025)
        self.assertEqual(row['score_witness']['raw_wire_score'], 0)
        self.assertEqual(row['score_witness']['effective_raw_score'], 25)
        self.assertEqual(row['score_witness']['source_witness'], torn['source_witness'])

    def test_completed_OLDUID_joins_old_score_not_new_UID_offset(self):
        recorder, clock, deadline = self.armed()
        self.recent(recorder, clock, deadline, score=200)
        slot = 4096
        clock.now = deadline - 5
        done = terminal_sample(slot, clock.now, 200)
        recorder.observe(slot, done)
        later = deepcopy(done)
        later.update(sequence=1204, before_ordinal=12, accepted_ordinal=13,
                     completed_exchange_ns=deadline - 1, full_score=999_999,
                     effective_raw_score=999_999, raw_wire_score=999_999)
        clock.now = deadline - 1
        recorder.observe(slot, later)
        result = self.seal(recorder, clock, deadline)
        row = result['rows'][0]
        self.assertEqual((result['n_completed'], result['n_censored']), (1, 31))
        self.assertEqual(row['score_at_deadline'], 200)
        self.assertEqual(row['last_activity']['origin_game_uid'], slot + 50000)
        self.assertTrue(row['whole_game_complete'])

    def test_zero_score_confirmed_restart_can_keep_origin_UID(self):
        recorder, clock, deadline = self.armed(0)
        self.recent(recorder, clock, deadline, score=0)
        clock.now = deadline - 1
        recorder.observe(4096, terminal_sample(4096, clock.now, 0, zero_same_uid=True))
        result = self.seal(recorder, clock, deadline)
        self.assertEqual((result['n_completed'], result['rows'][0]['score_at_deadline']), (1, 0))

    def test_first_game_completed_before_common_anchor_is_not_replaced(self):
        recorder, clock = self.ready()
        clock.now += 1
        done = terminal_sample(4096, clock.now, 100, sequence=1202, before=10)
        recorder.observe(4096, done)
        deadline = recorder.arm(readiness())['deadline_monotonic_ns']
        self.recent(recorder, clock, deadline, skip=4096)
        later = deepcopy(done)
        later.update(sequence=1203, before_ordinal=11, accepted_ordinal=12,
                     completed_exchange_ns=clock.now, full_score=1000,
                     effective_raw_score=1000, raw_wire_score=1000)
        recorder.observe(4096, later)
        row = self.seal(recorder, clock, deadline)['rows'][0]
        self.assertEqual((row['score_at_anchor'], row['score_at_deadline']), (100, 100))
        self.assertTrue(row['whole_game_complete_at_anchor'])
        self.assertEqual(row['score_observed_ns_at_anchor'], 10_000_000_000)
        self.assertEqual(row['playable_frames_at_anchor'], 1201)

    def test_closing_exchange_AFTER_deadline_does_not_complete_or_add_points(self):
        recorder, clock, deadline = self.armed()
        self.recent(recorder, clock, deadline, score=200)
        clock.now = deadline + 1
        self.assertFalse(recorder.observe(4096, terminal_sample(4096, clock.now, 200)))
        result = self.seal(recorder, clock, deadline)
        self.assertEqual(result['n_completed'], 0)
        self.assertEqual(result['rows'][0]['score_at_deadline'], 200)
        self.assertEqual(result['post_deadline_observations_not_credited'], 1)

    def test_predeadline_completion_can_commit_late_before_closed_barrier(self):
        recorder, clock, deadline = self.armed()
        self.recent(recorder, clock, deadline, score=200)
        clock.now = deadline + 1
        self.assertTrue(recorder.observe(4096, terminal_sample(4096, deadline, 200)))
        result = self.seal(recorder, clock, deadline)
        self.assertEqual(result['n_completed'], 1)
        with self.assertRaises(ValueError):
            recorder.observe(4096, terminal_sample(4096, deadline, 200))

    def test_first_binding_and_policy_cannot_change(self):
        recorder, clock = self.ready()
        changed = member(4096); changed['game_uid'] += 90000
        with self.assertRaises(ValueError):
            recorder.bind(4096, changed)
        value = sample(4096, clock.now, sequence=1202, before=10)
        value['policy_sha256'] = 'e' * 64
        with self.assertRaises(ValueError):
            recorder.observe(4096, value)

    def test_missing_member_uncertified_start_and_unarmed_generation_fail(self):
        recorder, clock = self.ready(missing=4127)
        with self.assertRaises(ValueError):
            recorder.arm(readiness())
        for field, value in [('active', False), ('acknowledged', 31), ('requested_generation', 2)]:
            recorder, clock = self.ready(); ready = readiness(); ready['boundary'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                recorder.arm(ready)
        recorder, clock = self.ready(); bad = sample(4096, clock.now, sequence=1202, before=10)
        bad['selected']['first_play_level'] = 2
        with self.assertRaises(ValueError):
            recorder.observe(4096, bad)

    def test_stale_pending_score_or_completed_slot_activity_fails(self):
        recorder, clock, deadline = self.armed()
        self.recent(recorder, clock, deadline, skip=4127)
        with self.assertRaises(ValueError):
            self.seal(recorder, clock, deadline)
        recorder, clock, deadline = self.armed()
        self.recent(recorder, clock, deadline, skip=4127)
        recorder.observe(4127, sample(4127, clock.now, sequence=1202, before=10,
                                     score=100, accepted=False))
        with self.assertRaisesRegex(ValueError, 'Stale pending score'):
            self.seal(recorder, clock, deadline)
        # A completed score may be old, but its still-active slot must be fresh.
        recorder, clock, deadline = self.armed()
        clock.now += 1
        recorder.observe(4096, terminal_sample(4096, clock.now, 100, sequence=1202, before=10))
        self.recent(recorder, clock, deadline, skip=4096)
        with self.assertRaises(ValueError):
            self.seal(recorder, clock, deadline)
        recorder, clock, deadline = self.armed()
        clock.now += 1
        done = terminal_sample(4096, clock.now, 100, sequence=1202, before=10)
        recorder.observe(4096, done)
        self.recent(recorder, clock, deadline, skip=4096)
        later = deepcopy(done)
        later.update(sequence=1203, before_ordinal=11, accepted_ordinal=12,
                     completed_exchange_ns=clock.now, full_score=1234,
                     effective_raw_score=1234, raw_wire_score=1234)
        recorder.observe(4096, later)
        result = self.seal(recorder, clock, deadline)
        self.assertEqual(result['n_completed'], 1)
        self.assertGreater(result['rows'][0]['score_snapshot_age_ns'], MAX_AGE_NS)

    def test_cannot_seal_inflight_early_or_after_service_bound(self):
        recorder, clock, deadline = self.armed()
        self.recent(recorder, clock, deadline)
        with self.assertRaises(ValueError):
            recorder.seal(clock.now, barrier=dict(deadline_monotonic_ns=deadline,
                no_new_origin_entries=True, inflight=0, closed_monotonic_ns=clock.now))
        for changes in ({'inflight': 1}, {'no_new_origin_entries': False},
                        {'deadline_monotonic_ns': deadline + 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.seal(recorder, clock, deadline, **changes)
        clock.now = deadline + MAX_AGE_NS + 1
        with self.assertRaises(ValueError):
            recorder.seal(clock.now, barrier=dict(deadline_monotonic_ns=deadline,
                no_new_origin_entries=True, inflight=0, closed_monotonic_ns=clock.now))

    def test_bad_terminal_disconnection_and_lost_accepted_frame_never_become_censoring(self):
        recorder, clock, deadline = self.armed()
        self.recent(recorder, clock, deadline)
        clock.now = deadline - 1
        for kind in ('score', 'identity', 'disconnect'):
            value = terminal_sample(4096, clock.now, 200)
            if kind == 'score':
                value['selected']['result']['score'] = 201
            elif kind == 'identity':
                value['selected']['result']['terminal_confirmation']['previous_game_uid'] = 999
            else:
                value['selected']['result']['complete'] = False
                value['selected']['result']['eligible'] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                recorder.observe(4096, value)
        lost = sample(4096, clock.now, sequence=1204, before=12, score=400)
        with self.assertRaises(ValueError):
            recorder.observe(4096, lost)

    def test_REAL_frozen_journal_reset_and_zero_restart_results_join_old_score(self):
        robotron = next(p for p in Path(__file__).resolve().parents if p.name == 'Robotron')
        path = robotron / 'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/game_journal.py'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         '96864c78df67f46bc58b1c4af4ce1bceb3791a8842fdcf02871385a1013d1e0f')
        spec = importlib.util.spec_from_file_location('_actual_deadline_journal', path)
        source = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(source)
        for zero in (False, True):
            with self.subTest(zero_score_restart=zero), tempfile.TemporaryDirectory() as directory:
                clock = Clock()
                journal = source.GameJournal(directory, clock=lambda: clock.now / 1e9,
                    completion_policy='confirmed_reset_reserves_v1')
                recorder = DeadlineScoreRecorder(clock_ns=clock)
                context = lambda: dict(experiment='new-deadline-original',
                    measurement_active=True, measurement_generation=1)
                cs = dict(game_uid=4096, client_slot=4096, eval_only=True)
                def frame(score, alive, reserves, start=False):
                    return SimpleNamespace(game_score=score, level_number=1, player_alive=alive,
                        lives=reserves, num_lasers=reserves, start_pressed=start, done=not alive)
                journal.observe(1, frame(0 if zero else 100, True, 2), cs,
                                new_game=True, context=context)
                game = journal.active[1]
                value = member(4096); value['journal_game_id'] = game['journal_game_id']
                recorder.bind(4096, value)
                def selected():
                    keys = ('journal_game_id', 'game_uid', 'known_start', 'first_play_level',
                        'measurement_active', 'measurement_generation', 'mixed_experiment',
                        'mixed_measurement', 'score', 'playable_frames', 'finished', 'result')
                    result = {key: deepcopy(game[key]) for key in keys}
                    result['experiment'] = game['start']['experiment']
                    return result
                recorder.observe(4096, sample(4096, clock.now, score=game['score'], selected=selected()))
                final_score = 0 if zero else 100_000_200
                journal.observe(1, frame(final_score, False, 0), cs, context=context)
                recorder.observe(4096, sample(4096, clock.now, sequence=1202, before=10,
                    score=final_score, offset=0 if zero else 100_000_000, selected=selected()))
                for slot in SLOTS[1:]:
                    recorder.bind(slot, member(slot))
                    recorder.observe(slot, sample(slot, clock.now))
                deadline = recorder.arm(readiness())['deadline_monotonic_ns']
                self.recent(recorder, clock, deadline, skip=4096)
                clock.now = deadline - 1
                if not zero:
                    cs['game_uid'] += 50000
                journal.observe(1, frame(0, True, 2, True), cs,
                                new_game=not zero, context=context)
                recorder.observe(4096, sample(4096, clock.now, sequence=1203, before=11,
                    score=0, origin_uid=cs['game_uid'], selected=selected()))
                result = self.seal(recorder, clock, deadline)
                row = result['rows'][0]
                self.assertEqual((result['n_completed'], row['score_at_deadline']), (1, final_score))
                self.assertEqual(row['completed_row'], journal.completed[0])
                self.assertEqual(row['completed_row']['terminal_confirmation']['reason'],
                                 'zero_score_restart' if zero else 'score_reset')


if __name__ == '__main__':
    unittest.main(verbosity=2)
