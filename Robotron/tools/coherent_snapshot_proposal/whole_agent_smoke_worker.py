#!/usr/bin/env python3
"""Private worker. Never invoke directly; the guarded parent owns its cgroup.

There are intentionally no numerical imports at module scope. The executable
bootstrap verifies the parent token, ownership, cgroup and GPU/quality guards
before importing Torch, NumPy or the copied candidate package.
"""
from __future__ import annotations
import argparse
import ctypes
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import threading
import time
import traceback
from types import SimpleNamespace
import uuid

HERE=Path(__file__).resolve().parent


def launcher_module():
    name='_private_snapshot_smoke_launcher'
    spec=importlib.util.spec_from_file_location(name,HERE/'whole_agent_smoke.py')
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canonical_uuid(value):
    return str(value).lower().removeprefix('gpu-').replace('-','')


def arm_parent_death_signal(expected_pid, *, libc=None):
    library=ctypes.CDLL(None,use_errno=True) if libc is None else libc
    function=library.prctl
    function.argtypes=[ctypes.c_int,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong]
    function.restype=ctypes.c_int
    require(function(1,int(signal.SIGKILL),0,0,0)==0,'Unable to arm Linux parent-death protection')
    require(os.getppid()==expected_pid,'Parent exited while arming lifetime protection')


def reset_inherited_signal_mask():
    # Popen is intentionally protected by the parent's blocked cleanup signals.
    # Exec retains that mask; the worker must accept TERM/INT/HUP itself.
    signal.pthread_sigmask(signal.SIG_UNBLOCK,(signal.SIGINT,signal.SIGTERM,signal.SIGHUP))


def bootstrap(manifest_path, phase, *, token_reader=None):
    parent=launcher_module()
    parent.regular(manifest_path)
    manifest=json.loads(Path(manifest_path).read_text())
    require(manifest['explicit_launch'] is True,'Explicit parent launch is required')
    require(manifest['schema']=='robotron-private-whole-agent-smoke-v1','Unknown manifest')
    require(manifest['gpu_uuid']==parent.GPU0_UUID and manifest['forbidden_gpu_uuid']==parent.MAIN_GPU_UUID,
            'GPU manifest identity differs')
    require(manifest['bounds']==parent.BOUNDS,'Resource manifest differs')
    require(os.getppid()==manifest['parent']['pid'] and parent.identity(os.getppid())==manifest['parent'],
            'Worker is not owned by its recorded parent')
    arm_parent_death_signal(manifest['parent']['pid'])
    reset_inherited_signal_mask()
    layout=parent.Layout(Path(manifest['output']),manifest['nonce'],Path(manifest['tmpfs']).parent)
    require(str(layout.tmpfs)==manifest['tmpfs'],'Unexpected tmpfs identity')
    require(Path(manifest_path)==layout.output/'launch-manifest.json','Manifest is not in owned output')
    parent.check_directory(layout.output,manifest['output_identity'])
    parent.check_directory(layout.tmpfs,manifest['tmpfs_identity'])
    require(parent.digest(HERE/'whole_agent_smoke.py')==manifest['launcher_sha256'] and
            parent.digest(__file__)==manifest['worker_sha256'],'Harness source changed')
    # Parent attaches this child only after Popen returns. Wait for its token
    # before inspecting cgroup membership; no numerical import precedes either.
    token=(token_reader or (lambda:sys.stdin.buffer.readline(128)))()
    require(token==(manifest['launch_token']+'\n').encode(),'Missing parent launch token')
    cg=Path(manifest['cgroup'])
    parent.check_directory(cg,manifest['cgroup_identity'])
    unified=[row.split(':',2)[2] for row in Path('/proc/self/cgroup').read_text().splitlines() if row.startswith('0::')]
    require(len(unified)==1 and Path('/sys/fs/cgroup')/unified[0].lstrip('/')==cg,
            'Worker has not joined its owned bounded cgroup')
    require(os.getpid() in [int(value) for value in (cg/'cgroup.procs').read_text().split()],
            'Worker cgroup membership is missing')
    for name, expected in {'memory.max':str(parent.BOUNDS['memory_bytes']),'memory.swap.max':'0',
            'memory.oom.group':'1','pids.max':str(parent.BOUNDS['tasks']),'cpu.max':'200000 100000'}.items():
        require((cg/name).read_text().strip()==expected,'Cgroup limit differs: '+name)
    expected_env=parent.configure_environment(layout,phase)
    for name, expected in expected_env.items():
        require(os.environ.get(name)==expected,'Private environment differs: '+name)
    require('LD_PRELOAD' not in os.environ and 'PYTHONPATH' not in os.environ,'Inherited import/preload hooks forbidden')
    for name in os.environ:
        if name.startswith(('DQN_','ROBOTRON_')):
            require(name in expected_env,'Unexpected inherited training environment: '+name)
    require(Path.cwd()==layout.output/'private','Worker cwd differs')
    parent.verify_source_copies(layout,manifest['sources'])
    parent.guard_live_resources(allowed_pids={os.getpid(),os.getppid()},expected_main=manifest['main_owners'],initial=True)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(1<<30,1<<30))
    resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
    return parent,manifest,layout


def assert_private_modules(layout):
    package=layout.scripts/'dqn'
    for name,module in list(sys.modules.items()):
        if name=='dqn' or name.startswith('dqn.'):
            filename=getattr(module,'__file__',None)
            require(filename is not None and Path(filename).resolve().is_relative_to(package),
                    'Candidate import escaped private package: '+name)


def setup(parent,manifest,layout,phase):
    # bootstrap is the only caller; every guard and cgroup check precedes here.
    import numpy as np
    import torch
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    require(torch.cuda.device_count()==1,'CUDA visibility must contain exactly display GPU0')
    require(canonical_uuid(torch.cuda.get_device_properties(0).uuid)==canonical_uuid(parent.GPU0_UUID),
            'CUDA UUID differs from approved display GPU0')
    free,total=torch.cuda.mem_get_info(0)
    require(free>=11*parent.GIB,'Post-context GPU free margin is insufficient')
    torch.cuda.set_per_process_memory_fraction(parent.BOUNDS['vram_allocator_bytes']/total,0)
    paths=layout.phase(phase)
    for key in ('models','tmpfs','journal','cache'):
        parent.directory_identity(paths[key])
        require(paths[key].resolve()==paths[key] and
                paths[key].is_relative_to(layout.tmpfs if key=='tmpfs' else layout.output),
                'Phase path escaped owned roots')
    require(not any(name=='dqn' or name.startswith('dqn.') for name in sys.modules),'Candidate package was imported early')
    sys.path[:]=[value for value in sys.path if value not in ('',str(parent.REPO),str(parent.GAME/'Scripts'))]
    sys.path.insert(0,str(layout.scripts))
    config=importlib.import_module('dqn.config')
    cfg=config.RL_CONFIG
    values=dict(memory_size=128,batch_size=8,min_replay_to_train=32,replay_tmpfs_dir=str(paths['tmpfs']),
        hof_enabled=True,ephof_enabled=True,hof_max_episodes=2,ephof_max_episodes=2,
        hof_episode_stride=64,ephof_episode_stride=64,hof_min_transitions=1,ephof_min_transitions=1,
        hof_min_game_score=0,ephof_min_episode_score=0,interesting_replay_bank_size=128,
        replay_live_mmap=True,replay_flush_msync=True,replay_prefetch=True,replay_prefetch_slots=2,
        use_torch_compile=False,compile_full_loss=False,optimizer_fused=True,enable_amp=True,
        inference_on_cpu=False,use_separate_inference_model=True,inference_batching_enabled=False,
        ratchet_enabled=False,training_steps_per_cycle=1,replay_direct_state_fill=False)
    for name,value in values.items():
        require(hasattr(cfg,name),'Unknown bounded configuration field: '+name)
        setattr(cfg,name,value)
    require(cfg.state_size==11128 and cfg.frame_stack==4,'Actual stacked network geometry changed')
    require(Path(config.MODEL_DIR)==paths['models'] and Path(config.LATEST_MODEL_PATH)==paths['models']/'robotron_dqn_latest.pt'
            and config.learning_control.path==paths['control'],'Import-time model/control paths escaped')
    metrics=config.metrics
    metrics.training_enabled=False
    metrics.coherent_snapshot_keyboard_disabled=True  # No keyboard object/thread is ever constructed.
    metrics.measurement_active=False
    metrics.ratchet_frozen=False
    if phase=='capture':
        config.game_settings.save()
    module=importlib.import_module('dqn.agent')
    assert_private_modules(layout)
    ring=paths['tmpfs']/'robotron_dqn_latest_replay'
    banks={bank:paths['models']/('robotron_dqn_latest_replay_'+bank) for bank in ('hof','ephof')}
    if phase=='capture':
        require(not ring.exists() and not any(value.exists() for value in banks.values()),'Capture paths are not fresh')
    else:
        require((ring/'_meta.npy').is_file() and all((value/'CURRENT.json').is_file() for value in banks.values()),
                'Restore artifacts were not staged before construction')
    agent=None
    try:
        agent=module.RainbowAgent(cfg.state_size)
        agent.training_enabled=False
        require(agent.device==torch.device('cuda:0') and agent.inference_device==torch.device('cuda:0'),
                'Agent selected an unapproved device')
        require(all(isinstance(net,module.RainbowNet) for net in (agent.online_net,agent.target_net,agent.infer_net)),
                'Full Rainbow networks were not constructed')
        require(agent.optimizer.defaults.get('fused') is True and all(group.get('fused') is True for group in agent.optimizer.param_groups),
                'Fused Adam fallback is forbidden')
        require(agent.use_amp and agent.grad_scaler.is_enabled(),'Enabled CUDA AMP/scaler required')
        require(agent._prefetcher is not None and agent._prefetcher._thread.is_alive(),'Actual replay prefetch is missing')
        require(Path(agent._ring_dir)==ring and all(Path(getattr(agent.memory,'_'+bank+'_dir'))==value for bank,value in banks.items()),
                'Constructor replay/bank path differs')
        agent._train_queue.put(None,timeout=1)
        agent._train_thread.join(timeout=10)
        require(not agent._train_thread.is_alive(),'Background learner did not join')
        assert_private_modules(layout)
    except BaseException:
        if agent is not None:
            agent.stop()
        raise
    return SimpleNamespace(parent=parent,manifest=manifest,layout=layout,phase=phase,paths=paths,
        np=np,torch=torch,config=config,cfg=cfg,metrics=metrics,module=module,agent=agent,ring=ring,banks=banks,
        server=None,server_thread=None,consumer=None,server_errors=[])


def finite_tensors(ctx,value):
    torch=ctx.torch
    if isinstance(value,torch.Tensor):
        require(bool(torch.isfinite(value).all().item()),'Nonfinite tensor observed')
    elif isinstance(value,dict):
        for item in value.values():finite_tensors(ctx,item)
    elif isinstance(value,(list,tuple)):
        for item in value:finite_tensors(ctx,item)
    elif isinstance(value,float):
        require(math.isfinite(value),'Nonfinite scalar observed')


def nested_equal(ctx,left,right):
    torch=ctx.torch
    if isinstance(left,torch.Tensor):
        require(isinstance(right,torch.Tensor) and left.dtype==right.dtype and torch.equal(left.detach().cpu(),right.detach().cpu()),
                'Persisted tensor differs')
    elif isinstance(left,dict):
        require(left.keys()==right.keys(),'Persisted mapping keys differ')
        for name in left:nested_equal(ctx,left[name],right[name])
    elif isinstance(left,(list,tuple)):
        require(len(left)==len(right),'Persisted sequence length differs')
        for x,y in zip(left,right):nested_equal(ctx,x,y)
    else:
        require(left==right,'Persisted scalar differs: '+repr((left,right)))


def optimizer_steps(ctx):
    values=[float(state['step'].detach().cpu()) for state in ctx.agent.optimizer.state.values() if 'step' in state]
    return max(values,default=0.)


def model_digest(ctx):
    import hashlib
    digest=hashlib.sha256()
    for name,value in ctx.agent.online_net.state_dict().items():
        digest.update(json.dumps([name,str(value.dtype),list(value.shape)]).encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def classify_optimizer_attempt(before,after,*,loss,gradients_finite,persistent_finite):
    """Admit a real update or a positively proven AMP skip; never guess.

    Pure host-scalar validation permits CPU tests without importing Torch. Adam
    observations include EVERY optimizer parameter, with absent lazy slots=0.
    """
    try:
        require(loss is not None and math.isfinite(float(loss)),'Missing/nonfinite update loss')
        require(persistent_finite is True,'Nonfinite or unverified persistent state')
        fields=('attempts_started','outcomes_recorded','applied','amp_skipped','unavailable')
        for observation in (before,after):
            require(isinstance(observation,dict),'Missing optimizer observation')
            scale=observation['scale']
            require(not isinstance(scale,bool) and math.isfinite(float(scale)) and float(scale)>0,'Invalid scaler scale')
            steps=observation['adam_steps']
            require(isinstance(steps,dict) and bool(steps),'Missing Adam parameter steps')
            for name,step in steps.items():
                require(isinstance(name,str) and bool(name) and not isinstance(step,bool) and
                        math.isfinite(float(step)) and float(step)>=0,'Invalid Adam parameter step')
            for name in ('online_sha256','adam_nonzero_state_sha256'):
                value=observation[name]
                require(isinstance(value,str) and len(value)==64 and all(letter in '0123456789abcdef' for letter in value),
                        'Missing state digest: '+name)
            exposure=observation['exposure']
            require(exposure['schema']=='robotron-optimizer-exposure-v1' and exposure['enabled'] is True,
                    'Unsupported optimizer exposure')
            require(exposure['unclassified_started_total']==0 and exposure['prior_epoch_outcomes_total']==0,
                    'Unfinished or cross-epoch optimizer outcome')
            total=exposure['total']
            require(all(type(total[name]) is int and total[name]>=0 for name in fields),'Malformed optimizer counters')
            require(total['attempts_started']==total['outcomes_recorded']==
                    total['applied']+total['amp_skipped']+total['unavailable'],'Unclassified optimizer counters')
        previous,current=before['exposure'],after['exposure']
        for name in ('process_id','instance_monotonic_ns','epoch','epoch_reason','supported_torch'):
            require(previous.get(name)==current.get(name),'Optimizer exposure identity/epoch/source changed: '+name)
        for name in ('process_id','instance_monotonic_ns','epoch'):
            require(type(current[name]) is int and current[name]>=0,'Missing exposure identity: '+name)
        require(previous['available'] is True or previous['available'] is False and
                all(previous['total'][name]==0 for name in fields),'Unavailable prior optimizer exposure')
        require(current['available'] is True and current['last_reason']=='single_cuda_found_inf',
                'AMP outcome unavailable or unsupported')
        require(previous['total']['unavailable']==0,'Prior unsupported optimizer outcome')
        delta={name:current['total'][name]-previous['total'][name] for name in fields}
        require(delta['attempts_started']==delta['outcomes_recorded']==1 and delta['unavailable']==0,
                'Expected exactly one classified optimizer attempt')
        old,new=before['adam_steps'],after['adam_steps']
        require(old.keys()==new.keys(),'Adam optimizer parameter set changed')
        unchanged=all(float(old[name])==float(new[name]) for name in old)
        if delta['amp_skipped']==1 and delta['applied']==0:
            require(unchanged and before['online_sha256']==after['online_sha256'] and
                    before['adam_nonzero_state_sha256']==after['adam_nonzero_state_sha256'],
                    'AMP-skip claim disagrees with Adam or online mutation')
            require(float(after['scale'])<float(before['scale']),'AMP skip did not lower a finite scaler scale')
            return 'amp_skipped'
        require(delta['applied']==1 and delta['amp_skipped']==0,'Ambiguous optimizer outcome')
        require(gradients_finite is True,'Applied update has nonfinite or unverified gradients')
        require(all(float(new[name])>=float(old[name]) for name in old) and not unchanged,
                'Applied update lacks nonregressing Adam step advancement')
        require(before['online_sha256']!=after['online_sha256'],'Applied update did not change online state')
        return 'applied'
    except (KeyError,TypeError,ValueError,OverflowError,AttributeError) as error:
        raise RuntimeError('Malformed optimizer-attempt evidence: '+str(error)) from error


def optimizer_observation(ctx):
    """Full per-slot steps plus zero-normalized Adam state, no tensors retained.

    Fused Adam may allocate step0/all-zero moments even when AMP skips its first
    call. Those fresh zeros are equivalent to absent lazy state; any nonzero
    state or per-slot advancement changes the evidence.
    """
    import hashlib
    agent=ctx.agent
    names={id(parameter):name for name,parameter in agent.online_net.named_parameters()}
    steps={}
    digest=hashlib.sha256()
    for group in agent.optimizer.param_groups:
        for parameter in group['params']:
            name=names.get(id(parameter))
            require(name is not None and name not in steps,'Optimizer parameter ownership differs')
            state=agent.optimizer.state.get(parameter,{})
            step=state.get('step',0.)
            steps[name]=float(step.detach().cpu()) if isinstance(step,ctx.torch.Tensor) else float(step)
            for key,value in sorted(state.items()):
                if key=='step':continue
                if isinstance(value,ctx.torch.Tensor):
                    host=value.detach().cpu().contiguous()
                    array=host.numpy()
                    if not bool(ctx.np.any(array!=0)):continue
                    digest.update(json.dumps([name,key,str(host.dtype),list(host.shape)]).encode())
                    digest.update(array.tobytes())
                elif value!=0:
                    digest.update(json.dumps([name,key,value],sort_keys=True,allow_nan=False).encode())
    exposure=getattr(agent,'_learning_optimizer_exposure',None)
    require(exposure is not None,'Actual optimizer exposure is absent')
    return dict(adam_steps=steps,online_sha256=model_digest(ctx),adam_nonzero_state_sha256=digest.hexdigest(),
                scale=float(agent.grad_scaler.get_scale()),exposure=exposure.snapshot())


def runtime_details(ctx):
    check=getattr(sys,'_is_gil_enabled',None)
    server=sys.modules.get('dqn.socket_server')
    return dict(python=sys.version,torch=str(ctx.torch.__version__),cuda=ctx.torch.version.cuda,
        effective_gil_enabled=check() if check is not None else None,
        expert_guidance_available=(getattr(server,'get_expert_action',None) is not None) if server is not None else None,
        expert_guidance_exercised=False)


def record_optimizer_attempt(ctx,row):
    """Persist BEFORE classification, including rejected/nonfinite evidence."""
    def safe(value):
        if isinstance(value,float) and not math.isfinite(value):return str(value)
        if isinstance(value,dict):return {name:safe(item) for name,item in value.items()}
        if isinstance(value,(list,tuple)):return [safe(item) for item in value]
        return value
    with (ctx.paths['root']/'optimizer-attempts.jsonl').open('a') as stream:
        stream.write(json.dumps(safe(row),sort_keys=True,allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def attempt_checks(ctx):
    """Inspect each persistent component and every gradient without early exit."""
    agent=ctx.agent
    checks={}
    for name,value in (('online',agent.online_net.state_dict()),('target',agent.target_net.state_dict()),
                       ('inference',agent.infer_net.state_dict()),('optimizer',agent.optimizer.state_dict()),
                       ('scaler',agent.grad_scaler.state_dict())):
        try:
            finite_tensors(ctx,value)
            checks[name]=True
        except RuntimeError:
            checks[name]=False
    bad=[]
    present=0
    for name,parameter in agent.online_net.named_parameters():
        if parameter.grad is None:continue
        present+=1
        if not bool(ctx.torch.isfinite(parameter.grad).all().item()):bad.append(name)
    grad_norm=float(getattr(ctx.metrics,'last_grad_norm',math.nan))
    return dict(persistent=checks,persistent_finite=all(checks.values()),
                gradients_finite=not bad and present>0 and math.isfinite(grad_norm),
                gradient_values_finite=not bad,gradient_norm_finite=math.isfinite(grad_norm),
                gradient_tensors=present,nonfinite_gradient_count=len(bad),nonfinite_gradient_names=bad[:16],
                reported_grad_norm=grad_norm)


def update_once(ctx):
    agent,metrics=ctx.agent,ctx.metrics
    ordinal=getattr(ctx,'attempt_ordinal',0)+1
    ctx.attempt_ordinal=ordinal
    row=dict(schema='robotron-private-optimizer-attempt-v1',phase=ctx.phase,attempt=ordinal,
             runtime=runtime_details(ctx),loss=None)
    batch=None
    loss=None
    with agent._training_lock:
        try:
            # Seal warmup anchor before earning a bounded private frame budget.
            ctx.module.replay_pressure_reached(agent)
            with metrics.lock:
                metrics.frame_count+=32
                metrics.learner_frame_count+=32
            ctx.torch.cuda.synchronize(agent.device)
            row['before']=optimizer_observation(ctx)
            row['before_checks']=attempt_checks(ctx)
            record_optimizer_attempt(ctx,dict(row,event='before'))
            require(row['before_checks']['persistent_finite'],'Nonfinite persistent state before attempt')
            agent.training_enabled=metrics.training_enabled=True
            deadline=time.monotonic()+3
            while batch is None:
                if time.monotonic()>=deadline:
                    raise TimeoutError('Real prefetch did not supply a bounded update')
                batch=agent._prefetcher.get(timeout=.1)
            # train_step owns/relinquishes this lease, including on exceptions.
            owned,batch=batch,None
            try:
                loss=ctx.module.train_step(agent,prefetched_batch=owned)
            except BaseException as error:
                row['train_step_error']=repr(error)
                raise
            finally:
                agent.training_enabled=metrics.training_enabled=False
                ctx.torch.cuda.synchronize(agent.device)
                row['after']=optimizer_observation(ctx)
                row['after_checks']=attempt_checks(ctx)
                row['loss']=None if loss is None else float(loss)
                row['training_steps']=int(agent.training_steps)
                row['optimized_samples']=int(agent.optimized_samples)
                record_optimizer_attempt(ctx,dict(row,event='observed'))
            outcome=classify_optimizer_attempt(row['before'],row['after'],loss=loss,
                gradients_finite=row['after_checks']['gradients_finite'],
                persistent_finite=row['before_checks']['persistent_finite'] and row['after_checks']['persistent_finite'])
            row['classification']=outcome
            record_optimizer_attempt(ctx,dict(row,event='classified'))
        except BaseException as error:
            row['error']=repr(error)
            record_optimizer_attempt(ctx,dict(row,event='rejected'))
            raise
        finally:
            agent.training_enabled=metrics.training_enabled=False
            if batch is not None:batch.release()
    before,after=row['before'],row['after']
    return dict(loss=float(loss),adam_step_before=max(before['adam_steps'].values()),
        adam_step_after=max(after['adam_steps'].values()),applied=outcome=='applied',outcome=outcome,
        weights_changed=before['online_sha256']!=after['online_sha256'],
        training_steps=row['training_steps'],optimized_samples=row['optimized_samples'],scale=after['scale'],
        attempt=ordinal,diagnostics='optimizer-attempts.jsonl',runtime=row['runtime'])


def state_fixture(ctx,index):
    state=ctx.np.zeros(ctx.cfg.state_size,dtype=ctx.np.float32)
    for frame in range(4):
        offset=frame*ctx.cfg.single_frame_state_size
        state[offset:offset+2]=(.3+index%5*.01,.5)
        if index%2:
            token=offset+ctx.config.ENEMY_TOKEN_OFFSET
            state[token:token+4]=(1.,.2,-.1,.25)
            state[token+ctx.config.TYPE_ONEHOT_OFFSET]=1.
            state[offset+ctx.config.MODEL_LANE_OFFSET]=.25
            state[offset+ctx.config.MODEL_GRID_OFFSET]=.5
    return state


def start_private_server(ctx):
    module=importlib.import_module('dqn.socket_server')
    assert_private_modules(ctx.layout)
    server=module.SocketServer('127.0.0.1',0,ctx.agent)
    ctx.server,ctx.consumer=server,server.async_buffer
    def run():
        try:server.start()
        except BaseException as error:ctx.server_errors.append(repr(error))
    thread=threading.Thread(target=run,name='private-snapshot-accept',daemon=True)
    ctx.server_thread=thread
    thread.start()
    deadline=time.monotonic()+5
    while True:
        with server.snapshot_gate._condition:
            registered=any(item['name']=='accept-loop' for item in server.snapshot_gate._workers.values())
        if server.running and server.server_socket is not None and registered:break
        require(not ctx.server_errors,'Private server failed: '+repr(ctx.server_errors))
        if time.monotonic()>=deadline:raise TimeoutError('Private accept loop did not start')
        time.sleep(.01)
    address=server.server_socket.getsockname()
    require(address[0]=='127.0.0.1' and address[1] not in (9999,9998,9876,9877),'Unexpected private server binding')
    require(ctx.consumer is not None and ctx.consumer._thread.is_alive(),'Real async replay consumer is missing')
    ctx.metrics.global_server=server
    return address


def verify_archive(parent,archive):
    parent.regular(archive/'COMPLETE.json')
    complete=json.loads((archive/'COMPLETE.json').read_text())
    require(complete['before']==complete['after'],'Snapshot guard changed')
    for relative,item in complete['files'].items():
        path=archive/relative
        require(path.resolve().is_relative_to(archive),'Archive path escaped')
        parent.regular(path)
        require(path.stat().st_size==item['bytes'] and parent.digest(path)==item['sha256'],'Archive file hash differs: '+relative)
    return complete


def capture(ctx):
    address=start_private_server(ctx)
    for index in range(160):
        state=state_fixture(ctx,index)
        following=state_fixture(ctx,index+1)
        ctx.consumer.step_async(state,index%81,(index%7-3)/100,following,index%19==0,
            actor=('dqn','epsilon','expert')[index%3],horizon=1+index%3,client_id=7001)
    require(ctx.consumer.barrier_async(timeout=5).wait(10),'Private replay FIFO failed')
    require(not ctx.consumer.snapshot_command_failures and not ctx.consumer.dropped_steps,'Async replay lost/failed commands')
    memory=ctx.agent.memory
    require(len(memory)==128 and memory.tree.data_ptr==32 and memory._adds_total==160,'Wrapped synthetic ring differs')
    slots=ctx.np.arange(64,dtype=ctx.np.int64)
    require(memory.hof_admit(slots,100000,game_uid=7,level=3),'HOF admission failed')
    require(memory.ephof_admit(ctx.np.roll(slots,8),50000,game_uid=8,level=2),'EpHOF admission failed')
    ctx.agent.training_steps=7
    ctx.agent.optimized_samples=ctx.cfg.target_update_period*ctx.cfg.baseline_batch_size-8
    ctx.agent.last_target_update_samples=0
    ctx.agent.lr_gear='hold'
    ctx.agent.lr_anchor_step=0.
    ctx.agent.lr_manual_scale=.5
    ctx.agent.loaded_training_steps=7
    ctx.agent.loaded_optimized_samples=ctx.agent.optimized_samples
    with ctx.metrics.lock:
        ctx.metrics.frame_count=ctx.metrics.learner_frame_count=160
        ctx.metrics.measurement_frame_count=0
        ctx.metrics.total_training_steps=7
        ctx.metrics.total_optimized_samples=ctx.metrics.loaded_optimized_samples=ctx.agent.optimized_samples
        ctx.metrics.loaded_frame_count=ctx.metrics.loaded_measurement_frame_count=0
        ctx.metrics.epsilon=ctx.metrics.expert_ratio=.1
    updates=[]
    for _ in range(3):
        updates.append(update_once(ctx))
        if updates[-1]['applied']:break
    require(updates[-1]['applied'] and updates[-1]['weights_changed'],'No real fused Adam update applied within bounds')
    require(ctx.agent.optimizer.state and any(bool(value['exp_avg'].abs().sum().item()>0)
            for value in ctx.agent.optimizer.state.values() if 'exp_avg' in value),'Adam moments are empty/zero')
    module=importlib.import_module('dqn.coherent_snapshot')
    info=ctx.ring.stat()
    request=dict(tag='private-whole-agent',request_id=uuid.uuid4().hex,expected_pid=os.getpid(),
        expected_start_ticks=module.process_identity()['start_ticks'],expected_ring_dir=str(ctx.ring),
        expected_ring_device=info.st_dev,expected_ring_inode=info.st_ino,timeout_s=90)
    result=module.capture_snapshot(ctx.agent,ctx.metrics,ctx.server,ctx.cfg,ctx.paths['models'],request,
        control=ctx.config.learning_control,game_settings=ctx.config.game_settings)
    require(result['valid'],'Actual snapshot capture was not certified')
    archive=Path(result['directory'])
    complete=verify_archive(ctx.parent,archive)
    require(complete['device_barrier']['mode']=='owned_cuda_device_synchronized','Real owned-device barrier absent')
    require('accept-loop' in complete['boundary']['parked_workers'],'Actual accept loop did not park')
    require(not ctx.agent.training_enabled and not ctx.metrics.training_enabled and not ctx.agent._prefetch_paused,
            'Snapshot did not restore prior paused flags/prefetch state')
    require(not ctx.metrics.coherent_snapshot_active and not ctx.server.snapshot_gate._closed,'Snapshot gate/status did not reopen')
    require(not ctx.server.clients and not ctx.server_errors,'Unexpected client/server activity')
    return dict(status='PASS',phase='capture',archive=str(archive),address=list(address),updates=updates,
        clocks=complete['after']['clocks'],device_barrier=complete['device_barrier'],
        source_patch_sha256=ctx.parent.PATCH_SHA256,runtime=runtime_details(ctx),
        optimizer_attempt_diagnostics='optimizer-attempts.jsonl')


def check_replay_restore(ctx,archive,complete):
    np=ctx.np
    memory=ctx.agent.memory
    require(Path(memory._mmap_dir)==ctx.ring,'Restored ring mapping is not private')
    meta=np.load(archive/'ring/_meta.npy',allow_pickle=False)
    require(memory.tree.data_ptr==int(meta[0]) and len(memory)==int(meta[1]) and memory.tree.max_priority==float(meta[2]),
            'Restored replay metadata differs')
    for name,(attribute,_,_) in memory._storage_specs().items():
        value=getattr(memory,attribute)
        require(isinstance(value,np.memmap) and Path(value.filename)==ctx.ring/(name+'.npy'),'Restored array escaped private ring')
        np.testing.assert_array_equal(value,np.load(archive/'ring'/(name+'.npy'),mmap_mode='r',allow_pickle=False))
    np.testing.assert_array_equal(memory.tree.tree[memory.capacity:memory.capacity+memory.size],
                                 np.load(archive/'ring/priorities.npy',allow_pickle=False)[:memory.size])
    for bank in ('hof','ephof'):
        require(Path(getattr(memory,'_'+bank+'_dir'))==ctx.banks[bank],'Restored bank path escaped')
        generation=complete['banks'][bank]['generation']
        source=archive/'banks'/bank/'generations'/generation
        with np.load(source/(bank+'_meta.npz'),allow_pickle=False) as metadata:
            lengths=metadata['ep_len']
            require(getattr(memory,bank+'_ep_count')==len(lengths) and getattr(memory,bank+'_total')==int(lengths.sum()),
                    'Restored bank counts differ')
            for name in ('ep_score','ep_len','ep_game','ep_level'):
                np.testing.assert_array_equal(getattr(memory,bank+'_'+name)[:len(lengths)],metadata[name])
            for name in memory._BANK_FIELDS:
                saved=np.load(source/(bank+'_'+name+'.npy'),mmap_mode='r',allow_pickle=False)
                for episode,length in enumerate(lengths):
                    start=episode*getattr(memory,'_'+bank+'_stride')
                    np.testing.assert_array_equal(getattr(memory,bank+'_'+name)[start:start+int(length)],saved[start:start+int(length)])
            require(memory._adds_total-getattr(memory,'_'+bank+'_last_admit_add')==int(metadata['stale_age']) and
                    memory._adds_total-getattr(memory,'_'+bank+'_last_normal_admit_add')==int(metadata['stale_age_normal']),
                    'Restored bank ages differ')


def restore(ctx):
    capture=json.loads((ctx.layout.phase('capture')['root']/'phase-result.json').read_text())
    archive=Path(capture['archive'])
    require(archive.is_absolute() and archive==archive.resolve() and
            archive.is_relative_to(ctx.layout.phase('capture')['models']/'coherent-snapshots'),
            'Restored archive escaped its owned capture root')
    complete=verify_archive(ctx.parent,archive)
    checkpoint=ctx.torch.load(ctx.paths['models']/'robotron_dqn_latest.pt',map_location='cpu',weights_only=True)
    ctx.agent.training_steps=991
    ctx.agent.optimized_samples=9911
    ctx.agent.last_target_update_samples=-5
    ctx.agent.lr_gear='climb'
    ctx.agent.lr_anchor_step=123.
    ctx.agent.lr_manual_scale=.73
    ctx.agent.optimizer.param_groups[0]['lr']=.012
    for key in ('frame_count','learner_frame_count','measurement_frame_count','total_training_steps','total_optimized_samples'):
        setattr(ctx.metrics,key,-123)
    ctx.metrics.epsilon,ctx.metrics.expert_ratio=.9,.7
    ctx.config.game_settings.difficulty=9
    ctx.config.learning_control.lr_scale=1.
    require(ctx.agent.load(str(ctx.paths['models']/'robotron_dqn_latest.pt'),show_status=False),'Actual checkpoint load failed')
    require(not hasattr(ctx.agent,'ratchet_warmup_start_step'),'Cold optimizer fallback was armed')
    for key in ('training_steps','optimized_samples','last_target_update_samples','lr_gear','lr_anchor_step'):
        require(getattr(ctx.agent,key)==checkpoint[key],'Agent checkpoint clock/control failed to restore: '+key)
    for key in ('frame_count','learner_frame_count','measurement_frame_count','total_training_steps','epsilon','expert_ratio'):
        require(getattr(ctx.metrics,key)==checkpoint[key],'Metrics checkpoint value failed to restore: '+key)
    require(ctx.metrics.total_optimized_samples==checkpoint['optimized_samples'] and
            ctx.metrics.loaded_optimized_samples==checkpoint['optimized_samples'],'Optimized sample clocks did not restore')
    nested_equal(ctx,ctx.agent.online_net.state_dict(),checkpoint['online_state_dict'])
    nested_equal(ctx,ctx.agent.target_net.state_dict(),checkpoint['target_state_dict'])
    nested_equal(ctx,ctx.agent.infer_net.state_dict(),ctx.agent.online_net.state_dict())
    nested_equal(ctx,ctx.agent.optimizer.state_dict(),checkpoint['optimizer_state_dict'])
    nested_equal(ctx,ctx.agent.grad_scaler.state_dict(),checkpoint['grad_scaler_state_dict'])
    require(all(group.get('fused') is True for group in ctx.agent.optimizer.param_groups),'Restored optimizer lost fused mode')
    check_replay_restore(ctx,archive,complete)
    runtime=json.loads((archive/'runtime.json').read_text())
    expected_cfg=dict(runtime['config'],replay_tmpfs_dir=str(ctx.paths['tmpfs']))
    require(json.dumps(vars(ctx.cfg),sort_keys=True,default=str)==json.dumps(expected_cfg,sort_keys=True,default=str),
            'Restored configuration differs beyond intentional private path relocation')
    ctx.agent.lr_manual_scale=float(runtime['lr_manual_scale'])
    ctx.config.game_settings.load()
    ctx.config.learning_control._raw=None
    ctx.config.learning_control.refresh()
    require(ctx.config.game_settings.snapshot()==runtime['game_settings'],'Private runtime game settings were not applied')
    require(ctx.config.learning_control.label==runtime['control']['label'] and
            ctx.config.learning_control.lr_scale==runtime['control']['lr_scale'],'Private control was not applied')
    require([float(group['lr']) for group in ctx.agent.optimizer.param_groups]==runtime['optimizer_group_lrs'],
            'Saved optimizer learning rates differ')
    support=ctx.agent.online_net.support.detach().cpu()
    require(ctx.torch.equal(support,ctx.torch.linspace(ctx.cfg.v_min,ctx.cfg.v_max,ctx.cfg.num_atoms)),
            'Rebuilt C51 support differs from matching runtime configuration')
    before=optimizer_steps(ctx)
    update=update_once(ctx)
    require(update['applied'] and update['weights_changed'] and update['adam_step_after']>before,
            'Restored actual fused Adam update did not apply')
    verify_archive(ctx.parent,archive)
    return dict(status='PASS',phase='restore',update=update,restored_clocks=complete['after']['clocks'],
        restored_private_ring=str(ctx.ring),process_local_replay_adds=int(ctx.agent.memory._adds_total),
        archive_hashes_preserved=True,rng_restored=False,runtime=runtime_details(ctx),
        optimizer_attempt_diagnostics='optimizer-attempts.jsonl')


def cleanup(ctx):
    agent=ctx.agent
    agent.training_enabled=ctx.metrics.training_enabled=False
    if ctx.server is not None:
        require(not ctx.server.clients,'Unexpected private clients require failure cleanup')
        ctx.server.stop()
    if ctx.server_thread is not None:
        ctx.server_thread.join(timeout=10)
        require(not ctx.server_thread.is_alive(),'Owned accept thread survived shutdown')
    if ctx.consumer is not None:
        require(not ctx.consumer._thread.is_alive(),'Owned async replay consumer survived shutdown')
    agent.stop()
    agent.memory._wait_bank_writer(timeout=10)
    require(not agent._train_thread.is_alive(),'Owned learner thread survived shutdown')
    if agent._prefetcher is not None:
        require(not agent._prefetcher._thread.is_alive(),'Owned prefetch producer survived shutdown')
    ctx.torch.cuda.synchronize(agent.device)
    assert_private_modules(ctx.layout)
    ctx.parent.verify_source_copies(ctx.layout,ctx.manifest['sources'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--phase',choices=('capture','restore'),required=True)
    args=parser.parse_args(argv)
    parent,manifest,layout=bootstrap(args.manifest,args.phase)
    ctx=None
    result=None
    try:
        ctx=setup(parent,manifest,layout,args.phase)
        result=capture(ctx) if args.phase=='capture' else restore(ctx)
    finally:
        if ctx is not None:cleanup(ctx)
    parent.json_exclusive(layout.phase(args.phase)['root']/'phase-result.json',result)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except BaseException:
        traceback.print_exc()
        raise
