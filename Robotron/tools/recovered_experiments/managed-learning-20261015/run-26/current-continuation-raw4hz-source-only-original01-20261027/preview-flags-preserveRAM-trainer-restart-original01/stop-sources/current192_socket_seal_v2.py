"""Read-only TCP/native-thread ownership seal for frozen Robotron input.

No socket writes, process signals, cgroup writes or model imports. Only the
explicit backend may request a seal, after its supported pause and kernel holds.
"""
import os
from pathlib import Path
import re
import socket
import struct
import time


def require(value, message):
    if not value:
        raise RuntimeError(message)


def birth(pid, tid=None):
    path = Path('/proc', str(pid))
    if tid is not None:
        path = path/'task'/str(tid)
    try:
        value = (path/'stat').read_text()
    except FileNotFoundError:
        return None
    return int(value[value.rfind(')')+2:].split()[19])


def socket_inodes(pid):
    result = {}
    for fd in Path('/proc', str(pid), 'fd').iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        match = re.fullmatch(r'socket:\[(\d+)\]', target)
        if match:
            result.setdefault(int(match.group(1)), []).append(int(fd.name))
    return result


def endpoint(raw):
    host, port = raw.split(':')
    require(len(host) == 8 and len(port) == 4, 'Only an IPv4 trainer endpoint is selected')
    return (socket.inet_ntoa(struct.pack('=I', int(host, 16))), int(port, 16))


def tcp_rows(pid, port):
    result = []
    lines = Path('/proc', str(pid), 'net/tcp').read_text().splitlines()
    for line in lines[1:]:
        columns = line.split()
        require(len(columns) >= 10, 'Malformed kernel TCP table')
        local, peer = endpoint(columns[1]), endpoint(columns[2])
        if columns[3] != '01' or port not in (local[1], peer[1]):
            continue
        tx, rx = (int(x, 16) for x in columns[4].split(':'))
        result.append(dict(local=local, peer=peer, tx_bytes=tx, rx_bytes=rx,
                           inode=int(columns[9])))
    require(len({row['inode'] for row in result}) == len(result), 'Duplicate TCP inode')
    return result


def join_owned_connections(rows, server_inodes, client_inodes, *, port):
    """Join both ends, including all unexpected established trainer sockets."""
    server = [row for row in rows if row['local'][1] == port and row['inode'] in server_inodes]
    require(len(server) == len(client_inodes), 'Unexpected established trainer connection count')
    joined = []
    selected = set()
    for label, owned in client_inodes.items():
        clients = [row for row in rows if row['peer'][1] == port and row['inode'] in owned]
        require(len(clients) == 1, 'Each original input owner must own exactly one trainer socket: '+str(label))
        client = clients[0]
        peers = [row for row in server if row['local'] == client['peer'] and row['peer'] == client['local']]
        require(len(peers) == 1 and peers[0]['inode'] not in selected, 'TCP peer ownership is not one-to-one')
        selected.add(peers[0]['inode'])
        joined.append(dict(owner=label, client=client, server=peers[0]))
    require(selected == {row['inode'] for row in server}, 'An unowned trainer endpoint remains')
    require(len({v['client']['inode'] for v in joined}) == len(joined), 'A client socket has multiple claimed owners')
    return joined


def verify_waiting_threads(pid, candidates, probe, original_candidates):
    """Native TID and birth checks; a Linux truncated name is never identity."""
    waiting = {}
    for tid, value in candidates.items():
        if not value['wchan'].startswith('poll_schedule_timeout'):
            continue
        require(birth(pid, tid) == value['starttime_ticks'], 'Input wait TID was replaced')
        waiting[tid] = value
    require(len(waiting) == 193 and probe['tid'] in waiting
            and waiting[probe['tid']]['starttime_ticks'] == probe['starttime_ticks'],
            'Not all193 native input receive waits are established')
    require(set(waiting)-{probe['tid']} <= set(original_candidates), 'A new unknown native input waiter exists')
    for tid in set(waiting)-{probe['tid']}:
        require(waiting[tid]['starttime_ticks'] == original_candidates[tid]['starttime_ticks'],
                'An original native input waiter was replaced')
    return waiting


def seal(backend, context, probe, pause):
    b = backend
    require(b.accept_held and b.fleet_frozen, 'Input holds must precede the socket seal')
    actors = b.original_actors
    require(set(b.producer_roots) == set(b.producer_owners) == {'fleet','supplemental0'}
            and len({str(root) for root in b.producer_roots.values()}) == 2
            and all(b.producer_roots[key] == Path('/sys/fs/cgroup'+b.producer_owners[key]['cgroup'])
                    for key in b.producer_roots)
            and b.actor_owner_keys == {str(slot):('supplemental0' if slot == 0 else 'fleet')
                                      for slot in range(192)},
            'Exact191-plus-slot0 producer ownership required')
    require(len(actors) == 192 and {a['slot'] for a in actors} == set(range(192)), 'Original192 actor set differs')
    result = None

    def attempt():
        nonlocal result
        api = b.api()
        b.check_pause(api, pause)
        require(api['client_count'] == 193 and len(api['client_rows']) == 193,
                'A client changed before the frozen input seal')
        rows_by_slot = {row['client_slot']:row['client_id'] for row in api['client_rows']}
        require(len(rows_by_slot) == 193 and rows_by_slot.get(8191) == b.probe_id
                and all(rows_by_slot.get(s) == context['original192_rows'][s]['cid'] for s in range(192)),
                'Registered original client identities changed')
        for root in (b.listener_child, *b.producer_roots.values()):
            events = dict(line.split() for line in (root/'cgroup.events').read_text().splitlines())
            require(events.get('frozen') == '1', 'A selected kernel input hold was lost')
        require(set(map(int,(b.listener_child/'cgroup.threads').read_text().split())) == {b.listener['tid']}
                and birth(b.owner['pid'],b.listener['tid']) == b.listener['starttime_ticks'],
                'The listener hold contains another native thread')
        require(birth(b.owner['pid']) == b.owner['starttime_ticks'], 'Original trainer process changed')
        clients = {}
        for actor in actors:
            pid = actor['pid']
            require(birth(pid) == actor['starttime_ticks'] and sorted(os.sched_getaffinity(pid)) == actor['mask']
                    and Path('/proc',str(pid),'cgroup').read_text().strip() ==
                    '0::'+b.producer_owners[b.actor_owner_keys[str(actor['slot'])]]['cgroup'],
                    'Original actor process/affinity/cgroup changed')
            clients['slot-'+str(actor['slot'])] = socket_inodes(pid)
        own_socket = os.readlink(Path('/proc/self/fd',str(b.probe.fileno())))
        match = re.fullmatch(r'socket:\[(\d+)\]',own_socket)
        require(match is not None and b.probe.getsockname() == tuple(probe['local_endpoint'])
                and b.probe.getpeername() == tuple(probe['peer_endpoint']), 'Owned probe socket changed')
        clients['owned-probe'] = {int(match.group(1)): [b.probe.fileno()]}
        rows = tcp_rows(b.owner['pid'], 9998)
        connections = join_owned_connections(rows, socket_inodes(b.owner['pid']), clients, port=9998)
        # Frozen emulator receive queues may contain an action already sent.
        # Only bytes that can still reach the server are input producers.
        if any(v['server']['rx_bytes'] or v['client']['tx_bytes'] for v in connections):
            return False
        native = b.native_candidates()
        try:
            waiting = verify_waiting_threads(b.owner['pid'],native,b.probe_tid,b.original_native)
        except RuntimeError as error:
            if str(error) == 'Not all193 native input receive waits are established':
                return False
            raise
        result = dict(all193_socket_owners_verified=True, all193_receive_queues_empty=True,
            all193_handlers_waiting_for_input=True, server_receive_queue_scope=True,
            owned_probe=b.probe_tid, connections=connections, native_receive_waiters=waiting,
            native_candidate_superset=native, observed_unix_s=time.time(), runtime_changed=False)
        return True

    b.wait(attempt, 8, 'The original193 socket/native input seal did not settle')
    return result
