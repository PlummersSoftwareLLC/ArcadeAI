"""Root read-only observer of one explicitly launched original quality job.

No project imports, model reads, process signals, retries, or state.json writes.
Stops to notify root when a leg after --observed-through finishes, campaign ends,
or a health problem is observed. Explicit execute only; default PLAN makes no reads.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path('/home/dave/source/repos/ArcadeAI')
BASE = ROOT / 'Robotron/logs/managed-learning-20261015'
RUN = BASE / 'run-26'
QUALITY = BASE / 'quality-CE543M-vs-retained-CE2048-first8M-trial02-20261017'
OUT = None
UNIT = 'robotron-quality-CE543M-vs-CE2048-first8M-trial02-followup-20261017.service'
PLAN = 'fdb13f963f7433d8dcd816934fe266f327760a7953d47a1208f752f284d5fe85'
MAIN = 1626184
MAIN_START = 36413669
PARENT = 1673818
PARENT_START = 36563185
INVOCATION = '942c390f35d84884bd41f3d04ac9d7ff'
GPU1 = 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'


def write(name, raw):
    with (OUT / name).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    fd = os.open(OUT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(name, value):
    write(name, (json.dumps(value, indent=2, allow_nan=False) + '\n').encode())


def ticks(pid):
    return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])


def call(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    return dict(argv=argv, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


def main(argv=None):
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--observed-through', type=int, choices=(1, 2, 3))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no reads, queries, process observations or output')
        return 0
    if args.observed_through is None or args.output is None:
        parser.error('--execute requires --observed-through and --output')
    OUT = args.output
    assert OUT.is_absolute() and OUT.parent == RUN and not os.path.lexists(OUT), 'Fresh direct run26 output required'
    OUT.mkdir()
    assert hashlib.sha256((QUALITY / 'plan.json').read_bytes()).hexdigest() == PLAN
    start = time.monotonic()
    while time.monotonic() - start < 3000:
        stamp = str(time.time_ns())
        item = dict(observed_unix_s=time.time(), quality_plan_sha256=PLAN,
                    readonly=True, original_job=True, automatic_retry=False,
                    observed_through=args.observed_through, target_leg=args.observed_through + 1)
        try:
            status_raw = (QUALITY / 'status.json').read_bytes()
            write(stamp + '-campaign-status.json', status_raw)
            status = json.loads(status_raw)
            assert status['plan_sha256'] == PLAN
            item['campaign'] = status
            query = call(['systemctl', '--user', 'show', UNIT,
                          '--property=MainPID,ExecMainPID,InvocationID,NRestarts,SubState,ExecMainCode,ExecMainStatus,Result'])
            item['parent_unit'] = query
            assert query['returncode'] == 0
            unit = dict(line.split('=', 1) for line in query['stdout'].splitlines() if '=' in line)
            assert unit['InvocationID'] == INVOCATION and unit['NRestarts'] == '0' and unit['ExecMainPID'] == str(PARENT)
            if status['state'] == 'running':
                assert unit['MainPID'] == str(PARENT) and ticks(PARENT) == PARENT_START
            assert ticks(MAIN) == MAIN_START
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
                api_raw = response.read()
            write(stamp + '-api.raw.json', api_raw)
            api = json.loads(api_raw)
            pipeline = api['host_pipeline']
            graph = pipeline['inference_graphs']
            errors = {name: pipeline[name]['errors'] for name in
                      ('inference', 'actor_refresh', 'target_refresh', 'learner_priority')}
            item['main'] = {key: api[key] for key in
                            ('ts', 'client_count', 'training_enabled', 'measurement_active',
                             'learner_frame_count', 'frame_count', 'training_steps', 'optimized_samples')}
            item['main'].update(pid=MAIN, starttime_ticks=MAIN_START, pipeline_errors=errors,
                                graph={key: graph[key] for key in
                                       ('ready', 'capture_count', 'validation_replay_count',
                                        'runtime_capture_count', 'fallback_count', 'fatal_error')})
            assert api['client_count'] == 192 and api['training_enabled'] and not api['measurement_active']
            assert all(pipeline['learning_exposure'][name]['process_id'] == MAIN for name in ('optimizer', 'replay'))
            assert not any(errors.values())
            assert graph['ready'] and graph['capture_count'] == 128 and graph['validation_replay_count'] == 640
            assert graph['runtime_capture_count'] == graph['fallback_count'] == 0 and graph['fatal_error'] is None
            latest = ROOT / 'Robotron/models_dqn/robotron_dqn_latest.pt'
            stat = latest.stat()
            item['main']['autosave_age_s'] = time.time() - stat.st_mtime
            item['main']['autosave_bytes'] = stat.st_size
            assert 0 <= item['main']['autosave_age_s'] <= 600
            gpu = call(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader,nounits'])
            item['GPU_owners'] = gpu
            assert gpu['returncode'] == 0
            rows = [(int(line.split(',')[0]), line.split(',')[1].strip())
                    for line in gpu['stdout'].splitlines() if line.strip()]
            assert [(pid, uuid) for pid, uuid in rows if uuid == GPU1] == [(MAIN, GPU1)]
            current = next((leg for leg in status['legs'] if leg['index'] == status.get('current_leg')), None)
            if current:
                ep = Path(current['evaluator_status_path'])
                if ep.exists():
                    raw = ep.read_bytes()
                    write(stamp + '-evaluator-status.json', raw)
                    es = json.loads(raw)
                    item['evaluator'] = {key: es.get(key) for key in
                                         ('phase', 'valid', 'complete', 'reason', 'start_ts', 'close_ts',
                                          'count', 'started', 'pending', 'abandoned', 'boundary', 'job', 'actor_pids')}
                else:
                    item['evaluator'] = dict(phase='startup_before_first_status', pid=current['pid'])
            item['status'] = 'PASS_READONLY_OBSERVATION'
            completed = [leg['index'] for leg in status['legs'] if leg['state'] == 'finished']
            save(stamp + '-observation.json', item)
            print(json.dumps(dict(status=item['status'], observed_unix_s=item['observed_unix_s'],
                                  current_leg=status.get('current_leg'), completed=completed,
                                  main_frames=api['learner_frame_count'],
                                  evaluator_phase=item.get('evaluator', {}).get('phase')), allow_nan=False), flush=True)
            if any(index > args.observed_through for index in completed) or status['state'] != 'running':
                return 0
        except BaseException as error:
            item['status'] = 'OBSERVATION_ALERT_OR_REFUSAL'
            item['error'] = dict(type=type(error).__name__, message=str(error))
            save(stamp + '-observation-alert.json', item)
            print(json.dumps(dict(status=item['status'], error=item['error'])), flush=True)
            return 3
        time.sleep(30)
    print('Read-only observation deadline expired; original campaign untouched.', flush=True)
    return 4


if __name__ == '__main__':
    raise SystemExit(main())
