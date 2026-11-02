#!/usr/bin/env python3
"""Alternate live batch-size trials, preserve checkpoints, leave winner running.

Run with no other trainer active. Measurements exclude each process's first
report and use three subsequent 30-second intervals with all 16 actors present.
"""
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'logs' / ('batch-tuning-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
OUT.mkdir(parents=True)
( ROOT / 'logs' / 'batch-tuning' / 'latest.txt').write_text(str(OUT))
RESULTS = []
ACTIVE = None


def log(message):
    print('[BATCH TUNER] ' + message, flush=True)


def fleet(*args, directory=OUT):
    with (directory / 'fleet.log').open('a') as stream:
        subprocess.run([str(ROOT / 'startmame.sh'), *args], cwd=ROOT,
                       env={**os.environ, 'MAME_BIN': '/usr/games/mame', 'SDL_VIDEODRIVER': 'dummy'},
                       stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=45)


def stop():
    global ACTIVE
    if ACTIVE is None:
        return
    process, _, thread = ACTIVE
    fleet('-kill')
    log(f'Saving checkpoint/replay and stopping PID {process.pid}')
    process.send_signal(signal.SIGINT)
    process.wait(timeout=240)
    thread.join(timeout=5)
    ACTIVE = None


def forward(process, directory):
    with (directory / 'console.log').open('w') as stream:
        for line in process.stdout:
            stream.write(line)
            stream.flush()
            print(line, end='', flush=True)


def start(batch, name):
    global ACTIVE
    directory = OUT / name
    directory.mkdir()
    env = {**os.environ, 'DQN_BATCH_SIZE': str(batch), 'ROBOTRON_RUN_DIR': str(directory),
           'DQN_RATCHET': '0'}
    log(f'Starting {name}, batch={batch}, preserving model/optimizer/replay')
    process = subprocess.Popen([str(ROOT / 'starttrainer.sh')], cwd=ROOT,
                               env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1)
    thread = threading.Thread(target=forward, args=(process, directory), daemon=True)
    thread.start()
    ACTIVE = process, directory, thread
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Trainer exited: {process.returncode}')
        path = directory / 'console.log'
        if path.exists() and 'SocketServer listening on' in path.read_text(errors='replace'):
            fleet('16', 'novideo', directory=directory)
            return directory
        time.sleep(1)
    raise TimeoutError('Trainer startup timed out')


def measure(batch, name):
    stop()
    directory = start(batch, name)
    path = directory / 'training.csv'
    deadline = time.monotonic() + 270
    last_report = 0
    while time.monotonic() < deadline:
        if ACTIVE[0].poll() is not None:
            raise RuntimeError('Trainer exited during trial')
        rows = []
        if path.exists():
            with path.open() as stream:
                # Drop the baseline row: it has no rate and no GPU samples.
                rows = list(csv.DictReader(stream))[1:]
            rows = [row for row in rows if int(row.get('clients') or 0) == 16
                    and float(row.get('samples_per_s') or 0) > 0
                    and row.get('gpu_util_pct') not in ('', None)]
        if len(rows) != last_report:
            last_report = len(rows)
            log(f'{name}: collected {last_report}/3 steady reporting intervals')
        if len(rows) >= 3:
            keys = ['frames_per_s', 'samples_per_s', 'inference_ms', 'steps_per_s',
                    'gpu_util_pct', 'gpu_power_w', 'gpu_memory_mib', 'gpu_compute_ms',
                    'samples_per_frame', 'sample_wall_ms', 'priority_and_readback_ms',
                    'eval_score', 'eval_level', 'replay_dropped', 'prefetched_batches', 'steps']
            result = {'name': name, 'batch': batch,
                      **{key: statistics.mean(float(row[key]) for row in rows[-3:]) for key in keys},
                      'rows': rows[-3:]}
            RESULTS.append(result)
            (OUT / 'results.json').write_text(json.dumps(RESULTS, indent=2))
            with (OUT / 'results.csv').open('w', newline='') as stream:
                fields = ['name', 'batch', *keys]
                writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(RESULTS)
            log(f"{name} RESULT: {result['frames_per_s']:.0f} FPS, "
                f"{result['samples_per_s']:.0f} samples/s, "
                f"{result['inference_ms']:.2f}ms inference, {result['gpu_util_pct']:.1f}% GPU")
            return result
        time.sleep(2)
    raise TimeoutError('Not enough valid measurement intervals')


def rankings():
    groups = {}
    for result in RESULTS:
        groups.setdefault(result['batch'], []).append(result)
    # Equal weight to fresh experience and optimization; at the fixed replay
    # cap these largely track together. Geometric mean avoids unit scaling.
    ranked = []
    for batch, results in groups.items():
        fps = statistics.mean(r['frames_per_s'] for r in results)
        samples = statistics.mean(r['samples_per_s'] for r in results)
        ranked.append((math.sqrt(fps * samples), batch))
    return sorted(ranked, reverse=True)


if __name__ == '__main__':
    log(f'Results directory: {OUT}')
    # Alternate endpoints first, then intermediate sizes, then reconfirm the
    # best two in reverse order to reduce sequential policy/episode drift.
    for i, batch in enumerate((2048, 8192, 4096, 6144), 1):
        measure(batch, f'{i:02d}-batch-{batch}')
    finalists = [batch for _, batch in rankings()[:2]]
    for i, batch in enumerate(reversed(finalists), 5):
        measure(batch, f'{i:02d}-confirm-{batch}')
    winner = rankings()[0][1]
    log(f'Selected batch={winner}; starting continuing training')
    if int(RESULTS[-1]['batch']) != winner:
        stop()
        start(winner, f'continue-batch-{winner}')
    selection = dict(batch=winner, trainer_pid=ACTIVE[0].pid,
                     run_directory=str(ACTIVE[1]), rankings=rankings(),
                     criterion='Geometric mean of mean FPS and training samples/s; top two repeated',
                     note='Live sequential trials; evaluates throughput, not long-run policy quality.')
    (OUT / 'selection.json').write_text(json.dumps(selection, indent=2))
    log(f'DONE: training continues at batch {winner}, PID {ACTIVE[0].pid}')
    ACTIVE[0].wait()
