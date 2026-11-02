#!/usr/bin/env python3
"""Owned fixed attempt01 raw-KL Stage A three-route numeric validation.

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


ROUTES = ('original4', 'candidate_ce4', 'candidate_kl5')
SELECTED_INDEX = 1
INPUT_NAMES = ('states', 'actions', 'rewards', 'next_states', 'dones', 'horizons', 'is_expert', 'weights')
CONSTANT_NAMES = ('num_fire', 'num_atoms', 'v_min', 'v_max', 'delta_z', 'gamma', 'smooth_eps',
                  'branch_aux', 'bc_floor', 'q_temperature', 'q_margin', 'diagnostics')


def setup(ctx):
    item = ctx.lock['route_helpers']
    ctx.route_helper = ctx.parent.checked_module(item['source'], item['sha256'], '_sealed_same_gpu_route')
    # Functions only: never the predecessor's bootstrap, forward loop or main.
    ctx.route_helper.setup(ctx)
    ctx.candidate = importlib.import_module('dqn.candidate_loss_kernel')
    require(ctx.parent.digest(ctx.candidate.__file__) == ctx.lock['candidate_science_files']['loss_kernel.py']['sha256'],
            'Private candidate loss changed')
    ctx.attempted_forward_routes = []
    ctx.backward_routes = []
    ctx.route_results = []


def selected_item(ctx):
    items = ctx.manifest['retained_inputs']['attempts']
    require([item['index'] for item in items] == list(range(1, 9))
            and ctx.lock['reconstruction_policy']['attempt_indices'] == [SELECTED_INDEX]
            and ctx.lock['stage_a']['routes'] == list(ROUTES), 'Fixed genuine attempt01 binding differs')
    return items[0]


def make_kernel(ctx, payload, route):
    require(route in ROUTES, 'Unknown fixed route')
    pre = payload['pre_context']; cfg = SimpleNamespace(**pre['config'])
    if route == 'original4':
        module = ctx.original_loss.TrainingLoss(ctx.agent.online_net, ctx.agent.target_net, cfg, diagnostics=False)
    elif route == 'candidate_ce4':
        # Intentionally omit the new flag, testing the candidate DEFAULT CE4.
        module = ctx.candidate.TrainingLoss(ctx.agent.online_net, ctx.agent.target_net, cfg, diagnostics=False)
    else:
        module = ctx.candidate.TrainingLoss(ctx.agent.online_net, ctx.agent.target_net, cfg,
                                            diagnostics=False, return_priorities=True)
    require({name: getattr(module, name) for name in CONSTANT_NAMES} == pre['kernel_constants'],
            'Captured constants differ: '+route)
    return ctx.conditional.compile_loss(ctx, module)


def priority_statistics_contract(stats, minimum, maximum):
    require(len(stats) == 7 and all(type(value) is float and math.isfinite(value) for value in stats),
            'Nonfinite or malformed KL stats')
    signed_min, signed_max, negative, near_zero, target_min, mass_max, mass_mean = stats
    require(signed_min <= signed_max and signed_min >= -1e-5 and target_min >= 0
            and 0 <= mass_mean <= mass_max <= 1e-5
            and negative.is_integer() and near_zero.is_integer()
            and 0 <= negative <= 4096 and 0 <= near_zero <= 4096,
            'Precommitted signed/mass/count KL validity guard failed')
    require(math.isfinite(minimum) and math.isfinite(maximum)
            and minimum == max(0.0, signed_min) and maximum == max(0.0, signed_max),
            'Returned vector extrema disagree with clamp of raw signed extrema')


def priority_guard(ctx, outputs):
    """Check the exact returned detached vector and seven raw same-forward stats.

    KL5 does not expose all projected rows/entropy. This is not an independent
    full entropy recomputation and does not identify the historical live target.
    """
    torch = ctx.torch; priority = outputs[4]; diagnostics = outputs[3]
    require(isinstance(priority, torch.Tensor) and priority.shape == (4096,)
            and priority.dtype == torch.float32 and priority.device == ctx.agent.device
            and priority.requires_grad is False and priority.grad_fn is None,
            'KL priority vector is not exact detached FP32/owned-device ABI')
    require(isinstance(diagnostics, torch.Tensor) and diagnostics.shape == (19,)
            and diagnostics.dtype == torch.float32, 'KL stats must append seven to existing twelve')
    stats = [float(value) for value in diagnostics[12:].detach().cpu().tolist()]
    signed_min, signed_max, negative, near_zero, target_min, mass_max, mass_mean = stats
    require(bool(torch.isfinite(priority).all()) and bool((priority >= 0).all()),
            'Nonfinite or negative returned KL priority')
    minimum, maximum = float(priority.min()), float(priority.max())
    priority_statistics_contract(stats, minimum, maximum)
    return dict(passed=True, detached=True, priority_shape=[4096], priority_dtype=str(priority.dtype),
        priority_min=minimum, priority_max=maximum,
        signed_min=signed_min, signed_max=signed_max, negative_count=int(negative),
        abs_le_1e_6_count=int(near_zero), target_min=target_min,
        target_mass_error_max=mass_max, target_mass_error_mean=mass_mean,
        minimum_signed_kl=-1e-5, maximum_target_mass_error=1e-5,
        entropy_log_floor=1e-12, priority_clamp_min=0,
        scope='Returned detached same-forward vector/stats and source contract; full entropy rows are not exposed')


def gradients(ctx):
    return {name: {key: parameter.grad for key, parameter in net.named_parameters()}
            for name, net in (('online', ctx.agent.online_net), ('target', ctx.agent.target_net))}


def one_forward_backward(ctx, kernel, inputs, schedule, payload, item, route, pre_rng, directory):
    """Exactly one AMP forward and one unscaled, unclipped objective backward.

    Each counter is registered before the possible call. Raw forward and then
    native preclip gradients are durable BEFORE finite/gradient interpretation.
    No scaler adjustment, step, clip, optimization or validation warmup occurs.
    """
    require(len(ctx.attempted_forward_routes) < 3
            and route == ROUTES[len(ctx.attempted_forward_routes)], 'Duplicate/out-of-order forward; no retry')
    ctx.attempted_forward_routes.append(route)
    torch, science, agent = ctx.torch, ctx.science, ctx.agent
    with ctx.conditional.forbidden_offline_updates(ctx) as calls:
        with torch.autocast(device_type='cuda', dtype=torch.float16):
            outputs = kernel(*inputs, schedule)
        torch.cuda.synchronize(agent.device)
        post_forward_rng = science.rng_state(ctx)
        forward_pin = ctx.conditional.save_payload(ctx, directory/'raw-forward.pt', dict(
            route=route, selected_original_index=1, raw_outputs=outputs,
            expected_actual_capture=payload['actual'], rng_before=pre_rng, rng_after=post_forward_rng,
            source_capture_payload=item['payload'], source_capture_receipt=item['receipt']))
        arity = 5 if route == 'candidate_kl5' else 4
        require(isinstance(outputs, tuple) and len(outputs) == arity, 'Output ABI differs: '+route)
        actual = dict(weighted_loss=outputs[0], ce=outputs[1], bc_loss=outputs[2], diagnostic_values=outputs[3])
        require(outputs[1].shape == (4096,) and outputs[3].shape == ((19,) if arity == 5 else (12,)),
                'CE/diagnostics geometry differs: '+route)
        require(science.finite(ctx, outputs), 'Nonfinite output; raw retained: '+route)
        guard = priority_guard(ctx, outputs) if arity == 5 else None
        require(route == ROUTES[len(ctx.backward_routes)], 'Duplicate/out-of-order backward; no retry')
        ctx.backward_routes.append(route)
        # Deliberately unscaled objective differentiation, with autocast OFF as
        # in production backward; no trained-scaler admission claim is made.
        try:
            outputs[0].backward()
        except BaseException as primary:
            # Keep any partial native gradients without replacing the original
            # backward failure if synchronization/publication also fails.
            try:
                ctx.conditional.save_payload(ctx, directory/'backward-failure.pt', dict(
                    route=route, primary_error=repr(primary), gradients=gradients(ctx),
                    explicit_unscaled_objective_backward_calls=1, clipped=False, scaled=False))
            except BaseException as secondary:
                try:print('Secondary backward evidence error: '+repr(secondary),file=sys.stderr,flush=True)
                except BaseException:pass
            raise
        torch.cuda.synchronize(agent.device)
        post_backward_rng = science.rng_state(ctx)
        native = gradients(ctx)
        gradient_pin = ctx.conditional.save_payload(ctx, directory/'raw-preclip-gradients.pt', dict(
            route=route, gradients=native, explicit_unscaled_objective_backward_calls=1,
            clipped=False, scaled=False, rng_before=pre_rng,
            rng_after_forward=post_forward_rng, rng_after_backward=post_backward_rng,
            scope='Unscaled objective gradients before clipping; not saved-scale admission or optimizer outcome'))
        require(science.finite(ctx, native), 'Nonfinite unscaled gradients; raw retained: '+route)
        target_none = all(value is None for value in native['target'].values())
        require(target_none, 'No-grad target acquired gradients')
        require(any(value is not None for value in native['online'].values()), 'No online gradient observed')
        cpu = science.cpu(ctx, dict(actual=actual, gradients=native))
    return cpu, dict(forward=forward_pin, gradients=gradient_pin), post_backward_rng, dict(calls), guard


def run_route(ctx, payload, row, item, route):
    directory = ctx.paths['root']/route; directory.mkdir(mode=0o700)
    write_json(directory/'entered.json', dict(route=route, selected_original_index=1,
        fixed_route_order=list(ROUTES), source_payload=item['payload'], source_receipt=item['receipt']))
    for net in (ctx.agent.online_net, ctx.agent.target_net):
        net.zero_grad(set_to_none=True)
    inputs, schedule, before = ctx.route_helper.restore_pre(ctx, payload)
    kernel = make_kernel(ctx, payload, route)
    ctx.science.restore_rng(ctx, payload['rng']); pre_rng = ctx.science.rng_state(ctx)
    require(ctx.science.digest_tree(ctx, pre_rng) == ctx.science.digest_tree(ctx, payload['rng']),
            'PRE RNG did not restore exactly: '+route)
    values, raw, post_rng, calls, guard = one_forward_backward(
        ctx, kernel, inputs, schedule, payload, item, route, pre_rng, directory)
    after = ctx.reconstruction.snapshot(ctx)
    require(before == after and calls == dict(optimizer_step=0, scaler_step=0, scaler_update=0),
            'Model/owned inert optimizer/scaler changed: '+route)
    require(getattr(sys, '_is_gil_enabled', lambda: None)() is False, 'Effective GIL changed')
    source = item['payload']
    require(ctx.parent.stable_file(source['path'], source['sha256'], source['bytes']) == source,
            'Original PRE changed during route')
    result = dict(index=1, route=route, status='OBSERVATIONS_COMPLETE', diagnostics=False,
        output_arity=5 if route=='candidate_kl5' else 4, raw_payloads=raw,
        model_before=before, model_after=after, source_receipt=item['receipt'], source_payload=source,
        update_guard_counts=calls, explicit_unscaled_backward_calls=1, gradients_retained=True,
        target_all_grads_none=all(value is None for value in values['gradients']['target'].values()),
        priority_guard=guard, actual_historical_optimizer_outcome=row['optimizer_outcome'],
        pre_context=payload['pre_context'],
        rng_observations=dict(pre=ctx.science.digest_tree(ctx, pre_rng), post=ctx.science.digest_tree(ctx, post_rng),
            post_changed=ctx.science.digest_tree(ctx, pre_rng)!=ctx.science.digest_tree(ctx, post_rng),
            scope='Recorded components independently restored, not a coherent live all-thread RNG anchor'),
        grad_flags_scope='Pinned source-default requires_grad=True; not independently serialized by live capture',
        gradient_scope='Unscaled weighted-objective gradients before clip; Stage B saved-scaler/admission is separate')
    write_json(directory/'route-result.json', result); ctx.route_results.append(result)
    return values


def compare_tensor(ctx, actual, expected, tolerance):
    torch=ctx.torch
    require(isinstance(actual, torch.Tensor) and isinstance(expected, torch.Tensor)
            and actual.shape==expected.shape and actual.dtype==expected.dtype, 'Compared tensor ABI differs')
    require(ctx.science.finite(ctx, actual) and ctx.science.finite(ctx, expected), 'Compared tensor is nonfinite')
    actual,expected=actual.detach().cpu(),expected.detach().cpu()
    mask=~torch.isclose(actual,expected,**tolerance,equal_nan=False)
    difference=(actual.double()-expected.double()).abs()
    return dict(passed=not bool(mask.any()),tolerance=dict(tolerance),violations=int(mask.sum()),
        elements=mask.numel(),max_abs=float(difference.max()) if mask.numel() else 0.0,
        actual_sha256=ctx.science.digest_tree(ctx,actual),expected_sha256=ctx.science.digest_tree(ctx,expected),
        predicate='native-dtype torch.isclose',first_coordinates=torch.nonzero(mask,as_tuple=False)[:16].tolist()),mask


def compare_gradients(ctx, actual, expected, directory):
    tolerance=ctx.lock['tolerances']['gradient']; records={};masks={};passed=True
    require(set(actual)==set(expected)=={'online','target'}, 'Gradient network keyset differs')
    for name in ('online','target'):
        require(set(actual[name])==set(expected[name]), 'Gradient parameter keyset differs')
        for key in actual[name]:
            left,right=actual[name][key],expected[name][key];label=name+'.'+key
            if left is None or right is None:
                record=dict(passed=left is None and right is None,actual_none=left is None,expected_none=right is None)
            else:
                record,masks[label]=compare_tensor(ctx,left,right,tolerance)
            records[label]=record;passed=passed and record['passed']
    pin=ctx.conditional.save_payload(ctx,directory/'gradient-mismatch-masks.pt',masks)
    return dict(passed=passed,tolerance=tolerance,parameters=records,mismatch_masks=pin,
        scope='Exact None patterns and original native unscaled preclip gradient tolerance')


def compare_routes(ctx, name, left, right):
    directory=ctx.paths['root']/name;directory.mkdir(mode=0o700);fields={};masks={}
    for field in ('ce','weighted_loss','bc_loss','diagnostic_values'):
        # Compare only the original twelve diagnostics, retaining KL stats separately.
        a,b=left['actual'][field],right['actual'][field]
        if field=='diagnostic_values':a,b=a[:12],b[:12]
        tolerance=ctx.lock['tolerances']['ce' if field=='ce' else 'scalars']
        fields[field],masks[field]=compare_tensor(ctx,a,b,tolerance)
    fields['gradients']=compare_gradients(ctx,left['gradients'],right['gradients'],directory)
    pin=ctx.conditional.save_payload(ctx,directory/'output-mismatch-masks.pt',masks)
    return dict(passed=all(value['passed'] for value in fields.values()),fields=fields,mismatch_masks=pin)


def validate_stage_a(ctx):
    item=selected_item(ctx);payload,row=ctx.route_helper.load_selected(ctx,item)
    values={route:run_route(ctx,payload,row,item,route) for route in ROUTES}
    require(ctx.attempted_forward_routes==ctx.backward_routes==list(ROUTES), 'Exactly three fixed calls required')
    residual,mask=ctx.conditional.compare_ce(ctx,values['original4']['actual']['ce'],payload['actual']['ce'])
    residual['mismatch_mask']=ctx.conditional.save_payload(ctx,ctx.paths['root']/'captured-ce-residual-mask.pt',dict(ce=mask))
    comparisons=dict(original4_vs_captured_actual=residual,
        candidate_ce4_vs_original4=compare_routes(ctx,'candidate_ce4_vs_original4',values['candidate_ce4'],values['original4']),
        candidate_kl5_vs_candidate_ce4=compare_routes(ctx,'candidate_kl5_vs_candidate_ce4',values['candidate_kl5'],values['candidate_ce4']))
    passed=all(comparisons[name]['passed'] for name in ('candidate_ce4_vs_original4','candidate_kl5_vs_candidate_ce4'))
    require(ctx.parent.bind_inputs(ctx.lock)==ctx.manifest['retained_inputs'], 'Final genuine input binding changed')
    return dict(status='OBSERVATIONS_COMPLETE',variant=ctx.variant,selected_original_index=1,
        forward_routes=list(ROUTES),attempted_forward_routes=ctx.attempted_forward_routes,
        backward_routes=ctx.backward_routes,explicit_worker_backward_calls=3,actual_attempts_in_this_process=0,
        routes=ctx.route_results,comparisons=comparisons,comparison_pass=passed,qualification_pass=False,
        stage_b_required_before_adoption=True,
        interpretation_requires_review=not passed or not residual['passed'] or any(
            value['rng_observations']['post_changed'] for value in ctx.route_results),
        comparison_scope='Stage A internal CE/objective/unscaled-preclip-gradient comparisons; historical captured CE residual separate/descriptive',
        source_lock_sha256=ctx.parent.SOURCE_LOCK_SHA256,grad_enabled=True,
        peak_cuda_allocated=ctx.torch.cuda.max_memory_allocated(0),peak_cuda_reserved=ctx.torch.cuda.max_memory_reserved(0),
        limitations=['Exactly one genuine original index; no replay-population, learning benefit or historical all8 rescue',
            'Three fixed forwards/backwards can fail the unchanged180s/12GiB allocation cap; no smaller-batch/retry rescue',
            'No trained-scaler admission, full agent constructor, native replay update, fusedAdam/readback or phase-load proof',
            'Stage B remains mandatory before any live proposal adoption; this source proposal is not adoption authorization',
            'KL returned vector/stats/source checked; target/entropy rows not exposed by sealed KL5 for independent full reconstruction',
            'Original sampler unknown strings do not erase joined historical outcomes or captured full PRE state',
            'No extra warmup, clipping, optimizer/scaler calls, data draw, raw target renormalization or tolerance change'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--variant',required=True,choices=('stage_a',));args=parser.parse_args(argv);ctx=None
    try:
        ctx=bootstrap(args.manifest,args.variant);setup(ctx);result=validate_stage_a(ctx)
        ctx.science.modules_private(ctx);ctx.base.verify_source_copies(ctx.layout,ctx.manifest['sources'])
        require(ctx.parent.read_lock()==ctx.lock,'Final source lock changed')
        ctx.base.guard_live_resources(allowed_pids={os.getpid(),os.getppid()},expected_main=ctx.manifest['main_owners'])
        write_json(ctx.paths['root']/'phase-result.json',result);return 0
    except BaseException as error:
        if ctx is not None:
            try:
                write_json(ctx.paths['root']/'phase-failure.json',dict(status='INVALID_OR_INCOMPLETE',
                    variant=ctx.variant,error=repr(error),traceback=traceback.format_exc(),
                    attempted_forward_routes=getattr(ctx,'attempted_forward_routes',[]),
                    backward_routes=getattr(ctx,'backward_routes',[]),
                    completed_routes=[value['route'] for value in getattr(ctx,'route_results',[])],
                    update_guard_counts=getattr(ctx,'offline_update_guard_counts',None)))
            except BaseException as persistence:
                try:print('Failure-evidence error: '+repr(persistence),file=sys.stderr,flush=True)
                except BaseException:pass
        try:traceback.print_exc()
        except BaseException:pass
        return 1


if __name__=='__main__':
    raise SystemExit(main())
