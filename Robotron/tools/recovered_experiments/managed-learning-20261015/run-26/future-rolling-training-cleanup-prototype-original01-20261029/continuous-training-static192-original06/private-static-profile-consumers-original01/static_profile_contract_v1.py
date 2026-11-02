"""Source-only static-main inventory/domain joins; no import-time actions.

Root must create actual immutable inventory after the owned same-state mode
transition. This file cannot create an authority or qualify a current case.
"""
import json


def require(value, reason):
    if not value:
        raise ValueError(reason)


def read(value, h):
    require(value['identity']['mode'] == '0o444', 'Immutable Root-selected metadata required')
    path = h.checked(value)
    require(path.stat().st_size <= 2_000_000, 'Bounded Root inventory/case required')
    return json.loads(path.read_bytes())


def validate_inventory(binding, h):
    require(binding['schema'] == 'robotron-continuous-static192-health-case-v1',
            'New typed static-original192 case required')
    authority = read(binding['input_inventory_authority'], h)
    require(authority['schema'] == 'robotron-root-continuous-static192-input-inventory-v1'
            and authority['status'] == 'ROOT_SELECTED_EXACT_HELD_INPUTS'
            and authority['mode'] == 'CONTINUOUS_TRAIN155_EVAL37_ONCE'
            and authority['source_authority'] == binding['continuous']['source_authority']
            and authority['inputs'] == binding['inputs']
            and type(authority['input_count']) is int
            and authority['input_count'] == len(binding['inputs']),
            'Actual exact new held-source inventory authority required')
    parent = read(authority['parent_case'], h)
    require(parent['schema'] == 'robotron-round-main-health-case-v1' and len(parent['inputs']) == 247,
            'Actual historical247-input predecessor must remain explicit')
    old, current = parent['inputs'], binding['inputs']
    require(set(old) <= set(current), 'New mode silently dropped a historical held input')
    changed = {path: dict(before=old[path], after=current[path]) for path in old if old[path] != current[path]}
    added = {path: current[path] for path in set(current) - set(old)}
    require(authority['replacements'] == changed and authority['added_inputs'] == added,
            'Every actual changed/added source must be an explicit exact transition')
    require(binding['input_inventory_authority']['path'] not in current,
            'Inventory must be held separately, never include its own hash recursively')
    return authority


def same_domain(proved, current):
    require(proved['schema'] == current['schema'] == 'robotron-continuous-static192-health-case-v1'
            and proved['inputs'] == current['inputs'] and proved['slot_eval'] == current['slot_eval']
            and proved['continuous'] == current['continuous']
            and proved['input_inventory_authority'] == current['input_inventory_authority'],
            'Readiness belongs to another original static physical/source/role authority')
    fields = ('pid', 'starttime_ticks', 'parent_pid', 'cgroup', 'command',
              'environment', 'affinity', 'uids', 'executable')
    for role in ('trainer', 'fleet'):
        old, actual = proved['owners'][role], current['owners'][role]
        require(old['unit'] == actual['unit'] and old['invocation'] == actual['invocation']
                and all(old['process'][key] == actual['process'][key] for key in fields),
                'Readiness original main owner/source/recipe changed')
    for kind in ('optimizer', 'replay'):
        require(all(proved['exposure'][kind][key] == current['exposure'][kind][key]
                    for key in ('process_id', 'instance_monotonic_ns', 'epoch', 'epoch_reason')),
                'Readiness optimizer/replay exposure lineage changed')


def sample_domain(binding, sample):
    """Additional coverage join AFTER exact typed health replay, not a substitute."""
    expected = set(map(str, range(192))); status = sample['status']
    require(status['schema'] == 'robotron-continuous-training-static192-snapshot-v2'
            and status['mode'] == 'CONTINUOUS_TRAIN155_EVAL37_ONCE'
            and status['epoch'] == binding['continuous']['epoch']
            and status['original_membership'] == binding['continuous']['original_membership']
            and set(status['slots']) == expected, 'Readiness does not hold the exact static192 domain')
    retired = {slot for slot, row in status['slots'].items()
               if row['eval_only'] is True and row['state'] in ('retiring_eval', 'closed_eval')
               and row['natural_result'] is not None}
    require(set(sample['actors']) | retired == expected
            and all(str(slot) in sample['actors'] for slot in expected if not binding['slot_eval'][slot]),
            'Readiness omits an original TRAIN/active EVAL without exact retirement evidence')


if __name__ == '__main__':
    print('SOURCE_ONLY_INERT_NO_AUTHORITY_OUTPUTS_OR_ACTIONS')
