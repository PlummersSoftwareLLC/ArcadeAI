"""Four real loopback TCP cases for an unapplied private server copy."""
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
    path=Path(entry['path'])
    assert path.stat().st_size==entry['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
    return path


def wait_for(predicate, seconds=5):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.01)
    raise TimeoutError('Original private TCP case did not reach expected state')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY');return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
    raw=Path(args.job).read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256
    job=json.loads(raw);assert job['schema']=='robotron-private-real-TCP-peer-admission-job-v1'
    output=Path(job['output']);output.mkdir(mode=0o700)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    for entry in job['private_sources']:checked(entry)
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[name]='2'
    os.environ['ROBOTRON_DQN_MODEL_DIR']=str(output/'empty-model-directory')
    os.environ['ROBOTRON_DQN_CONTROL_PATH']=str(output/'absent-control.json')
    sys.path.insert(0,job['package_root'])
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    runtime=importlib.import_module('dqn.socket_server')
    config=importlib.import_module('dqn.config')
    assert Path(runtime.__file__).resolve()==checked(job['candidate_private_source'])
    assert torch.cuda.device_count()==0 and not torch.cuda.is_initialized()
    packet_bytes=checked(job['wire_packets']).read_bytes();packet=None
    assert len(packet_bytes)==1200*7597
    for index in range(1200):
        candidate=packet_bytes[index*7597:(index+1)*7597]
        fields=struct.unpack_from('>HddBIBBBIBBB',candidate)
        if fields[0]==1890 and fields[3]==0 and fields[5]==1 and fields[10]==1:
            packet=candidate;break
    assert packet is not None
    results=[]
    specs=[('strict_local_allowed','127.0.0.1',True,'127.0.0.1',True),
           ('strict_alias_rejected','127.0.0.2',True,'127.0.0.1',False),
           ('legacy_alias_allowed','127.0.0.2',True,None,True),
           ('inference_only_alias_allowed','127.0.0.2',False,'127.0.0.1',True)]
    for name,source_ip,replay_enabled,peers,admitted in specs:
        case=output/name;case.mkdir(mode=0o700)
        os.environ['ROBOTRON_RUN_DIR']=str(case/'journal')
        if peers is None:os.environ.pop('ROBOTRON_ALLOWED_TRAINING_PEERS',None)
        else:os.environ['ROBOTRON_ALLOWED_TRAINING_PEERS']=peers
        server=runtime.SocketServer('127.0.0.1',0,None,replay_enabled=replay_enabled)
        assert server.async_buffer is server.inference_batcher is None
        calls=dict(allocate=0,initialize=0)
        original_allocate,original_initialize=server._alloc_id,server._init_client
        def allocated():
            calls['allocate']+=1;return original_allocate()
        def initialized(cid):
            calls['initialize']+=1;return original_initialize(cid)
        server._alloc_id=allocated;server._init_client=initialized
        worker=threading.Thread(target=server.start,name='private-real-TCP-'+name)
        worker.start();client=None;handlers=[];reply=b'';remote=None
        try:
            wait_for(lambda:server.running and server.server_socket is not None)
            endpoint=server.server_socket.getsockname()
            assert endpoint[0]=='127.0.0.1' and endpoint[1]not in (9998,19998,*range(20000,20032))
            client=socket.socket(socket.AF_INET,socket.SOCK_STREAM);client.settimeout(3)
            client.bind((source_ip,0));client.connect(endpoint);remote=client.getsockname()
            if admitted:
                handshake=(0 if replay_enabled else 1)<<14
                client.sendall(struct.pack('>H',handshake)+struct.pack('>I',len(packet))+packet)
                while len(reply)<6:
                    part=client.recv(6-len(reply));assert part;reply+=part
                assert len(reply)==6 and calls==dict(allocate=1,initialize=1)
                wait_for(lambda:len(server.client_states)==1)
                with server.client_lock:
                    rows=list(server.client_states.values())
                    handlers=[thread for thread in server.clients.values() if isinstance(thread,threading.Thread)]
                assert len(rows)==1 and rows[0]['client_slot']==0 and rows[0]['proto_v2']is True
                assert rows[0]['replay_disabled']is (not replay_enabled)
            else:
                assert client.recv(1)==b''
                assert calls==dict(allocate=0,initialize=0) and not server.client_states and not server.clients
            results.append(dict(case=name,source_ip=source_ip,private_listener=endpoint,actual_peer=remote,
                replay_enabled=replay_enabled,configured_allowed_peers=peers,expected_admitted=admitted,
                allocation_calls=calls['allocate'],initialization_calls=calls['initialize'],
                actual_action_response_hex=reply.hex(),private_client_count=len(server.client_states)))
        finally:
            server.shutdown_event.set();server.stop()
            if client is not None:client.close()
            worker.join(5)
            for handler in handlers:handler.join(5)
        assert not worker.is_alive() and all(not handler.is_alive() for handler in handlers)
        assert not server.client_states and config.metrics.client_count==0
        probe=socket.socket(socket.AF_INET,socket.SOCK_STREAM);probe.settimeout(.2)
        try:assert probe.connect_ex(endpoint)!=0
        finally:probe.close()
        results[-1].update(all_original_server_handlers_stopped=True,private_listener_closed=True)
    assert not torch.cuda.is_initialized()
    report=dict(status='ORIGINAL_FOUR_REAL_LOOPBACK_TCP_CASES_PASSED',job_sha256=args.job_sha256,
        source_sha256=args.source_sha256,candidate_private_source=job['candidate_private_source'],cases=results,
        actual_constructor_accept_loop_handshake_frame_parser_and_action_response_executed=True,
        only_allocation_and_initialization_call_counters_wrapped=True,original_methods_called_by_wrappers=True,
        actual_policy_weights_loaded=False,CUDA_initialized=False,visible_CUDA_devices=0,
        production_source_changed=False,production_trainer_port_used=False,real_remote_client_touched=False,
        failed_scientific_case_requalified=False,
        limits=['Private full runtime with agent=None; no neural policy/replay worker or production handoff tested.',
                '127.0.0.2 represents an unselected real TCP source; actual192.168.1.13 was covered by prior synthetic guards.',
                'No change to existing local-slot/runtime validity checks or main listening socket.'])
    with(output/'report.json').open('x')as stream:
        json.dump(report,stream,separators=(',',':'),allow_nan=False);stream.write('\n')
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'],cases=len(results),report=str(output/'report.json'))),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
