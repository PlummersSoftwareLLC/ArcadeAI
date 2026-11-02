"""Exercise the actual native health interface without Torch, GPU or games."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')


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
    source = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation')
    selected = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/future-two-second-main-proof-contract-original01-preparation/source-family-original01')
    component = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/retired-api-row-projection-original01-preparation/capture-bracket-revision02')
    sources = dict(client=h.pin(selected / 'round_observer_client_proof2s_v1.py'),
        worker=h.pin(selected / 'round_observer_proof2s_v1.py'),
        health=h.pin(component / 'round_health_transport_retired_API_v4.py'),
        health_base=h.pin(component / 'round_main_health_retired_API_v4.py'),
        API_projection=h.pin(component / 'api_cached_projections_v3.py'),
        round_admission=h.pin(source / 'round_admission_proof_v2.py'),
        launcher_census=h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/post-recovery-evaluation-isolation-original01-20261027/declared-launcher-census-original34-preparation/launcher_census_v1.py')),
        durability=h.pin(source / 'buffered_raw_writer_v2.py'),
        control=h.pin(source / 'volatile_live_control_v1.py'),
        interpreter=h.pin(Path('/usr/bin/python3').resolve()))
    expected_source_sha={'client': 'b61608ccc77a452c83eda35676b42da588045e08d4b98942a4a50188e987dfb1', 'worker': 'feaeba112ba001b52a3e2e30d882899c37e20c91dc53da709599a8051d39e8cf', 'health': '46da3997f9a388f93f3473f9fc866df37e175664f73dc7ef024584a70e6f2985', 'health_base': 'bb578e92a7cb796651673ca7e0bbf43027bc5058ee88ed4ae65a973ce7460c3a', 'API_projection': 'db5f06e406bf62128ccaa46ce3155c2a90c76c31daad37d8afb2fcbfa8c36f02'}
    assert all(sources[role]['sha256']==digest for role,digest in expected_source_sha.items())
    reviewer_pin=h.pin(selected/'review_round_observer_proof2s_v1.py')
    assert reviewer_pin['sha256']=='e304bed18692308f3bf4eacfde3c2c44d4bebc1e4bf4033e836b549c8f95dea8'
    job = dict(schema='robotron-round-health-interface-engineering-only-v1',
        output=str(directory), runtime=h.pin(Path(__file__).resolve()), main_binding=case)
    jp = h.put(directory / 'engineering-native-job.json', job)
    protocol = dict(schema='robotron-native-round-main-health-declared-launcher-proof2s-protocol-v1', case=case,
                    raw_API_required=True, close_requires_final_sample=True, hot_max_gap_s=2.0, initial_samples=100,
                    raw_queue_protocol='pending-byte-digest-v2', volatile_live_tmpfs=True, source_bound_API_reconnect_projection=True, source_bound_natural_round_admission=True, source_bound_declared_launcher_census=True)
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
        until = time.monotonic()+(600 if args.mode == 'long' else 5)
        while time.monotonic() < until:
            assert not errors, errors
            time.sleep(.2)
    except Exception as failure:
        errors.append(repr(failure))
    finalizer_path = ROOT / 'tools/training_connection_lifecycle_proposal_20261023/finalize_dedicated_main_health_v1.py'
    assert hashlib.sha256(finalizer_path.read_bytes()).hexdigest() == '64c4001e3a46dd1f620bfa28b088f500bf8e9d3788a463d324cc408d7a42e6ee'
    finalizer = load('_round_bridge_unchanged_native_finalizer', finalizer_path)
    result = finalizer.finalize(guard, watcher, stopped, lock, guard.observe,
        started+4200, h, directory/'main-observations', case_already_failed=bool(errors) or args.mode == 'abort')
    if args.mode == 'long':
        errors.extend(result['errors'])
        assert not errors and result['scope_complete'] and result['writer_stopped'], errors
        reviewer = load('_async_durability_actual_reviewer', h.checked(reviewer_pin))
        raw_review = reviewer.verify(guard.lifecycle, h)
        h.put(directory / 'independent-raw-review.json', raw_review)
    else:
        assert not errors and result['scope_complete'] and result['writer_stopped'], (errors, result)
        assert result['report'] is None and result['failure'] is not None and result['errors']
        lifecycle = json.loads(h.checked(guard.lifecycle).read_bytes())
        terminal = json.loads(h.checked(lifecycle['terminal_properties']).read_bytes())
        assert terminal['Result'] == 'exit-code' and terminal['ExecMainStatus'] == '1'
        assert lifecycle['success'] is False and lifecycle['original_scope_released'] is True
        raw_review = None
    report = dict(schema='robotron-round-health-actual-native-interface-probe-v1',
        status='PASS_ENGINEERING_INTERFACE_ONLY', original_job=jp, initial=initial, mode=args.mode,
        proof_gap_contract='robotron-main-proof-gap-2s-v1',maximum_gap_s=2.0,
        independently_replayed_raw_review=raw_review,
        actual_watch_observations=len(observations), elapsed_s=time.monotonic()-started,
        actual_unchanged_native_finalizer=h.pin(finalizer_path), closure=result,
        observer_lifecycle=guard.lifecycle, sources=sources, retired_API_reviewer_source=reviewer_pin,
        main_runtime_changed=False, private_policy_or_GPU_loaded=False,
        scientific_launch_qualified=False, quality_qualified=False)
    h.put(directory/'result.json', report)
    print(json.dumps(dict(status=report['status'], elapsed_s=report['elapsed_s'],
                          watch_observations=len(observations))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--mode', choices=['long', 'abort'], required=True)
    parser.add_argument('--case', type=Path)
    parser.add_argument('--case-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.execute:
        run(args)
    else:
        print('PLAN_ONLY: no process, training, GPU, or file actions')
