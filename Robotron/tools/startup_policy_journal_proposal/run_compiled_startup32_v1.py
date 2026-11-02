"""One original32-slot compiled-GPU startup integration prefix; inert by default.

Every actor keeps the tested full Lua, proxy-v3, accepted START certificate and
prospective journal handoff. This is not a full-game quality experiment. Main
learning is observed read-only; this program never repairs or changes main.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
G=HERE.parents[1]
GPU='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
SLOTS=tuple(range(4096,4128))
PORTS={slot:20000+slot-4096 for slot in SLOTS}
LEASE=Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def helpers():
    path=HERE/'run_full_policy_startup_v3.py'
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1',
            'Actual CPU integration helper definitions differ')
    return load('_compiled32_original_helper_defs',path)


def validate_job(job):
    require(job['schema']=='robotron-compiled-startup32-original-v1'
        and job['actor_slots']==list(SLOTS)and job['frames']==1200 and job['origin_port']==19998
        and job['proxy_ports']=={str(k):v for k,v in PORTS.items()}
        and job['device']=='cuda'and job['backend']=='inductor'and job['gpu_uuid']==GPU
        and job['cpu_threads']==2 and job['admission_s']==90 and job['wall_limit_s']==840,
        'Exact compiled32 original scope required')
    require(all(type(job[k])is int for k in ('frames','origin_port','cpu_threads','admission_s','wall_limit_s'))
        and all(type(v)is int for v in job['proxy_ports'].values()),'Typed fixed original limits required')
    require(job['source_package']['sha256']=='9c9d513328fb8f82427217b2bb2844d73226b3814de34905e28808a93496532e'
        and job['checkpoint']['sha256']=='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83'
        and job['validated_CPU_prefix']['sha256']=='7d0cc6f960626fef0b9c0a6c40f68f9dcb55fa98d351c6b25111792156cdb647',
        'Exact frozen source/policy and actual CPU handoff predecessor required')
    expected=dict(supervision='1f41d360fa23632cb26d6dee33d3c822bec7f9cf79fdbb75e47f3418059ca5f0',
        window='f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3',
        reader='c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    require(set(job['main_sources'])==set(expected)and all(job['main_sources'][k]['sha256']==v for k,v in expected.items()),
            'Exact read-only main supervision dependencies required')
    require(set(job['sessions'])==set(job['connections'])=={str(slot)for slot in SLOTS},
            'All32 original session/connection bindings required')
    values=[*job['sessions'].values(),*job['connections'].values()]
    require(len(set(values))==64 and all(type(v)is str and len(v)==32
        and v!='0'*32 and all(c in '0123456789abcdef'for c in v)for v in values),
        'Exactly64 distinct fresh nonzero identities required')
    output=Path(job['output'])
    require(output.is_absolute()and output.resolve()==output and not output.exists()
        and output.parent.is_dir(),'Fresh exact private output required')
    return output


def actor_environment(base,private,slot,session,connection,library):
    require(type(slot)is int and slot in SLOTS,'Unexpected original slot')
    env={k:v for k,v in base.items()if not k.startswith('ROBOTRON_')and k not in ('LD_PRELOAD','PYTHONPATH')}
    env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',CUDA_VISIBLE_DEVICES='',
        XDG_CONFIG_HOME=str(private/'mame-config'),XDG_DATA_HOME=str(private/'mame-data'),
        LD_PRELOAD=str(library),ROBOTRON_SOCKET_WAIT_US='1000',ROBOTRON_SOCKET_WAIT_PORT=str(PORTS[slot]),
        ROBOTRON_SOCKET_ADDRESS='127.0.0.1:'+str(PORTS[slot]),ROBOTRON_CLIENT_SLOT=str(slot),
        ROBOTRON_EVAL_MODE='1',ROBOTRON_PREVIEW_CLIENT='0',ROBOTRON_SKIP_UNUSED_TACTICAL_FEATURES='0',
        ROBOTRON_ENABLE_RRCHRIS_PATCH='0',ROBOTRON_FULL_STARTUP_TRACE=str(private/'producer.jsonl'),
        ROBOTRON_FULL_STARTUP_SLOT=str(slot),ROBOTRON_FULL_STARTUP_SESSION=session,
        ROBOTRON_FULL_STARTUP_CONNECTION=connection)
    return env


def actor_command(job,private):
    argv=[job['mame']['path'],'robotron','-rompath',job['rompath'],'-noreadconfig','-cheat',
        '-noplugins','-nothrottle','-sound','none','-video','none','-skip_gameinfo',
        '-seconds_to_run','60','-autoboot_script',str(private/'boot.lua'),'-inipath',str(private/'ini')]
    for option,name in [('cfg','cfg'),('nvram','nvram'),('input','inp'),('state','sta'),
        ('snapshot','snap'),('diff','diff'),('share','share'),('comment','comments')]:
        argv.extend(['-'+option+'_directory',str(private/name)])
    return argv


class PrivateLease:
    """Create one fresh canonical inode; never adopt or unlink a foreign one."""
    def __init__(self,path=LEASE):self.path=Path(path);self.fd=None;self.identity=None;self.locked=False
    def acquire(self):
        self.fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600)
        s=os.fstat(self.fd);self.identity=(s.st_dev,s.st_ino)
        fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.locked=True
        os.write(self.fd,(json.dumps(dict(pid=os.getpid(),starttime_ticks=process_birth(os.getpid())))+'\n').encode())
        os.fsync(self.fd)
        return dict(path=str(self.path),device=s.st_dev,inode=s.st_ino)
    def release(self):
        require(self.fd is not None and self.locked,'No original lease held')
        s=self.path.lstat();fd=os.fstat(self.fd)
        require(stat.S_ISREG(s.st_mode)and (s.st_dev,s.st_ino)==self.identity==(fd.st_dev,fd.st_ino)
            and s.st_nlink==1,'Original private lease replaced; no unlink')
        self.path.unlink();os.close(self.fd);self.fd=None;self.locked=False


def process_birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def run(job,jp,h):
    output=validate_job(job)
    require(not os.environ.get('LD_PRELOAD'),'Never preload Python')
    for entry in job['inputs']:h.checked(entry)
    root,package_pins=h.package_inputs(job['source_package'])
    output.mkdir(mode=0o700);(output/'actors').mkdir(mode=0o700);(output/'main-observations').mkdir(mode=0o700)
    stopped=threading.Event();bridge_stop=threading.Event();errors=[];actors={};streams=[]
    server=actor=controller=server_worker=None;policy_before=policy_after=None
    before_stop=after_stop=controller_exit=None;acquisition=None;library_entry=None
    lease=PrivateLease();lease_entry=None;main_samples=[];source_unchanged=False
    started=time.monotonic();deadline=started+840
    previous={sig:signal.signal(sig,lambda *_:stopped.set())for sig in (signal.SIGTERM,signal.SIGINT)}
    try:
        lease_entry=lease.acquire();h.put(output/'original-lease.json',lease_entry)
        gpu_before=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory',
            '--format=csv,noheader'],capture_output=True,text=True,timeout=10)
        require(gpu_before.returncode==0 and GPU not in gpu_before.stdout,'Private GPU0 is not idle')
        h.put(output/'original-GPU-before.json',dict(exit=gpu_before.returncode,stdout=gpu_before.stdout,stderr=gpu_before.stderr))
        supervision=load('_compiled32_main_supervision',h.checked(job['main_sources']['supervision']))
        window=load('_compiled32_main_health',h.checked(job['main_sources']['window']))
        reader=load('_compiled32_immutable_reader',h.checked(job['main_sources']['reader']))
        main=reader.read_pin(job['main_binding'])
        policy=reader.read_pin(main['supervision_policy'])
        baseline=reader.read_pin(main['baseline_API'])
        def check_main():
            import urllib.request
            snapshot=supervision.collect(policy)
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5)as response:wire=response.read(1048577)
            require(len(wire)<=1048576,'Bounded main API required');api=json.loads(wire)
            state=supervision.validate_snapshot(policy,snapshot,api['client_count'])
            require(state['full_capacity']and not state['pending']and not state['completed_episodes'],
                    'All192 unchanged main actors required for this prefix diagnostic')
            window.owner_and_files(main);window.healthy(api,baseline,main['experiment'],time.time())
            require(0<=time.time()-(G/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime<=360,'Main autosave stale')
            index=len(main_samples);directory=output/'main-observations'
            with (directory/f'{index:04d}-API.raw.json').open('xb')as stream:
                stream.write(wire);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o444)
            record=dict(snapshot=h.put(directory/f'{index:04d}-census.json',snapshot),
                raw_API=h.pin(directory/f'{index:04d}-API.raw.json'),learner_frames=api['learner_frame_count'],
                training_steps=api['training_steps'],unix_s=time.time())
            main_samples.append(record)
        check_main()
        sidecar=load('_compiled32_profile06_sidecar',root/'tools/run_frozen_sidecar.py')
        sidecar.configure_environment(SimpleNamespace(directory=output,gpu_uuid=GPU,device='cuda',
            completion_policy='confirmed_reset_reserves_v1',game_boundary_diagnostics=True,cpu_threads=2))
        sys.path.insert(0,str(root/'Scripts'));sys.path.insert(0,str(HERE))
        import torch
        from dqn import config
        from dqn.inference_actor import InferenceActor
        from dqn.managed_measurement import ManagedMeasurement
        from dqn.socket_server import SocketServer,parse_frame_data
        import full_startup_proxy_v3 as bridge
        import startup_handoff_v1 as authority
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        config.RL_CONFIG.inference_batch_max_size=16
        source=h.checked(job['checkpoint']);checkpoint=output/'checkpoint.pt'
        import shutil
        with source.open('rb')as incoming,checkpoint.open('xb')as outgoing:
            shutil.copyfileobj(incoming,outgoing);outgoing.flush();os.fsync(outgoing.fileno());os.fchmod(outgoing.fileno(),0o444)
        acquisition=h.pin(checkpoint)
        require(acquisition['sha256']==job['checkpoint']['sha256'],'Acquired policy bytes differ')
        actor=InferenceActor(checkpoint,device='cuda:0',inference_backend='inductor')
        metadata=actor.checkpoint_metadata
        for key in ('learner_frame_count','frame_count','measurement_frame_count'):
            setattr(config.metrics,key,int(metadata[key]))
        config.metrics.total_training_steps=actor.training_steps
        config.metrics.total_optimized_samples=actor.optimized_samples
        config.metrics.training_enabled=False;config.metrics.preview_capture_enabled=False;config.metrics.hud_enabled=False
        for key,value in dict(start_advanced=False,start_level_min=1,epsilon_pct=0,expert_pct=0,
                              auto_curriculum=False,difficulty=5).items():setattr(config.game_settings,key,value)
        require(torch.cuda.device_count()==1 and os.environ['CUDA_VISIBLE_DEVICES']==GPU
            and actor.memory is actor.optimizer is None,'Actual private GPU inference isolation differs')
        server=SocketServer('127.0.0.1',19998,actor,replay_enabled=False)
        def boundary(generation):
            value=server.measurement_boundary_status(generation)
            value['ready']=bool(value['ready']and value['clients']==32 and value['actor_slots']==list(SLOTS))
            return value
        controller=ManagedMeasurement(actor,config.metrics,server.game_journal,boundary_status=boundary)
        controller.enter(job['label'],cohort_s=90,timeout_s=180)
        policy_reader=authority.live_policy_reader(actor,config.metrics,server,config.game_settings,
            checkpoint_path=checkpoint,checkpoint_sha256=acquisition['sha256'],actor_source_sha256=job['actor_source_sha256'])
        policy_before=policy_reader();compile_before=actor.compile_report
        require(policy_before['numeric_policy']['compiled']is True and compile_before['all_shapes_verified']==list(range(1,17)),
                'Actual common compiled backend readiness differs')
        h.put(output/'original-loaded-policy.json',dict(policy=policy_before,compile_report=compile_before,
            gpu_uuid=GPU,CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],replay_enabled=server.replay_enabled,
            memory_is_none=actor.memory is None,optimizer_is_none=actor.optimizer is None))
        check_main();require(not stopped.is_set()and time.monotonic()<deadline,'Interrupted before original fleet')
        seed=load('_compiled32_seed_restore_defs',h.checked(job['seed_runtime']))
        builder=load('_compiled32_wait_builder',root/'tools/build_socket_wait.py')
        library=builder.build(output/'socket-wait-build');library.chmod(0o444);library_entry=h.pin(library)
        def admission():
            if controller.start_ts is None:return None
            return dict(open_unix_ns=int(controller.start_ts*1e9),close_unix_ns=int(controller.close_ts*1e9),
                        generation=controller.generation,experiment=controller.label)
        server_worker=threading.Thread(target=server.start,name='compiled32-origin',daemon=True);server_worker.start()
        ready_end=min(deadline,time.monotonic()+15)
        while not server.running:
            require(server_worker.is_alive()and time.monotonic()<ready_end,'Original compiled origin failed to bind');time.sleep(.01)
        for slot in SLOTS:
            private=output/'actors'/str(slot);private.mkdir(mode=0o700)
            for name in ('cfg','nvram','ini','inp','sta','snap','diff','share','comments','mame-data','mame-config'):
                (private/name).mkdir(mode=0o700)
            restored=seed.restore_seed(job,private)
            trace=private/'producer.jsonl';trace.touch(mode=0o600);s=trace.stat()
            trace_identity=dict(device=s.st_dev,inode=s.st_ino,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
            witness=(private/'proxy.jsonl').open('xb');streams.append(witness)
            def emit(value,stream=witness):
                raw=(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()
                require(len(raw)<=65536 and stream.tell()+len(raw)<=64*1024*1024,'Bounded original proxy log exceeded')
                stream.write(raw);stream.flush()
            proxy=bridge.StartupProxy(server,slot=slot,session=job['sessions'][str(slot)],connection=job['connections'][str(slot)],
                trace_path=trace,trace_identity=trace_identity,rom_sha256=job['loaded_rom_sha256'],policy_reader=policy_reader,
                admission_reader=admission,frame_parser=parse_frame_data,emit=emit,stop_event=bridge_stop)
            listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,0)
            listener.bind(('127.0.0.1',PORTS[slot]));listener.listen(1);listener.settimeout(30)
            def serve(listener=listener,proxy=proxy,slot=slot):
                try:
                    with listener.accept()[0]as peer,socket.create_connection(('127.0.0.1',19998),timeout=5)as origin:
                        proxy.serve(peer,origin)
                except Exception as error:errors.append('Original slot'+str(slot)+': '+repr(error))
            worker=threading.Thread(target=serve,name='compiled32-proxy-'+str(slot),daemon=True)
            actors[slot]=dict(private=private,proxy=proxy,listener=listener,worker=worker,child=None,birth=None,
                              boot_restore=restored,trace_identity=trace_identity,worker_started=False)
            with (private/'boot.lua').open('x')as stream:
                stream.write('local ok,err=pcall(function() assert(loadfile('+json.dumps(job['lua']['path'])+'))() end)\n'
                    'if not ok then print("COMPILED32_STARTUP_FATAL "..tostring(err));manager.machine:exit() end\n')
        for slot,row in actors.items():
            require(not stopped.is_set()and time.monotonic()<deadline,'Interrupted during original fleet launch')
            row['worker'].start();row['worker_started']=True
            private=row['private'];env=actor_environment(os.environ,private,slot,job['sessions'][str(slot)],
                                                       job['connections'][str(slot)],library)
            out=(private/'actor-stdout.txt').open('xb');err=(private/'actor-stderr.txt').open('xb');streams.extend([out,err])
            argv=actor_command(job,private)
            child=subprocess.Popen(argv,stdout=out,stderr=err,stdin=subprocess.DEVNULL,env=env,cwd=private)
            row.update(child=child,birth=process_birth(child.pid))
            require(row['birth']is not None,'Original actor birth not captured')
            h.put(private/'original-actor.json',dict(pid=child.pid,starttime_ticks=row['birth'],slot=slot,
                session=job['sessions'][str(slot)],connection=job['connections'][str(slot)],argv=argv,
                original_job=jp,trace_identity=row['trace_identity'],proxy_port=PORTS[slot],boot_restore=row['boot_restore']))
        fixed_window=None;last_health=time.monotonic()
        while True:
            require(time.monotonic()<deadline and not stopped.is_set(),'Original compiled32 wall bound/interruption')
            require(not errors and server.inference_only_error is None and server_worker.is_alive()and server.running,
                    'Original bridge/inference/server failed')
            for slot,row in actors.items():
                child=row['child']
                require(child is not None and row['proxy'].error is None,'Original slot bridge failed')
                if child.poll()is None:require(process_birth(child.pid)==row['birth'],'Original actor birth changed')
                else:require(child.returncode==0,'Original actor exited nonzero')
            if all(row['child'].poll()is not None for row in actors.values()):break
            status=controller.tick();require(not status['complete'],'Original measurement became terminal during prefix')
            window_value=admission()
            if window_value is not None:
                if fixed_window is None:fixed_window=window_value;h.put(output/'original-fixed-admission.json',window_value)
                require(window_value==fixed_window,'Original admission moved')
                require(boundary(controller.generation)['ready'],'All32 original slots must remain acknowledged')
            if time.monotonic()-last_health>=5:check_main();last_health=time.monotonic()
            time.sleep(.01)
        for slot,row in actors.items():
            require(row['proxy'].sent_complete.is_set()and row['proxy'].sequence==1200 and row['proxy'].handoff,
                    'Original slot did not complete startup handoff/prefix')
            rows=[json.loads(line)for line in (row['private']/'producer.jsonl').read_bytes().splitlines()]
            footers=[r for r in rows if r['kind']=='footer']
            require(len(footers)==1 and footers[0]['sequence']==1200 and footers[0]['failed']is False
                and footers[0]['first_play_sequence']>0 and not any(r['kind']=='fault'for r in rows),
                'Original slot complete footer differs')
            row['footer']=footers[0]
        policy_after=policy_reader();require(policy_after==policy_before and actor.compile_report==compile_before,
                                             'Actual common compiled policy/clocks/graphs changed')
        before_stop=server.game_journal.cohort_status(controller.label,controller.start_ts,controller.close_ts)
        certified={row['proxy'].handoff['journal_game_id']for row in actors.values()}
        require(len(certified)==32 and certified.issubset(set(before_stop['started_ids']))
            and before_stop['abandoned']==0 and before_stop['count']+before_stop['pending']==before_stop['started']
            and before_stop['started_actor_slots']==list(SLOTS),'All32 first certificates and every admitted game required')
        check_main()
        h.put(output/'before-intentional-prefix-stop.json',dict(cohort=before_stop,policy=policy_after,
            compile_report=actor.compile_report,controller=controller.status(),
            slots={str(slot):dict(footer=row['footer'],handoff=row['proxy'].handoff,
                actual_MAME_exit=row['child'].returncode)for slot,row in actors.items()}))
    except Exception as error:errors.append(repr(error))
    finally:
        for slot,row in actors.items():
            child=row['child']
            if child is not None and child.poll()is None:
                try:
                    require(process_birth(child.pid)==row['birth'],'Changed original birth; no signal')
                    child.terminate()
                except Exception as error:errors.append('Original actor cleanup'+str(slot)+': '+repr(error))
        stop_end=time.monotonic()+10
        while any(row['child']is not None and row['child'].poll()is None for row in actors.values())and time.monotonic()<stop_end:
            time.sleep(.05)
        client_threads=[]
        if server is not None:
            with server.client_lock:client_threads=list(server.clients.values())
            try:server.stop()
            except Exception as error:errors.append('Original server stop: '+repr(error))
        bridge_stop.set()
        for row in actors.values():row['listener'].close()
        join_end=time.monotonic()+20
        owned_threads=[server_worker,*client_threads,*[r['worker']for r in actors.values()if r['worker_started']]]
        for worker in owned_threads:
            if worker is not None:
                worker.join(max(0,join_end-time.monotonic()))
                if worker.is_alive():errors.append('Original thread completion unknown: '+worker.name)
        if server is not None and controller is not None and controller.start_ts is not None:
            after_stop=server.game_journal.cohort_status(controller.label,controller.start_ts,controller.close_ts)
        if server is not None and server.inference_only_error is not None:errors.append('Actual inference error: '+server.inference_only_error)
        if controller is not None:
            try:controller_exit=controller.exit()
            except Exception as error:errors.append('Original measurement exit: '+repr(error))
        if actor is not None:actor.close()
        for stream in streams:
            try:stream.flush();os.fsync(stream.fileno());stream.close()
            except Exception as error:errors.append('Original stream close: '+repr(error))
        for sig,handler in previous.items():signal.signal(sig,handler)
    try:
        for entry in job['inputs']+package_pins:h.checked(entry)
        require(acquisition is None or h.pin(acquisition['path'])==acquisition,'Acquired policy changed')
        source_unchanged=True
    except Exception as error:errors.append('Final input check: '+repr(error))
    actual_slots={}
    for slot,row in actors.items():
        files={}
        for name in ('producer.jsonl','proxy.jsonl','actor-stdout.txt','actor-stderr.txt','boot.lua'):
            path=row['private']/name
            if path.exists():path.chmod(0o444);files[name]=h.pin(path)
        child=row['child'];actual_slots[str(slot)]=dict(pid=child.pid if child else None,birth=row['birth'],
            actual_exit=child.poll()if child else None,frames=row['proxy'].sequence,handoff=row['proxy'].handoff,
            footer=row.get('footer'),files=files,boot_restore=row['boot_restore'])
        if child is not None and child.poll()is None:errors.append('Original actor completion unknown: '+str(slot))
    journal={}
    for name in ('games.jsonl','lives.jsonl','measurement_starts.jsonl'):
        path=output/'journal'/name
        if path.is_file():path.chmod(0o444);journal[name]=h.pin(path)
    released=False
    if lease.fd is not None:
        try:
            require(all(row['child']is None or row['child'].poll()is not None for row in actors.values())
                and all(worker is None or not worker.is_alive()for worker in owned_threads),
                'Unknown owned actor/thread completion; preserve original lease')
            lease.release();released=True
        except Exception as error:errors.append('Original private lease cleanup: '+repr(error))
    complete=bool(not errors and len(actual_slots)==32 and policy_before==policy_after
                  and policy_after is not None and source_unchanged and released)
    result=h.put(output/'result.json',dict(schema='robotron-compiled-startup32-original-result-v1',
        status='PASS_ALL32_COMMON_COMPILED_STARTUP_HANDOFF_PREFIX_ONLY'if complete else 'ORIGINAL_COMPILED32_DIAGNOSTIC_INVALID_NO_RETRY',
        complete=complete,errors=errors,original_attempt=1,no_retry=True,original_slots=actual_slots,
        policy_before=policy_before,policy_after=policy_after,acquired_checkpoint=acquisition,
        before_intentional_stop=before_stop,after_intentional_stop=after_stop,controller_exit=controller_exit,
        journal=journal,main_samples=main_samples,lease=lease_entry,original_lease_released=released,
        socket_wait_library=library_entry,immutable_inputs_unchanged=source_unchanged,
        quality_qualified=False,full_game_score_verified=False,learning_speed_gain_verified=False,
        main_runtime_changed=False,quality_protocol_changed=False,
        limitations='32 compiled-GPU actors and1200-frame prefixes. Intentionally incomplete games; full-tail validation and new quality protocol still required.'))
    print(json.dumps(dict(result=result,complete=complete)),flush=True)
    return 0 if complete else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--job')
    parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY: no policy load, GPU, emulator, socket or outputs');return 0
    h=helpers();require(args.job and args.job_sha256 and args.source_sha256,'Explicit original bindings required')
    require(h.pin(__file__)['sha256']==args.source_sha256,'Actual compiled32 source differs')
    jp=h.pin(args.job);require(jp['sha256']==args.job_sha256 and jp['identity']['mode']=='0o444','Actual original job differs')
    return run(json.loads(Path(args.job).read_bytes()),jp,h)


if __name__=='__main__':sys.exit(main())
