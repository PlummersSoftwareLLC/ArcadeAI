import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import stat
import threading
import time
from datetime import datetime, timezone

REPO = Path('/home/dave/source/repos/ArcadeAI')
GAME = REPO / 'Robotron'
CAMPAIGN = GAME / 'logs/managed-learning-20261015'
OUT = CAMPAIGN / 'replay-archive-r16'
ROOTS = [
    (Path('/dev/shm/robotron_dqn_latest_replay'), 'replay'),
    (GAME / 'models_dqn/robotron_dqn_latest_replay_hof', 'hof'),
    (GAME / 'models_dqn/robotron_dqn_latest_replay_ephof', 'ephof'),
]
SMALL = [
    (GAME / 'models_dqn/robotron_dqn_latest.pt', 'model/robotron_dqn_latest.pt'),
    (GAME / 'models_dqn/game_settings.json', 'metadata/game_settings.json'),
    (GAME / 'models_dqn/learning_control.json', 'metadata/learning_control.json'),
    (CAMPAIGN / 'state.json', 'metadata/campaign_state.json'),
    (CAMPAIGN / 'run-04/metadata.json', 'metadata/run-04-metadata.json'),
    (CAMPAIGN / 'run-04/console.log', 'metadata/run-04-console.log'),
]

def now():
    return datetime.now(timezone.utc).isoformat()

def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    os.replace(temp, path)

def writers():
    found = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = (entry / 'cmdline').read_bytes().split(b'\0')
            args = [arg.decode(errors='replace') for arg in args if arg]
        except (OSError, ProcessLookupError):
            continue
        if not args:
            continue
        executable = Path(args[0]).name
        if ((executable.startswith('python') and any(arg.endswith(('run_dqn.py', 'dqn/main.py')) for arg in args))
                or (executable == 'mame' and any('robotron' in arg for arg in args[1:]))):
            found.append(dict(pid=int(entry.name), arguments=args))
    return found

assert not Path('/proc/397281').exists(), 'Requested trainer PID still exists'
assert not writers(), 'Trainer or MAME writer still active'
assert 'Shutdown complete' in (CAMPAIGN / 'run-04/console.log').read_text(), 'No clean shutdown receipt'
OUT.mkdir(exist_ok=False)
shutil.copy2(__file__, OUT / 'archive_copy.py')
started = time.monotonic()
progress = dict(status='preparing', started_utc=now(), writer_check=[],
                source_writer_pid=397281, shutdown_log='run-04/console.log', files_done=0,
                bytes_copied=0, total_bytes=0, current_file=None)
atomic_json(OUT / 'progress.json', progress)
manifest = []
jobs = []
for source, relative in SMALL:
    assert source.is_file(), str(source)
    jobs.append((source, OUT / relative))
for source, relative in ROOTS:
    assert source.is_dir() and not source.is_symlink(), str(source)
    files = sorted(source.rglob('*'))
    for item in files:
        assert not item.is_symlink(), f'Unexpected symlink: {item}'
        if item.is_file():
            jobs.append((item, OUT / relative / item.relative_to(source)))
for source, destination in jobs:
    info = source.stat()
    manifest.append(dict(source=str(source), destination=str(destination.relative_to(OUT)),
                         size=info.st_size, source_mtime_ns=info.st_mtime_ns,
                         source_mode=stat.S_IMODE(info.st_mode)))
total = sum(item['size'] for item in manifest)
assert shutil.disk_usage(OUT).free > total * 1.02, 'Insufficient destination space'
progress['total_bytes'] = total
atomic_json(OUT / 'source-manifest.json', dict(created_utc=now(), total_bytes=total, files=manifest))
done = 0
last_status = 0.0
try:
    for (source, destination), record in zip(jobs, manifest):
        destination.parent.mkdir(parents=True, exist_ok=True)
        failures = []
        def copy():
            try:
                # Actual independent data copy: no hardlinks or reflinks.
                shutil.copyfile(source, destination)
                with destination.open('rb') as stream:
                    os.fsync(stream.fileno())
                shutil.copystat(source, destination)
            except BaseException as exc:
                failures.append(exc)
        worker = threading.Thread(target=copy, daemon=True)
        worker.start()
        while worker.is_alive():
            timestamp = time.monotonic()
            if timestamp-last_status >= 15:
                live_writers = writers()
                if live_writers:
                    raise RuntimeError(f'Writers resumed during archive: {live_writers}')
                current = destination.stat().st_size if destination.exists() else 0
                copied = done + min(current, record['size'])
                elapsed = timestamp-started
                progress.update(status='copying', current_file=record['destination'],
                                bytes_copied=copied, percent=100*copied/total,
                                elapsed_s=elapsed, gib_per_s=copied/max(1, elapsed)/2**30,
                                updated_utc=now())
                atomic_json(OUT / 'progress.json', progress)
                print(json.dumps({key: progress[key] for key in (
                    'status','current_file','percent','bytes_copied','elapsed_s','gib_per_s')}), flush=True)
                last_status = timestamp
            worker.join(timeout=1)
        if failures:
            raise failures[0]
        after = source.stat()
        if (after.st_size, after.st_mtime_ns) != (record['size'], record['source_mtime_ns']):
            raise RuntimeError(f'Source changed during copy: {source}')
        assert destination.stat().st_size == record['size'], f'Size mismatch: {destination}'
        assert destination.stat().st_ino != source.stat().st_ino or destination.stat().st_dev != source.stat().st_dev
        done += record['size']
        progress['files_done'] += 1
    assert not writers(), 'Writers resumed before verification'
    progress.update(status='verifying', bytes_copied=done, percent=100., updated_utc=now())
    atomic_json(OUT / 'progress.json', progress)
    print('Copy complete; verifying file sizes, metadata hashes, independent files and sample byte checks', flush=True)
    verified = []
    for record in manifest:
        source, destination = Path(record['source']), OUT / record['destination']
        result = dict(destination=record['destination'], size=record['size'], size_verified=True)
        if record['size'] <= 64 * 2**20 or source.suffix in ('.pt', '.json', '.log'):
            def digest(path):
                value = hashlib.sha256()
                with path.open('rb') as stream:
                    while block := stream.read(8*2**20):
                        value.update(block)
                return value.hexdigest()
            left, right = digest(source), digest(destination)
            assert left == right, f'Metadata/checkpoint hash mismatch: {source}'
            result['sha256'] = left
            result['verification'] = 'full_sha256'
        else:
            size = record['size']
            length = min(65536, size)
            rng = random.Random(int.from_bytes(hashlib.sha256(record['destination'].encode()).digest()[:8], 'big'))
            positions = sorted({0, max(0,size-length), *(rng.randrange(max(1,size-length+1)) for _ in range(16))})
            checks = []
            with source.open('rb') as left, destination.open('rb') as right:
                for offset in positions:
                    left.seek(offset); right.seek(offset)
                    a, b = left.read(length), right.read(length)
                    assert a == b and len(a) == length, f'Sample mismatch: {source} at {offset}'
                    checks.append(dict(offset=offset,length=length,sha256=hashlib.sha256(a).hexdigest()))
            result.update(verification='18_deterministic_sample_byte_checks', samples=checks)
        verified.append(result)
        if time.monotonic()-last_status >= 15:
            progress.update(status='verifying', verification_files_done=len(verified), current_file=record['destination'],
                            updated_utc=now(), elapsed_s=time.monotonic()-started)
            atomic_json(OUT / 'progress.json', progress)
            print(json.dumps({k:progress.get(k) for k in ('status','verification_files_done','current_file','elapsed_s')}),flush=True)
            last_status=time.monotonic()
    import numpy as np
    small_meta={}
    for name in ('replay/_meta.npy','hof/hof_meta.npz','ephof/ephof_meta.npz'):
        value=np.load(OUT/name)
        if hasattr(value,'files'):
            small_meta[name]={key:value[key].tolist() for key in value.files}
            value.close()
        else:
            small_meta[name]=value.tolist()
    import torch
    checkpoint=torch.load(OUT/'model/robotron_dqn_latest.pt',map_location='cpu',weights_only=True)
    clock_keys=('engine_version','training_steps','optimized_samples','baseline_batch_size','last_target_update_samples',
                'frame_count','learner_frame_count','measurement_frame_count','total_training_steps','expert_ratio',
                'epsilon','lr_anchor_step','lr_gear','state_size','frame_stack')
    counters={key:checkpoint.get(key) for key in clock_keys}
    counters['optimizer_param_group_lr']=[group['lr'] for group in checkpoint['optimizer_state_dict']['param_groups']]
    atomic_json(OUT/'metadata/source-array-metadata.json',small_meta)
    atomic_json(OUT/'metadata/final-checkpoint-counters.json',counters)
    assert not writers(), 'Writers resumed before verified receipt'
    receipt=dict(status='verified', completed_utc=now(), total_bytes=done, files_verified=len(verified),
                 elapsed_s=time.monotonic()-started, verification_method='all sizes; full metadata/checkpoint SHA256; 18 deterministic 64KiB byte checks per large array',
                 no_hardlinks=True, sources_unchanged=True, writers=[], checkpoint_counters=counters, files=verified)
    atomic_json(OUT/'verification.json',receipt)
    progress.update(status='verified', bytes_copied=done, verification_files_done=len(verified),
                    elapsed_s=time.monotonic()-started, updated_utc=now(), current_file=None)
    atomic_json(OUT/'progress.json',progress)
    print(json.dumps({k:receipt[k] for k in ('status','total_bytes','files_verified','elapsed_s')}),flush=True)
except BaseException as exc:
    progress.update(status='FAILED', error=repr(exc), updated_utc=now(), elapsed_s=time.monotonic()-started)
    atomic_json(OUT/'progress.json',progress)
    raise
