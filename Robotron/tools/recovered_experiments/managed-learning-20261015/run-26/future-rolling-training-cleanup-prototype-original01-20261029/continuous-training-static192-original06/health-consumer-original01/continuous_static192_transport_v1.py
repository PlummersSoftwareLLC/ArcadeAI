"""Prospective static192 continuous-main TCP/retired-API evidence.

Original complete Linux TCP ownership predicate is retained exactly. Raw API
is preserved; only a separately labelled retirement view can omit a cached row.
No import-time reads or actions. No runtime or scientific qualification implied.
"""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import sys
import time

BASE=Path(__file__).with_name('continuous_static192_health_v1.py')
BASE_SHA='6fcff86103d409a3646f523a6adf6a95cc9eabd3b0090826493aaa99a7b9fbcc'
PORT=9998

def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def endpoint(value, ipv6=False):
    address, port = value.split(':')
    raw = bytes.fromhex(address)
    # Linux prints each native-endian32-bit word, including IPv6 addresses.
    raw = b''.join(raw[i:i+4][::-1] for i in range(0, len(raw), 4))
    return [socket.inet_ntop(socket.AF_INET6 if ipv6 else socket.AF_INET, raw), int(port, 16)]


def tcp_rows(raw, ipv6=False):
    result = []
    for line in raw.splitlines()[1:]:
        fields = line.split()
        local, remote = endpoint(fields[1], ipv6), endpoint(fields[2], ipv6)
        if PORT not in (local[1], remote[1]) or fields[3] not in ('01', '0A'):
            continue
        result.append(dict(local=local, remote=remote, state=fields[3],
                           uid=int(fields[7]), inode=fields[9], ipv6=ipv6))
    return sorted(result, key=lambda row: (row['ipv6'], row['inode'], row['local'], row['remote']))


def socket_inodes(pid):
    result = set()
    for path in Path('/proc', str(pid), 'fd').iterdir():
        try:
            value = os.readlink(path)
        except FileNotFoundError:
            continue
        if value.startswith('socket:[') and value.endswith(']'):
            result.add(value[8:-1])
    return sorted(result)


def validate_transport(sample):
    transport = sample['transport']
    rows = tcp_rows(transport['raw_tables']['tcp']) + tcp_rows(transport['raw_tables']['tcp6'], ipv6=True)
    owners = transport['socket_inodes']
    require(set(owners) == {'trainer', *sample['actors']}, 'TCP owner census differs from actor census')
    require(set(transport['namespaces']) == set(owners) and
            all(value == transport['collector_namespace'] for value in transport['namespaces'].values()),
            'TCP evidence came from a different network namespace')
    require(all(not row['ipv6'] and row['uid'] == os.getuid() for row in rows),
            'Unexpected IPv6 or foreign-user training socket')
    listeners = [row for row in rows if row['state'] == '0A']
    require(len(listeners) == 1 and listeners[0]['local'] == ['0.0.0.0', PORT]
            and listeners[0]['inode'] in owners['trainer'], 'Original trainer listener ownership differs')
    server = [row for row in rows if row['state'] == '01' and row['local'][1] == PORT]
    clients = [row for row in rows if row['state'] == '01' and row['remote'][1] == PORT]
    require(all(row['inode'] in owners['trainer'] for row in server),
            'Connected training socket is not owned by the original trainer')
    api_slots = {str(row['client_slot']) for row in sample['api']['client_rows']}
    matched_server, matched_client = set(), set()
    for slot in sample['actors']:
        actor_rows = [row for row in clients if row['inode'] in owners[slot]]
        require(len(actor_rows) == (1 if slot in api_slots else 0),
                'Actor TCP connection differs from its API registration')
        for actor in actor_rows:
            peers = [row for row in server if row['local'] == actor['remote'] and row['remote'] == actor['local']]
            require(len(peers) == 1 and actor['inode'] not in matched_client
                    and peers[0]['inode'] not in matched_server, 'TCP endpoint join is missing or duplicated')
            matched_client.add(actor['inode'])
            matched_server.add(peers[0]['inode'])
    require(len(matched_server) == len(server) == len(matched_client) == len(clients) == len(api_slots),
            'Unknown or unregistered client connected to the training port')


def base():
    require(hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA, 'Selected continuous health source changed')
    name = '_prospective_continuous_static192_health_v1'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, BASE)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        sys.modules[name] = module
    return sys.modules[name]


def check_inputs(case, full=False):
    base().check_inputs(case, full=full)
    if full:
        base().registry().validate_case(case)


def anchor(case, previous, slot):
    require(previous is not None, 'Cached retired API needs a preceding accepted original census')
    if slot not in previous['actors']:
        proof = previous.get('retired_API_projection', {})
        require(proof.get('schema') == 'robotron-continuous-retired-API-evidence-v1'
                and slot in proof['entries'], 'No original accepted physical/registration retirement anchor')
        return copy.deepcopy(proof['entries'][slot]['anchor'])
    actor = previous['actors'][slot]
    rows = [r for r in previous['api']['client_rows'] if str(r['client_slot']) == slot]
    require(len(rows) == 1, 'Ambiguous previous original EVAL registration')
    raw = tcp_rows(previous['transport']['raw_tables']['tcp']) + tcp_rows(previous['transport']['raw_tables']['tcp6'], True)
    owned = previous['transport']['socket_inodes']
    clients = [r for r in raw if r['state'] == '01' and r['remote'][1] == PORT and r['inode'] in owned[slot]]
    require(len(clients) == 1, 'Previous EVAL lacks one original process-owned TCP connection')
    client = clients[0]
    servers = [r for r in raw if r['state'] == '01' and r['local'] == client['remote']
               and r['remote'] == client['local'] and r['inode'] in owned['trainer']]
    require(len(servers) == 1, 'Previous original trainer TCP peer missing')
    return dict(actor=copy.deepcopy(actor), API_row=copy.deepcopy(rows[0]),
                accepted_monotonic_s=previous['monotonic_s'], accepted_unix_s=previous['unix_s'],
                client=client, server=servers[0])


def collect(case, previous=None):
    sample = None; evidence = dict(stage='continuous-main-and-TCP')
    try:
        started = time.monotonic(); module = base(); sample = module.collect(case, previous)
        processes = dict(trainer=sample['owners']['trainer']['process'], **sample['actors'])
        kernel = {name: Path('/proc/net', name).read_text() for name in ('tcp', 'tcp6')}
        evidence['partial_raw_TCP_tables'] = kernel
        inodes = {key: socket_inodes(value['pid']) for key, value in processes.items()}
        evidence['partial_socket_inodes'] = inodes
        namespaces = {key: os.readlink('/proc/%d/ns/net' % value['pid']) for key, value in processes.items()}
        for name in ('tcp', 'tcp6'):
            require(tcp_rows(Path('/proc/net', name).read_text(), ipv6=name == 'tcp6') ==
                    tcp_rows(kernel[name], ipv6=name == 'tcp6'), 'TCP roster raced capture')
        reader = module.linux()
        for value in processes.values():
            current = reader.process_stat(value['pid'])
            require(current is not None and current['starttime_ticks'] == value['starttime_ticks'],
                    'TCP owner birth changed during capture')
        require(time.monotonic() - started <= 5, 'Continuous registry/physical/TCP capture exceeded5s')
        sample['transport'] = dict(raw_tables=kernel, socket_inodes=inodes, namespaces=namespaces,
                                   collector_namespace=os.readlink('/proc/self/ns/net'))
        extras = {str(r['client_slot']) for r in sample['api']['client_rows']} - set(sample['actors'])
        if extras:
            entries = {}
            for slot in sorted(extras):
                try:
                    entries[slot] = dict(anchor=anchor(case, previous, slot),
                                         PID_absence=sample['PID_absence'][slot])
                except (OSError, ValueError, KeyError) as error:
                    entries[slot] = dict(error=repr(error))
            sample['retired_API_projection'] = dict(schema='robotron-continuous-retired-API-evidence-v1', entries=entries)
        return sample
    except (OSError, ValueError, KeyError) as failure:
        if getattr(failure, 'raw_snapshot', None) is not None:
            raise
        evidence.update(failure=repr(failure), partial_main_snapshot=sample)
        raise base().CensusFailure(repr(failure), evidence) from failure


def project_API(case, sample, previous, partition):
    """Only absent naturally retired EVAL rows; never hide an active TRAIN."""
    reg = base().registry(); rows = sample['api']['client_rows']; actors = sample['actors']
    require(type(sample['api']['client_count']) is int
            and len(rows) == sample['api']['client_count'] <= 192,
            'Raw API count/list differs')
    identifiers = [r['client_id'] for r in rows]
    require(all(type(x) is int and x >= 0 for x in identifiers)
            and len(identifiers) == len(set(identifiers)), 'Duplicate/invalid live or cached CID')
    slots = [str(r['client_slot']) for r in rows]
    require(all(type(r['client_slot']) is int and 0 <= r['client_slot'] < 192
                and type(r['eval']) is bool and r['eval'] is case['slot_eval'][str(r['client_slot'])] for r in rows)
            and len(slots) == len(set(slots)), 'Unknown/duplicate slot or wrong role in raw API')
    for slot, row in zip(slots, rows):
        conn = reg.binding(case, slot, case['continuous']['original_slots'][slot]['connection_binding'],
                           case['continuous']['original_slots'][slot]['original_child'])
        require(row['client_id'] == conn['client_id'], 'Original fixed connection CID changed')
    extras = set(slots) - set(actors)
    require(extras <= partition['retiring'] | partition['closed'], 'Unknown extra API row is not a natural EVAL retirement')
    projected = sample
    if extras:
        require(previous is not None and sample['status']['epoch'] == previous['status']['epoch']
                and 0 <= sample['monotonic_s'] - previous['monotonic_s'] <= .5,
                'Retired cached-row exception exceeds original500ms accepted-proof TTL')
        require(0 <= sample['unix_s'] - sample['api']['ts'] <= .5
                and sample['capture_started_monotonic_s'] <= sample['capture_ended_monotonic_s'] <= sample['monotonic_s']
                and 0 <= sample['monotonic_s'] - sample['capture_started_monotonic_s'] <= .5,
                'Cached API/capture bracket is future or exceeds original500ms TTL')
        proof = sample.get('retired_API_projection', {})
        require(proof.get('schema') == 'robotron-continuous-retired-API-evidence-v1'
                and set(proof.get('entries', {})) == extras, 'No positive original retired API evidence')
        raw = tcp_rows(sample['transport']['raw_tables']['tcp']) + tcp_rows(sample['transport']['raw_tables']['tcp6'], True)
        for slot in sorted(extras):
            entry = proof['entries'][slot]
            require('error' not in entry and entry['anchor'] == anchor(case, previous, slot),
                    'Original accepted EVAL anchor changed')
            old = entry['anchor']; actor = old['actor']; prior = old['API_row']; row = rows[slots.index(slot)]
            original = case['continuous']['original_slots'][slot]['original_child']
            require(actor['pid'] == original['pid'] and actor['starttime_ticks'] == original['birth']
                    and row['client_id'] == prior['client_id'] and row['eval'] is prior['eval'] is True
                    and reg.number(row['connected_seconds']) >= reg.number(prior['connected_seconds']),
                    'Cached retired EVAL changed original physical/CID/registration role')
            natural, result = partition['naturals'][slot]
            require(0 <= sample['unix_s'] - reg.number(result['end_unix_s']) <= .5
                    and 0 <= sample['unix_s'] - sample['status']['slots'][slot]['natural_result']['identity']['mtime_ns']/1e9 <= .5,
                    'Original natural-result end/publication500ms expiry exceeded')
            probe = entry['PID_absence']
            require(probe == sample['PID_absence'][slot] and probe['absent'] is True
                    and probe['current_birth'] is probe['state'] is None
                    and probe['pid'] == original['pid']
                    and sample['capture_started_monotonic_s'] <= probe['before_monotonic_s']
                    <= probe['after_monotonic_s'] <= sample['capture_ended_monotonic_s'],
                    'Original retired API PID is live, reused, unobserved or out of capture bracket')
            require(slot not in sample['transport']['socket_inodes'] and slot not in sample['transport']['namespaces'],
                    'Retired actor still owns captured sockets')
            require(not any(r['state'] == '01' and (r['inode'] in (old['client']['inode'], old['server']['inode'])
                        or (r['local'], r['remote']) in ((old['client']['local'], old['client']['remote']),
                                                        (old['server']['local'], old['server']['remote']))) for r in raw),
                    'Original retired TCP pair remains established')
        projected = dict(sample); projected['api'] = dict(sample['api'])
        projected['api']['client_rows'] = [r for r in rows if str(r['client_slot']) not in extras]
        projected['api']['client_count'] = len(projected['api']['client_rows'])
        projected['projected_retired_API_slots'] = sorted(extras)
    active_api = {str(r['client_slot']) for r in projected['api']['client_rows']}
    require(active_api <= set(actors) and set(actors) - active_api <= partition['retiring'],
            'Actual API projection hides a missing live original TRAIN/EVAL')
    return projected


def validate(case, sample, previous=None):
    module = base(); partition = module.validate(case, sample, previous)
    projected = project_API(case, sample, previous, partition)
    validate_transport(projected)  # Exact original no-unmatched-TCP predicate.
    connections = sample['connections_capture']['value']['connections']
    fresh = {str(row['client_slot']): row for row in connections}
    raw = tcp_rows(sample['transport']['raw_tables']['tcp']) + tcp_rows(sample['transport']['raw_tables']['tcp6'], True)
    owners = sample['transport']['socket_inodes']
    for slot, connection in fresh.items():
        expected = connection['socket_endpoints']
        matches = [r for r in raw if r['state'] == '01' and r['inode'] in owners[slot]
                   and r['local'] == expected['peer'] and r['remote'] == expected['server']]
        require(len(matches) == 1, 'Fresh server connection token does not join this exact original process socket')
    api_slots = {str(r['client_slot']) for r in projected['api']['client_rows']}
    require(api_slots - set(fresh) <= partition['retiring'],
            'Live API registration lacks its current original handler/connection token')
    exposure = sample['api']['host_pipeline']['learning_exposure']
    optimizer = exposure['optimizer']['total']; replay = exposure['replay']
    require(replay['accepted_total'] == sum(replay['accepted_by_source_total'].values())
            and replay['accepted_learner_total'] == sum(replay['accepted_by_source_total'][k] for k in ('dqn', 'epsilon')),
            'Accepted experience attribution differs')
    if previous is not None:
        old = previous['api']['host_pipeline']['learning_exposure']
        require(all(v >= old['optimizer']['total'][k] for k, v in optimizer.items())
                and replay['accepted_total'] >= old['replay']['accepted_total']
                and replay['accepted_learner_total'] >= old['replay']['accepted_learner_total']
                and all(v >= old['replay']['accepted_by_source_total'][k]
                        for k, v in replay['accepted_by_source_total'].items()), 'Learning exposure counters rolled back')
    return dict(profile='STATIC_ORIGINAL192_NO_FAULT_ADOPTION', partition=partition['counts'],
                raw_API_unchanged=True, projected_retired_API_slots=projected.get('projected_retired_API_slots', []))


if __name__ == '__main__':
    print('SOURCE_ONLY_INERT_NO_READS_WRITES_PROBES_OR_ACTIONS')


