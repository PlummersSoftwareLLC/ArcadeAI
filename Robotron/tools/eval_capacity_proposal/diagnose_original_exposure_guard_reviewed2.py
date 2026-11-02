"""CPU-only reproduction of the original pilot guard's in-flight rejection.

This exercises original sources without changing them or rescuing the failed
pilot. The actual rejected API sample was not retained, so this establishes a
guard defect, not the precise cause of the original runtime stop.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace


ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
PREP = ROOT / 'logs/managed-learning-20261015/run-26/confirmed-scoring-quality-original01-preparation-20261018/future-capacity32-runtime-pilot-preparation-20261019'


def load(name, path, expected):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run():
    binding = json.loads((PREP / 'runtime-bindings/main-binding.json').read_bytes())
    exposure_path = ROOT / 'Scripts/dqn/learning_exposure.py'
    exposure_sha = binding['held_hashes'][str(exposure_path)]
    exposure = load('_diagnostic_actual_exposure', exposure_path, exposure_sha)
    guard_path = ROOT / 'tools/eval_capacity_proposal/pilot_runtime_guard.py'
    guard_sha = '6f82f562a526b8a4a04f8f02317847c3849b58381a90daf9547428cd3f4b7131'
    original = load('_diagnostic_original_guard', guard_path, guard_sha)
    reader = original.reader_module()
    api = json.loads((PREP / 'runtime-bindings/baseline-API.raw.json').read_bytes())
    optimizer = exposure.OptimizerExposure()
    optimizer.new_epoch('synthetic_initial_restore')
    optimizer.finish(optimizer.begin(), 'unscaled')
    replay = exposure.ReplayInsertExposure()
    replay.new_epoch('synthetic_initial_adoption')
    replay.accepted('dqn', False, 0)
    clock = [1000.0]

    def snapshot():
        result = copy.deepcopy(api)
        result['host_pipeline']['learning_exposure'] = dict(
            optimizer=optimizer.snapshot(), replay=replay.snapshot())
        return result

    cases = []
    with tempfile.TemporaryDirectory(prefix='robotron-exposure-guard-') as temp:
        fixture = Path(temp)
        checkpoint = fixture / 'models_dqn/robotron_dqn_latest.pt'
        checkpoint.parent.mkdir()
        checkpoint.write_bytes(b'synthetic checkpoint freshness fixture')
        bindings = fixture / 'bindings'
        (bindings / 'main-samples').mkdir(parents=True)
        original.GAME = fixture

        def read_api():
            os.utime(checkpoint, (clock[0] - 5, clock[0] - 5))
            return snapshot()

        original.read_API = read_api
        window = SimpleNamespace(owner_and_files=lambda _: None, healthy=lambda *args: None)
        instance = original.MainGuard({}, dict(
            reader=reader, review_job={'closed_context_path': str(bindings / 'closed.json')},
            main={'owner': {'pid': os.getpid()}, 'experiment': 'synthetic-only'}, window=window, baseline=snapshot()))
        instance.held_sha = 'synthetic-owned-inputs'
        instance.clock = lambda: clock[0]
        instance.monotonic = lambda: clock[0]
        instance.sample()
        before = optimizer.snapshot()
        ticket = optimizer.begin()
        inflight = optimizer.snapshot()
        clock[0] += 10
        assert inflight['available'] is False
        assert inflight['unclassified_started_total'] == 1
        assert inflight['total']['unavailable'] == 0
        assert all(inflight[k] == before[k] for k in ('process_id', 'instance_monotonic_ns', 'epoch'))
        try:
            instance.sample()
        except ValueError as error:
            assert str(error) == 'Main exposure accounting changed'
            cases.append(dict(case='coherent_inflight_original_guard_rejects', status='REPRODUCED', snapshot=inflight))
        else:
            raise AssertionError('Original guard did not reproduce the in-flight rejection')
        optimizer.finish(ticket, 'unscaled')
        clock[0] += 10
        api['learner_frame_count'] += 100
        replay.accepted('dqn', False, 0)
        instance.sample()
        drained = optimizer.snapshot()
        assert drained['available'] is True and drained['epoch'] == before['epoch']
        assert drained['total']['applied'] == before['total']['applied'] + 1
        cases.append(dict(case='same_identity_same_epoch_finished_update_original_guard_accepts', status='PASS', snapshot=drained))
        optimizer.finish(optimizer.begin(), 'synthetic_unclassified_failure')
        clock[0] += 1
        try:
            instance.sample()
        except ValueError as error:
            assert str(error) == 'Main exposure accounting changed'
            assert optimizer.snapshot()['total']['unavailable'] == 1
            cases.append(dict(case='genuine_unclassified_outcome_rejected', status='PASS'))
        else:
            raise AssertionError('Original guard accepted a genuinely unavailable outcome')
    assert not any(name == 'torch' or name.startswith('torch.') for name in sys.modules)
    return dict(schema='robotron-original-exposure-guard-source-diagnostic-v1', status='PASS',
                cases=cases, source_sha256={str(exposure_path): exposure_sha, str(guard_path): guard_sha},
                cuda_initialized=False, production_changed=False, actual_failed_sample_retained=False,
                precise_original_stop_cause_proven=False, original_pilot_valid=False,
                pilot_retried=False, original_scientific_audits_rerun=False)


if __name__ == '__main__':
    output = Path(sys.argv[1])
    report = run()
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'], cases=len(report['cases']), report=str(output))))
