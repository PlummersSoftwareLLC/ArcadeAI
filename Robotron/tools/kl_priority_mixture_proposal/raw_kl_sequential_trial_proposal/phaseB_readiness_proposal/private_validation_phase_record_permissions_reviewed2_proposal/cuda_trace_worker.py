#!/usr/bin/env python3
"""Stage B: actual private RainbowAgent with an explicit fixed-input replay adapter.

SOURCE PREPARATION ONLY. The owned parent is the sole execution gate. No full
ring, serving/learner coexistence, policy benefit or live mixture claim is made.
"""
from __future__ import annotations
import argparse
import copy
import gc
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import resource
import sys
import threading
import traceback
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROLES = ('kl18', 'resume', 'return_ce')
ATTEMPTS = 18
BATCH = 4096
CAPACITY = 6000000
FRAME_CREDIT = 512
INPUT_NAMES = ('states','actions','rewards','next_states','dones','horizons','is_expert','weights')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def safe(value):
    if isinstance(value,float) and not math.isfinite(value): return str(value)
    if isinstance(value,dict): return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)): return [safe(v) for v in value]
    if type(value).__module__.startswith('numpy') and hasattr(value,'tolist'):return safe(value.tolist())
    return value


def write_json(path, value):
    path=Path(path)
    with path.open('x') as stream:
        json.dump(safe(value),stream,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    path.chmod(0o444)
    fsync_directory(path.parent)


def fsync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def bootstrap(path, variant):
    require(not any(name == 'torch' or name == 'numpy' or name.startswith('dqn') for name in sys.modules),
            'Numerical/application import before bootstrap')
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink(), 'Manifest path differs')
    manifest = json.loads(path.read_text())
    source = HERE / 'cuda_trace_parent.py'
    data = source.read_bytes()
    require(hashlib.sha256(data).hexdigest() == manifest['parent_sha256'], 'Parent source changed')
    specification = importlib.util.spec_from_file_location('_cuda_trace_parent', source)
    parent = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = parent
    exec(compile(data, str(source), 'exec'), parent.__dict__)
    require(parent.digest(__file__) == manifest['worker_sha256'], 'Worker source changed')
    lock = parent.read_lock()
    base, old = parent.helpers(lock)
    require(manifest['schema'] == parent.SCHEMA and manifest['explicit_launch'] is True and
            manifest['source_lock_sha256'] == parent.digest(HERE / 'source-lock.json') and
            manifest['sources'] == lock['source_files'] and variant in parent.VARIANTS and
            manifest['bounds'] == parent.BOUNDS and manifest['gpu_uuid'] == base.GPU0_UUID and
            manifest['forbidden_gpu_uuid'] == base.MAIN_GPU_UUID, 'Manifest protocol/bounds differ')
    require(os.getppid() == manifest['parent']['pid'] and base.identity(os.getppid()) == manifest['parent'],
            'Parent identity changed')
    old.arm_parent_death_signal(manifest['parent']['pid'])
    old.reset_inherited_signal_mask()
    layout = parent.Layout(Path(manifest['output']), manifest['nonce'], Path(manifest['tmpfs']).parent)
    require(str(layout.tmpfs) == manifest['tmpfs'] and path == layout.output / 'launch-manifest.json', 'Owned layout differs')
    base.check_directory(layout.output, manifest['output_identity'])
    base.check_directory(layout.tmpfs, manifest['tmpfs_identity'])
    require(sys.stdin.buffer.readline(128) == (manifest['launch_token'] + '\n').encode(), 'Parent token missing')
    cgroup = Path(manifest['cgroup'])
    base.check_directory(cgroup, manifest['cgroup_identity'])
    rows = [line.split(':', 2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::')]
    require(len(rows) == 1 and Path('/sys/fs/cgroup') / rows[0].lstrip('/') == cgroup and
            os.getpid() in [int(value) for value in (cgroup / 'cgroup.procs').read_text().split()], 'Cgroup membership differs')
    for name, expected in {'memory.max': str(parent.BOUNDS['memory_bytes']), 'memory.swap.max': '0',
            'memory.oom.group': '1', 'pids.max': str(parent.BOUNDS['tasks']), 'cpu.max': '200000 100000'}.items():
        require((cgroup / name).read_text().strip() == expected, 'Cgroup limit changed: ' + name)
    expected = parent.configure_environment(layout, variant)
    require(all(os.environ.get(name) == value for name, value in expected.items()), 'Private environment differs')
    require('LD_PRELOAD' not in os.environ and 'PYTHONPATH' not in os.environ, 'Preload/import hooks forbidden')
    require(all(name in expected for name in os.environ if name.startswith(('DQN_', 'ROBOTRON_'))), 'Unexpected training environment')
    require(Path.cwd() == layout.output / 'private', 'Private cwd differs')
    base.verify_source_copies(layout, manifest['sources'])
    require(parent.bind_inputs(lock)==manifest['retained_inputs'],'Original live8 input identities changed')
    base.guard_live_resources(allowed_pids={os.getpid(),os.getppid()},expected_main=manifest['main_owners'],initial=True)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(1<<30,1<<30))
    resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
    role = parent.read_role_input(layout, variant, parent.digest(path))
    return SimpleNamespace(parent=parent,base=base,old=old,lock=lock,manifest=manifest,
        layout=layout,variant=variant,paths=layout.phase(variant),role=role)


def setup(ctx):
    # This is reached only after the unchanged owned-launch bootstrap above.
    import numpy as np
    import torch
    ctx.np,ctx.torch=np,torch
    torch.set_num_threads(2);torch.set_num_interop_threads(2)
    require(torch.cuda.device_count()==1 and ctx.old.canonical_uuid(torch.cuda.get_device_properties(0).uuid)
            ==ctx.old.canonical_uuid(ctx.base.GPU0_UUID),'Visible GPU UUID/count differs')
    free,total=torch.cuda.mem_get_info(0)
    require(free>=13*ctx.base.GIB,'Post-context free margin insufficient')
    torch.cuda.set_per_process_memory_fraction(ctx.parent.BOUNDS['vram_allocator_bytes']/total,0)
    for key,name,attribute in (('frozen_science_helpers','_stageB_science','science'),
                              ('reconstruction_helpers','_stageB_input_contract','reconstruction')):
        item=ctx.lock[key]
        setattr(ctx,attribute,ctx.parent.checked_module(item['source'],item['sha256'],name))
    sys.path[:]=[v for v in sys.path if v not in ('',str(ctx.base.REPO),str(ctx.base.GAME/'Scripts'))]
    sys.path.insert(0,str(ctx.layout.scripts))
    random.seed(ctx.lock['seed']);np.random.seed(ctx.lock['seed']);torch.manual_seed(ctx.lock['seed'])
    torch.set_float32_matmul_precision('high')
    torch.backends.cuda.matmul.allow_tf32=True
    torch.backends.cudnn.allow_tf32=True
    torch.backends.cudnn.benchmark=True
    ctx.config=importlib.import_module('dqn.config');ctx.cfg=ctx.config.RL_CONFIG;ctx.metrics=ctx.config.metrics
    require(Path(ctx.config.MODEL_DIR)==ctx.paths['models'] and
            ctx.config.learning_control.path==ctx.paths['control'],'Private config paths differ')
    cfg=ctx.cfg
    require(cfg.memory_size==CAPACITY and cfg.state_size==11128 and cfg.frame_stack==4 and
            cfg.batch_size==BATCH and cfg.num_atoms==51 and cfg.num_joint_actions==81 and
            cfg.diagnostic_interval==20 and cfg.max_samples_per_frame==8 and
            cfg.priority_alpha==.7 and cfg.enable_amp and cfg.optimizer_fused and
            cfg.compile_full_loss and cfg.use_torch_compile and cfg.torch_compile_mode=='default' and
            cfg.replay_prefetch_slots==3 and cfg.replay_direct_state_fill,'Held recipe differs')
    require(cfg.per_priority_metric==('ce' if ctx.variant=='return_ce' else 'kl'), 'Role metric differs')
    require(ctx.config.RESET_METRICS is False,'Load-time metrics reset forbidden')
    require(not os.getenv('DQN_RECOMPUTED_CE_CAPTURE_DIR') and not os.getenv('DQN_EXECUTED_CE_TRACE_DIR'),
            'Observation flags forbidden')
    # Location-only isolation: constructor still probes _meta.npy before its
    # RAM-fallback guard even with an adapter. Never probe the live ring path.
    require(ctx.paths['tmpfs'].is_dir(),'Owned private tmpfs role path missing')
    cfg.replay_tmpfs_dir=str(ctx.paths['tmpfs'])
    ctx.metrics.training_enabled=False
    ctx.context,_=ctx.parent.bounded_json(ctx.manifest['retained_inputs']['metadata']['context'],read_only=True)
    item=ctx.manifest['retained_inputs']['attempts'][0]
    require(item['index']==1,'Only predeclared genuine attempt01 allowed')
    row,_=ctx.parent.bounded_json(item['receipt'],read_only=True)
    pin=item['payload']
    require(ctx.parent.stable_file(pin['path'],pin['sha256'],pin['bytes'])==pin,'Genuine source moved')
    payload=torch.load(pin['path'],map_location='cpu',weights_only=True,mmap=True)
    ctx.reconstruction.payload_contract(ctx,payload,row,1)
    require(ctx.parent.stable_file(pin['path'],pin['sha256'],pin['bytes'])==pin,'Genuine source moved on load')
    ctx.payload,ctx.original_row,ctx.original_item=payload,row,item
    latest=ctx.role['latest']
    require(ctx.parent.stable_file(latest['path'],latest['sha256'],latest['bytes'])==latest,'Latest copy differs')
    ctx.expected= torch.load(latest['path'],map_location='cpu',weights_only=True,mmap=True)
    ctx.replay=importlib.import_module('dqn.replay_buffer')
    ctx.training=importlib.import_module('dqn.training')
    ctx.agent_module=importlib.import_module('dqn.agent')
    ctx.native=importlib.import_module('dqn.native_sumtree')
    require(ctx.native.batch_update_status()['enabled'] and ctx.native.batch_update_status()['available'],
            'Actual private native batch update unavailable; no fallback')
    require(getattr(sys,'_is_gil_enabled',lambda:None)() is False,'Effective GIL changed after numerical imports')
    ctx.completed=[];ctx.entered_attempts=[];ctx.frame_credit_ledger=[]


class FixedReplayAdapter:
    """Test-owned states, genuine ordered indices, and the REAL six-million native tree.

    This replaces only the agent replay factory. Its synthetic eligible length
    is explicit; ensure_live_mmap/load never pretend to restore a live ring.
    """
    def __init__(self,ctx,capacity,state_size,alpha):
        require(capacity==CAPACITY and state_size==11128 and alpha==.7,'Adapter constructor differs')
        self.ctx=ctx;self.capacity=capacity;self.state_size=state_size;self.alpha=alpha
        self.lock=threading.RLock();self.tree=ctx.replay.SumTree(capacity)
        self.tree.size=capacity
        self._mmap_dir=None;self._ephof_base=capacity+192*1536
        self.storage_requests=[];self.load_requests=[];self.samples=0;self.updates=[]
        self.active_forward=None
        payload=ctx.payload;np=ctx.np
        fields=payload['inputs'];draw=payload['draw']
        require(draw['indices'].shape==(BATCH,),'Genuine indices geometry differs')
        self.batch=(fields['states'].numpy(),fields['actions'].numpy(),fields['rewards'].numpy(),
            fields['next_states'].numpy(),fields['dones'].numpy(),fields['horizons'].numpy(),
            fields['is_expert'].numpy(),np.asarray(draw['small_batch_fields']['actor_kind'],dtype=np.uint8).copy(),
            draw['indices'].numpy().astype(np.int64,copy=True),fields['weights'].numpy())
        require((self.batch[8]>=0).all(),'Negative genuine replay index')
        self.states=self.batch[0][:128]
        self.ring_indices=self.batch[8][self.batch[8]<capacity]
        require(len(self.ring_indices)>0,'No genuine PER rows')
        for index in np.unique(self.ring_indices):self.tree.update(int(index),1.)
        self.initial_native=ctx.native.batch_update_status()

    def __len__(self):return self.capacity

    def ensure_live_mmap(self,path):
        self.storage_requests.append(str(path))

    def load(self,path,verbose=False):
        self.load_requests.append(str(path))
        return False

    def sample(self,batch_size,beta=1.):
        require(batch_size==BATCH,'Fixed batch width differs')
        with self.lock:
            self.samples+=1
            require(self.samples<=ATTEMPTS+3,'Fixed producer draw bound exceeded')
            return self.batch

    def sample_into(self,batch_size,states_out,next_states_out,beta=1.):
        batch=self.sample(batch_size,beta)
        self.ctx.np.copyto(states_out,batch[0]);self.ctx.np.copyto(next_states_out,batch[3])
        return (states_out,*batch[1:3],next_states_out,*batch[4:])

    def update_priorities(self,indices,priorities,timing_out=None):
        ctx=self.ctx;np=ctx.np
        require(np.array_equal(indices,self.batch[8]),'Actual priority update reordered/remapped indices')
        require(self.active_forward is not None and np.array_equal(priorities,self.active_forward['priority']),
                'Packed priority readback differs from executed fifth vector')
        before=ctx.native.batch_update_status()
        # The held method performs epsilon/alpha, filters bank sentinels, and
        # calls actual SumTree.batch_update/native C without algorithm copies.
        ctx.replay.PrioritizedReplayBuffer.update_priorities(self,indices,priorities,timing_out=timing_out)
        after=ctx.native.batch_update_status()
        require(after['success_count']==before['success_count']+1 and
                after['fallback_count']==before['fallback_count'] and
                after['error_count']==before['error_count'],'Native update fallback/error/no-call')
        expected={}
        transformed=(np.abs(np.asarray(priorities).astype(np.float64))+1e-6)**self.alpha
        for index,value in zip(np.asarray(indices),transformed):
            if index<self.capacity:expected[int(index)]=float(value)
        ordered=np.array(list(expected),dtype=np.int64)
        wanted=np.array(list(expected.values()),dtype=np.float64)
        require(np.array_equal(self.tree.tree[ordered+self.capacity],wanted),
                'Native ordered duplicate-last leaves differ')
        nodes=self.tree.tree
        require(np.array_equal(nodes[1:self.capacity],nodes[2:2*self.capacity:2]+nodes[3:2*self.capacity:2]),
                'Native tree internal parent sums differ')
        require(np.count_nonzero(nodes[self.capacity:])==len(expected), 'Unaffected native leaf changed')
        record=dict(native_before=before,native_after=after,submitted_rows=len(indices),ring_rows=len(self.ring_indices),
            unique_ring_rows=len(expected),bank_rows=int((np.asarray(indices)>=self.capacity).sum()),
            ordered_indices_sha256=hashlib.sha256(np.asarray(indices,dtype=np.int64).tobytes()).hexdigest(),
            leaves_sha256=hashlib.sha256(nodes[ordered+self.capacity].tobytes()).hexdigest(),
            priorities_sha256=hashlib.sha256(np.asarray(priorities).tobytes()).hexdigest(),
            root=float(nodes[1]),all_internal_sums_exact=True,unaffected_leaves_zero=True)
        self.updates.append(record)


def four_clocks(ctx):
    return dict(training_steps=int(ctx.agent.training_steps),optimized_samples=int(ctx.agent.optimized_samples),
        frame_count=int(ctx.metrics.frame_count),learner_frame_count=int(ctx.metrics.learner_frame_count))


def named_optimizer(ctx):
    return {name:ctx.science.cpu(ctx,ctx.agent.optimizer.state.get(parameter,{}))
            for name,parameter in ctx.agent.online_net.named_parameters()}


def state_snapshot(ctx):
    a=ctx.agent;s=ctx.science
    return dict(online=s.cpu(ctx,a.online_net.state_dict()),target=s.cpu(ctx,a.target_net.state_dict()),
        optimizer=named_optimizer(ctx),scaler=copy.deepcopy(a.grad_scaler.state_dict()),clocks=four_clocks(ctx),
        optimizer_groups=[{key:copy.deepcopy(value) for key,value in group.items() if key!='params'}
            for group in a.optimizer.param_groups])


def describe_slots(ctx,slots):
    result={}
    for name,state in slots.items():
        result[name]=dict(initialized=bool(state),step=None if not state else float(state['step']),
            tensor_sha256=ctx.science.digest_tree(ctx,state))
    return result


def require_loaded(ctx):
    expected=ctx.expected;a=ctx.agent;s=ctx.science
    require(four_clocks(ctx)=={name:int(expected[name]) for name in four_clocks(ctx)},'Actual loaded four clocks differ')
    require(s.digest_tree(ctx,a.online_net.state_dict())==s.digest_tree(ctx,expected['online_state_dict']) and
            s.digest_tree(ctx,a.target_net.state_dict())==s.digest_tree(ctx,expected['target_state_dict']),
            'Actual strict loaded model tensors differ')
    require(s.digest_tree(ctx,a.optimizer.state_dict())==s.digest_tree(ctx,expected['optimizer_state_dict']),
            'Actual loaded optimizer tensors/groups differ')
    require(a.grad_scaler.state_dict()==expected['grad_scaler_state_dict'],'Actual saved scaler not restored')
    require(a.last_target_update_samples==expected['last_target_update_samples'] and
            a.lr_gear==expected['lr_gear'] and a.lr_anchor_step==expected['lr_anchor_step'], 'Loaded target/schedule differs')
    require(ctx.metrics.loaded_frame_count==expected['frame_count'] and
            ctx.metrics.loaded_measurement_frame_count==expected['measurement_frame_count'] and
            ctx.metrics.loaded_optimized_samples==expected['optimized_samples'] and
            ctx.metrics.measurement_frame_count==expected['measurement_frame_count'] and
            '_replay_pressure_anchor' not in a.__dict__ and '_replay_warmup_pending' not in a.__dict__,
            'Loaded cap8 anchors differ or unexpected warmup anchor')
    require(a._exact_graph_loaded and a._priority_phase.loaded,'Actual graph/priority phase load incomplete')
    stats=a._exact_inference_graphs.snapshot()
    require(stats['ready'] and stats['covered_shapes']==list(range(1,129)) and stats['capture_count']==128 and
            stats['postload_validations']==1 and stats['fallback_count']==0,'Actual128 graph load proof incomplete')
    require(all(group.get('fused') is True for group in a.optimizer.param_groups) and
            a.use_amp and type(a.grad_scaler) is ctx.torch.amp.GradScaler,'Actual fused Adam/AMP unavailable')
    require(a.device==ctx.torch.device('cuda:0') and a.online_net.training and
            not a.target_net.training and not a.infer_net.training,'Actual train/target/inference modes/device differ')
    exposure=a._learning_optimizer_exposure.snapshot()
    require(all(value==0 for value in exposure['total'].values()),'Constructor/load admitted an uncounted optimizer call')
    slots=describe_slots(ctx,named_optimizer(ctx))
    if ctx.variant=='kl18':
        require(sum(value['initialized'] for value in slots.values())==81 and all(
            value['step']==2155894 for value in slots.values() if value['initialized']), 'Initial actual81 saved Adam slots differ')
    return dict(clocks=four_clocks(ctx),graphs=stats,slots=slots,scaler=a.grad_scaler.state_dict(),
        phase=a._priority_phase.snapshot(),exposure=exposure,strict_model_optimizer_hashes_exact=True,
        memory_load_return=False,ring_restore_exercised=False,private_replay_path=str(a._ring_dir),
        modes=dict(online=a.online_net.training,target=a.target_net.training,infer=a.infer_net.training))


def construct_and_load(ctx):
    original=ctx.agent_module.PrioritizedReplayBuffer
    created=[]
    def factory(*args,**kwargs):
        require(not created,'More than one private replay factory call')
        value=FixedReplayAdapter(ctx,*args,**kwargs);created.append(value);return value
    ctx.agent_module.PrioritizedReplayBuffer=factory
    try:ctx.agent=ctx.agent_module.RainbowAgent(11128)
    finally:ctx.agent_module.PrioritizedReplayBuffer=original
    a=ctx.agent
    require(created==[a.memory] and a._exact_graph_requested and not a._exact_graph_loaded,
            'Actual constructor/factory/exact-load guard differs')
    require(a.compiled_training_loss is not None and a.compiled_training_loss_diagnostics is not None,
            'Constructor compile fallback; no rescue')
    a.stop()
    require(not a._train_thread.is_alive() and not a.running,'Private TrainWorker failed to join')
    old_prefetch=a._prefetcher
    require(old_prefetch is not None and not old_prefetch._thread.is_alive() and
            old_prefetch.produced_batches==0,'Constructor producer ran or failed to join')
    a._prefetcher=None
    del old_prefetch
    require(a.load(ctx.role['latest']['path'],show_status=True) is True,'Actual agent.load failed')
    ctx.torch.cuda.synchronize(a.device)
    ctx.loaded=require_loaded(ctx)
    write_json(ctx.paths['root']/'loaded-proof.json',ctx.loaded)
    # The actual128 graph constructor/load proof has completed. This deliberate
    # PRIVATE release makes subsequent isolated-learner feasibility honest.
    with a._training_lock,a._sync_lock:
        ctx.torch.cuda.synchronize(a.device)
        graphs=a._exact_inference_graphs
        graphs.slots.clear();graphs._pending=None
        a._exact_inference_graphs=None
        del graphs
        gc.collect();ctx.torch.cuda.empty_cache();ctx.torch.cuda.synchronize(a.device)
    ctx.graph_release=dict(explicit_private_release=True,after_actual_128_postload_proof=True,
        serving_during_learner=False,reserved_after=int(ctx.torch.cuda.memory_reserved(a.device)))
    write_json(ctx.paths['root']/'private-serving-graphs-released.json',ctx.graph_release)
    require(getattr(sys,'_is_gil_enabled',lambda:None)() is False,'Effective GIL changed during actual constructor')


def save_payload(ctx,path,value):
    path=Path(path)
    with path.open('xb') as stream:
        ctx.torch.save(value,stream);stream.flush();os.fsync(stream.fileno())
    path.chmod(0o444);fsync_directory(path.parent)
    return ctx.parent.stable_file(path,ctx.parent.digest(path),path.stat().st_size)


def grant_frame_credit(ctx,ordinal):
    require(ordinal==len(ctx.frame_credit_ledger)+1 and 1<=ordinal<=ATTEMPTS,'Credit ordinal/no19 violated')
    a=ctx.agent;m=ctx.metrics;initial=ctx.loaded['clocks']
    with m.lock:
        require(m.frame_count==initial['frame_count']+(ordinal-1)*FRAME_CREDIT and
                m.learner_frame_count==initial['learner_frame_count'] and
                m.measurement_frame_count==ctx.expected['measurement_frame_count'] and
                m.loaded_frame_count==initial['frame_count'] and
                m.loaded_optimized_samples==initial['optimized_samples'] and
                '_replay_pressure_anchor' not in a.__dict__ and '_replay_warmup_pending' not in a.__dict__,
                'Private credit/loaded anchor changed unexpectedly')
        before=int(m.frame_count);m.frame_count+=FRAME_CREDIT
        row=dict(ordinal=ordinal,before=before,after=int(m.frame_count),synthetic_frames=FRAME_CREDIT,
            real_ingested_frames=0,learner_frame_count=int(m.learner_frame_count),samples_planned=BATCH,cap=8)
        ctx.frame_credit_ledger.append(row)
    require(not ctx.training.replay_pressure_reached(a),'Predetermined cap8 credits insufficient')
    return row


def verify_progress(ctx,before,after,gradients,delta,found_inf,*,grad_norm):
    torch=ctx.torch;s=ctx.science
    require(delta['attempts_started']==delta['outcomes_recorded']==1 and delta['unavailable']==0 and
            delta['applied']+delta['amp_skipped']==1 and found_inf in (0.,1.), 'Actual outcome unavailable/ambiguous')
    skipped=delta['amp_skipped']==1
    require(skipped==(found_inf==1.),'Packed found_inf disagrees with exposure')
    records={};changed_online=0;changed_moments=0
    for name,old in before['optimizer'].items():
        new=after['optimizer'][name];grad=gradients[name]
        if skipped:
            require(s.digest_tree(ctx,old)==s.digest_tree(ctx,new),'AMP skip changed Adam state: '+name)
        elif grad is not None:
            require(s.finite(ctx,grad) and new and float(new['step'])==(float(old['step']) if old else 0)+1,
                    'Applied gradient slot did not advance exactly once: '+name)
        else:
            require(s.digest_tree(ctx,old)==s.digest_tree(ctx,new),'None-grad Adam slot changed: '+name)
        slot_changed=s.digest_tree(ctx,old)!=s.digest_tree(ctx,new)
        moment_changed=s.digest_tree(ctx,{key:old[key] for key in ('exp_avg','exp_avg_sq') if key in old})!=s.digest_tree(
            ctx,{key:new[key] for key in ('exp_avg','exp_avg_sq') if key in new})
        changed_moments+=int(moment_changed)
        records[name]=dict(before_initialized=bool(old),after_initialized=bool(new),gradient_present=grad is not None,
            before_step=None if not old else float(old['step']),after_step=None if not new else float(new['step']),
            state_changed=slot_changed,moments_changed=moment_changed)
    for name,value in before['online'].items():
        changed=not torch.equal(value,after['online'][name])
        changed_online+=int(changed and name in before['optimizer'])
        if skipped:require(not changed,'AMP skip changed online tensor: '+name)
    require(s.finite(ctx,after),'Nonfinite persistent state after attempt')
    if skipped:
        require(after['scaler']['scale']<before['scaler']['scale'],'Known AMP skip did not reduce actual scaler')
    else:
        require(math.isfinite(float(grad_norm)),'Applied outcome has nonfinite actual packed gradient norm')
        require(changed_online>0 and changed_moments>0,'Applied classification lacks actual parameter/moment progress')
    return dict(outcome='amp_skipped' if skipped else 'applied',found_inf=found_inf,slots=records,
        changed_online_parameters=changed_online,changed_adam_moment_slots=changed_moments,
        packed_grad_norm=float(grad_norm),scaler_before=before['scaler'],scaler_after=after['scaler'])


class StepObservers:
    """Observers outside compiled graphs; original forward/clip/finish run ONCE.

    The actual optimizer.step method is never rebound: supported fused-AMP
    exposure checks continue to inspect the original optimizer method identity.
    """
    def __init__(self,ctx):
        self.ctx=ctx;self.originals={};self.forward=None;self.gradients=None;self.finished=[]
        self.clip_calls=0;self.scaler_calls=dict(step=0,update=0)

    def install(self):
        ctx=self.ctx;a=ctx.agent;torch=ctx.torch
        for attribute in ('compiled_training_loss','compiled_training_loss_diagnostics'):
            original=getattr(a,attribute);self.originals[attribute]=original
            def observed(*args,_original=original,_diagnostic=attribute.endswith('_diagnostics'),**kwargs):
                require(self.forward is None,'More than one actual loss forward in a planned step')
                outputs=_original(*args,**kwargs)
                require(isinstance(outputs,tuple) and len(outputs)==5,'Actual KL compiled5 ABI changed')
                # Actual outputs copied before backward, with no second loss call.
                values=ctx.science.cpu(ctx,outputs)
                self.forward=dict(diagnostic=_diagnostic,ce=values[1].numpy(),priority=values[4].numpy(),
                    weighted_loss=float(values[0]),bc_loss=float(values[2]),diagnostics=values[3].tolist(),
                    actual_schedule=args[-1].detach().cpu().tolist(),
                    actual_lrs=[float(group['lr']) for group in a.optimizer.param_groups])
                require(values[4].shape==(BATCH,) and values[4].dtype==torch.float32 and
                        outputs[4].requires_grad is False and outputs[4].grad_fn is None,
                        'Actual fifth priority vector is not detached FP32')
                require(ctx.science.finite(ctx,values),'Actual executed loss/priority is nonfinite')
                ctx.agent.memory.active_forward=self.forward
                return outputs
            setattr(a,attribute,observed)
        original_clip=torch.nn.utils.clip_grad_norm_;self.originals['clip']=original_clip
        def clip(parameters,*args,**kwargs):
            self.clip_calls+=1
            require(self.clip_calls==1,'Multiple gradient clips in one planned attempt')
            actual=list(parameters)
            require([id(p) for p in actual]==[id(p) for p in a.online_net.parameters()], 'Unexpected clip owner')
            # This occurs after actual GradScaler.unscale_, before original clip.
            self.gradients={name:None if parameter.grad is None else parameter.grad.detach().cpu().clone()
                for name,parameter in a.online_net.named_parameters()}
            if ctx.current_ordinal in (1,ATTEMPTS):
                save_payload(ctx,ctx.paths['root']/('attempt-%02d-preclip.pt'%ctx.current_ordinal),
                    dict(ordinal=ctx.current_ordinal,gradients=self.gradients,unscaled=True,clipped=False))
            return original_clip(actual,*args,**kwargs)
        torch.nn.utils.clip_grad_norm_=clip
        exposure=a._learning_optimizer_exposure
        self.originals['finish']=exposure.finish
        def finish(ticket,mode,found_inf=None):
            result=self.originals['finish'](ticket,mode,found_inf)
            self.finished.append(dict(mode=mode,found_inf=None if found_inf is None else float(found_inf),
                ticket_epoch=ticket.epoch,ticket_finished=ticket.finished))
            return result
        exposure.finish=finish
        for method in ('step','update'):
            original=getattr(a.grad_scaler,method);self.originals['scaler_'+method]=original
            def called(*args,_method=method,_original=original,**kwargs):
                self.scaler_calls[_method]+=1
                return _original(*args,**kwargs)
            setattr(a.grad_scaler,method,called)
        return self

    def reset(self):
        self.forward=None;self.gradients=None;self.finished=[];self.clip_calls=0
        self.scaler_calls=dict(step=0,update=0);self.ctx.agent.memory.active_forward=None

    def close(self):
        a=self.ctx.agent
        for attribute in ('compiled_training_loss','compiled_training_loss_diagnostics'):
            if attribute in self.originals:setattr(a,attribute,self.originals[attribute])
        if 'clip' in self.originals:self.ctx.torch.nn.utils.clip_grad_norm_=self.originals['clip']
        if 'finish' in self.originals:a._learning_optimizer_exposure.finish=self.originals['finish']
        for method in ('step','update'):
            if 'scaler_'+method in self.originals:setattr(a.grad_scaler,method,self.originals['scaler_'+method])


def one_attempt(ctx,ordinal,prefetch,observers):
    a=ctx.agent;ctx.current_ordinal=ordinal
    credit=grant_frame_credit(ctx,ordinal)
    observers.reset()
    before=state_snapshot(ctx)
    exposure_before=a._learning_optimizer_exposure.snapshot()
    diagnostic_due=a.training_steps%ctx.cfg.diagnostic_interval==0
    require(diagnostic_due==(ordinal==ATTEMPTS),'Natural diagnostic clock differs; no reclocking')
    lease=None;lease_proof=None;primary_failure=None
    try:
        ctx.producer_allowed=True
        lease=prefetch.get(timeout=30.)
        ctx.producer_allowed=False
        require(lease is not None and lease.is_current,'No current prepared lease; no replacement')
        require(lease._owner is prefetch and len(lease.batch)==10 and
                ctx.np.array_equal(lease.batch[8],a.memory.batch[8]),'Actual owned fixed-input lease differs')
        lease_proof=dict(epoch=lease._epoch,owner_epoch=prefetch._epoch,current=bool(lease.is_current),
            source='actual three-slot ReplayPrefetcher',direct_fill=bool(prefetch.direct_state_fill))
        write_json(ctx.paths['root']/('attempt-%02d-entered.json'%ordinal),dict(ordinal=ordinal,
            before=four_clocks(ctx),synthetic_credit=credit,lease=lease_proof,diagnostic_due=diagnostic_due))
        # Register once immediately BEFORE the actual call, after proof I/O.
        ctx.entered_attempts.append(ordinal)
        result=ctx.training.train_step(a,prefetched_batch=lease)
    except BaseException as primary:
        primary_failure=primary
        try:
            write_json(ctx.paths['root']/('attempt-%02d-failure.json'%ordinal),dict(ordinal=ordinal,
                error=repr(primary),forward=observers.forward,finished=observers.finished,
                actual_train_call_entered=ordinal in ctx.entered_attempts,
                exposure=a._learning_optimizer_exposure.snapshot(),
                lease_acquired=lease is not None,lease_released=None if lease is None else lease._released,
                native=a.memory.updates[-1] if len(a.memory.updates)==ordinal else None))
        except BaseException as secondary:
            try:print('Secondary attempt evidence error: '+repr(secondary),file=sys.stderr,flush=True)
            except BaseException:pass
        raise
    finally:
        ctx.producer_allowed=False
        # Every acquired lease, including failed proof/publication, is covered.
        # The held train_step also releases it; PreparedBatch is idempotent.
        if lease is not None:
            try:lease.release()
            except BaseException as secondary:
                if primary_failure is None:raise
                try:print('Secondary lease release error: '+repr(secondary),file=sys.stderr,flush=True)
                except BaseException:pass
    require(result is not None,'Actual train_step returned None; ordinal consumed, no retry')
    ctx.torch.cuda.synchronize(a.device)
    after=state_snapshot(ctx)
    exposure_after=a._learning_optimizer_exposure.snapshot()
    delta={key:exposure_after['total'][key]-exposure_before['total'][key]
           for key in exposure_before['total']}
    require(observers.forward is not None and observers.gradients is not None and observers.clip_calls==1 and
            observers.scaler_calls==dict(step=1,update=1) and len(observers.finished)==1 and
            observers.finished[0]['mode']=='single_cuda_found_inf' and
            observers.finished[0]['ticket_finished'] is True,'Actual fused AMP/call/packed outcome route incomplete')
    progress=verify_progress(ctx,before,after,observers.gradients,delta,observers.finished[0]['found_inf'],
        grad_norm=ctx.metrics.last_grad_norm)
    require(after['clocks']['training_steps']==before['clocks']['training_steps']+1 and
            after['clocks']['optimized_samples']==before['clocks']['optimized_samples']+BATCH and
            after['clocks']['frame_count']==before['clocks']['frame_count'] and
            after['clocks']['learner_frame_count']==before['clocks']['learner_frame_count'],
            'Actual completed clock increment differs')
    require(len(a.memory.updates)==ordinal,'Native priority updates not exactly one per completed attempt')
    phase=a._priority_phase.snapshot()
    require(phase['valid'] and phase['priority_update_calls']==ordinal and
            phase['ring_rows_submitted']==ordinal*len(a.memory.ring_indices) and
            list(phase['last_diagnostics'].values())==observers.forward['diagnostics'][12:],
            'Actual phase/signed stats/packed readback did not join executed forward')
    require(float(result)==observers.forward['weighted_loss'] and
            float(ctx.metrics.last_bc_loss)==observers.forward['bc_loss'], 'Actual objective/BC packed scalars differ')
    require(ctx.training.replay_pressure_reached(a),'Expected exact cap8 boundary after fixed4096 update')
    row=dict(ordinal=ordinal,status='ATTEMPT_COMPLETE',before=before['clocks'],after=after['clocks'],
        diagnostic_due=diagnostic_due,forward=observers.forward,optimizer_progress=progress,
        actual_exposure_delta=delta,exposure_before=exposure_before,exposure_after=exposure_after,
        actual_finished=observers.finished,lease=lease_proof,lease_released=lease._released,
        native_priority=a.memory.updates[-1],phase=phase,
        persistent_before_sha256=ctx.science.digest_tree(ctx,before),
        persistent_after_sha256=ctx.science.digest_tree(ctx,after),synthetic_credit=credit,
        gradients_artifact_retained=ordinal in (1,ATTEMPTS))
    write_json(ctx.paths['root']/('attempt-%02d-result.json'%ordinal),row)
    ctx.completed.append(row)
    # Large independent before/after/gradient snapshots die before next lease.
    observers.gradients=None
    return row


def save_post_checkpoint(ctx):
    root=ctx.paths['root'];target=root/'post-step-checkpoint.pt'
    require(ctx.variant=='kl18' and len(ctx.completed)==ATTEMPTS and all(
        not Path(str(target)+suffix).exists() for suffix in ('','.tmp','.bak')),'Save target not unique or attempts incomplete')
    marker=dict(schema='robotron-raw-kl-stage-b-save-v1',variant='kl18',stage='entered',path=str(target))
    write_json(root/'save-entered.json',marker)
    ctx.agent.save(str(target),show_status=False,save_replay=False)
    require(target.is_file() and not target.is_symlink() and not Path(str(target)+'.tmp').exists() and
            not Path(str(target)+'.bak').exists(),'Actual save left unexpected paths')
    with target.open('rb') as stream:os.fsync(stream.fileno())
    target.chmod(0o444);fsync_directory(root)
    pin=ctx.parent.stable_file(target,ctx.parent.digest(target),target.stat().st_size)
    checkpoint=ctx.torch.load(target,map_location='cpu',weights_only=True,mmap=True)
    require({name:int(checkpoint[name]) for name in four_clocks(ctx)}==four_clocks(ctx) and
            checkpoint['priority_metric_phase']==ctx.agent._priority_phase.snapshot() and
            checkpoint['grad_scaler_state_dict']==ctx.agent.grad_scaler.state_dict() and
            ctx.science.digest_tree(ctx,checkpoint['optimizer_state_dict'])==
            ctx.science.digest_tree(ctx,ctx.agent.optimizer.state_dict()) and
            ctx.science.digest_tree(ctx,checkpoint['online_state_dict'])==
            ctx.science.digest_tree(ctx,ctx.agent.online_net.state_dict()) and
            ctx.science.digest_tree(ctx,checkpoint['target_state_dict'])==
            ctx.science.digest_tree(ctx,ctx.agent.target_net.state_dict()), 'Actual post-save state differs')
    require(ctx.parent.stable_file(target,pin['sha256'],pin['bytes'])==pin,'Post-save bytes moved')
    write_json(root/'save-complete.json',dict(marker,stage='complete',saved_checkpoint=pin))
    return pin


def run_kl18(ctx):
    a=ctx.agent
    require(four_clocks(ctx)==ctx.lock['stage_b']['initial_clocks'],'Actual448 start no longer matches fixed18 protocol')
    ctx.science.restore_rng(ctx,ctx.payload['rng'])
    ctx.producer_allowed=False
    prefetch=a._prefetcher=ctx.agent_module.ReplayPrefetcher(a.memory,BATCH,
        beta_fn=lambda:ctx.training._beta_schedule(ctx.metrics.frame_count),device=a.device,use_amp=a.use_amp,
        depth=3,min_replay_size=max(ctx.cfg.min_replay_to_train,BATCH),direct_state_fill=True,
        enabled_fn=lambda:ctx.producer_allowed and not ctx.training.replay_pressure_reached(a))
    observers=StepObservers(ctx).install()
    ctx.metrics.training_enabled=True;a.training_enabled=True
    primary=None
    try:
        for ordinal in range(1,ATTEMPTS+1):one_attempt(ctx,ordinal,prefetch,observers)
    except BaseException as error:
        primary=error;raise
    finally:
        ctx.producer_allowed=False;ctx.metrics.training_enabled=False;a.training_enabled=False
        try:
            observers.close()
            require(prefetch.close(timeout=10.) and not prefetch._thread.is_alive(),'Owned producer did not stop')
            ctx.torch.cuda.synchronize(a.device)
        except BaseException as cleanup:
            if primary is None:raise
            try:print('Secondary producer/observer cleanup error: '+repr(cleanup),file=sys.stderr,flush=True)
            except BaseException:pass
        a._prefetcher=None
    require(ctx.entered_attempts==list(range(1,ATTEMPTS+1)) and len(ctx.completed)==ATTEMPTS and
            a.training_steps==ctx.loaded['clocks']['training_steps']+ATTEMPTS and
            a.optimized_samples==ctx.loaded['clocks']['optimized_samples']+ATTEMPTS*BATCH,
            '18 consecutive actual attempts incomplete; no19')
    require(prefetch.produced_batches==a.memory.samples<=ATTEMPTS+3 and prefetch.direct_state_batches==prefetch.produced_batches,
            'Actual direct-fill producer bound/route differs')
    saved=save_post_checkpoint(ctx)
    applied=sum(row['optimizer_progress']['outcome']=='applied' for row in ctx.completed)
    return dict(actual_attempts=ATTEMPTS,applied_outcomes=applied,amp_skips=ATTEMPTS-applied,
        readiness_pass=applied>=1,saved_checkpoint=saved,attempts=[row['ordinal'] for row in ctx.completed],
        natural_diagnostic_ordinals=[row['ordinal'] for row in ctx.completed if row['diagnostic_due']],
        synthetic_frame_credit_ledger=ctx.frame_credit_ledger,synthetic_frames_total=ATTEMPTS*FRAME_CREDIT,
        real_ingested_frames=0,producer_batches=prefetch.produced_batches,direct_fill_batches=prefetch.direct_state_batches,
        final_clocks=four_clocks(ctx),final_phase=a._priority_phase.snapshot(),native=ctx.native.batch_update_status())


def run(ctx):
    setup(ctx);construct_and_load(ctx)
    if ctx.variant=='kl18':detail=run_kl18(ctx)
    else:
        require(ctx.agent._learning_optimizer_exposure.snapshot()['total']['attempts_started']==0 and
                four_clocks(ctx)==ctx.loaded['clocks'],'Fresh phase limb executed unexpected learner work')
        phase=ctx.agent._priority_phase.snapshot();spec=ctx.agent._priority_phase.spec
        if ctx.variant=='resume':
            require(spec['action']=='resume' and phase['metric']=='kl' and
                    phase['priority_update_calls']==ATTEMPTS and
                    phase['last_resume_record_sha256']==ctx.role['phase_record']['sha256'], 'Actual KL resume phase differs')
        else:
            require(spec['action']=='start' and phase['metric']=='ce' and phase['predecessor']['metric']=='kl' and
                    phase['priority_update_calls']==0 and phase['ring_rows_submitted']==0,
                    'Actual explicit return-to-CE phase differs')
        detail=dict(actual_attempts=0,readiness_pass=True,applied_outcomes=0,loaded_phase=phase,
            source_checkpoint=ctx.role['source'],latest_checkpoint=ctx.role['latest'])
    ctx.science.modules_private(ctx)
    ctx.base.verify_source_copies(ctx.layout,ctx.manifest['sources'])
    genuine=ctx.original_item['payload']
    require(ctx.parent.stable_file(genuine['path'],genuine['sha256'],genuine['bytes'])==genuine,
            'Genuine fixed-input source moved during owned role')
    require(ctx.parent.read_lock()==ctx.lock,'Final source lock changed')
    require(ctx.parent.read_role_input(ctx.layout,ctx.variant,ctx.parent.digest(ctx.layout.output/'launch-manifest.json'))==ctx.role,
            'Final role input changed')
    require(getattr(sys,'_is_gil_enabled',lambda:None)() is False,'Final effective GIL changed')
    ctx.base.guard_live_resources(allowed_pids={os.getpid(),os.getppid()},expected_main=ctx.manifest['main_owners'])
    return dict(status='OBSERVATIONS_COMPLETE',variant=ctx.variant,qualification_pass=False,
        constructor_verified=True,phase_load_verified=True,loaded_proof=ctx.loaded,
        private_serving_graph_release=ctx.graph_release,source_lock_sha256=ctx.parent.SOURCE_LOCK_SHA256,
        peak_cuda_allocated=ctx.torch.cuda.max_memory_allocated(0),peak_cuda_reserved=ctx.torch.cuda.max_memory_reserved(0),
        scope='Actual private constructor/load then isolated whole learner with fixed-input/native-tree adapter; not full live replay/serving',
        **detail)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--variant',required=True,choices=ROLES)
    args=parser.parse_args(argv);ctx=None
    try:
        ctx=bootstrap(args.manifest,args.variant)
        result=run(ctx)
        write_json(ctx.paths['root']/'phase-result.json',result)
        return 0
    except BaseException as primary:
        if ctx is not None:
            try:
                write_json(ctx.paths['root']/'phase-failure.json',dict(status='INVALID_OR_INCOMPLETE',variant=ctx.variant,
                    error=repr(primary),traceback=traceback.format_exc(),qualification_pass=False,
                    entered_attempts=getattr(ctx,'entered_attempts',[]),completed_attempts=[v['ordinal'] for v in getattr(ctx,'completed',[])],
                    synthetic_frame_credit_ledger=getattr(ctx,'frame_credit_ledger',[])))
            except BaseException as secondary:
                try:print('Secondary failure evidence error: '+repr(secondary),file=sys.stderr,flush=True)
                except BaseException:pass
        try:traceback.print_exc()
        except BaseException:pass
        return 1


if __name__=='__main__':
    raise SystemExit(main())

