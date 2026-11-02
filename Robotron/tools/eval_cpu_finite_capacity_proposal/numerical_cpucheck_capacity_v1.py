"""Numerical body of the precommitted private CPU-return check comparison."""
import hashlib
import os
from pathlib import Path
import sys
import threading
import time
from types import MethodType


def run(job, reader, before_health, h):
    require, publish = h['require'], h['publish']
    health_check, summary, parity = h['original_main_health'], h['summary_ms'], h['q_parity']
    out, profile = Path(job['output']), h['PROFILE']
    out.mkdir(mode=0o700)
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'TORCHINDUCTOR_COMPILE_THREADS'):
        os.environ[name] = '2'
    for key, leaf in dict(TORCHINDUCTOR_CACHE_DIR='inductor', TRITON_CACHE_DIR='triton',
                          CUDA_CACHE_PATH='cuda-cache', TORCH_HOME='torch-home',
                          TORCH_EXTENSIONS_DIR='extensions', ROBOTRON_DQN_MODEL_DIR='isolated-models',
                          ROBOTRON_DQN_CONTROL_PATH='isolated-control.json', ROBOTRON_RUN_DIR='isolated-report').items():
        os.environ[key] = str(out/leaf)
    os.environ['ROBOTRON_TRAIN_GPU'] = os.environ['ROBOTRON_INFERENCE_GPU'] = '0'
    sys.path.insert(0, str(profile/'Scripts'))
    import numpy as np
    import torch
    from dqn.inference_actor import InferenceActor
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    normalize = lambda value: str(value).lower().removeprefix('gpu-').replace('-', '')
    require(torch.cuda.device_count() == 1 and normalize(torch.cuda.get_device_properties(0).uuid) == normalize(h['GPU0']),
            'Physical CUDA device differs from private GPU0')
    proposed = reader.checked_module('dqn.cpucheck_benchmark_candidate', job['candidate_source'])
    started = time.monotonic()
    actor = InferenceActor(job['checkpoint']['path'], device='cuda:0', inference_backend='inductor')
    require(actor.checkpoint_sha256 == h['POLICY_SHA'], 'Policy bytes differ')
    baseline = actor._infer_q_joint
    methods = dict(gpu_check=baseline, cpu_check=MethodType(proposed.InferenceActor._infer_q_joint, actor))
    pointers = {key: value.data_ptr() for key, value in actor.infer_net.state_dict().items()}
    guard = dict(actor._compile_guard)
    data = np.random.default_rng(job['seed']).random((256, actor.state_size), dtype=np.float32)
    variants = dict(empty=np.zeros_like(data), populated=data)
    warm_s = time.monotonic()-started
    try:
        failures = []
        def serving_probe():
            try:
                for method in methods.values():
                    actor._infer_q_joint = method
                    for size in range(1, 17):
                        for array in variants.values():
                            actor.act_batch(array[:size], [0.0]*size,
                                            [None if i % 2 == 0 else i % 9 for i in range(size)])
            except BaseException as error:
                failures.append(repr(error))
        thread = threading.Thread(target=serving_probe, name='CPUCheckServingProbe', daemon=True)
        thread.start(); thread.join(timeout=60)
        require(not thread.is_alive() and not failures, 'Serving-thread guard failed: '+repr(failures))
        timings, checks, records, actions_equal = {}, {}, [], True
        health = [before_health, health_check()]
        for variant, array in variants.items():
            samples = {key: [] for key in methods}
            for repeat in range(job['rounds']):
                first = (repeat % 8)*32
                states = array[first:first+32]
                locks = [None if i % 2 == 0 else i % 9 for i in range(32)]
                reference = None
                for condition in job['schedule']:
                    actor._infer_q_joint = methods[condition]
                    t0 = time.perf_counter()
                    actions = []
                    for a, b in h['slices_for'](condition):
                        actions.extend(actor.act_batch(states[a:b], [0.0]*(b-a), locks[a:b]))
                    samples[condition].append((time.perf_counter()-t0)*1000)
                    records.append(dict(variant=variant, repeat=repeat, position=len(records) % 4,
                                        condition=condition, first_row=first, request_rows=32,
                                        wall_ms=samples[condition][-1]))
                    reference = actions if reference is None else reference
                    actions_equal &= actions == reference
                health.append(health_check())
            timings[variant] = {key: summary(value) for key, value in samples.items()}
            values, raw_values, raw_pins = {}, {}, {}
            for condition, method in methods.items():
                actor._infer_q_joint = method
                tensors = [actor._infer_q_joint(torch.from_numpy(array[first:first+16]), True)
                           for first in range(0, 256, 16)]
                values[condition] = torch.cat(tensors).contiguous()
                raw_values[condition] = values[condition].numpy().astype('<f4', copy=False).tobytes()
                raw_pins[condition] = publish(reader, out/(variant+'-'+condition+'-Q.f32'), raw_values[condition])
            checks[variant] = parity(values['gpu_check'].tolist(), values['cpu_check'].tolist())
            checks[variant].update(bitwise_q_equal=raw_values['gpu_check'] == raw_values['cpu_check'],
                                   raw_q=raw_pins, raw_q_dtype='little-endian float32', raw_q_shape=[256, 81])
        unchanged = all(torch.equal(value.detach().cpu(), actor._original_policy[key])
                        for key, value in actor.infer_net.state_dict().items())
        require(unchanged and all(value.data_ptr() == pointers[key] for key, value in actor.infer_net.state_dict().items()),
                'Policy values or tensor storage changed')
        actor._verify_compile_guard()
        require(actor._compiled_graph_state() == guard, 'Compiled graph state changed')
        for key in ('checkpoint', 'profile_package', 'candidate_source', 'numerical_source', 'worker_source'):
            require(reader.pin(job[key]['path']) == job[key], 'Selected input changed: '+key)
        package = reader.read_pin(job['profile_package'])
        for relative, sha in package['files'].items():
            require(hashlib.sha256((profile/relative).read_bytes()).hexdigest() == sha, 'Frozen source changed')
        numeric_gate = bool(actions_equal and all(value['bitwise_q_equal'] and value['joint_actions_equal'] and
                                                  value['all_locked_fire_actions_equal'] for value in checks.values()))
        result = dict(schema='robotron-isolated-cpucheck-capacity-result-v1', job=job,
                      checkpoint_sha256=actor.checkpoint_sha256, checkpoint_metadata=actor.checkpoint_metadata,
                      torch=torch.__version__, gpu_name=torch.cuda.get_device_name(0), numeric_policy=actor.numeric_policy,
                      same_compiled_model_and16_request_batches=True, private_method_swap=True,
                      compiled_graph_state=guard, warm_s=warm_s, timings_per32_requests=timings,
                      workload_timing_records=records, sample_parity=checks, timed_actions_equal=bool(actions_equal),
                      sample_numeric_gate=numeric_gate, exact_policy_values_and_storage_preserved=True,
                      main_health=health, input_sha256=hashlib.sha256(data.tobytes()).hexdigest(),
                      input_kind='fixed synthetic empty/populated states; no live replay/RNG',
                      production_changed=False, mame_started=False, quality_qualified=False,
                      full_game_throughput_gain_verified=False, learning_speed_gain_verified=False,
                      elapsed_s=time.monotonic()-started,
                      limitation='Isolated serving microbenchmark only. Sample exactness does not replace future matched full-game controls.')
        receipt = publish(reader, out/'result.json', result)
        print(__import__('json').dumps(dict(result=receipt, sample_numeric_gate=numeric_gate,
                                           timings_per32_requests=timings)), flush=True)
        return result
    finally:
        actor._infer_q_joint = baseline
        actor.close()
