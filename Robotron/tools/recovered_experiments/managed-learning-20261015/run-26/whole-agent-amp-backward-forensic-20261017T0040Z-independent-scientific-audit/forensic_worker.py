#!/usr/bin/env python3
"""Internal token-gated OLD-source worker; no numerical imports at module scope."""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import random
import resource
import sys
import traceback

HERE=Path(__file__).resolve().parent


class BoundaryReached(BaseException):
    pass


class ForbiddenStep(RuntimeError):
    pass


def require(condition,message):
    if not condition:raise RuntimeError(message)


def safe_json(value):
    if isinstance(value,float) and not math.isfinite(value):return str(value)
    if isinstance(value,dict):return {str(key):safe_json(item) for key,item in value.items()}
    if isinstance(value,(tuple,list)):return [safe_json(item) for item in value]
    return value


def write_json(path,value):
    with Path(path).open('x') as stream:
        json.dump(safe_json(value),stream,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())


def bootstrap(path,*,token_reader=None):
    path=Path(path)
    require(path.is_absolute() and path==path.resolve() and not path.is_symlink(),'Manifest path is not regular/absolute')
    manifest=json.loads(path.read_text())
    parent_path=HERE/'forensic_parent.py'
    require(hashlib.sha256(parent_path.read_bytes()).hexdigest()==manifest['parent_sha256'],'Parent adapter changed')
    spec=importlib.util.spec_from_file_location('_forensic_parent_adapter',parent_path)
    parent=importlib.util.module_from_spec(spec);sys.modules[spec.name]=parent;spec.loader.exec_module(parent)
    require(parent.digest(__file__)==manifest['worker_sha256'],'Worker adapter changed')
    lock=parent.read_lock();base,old=parent.helpers(lock)
    require(manifest['schema']==parent.SCHEMA and manifest['explicit_launch'] is True and
            manifest['source_lock_sha256']==parent.LOCK_SHA and manifest['sources']==lock['source_files'] and
            manifest['seed']==parent.SEED and manifest['cases']==[list(case) for case in parent.CASES] and
            manifest['forensic_old_sources'] is True and manifest['current_merged_snapshot_qualification'] is False,
            'Manifest differs from fixed forensic scope')
    require(manifest['bounds']==base.BOUNDS and manifest['gpu_uuid']==base.GPU0_UUID and
            manifest['forbidden_gpu_uuid']==base.MAIN_GPU_UUID,'Resource/GPU manifest changed')
    require(os.getppid()==manifest['parent']['pid'] and base.identity(os.getppid())==manifest['parent'],'Parent identity differs')
    old.arm_parent_death_signal(manifest['parent']['pid']);old.reset_inherited_signal_mask()
    layout=base.Layout(Path(manifest['output']),manifest['nonce'],Path(manifest['tmpfs']).parent)
    require(str(layout.tmpfs)==manifest['tmpfs'] and path==layout.output/'launch-manifest.json','Owned root identity differs')
    base.check_directory(layout.output,manifest['output_identity']);base.check_directory(layout.tmpfs,manifest['tmpfs_identity'])
    token=(token_reader or (lambda:sys.stdin.buffer.readline(128)))()
    require(token==(manifest['launch_token']+'\n').encode(),'Missing parent token')
    cg=Path(manifest['cgroup']);base.check_directory(cg,manifest['cgroup_identity'])
    rows=[line.split(':',2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::')]
    require(len(rows)==1 and Path('/sys/fs/cgroup')/rows[0].lstrip('/')==cg and
            os.getpid() in [int(value) for value in (cg/'cgroup.procs').read_text().split()],'Owned cgroup membership differs')
    for name,expected in {'memory.max':str(base.BOUNDS['memory_bytes']),'memory.swap.max':'0',
            'memory.oom.group':'1','pids.max':str(base.BOUNDS['tasks']),'cpu.max':'200000 100000'}.items():
        require((cg/name).read_text().strip()==expected,'Cgroup limit changed: '+name)
    expected=base.configure_environment(layout,'capture')
    require(all(os.environ.get(name)==value for name,value in expected.items()),'Private environment differs')
    require('LD_PRELOAD' not in os.environ and 'PYTHONPATH' not in os.environ,'Import/preload hooks forbidden')
    require(all(name in expected for name in os.environ if name.startswith(('DQN_','ROBOTRON_'))),'Unexpected training environment')
    require(Path.cwd()==layout.output/'private','Worker cwd differs')
    base.verify_source_copies(layout,manifest['sources'])
    base.guard_live_resources(allowed_pids={os.getpid(),os.getppid()},expected_main=manifest['main_owners'],initial=True)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_FSIZE,(1<<30,1<<30))
    resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
    return parent,base,old,lock,manifest,layout


def tensor_bytes(tensor):
    return tensor.detach().cpu().contiguous().reshape(-1).view(dtype=__import__('torch').uint8).numpy().tobytes()


def structure_digest(ctx,value):
    digest=hashlib.sha256()
    def walk(item):
        if isinstance(item,ctx.torch.Tensor):
            digest.update(json.dumps([str(item.dtype),list(item.shape)]).encode());digest.update(tensor_bytes(item))
        elif isinstance(item,ctx.np.ndarray):
            digest.update(json.dumps([str(item.dtype),list(item.shape)]).encode());digest.update(item.tobytes())
        elif isinstance(item,dict):
            for key in sorted(item,key=lambda key:(type(key).__name__,str(key))):
                digest.update(repr(key).encode());walk(item[key])
        elif isinstance(item,(tuple,list)):
            digest.update(type(item).__name__.encode())
            for value in item:walk(value)
        else:digest.update(repr(item).encode())
    walk(value)
    return digest.hexdigest()


def cpu_copy(ctx,value):
    if isinstance(value,ctx.torch.Tensor):return value.detach().cpu().clone()
    if isinstance(value,dict):return {key:cpu_copy(ctx,item) for key,item in value.items()}
    if isinstance(value,list):return [cpu_copy(ctx,item) for item in value]
    if isinstance(value,tuple):return tuple(cpu_copy(ctx,item) for item in value)
    return copy.deepcopy(value)


def save_tensors(ctx,path,value):
    host=cpu_copy(ctx,value)
    with Path(path).open('xb') as stream:
        ctx.torch.save(host,stream);stream.flush();os.fsync(stream.fileno())
    tensors={}
    def walk(item,name):
        if isinstance(item,ctx.torch.Tensor):
            tensors[name]=dict(dtype=str(item.dtype),shape=list(item.shape),numel=item.numel(),
                               sha256=hashlib.sha256(tensor_bytes(item)).hexdigest())
        elif isinstance(item,dict):
            for key,value in item.items():walk(value,name+'/'+str(key))
        elif isinstance(item,(tuple,list)):
            for index,value in enumerate(item):walk(value,name+'/'+str(index))
    walk(host,'')
    return dict(path=Path(path).name,bytes=Path(path).stat().st_size,sha256=ctx.parent.digest(path),
                content_sha256=structure_digest(ctx,host),tensors=tensors)


AGENT_SCALARS=('training_steps','optimized_samples','last_target_update_samples','lr_gear','lr_anchor_step',
               'lr_manual_scale','loaded_training_steps','loaded_optimized_samples','_replay_pressure_anchor','_replay_warmup_pending')
METRIC_SCALARS=('frame_count','learner_frame_count','measurement_frame_count','total_training_steps','total_optimized_samples',
                'loaded_optimized_samples','loaded_frame_count','loaded_measurement_frame_count','epsilon','expert_ratio')


def scalars(ctx):
    return dict(agent={name:copy.deepcopy(getattr(ctx.agent,name)) for name in AGENT_SCALARS if hasattr(ctx.agent,name)},
                metrics={name:copy.deepcopy(getattr(ctx.metrics,name)) for name in METRIC_SCALARS})


def replay_digest(ctx):
    memory=ctx.agent.memory
    arrays={name:getattr(memory,attribute) for name,(attribute,_,_) in memory._storage_specs().items()}
    return structure_digest(ctx,dict(fields=arrays,priorities=memory.tree.tree,ptr=memory.tree.data_ptr,
                                    size=len(memory),max_priority=memory.tree.max_priority,adds=memory._adds_total))


def state_certificate(ctx):
    agent=ctx.agent
    return dict(networks={name:structure_digest(ctx,getattr(agent,name).state_dict())
                         for name in ('online_net','target_net','infer_net')},
                optimizer=structure_digest(ctx,agent.optimizer.state_dict()),scalars=scalars(ctx),
                exposure=agent._learning_optimizer_exposure.snapshot(),replay_sha256=replay_digest(ctx))


def save_rng(ctx,path):
    state=ctx.np.random.get_state()
    data=dict(python=random.getstate(),numpy_name=state[0],numpy_position=int(state[2]),
              numpy_has_gauss=int(state[3]),numpy_cached_gauss=float(state[4]))
    tensors=dict(cpu=ctx.torch.get_rng_state().clone(),cuda=ctx.torch.cuda.get_rng_state(ctx.agent.device).cpu().clone())
    with (path/'numpy-rng.npy').open('xb') as stream:
        ctx.np.save(stream,state[1],allow_pickle=False);stream.flush();os.fsync(stream.fileno())
    write_json(path/'rng.json',data)
    save_tensors(ctx,path/'torch-rng.pt',tensors)
    return dict(metadata=data,numpy_keys=state[1].copy(),torch=tensors)


def restore_rng(ctx,rng):
    def tuples(value):return tuple(tuples(item) for item in value) if isinstance(value,list) else value
    data=rng['metadata']
    random.setstate(tuples(data['python']))
    ctx.np.random.set_state((data['numpy_name'],rng['numpy_keys'].copy(),data['numpy_position'],
                            data['numpy_has_gauss'],data['numpy_cached_gauss']))
    ctx.torch.set_rng_state(rng['torch']['cpu']);ctx.torch.cuda.set_rng_state(rng['torch']['cuda'],ctx.agent.device)


def current_rng_digest(ctx):
    state=ctx.np.random.get_state()
    return structure_digest(ctx,dict(python=random.getstate(),numpy=state,
        cpu=ctx.torch.get_rng_state(),cuda=ctx.torch.cuda.get_rng_state(ctx.agent.device)))


def runtime_flags(ctx):
    torch=ctx.torch
    return dict(python=sys.version,torch=str(torch.__version__),cuda=torch.version.cuda,
        effective_gil_enabled=getattr(sys,'_is_gil_enabled',lambda:None)(),
        float32_matmul_precision=torch.get_float32_matmul_precision(),
        deterministic_algorithms=torch.are_deterministic_algorithms_enabled(),
        matmul={name:getattr(torch.backends.cuda.matmul,name,None) for name in
                ('allow_tf32','allow_fp16_reduced_precision_reduction','allow_bf16_reduced_precision_reduction')},
        cudnn={name:getattr(torch.backends.cudnn,name,None) for name in ('enabled','allow_tf32','benchmark','deterministic')},
        modules={name:dict(training=net.training,dropouts=[float(module.p) for module in net.modules()
                         if isinstance(module,torch.nn.Dropout)]) for name,net in
                 (('online',ctx.agent.online_net),('target',ctx.agent.target_net),('inference',ctx.agent.infer_net))},
        optional_expert_module_loaded='dqn.expert_fast' in sys.modules,expert_guidance_exercised=False,
        current_expert_availability='not_tested_no_expert_import',current_expert_import_error=None,
        expert_status_scope='Module-loaded is an import observation, not proof of optional v3 availability. No expert import/guidance is attempted.',
        prior_reviewed2_expert=dict(available=False,import_error="No module named 'v3'",scope='Historical failed reviewed2 observation only'),
        precision_limit='FP32 case disables autocast; recorded TF32/backend policy is retained')


def tensor_stats(ctx,value):
    host=value.detach().cpu()
    finite=ctx.torch.isfinite(host)
    good=host[finite].double()
    norm=ctx.torch.linalg.vector_norm(host.double().reshape(-1))
    return dict(dtype=str(host.dtype),shape=list(host.shape),numel=host.numel(),
        sha256=hashlib.sha256(tensor_bytes(host)).hexdigest(),all_finite=bool(finite.all()),
        nan=int(ctx.torch.isnan(host).sum()),positive_inf=int(ctx.torch.isposinf(host).sum()),
        negative_inf=int(ctx.torch.isneginf(host).sum()),finite_max_abs=float(good.abs().max()) if good.numel() else None,
        finite_l2=float(ctx.torch.linalg.vector_norm(good)) if good.numel() else 0.,full_l2=float(norm))


def gradients(ctx,path,stage):
    native={name:None if parameter.grad is None else parameter.grad.detach().cpu().clone()
            for name,parameter in ctx.agent.online_net.named_parameters()}
    stats={name:None if tensor is None else tensor_stats(ctx,tensor) for name,tensor in native.items()}
    artifact=save_tensors(ctx,path/(stage+'-gradients.pt'),native)
    write_json(path/(stage+'-gradients.json'),dict(stage=stage,parameters=stats,artifact=artifact))
    return dict(parameters=stats,artifact=artifact)


class CaseHooks:
    """Reversible child-only hooks; the original loss/backward stays untouched."""
    def __init__(self,ctx,directory,amp):
        self.ctx,self.directory,self.amp=ctx,directory,amp
        self.calls=dict(optimizer_step=0,scaler_step=0,scaler_update=0,unscale=0,boundary=0)
        self.handles=[];self.restore=[];self.forward=[];self.boundary=None
        self.parameter_ids=tuple(id(parameter) for parameter in ctx.agent.online_net.parameters())
        self.sentinel=BoundaryReached('recorded preclip boundary')

    def replace(self,target,name,value):
        existed=name in vars(target);original=vars(target).get(name)
        self.restore.append((target,name,existed,original));setattr(target,name,value)

    def check_caller(self,frame):
        expected=self.ctx.training._train_step_impl
        require(frame.f_code is expected.__code__ and Path(frame.f_code.co_filename).resolve()==
                self.ctx.layout.scripts/'dqn/training.py','Unexpected backward-boundary caller')

    def forbid(self,name):
        def forbidden(*args,**kwargs):
            self.calls[name]+=1
            raise ForbiddenStep(name+' is forbidden in backward-only forensics')
        return forbidden

    def unscale(self,optimizer):
        frame=inspect.currentframe().f_back
        try:self.check_caller(frame)
        finally:del frame
        require(optimizer is self.ctx.agent.optimizer and self.calls['unscale']==0,'Unscale ownership/count differs')
        self.calls['unscale']+=1
        gradients(self.ctx,self.directory,'scaled')
        self.original_unscale(optimizer)
        gradients(self.ctx,self.directory,'unscaled')

    def clip(self,parameters,*args,**kwargs):
        frame=inspect.currentframe().f_back
        data=actual=None
        try:
            self.check_caller(frame)
            require(tuple(id(parameter) for parameter in parameters)==self.parameter_ids,'Clipping parameter ownership differs')
            require(self.calls['boundary']==0 and self.calls['unscale']==int(self.amp),'Unexpected backward boundary order')
            self.calls['boundary']+=1
            if not self.amp:gradients(self.ctx,self.directory,'unscaled')
            data=frame.f_locals
            names=('weighted_loss','ce_loss','bc_loss','m_joint','joint_log_p','joint_log_p_a',
                   'joint_logits','move_logits','fire_logits','joint_q_next','joint_tp','joint_tp_a','Tz_raw',
                   'states_t','next_states_t','rewards_t','dones_t','horizons_t','is_expert_t','weights_t','outcome_tensor')
            actual={name:data[name] for name in names if name in data and isinstance(data[name],self.ctx.torch.Tensor)}
            require('weighted_loss' in actual and 'm_joint' in actual,'Actual eager training loss locals missing')
            if self.amp:
                require(data.get('outcome_mode')=='single_cuda_found_inf' and 'outcome_tensor' in actual,
                        'Actual AMP found-inf capture is unsupported')
            self.boundary=dict(actual=save_tensors(self.ctx,self.directory/'actual-loss-and-inputs.pt',actual),
                loss=float(data['weighted_loss'].detach().float().cpu()),outcome_mode=data.get('outcome_mode'),
                tensors={name:tensor_stats(self.ctx,value) for name,value in actual.items()},
                scaled_stage='recorded' if self.amp else 'not_applicable')
            write_json(self.directory/'boundary.json',self.boundary)
        finally:
            # Do not retain the caller's autograd tensors through this frame.
            data=actual=None
            del frame
        raise self.sentinel

    def prehook(self,name,module,args,kwargs):
        torch=self.ctx.torch
        record=dict(module=name,stage='pre',inputs=[tensor_stats(self.ctx,value) for value in args if isinstance(value,torch.Tensor)])
        if isinstance(module,torch.nn.LayerNorm) and args and isinstance(args[0],torch.Tensor):
            x=args[0].detach().cpu().double()
            dimensions=tuple(range(x.ndim-len(module.normalized_shape),x.ndim))
            record['layernorm_variance']=tensor_stats(self.ctx,x.var(dim=dimensions,unbiased=False))
            record['eps']=float(module.eps)
        masks={key:value.detach().cpu().clone() for key,value in kwargs.items()
               if key in ('key_padding_mask','attn_mask') and isinstance(value,torch.Tensor)}
        if masks:record['masks']=save_tensors(self.ctx,self.directory/('mask-'+str(len(self.forward))+'.pt'),masks)
        self.forward.append(record)

    def posthook(self,name,module,args,kwargs,output):
        values=output if isinstance(output,(tuple,list)) else (output,)
        self.forward.append(dict(module=name,stage='post',outputs=[tensor_stats(self.ctx,value)
            for value in values if isinstance(value,self.ctx.torch.Tensor)]))

    def __enter__(self):
        try:
            agent,torch=self.ctx.agent,self.ctx.torch
            self.handles.append(agent.optimizer.register_step_pre_hook(self.forbid('optimizer_step')))
            if self.amp:
                self.original_unscale=agent.grad_scaler.unscale_
                self.replace(agent.grad_scaler,'step',self.forbid('scaler_step'))
                self.replace(agent.grad_scaler,'update',self.forbid('scaler_update'))
                self.replace(agent.grad_scaler,'unscale_',self.unscale)
            self.replace(torch.nn.utils,'clip_grad_norm_',self.clip)
            for network,net in (('online',agent.online_net),('target',agent.target_net),('inference',agent.infer_net)):
                for name,module in net.named_modules():
                    if isinstance(module,(torch.nn.Linear,torch.nn.LayerNorm,torch.nn.MultiheadAttention)) or module.__class__.__name__.endswith('Encoder'):
                        label=network+'.'+name
                        self.handles.append(module.register_forward_pre_hook(
                            lambda module,args,kwargs,label=label:self.prehook(label,module,args,kwargs),with_kwargs=True))
                        self.handles.append(module.register_forward_hook(
                            lambda module,args,kwargs,output,label=label:self.posthook(label,module,args,kwargs,output),with_kwargs=True))
            return self
        except BaseException:
            self.__exit__(None,None,None);raise

    def __exit__(self,*unused):
        for handle in reversed(self.handles):handle.remove()
        for target,name,existed,original in reversed(self.restore):
            if existed:setattr(target,name,original)
            else:delattr(target,name)
        self.handles=[];self.restore=[]


def setup_inputs(ctx,old):
    agent,metrics=ctx.agent,ctx.metrics
    require(not agent._train_thread.is_alive(),'Background learner still alive')
    require(agent._prefetcher.close(timeout=10) and not agent._prefetcher._thread.is_alive(),'Prefetch did not join')
    agent.training_enabled=metrics.training_enabled=False
    for index in range(160):
        agent.step(old.state_fixture(ctx,index),index%81,(index%7-3)/100,old.state_fixture(ctx,index+1),
            index%19==0,actor=('dqn','epsilon','expert')[index%3],horizon=1+index%3)
    memory=agent.memory
    require(len(memory)==128 and memory.tree.data_ptr==32 and memory._adds_total==160,'Fixture ring differs')
    slots=ctx.np.arange(64,dtype=ctx.np.int64)
    require(memory.hof_admit(slots,100000,game_uid=7,level=3),'HOF admission failed')
    require(memory.ephof_admit(ctx.np.roll(slots,8),50000,game_uid=8,level=2),'EpHOF admission failed')
    agent.training_steps=7;agent.optimized_samples=ctx.cfg.target_update_period*ctx.cfg.baseline_batch_size-8
    agent.last_target_update_samples=0;agent.lr_gear='hold';agent.lr_anchor_step=0.;agent.lr_manual_scale=.5
    agent.loaded_training_steps=7;agent.loaded_optimized_samples=agent.optimized_samples
    metrics.frame_count=metrics.learner_frame_count=160;metrics.measurement_frame_count=0
    metrics.total_training_steps=7;metrics.total_optimized_samples=metrics.loaded_optimized_samples=agent.optimized_samples
    metrics.loaded_frame_count=metrics.loaded_measurement_frame_count=0;metrics.epsilon=metrics.expert_ratio=.1
    ctx.module.replay_pressure_reached(agent)
    metrics.frame_count+=32;metrics.learner_frame_count+=32
    require(not ctx.module.replay_pressure_reached(agent),'Exact private frame budget does not permit backward')
    beta=ctx.training._beta_schedule(metrics.frame_count)
    batch=memory.sample(ctx.cfg.batch_size,beta=beta)
    require(batch is not None and len(batch)==10,'Actual ten-array sample missing')
    batch=tuple(ctx.np.array(value,copy=True) for value in batch)
    names=('states','actions','rewards','next_states','dones','horizons','is_expert','actor_kind','indices','weights')
    root=ctx.paths['root']/'inputs';root.mkdir()
    array_meta={}
    for name,value in zip(names,batch):
        require(not value.dtype.hasobject,'Object arrays are forbidden')
        path=root/(name+'.npy')
        with path.open('xb') as stream:ctx.np.save(stream,value,allow_pickle=False);stream.flush();os.fsync(stream.fileno())
        array_meta[name]=dict(dtype=str(value.dtype),shape=list(value.shape),sha256=ctx.parent.digest(path),
                              raw_sha256=hashlib.sha256(value.tobytes()).hexdigest())
    write_json(root/'batch.json',dict(beta=beta,arrays=array_meta))
    payload=dict(networks={name:getattr(agent,name).state_dict() for name in ('online_net','target_net','infer_net')},
        optimizer=agent.optimizer.state_dict(),scaler=agent.grad_scaler.state_dict())
    fresh_artifact=save_tensors(ctx,root/'fresh-state.pt',payload)
    write_json(root/'fresh-state-manifest.json',fresh_artifact)
    control=dict(config=vars(ctx.cfg),scalars=scalars(ctx),training_flags={name:getattr(agent,name).training for name in
                 ('online_net','target_net','infer_net')},runtime=runtime_flags(ctx),
                 learning_control=dict(path=str(ctx.config.learning_control.path),label=ctx.config.learning_control.label,
                     lr_scale=ctx.config.learning_control.lr_scale,
                     file=json.loads(ctx.config.learning_control.path.read_text())),
                 game_settings=ctx.config.game_settings.snapshot())
    write_json(root/'configuration.json',control)
    presence={}
    for name,array in (('states',batch[0]),('next_states',batch[3])):
        start=ctx.cfg.global_features
        stop=start+ctx.cfg.object_token_count*ctx.cfg.object_token_features
        tokens=array[:,:ctx.cfg.single_frame_state_size][:,start:stop].reshape(
            array.shape[0],ctx.cfg.object_token_count,ctx.cfg.object_token_features)
        mask=tokens[...,0]>.5
        with (root/(name+'-present.npy')).open('xb') as stream:
            ctx.np.save(stream,mask,allow_pickle=False);stream.flush();os.fsync(stream.fileno())
        presence[name]=dict(present_per_row=mask.sum(axis=1).tolist(),
            padding_per_row=(~mask).sum(axis=1).tolist(),fully_empty_rows=int((~mask.any(axis=1)).sum()))
    write_json(root/'presence.json',presence)
    rng=save_rng(ctx,root)
    baseline=dict(root=root,batch_names=names,array_meta=array_meta,scalars=scalars(ctx),
                  training_flags=control['training_flags'],rng=rng,rng_sha256=current_rng_digest(ctx),
                  state_sha256=ctx.parent.digest(root/'fresh-state.pt'),certificate=state_certificate(ctx))
    write_json(root/'baseline-certificate.json',dict(certificate=baseline['certificate'],rng_sha256=baseline['rng_sha256']))
    baseline['input_files']={path.name:ctx.parent.digest(path) for path in root.iterdir() if path.is_file()}
    return baseline


def restore_case(ctx,baseline,scale):
    agent=ctx.agent
    require(all(ctx.parent.digest(baseline['root']/name)==digest for name,digest in baseline['input_files'].items()),
            'Saved initial inputs/state/RNG changed')
    payload=ctx.torch.load(baseline['root']/'fresh-state.pt',map_location='cpu',weights_only=True)
    for name,state in payload['networks'].items():
        getattr(agent,name).load_state_dict(state);getattr(agent,name).train(baseline['training_flags'][name])
    agent.optimizer.load_state_dict(payload['optimizer'])
    agent.optimizer.zero_grad(set_to_none=True)
    for name,value in baseline['scalars']['agent'].items():setattr(agent,name,copy.deepcopy(value))
    for name,value in baseline['scalars']['metrics'].items():setattr(ctx.metrics,name,copy.deepcopy(value))
    # Aborted unscale leaves UNSCALED transient state; never reuse that scaler.
    agent.use_amp=scale is not None
    agent.grad_scaler=ctx.torch.amp.GradScaler('cuda',enabled=True,init_scale=float(scale)) if scale is not None else None
    if scale is not None:
        require(agent.grad_scaler.is_enabled() and agent.grad_scaler.get_scale()==scale,'Fresh scaler differs')
        require(not agent.grad_scaler._per_optimizer_states,'Fresh scaler registry is not empty')
        expected=dict(payload['scaler'],scale=float(scale))
        require(agent.grad_scaler.state_dict()==expected,'Fresh scaler differs beyond declared initial scale')
    batch=[]
    for name in baseline['batch_names']:
        path=baseline['root']/(name+'.npy')
        require(ctx.parent.digest(path)==baseline['array_meta'][name]['sha256'],'Saved batch changed')
        batch.append(ctx.np.load(path,allow_pickle=False))
    persisted_rng=dict(metadata=json.loads((baseline['root']/'rng.json').read_text()),
        numpy_keys=ctx.np.load(baseline['root']/'numpy-rng.npy',allow_pickle=False),
        torch=ctx.torch.load(baseline['root']/'torch-rng.pt',map_location='cpu',weights_only=True))
    restore_rng(ctx,persisted_rng)
    ctx.torch.cuda.synchronize(agent.device)
    require(current_rng_digest(ctx)==baseline['rng_sha256'],'Pre-forward RNG differs')
    require(state_certificate(ctx)==baseline['certificate'],'Pre-forward model/optimizer/clocks/replay differ')
    return tuple(batch)


def run_case(ctx,baseline,name,scale):
    directory=ctx.paths['root']/name;directory.mkdir()
    row=dict(case=name,status='ERROR',amp=scale is not None,initial_scale=scale,planned_backward_calls=1)
    batch=restore_case(ctx,baseline,scale)
    before=state_certificate(ctx)
    row.update(before=before,pre_forward_rng_sha256=current_rng_digest(ctx),runtime=runtime_flags(ctx))
    row['scaler_before']=ctx.agent.grad_scaler.state_dict() if ctx.agent.grad_scaler is not None else None
    write_json(directory/'before.json',row)
    hooks=CaseHooks(ctx,directory,scale is not None)
    try:
        with hooks:
            ctx.agent.training_enabled=ctx.metrics.training_enabled=True
            try:
                value=ctx.training.train_step(ctx.agent,prefetched_batch=batch)
                raise RuntimeError('Train step returned before recorded backward boundary: '+repr(value))
            except BoundaryReached as error:
                require(error is hooks.sentinel and hooks.calls['boundary']==1,'Unknown boundary sentinel')
                row['status']='OBSERVED';row['boundary']=hooks.boundary
                error.__traceback__=None
            finally:ctx.agent.training_enabled=ctx.metrics.training_enabled=False
    except Exception as error:
        row['error']=repr(error);row['traceback']=traceback.format_exc()
    finally:
        ctx.agent.training_enabled=ctx.metrics.training_enabled=False
        ctx.torch.cuda.synchronize(ctx.agent.device)
        write_json(directory/'forward.json',hooks.forward)
        row['calls']=hooks.calls
        row['backward_completed_before_boundary']=hooks.calls['boundary']==1
        # Scheduled LR assignment is allowed before backward; preserve it as
        # evidence and remove only that documented metadata change for equality.
        row['scheduled_optimizer_group_lrs']=[float(group['lr']) for group in ctx.agent.optimizer.param_groups]
        for current,saved in zip(ctx.agent.optimizer.param_groups,
                                 ctx.torch.load(baseline['root']/'fresh-state.pt',map_location='cpu',weights_only=True)['optimizer']['param_groups']):
            current['lr']=saved['lr']
        row['after']=state_certificate(ctx)
        row['post_backward_rng_sha256']=current_rng_digest(ctx)
        if ctx.agent.grad_scaler is not None:row['scaler_after']=ctx.agent.grad_scaler.state_dict()
        row['no_step_certificate']=all(hooks.calls[key]==0 for key in ('optimizer_step','scaler_step','scaler_update')) and row['after']==before
        write_json(directory/'result.json',row)
    require(row['no_step_certificate'],'No-step certificate failed; remaining cases must not run')
    return row


def observe(ctx,old,parent):
    ctx.training=importlib.import_module('dqn.training')
    require(ctx.training._train_step_impl.__code__.co_filename==str(ctx.layout.scripts/'dqn/training.py'),'Actual training source escaped')
    baseline=setup_inputs(ctx,old)
    results=[]
    with ctx.agent._training_lock:
        for name,scale in parent.CASES:
            try:results.append(run_case(ctx,baseline,name,scale))
            except Exception as error:
                results.append(dict(case=name,status='SAFETY_ERROR',error=repr(error)))
                for pending,_ in parent.CASES[len(results):]:results.append(dict(case=pending,status='NOT_RUN_AFTER_SAFETY_ERROR'))
                break
    return dict(status='OBSERVATIONS_COMPLETE' if all(row['status']=='OBSERVED' for row in results) else 'DIAGNOSTIC_ERROR',
        schema=parent.SCHEMA,seed=parent.SEED,cases=results,forensic_old_sources=True,
        current_merged_snapshot_qualification=False,snapshot_qualified=False,optimizer_steps_allowed=0,
        source_lock_sha256=parent.LOCK_SHA,limitations=['Fresh seeded case; exact reviewed2 weights/batches were not retained',
            'No optimizer step/capture/restore/MAME/playing-performance validation','Old archived source only; no merged production qualification',
            'Saved RNG does not guarantee deterministic CUDA kernels; recorded GIL/TF32/backend policy retained'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',required=True,type=Path)
    args=parser.parse_args(argv)
    parent,base,old,lock,manifest,layout=bootstrap(args.manifest)
    ctx=result=None
    try:
        # Every path/source/token/cgroup/GPU guard has completed before imports.
        import numpy as np
        import torch
        random.seed(parent.SEED);np.random.seed(parent.SEED);torch.manual_seed(parent.SEED);torch.cuda.manual_seed_all(parent.SEED)
        ctx=old.setup(base,manifest,layout,'capture')
        result=observe(ctx,old,parent)
    finally:
        if ctx is not None:old.cleanup(ctx)
    base.json_exclusive(layout.phase('capture')['root']/'phase-result.json',safe_json(result))
    return 0 if result['status']=='OBSERVATIONS_COMPLETE' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except BaseException:
        traceback.print_exc();raise
