"""One passive1800-second API/actor-log follow-up prefix; never qualify a policy or window."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

G = Path(__file__).resolve().parents[2]
R = G / 'logs/managed-learning-20261015/run-26'
D = R / 'LR125-survival32M-original01-preparation-20261023'


def load(name, path, sha):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    assert sys.argv[1:] == ['--observe-original-passive1800s']
    h = load('_transport_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    guard = load('_transport_guard', G / 'tools/lr125_survival_trial_proposal_20261023/window_observer.py',
        'ef7b13fc39493b5986a77718263ee2e6b51147e6361cf40c90e733644c43428a')
    binding = json.loads((D / 'activation-original01/current-main-binding.json').read_bytes())
    guard.owner_and_files(binding)
    out = D / 'passive-transport-prefix-30m-original01'
    out.mkdir(mode=0o700)
    h.put(out / 'intent.json', dict(purpose='Passive API and already-existing log observations only',
        source=h.pin(Path(__file__).resolve()), binding=h.pin(D / 'activation-original01/current-main-binding.json'),
        duration_s=1800, poll_s=.2, quality_qualified=False, original_attempt=1, no_retry=True,
        no_model_or_replay_access=True, no_control_write_or_signal=True))
    paths = {str(actor['slot']): Path(os.readlink('/proc/' + str(actor['pid']) + '/fd/1')).resolve(strict=True) for actor in binding['actors']}
    assert len(set(paths.values())) == 192 and all(path.is_relative_to(G / 'logs') for path in paths.values())
    paths['trainer_console'] = R / 'console.log'
    offsets = {key: dict(inode=path.stat().st_ino, offset=path.stat().st_size) for key, path in paths.items()}
    counts = dict(observations=0, bad_recipe_snapshots=0, log_chunks=0, wavecap_chunks=0, connection_chunks=0)
    bad_pins = []
    start = time.monotonic(); last_guard = start; last_logs = start
    observation = (out / 'all-observations.jsonl').open('xb')
    events = (out / 'all-new-log-chunks.jsonl').open('xb')

    def raw_put(name, raw):
        with (out / name).open('xb') as stream:
            stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        return h.pin(out / name)

    def write(stream, value):
        stream.write((json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n').encode())
        assert stream.tell() < 32 << 20

    error = None
    try:
        while time.monotonic() - start < 1800:
            tick = time.monotonic(); wall = time.time()
            with urllib.request.urlopen('http://127.0.0.1:8771/api/now', timeout=5) as response:
                raw = response.read((2 << 20) + 1)
            assert len(raw) <= 2 << 20
            api = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            predicates = dict(client_count=api['client_count'] == 192,
                training_enabled=api['training_enabled'] is True,
                measurement_inactive=api['measurement_active'] is False,
                experiment=api['managed_experiment'] == binding['experiment'], lr=api['lr'] == 6.25e-6)
            row = dict(observed_unix_s=wall, elapsed_s=tick - start,
                API={key: api[key] for key in ('ts', 'client_count', 'training_enabled', 'measurement_active',
                    'managed_experiment', 'lr', 'learner_frame_count', 'training_steps', 'optimized_samples')},
                all_five_recipe_predicates=predicates,
                missing_API_slots=sorted(set(range(192)) - {r['client_slot'] for r in api['client_rows']}))
            if not all(predicates.values()) or row['missing_API_slots']:
                counts['bad_recipe_snapshots'] += 1
                pin = raw_put(f"bad-recipe-{counts['bad_recipe_snapshots']:04d}-API.raw.json", raw)
                bad_pins.append(pin); row['full_original_API'] = pin
            write(observation, row)
            counts['observations'] += 1
            if counts['observations'] == 1:
                raw_put('initial-API.raw.json', raw)
            if tick - last_guard >= 5:
                guard.owner_and_files(binding); last_guard = tick
            if tick - last_logs >= .5:
                for key, path in paths.items():
                    with path.open('rb') as stream:
                        st = os.fstat(stream.fileno()); before = offsets[key]
                        offset_start = before['offset']
                        assert st.st_ino == before['inode'] and st.st_size >= before['offset']
                        assert st.st_size - before['offset'] <= 256 << 10
                        stream.seek(before['offset']); data = stream.read(st.st_size - before['offset'])
                    offsets[key]['offset'] = st.st_size
                    if data:
                        text = data.decode('utf-8', errors='strict')
                        write(events, dict(observed_unix_s=time.time(), source=key, path=str(path),
                            offset_start=offset_start, offset_end=st.st_size, text=text))
                        counts['log_chunks'] += 1
                        counts['wavecap_chunks'] += '[WAVECAP]' in text
                        counts['connection_chunks'] += ('disconnected' in text or 'connection opened' in text)
                last_logs = tick
            time.sleep(max(0, .2 - (time.monotonic() - tick)))
        guard.owner_and_files(binding)
        raw_put('final-API.raw.json', raw)
    except BaseException as exc:
        error = repr(exc)
    finally:
        for stream in (observation, events):
            stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno()); stream.close()
    report = dict(schema='robotron-passive-transport-prefix-v1',
        status='OBSERVATIONS_COMPLETE' if error is None else 'FAILED_DIAGNOSTIC_PRESERVED', error=error,
        elapsed_s=time.monotonic() - start, counts=counts, failing_original_API_responses=bad_pins,
        all_observations=h.pin(out / 'all-observations.jsonl'), all_new_log_chunks=h.pin(out / 'all-new-log-chunks.jsonl'),
        only_future_passive_diagnosis=True, original_failed32M_window_requalified=False,
        policy_quality_or_learning_gain_verified=False, source_or_control_changed=False,
        trainer_or_actor_signaled_or_restarted=False, created_unix_s=time.time())
    pin = h.put(out / 'readback.json', report)
    print(json.dumps(dict(readback=pin, status=report['status'], counts=counts)), flush=True)
    return 0 if error is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
