#!/usr/bin/env python3
"""Internal owned one-attempt capture / conditional offline forward worker.

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
    item = ctx.lock['frozen_science_helpers']
    module = ctx.parent.checked_module(item['source'], item['sha256'], '_frozen_capture_fixture_science')
    # Reuse only setup, bounded synthetic storage, CPU fingerprint and RNG
    # helpers. Never call old bootstrap, warmups, inputs(), or observe_steps().
    module.HERE = HERE
    return module


def setup(ctx):
    role = ctx.variant
    try:
        ctx.variant = 'off'  # Select private training.py and original loss_kernel.py.
        ctx.science.setup(ctx)
    finally:
        ctx.variant = role
    require(ctx.agent._executed_ce_trace is None and 'DQN_EXECUTED_CE_TRACE_DIR' not in os.environ,
            'Old executed-target observer is forbidden')
    require(ctx.parent.digest(ctx.loss.__file__) == ctx.lock['original_loss_sha256'] and
            Path(ctx.loss.__file__) == ctx.layout.scripts/'dqn/loss_kernel.py',
            'Actual training must retain byte-exact four-output loss source')
    require(getattr(sys, '_is_gil_enabled', lambda: None)() is False,
            'Current free-threaded learner profile requires effective GIL disabled')
    ctx.agent._recomputed_ce_capture = None
    ctx.requires_grad = {role:{name:bool(parameter.requires_grad) for name,parameter in net.named_parameters()}
                        for role,net in (('online',ctx.agent.online_net),('target',ctx.agent.target_net))}
    require(all(flags and all(flags.values()) for flags in ctx.requires_grad.values()),
            'Default model gradient flags differ')


def json_input(ctx, path):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and path.is_relative_to(ctx.layout.output)
            and not path.is_symlink(), 'JSON input escaped this owned output')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
            and not stat.S_IMODE(info.st_mode) & 0o222 and info.st_size <= 1024**2,
            'JSON input is not bounded owned readonly evidence')
    record = ctx.parent.stable_file(path, ctx.parent.digest(path), info.st_size)
    value = json.loads(path.read_text())
    require(ctx.parent.stable_file(path, record['sha256'], record['bytes']) == record,
            'JSON input changed during read')
    return value, record


def save_payload(ctx, path, value):
    record = ctx.science.save_tensors(ctx, path, value)
    ctx.parent.sync_directory(Path(path).parent)
    return ctx.parent.stable_file(path, record['sha256'], record['bytes'])


def compile_loss(ctx, module):
    """Use the production agent factory flags, without executing its warmups."""
    import torch._dynamo as dynamo
    for name, value in (('recompile_limit',64), ('cache_size_limit',64),
                        ('accumulated_recompile_limit',1024), ('accumulated_cache_size_limit',1024)):
        if hasattr(dynamo.config,name):
            setattr(dynamo.config,name,value)
    options = {'triton.cudagraphs':False}
    if str(ctx.cfg.torch_compile_mode).startswith('max-autotune'):
        options['max_autotune'] = True
    require(ctx.cfg.torch_compile_mode == 'default' and options == {'triton.cudagraphs':False},
            'Held default compilation profile changed')
    return ctx.torch.compile(module,dynamic=False,options=options)


def optimizer_outcome(ctx, before, after, row):
    old, new = before['exposure'], after['exposure']
    require(all(old[key] == new[key] for key in ('process_id', 'instance_monotonic_ns', 'epoch')),
            'Optimizer exposure identity/epoch changed')
    delta = {key: new['total'][key]-old['total'][key] for key in
             ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable')}
    require(new['available'] and delta['attempts_started'] == delta['outcomes_recorded'] == 1
            and delta['applied']+delta['amp_skipped'] == 1 and delta['unavailable'] == 0
            and delta == row['actual_exposure_delta'] and row['outcome_available'],
            'Actual one-attempt outcome is unavailable or ambiguous')
    require(before['persistent_finite'] and after['persistent_finite']
            and set(before['steps']) == set(after['steps']), 'Persistent Adam state malformed/nonfinite')
    if delta['amp_skipped']:
        require(before['steps'] == after['steps'] and before['online'] == after['online']
                and before['moments'] == after['moments']
                and 0 < after['scaler']['scale'] < before['scaler']['scale'],
                'Skip lacks unchanged Adam/model and reduced saved scale')
        outcome = 'amp_skipped'
    else:
        differences = {name: after['steps'][name]-value for name, value in before['steps'].items()}
        require(all(value in (0, 1) for value in differences.values()) and any(differences.values())
                and before['online'] != after['online'], 'Applied admission lacks one actual Adam/model update')
        outcome = 'applied_admission'
    require(row['optimizer_outcome'] == outcome, 'Observer and independent outcome differ')
    require(after['clocks']['training_steps'] == before['clocks']['training_steps']+1
            and after['clocks']['optimized_samples'] == before['clocks']['optimized_samples']+4096,
            'Original logical attempted clock must advance once, including a valid AMP skip')
    return outcome, delta


def capture(ctx):
    torch, s, a = ctx.torch, ctx.science, ctx.agent
    module = importlib.import_module('dqn.recomputed_ce_capture')
    directory = Path(os.environ['DQN_RECOMPUTED_CE_CAPTURE_DIR'])
    require(directory == ctx.paths['root']/'ce-recomputed-capture-private-one', 'Capture path differs')
    observer = module.RecomputedCECapture(directory, ctx.cfg,
        optimizer_exposure=a._learning_optimizer_exposure,
        runtime=dict(ctx.runtime, private_rehearsal=True, source_lock_sha256=ctx.parent.SOURCE_LOCK_SHA256,
                     model_requires_grad=ctx.requires_grad,
                     rng_scope='Sequential process/global RNG observations, not an all-thread atomic anchor'))
    a._recomputed_ce_capture = observer
    a.memory = s.make_private_replay(ctx)
    require(not ctx.training.replay_pressure_reached(a), 'First actual attempt refused by unchanged cap8 guard')
    # No eager/compiled warmup forward or previous optimizer call. Compilation
    # of the original class remains lazy until this one actual training call.
    for diagnostic, name in ((False, 'compiled_training_loss'), (True, 'compiled_training_loss_diagnostics')):
        kernel = ctx.loss.TrainingLoss(a.online_net, a.target_net, ctx.cfg, diagnostics=diagnostic)
        setattr(a, name, compile_loss(ctx,kernel))
    require(a.grad_scaler.get_scale() == ctx.lock['checkpoint']['grad_scaler_scale']
            and a.grad_scaler.state_dict()['_growth_tracker'] == ctx.lock['checkpoint']['grad_scaler_growth_tracker'],
            'Original saved scaler changed before first attempt')
    before = s.optimizer_observation(ctx)
    native_before = ctx.native.batch_update_status()
    write_json(ctx.paths['root']/'attempt-entered.json', dict(before=before, requires_grad=ctx.requires_grad,
        original_loss_sha256=ctx.parent.digest(ctx.loss.__file__), actual_attempt_limit=1,
        first8_class_limit=module.ATTEMPTS, artificial_frame_credits=0, warmup_forwards=0))
    producer = lease = None
    closed = False
    result = None
    enabled = [True]
    primary = None
    try:
        producer = ctx.prefetch.ReplayPrefetcher(a.memory, 4096,
            lambda: ctx.training._beta_schedule(ctx.metrics.frame_count), a.device, use_amp=True,
            depth=3, enabled_fn=lambda: enabled[0], min_replay_size=4096,
            direct_state_fill=True, trace_observer=observer)
        lease = producer.get(timeout=10.)
        require(lease is not None and lease.is_current and lease.draw_metadata is not None,
                'No real current captured CUDA lease')
        # At most three producer slots exist. Stop initiating later draws after
        # leasing; an already-running producer draw is not a second consumed
        # attempt and its global RNG may interleave with PRE observations.
        enabled[0] = False
        epoch = lease._epoch
        ctx.ordinal = 1
        result = ctx.training.train_step(a, lease)
        require(lease._released, 'Original wrapper did not release the actual consumed lease')
        require(result is not None and math.isfinite(float(result)), 'Original attempt returned None/nonfinite')
        require(observer.consumed == len(observer.rows) == 1 and observer.current is observer.raw is None
                and not observer.invalid and not observer.reporting_failed and not observer.errors,
                'One consumed capture did not drain cleanly')
        row = observer.rows[0]
        require(row['index'] == 1 and row['capture_complete'] and row['prefetch']['lease_epoch'] == epoch,
                'First consumed row missing, incomplete, or wrong lease epoch')
        after = s.optimizer_observation(ctx)
        outcome, delta = optimizer_outcome(ctx, before, after, row)
        native_after = ctx.native.batch_update_status()
        native_delta = {key: native_after[key]-native_before[key] for key in
                        ('completed_count', 'success_count', 'fallback_count', 'error_count')}
        require(native_after['enabled'] and native_after['available'] and native_delta ==
                dict(completed_count=1, success_count=1, fallback_count=0, error_count=0),
                'Original one CE reprioritization lacked exact native completion')
    except BaseException as error:
        primary = error
        ctx.capture_primary_failure = dict(error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        enabled[0] = False
        ctx.capture_cleanup_errors = errors = []
        try:
            if lease is not None and not lease._released:
                lease.release()
        except BaseException as error:
            errors.append('lease release: '+repr(error))
        try:
            if producer is not None:
                closed = producer.close(timeout=5.)
                require(closed, 'Owned producer did not stop')
        except BaseException as error:
            errors.append('producer close: '+repr(error))
        try:
            torch.cuda.synchronize(a.device)
        except BaseException as error:
            errors.append('owned device sync: '+repr(error))
        try:
            write_json(ctx.paths['root']/'producer-cleanup.json', dict(producer_closed=closed,
                lease_released=lease is not None and lease._released,
                produced_batches=0 if producer is None else producer.produced_batches,
                direct_state_batches=0 if producer is None else producer.direct_state_batches,
                consumed_attempts=observer.consumed, raw_drained=observer.raw is observer.current is None,
                primary_failure=getattr(ctx,'capture_primary_failure',None),cleanup_errors=list(errors)))
        except BaseException as error:
            errors.append('cleanup evidence: '+repr(error))
        if errors:
            if primary is None:
                raise RuntimeError('Owned capture cleanup failed: '+repr(errors))
            # Preserve the original sampler/train-step exception and traceback;
            # every secondary cleanup failure is retained in phase-failure.
            try:
                print('Secondary capture cleanup failures: '+repr(errors),file=sys.stderr,flush=True)
            except BaseException:
                pass
    require(not (directory/'final.json').exists(), 'One-attempt rehearsal must not manufacture final-eight completion')
    published, row_record = json_input(ctx, directory/'attempt-01.json')
    require(published == observer.rows[0] and published['capture_complete'], 'Durable row differs from observed outcome')
    payload = published['payload']
    require(Path(payload['path']) == directory/'attempt-01.payload.pt', 'Unexpected captured payload path')
    payload_record = ctx.parent.stable_file(payload['path'], payload['sha256'], payload['bytes'])
    context, context_record = json_input(ctx, directory/'context.json')
    require(context['capture_id'] == published['draw_capture_id'] == observer.capture_id
            and published['draw_batch_join_checked'] and published['staged_draw_join_checked']
            and all(published['prefetch_'+where]['current']
                    and published['prefetch_'+where]['lease_epoch'] == epoch
                    and published['prefetch_'+where]['owner_epoch_at_consumption'] == epoch
                    for where in ('begin','pre_loss','exit')),
            'Capture identity differs')
    s.modules_private(ctx)
    return dict(status='OBSERVATIONS_COMPLETE', variant=ctx.variant, qualification_pass=False,
        comparison_pass=True, comparison_scope='actual_capture_only_no_independent_comparison',
        interpretation_requires_review=False, consumed_attempts=1, capture_complete=True, loss_abi=4,
        optimizer_outcome=outcome, actual_exposure_delta=delta, native_priority_delta=native_delta,
        lease_epoch=epoch, lease_released=True, producer_closed=closed,
        before=before, after=after, context=context_record, row=row_record, payload=payload_record,
        model_requires_grad=ctx.requires_grad, source_lock_sha256=ctx.parent.SOURCE_LOCK_SHA256,
        peak_cuda_allocated=torch.cuda.max_memory_allocated(0), peak_cuda_reserved=torch.cuda.max_memory_reserved(0),
        limitations=['One private consumed attempt, not final8 or live agent/server lifecycle',
            'Saved-scaler AMP skip is retained without replacement',
            'Synthetic bounded replay population; no learning/speed/priority-ranking claim',
            'Sequential global RNG observations can overlap producer activity'])


def compare_ce(ctx, actual, expected):
    """Finite numeric mismatches are retained at the original CE tolerance."""
    torch = ctx.torch
    require(isinstance(actual, torch.Tensor) and isinstance(expected, torch.Tensor)
            and actual.shape == expected.shape == (4096,) and actual.dtype == expected.dtype,
            'Conditional/actual CE structure differs')
    require(ctx.science.finite(ctx, actual) and ctx.science.finite(ctx, expected), 'Nonfinite CE interpretation')
    actual, expected = actual.detach().cpu(), expected.detach().cpu()
    tolerance = ctx.lock['tolerances']['ce']
    bad = ~torch.isclose(actual, expected, **tolerance, equal_nan=False)
    difference = (actual.double()-expected.double()).abs()
    allowed = tolerance['atol']+tolerance['rtol']*expected.double().abs()
    records = dict(passed=not bool(bad.any()), tolerance=tolerance, predicate='native-dtype torch.isclose',
        violations=int(bad.sum()), max_abs=float(difference.max()),
        actual_sha256=ctx.science.digest_tree(ctx, actual), expected_sha256=ctx.science.digest_tree(ctx, expected),
        coordinate_examples=[])
    if bool(bad.any()):
        for coordinate in torch.nonzero(bad, as_tuple=False)[:16].tolist():
            key = coordinate[0]
            records['coordinate_examples'].append(dict(index=key, actual=float(actual[key]),
                expected=float(expected[key]), absolute_error=float(difference[key]), allowed_bound=float(allowed[key])))
        records['max_violation_index'] = int(torch.argmax(torch.where(bad, difference,
            torch.full_like(difference, -1))))
    return records, bad


@contextlib.contextmanager
def forbidden_offline_updates(ctx):
    """Observe/reject calls to this owned optimizer/scaler, without forward hooks."""
    calls = dict(optimizer_step=0,scaler_step=0,scaler_update=0)
    ctx.offline_update_guard_counts = calls
    def reject(name):
        def forbidden(*args,**kwargs):
            calls[name] += 1
            raise RuntimeError('Forbidden offline update call: '+name)
        return forbidden
    hook = ctx.agent.optimizer.register_step_pre_hook(reject('optimizer_step'))
    scaler = ctx.agent.grad_scaler
    original_step,original_update = scaler.step,scaler.update
    try:
        scaler.step,scaler.update = reject('scaler_step'),reject('scaler_update')
        yield calls
    finally:
        scaler.step,scaler.update = original_step,original_update
        hook.remove()


def conditional_forward(ctx,kernel,inputs,schedule,payload,*,record,row_record,capture_record,pre_rng):
    """One grad-enabled forward; retain all returned values before validating."""
    torch,s,a = ctx.torch,ctx.science,ctx.agent
    with forbidden_offline_updates(ctx) as update_calls:
        with torch.autocast(device_type='cuda',dtype=torch.float16):
            outputs = kernel(*inputs,schedule)
    torch.cuda.synchronize(a.device)
    after_rng = s.rng_state(ctx)
    retained = save_payload(ctx,ctx.paths['root']/'conditional-recomputed.pt',
        dict(scope='CONDITIONAL RECOMPUTED; never actual executed target',raw_outputs=outputs,
             expected_actual_capture=payload['actual'],rng_before=pre_rng,rng_after=after_rng,
             source_capture_payload=record,source_capture_row=row_record,source_capture_result=capture_record))
    require(isinstance(outputs,tuple) and len(outputs)==5 and isinstance(outputs[4],tuple) and len(outputs[4])==10,
            'Conditional five-output ABI differs')
    actual = dict(weighted_loss=outputs[0],ce=outputs[1],bc_loss=outputs[2],diagnostic_values=outputs[3],
                  conditional={name:value for name,value in zip(TRACE_NAMES,outputs[4])})
    require(s.finite(ctx,actual),'Nonfinite conditional forward; interpretation invalid')
    return actual,retained,after_rng,dict(update_calls)


def recompute(ctx):
    torch, s, a = ctx.torch, ctx.science, ctx.agent
    capture_result, capture_record = json_input(ctx, ctx.layout.output/'capture/phase-result.json')
    require(capture_result['status'] == 'OBSERVATIONS_COMPLETE' and capture_result['variant'] == 'capture'
            and capture_result['capture_complete'] and capture_result['consumed_attempts'] == 1
            and capture_result['loss_abi'] == 4 and capture_result['qualification_pass'] is False
            and capture_result['source_lock_sha256'] == ctx.parent.SOURCE_LOCK_SHA256,
            'Complete one-attempt capture binding required')
    record = capture_result['payload']
    source = ctx.layout.output/'capture/ce-recomputed-capture-private-one/attempt-01.payload.pt'
    require(Path(record['path']) == source and ctx.parent.stable_file(source, record['sha256'], record['bytes']) == record,
            'Captured PRE payload identity changed')
    payload = torch.load(source, map_location='cpu', weights_only=True)
    require(ctx.parent.stable_file(source, record['sha256'], record['bytes']) == record,
            'PRE payload changed during load')
    require(payload['attempt'] == 1 and payload['nonfinite_copies'] == 0 and s.finite(ctx, payload),
            'Captured PRE/actual payload malformed/nonfinite')
    row, row_record = json_input(ctx, capture_result['row']['path'])
    require(row_record == capture_result['row'] and row['capture_complete']
            and row['payload']['sha256'] == record['sha256'] and row['optimizer_outcome'] == capture_result['optimizer_outcome']
            and row['draw_capture_id'] == payload['capture_id'] == payload['draw']['capture_id']
            and payload['draw']['schema'] == 'robotron-replay-draw-observation-v1'
            and row['draw_batch_join_checked'] and row['staged_draw_join_checked'],
            'PRE payload is not joined to the complete actual outcome')
    pre = payload['pre_context']
    require(pre['loss_sha256'] == ctx.lock['original_loss_sha256'] and pre['use_amp'] is True,
            'Captured original loss/autocast profile differs')
    require(pre['learner_device'] == pre['schedule_device'] == 'cuda:0'
            and pre['input_devices'] == ['cuda:0']*8, 'Actual capture was not on the owned CUDA device')
    own_config = {name:value for name,value in vars(ctx.cfg).items()
                  if value is None or type(value) in (bool,int,float,str)}
    cfg = dict(pre['config'])
    require(cfg.pop('replay_tmpfs_dir') == str(ctx.layout.phase('capture')['tmpfs']), 'Captured tmpfs context differs')
    own_config.pop('replay_tmpfs_dir')
    require(cfg == own_config, 'Fresh offline scientific configuration differs from captured PRE')
    require(pre['modes'] == dict(online=True, target=False), 'Unexpected PRE model modes')
    require(torch.get_float32_matmul_precision() == pre['matmul_precision']
            and bool(torch.backends.cuda.matmul.allow_tf32) == pre['tf32_matmul']
            and bool(torch.backends.cudnn.allow_tf32) == pre['tf32_cudnn']
            and bool(torch.backends.cudnn.benchmark) == pre['cudnn_benchmark'], 'Offline numeric policy differs')
    require(capture_result['model_requires_grad'] == ctx.requires_grad, 'Source-default parameter gradient flags differ')
    a.online_net.load_state_dict(payload['online'], strict=True)
    a.target_net.load_state_dict(payload['target'], strict=True)
    a.online_net.train(pre['modes']['online']); a.target_net.train(pre['modes']['target'])
    require(torch.is_grad_enabled(), 'Offline forward must retain training grad-enabled lowering')
    inputs = [payload['inputs'][name].to(device=a.device) for name in INPUT_NAMES]
    expected_dtypes = (torch.float32, torch.long, torch.float32, torch.float32,
                       torch.float32, torch.float32, torch.bool, torch.float32)
    require(tuple(value.dtype for value in inputs) == expected_dtypes
            and inputs[0].shape == inputs[3].shape == (4096,11128)
            and all(value.shape == (4096,) for value in inputs[1:3]+inputs[4:])
            and all(value.device == a.device for value in inputs), 'Offline actual FP32 input reconstruction differs')
    schedule = payload['schedule'].to(device=a.device)
    require(schedule.shape == (3,) and schedule.dtype == torch.float32, 'Offline schedule reconstruction differs')
    offline = importlib.import_module('dqn.offline_loss_kernel')
    require(ctx.parent.digest(offline.__file__) == ctx.lock['offline_loss_sha256'], 'Conditional five-output source differs')
    module = offline.TrainingLoss(a.online_net, a.target_net, SimpleNamespace(**pre['config']),
                                 diagnostics=pre['kernel_constants']['diagnostics'], trace_rows=True)
    require({name:getattr(module,name) for name in CONSTANT_NAMES} == pre['kernel_constants'],
            'Offline loss constants do not exactly match captured compiled4 constants')
    kernel = compile_loss(ctx,module)
    before = dict(online=s.digest_tree(ctx, a.online_net.state_dict()),
        target=s.digest_tree(ctx,a.target_net.state_dict()), optimizer=s.digest_tree(ctx,a.optimizer.state_dict()),
        scaler=a.grad_scaler.state_dict(), clocks=s.clocks(ctx), exposure=a._learning_optimizer_exposure.snapshot())
    s.restore_rng(ctx, payload['rng'])
    pre_rng = s.rng_state(ctx)
    require(s.digest_tree(ctx,pre_rng) == s.digest_tree(ctx,payload['rng']), 'Offline PRE RNG did not restore exactly')
    # Deliberately no torch.no_grad(): this observes the original training
    # forward/autocast lowering. No backward, optimizer/scaler step or update.
    actual,retained,after_rng,update_calls = conditional_forward(ctx,kernel,inputs,schedule,payload,
        record=record,row_record=row_record,capture_record=capture_record,pre_rng=pre_rng)
    # All full tensors are durable BEFORE the first comparison. A finite
    # mismatch cannot discard them or trigger a replacement/retry.
    comparisons, mask = compare_ce(ctx, actual['ce'], payload['actual']['ce'])
    mask_record = save_payload(ctx,ctx.paths['root']/'ce-mismatch-mask.pt',dict(ce=mask))
    after = dict(online=s.digest_tree(ctx,a.online_net.state_dict()),
        target=s.digest_tree(ctx,a.target_net.state_dict()), optimizer=s.digest_tree(ctx,a.optimizer.state_dict()),
        scaler=a.grad_scaler.state_dict(),clocks=s.clocks(ctx),exposure=a._learning_optimizer_exposure.snapshot())
    require(before == after, 'Offline forward changed persistent model/Adam/scaler/exposure/clocks')
    require(update_calls == dict(optimizer_step=0,scaler_step=0,scaler_update=0), 'Offline update guard observed a call')
    require(all(parameter.grad is None for parameter in a.online_net.parameters()), 'Offline backward unexpectedly executed')
    require(ctx.parent.stable_file(source,record['sha256'],record['bytes']) == record, 'Original capture changed')
    s.modules_private(ctx)
    rng_changed = s.digest_tree(ctx,pre_rng) != s.digest_tree(ctx,after_rng)
    return dict(status='OBSERVATIONS_COMPLETE',variant=ctx.variant,qualification_pass=False,
        comparison_pass=comparisons['passed'],interpretation_requires_review=not comparisons['passed'] or rng_changed,
        comparison_scope='Only4096 per-row CE compared at original fixed CE tolerances; weighted loss/BC/diagnostic outputs retained but not compared',
        conditional_recomputed=True,executed_target_observed=False,grad_enabled=True,
        optimizer_steps=update_calls['optimizer_step'],update_guard_counts=dict(update_calls),
        explicit_worker_backward_calls=0,backward_evidence_scope='Source-level explicit worker calls and all parameter.grad None; no AOT/autograd engine hook',
        actual_attempts_in_this_process=0,
        original_capture_outcome=capture_result['optimizer_outcome'],capture_payload=record,
        retained_conditional_payload=retained,ce_mismatch_mask=mask_record,ce_comparison=comparisons,
        rng_observations=dict(pre=s.digest_tree(ctx,pre_rng),post=s.digest_tree(ctx,after_rng),
            post_changed=rng_changed,
            limitation='Restored observations do not establish an all-thread atomic live RNG anchor'),
        before=before,after=after,source_lock_sha256=ctx.parent.SOURCE_LOCK_SHA256,
        peak_cuda_allocated=torch.cuda.max_memory_allocated(0),peak_cuda_reserved=torch.cuda.max_memory_reserved(0),
        limitations=['Offline target/entropy/KL are conditional RECOMPUTED values',
            'CE agreement does not bound missing actual target entropy/KL or replay priority ranks',
            'No explicit worker backward or owned optimizer/scaler calls; no full-agent lifecycle or learning-quality qualification'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--variant',required=True,choices=('capture','recompute'))
    args=parser.parse_args(argv)
    ctx=None
    try:
        ctx=bootstrap(args.manifest,args.variant)
        ctx.science=load_science(ctx)
        setup(ctx)
        result=capture(ctx) if ctx.variant=='capture' else recompute(ctx)
        ctx.science.modules_private(ctx)
        ctx.base.verify_source_copies(ctx.layout,ctx.manifest['sources'])
        require(ctx.parent.read_lock()==ctx.lock,'Final source lock changed')
        ctx.base.guard_live_resources(allowed_pids={os.getpid(),os.getppid()},
                                      expected_main=ctx.manifest['main_owners'])
        write_json(ctx.paths['root']/'phase-result.json',result)
        return 0
    except BaseException as error:
        if ctx is not None:
            try:
                write_json(ctx.paths['root']/'phase-failure.json',dict(status='INVALID_OR_INCOMPLETE',
                    variant=ctx.variant,error=repr(error),traceback=traceback.format_exc(),
                    capture_primary_failure=getattr(ctx,'capture_primary_failure',None),
                    capture_cleanup_errors=getattr(ctx,'capture_cleanup_errors',None),
                    offline_update_guard_counts=getattr(ctx,'offline_update_guard_counts',None)))
            except BaseException as persistence:
                try:
                    print('Failure-evidence error: '+repr(persistence),file=sys.stderr,flush=True)
                except BaseException:
                    pass
        try:
            traceback.print_exc()
        except BaseException:
            pass
        return 1


if __name__=='__main__':
    raise SystemExit(main())

