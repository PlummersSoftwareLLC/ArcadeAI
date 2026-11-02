"""Root-owned finite passive observation; no training, control, GPU or unit writes."""
import csv
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
R = G / 'logs/managed-learning-20261015/run-26'
P = R / 'continuous-guard-same-LR25-continuation-original01-root-preparation-20261018'
OUT = R / 'continuous-guard-same-LR25-passive-cap120-original01-20261018'
EXPERIMENT = 'CE4096-continuous-zero-dip-guard-LR25-continuation-trial01-20261018'
OWNERS = (
    ('robotron-managed-run-26-d3b365c9-trainer.service', 2863379, 39797375, '5a8bfc5e10674a8e9169978804378393'),
    ('robotron-continuous-guard-same-LR25-continuation-capture-original01-20261018.service', 254301, 44388221, '6c35df9bfd524df683cf541f34a53bc8'),
)


def pin(path):
    raw = path.read_bytes()
    s = path.stat()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                              mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns,
                              mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink))


def publish(path, value, raw=False):
    data = value if raw else (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fchmod(f.fileno(), 0o444)
        os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)
    return pin(path)


def sample(index, started):
    owners = []
    for unit, pid, ticks, invocation in OWNERS:
        result = subprocess.run(['systemctl', '--user', 'show', unit, '-p', 'MainPID',
                                 '-p', 'InvocationID', '-p', 'NRestarts', '-p', 'ActiveState',
                                 '-p', 'SubState'], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        assert fields['MainPID'] == str(pid) and fields['InvocationID'] == invocation
        assert fields['NRestarts'] == '0' and fields['ActiveState'] == 'active' and fields['SubState'] == 'running'
        actual = int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
        assert actual == ticks
        owners.append(dict(unit=unit, fields=fields, starttime_ticks=actual))
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=10) as response:
        raw_api = response.read((4 << 20) + 1)
    assert len(raw_api) <= 4 << 20
    api = json.loads(raw_api)
    assert api['client_count'] == 192 and api['training_enabled'] is True
    assert api['managed_experiment'] == EXPERIMENT and api['lr'] == 1.25e-5
    assert 0 <= api['pipeline_snapshot_age_s'] <= 5
    assert not api['pipeline_read_error'] and not api['bank_persistence_read_error']
    api_pin = publish(OUT / ('sample-%02d-API.json' % index), raw_api, True)
    with (R / 'training.csv').open('rb') as f:
        before = os.fstat(f.fileno())
        header = f.readline(65537)
        assert len(header) <= 65536 and header.endswith(b'\n')
        f.seek(0, 2)
        offset = max(len(header), f.tell() - (1 << 20))
        f.seek(offset)
        tail = f.read(1 << 20)
        after = os.fstat(f.fileno())
    if offset > len(header):
        tail = tail.split(b'\n', 1)[1]
    if not tail.endswith(b'\n'):
        tail = tail.rsplit(b'\n', 1)[0] + b'\n'
    assert before.st_dev == after.st_dev and before.st_ino == after.st_ino
    snapshot = header + tail
    rows = list(csv.DictReader(io.StringIO(snapshot.decode()), strict=True))
    assert rows and None not in rows[-1] and all(v is not None for v in rows[-1].values())
    row = rows[-1]
    row_wall = datetime.datetime.fromisoformat(row['utc']).timestamp()
    assert 0 <= time.time() - row_wall <= 60
    assert row['experiment'] == EXPERIMENT and row['mode'] == 'TRAIN'
    assert row['measurement_active'] == 'False' and int(row['clients']) == 192
    assert float(row['replay_sample_cap']) == 8 and int(row['batch_size']) == 4096
    assert int(row['replay_size']) == 6000000
    assert not row['pipeline_read_error'] and row['pipeline_counter_reset'] == 'False'
    csv_pin = publish(OUT / ('sample-%02d-bounded-training.csv' % index), snapshot, True)
    record = dict(index=index, observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  elapsed_observation_s=time.monotonic()-started, owners=owners, API=api_pin,
                  csv_snapshot=csv_pin, csv_observation=dict(path=str(R/'training.csv'),
                  device=before.st_dev, inode=before.st_ino, bytes_before=before.st_size,
                  bytes_after=after.st_size, read_offset=offset), row=row)
    publish(OUT / ('sample-%02d.json' % index), record)
    print(json.dumps(dict(sample=index, csv_utc=row['utc'], frames=row['frames'],
                         samples=row['optimized_samples'], waits=row['replay_pressure_waits'])), flush=True)
    return record


def main():
    if sys.argv[1:] != ['--execute']:
        print('PLAN_ONLY_NO_READS_OR_ACTIONS')
        return
    case_path = P / 'original02-fresh-capture-case.json'
    case = json.loads(case_path.read_text())
    baseline = json.loads(Path(case['runtime_baseline']['path']).read_text())
    source_names = {'training.py', 'agent.py', 'loss_kernel.py', 'metrics_display.py', 'run_telemetry.py'}
    sources = {path: sha for path, sha in baseline['source_hashes'].items() if Path(path).name in source_names}
    assert {Path(path).name for path in sources} == source_names
    before_sources = [pin(Path(path)) for path in sorted(sources)]
    assert all(p['sha256'] == sources[p['path']] for p in before_sources)
    OUT.mkdir(mode=0o700)
    publish(OUT/'precommit.json', dict(schema='robotron-root-passive-cap120-v1',
            source=pin(Path(__file__).resolve()), duration_s=120, sample_offsets_s=[0, 30, 60, 90, 120],
            expected_owners=OWNERS, experiment=EXPERIMENT, cap=8, batch_size=4096,
            capture_case=pin(case_path), capture_baseline=case['runtime_baseline'], held_sources_before=before_sources,
            ratio_tolerance_fraction=0.02, source_producers_changed=False,
            scope='Existing telemetry only; no benchmark, control, GPU/model/replay read, or learning-speed claim.'))
    started = time.monotonic()
    records = []
    try:
        for index, offset in enumerate((0, 30, 60, 90, 120)):
            delay = started + offset - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            records.append(sample(index, started))
        spans = []
        for left, right in list(zip(records, records[1:])) + [(records[0], records[-1])]:
            a, b = left['row'], right['row']
            assert all(a[k] == b[k] for k in ('pressure_anchor_frames', 'pressure_anchor_samples', 'batch_size', 'replay_sample_cap'))
            duration = float(b['elapsed_s']) - float(a['elapsed_s'])
            df = int(b['frames']) - int(a['frames'])
            dm = int(b['measurement_frames']) - int(a['measurement_frames'])
            ds = int(b['optimized_samples']) - int(a['optimized_samples'])
            dw = int(b['replay_pressure_waits']) - int(a['replay_pressure_waits'])
            assert duration > 0 and df > dm >= 0 and ds > 0 and dw >= 0
            ratio = ds / (df-dm)
            spans.append(dict(left=left['index'], right=right['index'], actual_csv_span_s=duration,
                              eligible_frames=df-dm, optimized_samples=ds, pressure_waits=dw,
                              samples_per_eligible_frame=ratio, cap8_headroom_change=8*(df-dm)-ds,
                              samples_per_s=ds/duration, eligible_frames_per_s=(df-dm)/duration,
                              supports_cap_binding=dw>0 and 8*.98<=ratio<=8*1.02))
        after_sources = [pin(Path(path)) for path in sorted(sources)]
        assert after_sources == before_sources
        publish(OUT/'result.json', dict(status='COMPLETE_PASSIVE_OBSERVATION', samples=5, spans=spans,
                held_sources_after=after_sources,
                consistent_cap_binding_evidence=all(s['supports_cap_binding'] for s in spans),
                limitations=['Pressure waits are polling counts, not wait duration.',
                             'CSV omits measurement anchor; interval deltas do not prove exact cumulative budget.',
                             'Latest timing values and non-atomic row fields are descriptive.',
                             'No causal throughput or learning-speed improvement measured.']))
        print(json.dumps(dict(status='COMPLETE_PASSIVE_OBSERVATION', spans=spans)), flush=True)
    except BaseException as error:
        publish(OUT/'error.json', dict(status='PASSIVE_OBSERVATION_INCOMPLETE_NO_RETRY',
                error=repr(error), completed_samples=len(records)))
        raise


if __name__ == '__main__':
    main()
