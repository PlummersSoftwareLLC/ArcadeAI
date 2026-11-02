"""Reusable passive original C2 interval watch; no scheduling or runtime changes."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
N = Path(__file__).parent
D = N / '04-candidate/diagnostic-output-original01'
OUT = None
spec = importlib.util.spec_from_file_location('_watch_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
assert h.pin(h.__file__)['sha256'] == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'

def birth(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except (FileNotFoundError, ProcessLookupError):
        return None

def read(path):
    return json.loads(path.read_bytes())

def copy_live(path, target):
    with path.open('rb') as stream:
        stat = os.fstat(stream.fileno())
        raw = stream.read(stat.st_size)
    if path.suffix == '.jsonl':
        raw = raw[:raw.rfind(b'\n') + 1]
    assert len(raw) <= 4 << 20
    with target.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 292)
        os.fsync(stream.fileno())
    return (raw, h.pin(target), dict(path=str(path), device=stat.st_dev, inode=stat.st_ino, bytes_at_open=stat.st_size, mtime_ns_at_open=stat.st_mtime_ns))

def observe(index):
    root = OUT / f'{index:02d}'
    root.mkdir(mode=448)
    for path in [N / 'original-fresh-sequence-observer-original01-intent.json', N / 'display-observer-original-intent.json', N / '04-candidate/execution-original01/root-original-identity.json', D / 'main-health-scope/execution-original01/root-original-identity.json']:
        row = read(path)
        assert birth(row['pid']) == row.get('birth', row.get('starttime_ticks'))
    raw, statuspin, producer = copy_live(D / 'status.json', root / 'native-status.raw.json')
    status = json.loads(raw)
    assert time.time() - status['observed_unix_s'] < 15 and (not status['errors'])
    cohort = status['controller']['cohort']
    boundary = status['controller']['boundary']
    slots = status['slots']
    assert sorted(map(int, slots)) == list(range(4096, 4128))
    assert boundary['ready'] is True and boundary['acknowledged'] == 32 and (not boundary['pending_client_ids'])
    assert not cohort['abandoned'] and cohort['failure_reason'] is None
    raw, startpin, startproducer = copy_live(D / 'journal/measurement_starts.jsonl', root / 'measurement-starts-prefix.raw.jsonl')
    starts = [json.loads(line) for line in raw.splitlines()]
    first = {}
    for row in starts:
        first.setdefault(row['client_slot'], row)
    assert sorted(first) == list(range(4096, 4128))
    job = read(N / '04-candidate/job.json')
    loaded = read(D / 'original-loaded-policy.json')
    policy = loaded['policy']
    assert policy['checkpoint_sha256'] == job['checkpoint']['sha256'] == 'df4314b05aceddeec263e598690fe803e32985497a0e26b38f36162452291bb4'
    assert loaded['replay_enabled'] is False and loaded['memory_is_none'] is loaded['optimizer_is_none'] is True
    assert policy['training_enabled'] is policy['replay_enabled'] is False
    assert policy['epsilon'] == policy['expert_ratio'] == 0 and policy['cohort_selection']['selector_source_sha256'] == job['quota64_source_pins']['view']['sha256']
    identities = []
    for slot, row in sorted(first.items()):
        cert = row['context']['startup_certificate']
        body = {k: v for k, v in cert.items() if k != 'identifier'}
        assert hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() == cert['identifier']
        assert cert['policy'] == policy and cert['session'] == job['sessions'][str(slot)] and (cert['connection'] == job['connections'][str(slot)])
        assert cert['slot'] == slot and cert['loaded_rom_sha256'] == job['loaded_rom_sha256']
        assert row['known_start'] is True and row['start_reason'] == 'prospective_certified_first_start_v2' and (row['journal_game_id'] in cohort['started_ids'])
        assert cert['admission'] == dict(close_unix_ns=status['fixed_admission']['close_unix_ns'], experiment=job['label'], generation=1, open_unix_ns=status['fixed_admission']['open_unix_ns'])
        assert cert['lower_before_send_unix_ns'] >= cert['admission']['open_unix_ns'] and cert['upper_after_receive_unix_ns'] <= cert['admission']['close_unix_ns']
        actor = read(D / 'actors' / str(slot) / 'original-actor.json')
        live = slots[str(slot)]
        assert birth(actor['pid']) == actor['starttime_ticks'] == live['birth'] and actor['pid'] == live['pid']
        assert actor['session'] == cert['session'] and actor['connection'] == cert['connection']
        argv = Path('/proc', str(actor['pid']), 'cmdline').read_bytes().rstrip(b'\x00').decode().split('\x00')
        assert argv == actor['argv']
        assert live['prefix_verified'] is True and live['error'] is None and (live['actual_exit'] is None) and (live['sequence'] >= 1200)
        assert live['handoff']['certificate_identifier'] == cert['identifier'] and live['handoff']['journal_game_id'] == row['journal_game_id']
        identities.append(dict(slot=slot, pid=actor['pid'], birth=actor['starttime_ticks'], certificate_identifier=cert['identifier'], journal_game_id=row['journal_game_id'], sequence=live['sequence']))
    samplepath = sorted((D / 'main-observations/samples').glob('*-original.json'))[-1]
    sample = read(samplepath)
    transport = sample['transport']
    assert time.time() - transport['observed_unix_s'] < 3
    api_raw = base64.b64decode(transport['raw_API']['base64'])
    assert hashlib.sha256(api_raw).hexdigest() == transport['raw_API']['sha256']
    api = json.loads(api_raw)
    assert api['client_count'] == 192
    mainproc = subprocess.run(['/usr/bin/python3.12', '-I', '-B', str(N.parent / 'LR125-after-protected3045-firstSave-original01-preparation-20261025/postcapture-current-main-readonly-monitor-v2.py')], capture_output=True, text=True, timeout=30)
    assert mainproc.returncode == 0, mainproc.stderr
    main = json.loads(mainproc.stdout)
    assert main['client_count'] == 192 and main['held_inputs'] == 197
    result = dict(status_snapshot=statuspin, status_producer_at_capture=producer, measurement_starts_prefix=startpin, measurement_starts_producer_at_capture=startproducer, loaded_policy=h.pin(D / 'original-loaded-policy.json'), original_job=h.pin(N / '04-candidate/job.json'), identities=identities, main_sample=h.pin(samplepath), main_sample_index=transport['index'], main_sample_observed_unix_s=transport['observed_unix_s'], main=main, cohort={k: cohort[k] for k in ['count', 'started', 'pending', 'abandoned', 'mean', 'median']}, all32_actual_MAME_births_and_argv_live=True, all32_certificate_identifiers_recomputed=True, all32_known_first_starts_joined_to_actual_admission_and_policy=True, producer_all32_1200_prefix_flags_positive=True, full_raw_ROM_and1200_pair_review_deferred_to_original_terminal_reviewer=True, quality_qualified=False, created_unix_s=time.time())
    pin = h.put(root / 'observation.json', result)
    print(json.dumps(dict(observation=pin, cohort=result['cohort'], main_sample_index=result['main_sample_index'], minimum_slot_sequence=min((row['sequence'] for row in identities)))), flush=True)
    return (result, pin)

def main():
    global OUT
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--duration-s', type=int, default=300)
    parser.add_argument('--interval-s', type=int, default=60)
    args = parser.parse_args()
    if not args.observe:
        print('PLAN_ONLY')
        return 0
    assert args.output is not None and args.output.is_absolute() and (args.output.resolve() == args.output)
    assert args.output.parent == N and (not args.output.exists())
    assert 1 <= args.interval_s <= 60 and args.interval_s <= args.duration_s <= 3600 and (args.duration_s % args.interval_s == 0)
    OUT = args.output
    OUT.mkdir(mode=448)
    h.put(OUT / 'watch-intent.json', dict(schema='robotron-readonly-original-C2-interval-watch-intent-v1', source=h.pin(__file__), base_source=h.pin(N / 'passive-original-R1-all32-watch60-original01.py'), duration_s=args.duration_s, interval_s=args.interval_s, pid=os.getpid(), birth=birth(os.getpid()), no_scheduling_or_runtime_mutation=True, created_unix_s=time.time()))
    results = []
    pins = []
    start = time.monotonic()
    transition = False
    for index in range(args.duration_s // args.interval_s + 1):
        if index:
            time.sleep(max(0, index * args.interval_s - (time.monotonic() - start)))
        current = read(D / 'status.json')
        if (D / 'result.json').exists() or current['controller'].get('complete') is True:
            transition = True
            break
        value, pin = observe(index)
        results.append(value)
        pins.append(pin)
    for prior, current in zip(results, results[1:]):
        assert current['main_sample_index'] > prior['main_sample_index']
        for a, b in zip(prior['identities'], current['identities']):
            assert all((a[key] == b[key] for key in ['slot', 'pid', 'birth', 'certificate_identifier', 'journal_game_id'])) and b['sequence'] > a['sequence']
    receipt = h.put(OUT / 'watch-receipt.json', dict(schema='robotron-readonly-original-C2-interval-watch-receipt-v2', observations=pins, elapsed_s=time.monotonic() - start, planned_duration_s=args.duration_s, observation_count=len(pins), native_terminal_or_complete_transition_observed=transition, all_observed_original32_births_argv_certificates_and_advancing_sequences_verified=bool(pins), all_observed_main192_held197_healthy=bool(pins), original_quality_cohort_validated=False, quality_qualified=False, runtime_changed=False, classification='verified_wait' if pins else 'original_transition_requires_review', created_unix_s=time.time()))
    print(json.dumps(dict(receipt=receipt, transition_observed=transition)), flush=True)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
