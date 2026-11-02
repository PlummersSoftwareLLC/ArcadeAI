"""Unselected read-only main-fleet evidence collector and bounded replay validator.

Only the learning fleet may recover through its existing supervisor. This module
does not launch, signal, restart, change training, inspect game scores, or grant
any exception to private evaluator identities. Import and CLI default are inert.
Each immutable snapshot is intended to be joined to its original raw API wire
by a future, separately selected launch observer and closed reviewer.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

LIMITS = dict(max_missing_slots=1, recovery_s=45, total_recovery_s=120,
              max_recoveries=4, max_sample_gap_s=30, max_collection_s=5)
SLOTS = {str(slot) for slot in range(192)}
STATIC = ('parent_pid', 'cgroup', 'command', 'environment', 'affinity', 'uids', 'executable')
ENV_KEYS = {'LD_PRELOAD', 'LUA_PATH', 'LUA_CPATH', 'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def birth(value):
    return {key: value[key] for key in ('pid', 'starttime_ticks')}


def file_identity(path):
    stat = path.stat()
    return dict(device=stat.st_dev, inode=stat.st_ino, bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns, ctime_ns=stat.st_ctime_ns,
                mode=oct(stat.st_mode & 0o777), uid=stat.st_uid)


def process_stat(pid):
    try:
        data = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return dict(state=data[0], parent_pid=int(data[1]), starttime_ticks=int(data[19]))


def process_record(pid):
    directory = Path('/proc', str(pid))
    before = process_stat(pid)
    require(before is not None and before['state'] not in ('Z', 'X', 'x'),
            'Process vanished or is no longer live')
    command = [part.decode() for part in directory.joinpath('cmdline').read_bytes().rstrip(b'\0').split(b'\0')]
    environment = {}
    for item in directory.joinpath('environ').read_bytes().split(b'\0'):
        if b'=' not in item:
            continue
        raw_key, raw_value = item.split(b'=', 1)
        key = raw_key.decode()
        if key.startswith('ROBOTRON_') or key in ENV_KEYS:
            environment[key] = raw_value.decode()
    groups = directory.joinpath('cgroup').read_text().splitlines()
    require(len(groups) == 1 and groups[0].startswith('0::'), 'Unified exact process cgroup required')
    status = dict(line.split(':', 1) for line in directory.joinpath('status').read_text().splitlines() if ':' in line)
    executable = dict(path=os.readlink(directory/'exe'), identity=file_identity(directory/'exe'))
    affinity = sorted(os.sched_getaffinity(pid))
    uids = [int(part) for part in status['Uid'].split()]
    after = process_stat(pid)
    require(after is not None and all(before[key] == after[key] for key in ('parent_pid', 'starttime_ticks'))
            and after['state'] not in ('Z', 'X', 'x'), 'Process changed during identity capture')
    return dict(pid=pid, starttime_ticks=before['starttime_ticks'], parent_pid=before['parent_pid'],
                cgroup=groups[0][3:], command=command, environment=environment,
                affinity=affinity, uids=uids, executable=executable)


def unit_observation(owner):
    result = subprocess.run(['systemctl', '--user', 'show', owner['unit']],
                            capture_output=True, text=True, timeout=5)
    require(result.returncode == 0, 'Original main unit query failed')
    return dict(argv=['systemctl', '--user', 'show', owner['unit']], exit=result.returncode,
                stdout=result.stdout, stderr=result.stderr, process=process_record(owner['pid']))


def capture(trainer, fleet, previous):
    """Read one bracketed fleet census. A racing/corrupt capture never becomes success."""
    started_unix, started_mono = time.time(), time.monotonic()
    owners = dict(trainer=unit_observation(trainer), fleet=unit_observation(fleet))
    actors = {}
    directory = Path('/sys/fs/cgroup' + fleet['cgroup'])
    for item in directory.joinpath('cgroup.procs').read_text().splitlines():
        pid = int(item)
        try:
            command = Path('/proc', item, 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError):
            continue
        if not command or command[0] != b'/usr/games/mame':
            continue
        actor = process_record(pid)
        slot = actor['environment'].get('ROBOTRON_CLIENT_SLOT')
        require(slot in SLOTS and slot not in actors, 'Unknown or duplicate main actor slot')
        actors[slot] = actor
    probes = {}
    for slot, actor in previous.items():
        observed = process_stat(actor['pid'])
        probes[slot] = None if observed is None else observed['starttime_ticks']
    # Rejoin all claimed live births after the census and prior-birth probes.
    for actor in actors.values():
        actual = process_stat(actor['pid'])
        require(actual is not None and actual['starttime_ticks'] == actor['starttime_ticks']
                and actual['parent_pid'] == actor['parent_pid'] and actual['state'] not in ('Z', 'X', 'x'),
                'Actor changed across the bracketed census')
    return dict(schema='robotron-main-supervision-snapshot-v1',
                collection_started_unix_s=started_unix, collection_started_monotonic_s=started_mono,
                unix_s=time.time(), monotonic_s=time.monotonic(),
                owners=owners, actors=actors, previous_birth_probes=probes)


def validate_owner(claim, observation):
    require(observation['argv'] == ['systemctl', '--user', 'show', claim['unit']]
            and type(observation['exit']) is int and observation['exit'] == 0,
            'Exact original main unit observation required')
    require(observation['stderr'] == '', 'Unexpected main-unit query diagnostic')
    fields = {}
    for line in observation['stdout'].splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        require(key not in fields, 'Duplicate main-unit show field')
        fields[key] = value
    wanted = dict(Id=claim['unit'], MainPID=str(claim['pid']), InvocationID=claim['invocation_id'],
                  NRestarts='0', ActiveState='active', SubState='running', ControlGroup=claim['cgroup'])
    require(all(fields.get(key) == value for key, value in wanted.items()), 'Trainer or fleet unit changed')
    process = observation['process']
    require(birth(process) == birth(claim) and process['cgroup'] == claim['cgroup']
            and process['uids'] == [os.getuid()] * 4, 'Trainer or supervisor birth/owner/cgroup changed')


def validate_actor(slot, actor, original, fleet, contract):
    require(type(actor['pid']) is int and actor['pid'] > 0
            and type(actor['starttime_ticks']) is int and actor['starttime_ticks'] > 0,
            'Positive exact actor birth required')
    require(all(actor[key] == original[key] for key in STATIC),
            'Main actor role, command, environment, affinity, uid or executable changed')
    require(actor['parent_pid'] == fleet['pid'] and actor['cgroup'] == fleet['cgroup']
            and actor['uids'] == [os.getuid()] * 4 and actor['affinity']
            and actor['command'][0] == actor['executable']['path'] == '/usr/games/mame'
            and actor['environment']['ROBOTRON_CLIENT_SLOT'] == slot
            and actor['environment']['ROBOTRON_SOCKET_ADDRESS'] == 'dell:9998'
            and actor['environment']['ROBOTRON_EVAL_MODE'] == contract['eval_mode']
            and actor['command'].count('-autoboot_script') == 1
            and actor['command'][actor['command'].index('-autoboot_script') + 1] == contract['lua_path'],
            'Only the original supervisor may replace a matching training slot')


def validate_slot_contracts(policy):
    wanted = {str(slot) for slot in range(192)}
    contracts = policy['preview_slot_contracts']
    overrides = policy['preview_override_slots']
    require(type(overrides) is list and all(type(slot) is int and 0 <= slot < 192 for slot in overrides)
            and overrides == sorted(set(overrides)), 'Exact declared override subset required')
    require(set(contracts) == wanted and set(policy['preview_input_roles']) == wanted,
            'Exact192 source/role contracts required')
    require(policy['preview_input_lua']['sha256'] == '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf'
            and policy['preview_target_lua']['sha256'] == '507f3f5a799d49791d2c6cbca3f4600167a166c4a410723d4d29225d18b6e0ab',
            'Exact original and accepted preview sources required')
    for slot, contract in contracts.items():
        require(set(contract) == {'slot','upgraded','actual_eval','eval_mode','lua_path','lua_sha256'}
                and type(contract['slot']) is int and str(contract['slot']) == slot
                and type(contract['actual_eval']) is bool
                and type(contract['upgraded']) is bool
                and type(policy['preview_input_roles'][slot]) is bool
                and contract['actual_eval'] == policy['preview_input_roles'][slot],
                'Exact per-slot source/actual-role contract required')
        upgraded = int(slot) in overrides
        expected = policy['preview_target_lua'] if upgraded else policy['preview_input_lua']
        mode = ('1' if contract['actual_eval'] else '2') if upgraded else '0'
        require(contract['upgraded'] == upgraded and contract['eval_mode'] == mode
                and (contract['lua_path'],contract['lua_sha256']) == (expected['path'],expected['sha256']),
                'Declared slot source or role differs')


def validate_policy(policy):
    validate_slot_contracts(policy)
    require(policy['schema'] == 'robotron-preview-declared-subset-supervision-policy-v1'
            and policy['limits'] == LIMITS and set(policy['baseline_actors']) == SLOTS
            and len({row['pid'] for row in policy['baseline_actors'].values()}) == 192
            and len(policy['held_hashes_sha256']) == 64,
            'Exact prospectively fixed 192-slot supervision policy required')
    require(policy['trainer']['pid'] != policy['fleet']['pid'], 'Separate trainer and original supervisor required')
    for slot, actor in policy['baseline_actors'].items():
        validate_actor(slot, actor, actor, policy['fleet'], policy['preview_slot_contracts'][slot])
    for role in ('trainer', 'fleet'):
        validate_owner(policy[role], policy['baseline_owners'][role])


def make_policy(main, fleet):
    """Explicit read-only preparation; does not publish or select this proposal."""
    require(len(main['actors']) == 192 and len(main['held_hashes']) == 196,
            'Current 192 actors and all 196 source/control holds required')
    previous = {str(actor['slot']): actor for actor in main['actors']}
    require(set(previous) == SLOTS, 'Exactly the known current main slot registry required')
    snapshot = capture(main['owner'], fleet, previous)
    require(set(snapshot['actors']) == SLOTS, 'Policy must begin at full live capacity')
    for slot, actor in previous.items():
        actual = snapshot['actors'][slot]
        require(birth(actor) == birth(actual) and actor['mask'] == actual['affinity'],
                'Cannot prepare a policy around an unverified main transition')
    policy = dict(schema='robotron-main-supervision-policy-v1', limits=copy.deepcopy(LIMITS),
                  trainer=copy.deepcopy(main['owner']), fleet=copy.deepcopy(fleet),
                  baseline_actors=snapshot['actors'], baseline_owners=snapshot['owners'],
                  held_hashes_sha256=hashlib.sha256(json.dumps(main['held_hashes'], sort_keys=True,
                      separators=(',', ':')).encode()).hexdigest())
    validate_policy(policy)
    validate_snapshot(policy, snapshot, 192)
    return policy, snapshot


def collect(policy, state=None):
    validate_policy(policy)
    previous = policy['baseline_actors'] if state is None else state['registry']
    return capture(policy['trainer'], policy['fleet'], previous)


def validate_snapshot(policy, snapshot, api_client_count, state=None):
    """Pure replay: return a new state; reject unexplained or over-budget changes.

    An outage is conservatively charged from the preceding accepted observation,
    including an already-recovered replacement first seen at this observation.
    Only one missing/reconnecting slot is permitted at a time, four distinct slots
    per study, at most45s each and120s total. A study must finish at full capacity.
    """
    validate_policy(policy)
    require(snapshot['schema'] == 'robotron-main-supervision-snapshot-v1'
            and type(api_client_count) is int and api_client_count in (191, 192),
            'Unknown main census or unexpected/extra API connections')
    now, unix = snapshot['monotonic_s'], snapshot['unix_s']
    start_mono, start_unix = snapshot['collection_started_monotonic_s'], snapshot['collection_started_unix_s']
    require(all(finite(value) and value > 0 for value in (now, unix, start_mono, start_unix))
            and 0 <= now - start_mono <= LIMITS['max_collection_s']
            and 0 <= unix - start_unix <= LIMITS['max_collection_s'], 'Invalid or excessively slow census capture')
    require(set(snapshot['owners']) == {'trainer', 'fleet'}, 'Both original main owners required')
    for role in ('trainer', 'fleet'):
        validate_owner(policy[role], snapshot['owners'][role])
        require(all(snapshot['owners'][role]['process'][key] == policy['baseline_owners'][role]['process'][key]
                    for key in STATIC), 'Original main owner process configuration changed')
    actors = snapshot['actors']
    require(set(actors) <= SLOTS and len(actors) >= 191
            and len({row['pid'] for row in actors.values()}) == len(actors),
            'At most one missing actor; unknown slots/duplicate PIDs forbidden')
    for slot, actor in actors.items():
        validate_actor(slot, actor, policy['baseline_actors'][slot], policy['fleet'], policy['preview_slot_contracts'][slot])
    previous = policy['baseline_actors'] if state is None else state['registry']
    probes = snapshot['previous_birth_probes']
    require(set(probes) == SLOTS, 'Every previously registered birth must be probed')
    changed = []
    for slot, original in previous.items():
        current = actors.get(slot)
        probe = probes[slot]
        require(probe is None or (type(probe) is int and probe > 0), 'Malformed previous-birth probe')
        if current is not None and birth(current) == birth(original):
            require(probe == original['starttime_ticks'], 'Unchanged actor probe contradicts census')
        else:
            require(probe != original['starttime_ticks'], 'Departed actor birth still exists')
            if current is not None:
                require(current['starttime_ticks'] > original['starttime_ticks'], 'Replacement birth did not advance')
            changed.append(slot)
    if state is None:
        require(not changed and api_client_count == 192, 'Initial observation must preserve all precommitted births')
        return dict(schema='robotron-main-supervision-state-v1', registry=copy.deepcopy(actors),
                    last_monotonic_s=now, last_unix_s=unix, pending=None,
                    used_slots=[], completed_episodes=[], total_recovery_s=0, total_recovery_wall_s=0,
                    full_capacity=True)
    require(state['schema'] == 'robotron-main-supervision-state-v1'
            and 0 < now - state['last_monotonic_s'] <= LIMITS['max_sample_gap_s']
            and 0 < unix - state['last_unix_s'] <= LIMITS['max_sample_gap_s'],
            'Main observation clock regressed or gap exceeded30 seconds')
    updated = copy.deepcopy(state)
    pending = updated['pending']
    if pending is None and changed:
        require(len(changed) == 1 and changed[0] not in updated['used_slots']
                and len(updated['used_slots']) < LIMITS['max_recoveries'],
                'Unexplained multiple, repeated-slot or excessive recoveries')
        slot = changed[0]
        pending = dict(slot=slot, departed=birth(previous[slot]), replacement=None,
                       started_monotonic_s=state['last_monotonic_s'], started_unix_s=state['last_unix_s'])
        updated['used_slots'].append(slot)
    if pending is not None:
        slot = pending['slot']
        require(set(changed) <= {slot}, 'Another actor changed during pending supervision')
        current = actors.get(slot)
        if current is not None:
            require(birth(current) != pending['departed'], 'Departed birth reappeared')
            if pending['replacement'] is None:
                pending['replacement'] = birth(current)
                updated['registry'][slot] = copy.deepcopy(current)
            else:
                require(birth(current) == pending['replacement'], 'Replacement itself changed during recovery')
        else:
            require(pending['replacement'] is None, 'Replacement exited during recovery')
        duration, wall = now - pending['started_monotonic_s'], unix - pending['started_unix_s']
        require(0 < duration <= LIMITS['recovery_s'] and 0 < wall <= LIMITS['recovery_s']
                and updated['total_recovery_s'] + duration <= LIMITS['total_recovery_s']
                and updated['total_recovery_wall_s'] + wall <= LIMITS['total_recovery_s'],
                'Supervised recovery duration or whole-study budget exceeded')
        if len(actors) == 192 and api_client_count == 192:
            require(pending['replacement'] is not None, 'Recovery lacks its supervised replacement')
            updated['completed_episodes'].append(dict(pending, ended_monotonic_s=now,
                ended_unix_s=unix, charged_s=duration, charged_wall_s=wall))
            updated['total_recovery_s'] += duration
            updated['total_recovery_wall_s'] += wall
            pending = None
    else:
        require(len(actors) == 192 and api_client_count == 192,
                'Connection loss without a departed supervised actor is not covered')
    updated.update(pending=pending, last_monotonic_s=now, last_unix_s=unix,
                   full_capacity=pending is None and len(actors) == api_client_count == 192)
    return updated


def validate_closed(state):
    require(state['pending'] is None and state['full_capacity'] is True,
            'Closed quality study must end with all 192 registered actors and connections restored')
    return dict(recoveries=len(state['completed_episodes']), charged_recovery_s=state['total_recovery_s'],
                charged_recovery_wall_s=state['total_recovery_wall_s'], full_capacity=True)


if __name__ == '__main__':
    print('PLAN_ONLY: unselected main-fleet proposal; no reads, queries, outputs or runtime changes')
