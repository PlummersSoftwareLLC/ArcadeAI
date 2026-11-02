#!/usr/bin/env python3
"""Owned fixed attempt01 same-GPU original4/conditional5 route diagnostic.

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


ROUTES = ('original4', 'conditional5')
SELECTED_INDEX = 1


def setup(ctx):
    item = ctx.lock['reconstruction_helpers']
    ctx.reconstruction = ctx.parent.checked_module(item['source'], item['sha256'], '_original_live8_reconstruction')
    # Reuse only the reviewed setup, payload and snapshot FUNCTIONS. Never its
    # bootstrap, reconstruct_one, recompute8, or main entry points.
    ctx.reconstruction.setup(ctx)
    ctx.original_loss = importlib.import_module('dqn.loss_kernel')
    require(ctx.parent.digest(ctx.original_loss.__file__) == ctx.lock['original_loss_sha256'],
            'Private original four-output source differs')
    ctx.attempted_forward_routes = []
    ctx.route_results = []


def selected_item(ctx):
    items = ctx.manifest['retained_inputs']['attempts']
    require([item['index'] for item in items] == list(range(1, 9)), 'Original acquisition binding differs')
    require(ctx.lock['reconstruction_policy']['attempt_indices'] == [SELECTED_INDEX]
            and ctx.lock['reconstruction_policy']['forward_routes'] == list(ROUTES),
            'Predeclared index/order differs')
    return items[0]


def load_selected(ctx, item):
    require(item['index'] == SELECTED_INDEX, 'A substitute original index is forbidden')
    row, row_pin = ctx.parent.bounded_json(item['receipt'], read_only=True)
    require(row_pin == item['receipt'], 'Original selected row identity changed')
    source = item['payload']
    require(ctx.parent.stable_file(source['path'], source['sha256'], source['bytes']) == source,
            'Original PRE identity changed before load')
    payload = ctx.torch.load(source['path'], map_location='cpu', weights_only=True)
    require(ctx.parent.stable_file(source['path'], source['sha256'], source['bytes']) == source,
            'Original PRE changed during weights_only load')
    ctx.reconstruction.payload_contract(ctx, payload, row, SELECTED_INDEX)
    require(row['backend'] == 'original_compiled4'
            and payload['pre_context']['kernel_constants']['diagnostics'] is False,
            'The predeclared first attempt must use the ordinary original route')
    return payload, row


def restore_pre(ctx, payload):
    """Independently reload the same captured PRE before EACH fixed route."""
    torch, science, agent = ctx.torch, ctx.science, ctx.agent
    pre = payload['pre_context']
    for name, net in (('online', agent.online_net), ('target', agent.target_net)):
        expected = net.state_dict()
        require(set(payload[name]) == set(expected) and all(isinstance(payload[name][key], torch.Tensor)
                and payload[name][key].device.type == 'cpu' and payload[name][key].dtype == value.dtype
                and payload[name][key].shape == value.shape for key, value in expected.items()),
                'Captured PRE state ABI/dtype differs: ' + name)
        net.load_state_dict(payload[name], strict=True)
        net.train(pre['modes'][name])
    inputs = [payload['inputs'][name].to(device=agent.device) for name in INPUT_NAMES]
    schedule = payload['schedule'].to(device=agent.device)
    before = ctx.reconstruction.snapshot(ctx)
    require(before['online'] == science.digest_tree(ctx, payload['online'])
            and before['target'] == science.digest_tree(ctx, payload['target']),
            'Loaded models do not match exact original PRE fingerprints')
    require(torch.is_grad_enabled() and all(parameter.requires_grad and parameter.grad is None
            for net in (agent.online_net, agent.target_net) for parameter in net.parameters()),
            'Source-default grad flags or no-backward state differs')
    return inputs, schedule, before


def make_kernel(ctx, payload, route):
    require(route in ROUTES, 'Unknown fixed route')
    pre = payload['pre_context']
    cfg = SimpleNamespace(**pre['config'])
    if route == 'original4':
        # This constructor has no trace_rows argument and the source is byte
        # exact production de962..., not an OFF call to the five-output class.
        module = ctx.original_loss.TrainingLoss(ctx.agent.online_net, ctx.agent.target_net, cfg, diagnostics=False)
    else:
        module = ctx.offline.TrainingLoss(ctx.agent.online_net, ctx.agent.target_net, cfg,
                                          diagnostics=False, trace_rows=True)
    require({name: getattr(module, name) for name in CONSTANT_NAMES} == pre['kernel_constants'],
            'Original captured loss constants differ in route: ' + route)
    return ctx.conditional.compile_loss(ctx, module)


def forward_and_retain(ctx, kernel, inputs, schedule, payload, item, route, pre_rng, directory):
    """Exactly one forward per route; all raw values precede interpretation."""
    require(len(ctx.attempted_forward_routes) < len(ROUTES)
            and route == ROUTES[len(ctx.attempted_forward_routes)], 'Duplicate/out-of-order forward; no retry')
    ctx.attempted_forward_routes.append(route)  # Register before possible call.
    torch, science, agent = ctx.torch, ctx.science, ctx.agent
    with ctx.conditional.forbidden_offline_updates(ctx) as calls:
        with torch.autocast(device_type='cuda', dtype=torch.float16):
            outputs = kernel(*inputs, schedule)
    torch.cuda.synchronize(agent.device)
    post_rng = science.rng_state(ctx)
    raw_pin = ctx.conditional.save_payload(ctx, directory/'raw-outputs.pt', dict(
        route=route, selected_original_index=SELECTED_INDEX,
        scope='Fresh same-GPU route observation; conditional target is never actual executed target',
        raw_outputs=outputs, expected_actual_capture=payload['actual'],
        rng_before=pre_rng, rng_after=post_rng,
        source_capture_payload=item['payload'], source_capture_receipt=item['receipt']))
    arity = 4 if route == 'original4' else 5
    require(isinstance(outputs, tuple) and len(outputs) == arity, 'Route output ABI differs: ' + route)
    if route == 'conditional5':
        require(isinstance(outputs[4], tuple) and len(outputs[4]) == len(TRACE_NAMES),
                'Conditional auxiliary ABI differs')
    actual = dict(weighted_loss=outputs[0], ce=outputs[1], bc_loss=outputs[2], diagnostic_values=outputs[3])
    if route == 'conditional5':
        actual['conditional'] = {name: value for name, value in zip(TRACE_NAMES, outputs[4])}
    require(science.finite(ctx, actual), 'Nonfinite route output; raw values retained: ' + route)
    # Detach independently to CPU before the other route runs. This does not
    # retain the first forward's autograd graph or device output references.
    return science.cpu(ctx, actual), raw_pin, post_rng, dict(calls)


def run_route(ctx, payload, row, item, route):
    directory = ctx.paths['root']/route
    directory.mkdir(mode=0o700)
    write_json(directory/'entered.json', dict(selected_original_index=SELECTED_INDEX,
        route=route, fixed_route_order=list(ROUTES), source_payload=item['payload'], source_receipt=item['receipt']))
    inputs, schedule, before = restore_pre(ctx, payload)
    kernel = make_kernel(ctx, payload, route)
    # Lazy compilation is inside the sole forward, never an extra warmup.
    ctx.science.restore_rng(ctx, payload['rng'])
    pre_rng = ctx.science.rng_state(ctx)
    require(ctx.science.digest_tree(ctx, pre_rng) == ctx.science.digest_tree(ctx, payload['rng']),
            'PRE RNG did not independently restore exactly: ' + route)
    actual, raw_pin, post_rng, calls = forward_and_retain(
        ctx, kernel, inputs, schedule, payload, item, route, pre_rng, directory)
    after = ctx.reconstruction.snapshot(ctx)
    grads_none = all(parameter.grad is None for net in (ctx.agent.online_net, ctx.agent.target_net)
                     for parameter in net.parameters())
    require(before == after and calls == dict(optimizer_step=0, scaler_step=0, scaler_update=0) and grads_none,
            'Forward changed model/owned inert optimizer/scaler or gradients: ' + route)
    require(getattr(sys, '_is_gil_enabled', lambda: None)() is False, 'Effective GIL changed after route forward')
    source = item['payload']
    require(ctx.parent.stable_file(source['path'], source['sha256'], source['bytes']) == source,
            'Original PRE changed after route forward')
    rng_changed = ctx.science.digest_tree(ctx, pre_rng) != ctx.science.digest_tree(ctx, post_rng)
    result = dict(index=SELECTED_INDEX, route=route, status='OBSERVATIONS_COMPLETE', diagnostics=False,
        output_arity=4 if route == 'original4' else 5, raw_payload=raw_pin,
        source_receipt=item['receipt'], source_payload=source, model_before=before, model_after=after,
        all_grads_none=grads_none, update_guard_counts=calls, actual_optimizer_outcome=row['optimizer_outcome'],
        pre_context=payload['pre_context'],
        rng_observations=dict(pre=ctx.science.digest_tree(ctx, pre_rng),
            post=ctx.science.digest_tree(ctx, post_rng), post_changed=rng_changed,
            scope='Restored recorded PRE components; not a coherent all-thread live RNG anchor'),
        logical_device_mapping=dict(captured=payload['pre_context']['learner_device'],
            offline=str(ctx.agent.device), offline_uuid=ctx.base.GPU0_UUID),
        grad_flags_scope='Source-default requires_grad=True; flags were not recorded independently in the live payload')
    write_json(directory/'route-result.json', result)
    ctx.route_results.append(result)
    return actual


def route_diagnostic(ctx):
    item = selected_item(ctx)
    payload, row = load_selected(ctx, item)
    # Order is fixed in advance. Finite numeric mismatches cannot select a
    # different batch/route or trigger an additional forward.
    original4 = run_route(ctx, payload, row, item, 'original4')
    conditional5 = run_route(ctx, payload, row, item, 'conditional5')
    require(ctx.attempted_forward_routes == list(ROUTES), 'Exactly two fixed forwards required')
    comparisons = {}
    for name, actual, expected in (
            ('original4_vs_captured_actual', original4['ce'], payload['actual']['ce']),
            ('conditional5_vs_local_original4', conditional5['ce'], original4['ce'])):
        values, mask = ctx.conditional.compare_ce(ctx, actual, expected)
        values['mismatch_mask'] = ctx.conditional.save_payload(
            ctx, ctx.paths['root']/(name+'-mismatch-mask.pt'), dict(ce=mask))
        comparisons[name] = values
    require(ctx.parent.bind_inputs(ctx.lock) == ctx.manifest['retained_inputs'], 'Final original input provenance changed')
    passed = all(value['passed'] for value in comparisons.values())
    return dict(status='OBSERVATIONS_COMPLETE', variant=ctx.variant, selected_original_index=SELECTED_INDEX,
        forward_routes=list(ROUTES), attempted_forward_routes=ctx.attempted_forward_routes,
        routes=ctx.route_results, comparisons=comparisons, comparison_pass=passed,
        qualification_pass=False, interpretation_requires_review=not passed or any(
            value['rng_observations']['post_changed'] for value in ctx.route_results),
        comparison_scope='CE-only original4 vs captured actual, separately conditional5 vs same-GPU original4; original rtol2e-4/atol2e-5',
        grad_enabled=True, explicit_worker_backward_calls=0, actual_attempts_in_this_process=0,
        executed_target_observed=False, source_lock_sha256=ctx.parent.SOURCE_LOCK_SHA256,
        backward_evidence_scope='No explicit worker backward plus all gradsNone; not an AOT/autograd-engine counter',
        peak_cuda_allocated=ctx.torch.cuda.max_memory_allocated(0),
        peak_cuda_reserved=ctx.torch.cuda.max_memory_reserved(0),
        inherited_sampler_unknown_scope='Original draw.unknown strings concern standalone sampler metadata; original outcomes/full PRE remain available through receipts and payload',
        limitations=['Two fixed same-GPU forwards do not exclude nondeterminism or uniquely prove an ABI/lowering cause',
            'The first comparison includes the original capture/device/profile residual; the second is a local route contrast',
            'Any index1 result does not rescue or requalify the prior all8 comparison failure',
            'Conditional5 projected target/entropy/KL are not actual executed target observations',
            'Only CE is compared; weighted loss, BC, diagnostics and conditional auxiliaries are retained',
            'Owned inert optimizer/scaler are forbidden-call sentinels, not reconstructed live Adam/scaler',
            'No extra warmup, calibration forward, backward, sampler draw, live source adoption or learning claim'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--variant', required=True, choices=('route1',))
    args = parser.parse_args(argv)
    ctx = None
    try:
        ctx = bootstrap(args.manifest, args.variant)
        setup(ctx)
        result = route_diagnostic(ctx)
        ctx.science.modules_private(ctx)
        ctx.base.verify_source_copies(ctx.layout, ctx.manifest['sources'])
        require(ctx.parent.read_lock() == ctx.lock, 'Final source lock changed')
        ctx.base.guard_live_resources(allowed_pids={os.getpid(), os.getppid()}, expected_main=ctx.manifest['main_owners'])
        write_json(ctx.paths['root']/'phase-result.json', result)
        return 0
    except BaseException as error:
        if ctx is not None:
            try:
                write_json(ctx.paths['root']/'phase-failure.json', dict(status='INVALID_OR_INCOMPLETE',
                    variant=ctx.variant, error=repr(error), traceback=traceback.format_exc(),
                    completed_routes=[value['route'] for value in getattr(ctx, 'route_results', [])],
                    attempted_forward_routes=getattr(ctx, 'attempted_forward_routes', []),
                    offline_update_guard_counts=getattr(ctx, 'offline_update_guard_counts', None)))
            except BaseException as persistence:
                try:
                    print('Failure-evidence error: '+repr(persistence), file=sys.stderr, flush=True)
                except BaseException:
                    pass
        try:
            traceback.print_exc()
        except BaseException:
            pass
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

