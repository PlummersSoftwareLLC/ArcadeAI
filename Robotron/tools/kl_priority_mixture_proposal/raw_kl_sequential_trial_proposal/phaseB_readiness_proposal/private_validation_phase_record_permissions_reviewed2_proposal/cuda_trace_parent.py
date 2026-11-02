#!/usr/bin/env python3
"""SOURCE-ONLY private raw-KL Stage B constructor/learner/phase readiness.

Default prints a literal plan without helper/source/data reads or live queries.
Future --launch requires a separately reviewed exclusive resource window and a
dedicated delegated robotron-snapshot-smoke-*.service. It does not train the
live agent, alter its sources or repair failed observations. Three owned roles
use verified448 weights and a declared reused genuine older regression input.
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
GAME = HERE.parents[4]
REPO = GAME.parent
SCHEMA = 'robotron-raw-kl-stage-b-private-v1'
SEED = 20261017
VARIANTS = ('kl18', 'resume', 'return_ce')
GIB, MIB = 1 << 30, 1 << 20
BOUNDS = dict(cpu_threads=2, memory_bytes=16*GIB, vram_allocator_bytes=12*GIB,
              vram_process_bytes=13*GIB, artifact_bytes=6*GIB, tmpfs_bytes=128*MIB,
              tasks=128, phase_timeout_s=600, total_timeout_s=2100)
SOURCE_LOCK_SHA256 = '8edbe0082cb93939ebc9bfe6be922058f9c821addf72567f57d2c7a83b53b5fc'
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


def owned_byte_count(root, expected_identity, *, volatile_caches=(), events=None, observer=None,
                     checkpoint_save=None):
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
    checkpoint_path=Path(checkpoint_save['path']) if checkpoint_save is not None else None
    if checkpoint_path is not None:
        require(checkpoint_path==root/'kl18/post-step-checkpoint.pt.tmp'
                and isinstance(checkpoint_save['initial_complete'],bool),
                'Checkpoint context must be exact owned kl18 publication')

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
        if checkpoint_path is not None:
            require(storage_directory_identity(checkpoint_path.parent)==checkpoint_save['parent_identity'],
                    'Checkpoint publication parent changed')
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
            if (checkpoint_path is not None and path==checkpoint_path and regular is not False
                    and checkpoint_temp_vanish_allowed(checkpoint_save)):
                checkpoint_save['events']['ignored_enoent']+=1
                checkpoint_save['events']['last_path']=str(path)
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
    path=HERE/'source-lock.json'
    require(path.is_absolute() and path==path.resolve() and not path.is_symlink(), 'Noncanonical source lock')
    data=path.read_bytes()
    require(hashlib.sha256(data).hexdigest()==SOURCE_LOCK_SHA256, 'Reviewed source lock changed')
    lock=json.loads(data)
    require(lock['schema']==SCHEMA and lock['seed']==SEED and lock['variants']==list(VARIANTS)
            and lock['batch_rows']==4096 and lock['state_width']==11128
            and lock['joint_actions']==81 and lock['atoms']==51
            and lock['stage_b']['attempts']==18 and lock['stage_b']['roles']==list(VARIANTS)
            and lock['stage_b']['qualification_pass'] is False
            and lock['stage_b']['wall_seconds_per_role']==BOUNDS['phase_timeout_s']==600
            and lock['stage_b']['wall_seconds_total']==BOUNDS['total_timeout_s']==2100
            and lock['stage_b']['no_replacement'] is True and lock['stage_b']['cap']==8
            and lock['stage_b']['samples_per_attempt']==4096
            and lock['stage_b']['synthetic_frame_credit_per_attempt']==512
            and lock['stage_b']['synthetic_frame_credits_total']==9216
            and lock['stage_b']['required_applied_outcomes']==1, 'Fixed Stage B protocol changed')
    for group in ('immutable_helpers','source_files'):
        for name,item in lock[group].items():
            source=Path(item['source'])
            if group=='source_files':
                require(name==Path(name).name and name not in ('','.','..'), 'Private source name escapes package')
            require(source.is_absolute() and source==source.resolve() and not source.is_symlink()
                    and source.is_file() and digest(source)==item['sha256'], 'Pinned source changed: '+name)
    for name in ('frozen_science_helpers','original_numeric_lock','conditional_helpers','reconstruction_helpers',
                 'acquisition_audit','retained_input_binding','observer_review','raw_kl_bundle',
                 'raw_kl_fixture_companion'):
        item=lock[name]; source=Path(item['source'])
        require(source.is_absolute() and source==source.resolve() and not source.is_symlink()
                and source.is_file() and digest(source)==item['sha256'], 'Pinned Stage B helper/evidence changed: '+name)
    expected={'agent.py':'865a0df717b39951b7f7c516e4a962e3d48cf4d3dc11295ff266e58653e6c74b',
        'training.py':'90b847856f810cb4f52513a4bd0625b2d15d4801107bff398060faae25bc4be4',
        'loss_kernel.py':'23eb8fc0d8409c9f31ef26ec4596da9c2257e3985abbbfa7d5fbdcb337e21f67',
        'config.py':'19abcbde4d08cf8465b82185ac6dd52eb8965adb8611584e0677c4c7ff21d1fd',
        'priority_phase.py':'ee3c0d02bc1eab55e92ffd605c3736fe5a0ef905a8a8ee242c687301ea2b7c5b'}
    require(all(lock['source_files'][name]['sha256']==h for name,h in expected.items()),
            'Candidate five-source scientific bundle changed')
    require(lock['raw_kl_bundle']['sha256']=='1144139f168292b7c0648fcc76d24a945d7d7f295ec14d5f304f70d5ca5dfe11'
            and lock['trained_checkpoint']['source']['sha256']=='1e085a128e237c2bb0636b073e5053dd8bf5be932bcbd8249543b3af20e23021'
            and lock['trained_checkpoint']['source']['bytes']==275181008
            and lock['trained_checkpoint']['cpu_verification']['sha256']=='98bae7f701493353a6cb4948d8a4653c5546411d2c40ba10d62f52dc412ddf52'
            and lock['trained_checkpoint']['cpu_job']['sha256']=='61647cd85d45ee30e73404d1f7463486c54cb80dea4c826ef6d799be63efeecb',
            'CPU-verified448 fixture binding changed')
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
    paths=layout.phase(variant)
    environment=_BASE.configure_environment(layout,variant)
    record=paths['root']/'phase-record.json'
    require(record.is_file() and not record.is_symlink(), 'Owned phase record must precede worker launch')
    environment.update(DQN_BATCH_SIZE='4096',DQN_TORCH_COMPILE='1',DQN_FULL_LOSS_COMPILE='1',
        DQN_COHERENT_SNAPSHOT='0',DQN_PER_PRIORITY_METRIC='ce' if variant=='return_ce' else 'kl',
        DQN_PRIORITY_PHASE_RECORD=str(record),DQN_PRIORITY_PHASE_RECORD_SHA256=digest(record),
        DQN_EXACT_INFERENCE_GRAPHS='1',DQN_EXACT_GRAPH_CHECKPOINT=str(paths['models']/'robotron_dqn_latest.pt'),
        DQN_RATCHET='0',DQN_NATIVE_BATCH_UPDATE='1',DQN_DIRECT_REPLAY_FILL='1',
        DQN_COMPILE_MODE='default',DQN_DIAGNOSTIC_INTERVAL='20',PYTHONDONTWRITEBYTECODE='1')
    environment.pop('DQN_EXECUTED_CE_TRACE_DIR',None); environment.pop('DQN_RECOMPUTED_CE_CAPTURE_DIR',None)
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


def job_pin_matches(record, observed):
    """Join existing CPU-job PIN fields to this parent's stronger FD/path PIN."""
    require(all(record[key]==observed[key] for key in ('path','sha256','bytes')), 'CPU job checkpoint differs')
    expected=record['identity']; actual=observed['identity']
    fields=dict(device='device',inode='inode',bytes='size',mtime_ns='mtime_ns',ctime_ns='ctime_ns',
                uid='uid',nlink='nlink')
    require(all(expected[name]==actual[target] for name,target in fields.items())
            and int(expected['mode'],8)==actual['mode'], 'CPU job checkpoint metadata differs')


def trained_fixture(lock):
    item=lock['trained_checkpoint']; source=item['source']
    model=stable_file(source['path'],source['sha256'],source['bytes'])
    metadata={}
    for key in ('cpu_job','cpu_verification'):
        entry=item[key]; path=Path(entry['source']); size=path.stat().st_size
        value,pin=bounded_json(dict(path=str(path),sha256=entry['sha256'],bytes=size),read_only=False)
        metadata[key]=(value,pin)
    job,jpin=metadata['cpu_job']; report,rpin=metadata['cpu_verification']
    require(job['schema']=='robotron-managed-candidate-checkpoint-CPU-job-v1'
            and report['schema']=='robotron-managed-candidate-checkpoint-CPU-result-v1'
            and report['status']=='PASS' and report['root_job']==job
            and report['job_file']['sha256']==jpin['sha256']
            and report['job_file']['path']==jpin['path']
            and all(report[key]==model[key] for key in ('path','sha256','bytes')),
            'Actual448 strict CPU proof/job/checkpoint join differs')
    job_pin_matches(job['verification_copy'],model)
    require(report['clocks']['training_steps']==2156883
            and report['clocks']['optimized_samples']==7387004928
            and report['clocks']['learner_frame_count']==452630871
            and report['clocks']['frame_count']==905164910,
            'Precommitted trained448 persisted clocks differ')
    return dict(source=model,candidate_source=job['source'],cpu_verification=rpin,cpu_job=jpin,
                saved_clocks=report['clocks'])


def copy_checkpoint(source, destination):
    """Create one independent0444 latest copy, without changing its source."""
    path=Path(source['path']); destination=Path(destination)
    require(stable_file(path,source['sha256'],source['bytes'])==source,
            'Checkpoint source changed before independent copy')
    require(not destination.exists() and not destination.is_symlink(), 'Private latest already exists')
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as incoming, destination.open('xb') as outgoing:
        identity=file_identity(os.fstat(incoming.fileno()))
        require(identity==source['identity'] and file_identity(path.lstat())==identity,
                'Checkpoint source FD/path mismatch before copying')
        digesting=hashlib.sha256(); copied=0
        while data:=incoming.read(MIB):
            outgoing.write(data);digesting.update(data);copied+=len(data)
        outgoing.flush();os.fsync(outgoing.fileno())
        require(file_identity(os.fstat(incoming.fileno()))==identity and file_identity(path.lstat())==identity,
                'Checkpoint source moved during copy')
    require(copied==source['bytes'] and digesting.hexdigest()==source['sha256'], 'Private latest copy hash differs')
    destination.chmod(0o444);sync_directory(destination.parent)
    copied=stable_file(destination,source['sha256'],source['bytes'])
    require((copied['identity']['device'],copied['identity']['inode'])!=
            (source['identity']['device'],source['identity']['inode']), 'Private latest aliases source')
    return copied


def prepare_role_inputs(base,layout,manifest_path,variant,results):
    manifest=json.loads(Path(manifest_path).read_text()); manifest_sha=digest(manifest_path)
    require(variant==VARIANTS[len(results)], 'Stage B role order changed')
    source_result=None
    if variant=='kl18':
        source=manifest['trained_fixture']['source']
    else:
        require(results and results[0]['variant']=='kl18', 'Newest post-step phase source missing')
        source=results[0]['saved_checkpoint']
        require(Path(source['path'])==layout.phase('kl18')['root']/'post-step-checkpoint.pt',
                'Later roles must use newest private post-step bytes, never original448')
        result_path=layout.phase('kl18')['root']/'phase-result.json'
        source_result=stable_file(result_path,digest(result_path),result_path.stat().st_size)
        recorded,_=bounded_json(source_result,read_only=True)
        require(recorded==results[0], 'Completed kl18 proof changed')
    paths=layout.phase(variant);latest=copy_checkpoint(source,paths['models']/'robotron_dqn_latest.pt')
    metric='ce' if variant=='return_ce' else 'kl'
    phase_id=('ce-stageB-' if variant=='return_ce' else 'kl-stageB-')+manifest['nonce']
    record=dict(schema='robotron-priority-metric-start-v1',phase_id=phase_id,metric=metric,
        action='resume' if variant=='resume' else 'start',previous_metric='unknown' if variant=='kl18' else 'kl',
        checkpoint={name:latest[name] for name in ('path','sha256','bytes')},model_dir=str(paths['models']),
        root_precommit_sha256=manifest_sha)
    record_path=paths['root']/'phase-record.json';publish(base,record_path,record,read_only=True)
    record_pin=stable_file(record_path,digest(record_path),record_path.stat().st_size)
    value=dict(schema='robotron-raw-kl-stage-b-role-input-v1',variant=variant,
        global_manifest_sha256=manifest_sha,source=source,latest=latest,phase_record=record_pin,
        source_role_result=source_result,metric=metric)
    publish(base,paths['root']/'role-input.json',value,read_only=True)
    return value


def read_role_input(layout,variant,manifest_sha):
    path=layout.phase(variant)['root']/'role-input.json'
    value,_=bounded_json(dict(path=str(path),sha256=digest(path),bytes=path.stat().st_size),read_only=True)
    paths=layout.phase(variant)
    require(value['schema']=='robotron-raw-kl-stage-b-role-input-v1'
            and value['variant']==variant and value['global_manifest_sha256']==manifest_sha
            and value['metric']==('ce' if variant=='return_ce' else 'kl')
            and Path(value['latest']['path'])==paths['models']/'robotron_dqn_latest.pt'
            and Path(value['phase_record']['path'])==paths['root']/'phase-record.json',
            'Owned role input manifest differs')
    for key in ('source','latest','phase_record'):
        pin=value[key]
        require(stable_file(pin['path'],pin['sha256'],pin['bytes'])==pin, 'Role input changed: '+key)
    record,_=bounded_json(value['phase_record'],read_only=True)
    require(digest(layout.output/'launch-manifest.json')==manifest_sha, 'Global launch manifest changed')
    manifest=json.loads((layout.output/'launch-manifest.json').read_text())
    if variant=='kl18':
        require(value['source']==manifest['trained_fixture']['source'] and value['source_role_result'] is None,
                'Initial role must load exact verified448 copy')
    else:
        require(Path(value['source']['path'])==layout.phase('kl18')['root']/'post-step-checkpoint.pt'
                and Path(value['source_role_result']['path'])==layout.phase('kl18')['root']/'phase-result.json',
                'Later role newest-checkpoint ancestry differs')
        predecessor,_=bounded_json(value['source_role_result'],read_only=True)
        require(predecessor['saved_checkpoint']==value['source'] and predecessor['variant']=='kl18'
                and predecessor['status']=='OBSERVATIONS_COMPLETE' and predecessor['actual_attempts']==18,
                'Later role must use completed fixed18 source proof')
    require(value['source']['sha256']==value['latest']['sha256']
            and value['source']['bytes']==value['latest']['bytes']
            and (value['source']['identity']['device'],value['source']['identity']['inode'])!=
                (value['latest']['identity']['device'],value['latest']['identity']['inode']),
            'Private latest must independently copy exact source')
    require(record['root_precommit_sha256']==manifest_sha and record['metric']==value['metric']
            and record['checkpoint']=={key:value['latest'][key] for key in ('path','sha256','bytes')}
            and record['model_dir']==str(paths['models'])
            and record['phase_id']==('ce-stageB-' if variant=='return_ce' else 'kl-stageB-')+manifest['nonce']
            and record['action']==('resume' if variant=='resume' else 'start')
            and record['previous_metric']==('unknown' if variant=='kl18' else 'kl'), 'Role phase/checkpoint mismatch')
    return value


def checkpoint_marker_snapshot(directory,events):
    directory=Path(directory);target=directory/'post-step-checkpoint.pt'
    def read_marker(stage,name):
        path=directory/name
        try:
            info=path.lstat()
        except OSError as error:
            if error.errno==errno.ENOENT:
                return None
            raise
        mode=stat.S_IMODE(info.st_mode)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid()
                and info.st_nlink==1 and 0<=info.st_size<=65536 and not mode&0o111,
                'Save marker must be owned single-link bounded regular metadata')
        if mode&0o200:
            # Visible create-only publication is not yet authority.
            events['pending_marker_snapshots']=events.get('pending_marker_snapshots',0)+1
            events['last_pending_marker']=name
            return dict(pending=True)
        require(mode==0o444 and info.st_size>0, 'Completed save marker must be readonly/nonempty')
        value,_=bounded_json(dict(path=str(path),sha256=digest(path),bytes=info.st_size),read_only=True)
        require(value['schema']=='robotron-raw-kl-stage-b-save-v1' and value['variant']=='kl18'
                and value['stage']==stage and value['path']==str(target), 'Save marker context differs')
        return value
    entered=read_marker('entered','save-entered.json')
    complete=read_marker('complete','save-complete.json')
    if complete is not None and (entered is None or entered.get('pending',False)):
        # Reads are not a coherent snapshot. Intent is monotonic/create-only;
        # allow ONE fresh strict read if completion appeared after a stale view.
        entered=read_marker('entered','save-entered.json')
    require(complete is None or (entered is not None and not entered.get('pending',False)),
            'Completed save lacks validated entered record')
    return dict(entered_valid=entered is not None and not entered.get('pending',False),
        completed=complete if complete is not None and not complete.get('pending',False) else None)


def checkpoint_publication_state(layout,variant,parent_identity,events):
    """Snapshot context, not permission, before one non-atomic traversal."""
    if variant!='kl18':
        return None
    directory=layout.phase('kl18')['root']
    require(storage_directory_identity(directory)==parent_identity, 'Owned kl18 directory changed')
    snapshot=checkpoint_marker_snapshot(directory,events)
    return dict(path=str(directory/'post-step-checkpoint.pt.tmp'),parent_identity=parent_identity,
        initial_complete=snapshot['completed'] is not None,events=events)


def checkpoint_temp_vanish_allowed(context):
    """Revalidate only the exact source-proven single save at observed ENOENT.

    A pending intent can become valid and save/rename during this walk. A new
    completion therefore needs exact readonly final FD/path metadata as well.
    Already-complete-at-start means this walk has no active publication edge.
    """
    path=Path(context['path']);directory=path.parent
    require(storage_directory_identity(directory)==context['parent_identity'],
            'Owned checkpoint directory changed at publication edge')
    if context['initial_complete']:
        return False
    current=checkpoint_marker_snapshot(directory,context['events'])
    if not current['entered_valid']:
        return False
    if current['completed'] is None:
        return True
    pin=current['completed']['saved_checkpoint'];final=directory/'post-step-checkpoint.pt'
    require(pin['path']==str(final) and type(pin['bytes']) is int and pin['bytes']>0
            and isinstance(pin['sha256'],str) and len(pin['sha256'])==64
            and all(value in '0123456789abcdef' for value in pin['sha256']),
            'Completed checkpoint marker has wrong final identity')
    descriptor=os.open(final,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(descriptor);identity=file_identity(info)
        require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o444
                and info.st_uid==os.getuid() and info.st_nlink==1
                and identity==pin['identity'] and info.st_size==pin['bytes']
                and file_identity(final.lstat())==identity,
                'Completed checkpoint final FD/path readonly binding differs')
    finally:
        os.close(descriptor)
    context['events']['completed_during_scan']=context['events'].get('completed_during_scan',0)+1
    return True


def publish(base, path, value, *, read_only=False):
    base.json_exclusive(path, value)
    if read_only:
        # Only NEW phase-record/role-input metadata requests this seal, before
        # stable_file or a worker can consume it. Other publication is unchanged.
        path=Path(path)
        descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(descriptor)
            require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid()
                    and before.st_nlink==1 and 0<before.st_size<=2*MIB
                    and file_identity(path.lstat())==file_identity(before),
                    'Readonly role metadata FD/path identity differs before sealing')
            os.fchmod(descriptor,0o444)
            os.fsync(descriptor)
            sealed=os.fstat(descriptor)
            require(stat.S_IMODE(sealed.st_mode)==0o444
                    and file_identity(path.lstat())==file_identity(sealed),
                    'Readonly role metadata FD/path identity differs after sealing')
        finally:
            os.close(descriptor)
    sync_directory(Path(path).parent)


def command(manifest_path, variant):
    return [sys.executable, '-Xgil=0', '-I', '-B', str(HERE/'cuda_trace_worker.py'),
            '--manifest', str(manifest_path), '--variant', variant]


def result_contract(result,variant):
    require(result.get('status')=='OBSERVATIONS_COMPLETE' and result.get('variant')==variant
            and result.get('qualification_pass') is False, 'Stage B role completion/scope differs')
    require(result.get('actual_attempts')==(18 if variant=='kl18' else 0),
            'Fixed Stage B role update budget differs')
    require(result.get('phase_load_verified') is True and result.get('constructor_verified') is True,
            'Actual constructor/load proof missing')
    require(isinstance(result.get('readiness_pass'),bool), 'Stage B readiness flag missing')
    if variant=='kl18':
        require(isinstance(result.get('saved_checkpoint'),dict)
                and type(result.get('applied_outcomes')) is int and 0<=result['applied_outcomes']<=18
                and (result['applied_outcomes']>0 or result['readiness_pass'] is False),
                'New post-step checkpoint/applied-outcome proof missing')
    return result


def run_variant(base, layout, manifest_path, variant, cgroup, main, overall_deadline):
    paths = layout.phase(variant)
    manifest = json.loads(manifest_path.read_text())
    native_cache = manifest['native_compiler_cache']
    require(Path(native_cache['path']) == layout.scripts/'dqn/__pycache__', 'Unexpected native compiler-cache path')
    cache_identity = storage_directory_identity(paths['cache'])
    cache_events = dict(ignored_enoent=0, last_relative_path=None)
    checkpoint_parent_identity=storage_directory_identity(paths['root']) if variant=='kl18' else None
    checkpoint_events=dict(ignored_enoent=0,last_path=None)
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
                            observer=observer,
                            checkpoint_save=checkpoint_publication_state(
                                layout,variant,checkpoint_parent_identity,checkpoint_events)) <= BOUNDS['artifact_bytes'] and
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
                            checkpoint_publication_observations=checkpoint_events,
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
            fixture = trained_fixture(lock)
            for variant in VARIANTS:
                paths = layout.phase(variant)
                for name in ('root', 'models', 'journal', 'tmpfs', 'cache'):
                    paths[name].mkdir(parents=True, mode=0o700)
                for name in ('inductor', 'triton', 'cuda', 'torch', 'extensions', 'tmp'):
                    (paths['cache']/name).mkdir(mode=0o700)
                publish(base, paths['control'], dict(experiment='isolated-raw-kl-stage-b', lr_scale=.5))
            cgroup = base.OwnedCgroup(delegated, nonce)
            manifest = dict(schema=SCHEMA, explicit_launch=True, seed=SEED, variants=list(VARIANTS),
                attempts=18, retained_acquisition_attempts=8, selected_original_index=1,
                actual_training_attempts=18, qualification_pass=False, trained_fixture=fixture,
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
                prepare_role_inputs(base,layout,path,variant,results)
                results.append(run_variant(base, layout, path, variant, cgroup,
                                           initial['main_owners'], overall_deadline))
            require(owned_byte_count(layout.output, root_identity) <= BOUNDS['artifact_bytes'] and
                    owned_byte_count(layout.tmpfs, tmp_identity) <= BOUNDS['tmpfs_bytes'], 'Final storage bound exceeded')
            base.verify_source_copies(layout, lock['source_files'])
            require(read_lock() == lock and digest(path) == manifest_sha, 'Final immutable source/protocol changed')
            require(bind_inputs(lock)==retained_inputs,'Original live8 source identities/provenance changed')
            require(trained_fixture(lock)==fixture,'Initial readonly448 fixture/CPU proof changed')
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
        aggregate = dict(status='OBSERVATIONS_COMPLETE',schema=SCHEMA,variants=results,
            readiness_pass=all(result['readiness_pass'] for result in results),qualification_pass=False,
            applied_outcomes=results[0]['applied_outcomes'],actual_attempts=18,
            source_lock_sha256=SOURCE_LOCK_SHA256,owned_cleanup_complete=True,
            parent_process_scan_observations=dict(base.process_scan_observations),
            scope='Actual private candidate constructor/load and isolated fixed-input learner/phase-lifecycle readiness; no live adoption or learning-quality qualification',
            limitations=['Readonly verified448 weights with reused genuine older attempt01 inputs are a declared regression fixture, never a new current draw',
                'A bounded replay adapter/native6M scalar tree is not full ring/bank restoration or a coherent live learning anchor',
                'Private serving graphs are explicitly released before isolated learner updates; no serving/learning concurrency proof',
                'Exactly18 actual attempts, no19th rescue; all-skip coverage remains readinessFalse',
                'Resume/return-CE use newest post-step checkpoint bytes and no optimizer attempt',
                'Previous all8 captured-vs-recomputed failures remain unchanged; no historical actualH/KL or learning-benefit claim',
                'Original parent unit terminal identity/exit must be archived by root before release'])
        publish(base, directory/'result.json', aggregate)
        return aggregate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--launch', action='store_true')
    args = parser.parse_args(argv)
    if not args.launch:
        print(json.dumps(dict(status='PLAN_ONLY_UNEXECUTED',schema=SCHEMA,launch=False,
            variants=list(VARIANTS),batch_rows=4096,attempts=18,selected_original_index=1,
            role_attempts={'kl18':18,'resume':0,'return_ce':0},qualification_pass=False,
            bounds=BOUNDS,source_lock_sha256=SOURCE_LOCK_SHA256,numerical_imports=False,
            runtime_queries=False,outputs_created=False,automatic_retry=False),indent=2))
        return 0
    require(args.directory is not None, 'Explicit launch requires a NEW absolute output directory')
    result = launch(args.directory)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
