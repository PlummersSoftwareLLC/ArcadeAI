"""Replay real closed evidence and bound synthetic maximum-duration metadata.

Synthetic repeated pins exercise memory and reader ceilings only. They are
never passed to the scientific verifier or used as duration/game evidence.
"""
import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time
import weakref


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def execute(args):
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256
    assert hashlib.sha256(args.job.read_bytes()).hexdigest() == args.job_sha256
    job = json.loads(args.job.read_bytes())
    assert job['schema'] == 'robotron-async-observer-capacity-engineering-job-v1'
    assert os.environ['CUDA_VISIBLE_DEVICES'] == '' and 'torch' not in sys.modules
    h = load('_async_capacity_helpers', Path(job['helpers']['path']))
    for pin in job['inputs']:
        h.checked(pin)
    reports = []

    class TrackedSnapshot(dict):
        __slots__ = ('__weakref__',)

    for index, case in enumerate(job['cases']):
        review = load('_async_capacity_actual_reviewer_'+str(index), h.checked(case['reviewer']))
        common = load('_async_capacity_common_'+str(index), h.checked(case['worker']))
        prior = json.loads(h.checked(case['actual_review']).read_bytes())
        life = json.loads(h.checked(prior['lifecycle']).read_bytes())
        outcome = json.loads(h.checked(life['outcome']).read_bytes())
        assert outcome['success'] is True and outcome['all_writer_threads_stopped'] is True
        original_read = review.read
        references = []
        peak = [0]

        def tracking(pin, helpers):
            value = original_read(pin, helpers)
            if value.get('schema') == 'robotron-round-observer-raw-sample-v1':
                value['snapshot'] = TrackedSnapshot(value['snapshot'])
                references.append(weakref.ref(value['snapshot']))
                peak[0] = max(peak[0], sum(ref() is not None for ref in references))
            return value

        review.read = tracking
        started = time.monotonic()
        try:
            replayed = review.verify(prior['lifecycle'], h)
        finally:
            review.read = original_read
        assert replayed == prior and replayed['accepted_samples'] >= 3000
        assert peak[0] <= 3
        gc.collect()
        assert not any(ref() is not None for ref in references)
        elapsed = time.monotonic()-started
        with tempfile.TemporaryDirectory(prefix='robotron-async-capacity-') as temporary:
            path = Path(temporary)/'SYNTHETIC-REPEATED-METADATA-NOT-RUNTIME.json'
            count = case['maximum_samples']
            fixture = dict(schema='robotron-async-SYNTHETIC-metadata-capacity-v1',
                engineering_only=True, scientific_runtime_proof=False,
                samples=[outcome['samples'][i % len(outcome['samples'])] for i in range(count)],
                publications=[dict(index=i, updated_monotonic_s=float(i)) for i in range(count)],
                initial=outcome['initial'], durability_seal=outcome['durability_seal'])
            path.write_text(json.dumps(fixture, indent=2, allow_nan=False))
            path.chmod(0o444)
            del fixture
            size = path.stat().st_size
            limit = case['manifest_limit_bytes']
            assert 8 << 20 < size < limit
            try:
                common.read(path)
            except ValueError as error:
                assert 'bound' in str(error)
            else:
                raise AssertionError('Synthetic maximum manifest did not exercise old8MiB ceiling')
            parsed = common.read(path, limit=limit)
            assert len(parsed['samples']) == len(parsed['publications']) == count
            assert parsed['scientific_runtime_proof'] is False
            del parsed
            parsed = review.read(h.pin(path), h)
            assert len(parsed['samples']) == count
            del parsed
            gc.collect()
        reports.append(dict(name=case['name'], real_accepted_samples=prior['accepted_samples'],
            actual_raw_proof_identical=True, peak_retained_full_raw_snapshots=peak[0],
            real_replay_elapsed_s=elapsed, synthetic_metadata_samples=count,
            synthetic_metadata_bytes=size, reader_limit_bytes=limit,
            raw_and_sealed_manifest_readers_accepted=True, synthetic_runtime_proof=False))
    for pin in job['inputs']:
        h.checked(pin)
    directory = Path(job['output'])
    directory.mkdir(mode=0o700)
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    assert peak_rss < 4 << 30 and 'torch' not in sys.modules
    h.put(directory/'report.json', dict(schema='robotron-async-observer-capacity-engineering-result-v1',
        status='PASS', original_job=h.pin(args.job), actual_PID=os.getpid(), cases=reports,
        peak_process_RSS_bytes=peak_rss, Torch_imported=False, GPU_or_MAME_launched=False,
        long_duration_scientific_runtime_exercised=False, quality_qualified=False, promotion=False))
    print(json.dumps(dict(status='PASS', cases=reports, peak_RSS_bytes=peak_rss)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--job', type=Path)
    p.add_argument('--job-sha256')
    p.add_argument('--source-sha256')
    args = p.parse_args()
    if args.execute:
        execute(args)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
