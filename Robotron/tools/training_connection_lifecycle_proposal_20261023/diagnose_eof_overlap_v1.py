"""Private real-TCP observation of the unmodified training connection lifecycle."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import struct
import sys
import threading
import time


def checked(entry):
    p = Path(entry['path'])
    raw = p.read_bytes()
    assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
    return p


def wait_for(predicate, seconds=5):
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.01)
    raise TimeoutError('Private original lifecycle case did not reach expected state')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw = Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job = json.loads(raw)
    assert job['schema'] == 'robotron-private-training-EOF-overlap-job-v1'
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    output = Path(job['output']);output.mkdir(mode=0o700)
    for entry in job['private_sources']:
        checked(entry)
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):
        os.environ[name] = '2'
    os.environ['ROBOTRON_DQN_MODEL_DIR'] = str(output/'empty-model-directory')
    os.environ['ROBOTRON_DQN_CONTROL_PATH'] = str(output/'absent-control.json')
    sys.path.insert(0,job['package_root'])
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    runtime = importlib.import_module('dqn.socket_server')
    config = importlib.import_module('dqn.config')
    assert Path(runtime.__file__).resolve() == checked(job['private_socket_source'])
    assert torch.cuda.device_count() == 0 and not torch.cuda.is_initialized()
    packets = checked(job['wire_packets']).read_bytes()
    assert len(packets) == 1200*7597
    packet = None
    for index in range(1200):
        sample = packets[index*7597:(index+1)*7597]
        header = struct.unpack_from('>HddBIBBBIBBB',sample)
        if header[0] == 1890 and header[3] == 0 and header[5] == 1 and header[10] == 1:
            packet = sample;break
    assert packet is not None
    cases = []
    for name,new_slot in [('same_slot_after_old_EOF',131),('distinct_slot_after_old_EOF',132)]:
        case = output/name;case.mkdir(mode=0o700)
        os.environ['ROBOTRON_RUN_DIR'] = str(case/'journal')
        config.metrics.measurement_active = False
        config.metrics.measurement_generation = 0
        server = runtime.SocketServer('127.0.0.1',0,None,replay_enabled=True)
        assert server.async_buffer is server.inference_batcher is None
        old_port = None
        saw_EOF = threading.Event();release_cleanup = threading.Event()
        original_recv = server._recv_exact
        def delayed_EOF(sock,n,timeout_s=.5):
            data = original_recv(sock,n,timeout_s=timeout_s)
            if n == 4 and data == b'' and sock.getpeername()[1] == old_port:
                saw_EOF.set()
                assert release_cleanup.wait(10),'Private fixture cleanup delay expired'
            return data
        server._recv_exact = delayed_EOF
        worker = threading.Thread(target=server.start,name='private-original-EOF-'+name)
        worker.start();old = new = None;handlers=[]
        def connect_and_exchange(slot):
            client = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            client.settimeout(3);client.bind(('127.0.0.1',0))
            client.connect(endpoint)
            client.sendall(struct.pack('>H',(2<<14)|(slot<<1)|1)+struct.pack('>I',len(packet))+packet)
            reply = b''
            while len(reply) < 6:
                chunk = client.recv(6-len(reply));assert chunk;reply += chunk
            return client,reply
        try:
            wait_for(lambda:server.running and server.server_socket is not None)
            endpoint = server.server_socket.getsockname()
            assert endpoint[0] == '127.0.0.1' and endpoint[1] not in (9998,19998,*range(20000,20032))
            old,old_reply = connect_and_exchange(131)
            old_port = old.getsockname()[1]
            wait_for(lambda:len(server.client_states) == config.metrics.client_count == 1)
            old.shutdown(socket.SHUT_RDWR);old.close();old=None
            assert saw_EOF.wait(3),'Actual old TCP EOF was not observed'
            new,new_reply = connect_and_exchange(new_slot)
            with server.client_lock:
                rows = [dict(cid=cid,slot=cs['client_slot'],frames=cs['frames'])
                        for cid,cs in sorted(server.client_states.items())]
                handlers = [t for t in server.clients.values() if isinstance(t,threading.Thread)]
                overlap_count = config.metrics.client_count
            assert overlap_count == len(rows) == 2
            assert sorted(row['slot'] for row in rows) == sorted([131,new_slot])
            assert all(row['frames'] >= 1 for row in rows)
            release_cleanup.set()
            wait_for(lambda:len(server.client_states) == config.metrics.client_count == 1)
            with server.client_lock:
                surviving_slots = [row['client_slot'] for row in server.client_states.values()]
            assert surviving_slots == [new_slot]
            cases.append(dict(case=name,private_listener=endpoint,old_slot=131,new_slot=new_slot,
                actual_old_TCP_EOF_observed=True,only_fixture_change='Hold original recv return after EOF, before old-handler teardown; no production method body changed.',
                observed_overlap_rows=rows,observed_overlap_client_count=overlap_count,
                duplicate_slot_visible=(new_slot==131),old_action_response_hex=old_reply.hex(),
                new_action_response_hex=new_reply.hex(),count_after_old_cleanup=1,surviving_slots=surviving_slots))
        finally:
            release_cleanup.set()
            server.shutdown_event.set();server.stop()
            for client in (old,new):
                if client is not None:
                    client.close()
            worker.join(5)
            for handler in handlers:
                handler.join(5)
        assert not worker.is_alive() and all(not handler.is_alive() for handler in handlers)
        assert not server.client_states and config.metrics.client_count == 0
        probe = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            probe.settimeout(.2);assert probe.connect_ex(endpoint) != 0
        finally:
            probe.close()
        cases[-1].update(all_original_private_handlers_stopped=True,private_listener_closed=True)
    for entry in job['private_sources']:
        checked(entry)
    assert not torch.cuda.is_initialized()
    report = dict(schema='robotron-private-training-EOF-overlap-report-v1',
        status='TWO_REAL_TCP_CASES_REPRODUCE_DUPLICATE_REGISTRATION_ON_ORIGINAL_SOURCE',cases=cases,
        source_sha256=args.source_sha256,job_sha256=args.job_sha256,original_socket_source=job['original_socket_source'],
        private_socket_source=job['private_socket_source'],CUDA_initialized=False,visible_CUDA_devices=0,
        actual_policy_loaded=False,production_runtime_changed=False,scientific_original_retried=False,
        original_failure_exact_cause_proven=False,quality_qualified=False,prevention_implemented=False,
        limits=['Private server with agent=None; real TCP handshake/frame parsing/action reply, no replay worker or neural weights.',
                'Controlled old-EOF teardown delay reproduces an allowed overlap; actual failed193 snapshot had no per-socket ownership evidence.',
                'No MAME, cap75 ROM reset, production connection, failure requalification or proposed gate exception tested.'])
    with (output/'report.json').open('x') as stream:
        json.dump(report,stream,separators=(',',':'),allow_nan=False)
        stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'],cases=len(cases),report=str(output/'report.json'))),flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
