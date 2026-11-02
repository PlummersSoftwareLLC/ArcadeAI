"""Pure proposed guard contracts on saved metadata and synthetic gap clocks.

The copied cap94 text is observed data. Constructed191 APIs and their clocks
are adversarial fixtures, never actual reset observations or study evidence.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

P = Path(__file__).resolve().parent
G = P.parents[1]
D = G / 'logs/managed-learning-20261015/run-26/LR125-survival32M-original01-preparation-20261023'


def load(name, path, sha=None):
    if sha:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapHealthContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = load('_cap_health_proposal', P / 'certified_cap_health_proposal_v1.py')
        cls.sup = load('_cap_actual_census_predicates', G / 'tools/quality_capacity_proposal/supervised_main_fleet_v2.py',
            '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0')
        cls.window = load('_cap_actual_old_window', P / 'window_observer.py', cls.p.WINDOW_SHA)
        cls.policy = json.loads((D / 'quality-static-current197-seed-original01/prospective-LR125-main-supervision-policy.json').read_bytes())
        cls.census = json.loads((D / 'quality-static-current197-seed-original01/current-original192-census.json').read_bytes())
        cls.api = json.loads((D / 'quality-static-current197-seed-original01/baseline-main-API.raw.json').read_bytes())
        fixture = D / 'certified-cap-health-component-preparation-original01/actual-cap94-log-fixture.json'
        assert hashlib.sha256(fixture.read_bytes()).hexdigest() == '6b18f9ca42f1c43d9bf89600781c4e545b6c25dcffb990e8ce3517fd771e6868'
        cls.cap_raw = json.loads(fixture.read_bytes())['observed_event']['text']

    def setUp(self):
        self.origins = {str(i): dict(inode=1000 + i, offset=0) for i in range(192)}
        self.guard = self.p.CapHealth(self.sup, self.policy, self.api,
                                      (P / 'window_observer.py').read_bytes(), self.origins)
        self.epochs = {str(r['client_slot']): self.api['ts'] - r['connected_seconds'] for r in self.api['client_rows']}
        self.state = self.observe(0)

    def inputs(self, t, missing=None):
        snapshot, api = copy.deepcopy(self.census), copy.deepcopy(self.api)
        for key in ('monotonic_s', 'unix_s', 'collection_started_monotonic_s', 'collection_started_unix_s'):
            snapshot[key] += t
        clock = dict(monotonic_s=snapshot['monotonic_s'] + .1, unix_s=snapshot['unix_s'] + .1)
        api['ts'] = clock['unix_s'] - .01
        for row in api['client_rows']:
            row['connected_seconds'] = api['ts'] - self.epochs[str(row['client_slot'])]
        if missing is not None:
            slots = {missing} if type(missing) is int else set(missing)
            api['client_rows'] = [r for r in api['client_rows'] if r['client_slot'] not in slots]
            api['client_count'] = len(api['client_rows'])
        return snapshot, api, clock

    def chunk(self, slot, t, state=None):
        state = self.state if state is None else state
        raw = self.cap_raw.replace('pid=2258412 ', f"pid={self.policy['baseline_actors'][str(slot)]['pid']} ")
        start = state['cursors'][str(slot)]['offset']
        return dict(slot=str(slot), raw=raw, lua_sha256=self.p.LUA_SHA,
            inode=self.origins[str(slot)]['inode'], offset_start=start, offset_end=start + len(raw.encode()),
            monotonic_s=self.census['monotonic_s'] + .1 + t,
            unix_s=self.census['unix_s'] + .1 + t)

    def observe(self, t, missing=None, chunks=(), state=None):
        args = self.inputs(t, missing)
        return self.guard.observe(*args, chunks=chunks, state=state)

    def episode(self, slot, bad, good):
        event = self.chunk(slot, bad - .1)
        self.state = self.observe(bad, slot, [event], self.state)
        self.epochs[str(slot)] = self.census['unix_s'] + bad
        self.state = self.observe(good, state=self.state)

    def test_valid_actual_physical_metadata_and_certified_synthetic_gap_keep_raw_API(self):
        snapshot, api, clock = self.inputs(5, 94)
        original = copy.deepcopy(api)
        with self.assertRaises(ValueError):
            self.window.healthy(api, self.api, self.api['managed_experiment'], clock['unix_s'])
        pending = self.guard.observe(snapshot, api, clock, [self.chunk(94, 4.9)], self.state)
        self.assertEqual(api, original)
        self.assertEqual(api['client_count'], 191)
        self.assertFalse(pending['full_capacity'])
        with self.assertRaises(ValueError):
            self.p.closed_summary(pending)
        self.epochs['94'] = self.census['unix_s'] + 5
        recovered = self.observe(10, state=pending)
        summary = self.p.closed_summary(recovered)
        self.assertEqual(summary['used_slots'], ['94'])
        self.assertEqual(summary['total_charged_s'], 10)

    def test_no_gap_exception_at_initial_observation(self):
        for count in (191, 190):
            snapshot, api, clock = self.inputs(0, set(range(192 - count)))
            with self.assertRaises(ValueError):
                self.guard.observe(snapshot, api, clock)

    def test_unknown_multiple_wrong_slot_and_missing_certificate_refuse(self):
        for missing, chunks in [(94, []), ({94, 95}, [self.chunk(94, 4.9)]),
                                 (95, [self.chunk(94, 4.9)])]:
            with self.assertRaises(ValueError):
                self.observe(5, missing, chunks, self.state)

    def test_actor_replacement_missing_process_and_configuration_changes_refuse(self):
        for mutation in ('missing', 'birth', 'affinity', 'owner'):
            snapshot, api, clock = self.inputs(5, 94)
            if mutation == 'missing': snapshot['actors'].pop('94')
            if mutation == 'birth': snapshot['actors']['94']['starttime_ticks'] += 1
            if mutation == 'affinity': snapshot['actors']['94']['affinity'] = []
            if mutation == 'owner': snapshot['owners']['trainer']['process']['starttime_ticks'] += 1
            with self.assertRaises(ValueError):
                self.guard.observe(snapshot, api, clock, [self.chunk(94, 4.9)], self.state)

    def test_log_identity_range_source_pid_and_event_replay_refuse(self):
        good = self.chunk(94, 4.9)
        for key, value in [('inode', 999), ('offset_start', 1), ('offset_end', good['offset_end'] + 1),
                           ('lua_sha256', '0' * 64), ('raw', good['raw'].replace('pid=2258412 ', 'pid=1 '))]:
            bad = dict(good, **{key: value})
            if key == 'raw': bad['offset_end'] = len(bad['raw'].encode())
            with self.assertRaises(ValueError):
                self.observe(5, 94, [bad], self.state)
        state = self.observe(5, chunks=[good], state=self.state)
        with self.assertRaises(ValueError):
            self.observe(6, chunks=[good], state=state)

    def test_expired_certificate_and_clock_regression_refuse(self):
        state = self.observe(5, chunks=[self.chunk(94, 4.9)], state=self.state)
        with self.assertRaises(ValueError): self.observe(16, 94, state=state)
        with self.assertRaises(ValueError): self.observe(4, state=state)
        with self.assertRaises(ValueError): self.observe(36, state=state)

    def test_all_original_nonconnection_health_predicates_remain_required(self):
        for key, value in [('lr', 1.25e-5), ('training_enabled', False), ('measurement_active', True),
                           ('managed_experiment', 'wrong'), ('pipeline_read_error', 'error')]:
            snapshot, api, clock = self.inputs(5, 94); api[key] = value
            with self.assertRaises(ValueError):
                self.guard.observe(snapshot, api, clock, [self.chunk(94, 4.9)], self.state)
        snapshot, api, clock = self.inputs(5, 94)
        api['bank_persistence']['write_failures'] = 1
        with self.assertRaises(ValueError):
            self.guard.observe(snapshot, api, clock, [self.chunk(94, 4.9)], self.state)

    def test_reconnection_must_have_a_fresh_epoch_for_the_missing_slot(self):
        state = self.observe(5, 94, [self.chunk(94, 4.9)], self.state)
        with self.assertRaises(ValueError): self.observe(10, state=state)

    def test_episode_limit_uses_preceding_good_sample_and_rejects_long_dip(self):
        self.episode(94, 20, 45)
        self.assertEqual(self.state['total_charged_s'], 45)
        self.setUp()
        pending = self.observe(20, 94, [self.chunk(94, 19.9)], self.state)
        self.epochs['94'] = self.census['unix_s'] + 20
        with self.assertRaises(ValueError): self.observe(46, state=pending)

    def test_total_budget_and_repeated_slot_are_strict(self):
        self.episode(94, 20, 45); self.episode(95, 65, 90); self.episode(96, 110, 120)
        self.assertEqual(self.state['total_charged_s'], 120)
        with self.assertRaises(ValueError):
            self.observe(121, 97, [self.chunk(97, 120.9)], self.state)
        self.setUp(); self.episode(94, 5, 10)
        with self.assertRaises(ValueError):
            self.observe(15, 94, [self.chunk(94, 14.9)], self.state)

    def test_case_merge_cannot_reset_count_duration_or_slot_budget_between_legs(self):
        self.episode(94, 5, 10)
        first = self.p.closed_summary(self.state)
        self.assertEqual(self.p.combine_closed_legs([first])['used_slots'], ['94'])
        with self.assertRaises(ValueError): self.p.combine_closed_legs([first, first])
        summaries = []
        for slot in range(90, 95):
            summary = copy.deepcopy(first)
            summary['episodes'][0]['slot'] = str(slot)
            summaries.append(summary)
        with self.assertRaises(ValueError): self.p.combine_closed_legs(summaries)
        summaries = summaries[:3]
        for summary in summaries:
            summary['episodes'][0].update(charged_s=45., charged_wall_s=45.)
        with self.assertRaises(ValueError): self.p.combine_closed_legs(summaries)


if __name__ == '__main__':
    unittest.main(verbosity=2)
