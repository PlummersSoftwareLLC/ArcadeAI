"""CPU-only engineering capacity check; synthetic metadata is never runtime proof."""
import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import weakref


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def execute(args):
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.source_sha256, 'Exact scale-check source required')
    raw = args.job.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == args.job_sha256, 'Exact scale job required')
    job = json.loads(raw)
    require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and 'torch' not in sys.modules, 'CPU-only engineering required')
    fields = dict(line.split('=',1) for line in subprocess.check_output(
        ['systemctl','--user','show',job['unit']],text=True,timeout=5).splitlines() if '=' in line)
    expected = dict(MainPID=str(os.getpid()),InvocationID=os.environ['INVOCATION_ID'],CPUQuotaPerSecUSec='2s',
        MemoryMax=str(4 << 30),MemorySwapMax='0',TasksMax='128',RuntimeMaxUSec='3min',NRestarts='0',Restart='no')
    require(all(fields.get(key) == value for key,value in expected.items()), 'Actual2CPU/4GiB/180s scope differs')
    h = load('_observer_scale_helpers', Path(job['helpers']['path']))
    for pin in job['inputs']:
        h.checked(pin)
    class TrackedSnapshot(dict):
        __slots__ = ('__weakref__',)
    replays, manifests = [], []
    for number, case in enumerate(job['cases']):
        life = json.loads(h.checked(case['lifecycle']).read_bytes())
        outcome = json.loads(h.checked(life['outcome']).read_bytes())
        reader = load('_observer_scale_reader_'+str(number), h.checked(case['new_reviewer']))
        original = load('_observer_scale_old_reader_'+str(number), h.checked(case['old_reviewer']))
        def run_review(module):
            original_read = module.read
            references = []
            peak = 0
            def tracking(pin, helpers):
                nonlocal peak
                value = original_read(pin, helpers)
                if value.get('schema') == 'robotron-round-observer-raw-sample-v1':
                    value['snapshot'] = TrackedSnapshot(value['snapshot'])
                    references.append(weakref.ref(value['snapshot']))
                    peak = max(peak,sum(ref() is not None for ref in references))
                return value
            module.read = tracking
            start = time.monotonic()
            try:
                result = module.verify(case['lifecycle'], h)
            finally:
                module.read = original_read
            gc.collect()
            return result,peak,time.monotonic()-start
        fresh, peak, elapsed = run_review(reader)
        old, old_peak, old_elapsed = run_review(original)
        require(fresh == old and fresh['accepted_samples'] == len(outcome['samples']), 'Streaming reviewer changed actual proof')
        require(peak <= 3 and old_peak == len(outcome['samples']), 'Full raw-snapshot retention did not become bounded')
        replays.append(dict(case=case['name'],actual_samples=fresh['accepted_samples'],
            proof_identical=True,new_live_full_snapshots_peak=peak,old_live_full_snapshots_peak=old_peak,
            new_elapsed_s=elapsed,old_elapsed_s=old_elapsed))
        common = load('_observer_scale_common_'+str(number), h.checked(case['worker']))
        with tempfile.TemporaryDirectory(prefix='robotron-observer-capacity-') as temporary:
            path = Path(temporary)/'SYNTHETIC_METADATA_NOT_RUNTIME.json'
            count,limit = case['maximum_samples'],case['manifest_limit_MiB'] << 20
            fixture = dict(schema='robotron-observer-SYNTHETIC-capacity-fixture-v1',
                engineering_only=True,scientific_runtime_proof=False,
                samples=[outcome['samples'][index % len(outcome['samples'])] for index in range(count)],
                publications=[dict(index=index,updated_monotonic_s=float(index)) for index in range(count)])
            with path.open('x') as stream:
                json.dump(fixture,stream,indent=2,allow_nan=False)
            path.chmod(0o444)
            del fixture
            size = path.stat().st_size
            require(8 << 20 < size < limit, 'Declared ceiling did not exercise the old8MiB failure or fit new bound')
            try:
                common.read(path)
            except ValueError as error:
                require('bound' in str(error), 'Old reader failed for an unrelated reason')
            else:
                raise ValueError('Old8MiB reader unexpectedly accepted the capacity fixture')
            parsed = common.read(path,limit=limit)
            require(len(parsed['samples']) == len(parsed['publications']) == count
                    and parsed['scientific_runtime_proof'] is False, 'Bounded outcome reader lost synthetic metadata')
            del parsed
            verified = reader.read(h.pin(path),h)
            require(len(verified['samples']) == count, 'Sealed full manifest reader lost metadata')
            del verified
            # Only three original raw snapshots may be retained, even though their complete bytes are checked.
            manifests.append(dict(case=case['name'],synthetic_sample_count=count,bytes=size,
                bounded_reader_limit_bytes=limit,old8MiB_rejected=True,new_bounded_and_sealed_readers_passed=True,
                scientific_runtime_proof=False))
    require('torch' not in sys.modules, 'Scale check imported Torch')
    for pin in job['inputs']:
        h.checked(pin)
    out = Path(job['output'])
    out.mkdir(mode=0o700)
    proof = h.put(out/'report.json',dict(schema='robotron-observer-capacity-engineering-result-v1',status='PASS',
        original_job=h.pin(args.job),actual_PID=os.getpid(),actual_scope=fields,
        real_closed_component_replays=replays,synthetic_metadata_capacity=manifests,
        peak_process_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        Torch_imported=False,GPU_or_MAME_launched=False,main_changed=False,
        long_duration_scientific_runtime_exercised=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(report=proof,status='PASS',peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--job',type=Path)
    parser.add_argument('--job-sha256')
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if args.execute:
        execute(args)
    else:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
