"""Capture original R1 OS counters without signals, attachments or GPU imports."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).parent
OUT = N / 'readonly-private-native-CPU-thread-split-original01'
D = N / '01-reference/diagnostic-output-original01'
PID = 437094
BIRTH = 105466651


def decode_stat(raw):
    values = raw.rsplit(')', 1)[1].split()
    return dict(comm=raw.split('(', 1)[1].rsplit(')', 1)[0],
                state=values[0], utime_ticks=int(values[11]),
                stime_ticks=int(values[12]), birth=int(values[19]))


def capture(stage):
    helper = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    spec = importlib.util.spec_from_file_location('_cpu_capture_h', helper)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    assert stage in ('before', 'after')
    assert OUT.parent == N and OUT.resolve() == OUT
    OUT.mkdir(mode=0o700, exist_ok=True)
    output = OUT / (stage + '.json')
    assert not output.exists()
    begin = time.monotonic_ns()
    observed = time.time()
    native_raw = Path('/proc', str(PID), 'stat').read_text()
    assert decode_stat(native_raw)['birth'] == BIRTH
    cg_raw = Path('/proc', str(PID), 'cgroup').read_text()
    lines = cg_raw.strip().splitlines()
    assert len(lines) == 1 and lines[0].startswith('0::')
    cg = Path('/sys/fs/cgroup') / lines[0][3:].lstrip('/')
    cg_info = cg.stat()
    resources = {name: (cg / name).read_text() for name in
                 ['cpu.stat', 'cpu.max', 'pids.current', 'pids.max', 'pids.peak',
                  'memory.current', 'memory.peak', 'memory.max', 'memory.events']}
    assert resources['cpu.max'].strip() == '1200000 100000'
    assert resources['pids.max'].strip() == '512'
    assert resources['memory.max'].strip() == str(16 << 30)
    status = json.loads((D / 'status.json').read_bytes())
    assert time.time() - status['observed_unix_s'] < 15 and not status['errors']
    assert sorted(map(int, status['slots'])) == list(range(4096, 4128))
    actors = []
    for slot, current in sorted(status['slots'].items()):
        actor_path = D / 'actors' / slot / 'original-actor.json'
        actor = json.loads(actor_path.read_bytes())
        assert current['pid'] == actor['pid']
        raw = Path('/proc', str(actor['pid']), 'stat').read_text()
        assert decode_stat(raw)['birth'] == actor['starttime_ticks'] == current['birth']
        assert Path('/proc', str(actor['pid']), 'cmdline').read_bytes().rstrip(b'\0').decode().split('\0') == actor['argv']
        actors.append(dict(slot=int(slot), original_actor=h.pin(actor_path),
                           pid=actor['pid'], raw_stat=raw, parsed=decode_stat(raw),
                           accepted_sequence=current['sequence']))
    threads = []
    disappeared = []
    for task in sorted(Path('/proc', str(PID), 'task').iterdir(), key=lambda p: int(p.name)):
        try:
            raw = (task / 'stat').read_text()
        except (FileNotFoundError, ProcessLookupError):
            disappeared.append(int(task.name))
            continue
        threads.append(dict(tid=int(task.name), raw_stat=raw, parsed=decode_stat(raw)))
    assert decode_stat(Path('/proc', str(PID), 'stat').read_text())['birth'] == BIRTH
    end = time.monotonic_ns()
    report = dict(schema='robotron-original-private-CPU-counter-snapshot-v1',
                  stage=stage, source=h.pin(__file__), observed_unix_s=observed,
                  begin_monotonic_ns=begin, end_monotonic_ns=end,
                  capture_midpoint_monotonic_ns=(begin + end) // 2,
                  clock_ticks_per_second=os.sysconf('SC_CLK_TCK'),
                  original_native_owner=h.pin(N / '01-reference/execution-original01/root-original-identity.json'),
                  original_job=h.pin(N / '01-reference/job.json'), native_pid=PID,
                  native_raw_stat=native_raw, native_parsed=decode_stat(native_raw),
                  cgroup_raw=cg_raw, cgroup_path=str(cg),
                  cgroup_identity=dict(device=cg_info.st_dev, inode=cg_info.st_ino),
                  resources_raw=resources, actors=actors, threads=threads,
                  thread_reads_disappeared=disappeared,
                  native_status_observed_unix_s=status['observed_unix_s'],
                  cohort={k: status['controller']['cohort'][k] for k in
                          ['count', 'started', 'pending', 'abandoned', 'mean', 'median']},
                  profiler_attached=False, process_signals_sent=False,
                  GPU_context_created=False, scientific_runtime_changed=False)
    pin = h.put(output, report)
    print(json.dumps(dict(snapshot=pin, stage=stage, actors=len(actors),
                          threads=len(threads), capture_ms=(end - begin) / 1e6)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', choices=('before', 'after'))
    args = parser.parse_args()
    if args.capture is None:
        print('PLAN_ONLY: no input reads, captures, signals, attachments or GPU work')
        return 0
    capture(args.capture)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
