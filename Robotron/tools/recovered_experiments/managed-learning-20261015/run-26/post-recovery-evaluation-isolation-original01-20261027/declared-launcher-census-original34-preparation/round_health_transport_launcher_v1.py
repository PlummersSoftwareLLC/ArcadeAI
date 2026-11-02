"""Join round retirement evidence to actual Linux TCP ownership.

This adds predicates to the pinned engineering reader. It does not change the
running reader, private evaluation protocol, or any training process. A caller
must preserve every accepted raw snapshot for independent replay; this module
alone does not qualify a scientific launch.
"""
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import socket
import sys
import time

BASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/round_main_health_launcher_v1.py')
BASE_SHA = '44371d76f1be25453050a1a508afb70325a86bcec965fe19fbd47a0ab3bf65ef'
PORT = 9998


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def base():
    require(hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA, 'Round reader source changed')
    name = '_pinned_round_transport_declared_launchers_v1'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, BASE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[name] = module
    return sys.modules[name]


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


def check_inputs(case, full=False):
    base().check_inputs(case, full=full)


def collect(case, previous=None):
    sample = None
    try:
        started = time.monotonic()
        module = base()
        sample = module.collect(case,previous=previous)
        processes = dict(trainer=sample['owners']['trainer']['process'], **sample['actors'])
        kernel = {}
        for name in ('tcp', 'tcp6'):
            kernel[name] = Path('/proc/net', name).read_text()
        rows = tcp_rows(kernel['tcp']) + tcp_rows(kernel['tcp6'], ipv6=True)
        inodes = {role: socket_inodes(process['pid']) for role, process in processes.items()}
        namespaces = {role: os.readlink('/proc/%d/ns/net' % process['pid'])
                      for role, process in processes.items()}
        for name in ('tcp', 'tcp6'):
            require(tcp_rows(Path('/proc/net', name).read_text(), ipv6=name == 'tcp6') ==
                    tcp_rows(kernel[name], ipv6=name == 'tcp6'), 'TCP roster raced capture')
        reader = module.linux()
        for process in processes.values():
            current = reader.process_stat(process['pid'])
            require(current is not None and current['starttime_ticks'] == process['starttime_ticks'],
                    'TCP owner birth changed during capture')
        require(time.monotonic() - started <= 5, 'Round and TCP census exceeded5s')
        sample['transport'] = dict(raw_tables=kernel, socket_inodes=inodes, namespaces=namespaces,
                                   collector_namespace=os.readlink('/proc/self/ns/net'))
        return sample
    except (OSError,ValueError,KeyError) as failure:
        if getattr(failure,'raw_snapshot',None) is not None:
            raise
        evidence=dict(stage='transport-capture',failure=repr(failure),partial_main_snapshot=sample)
        if 'kernel' in locals():evidence['partial_raw_TCP_tables']=kernel
        if 'inodes' in locals():evidence['partial_socket_inodes']=inodes
        raise base().launchers().CensusFailure(repr(failure),evidence) from failure


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


def validate(case, sample, previous=None):
    base().validate(case, sample, previous=previous)
    validate_transport(sample)
    api = sample['api']
    require(math.isclose(api['epsilon'], .1, rel_tol=0, abs_tol=1e-12)
            and math.isclose(api['expert_ratio'], .1, rel_tol=0, abs_tol=1e-12),
            'Live exploration controls changed')
    require(all(type(row['eval']) is bool and row['eval'] == case['slot_eval'][str(row['client_slot'])]
                for row in api['client_rows']), 'API evaluation role differs from the declared actor role')
    exposure = api['host_pipeline']['learning_exposure']
    require(all(exposure[key]['enabled'] is True for key in ('optimizer', 'replay')),
            'Learning exposure disabled')
    base().validate_optimizer_accounting(exposure['optimizer'])
    optimizer = exposure['optimizer']['total']
    replay = exposure['replay']
    require(replay['accepted_total'] == sum(replay['accepted_by_source_total'].values()) and
            replay['accepted_learner_total'] == sum(replay['accepted_by_source_total'][key]
                                                  for key in ('dqn', 'epsilon')),
            'Accepted experience attribution differs')
    if previous is not None:
        old = previous['api']['host_pipeline']['learning_exposure']
        require(all(value >= old['optimizer']['total'][key] for key, value in optimizer.items())
                and replay['accepted_total'] >= old['replay']['accepted_total']
                and replay['accepted_learner_total'] >= old['replay']['accepted_learner_total']
                and all(value >= old['replay']['accepted_by_source_total'][key]
                        for key, value in replay['accepted_by_source_total'].items()),
                'Learning exposure counters rolled back')
