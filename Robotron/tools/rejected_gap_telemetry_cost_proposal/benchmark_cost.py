"""Deferred synthetic helper-cost measurement; default PLAN performs no reads.

Root may execute this only after reviewing the source. This does not construct a
server, parse frames, run n-step replay, enqueue training, or measure throughput.
The single dispatch thread rotates over 192 synthetic connections; it does not
model contention between 192 concurrent client threads.
"""
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import sysconfig
import time
from types import SimpleNamespace


HELPER = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/rejected_gap_telemetry_proposal/rejected_gap_telemetry_reviewed3.py')
HELPER_SHA = 'd58610a139644b79f39504e48e1bc43bda9837cc51d743bec623103918c50cbd'
HELPER_BYTES = 12216
CLIENTS = 192
ROUNDS = 256
REPEATS = 3
GAPS = 32
MODES = ('nohooks', 'noop', 'disabled', 'enabled')
ORDERS = (MODES, tuple(reversed(MODES)), ('enabled', 'nohooks', 'disabled', 'noop'))
COMMON_HOOK_CALLS = 10
REASONS = ('parse_none', 'crash_jump', 'crash_drop')


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


def stamp():
    return time.perf_counter_ns(), time.process_time_ns()


def duration(start):
    end = stamp()
    return dict(elapsed_ns=end[0] - start[0], process_cpu_ns=end[1] - start[1])


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


def run_once(cls, mode, workload):
    states = synthetic_states()
    started = stamp()
    observer = cls(enabled=mode == 'enabled') if mode in ('disabled', 'enabled') else None
    event = observer.event if observer is not None else noop
    connections = [event('connect', cid=i) for i in range(CLIENTS)] if mode != 'nohooks' else [None] * CLIENTS
    setup = duration(started)
    require((mode != 'enabled' or len(set(connections)) == CLIENTS)
            and (mode == 'enabled' or connections == [None] * CLIENTS), 'Connection setup mismatch')
    frames = CLIENTS * ROUNDS if workload == 'no_gap' else GAPS
    started = stamp()
    if workload == 'no_gap':
        if mode == 'nohooks':
            for _ in range(ROUNDS):
                for cs in states:
                    cs['frames'] += 1
                    cs['last_game_score'] += 1
        else:
            for _ in range(ROUNDS):
                for cs, connection in zip(states, connections):
                    accepted(event, connection, cs)
    elif mode == 'nohooks':
        for cs in states[:GAPS]:
            cs['frames'] += 1
            cs['last_game_score'] += 1
    else:
        # Exactly 32 complete gaps per NEW observer; never overflow retained witnesses.
        for i in range(GAPS):
            cs, connection = states[i], connections[i]
            event('received', connection)
            event('reject', connection, reason=REASONS[i % 3], cs=cs)
            event('neutral_result', connection, ok=True)
            accepted(event, connection, cs)
    measured = duration(started)
    for i, cs in enumerate(states):
        n = ROUNDS if workload == 'no_gap' else int(i < GAPS)
        require(cs['frames'] == 16 + n and cs['last_game_score'] == 100 * (i + 1) + n,
                'Synthetic state update mismatch')
    snapshot_cost = None
    summary = None
    expected = {}
    if mode == 'enabled':
        expected = dict(connections=CLIENTS, payloads_complete=frames,
                        accepted_frames=frames)
        if workload == 'gap_burst':
            expected.update(payloads_complete=2 * GAPS, parse_none=11,
                            crash_jump=11, crash_drop=10, neutral_write_ok=GAPS,
                            gaps_opened=GAPS, accepted_closures=GAPS,
                            same_classifier_game=GAPS, previous_step_entered=GAPS,
                            nstep_add_called=GAPS, matured_total=GAPS,
                            matured_including_current_input=GAPS,
                            enqueue_calls=GAPS, enqueue_returns=GAPS,
                            including_current_input_enqueue_calls=GAPS)
    if observer is not None:
        started = stamp()
        snapshot = observer.snapshot()
        snapshot_cost = duration(started)
        kept = GAPS if mode == 'enabled' and workload == 'gap_burst' else 0
        assert_snapshot(snapshot, expected, CLIENTS if mode == 'enabled' else 0,
                        enabled=mode == 'enabled', witnesses=kept)
        for row in snapshot['witnesses']:
            require(row['same_classifier_game'] is True and row['measurement_boundary'] is False
                    and row['outcome'] == 'accepted_action_write_completed'
                    and row['enqueue_calls'] == row['enqueue_returns'] == 1,
                    'Wrong synthetic gap followthrough')
        summary = {k: snapshot[k] for k in ('enabled', 'available', 'observer_error',
                   'counter_saturated', 'active_tracked_clients', 'pending_gaps',
                   'accepted_frames_in_progress', 'counters')}
        summary['witnesses'] = len(snapshot['witnesses'])
    started = stamp()
    if mode != 'nohooks':
        for connection in connections:
            event('disconnect', connection)
    teardown = duration(started)
    if observer is not None:
        assert_snapshot(observer.snapshot(), expected, 0, enabled=mode == 'enabled',
                        witnesses=GAPS if mode == 'enabled' and workload == 'gap_burst' else 0)
    return dict(mode=mode, workload=workload, accepted_frames=frames,
                nominal_hook_calls=0 if mode == 'nohooks' else
                frames * COMMON_HOOK_CALLS + (3 * GAPS if workload == 'gap_burst' else 0),
                measured=measured,
                elapsed_ns_per_accepted_frame=measured['elapsed_ns'] / frames,
                process_cpu_ns_per_accepted_frame=measured['process_cpu_ns'] / frames,
                setup_new_instance_and_connections=setup, snapshot=snapshot_cost,
                disconnects=teardown, exact_counter_assertions_passed=True,
                diagnostic_snapshot=summary)


def execute(expected_source):
    source = Path(__file__).read_bytes()
    require(hashlib.sha256(source).hexdigest() == expected_source, 'Benchmark source SHA mismatch')
    require(sysconfig.get_config_var('Py_GIL_DISABLED') == 1
            and hasattr(sys, '_is_gil_enabled') and not sys._is_gil_enabled(),
            'Use the main free-threaded Python with -Xgil=0')
    raw = HELPER.read_bytes()
    require(len(raw) == HELPER_BYTES and hashlib.sha256(raw).hexdigest() == HELPER_SHA,
            'Exact reviewed3 helper required')
    namespace = {'__name__': '_root_deferred_rejected_gap_cost', '__file__': str(HELPER)}
    # Deliberately executed ONLY by root's explicit future --execute action.
    exec(compile(raw, str(HELPER), 'exec'), namespace)
    require(not sys._is_gil_enabled(), 'An import unexpectedly enabled the GIL')
    cls = namespace['RejectedGapTelemetry']
    overall = time.perf_counter_ns()
    rows = []
    for repeat, order in enumerate(ORDERS):
        for mode in order:
            require(time.perf_counter_ns() - overall < 45_000_000_000,
                    'Fixed benchmark exceeded internal 45s budget; no retry')
            row = run_once(cls, mode, 'no_gap')
            row['repeat'] = repeat
            rows.append(row)
    bursts = [run_once(cls, mode, 'gap_burst') for mode in MODES]
    summaries = {}
    for mode in MODES:
        selected = [row for row in rows if row['mode'] == mode]
        summaries[mode] = {metric: statistics.median(row[metric] for row in selected)
                           for metric in ('elapsed_ns_per_accepted_frame',
                                          'process_cpu_ns_per_accepted_frame')}
    differences = []
    for repeat in range(REPEATS):
        paired = {row['mode']: row for row in rows if row['repeat'] == repeat}
        differences.append(dict(repeat=repeat, **{
            mode + '_minus_' + base + '_process_cpu_ns_per_accepted_frame':
            paired[mode]['process_cpu_ns_per_accepted_frame'] - paired[base]['process_cpu_ns_per_accepted_frame']
            for mode, base in (('noop', 'nohooks'), ('disabled', 'noop'),
                               ('enabled', 'disabled'), ('enabled', 'nohooks'))}))
    return dict(schema='robotron-rejected-gap-synthetic-cost-v1', status='PASS_SYNTHETIC_COST_ONLY',
                source_sha256=expected_source, helper=dict(path=str(HELPER), sha256=HELPER_SHA, bytes=HELPER_BYTES),
                python=dict(executable=sys.executable, version=sys.version,
                            Py_GIL_DISABLED=sysconfig.get_config_var('Py_GIL_DISABLED'),
                            gil_enabled=sys._is_gil_enabled()),
                parameters=dict(clients=CLIENTS, rounds_per_client=ROUNDS, repeats=REPEATS,
                                accepted_hook_calls=COMMON_HOOK_CALLS,
                                gap_burst_per_fresh_instance=GAPS, orders=ORDERS),
                observer_reset='NEW instance and 192 connections before each measurement; no reset API exists',
                no_gap_runs=rows, no_gap_medians=summaries, paired_cpu_differences=differences,
                gap_bursts=bursts,
                scope='Single dispatch thread over synthetic metadata; no sockets, handler, nstep/add, replay enqueue, inference, training or model data.',
                limitations=['The nohooks loop is a loop/update control; noop includes the ten hooks and keyword construction.',
                             'The synthetic mature n3 path assumes one emitted learner prefix and successful action/enqueue calls; it does not execute those operations.',
                             '192 connections do not simulate 192 simultaneous threads or lock contention. CPU quota and host scheduling affect wall time.',
                             '32-gap burst is a small bounded sample; no population rejection rate, production throughput, noninterference or learning claim follows.',
                             'Subtracted small timings may be noisy or negative. No automatic enable/change decision is made.'])


def main():
    if len(sys.argv) == 1:
        print('PLAN: deferred synthetic rejected-gap helper cost; root execution required')
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
    exit_code = 0
    try:
        result = execute(args.expected_source_sha256)
    except Exception as exc:
        result = dict(schema='robotron-rejected-gap-synthetic-cost-v1',
                      status='ERROR_ORIGINAL_BENCHMARK_NO_RETRY', error_type=type(exc).__name__,
                      error=str(exc), actual_results_qualified=False)
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
    print(json.dumps(dict(status=result['status'], output=str(output), sha256=hashlib.sha256(data).hexdigest())))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
