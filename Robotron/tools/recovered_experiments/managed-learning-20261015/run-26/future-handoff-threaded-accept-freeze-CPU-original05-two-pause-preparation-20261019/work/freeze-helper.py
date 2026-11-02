"""Private kernel test: isolate/freeze one accept thread, never the trainer.

The unchanged SocketServer.start body runs with explicit handler/agent doubles
on an ephemeral loopback port. All cgroup writes stay inside this original
bounded CPU test unit. An independent controller watchdog must be active.
"""
import argparse
import ast
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import queue
import select
import socket
import sys
import threading
import time
import traceback


SOCKET_SHA = '5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408'
UNIT_PREFIX = 'robotron-future-handoff-threaded-accept-freeze-CPU-original'


def require(value, message):
    if not value:
        raise AssertionError(message)


def starttime(path):
    raw = path.read_text()
    return int(raw[raw.rfind(')') + 2:].split()[19])


def fields(path):
    return dict(line.split() for line in path.read_text().splitlines())


def publish(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.005)
    return False


@contextmanager
def private_listener_hold(root, listener, work, ordinal):
    """The proposed ordering, restricted to this private CPU test's subtree."""
    require(root.name.startswith(UNIT_PREFIX) and root.name.endswith('.service'),
            'Only the test unit can be changed')
    require(root.stat().st_uid == os.getuid(), 'Test cgroup not owned by this user')
    parent_kind = (root/'cgroup.type').read_text().strip()
    require(parent_kind == 'domain' and not (root/'cgroup.subtree_control').read_text().strip(),
            'Only an empty-controller ordinary test domain is allowed')
    require(not any(p.is_dir() for p in root.iterdir()), 'Unexpected preexisting child cgroup')
    pid, tid = os.getpid(), listener.native_id
    task = Path('/proc', str(pid), 'task', str(tid))
    born = starttime(task/'stat')
    require(tid != pid and listener.is_alive(), 'Original live non-main thread required')
    relative = '/' + str(root.relative_to('/sys/fs/cgroup'))
    require((task/'cgroup').read_text().strip() == '0::' + relative,
            'Original thread not in the test parent domain')
    child = root/('listener-proof-' + str(ordinal))
    created = moved = False
    try:
        child.mkdir()
        created = True
        (child/'cgroup.type').write_text('threaded\n')
        require((root/'cgroup.type').read_text().strip() == 'domain threaded'
                and (child/'cgroup.type').read_text().strip() == 'threaded',
                'Actual threaded topology differs')
        require(pid in set(map(int, (root/'cgroup.procs').read_text().split())),
                'Test process resource domain changed')
        # Write before freezing: even a kernel that unexpectedly freezes the
        # whole process can be recovered by the separate original controller.
        publish(work/'freeze-attempts'/f'{ordinal}.json', dict(pid=pid,
            process_starttime_ticks=starttime(Path('/proc', str(pid), 'stat')),
            tid=tid, thread_starttime_ticks=born, child_path=str(child),
            root_path=str(root), deadline_monotonic_s=time.monotonic() + 8,
            original_unit=root.name))
        (child/'cgroup.freeze').write_text('1\n')
        require(wait_for(lambda: fields(child/'cgroup.events').get('frozen') == '1'),
                'Kernel did not acknowledge the empty frozen child')
        require(starttime(task/'stat') == born, 'Listener identity changed before move')
        (child/'cgroup.threads').write_text(str(tid) + '\n')
        moved = True
        require(wait_for(lambda: fields(child/'cgroup.events').get('frozen') == '1'),
                'Kernel did not acknowledge the frozen original listener')
        require((task/'cgroup').read_text().strip() == '0::' + relative + '/' + child.name,
                'Only the exact listener thread must enter the child')
        require(set(map(int, (child/'cgroup.threads').read_text().split())) == {tid},
                'Frozen threaded child contains an unexpected task')
        require((root/'cgroup.freeze').read_text().strip() == '0', 'Parent domain froze')
        yield dict(pid=pid, tid=tid, thread_starttime_ticks=born,
                   child=str(child), parent_type=(root/'cgroup.type').read_text().strip(),
                   frozen_events=fields(child/'cgroup.events'))
    finally:
        if created and child.exists():
            # Migrate the listener OUT while its child is still frozen. If it
            # is thawed first, an accept/fork can create a handler inheriting
            # the temporary child and defeat the single-thread cleanup proof.
            if moved and task.exists():
                require(starttime(task/'stat') == born, 'Refuse cleanup of a replaced TID')
                (root/'cgroup.threads').write_text(str(tid) + '\n')
                require((task/'cgroup').read_text().strip() == '0::' + relative,
                        'Original listener did not return to the parent')
            # A rejected freeze can have caught a handler born during the
            # migration. Cleanup is confined to this test process's exact
            # temporary child; returning its own threads does not signal them.
            for extra in map(int, (child/'cgroup.threads').read_text().split()):
                own_task = Path('/proc', str(pid), 'task', str(extra))
                require(own_task.exists(), 'Refuse a task outside the original test process')
                require((own_task/'cgroup').read_text().strip() == '0::' + relative + '/' + child.name,
                        'Extra task no longer belongs to the exact child')
                (root/'cgroup.threads').write_text(str(extra) + '\n')
            (child/'cgroup.freeze').write_text('0\n')
            require(wait_for(lambda: fields(child/'cgroup.events').get('frozen') == '0'),
                    'Original threaded child did not thaw')
            require(not (child/'cgroup.threads').read_text().strip(), 'Child still contains a task')
            child.rmdir()
            require((root/'cgroup.type').read_text().strip() == parent_kind,
                    'Parent did not return to its exact original domain type')


def execute(args):
    require(hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled(),
            'Use the actual free-threaded interpreter')
    require((args.work/'watchdog-ready.json').exists(), 'Independent watchdog not ready')
    raw = args.socket_source.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SOCKET_SHA, 'Held socket source changed')
    tree = ast.parse(raw)
    server_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
    start = next(n for n in server_node.body if isinstance(n, ast.FunctionDef) and n.name == 'start')
    namespace = dict(socket=socket, select=select, threading=threading,
                     time=time, traceback=traceback)
    exec(compile(ast.Module(body=[start], type_ignores=[]), str(args.socket_source), 'exec'), namespace)
    cgroup = Path('/proc/self/cgroup').read_text().strip()
    require(cgroup.startswith('0::/'), 'Unified cgroup required')
    root = Path('/sys/fs/cgroup' + cgroup[3:])
    require(root.name.startswith(UNIT_PREFIX), 'Do not touch another process cgroup')
    watchdog = json.loads((args.work/'watchdog-ready.json').read_bytes())
    require(watchdog['unit'] == root.name and watchdog['pid'] != os.getpid()
            and starttime(Path('/proc', str(watchdog['pid']), 'stat')) == watchdog['starttime_ticks'],
            'Exact independent watchdog owner is not live')
    args.work.joinpath('freeze-attempts').mkdir()
    reports, connections, threads = [], [], []
    stop_heartbeat = threading.Event()
    heartbeat = [0]

    class Server:
        start = namespace['start']

        def __init__(self):
            self.host, self.port = '127.0.0.1', 0
            self.shutdown_event = threading.Event()
            self.server_socket = None
            self.running = False
            self.client_lock = threading.Lock()
            self.clients = {}
            self.accepted = queue.Queue()
            self.identities = []
            self.errors = []

        def _alloc_id(self):
            return len(self.identities)

        def _init_client(self, cid):
            self.identities.append(cid)

        def handle_client(self, connection, cid):
            self.accepted.put(cid)
            try:
                connection.settimeout(.1)
                while not self.shutdown_event.is_set():
                    try:
                        data = connection.recv(32)
                    except socket.timeout:
                        continue
                    if not data:
                        break
                    connection.sendall(data)
            except OSError as error:
                if not self.shutdown_event.is_set():
                    self.errors.append(repr(error))
            finally:
                connection.close()

        def _fail_inference_only(self, reason):
            self.errors.append(reason)

        def stop(self):
            self.running = False
            self.shutdown_event.set()
            if self.server_socket:
                self.server_socket.close()

    namespace['SERVER_CONFIG'] = type('ServerConfig', (), dict(max_clients=16))()
    server = Server()
    listener = threading.Thread(target=server.start, name='ThreadedAcceptProof', daemon=True)
    threads.append(listener)

    def beat():
        while not stop_heartbeat.wait(.005):
            heartbeat[0] += 1

    heartbeat_thread = threading.Thread(target=beat)
    threads.append(heartbeat_thread)
    heartbeat_thread.start()

    def connect():
        client = socket.create_connection(server.server_socket.getsockname(), timeout=2)
        client.settimeout(2)
        connections.append(client)
        return client

    def echo(client, value):
        client.sendall(value)
        require(client.recv(len(value)) == value, 'Existing handler stopped responding')

    failure = None
    try:
        listener.start()
        require(wait_for(lambda: server.running), 'Actual listener did not start')
        first = connect()
        require(server.accepted.get(timeout=2) == 0, 'Initial connection not handled')
        echo(first, b'initial')
        with private_listener_hold(root, listener, args.work, 1) as held:
            before = heartbeat[0]
            echo(first, b'existing')
            pending = connect()
            try:
                server.accepted.get(timeout=.1)
                raise AssertionError('Frozen actual accept thread admitted another client')
            except queue.Empty:
                pass
            require(heartbeat[0] > before, 'Other process threads froze')
            require(server.identities == [0] and listener.is_alive(), 'Original listener changed')
            reports.append(dict(case='freeze_accept_only', **held,
                existing_handler_echo=True, unrelated_heartbeat_advanced=True,
                new_connection_stayed_unaccepted=True))
        require(server.accepted.get(timeout=2) == 1, 'Thawed actual accept thread did not resume')
        echo(pending, b'resumed')
        try:
            with private_listener_hold(root, listener, args.work, 2):
                echo(first, b'exception')
                raise RuntimeError('intentional fixture exception')
        except RuntimeError as error:
            require(str(error) == 'intentional fixture exception', 'Unexpected exception')
        require(not any(p.is_dir() for p in root.iterdir()), 'Exception cleanup left a child cgroup')
        third = connect()
        require(server.accepted.get(timeout=2) == 2, 'Exception cleanup did not restore accepting')
        echo(third, b'after-finally')
        reports.append(dict(case='exception_thaws_restores_thread_and_removes_child',
            exact_parent_domain_restored=(root/'cgroup.type').read_text().strip() == 'domain',
            original_listener_live=listener.is_alive(), new_connection_handled=True))
        require(not server.errors, 'Actual listener fixture reported an error: ' + repr(server.errors))
    except BaseException as error:
        failure = repr(error)
        traceback.print_exc()
    finally:
        stop_heartbeat.set()
        for client in connections:
            client.close()
        server.stop()
        for thread in threads:
            thread.join(5)
        for thread in list(server.clients.values()):
            thread.join(5)
        require(not any(t.is_alive() for t in threads + list(server.clients.values())),
                'Private test left an owned thread alive')
    require(not (args.work/'watchdog-triggered.json').exists(), 'External rescue occurred; proof invalid')
    require(not any(p.is_dir() for p in root.iterdir()), 'Test left a child cgroup')
    report = dict(status='PASS' if failure is None else 'FAIL', error=failure,
        cases=reports, kernel=os.uname().release, uid=os.getuid(),
        gil_enabled=sys._is_gil_enabled(), actual_original_start_body=True,
        socket_source_sha256=SOCKET_SHA, ephemeral_loopback_only=True,
        trainer_or_fleet_changed=False, watchdog_triggered=False,
        production_deployment_ready=False, original_parent_domain_restored=True,
        limitations=[
            'Tests the real kernel/cgroup control and original SocketServer.start only; handlers, inference and replay are doubles.',
            'A future production hold additionally needs the exact original accept-thread birth and source provenance, bounded rescue, proof that no shared application lock is held and independent producer/FIFO/bank verification.',
            'No live trainer thread, actor, cgroup or source is changed by this test.'
        ])
    publish(args.work/'CPU-report.json', report)
    return 0 if failure is None else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--socket-source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    return execute(args) if args.execute else print('PLAN_ONLY')


if __name__ == '__main__':
    raise SystemExit(main())
