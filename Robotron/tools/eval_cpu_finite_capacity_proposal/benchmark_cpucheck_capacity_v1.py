"""One isolated GPU0 finite-check serving comparison with unchanged16-row batches.
The original compiled actor and isolated candidate method share one model.
No MAME, training, production source, policy or quality evaluation is changed.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time

GPU0 = "GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0"
ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
PROFILE = ROOT / 'tools/quality_capacity_proposal/profile03/Robotron'
PROTECTOR = ROOT / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
PROTECTOR_SHA = 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
POLICY_SHA = '4446df3291d7196e35f4d865ba63f0edf18d4a132ef5223346ae1c0ff49cae2e'
PACKAGE_SHA = '40a9fc7148764623c723dc9b8f3ae2368ee5a4c29a39e353e3975371c79d04a1'


def require(value, message):
    if not value:
        raise ValueError(message)


def reader_module():
    require(hashlib.sha256(PROTECTOR.read_bytes()).hexdigest() == PROTECTOR_SHA,
            'Immutable evidence reader changed')
    spec = importlib.util.spec_from_file_location('_batch_capacity_reader', PROTECTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_job(job):
    require(job['schema'] == 'robotron-isolated-cpucheck-capacity-job-v1', 'Unknown job')
    require(job['gpu_uuid'] == GPU0 and job['checkpoint']['sha256'] == POLICY_SHA,
            'Only protected1059 on private GPU0 is selected')
    require(job['profile_package']['sha256'] == PACKAGE_SHA,
            'Exact frozen evaluator source package required')
    selected = ROOT/'tools/eval_cpu_finite_capacity_proposal'
    require(Path(job['candidate_source']['path']) == selected/'inference_actor_cpucheck_v1.py' and
            Path(job['numerical_source']['path']) == selected/'numerical_cpucheck_capacity_v1.py',
            'Exact isolated proposal modules required')
    out = Path(job['output'])
    base = ROOT / 'logs/managed-learning-20261015/run-26'
    require(out.is_absolute() and out.parent.parent == base and
            out.parent.name == 'eval-cpucheck-capacity-original01-preparation-20261019' and
            out.name == 'work' and not out.exists(), 'New exact private output required')
    require(job['rounds'] == 12 and type(job['rounds']) is int and
            job['sample_rows'] == 256 and type(job['sample_rows']) is int and
            job['seed'] == 20261020 and job['schedule'] == ['gpu_check', 'cpu_check', 'cpu_check', 'gpu_check'],
            'Fixed matched-workload ABBA design required')
    require(job['rows_per_workload'] == 32 and job['cpu_threads'] == 2 and
            job['compile_options'] == {'triton.cudagraphs': False}, 'Numeric/runtime design differs')
    require(job['quality_qualification'] is False and job['mame'] is False and
            job['training'] is False, 'Inference-only scope required')


def slices_for(condition):
    require(condition in ('gpu_check', 'cpu_check'), 'Unknown capacity condition')
    return [(0, 16), (16, 32)]


def summary_ms(values):
    require(values and all(math.isfinite(v) and v > 0 for v in values), 'Invalid wall timings')
    ordered = sorted(values)
    return dict(calls=len(values), median_ms=statistics.median(values),
                p95_ms=ordered[math.ceil(.95*len(values))-1],
                minimum_ms=min(values), maximum_ms=max(values))


def q_parity(left, right):
    require(len(left) == len(right) > 0 and
            all(len(a) == len(b) == 81 for a, b in zip(left, right)), 'Aligned81-action rows required')
    differences, close, joint, locked = [], True, 0, 0
    for a, b in zip(left, right):
        require(all(math.isfinite(v) for row in (a, b) for v in row), 'Nonfinite Q row')
        differences.extend(abs(x-y) for x, y in zip(a, b))
        close &= all(abs(x-y) <= .001 + .001*abs(x) for x, y in zip(a, b))
        joint += max(range(81), key=a.__getitem__) == max(range(81), key=b.__getitem__)
        for fire in range(9):
            locked += max(range(9), key=lambda move: a[move*9+fire]) == max(
                range(9), key=lambda move: b[move*9+fire])
    return dict(rows=len(left), q_allclose=bool(close), atol=.001, rtol=.001,
                maximum_abs_error=max(differences), joint_actions_equal=joint == len(left),
                all_locked_fire_actions_equal=locked == 9*len(left))


def original_main_health():
    import urllib.request
    for pid, start in ((3170722, 52892579), (2258189, 26614335)):
        fields = Path('/proc', str(pid), 'stat').read_text().rsplit(') ', 1)[1].split()
        require(int(fields[19]) == start and fields[0] in ('R', 'S', 'D'), 'Main original owner changed')
    api = json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5))
    now = time.time()
    age = now - (ROOT/'models_dqn/robotron_dqn_latest.pt').stat().st_mtime
    require(api['client_count'] == 192 and api['training_enabled'] is True and
            0 <= now-api['ts'] <= 5 and 0 <= age <= 360, 'Main health/freshness failed')
    require(api['quality_campaign']['available'] is False, 'A quality campaign is registered')
    return dict(unix_s=now, clients=192, learner_frames=api['learner_frame_count'],
                training_steps=api['training_steps'], autosave_age_s=age)


def publish(reader, path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return reader.pin(path)


def execute(job, reader):
    validate_job(job)
    require('torch' not in sys.modules and 'numpy' not in sys.modules, 'Fresh numerical process required')
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == GPU0, 'GPU0 must be isolated before imports')
    package = reader.read_pin(job['profile_package'])
    require(Path(package['root']) == PROFILE, 'Frozen source root differs')
    for relative, sha in package['files'].items():
        require(hashlib.sha256((PROFILE/relative).read_bytes()).hexdigest() == sha, 'Frozen source changed')
    reader.read_pin(job['checkpoint'], as_json=False)
    before_health = original_main_health()
    for name in ('tcp', 'tcp6'):
        for line in Path('/proc/net', name).read_text().splitlines()[1:]:
            fields = line.split()
            require(not (fields[3] == '0A' and int(fields[1].rsplit(':', 1)[1], 16) == 9999),
                    'Private evaluation port is occupied')
    lease = Path('/dev/shm/robotron-snapshot-smoke-gpu0.lock')
    info = lease.lstat()
    require(dict(device=info.st_dev, inode=info.st_ino) == job['lease_identity'] and
            info.st_uid == os.getuid() and info.st_nlink == 1, 'Canonical lease identity differs')
    with lease.open('rb') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        query = subprocess.run(['nvidia-smi', '--id='+GPU0, '--query-compute-apps=pid',
                                '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10)
        require(query.returncode == 0 and not query.stdout.strip(), 'Private GPU already has users')
        return numerical(job, reader, before_health)


def numerical(job, reader, before_health):
    numeric = reader.checked_module('_cpucheck_selected_numerical', job['numerical_source'])
    helpers = dict(publish=publish, q_parity=q_parity, summary_ms=summary_ms,
                   original_main_health=original_main_health, slices_for=slices_for,
                   require=require, ROOT=ROOT, PROFILE=PROFILE, GPU0=GPU0, POLICY_SHA=POLICY_SHA)
    return numeric.run(job, reader, before_health, helpers)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: no model/GPU/MAME imports, files, processes or controls changed')
        return 0
    require(args.job and args.job_sha256, 'Exact selected job required')
    reader = reader_module()
    entry = reader.pin(args.job)
    require(entry['sha256'] == args.job_sha256, 'Job SHA differs')
    job = reader.read_pin(entry)
    require(reader.pin(Path(__file__).resolve()) == job['worker_source'], 'Worker source changed')
    execute(job, reader)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
