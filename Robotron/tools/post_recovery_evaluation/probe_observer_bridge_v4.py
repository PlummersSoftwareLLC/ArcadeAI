"""Exercise the actual native health interface without Torch, GPU or games."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
import time

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args):
    directory = args.output.resolve()
    directory.mkdir(mode=0o700)
    helper_path = ROOT / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    h = load('_round_bridge_evidence_helpers', helper_path)
    case = h.pin(args.case.resolve())
    assert case['sha256'] == args.case_sha256
    source = Path(__file__).resolve().parent
    sources = dict(client=h.pin(source / 'round_observer_client_v4.py'),
        worker=h.pin(source / 'round_observer_v4.py'),
        health=h.pin(source / 'round_health_transport_v2.py'),
        interpreter=h.pin(Path('/usr/bin/python3').resolve()))
    job = dict(schema='robotron-round-health-interface-engineering-only-v1',
        output=str(directory), runtime=h.pin(Path(__file__).resolve()), main_binding=case)
    jp = h.put(directory / 'engineering-native-job.json', job)
    protocol = dict(schema='robotron-native-round-main-health-protocol-v4', case=case,
                    raw_API_required=True, close_requires_final_sample=True, hot_max_gap_s=.5, initial_samples=100)
    client = load('_round_bridge_actual_client', h.checked(sources['client']))
    started = time.monotonic()
    guard = client.DedicatedMainHealth(job, jp, protocol, dict(main_observer=sources), h,
        started=started, deadline=started+4200, prior_groups=[])
    errors, observations = [], []
    stopped = threading.Event()
    lock = threading.Lock()
    watcher = None
    initial = None
    try:
        initial = guard.start()
        assert guard.initial['index'] == 99 and not initial['phase']['overlap_pending']

        def watch():
            while not stopped.wait(.2):
                try:
                    with lock:
                        observations.append(guard.observe())
                except Exception as failure:
                    errors.append(repr(failure))
                    stopped.set()
                    return

        watcher = threading.Thread(target=watch, name='engineering-native-health-watch')
        watcher.start()
        until = time.monotonic()+15
        while time.monotonic() < until:
            assert not errors, errors
            time.sleep(.2)
    except Exception as failure:
        errors.append(repr(failure))
    finalizer_path = ROOT / 'tools/training_connection_lifecycle_proposal_20261023/finalize_dedicated_main_health_v1.py'
    assert hashlib.sha256(finalizer_path.read_bytes()).hexdigest() == '64c4001e3a46dd1f620bfa28b088f500bf8e9d3788a463d324cc408d7a42e6ee'
    finalizer = load('_round_bridge_unchanged_native_finalizer', finalizer_path)
    result = finalizer.finalize(guard, watcher, stopped, lock, guard.observe,
        started+4200, h, directory/'main-observations', case_already_failed=bool(errors))
    errors.extend(result['errors'])
    assert not errors and result['scope_complete'] and result['writer_stopped'], errors
    report = dict(schema='robotron-round-health-actual-native-interface-probe-v1',
        status='PASS_ENGINEERING_INTERFACE_ONLY', original_job=jp, initial=initial,
        actual_watch_observations=len(observations), elapsed_s=time.monotonic()-started,
        actual_unchanged_native_finalizer=h.pin(finalizer_path), closure=result,
        observer_lifecycle=guard.lifecycle, sources=sources,
        main_runtime_changed=False, private_policy_or_GPU_loaded=False,
        scientific_launch_qualified=False, quality_qualified=False)
    h.put(directory/'result.json', report)
    print(json.dumps(dict(status=report['status'], elapsed_s=report['elapsed_s'],
                          watch_observations=len(observations))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--case', type=Path)
    parser.add_argument('--case-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.execute:
        run(args)
    else:
        print('PLAN_ONLY: no process, training, GPU, or file actions')
