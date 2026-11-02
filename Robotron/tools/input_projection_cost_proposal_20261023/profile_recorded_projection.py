"""CPU-only cost attribution on one immutable recorded startup prefix."""
import argparse
import cProfile
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import pstats
import statistics
import struct
import sys
import time
import types


def checked(entry):
    path = Path(entry['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
    assert path.stat().st_size == entry['bytes']
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job'); parser.add_argument('--job-sha256'); parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY'); return 0
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    job_path = Path(args.job)
    assert hashlib.sha256(job_path.read_bytes()).hexdigest() == args.job_sha256
    job = json.loads(job_path.read_bytes())
    assert job['schema'] == 'robotron-recorded-input-projection-cost-job-v1'
    assert job['original_attempt'] == 1 and job['no_retry'] is True
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    output = Path(job['output']); output.mkdir(mode=0o700)
    private_models = output / 'empty-model-directory'; private_models.mkdir(mode=0o700)
    os.environ['ROBOTRON_DQN_MODEL_DIR'] = str(private_models)
    os.environ['ROBOTRON_DQN_CONTROL_PATH'] = str(private_models / 'absent-control.json')
    import numpy as np
    package = types.ModuleType('_recorded_projection_package')
    package.__path__ = [str(checked(job['config']).parent)]
    sys.modules[package.__name__] = package
    for name in ('learning_control', 'config'):
        spec = importlib.util.spec_from_file_location(package.__name__ + '.' + name, checked(job[name]))
        module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    config = sys.modules[package.__name__ + '.config']
    packets = checked(job['packets']).read_bytes()
    size = 7597; count = 1200; offset = struct.calcsize('>HddBIBBBIBBB')
    assert len(packets) == count * size and config.WIRE_PARAMS_COUNT == 1890
    assert config.SINGLE_FRAME_STATE_SIZE == 2782 and config.MODEL_STATE_SIZE == 11128
    payloads = [packets[i*size:(i+1)*size] for i in range(count)]
    assert all(struct.unpack_from('>H', row)[0] == 1890 and struct.unpack_from('>I', row, size-4)[0] == 0 for row in payloads)
    def decode_all():
        return [np.frombuffer(row[offset:offset+1890*4], dtype='>f4', count=1890).astype(np.float32) for row in payloads]
    wires = decode_all()
    def project_all():
        return [config.slice_model_state(wire) for wire in wires]
    expected = project_all()
    assert all(row.shape == (2782,) and row.dtype == np.float32 and np.isfinite(row).all() for row in expected)
    expected_hash = hashlib.sha256(b''.join(row.tobytes() for row in expected)).hexdigest()
    timings = {}
    for label, operation in [('wire_float_decode_only', decode_all), ('complete_model_frame_projection', project_all)]:
        operation()
        times = []
        for _ in range(8):
            start_wall, start_cpu = time.perf_counter(), time.process_time()
            result = operation()
            elapsed_cpu, elapsed_wall = time.process_time()-start_cpu, time.perf_counter()-start_wall
            times.append(dict(wall_s=elapsed_wall, CPU_s=elapsed_cpu))
        timings[label] = dict(repetitions=8, frames_per_repetition=count, samples=times,
            median_wall_us_per_frame=statistics.median(x['wall_s'] for x in times)*1e6/count,
            median_CPU_us_per_frame=statistics.median(x['CPU_s'] for x in times)*1e6/count)
    assert hashlib.sha256(b''.join(row.tobytes() for row in project_all())).hexdigest() == expected_hash
    profile = cProfile.Profile(); profile.enable(); project_all(); profile.disable()
    text = io.StringIO(); pstats.Stats(profile, stream=text).strip_dirs().sort_stats('cumulative').print_stats(25)
    report = dict(status='RECORDED_CPU_COST_ATTRIBUTION_COMPLETE', job_sha256=args.job_sha256,
        source_sha256=args.source_sha256, Python=sys.version, gil_enabled=sys._is_gil_enabled(), numpy=np.__version__,
        CUDA_VISIBLE_DEVICES=os.environ['CUDA_VISIBLE_DEVICES'], torch_imported='torch' in sys.modules,
        config=job['config'], packet_input=job['packets'], input_frames=count, all_features_preserved=True,
        frame_input_features=2782, stack_input_features=11128, exact_output_sha256=expected_hash,
        timings=timings, profile=text.getvalue(), production_changed=False, controlled_speed_gain_verified=False,
        policy_quality_verified=False,
        limits=['One actor startup prefix and isolated serial replay; early-wave data only.',
                'No actual handler end-to-end, Lua computation, socket wait, concurrent live service or GPU timings.',
                'Cost attribution only; no replacement implementation or speed gain measured.'])
    with (output / 'cost-attribution.json').open('x') as stream:
        json.dump(report, stream, separators=(',', ':'), allow_nan=False)
        stream.write('\n'); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'], timings={k:v['median_wall_us_per_frame'] for k,v in timings.items()},
                          report=str(output / 'cost-attribution.json'))), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
