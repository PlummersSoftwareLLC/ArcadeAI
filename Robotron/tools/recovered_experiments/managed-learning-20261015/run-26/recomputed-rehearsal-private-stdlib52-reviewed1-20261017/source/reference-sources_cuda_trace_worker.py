#!/usr/bin/env python3
"""Internal guarded warmup-only repeatability diagnostic; no startup numerics.

Only the explicitly launched owned parent may release this worker's token.
No optimizer step, ON observer or full-training parity qualification is performed.
"""
from __future__ import annotations
import argparse
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
import sys
import traceback
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
FIELDS = ('states', 'actions', 'rewards', 'next_states', 'dones', 'horizons',
          'is_expert', 'actor_kind', 'indices', 'weights')


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
    with Path(path).open('x') as stream:
        json.dump(safe(value), stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


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
    trained = layout.output / 'inputs/trained.pt'
    require(parent.stable_file(trained,lock['checkpoint']['sha256'],lock['checkpoint']['bytes']) ==
            manifest['trained_fixture']['copied'], 'Private trained checkpoint identity differs')
    base.guard_live_resources(allowed_pids={os.getpid(), os.getppid()}, expected_main=manifest['main_owners'], initial=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 30, 1 << 30))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    return SimpleNamespace(parent=parent, base=base, old=old, lock=lock, manifest=manifest,
                           layout=layout, variant=variant, paths=layout.phase(variant), trained=trained)


def load_science(ctx):
    record = ctx.lock['frozen_science_helpers']
    module = ctx.parent.checked_module(record['source'], record['sha256'], '_frozen_warmup_science')
    # Only the immutable setup/input/CPU/RNG helper functions are reused.
    # Their bootstrap and eight-step runner are never called. inputs() reads
    # this NEW numerical lock; all numerical fixture algorithms stay pinned.
    module.HERE = HERE
    return module


def full_state(ctx):
    a, s = ctx.agent, ctx.science
    # Fresh roles necessarily have distinct process-local exposure identities.
    # Keep those in the complete before/after optimizer observations, while
    # scientific state fingerprints compare every counter/config field.
    exposure=a._learning_optimizer_exposure.snapshot()
    exposure={key:value for key,value in exposure.items() if key not in ('process_id','instance_monotonic_ns')}
    return dict(online=a.online_net.state_dict(), target=a.target_net.state_dict(),
        inference=a.infer_net.state_dict(), optimizer=a.optimizer.state_dict(),
        scaler=a.grad_scaler.state_dict(), clocks=s.clocks(ctx),
        exposure=exposure,
        modes=[net.training for net in (a.online_net,a.target_net,a.infer_net)])


def rng_hashes(ctx, value):
    return {name:ctx.science.digest_tree(ctx, part) for name,part in value.items()}


def tolerance_for(ctx, path, floating=True):
    if not floating:
        return dict(rtol=0.,atol=0.)
    key = 'ce' if path.endswith('/ce') else 'scalars' if path.endswith(('/loss','/bc_loss')) else 'gradient'
    return dict(ctx.lock['tolerances'][key])


def compare_payload(ctx, actual, expected, case, *, records=None, masks=None):
    """Structural/nonfinite errors are fatal; only finite numeric mismatches return.

    Full payloads already exist before this function starts. Every failed tensor
    retains a complete boolean mask plus bounded coordinate examples; nothing
    outside the native torch assert_close failure boundary is swallowed.
    """
    torch, s = ctx.torch, ctx.science
    records = [] if records is None else records
    masks = {} if masks is None else masks
    def walk(left, right, path):
        if isinstance(right,torch.Tensor):
            require(isinstance(left,torch.Tensor) and left.shape == right.shape and left.dtype == right.dtype,
                    'Structural tensor mismatch: '+path)
            require(s.finite(ctx,left) and s.finite(ctx,right), 'Nonfinite unscaled warmup: '+path)
            left,right = left.detach().cpu(),right.detach().cpu()
            tol = tolerance_for(ctx,path,left.is_floating_point())
            difference = (left.double()-right.double()).abs()
            allowed = tol['atol']+tol['rtol']*right.double().abs()
            bad = ~torch.isclose(left,right,**tol,equal_nan=False)
            record = dict(path=path,shape=list(left.shape),dtype=str(left.dtype),tolerance=tol,
                actual_sha256=hashlib.sha256(s.tensor_bytes(ctx,left)).hexdigest(),
                expected_sha256=hashlib.sha256(s.tensor_bytes(ctx,right)).hexdigest(),
                max_abs=float(difference.max()) if difference.numel() else 0.,
                l2_error=float(torch.linalg.vector_norm((left.double()-right.double()).reshape(-1))),
                reference_l2=float(torch.linalg.vector_norm(right.double().reshape(-1))))
            try:
                torch.testing.assert_close(left,right,**tol,equal_nan=False)
                record.update(passed=True,violations=0,coordinate_examples=[])
                require(not bool(bad.any()), 'Comparison predicate differs from original assert_close: '+path)
            except AssertionError as error:
                require(bool(bad.any()), 'Assertion not explained by finite tolerance predicate: '+path)
                indices = torch.nonzero(bad,as_tuple=False)
                examples=[]
                for coordinate in indices[:16].tolist():
                    key=tuple(coordinate)
                    examples.append(dict(index=coordinate,actual=float(left[key]),expected=float(right[key]),
                        signed_difference=float(left[key].double()-right[key].double()),
                        absolute_error=float(difference[key]),allowed_bound=float(allowed[key])))
                worst=torch.nonzero(bad & (difference==difference[bad].max()),as_tuple=False)[0].tolist()
                worst_key=tuple(worst)
                record.update(passed=False,violations=int(bad.sum()),coordinate_examples=examples,
                    max_violation=dict(index=worst,actual=float(left[worst_key]),expected=float(right[worst_key]),
                        signed_difference=float(left[worst_key].double()-right[worst_key].double()),
                        absolute_error=float(difference[worst_key]),allowed_bound=float(allowed[worst_key])),
                    predicate='native-dtype torch.isclose; double error/bound are descriptive',original_assertion=str(error))
                masks[path]=bad.clone()
            records.append(record)
        elif isinstance(right,dict):
            require(isinstance(left,dict) and set(left)==set(right), 'Mapping mismatch: '+path)
            for key in right:walk(left[key],right[key],path+'/'+str(key))
        elif isinstance(right,(list,tuple)):
            require(type(left) is type(right) and len(left)==len(right),'Sequence mismatch: '+path)
            for index,(a,b) in enumerate(zip(left,right)):walk(a,b,path+'/'+str(index))
        elif isinstance(right,float):
            require(type(left) in (float,int) and math.isfinite(left) and math.isfinite(right),'Nonfinite/malformed scalar: '+path)
            tol=tolerance_for(ctx,path)
            # Preserve the original validator's Python-scalar predicate.
            passed=math.isclose(left,right,rel_tol=tol['rtol'],abs_tol=tol['atol'])
            records.append(dict(path=path,actual=left,expected=right,tolerance=tol,passed=passed,
                predicate='original math.isclose',absolute_error=abs(left-right),
                allowed_bound=max(tol['atol'],tol['rtol']*max(abs(left),abs(right)))))
        else:
            require(type(left) is type(right) and left==right,'Structural value/None mismatch: '+path)
    walk(actual,expected,case)
    return records,masks


def setup_case_source(ctx):
    s=ctx.science
    role=ctx.variant
    try:
        ctx.variant='base' if role in ('base_a','base_repeat') else 'off'
        s.setup(ctx)
        ctx.variant='base' if role=='base_a' else 'off'
        s.inputs(ctx)
    finally:
        ctx.variant=role
    require(ctx.agent._executed_ce_trace is None and 'DQN_EXECUTED_CE_TRACE_DIR' not in os.environ,
            'Warmup diagnostic forbids ON observer')
    module_name='baseline_loss_kernel.py' if role in ('base_a','base_repeat') else 'loss_kernel.py'
    require(Path(ctx.loss.__file__) == ctx.layout.scripts/'dqn'/module_name,'Wrong scientific source role')
    require(ctx.parent.digest(ctx.loss.__file__) == ctx.manifest['sources'][module_name]['sha256'], 'Loss source changed')


def run_cases(ctx):
    torch,s,a=ctx.torch,ctx.science,ctx.agent
    import torch._dynamo as dynamo
    from torch._dynamo.utils import counters
    for name,value in (('recompile_limit',64),('cache_size_limit',64),
                       ('accumulated_recompile_limit',1024),('accumulated_cache_size_limit',1024)):
        if hasattr(dynamo.config,name):setattr(dynamo.config,name,value)
    counters.clear()
    calls=dict(optimizer_step=0,scaler_step=0,scaler_update=0)
    def forbid(name):
        def denied(*args,**kwargs):
            calls[name]+=1
            raise RuntimeError('Forbidden update attempted: '+name)
        return denied
    hook=a.optimizer.register_step_pre_hook(forbid('optimizer_step'))
    original_step,original_update=a.grad_scaler.step,a.grad_scaler.update
    a.grad_scaler.step,a.grad_scaler.update=forbid('scaler_step'),forbid('scaler_update')
    kernels={}
    for diagnostics in (False,True):
        kwargs={} if ctx.variant in ('base_a','base_repeat') else dict(trace_rows=False)
        kernel=ctx.loss.TrainingLoss(a.online_net,a.target_net,ctx.cfg,diagnostics=diagnostics,**kwargs)
        kernels[diagnostics]=torch.compile(kernel,dynamic=False,options={'triton.cudagraphs':False})
    tensors=tuple(torch.from_numpy(ctx.batch[index]).to(device='cuda:0',dtype=dtype) for index,dtype in
        zip((0,1,2,3,4,5,6,9),(torch.float32,torch.long,torch.float32,torch.float32,
                             torch.float32,torch.float32,torch.bool,torch.float32)))
    schedule=torch.ones(3,device='cuda:0',dtype=torch.float32)
    rows=[]
    baseline=None
    if ctx.variant!='base_a':
        baseline=json.loads((ctx.layout.output/'base_a/phase-result.json').read_text())
        require(baseline['status']=='OBSERVATIONS_COMPLETE' and baseline['variant']=='base_a'
                and len(baseline['cases'])==4 and baseline['input_manifest_sha256']==ctx.input_description_sha256,
                'Fresh BASE_A reference missing/provenance mismatch')
    initial=full_state(ctx)
    require(s.finite(ctx,initial),'Initial persistent nonfinite state')
    initial_digest=s.digest_tree(ctx,initial)
    initial_observation=s.optimizer_observation(ctx)
    require(all(value==0 for value in initial_observation['exposure']['total'].values()),'Optimizer exposure not fresh')
    expected_rng=rng_hashes(ctx,ctx.rng)
    try:
        for case in ctx.lock['warmup_cases']:
            index,diagnostics,empty=case['index'],case['diagnostics'],case['empty']
            label='case-%02d-diagnostic%d-empty%d'%(index,diagnostics,empty)
            a.optimizer.zero_grad(set_to_none=True)
            require(all(p.grad is None for p in a.online_net.parameters()),'Initial None-gradient boundary failed')
            s.restore_rng(ctx,ctx.rng)
            pre_rng=s.rng_state(ctx)
            require(rng_hashes(ctx,pre_rng)==expected_rng,'Pre-case RNG differs from sealed input')
            pre_state=s.digest_tree(ctx,full_state(ctx))
            require(pre_state==initial_digest,'Persistent state changed before case')
            entered=dict(variant=ctx.variant,case=case,label=label,pre_state_sha256=pre_state,
                         pre_rng_sha256=rng_hashes(ctx,pre_rng),update_calls=dict(calls))
            write_json(ctx.paths['root']/(label+'.entered.json'),entered)
            try:
                states=torch.zeros_like(tensors[0]) if empty else tensors[0]
                next_states=torch.zeros_like(tensors[3]) if empty else tensors[3]
                with torch.autocast('cuda',dtype=torch.float16):
                    outputs=kernels[diagnostics](states,tensors[1],tensors[2],next_states,
                        tensors[4],tensors[5],tensors[6],tensors[7],schedule)
                require(len(outputs)==4,'Warmup requires exact original four-output ABI')
                outputs[0].backward()
                torch.cuda.synchronize(0)
                gradient={name:None if p.grad is None else p.grad.detach().cpu().clone()
                          for name,p in a.online_net.named_parameters()}
                numerical=dict(ce=outputs[1].detach().cpu().clone(),loss=float(outputs[0].detach().cpu()),
                    bc_loss=float(outputs[2].detach().cpu()),diagnostic_output=outputs[3].detach().cpu().clone(),
                    gradient=gradient,diagnostics=diagnostics,empty=empty)
                post_rng=s.rng_state(ctx)
                a.optimizer.zero_grad(set_to_none=True)
                post_state=s.digest_tree(ctx,full_state(ctx))
                payload=dict(variant=ctx.variant,case=case,numerical=numerical,pre_rng=pre_rng,post_rng=post_rng,
                    pre_state_sha256=pre_state,post_state_sha256=post_state,
                    input_manifest_sha256=ctx.input_description_sha256,update_calls=dict(calls))
                actual=s.save_tensors(ctx,ctx.paths['root']/(label+'.actual.pt'),payload)
                # Complete actual output/grad/RNG payload is durable BEFORE
                # finiteness/control/comparison assertions can reject it.
                row=dict(index=index,case=case,label=label,actual=actual,pre_rng_sha256=rng_hashes(ctx,pre_rng),
                    post_rng_sha256=rng_hashes(ctx,post_rng),pre_state_sha256=pre_state,post_state_sha256=post_state,
                    update_calls=dict(calls),comparisons=[],compared_to=None,comparison_pass=True,
                    comparison_scope='baseline_reference_only' if baseline is None else 'fresh_original_tolerance_comparison')
                write_json(ctx.paths['root']/(label+'.payload-retained.json'),row)
                require(s.finite(ctx,numerical),'Nonfinite unscaled warmup payload; no AMP skip explanation')
                require(post_state==initial_digest and all(value==0 for value in calls.values()),'Persistent state/update guard failed')
                require(all(p.grad is None for p in a.online_net.parameters()),'Final None-gradient boundary failed')
                row['rng_changed_components']=[name for name in expected_rng if row['post_rng_sha256'][name]!=expected_rng[name]]
                row['cross_role_post_rng_changed_components']=[]
                if baseline is not None:
                    expected=baseline['cases'][index-1]['actual']
                    expected_path=Path(expected['path'])
                    require(expected_path==ctx.layout.output/'base_a'/(label+'.actual.pt') and
                            ctx.parent.digest(expected_path)==expected['sha256'],'Fresh reference changed')
                    reference=torch.load(expected_path,map_location='cpu',weights_only=True)
                    require(ctx.parent.digest(expected_path)==expected['sha256'],'Reference changed while loading')
                    require(reference['case']==case and reference['input_manifest_sha256']==ctx.input_description_sha256,
                            'Reference case/input mismatch')
                    require(reference['pre_state_sha256']==reference['post_state_sha256']==initial_digest==pre_state==post_state,
                            'Cross-role persistent scientific state mismatch')
                    require(rng_hashes(ctx,reference['pre_rng'])==expected_rng,'Reference pre-RNG mismatch')
                    row['cross_role_post_rng_changed_components']=[name for name,value in rng_hashes(ctx,reference['post_rng']).items()
                                                                 if row['post_rng_sha256'][name]!=value]
                    row['compared_to']=expected
                    comparison_error=None
                    masks={}
                    row['comparison_complete']=False
                    try:
                        compare_payload(ctx,numerical,reference['numerical'],label,records=row['comparisons'],masks=masks)
                        row['comparison_pass']=all(record['passed'] for record in row['comparisons'])
                        row['comparison_complete']=True
                    except BaseException as error:
                        comparison_error=error
                        row.update(comparison_pass=False,comparison_error=repr(error))
                        raise
                    finally:
                        try:
                            if masks:row['all_failed_coordinate_masks']=s.save_tensors(ctx,ctx.paths['root']/(label+'.violations.pt'),masks)
                            write_json(ctx.paths['root']/(label+'.comparison.json'),row)
                        except BaseException as persistence:
                            if comparison_error is None:raise
                            try:print('Comparison-evidence error: '+repr(persistence)+'; original: '+repr(comparison_error),
                                      file=sys.stderr,flush=True)
                            except BaseException:pass
                    del reference
                row['interpretation_requires_review']=bool(not row['comparison_pass'] or row['rng_changed_components']
                    or row['cross_role_post_rng_changed_components'])
                write_json(ctx.paths['root']/(label+'.json'),row)
                rows.append(row)
                del outputs,gradient,numerical,payload
            except BaseException as error:
                try:
                    write_json(ctx.paths['root']/(label+'.failure.json'),dict(status='INVALID_OR_INCOMPLETE',case=case,
                        error=repr(error),traceback=traceback.format_exc(),update_calls=dict(calls)))
                except BaseException as persistence:
                    try:print('Failure-evidence error: '+repr(persistence)+'; original: '+repr(error),file=sys.stderr,flush=True)
                    except BaseException:pass
                raise
        final=s.optimizer_observation(ctx)
        require(final==initial_observation and s.digest_tree(ctx,full_state(ctx))==initial_digest,
                'Warmup-only phase mutated persistent state/optimizer clocks')
        require(sum(counters['graph_break'].values())==0 and counters['stats']['unique_graphs']==2,
                'Unexpected compile graph/fallback/recompile')
        require(getattr(sys,'_is_gil_enabled',lambda:None)() is False,'Effective held GIL policy differs')
        for name,record in ctx.input_files.items():
            require(ctx.parent.digest(ctx.layout.output/'inputs'/name)==record['sha256'],'Frozen input changed')
        s.modules_private(ctx);ctx.base.verify_source_copies(ctx.layout,ctx.manifest['sources'])
        require(ctx.parent.stable_file(ctx.trained,ctx.lock['checkpoint']['sha256'],ctx.lock['checkpoint']['bytes'])==
                ctx.manifest['trained_fixture']['copied'],'Trained fixture changed')
        return dict(status='OBSERVATIONS_COMPLETE',variant=ctx.variant,cases=rows,qualification_pass=False,
            comparison_pass=all(row['comparison_pass'] for row in rows),
            comparison_scope='baseline_reference_only' if baseline is None else 'fresh_original_tolerance_comparison',
            interpretation_requires_review=any(row['interpretation_requires_review'] for row in rows),
            before=initial_observation,after=final,update_calls=dict(calls),input_manifest_sha256=ctx.input_description_sha256,
            source_lock_sha256=ctx.parent.digest(HERE/'source-lock.json'),source_loss_path=str(ctx.loss.__file__),
            source_loss_sha256=ctx.parent.digest(ctx.loss.__file__),
            peak_cuda_allocated=torch.cuda.max_memory_allocated(0),peak_cuda_reserved=torch.cuda.max_memory_reserved(0),
            scope='Four backward-only cases; same-source A/A and defaultOFF sensitivity, no optimizer/ON/full-step qualification')
    finally:
        a.grad_scaler.step,a.grad_scaler.update=original_step,original_update
        hook.remove()
        a.optimizer.zero_grad(set_to_none=True)
        torch.cuda.synchronize(0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--variant',required=True,choices=('base_a','base_repeat','off'))
    args=parser.parse_args(argv)
    ctx=None
    try:
        ctx=bootstrap(args.manifest,args.variant)
        ctx.science=load_science(ctx)
        setup_case_source(ctx)
        result=run_cases(ctx)
        write_json(ctx.paths['root']/'phase-result.json',result)
        return 0
    except BaseException as error:
        if ctx is not None:
            try:write_json(ctx.paths['root']/'phase-failure.json',dict(status='INVALID_OR_INCOMPLETE',
                variant=ctx.variant,error=repr(error),traceback=traceback.format_exc()))
            except BaseException as persistence:
                print('Failure-evidence error: '+repr(persistence),file=sys.stderr,flush=True)
        traceback.print_exc()
        return 1


if __name__=='__main__':
    raise SystemExit(main())


