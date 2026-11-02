"""One original CPU/eager, policy-loaded MAME startup prefix; inert by default.

This is an integration diagnostic, not a full-game quality experiment. It uses
the unchanged selected profile06 actor, server, measurement and journal. Its
prefix ends intentionally and cannot supply a complete-game score or a gain.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from types import SimpleNamespace


def require(value,message):
    if not value:raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def pin(path):
    p=Path(path);before=identity(p.stat())
    with p.open('rb')as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    require(identity(p.stat())==before,'Bound input changed during read')
    return dict(path=str(p),sha256=sha,bytes=before['bytes'],identity=before)


def put(path,value):
    with Path(path).open('xb')as stream:
        stream.write((json.dumps(value,indent=2,allow_nan=False)+'\n').encode())
        stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return pin(path)


def checked(entry):
    require(pin(entry['path'])==entry,'Selected input differs: '+entry['path'])
    return Path(entry['path'])


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def package_inputs(entry):
    package=json.loads(checked(entry).read_bytes());root=Path(package['root'])
    require(package['source_count']==123 and len(package['files'])==123,'Exact profile06 closure required')
    result=[]
    for relative,sha in package['files'].items():
        path=root/relative
        require(path.resolve(strict=True).is_relative_to(root),'Package path escaped')
        value=pin(path)
        require(value['sha256']==sha and value['identity']['mode']=='0o444','Frozen package source differs')
        result.append(value)
    return root,result


def run(job,jp):
    require(job['schema']=='robotron-full-policy-startup-original-v1'
            and job['actor_slots']==[4096] and job['frames']==1200
            and job['origin_port']==19998 and job['proxy_port']==19997
            and job['device']=='cpu' and job['backend']=='eager' and job['cpu_threads']==2
            and job['admission_s']==90 and job['wall_limit_s']==120,
            'Exact original diagnostic scope required')
    require(not os.environ.get('LD_PRELOAD'),'Never preload the Python policy process')
    for entry in job['inputs']:checked(entry)
    root,package_pins=package_inputs(job['source_package'])
    output=Path(job['output'])
    require(output.is_absolute()and not output.exists(),'Fresh exact output required')
    output.mkdir(mode=0o700)
    started=time.monotonic();deadline=started+job['wall_limit_s']
    stopped=threading.Event();bridge_stop=threading.Event();errors=[]
    previous={sig:signal.signal(sig,lambda *_:stopped.set())for sig in (signal.SIGTERM,signal.SIGINT)}
    child=None;actor_birth=None;actor=None;server=None;controller=None;proxy=None
    server_worker=None;proxy_worker=None;original_client_threads=[]
    boot_restore=None;policy_before=None;policy_after=None;before_stop=None;after_stop=None
    controller_exit=None;source_after=None;raw_files={};acquisition=None
    streams=[];listener=None
    try:
        # Configure process-global paths/device visibility before Torch imports.
        sidecar=load('_original_profile06_sidecar_defs',root/'tools/run_frozen_sidecar.py')
        sidecar.configure_environment(SimpleNamespace(directory=output,gpu_uuid=None,device='cpu',
            completion_policy='confirmed_reset_reserves_v1',game_boundary_diagnostics=True,cpu_threads=2))
        os.environ['ROBOTRON_ENABLE_RRCHRIS_PATCH']='0'
        sys.path.insert(0,str(root/'Scripts'))
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        import full_startup_proxy_v1 as bridge
        import startup_handoff_v1 as authority
        import torch
        import numpy as np
        from dqn import config
        from dqn.inference_actor import InferenceActor
        from dqn.managed_measurement import ManagedMeasurement
        from dqn.socket_server import SocketServer,parse_frame_data
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        checkpoint=output/'checkpoint.pt';source=checked(job['checkpoint'])
        with source.open('rb')as incoming,checkpoint.open('xb')as outgoing:
            shutil.copyfileobj(incoming,outgoing);outgoing.flush();os.fsync(outgoing.fileno())
            os.fchmod(outgoing.fileno(),0o444)
        acquisition=pin(checkpoint)
        require(acquisition['sha256']==job['checkpoint']['sha256'],'Acquired policy bytes differ')
        checked(job['checkpoint']);put(output/'original-acquisition.json',dict(source=job['checkpoint'],copy=acquisition))
        actor=InferenceActor(checkpoint,device='cpu',inference_backend='eager')
        metadata=actor.checkpoint_metadata
        for key in ('learner_frame_count','frame_count','measurement_frame_count'):
            setattr(config.metrics,key,int(metadata[key]))
        config.metrics.total_training_steps=actor.training_steps
        config.metrics.total_optimized_samples=actor.optimized_samples
        config.metrics.training_enabled=False;config.metrics.preview_capture_enabled=False
        config.metrics.hud_enabled=False
        for key,value in dict(start_advanced=False,start_level_min=1,epsilon_pct=0,
                              expert_pct=0,auto_curriculum=False,difficulty=5).items():
            setattr(config.game_settings,key,value)
        require(actor.checkpoint_sha256==acquisition['sha256']and actor.memory is actor.optimizer is None,
                'Actual acquired inference isolation differs')
        server=SocketServer('127.0.0.1',19998,actor,replay_enabled=False)
        def boundary(generation):
            result=server.measurement_boundary_status(generation)
            result['ready']=bool(result['ready']and result['clients']==1 and result['actor_slots']==[4096])
            return result
        controller=ManagedMeasurement(actor,config.metrics,server.game_journal,boundary_status=boundary)
        controller.enter(job['label'],cohort_s=90,timeout_s=120)
        # Operational eager warmup before MAME, with the same actual loaded policy.
        warmup=actor.act(np.zeros(actor.state_size,dtype=np.float32),epsilon=0.)
        require(actor.inference_error is None,'Actual eager policy warmup failed')
        policy_reader=authority.live_policy_reader(actor,config.metrics,server,config.game_settings,
            checkpoint_path=checkpoint,checkpoint_sha256=acquisition['sha256'],
            actor_source_sha256=job['actor_source_sha256'])
        policy_before=policy_reader()
        put(output/'original-loaded-policy.json',dict(policy=policy_before,warmup_action=warmup,
            inference_device=str(actor.inference_device),CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],
            replay_enabled=server.replay_enabled,memory_is_none=actor.memory is None,
            optimizer_is_none=actor.optimizer is None))
        require(os.environ['CUDA_VISIBLE_DEVICES']=='','CPU diagnostic must not allocate a GPU')
        def admission():
            if controller.start_ts is None:return None
            return dict(open_unix_ns=int(controller.start_ts*1e9),close_unix_ns=int(controller.close_ts*1e9),
                        generation=controller.generation,experiment=controller.label)
        for name in ('cfg','nvram','ini','inp','sta','snap','diff','share','comments','mame-data','mame-config'):
            (output/name).mkdir(mode=0o700)
        seed_runtime=load('_initialized_seed_restore_defs',checked(job['seed_runtime']))
        boot_restore=seed_runtime.restore_seed(job,output)
        builder=load('_original_profile06_wait_builder',root/'tools/build_socket_wait.py')
        library=builder.build(output/'socket-wait-build')
        library.chmod(0o444)
        put(output/'original-socket-wait-library.json',dict(library=pin(library),wait_us=1000,port=19997,
                                                          applies_only_to_original_MAME_child=True))
        trace=output/'producer.jsonl';trace.touch(mode=0o600)
        s=trace.stat();trace_identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(stat.S_IMODE(s.st_mode)),
                                         uid=s.st_uid,nlink=s.st_nlink)
        witness=(output/'proxy.jsonl').open('xb');streams.append(witness)
        def emit(value):
            raw=(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()
            require(len(raw)<=65536 and witness.tell()+len(raw)<=64*1024*1024,'Proxy witness bound exceeded')
            witness.write(raw);witness.flush()
        proxy=bridge.StartupProxy(server,slot=4096,session=job['session'],connection=job['connection'],
            trace_path=trace,trace_identity=trace_identity,rom_sha256=job['loaded_rom_sha256'],
            policy_reader=policy_reader,admission_reader=admission,frame_parser=parse_frame_data,
            emit=emit,stop_event=bridge_stop)
        server_worker=threading.Thread(target=server.start,name='original-frozen-origin',daemon=True)
        server_worker.start()
        ready_end=min(deadline,time.monotonic()+10)
        while not server.running:
            require(server_worker.is_alive()and time.monotonic()<ready_end,'Original origin failed to bind')
            time.sleep(.01)
        listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,0)
        listener.bind(('127.0.0.1',19997));listener.listen(1);listener.settimeout(15)
        def serve():
            try:
                with listener.accept()[0]as peer,socket.create_connection(('127.0.0.1',19998),timeout=5)as origin:
                    proxy.serve(peer,origin)
            except Exception as error:errors.append('Original proxy: '+repr(error))
        proxy_worker=threading.Thread(target=serve,name='original-full-observation-proxy',daemon=True)
        proxy_worker.start()
        boot=output/'boot.lua'
        with boot.open('x')as stream:
            stream.write('local ok,err=pcall(function() assert(loadfile('+json.dumps(job['lua']['path'])+'))() end)\n'
                         'if not ok then print("FULL_POLICY_STARTUP_FATAL "..tostring(err));manager.machine:exit() end\n')
        env={k:v for k,v in os.environ.items()if not k.startswith('ROBOTRON_')and k not in ('LD_PRELOAD','PYTHONPATH')}
        env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',CUDA_VISIBLE_DEVICES='',
            XDG_CONFIG_HOME=str(output/'mame-config'),XDG_DATA_HOME=str(output/'mame-data'),
            LD_PRELOAD=str(library),ROBOTRON_SOCKET_WAIT_US='1000',ROBOTRON_SOCKET_WAIT_PORT='19997',
            ROBOTRON_SOCKET_ADDRESS='127.0.0.1:19997',ROBOTRON_CLIENT_SLOT='4096',ROBOTRON_EVAL_MODE='1',
            ROBOTRON_PREVIEW_CLIENT='0',ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES='0',
            ROBOTRON_ENABLE_RRCHRIS_PATCH='0',ROBOTRON_FULL_STARTUP_TRACE=str(trace),
            ROBOTRON_FULL_STARTUP_SLOT='4096',ROBOTRON_FULL_STARTUP_SESSION=job['session'],
            ROBOTRON_FULL_STARTUP_CONNECTION=job['connection'])
        argv=[job['mame']['path'],'robotron','-rompath',job['rompath'],'-noreadconfig','-cheat',
            '-noplugins','-nothrottle','-sound','none','-video','none','-skip_gameinfo',
            '-seconds_to_run','60','-autoboot_script',str(boot),'-inipath',str(output/'ini')]
        for option,name in [('cfg','cfg'),('nvram','nvram'),('input','inp'),('state','sta'),
                            ('snapshot','snap'),('diff','diff'),('share','share'),('comment','comments')]:
            argv.extend(['-'+option+'_directory',str(output/name)])
        out=(output/'actor-stdout.txt').open('xb');err=(output/'actor-stderr.txt').open('xb')
        streams.extend([out,err])
        child=subprocess.Popen(argv,stdout=out,stderr=err,stdin=subprocess.DEVNULL,env=env,cwd=output)
        actor_birth=seed_runtime.birth(child.pid)
        require(actor_birth is not None,'Original actor birth was not captured')
        put(output/'original-actor.json',dict(pid=child.pid,starttime_ticks=actor_birth,argv=argv,job=jp,
            session=job['session'],connection=job['connection'],trace_identity=trace_identity,
            loaded_policy=policy_before,child_env={k:v for k,v in env.items()if k.startswith('ROBOTRON_')
                or k in ('SDL_VIDEODRIVER','SDL_AUDIODRIVER','CUDA_VISIBLE_DEVICES',
                         'XDG_CONFIG_HOME','XDG_DATA_HOME','LD_PRELOAD')},LD_PRELOAD_only_MAME=True))
        fixed_window=None
        while child.poll()is None:
            require(time.monotonic()<deadline and not stopped.is_set(),'Original diagnostic wall bound/interruption')
            require(not errors and proxy.error is None,'Original proxy failed')
            require(server_worker.is_alive()and server.running and server.inference_only_error is None,
                    'Original inference server failed')
            status=controller.tick()
            require(not status['complete'],'Original measurement became terminal during prefix')
            window=admission()
            if window is not None:
                if fixed_window is None:
                    fixed_window=window;put(output/'original-fixed-admission.json',window)
                require(window==fixed_window,'Original fixed admission moved')
            time.sleep(.01)
        require(child.returncode==0,'Original MAME actual exit differs')
        require(proxy.sent_complete.is_set()and proxy.sequence==1200,'Original full prefix was not sent')
        rows=[json.loads(line)for line in trace.read_bytes().splitlines()]
        footers=[r for r in rows if r.get('kind')=='footer']
        require(len(footers)==1 and footers[0]['sequence']==1200 and footers[0]['failed']is False
                and not any(r.get('kind')=='fault'for r in rows),'Original complete MAME footer differs')
        require(proxy.handoff is not None and footers[0]['first_play_sequence']>0,
                'No actual policy/journal/start/first-play integration')
        policy_after=policy_reader();require(policy_after==policy_before,'Actual policy or frozen clocks changed')
        before_stop=server.game_journal.cohort_status(controller.label,controller.start_ts,controller.close_ts)
        require(before_stop['started']==1 and before_stop['count']==0 and before_stop['pending']==1
                and before_stop['abandoned']==0,'Diagnostic must preserve exactly one incomplete pending game')
        put(output/'before-intentional-prefix-stop.json',dict(cohort=before_stop,controller=controller.status(),
            footer=footers[0],policy=policy_after,actual_MAME_exit=child.returncode,proxy_handoff=proxy.handoff))
    except Exception as error:
        errors.append(repr(error))
    finally:
        if child is not None and child.poll()is None:
            try:
                require(seed_runtime.birth(child.pid)==actor_birth,'Changed original actor birth; no signal')
                seed_runtime.terminate_owned(child,actor_birth)
            except Exception as error:errors.append('Original actor cleanup: '+repr(error))
        if server is not None:
            with server.client_lock:original_client_threads=list(server.clients.values())
            try:server.stop()
            except Exception as error:errors.append('Original server stop: '+repr(error))
        bridge_stop.set()
        if listener is not None:listener.close()
        for worker in [proxy_worker,server_worker,*original_client_threads]:
            if worker is not None:
                worker.join(10)
                if worker.is_alive():errors.append('Original thread completion unknown: '+worker.name)
        if server is not None and controller is not None and controller.start_ts is not None:
            after_stop=server.game_journal.cohort_status(controller.label,controller.start_ts,controller.close_ts)
        if server is not None and server.inference_only_error is not None:
            errors.append('Actual frozen server error: '+str(server.inference_only_error))
        if controller is not None:
            try:controller_exit=controller.exit()
            except Exception as error:errors.append('Original measurement exit: '+repr(error))
        if actor is not None:actor.close()
        for stream in streams:
            try:stream.flush();os.fsync(stream.fileno());stream.close()
            except Exception as error:errors.append('Original stream close: '+repr(error))
        for sig,handler in previous.items():signal.signal(sig,handler)
    try:
        for entry in [*job['inputs'],*package_pins]:checked(entry)
        require(acquisition is None or pin(acquisition['path'])==acquisition,'Acquired policy changed')
        source_after=True
    except Exception as error:errors.append('Final immutable input check: '+repr(error));source_after=False
    for relative in ['producer.jsonl','proxy.jsonl','actor-stdout.txt','actor-stderr.txt','boot.lua',
                     'journal/games.jsonl','journal/lives.jsonl','journal/measurement_starts.jsonl']:
        path=output/relative
        if path.is_file():path.chmod(0o444);raw_files[relative]=pin(path)
    actual_exit=child.poll()if child else None
    complete=bool(not errors and actual_exit==0 and proxy is not None and proxy.handoff
                  and policy_before==policy_after and source_after is True)
    result=put(output/'result.json',dict(schema='robotron-full-policy-startup-original-result-v1',
        status='PASS_ACTUAL_POLICY_STARTUP_HANDOFF_PREFIX_ONLY'if complete else 'ORIGINAL_DIAGNOSTIC_INVALID_NO_RETRY',
        complete=complete,errors=errors,original_MAME_exit=actual_exit,original_MAME_pid=child.pid if child else None,
        original_MAME_birth=actor_birth,original_frames=proxy.sequence if proxy else 0,
        actual_handoff=proxy.handoff if proxy else None,policy_before=policy_before,policy_after=policy_after,
        acquired_checkpoint=acquisition,initialized_boot_restore=boot_restore,
        before_intentional_stop=before_stop,after_intentional_stop=after_stop,controller_exit=controller_exit,
        immutable_inputs_unchanged=source_after,files=raw_files,original_attempt=1,no_retry=True,
        quality_qualified=False,quality_protocol_changed=False,main_runtime_changed=False,
        full_game_score_verified=False,learning_speed_gain_verified=False,
        limitations='One CPU/eager actor and1200 frames; deliberate prefix termination. No complete game or GPU/all32-slot validation.'))
    print(json.dumps(dict(result=result,complete=complete,actual_MAME_exit=actual_exit)),flush=True)
    return 0 if complete else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job')
    parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY: no policy load, emulator, socket or writes');return 0
    require(args.job and args.job_sha256 and args.source_sha256,'Explicit original bindings required')
    require(pin(__file__)['sha256']==args.source_sha256,'Actual diagnostic runtime source differs')
    jp=pin(Path(args.job));require(jp['sha256']==args.job_sha256 and jp['identity']['mode']=='0o444','Job differs')
    return run(json.loads(Path(args.job).read_bytes()),jp)


if __name__=='__main__':sys.exit(main())
