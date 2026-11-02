"""Finite read-only Main connection capture; never admits or closes a client.

This is diagnostic sampling, not a scientific evaluator or a health verdict.
Missing a short overlap does not prove that no overlap occurred.
"""
import argparse
from collections import Counter, deque
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback
import urllib.parse
import urllib.request

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def get_json(path):
    with urllib.request.urlopen('http://127.0.0.1:8771' + path, timeout=3) as response:
        raw = response.read((2 << 20) + 1)
    if len(raw) > 2 << 20:
        raise ValueError('Bounded local diagnostic response exceeded')
    return json.loads(raw)


def inspect_slots(snapshot, slots, physical, h):
    """Keep real failures as failures; no API-CID-to-PID inference."""
    evidence = {}
    for slot in slots:
        row = snapshot['fleet']['slots'].get(str(slot))
        if row is None:
            evidence[str(slot)] = dict(error='Slot outside original membership')
            continue
        result = dict(original_pid=row['original_pid'], original_birth=row['original_birth'],
                      fleet_state=row['state'], binding=row['current_physical_binding'])
        try:
            result['retained_binding'] = json.loads(h.checked(row['current_physical_binding']).read_text())
            old_token = result['retained_binding']['data']['connection']['token']
            try:
                result['retained_binding_cleanup'] = get_json('/api/connection_cleanup_token?' +
                    urllib.parse.urlencode({'token': old_token}))
            except Exception:
                result['retained_binding_cleanup_error'] = traceback.format_exc()
            actor = physical.actor(row['original_pid'])
            allowed = result['retained_binding']['data']['actor']['environment']
            actor['environment'] = {k: actor['environment'].get(k) for k in allowed}
            result['actor'] = actor
            result['original_birth_matches'] = actor['birth'] == row['original_birth']
        except Exception:
            result['actor_error'] = traceback.format_exc()
        result['connections'] = []
        for connection in snapshot['connections']['connections']:
            if connection['client_slot'] != slot:
                continue
            proof = dict(identity=connection)
            try:
                proof['process_owned_TCP'] = physical.tcp_binding(
                    row['original_pid'], connection['socket_endpoints'])
            except Exception:
                proof['TCP_error'] = traceback.format_exc()
            try:
                proof['cleanup'] = get_json('/api/connection_cleanup_token?' +
                                            urllib.parse.urlencode({'token': connection['token']}))
            except Exception:
                proof['cleanup_error'] = traceback.format_exc()
            result['connections'].append(proof)
        evidence[str(slot)] = result
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--job-sha256')
    args = parser.parse_args()
    if not args.execute:
        parser.print_help()
        return 0
    assert args.job and hashlib.sha256(args.job.read_bytes()).hexdigest() == args.job_sha256
    job = json.loads(args.job.read_text())
    assert job['duration_s'] == 180 and job['interval_s'] == 0.1 and job['after_rejection_s'] == 10
    h = load('_overlap_capture_h', G / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h.checked(job['runtime'])
    health = load('_overlap_capture_guard', h.checked(job['health_source']))
    physical = load('_overlap_capture_physical', h.checked(job['current_fleet']['physical_helper']))
    membership = json.loads(h.checked(job['current_fleet']['original_membership']).read_text())
    roles = json.loads(h.checked(job['current_fleet']['rolemap']).read_text())['slot_eval']
    output = Path(job['output'])
    output.mkdir(mode=0o700)
    owner = h.put(output / 'original-owner.json', dict(
        pid=os.getpid(), birth=physical.birth(os.getpid())['birth'], job=h.pin(args.job),
        source=h.pin(Path(__file__)), read_only=True, child_scope_created=False))
    print(json.dumps(dict(started=True, owner=owner)), flush=True)
    begin = time.monotonic()
    deadline = begin + job['duration_s']
    next_report = begin + 15
    recent = deque(maxlen=3)
    captured = []
    polls = 0
    first_rejection = None
    interesting_slots = set()
    rejection_types = Counter()
    error = None
    last = None
    try:
        while time.monotonic() < deadline:
            poll_begin = time.monotonic()
            raw = Path(job['current_fleet']['status_path']).read_bytes()
            assert len(raw) <= 2 << 20
            fleet = json.loads(raw)
            connections = get_json('/api/continuous_training_connections')
            snapshot = dict(observed_monotonic_s=time.monotonic(), observed_unix_s=time.time(),
                            fleet=fleet, connections=connections)
            validation_error = None
            try:
                health.retained_metadata_validation(h, output, polls, 'poll', fleet,
                    connections, job['current_fleet'], membership, roles,
                    now=snapshot['observed_unix_s'])
            except Exception as exc:
                validation_error = repr(exc)
                rejection_types[validation_error] += 1
                if first_rejection is None:
                    first_rejection = time.monotonic()
                    deadline = min(deadline, first_rejection + job['after_rejection_s'])
                    for index, previous in enumerate(recent):
                        captured.append(h.put(output / f'preceding-{index:02d}.json', previous))
                    counts = Counter(row['client_slot'] for row in connections['connections'])
                    tokens = Counter(row['token'] for row in connections['connections'])
                    interesting_slots = {slot for slot, count in counts.items()
                                         if count > 1 or str(slot) not in roles}
                    interesting_slots.update(row['client_slot'] for row in connections['connections']
                        if tokens[row['token']] > 1 or row['eval_only'] is not roles.get(str(row['client_slot'])))
                    interesting_slots.update(int(k) for k, row in fleet['slots'].items()
                                             if row['state'] in ('reconnecting_train', 'retiring_eval'))
                    snapshot['physical_at_first_rejection'] = inspect_slots(
                        snapshot, sorted(interesting_slots), physical, h)
                    print(json.dumps(dict(first_rejection=True, poll=polls,
                                          error=validation_error, slots=sorted(interesting_slots))), flush=True)
            snapshot['validation_error'] = validation_error
            if first_rejection is not None:
                captured.append(h.put(output / f'after-{polls:05d}.json', snapshot))
            recent.append(snapshot)
            last = snapshot
            polls += 1
            if time.monotonic() >= next_report:
                print(json.dumps(dict(polls=polls, elapsed_s=time.monotonic()-begin,
                                      rejection_count=sum(rejection_types.values()))), flush=True)
                next_report = time.monotonic() + 15
            time.sleep(max(0, job['interval_s'] - (time.monotonic()-poll_begin)))
        if last is not None:
            last['physical_at_end'] = inspect_slots(last, sorted(interesting_slots), physical, h)
            captured.append(h.put(output / 'last-snapshot.json', last))
    except Exception:
        error = traceback.format_exc()
    assert 'torch' not in sys.modules
    report = h.put(output / 'capture-result.json', dict(
        status=('READONLY_CAPTURE_ERROR' if error else
                'REJECTION_CAPTURED_NO_HEALTH_VERDICT' if first_rejection is not None else
                'NO_REJECTION_OBSERVED_IN_FINITE_SAMPLES'),
        error=error, owner=owner, polls=polls, elapsed_s=time.monotonic()-begin,
        rejection_types=dict(rejection_types), snapshots=captured,
        full_fleet_physical_health_qualified=False, client_or_trainer_actions_taken=False,
        GPU_or_MAME_launched=False, scientific_qualification=False, promotion=False))
    print(json.dumps(dict(result=report, error=error)), flush=True)
    return 1 if error else 0


if __name__ == '__main__':
    raise SystemExit(main())
