"""Matched ephemeral control-file placement probe; no trainer/GPU/game changes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time


def load(pin, name):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    raw = Path(args.job).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == args.job_sha256
    job = json.loads(raw)
    assert job['schema'] == 'robotron-matched-control-storage-probe-job-v1'
    assert sys.version_info[:2] == (3, 14) and sys._is_gil_enabled() is False
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert job['iterations'] == 400 and job['poll_s'] == .2
    assert sys.executable == job['interpreter']['path']
    h = load(job['helpers'], '_placement_h')
    for pin in job['inputs']:
        h.checked(pin)
    codec = load(job['codec'], '_placement_original_codec')
    assert job['codec']['sha256'] == 'f59df995a625ed534af1c2cb54a15c885a8e431ab84e3829e6a8b2c6ceb7bf10'
    root = Path(job['output'])
    root.mkdir(mode=0o700)
    disk = root / 'ext4-control'
    disk.mkdir(mode=0o700)
    ram = Path('/dev/shm') / ('robotron-control-placement-' + secrets.token_hex(16))
    ram.mkdir(mode=0o700)
    ram_identity = (ram.stat().st_dev, ram.stat().st_ino, ram.stat().st_uid)
    paths = dict(ext4=disk / 'live.json', tmpfs=ram / 'live.json')
    mounts = []
    for storage, path in paths.items():
        argv = ['findmnt', '-T', str(path.parent), '-n', '-o', 'FSTYPE']
        result = subprocess.run(argv, capture_output=True, text=True, timeout=5)
        mounts.append(dict(storage=storage, argv=argv, exit=result.returncode,
                           stdout=result.stdout, stderr=result.stderr))
        assert result.returncode == 0 and result.stdout.strip() == storage
    rows = []
    errors = []
    stop = threading.Event()
    payload = 'x' * 4096

    def timed(storage, action, function, *values, **kwargs):
        start = time.monotonic()
        cpu = time.thread_time()
        error = None
        try:
            return function(*values, **kwargs)
        except BaseException as exception:
            error = repr(exception)
            raise
        finally:
            rows.append(dict(storage=storage, action=action, begin_monotonic_s=start,
                             end_monotonic_s=time.monotonic(), thread_cpu_s=time.thread_time()-cpu,
                             thread_id=threading.get_native_id(), error=error))
            assert len(rows) <= 4096

    def reader(storage, path):
        previous = -1
        try:
            while not stop.wait(.2):
                value = timed(storage, 'read', codec.checked_read, path, os.geteuid(), mode=0o644)
                assert value['payload'] == payload and type(value['sequence']) is int
                assert previous <= value['sequence'] <= job['iterations']
                previous = value['sequence']
        except BaseException as exception:
            errors.append(dict(storage=storage, action='read', error=repr(exception)))
            stop.set()

    threads = []
    begin = time.monotonic()
    try:
        for path in paths.values():
            codec.publish_live(path, dict(sequence=0, payload=payload))
        for storage, path in paths.items():
            thread = threading.Thread(target=reader, args=(storage, path))
            thread.start()
            threads.append(thread)
        for sequence in range(1, job['iterations'] + 1):
            assert sys._is_gil_enabled() is False
            tick = time.monotonic()
            assert not errors
            order = list(paths.items())
            if sequence % 2:
                order.reverse()
            for storage, path in order:
                timed(storage, 'publish', codec.publish_live, path,
                      dict(sequence=sequence, payload=payload))
            if stop.wait(max(0., tick + job['poll_s'] - time.monotonic())):
                raise ValueError('Original placement reader failed; no retry')
    except BaseException as exception:
        errors.append(dict(action='probe', error=repr(exception)))
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=2)
    assert all(not thread.is_alive() for thread in threads)
    ended = time.monotonic()
    archives = []
    for storage, path in paths.items():
        members = list(path.parent.iterdir())
        assert all(p.name in ('live.json', 'live.json.lock', 'live.json.' + str(os.getpid()) + '.tmp')
                   for p in members)
        for original in members:
            before = h.pin(original)
            data = original.read_bytes()
            assert h.pin(original) == before and before['identity']['uid'] == os.geteuid()
            target = root / (storage + '-' + original.name + '.original-bytes')
            with target.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fchmod(stream.fileno(), 0o444)
                os.fsync(stream.fileno())
            archived = h.pin(target)
            assert archived['sha256'] == before['sha256'] and archived['bytes'] == before['bytes']
            archives.append(dict(storage=storage, original=before, archived=archived))
        if not errors:
            assert codec.checked_read(path, os.geteuid(), mode=0o644) == dict(sequence=400, payload=payload)
    assert (ram.stat().st_dev, ram.stat().st_ino, ram.stat().st_uid) == ram_identity
    for item in archives:
        if item['storage'] == 'tmpfs':
            assert h.pin(item['original']['path']) == item['original']
            Path(item['original']['path']).unlink()
    ram.rmdir()
    assert not ram.exists() and 'torch' not in sys.modules
    summary = {}
    for storage in paths:
        for action in ('publish', 'read'):
            selected = [r for r in rows if r['storage'] == storage and r['action'] == action]
            if selected:
                durations = sorted(r['end_monotonic_s'] - r['begin_monotonic_s'] for r in selected)
                summary[storage + '_' + action] = dict(count=len(selected), maximum_s=max(durations),
                    mean_s=sum(durations)/len(durations), p99_s=durations[(len(durations)-1)*99//100])
    report = h.put(root / 'report.json', dict(schema='robotron-matched-control-storage-probe-report-v1',
        codec=job['codec'], interpreter=job['interpreter'], GIL_enabled=sys._is_gil_enabled(),
        job=h.pin(args.job), started_monotonic_s=begin, ended_monotonic_s=ended,
        mounts=mounts, rows=rows, errors=errors, summary=summary, original_control_archives=archives,
        original_tmpfs_directory=str(ram), original_tmpfs_identity=list(ram_identity),
        tmpfs_outputs_archived_before_owned_cleanup=True, all_reader_threads_stopped=True,
        alternating_publication_order=True, shared_disk_stress_not_induced=True,
        payload_is_explicit_synthetic_control_fixture=True, original_stall_cause_not_proven=True,
        production_changed=False, scientific_case=False, quality_qualified=False))
    print(json.dumps(dict(report=report, summary=summary, errors=errors)), flush=True)
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
