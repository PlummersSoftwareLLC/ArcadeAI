#!/usr/bin/env python3
"""Internal guarded actual-Rainbow4096 CUDA trace control; no startup numerics.

Only the explicitly launched owned parent may release this worker's token.
This validates an observer on private fixed synthetic inputs, not live learning.
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


def cpu(ctx, value):
    if isinstance(value, ctx.torch.Tensor):
        return value.detach().cpu().clone()
    if isinstance(value, ctx.np.ndarray):
        return ctx.torch.from_numpy(value.copy())
    if isinstance(value, dict):
        return {key: cpu(ctx, item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return type(value)(cpu(ctx, item) for item in value)
    return copy.deepcopy(value)


def tensor_bytes(ctx, value):
    return value.detach().cpu().contiguous().reshape(-1).view(ctx.torch.uint8).numpy().tobytes()


def digest_tree(ctx, value):
    digest = hashlib.sha256()
    def walk(item):
        if isinstance(item, ctx.torch.Tensor):
            digest.update(str((str(item.dtype), list(item.shape))).encode()); digest.update(tensor_bytes(ctx, item))
        elif isinstance(item, ctx.np.ndarray):
            digest.update(str((str(item.dtype), item.shape)).encode()); digest.update(item.tobytes())
        elif isinstance(item, dict):
            for key in sorted(item, key=lambda key: (type(key).__name__, str(key))):
                digest.update(repr(key).encode()); walk(item[key])
        elif isinstance(item, (list, tuple)):
            digest.update(type(item).__name__.encode())
            for part in item: walk(part)
        else: digest.update(repr(item).encode())
    walk(value)
    return digest.hexdigest()


def finite(ctx, value):
    if isinstance(value, ctx.torch.Tensor): return bool(ctx.torch.isfinite(value).all())
    if isinstance(value, dict): return all(finite(ctx, item) for item in value.values())
    if isinstance(value, (list, tuple)): return all(finite(ctx, item) for item in value)
    return not isinstance(value, float) or math.isfinite(value)


def save_tensors(ctx, path, value):
    with Path(path).open('xb') as stream:
        ctx.torch.save(cpu(ctx, value), stream); stream.flush(); os.fsync(stream.fileno())
    Path(path).chmod(0o444)
    return dict(path=str(path), sha256=ctx.parent.digest(path), bytes=Path(path).stat().st_size)


def modules_private(ctx):
    root = ctx.layout.scripts / 'dqn'
    for name, module in list(sys.modules.items()):
        if name == 'dqn' or name.startswith('dqn.'):
            require(Path(module.__file__).resolve().is_relative_to(root), 'Module escaped private sources: ' + name)


def setup(ctx):
    import numpy as np
    import torch
    ctx.np, ctx.torch = np, torch
    torch.set_num_threads(2); torch.set_num_interop_threads(2)
    require(torch.cuda.device_count() == 1 and ctx.old.canonical_uuid(torch.cuda.get_device_properties(0).uuid) ==
            ctx.old.canonical_uuid(ctx.base.GPU0_UUID), 'Visible CUDA UUID/count differs')
    free, total = torch.cuda.mem_get_info(0)
    require(free >= 13 * ctx.base.GIB, 'Post-context free GPU margin insufficient')
    torch.cuda.set_per_process_memory_fraction(ctx.parent.BOUNDS['vram_allocator_bytes'] / total, 0)
    random.seed(ctx.lock['seed']); np.random.seed(ctx.lock['seed']); torch.manual_seed(ctx.lock['seed'])
    sys.path[:] = [value for value in sys.path if value not in ('', str(ctx.base.REPO), str(ctx.base.GAME / 'Scripts'))]
    sys.path.insert(0, str(ctx.layout.scripts))
    ctx.config = importlib.import_module('dqn.config')
    ctx.cfg, ctx.metrics = ctx.config.RL_CONFIG, ctx.config.metrics
    cfg = ctx.cfg
    for name, value in dict(memory_size=8192, min_replay_to_train=4096, batch_size=4096,
            replay_tmpfs_dir=str(ctx.paths['tmpfs']), replay_prefetch_slots=3,
            hof_enabled=True, ephof_enabled=True, hof_max_episodes=8, ephof_max_episodes=8,
            hof_episode_stride=512, ephof_episode_stride=512, hof_min_transitions=4096, ephof_min_transitions=4096,
            interesting_replay_bank_size=8192, recent_replay_window=1024,
            bank_starvation_adds=1000, bank_stale_quota_floor=.25).items():
        require(hasattr(cfg, name), 'Unknown fixture configuration: ' + name); setattr(cfg, name, value)
    require(ctx.paths['tmpfs'].is_dir() and Path(cfg.replay_tmpfs_dir) == ctx.paths['tmpfs'], 'Private tmpfs must preexist')
    require(cfg.state_size == 11128 and cfg.frame_stack == 4 and cfg.single_frame_state_size == 2782 and
            cfg.batch_size == 4096 and cfg.num_atoms == 51 and cfg.num_joint_actions == 81 and
            cfg.n_step == 3 and cfg.max_samples_per_frame == 8 and cfg.c51_target_smoothing == 0 and
            cfg.diagnostic_interval == 20 and cfg.replay_prefetch_slots == 3 and cfg.replay_direct_state_fill and
            cfg.optimizer_fused and cfg.torch_compile_mode == 'default', 'Held geometry/recipe differs')
    require(Path(ctx.config.MODEL_DIR) == ctx.paths['models'] and ctx.config.learning_control.path == ctx.paths['control'],
            'Private model/control path differs')
    ctx.metrics.training_enabled = True
    ctx.model = importlib.import_module('dqn.model')
    ctx.replay = importlib.import_module('dqn.replay_buffer')
    native = importlib.import_module('dqn.native_sumtree')
    require(native.NATIVE_AVAILABLE and native.NATIVE_GATHER_AVAILABLE and native.NATIVE_BATCH_AVAILABLE and native.NATIVE_BATCH_ENABLED,
            'Current native propagation/gather/batch-update capability required; no fallback')
    ctx.native = native
    ctx.prefetch = importlib.import_module('dqn.prefetch')
    ctx.exposure = importlib.import_module('dqn.learning_exposure')
    ctx.trace_module = importlib.import_module('dqn.executed_ce_trace') if ctx.variant == 'on' else None
    ctx.training = importlib.import_module('dqn.baseline_training' if ctx.variant == 'base' else 'dqn.training')
    ctx.loss = importlib.import_module('dqn.baseline_loss_kernel' if ctx.variant == 'base' else 'dqn.loss_kernel')
    modules_private(ctx)
    require(ctx.model.device == torch.device('cuda:0') and ctx.training.device == torch.device('cuda:0'), 'Unexpected learner device')
    checkpoint = torch.load(ctx.trained, map_location='cpu', weights_only=True)
    require(ctx.parent.stable_file(ctx.trained,ctx.lock['checkpoint']['sha256'],ctx.lock['checkpoint']['bytes']) ==
            ctx.manifest['trained_fixture']['copied'], 'Private trained checkpoint changed during load')
    require(finite(ctx, checkpoint), 'Trained fixture nonfinite')
    for name in ('training_steps', 'optimized_samples'):
        require(checkpoint[name] == ctx.lock['checkpoint'][name], 'Fixture clock differs: ' + name)
    agent = SimpleNamespace(online_net=ctx.model.RainbowNet(11128).cuda(), target_net=ctx.model.RainbowNet(11128).cuda(),
        infer_net=ctx.model.RainbowNet(11128).cuda(), device=torch.device('cuda:0'), use_amp=True,
        training_enabled=True, training_steps=checkpoint['training_steps'], optimized_samples=checkpoint['optimized_samples'],
        last_target_update_samples=checkpoint['last_target_update_samples'], baseline_batch_size=checkpoint['baseline_batch_size'],
        lr_gear=checkpoint['lr_gear'], lr_anchor_step=checkpoint['lr_anchor_step'], lr_manual_scale=1.,
        loaded_training_steps=checkpoint['training_steps'], last_inference_sync=checkpoint['training_steps'],
        last_inference_sync_samples=checkpoint['optimized_samples'], _training_lock=__import__('threading').RLock(),
        compiled_online_joint_dist=None, compiled_online_q_joint=None, compiled_target_joint_dist=None,
        compiled_training_outputs=None, compiled_training_loss=None, compiled_training_loss_diagnostics=None,
        _executed_ce_trace=None, _learning_optimizer_exposure=ctx.exposure.OptimizerExposure())
    agent.online_net.load_state_dict(checkpoint['online_state_dict'], strict=True)
    agent.target_net.load_state_dict(checkpoint['target_state_dict'], strict=True)
    agent.infer_net.load_state_dict(checkpoint['online_state_dict'], strict=True)
    agent.online_net.train(); agent.target_net.eval(); agent.infer_net.eval()
    agent.optimizer = torch.optim.Adam(agent.online_net.parameters(), lr=2.5e-5, eps=1.5e-4, fused=True)
    agent.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    require(type(agent.optimizer) is torch.optim.Adam and agent.optimizer.defaults.get('fused') is True and
            all(group.get('fused') is True and group['lr'] == 2.5e-5 for group in agent.optimizer.param_groups),
            'Actual fused Adam required without fallback')
    agent.grad_scaler = torch.amp.GradScaler('cuda', enabled=True)
    agent.grad_scaler.load_state_dict(checkpoint['grad_scaler_state_dict'])
    require(agent.grad_scaler.is_enabled() and agent.grad_scaler.get_scale() == ctx.lock['checkpoint']['grad_scaler_scale'] and
            agent.grad_scaler.state_dict()['_growth_tracker'] == ctx.lock['checkpoint']['grad_scaler_growth_tracker'],
            'Actual saved CUDA scaler required; no scale override')
    ctx.agent, ctx.checkpoint = agent, checkpoint
    agent.schedule_steps = agent.optimized_samples / agent.baseline_batch_size
    ctx.current = None; ctx.ordinal = 0; ctx.target_reference = ctx.infer_reference = 0
    def update_lr():
        for group in agent.optimizer.param_groups: group['lr'] = 2.5e-5
    def update_target():
        require(cfg.target_tau == 1., 'This source-equivalent hook requires held hard target update')
        agent.target_net.load_state_dict(agent.online_net.state_dict())
        agent.target_net.eval(); agent.last_target_update_samples = agent.optimized_samples
        ctx.target_reference = ctx.ordinal
    def sync_inference(force=False):
        if force or agent.optimized_samples - agent.last_inference_sync_samples >= cfg.inference_sync_steps * agent.baseline_batch_size:
            agent.infer_net.load_state_dict(agent.online_net.state_dict())
            agent.last_inference_sync = agent.training_steps; agent.last_inference_sync_samples = agent.optimized_samples
            ctx.infer_reference = ctx.ordinal
    agent._update_lr, agent.update_target, agent._sync_inference = update_lr, update_target, sync_inference
    for name in ('frame_count', 'learner_frame_count', 'measurement_frame_count', 'epsilon', 'expert_ratio'):
        setattr(ctx.metrics, name, checkpoint[name])
    ctx.metrics.total_training_steps = checkpoint['total_training_steps']
    ctx.metrics.total_optimized_samples = ctx.metrics.loaded_optimized_samples = checkpoint['optimized_samples']
    ctx.metrics.loaded_frame_count = checkpoint['frame_count']
    ctx.metrics.loaded_measurement_frame_count = checkpoint['measurement_frame_count']
    require(len(agent.optimizer.state) == 81 and all(float(slot['step']) == ctx.lock['checkpoint']['adam_steps']
            for slot in agent.optimizer.state.values()), 'Actual81 initial Adam clocks differ')
    ctx.runtime = dict(python=sys.version, torch=str(torch.__version__), cuda=torch.version.cuda,
        gpu_uuid=str(torch.cuda.get_device_properties(0).uuid), gpu_name=torch.cuda.get_device_name(0),
        effective_gil_enabled=getattr(sys, '_is_gil_enabled', lambda: None)(),
        matmul_precision=torch.get_float32_matmul_precision(), tf32_matmul=torch.backends.cuda.matmul.allow_tf32,
        tf32_cudnn=torch.backends.cudnn.allow_tf32, cudnn_benchmark=torch.backends.cudnn.benchmark,
        model_modes={name:net.training for name, net in (('online',agent.online_net),('target',agent.target_net),('infer',agent.infer_net))},
        dropout=[float(module.p) for module in agent.online_net.modules() if isinstance(module,torch.nn.Dropout)],
        noise_buffer_names=[name for name,_ in agent.online_net.named_buffers() if 'noise' in name.lower()],
        optional_expert='not imported or exercised; expert-labelled synthetic rows only',
        hardware_scope='Display GPU0, not live GB300; no actual agent constructor/lifecycle claim')
    ctx.runtime['native'] = dict(status=native.NATIVE_STATUS,propagation=native.NATIVE_AVAILABLE,
        gather=native.NATIVE_GATHER_AVAILABLE,batch_available=native.NATIVE_BATCH_AVAILABLE,batch_enabled=native.NATIVE_BATCH_ENABLED)
    write_json(ctx.paths['root'] / 'runtime.json', ctx.runtime)
    return ctx


def make_private_replay(ctx):
    """Frozen bounded synthetic storage; production sampler/update algorithms.

    No width8 fixture expansion: EVERY state/next-state coordinate is in[0,1].
    Four declared patterns repeat; they are not a game-state population claim.
    """
    np, cfg = ctx.np, ctx.cfg
    memory = ctx.replay.PrioritizedReplayBuffer(8192, 11128, alpha=cfg.priority_alpha)
    patterns = np.zeros((4, 11128), dtype=np.float32)
    for mode in (1, 2, 3):
        for frame in range(4):
            offset = frame * cfg.single_frame_state_size
            patterns[mode, offset:offset + 2] = (.3, .5)
            if mode >= 2:
                token = offset + ctx.config.ENEMY_TOKEN_OFFSET
                patterns[mode, token:token + 4] = (1., .2, .1, .25)
                patterns[mode, token + ctx.config.TYPE_ONEHOT_OFFSET] = 1.
            if mode == 3:
                patterns[mode, offset + ctx.config.MODEL_LANE_OFFSET] = .25
                patterns[mode, offset + ctx.config.MODEL_GRID_OFFSET] = .5
    indices = np.arange(8192)
    # Block assignments avoid column-rule expansion and its out-of-range values.
    for mode in range(4):
        memory.states[mode::4] = patterns[mode]
        memory.next_states[mode::4] = patterns[(mode + 1) % 4]
    memory.actions[:] = indices % 81
    memory.rewards[:] = np.asarray(ctx.lock['fixture_recipe']['reward_cycle'], dtype=np.float32)[indices % 5]
    memory.dones[:] = indices % 17 == 0
    memory.horizons[:] = indices % 3 + 1
    memory.is_expert[:] = indices % 7 == 0
    memory.actor_kind[:] = np.where(memory.is_expert, 2, indices % 2)
    memory.interesting[:] = 1.
    memory._interesting_bank[:] = indices
    memory._interesting_bank_count = memory._n_interesting = 8192
    memory.size = memory.tree.size = 8192
    memory.tree.data_ptr = 137; memory._adds_total = 8192 + 137
    memory.tree.tree[8192:] = .03 + (indices % 101) / 11.
    for parent in range(8191, 0, -1):
        memory.tree.tree[parent] = memory.tree.tree[2 * parent] + memory.tree.tree[2 * parent + 1]
    memory.tree.max_priority = float(memory.tree.tree[8192:].max())
    for bank in ('hof', 'ephof'):
        getattr(memory, bank + '_ep_len')[:] = 512
        getattr(memory, bank + '_ep_score')[:] = 100000
        setattr(memory, bank + '_ep_count', 8); setattr(memory, bank + '_total', 4096)
        setattr(memory, '_' + bank + '_flat', np.arange(4096, dtype=np.int64))
        setattr(memory, '_' + bank + '_last_admit_add', memory._adds_total)
        setattr(memory, '_' + bank + '_last_normal_admit_add', memory._adds_total)
        memory._bank_revision[bank] = 4
        for field in ('actions', 'rewards', 'dones', 'horizons', 'is_expert', 'actor_kind'):
            getattr(memory, bank + '_' + field)[:] = getattr(memory, field)[:4096]
        for mode in range(4):
            getattr(memory, bank + '_states')[mode::4] = patterns[mode]
            getattr(memory, bank + '_next_states')[mode::4] = patterns[(mode + 1) % 4]
    require(np.isfinite(patterns).all() and float(patterns.min()) >= 0. and float(patterns.max()) <= 1., 'Bounded pattern contract failed')
    return memory


def tensorize_arrays(ctx, value):
    if isinstance(value, ctx.np.ndarray): return ctx.torch.from_numpy(value.copy())
    if isinstance(value, dict): return {key:tensorize_arrays(ctx,item) for key,item in value.items()}
    if isinstance(value, (tuple,list)): return type(value)(tensorize_arrays(ctx,item) for item in value)
    return value


def numpy_arrays(ctx, value):
    if isinstance(value, ctx.torch.Tensor): return value.numpy().copy()
    if isinstance(value, dict): return {key:numpy_arrays(ctx,item) for key,item in value.items()}
    if isinstance(value, (tuple,list)): return type(value)(numpy_arrays(ctx,item) for item in value)
    return value


def rng_state(ctx):
    state = ctx.np.random.get_state()
    return dict(python=random.getstate(), numpy=(state[0], ctx.torch.from_numpy(state[1].astype(ctx.np.int64)), *state[2:]),
                cpu=ctx.torch.get_rng_state().clone(), cuda=ctx.torch.cuda.get_rng_state(0).cpu().clone())


def restore_rng(ctx, value):
    random.setstate(value['python'])
    state = value['numpy']
    ctx.np.random.set_state((state[0], state[1].numpy().astype(ctx.np.uint32), *state[2:]))
    ctx.torch.set_rng_state(value['cpu']); ctx.torch.cuda.set_rng_state(value['cuda'], 0)


def inputs(ctx):
    directory = ctx.layout.output / 'inputs'
    ctx.backing = make_private_replay(ctx)
    if ctx.variant == 'base':
        batch, draw = ctx.backing.sample_with_metadata(4096, beta=1., capture_id='synthetic-fixed-cuda-draw')
        require(batch is not None and draw is not None and not draw.get('observer_error'), 'Fixture sampler observation failed')
        draw = copy.deepcopy(draw)
        draw.update(fixture_reuse=True, fixture_original_draw_only=True, sampler_draw_repeated=False)
        for index in (0, 3):
            require(batch[index].shape == (4096,11128) and ctx.np.isfinite(batch[index]).all() and
                    float(batch[index].min()) >= 0. and float(batch[index].max()) <= 1., 'Persisted state range failed')
        with (directory / 'batch.npz').open('xb') as stream:
            ctx.np.savez(stream, **dict(zip(FIELDS, batch))); stream.flush(); os.fsync(stream.fileno())
        (directory / 'batch.npz').chmod(0o444)
        save_tensors(ctx, directory / 'draw.pt', tensorize_arrays(ctx, draw))
        save_tensors(ctx, directory / 'torch-rng.pt', rng_state(ctx))
        files = {name:dict(sha256=ctx.parent.digest(directory / name), bytes=(directory / name).stat().st_size)
                 for name in ('trained.pt','batch.npz','draw.pt','torch-rng.pt')}
        write_json(directory / 'inputs.json', dict(schema=ctx.parent.SCHEMA, seed=ctx.lock['seed'],
                   source_lock_sha256=ctx.parent.digest(HERE / 'source-lock.json'), files=files,
                   fixture_recipe=ctx.lock['fixture_recipe'], checkpoint=ctx.lock['checkpoint']))
        (directory / 'inputs.json').chmod(0o444)
    description = json.loads((directory / 'inputs.json').read_text())
    require(description['source_lock_sha256'] == ctx.parent.digest(HERE / 'source-lock.json') and
            description['fixture_recipe'] == ctx.lock['fixture_recipe'] and description['checkpoint'] == ctx.lock['checkpoint'],
            'Fixed input provenance differs')
    for name, record in description['files'].items():
        require(Path(name).name == name and ctx.parent.digest(directory / name) == record['sha256'] and
                (directory / name).stat().st_size == record['bytes'], 'Persisted input changed: ' + name)
    with ctx.np.load(directory / 'batch.npz', allow_pickle=False) as archive:
        require(set(archive.files) == set(FIELDS), 'Batch fields differ')
        ctx.batch = tuple(archive[name].copy() for name in FIELDS)
    ctx.draw = numpy_arrays(ctx, ctx.torch.load(directory / 'draw.pt', map_location='cpu', weights_only=True))
    ctx.rng = ctx.torch.load(directory / 'torch-rng.pt', map_location='cpu', weights_only=True)
    ctx.input_files = description['files']
    ctx.input_description_sha256 = ctx.parent.digest(directory / 'inputs.json')


class FixedBatchSource:
    """Declared test-side reuse; actual staging and priority implementation.

    Exactly one actual synthetic sampler draw was persisted. This facade is
    not a new production sampler or a claim of eight fresh production draws.
    """
    def __init__(self, ctx):
        self.ctx = ctx
        self.state_size = 11128
        self.capacity = ctx.backing.capacity
        self._ephof_base = ctx.backing._ephof_base
        self.calls = 0
    def __len__(self): return len(self.ctx.backing)
    def sample(self, size, beta=1., _state_out=None):
        require(size == 4096 and beta == 1., 'Fixed fixture size/beta differs')
        self.calls += 1
        outputs = dict(zip((0,3), _state_out)) if _state_out is not None else {}
        batch = []
        for index, item in enumerate(self.ctx.batch):
            if index in outputs:
                outputs[index][:] = item; batch.append(outputs[index])
            else:
                batch.append(item.copy())
        return tuple(batch)
    def sample_into(self, size, states_out, next_states_out, beta=1.):
        return self.sample(size, beta, _state_out=(states_out,next_states_out))
    def sample_with_metadata(self, size, beta=1., capture_id=None, _state_out=None):
        return self.sample(size, beta, _state_out), copy.deepcopy(self.ctx.draw)
    def update_priorities(self, indices, errors, **kwargs):
        require(self.ctx.np.array_equal(indices, self.ctx.batch[8]), 'Priority indices differ from fixed draw')
        self.ctx.current['priorities'] = self.ctx.np.array(errors, copy=True)
        return self.ctx.backing.update_priorities(indices, errors, **kwargs)


def clocks(ctx):
    agent = ctx.agent
    return dict(training_steps=agent.training_steps, optimized_samples=agent.optimized_samples,
        last_target_update_samples=agent.last_target_update_samples, last_inference_sync=agent.last_inference_sync,
        last_inference_sync_samples=agent.last_inference_sync_samples,
        frame_count=ctx.metrics.frame_count, learner_frame_count=ctx.metrics.learner_frame_count,
        measurement_frame_count=ctx.metrics.measurement_frame_count,
        total_training_steps=ctx.metrics.total_training_steps, total_optimized_samples=ctx.metrics.total_optimized_samples,
        target_reference_attempt=ctx.target_reference, infer_reference_attempt=ctx.infer_reference,
        learning_rates=[group['lr'] for group in agent.optimizer.param_groups])


def optimizer_observation(ctx):
    torch, agent = ctx.torch, ctx.agent
    torch.cuda.synchronize(0)
    steps, moments = {}, {}
    for name, parameter in agent.online_net.named_parameters():
        slot = agent.optimizer.state.get(parameter, {})
        step = slot.get('step')
        steps[name] = 0. if step is None else float(step.detach().cpu())
        require(math.isfinite(steps[name]) and steps[name] >= 0 and steps[name].is_integer(), 'Malformed actual Adam clock')
        moments[name] = {key:value for key,value in slot.items() if key != 'step'}
    persistent = dict(online=agent.online_net.state_dict(), target=agent.target_net.state_dict(),
        infer=agent.infer_net.state_dict(), optimizer=agent.optimizer.state_dict(), scaler=agent.grad_scaler.state_dict())
    return dict(steps=steps, online=digest_tree(ctx, persistent['online']), moments=digest_tree(ctx,moments),
        persistent_finite=finite(ctx,persistent), scaler=agent.grad_scaler.state_dict(),
        exposure=agent._learning_optimizer_exposure.snapshot(), clocks=clocks(ctx),
        modes=[net.training for net in (agent.online_net,agent.target_net,agent.infer_net)])


def classify(ctx, before, after):
    old, new = before['exposure'], after['exposure']
    require(all(old[name] == new[name] for name in ('process_id','instance_monotonic_ns','epoch')),
            'Exposure identity/epoch changed')
    delta = {name:new['total'][name]-old['total'][name] for name in old['total']}
    require(new['available'] and delta['attempts_started'] == delta['outcomes_recorded'] == 1 and
            delta['unavailable'] == 0 and delta['applied']+delta['amp_skipped'] == 1,
            'Actual packed CUDA outcome unavailable or ambiguous')
    require(after['persistent_finite'] and set(before['steps']) == set(after['steps']), 'Persistent state nonfinite/Adam identities changed')
    gradients = ctx.current.get('gradients')
    require(gradients is not None, 'No real preclip gradient observation')
    if delta['amp_skipped'] == 1:
        require(before['steps'] == after['steps'] and before['online'] == after['online'] and
                before['moments'] == after['moments'] and 0 < after['scaler']['scale'] < before['scaler']['scale'],
                'AMP skip lacks unchanged slots/online/moments and reduced finite scale')
        outcome = 'amp_skipped'
    else:
        require(all(after['steps'][key] >= value for key,value in before['steps'].items()) and
                any(after['steps'][key] > value for key,value in before['steps'].items()) and
                after['online'] != before['online'] and finite(ctx,gradients) and
                math.isfinite(float(ctx.current['grad_norm'])), 'Applied call lacks real finite-gradient/Adam/online progress')
        outcome = 'applied'
    return outcome, delta


def compile_kernels(ctx):
    torch, agent = ctx.torch, ctx.agent
    if ctx.variant == 'on':
        agent._executed_ce_trace = ctx.trace_module.ExecutedCETrace(Path(os.environ['DQN_EXECUTED_CE_TRACE_DIR']), ctx.cfg,
            optimizer_exposure=agent._learning_optimizer_exposure, runtime=ctx.runtime | {
                'fixture':'persisted one synthetic draw reused8times; not live8',
                'input_manifest_sha256':ctx.input_description_sha256})
    before = optimizer_observation(ctx)
    import torch._dynamo as dynamo
    from torch._dynamo.utils import counters
    for name, value in (('recompile_limit',64),('cache_size_limit',64),
                        ('accumulated_recompile_limit',1024),('accumulated_cache_size_limit',1024)):
        if hasattr(dynamo.config,name): setattr(dynamo.config,name,value)
    counters.clear()
    kernels = []
    expected_abi = 5 if ctx.variant == 'on' else 4
    def observed(compiled):
        def invoke(*args):
            outputs = compiled(*args)
            require(len(outputs) == expected_abi, 'Real compiled return ABI differs')
            if ctx.current is not None:
                require('ce' not in ctx.current, 'A second training loss forward occurred')
                ctx.current['ce'] = outputs[1].detach().float().cpu().clone()
                ctx.current['weighted_loss'] = float(outputs[0].detach().float().cpu())
                ctx.current['bc_loss'] = float(outputs[2].detach().float().cpu())
                ctx.current['diagnostic'] = outputs[3].detach().float().cpu().clone()
            return outputs
        return invoke
    for diagnostics in (False,True):
        kwargs = {} if ctx.variant == 'base' else {'trace_rows':ctx.variant == 'on'}
        kernel = ctx.loss.TrainingLoss(agent.online_net,agent.target_net,ctx.cfg,diagnostics=diagnostics,**kwargs)
        kernels.append(torch.compile(kernel,dynamic=False,options={'triton.cudagraphs':False}))
    agent.compiled_training_loss, agent.compiled_training_loss_diagnostics = [observed(kernel) for kernel in kernels]
    tensors = tuple(torch.from_numpy(ctx.batch[index]).to(device='cuda:0',dtype=dtype) for index,dtype in
        zip((0,1,2,3,4,5,6,9),(torch.float32,torch.long,torch.float32,torch.float32,
                               torch.float32,torch.float32,torch.bool,torch.float32)))
    schedule = torch.ones(3,device='cuda:0',dtype=torch.float32)
    warmups = []
    for diagnostics, kernel in zip((False,True), kernels):
        for empty in (False,True):
            states = torch.zeros_like(tensors[0]) if empty else tensors[0]
            next_states = torch.zeros_like(tensors[3]) if empty else tensors[3]
            with torch.autocast('cuda',dtype=torch.float16):
                outputs = kernel(states,tensors[1],tensors[2],next_states,tensors[4],tensors[5],tensors[6],tensors[7],schedule)
            require(len(outputs) == expected_abi, 'Warmup ABI differs')
            if ctx.variant == 'on':
                require(len(outputs[4])==10 and all(not item.requires_grad for item in outputs[4]), 'Warmup fifth payload detached ABI differs')
                projected,logp=outputs[4][:2]
                torch.testing.assert_close(outputs[1].detach().float(),-(projected.float()*logp.float()).sum(1),
                                           **ctx.lock['tolerances']['ce'])
                reconstructed=(tensors[7]*outputs[1]).mean()+sum(outputs[4][7:10])
                torch.testing.assert_close(outputs[0].detach().float(),reconstructed.detach().float(),
                                           **ctx.lock['tolerances']['ce'])
            outputs[0].backward()
            gradient = {name:None if parameter.grad is None else parameter.grad.detach().cpu().clone()
                        for name,parameter in agent.online_net.named_parameters()}
            payload = dict(ce=outputs[1].detach().float().cpu().clone(), loss=float(outputs[0].detach().float().cpu()),
                           gradient=gradient, diagnostics=diagnostics, empty=empty)
            require(finite(ctx,payload), 'Nonfinite unscaled compile-warmup values; no optimizer skip inference')
            path = ctx.layout.output / 'base' / ('warmup-%d-%d.pt' % (diagnostics,empty))
            if ctx.variant == 'base': save_tensors(ctx,path,payload)
            else:
                reference = torch.load(path,map_location='cpu',weights_only=True)
                warmups.append(compare(ctx,payload,reference,'warmup',mode='gradient'))
            agent.optimizer.zero_grad(set_to_none=True)
            del outputs,gradient,payload
    after = optimizer_observation(ctx)
    require(before == after, 'Compile warmup mutated model/Adam/scaler/exposure/clocks')
    require(agent._executed_ce_trace is None or agent._executed_ce_trace.consumed == 0, 'Warmup consumed a trace ordinal')
    require(sum(counters['graph_break'].values()) == 0 and counters['stats']['unique_graphs'] == 2,
            'Graph break/fallback/unexpected compile specialization')
    require(getattr(sys,'_is_gil_enabled',lambda:None)() is False,
            'Held free-thread runtime required after Torch/Triton imports; no silent GIL-enabled validation')
    ctx.compile_counters = counters
    write_json(ctx.paths['root'] / 'warmup-proof.json', dict(before=before,after=after,
        trace_consumed=0,expected_abi=expected_abi,comparisons=warmups,
        counters={str(key):dict(value) for key,value in counters.items()},
        scope='Both static diagnostic flags warmed; natural first8 full steps use saved diagnostic_interval20'))
    del tensors
    restore_rng(ctx,ctx.rng)


def compare(ctx, actual, expected, path, *, mode='online', output=None):
    """Actual tensor tolerance comparisons, with per-tensor evidence/hashes."""
    torch = ctx.torch
    output = [] if output is None else output
    if isinstance(expected,torch.Tensor):
        require(isinstance(actual,torch.Tensor) and actual.shape == expected.shape and actual.dtype == expected.dtype,
                'Tensor structure differs: '+path)
        left,right = actual.detach().cpu(),expected.detach().cpu()
        selected = ('gradient' if '/gradient' in path else 'moment' if '/optimizer' in path and
                    path.endswith(('/exp_avg','/exp_avg_sq')) else 'ce' if path.endswith(('/ce','/priority_errors')) else mode)
        exact = path.endswith('/step') or not expected.is_floating_point()
        tolerance = dict(rtol=0.,atol=0.) if exact else ctx.lock['tolerances'][selected]
        record = dict(path=path,dtype=str(left.dtype),shape=list(left.shape),tolerance=tolerance,
            actual_sha256=hashlib.sha256(tensor_bytes(ctx,left)).hexdigest(),
            expected_sha256=hashlib.sha256(tensor_bytes(ctx,right)).hexdigest())
        mask = torch.isfinite(left) & torch.isfinite(right)
        if bool(mask.any()):
            difference = left[mask].double()-right[mask].double()
            record.update(max_abs=float(difference.abs().max()),l2_error=float(torch.linalg.vector_norm(difference)),
                reference_l2=float(torch.linalg.vector_norm(right[mask].double())))
        try:
            torch.testing.assert_close(left,right,**tolerance,equal_nan=selected=='gradient')
            record['passed'] = True
        except Exception:
            record['passed'] = False
            output.append(record)
            raise
        output.append(record)
    elif isinstance(expected,dict):
        require(isinstance(actual,dict) and set(actual)==set(expected),'Mapping keys differ: '+path)
        for key in expected: compare(ctx,actual[key],expected[key],path+'/'+str(key),mode=mode,output=output)
    elif isinstance(expected,(tuple,list)):
        require(type(actual)==type(expected) and len(actual)==len(expected),'Sequence differs: '+path)
        for index,(left,right) in enumerate(zip(actual,expected)):
            compare(ctx,left,right,path+'/'+str(index),mode=mode,output=output)
    elif isinstance(expected,float) and not math.isfinite(expected):
        require(isinstance(actual,float) and (math.isnan(actual) and math.isnan(expected) or actual==expected),
                'Nonfinite scalar pattern differs: '+path)
    elif isinstance(expected,float) and path.endswith(('/loss','/weighted_loss','/bc_loss','/grad_norm')):
        tolerance=ctx.lock['tolerances']['scalars']
        require(isinstance(actual,(int,float)) and math.isclose(actual,expected,rel_tol=tolerance['rtol'],abs_tol=tolerance['atol']),
                'Scalar differs: '+path)
    else: require(actual==expected,'Exact field differs: '+path)
    return output


def checked_reference(ctx, ordinal):
    row = ctx.base_result['references'][ordinal-1]
    path = ctx.layout.output / 'base' / ('reference-%02d.pt' % ordinal)
    require(ctx.parent.digest(path) == row['sha256'] and path.stat().st_size == row['bytes'], 'Baseline reference changed')
    value = ctx.torch.load(path,map_location='cpu',weights_only=True)
    require(ctx.parent.digest(path) == row['sha256'], 'Baseline reference changed during load')
    return value


def refreshed_reference(ctx, ordinal, *, target):
    if ordinal == 0:
        return ctx.checkpoint['target_state_dict' if target else 'online_state_dict']
    return checked_reference(ctx,ordinal)['online']


def observe_steps(ctx):
    torch, agent = ctx.torch, ctx.agent
    inputs(ctx)
    agent.memory = FixedBatchSource(ctx)
    compile_kernels(ctx)
    if ctx.variant != 'base':
        ctx.base_result = json.loads((ctx.layout.output / 'base/phase-result.json').read_text())
        require(ctx.base_result['status'] == 'VARIANT_COMPLETE' and ctx.base_result['variant'] == 'base' and
                ctx.base_result['input_manifest_sha256'] == ctx.input_description_sha256 and
                ctx.base_result['source_lock_sha256'] == ctx.parent.digest(HERE / 'source-lock.json'), 'Baseline provenance differs')
    original_clip = torch.nn.utils.clip_grad_norm_
    def observe_clip(parameters,*args,**kwargs):
        parameters = list(parameters)
        require(ctx.current is not None and 'gradients' not in ctx.current, 'Unexpected/repeated clip boundary')
        ctx.current['gradients'] = {name:None if parameter.grad is None else parameter.grad.detach().cpu().clone()
                                   for name,parameter in agent.online_net.named_parameters()}
        result = original_clip(parameters,*args,**kwargs)
        ctx.current['grad_norm'] = float(result.detach().float().cpu())
        return result
    torch.nn.utils.clip_grad_norm_ = observe_clip
    producer = None
    rows, references = [], []
    try:
        producer = ctx.prefetch.ReplayPrefetcher(agent.memory,4096,lambda:1.,torch.device('cuda:0'),use_amp=True,
            depth=3,min_replay_size=4096,direct_state_fill=True,trace_observer=agent._executed_ce_trace)
        for ordinal in range(1,9):
            ctx.ordinal = ordinal
            ctx.current = {}
            before = optimizer_observation(ctx)
            native_before = ctx.native.batch_update_status()
            write_json(ctx.paths['root'] / ('attempt-%02d.entered.json' % ordinal), dict(index=ordinal,before=before))
            lease = None
            try:
                lease = producer.get(timeout=10.)
                require(lease is not None and lease.is_current, 'No current real CUDA prefetch lease')
                lease_epoch = lease._epoch
                # Private synthetic credits preserve the actual cap8 guard;
                # these are not actor/wire observations or learner evidence.
                ctx.metrics.frame_count += 1024; ctx.metrics.learner_frame_count += 512
                agent.schedule_steps = agent.optimized_samples / agent.baseline_batch_size
                result = ctx.training.train_step(agent,lease)
                require(lease._released, 'Real training wrapper did not release CUDA lease')
                after = optimizer_observation(ctx)
                ctx.current['after'] = after
                require(result is not None and math.isfinite(float(result)), 'Actual training returnedNone/nonfinite loss; no replacement')
                outcome, delta = classify(ctx,before,after)
                native_after = ctx.native.batch_update_status()
                native_delta = {key:native_after[key]-native_before[key] for key in
                                ('completed_count','success_count','fallback_count','error_count')}
                require(native_after['enabled'] and native_after['available'] and native_delta ==
                        dict(completed_count=1,success_count=1,fallback_count=0,error_count=0),
                        'Actual CE reprioritization did not complete exactlyone native batch update without fallback')
                require(ctx.current.get('priorities') is not None and
                        ctx.current.get('ce') is not None, 'No executed loss/priority observation')
                payload = dict(outcome=outcome,exposure_delta=delta,native_priority_delta=native_delta,clocks=clocks(ctx),
                    scaler=agent.grad_scaler.state_dict(),adam_steps=after['steps'],
                    rng=rng_state(ctx),online=cpu(ctx,agent.online_net.state_dict()),
                    gradient=ctx.current['gradients'],optimizer=cpu(ctx,agent.optimizer.state_dict()),
                    ce=ctx.current['ce'],priority_errors=torch.from_numpy(ctx.current['priorities'].copy()),
                    weighted_loss=ctx.current['weighted_loss'],bc_loss=ctx.current['bc_loss'],
                    grad_norm=ctx.current['grad_norm'],diagnostic=ctx.current['diagnostic'])
                row = dict(index=ordinal,outcome=outcome,before=before,after=after,lease_epoch=lease_epoch,
                           released=True,payload_sha256=digest_tree(ctx,payload),comparisons=[])
                if ctx.variant == 'base':
                    record = save_tensors(ctx,ctx.paths['root'] / ('reference-%02d.pt' % ordinal),payload)
                    references.append(record)
                else:
                    reference = checked_reference(ctx,ordinal)
                    try:
                        compare(ctx,payload,reference,'attempt-%02d'%ordinal,output=row['comparisons'])
                        compare(ctx,agent.target_net.state_dict(),refreshed_reference(ctx,ctx.target_reference,target=True),
                                'target',output=row['comparisons'])
                        compare(ctx,agent.infer_net.state_dict(),refreshed_reference(ctx,ctx.infer_reference,target=False),
                                'inference',output=row['comparisons'])
                    finally:
                        write_json(ctx.paths['root'] / ('attempt-%02d.comparisons.json' % ordinal),row)
                    del reference
                if agent._executed_ce_trace is not None:
                    trace_row = agent._executed_ce_trace.rows[ordinal-1]
                    require(agent._executed_ce_trace.consumed == ordinal and trace_row['numerical_capture_complete'] and
                            trace_row['optimizer_outcome'] == ('amp_skipped' if outcome == 'amp_skipped' else 'applied_admission'),
                            'Enabled trace did not retain this actual consumed outcome')
                    arrays = trace_row['arrays']
                    torch.testing.assert_close(torch.from_numpy(arrays['ce']),
                        -(torch.from_numpy(arrays['projected_target'])*torch.from_numpy(arrays['taken_action_log_probabilities'])).sum(1),
                        **ctx.lock['tolerances']['ce'])
                    row['trace_outcome_joined'] = True
                row['status'] = 'COMPLETE'
                write_json(ctx.paths['root'] / ('attempt-%02d.json' % ordinal),row)
                rows.append(dict(index=ordinal,outcome=outcome,status='COMPLETE',adam_steps=after['steps'],
                                 scaler=after['scaler'],clocks=clocks(ctx)))
                del payload
            except BaseException as error:
                failure = dict(index=ordinal,status='INCOMPLETE_OR_INVALID',error=repr(error),traceback=traceback.format_exc(),
                               before=before,after=ctx.current.get('after'),observed_keys=list(ctx.current))
                try:
                    if 'gradients' in ctx.current:
                        failure['native_failure_evidence'] = save_tensors(ctx,ctx.paths['root'] /
                            ('attempt-%02d.failure.pt'%ordinal),ctx.current)
                    write_json(ctx.paths['root'] / ('attempt-%02d.failure.json'%ordinal),failure)
                except BaseException as persistence:
                    print('Failure-evidence persistence error: '+repr(persistence),file=sys.stderr,flush=True)
                raise  # original learner/validation failure; never a ninth retry
            finally:
                if lease is not None: lease.release()
                ctx.current = None
        require(any(row['outcome']=='applied' for row in rows), 'All8 were AMP-skipped; actual applied behavior unvalidated')
        require(sum(ctx.compile_counters['graph_break'].values())==0 and ctx.compile_counters['stats']['unique_graphs']==2,
                'Actual steps caused graph break/fallback/recompile')
        if agent._executed_ce_trace is not None:
            trace = agent._executed_ce_trace
            require(trace.consumed==len(trace.rows)==8 and not trace.want_draw() and not trace.errors and
                    not (trace.directory/'attempt-09.json').exists(), 'Trace cap/error contract failed')
            require(json.loads((trace.directory/'status.json').read_text())['numerical_captures_complete'], 'Eight trace payloads incomplete')
        require(ctx.parent.stable_file(ctx.trained,ctx.lock['checkpoint']['sha256'],ctx.lock['checkpoint']['bytes']) ==
                ctx.manifest['trained_fixture']['copied'], 'Trained private fixture changed')
        for name, record in ctx.input_files.items():
            require(ctx.parent.digest(ctx.layout.output/'inputs'/name)==record['sha256'], 'Frozen input changed')
        modules_private(ctx)
        ctx.base.verify_source_copies(ctx.layout,ctx.manifest['sources'])
        return dict(status='PARITY_COMPLETE' if ctx.variant=='on' else 'VARIANT_COMPLETE',variant=ctx.variant,
            input_manifest_sha256=ctx.input_description_sha256,source_lock_sha256=ctx.parent.digest(HERE/'source-lock.json'),
            attempts=rows,references=references,actual_applied=sum(row['outcome']=='applied' for row in rows),
            peak_cuda_allocated=torch.cuda.max_memory_allocated(0),peak_cuda_reserved=torch.cuda.max_memory_reserved(0),
            effective_gil_after_compile=getattr(sys,'_is_gil_enabled',lambda:None)(),
            actual_gpu_full_step_diagnostic_route=False,static_both_diagnostic_flags_warmed=True,
            scope='Private persisted bounded synthetic batch repeated8times; actual CUDA full-step observer control, no live8/quality/learning claim')
    finally:
        torch.nn.utils.clip_grad_norm_ = original_clip
        if producer is not None:
            require(producer.close(timeout=10.) and not producer._thread.is_alive(), 'Owned CUDA producer did not join')
        torch.cuda.synchronize(0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--variant',required=True,choices=('base','off','on'))
    args = parser.parse_args(argv)
    ctx = None
    try:
        ctx = bootstrap(args.manifest,args.variant)
        setup(ctx)
        result = observe_steps(ctx)
        write_json(ctx.paths['root']/'phase-result.json',result)
        return 0
    except BaseException as error:
        if ctx is not None:
            try:
                write_json(ctx.paths['root']/'phase-failure.json',dict(status='INCOMPLETE_OR_INVALID',
                    error=repr(error),traceback=traceback.format_exc(),variant=ctx.variant))
            except BaseException as persistence:
                print('Phase-failure receipt error: '+repr(persistence),file=sys.stderr,flush=True)
        traceback.print_exc()
        return 1


if __name__=='__main__':
    raise SystemExit(main())
