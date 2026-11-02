"""CPU reproduction of original observer sample/rejection serialization failure."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE = GAME / 'tools/eval_capacity_proposal'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY')
        return
    source = BASE / 'pilot_runtime_guard_inflight_v1.py'
    expected = '95d477eedab282b016b100f930cb382511fd90e3f5676b774a410e497dafeaff'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    fixture = GAME / ('logs/managed-learning-20261015/run-26/'
        'capacity-inflight-v1-CPU-original02-preparation-20261019/immutable')
    test_source = fixture / 'test_pilot_runtime_guard_inflight_v1.py'
    assert hashlib.sha256(test_source.read_bytes()).hexdigest() == '25f33580c648312435499de82750205ebc96cac78ecfa917dbb9de0bce7b4bc5'
    sys.path.insert(0, str(BASE))
    sys.path.insert(0, str(fixture))
    from test_pilot_runtime_guard_inflight_v1 import GuardFixture, guard
    assert hashlib.sha256(Path(guard.__file__).read_bytes()).hexdigest() == expected
    cases = []
    for name, value, rejected in [('finite', 1.0, False), ('positive_infinity', float('inf'), True),
                                  ('negative_infinity', float('-inf'), True), ('nan', float('nan'), True)]:
        case = GuardFixture()
        case.setUp()
        try:
            before = len(case.g.samples)
            case.api['grad_norm'] = value
            case.advance()
            error = None
            try:
                case.g.sample()
            except ValueError as exc:
                error = str(exc)
            assert (error is not None) is rejected
            assert len(case.g.samples) == before + (not rejected)
            if rejected:
                assert 'Out of range float values are not JSON compliant' in error
                assert case.g.failed is not None and not case.g.rejected_observations
                assert not list((case.g.binding_dir / 'main-rejections').glob('*.json'))
                assert not (case.g.binding_dir / 'main-samples' / f'{before:04d}.json').exists()
            cases.append(dict(name=name, status='EXPECTED_ORIGINAL_BEHAVIOR_REPRODUCED',
                accepted_sample_written=not rejected, rejection_record_count=len(case.g.rejected_observations),
                bad_API_payload_retained=False if rejected else None, error=error))
        finally:
            case.doCleanups()
    assert 'torch' not in sys.modules
    report = dict(schema='robotron-original-nonfinite-observer-storage-CPU-reproduction-v1',
        status='PASS', cases=cases, original_guard_sha256=expected,
        original_failed_runtime_snapshot_reconstructed=False,
        original_runtime_field_identified=False, synthetic_nonfinite_field='grad_norm',
        window_health_is_a_fixture=True, scope='Actual MainGuard.sample/_sample/save exception path and rejection writer, using the existing CPU fixture. This is not a model-health test or reconstruction of the lost runtime payload.',
        actual_GPU_MAME_optimizer_or_live_control=False, original_runtime_retried=False,
        production_changed=False)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    print(json.dumps(dict(status='PASS', cases=len(cases), original_runtime_field_identified=False)))


if __name__ == '__main__':
    main()
