"""Post-terminal stdlib audit: JSON joins and raw hashes, never tensor loading."""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time

REPO = Path('/home/dave/source/repos/ArcadeAI')
RUN = REPO / 'Robotron/logs/managed-learning-20261015/run-26/warmup-repeatability-reviewed1-20261017'
PROPOSAL = REPO / 'Robotron/tools/kl_priority_mixture_proposal/cuda_trace_validation_proposal/warmup_repeatability_proposal'
OUT = Path(__file__).resolve().parent
ROLES = ('base_a', 'base_repeat', 'off')
CASES = [dict(index=i + 1, diagnostics=i >= 2, empty=bool(i % 2)) for i in range(4)]
LOCK = '20057c290b1a9f121a03dfb5e81d33c67170a2d51807c0c149e295f393fa359e'
PREP = 'e475659e01593ee871709c5fc6548b4e1a0ef6e38a69137f1caa30a54e2fe0e6'
RUNTIME = REPO / 'Robotron/logs/managed-learning-20261015/run-26/warmup-repeatability-reviewed1-independent-runtime-review-20261017/terminal-cleanup-review.json'
RUNTIME_SHA = '7df310051a9f67f653d54328c79b3746c9136202b6cd0b43406853eeba84fdea'
INVENTORY = {}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(s):
    return {key: getattr(s, 'st_' + key) for key in
            ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns')}


def stable(path, sha=None, size=None, keep_bytes=False):
    """Hash a nofollow regular file; bracket exact FD/path metadata identity."""
    path = Path(path)
    key = str(path)
    if key in INVENTORY:
        record = INVENTORY[key]
        require(identity(path.lstat()) == record['identity'], 'Previously read file changed: ' + key)
        require(sha is None or record['sha256'] == sha, 'SHA mismatch: ' + key)
        require(size is None or record['bytes'] == size, 'Size mismatch: ' + key)
        if not keep_bytes:
            return record
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = identity(os.fstat(fd))
        require(stat.S_ISREG(before['mode']) and before == identity(path.lstat()), 'Not stable regular file: ' + key)
        h = hashlib.sha256()
        pieces = [] if keep_bytes else None
        count = 0
        while True:
            data = os.read(fd, 1024 * 1024)
            if not data:
                break
            h.update(data)
            count += len(data)
            if pieces is not None:
                pieces.append(data)
        require(before == identity(os.fstat(fd)) == identity(path.lstat()), 'File changed during hash: ' + key)
    finally:
        os.close(fd)
    record = dict(path=key, sha256=h.hexdigest(), bytes=count, identity=before)
    require(count == before['size'], 'Short read: ' + key)
    require(sha is None or record['sha256'] == sha, 'SHA mismatch: ' + key)
    require(size is None or count == size, 'Size mismatch: ' + key)
    INVENTORY[key] = record
    return (record, b''.join(pieces)) if keep_bytes else record


def finite_json(value):
    if isinstance(value, float):
        require(math.isfinite(value), 'Nonfinite JSON scalar')
    elif isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)


def read(path, sha=None):
    record, data = stable(path, sha=sha, keep_bytes=True)
    value = json.loads(data)
    finite_json(value)
    return value


def owned_record(record, expected_path):
    require(Path(record['path']) == expected_path and expected_path.is_relative_to(RUN), 'Wrong owned payload path')
    return stable(expected_path, record['sha256'], record['bytes'])


def main():
    started = time.monotonic()
    preparation = read(PROPOSAL / 'preparation-manifest.json', PREP)
    for name, record in preparation['files'].items():
        stable(PROPOSAL / name, record['sha256'], record['bytes'])
    for source, sha in preparation['pinned_sources_verified_sha256'].items():
        stable(source, sha)
    lock = read(PROPOSAL / 'source-lock.json', LOCK)
    launch = read(RUN / 'launch-manifest.json')
    aggregate = read(RUN / 'result.json')
    runtime_review = read(RUNTIME, RUNTIME_SHA)
    require(launch['parent'] == dict(pid=3569083, start_ticks='30052135', ppid=11124, pgid=3569083), 'Wrong parent identity')
    require(launch['variants'] == list(ROLES) and launch['warmup_cases'] == CASES and launch['attempts'] == 0, 'Wrong fixed protocol')
    require(launch['source_lock_sha256'] == LOCK and launch['numerical_protocol'] == lock, 'Protocol binding changed')
    require(aggregate['status'] == 'OBSERVATIONS_COMPLETE' and aggregate['owned_cleanup_complete'] is True, 'Not completed/cleaned')
    require(aggregate['qualification_pass'] is False and aggregate['comparison_pass'] is False and
            aggregate['interpretation_requires_review'] is True, 'Aggregate scope mismatch')
    require(len(aggregate['variants']) == 3 and aggregate['source_lock_sha256'] == LOCK, 'Aggregate lineage mismatch')
    for name, record in launch['sources'].items():
        stable(record['source'], record['sha256'])
        stable(RUN / 'private/Robotron/Scripts/dqn' / name, record['sha256'])
    inputs = read(RUN / 'inputs/inputs.json')
    input_sha = INVENTORY[str(RUN / 'inputs/inputs.json')]['sha256']
    require(inputs['seed'] == lock['seed'] and inputs['source_lock_sha256'] == LOCK and
            inputs['fixture_recipe'] == lock['fixture_recipe'] and inputs['checkpoint'] == lock['checkpoint'], 'Input provenance mismatch')
    require(set(inputs['files']) == {'trained.pt', 'batch.npz', 'draw.pt', 'torch-rng.pt'}, 'Input set changed')
    for name, record in inputs['files'].items():
        stable(RUN / 'inputs' / name, record['sha256'], record['bytes'])
    require(inputs['files']['trained.pt']['sha256'] == lock['checkpoint']['sha256'], 'Wrong trained fixture')
    zero_calls = dict(optimizer_step=0, scaler_step=0, scaler_update=0)
    expected_pre = expected_state = expected_runtime = None
    phase_rows = []
    summaries = []
    for role_index, role in enumerate(ROLES):
        folder = RUN / role
        phase = read(folder / 'phase-result.json')
        child = read(folder / 'child-exit.json')
        runtime = read(folder / 'runtime.json')
        require(phase == aggregate['variants'][role_index], 'Phase/aggregate row mismatch')
        require(phase['status'] == 'OBSERVATIONS_COMPLETE' and phase['variant'] == role and
                phase['qualification_pass'] is False and len(phase['cases']) == 4, 'Phase incomplete or qualification wrong')
        require(child['variant'] == role and child['actual_returncode'] == 0 and child['token_released'] is True,
                'Child did not finish normally')
        require(child['elapsed_s'] <= launch['bounds']['phase_timeout_s'], 'Phase timeout bound exceeded')
        require(phase['before'] == phase['after'] and phase['update_calls'] == zero_calls and
                phase['before']['persistent_finite'] is True, 'Reported persistent/update guard failed')
        before = phase['before']
        require(all(x == 0 for x in before['exposure']['total'].values()) and
                before['scaler']['scale'] == 1048576.0 and before['scaler']['_growth_tracker'] == 27,
                'Optimizer/scaler guard mismatch')
        require(sum(x == 1655313 for x in before['steps'].values()) == 81 and
                sum(x == 0 for x in before['steps'].values()) == 18, 'Saved Adam step map mismatch')
        require(phase['input_manifest_sha256'] == input_sha and phase['source_lock_sha256'] == LOCK, 'Phase input/source mismatch')
        loss_name = 'baseline_loss_kernel.py' if role != 'off' else 'loss_kernel.py'
        require(phase['source_loss_path'] == str(RUN / 'private/Robotron/Scripts/dqn' / loss_name) and
                phase['source_loss_sha256'] == launch['sources'][loss_name]['sha256'], 'Source role mismatch')
        require(runtime['effective_gil_enabled'] is False and runtime['native']['batch_available'] is True and
                runtime['native']['batch_enabled'] is True, 'Held runtime route mismatch')
        require(phase['peak_cuda_allocated'] <= launch['bounds']['vram_allocator_bytes'], 'Allocator bound exceeded')
        if expected_runtime is None:
            expected_runtime = runtime
        require(runtime == expected_runtime, 'Runtime flags differ between roles')
        case_summaries = []
        for case, row in zip(CASES, phase['cases']):
            label = 'case-%02d-diagnostic%d-empty%d' % (case['index'], case['diagnostics'], case['empty'])
            require(row['case'] == case and row['label'] == label and row['index'] == case['index'], 'Wrong case order')
            require(row == read(folder / (label + '.json')), 'Case/phase mismatch')
            entered = read(folder / (label + '.entered.json'))
            retained = read(folder / (label + '.payload-retained.json'))
            require(entered['variant'] == role and entered['case'] == case and entered['update_calls'] == zero_calls, 'Entered guard mismatch')
            for key in ('actual', 'case', 'index', 'label', 'pre_rng_sha256', 'post_rng_sha256', 'pre_state_sha256', 'post_state_sha256', 'update_calls'):
                require(retained[key] == row[key], 'Retained payload/control mismatch: ' + key)
            require(retained['comparisons'] == [] and retained['compared_to'] is None, 'Payload was not retained before comparisons')
            owned_record(row['actual'], folder / (label + '.actual.pt'))
            if expected_pre is None:
                expected_pre, expected_state = row['pre_rng_sha256'], row['pre_state_sha256']
            require(row['pre_rng_sha256'] == row['post_rng_sha256'] == expected_pre and
                    row['pre_state_sha256'] == row['post_state_sha256'] == expected_state and
                    entered['pre_rng_sha256'] == expected_pre and entered['pre_state_sha256'] == expected_state and
                    row['update_calls'] == zero_calls and row['rng_changed_components'] == [] and
                    row['cross_role_post_rng_changed_components'] == [], 'Reported RNG/scientific state control mismatch')
            summary = dict(index=case['index'], case=case, comparison_pass=row['comparison_pass'])
            if role == 'base_a':
                require(row['comparisons'] == [] and row['compared_to'] is None and row['comparison_scope'] == 'baseline_reference_only', 'BASE must be reference-only')
            else:
                comparison = read(folder / (label + '.comparison.json'))
                require(comparison == {k: v for k, v in row.items() if k != 'interpretation_requires_review'}, 'Final comparison evidence mismatch')
                require(row['comparison_complete'] is True and row['compared_to'] == phase_rows[0]['cases'][case['index'] - 1]['actual'], 'Wrong fresh reference')
                records = row['comparisons']
                paths = {record['path']: record for record in records}
                require(len(paths) == len(records) == 85, 'Unexpected recorded comparison path count')
                gradients = [r for r in records if r['path'].startswith(label + '/gradient/')]
                require(len(gradients) == 81, 'Unexpected exercised gradient count')
                failed = [r for r in records if r['passed'] is False]
                require(row['comparison_pass'] == (not failed) and row['interpretation_requires_review'] == bool(failed), 'Case comparison/review summary mismatch')
                for record in records:
                    path = record['path']
                    key = 'ce' if path.endswith('/ce') else 'scalars' if path.endswith(('/loss', '/bc_loss')) else 'gradient'
                    require(record['tolerance'] == lock['tolerances'][key], 'Tolerance changed: ' + path)
                    if 'actual_sha256' in record:
                        require(record['passed'] == (record['violations'] == 0), 'Tensor violation summary mismatch')
                    else:
                        require(record['passed'] == math.isclose(record['actual'], record['expected'], rel_tol=record['tolerance']['rtol'], abs_tol=record['tolerance']['atol']), 'Scalar predicate mismatch')
                failed_tensors = [r for r in failed if 'actual_sha256' in r]
                require(bool(failed_tensors) == ('all_failed_coordinate_masks' in row), 'Missing/spurious violation masks')
                if failed_tensors:
                    owned_record(row['all_failed_coordinate_masks'], folder / (label + '.violations.pt'))
                ce = paths[label + '/ce']
                diag = paths[label + '/diagnostic_output']
                summary.update(
                    ce=dict(exact_hash_equal=ce['actual_sha256'] == ce['expected_sha256'], **ce),
                    loss=dict(exact_value_equal=paths[label + '/loss']['actual'] == paths[label + '/loss']['expected'], **paths[label + '/loss']),
                    bc_loss=dict(exact_value_equal=paths[label + '/bc_loss']['actual'] == paths[label + '/bc_loss']['expected'], **paths[label + '/bc_loss']),
                    diagnostic_output=dict(exact_hash_equal=diag['actual_sha256'] == diag['expected_sha256'], **diag),
                    gradients=dict(recorded_tensors=len(gradients), failed_tensors=len([g for g in gradients if not g['passed']]),
                        exact_hash_equal_tensors=sum(g['actual_sha256'] == g['expected_sha256'] for g in gradients),
                        failed_coordinates=sum(g['violations'] for g in gradients),
                        l2_error_from_recorded_per_tensor_norms=math.sqrt(sum(g['l2_error'] ** 2 for g in gradients)),
                        reference_l2_from_recorded_per_tensor_norms=math.sqrt(sum(g['reference_l2'] ** 2 for g in gradients)),
                        failed_records=[g for g in gradients if not g['passed']]))
            case_summaries.append(summary)
        require(phase['comparison_pass'] == all(row['comparison_pass'] for row in phase['cases']), 'Phase summary inconsistent')
        require(phase['interpretation_requires_review'] == any(row['interpretation_requires_review'] for row in phase['cases']), 'Phase review inconsistent')
        require(not list(folder.glob('case-*.failure.json')) and not (folder / 'phase-failure.json').exists(), 'Unexpected fatal evidence')
        require(not list(folder.glob('attempt*')) and not (folder / 'ce-executed-trace-cuda-validation').exists(), 'Unexpected actual optimizer/ON trace artifacts')
        phase_rows.append(phase)
        summaries.append(dict(role=role, actual_returncode=child['actual_returncode'], elapsed_s=child['elapsed_s'],
            comparison_pass=phase['comparison_pass'], qualification_pass=False,
            interpretation_requires_review=phase['interpretation_requires_review'], peak_cuda_allocated=phase['peak_cuda_allocated'],
            peak_cuda_reserved=phase['peak_cuda_reserved'], cases=case_summaries))
    for path, record in INVENTORY.items():
        require(identity(Path(path).lstat()) == record['identity'], 'Artifact changed before receipt: ' + path)
    require(not any(name in sys.modules for name in ('torch', 'numpy', 'dqn')), 'Numerical/framework import occurred')
    receipt = dict(schema='robotron-warmup-json-hash-scientific-review-v1', status='PASS_WITH_REPORTED_AA_REPEATABILITY_MISMATCH',
        actual_diagnostic_status=aggregate['status'], qualification_pass=False, comparison_pass=False, interpretation_requires_review=True,
        completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), elapsed_s=time.monotonic() - started,
        run=str(RUN), parent_identity=launch['parent'], original_invocation='7feaeb7b47174978a8c102eae18282c2',
        runtime_cleanup_receipt=dict(path=str(RUNTIME), sha256=RUNTIME_SHA, status=runtime_review['status'],
            independently_audited_by='runtime_review; not rerun by this auditor'),
        source_lock_sha256=LOCK, preparation_manifest_sha256=PREP, phases=summaries,
        scientific_control_summary=dict(cases=12, attempts=0, optimizer_steps=0, scaler_steps=0, scaler_updates=0,
            runtime_flags=expected_runtime, persistent_scientific_state_sha256=expected_state, rng_sha256=expected_pre,
            per_role_before_after_observations_equal=True, all_case_pre_post_controls_equal=True),
        artifact_files=len(INVENTORY), artifact_bytes=sum(r['bytes'] for r in INVENTORY.values()), artifacts=list(INVENTORY.values()),
        interpretation=[
            'Same-source BASE_REPEAT exceeded original gradient tolerance in first two cases; all cases completed.',
            'OFF passed all four fresh BASE_A comparisons in this run; neither outcome qualifies full-step OFF/ON parity.',
            'All scalar losses and BC losses were exact in the recorded comparisons; per-case CE/diagnostic hashes and gradient norms are retained separately.',
            'No causal CUDA operator, original failure parameter, deterministic continuation, learning quality, or live adoption claim.'],
        limitations=[
            'No Torch/NumPy/framework import or tensor/model deserialization; tensor values, finiteness, masks and comparisons are producer-reported with independently verified raw artifact hashes and JSON joins.',
            'Raw stream hashes prove archived byte identity, not independent numerical recomputation.',
            'Full tensor/RNG payloads retained before comparison; their internal fields were not deserialized by this audit.',
            'Backward-only compile cases with per-case RNG reset differ from old sequential warmups; no optimizer outcomes/ON observer/full train-step proof.',
            'Display GPU0 differs from the live main GB300; fixed synthetic batch is not actual replay-population capture.',
            'Original service exit and actual process/GPU/cgroup cleanup were independently audited by runtime_review, not queried here.'])
    destination = OUT / 'review-receipt.json'
    with destination.open('x') as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps(dict(status=receipt['status'], receipt=str(destination), artifact_files=receipt['artifact_files'],
        artifact_bytes=receipt['artifact_bytes'], elapsed_s=receipt['elapsed_s'],
        summary=[dict(role=p['role'], comparison_pass=p['comparison_pass'], cases=[dict(index=c['index'],
            comparison_pass=c['comparison_pass'], gradient_failed=c.get('gradients', {}).get('failed_tensors')) for c in p['cases']]) for p in summaries])))


if __name__ == '__main__':
    main()
