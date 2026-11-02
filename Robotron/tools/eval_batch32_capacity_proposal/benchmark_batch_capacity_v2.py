"""Isolated GPU0 batch-capacity microbenchmark; never a quality evaluation.

The existing FP32 policy and act_batch decoder are retained. Only this private
instance receives an experimental compiled Q dispatcher supporting batches1..32.
The deployed actor's16-request guard and every production source stay untouched.
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
    require(job['schema'] == 'robotron-isolated-batch-capacity-job-v1', 'Unknown job')
    require(job['gpu_uuid'] == GPU0 and job['checkpoint']['sha256'] == POLICY_SHA,
            'Only protected1059 on private GPU0 is selected')
    require(job['profile_package']['sha256'] == PACKAGE_SHA,
            'Exact frozen evaluator source package required')
    out = Path(job['output'])
    base = ROOT / 'logs/managed-learning-20261015/run-26'
    require(out.is_absolute() and out.parent.parent == base and
            out.parent.name == 'eval-batch32-capacity-original01-preparation-20261019' and
            out.name == 'work' and not out.exists(), 'New exact private output required')
    require(job['rounds'] == 12 and type(job['rounds']) is int and
            job['sample_rows'] == 256 and type(job['sample_rows']) is int and
            job['seed'] == 20261020 and job['schedule'] == ['16', '32', '32', '16'],
            'Fixed matched-workload ABBA design required')
    require(job['rows_per_workload'] == 32 and job['cpu_threads'] == 2 and
            job['compile_options'] == {'triton.cudagraphs': False}, 'Numeric/runtime design differs')
    require(job['quality_qualification'] is False and job['mame'] is False and
            job['training'] is False, 'Inference-only scope required')


def slices_for(condition):
    require(condition in ('16', '32'), 'Unknown capacity condition')
    return [(0, 16), (16, 32)] if condition == '16' else [(0, 32)]


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
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
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
    out = Path(job['output'])
    out.mkdir(mode=0o700)
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'TORCHINDUCTOR_COMPILE_THREADS'):
        os.environ[name] = '2'
    for key, relative in dict(TORCHINDUCTOR_CACHE_DIR='inductor', TRITON_CACHE_DIR='triton',
                              CUDA_CACHE_PATH='cuda-cache', TORCH_HOME='torch-home',
                              TORCH_EXTENSIONS_DIR='extensions', ROBOTRON_DQN_MODEL_DIR='isolated-models',
                              ROBOTRON_DQN_CONTROL_PATH='isolated-control.json',
                              ROBOTRON_RUN_DIR='isolated-report').items():
        os.environ[key] = str(out/relative)
    os.environ['ROBOTRON_TRAIN_GPU'] = os.environ['ROBOTRON_INFERENCE_GPU'] = '0'
    sys.path.insert(0, str(PROFILE/'Scripts'))
    import numpy as np
    import torch
    import torch._dynamo as dynamo
    from dqn.inference_actor import InferenceActor
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    normalize = lambda value: str(value).lower().removeprefix('gpu-').replace('-', '')
    require(torch.cuda.device_count() == 1 and normalize(torch.cuda.get_device_properties(0).uuid) == normalize(GPU0),
            'Physical CUDA device differs from private GPU0')
    actor = InferenceActor(job['checkpoint']['path'], device='cuda:0', inference_backend='eager')
    require(actor.checkpoint_sha256 == POLICY_SHA, 'Policy bytes differ')
    pointers = {k: v.data_ptr() for k, v in actor.infer_net.state_dict().items()}
    data = np.random.default_rng(job['seed']).random((256, actor.state_size), dtype=np.float32)
    variants = dict(empty=np.zeros_like(data), populated=data)
    dynamo.config.suppress_errors = False
    dynamo.config.error_on_recompile = False
    for name, value in (('recompile_limit', 64), ('cache_size_limit', 64),
                        ('accumulated_recompile_limit', 1024), ('accumulated_cache_size_limit', 1024)):
        if hasattr(dynamo.config, name):
            setattr(dynamo.config, name, value)
    compiled = torch.compile(actor.infer_net.q_values_joint, backend='inductor', dynamic=True,
                             options=dict(job['compile_options']))
    guard = None

    def dispatch(states, return_cpu=False):
        with actor._sync_lock, torch.inference_mode(), torch.autocast('cuda', enabled=False):
            require(states.ndim == 2 and states.shape[1] == actor.state_size and
                    1 <= len(states) <= 32 and bool(torch.isfinite(states).all()), 'Invalid private benchmark input')
            if guard is not None:
                require(dynamo.config.error_on_recompile and not dynamo.config.suppress_errors and
                        actor._compiled_graph_state() == guard, 'Compiled guard changed')
            q = compiled(states.to(actor.device, dtype=torch.float32))
            require(q.shape == (len(states), 81) and bool(torch.isfinite(q).all()), 'Invalid Q output')
            if guard is not None:
                require(actor._compiled_graph_state() == guard, 'Serving recompiled or fell back')
            if return_cpu:
                return q.detach().cpu()
            torch.cuda.synchronize(actor.device)
            return q

    original = actor._infer_q_joint
    actor._infer_q_joint = dispatch
    started = time.monotonic()
    try:
        for size in (1, 2, 4, 8, 16, 32, *(v for v in range(1, 33) if v not in (1, 2, 4, 8, 16, 32))):
            for array in variants.values():
                actor.act_batch(array[:size], [0.0]*size)
        warm_s = time.monotonic()-started
        guard = actor._compiled_graph_state()
        require(guard['unique_graphs'] > 0 and guard['graph_breaks'] == guard['unimplemented'] == 0,
                'Incomplete compiled graphs')
        dynamo.config.error_on_recompile = True
        failures = []

        def serving_probe():
            try:
                for size in range(1, 33):
                    for array in variants.values():
                        actor.act_batch(array[:size], [0.0]*size,
                                        [None if i % 2 == 0 else i % 9 for i in range(size)])
            except BaseException as error:
                failures.append(repr(error))

        thread = threading.Thread(target=serving_probe, name='BatchCapacityServingProbe', daemon=True)
        thread.start()
        thread.join(timeout=60)
        require(not thread.is_alive() and not failures, 'Serving-thread guard failed: '+repr(failures))
        timings, checks, actions_equal = {}, {}, True
        workload_timing_records = []
        health = [before_health, original_main_health()]
        for variant, array in variants.items():
            values = {'16': [], '32': []}
            for repeat in range(job['rounds']):
                first = (repeat % 8)*32
                states = array[first:first+32]
                locks = [None if i % 2 == 0 else i % 9 for i in range(32)]
                reference = None
                for condition in job['schedule']:
                    t0 = time.perf_counter()
                    actions = []
                    for a, b in slices_for(condition):
                        actions.extend(actor.act_batch(states[a:b], [0.0]*(b-a), locks[a:b]))
                    values[condition].append((time.perf_counter()-t0)*1000)
                    workload_timing_records.append(dict(variant=variant, repeat=repeat,
                        position=len(workload_timing_records) % 4, condition=condition,
                        first_row=first, request_rows=32, wall_ms=values[condition][-1]))
                    reference = actions if reference is None else reference
                    actions_equal &= actions == reference
                health.append(original_main_health())
            timings[variant] = {key: summary_ms(v) for key, v in values.items()}
            small, large = [], []
            for first in range(0, len(array), 32):
                tensor = torch.from_numpy(array[first:first+32])
                small.extend(dispatch(tensor[:16], True).tolist())
                small.extend(dispatch(tensor[16:], True).tolist())
                large.extend(dispatch(tensor, True).tolist())
            checks[variant] = q_parity(small, large)
        unchanged = all(torch.equal(v.detach().cpu(), actor._original_policy[k])
                        for k, v in actor.infer_net.state_dict().items())
        require(unchanged and all(v.data_ptr() == pointers[k] for k, v in actor.infer_net.state_dict().items()),
                'Policy tensors or storage changed')
        require(reader.pin(job['checkpoint']['path']) == job['checkpoint'], 'Checkpoint changed')
        require(reader.pin(job['profile_package']['path']) == job['profile_package'], 'Source package changed')
        package = reader.read_pin(job['profile_package'])
        for relative, sha in package['files'].items():
            require(hashlib.sha256((PROFILE/relative).read_bytes()).hexdigest() == sha,
                    'Frozen source changed during the benchmark')
        require(reader.pin(Path(__file__).resolve()) == job['worker_source'], 'Worker source changed')
        result = dict(schema='robotron-isolated-batch-capacity-result-v1', job=job,
                      checkpoint_sha256=actor.checkpoint_sha256, checkpoint_metadata=actor.checkpoint_metadata,
                      torch=torch.__version__, gpu_name=torch.cuda.get_device_name(0), numeric_policy=actor.numeric_policy,
                      experimental_dispatch=True, compile_backend='inductor', compile_dynamic=True,
                      compiled_graph_state=guard, warm_s=warm_s, timings_per32_requests=timings,
                      workload_timing_records=workload_timing_records,
                      sample_parity=checks, timed_actions_equal=bool(actions_equal), exact_policy_values_and_storage_preserved=True,
                      main_health=health, input_kind='fixed synthetic empty/populated states; no live replay or RNG',
                      input_sha256=hashlib.sha256(data.tobytes()).hexdigest(),
                      sample_numeric_gate=bool(actions_equal and all(v['q_allclose'] and v['joint_actions_equal'] and
                                                                     v['all_locked_fire_actions_equal'] for v in checks.values())),
                      mame_started=False, production_changed=False, quality_qualified=False,
                      full_game_throughput_gain_verified=False, learning_speed_gain_verified=False,
                      elapsed_s=time.monotonic()-started,
                      limitation='Microbenchmark only. Synthetic agreement cannot establish full-policy equivalence or full-game throughput. A deployment needs its own guarded source/test path and fresh matched reference/candidate cohorts.')
        result['receipt'] = publish(reader, out/'result.json', result)
        print(json.dumps({'result': result['receipt'], 'sample_numeric_gate': result['sample_numeric_gate'],
                          'timings_per32_requests': timings}), flush=True)
        return result
    finally:
        actor._infer_q_joint = original
        actor.close()


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
