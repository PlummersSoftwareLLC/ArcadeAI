"""Check a checkpoint against the preserved evaluator profile on CPU only."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


def checked(pin):
    path = Path(pin['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin['sha256']
    return path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main(job):
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert checked(job['driver']) == Path(__file__).resolve()
    package = json.loads(checked(job['package']).read_bytes())
    root = Path(package['root'])
    assert len(package['files']) == package['source_count'] == 123
    for name, digest in package['files'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    checkpoint = checked(job['checkpoint'])
    baseline = json.loads(checked(job['canonical_CPU_facts']).read_bytes())
    source = checked(job['benchmark'])
    spec = importlib.util.spec_from_file_location('_frozen_profile_CPU_benchmark', source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # Select the preserved123-file evaluator profile, never the live learner.
    module.GAME = root
    result = module.run(module.Plan(checkpoint, Path(job['output'])), cpu=True)
    assert result['cuda_initialized'] is False and result['inference_error'] is None
    assert result['checkpoint_sha256'] == baseline['checkpoint_sha256'] == job['checkpoint']['sha256']
    assert result['copied_state_sha256'] == baseline['copied_state_sha256']
    assert canonical(result['checkpoint_metadata']) == canonical(baseline['checkpoint_metadata'])
    assert canonical(result['numeric_policy']) == canonical(baseline['numeric_policy'])
    for field in ['q_min', 'q_max', 'q_mean']:
        assert result[field] == baseline[field], field
    proof = dict(schema='robotron-frozen-profile-CPU-compatibility-v1',
        checkpoint=job['checkpoint'], package=job['package'],
        matched_canonical_CPU_facts=job['canonical_CPU_facts'],
        source_files_verified=123, exact_synthetic_CPU_Q_summaries_match=True,
        inference_model_compatibility_passed=True, CUDA_initialized=False,
        synthetic_inputs_not_gameplay=True, GPU_numeric_or_gameplay_parity_proven=False,
        scientific_leg_launch_qualified=False, quality_qualified=False)
    with (Path(job['output']) / 'profile-compatibility.json').open('x') as stream:
        json.dump(proof, stream, indent=2)
        stream.flush()
        os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--job-sha256', required=True)
    args = parser.parse_args()
    main(json.loads(checked(dict(path=str(args.job), sha256=args.job_sha256)).read_bytes()))
