#!/usr/bin/env python3
"""SOURCE-ONLY fixed attempt01 original4-versus-conditional5 route diagnostic.

Default prints a literal plan without helper/source/data reads or live queries.
Future --launch requires a separately reviewed exclusive resource window and a
dedicated delegated robotron-snapshot-smoke-*.service. It does not train the
live agent, alter its sources or repair failed observations.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import uuid


HERE = Path(__file__).parent
GAME = HERE.parents[3]
REPO = GAME.parent
SCHEMA = 'robotron-raw-kl-stage-a-numeric-validation-v1'
SEED = 20261017
VARIANTS = ('stage_a',)
GIB, MIB = 1 << 30, 1 << 20
BOUNDS = dict(cpu_threads=2, memory_bytes=16*GIB, vram_allocator_bytes=12*GIB,
              vram_process_bytes=13*GIB, artifact_bytes=6*GIB, tmpfs_bytes=128*MIB,
              tasks=128, phase_timeout_s=180, total_timeout_s=600)
SOURCE_LOCK_SHA256 = 'bcc1c696ed1ddbd18879e64cee01d55909b99c8401d908f636228d4c83b36551'
LOCK_SHA = SOURCE_LOCK_SHA256
BLOCKED_NAMES = {
    'cuda_trace_parent.py', 'cuda_trace_worker.py', 'checkpoint_at_frame.py',
    'cpu_reservation_trial.py', 'forensic_parent.py', 'forensic_worker.py',
    'whole_agent_smoke.py', 'whole_agent_smoke_worker.py',
    'restore_serial_after_parallel_trial.py',
}
_BASE = None


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sync_directory(path):
    descriptor = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def storage_directory_identity(path):
    info = Path(path).lstat()
    require(stat.S_ISDIR(info.st_mode), 'Storage boundary is not a nonsymlink directory: ' + str(path))
    return dict(device=info.st_dev, inode=info.st_ino)


def owned_byte_count(root, expected_identity, *, volatile_caches=(), events=None, observer=None):
    """Count owned files without following links or hiding scientific I/O loss.

    Only declared compiler-cache churn and the pinned ON observer's exact
    atomic JSON publication paths are tolerated. Persistent scientific loss
    remains fatal. All observed directory boundaries must survive unchanged.
    This remains a cooperative, non-atomic storage observation, not a quota.
    """
    root = Path(root)
    caches = [(Path(path), identity) for path, identity in volatile_caches]
    require(root.is_absolute(), 'Storage root must be absolute')
    for path, identity in caches:
        require(path != root and path.is_relative_to(root), 'Volatile cache must be strictly inside owned root')
    observer_path = Path(observer['path']) if observer is not None else None
    if observer_path is not None:
        require(observer_path != root and observer_path.is_relative_to(root), 'Observer must be strictly inside owned root')
    observer_temporaries = {'context.json.tmp', 'status.json.tmp'} | {
        'attempt-%02d.json.tmp' % index for index in range(1, 9)}

    def pin_observer(info=None):
        if observer is None:
            return
        if info is None:
            try:
                info = observer_path.lstat()
            except OSError as error:
                if error.errno == errno.ENOENT and observer['identity'] is None:
                    return  # Session has not created its NEW directory yet.
                raise
        require(stat.S_ISDIR(info.st_mode), 'Observer boundary is not a nonsymlink directory')
        identity = dict(device=info.st_dev, inode=info.st_ino)
        if observer['identity'] is None:
            observer['identity'] = identity
        require(identity == observer['identity'], 'Observer directory identity changed')

    def boundaries():
        require(storage_directory_identity(root) == expected_identity, 'Owned storage root identity changed')
        for path, identity in caches:
            require(storage_directory_identity(path) == identity, 'Active compiler-cache boundary changed')
        pin_observer()

    def cache_for(path):
        return next((cache for cache, identity in caches if path != cache and path.is_relative_to(cache)), None)

    def vanished(path, error, *, regular=None):
        if error.errno == errno.ENOENT:
            cache = cache_for(path)
            if cache is not None:
                if events is not None:
                    events['ignored_enoent'] = events.get('ignored_enoent', 0) + 1
                    events['last_relative_path'] = str(path.relative_to(cache))
                    events['last_cache_root'] = str(cache)
                return True
            if (observer is not None and observer['identity'] is not None and regular is not False
                    and path.parent == observer_path and path.name in observer_temporaries):
                observer['ignored_temp_enoent'] = observer.get('ignored_temp_enoent', 0) + 1
                observer['last_temp_name'] = path.name
                return True
        return False

    def inspect(parent_fd, name, path, *, previous=None):
        try:
            return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as error:
            if vanished(path, error, regular=None if previous is None else stat.S_ISREG(previous.st_mode)):
                return None
            raise

    def walk(descriptor, path):
        try:
            with os.scandir(descriptor) as iterator:
                entries = list(iterator)
        except OSError as error:
            if vanished(path, error, regular=False):
                return 0
            raise
        total = 0
        for entry in entries:
            child = path / entry.name
            info = inspect(descriptor, entry.name, child)
            if info is None:
                continue
            require(not stat.S_ISLNK(info.st_mode), 'Unexpected symlink in owned artifacts: ' + str(child))
            if child == observer_path:
                pin_observer(info)
            if stat.S_ISDIR(info.st_mode):
                try:
                    nested = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                except OSError as error:
                    if vanished(child, error, regular=False):
                        continue
                    raise
                try:
                    opened = os.fstat(nested)
                    require((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino),
                            'Storage directory replaced during traversal: ' + str(child))
                    size = walk(nested, child)
                finally:
                    os.close(nested)
            elif stat.S_ISREG(info.st_mode):
                size = info.st_size
            else:
                size = 0  # Same accounting as the pinned watcher for other file types.
            after = inspect(descriptor, entry.name, child, previous=info)
            if after is None:
                continue
            require(not stat.S_ISLNK(after.st_mode), 'Unexpected symlink in owned artifacts: ' + str(child))
            if (after.st_dev, after.st_ino) != (info.st_dev, info.st_ino):
                regular_pair = stat.S_ISREG(info.st_mode) and stat.S_ISREG(after.st_mode)
                cache = cache_for(child)
                if regular_pair and cache is not None:
                    if events is not None:
                        events['regular_cache_replacements'] = events.get('regular_cache_replacements', 0) + 1
                        events['last_cache_replacement_relative_path'] = str(child.relative_to(cache))
                        events['last_cache_root'] = str(cache)
                elif (regular_pair and observer is not None and observer['identity'] is not None
                      and child.parent == observer_path and child.name in ('status.json', 'status.json.tmp')):
                    field = 'status_replacements' if child.name == 'status.json' else 'status_tmp_replacements'
                    observer[field] = observer.get(field, 0) + 1
                else:
                    raise RuntimeError('Storage entry replaced during traversal: ' + str(child))
            total += max(size, after.st_size) if stat.S_ISREG(info.st_mode) else size
        return total

    boundaries()
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        require(dict(device=opened.st_dev, inode=opened.st_ino) == expected_identity,
                'Owned storage root changed before open')
        total = walk(descriptor, root)
        boundaries()
        return total
    finally:
        os.close(descriptor)


def scan_quality_processes(base, *, proc_root=Path('/proc'), allowed_pids=(), observations):
    """Preserve the pinned classifier; skip only vanished UNCLASSIFIED reads.

    Once argv matches a blocked name, any identity-read failure is fatal. A
    permission or other I/O failure never becomes evidence that a PID vanished.
    """
    blocked = []
    allowed = set(allowed_pids)
    for entry in Path(proc_root).iterdir():
        if not entry.name.isdigit() or int(entry.name) in allowed:
            continue
        try:
            raw = (entry/'cmdline').read_bytes()
        except OSError as error:
            if error.errno in (errno.ENOENT, errno.ESRCH):
                observations['unclassified_cmdline_disappearances'] += 1
                observations['last_pid'] = int(entry.name)
                observations['last_errno'] = error.errno
                continue
            if isinstance(error, PermissionError):
                raise RuntimeError('Cannot establish process ownership: ' + entry.name) from error
            raise
        words = [part.decode(errors='replace') for part in raw.split(b'\0') if part]
        names = [Path(word).name for word in words]
        if any(name in base.QUALITY_NAMES or name.startswith('benchmark_') or
               word.rsplit('.',1)[-1]+'.py' in base.QUALITY_NAMES or
               word.rsplit('.',1)[-1].startswith('benchmark_') for name, word in zip(names, words)):
            try:
                identity = base.identity(int(entry.name), proc_root)
            except OSError as error:
                raise RuntimeError('Classified blocked process identity failed PID' + entry.name) from error
            blocked.append(dict(identity=identity, command=words))
    return blocked


def checked_module(path, expected, name):
    """Execute only verified helper bytes, exclusively on the explicit path."""
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink()
            and path.is_file(), 'Pinned helper path is not a canonical regular file')
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == expected, 'Pinned helper bytes differ: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


def read_lock():
    path = HERE / 'source-lock.json'
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink(), 'Noncanonical source lock')
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == SOURCE_LOCK_SHA256, 'Reviewed source lock changed')
    lock = json.loads(data)
    require(lock['schema'] == SCHEMA and lock['seed'] == SEED and lock['variants'] == list(VARIANTS)
            and lock['attempts'] == 1 and lock['retained_acquisition_attempts'] == 8
            and lock['actual_training_attempts'] == 0 and lock['conditional_forwards'] == 0 and lock['original4_forwards'] == 1
            and lock['candidate_default_forwards'] == lock['candidate_kl_forwards'] == 1
            and lock['explicit_worker_backward_calls'] == 3 and lock['optimizer_steps'] == 0
            and lock['compiled_loss_outputs'] == 4
            and lock['offline_outputs'] == 5 and lock['qualification_pass'] is False
            and lock['batch_rows'] == 4096
            and lock['state_width'] == 11128 and lock['joint_actions'] == 81 and lock['atoms'] == 51,
            'Fixed trace validation protocol changed')
    require('checkpoint' not in lock and 'fixture_recipe' not in lock
            and lock['tolerances']['ce'] == dict(rtol=2e-4,atol=2e-5)
            and lock['reconstruction_policy']['attempt_indices'] == [1]
            and lock['reconstruction_policy']['forward_routes'] == ['original4','candidate_ce4','candidate_kl5']
            and lock['reconstruction_policy']['diagnostics_indices'] == [], 'Live8 population/tolerance changed')
    for group in ('immutable_helpers', 'source_files', 'candidate_science_files'):
        for name, item in lock[group].items():
            if group == 'source_files':
                require(name == Path(name).name and name not in ('', '.', '..'), 'Private source name escapes package')
            source = Path(item['source'])
            require(source.is_absolute() and source == source.resolve() and not source.is_symlink()
                    and source.is_file() and digest(source) == item['sha256'], 'Pinned source changed: ' + name)
    for name, expected in (
            ('frozen_science_helpers', 'ba0039d406676f092309c6bf2248ddcf169af8960f60ed18b698ece1ea602f93'),
            ('original_numeric_lock', 'd6ffdaae63d97bce24a18d1b11ed165b9e12484d17d65365415aab3c08beb13b'),
            ('conditional_helpers','53ab48313f79bc6cdae6ba2ab70969a229ec478ff94b7d52a331c8c64dd37464'),
            ('acquisition_audit','5c73ef6520c36ff26ddf7334782ae7407692c566f4d526d24e087c6725feaaf4'),
            ('reconstruction_helpers','182f008a969f55c2aa5952612f1631b3435cab61cbc5ae42fcd708c4f91a03a7'),
            ('predecessor_parent','02af5b4ab846c1fe2579ceeba4ceabff8f05a4686c6debe490df56c1978779ba'),
            ('prior_conditional8_result','29e9befde24e973573751b0dd65d8e5e6f7eed81ac560d32ab1242b75b564a86'),
            ('prior_conditional8_cleanup_review','34ec366eeef3a52285946930663eea1bc60ae5b24e90737495b77c60b1a441c8')):
        item = lock[name]
        source = Path(item['source'])
        require(item['sha256'] == expected and source.is_absolute() and source == source.resolve()
                and not source.is_symlink() and source.is_file() and digest(source) == expected,
                'Pinned science helper/numeric lock changed: ' + name)
    review = lock['observer_review']
    source = Path(review['source'])
    require(source.is_absolute() and source == source.resolve() and not source.is_symlink()
            and digest(source) == review['sha256'], 'Reviewed observer manifest changed')
    for name, item in json.loads(source.read_text())['files'].items():
        require(name == Path(name).name and digest(source.parent/name) == item['sha256'],
                'Reviewed observer source/test changed: ' + name)
    require(lock['original_loss_sha256'] == 'de9621e3d926a8f49f230f9e271c645a7498d38445622d6ae2761ab2bbd7253a'
            and lock['offline_loss_sha256'] == 'ce527c840f1b0cce3f77fece52923c7023519605db92d7c5e691b1b573ee6d2f',
            'Original4 or conditional offline5 source differs')
    for name in ('route_helpers', 'guard_predecessor', 'raw_kl_bundle', 'raw_kl_fixture_companion'):
        item = lock[name]; source = Path(item['source'])
        require(source.is_absolute() and source == source.resolve() and not source.is_symlink()
                and source.is_file() and digest(source) == item['sha256'], 'Stage A source pin changed: '+name)
    require(lock['raw_kl_bundle']['sha256']=='1144139f168292b7c0648fcc76d24a945d7d7f295ec14d5f304f70d5ca5dfe11'
            and lock['raw_kl_fixture_companion']['sha256']=='2f083c4327540380498f10f7e3274b7cd1c9a1c2d4c54d9f5f8262cfbb2afd9a'
            and lock['stage_a']['routes']==['original4','candidate_ce4','candidate_kl5']
            and lock['stage_a']['forwards']==lock['stage_a']['explicit_unscaled_backwards']==3
            and lock['stage_a']['max_target_mass_error']==1e-5
            and lock['stage_a']['minimum_signed_kl']==-1e-5
            and lock['stage_a']['stage_b_required_before_adoption'] is True, 'Stage A fixed science policy changed')
    return lock


def helpers(lock):
    global _BASE
    launcher = lock['immutable_helpers']['launcher']
    worker = lock['immutable_helpers']['worker']
    base = checked_module(launcher['source'], launcher['sha256'], '_ce_trace_owned_launcher')
    old_worker = checked_module(worker['source'], worker['sha256'], '_ce_trace_lifetime_worker')
    # These reviewed FUNCTIONS are reused; no old source_manifest/launch/setup
    # or old snapshot numerical policy is called.
    base.GAME, base.REPO, base.BOUNDS = GAME, REPO, dict(BOUNDS)
    base.QUALITY_NAMES = set(base.QUALITY_NAMES) | BLOCKED_NAMES
    base.process_scan_observations = dict(unclassified_cmdline_disappearances=0, last_pid=None, last_errno=None)
    base.scan_quality_processes = lambda **kwargs: scan_quality_processes(
        base, observations=base.process_scan_observations, **kwargs)
    original_guard = base.guard_live_resources
    last_logged = 0

    def resource_guard(**kwargs):
        nonlocal last_logged
        try:
            result = original_guard(**kwargs)
        finally:
            count = base.process_scan_observations['unclassified_cmdline_disappearances']
            if count != last_logged:
                print('[PROCESS SCAN] ' + json.dumps(dict(scope='initial unclassified cmdline only',
                    process_id=os.getpid(), **base.process_scan_observations)), file=sys.stderr, flush=True)
                last_logged = count
        if kwargs.get('initial', False):
            require(result['gpu']['devices'][base.GPU0_UUID]['free_bytes'] >= 14*GIB,
                    'GPU0 requires at least14GiB free before numerical import')
        return result

    base.guard_live_resources = resource_guard
    _BASE = base
    return base, old_worker


@dataclass(frozen=True)
class Layout:
    output: Path
    nonce: str
    tmpfs_parent: Path = Path('/dev/shm')

    @property
    def tmpfs(self):
        return self.tmpfs_parent / ('robotron-snapshot-smoke-' + self.nonce)

    @property
    def scripts(self):
        return self.output / 'private/Robotron/Scripts'

    def phase(self, variant):
        require(variant in VARIANTS, 'Unknown fixed variant')
        root = self.output / variant
        return dict(root=root, models=root/'models', control=root/'control.json',
                    journal=root/'journal', tmpfs=self.tmpfs/variant, cache=root/'cache')


def configure_environment(layout, variant):
    require(_BASE is not None, 'Verified helper initialization is required')
    paths = layout.phase(variant)
    environment = _BASE.configure_environment(layout, variant)
    environment.update(DQN_BATCH_SIZE='4096', DQN_TORCH_COMPILE='1', DQN_FULL_LOSS_COMPILE='1',
                       DQN_COHERENT_SNAPSHOT='0', DQN_PER_PRIORITY_METRIC='ce',
                       DQN_NATIVE_BATCH_UPDATE='1', DQN_DIRECT_REPLAY_FILL='1',
                       DQN_COMPILE_MODE='default', DQN_DIAGNOSTIC_INTERVAL='20',
                       PYTHONDONTWRITEBYTECODE='1')
    environment.pop('DQN_EXECUTED_CE_TRACE_DIR', None)
    environment.pop('DQN_RECOMPUTED_CE_CAPTURE_DIR', None)
    return environment


def file_identity(value):
    return dict(device=value.st_dev, inode=value.st_ino, mode=stat.S_IMODE(value.st_mode),
                uid=value.st_uid, gid=value.st_gid, nlink=value.st_nlink,
                size=value.st_size, mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns)


def stable_file(path, expected_sha, expected_bytes=None, *, read_only=True):
    """Hash an owned source with identical FD/path before/after views.

    Model bytes always use the default readonly requirement. The historical
    CPU verifier JSON is an ordinary writable output; its exact pinned hash,
    mode and full identity are retained without changing the original file.
    """
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink(), 'Noncanonical readonly input')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1,
                'Input must be an owned single-link regular file')
        require(not read_only or not stat.S_IMODE(before.st_mode) & 0o222, 'Model input must be readonly')
        identity = file_identity(before)
        require(file_identity(path.lstat()) == identity, 'Input path/FD identity differs before read')
        observed = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(file_identity(os.fstat(stream.fileno())) == identity and file_identity(path.lstat()) == identity,
                'Input changed while fingerprinting')
    require(observed == expected_sha and (expected_bytes is None or identity['size'] == expected_bytes),
            'Input hash/size differs')
    return dict(path=str(path), sha256=observed, bytes=identity['size'], identity=identity)


def bounded_json(record, *, read_only=False):
    require(0 < record['bytes'] <= 2*MIB, 'JSON evidence exceeds bounded metadata size')
    proof = stable_file(record['path'],record['sha256'],record['bytes'],read_only=read_only)
    value = json.loads(Path(record['path']).read_text())
    require(stable_file(record['path'],record['sha256'],record['bytes'],read_only=read_only) == proof,
            'JSON evidence changed during read')
    return value,proof


def payload_metadata(record, directory, index):
    path = Path(record['path'])
    require(path == directory/('attempt-%02d.payload.pt'%index) and path.is_absolute()
            and path == path.resolve() and not path.is_symlink(), 'Payload escaped fixed capture directory')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
            and not stat.S_IMODE(info.st_mode)&0o222 and info.st_size == record['bytes']
            and 0 < info.st_size <= 640*MIB and isinstance(record['sha256'],str)
            and len(record['sha256']) == 64, 'Captured payload metadata differs')
    # Parent binds full metadata only. The numerical worker hashes each full
    # payload before/after weights_only load; no repeated4GB parent guard read.
    return dict(path=str(path),sha256=record['sha256'],bytes=record['bytes'],identity=file_identity(info))


def row_contract(row,index,capture_id):
    require(row['index']==index and row['capture_complete'] is True
            and row['optimizer_outcome']=='applied_admission'
            and row['actual_exposure_delta']==dict(amp_skipped=0,applied=1,attempts_started=1,outcomes_recorded=1,unavailable=0)
            and row['draw_capture_id']==capture_id and row['draw_batch_join_checked'] is True
            and row['staged_draw_join_checked'] is True,'Original complete row/outcome/draw binding differs')
    require(row['backend']==('original_compiled4_diagnostics' if index==7 else 'original_compiled4'),
            'Actual diagnostic route differs')
    prefetch=row['prefetch']
    require(prefetch['current'] is True and prefetch['lease_epoch']==prefetch['owner_epoch_at_consumption'],
            'Original lease was not current')
    expected={name:prefetch[name] for name in ('current','lease_epoch','owner_epoch_at_consumption')}
    require(all(row['prefetch_'+point]==expected for point in ('begin','pre_loss','exit')),
            'Original consumed lease epochs differ')
    require(row['after']['training_steps']==row['before']['training_steps']+1
            and row['after']['optimized_samples']==row['before']['optimized_samples']+4096,
            'Original consumed logical clocks differ')


def bind_inputs(lock):
    item=lock['retained_input_binding']
    data,binding_pin=bounded_json(dict(path=item['source'],sha256=item['sha256'],bytes=item['bytes']))
    require(data['schema']=='robotron-actual-ce-observational-analysis-inputs-v1'
            and data['population']=='live_consecutive_consumed_attempts'
            and data['actual_target_entropy_or_KL_observed'] is False and len(data['attempts'])==8,
            'Actual live8 input manifest differs')
    metadata={};values={}
    for name in ('producer_manifest','acquisition_review','maintenance_result','maintenance_root_job','context','final'):
        values[name],metadata[name]=bounded_json(data[name],read_only=name in ('context','final'))
    context,final=values['context'],values['final']
    require(context['schema']=='robotron-recomputed-ce-capture-v1' and context['loss_abi']==4
            and context['loss_sha256']==lock['original_loss_sha256'] and context['attempts']==8
            and final['status']=='EIGHT_INPUT_CE_CAPTURES_COMPLETE' and final['complete'] is True
            and final['attempts_consumed']==8 and final['observer_errors']==[] and len(final['rows'])==8
            and values['maintenance_result']['status']=='COMPLETE'
            and values['maintenance_result']['capture_complete'] is True
            and values['maintenance_result']['manual_recovery_required'] is False,
            'Complete original live8 acquisition required')
    directory=Path(metadata['context']['path']).parent
    require(Path(metadata['final']['path'])==directory/'final.json','Context/final roots differ')
    rows=[]
    for index,item in enumerate(data['attempts'],1):
        require(Path(item['receipt']['path'])==directory/('attempt-%02d.json'%index), 'Receipt escaped exact index')
        row,row_pin=bounded_json(item['receipt'],read_only=True)
        row_contract(row,index,context['capture_id'])
        require(row==final['rows'][index-1] and all(row['payload'][key]==item['payload'][key]
                for key in ('path','sha256','bytes')),'Original row/final/payload identity differs')
        rows.append(dict(index=index,receipt=row_pin,payload=payload_metadata(item['payload'],directory,index)))
    return dict(input_binding=binding_pin,metadata=metadata,attempts=rows,capture_id=context['capture_id'])


def publish(base, path, value):
    base.json_exclusive(path, value)
    sync_directory(Path(path).parent)


def command(manifest_path, variant):
    return [sys.executable, '-Xgil=0', '-I', '-B', str(HERE/'cuda_trace_worker.py'),
            '--manifest', str(manifest_path), '--variant', variant]


def result_contract(result,variant):
    routes=['original4','candidate_ce4','candidate_kl5']
    require(result.get('status')=='OBSERVATIONS_COMPLETE' and result.get('variant')==variant
            and result.get('qualification_pass') is False and result.get('stage_b_required_before_adoption') is True
            and isinstance(result.get('comparison_pass'),bool)
            and isinstance(result.get('interpretation_requires_review'),bool), 'Stage A identity/scope differs')
    require(result.get('selected_original_index')==1 and result.get('forward_routes')==routes
            and result.get('attempted_forward_routes')==routes and result.get('backward_routes')==routes
            and result.get('explicit_worker_backward_calls')==3 and result.get('actual_attempts_in_this_process')==0,
            'Exactly three predeclared forwards/unscaled backwards required')
    rows=result.get('routes',[]); zero=dict(optimizer_step=0,scaler_step=0,scaler_update=0)
    require([row['route'] for row in rows]==routes and all(row['index']==1
            and row['status']=='OBSERVATIONS_COMPLETE' and row['diagnostics'] is False
            and row['output_arity']==(5 if row['route']=='candidate_kl5' else 4)
            and row['update_guard_counts']==zero and row['model_before']==row['model_after']
            and row['explicit_unscaled_backward_calls']==1 and row['gradients_retained'] is True
            and row['target_all_grads_none'] is True for row in rows), 'All three unchanged-state routes required')
    require(all(row['model_before']==rows[0]['model_before']
            and row['rng_observations']['pre']==rows[0]['rng_observations']['pre'] for row in rows),
            'Same PRE model/RNG required independently')
    comparisons=result.get('comparisons',{})
    require(set(comparisons)=={'original4_vs_captured_actual','candidate_ce4_vs_original4','candidate_kl5_vs_candidate_ce4'}
            and all(isinstance(value['passed'],bool) for value in comparisons.values()), 'Separate comparisons required')
    for name in ('candidate_ce4_vs_original4','candidate_kl5_vs_candidate_ce4'):
        record=comparisons[name]
        require(set(record['fields'])=={'ce','weighted_loss','bc_loss','diagnostic_values','gradients'}
                and record['fields']['ce']['tolerance']==dict(rtol=2e-4,atol=2e-5)
                and all(record['fields'][field]['tolerance']==dict(rtol=2e-3,atol=2e-6)
                        for field in ('weighted_loss','bc_loss','diagnostic_values','gradients'))
                and record['passed']==all(v['passed'] for v in record['fields'].values()), 'Original tolerances/gates differ')
    require(comparisons['original4_vs_captured_actual']['tolerance']==dict(rtol=2e-4,atol=2e-5)
            and result['comparison_pass']==all(comparisons[name]['passed'] for name in
                ('candidate_ce4_vs_original4','candidate_kl5_vs_candidate_ce4'))
            and rows[2]['priority_guard']['passed'] is True, 'Stage A internal pass/priority guard differs')
    require(result['interpretation_requires_review']==(not result['comparison_pass']
            or not comparisons['original4_vs_captured_actual']['passed']
            or any(row['rng_observations']['post_changed'] for row in rows)),
            'Interpretation flag must preserve historical residual and RNG differences')


def run_variant(base, layout, manifest_path, variant, cgroup, main, overall_deadline):
    paths = layout.phase(variant)
    manifest = json.loads(manifest_path.read_text())
    native_cache = manifest['native_compiler_cache']
    require(Path(native_cache['path']) == layout.scripts/'dqn/__pycache__', 'Unexpected native compiler-cache path')
    cache_identity = storage_directory_identity(paths['cache'])
    cache_events = dict(ignored_enoent=0, last_relative_path=None)
    observer = (dict(path=str(paths['root']/'ce-executed-trace-cuda-validation'), identity=None,
                     ignored_temp_enoent=0, last_temp_name=None, status_replacements=0, status_tmp_replacements=0)
                if variant == 'on' else None)
    deadline = min(overall_deadline, time.monotonic() + BOUNDS['phase_timeout_s'])
    process = owned = None
    token_released = False
    launched = time.monotonic()
    with (paths['root']/'worker.log').open('xb') as log:
        try:
            require(time.monotonic() < deadline, 'Fixed overall deadline reached before variant')
            with base.blocked_handled_signals():
                process = subprocess.Popen(command(manifest_path, variant), cwd=layout.output/'private',
                    env=configure_environment(layout, variant), stdin=subprocess.PIPE,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                owned = base.identity(process.pid)
                require(owned['pgid'] == process.pid, 'Worker process group is not isolated')
                cgroup.attach(process.pid)
            base.guard_live_resources(allowed_pids={os.getpid(), process.pid}, expected_main=main)
            process.stdin.write((manifest['launch_token'] + '\n').encode())
            process.stdin.close()
            token_released = True
            next_guard = 0.0
            while process.poll() is None:
                require(time.monotonic() < deadline, 'Fixed variant/overall deadline exceeded')
                require(owned_byte_count(layout.output, manifest['output_identity'],
                            volatile_caches=((paths['cache'], cache_identity),
                                             (Path(native_cache['path']), native_cache['identity'])), events=cache_events,
                            observer=observer) <= BOUNDS['artifact_bytes'] and
                        owned_byte_count(layout.tmpfs, manifest['tmpfs_identity']) <= BOUNDS['tmpfs_bytes'],
                        'Owned storage bound exceeded')
                if time.monotonic() >= next_guard:
                    base.guard_live_resources(allowed_pids={os.getpid(), process.pid}, expected_main=main)
                    next_guard = time.monotonic() + 1
                time.sleep(.1)
            require(process.returncode == 0, 'Worker failed; original log/variant artifacts are retained')
            require(not cgroup.members(), 'Worker left surviving descendants')
        finally:
            # Handler lifetime encloses this block and outer cgroup/tmpfs undo.
            with base.blocked_handled_signals():
                try:
                    if process is not None:
                        if owned is None:
                            # Still-unreaped Popen child received no token, so
                            # its PID cannot have been reused by another owner.
                            if process.stdin and not process.stdin.closed:
                                process.stdin.close()
                            if process.poll() is None:
                                process.terminate()
                            process.wait(timeout=5)
                        elif process.poll() is None or cgroup.members():
                            base.terminate_owned(process, owned, cgroup)
                        else:
                            process.wait(timeout=5)
                finally:
                    if process is not None and process.stdin and not process.stdin.closed:
                        process.stdin.close()
                    if process is not None:
                        publish(base, paths['root']/'child-exit.json', dict(
                            variant=variant, owned_identity=owned, pid=process.pid,
                            actual_returncode=process.returncode, token_released=token_released,
                            elapsed_s=time.monotonic()-launched,
                            compiler_cache_identity=cache_identity, compiler_cache_observations=cache_events,
                            native_compiler_cache=native_cache,
                            observer_storage_observations=observer,
                            parent_process_scan_observations=dict(base.process_scan_observations),
                            scope='Direct owned Popen result; parent service exit retained separately by root'))
    require(time.monotonic() <= overall_deadline, 'Overall deadline exceeded at variant completion')
    result = json.loads((paths['root']/'phase-result.json').read_text())
    result_contract(result,variant)
    return result


def launch(directory):
    require(not any(name.split('.')[0] in ('numpy', 'torch', 'dqn') for name in sys.modules),
            'Fresh stdlib-only parent is required')
    sys.dont_write_bytecode = True
    lock = read_lock()
    base, _ = helpers(lock)
    directory = base.validate_output(directory, logs_root=GAME/'logs')
    with base.installed_signal_handlers():
        overall_deadline = time.monotonic() + BOUNDS['total_timeout_s']
        initial = base.guard_live_resources(allowed_pids={os.getpid()}, initial=True)
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0])*1024 >= 20*GIB, 'Host RAM free margin insufficient')
        require(shutil.disk_usage(directory.parent).free >= 8*GIB and
                shutil.disk_usage('/dev/shm').free >= 256*MIB, 'Disk/tmpfs free margin insufficient')
        delegated = base.cgroup_parent()
        nonce = uuid.uuid4().hex
        layout = Layout(directory, nonce)
        require(not layout.tmpfs.exists(), 'Private tmpfs already exists')
        descriptor = os.open('/dev/shm/robotron-snapshot-smoke-gpu0.lock',
                             os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        lease = os.fdopen(descriptor, 'r+')
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            lease.close()
            raise
        cgroup = root_identity = tmp_identity = None
        results = []
        try:
            base.guard_live_resources(allowed_pids={os.getpid()}, expected_main=initial['main_owners'], initial=True)
            directory.mkdir(mode=0o700)
            root_identity = base.directory_identity(directory)
            layout.tmpfs.mkdir(mode=0o700)
            tmp_identity = base.directory_identity(layout.tmpfs)
            publish(base, directory/'ownership.json', dict(nonce=nonce, parent=base.identity(),
                    output=root_identity, tmpfs=tmp_identity))
            publish(base, layout.tmpfs/'ownership.json', dict(nonce=nonce, parent=base.identity()))
            base.prepare_private_sources(layout, lock['source_files'])
            native_cache_path = layout.scripts/'dqn/__pycache__'
            native_cache_path.mkdir(mode=0o700)
            native_cache = dict(path=str(native_cache_path), identity=storage_directory_identity(native_cache_path))
            retained_inputs = bind_inputs(lock)
            for variant in VARIANTS:
                paths = layout.phase(variant)
                for name in ('root', 'models', 'journal', 'tmpfs', 'cache'):
                    paths[name].mkdir(parents=True, mode=0o700)
                for name in ('inductor', 'triton', 'cuda', 'torch', 'extensions', 'tmp'):
                    (paths['cache']/name).mkdir(mode=0o700)
                publish(base, paths['control'], dict(experiment='isolated-raw-kl-stage-a', lr_scale=.5))
            cgroup = base.OwnedCgroup(delegated, nonce)
            manifest = dict(schema=SCHEMA, explicit_launch=True, seed=SEED, variants=list(VARIANTS),
                attempts=1, retained_acquisition_attempts=8, selected_original_index=1, forward_routes=['original4','candidate_ce4','candidate_kl5'],
                actual_training_attempts=0, compiled_loss_outputs=4, offline_outputs=5, qualification_pass=False,
                source_lock_sha256=SOURCE_LOCK_SHA256,
                parent_sha256=digest(__file__), worker_sha256=digest(HERE/'cuda_trace_worker.py'),
                launch_token=uuid.uuid4().hex, nonce=nonce, parent=base.identity(), output=str(directory),
                output_identity=root_identity, tmpfs=str(layout.tmpfs), tmpfs_identity=tmp_identity,
                cgroup=str(cgroup.path), cgroup_identity=cgroup.identity, main_owners=initial['main_owners'],
                gpu_uuid=base.GPU0_UUID, forbidden_gpu_uuid=base.MAIN_GPU_UUID,
                bounds=dict(BOUNDS), sources=lock['source_files'], retained_inputs=retained_inputs,
                native_compiler_cache=native_cache,
                parent_process_scan_observations=dict(base.process_scan_observations),
                numerical_protocol=lock, service_exit_provenance='Root must retain original invocation and terminal fields before owned unit release')
            path = directory/'launch-manifest.json'
            publish(base, path, manifest)
            manifest_sha = digest(path)
            for variant in VARIANTS:
                require(time.monotonic() < overall_deadline, 'Fixed total deadline reached')
                require(digest(path) == manifest_sha and read_lock() == lock, 'Immutable launch protocol changed')
                base.verify_source_copies(layout, lock['source_files'])
                base.guard_live_resources(allowed_pids={os.getpid()}, expected_main=initial['main_owners'], initial=True)
                results.append(run_variant(base, layout, path, variant, cgroup,
                                           initial['main_owners'], overall_deadline))
            require(owned_byte_count(layout.output, root_identity) <= BOUNDS['artifact_bytes'] and
                    owned_byte_count(layout.tmpfs, tmp_identity) <= BOUNDS['tmpfs_bytes'], 'Final storage bound exceeded')
            base.verify_source_copies(layout, lock['source_files'])
            require(read_lock() == lock and digest(path) == manifest_sha, 'Final immutable source/protocol changed')
            require(bind_inputs(lock)==retained_inputs,'Original live8 source identities/provenance changed')
            base.guard_live_resources(allowed_pids={os.getpid()}, expected_main=initial['main_owners'])
        except BaseException as error:
            if root_identity is not None:
                base.check_directory(directory, root_identity)
                publish(base, directory/'failure.json', dict(status='VALIDATION_ERROR', error=repr(error),
                        parent_process_scan_observations=dict(base.process_scan_observations)))
            raise
        finally:
            with base.blocked_handled_signals():
                errors = []
                if cgroup is not None:
                    try:
                        cgroup.close()
                    except BaseException as error:
                        errors.append('cgroup: ' + repr(error))
                if tmp_identity is not None and not errors:
                    try:
                        base.check_directory(layout.tmpfs, tmp_identity)
                        require(json.loads((layout.tmpfs/'ownership.json').read_text())['nonce'] == nonce,
                                'Tmpfs ownership changed')
                        shutil.rmtree(layout.tmpfs)
                    except BaseException as error:
                        errors.append('tmpfs: ' + repr(error))
                lease.close()
                if errors:
                    publish(base, directory/'cleanup-failure.json', dict(
                        status='VALIDATION_ERROR', recovery_required=True, errors=errors))
                    raise RuntimeError('Owned cleanup requires recovery: ' + repr(errors))
        aggregate = dict(status='OBSERVATIONS_COMPLETE', schema=SCHEMA, variants=results,
            qualification_pass=False, comparison_pass=all(result['comparison_pass'] for result in results),
            comparison_scope='Stage A internal defaultCE4/original4 and KL5/defaultCE4 CE/objective/unscaled gradients; captured CE residual descriptive only; Stage B mandatory',
            interpretation_requires_review=any(result['interpretation_requires_review'] for result in results),
            comparison_summary=[dict(variant=result['variant'], comparison_pass=result['comparison_pass'],
                interpretation_requires_review=result['interpretation_requires_review'],
                actual_training_capture=False,selected_original_index=1,forward_routes=['original4','candidate_ce4','candidate_kl5']) for result in results],
            source_lock_sha256=SOURCE_LOCK_SHA256, owned_cleanup_complete=True,
            parent_process_scan_observations=dict(base.process_scan_observations),
            limitations=['Completed diagnostic may include original-tolerance mismatches; exit0 is not parity qualification',
                         'All8 original acquisition bindings preserved; only predeclared index1 is forwarded, with no new training attempt or selection',
                         'Three fixed compiled AMP forwards and three unscaled objective backwards, no clipping/optimizer/scaler step; not trained-scaler admission proof',
                         'Same-GPU route contrast alone does not exclude nondeterminism or uniquely establish a lowering cause',
                         'Any result on index1 cannot rescue the prior original-tolerance all8 comparison failure',
                         'Candidate KL is from this new candidate forward, never the historical captured executed target; no actual historical H/KL proof',
                         'Detached KL vector and returned stats checked, not independently full entropy reconstructed; no native replay readback or live phase/load proof',
                         'One predeclared batch does not establish replay-population or learning-quality conclusions',
                         'No actual live Rainbow agent/server lifecycle or throughput comparison',
                         'Storage watcher is cooperative, not a filesystem quota',
                         'Parent service original exit must be independently archived by root before release'])
        publish(base, directory/'result.json', aggregate)
        return aggregate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--launch', action='store_true')
    args = parser.parse_args(argv)
    if not args.launch:
        print(json.dumps(dict(status='PLAN_ONLY_UNEXECUTED', schema=SCHEMA, launch=False,
            variants=list(VARIANTS), batch_rows=4096, attempts=1, selected_original_index=1, forward_routes=['original4','candidate_ce4','candidate_kl5'],
            actual_training_attempts=0, compiled_loss_outputs=4, offline_outputs=5,
            qualification_pass=False, bounds=BOUNDS,
            source_lock_sha256=SOURCE_LOCK_SHA256, numerical_imports=False,
            runtime_queries=False, outputs_created=False, automatic_retry=False), indent=2))
        return 0
    require(args.directory is not None, 'Explicit launch requires a NEW absolute output directory')
    result = launch(args.directory)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
