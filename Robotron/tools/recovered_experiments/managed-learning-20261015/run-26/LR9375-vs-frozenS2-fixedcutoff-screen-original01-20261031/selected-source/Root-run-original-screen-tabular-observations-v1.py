"""Root-only bounded serial instrumentation; never controls the original pair.

Each child is the exact frozen F observer. Only that observer reads its existing
API/status inputs and appends the three F CSVs. This runner preserves its stdout,
stderr and actual reaped exit; a failure stops instrumentation without a retry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

CASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/LR9375-vs-frozenS2-fixedcutoff-screen-original01-20261031')
OBSERVER = CASE / 'selected-source/Root-observe-original-screen-and-learning-totals-v7.py'
OBSERVER_SHA = '62fff4d284b683beb140b6772094dc3335987867113dd2d700f722e42eb5e8d6'
OBSERVER_IDENTITY = dict(device=2304, inode=82727320, bytes=8732,
    mtime_ns=1793470035625296463, ctime_ns=1793470116349090355,
    mode='0o444', uid=1001, nlink=1)
COMMAND = ['/usr/bin/python3.12', '-I', '-B', str(OBSERVER)]
OUTER_PID, OUTER_BIRTH, OUTER_SESSION = 1535267, 35349191, 2024
INTERVAL_S, MAX_SECONDS, MAX_OBSERVATIONS = 45.0, 14400.0, 330
OUTPUT = CASE / 'original-observation-loop-original01'
RECORDS = OUTPUT / 'observations'


def require(ok, message):
    if not ok: raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path, expected_sha=None, expected_identity=None):
    before = path.lstat()
    require(path.resolve() == path and stat.S_ISREG(before.st_mode)
            and stat.S_IMODE(before.st_mode) == 0o444 and before.st_uid == os.getuid()
            and before.st_nlink == 1, 'Owned canonical immutable regular file required')
    raw = path.read_bytes()
    require(identity(path.lstat()) == identity(before), 'Immutable file changed while reading')
    result = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=identity(before))
    if expected_sha is not None: require(result['sha256'] == expected_sha, 'Source SHA differs')
    if expected_identity is not None: require(result['identity'] == expected_identity, 'Observer full identity differs')
    return result


def birth(pid):
    try: text = Path('/proc', str(pid), 'stat').read_text()
    except FileNotFoundError: return None
    value = int(text.rsplit(')', 1)[1].split()[19])
    require(value > 0, 'Positive original process birth required')
    return value


def outer_observation():
    value = birth(OUTER_PID)
    return dict(pid=OUTER_PID, expected_birth=OUTER_BIRTH, observed_birth=value,
                original_live=value == OUTER_BIRTH)


def write_json(path, value, *, replace=False):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    temporary = path.with_name('.' + path.name + '.' + str(os.getpid()) + '.tmp') if replace else path
    with temporary.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o444)
    if replace: os.replace(temporary, path)
    return pin(path)


def observe_once(index, before):
    selected = pin(OBSERVER, OBSERVER_SHA, OBSERVER_IDENTITY)
    prefix = f'{index:06d}'
    started, started_monotonic = time.time(), time.monotonic()
    intent = dict(index=index, started_unix_s=started, command=COMMAND, observer=selected,
                  original_outer_before=before, final_after_original_outer_absence=not before['original_live'])
    write_json(RECORDS / (prefix + '-intent.json'), intent)
    stdout_path, stderr_path = [RECORDS / (prefix + '-' + name + '.txt') for name in ('stdout', 'stderr')]
    child, code, error = None, None, None
    with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
        try:
            child = subprocess.Popen(COMMAND, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
            code = child.wait()  # No timeout, cancellation, retry, restart or foreign-process action.
        except Exception as exc:
            error = repr(exc)
        finally:
            for stream in (stdout, stderr):
                stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o444)
    try: pin(OBSERVER, OBSERVER_SHA, OBSERVER_IDENTITY)
    except Exception as exc: error = (error + '; ' if error else '') + 'Post-observation source check: ' + repr(exc)
    after = outer_observation()
    record = dict(index=index, started_unix_s=started, ended_unix_s=time.time(),
                  elapsed_s=time.monotonic()-started_monotonic, command=COMMAND, observer=selected,
                  original_observer_child_pid=None if child is None else child.pid,
                  original_observer_child_wait_reaped=code is not None, observer_actual_exit=code,
                  instrumentation_error=error, original_outer_before=before, original_outer_after=after,
                  final_after_original_outer_absence=not before['original_live'],
                  stdout=pin(stdout_path), stderr=pin(stderr_path))
    reference = write_json(RECORDS / (prefix + '-result.json'), record)
    return record, reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--expected-source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: exact frozen observer, serial45s, max4h/330; no reads or outputs')
        return 0
    require(type(args.expected_source_sha256) is str and re.fullmatch(r'[0-9a-f]{64}', args.expected_source_sha256), 'Exact runner SHA required')
    source = pin(Path(__file__).resolve(), args.expected_source_sha256)
    observer = pin(OBSERVER, OBSERVER_SHA, OBSERVER_IDENTITY)
    require(OUTPUT.resolve() == OUTPUT and not OUTPUT.exists(), 'Fresh F-local output only')
    started, started_monotonic = time.time(), time.monotonic()
    deadline = started_monotonic + MAX_SECONDS
    pid = os.getpid(); own_birth = birth(pid)
    OUTPUT.mkdir(mode=0o700, exist_ok=False); RECORDS.mkdir(mode=0o700)
    write_json(OUTPUT / 'owner.json', dict(pid=pid, birth=own_birth, started_unix_s=started,
        source=source, observer=observer, command=COMMAND, interval_s=INTERVAL_S,
        maximum_observations=MAX_OBSERVATIONS, maximum_launch_window_s=MAX_SECONDS,
        original_outer=dict(pid=OUTER_PID, birth=OUTER_BIRTH, tool_session=OUTER_SESSION),
        CONTROL_PUBLIC_Main_fleet_actions=False))
    count, exit_code, reason, last, error = 0, 0, 'observation_limit', None, None
    next_launch = started_monotonic
    try:
        while count < MAX_OBSERVATIONS:
            remaining = deadline-time.monotonic()
            if remaining <= 0: reason = 'four_hour_launch_budget'; break
            delay = next_launch-time.monotonic()
            if delay > 0: time.sleep(min(delay, remaining))
            if time.monotonic() >= deadline: reason = 'four_hour_launch_budget'; break
            before = outer_observation(); count += 1
            launched = time.monotonic(); last, reference = observe_once(count, before)
            write_json(OUTPUT / 'latest.json', dict(pid=pid, birth=own_birth,
                completed_observations=count, updated_unix_s=time.time(), last_result=reference,
                original_outer=last['original_outer_after']), replace=True)
            if last['observer_actual_exit'] != 0 or last['instrumentation_error'] is not None:
                exit_code, reason = 1, 'original_observation_failed'; break
            if not before['original_live']: reason = 'final_observation_after_original_outer_absence'; break
            # A disappearance during the child requires one subsequent observation
            # begun AFTER absence. Otherwise keep45s start cadence without catch-up.
            next_launch = (time.monotonic() if not last['original_outer_after']['original_live']
                           else max(launched+INTERVAL_S, time.monotonic()))
    except Exception as exc:
        exit_code, reason, error = 1, 'instrumentation_failed', repr(exc)
    write_json(OUTPUT / 'result.json', dict(actual_exit=exit_code, reason=reason, instrumentation_error=error,
        pid=pid, birth=own_birth, ended_unix_s=time.time(), elapsed_s=time.monotonic()-started_monotonic,
        observations_started=count, last_observer_actual_exit=None if last is None else last['observer_actual_exit'],
        maximum_launch_window_s=MAX_SECONDS, in_flight_child_never_timed_out_or_killed=True,
        original_outer_completion_or_quality_inferred=False, CONTROL_PUBLIC_Main_fleet_actions=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
