"""Exercise actual prepared engineering initialization; stop before worker work."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256')
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY'); return 0
    assert hashlib.sha256(args.job.read_bytes()).hexdigest() == args.job_sha256
    job = json.loads(args.job.read_text())
    assert job['schema'] == 'robotron-active600-actual-initializer-CPU-job-v1'
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == job['runner_sha256']
    assert 'torch' not in sys.modules

    def load(pin, name):
        path = Path(pin['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    h = load(job['helpers'], '_active600_initializer_h')
    reader = load(job['reader'], '_active600_initializer_reader')
    fixture = reader.read_pin(job['fixture'])
    assert fixture['initializer_fixture_only'] is True
    output = Path(fixture['output'])
    assert output.parent.name == 'explicit-never-launched-initializer-fixture' and not output.exists()
    proof = reader.read_pin(h.pin(fixture['prelaunch_family_guard_closeout']))
    assert proof['native_job'] == job['fixture'] and proof['fixture_only'] is True
    assert proof['tests'] == 12 and proof['negative_checks'] == 31
    assert proof['actual_exit'] == 0 and proof['actual6_original_descriptors_argv_resources_pins_release_and_birth_absence_verified'] is True
    runtime = load(fixture['runtime'], '_active600_actual_native_initializer')
    protocol = reader.read_pin(fixture['main_health_protocol'])
    family = reader.read_pin(fixture['source_family_manifest'])
    runtime.validate_main_health_contract(fixture, protocol, family)
    assert protocol['schema'] == 'robotron-native-quota64-API-epoch-reference600-main-health-protocol-v1'
    called = []

    class NoPrivateWork(Exception):
        pass

    class Client:
        @staticmethod
        def DedicatedMainHealth(*args, **kwargs):
            called.append(True)
            raise NoPrivateWork('EXPLICIT_ACTIVE600_FIXTURE_STOP_BEFORE_WORKER_POLICY_TORCH_MAME')

    original_load = runtime.load
    def controlled_load(name, path):
        if name == '_compiled32_dedicated_main_health_client':
            return Client
        return original_load(name, path)
    try:
        runtime.load = controlled_load
        result_code = runtime.run(fixture, job['fixture'], h)
    finally:
        runtime.load = original_load
    assert result_code == 1 and called == [True]
    resultpin = h.pin(output / 'result.json')
    result = reader.read_pin(resultpin)
    assert result['errors'] == ["NoPrivateWork('EXPLICIT_ACTIVE600_FIXTURE_STOP_BEFORE_WORKER_POLICY_TORCH_MAME')"]
    assert result['original_slots'] == {} and result['main_samples'] == []
    assert result['main_observer_lifecycle'] is result['policy_before'] is result['acquired_checkpoint'] is None
    assert result['original_lease_released'] is result['immutable_inputs_unchanged'] is True
    assert result['active_start'] is result['active_end'] is result['active_frame_rate'] is result['selector_call_timing'] is None
    assert result['quality_qualified'] is False and 'torch' not in sys.modules
    for pin in fixture['inputs']:
        h.checked(pin)
    reportpin = h.put(Path(job['report']), dict(
        schema='robotron-active600-actual-initializer-CPU-report-v1',
        status='PASS_ACTUAL_ENGINEERING_PREPARER_PROTOCOL_CONSUMED_BEFORE_ANY_WORKER_POLICY_TORCH_MAME',
        job=h.pin(args.job), fixture=job['fixture'], native_result=resultpin,
        actual_fixture_native_return=1, expected_pre_worker_sentinel=True,
        actual_preparer_engineering_protocol=fixture['main_health_protocol'],
        original_source_guard_closeout=h.pin(fixture['prelaunch_family_guard_closeout']),
        original_lease_released=True, immutable_inputs_unchanged=True,
        original_engineering_case_launched=False, evaluator_worker_Torch_or_MAME_started=False,
        quality_qualified=False, production_changed=False))
    print(json.dumps(dict(passed=True, report=reportpin)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
