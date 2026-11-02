"""Prospective same-original-process TRAIN overlap checks; inert on import.

An authenticated overlap is pending, never an accepted physical census. Callers
must keep the existing ten-second deadline and require a later unique binding
with original-token cleanup before accepting another observation.
"""
from collections import defaultdict
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
