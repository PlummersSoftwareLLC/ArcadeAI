"""Restore a verified durable ring into an empty, offline reboot allocation.

Never changes the current checkpoint, banks, controls or training sources. The
ring stays explicitly empty until every data file passes both stream and reread
checksums. A separate exact CPU/startup validation is required before training.
"""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import time


def require(value, reason):
    if not value:
        raise ValueError(reason)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid,
                nlink=info.st_nlink)


def regular(path):
    path = Path(path)
    info = path.lstat()
    require(path.is_absolute() and path.resolve(strict=True) == path
            and stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and info.st_nlink == 1, 'Canonical owned single-link regular file required')
    return identity(info)


def put(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=regular(path))


def meta_values(raw):
    require(raw[:8] == b'\x93NUMPY\x01\x00', 'Exact original NPY metadata format required')
    length = struct.unpack('<H', raw[8:10])[0]
    header = ast.literal_eval(raw[10:10 + length].decode('ascii'))
    require(header == dict(descr='<f8', fortran_order=False, shape=(3,))
            and len(raw) == 10 + length + 24, 'Exact three-float replay metadata required')
    return struct.unpack('<3d', raw[10 + length:])


def offline_units():
    result = subprocess.run(['systemctl', '--user', 'show', 'robotron-trainer.service',
                             'robotron-mame.service', '--property=Id,ActiveState,MainPID'],
                            capture_output=True, text=True, timeout=5, check=True)
    records = [dict(line.split('=', 1) for line in block.splitlines() if '=' in line)
               for block in result.stdout.strip().split('\n\n')]
    require({row['Id'] for row in records} == {'robotron-trainer.service', 'robotron-mame.service'}
            and all(row['MainPID'] == '0' and row['ActiveState'] in ('inactive', 'failed')
                    for row in records), 'Both original training units must remain offline')
    return records


class Guard:
    def __init__(self, job):
        self.job = job; self.next_units = 0; self.meta_committed = False

    def __call__(self):
        require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == self.job['boot_id'],
                'Recovery boot changed')
        require(regular(self.job['checkpoint']['path']) == self.job['checkpoint']['identity'],
                'Latest checkpoint changed during recovery')
        if not self.meta_committed:
            require(regular(self.job['empty_meta']['path']) == self.job['empty_meta']['identity'],
                    'Empty ring commit marker changed before data verification')
        if time.monotonic() >= self.next_units:
            offline_units(); self.next_units = time.monotonic() + 2


def hash_file(path, guard):
    before = regular(path); digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(8 << 20):
            guard(); digest.update(chunk)
    require(regular(path) == before, 'File changed during checksum read')
    return digest.hexdigest()


def copy_verified(row, guard, progress):
    source = Path(row['source']); target = Path(row['target'])
    require(regular(source) == row['source_identity'] and row['source_identity']['mode'] == '0o444',
            'Immutable backup source changed')
    require(regular(target) == row['target_identity']
            and row['target_identity']['bytes'] == row['source_identity']['bytes'],
            'Existing empty destination object changed')
    digest = hashlib.sha256(); copied = 0
    # Do not truncate or allocate a second 249GiB tmpfs ring.
    with source.open('rb') as incoming, target.open('r+b') as outgoing:
        while chunk := incoming.read(8 << 20):
            guard(); require(outgoing.write(chunk) == len(chunk), 'Short recovery write')
            digest.update(chunk); copied += len(chunk); progress(copied, 'copy')
        outgoing.flush(); os.fsync(outgoing.fileno())
    require(copied == row['source_identity']['bytes'] and digest.hexdigest() == row['sha256']
            and regular(source) == row['source_identity'], 'Backup stream checksum or identity differs')
    progress(copied, 'reread')
    require(hash_file(target, guard) == row['sha256'], 'Restored destination reread checksum differs')
    return dict(source=str(source), target=str(target), bytes=copied, sha256=digest.hexdigest(),
                destination=regular(target), full_destination_reread_verified=True)


def restore_data_then_commit(rows, copy, commit):
    receipts = []
    for row in rows:
        receipts.append(copy(row))
    return receipts, commit()


def validate_targets(job):
    root = Path('/dev/shm/robotron_dqn_latest_replay')
    names = {'states', 'next_states', 'actions', 'rewards', 'dones', 'horizons',
             'is_expert', 'actor_kind', 'interesting', 'priorities'}
    require(len(job['files']) == 10 and {row['name'] for row in job['files']} == names,
            'Exact ten original replay fields required')
    require(Path(job['empty_meta']['path']) == root/'_meta.npy'
            and regular(job['empty_meta']['path']) == job['empty_meta']['identity'],
            'Exact empty original ring marker required')
    for row in job['files']:
        require(Path(row['target']) == root/(row['name']+'.npy')
                and regular(row['target']) == row['target_identity']
                and row['target_identity']['ctime_ns'] >= job['boot_unix_lower_ns'],
                'Only the verified reboot-created empty replay allocation may be restored')


def execute(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256,
            'Selected recovery source changed')
    raw = args.job.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == args.job_sha256, 'Selected recovery job changed')
    job = json.loads(raw)
    require(job['schema'] == 'robotron-reboot-empty-ring-restore-job-v1'
            and job['original_attempt'] == 1 and job['no_retry'] is True
            and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'One original CPU-only recovery required')
    directory = Path(job['output']); directory.mkdir(mode=0o700)
    started = time.monotonic(); guard = Guard(job); guard()
    owner = dict(pid=os.getpid(), birth=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
                 invocation_id=os.environ.get('INVOCATION_ID'), unit=job['unit'])
    put(directory/'owner.json', owner)
    outcome = dict(schema='robotron-reboot-ring-restoration-result-v1', original_job=str(args.job), owner=owner,
                   quality_qualified=False, training_startup_qualified=False, promotion=False)
    last_print = [0]
    def progress(name, count, phase):
        if time.monotonic() - last_print[0] < 10:
            return
        value = dict(state='restoring_verified_backup', file=name, bytes=count, phase=phase,
                     elapsed_s=time.monotonic()-started, observed_unix_s=time.time())
        temporary = directory/'progress.next.json'
        with temporary.open('w') as stream:
            json.dump(value, stream); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, directory/'progress.json'); print(json.dumps(value), flush=True)
        last_print[0] = time.monotonic()
    try:
        validate_targets(job)
        empty = Path(job['empty_meta']['path'])
        require(meta_values(empty.read_bytes())[:2] == (0, 0), 'Never overwrite a populated replay ring')
        require(hash_file(job['checkpoint']['path'], guard) == job['checkpoint']['sha256'],
                'Latest checkpoint digest differs')
        preserved = directory/'latest-checkpoint-preserved.pt'
        with Path(job['checkpoint']['path']).open('rb') as src, preserved.open('xb') as dst:
            while chunk := src.read(8 << 20):
                guard(); dst.write(chunk)
            dst.flush(); os.fchmod(dst.fileno(), 0o444); os.fsync(dst.fileno())
        require(hash_file(preserved, guard) == job['checkpoint']['sha256'], 'Checkpoint preservation differs')
        put(directory/'empty-allocation-preimage.json', dict(meta_base64=base64.b64encode(empty.read_bytes()).decode(),
            objects=job['files'], valid_experience_count=0, allocation_created_after_current_boot=True))
        meta = job['backup_meta']; source_meta = Path(meta['source'])
        require(regular(source_meta) == meta['source_identity'], 'Original backup metadata changed')
        meta_raw = source_meta.read_bytes()
        require(hashlib.sha256(meta_raw).hexdigest() == meta['sha256'] and meta_values(meta_raw)[0] == 6000000,
                'Backup does not contain the complete six-million-transition ring')
        def commit():
            guard(); require(hash_file(job['checkpoint']['path'], guard) == job['checkpoint']['sha256'],
                             'Checkpoint changed before replay commit')
            temporary = empty.with_name('._meta.reboot-restore-%d.npy' % os.getpid())
            with temporary.open('xb') as stream:
                stream.write(meta_raw); stream.flush(); os.fchmod(stream.fileno(), 0o664); os.fsync(stream.fileno())
            guard(); os.replace(temporary, empty); guard.meta_committed = True
            fd = os.open(empty.parent, os.O_RDONLY | os.O_DIRECTORY); os.fsync(fd); os.close(fd)
            require(empty.read_bytes() == meta_raw, 'Committed replay metadata differs')
            return dict(path=str(empty), identity=regular(empty), values=meta_values(meta_raw),
                        sha256=hashlib.sha256(meta_raw).hexdigest())
        restored, committed = restore_data_then_commit(job['files'],
            lambda row:copy_verified(row, guard, lambda count, phase:progress(row['name'], count, phase)), commit)
        guard(); offline_units()
        outcome.update(status='DURABLE_RING_RESTORED_AND_REREAD_VERIFIED', restored_files=restored,
            committed_meta=committed, checkpoint_preserved=str(preserved),
            latest_model_optimizer_and_banks_unchanged=True, replay_backup_is_older_than_latest_checkpoint=True,
            restored_replay_belongs_to_checkpoint_sha256=job['backup_checkpoint_sha256'],
            all_data_verified_before_meta_commit=True, Torch_imported='torch' in sys.modules,
            GPU_or_MAME_launched=False)
    except BaseException as error:
        outcome.update(status='FAILED_ORIGINAL_RESTORE_NO_RETRY', error=repr(error),
                       replay_meta_commit_occurred=guard.meta_committed)
    outcome['elapsed_s'] = time.monotonic() - started
    put(directory/'result.json', outcome)
    print(json.dumps(dict(status=outcome['status'], report=str(directory/'result.json'))), flush=True)
    return 0 if outcome['status'] == 'DURABLE_RING_RESTORED_AND_REREAD_VERIFIED' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256'); parser.add_argument('--source-sha256'); args = parser.parse_args()
    if args.execute:
        raise SystemExit(execute(args))
    print('PLAN_ONLY_NO_READS_OR_ACTIONS')
