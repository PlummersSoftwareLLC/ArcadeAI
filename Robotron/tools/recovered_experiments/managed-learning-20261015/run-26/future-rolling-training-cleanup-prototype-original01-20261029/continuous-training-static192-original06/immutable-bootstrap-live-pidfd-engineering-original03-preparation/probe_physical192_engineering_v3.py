"""Exercise the actual native health interface without Torch, GPU or games."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
import time

ROOT = Path('/home/dave/source/repos/ArcadeAI/Robotron')
INVENTORY_SHA = 'd8d39fcf36c6f2ff6fcd955fb99fe3bb983aa23d34412c5d985c70a90dc36de7'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args):
    directory = args.output.resolve()
    directory.mkdir(mode=0o700)
    helper_path = ROOT / 'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(helper_path.read_bytes()).hexdigest() == '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    h = load('_round_bridge_evidence_helpers', helper_path)
    case = h.pin(args.case.resolve())
    assert case['sha256'] == args.case_sha256
    source = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation')
    sources = {
        'registry': h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-immutable-bootstrap-live-pidfd-original04/continuous_physical192_registry_v4.py')),
        'health_base': h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-immutable-bootstrap-live-pidfd-original04/continuous_physical192_health_v4.py')),
        'health': h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-immutable-bootstrap-live-pidfd-original04/continuous_physical192_transport_v4.py')),
        'worker': h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-immutable-bootstrap-live-pidfd-original04/observe_continuous_physical192_v4.py')),
        'client': h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-immutable-bootstrap-live-pidfd-original04/continuous_physical192_observer_client_v4.py')),
        'durability': h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/buffered_raw_writer_v2.py')),
        'control': h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/post_recovery_evaluation/volatile_live_control_v1.py')),
        'interpreter': h.pin(Path('/usr/bin/python3.12')),
    }
    expected_source_sha = {'registry': '4bd2cd67c68a908a44c984f00f2586cd7116e6fb2ab4cf53ad8037dd2052b8a2', 'health_base': '42bfa00072a6ad7a0003fa0fea0672c997352c7e9e5f01104aa1463e0eef388a', 'health': '2d38c2ac7dfd09b148fa8db228a65a2e07541acbc5c3d4dd06251b9399327b75', 'worker': '3fddf6e8bed7492838f926e4bf103c05053f6c6efe6b0691668ee377e9968d01', 'client': '266db7465bcf6daed11782d309396a47afbd571d6c94f3b40c01fd5bff0f46da', 'durability': '5dbeb347474dd9289ae18a2de0c438820f535fa9d75badaa3cfbf82dff6c1aa5', 'control': 'a2ce55471f7ff14490553cf05871e79a0ff15c925d01441065821b0f95daade8', 'interpreter': 'c86f21d0da9290ece2d7d49a3f7ed52aed59cb029abdf0ea25c79634f6cbe960'}
    assert set(sources) == set(expected_source_sha) and all(sources[k]['sha256'] == v for k,v in expected_source_sha.items())
    reviewer_pin = h.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-immutable-bootstrap-live-pidfd-original04/review_continuous_physical192_observer_v4.py'))
    assert reviewer_pin['sha256'] == '9d4442cd4bde938923c61a22182b50261a4ef0a1b6700770d05c97d92c04fb4d'
    profile_path = Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/health-consumer-immutable-bootstrap-live-pidfd-original04/prepare_immutable_bootstrap_live_pidfd_case_v4.py')
    assert hashlib.sha256(profile_path.read_bytes()).hexdigest() == INVENTORY_SHA
    profile = load('_static_engineering_inventory', profile_path)
    binding = json.loads(h.checked(case).read_bytes())
    profile.validate_inventory(binding, h)
    job = dict(schema='robotron-original192-immutable-bootstrap-live-pidfd-health-interface-engineering-v3',
        output=str(directory), runtime=h.pin(Path(__file__).resolve()), main_binding=case)
    jp = h.put(directory / 'engineering-native-job.json', job)
    protocol = dict(schema='robotron-native-original192-immutable-bootstrap-live-pidfd-proof2s-protocol-v4', case=case,
                    raw_API_required=True, close_requires_final_sample=True, hot_max_gap_s=2.0, initial_samples=100,
                    raw_queue_protocol='pending-byte-digest-v2', volatile_live_tmpfs=True, source_bound_retired_API_projection=True, source_bound_original192_physical_bootstrap=True, source_bound_physical_original192_partition=True, immutable_original192_bootstrap_certificate=True, fresh_original_keeper_pidfd_census=True)
    client = load('_round_bridge_actual_client', h.checked(sources['client']))
    started = time.monotonic()
    guard = client.DedicatedMainHealth(job, jp, protocol, dict(main_observer=sources), h,
        started=started, deadline=started+4200, prior_groups=[])
    errors, observations = [], []
    stopped = threading.Event()
    lock = threading.Lock()
    watcher = None
    initial = None
    actual_long_work_s = None
    last_validated_long_count = None
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
        if args.mode == 'long':
            work_started = time.monotonic()
            while True:
                assert not errors, errors
                with lock:
                    count = (observations[-1] if observations else initial)['observed_samples']
                elapsed = time.monotonic()-work_started
                assert type(count) is int and count >= 100, 'Validated accepted-sample count required'
                assert 0 <= elapsed <= 1200, 'Count-bounded original long work exceeded1200s'
                if elapsed >= 600 and count >= 3000:
                    actual_long_work_s = elapsed
                    last_validated_long_count = count
                    break
                time.sleep(.2)
        else:
            until = time.monotonic()+(0 if args.mode == 'warmup' else 5)
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
    if args.mode in ('warmup','long'):
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
    report = dict(schema='robotron-original192-immutable-bootstrap-live-pidfd-health-interface-probe-v3',
        status='PASS_ENGINEERING_INTERFACE_ONLY', original_job=jp, initial=initial, mode=args.mode,
        proof_gap_contract='robotron-main-proof-gap-2s-v1',maximum_gap_s=2.0,
        independently_replayed_raw_review=raw_review,
        actual_watch_observations=len(observations), elapsed_s=time.monotonic()-started,
        long_work_contract='MINIMUM600S_AND_VALIDATED3000_SAMPLES_HARD1200S',
        long_minimum_work_s=600,long_maximum_work_s=1200,long_minimum_observed_samples=3000,
        actual_long_work_s=actual_long_work_s,last_validated_long_count=last_validated_long_count,
        actual_unchanged_native_finalizer=h.pin(finalizer_path), closure=result,
        observer_lifecycle=guard.lifecycle, sources=sources, retired_API_reviewer_source=reviewer_pin,
        main_runtime_changed=False, private_policy_or_GPU_loaded=False,
        main_health_profile='PHYSICAL_ORIGINAL192_IMMUTABLE_BOOTSTRAP_LIVE_PIDFD_V4',
        actual_logical_slot_domain=192, simultaneous192_actors_claimed=False,
        case_inventory_authority=binding['input_inventory_authority'],
        scientific_launch_qualified=False, quality_qualified=False)
    h.put(directory/'result.json', report)
    print(json.dumps(dict(status=report['status'], elapsed_s=report['elapsed_s'],
                          watch_observations=len(observations))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--mode', choices=['warmup', 'long', 'abort'], required=True)
    parser.add_argument('--case', type=Path)
    parser.add_argument('--case-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.execute:
        run(args)
    else:
        print('PLAN_ONLY: no process, training, GPU, or file actions')
