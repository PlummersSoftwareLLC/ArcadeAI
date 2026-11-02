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
TARGET_SHA = '0ad741f9048aaf1c9598b23d71b65546a4c3d6e6bb5547ac8e762e675d28db7e'
REQUIRED_EXTRA = {'installed_wrapper', 'next_helper', 'accepted_guards', 'parent_collector',
                  'next_authority', 'target_lua', 'capture_equivalence_proof',
                  'root_selection', 'reconciler'}
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


def prepare(plan, read, selected, normalise, window):
    """Validate FUTURE facts and return objects; never publish or rebind anything."""
    require(plan['schema'] == 'robotron-slot163-next-output-reconciliation-plan-v1'
            and plan['root_selection'] is not None,
            'Future ROOT freeze-release authority required')
    selection = read(plan['root_selection'])
    require(selection['schema'] == 'robotron-root-slot163-next-capture-experiment-selection-v1'
            and selection['mode'] == 'NEXT_ONE_USE_PREVIEW_CAPTURE_EXPERIMENT_SLOT163'
            and selection['one_original_exec_only'] is True
            and selection['persistent_or_rollout_acceptance'] is False,
            'Exact ROOT one-use NEXT experiment selection required')
    release = read(selection['root_freeze_release'])
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
    require(plan['selected_was_historical_original_actor'] is False,
            'Current658236 OUTPUT is already a replacement, never a historical survivor')
    facts = {key: read(pin) for key, pin in plan['facts'].items()}
    old = facts['prior_binding']; policy = read(old['supervision_policy'])
    before = facts['before_snapshot']; after = facts['after_old_birth_probe_snapshot']
    ready = facts['new_registry_snapshot']; first_api, last_api = facts['before_API'], facts['after_API']
    require(plan['facts']['prior_binding']['sha256'] ==
            'd1661e1c52eb990281f2ebdf1eca63f042abf97863656b706d76b0bfa9515d23'
            and len(old['held_hashes']) == 207, 'Exact current207 OUTPUT binding required')
    core = read(old['prior_binding'])
    require(len(core['held_hashes']) == 197
            and all(old['held_hashes'].get(path) == sha for path, sha in core['held_hashes'].items()),
            'Original core197 must still be retained in current207')
    require(all(type(pin) is dict and type(pin.get('path')) is str
                for pin in plan['extra_pins'].values()), 'Exact extra source paths required')
    extra_paths = [pin['path'] for pin in plan['extra_pins'].values()]
    wrapper_path = '/home/dave/source/repos/ArcadeAI/Robotron/tools/mame_with_socket_wait.sh'
    require(len(extra_paths) == len(set(extra_paths)) == 9
            and set(extra_paths).intersection(old['held_hashes']) == {wrapper_path}
            and wrapper_path not in core['held_hashes'],
            'Exactly eight DISTINCT new paths and the owned existing wrapper path required')
    selected.validate_snapshot(policy, before, first_api['client_count'])
    wanted = {str(slot) for slot in range(192)}
    require(set(after['actors']) == set(ready['actors']) == wanted
            and len({row['pid'] for row in after['actors'].values()}) == 192,
            'Full distinct post-handoff192 registry required')
    require(0 < after['monotonic_s'] - before['monotonic_s'] <= plan['max_handoff_s']
            and 0 < after['unix_s'] - before['unix_s'] <= plan['max_handoff_s'],
            'Actual handoff exceeded declared bound')
    for role in ('trainer', 'fleet'):
        for observation in (after, ready):
            selected.validate_owner(policy[role], observation['owners'][role])
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
            '507f3f5a799d49791d2c6cbca3f4600167a166c4a410723d4d29225d18b6e0ab',
            'Current OUTPUT507 source authority differs')
    argv[argv.index('-autoboot_script') + 1] = target['path']
    require(expected['environment']['ROBOTRON_EVAL_MODE'] == '1', 'Current OUTPUT EVAL1 role required')
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
    authority = read(plan['extra_pins']['next_authority'])
    require(authority['schema'] == 'robotron-slot163-next-one-use-capture-authority-v1'
            and authority['mode'] == selection['mode']
            and authority['root_selection'] == plan['root_selection']
            and plan['extra_pins']['root_selection'] == plan['root_selection']
            and authority['current_output_binding'] == selection['current_output_binding']
            == plan['facts']['prior_binding']
            and authority['prior_actor'] == selection['prior_actor'] == old_actor
            and authority['output_lua'] == selection['output_lua'] == target
            and authority['base_manifest'] == selection['base_manifest']
            == old['preview_extra_source_pins']['launch_input_manifest']
            and authority['claim_directory'] == selection['claim_directory']
            and authority['supervisor_owner'] == policy['fleet']
            and authority['supervisor_process'] == before['owners']['fleet']['process'],
            'NEXT authority must join exact current OUTPUT/ROOT target/original supervisor')
    fresh_parent = read(authority['fresh_parent_snapshot'])
    require(authority['fresh_parent_snapshot'] == selection['fresh_parent_snapshot']
            and fresh_parent['actors'] == before['actors']
            and fresh_parent['owners']['fleet']['process'] == before['owners']['fleet']['process'],
            'Fresh authority parent facts differ from actual before census')
    require(claim['original_permit'] == plan['extra_pins']['next_authority']
            and claim['manifest'] == authority['base_manifest']
            and claim['observed_parent']['prior_owned_output_identity'] ==
                dict(pid=old_actor['pid'], starttime_ticks=old_actor['starttime_ticks'])
            and claim['observed_parent']['prior_owned_output_absent'] is True,
            'Actual NEXT claim must retire current OUTPUT, never original cached INPUT')
    proof = read(plan['extra_pins']['capture_equivalence_proof'])
    require(selection['capture_equivalence_proof'] == plan['extra_pins']['capture_equivalence_proof']
            and proof['schema'] == 'robotron-preview-fast-capture-byte-equivalence-and-CPU-source-package-v2'
            and proof['parent'] == old['preview_extra_source_pins']['target_lua']
            and proof['candidate'] == target and proof['preview_bytes_only'] is True
            and proof['gameplay_tensor_input_transport_timer_source_unchanged'] is True,
            'Exact preview-only source equivalence proof required')
    benchmark = read(proof['benchmark'])
    require(benchmark['schema'] == 'robotron-offline-exact-Lua54-preview-capture-benchmark-v1'
            and benchmark['actual_lua'] == 'Lua 5.4'
            and benchmark['actual_source_syntax_both_pass'] is True
            and benchmark['raw_and_compressed_preview_byte_equality_all_cases'] is True
            and benchmark['exact_whole_source_allowed_delta_verified'] is True
            and len(benchmark['cases']) >= 6, 'Original exact-Lua capture proof failed')
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
    require(plan['extra_pins']['installed_wrapper']['path'] == wrapper_path
            and old['held_hashes'][wrapper_path] ==
                'd38e6c2e689f22d2b89eabea0cae77f206fa1ec9d50da95f94484a900fa93004'
            and plan['extra_pins']['installed_wrapper']['sha256'] != old['held_hashes'][wrapper_path]
            and plan['extra_pins']['next_helper']['sha256'] ==
                '320c7b872a22d4e48d806b1868fe98ee85567b5e74ed1018248af4b06c89be48'
            and plan['extra_pins']['accepted_guards']['sha256'] ==
                '9a8fe7c08e1e941e2d26a2cc3c65124b27129b9f470a0020453e33010bf32027'
            and plan['extra_pins']['parent_collector']['sha256'] ==
                '1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0',
            'Only exact owned NEXT wrapper/helper/accepted guards/parent collector allowed')
    wrapper = read(plan['extra_pins']['installed_wrapper'], False).decode('utf-8')
    for role in ('next_helper', 'next_authority'):
        require(wrapper.count(plan['extra_pins'][role]['path']) == 1
                and wrapper.count(plan['extra_pins'][role]['sha256']) == 1,
                'Actual wrapper must invoke exact NEXT helper and authority')
    for role in ('accepted_guards', 'parent_collector'):
        require(wrapper.count(plan['extra_pins'][role]['path']) == 1,
                'Actual wrapper must select exact reviewed source dependencies')
    for role, pin in plan['extra_pins'].items():
        require(not pin['path'].endswith('.pt') and 0 < pin['bytes'] <= 2_000_000,
                'Extra holds are small source/config files, never model bodies')
        read(pin, False)  # Future caller verifies exact FULL identities and hashes.
        require(pin['path'] == wrapper_path or pin['path'] not in old['held_hashes'],
                'Only the exact existing wrapper may be rewritten')
        held[pin['path']] = pin['sha256']
    require(len(held) == 215
            and all(held[path] == sha for path, sha in old['held_hashes'].items() if path != wrapper_path)
            and all(held[path] == sha for path, sha in core['held_hashes'].items()),
            'Core197/all206 unchanged holds plus eight distinct NEXT pins required')
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
                   preview_next_root_selection=plan['root_selection'],
                   preview_previous_output_binding=plan['facts']['prior_binding'],
                   preview_current_binding_reason='Owned163 OUTPUT507 to exact preview-only fastLua; EVAL1/trainer/191 actors retained. New prospective binding only.')
    binding['historical_original_actor_survivors'] = old['historical_original_actor_survivors'] - int(plan['selected_was_historical_original_actor'])
    binding['verified_between_study_replacement_count'] = old['verified_between_study_replacement_count'] + 1
    binding['owned_preview_actor_transition_count'] = old.get('owned_preview_actor_transition_count', 0) + 1
    proof = dict(schema='robotron-owned-slot163-next-output-readonly-reconciliation-evidence-v1',
                 original_facts=copy.deepcopy(plan['facts']), old_actor=old_actor, actual_new_actor=new_actor,
                 old_CID=first_roles[SLOT]['connection_id'], actual_new_CID=last_roles[SLOT]['connection_id'],
                 actual_eval_preserved=True, original191_exact=True, original_trainer_and_supervisor_retained=True,
                 selected_connection_incarnation=connection_incarnation,
                 old_lua=old_lua, private_target=target, actual_claim_joined_to_live_MAME=True,
                 old_held_count=len(old['held_hashes']), new_held_count=len(held),
                 core197_hashes_retained=True, all206_nonwrapper_hashes_retained=True,
                 old_wrapper_sha256=old['held_hashes'][wrapper_path],
                 new_wrapper=plan['extra_pins']['installed_wrapper'],
                 capture_equivalence_proof_verified=True, extra_pins=copy.deepcopy(plan['extra_pins']),
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
