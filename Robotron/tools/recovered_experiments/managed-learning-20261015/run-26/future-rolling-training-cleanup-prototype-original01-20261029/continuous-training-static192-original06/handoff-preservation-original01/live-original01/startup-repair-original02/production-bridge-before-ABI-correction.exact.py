"""Explicit continuous MAIN startup hold; inert until called by held main.

No managed measurement, save, source install, actor launch or network listener
is created here. Root alone supplies actual stopped proof and one-use release.
The learner/prefetch were disabled before their construction by the paired
agent source. Exact restoration is compared under both original locks before
the first optimizer attempt; the locks remain held until Root releases them.
"""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

MODE = 'CONTINUOUS_TRAIN155_EVAL37_ONCE'
TOOLS_SHA = '3ab7c6a018afce917bd1199ec9d09b5d3041936d638cdf17f91514006685faf7'


def require(value, reason):
    if not value:
        raise RuntimeError('Controlled startup: ' + reason)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def checked_bytes(value, *, immutable=True, limit=4 << 20):
    require(type(value) is dict and set(value) == {'path', 'sha256', 'bytes', 'identity'},
            'Exact full8 selected file required')
    path = Path(value['path'])
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(),
            'Canonical regular selected file required')
    require(0 < value['bytes'] <= limit, 'Bounded selected file required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and identity(info) == value['identity']
                and info.st_uid == os.getuid() and info.st_nlink == 1
                and (not immutable or stat.S_IMODE(info.st_mode) == 0o444),
                'Selected immutable file identity differs')
        raw = stream.read(limit + 1)
        require(len(raw) == value['bytes'] and hashlib.sha256(raw).hexdigest() == value['sha256']
                and identity(os.fstat(stream.fileno())) == value['identity']
                and identity(path.lstat()) == value['identity'], 'Selected file changed during read')
    return raw


def read(value):
    return json.loads(checked_bytes(value))


def publish(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    require(len(raw) <= 4 << 20, 'Bounded immutable startup receipt required')
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    info = path.stat()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=identity(info))


def unit_owner(unit):
    raw = subprocess.check_output(['systemctl', '--user', 'show', unit], text=True, timeout=5)
    values = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    wanted = dict(Id=unit, MainPID=str(os.getpid()), Type='exec', ActiveState='active',
                  SubState='running', Restart='no', NRestarts='0')
    require(all(values.get(k) == v for k, v in wanted.items())
            and re.fullmatch('[0-9a-f]{32}', values.get('InvocationID', '')),
            'Exact new owned trainer MainPID/unit/invocation required')
    proc = Path('/proc', str(os.getpid()))
    fields = (proc/'stat').read_text().rsplit(')', 1)[1].split()
    groups = (proc/'cgroup').read_text().splitlines()
    require(len(groups) == 1 and groups[0] == '0::' + values['ControlGroup']
            and proc.stat().st_uid == os.getuid(), 'Actual trainer birth/cgroup/UID differs')
    return dict(pid=os.getpid(), birth=int(fields[19]), unit=unit,
        invocation_id=values['InvocationID'], cgroup=values['ControlGroup'], uid=os.getuid())


def cpu_tree(value, torch):
    if isinstance(value, torch.Tensor):
        return value.detach().cpu()
    if isinstance(value, dict):
        return {key: cpu_tree(item, torch) for key, item in value.items()}
    if type(value) in (list, tuple):
        return type(value)(cpu_tree(item, torch) for item in value)
    return value


def live_scalars(agent, metrics, cfg, engine_version):
    with metrics.lock:
        return dict(training_steps=agent.training_steps, optimized_samples=int(agent.optimized_samples),
            baseline_batch_size=int(agent.baseline_batch_size), last_target_update_samples=int(agent.last_target_update_samples),
            frame_count=int(metrics.frame_count), learner_frame_count=int(metrics.learner_frame_count),
            measurement_frame_count=int(metrics.measurement_frame_count), total_training_steps=int(metrics.total_training_steps),
            expert_ratio=float(metrics.expert_ratio), epsilon=float(metrics.epsilon), engine_version=engine_version,
            lr_anchor_step=float(agent.lr_anchor_step), lr_gear=str(agent.lr_gear), state_size=agent.state_size,
            single_frame_state_size=int(getattr(cfg, 'single_frame_state_size', agent.state_size)),
            frame_stack=int(getattr(cfg, 'frame_stack', 1)))


def no_training_attempts(agent, metrics):
    require(agent._continuous_startup_held is True and agent.training_enabled is False
            and metrics.training_enabled is False and metrics.measurement_active is False
            and metrics.ratchet_frozen is False, 'Actual before-workers hold disappeared')
    require(agent._learning_optimizer_exposure is not None, 'Actual optimizer accounting required')
    optimizer = agent._learning_optimizer_exposure.snapshot()
    require(agent.memory._insert_exposure is not None, 'Actual replay accounting required')
    # Caller already holds the non-reentrant replay lock. No nested getter.
    replay = agent.memory._insert_exposure.snapshot()
    # available=False is the actual exposure ABI before its first outcome.
    # Exact zero counters distinguish it from an unknown failed attempt.
    require(optimizer['enabled'] is True and optimizer['available'] is False
            and optimizer['process_id'] == replay['process_id'] == os.getpid()
            and optimizer['epoch'] == replay['epoch'] == 1
            and optimizer['epoch_reason'] == 'optimizer_restore_begin'
            and replay['epoch_reason'] == 'directory_adopt_begin'
            and all(optimizer['total'][k] == 0 for k in
                    ('attempts_started', 'outcomes_recorded', 'applied', 'amp_skipped', 'unavailable'))
            and optimizer['unclassified_started_total'] == 0
            and replay['enabled'] is replay['available'] is True and replay['accepted_total'] == 0,
            'An optimizer attempt or replay insertion occurred before restoration proof')
    return dict(optimizer=optimizer, replay=replay)


def compare_payload(agent, metrics, cfg, manifest, tools, torch):
    expected = manifest['checkpoint_payload']
    actual = dict(online_state_dict=agent.online_net.state_dict(), target_state_dict=agent.target_net.state_dict(),
                  optimizer_state_dict=agent.optimizer.state_dict(), grad_scaler_state_dict=agent.grad_scaler.state_dict())
    require(set(expected) == set(actual), 'Exact full model/Adam/scaler key set required')
    for key, value in actual.items():
        require(tools.typed_tree(cpu_tree(value, torch), torch) == expected[key],
                'Restored full payload differs before first update: ' + key)
    module = sys.modules[agent.__class__.__module__]
    scalars = live_scalars(agent, metrics, cfg, getattr(module, 'ENGINE_VERSION'))
    require(tools.typed_tree(scalars, torch) == tools.typed_tree(manifest['saved_scalars'], torch),
            'Restored clocks/geometry/LR gear/scalars differ')
    phase = copy.deepcopy(manifest['priority_metric_phase'])
    phase['last_resume_record_sha256'] = os.environ['DQN_PRIORITY_PHASE_RECORD_SHA256']
    require(tools.typed_tree(agent._priority_phase.snapshot(), torch) == tools.typed_tree(phase, torch),
            'CE phase/founder/counters differ beyond exact new resume record')
    require(agent.loaded_training_steps == scalars['training_steps']
            and agent.loaded_optimized_samples == scalars['optimized_samples']
            and metrics.loaded_frame_count == scalars['frame_count']
            and metrics.loaded_measurement_frame_count == scalars['measurement_frame_count']
            and metrics.loaded_optimized_samples == scalars['optimized_samples'],
            'Actual loaded budget anchors differ from saved clocks')
    return scalars


def compare_loaded_replay(memory, manifest, tools, np):
    """Caller holds memory.lock. No helper may reacquire that non-reentrant lock."""
    stopped = manifest['ring_and_banks']; ring = stopped['ring']
    require(str(Path(memory._mmap_dir).resolve(strict=True)) == ring['directory']['path']
            and memory.capacity == 6000000 and memory.size == ring['meta']['size'] == 6000000
            and memory.tree.data_ptr == ring['meta']['ptr']
            and memory.tree.max_priority == ring['meta']['max_priority']
            and memory._continuous_exact_resume_consumed is True,
            'Exact full stopped ring adoption failed')
    specs = memory._storage_specs()
    require(set(specs) | {'priorities'} == set(ring['arrays']), 'Exact ten original ring storage fields required')
    for name, (attribute, dtype, shape) in specs.items():
        row = ring['arrays'][name]; actual = getattr(memory, attribute)
        require(str(Path(actual.filename).resolve(strict=True)) == row['path']
                and actual.dtype.str == row['dtype'] and list(actual.shape) == row['shape']
                and actual.dtype == dtype and actual.shape == tuple(shape),
                'Ring field is not the original mapped storage: ' + name)
        # Descriptor identity uses the bank-state ABI (size, not fullpin bytes).
        info = Path(row['path']).stat(); expected = row['identity']
        require(info.st_dev == expected['device'] and info.st_ino == expected['inode']
                and info.st_size == expected['size'] and info.st_uid == expected['uid']
                and info.st_nlink == expected['nlink']
                and info.st_mtime_ns == expected['mtime_ns'] and info.st_ctime_ns == expected['ctime_ns']
                and stat.S_IMODE(info.st_mode) == expected['mode'], 'Original ring storage object changed: ' + name)
    fields = set(ring['arrays']) - {'states', 'next_states'}
    require(set(manifest['ring_scalar_payload']) == fields, 'Complete eight scalar replay payloads required')
    for name in fields - {'priorities'}:
        attribute = specs[name][0]
        require(tools.ndarray_payload(getattr(memory, attribute), np)
                == manifest['ring_scalar_payload'][name]['payload'],
                'Loaded scalar replay values differ: ' + name)
    leaves = memory.tree.tree[memory.tree.capacity:memory.tree.capacity + memory.capacity]
    require(tools.ndarray_payload(leaves, np) == manifest['ring_priorities']['payload'],
            'Loaded PER leaf priorities differ from complete stopped priority payload')
    result = {}
    for name, bank in stopped['banks'].items():
        meta = bank['metadata']; scalars = meta['scalars']; lengths = meta['ep_len']
        require(str(Path(getattr(memory, '_' + name + '_dir')).resolve(strict=True)) == bank['directory']['path']
                and getattr(memory, name + '_ep_count') == bank['counts']['episodes']
                and getattr(memory, name + '_total') == bank['counts']['transitions']
                and getattr(memory, '_' + name + '_stride') == scalars['stride'],
                'Loaded bank count/stride differs: ' + name)
        count = bank['counts']['episodes']
        for key in ('ep_len', 'ep_score', 'ep_game', 'ep_level'):
            require(getattr(memory, name + '_' + key)[:count].tolist() == meta[key],
                    'Loaded complete bank episode metadata differs: ' + name + '/' + key)
        for scalar, attribute in (('stale_age', '_last_admit_add'),
                                  ('stale_age_normal', '_last_normal_admit_add')):
            require(memory._adds_total - getattr(memory, '_' + name + attribute) == scalars[scalar],
                    'Loaded relative bank admission age differs: ' + name + '/' + scalar)
        for field, entry in manifest['bank_payload'][name]['fields'].items():
            actual = getattr(memory, name + '_' + field)
            require(tools.bank_valid_prefix_payload(actual, lengths, scalars['stride'], np) == entry['valid_prefix'],
                    'Loaded bank valid payload differs: ' + name + '/' + field)
        result[name] = dict(episodes=count, transitions=bank['counts']['transitions'],
                           all_valid_field_payloads_and_episode_metadata_equal=True)
    return dict(full_original_mmap_adoption=True, all_eight_scalar_replay_payloads_equal=True,
                all_PER_leaf_priorities_equal=True, banks=result,
                ring_states_and_next_states_fully_hashed=False,
                derived_indexes_rebuilt_from_persisted_rows_not_bitwise_trajectory=True)


def verify_restoration_and_wait(agent, metrics, checkpoint_path):
    require(os.environ.get('ROBOTRON_CONTINUOUS_TRAINING_MODE') == '1'
            and os.environ.get('ROBOTRON_CONTINUOUS_STARTUP_HOLD') == '1', 'Explicit MAIN hold mode required')
    job_path = Path(os.environ['ROBOTRON_CONTINUOUS_STARTUP_JOB'])
    raw = job_path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == os.environ['ROBOTRON_CONTINUOUS_STARTUP_JOB_SHA256'],
            'Exact immutable Root startup job required')
    info = job_path.stat(); job_pin = dict(path=str(job_path), sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw), identity=identity(info)); job = read(job_pin)
    require(job['schema'] == 'robotron-continuous-main-before-update-startup-hold-job-v1'
            and job['mode'] == MODE and job['original_attempt'] == 1 and job['no_retry'] is True,
            'One fresh Root startup hold selection required')
    for entry in job['source_pins']:
        checked_bytes(entry, immutable=False)
    selected_sources = {entry['path']: entry for entry in job['source_pins']}
    for module_name in (__name__, agent.__class__.__module__, agent.memory.__class__.__module__,
                        'dqn.main', 'dqn.config'):
        module = sys.modules.get(module_name)
        require(module is not None and str(Path(module.__file__).resolve(strict=True)) in selected_sources,
                'Actual installed module is not a held startup source: ' + module_name)
    require(not os.getenv('LD_PRELOAD') and not os.getenv('ROBOTRON_TRAINING_ROUND_STATUS'),
            'No Python preload or stale old-round dashboard feed in the new trainer')
    owner = unit_owner(job['unit'])
    manifest = read(job['restoration_manifest']); report = read(job['stopped_CPU_report'])
    require((owner['pid'], owner['birth']) != (manifest['owner']['pid'], manifest['owner']['starttime_ticks']),
            'Old stopped trainer incarnation cannot serve as the new held owner')
    require(manifest['schema'] == 'robotron-stopped-full-training-state-restoration-manifest-v1'
            and manifest['status'] == 'VERIFIED_STOPPED_STATE' and report['status'] == 'PASS'
            and report['restoration_manifest'] == job['restoration_manifest']
            and report['original_job'] == manifest['original_job'], 'Closed stopped verification/manifest join differs')
    authority = read(job['stopped_state_authority'])
    require(authority['schema'] == 'robotron-root-closed-stopped-full-state-startup-authority-v1'
            and authority['CPU_report'] == job['stopped_CPU_report']
            and authority['restoration_manifest'] == job['restoration_manifest']
            and authority['original_CPU_exit'] == 0 and authority['all_original_CPU_resources_closed'] is True
            and authority['old_trainer_and_population_closed'] is True,
            'Actual independently closed stopped-state authority required')
    require(job['checkpoint']['sha256'] == manifest['checkpoint']['sha256']
            and job['checkpoint']['bytes'] == manifest['checkpoint']['bytes']
            and str(Path(checkpoint_path).resolve(strict=True)) == job['checkpoint']['path'],
            'Actual canonical restore checkpoint differs from stopped bytes')
    # Read-only full checkpoint digest; no torch.load or model mutation here.
    path = Path(checkpoint_path)
    require(path.resolve(strict=True) == path and not path.is_symlink(), 'Canonical restore checkpoint required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = identity(os.fstat(stream.fileno())); digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode) and before['uid'] == os.getuid()
                and before['nlink'] == 1 and before == job['checkpoint']['identity'] == identity(os.fstat(stream.fileno()))
                == identity(path.stat()) and digest == job['checkpoint']['sha256'], 'Restored checkpoint changed')
    entry = manifest['manifest_tools']
    require(isinstance(TOOLS_SHA, str) and len(TOOLS_SHA) == 64 and entry['sha256'] == TOOLS_SHA,
            'Frozen shared restoration descriptor source required')
    code = checked_bytes(entry); spec = importlib.util.spec_from_file_location('_continuous_restore_tools', entry['path'])
    tools = importlib.util.module_from_spec(spec); exec(compile(code, entry['path'], 'exec'), tools.__dict__)
    require(job['resume_record']['sha256'] == os.environ['DQN_PRIORITY_PHASE_RECORD_SHA256']
            and job['resume_record']['path'] == os.environ['DQN_PRIORITY_PHASE_RECORD'],
            'Actual new exact resume record required')
    read(job['resume_record'])
    import torch
    import numpy as np
    from .config import RL_CONFIG
    root = Path(job['output_directory'])
    require(root.is_absolute() and root.resolve(strict=False) == root and not root.exists(),
            'Fresh owned startup hold output required')
    root.mkdir(mode=0o700)
    with agent._training_lock, agent.memory.lock:
        exposure = no_training_attempts(agent, metrics)
        scalars = compare_payload(agent, metrics, RL_CONFIG, manifest, tools, torch)
        replay = compare_loaded_replay(agent.memory, manifest, tools, np)
        require(unit_owner(job['unit']) == owner, 'Original startup owner changed during exact verification')
        held = publish(root/'verified-held-before-first-update.json', dict(
            schema='robotron-continuous-main-held-exact-restoration-report-v1', status='VERIFIED_HELD_BEFORE_FIRST_UPDATE',
            original_job=job_pin, owner=owner, checkpoint=job['checkpoint'], restoration_manifest=job['restoration_manifest'],
            stopped_CPU_report=job['stopped_CPU_report'], all_online_target_Adam_scaler_payloads_equal=True,
            optimizer_implementation_flags_exactly_equal=True, saved_scalars=scalars, replay=replay, exposure=exposure,
            training_and_memory_locks_held_until_Root_release=True, dashboard_and_GAME_listener_not_created=True,
            optimizer_attempts_before_release=0, new_replay_inserts_before_release=0,
            RNG_or_episode_maps_restored=False, scientific_launch_qualified=False))
        print(json.dumps(dict(phase='CONTINUOUS_STARTUP_VERIFIED_HELD', report=held)), flush=True)
        release_path = Path(job['release_path'])
        require(release_path.parent == root and release_path.name == 'ROOT-release.json', 'Exact private one-use release path required')
        # Root publishes an already-fsynced0444 staging file by exclusive
        # link/unlink. The brief2-link publication interval is still held,
        # never treated as a valid release or as permission to train.
        while (not release_path.exists() or release_path.lstat().st_nlink != 1
               or stat.S_IMODE(release_path.lstat().st_mode) != 0o444):
            time.sleep(.2)
        release_raw = release_path.read_bytes(); release_pin = dict(path=str(release_path),
            sha256=hashlib.sha256(release_raw).hexdigest(), bytes=len(release_raw), identity=identity(release_path.stat()))
        release = read(release_pin)
        require(release['schema'] == 'robotron-root-continuous-startup-one-use-release-v1'
                and release['owner'] == owner and release['original_job'] == job_pin
                and release['held_report'] == held and release['checkpoint'] == job['checkpoint']
                and release['allow_training'] is True, 'Root release does not bind exact verified owner/state')
        require(unit_owner(job['unit']) == owner, 'Original startup owner changed before one-use release')
        no_training_attempts(agent, metrics)
        for entry in job['source_pins']:
            checked_bytes(entry, immutable=False)
        publish(root/'release-consumed.json', dict(schema='robotron-continuous-startup-release-consumed-v1',
            owner=owner, original_job=job_pin, held_report=held, Root_release=release_pin,
            no_optimizer_or_replay_work_before_release=True))
        with metrics.lock:
            metrics.training_enabled = True
        agent._continuous_startup_held = False
        agent.training_enabled = True


if __name__ == '__main__':
    print('SOURCE_ONLY_INERT_NO_READS_OR_ACTIONS')
