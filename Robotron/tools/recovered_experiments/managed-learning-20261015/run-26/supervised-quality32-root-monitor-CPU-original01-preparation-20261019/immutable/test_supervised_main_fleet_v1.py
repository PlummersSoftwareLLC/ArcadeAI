"""Deterministic supervision replay failures; no models, GPU or emulator launches."""
import copy
import importlib.util
import math
import os
from pathlib import Path
import subprocess
import sys
import unittest

SOURCE = Path(__file__).with_name('supervised_main_fleet_v1.py')
SPEC = importlib.util.spec_from_file_location('supervision_under_test', SOURCE)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def fixture():
    def owner(pid, role):
        return dict(pid=pid, starttime_ticks=pid * 100, unit='robotron-fixture-' + role + '.service',
                    invocation_id=str(pid).zfill(32), cgroup='/fixture/' + role)
    trainer, fleet = owner(90, 'trainer'), owner(91, 'fleet')
    executable = dict(path='/usr/games/mame', identity=dict(device=1, inode=2, bytes=300000000,
        mtime_ns=1792000000123456789, ctime_ns=1792000000123456789, mode='0o755', uid=0))
    actors = {}
    for number in range(192):
        slot = str(number)
        actors[slot] = dict(pid=10000 + number, starttime_ticks=100000 + number, parent_pid=91,
            cgroup=fleet['cgroup'], command=['/usr/games/mame', 'robotron', '-autoboot_script', '/fixture/main.lua'],
            environment=dict(ROBOTRON_CLIENT_SLOT=slot, ROBOTRON_SOCKET_ADDRESS='dell:9998',
                             ROBOTRON_EVAL_MODE='0', ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES='0'),
            affinity=list(range(72)), uids=[os.getuid()] * 4, executable=copy.deepcopy(executable))
    def observation(claim):
        process = dict(actors['0'], **m.birth(claim), cgroup=claim['cgroup'], parent_pid=1)
        fields = dict(Id=claim['unit'], MainPID=str(claim['pid']), InvocationID=claim['invocation_id'],
            NRestarts='0', ActiveState='active', SubState='running', ControlGroup=claim['cgroup'])
        return dict(argv=['systemctl', '--user', 'show', claim['unit']], exit=0, stderr='',
                    stdout='\n'.join(key + '=' + value for key, value in fields.items()) + '\n', process=process)
    policy = dict(schema='robotron-main-supervision-policy-v1', limits=copy.deepcopy(m.LIMITS),
                  trainer=trainer, fleet=fleet, baseline_actors=actors,
                  baseline_owners=dict(trainer=observation(trainer), fleet=observation(fleet)),
                  held_hashes_sha256='0' * 64)
    return policy


def snapshot(policy, state=None, at=100, missing=(), replacements=None):
    registry = policy['baseline_actors'] if state is None else state['registry']
    actors = copy.deepcopy(registry)
    probes = {slot: row['starttime_ticks'] for slot, row in registry.items()}
    if state and state['pending'] and state['pending']['replacement'] is None:
        slot = state['pending']['slot']
        actors.pop(slot)
        probes[slot] = None
    for slot in missing:
        actors.pop(slot, None)
        probes[slot] = None
    for slot, row in (replacements or {}).items():
        actors[slot] = row
        probes[slot] = row['starttime_ticks'] if row['pid'] == registry[slot]['pid'] else None
    return dict(schema='robotron-main-supervision-snapshot-v1', owners=copy.deepcopy(policy['baseline_owners']),
                actors=actors, previous_birth_probes=probes, monotonic_s=at, unix_s=at + 1000000,
                collection_started_monotonic_s=at - .01, collection_started_unix_s=at + 1000000 - .01)


def replacement(policy, slot, bump=1000):
    original = policy['baseline_actors'][slot]
    return dict(copy.deepcopy(original), pid=original['pid'] + bump,
                starttime_ticks=original['starttime_ticks'] + bump)


class Replay(unittest.TestCase):
    def setUp(self):
        self.policy = fixture()
        self.initial = snapshot(self.policy)
        self.state = m.validate_snapshot(self.policy, self.initial, 192)

    def accept(self, snap, count=192, state=None):
        return m.validate_snapshot(self.policy, snap, count, self.state if state is None else state)

    def reject(self, snap, count=192, state=None):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.accept(snap, count, state)

    def test_unchanged_fleet_and_closed_summary(self):
        state = self.accept(snapshot(self.policy, self.state, 110))
        self.assertEqual(m.validate_closed(state), dict(recoveries=0, charged_recovery_s=0,
            charged_recovery_wall_s=0, full_capacity=True))

    def test_already_recovered_birth_charged_from_previous_observation(self):
        snap = snapshot(self.policy, self.state, 110, replacements={'168': replacement(self.policy, '168')})
        state = self.accept(snap)
        self.assertTrue(state['full_capacity'])
        self.assertEqual(state['total_recovery_s'], 10)
        self.assertEqual(state['completed_episodes'][0]['departed'], m.birth(self.policy['baseline_actors']['168']))
        self.assertEqual(state['registry']['168']['pid'], 11168)
        self.assertEqual(self.state['registry']['168']['pid'], 10168)

    def test_missing_then_new_birth_then_connected(self):
        state = self.accept(snapshot(self.policy, self.state, 110, missing=['168']), 191)
        self.assertFalse(state['full_capacity'])
        with self.assertRaises(ValueError):
            m.validate_closed(state)
        state = self.accept(snapshot(self.policy, state, 120,
            replacements={'168': replacement(self.policy, '168')}), 191, state)
        self.assertIsNotNone(state['pending']['replacement'])
        state = self.accept(snapshot(self.policy, state, 130), 192, state)
        self.assertEqual(state['total_recovery_s'], 30)
        self.assertEqual(m.validate_closed(state)['recoveries'], 1)

    def test_server_can_briefly_retain_departed_socket(self):
        state = self.accept(snapshot(self.policy, self.state, 110, missing=['168']), 192)
        self.assertFalse(state['full_capacity'])
        state = self.accept(snapshot(self.policy, state, 125,
            replacements={'168': replacement(self.policy, '168')}), 192, state)
        self.assertEqual(state['total_recovery_s'], 25)

    def test_reused_pid_needs_new_starttime_and_matching_probe(self):
        row = replacement(self.policy, '168')
        row['pid'] = self.policy['baseline_actors']['168']['pid']
        state = self.accept(snapshot(self.policy, self.state, 110, replacements={'168': row}))
        self.assertEqual(state['registry']['168']['starttime_ticks'], row['starttime_ticks'])

    def test_four_distinct_recoveries_and_exact120_second_budget(self):
        state = self.state
        for index, slot in enumerate(['1', '2', '3', '4']):
            snap = snapshot(self.policy, state, 130 + 30 * index,
                            replacements={slot: replacement(self.policy, slot)})
            state = self.accept(snap, state=state)
        self.assertEqual(m.validate_closed(state)['charged_recovery_s'], 120)
        self.reject(snapshot(self.policy, state, 230,
            replacements={'5': replacement(self.policy, '5')}), state=state)

    def test_per_recovery45_second_bound_includes_unobserved_interval(self):
        state = self.accept(snapshot(self.policy, self.state, 130, missing=['168']), 191)
        state = self.accept(snapshot(self.policy, state, 144, missing=['168']), 191, state)
        self.reject(snapshot(self.policy, state, 146,
            replacements={'168': replacement(self.policy, '168')}), state=state)
        state = self.accept(snapshot(self.policy, state, 145,
            replacements={'168': replacement(self.policy, '168')}), state=state)
        self.assertEqual(state['total_recovery_s'], 45)

    def test_connection_loss_without_process_departure_is_rejected(self):
        self.reject(snapshot(self.policy, self.state, 110), 191)

    def test_extra_connections_invalid_counts_and_types_are_rejected(self):
        for count in [193, 190, 0, -1, True, 192.0, '192', None]:
            with self.subTest(count=count):
                self.reject(snapshot(self.policy, self.state, 110), count)

    def test_two_missing_or_two_replaced_slots_are_rejected(self):
        self.reject(snapshot(self.policy, self.state, 110, missing=['1', '2']), 191)
        self.reject(snapshot(self.policy, self.state, 110,
            replacements={slot: replacement(self.policy, slot) for slot in ['1', '2']}))

    def test_departed_actor_still_live_is_rejected(self):
        for missing in [False, True]:
            snap = snapshot(self.policy, self.state, 110,
                missing=['168'] if missing else [],
                replacements={} if missing else {'168': replacement(self.policy, '168')})
            snap['previous_birth_probes']['168'] = self.policy['baseline_actors']['168']['starttime_ticks']
            self.reject(snap, 191 if missing else 192)

    def test_all_matching_role_and_provenance_fields_are_required(self):
        for key, value in [('parent_pid', 92), ('cgroup', '/foreign'), ('command', ['/usr/games/mame', 'other']),
                           ('affinity', [1]), ('uids', [0] * 4), ('environment', {}),
                           ('executable', dict(path='/tmp/mame', identity={}))]:
            with self.subTest(key=key):
                row = replacement(self.policy, '168')
                row[key] = value
                self.reject(snapshot(self.policy, self.state, 110, replacements={'168': row}))
        for key, value in [('ROBOTRON_CLIENT_SLOT', '169'), ('ROBOTRON_SOCKET_ADDRESS', 'dell:9999'),
                           ('ROBOTRON_EVAL_MODE', '1'), ('ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES', '1')]:
            with self.subTest(environment=key):
                row = replacement(self.policy, '168')
                row['environment'][key] = value
                self.reject(snapshot(self.policy, self.state, 110, replacements={'168': row}))

    def test_unchanged_actors_cannot_change_role_either(self):
        snap = snapshot(self.policy, self.state, 110)
        snap['actors']['10']['environment']['ROBOTRON_EVAL_MODE'] = '1'
        self.reject(snap)

    def test_unknown_slot_duplicate_pid_and_incomplete_probes_are_rejected(self):
        for problem in ['unknown', 'duplicate', 'probe', 'contradictory']:
            with self.subTest(problem=problem):
                snap = snapshot(self.policy, self.state, 110)
                if problem == 'unknown':
                    snap['actors']['192'] = snap['actors'].pop('168')
                elif problem == 'duplicate':
                    snap['actors']['168']['pid'] = snap['actors']['169']['pid']
                elif problem == 'probe':
                    del snap['previous_birth_probes']['168']
                else:
                    snap['previous_birth_probes']['168'] = None
                self.reject(snap)

    def test_invalid_replacement_births_are_rejected(self):
        for value in [0, -1, True, 100, self.policy['baseline_actors']['168']['starttime_ticks']]:
            with self.subTest(value=value):
                row = replacement(self.policy, '168')
                row['starttime_ticks'] = value
                self.reject(snapshot(self.policy, self.state, 110, replacements={'168': row}))

    def test_main_owner_unit_changes_and_query_diagnostics_are_rejected(self):
        for role in ['trainer', 'fleet']:
            for key, value in [('MainPID', '999'), ('InvocationID', 'f' * 32), ('NRestarts', '1'),
                               ('ControlGroup', '/foreign'), ('ActiveState', 'failed'), ('SubState', 'exited')]:
                with self.subTest(role=role, key=key):
                    snap = snapshot(self.policy, self.state, 110)
                    obs = snap['owners'][role]
                    fields = dict(line.split('=', 1) for line in obs['stdout'].splitlines())
                    fields[key] = value
                    obs['stdout'] = '\n'.join(k + '=' + v for k, v in fields.items())
                    self.reject(snap)
            snap = snapshot(self.policy, self.state, 110)
            snap['owners'][role]['process']['starttime_ticks'] += 1
            self.reject(snap)
            snap = snapshot(self.policy, self.state, 110)
            snap['owners'][role]['stderr'] = 'query warning'
            self.reject(snap)
            snap = snapshot(self.policy, self.state, 110)
            snap['owners'][role]['stdout'] += 'Id=foreign.service\n'
            self.reject(snap)

    def test_sampling_gaps_and_nonfinite_clocks_are_rejected(self):
        for at in [100, 99, 131, math.inf, math.nan, True]:
            with self.subTest(at=at):
                self.reject(snapshot(self.policy, self.state, at))
        for field in ['unix_s', 'monotonic_s', 'collection_started_unix_s', 'collection_started_monotonic_s']:
            snap = snapshot(self.policy, self.state, 110)
            snap[field] = float('nan')
            self.reject(snap)
        snap = snapshot(self.policy, self.state, 110)
        snap['collection_started_monotonic_s'] = 104
        self.reject(snap)

    def test_recovery_wall_clock_budget_independently_enforced(self):
        state = self.accept(snapshot(self.policy, self.state, 130, missing=['168']), 191)
        snap = snapshot(self.policy, state, 140, replacements={'168': replacement(self.policy, '168')})
        snap['unix_s'] += 6
        snap['collection_started_unix_s'] += 6
        self.reject(snap, state=state)

    def test_another_slot_during_pending_recovery_is_rejected(self):
        state = self.accept(snapshot(self.policy, self.state, 110, missing=['168']), 191)
        self.reject(snapshot(self.policy, state, 120,
            replacements={'167': replacement(self.policy, '167')}), 191, state)

    def test_replacement_that_crashes_before_connecting_is_rejected(self):
        state = self.accept(snapshot(self.policy, self.state, 110,
            replacements={'168': replacement(self.policy, '168')}), 191)
        self.reject(snapshot(self.policy, state, 120, missing=['168']), 191, state)
        self.reject(snapshot(self.policy, state, 120,
            replacements={'168': replacement(self.policy, '168', 2000)}), 191, state)

    def test_reappearing_departed_birth_is_rejected(self):
        state = self.accept(snapshot(self.policy, self.state, 110, missing=['168']), 191)
        snap = snapshot(self.policy, state, 120)
        snap['actors']['168'] = copy.deepcopy(self.policy['baseline_actors']['168'])
        snap['previous_birth_probes']['168'] = snap['actors']['168']['starttime_ticks']
        self.reject(snap, state=state)

    def test_same_slot_cannot_recover_twice(self):
        state = self.accept(snapshot(self.policy, self.state, 110,
            replacements={'168': replacement(self.policy, '168')}))
        self.reject(snapshot(self.policy, state, 120,
            replacements={'168': replacement(self.policy, '168', 2000)}), state=state)

    def test_accumulated_budget_rejects_even_below_four_recoveries(self):
        state = self.state
        at = 100
        for slot in ['1', '2']:
            at += 30
            state = self.accept(snapshot(self.policy, state, at, missing=[slot]), 191, state)
            at += 15
            state = self.accept(snapshot(self.policy, state, at,
                replacements={slot: replacement(self.policy, slot)}), state=state)
        state = self.accept(snapshot(self.policy, state, at + 30, missing=['3']), 191, state)
        self.reject(snapshot(self.policy, state, at + 31,
            replacements={'3': replacement(self.policy, '3')}), state=state)

    def test_initial_baseline_cannot_adopt_a_replacement_or_missing_actor(self):
        for snap, count in [(snapshot(self.policy, missing=['168']), 191),
                            (snapshot(self.policy, replacements={'168': replacement(self.policy, '168')}), 192)]:
            with self.assertRaises(ValueError):
                m.validate_snapshot(self.policy, snap, count)

    def test_policy_cannot_expand_budget(self):
        for field in m.LIMITS:
            with self.subTest(field=field):
                policy = copy.deepcopy(self.policy)
                policy['limits'][field] += 1
                with self.assertRaises(ValueError):
                    m.validate_snapshot(policy, self.initial, 192)

    def test_rejection_does_not_mutate_previous_state_or_input(self):
        snap = snapshot(self.policy, self.state, 110, missing=['1', '2'])
        before_state, before_snapshot = copy.deepcopy(self.state), copy.deepcopy(snap)
        self.reject(snap, 191)
        self.assertEqual(self.state, before_state)
        self.assertEqual(snap, before_snapshot)

    def test_cli_default_is_inert(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(SOURCE)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith('PLAN_ONLY:'))
        self.assertEqual(result.stderr, '')
        self.assertNotIn('torch', sys.modules)


if __name__ == '__main__':
    unittest.main()
