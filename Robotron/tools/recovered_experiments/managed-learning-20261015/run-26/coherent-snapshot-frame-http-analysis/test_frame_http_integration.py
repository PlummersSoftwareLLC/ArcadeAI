"""One CPU subprocess integration of actual staged frame/HTTP/gate lifecycles.

Uses a writable copy of the sealed candidate, real replay/n-step/FIFO/settings,
actual SocketServer.handle_client and actual HTTP handler over Unix socketpairs.
Only inference is fake. No listener, MAME, optimizer or CUDA context is created.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]
EVIDENCE=GAME/'logs/managed-learning-20261015/run-26/coherent-snapshot-harness-analysis'
RECEIPT_SHA256='57c1c7acfc1d6eb74eb4176e7c0a6bbe43a289cec0c65eb30e80e1c163315620'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def require(value,message):
    if not value:raise AssertionError(message)


def wait_for(predicate,message,timeout=5):
    deadline=time.monotonic()+timeout
    while not predicate():
        if time.monotonic()>=deadline:raise TimeoutError(message)
        time.sleep(.005)


class SocketPairTransport:
    """Real socket I/O; omit the TCP-only latency option for AF_UNIX transport."""
    def __init__(self,connection):self.connection=connection
    def __getattr__(self,name):return getattr(self.connection,name)
    def fileno(self):return self.connection.fileno()
    def setsockopt(self,level,name,value):
        if (level,name)==(socket.IPPROTO_TCP,socket.TCP_NODELAY):return
        return self.connection.setsockopt(level,name,value)


def receive_exact(connection,count):
    result=b''
    while len(result)<count:
        part=connection.recv(count-len(result))
        require(part,'Unexpected EOF while receiving action')
        result+=part
    return result


def child(root,tmpfs):
    # The fresh parent environment is already private before these imports.
    require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CUDA must be hidden')
    require(not any(name=='dqn' or name.startswith('dqn.') for name in sys.modules),'Candidate imported too early')
    package=root/'private/Scripts/dqn'
    sys.path.insert(0,str(package.parent))
    import numpy as np
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    require(torch.cuda.device_count()==0 and not torch.cuda.is_initialized(),'CUDA must be invisible and uninitialized')
    from dqn import config
    cfg=config.RL_CONFIG
    for name,value in dict(memory_size=16,batch_size=4,min_replay_to_train=4,replay_tmpfs_dir=str(tmpfs),
        hof_enabled=False,ephof_enabled=False,interesting_replay_bank_size=16,
        inference_batching_enabled=False,n_step=3,replay_live_mmap=True,replay_flush_msync=True,
        use_torch_compile=False,replay_prefetch=False,ratchet_enabled=False).items():setattr(cfg,name,value)
    require(Path(config.MODEL_DIR)==root/'models' and config.learning_control.path==root/'control.json',
            'Import-time model/control paths escaped')
    config.game_settings.expert_pct=0
    config.game_settings.epsilon_pct=0
    config.game_settings.save()
    metrics=config.metrics
    metrics.training_enabled=False
    metrics.measurement_active=False
    metrics.ratchet_frozen=False
    from dqn import replay_buffer, socket_server, metrics_dashboard
    for name,module in list(sys.modules.items()):
        if name=='dqn' or name.startswith('dqn.'):
            require(Path(module.__file__).resolve().is_relative_to(package),'Candidate module escaped private copy: '+name)
    expected=json.loads((root/'source-manifest.json').read_text())
    require(all(sha(package/name)==record['sha256'] for name,record in expected.items()),'Private module source drift')
    memory=replay_buffer.PrioritizedReplayBuffer(16,cfg.state_size)
    ring=tmpfs/'wire-replay'
    require(memory.ensure_live_mmap(str(ring),verbose=False),'Private real mmap failed')
    memory._hof_dir=str(root/'models/private-hof')
    memory._ephof_dir=str(root/'models/private-ephof')
    frame_entered,release_frame=threading.Event(),threading.Event()
    save_entered,release_save=threading.Event(),threading.Event()
    remove_entered,release_remove=threading.Event(),threading.Event()
    trace=[]
    errors=[]
    threads=[]
    peers=[]

    class Agent:
        def __init__(self):self.memory=memory;self.calls=0
        def act(self,state,epsilon,locked_fire=None):
            require(state.shape==(cfg.state_size,) and np.isfinite(state).all(),'Invalid actual stacked model state')
            self.calls+=1
            if self.calls==4:
                frame_entered.set()
                require(release_frame.wait(10),'Test did not release in-flight frame')
            return 8,8,False
    # Execute actual candidate ingestion without constructing a network/agent.
    tree=ast.parse((package/'agent.py').read_text())
    definition=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='RainbowAgent')
    method=next(node for node in definition.body if isinstance(node,ast.FunctionDef) and node.name=='step')
    namespace=dict(RL_CONFIG=cfg,combine_action=socket_server.combine_action)
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(package/'agent.py'),'exec'),namespace)
    Agent.step=namespace['step']
    agent=Agent()
    server=socket_server.SocketServer('private-socketpair',0,agent)
    server.running=True  # No accept loop/listener; invoke the real frame handler.
    metrics.global_server=server
    consumer=server.async_buffer
    gate=server.snapshot_gate
    require(gate.enabled,'Proposed startup gate is not enabled')
    new_http_attempted=threading.Event()
    original_register=gate.register
    def traced_register(name):
        if threading.current_thread().name=='actual-http-after-close':new_http_attempted.set()
        return original_register(name)
    gate.register=traced_register
    cid=7
    server._init_client(cid)
    nstep=server.client_states[cid]['nstep']
    source=socket.socketpair()
    wire_client,wire_server=source
    wire_client.settimeout(5)
    peers.append(wire_client)

    def spawn(target,name):
        def run():
            try:target()
            except BaseException as error:errors.append((name,repr(error)))
        thread=threading.Thread(target=run,name=name,daemon=True)
        threads.append(thread)
        thread.start()
        return thread

    handler=threading.Thread(target=lambda:server.handle_client(SocketPairTransport(wire_server),cid),
                             name='actual-private-frame-handler',daemon=True)
    server.clients[cid]=handler
    threads.append(handler)
    handler.start()
    wire_client.sendall(struct.pack('>H',(2<<14)|(1<<1))) # Explicit non-eval, slot1.

    def send_frame(number):
        state=np.zeros(config.WIRE_PARAMS_COUNT,dtype='>f4')
        # Complete v2 Robotron wire frame: finite state, live player, wave1.
        header=struct.pack(socket_server._HDR_FMT_V2,config.WIRE_PARAMS_COUNT,0.,0.,0,
                           number*100,1,0,0,0,0,1,3)
        payload=header+state.tobytes()
        wire_client.sendall(struct.pack('>I',len(payload))+payload)

    def read_action():
        action=struct.unpack('>bbBBBB',receive_exact(wire_client,6))
        require(action[:2]==(-1,-1) and action[2]&15==socket_server._SRC_DQN,
                'Actual action packer/source differs')
        return action

    actual_save=config.game_settings.save
    def held_save(*args,**kwargs):
        if threading.current_thread().name=='actual-http-existing':
            save_entered.set()
            require(release_save.wait(10),'Test did not release admitted settings save')
        return actual_save(*args,**kwargs)
    config.game_settings.save=held_save
    http_handler=metrics_dashboard._make_handler(SimpleNamespace(metrics=metrics))

    def start_post(difficulty,name):
        client,connection=socket.socketpair()
        client.settimeout(5)
        peers.append(client)
        body=json.dumps(dict(difficulty=difficulty)).encode()
        request=b'POST /api/game_settings HTTP/1.0\r\nHost: private\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body
        def handle():
            try:http_handler(connection,('private',0),SimpleNamespace())
            finally:connection.close()
        thread=spawn(handle,name)
        client.sendall(request)
        return client,thread

    def response(client,thread):
        result=b''
        while True:
            part=client.recv(65536)
            if not part:break
            result+=part
        thread.join(5)
        require(not thread.is_alive(),'Actual HTTP handler did not finish')
        header,body=result.split(b'\r\n\r\n',1)
        require(b' 200 ' in header,'Actual HTTP handler failed: '+repr(result))
        return json.loads(body)

    first_done,second_done=threading.Event(),threading.Event()
    proofs={}
    def close_gate(owner,event):
        proofs[owner]=gate.close(owner,10)
        event.set()
    def is_closed():
        with gate._condition:return gate._closed
    def frame_parked():
        with gate._condition:return any(row['name']=='client:7' and row['parked'] for row in gate._workers.values())
    reset_ack=[]
    original_remove=consumer.remove_client
    def held_remove(client_id):
        with gate._condition:
            require(any(row['name']=='client:7' and not row['parked'] for row in gate._workers.values()),
                    'Disconnect cleanup lost gate membership before reset enqueue')
        trace.append('cleanup_entered_with_gate_membership')
        remove_entered.set()
        require(release_remove.wait(10),'Test did not release disconnect reset')
        event=original_remove(client_id)
        reset_ack.append(event)
        with gate._condition:
            require(any(row['name']=='client:7' for row in gate._workers.values()),
                    'Handler unregistered before accepting reset enqueue')
        trace.append('reset_enqueued_before_unregister')
        return event

    try:
        for number in (1,2,3):send_frame(number);read_action()
        require(agent.calls==3 and metrics.frame_count==0 and metrics.learner_frame_count==3,
                'Expected local frame batching before gate closure')
        send_frame(4)
        require(frame_entered.wait(5),'Actual handler never reached in-flight inference')
        existing_http,existing_thread=start_post(6,'actual-http-existing')
        require(save_entered.wait(5),'Actual HTTP transaction did not reach RAM-before-save boundary')
        settings_path=root/'models/game_settings.json'
        require(config.game_settings.difficulty==6 and json.loads(settings_path.read_text())['difficulty']==5,
                'Could not establish admitted RAM/disk transaction gap')
        first_close=spawn(lambda:close_gate('frame-http-first',first_done),'close-first-gate')
        wait_for(is_closed,'Gate did not begin closing')
        require(not first_done.is_set(),'Gate certified an unfinished frame/settings transaction')
        release_frame.set()
        read_action()
        wait_for(frame_parked,'Completed frame did not flush/park')
        require(metrics.frame_count==4 and metrics.learner_frame_count==4 and not first_done.is_set(),
                'Gate failed to await full admitted settings save after frame completed')
        release_save.set()
        require(response(existing_http,existing_thread)['difficulty']==6,'First actual settings POST differs')
        require(first_done.wait(5),'Gate did not close after settings transaction completed')
        first_close.join(5)
        require(proofs['frame-http-first']['parked_workers']==['client:7'],'Unexpected first boundary workers')
        require(consumer.barrier_async(timeout=1).wait(5),'Real replay FIFO did not drain accepted frame')
        require(len(memory)==1 and memory._adds_total==1 and int(memory.horizons[0])==3,
                'Actual parser/n-step/agent-step/FIFO did not persist one mature row')
        require(config.game_settings.snapshot()==json.loads(settings_path.read_text()),'Boundary settings RAM/disk differ')
        before=(metrics.frame_count,metrics.learner_frame_count,memory._adds_total,sha(settings_path))
        send_frame(5)
        waiting_http,waiting_thread=start_post(7,'actual-http-after-close')
        require(new_http_attempted.wait(5),'New actual HTTP request did not reach the closed gate')
        require(not select.select([wire_client,waiting_http],[],[],.1)[0],
                'Frame or new settings request replied through a closed gate')
        require(agent.calls==4 and before==(metrics.frame_count,metrics.learner_frame_count,memory._adds_total,sha(settings_path)),
                'Closed gate allowed frame/replay/counter/settings mutation')
        gate.open('frame-http-first')
        read_action()
        require(response(waiting_http,waiting_thread)['difficulty']==7,'Queued actual settings POST did not resume')
        require(consumer.barrier_async(timeout=1).wait(5),'Post-resume replay FIFO failed')
        require(agent.calls==5 and len(memory)==2 and len(nstep._deque)==2,'Expected two mature rows plus two pending tails')
        consumer.remove_client=held_remove
        wire_client.shutdown(socket.SHUT_WR)
        require(remove_entered.wait(5),'Actual disconnect did not enter reset cleanup')
        require(metrics.frame_count==5 and metrics.learner_frame_count==5,'Disconnect did not flush its last local frame')
        final_close=spawn(lambda:close_gate('frame-http-final',second_done),'close-disconnect-gate')
        wait_for(is_closed,'Final gate did not close')
        require(not second_done.wait(.1),'Gate certified cleanup before reset enqueue/unregister')
        release_remove.set()
        require(second_done.wait(5),'Final gate did not wait through real disconnect cleanup')
        final_close.join(5)
        handler.join(5)
        require(not handler.is_alive() and proofs['frame-http-final']['parked_workers']==[],
                'Exited handler retained/missed gate membership')
        require(consumer.barrier_async(timeout=1).wait(5) and reset_ack[0].is_set(),'FIFO reset acknowledgment missing')
        require(cid not in consumer._client_indices and cid not in consumer._episode_indices and cid not in server.client_states,
                'Disconnect left consumer/client replay history')
        require(len(memory)==2 and memory._adds_total==2 and len(nstep._deque)==2,
                'Disconnected pending n-step tails leaked additional replay writes')
        memory.save(str(ring),verbose=False)
        meta=np.load(ring/'_meta.npy',allow_pickle=False)
        require(tuple(meta[:2])==(2,2),'Final real persisted pointer/size differs')
        saved={path.name:sha(path) for path in ring.iterdir() if path.is_file()}
        # Exercise the actual delayed client-bookkeeping timer too. It must not
        # mutate persisted replay or learner/frame clocks after handler exit.
        timers=[thread for thread in threading.enumerate() if isinstance(thread,threading.Timer)]
        for timer in timers:timer.join(2)
        require(not any(timer.is_alive() for timer in timers),'Delayed bookkeeping timer did not finish')
        require((metrics.frame_count,metrics.learner_frame_count,memory._adds_total)==(5,5,2),
                'Post-save cleanup changed persisted clocks/replay')
        require(saved=={path.name:sha(path) for path in ring.iterdir() if path.is_file()},'Post-save cleanup changed replay files')
        require(not errors and not consumer.snapshot_command_failures and not consumer.dropped_steps,
                'Private real worker/consumer failed: '+repr(errors))
        require(not torch.cuda.is_initialized(),'CPU integration initialized CUDA')
        require(all(sha(package/name)==record['sha256'] for name,record in expected.items()),'Candidate code changed')
        return dict(status='PASS',frames=5,learner_frames=5,mature_replay_rows=2,pending_disconnected_tails=2,
            first_boundary=proofs['frame-http-first'],disconnect_boundary=proofs['frame-http-final'],
            actual_http_transactions=2,settings_difficulty=7,disconnect_trace=trace,
            post_save_replay_unchanged=True,post_save_clocks_unchanged=True,cuda_initialized=False,visible_cuda_devices=0,
            tcp_listeners_created=0,source_entries=len(expected),
            limitations=['Unix socketpair omits TCP_NODELAY/transport deadline behavior','Fake inference; no neural network/optimizer/model archive',
                         'No MAME/game timing or full trainer lifecycle','Disconnected pending n-step tails are omitted, not restored'])
    finally:
        release_frame.set();release_save.set();release_remove.set()
        for owner in ('frame-http-first','frame-http-final'):
            if gate.owned_by(owner):gate.open(owner)
        for peer in peers:
            try:peer.close()
            except OSError:pass
        server.running=False
        server.shutdown_event.set()
        for thread in threads:thread.join(5)
        server.stop()
        # stop() can return early when shutdown flags were already set, so
        # explicitly stop the captured actual consumer and assert liveness.
        if consumer.running:consumer.stop()
        require(not consumer._thread.is_alive(),'Actual consumer survived private cleanup')
        require(not any(thread.is_alive() for thread in threads),'Private integration thread survived cleanup')
        memory._wait_bank_writer(timeout=5)


class FrameHttpIntegrationTests(unittest.TestCase):
    def test_actual_frame_http_and_disconnect_share_snapshot_boundary(self):
        self.assertEqual(sha(EVIDENCE/'review-receipt.json'),RECEIPT_SHA256)
        record=json.loads((EVIDENCE/'candidate-source-manifest.json').read_text())['source_files']
        original={name:sha(EVIDENCE/'candidate-source/dqn'/name) for name in record}
        self.assertTrue(all(original[name]==item['sha256'] for name,item in record.items()))
        with tempfile.TemporaryDirectory(prefix='robotron-frame-http-') as temporary, \
             tempfile.TemporaryDirectory(prefix='robotron-frame-http-',dir='/dev/shm') as private_tmpfs:
            root=Path(temporary)
            package=root/'private/Scripts/dqn'
            shutil.copytree(EVIDENCE/'candidate-source/dqn',package)
            # Copies of sealed directories are read-only by default. Only the
            # fresh private tree is made writable for native sibling caches.
            for directory in [package,*[path for path in package.rglob('*') if path.is_dir()]]:directory.chmod(0o700)
            for name in ('models','journal','cache'):(root/name).mkdir()
            (root/'control.json').write_text('{"experiment":"cpu-frame-http-integration","lr_scale":0.5}\n')
            (root/'source-manifest.json').write_text(json.dumps(record))
            environment={name:os.environ[name] for name in ('PATH','HOME','USER','LOGNAME','LANG','LC_ALL','TZ') if name in os.environ}
            environment.update(CUDA_VISIBLE_DEVICES='',ROBOTRON_DQN_MODEL_DIR=str(root/'models'),
                ROBOTRON_DQN_CONTROL_PATH=str(root/'control.json'),ROBOTRON_RUN_DIR=str(root/'journal'),
                ROBOTRON_TRAIN_GPU='0',ROBOTRON_INFERENCE_GPU='0',DQN_COHERENT_SNAPSHOT='1',
                DQN_FRAME_STACK='4',DQN_N_STEP='3',DQN_REPLAY_PREFETCH='0',DQN_TORCH_COMPILE='0',
                DQN_EXACT_INFERENCE_GRAPHS='0',DQN_PARALLEL_STATE_FILL='0',
                OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',
                TORCH_HOME=str(root/'cache'),TORCH_EXTENSIONS_DIR=str(root/'cache'),TMPDIR=str(root/'cache'))
            process=subprocess.Popen([sys.executable,'-I','-B',str(Path(__file__).resolve()),'--cpu-child',
                '--root',str(root),'--tmpfs',private_tmpfs],cwd=root,env=environment,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
            try:
                output,_=process.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL) # Dedicated still-unreaped child group only.
                output,_=process.communicate()
                self.fail('Private CPU integration timed out:\n'+output)
            self.assertEqual(process.returncode,0,output)
            results=[line.removeprefix('INTEGRATION_RESULT=') for line in output.splitlines() if line.startswith('INTEGRATION_RESULT=')]
            self.assertEqual(len(results),1,output)
            result=json.loads(results[0])
            self.assertEqual(result['status'],'PASS')
            print('INTEGRATION_RESULT='+json.dumps(result,sort_keys=True))
        self.assertEqual(original,{name:sha(EVIDENCE/'candidate-source/dqn'/name) for name in record})
        self.assertEqual(sha(EVIDENCE/'review-receipt.json'),RECEIPT_SHA256)


if __name__=='__main__':
    if '--cpu-child' in sys.argv:
        parser=argparse.ArgumentParser()
        parser.add_argument('--cpu-child',action='store_true')
        parser.add_argument('--root',type=Path,required=True)
        parser.add_argument('--tmpfs',type=Path,required=True)
        arguments=parser.parse_args()
        value=child(arguments.root,arguments.tmpfs)
        print('INTEGRATION_RESULT='+json.dumps(value,sort_keys=True),flush=True)
    else:unittest.main()
