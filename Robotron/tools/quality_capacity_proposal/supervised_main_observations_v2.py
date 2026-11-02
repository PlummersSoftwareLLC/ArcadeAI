"""Unselected supervision/API joins for a future quality observer and reviewer.

Original raw API bytes are never rewritten. After independently validating each
process census and its bounded recovery state, an internal capacity-normalised
view lets the unchanged legacy validator check all other API, source, checkpoint,
clock, optimizer/replay identity, outcome, progress and interval predicates.
That internal view is never published as an original observation.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'robotron-supervised-main-observations-v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def pack(snapshot, supervision):
    """Commit every observed static role without duplicating its baseline fields."""
    result = copy.deepcopy(snapshot)
    result['schema'] = 'robotron-main-supervision-compact-snapshot-v1'
    actors = {}
    for slot, actor in snapshot['actors'].items():
        require(set(actor) == {'pid', 'starttime_ticks', *supervision.STATIC}, 'Unexpected actor census fields')
        actors[slot] = dict(supervision.birth(actor), role_sha256=checksum({key: actor[key] for key in supervision.STATIC}))
    result['actors'] = actors
    return result


def unpack(policy, compact, supervision):
    require(compact['schema'] == 'robotron-main-supervision-compact-snapshot-v1', 'Exact compact census schema required')
    result = copy.deepcopy(compact)
    result['schema'] = 'robotron-main-supervision-snapshot-v1'
    actors = {}
    for slot, actor in compact['actors'].items():
        require(slot in policy['baseline_actors'] and set(actor) == {'pid', 'starttime_ticks', 'role_sha256'},
                'Unknown compact slot or substituted census fields')
        role = {key: policy['baseline_actors'][slot][key] for key in supervision.STATIC}
        require(actor['role_sha256'] == checksum(role), 'Observed process role hash differs from the precommitted role')
        actors[slot] = dict(copy.deepcopy(role), **supervision.birth(actor))
    result['actors'] = actors
    return result


def validate_binding(main, policy, supervision):
    supervision.validate_policy(policy)
    expected = {str(actor['slot']): actor for actor in main['actors']}
    require(len(main['actors']) == 192 and set(expected) == supervision.SLOTS
            and len(main['held_hashes']) == 196 and policy['trainer'] == main['owner']
            and policy['held_hashes_sha256'] == checksum(main['held_hashes']),
            'Supervision policy is not bound to the held main trainer/196 sources')
    for slot, actor in expected.items():
        require(supervision.birth(actor) == supervision.birth(policy['baseline_actors'][slot])
                and actor['mask'] == policy['baseline_actors'][slot]['affinity'],
                'Supervision baseline substituted a precommitted main actor')


def observed_main(main, snapshot):
    result = dict(main)
    result['actors'] = [dict(pid=actor['pid'], starttime_ticks=actor['starttime_ticks'],
                             slot=int(slot), mask=actor['affinity'])
                        for slot, actor in snapshot['actors'].items()]
    return result


def joined_census(policy, compact, sample, state, supervision):
    snapshot = unpack(policy, compact, supervision)
    require(0 <= sample['unix_s'] - snapshot['unix_s'] <= 5
            and 0 <= sample['monotonic_s'] - snapshot['monotonic_s'] <= 5,
            'Original API observation is not adjacent to its process census')
    return snapshot, supervision.validate_snapshot(policy, snapshot, sample['API']['client_count'], state)


def healthy(api, baseline, experiment, unix, state, original_healthy):
    require(state is not None and (state['full_capacity'] or state['pending'] is not None),
            'Capacity exception requires a validated, bounded supervision state')
    require(type(api['client_count']) is int and api['client_count'] in (191, 192)
            and (api['client_count'] == 192 or state['pending'] is not None),
            'Unknown or unexplained main connection count')
    # Only this local view changes capacity. The original API wire and critical
    # projection remain unchanged and are separately rejoined by the reviewer.
    view = dict(api, client_count=192)
    original_healthy(view, baseline, experiment, unix)


def sample(guard, read_API_bytes, raw_witness_module):
    """Preserve the inherited exposure/progress predicates with explicit census joins."""
    snapshot = guard.supervision.collect(guard.supervision_policy, guard.fleet_state)
    compact = pack(snapshot, guard.supervision)
    snapshot_pin = guard.save(guard.binding_dir/'main-fleet-snapshots'/f'{guard.observation_serial:04d}.json', compact)
    guard.observation_attempt['main_fleet_snapshot'] = snapshot_pin
    raw = read_API_bytes()
    raw_entry = guard.save(guard.binding_dir/'API-wires'/f'{guard.observation_serial:04d}.raw', raw)
    guard.observation_attempt.update(API_wire=raw_entry, API_received=True,
        API_wire_complete_within_bound=len(raw) <= raw_witness_module().MAX_WIRE_BYTES)
    api = raw_witness_module().parse_wire(raw)
    guard.observation_attempt['API_parsed'] = True
    save = (Path(guard.window.MODEL)/'robotron_dqn_latest.pt').stat()
    unix, monotonic = guard.clock(), guard.monotonic()
    guard.observation_attempt.update(unix_s=unix, monotonic_s=monotonic,
        autosave=dict(mtime_ns=save.st_mtime_ns, bytes=save.st_size, age_s=unix - save.st_mtime_ns/1e9))
    _, state = joined_census(guard.supervision_policy, compact,
        dict(API=api, unix_s=unix, monotonic_s=monotonic), guard.fleet_state, guard.supervision)
    # The original helper checks the exact currently observed live actors plus
    # the unchanged trainer, all196 controls/sources and save-request absence.
    # The full census additionally proves supervisor parentage and held roles.
    guard.window.owner_and_files(observed_main(guard.main, snapshot))
    healthy(api, guard.baseline, guard.main['experiment'], unix, state, guard.window.healthy)
    age = unix - save.st_mtime_ns/1e9
    require(save.st_size > 0 and math.isfinite(age) and 0 <= age <= 360, 'Main autosave stale, future or empty')
    if guard.last_sample:
        previous = guard.last_sample
        require(0 < monotonic - previous['monotonic_s'] <= 30 and 0 < unix - previous['unix_s'] <= 30,
                'Main observation gap exceeded30 seconds')
        require(all(api[key] >= previous['API'][key] for key in
                    ('frame_count', 'learner_frame_count', 'optimized_samples', 'training_steps')), 'Main work clocks regressed')
    exposure = api['host_pipeline']['learning_exposure']
    guard.validate_exposure(api, monotonic)
    progress = dict(applied=exposure['optimizer']['total']['applied'], learner=api['learner_frame_count'],
                    accepted=exposure['replay']['accepted_learner_total'])
    for name, count in progress.items():
        require(type(count) is int and count >= 0, 'Invalid main progress counter: ' + name)
        previous = guard.progress.get(name)
        require(previous is None or count >= previous[0], 'Main progress counter regressed: ' + name)
        if previous is None or count > previous[0]:
            guard.progress[name] = (count, monotonic)
        else:
            require(monotonic - previous[1] < 60, 'Main made no ' + name + ' progress for60 seconds')
    value = dict(monotonic_s=monotonic, unix_s=unix, main_owner=guard.main['owner'],
        supervised_main_fleet_verified=True, main_fleet_snapshot=snapshot_pin,
        main_fleet_state_sha256=checksum(state), held_hashes_sha256=guard.held_sha,
        **raw_witness_module().witness_fields(api, raw_entry),
        autosave=dict(mtime_ns=save.st_mtime_ns, bytes=save.st_size, age_s=age))
    guard.samples.append(guard.save(guard.binding_dir/'main-samples'/f'{len(guard.samples):04d}.json', value))
    guard.last_sample = value
    guard.fleet_state = state


def finish(guard):
    summary = None
    if guard.failed is None:
        try:
            require(guard.fleet_state is not None, 'No accepted main supervision census')
            summary = guard.supervision.validate_closed(guard.fleet_state)
        except Exception as error:
            guard.failed = repr(error)
    manifest = dict(schema=SCHEMA, status='PASS' if guard.failed is None else 'FAILED',
        configuration_changed=False if guard.failed is None else None, controller_changed_learning=False,
        main_owner=guard.main['owner'], samples=guard.samples, error=guard.failed,
        API_witness_format=guard.wire_format, accounting_policy='single_inflight_optimizer_v1',
        rejected_observations=guard.rejected_observations, supervision_policy=guard.job['main_supervision_policy'],
        supervision_summary=summary, progress_guard='Applied optimizer, learner frames and accepted learner inserts must advance within60 seconds')
    guard.main_manifest = guard.save(guard.review_job['runtime_paths']['main_observations'], manifest)
    guard.finished = True


def review(main, policy, manifest, samples, start, end, read, runtime, window, supervision):
    """Rejoin original census evidence first, then reuse unchanged exposure checks."""
    validate_binding(main, policy, supervision)
    require(manifest['schema'] == SCHEMA and manifest['supervision_policy'] == main['supervision_policy'],
            'Exact prospective supervision policy and observation schema required')
    state = None
    paths = set()
    views = []
    for sample in samples:
        require(sample.get('supervised_main_fleet_verified') is True
                and 'original192_actors_verified' not in sample, 'Explicit supervised main witness required')
        pin = sample['main_fleet_snapshot']
        require(pin['path'] not in paths, 'A main process census was reused')
        paths.add(pin['path'])
        _, state = joined_census(policy, read(pin), sample, state, supervision)
        require(sample['main_fleet_state_sha256'] == checksum(state), 'Recorded supervision state differs from independent replay')
        # This internal legacy view checks exposure/progress/other API predicates
        # only after actual process capacity and recovery have been verified.
        # It is not a replacement for the original raw witness or its actor claim.
        view = dict(sample, original192_actors_verified=True, API=dict(sample['API'], client_count=192))
        views.append(view)
    require(state is not None, 'No original supervision observations')
    summary = supervision.validate_closed(state)
    require(manifest['supervision_summary'] == summary, 'Closed supervision budget/summary differs')
    legacy_manifest = dict(manifest, schema='robotron-main192-pilot-observations-v1')
    runtime.validate_main_samples(main, legacy_manifest, views, start, end, window.healthy)
    return state, summary


def validate_current(main, policy, snapshot, state, supervision, window):
    """Require the exact final accepted registry still live at review completion.

    The scientific interval is already closed. This fresh read-only check grants
    no additional recovery or observation-gap exception after the native exit.
    """
    require(state['pending'] is None and state['full_capacity'], 'Unrestored final main fleet')
    final_policy = dict(policy, baseline_actors=state['registry'])
    supervision.validate_snapshot(final_policy, snapshot, 192)
    window.owner_and_files(observed_main(main, snapshot))


if __name__ == '__main__':
    print('PLAN_ONLY: unselected API/census join; no reads, queries, outputs or runtime changes')
