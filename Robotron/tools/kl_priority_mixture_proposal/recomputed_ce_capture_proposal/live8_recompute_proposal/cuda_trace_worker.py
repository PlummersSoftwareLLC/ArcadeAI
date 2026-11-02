#!/usr/bin/env python3
"""Owned fresh-process conditional reconstruction of eight retained live PREs.

Numerical imports are forbidden until exact parent identity, token, delegated
cgroup, private paths/environment/source bundle and resource guards pass.
This is source-only preparation; no actual agent/server or learning claim.
"""
from __future__ import annotations
import argparse
import contextlib
import copy
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import resource
import stat
import sys
import traceback
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
INPUT_NAMES = ('states', 'actions', 'rewards', 'next_states', 'dones', 'horizons', 'is_expert', 'weights')
CONSTANT_NAMES = ('num_fire', 'num_atoms', 'v_min', 'v_max', 'delta_z', 'gamma', 'smooth_eps',
                  'branch_aux', 'bc_floor', 'q_temperature', 'q_margin', 'diagnostics')
TRACE_NAMES = ('projected', 'joint_log_p_taken', 'per_row_bc', 'per_row_q_policy', 'per_row_margin',
               'target_p_taken', 'unclipped_support', 'bc_contribution', 'q_contribution', 'margin_contribution')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe(item) for item in value]
    return value


def write_json(path, value):
    """Create-only durable publication, with no temporary atomic names."""
    path = Path(path)
    with path.open('x') as stream:
        json.dump(safe(value), stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o444)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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
    return SimpleNamespace(parent=parent,base=base,old=old,lock=lock,manifest=manifest,
        layout=layout,variant=variant,paths=layout.phase(variant))


def setup(ctx):
    import numpy as np
    import torch
    ctx.np,ctx.torch=np,torch
    torch.set_num_threads(2);torch.set_num_interop_threads(2)
    require(torch.cuda.device_count()==1 and ctx.old.canonical_uuid(torch.cuda.get_device_properties(0).uuid)
            ==ctx.old.canonical_uuid(ctx.base.GPU0_UUID),'Visible GPU UUID/count differs')
    free,total=torch.cuda.mem_get_info(0)
    require(free>=13*ctx.base.GIB,'Post-context GPU free margin insufficient')
    torch.cuda.set_per_process_memory_fraction(ctx.parent.BOUNDS['vram_allocator_bytes']/total,0)
    require(getattr(sys,'_is_gil_enabled',lambda:None)() is False,'Effective GIL must remain disabled')
    for key,name in (('frozen_science_helpers','_live8_science'),('conditional_helpers','_live8_conditional')):
        item=ctx.lock[key]
        setattr(ctx,'science' if key=='frozen_science_helpers' else 'conditional',
            ctx.parent.checked_module(item['source'],item['sha256'],name))
    sys.path[:]=[value for value in sys.path if value not in ('',str(ctx.base.REPO),str(ctx.base.GAME/'Scripts'))]
    sys.path.insert(0,str(ctx.layout.scripts))
    ctx.config=importlib.import_module('dqn.config')
    require(Path(ctx.config.MODEL_DIR)==ctx.paths['models'] and ctx.config.learning_control.path==ctx.paths['control'],
            'Model/control import escaped owned private paths')
    context_pin=ctx.manifest['retained_inputs']['metadata']['context']
    ctx.context,_=ctx.parent.bounded_json(context_pin,read_only=True)
    ctx.cfg=ctx.config.RL_CONFIG
    primitive=lambda cfg:{name:value for name,value in vars(cfg).items() if value is None or type(value) in (bool,int,float,str)}
    captured=ctx.context['config']
    require(set(captured)==set(primitive(ctx.cfg)),'Captured scientific config keyset differs')
    for name,value in captured.items():
        require(value is None or type(value) in (bool,int,float,str),'Nonprimitive captured configuration')
        setattr(ctx.cfg,name,value)
    require(primitive(ctx.cfg)==captured and ctx.cfg.batch_size==4096 and ctx.cfg.state_size==11128
            and ctx.cfg.num_atoms==51 and ctx.cfg.num_joint_actions==81
            and ctx.cfg.torch_compile_mode=='default' and ctx.cfg.c51_target_smoothing==0
            and ctx.cfg.use_torch_compile and ctx.cfg.compile_full_loss and ctx.cfg.enable_amp,
            'Held PRE geometry/profile differs')
    require(str(torch.__version__)==ctx.context['runtime']['torch']
            and torch.version.cuda==ctx.context['runtime']['cuda'],'Captured Torch/CUDA runtime version differs')
    # replay_tmpfs_dir is retained as an opaque scientific config string. No
    # replay/agent/training is imported or constructed, and this path is not used.
    model=importlib.import_module('dqn.model')
    ctx.offline=importlib.import_module('dqn.offline_loss_kernel')
    require(ctx.parent.digest(model.__file__)==ctx.lock['source_files']['model.py']['sha256']
            and ctx.parent.digest(ctx.offline.__file__)==ctx.lock['offline_loss_sha256'],'Private model/loss source differs')
    online,target=model.RainbowNet(11128).cuda(),model.RainbowNet(11128).cuda()
    device=torch.device('cuda:0')
    require(model.device==device and all(parameter.requires_grad for net in (online,target) for parameter in net.parameters()),
            'Source-default model/device/requires_grad differs')
    # Inert OWNED optimizer/scaler exist only for actual forbidden-call hooks.
    # Their empty state is not the captured live Adam/scaler and is never loaded.
    ctx.agent=SimpleNamespace(online_net=online,target_net=target,device=device,
        optimizer=torch.optim.AdamW(online.parameters(),lr=1e-4),grad_scaler=torch.amp.GradScaler('cuda'))
    ctx.kernels={};ctx.rows=[];ctx.attempted_forward_indices=[]
    ctx.science.modules_private(ctx)
    require(getattr(sys,'_is_gil_enabled',lambda:None)() is False,'Private model/loss import changed effective GIL')


def draw_contract(payload,row,capture_id):
    draw=payload['draw']
    require(draw['capture_id']==payload['capture_id']==row['draw_capture_id']==capture_id
            and draw['schema']=='robotron-replay-draw-observation-v1','Raw draw/session identity differs')
    outcome=payload['outcome']
    require(payload['attempt']==row['index']==outcome['index'] and all(outcome[key]==row[key] for key in
            ('before','at_loss','after','optimizer_outcome','actual_exposure_delta','draw_capture_id',
             'prefetch','prefetch_begin','prefetch_pre_loss','prefetch_exit')),
            'Raw outcome does not join original compact receipt')
    return draw


def payload_contract(ctx,payload,row,index):
    torch=ctx.torch
    require(payload['attempt']==index and payload['capture_id']==ctx.context['capture_id']==row['draw_capture_id']
            and payload['nonfinite_copies']==0 and ctx.science.finite(ctx,payload),'Malformed/nonfinite captured PRE')
    draw=draw_contract(payload,row,ctx.context['capture_id'])
    pre=payload['pre_context']
    require(pre['config']==ctx.context['config'] and pre['loss_sha256']==ctx.lock['original_loss_sha256']
            and pre['use_amp'] is True and pre['modes']==dict(online=True,target=False)
            and pre['clocks']==row['at_loss'],'Captured PRE config/clocks/modes/original4 differs')
    require(pre['learner_device']==pre['schedule_device']=='cuda:0' and pre['input_devices']==['cuda:0']*8,
            'Actual capture did not use its owned logical CUDA device')
    require(pre['kernel_constants']['diagnostics'] is (index==7),'Captured actual diagnostic route differs')
    require(torch.get_float32_matmul_precision()==pre['matmul_precision']
            and bool(torch.backends.cuda.matmul.allow_tf32)==pre['tf32_matmul']
            and bool(torch.backends.cudnn.allow_tf32)==pre['tf32_cudnn']
            and bool(torch.backends.cudnn.benchmark)==pre['cudnn_benchmark'],'Offline numeric policy differs')
    require(set(payload['inputs'])==set(INPUT_NAMES),'Actual8 input names differ')
    dtypes=(torch.float32,torch.long,torch.float32,torch.float32,torch.float32,torch.float32,torch.bool,torch.float32)
    for name,dtype in zip(INPUT_NAMES,dtypes):
        value=payload['inputs'][name]
        require(isinstance(value,torch.Tensor) and value.device.type=='cpu' and value.dtype==dtype
                and tuple(value.shape)==((4096,11128) if name in ('states','next_states') else (4096,)),
                'Actual FP32 batch/input ABI differs: '+name)
    require(payload['schedule'].shape==(3,) and payload['schedule'].dtype==torch.float32
            and payload['actual']['ce'].shape==(4096,) and payload['actual']['ce'].dtype==torch.float32,
            'Actual schedule/CE ABI differs')
    require(isinstance(draw['supplied_weights_float32'],torch.Tensor)
            and draw['supplied_weights_float32'].dtype==torch.float32
            and torch.equal(payload['inputs']['weights'],draw['supplied_weights_float32']),
            'Consumed weights do not join exact original draw')
    for name in ('actions','rewards','dones','horizons','is_expert'):
        require(torch.equal(payload['inputs'][name],torch.as_tensor(draw['small_batch_fields'][name],dtype=payload['inputs'][name].dtype,device='cpu')),
                'Consumed small field differs from original draw: '+name)
    # Actual model features include signed offsets/velocities and passthrough
    # globals. Finite/shape/dtype+exact captured bytes are the state contract;
    # the synthetic fixture's0..1 range is deliberately inapplicable here.
    require(torch.all((payload['inputs']['actions']>=0)&(payload['inputs']['actions']<81)),'Captured action range differs')


def snapshot(ctx):
    a,s=ctx.agent,ctx.science
    return dict(online=s.digest_tree(ctx,a.online_net.state_dict()),target=s.digest_tree(ctx,a.target_net.state_dict()),
        optimizer=s.digest_tree(ctx,a.optimizer.state_dict()),scaler=copy.deepcopy(a.grad_scaler.state_dict()))


def retain_readout_inputs(ctx,actual,payload,row,directory):
    torch=ctx.torch
    projected=actual['conditional']['projected'].detach().float().cpu()
    ce=actual['ce'].detach().float().cpu()
    entropy=-(projected*projected.clamp_min(1e-12).log()).sum(dim=1)
    signed_kl=ce-entropy
    values=dict(emitted_weights=payload['inputs']['weights'],actual_ce=payload['actual']['ce'],
        recomputed_ce=ce,recomputed_entropy=entropy,recomputed_kl_signed=signed_kl,
        recomputed_kl_nonnegative=signed_kl.clamp_min(0),draw=payload['draw'])
    record=ctx.conditional.save_payload(ctx,directory/'conditional-readout-inputs.pt',dict(
        scope='FP32 CPU arithmetic on retained conditional target/CE; not actual executed entropy/KL',**values))
    require(projected.shape==(4096,51) and ctx.science.finite(ctx,values),'Conditional readout shape/finite interpretation differs')
    return dict(payload=record,scope='Emitted weights and actual/recomputed CE plus conditional H/signed+clamped KL retained',
        formula='H=-(projected*log(clamp_min(projected,1e-12))).sum(1); KLsigned=recomputedCE-H; KLnonnegative=clamp_min(KLsigned,0)',
        reduction_device='cpu',dtype='torch.float32',
        priority_readout_policy='Separate pinned CPU analysis: actual emitted versus freshactualCE versus freshrecomputedCE versus freshsameforwardKL; selected-row sensitivity only, no new whole-tree IS claim')


def forward_and_retain(ctx,kernel,inputs,schedule,payload,item,row,index,pre_rng,directory):
    torch,s,a=ctx.torch,ctx.science,ctx.agent
    require(index not in ctx.attempted_forward_indices,'Duplicate conditional forward; no retry')
    ctx.attempted_forward_indices.append(index)
    with ctx.conditional.forbidden_offline_updates(ctx) as calls:
        with torch.autocast(device_type='cuda',dtype=torch.float16):
            outputs=kernel(*inputs,schedule)
    torch.cuda.synchronize(a.device)
    after_rng=s.rng_state(ctx)
    record=ctx.conditional.save_payload(ctx,directory/'conditional-recomputed.pt',dict(
        scope='CONDITIONAL RECOMPUTED; not actual executed target',raw_outputs=outputs,
        expected_actual_capture=payload['actual'],rng_before=pre_rng,rng_after=after_rng,
        source_capture_payload=item['payload'],source_capture_receipt=item['receipt'],
        four_readout_inputs=dict(emitted_weights=payload['inputs']['weights'],actual_ce=payload['actual']['ce'])))
    # Scientific tensors and RNG are durable before ABI, finite or tolerance
    # interpretation. A fault retains them and never substitutes another row.
    require(isinstance(outputs,tuple) and len(outputs)==5 and isinstance(outputs[4],tuple) and len(outputs[4])==10,
            'Conditional five-output ABI differs')
    actual=dict(weighted_loss=outputs[0],ce=outputs[1],bc_loss=outputs[2],diagnostic_values=outputs[3],
        conditional={name:value for name,value in zip(TRACE_NAMES,outputs[4])})
    require(s.finite(ctx,actual),'Nonfinite conditional forward; retained raw interpretation invalid')
    return actual,record,after_rng,dict(calls)


def reconstruct_one(ctx,item):
    torch,s,a=ctx.torch,ctx.science,ctx.agent
    index=item['index'];directory=ctx.paths['root']/('attempt-%02d'%index)
    directory.mkdir(mode=0o700)
    write_json(directory/'entered.json',dict(index=index,source_payload=item['payload'],source_receipt=item['receipt']))
    row,row_pin=ctx.parent.bounded_json(item['receipt'],read_only=True)
    require(row_pin==item['receipt'],'Original row identity changed')
    source=item['payload']
    require(ctx.parent.stable_file(source['path'],source['sha256'],source['bytes'])==source,'Original PRE identity changed before load')
    payload=torch.load(source['path'],map_location='cpu',weights_only=True)
    require(ctx.parent.stable_file(source['path'],source['sha256'],source['bytes'])==source,'Original PRE changed during weights_only load')
    payload_contract(ctx,payload,row,index)
    pre=payload['pre_context']
    for name,net in (('online',a.online_net),('target',a.target_net)):
        expected=net.state_dict()
        require(set(payload[name])==set(expected) and all(isinstance(payload[name][key],torch.Tensor)
                and payload[name][key].device.type=='cpu' and payload[name][key].dtype==value.dtype
                and payload[name][key].shape==value.shape for key,value in expected.items()),
                'Captured PRE state ABI/dtype differs: '+name)
    a.online_net.load_state_dict(payload['online'],strict=True);a.target_net.load_state_dict(payload['target'],strict=True)
    a.online_net.train(pre['modes']['online']);a.target_net.train(pre['modes']['target'])
    inputs=[payload['inputs'][name].to(device=a.device) for name in INPUT_NAMES]
    schedule=payload['schedule'].to(device=a.device)
    diagnostic=pre['kernel_constants']['diagnostics']
    if diagnostic not in ctx.kernels:
        module=ctx.offline.TrainingLoss(a.online_net,a.target_net,SimpleNamespace(**pre['config']),diagnostics=diagnostic,trace_rows=True)
        require({name:getattr(module,name) for name in CONSTANT_NAMES}==pre['kernel_constants'],'Offline loss constants differ')
        ctx.kernels[diagnostic]=(ctx.conditional.compile_loss(ctx,module),pre['kernel_constants'])
    kernel,constants=ctx.kernels[diagnostic]
    require(constants==pre['kernel_constants'] and torch.is_grad_enabled(),'Cached constants/grad-enabled lowering differs')
    before=snapshot(ctx)
    require(before['online']==s.digest_tree(ctx,payload['online']) and before['target']==s.digest_tree(ctx,payload['target']),
            'Fresh loaded models do not match exact captured PRE tensor fingerprints')
    s.restore_rng(ctx,payload['rng']);pre_rng=s.rng_state(ctx)
    require(s.digest_tree(ctx,pre_rng)==s.digest_tree(ctx,payload['rng']),'PRE RNG did not restore exactly')
    actual,retained,after_rng,calls=forward_and_retain(ctx,kernel,inputs,schedule,payload,item,row,index,pre_rng,directory)
    comparison,mask=ctx.conditional.compare_ce(ctx,actual['ce'],payload['actual']['ce'])
    mask_pin=ctx.conditional.save_payload(ctx,directory/'ce-mismatch-mask.pt',dict(ce=mask))
    readouts=retain_readout_inputs(ctx,actual,payload,row,directory)
    after=snapshot(ctx)
    require(before==after and calls==dict(optimizer_step=0,scaler_step=0,scaler_update=0)
            and all(parameter.grad is None for net in (a.online_net,a.target_net) for parameter in net.parameters()),
            'Offline forward changed model/owned inert optimizer/scaler or gradients')
    require(getattr(sys,'_is_gil_enabled',lambda:None)() is False,'Offline compile/forward changed effective GIL')
    require(ctx.parent.stable_file(source['path'],source['sha256'],source['bytes'])==source,'Original PRE changed after forward')
    rng_changed=s.digest_tree(ctx,pre_rng)!=s.digest_tree(ctx,after_rng)
    result=dict(index=index,status='OBSERVATIONS_COMPLETE',backend=row['backend'],diagnostics=diagnostic,
        qualification_pass=False,comparison_pass=comparison['passed'],interpretation_requires_review=not comparison['passed'] or rng_changed,
        comparison_scope='Only original-tolerance4096 conditional CE; weighted loss/BC/diagnostics retained, not compared',
        source_receipt=item['receipt'],source_payload=source,original_optimizer_outcome=row['optimizer_outcome'],
        retained_conditional_payload=retained,ce_mismatch_mask=mask_pin,ce_comparison=comparison,
        pre_context=pre,model_before=before,model_after=after,update_guard_counts=calls,
        input_state_ranges={name:dict(minimum=float(payload['inputs'][name].min()),maximum=float(payload['inputs'][name].max()))
            for name in ('states','next_states')},
        parameter_grad_flags_scope='Source-inferred defaults from pinned model/agent/training; not an independently captured requires_grad field',
        inherited_sampler_unknown_scope='Original draw.unknown optimizer_outcome/full_states labels concern standalone sampler metadata only; outer receipt/exposure and payload provide actual outcome/full PRE',
        rng_observations=dict(pre=s.digest_tree(ctx,pre_rng),post=s.digest_tree(ctx,after_rng),post_changed=rng_changed,
            scope='Sequential observations, not coherent all-thread live anchor'),
        four_readout_inputs=readouts,
        logical_device_mapping=dict(captured=pre['learner_device'],offline=str(a.device),offline_uuid=ctx.base.GPU0_UUID,
            limitation='Logical cuda:0 equality does not imply same physical live training GPU'))
    write_json(directory/'attempt-result.json',result)
    # No tensor references survive this call: raw payload, device batch and
    # grad-enabled output graph drain before the next independent PRE is loaded.
    return result


def recompute8(ctx):
    for item in ctx.manifest['retained_inputs']['attempts']:
        ctx.rows.append(reconstruct_one(ctx,item))
    require(ctx.attempted_forward_indices==list(range(1,9)) and len(ctx.rows)==8,'All original8 conditional forwards required')
    require(ctx.parent.bind_inputs(ctx.lock)==ctx.manifest['retained_inputs'],'Final input identity/provenance changed')
    return dict(status='OBSERVATIONS_COMPLETE',variant=ctx.variant,qualification_pass=False,
        comparison_pass=all(row['comparison_pass'] for row in ctx.rows),
        interpretation_requires_review=any(row['interpretation_requires_review'] for row in ctx.rows),attempts=ctx.rows,
        comparison_scope='CONDITIONAL CE ONLY at original tolerances; no four-output parity or learning qualification',
        conditional_recomputed=True,executed_target_observed=False,grad_enabled=True,optimizer_steps=0,
        update_guard_counts=dict(optimizer_step=0,scaler_step=0,scaler_update=0),explicit_worker_backward_calls=0,
        backward_evidence_scope='Source-level explicit worker calls plus all gradsNone; not AOT/autograd-engine counting',
        actual_attempts_in_this_process=0,source_lock_sha256=ctx.parent.SOURCE_LOCK_SHA256,
        peak_cuda_allocated=ctx.torch.cuda.max_memory_allocated(0),peak_cuda_reserved=ctx.torch.cuda.max_memory_reserved(0),
        limitations=['Conditional projected targets/entropy/KL are not actual executed observations',
            'CE agreement cannot bound missing actual entropy/KL or replay priority ranks',
            'Private inert optimizer/scaler are forbidden-call sentinels, not original captured Adam/scaler state',
            'Eight observed batches do not establish replay-population, learning-quality or throughput conclusions'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--variant',required=True,choices=('recompute8',))
    args=parser.parse_args(argv);ctx=None
    try:
        ctx=bootstrap(args.manifest,args.variant);setup(ctx);result=recompute8(ctx)
        ctx.science.modules_private(ctx);ctx.base.verify_source_copies(ctx.layout,ctx.manifest['sources'])
        require(ctx.parent.read_lock()==ctx.lock,'Final source lock changed')
        ctx.base.guard_live_resources(allowed_pids={os.getpid(),os.getppid()},expected_main=ctx.manifest['main_owners'])
        write_json(ctx.paths['root']/'phase-result.json',result)
        return 0
    except BaseException as error:
        if ctx is not None:
            try:
                write_json(ctx.paths['root']/'phase-failure.json',dict(status='INVALID_OR_INCOMPLETE',variant=ctx.variant,
                    error=repr(error),traceback=traceback.format_exc(),completed_indices=[row['index'] for row in getattr(ctx,'rows',[])],
                    attempted_forward_indices=getattr(ctx,'attempted_forward_indices',[]),
                    offline_update_guard_counts=getattr(ctx,'offline_update_guard_counts',None)))
            except BaseException as persistence:
                try:print('Failure-evidence error: '+repr(persistence),file=sys.stderr,flush=True)
                except BaseException:pass
        try:traceback.print_exc()
        except BaseException:pass
        return 1


if __name__=='__main__':
    raise SystemExit(main())
