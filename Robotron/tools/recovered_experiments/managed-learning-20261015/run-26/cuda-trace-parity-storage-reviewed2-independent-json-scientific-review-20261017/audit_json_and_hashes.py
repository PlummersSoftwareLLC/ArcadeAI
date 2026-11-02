"""Read-only stdlib audit of the terminal reviewed2 run; never deserialize tensors."""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat

GAME = Path(__file__).resolve().parents[4]
RUN = GAME / 'logs/managed-learning-20261015/run-26/cuda-trace-parity-storage-reviewed2-20261017'
HERE = Path(__file__).resolve().parent
SOURCE = GAME / 'tools/kl_priority_mixture_proposal/cuda_trace_validation_proposal/storage_watcher_revision'
PIN = dict(parent='077420acc0d643f345225c66b0e8430d7f30f49b45a80c136153be57916ea470',
           worker='ba0039d406676f092309c6bf2248ddcf169af8960f60ed18b698ece1ea602f93',
           lock='d6ffdaae63d97bce24a18d1b11ed165b9e12484d17d65365415aab3c08beb13b',
           revision='5572396f25c0ee64943f75c4bc65cc994c02be2ddb18f2b897ea95893803176d')
files = {}


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def identity(info):
    return {name:getattr(info, 'st_' + name) for name in
            ('dev','ino','mode','uid','gid','nlink','size','mtime_ns','ctime_ns')}


def fingerprint(path, expected=None, expected_bytes=None):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve() and not path.is_symlink(), 'Noncanonical file: ' + str(path))
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid(), 'Unowned/nonregular file')
        view = identity(before)
        require(identity(path.lstat()) == view, 'Path/FD changed before hash')
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(identity(os.fstat(stream.fileno())) == view and identity(path.lstat()) == view, 'File changed during hash')
    require(expected is None or digest == expected, 'SHA mismatch: ' + str(path))
    require(expected_bytes is None or view['size'] == expected_bytes, 'Size mismatch: ' + str(path))
    result = dict(path=str(path), sha256=digest, bytes=view['size'], identity=view)
    files[str(path)] = result
    return result


def read_json(path):
    before = fingerprint(path)
    value = json.loads(Path(path).read_text())
    require(fingerprint(path) == before, 'JSON changed during audit')
    return value


def main():
    for key, name in (('parent','cuda_trace_parent.py'),('worker','cuda_trace_worker.py'),
                      ('lock','source-lock.json'),('revision','revision-manifest.json')):
        fingerprint(SOURCE / name, PIN[key])
    manifest = read_json(RUN / 'launch-manifest.json')
    require(manifest['parent_sha256'] == PIN['parent'] and manifest['worker_sha256'] == PIN['worker']
            and manifest['source_lock_sha256'] == PIN['lock'], 'Launch code mismatch')
    require(manifest['parent']['pid'] == 3479610 and manifest['parent']['start_ticks'] == '29814424', 'Parent identity mismatch')
    lock = read_json(SOURCE / 'source-lock.json')
    require(lock['attempts'] == 8 and lock['batch_rows'] == 4096 and lock['state_width'] == 11128, 'Fixed shape changed')
    input_description = read_json(RUN / 'inputs/inputs.json')
    require(input_description['source_lock_sha256'] == PIN['lock'], 'Input protocol mismatch')
    for name, record in input_description['files'].items():
        require(Path(name).name == name, 'Input traversal')
        fingerprint(RUN / 'inputs' / name, record['sha256'], record['bytes'])
    phase = read_json(RUN / 'base/phase-result.json')
    require(phase['status'] == 'VARIANT_COMPLETE' and phase['variant'] == 'base', 'Base incomplete')
    require(phase['source_lock_sha256'] == PIN['lock'] and phase['input_manifest_sha256'] ==
            files[str(RUN / 'inputs/inputs.json')]['sha256'], 'Base input/source mismatch')
    require(len(phase['attempts']) == len(phase['references']) == 8, 'Base length mismatch')
    warmup = read_json(RUN / 'base/warmup-proof.json')
    require(warmup['before'] == warmup['after'] and warmup['trace_consumed'] == 0
            and warmup['expected_abi'] == 4 and warmup['counters']['stats']['unique_graphs'] == 2
            and not warmup['counters']['graph_break'], 'Warmup state/ABI contract failed')
    for path in sorted((RUN / 'base').glob('warmup-*.pt')):
        fingerprint(path)
    rows = []
    previous = warmup['after']
    for index in range(1, 9):
        entered = read_json(RUN / 'base' / ('attempt-%02d.entered.json' % index))
        row = read_json(RUN / 'base' / ('attempt-%02d.json' % index))
        before, after = row['before'], row['after']
        require(row['index'] == index and row['status'] == 'COMPLETE' and row['released'], 'Bad ordinal/lease')
        require(entered['index'] == index and entered['before'] == before == previous, 'Attempt discontinuity')
        require(before['persistent_finite'] and after['persistent_finite'], 'Persistent nonfinite report')
        old, new = before['exposure'], after['exposure']
        require(all(old[key] == new[key] for key in ('schema','process_id','instance_monotonic_ns','epoch')), 'Exposure identity drift')
        delta = {key:new['total'][key]-old['total'][key] for key in old['total']}
        require(new['enabled'] and new['available'] and delta['attempts_started'] == delta['outcomes_recorded'] == 1
                and delta['unavailable'] == 0 and new['unclassified_started_total'] == 0, 'Unsupported outcome')
        require(before['steps'].keys() == after['steps'].keys(), 'Adam slot identity drift')
        require(all(math.isfinite(value) and value >= 0 and value.is_integer() for value in after['steps'].values()), 'Bad Adam clock')
        advanced = [name for name,value in before['steps'].items() if after['steps'][name] > value]
        require(all(after['steps'][name] >= value for name,value in before['steps'].items()), 'Adam regression')
        if row['outcome'] == 'amp_skipped':
            require(delta['amp_skipped'] == 1 and delta['applied'] == 0 and not advanced
                    and before['steps'] == after['steps'] and before['online'] == after['online']
                    and before['moments'] == after['moments']
                    and 0 < after['scaler']['scale'] < before['scaler']['scale'], 'Unproven skip')
        else:
            require(row['outcome'] == 'applied' and delta['applied'] == 1 and delta['amp_skipped'] == 0
                    and len(advanced) == 81 and before['online'] != after['online']
                    and before['moments'] != after['moments'], 'No recorded applied progress')
        require(after['clocks']['training_steps'] == before['clocks']['training_steps'] + 1
                and after['clocks']['optimized_samples'] == before['clocks']['optimized_samples'] + 4096, 'Logical clock step mismatch')
        summary = phase['attempts'][index-1]
        require(summary['index'] == index and summary['outcome'] == row['outcome']
                and summary['adam_steps'] == after['steps'] and summary['scaler'] == after['scaler']
                and summary['clocks'] == after['clocks'], 'Phase row mismatch')
        reference = phase['references'][index-1]
        expected_path = RUN / 'base' / ('reference-%02d.pt' % index)
        require(reference['path'] == str(expected_path), 'Wrong reference path')
        fingerprint(expected_path, reference['sha256'], reference['bytes'])
        rows.append(dict(index=index,outcome=row['outcome'],named_slots=len(after['steps']),advanced_slots=len(advanced),
                         scale_before=before['scaler']['scale'],scale_after=after['scaler']['scale'],
                         persistent_finite_reported=True,exposure_delta=delta))
        previous = after
    require([row['outcome'] for row in rows] == ['amp_skipped']*4 + ['applied','amp_skipped','applied','applied'], 'Unexpected actual sequence')
    require(phase['actual_applied'] == 3 and phase['effective_gil_after_compile'] is False, 'Base totals/runtime differ')
    require(not phase['actual_gpu_full_step_diagnostic_route'] and phase['static_both_diagnostic_flags_warmed'], 'Diagnostic scope differs')
    for variant in ('base','off','on'):
        require(not list((RUN / variant).glob('attempt-09*')), 'Unexpected ninth attempt')
        if variant != 'base':
            require(not list((RUN / variant).glob('attempt-*.json')) and not (RUN / variant / 'phase-result.json').exists(), 'Unexpected candidate evidence')
    children = {variant:read_json(RUN / variant / 'child-exit.json') for variant in ('base','off')}
    require(children['base']['actual_returncode'] == 0 and children['off']['actual_returncode'] == -15, 'Child exits differ')
    failure = read_json(RUN / 'failure.json')
    require(failure == {'status':'VALIDATION_ERROR','error':"ProcessLookupError(3, 'No such process')"}, 'Parent failure differs')
    require(not (RUN / 'result.json').exists() and not (RUN / 'cleanup-failure.json').exists(), 'Unexpected aggregate result/cleanup failure')
    for variant in ('base','off'):
        runtime = read_json(RUN / variant / 'runtime.json')
        require(runtime['effective_gil_enabled'] is False and runtime['native']['batch_available']
                and runtime['native']['batch_enabled'], 'Runtime profile differs')
    for name, record in manifest['sources'].items():
        require(Path(name).name == name, 'Source-copy traversal')
        fingerprint(RUN / 'private/Robotron/Scripts/dqn' / name, record['sha256'])
    receipt = dict(schema='robotron-cuda-reviewed2-independent-json-science-audit-v1',
        completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        audit_status='PASS_FAILED_RUN_EVIDENCE',run_status='VALIDATION_ERROR_INCOMPLETE_OFF_ON',
        root_authoritative_terminal=dict(unit='robotron-snapshot-smoke-ce-trace-storage-reviewed2-20261017.service',
            invocation='bed1d82d91f84dfb8834408c02a44ea7',pid=3479610,start_ticks='29814424',
            exec_main_code=1,exec_main_status=1,scope='Root-provided original terminal observation; not independently queried here'),
        parent_error=failure,attempts=rows,base_actual_applied=3,base_actual_amp_skipped=5,
        base_final_clocks=previous['clocks'],base_final_scaler=previous['scaler'],
        base_peak_cuda_allocated=phase['peak_cuda_allocated'],base_peak_cuda_reserved=phase['peak_cuda_reserved'],
        base_warmup=dict(abi=4,unique_graphs=2,graph_breaks=0,trace_consumed=0,all_recorded_persistent_state_unchanged=True),
        fixed_tolerances=lock['tolerances'],references_hashed_without_loading=True,
        off=dict(attempts=0,child=children['off']),on=dict(attempts=0,started=False),
        scope=dict(fixed_synthetic_batch_reuses=8,actual_sampler_calls_to_create_batch=1,
                   live_mixture=False,full_agent_lifecycle=False,off_on_parity_established=False,
                   intervariant_rng_or_tolerance_comparisons_exist=False,neural_tensors_deserialized=False,
                   base_native_gradient_finiteness='Asserted by frozen worker for applied calls; not independently recomputed from tensors',
                   base_rng='Persisted input RNG file independently SHA-verified; no candidate parity exists',
                   actual_cleanup='Owned lifecycle audited separately by runtime_review/root; no proc/GPU/cgroup query here'),
        file_evidence=list(files.values()),audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    target = HERE / 'review-receipt.json'
    with target.open('x') as stream:
        json.dump(receipt,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    target.chmod(0o444)
    print(json.dumps(dict(status=receipt['audit_status'],receipt=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                         hashed_files=len(files),base_attempts=8,applied=3,skipped=5,off_attempts=0,on_attempts=0)))


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        with (HERE/'audit-failure.json').open('x') as stream:
            json.dump(dict(status='AUDIT_ERROR',error=repr(error),files_completed=list(files.values())),stream,indent=2)
            stream.write('\n')
        raise
