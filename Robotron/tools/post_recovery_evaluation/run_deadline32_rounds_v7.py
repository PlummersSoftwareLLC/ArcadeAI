"""One original fixed 60-minute first-game deadline leg; inert without --execute.

All32 original actors remain active until D. A separate source-bound recorder
seals one first-game score per slot as completed or right-censored BEFORE any
intentional private teardown. Historical full-game gates do not judge this new
metric. Main training and all production source remain untouched.
"""
import argparse
import copy
import hashlib
import importlib.util
import inspect
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

D=Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/deadline-score60min-protocol-original01-preparation-20261026')
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=G/'tools/startup_policy_journal_proposal'
PARENT=D.parent/'quality32-protected3045-vs-later3262-selectorReuse-original01-preparation-20261025/evaluator-count-active600-counterbalanced-engineering-original06/future-startup-slot64-chain-correction-original01/run_cold_slot64_prefix_v1.py'
PARENT_SHA='9f6820ea3633d8e411f4408846d0aaef7a9b9bde1393b16975293315a32ca25d'
REFERENCE_SHA='b23152ece3bb614831a278fe0572c07433f1bee59c5accef5a1ab7d3007af883'
SLOTS=tuple(range(4096,4128))
PORTS={slot:20000+slot-4096 for slot in SLOTS}
GPU='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
COMPONENT_KEYS={'recorder','hooks','report','lifecycle','clock_proxy','clock_authority','clock_codec','clock_readiness','clock_ledger','clock_sampler','prefix_auditor','score_auditor'}


def require(ok,message):
    if not ok:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value


def parent():
    require(hashlib.sha256(PARENT.read_bytes()).hexdigest()==PARENT_SHA,'Frozen ownership/health helper source differs')
    return load('_deadline_owned_resource_helpers',PARENT)


def validate_job(job):
    require(job['runtime']['path']==str(Path(__file__).resolve()) and
            job['runtime']['sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'Actual deadline runtime differs')
    require(job['schema']=='robotron-deadline32-one-original-leg-v1' and job['leg'] in ('R1','C1','R2','C2')
            and type(job['attempt']) is int and job['attempt']==1 and job['no_retry'] is True,'One original preselected deadline leg required')
    require(all(type(job[k]) is int for k in ('origin_port','horizon_ns','startup_limit_s','wall_limit_s',
            'cleanup_limit_s','inflight_drain_bound_ns','startup_trace_frames','cpu_threads','inference_max_batch_size',
            'controller_observation_s','startup_admission_duration_ns')),
            'Exact integer native bounds required')
    require(job['actor_slots']==list(SLOTS) and job['origin_port']==19998 and
            job['proxy_ports']=={str(k):v for k,v in PORTS.items()} and
            job['horizon_ns']==3_600_000_000_000 and job['startup_limit_s']==300 and
            job['wall_limit_s']==4200 and job['cleanup_limit_s']==60 and
            job['inflight_drain_bound_ns']==3_500_000_000,'Exact selected32/60-minute/native bounds required')
    require(job['resources']==dict(cpu_cores=12,memory_bytes=24<<30,tasks_max=512,runtime_max_s=4260)
            and job['observer_resources']==dict(cpu_cores=2,memory_bytes=4<<30,tasks_max=128,runtime_max_s=4260)
            and job['controller_observation_s']==4320,'Exact selected durable resources required')
    require(job['startup_trace_frames']==1200 and job['device']=='cuda' and job['backend']=='inductor'
            and job['gpu_uuid']==GPU and job['cpu_threads']==2 and job['inference_max_batch_size']==16,
            'Matched original compiled backend/ROM prefix required')
    require(set(job['components'])==COMPONENT_KEYS,'Exact actual deadline source chain required')
    require(set(job['sessions'])==set(job['connections'])=={str(s) for s in SLOTS},'All32 original transport identities required')
    values=[*job['sessions'].values(),*job['connections'].values()]
    require(len(set(values))==64 and all(type(v) is str and len(v)==32 and v!='0'*32
            and all(c in '0123456789abcdef' for c in v) for v in values),'Fresh original transport identities required')
    require(type(job['loaded_rom_sha256']) is str and len(job['loaded_rom_sha256'])==64 and
            job['training_experiment']!=job['measurement_label'] and job['label']==job['measurement_label'] and
            job['startup_admission_duration_ns']==300_000_000_000,
            'Saved training recipe and new measurement label must remain distinct')
    output=Path(job['output'])
    require(output.is_absolute() and output.resolve()==output and not output.exists() and output.parent.is_dir(),'Fresh original output required')
    return output


def load_components(job,h):
    # Exact names prevent implicit fallback to the old authority/codec chain.
    names={'clock_sampler':'clock_cosampling_v1','clock_authority':'startup_handoff_deadline32_v1',
        'clock_codec':'wire_codec_deadline32_v1','clock_readiness':'boot_readiness_deadline32_v1',
        'clock_ledger':'tail_ledger_deadline32_v1','clock_proxy':'full_startup_proxy_deadline32_v1',
        'recorder':'_deadline_real_recorder','hooks':'_deadline_real_hooks','report':'_deadline_real_report',
        'lifecycle':'_deadline_real_lifecycle','prefix_auditor':'_deadline_real_prefix_auditor','score_auditor':'_deadline_real_score_auditor'}
    modules={}
    for key in ('clock_sampler','clock_authority','clock_codec','clock_readiness','clock_ledger','clock_proxy',
                'recorder','hooks','report','lifecycle','prefix_auditor','score_auditor'):
        modules[key]=load(names[key],h.checked(job['components'][key]))
    modules['clock_proxy']._dependencies()
    for key,attribute in (('clock_authority','authority'),('clock_codec','codec')):
        actual=getattr(modules['clock_proxy'],attribute)
        path=Path(inspect.getsourcefile(actual)).resolve()
        require(path==Path(job['components'][key]['path']).resolve() and
                hashlib.sha256(path.read_bytes()).hexdigest()==job['components'][key]['sha256'],
                'Actual private clock proxy nested source differs')
        modules[key]=actual
    return modules


def round_contract():
    path=Path(__file__).with_name('deadline_round_contract_v7.py')
    require(hashlib.sha256(path.read_bytes()).hexdigest()=='ba361afde6005425741de09feb025ee413da3e3d5a5376298ca5769f59c34442','Exact round contract source required')
    return load('_deadline_round_contract',path)

def validate_main_health_contract(job,protocol,family):
    return round_contract().validate_static(job,protocol,family,parent().helpers())


def validate_completed_context(job,h):
    """Pure actual-job preflight used by both bounded CPU guard and real run."""
    validate_job(job)
    modules=load_components(job,h)
    reader=load('_deadline_prebody_immutable_reader',h.checked(job['main_sources']['reader']))
    def read(pin,as_json=True):return reader.read_pin(pin,as_json=as_json)
    protocol=read(job['main_health_protocol']);family=read(job['source_family_manifest'])
    validate_main_health_contract(job,protocol,family)
    study=read(job['study_precommit']);role='reference' if job['leg'].startswith('R') else 'candidate'
    require(study['schema']=='robotron-deadline32-fixed-fresh-RCRC-study-v1' and
            study['ordered_legs']==['R1','C1','R2','C2'] and study['horizon_ns']==job['horizon_ns'] and
            study['actor_slots']==list(SLOTS),'Exact prospective fixed new metric study required')
    selected=study['policies'][role]
    require(selected['checkpoint']==job['checkpoint'] and selected['expected_policy_clocks']==job['expected_policy_clocks'] and
            selected['training_experiment']==job['training_experiment'] and
            selected['immutable_numerical_or_protection_authority']==job['policy_authority'] and
            study['policies']['reference']['checkpoint']['sha256']==REFERENCE_SHA,
            'Exact selected policy, recipe, prior CPU/protection authority and clocks required')
    read(job['policy_authority'])
    binding,baseline=round_contract().validate_binding(job,protocol,family,read,h)
    provenance=round_contract().validate_static(job,protocol,family,h)
    root,package_pins=h.package_inputs(job['source_package'])
    return dict(modules=modules,reader=reader,protocol=protocol,family=family,
        main_binding=binding,baseline_API=baseline,protocol_provenance=provenance,study=study,
        source_root=root,package_pins=package_pins)


def capture_origin_writers(server,*,require_all32=True):
    """Retain actual thread objects before the frozen server clears its registry."""
    with server.client_lock:
        values=list(server.clients.values())
        clients=tuple(v for v in values if isinstance(v,threading.Thread))
        require(len({id(t)for t in clients})==len(clients),'Origin client Thread reused')
        if require_all32:
            require(len(values)==len(clients)==32 and all(t.is_alive()for t in clients),
                    'Retain all32 original live client threads before intentional shutdown')
    batcher=getattr(server,'inference_batcher',None)
    inference=None if batcher is None else getattr(batcher,'_thread',None)
    require(inference is None or isinstance(inference,threading.Thread),'Actual inference batch worker differs')
    if require_all32:require(inference is not None and inference.is_alive(),'Retain actual live InferBatchWorker')
    return clients,inference


def owned_cleanup_timers(server):
    # The frozen handler creates these only at its very end. Call after every
    # retained handler joins, so no later owned cleanup Timer can be created.
    return tuple(t for t in threading.enumerate() if isinstance(t,threading.Timer) and t.function==server._cleanup)


def prepare_actors(*,job,output,server,h,seed,bridge,ledger,bridge_stop,policy_reader,admission,
                   frame_parser,registration,actors,streams,errors,failures,cleanup_event,cleanup_state,hooks):
    for slot in SLOTS:
        private=output/'actors'/str(slot);private.mkdir(mode=0o700)
        for name in ('cfg','nvram','ini','inp','sta','snap','diff','share','comments','mame-data','mame-config'):
            (private/name).mkdir(mode=0o700)
        restored=seed.restore_seed(job,private)
        identities={}
        for name in ('producer.jsonl','lifecycle.jsonl'):
            path=private/name;path.touch(mode=0o600);s=path.stat()
            identities[name]=dict(device=s.st_dev,inode=s.st_ino,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)
        witness=(private/'proxy.jsonl').open('xb');streams.append(witness);writer=ledger.BoundedWitness(witness)
        def emit(value,writer=writer):
            if value.get('kind')=='original_proxy_failure':
                flag=cleanup_event.is_set()  # Observe flag BEFORE its timestamp.
                stamp=time.monotonic_ns()
                value=dict(value,intentional_cleanup_flag=flag,observed_monotonic_ns=stamp,
                    cleanup_begin_monotonic_ns=cleanup_state.get('begin_monotonic_ns'),
                    cleanup_declared_monotonic_ns=cleanup_state.get('declared_monotonic_ns'))
            return writer.emit(value)
        proxy=bridge(server,slot=slot,session=job['sessions'][str(slot)],connection=job['connections'][str(slot)],
            trace_path=private/'producer.jsonl',trace_identity=identities['producer.jsonl'],rom_sha256=job['loaded_rom_sha256'],
            policy_reader=policy_reader,admission_reader=admission,frame_parser=frame_parser,emit=emit,
            stop_event=bridge_stop,drain_reader=lambda:registration)
        listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,0)
        listener.bind(('127.0.0.1',PORTS[slot]));listener.listen(1);listener.settimeout(30)
        retired=threading.Event()
        def serve(listener=listener,proxy=proxy,slot=slot,retired=retired):
            try:
                with listener.accept()[0] as peer,socket.create_connection(('127.0.0.1',19998),timeout=3) as origin:
                    proxy.serve(peer,origin)
            except Exception as error:
                flag=cleanup_event.is_set();stamp=time.monotonic_ns()
                expected=(isinstance(error,hooks.DeadlineRetired) and flag and
                    server.shutdown_event.is_set() and cleanup_state.get('score_seal') is not None)
                event=dict(slot=slot,error=repr(error),intentional_cleanup_flag=flag,
                    observed_monotonic_ns=stamp,expected_deadline_retirement=bool(expected))
                failures.append(event)
                if expected:retired.set()
                else:errors.append('Original slot '+str(slot)+': '+repr(error))
        worker=threading.Thread(target=serve,name='deadline32-proxy-'+str(slot),daemon=True)
        actors[slot]=dict(private=private,proxy=proxy,listener=listener,worker=worker,child=None,birth=None,
            boot_restore=restored,trace_identity=identities['producer.jsonl'],lifecycle_identity=identities['lifecycle.jsonl'],
            witness_writer=writer,worker_started=False,retired=retired)
        with (private/'boot.lua').open('x') as stream:
            stream.write('local ok,err=pcall(function() assert(loadfile('+json.dumps(job['lua']['path'])+'))() end)\nif not ok then print("DEADLINE32_LUA_FATAL "..tostring(err));manager.machine:exit() end\n')


def run(job,jp,h):
    output=validate_job(job)
    require(not os.environ.get('LD_PRELOAD'),'Never preload private Python')
    for entry in job['inputs']:h.checked(entry)
    context=validate_completed_context(job,h);modules=context['modules']
    guard_path=Path(job['prelaunch_family_guard_closeout'])
    require(guard_path==output.parent/'source-family-guards-CPU-original01'/'independent-deadline32-family-guards-and-CPU-closeout.json',
            'Exact prospective original CPU closeout path required')
    guard=json.loads(h.checked(h.pin(guard_path)).read_bytes())
    require(guard['schema']=='robotron-deadline32-original-prelaunch-family-guard-v1' and
            guard['status']=='PASS' and guard['native_job']==jp and guard['runtime']==job['runtime']
            and guard['actual_exit']==0 and guard['actual_CPU_cores']==2 and
            guard['actual_memory_bytes']==4<<30 and guard['actual_runtime_limit_s']==180,
            'Actual bounded CPU closure of this exact new native job required before GPU')
    round_contract().validate_launch(job, context, h)
    owned=parent();root=context['source_root'];package_pins=context['package_pins']
    output.mkdir(mode=0o700);(output/'actors').mkdir(mode=0o700);(output/'status-samples').mkdir(mode=0o700)
    stopped=threading.Event();bridge_stop=threading.Event();health_stop=threading.Event()
    cleanup_event=threading.Event();cleanup_state={};errors=[];failures=[];actors={};streams=[]
    main_lock=threading.Lock();main_guard=main_finalizer=health_worker=None
    main_report=main_failure=main_initial=None;main_samples=[]
    server=actor=lifecycle=server_worker=None;client_threads=[];owned_threads=[]
    retained_clients=();retained_inference=None;captured_all_original_writers=False;cleanup_timers=()
    lease=owned.PrivateLease(job['lease']);lease_entry=None;released=False
    policy_before=policy_after=acquisition=library_entry=compile_before=None
    anchor_pin=seal_pin=cleanup_pin=restoration=None;barrier=None
    all_threads_stopped=False;child_reap=None;source_unchanged=False
    started=time.monotonic();native_deadline=started+4200
    previous={sig:signal.signal(sig,lambda *_:stopped.set()) for sig in (signal.SIGTERM,signal.SIGINT)}
    gate=modules['hooks'].DeadlineExchangeGate();recorder=modules['recorder'].DeadlineScoreRecorder()
    registration=modules['hooks'].FirstGameRegistration()
    try:
        lease_entry=lease.acquire();h.put(output/'original-lease.json',lease_entry)
        gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=10)
        require(gpu.returncode==0 and GPU not in gpu.stdout,'Private GPU0 is not idle')
        h.put(output/'original-GPU-before.json',dict(exit=gpu.returncode,stdout=gpu.stdout,stderr=gpu.stderr))
        reader=context['reader'];protocol=context['protocol'];family=context['family']
        validate_main_health_contract(job,protocol,family)
        client=load('_deadline_health_client',h.checked(family['main_observer']['client']))
        main_finalizer=load('_deadline_main_finalizer',h.checked(family['main_health_finalizer']))
        main_guard=client.DedicatedMainHealth(job,jp,protocol,family,h,started=started,deadline=native_deadline,prior_groups=[])
        main_guard.start()
        def collect_main():
            value=main_guard.observe();main_samples.append(value);return value
        def check_main(require_closed=False):
            while True:
                with main_lock:value=collect_main()
                if not require_closed or not value['phase']['overlap_pending']:return value
                require(time.monotonic()<native_deadline and not stopped.is_set(),'No late main-health rescue')
                time.sleep(.2)
        initial=check_main(require_closed=True);ready=main_guard.initial
        require(ready['index'] is not None and not initial['phase']['overlap_pending'],'Initial main proof must close before private setup')
        main_initial=h.put(output/'original-initial-main-readiness.json',dict(schema='robotron-native-initial-main-readiness-v1',
            original_job=jp,runtime=job['runtime'],main_health_protocol=job['main_health_protocol'],
            first_qualified_baseline_index=ready['index'],first_qualified_baseline_unix_s=ready['unix_s'],
            unaccepted_initial_samples=ready['unaccepted_samples'],observed_monotonic_s=time.monotonic(),
            observed_unix_s=time.time(),
            before_sidecar_Torch_policy_or_MAME=True,quality_qualified=False))
        def watch_main():
            while not health_stop.wait(.2):
                try:
                    with main_lock:
                        if health_stop.is_set():return
                        collect_main()
                except Exception as error:
                    errors.append('Original independent main-health watch: '+repr(error));stopped.set();return
        health_worker=threading.Thread(target=watch_main,name='deadline32-main-health',daemon=True);health_worker.start()
        sidecar=load('_deadline_frozen_sidecar',root/'tools/run_frozen_sidecar.py')
        sidecar.configure_environment(SimpleNamespace(directory=output,gpu_uuid=GPU,device='cuda',
            completion_policy='confirmed_reset_reserves_v1',game_boundary_diagnostics=True,cpu_threads=2))
        sys.path.insert(0,str(root/'Scripts'))
        import torch
        from dqn import config
        from dqn.inference_actor import InferenceActor
        from dqn.socket_server import SocketServer,parse_frame_data
        torch.set_num_threads(2);torch.set_num_interop_threads(1);config.RL_CONFIG.inference_batch_max_size=16
        source=h.checked(job['checkpoint']);checkpoint=output/'checkpoint.pt'
        import shutil
        with source.open('rb') as incoming,checkpoint.open('xb') as outgoing:
            shutil.copyfileobj(incoming,outgoing);outgoing.flush();os.fsync(outgoing.fileno());os.fchmod(outgoing.fileno(),0o444)
        acquisition=h.pin(checkpoint);require(acquisition['sha256']==job['checkpoint']['sha256'],'Acquired policy changed')
        actor=InferenceActor(checkpoint,device='cuda:0',inference_backend='inductor');metadata=actor.checkpoint_metadata
        require(all(type(metadata.get(k)) is int and metadata[k]==v for k,v in job['expected_policy_clocks'].items()),'Loaded policy clocks differ')
        # The exact frozen InferenceActor exports validated numeric clocks only;
        # saved recipe identity belongs to the SHA-bound prior CPU verification
        # and the prebody source/baseline context, never an invented actor field.
        for key in ('learner_frame_count','frame_count','measurement_frame_count'):setattr(config.metrics,key,int(metadata[key]))
        config.metrics.total_training_steps=actor.training_steps;config.metrics.total_optimized_samples=actor.optimized_samples
        config.metrics.training_enabled=False;config.metrics.preview_capture_enabled=False;config.metrics.hud_enabled=False
        for key,value in dict(start_advanced=False,start_level_min=1,epsilon_pct=0,expert_pct=0,auto_curriculum=False,difficulty=5).items():setattr(config.game_settings,key,value)
        require(torch.cuda.device_count()==1 and os.environ['CUDA_VISIBLE_DEVICES']==GPU and actor.memory is actor.optimizer is None,'Actual inference isolation differs')
        server=SocketServer('127.0.0.1',19998,actor,replay_enabled=False)
        def boundary(generation):return server.measurement_boundary_status(generation)
        lifecycle=modules['lifecycle'].DeadlineMeasurementLifecycle(actor,config.metrics,server.game_journal,boundary_status=boundary)
        lifecycle.enter(job['measurement_label'])
        policy_reader=modules['clock_authority'].live_policy_reader(actor,config.metrics,server,config.game_settings,
            checkpoint_path=checkpoint,checkpoint_sha256=acquisition['sha256'],actor_source_sha256=job['actor_source_sha256'])
        policy_before=policy_reader();compile_before=copy.deepcopy(actor.compile_report)
        require(policy_before['numeric_policy']['compiled'] is True and compile_before['all_shapes_verified']==list(range(1,17)),
                'Actual common compiled backend not ready')
        selected_policy=dict(policy_sha256=policy_before['checkpoint_sha256'],measurement_generation=lifecycle.generation,
            experiment=job['measurement_label'],policy_clocks={k:policy_before[k] for k in ('learner_frame_count','training_steps','optimized_samples')})
        bridge=modules['hooks'].build_deadline_proxy(modules['clock_proxy'].StartupProxy,
            expected_base_sha256=job['components']['clock_proxy']['sha256'],recorder=recorder,gate=gate,
            policy=selected_policy,on_cutoff=gate.retire_received_request)
        h.put(output/'original-loaded-policy.json',dict(policy=policy_before,compile_report=compile_before,
            gpu_uuid=GPU,CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'],replay_enabled=False,memory_is_none=True,optimizer_is_none=True))
        check_main();seed=load('_deadline_seed_restore',h.checked(job['seed_runtime']))
        builder=load('_deadline_wait_builder',root/'tools/build_socket_wait.py');library=builder.build(output/'socket-wait-build')
        library.chmod(0o444);library_entry=h.pin(library)
        def admission():return copy.deepcopy(lifecycle.fixed_admission)
        server_worker=threading.Thread(target=server.start,name='deadline32-origin',daemon=True);server_worker.start()
        ready_end=min(native_deadline,time.monotonic()+15)
        while not server.running:
            require(server_worker.is_alive() and time.monotonic()<ready_end,'Original origin did not bind');time.sleep(.01)
        prepare_actors(job=job,output=output,server=server,h=h,seed=seed,bridge=bridge,ledger=modules['clock_ledger'],
            bridge_stop=bridge_stop,policy_reader=policy_reader,admission=admission,frame_parser=parse_frame_data,
            registration=registration,actors=actors,streams=streams,errors=errors,failures=failures,
            cleanup_event=cleanup_event,cleanup_state=cleanup_state,hooks=modules['hooks'])
        for slot,row in actors.items():
            require(not stopped.is_set() and time.monotonic()<native_deadline,'Interrupted during actor launch')
            row['worker'].start();row['worker_started']=True;private=row['private']
            env=owned.actor_environment(os.environ,private,slot,job['sessions'][str(slot)],job['connections'][str(slot)],library)
            out=(private/'actor-stdout.txt').open('xb');err=(private/'actor-stderr.txt').open('xb');streams.extend((out,err))
            argv=owned.actor_command(job,private)
            child=subprocess.Popen(argv,stdout=out,stderr=err,stdin=subprocess.DEVNULL,env=env,cwd=private)
            row.update(child=child,birth=owned.process_birth(child.pid));require(row['birth'] is not None,'Original birth unavailable')
            h.put(private/'original-actor.json',dict(pid=child.pid,starttime_ticks=row['birth'],slot=slot,
                session=job['sessions'][str(slot)],connection=job['connections'][str(slot)],argv=argv,original_job=jp,
                trace_identity=row['trace_identity'],lifecycle_identity=row['lifecycle_identity'],proxy_port=PORTS[slot],boot_restore=row['boot_restore']))
        status_index=0;last_status=0;anchor=None
        while True:
            require(time.monotonic()<native_deadline and not stopped.is_set(),'Native bound/interruption')
            require(not errors and server.inference_only_error is None and server_worker.is_alive() and server.running,
                    'Actual private source/runtime failure is never censoring')
            for slot,row in actors.items():
                require(row['child'].poll() is None and owned.process_birth(row['child'].pid)==row['birth'] and
                        row['proxy'].error is None and row['worker'].is_alive(),'All32 original actors/proxies must remain active until D')
            window=lifecycle.admit_when_ready()
            if anchor is None:
                require(time.monotonic()-started<300,'All32 certified first-play prefixes exceeded startup300')
                if window is not None and all(row['proxy'].prefix_verified.is_set() and row['proxy'].sequence>1200 for row in actors.values()):
                    require(policy_reader()==policy_before and actor.compile_report==compile_before,'Frozen startup policy changed')
                    retained_clients,retained_inference=capture_origin_writers(server)
                    captured_all_original_writers=True
                    anchor=modules['hooks'].arm_ready32({s:r['proxy'] for s,r in actors.items()},lifecycle.guard(),recorder,gate,selected_policy)
                    anchor_pin=h.put(output/'original-deadline-anchor.json',dict(schema='robotron-deadline32-origin-anchor-v1',anchor=anchor,
                        policy=selected_policy,fixed_admission=window,original_job=jp,
                        prefixes={str(s):dict(summary=r['proxy'].prefix_summary,handoff=r['proxy'].handoff,sequence=r['proxy'].sequence) for s,r in actors.items()}))
            elif time.monotonic_ns()>=anchor['deadline_monotonic_ns']:
                policy_after=policy_reader();require(policy_after==policy_before and actor.compile_report==compile_before,'Frozen cutoff policy changed')
                barrier=gate.close_and_drain()
                require(not errors and server.inference_only_error is None,'Runtime failure before seal cannot become censoring')
                seal=recorder.seal(time.monotonic_ns(),barrier=barrier)
                seal_pin=h.put(output/'original-deadline-score-seal.json',seal);lifecycle.mark_sealed(seal_pin)
                gate.mark_sealed()
                table=modules['report'].format_console(seal)
                with (output/'original-deadline-score-table.txt').open('x') as stream:stream.write(table);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o444)
                print(table,flush=True)
                begin=time.monotonic_ns();cleanup_state.update(begin_monotonic_ns=begin,score_seal=seal_pin)
                require(not errors and server.inference_only_error is None and not server.shutdown_event.is_set(),'Fault before intentional teardown')
                current_clients,current_inference=capture_origin_writers(server)
                require(set(current_clients)==set(retained_clients) and current_inference is retained_inference,
                        'Actual original writer identities changed before intentional shutdown')
                cleanup_event.set();declared=time.monotonic_ns();cleanup_state['declared_monotonic_ns']=declared
                server.shutdown_event.set();after=time.monotonic_ns()
                cleanup_pin=h.put(output/'original-intentional-deadline-cleanup.json',dict(schema='robotron-deadline32-intentional-cleanup-v1',
                    begin_monotonic_ns=begin,declared_monotonic_ns=declared,after_flags_monotonic_ns=after,
                    score_sealed_monotonic_ns=seal['seal_observed_monotonic_ns'],original_score_seal=seal_pin,
                    original_barrier=barrier,errors_before=[],inference_error_before=None,
                    server_shutdown_set_before_owned_signals=True,all32_original_children_live_before_cutoff=True))
                gate.declare_teardown(server_shutdown_is_set=server.shutdown_event.is_set())
                # Every blocked post-D request retires through the dedicated
                # positively gated exception before any origin/actor close.
                end=(anchor['deadline_monotonic_ns']+3_500_000_000)/1e9
                for row in actors.values():row['worker'].join(max(0,end-time.monotonic()))
                require(all(r['retired'].is_set() and not r['worker'].is_alive() for r in actors.values()),'Every32 original proxy must retire after its sealed cutoff')
                require(not errors,'Unexpected source/runtime failure during deadline retirement')
                check_main(require_closed=True);break
            if time.monotonic()-last_status>=5:
                current=dict(schema='robotron-deadline32-live-status-v1',original_job=jp,leg=job['leg'],
                    observed_unix_s=time.time(),phase='startup' if anchor is None else 'active_deadline',
                    anchor=anchor,n_selected_first_games=len(registration.registered),n_scored=None,n_completed=None,n_censored=None,
                    deadline_scores_sealed=False,lifecycle=lifecycle.status(),errors=list(errors),
                    slots={str(s):dict(pid=r['child'].pid,birth=r['birth'],sequence=r['proxy'].sequence,
                        prefix_verified=r['proxy'].prefix_verified.is_set(),ledger=r['proxy'].ledger.summary()) for s,r in actors.items()})
                h.put(output/'status-samples'/f'{status_index:04d}.json',current);status_index+=1
                temp=output/'status.next.json'
                with temp.open('w') as stream:json.dump(current,stream,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
                os.replace(temp,output/'status.json');last_status=time.monotonic()
            time.sleep(.01)
    except Exception as error:errors.append(repr(error))
    finally:
        # Unexpected failures keep their original errors, flags and raw logs.
        # No post-hoc cutoff snapshot is invented in this cleanup path.
        if server is not None:
            fallback_clients,fallback_inference=capture_origin_writers(server,require_all32=False)
            client_threads=list(dict.fromkeys((*retained_clients,*fallback_clients)))
            if retained_inference is None:retained_inference=fallback_inference
            try:server.stop()
            except Exception as error:errors.append('Original origin stop: '+repr(error))
        bridge_stop.set()
        for row in actors.values():
            child=row['child']
            if child is not None and child.poll() is None:
                try:
                    require(owned.process_birth(child.pid)==row['birth'],'Changed original birth; no signal');child.terminate()
                except Exception as error:errors.append('Original actor cleanup: '+repr(error))
            row['listener'].close()
        join_end=min(native_deadline,time.monotonic()+20)
        owned_threads=[server_worker,*client_threads,retained_inference,*[r['worker'] for r in actors.values() if r['worker_started']]]
        for worker in owned_threads:
            if worker is not None:
                worker.join(max(0,join_end-time.monotonic()))
                if worker.is_alive():errors.append('Original thread completion unknown: '+worker.name)
        if server is not None and all(not t.is_alive()for t in client_threads):
            cleanup_timers=owned_cleanup_timers(server)
            for timer in cleanup_timers:
                timer.join(max(0,join_end-time.monotonic()))
                if timer.is_alive():errors.append('Original server cleanup Timer completion unknown')
            owned_threads.extend(cleanup_timers)
        if main_guard is not None and main_finalizer is not None:
            value=main_finalizer.finalize(main_guard,health_worker,health_stop,main_lock,collect_main,native_deadline,h,output/'main-observations',case_already_failed=bool(errors))
            main_report=value['report'];main_failure=value['failure'];errors.extend(value['errors']);main_samples=value['statuses']
        else:
            health_stop.set()
            if health_worker is not None:health_worker.join(timeout=20)
        owned_threads.append(health_worker)
        all_threads_stopped=captured_all_original_writers and all(w is None or not w.is_alive() for w in owned_threads)
        try:
            child_reap=owned.await_original_actor_exits(actors)
            require(child_reap['all_original_children_reaped'],'Original child completion unknown')
        except Exception as error:errors.append('Original actor reap: '+repr(error))
        if server is not None and server.inference_only_error is not None:errors.append('Actual inference error: '+server.inference_only_error)
        if lifecycle is not None:
            try:restoration=lifecycle.exit(all_original_threads_stopped=all_threads_stopped)
            except Exception as error:errors.append('Actual measurement restoration: '+repr(error))
        if actor is not None:
            try:actor.close()
            except Exception as error:errors.append('Actual actor close: '+repr(error))
        for stream in streams:
            try:stream.flush();os.fsync(stream.fileno());stream.close()
            except Exception as error:errors.append('Original stream close: '+repr(error))
        for sig,handler in previous.items():signal.signal(sig,handler)
    try:
        for entry in job['inputs']+package_pins:h.checked(entry)
        require(acquisition is None or h.pin(acquisition['path'])==acquisition,'Acquired policy changed')
        source_unchanged=True
    except Exception as error:errors.append('Final source check: '+repr(error))
    actual_slots={}
    for slot,row in actors.items():
        value=owned.finalize_actor_outputs(row,bool(child_reap and child_reap['all_original_children_reaped']),all_threads_stopped,h.pin)
        child=row['child']
        actual_slots[str(slot)]=dict(pid=None if child is None else child.pid,birth=row['birth'],actual_exit=None if child is None else child.poll(),
            frames=row['proxy'].sequence,handoff=row['proxy'].handoff,prefix_summary=row['proxy'].prefix_summary,
            footer=None if row['proxy'].prefix_summary is None else row['proxy'].prefix_summary['footer'],
            files=value['files'],outputs_sealed_after_original_writer_closure=value['outputs_sealed_after_original_writer_closure'],
            original_unsealed_output_paths=value['original_unsealed_output_paths'],boot_restore=row['boot_restore'],
            trace_identity=row['trace_identity'],lifecycle_identity=row['lifecycle_identity'],
            expected_deadline_retirement=row['retired'].is_set(),actual_proxy_error=row['proxy'].error)
        if cleanup_pin is not None:
            actual_slots[str(slot)]['intentional_cleanup']=dict(begin_monotonic_ns=cleanup_state['begin_monotonic_ns'],
                declared_monotonic_ns=cleanup_state['declared_monotonic_ns'],
                after_flags_monotonic_ns=after,score_sealed_monotonic_ns=seal['seal_observed_monotonic_ns'])
    journal={}
    for name in ('games.jsonl','lives.jsonl','measurement_starts.jsonl'):
        path=output/'journal'/name
        if path.is_file() and all_threads_stopped and child_reap and child_reap['all_original_children_reaped']:
            path.chmod(0o444);journal[name]=h.pin(path)
    if lease.fd is not None:
        try:
            require(all(r['child'] is None or r['child'].poll() is not None for r in actors.values()) and all_threads_stopped
                    and (main_guard is None or main_guard.child is None or main_guard.scope_complete),'Unknown owned completion; preserve lease')
            lease.release();released=True
        except Exception as error:errors.append('Original private lease cleanup: '+repr(error))
    complete=bool(not errors and seal_pin is not None and cleanup_pin is not None and len(actual_slots)==32 and
        policy_before==policy_after and policy_after is not None and source_unchanged and released and
        main_report is not None and main_initial is not None and main_guard.scope_complete and
        main_guard.lifecycle is not None and restoration and restoration['metric_sealed'])
    result=h.put(output/'result.json',dict(schema='robotron-deadline32-original-leg-result-v1',
        status='ORIGINAL_DEADLINE32_SEALED_AND_CLOSED' if complete else 'ORIGINAL_DEADLINE32_FAILED_NO_RETRY',
        complete=complete,errors=errors,original_job=jp,leg=job['leg'],attempt=1,no_retry=True,
        original_slots=actual_slots,deadline_anchor=anchor_pin,deadline_score_seal=seal_pin,
        intentional_cleanup=cleanup_pin,private_failure_events=failures,original_barrier=barrier,
        policy_before=policy_before,policy_after=policy_after,acquired_checkpoint=acquisition,
        expected_policy_clocks=job['expected_policy_clocks'],compile_report=compile_before,
        measurement_restoration=restoration,journal=journal,main_samples=main_samples,
        main_health_report=main_report,main_health_failure=main_failure,initial_main_readiness=main_initial,
        main_health_protocol=job['main_health_protocol'],source_family_manifest=job['source_family_manifest'],
        main_observer_lifecycle=None if main_guard is None else main_guard.lifecycle,
        native_started_monotonic_s=started,native_deadline_monotonic_s=native_deadline,
        original_post_origin_child_reap=child_reap,all_original_threads_stopped=all_threads_stopped,
        original_writer_capture=dict(all32_client_thread_objects_retained_before_shutdown=captured_all_original_writers,
            retained_client_threads=len(retained_clients),retained_inference_thread=retained_inference is not None,
            original_cleanup_timers_joined=len(cleanup_timers),all_retained_writers_stopped=all_threads_stopped),
        lease=lease_entry,original_lease_released=released,socket_wait_library=library_entry,
        immutable_inputs_unchanged=source_unchanged,full_game_quality_qualified=False,
        deadline_metric_independently_qualified=False,improvement_qualified=False,
        main_runtime_changed=False,promotion_gates_changed=False))
    print(json.dumps(dict(result=result,complete=complete)),flush=True);return 0 if complete else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job');parser.add_argument('--job-sha256');parser.add_argument('--source-sha256');args=parser.parse_args()
    if not args.execute:print('PLAN_ONLY: no model, GPU, emulator, socket or outputs');return 0
    require(args.source_sha256==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'Exact runtime source SHA required')
    path=Path(args.job);raw=path.read_bytes();require(hashlib.sha256(raw).hexdigest()==args.job_sha256,'Exact native job SHA required')
    job=json.loads(raw);owned=parent();h=owned.helpers();jp=h.pin(path)
    return run(job,jp,h)


if __name__=='__main__':raise SystemExit(main())
