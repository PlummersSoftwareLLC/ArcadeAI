"""Accepted-preview declared-subset source definitions; default CLI is inert.

No batches, stops, installs, retries or binding publication. INPUT remains the
cached supervisor's original192 oldLua/env0. Current OUTPUT is separate and may
be mixed. Every upgraded eval/non-eval role is explicitly forced1/2.
"""
import copy
import hashlib
import json
import os


def require(value, message):
    if not value:
        raise ValueError(message)


def subset(values):
    require(type(values) is list and all(type(v) is int and 0 <= v < 192 for v in values)
            and values == sorted(set(values)), 'Sorted unique declared192 subset required')
    return set(values)


def source_contracts(manifest, overrides):
    selected = subset(overrides)
    require(set(manifest['slots']) == {str(v) for v in range(192)}, 'Original192 INPUT required')
    result = {}
    for key, row in manifest['slots'].items():
        require(row['expected_environment']['ROBOTRON_EVAL_MODE'] == '0'
                and type(row['eval']) is bool, 'Cached original INPUT0 and actual role required')
        upgraded = int(key) in selected
        source = manifest['target_lua'] if upgraded else manifest['original_lua']
        result[key] = dict(slot=int(key), upgraded=upgraded, actual_eval=row['eval'],
            eval_mode=('1' if row['eval'] else '2') if upgraded else '0',
            lua_path=source['path'], lua_sha256=source['sha256'])
    return result


def prepare_output(manifest, overrides, args, environment, base):
    """Keep bfff INPUT/wait/argv validation, then apply ONLY declared outputs.

    bfff prepares a163-specific output. Reset its two output values to the
    authenticated INPUT template, then choose this declaration's source/role.
    No other argv/environment value is reconstructed or changed.
    """
    command, output = base.prepare_launch(manifest, args, environment)
    contract = source_contracts(manifest, overrides)[environment['ROBOTRON_CLIENT_SLOT']]
    at = command.index('-autoboot_script') + 1
    command[at] = contract['lua_path']
    output['ROBOTRON_EVAL_MODE'] = contract['eval_mode']
    return command, output


def validate_output_registry(registry, manifest, input_actors, roles):
    require(registry['schema'] == 'robotron-preview-current-mixed-output-registry-v1'
            and set(registry['actors']) == {str(v) for v in range(192)}
            and len({row['pid'] for row in registry['actors'].values()}) == 192,
            'Distinct actual current192 OUTPUT registry required')
    contracts = source_contracts(manifest, registry['override_slots'])
    require(set(roles) == set(contracts), 'Actual OUTPUT roles incomplete')
    for slot, actual in registry['actors'].items():
        require(type(actual['pid']) is int and actual['pid'] > 0
                and type(actual['starttime_ticks']) is int and actual['starttime_ticks'] > 0,
                'Actual positive OUTPUT process identity required')
        expected = copy.deepcopy(input_actors[slot])
        expected.update(pid=actual['pid'], starttime_ticks=actual['starttime_ticks'])
        contract = contracts[slot]
        expected['command'][expected['command'].index('-autoboot_script') + 1] = contract['lua_path']
        expected['environment']['ROBOTRON_EVAL_MODE'] = contract['eval_mode']
        require(actual == expected, 'OUTPUT differs from declared source/role or original static fields')
        require(roles[slot]['eval'] is contract['actual_eval'], 'Actual role drifted across new CID')
    return contracts


def validate_plan(plan, read, base, accepted163, role_reader):
    require(plan['schema'] == 'robotron-accepted-preview-declared-subset-plan-v1'
            and all(plan[key] is not None for key in ('accepted_one_slot_authority', 'input_manifest',
                'current_output_registry', 'fresh_parent_snapshot', 'ROOT_rollout_selection', 'override_slots')),
            'Future accepted benchmark/current OUTPUT/parent/subset remain unfilled')
    authority = read(plan['accepted_one_slot_authority'])
    require(authority['mode'] == accepted163.ACCEPT, 'Only an actually accepted one-slot authority opens rollout')
    manifest = accepted163.validate_authority(authority, read, base)
    require(plan['input_manifest'] == authority['base_manifest'], 'Cached INPUT manifest changed')
    chosen = subset(plan['override_slots'])
    registry = read(plan['current_output_registry'])
    existing = subset(registry['override_slots'])
    require(existing <= chosen and 163 in existing, 'Accepted163 coverage cannot be silently rolled back')
    selection = read(plan['ROOT_rollout_selection'])
    require(selection['schema'] == 'robotron-root-preview-declared-subset-selection-v1'
            and selection['accepted_one_slot_authority'] == plan['accepted_one_slot_authority']
            and selection['input_manifest'] == plan['input_manifest']
            and selection['current_output_registry'] == plan['current_output_registry']
            and selection['fresh_parent_snapshot'] == plan['fresh_parent_snapshot']
            and selection['override_slots'] == plan['override_slots']
            and type(selection['maximum_new_overrides']) is int
            and 0 <= len(chosen - existing) <= selection['maximum_new_overrides'] <= 192,
            'ROOT must prospectively choose a bounded addition subset')
    snapshot = read(registry['actual_snapshot'])
    api = read(registry['actual_API'])
    require(snapshot['actors'] == registry['actors'], 'Current OUTPUT snapshot differs')
    roles = role_reader(api)
    require(roles == registry['actual_roles'], 'Current OUTPUT CID/role proof differs')
    census = base.strict_json(base.read_bytes_pin(manifest['role_census']))
    validate_output_registry(registry, manifest, census['actual_snapshot']['actors'], roles)
    parent = read(plan['fresh_parent_snapshot'])
    require(parent['owners']['fleet']['process'] == authority['supervisor_process'],
            'Fresh original supervisor INPUT process changed')
    return dict(manifest=manifest, current_registry=registry, source_contracts=source_contracts(manifest, plan['override_slots']),
                parent_owner=authority['supervisor_owner'], parent_process=authority['supervisor_process'],
                newly_declared_slots=sorted(chosen - existing))


def validate_bounded_transition(before, after, manifest, input_actors, before_roles, after_roles, maximum_new):
    """Pure future observation join. Does not cause any actor transition."""
    old = subset(before['override_slots']); new = subset(after['override_slots'])
    require(old <= new and type(maximum_new) is int and 0 <= len(new - old) <= maximum_new,
            'Undeclared coverage removal or oversized future addition')
    validate_output_registry(before, manifest, input_actors, before_roles)
    contracts = validate_output_registry(after, manifest, input_actors, after_roles)
    added = new - old
    for slot in range(192):
        key = str(slot)
        if slot not in added:
            require(before['actors'][key] == after['actors'][key]
                    and before_roles[key] == after_roles[key], 'Unselected OUTPUT member changed')
        else:
            previous, current = before['actors'][key], after['actors'][key]
            require(current['pid'] != previous['pid'] and current['starttime_ticks'] > previous['starttime_ticks']
                    and before_roles[key]['connection_id'] != after_roles[key]['connection_id'],
                    'Upgraded slot needs a NEW actual process/CID, not hot source relabelling')
    return dict(newly_observed_upgraded_slots=sorted(added), contracts=contracts,
                all_other_output_identities_CIDs_and_roles_unchanged=True)


def prepare_policy(prior_policy, manifest, overrides, snapshot, actual_roles, held_hashes, input_actors, collector):
    """Pure new policy object from actual future full OUTPUT; no publication."""
    registry = dict(schema='robotron-preview-current-mixed-output-registry-v1',
                    override_slots=overrides, actors=snapshot['actors'])
    contracts = validate_output_registry(registry, manifest, input_actors, actual_roles)
    policy = copy.deepcopy(prior_policy)
    policy.update(schema='robotron-preview-declared-subset-supervision-policy-v1',
        baseline_actors=copy.deepcopy(snapshot['actors']), baseline_owners=copy.deepcopy(snapshot['owners']),
        held_hashes_sha256=hashlib.sha256(json.dumps(held_hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        preview_slot_contracts=contracts, preview_override_slots=list(overrides),
        preview_input_lua=manifest['original_lua'], preview_target_lua=manifest['target_lua'],
        preview_input_roles={key: value['eval'] for key, value in manifest['slots'].items()})
    collector.validate_snapshot(policy, snapshot, 192)
    return policy


def dispatch(plan, args, environment, read, base, accepted163, role_reader, fuse, collector, exec_function=None):
    """Accepted persistent admission only. This function never starts a batch."""
    context = validate_plan(plan, read, base, accepted163, role_reader)
    command, output = prepare_output(context['manifest'], plan['override_slots'], args, environment, base)
    slot = environment['ROBOTRON_CLIENT_SLOT']
    if int(slot) in subset(plan['override_slots']):
        # Unlike a163-only input census, this is the chosen slot's CURRENT
        # output identity. No stop/signal is performed; require its absence.
        fuse.verify_parent(dict(supervisor_owner=context['parent_owner'],
            supervisor_process=context['parent_process'],
            prior_actor=context['current_registry']['actors'][slot]), collector)
    (os.execve if exec_function is None else exec_function)(command[0], command, output)
    raise AssertionError('execve returned without replacing the launcher')


if __name__ == '__main__':
    print('PLAN_ONLY: accepted-benchmark gate and future subset/OUTPUT facts unfilled; no rollout or exec')
