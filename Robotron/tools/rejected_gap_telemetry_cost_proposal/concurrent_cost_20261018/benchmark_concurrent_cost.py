"""Unexecuted concurrent synthetic cost proposal; no-argument PLAN reads nothing.

Only root's explicit future --execute loads the pinned stdlib helper. Each arm
uses 192 real free-threaded Python workers and fresh primitive client metadata.
No server, socket, project module, model, replay or device work is performed.
"""
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import queue
import stat
import statistics
import sys
import sysconfig
import threading
import time
from types import SimpleNamespace

HELPER = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/rejected_gap_telemetry_proposal/rejected_gap_telemetry_reviewed3.py')
HELPER_SHA = 'd58610a139644b79f39504e48e1bc43bda9837cc51d743bec623103918c50cbd'
HELPER_BYTES = 12216
PREDECESSOR = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/rejected_gap_telemetry_cost_proposal/benchmark_cost.py')
PREDECESSOR_SHA = '5ef1db71cdabf8bbca4f560799fe041164757f437d65c64c951e92eba79f0794'
PREDECESSOR_BYTES = 14596
CLIENTS = 192
FRAMES = 128
REPEATS = 3
COMMON_HOOK_CALLS = 10
MODES = ('nohooks', 'noop', 'disabled', 'enabled')
# Three rows of a four-arm balanced design: each arm occupies three positions.
# This is partial counterbalance, not perfect four-position balance/randomization.
ORDERS = (('nohooks', 'noop', 'enabled', 'disabled'),
          ('noop', 'disabled', 'nohooks', 'enabled'),
          ('disabled', 'enabled', 'noop', 'nohooks'))
SCHEMA = 'robotron-rejected-gap-concurrent-synthetic-cost-v1'

COUNTERS = (
    "connections", "tracking_overflow", "payloads_complete", "param_mismatch",
    "short_payload", "receive_header_idle", "receive_header_eof", "receive_invalid_length",
    "receive_broken_payload", "parse_none", "crash_jump", "crash_drop", "accepted_frames",
    "neutral_write_ok", "neutral_write_failed", "gaps_opened", "accepted_closures",
    "disconnect_closures", "same_classifier_game", "new_game_classified",
    "measurement_boundary", "previous_step_entered", "nstep_add_called",
    "one_step_called", "matured_total", "group_flush_before_input",
    "matured_including_current_input", "enqueue_calls", "enqueue_returns",
    "including_current_input_enqueue_calls", "witness_overflow",
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def noop(kind, connection=None, **data):
    return None


def synthetic_states():
    # Primitive metadata only. Sentinels are never a model/replay state array.
    return [dict(game_uid=i + 1, client_slot=i, frames=16,
                 last_state=True, last_action=(1, 1), prev_action_source='dqn',
                 frame_history=deque((True, True, True), maxlen=4),
                 nstep=SimpleNamespace(_deque=deque((SimpleNamespace(actor='dqn'),
                                                   SimpleNamespace(actor='dqn')))),
                 measurement_generation=0, measurement_active=False,
                 was_done=False, player_alive=True,
                 last_game_score=100 * (i + 1), last_level_number=2)
            for i in range(CLIENTS)]


def accepted(event, connection, cs):
    """The ten accepted-frame observation calls in b095/ecc2's mature n3 path.

    The real caller's nstep/add/enqueue/action work between these hooks is absent.
    One synthetic matured learner prefix, one successful enqueue return, no reset,
    no terminal, and a successful action write are declared workload assumptions.
    """
    event('received', connection)
    ticket = event('accepted', connection, cs=cs,
                   score=int(cs['last_game_score']), wave=int(cs['last_level_number']),
                   alive=bool(cs['player_alive']), done=False, new_game=False)
    cs['frames'] += 1
    event('after_reset', ticket, cs=cs, writable=True)
    event('previous_step', ticket)
    event('nstep_before', ticket, nstep=cs['nstep'], actor='dqn', done=False)
    event('nstep_after', ticket, count=1)
    event('enqueue_called', ticket)
    event('enqueue_returned', ticket)
    cs['last_game_score'] += 1
    event('next_action', ticket, cs=cs)
    event('finish', ticket, outcome='accepted_action_write_completed')


def assert_snapshot(snapshot, counters, count, *, enabled, witnesses):
    require(snapshot['schema'] == 'robotron-rejected-gap-observation-v1', 'Wrong helper schema')
    require(snapshot['enabled'] is enabled and snapshot['available'] is enabled,
            'Availability differs from intentional mode')
    require(snapshot['observer_error'] is False and snapshot['counter_saturated'] is False,
            'Observer fault or saturation')
    require(snapshot['active_tracked_clients'] == count and snapshot['pending_gaps'] == 0
            and snapshot['accepted_frames_in_progress'] == 0, 'Unclosed synthetic state')
    require(snapshot['witness_limit'] == 32 and len(snapshot['witnesses']) == witnesses,
            'Unexpected witness count')
    expected = dict.fromkeys(snapshot['counters'], 0)
    expected.update(counters)
    require(snapshot['counters'] == expected, 'Unexpected exact diagnostic counters')


def stamp():
    return time.perf_counter_ns(), time.process_time_ns()


def duration(start):
    end = stamp()
    return dict(elapsed_ns=end[0] - start[0], process_cpu_ns=end[1] - start[1])


def source_bytes(path, expected_sha, expected_bytes=None):
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o444
            and before.st_uid == os.getuid() and before.st_nlink == 1,
            'Source must be an owned regular readonly single-link file: ' + str(path))
    raw = path.read_bytes()
    after = path.lstat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_uid', 'st_nlink',
              'st_mtime_ns', 'st_ctime_ns')
    require(all(getattr(before, k) == getattr(after, k) for k in fields),
            'Source identity changed while reading: ' + str(path))
    require(hashlib.sha256(raw).hexdigest() == expected_sha
            and (expected_bytes is None or len(raw) == expected_bytes),
            'Source bytes mismatch: ' + str(path))
    return raw, dict(path=str(path), sha256=expected_sha, bytes=len(raw),
                     identity={k: getattr(after, k) for k in fields})


def guard(expected_source):
    require(sysconfig.get_config_var('Py_GIL_DISABLED') == 1
            and hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled(),
            'Use free-threaded CPython with -Xgil=0')
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == ''
            and not os.environ.get('LD_PRELOAD') and not os.environ.get('PYTHONPATH'),
            'Root must hide CUDA and remove preload/pythonpath')
    require(not any(name.split('.')[0] in ('torch', 'numpy', 'dqn') for name in sys.modules),
            'A scientific/project module is already loaded')
    own, a = source_bytes(Path(__file__).absolute(), expected_source)
    raw, b = source_bytes(HELPER, HELPER_SHA, HELPER_BYTES)
    _, c = source_bytes(PREDECESSOR, PREDECESSOR_SHA, PREDECESSOR_BYTES)
    return raw, [a, b, c]


def remaining(deadline):
    value = deadline - time.perf_counter()
    require(value > 0, 'Original internal 45s budget exhausted; no retry')
    return value


def run_once(cls, mode, deadline, live_progress):
    started_setup = stamp()
    states = synthetic_states()
    observer = cls(enabled=mode == 'enabled') if mode in ('disabled', 'enabled') else None
    event = observer.event if observer is not None else noop
    connections = [None] * CLIENTS
    native_ids = [None] * CLIENTS
    completed_frames = [0] * CLIENTS
    worker_ends = [None] * CLIENTS
    errors = queue.Queue(maxsize=CLIENTS)
    ready = threading.Barrier(CLIENTS + 1)
    start_gate = threading.Event()
    release_gate = threading.Event()
    all_done = threading.Event()
    done_lock = threading.Lock()
    done_count = 0
    workers = []
    live_progress.update(mode=mode, stage='worker_setup', workers_started=0)

    def worker(index):
        nonlocal done_count
        try:
            native_ids[index] = threading.get_native_id()
            require(not sys._is_gil_enabled(), 'Worker GIL unexpectedly enabled')
            connection = event('connect', cid=index) if mode != 'nohooks' else None
            connections[index] = connection
            ready.wait(timeout=min(8.0, remaining(deadline)))
            require(start_gate.wait(timeout=remaining(deadline)), 'Start gate timed out')
            cs = states[index]
            if mode == 'nohooks':
                for _ in range(FRAMES):
                    cs['frames'] += 1
                    cs['last_game_score'] += 1
                    completed_frames[index] += 1
            else:
                for _ in range(FRAMES):
                    accepted(event, connection, cs)
                    completed_frames[index] += 1
            worker_ends[index] = stamp()
        except BaseException as exc:
            errors.put_nowait(dict(worker=index, error_type=type(exc).__name__,
                                   error=str(exc)[:512]))
        finally:
            with done_lock:
                done_count += 1
                if done_count == CLIENTS:
                    all_done.set()
            # Keep completed threads alive: their teardown occurs after timing.
            release_gate.wait(timeout=max(0.0, deadline - time.perf_counter()))

    try:
        for index in range(CLIENTS):
            thread = threading.Thread(target=worker, args=(index,),
                                      name='synthetic-cost-' + str(index), daemon=True)
            thread.start()
            workers.append(thread)
            live_progress['workers_started'] = len(workers)
        ready.wait(timeout=min(8.0, remaining(deadline)))
        require(errors.empty(), 'Worker setup failed')
        require(len(set(native_ids)) == CLIENTS and all(type(x) is int and x > 0 for x in native_ids)
                and all(thread.is_alive() for thread in workers), 'Need 192 distinct live native workers')
        require((mode == 'enabled' and len(set(connections)) == CLIENTS
                 and all(type(x) is int for x in connections))
                or (mode != 'enabled' and connections == [None] * CLIENTS),
                'Connection setup mismatch')
        setup = duration(started_setup)
        live_progress['stage'] = 'timed_frames'
        started = stamp()
        start_gate.set()
        require(all_done.wait(timeout=remaining(deadline)), 'Original worker cohort timed out')
        failures = []
        while not errors.empty():
            failures.append(errors.get_nowait())
        live_progress['worker_failures'] = failures
        require(not failures, 'Worker failure: ' + repr(failures))
        require(completed_frames == [FRAMES] * CLIENTS
                and all(pair is not None for pair in worker_ends), 'A worker missed frames/end clock')
        # Endpoint is the last worker's end clock, before main coordination/join.
        end = max(worker_ends, key=lambda pair: pair[0])
        measured = dict(elapsed_ns=end[0] - started[0], process_cpu_ns=end[1] - started[1])
        require(measured['elapsed_ns'] > 0 and measured['process_cpu_ns'] > 0,
                'Invalid measurement clocks')
    finally:
        original_exception_in_flight = sys.exc_info()[0] is not None
        release_gate.set()
        start_gate.set()
        ready.abort()
        joined = stamp()
        join_deadline = time.perf_counter() + min(2.0, max(0.0, deadline - time.perf_counter()))
        for thread in workers:
            thread.join(timeout=max(0.0, join_deadline - time.perf_counter()))
        join_cost = duration(joined)
        live_progress['workers_still_alive'] = sum(thread.is_alive() for thread in workers)
        live_progress['completed_frames_by_worker'] = list(completed_frames)
        if not original_exception_in_flight:
            require(not live_progress['workers_still_alive'], 'Original worker teardown incomplete')
    for index, cs in enumerate(states):
        require(cs['frames'] == 16 + FRAMES
                and cs['last_game_score'] == 100 * (index + 1) + FRAMES,
                'Synthetic per-connection state mismatch')
    frames = CLIENTS * FRAMES
    expected = (dict(connections=CLIENTS, payloads_complete=frames, accepted_frames=frames)
                if mode == 'enabled' else {})
    snapshot_cost = None
    snapshot = None
    if observer is not None:
        start = stamp()
        snapshot = observer.snapshot()
        snapshot_cost = duration(start)
        require(set(snapshot['counters']) == set(COUNTERS), 'Wrong exact counter name set')
        assert_snapshot(snapshot, expected, CLIENTS if mode == 'enabled' else 0,
                        enabled=mode == 'enabled', witnesses=0)
    start = stamp()
    if mode != 'nohooks':
        for connection in connections:
            event('disconnect', connection)
    disconnect_cost = duration(start)
    if observer is not None:
        assert_snapshot(observer.snapshot(), expected, 0, enabled=mode == 'enabled', witnesses=0)
    live_progress['stage'] = 'complete'
    return dict(mode=mode, accepted_frames=frames, workers=CLIENTS,
                frames_per_worker=FRAMES, distinct_native_worker_ids=sorted(native_ids),
                completed_frames_per_worker=completed_frames,
                nominal_hook_calls=0 if mode == 'nohooks' else frames * COMMON_HOOK_CALLS,
                measured=measured,
                elapsed_ns_per_accepted_frame=measured['elapsed_ns'] / frames,
                process_cpu_ns_per_accepted_frame=measured['process_cpu_ns'] / frames,
                process_cpu_to_elapsed_ratio=measured['process_cpu_ns'] / measured['elapsed_ns'],
                setup_including_thread_creation_connect_ready_barrier=setup,
                worker_release_and_join=join_cost, snapshot=snapshot_cost,
                disconnects=disconnect_cost, diagnostic_snapshot=snapshot,
                exact_state_and_counter_assertions_passed=True,
                absent_helper_counters='no helper exists in nohooks/noop arms; snapshot is null')


def execute(expected_source, progress):
    raw, initial_pins = guard(expected_source)
    namespace = {'__name__': '_root_concurrent_rejected_gap_cost', '__file__': str(HELPER)}
    # Root's future --execute is the only code path that compiles/executes helper.
    exec(compile(raw, str(HELPER), 'exec'), namespace)
    require(tuple(namespace['COUNTERS']) == COUNTERS, 'Exact helper counter contract changed')
    _, after_load_pins = guard(expected_source)
    require(after_load_pins == initial_pins, 'Source identity changed during helper loading')
    cls = namespace['RejectedGapTelemetry']
    deadline = time.perf_counter() + 45.0
    rows = progress['completed_runs']
    for repeat, order in enumerate(ORDERS):
        for position, mode in enumerate(order):
            remaining(deadline)
            _, before = guard(expected_source)
            require(before == initial_pins, 'Source drift before arm')
            progress['current_arm'] = dict(repeat=repeat, position=position, mode=mode)
            row = run_once(cls, mode, deadline, progress['current_arm'])
            _, after = guard(expected_source)
            require(after == before, 'Source drift after arm')
            row.update(repeat=repeat, position=position,
                       source_and_free_threading_checks_before_after=True)
            rows.append(row)
    _, final_pins = guard(expected_source)
    require(final_pins == initial_pins, 'Source drift at final boundary')
    summaries = {mode: {metric: statistics.median(row[metric] for row in rows if row['mode'] == mode)
                        for metric in ('elapsed_ns_per_accepted_frame',
                                       'process_cpu_ns_per_accepted_frame')}
                 for mode in MODES}
    differences = []
    for repeat in range(REPEATS):
        paired = {row['mode']: row for row in rows if row['repeat'] == repeat}
        differences.append(dict(repeat=repeat, **{
            mode + '_minus_' + base + '_' + metric:
            paired[mode][metric] - paired[base][metric]
            for mode, base in (('noop', 'nohooks'), ('disabled', 'noop'),
                               ('enabled', 'disabled'), ('enabled', 'nohooks'))
            for metric in ('elapsed_ns_per_accepted_frame', 'process_cpu_ns_per_accepted_frame')}))
    return dict(schema=SCHEMA, status='PASS_CONCURRENT_SYNTHETIC_COST_ONLY',
                actual_results_qualified=False, source_sha256=expected_source,
                source_pins_before=initial_pins, source_pins_after=final_pins,
                python=dict(executable=sys.executable, version=sys.version,
                            Py_GIL_DISABLED=sysconfig.get_config_var('Py_GIL_DISABLED'),
                            gil_enabled=sys._is_gil_enabled()),
                parameters=dict(clients=CLIENTS, frames_per_worker=FRAMES,
                                repeats=REPEATS, accepted_hook_calls=COMMON_HOOK_CALLS,
                                orders=ORDERS, workload='accepted_no_gap_only'),
                timing='Starts immediately before start_gate.set; ends at last worker frame-loop clock. '
                       'Thread creation/connect/ready barrier and thread teardown are excluded. '
                       'Gate wakeups, scheduling, per-worker loop counters and earlier-worker completion '
                       'coordination remain within the measured span. CPU is process-wide.',
                no_gap_runs=rows, medians=summaries, paired_differences=differences,
                scope='192 native FT threads over primitive metadata; no sockets, real handler, nstep/add, '
                      'replay enqueue, inference, training, models or GPU.',
                limitations=['Three fixed orders partially counterbalance four positions; no randomization.',
                             'Continuous back-to-back synthetic threads differ from real connection duty cycles. '
                             'This is neither an observed live overhead nor a production upper bound.',
                             'Four-CPU quota, host scheduling, synthetic loop bookkeeping and short spans '
                             'affect wall/CPU differences; negative/noisy differences remain reported.',
                             'Nohooks is a loop/update control. Noop includes the same ten calls and kwargs; '
                             'disabled invokes real disabled helper; enabled counts received and accepted '
                             'under one shared lock, with eight no-ticket pre-lock returns.',
                             'No rejection/gap burst, quality/learning outcome, causal speed claim or '
                             'automatic enable/control/source decision is made.'])


def main():
    if len(sys.argv) == 1:
        print('PLAN: deferred 192-thread rejected-gap synthetic cost; no reads/actions')
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', required=True)
    parser.add_argument('--expected-source-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    require(output.is_absolute() and output.suffix == '.json'
            and output.parent.is_dir() and not output.exists(), 'Require fresh absolute JSON output')
    require(len(args.expected_source_sha256) == 64
            and all(x in '0123456789abcdef' for x in args.expected_source_sha256), 'Malformed source SHA')
    progress = dict(completed_runs=[], current_arm=None)
    exit_code = 0
    try:
        result = execute(args.expected_source_sha256, progress)
    except Exception as exc:
        result = dict(schema=SCHEMA, status='ERROR_ORIGINAL_CONCURRENT_BENCHMARK_NO_RETRY',
                      source_sha256=args.expected_source_sha256,
                      error_type=type(exc).__name__, error=str(exc),
                      original_progress=progress, actual_results_qualified=False)
        exit_code = 1
    data = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(output.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    print(json.dumps(dict(status=result['status'], output=str(output),
                          sha256=hashlib.sha256(data).hexdigest())))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
