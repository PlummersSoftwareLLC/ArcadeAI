"""Original raw API/census joins and untouched legacy exposure predicates."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import supervised_main_fleet_v1 as fleet
import supervised_main_observations_v1 as joins
import test_supervised_main_fleet_v1 as fixtures


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
runtime = module(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py', 'legacy_runtime_for_joins')
wire = module(G/'tools/eval_capacity_proposal/raw_api_witness_v1.py', 'wire_for_joins')
window = module(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py', 'window_for_joins')
reader = module(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py', 'reader_for_joins')


def api(main, at, index, count=192):
    counters = dict(attempts_started=1000+index, outcomes_recorded=1000+index,
                    applied=1000+index, amp_skipped=0, unavailable=0)
    exposure = dict(optimizer=dict(schema='robotron-optimizer-exposure-v1', enabled=True, available=True,
        process_id=main['owner']['pid'], instance_monotonic_ns=10, epoch=1,
        total=dict(counters), since_epoch=dict(counters), unclassified_started_total=0),
        replay=dict(enabled=True, available=True, process_id=main['owner']['pid'],
            instance_monotonic_ns=11, epoch=1, accepted_learner_total=1000+index))
    pipeline = dict(schema='robotron-host-pipeline-v1', available=True, generation=0, learning_exposure=exposure)
    pipeline.update({kind: dict(errors=0) for kind in ('inference', 'actor_refresh', 'target_refresh', 'learner_priority')})
    value = dict(ts=at, client_count=count, training_enabled=True, measurement_active=False,
        managed_experiment=main['experiment'], lr=1.25e-5, pipeline_read_error='', bank_persistence_read_error='',
        pipeline_snapshot_age_s=0, host_pipeline=pipeline, bank_persistence=dict(write_failures=0),
        grad_norm=float('inf'))
    value.update({key: 1000+index for key in ('frame_count', 'learner_frame_count', 'optimized_samples', 'training_steps')})
    return value


class JoinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = fixtures.fixture()
        self.main = dict(owner=self.policy['trainer'], actors=[dict(slot=int(slot), pid=row['pid'],
            starttime_ticks=row['starttime_ticks'], mask=row['affinity'])
            for slot, row in self.policy['baseline_actors'].items()],
            held_hashes={str(index): 'a'*64 for index in range(195)}, experiment='synthetic-supervised-main')
        self.policy['held_hashes_sha256'] = joins.checksum(self.main['held_hashes'])
        self.main['supervision_policy'] = self.put('policy.json', self.policy)
        self.baseline = api(self.main, 1000100, 0)
        self.main['baseline_API_value'] = self.baseline

    def put(self, name, value):
        path = self.root/name
        path.parent.mkdir(exist_ok=True, parents=True)
        if path.exists():
            path.chmod(0o644)
        path.write_bytes(value if isinstance(value, bytes) else (json.dumps(value, allow_nan=False)+'\n').encode())
        path.chmod(0o444)
        return reader.pin(path)

    def read(self, pin, as_json=True):
        return reader.read_pin(pin, as_json=as_json)

    def observations(self, mode='recovered'):
        state, samples = None, []
        for index, at in enumerate([100, 110, 120, 130]):
            missing = ['168'] if mode != 'unchanged' and index == 1 else []
            changed = {'168': fixtures.replacement(self.policy, '168')} if mode != 'unchanged' and index == 2 else {}
            snapshot = fixtures.snapshot(self.policy, state, at, missing=missing, replacements=changed)
            count = 191 if mode != 'unchanged' and index in (1, 2) else 192
            state = fleet.validate_snapshot(self.policy, snapshot, count, state)
            compact = joins.pack(snapshot, fleet)
            current = api(self.main, snapshot['unix_s'], index, count)
            raw = self.put('wires/'+str(index)+'.raw', json.dumps(current, allow_nan=True).encode())
            sample = dict(monotonic_s=at, unix_s=snapshot['unix_s'], main_owner=self.main['owner'],
                supervised_main_fleet_verified=True,
                main_fleet_snapshot=self.put('censuses/'+str(index)+'.json', compact),
                main_fleet_state_sha256=joins.checksum(state), held_hashes_sha256=joins.checksum(self.main['held_hashes']),
                autosave=dict(mtime_ns=(snapshot['unix_s']-5)*10**9, bytes=275000000, age_s=5),
                **wire.witness_fields(current, raw))
            samples.append(sample)
        manifest = dict(schema=joins.SCHEMA, status='PASS', configuration_changed=False,
            main_owner=self.main['owner'], accounting_policy='single_inflight_optimizer_v1', rejected_observations=[],
            supervision_policy=self.main['supervision_policy'], supervision_summary=fleet.validate_closed(state),
            API_witness_format=wire.FORMAT)
        return manifest, samples, state

    def review(self, manifest, samples):
        original = copy.deepcopy(samples)
        rejoined = runtime.validate_raw_API_samples(manifest, samples, self.read)
        result = joins.review(self.main, self.policy, manifest, rejoined, 101, 129,
                              self.read, runtime, window, fleet)
        self.assertEqual(samples, original)
        return result

    def test_original191_API_wires_recover_and_legacy_exposure_checks_pass(self):
        manifest, samples, expected = self.observations()
        state, summary = self.review(manifest, samples)
        self.assertEqual(state, expected)
        self.assertEqual(summary['recoveries'], 1)
        self.assertEqual(summary['charged_recovery_s'], 30)
        self.assertEqual([row['API']['client_count'] for row in samples], [192, 191, 191, 192])
        self.assertTrue(all('original192_actors_verified' not in row for row in samples))

    def test_unchanged_fleet_uses_same_original_exposure_checks(self):
        manifest, samples, state = self.observations('unchanged')
        self.assertEqual(self.review(manifest, samples)[0], state)

    def test_compact_roundtrip_commits_every_observed_static_field(self):
        snapshot = fixtures.snapshot(self.policy)
        self.assertEqual(joins.unpack(self.policy, joins.pack(snapshot, fleet), fleet), snapshot)
        for key in fleet.STATIC:
            with self.subTest(field=key):
                changed = copy.deepcopy(snapshot)
                changed['actors']['168'][key] = {'unexpected': True}
                with self.assertRaises(ValueError):
                    joins.unpack(self.policy, joins.pack(changed, fleet), fleet)

    def test_changed_role_hash_missing_snapshot_or_reused_snapshot_cannot_pass(self):
        for problem in ['role', 'reuse', 'state', 'schema']:
            manifest, samples, _ = self.observations()
            if problem == 'role':
                pin = samples[1]['main_fleet_snapshot']
                value = self.read(pin)
                value['actors']['1']['role_sha256'] = 'f'*64
                samples[1]['main_fleet_snapshot'] = self.put('tampered-census.json', value)
            elif problem == 'reuse':
                samples[1]['main_fleet_snapshot'] = samples[0]['main_fleet_snapshot']
            elif problem == 'state':
                samples[1]['main_fleet_state_sha256'] = 'f'*64
            else:
                manifest['schema'] = 'robotron-main192-pilot-observations-v1'
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.review(manifest, samples)

    def test_source_owner_exposure_and_progress_checks_cannot_be_bypassed(self):
        mutations = {
            'lr': lambda value: value.update(lr=0),
            'training_disabled': lambda value: value.update(training_enabled=False),
            'pipeline': lambda value: value['host_pipeline']['inference'].update(errors=1),
            'epoch': lambda value: value['host_pipeline']['learning_exposure']['replay'].update(epoch=2),
            'unclassified': lambda value: value['host_pipeline']['learning_exposure']['optimizer']['total'].update(unavailable=1),
            'regression': lambda value: value.update(learner_frame_count=1),
            'extra_client': lambda value: value.update(client_count=193),
        }
        for problem, change in mutations.items():
            manifest, samples, _ = self.observations()
            current = wire.rejoin_witness(samples[2], lambda pin: self.read(pin, False))
            change(current)
            raw = self.put('changed-'+problem+'.raw', json.dumps(current, allow_nan=True).encode())
            samples[2].update(wire.witness_fields(current, raw))
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.review(manifest, samples)

    def test_RAW_projection_tamper_fails_before_capacity_normalisation(self):
        manifest, samples, _ = self.observations()
        samples[1]['API']['client_count'] = 192
        with self.assertRaises(ValueError):
            self.review(manifest, samples)

    def test_observation_census_time_join_and_closed_summary_are_checked(self):
        for problem in ['late', 'future', 'summary', 'legacy_claim', 'held_source', 'checkpoint']:
            manifest, samples, _ = self.observations()
            if problem == 'late':
                samples[1]['unix_s'] += 6
            elif problem == 'future':
                samples[1]['monotonic_s'] -= .1
            elif problem == 'summary':
                manifest['supervision_summary']['charged_recovery_s'] = 0
            elif problem == 'legacy_claim':
                samples[1]['original192_actors_verified'] = True
            elif problem == 'held_source':
                samples[1]['held_hashes_sha256'] = 'f'*64
            else:
                samples[1]['autosave']['age_s'] = 361
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                self.review(manifest, samples)

    def test_missing_terminal_recovery_cannot_be_declared_closed(self):
        manifest, samples, _ = self.observations()
        with self.assertRaises(ValueError):
            self.review(manifest, samples[:-1])

    def test_baseline_policy_binds_actor_source_and_trainer(self):
        joins.validate_binding(self.main, self.policy, fleet)
        for problem in ['actor', 'source', 'trainer']:
            changed = copy.deepcopy(self.main)
            if problem == 'actor':
                changed['actors'][0]['pid'] += 1
            elif problem == 'source':
                changed['held_hashes']['0'] = 'f'*64
            else:
                changed['owner']['pid'] += 1
            with self.subTest(problem=problem), self.assertRaises(ValueError):
                joins.validate_binding(changed, self.policy, fleet)


if __name__ == '__main__':
    unittest.main()
