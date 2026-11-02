"""Exercise actual A32/B64 initializers under GIL-disabled Python, before lease."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).resolve().parent
P = N / 'future-evaluator-concurrency64-UNSELECTED-source-preparation-original02'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert sys.version_info[:2] == (3, 14) and sys._is_gil_enabled() is False
    helper = G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    h = load('_capacity_initializer_h', helper)
    index_path = P / 'CPU-fixture-index-v2.json'
    assert hashlib.sha256(index_path.read_bytes()).hexdigest() == '23e79011cceacbc9cc73a03c11e37e4d9d5ce646d17643906e823a2d58b70064'
    index = json.loads(index_path.read_bytes())
    results = []
    for c in index['cases']:
        runtime = load('_actual_capacity_initializer_' + c['role'], h.checked(c['sources']['runtime']))
        job = json.loads(h.checked(c['job']).read_bytes())
        assert not Path(job['output']).exists()
        assert 'torch' not in sys.modules and 'numpy' not in sys.modules
        coordinator_before = h.pin(job['lease']['path'])
        with patch.object(runtime.PrivateLease, 'acquire', side_effect=AssertionError('GPU lease forbidden')) as lease, \
             patch.object(runtime.subprocess, 'run', side_effect=AssertionError('subprocess forbidden')) as run, \
             patch.object(runtime.subprocess, 'Popen', side_effect=AssertionError('child forbidden')) as popen, \
             patch.object(runtime.threading.Thread, 'start', side_effect=AssertionError('thread forbidden')) as thread:
            exit_code = runtime.run(job, c['job'], h, cpu_initializer=True)
            lease.assert_not_called();run.assert_not_called();popen.assert_not_called();thread.assert_not_called()
        assert exit_code == 1
        result_pin = h.pin(Path(job['output']) / 'result.json')
        result = json.loads(h.checked(result_pin).read_bytes())
        assert result['errors'] == ["RuntimeError('CPU_INITIALIZER_STOP_BEFORE_GPU_LEASE_WORKER_TORCH_MAME')"], result['errors']
        assert result['original_slots'] == {} and result['main_samples'] == []
        for key in ['policy_before', 'policy_after', 'acquired_checkpoint', 'main_health_report',
                    'main_observer_lifecycle', 'initial_main_readiness', 'lease', 'socket_wait_library']:
            assert result[key] is None, key
        assert result['original_lease_released'] is False  # It was never acquired.
        assert result['immutable_inputs_unchanged'] is True and result['all_original_threads_stopped'] is True
        assert result['quality_qualified'] is result['complete'] is result['full_game_score_verified'] is False
        assert result['main_runtime_changed'] is False
        assert h.pin(job['lease']['path']) == coordinator_before
        assert 'torch' not in sys.modules and 'numpy' not in sys.modules
        assert sys._is_gil_enabled() is False
        results.append(dict(role=c['role'], actor_count=c['actor_count'], job=c['job'],
                            runtime=c['sources']['runtime'], result=result_pin, actual_initializer_exit=exit_code,
                            exact_expected_prelease_stop=True, lease_subprocess_thread_calls=0,
                            Torch_numpy_MAME_and_main_observer_started=False,
                            persistent_coordinator_unchanged=True))
    report = dict(schema='robotron-capacity64-actual-free-threaded-prelease-initializer-proof-v1',
                  source=h.pin(__file__), fixtures=h.pin(index_path), python=sys.version,
                  GIL_enabled=False, cases=results, actual_both_prelease_initializers_verified=True,
                  fixture_only=True, native_launch_ready=False, actual64_startup_verified=False,
                  quality_qualified=False, throughput_gain_verified=False,
                  limits='Initializers intentionally stop before lease, worker, Torch and MAME. Actual native setup, all64 startup, resource/load and engineering comparison remain unproven.')
    target = P / 'CPU-prelease-initializers-original01' / 'actual-prelease-initializer-report.json'
    print(json.dumps(dict(report=h.put(target, report), cases_verified=len(results))), flush=True)
    time.sleep(8)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
