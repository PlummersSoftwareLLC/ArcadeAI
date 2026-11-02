"""Root-only offline projection of a captured immutable dose-observation prefix.

Never imports training code or reads live APIs, control, procfs, games or models.
Missing telemetry stays blank. Cumulative host counters are not interval/disk
service times; snapshot_lock_max_ms is a process-lifetime maximum.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

CASE = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/hot-LR9375-applied120k-replay40M-learner32M-original01-20261031')
INPUTS = CASE / 'dose-observations-original01'
ANALYZER_SHA = '2c35dfe9e94719913c507da89f5b0b69a5f0031b30633752a13d0a5c83524c48'
NAME = re.compile(r'([0-9]{6})-(analysis|sample)\.json')
MAX_PAIRS, MAX_FILE_BYTES, MAX_TOTAL_BYTES = 4096, 2 << 20, 256 << 20
SYSTEM_FIELDS = ('cpu_util', 'cpu_count', 'cpu_load_1m', 'cpu_load_5m', 'cpu_load_15m',
                 'ram_total_mib', 'ram_available_mib', 'ram_free_mib', 'ram_used_mib', 'ram_free_pct')


def require(ok, reason):
    if not ok: raise ValueError(reason)


def identity(s):
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def finite_float(text):
    value = float(text)
    require(math.isfinite(value), 'Nonfinite JSON number')
    return value


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def sealed(path, seen, budget, expected=None):
    require(path.parent == INPUTS and NAME.fullmatch(path.name), 'Exact dose metadata filename required')
    require(path.resolve() == path and INPUTS.resolve() == INPUTS, 'Canonical nonsymlink input required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o444
            and before.st_uid == os.getuid() and before.st_nlink == 1
            and 0 < before.st_size <= MAX_FILE_BYTES, 'Bounded owned sealed regular input required')
    if expected is not None:
        require(type(expected) is dict and expected.get('path') == str(path)
                and type(expected.get('bytes')) is int and expected['bytes'] == before.st_size
                and type(expected.get('sha256')) is str and re.fullmatch(r'[0-9a-f]{64}', expected['sha256']),
                'Exact sample descriptor required before opening')
    budget[0] += before.st_size
    require(budget[0] <= MAX_TOTAL_BYTES, 'Finite prefix byte bound exceeded')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(fd)) == identity(before), 'Opened input identity changed')
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, min(65536, MAX_FILE_BYTES + 1 - size))
            if not chunk: break
            chunks.append(chunk); size += len(chunk)
            require(size <= MAX_FILE_BYTES, 'Input grew beyond bound')
        require(identity(os.fstat(fd)) == identity(before), 'Input changed while reading')
    finally:
        os.close(fd)
    require(identity(path.lstat()) == identity(before), 'Input path changed while reading')
    raw = b''.join(chunks)
    require(len(raw) == before.st_size, 'Input byte count changed')
    pin = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=identity(before))
    if expected is not None:
        require(type(expected) is dict and all(expected.get(k) == pin[k] for k in ('path', 'sha256', 'bytes')),
                'Analysis/sample path, SHA or byte join failed')
        if 'identity' in expected:
            require(type(expected['identity']) is dict
                    and all(pin['identity'].get(k) == v for k, v in expected['identity'].items()), 'Sample identity join failed')
    seen.append(pin)
    def invalid_constant(value): raise ValueError('Nonfinite JSON constant: ' + value)
    value = json.loads(raw, object_pairs_hook=object_pairs, parse_float=finite_float, parse_constant=invalid_constant)
    require(type(value) is dict, 'Metadata object required')
    return value


def mapping(value):
    return value if type(value) is dict else {}


def cell(value):
    require(value is None or type(value) in (str, bool, int, float), 'Scalar telemetry required')
    require(type(value) is not float or math.isfinite(value), 'Finite telemetry required')
    return '' if value is None else value


def projection(index, analysis, sample):
    require(analysis.get('status') in ('VALID', 'PENDING', 'REJECTED')
            and analysis.get('source_sha256') == ANALYZER_SHA, 'Exact saved analyzer result required')
    require(sample.get('schema') == 'robotron-Root-LR9375-autoexpert-dose-observation-v1', 'Exact saved sample schema required')
    observed = analysis.get('observed_unix_s')
    require(type(observed) in (int, float) and observed > 0 and observed == sample.get('observed_unix_s'), 'Observation time join failed')
    api = mapping(sample.get('api_now')); bank = mapping(api.get('bank_persistence'))
    output = mapping(bank.get('output')); totals = mapping(output.get('totals'))
    dirty = mapping(bank.get('dirty')); delta = mapping(analysis.get('deltas'))
    row = dict(index=index, observed_unix_s=observed, API_ts=cell(api.get('ts')), status=analysis['status'],
               applied_updates_delta_from_anchor=cell(delta.get('applied_updates')), replay_additions_delta_from_anchor=cell(delta.get('replay_additions')),
               learner_frames_delta_from_anchor=cell(delta.get('learner_frames')), Main_FPS=cell(analysis.get('Main_FPS', api.get('fps'))),
               Main_loss=cell(analysis.get('Main_loss', api.get('loss'))), Main_grad_norm=cell(analysis.get('Main_grad_norm', api.get('grad_norm'))))
    for name in ('writer_active', 'capture_attempts', 'capture_deferrals', 'writes', 'write_failures',
                 'write_duration_s', 'last_write_duration_s', 'last_error'):
        suffix = '_total' if name in ('capture_attempts', 'capture_deferrals', 'writes', 'write_failures', 'write_duration_s') else ''
        row['bank_' + name + suffix] = cell(bank.get(name))
    row['bank_snapshot_lock_max_ms_lifetime'] = cell(bank.get('snapshot_lock_max_ms'))
    row.update(bank_dirty_hof=cell(dirty.get('hof')), bank_dirty_ephof=cell(dirty.get('ephof')),
               bank_output_backend=cell(output.get('backend')), bank_stream_output_enabled=cell(output.get('stream_output_enabled')),
               bank_output_schema=cell(output.get('schema')),
               bank_output_available=cell(output.get('available')),
               bank_output_active_json=(json.dumps(output['active'], separators=(',', ':'), allow_nan=False) if 'active' in output else ''),
               bank_API_read_error=cell(api.get('bank_persistence_read_error')),
               pipeline_read_error=cell(api.get('pipeline_read_error')), pipeline_snapshot_age_s=cell(api.get('pipeline_snapshot_age_s')))
    for phase, names in [('write', ('count', 'errors', 'host_total_ms', 'host_max_ms', 'payload_bytes', 'logical_bytes')),
                         ('file_fsync', ('count', 'errors', 'host_total_ms', 'host_max_ms'))]:
        for name in names:
            row['bank_field_' + phase + '_' + name + '_cumulative'] = cell(mapping(totals.get(phase)).get(name))
    policy = mapping(sample.get('continuous_policy')); stamp = policy.get('observed_monotonic_ns')
    recent = output.get('recent'); ended = []
    if type(recent) is list:
        ended = [event['ended_monotonic_ns'] for event in recent if type(event) is dict
                 and type(event.get('ended_monotonic_ns')) is int and event['ended_monotonic_ns'] > 0]
    row['bank_last_output_age_s_at_policy_observation'] = ''
    row['bank_last_output_age_reference_monotonic_ns'] = ''
    row['bank_last_output_age_reason'] = 'No saved policy monotonic timestamp'
    owner = mapping(sample.get('observed_main_owner')); policy_owner = mapping(policy.get('server_stamp'))
    row['observed_main_pid'] = cell(owner.get('pid'))
    row['observed_main_birth'] = cell(owner.get('birth'))
    row['bank_output_started_monotonic_ns'] = cell(output.get('started_monotonic_ns'))
    same_owner = all(type(owner.get(k)) is int and owner[k] > 0 and owner[k] == policy_owner.get(k) for k in ('pid', 'birth'))
    start = output.get('started_monotonic_ns')
    if type(stamp) is int and stamp > 0 and same_owner:
        row['bank_last_output_age_reference_monotonic_ns'] = stamp
        row['bank_last_output_age_reason'] = 'No retained completed field phase'
        if ended and type(start) is int and 0 < start <= max(ended) <= stamp:
            row['bank_last_output_age_s_at_policy_observation'] = (stamp - max(ended)) / 1e9
            row['bank_last_output_age_reason'] = 'Saved same-Main policy reference; includes cache/call skew'
        elif ended:
            row['bank_last_output_age_reason'] = 'Inconsistent or missing monotonic lineage; age unavailable'
    elif type(stamp) is int and stamp > 0:
        row['bank_last_output_age_reason'] = 'Policy/Main owner differs; age unavailable'
    for name in SYSTEM_FIELDS: row[name] = cell(api.get(name))
    return row


def write_new(path, raw):
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o444)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args(); out = args.output_directory
    require(out.parent == CASE and out.name.startswith('Root-bank-table-') and out.resolve() == out
            and not out.exists(), 'Fresh dedicated case output directory required')
    require(INPUTS.is_dir() and INPUTS.resolve() == INPUTS, 'Canonical saved dose directory required')
    paths = []
    for path in INPUTS.iterdir():
        if re.fullmatch(r'[0-9]{6}-analysis\.json', path.name):
            paths.append(path); require(len(paths) <= MAX_PAIRS, 'Finite completed-pair count bound exceeded')
    paths.sort()
    require(0 < len(paths) <= MAX_PAIRS, 'Bounded nonempty completed analysis prefix required')
    seen, rows, budget = [], [], [0]
    for path in paths:
        index = int(path.name[:6]); require(index > 0, 'Positive sample index required')
        analysis = sealed(path, seen, budget)
        sample_path = INPUTS / f'{index:06d}-sample.json'
        require(type(analysis.get('sample')) is dict, 'Saved analysis must identify its original sample')
        sample = sealed(sample_path, seen, budget, analysis.get('sample'))
        rows.append(projection(index, analysis, sample))
    for pin in seen: require(identity(Path(pin['path']).lstat()) == pin['identity'], 'Captured prefix identity changed')
    out.mkdir(mode=0o700, exist_ok=False)
    table = out / 'bank-persistence.csv'
    with table.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        stream.flush(); os.fsync(stream.fileno()); os.fchmod(stream.fileno(), 0o444)
    raw = table.read_bytes()
    summary = dict(schema='robotron-saved-bank-persistence-prefix-projection-v1', status='PROJECTED_SAVED_METADATA_ONLY',
                   rows=len(rows), first_index=rows[0]['index'], last_index=rows[-1]['index'], input_bytes=budget[0], inputs=seen,
                   CSV=dict(path=str(table), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)),
                   captured_analysis_filename_set_fixed_before_reading=True, new_later_pairs_not_followed=True,
                   qualification_or_causal_performance_claim=False, missing_values_blank_not_zero=True,
                   scope='Cumulative host/field-file telemetry; fsync totals exclude bank metadata/CURRENT/directory fsyncs; last-output age uses saved policy monotonic timestamp only; no Main mutation.')
    write_new(out / 'projection.json', (json.dumps(summary, sort_keys=True, allow_nan=False) + '\n').encode())
    print(json.dumps(dict(status=summary['status'], rows=len(rows), output=str(out))))


if __name__ == '__main__':
    main()
