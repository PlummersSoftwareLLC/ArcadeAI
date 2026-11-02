"""Separately scoped round/TCP observer; inert without --execute.

Every accepted sample retains raw API bytes and both raw kernel TCP tables.
One source/job/parent/nonce-bound close request ends the original observer.
Unavailability re-polls the same owners; an expired proof cannot be rescued.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
import urllib.request

SCHEMA = 'robotron-round-observer-job-v3'


def require(value, message):
    if not value:
        raise ValueError(message)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
        mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)


def pin(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(), 'Noncanonical evidence path')
    before = identity(path.stat())
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    require(identity(path.stat()) == before, 'Evidence changed during hash')
    return dict(path=str(path), sha256=digest, bytes=before['bytes'], identity=before)


def checked(value):
    actual = pin(value['path'])
    require(all(actual[key] == expected for key, expected in value.items()), 'Pinned input changed: ' + value['path'])
    return Path(value['path'])


def read(path, limit=8 << 20):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        require(os.fstat(stream.fileno()).st_uid == os.getuid(), 'Evidence has a foreign owner')
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'Evidence exceeds bound')
    return json.loads(raw)


def write(path, value, live=False):
    path = Path(path)
    temporary = path.with_name(path.name + '.next') if live else path
    with temporary.open('xb') as stream:
        stream.write((json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n').encode())
        stream.flush()
        os.fchmod(stream.fileno(), 0o644 if live else 0o444)
        if not live:
            os.fsync(stream.fileno())
    if live:
        os.replace(temporary, path)
    else:
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return None if live else pin(path)


def load(name, value):
    spec = importlib.util.spec_from_file_location(name, checked(value))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None


def show(unit):
    raw = subprocess.check_output(['systemctl', '--user', 'show', unit], text=True, timeout=5)
    return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)


def owner():
    cgroup = next(line[3:] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
    unit = Path(cgroup).name
    values = show(unit)
    require(values['MainPID'] == str(os.getpid()) and values['ControlGroup'] == cgroup
            and values['InvocationID'] == os.environ['INVOCATION_ID'], 'Original scope identity differs')
    return dict(pid=os.getpid(), birth=birth(os.getpid()), unit=unit,
                invocation_id=values['InvocationID'], cgroup=cgroup, uid=os.getuid())


def check_parent(parent):
    require(birth(parent['pid']) == parent['birth'], 'Original parent disappeared or changed birth')
    root = Path('/proc', str(parent['pid']))
    require(root.joinpath('cgroup').read_text().strip() == '0::' + parent['cgroup'], 'Original parent moved scope')
    require([part.decode() for part in root.joinpath('cmdline').read_bytes().split(b'\0')[:-1]] == parent['argv'],
            'Original parent command changed')
    require(root.stat().st_uid == parent['uid'] == os.getuid(), 'Original parent owner changed')


def collect(health, case):
    started = time.monotonic()
    sample = health.collect(case)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
        raw = response.read((1 << 20) + 1)
    require(len(raw) <= 1 << 20, 'Raw API exceeds bound')
    sample['base_API_wire_sha256'] = sample['api_wire_sha256']
    sample['raw_API_wire'] = raw.decode('utf-8')
    sample['api'] = json.loads(raw)
    sample['api_wire_sha256'] = hashlib.sha256(raw).hexdigest()
    require(read(Path(case['round_root']) / 'status.json') == sample['status'], 'Round publication raced raw API capture')
    sample['unix_s'] = time.time()
    sample['monotonic_s'] = time.monotonic()
    require(sample['monotonic_s'] - started <= 5, 'Raw API/TCP capture exceeded5s')
    return sample


def run(job, job_pin):
    require(job['schema'] == SCHEMA and job['attempt'] == 1 and job['no_retry'] is True, 'One original observer required')
    require(job['interval_s'] == .2 and job['initial_samples'] == 100 and job['maximum_gap_s'] == .5
            and job['work_s'] == 4200 and job['runtime_s'] == 4260, 'Exact deadline observer bounds required')
    require(len(job['nonce']) == 32 and all(c in '0123456789abcdef' for c in job['nonce']), 'Fresh nonce required')
    require(pin(Path(__file__).resolve()) == job['sources']['worker'], 'Actual worker source differs')
    for value in job['sources'].values():
        checked(value)
    checked(job['native_job'])
    checked(job['native_runtime'])
    check_parent(job['parent'])
    actual_owner = owner()
    require(actual_owner['unit'] == job['unit'], 'Original observer unit differs')
    directory = Path(job['output'])
    directory.mkdir(mode=0o700)
    health = load('_original_round_TCP_health', job['sources']['health'])
    case = read(checked(job['case']))
    health.check_inputs(case, full=True)
    owner_pin = write(directory / 'owner.json', actual_owner)
    samples, retries, signals = [], [], []
    publications = []
    previous = None
    started = time.monotonic()
    last_advance = started
    initial = None
    error = None
    closed = False
    finish_request_pin = None
    finish_observed = None
    signal_before = {number: signal.signal(number, lambda signum, frame: signals.append(signum))
                     for number in (signal.SIGTERM, signal.SIGINT)}
    try:
        while True:
            iteration_started = time.monotonic()
            require(not signals, 'Original observer received a signal')
            check_parent(job['parent'])
            require(time.monotonic() < job['deadline_monotonic_s'], 'Original observer work bound reached')
            checked(job_pin)
            for value in job['sources'].values():
                checked(value)
            health.check_inputs(case)
            closing = False
            request_path = directory / 'finish-request.json'
            if request_path.exists():
                request = read(request_path)
                require(request['job'] == job_pin and request['nonce'] == job['nonce']
                        and request['parent'] == job['parent'] and request['action'] in ('close', 'abort'),
                        'Finish request does not target the original observer')
                require(request['action'] == 'close' and initial is not None, 'Original parent aborted or never became ready')
                require(type(request['created_monotonic_s']) in (int, float)
                        and started <= request['created_monotonic_s'] <= time.monotonic(),
                        'Original finish request timestamp differs')
                finish_request_pin = pin(request_path)
                finish_observed = time.monotonic()
                closing = True
            sample = None
            try:
                sample = collect(health, case)
                health.validate(case, sample, previous=previous)
            except (OSError, ValueError) as failure:
                retry = write(directory / ('unaccepted-%06d.json' % len(retries)),
                    dict(reason=repr(failure), unix_s=time.time(), raw_snapshot=sample))
                retries.append(retry)
                baseline = started if previous is None else previous['monotonic_s']
                require(time.monotonic() - baseline < job['maximum_gap_s'], 'No accepted original main proof for500ms')
                time.sleep(.01)
                continue
            if previous is not None:
                require(sample['monotonic_s'] - previous['monotonic_s'] <= .5, 'Accepted main proof gap exceeds500ms')
                if sample['api']['training_steps'] > previous['api']['training_steps']:
                    last_advance = time.monotonic()
            require(time.monotonic() - last_advance < 60, 'No advancing learner step for60s')
            entry = write(directory / ('sample-%06d.json' % len(samples)),
                dict(schema='robotron-round-observer-raw-sample-v1', job=job_pin, nonce=job['nonce'],
                     owner=actual_owner, index=len(samples), snapshot=sample))
            samples.append(entry)
            previous = sample
            if closing:
                closed = True
                break
            if initial is None and len(samples) >= job['initial_samples']:
                initial = dict(index=len(samples)-1, unix_s=sample['unix_s'], unaccepted_samples=len(retries))
            published = time.monotonic()
            require(0 <= published - sample['monotonic_s'] <= .5, 'Main projection source exceeds500ms')
            if publications:
                require(published-publications[-1]['updated_monotonic_s'] <= .5, 'Main projection gap exceeds500ms')
            publications.append(dict(index=len(samples)-1, updated_monotonic_s=published))
            write(directory / 'live.json', dict(schema='robotron-round-observer-live-v1',
                job=job_pin, nonce=job['nonce'], owner=actual_owner, observed_samples=len(samples),
                updated_monotonic_s=published, latest_sample=entry, initial=initial,
                phase=dict(overlap_pending=initial is None), state='running'), live=True)
            time.sleep(max(0, job['interval_s']-(time.monotonic()-iteration_started)))
        health.check_inputs(case, full=True)
        for value in job['sources'].values():
            checked(value)
    except BaseException as failure:
        error = repr(failure)
    finally:
        for number, handler in signal_before.items():
            signal.signal(number, handler)
    outcome = dict(schema='robotron-round-observer-outcome-v1', job=job_pin, nonce=job['nonce'],
        owner=owner_pin, parent=job['parent'], success=closed and error is None and not signals,
        error=error, signals_received=signals, initial=initial, samples=samples, unaccepted=retries,
        sources=job['sources'], all_writer_threads_stopped=True, publications=publications,
        finish_request=finish_request_pin, finish_observed_monotonic_s=finish_observed,
        final_snapshot_after_finish_request=closed,
        ended_monotonic_s=time.monotonic(), quality_qualified=False)
    write(directory / 'outcome.json', outcome)
    return 0 if outcome['success'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job')
    parser.add_argument('--job-sha256')
    args = parser.parse_args()
    if args.execute:
        value = pin(Path(args.job))
        require(value['sha256'] == args.job_sha256, 'Original job SHA differs')
        raise SystemExit(run(read(args.job), value))
    print('PLAN_ONLY: no reads, process actions, model or GPU operations')
