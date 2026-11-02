"""Prospective same-original-process TRAIN overlap checks; inert on import.

An authenticated overlap is pending, never an accepted physical census. Callers
must keep the existing ten-second deadline and require a later unique binding
with original-token cleanup before accepting another observation.
"""
from collections import defaultdict
import copy
import os


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_ownership(fleet, slot, binding, candidate, proof):
    row = fleet['slots'][str(slot)]
    require(binding['kind'] == 'physical-connection' and binding['slot'] == slot
            and binding['incarnation'] == 1
            and all(binding[k] == fleet[k] for k in
                    ('epoch', 'supervisor', 'trainer', 'source_authority')),
            'Pending TRAIN binding lineage changed')
    recorded = binding['data']['actor']
    before, after = proof['actor_before'], proof['actor_after']
    require(before == after and all(before[k] == recorded[k] for k in
            ('pid', 'birth', 'parent', 'exe', 'command', 'cgroup', 'uid'))
            and before['pid'] == row['original_pid']
            and before['birth'] == row['original_birth']
            and before['parent'] == fleet['supervisor']['pid']
            and before['cgroup'] == fleet['supervisor']['cgroup']
            and before['uid'] == os.getuid() and before['exe'] == '/usr/games/mame'
            and all(before['environment'].get(k) == value
                    for k, value in recorded['environment'].items()),
            'Pending TRAIN candidate is not the same original MAME process')
    tcp = proof['TCP']
    require(type(tcp['inode']) is int and tcp['inode'] > 0
            and tcp['local'] == candidate['socket_endpoints']['peer']
            and tcp['remote'] == candidate['socket_endpoints']['server'],
            'Pending TRAIN candidate lacks its process-owned TCP proof')


def capture_pending(fleet, connections, expected, membership, roles, *, now,
                    strict_validator, read_pin, physical_actor, tcp_binding):
    """Try unchanged strict validation first, then prove a narrow pending case.

The callbacks must be the pinned immutable reader and original physical helpers.
No client is adopted, signalled, or treated as completed by this function.
"""
    try:
        pending = strict_validator(fleet, connections, expected, membership, roles, now=now)
        return dict(pending_slots=pending, overlaps={}, census_qualified=False)
    except ValueError as error:
        if str(error) != 'Duplicate/foreign live Main connection':
            raise
    rows = connections['connections']
    require(type(rows) is list and all(type(r['client_slot']) is int
            and str(r['client_slot']) in roles
            and type(r['token']) is str and type(r['client_id']) is int
            and r['eval_only'] is roles[str(r['client_slot'])] for r in rows)
            and len({r['token'] for r in rows}) == len(rows)
            and len({r['client_id'] for r in rows}) == len(rows),
            'Foreign or duplicated Main identity is not a pending TRAIN reconnect')
    grouped = defaultdict(list)
    for connection in rows:
        grouped[connection['client_slot']].append(connection)
    duplicates = {slot: values for slot, values in grouped.items() if len(values) > 1}
    require(bool(duplicates) and all(len(values) == 2 and roles[str(slot)] is False
            and fleet['slots'][str(slot)]['state'] in ('active_train', 'reconnecting_train')
            for slot, values in duplicates.items()),
            'Only one old plus one new original TRAIN connection may be pending')
    pruned = []
    overlaps = {}
    for slot, values in grouped.items():
        if slot not in duplicates:
            pruned.extend(values)
            continue
        row = fleet['slots'][str(slot)]
        binding = read_pin(row['current_physical_binding'])
        old = binding['data']['connection']
        old_rows = [value for value in values if value['token'] == old['token']]
        fresh = [value for value in values if value['token'] != old['token']]
        require(old_rows == [old] and len(fresh) == 1,
                'Pending TRAIN overlap does not contain the exact retained old binding')
        candidate = fresh[0]
        require(type(candidate['connection_ns']) is int
                and candidate['connection_ns'] > old['connection_ns'],
                'Pending TRAIN candidate must have a strictly newer connection')
        before = physical_actor(row['original_pid'])
        tcp = tcp_binding(row['original_pid'], candidate['socket_endpoints'])
        after = physical_actor(row['original_pid'])
        # Keep only the same declared environment keys as the original binding.
        for actor in (before, after):
            actor['environment'] = {key: actor['environment'].get(key)
                                    for key in binding['data']['actor']['environment']}
        proof = dict(actor_before=before, TCP=tcp, actor_after=after)
        validate_ownership(fleet, slot, binding, candidate, proof)
        overlaps[str(slot)] = dict(binding_pin=row['current_physical_binding'],
                                  binding=binding, candidate=candidate, proof=proof)
        pruned.append(old)
    # All existing provenance, freshness, role, fault and original-membership
    # checks still run. The pruned view is only a validation aid, never a saved
    # replacement for the actual complete connection snapshot.
    strict_view = dict(connections, connections=pruned)
    pending = strict_validator(fleet, strict_view, expected, membership, roles, now=now)
    return dict(pending_slots=sorted(set(pending) | set(duplicates)),
                overlaps=overlaps, census_qualified=False)


def replay_pending(fleet, connections, expected, membership, roles, captured, *, now,
                   strict_validator, read_pin):
    """Recheck saved ownership evidence against independently read binding pins."""
    require(type(captured) is dict and set(captured) ==
            {'pending_slots', 'overlaps', 'census_qualified'}
            and captured['census_qualified'] is False,
            'Exact pending metadata evidence required')
    entries = captured['overlaps']
    require(type(entries) is dict, 'Exact overlap proof mapping required')
    by_pid = {}
    for key, entry in entries.items():
        require(key in fleet['slots'] and str(int(key)) == key,
                'Foreign saved overlap slot')
        row = fleet['slots'][key]
        require(entry['binding_pin'] == row['current_physical_binding']
                and entry['binding'] == read_pin(entry['binding_pin']),
                'Saved overlap binding differs from immutable original event')
        require(row['original_pid'] not in by_pid, 'Ambiguous saved actor ownership')
        by_pid[row['original_pid']] = entry
    calls = defaultdict(int)

    def actor(pid):
        require(pid in by_pid and calls[pid] < 2, 'Missing original actor overlap evidence')
        key = 'actor_before' if calls[pid] == 0 else 'actor_after'
        calls[pid] += 1
        return copy.deepcopy(by_pid[pid]['proof'][key])

    def tcp(pid, endpoints):
        require(pid in by_pid and endpoints == by_pid[pid]['candidate']['socket_endpoints'],
                'Saved candidate endpoint differs')
        return copy.deepcopy(by_pid[pid]['proof']['TCP'])

    replayed = capture_pending(fleet, connections, expected, membership, roles,
        now=now, strict_validator=strict_validator, read_pin=read_pin,
        physical_actor=actor, tcp_binding=tcp)
    require(replayed == captured and all(calls[pid] == 2 for pid in by_pid),
            'Saved pending ownership result differs from independent replay')
    return replayed


def validate_binding_cleanup(fleet, slot, binding, *, read_pin, closed_connection):
    """An accepted rebind must retain the exact positively closed old token."""
    data = binding['data']
    previous = data.get('previous_binding')
    cleanup_pin = data.get('old_token_cleanup')
    if previous is None:
        require(cleanup_pin is None, 'Initial binding cannot claim an old-token cleanup')
        return
    require(fleet['slots'][str(slot)]['eval_only'] is False and cleanup_pin is not None,
            'Only original TRAIN may rebind, with retained cleanup evidence')
    old = read_pin(previous)
    retired = read_pin(cleanup_pin)
    for event in (binding, old, retired):
        require(event['slot'] == slot and event['incarnation'] == 1
                and all(event[key] == fleet[key] for key in
                        ('epoch', 'supervisor', 'trainer', 'source_authority')),
                'Accepted rebind cleanup lineage differs')
    require(old['kind'] == binding['kind'] == 'physical-connection'
            and retired['kind'] == 'train-binding-retired'
            and retired['data']['previous_binding'] == previous
            and retired['data']['actor_not_replaced'] is True
            and retired['data']['actor_exit_or_game_completion_claimed'] is False
            and closed_connection(old['data']['connection'], retired['data']['cleanup'],
                                  fleet['trainer']['server_stamp']),
            'Accepted rebind lacks exact original old-token cleanup')
