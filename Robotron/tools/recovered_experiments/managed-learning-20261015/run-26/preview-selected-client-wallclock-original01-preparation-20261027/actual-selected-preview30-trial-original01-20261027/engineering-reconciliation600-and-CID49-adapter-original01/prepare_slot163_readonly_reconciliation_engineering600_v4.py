"""Prospective read-only/pure one-slot reconciliation definitions.

No import-time I/O. No installation, signals, launch, save, retry or canonical
write. ROOT supplies source-authenticated modules and future immutable facts.
The unfilled template deliberately cannot produce a binding today.
"""
import copy
import hashlib
import json
import math

SLOT = '163'
TARGET_SHA = '507f3f5a799d49791d2c6cbca3f4600167a166c4a410723d4d29225d18b6e0ab'
REQUIRED_EXTRA = {'installed_wrapper', 'base_helper', 'trial_fuse_helper',
                  'launch_input_manifest', 'single_use_permit', 'target_lua',
                  'launcher', 'collector_derivative', 'reconciler', 'readonly_monitor'}
FACTS = {'prior_binding', 'before_snapshot', 'after_old_birth_probe_snapshot',
         'new_registry_snapshot', 'before_API', 'after_API', 'trial_claim'}


def require(value, message):
    if not value:
        raise ValueError(message)


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def roles(api):
    rows = api['client_rows']
    require(api['client_count'] == 192 and len(rows) == 192, 'Exactly192 actual API members required')
    result = {}
    for row in rows:
        slot = row['client_slot']
        require(type(slot) is int and 0 <= slot < 192 and str(slot) not in result
                and type(row['client_id']) is int and row['client_id'] >= 0
                and type(row['eval']) is bool, 'Exact unique slot/CID/actual role required')
        result[str(slot)] = dict(connection_id=row['client_id'], eval=row['eval'])
    require(len({v['connection_id'] for v in result.values()}) == 192, 'Duplicate actual CID')
    return result


def check_exposure(before, after, trainer_pid, normalise, window):
    first, last = normalise(before), normalise(after)
    require(first['optimizer_identity']['process_id'] == first['replay_identity']['process_id']
            == trainer_pid, 'Exposure does not belong to original trainer')
    window.progress(last, first, first)  # Existing identity/monotonic/outcome checks.
    return first, last


def prepare(plan, read, base, selected, normalise, window):
    """Validate FUTURE facts and return objects; never publish or rebind anything."""
    require(plan['schema'] == 'robotron-slot163-prospective-reconciliation-plan-v1'
            and plan['root_freeze_release'] is not None,
            'Future ROOT freeze-release authority required')
    release = read(plan['root_freeze_release'])
    require(release['schema'] == 'robotron-root-fixed03-preview-freeze-release-v1'
            and release['all_four_legs_qualified'] is True
            and release['all_owned_scopes_closed'] is True,
            'Original fixed comparison and scopes must finish first')
    require(set(plan['facts']) == FACTS and all(plan['facts'][key] is not None for key in FACTS)
            and set(plan['extra_pins']) == REQUIRED_EXTRA
            and all(plan['extra_pins'][key] is not None for key in REQUIRED_EXTRA),
            'Future actual PID/CID/inodes/observations remain unfilled')
    require(type(plan['max_handoff_s']) is int and 0 < plan['max_handoff_s'] <= 600,
            'ROOT must preselect bounded operational handoff time')
    require(type(plan['selected_was_historical_original_actor']) is bool,
            'Historical survivor classification must be explicitly proven')
    facts = {key: read(pin) for key, pin in plan['facts'].items()}
    old = facts['prior_binding']; policy = read(old['supervision_policy'])
    before = facts['before_snapshot']; after = facts['after_old_birth_probe_snapshot']
    ready = facts['new_registry_snapshot']; first_api, last_api = facts['before_API'], facts['after_API']
    require(len(old['held_hashes']) == 197, 'Exact original197 held sources required')
    require(all(type(pin) is dict and type(pin.get('path')) is str
                for pin in plan['extra_pins'].values()), 'Exact extra source paths required')
    extra_paths = [pin['path'] for pin in plan['extra_pins'].values()]
    require(len(extra_paths) == len(set(extra_paths)) == 10
            and set(extra_paths).isdisjoint(old['held_hashes']),
            'Ten DISTINCT extra source paths disjoint from original197 required')
    base.validate_snapshot(policy, before, first_api['client_count'])
    wanted = {str(slot) for slot in range(192)}
    require(set(after['actors']) == set(ready['actors']) == wanted
            and len({row['pid'] for row in after['actors'].values()}) == 192,
            'Full distinct post-handoff192 registry required')
    require(0 < after['monotonic_s'] - before['monotonic_s'] <= plan['max_handoff_s']
            and 0 < after['unix_s'] - before['unix_s'] <= plan['max_handoff_s'],
            'Actual handoff exceeded declared bound')
    for role in ('trainer', 'fleet'):
        for observation in (after, ready):
            base.validate_owner(policy[role], observation['owners'][role])
            require(observation['owners'][role]['process'] == before['owners'][role]['process'],
                    'Trainer/supervisor process configuration changed')
    old_actor = before['actors'][SLOT]; new_actor = after['actors'][SLOT]
    require(type(new_actor['pid']) is int and type(new_actor['starttime_ticks']) is int
            and new_actor['pid'] > 0 and new_actor['pid'] != old_actor['pid']
            and new_actor['starttime_ticks'] > old_actor['starttime_ticks']
            and after['previous_birth_probes'][SLOT] != old_actor['starttime_ticks'],
            'Actual new actor and positive original-birth absence required')
    target = plan['extra_pins']['target_lua']
    require(target['sha256'] == TARGET_SHA, 'Exact approved private preview Lua required')
    expected = copy.deepcopy(old_actor)
    expected['pid'] = new_actor['pid']; expected['starttime_ticks'] = new_actor['starttime_ticks']
    argv = expected['command']; require(argv.count('-autoboot_script') == 1, 'Exact Lua argument required')
    old_lua = argv[argv.index('-autoboot_script') + 1]
    require(old['held_hashes'].get(old_lua) ==
            '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf',
            'Original cached Lua/source authority differs')
    argv[argv.index('-autoboot_script') + 1] = target['path']
    require(expected['environment']['ROBOTRON_EVAL_MODE'] == '0', 'Cached original input role required')
    expected['environment']['ROBOTRON_EVAL_MODE'] = '1'
    require(new_actor == expected, 'Replacement changed more than PID/birth/Lua/explicitEVAL')
    for slot in wanted - {SLOT}:
        require(after['actors'][slot] == before['actors'][slot]
                and after['previous_birth_probes'][slot] == before['actors'][slot]['starttime_ticks'],
                'Another original actor changed')
    require(ready['actors'] == after['actors'], 'Replacement changed before new baseline')
    first_roles, last_roles = roles(first_api), roles(last_api)
    require(first_roles[SLOT]['eval'] is True and last_roles[SLOT]['eval'] is True
            and (first_roles[SLOT]['connection_id'] != last_roles[SLOT]['connection_id']
                 or first_roles[SLOT]['connection_id'] == 49),
            'Actual connection must preserve selected eval role; only CID49 reuse is allowed')
    require(all(first_roles[key] == last_roles[key] for key in wanted - {SLOT}),
            'Another actual CID/role changed')
    claim = facts['trial_claim']
    require(claim['schema'] == 'robotron-slot163-exec-reservation-consumed-v1'
            and claim['status'] == 'CONSUMED_RESERVATION_NOT_PROOF_OF_SUCCESSFUL_EXEC'
            and claim['claimant_pid'] == new_actor['pid']
            and claim['claimant_birth'] == new_actor['starttime_ticks']
            and claim['command'] == new_actor['command']
            and claim['observed_parent']['pid'] == policy['fleet']['pid']
            and claim['observed_parent']['starttime_ticks'] == policy['fleet']['starttime_ticks']
            and claim['observed_parent']['prior_actor_birth_absent'] is True,
            'Actual replacement must be the exact single-use claimant')
    require(claim['original_permit'] == plan['extra_pins']['single_use_permit']
            and claim['manifest'] == plan['extra_pins']['launch_input_manifest'],
            'Claim selected another permit/input manifest')
    # Engineering-only CID49 reuse is a new connection incarnation, never a fake CID.
    # Earlier positive old-birth absence/newPID/newbirth and the exact claim join
    # above remain mandatory. The public connected_seconds clock must reset
    # consistently with the consumed claim, within the existing API 5s cache bound.
    reused_CID = first_roles[SLOT]['connection_id'] == last_roles[SLOT]['connection_id']
    connection_incarnation = dict(numeric_CID_reused=reused_CID)
    if reused_CID:
        selected_row = next(row for row in last_api['client_rows'] if row['client_slot'] == 163)
        connected_s = selected_row.get('connected_seconds')
        api_stamp = last_api['ts']
        reserved_ns = claim.get('reserved_unix_ns')
        require(type(connected_s) in (int, float) and math.isfinite(connected_s) and connected_s >= 0
                and type(api_stamp) in (int, float) and math.isfinite(api_stamp)
                and type(reserved_ns) is int and reserved_ns > 0,
                'Reused CID49 requires actual finite reset connection-time evidence')
        connection_start_s = api_stamp - connected_s
        require(last_roles[SLOT]['connection_id'] == 49
                and new_actor['pid'] != old_actor['pid']
                and new_actor['starttime_ticks'] > old_actor['starttime_ticks']
                and after['previous_birth_probes'][SLOT] != old_actor['starttime_ticks']
                and claim['claimant_pid'] == new_actor['pid']
                and claim['claimant_birth'] == new_actor['starttime_ticks']
                and connection_start_s >= reserved_ns / 1e9 - 5.0
                and connection_start_s <= reserved_ns / 1e9 + 5.0
                and reserved_ns / 1e9 <= api_stamp + 5.0,
                'Reused CID49 is not joined to the new claimed actor/connection after old-birth absence')
        connection_incarnation.update(connection_start_unix_s=connection_start_s,
            claim_reserved_unix_s=reserved_ns / 1e9, timestamp_cache_tolerance_s=5.0)
    first, last = check_exposure(first_api, last_api, old['owner']['pid'], normalise, window)
    baseline = read(old['baseline_API'])
    window.healthy(first_api, baseline, old['experiment'], before['unix_s'])
    window.healthy(last_api, baseline, old['experiment'], ready['unix_s'])
    held = copy.deepcopy(old['held_hashes'])
    require(plan['extra_pins']['installed_wrapper']['path'] ==
            '/home/dave/source/repos/ArcadeAI/Robotron/tools/mame_with_socket_wait.sh'
            and plan['extra_pins']['installed_wrapper']['sha256'] == release['trial_wrapper_source_sha256']
            and plan['extra_pins']['launcher']['path'] ==
            '/home/dave/source/repos/ArcadeAI/Robotron/startmame.sh',
            'Installed wrapper/launcher path and selected source must be explicit')
    for role, pin in plan['extra_pins'].items():
        require(not pin['path'].endswith('.pt') and 0 < pin['bytes'] <= 2_000_000,
                'Extra holds are small source/config files, never model bodies')
        read(pin, False)  # Future caller verifies exact FULL identities and hashes.
        require(pin['path'] not in old['held_hashes'] or old['held_hashes'][pin['path']] == pin['sha256'],
                'Old held input would be rewritten')
        held[pin['path']] = pin['sha256']
    require(len(held) == 207
            and all(held[path] == sha for path, sha in old['held_hashes'].items()),
            'All original197+ holds must remain and new installed sources be explicit')
    new_policy = copy.deepcopy(policy)
    new_policy['baseline_actors'] = copy.deepcopy(ready['actors'])
    new_policy['baseline_owners'] = copy.deepcopy(ready['owners'])
    new_policy['held_hashes_sha256'] = checksum(held)
    selected.validate_snapshot(new_policy, ready, last_api['client_count'])
    binding = copy.deepcopy(old)
    for actor in binding['actors']:
        if actor['slot'] == 163:
            actor['pid'] = new_actor['pid']; actor['starttime_ticks'] = new_actor['starttime_ticks']
    binding.update(held_hashes=held, supervision_policy=None,
                   preview_slot163_transition=None, prior_binding=plan['facts']['prior_binding'],
                   preview_actual_roles=last_roles, preview_before_exposure=first,
                   preview_expected_target_sha256=TARGET_SHA,
                   preview_extra_source_pins=copy.deepcopy(plan['extra_pins']),
                   preview_current_binding_reason='Owned163 privateLua+expliciteval transition; trainer and191 actors retained. New prospective binding only.')
    binding['historical_original_actor_survivors'] = old['historical_original_actor_survivors'] - int(plan['selected_was_historical_original_actor'])
    binding['verified_between_study_replacement_count'] = old['verified_between_study_replacement_count'] + 1
    binding['owned_preview_actor_transition_count'] = old.get('owned_preview_actor_transition_count', 0) + 1
    proof = dict(schema='robotron-owned-slot163-readonly-reconciliation-evidence-v1',
                 original_facts=copy.deepcopy(plan['facts']), old_actor=old_actor, actual_new_actor=new_actor,
                 old_CID=first_roles[SLOT]['connection_id'], actual_new_CID=last_roles[SLOT]['connection_id'],
                 actual_eval_preserved=True, original191_exact=True, original_trainer_and_supervisor_retained=True,
                 selected_connection_incarnation=connection_incarnation,
                 old_lua=old_lua, private_target=target, actual_claim_joined_to_live_MAME=True,
                 old_held_count=len(old['held_hashes']), new_held_count=len(held),
                 original_source_hashes_retained=True, extra_pins=copy.deepcopy(plan['extra_pins']),
                 original_exposure=first, actual_after_exposure=last,
                 model_weights_replay_optimizer_not_reloaded_by_this_component=True,
                 weights_continue_evolving_under_training=True,
                 canonical_or_current_binding_changed=False, preparation_only_until_ROOT_publishes=True)
    return dict(policy=new_policy, binding_requiring_actual_policy_and_transition_pins=binding,
                transition=proof, selected_collector_source_required=True)


def finalize(prepared, actual_policy_pin, actual_transition_pin, read):
    """Bind only actually published matching files; no filesystem/canonical writes."""
    require(read(actual_policy_pin) == prepared['policy']
            and read(actual_transition_pin) == prepared['transition'],
            'Actual immutable policy/transition differ from prepared values')
    result = copy.deepcopy(prepared['binding_requiring_actual_policy_and_transition_pins'])
    result['supervision_policy'] = actual_policy_pin
    result['preview_slot163_transition'] = actual_transition_pin
    return result


if __name__ == '__main__':
    print('PLAN_ONLY: prospective read-only definitions; no current facts, output, capture or binding action')
