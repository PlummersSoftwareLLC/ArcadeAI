"""One bounded policy-free emulator trace; default invocation is inert.

Uses a private custom socket, never trainer ports9998/9999 or a quality journal.
The clock acknowledgement is reconstructed from the raw producer snapshot and
retained alongside it. It is not a scientific ROM/start certificate.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import stat
import struct
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
CLOCK_SHA = 'e5ff6fac134c8c9a6ff3b7ddc8d5ddb8f9eae0bafa183107284553649752eb54'
RESPONSE = struct.Struct('>4sIBB32s')
ZERO = bytes(32)


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path):
    p = Path(path)
    before = identity(p.stat())
    with p.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    require(identity(p.stat()) == before, 'Input changed during hashing')
    return dict(path=str(p), sha256=sha, bytes=before['bytes'], identity=before)


def put(path, value):
    with Path(path).open('xb') as stream:
        stream.write((json.dumps(value, indent=2, allow_nan=False) + '\n').encode())
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    return pin(path)


def checked(entry):
    require(pin(entry['path']) == entry, 'Selected original input changed')
    return Path(entry['path'])


def clock_module():
    path = HERE/'startup_response_clock_v1.py'
    require(pin(path)['sha256'] == CLOCK_SHA, 'Consumed clock component source changed')
    spec = importlib.util.spec_from_file_location('_gated_start_clock', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recv_exact(sock, count):
    chunks = []
    remaining = count
    while remaining:
        chunk = sock.recv(remaining)
        require(chunk, 'Original connection ended before complete frame')
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)


def read_frame(sock):
    size, = struct.unpack('>I', recv_exact(sock, 4))
    require(0 < size <= 2048, 'Original producer frame exceeds bound')
    return recv_exact(sock, size)


def schedule(sequence):
    return int(768 <= sequence < 771), int(750 <= sequence < 753)


class Protocol:
    def __init__(self, session, connection, admission_open_ns, admission_close_ns, emit):
        self.session, self.connection = session, connection
        require(all(type(v) is str and len(v) == 32 and
                    all(c in '0123456789abcdef' for c in v)
                    for v in (session, connection)), 'Bound original identities required')
        self.open, self.close, self.emit = admission_open_ns, admission_close_ns, emit
        self.sequence = 0
        self.nonce = ZERO
        self.clock = None
        self.bracket = None
        self.module = clock_module()

    def process(self, raw, send):
        require(self.sequence < 1200, 'Original frame capacity exhausted')
        row = self.module.decode(raw)
        sequence = self.sequence + 1
        require(row.get('schema') == 'robotron-gated-start-trace-v1' and row.get('kind') == 'snapshot'
                and row.get('session') == self.session and row.get('connection') == self.connection
                and type(row.get('slot')) is int and row['slot'] == 4096
                and type(row.get('sequence')) is int and row['sequence'] == sequence,
                'Original producer identity/frame differs')
        for key in ('status', 'wave', 'reserves', 'player_count', 'current_player', 'credit'):
            require(type(row.get(key)) is int and 0 <= row[key] <= 255, 'Malformed raw snapshot')
        require(type(row.get('score_hex')) is str and len(row['score_hex']) == 8
                and all(c in '0123456789abcdef' for c in row['score_hex']), 'Raw score bytes differ')
        previous_start, previous_coin = schedule(sequence - 1)
        require(type(row.get('last_start')) is int and row['last_start'] == previous_start
                and type(row.get('last_coin')) is int and row['last_coin'] == previous_coin,
                'Prior actually-applied input differs from fixed schedule')
        require(row.get('nonce') == self.nonce.hex(), 'Original nonce echo differs')
        for key in ('last_apply_ok', 'last_socket_ok'):
            require(type(row.get(key)) is bool and row[key] is (sequence > 1), 'Prior exchange/apply failed')
        for key in ('accepted_site_count', 'accepted_site_sequence', 'initialized_sequence', 'first_play_sequence'):
            require(type(row.get(key)) is int and -1 <= row[key] <= 1200, 'Malformed marker sequence')
        require(0 <= row['accepted_site_count'] <= 1, 'Repeated distinguished START setup')
        self.emit(dict(kind='request', sequence=sequence, received_monotonic_ns=time.monotonic_ns(),
                       payload_hex=raw.hex()))
        if self.clock is not None and self.bracket is None and row['accepted_site_count'] == 1:
            accepted, initialized = row['accepted_site_sequence'], row['initialized_sequence']
            if 768 <= accepted < sequence and accepted < initialized <= sequence:
                require(row['first_play_sequence'] == -1 or initialized < row['first_play_sequence'],
                        'Initialization was not witnessed before play')
                ack = dict(schema='robotron-startup-clock-ack-v1', nonce=row['nonce'],
                           **self.clock.binding, snapshot_frame=sequence,
                           socket_ok=row['last_socket_ok'], apply_ok=row['last_apply_ok'],
                           debug_bypass=False, held_start_before_response=False)
                self.bracket = self.clock.receive_snapshot(
                    lambda: (json.dumps(ack)+'\n').encode(), connection=self.connection)
                self.emit(dict(kind='clock_bracket', bracket=self.bracket,
                               raw_producer_sequence=sequence, no_ROM_certificate=True))
        start, coin = schedule(sequence)

        def send_response(nonce):
            response = RESPONSE.pack(b'RSC1', sequence, start, coin, nonce)
            self.emit(dict(kind='response_before_send', sequence=sequence,
                           response_hex=response.hex(), host_monotonic_ns=time.monotonic_ns()))
            result = send(response)
            require(result is None, 'Actual complete sendall required')
            self.emit(dict(kind='response_send_complete', sequence=sequence,
                           host_monotonic_ns=time.monotonic_ns()))

        if sequence == 768:
            self.clock = self.module.ResponseClock(session=self.session, connection=self.connection,
                slot=4096, epoch=1, exchange=768, frame=768,
                checkpoint_sha256='0'*64, generation=1,
                admission_open_ns=self.open, admission_close_ns=self.close)

            def authorize(raw_token):
                token = self.module.decode(raw_token)
                self.nonce = bytes.fromhex(token['nonce'])
                self.emit(dict(kind='original_start_token', token=token,
                               actual_policy_loaded=False, nonce_is_transport_join_only=True))
                send_response(self.nonce)

            self.clock.send_response(authorize)
        else:
            send_response(self.nonce)
        self.sequence = sequence


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


def terminate_owned(child, original_birth):
    if child.poll() is not None:
        return child.returncode
    require(birth(child.pid) == original_birth, 'Refuse to signal a changed original birth')
    child.terminate()
    end = time.monotonic()+10
    while child.poll() is None and time.monotonic() < end:
        time.sleep(0.05)
    # Unknown completion is retained; no SIGKILL or success substitution.
    return child.poll()


def run(job, job_pin):
    require(job['schema'] == 'robotron-gated-start-trace-original-v1'
            and job['limit'] == 1200 and job['start_sequence'] == 768
            and job['port'] == 19997 and job['admission_s'] == 90
            and job['wall_limit_s'] == 120, 'Exact new diagnostic scope required')
    for entry in [job['runtime'], job['lua'], job['mame'], *job['rom_inputs']]:
        checked(entry)
    output = Path(job['output'])
    output.mkdir(mode=0o700)
    for name in ['cfg', 'nvram', 'inp', 'sta', 'snap', 'mame-data', 'mame-config']:
        (output/name).mkdir(mode=0o700)
    lua_trace = output/'producer.jsonl'
    with lua_trace.open('xb'):
        pass
    boot = output/'boot.lua'
    boot.write_text('local ok,err=pcall(function() assert(loadfile('+json.dumps(job['lua']['path'])+'))().from_environment() end)\n'
                    'if not ok then print("GATED_START_DIAGNOSTIC_FATAL "..tostring(err));manager.machine:exit() end\n')
    actor_stdout, actor_stderr = output/'actor-stdout.txt', output/'actor-stderr.txt'
    child = None
    actor_birth = None
    stop_requested = threading.Event()
    errors = []
    protocol = None
    old_term = signal.signal(signal.SIGTERM, lambda *_: stop_requested.set())
    started = time.monotonic()
    try:
        with socket.socket() as listener, (output/'server.jsonl').open('xb') as server_file:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            listener.bind(('127.0.0.1', job['port']))
            listener.listen(1)
            listener.settimeout(15)
            open_ns = time.monotonic_ns()
            close_ns = open_ns + 90_000_000_000

            def emit(row):
                raw = (json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n').encode()
                require(len(raw) <= 8192 and server_file.tell()+len(raw) <= 12*1024*1024,
                        'Bounded server witness exceeded')
                server_file.write(raw)
                server_file.flush()

            protocol = Protocol(job['session'], job['connection'], open_ns, close_ns, emit)
            emit(dict(kind='admission', open_ns=open_ns, close_ns=close_ns,
                      session=job['session'], connection=job['connection'], policy_loaded=False))

            def serve():
                try:
                    with listener.accept()[0] as sock:
                        sock.settimeout(5)
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        for _ in range(1200):
                            protocol.process(read_frame(sock), sock.sendall)
                except Exception as error:
                    errors.append(repr(error))

            worker = threading.Thread(target=serve, daemon=True, name='one-original-gated-start-server')
            worker.start()
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith('ROBOTRON_') and k not in ('LD_PRELOAD', 'PYTHONPATH')}
            env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', CUDA_VISIBLE_DEVICES='',
                       XDG_CONFIG_HOME=str(output/'mame-config'), XDG_DATA_HOME=str(output/'mame-data'),
                       ROBOTRON_GATED_TRACE_PATH=str(lua_trace),
                       ROBOTRON_GATED_TRACE_ADDRESS='127.0.0.1:'+str(job['port']),
                       ROBOTRON_GATED_TRACE_SLOT='4096', ROBOTRON_GATED_TRACE_SESSION=job['session'],
                       ROBOTRON_GATED_TRACE_CONNECTION=job['connection'])
            argv = [job['mame']['path'], 'robotron', '-rompath', job['rompath'], '-noreadconfig',
                    '-nocheat', '-noplugins', '-nothrottle', '-sound', 'none', '-video', 'none',
                    '-skip_gameinfo', '-seconds_to_run', '60', '-autoboot_script', str(boot)]
            for option, name in [('cfg', 'cfg'), ('nvram', 'nvram'), ('input', 'inp'),
                                 ('state', 'sta'), ('snapshot', 'snap')]:
                argv.extend(['-'+option+'_directory', str(output/name)])
            with actor_stdout.open('xb') as out, actor_stderr.open('xb') as err:
                child = subprocess.Popen(argv, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                         env=env, cwd=output)
                actor_birth = birth(child.pid)
                require(actor_birth is not None, 'Original actor birth not captured')
                put(output/'original-actor.json', dict(pid=child.pid, starttime_ticks=actor_birth,
                    argv=argv, job=job_pin, admission_open_ns=open_ns, admission_close_ns=close_ns,
                    CUDA_VISIBLE_DEVICES='', policy_loaded=False))
                while child.poll() is None and time.monotonic()-started < 120 and not errors and not stop_requested.is_set():
                    time.sleep(0.05)
                if child.poll() is None:
                    errors.append('Original actor interrupted or exceeded precommitted wall bound')
                    terminate_owned(child, actor_birth)
                worker.join(20)
                require(not worker.is_alive(), 'Original server completion unknown')
                for stream in (out, err):
                    stream.flush()
                    os.fsync(stream.fileno())
            server_file.flush()
            os.fsync(server_file.fileno())
    except Exception as error:
        errors.append(repr(error))
        if child is not None and child.poll() is None:
            terminate_owned(child, actor_birth)
    finally:
        signal.signal(signal.SIGTERM, old_term)
    for entry in [job['runtime'], job['lua'], job['mame'], *job['rom_inputs']]:
        checked(entry)
    actor_exit = child.poll() if child is not None else None
    files = {}
    for name in ['producer.jsonl', 'server.jsonl', 'actor-stdout.txt', 'actor-stderr.txt', 'boot.lua']:
        path = output/name
        if path.exists():
            os.chmod(path, 0o444)
            files[name] = pin(path)
    try:
        rows = [json.loads(line) for line in lua_trace.read_bytes().splitlines()] if lua_trace.exists() else []
    except (ValueError, UnicodeError) as error:
        errors.append('Original producer log malformed: '+repr(error))
        rows = []
    footers = [v for v in rows if v.get('kind') == 'footer']
    complete = (actor_exit == 0 and not errors and protocol is not None and protocol.sequence == 1200
                and len(footers) == 1 and footers[0]['sequence'] == 1200 and footers[0]['failed'] is False
                and not any(v.get('kind') == 'fault' for v in rows))
    report = dict(schema='robotron-gated-start-trace-original-result-v1',
        status='COMPLETE_RAW_TRACE_NO_START_CERTIFICATE' if complete else 'ORIGINAL_DIAGNOSTIC_INCOMPLETE_NO_RETRY',
        original_actor_exit=actor_exit, errors=errors, complete=complete,
        original_frames=protocol.sequence if protocol else 0, files=files,
        clock_bracket=protocol.bracket if protocol else None,
        no_neural_policy_loaded=True, real_ROM_start_acceptance_proven=False,
        start_eligibility_changed=False, main_runtime_changed=False,
        learning_speed_gain_verified=False, original_attempt=1, no_retry=True)
    result = put(output/'result.json', report)
    print(json.dumps(dict(result=result, complete=complete, original_actor_exit=actor_exit)), flush=True)
    return 0 if complete else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, emulator, transport, source mutation or outputs')
        return 0
    require(args.job and args.job_sha256 and args.source_sha256, 'Explicit original bindings required')
    require(pin(__file__)['sha256'] == args.source_sha256, 'Actual runtime source differs')
    jp = pin(args.job)
    require(jp['sha256'] == args.job_sha256 and jp['identity']['mode'] == '0o444', 'Original job differs')
    return run(json.loads(Path(args.job).read_bytes()), jp)


if __name__ == '__main__':
    sys.exit(main())
